# sad_control_core.py — S.A.D. v2.1: порівняння номерів зі стандартом (тест Дуннетта) без tkinter
# -*- coding: utf-8 -*-
"""
Порівняння кожного номера (сорту, лінії) зі стандартом (контролем).

Загальна лінійна модель: y = μ + блок + номер + ε (МНК через псевдообернену матрицю), тож працює для
повної рандомізації, блоків (RCBD), пропущених ділянок і неоднакової кількості повторностей.
Кожне порівняння — лінійний контраст «номер − стандарт» (або «номер − середнє кількох стандартів»).
Одночасні (поправлені) p-значення й довірчі інтервали — за Dunnett (1955): розподіл максимуму модулів
сумісних t-статистик, що є багатовимірним t-розподілом із кореляцією, виведеною з плану.

Джерела: Dunnett C.W. 1955 JASA 50:1096; Genz A., Bretz F. 2009 (чисельне інтегрування).
"""
import math, functools
import numpy as np
from scipy import stats, optimize
from sad_gxe_core import BreedingError

NAN = float("nan")
_MAXPTS = 50000
_SEED = 20240611        # фіксоване зерно: однакові дані → однакові p-значення
_ZN, _GN = 160, 96       # вузли квадратур Гаусса (по z і по χ²)
_MC_N = 400000           # розмір вибірки Монте-Карло (запасний метод)


def _need_mvt():
    if not hasattr(stats, "multivariate_t"):
        raise BreedingError("Тест Дуннетта потребує scipy ≥ 1.11 (pip install -U scipy).")


def _onefactor(R, tol=1e-6):
    """Якщо R = λλ' + diag(1 − λ²) (так для збалансованих планів і однофакторних схем), повертає λ, інакше None."""
    k = R.shape[0]
    if k == 1: return np.array([0.0])
    if k == 2:
        r = R[0, 1]
        return np.array([math.sqrt(r), math.sqrt(r)]) if r >= 0 else None
    lam = np.empty(k)
    for i in range(k):
        j, l = [m for m in range(k) if m != i][:2]
        v = R[i, j] * R[i, l] / R[j, l] if R[j, l] != 0 else -1
        if v < 0: return None
        lam[i] = math.sqrt(v)
    if np.any(lam >= 1.0): return None
    rec = np.outer(lam, lam) + np.diag(1 - lam ** 2)
    return lam if np.max(np.abs(rec - R)) < tol else None


_zx, _zw = np.polynomial.hermite_e.hermegauss(_ZN)
_zw = _zw / math.sqrt(2 * math.pi)


@functools.lru_cache(maxsize=256)
def _s_nodes(df):
    """Вузли й ваги для s = √(χ²_ν/ν): Гаусс–Лагерр для малих df; рівноймовірні квантилі χ² для великих
    (там гамма-функція переповнюється, а розподіл s вузький і гладкий)."""
    if df <= 60:
        from scipy.special import roots_genlaguerre
        gx, gw = roots_genlaguerre(_GN, df / 2.0 - 1.0)
        return np.sqrt(2.0 * gx / df), gw / math.gamma(df / 2.0)
    n = 110
    v = stats.chi2.ppf((np.arange(n) + 0.5) / n, df)
    return np.sqrt(v / df), np.full(n, 1.0 / n)


def _cdf_onefactor(lam, df, c, alternative):
    """P(max_j T_j < c) (одностороннє) чи P(max_j |T_j| < c) (двобічне) для t з однофакторною кореляцією."""
    from scipy.special import ndtr
    s, gw = _s_nodes(df)
    sq = np.sqrt(1.0 - lam ** 2)
    total = 0.0
    for zi, zw in zip(_zx, _zw):
        up = ndtr((c * s[:, None] - lam[None, :] * zi) / sq[None, :])
        if alternative == "two-sided":
            lo = ndtr((-c * s[:, None] - lam[None, :] * zi) / sq[None, :])
            prod = np.prod(np.clip(up - lo, 1e-300, 1.0), axis=1)
        else:
            prod = np.prod(np.clip(up, 1e-300, 1.0), axis=1)
        total += zw * float(np.dot(gw, prod))
    return min(max(total, 0.0), 1.0)


def _mvt_box(lower, upper, R, df):
    k = len(upper)
    if k == 1:
        return float(stats.t.cdf(upper[0], df) - stats.t.cdf(lower[0], df))
    mv = stats.multivariate_t(loc=np.zeros(k), shape=R, df=df, allow_singular=True)
    return float(mv.cdf(np.asarray(upper, float), lower_limit=np.asarray(lower, float),
                        maxpts=_MAXPTS, random_state=np.random.default_rng(_SEED)))


def _mc_max(R, df, alternative):
    """Запасний метод для довільної R і великих k: вибірка розподілу max|T| (або max T) методом Монте-Карло."""
    k = R.shape[0]
    Lc = np.linalg.cholesky(R + 1e-12 * np.eye(k))
    rng = np.random.default_rng(_SEED); out = []; chunk = max(1000, int(2e7 // k)); left = _MC_N
    while left > 0:
        m = min(chunk, left); Z = rng.standard_normal((m, k)) @ Lc.T
        S = np.sqrt(rng.chisquare(df, m) / df)[:, None]
        T = Z / S
        out.append(np.max(np.abs(T), axis=1) if alternative == "two-sided" else np.max(T, axis=1)); left -= m
    return np.sort(np.concatenate(out))


def _method(R):
    lam = _onefactor(R)
    if lam is not None: return "onefactor", lam
    return ("mvt" if R.shape[0] <= 15 else "mc"), None


def dunnett_pvalues(t, R, df, alternative="two-sided"):
    """Поправлені p-значення Дуннетта для статистик t (k) із кореляційною матрицею R."""
    t = np.asarray(t, float); k = len(t); out = np.full(k, NAN)
    if k == 1:                                                  # одне порівняння: точний t-розподіл
        if np.isnan(t[0]): return out
        out[0] = (2 * stats.t.sf(abs(t[0]), df) if alternative == "two-sided"
                  else stats.t.sf(t[0], df) if alternative == "greater" else stats.t.cdf(t[0], df))
        return out
    kind, lam = _method(R)
    stat = np.abs(t) if alternative == "two-sided" else (t if alternative == "greater" else -t)
    ok = ~np.isnan(stat)
    if kind == "mc":
        M = _mc_max(R, df, alternative)
        out[ok] = 1.0 - np.searchsorted(M, stat[ok], side="left") / len(M)
        return np.clip(out, 1.0 / len(M), 1.0)
    vals = stat[ok]
    if kind == "onefactor":
        if len(vals) > 30:                                      # гладка залежність: сітка + інтерполяція
            grid = np.linspace(vals.min(), vals.max(), 28)
            cg = np.array([_cdf_onefactor(lam, df, c, alternative) for c in grid])
            cv = np.interp(vals, grid, cg)
        else:
            cv = np.array([_cdf_onefactor(lam, df, c, alternative) for c in vals])
    else:
        big = 60.0
        cv = np.array([(_mvt_box([-c] * k, [c] * k, R, df) if alternative == "two-sided"
                        else _mvt_box([-big] * k, [c] * k, R, df)) for c in vals])
    out[ok] = np.clip(1.0 - cv, 0.0, 1.0)
    return out


def dunnett_critical(R, df, alpha=0.05, alternative="two-sided"):
    """Критичне значення Дуннетта c: P(max|Tⱼ| < c) = 1 − α (двобічне) чи P(max Tⱼ < c) = 1 − α."""
    k = R.shape[0]
    lo = stats.t.ppf(1 - alpha / (2 if alternative == "two-sided" else 1), df)
    if k == 1: return float(lo)
    kind, lam = _method(R)
    if kind == "mc":
        M = _mc_max(R, df, alternative)
        return float(np.quantile(M, 1 - alpha))
    big = 60.0
    if kind == "onefactor":
        f = lambda c: _cdf_onefactor(lam, df, c, alternative) - (1 - alpha)
    elif alternative == "two-sided":
        f = lambda c: _mvt_box([-c] * k, [c] * k, R, df) - (1 - alpha)
    else:
        f = lambda c: _mvt_box([-big] * k, [c] * k, R, df) - (1 - alpha)
    hi = stats.t.ppf(1 - alpha / (2 * k if alternative == "two-sided" else k), df) * 1.5 + 1.0
    if f(lo) >= 0: return float(lo)
    return float(optimize.brentq(f, lo, hi, xtol=1e-6))


# ═══════════════════════════════════════════════════════════════
def compare_to_control(entries, y, control, blocks=None, alpha=0.05, alternative="two-sided", ci=True):
    """entries — мітки номерів для кожної ділянки; y — значення; control — мітка стандарту або список
    міток (тоді порівнюємо з СЕРЕДНІМ кількох стандартів); blocks — повторність/блок (необов'язково).
    Повертає dict із таблицею по номерах, MSE, df та попередженнями."""
    _need_mvt()
    entries = [str(e) for e in entries]; y = np.asarray(y, float)
    if len(entries) != len(y): raise BreedingError("Довжини списків номерів і значень різні.")
    if np.any(np.isnan(y)): raise BreedingError("У даних є порожні або нечислові значення.")
    controls = [str(c) for c in (control if isinstance(control, (list, tuple)) else [control])]
    levels = list(dict.fromkeys(entries))
    for c in controls:
        if c not in levels: raise BreedingError(f"Стандарту «{c}» немає серед номерів у таблиці.")
    others = [l for l in levels if l not in controls]
    if len(others) < 1: raise BreedingError("Потрібен щонайменше один номер, окрім стандарту.")
    n = len(y)
    q = len(levels)
    idx = {l: i for i, l in enumerate(levels)}
    cols = [np.array([1.0 if e == l else 0.0 for e in entries]) for l in levels]
    nb = 0
    if blocks is not None:
        blocks = [str(b) for b in blocks]
        bl = list(dict.fromkeys(blocks)); nb = len(bl)
        for b in bl[1:]: cols.append(np.array([1.0 if x == b else 0.0 for x in blocks]))
    X = np.column_stack(cols)
    XtXp = np.linalg.pinv(X.T @ X)
    beta = XtXp @ (X.T @ y)
    rank = int(np.linalg.matrix_rank(X))
    df = n - rank
    if df < 1: raise BreedingError("Немає ступенів свободи для похибки: потрібні повторності номерів.")
    rss = float(np.sum((y - X @ beta) ** 2)); mse = rss / df
    p = X.shape[1]
    proj = np.eye(p) - XtXp @ (X.T @ X)               # нульовий простір: допустимі лише оцінювані контрасти
    def lvec(entry_weights):
        v = np.zeros(p)
        for e, w in entry_weights.items(): v[idx[e]] = w
        return v
    cw = {c: 1.0 / len(controls) for c in controls}
    ctrl_lm = lvec(cw)
    # LS-середні: ефект номера + середній ефект блоку
    def lsm_vec(entry_weights):
        v = lvec(entry_weights)
        if nb > 1: v[q:] = 1.0 / nb
        return v
    # контрасти «номер − стандарт»
    L = np.array([lvec({o: 1.0}) - ctrl_lm for o in others])
    bad = [others[i] for i in range(len(others)) if np.max(np.abs(L[i] @ proj)) > 1e-8]
    if bad:
        raise BreedingError("Порівняння неможливе (план не пов'язаний зі стандартом) для: " + ", ".join(bad[:6]) +
                            ". Номер і стандарт мають зустрічатися хоча б в одному спільному блоці.")
    d = L @ beta
    A = L @ XtXp @ L.T
    se = np.sqrt(np.maximum(np.diag(A), 0.0) * mse)
    with np.errstate(invalid="ignore", divide="ignore"):
        t = d / se
        Rm = A / np.sqrt(np.outer(np.diag(A), np.diag(A)))
    k = len(others)
    p_dun = dunnett_pvalues(t, Rm, df, alternative)
    crit = dunnett_critical(Rm, df, alpha, alternative) if (ci and k >= 1) else NAN
    if alternative == "two-sided":
        p_lsd = 2 * stats.t.sf(np.abs(t), df); tcrit = stats.t.ppf(1 - alpha / 2, df)
        ci_lo, ci_hi = d - crit * se, d + crit * se
    elif alternative == "greater":
        p_lsd = stats.t.sf(t, df); tcrit = stats.t.ppf(1 - alpha, df)
        ci_lo, ci_hi = d - crit * se, np.full(k, np.inf)
    else:
        p_lsd = stats.t.cdf(t, df); tcrit = stats.t.ppf(1 - alpha, df)
        ci_lo, ci_hi = np.full(k, -np.inf), d + crit * se
    ctrl_mean = float(lsm_vec(cw) @ beta)
    ctrl_se = math.sqrt(float(lsm_vec(cw) @ XtXp @ lsm_vec(cw)) * mse)
    rows = []
    ncount = {l: entries.count(l) for l in levels}
    for i, o in enumerate(others):
        lv = lsm_vec({o: 1.0}); lm = float(lv @ beta); lse = math.sqrt(float(lv @ XtXp @ lv) * mse)
        if alternative == "two-sided": sigp = p_dun[i] < alpha
        else: sigp = p_dun[i] < alpha
        verdict = ("достовірно вище стандарту" if (sigp and d[i] > 0) else
                   "достовірно нижче стандарту" if (sigp and d[i] < 0) else "не відрізняється")
        rows.append({"entry": o, "n": ncount[o], "mean": lm, "se": lse, "diff": float(d[i]), "se_diff": float(se[i]),
                     "pct": 100.0 * lm / ctrl_mean if ctrl_mean else NAN, "t": float(t[i]),
                     "p_dunnett": float(p_dun[i]), "p_lsd": float(p_lsd[i]), "ci_lo": float(ci_lo[i]),
                     "ci_hi": float(ci_hi[i]), "lsd": float(tcrit * se[i]) if alternative == "two-sided" else float(tcrit * se[i]),
                     "dunnett_diff": float(crit * se[i]), "verdict": verdict, "sig": bool(sigp)})
    w = []
    for c in controls:
        if ncount[c] < 2: w.append(f"Стандарт «{c}» має лише {ncount[c]} спостереження: оцінка похибки спирається на інші номери, "
                                 f"а надійність порівняння знижена.")
    if df < 6: w.append(f"Лише {df} ступенів свободи похибки — тест малопотужний; для надійних висновків потрібні повторності.")
    cnts = {ncount[l] for l in levels}
    if len(cnts) > 1: w.append("Кількість повторностей номерів різна: використано МНК-середні (скориговані на блоки), "
                              "довірчі інтервали й похибки різняться за номерами.")
    if len(controls) > 1: w.append(f"Порівняння — із СЕРЕДНІМ {len(controls)} стандартів ({', '.join(controls)}).")
    kind = _method(Rm)[0] if k >= 1 else "onefactor"
    if kind == "mc":
        w.append("Кореляційна структура плану нерегулярна, а номерів багато (k > 15): поправлені p-значення й інтервали "
                 "обчислено методом Монте-Карло (похибка ≈ ±0,001; найменше p-значення — 1/400000).")
    n_unadj = sum(1 for r in rows if r["p_lsd"] < alpha)
    n_adj = sum(1 for r in rows if r["p_dunnett"] < alpha)
    if k > 1 and n_unadj > n_adj:
        w.append(f"Без поправки на множинні порівняння (НІР) значущими були б {n_unadj} із {k} номерів, за Дуннеттом — {n_adj}: "
                 f"НІР при порівнянні багатьох номерів із одним стандартом завищує кількість «істотно кращих».")
    return {"rows": rows, "control": controls, "control_mean": ctrl_mean, "control_se": ctrl_se, "mse": mse, "df": df,
            "n": n, "cv": 100.0 * math.sqrt(mse) / float(np.mean(y)) if np.mean(y) else NAN, "k": k,
            "alpha": alpha, "alternative": alternative, "crit": crit, "R": Rm, "blocks": nb, "warnings": w}


def compare_estimates_to_control(levels, means, cov, controls, df, alpha=0.05, alternative="two-sided", ci=True):
    """Порівняння зі стандартом за ГОТОВИМИ оцінками (напр. скоригованими середніми змішаної моделі):
    means (q), cov (q × q) — їх коваріація. df — ступені свободи для t-розподілу (для змішаних моделей —
    наближення; рекомендується консервативне, напр. внутрішньоблочне). Повертає той самий dict, що й
    compare_to_control (без n і MSE)."""
    _need_mvt()
    levels = [str(l) for l in levels]; means = np.asarray(means, float); cov = np.asarray(cov, float)
    controls = [str(x) for x in (controls if isinstance(controls, (list, tuple)) else [controls])]
    for c_ in controls:
        if c_ not in levels: raise BreedingError(f"Стандарту «{c_}» немає серед оцінених номерів.")
    others = [l for l in levels if l not in controls]
    if not others: raise BreedingError("Потрібен щонайменше один номер, окрім стандарту.")
    if df < 1: raise BreedingError("Немає ступенів свободи для порівняння.")
    ix = {l: i for i, l in enumerate(levels)}; q = len(levels)
    cw = np.zeros(q)
    for c_ in controls: cw[ix[c_]] = 1.0 / len(controls)
    L = np.zeros((len(others), q))
    for r_, o in enumerate(others): L[r_, ix[o]] = 1.0; L[r_] -= cw
    d = L @ means; A = L @ cov @ L.T
    se = np.sqrt(np.maximum(np.diag(A), 0))
    if np.any(se <= 0): raise BreedingError("Дисперсія різниці дорівнює нулю — порівняння неможливе (перевірте дані).")
    t = d / se; Rm = A / np.sqrt(np.outer(np.diag(A), np.diag(A))); k = len(others)
    p_dun = dunnett_pvalues(t, Rm, df, alternative)
    crit = dunnett_critical(Rm, df, alpha, alternative) if ci else NAN
    if alternative == "two-sided": p_lsd = 2 * stats.t.sf(np.abs(t), df); tcrit = stats.t.ppf(1 - alpha / 2, df); lo, hi = d - crit * se, d + crit * se
    elif alternative == "greater": p_lsd = stats.t.sf(t, df); tcrit = stats.t.ppf(1 - alpha, df); lo, hi = d - crit * se, np.full(k, np.inf)
    else: p_lsd = stats.t.cdf(t, df); tcrit = stats.t.ppf(1 - alpha, df); lo, hi = np.full(k, -np.inf), d + crit * se
    cm = float(cw @ means); cse = math.sqrt(float(cw @ cov @ cw))
    rows = []
    for i, o in enumerate(others):
        sg = bool(p_dun[i] < alpha)
        rows.append({"entry": o, "n": None, "mean": float(means[ix[o]]), "se": math.sqrt(max(cov[ix[o], ix[o]], 0)),
                     "diff": float(d[i]), "se_diff": float(se[i]), "pct": 100.0 * float(means[ix[o]]) / cm if cm else NAN,
                     "t": float(t[i]), "p_dunnett": float(p_dun[i]), "p_lsd": float(p_lsd[i]), "ci_lo": float(lo[i]), "ci_hi": float(hi[i]),
                     "lsd": float(tcrit * se[i]), "dunnett_diff": float(crit * se[i]),
                     "verdict": ("достовірно вище стандарту" if (sg and d[i] > 0) else "достовірно нижче стандарту" if (sg and d[i] < 0) else "не відрізняється"),
                     "sig": sg})
    return {"rows": rows, "control": controls, "control_mean": cm, "control_se": cse, "mse": NAN, "df": df, "n": None, "cv": NAN, "k": k,
            "alpha": alpha, "alternative": alternative, "crit": crit, "R": Rm, "blocks": 0, "warnings": []}
