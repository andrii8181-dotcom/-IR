# sad_weather_export.py – S.A.D. v2.1: експорт модуля «Погода» (без tkinter)
# -*- coding: utf-8 -*-
import io, math, datetime as dt
import numpy as np
import sad_weather_core as W

HTC_FILL = {"d4": "F4B6B6", "d3": "F8CBAD", "d2": "FCE4D6", "d1": "FFF2CC",
            "ok": "E2EFDA", "wet": "DDEBF7", "na": "FFFFFF"}


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
    if s.has("et0"): cols.append(("ET₀, мм", lambda r: r["et0_sum"], 0, "num", False))
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
        rows.append(("Водний баланс (опади − ET₀), мм", t["water_balance"], 0))
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


def all_specs(rep):
    out = [spec_total(rep), spec_months(rep), spec_decades(rep)]
    if rep["years"]: out.append(spec_years(rep))
    if rep["periods"]: out.append(spec_periods(rep))
    return out


def to_strings(spec, comma=False, compact=False):
    """→ (headers, rows[str], htc_classes[list|None])."""
    if spec["kind"] == "kv":
        rows = []
        for label, v, nd in spec["rows"]:
            rows.append([label, v if isinstance(v, str) else fnum(v, nd or 0, comma)])
        return ["Показник", "Значення"], rows, None
    cols = [c for c in spec["cols"] if (c[4] or not compact)]
    headers = [c[0] for c in cols]
    rows, classes = [], []
    for r in spec["rows"]:
        row = []; cls = None
        empty = r.get("empty", False)
        for h, fn, nd, kind, _ in cols:
            if empty and h not in ("Період", "Початок", "Кінець", "Діб"):
                row.append("немає даних"); continue
            try: v = fn(r)
            except Exception: v = None
            if kind == "text": row.append("" if v is None else str(v))
            elif kind == "date": row.append(f"{v:%d.%m.%Y}" if v else "")
            elif kind == "htc":
                row.append(fnum(v, nd, comma)); cls = W.htc_class(v)[1]
            else: row.append(fnum(v, nd, comma))
        rows.append(row); classes.append(cls)
    return headers, rows, classes


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
    m1, d1, m2, d2 = st["window"]
    rows += [("Біологічний мінімум для СЕТ, °C", f"{st['gdd_base']:g}"),
             ("Облік активних температур у ГТК", {"decade": "декадний", "month": "місячний",
                                                  "daily": "добовий"}.get(st["htc_method"], st["htc_method"])),
             ("Вікно для порівняння років", f"{d1:02d}.{m1:02d} – {d2:02d}.{m2:02d}")]
    return rows


def publication_text(rep, place, lat, lon, source, extras=None):
    st = rep["settings"]; series = rep["series"]
    parts = ["МЕТОДИКА ЗБОРУ МЕТЕОДАНИХ",
             W.methods_paragraph(series, rep["d0"], rep["d1"], lat, lon, source,
                                 st["gdd_base"], st["htc_method"], extras)]
    cites = W.citation_block(source)
    if cites:
        parts += ["", "ДЖЕРЕЛА ТА ПОДЯКА (вимагаються умовами використання даних)"] + cites
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
        title = {"total": "Підсумок", "months": "Місяці", "decades": "Декади",
                 "years": "За роками", "periods": "Періоди"}[spec["key"]]
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
            empty = r.get("empty", False); vals = []; cls = None
            for h, fn, nd, kind, _ in cols:
                if empty and h not in ("Період", "Початок", "Кінець", "Діб"):
                    vals.append("немає даних"); continue
                try: v = fn(r)
                except Exception: v = None
                if isinstance(v, float) and math.isnan(v): v = None
                vals.append(v)
                if kind == "htc" and v is not None: cls = W.htc_class(v)[1]
            ws.append(vals)
            row_cells = list(ws.iter_rows(min_row=ws.max_row, max_row=ws.max_row))[0]
            for c, (h, fn, nd, kind, _) in zip(row_cells, cols):
                c.font = body_font; c.border = border
                if kind == "num" and nd is not None: c.number_format = "0" if nd == 0 else "0." + "0" * nd
                if kind == "date": c.number_format = "DD.MM.YYYY"
                if kind == "htc":
                    c.number_format = "0.00"
                    if cls: c.fill = PatternFill("solid", fgColor=HTC_FILL[cls])
            if cls:
                for c, (h, *_r) in zip(row_cells, cols):
                    if h == "Умови зволоження": c.fill = PatternFill("solid", fgColor=HTC_FILL[cls])
        style_header(ws, len(cols))
        for j, col in enumerate(cols, 1):
            ws.column_dimensions[get_column_letter(j)].width = 24 if col[0] == "Умови зволоження" else \
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
        if spec["key"] == "decades" and len(spec["rows"]) > 45: continue   # надто довга для тексту – є в Excel
        headers, rows, classes = to_strings(spec, comma, compact=True)
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
        para("", space_after=6)

    for k, (cap, png) in enumerate(figures, 1):
        doc.add_picture(io.BytesIO(png), width=Cm(16))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        para(f"Рис. {k} – {cap}", align="center", size=11)

    headings = {"ДЖЕРЕЛА": "Джерела даних", "ПРИМІТКИ": "Примітки щодо якості даних",
                "ШКАЛА": "Шкала вологозабезпеченості за ГТК"}
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
