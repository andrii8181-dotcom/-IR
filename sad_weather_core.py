# sad_weather_core.py – S.A.D. v2.1: ядро модуля «Погода» (без tkinter)
# -*- coding: utf-8 -*-
"""
Отримання добових метеоданих (NASA POWER, власний файл), агрокліматичні показники
та формування тексту для публікації. Дані завантажуються щоразу заново (кешу немає).

ГТК – за визначенням Г.Т. Селянінова (1928); усі формули задокументовані в коді.
"""
import os, re, json, math, time, calendar
import datetime as _dt
from decimal import Decimal, ROUND_HALF_UP
import urllib.request, urllib.parse, urllib.error
import numpy as np
import sad_weather_indices as WI

NAN = float("nan")
RH_HI, RH_LO = 80.0, 30.0            # пороги вологості повітря, %: висока (сприятлива для хвороб) і низька (суха повітря)

# ═══════════════════════════════════════════════════════════════
# 1. ЗМІННІ (внутрішній каталог, спільний для всіх джерел)
# ═══════════════════════════════════════════════════════════════
# ключ: (назва, одиниця, чи сума (для агрегації за період))
VARIABLES = {
    "tmean": ("Середня температура повітря", "°C", False),
    "tmax":  ("Максимальна температура повітря", "°C", False),
    "tmin":  ("Мінімальна температура повітря", "°C", False),
    "prec":  ("Опади", "мм", True),
    "rh":    ("Відносна вологість повітря", "%", False),
    "wind":  ("Швидкість вітру", "м/с", False),
    "rad":   ("Сумарна сонячна радіація", "МДж/м²", True),
    "et0":   ("Еталонне випаровування ET₀", "мм", True),
    "sun":   ("Тривалість сонячного сяйва", "год", True),
}
VAR_ORDER = ["tmean", "tmax", "tmin", "prec", "rh", "wind", "rad", "et0", "sun"]

# Мінімальні дати даних (документація джерел)
SOURCE_MIN_DATE = {"nasa": _dt.date(1981, 1, 1)}
# Затримка доступності найсвіжіших даних, діб (документація джерел)
SOURCE_LAG_DAYS = {"nasa": 3}

SOURCE_TITLES = {
    "nasa": "NASA POWER (MERRA-2/CERES, агрокліматична спільнота AG)",
    "file": "Власні дані (метеостанція, файл)",
}

# ═══════════════════════════════════════════════════════════════
# 2. КООРДИНАТИ
# ═══════════════════════════════════════════════════════════════
def parse_coord(text, kind="lat"):
    """Розбирає координату: 48.75 | 48,75 | 48°45'N | 48 45 00 | S 48 45 | -48°45'.
    Півкулі лише латиницею (N,S,E,W). Повертає float (градуси); ValueError – хибний
    формат, діапазон чи невідповідність літери півкулі виду координати."""
    if text is None: raise ValueError("порожня координата")
    s = str(text).strip().upper().replace(",", ".")
    for a, b in (("′", "'"), ("’", "'"), ("″", '"'), ("”", '"'), ("º", "°")):
        s = s.replace(a, b)
    if not s: raise ValueError("порожня координата")
    sign = 1.0
    letters = re.findall(r"[NSEW]", s)
    if len(letters) > 1: raise ValueError(f"не вдалося розібрати «{text}»")
    if letters:
        L = letters[0]
        if kind == "lat" and L in "EW": raise ValueError("для широти допустимі N або S")
        if kind == "lon" and L in "NS": raise ValueError("для довготи допустимі E або W")
        if L in "SW": sign = -1.0
        s = s.replace(L, " ")
    s = s.strip()
    if s.startswith("-"): sign *= -1.0; s = s[1:]
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    if not nums or len(nums) > 3: raise ValueError(f"не вдалося розібрати «{text}»")
    deg, mn, sec = [float(x) for x in nums] + [0.0] * (3 - len(nums))
    if mn >= 60 or sec >= 60: raise ValueError("хвилини/секунди мають бути < 60")
    value = sign * (deg + mn / 60.0 + sec / 3600.0)
    lim = 90.0 if kind == "lat" else 180.0
    if abs(value) > lim:
        raise ValueError(f"{'широта' if kind=='lat' else 'довгота'} має бути в межах ±{lim:.0f}°")
    return value

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# ═══════════════════════════════════════════════════════════════
# 3. ДОБОВИЙ РЯД
# ═══════════════════════════════════════════════════════════════
class DailySeries:
    """Добові дані: dates (list[date]) + dict ключ→np.ndarray(float, NaN = немає даних).
    meta – словник походження даних (для відтворюваності й тексту методики)."""
    def __init__(self, dates, data, meta=None):
        self.dates = list(dates)
        n = len(self.dates)
        self.data = {}
        for k, v in data.items():
            arr = np.asarray(v, dtype=float)
            if len(arr) != n: raise ValueError(f"довжина «{k}» ≠ кількості дат")
            self.data[k] = arr
        self.meta = dict(meta or {})
        # tmean: якщо немає, але є tmax і tmin – наближення (tmax+tmin)/2 (з позначкою)
        if "tmean" not in self.data and "tmax" in self.data and "tmin" in self.data:
            self.data["tmean"] = (self.data["tmax"] + self.data["tmin"]) / 2.0
            self.meta["tmean_derived"] = True

    def __len__(self): return len(self.dates)
    def has(self, key): return key in self.data and not np.all(np.isnan(self.data[key]))
    def get(self, key):
        return self.data.get(key, np.full(len(self.dates), NAN))
    def slice(self, d0, d1):
        idx = [i for i, d in enumerate(self.dates) if d0 <= d <= d1]
        return DailySeries([self.dates[i] for i in idx],
                           {k: v[idx] for k, v in self.data.items()}, self.meta)
    def missing_share(self, key):
        a = self.get(key)
        return float(np.mean(np.isnan(a))) if len(a) else 1.0
    @staticmethod
    def merge(parts):
        """Об'єднує кілька рядів (частини за роками) у один відсортований без дублів."""
        by_date = {}
        keys = []
        for p in parts:
            for k in p.data:
                if k not in keys: keys.append(k)
        for p in parts:
            for i, d in enumerate(p.dates):
                rec = by_date.setdefault(d, {})
                for k in p.data: rec[k] = p.data[k][i]
        dates = sorted(by_date)
        data = {k: [by_date[d].get(k, NAN) for d in dates] for k in keys}
        meta = dict(parts[0].meta) if parts else {}
        return DailySeries(dates, data, meta)

def iso(d): return d.isoformat()
def parse_date(s):
    s = str(s).strip()
    for f in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y%m%d"):
        try: return _dt.datetime.strptime(s, f).date()
        except ValueError: continue
    raise ValueError(f"дата «{s}»: використовуйте формат РРРР-ММ-ДД або ДД.ММ.РРРР")

# ═══════════════════════════════════════════════════════════════
# 4. HTTP + КЕШ
# ═══════════════════════════════════════════════════════════════
class WeatherError(Exception):
    """Помилка отримання/розбору даних із зрозумілим для користувача текстом."""

USER_AGENT = "S.A.D./2.1 (agronomic statistics; weather module)"

def http_get(url, timeout=60):
    """Звичайний GET; повертає (status, text). Мережеві помилки → WeatherError."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try: body = e.read().decode("utf-8", errors="replace")
        except Exception: body = ""
        return e.code, body
    except urllib.error.URLError as e:
        raise WeatherError(f"Немає з'єднання з сервером ({e.reason}). Перевірте інтернет-з'єднання.")
    except Exception as e:
        raise WeatherError(f"Помилка мережі: {e}")

# ═══════════════════════════════════════════════════════════════
# 5. NASA POWER
# ═══════════════════════════════════════════════════════════════
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMS = {"T2M": "tmean", "T2M_MAX": "tmax", "T2M_MIN": "tmin", "PRECTOTCORR": "prec",
               "RH2M": "rh", "WS2M": "wind", "ALLSKY_SFC_SW_DWN": "rad"}

def nasa_url(lat, lon, d0, d1):
    q = {"parameters": ",".join(NASA_PARAMS), "community": "AG",
         "longitude": f"{lon:.4f}", "latitude": f"{lat:.4f}",
         "start": d0.strftime("%Y%m%d"), "end": d1.strftime("%Y%m%d"), "format": "JSON"}
    return NASA_URL + "?" + urllib.parse.urlencode(q, safe=",")

def parse_nasa(payload):
    """JSON POWER → DailySeries. -999 (fill_value) → NaN; одиниці беремо з відповіді."""
    try:
        props = payload["properties"]["parameter"]
    except (KeyError, TypeError):
        msgs = payload.get("messages") if isinstance(payload, dict) else None
        raise WeatherError(f"NASA POWER повернув відповідь без даних. {msgs or ''}".strip())
    header = payload.get("header", {}) or {}
    fill = header.get("fill_value", -999)
    units = {k: (v or {}).get("units", "") for k, v in (payload.get("parameters") or {}).items()}
    date_keys = sorted({dk for series in props.values() for dk in series})
    dates = [_dt.datetime.strptime(k, "%Y%m%d").date() for k in date_keys]
    data = {}
    for pname, key in NASA_PARAMS.items():
        series = props.get(pname)
        if series is None: continue
        arr = []
        for dk in date_keys:
            v = series.get(dk, fill)
            try: v = float(v)
            except (TypeError, ValueError): v = NAN
            arr.append(NAN if (v == fill or v <= -990) else v)
        arr = np.array(arr, dtype=float)
        u = units.get(pname, "").lower().replace(" ", "")
        if key == "rad" and ("kw" in u):          # kWh/м²/добу → МДж/м²
            arr = arr * 3.6
        if key == "wind" and ("km" in u):         # км/год → м/с
            arr = arr / 3.6
        data[key] = arr
    coords = (payload.get("geometry") or {}).get("coordinates") or []
    meta = {"source": "nasa", "time_standard": header.get("time_standard", ""),
            "api_version": (header.get("api") or {}).get("version", ""),
            "title": header.get("title", ""),
            "grid_elevation_m": coords[2] if len(coords) > 2 else None}
    return DailySeries(dates, data, meta)

def _year_chunks(d0, d1):
    """Розбиває [d0,d1] на відрізки в межах календарних років (≤ 366 діб)."""
    out, cur = [], d0
    while cur <= d1:
        end = min(d1, _dt.date(cur.year, 12, 31))
        out.append((cur, end)); cur = end + _dt.timedelta(days=1)
    return out

def _get_json_with_retry(url, getter, progress=None, max_tries=4, sleep=time.sleep):
    """GET з очікуванням при ліміті (429) і серверних збоях (5xx/45x/46x)."""
    delay = 5
    last = ""
    for attempt in range(1, max_tries + 1):
        status, text = getter(url)
        if status == 200:
            try: return json.loads(text)
            except ValueError: raise WeatherError("Сервер повернув не-JSON відповідь.")
        last = f"HTTP {status}: {text[:300]}"
        if status == 400:
            raise WeatherError(f"Сервер відхилив запит (400). {text[:400]}")
        if status in (429, 500, 502, 503, 504, 450, 460, 550) and attempt < max_tries:
            if progress: progress(f"Сервер зайнятий (код {status}), повтор через {delay} с…")
            sleep(delay); delay *= 3
            continue
        break
    raise WeatherError(f"Не вдалося отримати дані. {last}")

def fetch_nasa(lat, lon, d0, d1, getter=None, progress=None, sleep=time.sleep, today=None):
    """Завантажує добові дані NASA POWER щоразу заново (без кешу), по одному запиту на календарний рік."""
    getter = getter or http_get
    parts, stamps = [], []
    chunks = _year_chunks(d0, d1)
    for i, (a, b) in enumerate(chunks):
        if progress: progress(f"NASA POWER: {a.year} ({i+1}/{len(chunks)})…")
        payload = _get_json_with_retry(nasa_url(lat, lon, a, b), getter, progress, sleep=sleep)
        stamps.append(_dt.datetime.now().replace(microsecond=0).isoformat())
        if i < len(chunks) - 1: sleep(1.0)          # ввічлива пауза між запитами
        parts.append(parse_nasa(payload))
    ser = DailySeries.merge(parts)
    ser.meta.update({"lat": lat, "lon": lon, "retrieved_at": max(stamps) if stamps else "",
                     "source": "nasa", "start": iso(d0), "end": iso(d1)})
    return ser

# ═══════════════════════════════════════════════════════════════
# 6. ПОШУК МІСЦЯ ЗА НАЗВОЮ (OpenStreetMap Nominatim)
# ═══════════════════════════════════════════════════════════════
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSM_ATTRIBUTION = "Дані пошуку: © учасники OpenStreetMap (ліцензія ODbL)."

def geocode(name, getter=None, count=8):
    """Онлайн-пошук населеного пункту в OpenStreetMap (Nominatim). Умови публічного сервера: не частіше 1 запиту/с,
    ідентифікація програми в User-Agent, без автодоповнення; атрибуція © OpenStreetMap. Один запит на натискання кнопки."""
    getter = getter or http_get
    q = {"q": name, "format": "jsonv2", "limit": count, "accept-language": "uk", "addressdetails": 0}
    status, text = getter(NOMINATIM_URL + "?" + urllib.parse.urlencode(q))
    if status != 200: raise WeatherError(f"Сервіс пошуку недоступний (HTTP {status}).")
    try: res = json.loads(text)
    except ValueError: raise WeatherError("Сервіс пошуку повернув некоректну відповідь.")
    if not isinstance(res, list): raise WeatherError("Сервіс пошуку повернув неочікувану відповідь.")
    out = []
    for r in res:
        try: lat, lon = float(r["lat"]), float(r["lon"])
        except (KeyError, TypeError, ValueError): continue
        out.append({"label": str(r.get("display_name") or r.get("name") or f"{lat:.4f}, {lon:.4f}"), "lat": lat, "lon": lon,
                    "kind": str(r.get("type") or "")})
    return out

# ═══════════════════════════════════════════════════════════════
# 7. ВЛАСНИЙ ФАЙЛ (CSV / вставка з Excel)
# ═══════════════════════════════════════════════════════════════
_COL_HINTS = {
    "date": ["дата", "date", "day", "день", "time", "yyyymmdd"],
    "tmean": ["tсер", "tср", "t сер", "tmean", "t2m", "temp", "темпер", "середня т", "сер.т", "tavg", "t_avg"],
    "tmax": ["tmax", "t_max", "максим", "t2m_max", "tмакс"],
    "tmin": ["tmin", "t_min", "мінім", "t2m_min", "tмін"],
    "prec": ["опад", "prec", "rain", "pr", "precip"],
    "rh": ["вологіст", "rh", "humid"],
    "wind": ["вітер", "wind", "ws"],
    "rad": ["радіац", "rad", "solar", "sw_dwn"],
}

def guess_columns(headers):
    """Повертає {ключ: індекс стовпця} за назвами заголовків (нечутливо до регістру)."""
    res = {}
    low = [str(h).strip().lower() for h in headers]
    order = ["date", "tmax", "tmin", "tmean", "prec", "rh", "wind", "rad"]  # tmax/tmin раніше за tmean
    for key in order:
        for i, h in enumerate(low):
            if i in res.values(): continue
            if any(hint in h for hint in _COL_HINTS[key]):
                res[key] = i; break
    if "tmean" not in res:      # заголовок із самої літери: «t», «T, °C», «т (°C)»
        for i, h in enumerate(low):
            if i not in res.values() and re.match(r"^\s*[tт]\s*([,(\[°].*)?$", h):
                res["tmean"] = i; break
    return res

def _num(s):
    if s is None: return NAN
    s = str(s).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "–", "NA", "N/A", "nan", "NaN", "None", "9999", "-999", "-9999"): return NAN
    try: return float(s)
    except ValueError: return NAN

def read_table_text(text):
    """Розбір CSV/TSV-тексту (роздільник ; , або Tab визначається автоматично)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2: raise WeatherError("Файл порожній або має лише заголовок.")
    head = lines[0]
    delim = max([";", "\t", ","], key=lambda d: head.count(d))
    rows = [[c.strip().strip('"') for c in ln.split(delim)] for ln in lines]
    return rows[0], rows[1:]

def series_from_table(headers, rows, mapping, extra_meta=None):
    """mapping: {'date': i, 'tmean': j, ...}. Невалідні дати пропускаються з підрахунком."""
    if "date" not in mapping: raise WeatherError("Не вказано стовпець із датою.")
    recs, bad = {}, 0
    for r in rows:
        try: d = parse_date(r[mapping["date"]])
        except (ValueError, IndexError): bad += 1; continue
        rec = {}
        for k, idx in mapping.items():
            if k == "date": continue
            rec[k] = _num(r[idx]) if idx < len(r) else NAN
        recs[d] = rec
    if not recs: raise WeatherError("Жодного рядка з коректною датою.")
    dates = sorted(recs)
    keys = [k for k in mapping if k != "date"]
    data = {k: [recs[d].get(k, NAN) for d in dates] for k in keys}
    meta = {"source": "file", "bad_rows": bad}
    meta.update(extra_meta or {})
    return DailySeries(dates, data, meta)

# ═══════════════════════════════════════════════════════════════
# 8. ПЕРІОДИ (декади, місяці, довільні)
# ═══════════════════════════════════════════════════════════════
MONTHS_UA = ["січень", "лютий", "березень", "квітень", "травень", "червень",
             "липень", "серпень", "вересень", "жовтень", "листопад", "грудень"]
MONTHS_UA_SHORT = ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"]

def decade_of(d):
    """Номер декади в місяці: 1 (1–10), 2 (11–20), 3 (21–кінець)."""
    return 1 if d.day <= 10 else (2 if d.day <= 20 else 3)

def month_key(d): return (d.year, d.month)
def decade_key(d): return (d.year, d.month, decade_of(d))

def group_indices(series, keyfunc):
    groups = {}
    for i, d in enumerate(series.dates):
        groups.setdefault(keyfunc(d), []).append(i)
    return dict(sorted(groups.items()))

def _nan_sum(a): 
    a = a[~np.isnan(a)]
    return float(np.sum(a)) if len(a) else NAN
def _nan_mean(a):
    a = a[~np.isnan(a)]
    return float(np.mean(a)) if len(a) else NAN

# ═══════════════════════════════════════════════════════════════
# 9. АГРОКЛІМАТИЧНІ ПОКАЗНИКИ
# ═══════════════════════════════════════════════════════════════
def active_temp_sum(tmean, base=10.0):
    """Сума активних температур (САТ): Σ tсер за доби, коли tсер > base (стандарт
    агрометеорології: tсер ≥ base для ГТК – див. нижче; тут строго «вище порога»)."""
    t = np.asarray(tmean, float)
    m = t > base
    return float(np.sum(t[m])) if np.any(m) else 0.0

def effective_temp_sum(tmean, base=10.0, upper=None):
    """Сума ефективних температур (СЕТ): Σ (tсер − base) за доби, коли tсер > base.
    upper – необов'язкове верхнє обмеження tсер (напр. 30 °C для кукурудзи)."""
    t = np.asarray(tmean, float)
    if upper is not None: t = np.minimum(t, upper)
    ex = t - base
    return float(np.sum(ex[ex > 0])) if np.any(ex > 0) else 0.0

def htc_class(value, scale=None):
    """Клас ГТК за шкалою джерела. Клас визначається за значенням, ОКРУГЛЕНИМ до 0,1
    (так у розрахункових прикладах джерела: 0,505→0,5 «сильна посуха»; 0,749→0,7
    «середня»; 0,85→0,9 «слабка»). Повертає (мітка, ключ-кольору)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "н/д", "na"
    r = float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    if r < 0.4:  return "дуже сильна посуха", "d4"
    if r <= 0.5: return "сильна посуха", "d3"
    if r <= 0.7: return "середня посуха", "d2"
    if r <= 0.9: return "слабка посуха", "d1"
    if r <= 1.5: return "достатньо волого", "ok"
    return "надмірно волого", "wet"

HTC_SCALE_TEXT = ("ГТК < 0,4 – дуже сильна посуха; 0,4–0,5 – сильна посуха; 0,6–0,7 – середня посуха; "
                  "0,8–0,9 – слабка посуха; 1,0–1,5 – достатньо волого; > 1,5 – надмірно волого "
                  "(клас визначено за значенням ГТК, округленим до 0,1).")

def htc(prec, tmean, method="calendar", threshold=10.0):
    """ГТК Селянінова = ΣR / (0,1 · Σt) за період із tсер > threshold.
    method:
      'calendar' – як у навчальних прикладах джерела: якщо середня t періоду > 10 °C, то
                   Σt і ΣR беруться за ВСІ доби періоду; інакше ГТК не розраховується
                   (декада/місяць без активних температур).
      'daily'    – суворо за добами: лише доби з tсер > 10 °C (і опади лише цих діб).
    Повертає dict: htc, sum_t, sum_r, days (кількість діб), ok (bool)."""
    p = np.asarray(prec, float); t = np.asarray(tmean, float)
    valid = ~np.isnan(t) & ~np.isnan(p)
    if not np.any(valid):
        return {"htc": NAN, "sum_t": NAN, "sum_r": NAN, "days": 0, "ok": False}
    p, t = p[valid], t[valid]
    if method == "daily":
        m = t > threshold
        st, sr, nd = float(np.sum(t[m])), float(np.sum(p[m])), int(np.sum(m))
    else:
        if float(np.mean(t)) <= threshold:
            return {"htc": NAN, "sum_t": 0.0, "sum_r": float(np.sum(p)), "days": 0, "ok": False}
        st, sr, nd = float(np.sum(t)), float(np.sum(p)), len(t)
    if st <= 0: return {"htc": NAN, "sum_t": st, "sum_r": sr, "days": nd, "ok": False}
    return {"htc": sr / (0.1 * st), "sum_t": st, "sum_r": sr, "days": nd, "ok": True}

def htc_period(series, method="decade", threshold=10.0):
    """ГТК за довільний період (вегетаційний тощо).
    method:
      'decade' / 'month' – за методикою джерела: Σt складається з сум активних температур
          тих декад (місяців), СЕРЕДНЯ температура яких > 10 °C (сума за такий відрізок =
          середня × кількість діб); ΣR – опади за ВЕСЬ період (так у розрахункових прикладах
          джерела: 135,3 мм / (0,1·1373) ≈ 1,0 для квітня–червня).
      'daily' – суворо за добами: лише доби з tсер > 10 °C (і опади лише цих діб).
    Повертає dict: htc, sum_t, sum_r, days, ok."""
    p = series.get("prec"); t = series.get("tmean")
    if method == "daily":
        return htc(p, t, "daily", threshold)
    keyf = decade_key if method == "decade" else month_key
    valid = ~np.isnan(t) & ~np.isnan(p)
    if not np.any(valid):
        return {"htc": NAN, "sum_t": NAN, "sum_r": NAN, "days": 0, "ok": False}
    sum_t, nd = 0.0, 0
    for key, idx in group_indices(series, keyf).items():
        ii = [i for i in idx if valid[i]]
        if not ii: continue
        tt = t[ii]
        if float(np.mean(tt)) > threshold:
            sum_t += float(np.sum(tt)); nd += len(ii)
    sum_r = float(np.sum(p[valid]))
    if sum_t <= 0:
        return {"htc": NAN, "sum_t": 0.0, "sum_r": sum_r, "days": 0, "ok": False}
    return {"htc": sum_r / (0.1 * sum_t), "sum_t": sum_t, "sum_r": sum_r, "days": nd, "ok": True}

def longest_run(mask):
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best

def period_stats(series, base_temps=(5.0, 10.0, 15.0), gdd_base=10.0, gdd_upper=None,
                 htc_method="decade", row_rule=None):
    """Зведені показники за весь ряд series (довільний період). Повертає dict.
    htc_method: 'decade' | 'month' | 'daily' (див. htc_period). row_rule – для рядків
    таблиць за декадами/місяцями: 'calendar' (правило одного відрізка) чи 'daily'."""
    r = {}
    n = len(series)
    r["days"] = n
    tm, tx, tn = series.get("tmean"), series.get("tmax"), series.get("tmin")
    pr = series.get("prec")
    r["tmean"] = _nan_mean(tm)
    r["miss_tmean"] = float(np.mean(np.isnan(tm))) if len(tm) else 1.0
    r["miss_prec"] = float(np.mean(np.isnan(pr))) if len(pr) else 1.0
    r["tmax_mean"] = _nan_mean(tx); r["tmin_mean"] = _nan_mean(tn)
    r["tmax_abs"] = float(np.nanmax(tx)) if np.any(~np.isnan(tx)) else NAN
    r["tmin_abs"] = float(np.nanmin(tn)) if np.any(~np.isnan(tn)) else NAN
    r["prec_sum"] = _nan_sum(pr)
    valid_p = ~np.isnan(pr)
    r["prec_days_01"] = int(np.sum(pr[valid_p] >= 0.1)) if np.any(valid_p) else 0
    r["prec_days_1"] = int(np.sum(pr[valid_p] >= 1.0)) if np.any(valid_p) else 0
    r["prec_days_10"] = int(np.sum(pr[valid_p] >= 10.0)) if np.any(valid_p) else 0
    r["prec_max_day"] = float(np.nanmax(pr)) if np.any(valid_p) else NAN
    r["dry_spell_max"] = longest_run([(v < 1.0) for v in pr[valid_p]]) if np.any(valid_p) else 0
    r["rh"] = _nan_mean(series.get("rh"))
    rhv = series.get("rh"); vr_ = ~np.isnan(rhv)
    r["miss_rh"] = float(np.mean(np.isnan(rhv))) if len(rhv) else 1.0
    r["days_rh_hi"] = int(np.sum(rhv[vr_] >= RH_HI)) if np.any(vr_) else NAN              # немає вологості – «немає даних», а не нуль діб
    r["days_rh_lo"] = int(np.sum(rhv[vr_] <= RH_LO)) if np.any(vr_) else NAN
    r["vpd"] = _nan_mean(WI.vpd_daily(tx, tn, rhv, tm)) if np.any(vr_) else NAN
    r["wind"] = _nan_mean(series.get("wind"))
    r["rad_sum"] = _nan_sum(series.get("rad"))
    r["et0_sum"] = _nan_sum(series.get("et0"))
    r["sun_sum"] = _nan_sum(series.get("sun"))
    for b in base_temps:
        r[f"sat_{int(b)}"] = active_temp_sum(tm[~np.isnan(tm)], b)
    r["set"] = effective_temp_sum(tm[~np.isnan(tm)], gdd_base, gdd_upper)
    h = htc(pr, tm, row_rule) if row_rule else htc_period(series, htc_method)
    r["htc"] = h["htc"]; r["htc_sum_t"] = h["sum_t"]; r["htc_sum_r"] = h["sum_r"]
    r["htc_class"] = htc_class(h["htc"])[0]
    vt = ~np.isnan(tx)
    r["days_tmax25"] = int(np.sum(tx[vt] >= 25)); r["days_tmax30"] = int(np.sum(tx[vt] >= 30))
    r["days_tmax35"] = int(np.sum(tx[vt] >= 35))
    vn = ~np.isnan(tn)
    r["days_frost"] = int(np.sum(tn[vn] < 0.0))
    return r

def balance_water(series):
    """Кліматичний водний баланс P − ET₀ (мм) за ряд; NaN, якщо немає ET₀."""
    if not series.has("et0"): return NAN
    p, e = series.get("prec"), series.get("et0")
    m = ~np.isnan(p) & ~np.isnan(e)
    return float(np.sum(p[m] - e[m])) if np.any(m) else NAN

def table_by_groups(series, keyfunc, labelfunc, **kw):
    """Таблиця показників за групами (місяці/декади). Повертає list[dict].
    ГТК рядка: правило одного відрізка (календарне) або добове – залежно від htc_method."""
    kw = dict(kw)
    kw["row_rule"] = "daily" if kw.get("htc_method") == "daily" else "calendar"
    out = []
    for key, idx in group_indices(series, keyfunc).items():
        sub = DailySeries([series.dates[i] for i in idx],
                          {k: v[idx] for k, v in series.data.items()}, series.meta)
        st = period_stats(sub, **kw)
        st["key"] = key; st["label"] = labelfunc(key)
        st["start"] = sub.dates[0]; st["end"] = sub.dates[-1]
        out.append(st)
    return out

def month_label(key): return f"{MONTHS_UA_SHORT[key[1]-1]} {key[0]}"
def decade_label(key): return f"{MONTHS_UA_SHORT[key[1]-1]} {key[0]}, {key[2]} дек."

def frost_events(series, threshold=0.0):
    """Доби з tmin < threshold: список (date, tmin); перший і останній у ряді."""
    tn = series.get("tmin")
    ev = [(d, float(v)) for d, v in zip(series.dates, tn) if not math.isnan(v) and v < threshold]
    return ev

def threshold_dates(series, threshold, run=5):
    """Спрощені дати переходу tсер через поріг: початок = перша доба, з якої tсер ≥ порога
    `run` діб поспіль; завершення = остання доба останньої такої послідовності.
    Повертає dict(start, end, start_before_window, end_after_window)."""
    t = series.get("tmean")
    ok = [(not math.isnan(v)) and v >= threshold for v in t]
    n = len(ok)
    starts = [i for i in range(n - run + 1) if all(ok[i:i + run])]
    if not starts:
        return {"start": None, "end": None, "start_before_window": False, "end_after_window": False}
    first = starts[0]
    last_end = max(i + run - 1 for i in starts)
    # розширюємо останню послідовність вправо, поки умова виконується
    j = last_end
    while j + 1 < n and ok[j + 1]: j += 1
    return {"start": series.dates[first], "end": series.dates[j],
            "start_before_window": first == 0, "end_after_window": j == n - 1}

def cumulative(series, key, base=None):
    """Наростаючі суми: для опадів/радіації – Σ; для температур із base – СЕТ чи САТ
    (base задає поріг; повертає два масиви: (active, effective))."""
    v = series.get(key)
    v0 = np.where(np.isnan(v), 0.0, v)
    if base is None: return np.cumsum(v0)
    act = np.where(v0 > base, v0, 0.0)
    eff = np.where(v0 > base, v0 - base, 0.0)
    return np.cumsum(act), np.cumsum(eff)

# ═══════════════════════════════════════════════════════════════
# 10. НОРМА ТА АНОМАЛІЇ
# ═══════════════════════════════════════════════════════════════
def window_for_year(year, m1, d1, m2, d2):
    """Календарне вікно в заданому році; 29 лютого → 28 у невисокосні."""
    def mk(y, m, d):
        d = min(d, calendar.monthrange(y, m)[1]); return _dt.date(y, m, d)
    a = mk(year, m1, d1)
    b = mk(year + (1 if (m2, d2) < (m1, d1) else 0), m2, d2)
    return a, b

def normal_from_years(series_by_year, **kw):
    """Багаторічна норма за періодом: середнє (за роками) від показників року.
    series_by_year: {рік: DailySeries (вікно)}. Повертає (норма dict, список років)."""
    stats = {y: period_stats(s, **kw) for y, s in series_by_year.items() if len(s) > 0}
    keys = ["tmean", "tmax_mean", "tmin_mean", "prec_sum", "sat_5", "sat_10", "sat_15",
            "set", "htc", "rad_sum", "et0_sum", "days_frost", "days_tmax30", "rh", "days_rh_hi", "days_rh_lo", "vpd"]
    norm = {}
    for k in keys:
        vals = [st[k] for st in stats.values() if st.get(k) is not None and not
                (isinstance(st[k], float) and math.isnan(st[k]))]
        norm[k] = float(np.mean(vals)) if vals else NAN
        norm[k + "_sd"] = float(np.std(vals, ddof=1)) if len(vals) > 1 else NAN
    return norm, sorted(stats)

def anomaly_row(stats, norm):
    """Відхилення року від норми: Δt (°C), опади у % норми, ΔСАТ."""
    def d(k): 
        a, b = stats.get(k, NAN), norm.get(k, NAN)
        return (a - b) if not (math.isnan(a) or math.isnan(b)) else NAN
    pn = norm.get("prec_sum", NAN)
    pct = (stats["prec_sum"] / pn * 100.0) if (pn and not math.isnan(pn) and pn > 0
                                               and not math.isnan(stats["prec_sum"])) else NAN
    return {"d_tmean": d("tmean"), "prec_pct": pct, "d_sat_10": d("sat_10"), "d_htc": d("htc")}

def precip_deviation_class(pct):
    """Оцінка за відхиленням опадів від норми (джерело ЖДТУ: відхилення понад 20 % –
    суттєві)."""
    if pct is None or math.isnan(pct): return "н/д"
    if pct < 80: return "суттєво нижче норми"
    if pct > 120: return "суттєво вище норми"
    return "в межах норми"

# ═══════════════════════════════════════════════════════════════
# 11. ПОПЕРЕДЖЕННЯ ПРО ЯКІСТЬ ДАНИХ
# ═══════════════════════════════════════════════════════════════
def quality_notes(series, source, d0, d1, today=None):
    """Список попереджень для користувача: пропуски, свіжі/попередні дані, реаналіз."""
    today = today or _dt.date.today()
    notes = []
    exp_days = (d1 - d0).days + 1
    if len(series) < exp_days:
        notes.append(f"У ряді {len(series)} діб із запитаних {exp_days}: решта не повернута джерелом.")
    for k in ("tmean", "prec"):
        ms = series.missing_share(k)
        if series.has(k) and ms > 0:
            notes.append(f"«{VARIABLES[k][0]}»: пропущено {ms*100:.1f}% значень – "
                         f"показники за такі періоди розраховані за наявними добами.")
        if not series.has(k) and source != "file":
            notes.append(f"«{VARIABLES[k][0]}»: даних немає.")
    lag = SOURCE_LAG_DAYS.get(source)
    if lag and (today - d1).days <= lag + 3:
        notes.append(f"Кінець періоду близько до сьогодні: останні доби можуть бути відсутні "
                     f"(затримка джерела ≈ {lag} діб) або попередніми.")
    if source == "nasa" and (today - d1).days < 100:
        notes.append("NASA POWER: метеорологічні дані останніх 2–3 місяців – попередні "
                     "(швидкий перегляд) і будуть замінені кліматично-якісними; повторний "
                     "запит пізніше може дати дещо інші значення. Зафіксуйте дату отримання.")
    if source == "nasa":
        notes.append("Це дані реаналізу/супутникової оцінки для комірки сітки, а не вимірювання "
                     "метеостанції на ділянці: опади згладжені, екстремуми занижені. Для "
                     "дисертації бажано порівняти з найближчою станцією, якщо вона є.")
    if series.meta.get("tmean_derived"):
        notes.append("Середню добову температуру обчислено як (tmax + tmin)/2.")
    if series.meta.get("et0_note"):
        notes.append(series.meta["et0_note"])
    return notes

# ═══════════════════════════════════════════════════════════════
# 12. ТЕКСТ ДЛЯ ПУБЛІКАЦІЇ
# ═══════════════════════════════════════════════════════════════
NASA_ACK = ("These data were obtained from the NASA Langley Research Center POWER Project "
            "funded through the NASA Earth Science Directorate Applied Science Program.")
def methods_paragraph(series, d0, d1, lat, lon, source, gdd_base, htc_method, extras=None):
    """Абзац «Методика збору метеоданих» у науковому стилі (укр.)."""
    ret = series.meta.get("retrieved_at", "")
    if lat is None or lon is None:
        coords = "що не вказані"
    else:
        coords = (f"{abs(lat):.4f}".replace(".", ",") + f"° {'пн.' if lat >= 0 else 'пд.'} ш., "
                  + f"{abs(lon):.4f}".replace(".", ",") + f"° {'сх.' if lon >= 0 else 'зх.'} д.")
    per = f"{d0.strftime('%d.%m.%Y')}–{d1.strftime('%d.%m.%Y')}"
    if source == "nasa":
        src = ("Метеорологічні дані отримано з бази NASA POWER (Prediction Of Worldwide Energy "
               "Resources; агрокліматична спільнота AG), побудованої на реаналізі MERRA-2 "
               "(просторове розрізнення 0,5° × 0,625° для метеорологічних параметрів та 1° × 1° "
               "для параметрів сонячної радіації). Використано добові значення середньої, "
               "максимальної й мінімальної температури повітря на висоті 2 м, скоригованої суми "
               "опадів (PRECTOTCORR), відносної вологості повітря, швидкості вітру та сумарної "
               "сонячної радіації.")
    else:
        src = "Метеорологічні дані наведено за вимірюваннями метеостанції (власні дані дослідника)."
    htc_txt = {"daily": "розраховано за добами з tсер > 10 °C",
               "decade": "розраховано за декадним обліком активних температур: до суми Σt включали "
                         "декади із середньою температурою вище 10 °C, опади враховували за весь період; "
                         "для декад без активних температур показник не визначали",
               "month": "розраховано за місячним обліком активних температур: до суми Σt включали "
                        "місяці із середньою температурою вище 10 °C, опади враховували за весь період; "
                        "для місяців без активних температур показник не визначали"}.get(htc_method, "")
    calc = (f"Суму активних температур (САТ) обчислювали як суму середньодобових температур за доби з "
            f"tсер > 5, 10 та 15 °C; суму ефективних температур (СЕТ; у зарубіжній літературі – growing degree days, GDD) – як суму перевищень "
            f"середньодобової температури над біологічним мінімумом {gdd_base:g} °C. "
            f"Гідротермічний коефіцієнт Селянінова (ГТК) визначали за формулою ГТК = ΣR / (0,1·Σt), де "
            f"ΣR – сума опадів, мм, Σt – сума активних температур вище 10 °C за той самий період; {htc_txt}. "
            f"Умови зволоження оцінювали за значенням ГТК: {HTC_SCALE_TEXT}")
    ret_fmt = ""
    if ret:
        try: ret_fmt = _dt.datetime.fromisoformat(ret).strftime("%d.%m.%Y")
        except ValueError: ret_fmt = ret[:10]
    if lat is None or lon is None:
        clauses = [f"Дані стосуються періоду {per}"]
    else:
        clauses = [f"Дані стосуються точки з координатами {coords} за період {per}"]
    if ret_fmt and source == "nasa":
        clauses.append(f"дата отримання даних – {ret_fmt}")
    tail = " " + "; ".join(clauses) + "."
    if source == "nasa":
        tail += (" Оскільки джерелом є реаналіз для комірки сітки, значення відображають умови "
                 "регіону, а не безпосередні вимірювання на дослідній ділянці.")
    if extras: tail += " " + extras
    return src + " " + calc + tail

def citation_block(source):
    """Бібліографічні посилання/подяки, яких вимагає джерело."""
    if source == "nasa":
        return ["NASA POWER: " + NASA_ACK, "https://power.larc.nasa.gov"]
    return []

def licence_notice(source):
    if source == "nasa":
        return ("NASA POWER: дані безкоштовні; NASA просить зазначати подяку в публікаціях "
                "(текст додано до експорту). Не зловживайте частотою запитів.")
    return ""


# ═══════════════════════════════════════════════════════════════
# 13. ТАБЛИЦІ ЗА РОКАМИ, ДОВІЛЬНІ ПЕРІОДИ, ЗВІТ
# ═══════════════════════════════════════════════════════════════
# (ключ, назва, одиниця) – показники, придатні для передачі в аналізи як коваріати
INDICATOR_DEFS = [
    ("tmean", "Середня температура повітря", "°C"),
    ("prec_sum", "Сума опадів", "мм"),
    ("sat_5", "Сума активних температур >5 °C", "°C"),
    ("sat_10", "Сума активних температур >10 °C", "°C"),
    ("sat_15", "Сума активних температур >15 °C", "°C"),
    ("set", "Сума ефективних температур", "°C"),
    ("htc", "ГТК Селянінова", ""),
    ("days_frost", "Діб із заморозком (tmin < 0 °C)", "діб"),
    ("days_tmax30", "Діб з tmax ≥ 30 °C", "діб"),
    ("prec_days_1", "Діб з опадами ≥ 1 мм", "діб"),
    ("dry_spell_max", "Найдовший період без опадів (<1 мм)", "діб"),
    ("rad_sum", "Сумарна сонячна радіація", "МДж/м²"),
    ("rh", "Середня відносна вологість повітря", "%"),
    ("days_rh_hi", f"Діб з вологістю повітря ≥ {RH_HI:g} %", "діб"),
    ("days_rh_lo", f"Діб з вологістю повітря ≤ {RH_LO:g} %", "діб"),
    ("vpd", "Середній дефіцит насичення повітря (VPD)", "кПа"),
    ("et0_sum", "Еталонне випаровування ET₀", "мм"),
    ("water_balance", "Водний баланс (опади – ET₀)", "мм"),
    ("ai", "Індекс сухості P/ET₀ у вікні", ""),
]

def year_windows(series, window, years=None):
    """Календарні вікна window=(м1,д1,м2,д2) для кожного року, ПОВНІСТЮ покритого рядом.
    years=(рік_від, рік_до) – залишити лише ці роки (None – усі). Повертає (ok: [(рік, a, b, піддіапазон)],
    skipped: [(рік, a, b)] – перекриті частково)."""
    if not series.dates: return [], []
    m1, d1, m2, d2 = window
    smin, smax = series.dates[0], series.dates[-1]
    ok, skipped = [], []
    for y in range(smin.year - 1, smax.year + 1):
        if years is not None and not (years[0] <= y <= years[1]): continue
        a, b = window_for_year(y, m1, d1, m2, d2)
        if a >= smin and b <= smax: ok.append((y, a, b, series.slice(a, b)))
        elif b >= smin and a <= smax: skipped.append((y, a, b))
    return ok, skipped

def by_year_table(series, window, years=None, **kw):
    ok, skipped = year_windows(series, window, years)
    rows = []
    for y, a, b, sub in ok:
        st = period_stats(sub, **kw)
        st.update(year=y, start=a, end=b, water_balance=balance_water(sub))
        rows.append(st)
    return rows, skipped

def periods_table(series, periods, **kw):
    """periods: [(назва, початок, кінець)] → рядки показників; empty=True, якщо даних немає."""
    rows = []
    for name, a, b in periods:
        sub = series.slice(a, b); exp = (b - a).days + 1
        if len(sub) == 0:
            rows.append({"name": name, "start": a, "end": b, "days": 0, "expected": exp, "empty": True})
            continue
        st = period_stats(sub, **kw)
        st.update(name=name, start=a, end=b, expected=exp, empty=False, water_balance=balance_water(sub))
        rows.append(st)
    return rows

def intervals_from_dates(dates, season_start=None, mode="between"):
    """Періоди за датами замірів. mode='between' – між сусідніми замірами (перший –
    від початку сезону, якщо він заданий); mode='cumulative' – від початку сезону до
    кожного заміру (потрібен season_start). Повертає [(назва, початок, кінець)]."""
    ds = sorted(set(dates)); out = []; prev = None
    for d in ds:
        if mode == "cumulative":
            if season_start is None: raise ValueError("Для нагромадження потрібна дата початку сезону.")
            if d >= season_start: out.append((f"{season_start:%d.%m}–{d:%d.%m.%Y}", season_start, d))
        else:
            a = season_start if prev is None else prev + _dt.timedelta(days=1)
            if a is not None and a <= d: out.append((f"{a:%d.%m}–{d:%d.%m.%Y}", a, d))
        prev = d
    return out

def default_settings():
    return {"gdd_base": 10.0, "gdd_upper": None, "htc_method": "decade", "frost_thr": 0.0,
            "window": (4, 1, 10, 31), "years": None, "base_temps": (5.0, 10.0, 15.0),
            "lat": None, "lon": None, "elev": None}

def stat_kwargs(settings):
    return {"base_temps": tuple(settings.get("base_temps", (5.0, 10.0, 15.0))),
            "gdd_base": settings.get("gdd_base", 10.0), "gdd_upper": settings.get("gdd_upper"),
            "htc_method": settings.get("htc_method", "decade")}

def _range_sum(series, arr, a, b, min_share=0.95):
    """Сума масиву arr (вирівняного з series.dates) за [a, b] із пропорційною компенсацією пропусків; NaN, якщо покриття < min_share."""
    ix = [i for i, d in enumerate(series.dates) if a <= d <= b]
    if not ix: return NAN
    v = arr[ix]; ok = ~np.isnan(v)
    if ok.mean() < min_share: return NAN
    return float(np.sum(v[ok]) * len(ix) / ok.sum())


def build_report(series, settings, norm=None, periods=None, spi=None):
    """Єдиний розрахунковий звіт – вхід для вікна, графіків і експорту.
    Якщо в ряді немає ET₀, але є координати й tmax/tmin, ET₀ розраховується (Пенман–Монтейт або Харгрівз–Самані) і підставляється
    у робочу копію ряду як «et0»: тоді ET₀, водний баланс і P/ET₀ з'являються в усіх таблицях. Вихідний ряд користувача не змінюється."""
    lat = settings.get("lat")
    pet, pmeth, pnote = WI.pet_series(series, lat, settings.get("elev"))
    if pmeth in ("pm", "hs"):
        data = dict(series.data); data["et0"] = pet
        series = DailySeries(series.dates, data, {**series.meta, "et0_method": pmeth, "et0_note": pnote})
    kw = stat_kwargs(settings)
    d0, d1 = series.dates[0], series.dates[-1]
    rep = {"settings": dict(settings), "series": series, "d0": d0, "d1": d1}
    rep["total"] = period_stats(series, **kw)
    rep["total"]["water_balance"] = balance_water(series)
    rep["total"]["ai"] = WI.window_ai(rep["total"]["prec_sum"], rep["total"]["et0_sum"])
    rep["decades"] = table_by_groups(series, decade_key, decade_label, **kw)
    rep["months"] = table_by_groups(series, month_key, month_label, **kw)
    rep["years"], rep["years_skipped"] = by_year_table(series, settings["window"], settings.get("years"), **kw)
    for r in rep["years"]: r["ai"] = WI.window_ai(r["prec_sum"], r["et0_sum"])
    rep["norm"] = norm            # (norm_dict, years_list, label) або None
    if norm:
        nd = norm[0]
        for r in rep["years"]:
            r["anom"] = anomaly_row(r, nd)
    rep["periods"] = periods_table(series, periods, **kw) if periods else []
    for r in rep["periods"]:
        if not r.get("empty"): r["ai"] = WI.window_ai(r["prec_sum"], r["et0_sum"])
    rep["frost"] = frost_events(series, settings.get("frost_thr", 0.0))
    rep["intl"] = {"lat": lat, "pet_method": pmeth, "pet_note": pnote, "vine": WI.vine_rows(series, lat),
                   "aridity": WI.aridity_rows(series, series.get("et0") if series.has("et0") else np.full(len(series), NAN))}
    rep["spi"] = spi
    return rep

def weather_set(rep, place="", lat=None, lon=None, source=""):
    """Набір погодних показників за роками – для передачі в аналізи (ANCOVA тощо)."""
    years = {}
    for r in rep["years"]:
        years[str(r["year"])] = {k: (None if (isinstance(r.get(k), float) and math.isnan(r.get(k)))
                                     else r.get(k)) for k, _, _ in INDICATOR_DEFS if k in r}
    m1, d1, m2, d2 = rep["settings"]["window"]
    return {"type": "sad_weather_set", "version": 1, "place": place, "lat": lat, "lon": lon,
            "source": source, "retrieved_at": rep["series"].meta.get("retrieved_at", ""),
            "window": [m1, d1, m2, d2], "settings": {k: v for k, v in rep["settings"].items()
                                                     if k in ("gdd_base", "gdd_upper", "htc_method")},
            "indicators": [{"key": k, "label": l, "unit": u} for k, l, u in INDICATOR_DEFS],
            "years": years}
