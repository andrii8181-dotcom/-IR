# sad_phenology_win.py – S.A.D. v2.1: вікно «Фенологічні спостереження»
# -*- coding: utf-8 -*-
import os, math, json, datetime as _dt, calendar
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import numpy as np
from matplotlib.figure import Figure
from sad_common import set_icon, make_tv, embed_figure, attach_export_bar
import sad_phenology as P

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)
FONT = ["Times New Roman", "DejaVu Serif"]
BG_ERR, BG_WARN, BG_OK, BG_NORM = "#ffcdd2", "#ffe0b2", "#ffffff", "#ffffff"
COL_NAME, COL_REP, COL0 = 0, 1, 2
HELP = """
ФЕНОЛОГІЧНІ СПОСТЕРЕЖЕННЯ

Призначення: облік дат настання фенологічних фаз при сортовивченні (за шкалою BBCH), порівняння сортів і років, суми температур до фази.

1. КУЛЬТУРА Й ФАЗИ
   Оберіть культуру – з'являться типові фази зі шкали BBCH. Коди й критерії настання узято з монографії «BBCH Monograph» (2nd ed., 2001,
   ред. U. Meier); критерій видно у спливній підказці над заголовком фази й у бланку. Кнопка «Фази…» дозволяє додати власні фази,
   змінити назву, код і критерій, змінити порядок чи прибрати зайві. Є набори для яблуні/груші, кісточкових, винограду, смородини, суниці,
   зернових, кукурудзи, соняшнику, сої, ріпаку, гороху, картоплі, томата/перцю/баклажана та універсальний.

2. ВВЕДЕННЯ ДАТ
   У кожному рядку – сорт (варіант) і, за потреби, повторність; у стовпцях фаз – дата настання. Дату можна набирати як завгодно:
   12.05 · 12.5 · 1205 · 120526 · 12/05 · 12 травня · 2026-05-12 · дата з Excel. Рік береться з вкладки року.
   «т» + Enter – сьогоднішня дата. Подвійний клік по клітинці – календар. Ctrl+D – скопіювати дату з клітинки вище.
   Правий клік – меню клітинки. Вставка блоку з Excel – Ctrl+V.
   Колір клітинки: червоний – не схоже на дату; оранжевий – порушено хронологічний порядок фаз у рядку або дата з іншого року.
   Однакові назви сортів у різних рядках – повторності (нумеруються за порядком, або вкажіть у стовпці «Повт.»).

3. РОКИ
   Вкладки «2024 · 2025 …» – роки досліду; «＋ Рік» додає рік (можна скопіювати список сортів з попереднього). Аналіз враховує всі роки.

3а. ГРУПИ СТИГЛОСТІ
   Якщо в досліді сорти різних груп стиглості, кнопка «👥 Групи стиглості…» дозволяє призначити кожному сорту групу й вибрати стандарт
   групи (або вставити пари «сорт – група» з Excel; стовпчик «Група» читається й під час імпорту). Тоді різниця в днях, класи
   «ранній / середній / пізній» і тест Даннетта рахуються відносно стандарту своєї групи. Сорти без групи – відносно загального стандарту.

3б. ДАНІ З ПОЛЬОВОГО ЖУРНАЛУ
   Для досліду, побудованого конструктором схеми (сорти – рівні фактора «Сорт», повторності, етикетки з QR), фенофази зручно вносити
   в польовому журналі кнопкою «🌸 Фенофаза…» – поряд із ростовими показниками й урожайністю. «📂 З польового журналу…» переносить
   у цей модуль усі роки: сорти, повторності й дати (кілька рослин ділянки – медіана дат).

4. ОБЛІК ЗА ВІЗИТАМИ
   Якщо у полі записували не дату, а відсоток рослин у фазі (на кожному візиті), «📋 Облік за візитами…» обчислює дату настання за
   порогом (наприклад, 10 % – початок, 50 % – масова, 90 % – кінець) лінійною інтерполяцією між візитами й вносить її в таблицю.

5. АНАЛІЗ
   Середні дати (± SD, діб) за сортами, відмінності від стандарту й групування на ранні / середні / пізні, тривалість періодів,
   дисперсійний аналіз дат, суми температур до фази (за погодою), графіки. Дати перетворюються на номер дня року (з поправкою на
   високосний рік). ANOVA – наближена, бо дати цілі; рік – фіксований фактор, блок – повторність, спільна для років.
   Порівняння середніх – у вкладці «ANOVA і порівняння середніх»; метод обирається зі списку, таблиці перераховуються одразу:
   • Автоматично: до 5 сортів – НІР05 із захистом F-тестом (якщо F неістотний, усі сорти «a»), до 30 – Тьюкі, понад 30 – Скотт–Кнотт;
   • НІР05 (Фішер) – найчутливіший, без поправки на кількість порівнянь: доречний для 3–5 сортів;
   • Тьюкі HSD і Бонферроні – суворіші (контролюють помилку по всіх парах); Дункан – до 30 сортів;
   • Скотт–Кнотт – розбиває середні на групи без перекриття (літери «a, b, c…» за групами; «a» – найраніша): зручний для десятків
     і сотень гібридів, коли парні літери нечитабельні;
   • Порівняння зі стандартом – тест Даннетта: класичний метод «багато номерів проти одного стандарту» (спільна помилка першого роду
     для всіх порівнянь), придатний і для сотень гібридів; ↓ істотно раніше, ↑ істотно пізніше, ≈ без різниці;
   • Порівняння зі стандартом – t із поправкою Холма: той самий підсумок, покроково-консервативна поправка (альтернатива Даннетту);
   • Краскел–Уолліс + Данн (з поправкою Холма) – непараметричний варіант за рангами, коли розподіл дат далекий від нормального.
   Літери парних порівнянь (НІР, Тьюкі, Бонферроні, Дункан, Данн) формуються до 60 сортів; для більшої кількості програма пояснює це й
   радить Скотт–Кнотт або порівняння зі стандартом. У таблиці результатів є H² – успадковуваність на середніх за сортами
   (1 − 1/F; для кількох років 1 − MS(сорт×рік)/MS(сорт)).

6. ПОГОДА
   «🌦 Погода…» підключає добові температури (з вікна «Погода», файла Excel/CSV або буфера): тоді додається вкладка «Суми температур».

7. БЛАНК ДЛЯ ПОЛЯ
   «🖨 Бланк» створює у Word порожню таблицю (сорти × фази) для друку й заповнення ручкою.

9. БАГАТО ГІБРИДІВ (ДЕСЯТКИ Й СОТНІ)
   Таблиця понад 120 рядків показується сторінками з кнопками «◀ ▶», переходом до рядка № і Enter / ↓ внизу сторінки; усі рядки
   лишаються в моделі й беруть участь в аналізі. Дані краще вставляти з Excel (Ctrl+V блоком) або імпортувати («📥 Excel…»).
   На графіках понад 30 сортів показуються найраніші, найпізніші й стандарт; для всіх сортів є гістограма середніх дат і
   ранжований профіль. Таблиці й звіт Word / Excel містять усі сорти.

8. ЗВІТ
   У вікні результатів кнопки «📄 Word» і «📊 Excel» зберігають усе: таблиці з сіткою й графіки.
"""


# ═══════════════════════════════════════════════════════════════
# Допоміжні діалоги
# ═══════════════════════════════════════════════════════════════
class Tooltip:
    """Спливна підказка біля курсора (текст береться в момент показу)."""
    def __init__(self, widget, text_fn, delay=350):
        self.w = widget; self.fn = text_fn; self.delay = delay; self.tip = None; self.job = None
        widget.bind("<Enter>", self._enter, add="+"); widget.bind("<Leave>", self._hide, add="+"); widget.bind("<ButtonPress>", self._hide, add="+")

    def _enter(self, ev=None):
        self._hide()
        self.job = self.w.after(self.delay, lambda: self._show(ev))

    def _show(self, ev):
        self.job = None; text = self.fn()
        if not text: return
        x = (ev.x_root if ev else self.w.winfo_rootx()) + 12; y = (ev.y_root if ev else self.w.winfo_rooty()) + 18
        self.tip = tk.Toplevel(self.w); self.tip.wm_overrideredirect(True); self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=text, font=("Times New Roman", 10), bg="#fffde7", fg="#222", relief=tk.SOLID, bd=1, justify="left", wraplength=360, padx=6, pady=3).pack()

    def _hide(self, ev=None):
        if self.job is not None:
            try: self.w.after_cancel(self.job)
            except Exception: pass
            self.job = None
        if self.tip is not None:
            try: self.tip.destroy()
            except Exception: pass
            self.tip = None



class DatePicker:
    """Простий календар: вибір дня; навігація по місяцях. on_pick(date) викликається при виборі."""
    def __init__(self, parent, start, on_pick, year_hint=None):
        self.on_pick = on_pick; self.sel = start
        base = start or _dt.date(year_hint or _dt.date.today().year, _dt.date.today().month, 1)
        self.y, self.m = base.year, base.month
        self.win = tk.Toplevel(parent); self.win.title("Календар"); self.win.resizable(False, False); set_icon(self.win); self.win.transient(parent)
        top = tk.Frame(self.win, padx=6, pady=6); top.pack(fill=tk.X)
        tk.Button(top, text="◀", width=3, command=lambda: self._shift(-1)).pack(side=tk.LEFT)
        self.lbl = tk.Label(top, font=RB, width=18); self.lbl.pack(side=tk.LEFT, expand=True)
        tk.Button(top, text="▶", width=3, command=lambda: self._shift(1)).pack(side=tk.RIGHT)
        self.body = tk.Frame(self.win, padx=6, pady=2); self.body.pack()
        tk.Button(self.win, text="Сьогодні", command=lambda: self._pick(_dt.date.today())).pack(pady=(2, 8))
        self._draw()

    def _shift(self, d):
        self.m += d
        if self.m < 1: self.m, self.y = 12, self.y - 1
        if self.m > 12: self.m, self.y = 1, self.y + 1
        self._draw()

    def _draw(self):
        for w in self.body.winfo_children(): w.destroy()
        self.lbl.configure(text=f"{['Січень', 'Лютий', 'Березень', 'Квітень', 'Травень', 'Червень', 'Липень', 'Серпень', 'Вересень', 'Жовтень', 'Листопад', 'Грудень'][self.m - 1]} {self.y}")
        for j, d in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]): tk.Label(self.body, text=d, font=SM, fg="#666", width=4).grid(row=0, column=j)
        for i, week in enumerate(calendar.Calendar(0).monthdayscalendar(self.y, self.m), 1):
            for j, day in enumerate(week):
                if not day: continue
                dd = _dt.date(self.y, self.m, day); cur = (dd == self.sel)
                tk.Button(self.body, text=str(day), width=3, relief=tk.SUNKEN if cur else tk.FLAT, bg="#1a4b8c" if cur else ("#fff3e0" if j >= 5 else "#f4f4f4"), fg="white" if cur else "black",
                          command=lambda d=dd: self._pick(d)).grid(row=i, column=j, padx=1, pady=1)

    def _pick(self, d):
        self.win.destroy(); self.on_pick(d)


class PhaseEditor:
    """Редактор списку фаз: додати, перейменувати, змінити код BBCH, порядок, видалити."""
    def __init__(self, parent, phases, preset_phases, on_ok):
        self.phases = [dict(p) for p in phases]; self.preset_phases = preset_phases; self.on_ok = on_ok
        self.win = tk.Toplevel(parent); self.win.title("Фази"); self.win.geometry("640x520"); set_icon(self.win); self.win.transient(parent); self.win.grab_set()
        tk.Label(self.win, text="Фази в порядку настання. Дані прихованих фаз не втрачаються.", font=SM, fg="#555").pack(anchor="w", padx=10, pady=(8, 2))
        frm = tk.Frame(self.win); frm.pack(fill=tk.BOTH, expand=True, padx=10)
        self.lb = tk.Listbox(frm, font=RF, exportselection=False, activestyle="none"); sb = ttk.Scrollbar(frm, command=self.lb.yview); self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); sb.pack(side=tk.LEFT, fill=tk.Y)
        side = tk.Frame(frm); side.pack(side=tk.LEFT, padx=8, fill=tk.Y)
        for txt, cmd in (("＋ Додати…", self.add), ("✎ Змінити…", self.edit), ("▲ Вище", lambda: self.move(-1)), ("▼ Нижче", lambda: self.move(1)), ("✖ Видалити", self.delete), ("↺ Типові фази культури", self.reset)):
            tk.Button(side, text=txt, font=RF, anchor="w", command=cmd).pack(fill=tk.X, pady=2)
        bt = tk.Frame(self.win); bt.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(bt, text="OK", font=RB, bg="#1a6b1a", fg="white", width=10, command=self.ok).pack(side=tk.RIGHT, padx=4)
        tk.Button(bt, text="Скасувати", font=RF, width=10, command=self.win.destroy).pack(side=tk.RIGHT)
        self.lb.bind("<Double-Button-1>", lambda e: self.edit()); self._fill()

    def _fill(self, sel=None):
        self.lb.delete(0, tk.END)
        for p in self.phases: self.lb.insert(tk.END, P.phase_label(p))
        if sel is not None and self.phases: self.lb.selection_set(min(sel, len(self.phases) - 1)); self.lb.see(min(sel, len(self.phases) - 1))

    def _cur(self):
        s = self.lb.curselection(); return s[0] if s else None

    def _ask(self, p=None):
        d = tk.Toplevel(self.win); d.title("Фаза"); d.transient(self.win); d.grab_set(); set_icon(d); out = {}
        tk.Label(d, text="Назва фази:", font=RF).grid(row=0, column=0, padx=8, pady=6, sticky="w"); nv = tk.StringVar(value=p["name"] if p else ""); tk.Entry(d, textvariable=nv, font=RF, width=40).grid(row=0, column=1, padx=8)
        tk.Label(d, text="Код BBCH (необов'язково):", font=RF).grid(row=1, column=0, padx=8, pady=6, sticky="w"); bv = tk.StringVar(value=p["bbch"] if p else ""); tk.Entry(d, textvariable=bv, font=RF, width=8).grid(row=1, column=1, padx=8, sticky="w")
        tk.Label(d, text="Критерій настання (підказка):", font=RF).grid(row=2, column=0, padx=8, pady=6, sticky="w"); hv = tk.StringVar(value=p.get("hint", "") if p else ""); tk.Entry(d, textvariable=hv, font=RF, width=60).grid(row=2, column=1, padx=8, sticky="w")
        def ok():
            if not nv.get().strip(): messagebox.showwarning("", "Вкажіть назву фази.", parent=d); return
            out.update(name=nv.get().strip(), bbch=bv.get().strip(), hint=hv.get().strip()); d.destroy()
        tk.Button(d, text="OK", font=RB, bg="#1a6b1a", fg="white", width=8, command=ok).grid(row=3, column=1, sticky="e", padx=8, pady=8)
        d.wait_window(d); return out or None

    def add(self):
        r = self._ask()
        if r:
            r["key"] = P.new_phase_key(r["name"], {p["key"] for p in self.phases}); i = self._cur(); i = len(self.phases) if i is None else i + 1
            self.phases.insert(i, r); self._fill(i)

    def edit(self):
        i = self._cur()
        if i is None: return
        r = self._ask(self.phases[i])
        if r: self.phases[i].update(r); self._fill(i)

    def move(self, d):
        i = self._cur()
        if i is None or not 0 <= i + d < len(self.phases): return
        self.phases[i], self.phases[i + d] = self.phases[i + d], self.phases[i]; self._fill(i + d)

    def delete(self):
        i = self._cur()
        if i is not None: del self.phases[i]; self._fill(i)

    def reset(self):
        self.phases = [dict(p) for p in self.preset_phases]; self._fill(0)

    def ok(self):
        if not self.phases: messagebox.showwarning("", "Потрібна хоча б одна фаза.", parent=self.win); return
        self.win.destroy(); self.on_ok(self.phases)


# ═══════════════════════════════════════════════════════════════
# Головне вікно
# ═══════════════════════════════════════════════════════════════
class PhenologyWindow:
    N_ROWS = 24
    PAGE_SIZE = 120          # понад стільки рядків таблиця показується сторінками (усі рядки лишаються в моделі й в аналізі)

    def __init__(self, parent, gs=None):
        self.parent = parent; self.gs = gs
        self.preset_key = "pome"; self.phases = P.preset_phases("pome")
        self.cur_year = _dt.date.today().year; self.years_data = {self.cur_year: []}
        self.standard = ""; self.thr = 3.0; self.groups = {}; self.group_std = {}
        self.series = None; self.weather_note = ""; self.sum_cfg = {"kind": "sat", "base": 10.0, "start": ["md", 3, 1]}
        self.entries = []; self.hdr = []; self._job = None; self._cell = (0, 0); self.results_win = None; self._path = None
        self.page = 0; self._paged_mode = False; self._off = 0; self._page_len = 0; self._total = 0; self._sig = None
        self.win = tk.Toplevel(parent); self.win.title("Фенологічні спостереження"); self.win.geometry("1260x760"); set_icon(self.win)
        self._build(); self._write_grid([]); self._update_years(); self._validate_all()

    # ── побудова ──
    def _build(self):
        w = self.win
        mb = tk.Menu(w); fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="Відкрити проєкт…", command=self.open_project); fm.add_command(label="Зберегти проєкт…", command=self.save_project)
        fm.add_separator(); fm.add_command(label="Дати в Excel…", command=self.export_excel); fm.add_command(label="Бланк для поля (Word)…", command=self.blank_form)
        mb.add_cascade(label="Файл", menu=fm); w.config(menu=mb)
        tb = tk.Frame(w, padx=6, pady=4); tb.pack(fill=tk.X)
        def sep(f): ttk.Separator(f, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=2)
        def grp(f, t): tk.Label(f, text=t, font=("Times New Roman", 9, "bold"), fg="#1a4b8c").pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(tb, text="▶ Аналіз", bg="#c62828", fg="white", font=("Times New Roman", 13), command=self._run).pack(side=tk.LEFT, padx=4)
        sep(tb); grp(tb, "Культура:")
        self.preset_var = tk.StringVar(value=P.PRESETS["pome"]["name"])
        cb = ttk.Combobox(tb, textvariable=self.preset_var, values=[P.PRESETS[k]["name"] for k in P.PRESET_ORDER], state="readonly", width=40); cb.pack(side=tk.LEFT, padx=2)
        cb.bind("<<ComboboxSelected>>", self._on_preset)
        tk.Button(tb, text="✎ Фази…", font=RF, command=self.edit_phases).pack(side=tk.LEFT, padx=3)
        tk.Button(tb, text="📚 Довідка", bg="#1a4b8c", fg="white", font=RF, command=self._show_help).pack(side=tk.RIGHT, padx=6)
        tbd = tk.Frame(w, padx=6, pady=2); tbd.pack(fill=tk.X); grp(tbd, "Дані:")
        tk.Button(tbd, text="Вставити з буфера", font=RF, command=self.paste_clipboard).pack(side=tk.LEFT, padx=2)
        tk.Button(tbd, text="📥 Excel…", font=RF, command=self.import_excel).pack(side=tk.LEFT, padx=2)
        tk.Button(tbd, text="📂 З польового журналу…", font=RF, command=self.import_journal).pack(side=tk.LEFT, padx=2)
        tk.Button(tbd, text="📋 Облік за візитами…", font=RF, command=self.open_visits).pack(side=tk.LEFT, padx=2)
        sep(tbd); grp(tbd, "Додатково:")
        tk.Button(tbd, text="🌦 Погода…", font=RF, command=self.open_weather).pack(side=tk.LEFT, padx=2)
        tk.Button(tbd, text="🖨 Бланк для поля", font=RF, command=self.blank_form).pack(side=tk.LEFT, padx=2)
        tb2 = tk.Frame(w, padx=6); tb2.pack(fill=tk.X); self._tb2 = tb2
        self.pagebar = tk.Frame(w, padx=6, pady=2, bg="#fff3e0")
        self.pg_lbl = tk.Label(self.pagebar, bg="#fff3e0", font=RF, fg="#8c5a1a")
        self.pg_lbl.pack(side=tk.LEFT, padx=(0, 10))
        for txt, cmd in (("⏮", lambda: self.goto_page(0)), ("◀ Попередня", lambda: self.goto_page(self.page - 1)), ("Наступна ▶", lambda: self.goto_page(self.page + 1)), ("⏭", lambda: self.goto_page(self._page_count() - 1))):
            tk.Button(self.pagebar, text=txt, font=SM, command=cmd).pack(side=tk.LEFT, padx=2)
        tk.Label(self.pagebar, text="  Перейти до рядка №", bg="#fff3e0", font=SM).pack(side=tk.LEFT); self.pg_row = tk.StringVar()
        ent = tk.Entry(self.pagebar, textvariable=self.pg_row, width=6, font=RF); ent.pack(side=tk.LEFT, padx=3); ent.bind("<Return>", lambda ev=None: self.goto_row())
        tk.Button(self.pagebar, text="Перейти", font=SM, command=self.goto_row).pack(side=tk.LEFT)
        tk.Label(self.pagebar, text="  (усі рядки беруть участь в аналізі; Enter внизу сторінки – на наступну)", bg="#fff3e0", font=SM, fg="#777").pack(side=tk.LEFT, padx=8)
        tk.Label(tb2, text="Роки:", font=RB, fg="#1a4b8c").pack(side=tk.LEFT, padx=(0, 4)); self.years_bar = tk.Frame(tb2); self.years_bar.pack(side=tk.LEFT)
        tk.Label(tb2, text="   Стандарт:", font=RF).pack(side=tk.LEFT); self.std_var = tk.StringVar()
        self.std_cb = ttk.Combobox(tb2, textvariable=self.std_var, state="readonly", width=24, postcommand=self._refresh_std); self.std_cb.pack(side=tk.LEFT, padx=3)
        self.std_cb.bind("<<ComboboxSelected>>", lambda e: setattr(self, "standard", "" if self.std_var.get() == "(середнє за сортами)" else self.std_var.get()))
        tk.Button(tb2, text="👥 Групи стиглості…", font=RF, command=self.open_groups).pack(side=tk.LEFT, padx=(4, 2))
        self.groups_lbl = tk.Label(tb2, text="", font=SM, fg="#1a4b8c"); self.groups_lbl.pack(side=tk.LEFT)
        tk.Label(tb2, text="  ранній/пізній при різниці ≥", font=RF).pack(side=tk.LEFT); self.thr_var = tk.StringVar(value="3")
        tk.Entry(tb2, textvariable=self.thr_var, width=4, font=RF).pack(side=tk.LEFT); tk.Label(tb2, text="діб", font=RF).pack(side=tk.LEFT)
        self.status = tk.Label(w, text="", font=SM, fg="#555", anchor="w"); self.status.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 4))
        tk.Label(w, text="Дата: 12.05 · 1205 · 12 травня · «т» – сьогодні. Подвійний клік – календар; Ctrl+D – дата з клітинки вище; Ctrl+V – вставка блоку з Excel.", font=SM, fg="#666").pack(side=tk.BOTTOM, anchor="w", padx=10)
        body = tk.Frame(w); body.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.cv = tk.Canvas(body, highlightthickness=0); vs = ttk.Scrollbar(body, orient="vertical", command=self.cv.yview); hs = ttk.Scrollbar(body, orient="horizontal", command=self.cv.xview)
        self.cv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set); vs.pack(side=tk.RIGHT, fill=tk.Y); hs.pack(side=tk.BOTTOM, fill=tk.X); self.cv.pack(fill=tk.BOTH, expand=True)
        self.gf = tk.Frame(self.cv); self.cv.create_window((0, 0), window=self.gf, anchor="nw"); self.gf.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120), "units"))
        self.menu = tk.Menu(w, tearoff=0)
        for lab, cmd in (("Сьогодні", self._cell_today), ("Дата з клітинки вище", self._cell_fill_down), ("Календар…", self._cell_calendar), ("Очистити клітинку", self._cell_clear)): self.menu.add_command(label=lab, command=cmd)

    # ── сітка ──
    def _phase_cols(self): return len(self.phases)

    def _rebuild_grid(self, rows, need=None):
        for ch in self.gf.winfo_children(): ch.destroy()
        self.entries = []; self.hdr = []
        heads = ["Сорт / варіант", "Повт."] + [P.phase_label(p) for p in self.phases]
        for j, h in enumerate(heads):
            lb = tk.Label(self.gf, text=h, font=("Times New Roman", 10, "bold"), bg="#1a4b8c", fg="white", wraplength=130 if j >= 2 else 0, justify="center", pady=3)
            lb.grid(row=0, column=j, sticky="nsew", padx=1, pady=(0, 2)); self.hdr.append(lb)
            if j >= 2: Tooltip(lb, lambda ph=self.phases[j - 2]: P.phase_hint(ph))
        n = need or max(self.N_ROWS, len(rows) + 6)
        for i in range(n): self._make_row(i)
        self._write_rows(rows)
    def _make_row(self, i):
        row = []
        for j in range(2 + self._phase_cols()):
            e = tk.Entry(self.gf, font=RF, width=22 if j == 0 else (5 if j == 1 else 13), justify="left" if j == 0 else "center", relief=tk.SOLID, bd=1)
            e.grid(row=i + 1, column=j, padx=1, pady=1, sticky="nsew"); self._bind_cell(e, i, j); row.append(e)
        self.entries.append(row)

    def _bind_cell(self, e, i, j):
        e.bind("<FocusIn>", lambda ev=None, i=i, j=j: setattr(self, "_cell", (i, j)))
        if j >= COL0:
            e.bind("<FocusOut>", lambda ev=None, i=i, j=j: self._normalize(i, j)); e.bind("<Double-Button-1>", lambda ev=None, i=i, j=j: (setattr(self, "_cell", (i, j)), self._cell_calendar()))
            e.bind("<Control-d>", lambda ev=None, i=i, j=j: (setattr(self, "_cell", (i, j)), self._cell_fill_down(), "break")[2])
        e.bind("<Return>", lambda ev=None, i=i, j=j: self._move(i, j, 1)); e.bind("<Down>", lambda ev=None, i=i, j=j: self._move(i, j, 1)); e.bind("<Up>", lambda ev=None, i=i, j=j: self._move(i, j, -1))
        e.bind("<Button-3>", lambda ev=None, i=i, j=j: (setattr(self, "_cell", (i, j)), self.menu.tk_popup(ev.x_root, ev.y_root)))
        e.bind("<Control-v>", lambda ev=None, i=i, j=j: (setattr(self, "_cell", (i, j)), self.paste_clipboard(), "break")[2])
        e.bind("<KeyRelease>", lambda ev=None: self._schedule())

    def _move(self, i, j, d):
        if j >= COL0: self._normalize(i, j)
        k = i + d
        if self._paged_mode and (k >= len(self.entries) or k < 0):
            self._turn_page(1 if k >= len(self.entries) else -1, j); return "break"
        if k >= len(self.entries): self._extend(5)
        if 0 <= k < len(self.entries): self.entries[k][j].focus_set(); self.entries[k][j].icursor(tk.END)
        return "break"
    def _extend(self, n):
        for _ in range(n): self._make_row(len(self.entries))

    def _write_rows(self, rows):
        for r in self.entries:
            for e in r: e.delete(0, tk.END)
        while not self._paged_mode and len(self.entries) < len(rows) + 3: self._make_row(len(self.entries))
        for i, r in enumerate(rows):
            self.entries[i][COL_NAME].insert(0, r.get("name", "")); self.entries[i][COL_REP].insert(0, r.get("rep", ""))
            for j, p in enumerate(self.phases):
                v = r.get("dates", {}).get(p["key"], "")
                if v: self.entries[i][COL0 + j].insert(0, v)

    def _write_grid(self, rows):
        """Показує рядки моделі: до PAGE_SIZE – усі; більше – поточну сторінку. Віджети перевикористовуються, якщо набір фаз не змінився."""
        ps = self.PAGE_SIZE; total = len(rows); self._total = total; self._paged_mode = total > ps
        if self._paged_mode:
            self.page = max(0, min(self.page, (total - 1) // ps)); off = self.page * ps; sl = rows[off:off + ps]; need = ps
        else: self.page = 0; off = 0; sl = rows; need = max(self.N_ROWS, len(rows) + 6)
        self._off = off; self._page_len = len(sl); sig = tuple((P.phase_label(p), p.get("hint", "")) for p in self.phases)
        reuse = bool(self.entries) and sig == self._sig and ((self._paged_mode and len(self.entries) == need) or (not self._paged_mode and len(self.entries) >= need))
        if reuse: self._write_rows(sl)
        else: self._rebuild_grid(sl, need); self._sig = sig
        self._update_pagebar()

    def _page_count(self): return max(1, (self._total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

    def _update_pagebar(self):
        if self._paged_mode:
            self.pg_lbl.configure(text=f"Рядки {self._off + 1}–{self._off + self._page_len} із {self._total} · сторінка {self.page + 1} із {self._page_count()}")
            if not self.pagebar.winfo_ismapped(): self.pagebar.pack(fill=tk.X, after=self._tb2)
        elif self.pagebar.winfo_ismapped(): self.pagebar.pack_forget()

    def goto_page(self, n):
        self._save_current(); n = max(0, min(n, self._page_count() - 1))
        if self._paged_mode: self.page = n; self._write_grid(self.years_data[self.cur_year]); self._validate_all()

    def goto_row(self, r=None):
        try: r = int(r if r is not None else self.pg_row.get())
        except (TypeError, ValueError): return
        self._save_current(); self.page = max(0, (r - 1) // self.PAGE_SIZE); self._write_grid(self.years_data[self.cur_year]); self._validate_all()
        i = (r - 1) - self._off
        if self._paged_mode and 0 <= i < len(self.entries): self.entries[i][COL_NAME].focus_set()

    def _turn_page(self, step, col):
        self._save_current(); model = self.years_data[self.cur_year]; target = self.page + step
        if target < 0: return
        if target >= self._page_count(): model.extend({"name": "", "rep": "", "dates": {}} for _ in range((-len(model)) % self.PAGE_SIZE + self.PAGE_SIZE))   # добити поточну сторінку й додати нову порожню
        self.page = target; self._write_grid(model); self._validate_all(); row = 0 if step > 0 else len(self.entries) - 1
        self.entries[row][col].focus_set()
    def _row_dict(self, r):
        return {"name": r[COL_NAME].get().strip(), "rep": r[COL_REP].get().strip(), "dates": {p["key"]: r[COL0 + j].get().strip() for j, p in enumerate(self.phases) if r[COL0 + j].get().strip()}}

    def _read_rows(self):
        rows = []
        for r in self.entries:
            d = self._row_dict(r)
            if d["name"] or d["rep"] or d["dates"]: rows.append(d)
        return rows
    def _save_current(self):
        keys = {p["key"] for p in self.phases}; model = self.years_data.get(self.cur_year, [])
        if not self._paged_mode:
            rows = self._read_rows(); prev = model                           # дані прихованих фаз (інший набір) зберігаємо
            for k, r in enumerate(rows):
                if k < len(prev):
                    vis_same = {pk: v for pk, v in prev[k].get("dates", {}).items() if pk in keys} == r["dates"]            # змінено лише назву – дані прихованих фаз зберігаємо
                    for pk, v in prev[k].get("dates", {}).items():
                        if pk not in keys and pk not in r["dates"] and (prev[k].get("name") == r["name"] or vis_same): r["dates"][pk] = v
            self.years_data[self.cur_year] = rows; self._total = len(rows); return
        off, plen = self._off, self._page_len; rows = [self._row_dict(r) for r in self.entries]
        if off + self.PAGE_SIZE >= self._total:                                # остання сторінка: хвіст із порожніх рядків відкидаємо
            while rows and not (rows[-1]["name"] or rows[-1]["rep"] or rows[-1]["dates"]): rows.pop()
        else: rows = rows[:plen]                                               # інші сторінки: позиції рядків незмінні
        prev = model[off:off + plen]
        for k, r in enumerate(rows):
            if k < len(prev):
                vis_same = {pk: v for pk, v in prev[k].get("dates", {}).items() if pk in keys} == r["dates"]
                for pk, v in prev[k].get("dates", {}).items():
                    if pk not in keys and pk not in r["dates"] and (prev[k].get("name") == r["name"] or vis_same): r["dates"][pk] = v
        merged = model[:off] + rows + model[off + plen:]
        while merged and not (merged[-1]["name"] or merged[-1]["rep"] or merged[-1]["dates"]): merged.pop()          # порожній хвіст (нова сторінка, у яку нічого не внесли) не зберігається
        self.years_data[self.cur_year] = merged; self._total = len(merged); self._page_len = len(rows)
    def _cell_color(self, e, color):
        if str(e.cget("bg")) != color: e.configure(bg=color)

    def _normalize(self, i, j):
        e = self.entries[i][j]; t = e.get().strip()
        if t:
            d, msg = P.parse_date_flex(t, self.cur_year)
            if d is not None and e.get().strip() != P.fmt_date(d): e.delete(0, tk.END); e.insert(0, P.fmt_date(d))
        self._validate_all()

    def _schedule(self):
        if self._job is not None:
            try: self.win.after_cancel(self._job)
            except Exception: pass
        self._job = self.win.after(350, self._validate_all)

    def _validate_all(self):
        self._job = None; nerr = nwarn = nfill = 0; names = set()
        if self._paged_mode: names = {r["name"] for r in self.years_data.get(self.cur_year, []) if r.get("name")}
        for r in self.entries:
            prev = None
            if r[COL_NAME].get().strip(): names.add(r[COL_NAME].get().strip())
            for j in range(self._phase_cols()):
                e = r[COL0 + j]; t = e.get().strip()
                if not t: self._cell_color(e, BG_NORM); continue
                d, msg = P.parse_date_flex(t, self.cur_year)
                if d is None: self._cell_color(e, BG_ERR); nerr += 1; continue
                nfill += 1
                if d.year != self.cur_year or (prev is not None and d < prev): self._cell_color(e, BG_WARN); nwarn += 1
                else: self._cell_color(e, BG_OK)
                prev = d
        self.status.configure(text=f"Рік {self.cur_year}: сортів {len(names)}, дат {nfill}" + (f" (на сторінці {self.page + 1})" if self._paged_mode else "") + (f", помилок {nerr}" if nerr else "") + (f", попереджень {nwarn}" if nwarn else ""), fg="#c62828" if nerr else ("#8c5a1a" if nwarn else "#555"))
        return nerr, nwarn

    # ── дії над клітинкою ──
    def _cur_entry(self):
        i, j = self._cell
        return self.entries[i][j] if i < len(self.entries) and j < len(self.entries[i]) else None

    def _cell_today(self):
        e = self._cur_entry()
        if e is not None and self._cell[1] >= COL0: e.delete(0, tk.END); e.insert(0, P.fmt_date(_dt.date.today())); self._validate_all()

    def _cell_fill_down(self):
        i, j = self._cell
        if i > 0 and j >= COL0:
            above = self.entries[i - 1][j].get().strip(); e = self.entries[i][j]
            if above: e.delete(0, tk.END); e.insert(0, above); self._validate_all()

    def _cell_clear(self):
        e = self._cur_entry()
        if e is not None: e.delete(0, tk.END); self._validate_all()

    def _cell_calendar(self):
        e = self._cur_entry(); i, j = self._cell
        if e is None or j < COL0: return
        d, _ = P.parse_date_flex(e.get(), self.cur_year)
        if d is None:                                                    # підказка: остання дата в цьому рядку або в цьому стовпці
            for jj in range(j - 1, COL0 - 1, -1):
                d, _ = P.parse_date_flex(self.entries[i][jj].get(), self.cur_year)
                if d: break
        def put(dd): e.delete(0, tk.END); e.insert(0, P.fmt_date(dd)); self._validate_all()
        DatePicker(self.win, d, put, self.cur_year)

    # ── роки ──
    def _update_years(self):
        for ch in self.years_bar.winfo_children(): ch.destroy()
        for y in sorted(self.years_data):
            cur = y == self.cur_year
            tk.Button(self.years_bar, text=str(y), font=RB if cur else RF, relief=tk.SUNKEN if cur else tk.RAISED, bg="#1a4b8c" if cur else "#e8eef7", fg="white" if cur else "black", width=6, command=lambda y=y: self.goto_year(y)).pack(side=tk.LEFT, padx=1)
        tk.Button(self.years_bar, text="＋ Рік", font=RF, command=self.add_year).pack(side=tk.LEFT, padx=(6, 1))
        tk.Button(self.years_bar, text="✖ Видалити рік", font=SM, command=self.delete_year).pack(side=tk.LEFT, padx=1)

    def goto_year(self, y):
        self._save_current(); self.cur_year = y; self.page = 0; self.years_data.setdefault(y, []); self._write_grid(self.years_data[y]); self._update_years(); self._validate_all()

    def add_year(self, year=None, copy=None):
        if year is None:
            year = simpledialog.askinteger("Новий рік", "Рік досліду:", initialvalue=(max(self.years_data) + 1 if self.years_data else _dt.date.today().year), minvalue=1900, maxvalue=2200, parent=self.win)
            if year is None: return
        if year in self.years_data: self.goto_year(year); return
        self._save_current(); prev = self.years_data.get(max(self.years_data)) if self.years_data else []
        if copy is None: copy = bool(prev) and messagebox.askyesno("Новий рік", "Скопіювати список сортів і повторностей з попереднього року (без дат)?", parent=self.win)
        self.years_data[year] = [{"name": r["name"], "rep": r["rep"], "dates": {}} for r in (prev or [])] if copy else []
        self.cur_year = year; self.page = 0; self._write_grid(self.years_data[year]); self._update_years(); self._validate_all()

    def delete_year(self):
        if len(self.years_data) <= 1: messagebox.showinfo("", "Має лишитись хоча б один рік.", parent=self.win); return
        if not messagebox.askyesno("Видалити рік", f"Видалити всі дані за {self.cur_year} рік?", parent=self.win): return
        del self.years_data[self.cur_year]; self.cur_year = max(self.years_data); self.page = 0; self._write_grid(self.years_data[self.cur_year]); self._update_years(); self._validate_all()

    # ── культура й фази ──
    def _on_preset(self, ev=None):
        key = next(k for k in P.PRESET_ORDER if P.PRESETS[k]["name"] == self.preset_var.get())
        self._save_current(); self.preset_key = key; self.phases = P.preset_phases(key); self._write_grid(self.years_data.get(self.cur_year, [])); self._validate_all()

    def edit_phases(self):
        def ok(phases):
            self._save_current(); self.phases = phases; self._write_grid(self.years_data.get(self.cur_year, [])); self._validate_all()
        PhaseEditor(self.win, self.phases, P.preset_phases(self.preset_key), ok)

    def _refresh_std(self):
        self._save_current(); names = P.cultivar_order([{"name": r["name"]} for rows in self.years_data.values() for r in rows if r["name"]])
        self.std_cb.configure(values=["(середнє за сортами)"] + names)

    # ── вставка, Excel ──
    def paste_clipboard(self):
        try: txt = self.win.clipboard_get()
        except tk.TclError: messagebox.showinfo("", "Буфер обміну порожній.", parent=self.win); return
        rows = [ln.split("\t") for ln in txt.replace("\r", "").split("\n") if ln.strip() != ""]
        if not rows: return
        i0, j0 = self._cell if self._cell else (0, 0)
        if len(rows) == 1 and len(rows[0]) == 1:
            e = self._cur_entry()
            if e is not None: e.insert(tk.INSERT, rows[0][0].strip()); self._validate_all()
            return
        self._save_current(); model = self.years_data.setdefault(self.cur_year, []); base = self._off + i0
        while len(model) < base + len(rows): model.append({"name": "", "rep": "", "dates": {}})
        for di, r in enumerate(rows):
            row = model[base + di]
            for dj, v in enumerate(r):
                j = j0 + dj; v = v.strip()
                if j == COL_NAME: row["name"] = v
                elif j == COL_REP: row["rep"] = v
                elif COL0 <= j < COL0 + len(self.phases):
                    key = self.phases[j - COL0]["key"]
                    if v:
                        d, _ = P.parse_date_flex(v, self.cur_year); row["dates"][key] = P.fmt_date(d) if d else v
                    else: row["dates"].pop(key, None)
        self._write_grid(model); self._validate_all()

    def import_excel(self, path=None):
        path = path or filedialog.askopenfilename(parent=self.win, title="Excel з датами фаз", filetypes=[("Excel", "*.xlsx *.xlsm"), ("CSV", "*.csv")])
        if not path: return
        try: rows = self._read_table_file(path)
        except Exception as e: messagebox.showerror("Excel", f"Не вдалося прочитати файл: {e}", parent=self.win); return
        res = self.load_table(rows)
        messagebox.showinfo("Excel", res, parent=self.win)

    def _read_table_file(self, path):
        if path.lower().endswith((".xlsx", ".xlsm")):
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True); ws = wb.worksheets[0]; out = []
            for r in ws.iter_rows(values_only=True):
                out.append([("" if v is None else (v.strftime("%d.%m.%Y") if isinstance(v, (_dt.datetime, _dt.date)) else str(v))) for v in r])
            return out
        import sad_weather_core as W
        h, rows = W.read_table_text(open(path, encoding="utf-8-sig", errors="replace").read()); return [h] + rows

    @staticmethod
    def _norm(s): return "".join(ch for ch in str(s).lower() if ch.isalnum())

    def load_table(self, table):
        """table: список рядків (перший – заголовки). Зіставляє стовпці з фазами за назвою або кодом BBCH. Рік – зі стовпця «Рік» або поточний."""
        if len(table) < 2: return "Файл порожній."
        head = table[0]; nh = [self._norm(h) for h in head]
        def find(*hints):
            for i, h in enumerate(nh):
                if any(h.startswith(x) for x in hints): return i
        ci_name = find("сорт", "варіант", "genotype", "cultivar", "назва"); ci_rep = find("повт", "rep"); ci_year = find("рік", "year"); ci_grp = find("груп", "group")
        if ci_name is None: ci_name = 0
        pmap = {}
        for j, h in enumerate(head):
            if j in (ci_name, ci_rep, ci_year, ci_grp): continue
            for k, p in enumerate(self.phases):
                if self._norm(P.phase_label(p)) == nh[j] or self._norm(p["name"]) == nh[j] or (p["bbch"] and f"({p['bbch']})" in str(h).replace(" ", "")) :
                    pmap[j] = p["key"]; break
        ignored = [str(head[j]) for j in range(len(head)) if j not in pmap and j not in (ci_name, ci_rep, ci_year, ci_grp) and str(head[j]).strip()]
        if not pmap: return "Жодного стовпця з датою фази не розпізнано: назви стовпців мають збігатися з назвами фаз або містити код BBCH, наприклад «Початок цвітіння (61)»."
        self._save_current(); n = 0; years_seen = set()
        for r in table[1:]:
            name = str(r[ci_name]).strip() if ci_name < len(r) else ""
            if not name: continue
            y = self.cur_year
            if ci_year is not None and ci_year < len(r) and str(r[ci_year]).strip():
                try: y = int(float(str(r[ci_year]).strip()))
                except ValueError: pass
            dates = {}
            for j, k in pmap.items():
                txt = str(r[j]).strip() if j < len(r) else ""
                if txt:
                    d_, _m = P.parse_date_flex(txt, y); dates[k] = P.fmt_date(d_) if d_ else txt          # дати нормалізуємо до дд.мм.рррр
            self.years_data.setdefault(y, []).append({"name": name, "rep": str(r[ci_rep]).strip() if ci_rep is not None and ci_rep < len(r) else "", "dates": dates}); years_seen.add(y); n += 1
            if ci_grp is not None and ci_grp < len(r) and str(r[ci_grp]).strip(): self.groups[name] = str(r[ci_grp]).strip()
        self._write_grid(self.years_data.get(self.cur_year, [])); self._update_years(); self._validate_all(); self._update_groups_label()
        return f"Прочитано рядків: {n}; років: {len(years_seen) or 1}; розпізнано фаз: {len(pmap)}." + (f"\nНе розпізнано стовпці: {', '.join(ignored)}." if ignored else "")

    def import_journal(self, years_json=None):
        """Фенофази з польового журналу схеми досліду (усі роки): сорти, повторності, дати; набір фаз – як у журналі."""
        import sad_phenology_journal as PJ
        if years_json is None:
            from sad_journal_trial import _find_scheme_folder_and_years
            found = _find_scheme_folder_and_years(self.win, title="Оберіть файл схеми або журналу будь-якого року")
            if not found: return None
            years_json = found[1]
        try: res = PJ.from_journal_years(years_json)
        except ValueError as e: messagebox.showinfo("Польовий журнал", str(e), parent=self.win); return None
        self._save_current()
        if any(r["dates"] for rows in self.years_data.values() for r in rows) and not messagebox.askyesno("Польовий журнал", "Поточні дані у вікні буде замінено даними журналу. Продовжити?", parent=self.win): return None
        self.preset_key = res["preset"] if res["preset"] in P.PRESETS else "custom"; self.preset_var.set(P.PRESETS[self.preset_key]["name"]); self.phases = res["phases"]
        self.years_data = res["years_data"] or {_dt.date.today().year: []}; self.cur_year = max(self.years_data)
        if res.get("standards"): self.standard = res["standards"][0]; self.std_var.set(self.standard)
        if res.get("groups"): self.groups = dict(res["groups"]); self.group_std = dict(res.get("group_std") or {})
        self._update_groups_label()
        self._write_grid(self.years_data[self.cur_year]); self._update_years(); self._validate_all()
        msg = (f"З журналу перенесено: років {len(res['years_data'])}, сортів {len(res['cultivars'])} (фактор «{res['factor']}»), дат фенофаз {res['n_dates']}. "
               "Кілька рослин ділянки зведено в одну дату (медіана).") + (f"\nСтандарт зі схеми: {res['standards'][0]}." if res.get("standards") else "") + \
              (f" Групи стиглості: {len(set(res['groups'].values()))}." if res.get("groups") else "") + ("\n" + "\n".join(res["notes"]) if res["notes"] else "")
        messagebox.showinfo("Польовий журнал", msg, parent=self.win); return res

    def export_excel(self, path=None):
        path = path or filedialog.asksaveasfilename(parent=self.win, defaultextension=".xlsx", initialfile="фенологія_дати.xlsx", filetypes=[("Excel", "*.xlsx")], title="Дати в Excel")
        if not path: return
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        self._save_current(); wb = Workbook(); first = True
        for y in sorted(self.years_data):
            ws = wb.active if first else wb.create_sheet(); first = False; ws.title = str(y)
            ws.append(["Сорт", "Повторність"] + [P.phase_label(p) for p in self.phases])
            for c in ws[1]: c.font = Font(bold=True); c.fill = PatternFill("solid", fgColor="D9E2F3"); c.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
            for r in P.assign_reps(self.years_data[y]):
                vals = [r["name"], r["rep"]]
                for p in self.phases:
                    d, _ = P.parse_date_flex(r["dates"].get(p["key"], ""), y); vals.append(d if d else (r["dates"].get(p["key"], "") or None))
                ws.append(vals)
                for c in ws[ws.max_row][2:]:
                    if isinstance(c.value, _dt.date): c.number_format = "DD.MM.YYYY"
            ws.column_dimensions["A"].width = 28
            for j in range(len(self.phases)): ws.column_dimensions[chr(67 + j) if j < 24 else "AA"].width = 16
            ws.freeze_panes = "C2"
        wb.save(path); return path

    def blank_form(self, path=None):
        """Порожній бланк (Word) для запису дат у полі: сорти × фази."""
        import sad_report as R
        self._save_current(); rows = P.assign_reps(self.years_data.get(self.cur_year, [])); n = max(20, len(rows))
        path = path or filedialog.asksaveasfilename(parent=self.win, defaultextension=".docx", initialfile=f"бланк_фенологія_{self.cur_year}.docx", filetypes=[("Word", "*.docx")], title="Бланк для поля")
        if not path: return
        heads = ["№", "Сорт / варіант", "Повт."] + [P.phase_label(p) for p in self.phases]; body = []
        for i in range(n):
            r = rows[i] if i < len(rows) else None; body.append([str(i + 1), r["name"] if r else "", r["rep"] if r else ""] + [""] * len(self.phases))
        items = [{"kind": "text", "text": f"Культура: {P.PRESETS[self.preset_key]['name']}     Рік: {self.cur_year}     Ділянка/поле: ______________     Спостерігач: ______________", "warn": False},
                 {"kind": "text", "text": "У клітинці записують дату настання фази (дд.мм). Початок – 10 % рослин у фазі, масова – 50 %, кінець – 90 %.", "warn": False},
                 {"kind": "table", "headers": heads, "rows": body, "fills": [None] * len(body), "widths": [28, 150, 40] + [78] * len(self.phases)}]
        scale = [[p["bbch"] or "–", p["name"], p.get("hint", "")] for p in self.phases]
        items += [{"kind": "heading", "text": "Шкала фаз і критерії настання", "level": 2},
                  {"kind": "table", "headers": ["BBCH", "Фаза", "Критерій настання"], "rows": scale, "fills": [None] * len(scale), "widths": [50, 250, 450]},
                  {"kind": "text", "text": P.SOURCE, "warn": False}]
        R.export_docx(path, items, f"Бланк фенологічних спостережень – {self.cur_year}", ""); return path

    # ── погода, візити, аналіз ──
    def open_weather(self):
        from sad_phenology_dialogs import WeatherDialog
        WeatherDialog(self.win, self)

    def open_visits(self):
        from sad_phenology_dialogs import VisitsDialog
        self._visits = VisitsDialog(self.win, self)

    def open_groups(self):
        from sad_phenology_dialogs import GroupsDialog
        self._groups_dlg = GroupsDialog(self.win, self)

    def _update_groups_label(self):
        ng = len(set(self.groups.values())); ns = len(self.group_std)
        self.groups_lbl.configure(text=(f"груп: {ng}, стандартів груп: {ns}" if ng else ""))

    def _run(self):
        self._save_current(); self._validate_all()
        try: ctx = P.analyze(self.years_data, self.phases, self.standard, self._thr(), self.series, self.sum_cfg if self.series is not None else None,
                             groups=self.groups, group_std=self.group_std)
        except ValueError as e: messagebox.showwarning("Фенологія", str(e), parent=self.win); return None
        if ctx["errors"]:
            lst = "\n".join(f"• {e['year']}, {e['name']}, {next((p['name'] for p in self.phases if p['key'] == e['phase']), e['phase'])}: «{e['text']}»" for e in ctx["errors"][:6])
            if not messagebox.askyesno("Не розпізнано дати", f"Не схоже на дату: {len(ctx['errors'])} клітинок (червоні). Вони не будуть враховані.\n\n{lst}\n\nПродовжити аналіз?", parent=self.win): return None
        if ctx["warnings"]:
            lst = "\n".join(f"• {w['year']}, {w['name']}: {w['msg']}" for w in ctx["warnings"][:6])
            if not messagebox.askyesno("Попередження", f"Знайдено підозрілих дат: {len(ctx['warnings'])} (оранжеві клітинки).\n\n{lst}\n\nПродовжити аналіз?", parent=self.win): return None
        from sad_phenology_results import PhenologyResults
        self.results_win = PhenologyResults(self.win, ctx, P.PRESETS[self.preset_key]["name"]); return ctx

    # ── проєкт ──
    def project(self):
        self._save_current()
        return {"preset": self.preset_key, "phases": self.phases, "years_data": self.years_data, "cur_year": self.cur_year, "standard": self.standard, "thr": self._thr(), "sum_cfg": self.sum_cfg,
                "groups": self.groups, "group_std": self.group_std}

    def save_project(self, path=None):
        path = path or filedialog.asksaveasfilename(parent=self.win, defaultextension=".sadph", initialfile="фенологія.sadph", filetypes=[("Проєкт фенології", "*.sadph")], title="Зберегти проєкт")
        if not path: return
        open(path, "w", encoding="utf-8").write(P.project_to_json(self.project())); self._path = path; return path

    def open_project(self, path=None):
        path = path or filedialog.askopenfilename(parent=self.win, filetypes=[("Проєкт фенології", "*.sadph")], title="Відкрити проєкт")
        if not path: return
        try: d = P.project_from_json(open(path, encoding="utf-8").read())
        except Exception as e: messagebox.showerror("Проєкт", f"Не вдалося відкрити: {e}", parent=self.win); return
        self.preset_key = d.get("preset", "custom") if d.get("preset") in P.PRESETS else "custom"; self.preset_var.set(P.PRESETS[self.preset_key]["name"])
        self.phases = d.get("phases") or P.preset_phases(self.preset_key); self.years_data = d["years_data"] or {_dt.date.today().year: []}
        self.cur_year = d.get("cur_year") if d.get("cur_year") in self.years_data else min(self.years_data); self.standard = d.get("standard", ""); self.std_var.set(self.standard)
        self.thr = float(d.get("thr", 3.0)); self.thr_var.set(str(self.thr).rstrip("0").rstrip(".")); self.sum_cfg = d.get("sum_cfg", self.sum_cfg); self._path = path
        self.groups = dict(d.get("groups") or {}); self.group_std = dict(d.get("group_std") or {}); self._update_groups_label()
        self.page = 0; self._write_grid(self.years_data[self.cur_year]); self._update_years(); self._validate_all()

    def _thr(self):
        try: return max(0.0, float(self.thr_var.get().replace(",", ".")))
        except ValueError: return 3.0

    def _show_help(self):
        win = tk.Toplevel(self.win); win.title("Довідка – Фенологічні спостереження"); win.geometry("760x700"); set_icon(win)
        txt = tk.Text(win, wrap="word", font=("Times New Roman", 11), padx=12, pady=10, relief=tk.FLAT, bg="#fafafa"); sb = ttk.Scrollbar(win, command=txt.yview); txt.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y); txt.pack(fill=tk.BOTH, expand=True); txt.insert("1.0", HELP.strip()); txt.configure(state="disabled")
