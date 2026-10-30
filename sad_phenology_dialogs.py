# sad_phenology_dialogs.py – S.A.D. v2.1: діалоги фенології (погода, облік за візитами)
# -*- coding: utf-8 -*-
import datetime as _dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import numpy as np
from sad_common import set_icon
import sad_phenology as P

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)


# ═══════════════════════════════════════════════════════════════
# Погода: розбір таблиці й діалог
# ═══════════════════════════════════════════════════════════════
def series_from_rows(headers, rows, origin="файл"):
    """Добові температури з таблиці: стовпці визначаються за назвами (дата; tсер або tmax+tmin). → DailySeries."""
    import sad_weather_core as W
    m = W.guess_columns(headers)
    if "date" not in m: raise ValueError("Не знайдено стовпець із датою (назва має містити «дата» або «date»).")
    if "tmean" not in m and not ("tmax" in m and "tmin" in m): raise ValueError("Не знайдено стовпець температури: потрібна середня добова (tсер, tmean) або пара tmax + tmin.")
    mapping = {k: v for k, v in m.items() if k in ("date", "tmean", "tmax", "tmin", "prec")}
    ser = W.series_from_table(headers, rows, mapping, extra_meta={"source": origin})
    if len(ser) < 10: raise ValueError(f"Розпізнано лише {len(ser)} діб із коректною датою – замало.")
    return ser


def series_from_text(text):
    import sad_weather_core as W
    h, rows = W.read_table_text(text); return series_from_rows(h, rows, "буфер")


class WeatherDialog:
    """Підключення погоди й вибір суми температур: тип (САТ/СЕТ), поріг, початок підрахунку."""
    def __init__(self, parent, owner):
        self.o = owner; self.win = tk.Toplevel(parent); self.win.title("Погода для сум температур"); self.win.transient(parent); set_icon(self.win); self.win.grab_set()
        f = tk.Frame(self.win, padx=14, pady=10); f.pack(fill=tk.BOTH, expand=True)
        tk.Label(f, text="1. Добова температура", font=RB).grid(row=0, column=0, columnspan=3, sticky="w")
        self.info = tk.Label(f, text=owner.weather_note or "Погода не підключена.", font=RF, fg="#1a4b8c", anchor="w", wraplength=520, justify="left"); self.info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 4))
        self.b_win = tk.Button(f, text="З вікна «Погода»", font=RF, command=self.from_weather_window); self.b_win.grid(row=2, column=0, sticky="we", padx=(0, 4))
        tk.Button(f, text="З файлу Excel / CSV…", font=RF, command=self.from_file).grid(row=2, column=1, sticky="we", padx=4)
        tk.Button(f, text="Вставити з буфера", font=RF, command=self.from_clipboard).grid(row=2, column=2, sticky="we", padx=(4, 0))
        tk.Label(f, text="Стовпці: дата та середня добова температура (або tmax і tmin). Дані можна отримати у модулі «Погода» (NASA POWER).", font=SM, fg="#666", wraplength=520, justify="left").grid(row=3, column=0, columnspan=3, sticky="w", pady=(2, 8))
        tk.Label(f, text="2. Яку суму рахувати", font=RB).grid(row=4, column=0, columnspan=3, sticky="w")
        cfg = owner.sum_cfg; self.kind = tk.StringVar(value="Активних температур (САТ: Σ t при t > порогу)" if cfg["kind"] == "sat" else "Ефективних температур (СЕТ: Σ (t − поріг) при t > порогу)")
        ttk.Combobox(f, textvariable=self.kind, state="readonly", width=58, values=["Активних температур (САТ: Σ t при t > порогу)", "Ефективних температур (СЕТ: Σ (t − поріг) при t > порогу)"]).grid(row=5, column=0, columnspan=3, sticky="w", pady=2)
        r6 = tk.Frame(f); r6.grid(row=6, column=0, columnspan=3, sticky="w", pady=2); tk.Label(r6, text="Поріг, °C:", font=RF).pack(side=tk.LEFT); self.base = tk.StringVar(value=str(cfg["base"]).rstrip("0").rstrip("."))
        tk.Entry(r6, textvariable=self.base, width=6, font=RF).pack(side=tk.LEFT, padx=4); tk.Label(r6, text="(5 – для більшості культур помірного поясу, 10 – для теплолюбних)", font=SM, fg="#666").pack(side=tk.LEFT)
        tk.Label(f, text="3. З якого моменту рахувати", font=RB).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.start_mode = tk.StringVar(value="md" if cfg["start"][0] == "md" else "phase")
        r8 = tk.Frame(f); r8.grid(row=8, column=0, columnspan=3, sticky="w"); tk.Radiobutton(r8, text="щороку з", variable=self.start_mode, value="md", font=RF).pack(side=tk.LEFT)
        self.sd = tk.StringVar(value=str(cfg["start"][2] if cfg["start"][0] == "md" else 1)); self.sm = tk.StringVar(value=str(cfg["start"][1] if cfg["start"][0] == "md" else 3))
        tk.Entry(r8, textvariable=self.sd, width=3, font=RF).pack(side=tk.LEFT); tk.Label(r8, text=".", font=RF).pack(side=tk.LEFT); tk.Entry(r8, textvariable=self.sm, width=3, font=RF).pack(side=tk.LEFT); tk.Label(r8, text="(день.місяць)", font=SM, fg="#666").pack(side=tk.LEFT, padx=4)
        r9 = tk.Frame(f); r9.grid(row=9, column=0, columnspan=3, sticky="w", pady=2); tk.Radiobutton(r9, text="від дати фази:", variable=self.start_mode, value="phase", font=RF).pack(side=tk.LEFT)
        self.phase_labels = {P.phase_label(p): p["key"] for p in owner.phases}; self.phase_var = tk.StringVar()
        cur = cfg["start"][1] if cfg["start"][0] == "phase" else (owner.phases[0]["key"] if owner.phases else "")
        self.phase_var.set(next((l for l, k in self.phase_labels.items() if k == cur), "")); ttk.Combobox(r9, textvariable=self.phase_var, values=list(self.phase_labels), state="readonly", width=40).pack(side=tk.LEFT, padx=4)
        bt = tk.Frame(f); bt.grid(row=10, column=0, columnspan=3, sticky="we", pady=(12, 0))
        tk.Button(bt, text="Застосувати", font=RB, bg="#1a6b1a", fg="white", width=14, command=self.apply).pack(side=tk.RIGHT, padx=4)
        tk.Button(bt, text="Прибрати погоду", font=RF, command=self.clear).pack(side=tk.LEFT); tk.Button(bt, text="Закрити", font=RF, command=self.win.destroy).pack(side=tk.RIGHT)
        self._refresh()

    def _refresh(self):
        try:
            import sad_weather as SW
            ok = SW.SHARED.get("series") is not None
        except Exception: ok = False
        self.b_win.configure(state=tk.NORMAL if ok else tk.DISABLED)

    def _set(self, ser, note):
        self.o.series = ser; self.o.weather_note = f"{note}: {len(ser)} діб, {ser.dates[0]:%d.%m.%Y} – {ser.dates[-1]:%d.%m.%Y}"; self.info.configure(text=self.o.weather_note)

    def from_weather_window(self):
        import sad_weather as SW
        s = SW.SHARED.get("series")
        if s is None: messagebox.showinfo("", "У вікні «Погода» ще немає даних. Спершу отримайте або завантажте їх там.", parent=self.win); return
        if not s.has("tmean"): messagebox.showwarning("", "У даних вікна «Погода» немає середньої добової температури.", parent=self.win); return
        self._set(s, "З вікна «Погода»" + (f" ({SW.SHARED.get('place')})" if SW.SHARED.get("place") else ""))

    def from_file(self, path=None):
        path = path or filedialog.askopenfilename(parent=self.win, title="Добові температури", filetypes=[("Excel / CSV", "*.xlsx *.xlsm *.csv *.txt")])
        if not path: return
        try: rows = self.o._read_table_file(path); self._set(series_from_rows(rows[0], rows[1:], "файл"), "З файлу")
        except Exception as e: messagebox.showerror("Погода", str(e), parent=self.win)

    def from_clipboard(self):
        try: self._set(series_from_text(self.win.clipboard_get()), "З буфера")
        except Exception as e: messagebox.showerror("Погода", str(e), parent=self.win)

    def clear(self):
        self.o.series = None; self.o.weather_note = ""; self.info.configure(text="Погода не підключена.")

    def apply(self):
        try: base = float(self.base.get().replace(",", "."))
        except ValueError: messagebox.showwarning("", "Поріг температури має бути числом.", parent=self.win); return
        if self.start_mode.get() == "md":
            try: d, m = int(self.sd.get()), int(self.sm.get()); _dt.date(2001, m, d)
            except ValueError: messagebox.showwarning("", "Початок підрахунку: вкажіть існуючу дату (день.місяць).", parent=self.win); return
            start = ["md", m, d]
        else:
            if not self.phase_var.get(): messagebox.showwarning("", "Оберіть фазу, від якої рахувати.", parent=self.win); return
            start = ["phase", self.phase_labels[self.phase_var.get()]]
        if self.o.series is None: messagebox.showwarning("", "Спершу підключіть добову температуру (крок 1).", parent=self.win); return
        self.o.sum_cfg = {"kind": "sat" if self.kind.get().startswith("Активних") else "set", "base": base, "start": start}; self.win.destroy()


# ═══════════════════════════════════════════════════════════════
# Облік за візитами
# ═══════════════════════════════════════════════════════════════
class VisitsDialog:
    """Візити: відсоток рослин у фазі → дата настання за порогом (лінійна інтерполяція) → у таблицю."""
    def __init__(self, parent, owner):
        self.o = owner; owner._save_current(); self.model = owner.years_data.setdefault(owner.cur_year, []); self.rows = [(i, r) for i, r in enumerate(self.model) if r["name"].strip()]
        self.dates = []; self.cells = []; self.results = []
        self.win = tk.Toplevel(parent); self.win.title("Облік за візитами"); self.win.geometry("980x560"); self.win.transient(parent); set_icon(self.win)
        tk.Label(self.win, text="Для кожного візиту вкажіть, який відсоток рослин (пагонів, бруньок, суцвіть) був у фазі. Програма знайде дату, коли досягнуто поріг, і запише її в таблицю.", font=SM, fg="#555", wraplength=940, justify="left").pack(anchor="w", padx=10, pady=(8, 2))
        top = tk.Frame(self.win); top.pack(fill=tk.X, padx=10); tk.Button(top, text="＋ Візит (дата)…", font=RF, command=self.add_visit).pack(side=tk.LEFT); tk.Button(top, text="✖ Прибрати останній візит", font=RF, command=self.del_visit).pack(side=tk.LEFT, padx=6)
        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True, padx=10, pady=6); self.cv = tk.Canvas(body, highlightthickness=0, height=240)
        hs = ttk.Scrollbar(body, orient="horizontal", command=self.cv.xview); vs = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview); self.cv.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        vs.pack(side=tk.RIGHT, fill=tk.Y); hs.pack(side=tk.BOTTOM, fill=tk.X); self.cv.pack(fill=tk.BOTH, expand=True); self.gf = tk.Frame(self.cv); self.cv.create_window((0, 0), window=self.gf, anchor="nw")
        self.gf.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        tg = tk.LabelFrame(self.win, text=" Записати в таблицю ", font=RB, padx=8, pady=6); tg.pack(fill=tk.X, padx=10, pady=4)
        self.phase_labels = {P.phase_label(p): p["key"] for p in owner.phases}; names = list(self.phase_labels); self.targets = []
        defaults = [("bloom0", 10), ("bloom50", 50), ("bloom1", 90)]; keys = {p["key"]: P.phase_label(p) for p in owner.phases}
        for i in range(3):
            fr = tk.Frame(tg); fr.pack(fill=tk.X, pady=1); tk.Label(fr, text=f"Фаза {i + 1}:", font=RF, width=8, anchor="w").pack(side=tk.LEFT)
            pv = tk.StringVar(value=keys.get(defaults[i][0], "") if i < len(defaults) else ""); ttk.Combobox(fr, textvariable=pv, values=[""] + names, state="readonly", width=46).pack(side=tk.LEFT, padx=4)
            tk.Label(fr, text="при ≥", font=RF).pack(side=tk.LEFT); tv = tk.StringVar(value=str(defaults[i][1]) if i < len(defaults) else "50"); tk.Entry(fr, textvariable=tv, width=5, font=RF).pack(side=tk.LEFT, padx=3); tk.Label(fr, text="% рослин у фазі", font=RF).pack(side=tk.LEFT)
            self.targets.append((pv, tv))
        bt = tk.Frame(self.win); bt.pack(fill=tk.X, padx=10, pady=(2, 8)); self.msg = tk.Label(bt, text="", font=SM, fg="#555", anchor="w", justify="left", wraplength=700); self.msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(bt, text="Обчислити й записати", font=RB, bg="#1a6b1a", fg="white", command=self.apply).pack(side=tk.RIGHT, padx=4); tk.Button(bt, text="Закрити", font=RF, command=self.win.destroy).pack(side=tk.RIGHT)
        self._draw()
        if not self.rows: self.msg.configure(text="У таблиці ще немає сортів: введіть їх у першому стовпці й відкрийте діалог знову.", fg="#c62828")

    def _draw(self, keep=None):
        keep = keep if keep is not None else [[e.get() for e in row] for row in self.cells]
        for w in self.gf.winfo_children(): w.destroy()
        self.cells = []; tk.Label(self.gf, text="Сорт", font=RB, bg="#1a4b8c", fg="white", width=24).grid(row=0, column=0, padx=1); tk.Label(self.gf, text="Повт.", font=RB, bg="#1a4b8c", fg="white", width=5).grid(row=0, column=1, padx=1)
        for j, d in enumerate(self.dates): tk.Label(self.gf, text=d.strftime("%d.%m"), font=RB, bg="#1a4b8c", fg="white", width=8).grid(row=0, column=2 + j, padx=1)
        for i, (gi, r) in enumerate(self.rows):
            tk.Label(self.gf, text=r["name"], font=RF, anchor="w", width=24).grid(row=i + 1, column=0); tk.Label(self.gf, text=r["rep"], font=RF, width=5).grid(row=i + 1, column=1); row = []
            for j in range(len(self.dates)):
                e = tk.Entry(self.gf, font=RF, width=8, justify="center"); e.grid(row=i + 1, column=2 + j, padx=1, pady=1)
                if i < len(keep) and j < len(keep[i]): e.insert(0, keep[i][j])
                row.append(e)
            self.cells.append(row)

    def add_visit(self, date=None):
        if date is None:
            txt = simpledialog.askstring("Візит", "Дата візиту (наприклад, 05.05):", parent=self.win)
            if not txt: return
            date, msg = P.parse_date_flex(txt, self.o.cur_year)
            if date is None: messagebox.showwarning("", msg or "Не схоже на дату.", parent=self.win); return
        if date in self.dates: messagebox.showinfo("", "Такий візит уже є.", parent=self.win); return
        keep = [[e.get() for e in row] for row in self.cells]; pos = sum(1 for d in self.dates if d < date)
        self.dates.insert(pos, date)
        keep = [r[:pos] + [""] + r[pos:] for r in keep]; self._draw(keep)

    def del_visit(self):
        if self.dates: keep = [[e.get() for e in row][:-1] for row in self.cells]; self.dates.pop(); self._draw(keep)

    def compute(self):
        """→ список {row, name, rep, phase, date, kind, thr}. Дати з візитів і порогів, без запису в таблицю."""
        out = []; tg = [(self.phase_labels[pv.get()], tv.get()) for pv, tv in self.targets if pv.get()]
        thrs = []
        for k, t in tg:
            try: thrs.append((k, float(t.replace(",", "."))))
            except ValueError: raise ValueError(f"Поріг «{t}» має бути числом від 0 до 100.")
        for (gi, r), cells in zip(self.rows, self.cells):
            vis = []
            for d, e in zip(self.dates, cells):
                t = e.get().strip().replace(",", ".").replace("%", "")
                if t:
                    try: vis.append((d, float(t)))
                    except ValueError: raise ValueError(f"«{e.get()}» у рядку «{r['name']}» (візит {d:%d.%m}) – не число.")
            for k, thr in thrs:
                d, kind = P.onset_from_visits(vis, thr); out.append({"row": gi, "name": r["name"], "rep": r["rep"], "phase": k, "date": d, "kind": kind, "thr": thr})
        return out

    def apply(self):
        if not self.dates: messagebox.showinfo("", "Додайте хоча б один візит.", parent=self.win); return
        if not any(pv.get() for pv, _ in self.targets): messagebox.showinfo("", "Оберіть хоча б одну фазу для запису.", parent=self.win); return
        try: res = self.compute()
        except ValueError as e: messagebox.showwarning("", str(e), parent=self.win); return
        n = first = none = 0
        for r in res:
            if r["date"] is None: none += 1; continue
            self.model[r["row"]].setdefault("dates", {})[r["phase"]] = P.fmt_date(r["date"]); n += 1; first += r["kind"] == "first"
        self.o._write_grid(self.model)
        self.o._validate_all(); self.results = res
        self.msg.configure(text=f"Записано дат: {n}" + (f"; поріг уже досягнуто на першому візиті (дата не пізніша за нього): {first}" if first else "") + (f"; поріг не досягнуто: {none}" if none else "") + ".", fg="#1a6b1a" if n else "#8c5a1a")


# ═══════════════════════════════════════════════════════════════
# Групи стиглості й стандарти груп
# ═══════════════════════════════════════════════════════════════
DEFAULT_GROUPS = ["ранні", "середні", "пізні"]


class GroupsDialog:
    """Призначення сортам груп стиглості та вибір стандарту для кожної групи. Сорти без групи порівнюються із загальним стандартом.
    Результат записується в owner.groups ({сорт: група}) і owner.group_std ({група: сорт-стандарт})."""
    def __init__(self, parent, owner):
        self.o = owner; owner._save_current()
        self.cultivars = P.cultivar_order([{"name": r["name"]} for y in sorted(owner.years_data) for r in owner.years_data[y] if r["name"].strip()])
        self.groups = {c: g for c, g in (owner.groups or {}).items() if c in self.cultivars and g}
        self.group_std = {g: s for g, s in (owner.group_std or {}).items() if s in self.cultivars}
        self.win = tk.Toplevel(parent); self.win.title("Групи стиглості й стандарти"); self.win.geometry("900x600"); self.win.transient(parent); set_icon(self.win)
        tk.Label(self.win, text="Якщо в досліді сорти різних груп стиглості (наприклад, літні, осінні й зимові сорти яблуні), призначте кожному групу й виберіть "
                 "стандарт групи: тоді кожен сорт порівнюється зі стандартом своєї групи (різниця в днях, класи, тест Даннетта). Сорти без групи "
                 "порівнюються із загальним стандартом.", font=SM, fg="#555", wraplength=860, justify="left").pack(anchor="w", padx=10, pady=(8, 4))
        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True, padx=10)
        left = tk.Frame(body); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tv = ttk.Treeview(left, columns=("c", "g"), show="headings", selectmode="extended"); self.tv.heading("c", text="Сорт"); self.tv.heading("g", text="Група")
        self.tv.column("c", width=260); self.tv.column("g", width=140); sb = ttk.Scrollbar(left, command=self.tv.yview); self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.LEFT, fill=tk.Y)
        right = tk.Frame(body, padx=10); right.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(right, text="Група для виділених сортів:", font=RB).pack(anchor="w")
        self.gv = tk.StringVar(value=DEFAULT_GROUPS[0]); self.gcb = ttk.Combobox(right, textvariable=self.gv, values=self._group_names(), width=24); self.gcb.pack(anchor="w", pady=2)
        tk.Label(right, text="(можна вписати свою назву групи)", font=SM, fg="#666").pack(anchor="w")
        tk.Button(right, text="Призначити групу", font=RF, command=self.assign).pack(fill=tk.X, pady=(4, 2))
        tk.Button(right, text="Прибрати групу", font=RF, command=self.clear_sel).pack(fill=tk.X, pady=2)
        tk.Button(right, text="Вставити з буфера (сорт → група)", font=RF, command=self.paste).pack(fill=tk.X, pady=2)
        tk.Label(right, text="Стандарт кожної групи:", font=RB).pack(anchor="w", pady=(12, 2))
        self.std_box = tk.Frame(right); self.std_box.pack(fill=tk.X)
        self.msg = tk.Label(self.win, text="", font=SM, fg="#8c5a1a", anchor="w", justify="left", wraplength=860); self.msg.pack(fill=tk.X, padx=10)
        bt = tk.Frame(self.win); bt.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(bt, text="OK", font=RB, bg="#1a6b1a", fg="white", width=12, command=self.ok).pack(side=tk.RIGHT, padx=4)
        tk.Button(bt, text="Скасувати", font=RF, width=12, command=self.win.destroy).pack(side=tk.RIGHT)
        tk.Button(bt, text="Прибрати всі групи", font=RF, command=self.clear_all).pack(side=tk.LEFT)
        self._fill(); self._stds()
        if not self.cultivars: self.msg.configure(text="У таблиці ще немає сортів: спершу введіть їх.", fg="#c62828")

    def _group_names(self):
        seen = list(DEFAULT_GROUPS)
        for g in self.groups.values():
            if g not in seen: seen.append(g)
        return seen

    def _fill(self):
        sel = [self.tv.item(i, "values")[0] for i in self.tv.selection()]
        self.tv.delete(*self.tv.get_children())
        for c in self.cultivars:
            iid = self.tv.insert("", tk.END, values=(c, self.groups.get(c, "")))
            if c in sel: self.tv.selection_add(iid)
        self.gcb.configure(values=self._group_names())

    def _stds(self):
        for w in self.std_box.winfo_children(): w.destroy()
        used = [g for g in self._group_names() if g in set(self.groups.values())]; self.std_vars = {}
        for g in list(self.group_std):
            if g not in used: del self.group_std[g]
        if not used: tk.Label(self.std_box, text="Груп ще немає.", font=SM, fg="#666").pack(anchor="w"); return
        for g in used:
            fr = tk.Frame(self.std_box); fr.pack(fill=tk.X, pady=1); tk.Label(fr, text=f"{g}:", font=RF, width=12, anchor="w").pack(side=tk.LEFT)
            members = [c for c in self.cultivars if self.groups.get(c) == g]; v = tk.StringVar(value=self.group_std.get(g, ""))
            cb = ttk.Combobox(fr, textvariable=v, values=members, state="readonly", width=24); cb.pack(side=tk.LEFT)
            cb.bind("<<ComboboxSelected>>", lambda e, g=g, v=v: self.group_std.__setitem__(g, v.get())); self.std_vars[g] = v

    def _selected(self): return [self.tv.item(i, "values")[0] for i in self.tv.selection()]

    def assign(self, group=None, names=None):
        g = (group if group is not None else self.gv.get()).strip(); names = names if names is not None else self._selected()
        if not names: self.msg.configure(text="Виділіть сорти в списку (Ctrl або Shift – кілька).", fg="#8c5a1a"); return
        if not g: self.msg.configure(text="Вкажіть назву групи.", fg="#8c5a1a"); return
        for c in names: self.groups[c] = g
        self._fill(); self._stds(); self.msg.configure(text=f"Групу «{g}» призначено сортам: {len(names)}.", fg="#1a6b1a")

    def clear_sel(self):
        for c in self._selected(): self.groups.pop(c, None)
        self._fill(); self._stds()

    def clear_all(self):
        self.groups = {}; self.group_std = {}; self._fill(); self._stds()

    def paste(self, text=None):
        if text is None:
            try: text = self.win.clipboard_get()
            except tk.TclError: self.msg.configure(text="Буфер обміну порожній.", fg="#8c5a1a"); return
        n = 0; unknown = []
        for ln in text.replace("\r", "").split("\n"):
            parts = [x.strip() for x in ln.split("\t")]
            if len(parts) < 2 or not parts[0] or not parts[1]: continue
            if parts[0] in self.cultivars: self.groups[parts[0]] = parts[1]; n += 1
            elif parts[0].lower() not in ("сорт", "назва", "cultivar"): unknown.append(parts[0])
        self._fill(); self._stds()
        self.msg.configure(text=f"Вставлено груп: {n}." + (f" Немає в таблиці: {', '.join(unknown[:5])}{' …' if len(unknown) > 5 else ''}." if unknown else ""), fg="#1a6b1a" if n else "#8c5a1a")

    def ok(self):
        missing = [g for g in set(self.groups.values()) if not self.group_std.get(g)]
        if missing and not messagebox.askyesno("Стандарти груп", f"Для груп без стандарту ({', '.join(sorted(missing))}) сорти порівнюватимуться із загальним стандартом. Продовжити?", parent=self.win): return
        self.o.groups = dict(self.groups); self.o.group_std = {g: s for g, s in self.group_std.items() if s}
        self.o._update_groups_label(); self.win.destroy()
