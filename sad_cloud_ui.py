# sad_cloud_ui.py – S.A.D. v2.1: хмара в інтерфейсі: вхід, обліковий запис, синхронізація польового журналу, «Хмара і доступ»
# -*- coding: utf-8 -*-
import os, json, queue, threading, datetime as _dt
import tkinter as tk
from tkinter import ttk, messagebox
import sad_cloud as C

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)
SYNC_EVERY_MS = 60_000                    # автоматична перевірка нових значень з поля
_cloud = None; _listeners = []


def get_cloud():
    global _cloud
    if _cloud is None: _cloud = C.Cloud()
    return _cloud


def on_account_change(fn): _listeners.append(fn)


def _notify():
    for fn in list(_listeners):
        try: fn()
        except Exception: _listeners.remove(fn)


def account_text():
    cl = get_cloud()
    if not cl.signed_in: return "☁ Увійти в хмару…"
    return f"☁ {cl.email}" + ("" if cl.verified else " (не підтверджено)")


def run_bg(widget, fn, done, poll=100):
    """fn() у фоновому потоці (мережа не «заморожує» вікно); done(результат, помилка) – у головному потоці Tk."""
    q = queue.Queue()
    def work():
        try: q.put((fn(), None))
        except Exception as e: q.put((None, e))
    threading.Thread(target=work, daemon=True).start()
    def check():
        try: res, err = q.get_nowait()
        except queue.Empty:
            try: widget.after(poll, check)
            except tk.TclError: pass
            return
        done(res, err)
    widget.after(poll, check)


def _center(win):
    try:
        from sad_common import set_icon, center_win; set_icon(win); center_win(win)
    except Exception: pass


# ═══════════════════════════════════════════════════════════════
# Вхід і обліковий запис
# ═══════════════════════════════════════════════════════════════
def account_dialog(parent):
    """Вхід / реєстрація, якщо ще не ввійшли; інакше – стан облікового запису."""
    cl = get_cloud()
    return _signed_in_dialog(parent) if cl.signed_in else _login_dialog(parent)


def _login_dialog(parent):
    cl = get_cloud()
    dlg = tk.Toplevel(parent); dlg.title("Хмара S.A.D. – вхід"); dlg.resizable(False, False); dlg.transient(parent)
    f = tk.Frame(dlg, padx=18, pady=14); f.pack()
    tk.Label(f, text="Вхід у хмару S.A.D.", font=("Times New Roman", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(f, text="Досліди й обліки зберігаються не лише на комп'ютері, а й у хмарі: виконавці вносять значення в застосунку на телефоні, "
                     "і вони самі з'являються в польовому журналі.", font=SM, fg="#555", wraplength=380, justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))
    tk.Label(f, text="Електронна пошта:", font=RF).grid(row=2, column=0, sticky="w")
    v_mail = tk.StringVar(value=cl.email); e_mail = tk.Entry(f, textvariable=v_mail, width=32, font=RF); e_mail.grid(row=2, column=1, pady=3)
    tk.Label(f, text="Пароль:", font=RF).grid(row=3, column=0, sticky="w")
    v_pw = tk.StringVar(); e_pw = tk.Entry(f, textvariable=v_pw, width=32, font=RF, show="•"); e_pw.grid(row=3, column=1, pady=3)
    msg = tk.Label(f, text="", font=SM, fg="#c62828", wraplength=380, justify="left"); msg.grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))
    bf = tk.Frame(f); bf.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="we")
    btns = []

    def busy(on):
        for b in btns: b.configure(state=tk.DISABLED if on else tk.NORMAL)
        dlg.configure(cursor="watch" if on else "")

    def act(kind):
        mail, pw = v_mail.get().strip(), v_pw.get()
        if not mail or "@" not in mail: msg.configure(text="Вкажіть адресу електронної пошти."); return
        if kind != "reset" and len(pw) < 6: msg.configure(text="Пароль – щонайменше 6 символів."); return
        msg.configure(text="Зачекайте…", fg="#1a4b8c"); busy(True)
        fn = {"in": lambda: cl.sign_in(mail, pw), "up": lambda: cl.sign_up(mail, pw), "reset": lambda: cl.reset_password(mail)}[kind]
        def done(_r, err):
            busy(False)
            if err is not None: msg.configure(text=str(err), fg="#c62828"); return
            if kind == "reset":
                msg.configure(text=f"Лист для відновлення пароля надіслано на {mail}.", fg="#1a6b1a"); return
            _notify(); dlg.destroy()
            if kind == "up" or not cl.verified:
                messagebox.showinfo("Підтвердіть адресу",
                    f"Ми надіслали лист на {cl.email}.\n\nВідкрийте його й перейдіть за посиланням – так хмара знає, що адреса ваша. "
                    "Після цього натисніть у S.A.D. «☁ …» → «Я підтвердив адресу».\n\nЯкщо листа немає – перевірте теку «Спам».", parent=parent)
        run_bg(dlg, fn, done)

    for txt, kind, bg in (("Увійти", "in", "#1a6b1a"), ("Зареєструватися", "up", "#1a4b8c"), ("Забули пароль?", "reset", None)):
        b = tk.Button(bf, text=txt, font=RF, command=lambda k=kind: act(k), **({"bg": bg, "fg": "white"} if bg else {})); b.pack(side=tk.LEFT, padx=(0, 6)); btns.append(b)
    tk.Button(bf, text="Скасувати", font=RF, command=dlg.destroy).pack(side=tk.RIGHT)
    tk.Label(f, text="Новий користувач – введіть адресу, придумайте пароль і натисніть «Зареєструватися».", font=SM, fg="#666", wraplength=380, justify="left"
             ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))
    e_pw.bind("<Return>", lambda e: act("in")); (e_pw if cl.email else e_mail).focus_set(); _center(dlg)
    return dlg


def _signed_in_dialog(parent):
    cl = get_cloud()
    dlg = tk.Toplevel(parent); dlg.title("Хмара S.A.D. – обліковий запис"); dlg.resizable(False, False); dlg.transient(parent)
    f = tk.Frame(dlg, padx=18, pady=14); f.pack()
    tk.Label(f, text=cl.email, font=("Times New Roman", 13, "bold")).pack(anchor="w")
    st = tk.Label(f, text="", font=RF, justify="left", wraplength=380); st.pack(anchor="w", pady=(4, 8))
    msg = tk.Label(f, text="", font=SM, fg="#1a4b8c", wraplength=380, justify="left"); msg.pack(anchor="w")
    bf = tk.Frame(f); bf.pack(fill=tk.X, pady=(8, 0))

    def refresh():
        st.configure(text="✓ Адресу підтверджено – можна надсилати досліди в хмару й запрошувати виконавців." if cl.verified else
                     "Адресу ще не підтверджено. Відкрийте лист від хмари S.A.D. і перейдіть за посиланням (перевірте й теку «Спам»).",
                     fg="#1a6b1a" if cl.verified else "#8c5a1a")
        for w in bf.winfo_children(): w.destroy()
        if not cl.verified:
            tk.Button(bf, text="Я підтвердив адресу", font=RF, bg="#1a6b1a", fg="white", command=check).pack(side=tk.LEFT, padx=(0, 6))
            tk.Button(bf, text="Надіслати лист ще раз", font=RF, command=resend).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(bf, text="Вийти", font=RF, command=out).pack(side=tk.LEFT)
        tk.Button(bf, text="Закрити", font=RF, command=dlg.destroy).pack(side=tk.RIGHT)

    def check():
        msg.configure(text="Перевіряю…")
        def done(ok, err):
            if err is not None: msg.configure(text=str(err), fg="#c62828"); return
            msg.configure(text="" if ok else "Хмара ще не бачить підтвердження. Перейдіть за посиланням у листі й спробуйте знову.", fg="#8c5a1a")
            _notify(); refresh()
        run_bg(dlg, cl.check_verified, done)

    def resend():
        def done(_r, err): msg.configure(text=str(err) if err else f"Лист надіслано на {cl.email}.", fg="#c62828" if err else "#1a6b1a")
        run_bg(dlg, cl.send_verification, done)

    def out():
        if messagebox.askyesno("Вийти з хмари", "Вийти з облікового запису? Дані на комп'ютері лишаються; синхронізація зупиниться до наступного входу.", parent=dlg):
            cl.sign_out(); _notify(); dlg.destroy()
    refresh(); _center(dlg)
    return dlg


# ═══════════════════════════════════════════════════════════════
# Синхронізація польового журналу
# ═══════════════════════════════════════════════════════════════
class JournalCloud:
    """Хмара для одного вікна польового журналу: прив'язка теки схеми до досліду, автоматичне надсилання після кожного збереження,
    перевірка нових значень з поля щохвилини, позначка стану. Усі мережеві запити – у фоновому потоці."""
    def __init__(self, jw, status_label):
        self.jw, self.lbl = jw, status_label; self.cl = get_cloud()
        self.state = None; self.folder = None; self.scheme = None; self.data = None; self.pmap = {}; self.eid = None; self.sig = ""
        self._busy = False; self._again = False; self._timer = None; self.last = None; self.err = None; self.note = ""
        on_account_change(self._account_changed)
        self.lbl.bind("<Button-1>", lambda e: self.open_dialog())

    # ── стан для користувача ──
    def show(self, text=None, color=None):
        if text is None:
            if not self.cl.signed_in: text, color = "☁ Хмара: не ввійшли (натисніть, щоб увійти)", "#888"
            elif self.err: text, color = f"☁ {self.err}", "#c62828"
            else:
                n = len(self.state.outbox()) if self.state else 0
                when = self.last.strftime("%H:%M") if self.last else "–"
                text = (f"☁ Немає зв'язку · у черзі {n} знач. (надішлю, щойно з'явиться)" if n else f"☁ Усе збережено в хмарі · {when}") + (f" · {self.note}" if self.note else "")
                color = "#8c5a1a" if n else "#1a6b1a"
        try: self.lbl.configure(text=text, fg=color or "#555")
        except tk.TclError: pass

    def _account_changed(self):
        try: self.jw.win.winfo_exists()
        except tk.TclError: return
        self.err = None; self.attach()

    # ── прив'язка до теки схеми ──
    def attach(self):
        """Викликається після відкриття схеми чи зміни року: читає схему, готує дослід для хмари і запускає синхронізацію."""
        jw = self.jw; self.err = None; self.note = ""
        if not jw._scheme_folder: self.show("☁ Хмара: відкрийте схему", "#888"); return
        if self.folder != jw._scheme_folder:
            self.folder = jw._scheme_folder; self.state = C.SyncState(self.folder); self.eid = None
        if not self.cl.signed_in: self.show(); return
        sch = None
        if jw._scheme_file_path and os.path.exists(jw._scheme_file_path):
            try:
                with open(jw._scheme_file_path, "r", encoding="utf-8") as f: sch = json.load(f)
            except Exception: sch = None
        if sch is None: self.err = "Хмара: не знайдено файл схеми в теці"; self.show(); return
        if (sch.get("cfg") or {}).get("blind"):
            self.err = "Це схема для виконавців – у хмару дослід надсилає керівник"; self.show(); return
        try: self.data = C.build_cloud_experiment(sch, (sch.get("cfg") or {}).get("qr"))
        except ValueError as e:
            self.err = "Хмара: " + str(e).split(". ")[0]; self.show(); return
        self.scheme = sch; self.pmap = C.plot_map(self.data); self.sig = self.data["exp"]["signature"]
        self.eid = self.cl.exp_id(self.data["exp"]["id"]); self.sync()

    def close(self):
        if self._timer:
            try: self.jw.win.after_cancel(self._timer)
            except tk.TclError: pass
        self._timer = None
        if self.state: self.state.save()

    # ── цикл синхронізації ──
    def on_saved(self):
        """Після кожного збереження журналу: одразу надіслати зміни."""
        self.sync()

    def sync(self):
        if not (self.cl.signed_in and self.eid and self.state): self.show(); return
        if self._busy: self._again = True; return
        jw = self.jw; years = sorted({str(y) for y in (jw._current_year, _dt.date.today().year) if y})
        if not self.cl.verified:
            self.err = "Хмара: підтвердьте адресу пошти (натисніть тут)"; self.show(); return
        self.note = ""
        # 1) що змінилося в журналі (головний потік: читаємо файли, ставимо записи в чергу)
        for y in years:
            p = C.journal_path(self.folder, y)
            if not os.path.exists(p): continue
            try:
                with open(p, "r", encoding="utf-8") as f: jd = json.load(f)
            except Exception: continue
            items, skipped = C.plan_push(self.state, jd, self.pmap, self.cl.uid, self.cl.email, self.sig)
            if items: self.state.enqueue(C.serialize(items))
            if skipped: self.note = f"не надіслано (не число): {skipped}"
        self.state.save()
        need_upload = (self.state.exp_id != self.eid or self.state.d.get("sig") != self.sig
                       or self.state.d.get("man_hash") != self._man_hash())
        indicators_local = {y: self._local_indicators(y) for y in years}
        cursors = {y: self.state.year(y).get("cursor") for y in years}
        outbox = C.deserialize(self.state.outbox()); eid, cl, scheme = self.eid, self.cl, self.scheme
        self._busy = True; self.show("☁ Синхронізація…", "#1a4b8c")

        def work():
            res = {"pushed": [], "denied": [], "docs": {}, "inds": {}, "offline": False, "uploaded": False}
            try:
                if need_upload:
                    cl.upload_experiment(scheme, (scheme.get("cfg") or {}).get("qr")); res["uploaded"] = True
                for i in range(0, len(outbox), C.BATCH):
                    chunk = outbox[i:i + C.BATCH]
                    try: cl.push_values(eid, chunk); res["pushed"] += [vid for vid, _ in chunk]
                    except C.CloudDenied:                              # рік закрито чи інша відмова – по одному, щоб не загубити решту
                        for vid, f in chunk:
                            try: cl.push_values(eid, [(vid, f)]); res["pushed"].append(vid)
                            except C.CloudDenied: res["denied"].append(vid)
                for y in years:
                    cur_inds = cl.indicators(eid, y); res["inds"][y] = cur_inds
                    have = {(d.get("name"), d.get("unit", ""), d.get("kind", "number")) for d in cur_inds.values()}
                    missing = [it for it in indicators_local[y] if (it["name"], it["unit"], it["kind"]) not in have]
                    if missing: cl.set_indicators(eid, missing); res["inds"][y] = cl.indicators(eid, y)
                    res["docs"][y] = cl.values_since(eid, y, cursors[y])
            except C.CloudOffline: res["offline"] = True
            return res

        run_bg(jw.win, work, self._done)

    def _done(self, res, err):
        self._busy = False
        try: self.jw.win.winfo_exists()
        except tk.TclError: return
        if err is not None:
            self.err = ("Хмара: " + str(err)) if not isinstance(err, C.CloudAuthError) else "Хмара: увійдіть знову (натисніть тут)"
            if isinstance(err, C.CloudAuthError): _notify()
        else:
            self.err = None
            if res["uploaded"]: self.state.d.update(man_hash=self._man_hash()); self.state.bind(self.eid, self.sig, self.cl.uid)
            if res["pushed"] or res["denied"]: self.state.drop(res["pushed"] + res["denied"])
            if res["denied"]: self.note = f"хмара відхилила {len(res['denied'])} знач. (облік року закрито?)"
            fresh = []
            for y, docs in res["docs"].items():
                if not docs: continue
                s = self._apply(y, docs, res["inds"].get(y, {}))
                if s["applied"]: fresh.append((y, s))
            self.state.save()
            if not res["offline"]: self.last = _dt.datetime.now()
            if fresh:
                n = sum(s["applied"] for _, s in fresh); nc = sum(s["conflicts"] for _, s in fresh)
                who = ", ".join(sorted(set().union(*[s["authors"] for _, s in fresh]) - {self.cl.email}))[:60]
                self.note = f"нові значення з поля: {n}" + (f" ({who})" if who else "") + (f" · ⚠ конфліктів: {nc}" if nc else "")
        self.show()
        if self._again: self._again = False; self.sync(); return
        if self._timer:
            try: self.jw.win.after_cancel(self._timer)
            except tk.TclError: pass
        try: self._timer = self.jw.win.after(SYNC_EVERY_MS, self.sync)
        except tk.TclError: self._timer = None

    def _apply(self, year, docs, inds):
        """Вносить значення з поля у файл журналу року (з резервною копією) і, якщо цей рік відкрито, – у вікно."""
        jw = self.jw
        try: from sad_common import APP_VER as _ver
        except Exception: _ver = ""
        jd = C.load_or_new_journal(self.folder, year, self.scheme, _ver)
        s = C.apply_pulled(self.state, jd, docs, inds, self.cl.uid)
        if not s["applied"]: return s
        C.backup_journal(self.folder, year); path = C.write_journal(self.folder, year, jd)
        if str(jw._current_year) == str(year):
            cur = jw._current_indicator_name
            unsaved = cur is None and bool(jw._working_values) or (cur and jw._working_values != jw.records.get(cur, {}).get("values", {}))
            jw.records = jd.get("records", {}); jw._journal_path = path
            jw._record_cb.configure(values=["(новий показник)"] + list(jw.records.keys()))
            if cur in jw.records and not unsaved: jw._working_values = dict(jw.records[cur]["values"])
            if not unsaved: jw._build_grid()
        return s

    def _man_hash(self):
        import hashlib
        try: return hashlib.sha1(json.dumps(C.cloud_manifest(self.data), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        except Exception: return ""

    def _local_indicators(self, year):
        p = C.journal_path(self.folder, year); out = []
        try:
            with open(p, "r", encoding="utf-8") as f: recs = json.load(f).get("records", {})
        except Exception: recs = {}
        for nm, r in recs.items():
            it = {"name": nm, "unit": r.get("unit", ""), "kind": "date" if r.get("kind") == "date" else "number", "year": int(year)}
            meta = {k: r[k] for k in ("kind", "preset", "phase_key", "bbch", "phase_name") if k in r}
            if meta: it["meta"] = meta
            out.append(it)
        return out

    # ── «Хмара і доступ» ──
    def open_dialog(self):
        if not self.cl.signed_in or not self.cl.verified: account_dialog(self.jw.win); return
        if not self.eid:
            messagebox.showinfo("Хмара", self.err or "Спочатку відкрийте схему досліду.", parent=self.jw.win); return
        AccessDialog(self)


class AccessDialog:
    """Виконавці (за адресою пошти), показники для застосунку на поточний рік, закриття обліку року."""
    def __init__(self, jc):
        self.jc = jc; self.cl = jc.cl; jw = jc.jw; self.year = int(jw._current_year or _dt.date.today().year)
        self.win = tk.Toplevel(jw.win); self.win.title("Хмара і доступ"); self.win.transient(jw.win); self.win.resizable(False, False)
        f = tk.Frame(self.win, padx=16, pady=12); f.pack(fill=tk.BOTH)
        e = jc.data["exp"]
        tk.Label(f, text=f"Дослід {e['id']}" + (f" · {e['name']}" if e.get("name") and not jc.data.get("blind") else "") + (" · сліпий облік" if jc.data.get("blind") else ""),
                 font=("Times New Roman", 13, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        self.msg = tk.Label(f, text="Завантаження…", font=SM, fg="#1a4b8c", wraplength=520, justify="left"); self.msg.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 8))
        m = tk.LabelFrame(f, text="Виконавці (запрошення за адресою пошти)", font=RB, padx=8, pady=6); m.grid(row=2, column=0, columnspan=3, sticky="we")
        self.lb_m = tk.Listbox(m, height=6, width=48, font=RF); self.lb_m.grid(row=0, column=0, rowspan=3, sticky="w")
        self.v_mail = tk.StringVar(); tk.Entry(m, textvariable=self.v_mail, width=28, font=RF).grid(row=0, column=1, padx=6, sticky="w")
        tk.Button(m, text="➕ Запросити", font=RF, command=self._add_member).grid(row=1, column=1, padx=6, sticky="we")
        tk.Button(m, text="✖ Відкликати доступ", font=RF, command=self._del_member).grid(row=2, column=1, padx=6, sticky="we")
        tk.Label(m, text="Виконавець встановлює застосунок і входить під цією адресою – дослід з'являється в його списку. "
                         "Відкликаний виконавець більше не бачить дослід; внесені ним дані лишаються.", font=SM, fg="#666", wraplength=500, justify="left"
                 ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        i = tk.LabelFrame(f, text=f"Показники для застосунку на {self.year} рік", font=RB, padx=8, pady=6); i.grid(row=3, column=0, columnspan=3, sticky="we", pady=(8, 0))
        self.lb_i = tk.Listbox(i, height=6, width=48, font=RF); self.lb_i.grid(row=0, column=0, rowspan=4, sticky="w")
        self.v_iname = tk.StringVar(); self.v_iunit = tk.StringVar(); self.v_ikind = tk.StringVar(value="число")
        g = tk.Frame(i); g.grid(row=0, column=1, padx=6, sticky="w")
        tk.Label(g, text="Назва:", font=SM).grid(row=0, column=0, sticky="w"); tk.Entry(g, textvariable=self.v_iname, width=20, font=RF).grid(row=0, column=1)
        tk.Label(g, text="Одиниця:", font=SM).grid(row=1, column=0, sticky="w"); tk.Entry(g, textvariable=self.v_iunit, width=10, font=RF).grid(row=1, column=1, sticky="w")
        tk.Label(g, text="Тип:", font=SM).grid(row=2, column=0, sticky="w")
        ttk.Combobox(g, textvariable=self.v_ikind, values=["число", "дата фенофази"], state="readonly", width=14).grid(row=2, column=1, sticky="w")
        tk.Button(i, text="➕ Додати показник", font=RF, command=self._add_ind).grid(row=1, column=1, padx=6, sticky="we")
        tk.Button(i, text="✖ Прибрати зі списку", font=RF, command=self._del_ind).grid(row=2, column=1, padx=6, sticky="we")
        tk.Label(i, text="Показники, уже збережені в журналі, додаються самі. Тут можна заздалегідь додати ті, які виконавці вноситимуть у полі.",
                 font=SM, fg="#666", wraplength=500, justify="left").grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.v_closed = tk.BooleanVar(value=False)
        self.cb_closed = tk.Checkbutton(f, text=f"🔒 Облік {self.year} року закрито (виконавці більше не вносять значень за цей рік)", variable=self.v_closed, font=RF, command=self._toggle_closed)
        self.cb_closed.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        tk.Button(f, text="Закрити", font=RF, command=self.win.destroy).grid(row=5, column=2, sticky="e", pady=(10, 0))
        self.exp = {}; self.inds = {}; _center(self.win); self._load()

    def _run(self, fn, after=None, text="Зачекайте…"):
        self.msg.configure(text=text, fg="#1a4b8c"); self.win.configure(cursor="watch")
        def done(res, err):
            try: self.win.configure(cursor="")
            except tk.TclError: return
            if err is not None: self.msg.configure(text=str(err), fg="#c62828"); return
            self.msg.configure(text="", fg="#1a4b8c")
            if after: after(res)
        run_bg(self.win, fn, done)

    def _load(self):
        jc = self.jc
        def fn():
            if jc.state.exp_id != jc.eid or not self.cl.experiment(jc.eid):
                self.cl.upload_experiment(jc.scheme, (jc.scheme.get("cfg") or {}).get("qr"))
            return self.cl.experiment(jc.eid), self.cl.indicators(jc.eid, self.year)
        self._run(fn, self._show)

    def _show(self, res):
        self.exp, self.inds = res
        self.lb_m.delete(0, tk.END)
        for m in self.exp.get("memberEmails") or []: self.lb_m.insert(tk.END, m)
        self.lb_i.delete(0, tk.END)
        for d in sorted(self.inds.values(), key=lambda d: d.get("name", "")):
            self.lb_i.insert(tk.END, f"{d.get('name')}" + (f", {d.get('unit')}" if d.get("unit") else "") + (" · дата" if d.get("kind") == "date" else ""))
        self.v_closed.set(self.year in (self.exp.get("closedYears") or []))
        if not self.exp.get("memberEmails"): self.msg.configure(text="Виконавців ще немає – додайте адресу й натисніть «Запросити».", fg="#555")

    def _members(self, emails):
        self._run(lambda: (self.cl.update_experiment(self.jc.eid, memberEmails=emails), self.cl.experiment(self.jc.eid), self.cl.indicators(self.jc.eid, self.year))[1:], self._show)

    def _add_member(self):
        m = self.v_mail.get().strip().lower()
        if "@" not in m or "." not in m.split("@")[-1]: self.msg.configure(text="Вкажіть правильну адресу пошти.", fg="#c62828"); return
        if m == self.cl.email: self.msg.configure(text="Це ваша адреса – ви власник досліду.", fg="#c62828"); return
        self.v_mail.set(""); self._members(list(self.exp.get("memberEmails") or []) + [m])

    def _del_member(self):
        sel = self.lb_m.curselection()
        if not sel: return
        m = self.lb_m.get(sel[0])
        if messagebox.askyesno("Відкликати доступ", f"Відкликати доступ для {m}? Внесені дані лишаться.", parent=self.win):
            self._members([x for x in (self.exp.get("memberEmails") or []) if x != m])

    def _add_ind(self):
        nm = self.v_iname.get().strip()
        if not nm: self.msg.configure(text="Вкажіть назву показника.", fg="#c62828"); return
        kind = "date" if self.v_ikind.get().startswith("дата") else "number"
        it = {"name": nm, "unit": self.v_iunit.get().strip() or ("дата" if kind == "date" else ""), "kind": kind, "year": self.year}
        if kind == "date": it["meta"] = {"kind": "date"}
        self.v_iname.set(""); self.v_iunit.set("")
        self._run(lambda: (self.cl.set_indicators(self.jc.eid, [it]), self.cl.experiment(self.jc.eid), self.cl.indicators(self.jc.eid, self.year))[1:], self._show)

    def _del_ind(self):
        sel = self.lb_i.curselection()
        if not sel: return
        d = sorted(self.inds.values(), key=lambda d: d.get("name", ""))[sel[0]]
        self._run(lambda: (self.cl.delete_indicator(self.jc.eid, d["name"], self.year), self.cl.experiment(self.jc.eid), self.cl.indicators(self.jc.eid, self.year))[1:], self._show)

    def _toggle_closed(self):
        ys = set(self.exp.get("closedYears") or [])
        ys = ys | {self.year} if self.v_closed.get() else ys - {self.year}
        self._run(lambda: (self.cl.update_experiment(self.jc.eid, closedYears=sorted(ys)), self.cl.experiment(self.jc.eid), self.cl.indicators(self.jc.eid, self.year))[1:], self._show)
