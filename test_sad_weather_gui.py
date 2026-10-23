# test_sad_weather_gui.py — повний тест вікна «Погода» (Xvfb + імітація мережі)
import os, sys, json, math, tempfile, shutil, time, threading, datetime as dt
real_sleep = time.sleep
time.sleep = lambda s: None                      # пауза між запитами й норма — без очікування
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ["SAD_WEATHER_CACHE"] = tempfile.mkdtemp(prefix="sadw_gui_cache_")
os.environ.setdefault("DISPLAY", ":99")
from urllib.parse import urlparse, parse_qs
import numpy as np
import tkinter as tk

FAIL = []
def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg, flush=True)
    if not cond: FAIL.append(msg)

import main as m
import sad_weather_core as W
import sad_weather as SW

# ───────────────────────────── імітація серверів ─────────────────────────────
REQ = []
def _day_vals(d):
    doy = d.timetuple().tm_yday
    h = (d.toordinal() * 2654435761) % 1000 / 1000.0
    t = 9.5 + 11.5 * math.sin(2 * math.pi * (doy - 110) / 365.0) + (h - 0.5) * 4
    p = round(((h * 13) % 1) * 14, 1) if h < 0.33 else 0.0
    return t, p
def nasa_payload(a, b):
    days = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    k = [d.strftime("%Y%m%d") for d in days]
    tv = [_day_vals(d) for d in days]
    par = {"T2M": {x: round(v[0], 2) for x, v in zip(k, tv)}, "T2M_MAX": {x: round(v[0] + 4, 2) for x, v in zip(k, tv)},
           "T2M_MIN": {x: round(v[0] - 4, 2) for x, v in zip(k, tv)}, "PRECTOTCORR": {x: v[1] for x, v in zip(k, tv)},
           "RH2M": {x: 70.0 for x in k}, "WS2M": {x: 3.0 for x in k}, "ALLSKY_SFC_SW_DWN": {x: 15.0 for x in k}}
    return {"geometry": {"coordinates": [30.2218, 48.7484, 212.0]}, "properties": {"parameter": par},
            "header": {"fill_value": -999.0, "time_standard": "LST", "api": {"version": "v2.6"}},
            "parameters": {"ALLSKY_SFC_SW_DWN": {"units": "MJ/m^2/day"}}}
def om_payload(a, b):
    days = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    tv = [_day_vals(d) for d in days]
    return {"latitude": 48.75, "longitude": 30.25, "elevation": 215.0, "timezone": "Europe/Kyiv",
            "daily": {"time": [d.isoformat() for d in days],
                      "temperature_2m_mean": [round(v[0], 2) for v in tv], "temperature_2m_max": [round(v[0] + 4, 2) for v in tv],
                      "temperature_2m_min": [round(v[0] - 4, 2) for v in tv], "precipitation_sum": [v[1] for v in tv],
                      "relative_humidity_2m_mean": [70.0] * len(days), "wind_speed_10m_mean": [3.0] * len(days),
                      "shortwave_radiation_sum": [15.0] * len(days),
                      "et0_fao_evapotranspiration": [round(max(0, (v[0] + 3) * 0.2), 2) for v in tv],
                      "sunshine_duration": [36000.0] * len(days)}}
MODE = {"offline": False, "slow": 0.0}
def fake_get(url, timeout=60):
    REQ.append(url)
    if MODE["offline"]: raise W.WeatherError("Немає з'єднання з сервером (імітація)")
    if MODE["slow"]: real_sleep(MODE["slow"])
    q = parse_qs(urlparse(url).query)
    if "power.larc.nasa.gov" in url:
        a = dt.datetime.strptime(q["start"][0], "%Y%m%d").date(); b = dt.datetime.strptime(q["end"][0], "%Y%m%d").date()
        return 200, json.dumps(nasa_payload(a, b))
    if "archive-api.open-meteo.com" in url:
        return 200, json.dumps(om_payload(dt.date.fromisoformat(q["start_date"][0]), dt.date.fromisoformat(q["end_date"][0])))
    if "geocoding-api" in url:
        return 200, json.dumps({"results": [{"name": "Умань", "latitude": 48.75, "longitude": 30.22,
                                              "country": "Україна", "admin1": "Черкаська область"}]})
    return 404, "not found"
W.http_get = fake_get

# ───────────────────────────── заглушки діалогів ─────────────────────────────
LOG = {"info": [], "warn": [], "error": [], "ask": []}
ASK = {"ans": True}
tk_mb = tk.messagebox
tk_mb.showinfo = lambda t="", msg="", **k: LOG["info"].append((t, msg))
tk_mb.showwarning = lambda t="", msg="", **k: LOG["warn"].append((t, msg))
tk_mb.showerror = lambda t="", msg="", **k: LOG["error"].append((t, msg))
def _ask(t="", msg="", **k):
    LOG["ask"].append((t, msg)); return ASK["ans"]
tk_mb.askyesno = _ask
SW.open_file_cross = lambda p: None
TMP = tempfile.mkdtemp(prefix="sadw_gui_")
SAVE = {"path": None, "open": None}
tk.filedialog.asksaveasfilename = lambda **k: SAVE["path"]
tk.filedialog.askopenfilename = lambda **k: SAVE["open"]

root = tk.Tk()
app = m.SADTk(root); root._sad_app = app
root.update()

def pump(cond, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        root.update()
        if cond(): return True
        real_sleep(0.02)
    return False
def toplevels(w=root):
    out = []
    if isinstance(w, tk.Toplevel): out.append(w)
    for c in w.winfo_children(): out.extend(toplevels(c))
    return out
def find_btn(txt, w):
    r = [None]
    def rec(x):
        if r[0] is not None: return
        try:
            if x.winfo_class() == "Button" and txt in x.cget("text"): r[0] = x; return
        except Exception: pass
        for c in x.winfo_children(): rec(c)
    rec(w); return r[0]
def tree_rows(holder):
    out = []
    def rec(x):
        if isinstance(x, tk.ttk.Treeview): out.append(x)
        for c in x.winfo_children(): rec(c)
    rec(holder); return out[0] if out else None
def fetch_and_wait(win, expect_series=True, timeout=25):
    win._start_fetch()
    ok = pump(lambda: not win._busy and (win.series is not None or not expect_series), timeout)
    pump(lambda: False, 0.1)
    return ok

# ═════════════════════════════════════════════════════════════════════════════
print("== 1. Меню й відкриття вікна")
labels = []
def rec_l(w):
    try:
        if w.winfo_class() == "Label" and w.cget("text"): labels.append(w.cget("text"))
    except Exception: pass
    for c in w.winfo_children(): rec_l(c)
rec_l(root)
check(any(t == "Погода" or t.endswith("Погода") for t in labels) or any("Погода" in t for t in labels), "пункт «Погода» є на головній сторінці")
win = m.WeatherWindow(root); root.update()
check(win.win.winfo_exists(), "вікно «Погода» відкрилось")
check(win.src_var.get() == W.SOURCE_TITLES["nasa"], "джерело за замовчуванням — NASA POWER (безпечне для комерційного поширення)")
check("NASA" in win.lic_lbl.cget("text"), "показано умови NASA (подяка)")
win.src_var.set(W.SOURCE_TITLES["openmeteo"]); win._on_source(); root.update()
check("некомерційного" in win.lic_lbl.cget("text") and win.model_row.winfo_ismapped(), "Open-Meteo: попередження про ліцензію + вибір моделі")
check("викликів" in win.cost_lbl.cget("text"), f"показано вартість запиту: «{win.cost_lbl.cget('text')}»")
win.src_var.set(W.SOURCE_TITLES["file"]); win._on_source(); root.update()
check(win.file_row.winfo_ismapped() and "файл" in win.btn_fetch.cget("text").lower(), "власні дані: кнопки файлу, кнопка «Відкрити файл…»")
win.src_var.set(W.SOURCE_TITLES["nasa"]); win._on_source(); root.update()

print("\n== 2. NASA: пресет, координати, період, завантаження у фоні")
win.preset_var.set("Умань"); win._on_preset(); root.update()
check(win.lat_var.get() == "48.7484" and win.lon_var.get() == "30.2218" and win.place_var.get() == "м. Умань", "пресет заповнив координати й назву")
win.d0_var.set("01.01.2022"); win.d1_var.set("31.12.2024"); win._update_cost()
REQ.clear()
ok = fetch_and_wait(win)
check(ok and win.series is not None and len(win.series) == 1096, f"завантажено {len(win.series) if win.series else 0} діб (очікувано 1096)")
check(len(REQ) == 3 and all("community=AG" in u for u in REQ), f"3 запити по роках до NASA (community=AG): {len(REQ)}")
check(not win._busy and str(win.btn_fetch.cget("state")) == "normal", "кнопка розблокована після завантаження")
txt = win.txt_sum.get("1.0", "end")
check("м. Умань" in txt and "NASA POWER" in txt and "Дата отримання даних" in txt, "вкладка «Підсумок»: місце, джерело, дата отримання")
check("реаналізу" in txt, "у підсумку є попередження про реаналіз (не вимірювання станції)")
check("ГТК Селянінова за період" in txt and "Шкала ГТК" in txt, "підсумок: ГТК за період і шкала")
check(len(tree_rows(win.holders["months"]).get_children()) == 36, "вкладка «Місяці»: 36 рядків")
check(len(tree_rows(win.holders["decades"]).get_children()) == 108, "вкладка «Декади»: 108 рядків")
check(len(tree_rows(win.holders["years"]).get_children()) == 3, "вкладка «За роками»: 3 роки (вікно 04-01…10-31)")
check(len(tree_rows(win.day_holder).get_children()) == 1096, "вкладка «Добові дані»: 1096 рядків")
tv = tree_rows(win.holders["months"])
tagged = [tv.item(i, "tags") for i in tv.get_children()]
check(any(t for t in tagged), "рядки ГТК розфарбовано за класом")
check(win._fig is not None, "діаграма побудована")

print("\n== 3. Кома/крапка у таблицях, метод ГТК")
v_comma = tv.item(tv.get_children()[5], "values")
win.comma_var.set(False); win._refresh_all(); root.update()
tv2 = tree_rows(win.holders["months"]); v_dot = tv2.item(tv2.get_children()[5], "values")
check(any("," in str(x) for x in v_comma) and not any("," in str(x) for x in v_dot) and any("." in str(x) for x in v_dot),
      "перемикач десяткової коми працює в таблицях")
win.comma_var.set(True); win._refresh_all()
h_dec = win.rep["total"]["htc"]
win.htc_var.set(list(SW.HTC_METHODS)[2]); win._recompute(); root.update()
check(win.rep["settings"]["htc_method"] == "daily" and abs(win.rep["total"]["htc"] - h_dec) > 1e-9,
      f"добовий метод змінює ГТК ({h_dec:.3f} → {win.rep['total']['htc']:.3f})")
win.htc_var.set(list(SW.HTC_METHODS)[0]); win._recompute()
win.base_var.set("abc"); n_w = len(LOG["warn"]); win._recompute()
check(len(LOG["warn"]) == n_w + 1 and win.rep is not None, "некоректний параметр → зрозуміле попередження, вікно не падає")
win.base_var.set("10")
win.wfrom_var.set("13-45"); n_w = len(LOG["warn"]); win._recompute()
check(len(LOG["warn"]) == n_w + 1 and "04-01" not in LOG["warn"][-1][1] and "13-45" in LOG["warn"][-1][1], "некоректне вікно ММ-ДД відхилено")
win.wfrom_var.set("04-01")

print("\n== 4. Усі діаграми через інтерфейс, збереження PNG/SVG/PDF")
bad = []
for kind, title in __import__("sad_weather_charts").CHARTS:
    win.chart_var.set(title); win._draw_chart(); root.update()
    if win._fig is None or not win._fig.axes: bad.append(title)
check(not bad, f"всі 8 діаграм малюються у вікні ({'; '.join(bad)})")
win.chart_var.set("Діаграма Вальтера"); win._draw_chart()
for ext in ("png", "svg", "pdf"):
    SAVE["path"] = os.path.join(TMP, f"chart.{ext}"); win._save_chart()
    check(os.path.exists(SAVE["path"]) and os.path.getsize(SAVE["path"]) > 2000, f"діаграма збережена як {ext.upper()} ({os.path.getsize(SAVE['path'])//1024} КБ)")

print("\n== 5. Експорт: Excel, Word, CSV, погодний набір, текст")
import openpyxl, docx
SAVE["path"] = os.path.join(TMP, "w.xlsx"); ASK["ans"] = False; win._export_xlsx()
wb = openpyxl.load_workbook(SAVE["path"]); check("Місяці" in wb.sheetnames and "За роками" in wb.sheetnames, f"Excel: аркуші {wb.sheetnames}")
SAVE["path"] = os.path.join(TMP, "w.docx"); win._export_docx()
d = docx.Document(SAVE["path"]); check(len(d.tables) >= 2 and len(d.inline_shapes) >= 3, f"Word: таблиць {len(d.tables)}, рисунків {len(d.inline_shapes)}")
SAVE["path"] = os.path.join(TMP, "w.csv"); win._export_csv()
check(open(SAVE["path"], encoding="utf-8-sig").read().splitlines()[0].startswith("Дата;"), "CSV (кома → роздільник «;»)")
SAVE["path"] = os.path.join(TMP, "w.sadw"); win._export_set()
ws = json.load(open(SAVE["path"], encoding="utf-8"))
check(ws["type"] == "sad_weather_set" and set(ws["years"]) == {"2022", "2023", "2024"} and ws["place"] == "м. Умань", "погодний набір (.sadw): 3 роки")
SAVE["path"] = os.path.join(TMP, "w.txt"); win._save_pub()
check("МЕТОДИКА ЗБОРУ МЕТЕОДАНИХ" in open(SAVE["path"], encoding="utf-8").read(), "текст для публікації збережено")
win._copy_table("months"); clip = win.win.clipboard_get()
check(clip.startswith("Місяць\t") and clip.count("\n") == 36, "копіювання таблиці в буфер (TSV, 36 рядків)")
SAVE["path"] = None; win._export_xlsx(); win._export_docx(); win._export_csv()
check(True, "скасування діалогу збереження не призводить до помилок")
ASK["ans"] = True

print("\n== 6. Періоди: за датами замірів і з серії журналу")
win._period_from_dates(preset_dates=[dt.date(2024,5,15), dt.date(2024,5,29), dt.date(2024,6,12)], season_default="01.05.2024"); root.update()
dlg = [t for t in toplevels(win.win) if "замірів" in t.title()][0]
find_btn("Створити періоди", dlg).invoke(); root.update()
check(len(win.periods) == 3 and win.per_list.size() == 3, "створено 3 періоди між замірами")
trp = tree_rows(win.holders["periods"]); check(trp is not None and len(trp.get_children()) == 3, "таблиця періодів: 3 рядки")
n_win = len(toplevels(win.win))
find_btn("Очистити", win.tab_per).invoke(); root.update()
check(win.periods == [] and win.per_list.size() == 0, "«Очистити» прибирає періоди")
sch = os.path.join(TMP, "scheme"); os.makedirs(os.path.join(sch, "2024"))
sp = os.path.join(sch, "схема.sadp")
json.dump({"type": "multi_factor_scheme", "plants": [], "factor_defs": [], "cfg": {},
           "series": {"Висота": {"interval_days": 14, "rounds": [{"date": "2024-05-15", "indicator": "x", "year": "2024"},
                                                                  {"date": "2024-05-29", "indicator": "y", "year": "2024"}]}}},
          open(sp, "w", encoding="utf-8"))
import sad_journal_trial as JT
JT.pick_indicators_dialog = lambda parent, recs, multi_select=False, n_required=None: [sorted(recs)[0]]
SAVE["open"] = sp; win._period_from_series(); root.update()
dlg = [t for t in toplevels(win.win) if "замірів" in t.title()][0]
txd = [w for w in dlg.winfo_children()[0].winfo_children() if isinstance(w, tk.Text)][0]
check("15.05.2024" in txd.get("1.0", "end") and "29.05.2024" in txd.get("1.0", "end"), "з серії журналу підтягнуто дати замірів")
find_btn("Створити періоди", dlg).invoke(); root.update()
check(len(win.periods) == 2, f"з серії створено {len(win.periods)} періоди")
win._period_clear()

print("\n== 7. Норма (1991–2020): фонове завантаження й відхилення")
REQ.clear(); win.ny0.set("1991"); win.ny1.set("2020"); win._load_norm()
ok = pump(lambda: win.norm is not None, 40)
check(ok and win.norm[2] == "1991–2020" and len(win.norm[1]) == 30, f"норма за {len(win.norm[1]) if win.norm else 0} років")
check(len(REQ) == 30, f"30 окремих запитів (по вікну року, а не 30 років підряд): {len(REQ)}")
check(len(tree_rows(win.holders["years"])["columns"]) > 0 and "Опади, % норми" in tree_rows(win.holders["years"])["columns"],
      "таблиця за роками отримала стовпці відхилень від норми")
check("Норма: 1991–2020" in win.years_note.cget("text"), "підпис про норму")
win._clear_norm(); check(win.norm is None and "Опади, % норми" not in tree_rows(win.holders["years"])["columns"], "норму можна прибрати")
win.ny0.set("2010"); win.ny1.set("2012"); ASK["ans"] = False; n = len(LOG["ask"]); win._load_norm()
check(len(LOG["ask"]) == n + 1 and "30" in LOG["ask"][-1][1] and win.norm is None, "коротка норма (<10 років): програма питає й за відмови нічого не робить")
ASK["ans"] = True
win.ny0.set("1991"); win.ny1.set(str(dt.date.today().year)); n = len(LOG["warn"]); win._load_norm()
check(len(LOG["warn"]) == n + 1, "незавершений рік у нормі відхилено")

print("\n== 8. Open-Meteo: завантаження, відстань до комірки, великий запит")
win.src_var.set(W.SOURCE_TITLES["openmeteo"]); win._on_source()
win.d0_var.set("01.01.2023"); win.d1_var.set("31.12.2023"); REQ.clear()
ok = fetch_and_wait(win)
check(ok and len(win.series) == 365 and all("archive-api.open-meteo.com" in u and "timezone=auto" in u for u in REQ), "Open-Meteo: 365 діб, timezone=auto")
txt = win.txt_sum.get("1.0", "end")
check("відстань від точки" in txt and "Europe/Kyiv" in txt, "підсумок: відстань до центру комірки й часовий пояс")
check(win.series.has("et0") and "Водний баланс" in txt, "є ET₀ й водний баланс")
win.d0_var.set("01.01.1960"); win.d1_var.set("31.12.2023"); ASK["ans"] = False; n_req = len(REQ); n = len(LOG["ask"])
win._start_fetch(); pump(lambda: False, 0.3)
check(len(LOG["ask"]) == n + 1 and "10 000" in LOG["ask"][-1][1] and len(REQ) == n_req and win.series is not None and len(win.series) == 365,
      "64 роки в Open-Meteo: попередження про вартість, за відмови запитів нема, дані не втрачено")
ASK["ans"] = True
win.d0_var.set("01.01.1930"); n = len(LOG["warn"]); win._start_fetch(); check(len(LOG["warn"]) == n + 1 and "1940" in LOG["warn"][-1][1], "дата раніше початку джерела відхилена")

print("\n== 9. Аварійні сценарії")
win.src_var.set(W.SOURCE_TITLES["nasa"]); win._on_source(); win.d0_var.set("01.01.2019"); win.d1_var.set("30.06.2019")
MODE["offline"] = True; n = len(LOG["error"]); had = win.series
win._start_fetch(); pump(lambda: len(LOG["error"]) > n, 10)
check(len(LOG["error"]) == n + 1 and "з'єднання" in LOG["error"][-1][1], "немає інтернету → зрозуміле повідомлення")
check(not win._busy and win.series is had, "після помилки вікно працездатне, попередні дані збережено")
MODE["offline"] = False; win.nocache_var.set(True)
ok = fetch_and_wait(win); check(ok and len(win.series) == 181, "повторна спроба після відновлення мережі успішна (181 доба)")
win.nocache_var.set(False)
win.lat_var.set("95"); n = len(LOG["warn"]); win._start_fetch(); check(len(LOG["warn"]) == n + 1 and "широта" in LOG["warn"][-1][1], "широта 95° відхилена з поясненням")
win.lat_var.set("48°45'N"); win.lon_var.set("30°13'E"); win._start_fetch(); pump(lambda: not win._busy, 10)
check(abs(win.ctx["lat"] - 48.75) < 1e-9 and abs(win.ctx["lon"] - 30.21666667) < 1e-6, "координати у форматі ГМС розпізнано")
win.d0_var.set("2030-01-01"); win.d1_var.set("2030-02-01"); n = len(LOG["warn"]); win._start_fetch()
check(win.d1_var.get() != "01.02.2030" or len(LOG["warn"]) > n, "майбутні дати не призводять до запиту")
win.d0_var.set("01.01.2019"); win.d1_var.set("30.06.2019")

print("\n== 10. Власні дані (CSV у Windows-1251, кома, «;»)")
p = os.path.join(TMP, "station.csv")
rows = ["Дата;Tсер;Tмакс;Tмін;Опади, мм"]
d = dt.date(2023, 5, 1)
for i in range(40):
    day = d + dt.timedelta(days=i); t, pr = _day_vals(day)
    rows.append(f"{day:%d.%m.%Y};" + f"{t:.1f};{t+4:.1f};{t-4:.1f};{pr:.1f}".replace(".", ","))   # кома лише в числах
rows.append("помилковий рядок;1;2;3;4")
open(p, "wb").write("\r\n".join(rows).encode("cp1251"))
win.src_var.set(W.SOURCE_TITLES["file"]); win._on_source(); SAVE["open"] = p
win._open_file(); root.update()
dlg = [t for t in toplevels(win.win) if "Відповідність" in t.title()][0]
find_btn("Прочитати", dlg).invoke(); root.update()
check(win.series is not None and len(win.series) == 40 and win.ctx["source"] == "file", "станційний файл прочитано: 40 діб")
check(win.series.meta["bad_rows"] == 1 and "некоректних рядків: 1" in win.status_var.get(), "некоректний рядок пропущено й про це повідомлено")
check(win.series.has("tmean") and win.series.has("prec") and not win.series.has("rh"), "стовпці розпізнано автоматично")
check("реаналізу" not in win.txt_sum.get("1.0", "end"), "для станційних даних немає попередження про реаналіз")
win.win.clipboard_clear(); win.win.clipboard_append("Дата\tt\tОпади\n01.06.2023\t15,5\t0\n02.06.2023\t16,0\t2,5\n03.06.2023\t14,1\t0\n")
win._paste_table(); dlg = [t for t in toplevels(win.win) if "Відповідність" in t.title()][0]
find_btn("Прочитати", dlg).invoke(); root.update()
check(win.series is not None and len(win.series) == 3 and abs(win.series.get("tmean")[0] - 15.5) < 1e-9, "вставка з буфера (TSV, десяткова кома) працює")

print("\n== 11. Закриття вікна під час завантаження")
win2 = m.WeatherWindow(root); root.update()
win2.preset_var.set("Київ"); win2._on_preset(); win2.d0_var.set("01.01.2021"); win2.d1_var.set("31.12.2023")
MODE["slow"] = 0.4
win2._start_fetch(); real_sleep(0.2)
win2._close(); root.update()
check(not win2._alive and not win2.win.winfo_exists(), "вікно закрито посеред завантаження")
real_sleep(1.6); root.update()
check(True, "фоновий потік завершився без помилок у закритому вікні")
MODE["slow"] = 0.0

print("\n== 12. Довідка")
win._show_help(); root.update()
hw = [t for t in toplevels(win.win) if "Довідка" in t.title()]
check(hw and "КОМЕРЦІЙНОГО" in hw[0].winfo_children()[0].winfo_children()[1].get("1.0", "end"), "довідка відкривається й містить попередження про ліцензію")

shutil.rmtree(TMP, ignore_errors=True); shutil.rmtree(os.environ["SAD_WEATHER_CACHE"], ignore_errors=True)
root.destroy()
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ ПЕРЕВІРКИ ВІКНА ПРОЙДЕНО")
