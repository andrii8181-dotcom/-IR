# sad_qr_dialog.py – S.A.D. v2.1: діалог «QR-таблички для ділянок» (перегляд, налаштування, збереження, друк)
# -*- coding: utf-8 -*-
import os, tempfile, datetime as _dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sad_qrlabels as Q

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)
STYLES = {"Описовий (читає будь-який телефон)": "descriptive", "Компактний (лише службовий рядок)": "compact"}
ECCS = {"M – звичайна (рекомендовано)": "m", "Q – підвищена стійкість до забруднення": "q"}
DEFAULTS = {"exp_name": "", "exp_id": "", "origin": "ряд 1, місце 1 – лівий верхній кут карти", "preset": "M", "style": "descriptive", "ecc": "m", "neighbors": True, "cut_lines": True,
            "mono": True, "printer_dpi": 203}
CUSTOM_ROLL = "Рулон – свій розмір…"
DPIS = {"203 dpi (8 точок/мм) – більшість принтерів етикеток": 203, "300 dpi (12 точок/мм)": 300}
ROLL_HINT = ("Друк на принтері етикеток: у налаштуваннях драйвера задайте розмір етикетки {w}×{h} мм і проміжок між етикетками (зазвичай 2–3 мм), "
             "у вікні друку PDF оберіть масштаб 100 % («Фактичний розмір», без «Підігнати»). Кожна сторінка PDF – одна етикетка.")


class QRLabelsDialog:
    """Створення QR-табличок для всіх ділянок схеми. scheme – словник схеми (формат .sadp); settings – збережені налаштування;
    on_settings(dict) викликається при кожній зміні (щоб налаштування потрапили у файл схеми)."""
    def __init__(self, parent, scheme, settings=None, on_settings=None, title="QR-таблички для ділянок"):
        self.scheme = scheme; self.on_settings = on_settings; self.data = None; self._job = None; self._photo = None
        st = dict(DEFAULTS); st.update({k: v for k, v in (settings or {}).items() if k in DEFAULTS}); self.settings = st
        if st["preset"] not in Q.LABEL_PRESETS:                       # власний рулонний розмір зі збереженої схеми
            wh = Q.parse_roll_key(st["preset"])
            try: st["preset"] = Q.register_roll(*wh) if wh else "M"
            except ValueError: st["preset"] = "M"
        self._custom_key = st["preset"] if Q.is_roll(st["preset"]) and Q.parse_roll_key(st["preset"]) not in [(float(a), float(b)) for a, b in Q.ROLL_SIZES] else None
        names = " × ".join(fd["name"] for fd in scheme["factor_defs"])
        if not st["exp_name"]: st["exp_name"] = ("Дослід: " + names)[:48]
        self.id_manual = bool(st["exp_id"]); self._auto_id = False
        if not st["exp_id"]: st["exp_id"] = Q.suggest_exp_id(st["exp_name"], str(_dt.date.today().year))
        self.win = tk.Toplevel(parent); self.win.title(title); self.win.geometry("1180x800"); self.win.minsize(980, 680); self.win.transient(parent)
        try:
            from sad_common import set_icon, center_win; set_icon(self.win); self._center = center_win
        except Exception: self._center = None
        self.v_name = tk.StringVar(value=st["exp_name"]); self.v_id = tk.StringVar(value=st["exp_id"]); self.v_origin = tk.StringVar(value=st["origin"])
        self.v_preset = tk.StringVar(value=Q.LABEL_PRESETS[st["preset"]]["name"]); self.v_style = tk.StringVar(value=next(k for k, v in STYLES.items() if v == st["style"]))
        self.v_ecc = tk.StringVar(value=next(k for k, v in ECCS.items() if v == st["ecc"])); self.v_nb = tk.BooleanVar(value=st["neighbors"]); self.v_cut = tk.BooleanVar(value=st["cut_lines"])
        self.v_prev = tk.StringVar(value="1"); self.v_mono = tk.BooleanVar(value=bool(st["mono"])); self.v_dpi = tk.StringVar(value=next((k for k, v in DPIS.items() if v == int(st["printer_dpi"])), list(DPIS)[0]))
        cw, ch = Q.parse_roll_key(st["preset"]) or (58.0, 40.0); self.v_rw = tk.StringVar(value=f"{cw:g}"); self.v_rh = tk.StringVar(value=f"{ch:g}")
        if self._custom_key: self.v_preset.set(CUSTOM_ROLL)
        body = tk.Frame(self.win, padx=10, pady=8); body.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(body, width=520); left.pack(side=tk.LEFT, fill=tk.Y); left.pack_propagate(False)
        right = tk.Frame(body, padx=12); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        g = tk.LabelFrame(left, text="Дослід", font=RB, padx=8, pady=6); g.pack(fill=tk.X)
        tk.Label(g, text="Назва:", font=RF).grid(row=0, column=0, sticky="w"); tk.Entry(g, textvariable=self.v_name, font=RF, width=44).grid(row=0, column=1, columnspan=2, sticky="we", pady=2)
        tk.Label(g, text="Код (3–6 символів):", font=RF).grid(row=1, column=0, sticky="w")
        self.e_id = tk.Entry(g, textvariable=self.v_id, font=("Courier New", 12, "bold"), width=8); self.e_id.grid(row=1, column=1, sticky="w", pady=2)
        tk.Button(g, text="↻ Запропонувати", font=SM, command=self._suggest).grid(row=1, column=2, sticky="w", padx=6)
        tk.Label(g, text="Код друкується на кожній табличці й у QR, тож таблички різних дослідів не сплутаються. Допустимі символи: 2–9, A–Z (без I, L, O).",
                 font=SM, fg="#666", wraplength=470, justify="left").grid(row=2, column=0, columnspan=3, sticky="w")
        tk.Label(g, text="Початок схеми:", font=RF).grid(row=3, column=0, sticky="w", pady=(4, 0)); tk.Entry(g, textvariable=self.v_origin, font=RF, width=44).grid(row=3, column=1, columnspan=2, sticky="we", pady=(4, 0))
        tk.Label(g, text="Де на місцевості ряд 1, місце 1 (наприклад, «північно-західний кут поля»): друкується в інструкції та на карті.", font=SM, fg="#666", wraplength=470, justify="left").grid(row=4, column=0, columnspan=3, sticky="w")
        t = tk.LabelFrame(left, text="Таблички й QR", font=RB, padx=8, pady=6); t.pack(fill=tk.X, pady=(8, 0))
        tk.Label(t, text="Розмір таблички:", font=RF).grid(row=0, column=0, sticky="w")
        self.cb_preset = ttk.Combobox(t, textvariable=self.v_preset, values=self._preset_names(), state="readonly", width=38); self.cb_preset.grid(row=0, column=1, sticky="w", pady=2)
        tk.Label(t, text="Вміст QR:", font=RF).grid(row=1, column=0, sticky="w"); ttk.Combobox(t, textvariable=self.v_style, values=list(STYLES), state="readonly", width=38).grid(row=1, column=1, sticky="w", pady=2)
        tk.Label(t, text="Стійкість:", font=RF).grid(row=2, column=0, sticky="w"); ttk.Combobox(t, textvariable=self.v_ecc, values=list(ECCS), state="readonly", width=38).grid(row=2, column=1, sticky="w", pady=2)
        tk.Checkbutton(t, text="Показувати сусідні ділянки (середня й велика таблички)", variable=self.v_nb, font=RF).grid(row=3, column=0, columnspan=2, sticky="w")
        self.cb_cut = tk.Checkbutton(t, text="Лінії різання навколо табличок (для звичайного паперу)", variable=self.v_cut, font=RF); self.cb_cut.grid(row=4, column=0, columnspan=2, sticky="w")
        self.roll = tk.Frame(t); self.roll.grid(row=5, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.roll_custom = tk.Frame(self.roll); self.roll_custom.pack(fill=tk.X)
        tk.Label(self.roll_custom, text="Етикетка, мм: ширина", font=RF).pack(side=tk.LEFT); tk.Entry(self.roll_custom, textvariable=self.v_rw, width=6, font=RF).pack(side=tk.LEFT, padx=3)
        tk.Label(self.roll_custom, text="× висота", font=RF).pack(side=tk.LEFT); tk.Entry(self.roll_custom, textvariable=self.v_rh, width=6, font=RF).pack(side=tk.LEFT, padx=3)
        tk.Button(self.roll_custom, text="Застосувати", font=SM, command=self._apply_custom).pack(side=tk.LEFT, padx=6)
        r2 = tk.Frame(self.roll); r2.pack(fill=tk.X, pady=2); tk.Label(r2, text="Принтер:", font=RF).pack(side=tk.LEFT)
        ttk.Combobox(r2, textvariable=self.v_dpi, values=list(DPIS), state="readonly", width=46).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(self.roll, text="Чорно-білий друк (для термопринтера: без кольорових і сірих заливок)", variable=self.v_mono, font=RF).pack(anchor="w")
        self.roll_hint = tk.Label(self.roll, text="", font=SM, fg="#1a4b8c", wraplength=480, justify="left"); self.roll_hint.pack(anchor="w", pady=(2, 0))
        a = tk.LabelFrame(left, text="Зберегти і друкувати", font=RB, padx=8, pady=6); a.pack(fill=tk.X, pady=(8, 0))
        self.buttons = []
        for r, (txt, cmd, bg) in enumerate((("📄 Таблички: PDF…", self.save_labels_pdf, None), ("🗺 Розкладка: PDF (інструкція, карта, чек-лист)…", self.save_layout_pdf, None),
                                             ("🖼 PNG кожної таблички…", self.save_png, None), ("📊 Список ділянок: Excel…", self.save_xlsx, None),
                                             ("💾 Маніфест для польового журналу: JSON…", self.save_manifest, None), ("📦 Зберегти все в теку…", self.save_everything, "#1a6b1a"),
                                             ("🖨 Друкувати таблички", lambda: self.print_pdf("labels"), "#1a4b8c"), ("🖨 Друкувати розкладку", lambda: self.print_pdf("layout"), "#1a4b8c"))):
            b = tk.Button(a, text=txt, font=RF, anchor="w", command=cmd, **({"bg": bg, "fg": "white"} if bg else {}))
            if r < 6: b.grid(row=r, column=0, columnspan=2, sticky="we", pady=1)                      # кожна дія – у власному рядку
            else: b.grid(row=6, column=r - 6, sticky="we", pady=(6, 1), padx=(0, 4) if r == 6 else (4, 0))
            self.buttons.append(b)
        a.columnconfigure(0, weight=1); a.columnconfigure(1, weight=1)
        tk.Button(left, text="Закрити", font=RF, command=self.win.destroy).pack(side=tk.BOTTOM, anchor="e", pady=(8, 0))
        pv = tk.LabelFrame(right, text="Попередній перегляд (реальний розмір, масштаб екрана)", font=RB, padx=8, pady=6); pv.pack(fill=tk.X)
        pr = tk.Frame(pv); pr.pack(fill=tk.X)
        tk.Label(pr, text="Ділянка №", font=RF).pack(side=tk.LEFT); self.sp = tk.Spinbox(pr, from_=1, to=max(1, len(scheme.get("plants", [])) or 1), textvariable=self.v_prev, width=6, font=RF, command=self._schedule); self.sp.pack(side=tk.LEFT, padx=4)
        self.lbl_img = tk.Label(pv, bg="#e6e6e6", relief=tk.SUNKEN); self.lbl_img.pack(pady=6, fill=tk.X)
        self.info = tk.Label(right, text="", font=RF, justify="left", anchor="w", wraplength=520); self.info.pack(fill=tk.X, pady=(6, 0))
        self.warn = tk.Label(right, text="", font=SM, fg="#8c5a1a", justify="left", anchor="w", wraplength=520); self.warn.pack(fill=tk.X, pady=(4, 0))
        self.err = tk.Label(right, text="", font=RB, fg="#c62828", justify="left", anchor="w", wraplength=520); self.err.pack(fill=tk.X)
        tk.Label(right, text="Розміщення без помилок: наскрізний номер, код досліду з контрольним символом, підпис схеми, колір варіанта, сусіди, карта й чек-лист (див. PDF розкладки). "
                             "Формат QR описано у файлі QR_FORMAT.md – за ним польовий журнал впізнає ділянку.", font=SM, fg="#555", wraplength=520, justify="left").pack(fill=tk.X, pady=(10, 0))
        for v in (self.v_name, self.v_origin, self.v_preset, self.v_style, self.v_ecc, self.v_nb, self.v_cut, self.v_prev, self.v_mono, self.v_dpi): v.trace_add("write", self._on_change)
        self.v_preset.trace_add("write", lambda *_: self._sync_roll())
        self.v_name.trace_add("write", self._name_changed); self.v_id.trace_add("write", self._id_changed); self.v_id.trace_add("write", self._on_change)
        self._sync_roll(); self._rebuild(); self._push()
        if self._center:
            try: self._center(self.win)
            except Exception: pass

    # ── стан ──
    @property
    def key(self):
        if self.v_preset.get() == CUSTOM_ROLL: return self._custom_key or Q.register_roll(58, 40)
        return next(k for k, v in Q.LABEL_PRESETS.items() if v["name"] == self.v_preset.get())
    @property
    def style(self): return STYLES[self.v_style.get()]
    @property
    def ecc(self): return ECCS[self.v_ecc.get()]
    def opts(self):
        roll = Q.is_roll(self.key)
        return {"style": self.style, "ecc": self.ecc, "neighbors": self.v_nb.get(), "cut_lines": self.v_cut.get() and not roll, "mono": bool(self.v_mono.get()) and roll,
                "printer_dpi": DPIS[self.v_dpi.get()]}

    @property
    def is_roll(self): return Q.is_roll(self.key)

    def _preset_names(self):
        fixed = [v["name"] for k, v in Q.LABEL_PRESETS.items() if not Q.is_roll(k) or Q.parse_roll_key(k) in [(float(a), float(b)) for a, b in Q.ROLL_SIZES]]
        return fixed + [CUSTOM_ROLL]

    def _apply_custom(self):
        try: w, h = float(self.v_rw.get().replace(",", ".")), float(self.v_rh.get().replace(",", "."))
        except ValueError: messagebox.showwarning("Розмір етикетки", "Ширина й висота мають бути числами (мм).", parent=self.win); return False
        try: self._custom_key = Q.register_roll(w, h)
        except ValueError as e: messagebox.showwarning("Розмір етикетки", str(e), parent=self.win); return False
        if self.v_preset.get() != CUSTOM_ROLL: self.v_preset.set(CUSTOM_ROLL)
        self._sync_roll(); self._schedule(); return True

    def _sync_roll(self):
        """Показує рулонні параметри лише для рулонних розмірів; підказка – з розміром етикетки."""
        custom = self.v_preset.get() == CUSTOM_ROLL
        if custom and self._custom_key is None:
            try: self._custom_key = Q.register_roll(float(self.v_rw.get().replace(",", ".")), float(self.v_rh.get().replace(",", ".")))
            except ValueError: self._custom_key = Q.register_roll(58, 40)
        roll = custom or Q.is_roll(next((k for k, v in Q.LABEL_PRESETS.items() if v["name"] == self.v_preset.get()), "M"))
        if roll:
            self.roll.grid(); self.cb_cut.grid_remove()
            (self.roll_custom.pack(fill=tk.X, before=self.roll.winfo_children()[1]) if custom else self.roll_custom.pack_forget())
            P = Q.LABEL_PRESETS[self.key]; hint = ROLL_HINT.format(w=Q._num(P["w"]), h=Q._num(P["h"]))
            if P["w"] > Q.PRINTER_PRINT_W: hint += f" Увага: ширина {Q._num(P['w'])} мм більша за ширину друку 4-дюймових принтерів ({Q._num(Q.PRINTER_PRINT_W)} мм) – краї не надрукуються."
            if P["w"] < 45: hint += " Етикетка мала: розбірливими лишаться QR, номер, повторність і варіант; дрібний текст – на межі можливостей 203 dpi."
            self.roll_hint.configure(text=hint)
        else:
            self.roll.grid_remove(); self.cb_cut.grid()

    def _push(self):
        self.settings.update(exp_name=self.v_name.get().strip(), exp_id=self.v_id.get().strip().upper(), origin=self.v_origin.get().strip(), preset=self.key, style=self.style, ecc=self.ecc,
                             neighbors=bool(self.v_nb.get()), cut_lines=bool(self.v_cut.get()), mono=bool(self.v_mono.get()), printer_dpi=DPIS[self.v_dpi.get()])
        if self.on_settings: self.on_settings(dict(self.settings))

    def _set_auto_id(self):
        self._auto_id = True
        try: self.v_id.set(Q.suggest_exp_id(self.v_name.get(), str(_dt.date.today().year)))
        finally: self._auto_id = False
    def _name_changed(self, *_):
        if not self.id_manual: self._set_auto_id()
    def _id_changed(self, *_):
        if self._auto_id: return
        self.id_manual = True                                  # будь-яка зміна коду не програмою (набір, вставка мишею) – ручна
        v = self.v_id.get()
        if v != v.upper(): self._auto_id = True; self.v_id.set(v.upper()); self._auto_id = False        # код завжди великими літерами
    def _suggest(self):
        self.id_manual = False; self._set_auto_id()
    def _on_change(self, *_): self._schedule()
    def _schedule(self):
        if self._job is not None:
            try: self.win.after_cancel(self._job)
            except Exception: pass
        self._job = self.win.after(250, self._rebuild_job)
    def _rebuild_job(self): self._job = None; self._rebuild(); self._push()

    def _rebuild(self):
        eid = self.v_id.get().strip().upper()
        ok_id = Q.valid_exp_id(eid)
        for b in self.buttons: b.configure(state=tk.NORMAL if ok_id else tk.DISABLED)
        if not ok_id:
            self.err.configure(text="Код досліду має містити 3–6 символів із набору 2–9, A–Z (без I, L, O)."); self.data = None; return
        try:
            self.data = Q.build_experiment(self.scheme, eid, self.v_name.get(), self.v_origin.get())
        except ValueError as e:
            self.err.configure(text=str(e)); self.data = None
            for b in self.buttons: b.configure(state=tk.DISABLED)
            return
        self.err.configure(text="")
        self.win.configure(cursor="watch" if len(self.data["plots"]) > 300 else "")
        Q.fill_payloads(self.data, self.style, self.ecc, self.key); sm = Q.summary(self.data, self.key, self.ecc, self.style); self.win.configure(cursor="")
        e = self.data["exp"]
        self.info.configure(text=f"Ділянок: {e['n_plots']} · варіантів: {e['n_variants']} · повторностей: {e['n_reps']} · підпис схеми: {e['signature']}\n"
                                 f"QR: версія {sm['version']}, модуль {sm['module']:.2f} мм · сканується з відстані до ≈ {sm['scan_cm']:.0f} см (камера 1080p)\n"
                                 f"Аркушів A4: {sm['sheets']} ({sm['per_sheet']} табличок на аркуші)")
        self.warn.configure(text="\n".join("• " + w for w in sm["warnings"]))
        self.sp.configure(to=len(self.data["plots"]))
        self._preview()

    def _preview(self):
        if not self.data: return
        try: n = min(max(1, int(self.v_prev.get())), len(self.data["plots"]))
        except ValueError: n = 1
        try:
            from PIL import ImageTk
            img = Q.render_label_png(self.data, self.data["plots"][n - 1], self.key, self.opts(), dpi=96)
            self._photo = ImageTk.PhotoImage(img); self.lbl_img.configure(image=self._photo)
        except Exception as ex:
            self.lbl_img.configure(image="", text=f"(перегляд недоступний: {ex})")

    # ── дії ──
    def _need(self):
        if not self.data: messagebox.showwarning("QR-таблички", "Спочатку виправте код досліду.", parent=self.win); return False
        return True
    def _stem(self): return self.data["exp"]["id"]
    def _done(self, what, path): messagebox.showinfo("Збережено", f"{what}:\n{path}", parent=self.win)

    def save_labels_pdf(self):
        if not self._need(): return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".pdf", initialfile=f"{self._stem()}_таблички.pdf", filetypes=[("PDF", "*.pdf")], title="Зберегти таблички")
        if p: n = Q.render_labels_pdf(p, self.data, self.key, self.opts()); self._done(f"PDF етикеток для принтера етикеток ({n} шт., по одній на сторінці)" if self.is_roll else f"PDF табличок ({n} арк.)", p)
    def save_layout_pdf(self):
        if not self._need(): return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".pdf", initialfile=f"{self._stem()}_розкладка.pdf", filetypes=[("PDF", "*.pdf")], title="Зберегти розкладку")
        if p: n = Q.render_layout_pdf(p, self.data, self.key, self.opts()); self._done(f"PDF розкладки ({n} стор.)", p)
    def save_png(self):
        if not self._need(): return
        d = filedialog.askdirectory(parent=self.win, title="Тека для PNG табличок")
        if d:
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try: files = Q.save_png_labels(os.path.join(d, f"{self._stem()}_png"), self.data, self.key, self.opts(), self.opts()["printer_dpi"] if self.is_roll else 300)
            finally: self.win.configure(cursor="")
            self._done(f"PNG табличок: {len(files)} файлів у теці", os.path.join(d, f"{self._stem()}_png"))
    def save_xlsx(self):
        if not self._need(): return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".xlsx", initialfile=f"{self._stem()}_розкладка.xlsx", filetypes=[("Excel", "*.xlsx")], title="Зберегти список ділянок")
        if p: Q.export_xlsx(p, self.data); self._done("Список ділянок", p)
    def save_manifest(self):
        if not self._need(): return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".json", initialfile=f"{self._stem()}_manifest.json", filetypes=[("JSON", "*.json")], title="Зберегти маніфест")
        if p: Q.export_manifest(p, self.data, self.style, self.ecc); self._done("Маніфест для польового журналу", p)
    def save_everything(self):
        if not self._need(): return
        d = filedialog.askdirectory(parent=self.win, title="Тека для комплекту QR-табличок")
        if d:
            folder = os.path.join(d, f"{self._stem()}_QR"); self.win.configure(cursor="watch"); self.win.update_idletasks()
            try: files = Q.save_all(folder, self.data, self.key, self.opts(), self.opts()["printer_dpi"] if self.is_roll else 300)
            finally: self.win.configure(cursor="")
            self._done(f"Комплект ({len(files)} файлів: PDF табличок, PDF розкладки, Excel, маніфест, PNG) у теці", folder)
    def print_pdf(self, what):
        if not self._need(): return
        folder = os.path.join(tempfile.gettempdir(), "SAD_QR"); os.makedirs(folder, exist_ok=True)
        try:
            if what == "labels": p = os.path.join(folder, f"{self._stem()}_таблички.pdf"); Q.render_labels_pdf(p, self.data, self.key, self.opts())
            else: p = os.path.join(folder, f"{self._stem()}_розкладка.pdf"); Q.render_layout_pdf(p, self.data, self.key, self.opts())
            Q.open_for_print(p)
        except Exception as ex:
            messagebox.showerror("Друк", f"Не вдалося відкрити файл для друку: {ex}", parent=self.win)
