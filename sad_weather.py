# sad_weather.py – S.A.D. v2.1: модуль «Погода» (вікно)
# -*- coding: utf-8 -*-
from sad_common import *
import re, time, json, queue, threading, calendar
import datetime as _dt
import sad_weather_core as W
import sad_weather_charts as CH
import sad_weather_export as X
import sad_worldmap as WM
import sad_clip as SC
import sad_weather_indices as W_indices

HTC_BG = {"d4": "#f4b6b6", "d3": "#f8cbad", "d2": "#fce4d6", "d1": "#fff2cc",
          "ok": "#e2efda", "wet": "#ddebf7"}
RF = ("Times New Roman", 11)
RB = ("Times New Roman", 11, "bold")
HTC_METHODS = {"Декадний облік (за методичним посібником)": "decade",
               "Місячний облік (за методичним посібником)": "month",
               "Добовий (лише доби з t > 10 °C)": "daily"}



SHARED = {"series": None, "place": ""}              # остання завантажена серія – для інших модулів (фенологія: суми температур до фази)


class WeatherWindow:
    HELP_TEXT = """
МОДУЛЬ «ПОГОДА» – ІНСТРУКЦІЯ
═══════════════════════════════════════════════

ДЛЯ ЧОГО?
  Отримати метеодані для місця й періоду досліду, одразу порахувати агрокліматичні
  показники, побудувати графіки й експортувати все у вигляді, придатному для статті
  чи дисертації. Погода пояснює частину змін у показниках між роками (посуха, нестача
  тепла, заморозки).

ДЖЕРЕЛА ДАНИХ
  NASA POWER (за замовчуванням)
    Реаналіз MERRA-2, розрізнення 0,5°×0,625° (≈ 55×46 км) для метеорології, 1°×1° для
    радіації. Дані з 1981 р., для будь-якої точки світу. Безкоштовно; у публікації потрібна
    подяка NASA (її текст додається до експорту). Дані останніх 2–3 місяців – попередні,
    потім NASA їх уточнює. Дані завантажуються щоразу заново.
  Власні дані (метеостанція)
    CSV / Excel / вставка з буфера: стовпці дата, tсер, tmax, tmin, опади тощо.
    Найточніше для дисертації, якщо станція поблизу ділянки.

МІСЦЕ ДОСЛІДУ
  «🗺 Обрати на карті» відкриває вбудовану карту світу (працює без інтернету): рухайте її
  мишею, масштабуйте коліщатком чи кнопками «＋» «－», клікніть у потрібному місці –
  координати визначаться автоматично. У вікні карти є пошук за назвою міста, а також
  поля координат (градуси або ГМС) для переходу в точку.
  «🔍 Знайти за назвою»: введіть назву населеного пункту (українською чи англійською) – програма знайде його сама, у тому числі
  малі села. Сітка NASA POWER ≈ 50 км, тож точності вибору до кількох кілометрів достатньо. «✎ Ввести координати» – для тих, хто
  має точні координати ділянки.

ВАЖЛИВО ПРО ТОЧНІСТЬ
  NASA POWER – це реаналіз для комірки сітки, а не вимірювання на вашій ділянці. Опади
  згладжені, екстремуми занижені. Для дисертації бажано порівняти з найближчою станцією.

РОКИ Й СЕЗОН
  Вкажіть лише роки (від – до) і те, що порівнювати в кожному році: весь рік, вегетацію (1 квітня – 31 жовтня) або свій
  відрізок року (наприклад, 15 травня – 20 вересня). Період завантаження програма виводить сама: повні роки (щоб порахувати
  й річні показники); для поточного року дані беруться до сьогоднішнього дня. Під полями написано, що саме буде
  завантажено й порівняно. Таблиця «За роками» та відповідна діаграма порівнюють той самий відрізок у кожному році.
  Неповні роки (дані покривають відрізок частково) у порівняння не входять. Довільні відрізки між замірами –
  вкладка «Періоди».

ПОКАЗНИКИ
  САТ (сума активних температур) – сума середньодобових температур за доби, коли t > порогу
    (5, 10, 15 °C).
  СЕТ (сума ефективних температур) – сума перевищень середньодобової температури над
    біологічним мінімумом (задається вами).
  ГТК Селянінова = ΣR / (0,1·Σt), де ΣR – сума опадів, мм, Σt – сума активних температур
    вище 10 °C за той самий період.
    Облік активних температур:
      декадний / місячний – до Σt входять лише декади (місяці) із середньою t > 10 °C, опади –
        за весь період; для декади без активних температур ГТК не розраховується;
      добовий – лише доби з t > 10 °C (і опади лише цих діб).
    Шкала: < 0,4 дуже сильна посуха; 0,4–0,5 сильна; 0,6–0,7 середня; 0,8–0,9 слабка;
    1,0–1,5 достатньо волого; > 1,5 надмірно волого (за значенням, округленим до 0,1).

ВОЛОГІСТЬ ПОВІТРЯ
  NASA POWER надає відносну вологість на 2 м (RH2M, середня добова, %). У таблицях «Декади», «Місяці», «За роками» і «Періоди» (у повному вигляді
  таблиці) з'являються: середня вологість, кількість діб із вологістю ≥ 80 % (сприятлива для грибних хвороб) і ≤ 30 % (суха повітря),
  дефіцит насичення повітря VPD = e_s·(1 − RH/100), кПа (за добовими середніми: у денні години він більший). Графік «Вологість повітря й
  дефіцит насичення» – у розділі «Графіки». RH2M – модельне значення на сітці ≈ 50 км, а не вимірювання на ділянці; тривалість змочування
  листя з неї отримати не можна. У власному файлі додайте стовпець «Вологість» (%), щоб ці показники з'явились.

МІЖНАРОДНІ ПОКАЗНИКИ (вкладки «Індекси» й «SPI»)
  Назви: СЕТ у програмі = GDD (growing degree days) з порогом 10 °C; САТ – сума активних температур.
  ET₀ (еталонне випаровування) програма розраховує сама, якщо вказано місце й є добові tmax і tmin: за FAO-56 Пенман–Монтейт
  (потрібні також радіація, вітер на висоті 2 м і вологість – у NASA POWER вони є), інакше за Харгрівзом–Самані (менш точно).
  Якщо ET₀ є у ваших даних, використовується вона. ET₀ та водний баланс (опади – ET₀) з'являються в таблицях.
  Індекс сухості ЮНЕП = P/ET₀ за календарний рік: < 0,05 гіперарідний; 0,05–0,20 арідний; 0,20–0,50 напівзасушливий;
  0,50–0,65 сухий субвологий; ≥ 0,65 вологий. У таблиці «За роками» P/ET₀ наведено й для вашого вікна (це не стандартний річний показник).
  Вінклер – сума (tсер – 10 °C) за 1 квітня – 31 жовтня (на півдні 1 жовтня – 30 квітня): регіони I–V (1389, 1667, 1944, 2222 °C·діб).
  Югліна (HI) – k·Σ((tсер – 10) + (tmax – 10))/2 за 1 квітня – 30 вересня; k – за широтою (1,00 до 40°; 1,02…1,06 для 40–50°;
  понад 50° – 1,06). Класи: HI–3 (до 1500) … HI+3 (понад 3000). Індекси рахуються лише за сезони з повним покриттям даними.
  SPI – стандартизований індекс опадів для масштабів 1, 3, 6, 12 місяців: гамма-розподіл за методом максимальної правдоподібності
  окремо для кожного календарного місяця за еталонні роки (за замовчуванням 1991–2020; WMO: не менше 30 років, програма вимагає ≥ 20).
  Кнопка «Завантажити дані й обчислити SPI» бере добові опади NASA POWER за еталонні роки й ваш період (≈ 2–4 с на рік).
  Класи: ≥ 2 екстремально волого … ≤ –2 екстремально сухо. Для власних даних SPI рахується з наявного ряду (потрібні довгі спостереження).
  У Word і Excel індекси додаються таблицями з кольоровими класами; у тексті для публікації з'являється опис методів і нумерована
  література (за порядком першої появи).

ВКЛАДКИ
  Підсумок · Добові дані · Декади · Місяці · За роками (+ норма й відхилення) · Періоди
  (довільні, напр. між замірами журналу) · Індекси · SPI · Графіки · Для публікації (методика, подяка, примітки).

ТАБЛИЦІ Й КОПІЮВАННЯ
  Кнопка «Копіювати таблицю» кладе в буфер таблицю разом із сіткою: у Word і Excel (Windows)
  вона вставиться як таблиця з рамками й заливкою ГТК. В інших системах копіюється текст.

ГРАФІКИ
  Кнопка «⚙ Налаштування» відкриває розмір діаграми (см), шрифт і розміри написів, кольори
  складових (лінії, стовпчики, заливки), заголовок, сітку й положення легенди. Налаштування
  зберігаються й діють при збереженні та в Word. Діаграма показується в заданому розмірі;
  якщо вона більша за вікно, з'являються смуги прокрутки.

НОРМА Й ВІДХИЛЕННЯ
  На вкладці «За роками» вкажіть роки норми (стандарт WMO – 1991–2020) і натисніть
  «Завантажити норму»: програма порахує середнє за ці роки для вашого вікна й покаже
  відхилення кожного року. Кожен рік завантажується окремим запитом (≈ 2–4 с), тож норма
  за 30 років займає 1–2 хвилини.

ПЕРІОДИ КОРИСТУВАЧА
  Довільні відрізки (фенофази, інтервали між замірами). «З серії журналу» бере дати замірів
  і рахує погоду між ними – для пояснення динаміки повторних вимірювань.

ЕКСПОРТ
  Excel (числа лишаються числами, ГТК розфарбовано) · Word (таблиці, рисунки, методика, подяка) ·
  CSV добових даних · «погодний набір» (.sadw) для передачі в аналізи.

ПОГОДА В АНАЛІЗАХ – ЗАСТЕРЕЖЕННЯ
  Погодний показник року однаковий для всіх ділянок цього року, тож він змішується з ефектом
  «рік». Якщо дослід щороку на тих самих ділянках/деревах, спостереження залежні – ANCOVA з
  погодою некоректна (використовуйте змішаний RM і описову таблицю). Для кореляції року з
  погодою потрібно не менше ~8 років: на 3 роках зв'язок не оцінити.
"""

    # ═══════════════════════════════════════════════════════════
    def __init__(self, parent, gs=None):
        self.parent = parent
        self.win = tk.Toplevel(parent)
        self.win.title("Погода – метеодані та агрокліматичні показники")
        self.win.geometry("1340x840"); set_icon(self.win)
        self.series = None; self.rep = None; self.norm = None; self.periods = []
        self.ctx = {"place": "", "lat": None, "lon": None, "source": "nasa"}
        self._q = queue.Queue(); self._busy = False; self._alive = True
        self._fig = None; self._canvas = None
        self.chart_style = CH.load_style(); self._auto_place = ""; self.spi = None; self.auto_recompute = True; self._rc_job = None
        self._build()
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        self.win.after(150, self._poll)

    def _close(self):
        self._alive = False
        if self._rc_job is not None:
            try: self.win.after_cancel(self._rc_job)
            except Exception: pass
        try: self.win.destroy()
        except Exception: pass

    # ───────────────────────────────────────────────────────────
    # Побудова інтерфейсу
    # ───────────────────────────────────────────────────────────
    def _build(self):
        top = tk.Frame(self.win, padx=8, pady=6); top.pack(fill=tk.X)
        self.btn_fetch = tk.Button(top, text="▶ Отримати дані", bg="#c62828", fg="white",
                                   font=("Times New Roman", 13), command=self._start_fetch)
        self.btn_fetch.pack(side=tk.LEFT, padx=4)
        for txt, cmd in (("📊 Excel", self._export_xlsx), ("📄 Word", self._export_docx),
                         ("🧾 CSV добових", self._export_csv), ("📤 Погодний набір", self._export_set)):
            tk.Button(top, text=txt, font=RF, command=cmd).pack(side=tk.LEFT, padx=3)
        tk.Button(top, text="📚 Довідка", bg="#1a4b8c", fg="white", font=RF,
                  command=self._show_help).pack(side=tk.LEFT, padx=8)
        self.comma_var = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="Десяткова кома (таблиці, Word, CSV, буфер)", variable=self.comma_var,
                       font=("Times New Roman", 10), command=self._refresh_all).pack(side=tk.RIGHT, padx=6)

        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True)
        lc = tk.Frame(body, width=444); lc.pack(side=tk.LEFT, fill=tk.Y); lc.pack_propagate(False)   # ліва колонка з прокруткою
        lcv = tk.Canvas(lc, highlightthickness=0); lvs = ttk.Scrollbar(lc, orient="vertical", command=lcv.yview)
        lcv.configure(yscrollcommand=lvs.set); lvs.pack(side=tk.RIGHT, fill=tk.Y); lcv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left = tk.Frame(lcv, padx=8); lcv.create_window((0, 0), window=left, anchor="nw", width=420)
        left.bind("<Configure>", lambda e: lcv.configure(scrollregion=lcv.bbox("all")))
        def _wheel(e):
            d = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
            if lvs.get() != (0.0, 1.0): lcv.yview_scroll(d, "units")
        def _bind(_e=None):
            lcv.bind_all("<MouseWheel>", _wheel); lcv.bind_all("<Button-4>", _wheel); lcv.bind_all("<Button-5>", _wheel)
        def _unbind(_e=None):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"): lcv.unbind_all(ev)
        lc.bind("<Enter>", _bind); lc.bind("<Leave>", _unbind); self.left_canvas = lcv
        right = tk.Frame(body); right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self._build_left(left)
        self._build_tabs(right)

        self.status_var = tk.StringVar(value="Оберіть джерело, місце й період, потім «Отримати дані».")
        bar = tk.Frame(self.win, padx=8, pady=3); bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self.progress.pack(side=tk.LEFT)
        tk.Label(bar, textvariable=self.status_var, font=("Times New Roman", 10), fg="#1a4b8c",
                 anchor="w", justify="left").pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

    def _lf(self, parent, text):
        f = tk.LabelFrame(parent, text=text, font=RB, padx=6, pady=4)
        f.pack(fill=tk.X, pady=(0, 5)); return f

    WIN_MODES = {"Весь рік (1 січня – 31 грудня)": (1, 1, 12, 31), "Вегетація (1 квітня – 31 жовтня)": (4, 1, 10, 31), "Свій відрізок року…": None}
    MONTHS_GEN = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]

    def _build_left(self, left):
        # ── 1. Джерело ──
        f = self._lf(left, "1. Джерело даних")
        self._src_titles = {W.SOURCE_TITLES[k]: k for k in ("nasa", "file")}
        self.src_var = tk.StringVar(value=W.SOURCE_TITLES["nasa"])
        cb = ttk.Combobox(f, textvariable=self.src_var, values=list(self._src_titles), state="readonly", width=50)
        cb.pack(fill=tk.X); cb.bind("<<ComboboxSelected>>", lambda e: self._on_source())
        self.file_row = tk.Frame(f)
        tk.Button(self.file_row, text="📂 Відкрити файл…", font=RF, command=self._open_file).pack(side=tk.LEFT)
        tk.Button(self.file_row, text="📋 З буфера", font=RF, command=self._paste_table).pack(side=tk.LEFT, padx=4)
        self.lic_lbl = tk.Label(f, text="", font=("Times New Roman", 9), fg="#8c5a1a", justify="left", wraplength=390)
        self.lic_lbl.pack(anchor="w", pady=(4, 0))

        # ── 2. Місце ──
        f = self._lf(left, "2. Місце досліду")
        g = tk.Frame(f); g.pack(fill=tk.X)
        tk.Label(g, text="Назва:", font=RF).grid(row=0, column=0, sticky="w")
        self.place_var = tk.StringVar()
        tk.Entry(g, textvariable=self.place_var, font=RF, width=32).grid(row=0, column=1, sticky="we", pady=1, padx=(4, 0))
        g.columnconfigure(1, weight=1)
        tk.Button(f, text="🗺 Обрати на карті…", bg="#1a6b8c", fg="white", font=RF, command=self._pick_on_map).pack(anchor="w", pady=(5, 3))
        b = tk.Frame(f); b.pack(fill=tk.X, pady=(0, 2))
        tk.Button(b, text="🔍 Знайти за назвою…", font=("Times New Roman", 10), command=self._geocode_dlg).pack(side=tk.LEFT)
        tk.Button(b, text="✎ Ввести координати…", font=("Times New Roman", 10), command=self._coords_dlg).pack(side=tk.LEFT, padx=6)
        self.lat_var = tk.StringVar(); self.lon_var = tk.StringVar()
        self.coord_lbl = tk.Label(f, text="", font=("Times New Roman", 10, "bold"), justify="left", wraplength=390, anchor="w")
        self.coord_lbl.pack(anchor="w")
        tk.Label(f, text="Рухайте карту мишею, масштабуйте коліщатком і клікніть у потрібному місці: програма сама визначить координати. "
                         "Точніше місце – точніша комірка сітки.", font=("Times New Roman", 9), fg="#666", justify="left", wraplength=390).pack(anchor="w")
        self.lat_var.trace_add("write", lambda *a: self._update_coord_label()); self.lon_var.trace_add("write", lambda *a: self._update_coord_label())
        self._update_coord_label()

        # ── 3. Роки і сезон (одне введення: період завантаження програма виводить сама) ──
        f = self._lf(left, "3. Роки і сезон")
        today = _dt.date.today()
        g1 = tk.Frame(f); g1.pack(fill=tk.X)
        self.y0_var = tk.StringVar(value=str(today.year - 1)); self.y1_var = tk.StringVar(value=str(today.year - 1))
        tk.Label(g1, text="Роки: від", font=RF).grid(row=0, column=0, sticky="w")
        ey0 = tk.Entry(g1, textvariable=self.y0_var, font=RF, width=6); ey0.grid(row=0, column=1, padx=4)
        tk.Label(g1, text="до", font=RF).grid(row=0, column=2)
        ey1 = tk.Entry(g1, textvariable=self.y1_var, font=RF, width=6); ey1.grid(row=0, column=3, padx=4)
        tk.Label(f, text="Що порівнювати в кожному році:", font=RF).pack(anchor="w", pady=(6, 0))
        self.wmode_var = tk.StringVar(value=list(self.WIN_MODES)[1])
        wcb = ttk.Combobox(f, textvariable=self.wmode_var, values=list(self.WIN_MODES), state="readonly", width=44)
        wcb.pack(fill=tk.X); wcb.bind("<<ComboboxSelected>>", lambda e: self._on_win_mode()); self._wcb = wcb
        self.win_lbl = tk.Label(f, text="", font=("Times New Roman", 9), fg="#1a4b8c", justify="left", wraplength=390, anchor="w")
        self.win_lbl.pack(anchor="w", fill=tk.X, pady=(4, 0))
        self.custom_frame = tk.Frame(f)                      # показується лише для «Свій відрізок року…»
        self.wd1_var, self.wd2_var = tk.StringVar(value="1"), tk.StringVar(value="31")
        self.wm1_var, self.wm2_var = tk.StringVar(value=W.MONTHS_UA[3]), tk.StringVar(value=W.MONTHS_UA[9])
        days = [str(i) for i in range(1, 32)]
        self._win_widgets = []
        for row, (lab, dv, mv) in enumerate((("з", self.wd1_var, self.wm1_var), ("по", self.wd2_var, self.wm2_var))):
            tk.Label(self.custom_frame, text=lab, font=RF, width=3, anchor="e").grid(row=row, column=0, pady=1)
            cd = ttk.Combobox(self.custom_frame, textvariable=dv, values=days, width=4, state="readonly"); cd.grid(row=row, column=1, padx=3)
            cm = ttk.Combobox(self.custom_frame, textvariable=mv, values=W.MONTHS_UA, width=11, state="readonly"); cm.grid(row=row, column=2, padx=3)
            self._win_widgets += [cd, cm]
        for w_ in self._win_widgets: w_.bind("<<ComboboxSelected>>", lambda e: (self._update_window_preview(), self._schedule_recompute()))
        for e_ in (ey0, ey1): e_.bind("<KeyRelease>", lambda ev: (self._update_window_preview(), self._schedule_recompute()))

        # ── 4. Розрахунок ──
        f = self._lf(left, "4. Параметри розрахунку")
        g = tk.Frame(f); g.pack(fill=tk.X)
        self.base_var = tk.StringVar(value="10"); self.upper_var = tk.StringVar(value=""); self.frost_var = tk.StringVar(value="0")
        tk.Label(g, text="Біол. мінімум для СЕТ, °C:", font=RF).grid(row=0, column=0, sticky="w")
        tk.Entry(g, textvariable=self.base_var, font=RF, width=6).grid(row=0, column=1, sticky="w", padx=4)
        tk.Label(g, text="Верхня межа t для СЕТ (необов.):", font=("Times New Roman", 10)).grid(row=1, column=0, sticky="w")
        tk.Entry(g, textvariable=self.upper_var, font=RF, width=6).grid(row=1, column=1, sticky="w", padx=4)
        tk.Label(g, text="Заморозок: tmin нижче, °C:", font=RF).grid(row=2, column=0, sticky="w")
        tk.Entry(g, textvariable=self.frost_var, font=RF, width=6).grid(row=2, column=1, sticky="w", padx=4)
        tk.Label(f, text="Облік активних температур у ГТК:", font=RF).pack(anchor="w", pady=(4, 0))
        self.htc_var = tk.StringVar(value=list(HTC_METHODS)[0])
        ttk.Combobox(f, textvariable=self.htc_var, values=list(HTC_METHODS), state="readonly", width=50).pack(fill=tk.X)
        tk.Button(f, text="↻ Перерахувати з новими параметрами", font=RF, command=self._recompute).pack(anchor="w", pady=(8, 0))
        self._on_source(); self._update_window_preview()

    # ───────────────────────────────────────────────────────────
    # Місце, роки й вікно порівняння
    # ───────────────────────────────────────────────────────────
    def _update_coord_label(self):
        try: lat, lon = self._coords(False)
        except ValueError: lat = lon = "?"
        if lat is None:
            self.coord_lbl.configure(text="Місце не обрано: натисніть «Обрати на карті…» або «Знайти за назвою…».", fg="#b00020")
        elif lat == "?":
            self.coord_lbl.configure(text="Координати не розпізнано.", fg="#b00020")
        else:
            la, lo = f"{abs(lat):.4f}".replace(".", ","), f"{abs(lon):.4f}".replace(".", ",")
            self.coord_lbl.configure(text=f"Координати: {la}° {'пн.' if lat >= 0 else 'пд.'} ш., {lo}° {'сх.' if lon >= 0 else 'зх.'} д.", fg="#1a6b1a")

    def _set_point(self, lat, lon, label=""):
        self.lat_var.set(f"{lat:.4f}"); self.lon_var.set(f"{lon:.4f}")
        cur = self.place_var.get().strip()
        if label and (not cur or cur == self._auto_place):
            self.place_var.set(label); self._auto_place = label

    def _read_window(self):
        fixed = self.WIN_MODES.get(self.wmode_var.get())
        if fixed is not None: return fixed
        def month(var, what):
            try: return W.MONTHS_UA.index(var.get()) + 1
            except ValueError: raise ValueError(f"Оберіть місяць {what} відрізка.")
        def day(var, what):
            try: return int(str(var.get()).strip())
            except ValueError: raise ValueError(f"День {what} відрізка має бути цілим числом.")
        m1, d1 = month(self.wm1_var, "початку"), day(self.wd1_var, "початку")
        m2, d2 = month(self.wm2_var, "кінця"), day(self.wd2_var, "кінця")
        for m, d, what in ((m1, d1, "початку"), (m2, d2, "кінця")):
            if not (1 <= d <= calendar.monthrange(2024, m)[1]):
                raise ValueError(f"У місяці «{W.MONTHS_UA[m - 1]}» немає {d}-го числа ({what} відрізка).")
        return m1, d1, m2, d2

    def _read_years(self):
        try: y0, y1 = int(str(self.y0_var.get()).strip()), int(str(self.y1_var.get()).strip())
        except ValueError: raise ValueError("Роки мають бути цілими числами (наприклад, 2021 і 2024).")
        if y0 > y1: raise ValueError("Рік «від» більший за рік «до».")
        if y0 < 1900: raise ValueError("Рік «від» поза допустимими межами.")
        if y1 > _dt.date.today().year: raise ValueError("Рік «до» не може бути в майбутньому.")
        return y0, y1

    def _window_text(self, win):
        m1, d1, m2, d2 = win
        return f"{d1} {self.MONTHS_GEN[m1 - 1]} – {d2} {self.MONTHS_GEN[m2 - 1]}"

    def _update_window_preview(self, *_):
        """Пояснює, ЩО буде завантажено й ЩО порівняно (щоб не здогадуватися) і чи покриває це завантажений ряд."""
        if not hasattr(self, "win_lbl"): return
        try: win = self._read_window(); y0, y1 = self._read_years()
        except ValueError as e:
            self.win_lbl.configure(text=str(e), fg="#b00020"); return
        d0, d1 = self._dates(); today = _dt.date.today(); n = y1 - y0 + 1
        txt = f"Буде завантажено дані за {d0:%d.%m.%Y} – {min(d1, today):%d.%m.%Y} (повні роки" + (", поточний – до сьогоднішнього дня" if d1 > today else "") + ")."
        if win == (1, 1, 12, 31):
            txt += f"\nПорівнюватимуться повні роки: {y0}–{y1}." if n > 1 else f"\nПорівнюватиметься повний {y0} рік."
        else:
            ys = "; ".join(f"{y}: {a:%d.%m}–{b:%d.%m.%Y}" for y in range(y0, y1 + 1) for a, b in [W.window_for_year(y, *win)]) if n <= 6 else \
                f"кожен із {n} років ({y0}–{y1}), щороку відрізок {self._window_text(win)}"
            txt += f"\nУ кожному році порівнюватиметься відрізок «{self._window_text(win)}» ({ys})."
            if (win[2], win[3]) < (win[0], win[1]): txt += " Кінець відрізка припадає на наступний рік."
        color = "#1a4b8c"
        if getattr(self, "series", None) is not None:
            ok, skipped = W.year_windows(self.series, win, (y0, y1))
            okys = [y for y, *_ in ok]; sk = [y for y, *_ in skipped]
            missing = [y for y in range(y0, y1 + 1) if y not in okys and y not in sk]
            txt += f"\nУ завантаженому ряді повне покриття: {', '.join(map(str, okys)) or 'немає'}."
            if sk: txt += f" Покрито частково (не увійде): {', '.join(map(str, sk))}."
            if missing: txt += f" Немає даних: {', '.join(map(str, missing))}."
            if sk or missing: color = "#8c5a1a"
        self.win_lbl.configure(text=txt, fg=color)

    def _on_win_mode(self):
        if self.WIN_MODES.get(self.wmode_var.get()) is None: self.custom_frame.pack(fill=tk.X, pady=(4, 0), after=self._wcb)
        else: self.custom_frame.pack_forget()
        self._update_window_preview(); self._schedule_recompute()

    def _schedule_recompute(self):
        """Якщо дані вже завантажено, зміна років чи відрізка автоматично перераховує таблиці (з невеликою затримкою, щоб не
        перераховувати на кожну натиснуту клавішу). Мережа не потрібна."""
        if not self.auto_recompute or self.series is None: return
        if self._rc_job is not None:
            try: self.win.after_cancel(self._rc_job)
            except Exception: pass
        self._rc_job = self.win.after(350, self._auto_recompute)

    def _auto_recompute(self):
        self._rc_job = None
        if self._busy or self.series is None or not self.win.winfo_exists(): return
        try: self._read_settings()
        except ValueError: return                       # неповне введення (наприклад, рік ще дописується) – мовчки чекаємо
        self._recompute()

    def _pick_on_map(self):
        try: lat, lon = self._coords(False)
        except ValueError: lat = lon = None
        try:
            dlg = WM.MapPickerDialog(self.win, lat, lon, online_search=self._online_search)
        except FileNotFoundError as e:
            messagebox.showerror("Карта недоступна", f"{e}\nПокладіть файл sad_worldmap.npz поруч із програмою або скористайтесь «Знайти за назвою».", parent=self.win); return
        self._map_dlg = dlg
        res = dlg.show()
        if res: self._set_point(res["lat"], res["lon"], res["label"])

    def _coords_dlg(self):
        """Ручне введення координат (градуси 48.75 / 48,75 або ГМС 48°45'N) – для тих, хто має точні координати ділянки."""
        dlg = tk.Toplevel(self.win); dlg.title("Координати точки"); set_icon(dlg); dlg.grab_set(); dlg.resizable(False, False)
        f = tk.Frame(dlg, padx=14, pady=12); f.pack()
        lat_v, lon_v = tk.StringVar(value=self.lat_var.get()), tk.StringVar(value=self.lon_var.get())
        for r, (t, v) in enumerate((("Широта, °N:", lat_v), ("Довгота, °E:", lon_v))):
            tk.Label(f, text=t, font=RF).grid(row=r, column=0, sticky="w", pady=2)
            tk.Entry(f, textvariable=v, font=RF, width=18).grid(row=r, column=1, padx=6)
        tk.Label(f, text="Градуси (48.75 або 48,75) чи градуси-хвилини-секунди (48°45'N).\nПівдень і захід – від'ємні значення або літери S, W.",
                 font=("Times New Roman", 9), fg="#666", justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        def ok():
            try: lat = W.parse_coord(lat_v.get(), "lat"); lon = W.parse_coord(lon_v.get(), "lon")
            except Exception as e:
                messagebox.showwarning("Координати", str(e), parent=dlg); return
            self._set_point(lat, lon, ""); dlg.destroy()
        tk.Button(f, text="OK", font=RF, bg="#1a6b1a", fg="white", command=ok).grid(row=3, column=0, columnspan=2, pady=(10, 0))
        self._coords_win, self._coords_vars, self._coords_ok = dlg, (lat_v, lon_v), ok
        center_win(dlg)

    def _online_search(self, q):
        return W.geocode(q, getter=lambda u: W.http_get(u, timeout=12))

    def _geocode_dlg(self):
        dlg = tk.Toplevel(self.win); dlg.title("Пошук місця за назвою"); set_icon(dlg); dlg.grab_set(); dlg.geometry("640x380"); dlg.minsize(520, 300)
        f = tk.Frame(dlg, padx=12, pady=10); f.pack(fill=tk.BOTH, expand=True)
        tk.Label(f, text="Назва населеного пункту (українською чи англійською):", font=RF).pack(anchor="w")
        def pick(r):
            self._set_point(r["lat"], r["lon"], r["label"]); dlg.destroy()
        ps = WM.PlaceSearch(f, pick, online_search=self._online_search, width=40, lines=9)
        ps.pack(fill=tk.BOTH, expand=True); ps.qv.set(self.place_var.get().replace("м. ", "").split(",")[0])
        tk.Button(f, text="Обрати", font=RF, bg="#1a6b1a", fg="white", command=ps.pick).pack(pady=(6, 0))
        self._geo_dlg, self._geo_ps = dlg, ps
        center_win(dlg); ps.ent.focus_set()

    def _text_area(self, parent, font=("Times New Roman", 12), wrap=True, bar=None):
        """Текстове поле з вертикальною й горизонтальною прокруткою та перемикачем «Переносити рядки»."""
        if bar is None:
            bar = tk.Frame(parent); bar.pack(fill=tk.X, padx=6, pady=(2, 0))
        frm = tk.Frame(parent); frm.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        txt = tk.Text(frm, wrap="word" if wrap else "none", font=font, relief=tk.FLAT)
        vsb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview); hsb = ttk.Scrollbar(frm, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side=tk.BOTTOM, fill=tk.X); vsb.pack(side=tk.RIGHT, fill=tk.Y); txt.pack(fill=tk.BOTH, expand=True)
        var = tk.BooleanVar(value=wrap)
        tk.Checkbutton(bar, text="Переносити рядки", variable=var, font=("Times New Roman", 10),
                       command=lambda: txt.configure(wrap="word" if var.get() else "none")).pack(side=tk.RIGHT, padx=6)
        txt._wrap_var = var
        return txt

    def _build_tabs(self, right):
        self.nb = ttk.Notebook(right); self.nb.pack(fill=tk.BOTH, expand=True)
        # Підсумок
        self.tab_sum = tk.Frame(self.nb); self.nb.add(self.tab_sum, text="Підсумок")
        self.txt_sum = self._text_area(self.tab_sum, wrap=True)
        self.txt_sum.tag_configure("h", font=("Times New Roman", 14, "bold"), foreground="#1a4b8c")
        self.txt_sum.tag_configure("b", font=("Times New Roman", 12, "bold"))
        self.txt_sum.tag_configure("w", foreground="#8c5a1a")
        self.txt_sum.tag_configure("g", foreground="#666")
        self._set_text(self.txt_sum, "Дані ще не завантажено.")
        # Добові
        self.tab_day = tk.Frame(self.nb); self.nb.add(self.tab_day, text="Добові дані")
        self.day_holder = tk.Frame(self.tab_day); self.day_holder.pack(fill=tk.BOTH, expand=True)
        # Таблиці
        self.holders = {}
        for key, title in (("decades", "Декади"), ("months", "Місяці")):
            tab = tk.Frame(self.nb); self.nb.add(tab, text=title)
            bar = tk.Frame(tab, pady=4); bar.pack(fill=tk.X)
            tk.Button(bar, text="📋 Копіювати таблицю", font=RF, command=lambda k=key: self._copy_table(k)).pack(side=tk.LEFT, padx=6)
            tk.Label(bar, text="Колір ГТК: сині/зелені – достатньо чи надмірно волого; жовті/червоні – посуха. Копіюється разом із сіткою й кольорами.",
                     font=("Times New Roman", 9), fg="#666").pack(side=tk.LEFT, padx=6)
            holder = tk.Frame(tab); holder.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
            self.holders[key] = holder
        # За роками
        self.tab_years = tk.Frame(self.nb); self.nb.add(self.tab_years, text="За роками")
        bar = tk.Frame(self.tab_years, pady=4); bar.pack(fill=tk.X)
        tk.Button(bar, text="📋 Копіювати", font=RF, command=lambda: self._copy_table("years")).pack(side=tk.LEFT, padx=6)
        tk.Label(bar, text="Норма за роки:", font=RF).pack(side=tk.LEFT, padx=(14, 2))
        self.ny0 = tk.StringVar(value="1991"); self.ny1 = tk.StringVar(value="2020")
        tk.Entry(bar, textvariable=self.ny0, font=RF, width=6).pack(side=tk.LEFT)
        tk.Label(bar, text="–", font=RF).pack(side=tk.LEFT)
        tk.Entry(bar, textvariable=self.ny1, font=RF, width=6).pack(side=tk.LEFT)
        tk.Button(bar, text="⬇ Завантажити норму", font=RF, command=self._load_norm).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="✖ Прибрати норму", font=("Times New Roman", 10), command=self._clear_norm).pack(side=tk.LEFT)
        self.years_note = tk.Label(self.tab_years, text="", font=("Times New Roman", 10), fg="#8c5a1a", justify="left", wraplength=900, anchor="w")
        self.years_note.pack(fill=tk.X, padx=8)
        self.holders["years"] = tk.Frame(self.tab_years)
        self.holders["years"].pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        # Періоди
        self.tab_per = tk.Frame(self.nb); self.nb.add(self.tab_per, text="Періоди")
        bar = tk.Frame(self.tab_per, pady=4); bar.pack(fill=tk.X)
        for txt, cmd in (("➕ Додати…", self._period_add), ("🗑 Видалити", self._period_del),
                         ("📅 За датами замірів…", self._period_from_dates), ("📂 З серії журналу…", self._period_from_series),
                         ("Очистити", self._period_clear), ("📋 Копіювати", lambda: self._copy_table("periods"))):
            tk.Button(bar, text=txt, font=("Times New Roman", 10), command=cmd).pack(side=tk.LEFT, padx=3)
        lf = tk.Frame(self.tab_per); lf.pack(fill=tk.X, padx=8)
        self.per_list = tk.Listbox(lf, height=5, font=RF, exportselection=False)
        phsb = ttk.Scrollbar(lf, orient="horizontal", command=self.per_list.xview); self.per_list.configure(xscrollcommand=phsb.set)
        self.per_list.pack(fill=tk.X); phsb.pack(fill=tk.X)
        self.holders["periods"] = tk.Frame(self.tab_per)
        self.holders["periods"].pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        # Індекси: вінограрські та сухості
        self.tab_idx = tk.Frame(self.nb); self.nb.add(self.tab_idx, text="Індекси")
        bar = tk.Frame(self.tab_idx, pady=4); bar.pack(fill=tk.X)
        tk.Button(bar, text="📋 Копіювати Вінклер/Югліна", font=RF, command=lambda: self._copy_table("vine")).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="📋 Копіювати індекс сухості", font=RF, command=lambda: self._copy_table("aridity")).pack(side=tk.LEFT)
        self.idx_note = tk.Label(self.tab_idx, text="", font=("Times New Roman", 10), fg="#8c5a1a", justify="left", wraplength=900, anchor="w")
        self.idx_note.pack(fill=tk.X, padx=8)
        tk.Label(self.tab_idx, text="Вінклер і Югліна – вінограрські індекси за сезонами", font=RB, anchor="w").pack(fill=tk.X, padx=8, pady=(4, 0))
        self.holders["vine"] = tk.Frame(self.tab_idx); self.holders["vine"].pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))
        tk.Label(self.tab_idx, text="Індекс сухості ЮНЕП (P/ET₀) за календарними роками", font=RB, anchor="w").pack(fill=tk.X, padx=8)
        self.holders["aridity"] = tk.Frame(self.tab_idx); self.holders["aridity"].pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        # SPI
        self.tab_spi = tk.Frame(self.nb); self.nb.add(self.tab_spi, text="SPI")
        bar = tk.Frame(self.tab_spi, pady=4); bar.pack(fill=tk.X)
        tk.Label(bar, text="Еталонні роки:", font=RF).pack(side=tk.LEFT, padx=(6, 2))
        self.sr0 = tk.StringVar(value="1991"); self.sr1 = tk.StringVar(value="2020")
        tk.Entry(bar, textvariable=self.sr0, font=RF, width=6).pack(side=tk.LEFT); tk.Label(bar, text="–", font=RF).pack(side=tk.LEFT)
        tk.Entry(bar, textvariable=self.sr1, font=RF, width=6).pack(side=tk.LEFT)
        tk.Label(bar, text="Масштаби, міс.:", font=RF).pack(side=tk.LEFT, padx=(12, 2))
        self.spi_vars = {k: tk.BooleanVar(value=True) for k in (1, 3, 6, 12)}
        for k, v in self.spi_vars.items(): tk.Checkbutton(bar, text=str(k), variable=v, font=RF).pack(side=tk.LEFT)
        tk.Button(bar, text="⬇ Завантажити дані й обчислити SPI", font=RF, command=self._load_spi).pack(side=tk.LEFT, padx=8)
        tk.Button(bar, text="✖ Прибрати", font=("Times New Roman", 10), command=self._clear_spi).pack(side=tk.LEFT)
        tk.Button(bar, text="📋 Копіювати", font=RF, command=lambda: self._copy_table("spi")).pack(side=tk.LEFT, padx=6)
        self.spi_note = tk.Label(self.tab_spi, text="SPI – стандартизований індекс опадів (McKee та ін., 1993; WMO, 2012). Потрібен довгий ряд опадів (WMO: ≥ 30 років). Програма завантажує "
                                 "добові дані NASA POWER за еталонні роки та період дослідження (≈ 2–4 с на рік, щоразу заново) і обчислює SPI окремо для кожного календарного місяця.",
                                 font=("Times New Roman", 10), fg="#666", justify="left", wraplength=900, anchor="w")
        self.spi_note.pack(fill=tk.X, padx=8)
        self.holders["spi"] = tk.Frame(self.tab_spi); self.holders["spi"].pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        # Графіки
        self.tab_ch = tk.Frame(self.nb); self.nb.add(self.tab_ch, text="Графіки")
        bar = tk.Frame(self.tab_ch, pady=4); bar.pack(fill=tk.X)
        self._chart_titles = {t: k for k, t in CH.CHARTS}
        self.chart_var = tk.StringVar(value=CH.CHARTS[0][1])
        cc = ttk.Combobox(bar, textvariable=self.chart_var, values=[t for _, t in CH.CHARTS], state="readonly", width=48)
        cc.pack(side=tk.LEFT, padx=6); cc.bind("<<ComboboxSelected>>", lambda e: self._draw_chart())
        tk.Button(bar, text="💾 Зберегти…", font=RF, command=self._save_chart).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="📋 Копіювати", font=RF, command=self._copy_chart).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="⚙ Налаштування…", font=RF, command=self._chart_settings).pack(side=tk.LEFT, padx=3)
        host = tk.Frame(self.tab_ch); host.pack(fill=tk.BOTH, expand=True)
        self.chart_cv = tk.Canvas(host, highlightthickness=0, bg="#e6e6e6")
        cvs = ttk.Scrollbar(host, orient="vertical", command=self.chart_cv.yview); chs = ttk.Scrollbar(host, orient="horizontal", command=self.chart_cv.xview)
        self.chart_cv.configure(yscrollcommand=cvs.set, xscrollcommand=chs.set)
        chs.pack(side=tk.BOTTOM, fill=tk.X); cvs.pack(side=tk.RIGHT, fill=tk.Y); self.chart_cv.pack(fill=tk.BOTH, expand=True)
        self.chart_holder = tk.Frame(self.chart_cv, bg="#e6e6e6")
        self.chart_cv.create_window((0, 0), window=self.chart_holder, anchor="nw")
        self.chart_holder.bind("<Configure>", lambda e: self.chart_cv.configure(scrollregion=self.chart_cv.bbox("all")))
        # Для публікації
        self.tab_pub = tk.Frame(self.nb); self.nb.add(self.tab_pub, text="Для публікації")
        bar = tk.Frame(self.tab_pub, pady=4); bar.pack(fill=tk.X)
        tk.Button(bar, text="📋 Копіювати текст", font=RF, command=self._copy_pub).pack(side=tk.LEFT, padx=6)
        tk.Button(bar, text="💾 Зберегти .txt", font=RF, command=self._save_pub).pack(side=tk.LEFT)
        tk.Label(bar, text="Це чернетка для копіювання; експорт у Word формує текст заново з поточних налаштувань.",
                 font=("Times New Roman", 9), fg="#666").pack(side=tk.LEFT, padx=10)
        self.txt_pub = self._text_area(self.tab_pub, wrap=True, bar=bar)

    # ───────────────────────────────────────────────────────────
    # Допоміжні
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def _set_text(widget, text, tag=None):
        widget.configure(state="normal"); widget.delete("1.0", tk.END)
        widget.insert("1.0", text, tag) if tag else widget.insert("1.0", text)

    def _src_key(self): return self._src_titles.get(self.src_var.get(), "nasa")
    def _on_source(self):
        s = self._src_key()
        self.lic_lbl.configure(text=W.licence_notice(s) or "Власні дані: програма не змінює значення; одиниці – °C, мм, %, м/с, МДж/м².")
        if s == "file": self.file_row.pack(fill=tk.X, pady=(3, 0))
        else: self.file_row.pack_forget()
        self.btn_fetch.configure(text="▶ Отримати дані" if s != "file" else "▶ Відкрити файл…")

    def _dates(self):
        """Період завантаження: з 1 січня першого року по 31 грудня останнього (щоб порахувати й річні показники); якщо відрізок
        порівняння виходить за межі останнього року (напр., листопад – лютий), період продовжується до його кінця."""
        y0, y1 = self._read_years(); win = self._read_window()
        return _dt.date(y0, 1, 1), max(_dt.date(y1, 12, 31), W.window_for_year(y1, *win)[1])

    # ───────────────────────────────────────────────────────────
    # Налаштування й коордиати
    # ───────────────────────────────────────────────────────────
    def _read_settings(self):
        def fl(var, name):
            try: return float(str(var.get()).replace(",", "."))
            except ValueError: raise ValueError(f"«{name}»: потрібне число")
        base = fl(self.base_var, "Біологічний мінімум")
        up_txt = self.upper_var.get().strip()
        upper = fl(self.upper_var, "Верхня межа") if up_txt else None
        if upper is not None and upper <= base: raise ValueError("Верхня межа має бути вищою за біологічний мінімум.")
        frost = fl(self.frost_var, "Поріг заморозку")
        window = self._read_window(); years = self._read_years()
        st = W.default_settings()
        try: lat, lon = self._coords(False)
        except ValueError: lat = lon = None
        st.update(gdd_base=base, gdd_upper=upper, frost_thr=frost, window=window, years=years, htc_method=HTC_METHODS[self.htc_var.get()], lat=lat, lon=lon)
        return st

    def _coords(self, required):
        lt, ln = self.lat_var.get().strip(), self.lon_var.get().strip()
        if not lt and not ln:
            if required: raise ValueError("Оберіть місце досліду: натисніть «Обрати на карті…» або «Знайти за назвою…».")
            return None, None
        return W.parse_coord(lt, "lat"), W.parse_coord(ln, "lon")

    # ───────────────────────────────────────────────────────────
    # Отримання даних (фоновий потік)
    # ───────────────────────────────────────────────────────────
    def _busy_on(self, msg):
        self._busy = True; self.btn_fetch.configure(state="disabled")
        self.progress.start(12); self.status_var.set(msg)

    def _busy_off(self):
        self._busy = False; self.btn_fetch.configure(state="normal"); self.progress.stop()

    def _start_fetch(self):
        if self._busy: return
        src = self._src_key()
        if src == "file":
            self._open_file(); return
        try:
            lat, lon = self._coords(True)
            d0, d1 = self._dates()
            self._read_settings()
        except ValueError as e:
            messagebox.showwarning("Перевірте параметри", str(e), parent=self.win); return
        today = _dt.date.today()
        if d1 > today: d1 = today                        # поточний рік – до сьогоднішнього дня (без зайвих запитань)
        if d0 < W.SOURCE_MIN_DATE[src]:
            messagebox.showwarning("", f"Для цього джерела дані є з {W.SOURCE_MIN_DATE[src].year} р. Змініть рік «від».", parent=self.win); return
        if d0 > d1:
            messagebox.showwarning("", "Для обраних років ще немає даних.", parent=self.win); return
        self.ctx = {"place": self.place_var.get().strip(), "lat": lat, "lon": lon, "source": src}
        self._busy_on("Підключення до сервера…")
        threading.Thread(target=self._fetch_worker, args=(src, lat, lon, d0, d1), daemon=True).start()

    def _fetch_worker(self, src, lat, lon, d0, d1):
        prog = lambda m: self._q.put(("progress", m))
        try:
            ser = W.fetch_nasa(lat, lon, d0, d1, progress=prog)
            self._q.put(("done", (ser, d0, d1)))
        except W.WeatherError as e:
            self._q.put(("error", str(e)))
        except Exception as e:
            self._q.put(("error", f"Непередбачена помилка: {e}"))

    def _poll(self):
        if not self._alive: return
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "progress": self.status_var.set(payload)
                elif kind == "done":
                    self._busy_off(); self._on_fetched(*payload)
                elif kind == "norm":
                    self._busy_off(); self._on_norm(*payload)
                elif kind == "spi":
                    self._busy_off(); self._on_spi(*payload)
                elif kind == "error":
                    self._busy_off(); self.status_var.set("Помилка.")
                    messagebox.showerror("Помилка отримання даних", payload, parent=self.win)
        except queue.Empty:
            pass
        except Exception as e:
            self._busy_off(); self.status_var.set(f"Помилка: {e}")
        if self._alive:
            self.win.after(150, self._poll)

    def _on_fetched(self, ser, d0, d1):
        if len(ser) == 0:
            messagebox.showwarning("", "Джерело не повернуло жодної доби за цей період.", parent=self.win); return
        self.series = ser; self.norm = None; self.spi = None; SHARED.update(series=ser, place=self.place_var.get().strip())
        self.status_var.set(f"Отримано {len(ser)} діб. Дата отримання даних: {X.fmt_stamp(ser.meta.get('retrieved_at'))}")
        self._recompute(select_summary=True)
        self._update_window_preview()

    # ───────────────────────────────────────────────────────────
    # Розрахунок і оновлення вкладок
    # ───────────────────────────────────────────────────────────
    def _recompute(self, select_summary=False):
        if self.series is None:
            messagebox.showinfo("", "Спершу отримайте дані.", parent=self.win); return
        try:
            st = self._read_settings()
        except ValueError as e:
            messagebox.showwarning("Перевірте параметри", str(e), parent=self.win); return
        try:
            self.rep = W.build_report(self.series, st, norm=self.norm, periods=self.periods, spi=self.spi)
        except Exception as e:
            messagebox.showerror("Помилка розрахунку", str(e), parent=self.win); return
        self._refresh_all()
        if select_summary: self.nb.select(self.tab_sum)

    def _refresh_all(self):
        if self.rep is None: return
        self._fill_summary(); self._fill_daily()
        for key, fn in (("decades", X.spec_decades), ("months", X.spec_months)):
            self._fill_table(self.holders[key], fn(self.rep))
        if self.rep["years"]:
            self._fill_table(self.holders["years"], X.spec_years(self.rep))
        else:
            self._clear(self.holders["years"])
        note = ""
        if self.rep["years_skipped"]:
            note = ("Не включено (вікно покрито частково): " + ", ".join(str(y) for y, _, _ in self.rep["years_skipped"]) + ". ")
        if not self.rep["years"]:
            note += "Немає жодного року з повним покриттям вікна – змініть роки чи вікно порівняння в розділі 3 ліворуч або період даних."
        if self.norm: note += f"Норма: {self.norm[2]} ({len(self.norm[1])} р.)."
        self.years_note.configure(text=note)
        self.per_list.delete(0, tk.END)
        for n, a, b in self.periods: self.per_list.insert(tk.END, f"{n}:  {a:%d.%m.%Y} – {b:%d.%m.%Y}")
        if self.rep["periods"]: self._fill_table(self.holders["periods"], X.spec_periods(self.rep))
        else: self._clear(self.holders["periods"])
        self._fill_intl(); self._fill_spi()
        self._draw_chart(); self._fill_pub()

    @staticmethod
    def _clear(holder):
        for w in holder.winfo_children(): w.destroy()

    SHORT_HDR = {"tmax сер., °C": "tmax, °C", "tmin сер., °C": "tmin, °C", "Діб з опадами ≥1 мм": "Діб ≥1 мм",
                 "Умови зволоження": "Умови", "Пропуски опадів, %": "Пропуски оп., %", "Діб із заморозком": "Заморозк. діб"}

    def _fill_table(self, holder, spec):
        self._clear(holder)
        comma = self.comma_var.get()
        headers, rows, classes = X.to_strings(spec, comma, compact=False)
        headers = [self.SHORT_HDR.get(h, h) for h in headers]       # на екрані коротше; в експорті – точні назви
        frm, tv = make_tv(holder, headers, rows, min_col=40)
        tv.configure(height=6)             # мала «природна» висота: таблиця розтягується на всю вкладку, а смуги прокрутки (зокрема нижня) лишаються видимими
        frm.pack(fill=tk.BOTH, expand=True)
        fnt = tkfont.Font(family="Times New Roman", size=11)          # ущільнення: ширина за вмістом,
        for i, h in enumerate(headers):                               # остання колонка (умови) розтягується
            wmax = max([fnt.measure(h) + 16] + [fnt.measure(str(r[i])) + 14 for r in rows[:300] if i < len(r)])
            tv.column(h, width=max(44, wmax), minwidth=40, stretch=(i == len(headers) - 1))
        for k, bg in HTC_BG.items(): tv.tag_configure(k, background=bg)
        if classes:
            for iid, cls in zip(tv.get_children(), classes):
                if cls in HTC_BG: tv.item(iid, tags=(cls,))

    def _fill_daily(self):
        self._clear(self.day_holder)
        comma = self.comma_var.get()
        headers, rows, nds = X.daily_table(self.series, self.rep["settings"]["gdd_base"])
        frm = tk.Frame(self.day_holder, bd=1, relief=tk.SUNKEN); frm.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(frm, orient="vertical"); hsb = ttk.Scrollbar(frm, orient="horizontal")
        tv = ttk.Treeview(frm, columns=headers, show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.config(command=tv.yview); hsb.config(command=tv.xview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y); hsb.pack(side=tk.BOTTOM, fill=tk.X); tv.pack(fill=tk.BOTH, expand=True)
        for i, h in enumerate(headers):
            tv.heading(h, text=h); tv.column(h, width=92 if i == 0 else max(80, min(150, len(h) * 8)), anchor="center")
        for r in rows:
            vals = [f"{r[0]:%d.%m.%Y}"] + [X.fnum(v, nd, comma, dash="") for v, nd in zip(r[1:], nds[1:])]
            tv.insert("", "end", values=vals)

    def _fill_summary(self):
        rep = self.rep; ctx = self.ctx; s = self.series
        w = self.txt_sum; w.configure(state="normal"); w.delete("1.0", tk.END)
        w.insert(tk.END, f"{ctx['place'] or 'Метеодані'}\n", "h")
        for a, b in X.make_meta(rep, ctx["place"], ctx["lat"], ctx["lon"], ctx["source"]):
            w.insert(tk.END, f"{a}: ", "b"); w.insert(tk.END, f"{b}\n")
        notes = W.quality_notes(s, ctx["source"], rep["d0"], rep["d1"])
        if notes:
            w.insert(tk.END, "\nЗвернуть увагу\n", "b")
            for n in notes: w.insert(tk.END, f"• {n}\n", "w")
        w.insert(tk.END, "\nЗведені показники за весь період\n", "b")
        _, rows, _ = X.to_strings(X.spec_total(rep), self.comma_var.get())
        wd = max(len(r[0]) for r in rows)
        for a, b in rows: w.insert(tk.END, f"  {a}  –  {b}\n")
        lab, key = W.htc_class(rep["total"]["htc"])
        w.insert(tk.END, "\nШкала ГТК: ", "b"); w.insert(tk.END, W.HTC_SCALE_TEXT + "\n", "g")
        w.configure(state="disabled")

    # ───────────────────────────────────────────────────────────
    # Норма й відхилення
    # ───────────────────────────────────────────────────────────
    # ───────────────────────────────────────────────────────────
    # Міжнародні індекси й SPI
    # ───────────────────────────────────────────────────────────
    def _fill_intl(self):
        iv = self.rep["intl"]; notes = []
        if iv["lat"] is None:
            notes.append("Для вінограрських індексів і розрахунку ET₀ потрібна широта: оберіть місце досліду на карті або введіть координати, потім натисніть «Перерахувати».")
        else:
            if iv["pet_method"] in ("pm", "hs", "given"): notes.append(iv["pet_note"])
            elif iv["pet_note"]: notes.append("ET₀ не розраховано: " + iv["pet_note"])
        if iv["lat"] is not None and not iv["vine"]:
            notes.append("Вінограрські індекси не розраховано: потрібні добові дані про температуру (tmax для Югліна) за весь сезон – з 1 квітня по 31 жовтня / 30 вересня "
                         "(на південній півкулі – з 1 жовтня).")
        if not iv["aridity"] and iv["pet_method"] != "none":
            notes.append("Індекс сухості ЮНЕП визначається за повний календарний рік (з 1 січня по 31 грудня); у завантаженому періоді таких років немає. "
                         "Для вегетаційного вікна P/ET₀ наведено в таблиці «За роками».")
        notes.append("СЕТ у цій програмі відповідає GDD (growing degree days, поріг 10 °C); індекс Вінклера – це GDD за сезон. Колір класів видно в Excel, Word і при копіюванні таблиці.")
        self.idx_note.configure(text="\n".join(notes))
        for key, fn, rows in (("vine", X.spec_vine, iv["vine"]), ("aridity", X.spec_aridity, iv["aridity"])):
            if rows: self._fill_table(self.holders[key], fn(self.rep))
            else: self._clear(self.holders[key])

    def _fill_spi(self):
        sp = self.rep.get("spi")
        if sp and sp["rows"]:
            self._fill_table(self.holders["spi"], X.spec_spi(self.rep))
            ws = sp["warnings"]
            self.spi_note.configure(text=(" ".join(ws) + "\n" if ws else "") + f"Еталонний період {sp['ref'][0]}–{sp['ref'][1]}; масштаби {', '.join(str(k) for k in sp['scales'])} міс. "
                                    "Класи: ≥ 2 екстремально волого; 1,5…1,99 дуже волого; 1…1,49 помірно волого; −0,99…0,99 норма; −1…−1,49 помірно сухо; −1,5…−1,99 дуже сухо; ≤ −2 екстремально сухо.")
        else:
            self._clear(self.holders["spi"])

    def _clear_spi(self):
        self.spi = None
        if self.series is not None: self._recompute()

    def _load_spi(self):
        if self._busy: return
        if self.series is None:
            messagebox.showinfo("", "Спершу отримайте дані – вони задають період, для якого обчислюється SPI.", parent=self.win); return
        try:
            r0, r1 = int(self.sr0.get()), int(self.sr1.get())
        except ValueError:
            messagebox.showwarning("", "Еталонні роки мають бути цілими числами (наприклад, 1991 і 2020).", parent=self.win); return
        scales = [k for k, v in self.spi_vars.items() if v.get()]
        if not scales:
            messagebox.showwarning("", "Оберіть хоча б один масштаб SPI (1, 3, 6 або 12 місяців).", parent=self.win); return
        if r0 > r1 or r1 >= _dt.date.today().year:
            messagebox.showwarning("", "Еталонні роки: «від» ≤ «до», і «до» – завершений рік.", parent=self.win); return
        n = r1 - r0 + 1
        if n < 20:
            messagebox.showwarning("", f"Еталонний період із {n} років замалий: для SPI потрібно щонайменше 20 років для кожного календарного місяця (WMO рекомендує 30).", parent=self.win); return
        study = (self.series.dates[0], self.series.dates[-1]); src = self.ctx["source"]
        if src == "file":                                  # власні дані: беремо наявний ряд, без мережі
            self._on_spi(W_indices.spi_table(self.series, (r0, r1), tuple(scales), study)); return
        # ряд починаємо з року ПЕРЕД еталонним: для SPI-k перші місяці еталону потребують k − 1 попередніх місяців (до 11 для SPI-12)
        first = _dt.date(min(r0 - 1, study[0].year), 1, 1); last = min(_dt.date.today(), _dt.date(max(r1, study[1].year), 12, 31))
        n_req = last.year - first.year + 1
        if not messagebox.askyesno("Запит довгого ряду", f"Для SPI буде завантажено добові дані NASA POWER за {first.year}–{last.year}: {n_req} запитів "
                                   f"(орієнтовно {n_req * 2.5 / 60:.0f}–{n_req * 4 / 60:.0f} хв). Дані завантажуються щоразу заново. Продовжити?", parent=self.win):
            return
        self._busy_on(f"SPI: завантаження {first.year}–{last.year}…")
        threading.Thread(target=self._spi_worker, args=(self.ctx["lat"], self.ctx["lon"], first, last, (r0, r1), tuple(scales), study), daemon=True).start()

    def _spi_worker(self, lat, lon, first, last, ref, scales, study):
        prog = lambda m: self._q.put(("progress", m))
        try:
            ser = W.fetch_nasa(lat, lon, first, last, progress=prog)
            self._q.put(("spi", (W_indices.spi_table(ser, ref, scales, study),)))
        except W.WeatherError as e:
            self._q.put(("error", str(e)))
        except Exception as e:
            self._q.put(("error", f"Непередбачена помилка: {e}"))

    def _on_spi(self, spi):
        if not any(any(v == v for v in r["spi"].values()) for r in spi["rows"]):
            messagebox.showwarning("SPI не розраховано", "\n".join(spi["warnings"]) or "Для обраного періоду немає даних, з яких можна обчислити SPI.", parent=self.win)
            self.spi = None; self._recompute(); return
        self.spi = spi
        self.status_var.set(f"SPI розраховано: {len(spi['rows'])} місяців, масштаби {', '.join(str(k) for k in spi['scales'])}.")
        self._recompute(); self.nb.select(self.tab_spi)

    def _clear_norm(self):
        self.norm = None; self._recompute()

    def _load_norm(self):
        if self._busy: return
        if self.series is None:
            messagebox.showinfo("", "Спершу отримайте дані.", parent=self.win); return
        try:
            y0, y1 = int(self.ny0.get()), int(self.ny1.get())
            st = self._read_settings()
        except ValueError as e:
            messagebox.showwarning("", f"Перевірте роки норми й параметри: {e}", parent=self.win); return
        if y0 > y1 or y1 >= _dt.date.today().year:
            messagebox.showwarning("", "Роки норми: «від» ≤ «до», і «до» – завершений рік.", parent=self.win); return
        n = y1 - y0 + 1
        if n < 10 and not messagebox.askyesno(
                "Коротка норма", f"Кліматична норма зазвичай береться за 30 років (WMO: 1991–2020), а ви "
                                 f"вказали {n}. Продовжити?", parent=self.win):
            return
        src = self.ctx["source"]; kw = W.stat_kwargs(st); window = st["window"]
        if src == "file":                                  # норма з наявного ряду – без мережі
            ok = {y: sub for y, _, _, sub in W.year_windows(self.series, window)[0] if y0 <= y <= y1}
            self._on_norm(ok, y0, y1, kw); return
        if n >= 15 and not messagebox.askyesno(
                "Запит норми", f"Буде виконано {n} запитів до NASA POWER (орієнтовно {n * 2.5 / 60:.0f}–{n * 4 / 60:.0f} хв). "
                               f"Дані завантажуються щоразу заново. Продовжити?", parent=self.win):
            return
        lat, lon = self.ctx["lat"], self.ctx["lon"]
        self._busy_on(f"Норма {y0}–{y1}…")
        threading.Thread(target=self._norm_worker, args=(src, lat, lon, y0, y1, window, kw), daemon=True).start()

    def _norm_worker(self, src, lat, lon, y0, y1, window, kw):
        prog = lambda m: self._q.put(("progress", m))
        per_year = {}; today = _dt.date.today(); n = y1 - y0 + 1
        try:
            for i, y in enumerate(range(y0, y1 + 1)):
                a, b = W.window_for_year(y, *window)
                if b >= today: continue
                prog(f"Норма: {y} ({i + 1}/{n})…")
                ser = W.fetch_nasa(lat, lon, a, b, progress=prog)
                sub = ser.slice(a, b)
                if len(sub) >= 0.95 * ((b - a).days + 1): per_year[y] = sub
                time.sleep(0.5)                              # ввічлива пауза між запитами
            self._q.put(("norm", (per_year, y0, y1, kw)))
        except W.WeatherError as e:
            self._q.put(("error", str(e)))
        except Exception as e:
            self._q.put(("error", f"Непередбачена помилка: {e}"))

    def _on_norm(self, per_year, y0, y1, kw):
        if len(per_year) < 3:
            messagebox.showwarning("", f"Для норми вдалося зібрати лише {len(per_year)} повних років – замало.", parent=self.win)
            return
        nd, used = W.normal_from_years(per_year, **kw)
        self.norm = (nd, used, f"{used[0]}–{used[-1]}")
        self.status_var.set(f"Норму розраховано за {len(used)} років ({used[0]}–{used[-1]}).")
        self._recompute(); self.nb.select(self.tab_years)

    # ───────────────────────────────────────────────────────────
    # Періоди користувача
    # ───────────────────────────────────────────────────────────
    def _period_add(self):
        dlg = tk.Toplevel(self.win); dlg.title("Новий період"); set_icon(dlg); dlg.grab_set()
        f = tk.Frame(dlg, padx=14, pady=10); f.pack()
        nv, av, bv = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for r, (lbl, var) in enumerate((("Назва (напр. «цвітіння»):", nv), ("Початок:", av), ("Кінець:", bv))):
            tk.Label(f, text=lbl, font=RF).grid(row=r, column=0, sticky="w", pady=2)
            tk.Entry(f, textvariable=var, font=RF, width=22).grid(row=r, column=1, pady=2, padx=6)

        def ok():
            try:
                a, b = W.parse_date(av.get()), W.parse_date(bv.get())
                if a > b: raise ValueError("Початок пізніший за кінець.")
            except ValueError as e:
                messagebox.showwarning("", str(e), parent=dlg); return
            self.periods.append((nv.get().strip() or f"{a:%d.%m}–{b:%d.%m.%Y}", a, b))
            dlg.destroy(); self._after_periods()
        tk.Button(f, text="Додати", font=RF, bg="#1a6b1a", fg="white", command=ok).grid(row=3, column=0, columnspan=2, pady=8)
        center_win(dlg)

    def _period_del(self):
        sel = self.per_list.curselection()
        if not sel: return
        del self.periods[sel[0]]; self._after_periods()

    def _period_clear(self):
        self.periods = []; self._after_periods()

    def _after_periods(self):
        if self.series is not None: self._recompute()
        else:
            self.per_list.delete(0, tk.END)
            for n, a, b in self.periods: self.per_list.insert(tk.END, f"{n}:  {a:%d.%m.%Y} – {b:%d.%m.%Y}")

    def _period_from_dates(self, preset_dates=None, season_default=None):
        dlg = tk.Toplevel(self.win); dlg.title("Періоди за датами замірів"); set_icon(dlg); dlg.grab_set()
        f = tk.Frame(dlg, padx=14, pady=10); f.pack()
        tk.Label(f, text="Дати замірів (по одній у рядку чи через кому):", font=RF).pack(anchor="w")
        tx = tk.Text(f, width=34, height=7, font=RF); tx.pack()
        if preset_dates: tx.insert("1.0", "\n".join(d.strftime("%d.%m.%Y") for d in preset_dates))
        row = tk.Frame(f); row.pack(fill=tk.X, pady=4)
        tk.Label(row, text="Початок сезону:", font=RF).pack(side=tk.LEFT)
        sv = tk.StringVar(value=season_default or (self.series.dates[0].strftime("%d.%m.%Y") if self.series is not None else ""))
        tk.Entry(row, textvariable=sv, font=RF, width=12).pack(side=tk.LEFT, padx=6)
        mode = tk.StringVar(value="between")
        tk.Radiobutton(f, text="Між сусідніми замірами (погода, що діяла з попереднього заміру)", variable=mode,
                       value="between", font=("Times New Roman", 10)).pack(anchor="w")
        tk.Radiobutton(f, text="Нагромаджено від початку сезону до кожного заміру", variable=mode,
                       value="cumulative", font=("Times New Roman", 10)).pack(anchor="w")

        def ok():
            try:
                raw = re.split(r"[\n,;]+", tx.get("1.0", tk.END))
                dates = [W.parse_date(x) for x in raw if x.strip()]
                if not dates: raise ValueError("Вкажіть хоча б одну дату заміру.")
                start = W.parse_date(sv.get()) if sv.get().strip() else None
                new = W.intervals_from_dates(dates, start, mode.get())
                if not new: raise ValueError("Не вдалося утворити жодного періоду – вкажіть початок сезону.")
            except ValueError as e:
                messagebox.showwarning("", str(e), parent=dlg); return
            self.periods.extend(new); dlg.destroy(); self._after_periods()
            self.nb.select(self.tab_per)
        tk.Button(f, text="Створити періоди", font=RF, bg="#1a6b1a", fg="white", command=ok).pack(pady=6)
        center_win(dlg)

    def _period_from_series(self):
        try:
            from sad_journal_trial import _find_scheme_file_in_folder, pick_indicators_dialog
        except Exception as e:
            messagebox.showerror("", f"Модуль журналу недоступний: {e}", parent=self.win); return
        path = filedialog.askopenfilename(parent=self.win, filetypes=[("SAD файл", "*.sadp"), ("JSON", "*.json")],
                                          title="Оберіть файл схеми або журналу будь-якого року")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as fh: d = json.load(fh)
            if d.get("type") == "field_journal": folder = os.path.dirname(os.path.dirname(path))
            else: folder = os.path.dirname(path)
            sch = _find_scheme_file_in_folder(folder)
            series = {}
            if sch:
                with open(sch, "r", encoding="utf-8") as fh: series = json.load(fh).get("series", {})
        except Exception as e:
            messagebox.showerror("", f"Не вдалося прочитати файл: {e}", parent=self.win); return
        if not series:
            messagebox.showwarning("", "У цій схемі немає серій повторних вимірів.", parent=self.win); return
        chosen = pick_indicators_dialog(self.win, {n: {} for n in sorted(series)}, multi_select=False)
        if not chosen: return
        try: dates = [W.parse_date(r["date"]) for r in series[chosen[0]]["rounds"]]
        except Exception as e:
            messagebox.showerror("", f"Некоректні дати серії: {e}", parent=self.win); return
        self._period_from_dates(dates, season_default=None)

    # ───────────────────────────────────────────────────────────
    # Графіки
    # ───────────────────────────────────────────────────────────
    def _draw_chart(self):
        self._clear(self.chart_holder); self._fig = None; self._canvas = None
        if not HAS_MPL:
            tk.Label(self.chart_holder, text="Встановіть matplotlib: pip install matplotlib").pack(pady=30); return
        if self.rep is None:
            tk.Label(self.chart_holder, text="Спершу отримайте дані.", fg="#666", bg="#e6e6e6").pack(padx=30, pady=30); return
        kind = self._chart_titles[self.chart_var.get()]
        st = CH.Style(self.chart_style, kind)
        self._fig = Figure(figsize=st.figsize, dpi=100)
        CH.build_chart(self._fig, kind, self.rep, self.ctx["place"], self.chart_style)
        self._canvas = FigureCanvasTkAgg(self._fig, master=self.chart_holder)
        cw = self._canvas.get_tk_widget()
        wpx, hpx = (int(round(v * 100)) for v in self._fig.get_size_inches())
        cw.configure(width=wpx, height=hpx, highlightthickness=0, bd=0); cw.pack(padx=8, pady=8); self._canvas.draw_idle()
        self.chart_cv.xview_moveto(0); self.chart_cv.yview_moveto(0)

    def _save_chart(self):
        if self._fig is None:
            messagebox.showinfo("", "Спершу побудуйте діаграму.", parent=self.win); return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".png",
                                         filetypes=[("PNG", "*.png"), ("SVG", "*.svg"), ("PDF", "*.pdf")])
        if not p: return
        st = CH.Style(self.chart_style, self._chart_titles[self.chart_var.get()]); cur = self._fig.get_size_inches().copy()
        try:
            self._fig.set_size_inches(*st.figsize)                      # точний розмір із налаштувань (см), без обрізання по вмісту
            self._fig.savefig(p, dpi=st.g["dpi"])
        except Exception as e: messagebox.showerror("", str(e), parent=self.win); return
        finally:
            self._fig.set_size_inches(*cur); self._canvas.draw_idle()
        self.status_var.set(f"Діаграму збережено: {p}")

    def _chart_settings(self):
        if self.rep is None:
            messagebox.showinfo("", "Спершу отримайте дані.", parent=self.win); return
        from sad_chart_style_dlg import ChartStyleDialog
        kind = self._chart_titles[self.chart_var.get()]
        self._style_dlg = ChartStyleDialog(self.win, kind, self.chart_var.get(), self.rep, self.chart_style, self._on_style)

    def _on_style(self, st):
        self.chart_style = st; self._draw_chart()
        self.status_var.set("Налаштування діаграм застосовано й збережено.")

    def _copy_chart(self):
        if self._fig is None:
            messagebox.showinfo("", "Спершу побудуйте діаграму.", parent=self.win); return
        ok, msg = _copy_fig_to_clipboard(self._fig)
        if ok: messagebox.showinfo("", "Діаграму скопійовано.\nВставте у Word через Ctrl+V.", parent=self.win)
        else: messagebox.showwarning("", f"Помилка: {msg}", parent=self.win)

    # ───────────────────────────────────────────────────────────
    # Текст для публікації й експорт
    # ───────────────────────────────────────────────────────────
    def _pub(self):
        c = self.ctx
        return X.publication_text(self.rep, c["place"], c["lat"], c["lon"], c["source"])

    def _fill_pub(self):
        self.txt_pub.delete("1.0", tk.END); self.txt_pub.insert("1.0", self._pub())

    def _copy_pub(self):
        if self.rep is None: return
        self.win.clipboard_clear(); self.win.clipboard_append(self.txt_pub.get("1.0", tk.END))
        self.status_var.set("Текст скопійовано в буфер.")

    def _save_pub(self):
        if self.rep is None: return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".txt", filetypes=[("Текст", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as fh: fh.write(self.txt_pub.get("1.0", tk.END))

    def _copy_table(self, key):
        if self.rep is None:
            messagebox.showinfo("", "Спершу отримайте дані.", parent=self.win); return
        spec = {"decades": X.spec_decades, "months": X.spec_months, "years": X.spec_years, "periods": X.spec_periods,
                "vine": X.spec_vine, "aridity": X.spec_aridity, "spi": X.spec_spi}[key](self.rep)
        if spec["kind"] == "table" and not spec["rows"]:
            messagebox.showinfo("", "У цій таблиці немає рядків.", parent=self.win); return
        comma = self.comma_var.get()
        headers, rows, classes, cell_fills = X.to_strings_ex(spec, comma, compact=False)
        fills = [("#" + X.HTC_FILL[c] if c in X.HTC_FILL else None) for c in classes] if classes else None
        mode = SC.copy_table(self.win, headers, rows, fills, tsv=X.clipboard_text(spec, comma), cell_fills=cell_fills)
        self.status_var.set("Таблицю скопійовано разом із сіткою й кольорами – вставте у Word чи Excel (Ctrl+V)." if mode == "html" else
                            "Таблицю скопійовано як текст. Сітку таблиці в Word дає копіювання у Windows; або скористайтеся кнопкою «Word» угорі.")

    def _need(self):
        if self.rep is None:
            messagebox.showinfo("", "Спершу отримайте дані.", parent=self.win); return False
        return True

    def _default_name(self, ext):
        p = re.sub(r"[^\w\-]+", "_", (self.ctx["place"] or "погода"), flags=re.U).strip("_")[:30] or "погода"
        return f"погода_{p}_{self.rep['d0']:%Y%m%d}_{self.rep['d1']:%Y%m%d}.{ext}"

    def _export_xlsx(self):
        if not self._need(): return
        if not HAS_OPENPYXL:
            messagebox.showerror("", "Потрібен openpyxl: pip install openpyxl", parent=self.win); return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".xlsx", initialfile=self._default_name("xlsx"),
                                         filetypes=[("Excel", "*.xlsx")])
        if not p: return
        c = self.ctx
        try:
            X.export_xlsx(p, self.rep, X.make_meta(self.rep, c["place"], c["lat"], c["lon"], c["source"]), self._pub())
        except Exception as e:
            messagebox.showerror("Помилка експорту", str(e), parent=self.win); return
        self.status_var.set(f"Excel збережено: {p}")
        if messagebox.askyesno("", "Файл збережено. Відкрити?", parent=self.win): open_file_cross(p)

    def _export_docx(self):
        if not self._need(): return
        if not X._have_docx():
            messagebox.showerror("", "Для експорту у Word встановіть python-docx:\n  pip install python-docx", parent=self.win); return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".docx", initialfile=self._default_name("docx"),
                                         filetypes=[("Word", "*.docx")])
        if not p: return
        c = self.ctx; self.win.configure(cursor="watch"); self.win.update_idletasks()
        try:
            figs = []
            names = dict(CH.CHARTS)
            for kind in ("climo_decade", "walter", "htc_month", "years_cmp", "vine", "spi"):
                png = X.figure_png(self.rep, kind, c["place"], CH.build_chart, style=self.chart_style)
                if png: figs.append((names[kind], png))
            X.export_docx(p, self.rep, X.make_meta(self.rep, c["place"], c["lat"], c["lon"], c["source"]),
                          self._pub(), figs, comma=self.comma_var.get())
        except Exception as e:
            self.win.configure(cursor=""); messagebox.showerror("Помилка експорту", str(e), parent=self.win); return
        self.win.configure(cursor="")
        self.status_var.set(f"Word збережено: {p}")
        if messagebox.askyesno("", "Файл збережено. Відкрити?", parent=self.win): open_file_cross(p)

    def _export_csv(self):
        if not self._need(): return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".csv", initialfile=self._default_name("csv"),
                                         filetypes=[("CSV", "*.csv")])
        if not p: return
        comma = self.comma_var.get()
        try:
            X.export_csv_daily(p, self.series, comma=comma, sep=";" if comma else ",",
                               base=self.rep["settings"]["gdd_base"])
        except Exception as e:
            messagebox.showerror("Помилка експорту", str(e), parent=self.win); return
        self.status_var.set(f"CSV збережено: {p}")

    def _export_set(self):
        if not self._need(): return
        if not self.rep["years"]:
            messagebox.showwarning("", "Немає жодного року з повним покриттям вікна – набір порожній.\n"
                                       "Змініть вікно ММ-ДД або запросіть ширший період.", parent=self.win); return
        c = self.ctx
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".sadw", initialfile=self._default_name("sadw"),
                                         filetypes=[("Погодний набір S.A.D.", "*.sadw"), ("JSON", "*.json")])
        if not p: return
        ws = W.weather_set(self.rep, c["place"], c["lat"], c["lon"], c["source"])
        try:
            with open(p, "w", encoding="utf-8") as fh: json.dump(ws, fh, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("", str(e), parent=self.win); return
        self.status_var.set(f"Погодний набір збережено ({len(ws['years'])} р.): {p}")

    # ───────────────────────────────────────────────────────────
    # Власні дані
    # ───────────────────────────────────────────────────────────
    def _open_file(self):
        p = filedialog.askopenfilename(parent=self.win, title="Файл із добовими метеоданими",
                                       filetypes=[("Таблиці", "*.csv *.txt *.tsv *.xlsx"), ("Усі файли", "*.*")])
        if not p: return
        try:
            if p.lower().endswith(".xlsx"):
                if not HAS_OPENPYXL: raise W.WeatherError("Потрібен openpyxl: pip install openpyxl")
                wb = openpyxl.load_workbook(p, read_only=True, data_only=True); ws = wb.worksheets[0]
                rows = []
                for r in ws.iter_rows(values_only=True):
                    if r is None or all(v is None for v in r): continue
                    rows.append([(v.date().isoformat() if hasattr(v, "date") else ("" if v is None else str(v))) for v in r])
                wb.close()
                if len(rows) < 2: raise W.WeatherError("Аркуш порожній.")
                headers, data = rows[0], rows[1:]
            else:
                with open(p, "rb") as fh: raw = fh.read()
                text = None
                for enc in ("utf-8-sig", "cp1251"):
                    try: text = raw.decode(enc); break
                    except UnicodeDecodeError: continue
                headers, data = W.read_table_text(text)
        except W.WeatherError as e:
            messagebox.showerror("", str(e), parent=self.win); return
        except Exception as e:
            messagebox.showerror("Не вдалося прочитати файл", str(e), parent=self.win); return
        self._ask_mapping(headers, data, os.path.basename(p))

    def _paste_table(self):
        try: text = self.win.clipboard_get()
        except Exception:
            messagebox.showwarning("", "Буфер порожній. Скопіюйте таблицю з Excel (разом із заголовками).", parent=self.win); return
        try: headers, data = W.read_table_text(text)
        except W.WeatherError as e:
            messagebox.showwarning("", str(e), parent=self.win); return
        self._ask_mapping(headers, data, "буфер обміну")

    def _ask_mapping(self, headers, data, origin):
        dlg = tk.Toplevel(self.win); dlg.title("Відповідність стовпців"); set_icon(dlg); dlg.grab_set()
        f = tk.Frame(dlg, padx=14, pady=10); f.pack()
        tk.Label(f, text=f"Джерело: {origin}, рядків: {len(data)}.\nОдиниці: °C, мм, %, м/с, МДж/м² (програма їх не перераховує).",
                 font=("Times New Roman", 10), justify="left").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        guess = W.guess_columns(headers)
        opts = ["– немає –"] + [str(h) for h in headers]
        fields = [("date", "Дата *"), ("tmean", "Середня t, °C"), ("tmax", "Максимальна t, °C"),
                  ("tmin", "Мінімальна t, °C"), ("prec", "Опади, мм"), ("rh", "Відносна вологість, %"),
                  ("wind", "Вітер, м/с"), ("rad", "Радіація, МДж/м²")]
        vars_ = {}
        for r, (key, lbl) in enumerate(fields, start=1):
            tk.Label(f, text=lbl, font=RF).grid(row=r, column=0, sticky="w", pady=1)
            v = tk.StringVar(value=opts[guess[key] + 1] if key in guess else opts[0]); vars_[key] = v
            ttk.Combobox(f, textvariable=v, values=opts, state="readonly", width=30).grid(row=r, column=1, padx=6, pady=1)

        def ok():
            mp = {k: opts.index(v.get()) - 1 for k, v in vars_.items() if v.get() != opts[0]}
            if "date" not in mp:
                messagebox.showwarning("", "Вкажіть стовпець із датою.", parent=dlg); return
            if "tmean" not in mp and not ("tmax" in mp and "tmin" in mp):
                messagebox.showwarning("", "Потрібна середня температура або пара tmax + tmin.", parent=dlg); return
            try:
                ser = W.series_from_table(headers, data, mp, {"retrieved_at": _dt.datetime.now().replace(microsecond=0).isoformat()})
            except W.WeatherError as e:
                messagebox.showwarning("", str(e), parent=dlg); return
            dlg.destroy()
            lat = lon = None
            try: lat, lon = self._coords(False)
            except ValueError: pass
            self.ctx = {"place": self.place_var.get().strip(), "lat": lat, "lon": lon, "source": "file"}
            self.y0_var.set(str(ser.dates[0].year)); self.y1_var.set(str(ser.dates[-1].year))      # роки беремо з файлу
            msg = f"Прочитано {len(ser)} діб" + (f"; пропущено некоректних рядків: {ser.meta['bad_rows']}" if ser.meta.get("bad_rows") else "")
            self.series = ser; self.norm = None; SHARED.update(series=ser, place=self.place_var.get().strip()); self.status_var.set(msg + ".")
            self._recompute(select_summary=True)
        tk.Button(f, text="Прочитати", font=RF, bg="#1a6b1a", fg="white", command=ok).grid(
            row=len(fields) + 1, column=0, columnspan=2, pady=10)
        center_win(dlg)

    def _show_help(self):
        win = tk.Toplevel(self.win); win.title("Довідка – Погода"); win.geometry("780x720"); set_icon(win)
        frm = tk.Frame(win); frm.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        vsb = ttk.Scrollbar(frm, orient="vertical"); vsb.pack(side=tk.RIGHT, fill=tk.Y)
        txt = tk.Text(frm, wrap="word", font=("Times New Roman", 11), yscrollcommand=vsb.set, relief=tk.FLAT)
        txt.pack(fill=tk.BOTH, expand=True); vsb.config(command=txt.yview)
        txt.insert("1.0", self.HELP_TEXT); txt.configure(state="disabled")
