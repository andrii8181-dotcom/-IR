# sad_weather_export.py – S.A.D. v2.1: експорт модуля «Погода» (без tkinter)
# -*- coding: utf-8 -*-
import io, math, datetime as dt
import numpy as np
import sad_weather_core as W
import sad_weather_indices as WI

HTC_FILL = {"d4": "F4B6B6", "d3": "F8CBAD", "d2": "FCE4D6", "d1": "FFF2CC",
            "ok": "E2EFDA", "wet": "DDEBF7", "na": "FFFFFF"}


SPI_FILL = {"екстремально сухо": "F4B6B6", "дуже сухо": "F8CBAD", "помірно сухо": "FCE4D6", "норма": None,
            "помірно волого": "DDEBF7", "дуже волого": "BDD7EE", "екстремально волого": "9DC3E6"}
AI_FILL = {"гіперарідний": "F4B6B6", "арідний": "F8CBAD", "напівзасушливий": "FCE4D6", "сухий субвологий": "FFF2CC", "вологий": "E2EFDA"}
WK_FILL = {"I": "DDEBF7", "II": "E2EFDA", "III": "FFF2CC", "IV": "FCE4D6", "V": "F8CBAD"}
HI_FILL = {"HI−3": "9DC3E6", "HI−2": "DDEBF7", "HI−1": "E2EFDA", "HI+1": "FFF2CC", "HI+2": "FCE4D6", "HI+3": "F8CBAD"}


def _cls_spi(v): c = WI.spi_class(v); return c, c
def _cls_ai(v): c = WI.aridity_class(v); return c, c
def _cls_wk(v): r = WI.winkler_region(v); return (r.split(" ")[0] if r else ""), r
def _cls_hi(v):
    code, name = WI.huglin_class(v); return code, (f"{code} ({name})" if code else "")


# вид колонки → (функція класу, таблиця заливок); «_t» – текст класу замість числа
CELL_KINDS = {"spi": (_cls_spi, SPI_FILL, "num"), "spi_t": (_cls_spi, SPI_FILL, "text"), "ai": (_cls_ai, AI_FILL, "num"), "ai_t": (_cls_ai, AI_FILL, "text"),
              "wk": (_cls_wk, WK_FILL, "num"), "wk_t": (_cls_wk, WK_FILL, "text"), "hi": (_cls_hi, HI_FILL, "num"), "hi_t": (_cls_hi, HI_FILL, "text")}


def cell_info(kind, v):
    """→ (число чи None, текст класу, колір заливки hex без # або None) для колонок із кольоровим класом."""
    if v is None or (isinstance(v, float) and math.isnan(v)): return None, "", None
    clsfn, fills, _ = CELL_KINDS[kind]; key, text = clsfn(v)
    return v, text, fills.get(key)


def fnum(v, nd=1, comma=False, dash="–"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return dash
    s = f"{v:.{nd}f}"
    return s.replace(".", ",") if comma else s


def fmt_stamp(stamp):
    """ISO-мітка часу → «09.10.2026 18:31» (для людей); порожнє → «–»."""
    if not stamp: return "–"
    try: return dt.datetime.fromisoformat(stamp).strftime("%d.%m.%Y %H:%M")
    except ValueError: return str(stamp)


def htc_label(v):
    lab, key = W.htc_class(v)
    return "–" if key == "na" else lab


# ═══════════════════════════════════════════════════════════════
# Специфікації таблиць: (заголовок, getter, знаків, вид, у_компактній)
# вид: text | num | htc | date
# ═══════════════════════════════════════════════════════════════
def _opt_cols(rep, base_cols, full_only=True):
    s = rep["series"]
    cols = list(base_cols)
    if s.has("et0"):
        cols.append(("ET₀, мм", lambda r: r["et0_sum"], 0, "num", False))
        cols.append(("P/ET₀", lambda r: r.get("ai", float("nan")), 2, "num", False))
    if s.has("rad"): cols.append(("Радіація, МДж/м²", lambda r: r["rad_sum"], 0, "num", False))
    return cols


def spec_total(rep):
    t = rep["total"]; st = rep["settings"]; s = rep["series"]
    rows = [
        ("Кількість діб", t["days"], 0),
        ("Середня температура повітря, °C", t["tmean"], 1),
        ("Середня максимальна температура, °C", t["tmax_mean"], 1),
        ("Середня мінімальна температура, °C", t["tmin_mean"], 1),
        ("Абсолютний максимум, °C", t["tmax_abs"], 1),
        ("Абсолютний мінімум, °C", t["tmin_abs"], 1),
        ("Сума опадів, мм", t["prec_sum"], 1),
        ("Діб з опадами ≥ 1 мм", t["prec_days_1"], 0),
        ("Діб з опадами ≥ 10 мм", t["prec_days_10"], 0),
        ("Максимальна добова сума опадів, мм", t["prec_max_day"], 1),
        ("Найдовший період без суттєвих опадів (< 1 мм), діб", t["dry_spell_max"], 0),
        ("Сума активних температур > 5 °C", t["sat_5"], 0),
        ("Сума активних температур > 10 °C", t["sat_10"], 0),
        ("Сума активних температур > 15 °C", t["sat_15"], 0),
        (f"Сума ефективних температур (біологічний мінімум {st['gdd_base']:g} °C)", t["set"], 0),
        ("Діб із заморозком (tmin < 0 °C)", t["days_frost"], 0),
        ("Діб з tmax ≥ 25 / 30 / 35 °C", f"{t['days_tmax25']} / {t['days_tmax30']} / {t['days_tmax35']}", None),
        ("ГТК Селянінова за період", t["htc"], 2),
        ("Умови зволоження за ГТК", htc_label(t["htc"]), None),
    ]
    if s.has("rh"): rows.insert(7, ("Відносна вологість повітря, %", t["rh"], 0))
    if s.has("wind"): rows.append(("Середня швидкість вітру, м/с", t["wind"], 1))
    if s.has("rad"): rows.append(("Сумарна сонячна радіація, МДж/м²", t["rad_sum"], 0))
    if s.has("et0"):
        rows.append(("Еталонне випаровування ET₀, мм", t["et0_sum"], 0))
        rows.append(("Водний баланс (опади – ET₀), мм", t["water_balance"], 0))
        rows.append(("Індекс сухості P/ET₀ за період", t.get("ai", float("nan")), 2))
    return {"key": "total", "title": "Зведені показники за весь період", "kind": "kv", "rows": rows}


def _period_cols(rep, label_header, label_fn):
    st = rep["settings"]
    cols = [
        (label_header, label_fn, None, "text", True),
        ("Діб", lambda r: r["days"], 0, "num", False),
        ("tсер, °C", lambda r: r["tmean"], 1, "num", True),
        ("tmax сер., °C", lambda r: r["tmax_mean"], 1, "num", False),
        ("tmin сер., °C", lambda r: r["tmin_mean"], 1, "num", False),
        ("Опади, мм", lambda r: r["prec_sum"], 1, "num", True),
        ("Діб з опадами ≥1 мм", lambda r: r["prec_days_1"], 0, "num", False),
        ("САТ >10 °C", lambda r: r["sat_10"], 0, "num", True),
        (f"СЕТ (>{st['gdd_base']:g} °C)", lambda r: r["set"], 0, "num", False),
        ("ГТК", lambda r: r["htc"], 2, "htc", True),
        ("Умови зволоження", lambda r: htc_label(r["htc"]), None, "text", True),
    ]
    return _opt_cols(rep, cols)


def spec_months(rep):
    return {"key": "months", "title": "Метеорологічні умови за місяцями", "kind": "table",
            "cols": _period_cols(rep, "Місяць", lambda r: r["label"]), "rows": rep["months"]}


def spec_decades(rep):
    return {"key": "decades", "title": "Метеорологічні умови за декадами", "kind": "table",
            "cols": _period_cols(rep, "Декада", lambda r: r["label"]), "rows": rep["decades"]}


def spec_years(rep):
    st = rep["settings"]; m1, d1, m2, d2 = st["window"]
    cols = [
        ("Рік", lambda r: r["year"], 0, "num", True),
        ("Період", lambda r: f"{r['start']:%d.%m}–{r['end']:%d.%m}", None, "text", False),
        ("tсер, °C", lambda r: r["tmean"], 1, "num", True),
        ("Опади, мм", lambda r: r["prec_sum"], 0, "num", True),
        ("САТ >5 °C", lambda r: r["sat_5"], 0, "num", False),
        ("САТ >10 °C", lambda r: r["sat_10"], 0, "num", True),
        ("САТ >15 °C", lambda r: r["sat_15"], 0, "num", False),
        (f"СЕТ (>{st['gdd_base']:g} °C)", lambda r: r["set"], 0, "num", False),
        ("ГТК", lambda r: r["htc"], 2, "htc", True),
        ("Умови зволоження", lambda r: htc_label(r["htc"]), None, "text", True),
        ("Діб із заморозком", lambda r: r["days_frost"], 0, "num", False),
        ("Діб tmax ≥30 °C", lambda r: r["days_tmax30"], 0, "num", False),
        ("Пропуски t, %", lambda r: r["miss_tmean"] * 100, 1, "num", False),
        ("Пропуски опадів, %", lambda r: r["miss_prec"] * 100, 1, "num", False),
    ]
    cols = _opt_cols(rep, cols)
    if rep["years"] and "anom" in rep["years"][0]:
        cols += [("Δt від норми, °C", lambda r: r["anom"]["d_tmean"], 1, "num", True),
                 ("Опади, % норми", lambda r: r["anom"]["prec_pct"], 0, "num", True),
                 ("Оцінка опадів", lambda r: W.precip_deviation_class(r["anom"]["prec_pct"]), None, "text", False)]
    return {"key": "years", "title": f"Метеорологічні умови за роками (вікно {d1:02d}.{m1:02d}–{d2:02d}.{m2:02d})",
            "kind": "table", "cols": cols, "rows": rep["years"]}


def spec_periods(rep):
    cols = [
        ("Період", lambda r: r["name"], None, "text", True),
        ("Початок", lambda r: r["start"], None, "date", False),
        ("Кінець", lambda r: r["end"], None, "date", False),
        ("Діб", lambda r: (str(r.get("days", 0)) if r.get("days", 0) == r.get("expected", r.get("days", 0))
                           else f"{r.get('days', 0)} з {r.get('expected')}"), None, "text", True),
        ("tсер, °C", lambda r: r.get("tmean"), 1, "num", True),
        ("Опади, мм", lambda r: r.get("prec_sum"), 1, "num", True),
        ("САТ >10 °C", lambda r: r.get("sat_10"), 0, "num", True),
        ("СЕТ", lambda r: r.get("set"), 0, "num", False),
        ("tmax абс., °C", lambda r: r.get("tmax_abs"), 1, "num", False),
        ("tmin абс., °C", lambda r: r.get("tmin_abs"), 1, "num", False),
        ("Діб із заморозком", lambda r: r.get("days_frost"), 0, "num", False),
        ("ГТК", lambda r: r.get("htc"), 2, "htc", False),
    ]
    return {"key": "periods", "title": "Метеорологічні умови за періодами користувача",
            "kind": "table", "cols": cols, "rows": rep["periods"]}


def spec_vine(rep):
    iv = rep["intl"]; south = iv["lat"] is not None and iv["lat"] < 0
    cols = [("Сезон", lambda r: r["label"], None, "text", True),
            ("Вінклер (GDD >10 °C), °C·діб", lambda r: r["winkler"], 0, "wk", True),
            ("Регіон за Вінклером", lambda r: r["winkler"], None, "wk_t", True),
            ("Індекс Югліна (HI)", lambda r: r["huglin"], 0, "hi", True),
            ("Клас за Югліном", lambda r: r["huglin"], None, "hi_t", True),
            ("k (довжина дня)", lambda r: r["k"], 2, "num", False)]
    per = "1.10–30.04 / 1.10–31.03" if south else "1.04–31.10 / 1.04–30.09"
    lat_txt = f"{abs(iv['lat']):.2f}".replace(".", ",")
    return {"key": "vine", "title": f"Вінограрські агрокліматичні індекси за сезонами (Вінклер / Югліна: {per}; широта {lat_txt}° {'пд.' if south else 'пн.'})",
            "kind": "table", "cols": cols, "rows": iv["vine"]}


def spec_aridity(rep):
    cols = [("Рік", lambda r: r["year"], 0, "num", True), ("Опади, мм", lambda r: r["prec"], 0, "num", True),
            ("ET₀ (PET), мм", lambda r: r["pet"], 0, "num", True), ("Індекс сухості P/ET₀", lambda r: r["ai"], 2, "ai", True),
            ("Клас ЮНЕП", lambda r: r["ai"], None, "ai_t", True)]
    return {"key": "aridity", "title": "Індекс сухості ЮНЕП за календарними роками (P/ET₀)", "kind": "table", "cols": cols, "rows": rep["intl"]["aridity"]}


def spec_spi(rep):
    sp = rep["spi"]; ks = sp["scales"]
    cols = [("Місяць", lambda r: r["label"], None, "text", True), ("Опади, мм", lambda r: r["prec"], 0, "num", False)]
    for i, k in enumerate(ks):
        cols.append((f"SPI-{k}", (lambda r, k=k: r["spi"][k]), 2, "spi", True))
        cols.append((f"Оцінка SPI-{k}", (lambda r, k=k: r["spi"][k]), None, "spi_t", i == len(ks) - 1))
    return {"key": "spi", "title": f"SPI за місяцями (еталонний період {sp['ref'][0]}–{sp['ref'][1]}, гамма-розподіл)", "kind": "table", "cols": cols, "rows": sp["rows"]}


def all_specs(rep):
    out = [spec_total(rep), spec_months(rep), spec_decades(rep)]
    if rep["years"]: out.append(spec_years(rep))
    if rep["periods"]: out.append(spec_periods(rep))
    if rep.get("intl") and rep["intl"]["vine"]: out.append(spec_vine(rep))
    if rep.get("intl") and rep["intl"]["aridity"]: out.append(spec_aridity(rep))
    if rep.get("spi") and any(any(v == v for v in r["spi"].values()) for r in rep["spi"]["rows"]): out.append(spec_spi(rep))
    return out


def to_strings_ex(spec, comma=False, compact=False):
    """→ (headers, rows[str], htc_classes[list|None], cell_fills[list[dict стовпець→hex]])."""
    if spec["kind"] == "kv":
        rows = []
        for label, v, nd in spec["rows"]:
            rows.append([label, v if isinstance(v, str) else fnum(v, nd or 0, comma)])
        return ["Показник", "Значення"], rows, None, [{} for _ in rows]
    cols = [c for c in spec["cols"] if (c[4] or not compact)]
    headers = [c[0] for c in cols]
    rows, classes, fills = [], [], []
    for r in spec["rows"]:
        row = []; cls = None; cf = {}
        empty = r.get("empty", False)
        for j, (h, fn, nd, kind, _) in enumerate(cols):
            if empty and h not in ("Період", "Початок", "Кінець", "Діб"):
                row.append("немає даних"); continue
            try: v = fn(r)
            except Exception: v = None
            if kind == "text": row.append("" if v is None else str(v))
            elif kind == "date": row.append(f"{v:%d.%m.%Y}" if v else "")
            elif kind == "htc":
                row.append(fnum(v, nd, comma)); cls = W.htc_class(v)[1]
            elif kind in CELL_KINDS:
                num, text, fill = cell_info(kind, v)
                row.append(text if CELL_KINDS[kind][2] == "text" else fnum(num, nd or 0, comma))
                if fill: cf[j] = "#" + fill
            else: row.append(fnum(v, nd, comma))
        rows.append(row); classes.append(cls); fills.append(cf)
    return headers, rows, classes, fills


def to_strings(spec, comma=False, compact=False):
    """→ (headers, rows[str], htc_classes[list|None])."""
    h, r, c, _ = to_strings_ex(spec, comma, compact)
    return h, r, c


def clipboard_text(spec, comma=False, compact=False):
    headers, rows, _ = to_strings(spec, comma, compact)
    return "\n".join("\t".join(r) for r in [headers] + rows)


# ═══════════════════════════════════════════════════════════════
# Добові дані
# ═══════════════════════════════════════════════════════════════
DAILY_COLS = [("tmean", "tсер, °C", 1), ("tmax", "tmax, °C", 1), ("tmin", "tmin, °C", 1),
              ("prec", "Опади, мм", 1), ("rh", "Вологість, %", 0), ("wind", "Вітер, м/с", 1),
              ("rad", "Радіація, МДж/м²", 1), ("et0", "ET₀, мм", 1), ("sun", "Сяйво, год", 1)]


def daily_table(series, base=10.0):
    """→ (headers, rows(raw)); rows: [date, значення..., Σопадів, ΣСЕТ нагромаджені від початку]."""
    keys = [(k, h, nd) for k, h, nd in DAILY_COLS if series.has(k)]
    headers = ["Дата"] + [h for _, h, _ in keys]
    cum_p = cum_e = None
    if series.has("prec"): headers.append("Нагромаджені опади, мм"); cum_p = np.cumsum(np.nan_to_num(series.get("prec")))
    if series.has("tmean"):
        headers.append(f"Нагромаджена СЕТ (>{base:g} °C)")
        t = series.get("tmean"); cum_e = np.cumsum(np.where(t > base, t - base, 0.0))
    rows = []
    for i, d in enumerate(series.dates):
        row = [d] + [float(series.get(k)[i]) for k, _, _ in keys]
        if cum_p is not None: row.append(float(cum_p[i]))
        if cum_e is not None: row.append(float(cum_e[i]))
        rows.append(row)
    nds = [None] + [nd for _, _, nd in keys] + ([1] if cum_p is not None else []) + ([0] if cum_e is not None else [])
    return headers, rows, nds


def export_csv_daily(path, series, comma=False, sep=";", base=10.0):
    """CSV добових даних (UTF-8 із BOM – Excel коректно читає кирилицю)."""
    headers, rows, nds = daily_table(series, base)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        f.write(sep.join(headers) + "\r\n")
        for r in rows:
            cells = [f"{r[0]:%d.%m.%Y}"]
            for v, nd in zip(r[1:], nds[1:]):
                cells.append(fnum(v, nd, comma, dash=""))
            f.write(sep.join(cells) + "\r\n")


# ═══════════════════════════════════════════════════════════════
# Метадані та текст для публікації
# ═══════════════════════════════════════════════════════════════
def make_meta(rep, place, lat, lon, source):
    s = rep["series"]; st = rep["settings"]; mt = s.meta
    rows = [("Місце", place or "–"),
            ("Координати точки", "не вказано" if lat is None or lon is None
             else f"{lat:.4f}° пн. ш., {lon:.4f}° сх. д."),
            ("Джерело даних", W.SOURCE_TITLES.get(source, source)),
            ("Період", f"{rep['d0']:%d.%m.%Y} – {rep['d1']:%d.%m.%Y} ({len(s)} діб)"),
            ("Дата отримання даних", fmt_stamp(mt.get("retrieved_at")))]
    if mt.get("grid_lat") is not None and lat is not None and lon is not None:
        dist = W.haversine_km(lat, lon, mt["grid_lat"], mt["grid_lon"])
        rows.append(("Центр комірки сітки", f"{mt['grid_lat']:.3f}°, {mt['grid_lon']:.3f}° "
                                             f"(відстань від точки ≈ {dist:.1f} км)"))
    if mt.get("grid_elevation_m") is not None:
        rows.append(("Висота комірки сітки, м", f"{mt['grid_elevation_m']:.0f}"))
    if mt.get("timezone"): rows.append(("Часовий пояс (межі доби)", mt["timezone"]))
    if mt.get("time_standard"): rows.append(("Стандарт часу", mt["time_standard"]))
    iv = rep.get("intl") or {}
    if iv.get("pet_method") in ("pm", "hs", "given"): rows.append(("Еталонне випаровування ET₀", WI.PET_LABELS[iv["pet_method"]]))
    m1, d1, m2, d2 = st["window"]
    rows += [("Біологічний мінімум для СЕТ, °C", f"{st['gdd_base']:g}"),
             ("Облік активних температур у ГТК", {"decade": "декадний", "month": "місячний",
                                                  "daily": "добовий"}.get(st["htc_method"], st["htc_method"])),
             ("Вікно для порівняння років", f"{d1:02d}.{m1:02d} – {d2:02d}.{m2:02d}")]
    return rows


INTL_REFS = {
    "fao56": "Allen R.G., Pereira L.S., Raes D., Smith M. Crop evapotranspiration – Guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56. Rome: FAO, 1998.",
    "hs85": "Hargreaves G.H., Samani Z.A. Reference crop evapotranspiration from temperature. Applied Engineering in Agriculture. 1985. Vol. 1, No. 2. P. 96–99.",
    "unep": "World Atlas of Desertification. 2nd ed. / Ed. by N. Middleton, D. Thomas. London: Arnold; UNEP, 1997.",
    "winkler": "Amerine M.A., Winkler A.J. Composition and quality of musts and wines of California grapes. Hilgardia. 1944. Vol. 15, No. 6. P. 493–675.",
    "huglin": "Huglin P. Nouveau mode d'évaluation des possibilités héliothermiques d'un milieu viticole. Comptes Rendus de l'Académie d'Agriculture de France. 1978. Vol. 64. P. 1117–1126.",
    "tonietto": "Tonietto J., Carbonneau A. A multicriteria climatic classification system for grape-growing regions worldwide. Agricultural and Forest Meteorology. 2004. Vol. 124. P. 81–97.",
    "mckee": "McKee T.B., Doesken N.J., Kleist J. The relationship of drought frequency and duration to time scales. Proceedings of the 8th Conference on Applied Climatology. Boston: American Meteorological Society, 1993. P. 179–184.",
    "wmo": "Standardized Precipitation Index User Guide (WMO-No. 1090). Geneva: World Meteorological Organization, 2012.",
}


def intl_text(rep):
    """Абзац про міжнародні показники, що ДІЙСОВО розраховані в цьому звіті, і список літератури; посилання [n] нумеруються
    за порядком першої появи в тексті. → (абзац або '', [рядки літератури])."""
    iv = rep.get("intl") or {}; sp = rep.get("spi"); order = []

    def c(*keys):
        nums = []
        for k in keys:
            if k not in order: order.append(k)
            nums.append(order.index(k) + 1)
        return "[" + ", ".join(str(n) for n in sorted(set(nums))) + "]"
    parts = []
    if iv.get("pet_method") == "pm":
        parts.append(f"Еталонне випаровування (ET₀) розраховано за рівнянням Пенмана–Монтейта {c('fao56')} за добовими значеннями температури, відносної вологості "
                     f"повітря, швидкості вітру та сонячної радіації.")
    elif iv.get("pet_method") == "hs":
        parts.append(f"Еталонне випаровування (ET₀) розраховано за формулою Харгрівза–Самані {c('fao56', 'hs85')} за добовими значеннями максимальної й мінімальної "
                     f"температури повітря (радіація, вітер чи вологість у даних відсутні).")
    if iv.get("aridity"):
        parts.append(f"Індекс сухості визначали як відношення річної суми опадів до річної суми ET₀ (P/ET₀) {c('unep')}: гіперарідний – менше 0,05; арідний – 0,05–0,20; "
                     f"напівзасушливий – 0,20–0,50; сухий субвологий – 0,50–0,65; вологий – 0,65 і більше.")
    if iv.get("vine"):
        south = iv["lat"] is not None and iv["lat"] < 0
        k_txt = f"{iv['vine'][0]['k']:.2f}".replace(".", ",")
        parts.append(f"Індекс Вінклера {c('winkler')} (сума ефективних температур вище 10 °C за період "
                     f"{'з 1 жовтня по 30 квітня' if south else 'з 1 квітня по 31 жовтня'}, GDD) оцінювали за регіонами I–V (межі 1389, 1667, 1944 і 2222 °C·діб, що відповідає "
                     f"2500, 3000, 3500 і 4000 °F·діб). Геліотермічний індекс Югліна {c('huglin')} розраховували як суму "
                     f"((tсер − 10) + (tmax − 10))/2 за добами {'з 1 жовтня по 31 березня' if south else 'з 1 квітня по 30 вересня'} з коефіцієнтом довжини дня k = "
                     f"{k_txt}; класи – за {c('tonietto')}.")
    if sp and any(any(v == v for v in r["spi"].values()) for r in sp["rows"]):
        ks = ", ".join(str(k) for k in sp["scales"]); n_ref = min(sp["n_ref"].values()) if sp.get("n_ref") else 0
        parts.append(f"Стандартизований індекс опадів (SPI) {c('mckee', 'wmo')} розраховано за місячними сумами опадів для масштабів {ks} міс.: до сум опадів окремо для кожного "
                     f"календарного місяця підганяли гамма-розподіл методом максимальної правдоподібності (з урахуванням ймовірності нульових сум), еталонний період – "
                     f"{sp['ref'][0]}–{sp['ref'][1]} (не менше {n_ref} років), і перетворювали на стандартне нормальне відхилення.")
    refs = [f"{i}. {INTL_REFS[k]}" for i, k in enumerate(order, 1)]
    return " ".join(parts), refs


def publication_text(rep, place, lat, lon, source, extras=None):
    st = rep["settings"]; series = rep["series"]
    parts = ["МЕТОДИКА ЗБОРУ МЕТЕОДАНИХ",
             W.methods_paragraph(series, rep["d0"], rep["d1"], lat, lon, source,
                                 st["gdd_base"], st["htc_method"], extras)]
    intl_par, intl_refs = intl_text(rep)
    if intl_par: parts += ["", "МІЖНАРОДНІ АГРОКЛІМАТИЧНІ ПОКАЗНИКИ", intl_par]
    cites = W.citation_block(source)
    if cites:
        parts += ["", "ДЖЕРЕЛА ТА ПОДЯКА (вимагаються умовами використання даних)"] + cites
    if intl_refs: parts += ["", "ЛІТЕРАТУРА ДО МІЖНАРОДНИХ ПОКАЗНИКІВ"] + intl_refs
    lic = W.licence_notice(source)
    if lic: parts += ["", "УМОВИ ВИКОРИСТАННЯ", lic]
    notes = W.quality_notes(series, source, rep["d0"], rep["d1"])
    if rep["years_skipped"]:
        notes.append("Для років " + ", ".join(str(y) for y, _, _ in rep["years_skipped"]) +
                     " вікно порівняння покрито лише частково – ці роки не включено до таблиці за роками.")
    if notes: parts += ["", "ПРИМІТКИ ЩОДО ЯКОСТІ ДАНИХ"] + [f"• {n}" for n in notes]
    parts += ["", "ШКАЛА ВОЛОГОЗАБЕЗПЕЧЕНОСТІ ЗА ГТК", W.HTC_SCALE_TEXT]
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# Excel
# ═══════════════════════════════════════════════════════════════
def export_xlsx(path, rep, meta_rows, pub_text, comma_unused=None):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    wb = openpyxl.Workbook()
    hdr_font = Font(bold=True, name="Times New Roman", size=11)
    hdr_fill = PatternFill("solid", fgColor="D9E2F3")
    thin = Side(style="thin", color="BBBBBB"); border = Border(left=thin, right=thin, top=thin, bottom=thin)
    body_font = Font(name="Times New Roman", size=11)

    ws = wb.active; ws.title = "Метадані"
    ws.append(["Показник", "Значення"])
    for a, b in meta_rows: ws.append([a, b])
    ws.append([]); ws.append(["Текст для публікації", ""])
    for line in pub_text.split("\n"): ws.append([line, ""])
    ws.column_dimensions["A"].width = 46; ws.column_dimensions["B"].width = 80
    for c in ws[1]: c.font = hdr_font; c.fill = hdr_fill
    for row in ws.iter_rows(min_row=2):
        for c in row: c.font = body_font; c.alignment = Alignment(wrap_text=True, vertical="top")

    def style_header(sheet, ncols):
        for j in range(1, ncols + 1):
            c = sheet.cell(row=1, column=j); c.font = hdr_font; c.fill = hdr_fill
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = border
        sheet.freeze_panes = "A2"; sheet.row_dimensions[1].height = 32

    # добові
    ws = wb.create_sheet("Добові дані")
    headers, rows, nds = daily_table(rep["series"], rep["settings"]["gdd_base"])
    ws.append(headers)
    for r in rows:
        ws.append([r[0]] + [None if (isinstance(v, float) and math.isnan(v)) else v for v in r[1:]])
    for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
        row[0].number_format = "DD.MM.YYYY"
        for c, nd in zip(row[1:], nds[1:]):
            c.number_format = "0" if not nd else "0." + "0" * nd
            c.font = body_font
    style_header(ws, len(headers))
    for j in range(1, len(headers) + 1): ws.column_dimensions[get_column_letter(j)].width = 14
    ws.column_dimensions["A"].width = 12

    for spec in all_specs(rep):
        title = {"total": "Підсумок", "months": "Місяці", "decades": "Декади", "years": "За роками", "periods": "Періоди",
                 "vine": "Вінклер і Югліна", "aridity": "Індекс сухості", "spi": "SPI"}[spec["key"]]
        ws = wb.create_sheet(title)
        if spec["kind"] == "kv":
            ws.append(["Показник", "Значення"])
            for label, v, nd in spec["rows"]:
                ws.append([label, None if (isinstance(v, float) and math.isnan(v)) else v])
                if nd is not None and not isinstance(v, str):
                    ws.cell(row=ws.max_row, column=2).number_format = "0" if nd == 0 else "0." + "0" * nd
            ws.column_dimensions["A"].width = 62; ws.column_dimensions["B"].width = 22
            style_header(ws, 2)
            for row in ws.iter_rows(min_row=2):
                for c in row: c.font = body_font; c.border = border
            continue
        cols = spec["cols"]
        ws.append([c[0] for c in cols])
        for r in spec["rows"]:
            empty = r.get("empty", False); vals = []; cls = None; cfills = {}
            for h, fn, nd, kind, _ in cols:
                if empty and h not in ("Період", "Початок", "Кінець", "Діб"):
                    vals.append("немає даних"); continue
                try: v = fn(r)
                except Exception: v = None
                if isinstance(v, float) and math.isnan(v): v = None
                if kind in CELL_KINDS:
                    num, text, fill = cell_info(kind, v)
                    cfills[len(vals)] = fill; vals.append(text if CELL_KINDS[kind][2] == "text" else num); continue
                vals.append(v)
                if kind == "htc" and v is not None: cls = W.htc_class(v)[1]
            ws.append(vals)
            row_cells = list(ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row))[0]
            for c, (h, fn, nd, kind, _) in zip(row_cells, cols):
                c.font = body_font; c.border = border
                if kind == "num" and nd is not None: c.number_format = "0" if nd == 0 else "0." + "0" * nd
                if kind in CELL_KINDS and CELL_KINDS[kind][2] == "num" and nd is not None: c.number_format = "0" if nd == 0 else "0." + "0" * nd
                if kind == "date": c.number_format = "DD.MM.YYYY"
                if kind == "htc":
                    c.number_format = "0.00"
                    if cls: c.fill = PatternFill("solid", fgColor=HTC_FILL[cls])
            if cls:
                for c, (h, *_r) in zip(row_cells, cols):
                    if h == "Умови зволоження": c.fill = PatternFill("solid", fgColor=HTC_FILL[cls])
            for j, fill in cfills.items():
                if fill: row_cells[j].fill = PatternFill("solid", fgColor=fill)
        style_header(ws, len(cols))
        for j, col in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(j)].width = 24 if col[0] in ("Умови зволоження", "Регіон за Вінклером", "Клас за Югліном", "Клас ЮНЕП") or col[0].startswith("Оцінка SPI") else \
                                                              max(11, min(18, len(col[0]) + 3))

    if rep.get("norm"):
        nd_, years_, label = rep["norm"]
        ws = wb.create_sheet("Норма")
        ws.append(["Показник", f"Норма ({label})", "Станд. відхилення", "Кількість років"])
        names = {"tmean": "Середня температура, °C", "tmax_mean": "Середня tmax, °C", "tmin_mean": "Середня tmin, °C",
                 "prec_sum": "Сума опадів, мм", "sat_5": "САТ >5 °C", "sat_10": "САТ >10 °C", "sat_15": "САТ >15 °C",
                 "set": "СЕТ", "htc": "ГТК", "rad_sum": "Радіація, МДж/м²", "et0_sum": "ET₀, мм",
                 "days_frost": "Діб із заморозком", "days_tmax30": "Діб tmax ≥30 °C"}
        for k, nme in names.items():
            v, sd = nd_.get(k), nd_.get(k + "_sd")
            if v is None or (isinstance(v, float) and math.isnan(v)): continue
            ws.append([nme, v, None if (sd is None or math.isnan(sd)) else sd, len(years_)])
        style_header(ws, 4); ws.column_dimensions["A"].width = 32
        for j in "BCD": ws.column_dimensions[j].width = 20
        for row in ws.iter_rows(min_row=2):
            for c in row[1:3]: c.number_format = "0.00"
    wb.save(path)


# ═══════════════════════════════════════════════════════════════
# Word
# ═══════════════════════════════════════════════════════════════
def _have_docx():
    try:
        import docx  # noqa
        return True
    except ImportError:
        return False


def export_docx(path, rep, meta_rows, pub_text, figures, comma=True):
    """figures: [(підпис, png_bytes)]. Потрібен python-docx."""
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        raise RuntimeError("Для експорту у Word встановіть python-docx:\n  pip install python-docx")

    doc = Document()
    st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    for sec in doc.sections:
        sec.top_margin = Cm(2); sec.bottom_margin = Cm(2); sec.left_margin = Cm(2.5); sec.right_margin = Cm(1.5)

    def shade(cell, hex_):
        tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_); tcPr.append(shd)

    def para(text, bold=False, italic=False, align=None, size=None, space_after=6):
        p = doc.add_paragraph(); r = p.add_run(text); r.bold = bold; r.italic = italic
        r.font.name = "Times New Roman"
        if size: r.font.size = Pt(size)
        if align == "center": p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == "justify": p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(space_after)
        return p

    h = doc.add_heading("Метеорологічні умови періоду досліджень", level=1)
    for r in h.runs: r.font.name = "Times New Roman"; r.font.color.rgb = RGBColor(0, 0, 0)
    for a, b in meta_rows[:7]:
        para(f"{a}: {b}", size=11, space_after=2)
    para("")
    blocks = pub_text.split("\n\n")
    para("Методика", bold=True, space_after=2)
    para(blocks[0].split("\n", 1)[1] if "\n" in blocks[0] else blocks[0], align="justify")

    n_tab = 0
    for spec in all_specs(rep):
        if spec["key"] == "total": continue
        if spec["key"] in ("decades", "spi") and len(spec["rows"]) > 45: continue   # надто довга для тексту – є в Excel
        headers, rows, classes, cfills = to_strings_ex(spec, comma, compact=True)
        if not rows: continue
        n_tab += 1
        para(f"Таблиця {n_tab} – {spec['title']}", italic=True, space_after=3)
        tbl = doc.add_table(rows=1 + len(rows), cols=len(headers)); tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, hd in enumerate(headers):
            c = tbl.rows[0].cells[j]; c.text = ""; run = c.paragraphs[0].add_run(hd)
            run.bold = True; run.font.size = Pt(10); run.font.name = "Times New Roman"
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER; shade(c, "D9E2F3")
        for i, row in enumerate(rows, 1):
            for j, v in enumerate(row):
                c = tbl.rows[i].cells[j]; c.text = ""; run = c.paragraphs[0].add_run(v)
                run.font.size = Pt(10); run.font.name = "Times New Roman"
                c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if j else WD_ALIGN_PARAGRAPH.LEFT
                if classes and classes[i - 1] and headers[j] in ("ГТК", "Умови зволоження"):
                    shade(c, HTC_FILL[classes[i - 1]])
                elif cfills[i - 1].get(j): shade(c, cfills[i - 1][j][1:])
        para("", space_after=6)

    for k, (cap, png) in enumerate(figures, 1):
        doc.add_picture(io.BytesIO(png), width=Cm(16))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        para(f"Рис. {k} – {cap}", align="center", size=11)

    headings = {"МІЖНАРОДНІ": "Міжнародні агрокліматичні показники", "ДЖЕРЕЛА": "Джерела даних", "ЛІТЕРАТУРА": "Література до міжнародних показників",
                "ПРИМІТКИ": "Примітки щодо якості даних", "ШКАЛА": "Шкала вологозабезпеченості за ГТК"}
    for blk in blocks[1:]:
        lines = blk.split("\n")
        key = next((k for k in headings if lines and lines[0].startswith(k)), None)
        if key is None:                       # напр. «УМОВИ ВИКОРИСТАННЯ» – службова інформація, не для тексту
            continue
        para(headings[key], bold=True, size=11, space_after=2)
        for ln in lines[1:]:
            para(ln, size=10, space_after=2)
    doc.save(path)


def figure_png(rep, kind, place, build_chart, size=(9.0, 5.2), dpi=200, style=None):
    """PNG-байти діаграми, побудованої без вікна (для Word). build_chart передається ззовні,
    щоб цей модуль не залежав від matplotlib при імпорті."""
    from matplotlib.figure import Figure
    fig = Figure(figsize=size, dpi=dpi)
    res = build_chart(fig, kind, rep, place, style) if style is not None else build_chart(fig, kind, rep, place)
    if res: return None
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight"); return buf.getvalue()
