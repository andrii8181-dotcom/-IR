# sad_selection_core.py — S.A.D. v2.1: індекси добору за кількома ознаками (без tkinter)
# -*- coding: utf-8 -*-
"""
Генетична й фенотипна коваріація з багатоознакового блокового досліду (добутки середніх MANOVA):
    G = (MP_gen − MP_err)/r,   E = MP_err,   P (на середнє) = G + E/r,   P (на ділянку) = G + E.

Індекс I = bᵀx; агрегатний генотип H = aᵀg, де a — економічні ваги.
• Смітт–Хейзел (Smith 1936; Hazel 1943):      b = P⁻¹G a        — максимізує кореляцію I з H, а тому й ΔH;
• базовий індекс (Williams 1962):             b = a;
• Песек–Бейкер (Pesek & Baker 1969):          b = G⁻¹ d         — прирости пропорційні бажаним d.
Очікуваний відгук на добір із інтенсивністю i:  ΔG = i·G b/√(bᵀPb),  ΔH = aᵀΔG,  точність r_IH = bᵀGa/√(bᵀPb·aᵀGa).
"""
import math
import numpy as np
from scipy import stats
from sad_gxe_core import BreedingError

NAN = float("nan")


def selection_intensity(p):
    """Інтенсивність добору i = φ(z)/p для частки відібраних p (0 < p < 1), z = Φ⁻¹(1 − p)."""
    if not 0 < p < 1: raise BreedingError("Частка відбору має бути між 0 і 100 %.")
    z = stats.norm.ppf(1 - p)
    return float(stats.norm.pdf(z) / p)


# ═══════════════════════════════════════════════════════════════
# Коваріації з багатоознакового RCBD
# ═══════════════════════════════════════════════════════════════
def multitrait_rcbd(gen, rep, Y, trait_names):
    """gen, rep — мітки; Y — n × k значення ознак. Дослід має бути збалансованим. Повертає G, E, P та кореляції."""
    gen = [str(x) for x in gen]; rep = [str(x) for x in rep]; Y = np.asarray(Y, float)
    if Y.ndim != 2: raise BreedingError("Y має бути таблицею (спостереження × ознаки).")
    n, k = Y.shape
    if k < 2: raise BreedingError("Для індексу потрібно щонайменше 2 ознаки.")
    if np.any(np.isnan(Y)): raise BreedingError("У даних є порожні або нечислові значення.")
    gl = list(dict.fromkeys(gen)); rl = list(dict.fromkeys(rep)); g, r = len(gl), len(rl)
    if g < 3 or r < 2: raise BreedingError("Потрібно щонайменше 3 генотипи й 2 повторності.")
    arr = np.full((g, r, k), np.nan)
    for a_, b_, y_ in zip(gen, rep, Y):
        i, j = gl.index(a_), rl.index(b_)
        if not np.isnan(arr[i, j, 0]): raise BreedingError(f"Дублікат: генотип «{a_}», повторність «{b_}».")
        arr[i, j] = y_
    if np.any(np.isnan(arr)): raise BreedingError("Дослід має бути збалансованим: кожен генотип у кожній повторності.")
    gm = arr.mean(axis=(0, 1)); gmean = arr.mean(axis=1); rmean = arr.mean(axis=0)
    dg = gmean - gm; dr = rmean - gm
    SPg = r * dg.T @ dg; SPr = g * dr.T @ dr
    dev = arr - gm; SPt = np.einsum("ijk,ijl->kl", dev, dev)
    SPe = SPt - SPg - SPr
    MPg, MPe = SPg / (g - 1), SPe / ((g - 1) * (r - 1))
    G = (MPg - MPe) / r; E = MPe
    P_mean = G + E / r; P_plot = G + E
    sdP = np.sqrt(np.diag(P_mean))
    warns = []
    wg = np.linalg.eigvalsh((G + G.T) / 2)
    if wg.min() <= 1e-9 * max(wg.max(), 1e-12):
        warns.append("Матриця генетичних коваріацій не є додатно визначеною (оцінки за дисперсійним аналізом можуть давати від'ємні "
                     "власні значення): її скориговано мінімальною поправкою («вигинання»). Це ознака замалої кількості "
                     "генотипів/повторностей або відсутності генетичної мінливості за деякими ознаками.")
    gc = G / np.sqrt(np.outer(np.abs(np.diag(G)), np.abs(np.diag(G))))
    if np.any(np.abs(gc) > 1.0001):
        warns.append("Деякі генетичні кореляції за модулем перевищують 1 — наслідок похибки оцінювання при малій кількості генотипів.")
    h2 = np.diag(G) / np.diag(P_mean)
    return {"g": g, "r": r, "k": k, "traits": list(trait_names), "gen_names": gl, "means": gmean, "grand": gm,
            "G": G, "E": E, "P_mean": P_mean, "P_plot": P_plot, "r_gen": gc,
            "r_phen": P_mean / np.outer(sdP, sdP), "h2_mean": h2, "MP_g": MPg, "MP_e": MPe, "warnings": warns}


def bend_psd(M, floor=1e-4):
    """Мінімальне «вигинання»: від'ємні та майже нульові власні значення замінюються на floor·λ_max. → (M', змінено?)."""
    M = (M + M.T) / 2; w, V = np.linalg.eigh(M)
    lo = floor * max(w.max(), 1e-12)
    if w.min() >= lo: return M, False
    w2 = np.maximum(w, lo)
    return (V * w2) @ V.T, True


# ═══════════════════════════════════════════════════════════════
# Індекси
# ═══════════════════════════════════════════════════════════════
def index_coefficients(kind, G, P, a=None, d=None):
    """Коефіцієнти b індексу: 'sh' — Сміт–Хейзел (потрібні ваги a), 'base' — базовий (a), 'pb' — Песек–Бейкер (бажані прирости d)."""
    G = np.asarray(G, float); P = np.asarray(P, float); k = G.shape[0]
    if kind == "sh":
        if a is None: raise BreedingError("Потрібні економічні ваги.")
        return np.linalg.solve(P, G @ np.asarray(a, float))
    if kind == "base":
        if a is None: raise BreedingError("Потрібні економічні ваги.")
        return np.asarray(a, float).copy()
    if kind == "pb":
        if d is None: raise BreedingError("Потрібні бажані прирости.")
        if np.linalg.cond(G) > 1e10: raise BreedingError("Матриця G вироджена — індекс бажаних приростів неможливий.")
        return np.linalg.solve(G, np.asarray(d, float))
    raise BreedingError("Невідомий тип індексу.")


def expected_response(G, P, a, b, i):
    """Очікуваний відгук за ознаками ΔG = i·G b/√(bᵀPb), агрегатний ΔH = aᵀΔG, точність r_IH, спадковість індексу h²_I."""
    G = np.asarray(G, float); P = np.asarray(P, float); a = np.asarray(a, float); b = np.asarray(b, float)
    sI = math.sqrt(float(b @ P @ b))
    dG = i * (G @ b) / sI
    cov_IH = float(b @ G @ a); sH = math.sqrt(max(float(a @ G @ a), 0.0))
    return {"dG": dG, "dH": float(a @ dG), "sigma_I": sI, "accuracy": cov_IH / (sI * sH) if sH > 0 else NAN,
            "h2_index": float(b @ G @ b) / float(b @ P @ b)}


def single_trait_response(G, P, a, j, i):
    """Відгук при доборі лише за ознакою j (b = eⱼ)."""
    b = np.zeros(len(a)); b[j] = 1.0
    return expected_response(G, P, a, b, i)


def index_scores(Z, b):
    """Значення індексу для кожного генотипу за (центрованими) середніми Z (g × k)."""
    return np.asarray(Z, float) @ np.asarray(b, float)


# ═══════════════════════════════════════════════════════════════
# Одноознаковий відбір
# ═══════════════════════════════════════════════════════════════
def selection_response(values, p, h2=None):
    """Диференціал добору S = середнє відібраних − середнє всіх (відбір верхньої частки p), очікуваний відгук R = h²·S;
    за заданим відгуком — реалізована спадковість h²_r = R/S."""
    v = np.asarray(values, float); n = len(v)
    m = max(1, int(round(p * n))); top = np.sort(v)[::-1][:m]
    S = float(top.mean() - v.mean())
    return {"n_selected": m, "S": S, "R_expected": None if h2 is None else float(h2 * S),
            "i_normal": selection_intensity(p), "std_S": S / float(np.std(v, ddof=1)) if np.std(v, ddof=1) > 0 else NAN}


def realized_heritability(R, S):
    if S == 0: raise BreedingError("Диференціал добору дорівнює нулю — реалізована спадковість не визначена.")
    return R / S
