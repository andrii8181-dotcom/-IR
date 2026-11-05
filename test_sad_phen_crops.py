# test_sad_phen_crops.py – фенологія: власні культури (збереження наборів фаз), «Типові фази», бланк, погода з NASA, обходи, панель, налаштування й експорт графіків
import os, sys, json, tempfile, shutil, datetime as dt
TMP = tempfile.mkdtemp(prefix="sad_crops_"); os.environ["APPDATA"] = TMP               # власні культури – у тимчасовій теці, не в справжніх налаштуваннях
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import tkinter as tk
import matplotlib; matplotlib.use("Agg")
import sad_phenology as P
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
D = dt.date
print("== 1. Власні культури: збереження наборів фаз")
my = [{"key": "a", "name": "Розпускання бруньок", "bbch": "07", "hint": "своє"}, {"key": "b", "name": "Початок цвітіння", "bbch": "61", "hint": ""}]
k = P.save_user_preset("Лохина", my); path = P.user_presets_path()
check(k == "user:Лохина" and P.PRESETS[k]["name"] == "Лохина" and [p["name"] for p in P.PRESETS[k]["phases"]] == ["Розпускання бруньок", "Початок цвітіння"], "культуру «Лохина» збережено з її фазами")
check(P.PRESET_ORDER.index(k) == P.PRESET_ORDER.index("custom") - 1 and P.PRESET_ORDER[-1] == "custom", "у переліку – перед «Власним набором»")
check(os.path.exists(path) and json.load(open(path, encoding="utf-8"))["crops"][0]["name"] == "Лохина" and path.startswith(TMP), f"збережено у файлі налаштувань користувача ({os.path.relpath(path, TMP)})")
P._register_user([]); check(k not in P.PRESETS, "(імітація нового запуску програми)"); loaded = P.load_user_presets(); check(loaded == [k] and P.preset_phases(k)[0]["hint"] == "своє", "наступного запуску культура відновлюється з файла")
P.save_user_preset("Лохина", my[:1]); check(len(P.preset_phases(k)) == 1 and sum(1 for x in P.PRESET_ORDER if x == k) == 1, "збереження з тією ж назвою перезаписує, не дублює")
for bad, frag in (("", "назву"), ("Яблуня, груша", "вбудованих"), ("  ", "назву")):
    try: P.save_user_preset(bad, my); check(False, "мало впасти")
    except ValueError as e: check(frag in str(e), f"«{bad}» відхилено: {e}")
try: P.save_user_preset("Порожня", []); check(False, "мало впасти")
except ValueError as e: check("жодної фази" in str(e), "набір без фаз не зберігається")
k2 = P.save_user_preset("Смородина – мої фази", P.preset_phases("currants")[:3]); check(P.delete_user_preset(k2) and k2 not in P.PRESETS and len(json.load(open(path, encoding="utf-8"))["crops"]) == 1, "збережену культуру можна видалити з переліку й файла")
check(P.phases_from_monograph(P.preset_phases("pome")) and P.phases_from_monograph(P.preset_phases("pome")[2:5]), "фази з вбудованої шкали (і їх частина) – з монографії")
check(not P.phases_from_monograph(my) and not P.phases_from_monograph([dict(P.preset_phases("pome")[0], name="Моя назва")]) and not P.phases_from_monograph([]), "власні чи перейменовані фази – не з монографії")

if os.environ.get("DISPLAY"):
    import sad_phenology_win as PW, sad_phenology_dialogs as PD, sad_phenology_results as PR, sad_report as R, sad_journal_phen as JP, sad_weather_core as W
    LOG = []
    for m in (PW.messagebox, PD.messagebox):
        m.showinfo = lambda t="", msg="", **k: LOG.append(("info", msg)); m.showwarning = lambda t="", msg="", **k: LOG.append(("warn", msg)); m.askyesno = lambda *a, **k: True
    root = tk.Tk(); root.withdraw()
    def all_w(x):
        out = [x]
        for c in x.winfo_children(): out += all_w(c)
        return out
    print("\n== 2. Редактор фаз: «Зберегти як культуру», «Типові фази»")
    w = PW.PhenologyWindow(root); w.win.geometry("1260x760+0+0"); root.update()
    check("Лохина" in w.preset_cb.cget("values"), "збережена раніше культура є в переліку вікна")
    w.preset_var.set(P.PRESETS["custom"]["name"]); w._on_preset(); root.update()
    eds = [o for o in all_w(w.win) if isinstance(o, tk.Toplevel) and o.title() == "Фази"]; check(len(eds) == 1, "«Власний набір» – редактор відкрився сам"); eds[0].destroy()
    ed = w.edit_phases(); root.update(); check(str(ed.reset_btn.cget("state")) == "disabled" and any("типових фаз" in str(x.cget("text")) for x in all_w(ed.win) if x.winfo_class() == "Label"), "у власного набору «Типові фази» неактивна й пояснено чому")
    ed._ask = lambda p=None: {"name": "Сходи", "bbch": "09", "hint": ""}; ed.add(); ed._ask = lambda p=None: {"name": "Колосіння", "bbch": "51", "hint": ""}; ed.add()
    kk = ed.save_as_crop("Тритикале (моя шкала)"); root.update()
    check(kk == "user:Тритикале (моя шкала)" and w.preset_key == kk and w.preset_var.get() == "Тритикале (моя шкала)" and "Тритикале (моя шкала)" in w.preset_cb.cget("values"), "«💾 Зберегти як культуру…»: культура в переліку й одразу вибрана")
    check([h.cget("text") for h in w.hdr][2:] == ["Сходи (09)", "Колосіння (51)"], "таблиця – з фазами збереженої культури")
    ed2 = w.edit_phases(); root.update(); check(str(ed2.reset_btn.cget("state")) == "normal", "для збереженої культури «Типові фази» активна")
    ed2.lb.selection_set(0); ed2.delete(); ed2.reset(); check([p["name"] for p in ed2.phases] == ["Сходи", "Колосіння"], "«Типові фази» повертає збережений набір культури")
    check(any("Видалити цю культуру" in str(b.cget("text")) for b in all_w(ed2.win) if b.winfo_class() == "Button"), "для збереженої культури є «🗑 Видалити цю культуру з переліку»"); ed2.win.destroy()
    w.preset_var.set(P.PRESETS["pome"]["name"]); w._on_preset(); ed3 = w.edit_phases(); root.update(); ed3.lb.selection_set(0); ed3.delete(); ed3.delete(); n_ = len(ed3.phases); ed3.reset()
    check(n_ == 13 and len(ed3.phases) == 15 and str(ed3.reset_btn.cget("state")) == "normal", "яблуня: після видалень «Типові фази» повертає всі 15 фаз"); ed3.win.destroy()
    w.preset_var.set("Тритикале (моя шкала)"); w._on_preset(); ed4 = w.edit_phases(); root.update(); ed4.delete_crop(); root.update()
    check("user:Тритикале (моя шкала)" not in P.PRESETS and "Тритикале (моя шкала)" not in w.preset_cb.cget("values") and w.preset_key == "custom", "видалення культури прибирає її з переліку вікна")
    jt_vals = [P.PRESETS[k_]["name"] for k_ in P.PRESET_ORDER if P.PRESETS[k_]["phases"]]; check("Лохина" in jt_vals, "збережені культури доступні й у таблиці фенології журналу (той самий перелік)")

    print("\n== 3. Бланк для поля: посилання на монографію")
    import docx
    w.preset_var.set(P.PRESETS["pome"]["name"]); w._on_preset(); w.entries[0][0].insert(0, "Гала"); bp = os.path.join(TMP, "b1.docx"); w.blank_form(bp)
    check(any("BBCH Monograph" in p.text for p in docx.Document(bp).paragraphs), "фази зі шкали – посилання на монографію є")
    w.preset_var.set("Лохина"); w._on_preset(); bp2 = os.path.join(TMP, "b2.docx"); w.blank_form(bp2); d2 = docx.Document(bp2)
    check(not any("BBCH Monograph" in p.text for p in d2.paragraphs) and len(d2.tables) == 2, "власні фази – без посилання на монографію (шкала фаз у бланку лишається)")
    w.preset_var.set(P.PRESETS["pome"]["name"]); w._on_preset(); w.phases[0] = dict(w.phases[0], name="Набрякання (моє)"); bp3 = os.path.join(TMP, "b3.docx"); w.blank_form(bp3)
    check(not any("BBCH Monograph" in p.text for p in docx.Document(bp3).paragraphs), "якщо фазу перейменовано – посилання теж немає"); w._on_preset()

    print("\n== 4. Погода для сум температур: NASA POWER")
    w.years_data = {2025: [{"name": "Гала", "rep": "1", "dates": {"bloom0": "01.05.2025"}}], 2026: [{"name": "Гала", "rep": "1", "dates": {"bloom0": "04.05.2026"}}]}; w.cur_year = 2026; w._write_grid(w.years_data[2026]); w._update_years()
    calls = []
    def fake_fetch(lat, lon, d0, d1, progress=None, **k):
        calls.append((lat, lon, d0, d1)); progress and progress("NASA POWER: 2025 (1/2)…")
        days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]; doy = np.array([d.timetuple().tm_yday for d in days], float)
        return W.DailySeries(days, {"tmean": 10 + 12 * np.sin(2 * np.pi * (doy - 110) / 365)})
    real = W.fetch_nasa; W.fetch_nasa = fake_fetch
    wd = PD.WeatherDialog(w.win, w); root.update(); check(any("Отримати з NASA" in str(b.cget("text")) for b in all_w(wd.win) if b.winfo_class() == "Button"), "у діалозі погоди є «⬇ Отримати з NASA»")
    wd.lat.set("abc"); n_w = len(LOG); wd.from_nasa(); check(len(LOG) == n_w + 1 and "широту" in LOG[-1][1] and not calls, "некоректні координати – пояснення, без запиту")
    wd.lat.set("48,75"); wd.lon.set("30,22"); wd.from_nasa()
    for _ in range(40):
        root.update(); import time; time.sleep(0.05)
        if w.series is not None: break
    check(calls and calls[0][:2] == (48.75, 30.22) and calls[0][2] == D(2025, 1, 1) and calls[0][3].year == 2026, f"запит до NASA: координати й роки досліду 2025–2026 ({calls[0][2]} – {calls[0][3]})" if calls else "запиту не було")
    check(w.series is not None and "NASA POWER" in w.weather_note and "Отримано" in wd.nasa_msg.cget("text") and w.weather_coords == (48.75, 30.22), f"дані підключено: {w.weather_note}")
    pj = os.path.join(TMP, "p.sadph"); w.save_project(pj); w2 = PW.PhenologyWindow(root); w2.open_project(pj); check(getattr(w2, "weather_coords", None) == (48.75, 30.22), "координати зберігаються в проєкті й підставляються наступного разу")
    wd2 = PD.WeatherDialog(w2.win, w2); check(wd2.lat.get() == "48.75" and wd2.lon.get() == "30.22", "у діалозі погоди – збережені координати"); wd2.win.destroy(); w2.win.destroy()
    def fail_fetch(*a, **k): raise W.WeatherError("немає з'єднання з інтернетом")
    W.fetch_nasa = fail_fetch; wd.from_nasa()
    for _ in range(40):
        root.update(); time.sleep(0.05)
        if "Не вдалося" in wd.nasa_msg.cget("text"): break
    check("немає з'єднання" in wd.nasa_msg.cget("text") and str(wd.b_nasa.cget("state")) == "normal", "помилка мережі – зрозуміле повідомлення, кнопка знову активна"); W.fetch_nasa = real; wd.win.destroy()

    print("\n== 5. Обходи – зрозуміліше")
    vd = PD.VisitsDialog(w.win, w); root.update(); lbls = " ".join(str(x.cget("text")) for x in all_w(vd.win) if x.winfo_class() in ("Label", "Labelframe"))
    check(vd.win.title() == "Дата фази за % рослин у фазі (обходи)" and "Навіщо:" in lbls and "Приклад:" in lbls and "≈ 3 травня" in lbls, "пояснення: навіщо, як, приклад")
    vd.add_visit(D(2026, 5, 2)); root.update(); check(any("% у фазі" in str(x.cget("text")) for x in all_w(vd.gf) if x.winfo_class() == "Label"), "стовпчик обходу підписано «% у фазі»")
    check(any("Обхід" in str(b.cget("text")) for b in all_w(vd.win) if b.winfo_class() == "Button") and not any("Візит" in str(b.cget("text")) for b in all_w(vd.win) if b.winfo_class() == "Button"), "кнопки – «Обхід», без «візитів»"); vd.win.destroy()

    print("\n== 6. Панель: усі дії на видноті")
    w.win.geometry("1260x760+0+0"); root.update(); fr2 = [c for c in w.win.winfo_children() if c.winfo_class() == "Frame"][1]
    b2 = [b for b in fr2.winfo_children() if b.winfo_class() == "Button"]; g2 = [l.cget("text").strip() for l in fr2.winfo_children() if l.winfo_class() == "Label"]
    check(g2 == ["Дані:", "Аналіз:", "Файл:"] and len(b2) == 8, f"другий ряд: групи {g2}, кнопок {len(b2)}")
    check(all(b.winfo_rootx() + b.winfo_width() <= w.win.winfo_rootx() + w.win.winfo_width() + 2 for b in b2), "усі кнопки другого ряду вміщуються у вікні 1260 px")
    check(any("обходи" in b.cget("text") for b in b2) and any("Погода" in b.cget("text") for b in b2) and any("Бланк" in b.cget("text") for b in b2) and any("Групи" in b.cget("text") for b in b2), "обходи, погода, групи, бланк – кнопками, не лише в меню")

    print("\n== 7. Результати: налаштування графіків, експорт усіх графіків")
    rng = np.random.default_rng(2); w.preset_var.set(P.PRESETS["pome"]["name"]); w._on_preset()
    w.years_data = {2025: [{"name": c, "rep": str(r), "dates": {"bloom0": P.fmt_date(D(2025, 5, 1) + dt.timedelta(days=o + int(rng.integers(0, 2)))), "bloom1": P.fmt_date(D(2025, 5, 12) + dt.timedelta(days=o))}} for c, o in (("Голден", 0), ("Гала", 3), ("Фуджі", 7)) for r in (1, 2, 3)]}
    w.cur_year = 2025; w._write_grid(w.years_data[2025]); w._update_years(); w.std_var.set("Голден"); w.standard = "Голден"; w.series = None
    ctx = w._run(); rw = w.results_win; root.update()
    rw.nb.select(rw.nb.tabs()[[rw.nb.tab(t_, "text") for t_ in rw.nb.tabs()].index("Графіки")]); root.update()
    check(any("Налаштування" in str(b.cget("text")) for b in all_w(rw.win) if b.winfo_class() == "Button"), "біля графіка є «⚙ Налаштування»")
    fs0 = max(t_.get_fontsize() for t_ in rw.fig.axes[0].texts + [rw.fig.axes[0].title]) if rw.fig.axes[0].texts else rw.fig.axes[0].title.get_fontsize()
    from tkinter import colorchooser; colorchooser.askcolor = lambda *a, **k: ((0, 0, 0), "#000000")
    sd = rw._settings(); root.update(); sv = [x for x in all_w(sd) if x.winfo_class() == "Spinbox"][0]; sv.delete(0, tk.END); sv.insert(0, "150")
    [b for b in all_w(sd) if b.winfo_class() == "Button" and not b.cget("text").strip()][2].invoke(); root.update()      # кнопка кольору «Пізні сорти й стандарт»
    [b for b in all_w(sd) if b.winfo_class() == "Button" and "Застосувати" in b.cget("text")][0].invoke(); root.update()
    fs1 = max(t_.get_fontsize() for t_ in rw.fig.axes[0].texts + [rw.fig.axes[0].title]) if rw.fig.axes[0].texts else rw.fig.axes[0].title.get_fontsize()
    check(abs(fs1 - fs0 * 1.5) < 0.6 and rw.gs["scale"] == 150, f"розмір тексту 150 %: {fs0:.1f} → {fs1:.1f} пт")
    rw.chart_var.set(PR.CHARTS[2]); rw._draw(); root.update(); cols = {b.get_facecolor()[:3] for b in rw.fig.axes[0].patches}
    check((0.0, 0.0, 0.0) in cols, "колір «пізні сорти» змінено – на графіку відхилень пізні сорти чорні")
    [b for b in all_w(sd) if b.winfo_class() == "Button" and "Типові" in b.cget("text")][0].invoke(); root.update(); check(rw.gs == PR.GS_DEFAULT, "«Типові» повертають початкові налаштування")
    figs = rw._all_figures(); caps = [c_ for c_, _ in figs]; n_ph = 2
    check(len(figs) == 2 + 5 * n_ph - 0 * 1 - n_ph if False else (len([c_ for c_ in caps if c_.startswith("Фенологічний")]) == 1 and sum(1 for c_ in caps if c_.endswith(": Початок цвітіння (≈ 10 % квіток)")) >= 4), f"усі графіки для звіту: {len(figs)} (незалежні від фази – по одному, решта – для кожної фази)")
    check(not any("погода" in c_.lower() or "температур" in c_.lower() for c_ in caps), "без погоди графіки температур у звіт не потрапляють (порожніх рисунків немає)")
    dp = os.path.join(TMP, "r.docx"); R.export_window(rw.win, "docx", path=dp, ask_open=False); dd = docx.Document(dp)
    capt = [p.text for p in dd.paragraphs if p.text.startswith("Рисунок ")]
    check(len(dd.inline_shapes) == len(figs) and len(capt) == len(figs) and any("Кінець цвітіння" in c_ for c_ in capt), f"у Word – усі {len(figs)} графіків із підписами за фазами")
    xp = os.path.join(TMP, "r.xlsx"); R.export_window(rw.win, "xlsx", path=xp, ask_open=False); import openpyxl
    wb = openpyxl.load_workbook(xp); check("Графіки" in wb.sheetnames and len(wb["Графіки"]._images) == len(figs), f"в Excel на аркуші «Графіки» – усі {len(figs)} графіків")
    rw.win.destroy(); w.win.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ВЛАСНИХ КУЛЬТУР І ВИПРАВЛЕНЬ ФЕНОЛОГІЇ ПРОЙДЕНО")
