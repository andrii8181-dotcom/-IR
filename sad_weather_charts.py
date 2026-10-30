# sad_weather_charts.py – S.A.D. v2.1: графіки модуля «Погода» (лише matplotlib) зі стилем користувача
# -*- coding: utf-8 -*-
import os, json, math
import numpy as np
import matplotlib
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import sad_weather_core as W

CHARTS = [
    ("climo_daily", "Кліматограма (добова)"),
    ("climo_decade", "Температура й опади за декадами"),
    ("walter", "Діаграма Вальтера"),
    ("cum_prec", "Нагромаджені опади (за роками)"),
    ("cum_set", "Нагромаджена сума ефективних температур (за роками)"),
    ("htc_decade", "ГТК за декадами"),
    ("htc_month", "ГТК за місяцями"),
    ("humidity", "Вологість повітря й дефіцит насичення (за місяцями)"),
    ("years_cmp", "Порівняння років (температура й опади у вікні)"),
    ("vine", "Вінклер і Югліна за сезонами"),
    ("spi", "SPI за місяцями"),
]

HTC_COLORS = {"d4": "#a50f15", "d3": "#de2d26", "d2": "#fb6a4a", "d1": "#fcae91",
              "ok": "#74c476", "wet": "#2171b5", "na": "#bdbdbd"}
HTC_NAMES = {"d4": "дуже сильна посуха", "d3": "сильна посуха", "d2": "середня посуха",
             "d1": "слабка посуха", "ok": "достатньо волого", "wet": "надмірно волого"}
# Межі класів на неперервній шкалі (клас визначається за ГТК, округленим до 0,1)
HTC_BOUNDS = [0.35, 0.55, 0.75, 0.95, 1.55]
TAB = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
       "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

# ───────────────────────────────────────────────────────────
# Стиль користувача
# ───────────────────────────────────────────────────────────
DEFAULT_GENERAL = {"width_cm": 24.0, "height_cm": 14.0, "font_family": "Times New Roman", "font_size": 10.0,
                   "title_size": 11.0, "label_size": 10.0, "tick_size": 9.0, "legend_size": 9.0, "title_bold": False,
                   "show_subtitle": True, "grid": False, "legend_loc": "авто", "line_width": 1.6, "marker_size": 5.0, "dpi": 300}
LEGEND_LOCS = {"авто": None, "угорі ліворуч": "upper left", "угорі праворуч": "upper right", "внизу ліворуч": "lower left",
               "внизу праворуч": "lower right", "праворуч по центру": "center right", "під графіком": "below", "без легенди": "none"}
SERIF = {"Times New Roman", "Georgia", "Cambria", "Palatino Linotype", "Book Antiqua", "DejaVu Serif", "Garamond", "Century"}
GENERAL_LIMITS = {"width_cm": (8, 60), "height_cm": (6, 45), "font_size": (5, 30), "title_size": (5, 36), "label_size": (5, 30),
                  "tick_size": (4, 28), "legend_size": (4, 28), "line_width": (0.3, 8), "marker_size": (1, 20), "dpi": (72, 600)}


def style_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "SAD", "weather_chart_style.json")


def load_style(path=None):
    """Збережені налаштування діаграм або {} (помилки читання ігноруються: це лише зручність)."""
    try:
        with open(path or style_path(), "r", encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_style(data, path=None):
    p = path or style_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def sanitize_general(g):
    """Приводить значення до допустимих меж і типів (щоб помилковий ввід не ламав діаграму)."""
    out = dict(DEFAULT_GENERAL)
    for k, v in (g or {}).items():
        if k not in DEFAULT_GENERAL: continue
        d = DEFAULT_GENERAL[k]
        try:
            if isinstance(d, bool): out[k] = bool(v)
            elif isinstance(d, float):
                lo, hi = GENERAL_LIMITS.get(k, (-1e9, 1e9)); out[k] = min(max(float(v), lo), hi)
            elif isinstance(d, int) and not isinstance(d, bool):
                lo, hi = GENERAL_LIMITS.get(k, (-1e9, 1e9)); out[k] = int(min(max(float(v), lo), hi))
            else: out[k] = str(v)
        except (TypeError, ValueError):
            pass
    if out["legend_loc"] not in LEGEND_LOCS: out["legend_loc"] = "авто"
    return out


class Style:
    """Розв'язаний стиль однієї діаграми: загальні параметри + кольори й заголовок саме цього виду."""
    def __init__(self, data=None, kind=None):
        data = data or {}
        self.g = sanitize_general(data.get("general"))
        cols = (data.get("colors") or {}).get(kind) or {}
        self.colors = {k: v for k, v in cols.items() if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7)}
        self.title_text = str((data.get("titles") or {}).get(kind) or "").strip()

    def col(self, key, default): return self.colors.get(key) or default
    @property
    def figsize(self): return (self.g["width_cm"] / 2.54, self.g["height_cm"] / 2.54)


def components(kind, rep=None):
    """Складові діаграми, кольори яких можна змінювати: [(ключ, підпис, колір за замовчуванням)]."""
    if kind == "climo_daily":
        return [("range", "Розмах tmin–tmax (заливка)", "#f4a582"), ("tmean", "Середня температура (лінія)", "#b2182b"),
                ("prec", "Опади (стовпчики)", "#2171b5")]
    if kind == "climo_decade":
        return [("tmean", "Середня температура (крива)", "#b2182b"), ("prec", "Опади (стовпчики)", "#2171b5")]
    if kind == "walter":
        return [("temp", "Температура (лінія)", "#b2182b"), ("prec", "Опади (лінія, шкала 2:1)", "#08519c"),
                ("wet", "Вологий період (заливка)", "#6baed6"), ("dry", "Посушливий період (заливка)", "#fdae6b")]
    if kind in ("cum_prec", "cum_set"):
        yrs = sorted({d.year for d in rep["series"].dates}) if rep else []
        return [(f"y{y}", f"{y} р.", TAB[i % 10]) for i, y in enumerate(yrs)]
    if kind in ("htc_decade", "htc_month"):
        return [(c, HTC_NAMES[c], HTC_COLORS[c]) for c in ("d4", "d3", "d2", "d1", "ok", "wet")] + [("na", "немає даних", HTC_COLORS["na"])]
    if kind == "humidity":
        return [("rh", "Середня вологість (стовпчики)", "#6baed6"), ("vpd", "Дефіцит насичення VPD (лінія)", "#d94801"),
                ("hi", f"Діб з вологістю ≥ {W.RH_HI:g} %", "#2166ac"), ("lo", f"Діб з вологістю ≤ {W.RH_LO:g} %", "#e08214"), ("thr", "Пороги вологості (пунктир)", "#777777")]
    if kind == "years_cmp":
        return [("temp", "Температура (точки)", "#b2182b"), ("stem", "Температура (стебла)", "#f4a582"),
                ("prec", "Опади (стовпчики)", "#4393c3"), ("norm", "Норма (пунктир)", "#333333")]
    if kind == "vine":
        return [("winkler", "Індекс Вінклера (стовпчики)", "#d98c3f"), ("huglin", "Індекс Югліна (стовпчики)", "#8c4f9e"),
                ("bounds", "Межі класів (пунктир)", "#666666")]
    if kind == "spi":
        return [("wet", "Вологі місяці (SPI > 0)", "#2166ac"), ("dry", "Сухі місяці (SPI < 0)", "#b2182b"), ("lim", "Межі класів ±1, ±2 (пунктир)", "#777777")]
    return []


def _rc(st):
    fam = st.g["font_family"]
    fallback = "DejaVu Serif" if fam in SERIF else "DejaVu Sans"
    return {"font.family": [fam, fallback], "font.size": st.g["font_size"], "axes.titlesize": st.g["title_size"],
            "axes.labelsize": st.g["label_size"], "xtick.labelsize": st.g["tick_size"], "ytick.labelsize": st.g["tick_size"],
            "legend.fontsize": st.g["legend_size"], "axes.titleweight": "bold" if st.g["title_bold"] else "normal",
            "axes.grid": bool(st.g["grid"]), "grid.alpha": 0.35, "grid.linestyle": ":",
            "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8, "axes.unicode_minus": False}


def _message(fig, text):
    fig.clear()
    ax = fig.add_subplot(111); ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", wrap=True, fontsize=11, color="#555")


def _head(rep, place, what):
    sub = f"{place + ', ' if place else ''}{rep['d0']:%d.%m.%Y}–{rep['d1']:%d.%m.%Y}"
    return f"{what}\n{sub}"


def _title(ax, st, rep, place, what, sub_override=None):
    first = st.title_text or what
    sub = sub_override if sub_override is not None else f"{place + ', ' if place else ''}{rep['d0']:%d.%m.%Y}–{rep['d1']:%d.%m.%Y}"
    ax.set_title(first + (f"\n{sub}" if (st.g["show_subtitle"] and sub) else ""), loc="left")


def _headroom(ax, st, frac=0.24):
    """Запас по висоті над даними, щоб легенда всередині діаграми не накладалася на криві (не потрібен, якщо легенди немає чи вона під графіком)."""
    if LEGEND_LOCS[st.g["legend_loc"]] in ("none", "below"): return
    lo, hi = ax.get_ylim(); ax.set_ylim(lo, hi + (hi - lo) * frac)


def _legend(ax, st, handles=None, labels=None, default_loc="upper left", ncol=1):
    """Легенда з урахуванням налаштувань користувача (положення, відсутність, під графіком)."""
    choice = LEGEND_LOCS[st.g["legend_loc"]]
    if choice == "none": return None
    kw = {"frameon": False, "ncol": ncol}
    if choice == "below": kw.update(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=max(ncol, 2))
    else: kw["loc"] = choice or default_loc
    if handles is not None: return ax.legend(handles=handles, **kw)
    return ax.legend(**kw)


def build_chart(fig, kind, rep, place="", style=None):
    """Малює діаграму kind у fig зі стилем користувача. Повертає None при успіху, інакше – текст причини."""
    st = Style(style, kind)
    fig.set_size_inches(*st.figsize, forward=True)
    with matplotlib.rc_context(_rc(st)):
        fig.clear()
        fn = {"climo_daily": _climo_daily, "climo_decade": _climo_decade, "walter": _walter,
              "cum_prec": _cum_prec, "cum_set": _cum_set, "htc_decade": _htc_decade,
              "htc_month": _htc_month, "humidity": _humidity, "years_cmp": _years_cmp, "vine": _vine, "spi": _spi}.get(kind)
        if fn is None:
            return "Невідомий тип діаграми."
        try:
            res = fn(fig, rep, place, st)
        except Exception as e:                       # діаграма не повинна валити вікно
            res = f"Не вдалося побудувати діаграму: {e}"
        if res:
            _message(fig, res)
        return res


# ───────────────────────────────────────────────────────────
def _climo_daily(fig, rep, place, st):
    s = rep["series"]
    if not s.has("tmean") and not s.has("tmax"):
        return "Немає даних про температуру."
    ax = fig.add_subplot(111)
    x = mdates.date2num(s.dates); lw = st.g["line_width"]
    c_rng, c_t, c_p = st.col("range", "#f4a582"), st.col("tmean", "#b2182b"), st.col("prec", "#2171b5")
    handles = []
    if s.has("tmax") and s.has("tmin"):
        ax.fill_between(x, s.get("tmin"), s.get("tmax"), color=c_rng, alpha=0.35, lw=0)
        handles.append(Patch(facecolor=c_rng, alpha=0.35, label="Розмах tmin–tmax (заливка)"))
    ax.plot(x, s.get("tmean"), color=c_t, lw=lw * 0.7)
    handles.append(Line2D([0], [0], color=c_t, lw=lw, label="Середня температура, °C (лінія, ліва вісь)"))
    ax.axhline(0, color="#777", lw=0.7, ls="--")
    ax.set_ylabel("Температура повітря, °C")
    _headroom(ax, st, 0.34)
    ax.xaxis_date()
    loc = mdates.AutoDateLocator(); ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    if s.has("prec"):
        ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
        p = np.nan_to_num(s.get("prec"))
        ax2.bar(x, p, width=0.9, color=c_p, alpha=0.75)
        handles.append(Patch(facecolor=c_p, alpha=0.75, label="Опади, мм/добу (стовпчики, права вісь)"))
        ax2.set_ylabel("Опади, мм/добу")
        ax2.set_ylim(0, max(1.0, float(np.max(p))) * 3.0)     # опади займають нижню третину
        ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    _legend(ax, st, handles, default_loc="upper left", ncol=1)
    _title(ax, st, rep, place, "Кліматограма")
    fig.tight_layout()


def _climo_decade(fig, rep, place, st):
    dec = rep["decades"]
    if not dec:
        return "Немає даних."
    ax = fig.add_subplot(111)
    xs = np.arange(len(dec)); lw, ms = st.g["line_width"], st.g["marker_size"]
    c_t, c_p = st.col("tmean", "#b2182b"), st.col("prec", "#2171b5")
    pr = [d["prec_sum"] for d in dec]; tm = [d["tmean"] for d in dec]
    ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
    ax2.bar(xs, np.nan_to_num(pr), width=0.8, color=c_p, alpha=0.7)
    ax2.set_ylabel("Сума опадів за декаду, мм")
    ax2.set_ylim(0, max(1.0, float(np.nanmax(pr))) * 2.2)
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax.plot(xs, tm, color=c_t, marker="o", ms=ms * 0.6, lw=lw)
    ax.axhline(0, color="#777", lw=0.7, ls="--")
    ax.set_ylabel("Середня температура повітря, °C")
    _headroom(ax, st); ax2.set_ylim(0, max(1.0, float(np.nanmax(pr))) * 2.9)
    step = max(1, len(dec) // 36)
    labels = []
    for i, d in enumerate(dec):
        new_year = (d["key"][1] == 1 and d["key"][2] == 1) or i == 0
        labels.append(f"{d['start']:%d.%m}\n{d['start']:%Y}" if new_year else f"{d['start']:%d.%m}")
    ax.set_xticks(xs[::step]); ax.set_xticklabels(labels[::step], fontsize=max(5.0, st.g["tick_size"] - 2))
    handles = [Line2D([0], [0], color=c_t, marker="o", ms=ms * 0.6, lw=lw, label="Середня температура, °C (крива, ліва вісь)"),
               Patch(facecolor=c_p, alpha=0.7, label="Сума опадів за декаду, мм (стовпчики, права вісь)")]
    _legend(ax, st, handles, default_loc="upper left")
    _title(ax, st, rep, place, "Температура й опади за декадами")
    fig.tight_layout()


def _walter(fig, rep, place, st):
    full = [m for m in rep["months"] if m["days"] >= 20]     # неповні місяці не беремо
    if len(full) < 3:
        return "Для діаграми Вальтера потрібно щонайменше 3 повні місяці даних."
    by_cal = {}
    for m in full:
        by_cal.setdefault(m["key"][1], []).append(m)
    if len(by_cal) == 12:
        order = list(range(1, 13))
        T = [float(np.nanmean([m["tmean"] for m in by_cal[c]])) for c in order]
        P = [float(np.nanmean([m["prec_sum"] for m in by_cal[c]])) for c in order]
        labels = [W.MONTHS_UA_SHORT[c - 1] for c in order]
        yrs = sorted({m["key"][0] for m in full})
        sub = f"середній річний хід за {yrs[0]}–{yrs[-1]}" if len(yrs) > 1 else f"{yrs[0]} р."
    else:
        T = [m["tmean"] for m in full]; P = [m["prec_sum"] for m in full]
        labels = [f"{W.MONTHS_UA_SHORT[m['key'][1]-1]}\n{m['key'][0] % 100:02d}" for m in full]
        sub = "за місяцями періоду"
    n = len(T); lw, ms = st.g["line_width"], st.g["marker_size"]
    c_t, c_p, c_w, c_d = st.col("temp", "#b2182b"), st.col("prec", "#08519c"), st.col("wet", "#6baed6"), st.col("dry", "#fdae6b")
    ax = fig.add_subplot(111)
    xs = np.arange(1, n + 1)
    P2 = np.array(P) / 2.0                                   # масштаб Вальтера: 10 °C = 20 мм
    fx = np.linspace(1, n, 400)
    Ti = np.interp(fx, xs, T); Pi = np.interp(fx, xs, P2)
    ax.fill_between(fx, Ti, Pi, where=Pi >= Ti, color=c_w, alpha=0.45, lw=0, label="Вологий період (P > 2T)")
    ax.fill_between(fx, Ti, Pi, where=Pi < Ti, color=c_d, alpha=0.55, lw=0, label="Посушливий період (P < 2T)")
    ax.plot(xs, T, color=c_t, marker="o", ms=ms, lw=lw, label="Температура, °C")
    ax.plot(xs, P2, color=c_p, marker="s", ms=ms, lw=lw, label="Опади (шкала 2:1)")
    top = max(float(np.nanmax(T)), float(np.nanmax(P2))) * (1.15 if LEGEND_LOCS[st.g["legend_loc"]] in ("none", "below") else 1.38)
    bot = min(0.0, float(np.nanmin(T)) * 1.1)
    ax.set_ylim(bot, top)
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=st.g["tick_size"] - (1 if n > 14 else 0))
    ax.set_ylabel("Температура повітря, °C")
    sec = ax.secondary_yaxis("right", functions=(lambda y: y * 2.0, lambda y: y / 2.0))
    sec.set_ylabel("Сума опадів за місяць, мм"); sec.spines["right"].set_visible(True)
    ax.axhline(0, color="#777", lw=0.6)
    _legend(ax, st, None, default_loc="upper left", ncol=2)
    _title(ax, st, rep, place, f"Діаграма Вальтера – {sub}",
           sub_override=f"{place + ', ' if place else ''}{rep['d0']:%d.%m.%Y}–{rep['d1']:%d.%m.%Y}")
    fig.tight_layout()


def _month_ticks(ax, st):
    starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    ax.set_xticks(starts); ax.set_xticklabels(W.MONTHS_UA_SHORT, fontsize=st.g["tick_size"] - 1)
    ax.set_xlim(1, 366)


def _cum_by_year(fig, rep, place, st, ylabel, what, value_fn):
    """Нагромаджувальні криві по роках; value_fn(series, idx) → масив приростів за добу."""
    s = rep["series"]
    groups = {}
    for i, d in enumerate(s.dates):
        groups.setdefault(d.year, []).append(i)
    ax = fig.add_subplot(111)
    for k, (yr, idx) in enumerate(sorted(groups.items())):
        doy = np.array([s.dates[i].timetuple().tm_yday for i in idx])
        ax.plot(doy, np.cumsum(value_fn(s, idx)), lw=st.g["line_width"], label=str(yr), color=st.col(f"y{yr}", TAB[k % 10]))
    _month_ticks(ax, st)
    ax.set_ylabel(ylabel); _headroom(ax, st, 0.18)
    _legend(ax, st, None, default_loc="upper left", ncol=min(6, len(groups)))
    _title(ax, st, rep, place, what)
    fig.tight_layout()


def _cum_prec(fig, rep, place, st):
    if not rep["series"].has("prec"):
        return "Немає даних про опади."
    return _cum_by_year(fig, rep, place, st, "Нагромаджені опади, мм", "Нагромаджені опади",
                        lambda s, idx: np.nan_to_num(s.get("prec")[idx]))


def _cum_set(fig, rep, place, st):
    if not rep["series"].has("tmean"):
        return "Немає даних про температуру."
    b = rep["settings"].get("gdd_base", 10.0)
    return _cum_by_year(fig, rep, place, st, f"Σ(tсер − {b:g}), °C",
                        f"Нагромаджена сума ефективних температур (біологічний мінімум {b:g} °C)",
                        lambda s, idx: np.where(s.get("tmean")[idx] > b, s.get("tmean")[idx] - b, 0.0))


def _htc_bars(fig, rep, place, st, rows, labels, what, rotate):
    vals = [r["htc"] for r in rows]
    finite = [v for v in vals if not math.isnan(v)]
    if not finite:
        return "У цьому періоді немає активних температур (> 10 °C) – ГТК не розраховується."
    ax = fig.add_subplot(111)
    xs = np.arange(len(rows))
    colmap = {k: st.col(k, HTC_COLORS[k]) for k in HTC_COLORS}
    cols = [colmap[W.htc_class(v)[1]] for v in vals]
    ax.bar(xs, [0 if math.isnan(v) else v for v in vals], color=cols, width=0.8, edgecolor="#444", lw=0.4)
    for b in HTC_BOUNDS:
        ax.axhline(b, color="#666", lw=0.5, ls=":")
    if len(rows) <= 40:
        for x, v in zip(xs, vals):
            if not math.isnan(v):
                ax.text(x, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=max(5.0, st.g["tick_size"] - 2))
            else:
                ax.text(x, 0.02, "–", ha="center", va="bottom", fontsize=st.g["tick_size"] - 1, color="#888")
    step = max(1, len(rows) // 36)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels(labels[::step], rotation=rotate, fontsize=max(5.0, st.g["tick_size"] - 1.5), ha="right" if rotate else "center")
    ax.set_ylabel("ГТК Селянінова")
    present = [c for c in ("d4", "d3", "d2", "d1", "ok", "wet")
               if any(W.htc_class(v)[1] == c for v in vals)]
    _legend(ax, st, [Patch(facecolor=colmap[c], edgecolor="#444", label=HTC_NAMES[c]) for c in present], default_loc="upper left", ncol=3)
    ax.set_ylim(0, max(1.8, max(finite) * 1.15))
    _title(ax, st, rep, place, what)
    fig.text(0.99, 0.005, "Пунктир – межі класів вологозабезпеченості (шкала Селянінова)",
             ha="right", va="bottom", fontsize=max(5.0, st.g["legend_size"] - 2), color="#666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))


def _htc_decade(fig, rep, place, st):
    rows = rep["decades"]
    return _htc_bars(fig, rep, place, st, rows, [f"{r['start']:%d.%m}\n{r['start']:%y}" for r in rows], "ГТК за декадами", 0)


def _htc_month(fig, rep, place, st):
    rows = rep["months"]
    return _htc_bars(fig, rep, place, st, rows, [r["label"] for r in rows], "ГТК за місяцями", 45)


def _humidity(fig, rep, place, st):
    """Середня вологість повітря за місяцями (стовпчики) з дефіцитом насичення VPD (лінія, права вісь) і кількістю діб із високою / низькою вологістю."""
    s = rep["series"]
    if not s.has("rh"):
        return ("У даних немає вологості повітря. NASA POWER її надає (параметр RH2M); у власному файлі додайте стовпець «Вологість» (%).")
    rows = [r for r in rep["months"] if not math.isnan(r.get("rh", float("nan")))]
    if not rows:
        return "Немає місяців із даними про вологість."
    ax, ax3 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    xs = np.arange(len(rows)); lw, ms = st.g["line_width"], st.g["marker_size"]
    c_rh, c_v, c_hi, c_lo, c_thr = st.col("rh", "#6baed6"), st.col("vpd", "#d94801"), st.col("hi", "#2166ac"), st.col("lo", "#e08214"), st.col("thr", "#777777")
    ax.bar(xs, [r["rh"] for r in rows], width=0.8, color=c_rh, edgecolor="#444", lw=0.4)
    ax.axhline(W.RH_HI, color=c_thr, lw=0.8, ls="--"); ax.axhline(W.RH_LO, color=c_thr, lw=0.8, ls="--")
    ax.set_ylim(0, 112); ax.set_ylabel("Середня відносна вологість, %")
    if len(rows) <= 36:
        for x, r in zip(xs, rows): ax.text(x, r["rh"] + 1.2, f"{r['rh']:.0f}", ha="center", va="bottom", fontsize=max(5.0, st.g["tick_size"] - 2))
    ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
    vp = [r["vpd"] for r in rows]; ax2.plot(xs, vp, color=c_v, lw=lw, marker="o", ms=ms); ax2.set_ylabel("VPD, кПа")
    fin = [v for v in vp if not math.isnan(v)]; ax2.set_ylim(0, max(0.5, max(fin) * 1.25) if fin else 1.0)
    _legend(ax, st, [Patch(facecolor=c_rh, edgecolor="#444", label="Вологість повітря, % (стовпчики)"), Line2D([0], [0], color=c_v, lw=lw, marker="o", label="VPD, кПа (лінія, права вісь)"),
                     Line2D([0], [0], color=c_thr, lw=0.8, ls="--", label=f"Пороги {W.RH_LO:g} % і {W.RH_HI:g} %")], default_loc="upper left", ncol=3)
    w = 0.38; ax3.bar(xs - w / 2, [r["days_rh_hi"] for r in rows], width=w, color=c_hi); ax3.bar(xs + w / 2, [r["days_rh_lo"] for r in rows], width=w, color=c_lo)
    ax3.set_ylabel("Діб у місяці"); _headroom(ax3, st, 0.4); _legend(ax3, st, [Patch(facecolor=c_hi, label=f"вологість ≥ {W.RH_HI:g} %"), Patch(facecolor=c_lo, label=f"вологість ≤ {W.RH_LO:g} %")], default_loc="upper right", ncol=2)
    step = max(1, len(rows) // 36); ax3.set_xticks(xs[::step]); rot = 45 if len(rows) > 12 else 0
    ax3.set_xticklabels([r["label"] for r in rows][::step], rotation=rot, fontsize=max(5.0, st.g["tick_size"] - 1.5), ha="right" if rot else "center")
    _title(ax, st, rep, place, "Вологість повітря")
    fig.text(0.99, 0.005, "RH2M (NASA POWER) – модель, сітка ≈ 50 км; VPD – за добовими середніми", ha="right", va="bottom", fontsize=max(5.0, st.g["legend_size"] - 2), color="#666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))


def _years_cmp(fig, rep, place, st):
    ys = rep["years"]
    if not ys:
        return ("Немає жодного року з повним покриттям вікна. Змініть вікно порівняння років у розділі 3 ліворуч "
                "або запросіть ширший період.")
    m1, d1, m2, d2 = rep["settings"]["window"]
    ax1 = fig.add_subplot(211); ax2 = fig.add_subplot(212, sharex=ax1)
    xs = np.arange(len(ys)); labels = [str(r["year"]) for r in ys]
    nrm = rep["norm"][0] if rep.get("norm") else None
    c_t, c_s, c_p, c_n = st.col("temp", "#b2182b"), st.col("stem", "#f4a582"), st.col("prec", "#4393c3"), st.col("norm", "#333333")
    tvals = [r["tmean"] for r in ys]
    ax1.vlines(xs, min(tvals) - 1.5, tvals, color=c_s, lw=2)      # «стебла» від нижньої межі шкали
    ax1.plot(xs, tvals, "o", color=c_t, ms=st.g["marker_size"] * 1.5)
    ax2.bar(xs, [r["prec_sum"] for r in ys], color=c_p, width=0.6)
    h1 = [Line2D([0], [0], color=c_t, marker="o", ls="", ms=st.g["marker_size"] * 1.2, label="Середня температура у вікні, °C")]
    h2 = [Patch(facecolor=c_p, label="Сума опадів у вікні, мм (стовпчики)")]
    if nrm:
        for ax, key, h in ((ax1, "tmean", h1), (ax2, "prec_sum", h2)):
            ax.axhline(nrm[key], color=c_n, ls="--", lw=1)
            h.append(Line2D([0], [0], color=c_n, ls="--", lw=1, label=f"Норма ({rep['norm'][2]})"))
    for ax, key, f, dy in ((ax1, "tmean", "{:.1f}", 0.25), (ax2, "prec_sum", "{:.0f}", 0)):
        for x, r in zip(xs, ys):
            if not math.isnan(r[key]):
                ax.text(x, r[key] + dy, f.format(r[key]), ha="center", va="bottom", fontsize=max(5.0, st.g["tick_size"] - 1))
    ax1.set_ylabel("Середня t, °C"); ax2.set_ylabel("Сума опадів, мм")
    ax2.set_xticks(xs); ax2.set_xticklabels(labels)
    tfin = [v for v in tvals if not math.isnan(v)]
    lo, hi = min(tfin), max(tfin)
    if nrm and not math.isnan(nrm["tmean"]): lo, hi = min(lo, nrm["tmean"]), max(hi, nrm["tmean"])
    ax1.set_ylim(lo - 1.5, hi + 1.5)                          # вузька шкала: різниця між роками помітна
    ax2.set_ylim(0, max(r["prec_sum"] for r in ys if not math.isnan(r["prec_sum"])) * 1.2)
    _legend(ax1, st, h1, default_loc="upper right"); _legend(ax2, st, h2, default_loc="upper right")
    _title(ax1, st, rep, place, f"Порівняння років за вікном {d1:02d}.{m1:02d}–{d2:02d}.{m2:02d}",
           sub_override=place or "")
    fig.tight_layout()


def _vine(fig, rep, place, st):
    iv = rep.get("intl") or {}; rows = iv.get("vine") or []
    if not rows:
        if iv.get("lat") is None: return "Для вінограрських індексів потрібна широта: оберіть місце досліду на карті."
        return "Немає сезонів із повним покриттям: потрібні добові дані за весь сезон (1 квітня – 31 жовтня для індексу Вінклера, 1 квітня – 30 вересня для Югліна)."
    import sad_weather_indices as WI
    south = iv["lat"] < 0
    xs = np.arange(len(rows)); labels = [r["label"] for r in rows]
    c_w, c_h, c_b = st.col("winkler", "#d98c3f"), st.col("huglin", "#8c4f9e"), st.col("bounds", "#666666")
    ax1 = fig.add_subplot(211); ax2 = fig.add_subplot(212, sharex=ax1)
    wv = [r["winkler"] for r in rows]; hv = [r["huglin"] for r in rows]
    ax1.bar(xs, [0 if math.isnan(v) else v for v in wv], color=c_w, width=0.6)
    ax2.bar(xs, [0 if math.isnan(v) else v for v in hv], color=c_h, width=0.6)
    for ax, vals, fmt in ((ax1, wv, "{:.0f}"), (ax2, hv, "{:.0f}")):
        for x, v in zip(xs, vals):
            if not math.isnan(v): ax.text(x, v, fmt.format(v), ha="center", va="bottom", fontsize=max(5.0, st.g["tick_size"] - 1))
    top1 = max([v for v in wv if not math.isnan(v)] + [WI.WINKLER_BOUNDS_C[0]]); top2 = max([v for v in hv if not math.isnan(v)] + [1500.0])
    names = ["I", "II", "III", "IV", "V"]
    for b, nm in zip(WI.WINKLER_BOUNDS_C, names[1:]):
        if b < top1 * 1.25: ax1.axhline(b, color=c_b, ls=":", lw=0.9); ax1.text(len(rows) - 0.4 + 0.85, b, f"→ {nm}", va="bottom", ha="right", fontsize=max(5.0, st.g["tick_size"] - 1), color=c_b)
    for (hi, code, _n) in WI.HUGLIN_CLASSES[:-1]:
        if hi < top2 * 1.25: ax2.axhline(hi, color=c_b, ls=":", lw=0.9); ax2.text(len(rows) - 0.4 + 0.85, hi, f"→ {WI.huglin_class(hi + 0.001)[0]}", va="bottom", ha="right", fontsize=max(5.0, st.g["tick_size"] - 1), color=c_b)
    k_head = 1.25 if LEGEND_LOCS[st.g["legend_loc"]] in ("none", "below") else 1.6                             # запас під легенду всередині діаграми
    ax1.set_ylim(0, top1 * k_head); ax2.set_ylim(0, top2 * k_head); ax1.set_xlim(-0.6, len(rows) - 0.4 + 0.9)  # поле справа для підписів класів
    ax1.set_ylabel("Вінклер (GDD), °C·діб"); ax2.set_ylabel("Югліна (HI)")
    ax2.set_xticks(xs); ax2.set_xticklabels(labels, rotation=0 if len(rows) < 12 else 45, ha="center" if len(rows) < 12 else "right")
    hb = Line2D([0], [0], color=c_b, ls=":", lw=1.2, label="Межі класів (Вінклер I–V; Югліна HI−3…HI+3)")
    _legend(ax1, st, [Patch(facecolor=c_w, label="Індекс Вінклера (GDD >10 °C)"), hb], default_loc="upper left")
    _legend(ax2, st, [Patch(facecolor=c_h, label="Індекс Югліна (HI)"), hb], default_loc="upper left")
    per = "1.10–30.04 / 1.10–31.03" if south else "1.04–31.10 / 1.04–30.09"
    _title(ax1, st, rep, place, f"Вінклер і Югліна за сезонами ({per})", sub_override=f"{place + ', ' if place else ''}широта {str(round(abs(iv['lat']), 2)).replace('.', ',')}° {'пд.' if south else 'пн.'}")
    fig.tight_layout()


def _spi(fig, rep, place, st):
    sp = rep.get("spi")
    if not sp or not sp.get("rows") or not any(any(v == v for v in r["spi"].values()) for r in sp["rows"]):
        return "SPI ще не розраховано: на вкладці «SPI» натисніть «Завантажити й обчислити SPI»."
    ks = [k for k in sp["scales"] if any(r["spi"][k] == r["spi"][k] for r in sp["rows"])]
    c_w, c_d, c_l = st.col("wet", "#2166ac"), st.col("dry", "#b2182b"), st.col("lim", "#777777")
    rows = sp["rows"]; xs = np.arange(len(rows)); step = max(1, len(rows) // 24)
    axes = []
    for i, k in enumerate(ks):
        ax = fig.add_subplot(len(ks), 1, i + 1, sharex=axes[0] if axes else None); axes.append(ax)
        z = np.array([r["spi"][k] for r in rows], float); zz = np.nan_to_num(z)
        ax.bar(xs, np.where(zz >= 0, zz, 0), color=c_w, width=0.85); ax.bar(xs, np.where(zz < 0, zz, 0), color=c_d, width=0.85)
        for lim in (-2, -1, 1, 2): ax.axhline(lim, color=c_l, ls=":", lw=0.8)
        ax.axhline(0, color="#444", lw=0.7)
        top = max(2.5, float(np.nanmax(np.abs(z))) * 1.1) if np.any(~np.isnan(z)) else 2.5; ax.set_ylim(-top, top)
        ax.set_ylabel(f"SPI-{k}")
        if i < len(ks) - 1: ax.tick_params(labelbottom=False)
    axes[-1].set_xticks(xs[::step]); axes[-1].set_xticklabels([rows[j]["label"] for j in xs[::step]], rotation=45, ha="right", fontsize=max(5.0, st.g["tick_size"] - 1))
    _legend(axes[0], st, [Patch(facecolor=c_w, label="Вологі місяці (SPI > 0)"), Patch(facecolor=c_d, label="Сухі місяці (SPI < 0)"),
                          Line2D([0], [0], color=c_l, ls=":", label="Межі класів ±1, ±2")], default_loc="upper left", ncol=3)
    _title(axes[0], st, rep, place, f"SPI за місяцями (еталонний період {sp['ref'][0]}–{sp['ref'][1]})",
           sub_override=f"{place + ', ' if place else ''}{rows[0]['label']}–{rows[-1]['label']}")
    fig.tight_layout()
