# sad_mixed_core.py — S.A.D. v2.1: змішані лінійні моделі (REML, BLUP) без tkinter
# -*- coding: utf-8 -*-
"""
Модель: y = Xβ + Σₖ Zₖuₖ + ε,  uₖ ~ N(0, σ²ₖ I),  ε ~ N(0, σ²ₑ I).

Оцінювання компонентів дисперсії — обмежена максимальна правдоподібність (REML). Через рівняння Гендерсона
(MME) з матрицею коефіцієнтів C = W'W/σ²ₑ + blockdiag(0, G⁻¹), W = [X Z₁ … Z_K]:

    −2·ℓ_REML = n·ln σ²ₑ + Σₖ qₖ·ln σ²ₖ + ln|C| + y'Py + const,   y'Py = (y'y − θ̂'W'y)/σ²ₑ,

що еквівалентно ln|V| + ln|X'V⁻¹X| + y'Py (виведено через лему про визначник; перевірено в тестах проти
прямого обчислення з щільною V). Матриця C розріджена → розклад LU (SuperLU), тож метод масштабується
на тисячі рівнів ефектів. BLUP: û = G Z'V⁻¹(y − Xβ̂); похибка прогнозу PEV — з діагоналі C⁻¹.

Джерела: Henderson C.R. 1975 Biometrics 31:423; Patterson & Thompson 1971 Biometrika 58:545;
Cullis B.R., Smith A.B., Coombes N.E. 2006 JABES 11:381 (спадковість за BLUP).
"""
import math
import numpy as np
from scipy import sparse, optimize, stats
from scipy.sparse.linalg import splu
from sad_gxe_core import BreedingError

NAN = float("nan")


# ═══════════════════════════════════════════════════════════════
# Побудова матриць плану
# ═══════════════════════════════════════════════════════════════
def _levels(labels):
    lv = list(dict.fromkeys(labels))
    return lv, {l: i for i, l in enumerate(lv)}


def dummies(labels, drop_first=False):
    """Розріджена матриця індикаторів рівнів (n × q) і список рівнів."""
    lv, ix = _levels(labels)
    M = sparse.csr_matrix((np.ones(len(labels)), (np.arange(len(labels)), [ix[l] for l in labels])),
                          shape=(len(labels), len(lv)))
    if drop_first: M = M[:, 1:]; lv = lv[1:]
    return M, lv


def term_labels(factors, term):
    """Мітки рівнів для терму (кортеж імен факторів; для взаємодії — комбінація через «×»)."""
    if isinstance(term, str): term = (term,)
    cols = [factors[t] for t in term]
    return [" × ".join(str(c[i]) for c in cols) for i in range(len(cols[0]))]


def _full_rank_columns(Xd, tol=1e-9):
    """Індекси лінійно незалежних стовпців (жадібно, у порядку появи — тож перетин завжди зберігається)."""
    keep = []; Q = np.zeros((Xd.shape[0], 0))
    for j in range(Xd.shape[1]):
        v = Xd[:, j].astype(float); nv = np.linalg.norm(v)
        r = v - Q @ (Q.T @ v) if Q.shape[1] else v
        if np.linalg.norm(r) > tol * max(nv, 1.0):
            keep.append(j); Q = np.hstack([Q, (r / np.linalg.norm(r))[:, None]])
    return keep


def build_design(y, factors, fixed=(), random=()):
    """→ dict: X (щільна, повного рангу), x_names, Zs [(імена терму, розріджена Z, рівні)], n."""
    n = len(y)
    for k, v in factors.items():
        if len(v) != n: raise BreedingError(f"Фактор «{k}» має довжину {len(v)} ≠ {n}.")
    cols = [np.ones((n, 1))]; names = ["(перетин)"]; meta = [("(перетин)", None)]; fixed_levels = {}
    for term in fixed:
        lab = term_labels(factors, term)
        M, lv = dummies(lab, drop_first=True)
        Md = M.toarray()
        nm = " × ".join(term) if not isinstance(term, str) else term
        fixed_levels[nm] = list(dict.fromkeys(lab)); cols.append(Md)
        names += [f"{nm}: {l}" for l in lv]; meta += [(nm, l) for l in lv]
    X = np.hstack(cols)
    keep = _full_rank_columns(X)
    X = X[:, keep]; names = [names[i] for i in keep]; meta = [meta[i] for i in keep]
    Zs = []
    for term in random:
        lab = term_labels(factors, term)
        M, lv = dummies(lab)
        nm = " × ".join(term) if not isinstance(term, str) else term
        Zs.append((nm, M, lv))
    return {"X": X, "x_names": names, "x_meta": meta, "Zs": Zs, "n": n, "fixed_levels": fixed_levels}


# ═══════════════════════════════════════════════════════════════
# Функція правдоподібності й розв'язок MME
# ═══════════════════════════════════════════════════════════════
class _MME:
    def __init__(self, y, design):
        self.y = np.asarray(y, float); self.n = len(y)
        X = design["X"]; self.p = X.shape[1]
        self.qs = [Z.shape[1] for _, Z, _ in design["Zs"]]
        self.K = len(self.qs)
        W = sparse.hstack([sparse.csr_matrix(X)] + [Z for _, Z, _ in design["Zs"]], format="csc")
        self.W = W; self.WtW = (W.T @ W).tocsc(); self.Wty = np.asarray(W.T @ self.y).ravel()
        self.yty = float(self.y @ self.y)
        offs = np.cumsum([0] + self.qs) + self.p
        self.offs = offs

    def _C(self, s2):
        """C = WᵀW/σ²ₑ + blockdiag(0, I/σ²ₖ). s2 = [σ²₁, …, σ²_K, σ²ₑ]."""
        se = s2[-1]
        d = np.zeros(self.p + sum(self.qs))
        for k in range(self.K): d[self.offs[k]:self.offs[k + 1]] = 1.0 / s2[k]
        return (self.WtW / se + sparse.diags(d)).tocsc()

    def solve(self, s2):
        C = self._C(s2); lu = splu(C)
        theta = lu.solve(self.Wty / s2[-1])
        return C, lu, theta

    def negll(self, s2):
        """−2·ℓ_REML (без сталої): n ln σ²ₑ + Σ qₖ ln σ²ₖ + ln|C| + y'Py."""
        C, lu, theta = self.solve(s2)
        logdet = float(np.sum(np.log(np.abs(lu.U.diagonal()))))
        ypy = (self.yty - float(theta @ self.Wty)) / s2[-1]
        val = self.n * math.log(s2[-1]) + sum(q * math.log(s2[k]) for k, q in enumerate(self.qs)) + logdet + ypy
        return val


def reml_negll_dense(y, X, Zs, s2):
    """Контрольна реалізація: ln|V| + ln|X'V⁻¹X| + y'Py з щільною V (для перевірки в тестах)."""
    n = len(y); V = s2[-1] * np.eye(n)
    for k, Z in enumerate(Zs): V = V + s2[k] * (Z @ Z.T)
    Vi = np.linalg.inv(V); XtViX = X.T @ Vi @ X
    b = np.linalg.solve(XtViX, X.T @ Vi @ y); r = y - X @ b
    return (np.linalg.slogdet(V)[1] + np.linalg.slogdet(XtViX)[1] + float(r @ Vi @ r))


# ═══════════════════════════════════════════════════════════════
# Підгонка
# ═══════════════════════════════════════════════════════════════
def fit_mixed(y, factors, fixed=(), random=(), pev_terms=(), hessian=True, start=None, scale_y=True):
    """Підгонка змішаної моделі REML. y — відгук; factors — {ім'я: список міток}; fixed, random — списки
    термів (ім'я фактора або кортеж імен для взаємодії). pev_terms — для яких випадкових термів обчислити
    повну коваріацію похибок прогнозу (потрібна для спадковості за Каллісом).
    Повертає dict із компонентами дисперсії, β̂, BLUP, PEV, ℓ_REML, збіжністю."""
    y = np.asarray(y, float); n = len(y)
    if np.any(np.isnan(y)): raise BreedingError("У даних є порожні або нечислові значення.")
    if n < 5: raise BreedingError("Замало спостережень для змішаної моделі.")
    if np.ptp(y) == 0: raise BreedingError("Усі значення відгуку однакові — компоненти дисперсії не оцінюються.")
    des = build_design(y, factors, fixed, random)
    p = des["X"].shape[1]
    if n - p < 2: raise BreedingError("Замало ступенів свободи: спостережень не більше, ніж фіксованих ефектів + 1.")
    for nm, Z, lv in des["Zs"]:
        if len(lv) < 2: raise BreedingError(f"Випадковий ефект «{nm}» має лише один рівень.")
    sc = float(np.std(y, ddof=1)) if scale_y else 1.0
    ys = (y - np.mean(y)) / sc if scale_y else y
    mme = _MME(ys, des); K = mme.K
    f = lambda th: mme.negll(np.exp(th))
    lo, hi = math.log(1e-7), math.log(1e3)
    x0 = np.full(K + 1, math.log(1.0 / (K + 1))) if start is None else np.log(np.asarray(start) / sc ** 2)
    best = None
    for trial in range(3):
        x_init = x0 if trial == 0 else x0 + np.random.default_rng(trial).normal(0, 0.7, K + 1)
        r = optimize.minimize(f, np.clip(x_init, lo, hi), method="L-BFGS-B", bounds=[(lo, hi)] * (K + 1),
                              options={"maxiter": 200, "ftol": 1e-12, "gtol": 1e-8})
        if best is None or r.fun < best.fun - 1e-9: best = r
        if trial == 0 and r.success and K <= 3 and r.fun <= f(x0) + 1e-9: break
    th = best.x; s2 = np.exp(th)
    C, lu, theta = mme.solve(s2)
    # відновлення масштабу
    s2_orig = s2 * sc ** 2
    names = [nm for nm, _, _ in des["Zs"]] + ["Залишок"]
    comp = dict(zip(names, s2_orig))
    beta = theta[:p] * sc; beta[0] += float(np.mean(y)) if scale_y else 0.0
    out = {"n": n, "p": p, "x_names": des["x_names"], "x_meta": des["x_meta"], "X": des["X"], "beta": beta,
           "sigma2": comp, "term_names": names, "loglik": -0.5 * (best.fun + n * 2 * math.log(sc)) if scale_y else -0.5 * best.fun,
           "converged": bool(best.success), "design": des, "fixed_levels": des["fixed_levels"], "s2_scaled": s2, "sc": sc, "ymean": float(np.mean(y)) if scale_y else 0.0}
    tot = float(np.sum(s2))
    boundary = [names[k] for k in range(K + 1) if th[k] <= lo + 0.05 or s2[k] / tot < 0.002]     # «практично нуль»
    out["boundary"] = boundary
    # BLUP
    u = {}
    for k, (nm, Z, lv) in enumerate(des["Zs"]):
        u[nm] = {"levels": lv, "blup": theta[mme.offs[k]:mme.offs[k + 1]] * sc}
    out["u"] = u
    # коваріація фіксованих ефектів і PEV
    def inv_cols(idx):
        E = np.zeros((C.shape[0], len(idx))); E[idx, np.arange(len(idx))] = 1.0
        return lu.solve(E)
    Cb = inv_cols(list(range(p)))[:p] * sc ** 2
    out["beta_cov"] = Cb; out["beta_se"] = np.sqrt(np.maximum(np.diag(Cb), 0))
    for k, (nm, Z, lv) in enumerate(des["Zs"]):
        q = len(lv); idx = list(range(mme.offs[k], mme.offs[k + 1]))
        if nm in pev_terms and q <= 2500:
            E = np.zeros((C.shape[0], q)); E[idx, np.arange(q)] = 1.0
            blk = lu.solve(E)[idx] * sc ** 2
            u[nm]["pev_cov"] = blk; u[nm]["pev"] = np.diag(blk).copy()
        else:
            # діагональ через розв'язок по стовпцях пачками
            pev = np.empty(q); step = 200
            for a in range(0, q, step):
                cols_ = idx[a:a + step]
                E = np.zeros((C.shape[0], len(cols_))); E[cols_, np.arange(len(cols_))] = 1.0
                S = lu.solve(E)
                pev[a:a + len(cols_)] = np.array([S[cols_[j], j] for j in range(len(cols_))]) * sc ** 2
            u[nm]["pev"] = pev
    out["_mme"] = mme; out["_lu"] = lu; out["_C"] = C
    # SE компонентів дисперсії (асимптотичні, за гессіаном ℓ_REML у логарифмічній шкалі)
    out["sigma2_se"] = {nm: NAN for nm in names}
    if hessian and not boundary:
        try:
            H = np.zeros((K + 1, K + 1)); h = 1e-3
            for i in range(K + 1):
                for j in range(i, K + 1):
                    def ev(di, dj):
                        t = th.copy(); t[i] += di; t[j] += dj; return f(t)
                    H[i, j] = H[j, i] = (ev(h, h) - ev(h, -h) - ev(-h, h) + ev(-h, -h)) / (4 * h * h)
            cov = np.linalg.inv(0.5 * H)                        # f = −2ℓ → ℓ'' = −H/2 → Var = (H/2)⁻¹
            out["sigma2_se"] = {names[k]: float(math.sqrt(max(cov[k, k], 0)) * s2_orig[k]) for k in range(K + 1)}
        except Exception:
            pass
    return out


def refit_without(res, y, factors, fixed, random, drop_term):
    """Підгонка без одного випадкового терму (для LRT)."""
    rnd = [t for t in random if (" × ".join(t) if not isinstance(t, str) else t) != drop_term]
    return fit_mixed(y, factors, fixed, rnd, hessian=False)


def lrt_random_term(full, red):
    """Тест відношення правдоподібностей для випадкового терму: LR = 2(ℓ_повн − ℓ_скор);
    p = ½·P(χ²₁ > LR) — суміш χ²₀/χ²₁, бо нульова гіпотеза σ² = 0 лежить на межі простору параметрів."""
    lr = max(2.0 * (full["loglik"] - red["loglik"]), 0.0)
    return lr, (0.5 * float(stats.chi2.sf(lr, 1)) if lr > 0 else 1.0)


# ═══════════════════════════════════════════════════════════════
# Похідні величини
# ═══════════════════════════════════════════════════════════════
def blup_table(res, term, intercept_mean=None):
    """BLUP рівнів терму з SE, надійністю (reliability = 1 − PEV/σ²) та рангом."""
    u = res["u"][term]; s2 = res["sigma2"][term]
    blup = u["blup"]; pev = u["pev"]; se = np.sqrt(np.maximum(pev, 0))
    rel = 1.0 - pev / s2 if s2 > 0 else np.zeros_like(pev)
    mu = float(np.mean(res["X"] @ res["beta"])) if intercept_mean is None else intercept_mean
    order = stats.rankdata(-blup, method="min")
    return {"levels": u["levels"], "blup": blup, "se": se, "reliability": rel, "value": mu + blup, "rank": order, "mu": mu}


def cullis_heritability(res, term):
    """Спадковість за Каллісом (2006): H² = 1 − v̄_Δ/(2σ²_g), де v̄_Δ — середня дисперсія різниці двох BLUP.
    Потрібна повна коваріація похибок прогнозу (pev_terms). Інакше — середня надійність 1 − середнє PEV/σ²."""
    u = res["u"][term]; s2 = res["sigma2"][term]
    if s2 <= 0: return {"h2": 0.0, "kind": "σ² = 0"}
    if "pev_cov" in u:
        P = u["pev_cov"]; g = P.shape[0]
        vd = (2.0 / (g - 1)) * (np.trace(P) - float(np.sum(P)) / g)
        return {"h2": float(1.0 - vd / (2.0 * s2)), "kind": "Каллісу", "vdelta": float(vd)}
    return {"h2": float(1.0 - np.mean(u["pev"]) / s2), "kind": "середня надійність"}


def lsmeans_matrix(res, term, other_average=True):
    """Вектори МНК-середніх: рядок для кожного рівня ФІКСОВАНОГО терму (перетин + ефект рівня + усереднені
    решта фіксованих ефектів). Повертає (рівні, V) такі, що середні = V β̂, коваріація = V Cβ Vᵀ."""
    meta = res["x_meta"]; p = res["p"]
    tnames = {mt[0] for mt in meta if mt[0] != "(перетин)"}
    if term not in tnames: raise BreedingError(f"«{term}» не є фіксованим термом моделі.")
    items = {}
    for i, (t, l) in enumerate(meta):
        if t != "(перетин)": items.setdefault(t, []).append((i, l))
    base = res["fixed_levels"][term][0]
    lvls = [base] + [l for _, l in items[term]]
    V = np.zeros((len(lvls), p))
    for li in range(len(lvls)):
        c = np.zeros(p); c[0] = 1.0
        if li > 0: c[items[term][li - 1][0]] = 1.0
        if other_average:
            for t, its in items.items():
                if t == term: continue
                nl = len(res["fixed_levels"][t])
                for i, _ in its: c[i] = 1.0 / nl
        V[li] = c
    return lvls, V


def lsmeans_fixed(res, term, other_average=True):
    """МНК-середні (скориговані середні) і їх SE для рівнів фіксованого терму."""
    lv, V = lsmeans_matrix(res, term, other_average)
    means = V @ res["beta"]; se = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", V, res["beta_cov"], V), 0))
    return lv, means, se
