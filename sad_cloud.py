# sad_cloud.py – S.A.D. v2.1: хмара (Firebase): вхід, дослід у хмарі, надсилання й отримання значень польового журналу
# -*- coding: utf-8 -*-
"""Хмарна синхронізація польового журналу.

Мережа – лише стандартна бібліотека (urllib), без додаткових залежностей. Структуру даних і правила доступу описано в cloud/README.md.

Три рівні:
  Cloud        – запити до Firebase Authentication і Cloud Firestore (REST); вхід, дослід, показники, значення;
  SyncState    – локальний стан синхронізації теки схеми (файл .sad_cloud.json поруч зі схемою): що вже в хмарі, черга без зв'язку;
  plan_push / apply_pulled – чисті функції: що надіслати після збереження журналу і як внести в журнал значення, що прийшли з поля.

Значення в хмарі ніколи не змінюються: виправлення – новий запис із полем supersedes. Два різні значення однієї клітинки від різних людей
(жодне не виправляє інше) – конфлікт: у журналі лишається новіше, обидва записуються в record["conflicts"].
"""
import json, os, time, threading, socket, hashlib, secrets, shutil, datetime as _dt
import urllib.request, urllib.error, urllib.parse

# Публічні налаштування проєкту Firebase (не секрет: дані захищають правила доступу cloud/firestore.rules)
API_KEY = "AIzaSyClB6foMo0MPktl2Jk5gNJ7ZjJp-wRqsBc"
PROJECT_ID = "sad2-54cf9"
STATE_FILE = ".sad_cloud.json"
BACKUP_DIR = ".sad_cloud_backup"
BACKUP_KEEP = 30
BATCH = 200                      # записів за один запит commit (межа Firestore – 500)


def user_dir():
    d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "SAD"); os.makedirs(d, exist_ok=True); return d


# ═══════════════════════════════════════════════════════════════
# Помилки (повідомлення – для користувача)
# ═══════════════════════════════════════════════════════════════
class CloudError(Exception): pass
class CloudOffline(CloudError): pass          # немає зв'язку – дані лишаються в черзі
class CloudAuthError(CloudError): pass        # треба увійти знову
class CloudDenied(CloudError): pass           # правила доступу відмовили (немає прав, закритий рік тощо)

AUTH_MESSAGES = {
    "EMAIL_EXISTS": "Обліковий запис із цією адресою вже є. Увійдіть або відновіть пароль.",
    "EMAIL_NOT_FOUND": "Неправильна адреса або пароль.",
    "INVALID_PASSWORD": "Неправильна адреса або пароль.",
    "INVALID_LOGIN_CREDENTIALS": "Неправильна адреса або пароль.",
    "INVALID_EMAIL": "Неправильна адреса електронної пошти.",
    "MISSING_PASSWORD": "Вкажіть пароль.",
    "WEAK_PASSWORD": "Пароль закороткий – щонайменше 6 символів.",
    "USER_DISABLED": "Обліковий запис вимкнено.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Забагато спроб. Спробуйте за кілька хвилин.",
    "TOKEN_EXPIRED": "Сеанс завершився – увійдіть знову.",
    "INVALID_REFRESH_TOKEN": "Сеанс завершився – увійдіть знову.",
    "USER_NOT_FOUND": "Обліковий запис не знайдено – увійдіть знову.",
    "INVALID_ID_TOKEN": "Сеанс завершився – увійдіть знову.",
}


def _auth_message(code):
    code = (code or "").strip(); key = code.split(" ")[0].split(":")[0]
    return AUTH_MESSAGES.get(key, f"Помилка входу: {code or 'невідома'}")


# ═══════════════════════════════════════════════════════════════
# Значення Firestore ⇄ Python
# ═══════════════════════════════════════════════════════════════
def enc(v):
    if v is None: return {"nullValue": None}
    if isinstance(v, bool): return {"booleanValue": v}
    if isinstance(v, int): return {"integerValue": str(v)}
    if isinstance(v, float): return {"doubleValue": v}
    if isinstance(v, str): return {"stringValue": v}
    if isinstance(v, _dt.datetime):
        u = v.astimezone(_dt.timezone.utc) if v.tzinfo else v
        return {"timestampValue": u.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"}
    if isinstance(v, (list, tuple)): return {"arrayValue": {"values": [enc(x) for x in v]} if v else {}}
    if isinstance(v, dict): return {"mapValue": {"fields": {k: enc(x) for k, x in v.items()}}}
    raise TypeError(f"Непідтримуваний тип для хмари: {type(v).__name__}")


def dec(v):
    (t, x), = v.items()
    if t == "nullValue": return None
    if t == "integerValue": return int(x)
    if t in ("doubleValue", "booleanValue", "stringValue", "timestampValue", "referenceValue", "bytesValue"): return x
    if t == "arrayValue": return [dec(y) for y in (x or {}).get("values", [])]
    if t == "mapValue": return {k: dec(y) for k, y in (x or {}).get("fields", {}).items()}
    if t == "geoPointValue": return x
    raise ValueError(f"Невідомий тип значення Firestore: {t}")


def fields(d): return {k: enc(v) for k, v in d.items()}
def unfields(doc): return {k: dec(v) for k, v in (doc.get("fields") or {}).items()}


def ts_key(ts):
    """Час Firestore (RFC 3339, до 9 знаків дробу) → кортеж для порівняння: рядки з різною кількістю знаків дробу не можна порівнювати як текст."""
    if not ts: return (0, 0)
    base, _, frac = ts.rstrip("Z").partition(".")
    secs = int(_dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp())
    return (secs, int((frac + "000000000")[:9]) if frac else 0)


def new_id(n=20):
    abc = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(abc) for _ in range(n))


def indicator_id(name, year):
    return hashlib.sha1(f"{year}|{name}".encode("utf-8")).hexdigest()[:20]


# ═══════════════════════════════════════════════════════════════
# Клієнт хмари
# ═══════════════════════════════════════════════════════════════
class Cloud:
    """emulator – «хост_auth,хост_firestore» (для тестів) або змінна середовища SAD_CLOUD_EMULATOR."""
    def __init__(self, api_key=API_KEY, project_id=PROJECT_ID, emulator=None, session_path=None, timeout=15):
        self.api_key, self.project = api_key, project_id; self.timeout = timeout
        emulator = emulator if emulator is not None else os.environ.get("SAD_CLOUD_EMULATOR", "")
        if emulator:
            ah, fh = (emulator.split(",") + [""])[:2]
            self._auth = f"http://{ah}/identitytoolkit.googleapis.com/v1/accounts:"
            self._token_url = f"http://{ah}/securetoken.googleapis.com/v1/token"
            self._fs_root = f"http://{fh}/v1/projects/{project_id}/databases/(default)"
        else:
            self._auth = "https://identitytoolkit.googleapis.com/v1/accounts:"
            self._token_url = "https://securetoken.googleapis.com/v1/token"
            self._fs_root = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)"
        self.emulator = bool(emulator)
        self.session_path = session_path or os.path.join(user_dir(), "cloud_session.json")
        self._lock = threading.RLock(); self.session = self._load_session()

    # ── HTTP ──
    def _http(self, method, url, body=None, headers=None, form=False):
        h = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}; h.update(headers or {})
        data = None
        if body is not None: data = (urllib.parse.urlencode(body) if form else json.dumps(body, ensure_ascii=False)).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r: raw = r.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as e:
            try: err = json.loads(e.read().decode("utf-8"))
            except Exception: err = {}
            if isinstance(err, list) and err: err = err[0]
            info = err.get("error", {}) if isinstance(err, dict) else {}
            msg = info.get("message", "") if isinstance(info, dict) else str(info)
            status = info.get("status", "") if isinstance(info, dict) else ""
            raise _HTTPFail(e.code, status, msg)
        except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError, OSError) as e:
            raise CloudOffline("Немає зв'язку з хмарою – дані збережено на комп'ютері й буде надіслано пізніше.") from e

    # ── сеанс ──
    def _load_session(self):
        try:
            with open(self.session_path, "r", encoding="utf-8") as f: s = json.load(f)
            return s if s.get("refreshToken") and s.get("uid") else None
        except Exception: return None

    def _save_session(self):
        try:
            if self.session:
                with open(self.session_path, "w", encoding="utf-8") as f: json.dump(self.session, f, ensure_ascii=False)
            elif os.path.exists(self.session_path): os.remove(self.session_path)
        except OSError: pass

    @property
    def signed_in(self): return bool(self.session)
    @property
    def email(self): return (self.session or {}).get("email", "")
    @property
    def uid(self): return (self.session or {}).get("uid", "")
    @property
    def verified(self): return bool((self.session or {}).get("verified"))

    def _auth_call(self, op, body):
        try: return self._http("POST", f"{self._auth}{op}?key={self.api_key}", body)
        except _HTTPFail as e: raise CloudAuthError(_auth_message(e.message)) from None

    def _set_session(self, r, email=None):
        self.session = {"email": (email or r.get("email") or "").lower(), "uid": r.get("localId") or r.get("user_id"),
                        "idToken": r.get("idToken") or r.get("id_token"), "refreshToken": r.get("refreshToken") or r.get("refresh_token"),
                        "expiresAt": time.time() + int(r.get("expiresIn") or r.get("expires_in") or 3600) - 60,
                        "verified": bool((self.session or {}).get("verified")) if r.get("emailVerified") is None else bool(r.get("emailVerified"))}
        self._save_session(); return self.session

    def sign_up(self, email, password):
        with self._lock:
            r = self._auth_call("signUp", {"email": email.strip(), "password": password, "returnSecureToken": True})
            self.session = None; self._set_session(r, email.strip()); self.session["verified"] = False; self._save_session()
            self.send_verification(); return self.session

    def sign_in(self, email, password):
        with self._lock:
            r = self._auth_call("signInWithPassword", {"email": email.strip(), "password": password, "returnSecureToken": True})
            self.session = None; self._set_session(r, email.strip()); self.check_verified(); return self.session

    def sign_out(self):
        with self._lock: self.session = None; self._save_session()

    def send_verification(self):
        self._auth_call("sendOobCode", {"requestType": "VERIFY_EMAIL", "idToken": self._id_token()})

    def reset_password(self, email):
        self._auth_call("sendOobCode", {"requestType": "PASSWORD_RESET", "email": email.strip()})

    def check_verified(self):
        """Перепитує сервер, чи підтверджено адресу; після підтвердження оновлює токен (у ньому є ознака підтвердження для правил доступу)."""
        with self._lock:
            r = self._auth_call("lookup", {"idToken": self._id_token()})
            ok = bool(((r.get("users") or [{}])[0]).get("emailVerified"))
            was = self.verified; self.session["verified"] = ok
            if ok and not was: self._refresh()
            self._save_session(); return ok

    def _refresh(self):
        try: r = self._http("POST", f"{self._token_url}?key={self.api_key}", {"grant_type": "refresh_token", "refresh_token": self.session["refreshToken"]}, form=True)
        except _HTTPFail as e:
            if e.code in (400, 401, 403): self.session = None; self._save_session(); raise CloudAuthError(_auth_message(e.message)) from None
            raise CloudError(f"Помилка хмари ({e.code}): {e.message}") from None
        self._set_session(r, self.session.get("email"))

    def _id_token(self):
        with self._lock:
            if not self.session: raise CloudAuthError("Увійдіть у хмару (головне вікно → «☁ Увійти…»).")
            if time.time() >= self.session.get("expiresAt", 0): self._refresh()
            return self.session["idToken"]

    # ── Firestore ──
    def _fs(self, method, path, body=None, params=None, _retry=True):
        url = f"{self._fs_root}/{path}" + (("?" + urllib.parse.urlencode(params, doseq=True)) if params else "")
        try: return self._http(method, url, body, {"Authorization": f"Bearer {self._id_token()}"})
        except _HTTPFail as e:
            if e.code == 401 and _retry:
                with self._lock: self._refresh()
                return self._fs(method, path, body, params, _retry=False)
            if e.code == 403 or e.status == "PERMISSION_DENIED": raise CloudDenied("Хмара відмовила в доступі (немає прав або облік року закрито).") from None
            if e.code == 404: raise _NotFound(e.message) from None
            if e.status == "FAILED_PRECONDITION" and "index" in e.message.lower():
                raise CloudError("У хмарі ще будується індекс для вибірки значень – спробуйте за кілька хвилин.") from None
            raise CloudError(f"Помилка хмари ({e.code} {e.status}): {e.message}") from None

    def doc_name(self, path): return f"projects/{self.project}/databases/(default)/documents/{path}"

    def get(self, path):
        try: return unfields(self._fs("GET", f"documents/{path}"))
        except _NotFound: return None

    def commit(self, writes):
        for i in range(0, len(writes), BATCH): self._fs("POST", "documents:commit", {"writes": writes[i:i + BATCH]})

    def set_doc(self, path, data, mask=None, must_exist=None):
        w = {"update": {"name": self.doc_name(path), "fields": fields(data)}}
        if mask: w["updateMask"] = {"fieldPaths": list(mask)}
        if must_exist is not None: w["currentDocument"] = {"exists": bool(must_exist)}
        return w

    def delete_doc(self, path): return {"delete": self.doc_name(path)}

    def query(self, parent, collection, filters=(), order=None, limit=None):
        """filters: [(поле, оп, значення)], оп – EQUAL, GREATER_THAN, ARRAY_CONTAINS…; повертає [(id, дані, час_оновлення)]."""
        sq = {"from": [{"collectionId": collection}]}
        fl = [{"fieldFilter": {"field": {"fieldPath": f}, "op": op, "value": v if isinstance(v, dict) else enc(v)}} for f, op, v in filters]
        if len(fl) == 1: sq["where"] = fl[0]
        elif fl: sq["where"] = {"compositeFilter": {"op": "AND", "filters": fl}}
        if order: sq["orderBy"] = [{"field": {"fieldPath": order}, "direction": "ASCENDING"}]
        if limit: sq["limit"] = limit
        res = self._fs("POST", f"documents/{parent}:runQuery" if parent else "documents:runQuery", {"structuredQuery": sq})
        out = []
        for item in res if isinstance(res, list) else [res]:
            d = item.get("document")
            if d: out.append((d["name"].rsplit("/", 1)[1], unfields(d), d.get("updateTime")))
        return out

    # ── дослід ──
    def exp_id(self, code): return f"{self.uid}_{code}"

    def upload_experiment(self, scheme, qr):
        """Надсилає (або оновлює) дослід і поточну версію схеми з маніфестом ділянок. Список виконавців і закриті роки зберігаються.
        → (id досліду, підпис схеми, дані досліду з build_cloud_experiment)."""
        data = build_cloud_experiment(scheme, qr); e = data["exp"]
        eid = self.exp_id(e["id"]); cur = self.get(f"experiments/{eid}") or {}
        blind = bool(data.get("blind"))
        doc = {"ownerUid": self.uid, "ownerEmail": self.email, "code": e["id"], "name": "" if blind else e.get("name", ""),
               "mode": "blind" if blind else "open", "status": cur.get("status", "active"),
               "memberEmails": list(cur.get("memberEmails") or []), "closedYears": list(cur.get("closedYears") or []),
               "schemeSig": e["signature"], "updatedAt": _dt.datetime.now(_dt.timezone.utc)}
        man = cloud_manifest(data)
        sdoc = {"sig": e["signature"], "manifest": json.dumps(man, ensure_ascii=False, separators=(",", ":")), "uploadedAt": _dt.datetime.now(_dt.timezone.utc)}
        self.commit([self.set_doc(f"experiments/{eid}", doc)])        # окремо: правила перевіряють власника схеми за вже записаним дослідом
        self.commit([self.set_doc(f"experiments/{eid}/schemes/{e['signature']}", sdoc)])
        return eid, e["signature"], data

    def experiment(self, eid): return self.get(f"experiments/{eid}")

    def update_experiment(self, eid, **changes):
        """Змінює поля досліду (memberEmails, closedYears, status) – лише власник."""
        if "memberEmails" in changes: changes["memberEmails"] = sorted({m.strip().lower() for m in changes["memberEmails"] if m and m.strip()})
        if "closedYears" in changes: changes["closedYears"] = sorted({int(y) for y in changes["closedYears"]})
        changes["updatedAt"] = _dt.datetime.now(_dt.timezone.utc)
        self.commit([self.set_doc(f"experiments/{eid}", changes, mask=list(changes), must_exist=True)])

    def my_experiments(self):
        own = self.query("", "experiments", [("ownerUid", "EQUAL", self.uid)])
        shared = self.query("", "experiments", [("memberEmails", "ARRAY_CONTAINS", self.email)]) if self.verified else []
        seen = {}; [seen.setdefault(i, d) for i, d, _ in own + shared]; return seen

    # ── показники ──
    def indicators(self, eid, year=None):
        flt = [("year", "EQUAL", int(year))] if year is not None else []
        return {i: d for i, d, _ in self.query(f"experiments/{eid}", "indicators", flt)}

    def set_indicators(self, eid, items):
        """items: [{"name", "unit", "kind", "year", "meta"}] – створює/оновлює показники (виконавець обирає їх у застосунку)."""
        ws = []
        for it in items:
            d = {"name": it["name"], "unit": it.get("unit", ""), "kind": it.get("kind") or "number", "year": int(it["year"])}
            if it.get("meta"): d["meta"] = it["meta"]
            ws.append(self.set_doc(f"experiments/{eid}/indicators/{indicator_id(it['name'], it['year'])}", d))
        if ws: self.commit(ws)

    def delete_indicator(self, eid, name, year):
        self.commit([self.delete_doc(f"experiments/{eid}/indicators/{indicator_id(name, year)}")])

    # ── значення ──
    def value_write(self, eid, vid, v):
        w = self.set_doc(f"experiments/{eid}/values/{vid}", v, must_exist=False)
        w["updateTransforms"] = [{"fieldPath": "serverTime", "setToServerValue": "REQUEST_TIME"}]
        return w

    def push_values(self, eid, items):
        """items: [(id, поля значення без serverTime)] – створює записи значень (атомарно порціями)."""
        self.commit([self.value_write(eid, vid, v) for vid, v in items])

    def values_since(self, eid, year, cursor=None, page=500):
        """Значення року, що з'явилися в хмарі після cursor (час сервера) – у порядку надходження. → [(id, дані)]."""
        out, ids, cur = [], set(), cursor
        while True:
            flt = [("year", "EQUAL", int(year))]
            if cur: flt.append(("serverTime", "GREATER_THAN_OR_EQUAL", {"timestampValue": cur}))
            rows = self.query(f"experiments/{eid}", "values", flt, order="serverTime", limit=page)
            fresh = [(i, d) for i, d, _ in rows if i not in ids]
            out += fresh; ids.update(i for i, _ in fresh)
            if len(rows) < page or not fresh: break
            cur = rows[-1][1]["serverTime"]
        return out


class _HTTPFail(Exception):
    def __init__(self, code, status, message): super().__init__(message); self.code, self.status, self.message = code, status, message


class _NotFound(Exception): pass


# ═══════════════════════════════════════════════════════════════
# Дослід і маніфест для хмари
# ═══════════════════════════════════════════════════════════════
def build_cloud_experiment(scheme, qr):
    """Опис досліду й ділянок (як для QR-табличок): код досліду й назва – з налаштувань QR у схемі; у сліпому режимі – шифри ділянок
    (ті самі, що на надрукованих табличках). Кидає ValueError, якщо схема не підходить."""
    import sad_qrlabels as Q
    qr = qr or {}; code = (qr.get("exp_id") or "").strip().upper()
    if not Q.valid_exp_id(code): raise ValueError("У схемі ще немає коду досліду. Відкрийте «QR-таблички для ділянок» у конструкторі схеми, задайте код і збережіть схему.")
    data = Q.build_experiment(scheme, code, qr.get("exp_name", ""), qr.get("origin", ""))
    if qr.get("style") == "blind":
        store = {"ciphers": dict(qr.get("ciphers") or {}), "cipher_sig": qr.get("cipher_sig", "")}
        if Q.assign_ciphers(data, store):
            raise ValueError("Шифри сліпого обліку не збігаються зі схемою. Відкрийте «QR-таблички» в конструкторі, збережіть схему й передрукуйте таблички.")
    return data


def cloud_manifest(data):
    """Маніфест ділянок для застосунку (формат QR_FORMAT.md, без повного тексту QR); у сліпому режимі – без варіантів і назви досліду."""
    import sad_qrlabels as Q
    m = Q.manifest_dict(data)
    for p in m["plots"]: p.pop("payload", None)
    return m


def plot_map(data):
    """(ряд, місце) облікової рослини/ділянки → номер ділянки."""
    return {(int(r), int(q)): no for r, cells in data["grid"].items() for q, (kind, no) in cells.items() if kind == "plot"}


# ═══════════════════════════════════════════════════════════════
# Значення журналу ⇄ хмара
# ═══════════════════════════════════════════════════════════════
def is_date_record(rec): return (rec or {}).get("kind") == "date"


def to_cloud_value(raw, is_date, year):
    """Значення з журналу → хмара: число або дата «РРРР-ММ-ДД». None – значення не можна передати (текст)."""
    if raw is None or str(raw).strip() == "": return None
    if is_date:
        import sad_phenology as _P
        try: y = int(year)
        except (TypeError, ValueError): y = _dt.date.today().year
        d, _m = _P.parse_date_flex(str(raw), y)
        return d.isoformat() if d else None
    try:
        v = float(str(raw).strip().replace(",", ".").replace(" ", "").replace(" ", ""))
    except ValueError: return None
    return v if v == v and abs(v) != float("inf") else None


def to_journal_value(v, is_date):
    if v is None: return None
    if is_date:
        try: return _dt.date.fromisoformat(str(v)).strftime("%d.%m.%Y")
        except ValueError: return str(v)
    if isinstance(v, (int, float)):
        s = format(float(v), ".10g")
        return s.replace(".", ",")
    return str(v)


def same_value(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)): return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    return a == b


# ═══════════════════════════════════════════════════════════════
# Локальний стан синхронізації теки схеми
# ═══════════════════════════════════════════════════════════════
class SyncState:
    """Файл <тека схеми>/.sad_cloud.json:
       exp_id, sig, owner – прив'язка теки до досліду в хмарі;
       years[рік] = {cursor, cursor_ids, known{показник{"р:м": {id, v, a, e}}}} – що вже є в хмарі (останній запис кожної клітинки);
       outbox = [[id, поля]] – записи, ще не надіслані (немає зв'язку)."""
    def __init__(self, folder):
        self.folder = folder; self.path = os.path.join(folder, STATE_FILE); self._lock = threading.RLock()
        try:
            with open(self.path, "r", encoding="utf-8") as f: self.d = json.load(f)
        except Exception: self.d = {}
        self.d.setdefault("years", {}); self.d.setdefault("outbox", [])

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f: json.dump(self.d, f, ensure_ascii=False)
            os.replace(tmp, self.path)

    def year(self, y):
        return self.d["years"].setdefault(str(y), {"cursor": None, "cursor_ids": [], "known": {}})

    def bind(self, exp_id, sig, owner):
        if self.d.get("exp_id") and self.d.get("exp_id") != exp_id:          # тека прив'язана до іншого досліду – стан старого не годиться
            self.d = {"years": {}, "outbox": []}
        self.d.update(exp_id=exp_id, sig=sig, owner=owner)

    @property
    def exp_id(self): return self.d.get("exp_id")

    def enqueue(self, items):
        with self._lock: self.d["outbox"].extend([list(x) for x in items]); self.save()

    def outbox(self):
        with self._lock: return [tuple(x) for x in self.d["outbox"]]

    def drop(self, ids):
        ids = set(ids)
        with self._lock: self.d["outbox"] = [x for x in self.d["outbox"] if x[0] not in ids]; self.save()


# ═══════════════════════════════════════════════════════════════
# Що надіслати після збереження журналу
# ═══════════════════════════════════════════════════════════════
def plan_push(state, journal, pmap, uid, email, sig="", device="S.A.D."):
    """Порівнює журнал року з тим, що вже в хмарі (state.known), і повертає нові записи [(id, поля)] для змінених, нових і очищених
    клітинок. state.known одразу оновлюється (записи вже в черзі). Показники, яких немає в журналі, не чіпаються."""
    year = int(journal.get("year")); ys = state.year(year); out = []; skipped = 0
    now = _dt.datetime.now(_dt.timezone.utc)
    for name, rec in (journal.get("records") or {}).items():
        is_d = is_date_record(rec); kn = ys["known"].setdefault(name, {}); vals = rec.get("values") or {}
        keys = set(vals) | {k for k, e in kn.items() if e.get("v") is not None}
        for key in sorted(keys):
            try: r, q = (int(x) for x in key.split(":"))
            except ValueError: continue
            plot = pmap.get((r, q))
            if plot is None: continue
            new = to_cloud_value(vals.get(key), is_d, year) if key in vals else None
            if key in vals and new is None and str(vals.get(key)).strip(): skipped += 1; continue
            old = kn.get(key)
            if old and same_value(old.get("v"), new): continue
            if not old and new is None: continue
            vid = new_id()
            f = {"plot": plot, "row": r, "pos": q, "indicator": name, "year": year, "value": new, "authorUid": uid, "authorEmail": email,
                 "clientTime": now, "device": device}
            if sig: f["schemeSig"] = sig
            if old and old.get("id"): f["supersedes"] = old["id"]
            if new is None: f["deleted"] = True
            out.append((vid, f)); kn[key] = {"id": vid, "v": new, "a": uid, "e": email}
    return out, skipped


def serialize(items):
    """Записи для черги на диску (час – рядком)."""
    return [(vid, {k: (enc(v)["timestampValue"] if isinstance(v, _dt.datetime) else v) for k, v in f.items()}) for vid, f in items]


def deserialize(items):
    out = []
    for vid, f in items:
        g = dict(f)
        if isinstance(g.get("clientTime"), str):
            g["clientTime"] = _dt.datetime.strptime(g["clientTime"].rstrip("Z")[:26], "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=_dt.timezone.utc)
        out.append((vid, g))
    return out


# ═══════════════════════════════════════════════════════════════
# Як внести в журнал значення, що прийшли з хмари
# ═══════════════════════════════════════════════════════════════
def apply_pulled(state, journal, docs, indicators=None, uid=""):
    """docs – [(id, дані)] у порядку надходження. Вносить чужі (і власні з іншого пристрою) записи в journal["records"], позначає конфлікти,
    просуває курсор. indicators – {id: дані} показників (одиниця й тип для нових показників). → зведення {applied, conflicts, authors, new_records}."""
    year = int(journal.get("year")); ys = state.year(year); recs = journal.setdefault("records", {})
    by_name = {d.get("name"): d for d in (indicators or {}).values() if int(d.get("year", year)) == year}
    seen_at_cursor = set(ys.get("cursor_ids") or []); cur = ys.get("cursor")
    summ = {"applied": 0, "conflicts": 0, "authors": set(), "new_records": []}
    for vid, d in docs:
        t = d.get("serverTime")
        if cur and ts_key(t) < ts_key(cur): continue
        if cur and ts_key(t) == ts_key(cur) and vid in seen_at_cursor: continue
        if ts_key(t) > ts_key(cur): cur, seen_at_cursor = t, set()
        seen_at_cursor.add(vid)
        name = d.get("indicator"); key = f"{d.get('row')}:{d.get('pos')}"
        kn = ys["known"].setdefault(name, {}); old = kn.get(key)
        if old and old.get("id") == vid: continue                      # власний запис із цього комп'ютера
        rec = recs.get(name)
        if rec is None:
            meta = by_name.get(name) or {}
            rec = {"unit": meta.get("unit", ""), "values": {}}
            if meta.get("kind") == "date": rec["kind"] = "date"
            rec.update({k: v for k, v in (meta.get("meta") or {}).items() if k in ("kind", "preset", "phase_key", "bbch", "phase_name")})
            recs[name] = rec; summ["new_records"].append(name)
        is_d = is_date_record(rec); val = d.get("value"); deleted = bool(d.get("deleted"))
        conf = rec.setdefault("conflicts", {})
        if old and old.get("a") != d.get("authorUid") and d.get("supersedes") != old.get("id") and not same_value(old.get("v"), val) \
                and old.get("v") is not None and not deleted:
            conf[key] = [{"value": to_journal_value(old.get("v"), is_d), "author": old.get("e", ""), "id": old.get("id")},
                         {"value": to_journal_value(val, is_d), "author": d.get("authorEmail", ""), "id": vid}]
            summ["conflicts"] += 1
        elif key in conf and d.get("supersedes") in {c.get("id") for c in conf[key]}:
            del conf[key]                                               # хтось виправив одне зі спірних значень – конфлікт розв'язано
        if not conf: rec.pop("conflicts", None)
        if deleted or val is None: rec.setdefault("values", {}).pop(key, None)
        else: rec.setdefault("values", {})[key] = to_journal_value(val, is_d)
        kn[key] = {"id": vid, "v": None if deleted else val, "a": d.get("authorUid", ""), "e": d.get("authorEmail", "")}
        summ["applied"] += 1
        if d.get("authorEmail"): summ["authors"].add(d["authorEmail"])
    ys["cursor"], ys["cursor_ids"] = cur, sorted(seen_at_cursor)
    return summ


# ═══════════════════════════════════════════════════════════════
# Файли журналу: новий рік, резервна копія, запис
# ═══════════════════════════════════════════════════════════════
def journal_path(folder, year): return os.path.join(folder, str(year), f"журнал_{year}.sadp")


def load_or_new_journal(folder, year, scheme, version=""):
    p = journal_path(folder, year)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    return {"type": "field_journal", "version": version, "year": str(year), "cfg": scheme.get("cfg", {}),
            "variant_names": scheme.get("variant_names", []), "factor_defs": scheme.get("factor_defs", []),
            "plants": scheme.get("plants", []), "records": {}, "series": scheme.get("series", {})}


def backup_journal(folder, year):
    """Копія файлу журналу перед оновленням із хмари (зберігаються останні BACKUP_KEEP копій)."""
    p = journal_path(folder, year)
    if not os.path.exists(p): return None
    bd = os.path.join(folder, BACKUP_DIR); os.makedirs(bd, exist_ok=True)
    dst = os.path.join(bd, f"журнал_{year}_{_dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sadp"); shutil.copy2(p, dst)
    olds = sorted(f for f in os.listdir(bd) if f.startswith(f"журнал_{year}_"))
    for f in olds[:-BACKUP_KEEP]:
        try: os.remove(os.path.join(bd, f))
        except OSError: pass
    return dst


def write_journal(folder, year, journal):
    p = journal_path(folder, year); os.makedirs(os.path.dirname(p), exist_ok=True); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(journal, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p); return p
