# sad_weather_charts.py — S.A.D. v2.1: графіки модуля «Погода» (лише matplotlib)
# -*- coding: utf-8 -*-
import math
import numpy as np
import matplotlib
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import sad_weather_core as W

CHARTS = [
    ("climo_daily", "Кліматограма (добова)"),
    ("climo_decade", "Температура й опади за декадами"),
    ("walter", "Діаграма Вальтера"),
    ("cum_prec", "Нагромаджені опади (за роками)"),
    ("cum_set", "Нагромаджена сума ефективних температур (за роками)"),
    ("htc_decade", "ГТК за декадами"),
    ("htc_month", "ГТК за місяцями"),
    ("years_cmp", "Порівняння років (температура й опади у вікні)"),
]

HTC_COLORS = {"d4": "#a50f15", "d3": "#de2d26", "d2": "#fb6a4a", "d1": "#fcae91",
              "ok": "#74c476", "wet": "#2171b5", "na": "#bdbdbd"}
HTC_NAMES = {"d4": "дуже сильна посуха", "d3": "сильна посуха", "d2": "середня посуха",
             "d1": "слабка посуха", "ok": "достатньо волого", "wet": "надмірно волого"}
# Межі класів на неперервній шкалі (клас визначається за ГТК, округленим до 0,1)
HTC_BOUNDS = [0.35, 0.55, 0.75, 0.95, 1.55]
TAB = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
       "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

_RC = {"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
       "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
       "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8,
       "axes.unicode_minus": False}


def _message(fig, text):
    fig.clear()
    ax = fig.add_subplot(111); ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", wrap=True, fontsize=11, color="#555")


def _head(rep, place, what):
    sub = f"{place + ', ' if place else ''}{rep['d0']:%d.%m.%Y}–{rep['d1']:%d.%m.%Y}"
    return f"{what}\n{sub}"


def build_chart(fig, kind, rep, place=""):
    """Малює діаграму kind у fig. Повертає None при успіху, інакше — текст причини."""
    with matplotlib.rc_context(_RC):
        fig.clear()
        fn = {"climo_daily": _climo_daily, "climo_decade": _climo_decade, "walter": _walter,
              "cum_prec": _cum_prec, "cum_set": _cum_set, "htc_decade": _htc_decade,
              "htc_month": _htc_month, "years_cmp": _years_cmp}.get(kind)
        if fn is None:
            return "Невідомий тип діаграми."
        try:
            res = fn(fig, rep, place)
        except Exception as e:                       # діаграма не повинна валити вікно
            res = f"Не вдалося побудувати діаграму: {e}"
        if res:
            _message(fig, res)
        return res


# ───────────────────────────────────────────────────────────
def _climo_daily(fig, rep, place):
    s = rep["series"]
    if not s.has("tmean") and not s.has("tmax"):
        return "Немає даних про температуру."
    ax = fig.add_subplot(111)
    x = mdates.date2num(s.dates)
    if s.has("tmax") and s.has("tmin"):
        ax.fill_between(x, s.get("tmin"), s.get("tmax"), color="#f4a582", alpha=0.35, lw=0,
                        label="tmin–tmax")
    ax.plot(x, s.get("tmean"), color="#b2182b", lw=1.1, label="tсер")
    ax.axhline(0, color="#777", lw=0.7, ls="--")
    ax.set_ylabel("Температура повітря, °C")
    ax.xaxis_date()
    loc = mdates.AutoDateLocator(); ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
    if s.has("prec"):
        ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
        p = np.nan_to_num(s.get("prec"))
        ax2.bar(x, p, width=0.9, color="#2171b5", alpha=0.75, label="Опади")
        ax2.set_ylabel("Опади, мм/добу")
        ax2.set_ylim(0, max(1.0, float(np.max(p))) * 3.0)     # опади займають нижню третину
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8, frameon=False, ncol=3)
    else:
        ax.legend(loc="upper left", fontsize=8, frameon=False)
    ax.set_title(_head(rep, place, "Кліматограма"), fontsize=10.5, loc="left")
    fig.tight_layout()


def _climo_decade(fig, rep, place):
    dec = rep["decades"]
    if not dec:
        return "Немає даних."
    ax = fig.add_subplot(111)
    xs = np.arange(len(dec))
    pr = [d["prec_sum"] for d in dec]; tm = [d["tmean"] for d in dec]
    ax2 = ax.twinx(); ax2.spines["right"].set_visible(True)
    ax2.bar(xs, np.nan_to_num(pr), width=0.8, color="#2171b5", alpha=0.7)
    ax2.set_ylabel("Сума опадів за декаду, мм")
    ax2.set_ylim(0, max(1.0, float(np.nanmax(pr))) * 2.2)
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax.plot(xs, tm, color="#b2182b", marker="o", ms=3, lw=1.3)
    ax.axhline(0, color="#777", lw=0.7, ls="--")
    ax.set_ylabel("Середня температура повітря, °C")
    step = max(1, len(dec) // 36)
    labels = []
    for i, d in enumerate(dec):
        new_year = (d["key"][1] == 1 and d["key"][2] == 1) or i == 0
        labels.append(f"{d['start']:%d.%m}\n{d['start']:%Y}" if new_year else f"{d['start']:%d.%m}")
    ax.set_xticks(xs[::step]); ax.set_xticklabels(labels[::step], fontsize=7)
    ax.set_title(_head(rep, place, "Температура й опади за декадами"), fontsize=10.5, loc="left")
    fig.tight_layout()


def _walter(fig, rep, place):
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
    n = len(T)
    ax = fig.add_subplot(111)
    xs = np.arange(1, n + 1)
    P2 = np.array(P) / 2.0                                   # масштаб Вальтера: 10 °C = 20 мм
    fx = np.linspace(1, n, 400)
    Ti = np.interp(fx, xs, T); Pi = np.interp(fx, xs, P2)
    ax.fill_between(fx, Ti, Pi, where=Pi >= Ti, color="#6baed6", alpha=0.45, lw=0,
                    label="Вологий період (P > 2T)")
    ax.fill_between(fx, Ti, Pi, where=Pi < Ti, color="#fdae6b", alpha=0.55, lw=0,
                    label="Посушливий період (P < 2T)")
    ax.plot(xs, T, color="#b2182b", marker="o", lw=1.6, label="Температура, °C")
    ax.plot(xs, P2, color="#08519c", marker="s", lw=1.6, label="Опади (шкала 2:1)")
    top = max(float(np.nanmax(T)), float(np.nanmax(P2))) * 1.15
    bot = min(0.0, float(np.nanmin(T)) * 1.1)
    ax.set_ylim(bot, top)
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=8 if n > 14 else 9)
    ax.set_ylabel("Температура повітря, °C")
    sec = ax.secondary_yaxis("right", functions=(lambda y: y * 2.0, lambda y: y / 2.0))
    sec.set_ylabel("Сума опадів за місяць, мм"); sec.spines["right"].set_visible(True)
    ax.axhline(0, color="#777", lw=0.6)
    ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    ax.set_title(f"Діаграма Вальтера — {sub}\n{place + ', ' if place else ''}"
                 f"{rep['d0']:%d.%m.%Y}–{rep['d1']:%d.%m.%Y}", fontsize=10.5, loc="left")
    fig.tight_layout()


def _month_ticks(ax):
    starts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
    ax.set_xticks(starts); ax.set_xticklabels(W.MONTHS_UA_SHORT, fontsize=8)
    ax.set_xlim(1, 366)


def _cum_by_year(fig, rep, place, ylabel, what, value_fn):
    """Нагромаджувальні криві по роках; value_fn(series, idx) → масив приростів за добу."""
    s = rep["series"]
    groups = {}
    for i, d in enumerate(s.dates):
        groups.setdefault(d.year, []).append(i)
    ax = fig.add_subplot(111)
    for k, (yr, idx) in enumerate(sorted(groups.items())):
        doy = np.array([s.dates[i].timetuple().tm_yday for i in idx])
        ax.plot(doy, np.cumsum(value_fn(s, idx)), lw=1.6, label=str(yr), color=TAB[k % 10])
    _month_ticks(ax)
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=8, frameon=False, ncol=min(6, len(groups)))
    ax.set_title(_head(rep, place, what), fontsize=10.5, loc="left")
    fig.tight_layout()


def _cum_prec(fig, rep, place):
    if not rep["series"].has("prec"):
        return "Немає даних про опади."
    return _cum_by_year(fig, rep, place, "Нагромаджені опади, мм", "Нагромаджені опади",
                        lambda s, idx: np.nan_to_num(s.get("prec")[idx]))


def _cum_set(fig, rep, place):
    if not rep["series"].has("tmean"):
        return "Немає даних про температуру."
    b = rep["settings"].get("gdd_base", 10.0)
    return _cum_by_year(fig, rep, place, f"Σ(tсер − {b:g}), °C",
                        f"Нагромаджена сума ефективних температур (біологічний мінімум {b:g} °C)",
                        lambda s, idx: np.where(s.get("tmean")[idx] > b, s.get("tmean")[idx] - b, 0.0))


def _htc_bars(fig, rep, place, rows, labels, what, rotate):
    vals = [r["htc"] for r in rows]
    finite = [v for v in vals if not math.isnan(v)]
    if not finite:
        return "У цьому періоді немає активних температур (> 10 °C) — ГТК не розраховується."
    ax = fig.add_subplot(111)
    xs = np.arange(len(rows))
    cols = [HTC_COLORS[W.htc_class(v)[1]] for v in vals]
    ax.bar(xs, [0 if math.isnan(v) else v for v in vals], color=cols, width=0.8,
           edgecolor="#444", lw=0.4)
    for b in HTC_BOUNDS:
        ax.axhline(b, color="#666", lw=0.5, ls=":")
    if len(rows) <= 40:
        for x, v in zip(xs, vals):
            if not math.isnan(v):
                ax.text(x, v + 0.02, f"{v:.2f}", ha="center", va="bottom", fontsize=7)
            else:
                ax.text(x, 0.02, "—", ha="center", va="bottom", fontsize=8, color="#888")
    step = max(1, len(rows) // 36)
    ax.set_xticks(xs[::step])
    ax.set_xticklabels(labels[::step], rotation=rotate, fontsize=7.5, ha="right" if rotate else "center")
    ax.set_ylabel("ГТК Селянінова")
    present = [c for c in ("d4", "d3", "d2", "d1", "ok", "wet")
               if any(W.htc_class(v)[1] == c for v in vals)]
    ax.legend(handles=[Patch(facecolor=HTC_COLORS[c], edgecolor="#444", label=HTC_NAMES[c]) for c in present],
              fontsize=8, frameon=False, loc="upper left", ncol=3)
    ax.set_ylim(0, max(1.8, max(finite) * 1.15))
    ax.set_title(_head(rep, place, what), fontsize=10.5, loc="left")
    fig.text(0.99, 0.005, "Пунктир — межі класів вологозабезпеченості (шкала Селянінова)",
             ha="right", va="bottom", fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))


def _htc_decade(fig, rep, place):
    rows = rep["decades"]
    return _htc_bars(fig, rep, place, rows, [f"{r['start']:%d.%m}\n{r['start']:%y}" for r in rows],
                     "ГТК за декадами", 0)


def _htc_month(fig, rep, place):
    rows = rep["months"]
    return _htc_bars(fig, rep, place, rows, [r["label"] for r in rows], "ГТК за місяцями", 45)


def _years_cmp(fig, rep, place):
    ys = rep["years"]
    if not ys:
        return ("Немає жодного року з повним покриттям вікна. Змініть вікно (ММ-ДД) на вкладці "
                "«За роками» або запросіть ширший період.")
    m1, d1, m2, d2 = rep["settings"]["window"]
    ax1 = fig.add_subplot(211); ax2 = fig.add_subplot(212, sharex=ax1)
    xs = np.arange(len(ys)); labels = [str(r["year"]) for r in ys]
    nrm = rep["norm"][0] if rep.get("norm") else None
    tvals = [r["tmean"] for r in ys]
    ax1.vlines(xs, min(tvals) - 1.5, tvals, color="#f4a582", lw=2)      # «стебла» від нижньої межі шкали
    ax1.plot(xs, tvals, "o", color="#b2182b", ms=8)
    ax2.bar(xs, [r["prec_sum"] for r in ys], color="#4393c3", width=0.6)
    if nrm:
        for ax, key in ((ax1, "tmean"), (ax2, "prec_sum")):
            ax.axhline(nrm[key], color="#333", ls="--", lw=1, label=f"Норма ({rep['norm'][2]})")
            ax.legend(fontsize=8, frameon=False)
    for ax, key, f, dy in ((ax1, "tmean", "{:.1f}", 0.25), (ax2, "prec_sum", "{:.0f}", 0)):
        for x, r in zip(xs, ys):
            if not math.isnan(r[key]):
                ax.text(x, r[key] + dy, f.format(r[key]), ha="center", va="bottom", fontsize=8)
    ax1.set_ylabel("Середня t, °C"); ax2.set_ylabel("Сума опадів, мм")
    ax2.set_xticks(xs); ax2.set_xticklabels(labels)
    tfin = [v for v in tvals if not math.isnan(v)]
    lo, hi = min(tfin), max(tfin)
    if nrm and not math.isnan(nrm["tmean"]): lo, hi = min(lo, nrm["tmean"]), max(hi, nrm["tmean"])
    ax1.set_ylim(lo - 1.5, hi + 1.5)                          # вузька шкала: різниця між роками помітна
    ax2.set_ylim(0, max(r["prec_sum"] for r in ys if not math.isnan(r["prec_sum"])) * 1.2)
    ax1.set_title(f"Порівняння років за вікном {d1:02d}.{m1:02d}–{d2:02d}.{m2:02d}"
                  + (f"\n{place}" if place else ""), fontsize=10.5, loc="left")
    fig.tight_layout()
