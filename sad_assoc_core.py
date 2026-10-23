# sad_assoc_core.py – S.A.D. v2.1: зв'язок змінних різних типів (без tkinter)
# -*- coding: utf-8 -*-
"""
1) Кількісна ознака × номінальна (група):  кореляційне відношення η, η², ω², ε² (однофакторний ANOVA), довірчий інтервал η²
   через нецентральний F-розподіл (Steiger 2004); непараметричний аналог – ε² за Kruskal–Wallis (Tomczak & Tomczak 2014).
2) Дві групи × кількісна ознака:  рангово-бісеріальний коефіцієнт r_rb = 2U₁/(n₁n₂) − 1 (збігається з δ Кліффа),
   ймовірність переваги P(X > Y) = U₁/(n₁n₂), точково-бісеріальний r_pb (= кореляція Пірсона з індикатором групи).
3) Номінальна × номінальна (таблиця спряженості):  χ², точний тест (Фішер для 2×2, Монте-Карло для r×c), φ, V Крамера
   (зі зміщенням і скоригований за Bergsma 2013), T Чупрова, C Пірсона, відношення шансів, скориговані стандартизовані залишки.
Біссеріальний коефіцієнт (штучно розділена нормальна ознака) свідомо НЕ реалізовано: він вимагає припущення про нормальність
прихованої змінної і часто застосовується хибно.
"""
import math
import numpy as np
from scipy import stats, optimize
from sad_gxe_core import BreedingError

NAN = float("nan")


# ═══════════════════════════════════════════════════════════════
# 1. η і суміжні розміри ефекту (група × кількісна ознака)
# ═══════════════════════════════════════════════════════════════
def eta_squared(groups, alpha=0.05):
    """groups – список масивів (по групах). Повертає dict: η², η, ω², ε², F, df, p, довірчий інтервал η²,
    Kruskal–Wallis (H, p, ε²_H), Levene."""
    gs = [np.asarray(g, float) for g in groups]
    if any(np.any(np.isnan(g)) for g in gs): raise BreedingError("У даних є порожні або нечислові значення.")
    if len(gs) < 2: raise BreedingError("Потрібно щонайменше 2 групи.")
    if any(len(g) < 2 for g in gs): raise BreedingError("У кожній групі потрібно щонайменше 2 спостереження (інакше немає оцінки похибки).")
    k = len(gs); n = sum(len(g) for g in gs); allv = np.concatenate(gs); gm = allv.mean()
    ssb = sum(len(g) * (g.mean() - gm) ** 2 for g in gs); ssw = sum(np.sum((g - g.mean()) ** 2) for g in gs); sst = ssb + ssw
    df1, df2 = k - 1, n - k
    if df2 < 1: raise BreedingError("Немає ступенів свободи для похибки: у групах має бути більше спостережень, ніж груп.")
    if sst <= 0: raise BreedingError("Усі значення однакові – кореляційне відношення не визначене.")
    msw = ssw / df2
    F = (ssb / df1) / msw if msw > 0 else float("inf"); p = float(stats.f.sf(F, df1, df2)) if msw > 0 else 0.0
    eta2 = ssb / sst
    omega2 = (ssb - df1 * msw) / (sst + msw); eps2 = (ssb - df1 * msw) / sst
    # довірчий інтервал η² (Steiger): шукаємо нецентральність λ: P(F ≤ F_obs | λ) = 1 − α/2 (нижня), α/2 (верхня); η² = λ/(λ + N)
    lo = hi = NAN
    if msw > 0:
        def ncp_for(prob):
            f = lambda lam: stats.ncf.cdf(F, df1, df2, lam) - prob
            if f(1e-9) < 0: return 0.0                    # навіть при λ ≈ 0 ймовірність нижча за цільову → межа 0
            up = max(10.0, F * df1 * 5)
            while f(up) > 0 and up < 1e7: up *= 2
            return float(optimize.brentq(f, 1e-9, up, xtol=1e-9))
        lam_lo = ncp_for(1 - alpha / 2); lam_hi = ncp_for(alpha / 2)
        lo, hi = lam_lo / (lam_lo + n), lam_hi / (lam_hi + n)
    kw = stats.kruskal(*gs) if np.ptp(allv) > 0 else None
    lev = stats.levene(*gs, center="median") if k >= 2 and n > k else None
    return {"k": k, "n": n, "df1": df1, "df2": df2, "F": float(F), "p": p, "eta2": float(eta2), "eta": math.sqrt(eta2),
            "omega2": float(omega2), "eps2": float(eps2), "ci_lo": lo, "ci_hi": hi,
            "kw_H": float(kw.statistic) if kw else NAN, "kw_p": float(kw.pvalue) if kw else NAN,
            "kw_eps2": float(kw.statistic) / (n - 1) if kw else NAN,
            "levene_p": float(lev.pvalue) if lev is not None else NAN,
            "means": [float(g.mean()) for g in gs], "sds": [float(g.std(ddof=1)) for g in gs], "ns": [len(g) for g in gs],
            "medians": [float(np.median(g)) for g in gs], "ssb": float(ssb), "ssw": float(ssw)}


def eta_strength(e2):
    """Умовна шкала Cohen (1988) для η²: 0,01 малий, 0,06 середній, 0,14 великий."""
    if e2 is None or math.isnan(e2): return "н/д"
    return "дуже малий" if e2 < 0.01 else "малий" if e2 < 0.06 else "середній" if e2 < 0.14 else "великий"


# ═══════════════════════════════════════════════════════════════
# 2. Дві групи: рангово-бісеріальний і точково-бісеріальний
# ═══════════════════════════════════════════════════════════════
def _u1(x, y):
    nx, ny = len(x), len(y)
    r = stats.rankdata(np.concatenate([x, y]))
    return r[:nx].sum() - nx * (nx + 1) / 2


def two_group_effects(x, y, alpha=0.05, n_boot=2000, seed=20240611):
    x = np.asarray(x, float); y = np.asarray(y, float)
    if np.any(np.isnan(x)) or np.any(np.isnan(y)): raise BreedingError("У даних є порожні або нечислові значення.")
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2: raise BreedingError("У кожній групі потрібно щонайменше 2 спостереження.")
    if np.ptp(np.concatenate([x, y])) == 0: raise BreedingError("Усі значення однакові – коефіцієнти не визначені.")
    u1 = _u1(x, y); cles = u1 / (nx * ny); rrb = 2 * cles - 1
    mw = stats.mannwhitneyu(x, y, alternative="two-sided")
    rng = np.random.default_rng(seed); bs = np.empty(n_boot)
    for b in range(n_boot):
        bs[b] = 2 * _u1(rng.choice(x, nx), rng.choice(y, ny)) / (nx * ny) - 1
    lo, hi = float(np.quantile(bs, alpha / 2)), float(np.quantile(bs, 1 - alpha / 2))
    ind = np.r_[np.ones(nx), np.zeros(ny)]; allv = np.r_[x, y]
    rpb = float(np.corrcoef(allv, ind)[0, 1]); df = nx + ny - 2
    t_ = rpb * math.sqrt(df / max(1 - rpb ** 2, 1e-300)); p_pb = float(2 * stats.t.sf(abs(t_), df))
    z = math.atanh(rpb) if abs(rpb) < 1 else NAN; se = 1 / math.sqrt(nx + ny - 3)
    pb_lo, pb_hi = (math.tanh(z - stats.norm.ppf(1 - alpha / 2) * se), math.tanh(z + stats.norm.ppf(1 - alpha / 2) * se)) if not math.isnan(z) else (NAN, NAN)
    welch = stats.ttest_ind(x, y, equal_var=False)
    return {"n1": nx, "n2": ny, "U1": float(u1), "U_mw": float(mw.statistic), "p_mw": float(mw.pvalue), "cles": float(cles), "rrb": float(rrb),
            "rrb_lo": lo, "rrb_hi": hi, "rpb": rpb, "rpb_p": p_pb, "rpb_lo": pb_lo, "rpb_hi": pb_hi, "p_welch": float(welch.pvalue),
            "mean": (float(x.mean()), float(y.mean())), "median": (float(np.median(x)), float(np.median(y))),
            "sd": (float(x.std(ddof=1)), float(y.std(ddof=1))), "n_boot": n_boot}


def rrb_strength(r):
    a = abs(r)
    return "дуже малий" if a < 0.11 else "малий" if a < 0.28 else "середній" if a < 0.43 else "великий"       # Vargha & Delaney: δ 0,147 / 0,33 / 0,474


# ═══════════════════════════════════════════════════════════════
# 3. Таблиці спряженості
# ═══════════════════════════════════════════════════════════════
def crosstab(a_labels, b_labels, counts=None):
    """Рядки-спостереження → таблиця. Повертає (table, рядки, стовпці)."""
    a = [str(x) for x in a_labels]; b = [str(x) for x in b_labels]
    w = np.ones(len(a)) if counts is None else np.asarray(counts, float)
    if np.any(w < 0) or np.any(w != np.round(w)): raise BreedingError("Частоти мають бути невід'ємними цілими числами.")
    rl = list(dict.fromkeys(a)); cl = list(dict.fromkeys(b)); T = np.zeros((len(rl), len(cl)), int)
    for x, y, c in zip(a, b, w): T[rl.index(x), cl.index(y)] += int(c)
    return T, rl, cl


def _chi2(T):
    T = np.asarray(T, float); n = T.sum(); E = np.outer(T.sum(1), T.sum(0)) / n
    with np.errstate(divide="ignore", invalid="ignore"): c = np.nansum((T - E) ** 2 / E)
    return float(c), E


def _v_corrected(T):
    """V Крамера з поправкою на зміщення (Bergsma 2013)."""
    T = np.asarray(T, float); n = T.sum(); r, c = T.shape; chi2, _ = _chi2(T); phi2 = chi2 / n
    phi2c = max(0.0, phi2 - (r - 1) * (c - 1) / (n - 1)); rc = r - (r - 1) ** 2 / (n - 1); cc = c - (c - 1) ** 2 / (n - 1)
    d = min(rc - 1, cc - 1)
    return math.sqrt(phi2c / d) if d > 0 else NAN


def contingency_analysis(table, alpha=0.05, n_boot=2000, n_mc=20000, seed=20240611):
    T = np.asarray(table, float)
    if T.ndim != 2: raise BreedingError("Таблиця спряженості має бути двовимірною.")
    if np.any(T < 0) or np.any(T != np.round(T)): raise BreedingError("Частоти мають бути невід'ємними цілими числами.")
    T = T.astype(int); warns = []
    keep_r = T.sum(1) > 0; keep_c = T.sum(0) > 0
    if not keep_r.all() or not keep_c.all():
        warns.append("Рядки/стовпці з нульовою сумою виключено з аналізу."); T = T[keep_r][:, keep_c]
    r, c = T.shape; n = int(T.sum())
    if r < 2 or c < 2: raise BreedingError("Потрібно щонайменше 2 рядки й 2 стовпці з ненульовими частотами.")
    if n < 5: raise BreedingError("Замало спостережень для аналізу таблиці спряженості.")
    chi2, E = _chi2(T); dof = (r - 1) * (c - 1); p_chi = float(stats.chi2.sf(chi2, dof))
    out = {"table": T, "r": r, "c": c, "n": n, "expected": E, "chi2": chi2, "dof": dof, "p_chi2": p_chi}
    small = float(np.mean(E < 5)); out["min_expected"] = float(E.min()); out["share_small"] = small
    if E.min() < 1 or small > 0.2:
        warns.append(f"Малі очікувані частоти (мінімум {E.min():.2f}; {100 * small:.0f} % клітинок < 5): χ²-наближення ненадійне – орієнтуйтеся на точний тест.")
    rng_seed = np.random.default_rng(seed)
    if r == 2 and c == 2:
        out["yates_p"] = float(stats.chi2_contingency(T, correction=True)[1])
        fe = stats.fisher_exact(T); out["p_exact"] = float(fe.pvalue); out["exact_kind"] = "точний тест Фішера"
        a_, b_, c_, d_ = T.ravel().astype(float); zero = (T == 0).any()
        aa, bb, cc, dd = (a_ + .5, b_ + .5, c_ + .5, d_ + .5) if zero else (a_, b_, c_, d_)
        orr = aa * dd / (bb * cc); se = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd); zc = stats.norm.ppf(1 - alpha / 2)
        out.update(OR=float(orr), OR_lo=float(orr * math.exp(-zc * se)), OR_hi=float(orr * math.exp(zc * se)), OR_corrected=bool(zero))
        out["phi"] = float((a_ * d_ - b_ * c_) / math.sqrt((a_ + b_) * (c_ + d_) * (a_ + c_) * (b_ + d_)))
        if zero: warns.append("У таблиці є нульова клітинка: відношення шансів і його інтервал розраховано з поправкою 0,5 до кожної клітинки (Haldane–Anscombe).")
    else:
        sim = stats.random_table(T.sum(1), T.sum(0), seed=rng_seed).rvs(n_mc)
        Es = E[None, :, :]; sims = np.nansum((sim - Es) ** 2 / Es, axis=(1, 2))
        out["p_exact"] = float((1 + np.sum(sims >= chi2 - 1e-9)) / (n_mc + 1)); out["exact_kind"] = f"точний тест (Монте-Карло, {n_mc} таблиць із тими ж сумами)"
    m = min(r, c) - 1
    out["V"] = math.sqrt(chi2 / (n * m)); out["V_corr"] = _v_corrected(T)
    out["T"] = math.sqrt(chi2 / n / math.sqrt((r - 1) * (c - 1))); mm = min(r, c)
    out["C"] = math.sqrt(chi2 / (chi2 + n)); out["C_max"] = math.sqrt((mm - 1) / mm); out["C_adj"] = out["C"] / out["C_max"]
    # довірчий інтервал V (скоригованого): бутстреп – перевибірка n спостережень з мультиноміального розподілу
    brg = np.random.default_rng(seed + 1); pr = (T / n).ravel(); vs = []
    for _ in range(n_boot):
        tb = brg.multinomial(n, pr).reshape(r, c)
        if (tb.sum(1) > 0).all() and (tb.sum(0) > 0).all():
            v = _v_corrected(tb)
            if not math.isnan(v): vs.append(v)
    out["V_lo"], out["V_hi"] = ((float(np.quantile(vs, alpha / 2)), float(np.quantile(vs, 1 - alpha / 2))) if len(vs) > 0.8 * n_boot else (NAN, NAN))
    rows, cols = T.sum(1, keepdims=True), T.sum(0, keepdims=True)
    adj = (T - E) / np.sqrt(E * (1 - rows / n) * (1 - cols / n)); out["adj_resid"] = adj; out["adj_p"] = 2 * stats.norm.sf(np.abs(adj))
    out["resid_crit"] = float(stats.norm.ppf(1 - alpha / (2 * r * c)))
    out["warnings"] = warns
    return out


def v_strength(v, df_star):
    """Cohen (1988): межі для w = V·√df*, df* = min(r−1, c−1): 0,1 малий, 0,3 середній, 0,5 великий."""
    if v is None or math.isnan(v): return "н/д"
    w = v * math.sqrt(df_star)
    return "дуже малий" if w < 0.1 else "малий" if w < 0.3 else "середній" if w < 0.5 else "великий"
