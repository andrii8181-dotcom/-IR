# sad_phenology_journal.py – S.A.D. v2.1: фенофази з польового журналу (схема досліду → журнал → фенологія)
# -*- coding: utf-8 -*-
"""Перетворює журнали обліків за роками (формат .sadp, type=field_journal) на дані модуля фенології:
сорт (рівень фактора «Сорт»/«Гібрид»… або назва варіанта) × повторність × дати фенофаз. Рослини однієї ділянки зводяться
в одну дату – медіану (так фаза ділянки не залежить від однієї рослини-винятку)."""
import datetime as _dt, statistics
import sad_phenology as P

CULTIVAR_FACTOR_HINTS = ("сорт", "гібрид", "генотип", "номер", "cultivar", "variety", "genotype", "hybrid", "лінія")


def _cultivar_factor(factor_defs):
    for i, f in enumerate(factor_defs or []):
        if any(h in str(f.get("name", "")).lower() for h in CULTIVAR_FACTOR_HINTS): return i
    return 0 if len(factor_defs or []) == 1 else None


def _name_of(plant, factor_defs, variant_names, fi):
    fac = plant.get("factors") or {}
    if factor_defs and fac:
        if fi is not None:
            f = factor_defs[fi]; lv = fac.get(f["name"])
            if lv and 1 <= lv <= len(f["levels"]): return str(f["levels"][lv - 1])
        parts = []
        for f in factor_defs:
            lv = fac.get(f["name"]); parts.append(str(f["levels"][lv - 1]) if lv and 1 <= lv <= len(f["levels"]) else f"{f['name']} {lv}")
        return " + ".join(parts)
    v = plant.get("variant")
    if variant_names and v and 1 <= v <= len(variant_names): return str(variant_names[v - 1])
    return f"В{v}" if v else ""


def from_journal_years(years_json):
    """years_json: {рік (рядок/число): вміст журналу}. → dict(preset, phases, years_data, n_dates, notes, factor, cultivars).
    ValueError – у журналах немає жодного показника «дата фенофази»."""
    phase_meta = {}; preset_votes = {}; years_data = {}; n_dates = 0; notes = []; fname = None; cultivars = []
    standards = []; groups = {}; group_std = {}
    for ys in sorted(years_json, key=lambda x: int(x)):
        d = years_json[ys]; y = int(ys); fdefs = d.get("factor_defs") or []; vnames = d.get("variant_names") or []
        fi = _cultivar_factor(fdefs); fname = fname or (fdefs[fi]["name"] if fi is not None and fdefs else "Варіант")
        cfg = d.get("cfg") or {}                                          # стандарти й групи стиглості, позначені в конструкторі схеми
        for c in cfg.get("standards") or []:
            if c not in standards: standards.append(c)
        groups.update(cfg.get("groups") or {}); group_std.update(cfg.get("group_std") or {})
        date_recs = {nm: r for nm, r in (d.get("records") or {}).items() if r.get("kind") == "date"}
        for nm, r in date_recs.items():
            key = r.get("phase_key") or P.new_phase_key(r.get("phase_name") or nm, set())
            if key not in phase_meta: phase_meta[key] = {"key": key, "name": r.get("phase_name") or nm, "bbch": r.get("bbch", ""), "hint": "", "preset": r.get("preset")}
            if r.get("preset"): preset_votes[r["preset"]] = preset_votes.get(r["preset"], 0) + 1
        plots = {}
        for pl in d.get("plants") or []:
            if pl.get("role") != "recorded": continue
            name = _name_of(pl, fdefs, vnames, fi)
            if not name: continue
            plots.setdefault((name, pl.get("replication")), []).append(f"{pl['row']}:{pl['position']}")
        rows = []
        for (name, rep), keys in plots.items():
            if name not in cultivars: cultivars.append(name)
            dates = {}
            for nm, r in date_recs.items():
                vals = [P.parse_date_flex(str(r["values"][k]), y)[0] for k in keys if str(r.get("values", {}).get(k, "")).strip()]
                vals = [v for v in vals if v is not None]
                if not vals: continue
                med = _dt.date.fromordinal(int(statistics.median(v.toordinal() for v in vals) + 0.5))     # медіана; половина доби – вгору
                key = r.get("phase_key") or P.new_phase_key(r.get("phase_name") or nm, set())
                dates[key] = P.fmt_date(med); n_dates += 1
            rows.append({"name": name, "rep": "" if rep is None else str(rep), "dates": dates})
        rows.sort(key=lambda r: (cultivars.index(r["name"]), r["rep"]))
        if rows: years_data[y] = rows
    if not phase_meta: raise ValueError("У журналах цієї схеми немає жодного показника «дата фенофази». Додайте його в журналі кнопкою «🌸 Фенофаза…».")
    preset = max(preset_votes, key=preset_votes.get) if preset_votes else "custom"
    base = P.preset_phases(preset) if preset in P.PRESETS else []; keys = {p["key"] for p in base}
    extra = [{k: v for k, v in m.items() if k != "preset"} for m in phase_meta.values() if m["key"] not in keys]
    if extra: notes.append(f"Фази поза набором культури додано наприкінці: {', '.join(m['name'] for m in extra)}.")
    if len(preset_votes) > 1: notes.append("У журналі фази з різних наборів культур; використано набір, якого найбільше.")
    return {"preset": preset, "phases": base + extra, "years_data": years_data, "n_dates": n_dates, "notes": notes, "factor": fname, "cultivars": cultivars,
            "standards": standards, "groups": groups, "group_std": group_std}
