# test_sad_weather_indices.py – міжнародні показники: ET0 (FAO-56), індекс сухості, Вінклер, Югліна, SPI (без tkinter)
import os, sys, math, calendar, datetime as dt, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_weather_core as W, sad_weather_indices as I
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
def have(m):
    try: __import__(m); return True
    except Exception: return False
D = dt.date
def ser_from(d0, d1, **cols):
    n = (d1 - d0).days + 1; dts = [d0 + dt.timedelta(days=i) for i in range(n)]
    return W.DailySeries(dts, {k: (np.full(n, v) if np.isscalar(v) else np.asarray(v, float)) for k, v in cols.items()})

print("== 1. ET₀: FAO-56 Пенман–Монтейт")
lat = 50 + 48 / 60.0
check(abs(float(I.ra_daily(187, lat)) - 41.09) < 0.01, f"Ra (приклад 8 FAO-56, 6 липня, 50°48'): {float(I.ra_daily(187, lat)):.2f} = 41,09 МДж/м²/добу")
et = float(I.et0_pm(21.5, 12.3, 22.07, 2.078, 187, lat, 100.0, ea=1.409))
check(abs(et - 3.88) < 0.005, f"ET₀ за прикладом 18 FAO-56 (Брюссель, 6 липня) = {et:.3f} мм/добу (еталон 3,88)")
es_ = (I.sat_vp(21.5) + I.sat_vp(12.3)) / 2; check(abs(float(es_) - 1.997) < 0.001, f"es = {float(es_):.3f} кПа (еталон 1,997)")
et_rh = float(I.et0_pm(21.5, 12.3, 22.07, 2.078, 187, lat, 100.0, rh=1.409 / float(es_) * 100))
check(abs(et_rh - et) < 1e-9, "шлях через середню відносну вологість (ур. 19) еквівалентний прямому ea")
if have("pyet") and have("pandas"):
    import pandas as pd, pyet
    rg = np.random.default_rng(7); n = 400; idx = pd.date_range("2021-01-01", periods=n, freq="D"); dy = idx.dayofyear.values.astype(float)
    tmin = rg.uniform(-8, 22, n); tmax = tmin + rg.uniform(3, 14, n); rs = rg.uniform(2, 28, n); u2 = rg.uniform(0.3, 6, n); ea = rg.uniform(0.4, 2.2, n)
    for la, z in ((48.75, 212.0), (-33.9, 50.0), (60.0, 5.0), (5.0, 1500.0)):
        mine = I.et0_pm(tmax, tmin, rs, u2, dy, la, z, ea=ea)
        ref = pyet.pm_fao56(pd.Series((tmax + tmin) / 2, idx), pd.Series(u2, idx), rs=pd.Series(rs, idx), tmax=pd.Series(tmax, idx), tmin=pd.Series(tmin, idx),
                            ea=pd.Series(ea, idx), elevation=z, lat=math.radians(la)).values
        check(np.abs(mine - ref).max() < 1e-9, f"збіг із незалежною реалізацією pyet на 400 випадкових добах (φ = {la}°, {z:.0f} м): макс. |Δ| = {np.abs(mine - ref).max():.1e}")
else: print("  (pyet не встановлено – порівняння з незалежною реалізацією пропущено)")
hs = float(I.et0_hargreaves(30.0, 15.0, 180, 45.0))
phi = math.radians(45.0); jj = 180; dr = 1 + 0.033 * math.cos(2 * math.pi * jj / 365); dec = 0.409 * math.sin(2 * math.pi * jj / 365 - 1.39)
wsa = math.acos(-math.tan(phi) * math.tan(dec)); ra = 24 * 60 / math.pi * 0.082 * dr * (wsa * math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.sin(wsa))
check(abs(hs - 0.0023 * 0.408 * ra * (22.5 + 17.8) * math.sqrt(15.0)) < 1e-12, f"Харгрівз–Самані за ручним розрахунком (FAO-56, ур. 52): {hs:.3f} мм/добу")
check(2.0 < hs < 9.0, "значення у правдоподібних межах")
pol = I.et0_pm(np.full(3, 15.0), np.full(3, 8.0), np.full(3, 20.0), np.full(3, 2.0), np.array([172.0, 355.0, 80.0]), 80.0, 10.0, rh=np.full(3, 70.0))
check(np.all(np.isfinite(pol)) and np.all(pol >= 0), "полярні широти (80°): ні NaN, ні від'ємних значень")
check(float(I.et0_pm(25.0, 10.0, 20.0, 2.0, 180, 45.0, ea=0.5)) > float(I.et0_pm(25.0, 10.0, 20.0, 2.0, 180, 45.0, ea=1.5)), "сухіше повітря (менший ea) → більше випаровування")
check(float(I.et0_pm(25.0, 10.0, 20.0, 4.0, 180, 45.0, ea=0.8)) > float(I.et0_pm(25.0, 10.0, 20.0, 1.0, 180, 45.0, ea=0.8)), "сильніший вітер → більше випаровування")
n = 60; full = ser_from(D(2024, 6, 1), D(2024, 7, 29), tmax=27.0, tmin=14.0, tmean=20.5, rad=22.0, wind=2.0, rh=60.0, prec=1.0)
full.meta["grid_elevation_m"] = 212.0
pet, meth, note = I.pet_series(full, 48.75); check(meth == "pm" and np.all(pet > 0) and "212" in note and "2 м" in note, f"повний набір → Пенман–Монтейт; примітка: «{note[:70]}…»")
nr = ser_from(D(2024, 6, 1), D(2024, 6, 30), tmax=27.0, tmin=14.0, prec=1.0)
pet, meth, note = I.pet_series(nr, 48.75); check(meth == "hs" and "Харгрівз" in note and np.all(pet > 0), "лише tmax/tmin → Харгрівз–Самані з попередженням про точність")
pet, meth, note = I.pet_series(nr, None); check(meth == "none" and np.all(np.isnan(pet)) and "широта" in note, "без широти ET₀ не розраховується (пояснення)")
pet, meth, note = I.pet_series(ser_from(D(2024, 6, 1), D(2024, 6, 10), tmean=15.0, prec=1.0), 48.75); check(meth == "none" and "tmax" in note, "лише tсер → ET₀ не розраховується (пояснення)")
gv = ser_from(D(2024, 6, 1), D(2024, 6, 10), tmax=27.0, tmin=14.0, et0=3.3, prec=1.0); pet, meth, note = I.pet_series(gv, 48.75); check(meth == "given" and np.allclose(pet, 3.3), "якщо ET₀ є в даних користувача – використовується вона")
noelev = ser_from(D(2024, 6, 1), D(2024, 6, 10), tmax=27.0, tmin=14.0, rad=22.0, wind=2.0, rh=60.0, prec=1.0); _, _, note = I.pet_series(noelev, 48.75); check("не задано" in note, "висоту не задано → про це повідомлено")

print("\n== 2. Індекс сухості (ЮНЕП)")
for ai, cls in ((0.01, "гіперарідний"), (0.049, "гіперарідний"), (0.05, "арідний"), (0.19, "арідний"), (0.20, "напівзасушливий"), (0.49, "напівзасушливий"), (0.50, "сухий субвологий"),
                (0.64, "сухий субвологий"), (0.65, "вологий"), (1.2, "вологий")):
    check(I.aridity_class(ai) == cls, f"AI = {ai} → {cls}")
check(I.aridity_class(float("nan")) == "" and I.aridity_class(None) == "", "NaN/None → порожньо")
y = ser_from(D(2021, 7, 1), D(2024, 6, 30), prec=1.5, tmax=25.0, tmin=10.0)
pet_arr = np.full(len(y), 3.0); rows = I.aridity_rows(y, pet_arr)
check([r["year"] for r in rows] == [2022, 2023], f"лише повні календарні роки: {[r['year'] for r in rows]} (2021 і 2024 покриті частково)")
check(abs(rows[0]["prec"] - 1.5 * 365) < 1e-9 and abs(rows[0]["pet"] - 3.0 * 365) < 1e-9 and abs(rows[0]["ai"] - 0.5) < 1e-12 and rows[0]["class"] == "сухий субвологий", "P = 547,5; PET = 1095; AI = 0,5 → «сухий субвологий»")
leap = ser_from(D(2024, 1, 1), D(2024, 12, 31), prec=1.0); r_ = I.aridity_rows(leap, np.full(len(leap), 2.0)); check(len(r_) == 1 and abs(r_[0]["prec"] - 366.0) < 1e-9, "високосний рік (366 діб) враховано")
pm = np.full(365, 1.0); pm[:10] = np.nan; sr = ser_from(D(2023, 1, 1), D(2023, 12, 31), prec=pm); r_ = I.aridity_rows(sr, np.full(365, 2.0))
check(len(r_) == 1 and abs(r_[0]["prec"] - 365.0) < 1e-9, "пропуски опадів (10 діб) компенсуються пропорційно, якщо їх менше 5 %")
bad = np.full(365, 1.0); bad[:60] = np.nan; check(I.aridity_rows(ser_from(D(2023, 1, 1), D(2023, 12, 31), prec=bad), np.full(365, 2.0)) == [], "понад 5 % пропусків → рік не розраховується")
check(I.aridity_rows(ser_from(D(2023, 1, 1), D(2023, 12, 31), tmax=20.0), np.full(365, 2.0)) == [] and I.aridity_rows(y, np.full(len(y), np.nan)) == [], "без опадів або без PET – порожньо")
check(abs(I.window_ai(300.0, 600.0) - 0.5) < 1e-12 and math.isnan(I.window_ai(300.0, 0.0)) and math.isnan(I.window_ai(float("nan"), 500.0)), "AI для довільного відрізка: P/PET; ділення на нуль → NaN")

print("\n== 3. Індекс Вінклера")
check(np.allclose(I.WINKLER_BOUNDS_C, [1388.889, 1666.667, 1944.444, 2222.222], atol=1e-3), "межі регіонів у °C·діб = 2500/3000/3500/4000 °F·діб × 5/9")
for w, reg in ((1000, "I"), (1388.8, "I"), (1389.0, "II"), (1666.0, "II"), (1667.0, "III"), (1944.0, "III"), (1945.0, "IV"), (2222.0, "IV"), (2223.0, "V"), (3000, "V")):
    check(I.winkler_region(w).startswith(reg + " ") or I.winkler_region(w).startswith(reg + "("), f"Вінклер {w} → регіон {reg}")
check(I.winkler_region(float("nan")) == "", "NaN → порожньо")
n_days = (D(2022, 10, 31) - D(2022, 4, 1)).days + 1; check(n_days == 214, "сезон Вінклера (пн. півкуля) – 214 діб")
s = ser_from(D(2022, 1, 1), D(2022, 12, 31), tmean=20.0, tmax=26.0, tmin=14.0, prec=0.0)
rw = I.vine_rows(s, 48.75); check(len(rw) == 1 and abs(rw[0]["winkler"] - 214 * 10.0) < 1e-9 and rw[0]["winkler_region"].startswith("IV"), f"tсер = 20 °C усі 214 діб → Σ(t − 10) = 2140 → регіон IV: {rw[0]['winkler']:.0f}")
cold = ser_from(D(2022, 1, 1), D(2022, 12, 31), tmean=5.0, tmax=9.0, tmin=1.0, prec=0.0); rc = I.vine_rows(cold, 48.75)
check(len(rc) == 1 and rc[0]["winkler"] == 0.0 and rc[0]["huglin"] == 0.0 and rc[0]["winkler_region"].startswith("I ") and rc[0]["huglin_code"] == "HI−3", "холодний рік (t < 10 °C): від'ємні внески обнуляються, індекс = 0")
mix = np.where(np.arange(365) % 2 == 0, 20.0, 0.0); sm = ser_from(D(2022, 1, 1), D(2022, 12, 31), tmean=mix, tmax=mix + 5, tmin=mix - 5, prec=0.0)
days_apr_oct = [D(2022, 1, 1) + dt.timedelta(days=i) for i in range(365) if D(2022, 4, 1) <= D(2022, 1, 1) + dt.timedelta(days=i) <= D(2022, 10, 31)]
exp_w = sum(10.0 for d in days_apr_oct if ((d - D(2022, 1, 1)).days % 2 == 0)); check(abs(I.vine_rows(sm, 48.75)[0]["winkler"] - exp_w) < 1e-9, f"чергування 20/0 °C: враховано лише теплі доби ({exp_w:.0f})")
part = ser_from(D(2022, 5, 1), D(2023, 12, 31), tmean=20.0, tmax=26.0, tmin=14.0, prec=0.0); rp = I.vine_rows(part, 48.75)
check([r["year"] for r in rp] == [2023], "сезон 2022 покритий неповністю (з 1 травня) – не розраховується")
gap = ser_from(D(2022, 1, 1), D(2022, 12, 31), tmean=np.where(np.arange(365) < 140, 20.0, 20.0), tmax=26.0, tmin=14.0, prec=0.0)
tmg = gap.get("tmean").copy(); tmg[100:140] = np.nan; gap2 = W.DailySeries(gap.dates, {"tmean": tmg, "tmax": gap.get("tmax"), "tmin": gap.get("tmin"), "prec": gap.get("prec")})
check(I.vine_rows(gap2, 48.75) == [] or math.isnan(I.vine_rows(gap2, 48.75)[0]["winkler"]), "понад 5 % пропусків температури в сезоні → індекс не розраховується")
south = ser_from(D(2021, 1, 1), D(2023, 12, 31), tmean=20.0, tmax=26.0, tmin=14.0, prec=0.0); rs_ = I.vine_rows(south, -34.0)
check([r["label"] for r in rs_] == ["2021/22", "2022/23"] and abs(rs_[0]["winkler"] - 10.0 * ((D(2022, 4, 30) - D(2021, 10, 1)).days + 1)) < 1e-9, f"південна півкуля: сезони {[r['label'] for r in rs_]}, вікно 1 жовтня – 30 квітня")
if have("xclim") and have("xarray"):
    import xarray as xr, pandas as pd
    from xclim.indices import growing_degree_days
    from xclim.core.calendar import select_time
    rg = np.random.default_rng(3); n = 365 * 3 + 1; d0 = D(2020, 1, 1); dts = [d0 + dt.timedelta(days=i) for i in range(n)]
    tm = 12 + 11 * np.sin(2 * np.pi * (np.arange(n) - 110) / 365) + rg.normal(0, 2.5, n)
    ss = W.DailySeries(dts, {"tmean": tm, "tmax": tm + 5, "tmin": tm - 5, "prec": np.zeros(n)}); mine = {r["year"]: r["winkler"] for r in I.vine_rows(ss, 45.0)}
    tas = xr.DataArray(tm, dims="time", coords={"time": pd.date_range("2020-01-01", periods=n, freq="D")}, attrs={"units": "degC"})
    ref = growing_degree_days(select_time(tas, date_bounds=("04-01", "11-01"), include_bounds=(True, False)), thresh="10 degC", freq="YS")
    refd = {int(pd.Timestamp(t.values).year): float(v) for t, v in zip(ref.time, ref.values)}
    wmax = max(abs(refd[y] - mine[y]) for y in mine if y in refd and mine[y] == mine[y]); check(wmax < 1e-6, f"Вінклер збігається з xclim.growing_degree_days (1 квітня – 31 жовтня): макс. |Δ| = {wmax:.1e}")
else: print("  (xclim не встановлено – порівняння пропущено)")

print("\n== 4. Індекс Югліна")
for la, k in ((0, 1.00), (35, 1.00), (40, 1.00), (40.01, 1.02), (42, 1.02), (42.5, 1.03), (44, 1.03), (45, 1.04), (46, 1.04), (47, 1.05), (48, 1.05), (48.75, 1.06), (50, 1.06), (50.5, 1.06), (60, 1.06), (-41, 1.02), (-34, 1.00)):
    check(I.huglin_k(la) == k, f"k({la}°) = {k:.2f}")
for hi, code in ((0, "HI−3"), (1500, "HI−3"), (1500.5, "HI−2"), (1800, "HI−2"), (1801, "HI−1"), (2100, "HI−1"), (2101, "HI+1"), (2400, "HI+1"), (2401, "HI+2"), (3000, "HI+2"), (3001, "HI+3")):
    check(I.huglin_class(hi)[0] == code, f"Югліна {hi} → {code}")
check(I.huglin_class(float("nan")) == ("", ""), "NaN → порожньо")
hs_ = ser_from(D(2022, 1, 1), D(2022, 12, 31), tmean=20.0, tmax=26.0, tmin=14.0, prec=0.0); rh_ = I.vine_rows(hs_, 48.75)[0]
check(abs(rh_["huglin"] - 183 * 13.0 * 1.06) < 1e-9 and rh_["huglin_code"] == "HI+2" and rh_["huglin_class"] == "теплий", f"ручний приклад: 183 доби × ((20−10)+(26−10))/2 × 1,06 = {183 * 13.0 * 1.06:.2f} → HI+2: {rh_['huglin']:.2f}")
check(abs(I.vine_rows(hs_, 40.0)[0]["huglin"] - 183 * 13.0) < 1e-9, "широта ≤ 40°: k = 1,00")
check(I.season_bounds(2022, 48.0, "huglin") == (D(2022, 4, 1), D(2022, 9, 30)) and I.season_bounds(2022, -30.0, "huglin") == (D(2022, 10, 1), D(2023, 3, 31)), "межі сезону Югліна: 1.04–30.09 (пн.) і 1.10–31.03 (пд.)")
check(I.season_bounds(2022, 48.0, "winkler") == (D(2022, 4, 1), D(2022, 10, 31)) and I.season_bounds(2022, -30.0, "winkler") == (D(2022, 10, 1), D(2023, 4, 30)), "межі сезону Вінклера: 1.04–31.10 (пн.) і 1.10–30.04 (пд.)")
check(I.vine_rows(hs_, None) == [], "без широти вінограрські індекси не розраховуються")
nt = W.DailySeries(hs_.dates, {"tmean": hs_.get("tmean"), "prec": hs_.get("prec")}); rr = I.vine_rows(nt, 48.75)
check(len(rr) == 1 and rr[0]["winkler"] == rr[0]["winkler"] and rr[0]["huglin"] != rr[0]["huglin"], "без tmax Югліна не розраховується, Вінклер – так")

if have("xclim") and have("xarray"):
    import xarray as xr, pandas as pd; from xclim.indices import huglin_index
    rg2 = np.random.default_rng(5); n = 365 * 4 + 1; d0 = D(2020, 1, 1); dts = [d0 + dt.timedelta(days=i) for i in range(n)]
    doy_ = np.array([d.timetuple().tm_yday for d in dts], float); tt = pd.date_range("2020-01-01", periods=n, freq="D")
    for la in (35.0, 40.0, 41.0, 42.0, 43.5, 45.0, 47.0, 48.75, 50.0, 52.0, -34.0):
        south_ = la < 0; base = 12 + 11 * np.sin(2 * np.pi * (doy_ - 110) / 365) * (-1 if south_ else 1)
        tm = base + rg2.normal(0, 2.5, n); tx = tm + rg2.uniform(3, 9, n); tn = tm - rg2.uniform(3, 8, n)
        ss = W.DailySeries(dts, {"tmean": tm, "tmax": tx, "tmin": tn, "prec": np.zeros(n)}); mine = {r["year"]: r["huglin"] for r in I.vine_rows(ss, la)}
        A = lambda v: xr.DataArray(v, dims="time", coords={"time": tt}, attrs={"units": "degC"}); L = xr.DataArray(la, attrs={"units": "degrees_north"}); kw = dict(method="huglin", cap_value=0.06)
        hi = huglin_index(A(tm), A(tx), lat=L, start_date="10-01", end_date="04-01", freq="YS-JUL", **kw) if south_ else huglin_index(A(tm), A(tx), lat=L, **kw)
        ref = {int(pd.Timestamp(tv.values).year): float(v) for tv, v in zip(hi.time, hi.values) if not np.isnan(v)}
        common = [y for y in mine if mine[y] == mine[y] and y in ref]; dmax = max(abs(ref[y] - mine[y]) for y in common)
        check(len(common) >= 3 and dmax < 1e-9, f"Югліна збігається з xclim (φ = {la}°, k = {I.huglin_k(la):.2f}, {len(common)} сезони): макс. |Δ| = {dmax:.1e}")
else: print("  (xclim не встановлено – порівняння Югліна пропущено)")

print("\n== 5. SPI")
for z, cls in ((-2.5, "екстремально сухо"), (-2.0, "екстремально сухо"), (-1.99, "дуже сухо"), (-1.5, "дуже сухо"), (-1.49, "помірно сухо"), (-1.0, "помірно сухо"), (-0.99, "норма"), (0, "норма"), (0.99, "норма"),
               (1.0, "помірно волого"), (1.49, "помірно волого"), (1.5, "дуже волого"), (1.99, "дуже волого"), (2.0, "екстремально волого"), (3, "екстремально волого")):
    check(I.spi_class(z) == cls, f"SPI {z} → {cls}")
check(I.spi_class(float("nan")) == "", "NaN → порожньо")
rg = np.random.default_rng(11); months = [(y, m) for y in range(1981, 2023) for m in range(1, 13)]
shape = np.array([2.5, 2.2, 2.6, 3.0, 3.4, 3.6, 3.2, 3.0, 2.8, 2.6, 2.7, 2.4]); scl = np.array([14, 12, 15, 17, 22, 28, 30, 24, 20, 17, 16, 15.])
tot = np.array([rg.gamma(shape[m - 1], scl[m - 1]) for y, m in months])
def daily_from(tot, months):
    dts, vals = [], []
    for (y, m), t in zip(months, tot):
        dim = calendar.monthrange(y, m)[1]
        for d in range(1, dim + 1): dts.append(D(y, m, d)); vals.append(t / dim)
    return W.DailySeries(dts, {"prec": vals})
ser = daily_from(tot, months); mt = I.monthly_totals(ser)
check(len(mt) == len(months) and np.allclose([x[2] for x in mt], tot), "місячні суми з добових відтворено точно (504 місяці)")
res = I.spi_table(ser, ref=(1991, 2020), scales=(1, 3, 6, 12)); mine = {k: np.array([r["spi"][k] for r in res["rows"]]) for k in (1, 3, 6, 12)}
yrs = np.array([r["year"] for r in res["rows"]]); inref = (yrs >= 1991) & (yrs <= 2020)
check(abs(np.nanmean(mine[1][inref])) < 0.01 and abs(np.nanstd(mine[1][inref]) - 1.0) < 0.02, f"SPI-1 в еталонному періоді має середнє {np.nanmean(mine[1][inref]):.3f} і SD {np.nanstd(mine[1][inref]):.3f} (≈ 0 і ≈ 1)")
check(all(np.isnan(mine[k][:k - 1]).all() and not np.isnan(mine[k][k - 1]) for k in (1, 3, 6, 12)), "перші k − 1 місяців ряду для SPI-k – NaN (недостатньо попередніх місяців)")
if have("standard_precip") and have("pandas"):
    import pandas as pd; from standard_precip.spi import SPI
    df = pd.DataFrame({"date": pd.date_range("1981-01-01", periods=len(months), freq="MS"), "precip": tot})
    for k in (1, 3, 6, 12):
        sp = SPI().calculate(df, "date", "precip", freq="M", scale=k, fit_type="mle", dist_type="gam", baseline_start=1991, baseline_end=2020)
        sa = sp[[c for c in sp.columns if c.endswith("calculated_index")][0]].values; ok = ~np.isnan(sa) & ~np.isnan(mine[k])
        check(ok.sum() > 450 and np.abs(sa[ok] - mine[k][ok]).max() < 1e-9, f"SPI-{k} збігається з пакетом standard-precip (MLE-гамма, ті самі роки): n = {ok.sum()}, макс. |Δ| = {np.abs(sa[ok] - mine[k][ok]).max():.1e}")
else: print("  (standard-precip не встановлено – порівняння пропущено)")
if have("xclim") and have("xarray"):
    import xarray as xr, pandas as pd; from xclim.indices import standardized_precipitation_index as xspi
    pr = xr.DataArray(np.array(ser.get("prec")), dims="time", coords={"time": pd.date_range("1981-01-01", periods=len(ser), freq="D")}, attrs={"units": "mm/d"})
    ref = xspi(pr, freq="MS", window=3, dist="gamma", method="ML", fitkwargs={"floc": 0}, cal_start="1991-01-01", cal_end="2020-12-31").values
    ok = ~np.isnan(ref) & ~np.isnan(mine[3]); check(np.corrcoef(ref[ok], mine[3][ok])[0, 1] > 0.999 and np.abs(ref[ok] - mine[3][ok]).mean() < 0.03, f"SPI-3 узгоджується з xclim (кореляція {np.corrcoef(ref[ok], mine[3][ok])[0, 1]:.5f}; xclim усереднює добові потоки, тому точного збігу немає)")
x_ref = rg.gamma(3.0, 20.0, 60); a_, b_ = 3.0, 20.0
z_, par = I.spi_from_sample(x_ref, np.array([40.0, 60.0, 90.0])); aa, bb, q = par
check(q == 0.0 and np.allclose(z_, stats.norm.ppf(stats.gamma.cdf([40.0, 60.0, 90.0], aa, scale=bb))), "SPI = Φ⁻¹(G(x; a, β)) за підігнаними параметрами (без нулів)")
check(np.all(np.diff(I.spi_from_sample(x_ref, np.linspace(5, 200, 40))[0]) > 0), "SPI монотонно зростає з опадами")
xz = np.concatenate([rg.gamma(2.0, 15.0, 40), np.zeros(20)]); zz, parz = I.spi_from_sample(xz, np.array([0.0, 30.0]))
check(abs(parz[2] - 20 / 60) < 1e-12 and abs(zz[0] - stats.norm.ppf(20 / 60)) < 1e-12, f"нульові суми: q = 20/60, SPI(0) = Φ⁻¹(q) = {zz[0]:.3f}")
check(abs(zz[1] - stats.norm.ppf(parz[2] + (1 - parz[2]) * stats.gamma.cdf(30.0, parz[0], scale=parz[1]))) < 1e-12, "H(x) = q + (1 − q)·G(x) для ненульових сум")
zn, pn = I.spi_from_sample(x_ref[:12], np.array([50.0])); check(pn is None and np.isnan(zn[0]), "замало еталонних значень (< 20) → NaN, а не вигадане число")
zc, pc = I.spi_from_sample(np.full(30, 5.0), np.array([5.0])); check(pc is None and np.isnan(zc[0]), "стала вибірка (немає варіації) → NaN")
zin, _ = I.spi_from_sample(x_ref, np.array([float("nan"), 50.0])); check(np.isnan(zin[0]) and not np.isnan(zin[1]), "пропущене нове значення → NaN")
zex, _ = I.spi_from_sample(x_ref, np.array([1e6, 1e-9])); check(np.all(np.isfinite(zex)) and zex[0] > 4 and zex[1] < -3, "крайні значення обмежено (±4,75), без нескінченності")
# календар і покриття
part = ser_from(D(2020, 1, 15), D(2020, 6, 20), prec=1.0); mp_ = I.monthly_totals(part)
check([(y, m) for y, m, v in mp_] == [(2020, 1), (2020, 2), (2020, 3), (2020, 4), (2020, 5), (2020, 6)] and math.isnan(mp_[0][2]) and math.isnan(mp_[-1][2]) and abs(mp_[1][2] - 29.0) < 1e-12, "неповні перший і останній місяці → NaN; лютий 2020 = 29 мм")
pv = np.ones(31); pv[:2] = np.nan; sj = W.DailySeries([D(2021, 1, d) for d in range(1, 32)], {"prec": pv}); check(abs(I.monthly_totals(sj)[0][2] - 31.0) < 1e-9, "2 пропущені доби з 31 компенсуються пропорційно (сума 31 мм)")
pv2 = np.ones(31); pv2[:6] = np.nan; sj2 = W.DailySeries([D(2021, 1, d) for d in range(1, 32)], {"prec": pv2}); check(math.isnan(I.monthly_totals(sj2)[0][2]), "понад 10 % пропущених діб у місяці → NaN")
check(I.monthly_totals(W.DailySeries([D(2021, 1, 1)], {"tmean": [1.0]})) == [], "без опадів → порожньо")
res_s = I.spi_table(ser, ref=(1991, 2020), scales=(3,), study=(D(2020, 1, 15), D(2021, 3, 10)))
check([r["label"] for r in res_s["rows"]] == [f"{m:02d}.{y}" for y, m in [(2020, 1), (2020, 2), (2020, 3), (2020, 4), (2020, 5), (2020, 6), (2020, 7), (2020, 8), (2020, 9), (2020, 10), (2020, 11), (2020, 12), (2021, 1), (2021, 2), (2021, 3)]], "період дослідження обрізає таблицю за місяцями (з 01.2020 до 03.2021)")
jan = [r for r in res["rows"] if (r["year"], r["month"]) == (2005, 1)][0]; i_ = months.index((2005, 1)); expect3 = tot[i_] + tot[i_ - 1] + tot[i_ - 2]
check(abs(sum(tot[i_ - 2:i_ + 1]) - expect3) < 1e-12 and not math.isnan(jan["spi"][3]), "SPI-3 для січня використовує листопад і грудень попереднього року")
short = daily_from(tot[:12 * 15], months[:12 * 15]); rs3 = I.spi_table(short, ref=(1981, 1995), scales=(1,)); check(any("замало" in w for w in rs3["warnings"]) and all(math.isnan(r["spi"][1]) for r in rs3["rows"]), "еталон < 20 років: попередження, SPI не розраховано")
mid = daily_from(tot[:12 * 25], months[:12 * 25]); rm_ = I.spi_table(mid, ref=(1981, 2005), scales=(1,)); check(any("WMO" in w and "25" in w for w in rm_["warnings"]) and not math.isnan(rm_["rows"][5]["spi"][1]), "еталон 25 років: розрахунок є, з попередженням WMO (≥ 30 років)")
check(I.spi_table(W.DailySeries([D(2021, 1, 1)], {"tmean": [1.0]}))["warnings"] != [], "ряд без опадів: зрозуміле попередження")
r0 = res["rows"][100]; check(r0["class"][1] == I.spi_class(r0["spi"][1]) and set(r0["spi"]) == {1, 3, 6, 12}, "у рядку таблиці є SPI й клас для кожного масштабу")
print("\n" + "=" * 56)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ МІЖНАРОДНИХ ПОКАЗНИКІВ ПРОЙДЕНО")
