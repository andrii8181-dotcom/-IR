# test_sad_weather_export.py — перевірка експорту: файли записуються й ЧИТАЮТЬСЯ НАЗАД
import os, sys, re, math, tempfile, shutil, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sad_weather_core as W, sad_weather_charts as C, sad_weather_export as X

FAIL = []
def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond: FAIL.append(msg)

def synth(d0, d1, seed=1):
    rng = np.random.default_rng(seed)
    dts = []; cur = d0
    while cur <= d1: dts.append(cur); cur += dt.timedelta(days=1)
    doy = np.array([d.timetuple().tm_yday for d in dts], float)
    tm = 9.5 + 11.5 * np.sin(2*np.pi*(doy-110)/365.0) + rng.normal(0, 2.2, len(dts))
    pr = np.round(np.where(rng.random(len(dts)) < 0.30, rng.gamma(1.1, 5.0, len(dts)), 0.0), 1)
    s = W.DailySeries(dts, {"tmean": tm, "tmax": tm+4.5, "tmin": tm-4.5, "prec": pr,
                            "rh": np.full(len(dts), 70.0), "wind": np.full(len(dts), 3.0),
                            "rad": np.full(len(dts), 15.0), "et0": np.maximum(0, (tm+3)*0.2)})
    s.meta.update({"source": "openmeteo", "model": "era5", "timezone": "Europe/Kyiv",
                   "grid_lat": 48.75, "grid_lon": 30.25, "grid_elevation_m": 215.0,
                   "retrieved_at": "2026-10-09T12:00:00"})
    return s

tmp = tempfile.mkdtemp(prefix="sadw_exp_")
s = synth(dt.date(2021,1,1), dt.date(2024,12,31))
st = W.default_settings()
okw = {y: sub for y, _, _, sub in W.year_windows(s, st["window"])[0]}
nrm, used = W.normal_from_years(okw)
periods = W.intervals_from_dates([dt.date(2024,5,15), dt.date(2024,6,12)], dt.date(2024,5,1)) + [
    ("поза даними", dt.date(2030,1,1), dt.date(2030,1,5)),
    ("частково", dt.date(2024,12,25), dt.date(2025,1,10))]
rep = W.build_report(s, st, norm=(nrm, used, "2021–2024"), periods=periods)
meta = X.make_meta(rep, "Умань, дослідне поле", 48.7484, 30.2218, "openmeteo")
pub = X.publication_text(rep, "Умань, дослідне поле", 48.7484, 30.2218, "openmeteo")

print("== 1. Метадані й текст для публікації")
md = dict(meta)
check(md["Джерело даних"].startswith("Open-Meteo") and "48.7484" in md["Координати точки"], "джерело й координати")
check("відстань" in md["Центр комірки сітки"] and "км" in md["Центр комірки сітки"], "відстань до центру комірки сітки показано")
dist = W.haversine_km(48.7484, 30.2218, 48.75, 30.25)
check(f"{dist:.1f}" in md["Центр комірки сітки"], f"відстань {dist:.1f} км обчислена коректно")
check(md["Дата отримання даних"] == "09.10.2026 12:00", f"дата отримання даних по-українськи: {md['Дата отримання даних']}")
for need in ("МЕТОДИКА ЗБОРУ МЕТЕОДАНИХ", "ДЖЕРЕЛА ТА ПОДЯКА", "10.5281/ZENODO.7970649", "УМОВИ ВИКОРИСТАННЯ",
             "некомерційного", "ШКАЛА ВОЛОГОЗАБЕЗПЕЧЕНОСТІ", "Польовий А.М."):
    check(need in pub, f"текст містить «{need}»")

print("\n== 2. Рядкові таблиці (десяткова кома, компактність)")
sp = X.spec_months(rep)
h_full, r_full, c_full = X.to_strings(sp, comma=True, compact=False)
h_cmp, r_cmp, c_cmp = X.to_strings(sp, comma=True, compact=True)
check(len(h_cmp) < len(h_full) and "ГТК" in h_cmp and "Умови зволоження" in h_cmp, "компактна таблиця коротша й містить ГТК")
check(not any(re.fullmatch(r"-?\d+\.\d+", c) for row in r_full for c in row), "жодне число в таблиці не має десяткової крапки (лише кома)")
i_apr = next(i for i, r in enumerate(r_full) if r[0].startswith("кві 2022"))
check(any("," in c for c in r_full[i_apr]), "кома в числах рядка")
jan = next(i for i, r in enumerate(r_full) if r[0].startswith("січ 2022"))
check(r_full[jan][h_full.index("ГТК")] == "—" and c_full[jan] == "na", "січень: ГТК «—» (немає активних температур)")
check(any(c in ("d1","d2","d3","d4","ok","wet") for c in c_full), "для активних місяців є клас ГТК")
check(X.clipboard_text(sp, comma=True).count("\t") >= len(h_full) - 1, "TSV для буфера")
yr_spec = X.spec_years(rep); yh, yr, yc = X.to_strings(yr_spec, True, False)
check("Опади, % норми" in yh and "Δt від норми, °C" in yh, "таблиця за роками містить стовпці норми й аномалій")
ph, pr_, pc = X.to_strings(X.spec_periods(rep), True, False)
check(pr_[-2][4] == "немає даних" and pr_[0][4] != "немає даних", "період повністю поза даними → «немає даних», решта — числа")
check(pr_[-1][3] == "7 з 17" and pr_[-1][4] != "немає даних", f"частково покритий період позначено «{pr_[-1][3]}» (7 діб із 17), а не мовчки")
check(pr_[0][3] == "15", "повністю покритий період — просто число діб")
tot = X.spec_total(rep); th, trs, _ = X.to_strings(tot, True)
check(any("ГТК Селянінова" in r[0] for r in trs) and any("Водний баланс" in r[0] for r in trs), "зведена таблиця: ГТК і водний баланс (є ET₀)")

print("\n== 3. CSV добових даних")
p_csv = os.path.join(tmp, "daily.csv")
X.export_csv_daily(p_csv, s, comma=True, sep=";")
raw = open(p_csv, "rb").read()
check(raw[:3] == b"\xef\xbb\xbf", "UTF-8 із BOM (Excel читає кирилицю)")
lines = raw.decode("utf-8-sig").split("\r\n")
check(lines[0].startswith("Дата;tсер, °C;") and lines[1].startswith("01.01.2021;"), "заголовок і дата ДД.ММ.РРРР")
check(len(lines) - 1 - 1 == len(s), f"рядків даних = {len(s)}")
check("," in lines[1] and "." not in lines[1].split(";", 1)[1], "десяткова кома в CSV")
X.export_csv_daily(p_csv, s, comma=False, sep=",")
check("." in open(p_csv, encoding="utf-8-sig").read().splitlines()[1], "режим «крапка» теж працює")

print("\n== 4. Excel: читаємо назад")
import openpyxl
p_x = os.path.join(tmp, "weather.xlsx")
X.export_xlsx(p_x, rep, meta, pub)
wb = openpyxl.load_workbook(p_x)
check(wb.sheetnames == ["Метадані", "Добові дані", "Підсумок", "Місяці", "Декади", "За роками", "Періоди", "Норма"],
      f"аркуші: {wb.sheetnames}")
wd = wb["Добові дані"]
check(wd.max_row == len(s) + 1, "добових рядків стільки, скільки діб")
check(isinstance(wd["B2"].value, float) and isinstance(wd["A2"].value, dt.datetime), "числа — числа, дати — дати (не текст)")
check(wd["A2"].number_format == "DD.MM.YYYY", "формат дати ДД.ММ.РРРР")
wm = wb["Місяці"]
hdr = [c.value for c in wm[1]]
ig = hdr.index("ГТК") + 1
active = [row for row in wm.iter_rows(min_row=2) if isinstance(row[ig-1].value, float)]
check(len(active) > 10, f"ГТК у числовому вигляді для {len(active)} місяців")
filled = [row[ig-1].fill.fgColor.rgb for row in active]
check(all(f and f.endswith(tuple(X.HTC_FILL.values())) for f in filled), "комірки ГТК пофарбовані за класом")
check(wm.freeze_panes == "A2", "закріплено рядок заголовків")
wy = wb["За роками"]; yh_ = [c.value for c in wy[1]]
check("Опади, % норми" in yh_ and wy.max_row == 5, "аркуш «За роками»: 4 роки + норма й аномалії")
check(wb["Норма"].max_row >= 8 and wb["Норма"]["A1"].value == "Показник", "аркуш «Норма»")
check("ШКАЛА ВОЛОГОЗАБЕЗПЕЧЕНОСТІ" in " ".join(str(r[0].value) for r in wb["Метадані"].iter_rows()), "шкала ГТК у метаданих")
wp = wb["Періоди"]; vals = [[c.value for c in r] for r in wp.iter_rows(min_row=2)]
check(vals[-2][4] == "немає даних" and vals[-1][3] == "7 з 17", "аркуш «Періоди»: відсутні дані й неповне покриття позначено")

print("\n== 5. Word: читаємо назад")
import docx
png1 = X.figure_png(rep, "walter", "Умань", C.build_chart, dpi=80)
png2 = X.figure_png(rep, "htc_month", "Умань", C.build_chart, dpi=80)
check(png1 and png1[:8] == b"\x89PNG\r\n\x1a\n", "рисунок побудовано як PNG без вікна")
p_d = os.path.join(tmp, "weather.docx")
X.export_docx(p_d, rep, meta, pub, [("Діаграма Вальтера", png1), ("ГТК за місяцями", png2)], comma=True)
d = docx.Document(p_d)
texts = [p.text for p in d.paragraphs]
check(any(t.startswith("Таблиця 1 —") for t in texts) and any(t.startswith("Таблиця 2 —") for t in texts), "підписи таблиць «Таблиця N — …»")
check(len(d.tables) >= 3, f"таблиць у документі: {len(d.tables)}")
check(len(d.inline_shapes) == 2, "два рисунки вбудовано")
check(any(t.startswith("Рис. 1 —") for t in texts) and any(t.startswith("Рис. 2 —") for t in texts), "підписи рисунків")
tm_ = d.tables[0]
check(tm_.rows[0].cells[0].text == "Місяць" and any("," in c.text for c in tm_.rows[5].cells), "таблиця місяців: заголовок, десяткова кома")
hi = [c.text for c in tm_.rows[0].cells].index("ГТК")
shaded = 0
for row in tm_.rows[1:]:
    tcPr = row.cells[hi]._tc.tcPr
    if tcPr is not None and tcPr.xml.find("w:shd") != -1 and "FFFFFF" not in tcPr.xml and "D9E2F3" not in tcPr.xml: shaded += 1
check(shaded > 5, f"комірки ГТК у Word пофарбовано ({shaded})")
check(any("Джерела даних" == t for t in texts) and any("Шкала вологозабезпеченості за ГТК" == t for t in texts)
      and any("Примітки щодо якості даних" == t for t in texts), "розділи: джерела, примітки, шкала — кожен зі своїм заголовком")
check(not any("УМОВИ ВИКОРИСТАННЯ" in t for t in texts), "службовий блок про ліцензію не потрапив у текст для публікації")
check(any("ERA5" in t and "Open-Meteo" in t for t in texts), "методика згадує ERA5 і Open-Meteo")
check(len(d.tables) <= 4 and all("Декада" != t.rows[0].cells[0].text for t in d.tables), "декадна таблиця (108 рядків) не роздуває Word — вона в Excel")

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 56)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЕКСПОРТУ ПРОЙДЕНО")
