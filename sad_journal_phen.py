# sad_journal_phen.py – S.A.D. v2.1: фенологія в польовому журналі – одна таблиця «ділянки × фази», яку дозаповнюють протягом сезону
# -*- coding: utf-8 -*-
"""Відкривається з польового журналу кнопкою «🌸 Фенологія…». Рядки – ділянки (сорт/варіант, повторність або блок), стовпчики – фази
культури за шкалою BBCH. Кожна фаза зберігається в журналі як показник типу «дата» (його бачать усі аналізи; дата → номер дня року).
Якщо в ділянці кілька облікових рослин, дата ділянки записується всім її рослинам. «Обходи» – запис відсотка рослин у фазі на кожному
обході; програма обчислює дату настання (10 % – початок, 50 % – масове, 90 % – кінець) і вписує в таблицю. Обходи зберігаються в журналі,
тож їх можна вести кілька днів чи тижнів."""
import os, json, statistics, datetime as _dt
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from sad_common import set_icon
import sad_phenology as P
import sad_phenology_journal as PJ

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)
BG_ERR, BG_WARN, BG_OK, BG_MIXED = "#ffcdd2", "#ffe0b2", "#ffffff", "#e3f2fd"


def journal_plots(owner):
    """Ділянки поточного року журналу: [{id, name, rep, block, keys}] у порядку повторність → положення в полі."""
    import sad_journal_trial as JT
    fi = PJ._cultivar_factor(owner.factor_defs); groups = {}; cfg_std = set((owner.cfg or {}).get("standards") or [])
    for p in owner.plants:
        if p.role != JT.HP_ROLE_RECORDED: continue
        name = PJ._name_of({"factors": p.factors, "variant": p.variant}, owner.factor_defs, owner.variant_names, fi)
        if not name: continue
        rep = p.replication; blk = getattr(p, "block", None); pid = f"{rep}|{blk}|{name}"
        g = groups.setdefault(pid, {"id": pid, "name": name, "rep": rep, "block": blk, "keys": [], "pos": (p.row, p.position), "std": getattr(p, "kind", None) == "standard" or name in cfg_std})
        g["keys"].append(f"{p.row}:{p.position}"); g["pos"] = min(g["pos"], (p.row, p.position))
    return sorted(groups.values(), key=lambda g: (g["rep"] if g["rep"] is not None else 0, g["pos"]))


def scheme_years_json(folder):
    """Журнали всіх років із теки схеми: {рік: вміст}."""
    out = {}
    for nm in sorted(os.listdir(folder)) if folder and os.path.isdir(folder) else []:
        jp = os.path.join(folder, nm, f"журнал_{nm}.sadp")
        if nm.isdigit() and os.path.exists(jp):
            try: out[nm] = json.load(open(jp, encoding="utf-8"))
            except Exception: pass
    return out


class PhenologyTable:
    """Таблиця фенології поточного року журналу."""
    def __init__(self, parent, owner):
        self.o = owner; self.dirty = False; self.edited = set()
        self.plots = journal_plots(owner)
        presets = [r.get("preset") for r in owner.records.values() if r.get("kind") == "date" and r.get("preset")]
        self.preset = owner.cfg.get("phen_preset") or (max(set(presets), key=presets.count) if presets else "pome")
        if self.preset not in P.PRESETS: self.preset = "pome"
        self.win = tk.Toplevel(parent); self.win.title(f"Фенологія – {owner._current_year} рік"); self.win.geometry("1240x720"); set_icon(self.win)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        top = tk.Frame(self.win, padx=8, pady=5); top.pack(fill=tk.X)
        tk.Label(top, text="Культура:", font=RB, fg="#1a4b8c").pack(side=tk.LEFT)
        self.pv = tk.StringVar(value=P.PRESETS[self.preset]["name"])
        cb = ttk.Combobox(top, textvariable=self.pv, values=[P.PRESETS[k]["name"] for k in P.PRESET_ORDER if P.PRESETS[k]["phases"]], state="readonly", width=40); cb.pack(side=tk.LEFT, padx=6)
        cb.bind("<<ComboboxSelected>>", self._on_preset)
        tk.Button(top, text="💾 Зберегти", font=RB, bg="#1a6b1a", fg="white", command=self.save).pack(side=tk.LEFT, padx=(14, 4))
        tk.Button(top, text="📋 Обходи: % рослин у фазі…", font=RF, command=self.open_visits).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="▶ Аналіз фенофаз (усі роки)", font=RB, bg="#c62828", fg="white", command=self.analyze).pack(side=tk.RIGHT, padx=4)
        tk.Label(self.win, text="Дату вписуйте, коли фаза настала: 12.05 · 1205 · «12 травня» · «т» – сьогодні; подвійний клік – календар; Enter – униз; Ctrl+D – як вище. "
                 "Таблицю можна дозаповнювати протягом усього сезону: збережене не губиться. Наведіть курсор на заголовок фази – побачите критерій BBCH.",
                 font=SM, fg="#555", wraplength=1100, justify="left").pack(anchor="w", padx=10)
        self.status = tk.Label(self.win, text="", font=SM, fg="#555", anchor="w"); self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 4))
        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.cv = tk.Canvas(body, highlightthickness=0); vs = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview); hs = ttk.Scrollbar(body, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set); vs.pack(side=tk.RIGHT, fill=tk.Y); hs.pack(side=tk.BOTTOM, fill=tk.X); self.cv.pack(fill=tk.BOTH, expand=True)
        self.gf = tk.Frame(self.cv); self.cv.create_window((0, 0), window=self.gf, anchor="nw"); self.gf.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120), "units"))
        self._build()
        if not self.plots: self.status.configure(text="У схемі немає облікових ділянок.", fg="#c62828")

    # ── фази й значення ──
    def _phases(self):
        base = P.preset_phases(self.preset); keys = {p["key"] for p in base}
        for nm, r in self.o.records.items():                         # фази з журналу поза набором культури
            if r.get("kind") == "date" and r.get("phase_key") and r["phase_key"] not in keys:
                base.append({"key": r["phase_key"], "name": r.get("phase_name") or nm, "bbch": r.get("bbch", ""), "hint": ""}); keys.add(r["phase_key"])
        return base

    def _record_for(self, ph):
        for nm, r in self.o.records.items():
            if r.get("kind") == "date" and r.get("phase_key") == ph["key"]: return nm, r
        return P.phase_label(ph), None

    def _plot_value(self, plot, rec):
        """→ (текст, різні_дати): дата ділянки; якщо рослини мають різні дати – медіана з позначкою «~»."""
        if not rec: return "", False
        y = int(self.o._current_year); ds = []
        for k in plot["keys"]:
            v = (rec.get("values") or {}).get(k)
            if v:
                d, _m = P.parse_date_flex(v, y)
                if d: ds.append(d)
        if not ds: return "", False
        if len(set(ds)) == 1: return P.fmt_date(ds[0]), False
        med = _dt.date.fromordinal(int(statistics.median(x.toordinal() for x in ds) + 0.5)); return "~" + P.fmt_date(med), True

    def _build(self):
        for w in self.gf.winfo_children(): w.destroy()
        self.phases = self._phases(); self.cells = {}
        from sad_phenology_win import Tooltip
        heads = ["№", "Сорт / варіант", "Повт./блок"] + [P.phase_label(p) for p in self.phases]
        for j, h in enumerate(heads):
            lb = tk.Label(self.gf, text=h, font=("Times New Roman", 10, "bold"), bg="#1a4b8c", fg="white", wraplength=120 if j >= 3 else 0, pady=3)
            lb.grid(row=0, column=j, sticky="nsew", padx=1, pady=(0, 2))
            if j >= 3: Tooltip(lb, lambda ph=self.phases[j - 3]: P.phase_hint(ph))
        for i, pl in enumerate(self.plots):
            tk.Label(self.gf, text=str(i + 1), font=SM, fg="#666", width=4).grid(row=i + 1, column=0)
            tk.Label(self.gf, text=pl["name"] + ("  (станд.)" if pl["std"] else ""), font=RB if pl["std"] else RF, anchor="w", width=26).grid(row=i + 1, column=1, sticky="w")
            tk.Label(self.gf, text=str(pl["block"] if pl["block"] is not None and pl["rep"] == pl["block"] else (pl["rep"] if pl["block"] is None else f"{pl['rep']}.{pl['block']}")), font=RF, width=7).grid(row=i + 1, column=2)
            for j, ph in enumerate(self.phases):
                e = tk.Entry(self.gf, font=RF, width=12, justify="center", relief=tk.SOLID, bd=1); e.grid(row=i + 1, column=3 + j, padx=1, pady=1)
                txt, mixed = self._plot_value(pl, self._record_for(ph)[1])
                if txt: e.insert(0, txt)
                if mixed: e.configure(bg=BG_MIXED)
                self.cells[(i, j)] = e; self._bind(e, i, j)
        self._validate()

    def _bind(self, e, i, j):
        e.bind("<FocusOut>", lambda ev=None, i=i, j=j: self._norm(i, j)); e.bind("<Return>", lambda ev=None, i=i, j=j: self._move(i, j, 1)); e.bind("<Down>", lambda ev=None, i=i, j=j: self._move(i, j, 1))
        e.bind("<Up>", lambda ev=None, i=i, j=j: self._move(i, j, -1)); e.bind("<KeyRelease>", lambda ev=None, i=i, j=j: self._touched(i, j, ev))
        e.bind("<Control-d>", lambda ev=None, i=i, j=j: (self._fill_down(i, j), "break")[1]); e.bind("<Double-Button-1>", lambda ev=None, i=i, j=j: self._calendar(i, j))

    def _touched(self, i, j, ev=None):
        if ev is not None and getattr(ev, "keysym", "") in ("Return", "Down", "Up", "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Left", "Right"): return
        self.edited.add((i, j)); self.dirty = True

    def _norm(self, i, j):
        e = self.cells[(i, j)]; t = e.get().strip()
        if t and not t.startswith("~"):
            d, _m = P.parse_date_flex(t, int(self.o._current_year))
            if d and t != P.fmt_date(d): e.delete(0, tk.END); e.insert(0, P.fmt_date(d))
        self._validate()

    def _move(self, i, j, d):
        self._norm(i, j); k = i + d
        if 0 <= k < len(self.plots): self.cells[(k, j)].focus_set(); self.cells[(k, j)].icursor(tk.END)
        return "break"

    def _fill_down(self, i, j):
        if i > 0:
            v = self.cells[(i - 1, j)].get().strip().lstrip("~")
            if v: e = self.cells[(i, j)]; e.delete(0, tk.END); e.insert(0, v); self.edited.add((i, j)); self.dirty = True; self._validate()

    def _calendar(self, i, j):
        from sad_phenology_win import DatePicker
        e = self.cells[(i, j)]; d, _m = P.parse_date_flex(e.get().lstrip("~"), int(self.o._current_year))
        def put(dd): e.delete(0, tk.END); e.insert(0, P.fmt_date(dd)); self.edited.add((i, j)); self.dirty = True; self._validate()
        DatePicker(self.win, d, put, int(self.o._current_year))

    def _validate(self):
        y = int(self.o._current_year); nerr = nwarn = nfill = 0
        for i in range(len(self.plots)):
            prev = None
            for j in range(len(self.phases)):
                e = self.cells[(i, j)]; t = e.get().strip()
                mixed = t.startswith("~")
                if not t: e.configure(bg=BG_OK); continue
                d, _m = P.parse_date_flex(t.lstrip("~"), y)
                if d is None: e.configure(bg=BG_ERR); nerr += 1; continue
                nfill += 1
                if d.year != y or (prev is not None and d < prev): e.configure(bg=BG_WARN); nwarn += 1
                else: e.configure(bg=BG_MIXED if mixed else BG_OK)
                prev = d
        done = [P.phase_label(self.phases[j]) for j in range(len(self.phases)) if self.plots and all(self.cells[(i, j)].get().strip() for i in range(len(self.plots)))]
        self.status.configure(text=f"Ділянок: {len(self.plots)}; дат: {nfill}" + (f"; помилок: {nerr}" if nerr else "") + (f"; підозрілих: {nwarn}" if nwarn else "") +
                              (f"; повністю заповнено фаз: {len(done)}" if done else "") + ("  ·  є незбережені зміни" if self.dirty else ""), fg="#c62828" if nerr else ("#8c5a1a" if nwarn else "#555"))
        return nerr, nwarn

    def _on_preset(self, ev=None):
        key = next(k for k in P.PRESET_ORDER if P.PRESETS[k]["name"] == self.pv.get())
        if key == self.preset: return
        if self.dirty and not messagebox.askyesno("Культура", "Є незбережені зміни. Змінити культуру (незбережене буде втрачено)?", parent=self.win):
            self.pv.set(P.PRESETS[self.preset]["name"]); return
        self.preset = key; self.o.cfg["phen_preset"] = key; self.edited.clear(); self.dirty = False; self._build()

    # ── збереження в журнал ──
    def collect(self):
        """Зміни таблиці → записи журналу (лише відредаговані клітинки; рослинам ділянки – та сама дата). → (кількість дат, помилки)."""
        y = int(self.o._current_year); n = 0; errs = []
        for (i, j) in sorted(self.edited):
            pl = self.plots[i]; ph = self.phases[j]; t = self.cells[(i, j)].get().strip()
            if t.startswith("~"): continue                                # не змінювали: різні дати рослин лишаються як були
            nm, rec = self._record_for(ph)
            if rec is None:
                rec = {"unit": "дата", "kind": "date", "preset": self.preset, "phase_key": ph["key"], "bbch": ph.get("bbch", ""), "phase_name": ph["name"], "values": {}}
                self.o.records[nm] = rec
            vals = rec.setdefault("values", {})
            if not t:
                for k in pl["keys"]: vals.pop(k, None)
                continue
            d, msg = P.parse_date_flex(t, y)
            if d is None: errs.append(f"{pl['name']}, {ph['name']}: «{t}»"); continue
            for k in pl["keys"]: vals[k] = P.fmt_date(d)
            n += 1
        for nm in [nm for nm, r in self.o.records.items() if r.get("kind") == "date" and not r.get("values")]: del self.o.records[nm]
        return n, errs

    def save(self):
        nerr, _w = self._validate()
        if nerr and not messagebox.askyesno("Фенологія", f"Не схоже на дату: {nerr} клітинок (червоні). Їх не буде збережено. Зберегти решту?", parent=self.win): return False
        n, errs = self.collect()
        self.o.cfg["phen_preset"] = self.preset
        try: self.o._record_cb.configure(values=["(новий показник)"] + list(self.o.records.keys()))
        except Exception: pass
        ok = self.o._write_journal_to_disk("Фенологія")
        if ok: self.edited.clear(); self.dirty = False; self._validate()
        return ok

    def close(self):
        if self.dirty:
            ans = messagebox.askyesnocancel("Фенологія", "Зберегти зміни перед закриттям?", parent=self.win)
            if ans is None: return
            if ans and not self.save(): return
        self.win.destroy()

    def analyze(self):
        """Аналіз фенофаз за всі роки цього досліду (модуль «Фенологічні фази» з даними журналу)."""
        if self.dirty:
            if not messagebox.askyesno("Фенологія", "Спершу зберегти зміни (аналіз бере дані з журналу)?", parent=self.win): return None
            if not self.save(): return None
        yj = scheme_years_json(self.o._scheme_folder)
        if not yj: messagebox.showinfo("Фенологія", "Журнали цієї схеми ще не збережено.", parent=self.win); return None
        from sad_phenology_win import PhenologyWindow
        pw = PhenologyWindow(self.win.master); res = pw.import_journal(yj, quiet=True)
        if res is not None: pw._run()
        return pw

    def open_visits(self):
        return VisitsJournalDialog(self.win, self)


class VisitsJournalDialog:
    """Обходи: на кожному обході – відсоток рослин у фазі для кожної ділянки. Дата настання – коли досягнуто поріг (лінійна
    інтерполяція між обходами). Обходи зберігаються в журналі (параметр cfg «phen_visits»), тож облік можна вести кілька днів."""
    DEF_TARGETS = {"bloom": [("bloom0", 10), ("bloom50", 50), ("bloom1", 90)]}

    def __init__(self, parent, table):
        self.t = table; self.o = table.o
        self.store = self.o.cfg.setdefault("phen_visits", {})              # обходи поточного року – у даних журналу цього року
        self.win = tk.Toplevel(parent); self.win.title("Обходи: % рослин у фазі"); self.win.geometry("1100x640"); self.win.transient(parent); set_icon(self.win)
        tk.Label(self.win, text="На кожному обході запишіть, який відсоток рослин (пагонів, суцвіть) ділянки вже у фазі. Коли відсоток переходить поріг, "
                 "програма обчислює дату настання (між двома обходами – пропорційно) і вписує її в таблицю фенології. Обходи зберігаються – продовжуйте наступного дня.",
                 font=SM, fg="#555", wraplength=940, justify="left").pack(anchor="w", padx=10, pady=(8, 2))
        top = tk.Frame(self.win, padx=10); top.pack(fill=tk.X)
        tk.Label(top, text="Що обліковуєте:", font=RB).pack(side=tk.LEFT)
        self.sv = tk.StringVar(); self.scb = ttk.Combobox(top, textvariable=self.sv, width=26); self.scb.pack(side=tk.LEFT, padx=4)
        self.scb.bind("<<ComboboxSelected>>", lambda e: self._load_set())
        tk.Label(top, text="(наприклад, «Цвітіння»; можна вписати свою назву)", font=SM, fg="#666").pack(side=tk.LEFT)
        tk.Button(top, text="＋ Обхід (дата)…", font=RF, command=self.add_visit).pack(side=tk.LEFT, padx=(16, 4))
        tg = tk.LabelFrame(self.win, text=" Що записати в таблицю фенології ", font=RB, padx=8, pady=4); tg.pack(fill=tk.X, padx=10, pady=4)
        self.phase_labels = {P.phase_label(p): p["key"] for p in table.phases}; self.targets = []
        for i in range(3):
            fr = tk.Frame(tg); fr.pack(fill=tk.X, pady=1)
            pv = tk.StringVar(); ttk.Combobox(fr, textvariable=pv, values=[""] + list(self.phase_labels), state="readonly", width=46).pack(side=tk.LEFT)
            tk.Label(fr, text="– коли у фазі ≥", font=RF).pack(side=tk.LEFT, padx=4); tv = tk.StringVar(value=("10", "50", "90")[i]); tk.Entry(fr, textvariable=tv, width=5, font=RF).pack(side=tk.LEFT)
            tk.Label(fr, text="% рослин", font=RF).pack(side=tk.LEFT); self.targets.append((pv, tv))
        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.cv = tk.Canvas(body, highlightthickness=0); hs = ttk.Scrollbar(body, orient="horizontal", command=self.cv.xview); vs = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview)
        self.cv.configure(xscrollcommand=hs.set, yscrollcommand=vs.set); vs.pack(side=tk.RIGHT, fill=tk.Y); hs.pack(side=tk.BOTTOM, fill=tk.X); self.cv.pack(fill=tk.BOTH, expand=True)
        self.gf = tk.Frame(self.cv); self.cv.create_window((0, 0), window=self.gf, anchor="nw"); self.gf.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        bt = tk.Frame(self.win); bt.pack(fill=tk.X, padx=10, pady=(2, 8)); self.msg = tk.Label(bt, text="", font=SM, fg="#555", anchor="w", justify="left", wraplength=700); self.msg.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(bt, text="Обчислити дати й записати в таблицю", font=RB, bg="#1a6b1a", fg="white", command=self.apply).pack(side=tk.RIGHT, padx=4)
        tk.Button(bt, text="Закрити", font=RF, command=self.close).pack(side=tk.RIGHT)
        names = list(self.store) or ["Цвітіння"]; self.scb.configure(values=names); self.sv.set(names[0]); self._load_set()

    def _cur(self):
        nm = self.sv.get().strip() or "Цвітіння"
        return self.store.setdefault(nm, {"targets": [], "dates": [], "values": {}})

    def _load_set(self):
        st = self._cur(); keys = {v: k for k, v in self.phase_labels.items()}
        tg = st.get("targets") or [(k, th) for k, th in self.DEF_TARGETS["bloom"] if k in keys]
        for i, (pv, tv) in enumerate(self.targets):
            if i < len(tg): pv.set(keys.get(tg[i][0], "")); tv.set(str(tg[i][1]))
            else: pv.set(""); tv.set(("10", "50", "90")[i])
        self._draw()

    def _store(self):
        """Поточні клітинки → збережений набір обходів."""
        st = self._cur(); vals = st.setdefault("values", {})
        for (i, j), e in getattr(self, "cells", {}).items():
            pid = self.t.plots[i]["id"]; d = st["dates"][j]; t = e.get().strip().replace(",", ".").replace("%", "")
            if t: vals.setdefault(pid, {})[d] = t
            elif pid in vals: vals[pid].pop(d, None)
        st["targets"] = [[self.phase_labels[pv.get()], tv.get()] for pv, tv in self.targets if pv.get()]

    def _draw(self):
        for w in self.gf.winfo_children(): w.destroy()
        st = self._cur(); self.cells = {}
        tk.Label(self.gf, text="Сорт / варіант", font=RB, bg="#1a4b8c", fg="white", width=26).grid(row=0, column=0, padx=1)
        tk.Label(self.gf, text="Повт.", font=RB, bg="#1a4b8c", fg="white", width=6).grid(row=0, column=1, padx=1)
        for j, d in enumerate(st["dates"]): tk.Label(self.gf, text=d[:5] + "\n% у фазі", font=("Times New Roman", 10, "bold"), bg="#1a4b8c", fg="white", width=9).grid(row=0, column=2 + j, padx=1)
        for i, pl in enumerate(self.t.plots):
            tk.Label(self.gf, text=pl["name"], font=RF, anchor="w", width=26).grid(row=i + 1, column=0, sticky="w"); tk.Label(self.gf, text=str(pl["rep"]), font=RF, width=6).grid(row=i + 1, column=1)
            for j, d in enumerate(st["dates"]):
                e = tk.Entry(self.gf, font=RF, width=9, justify="center"); e.grid(row=i + 1, column=2 + j, padx=1, pady=1)
                v = st.get("values", {}).get(pl["id"], {}).get(d)
                if v is not None: e.insert(0, str(v))
                self.cells[(i, j)] = e
        if not st["dates"]: tk.Label(self.gf, text="Ще немає обходів – натисніть «＋ Обхід (дата)…».", font=RF, fg="#8c5a1a").grid(row=len(self.t.plots) + 2, column=0, columnspan=4, sticky="w", pady=6)

    def add_visit(self, date=None):
        self._store(); st = self._cur()
        if date is None:
            txt = simpledialog.askstring("Обхід", "Дата обходу (наприклад, 05.05; «т» – сьогодні):", parent=self.win)
            if not txt: return
            date, msg = P.parse_date_flex(txt, int(self.o._current_year))
            if date is None: messagebox.showwarning("", msg or "Не схоже на дату.", parent=self.win); return
        ds = P.fmt_date(date)
        if ds in st["dates"]: messagebox.showinfo("", "Такий обхід уже є.", parent=self.win); return
        st["dates"] = sorted(st["dates"] + [ds], key=lambda x: P.parse_date_flex(x, 2000)[0]); self._draw()
        names = list(self.store); self.scb.configure(values=names)

    def compute(self):
        """→ [{i, key, date, kind, thr}] без запису в таблицю."""
        self._store(); st = self._cur(); y = int(self.o._current_year); out = []
        thrs = []
        for k, t in st["targets"]:
            try: thrs.append((k, float(str(t).replace(",", "."))))
            except ValueError: raise ValueError(f"Поріг «{t}» має бути числом від 0 до 100.")
        for i, pl in enumerate(self.t.plots):
            vis = []
            for d, v in (st.get("values", {}).get(pl["id"]) or {}).items():
                try: vis.append((P.parse_date_flex(d, y)[0], float(str(v).replace(",", "."))))
                except ValueError: raise ValueError(f"«{v}» у рядку «{pl['name']}» (обхід {d[:5]}) – не число.")
            for k, thr in thrs:
                dd, kind = P.onset_from_visits(vis, thr); out.append({"i": i, "key": k, "date": dd, "kind": kind, "thr": thr})
        return out

    def apply(self):
        st = self._cur()
        if not st["dates"]: messagebox.showinfo("", "Додайте хоча б один обхід.", parent=self.win); return
        if not any(pv.get() for pv, _ in self.targets): messagebox.showinfo("", "Оберіть хоча б одну фазу для запису.", parent=self.win); return
        try: res = self.compute()
        except ValueError as e: messagebox.showwarning("", str(e), parent=self.win); return
        idx = {p["key"]: j for j, p in enumerate(self.t.phases)}; n = first = none = 0
        for r in res:
            if r["date"] is None: none += 1; continue
            j = idx[r["key"]]; e = self.t.cells[(r["i"], j)]; e.delete(0, tk.END); e.insert(0, P.fmt_date(r["date"])); self.t.edited.add((r["i"], j)); n += 1; first += r["kind"] == "first"
        self.t.dirty = True; self.t._validate()
        self.msg.configure(text=f"Записано в таблицю дат: {n}" + (f"; поріг досягнуто вже на першому обході (дата не пізніша за нього): {first}" if first else "") +
                           (f"; поріг ще не досягнуто: {none}" if none else "") + ". Не забудьте «💾 Зберегти» в таблиці фенології.", fg="#1a6b1a" if n else "#8c5a1a")

    def close(self):
        self._store(); self.t.dirty = True if self._cur()["dates"] else self.t.dirty; self.t._validate(); self.win.destroy()
