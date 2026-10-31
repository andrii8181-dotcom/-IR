# test_sad_journal_phenology.py – сортовивчення наскрізно: схема → польовий журнал (фенофази, урожайність) → аналізи й модуль фенології
import os, sys, json, math, tempfile, shutil, statistics, datetime as dt
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
import sad_phenology as P, sad_phenology_journal as PJ
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
D = dt.date; TMP = tempfile.mkdtemp(prefix="sad_jph_")
CV = ["Голден Делішес", "Гала", "Фуджі"]; PLANTS_PER_PLOT = 3
def scheme_dict():
    """Сортовивчення: фактор «Сорт» (3 сорти), 3 повторності (ряди), по 3 облікові дерева на ділянку, захисні дерева на краях ряду."""
    plants = []
    for b in range(1, 4):
        pos = 1; plants.append({"row": b, "position": pos, "role": "guard_edge", "replication": None, "factors": {}}); pos += 1
        order = [(b + i) % 3 + 1 for i in range(3)]
        for c in order:
            for k in range(PLANTS_PER_PLOT): plants.append({"row": b, "position": pos, "role": "recorded", "replication": b, "factors": {"Сорт": c}}); pos += 1
        plants.append({"row": b, "position": pos, "role": "guard_edge", "replication": None, "factors": {}})
    return {"type": "multi_factor_scheme", "factor_defs": [{"name": "Сорт", "levels": CV}], "variant_names": [], "cfg": {"model": "plant"}, "plants": plants}
SCH = scheme_dict(); folder = os.path.join(TMP, "Сортовивчення_яблуні"); os.makedirs(folder); sp = os.path.join(folder, "схема.sadp")
json.dump(SCH, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
OFF = {"Голден Делішес": 0, "Гала": 3, "Фуджі": 8}
def plant_date(pl, year, base, extra=0):
    c = CV[pl["factors"]["Сорт"] - 1]; return D(year, 5, 1) + dt.timedelta(days=base + OFF[c] + (pl["position"] % 3) - 1 + extra)

print("== 1. Перетворення журналу на дані фенології (без вікон)")
def journal_json(year, extra=0, with_dates=True):
    rec = {"Урожайність": {"unit": "кг/дерево", "values": {f"{p['row']}:{p['position']}": str(20 + p["position"]) for p in SCH["plants"] if p["role"] == "recorded"}}}
    if with_dates:
        rec["Початок цвітіння (≈ 10 % квіток) (61)"] = {"unit": "дата", "kind": "date", "preset": "pome", "phase_key": "bloom0", "bbch": "61", "phase_name": "Початок цвітіння (≈ 10 % квіток)",
                                                        "values": {f"{p['row']}:{p['position']}": P.fmt_date(plant_date(p, year, 0, extra)) for p in SCH["plants"] if p["role"] == "recorded"}}
        rec["Моя фаза"] = {"unit": "дата", "kind": "date", "phase_name": "Моя фаза", "values": {f"{p['row']}:{p['position']}": P.fmt_date(plant_date(p, year, 30, extra)) for p in SCH["plants"] if p["role"] == "recorded"}}
    return {"type": "field_journal", "year": str(year), **{k: SCH[k] for k in ("factor_defs", "variant_names", "cfg", "plants")}, "records": rec}
res = PJ.from_journal_years({"2025": journal_json(2025), "2026": journal_json(2026, extra=2)})
check(res["preset"] == "pome" and res["factor"] == "Сорт" and res["cultivars"] == ["Голден Делішес", "Гала", "Фуджі"] or set(res["cultivars"]) == set(CV), f"набір фаз з журналу – яблуня; сорти – рівні фактора «Сорт»: {res['cultivars']}")
check(sorted(res["years_data"]) == [2025, 2026] and len(res["years_data"][2025]) == 9 and all(r["rep"] in ("1", "2", "3") for r in res["years_data"][2025]), "2 роки, по 9 ділянок (3 сорти × 3 повторності)")
r0 = next(r for r in res["years_data"][2025] if r["name"] == "Гала" and r["rep"] == "2")
pl_g = [p for p in SCH["plants"] if p["role"] == "recorded" and p["replication"] == 2 and p["factors"]["Сорт"] == 2]; med = sorted(plant_date(p, 2025, 0) for p in pl_g)[1]
check(r0["dates"]["bloom0"] == P.fmt_date(med), f"дата ділянки – медіана дат її {len(pl_g)} дерев: {r0['dates']['bloom0']}")
check([p["key"] for p in res["phases"]][:len(P.PRESETS["pome"]["phases"])] == [p["key"] for p in P.PRESETS["pome"]["phases"]] and res["phases"][-1]["name"] == "Моя фаза" and any("поза набором" in n for n in res["notes"]), "фази набору культури + власна фаза наприкінці (з поясненням)")
check(res["n_dates"] == 2 * 9 * 2 and "Урожайність" not in str(res["phases"]), "числові показники (урожайність) у фенологію не потрапляють; дат – 36")
try: PJ.from_journal_years({"2025": journal_json(2025, with_dates=False)}); check(False, "мало впасти")
except ValueError as e: check("🌸 Фенофаза" in str(e), "журнал без фенофаз – пояснення, як їх додати")
hom = {"type": "field_journal", "factor_defs": [], "variant_names": ["Сорт А", "Сорт Б"], "plants": [{"row": 1, "position": i + 1, "role": "recorded", "replication": i // 2 + 1, "variant": i % 2 + 1, "factors": {}} for i in range(4)],
       "records": {"Ф": {"kind": "date", "preset": "vine", "phase_key": "bloom0", "phase_name": "Початок цвітіння", "values": {"1:1": "02.06.2025", "1:2": "05.06.2025", "1:3": "03.06.2025", "1:4": "06.06.2025"}}}}
rh = PJ.from_journal_years({"2025": hom}); check(rh["preset"] == "vine" and sorted((r["name"], r["rep"], r["dates"]["bloom0"]) for r in rh["years_data"][2025]) == [("Сорт А", "1", "02.06.2025"), ("Сорт А", "2", "03.06.2025"), ("Сорт Б", "1", "05.06.2025"), ("Сорт Б", "2", "06.06.2025")], "однофакторна схема (назви варіантів) і виноград")
two = dict(journal_json(2025)); two["factor_defs"] = [{"name": "Сорт", "levels": CV}, {"name": "Підщепа", "levels": ["М9", "ММ106"]}]; two["plants"] = [dict(p, factors=dict(p["factors"], Підщепа=1)) if p["role"] == "recorded" else p for p in SCH["plants"]]
check(PJ.from_journal_years({"2025": two})["cultivars"] == res["cultivars"], "двофакторна схема: сорт береться з фактора «Сорт»")
check(PJ._cultivar_factor([{"name": "Добриво", "levels": [1]}, {"name": "Гібрид", "levels": [1]}]) == 1 and PJ._cultivar_factor([{"name": "А", "levels": [1]}, {"name": "Б", "levels": [1]}]) is None, "фактор сорту впізнається за назвою (Сорт, Гібрид, Генотип…)")

print("\n== 2. Аналізи з журналу: дата фенофази → номер дня року")
import sad_journal_trial as JT
jj = journal_json(2025); plants = JT._plants_from_saved(jj["plants"])
fc, rows = JT.aggregate_journal_data(plants, jj["factor_defs"], [], jj["records"], ["Початок цвітіння (≈ 10 % квіток) (61)", "Урожайність"])
rg = next(r for r in rows if r["Сорт"] == "Гала" and r["replication"] == 2)
check(abs(rg["Початок цвітіння (≈ 10 % квіток) (61)"] - statistics.mean(P.doy_norm(plant_date(p, 2025, 0)) for p in pl_g)) < 1e-9, f"для ANOVA та інших аналізів дата стає номером дня року (середнє дерев ділянки): {rg['Початок цвітіння (≈ 10 % квіток) (61)']}")
check(abs(rg["Урожайність"] - statistics.mean(20 + p["position"] for p in pl_g)) < 1e-9, "числовий показник – як і раніше")
jl = journal_json(2024); fc2, rows2 = JT.aggregate_journal_data(JT._plants_from_saved(jl["plants"]), jl["factor_defs"], [], jl["records"], ["Початок цвітіння (≈ 10 % квіток) (61)"])
r24 = next(r for r in rows2 if r["Сорт"] == "Гала" and r["replication"] == 2); check(abs(r24["Початок цвітіння (≈ 10 % квіток) (61)"] - rg["Початок цвітіння (≈ 10 % квіток) (61)"]) < 1e-9, "високосний 2024 і звичайний 2025: та сама календарна дата – той самий номер дня")

if os.environ.get("DISPLAY"):
    print("\n== 3. Польовий журнал: облік фенофази у вікні")
    import tkinter as tk
    from tkinter import messagebox
    LOG = []
    for m in (JT.messagebox,): m.showinfo = lambda t="", msg="", **k: LOG.append(("info", msg)); m.showwarning = lambda t="", msg="", **k: LOG.append(("warn", msg)); m.askyesno = lambda *a, **k: True
    root = tk.Tk(); root.withdraw(); win = JT.FieldJournalWindow(root, {}); root.update()
    btn = [b for b in [w for w in win.win.winfo_children()][0].winfo_children() if b.winfo_class() == "Button" and "Фенофаза" in b.cget("text")]; check(len(btn) == 1, "у журналі є кнопка «🌸 Фенофаза…»")
    JT.filedialog.askopenfilename = lambda **k: sp; win._prompt_new_year = lambda: None; win._open_file(); win._current_year = "2025"; win._load_year("2025"); root.update()
    check(len([p for p in win.plants if p.role == JT.HP_ROLE_RECORDED]) == 27, "схема відкрита: 27 облікових дерев (3 сорти × 3 повторності × 3 дерева)")
    def save_dialog(name=None, unit=None):
        win._save_indicator(); root.update(); dl = [w for w in win.win.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == "Зберегти показник"][-1]
        ents = [w for w in dl.winfo_children()[0].winfo_children() if w.winfo_class() == "Entry"]
        vals_ = (ents[0].get(), ents[1].get())
        if name is not None: ents[0].delete(0, tk.END); ents[0].insert(0, name)
        if unit is not None: ents[1].delete(0, tk.END); ents[1].insert(0, unit)
        b_ = [w for w in dl.winfo_children()[0].winfo_children() if w.winfo_class() == "Frame"][-1].winfo_children()[0]; b_.invoke(); root.update(); return vals_
    win._new_phase_indicator("pome", "bloom0"); root.update()
    check(win._is_date_ind() and win._pending_meta["phase_key"] == "bloom0" and win._pending_meta["bbch"] == "61" and "BBCH 61" in LOG[-1][1], "обрано фенофазу «Початок цвітіння (61)»; підказка з критерієм BBCH")
    rec_pl = [p for p in win.plants if p.role == JT.HP_ROLE_RECORDED]
    forms = ["{d:%d.%m}", "{d:%d%m}", "{d.day} травня"]
    for i, p in enumerate(rec_pl):
        e = win._entry_widgets[(p.row, p.position)]; d = plant_date({"factors": p.factors, "position": p.position}, 2025, 0); e.delete(0, tk.END); e.insert(0, forms[i % 3].format(d=d)); win._on_cell_edit(p.row, p.position)
    e0 = win._entry_widgets[(rec_pl[0].row, rec_pl[0].position)]
    check(all(win._working_values[f"{p.row}:{p.position}"] == P.fmt_date(plant_date({"factors": p.factors, "position": p.position}, 2025, 0)) for p in rec_pl), "дати в будь-якому записі (12.05, 1205, «12 травня») нормалізовано до дд.мм.рррр")
    check(e0.get().endswith(".2025"), f"у клітинці – повна дата: {e0.get()}")
    eb = win._entry_widgets[(rec_pl[1].row, rec_pl[1].position)]; eb.delete(0, tk.END); eb.insert(0, "31.04"); win._on_cell_edit(rec_pl[1].row, rec_pl[1].position)
    check(str(eb.cget("bg")) == "#ffcdd2" and f"{rec_pl[1].row}:{rec_pl[1].position}" not in win._working_values, "неіснуюча дата (31.04): червона клітинка, значення не зберігається")
    d1 = plant_date({"factors": rec_pl[1].factors, "position": rec_pl[1].position}, 2025, 0); eb.delete(0, tk.END); eb.insert(0, d1.strftime("%d.%m")); win._on_cell_edit(rec_pl[1].row, rec_pl[1].position)
    nm_unit = save_dialog(); name0 = "Початок цвітіння (≈ 10 % квіток) (61)"
    check(nm_unit == (name0, "дата"), f"діалог збереження: назва й одиниця підставлені ({nm_unit})")
    jp = os.path.join(folder, "2025", "журнал_2025.sadp"); jd = json.load(open(jp, encoding="utf-8")); rr = jd["records"].get(name0, {})
    check(rr.get("kind") == "date" and rr.get("preset") == "pome" and rr.get("phase_key") == "bloom0" and rr.get("bbch") == "61" and len(rr.get("values", {})) == 27, "журнал на диску: показник типу «дата», культура, фаза, BBCH, 27 дат")
    check(win._pending_meta is None and not win._is_date_ind(), "після збереження таблиця готова до наступного показника")
    for p in rec_pl:                                                      # урожайність – звичайний числовий показник поряд
        e = win._entry_widgets[(p.row, p.position)]; e.delete(0, tk.END); e.insert(0, str(20 + p.position).replace(".", ",")); win._on_cell_edit(p.row, p.position)
    save_dialog("Урожайність", "кг/дерево"); jd = json.load(open(jp, encoding="utf-8"))
    check("kind" not in jd["records"]["Урожайність"] and jd["records"]["Урожайність"]["unit"] == "кг/дерево" and len(jd["records"]["Урожайність"]["values"]) == 27, "урожайність збережено як звичайний числовий показник")
    win._new_phase_indicator("pome", "bloom1"); root.update()
    for p in rec_pl:
        e = win._entry_widgets[(p.row, p.position)]; e.delete(0, tk.END); e.insert(0, P.fmt_date(plant_date({"factors": p.factors, "position": p.position}, 2025, 11))); win._on_cell_edit(p.row, p.position)
    save_dialog(); jd = json.load(open(jp, encoding="utf-8")); check(jd["records"].get("Кінець цвітіння (69)", {}).get("phase_key") == "bloom1", "другу фенофазу (кінець цвітіння) збережено")
    win._record_var.set(name0); win._switch_record(name0); root.update(); check(win._is_date_ind() and win._entry_widgets[(rec_pl[0].row, rec_pl[0].position)].get().endswith(".2025"), "повернення до збереженого показника фенофази: дати на місці, тип «дата» зберігся")
    n_l = len(LOG); win._new_phase_indicator("pome", "bloom0"); check(win._current_indicator_name == name0 and win._pending_meta is None, "повторний вибір уже облікованої фази відкриває наявний показник, а не дублює")
    win._record_var.set("(новий показник)"); win._switch_record("(новий показник)"); win._current_year = "2026"; win._load_year("2026"); root.update()
    win._new_phase_indicator("pome", "bloom0"); rec_pl = [p for p in win.plants if p.role == JT.HP_ROLE_RECORDED]
    for p in rec_pl:
        e = win._entry_widgets[(p.row, p.position)]; e.delete(0, tk.END); e.insert(0, plant_date({"factors": p.factors, "position": p.position}, 2026, 0, 2).strftime("%d.%m")); win._on_cell_edit(p.row, p.position)
    save_dialog(); check(os.path.exists(os.path.join(folder, "2026", "журнал_2026.sadp")), "другий рік (2026) збережено окремим журналом у теці схеми")
    eo = win._entry_widgets[(rec_pl[0].row, rec_pl[0].position)]; win._new_phase_indicator("pome", "bloom1"); eo = win._entry_widgets[(rec_pl[0].row, rec_pl[0].position)]
    eo.delete(0, tk.END); eo.insert(0, "10.05.2025"); win._on_cell_edit(rec_pl[0].row, rec_pl[0].position); check(str(eo.cget("bg")) == "#fff3e0", "дата з іншого року – оранжева клітинка (попередження)")
    win._working_values = {}; win._pending_meta = None

    print("\n== 4. Модуль фенології: «З польового журналу»")
    import sad_phenology_win as PW
    for m in (PW.messagebox,): m.showinfo = lambda t="", msg="", **k: LOG.append(("info", msg)); m.askyesno = lambda *a, **k: True
    pw = PW.PhenologyWindow(root); root.update(); btj = [b for b in [x for x in pw.win.winfo_children() if x.winfo_class() == "Frame"][1].winfo_children() if b.winfo_class() == "Button" and "журналу" in b.cget("text")]
    check(len(btj) == 1, "у фенології є кнопка «📂 З польового журналу…»")
    JT.filedialog.askopenfilename = lambda **k: jp; out_ = pw.import_journal(); root.update()
    check(out_ is not None and sorted(pw.years_data) == [2025, 2026] and pw.preset_key == "pome", f"перенесено обидва роки, набір фаз – яблуня: {sorted(pw.years_data)}")
    check("сортів 3" in LOG[-1][1] and "фактор «Сорт»" in LOG[-1][1] and "медіана" in LOG[-1][1], f"підсумок імпорту: {LOG[-1][1][:110]}…")
    r25 = {(r["name"], r["rep"]): r["dates"] for r in pw.years_data[2025]}; pg = [p for p in SCH["plants"] if p["role"] == "recorded" and p["replication"] == 2 and p["factors"]["Сорт"] == 2]
    check(r25[("Гала", "2")]["bloom0"] == P.fmt_date(sorted(plant_date(p, 2025, 0) for p in pg)[1]) and "bloom1" in r25[("Гала", "2")], "дати ділянок (медіана дерев) для обох фаз 2025 року")
    check(pw.cur_year == 2026 and pw.entries[0][0].get() in CV and pw.entries[0][PW.COL0 + [p["key"] for p in pw.phases].index("bloom0")].get().endswith(".2026"), "у таблиці – останній рік із датами")
    pw.std_var.set("Голден Делішес"); pw.standard = "Голден Делішес"; ctx = pw._run(); root.update()
    check(ctx is not None and ctx["years"] == [2025, 2026] and ctx["vs"][("Фуджі", "bloom0")][1] == "пізній", "аналіз фенології за даними журналу: Фуджі пізніше стандарту")
    pw.results_win.win.destroy(); pw.win.destroy(); win.win.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ «СХЕМА → ЖУРНАЛ → ФЕНОЛОГІЯ» ПРОЙДЕНО")
