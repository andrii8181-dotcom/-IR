# test_sad_phen_season.py – фенологія протягом сезону: таблиця в журналі, обходи (% рослин у фазі), аналіз, висновки, погода
import os, sys, json, math, tempfile, shutil, datetime as dt
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import tkinter as tk
from tkinter import ttk
import matplotlib; matplotlib.use("Agg")
import sad_phenology as P, sad_journal_trial as JT, sad_journal_phen as JP, sad_phenology_win as PW, sad_phenology_results as PR, sad_weather_core as W
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
D = dt.date; TMP = tempfile.mkdtemp(prefix="sad_season_"); LOG = []; ASK = {"ans": True, "ync": True}
for m in (JT.messagebox, JP.messagebox, PW.messagebox):
    m.showinfo = lambda t="", msg="", **k: LOG.append(("info", msg)); m.showwarning = lambda t="", msg="", **k: LOG.append(("warn", msg)); m.showerror = lambda t="", msg="", **k: LOG.append(("err", msg))
    m.askyesno = lambda *a, **k: ASK["ans"]; m.askyesnocancel = lambda *a, **k: ASK["ync"]
root = tk.Tk(); root.withdraw()
def all_w(x):
    out = [x]
    for c in x.winfo_children(): out += all_w(c)
    return out
CV = ["Голден Делішес", "Гала", "Фуджі"]
plants = []
for b in range(1, 4):
    pos = 1
    for c in [(b + i) % 3 + 1 for i in range(3)]:
        for k in range(2): plants.append({"row": b, "position": pos, "role": "recorded", "replication": b, "factors": {"Сорт": c}}); pos += 1
SCH = {"type": "multi_factor_scheme", "factor_defs": [{"name": "Сорт", "levels": CV}], "variant_names": [], "cfg": {"model": "plant", "standards": ["Голден Делішес"]}, "plants": plants}
folder = os.path.join(TMP, "Сорти"); os.makedirs(folder); sp = os.path.join(folder, "схема.sadp"); json.dump(SCH, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
def open_journal(year):
    jw = JT.FieldJournalWindow(root, {}); root.update(); JT.filedialog.askopenfilename = lambda **k: sp; jw._prompt_new_year = lambda: None; jw._open_file()
    jw._current_year = str(year); jw._load_year(str(year)); root.update(); return jw
OFF = {"Голден Делішес": 0, "Гала": 3, "Фуджі": 8}

print("== 1. Таблиця фенології в журналі")
jw = open_journal(2025)
btn = [b for b in all_w(jw.win) if b.winfo_class() == "Button" and "Фенологія" in str(b.cget("text"))]; check(len(btn) == 1 and not [b for b in all_w(jw.win) if b.winfo_class() == "Button" and "Фенофаза" in str(b.cget("text"))], "у журналі одна кнопка «🌸 Фенологія…» (стару «Фенофаза…» замінено)")
tb = jw._open_phenology_table(); root.update()
check(len(tb.plots) == 9 and [p["name"] for p in tb.plots[:3]] == [CV[(1 + i) % 3] for i in range(3)] and all(len(p["keys"]) == 2 for p in tb.plots), "рядки – 9 ділянок (3 сорти × 3 повторності) у порядку поля; по 2 дерева на ділянку")
check(tb.preset == "pome" and len(tb.phases) == len(P.PRESETS["pome"]["phases"]), "стовпчики – фази яблуні за BBCH")
check(all(p["std"] == (p["name"] == "Голден Делішес") for p in tb.plots), "стандарт зі схеми («Голден Делішес») виділено в таблиці, решту – ні")
heads = [x.cget("text") for x in tb.gf.grid_slaves(row=0)][::-1]; check(heads[:3] == ["№", "Сорт / варіант", "Повт./блок"] and "Початок цвітіння (≈ 10 % квіток) (61)" in heads, "заголовки: №, сорт, повторність і фази з кодами BBCH")
ib0 = [p["key"] for p in tb.phases].index("bloom0"); ib1 = [p["key"] for p in tb.phases].index("bloom1")
print("   травень: вносимо початок цвітіння")
forms = ["{d:%d.%m}", "{d:%d%m}", "{d.day} травня"]
for i, pl in enumerate(tb.plots):
    e = tb.cells[(i, ib0)]; d = D(2025, 5, 2) + dt.timedelta(days=OFF[pl["name"]] + pl["rep"] % 2); e.delete(0, tk.END); e.insert(0, forms[i % 3].format(d=d)); tb._touched(i, ib0); tb._norm(i, ib0)
check(all(tb.cells[(i, ib0)].get().endswith(".2025") for i in range(9)) and tb.dirty and "незбережені" in tb.status.cget("text"), "дати нормалізовано; позначено «є незбережені зміни»")
tb.save(); root.update(); jf = os.path.join(folder, "2025", "журнал_2025.sadp"); jd = json.load(open(jf, encoding="utf-8"))
rb = next((r for r in jd["records"].values() if r.get("phase_key") == "bloom0"), None)
check(rb is not None and rb["kind"] == "date" and len(rb["values"]) == 18 and jd["cfg"]["phen_preset"] == "pome" and not tb.dirty, "збережено в журнал: показник «дата» для 18 дерев (кожне дерево ділянки – дата ділянки), культура запам'ятована")
check(sum(1 for r in jd["records"].values() if r.get("kind") == "date") == 1, "порожні фази не створюють порожніх показників")
tb.close(); root.update()
print("   червень: відкриваємо знову й дописуємо кінець цвітіння")
tb2 = jw._open_phenology_table(); root.update()
check(all(tb2.cells[(i, ib0)].get().endswith(".2025") for i in range(9)) and all(not tb2.cells[(i, ib1)].get() for i in range(9)), "повторне відкриття: травневі дати на місці, червневих ще немає")
for i, pl in enumerate(tb2.plots):
    e = tb2.cells[(i, ib1)]; e.insert(0, P.fmt_date(D(2025, 5, 13) + dt.timedelta(days=OFF[pl["name"]]))); tb2._touched(i, ib1); tb2._norm(i, ib1)
e = tb2.cells[(0, ib1)]; e.delete(0, tk.END); e.insert(0, "01.05.2025"); tb2._touched(0, ib1); tb2._validate(); check(str(e.cget("bg")) == JP.BG_WARN, "кінець цвітіння раніше за початок – оранжева клітинка")
e.delete(0, tk.END); e.insert(0, P.fmt_date(D(2025, 5, 13) + dt.timedelta(days=OFF[tb2.plots[0]["name"]]))); tb2._touched(0, ib1)
tb2.save(); jd = json.load(open(jf, encoding="utf-8")); kinds = {r.get("phase_key") for r in jd["records"].values() if r.get("kind") == "date"}
check(kinds == {"bloom0", "bloom1"} and len(next(r for r in jd["records"].values() if r.get("phase_key") == "bloom1")["values"]) == 18, "у журналі тепер дві фази – таблицю дозаповнено, травневе не загубилось")
check(any(nm.startswith("Кінець цвітіння") for nm in jw._record_cb.cget("values")), "фази видно й у списку показників журналу (і на карті поля)")
print("   різні дати дерев однієї ділянки")
rb0 = next(nm for nm, r in jw.records.items() if r.get("phase_key") == "bloom0"); k0, k1 = tb2.plots[2]["keys"]; jw.records[rb0]["values"][k0] = "10.05.2025"; jw.records[rb0]["values"][k1] = "14.05.2025"
tb2.close(); tb3 = jw._open_phenology_table(); root.update(); c2 = tb3.cells[(2, ib0)]
check(c2.get() == "~12.05.2025" and str(c2.cget("bg")) == JP.BG_MIXED, "дерева ділянки мають різні дати – у таблиці медіана з позначкою «~» (блакитна клітинка)")
tb3.cells[(5, ib0)].delete(0, tk.END); tb3.cells[(5, ib0)].insert(0, "20.05.2025"); tb3._touched(5, ib0); n_, errs_ = tb3.collect()
check(jw.records[rb0]["values"][k0] == "10.05.2025" and jw.records[rb0]["values"][k1] == "14.05.2025" and n_ == 1, "незмінену «~»-клітинку при збереженні не перезаписано (дати дерев лишились свої)")
tb3.cells[(5, ib0)].delete(0, tk.END); tb3._touched(5, ib0); tb3.collect(); check(all(k not in jw.records[rb0]["values"] for k in tb3.plots[5]["keys"]), "очищена клітинка видаляє дату ділянки")
ASK["ync"] = False; tb3.close(); check(not tb3.win.winfo_exists(), "закриття з незбереженими змінами: запитання; «ні» – закрити без збереження")

print("\n== 2. Обходи: % рослин у фазі (кілька днів)")
tbv = jw._open_phenology_table(); root.update(); vd = tbv.open_visits(); root.update()
check(vd.win.title() == "Обходи: % рослин у фазі" and vd.sv.get() == "Цвітіння", "діалог «Обходи: % рослин у фазі», за замовчуванням – «Цвітіння»")
check([pv.get() for pv, _ in vd.targets] == ["Початок цвітіння (≈ 10 % квіток) (61)", "Повне цвітіння (≥ 50 % квіток) (65)", "Кінець цвітіння (69)"], "для цвітіння одразу запропоновано: початок 10 %, повне 50 %, кінець 90 %")
vd.add_visit(D(2025, 5, 1)); vd.add_visit(D(2025, 5, 5))
for i in range(9):
    vd.cells[(i, 0)].insert(0, "0"); vd.cells[(i, 1)].insert(0, "20" if i == 0 else "5")
vd.close(); root.update(); ASK["ync"] = True; tbv.save(); jd = json.load(open(jf, encoding="utf-8"))
st_ = jd["cfg"].get("phen_visits", {}).get("Цвітіння", {}); check(st_.get("dates") == ["01.05.2025", "05.05.2025"] and st_["values"][tbv.plots[0]["id"]]["05.05.2025"] == "20", "обходи двох днів збережено в журналі")
tbv.close(); jw.win.destroy()
jw2 = open_journal(2025); tbw = jw2._open_phenology_table(); root.update(); vd2 = tbw.open_visits(); root.update()
check(vd2._cur()["dates"] == ["01.05.2025", "05.05.2025"] and vd2.cells[(0, 1)].get() == "20", "наступного дня (новий запуск журналу) обходи на місці")
vd2.add_visit(D(2025, 5, 9)); vd2.cells[(0, 2)].insert(0, "80"); [vd2.cells[(i, 2)].insert(0, "30") for i in range(1, 9)]
res = vd2.compute(); r0 = {r["key"]: r for r in res if r["i"] == 0}
check(r0["bloom0"]["date"] == D(2025, 5, 3) and r0["bloom50"]["date"] == D(2025, 5, 7) and r0["bloom1"]["date"] is None, "обчислено: 10 % – 3.05, 50 % – 7.05; 90 % ще не досягнуто")
vd2.apply(); check(tbw.cells[(0, ib0)].get() == "03.05.2025" and "Записано в таблицю дат:" in vd2.msg.cget("text") and "ще не досягнуто" in vd2.msg.cget("text"), "дати записано в таблицю фенології; про недосягнутий поріг сказано")
vd2.targets[0][1].set("x"); n_w = len(LOG); vd2.apply(); check(len(LOG) == n_w + 1 and "числом" in LOG[-1][1], "некоректний поріг – пояснення"); vd2.targets[0][1].set("10")
vd2.close(); ASK["ync"] = True; tbw.save()
jw2._current_year = "2026"; jw2._load_year("2026"); root.update(); tbn = jw2._open_phenology_table(); root.update(); vdn = tbn.open_visits(); root.update()
check(vdn._cur()["dates"] == [] and all(not tbn.cells[(i, ib0)].get() for i in range(9)), "новий рік – чиста таблиця й порожні обходи (дані 2025 не «перетікають»)")
for i, pl in enumerate(tbn.plots):
    tbn.cells[(i, ib0)].insert(0, P.fmt_date(D(2026, 5, 5) + dt.timedelta(days=OFF[pl["name"]]))); tbn._touched(i, ib0)
vdn.win.destroy(); tbn.save()

print("\n== 3. Аналіз з таблиці журналу")
pw = tbn.analyze(); root.update()
check(pw is not None and sorted(pw.years_data) == [2025, 2026] and pw.results_win is not None and pw.standard == "Голден Делішес", "«▶ Аналіз фенофаз» – одразу результати за обидва роки; стандарт зі схеми")
rw = pw.results_win; tabs = [rw.nb.tab(t_, "text") for t_ in rw.nb.tabs()]; check(tabs[0] == "Висновки", f"перша вкладка – «Висновки»: {tabs[:3]}")
txt = [x for x in all_w(rw.concl_frame) if x.winfo_class() == "Text"][0].get("1.0", "end")
check("Найраніше – Голден Делішес" in txt and "найпізніше – Фуджі" in txt and "«Голден Делішес»" in txt, "висновки звичайними реченнями: найраніший і найпізніший сорт, стандарт")
check("Погоду не підключено" in txt, "висновки підказують, як підключити погоду")
print("   поріг «ранній / пізній» у вікні результатів")
sp_ = [x for x in all_w(rw.std_frame) if x.winfo_class() == "Spinbox"]; check(len(sp_) == 1 and rw.thr_var.get() == "3", "у вкладці «Стандарт і групи» – поле порогу (3 доби)")
gala_cls = rw.ctx["vs"][("Гала", "bloom0")][1]; rw.thr_var.set("2"); rw._set_thr(); gala2 = rw.ctx["vs"][("Гала", "bloom0")][1]
d_g = rw.ctx["summ"][("Гала", "bloom0")]["mean"] - rw.ctx["summ"][("Голден Делішес", "bloom0")]["mean"]
check(gala_cls == P.classify(d_g, 3) and gala2 == P.classify(d_g, 2) and rw.ctx["thr"] == 2.0 and pw.thr_var.get() == "2", f"зміна порогу перераховує класи (Гала: різниця {d_g:+.2f} доби → поріг 3: «{gala_cls}», поріг 2: «{gala2}») і запам'ятовується у вікні фенології")
rw.thr_var.set("1"); rw._set_thr(); check(rw.ctx["vs"][("Гала", "bloom0")][1] == P.classify(d_g, 1) == "пізній", "поріг 1 доба – Гала стає «пізньою» (клас справді змінюється)")
rw.thr_var.set("10"); rw._set_thr(); check(rw.ctx["vs"][("Гала", "bloom0")][1] == "середній" and rw.ctx["vs"][("Фуджі", "bloom0")][1] == "середній", "поріг 10 діб – Гала й Фуджі вже «середні»")
txt2 = [x for x in all_w(rw.concl_frame) if x.winfo_class() == "Text"][0].get("1.0", "end"); check("щонайменше на 10 доби" in txt2, "висновки оновились разом із порогом")
rw.chart_var.set(PR.CHARTS[6]); rw._draw(); root.update(); check(any("Погоду не підключено" in t_.get_text() for a in rw.fig.axes for t_ in a.texts), "графік «Фази на тлі температури» без погоди – підказка")
rw.win.destroy()

print("\n== 4. Погода: суми температур і графіки")
days = [D(2025, 1, 1) + dt.timedelta(days=i) for i in range(730)]; doy = np.array([d.timetuple().tm_yday for d in days], float)
ser = W.DailySeries(days, {"tmean": 10 + 12 * np.sin(2 * np.pi * (doy - 110) / 365)}); pw.series = ser; pw.weather_note = "тест"; pw._update_weather_label()
check("погода підключена" in pw.weather_lbl.cget("text"), "у головному вікні видно, що погоду підключено")
pw.sum_cfg = {"kind": "sat", "base": 10.0, "start": ["md", 3, 1]}; ctx = pw._run(); rw2 = pw.results_win; root.update()
check(ctx["series"] is ser and ctx["sums"] is not None and "Суми температур" in [rw2.nb.tab(t_, "text") for t_ in rw2.nb.tabs()], "з погодою: вкладка «Суми температур»")
rw2.chart_var.set(PR.CHARTS[6]); rw2.cphase_var.set([l for l in rw2._cp_labels if "Початок цвітіння" in l][0]); rw2._draw(); root.update(); f6 = rw2.fig; ax = f6.axes[0]
check(len([l for l in ax.lines if len(l.get_xdata()) > 20]) == 2 and len(ax.patches) >= 2, f"«Фази на тлі температури»: дві лінії температури (2025, 2026) і смуги фаз ({len(ax.patches)})")
tl = [l for l in ax.lines if len(l.get_xdata()) > 20]; edge_ok = all(abs(l.get_ydata()[-1] - l.get_ydata()[-3]) < 2.5 for l in tl)
check(edge_ok and {l.get_color() for l in tl}.isdisjoint({"#4c72b0", "#dd8452"}), "криві температури без провалу на краю; кольори років відрізняються від кольорів фаз")
check(any("Початок цвітіння" in t_.get_text() for t_ in ax.texts) and any(abs(l.get_ydata()[0] - 10.0) < 1e-9 for l in ax.lines if len(set(l.get_ydata())) == 1), "підписи фаз і лінія порогу 10 °C")
rw2.chart_var.set(PR.CHARTS[7]); rw2._draw(); root.update(); f7 = rw2.fig; a7 = f7.axes[0]
mean_g = ctx["sums"][("Голден Делішес", "bloom0")]["mean"]; check(len(a7.patches) == 3 and any(abs(p.get_width() - mean_g) < 1e-6 for p in a7.patches), f"«Суми температур до фази»: 3 сорти, стовпчик Голдена = {mean_g:.0f} °C·діб")
txt3 = [x for x in all_w(rw2.concl_frame) if x.winfo_class() == "Text"][0].get("1.0", "end"); check("Сума активних температур до фази" in txt3 and "Погоду не підключено" not in txt3, "висновки містять суми температур")
cl = PR.build_conclusions(ctx, "Яблуня"); check(cl[0] == ("h", "Загалом") and any(k_ == "h" and t_ == "Початок цвітіння (≈ 10 % квіток)" for k_, t_ in cl), "build_conclusions: розділи «Загалом» і по фазах")
rw2.win.destroy(); pw.win.destroy()

print("\n== 5. Вікно фенології для даних без схеми")
pv = PW.PhenologyWindow(root); root.update(); check(pv.hint.winfo_manager() == "place", "порожня таблиця – підказка «Як почати»")
pv.entries[0][0].insert(0, "Сорт А"); pv._validate_all(); check(pv.hint.winfo_manager() == "", "після введення першого сорту підказка зникає")
pv.entries[0][0].delete(0, tk.END); pv._validate_all(); check(pv.hint.winfo_manager() == "place", "таблицю знову очищено – підказка повертається")
pv.hint.event_generate("<Button-1>"); root.update(); pv._validate_all(); check(pv.hint.winfo_manager() == "" and pv._hint_dismissed, "клік по підказці ховає її, і вона не з'являється знову, хоч таблиця ще порожня")
c0 = {"years": [2025], "cultivars": ["А", "Б"], "n_obs": 4, "standard": "А", "ref_of": None, "thr": 3.0, "phases": [{"key": "p", "name": "Фаза"}], "summ": {("А", "p"): {"n": 2, "mean": 100.0}, ("Б", "p"): {"n": 2, "mean": 104.0}},
      "anova": {}, "compare": {}, "vs": {("А", "p"): (0.0, "середній"), ("Б", "p"): (4.0, "пізній")}, "sums": {("А", "p"): {"n": 2, "mean": 0.0}, ("Б", "p"): {"n": 2, "mean": 0.0}}, "sum_cfg": {"kind": "sat", "base": 10.0}, "pairs": [], "series": object()}
lines0 = [t_ for k_, t_ in PR.build_conclusions(c0)]; check(any("ще не перевищувала 10 °C" in l for l in lines0) and not any("від 0 (" in l for l in lines0), "нульові суми температур – зрозуміле речення замість «від 0 до 0»")
c0["sums"] = {("А", "p"): {"n": 2, "mean": 120.2}, ("Б", "p"): {"n": 2, "mean": 120.1}}; check(any("однакова для сортів" in t_ for k_, t_ in PR.build_conclusions(c0)), "однакові суми – «однакова для сортів»")
pv.win.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ФЕНОЛОГІЇ ПРОТЯГОМ СЕЗОНУ ПРОЙДЕНО")
