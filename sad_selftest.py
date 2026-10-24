# sad_selftest.py — S.A.D.: самоперевірка програми (для CI та перевірки зібраного .exe)
# -*- coding: utf-8 -*-
"""
Запуск:  SAD.exe --selftest [--selftest-out файл.log]   (або python main.py --selftest)
Перевіряє, що в зібраному пакеті є всі модулі й дані: імпорт усіх модулів, репрезентативні розрахунки (scipy, numpy),
побудова графіків (matplotlib), експорт Word/Excel, відкриття всіх вікон. Код виходу 0 — усе гаразд.
"""
import os, sys, io, tempfile, traceback, datetime as dt

MODULES = ['sad_app', 'sad_assoc_core', 'sad_assoc_sections', 'sad_breeding', 'sad_breeding_core', 'sad_breeding_ui', 'sad_breeding_win', 'sad_chart_style_dlg', 'sad_clip', 'sad_cluster_pca', 'sad_common',
           'sad_control_core', 'sad_corr_core', 'sad_corr_sections', 'sad_correlation', 'sad_descriptive_ttest', 'sad_design_core',
           'sad_design_sections', 'sad_gencorr_core', 'sad_gencorr_sections', 'sad_gxe_core', 'sad_het_ord_sections',
           'sad_heterosis_core', 'sad_homogeneous', 'sad_journal_trial', 'sad_manova', 'sad_mixed_core', 'sad_mixed_sections',
           'sad_ordinal_core', 'sad_regression', 'sad_repeated', 'sad_scheme_constructor', 'sad_selection_core',
           'sad_selection_sections', 'sad_stability_ancova', 'sad_weather', 'sad_weather_charts', 'sad_weather_core', 'sad_weather_export', 'sad_worldmap']
WINDOWS = ["CorrelationWindow", "DescriptiveWindow", "TTestWindow", "RegressionWindow", "ClusterWindow", "PCAWindow",
           "RepeatedMeasuresWindow", "MixedRepeatedWindow", "StabilityWindow", "AncovaWindow", "ManovaWindow", "FieldJournalWindow",
           "SchemeConstructorWindow", "WeatherWindow", "BreedingStabilityWindow", "GenParWindow", "CombAbilityWindow", "StressWindow",
           "PathWindow", "ControlWindow", "MixedWindow", "DesignWindow", "SelectionWindow", "HeterosisWindow", "ScoresWindow",
           "GenCorrWindow", "AssocWindow"]


class _Log:
    def __init__(self, path):
        self.path = path; self.lines = []; self.fail = 0
    def ok(self, msg): self._add("OK   ", msg)
    def bad(self, msg, exc=None):
        self.fail += 1
        self._add("ПРОВАЛ", msg + (f": {type(exc).__name__}: {exc}" if exc else ""))
        if exc: self.lines.append("".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-1500:])
    def _add(self, tag, msg):
        line = f"[{tag}] {msg}"; self.lines.append(line)
        try: print(line, flush=True)
        except Exception: pass
    def flush(self):
        if not self.path: return
        try:
            with open(self.path, "w", encoding="utf-8") as f: f.write("\n".join(self.lines) + "\n")
        except Exception: pass


def _check(log, name, fn):
    try:
        fn(); log.ok(name)
    except Exception as e:
        log.bad(name, e)


def run(main_module, out_path=None):
    log = _Log(out_path)
    log.lines.append(f"S.A.D. самоперевірка · {dt.datetime.now():%Y-%m-%d %H:%M:%S} · Python {sys.version.split()[0]} · "
                     f"{'зібрана програма' if getattr(sys, 'frozen', False) else 'вихідний код'}")
    import importlib
    # 1. імпорт усіх модулів
    for name in MODULES:
        _check(log, f"імпорт {name}", lambda n=name: importlib.import_module(n))
    # 2. розрахунки
    import numpy as np
    def t_control():
        import sad_control_core as C
        r = C.compare_to_control(["St"] * 4 + ["A"] * 4 + ["B"] * 4 + ["D"] * 4, np.r_[np.arange(4), np.arange(4) + 2, np.arange(4) + .5, np.arange(4) - 3.] + np.tile([.1, -.2, .3, 0], 4), "St")
        assert len(r["rows"]) == 3 and 0 <= r["rows"][0]["p_dunnett"] <= 1
    def t_mixed():
        import sad_mixed_core as M
        rg = np.random.default_rng(1); g = [f"G{i % 8}" for i in range(40)]; y = rg.normal(size=40) + np.array([int(x[1:]) for x in g]) * .3
        r = M.fit_mixed(y, {"gen": g}, [], ["gen"]); assert r["sigma2"]["gen"] >= 0
    def t_gxe():
        import sad_gxe_core as G
        rg = np.random.default_rng(2); X = 5 + rg.normal(size=(6, 1)) + rg.normal(size=(1, 5)) + rg.normal(0, .3, (6, 5))
        G.stability_indices(X); G.ammi(X); gg = G.gge(X); G.which_won_where(gg); G.aec_mean_stability(gg)
    def t_breeding():
        import sad_breeding_core as B
        rg = np.random.default_rng(3); gen = [f"G{i}" for i in range(6) for _ in range(3)]; rep = [f"R{k}" for _ in range(6) for k in range(3)]
        B.genetic_parameters_single(gen, rep, rg.normal(size=18) + np.repeat(np.arange(6), 3) * .5)
    def t_corr():
        import sad_corr_core as C
        rg = np.random.default_rng(4); a = [rg.normal(size=25) for _ in range(4)]
        C.correlation_matrix(a, list("ABCD"), "kendall"); C.partial_matrix(a, list("ABCD"), [3], [0, 1, 2])
    def t_gencorr():
        import sad_gencorr_core as G
        rg = np.random.default_rng(5); g = 12; ge = rg.normal(size=(g, 2)); gen, rep, Y = [], [], []
        for i in range(g):
            for j in range(3): gen.append(f"G{i}"); rep.append(f"R{j}"); Y.append(ge[i] + rg.normal(0, .8, 2))
        G.genotypic_correlations(gen, rep, np.array(Y), ["x", "y"], n_boot=30)
    def t_assoc():
        import sad_assoc_core as AC
        rg = np.random.default_rng(9)
        AC.eta_squared([rg.normal(m, 1, 8) for m in (0, 1, 2)]); AC.two_group_effects(rg.normal(0, 1, 12), rg.normal(.5, 1, 12), n_boot=50)
        AC.contingency_analysis([[12, 5, 3], [4, 9, 8]], n_boot=50, n_mc=500)
    def t_worldmap():
        import sad_worldmap as WM
        D = WM.MapData.get()
        assert len(D.pop) > 7000 and D.country_at(30.2109, 48.7543) == "Україна"
        n = D.nearest(30.2109, 48.7543); assert n and "Умань" in D.full_label(n[0])
        assert D.search("умань") and D.search("kyiv")
        poly = WM.clip_polygon([-1e6, 1e6, 1e6, -1e6], [-1e6, -1e6, 1e6, 1e6], 0, 0, 100, 80); assert len(poly) == 4
    def t_clip():
        import sad_clip as SC
        h = SC.build_html_table(["А", "Б"], [["1", "2"]]); hd, frag = SC.parse_cf_html(SC.cf_html(h)); assert frag == h and 'border="1"' in h
    def t_chart_style():
        import matplotlib; from matplotlib.figure import Figure
        import sad_weather_core as W, sad_weather_charts as CH
        s0 = dt.date(2022, 1, 1); n = 730; rg = np.random.default_rng(10); dts = [s0 + dt.timedelta(days=i) for i in range(n)]
        t = 9 + 11 * np.sin(2 * np.pi * np.array([d.timetuple().tm_yday for d in dts]) / 365)
        rep = W.build_report(W.DailySeries(dts, {"tmean": t, "tmax": t + 4, "tmin": t - 4, "prec": rg.random(n) * 5}), W.default_settings())
        for kind, _ in CH.CHARTS:
            f = Figure(); assert CH.build_chart(f, kind, rep, "Тест", {"general": {"width_cm": 18, "font_family": "DejaVu Sans"}, "colors": {kind: {}}}) is None, kind
    def t_scipy_misc():
        from scipy import stats, optimize, sparse, special, spatial
        from scipy.sparse.linalg import splu
        stats.t.sf(2, 10); special.roots_genlaguerre(10, 1.0); spatial.ConvexHull(np.random.default_rng(6).normal(size=(10, 2)))
        splu(sparse.eye(5, format="csc")); optimize.brentq(lambda x: x - 1, 0, 3)
    for n, f in (("розрахунок: тест Дуннетта", t_control), ("розрахунок: змішана модель REML", t_mixed), ("розрахунок: AMMI/GGE/стабільність", t_gxe),
                 ("розрахунок: генетичні параметри", t_breeding), ("розрахунок: кореляції (Кендалл, частинна)", t_corr),
                 ("розрахунок: генотипні кореляції", t_gencorr), ("розрахунок: η, бісеріальні, спряженість", t_assoc), ("scipy: stats/special/sparse/spatial/optimize", t_scipy_misc),
                 ("карта світу: дані, країна, найближче місто, пошук, відсікання", t_worldmap), ("копіювання таблиці: HTML-формат буфера", t_clip),
                 ("діаграми: усі 8 зі стилем користувача", t_chart_style)):
        _check(log, n, f)
    # 3. matplotlib і експорт
    def t_figs():
        import matplotlib; from matplotlib.figure import Figure
        f = Figure(figsize=(4, 3)); ax = f.add_subplot(111); ax.plot([1, 2, 3], label="Тест"); ax.set_title("Кирилиця: ГТК, σ², ρ"); ax.legend()
        b = io.BytesIO(); f.savefig(b, format="png", dpi=100); assert b.getvalue()[:4] == b"\x89PNG"
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa
    def t_export():
        import sad_breeding_ui as U, sad_corr_sections as CS
        rg = np.random.default_rng(7); arr = [rg.normal(size=40) + 0 for _ in range(4)]
        S, w, M = CS.sections_partial(arr, list("ABCD"), [3], [0, 1, 2])
        d = tempfile.mkdtemp()
        U.export_xlsx(os.path.join(d, "t.xlsx"), S, "Тест"); U.export_docx(os.path.join(d, "t.docx"), "Тест", S, True)
        assert os.path.getsize(os.path.join(d, "t.docx")) > 5000 and os.path.getsize(os.path.join(d, "t.xlsx")) > 2000
    def t_weather():
        import sad_weather_core as W, sad_weather_export as X, sad_weather_charts as CH
        s0 = dt.date(2023, 1, 1); n = 730; rg = np.random.default_rng(8); dts = [s0 + dt.timedelta(days=i) for i in range(n)]
        doy = np.array([d.timetuple().tm_yday for d in dts], float); t = 9 + 11 * np.sin(2 * np.pi * (doy - 110) / 365)
        ser = W.DailySeries(dts, {"tmean": t, "tmax": t + 4, "tmin": t - 4, "prec": np.where(rg.random(n) < .3, 5., 0.)})
        ser.meta.update({"retrieved_at": "2026-01-01T12:00:00"})
        rep = W.build_report(ser, W.default_settings())
        png = X.figure_png(rep, "walter", "Тест", CH.build_chart, dpi=80); assert png
        d = tempfile.mkdtemp(); meta = X.make_meta(rep, "Тест", 48.7, 30.2, "nasa")
        pub = X.publication_text(rep, "Тест", 48.7, 30.2, "nasa")
        X.export_xlsx(os.path.join(d, "w.xlsx"), rep, meta, pub); X.export_docx(os.path.join(d, "w.docx"), rep, meta, pub, [("Діаграма", png)])
    for n, f in (("matplotlib: PNG, кирилиця, TkAgg", t_figs), ("експорт Word і Excel (частинна кореляція)", t_export), ("погода: звіт, діаграма, Word, Excel", t_weather)):
        _check(log, n, f)
    # 4. вікна
    try:
        import tkinter as tk
        from tkinter import messagebox
        for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda *a, **k: None)
        messagebox.askyesno = lambda *a, **k: False
        root = tk.Tk(); root.withdraw()
        try:
            app = main_module.SADTk(root); root._sad_app = app; log.ok("головне вікно SADTk створено")
        except Exception as e:
            log.bad("головне вікно SADTk", e)
        for name in WINDOWS:
            cls = getattr(main_module, name, None)
            if cls is None: log.bad(f"вікно {name}: клас не знайдено в main"); continue
            try:
                try: w = cls(root, {})
                except TypeError: w = cls(root)
                root.update()
                try: w.win.destroy()
                except Exception: pass
                log.ok(f"вікно {name}")
            except Exception as e:
                log.bad(f"вікно {name}", e)
        try:
            import sad_worldmap as WM
            mp = WM.WorldMap(root, width=700, height=450); mp.size = lambda: (700, 450)       # головне вікно приховане – розмір задаємо явно
            mp.goto(30.2, 48.75, 7.0); assert mp.stats["items"] > 20, mp.stats
            mp.goto(31, 49, 5.5); assert mp.stats["items"] > 100, mp.stats; mp.destroy(); log.ok("віджет карти: малювання")
        except Exception as e:
            log.bad("віджет карти: малювання", e)
        try: root.destroy()
        except Exception: pass
    except Exception as e:
        log.bad("tkinter: створення вікон", e)
    log.lines.append(f"ПІДСУМОК: {'УСЕ ГАРАЗД' if log.fail == 0 else str(log.fail) + ' ПРОВАЛ(ИВ)'}")
    try: print(log.lines[-1], flush=True)
    except Exception: pass
    log.flush()
    return 0 if log.fail == 0 else 1
