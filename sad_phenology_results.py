# sad_phenology_results.py – S.A.D. v2.1: вікно результатів фенологічних спостережень
# -*- coding: utf-8 -*-
import math, tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from sad_common import set_icon, make_tv, embed_figure, attach_export_bar
import sad_phenology as P

RF = ("Times New Roman", 11); RB = ("Times New Roman", 11, "bold"); SM = ("Times New Roman", 9)
FONT = ["Times New Roman", "DejaVu Serif"]
MONTH_START = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]; MONTH_ABBR = ["січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру"]
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5"]
CLASS_BG = {"ранній": "#c8e6c9", "середній": "#ffffff", "пізній": "#ffe0b2"}
CHARTS = ["Фенологічний спектр (середні дати й тривалість періодів)", "Дати за сортами (розподіл за роками й повторностями)", "Відхилення від стандарту (діб)", "Динаміка за роками",
          "Розподіл середніх дат сортів (гістограма)", "Ранжований профіль середніх дат"]
MAX_SHOWN = 30                    # більше сортів на графіках не показуємо: стандарт + найранішi й найпізніші за вибраною фазою


def _f(x, nd=1, sign=False):
    if x is None or (isinstance(x, float) and math.isnan(x)): return "–"
    s = f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"; return s.replace(".", ",").replace("-", "−")


def _date_cell(s, show_sd=True):
    if s["n"] == 0: return "–"
    t = P.md_from_doy(s["mean"])
    if show_sd and s["n"] > 1 and not math.isnan(s["sd"]): t += f" ±{_f(s['sd'])}"
    return t


def _dow_axis(ax, lo, hi, axis="x"):
    """Підписує вісь днів року датами (дд.мм) або місяцями."""
    span = max(1.0, hi - lo)
    if span > 150 and axis == "x":
        ticks = [d for d in MONTH_START if lo - 2 <= d <= hi + 2]; labs = [MONTH_ABBR[MONTH_START.index(d)] for d in ticks]
    else:
        step = next(s for s in (1, 2, 3, 5, 7, 10, 15, 20, 30) if span / s <= 12); t0 = int(math.floor(lo / step) * step); ticks = list(range(t0, int(hi) + step + 1, step)); labs = [P.md_from_doy(d) for d in ticks]
    (ax.set_xticks if axis == "x" else ax.set_yticks)(ticks); (ax.set_xticklabels if axis == "x" else ax.set_yticklabels)(labs, fontfamily=FONT, fontsize=9)


class PhenologyResults:
    def __init__(self, parent, ctx, crop_name=""):
        self.ctx = ctx; self.crop = crop_name
        self._stds = set(ctx.get("standards") or ([ctx["standard"]] if ctx["standard"] else [])); self._grp = ctx.get("groups") or {}; self._gstd = ctx.get("group_std") or {}
        self._multi = bool(ctx.get("ref_of")) and len(set(v for v in ctx["ref_of"].values() if v)) > 1; self.fig = None; self.method = ctx.get("method", "auto"); self.comp = ctx["compare"]
        self.win = tk.Toplevel(parent); self.win.title("Фенологічні спостереження — Результати"); self.win.geometry("1240x800"); set_icon(self.win)
        self.win.after_idle(lambda w=self.win: attach_export_bar(w))
        c = ctx
        tk.Label(self.win, text=f"{crop_name} · роки: {', '.join(map(str, c['years']))} · сортів: {len(c['cultivars'])} · спостережень: {c['n_obs']}" + ((" · стандарти груп: " + ", ".join(f"«{s_}» ({g})" for g, s_ in self._gstd.items())) if self._gstd else (f" · стандарт: {c['standard']}" if c["standard"] else " · опорне значення – середнє за сортами")),
                 font=RB, anchor="w").pack(fill=tk.X, padx=10, pady=(6, 0))
        notes = []
        if c["errors"]: notes.append(f"Не розпізнано дат: {len(c['errors'])} (їх пропущено).")
        if c["warnings"]: notes.append(f"Попередження: {len(c['warnings'])} (порушено порядок фаз або дата з іншого року): " + "; ".join(f"{w['name']} {w['year']} – {w['msg']}" for w in c["warnings"][:3]) + (" …" if len(c["warnings"]) > 3 else ""))
        if notes: tk.Label(self.win, text=" ".join(notes), font=SM, fg="#8c5a1a", wraplength=1180, justify="left", anchor="w").pack(fill=tk.X, padx=10)
        self.nb = ttk.Notebook(self.win); self.nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        self._tab_means(); self._tab_standard(); self._tab_durations(); self._tab_anova()
        if c["sums"] is not None: self._tab_sums()
        self._tab_charts()

    # ── допоміжне ──
    def _tab(self, title):
        f = tk.Frame(self.nb, padx=8, pady=6); self.nb.add(f, text=title); return f

    def _table(self, parent, headers, rows, tags=None, height=None, expand=True):
        frm, tv = make_tv(parent, headers, rows, min_col=62); frm.pack(fill=tk.BOTH, expand=expand, pady=(2, 6))
        for tg, bg in {"std": "#e3f2fd", "early": CLASS_BG["ранній"], "late": CLASS_BG["пізній"], "sig": "#fff9c4"}.items(): tv.tag_configure(tg, background=bg)
        if tags:
            for iid, tg in zip(tv.get_children(), tags):
                if tg: tv.item(iid, tags=(tg,))
        if height:
            try: tv.configure(height=height)
            except tk.TclError: pass
        return tv

    def _phase_heads(self): return [P.phase_label(p) for p in self.ctx["phases"]]

    # ── вкладки ──
    def _tab_means(self):
        c = self.ctx; f = self._tab("Середні дати"); keys = [p["key"] for p in c["phases"]]
        tk.Label(f, text="Середня дата настання фази за всі роки й повторності (± SD, діб).", font=SM, fg="#555").pack(anchor="w")
        rows, tags = [], []
        for cv in c["cultivars"]:
            n = max(c["summ"][(cv, k)]["n"] for k in keys); rows.append([cv, str(n)] + [_date_cell(c["summ"][(cv, k)]) for k in keys]); tags.append("std" if cv in self._stds else None)
        self._table(f, ["Сорт", "n"] + self._phase_heads(), rows, tags)
        tk.Label(f, text="n – найбільша кількість спостережень (роки × повторності) по фазах. Дати – за нормованим номером дня року (високосні роки узгоджено).", font=SM, fg="#777", wraplength=1150, justify="left").pack(anchor="w")

    def _tab_standard(self):
        c = self.ctx; f = self._tab("Стандарт і групи"); keys = [p["key"] for p in c["phases"]]
        ref = ("стандарту своєї групи стиглості" if self._gstd else ("стандарту «" + c["standard"] + "»" if c["standard"] else "середнього за сортами"))
        tk.Label(f, text=f"Різниця середніх дат відносно {ref}, діб: «−» раніше, «+» пізніше. Ранній ≤ −{_f(c['thr'], 1).replace('−', '')} діб, пізній ≥ +{_f(c['thr'], 1).replace('−', '')} діб.", font=SM, fg="#555").pack(anchor="w")
        gcols = (lambda cv: [self._grp.get(cv, "–"), (c["ref_of"] or {}).get(cv) or "–"]) if self._gstd else (lambda cv: [])
        rows = [[cv] + gcols(cv) + [("станд." if cv in self._stds and (not self._gstd or (c["ref_of"] or {}).get(cv) == cv) else _f(c["vs"][(cv, k)][0], 1, True)) if c["summ"][(cv, k)]["n"] else "–" for k in keys] for cv in c["cultivars"]]
        self._table(f, ["Сорт"] + (["Група", "Стандарт групи"] if self._gstd else []) + self._phase_heads(), rows, ["std" if cv in self._stds else None for cv in c["cultivars"]], expand=False)
        tk.Label(f, text="Групування сорту за ключовою фазою", font=RB).pack(anchor="w", pady=(8, 0))
        bar = tk.Frame(f); bar.pack(fill=tk.X); tk.Label(bar, text="Ключова фаза:", font=RF).pack(side=tk.LEFT)
        self.key_var = tk.StringVar(); labels = {P.phase_label(p): p["key"] for p in c["phases"]}; self._key_labels = labels
        default = next((p for p in reversed(c["phases"]) if p["key"] in ("pick", "harvest", "full", "phys", "eat", "ripe0")), c["phases"][-1]); self.key_var.set(P.phase_label(default))
        cb = ttk.Combobox(bar, textvariable=self.key_var, values=list(labels), state="readonly", width=48); cb.pack(side=tk.LEFT, padx=6); cb.bind("<<ComboboxSelected>>", lambda e: self._fill_groups())
        self.group_holder = tk.Frame(f); self.group_holder.pack(fill=tk.BOTH, expand=True); self._fill_groups()

    def _fill_groups(self):
        for w in self.group_holder.winfo_children(): w.destroy()
        c = self.ctx; k = self._key_labels[self.key_var.get()]
        order = sorted([cv for cv in c["cultivars"] if c["summ"][(cv, k)]["n"] > 0], key=lambda cv: c["summ"][(cv, k)]["mean"])
        g = (lambda cv: [self._grp.get(cv, "–")]) if self._gstd else (lambda cv: [])
        rows = [[cv] + g(cv) + [P.md_from_doy(c["summ"][(cv, k)]["mean"]), _f(c["vs"][(cv, k)][0], 1, True), c["vs"][(cv, k)][1] or "–"] for cv in order]
        tags = [{"ранній": "early", "пізній": "late"}.get(c["vs"][(cv, k)][1]) for cv in order]
        self._table(self.group_holder, ["Сорт (від раннього до пізнього)"] + (["Група стиглості"] if self._gstd else []) + ["Середня дата", "Різниця, діб" + (" (від стандарту групи)" if self._gstd else ""), "Клас"], rows, tags)

    def _tab_durations(self):
        c = self.ctx; f = self._tab("Тривалість періодів"); name = {p["key"]: p["name"] for p in c["phases"]}
        tk.Label(f, text="Тривалість між фазами, діб (середнє ± SD): різниця дат у межах одного року й повторності.", font=SM, fg="#555").pack(anchor="w")
        heads = ["Сорт"] + [f"{name[a]} → {name[b]}" for a, b in c["pairs"]]
        rows = []
        for cv in c["cultivars"]:
            row = [cv]
            for pr in c["pairs"]:
                s = c["dur"][(cv, pr)]; row.append("–" if s["n"] == 0 else (_f(s["mean"]) + (f" ±{_f(s['sd'])}" if s["n"] > 1 and not math.isnan(s["sd"]) else "")))
            rows.append(row)
        self._table(f, heads, rows, ["std" if cv in self._stds else None for cv in c["cultivars"]])

    def _tab_anova(self):
        c = self.ctx; f = self._tab("ANOVA і порівняння середніх"); bar = tk.Frame(f); bar.pack(fill=tk.X)
        tk.Label(bar, text="Метод порівняння середніх:", font=RB).pack(side=tk.LEFT)
        self.method_var = tk.StringVar(value=P.METHOD_NAME[self.method]); cb = ttk.Combobox(bar, textvariable=self.method_var, values=[n for _, n in P.METHODS], state="readonly", width=52); cb.pack(side=tk.LEFT, padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_method())
        tk.Label(bar, text=f"Сортів: {len(c['cultivars'])}.  3–5 сортів – НІР05; до 30 – Тьюкі; багато гібридів – Скотт–Кнотт або зі стандартом.", font=SM, fg="#555").pack(side=tk.LEFT, padx=8)
        self.an_body = tk.Frame(f); self.an_body.pack(fill=tk.BOTH, expand=True); self._build_anova_body()

    def _on_method(self):
        key = next(k for k, n in P.METHODS if n == self.method_var.get()); self.method = key; c = self.ctx
        self.comp = {k: P.compare_means(c["records"], k, c["anova"][k], key, c["standard"], ref_of=c.get("ref_of")) for k in [p["key"] for p in c["phases"]]}
        c["method"] = key; c["compare"] = self.comp; self._build_anova_body()

    def _build_anova_body(self):
        for w in self.an_body.winfo_children(): w.destroy()
        c = self.ctx; f = self.an_body; keys = [p["key"] for p in c["phases"]]; an = c["anova"]; cp = self.comp
        k0 = next((cp[k] for k in keys if "error" not in cp[k]), None)
        tk.Label(f, text="Дисперсійний аналіз дат (номер дня року). Літера «a» – найраніша група; сорти зі спільною літерою істотно не відрізняються.", font=SM, fg="#555").pack(anchor="w")
        rows = []
        for p_ in c["phases"]:
            a = an[p_["key"]]; m = cp[p_["key"]]
            if "error" in a: rows.append([P.phase_label(p_), "–", "–", "–", "–", "–", a["error"], ""]); continue
            pall = m["p_overall"]; crit = "–" if m.get("crit") is None else _f(m["crit"], 1)
            rows.append([P.phase_label(p_), _f(a["F"], 2), "<0,0001" if pall < 1e-4 else _f(pall, 4), "–" if math.isnan(a["h2"]) else _f(a["h2"], 2), crit, a["design"],
                         "істотна" if pall < 0.05 else "неістотна", m["label"] + (f" ({m['ngroups']} гр.)" if m.get("ngroups") else "")])
        tags = ["sig" if "error" not in an[p_["key"]] and cp[p_["key"]]["p_overall"] < 0.05 else None for p_ in c["phases"]]
        self._table(f, ["Фаза", "F (сорт)", "p (критерій методу)", "H²", "Крит. різниця, діб", "Схема", "Вплив сорту", "Порівняння"], rows, tags, height=min(8, len(rows) + 1), expand=False)
        tk.Label(f, text="H² – успадковуваність на середніх за сортами (1 − 1/F; для кількох років 1 − MS(сорт×рік)/MS(сорт)); важливо для добору гібридів.", font=SM, fg="#777").pack(anchor="w")
        if k0 and k0["note"]: tk.Label(f, text=k0["note"], font=SM, fg="#8c5a1a", wraplength=1150, justify="left").pack(anchor="w", pady=(2, 0))
        tk.Label(f, text="Середні дати з позначками методу", font=RB).pack(anchor="w", pady=(4, 0))
        mrows = []
        for cv in c["cultivars"]:
            row = [cv]
            for k in keys:
                s_ = c["summ"][(cv, k)]; g = cp[k].get("groups", {}).get(cv, "") if "error" not in cp[k] else ""
                row.append("–" if s_["n"] == 0 else P.md_from_doy(s_["mean"]) + (" " + g if g else ""))
            mrows.append(row)
        self._table(f, ["Сорт"] + self._phase_heads(), mrows, ["std" if cv in self._stds else None for cv in c["cultivars"]], height=min(8, len(mrows) + 1), expand=False)
        bar = tk.Frame(f); bar.pack(fill=tk.X, pady=(6, 0)); tk.Label(bar, text="Таблиця ANOVA для фази:", font=RB).pack(side=tk.LEFT)
        self.an_var = tk.StringVar(value=P.phase_label(c["phases"][0])); self._an_labels = {P.phase_label(p_): p_["key"] for p_ in c["phases"]}
        cb = ttk.Combobox(bar, textvariable=self.an_var, values=list(self._an_labels), state="readonly", width=48); cb.pack(side=tk.LEFT, padx=6); cb.bind("<<ComboboxSelected>>", lambda e: self._fill_anova())
        self.an_holder = tk.Frame(f); self.an_holder.pack(fill=tk.BOTH, expand=True); self._fill_anova()

    def _fill_anova(self):
        for w in self.an_holder.winfo_children(): w.destroy()
        k = self._an_labels[self.an_var.get()]; a = self.ctx["anova"][k]
        if "error" in a: tk.Label(self.an_holder, text=a["error"], font=RF, fg="#8c5a1a").pack(anchor="w"); return
        rows = [[r["name"], _f(r["ss"], 3), "" if r["df"] is None or (isinstance(r["df"], float) and math.isnan(r["df"])) else str(int(r["df"])), _f(r["ms"], 3), _f(r["F"], 3), "" if math.isnan(r["p"]) else ("<0,0001" if r["p"] < 1e-4 else _f(r["p"], 4))] for r in a["table"]]
        self._table(self.an_holder, ["Джерело", "SS", "df", "MS", "F", "p"], rows, expand=False)
        tk.Label(self.an_holder, text=f"Схема: {a['design']}; MS залишку = {_f(a['mse'], 3)}, df = {a['dfe']}; НІР05 = {_f(a['nir'], 2)} діб; H² = {_f(a['h2'], 2)}.", font=SM, fg="#555").pack(anchor="w")

    def _tab_sums(self):
        c = self.ctx; f = self._tab("Суми температур"); cfg = c["sum_cfg"]; keys = [p["key"] for p in c["phases"]]
        what = "активних температур (САТ: Σ t за t > " if cfg["kind"] == "sat" else "ефективних температур (СЕТ: Σ (t − "
        start = f"з {int(cfg['start'][2]):02d}.{int(cfg['start'][1]):02d} щороку" if cfg["start"][0] == "md" else "від дати фази «" + next((p["name"] for p in c["all_phases"] if p["key"] == cfg["start"][1]), cfg["start"][1]) + "»"
        tk.Label(f, text=f"Сума {what}{_f(float(cfg['base']), 1).replace('−', '-')}{' °C)' if cfg['kind'] == 'sat' else ' °C) за t > ' + _f(float(cfg['base']), 1) + ' °C)'}, {start} до дати настання фази включно; середнє ± SD, °C·діб.", font=SM, fg="#555", wraplength=1150, justify="left").pack(anchor="w")
        rows = []
        for cv in c["cultivars"]:
            row = [cv]
            for k in keys:
                s = c["sums"][(cv, k)]; row.append("–" if s["n"] == 0 else f"{s['mean']:.0f}" + (f" ±{s['sd']:.0f}" if s["n"] > 1 and not math.isnan(s["sd"]) else ""))
            rows.append(row)
        self._table(f, ["Сорт"] + self._phase_heads(), rows, ["std" if cv in self._stds else None for cv in c["cultivars"]])
        if c["nan_sums"]: tk.Label(f, text=f"Для {c['nan_sums']} спостережень погода не покриває період (покриття < 95 %) – їх не враховано.", font=SM, fg="#8c5a1a").pack(anchor="w")

    # ── графіки ──
    def _tab_charts(self):
        c = self.ctx; f = self._tab("Графіки"); bar = tk.Frame(f); bar.pack(fill=tk.X)
        self.chart_var = tk.StringVar(value=CHARTS[0]); cb = ttk.Combobox(bar, textvariable=self.chart_var, values=CHARTS, state="readonly", width=60); cb.pack(side=tk.LEFT)
        tk.Label(bar, text="  Фаза:", font=RF).pack(side=tk.LEFT); self.cphase_var = tk.StringVar(value=P.phase_label(c["phases"][min(len(c["phases"]) - 1, 3 if len(c["phases"]) > 3 else 0)]))
        self._cp_labels = {P.phase_label(p): p["key"] for p in c["phases"]}; cb2 = ttk.Combobox(bar, textvariable=self.cphase_var, values=list(self._cp_labels), state="readonly", width=42); cb2.pack(side=tk.LEFT, padx=4)
        tk.Button(bar, text="💾 PNG…", font=RF, command=self._save_png).pack(side=tk.LEFT, padx=8)
        for w in (cb, cb2): w.bind("<<ComboboxSelected>>", lambda e: self._draw())
        self.chart_holder = tk.Frame(f); self.chart_holder.pack(fill=tk.BOTH, expand=True, pady=4); self._draw()

    def _subset(self, k):
        """Сорти для графіка: усі, якщо їх не більше MAX_SHOWN; інакше стандарт + найраніші й найпізніші за фазою k. → (сорти в порядку, примітка)."""
        c = self.ctx; have = [cv for cv in c["cultivars"] if c["summ"][(cv, k)]["n"] > 0]
        if len(have) <= MAX_SHOWN: return [cv for cv in c["cultivars"] if cv in have] or c["cultivars"], ""
        st_ = [x for x in self._stds if x in have]; srt = sorted(have, key=lambda cv: c["summ"][(cv, k)]["mean"]); half = max(1, (MAX_SHOWN - len(st_)) // 2)
        pick = set(srt[:half]) | set(srt[-half:]) | set(st_)
        return [cv for cv in c["cultivars"] if cv in pick], f"показано {len(pick)} із {len(have)} сортів: найраніші, найпізніші й стандарт"

    def _draw(self):
        for w in self.chart_holder.winfo_children(): w.destroy()
        kind = CHARTS.index(self.chart_var.get()); k = self._cp_labels[self.cphase_var.get()]
        fig = [self.fig_spectrum, self.fig_box, self.fig_dev, self.fig_dyn, self.fig_hist, self.fig_rank][kind](k)
        self.fig = fig; embed_figure(fig, self.chart_holder)

    def _save_png(self):
        if self.fig is None: return
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".png", filetypes=[("PNG", "*.png")], title="Зберегти графік")
        if p: self.fig.savefig(p, dpi=250, bbox_inches="tight", facecolor="white")

    def _empty(self, text):
        fig = Figure(figsize=(8, 3), dpi=100); ax = fig.add_subplot(111); ax.axis("off"); ax.text(0.5, 0.5, text, ha="center", va="center", fontfamily=FONT, fontsize=12, color="#8c5a1a", wrap=True); return fig

    def fig_spectrum(self, _k=None):
        c = self.ctx; phs = c["phases"]; cvs, note = self._subset(_k or phs[0]["key"]); n = len(cvs)
        fig = Figure(figsize=(11, max(3.6, 0.5 * n + 2.4)), dpi=100); ax = fig.add_subplot(111); col = {p["key"]: PALETTE[i % len(PALETTE)] for i, p in enumerate(phs)}; allx = []
        for i, cv in enumerate(cvs):
            y = n - 1 - i; pts = [(p["key"], c["summ"][(cv, p["key"])]) for p in phs if c["summ"][(cv, p["key"])]["n"] > 0]
            for (k0, s0), (k1, s1) in zip(pts, pts[1:]): ax.barh(y, s1["mean"] - s0["mean"], left=s0["mean"], height=0.56, color=col[k0], edgecolor="white", linewidth=0.8)
            for k, s in pts:
                allx.append(s["mean"]); ax.plot([s["mean"]], [y], marker="D", markersize=4.2, color="#222222", zorder=3)
                if s["n"] > 1 and not math.isnan(s["sd"]) and s["sd"] > 0: ax.errorbar(s["mean"], y, xerr=s["sd"], fmt="none", ecolor="#222222", elinewidth=0.9, capsize=2, zorder=3)
        if not allx: return self._empty("Немає даних для побудови.")
        ax.set_yticks(range(n)); ax.set_yticklabels(list(reversed(cvs)), fontfamily=FONT, fontsize=10); _dow_axis(ax, min(allx) - 4, max(allx) + 4); ax.set_xlim(min(allx) - 5, max(allx) + 5)
        ax.set_ylim(-0.7, n - 0.3); ax.grid(axis="x", alpha=0.3); ax.set_axisbelow(True); ax.set_xlabel("Дата (середня за роки й повторності; ромб – середня дата фази, лінія – ± SD)", fontfamily=FONT, fontsize=10)
        ax.set_title("Фенологічний спектр сортів" + (f" ({note})" if note else ""), fontfamily=FONT, fontsize=13 if not note else 11)
        short = lambda t, n=30: t if len(t) <= n else t[:n - 1].rstrip() + "…"
        hands = [Patch(color=col[p["key"]], label=short(p["name"])) for p in phs[:-1] if any(c["summ"][(cv, p["key"])]["n"] > 0 for cv in cvs)]
        if hands: ax.legend(handles=hands, title="Період, що починається з фази:", loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8.5, title_fontsize=9, frameon=False, prop={"family": FONT, "size": 8.5})
        fig.subplots_adjust(left=0.15, right=0.74 if hands else 0.97, bottom=0.14, top=0.9); return fig

    def fig_box(self, k):
        c = self.ctx; sub, note = self._subset(k); cvs = [cv for cv in sub if c["summ"][(cv, k)]["n"] > 0]
        if not cvs: return self._empty("Для цієї фази немає дат.")
        recs = [r for r in c["records"] if r["phase"] == k]; data = [[r["doy"] for r in recs if r["name"] == cv] for cv in cvs]
        fig = Figure(figsize=(max(7, 1.0 * len(cvs) + 3), 5.2), dpi=100); ax = fig.add_subplot(111)
        bp = ax.boxplot(data, widths=0.5, showmeans=True, patch_artist=True, meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "#222222", "markersize": 5}, medianprops={"color": "#222222"})
        for b in bp["boxes"]: b.set_facecolor("#dbe7f5"); b.set_edgecolor("#1a4b8c")
        years = sorted({r["year"] for r in recs}); ycol = {y: PALETTE[i % len(PALETTE)] for i, y in enumerate(years)}; rg = np.random.default_rng(3)
        for i, cv in enumerate(cvs, 1):
            for r in [r for r in recs if r["name"] == cv]: ax.scatter(i + rg.uniform(-0.16, 0.16), r["doy"], s=22, color=ycol[r["year"]], alpha=0.85, zorder=3, edgecolor="white", linewidth=0.4)
        ax.set_xticks(range(1, len(cvs) + 1)); ax.set_xticklabels(cvs, fontfamily=FONT, fontsize=10, rotation=30 if len(cvs) > 5 else 0, ha="right" if len(cvs) > 5 else "center")
        allv = [v for d in data for v in d]; _dow_axis(ax, min(allv) - 1, max(allv) + 1, "y"); ax.set_ylabel("Дата настання фази", fontfamily=FONT, fontsize=11); ax.grid(axis="y", alpha=0.3)
        pname = next(p["name"] for p in c["phases"] if p["key"] == k); ax.set_title(f"{pname}: розподіл дат за сортами" + (f"\n({note})" if note else ""), fontfamily=FONT, fontsize=13 if not note else 11)
        if len(years) > 1: ax.legend(handles=[Patch(color=ycol[y], label=str(y)) for y in years], title="Рік", loc="best", prop={"family": FONT, "size": 9}, frameon=False)
        fig.tight_layout(); return fig

    def fig_dev(self, k):
        c = self.ctx; sub, note = self._subset(k); cvs = [cv for cv in sub if c["summ"][(cv, k)]["n"] > 0]
        if not cvs: return self._empty("Для цієї фази немає дат.")
        order = sorted(cvs, key=lambda cv: c["vs"][(cv, k)][0]); vals = [c["vs"][(cv, k)][0] for cv in order]
        fig = Figure(figsize=(8.5, max(3.2, 0.42 * len(order) + 1.8)), dpi=100); ax = fig.add_subplot(111)
        cols = [{"ранній": "#2e7d32", "пізній": "#e65100"}.get(c["vs"][(cv, k)][1], "#78909c") for cv in order]
        ax.barh(range(len(order)), vals, color=cols, height=0.62); ax.axvline(0, color="#222222", linewidth=1)
        for i, v in enumerate(vals): ax.text(v + (0.15 if v >= 0 else -0.15), i, _f(v, 1, True), va="center", ha="left" if v >= 0 else "right", fontfamily=FONT, fontsize=9)
        ax.set_yticks(range(len(order))); ax.set_yticklabels(order, fontfamily=FONT, fontsize=10); ax.grid(axis="x", alpha=0.3); ax.set_axisbelow(True)
        lim = max(1.0, max(abs(v) for v in vals)) * 1.25; ax.set_xlim(-lim, lim); ref = ("стандарту своєї групи" if self._gstd else (f"стандарту «{c['standard']}»" if c["standard"] else "середнього за сортами"))
        ax.set_xlabel(f"Різниця від {ref}, діб (− раніше, + пізніше)", fontfamily=FONT, fontsize=10); pname = next(p["name"] for p in c["phases"] if p["key"] == k)
        ax.set_title(pname + (f"\n({note})" if note else ""), fontfamily=FONT, fontsize=13 if not note else 11); ax.legend(handles=[Patch(color="#2e7d32", label="ранній"), Patch(color="#78909c", label="середній"), Patch(color="#e65100", label="пізній")], loc="lower right", prop={"family": FONT, "size": 9}, frameon=False)
        fig.tight_layout(); return fig

    def fig_dyn(self, k):
        c = self.ctx; years = c["years"]; sub, note = self._subset(k)
        if len(years) < 2: return self._empty("Для динаміки потрібні дані щонайменше за два роки.")
        fig = Figure(figsize=(9.5, 5.2), dpi=100); ax = fig.add_subplot(111); allv = []
        for i, cv in enumerate(sub):
            xs, ys = [], []
            for y in years:
                v = [r["doy"] for r in c["records"] if r["phase"] == k and r["name"] == cv and r["year"] == y]
                if v: xs.append(y); ys.append(float(np.mean(v)))
            if xs: ax.plot(xs, ys, marker="o", linewidth=1.8, color=PALETTE[i % len(PALETTE)], label=cv, linestyle="-" if cv not in self._stds else "--"); allv += ys
        if not allv: return self._empty("Для цієї фази немає дат.")
        ax.set_xticks(years); ax.set_xticklabels([str(y) for y in years], fontfamily=FONT, fontsize=10); _dow_axis(ax, min(allv) - 1, max(allv) + 1, "y"); ax.grid(alpha=0.3); ax.set_xlabel("Рік", fontfamily=FONT, fontsize=11)
        pname = next(p["name"] for p in c["phases"] if p["key"] == k); ax.set_title(f"{pname}: середня дата за роками" + (f"\n({note})" if note else ""), fontfamily=FONT, fontsize=13 if not note else 11)
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=False, prop={"family": FONT, "size": 9}); fig.subplots_adjust(right=0.76, left=0.1, bottom=0.12); return fig

    def fig_hist(self, k):
        """Розподіл середніх дат усіх сортів: корисний для десятків і сотень гібридів; стандарт і межі «раннього/пізнього» позначено."""
        c = self.ctx; have = [cv for cv in c["cultivars"] if c["summ"][(cv, k)]["n"] > 0]
        if len(have) < 2: return self._empty("Для гістограми потрібно щонайменше два сорти з датами цієї фази.")
        v = np.array([c["summ"][(cv, k)]["mean"] for cv in have]); fig = Figure(figsize=(9.5, 5.2), dpi=100); ax = fig.add_subplot(111)
        bins = max(5, min(40, int(round(math.sqrt(len(v)) * 1.6)))); ax.hist(v, bins=bins, color="#9ecae1", edgecolor="#1a4b8c")
        ref = c["ref"][k]; thr = c["thr"]
        if self._gstd:                                                  # кілька стандартів: лінія кожного; класи – відносно стандарту своєї групи
            for i_, (g, s_) in enumerate(self._gstd.items()):
                x = c["summ"].get((s_, k), {"n": 0})
                if x["n"]: ax.axvline(x["mean"], color=PALETTE[i_ % len(PALETTE)], lw=1.6, label=f"стандарт «{s_}» ({g}): {P.md_from_doy(x['mean'])}")
        else:
            for x, col, lab in ((ref, "#222222", "стандарт" if c["standard"] else "середнє за сортами"), (ref - thr, "#2e7d32", "межа «ранній»"), (ref + thr, "#e65100", "межа «пізній»")):
                if not math.isnan(x): ax.axvline(x, color=col, lw=1.4, ls="-" if col == "#222222" else "--", label=f"{lab} ({P.md_from_doy(x)})")
        ne = sum(1 for cv in have if c["vs"][(cv, k)][1] == "ранній"); nl = sum(1 for cv in have if c["vs"][(cv, k)][1] == "пізній")
        _dow_axis(ax, v.min() - 1, v.max() + 1); ax.set_xlabel("Середня дата настання фази", fontfamily=FONT, fontsize=11); ax.set_ylabel("Кількість сортів", fontfamily=FONT, fontsize=11); ax.grid(axis="y", alpha=0.3)
        pname = next(p["name"] for p in c["phases"] if p["key"] == k); ax.set_title(f"{pname}: розподіл середніх дат {len(have)} сортів\nранніх {ne}, середніх {len(have) - ne - nl}, пізніх {nl}", fontfamily=FONT, fontsize=12)
        ax.legend(prop={"family": FONT, "size": 9}, frameon=False); fig.tight_layout(); return fig

    def fig_rank(self, k):
        """Сорти за зростанням середньої дати (ранжований профіль): ± SD – смуга; колір – клас (ранній / середній / пізній відносно стандарту)."""
        c = self.ctx; have = sorted([cv for cv in c["cultivars"] if c["summ"][(cv, k)]["n"] > 0], key=lambda cv: c["summ"][(cv, k)]["mean"])
        if len(have) < 2: return self._empty("Для профілю потрібно щонайменше два сорти з датами цієї фази.")
        m = np.array([c["summ"][(cv, k)]["mean"] for cv in have]); sd = np.array([0.0 if math.isnan(c["summ"][(cv, k)]["sd"]) else c["summ"][(cv, k)]["sd"] for cv in have]); x = np.arange(1, len(have) + 1)
        col = [{"ранній": "#2e7d32", "пізній": "#e65100"}.get(c["vs"][(cv, k)][1], "#78909c") for cv in have]
        fig = Figure(figsize=(10.5, 5.4), dpi=100); ax = fig.add_subplot(111); ax.fill_between(x, m - sd, m + sd, color="#cfd8dc", alpha=0.7, lw=0, label="± SD")
        ax.scatter(x, m, c=col, s=max(8, 90 - len(have) * 0.3), zorder=3, edgecolor="white", linewidth=0.3)
        for st_ in sorted(self._stds):
            if st_ in have: i = have.index(st_); ax.scatter([x[i]], [m[i]], marker="*", s=260, color="#1a4b8c", zorder=4, label="стандарт " + st_)
        if len(have) <= 40: ax.set_xticks(x); ax.set_xticklabels(have, rotation=70, ha="right", fontfamily=FONT, fontsize=8)
        else: ax.set_xlabel(f"Сорти від найранішого до найпізнішого (всього {len(have)})", fontfamily=FONT, fontsize=11)
        _dow_axis(ax, float((m - sd).min()) - 1, float((m + sd).max()) + 1, "y"); ax.grid(alpha=0.3); pname = next(p["name"] for p in c["phases"] if p["key"] == k)
        ax.set_title(f"{pname}: ранжований профіль середніх дат", fontfamily=FONT, fontsize=13); ax.legend(handles=[Patch(color="#2e7d32", label="ранній"), Patch(color="#78909c", label="середній"), Patch(color="#e65100", label="пізній")] + ax.get_legend_handles_labels()[0][:0],
                                                                                                      prop={"family": FONT, "size": 9}, frameon=False, loc="upper left"); fig.tight_layout(); return fig
