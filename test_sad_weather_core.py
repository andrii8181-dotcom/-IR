# test_sad_weather_core.py – перевірка ядра модуля «Погода» (без мережі й без tkinter)
# Запуск:  python test_sad_weather_core.py
import os, sys, json, math, tempfile, shutil, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sad_weather_core as W

FAIL = []
def check(cond, msg):
    print(("  [OK]   " if cond else "  [FAIL] ") + msg)
    if not cond: FAIL.append(msg)
def close(a, b, tol=1e-6): return abs(a - b) <= tol
D = dt.date

def const_series(spec):
    """spec: [(start, end, tmean, prec_total)] → добовий ряд зі сталою t і рівномірними опадами."""
    dates, tm, pr = [], [], []
    for a, b, t, p in spec:
        n = (b - a).days + 1
        for i in range(n):
            dates.append(a + dt.timedelta(days=i)); tm.append(t); pr.append(p / n)
    return W.DailySeries(dates, {"tmean": tm, "prec": pr})

# ─────────────────────────────────────────────────────────
print("== 1. Координати")
for txt, kind, exp in [("48.75","lat",48.75), ("48,75","lat",48.75), ("-33.5","lat",-33.5),
                       ("48°45'N","lat",48.75), ("48 45 00","lat",48.75), ("48°45'S","lat",-48.75),
                       ("S 48 45","lat",-48.75), ("-48°45'","lat",-48.75),
                       ("30°13'E","lon",30.21666667), ("30.22","lon",30.22), ("30°13'W","lon",-30.21666667),
                       ("48°45'30\"N","lat",48.758333333)]:
    try: v = W.parse_coord(txt, kind); check(close(v, exp, 1e-6), f"{txt!r} → {v:.6f}")
    except Exception as e: check(False, f"{txt!r} дав помилку {e}")
for txt, kind in [("91","lat"), ("abc","lat"), ("","lat"), ("181","lon"), ("48°75'","lat"),
                  ("48E","lat"), ("30N","lon"), ("1 2 3 4","lat"), ("N S 30","lat")]:
    try: W.parse_coord(txt, kind); check(False, f"{txt!r} ({kind}) мало б відхилитись")
    except ValueError: check(True, f"{txt!r} ({kind}) відхилено")

# ─────────────────────────────────────────────────────────
print("\n== 2. ГТК – відтворення прикладів джерела (табл. 6.1, декадний облік)")
Y = 2023
dec = [  # (початок, кінець, tсер, опади)
 (D(Y,4,1),D(Y,4,10),10.8,15.6),(D(Y,4,11),D(Y,4,20),8.5,11.0),(D(Y,4,21),D(Y,4,30),12.3,4.2),
 (D(Y,5,1),D(Y,5,10),14.3,13.8),(D(Y,5,11),D(Y,5,20),16.4,14.2),(D(Y,5,21),D(Y,5,31),18.5,22.9),
 (D(Y,6,1),D(Y,6,10),19.6,17.6),(D(Y,6,11),D(Y,6,20),21.6,16.3),(D(Y,6,21),D(Y,6,30),21.9,19.7)]
ser = const_series(dec)
rows = W.table_by_groups(ser, W.decade_key, W.decade_label, htc_method="decade")
exp_cls = ["достатньо волого", None, "дуже сильна посуха", "достатньо волого", "слабка посуха",
           "достатньо волого", "слабка посуха", "слабка посуха", "слабка посуха"]
exp_val = [1.4, None, 0.3, 1.0, 0.9, 1.1, 0.9, 0.8, 0.9]
check(len(rows) == 9, "9 декад")
for r, ec, ev in zip(rows, exp_cls, exp_val):
    if ev is None:
        check(math.isnan(r["htc"]), f"{r['label']}: активних температур немає → ГТК не розраховано")
    else:
        got = round(r["htc"] + 1e-9, 1)
        check(got == ev and r["htc_class"] == ec, f"{r['label']}: ГТК {r['htc']:.3f} → {got} «{r['htc_class']}»")
check(close(rows[2]["htc_sum_t"], 123.0, 1e-6), "Σt 3-ї декади квітня = 123 (12,3 × 10 діб)")
check(close(rows[5]["htc_sum_t"], 203.5, 1e-6), "Σt 3-ї декади травня = 203,5 (18,5 × 11 діб; у джерелі округлено до 204)")
whole = W.htc_period(ser, "decade")
check(close(whole["sum_r"], 135.3, 1e-6), f"ΣR за період = 135,3 мм (є {whole['sum_r']:.2f})")
check(close(whole["sum_t"], 1372.5, 1e-6), f"Σt за період = 1372,5 (джерело: 1373; є {whole['sum_t']:.1f})")
check(round(whole["htc"], 1) == 1.0 and W.htc_class(whole["htc"])[0] == "достатньо волого",
      f"ГТК за період {whole['htc']:.3f} → «{W.htc_class(whole['htc'])[0]}» (джерело: період достатньо вологий)")
naive = W.htc(ser.get("prec"), ser.get("tmean"), "calendar")
check(round(naive["htc"], 1) == 0.9, f"Контроль: наївне «все за всі доби» дало б {naive['htc']:.3f}→0,9 – інший висновок, "
      f"тому нашу реалізацію зроблено за джерелом")

print("\n== 3. ГТК – табл. 6.2 (місячний облік)")
mon = [(D(Y,4,1),D(Y,4,30),10.5,55.3),(D(Y,5,1),D(Y,5,31),16.4,50.9),(D(Y,6,1),D(Y,6,30),21.0,53.6),
       (D(Y,7,1),D(Y,7,31),24.0,37.6),(D(Y,8,1),D(Y,8,31),23.1,36.0),(D(Y,9,1),D(Y,9,30),17.0,38.2)]
ser2 = const_series(mon)
rows2 = W.table_by_groups(ser2, W.month_key, W.month_label, htc_method="month")
exp2 = [(1.8,"надмірно волого"),(1.0,"достатньо волого"),(0.9,"слабка посуха"),
        (0.5,"сильна посуха"),(0.5,"сильна посуха"),(0.7,"середня посуха")]
for r, (ev, ec) in zip(rows2, exp2):
    check(round(r["htc"] + 1e-9, 1) == ev and r["htc_class"] == ec, f"{r['label']}: {r['htc']:.3f} → {ev} «{r['htc_class']}»")
w2 = W.htc_period(ser2, "month")
check(round(w2["htc"], 1) == 0.8 and W.htc_class(w2["htc"])[0] == "слабка посуха",
      f"Період: {w2['htc']:.3f} → 0,8 «слабка посуха» (у джерелі: період слабко посушливий)")
check(close(w2["sum_r"], 271.6, 1e-6), "ΣR за період = 271,6 мм")

print("\n== 4. Клас ГТК: округлення до 0,1 (ROUND_HALF_UP) та межі")
for v, exp in [(0.349,"дуже сильна посуха"),(0.35,"сильна посуха"),(0.54,"сильна посуха"),(0.55,"середня посуха"),
               (0.74,"середня посуха"),(0.75,"слабка посуха"),(0.94,"слабка посуха"),(0.95,"достатньо волого"),
               (1.54,"достатньо волого"),(1.55,"надмірно волого"),(2.4,"надмірно волого"),(float("nan"),"н/д")]:
    got = W.htc_class(v)[0]; check(got == exp, f"ГТК {v} → {got}")

print("\n== 5. ГТК добовий метод і крайні випадки")
s = const_series([(D(Y,7,1), D(Y,7,10), 20.0, 30.0)])
check(close(W.htc(s.get("prec"), s.get("tmean"), "daily")["htc"], 30.0/(0.1*200.0)),
      "добовий: 30 мм / (0,1·200) = 1,5")
cold = const_series([(D(Y,1,1), D(Y,1,31), -3.0, 40.0)])
check(math.isnan(W.htc_period(cold, "decade")["htc"]) and math.isnan(W.htc_period(cold, "daily")["htc"]),
      "взимку (немає активних температур) ГТК не розраховується")
check(math.isnan(W.htc(np.array([]), np.array([]), "daily")["htc"]), "порожній ряд → NaN без помилки")
mixed = W.DailySeries([D(Y,7,1)+dt.timedelta(days=i) for i in range(4)],
                      {"tmean": [20, 8, 22, 5], "prec": [2.0, 10.0, 4.0, 1.0]})
dm = W.htc(mixed.get("prec"), mixed.get("tmean"), "daily")
check(dm["days"] == 2 and close(dm["sum_r"], 6.0) and close(dm["sum_t"], 42.0),
      "добовий метод враховує лише доби з t>10 і опади лише цих діб")

# ─────────────────────────────────────────────────────────
print("\n== 6. САТ / СЕТ")
t = np.array([4, 5, 6, 10, 10.5, 12, 31, 35])
check(close(W.active_temp_sum(t, 5), 6+10+10.5+12+31+35), "САТ>5: поріг строго «вище»")
check(close(W.active_temp_sum(t, 10), 10.5+12+31+35), "САТ>10 (10,0 не входить)")
check(close(W.effective_temp_sum(t, 10), 0.5+2+21+25), "СЕТ (base 10)")
check(close(W.effective_temp_sum(t, 10, upper=30), 0.5+2+20+20), "СЕТ із верхнім обмеженням 30 °C")
check(W.active_temp_sum([], 10) == 0.0 and W.effective_temp_sum([2, 3], 10) == 0.0, "порожні/холодні → 0")

# ─────────────────────────────────────────────────────────
print("\n== 7. period_stats: опади, посушливі періоди, заморозки, екстремуми")
dates = [D(2024,4,1)+dt.timedelta(days=i) for i in range(10)]
ser3 = W.DailySeries(dates, {
    "tmax": [8, 12, 16, 20, 26, 31, 36, 24, 18, 14], "tmin": [-3, -1, 0, 2, 8, 14, 18, 10, 4, -2],
    "prec": [0, 0, 0, 0.05, 1.0, 12.0, 0, 0, 0.5, 3.0]})
check(ser3.meta.get("tmean_derived") is True, "tmean виведено з (tmax+tmin)/2 з позначкою")
st = W.period_stats(ser3)
check(st["days_frost"] == 3, "доби з tmin<0: рівно 0 °C не заморозок")
check(st["days_tmax25"] == 3 and st["days_tmax30"] == 2 and st["days_tmax35"] == 1, "доби tmax ≥25/30/35")
check(st["prec_days_01"] == 4 and st["prec_days_1"] == 3 and st["prec_days_10"] == 1,
      f"доби з опадами ≥0,1/≥1/≥10 мм (1,0 мм входить у «≥1»): {st['prec_days_01']}/{st['prec_days_1']}/{st['prec_days_10']}")
check(st["dry_spell_max"] == 4, f"найдовший сухий період (<1 мм): {st['dry_spell_max']} діб")
check(close(st["prec_sum"], 16.55), "сума опадів")
check(close(st["tmax_abs"], 36) and close(st["tmin_abs"], -3), "абсолютні екстремуми")
fe = W.frost_events(ser3, 0.0)
check([e[0].day for e in fe] == [1, 2, 10], "перелік заморозкових діб")
check(len(W.frost_events(ser3, -2.0)) == 1 and W.frost_events(ser3, -2.0)[0][0].day == 1, "поріг −2 °C")

print("\n== 8. Дати переходу через поріг")
n = 60
tm = [2]*20 + [6, 4, 6, 7, 8, 9, 8, 9, 10, 11] + [12]*10 + [8]*20
ser4 = W.DailySeries([D(2024,3,1)+dt.timedelta(days=i) for i in range(n)], {"tmean": tm})
td = W.threshold_dates(ser4, 5.0, run=5)
check(td["start"] == D(2024,3,23), f"початок ≥5 °C: {td['start']} (перші 5 діб поспіль з 23.03)")
check(td["end"] == ser4.dates[-1] and td["end_after_window"], "кінець – за межами вікна → позначено")
tdw = W.threshold_dates(W.DailySeries([D(2024,3,1)+dt.timedelta(days=i) for i in range(10)], {"tmean":[9]*10}), 5.0)
check(tdw["start_before_window"], "якщо ряд починається вже вище порога → «до початку вікна»")
check(W.threshold_dates(W.DailySeries([D(2024,3,1)+dt.timedelta(days=i) for i in range(10)], {"tmean":[1]*10}), 5.0)["start"] is None,
      "поріг не досягнуто → None")

# ─────────────────────────────────────────────────────────
print("\n== 9. NASA POWER: розбір, пропуски -999, одиниці")
def nasa_payload(d0, n, rad_units="MJ/m^2/day", rad_scale=1.0):
    ds = [d0 + dt.timedelta(days=i) for i in range(n)]
    keys = [d.strftime("%Y%m%d") for d in ds]
    par = {"T2M": {k: 10.0 + i for i, k in enumerate(keys)},
           "T2M_MAX": {k: 15.0 + i for i, k in enumerate(keys)},
           "T2M_MIN": {k: 5.0 + i for i, k in enumerate(keys)},
           "PRECTOTCORR": {k: (-999.0 if i == 2 else 1.5) for i, k in enumerate(keys)},
           "RH2M": {k: 70.0 for k in keys}, "WS2M": {k: 3.0 for k in keys},
           "ALLSKY_SFC_SW_DWN": {k: 20.0 * rad_scale for k in keys}}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [30.2218, 48.7484, 212.5]},
            "properties": {"parameter": par},
            "header": {"title": "NASA/POWER CERES/MERRA2 Native Resolution Daily Data",
                       "api": {"version": "v2.6", "name": "POWER Daily API"}, "fill_value": -999.0,
                       "time_standard": "LST"},
            "messages": [],
            "parameters": {"ALLSKY_SFC_SW_DWN": {"units": rad_units}, "T2M": {"units": "C"},
                           "WS2M": {"units": "m/s"}, "PRECTOTCORR": {"units": "mm/day"}}}
ps = W.parse_nasa(nasa_payload(D(2024,5,1), 5))
check(len(ps) == 5 and ps.dates[0] == D(2024,5,1), "5 діб розібрано")
check(math.isnan(ps.get("prec")[2]) and ps.get("prec")[0] == 1.5, "-999 → NaN")
check(close(ps.get("rad")[0], 20.0), "радіація MJ/m²/добу без змін")
ps2 = W.parse_nasa(nasa_payload(D(2024,5,1), 3, "kW-hr/m^2/day", 5.0))
check(close(ps2.get("rad")[0], (20.0*5.0)*3.6), "kWh/м²/добу → МДж/м² (×3,6)")
check(ps.meta.get("time_standard") == "LST" and ps.meta.get("grid_elevation_m") == 212.5, "метадані (LST, висота)")
for bad in [{}, {"properties": {}}, {"messages": ["Parameter(s) invalid"]}]:
    try: W.parse_nasa(bad); check(False, "некоректна відповідь мала б дати помилку")
    except W.WeatherError: check(True, f"некоректна відповідь {str(bad)[:40]} → WeatherError")

# ─────────────────────────────────────────────────────────
print("\n== 11. Завантаження: чанки по роках, повтори; кешу немає")
calls = []
def getter_nasa(url):
    calls.append(url)
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(url).query)
    a = dt.datetime.strptime(q["start"][0], "%Y%m%d").date(); b = dt.datetime.strptime(q["end"][0], "%Y%m%d").date()
    return 200, json.dumps(nasa_payload(a, (b - a).days + 1))
slept = []
d0, d1 = D(2021,11,15), D(2023,2,10)
ser = W.fetch_nasa(48.75, 30.22, d0, d1, getter=getter_nasa, sleep=slept.append, today=D(2024,1,1))
check(len(calls) == 3, f"період 2021-11…2023-02 → 3 запити (по роках), було {len(calls)}")
check(all("community=AG" in u and "format=JSON" in u for u in calls), "параметри запиту: community=AG, format=JSON")
check(all(len(u.split("parameters=")[1].split("&")[0].split(",")) <= 20 for u in calls), "≤ 20 параметрів на запит")
check(len(ser) == (d1 - d0).days + 1 and ser.dates[0] == d0 and ser.dates[-1] == d1, "об'єднаний ряд без пропусків діб")
check(len(slept) == 2 and all(s == 1.0 for s in slept), "ввічлива пауза 1 с між запитами")
n_before = len(calls)
W.fetch_nasa(48.75, 30.22, d0, d1, getter=getter_nasa, sleep=slept.append, today=D(2024,1,1))
check(len(calls) == n_before + 3, "повторний запит знову йде в мережу: кешу немає, дані завантажуються щоразу заново")
check(ser.meta["retrieved_at"][:4] == str(dt.date.today().year), "дата отримання збережена в метаданих")

check(not hasattr(W, "cache_get") and not hasattr(W, "cache_put") and not hasattr(W, "cache_dir"), "кеш видалено з ядра")
import inspect
check("use_cache" not in inspect.signature(W.fetch_nasa).parameters, "параметра use_cache більше немає")

# повтори при 429
state = {"n": 0}
def flaky(url):
    state["n"] += 1
    if state["n"] <= 2: return 429, "Too Many Requests"
    return 200, json.dumps(nasa_payload(D(2020,1,1), 5))
slept2, msgs = [], []
sr = W.fetch_nasa(48.75, 30.22, D(2020,1,1), D(2020,1,5), getter=flaky, sleep=slept2.append,
                  progress=msgs.append)
check(state["n"] == 3 and slept2 == [5, 15], f"429 двічі → очікування {slept2} і успіх із 3-ї спроби")
check(any("повтор" in m for m in msgs), "користувачу показано повідомлення про очікування")
def always429(url): return 429, "x"
try: W.fetch_nasa(48.75, 30.22, D(2020,1,1), D(2020,1,5), getter=always429, sleep=lambda s: None); check(False, "мало впасти")
except W.WeatherError as e: check("429" in str(e), "після 4 спроб – зрозуміла помилка з кодом")
def bad400(url): return 400, '{"messages":["start date before 19810101"]}'
try: W.fetch_nasa(48.75, 30.22, D(2020,1,1), D(2020,1,5), getter=bad400, sleep=lambda s: None); check(False, "мало впасти")
except W.WeatherError as e: check("400" in str(e), "400 не повторюється, причина показана")
def offline(url): raise W.WeatherError("Немає з'єднання з сервером (x)")
try: W.fetch_nasa(48.75, 30.22, D(2020,1,1), D(2020,1,5), getter=offline); check(False, "мало впасти")
except W.WeatherError as e: check("з'єднання" in str(e), "офлайн → зрозуміле повідомлення")

# геокодер OpenStreetMap (Nominatim)
seen_geo = []
def geo(url):
    seen_geo.append(url)
    return 200, json.dumps([{"lat": "48.7484", "lon": "30.2218", "display_name": "Умань, Уманська міська громада, Черкаська область, Україна", "type": "city"},
                            {"lat": "bad", "lon": "1", "display_name": "зіпсований запис"},
                            {"lat": "48.9", "lon": "30.1", "name": "Умань (село)"}])
g = W.geocode("Умань", getter=geo)
check(len(g) == 2 and g[0]["lat"] == 48.7484 and "Черкаська" in g[0]["label"] and g[0]["kind"] == "city", "геокодер Nominatim розібрано; запис із некоректними координатами пропущено")
check("nominatim.openstreetmap.org/search" in seen_geo[0] and "format=jsonv2" in seen_geo[0] and "accept-language=uk" in seen_geo[0] and "limit=8" in seen_geo[0], "запит: сервер Nominatim, jsonv2, мова uk, ліміт")
check(W.geocode("zzzz", getter=lambda u: (200, "[]")) == [], "порожня відповідь → порожній список")
for bad, frag in ((lambda u: (503, "x"), "HTTP 503"), (lambda u: (200, "{}"), "неочікувану"), (lambda u: (200, "не json"), "некоректну")):
    try: W.geocode("x", getter=bad); check(False, "мало впасти")
    except W.WeatherError as e: check(frag in str(e), f"помилка геокодера: «{frag}»")
check("OpenStreetMap" in W.OSM_ATTRIBUTION and "ODbL" in W.OSM_ATTRIBUTION, "атрибуція OpenStreetMap збережена в ядрі")

# ─────────────────────────────────────────────────────────
print("\n== 12. Власний файл (CSV)")
csv_text = "Дата;Tсер;Tмакс;Tмін;Опади, мм\n01.05.2024;12,5;18,2;6,1;0,0\n02.05.2024;13,1;19,0;7,0;2,4\nbad;1;2;3;4\n03.05.2024;;20,0;8,0;-\n"
hd, rw = W.read_table_text(csv_text)
mp = W.guess_columns(hd)
check(mp == {"date": 0, "tmax": 2, "tmin": 3, "tmean": 1, "prec": 4}, f"авторозпізнавання стовпців: {mp}")
sf = W.series_from_table(hd, rw, mp)
check(len(sf) == 3 and sf.meta["bad_rows"] == 1, "3 коректні рядки, 1 хибний пропущено й пораховано")
check(close(sf.get("tmean")[0], 12.5) and math.isnan(sf.get("tmean")[2]) and math.isnan(sf.get("prec")[2]),
      "десяткова кома, порожнє/«-» → NaN")

# ─────────────────────────────────────────────────────────
print("\n== 12б. Розпізнавання стовпців у різних назвах")
for hdr, exp in [(["Дата","t","Опади"], {"date":0,"tmean":1,"prec":2}),
                 (["date","T, °C","tmax","tmin","rain"], {"date":0,"tmax":2,"tmin":3,"prec":4,"tmean":1}),
                 (["День","Температура","Опади, мм"], {"date":0,"tmean":1,"prec":2}),
                 (["Дата","tсер","Tмакс","Tмін"], {"date":0,"tmax":2,"tmin":3,"tmean":1})]:
    got = W.guess_columns(hdr); check(got == exp, f"{hdr} → {got}")
check("tmean" not in W.guess_columns(["Дата","вітер","Опади"]), "нерозпізнану температуру не вигадує")

print("\n== 13. Норма й аномалії")
yrs = {}
for yr, tshift, pmul in [(2018, 0.0, 1.0), (2019, 1.0, 0.8), (2020, -1.0, 1.2)]:
    a, b = W.window_for_year(yr, 4, 1, 10, 31)
    dts = [a + dt.timedelta(days=i) for i in range((b - a).days + 1)]
    yrs[yr] = W.DailySeries(dts, {"tmean": [15.0 + tshift]*len(dts), "prec": [2.0*pmul]*len(dts)})
norm, used = W.normal_from_years(yrs)
check(used == [2018, 2019, 2020] and close(norm["tmean"], 15.0), "норма t = 15,0")
check(close(norm["prec_sum"], 2.0*214*1.0, 1e-6), f"норма опадів = {norm['prec_sum']:.1f}")
an = W.anomaly_row(W.period_stats(yrs[2019]), norm)
check(close(an["d_tmean"], 1.0) and close(an["prec_pct"], 80.0), f"2019: Δt=+1,0; опади {an['prec_pct']:.0f}% норми")
check(W.precip_deviation_class(80.0) == "в межах норми" and W.precip_deviation_class(79.9) == "суттєво нижче норми"
      and W.precip_deviation_class(120.1) == "суттєво вище норми", "відхилення >20 % – суттєві (джерело ЖДТУ)")
a, b = W.window_for_year(2023, 2, 29, 3, 1)
check(a == D(2023,2,28), "29.02 у невисокосний рік → 28.02")
a, b = W.window_for_year(2024, 11, 1, 3, 31)
check(a == D(2024,11,1) and b == D(2025,3,31), "вікно через новий рік (листопад–березень)")

# ─────────────────────────────────────────────────────────
print("\n== 14. Попередження про якість і текст методики")
today = D(2024, 10, 9)
sr = const_series([(D(2024,10,1), D(2024,10,8), 10.0, 8.0)])
notes = W.quality_notes(sr, "nasa", D(2024,10,1), D(2024,10,9), today=today)
check(any("попередні" in n for n in notes) and any("реаналізу" in n for n in notes), "NASA, свіжі дані → 2 попередження")
check(any("діб із запитаних" in n for n in notes), "нестача діб повідомлена")
notes2 = W.quality_notes(const_series([(D(2015,5,1), D(2015,5,31), 10.0, 8.0)]), "nasa", D(2015,5,1), D(2015,5,31), today=today)
check(not any("попередні" in n for n in notes2) and any("метеостанції" in n for n in notes2),
      "давні дані: без попередження про «швидкий перегляд», з порадою щодо станції")
sh = W.fetch_nasa(48.75, 30.22, D(2020,6,1), D(2020,6,5), getter=getter_nasa, sleep=lambda s: None)
par = W.methods_paragraph(sh, D(2020,6,1), D(2020,6,5), 48.75, 30.22, "nasa", 10.0, "decade")
check("NASA POWER" in par and "MERRA-2" in par and "ГТК = ΣR / (0,1·Σt)" in par and "48,7500° пн. ш." in par and "30,2200° сх. д." in par,
      "абзац методики містить джерело, формулу ГТК і координати")
check("Селянінова" in par and "Умови зволоження оцінювали за значенням ГТК" in par and W.HTC_SCALE_TEXT in par, "є визначення ГТК за Селяніновим і шкала умов зволоження")
for bad in ("Польов", "Божко", "Вольвач", "Основи агрометеорології", "ТЕС, 2004", "подано за"):
    check(bad not in par and bad not in W.HTC_SCALE_TEXT, f"у тексті методики немає згадки «{bad}»")
check(not hasattr(W, "HTC_SOURCE"), "посилання на джерело градації ГТК видалено з ядра")
check("NASA Langley" in " ".join(W.citation_block("nasa")), "подяка NASA в експорті")
check(W.citation_block("openmeteo") == [] and W.licence_notice("openmeteo") == "", "Open-Meteo: джерело більше не підтримується (немає цитувань і ліцензійних приміток)")
check("NASA" in W.licence_notice("nasa"), "примітка про умови NASA POWER")
check(set(W.SOURCE_TITLES) == {"nasa", "file"} and set(W.SOURCE_MIN_DATE) == {"nasa"} and set(W.SOURCE_LAG_DAYS) == {"nasa"}, "джерела: лише NASA POWER і власні дані")
check(not any(hasattr(W, n) for n in ("fetch_openmeteo", "parse_om", "estimate_om_calls", "OM_URL", "OM_CITES", "PRESET_PLACES")), "Open-Meteo і швидкий вибір міст видалено з ядра")


# ─────────────────────────────────────────────────────────
print("\n== 15. Вікна за роками, періоди між замірами, звіт, погодний набір")
def synth(d0, d1):
    dts = []; cur = d0
    while cur <= d1: dts.append(cur); cur += dt.timedelta(days=1)
    doy = np.array([d.timetuple().tm_yday for d in dts], float)
    tm = 9.0 + 11.0 * np.sin(2*np.pi*(doy-110)/365.0)
    pr = np.where((np.arange(len(dts)) % 4) == 0, 5.0, 0.0)
    return W.DailySeries(dts, {"tmean": tm, "tmax": tm+4, "tmin": tm-4, "prec": pr})
big = synth(D(2022,1,1), D(2024,12,31))
okw, skw = W.year_windows(big, (4,1,10,31))
check([y for y,_,_,_ in okw] == [2022,2023,2024] and not skw, "3 повних вікна 01.04–31.10 у 2022–2024")
part = big.slice(D(2022,6,1), D(2024,8,31))
okp, skp = W.year_windows(part, (4,1,10,31))
check([y for y,_,_,_ in okp] == [2023] and sorted(y for y,_,_ in skp) == [2022, 2024],
      "часткові вікна 2022 і 2024 виключено й повідомлено, 2023 – повне")
okx, skx = W.year_windows(big, (11,1,3,31))
check([y for y,_,_,_ in okx] == [2022, 2023], "вікно листопад–березень через Новий рік: 2022/23, 2023/24")
check(okx[0][1] == D(2022,11,1) and okx[0][2] == D(2023,3,31), "межі вікна 2022/23 коректні")
rows, sk = W.by_year_table(big, (4,1,10,31), htc_method="decade")
check(len(rows) == 3 and all("year" in r and "water_balance" in r for r in rows), "таблиця за роками")
check(all(r["days"] == 214 for r in rows), "вікно 01.04–31.10 = 214 діб")

dts = [D(2024,5,15), D(2024,5,29), D(2024,6,12)]
bt = W.intervals_from_dates(dts, season_start=D(2024,5,1), mode="between")
check([(a, b) for _, a, b in bt] == [(D(2024,5,1), D(2024,5,15)), (D(2024,5,16), D(2024,5,29)), (D(2024,5,30), D(2024,6,12))],
      "між замірами: інтервали не перетинаються й не мають розривів")
cu = W.intervals_from_dates(dts, season_start=D(2024,5,1), mode="cumulative")
check([a for _, a, _ in cu] == [D(2024,5,1)]*3 and [b for _, _, b in cu] == dts, "нагромадження від початку сезону")
nb = W.intervals_from_dates(dts, season_start=None, mode="between")
check(len(nb) == 2 and nb[0][1] == D(2024,5,16) and nb[1][1] == D(2024,5,30), "без початку сезону перший замір не має інтервалу (перший інтервал – з 16.05)")
try: W.intervals_from_dates(dts, None, "cumulative"); check(False, "мало впасти")
except ValueError: check(True, "нагромадження без початку сезону → помилка")
big24 = synth(D(2024,1,1), D(2024,12,31))
pt = W.periods_table(big24, [("A", D(2024,5,1), D(2024,5,31)), ("B", D(2026,1,1), D(2026,1,5))], htc_method="daily")
check(pt[0]["empty"] is False and pt[0]["days"] == 31 and pt[1]["empty"] is True,
      "період поза даними → empty без винятку")

st = W.default_settings()
rep = W.build_report(big, st)
check(len(rep["months"]) == 36 and len(rep["decades"]) == 108, "36 місяців і 108 декад за 3 роки")
check(len(rep["years"]) == 3 and rep["total"]["days"] == len(big), "звіт: роки й підсумок")
ws = W.weather_set(rep, "Тест", 48.75, 30.22, "nasa")
check(ws["type"] == "sad_weather_set" and set(ws["years"]) == {"2022","2023","2024"}, "погодний набір за роками")
check(all(k in ws["years"]["2023"] for k in ("tmean","prec_sum","sat_10","set","htc")), "набір містить ключові показники")
json.dumps(ws)  # має серіалізуватись без NaN-проблем
check(True, "набір серіалізується в JSON")
nrm, used = W.normal_from_years({y: sub for y, _, _, sub in okw})
rep2 = W.build_report(big, st, norm=(nrm, used, "2022–2024"))
check(all("anom" in r for r in rep2["years"]), "аномалії додано до кожного року за наявності норми")
check(abs(sum(r["anom"]["d_tmean"] for r in rep2["years"])) < 1e-9, "сума відхилень від норми, обчисленої з тих самих років = 0")

print("\n== 16. Роки порівняння: явний діапазон")
big = const_series([(D(2021,1,1), D(2024,12,31), 12.0, 1400.0)])
ok_all, sk_all = W.year_windows(big, (4, 1, 10, 31))
check([y for y, *_ in ok_all] == [2021, 2022, 2023, 2024], "без обмеження – усі 4 роки з повним покриттям")
ok_f, sk_f = W.year_windows(big, (4, 1, 10, 31), (2022, 2023))
check([y for y, *_ in ok_f] == [2022, 2023] and sk_f == [], "years=(2022, 2023) залишає лише ці роки")
ok_o, _ = W.year_windows(big, (4, 1, 10, 31), (2019, 2020))
check(ok_o == [], "роки поза рядом → порожньо")
st = W.default_settings(); check(st["years"] is None, "у налаштуваннях за замовчуванням years = None")
st["years"] = (2023, 2024); rep16 = W.build_report(big, st)
check([r["year"] for r in rep16["years"]] == [2023, 2024], "build_report враховує settings['years']")
partial = const_series([(D(2022,7,1), D(2024,12,31), 12.0, 1000.0)])
ok_p, sk_p = W.year_windows(partial, (4, 1, 10, 31), (2022, 2024))
check([y for y, *_ in ok_p] == [2023, 2024] and [y for y, *_ in sk_p] == [2022], "рік, покритий частково (з 1 липня), потрапляє в «неповні», а не в порівняння")
st["years"] = None; ws = W.weather_set(W.build_report(big, st), "тест"); check(sorted(ws["years"]) == ["2021", "2022", "2023", "2024"], "погодний набір містить усі роки без обмеження")
st["years"] = (2022, 2022); check(sorted(W.weather_set(W.build_report(big, st), "тест")["years"]) == ["2022"], "погодний набір обмежується роками порівняння")

print("\n== 17. Міжнародні показники у звіті")
import sad_weather_indices as WI
st0 = W.default_settings()
check(st0["lat"] is None and st0["lon"] is None and st0["elev"] is None, "у налаштуваннях за замовчуванням координат немає")
rg17 = np.random.default_rng(17); n17 = 365 * 3; d17 = [D(2021, 1, 1) + dt.timedelta(days=i) for i in range(n17)]
doy17 = np.array([d.timetuple().tm_yday for d in d17], float); tm17 = 10 + 11 * np.sin(2 * np.pi * (doy17 - 110) / 365) + rg17.normal(0, 2, n17)
s17 = W.DailySeries(d17, {"tmean": tm17, "tmax": tm17 + 5, "tmin": tm17 - 5, "prec": np.where(rg17.random(n17) < .3, rg17.gamma(1.4, 5.0, n17), 0.), "rad": np.full(n17, 15.0), "wind": np.full(n17, 2.5), "rh": np.full(n17, 70.0)},
                    {"grid_elevation_m": 212.0})
r0 = W.build_report(s17, st0)
check(r0["series"] is s17 and r0["intl"]["pet_method"] == "none" and r0["intl"]["vine"] == [] and r0["intl"]["aridity"] == [] and not r0["series"].has("et0"), "без широти: звіт працює як раніше, ET₀ не додається, ряд той самий об'єкт")
check(math.isnan(r0["total"]["ai"]) and all(math.isnan(r["ai"]) for r in r0["years"]), "без ET₀ індекс P/ET₀ = NaN (не нуль)")
st1 = dict(st0); st1["lat"] = 48.75; r1 = W.build_report(s17, st1)
check(r1["series"] is not s17 and r1["series"].has("et0") and not s17.has("et0") and r1["series"].meta["et0_method"] == "pm", "з широтою: ET₀ додано до робочої копії; вихідний ряд користувача не змінено")
check(np.allclose(r1["series"].get("tmean"), s17.get("tmean")) and r1["series"].dates == s17.dates and r1["series"].get("prec").tolist() == s17.get("prec").tolist(), "інші змінні робочої копії ідентичні вихідним")
check(abs(r1["total"]["ai"] - r1["total"]["prec_sum"] / r1["total"]["et0_sum"]) < 1e-12 and all(abs(r["ai"] - r["prec_sum"] / r["et0_sum"]) < 1e-12 for r in r1["years"]), "P/ET₀ = опади / ET₀ для всього періоду й кожного року")
check(abs(r1["total"]["water_balance"] - (r1["total"]["prec_sum"] - r1["total"]["et0_sum"])) < 1e-6 and not math.isnan(r1["total"]["water_balance"]), "водний баланс (опади – ET₀) тепер розраховується й для NASA POWER")
check([r["year"] for r in r1["intl"]["aridity"]] == [2021, 2022, 2023] and [r["label"] for r in r1["intl"]["vine"]] == ["2021", "2022", "2023"], "індекс сухості й вінограрські індекси – за повними роками/сезонами")
check(abs(r1["intl"]["aridity"][0]["ai"] - r1["intl"]["aridity"][0]["prec"] / r1["intl"]["aridity"][0]["pet"]) < 1e-12, "AI у таблиці = P / PET")
notes = W.quality_notes(r1["series"], "nasa", D(2021, 1, 1), D(2023, 12, 30), today=D(2030, 1, 1))
check(any("Пенман–Монтейт" in n for n in notes) and any("2 м" in n for n in notes), "примітки про якість містять метод ET₀")
check(not any("Пенман" in n for n in W.quality_notes(s17, "nasa", D(2021, 1, 1), D(2023, 12, 30), today=D(2030, 1, 1))), "без розрахунку ET₀ такої примітки немає")
st2 = dict(st1); st2["elev"] = 0.0; r2 = W.build_report(s17, st2)
check(r2["total"]["et0_sum"] != r1["total"]["et0_sum"], "висота над рівнем моря з налаштувань змінює ET₀ (тиск, Rso)")
par17 = W.methods_paragraph(s17, D(2021, 1, 1), D(2023, 12, 31), 48.75, 30.22, "nasa", 10.0, "decade")
check("growing degree days, GDD" in par17, "у методиці вказано, що СЕТ = GDD (англійський термін для зарубіжних читачів)")
rw = W.build_report(s17, st1, periods=[("тест", D(2022, 5, 1), D(2022, 6, 30)), ("поза", D(2030, 1, 1), D(2030, 1, 5))])
check(abs(rw["periods"][0]["ai"] - rw["periods"][0]["prec_sum"] / rw["periods"][0]["et0_sum"]) < 1e-12 and "ai" not in rw["periods"][1], "довільні періоди: P/ET₀ є, а для періоду без даних – немає")
rsp = W.build_report(s17, st1, spi={"rows": [], "scales": [1]}); check(rsp["spi"] == {"rows": [], "scales": [1]} and r1["spi"] is None, "SPI передається у звіт без змін; за замовчуванням None")
ws17 = W.weather_set(r1, "тест"); check("ai" in ws17["years"]["2022"] and any(i["key"] == "ai" for i in ws17["indicators"]), "погодний набір для аналізів містить P/ET₀")

print("\n" + "=" * 56)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЯДРА ПРОЙДЕНО")
