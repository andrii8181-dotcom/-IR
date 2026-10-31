# test_sad_trials_many.py – досліди з сотнями номерів (гібриди сої, кукурудзи…): конструктор (аугментована схема, α-решітка, стандарти й групи)
# → етикетки → польовий журнал → «Порівняння зі стандартом» / «Змішана модель» / фенологія
import os, sys, json, math, random, tempfile, shutil, statistics, collections
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import tkinter as tk
from tkinter import ttk
import matplotlib; matplotlib.use("Agg")
import sad_scheme_constructor as SC, sad_journal_trial as JT, sad_qrlabels as Q, sad_breeding_win as BW, sad_phenology_journal as PJ, sad_control_core as CC
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
TMP = tempfile.mkdtemp(prefix="sad_many_"); LOG = {"warn": [], "info": [], "ask": []}; SAVE = {"path": None}
for m in (SC.messagebox, JT.messagebox, BW.messagebox):
    m.showwarning = lambda t="", msg="", **k: LOG["warn"].append(msg); m.showinfo = lambda t="", msg="", **k: LOG["info"].append(msg); m.showerror = lambda t="", msg="", **k: LOG["warn"].append(msg)
    m.askyesno = lambda t="", msg="", **k: (LOG["ask"].append(msg), True)[1]
SC.filedialog.asksaveasfilename = lambda **k: SAVE["path"]; SC.filedialog.askopenfilename = lambda **k: SAVE["path"]
root = tk.Tk(); root.withdraw()
def all_w(x):
    out = [x]
    for c in x.winfo_children(): out += all_w(c)
    return out
def dialogs(win): return [w for w in win.win.winfo_children() if isinstance(w, tk.Toplevel)]
def set_entry(e, t): e.delete(0, tk.END); e.insert(0, t); e.event_generate("<KeyRelease>"); root.update()
def btn(parent, text): return [b for b in all_w(parent) if b.winfo_class() == "Button" and text in b.cget("text")][0]
def fill_factors(win, factors):
    win._edit_factors(); root.update(); dlg = dialogs(win)[-1]
    spins = [x for x in all_w(dlg) if x.winfo_class() == "Spinbox"]; set_entry(spins[0], str(len(factors)))
    frames = [f for f in all_w(dlg) if f.winfo_class() == "Labelframe" and f.cget("text").startswith("Фактор ")]
    for f, (nm, lv) in zip(frames, factors):
        es = [c for c in f.winfo_children() if c.winfo_class() == "Entry"]; set_entry(es[0], nm); set_entry(es[1], lv)
    btn(dlg, "Зберегти").invoke(); root.update()
HYB = [f"Гібрид {i:03d}" for i in range(1, 301)]; STD = ["Стандарт ранній", "Стандарт середній", "Стандарт пізній", "Стандарт 4"]
AUG_DESIGN = "Аугментована (сотні номерів, стандарти в кожному блоці)"; ALPHA_DESIGN = "α-решітка (багато номерів, неповні блоки)"

print("== 1. Конструктор: аугментована схема для 300 гібридів")
w = SC.SchemeConstructorWindow(root, {}); root.update(); w._model_var.set("area"); w._on_model_change(); root.update()
fill_factors(w, [("Гібрид", ", ".join(HYB + STD))])
check(len(w.factor_defs) == 1 and len(w.factor_defs[0]["levels"]) == 304, "фактор «Гібрид» із 304 рівнями (300 гібридів + 4 стандарти) введено через діалог")
check(AUG_DESIGN in w._area_design_map and ALPHA_DESIGN in w._area_design_map, "у списку схем є аугментована й α-решітка")
w._area_design_disp.set(AUG_DESIGN); root.update()
check(w._many_frame.winfo_manager() == "grid" and w._aug_row.winfo_manager() == "pack" and w._alpha_row.winfo_manager() == "", "для аугментованої схеми показано поле кількості блоків і кнопку стандартів")
check("щонайменше 2 стандарти" in w._alpha_hint.cget("text") and str(btn(w._step3_area_content, "Стандарти й групи").cget("state")) == "normal", "без стандартів – підказка, але Крок 3 (із кнопкою стандартів) лишається доступним")
w._open_standards(); root.update(); sd = [d for d in w.win.winfo_children() if isinstance(d, tk.Toplevel) and d.title() == "Стандарти й групи стиглості"]
check(len(sd) == 1, "діалог «Стандарти й групи стиглості» відкривається"); sdo = sd[0]
dlg_obj = [o for o in [getattr(w, "_std_dlg", None)] if o]  # (об'єкт діалогу не зберігається у вікні – працюємо через віджети)
tv = [x for x in all_w(sdo) if x.winfo_class() == "Treeview"][0]
def ids(): return {tv.item(i, "values")[0]: i for i in tv.get_children()}
tv.selection_set([ids()[s] for s in STD]); btn(sdo, "Позначити стандартом").invoke(); root.update()
check(all(tv.item(ids()[s], "values")[1] == "⭐" for s in STD), "чотири номери позначено стандартами")
cb = [x for x in all_w(sdo) if x.winfo_class() == "TCombobox"][0]
for grp, names in (("ранні", ["Стандарт ранній"] + HYB[:100]), ("пізні", ["Стандарт пізній"] + HYB[200:])):
    tv.selection_set([ids()[n] for n in names]); cb.set(grp); btn(sdo, "Призначити групу").invoke(); root.update()
btn(sdo, "OK").invoke(); root.update()
check(w._std_cfg["standards"] == STD and w._std_cfg["groups"]["Гібрид 150"] if False else (w._std_cfg["standards"] == STD and w._std_cfg["groups"].get("Гібрид 250") == "пізні" and w._std_cfg["group_std"] == {"ранні": "Стандарт ранній", "пізні": "Стандарт пізній"}),
      f"стандарти й групи збережено; стандарт кожної групи – позначений у ній: {w._std_cfg['group_std']}")
check("стандарти: 4" in w._std_lbl.cget("text") and "груп: 2" in w._std_lbl.cget("text"), f"підпис: «{w._std_lbl.cget('text')}»")
w._aug_blocks.set("10"); root.update(); h = w._alpha_hint.cget("text")
check("Ділянок: 340 (300 нових + 4 стандарти × 10 блоків)" in h and "ступенів свободи похибки 27" in h, f"підказка: {h}")
btn(w._step3_area_content, "Сформувати план").invoke(); root.update(); plan = w._area_plan["plan"]
check(len(plan) == 340, f"план: 340 ділянок ({len(plan)})")
by_blk = collections.defaultdict(list)
for p in plan: by_blk[p["block"]].append(p)
lv = w.factor_defs[0]["levels"]; nm = lambda p: lv[p["combo"][0] - 1]
check(sorted(by_blk) == list(range(1, 11)) and all(sorted(nm(p) for p in ps if p["kind"] == "standard") == sorted(STD) for ps in by_blk.values()), "кожен стандарт – рівно один раз у кожному з 10 блоків")
newc = collections.Counter(nm(p) for p in plan if p["kind"] == "new"); check(len(newc) == 300 and set(newc.values()) == {1}, "кожен гібрид – рівно один раз")
check(all(p["row"] == p["block"] == p["rep"] for p in plan) and max(len(v) for v in by_blk.values()) - min(len(v) for v in by_blk.values()) <= 1, "блок = ряд поля; блоки рівного розміру (34 ділянки)")
check("ступенів свободи похибки 27" in w._area_plan_status_lbl.cget("text"), "у підсумку плану – ступені свободи похибки")
d = w._build_scheme_dict(); cfg = d["cfg"]
check(cfg["design_used"] == "augmented" and cfg["standards"] == STD and cfg["group_std"]["пізні"] == "Стандарт пізній" and cfg["many_params"]["n_blocks"] == "10", "у файлі схеми: схема, стандарти, групи, параметри")
check(sum(1 for p in d["plants"] if p["kind"] == "standard") == 40 and all(p["block"] for p in d["plants"]), "ділянки схеми мають блок і тип (40 ділянок стандартів)")
print("   етикетки:")
data = Q.build_experiment(d, "S7Y6", "Соя – гібриди 2026"); check(len(data["plots"]) == 340 and data["exp"]["rep_word"] == "Блок" and sum(1 for p in data["plots"] if p["std"]) == 40, "етикетки: 340 ділянок, 40 позначено як стандарти, замість «повторність» – «блок»")
Q.fill_payloads(data, "descriptive", "m", "R58x40"); sp = next(p for p in data["plots"] if p["std"]); np_ = next(p for p in data["plots"] if not p["std"])
mat = Q.qr_matrix(sp["payload"])[0]; txt = " ".join(str(x[3]) for x in Q.label_prims(data, sp, "R58x40", mat) if x[0] == "text")
check("СТАНДАРТ" in txt and "блок" in txt.lower() and "СТАНДАРТ" not in " ".join(str(x[3]) for x in Q.label_prims(data, np_, "R58x40", Q.qr_matrix(np_["payload"])[0]) if x[0] == "text"), "на етикетці стандарту – «СТАНДАРТ», на гібриді – ні")
check("Блок" in sp["payload"] and "СТАНДАРТ" in sp["payload"], "у тексті QR – «Блок» і позначка стандарту")
pdf = os.path.join(TMP, "labels.pdf"); n_ = Q.render_labels_pdf(pdf, data, "R58x40", {"mono": True}); check(n_ == 340, "PDF рулонних етикеток для 340 ділянок")
folder = os.path.join(TMP, "Соя_гібриди"); os.makedirs(folder); SAVE["path"] = os.path.join(folder, "схема.sadp"); w._save_scheme(); root.update()
check(os.path.exists(SAVE["path"]), "схему збережено")
w2 = SC.SchemeConstructorWindow(root, {}); root.update(); w2._load_scheme(); root.update()
check(w2._area_design_disp.get() == AUG_DESIGN and w2._aug_blocks.get() == "10" and w2._std_cfg["standards"] == STD and len(w2._area_plan["plan"]) == 340 and sum(1 for p in w2._area_plan["plan"] if p["kind"] == "standard") == 40,
      "повторне відкриття: схема, блоки, стандарти, план із блоками й типами відновлено")
w2.win.destroy()

print("\n== 2. α-решітка")
wa = SC.SchemeConstructorWindow(root, {}); root.update(); wa._model_var.set("area"); wa._on_model_change(); root.update()
ENT = [f"Лінія {i:03d}" for i in range(1, 121)]; fill_factors(wa, [("Генотип", ", ".join(ENT + ["Ст А", "Ст Б"]))])
wa._area_design_disp.set(ALPHA_DESIGN); root.update(); wa._area_design_disp.set(AUG_DESIGN); root.update(); wa._area_design_disp.set(ALPHA_DESIGN); root.update()
check(wa._alpha_row.winfo_manager() == "pack" and wa._aug_row.winfo_manager() == "", "перемикання α-решітка → аугментована → α-решітка працює (раніше падало)")
wa._av["reps"].set("3"); wa._alpha_k.set("7"); root.update()
check("не діляться на блоки по 7" in wa._alpha_hint.cget("text") and "можливі розміри блоку" in wa._alpha_hint.cget("text").lower(), f"неможливий розмір блоку – перелік можливих: {wa._alpha_hint.cget('text')[:90]}")
wa._std_cfg = {"standards": ["Ст А", "Ст Б"], "groups": {}, "group_std": {}}; wa._alpha_checks.set(True); wa._alpha_k.set("10"); root.update()
check("120 номерів × 3 повторності" in wa._alpha_hint.cget("text") and "12 блоків по 12 ділянок" in wa._alpha_hint.cget("text"), f"підказка: {wa._alpha_hint.cget('text')}")
btn(wa._step3_area_content, "Сформувати план").invoke(); root.update(); pa = wa._area_plan["plan"]; lva = wa.factor_defs[0]["levels"]; nma = lambda p: lva[p["combo"][0] - 1]
check(len(pa) == 120 * 3 + 2 * 12 * 3, f"план: {len(pa)} ділянок (360 номерів + 72 стандартів)")
check(all(collections.Counter(nma(p) for p in pa if p["rep"] == r_ and p["kind"] == "new") == collections.Counter({e: 1 for e in ENT}) for r_ in (1, 2, 3)), "кожен номер – рівно раз у кожній повторності")
blocks = collections.defaultdict(list)
for p in pa: blocks[(p["rep"], p["block"])].append(p)
check(len(blocks) == 36 and all(len(v) == 12 and sorted(nma(p) for p in v if p["kind"] == "standard") == ["Ст А", "Ст Б"] for v in blocks.values()), "36 неповних блоків по 10 номерів + 2 стандарти")
check("A-ефективність" in wa._area_plan_status_lbl.cget("text"), "у підсумку – A-ефективність α-решітки")
da = wa._build_scheme_dict(); folder_a = os.path.join(TMP, "Лінії"); os.makedirs(folder_a); json.dump(da, open(os.path.join(folder_a, "схема.sadp"), "w", encoding="utf-8"), ensure_ascii=False)
fill_factors(wa, [("Генотип", "А, Б"), ("Добриво", "0, N60")]); wa._area_design_disp.set(ALPHA_DESIGN); root.update()
check("для одного фактора" in wa._area_size_status.cget("text"), "два фактори – пояснення, що ці схеми для одного фактора")
wa.win.destroy()

print("\n== 3. Польовий журнал: блоки й типи ділянок зберігаються")
rg = np.random.default_rng(5); eff = {e: rg.normal(0, 1.2) for e in HYB}; eff.update({"Стандарт ранній": -2.0, "Стандарт середній": 0.0, "Стандарт пізній": 2.5, "Стандарт 4": 0.5})
for e in HYB[:5]: eff[e] = 6.0                                     # 5 справді кращих гібридів
blk_eff = {b: rg.normal(0, 1.5) for b in range(1, 11)}
jw = JT.FieldJournalWindow(root, {}); root.update(); JT.filedialog.askopenfilename = lambda **k: os.path.join(folder, "схема.sadp"); jw._prompt_new_year = lambda: None; jw._open_file()
jw._current_year = "2026"; jw._load_year("2026"); root.update()
check(sum(1 for p in jw.plants if p.kind == "standard") == 40 and all(p.block for p in jw.plants), "журнал бачить блоки й стандарти схеми")
lvj = jw.factor_defs[0]["levels"]; truth = {}
for p in jw.plants:
    e = jw._entry_widgets[(p.row, p.position)]; name = lvj[p.factors["Гібрид"] - 1]; y = 30 + eff[name] + blk_eff[p.block] + rg.normal(0, 0.8); truth[(p.row, p.position)] = y
    e.delete(0, tk.END); e.insert(0, f"{y:.2f}".replace(".", ",")); jw._on_cell_edit(p.row, p.position)
jw._save_indicator(); root.update(); dl = [x for x in jw.win.winfo_children() if isinstance(x, tk.Toplevel) and x.title() == "Зберегти показник"][-1]
es = [x for x in dl.winfo_children()[0].winfo_children() if x.winfo_class() == "Entry"]; es[0].insert(0, "Урожайність"); es[1].insert(0, "ц/га")
[x for x in dl.winfo_children()[0].winfo_children() if x.winfo_class() == "Frame"][-1].winfo_children()[0].invoke(); root.update()
jf = os.path.join(folder, "2026", "журнал_2026.sadp"); jd = json.load(open(jf, encoding="utf-8"))
check(sum(1 for p in jd["plants"] if p.get("kind") == "standard") == 40 and all(p.get("block") for p in jd["plants"]) and jd["cfg"].get("standards") == STD, "файл журналу: блоки, типи ділянок і стандарти схеми збережено")
jw.win.destroy()
rows, info = JT.plot_table_from_journal({"2026": jd}, ["Урожайність"])
check(len(rows) == 340 and info["standards"] == STD and info["has_blocks"] and info["design"] == "augmented", "зведення «ділянка – рядок»: 340 ділянок, стандарти, блоки")
r0 = next(r for r in rows if r["entry"] == "Гібрид 007"); p7 = next((k, v) for k, v in truth.items() if lvj[[p for p in jd["plants"] if (p["row"], p["position"]) == k][0]["factors"]["Гібрид"] - 1] == "Гібрид 007")
check(abs(r0["Урожайність"] - round(p7[1], 2)) < 1e-9 and r0["kind"] == "new", "значення ділянки = внесене в журналі")

print("\n== 4. «Порівняння зі стандартом» з журналу (аналіз аугментованого досліду з урахуванням блоків)")
cw = BW.ControlWindow(root); root.update(); cw._from_journal((rows, ["Урожайність"], info)); root.update()
rws = cw.rows(); check(len(rws) == 340 and cw.header_names()[:3] == ["Номер (сорт)", "Повторність / блок", "Урожайність"] and cw.ctl_var.get() == "; ".join(STD) and cw.blocks_var.get(), "таблиця заповнена: 340 ділянок, блок, урожайність; стандарти зі схеми; блоки враховуються")
ref = CC.compare_to_control([r[0] for r in rws], [float(r[2].replace(",", ".")) for r in rws], STD, blocks=[r[1] for r in rws])
top = [x["entry"] for x in ref["rows"] if x["sig"] and x["diff"] > 0]
check(set(HYB[:5]) <= set(top), f"5 справді кращих гібридів виявлено як істотно кращі за середнє стандартів: {sorted(set(top) & set(HYB[:5]))}")
check(ref["df"] == 27, f"ступені свободи похибки = (c−1)(b−1) = 27: {ref['df']}")
cw.win.destroy()

print("\n== 5. «Змішана модель» з журналу (α-решітка) і фенологія")
dja = json.load(open(os.path.join(folder_a, "схема.sadp"), encoding="utf-8")); dja["type"] = "field_journal"
dja["records"] = {"Урожайність": {"unit": "т/га", "values": {f"{p['row']}:{p['position']}": f"{5 + rg.normal(0, .5):.2f}" for p in dja["plants"] if p["role"] == "recorded"}}}
rows_a, info_a = JT.plot_table_from_journal({"2025": dja, "2026": dja}, ["Урожайність"])
mw = BW.MixedWindow(root); root.update(); mw._from_journal((rows_a, ["Урожайність"], info_a)); root.update(); rm = mw.rows()
check(len(rm) == 2 * 432 and mw.header_names()[:5] == ["Генотип", "Середовище", "Повторність", "Блок", "Урожайність"] and mw.blk_var.get() and mw.mode_var.get().startswith("Серія"), "змішана модель: 2 роки × 432 ділянки, повторність, неповний блок, серія дослідів")
check(rm[0][3].count(".") == 1 and len({r[3] for r in rm if r[1] == "2025"}) == 36, "блок записано як «повторність.блок» (36 унікальних блоків на рік)")
mw.win.destroy()
jph = dict(jd); jph["records"] = dict(jd["records"]); jph["records"]["Цвітіння"] = {"kind": "date", "preset": "soy", "phase_key": "bloom0", "phase_name": "Початок цвітіння (≈ 10 % квіток)", "values": {f"{p['row']}:{p['position']}": "05.07.2026" for p in jd["plants"]}}
rp = PJ.from_journal_years({"2026": jph}); check(rp["standards"] == STD and rp["group_std"]["ранні"] == "Стандарт ранній" and rp["groups"]["Гібрид 001"] == "ранні" and rp["preset"] == "soy", "фенологія отримує стандарти й групи стиглості зі схеми; набір фаз сої")
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ДОСЛІДІВ ІЗ БАГАТЬМА НОМЕРАМИ ПРОЙДЕНО")
