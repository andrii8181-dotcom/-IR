# sad_journal_trial.py — Польовий журнал, генератор плану досліду
# -*- coding: utf-8 -*-
from sad_common import *
from sad_homogeneous import (HPPlant, HP_ROLE_RECORDED, HP_ROLE_GUARD_EDGE,
    HP_ROLE_GUARD_REP, HP_ROLE_DEAD, HP_ROLE_POLLINIZER, HP_ROLE_UNASSIGNED,
    HP_ROLE_EXTRA, HP_ROLE_EXCLUDED_CV, HP_ROLE_COLORS, HP_ROLE_LABELS)


# ═══════════════════════════════════════════════════════════════
# СПІЛЬНІ ФУНКЦІЇ «ВІДКРИТИ ПОКАЗНИК» — використовуються з будь-якого
# модуля аналізу (ANOVA, регресія, кореляція, PCA, кластерний) для
# імпорту даних, збережених у польовому журналі, без ручного
# копіювання-вставляння.
# ═══════════════════════════════════════════════════════════════

def load_journal_file(parent):
    """Відкриває діалог вибору файлу журналу (.sadp, type=field_journal).
    Повертає dict {"plants","factor_defs","variant_names","records"} або
    None, якщо скасовано чи файл не підходить."""
    path = filedialog.askopenfilename(
        parent=parent, filetypes=[("SAD журнал","*.sadp"),("JSON","*.json")],
        title="Відкрити журнал обліків")
    if not path: return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as ex:
        messagebox.showerror("Помилка відкриття", str(ex)); return None
    if d.get("type") != "field_journal":
        messagebox.showwarning("Не той тип файлу",
            "Показники зберігаються в ЖУРНАЛІ обліків, а не в самій схемі без "
            "внесених даних. Відкрийте файл, збережений через «💾 Зберегти "
            "журнал» у польовому журналі обліків."); return None

    plants = []
    for pd in d.get("plants", []):
        p = HPPlant(pd["row"], pd["position"], pd.get("value"), pd.get("status","ok"))
        p.role = pd.get("role", HP_ROLE_UNASSIGNED)
        p.variant = pd.get("variant")
        p.replication = pd.get("replication")
        p.factors = pd.get("factors", {})
        plants.append(p)

    records = d.get("records", {})
    if not records:
        messagebox.showwarning("Немає обліків",
            "У цьому журналі ще немає жодного внесеного показника."); return None

    return {"plants": plants, "factor_defs": d.get("factor_defs", []),
            "variant_names": d.get("variant_names", []), "records": records,
            "path": path}


def aggregate_journal_data(plants, factor_defs, variant_names, records, record_names):
    """Зводить журнал у таблицю: один рядок на КОЖНУ повторність — значення
    облікових рослин У МЕЖАХ однієї повторності усереднюються в одне число
    (уникає псевдоповторності). Повертає (factor_cols, rows)."""
    is_multi = bool(factor_defs) and any(p.factors for p in plants)
    groups = {}
    for p in plants:
        if p.role != HP_ROLE_RECORDED: continue
        if is_multi:
            key = (tuple(sorted(p.factors.items())), p.replication)
        else:
            key = (p.variant, p.replication)
        groups.setdefault(key, []).append(p)

    factor_cols = [fdef["name"] for fdef in factor_defs] if is_multi else ["Варіант"]
    rows = []
    for key in sorted(groups.keys(), key=lambda k: (str(k[0]), k[1] or 0)):
        plist = groups[key]
        row = {"replication": key[1], "n_subsamples": len(plist)}
        if is_multi:
            factor_levels = dict(key[0])
            for fdef in factor_defs:
                fname = fdef["name"]; lv = factor_levels.get(fname)
                lvl_name = (fdef["levels"][lv-1] if lv and 1 <= lv <= len(fdef["levels"])
                           else f"Рівень {lv}")
                row[fname] = lvl_name
        else:
            v = key[0]
            vname = (variant_names[v-1] if variant_names and v and
                     1 <= v <= len(variant_names) else f"В{v}")
            row["Варіант"] = vname
        for rn in record_names:
            vals_dict = records.get(rn, {}).get("values", {})
            vals = []
            for p in plist:
                vkey = f"{p.row}:{p.position}"
                raw = vals_dict.get(vkey)
                if raw is None or str(raw).strip() == "": continue
                try: vals.append(float(str(raw).replace(",",".")))
                except ValueError: pass
            row[rn] = round(sum(vals)/len(vals), 4) if vals else None
        rows.append(row)
    return factor_cols, rows


def aggregate_to_variant_level(factor_cols, rows, record_names):
    """Друге усереднення — рядки (варіант×повторність), вже усереднені в
    межах повторності, усереднюються ЩЕ РАЗ по повторностях: одне число
    на варіант для кожного показника. Стандартний підхід для порівняння
    варіантів/сортів за кількома показниками одночасно (регресія,
    кореляція, PCA, кластерний аналіз)."""
    groups = {}
    for r in rows:
        key = tuple(r[fc] for fc in factor_cols)
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups.keys()):
        plist = groups[key]
        row = dict(zip(factor_cols, key))
        for rn in record_names:
            vals = [r[rn] for r in plist if r[rn] is not None]
            row[rn] = round(sum(vals)/len(vals), 4) if vals else None
        out.append(row)
    return out


def pick_indicators_dialog(parent, records, multi_select=False, n_required=None):
    """Показує список показників журналу для вибору. multi_select=False —
    один показник (радіо), True — довільна кількість чекбоксами.
    n_required — якщо задано (напр. 2 для регресії), вимагає рівно
    стільки позначених. Повертає list обраних назв, або None якщо
    скасовано.

    Якщо вибирати нема з чого (в журналі рівно один показник, або рівно
    стільки, скільки потрібно) — діалог НЕ показується, показники
    підставляються одразу: користувач уже обрав ПОТРІБНИЙ ФАЙЛ, і
    повторно питати «який саме показник» було б дублюванням, коли
    відповідь однозначна."""
    names = list(records.keys())
    if n_required and len(names) < n_required:
        messagebox.showwarning("", f"У журналі лише {len(names)} показник(и), "
                                   f"а для цього аналізу потрібно {n_required}.",
                               parent=parent)
        return None
    if n_required and len(names) == n_required:
        return names
    if not multi_select and len(names) == 1:
        return names

    result = {"value": None}
    dlg = tk.Toplevel(parent); dlg.title("Оберіть показник" + ("и" if multi_select else ""))
    dlg.resizable(False, False); set_icon(dlg); dlg.grab_set()
    rf = ("Times New Roman",11)
    frm = tk.Frame(dlg, padx=18, pady=14); frm.pack()
    tk.Label(frm, text="Оберіть показник" + (f" (рівно {n_required})" if n_required else
             " (один чи кілька)" if multi_select else "") + ":",
             font=("Times New Roman",11,"bold")).pack(anchor="w", pady=(0,8))

    if multi_select:
        vars_ = {nm: tk.BooleanVar(value=False) for nm in names}
        for nm in names:
            unit = records[nm].get("unit","")
            tk.Checkbutton(frm, text=f"{nm}" + (f" ({unit})" if unit else ""),
                          variable=vars_[nm], font=rf).pack(anchor="w")
    else:
        sel = tk.StringVar(value=names[0] if names else "")
        for nm in names:
            unit = records[nm].get("unit","")
            tk.Radiobutton(frm, text=f"{nm}" + (f" ({unit})" if unit else ""),
                          variable=sel, value=nm, font=rf).pack(anchor="w")

    def _ok():
        if multi_select:
            chosen = [nm for nm in names if vars_[nm].get()]
            if n_required and len(chosen) != n_required:
                messagebox.showwarning("",
                    f"Оберіть рівно {n_required} показники.", parent=dlg); return
            if not chosen:
                messagebox.showwarning("", "Оберіть хоча б один показник.", parent=dlg); return
            result["value"] = chosen
        else:
            if not sel.get():
                messagebox.showwarning("", "Оберіть показник.", parent=dlg); return
            result["value"] = [sel.get()]
        dlg.destroy()

    bf = tk.Frame(frm); bf.pack(pady=(12,0))
    tk.Button(bf, text="Обрати", bg="#1a6b1a", fg="white", font=rf,
              command=_ok).pack(side=tk.LEFT, padx=4)
    tk.Button(bf, text="Скасувати", font=rf, command=dlg.destroy).pack(side=tk.LEFT)
    center_win(dlg)
    dlg.wait_window()
    return result["value"]


def open_indicator_for_anova(parent):
    """Для ANOVA: варіант(и) × повторність. Повертає (factor_cols, rows)
    або None. rows містять "replication" і значення показника —
    придатні для прямого широкоформатного розкладання в таблицю ANOVA."""
    data = load_journal_file(parent)
    if data is None: return None
    chosen = pick_indicators_dialog(parent, data["records"], multi_select=False)
    if not chosen: return None
    factor_cols, rows = aggregate_journal_data(
        data["plants"], data["factor_defs"], data["variant_names"], data["records"], chosen)
    return factor_cols, rows, chosen[0]


def open_indicators_for_variant_analysis(parent, multi_select=True, n_required=None):
    """Для регресії/кореляції/PCA/кластерного: варіант-рівень (подвійне
    усереднення). Повертає (factor_cols, rows, record_names) або None.
    rows — по одному запису на варіант, значення — вже усереднені і в
    межах повторності, і по повторностях."""
    data = load_journal_file(parent)
    if data is None: return None
    chosen = pick_indicators_dialog(parent, data["records"],
                                    multi_select=multi_select, n_required=n_required)
    if not chosen: return None
    factor_cols, rows = aggregate_journal_data(
        data["plants"], data["factor_defs"], data["variant_names"], data["records"], chosen)
    variant_rows = aggregate_to_variant_level(factor_cols, rows, chosen)
    return factor_cols, variant_rows, chosen


def open_indicators_replication_level(parent, multi_select=True, n_required=None):
    """Для описової статистики / MANOVA / повторних вимірів: рівень
    ПОВТОРНОСТІ (без другого усереднення до варіанту) — кожен рядок
    довгого формату (варіант×повторність) лишається окремим
    спостереженням. Повертає (factor_cols, rows, record_names) де rows
    — довгий формат, кожен показник — свій ключ у кожному рядку."""
    data = load_journal_file(parent)
    if data is None: return None
    chosen = pick_indicators_dialog(parent, data["records"],
                                    multi_select=multi_select, n_required=n_required)
    if not chosen: return None
    factor_cols, rows = aggregate_journal_data(
        data["plants"], data["factor_defs"], data["variant_names"], data["records"], chosen)
    return factor_cols, rows, chosen


def pick_two_groups_dialog(parent, group_labels):
    """Показує список унікальних комбінацій факторів (варіантів) для
    вибору РІВНО ДВОХ — для порівняння двох груп (t-тест). Повертає
    (idx_a, idx_b) або None."""
    result = {"value": None}
    dlg = tk.Toplevel(parent); dlg.title("Оберіть дві групи для порівняння")
    dlg.resizable(False, False); set_icon(dlg); dlg.grab_set()
    rf = ("Times New Roman",11)
    frm = tk.Frame(dlg, padx=18, pady=14); frm.pack()
    tk.Label(frm, text="Група 1:", font=rf).grid(row=0, column=0, sticky="w", pady=4)
    v1 = tk.StringVar(value=group_labels[0] if group_labels else "")
    ttk.Combobox(frm, textvariable=v1, values=group_labels, state="readonly", width=28
                 ).grid(row=0, column=1, sticky="w", padx=8)
    tk.Label(frm, text="Група 2:", font=rf).grid(row=1, column=0, sticky="w", pady=4)
    v2 = tk.StringVar(value=group_labels[1] if len(group_labels) > 1 else "")
    ttk.Combobox(frm, textvariable=v2, values=group_labels, state="readonly", width=28
                 ).grid(row=1, column=1, sticky="w", padx=8)

    def _ok():
        if v1.get() == v2.get():
            messagebox.showwarning("", "Оберіть дві РІЗНІ групи.", parent=dlg); return
        result["value"] = (group_labels.index(v1.get()), group_labels.index(v2.get()))
        dlg.destroy()
    bf = tk.Frame(frm); bf.grid(row=2, column=0, columnspan=2, pady=(12,0))
    tk.Button(bf, text="Обрати", bg="#1a6b1a", fg="white", font=rf,
              command=_ok).pack(side=tk.LEFT, padx=4)
    tk.Button(bf, text="Скасувати", font=rf, command=dlg.destroy).pack(side=tk.LEFT)
    center_win(dlg)
    dlg.wait_window()
    return result["value"]


def open_two_groups_for_ttest(parent):
    """Для t-тесту: один показник, дві групи (комбінації факторів) для
    порівняння — значення на рівні повторності (не варіанту, щоб було
    достатньо спостережень для критерію). Повертає
    (values_a, values_b, label_a, label_b, record_name) або None."""
    data = load_journal_file(parent)
    if data is None: return None
    chosen = pick_indicators_dialog(parent, data["records"], multi_select=False)
    if not chosen: return None
    record_name = chosen[0]
    factor_cols, rows = aggregate_journal_data(
        data["plants"], data["factor_defs"], data["variant_names"], data["records"], chosen)
    combos = sorted({tuple(r[fc] for fc in factor_cols) for r in rows})
    if len(combos) < 2:
        messagebox.showwarning("", "У журналі менше двох варіантів — нема що порівнювати.",
                               parent=parent); return None
    labels = [" / ".join(map(str, c)) for c in combos]
    picked = pick_two_groups_dialog(parent, labels)
    if picked is None: return None
    idx_a, idx_b = picked
    values_a = [r[record_name] for r in rows
                if tuple(r[fc] for fc in factor_cols) == combos[idx_a] and r[record_name] is not None]
    values_b = [r[record_name] for r in rows
                if tuple(r[fc] for fc in factor_cols) == combos[idx_b] and r[record_name] is not None]
    return values_a, values_b, labels[idx_a], labels[idx_b], record_name


def _plants_from_saved(plants_data):
    """Відновлює список HPPlant із збереженого списку словників (без
    значень — для агрегації достатньо ролі/варіанту/повторності/факторів,
    самі значення читаються окремо з відповідного records[...]["values"])."""
    plants = []
    for pd in plants_data:
        p = HPPlant(pd["row"], pd["position"], None, pd.get("status","ok"))
        p.role = pd.get("role", HP_ROLE_UNASSIGNED)
        p.plot_id = pd.get("plot_id"); p.variant = pd.get("variant")
        p.replication = pd.get("replication"); p.factors = pd.get("factors", {})
        plants.append(p)
    return plants


def _find_scheme_file_in_folder(folder):
    """Шукає файл самої схеми (без записів) у корені теки."""
    if not folder or not os.path.isdir(folder): return None
    for name in os.listdir(folder):
        full = os.path.join(folder, name)
        if not os.path.isfile(full) or not name.lower().endswith((".sadp",".json")):
            continue
        try:
            with open(full, "r", encoding="utf-8") as f:
                dd = json.load(f)
            if dd.get("type") in ("homogeneous_plot_scheme", "multi_factor_scheme"):
                return full
        except Exception:
            continue
    return None


def _find_scheme_folder_and_years(parent, title="Оберіть будь-який файл у теці схеми"):
    """Відкриває діалог вибору файлу (схема чи файл конкретного року),
    визначає теку схеми і сканує в ній усі підтеки-роки з журналами.
    Повертає (scheme_folder, {year: parsed_json_dict}) або None."""
    path = filedialog.askopenfilename(
        parent=parent, filetypes=[("SAD файл","*.sadp"),("JSON","*.json")], title=title)
    if not path: return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as ex:
        messagebox.showerror("Помилка відкриття", str(ex), parent=parent); return None

    ftype = d.get("type")
    if ftype == "field_journal":
        scheme_folder = os.path.dirname(os.path.dirname(path))
    elif ftype in ("homogeneous_plot_scheme", "multi_factor_scheme"):
        scheme_folder = os.path.dirname(path)
    else:
        messagebox.showwarning("Не той тип файлу",
            "Оберіть файл схеми або журналу конкретного року.", parent=parent); return None

    years_data = {}
    if os.path.isdir(scheme_folder):
        for name in sorted(os.listdir(scheme_folder)):
            year_path = os.path.join(scheme_folder, name)
            if os.path.isdir(year_path) and name.isdigit():
                jf = os.path.join(year_path, f"журнал_{name}.sadp")
                if os.path.exists(jf):
                    try:
                        with open(jf, "r", encoding="utf-8") as f:
                            years_data[name] = json.load(f)
                    except Exception:
                        continue
    if not years_data:
        messagebox.showwarning("Немає даних за жоден рік",
            "У теці схеми ще немає жодного збереженого журналу за рік.", parent=parent)
        return None
    return scheme_folder, years_data


def open_indicator_across_years(parent):
    """Для того самого показника, виміряного КІЛЬКА РОКІВ на тих самих
    об'єктах (той самий сад/схема) — одна назва показника, обрана один
    раз, тягнеться з усіх наявних років теки схеми. Повертає
    (factor_cols, rows, years_present, indicator_name) або None. rows —
    рядок на кожну (комбінація факторів × повторність), стовпці —
    роки (значення — середнє в межах повторності за той рік) — готовий
    формат для «Змішаного RM»."""
    found = _find_scheme_folder_and_years(parent,
        title="Оберіть будь-який файл у теці схеми (сама схема або журнал будь-якого року)")
    if found is None: return None
    scheme_folder, years_data = found

    all_indicators = sorted({nm for yd in years_data.values() for nm in yd.get("records", {})})
    if not all_indicators:
        messagebox.showwarning("", "Жоден рік не містить жодного показника.", parent=parent); return None
    chosen = pick_indicators_dialog(parent, {nm: {} for nm in all_indicators}, multi_select=False)
    if not chosen: return None
    indicator = chosen[0]

    years_present = sorted(y for y, yd in years_data.items() if indicator in yd.get("records", {}))
    per_year_rows = {}; factor_cols = None
    for y in years_present:
        yd = years_data[y]
        plants = _plants_from_saved(yd.get("plants", []))
        fc, rows = aggregate_journal_data(
            plants, yd.get("factor_defs", []), yd.get("variant_names", []),
            yd.get("records", {}), [indicator])
        factor_cols = fc
        per_year_rows[y] = rows

    combo_rep_map = {}
    for y in years_present:
        for r in per_year_rows[y]:
            key = (tuple(r[fc_] for fc_ in factor_cols), r["replication"])
            combo_rep_map.setdefault(key, {})[y] = r[indicator]

    out_rows = []
    for (combo, rep) in sorted(combo_rep_map.keys()):
        row = dict(zip(factor_cols, combo))
        row["replication"] = rep
        for y in years_present:
            row[y] = combo_rep_map[(combo, rep)].get(y)
        out_rows.append(row)

    return factor_cols, out_rows, years_present, indicator


def open_series_for_analysis(parent):
    """Для серії повторних вимірів через інтервал (записана в самій
    схемі — може тривати через роки) — один клік і всі раунди серії
    готові у форматі для «Змішаного RM»: Варіант | Повторність | дата1 |
    дата2 | ... Повертає (factor_cols, rows, dates, base_name) або
    None."""
    path = filedialog.askopenfilename(
        parent=parent, filetypes=[("SAD файл","*.sadp"),("JSON","*.json")],
        title="Оберіть будь-який файл у теці схеми (сама схема або журнал будь-якого року)")
    if not path: return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as ex:
        messagebox.showerror("Помилка відкриття", str(ex), parent=parent); return None

    ftype = d.get("type")
    if ftype == "field_journal":
        scheme_folder = os.path.dirname(os.path.dirname(path))
    elif ftype in ("homogeneous_plot_scheme", "multi_factor_scheme"):
        scheme_folder = os.path.dirname(path)
    else:
        messagebox.showwarning("Не той тип файлу",
            "Оберіть файл схеми або журналу конкретного року.", parent=parent); return None

    scheme_file = _find_scheme_file_in_folder(scheme_folder)
    series = {}
    base_scheme = None
    if scheme_file:
        try:
            with open(scheme_file, "r", encoding="utf-8") as f:
                sd = json.load(f)
            series = sd.get("series", {})
            base_scheme = sd
        except Exception:
            pass
    if not series:
        messagebox.showwarning("Немає серій",
            "У цій схемі ще немає жодної серії повторних вимірів.", parent=parent); return None

    base_names = sorted(series.keys())
    chosen = pick_indicators_dialog(parent, {nm: {} for nm in base_names}, multi_select=False)
    if not chosen: return None
    base_name = chosen[0]
    rounds = series[base_name]["rounds"]
    if not rounds:
        messagebox.showwarning("", "У цієї серії ще немає жодного заміру.", parent=parent); return None

    plants = _plants_from_saved(base_scheme.get("plants", []))
    factor_defs = base_scheme.get("factor_defs", [])
    variant_names = base_scheme.get("variant_names", [])

    per_round_rows = {}; factor_cols = None; dates = []
    indicator_by_date = {}
    for rnd in rounds:
        year = rnd.get("year")
        if year:
            jf = os.path.join(scheme_folder, year, f"журнал_{year}.sadp")
            if not os.path.exists(jf): continue
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    yd = json.load(f)
            except Exception:
                continue
            values = yd.get("records", {}).get(rnd["indicator"], {}).get("values", {})
        else:
            continue
        if not values: continue
        fc, rows = aggregate_journal_data(
            plants, factor_defs, variant_names,
            {rnd["indicator"]: {"unit":"", "values": values}}, [rnd["indicator"]])
        factor_cols = fc
        per_round_rows[rnd["date"]] = rows
        indicator_by_date[rnd["date"]] = rnd["indicator"]
        dates.append(rnd["date"])

    if not per_round_rows:
        messagebox.showwarning("", "Не вдалось зібрати дані жодного раунду.", parent=parent); return None

    combo_rep_map = {}
    for dt in dates:
        for r in per_round_rows[dt]:
            key = (tuple(r[fc_] for fc_ in factor_cols), r["replication"])
            combo_rep_map.setdefault(key, {})[dt] = r.get(indicator_by_date[dt])

    out_rows = []
    for (combo, rep) in sorted(combo_rep_map.keys()):
        row = dict(zip(factor_cols, combo))
        row["replication"] = rep
        for dt in dates:
            row[dt] = combo_rep_map[(combo, rep)].get(dt)
        out_rows.append(row)

    return factor_cols, out_rows, dates, base_name


class FieldJournalWindow:
    """
    Окремий модуль від «Планування досліду за однорідністю» (навмисно —
    для простоти й зрозумілості кожен інструмент робить одну річ).

    Завантажує ЗБЕРЕЖЕНУ СХЕМУ (файл .sadp, type="homogeneous_plot_scheme")
    або вже існуючий журнал (type="field_journal") і дозволяє:
      • вписувати виміряні значення показника прямо в клітинки схеми —
        на екрані комп'ютера, у тому самому фізичному розташуванні, що
        й у саду;
      • вести кілька РІЗНИХ показників («Урожайність 2024», «Діаметр
        штамбу 2023» тощо) по ОДНІЙ і тій самій фізичній схемі —
        кожен зберігається як окремий «облік» (record) у тому самому
        файлі журналу;
      • роздрукувати порожній бланк для внесення даних у польових
        умовах олівцем/ручкою.
    """

    HELP_TEXT = """
ПОЛЬОВИЙ ЖУРНАЛ ОБЛІКІВ — ІНСТРУКЦІЯ
═════════════════════════════════════

ДЛЯ ЧОГО ЦЕЙ МОДУЛЬ?
  Модуль «Планування досліду за однорідністю» створює схему — яка саме
  рослина до якого варіанту й повторення належить. Але сама схема не
  містить майбутніх результатів обліків (урожайність, вміст цукру
  тощо) — для цього і є цей журнал.

КРОК 1. ВІДКРИЙТЕ СХЕМУ АБО ЖУРНАЛ
  «📂 Відкрити» — оберіть файл .sadp:
    • якщо це щойно збережена СХЕМА — журнал створюється з нуля на її
      основі (ще без жодного обліку);
    • якщо це вже існуючий ЖУРНАЛ — відкриються всі попередні обліки,
      які в ньому вже збережені.

КРОК 2. СТВОРІТЬ ОБЛІК (ПОКАЗНИК)
  «➕ Новий облік» — вкажіть назву показника й одиницю виміру
  (наприклад, «Урожайність 2024», кг). Можна створити скільки завгодно
  обліків по одній і тій самій схемі — для різних років чи показників.
  Перемикайтесь між ними через випадаючий список зверху.

КРОК 3. ВНОСЬТЕ ЗНАЧЕННЯ
  Зелені клітинки — облікові рослини поточного варіанту/повторення,
  саме туди вписуються виміряні значення. Сірі/жовті/помаранчеві —
  захисні/виключені рослини (не редагуються, показані лише для
  орієнтації в саду). Дані зберігаються автоматично в пам'яті —
  не забудьте «💾 Зберегти журнал» наприкінці роботи.

ДРУК
  «🖨 Друкувати бланк» — та сама схема, але порожня, з місцем для
  запису значень від руки в полі (як в модулі планування).
"""

    def __init__(self, parent, gs=None):
        self._parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Польовий журнал обліків")
        self.win.geometry("1400x820"); set_icon(self.win)
        self.gs = dict(gs) if gs else {}
        self.plants = []           # список HPPlant з завантаженої схеми
        self.cfg = {}
        self.variant_names = []
        self.factor_defs = []      # [{"name":...,"levels":[...]}, ...] — для багатофакторних схем
        self.records = {}          # {"Урожайність": {"unit":..., "values": {"r:p": val}}} — за ПОТОЧНИЙ рік
        self._working_values = {}  # поточні (можливо ще незбережені) значення в таблиці
        self._current_indicator_name = None  # назва показника, що редагується зараз (якщо є)
        self._scheme_folder = None  # тека схеми - в ній підтеки років
        self._current_year = None   # поточний обраний рік (текст, напр. "2024")
        self._journal_path = None   # шлях до файлу журналу ПОТОЧНОГО року
        self._base_scheme_data = None  # {"plants":...,"factor_defs":...,"variant_names":...,"cfg":...}
        self._scheme_file_path = None  # шлях до файлу самої схеми (для дозапису нових випадів)
        self._newly_marked_dead = set()  # (row,pos), позначені "-" у ЦІЙ сесії - для виділення
        self._series = {}  # {базова_назва: {"interval_days":N, "rounds":[{"date":,"indicator":}]}}
                                        # — сама схема (без даних), для старту нового року
        self._entry_widgets = {}   # (row,position) -> tk.Entry (лише для облікових)
        self._build()

    # ─────────────────────────────────────────────────────
    def _build(self):
        rf = ("Times New Roman", 11)
        top = tk.Frame(self.win, padx=8, pady=6); top.pack(fill=tk.X)
        tk.Button(top, text="📂 Відкрити схему / журнал", bg="#1a4b8c", fg="white",
                  font=rf, command=self._open_file).pack(side=tk.LEFT, padx=4)

        tk.Label(top, text="Рік:", font=rf).pack(side=tk.LEFT, padx=(16,2))
        self._year_var = tk.StringVar(value="")
        self._year_cb = ttk.Combobox(top, textvariable=self._year_var,
                                     state="readonly", width=12, values=[])
        self._year_cb.pack(side=tk.LEFT, padx=2)
        self._year_cb.bind("<<ComboboxSelected>>",
                           lambda e: self._switch_year(self._year_var.get()))

        tk.Label(top, text="Показник:", font=rf).pack(side=tk.LEFT, padx=(16,2))
        self._record_var = tk.StringVar(value="")
        self._record_cb = ttk.Combobox(top, textvariable=self._record_var,
                                       state="readonly", width=28, values=[])
        self._record_cb.pack(side=tk.LEFT, padx=2)
        self._record_cb.bind("<<ComboboxSelected>>",
                             lambda e: self._switch_record(self._record_var.get()))

        tk.Button(top, text="💾 Зберегти показник", bg="#1a6b1a", fg="white",
                  font=rf, command=self._save_indicator).pack(side=tk.LEFT, padx=(16,4))
        tk.Button(top, text="🖨 Друкувати бланк", font=rf,
                  command=self._print_blank_form).pack(side=tk.LEFT, padx=(16,4))
        tk.Button(top, text="📊 Звести для аналізу", bg="#8c1a1a", fg="white", font=rf,
                  command=self._reduce_for_analysis).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="📈 Показник по роках", bg="#8c1a6b", fg="white", font=rf,
                  command=self._show_indicator_by_years).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="📉 Динаміка серії", bg="#8c1a6b", fg="white", font=rf,
                  command=self._show_series_dynamics).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="✏ Редагувати серію", font=rf,
                  command=self._edit_series).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="📚 Довідка", bg="#1a4b8c", fg="white", font=rf,
                  command=self._show_help).pack(side=tk.LEFT, padx=4)

        self._info_lbl = tk.Label(self.win,
                text="Немає завантаженої схеми. Натисніть «📂 Відкрити схему / журнал», "
                     "щоб почати.",
                font=("Times New Roman",11), fg="#888", anchor="w")
        self._info_lbl.pack(fill=tk.X, padx=8, pady=(0,4))

        # ── Легенда (та сама, що й у схемі) ───────────────
        self._legend_f = tk.Frame(self.win, bg="#f7f7f7", padx=8, pady=6)
        self._legend_f.pack(fill=tk.X)

        # ── Прокручувана область сітки ─────────────────────
        tbl_area = tk.Frame(self.win); tbl_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2,4))
        self._canvas = tk.Canvas(tbl_area)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_v = ttk.Scrollbar(tbl_area, orient="vertical", command=self._canvas.yview)
        sb_v.pack(side=tk.RIGHT, fill=tk.Y)
        sb_h = ttk.Scrollbar(self.win, orient="horizontal", command=self._canvas.xview)
        sb_h.pack(fill=tk.X, padx=8)
        self._canvas.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self.inner = tk.Frame(self._canvas)
        self._canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self._canvas.config(scrollregion=self._canvas.bbox("all")))
        self.win.bind("<MouseWheel>",
                      lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)),"units"))

    def _show_help(self):
        win = tk.Toplevel(self.win); win.title("Довідка — Польовий журнал")
        win.geometry("700x600"); set_icon(win)
        txt = tk.Text(win, wrap="word", font=("Times New Roman",11), padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert("1.0", self.HELP_TEXT.strip()); txt.configure(state="disabled")
        tk.Button(win, text="Закрити", command=win.destroy,
                  font=("Times New Roman",11)).pack(pady=6)

    # ── Відкриття схеми/журналу ───────────────────────────
    def _open_file(self):
        path = filedialog.askopenfilename(
            parent=self.win, filetypes=[("SAD файл","*.sadp"),("JSON","*.json")],
            title="Відкрити схему або журнал (будь-який файл у теці схеми чи року)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as ex:
            messagebox.showerror("Помилка відкриття", str(ex)); return

        ftype = d.get("type")
        if ftype not in ("homogeneous_plot_scheme", "multi_factor_scheme", "field_journal"):
            messagebox.showwarning("Не той тип файлу",
                "Цей файл не є ані схемою досліду, ані журналом обліків.\n"
                "Оберіть файл, збережений через «💾 Зберегти схема» в модулі "
                "планування чи конструкторі схеми, або раніше збережений журнал."); return

        self._base_scheme_data = {
            "plants": d.get("plants", []), "cfg": d.get("cfg", {}),
            "variant_names": d.get("variant_names", []),
            "factor_defs": d.get("factor_defs", []),
        }

        if ftype == "field_journal":
            # Це журнал ОДНОГО РОКУ — тека року/файл, тека схеми на рівень вище.
            year_folder = os.path.dirname(path)
            self._scheme_folder = os.path.dirname(year_folder)
            self._scheme_file_path = self._find_scheme_file(self._scheme_folder)
            self._load_year(os.path.basename(year_folder), _preloaded=d, _path=path)
        else:
            # Свіжа схема без жодних даних — лежить прямо в теці схеми.
            self._scheme_folder = os.path.dirname(path)
            self._scheme_file_path = path
            self._current_year = None
            self._refresh_year_list()
            self._year_var.set("")
            self.plants = []; self.records = {}
            self._info_lbl.configure(
                text=f"Схема відкрита: {os.path.basename(path)}   |   "
                     f"Оберіть або створіть рік досліджень, щоб почати вносити дані.",
                fg="#8c5a1a")
            self._build_legend()
            self._prompt_new_year()

    def _find_scheme_file(self, folder):
        """Шукає файл самої схеми (без записів) у корені теки — потрібен,
        щоб дозаписувати нові випадкові випади для майбутніх років, коли
        користувач відкрив одразу файл журналу конкретного року, а не
        файл схеми."""
        return _find_scheme_file_in_folder(folder)

    def _refresh_year_list(self):
        years = []
        if self._scheme_folder and os.path.isdir(self._scheme_folder):
            for name in sorted(os.listdir(self._scheme_folder)):
                if os.path.isdir(os.path.join(self._scheme_folder, name)) and name.isdigit():
                    years.append(name)
        self._year_cb.configure(values=years + ["(новий рік)"])

    def _switch_year(self, year_str):
        if year_str == "(новий рік)":
            self._prompt_new_year(); return
        if year_str == self._current_year: return
        if self._working_values and self._current_indicator_name is None:
            if not messagebox.askyesno("Незбережені зміни",
                    "У поточній таблиці є незбережені дані — перемикання року їх "
                    "втратить. Продовжити без збереження?"):
                self._year_var.set(self._current_year or "")
                return
        self._load_year(year_str)

    def _prompt_new_year(self):
        import datetime
        dlg = tk.Toplevel(self.win); dlg.title("Рік досліджень")
        dlg.resizable(False, False); set_icon(dlg); dlg.grab_set()
        frm = tk.Frame(dlg, padx=16, pady=14); frm.pack()
        tk.Label(frm, text="Рік досліджень (напр. 2024):", font=("Times New Roman",11)
                 ).grid(row=0, column=0, sticky="w")
        year_v = tk.StringVar(value=str(datetime.date.today().year))
        tk.Entry(frm, textvariable=year_v, width=10, font=("Times New Roman",11)
                 ).grid(row=0, column=1, padx=8)
        tk.Label(frm, text="Багаторічний дослід — кожен рік зберігається окремо, "
                          "в своїй підтеці всередині теки схеми.",
                 font=("Times New Roman",9), fg="#666", justify="left", wraplength=340
                 ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8,0))

        def _ok():
            y = year_v.get().strip()
            if not (y.isdigit() and len(y) == 4):
                messagebox.showwarning("", "Вкажіть рік у форматі, напр. 2024.", parent=dlg); return
            dlg.destroy()
            self._load_year(y)
        bf = tk.Frame(frm); bf.grid(row=2, column=0, columnspan=2, pady=(12,0))
        tk.Button(bf, text="Обрати", bg="#1a6b1a", fg="white", font=("Times New Roman",11),
                  command=_ok).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Скасувати", font=("Times New Roman",11),
                  command=dlg.destroy).pack(side=tk.LEFT)
        center_win(dlg)

    def _load_year(self, year_str, _preloaded=None, _path=None):
        """Завантажує рік year_str у поточній теці схеми. Якщо для цього
        року вже є збережений журнал — підвантажує його показники; якщо
        немає — стартує з чистою схемою (без жодного показника), готовою
        для першого внесення даних."""
        self._newly_marked_dead.clear()
        year_folder = os.path.join(self._scheme_folder, year_str)
        journal_path = _path or os.path.join(year_folder, f"журнал_{year_str}.sadp")

        if _preloaded is not None:
            d = _preloaded
        elif os.path.exists(journal_path):
            with open(journal_path, "r", encoding="utf-8") as f:
                d = json.load(f)
        else:
            d = None  # новий, ще не збережений рік

        b = self._base_scheme_data
        src = d if d is not None else b
        plants = []
        for pd in src.get("plants", []):
            p = HPPlant(pd["row"], pd["position"],
                       pd.get("value") if d is not None else None,
                       pd.get("status","ok"))
            p.role = pd.get("role", HP_ROLE_UNASSIGNED)
            p.plot_id = pd.get("plot_id"); p.variant = pd.get("variant")
            p.replication = pd.get("replication"); p.factors = pd.get("factors", {})
            plants.append(p)
        self.plants = plants
        self.cfg = src.get("cfg", {})
        self.variant_names = src.get("variant_names", [])
        self.factor_defs = src.get("factor_defs", [])
        self.records = d.get("records", {}) if d is not None else {}
        # Серії читаємо З ФАЙЛУ СХЕМИ (переживають перехід на новий рік) —
        # із резервним варіантом зі збереженого року лише для сумісності
        # зі старими файлами, збереженими до цієї можливості.
        scheme_series = None
        if self._scheme_file_path and os.path.exists(self._scheme_file_path):
            try:
                with open(self._scheme_file_path, "r", encoding="utf-8") as f:
                    scheme_series = json.load(f).get("series")
            except Exception:
                scheme_series = None
        if scheme_series:
            self._series = scheme_series
        else:
            self._series = d.get("series", {}) if d is not None else {}
        self._journal_path = journal_path if d is not None else None

        self._current_year = year_str
        self._refresh_year_list()
        self._year_var.set(year_str)
        self._working_values = {}
        self._current_indicator_name = None
        names = list(self.records.keys())
        self._record_cb.configure(values=["(новий показник)"] + names)
        self._record_var.set("(новий показник)")

        n_rec = len(self.records)
        self._info_lbl.configure(
            text=f"Схема: {os.path.basename(self._scheme_folder)}   |   "
                 f"Рік: {year_str}   |   "
                 f"Облікових рослин: {sum(1 for p in self.plants if p.role == HP_ROLE_RECORDED)}   |   "
                 f"Показників за {year_str} рік: {n_rec}",
            fg="#1a6b1a")
        self._build_legend()
        self._build_grid()
        self._check_series_due()

    def _today_str(self):
        return __import__("datetime").date.today().isoformat()

    def _check_series_due(self):
        """Перевіряє, чи не настав час чергового заміру для якоїсь серії
        повторних вимірів (інтервал від останнього заміру вичерпано), і
        нагадує про це — не блокуючи роботу."""
        if not self._series: return
        today = __import__("datetime").date.fromisoformat(self._today_str())
        due = []
        for base_name, info in self._series.items():
            rounds = info.get("rounds", [])
            if not rounds: continue
            last_date_str = rounds[-1]["date"]
            try:
                last_date = __import__("datetime").date.fromisoformat(last_date_str)
            except ValueError:
                continue
            days_since = (today - last_date).days
            interval = info.get("interval_days", 0)
            if days_since >= interval:
                overdue = days_since - interval
                due.append((base_name, last_date_str, interval, days_since, overdue))
        if not due: return
        lines = []
        for base_name, last_date, interval, days_since, overdue in due:
            if overdue > 0:
                lines.append(f"  • «{base_name}»: минуло {days_since} дн. від останнього "
                            f"заміру ({last_date}), інтервал {interval} дн. — "
                            f"прострочено на {overdue} дн.")
            else:
                lines.append(f"  • «{base_name}»: минуло {days_since} дн. від останнього "
                            f"заміру ({last_date}), інтервал {interval} дн. — час проводити.")
        messagebox.showinfo("⏰ Час чергового обліку",
            "За цими серіями повторних вимірів настав час наступного заміру:\n\n"
            + "\n".join(lines))

    # ── Керування показниками ──────────────────────────────
    def _switch_record(self, name):
        if self._working_values and (
                self._current_indicator_name is None or
                self._working_values != self.records.get(self._current_indicator_name, {}).get("values", {})):
            if not messagebox.askyesno("Незбережені зміни",
                    "У поточній таблиці є незбережені дані — перемикання на інший "
                    "показник їх втратить (якщо не зберегти зараз). Продовжити без "
                    "збереження?"):
                # повернути вибір комбобоксу на попередній показник
                self._record_var.set(self._current_indicator_name or "(новий показник)")
                return
        if name == "(новий показник)":
            self._working_values = {}
            self._current_indicator_name = None
        elif name in self.records:
            self._working_values = dict(self.records[name]["values"])
            self._current_indicator_name = name
        self._build_grid()

    # ── Легенда (компактна, та сама палітра що й у схемі) ─
    def _build_legend(self):
        for w in self._legend_f.winfo_children(): w.destroy()
        row1 = tk.Frame(self._legend_f, bg="#f7f7f7"); row1.pack(fill=tk.X)
        for role, color in HP_ROLE_COLORS.items():
            sw = tk.Frame(row1, bg=color, width=14, height=14, relief=tk.RIDGE, bd=1)
            sw.pack(side=tk.LEFT, padx=(0,4), pady=2); sw.pack_propagate(False)
            tk.Label(row1, text=HP_ROLE_LABELS[role], bg="#f7f7f7",
                     font=("Times New Roman",9)).pack(side=tk.LEFT, padx=(0,12))
        if self.variant_names:
            names_txt = "   •   ".join(f"В{i+1}={nm}" for i, nm in enumerate(self.variant_names))
            tk.Label(self._legend_f, text="Варіанти: " + names_txt,
                     bg="#f7f7f7", fg="#1a4b8c", font=("Times New Roman",9,"bold"),
                     anchor="w").pack(fill=tk.X, pady=(2,0))
        tk.Label(self._legend_f,
                 text="Якщо облікова рослина випадково загинула (не через варіант "
                      "досліду — трактор, гризуни тощо) — впишіть «-» замість числа: "
                      "вона одразу виключається з розрахунків і назавжди запам'ятається "
                      "в схемі для всіх майбутніх років.",
                 bg="#f7f7f7", fg="#666", font=("Times New Roman",9), justify="left",
                 anchor="w", wraplength=900).pack(fill=tk.X, pady=(2,0))

    # ── Основна сітка внесення даних — завжди доступна для вводу ──
    def _build_grid(self):
        for w in self.inner.winfo_children(): w.destroy()
        self._entry_widgets = {}
        if not self.plants: return

        by_row = {}
        for p in self.plants:
            by_row.setdefault(p.row, {})[p.position] = p
        rows = sorted(by_row.keys())
        max_pos = max((p.position for p in self.plants), default=1)

        tk.Label(self.inner, text="Ряд \\ Поз.", width=9, relief=tk.RIDGE,
                 bg="#444444", fg="white", font=("Times New Roman",10,"bold")
                 ).grid(row=0, column=0, padx=1, pady=1, sticky="nsew")
        for j in range(1, max_pos+1):
            tk.Label(self.inner, text=str(j), width=6, relief=tk.RIDGE,
                     bg="#1a4b8c", fg="white", font=("Times New Roman",9,"bold")
                     ).grid(row=0, column=j, padx=1, pady=1, sticky="nsew")

        for ri, row_num in enumerate(rows):
            grid_row = 1 + ri
            tk.Label(self.inner, text=f"Ряд {row_num}", width=9, relief=tk.RIDGE,
                     bg="#444444", fg="white", font=("Times New Roman",9,"bold")
                     ).grid(row=grid_row, column=0, padx=1, pady=1, sticky="nsew")
            for pos in range(1, max_pos+1):
                p = by_row.get(row_num, {}).get(pos)
                if p is None:
                    continue
                if p.role == HP_ROLE_RECORDED:
                    key = f"{row_num}:{pos}"
                    e = tk.Entry(self.inner, width=6, font=("Times New Roman",9),
                                bg="#e8f5e9", justify="center")
                    e.grid(row=grid_row, column=pos, padx=1, pady=1)
                    if key in self._working_values: e.insert(0, str(self._working_values[key]))
                    e.bind("<FocusOut>", lambda ev, r=row_num, po=pos: self._on_cell_edit(r, po))
                    self._entry_widgets[(row_num,pos)] = e
                else:
                    label = {HP_ROLE_GUARD_EDGE:"К", HP_ROLE_GUARD_REP:"П",
                             HP_ROLE_DEAD:"-", HP_ROLE_POLLINIZER:"+",
                             HP_ROLE_EXTRA:"×", HP_ROLE_EXCLUDED_CV:"✕"}.get(p.role, "")
                    color = HP_ROLE_COLORS.get(p.role, "#eeeeee")
                    is_new_dead = p.role == HP_ROLE_DEAD and (row_num,pos) in self._newly_marked_dead
                    if is_new_dead:
                        label = "- новий"; color = "#ff8a80"  # яскравіше - щойно позначений цього разу
                    tk.Label(self.inner, text=label, width=6, relief=tk.RIDGE,
                             bg=color, font=("Times New Roman",9)
                             ).grid(row=grid_row, column=pos, padx=1, pady=1)
        _bind_nav(self._grid_as_2d(rows, max_pos, by_row), self.win)

    def _grid_as_2d(self, rows, max_pos, by_row):
        """Формує 2D-масив лише з редагованих (облікових) клітинок —
        для навігації Enter/стрілками (пропускаючи нередаговані)."""
        out = []
        for row_num in rows:
            line = []
            for pos in range(1, max_pos+1):
                p = by_row.get(row_num, {}).get(pos)
                if p is not None and p.role == HP_ROLE_RECORDED:
                    e = self._entry_widgets.get((row_num,pos))
                    if e is not None: line.append(e)
            if line: out.append(line)
        return out

    def _on_cell_edit(self, row, pos):
        e = self._entry_widgets.get((row,pos))
        if e is None: return
        key = f"{row}:{pos}"
        txt = e.get().strip()
        if txt == "-":
            # Випадковий випад (не наслідок варіанту досліду) - трактор,
            # заєць тощо. Переводимо рослину в статус "dead": вона одразу
            # й назавжди виключається з розрахунку середнього по цій
            # повторності (і для цього, і для всіх наступних показників),
            # а не просто отримує текстове значення "-" як вимір.
            self._reclassify_as_dead(row, pos)
            if key in self._working_values: del self._working_values[key]
            self._build_grid()
            return
        if txt:
            if self._looks_like_typo(key, txt, e):
                return  # користувач або виправив, або скасував - значення не зберігаємо
            self._working_values[key] = txt
        elif key in self._working_values: del self._working_values[key]

    def _looks_like_typo(self, key, txt, entry_widget):
        """Перевіряє, чи введене число не є явним викидом порівняно з уже
        внесеними значеннями ТОГО Ж показника (можлива описка — зайвий
        нуль, зсунута кома тощо). Повертає True, якщо користувач
        відмовився підтвердити значення (поле очищено, зберігати не
        треба) — False, якщо можна зберігати як є."""
        try:
            value = float(txt.replace(",", "."))
        except ValueError:
            return False  # не число - інші перевірки (чи взагалі коректне) не тут

        # Порівнюємо ЛИШЕ в межах того самого варіанту/комбінації факторів
        # — інакше легітимно вищі (чи нижчі) значення сильного варіанту
        # виглядали б як "викиди" відносно змішаного пулу всіх варіантів,
        # і саме там, де ефект обробки найсильніший, застереження
        # спрацьовувало б найчастіше - це зворотне тому, що потрібно.
        row_num, pos_num = (int(x) for x in key.split(":"))
        this_plant = next((p for p in self.plants
                           if p.row == row_num and p.position == pos_num), None)
        this_ident = (this_plant.variant, tuple(sorted(this_plant.factors.items()))
                     ) if this_plant else None

        others = []
        for k, v in self._working_values.items():
            if k == key: continue
            r2, p2 = (int(x) for x in k.split(":"))
            other_plant = next((p for p in self.plants
                                if p.row == r2 and p.position == p2), None)
            if other_plant is None: continue
            other_ident = (other_plant.variant, tuple(sorted(other_plant.factors.items())))
            if this_ident is not None and other_ident != this_ident: continue
            try: others.append(float(str(v).replace(",", ".")))
            except ValueError: continue
        if len(others) < 4:
            return False  # замало даних (у межах цього варіанту) для надійної статистики

        others_sorted = sorted(others)
        n = len(others_sorted)
        median = others_sorted[n//2] if n % 2 else (others_sorted[n//2-1]+others_sorted[n//2])/2
        abs_devs = sorted(abs(x-median) for x in others_sorted)
        mad = abs_devs[n//2] if n % 2 else (abs_devs[n//2-1]+abs_devs[n//2])/2

        is_outlier = False
        if mad > 1e-9:
            modified_z = 0.6745 * (value - median) / mad
            if abs(modified_z) > 3.5: is_outlier = True
        elif median != 0 and abs(value - median) / abs(median) > 0.5:
            is_outlier = True  # усі інші значення майже однакові, це - ні

        if not is_outlier: return False

        proceed = messagebox.askyesno("Можлива описка",
            f"Введене значення {txt} суттєво відрізняється від решти вже внесених "
            f"ДЛЯ ЦЬОГО Ж ВАРІАНТУ ({len(others)} шт., медіана ≈ {median:.3g}).\n\n"
            f"Це не описка (зайвий нуль, зсунута кома тощо)?\n\n"
            f"«Так» — залишити значення як є.\n«Ні» — очистити клітинку й ввести заново.")
        if proceed:
            return False
        entry_widget.delete(0, tk.END)
        entry_widget.focus_set()
        return True

    def _reclassify_as_dead(self, row, pos):
        """Позначає облікову рослину (row,pos) як випадково загиблу.
        Оновлює self.plants (діюча сесія), self._base_scheme_data
        (щоб наступні НОВІ роки одразу успадкували цей випад) і додає
        позначку "новий цього разу" для виділення в таблиці."""
        for p in self.plants:
            if p.row == row and p.position == pos:
                p.role = HP_ROLE_DEAD
                p.status = "dead"
                break
        if self._base_scheme_data:
            for pd in self._base_scheme_data.get("plants", []):
                if pd.get("row") == row and pd.get("position") == pos:
                    pd["role"] = HP_ROLE_DEAD
                    pd["status"] = "dead"
                    break
        self._newly_marked_dead.add((row, pos))

    def _get_round_values(self, round_info):
        """Повертає values-словник для одного раунду серії — з поточного
        self.records, якщо раунд з цього самого року, або з файлу
        журналу ВІДПОВІДНОГО року, якщо раунд був раніше (серія триває
        через роки)."""
        round_year = round_info.get("year")
        if round_year is None or round_year == self._current_year:
            return self.records.get(round_info["indicator"], {}).get("values", {})
        year_folder = os.path.join(self._scheme_folder, round_year)
        journal_path = os.path.join(year_folder, f"журнал_{round_year}.sadp")
        if not os.path.exists(journal_path):
            return {}
        try:
            with open(journal_path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return {}
        return d.get("records", {}).get(round_info["indicator"], {}).get("values", {})

    def _sync_series_to_scheme_file(self):
        """Дописує реєстр серій повторних вимірів у файл САМОЇ СХЕМИ —
        на відміну від self.records (дані конкретного року), серія має
        переживати перехід на новий рік: багаторічне стеження за ростом
        (штамб, пагін) саме для цього й потрібне."""
        if not self._scheme_file_path or not os.path.exists(self._scheme_file_path):
            return
        try:
            with open(self._scheme_file_path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return
        d["series"] = self._series
        try:
            with open(self._scheme_file_path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _sync_dead_to_scheme_file(self):
        """Дописує оновлені статуси (нові випадкові випади) у файл самої
        схеми — щоб наступні НОВІ роки, які стартують саме з нього, вже
        не показували цю рослину як облікову."""
        if not self._scheme_file_path or not os.path.exists(self._scheme_file_path):
            return
        try:
            with open(self._scheme_file_path, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            return
        by_pos = {(p.row, p.position): p for p in self.plants}
        changed = False
        for pd in d.get("plants", []):
            key = (pd.get("row"), pd.get("position"))
            p = by_pos.get(key)
            if p is not None and p.role == HP_ROLE_DEAD and pd.get("role") != HP_ROLE_DEAD:
                pd["role"] = HP_ROLE_DEAD
                pd["status"] = "dead"
                changed = True
        if changed:
            try:
                with open(self._scheme_file_path, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def _sync_grid_to_working_values(self):
        found_new_dead = False
        for (r,p), e in self._entry_widgets.items():
            txt = e.get().strip()
            key = f"{r}:{p}"
            if txt == "-":
                self._reclassify_as_dead(r, p)
                if key in self._working_values: del self._working_values[key]
                found_new_dead = True
                continue
            if txt: self._working_values[key] = txt
            elif key in self._working_values: del self._working_values[key]
        if found_new_dead:
            self._build_grid()

    # ── Зберегти показник (назва + дані + файл на диск за один крок) ──
    def _save_indicator(self):
        if not self.plants:
            messagebox.showwarning("", "Спочатку відкрийте схему."); return
        if not self._current_year:
            messagebox.showwarning("", "Спочатку оберіть або створіть рік досліджень "
                                       "(поле «Рік» угорі)."); return
        self._sync_grid_to_working_values()
        if not self._working_values:
            messagebox.showwarning("", "Таблиця порожня — немає що зберігати."); return

        dlg = tk.Toplevel(self.win); dlg.title("Зберегти показник")
        dlg.resizable(False, False); set_icon(dlg); dlg.grab_set()
        frm = tk.Frame(dlg, padx=16, pady=14); frm.pack()
        tk.Label(frm, text=f"Рік досліджень: {self._current_year}",
                 font=("Times New Roman",10,"bold"), fg="#1a4b8c"
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,8))
        tk.Label(frm, text="Назва показника (напр. «Урожайність»):",
                 font=("Times New Roman",11)).grid(row=1, column=0, sticky="w", pady=4)
        name_v = tk.StringVar(value=self._current_indicator_name or "")
        tk.Entry(frm, textvariable=name_v, width=30, font=("Times New Roman",11)
                 ).grid(row=1, column=1, sticky="w", padx=8)
        tk.Label(frm, text="Одиниця виміру:", font=("Times New Roman",11)
                 ).grid(row=2, column=0, sticky="w", pady=4)
        existing_unit = (self.records.get(self._current_indicator_name, {}).get("unit","")
                         if self._current_indicator_name else "")
        unit_v = tk.StringVar(value=existing_unit)
        tk.Entry(frm, textvariable=unit_v, width=15, font=("Times New Roman",11)
                 ).grid(row=2, column=1, sticky="w", padx=8)

        tk.Frame(frm, height=1, bg="#ccc").grid(row=3, column=0, columnspan=2,
                                                sticky="ew", pady=(10,8))
        series_v = tk.BooleanVar(value=False)
        series_extra = tk.Frame(frm)
        tk.Checkbutton(frm, text="📅 Це частина серії повторних вимірів через інтервал",
                      variable=series_v, font=("Times New Roman",11),
                      command=lambda: _build_series_extra()
                      ).grid(row=4, column=0, columnspan=2, sticky="w")

        def _build_series_extra():
            for w in series_extra.winfo_children(): w.destroy()
            if not series_v.get(): return
            tk.Label(series_extra, text="Базова назва серії:", font=("Times New Roman",11)
                     ).grid(row=0, column=0, sticky="w", pady=3)
            base_v = tk.StringVar(value=list(self._series.keys())[0] if self._series else "")
            base_cb = ttk.Combobox(series_extra, textvariable=base_v, width=22,
                                   values=list(self._series.keys()))
            base_cb.grid(row=0, column=1, sticky="w", padx=8, pady=3)
            tk.Label(series_extra, text="Інтервал між вимірами, днів:", font=("Times New Roman",11)
                     ).grid(row=1, column=0, sticky="w", pady=3)
            interval_v = tk.StringVar(value="14")

            def _on_base_change(*_):
                bn = base_v.get().strip()
                if bn in self._series:
                    interval_v.set(str(self._series[bn]["interval_days"]))
                    interval_entry.configure(state="disabled")
                else:
                    interval_entry.configure(state="normal")
            interval_entry = tk.Entry(series_extra, textvariable=interval_v, width=6,
                                      font=("Times New Roman",11))
            interval_entry.grid(row=1, column=1, sticky="w", padx=8, pady=3)
            base_v.trace_add("write", _on_base_change)
            _on_base_change()
            tk.Label(series_extra, text="Дата заміру (РРРР-ММ-ДД):", font=("Times New Roman",11)
                     ).grid(row=2, column=0, sticky="w", pady=3)
            date_v = tk.StringVar(value=self._today_str())
            tk.Entry(series_extra, textvariable=date_v, width=12, font=("Times New Roman",11)
                     ).grid(row=2, column=1, sticky="w", padx=8, pady=3)
            tk.Label(series_extra,
                     text="Дата самого виміру (не обов'язково сьогодні) — від неї рахується "
                          "наступний облік. Назва показника буде автоматично доповнена цією "
                          "датою: «{базова назва} (дата)».",
                     font=("Times New Roman",9), fg="#666", wraplength=380, justify="left"
                     ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4,0))
            series_extra._base_v = base_v; series_extra._interval_v = interval_v
            series_extra._date_v = date_v
        series_extra.grid(row=5, column=0, columnspan=2, sticky="w")

        def _do_save():
            is_series = series_v.get()
            if is_series:
                base_name = series_extra._base_v.get().strip()
                if not base_name:
                    messagebox.showwarning("", "Вкажіть базову назву серії.", parent=dlg); return
                try:
                    interval_days = int(series_extra._interval_v.get())
                except ValueError:
                    messagebox.showwarning("", "Перевірте інтервал (ціле число днів).", parent=dlg); return
                if interval_days <= 0:
                    messagebox.showwarning("", "Інтервал має бути додатним.", parent=dlg); return
                dt_mod = __import__("datetime")
                try:
                    measure_date = dt_mod.date.fromisoformat(series_extra._date_v.get().strip())
                except ValueError:
                    messagebox.showwarning("", "Дату заміру вкажіть у форматі РРРР-ММ-ДД "
                                               "(наприклад 2024-05-15).", parent=dlg); return
                if measure_date > dt_mod.date.fromisoformat(self._today_str()):
                    messagebox.showwarning("", "Дата заміру не може бути в майбутньому — "
                                               "швидше за все, описка.", parent=dlg); return
                today_str = measure_date.isoformat()
                nm = f"{base_name} ({today_str})"
                # Дата — це ідентифікатор моменту часу в межах серії. Збіг
                # з замірoм ТОГО Ж року — це виправлення (нижче запитаємо про
                # перезапис). Збіг із замірoм ІНШОГО року — неоднозначність:
                # той самий момент опинився б у двох журналах, а в аналізі
                # повторних вимірів з'явились би дубльовані стовпці.
                clash = next((r for r in self._series.get(base_name, {}).get("rounds", [])
                              if r["date"] == today_str
                              and r.get("year") not in (None, self._current_year)), None)
                if clash:
                    messagebox.showwarning("Дата вже є в серії",
                        f"У серії «{base_name}» уже є замір за {today_str}, збережений у "
                        f"журналі {clash['year']} року.\n\nОдин момент часу не може бути "
                        f"у двох журналах. Вкажіть іншу дату, або відкрийте {clash['year']} "
                        f"рік, щоб виправити той замір.", parent=dlg)
                    return
            else:
                nm = name_v.get().strip()
                if not nm:
                    messagebox.showwarning("", "Вкажіть назву показника.", parent=dlg); return

            if nm in self.records and nm != self._current_indicator_name:
                if not messagebox.askyesno("Показник уже існує",
                        f"Показник «{nm}» вже є в журналі за {self._current_year} рік. "
                        f"Перезаписати його поточними даними з таблиці?", parent=dlg):
                    return

            # Перевірка на зменшення відносно ІСТОРІЇ серії (не лише
            # останнього заміру) — для показників росту (висота, діаметр)
            # нове значення не повинне опускатись нижче за НАЙВИЩЕ з усіх
            # попередніх замірів цієї ж позиції. Порівняння з усією
            # історією, а не лише останнім раундом, важливе тому, що
            # дрібне коливання нижче за передостанній замір, але вище за
            # давніші, — природний шум вимірювання, а не помилка; звіряння
            # лише з останнім раундом плутало б одне з іншим. Невеликий
            # допуск (3%) додатково відсіює цей шум.
            if is_series and base_name in self._series and self._series[base_name]["rounds"]:
                # Раунд з тією самою назвою (= повторне збереження заміру
                # цієї ж дати, зазвичай виправлення описки) з історії
                # ВИКЛЮЧАЄМО — інакше нове значення порівнювалось би зі
                # старими значеннями того самого заміру, який воно замінює.
                # Історію ділимо за датою: попередні заміри задають НИЖНЮ
                # межу (ріст не зменшується), пізніші (якщо замір вносять
                # заднім числом) — ВЕРХНЮ.
                prior_max, later_min = {}, {}
                for rnd in self._series[base_name]["rounds"]:
                    if rnd["indicator"] == nm and rnd.get("year") in (None, self._current_year):
                        continue
                    is_later = rnd["date"] > today_str
                    for k, v in self._get_round_values(rnd).items():
                        try: fv = float(str(v).replace(",", "."))
                        except ValueError: continue
                        if is_later:
                            if k not in later_min or fv < later_min[k]: later_min[k] = fv
                        else:
                            if k not in prior_max or fv > prior_max[k]: prior_max[k] = fv

                problems = []
                for k, v in self._working_values.items():
                    try: new_v = float(str(v).replace(",", "."))
                    except ValueError: continue
                    if k in prior_max:
                        old_v = prior_max[k]
                        if new_v < old_v - max(0.03 * abs(old_v), 1e-9):
                            problems.append(f"  {k}: раніше було до {old_v:.3g} → тепер {new_v:.3g}")
                    if k in later_min:
                        nxt = later_min[k]
                        if new_v > nxt + max(0.03 * abs(nxt), 1e-9):
                            problems.append(f"  {k}: у пізнішому замірі лише {nxt:.3g}, а тут {new_v:.3g}")

                if problems:
                    preview = "\n".join(problems[:8])
                    more = f"\n  …і ще {len(problems)-8}" if len(problems) > 8 else ""
                    if not messagebox.askyesno("Незвична динаміка відносно інших замірів",
                            f"У {len(problems)} позиціях значення суперечить динаміці "
                            f"серії (показник росту не мав би зменшуватись; ~3% допуск на "
                            f"шум вимірювання вже враховано):\n\n{preview}{more}\n\n"
                            "Зазвичай це означає помилку вводу. Зберегти попри це?",
                            parent=dlg):
                        return

            self.records[nm] = {"unit": unit_v.get().strip(), "values": dict(self._working_values)}
            if is_series:
                self._series.setdefault(base_name, {"interval_days": interval_days, "rounds": []})
                self._series[base_name]["interval_days"] = interval_days
                # Повторне збереження заміру тієї ж дати (той самий показник)
                # ЗАМІНЮЄ запис, а не дублює його: дублікат дати в серії дав
                # б в аналізі повторних вимірів фіктивну "другу" часову
                # точку з тими самими даними.
                rounds_ = [r for r in self._series[base_name]["rounds"]
                           if not (r["indicator"] == nm
                                   and r.get("year") in (None, self._current_year))]
                rounds_.append({"date": today_str, "indicator": nm, "year": self._current_year})
                rounds_.sort(key=lambda r: r["date"])
                self._series[base_name]["rounds"] = rounds_
                self._sync_series_to_scheme_file()
            self._current_indicator_name = nm
            self._record_cb.configure(values=["(новий показник)"] + list(self.records.keys()))
            self._record_var.set(nm)
            dlg.destroy()
            saved_ok = self._write_journal_to_disk(nm)
            if saved_ok:
                # Готово до внесення НАСТУПНОГО показника одразу, без
                # повторного відкриття файлу — таблиця очищується, а
                # щойно збережений показник лишається доступним у
                # списку для перегляду/редагування пізніше.
                self._working_values = {}
                self._current_indicator_name = None
                self._record_var.set("(новий показник)")
                self._build_grid()

        bf = tk.Frame(frm); bf.grid(row=6, column=0, columnspan=2, pady=(12,0))
        tk.Button(bf, text="Зберегти", bg="#1a6b1a", fg="white",
                  font=("Times New Roman",11), command=_do_save).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Скасувати", font=("Times New Roman",11),
                  command=dlg.destroy).pack(side=tk.LEFT)
        center_win(dlg)

    def _write_journal_to_disk(self, indicator_name=""):
        plants_data = []
        for p in self.plants:
            plants_data.append({
                "row": p.row, "position": p.position, "value": p.value,
                "status": p.status, "role": p.role, "plot_id": p.plot_id,
                "variant": p.variant, "replication": p.replication,
                "factors": p.factors,
            })
        d = {
            "type": "field_journal", "version": APP_VER, "year": self._current_year,
            "cfg": self.cfg, "variant_names": self.variant_names,
            "factor_defs": self.factor_defs,
            "plants": plants_data, "records": self.records,
            "series": self._series,
        }
        # Шлях повністю визначається текою схеми й обраним роком — без
        # діалогу вибору файлу. Перший показник за рік створює підтеку.
        year_folder = os.path.join(self._scheme_folder, self._current_year)
        os.makedirs(year_folder, exist_ok=True)
        path = os.path.join(year_folder, f"журнал_{self._current_year}.sadp")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            self._journal_path = path
            self._sync_dead_to_scheme_file()
            self._newly_marked_dead.clear()
            messagebox.showinfo("Збережено", f"Показник «{indicator_name}» "
                                f"збережено в журналі:\n{path}")
            return True
        except Exception as ex:
            messagebox.showerror("Помилка збереження", str(ex))
            return False

    # ── Друк порожнього бланку ──────────────────────────────
    def _print_blank_form(self):
        if not self.plants:
            messagebox.showwarning("", "Спочатку відкрийте схему або журнал."); return
        if not HAS_MPL:
            messagebox.showwarning("", "Для друку потрібен matplotlib."); return

        by_row = {}
        for p in self.plants:
            by_row.setdefault(p.row, {})[p.position] = p
        rows = sorted(by_row.keys())

        POS_PER_PAGE = 14; ROWS_PER_PAGE = 4
        segments = []
        for row_num in rows:
            positions = sorted(by_row[row_num].keys())
            for i in range(0, len(positions), POS_PER_PAGE):
                segments.append((row_num, positions[i:i+POS_PER_PAGE]))
        pages = [segments[i:i+ROWS_PER_PAGE] for i in range(0, len(segments), ROWS_PER_PAGE)] \
                or [[]]

        page_idx = {"i": 0}
        win = tk.Toplevel(self.win); win.title("Друк бланку журналу")
        win.geometry("1100x750"); set_icon(win)
        tb = tk.Frame(win, padx=6, pady=5); tb.pack(fill=tk.X)
        lbl = tk.Label(tb, text="", font=("Times New Roman",11,"bold"))
        lbl.pack(side=tk.LEFT, padx=8)
        holder = tk.Frame(win); holder.pack(fill=tk.BOTH, expand=True)
        state = {"fig": None}

        def _render():
            for w in holder.winfo_children(): w.destroy()
            segs = pages[page_idx["i"]]
            n_seg = max(1, len(segs))
            max_len = max((len(pl) for _, pl in segs), default=1)
            fig = Figure(figsize=(max(9, max_len*0.85), max(4.5, n_seg*2.3+1.2)), dpi=100)
            ax = fig.add_subplot(111)
            ROW_H = 2.1
            for si, (row_num, pos_list) in enumerate(segs):
                y_top = n_seg*ROW_H - si*ROW_H
                ax.text(-0.7, y_top-1.0, f"Ряд {row_num}\n(поз. {pos_list[0]}-{pos_list[-1]})",
                        ha="right", va="center", fontsize=9, fontfamily="Times New Roman",
                        fontweight="bold")
                for ci, pos in enumerate(pos_list):
                    p = by_row.get(row_num, {}).get(pos)
                    if p is None: continue
                    x = ci
                    ax.text(x+0.5, y_top+0.15, str(pos), ha="center", va="center",
                            fontsize=8, fontfamily="Times New Roman", color="#555")
                    if p.role == HP_ROLE_RECORDED:
                        top_r = matplotlib.patches.Rectangle(
                            (x+0.03, y_top-0.72), 0.94, 0.55,
                            facecolor="#EAF2FB", edgecolor="#333", linewidth=1.0)
                        ax.add_patch(top_r)
                        ax.text(x+0.5, y_top-0.44, f"В{p.variant}-П{p.replication}",
                                ha="center", va="center", fontsize=8,
                                fontfamily="Times New Roman", color="#1a4b8c", fontweight="bold")
                        bot_r = matplotlib.patches.Rectangle(
                            (x+0.03, y_top-1.55), 0.94, 0.78,
                            facecolor="white", edgecolor="#333", linewidth=1.2)
                        ax.add_patch(bot_r)
                    else:
                        label = {HP_ROLE_GUARD_EDGE:"K", HP_ROLE_GUARD_REP:"P",
                                 HP_ROLE_DEAD:"-", HP_ROLE_POLLINIZER:"+",
                                 HP_ROLE_EXTRA:"x"}.get(p.role, "")
                        rect = matplotlib.patches.Rectangle(
                            (x+0.12, y_top-1.2), 0.76, 1.0,
                            facecolor="#eeeeee", edgecolor="#bbb", linewidth=0.6)
                        ax.add_patch(rect)
                        if label:
                            ax.text(x+0.5, y_top-0.7, label, ha="center", va="center",
                                    fontsize=8, color="#999", fontfamily="Times New Roman")
            ax.set_xlim(-1.6, max_len+0.5); ax.set_ylim(0, n_seg*ROW_H+1.3)
            ax.axis("off")
            ax.set_title(
                "БЛАНК ОБЛІКУ\n"
                "Показник: _______________________   Одиниця: _________\n"
                f"Дата: _______________     Виконав: _______________________     "
                f"Сторінка {page_idx['i']+1}/{len(pages)}",
                fontsize=10, fontfamily="Times New Roman", loc="left")
            fig.subplots_adjust(top=0.82, bottom=0.03, left=0.1, right=0.98)
            state["fig"] = fig
            lbl.configure(text=f"Сторінка {page_idx['i']+1} / {len(pages)}")
            embed_figure(fig, holder)

        def _step(d):
            page_idx["i"] = max(0, min(len(pages)-1, page_idx["i"]+d))
            _render()

        tk.Button(tb, text="◀ Попередня", font=("Times New Roman",10),
                  command=lambda: _step(-1)).pack(side=tk.LEFT, padx=4)
        tk.Button(tb, text="Наступна ▶", font=("Times New Roman",10),
                  command=lambda: _step(1)).pack(side=tk.LEFT, padx=4)
        def _save():
            if state["fig"] is None: return
            path = filedialog.asksaveasfilename(defaultextension=".png",
                        filetypes=[("PNG зображення","*.png")],
                        initialfile=f"blank_form_page_{page_idx['i']+1}.png",
                        title="Зберегти сторінку")
            if not path: return
            try:
                state["fig"].savefig(path, dpi=150, bbox_inches="tight")
                messagebox.showinfo("Збережено", f"Збережено:\n{path}")
            except Exception as ex:
                messagebox.showerror("Помилка", str(ex))
        tk.Button(tb, text="💾 Зберегти PNG", font=("Times New Roman",10),
                  command=_save).pack(side=tk.LEFT, padx=12)
        _render()

    # ── Зведення журналу в таблицю для аналізу ─────────────
    def _edit_series(self):
        """Дозволяє змінити інтервал уже створеної серії повторних
        вимірів (якщо протокол дослідження змінився) — без потреби
        створювати нову серію."""
        if not self._series:
            messagebox.showwarning("", "У цій схемі ще немає жодної серії повторних "
                                       "вимірів."); return
        dlg = tk.Toplevel(self.win); dlg.title("Редагувати серію")
        dlg.resizable(False, False); set_icon(dlg); dlg.grab_set()
        frm = tk.Frame(dlg, padx=16, pady=14); frm.pack()
        tk.Label(frm, text="Серія:", font=("Times New Roman",11)
                 ).grid(row=0, column=0, sticky="w")
        base_names = sorted(self._series.keys())
        base_v = tk.StringVar(value=base_names[0])
        base_cb = ttk.Combobox(frm, textvariable=base_v, values=base_names,
                               state="readonly", width=24)
        base_cb.grid(row=0, column=1, sticky="w", padx=8)

        info_lbl = tk.Label(frm, text="", font=("Times New Roman",9), fg="#666",
                            justify="left", wraplength=320)
        info_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))
        tk.Label(frm, text="Інтервал між вимірами, днів:", font=("Times New Roman",11)
                 ).grid(row=2, column=0, sticky="w", pady=(8,2))
        interval_v = tk.StringVar()
        tk.Entry(frm, textvariable=interval_v, width=6, font=("Times New Roman",11)
                 ).grid(row=2, column=1, sticky="w", padx=8, pady=(8,2))

        def _refresh(*_):
            bn = base_v.get()
            info = self._series.get(bn, {})
            rounds = info.get("rounds", [])
            interval_v.set(str(info.get("interval_days", "")))
            dates_txt = ", ".join(r["date"] for r in rounds) if rounds else "ще немає замірів"
            info_lbl.configure(text=f"Заміри в серії ({len(rounds)}): {dates_txt}")
        base_v.trace_add("write", _refresh)
        _refresh()

        def _save():
            try:
                new_interval = int(interval_v.get())
                if new_interval <= 0: raise ValueError
            except ValueError:
                messagebox.showwarning("", "Інтервал має бути додатним цілим числом днів.",
                                       parent=dlg); return
            bn = base_v.get()
            self._series[bn]["interval_days"] = new_interval
            self._sync_series_to_scheme_file()
            dlg.destroy()
            messagebox.showinfo("Збережено",
                f"Інтервал серії «{bn}» змінено на {new_interval} днів.")

        bf = tk.Frame(frm); bf.grid(row=3, column=0, columnspan=2, pady=(14,0))
        tk.Button(bf, text="Зберегти", bg="#1a6b1a", fg="white", font=("Times New Roman",11),
                  command=_save).pack(side=tk.LEFT, padx=4)
        tk.Button(bf, text="Скасувати", font=("Times New Roman",11),
                  command=dlg.destroy).pack(side=tk.LEFT)
        center_win(dlg)

    def _show_series_dynamics(self):
        """Швидкий огляд динаміки серії повторних вимірів — по кожному
        варіанту окремо, по датах замірів (раунди можуть належати різним
        рокам, якщо серія триває довше одного сезону)."""
        if not self._series:
            messagebox.showwarning("", "У цій схемі ще немає жодної серії повторних "
                                       "вимірів."); return
        base_names = sorted(self._series.keys())
        chosen = pick_indicators_dialog(self.win, {nm: {} for nm in base_names}, multi_select=False)
        if not chosen: return
        base_name = chosen[0]
        rounds = self._series[base_name]["rounds"]
        if not rounds:
            messagebox.showwarning("", "У цієї серії ще немає жодного заміру."); return

        variant_round_mean = {}
        factor_cols = None
        for rnd in rounds:
            values = self._get_round_values(rnd)
            if not values: continue
            # Для коректної агрегації потрібні й самі рослини (ролі/варіант/
            # фактори) — вони не змінюються між роками (крім випадів), тож
            # достатньо базової схеми.
            plants = _plants_from_saved(self._base_scheme_data.get("plants", []))
            fc, agg_rows = aggregate_journal_data(
                plants, self._base_scheme_data.get("factor_defs", []),
                self._base_scheme_data.get("variant_names", []),
                {rnd["indicator"]: {"unit": "", "values": values}}, [rnd["indicator"]])
            factor_cols = fc
            variant_rows = aggregate_to_variant_level(fc, agg_rows, [rnd["indicator"]])
            for r in variant_rows:
                combo = tuple(r[c] for c in fc)
                variant_round_mean.setdefault(combo, {})[rnd["date"]] = r[rnd["indicator"]]

        if not variant_round_mean:
            messagebox.showwarning("", "Не вдалось зібрати дані жодного раунду."); return

        dates = [r["date"] for r in rounds]
        win = tk.Toplevel(self.win); win.title(f"Динаміка серії «{base_name}»")
        win.geometry("750x450"); set_icon(win)
        headers = list(factor_cols) + dates
        tbl_rows = []
        for combo in sorted(variant_round_mean.keys()):
            row = list(combo)
            for dt in dates:
                v = variant_round_mean[combo].get(dt)
                row.append(v if v is not None else "")
            tbl_rows.append(row)
        tk.Label(win, text=f"Середнє по варіанту за кожну дату заміру "
                          f"(інтервал серії: {self._series[base_name]['interval_days']} дн.)",
                 font=("Times New Roman",10), fg="#555").pack(fill=tk.X, padx=10, pady=(8,4))
        frm, _ = make_tv(win, headers, tbl_rows)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

    def _show_indicator_by_years(self):
        """Швидкий огляд: як один показник змінювався по роках, по кожному
        варіанту окремо — без переходу в повноцінний аналіз. Корисно,
        щоб оцінити тенденцію, перш ніж вирішувати про змішаний RM."""
        if not self._scheme_folder:
            messagebox.showwarning("", "Спочатку відкрийте схему."); return
        years_data = {}
        for name in sorted(os.listdir(self._scheme_folder)):
            year_path = os.path.join(self._scheme_folder, name)
            if os.path.isdir(year_path) and name.isdigit():
                jf = os.path.join(year_path, f"журнал_{name}.sadp")
                if os.path.exists(jf):
                    with open(jf, "r", encoding="utf-8") as f:
                        years_data[name] = json.load(f)
        if not years_data:
            messagebox.showwarning("", "У теці схеми ще немає жодного збереженого "
                                       "журналу за рік."); return

        all_indicators = sorted({nm for yd in years_data.values() for nm in yd.get("records", {})})
        if not all_indicators:
            messagebox.showwarning("", "Жоден рік не містить жодного показника."); return
        chosen = pick_indicators_dialog(self.win, {nm: {} for nm in all_indicators}, multi_select=False)
        if not chosen: return
        indicator = chosen[0]

        years_present = sorted(y for y, yd in years_data.items() if indicator in yd.get("records", {}))
        variant_year_mean = {}
        for y in years_present:
            yd = years_data[y]
            plants = _plants_from_saved(yd.get("plants", []))
            factor_cols, rows = aggregate_journal_data(
                plants, yd.get("factor_defs", []), yd.get("variant_names", []),
                yd.get("records", {}), [indicator])
            variant_rows = aggregate_to_variant_level(factor_cols, rows, [indicator])
            for r in variant_rows:
                combo = tuple(r[fc] for fc in factor_cols)
                variant_year_mean.setdefault(combo, {})[y] = r[indicator]

        win = tk.Toplevel(self.win); win.title(f"«{indicator}» по роках")
        win.geometry("700x450"); set_icon(win)
        headers = list(factor_cols) + years_present
        tbl_rows = []
        for combo in sorted(variant_year_mean.keys()):
            row = list(combo)
            for y in years_present:
                v = variant_year_mean[combo].get(y)
                row.append(v if v is not None else "")
            tbl_rows.append(row)
        tk.Label(win, text=f"Середнє по варіанту за кожен рік (усереднено по повторностях)",
                 font=("Times New Roman",10), fg="#555").pack(fill=tk.X, padx=10, pady=(8,4))
        frm, _ = make_tv(win, headers, tbl_rows)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

    def _reduce_for_analysis(self):
        """Зводить дані ВИКЛЮЧНО з поточної таблиці (без жодного діалогу
        вибору обліків) у формат: фактор А, фактор Б…, Повт.1…Повт.N
        (стільки стовпців, скільки повторень заплановано в самій схемі —
        стовпець існує навіть якщо для якоїсь повторності бракує
        введеного значення), і останній стовпець — середнє по варіанту
        (між повтореннями). Кожна облікова рослина вже закодована в
        схемі своїм варіантом і повторністю — цей код лише розкладає
        уже усереднені (в межах повторності) значення по правильних
        місцях таблиці, без ручного перекладання."""
        if not self.plants:
            messagebox.showwarning("", "Спочатку відкрийте схему або журнал."); return
        self._sync_grid_to_working_values()
        if not self._working_values:
            messagebox.showwarning("", "Таблиця порожня — спочатку внесіть дані."); return

        is_multi = bool(self.factor_defs) and any(p.factors for p in self.plants)
        factor_cols = [fdef["name"] for fdef in self.factor_defs] if is_multi else ["Варіант"]

        tmp_records = {"__поточний__": {"unit": "", "values": self._working_values}}
        _fc, rows = aggregate_journal_data(
            self.plants, self.factor_defs, self.variant_names, tmp_records, ["__поточний__"])
        if not rows:
            messagebox.showwarning("", "Немає жодної сформованої повторності "
                                       "(облікові рослини не визначені в схемі)."); return

        # Повний перелік повторень ІЗ САМОЇ СХЕМИ (а не лише тих, де вже є
        # введене значення) — стовпці відповідають задуму досліду, а не
        # тому, скільки встигли заповнити.
        all_reps = sorted({p.replication for p in self.plants
                           if p.role == HP_ROLE_RECORDED and p.replication})

        by_combo = {}
        for r in rows:
            combo_key = tuple(r[fc] for fc in factor_cols)
            by_combo.setdefault(combo_key, {})[r["replication"]] = r["__поточний__"]
        combos_sorted = sorted(by_combo.keys())

        headers = factor_cols + [f"Повт.{i+1}" for i in range(len(all_reps))] + ["Середнє"]
        tbl_rows = []
        for combo in combos_sorted:
            row = list(combo)
            rep_vals = by_combo[combo]
            col_vals = [rep_vals.get(rep) for rep in all_reps]
            row += ["" if v is None else v for v in col_vals]
            present = [v for v in col_vals if v is not None]
            row.append(round(sum(present)/len(present), 4) if present else "")
            tbl_rows.append(row)

        win = tk.Toplevel(self.win); win.title("Зведена таблиця для аналізу")
        win.geometry("980x600"); set_icon(win)
        tb = tk.Frame(win, padx=6, pady=5); tb.pack(fill=tk.X)
        tk.Button(tb, text="📋 Копіювати таблицю", font=("Times New Roman",11),
                  command=lambda: self._copy_table(win, headers, tbl_rows)
                  ).pack(side=tk.LEFT, padx=4)
        if len(factor_cols) <= 4:
            tk.Button(tb, text="➡ Відкрити в головній ANOVA-таблиці", bg="#1a6b1a", fg="white",
                      font=("Times New Roman",11),
                      command=lambda: self._open_in_main_anova("__поточний__", rows, factor_cols)
                      ).pack(side=tk.LEFT, padx=4)

        note = ("Кожен рядок — унікальна комбінація " +
                ("рівнів факторів" if is_multi else "варіанту") +
                "; стовпці «Повт.N» — середнє значення показника в цій повторності "
                "(усереднено з облікових рослин у її межах — уникає псевдоповторності); "
                "останній стовпець «Середнє» — середнє по варіанту (між повтореннями).")
        tk.Label(win, text=note, font=("Times New Roman",10), fg="#555", justify="left",
                 wraplength=940, anchor="w").pack(fill=tk.X, padx=10, pady=(4,4))
        frm, _ = make_tv(win, headers, tbl_rows)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

    def _copy_table(self, win, headers, tbl_rows):
        lines = ["\t".join(headers)]
        for row in tbl_rows:
            lines.append("\t".join(str(v) for v in row))
        win.clipboard_clear(); win.clipboard_append("\n".join(lines))
        messagebox.showinfo("Скопійовано",
            "Таблицю скопійовано у буфер обміну.\n"
            "Вставте (Ctrl+V) у таблицю потрібного аналізу — курсор поставте "
            "в перший стовпчик, перший рядок.")

    def _open_in_main_anova(self, record_name, rows, factor_cols):
        """Відкриває головну багатофакторну ANOVA-таблицю програми (до 4
        факторів) і одразу заповнює її: один рядок на кожну унікальну
        комбінацію рівнів факторів, значення повторностей — у стовпці
        Повт.1, Повт.2… (номер визначається порядком номерів повторності)."""
        app = getattr(self._parent, "_sad_app", None)
        if app is None:
            messagebox.showerror("Не вдалося",
                "Не знайдено головного вікна програми — відкрийте таблицю "
                "вручну і скористайтесь «📋 Копіювати»."); return
        fc = len(factor_cols)
        if fc > 4:
            messagebox.showwarning("", "Головна таблиця підтримує максимум "
                                       "4 фактори одночасно."); return

        by_combo = {}
        for r in rows:
            combo_key = tuple(r[fname] for fname in factor_cols)
            by_combo.setdefault(combo_key, {})[r["replication"]] = r[record_name]
        combos_sorted = sorted(by_combo.keys())
        all_reps = sorted({rep for v in by_combo.values() for rep in v.keys()})
        n_rep_cols = max(len(all_reps), 1)

        app.open_table(fc)
        for i, fname in enumerate(factor_cols):
            key = app.factor_keys[i]
            app._set_ftitle(key, fname)
            app.header_labels[i].configure(text=app.ftitle(key))

        while len(app.entries) < len(combos_sorted): app.add_row()
        while (app.cols - fc) < n_rep_cols: app.add_column()

        for i, combo in enumerate(combos_sorted):
            for k, lvl_name in enumerate(combo):
                app.entries[i][k].delete(0, tk.END)
                app.entries[i][k].insert(0, str(lvl_name))
            rep_vals = by_combo[combo]
            for ci, rep_num in enumerate(all_reps):
                col = fc + ci
                if col >= app.cols: continue
                v = rep_vals.get(rep_num)
                app.entries[i][col].delete(0, tk.END)
                if v is not None: app.entries[i][col].insert(0, str(v))

        messagebox.showinfo("Дані перенесено",
            f"Дані показника «{record_name}» перенесено в головну {fc}-факторну "
            f"ANOVA-таблицю ({len(combos_sorted)} комбінацій × {n_rep_cols} повторень). "
            "Перевірте таблицю і натисніть «▶ Аналіз».")


# ═══════════════════════════════════════════════════════════════
# TRIAL DESIGN GENERATOR
# ═══════════════════════════════════════════════════════════════
class TrialDesignWindow:
    """Генератор плану польового досліду — універсальний для всіх культур."""

    # ── Типи культур з налаштуваннями ────────────────────────
    CULTURES = {
        "Зернові / польові культури": {
            "plot_w": 3.0, "plot_l": 10.0, "unit": "ділянка",
            "garden": False,
            "indicators": ["Висота рослин, см", "Маса 1000 зерен, г",
                           "Врожайність, т/га", "Вміст білку, %"],
        },
        "Садівництво (дерева)": {
            "plot_w": 4.0, "plot_l": 5.0, "unit": "дерево",
            "garden": True,
            "row_sp": 4.0, "plant_sp": 5.0,
            "plants_plot": 5, "guard_ends": 1, "guard_rows": 1,
            "indicators": ["Висота дерева, м", "Діаметр крони, м",
                           "Врожайність з дерева, кг", "Маса плоду, г",
                           "Вміст ЦРР, °Brix", "% зав'язування квіток"],
        },
        "Ягідники": {
            "plot_w": 2.0, "plot_l": 0.5, "unit": "кущ",
            "garden": True,
            "row_sp": 2.0, "plant_sp": 0.5,
            "plants_plot": 8, "guard_ends": 2, "guard_rows": 1,
            "indicators": ["Висота куща, см", "Кількість пагонів",
                           "Врожайність з куща, кг", "Маса ягоди, г",
                           "Вміст ЦРР, °Brix"],
        },
        "Овочівництво (відкритий ґрунт)": {
            "plot_w": 2.0, "plot_l": 5.0, "unit": "ділянка",
            "garden": False,
            "indicators": ["Висота рослин, см", "Маса плоду, г",
                           "Врожайність, т/га", "Товарність, %",
                           "Вихід стандарту, %"],
        },
        "Захищений ґрунт (теплиця)": {
            "plot_w": 1.0, "plot_l": 4.0, "unit": "грядка",
            "garden": False,
            "indicators": ["Висота рослин, см", "Кількість плодів/рослину",
                           "Врожайність, кг/м²", "Маса плоду, г"],
        },
        "Виноградарство": {
            "plot_w": 3.0, "plot_l": 1.5, "unit": "кущ",
            "garden": True,
            "row_sp": 3.0, "plant_sp": 1.5,
            "plants_plot": 6, "guard_ends": 2, "guard_rows": 1,
            "indicators": ["Маса грона, г", "Кількість грон/кущ",
                           "Врожайність з куща, кг", "Вміст ЦРР, °Brix",
                           "Кислотність, г/л"],
        },
    }

    DESIGNS = [
        ("crd",   "CRD — Повністю рандомізований",
         "Всі ділянки рівноцінні. Варіанти розміщуються випадково."),
        ("rcbd",  "RCBD — Рандомізовані повні блоки (рекомендується)",
         "Поле ділиться на повторності. Кожна повторність = всі варіанти."),
        ("latin", "Латинський квадрат",
         "Контролює 2 джерела мінливості. k варіантів = k рядів = k стовпців."),
        ("split", "Split-plot — Розщеплені ділянки",
         "Два фактори різного масштабу. WP = великі ділянки, SP = підділянки."),
    ]

    HELP_TEXT = """
ГЕНЕРАТОР ПЛАНУ ПОЛЬОВОГО ДОСЛІДУ
══════════════════════════════════════════════════

ЩО РОБИТЬ?
  Автоматично рандомізує розміщення варіантів
  і формує документи для польової роботи:
  • Польова схема (кольорова карта ділянок)
  • Список рандомізації (порядок закладки)
  • Польовий журнал (таблиця для вимірювань)

══════════════════════════════════════════════════
КРОК 1. ТИП КУЛЬТУРИ
══════════════════════════════════════════════════
  Оберіть тип культури — програма підлаштує:
  • Типові розміри ділянок
  • Стандартні показники для журналу
  • Термінологію (ділянка/дерево/кущ)

══════════════════════════════════════════════════
КРОК 2. ВАРІАНТИ ДОСЛІДУ
══════════════════════════════════════════════════
  Введіть назви варіантів — по одному на рядок.
  Приклади:
    Контроль (без добрив)
    N60P60K60
    N90P60K60
    N120P60K60

  Для Split-plot — введіть також sub-plot варіанти.

══════════════════════════════════════════════════
КРОК 3. ДИЗАЙН ДОСЛІДУ
══════════════════════════════════════════════════

  CRD — Повністю рандомізований:
    Для однорідних умов. Всі ділянки рівноцінні.
    Варіанти розміщуються абсолютно випадково.
    Простий але потребує однорідного фону.

  RCBD — Рандомізовані повні блоки:
    РЕКОМЕНДУЄТЬСЯ для більшості дослідів.
    Поле ділиться на ПОВТОРНОСТІ (блоки).
    Кожна повторність містить всі варіанти.
    Блоки розміщують перпендикулярно до основного
    градієнта мінливості (схил, зрошення, ряди).
    У садівництві: повторність = кілька дерев/ряд.

  Латинський квадрат:
    Контролює ДВА незалежних джерела мінливості.
    k варіантів → k рядів × k стовпців ділянок.
    Кожен варіант — рівно 1 раз у кожному ряду
    і рівно 1 раз у кожному стовпці.
    Рекомендується при k=4-6 варіантів.
    Після досліду → 3-факторна ANOVA у S.A.D.
    (Фактор A = Варіант, B = Рядок, C = Стовпець)

  Split-plot — Розщеплені ділянки:
    Для двох факторів різного масштабу.
    WP (whole-plot): головний фактор — великі ділянки.
    SP (sub-plot): другорядний — всередині WP.
    Приклади:
      Зернові:    WP = обробка ґрунту, SP = сорт
      Садівництво: WP = підщепа, SP = сорт
      Овочі:      WP = спосіб вирощування, SP = сорт

══════════════════════════════════════════════════
КРОК 4. SEED РАНДОМІЗАЦІЇ
══════════════════════════════════════════════════
  Seed — технічний номер жеребкування.
  При однаковому seed → однакова схема.
  ЗБЕРІГАЙТЕ seed у документації досліду!
  Seed ≠ Рік: seed може бути будь-яким числом.

══════════════════════════════════════════════════
КРОК 5. ПОЛЬОВИЙ ЖУРНАЛ
══════════════════════════════════════════════════
  Налаштуйте назви показників (через ";").
  Програма підставляє типові показники для
  обраного типу культури.
  Натисніть "▶ Оновити" після зміни назв.
  Збережіть журнал у Excel для польової роботи.

══════════════════════════════════════════════════
ПОЛЬОВІ КУЛЬТУРИ (ЗЕРНОВІ, ОВОЧІ) — ОСОБЛИВОСТІ
══════════════════════════════════════════════════
  Ділянка = прямокутна площа посіву одного варіанту.

  Захисна смуга (по периметру ділянки):
    Крайні рослини перебувають під впливом сусідньої
    ділянки (інший варіант, інше добриво/обробка) —
    це межовий ефект. Такі рослини НЕ включають в облік
    (збір урожаю, виміри) — рахують лише внутрішню,
    "облікову" площу.
    Типові значення: 0.3-1 м залежно від культури
    (ширші для високорослих/просапних культур).

  Буфер (прохід) між ділянками:
    Фізичний проміжок між сусідніми ділянками — щоб
    добрива/пестициди одного варіанту не зносило на
    сусідній, і для проходу техніки. Не є частиною
    жодної ділянки, у площу обліку не входить.
    Типові значення: 0.5-1 м (ширше — при обробці
    з обприскувача чи механізованому збиранні).

  Загальна потрібна площа поля істотно більша за просту
  суму ділянок — вона враховує ОБИДВІ смуги. Перевіряйте
  підсумок у вікні після генерації плану, перш ніж
  відводити поле під дослід.

══════════════════════════════════════════════════
САДІВНИЦТВО — ОСОБЛИВОСТІ
══════════════════════════════════════════════════
  Ділянка = кілька дерев одного варіанту в ряду.
  Повторність = окремий ряд або частина ряду.

  Приклад для яблуні (схема 4×5 м):
    4 сорти × 3 повторності = 12 ділянок
    По 3-5 дерев на ділянку
    Розмір ділянки: 4 м (ширина) × 15 м (5 дерев)

  У RCBD: кожна повторність = 1 ряд дерев,
  де всі 4 сорти розміщені випадково в ряду.

  Показники для кожного дерева усереднюють
  і записують одне середнє значення на ділянку.
"""

    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("Генератор плану польового досліду")
        self.win.geometry("1160x760")
        self.win.resizable(True, True)
        set_icon(self.win)
        self._plan_data = None
        self._build()

    # ═══════════════════════════════════════════════════════
    # _build — головний інтерфейс
    # ═══════════════════════════════════════════════════════
    def _build(self):
        rf = ("Times New Roman", 11)

        # ── Toolbar ────────────────────────────────────────
        top = tk.Frame(self.win, padx=8, pady=5); top.pack(fill=tk.X)
        tk.Button(top, text="▶ Згенерувати план", bg="#c62828", fg="white",
                  font=("Times New Roman", 13),
                  command=self._generate).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="💾 Зберегти схему для журналу", bg="#1a6b1a", fg="white",
                  font=("Times New Roman", 11),
                  command=self._export_to_journal).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="📚 Довідка", bg="#1a4b8c", fg="white",
                  font=rf, command=self._show_help).pack(side=tk.LEFT, padx=4)

        # ── Основна область ────────────────────────────────
        main = tk.Frame(self.win); main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # ── ЛІВА ПАНЕЛЬ (прокручувана) ─────────────────────
        left_outer = tk.Frame(main, width=360)
        left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_outer.pack_propagate(False)
        lc = tk.Canvas(left_outer, highlightthickness=0)
        lc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        lsb = ttk.Scrollbar(left_outer, orient="vertical", command=lc.yview)
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        lc.configure(yscrollcommand=lsb.set)
        lf = tk.Frame(lc); lc.create_window((0, 0), window=lf, anchor="nw")
        lf.bind("<Configure>", lambda e: lc.configure(scrollregion=lc.bbox("all")))
        left_outer.bind("<MouseWheel>",
                        lambda e: lc.yview_scroll(int(-1*(e.delta/120)), "units"))

        # ─── Тип культури ──────────────────────────────────
        cf = tk.LabelFrame(lf, text="1. Тип культури",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        cf.pack(fill=tk.X, pady=(0, 4))
        self.culture_var = tk.StringVar(value=list(self.CULTURES.keys())[0])
        self.culture_cb = ttk.Combobox(cf, textvariable=self.culture_var,
                                       values=list(self.CULTURES.keys()),
                                       state="readonly", width=36, font=rf)
        self.culture_cb.pack(fill=tk.X, pady=2)
        self.culture_cb.bind("<<ComboboxSelected>>", self._on_culture)
        self._culture_hint = tk.Label(cf, text="", font=("Times New Roman", 9),
                                      fg="#555", justify="left")
        self._culture_hint.pack(anchor="w")

        # Для ягідників прийнято ОБИДВА підходи — за окремими кущами (як
        # сад) або за площею повторності (як поле). Перемикач показується
        # лише для цієї культури.
        self._berry_model_frame = tk.Frame(cf)
        self._berry_model_var = tk.StringVar(value="garden")
        tk.Label(self._berry_model_frame, text="Модель розрахунку:",
                 font=("Times New Roman", 9)).pack(anchor="w", pady=(4,0))
        bm_row = tk.Frame(self._berry_model_frame); bm_row.pack(anchor="w")
        tk.Radiobutton(bm_row, text="За рослинами (ряд кущів)",
                      variable=self._berry_model_var, value="garden",
                      font=("Times New Roman", 9), command=self._on_culture
                      ).pack(side=tk.LEFT)
        tk.Radiobutton(bm_row, text="За площею повторності",
                      variable=self._berry_model_var, value="area",
                      font=("Times New Roman", 9), command=self._on_culture
                      ).pack(side=tk.LEFT, padx=(8,0))

        # ─── Варіанти ──────────────────────────────────────
        vf = tk.LabelFrame(lf, text="2. Варіанти досліду (один на рядок)",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        vf.pack(fill=tk.X, pady=(0, 4))
        self.var_text = tk.Text(vf, width=38, height=6, font=rf, wrap="word")
        self.var_text.pack(fill=tk.X, pady=2)
        self.var_text.insert("1.0", "Контроль\nВаріант 1\nВаріант 2\nВаріант 3")

        # ─── Дизайн ────────────────────────────────────────
        df = tk.LabelFrame(lf, text="3. Дизайн досліду",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        df.pack(fill=tk.X, pady=(0, 4))
        self.design_var = tk.StringVar(value="rcbd")
        for val, label, desc in self.DESIGNS:
            fr = tk.Frame(df); fr.pack(fill=tk.X, pady=1)
            tk.Radiobutton(fr, text=label, variable=self.design_var, value=val,
                           font=("Times New Roman", 11),
                           command=self._on_design).pack(side=tk.LEFT)
        self._design_hint = tk.Label(df, text="", font=("Times New Roman", 9),
                                     fg="#1a4b8c", bg="#eef4ff",
                                     justify="left", wraplength=320, padx=4, pady=3)
        self._design_hint.pack(fill=tk.X, pady=4)

        # Split-plot додатковий фактор
        self.sp_frame = tk.LabelFrame(lf, text="Sub-plot варіанти",
                                      font=("Times New Roman", 11, "bold"),
                                      padx=8, pady=4)
        self.sp_text = tk.Text(self.sp_frame, width=38, height=3, font=rf)
        self.sp_text.pack(fill=tk.X)
        self.sp_text.insert("1.0", "Сорт А\nСорт Б\nСорт В")
        # (показується лише для split-plot)

        # ─── Параметри ─────────────────────────────────────
        pf = tk.LabelFrame(lf, text="4. Параметри",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        pf.pack(fill=tk.X, pady=(0, 4))
        self._pv = {}
        for ri, (lbl, key, default, hint) in enumerate([
            ("Повторностей:", "reps", "3",
             "Кількість повторностей (рядів)"),
            ("Seed рандомізації:", "seed", "2024",
             "Число для відтворення жеребкування. ≠ рік!"),
        ]):
            tk.Label(pf, text=lbl, font=rf).grid(row=ri, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default); self._pv[key] = v
            tk.Entry(pf, textvariable=v, width=9, font=rf
                     ).grid(row=ri, column=1, sticky="w", padx=6)
            tk.Label(pf, text=hint, font=("Times New Roman", 9), fg="#666"
                     ).grid(row=ri, column=2, sticky="w")

        # ─── Польові параметри (для зернових/овочів) ────────
        self._field_frame = tk.LabelFrame(lf, text="Розміри ділянки",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        self._field_frame.pack(fill=tk.X, pady=(0, 4))

        tk.Label(self._field_frame, text="Спосіб задання розміру:", font=rf
                 ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(2,0))
        self._size_mode_var = tk.StringVar(value="wh")
        mode_row = tk.Frame(self._field_frame)
        mode_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(0,4))
        tk.Radiobutton(mode_row, text="Шириною і довжиною", variable=self._size_mode_var,
                      value="wh", font=rf, command=self._on_size_mode
                      ).pack(side=tk.LEFT)
        tk.Radiobutton(mode_row, text="Площею повторності", variable=self._size_mode_var,
                      value="rep_area", font=rf, command=self._on_size_mode
                      ).pack(side=tk.LEFT, padx=(10,0))

        self._size_wh_frame = tk.Frame(self._field_frame)
        for ri, (lbl, key, default, hint) in enumerate([
            ("Ширина, м:", "pw", "5", "Загальна (посівна) ширина ділянки"),
            ("Довжина, м:", "pl", "10", "Загальна (посівна) довжина ділянки"),
        ]):
            tk.Label(self._size_wh_frame, text=lbl, font=rf
                     ).grid(row=ri, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default); self._pv[key] = v
            tk.Entry(self._size_wh_frame, textvariable=v, width=9, font=rf
                     ).grid(row=ri, column=1, sticky="w", padx=6)
            tk.Label(self._size_wh_frame, text=hint,
                     font=("Times New Roman", 9), fg="#666"
                     ).grid(row=ri, column=2, sticky="w")

        self._size_rep_frame = tk.Frame(self._field_frame)
        for ri, (lbl, key, default, hint) in enumerate([
            ("Бажана площа повторності, м²:", "rep_area", "15",
             "За методикою досліду (напр. 12-20 м²) — довжину ділянки "
             "програма розрахує сама"),
            ("Ширина ділянки, м:", "pw_ra", "2",
             "Задана шириною сівалки/оброблювача — зазвичай стала величина"),
        ]):
            tk.Label(self._size_rep_frame, text=lbl, font=rf
                     ).grid(row=ri, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default); self._pv[key] = v
            tk.Entry(self._size_rep_frame, textvariable=v, width=9, font=rf
                     ).grid(row=ri, column=1, sticky="w", padx=6)
            tk.Label(self._size_rep_frame, text=hint,
                     font=("Times New Roman", 9), fg="#666", wraplength=220, justify="left"
                     ).grid(row=ri, column=2, sticky="w")
        self._rep_area_result_lbl = tk.Label(self._size_rep_frame, text="",
                     font=("Times New Roman", 9, "italic"), fg="#1a4b8c")
        self._rep_area_result_lbl.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2,0))

        self._size_wh_frame.grid(row=2, column=0, columnspan=3, sticky="w")

        for ri, (lbl, key, default, hint) in enumerate([
            ("Захисна смуга по периметру, м:", "border", "0.5",
             "Крайні рослини — під межовим ефектом сусіда, не враховуються"),
            ("Буфер (прохід) між ділянками, м:", "buffer", "0.5",
             "Проти зсуву добрив/пестицидів, для проходу техніки"),
        ]):
            r = 3 + ri
            tk.Label(self._field_frame, text=lbl, font=rf
                     ).grid(row=r, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default); self._pv[key] = v
            tk.Entry(self._field_frame, textvariable=v, width=9, font=rf
                     ).grid(row=r, column=1, sticky="w", padx=6)
            tk.Label(self._field_frame, text=hint,
                     font=("Times New Roman", 9), fg="#666"
                     ).grid(row=r, column=2, sticky="w")

        tk.Label(self._field_frame, text="Доступна площа під дослід, м² (необов'язково):",
                 font=rf).grid(row=5, column=0, sticky="w", pady=(6,2))
        self._pv["avail_area"] = tk.StringVar(value="")
        tk.Entry(self._field_frame, textvariable=self._pv["avail_area"], width=9, font=rf
                 ).grid(row=5, column=1, sticky="w", padx=6, pady=(6,2))
        tk.Label(self._field_frame, text="Якщо вказано — програма звірить і чесно "
                                         "попередить, якщо землі не вистачає",
                 font=("Times New Roman", 9), fg="#666"
                 ).grid(row=5, column=2, sticky="w", pady=(6,2))

        # ─── Садівничі параметри ─────────────────────────────
        self._garden_frame = tk.LabelFrame(lf, text="Параметри садіння",
                            font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        self._gv = {}
        garden_params = [
            ("Між рядами (A), м:",              "row_sp",     "4.0",
             "Відстань між рядами"),
            ("В ряду (B), м:",                  "plant_sp",   "5.0",
             "Відстань між рослинами в ряду"),
            ("Облікових рослин на ділянку:",   "plants_plot","5",
             "Без захисних — лише облікові"),
            ("Захисних рослин (поч. і кін.):", "guard_ends", "1",
             "Кількість з кожного боку ряду"),
            ("Захисних рядів між варіантами:", "guard_rows", "1",
             "Рядів-буферів між повторностями"),
        ]
        for ri, (lbl, key, default, hint) in enumerate(garden_params):
            tk.Label(self._garden_frame, text=lbl, font=rf
                     ).grid(row=ri, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=default); self._gv[key] = v
            tk.Entry(self._garden_frame, textvariable=v, width=9, font=rf
                     ).grid(row=ri, column=1, sticky="w", padx=6)
            tk.Label(self._garden_frame, text=hint,
                     font=("Times New Roman", 9), fg="#666"
                     ).grid(row=ri, column=2, sticky="w")

        # ─── Паспорт ───────────────────────────────────────
        nf = tk.LabelFrame(lf, text="5. Паспорт досліду",
                           font=("Times New Roman", 11, "bold"), padx=8, pady=4)
        nf.pack(fill=tk.X, pady=(0, 4))
        self._nv = {}
        for ri, (lbl, key) in enumerate([
            ("Назва:", "name"), ("Рік:", "year"),
            ("Місце:", "loc"),  ("Відповідальний:", "resp"),
        ]):
            tk.Label(nf, text=lbl, font=rf).grid(row=ri, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=(str(datetime.now().year) if key=="year" else ""))
            self._nv[key] = v
            tk.Entry(nf, textvariable=v, width=28, font=rf
                     ).grid(row=ri, column=1, sticky="w", padx=6, pady=2)

        # ── ПРАВА ПАНЕЛЬ — вкладки результатів ─────────────
        right = tk.Frame(main); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.nb = ttk.Notebook(right); self.nb.pack(fill=tk.BOTH, expand=True)

        # Вкладка 1: Схема
        t1 = tk.Frame(self.nb); self.nb.add(t1, text="🗺 Польова схема")
        t1_tb = tk.Frame(t1); t1_tb.pack(fill=tk.X, padx=4, pady=3)
        tk.Label(t1_tb,
                 text="Клітинки = ділянки/рослини. Кольори = варіанти.",
                 font=("Times New Roman", 9), fg="#666").pack(side=tk.LEFT)
        tk.Button(t1_tb, text="💾 Зберегти PNG", font=("Times New Roman",10),
                  command=self._save_png).pack(side=tk.RIGHT, padx=4)
        self._scheme_cv = tk.Canvas(t1, bg="white")
        s_vsb = ttk.Scrollbar(t1, orient="vertical",
                               command=self._scheme_cv.yview)
        s_hsb = ttk.Scrollbar(t1, orient="horizontal",
                               command=self._scheme_cv.xview)
        s_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        s_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self._scheme_cv.pack(fill=tk.BOTH, expand=True)
        self._scheme_cv.configure(yscrollcommand=s_vsb.set,
                                   xscrollcommand=s_hsb.set)

        # Вкладка 2: Рандомізація
        t2 = tk.Frame(self.nb); self.nb.add(t2, text="📋 Рандомізація")
        tb2 = tk.Frame(t2); tb2.pack(fill=tk.X, padx=4, pady=3)
        tk.Label(tb2, text="Порядок закладки ділянок:",
                 font=rf).pack(side=tk.LEFT)
        tk.Button(tb2, text="💾 Зберегти TXT", font=("Times New Roman",10),
                  command=self._save_rand_txt).pack(side=tk.RIGHT, padx=4)
        r_vsb = ttk.Scrollbar(t2, orient="vertical")
        r_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.rand_txt = tk.Text(t2, font=("Courier New", 10),
                                yscrollcommand=r_vsb.set,
                                state="disabled", wrap="none")
        self.rand_txt.pack(fill=tk.BOTH, expand=True)
        r_vsb.config(command=self.rand_txt.yview)

        # Вкладка 3: Журнал
        t3 = tk.Frame(self.nb); self.nb.add(t3, text="📓 Польовий журнал")
        tb3 = tk.Frame(t3); tb3.pack(fill=tk.X, padx=4, pady=3)
        tk.Button(tb3, text="💾 Зберегти Excel", font=("Times New Roman",10),
                  command=self._save_excel).pack(side=tk.RIGHT, padx=4)
        tk.Label(tb3, text="Показники:", font=rf).pack(side=tk.LEFT, padx=(0,4))
        self.ind_var = tk.StringVar()
        tk.Entry(tb3, textvariable=self.ind_var, width=55,
                 font=("Times New Roman", 10)).pack(side=tk.LEFT, padx=2)
        tk.Button(tb3, text="▶ Оновити", bg="#c62828", fg="white",
                  font=("Times New Roman", 10),
                  command=self._refresh_journal).pack(side=tk.LEFT, padx=4)
        tk.Label(tb3, text="(через крапку з комою)",
                 font=("Times New Roman", 9), fg="#888").pack(side=tk.LEFT)

        j_frame = tk.Frame(t3); j_frame.pack(fill=tk.BOTH, expand=True)
        j_vsb = ttk.Scrollbar(j_frame, orient="vertical")
        j_hsb = ttk.Scrollbar(j_frame, orient="horizontal")
        j_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        j_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.journal_tv = ttk.Treeview(j_frame, yscrollcommand=j_vsb.set,
                                       xscrollcommand=j_hsb.set)
        self.journal_tv.pack(fill=tk.BOTH, expand=True)
        j_vsb.config(command=self.journal_tv.yview)
        j_hsb.config(command=self.journal_tv.xview)

        # Ініціалізуємо підказки
        self._on_culture()
        self._on_design()

    # ═══════════════════════════════════════════════════════
    # Обробники змін
    # ═══════════════════════════════════════════════════════
    def _on_size_mode(self, *_):
        if self._size_mode_var.get() == "rep_area":
            self._size_wh_frame.grid_forget()
            self._size_rep_frame.grid(row=2, column=0, columnspan=3, sticky="w")
        else:
            self._size_rep_frame.grid_forget()
            self._size_wh_frame.grid(row=2, column=0, columnspan=3, sticky="w")

    def _effective_is_garden(self):
        """Чи трактувати поточну культуру як "сад" (окремі рослини) чи
        як "поле" (площа ділянки) — для ягідників це обирає користувач,
        для решти культур — фіксовано в CULTURES."""
        cfg = self.CULTURES.get(self.culture_var.get(), {})
        if self.culture_var.get() == "Ягідники":
            return self._berry_model_var.get() == "garden"
        return cfg.get("garden", False)

    def _on_culture(self, *_):
        key = self.culture_var.get()
        cfg = self.CULTURES.get(key, {})
        unit = cfg.get("unit", "ділянка")

        if key == "Ягідники":
            self._berry_model_frame.pack(anchor="w", fill=tk.X)
        else:
            self._berry_model_frame.pack_forget()

        is_garden = self._effective_is_garden()

        if is_garden:
            row_sp    = cfg.get("row_sp",    4.0)
            plant_sp  = cfg.get("plant_sp",  5.0)
            n_plot    = cfg.get("plants_plot",5)
            g_ends    = cfg.get("guard_ends", 1)
            g_rows    = cfg.get("guard_rows", 1)
            self._culture_hint.configure(
                text=f"Одиниця: {unit}  |  Схема: {row_sp}×{plant_sp} м")
            if hasattr(self, '_gv'):
                # Підказки заповнюємо лише якщо поля порожні
                if not self._gv["row_sp"].get() or self._gv["row_sp"].get() == "0":
                    self._gv["row_sp"].set(str(row_sp))
                if not self._gv["plant_sp"].get() or self._gv["plant_sp"].get() == "0":
                    self._gv["plant_sp"].set(str(plant_sp))
                if not self._gv["plants_plot"].get():
                    self._gv["plants_plot"].set(str(n_plot))
                if not self._gv["guard_ends"].get():
                    self._gv["guard_ends"].set(str(g_ends))
                if not self._gv["guard_rows"].get():
                    self._gv["guard_rows"].set(str(g_rows))
            # Показати садівничий фрейм, сховати польовий
            if hasattr(self, '_garden_frame'):
                self._garden_frame.pack(fill=tk.X, pady=(0,4),
                                        after=self._field_frame)
                self._field_frame.pack_forget()
        else:
            pw = cfg.get("plot_w", 5); pl = cfg.get("plot_l", 10)
            self._culture_hint.configure(
                text=f"Одиниця: {unit}  |  Типові розміри: {pw}×{pl} м")
            if hasattr(self, '_pv'):
                self._pv["pw"].set(str(pw))
                self._pv["pl"].set(str(pl))
            # Показати польовий фрейм, сховати садівничий
            if hasattr(self, '_garden_frame'):
                self._garden_frame.pack_forget()
                self._field_frame.pack(fill=tk.X, pady=(0,4))

        indicators = cfg.get("indicators", [])
        if hasattr(self, 'ind_var'):
            self.ind_var.set("; ".join(indicators))

    def _on_design(self, *_):
        val = self.design_var.get()
        hints = {
            "crd":   "Однорідний фон. Варіанти розміщуються абсолютно випадково по всьому полю.",
            "rcbd":  "Рекомендується. Поле ділиться на повторності. Кожна повторність = всі варіанти.",
            "latin": "k варіантів = k рядів = k стовпців. Аналіз — 3-факторна ANOVA у S.A.D.",
            "split": "Введіть WP (whole-plot) варіанти вище і SP варіанти нижче.",
        }
        if hasattr(self, '_design_hint'):
            self._design_hint.configure(text=hints.get(val, ""))
        if hasattr(self, 'sp_frame'):
            if val == "split":
                self.sp_frame.pack(fill=tk.X, pady=(0, 4),
                                   after=self.sp_frame.master.winfo_children()[-1]
                                   if self.sp_frame.master.winfo_children() else None)
            else:
                self.sp_frame.pack_forget()

    # ═══════════════════════════════════════════════════════
    # Довідка
    # ═══════════════════════════════════════════════════════
    def _show_help(self):
        win = tk.Toplevel(self.win)
        win.title("Довідка — Генератор плану досліду")
        win.geometry("700x660"); set_icon(win)
        frm = tk.Frame(win); frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        vsb = ttk.Scrollbar(frm, orient="vertical"); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frm, wrap="word", font=("Times New Roman", 11),
                      yscrollcommand=vsb.set, relief=tk.FLAT,
                      bg="#fafafa", padx=10, pady=8, cursor="arrow")
        txt.pack(fill=tk.BOTH, expand=True); vsb.config(command=txt.yview)
        txt.insert("1.0", self.HELP_TEXT.strip()); txt.configure(state="disabled")
        txt.bind("<MouseWheel>",
                 lambda e: txt.yview_scroll(int(-1*(e.delta/120)), "units"))
        tk.Button(win, text="Закрити", command=win.destroy,
                  font=("Times New Roman", 11)).pack(pady=6)

    # ═══════════════════════════════════════════════════════
    # Генерація плану
    # ═══════════════════════════════════════════════════════
    def _generate(self):
        import random

        variants = [v.strip() for v in
                    self.var_text.get("1.0", "end").splitlines() if v.strip()]
        if len(variants) < 2:
            messagebox.showwarning("", "Введіть щонайменше 2 варіанти."); return

        try:
            reps = int(self._pv["reps"].get())
            seed = int(self._pv["seed"].get())
        except ValueError:
            messagebox.showwarning("", "Перевірте числові поля."); return

        cfg = self.CULTURES.get(self.culture_var.get(), {})
        is_garden = self._effective_is_garden()
        area_shortage = None

        # ── Параметри залежно від режиму ──────────────────────
        if is_garden:
            try:
                row_sp    = float(self._gv["row_sp"].get())
                plant_sp  = float(self._gv["plant_sp"].get())
                n_plot    = int(self._gv["plants_plot"].get())
                g_ends    = int(self._gv["guard_ends"].get())
                g_rows    = int(self._gv["guard_rows"].get())
            except ValueError:
                messagebox.showwarning("", "Перевірте параметри садіння."); return
            pw = row_sp; pl = plant_sp  # для сумісності
        else:
            size_mode = getattr(self, "_size_mode_var", None)
            size_mode = size_mode.get() if size_mode else "wh"
            try:
                if size_mode == "rep_area":
                    rep_area_target = float(self._pv["rep_area"].get())
                    pw = float(self._pv["pw_ra"].get())
                    if rep_area_target <= 0 or pw <= 0:
                        raise ValueError
                    k_tmp = len(variants)
                    pl = (rep_area_target / k_tmp) / pw
                    self._rep_area_result_lbl.configure(
                        text=f"→ Розрахована довжина ділянки: {pl:.2f} м "
                             f"(площа одної ділянки {pw*pl:.2f} м² × {k_tmp} варіантів "
                             f"= {pw*pl*k_tmp:.1f} м² на повторність)")
                else:
                    pw = float(self._pv["pw"].get())
                    pl = float(self._pv["pl"].get())
                border = float(self._pv["border"].get())
                buffer_between = float(self._pv["buffer"].get())
            except ValueError:
                messagebox.showwarning("", "Перевірте розміри ділянки."); return
            if border < 0 or buffer_between < 0:
                messagebox.showwarning("", "Захисна смуга й буфер не можуть бути від'ємними."); return
            net_w = pw - 2*border; net_l = pl - 2*border
            if net_w <= 0 or net_l <= 0:
                messagebox.showwarning("Захисна смуга завелика",
                    f"При захисній смузі {border} м з кожного боку на ділянці "
                    f"{pw:.2f}×{pl:.2f} м не лишається жодної облікової площі "
                    f"(потрібно, щоб ширина й довжина були більші за {2*border} м).\n\n"
                    "Зменшіть захисну смугу, збільшіть розмір ділянки, або — якщо "
                    "задаєте через площу повторності — збільшіть саму цю площу."); return
            row_sp = pw; plant_sp = pl  # для сумісності
            n_plot = 1; g_ends = 0; g_rows = 0

        design = self.design_var.get()
        rng = random.Random(seed)
        k = len(variants)

        if design == "latin" and k > 8:
            messagebox.showwarning("Латинський квадрат",
                f"Максимум 8 варіантів. У вас {k}."); return

        plan = []

        if design == "crd":
            all_p = variants * reps; rng.shuffle(all_p)
            for i, v in enumerate(all_p):
                plan.append({"plot": i+1, "rep": "–",
                             "variant": v, "row": i//k+1, "col": i%k+1})

        elif design == "rcbd":
            pn = 0
            for b in range(1, reps+1):
                bv = variants[:]; rng.shuffle(bv)
                for i, v in enumerate(bv):
                    pn += 1
                    plan.append({"plot": pn, "rep": f"Повт. {b}",
                                "variant": v, "row": b, "col": i+1})

        elif design == "latin":
            reps = k
            base = list(range(k))
            rows_p = [base[:]]
            for _ in range(k-1):
                rows_p.append(rows_p[-1][1:] + [rows_p[-1][0]])
            rng.shuffle(rows_p)
            cp = list(range(k)); rng.shuffle(cp)
            pn = 0
            for r in range(k):
                for c in range(k):
                    pn += 1
                    plan.append({"plot": pn, "rep": f"Рядок {r+1}",
                                "variant": variants[rows_p[r][cp[c]]],
                                "row": r+1, "col": c+1,
                                "col_label": f"Стовп. {c+1}"})

        elif design == "split":
            sp_vars = [v.strip() for v in
                       self.sp_text.get("1.0", "end").splitlines() if v.strip()]
            if len(sp_vars) < 2:
                messagebox.showwarning("", "Введіть щонайменше 2 sub-plot варіанти."); return
            pn = 0
            for b in range(1, reps+1):
                wp_o = variants[:]; rng.shuffle(wp_o)
                for wp in wp_o:
                    sp_o = sp_vars[:]; rng.shuffle(sp_o)
                    for sp in sp_o:
                        pn += 1
                        plan.append({"plot": pn, "rep": f"Повт. {b}",
                                    "variant": f"{wp} / {sp}",
                                    "wp": wp, "sp": sp, "row": b,
                                    "col": wp_o.index(wp)*len(sp_vars)+sp_o.index(sp)+1})

        design_name = {v: l for v, l, _ in self.DESIGNS}.get(design, design)

        # Розраховуємо площу
        if is_garden:
            plot_area = n_plot * row_sp * plant_sp
            total_area = plot_area * len(plan)
            area_msg = (f"Облікових рослин/ділянку: {n_plot}\n"
                       f"Схема садіння: {row_sp}×{plant_sp} м\n"
                       f"Площа ділянки: {plot_area:.1f} м²\n"
                       f"Загальна площа (облікова): {total_area:.0f} м²")
        else:
            plot_area_gross = pw * pl
            plot_area_net = net_w * net_l
            n_plots = len(plan)
            # Буфер рахуємо як смугу шириною buffer_between довкола кожної
            # ділянки, поділену навпіл (щоб не подвоювати спільний прохід
            # між двома сусідніми ділянками) — практична оцінка знизу.
            buffer_area = n_plots * (2*(pw+pl)*buffer_between + 4*buffer_between**2) / 2
            total_area = plot_area_gross * n_plots + buffer_area
            area_msg = (f"Посівна площа ділянки: {pw:.2f}×{pl:.2f} м = {plot_area_gross:.1f} м²\n"
                       f"Облікова площа ділянки (за вирахуванням захисної смуги "
                       f"{border} м): {net_w:.2f}×{net_l:.2f} м = {plot_area_net:.1f} м²\n"
                       f"Орієнтовна загальна площа поля (з буферами {buffer_between} м "
                       f"між ділянками): {total_area:.0f} м²")

            # Чесна перевірка проти доступної площі, якщо вказана
            avail_txt = self._pv.get("avail_area", tk.StringVar(value="")).get().strip()
            area_shortage = None
            if avail_txt:
                try:
                    avail_area = float(avail_txt)
                    if avail_area > 0 and total_area > avail_area:
                        area_shortage = total_area - avail_area
                        area_msg += (f"\n\n⚠ НЕДОСТАТНЬО ПЛОЩІ: потрібно {total_area:.0f} м², "
                                    f"доступно {avail_area:.0f} м² — бракує "
                                    f"{area_shortage:.0f} м² ({area_shortage/avail_area*100:.0f}%).")
                    elif avail_area > 0:
                        area_msg += (f"\n\n✓ Доступної площі ({avail_area:.0f} м²) достатньо "
                                    f"(запас {avail_area-total_area:.0f} м²).")
                except ValueError:
                    pass

        self._plan_data = {
            "plan": plan, "variants": variants, "reps": reps,
            "design": design, "design_name": design_name,
            "seed": seed, "k": k, "pw": pw, "pl": pl,
            "is_garden": is_garden,
            "row_sp": row_sp if is_garden else pw,
            "plant_sp": plant_sp if is_garden else pl,
            "n_plot": n_plot, "g_ends": g_ends, "g_rows": g_rows,
            "border": border if not is_garden else 0,
            "buffer_between": buffer_between if not is_garden else 0,
            "culture": self.culture_var.get(),
            "unit": cfg.get("unit", "ділянка"),
            "name": self._nv["name"].get(),
            "year": self._nv["year"].get(),
            "loc":  self._nv["loc"].get(),
            "resp": self._nv["resp"].get(),
        }

        self._draw_scheme()
        self._fill_rand()
        self._fill_journal()
        self.nb.select(0)

        summary = (f"Дизайн: {design_name}\n"
                  f"Варіантів: {k}   |   Повторностей: {reps}\n"
                  f"Ділянок: {len(plan)}\n"
                  f"{area_msg}\n\n"
                  f"Seed рандомізації: {seed}\n"
                  f"⚠ Збережіть seed у документацію!")

        if not is_garden and area_shortage is not None:
            messagebox.showwarning("⚠ План згенеровано, але площі бракує",
                f"План технічно згенеровано, але:\n\n{summary}\n\n"
                "Перегляньте параметри — зменшіть розмір ділянки/повторності, "
                "кількість повторень, або знайдіть більшу площу під дослід.")
        else:
            messagebox.showinfo("Готово", f"План згенеровано!\n\n{summary}")
    # ═══════════════════════════════════════════════════════
    # Польова схема
    # ═══════════════════════════════════════════════════════
    def _export_to_journal(self):
        """Перетворює вже згенерований план на файл .sadp — той самий
        формат, що зберігає конструктор схеми, — щоб його можна було
        одразу відкрити «Польовим журналом обліків»: вносити дані,
        зберігати по роках, використовувати «Відкрити показник» у
        будь-якому аналізі."""
        if not self._plan_data:
            messagebox.showwarning("", "Спочатку згенеруйте план."); return
        d = self._plan_data
        plan = d["plan"]; design = d["design"]; is_garden = d["is_garden"]

        # ── Номер повторності для кожного запису плану ──────
        # RCBD і Split-plot: номер блоку (row) — і Є номером повторності.
        # CRD і Латинський квадрат: блоків немає — повторність варіанту
        # визначаємо за порядком появи цього варіанту в плані (k-та
        # поява варіанту = k-та повторність саме цього варіанту).
        rep_of = {}
        if design in ("rcbd", "split"):
            for p in plan: rep_of[id(p)] = p["row"]
        else:
            seen = {}
            for p in plan:
                key = p["variant"]
                seen[key] = seen.get(key, 0) + 1
                rep_of[id(p)] = seen[key]

        if not is_garden:
            # Польові культури: одна ділянка = одна облікова позиція.
            # Захист уже врахований як ПЛОЩА (захисна смуга й буфер),
            # тому окремих захисних позицій у сітці не потрібно.
            plants = []
            for p in plan:
                hp = HPPlant(p["row"], p["col"], None, "ok")
                hp.role = HP_ROLE_RECORDED
                hp.replication = rep_of[id(p)]
                if design == "split":
                    hp.factors = {"Головний фактор": p["wp"], "Підфактор": p["sp"]}
                else:
                    hp.variant = d["variants"].index(p["variant"]) + 1
                plants.append(hp)
            is_multi = (design == "split")
            if design == "split":
                factor_defs = [
                    {"name": "Головний фактор",
                     "levels": list(dict.fromkeys(pp["wp"] for pp in plan))},
                    {"name": "Підфактор",
                     "levels": list(dict.fromkeys(pp["sp"] for pp in plan))}]
                variant_names = []
            else:
                factor_defs = []
                variant_names = d["variants"]
        else:
            # Садові культури: ділянка = кілька облікових рослин одного
            # варіанту в ряду, із захисними рослинами на краях ряду і
            # захисними рядами між повтореннями (той самий принцип, що
            # й у плануванні за однорідністю).
            n_plot = d["n_plot"]; g_ends = d["g_ends"]; g_rows = d["g_rows"]
            by_row = {}
            for p in plan: by_row.setdefault(p["row"], []).append(p)
            row_keys_sorted = sorted(by_row.keys())

            plants = []
            out_row = 0
            for row_num in row_keys_sorted:
                out_row += 1
                plots_in_row = sorted(by_row[row_num], key=lambda pp: pp["col"])
                pos = 0
                for _ in range(g_ends):
                    pos += 1
                    hp = HPPlant(out_row, pos, None, "ok"); hp.role = HP_ROLE_GUARD_EDGE
                    plants.append(hp)
                for p in plots_in_row:
                    for _ in range(n_plot):
                        pos += 1
                        hp = HPPlant(out_row, pos, None, "ok")
                        hp.role = HP_ROLE_RECORDED
                        hp.variant = d["variants"].index(p["variant"]) + 1
                        hp.replication = rep_of[id(p)]
                        plants.append(hp)
                for _ in range(g_ends):
                    pos += 1
                    hp = HPPlant(out_row, pos, None, "ok"); hp.role = HP_ROLE_GUARD_EDGE
                    plants.append(hp)
                if row_num != row_keys_sorted[-1]:
                    for _ in range(g_rows):
                        out_row += 1
                        for gp in range(1, pos+1):
                            hp = HPPlant(out_row, gp, None, "ok")
                            hp.role = HP_ROLE_GUARD_EDGE
                            plants.append(hp)
            is_multi = False
            factor_defs = []
            variant_names = d["variants"]

        scheme_type = "multi_factor_scheme" if is_multi else "homogeneous_plot_scheme"
        design_used = design if design in ("rcbd","crd","latin") else "custom"
        dd = {
            "type": scheme_type, "version": APP_VER,
            "cfg": {"trait_name": d.get("name",""), "trait_unit": "",
                    "design_used": design_used},
            "factor_defs": factor_defs,
            "variant_names": variant_names,
            "plants": [{"row": p.row, "position": p.position, "value": p.value,
                       "status": p.status, "role": p.role, "plot_id": p.plot_id,
                       "variant": p.variant, "replication": p.replication,
                       "factors": p.factors} for p in plants],
        }
        default_name = "схема_" + (d.get("name") or d.get("culture","дослід")
                                   ).replace(" ","_")[:40] + ".sadp"
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".sadp", initialfile=default_name,
            filetypes=[("SAD схема","*.sadp"),("JSON","*.json")],
            title="Зберегти схему для польового журналу")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dd, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("Збережено",
                f"Схему збережено:\n{path}\n\n"
                "Тепер її можна відкрити в «Польовому журналі обліків» — "
                "вносити виміряні значення, зберігати по роках, і напряму "
                "передавати в будь-який аналіз через «Відкрити показник».")
        except Exception as ex:
            messagebox.showerror("Помилка збереження", str(ex))

    def _draw_scheme(self):
        if not self._plan_data: return
        cv = self._scheme_cv; cv.delete("all")
        d = self._plan_data; plan = d["plan"]
        is_garden = d.get("is_garden", False)

        if is_garden:
            self._draw_scheme_garden(cv, d, plan)
        else:
            self._draw_scheme_field(cv, d, plan)

    def _draw_scheme_field(self, cv, d, plan):
        """Польова схема — кожна клітинка = ділянка. Внутрішній прямокутник
        (темніший контур) — облікова площа; світла смуга по периметру —
        захисна зона; проміжок між клітинками — буфер між ділянками."""
        PALETTES = ["#aed6f1","#a9dfbf","#f9e79f","#f1948a","#d2b4de",
                    "#a3e4d7","#fad7a0","#d5d8dc","#82e0aa","#f0b27a",
                    "#85c1e9","#f7dc6f","#c39bd3","#76d7c4","#f8c471"]
        all_v = list(dict.fromkeys(p["variant"] for p in plan))
        cmap  = {v: PALETTES[i % len(PALETTES)] for i, v in enumerate(all_v)}
        cols_set = sorted(set(p["col"] for p in plan))
        rows_set = sorted(set(p["row"] for p in plan))
        nc = len(cols_set); nr = len(rows_set)
        cw = max(78, min(130, 680 // nc))
        ch = max(44, min(72,  400 // nr))
        border = d.get("border", 0); buf = d.get("buffer_between", 0)
        pw = d.get("pw", 1) or 1; pl = d.get("pl", 1) or 1
        # Проміжок між клітинками масштабується відносно розміру ділянки,
        # щоб при більшому буфері відносно ділянки розрив був помітнішим.
        pad = max(5, min(24, int(cw * (buf / max(pw, 0.1)) * 1.5)))
        # Товщина видимої захисної смуги всередині клітинки (пропорційно).
        bshare = min(0.35, (border / max(pw, 0.1))) if pw > 0 else 0
        bpix_w = int((cw - pad) * bshare); bpix_h = int((ch - pad) * bshare)
        x0 = 110; y0 = 55

        title = d.get("name") or "План досліду"
        sub   = f"{d.get('culture','')}  |  {d['design_name']}  |  Seed={d['seed']}  |  {d.get('year','')}"
        cv.create_text(x0+nc*cw//2, 16, text=title,
                       font=("Times New Roman",12,"bold"), fill="#000")
        cv.create_text(x0+nc*cw//2, 34, text=sub,
                       font=("Times New Roman",9), fill="#555")
        if border > 0 or buf > 0:
            cv.create_text(x0+nc*cw//2, 46,
                text=f"Захисна смуга: {border} м по периметру  |  Буфер між ділянками: {buf} м",
                font=("Times New Roman",8), fill="#8c5a1a")

        rep_map = {}
        for p in plan: rep_map[p["row"]] = p["rep"]
        for i, r in enumerate(rows_set):
            cv.create_text(x0-6, y0+i*ch+ch//2,
                           text=rep_map.get(r, f"Ряд {r}"),
                           anchor="e", font=("Times New Roman",9,"bold"), fill="#333")
        for j, c in enumerate(cols_set):
            lbl = next((p for p in plan if p["col"]==c), {}).get("col_label", f"#{c}")
            cv.create_text(x0+j*cw+cw//2, y0-14,
                           text=lbl, font=("Times New Roman",8), fill="#555")
        for p in plan:
            ci = cols_set.index(p["col"]); ri = rows_set.index(p["row"])
            x1,y1 = x0+ci*cw, y0+ri*ch; x2,y2 = x1+cw-pad, y1+ch-pad
            color = cmap.get(p["variant"],"#eee")
            # Зовнішній прямокутник — уся посівна площа (світліший, це і є
            # захисна смуга — вона проглядає з-під внутрішнього обліку).
            cv.create_rectangle(x1,y1,x2,y2, fill=color, outline="#888", width=1)
            if bpix_w > 0 or bpix_h > 0:
                cv.create_rectangle(x1+bpix_w,y1+bpix_h,x2-bpix_w,y2-bpix_h,
                                    fill=color, outline="#555", width=2, dash=(3,2))
            cv.create_text(x1+5,y1+6, text=f"№{p['plot']}",
                           anchor="nw", font=("Courier New",7), fill="#555")
            short = p["variant"][:14]+"…" if len(p["variant"])>14 else p["variant"]
            cv.create_text((x1+x2)//2,(y1+y2)//2, text=short,
                           font=("Times New Roman",8), fill="#000", width=cw-10)

        leg_y = y0+nr*ch+16
        cv.create_text(x0, leg_y, text="Легенда:",
                       anchor="w", font=("Times New Roman",10,"bold"))
        if border > 0:
            cv.create_text(x0+120, leg_y,
                           text="(пунктир — межа облікової площі)",
                           anchor="w", font=("Times New Roman",8), fill="#555")
        cpr = 3
        for i,v in enumerate(all_v):
            lx = x0+(i%cpr)*240; ly = leg_y+18+(i//cpr)*20
            cv.create_rectangle(lx,ly,lx+13,ly+13, fill=cmap[v], outline="#888")
            cv.create_text(lx+17,ly+7, text=v, anchor="w", font=("Times New Roman",9))

        tot_w = x0+nc*cw+20
        tot_h = leg_y+22*(len(all_v)//cpr+2)+10
        cv.configure(scrollregion=(0,0,tot_w,tot_h))

    def _draw_scheme_garden(self, cv, d, plan):
        """
        Садівнича схема — кожна клітинка = одна рослина.
        Захисні рослини на початку/кінці ряду — сірі.
        Захисні ряди між повторностями — штриховані.
        """
        PALETTES = ["#aed6f1","#a9dfbf","#f9e79f","#f1948a","#d2b4de",
                    "#a3e4d7","#fad7a0","#d5d8dc","#82e0aa","#f0b27a",
                    "#85c1e9","#f7dc6f","#c39bd3","#76d7c4","#f8c471"]
        GUARD_COLOR  = "#d0d0d0"   # захисні рослини
        GUARD_STIPPLE = "gray50"   # захисний ряд (штрих)

        all_v = list(dict.fromkeys(p["variant"] for p in plan))
        cmap  = {v: PALETTES[i % len(PALETTES)] for i, v in enumerate(all_v)}

        n_plot   = d.get("n_plot", 5)
        g_ends   = d.get("g_ends", 1)
        g_rows   = d.get("g_rows", 1)
        reps     = d.get("reps",   3)
        k        = d.get("k",      4)   # кількість варіантів
        design   = d.get("design", "rcbd")
        row_sp   = d.get("row_sp",  4.0)
        plant_sp = d.get("plant_sp",5.0)
        unit     = d.get("unit",   "дерево")

        # Загальна кількість рослин у ряду:
        # захисні_поч + [варіант_1 ... варіант_k] (повторяється n_plot) + захисні_кін
        # Для RCBD: 1 ряд = 1 повторність = k варіантів × n_plot рослин
        total_plants_row = g_ends + k * n_plot + g_ends
        # Рядів на схемі: reps повторностей + (reps-1)*g_rows захисних рядів
        total_rows = reps + (reps - 1) * g_rows

        # Розмір клітинки
        cw = max(28, min(60, 700 // total_plants_row))
        ch = max(28, min(55, 500 // total_rows))
        pad = 3; x0 = 120; y0 = 70

        # Заголовок
        title = d.get("name") or "Садівничий дослід"
        sub   = (f"{d.get('culture','')}  |  {d['design_name']}  |  "
                 f"Схема: {row_sp}×{plant_sp} м  |  "
                 f"Рослин/ділянку: {n_plot}  |  Seed={d['seed']}")
        cv.create_text(x0 + total_plants_row*cw//2, 18,
                       text=title, font=("Times New Roman",12,"bold"), fill="#000")
        cv.create_text(x0 + total_plants_row*cw//2, 36,
                       text=sub, font=("Times New Roman",9), fill="#555")

        # Мітки колонок (позиції рослин)
        for ci in range(total_plants_row):
            if ci < g_ends or ci >= total_plants_row - g_ends:
                lbl = "З"   # Захисна
            else:
                pos = ci - g_ends
                var_idx = pos // n_plot
                plant_in_var = pos % n_plot + 1
                lbl = f"#{plant_in_var}"
            cv.create_text(x0+ci*cw+cw//2, y0-14,
                           text=lbl, font=("Times New Roman",7), fill="#777")

        # Рядки (повторності + захисні ряди)
        row_screen = 0   # лічильник рядків на екрані
        for rep_idx in range(reps):
            # Мітка повторності
            row_y = y0 + row_screen * ch
            cv.create_text(x0-6, row_y+ch//2,
                           text=f"Повт.{rep_idx+1}",
                           anchor="e", font=("Times New Roman",8,"bold"), fill="#333")

            # Беремо план для цієї повторності
            rep_plan = [p for p in plan if p["row"] == rep_idx+1]
            # Будуємо порядок варіантів у ряду
            col_to_var = {p["col"]: p["variant"] for p in rep_plan}

            # Малюємо рослини в ряду
            for ci in range(total_plants_row):
                x1 = x0 + ci * cw; y1 = row_y
                x2 = x1 + cw - pad; y2 = y1 + ch - pad

                if ci < g_ends or ci >= total_plants_row - g_ends:
                    # Захисна рослина на початку/кінці
                    cv.create_oval(x1+2, y1+2, x2-2, y2-2,
                                   fill=GUARD_COLOR, outline="#999", width=1)
                    cv.create_text((x1+x2)//2, (y1+y2)//2,
                                   text="З", font=("Times New Roman",7), fill="#888")
                else:
                    pos = ci - g_ends
                    var_col = pos // n_plot + 1  # номер варіанту (стовпець)
                    variant = col_to_var.get(var_col, "")
                    color = cmap.get(variant, "#eee")
                    # Коло = дерево/кущ
                    cv.create_oval(x1+2, y1+2, x2-2, y2-2,
                                   fill=color, outline="#666", width=1)
                    plant_in_var = pos % n_plot + 1
                    cv.create_text((x1+x2)//2, (y1+y2)//2,
                                   text=str(plant_in_var),
                                   font=("Times New Roman",7), fill="#000")

            row_screen += 1

            # Захисні ряди між повторностями
            if rep_idx < reps - 1:
                for gr in range(g_rows):
                    gy = y0 + row_screen * ch
                    cv.create_text(x0-6, gy+ch//2,
                                   text="Захисний", anchor="e",
                                   font=("Times New Roman",7,"italic"), fill="#aaa")
                    for ci in range(total_plants_row):
                        x1 = x0+ci*cw; y1 = gy
                        x2 = x1+cw-pad; y2 = y1+ch-pad
                        cv.create_oval(x1+2, y1+2, x2-2, y2-2,
                                       fill="#e8e8e8", outline="#bbb",
                                       width=1, stipple=GUARD_STIPPLE
                                       if GUARD_STIPPLE else "")
                    row_screen += 1

        # Роздільники між варіантами у рядку (вертикальні лінії)
        for var_i in range(k+1):
            lx = x0 + (g_ends + var_i * n_plot) * cw
            cv.create_line(lx, y0-5, lx, y0+reps*ch + (reps-1)*g_rows*ch + 5,
                           fill="#1a4b8c", width=1, dash=(4,3))

        # Легенда варіантів
        leg_y = y0 + total_rows * ch + 20
        cv.create_text(x0, leg_y, text="Легенда (варіанти):",
                       anchor="w", font=("Times New Roman",10,"bold"))
        cpr = 3
        for i, v in enumerate(all_v):
            lx = x0 + (i%cpr)*260; ly = leg_y+18+(i//cpr)*22
            cv.create_oval(lx, ly, lx+14, ly+14, fill=cmap[v], outline="#666")
            cv.create_text(lx+18, ly+7, text=v, anchor="w",
                           font=("Times New Roman",9))

        leg_y2 = leg_y + 18 + ((len(all_v)-1)//cpr+1)*22 + 8
        # Пояснення символів
        cv.create_oval(x0, leg_y2, x0+14, leg_y2+14,
                       fill=GUARD_COLOR, outline="#999")
        cv.create_text(x0+18, leg_y2+7,
                       text="З — захисна рослина (не обліковується)",
                       anchor="w", font=("Times New Roman",9), fill="#666")
        cv.create_oval(x0, leg_y2+20, x0+14, leg_y2+34,
                       fill="#e8e8e8", outline="#bbb")
        cv.create_text(x0+18, leg_y2+27,
                       text="Захисний ряд між повторностями",
                       anchor="w", font=("Times New Roman",9), fill="#666")
        # Схема садіння
        cv.create_text(x0, leg_y2+50,
                       text=f"Схема садіння: {row_sp} м × {plant_sp} м  |  "
                            f"Облікових {unit}/ділянку: {n_plot}  |  "
                            f"Захисних з кожного боку: {g_ends}",
                       anchor="w", font=("Times New Roman",9), fill="#333")

        tot_w = x0 + total_plants_row*cw + 20
        tot_h = leg_y2 + 70
        cv.configure(scrollregion=(0, 0, tot_w, tot_h))

    # ═══════════════════════════════════════════════════════
    # Список рандомізації
    # ═══════════════════════════════════════════════════════
    def _fill_rand(self):
        if not self._plan_data: return
        d = self._plan_data; plan = d["plan"]
        self.rand_txt.configure(state="normal")
        self.rand_txt.delete("1.0", tk.END)
        lines = [
            "═"*62,
            "     СПИСОК РАНДОМІЗАЦІЇ ПОЛЬОВОГО ДОСЛІДУ",
            "═"*62,
            f"  Назва:          {d.get('name') or '—'}",
            f"  Рік:            {d.get('year','')}",
            f"  Місце:          {d.get('loc') or '—'}",
            f"  Відповідальний: {d.get('resp') or '—'}",
            f"  Культура:       {d.get('culture','')}",
            f"  Дизайн:         {d['design_name']}",
            f"  Варіантів:      {d['k']}",
            f"  Повторностей:   {d['reps']}",
            f"  Ділянок:        {len(plan)}",
            f"  Площа ділянки:  {d['pw']} × {d['pl']} м = {d['pw']*d['pl']:.1f} м²",
            f"  Загальна площа: {d['pw']*d['pl']*len(plan):.0f} м²",
            f"  Seed рандом.:   {d['seed']}  ← зберігайте цей номер!",
            "─"*62,
            f"  {'№':<6}  {'Повторність':<16}  Варіант",
            "─"*62,
        ]
        for p in sorted(plan, key=lambda x: x["plot"]):
            lines.append(f"  {p['plot']:<6}  {p['rep']:<16}  {p['variant']}")
        lines += [
            "─"*62,
            f"  Сформовано: {datetime.now().strftime('%d.%m.%Y  %H:%M')}",
        ]
        self.rand_txt.insert("1.0", "\n".join(lines))
        self.rand_txt.configure(state="disabled")

    # ═══════════════════════════════════════════════════════
    # Польовий журнал
    # ═══════════════════════════════════════════════════════
    def _fill_journal(self):
        if not self._plan_data: return
        d    = self._plan_data
        plan = d["plan"]
        is_garden = d.get("is_garden", False)
        n_plot    = d.get("n_plot", 1) if is_garden else 1
        unit      = d.get("unit", "ділянка")

        ind_text   = self.ind_var.get().strip()
        indicators = [s.strip() for s in ind_text.split(";") if s.strip()]
        if not indicators:
            indicators = ["Показник 1","Показник 2","Показник 3","Показник 4"]

        # Зберігаємо поточні назви заголовків для перейменування
        if not hasattr(self, '_ind_vars'):
            self._ind_vars = {}
        self._cur_indicators = indicators[:]

        for item in self.journal_tv.get_children():
            self.journal_tv.delete(item)

        # Стиль Treeview — чіткі межі
        style = ttk.Style()
        style.configure("Journal.Treeview",
                        rowheight=22,
                        font=("Times New Roman",10),
                        borderwidth=1)
        style.configure("Journal.Treeview.Heading",
                        font=("Times New Roman",10,"bold"),
                        background="#1a4b8c",
                        foreground="white",
                        relief="flat")
        style.map("Journal.Treeview.Heading",
                  background=[("active","#2a5ba8")])
        self.journal_tv.configure(style="Journal.Treeview")

        if is_garden:
            cols = ("№ діл.", "Повт.", f"{unit.capitalize()} №",
                    "Варіант") + tuple(indicators) + ("Примітки",)
        else:
            cols = ("№ діл.", "Повторність",
                    "Варіант") + tuple(indicators) + ("Примітки",)

        self.journal_tv["columns"] = cols
        self.journal_tv["show"]    = "headings"

        w_map = {"№ діл.":55, "Повт.":70, "Повторність":110,
                 f"{unit.capitalize()} №":70, "Варіант":160, "Примітки":100}
        for col in cols:
            self.journal_tv.heading(col, text=col)
            w = w_map.get(col, 100)
            self.journal_tv.column(col, width=w, minwidth=40,
                                   anchor="center" if w<130 else "w",
                                   stretch=True)

        # Подвійний клік на заголовок — перейменування показника
        def _on_heading_dbl(event):
            region = self.journal_tv.identify_region(event.x, event.y)
            if region != "heading": return
            col_id = self.journal_tv.identify_column(event.x)
            col_n  = int(col_id[1:]) - 1  # 0-based
            cur_name = cols[col_n]
            # Лише показники (не службові колонки)
            fixed = (3 if is_garden else 2) + 1  # перші fixed колонок - службові
            if col_n < fixed: return

            ind_idx = col_n - fixed
            if ind_idx >= len(indicators): return

            dlg = tk.Toplevel(self.win); dlg.title("Перейменувати показник")
            dlg.resizable(False,False); dlg.grab_set(); set_icon(dlg)
            tk.Label(dlg, text="Нова назва показника:",
                     font=("Times New Roman",12)).pack(padx=16, pady=(14,4))
            tv2 = tk.StringVar(value=cur_name)
            e = tk.Entry(dlg, textvariable=tv2,
                         font=("Times New Roman",12), width=28)
            e.pack(padx=16, pady=4)
            e.select_range(0, tk.END); e.focus_set()
            def _ok():
                nm = tv2.get().strip()
                if nm:
                    indicators[ind_idx] = nm
                    # Оновити поле indicators
                    self.ind_var.set("; ".join(indicators))
                    dlg.destroy()
                    self._fill_journal()
            tk.Button(dlg, text="ОК", bg="#c62828", fg="white",
                      font=("Times New Roman",12), command=_ok
                      ).pack(pady=(4,14))
            dlg.bind("<Return>", lambda e2: _ok())
            center_win(dlg)

        self.journal_tv.bind("<Double-1>", _on_heading_dbl)

        # Теги для чергування рядків
        self.journal_tv.tag_configure("even", background="#f0f4ff")
        self.journal_tv.tag_configure("odd",  background="#ffffff")

        row_i = 0
        for p in sorted(plan, key=lambda x: x["plot"]):
            if is_garden:
                # Кожна облікова рослина — окремий рядок
                for plant_n in range(1, n_plot + 1):
                    tag = "even" if row_i % 2 == 0 else "odd"
                    vals = (p["plot"], p["rep"], plant_n,
                            p["variant"]) + tuple("" for _ in indicators) + ("",)
                    self.journal_tv.insert("", "end", values=vals, tags=(tag,))
                    row_i += 1
            else:
                tag = "even" if row_i % 2 == 0 else "odd"
                vals = (p["plot"], p["rep"],
                        p["variant"]) + tuple("" for _ in indicators) + ("",)
                self.journal_tv.insert("", "end", values=vals, tags=(tag,))
                row_i += 1

    def _refresh_journal(self):
        if not self._plan_data:
            messagebox.showwarning("","Спочатку згенеруйте план."); return
        self._fill_journal()

    # ═══════════════════════════════════════════════════════
    # Збереження
    # ═══════════════════════════════════════════════════════
    def _save_rand_txt(self):
        if not self._plan_data:
            messagebox.showwarning("","Спочатку згенеруйте план."); return
        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".txt",
            filetypes=[("Текстовий файл","*.txt")],
            title="Зберегти список рандомізації")
        if not path: return
        try:
            with open(path,"w",encoding="utf-8") as f:
                f.write(self.rand_txt.get("1.0",tk.END))
            messagebox.showinfo("Збережено",f"Збережено:\n{path}")
        except Exception as ex:
            messagebox.showerror("Помилка",str(ex))

    def _save_excel(self):
        if not self._plan_data:
            messagebox.showwarning("","Спочатку згенеруйте план."); return
        if not HAS_OPENPYXL:
            messagebox.showerror("","Потрібен openpyxl: pip install openpyxl"); return

        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".xlsx",
            filetypes=[("Excel","*.xlsx")],
            title="Зберегти польовий журнал")
        if not path: return

        try:
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            d  = self._plan_data; plan = d["plan"]
            ind_text   = self.ind_var.get().strip()
            indicators = [s.strip() for s in ind_text.split(";") if s.strip()]
            if not indicators:
                indicators = ["Показник 1","Показник 2","Показник 3","Показник 4"]

            wb  = openpyxl.Workbook()
            hfill = PatternFill("solid", fgColor="1A4B8C")
            hfont = Font(color="FFFFFF", bold=True,
                         name="Times New Roman", size=11)
            nfont = Font(name="Times New Roman", size=11)
            bfont = Font(name="Times New Roman", size=11, bold=True)
            ca    = Alignment(horizontal="center", vertical="center",
                              wrap_text=True)
            thin  = Side(style="thin", color="AAAAAA")
            brd   = Border(left=thin, right=thin, top=thin, bottom=thin)

            is_garden = d.get("is_garden", False)
            n_plot    = d.get("n_plot", 1) if is_garden else 1
            unit      = d.get("unit", "ділянка")

            # ── Лист 1: Польовий журнал ─────────────────────
            ws = wb.active; ws.title = "Польовий журнал"

            # Шапка
            if is_garden:
                info_rows = [
                    "ПОЛЬОВИЙ ЖУРНАЛ СПОСТЕРЕЖЕНЬ",
                    f"Дослід: {d.get('name') or '—'}",
                    f"Рік: {d.get('year','')}    Місце: {d.get('loc') or '—'}    Відповідальний: {d.get('resp') or '—'}",
                    f"Культура: {d.get('culture','')}    Дизайн: {d['design_name']}",
                    f"Варіантів: {d['k']}    Повторностей: {d['reps']}    "
                    f"Облікових {unit}/ділянку: {n_plot}    "
                    f"Схема: {d.get('row_sp','?')}×{d.get('plant_sp','?')} м    "
                    f"Захисних: {d.get('g_ends',0)} з кожного боку",
                ]
            else:
                border_txt = (f"    Захисна смуга: {d.get('border',0)} м    "
                             f"Буфер між ділянками: {d.get('buffer_between',0)} м"
                             if d.get('border',0) or d.get('buffer_between',0) else "")
                info_rows = [
                    "ПОЛЬОВИЙ ЖУРНАЛ СПОСТЕРЕЖЕНЬ",
                    f"Дослід: {d.get('name') or '—'}",
                    f"Рік: {d.get('year','')}    Місце: {d.get('loc') or '—'}    Відповідальний: {d.get('resp') or '—'}",
                    f"Культура: {d.get('culture','')}    Дизайн: {d['design_name']}    "
                    f"Варіантів: {d['k']}    Повторностей: {d['reps']}    "
                    f"Ділянок: {len(plan)}    Площа: {d['pw']}×{d['pl']} м{border_txt}",
                ]
            for ri, txt in enumerate(info_rows, 1):
                c = ws.cell(ri, 1, txt)
                c.font = bfont if ri == 1 else nfont

            # Таблиця журналу
            hr = len(info_rows) + 2
            if is_garden:
                j_hdrs = ["№ діл.", "Повт.", f"{unit.capitalize()} №", "Варіант"] + indicators + ["Примітки"]
            else:
                j_hdrs = ["№ ділянки","Повторність","Варіант"] + indicators + ["Примітки"]

            for ci, h in enumerate(j_hdrs, 1):
                c = ws.cell(hr, ci, h)
                c.fill = hfill; c.font = hfont
                c.alignment = ca; c.border = brd

            PALETTES_HEX = ["AED6F1","A9DFBF","F9E79F","F1948A","D2B4DE",
                            "A3E4D7","FAD7A0","D5D8DC","82E0AA","F0B27A"]
            all_v = list(dict.fromkeys(p["variant"] for p in plan))
            vcols = {v: PALETTES_HEX[i % len(PALETTES_HEX)]
                     for i, v in enumerate(all_v)}

            row_excel = hr + 1
            row_i = 0
            for p in sorted(plan, key=lambda x: x["plot"]):
                if is_garden:
                    for plant_n in range(1, n_plot + 1):
                        even = row_i % 2 == 0
                        rfill = PatternFill("solid", fgColor="EEF4FF" if even else "FFFFFF")
                        vals = [p["plot"], p["rep"], plant_n, p["variant"]] + [""] * len(indicators) + [""]
                        for ci, val in enumerate(vals, 1):
                            c = ws.cell(row_excel, ci, val)
                            c.font = nfont; c.alignment = ca; c.border = brd
                            if ci <= 4 and even: c.fill = rfill
                        row_excel += 1; row_i += 1
                else:
                    even = row_i % 2 == 0
                    rfill = PatternFill("solid", fgColor="EEF4FF" if even else "FFFFFF")
                    vals = [p["plot"], p["rep"], p["variant"]] + [""] * len(indicators) + [""]
                    for ci, val in enumerate(vals, 1):
                        c = ws.cell(row_excel, ci, val)
                        c.font = nfont; c.alignment = ca; c.border = brd
                        if ci <= 3 and even: c.fill = rfill
                    row_excel += 1; row_i += 1

            # Ширини стовпців
            w_cols = ([8, 10, 10, 32] if is_garden else [9, 14, 32]) + [14]*len(indicators) + [16]
            for ci, w in enumerate(w_cols, 1):
                if ci <= 26:
                    ws.column_dimensions[chr(64+ci)].width = w
            ws.row_dimensions[hr].height = 30

            # ── Лист 2: Рандомізація ────────────────────────
            ws2 = wb.create_sheet("Рандомізація")
            r_hdrs = ["№ ділянки","Повторність","Варіант"]
            for ci, h in enumerate(r_hdrs, 1):
                c = ws2.cell(1, ci, h)
                c.fill = hfill; c.font = hfont
                c.alignment = ca; c.border = brd
            for ri, p in enumerate(sorted(plan, key=lambda x: x["plot"])):
                row = 2 + ri
                fc = PatternFill("solid",
                                 fgColor=vcols.get(p["variant"],"EEEEEE"))
                for ci, val in enumerate(
                    [p["plot"], p["rep"], p["variant"]], 1
                ):
                    c = ws2.cell(row, ci, val)
                    c.font = nfont; c.alignment = ca; c.border = brd
                    if ci == 3: c.fill = fc
            for ci, w in zip([1,2,3],[9,14,36]):
                ws2.column_dimensions[chr(64+ci)].width = w

            wb.save(path)
            messagebox.showinfo("Збережено",
                f"Збережено:\n{path}\n\n"
                "Лист 1 — Польовий журнал\n"
                "Лист 2 — Рандомізація")
        except Exception as ex:
            messagebox.showerror("Помилка збереження", str(ex))

    def _save_png(self):
        if not self._plan_data:
            messagebox.showwarning("","Спочатку згенеруйте план."); return
        if not HAS_MPL:
            messagebox.showwarning("","matplotlib недоступний."); return

        path = filedialog.asksaveasfilename(
            parent=self.win, defaultextension=".png",
            filetypes=[("PNG зображення","*.png")],
            title="Зберегти схему як PNG")
        if not path: return

        d  = self._plan_data; plan = d["plan"]
        all_v = list(dict.fromkeys(p["variant"] for p in plan))
        PALETTES = ["#aed6f1","#a9dfbf","#f9e79f","#f1948a","#d2b4de",
                    "#a3e4d7","#fad7a0","#d5d8dc","#82e0aa","#f0b27a"]
        cmap = {v: PALETTES[i%len(PALETTES)] for i,v in enumerate(all_v)}

        cols_set = sorted(set(p["col"] for p in plan))
        rows_set = sorted(set(p["row"] for p in plan))
        nc = len(cols_set); nr = len(rows_set)

        fig = Figure(figsize=(max(10, nc*1.6+2), max(5, nr*1.1+3)), dpi=130)
        ax  = fig.add_axes([0.09, 0.16, 0.88, 0.72])
        ax.set_xlim(0, nc); ax.set_ylim(0, nr); ax.set_aspect("equal")
        ax.axis("off")

        rep_map = {}
        for p in plan: rep_map[rows_set.index(p["row"])] = p["rep"]

        # Ділянки
        for p in plan:
            ci = cols_set.index(p["col"])
            ri = rows_set.index(p["row"])
            rect = matplotlib.patches.FancyBboxPatch(
                (ci+0.04, nr-ri-0.95), 0.91, 0.89,
                boxstyle="round,pad=0.02",
                facecolor=cmap.get(p["variant"],"#eee"),
                edgecolor="#777", linewidth=0.7)
            ax.add_patch(rect)
            short = (p["variant"][:13]+"…"
                     if len(p["variant"]) > 13 else p["variant"])
            ax.text(ci+0.5, nr-ri-0.5, short, ha="center", va="center",
                    fontsize=6.5, fontfamily="Times New Roman")
            ax.text(ci+0.07, nr-ri-0.1, f"#{p['plot']}",
                    ha="left", va="top", fontsize=5.5, color="#555",
                    fontfamily="Courier New")

        # Мітки рядків і стовпців
        for i,r in enumerate(rows_set):
            ax.text(-0.08, nr-i-0.5, rep_map.get(i,""),
                    ha="right", va="center", fontsize=7,
                    fontfamily="Times New Roman")
        for j,c in enumerate(cols_set):
            p_ = next(p for p in plan if p["col"]==c)
            lbl = p_.get("col_label", f"#{c}")
            ax.text(j+0.5, nr+0.08, lbl, ha="center", va="bottom",
                    fontsize=7, fontfamily="Times New Roman")

        # Заголовок
        name = d.get("name") or "План досліду"
        fig.suptitle(
            f"{name}  |  {d.get('year','')}",
            fontsize=11, fontfamily="Times New Roman", fontweight="bold", y=0.98)
        ax.set_title(
            f"Культура: {d.get('culture','')}  |  Дизайн: {d['design_name']}  "
            f"|  Варіантів: {d['k']}  |  Повторностей: {d['reps']}  "
            f"|  Seed: {d['seed']}",
            fontsize=8, fontfamily="Times New Roman")

        # Легенда
        from matplotlib.patches import Patch
        handles = [Patch(facecolor=cmap[v], edgecolor="#777", label=v)
                   for v in all_v]
        fig.legend(handles=handles, loc="lower center",
                   ncol=min(4, len(all_v)), fontsize=7,
                   framealpha=0.8, bbox_to_anchor=(0.5, 0.01))
        try:
            fig.savefig(path, dpi=150, bbox_inches="tight")
            messagebox.showinfo("Збережено", f"PNG збережено:\n{path}")
            open_file_cross(path)
        except Exception as ex:
            messagebox.showerror("Помилка", str(ex))




