# sad_weather_indices.py – S.A.D. v2.1: міжнародні показники для модуля «Погода» (без tkinter)
# -*- coding: utf-8 -*-
"""
• ET₀: FAO-56 Пенман–Монтейт (Allen et al., 1998); за браку радіації/вітру/вологості – Харгрівз–Самані (1985).
• Індекс сухості ЮНЕП: AI = P / PET (UNEP, 1992; Middleton & Thomas, 1997).
• Вінограрські індекси: Вінклер (Amerine & Winkler, 1944), геліотермічний індекс Югліна (Huglin, 1978; класи – Tonietto & Carbonneau, 2004).
• SPI – стандартизований індекс опадів (McKee et al., 1993; WMO, 2012): гамма-розподіл за методом максимальної правдоподібності,
  окремо для кожного календарного місяця й масштабу (1, 3, 6, 12 міс.); нульові суми враховано через ймовірність нуля.
Назви: СЕТ у цій програмі = GDD (growing degree days) із порогом 10 °C; САТ = сума активних температур.
"""
import math, calendar
import datetime as _dt
import numpy as np
from scipy import stats

NAN = float("nan")


# ═══════════════════════════════════════════════════════════════
# 1. Еталонне випаровування ET₀ (FAO-56)
# ═══════════════════════════════════════════════════════════════
def sat_vp(t):
    """Тиск насиченої водяної пари, кПа (FAO-56, ур. 11)."""
    t = np.asarray(t, float); return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def ra_daily(doy, lat_deg):
    """Позаатмосферна радіація Ra, МДж/м²/добу (FAO-56, ур. 21–25)."""
    j = np.asarray(doy, float); phi = math.radians(lat_deg)
    dr = 1.0 + 0.033 * np.cos(2 * math.pi / 365.0 * j)
    delta = 0.409 * np.sin(2 * math.pi / 365.0 * j - 1.39)
    x = np.clip(-math.tan(phi) * np.tan(delta), -1.0, 1.0)                   # полярний день/ніч
    ws = np.arccos(x)
    return (24 * 60 / math.pi) * 0.0820 * dr * (ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws))


def et0_pm(tmax, tmin, rs, u2, doy, lat, elev=0.0, rh=None, ea=None):
    """FAO-56 Penman–Monteith, добовий крок, G = 0. tmax/tmin °C; rs МДж/м²/добу; u2 м/с на висоті 2 м; rh – середня відносна
    вологість, %, (ea = RH/100·(e°(Tmax)+e°(Tmin))/2, ур. 19) або ea – фактичний тиск пари, кПа. Результат – мм/добу."""
    tmax = np.asarray(tmax, float); tmin = np.asarray(tmin, float); rs = np.asarray(rs, float); u2 = np.asarray(u2, float)
    tm = (tmax + tmin) / 2.0
    es = (sat_vp(tmax) + sat_vp(tmin)) / 2.0
    if ea is None:
        if rh is None: raise ValueError("Потрібна вологість повітря (rh) або тиск пари (ea).")
        ea = np.asarray(rh, float) / 100.0 * es
    ea = np.asarray(ea, float)
    P = 101.3 * ((293.0 - 0.0065 * elev) / 293.0) ** 5.26; gam = 0.000665 * P
    delta = 4098.0 * sat_vp(tm) / (tm + 237.3) ** 2
    ra = ra_daily(doy, lat); rso = (0.75 + 2e-5 * elev) * ra
    rns = (1 - 0.23) * rs
    ratio = np.clip(np.where(rso > 0, rs / np.where(rso > 0, rso, 1.0), 0.0), 0.3, 1.0)       # відношення Rs/Rso (FAO-56: 0,3–1,0)
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2.0 * (0.34 - 0.14 * np.sqrt(np.clip(ea, 0, None))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    et = (0.408 * delta * rn + gam * 900.0 / (tm + 273.0) * u2 * (es - ea)) / (delta + gam * (1 + 0.34 * u2))
    return np.clip(et, 0.0, None)


def et0_hargreaves(tmax, tmin, doy, lat):
    """Харгрівз–Самані: ET₀ = 0,0023·Ra(мм)·(Tсер + 17,8)·√(Tmax − Tmin), мм/добу."""
    tmax = np.asarray(tmax, float); tmin = np.asarray(tmin, float)
    ra_mm = 0.408 * ra_daily(doy, lat)
    return np.clip(0.0023 * ra_mm * ((tmax + tmin) / 2.0 + 17.8) * np.sqrt(np.clip(tmax - tmin, 0, None)), 0.0, None)


PET_LABELS = {"given": "ET₀ із даних користувача", "pm": "FAO-56 Пенман–Монтейт", "hs": "Харгрівз–Самані", "none": "не розраховано"}


def pet_series(series, lat, elev=None):
    """Добова PET (мм) для ряду. Пріоритет: ET₀ із даних → Пенман–Монтейт → Харгрівз–Самані. → (масив, ключ методу, примітка)."""
    n = len(series)
    doy = np.array([d.timetuple().tm_yday for d in series.dates], float)
    if series.has("et0"):
        return series.get("et0"), "given", "Використано ET₀ із даних користувача."
    if lat is None:
        return np.full(n, NAN), "none", "Для розрахунку ET₀ потрібні координати (широта)."
    need = ("tmax", "tmin")
    if not all(series.has(k) for k in need):
        return np.full(n, NAN), "none", "Для розрахунку ET₀ потрібні добові tmax і tmin."
    z = elev if elev is not None else series.meta.get("grid_elevation_m")
    z_known = z is not None
    z = float(z) if z_known else 0.0
    if all(series.has(k) for k in ("rad", "wind", "rh")):
        pet = et0_pm(series.get("tmax"), series.get("tmin"), series.get("rad"), series.get("wind"), doy, lat, z, rh=series.get("rh"))
        note = ("ET₀ за FAO-56 Пенман–Монтейт (G = 0; швидкість вітру вважається виміряною на висоті 2 м; вологість – середньодобова)"
                + (f"; висота {z:.0f} м." if z_known else "; висоту над рівнем моря не задано – прийнято 0 м."))
        return pet, "pm", note
    pet = et0_hargreaves(series.get("tmax"), series.get("tmin"), doy, lat)
    return pet, "hs", ("ET₀ за Харгрівзом–Самані (немає даних про радіацію, вітер чи вологість; точність нижча, ніж у Пенмана–Монтейта; "
                       "у вологому кліматі завищує, у посушливому може занижувати).")


# ═══════════════════════════════════════════════════════════════
# 2. Індекс сухості ЮНЕП
# ═══════════════════════════════════════════════════════════════
AI_CLASSES = [(0.05, "гіперарідний"), (0.20, "арідний"), (0.50, "напівзасушливий"), (0.65, "сухий субвологий"), (math.inf, "вологий")]


def aridity_class(ai):
    if ai is None or (isinstance(ai, float) and math.isnan(ai)): return ""
    for hi, name in AI_CLASSES:
        if ai < hi: return name
    return AI_CLASSES[-1][1]


def _covered(series, a, b):
    """Чи ряд містить усі доби [a, b] (без пропущених дат)."""
    if not series.dates or a < series.dates[0] or b > series.dates[-1]: return False
    n = (b - a).days + 1
    cnt = sum(1 for d in series.dates if a <= d <= b)
    return cnt == n


def _idx(series, a, b):
    return [i for i, d in enumerate(series.dates) if a <= d <= b]


def aridity_rows(series, pet, min_share=0.95):
    """Календарні роки з повним покриттям: P, PET, AI = P/PET, клас ЮНЕП. Це стандартне (річне) визначення."""
    rows = []
    if not series.dates or not series.has("prec") or np.all(np.isnan(pet)): return rows
    p = series.get("prec")
    for y in range(series.dates[0].year, series.dates[-1].year + 1):
        a, b = _dt.date(y, 1, 1), _dt.date(y, 12, 31)
        if not _covered(series, a, b): continue
        ix = _idx(series, a, b); pp, ee = p[ix], pet[ix]
        if np.mean(~np.isnan(pp)) < min_share or np.mean(~np.isnan(ee)) < min_share: continue
        P, E = float(np.nansum(pp) * len(ix) / max(1, np.sum(~np.isnan(pp)))), float(np.nansum(ee) * len(ix) / max(1, np.sum(~np.isnan(ee))))
        ai = P / E if E > 0 else NAN
        rows.append({"year": y, "prec": P, "pet": E, "ai": ai, "class": aridity_class(ai)})
    return rows


def window_ai(prec_sum, pet_sum):
    """AI для довільного відрізка (наприклад, вегетаційного вікна): не стандарт ЮНЕП (той – річний), але корисна характеристика."""
    return prec_sum / pet_sum if (pet_sum and pet_sum > 0 and prec_sum == prec_sum) else NAN


# ═══════════════════════════════════════════════════════════════
# 3. Вінограрські індекси: Вінклер і Югліна
# ═══════════════════════════════════════════════════════════════
WINKLER_BOUNDS_F = (2500.0, 3000.0, 3500.0, 4000.0)                   # °F·діб (Amerine & Winkler, 1944)
WINKLER_BOUNDS_C = tuple(b * 5.0 / 9.0 for b in WINKLER_BOUNDS_F)     # 1389, 1667, 1944, 2222 °C·діб
WINKLER_NAMES = ["I (дуже прохолодний)", "II (прохолодний)", "III (помірно теплий)", "IV (теплий)", "V (дуже теплий)"]
HUGLIN_CLASSES = [(1500.0, "HI−3", "дуже прохолодний"), (1800.0, "HI−2", "прохолодний"), (2100.0, "HI−1", "помірний"),
                  (2400.0, "HI+1", "помірно теплий"), (3000.0, "HI+2", "теплий"), (math.inf, "HI+3", "дуже теплий")]


def winkler_region(w):
    if w is None or w != w: return ""
    for b, name in zip(WINKLER_BOUNDS_C, WINKLER_NAMES):
        if w <= b: return name
    return WINKLER_NAMES[-1]


def huglin_class(hi):
    if hi is None or hi != hi: return "", ""
    for hi_max, code, name in HUGLIN_CLASSES:
        if hi <= hi_max: return code, name
    return HUGLIN_CLASSES[-1][1], HUGLIN_CLASSES[-1][2]


def huglin_k(lat):
    """Коефіцієнт довжини дня Югліна за смугами широт (Huglin, 1978): ≤ 40° → 1,00; (40; 42] → 1,02; (42; 44] → 1,03;
    (44; 46] → 1,04; (46; 48] → 1,05; (48; 50] → 1,06; понад 50° → 1,06 (останнє значення таблиці; індекс визначено для 40–50°)."""
    a = abs(lat)
    for hi, k in ((40, 1.00), (42, 1.02), (44, 1.03), (46, 1.04), (48, 1.05), (50, 1.06)):
        if a <= hi: return k
    return 1.06


def season_bounds(year, lat, kind):
    """Межі сезону: Вінклер – 1.04–31.10 (пн. півкуля) / 1.10–30.04 наступного року (пд.); Югліна – 1.04–30.09 / 1.10–31.03."""
    north = lat >= 0
    if kind == "winkler":
        return (_dt.date(year, 4, 1), _dt.date(year, 10, 31)) if north else (_dt.date(year, 10, 1), _dt.date(year + 1, 4, 30))
    return (_dt.date(year, 4, 1), _dt.date(year, 9, 30)) if north else (_dt.date(year, 10, 1), _dt.date(year + 1, 3, 31))


def vine_rows(series, lat, min_share=0.95):
    """Сезони з повним покриттям: GDD/Вінклер (Σ max(Tсер − 10, 0)) і Югліна (k·Σ max(((Tсер − 10) + (Tmax − 10))/2, 0))."""
    rows = []
    if lat is None or not series.dates: return rows
    tm, tx = series.get("tmean"), series.get("tmax")
    have_tm = series.has("tmean"); have_tx = series.has("tmax") and have_tm
    k = huglin_k(lat); south = lat < 0
    years = range(series.dates[0].year - 1, series.dates[-1].year + 1)
    for y in years:
        row = {"year": y, "label": f"{y}/{str(y + 1)[2:]}" if south else str(y), "winkler": NAN, "winkler_region": "", "huglin": NAN,
               "huglin_code": "", "huglin_class": "", "k": k}
        a, b = season_bounds(y, lat, "winkler")
        if have_tm and _covered(series, a, b):
            ix = _idx(series, a, b); t = tm[ix]
            if np.mean(~np.isnan(t)) >= min_share:
                row["winkler"] = float(np.nansum(np.clip(t - 10.0, 0, None))); row["winkler_region"] = winkler_region(row["winkler"])
        a, b = season_bounds(y, lat, "huglin")
        if have_tx and _covered(series, a, b):
            ix = _idx(series, a, b); t, x = tm[ix], tx[ix]
            if np.mean(~(np.isnan(t) | np.isnan(x))) >= min_share:
                row["huglin"] = float(k * np.nansum(np.clip(((t - 10.0) + (x - 10.0)) / 2.0, 0, None)))
                row["huglin_code"], row["huglin_class"] = huglin_class(row["huglin"])
        if row["winkler"] == row["winkler"] or row["huglin"] == row["huglin"]: rows.append(row)
    return rows


# ═══════════════════════════════════════════════════════════════
# 4. SPI
# ═══════════════════════════════════════════════════════════════
SPI_CLASSES = [(-2.0, "екстремально сухо"), (-1.5, "дуже сухо"), (-1.0, "помірно сухо"), (1.0, "норма"), (1.5, "помірно волого"),
               (2.0, "дуже волого"), (math.inf, "екстремально волого")]


def spi_class(z):
    """McKee та ін. (1993): ≥ 2 екстремально волого; 1,5…1,99 дуже волого; 1…1,49 помірно волого; −0,99…0,99 норма; … ≤ −2 екстремально сухо."""
    if z is None or z != z: return ""
    if z <= -2.0: return SPI_CLASSES[0][1]
    if z <= -1.5: return SPI_CLASSES[1][1]
    if z <= -1.0: return SPI_CLASSES[2][1]
    if z < 1.0: return SPI_CLASSES[3][1]
    if z < 1.5: return SPI_CLASSES[4][1]
    if z < 2.0: return SPI_CLASSES[5][1]
    return SPI_CLASSES[6][1]


def monthly_totals(series, min_share=0.9):
    """Місячні суми опадів для МІСЯЦІВ, повністю охоплених рядом. Якщо частка наявних діб ≥ min_share, пропуски компенсуються
    пропорційно (сума·днів_у_місяці/наявних_діб); інакше місяць = NaN. → список (рік, місяць, сума)."""
    if not series.dates or not series.has("prec"): return []
    p = series.get("prec"); out = []
    d0, d1 = series.dates[0], series.dates[-1]
    y, m = d0.year, d0.month
    by_month = {}
    for i, d in enumerate(series.dates): by_month.setdefault((d.year, d.month), []).append(i)
    while (y, m) <= (d1.year, d1.month):
        dim = calendar.monthrange(y, m)[1]; ix = by_month.get((y, m), [])
        full = len(ix) == dim
        val = NAN
        if full:
            v = p[ix]; ok = ~np.isnan(v)
            if ok.mean() >= min_share: val = float(np.sum(v[ok]) * dim / ok.sum())
        out.append((y, m, val))
        m += 1
        if m > 12: y, m = y + 1, 1
    return out


def _rolling(vals, k):
    n = len(vals); out = np.full(n, NAN)
    for t in range(k - 1, n):
        w = vals[t - k + 1:t + 1]
        if not np.any(np.isnan(w)): out[t] = float(np.sum(w))
    return out


def spi_from_sample(x_ref, x_new, min_ref=20, min_pos=8):
    """SPI нових значень x_new відносно еталонної вибірки x_ref (однакового календарного місяця й масштабу).
    H(x) = q + (1 − q)·G(x; a, β), q – частка нульових сум; SPI = Φ⁻¹(H). → (масив SPI, параметри (a, β, q) або None)."""
    x_ref = np.asarray(x_ref, float); x_ref = x_ref[~np.isnan(x_ref)]
    x_new = np.asarray(x_new, float)
    if len(x_ref) < min_ref: return np.full(len(x_new), NAN), None
    pos = x_ref[x_ref > 0]; q = 1.0 - len(pos) / len(x_ref)
    if len(pos) < min_pos or np.ptp(pos) == 0: return np.full(len(x_new), NAN), None
    a, _, beta = stats.gamma.fit(pos, floc=0)
    h = np.where(x_new > 0, q + (1 - q) * stats.gamma.cdf(np.where(x_new > 0, x_new, 1.0), a, scale=beta), q)
    h = np.clip(h, 1e-6, 1 - 1e-6)
    z = stats.norm.ppf(h)
    return np.where(np.isnan(x_new), NAN, z), (float(a), float(beta), float(q))


def spi_table(series, ref=(1991, 2020), scales=(1, 3, 6, 12), study=None, min_ref=20):
    """SPI за місяцями. series – ряд, що охоплює еталонний період і період дослідження; ref=(рік_від, рік_до) – еталонні роки;
    study=(дата_від, дата_до) – місяці, для яких наводиться SPI (за замовчуванням – усі). → dict(rows, scales, ref, n_ref, warnings, params)."""
    tot = monthly_totals(series); warns = []
    res = {"rows": [], "scales": list(scales), "ref": ref, "n_ref": {}, "warnings": warns, "params": {}}
    if not tot:
        warns.append("У ряді немає даних про опади."); return res
    vals = np.array([t[2] for t in tot]); ys = np.array([t[0] for t in tot]); ms = np.array([t[1] for t in tot])
    spi_by_scale = {}
    for k in scales:
        roll = _rolling(vals, k); z = np.full(len(vals), NAN); nmin = 10 ** 9
        for c in range(1, 13):
            sel = ms == c; in_ref = sel & (ys >= ref[0]) & (ys <= ref[1])
            zc, par = spi_from_sample(roll[in_ref], roll[sel], min_ref=min_ref)
            z[sel] = zc; res["params"][(k, c)] = par; nmin = min(nmin, int(np.sum(~np.isnan(roll[in_ref]))))
        spi_by_scale[k] = z; res["n_ref"][k] = nmin if nmin != 10 ** 9 else 0
        if res["n_ref"][k] < min_ref: warns.append(f"SPI-{k}: в еталонному періоді {ref[0]}–{ref[1]} замало повних місяців (потрібно ≥ {min_ref} років для кожного календарного місяця); значення не розраховано.")
        elif res["n_ref"][k] < 30: warns.append(f"SPI-{k}: еталонний період містить лише {res['n_ref'][k]} років – WMO рекомендує ≥ 30; значення менш надійні.")
    d0, d1 = (study if study else (series.dates[0], series.dates[-1]))
    for i, (y, m, v) in enumerate(tot):
        d = _dt.date(y, m, 1)
        if not (_dt.date(d0.year, d0.month, 1) <= d <= _dt.date(d1.year, d1.month, 1)): continue
        row = {"year": y, "month": m, "label": f"{m:02d}.{y}", "prec": v, "spi": {}, "class": {}}
        for k in scales:
            z = float(spi_by_scale[k][i]); row["spi"][k] = z; row["class"][k] = spi_class(z)
        res["rows"].append(row)
    return res
