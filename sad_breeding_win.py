# sad_breeding_win.py — S.A.D. v2.1: вікна розділу «Селекція та генетика»
# -*- coding: utf-8 -*-
from sad_common import *
import numpy as np
import sad_gxe_core as GX
import sad_breeding_core as BC
import sad_breeding as BR
import sad_mixed_sections as MS
import sad_gencorr_sections as GS
import sad_assoc_sections as AS
import sad_breeding_ui as U
import sad_design_sections as DS
import sad_selection_sections as SEL
import sad_het_ord_sections as HO
import sad_design_core as DC
from sad_breeding_ui import ResultsViewer, render_section, do_export, sec_text
from sad_stability_ancova import StabilityWindow

RF = ("Times New Roman", 11)
RB = ("Times New Roman", 11, "bold")


def _is_num(s):
    try:
        float(str(s).strip().replace(",", ".").replace("\u00a0", "").replace(" ", "")); return True
    except ValueError:
        return False


# ═══════════════════════════════════════════════════════════════
# Спільна основа: вікно з сіткою введення
# ═══════════════════════════════════════════════════════════════
class GridWindow:
    TITLE = ""; HELP = ""; INFO = ""
    HEADERS = []; N_ROWS = 30; COL_W = 14
    NUMERIC_FROM = 0            # з цього стовпця й далі очікуються числа (для розпізнавання рядка заголовків)
    DYNAMIC_COLS = False

    def __init__(self, parent, gs=None):
        self.parent = parent
        self.win = tk.Toplevel(parent); self.win.title(self.TITLE); self.win.geometry("1020x700"); set_icon(self.win)
        self.header_entries, self.entries = [], []
        self._build()

    # ── побудова ─────────────────────────────────────────────
    def _build(self):
        top = tk.Frame(self.win, padx=8, pady=6); top.pack(fill=tk.X)
        tk.Button(top, text="▶ Виконати", bg="#c62828", fg="white", font=("Times New Roman", 13),
                  command=self._run).pack(side=tk.LEFT, padx=4)
        mb = tk.Menubutton(top, text="⚙ Таблиця ▾", font=RF, relief=tk.RAISED, bd=2); mb.pack(side=tk.LEFT, padx=4)
        sm = tk.Menu(mb, tearoff=0)
        sm.add_command(label="Додати рядки (+10)", command=lambda: self._add_rows(10))
        sm.add_command(label="Видалити останній рядок", command=self._del_row)
        if self.DYNAMIC_COLS:
            sm.add_separator()
            sm.add_command(label="Додати стовпець", command=self._add_col)
            sm.add_command(label="Видалити останній стовпець", command=self._del_col)
        sm.add_separator(); sm.add_command(label="🗑 Очистити таблицю", command=self._clear)
        mb["menu"] = sm
        tk.Button(top, text="Вставити з буфера", font=RF, command=self._paste).pack(side=tk.LEFT, padx=4)
        if getattr(self, "JOURNAL", False):
            tk.Button(top, text="📂 З польового журналу…", font=RF, command=self._from_journal).pack(side=tk.LEFT, padx=4)
        tk.Button(top, text="📚 Довідка", bg="#1a4b8c", fg="white", font=RF, command=self._show_help).pack(side=tk.LEFT, padx=4)
        self.opts = tk.Frame(self.win, padx=8); self.opts.pack(fill=tk.X)
        self.build_options(self.opts)
        if self.INFO:
            info = tk.Frame(self.win, bg="#f0f4ff", padx=8, pady=4); info.pack(fill=tk.X, padx=8, pady=(2, 4))
            tk.Label(info, text=self.INFO, font=("Times New Roman", 10), bg="#f0f4ff", justify="left", wraplength=960).pack(anchor="w")
        mid = tk.Frame(self.win); mid.pack(fill=tk.BOTH, expand=True, padx=8)
        self._canvas = tk.Canvas(mid); self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(mid, orient="vertical", command=self._canvas.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.configure(yscrollcommand=sb.set)
        self.inner = tk.Frame(self._canvas); self._canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self._canvas.config(scrollregion=self._canvas.bbox("all")))
        self.win.bind("<MouseWheel>", lambda e: self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        for j, h in enumerate(self.HEADERS): self._make_header(j, h)
        for i in range(self.N_ROWS): self._make_row()
        self._rebind()
        self.after_build()

    def build_options(self, frame):
        pass

    def _new_col_name(self, j):
        return f"X{j}"

    def after_build(self):
        """Хук: викликається, коли сітка вже створена (заголовки й комірки існують)."""
        pass

    def _make_header(self, j, text):
        e = tk.Entry(self.inner, width=self.COL_W, bg="#1a4b8c", fg="white", font=("Times New Roman", 11, "bold"),
                     insertbackground="white", justify="center")
        e.insert(0, text); e.grid(row=0, column=j, padx=1, pady=1); self.header_entries.append(e)

    def _make_row(self):
        i = len(self.entries); row = []
        for j in range(len(self.header_entries)):
            e = tk.Entry(self.inner, width=self.COL_W, font=("Times New Roman", 11), highlightthickness=1,
                         highlightbackground="#c0c0c0")
            e.grid(row=i + 1, column=j, padx=1, pady=1); row.append(e)
        self.entries.append(row)

    def _rebind(self):
        _bind_nav(self.entries, self.win); _bind_fill_handle(self.entries, self.win)

    def _add_rows(self, n=1):
        for _ in range(n): self._make_row()
        self._rebind()

    def _del_row(self):
        if len(self.entries) <= 3: return
        for e in self.entries.pop(): e.destroy()

    def _add_col(self):
        j = len(self.header_entries); self._make_header(j, self._new_col_name(j))
        for i, row in enumerate(self.entries):
            e = tk.Entry(self.inner, width=self.COL_W, font=("Times New Roman", 11), highlightthickness=1,
                         highlightbackground="#c0c0c0")
            e.grid(row=i + 1, column=j, padx=1, pady=1); row.append(e)
        self._rebind()

    def _del_col(self):
        if len(self.header_entries) <= 3: return
        self.header_entries.pop().destroy()
        for row in self.entries: row.pop().destroy()
        self._rebind()

    def _clear(self):
        if not messagebox.askyesno("Очистити", "Видалити всі дані з таблиці?", parent=self.win): return
        for row in self.entries:
            for e in row: e.delete(0, tk.END)

    # ── дані ─────────────────────────────────────────────────
    def fill_table(self, headers, rows):
        """Заповнює таблицю програмно: заголовки й рядки (значення – текст або число; None – порожньо)."""
        while len(self.header_entries) < len(headers): self._add_col()
        for j, e in enumerate(self.header_entries):
            e.delete(0, tk.END); e.insert(0, headers[j] if j < len(headers) else "")
        while len(self.entries) < len(rows) + 2: self._make_row()
        self._rebind()
        for i, row in enumerate(self.entries):
            for j, e in enumerate(row):
                e.delete(0, tk.END)
                if i < len(rows) and j < len(rows[i]) and rows[i][j] is not None:
                    v = rows[i][j]; e.insert(0, (f"{v:.6g}" if isinstance(v, float) else str(v)))

    def _journal_rows(self):
        """Ділянки з журналу (усі роки) → (rows, chosen, info) або None."""
        from sad_journal_trial import open_journal_plots
        return open_journal_plots(self.win, multi_select=True)

    def header_names(self):
        return [e.get().strip() for e in self.header_entries]

    def rows(self):
        out = []
        for row in self.entries:
            vals = [e.get().strip() for e in row]
            if any(vals): out.append(vals)
        return out

    def _paste(self):
        try: data = self.win.clipboard_get()
        except Exception:
            messagebox.showwarning("", "Скопіюйте таблицю з Excel (Ctrl+C) і спробуйте знову.", parent=self.win); return
        parsed = [ln.split("\t") for ln in data.splitlines() if ln.strip()]
        if not parsed: return
        r0 = c0 = 0
        w = self.win.focus_get()
        if isinstance(w, tk.Entry):
            for i, row in enumerate(self.entries):
                for j, e in enumerate(row):
                    if e is w: r0, c0 = i, j
        ncols = len(self.header_entries)
        start = 0
        if r0 == 0 and c0 == 0:
            first = parsed[0]
            cols = [c for c in range(self.NUMERIC_FROM, min(len(first), ncols))]
            if cols and any(first[c].strip() and not _is_num(first[c]) for c in cols):    # перший рядок — заголовки
                for c in range(min(len(first), ncols)):
                    self.header_entries[c].delete(0, tk.END); self.header_entries[c].insert(0, first[c].strip())
                start = 1
        data_rows = parsed[start:]
        while r0 + len(data_rows) > len(self.entries): self._make_row()
        self._rebind()
        for ir, cells in enumerate(data_rows):
            for jc, val in enumerate(cells):
                cc = c0 + jc
                if cc >= ncols: continue
                en = self.entries[r0 + ir][cc]; en.delete(0, tk.END); en.insert(0, val.strip())

    # ── виконання ────────────────────────────────────────────
    def _run(self):
        raise NotImplementedError

    def _show(self, title, sections, banner=None):
        ResultsViewer(self.win, title, sections, banner=banner)

    def _fail(self, e):
        messagebox.showwarning("Перевірте дані", str(e), parent=self.win)

    def _show_help(self):
        win = tk.Toplevel(self.win); win.title("Довідка — " + self.TITLE); win.geometry("760x680"); set_icon(win)
        txt = ScrolledText(win, wrap="word", font=("Times New Roman", 11), relief=tk.FLAT)
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=6); txt.insert("1.0", self.HELP); txt.configure(state="disabled")


# ═══════════════════════════════════════════════════════════════
# Генетичні параметри
# ═══════════════════════════════════════════════════════════════
class GenParWindow(GridWindow):
    TITLE = "Генетичні параметри (H², GCV, PCV, GA)"
    HEADERS = ["Генотип", "Середовище", "Повторність", "Ознака 1", "Ознака 2", "Ознака 3"]
    NUMERIC_FROM = 3
    INFO = ("Один рядок — одна ділянка. Стовпці: генотип, середовище (лише для серії дослідів), повторність (блок), значення ознак. "
            "Назви ознак можна змінити в синіх заголовках. Дослід має бути збалансованим (кожен генотип у кожній повторності).")
    HELP = BR.GENPAR_HELP

    def build_options(self, f):
        self.multi_var = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="Серія дослідів у кількох середовищах (використати стовпець «Середовище»)",
                       variable=self.multi_var, font=RF).pack(side=tk.LEFT)
        tk.Label(f, text="Інтенсивність добору:", font=RF).pack(side=tk.LEFT, padx=(18, 4))
        self.k_var = tk.StringVar(value="5 %")
        ttk.Combobox(f, textvariable=self.k_var, values=list(BC.SELECTION_K), state="readonly", width=6).pack(side=tk.LEFT)

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            S, banner = BR.sections_genpar(rows, self.header_names(), self.multi_var.get(), self.k_var.get())
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("Генетичні параметри — результати", S, banner)


# ═══════════════════════════════════════════════════════════════
# Комбінаційна здатність
# ═══════════════════════════════════════════════════════════════
class CombAbilityWindow(GridWindow):
    TITLE = "Комбінаційна здатність (лінія × тестер, діалель)"
    HEADERS = ["Лінія", "Тестер", "Повторність", "Ознака 1", "Ознака 2", "Ознака 3"]
    NUMERIC_FROM = 3
    INFO = ("Один рядок — одна ділянка. Лінія × тестер: стовпці «Лінія», «Тестер». Діалель: стовпці «Батько 1», «Батько 2» "
            "(для батьківських форм обидва однакові). Дослід має бути збалансованим за повторностями.")
    HELP = BR.LT_HELP + "\n\n" + "═" * 40 + "\n\n" + BR.DIALLEL_HELP

    def build_options(self, f):
        self.design_var = tk.StringVar(value="Лінія × тестер")
        tk.Label(f, text="Схема:", font=RF).pack(side=tk.LEFT)
        cb = ttk.Combobox(f, textvariable=self.design_var, values=["Лінія × тестер", "Діалель (Гріффінг)"], state="readonly", width=20)
        cb.pack(side=tk.LEFT, padx=4); cb.bind("<<ComboboxSelected>>", lambda e: self._on_design())
        tk.Label(f, text="Метод:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.method_var = tk.StringVar(value="2 (батьки + F₁)")
        self.method_cb = ttk.Combobox(f, textvariable=self.method_var, values=["2 (батьки + F₁)", "4 (лише F₁)"], state="readonly", width=16)
        self.method_cb.pack(side=tk.LEFT)
        tk.Label(f, text="Модель:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.model_var = tk.StringVar(value="I — фіксована")
        self.model_cb = ttk.Combobox(f, textvariable=self.model_var, values=["I — фіксована", "II — випадкова"], state="readonly", width=15)
        self.model_cb.pack(side=tk.LEFT)
        tk.Label(f, text="Ознака:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.trait_var = tk.StringVar()
        self.trait_cb = ttk.Combobox(f, textvariable=self.trait_var, state="readonly", width=16, postcommand=self._refresh_traits)
        self.trait_cb.pack(side=tk.LEFT)

    def after_build(self):
        self._on_design()

    def _refresh_traits(self):
        names = [h for h in self.header_names()[3:] if h]
        self.trait_cb.configure(values=names)
        if self.trait_var.get() not in names and names: self.trait_var.set(names[0])

    def _on_design(self):
        lt = self.design_var.get().startswith("Лінія")
        for j, nm in ((0, "Лінія" if lt else "Батько 1"), (1, "Тестер" if lt else "Батько 2")):
            self.header_entries[j].delete(0, tk.END); self.header_entries[j].insert(0, nm)
        st = "disabled" if lt else "readonly"
        self.method_cb.configure(state=st); self.model_cb.configure(state=st)
        self._refresh_traits()

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); self._refresh_traits()
            tname = self.trait_var.get()
            if tname not in heads[3:]: raise BC.BreedingError("Оберіть ознаку для аналізу.")
            col = 3 + heads[3:].index(tname)
            if not any(r[col].strip() for r in rows): raise BC.BreedingError(f"Стовпець «{tname}» порожній.")
            if self.design_var.get().startswith("Лінія"):
                S, warns = BR.sections_line_tester(rows, col, tname); title = f"Лінія × тестер — {tname}"
            else:
                method = 2 if self.method_var.get().startswith("2") else 4
                model = "I" if self.model_var.get().startswith("I —") else "II"
                S, warns = BR.sections_diallel(rows, col, tname, method, model); title = f"Діалель — {tname}"
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(title, S, warns)


# ═══════════════════════════════════════════════════════════════
# Змішана модель (REML / BLUP)
# ═══════════════════════════════════════════════════════════════
class MixedWindow(GridWindow):
    JOURNAL = True
    TITLE = "Змішана модель (REML / BLUP) — незбалансовані дані"
    HEADERS = ["Генотип", "Середовище", "Повторність", "Блок", "Ознака 1", "Ознака 2", "Ознака 3"]
    NUMERIC_FROM = 4; COL_W = 13
    INFO = ("Один рядок — одна ділянка; допускаються пропущені ділянки й різна кількість повторностей. «Середовище» потрібне лише "
            "для серії дослідів; «Блок» — для схем із неповними блоками (він вкладений у повторність).")
    HELP = MS.MIXED_HELP

    def build_options(self, f):
        self.mode_var = tk.StringVar(value="Серія дослідів (кілька середовищ)")
        tk.Label(f, text="Схема:", font=RF).pack(side=tk.LEFT)
        ttk.Combobox(f, textvariable=self.mode_var, state="readonly", width=32,
                     values=["Серія дослідів (кілька середовищ)", "Один дослід"]).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text="Генотип:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.geno_var = tk.StringVar(value="випадковий (BLUP)")
        ttk.Combobox(f, textvariable=self.geno_var, state="readonly", width=20,
                     values=["випадковий (BLUP)", "фіксований (скориговані середні)"]).pack(side=tk.LEFT)
        tk.Label(f, text="Повторності:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.rep_var = tk.StringVar(value="фіксовані")
        ttk.Combobox(f, textvariable=self.rep_var, state="readonly", width=10, values=["фіксовані", "випадкові"]).pack(side=tk.LEFT)
        self.blk_var = tk.BooleanVar(value=False)
        tk.Checkbutton(f, text="Є неповні блоки", variable=self.blk_var, font=RF).pack(side=tk.LEFT, padx=8)
        tk.Label(f, text="Ознака:", font=RF).pack(side=tk.LEFT, padx=(6, 2))
        self.trait_var = tk.StringVar()
        self.trait_cb = ttk.Combobox(f, textvariable=self.trait_var, state="readonly", width=12, postcommand=self._refresh_traits)
        self.trait_cb.pack(side=tk.LEFT)
        tk.Label(f, text="Стандарти (через «;», лише для фіксованого генотипу):", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.ctl_var = tk.StringVar()
        tk.Entry(f, textvariable=self.ctl_var, width=16, font=RF).pack(side=tk.LEFT)

    def after_build(self):
        self._refresh_traits()

    def _from_journal(self, data=None):
        """Ділянки з польового журналу: генотип, середовище (рік – якщо їх кілька), повторність, неповний блок, ознаки."""
        res = data or self._journal_rows()
        if not res: return
        rows, chosen, info = res; multi = len(info["years"]) > 1
        self.fill_table(["Генотип", "Середовище", "Повторність", "Блок"] + chosen,
                        [[r["entry"], str(r["year"]) if multi else "", r["rep"], (f"{r['rep']}.{r['block']}" if r["block"] is not None else "")] + [r[c] for c in chosen] for r in rows])
        self.mode_var.set("Серія дослідів (кілька середовищ)" if multi else "Один дослід"); self.blk_var.set(bool(info["has_blocks"]))
        if info["standards"]: self.ctl_var.set("; ".join(info["standards"]))
        self._refresh_traits()
        if chosen: self.trait_var.set(chosen[0])

    def _refresh_traits(self):
        names = [h for h in self.header_names()[4:] if h]
        self.trait_cb.configure(values=names)
        if self.trait_var.get() not in names and names: self.trait_var.set(names[0])

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); self._refresh_traits(); tname = self.trait_var.get()
            if tname not in heads[4:]: raise BC.BreedingError("Оберіть ознаку для аналізу.")
            col = 4 + heads[4:].index(tname)
            rows = [r for r in rows if r[col].strip()]          # порожнє значення = пропущена ділянка
            mode = "met" if self.mode_var.get().startswith("Серія") else "single"
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                ctl = [c.strip() for c in self.ctl_var.get().split(";") if c.strip()] or None
                S, warns, _ = MS.sections_mixed(rows, col, tname, mode, self.geno_var.get().startswith("випадк"),
                                                self.rep_var.get() == "випадкові", self.blk_var.get(), controls=ctl)
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(f"Змішана модель — {tname}", S, warns)


# ═══════════════════════════════════════════════════════════════
# Генератор схем для багатьох номерів
# ═══════════════════════════════════════════════════════════════
class DesignWindow(GridWindow):
    TITLE = "Схеми для багатьох номерів (альфа-решітка, аугментована)"
    HEADERS = ["Номер (сорт, лінія)", "Тип (порожньо — новий; «ст» — стандарт)"]
    N_ROWS = 40; COL_W = 30; NUMERIC_FROM = 99
    INFO = ("Вставте список номерів (по одному в рядку) або згенеруйте кнопкою. Стандарти позначайте «ст» у другому стовпці. "
            "Альфа-решітка: стандарти (якщо є) додаються в кожен блок. Аугментована: потрібно ≥ 2 стандарти.")
    HELP = DS.DESIGN_HELP

    def build_options(self, f):
        self.kind_var = tk.StringVar(value="Альфа-решітка")
        tk.Label(f, text="Схема:", font=RF).pack(side=tk.LEFT)
        cb = ttk.Combobox(f, textvariable=self.kind_var, state="readonly", width=16, values=["Альфа-решітка", "Аугментована"])
        cb.pack(side=tk.LEFT, padx=4); cb.bind("<<ComboboxSelected>>", lambda e: self._on_kind())
        self.k_lbl = tk.Label(f, text="Розмір блоку k:", font=RF); self.k_lbl.pack(side=tk.LEFT, padx=(10, 2))
        self.k_var = tk.StringVar(value="6"); tk.Entry(f, textvariable=self.k_var, width=5, font=RF).pack(side=tk.LEFT)
        self.r_lbl = tk.Label(f, text="Повторностей r:", font=RF); self.r_lbl.pack(side=tk.LEFT, padx=(10, 2))
        self.r_var = tk.StringVar(value="2"); tk.Entry(f, textvariable=self.r_var, width=5, font=RF).pack(side=tk.LEFT)
        tk.Label(f, text="Зерно (необов.):", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.seed_var = tk.StringVar(); tk.Entry(f, textvariable=self.seed_var, width=8, font=RF).pack(side=tk.LEFT)
        tk.Button(f, text="Заповнити N1…Nv", font=RF, command=self._fill_names).pack(side=tk.LEFT, padx=10)
        self.hint = tk.Label(f, text="", font=("Times New Roman", 9), fg="#8c5a1a"); self.hint.pack(side=tk.LEFT)

    def after_build(self):
        self._on_kind()
        for r_ in self.entries: r_[0].bind("<KeyRelease>", lambda e: self._update_hint(), add="+")

    def _on_kind(self):
        alpha = self.kind_var.get().startswith("Альфа")
        self.k_lbl.configure(text="Розмір блоку k:" if alpha else "Кількість блоків b:")
        self.r_lbl.configure(text="Повторностей r:" if alpha else "")
        self.k_var.set("6" if alpha else "6")
        self._update_hint()

    def _lists(self):
        new, chk = [], []
        for r in self.rows():
            nm = r[0].strip()
            if not nm: continue
            (chk if (len(r) > 1 and r[1].strip().lower() in ("ст", "st", "стандарт", "check", "c")) else new).append(nm)
        return new, chk

    def _update_hint(self):
        try:
            new, chk = self._lists()
            if self.kind_var.get().startswith("Альфа") and new:
                ok = DC.valid_block_sizes(len(new))
                self.hint.configure(text=f"{len(new)} нових; допустимі k: " + ", ".join(str(k) for k, _ in ok[:10]) if ok else
                                    f"{len(new)} нових: підходящих k немає — змініть кількість номерів")
            else:
                self.hint.configure(text=f"{len(new)} нових; {len(chk)} стандартів" if new else "")
        except Exception:
            pass

    def _fill_names(self):
        dlg = tk.Toplevel(self.win); dlg.title("Згенерувати назви"); set_icon(dlg); dlg.grab_set()
        f = tk.Frame(dlg, padx=14, pady=10); f.pack()
        nv, cv, pv = tk.StringVar(value="48"), tk.StringVar(value="0"), tk.StringVar(value="N")
        for i, (lbl, var) in enumerate((("Нових номерів:", nv), ("Стандартів:", cv), ("Префікс назви:", pv))):
            tk.Label(f, text=lbl, font=RF).grid(row=i, column=0, sticky="w", pady=2)
            tk.Entry(f, textvariable=var, width=8, font=RF).grid(row=i, column=1, pady=2, padx=6)
        def ok():
            try: n, c = int(nv.get()), int(cv.get())
            except ValueError: messagebox.showwarning("", "Потрібні цілі числа.", parent=dlg); return
            for r_ in self.entries:
                for e in r_: e.delete(0, tk.END)
            while len(self.entries) < n + c: self._add_rows(10)
            for i in range(n): self.entries[i][0].insert(0, f"{pv.get()}{i + 1}")
            for j in range(c): self.entries[n + j][0].insert(0, f"St{j + 1}"); self.entries[n + j][1].insert(0, "ст")
            dlg.destroy(); self._update_hint()
        tk.Button(f, text="Заповнити", bg="#1a6b1a", fg="white", font=RF, command=ok).grid(row=3, column=0, columnspan=2, pady=8)
        center_win(dlg)

    def _run(self):
        try:
            new, chk = self._lists()
            if not new: raise BC.BreedingError("Список номерів порожній.")
            seed = int(self.seed_var.get()) if self.seed_var.get().strip() else None
            alpha = self.kind_var.get().startswith("Альфа")
            k = int(self.k_var.get()); r = int(self.r_var.get()) if alpha else None
        except ValueError:
            self._fail(BC.BreedingError("Розмір блоку, кількість повторностей і зерно мають бути цілими числами.")); return
        except BC.BreedingError as e:
            self._fail(e); return
        try:
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                if alpha: S, warns, _ = DS.sections_design("alpha", new, chk, k=k, r=r, seed=seed)
                else: S, warns, _ = DS.sections_design("aug", new, chk, n_blocks=k, seed=seed)
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("План досліду — " + self.kind_var.get(), S, warns)


# ═══════════════════════════════════════════════════════════════
# Індекси добору
# ═══════════════════════════════════════════════════════════════
class SelectionWindow(GridWindow):
    TITLE = "Індекси добору за кількома ознаками"
    HEADERS = ["Генотип", "Повторність", "Урожайність", "Ознака 2", "Ознака 3", "Ознака 4"]
    NUMERIC_FROM = 2; DYNAMIC_COLS = True; COL_W = 14
    INFO = ("Один рядок — одна ділянка збалансованого блокового досліду (кожен генотип у кожній повторності). Стовпці ознак — довільної кількості "
            "(меню «Таблиця»); назви змінюйте в заголовках. Ваги задайте в порядку ознак; знак «−» означає «менше — краще».")
    HELP = SEL.SELECTION_HELP

    def build_options(self, f):
        tk.Label(f, text="Ваги:", font=RF).pack(side=tk.LEFT)
        self.w_var = tk.StringVar(value="1; 1; 1; 1")
        tk.Entry(f, textvariable=self.w_var, width=18, font=RF).pack(side=tk.LEFT, padx=4)
        self.wm_var = tk.StringVar(value="відносні (на 1 σg)")
        ttk.Combobox(f, textvariable=self.wm_var, state="readonly", width=20, values=["відносні (на 1 σg)", "економічні"]).pack(side=tk.LEFT)
        tk.Label(f, text="Відбір, %:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.p_var = tk.StringVar(value="10")
        ttk.Combobox(f, textvariable=self.p_var, width=5, values=["1", "5", "10", "20", "30"]).pack(side=tk.LEFT)
        tk.Label(f, text="Бажані прирости (необов'язково, для Песека–Бейкера):", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.d_var = tk.StringVar()
        tk.Entry(f, textvariable=self.d_var, width=16, font=RF).pack(side=tk.LEFT)

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names()
            used = [c for c in range(2, len(heads)) if any(len(r) > c and r[c].strip() for r in rows)]
            try: p = float(self.p_var.get().replace(",", "."))
            except ValueError: raise BC.BreedingError("Частка відбору має бути числом (%).")
            if not 0 < p < 100: raise BC.BreedingError("Частка відбору має бути між 0 і 100 %.")
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                S, warns = SEL.sections_selection(rows, heads, self.w_var.get(), "relative" if self.wm_var.get().startswith("відн") else "economic",
                                                  self.d_var.get(), p)
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("Індекси добору — результати", S, warns)


# ═══════════════════════════════════════════════════════════════
# Гетерозис
# ═══════════════════════════════════════════════════════════════
class HeterosisWindow(GridWindow):
    TITLE = "Гетерозис гібридів F₁"
    HEADERS = ["Генотип", "Батько 1", "Батько 2", "Повторність", "Ознака 1", "Ознака 2", "Ознака 3"]
    NUMERIC_FROM = 4; COL_W = 13
    INFO = ("Один рядок — одна ділянка. Для БАТЬКІВСЬКИХ форм і стандарту стовпці «Батько 1», «Батько 2» залишайте порожніми; для ГІБРИДІВ — "
            "вкажіть обох батьків (їхні назви мають збігатися з назвами в стовпці «Генотип»). Дослід має містити ділянки батьків і гібридів.")
    HELP = HO.HET_HELP

    def build_options(self, f):
        tk.Label(f, text="Стандарт:", font=RF).pack(side=tk.LEFT)
        self.std_var = tk.StringVar()
        self.std_cb = ttk.Combobox(f, textvariable=self.std_var, width=18, postcommand=self._refresh_names); self.std_cb.pack(side=tk.LEFT, padx=4)
        tk.Label(f, text="Напрям:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.dir_var = tk.StringVar(value="більше — краще")
        ttk.Combobox(f, textvariable=self.dir_var, state="readonly", width=16, values=["більше — краще", "менше — краще"]).pack(side=tk.LEFT)
        tk.Label(f, text="α:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.alpha_var = tk.StringVar(value="0.05")
        ttk.Combobox(f, textvariable=self.alpha_var, state="readonly", width=5, values=["0.10", "0.05", "0.01"]).pack(side=tk.LEFT)
        tk.Label(f, text="Ознака:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.trait_var = tk.StringVar()
        self.trait_cb = ttk.Combobox(f, textvariable=self.trait_var, state="readonly", width=12, postcommand=self._refresh_traits); self.trait_cb.pack(side=tk.LEFT)

    def after_build(self):
        self._refresh_traits()

    def _refresh_names(self):
        self.std_cb.configure(values=list(dict.fromkeys(r[0] for r in self.rows() if r[0])))

    def _refresh_traits(self):
        names = [h for h in self.header_names()[4:] if h]
        self.trait_cb.configure(values=names)
        if self.trait_var.get() not in names and names: self.trait_var.set(names[0])

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); self._refresh_traits(); tname = self.trait_var.get()
            if tname not in heads[4:]: raise BC.BreedingError("Оберіть ознаку для аналізу.")
            col = 4 + heads[4:].index(tname)
            S, warns = HO.sections_heterosis(rows, col, tname, self.std_var.get(), "higher" if self.dir_var.get().startswith("більше") else "lower",
                                             float(self.alpha_var.get()))
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(f"Гетерозис — {tname}", S, warns)


# ═══════════════════════════════════════════════════════════════
# Бальні ознаки й AUDPC
# ═══════════════════════════════════════════════════════════════
class ScoresWindow(GridWindow):
    TITLE = "Бальні ознаки й AUDPC"
    HEADERS_SCORES = ["Генотип", "Повторність", "Бал", "Ознака 2", "Ознака 3"]
    HEADERS_AUDPC = ["Генотип", "Повторність", "01.06.2024", "08.06.2024", "15.06.2024"]
    HEADERS = HEADERS_SCORES
    NUMERIC_FROM = 2; DYNAMIC_COLS = True; COL_W = 13
    INFO = ("Режим «Порівняння за балами»: один рядок — одна рослина/ділянка, у стовпці ознаки — бал. Режим «AUDPC»: заголовки стовпців — моменти "
            "обліків (числа-дні або дати ДД.ММ.РРРР), у комірках — значення (бал чи % ураження) кожного обліку для ділянки.")
    HELP = HO.SCORES_HELP

    def build_options(self, f):
        self.mode_var = tk.StringVar(value="Порівняння за балами")
        cb = ttk.Combobox(f, textvariable=self.mode_var, state="readonly", width=22, values=["Порівняння за балами", "AUDPC (розвиток у часі)"])
        cb.pack(side=tk.LEFT); cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode())
        tk.Label(f, text="Шкала:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.smin_var, self.smax_var = tk.StringVar(value="1"), tk.StringVar(value="9")
        tk.Entry(f, textvariable=self.smin_var, width=4, font=RF).pack(side=tk.LEFT); tk.Label(f, text="–", font=RF).pack(side=tk.LEFT)
        tk.Entry(f, textvariable=self.smax_var, width=4, font=RF).pack(side=tk.LEFT)
        tk.Label(f, text="Краще:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.dir_var = tk.StringVar(value="менше — краще")
        ttk.Combobox(f, textvariable=self.dir_var, state="readonly", width=14, values=["менше — краще", "більше — краще"]).pack(side=tk.LEFT)
        tk.Label(f, text="Поправка:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.adj_var = tk.StringVar(value="Холм")
        ttk.Combobox(f, textvariable=self.adj_var, state="readonly", width=16, values=["Холм", "Бонферроні", "Беньяміні–Хохберг"]).pack(side=tk.LEFT)
        tk.Label(f, text="Макс. шкали (AUDPC):", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.ymax_var = tk.StringVar()
        tk.Entry(f, textvariable=self.ymax_var, width=6, font=RF).pack(side=tk.LEFT)
        tk.Label(f, text="Ознака:", font=RF).pack(side=tk.LEFT, padx=(10, 2))
        self.trait_var = tk.StringVar()
        self.trait_cb = ttk.Combobox(f, textvariable=self.trait_var, state="readonly", width=10, postcommand=self._refresh_traits); self.trait_cb.pack(side=tk.LEFT)

    def after_build(self):
        self._refresh_traits()

    def _refresh_traits(self):
        names = [h for h in self.header_names()[2:] if h]
        self.trait_cb.configure(values=names)
        if self.trait_var.get() not in names and names: self.trait_var.set(names[0])

    def _on_mode(self):
        hs = self.HEADERS_AUDPC if self.mode_var.get().startswith("AUDPC") else self.HEADERS_SCORES
        for j, e in enumerate(self.header_entries[:len(hs)]):
            e.delete(0, tk.END); e.insert(0, hs[j])
        self._refresh_traits()

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); adj = {"Холм": "holm", "Бонферроні": "bonferroni", "Беньяміні–Хохберг": "bh"}[self.adj_var.get()]
            if self.mode_var.get().startswith("AUDPC"):
                S, warns = HO.sections_audpc(rows, heads, adj, 0.05, self.ymax_var.get()); title = "AUDPC — результати"
            else:
                self._refresh_traits(); tname = self.trait_var.get()
                if tname not in heads[2:]: raise BC.BreedingError("Оберіть ознаку для аналізу.")
                col = 2 + heads[2:].index(tname)
                S, warns = HO.sections_scores(rows, col, tname, self.smin_var.get(), self.smax_var.get(), adj, 0.05,
                                              self.dir_var.get().startswith("менше")); title = f"Бальні ознаки — {tname}"
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(title, S, warns)


# ═══════════════════════════════════════════════════════════════
# Порівняння зі стандартом
# ═══════════════════════════════════════════════════════════════
class ControlWindow(GridWindow):
    JOURNAL = True
    TITLE = "Порівняння зі стандартом (тест Дуннетта)"
    HEADERS = ["Номер (сорт)", "Повторність / блок", "Ознака 1", "Ознака 2", "Ознака 3"]
    NUMERIC_FROM = 2; COL_W = 18
    INFO = ("Один рядок — одна ділянка. Стандарт (контроль) записується в тому ж стовпці, що й інші номери, під своєю назвою. "
            "Дослід може бути незбалансованим; повторності/блоки враховуються як блоки.")
    HELP = BR.CONTROL_HELP

    def build_options(self, f):
        tk.Label(f, text="Стандарт (кілька — через «;»):", font=RF).pack(side=tk.LEFT)
        self.ctl_var = tk.StringVar()
        self.ctl_cb = ttk.Combobox(f, textvariable=self.ctl_var, width=24, postcommand=self._refresh_entries)
        self.ctl_cb.pack(side=tk.LEFT, padx=4)
        tk.Label(f, text="Ознака:", font=RF).pack(side=tk.LEFT, padx=(12, 2))
        self.trait_var = tk.StringVar()
        self.trait_cb = ttk.Combobox(f, textvariable=self.trait_var, state="readonly", width=14, postcommand=self._refresh_traits)
        self.trait_cb.pack(side=tk.LEFT)
        tk.Label(f, text="Тест:", font=RF).pack(side=tk.LEFT, padx=(12, 2))
        self.alt_var = tk.StringVar(value="двобічний")
        ttk.Combobox(f, textvariable=self.alt_var, state="readonly", width=16,
                     values=["двобічний", "більше стандарту", "менше стандарту"]).pack(side=tk.LEFT)
        tk.Label(f, text="α:", font=RF).pack(side=tk.LEFT, padx=(12, 2))
        self.alpha_var = tk.StringVar(value="0.05")
        ttk.Combobox(f, textvariable=self.alpha_var, state="readonly", width=5, values=["0.10", "0.05", "0.01"]).pack(side=tk.LEFT)
        self.blocks_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="Враховувати блоки", variable=self.blocks_var, font=RF).pack(side=tk.LEFT, padx=10)

    def after_build(self):
        self._refresh_traits()

    def _refresh_entries(self):
        names = list(dict.fromkeys(r[0] for r in self.rows() if r[0]))
        self.ctl_cb.configure(values=names)

    def _from_journal(self, data=None):
        """Ділянки з польового журналу: номер, повторність/блок (для аугментованої схеми – блок), ознаки; стандарти – зі схеми."""
        res = data or self._journal_rows()
        if not res: return
        rows, chosen, info = res; years = info["years"]
        if len(years) > 1:
            messagebox.showinfo("Польовий журнал", f"У журналі кілька років ({', '.join(map(str, years))}): для порівняння зі стандартом взято "
                                f"останній рік {years[-1]}. Для серії років використайте «Змішану модель».", parent=self.win)
            rows = [r for r in rows if r["year"] == years[-1]]
        blk = lambda r: r["block"] if r["block"] is not None else r["rep"]
        self.fill_table(["Номер (сорт)", "Повторність / блок"] + chosen, [[r["entry"], blk(r)] + [r[c] for c in chosen] for r in rows])
        if info["standards"]: self.ctl_var.set("; ".join(info["standards"]))
        self.blocks_var.set(True); self._refresh_traits(); self._refresh_entries()
        if chosen: self.trait_var.set(chosen[0])

    def _refresh_traits(self):
        names = [h for h in self.header_names()[2:] if h]
        self.trait_cb.configure(values=names)
        if self.trait_var.get() not in names and names: self.trait_var.set(names[0])

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); self._refresh_traits(); tname = self.trait_var.get()
            if tname not in heads[2:]: raise BC.BreedingError("Оберіть ознаку для аналізу.")
            col = 2 + heads[2:].index(tname)
            ctl = [c.strip() for c in self.ctl_var.get().split(";") if c.strip()]
            if not ctl: raise BC.BreedingError("Вкажіть стандарт (назву номера-контролю).")
            alt = {"двобічний": "two-sided", "більше стандарту": "greater", "менше стандарту": "less"}[self.alt_var.get()]
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                S, warns = BR.sections_control(rows, col, tname, ctl, self.blocks_var.get(), float(self.alpha_var.get()), alt)
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(f"Порівняння зі стандартом — {tname}", S, warns)


# ═══════════════════════════════════════════════════════════════
# Генотипні й фенотипні кореляції
# ═══════════════════════════════════════════════════════════════
class GenCorrWindow(GridWindow):
    TITLE = "Генотипні й фенотипні кореляції (rG, rP)"
    HEADERS = ["Генотип", "Повторність", "Ознака 1", "Ознака 2", "Ознака 3", "Ознака 4"]
    NUMERIC_FROM = 2; DYNAMIC_COLS = True; COL_W = 14; N_ROWS = 40
    INFO = ("Один рядок — одна ділянка збалансованого блочного досліду: генотип, повторність, значення ознак. Ознак має бути ≥ 2, "
            "кожен генотип — у кожній повторності. Назви ознак змінюйте в синіх заголовках; стовпці додаються через меню «Таблиця». "
            "Для надійних висновків про rG потрібно ≥ 30 генотипів.")
    HELP = GS.GENCORR_HELP

    def _new_col_name(self, j):
        return f"Ознака {j - 1}"

    def build_options(self, f):
        tk.Label(f, text="α:", font=RF).pack(side=tk.LEFT)
        self.alpha_var = tk.StringVar(value="0.05")
        ttk.Combobox(f, textvariable=self.alpha_var, state="readonly", width=6, values=["0.05", "0.01", "0.10"]).pack(side=tk.LEFT, padx=4)
        tk.Label(f, text="Бутстреп-вибірок:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.boot_var = tk.StringVar(value="2000")
        ttk.Combobox(f, textvariable=self.boot_var, state="readonly", width=7, values=["500", "1000", "2000", "5000"]).pack(side=tk.LEFT)
        tk.Label(f, text="(більше вибірок — стабільніші межі інтервалу, але довше)", font=("Times New Roman", 9), fg="#666").pack(side=tk.LEFT, padx=8)

    def _run(self):
        try:
            rows = self.rows()
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                S, warns, _ = GS.sections_gencorr(rows, self.header_names(), float(self.alpha_var.get()), int(self.boot_var.get()))
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("Генотипні й фенотипні кореляції — результати", S, warns)


# ═══════════════════════════════════════════════════════════════
# Зв'язок змінних різних типів
# ═══════════════════════════════════════════════════════════════
class AssocWindow(GridWindow):
    TITLE = "Зв'язок змінних різних типів (η, r_rb, V Крамера)"
    HEADERS = ["Група", "Значення", "Частота"]
    MODES = ["η: група × кількісна ознака", "Дві групи: r_rb і r_pb", "Спряженість: ознака A × ознака B"]
    NUMERIC_FROM = 99; COL_W = 22; N_ROWS = 40
    INFO = ("Один рядок – одне спостереження. Режими η та «Дві групи»: стовпець 1 – назва групи (сорт, варіант), стовпець 2 – значення ознаки. "
            "Режим «Спряженість»: стовпці 1 і 2 – значення двох якісних ознак; стовпець 3 (необов'язково) – кількість таких спостережень, "
            "тоді можна вносити готову таблицю частот.")
    HELP = AS.ASSOC_HELP

    def build_options(self, f):
        tk.Label(f, text="Режим:", font=RF).pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value=self.MODES[0])
        cb = ttk.Combobox(f, textvariable=self.mode_var, state="readonly", width=32, values=self.MODES)
        cb.pack(side=tk.LEFT, padx=4); cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode())
        tk.Label(f, text="α:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.alpha_var = tk.StringVar(value="0.05")
        ttk.Combobox(f, textvariable=self.alpha_var, state="readonly", width=6, values=["0.05", "0.01", "0.10"]).pack(side=tk.LEFT)
        tk.Label(f, text="Бутстреп:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.boot_var = tk.StringVar(value="2000")
        ttk.Combobox(f, textvariable=self.boot_var, state="readonly", width=7, values=["500", "1000", "2000", "5000"]).pack(side=tk.LEFT)

    def after_build(self):
        self._on_mode()

    def _on_mode(self):
        heads = (["Група", "Значення", "(не використовується)"] if not self.mode_var.get().startswith("Спряженість")
                 else ["Ознака A", "Ознака B", "Частота (необов'язково)"])
        for e, h in zip(self.header_entries, heads):
            e.delete(0, tk.END); e.insert(0, h)

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            heads = self.header_names(); mode = self.mode_var.get(); alpha = float(self.alpha_var.get()); nb = int(self.boot_var.get())
            self.win.configure(cursor="watch"); self.win.update_idletasks()
            try:
                if mode.startswith("η"): S, warns, _ = AS.sections_eta(rows, heads[1] or "Значення", alpha); title = "Кореляційне відношення η – результати"
                elif mode.startswith("Дві"): S, warns, _ = AS.sections_two_groups(rows, heads[1] or "Значення", alpha, nb); title = "Дві групи – результати"
                else: S, warns, _ = AS.sections_contingency(rows, heads[0] or "Ознака A", heads[1] or "Ознака B", alpha, nb); title = "Таблиця спряженості – результати"
            finally:
                self.win.configure(cursor="")
        except BC.BreedingError as e:
            self._fail(e); return
        self._show(title, S, warns)


# ═══════════════════════════════════════════════════════════════
# Стресостійкість
# ═══════════════════════════════════════════════════════════════
class StressWindow(GridWindow):
    TITLE = "Індекси стресостійкості"
    HEADERS = ["Генотип", "Yp (сприятливі умови)", "Ys (стрес)"]
    NUMERIC_FROM = 1; COL_W = 22
    INFO = ("Для кожного генотипу — середній урожай (або інша ознака, де вище = краще) у сприятливих (Yp) і стресових (Ys) умовах. "
            "Значення мають бути додатними.")
    HELP = BR.STRESS_HELP

    def _run(self):
        try:
            rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            S, warns = BR.sections_stress([r[:3] for r in rows])
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("Стресостійкість — результати", S, warns)


# ═══════════════════════════════════════════════════════════════
# Шляховий аналіз
# ═══════════════════════════════════════════════════════════════
class PathWindow(GridWindow):
    TITLE = "Шляховий аналіз (path analysis)"
    HEADERS = ["X1", "X2", "X3", "X4", "X5", "Y (результат)"]
    NUMERIC_FROM = 0; DYNAMIC_COLS = True
    INFO = ("Один рядок — одне спостереження (генотип, ділянка). Останній стовпець — результативна ознака (напр. урожайність), "
            "решта — ознаки-причини. Назви змінюйте в синіх заголовках; стовпці додаються через меню «Таблиця». "
            "Порожні стовпці ігноруються.")
    HELP = BR.PATH_HELP

    def _run(self):
        try:
            heads = self.header_names(); rows = self.rows()
            if not rows: raise BC.BreedingError("Таблиця порожня.")
            ncol = len(heads)
            keep = [j for j in range(ncol - 1) if any(r[j].strip() for r in rows)]
            if len(keep) < 2: raise BC.BreedingError("Потрібно щонайменше 2 заповнені ознаки-причини.")
            sel = keep + [ncol - 1]
            S, warns = BR.sections_path([[r[j] for j in sel] for r in rows], [heads[j] for j in sel])
        except BC.BreedingError as e:
            self._fail(e); return
        self._show("Шляховий аналіз — результати", S, warns)


# ═══════════════════════════════════════════════════════════════
# Аналіз стабільності (розширений)
# ═══════════════════════════════════════════════════════════════
STAB_EXTRA = """

══════════════════════════════════════════════════
ДОДАТКОВІ АНАЛІЗИ (розділи «➕» у вікні результатів)
══════════════════════════════════════════════════

Таблиця має бути ПОВНОЮ (без порожніх клітинок): програма не підставляє пропущені значення.

ПОХИБКА ЗА ПОВТОРНОСТЯМИ. Якщо у вас є дані по повторностях, натисніть «📥 Довга таблиця з буфера»
і вставте стовпці: Генотип, Середовище, Повторність, Значення. Програма:
  • виконає комбінований ANOVA (G, E, G×E, повторності в середовищах, похибка);
  • перевірить однорідність похибок середовищ (тест Бартлетта);
  • заповнить таблицю середніх і поля r, MSE, df — це вмикає строгі тести S²d (Ебергарт–Рассел)
    і F-тести осей AMMI.
Без довгої таблиці можна вручну вказати r, MSE і df (з вашого ANOVA).

ЩО РАХУЄТЬСЯ: ANOVA; параметричні індекси (S², CV, W², σ² Шукли, P Ліна–Біннса, bᵢ, S²δ/S²d);
непараметричні (S(1–6), NP(1–4), TOP); ранг-сума Канга; кореляція рангів між індексами; AMMI (осі, ASV, YSI,
біплоти AMMI1/AMMI2); GGE-біплоти («хто де переміг», продуктивність × стабільність).

ПОРАДА. Різні індекси часто дублюють один одного (W² і σ² дають однакові ранги). Обирайте 2–3 різнотипні,
наприклад Ебергарт–Рассел + AMMI.
"""


class BreedingStabilityWindow(StabilityWindow):
    HELP_TEXT = StabilityWindow.HELP_TEXT + STAB_EXTRA

    def __init__(self, parent, gs):
        self._ca = None; self._ca_means = None
        super().__init__(parent, gs)

    def _build(self):
        super()._build()
        top = self.win.winfo_children()[0]
        opt = tk.Frame(self.win, padx=8, pady=2); opt.pack(fill=tk.X, after=top)
        tk.Label(opt, text="Для строгих тестів:", font=("Times New Roman", 10, "bold")).pack(side=tk.LEFT)
        self.r_var, self.mse_var, self.df_var = tk.StringVar(value="1"), tk.StringVar(), tk.StringVar()
        for lbl, var, w in (("повторностей r", self.r_var, 4), ("MSE (похибка)", self.mse_var, 9), ("df похибки", self.df_var, 5)):
            tk.Label(opt, text=lbl, font=("Times New Roman", 10)).pack(side=tk.LEFT, padx=(10, 2))
            tk.Entry(opt, textvariable=var, width=w, font=RF).pack(side=tk.LEFT)
        tk.Button(opt, text="📥 Довга таблиця з буфера", bg="#1a6b8c", fg="white", font=RF,
                  command=self._import_long).pack(side=tk.LEFT, padx=(14, 4))
        tk.Label(opt, text="GGE:", font=("Times New Roman", 10)).pack(side=tk.LEFT, padx=(12, 2))
        self.svp_var = tk.StringVar(value="genotype")
        ttk.Combobox(opt, textvariable=self.svp_var, values=["genotype", "environment", "symmetric"], state="readonly", width=11).pack(side=tk.LEFT)
        tk.Label(opt, text="(genotype — для порівняння генотипів)", font=("Times New Roman", 9), fg="#666").pack(side=tk.LEFT, padx=4)

    # ── імпорт довгої таблиці ────────────────────────────────
    def _import_long(self):
        try: data = self.win.clipboard_get()
        except Exception:
            messagebox.showwarning("", "Скопіюйте з Excel 4 стовпці: Генотип, Середовище, Повторність, Значення.", parent=self.win); return
        rows = [ln.split("\t") for ln in data.splitlines() if ln.strip()]
        if rows and len(rows[0]) >= 4 and not _is_num(rows[0][3]): rows = rows[1:]
        try:
            if not rows or any(len(r) < 4 for r in rows): raise BC.BreedingError("Потрібно 4 стовпці: Генотип, Середовище, Повторність, Значення.")
            y = [BR.to_float(r[3], f"рядок {i + 1}") for i, r in enumerate(rows)]
            ca = GX.combined_anova([r[0].strip() for r in rows], [r[1].strip() for r in rows], [r[2].strip() for r in rows], y)
        except BC.BreedingError as e:
            messagebox.showwarning("Перевірте дані", str(e), parent=self.win); return
        g, e = ca["g"], ca["e"]
        while self.cols_n < 1 + e: self._add_col()
        while self.cols_n > 1 + e and self.cols_n > 3: self._del_col()
        for j, nm in enumerate(ca["env_names"]): self.env_vars[j].set(nm)
        while len(self.entries) < g: self._add_row()
        for row in self.entries:
            for en in row: en.delete(0, tk.END)
        for i, gname in enumerate(ca["gen_names"]):
            self.entries[i][0].insert(0, gname)
            for j in range(e): self.entries[i][1 + j].insert(0, f"{ca['means'][i, j]:.6g}")
        self.r_var.set(str(ca["r"])); self.mse_var.set(f"{ca['mse']:.6g}"); self.df_var.set(str(ca["df_err"]))
        self._ca = ca; self._ca_means = ca["means"].copy(); _autofit_col(self.entries, 0)
        bp = ca["bartlett"]["p"]
        msg = (f"Прочитано: {g} генотипів × {e} середовищ × {ca['r']} повторностей.\nMSE = {ca['mse']:.4g}; df похибки = {ca['df_err']}.\n"
               f"Тест Бартлетта: p = {bp:.3f}" + (" — похибки НЕОДНОРІДНІ, комбінований аналіз ненадійний!" if bp < 0.05 else " — похибки однорідні."))
        (messagebox.showwarning if bp < 0.05 else messagebox.showinfo)("Довга таблиця прочитана", msg, parent=self.win)

    def _error_params(self):
        def num(var, conv, name, positive=True):
            s = var.get().strip().replace(",", ".")
            if not s: return None
            try: v = conv(float(s) if conv is int else s)
            except ValueError: raise BC.BreedingError(f"«{name}»: потрібне число.")
            if positive and v <= 0: raise BC.BreedingError(f"«{name}» має бути додатним.")
            return v
        r = num(self.r_var, int, "повторностей r") or 1
        mse = num(self.mse_var, float, "MSE")
        dfe = num(self.df_var, int, "df похибки")
        return r, mse, dfe

    # ── додаткові розділи у вікні результатів ───────────────
    def _after_results(self, win, sidebar, show_panel, sidebar_btn, content):
        d = self._st_data
        comma_var = tk.BooleanVar(value=True)
        try:
            r, mse, dfe = self._error_params()
            ca = self._ca
            # Комбінований ANOVA чинний, лише якщо таблицю не редагували після імпорту. Клітинки містять середні,
            # округлені до 6 значущих цифр, тому порівнюємо з допуском (а не на точну рівність — інакше ANOVA
            # відкидався б завжди); будь-яке реальне редагування значно перевищує цей допуск.
            if ca is not None:
                same = (ca["gen_names"] == d["gen_names"] and ca["env_names"] == d["env_names"]
                        and d["data"].shape == self._ca_means.shape
                        and np.allclose(np.nan_to_num(d["data"]), np.nan_to_num(self._ca_means), rtol=1e-5, atol=1e-9))
                if not same: ca = None
            if ca is not None: r, mse, dfe = ca["r"], ca["mse"], ca["df_err"]
            data_used = ca["means"] if ca is not None else d["data"]          # точні середні, а не округлені з клітинок
            sections, _ = BR.build_stability_sections(data_used, d["gen_names"], d["env_names"], r, mse, dfe, ca=ca,
                                                      svp=self.svp_var.get())
        except BC.BreedingError as e:
            sections = [sec_text("Додаткові аналізи недоступні", str(e), key="err")]
        self._st_sections = sections
        # Кнопки експорту пакуємо ПЕРШИМИ (внизу): Tk віддає місце тому, що запаковано раніше, тож вони
        # завжди лишаються видимими, а довгий список розділів прокручується.
        bar = tk.Frame(sidebar, bg="#2c3e50"); bar.pack(side=tk.BOTTOM, fill=tk.X, pady=8)
        tk.Checkbutton(bar, text="Десяткова кома", variable=comma_var, bg="#2c3e50", fg="#ecf0f1", selectcolor="#2c3e50",
                       activebackground="#2c3e50", activeforeground="white", font=("Times New Roman", 9)).pack(anchor="w", padx=10)
        for txt, kind in (("📊 Excel — нові розділи", "xlsx"), ("📄 Word — нові розділи", "docx")):
            tk.Button(bar, text=txt, font=("Times New Roman", 10), command=lambda k=kind: do_export(
                win, self._st_sections, "Аналіз стабільності", k, comma_var.get())).pack(fill=tk.X, padx=10, pady=2)
        tk.Label(sidebar, text="ДОДАТКОВІ АНАЛІЗИ", bg="#2c3e50", fg="#f1c40f", font=("Times New Roman", 10, "bold"),
                 pady=6).pack(fill=tk.X)
        holder = tk.Frame(sidebar, bg="#2c3e50"); holder.pack(fill=tk.BOTH, expand=True)
        cv = tk.Canvas(holder, bg="#2c3e50", highlightthickness=0, width=190)
        vs = ttk.Scrollbar(holder, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg="#2c3e50"); cv.create_window((0, 0), window=inner, anchor="nw", width=190)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.configure(yscrollcommand=vs.set); cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); vs.pack(side=tk.RIGHT, fill=tk.Y)
        def _wheel(ev):
            cv.yview_scroll(-1 if (getattr(ev, "num", 0) == 4 or getattr(ev, "delta", 0) > 0) else 1, "units")
        for w_ in (cv, inner):
            w_.bind("<MouseWheel>", _wheel); w_.bind("<Button-4>", _wheel); w_.bind("<Button-5>", _wheel)
        rendered = set()
        for sec in sections:
            frame = tk.Frame(content)
            btn = tk.Button(inner, text="➕ " + sec["title"], bg="#2c3e50", fg="#bdc3c7", font=("Times New Roman", 11),
                            relief=tk.FLAT, anchor="w", justify="left", wraplength=165, padx=10, pady=4,
                            activebackground="#c62828", activeforeground="white")
            btn.pack(fill=tk.X); tk.Frame(inner, bg="#3d5166", height=1).pack(fill=tk.X)
            btn.bind("<MouseWheel>", _wheel); btn.bind("<Button-4>", _wheel); btn.bind("<Button-5>", _wheel)
            def cmd(s=sec, f=frame, b=btn):
                if s["key"] not in rendered:
                    render_section(f, s, comma_var, win); rendered.add(s["key"])
                show_panel(f, b)
            btn.configure(command=cmd)
