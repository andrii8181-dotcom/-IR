# sad_gencorr_core.py — S.A.D. v2.1: генотипні (rG), фенотипні (rP) та середовищні (rE) кореляції
# -*- coding: utf-8 -*-
"""
Збалансований блочний дослід (RCBD): g генотипів × r повторностей × k ознак. Добутки середніх (MANOVA):
    G = (MP_ген − MP_похибки)/r  — генотипна коваріація;     E = MP_похибки — середовищна (залишкова);
    P_ділянка = G + E;   P_середнє = G + E/r = MP_ген/r.
    rG = G_xy/√(G_xx·G_yy)           генотипна кореляція (Fisher 1918; Falconer);
    rP(ділянка) = P_xy/√(P_xx·P_yy)  фенотипна на рівні ділянки (Al-Jibouri та ін. 1958);
    rP(середні) = кореляція Пірсона між середніми генотипів (рівносильна P_середнє);
    rE = E_xy/√(E_xx·E_yy)           середовищна (залишкова).
ВАЖЛИВО: rG — відношення оцінок компонентів, а не проста вибіркова кореляція; його «традиційна» перевірка
(критичне r за df = g − 2) наближена. Тому додано довірчий інтервал бутстрепом за генотипами (з перевіркою
покриття симуляцією). За від'ємної генотипної дисперсії rG НЕ ВИЗНАЧЕНО (а не обчислюється за модулем).
"""
import math
import numpy as np
from scipy import stats
from sad_gxe_core import BreedingError
import sad_selection_core as SC

NAN = float("nan")


def _components(arr):
    """arr: (g, r, k) → G, E (k×k) за добутками середніх."""
    g, r, k = arr.shape
    gm = arr.mean(axis=(0, 1)); dg = arr.mean(axis=1) - gm; dr = arr.mean(axis=0) - gm
    SPg = r * dg.T @ dg; SPr = g * dr.T @ dr
    dev = arr - gm; SPt = np.einsum("ijk,ijl->kl", dev, dev)
    SPe = SPt - SPg - SPr
    MPg, MPe = SPg / (g - 1), SPe / ((g - 1) * (r - 1))
    return (MPg - MPe) / r, MPe


def _corr(C, floor=None):
    """Кореляційна матриця з коваріаційної. Дисперсія вважається додатною, лише якщо вона перевищує допуск floor[i]
    (відносно масштабу даних): значення на кшталт 1e-17 — це шум обчислень, а не генетична мінливість."""
    k = C.shape[0]; d = np.diag(C); R = np.full((k, k), NAN)
    fl = np.zeros(k) if floor is None else np.asarray(floor, float)
    ok = d > fl
    for i in range(k):
        for j in range(k):
            if i == j: R[i, j] = 1.0 if ok[i] else NAN
            elif ok[i] and ok[j]: R[i, j] = C[i, j] / math.sqrt(d[i] * d[j])
    return R


def traditional_p(r, g):
    """p за «традиційним» критерієм (як для звичайної кореляції, df = g − 2). Для rG — наближення."""
    if r is None or math.isnan(r) or abs(r) >= 1: return 0.0 if (r is not None and not math.isnan(r)) else NAN
    df = g - 2
    return float(2 * stats.t.sf(abs(r) * math.sqrt(df / (1 - r * r)), df))


def genotypic_correlations(gen, rep, Y, traits, alpha=0.05, n_boot=2000, seed=20240611):
    """Повертає dict: матриці rG, rP_plot, rP_mean, rE, h2, G, E; pairs (список пар із бутстреп-ДІ для rG)."""
    gen = [str(x) for x in gen]; rep = [str(x) for x in rep]; Y = np.asarray(Y, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ref = SC.multitrait_rcbd(gen, rep, Y, traits)      # перевірка збалансованості та еталонні G, E
    g, r, k = ref["g"], ref["r"], ref["k"]
    gl = ref["gen_names"]; rl = list(dict.fromkeys(rep))
    arr = np.zeros((g, r, k))
    for a_, b_, y_ in zip(gen, rep, Y): arr[gl.index(a_), rl.index(b_)] = y_
    G, E = _components(arr)
    assert np.allclose(G, ref["G"]) and np.allclose(E, ref["E"])
    P_plot = G + E; P_mean = G + E / r
    floor = 1e-9 * np.var(Y, axis=0)                       # допуск: 1e-9 від загальної дисперсії ознаки
    rG = _corr(G, floor); rP = _corr(P_plot, floor); rPm = _corr(P_mean, floor); rE = _corr(E, floor)
    h2 = np.array([G[i, i] / P_mean[i, i] if (G[i, i] > floor[i] and P_mean[i, i] > floor[i]) else (0.0 if P_mean[i, i] > floor[i] else NAN)
                   for i in range(k)])
    warns = []
    neg = [traits[i] for i in range(k) if G[i, i] <= floor[i]]
    if neg:
        warns.append("Генотипна дисперсія ≤ 0 (генетичну мінливість не виявлено) для: " + ", ".join(neg) +
                     ". Генотипні кореляції з цими ознаками НЕ ВИЗНАЧЕНІ.")
    if g < 20:
        warns.append(f"Лише {g} генотипів: за симуляціями (g = 15) бутстреп-інтервал для rG покриває істинне значення лише ≈ 80 % разів "
                     f"(номінал 95 %), а в третині випадків rG взагалі не визначено. Висновки про rG ненадійні; для упевнених висновків "
                     f"потрібно ≥ 30 генотипів.")
    elif g < 30:
        warns.append(f"{g} генотипів: інтервали для rG наближені (покриття 91–95 % за симуляціями); краще мати ≥ 30 генотипів.")
    if r < 3: warns.append(f"{r} повторності: оцінка генотипної коваріації нестійка.")
    # бутстреп за генотипами
    rng = np.random.default_rng(seed)
    boots = np.full((n_boot, k, k), NAN)
    for b in range(n_boot):
        idx = rng.integers(0, g, size=g)
        Gb, _ = _components(arr[idx])
        boots[b] = _corr(Gb, floor)
    pairs = []
    for i in range(k):
        for j in range(i + 1, k):
            v = boots[:, i, j]; ok = v[~np.isnan(v)]
            lo = hi = lo99 = hi99 = NAN
            if len(ok) >= 0.8 * n_boot and not math.isnan(rG[i, j]):
                lo, hi = (float(np.quantile(ok, alpha / 2)), float(np.quantile(ok, 1 - alpha / 2)))
                lo99, hi99 = float(np.quantile(ok, 0.005)), float(np.quantile(ok, 0.995))
                lo, lo99 = max(lo, -1.0), max(lo99, -1.0); hi, hi99 = min(hi, 1.0), min(hi99, 1.0)   # кореляція не виходить за ±1
            pairs.append({"i": i, "j": j, "a": traits[i], "b": traits[j], "rG": float(rG[i, j]), "rG_lo": lo, "rG_hi": hi,
                          "rG_lo99": lo99, "rG_hi99": hi99,
                          "rG_p_trad": traditional_p(float(rG[i, j]), g), "rP": float(rP[i, j]), "rP_mean": float(rPm[i, j]),
                          "rP_mean_p": traditional_p(float(rPm[i, j]), g), "rE": float(rE[i, j]),
                          "boot_valid": int(len(ok)), "out_of_range": bool(not math.isnan(rG[i, j]) and abs(rG[i, j]) > 1)})
    if any(p["out_of_range"] for p in pairs):
        warns.append("Деякі rG за модулем перевищують 1 — наслідок похибки оцінювання (типово при малому числі генотипів); "
                     "істинна кореляція не може виходити за ±1.")
    if any((not math.isnan(p["rG"])) and p["boot_valid"] < 0.8 * n_boot for p in pairs):
        warns.append("У понад 20 % бутстреп-вибірок генотипна дисперсія була ≤ 0 — інтервали для частини пар не наведено (ненадійні).")
    return {"g": g, "r": r, "k": k, "traits": list(traits), "gen_names": gl, "G": G, "E": E, "P_plot": P_plot, "P_mean": P_mean,
            "rG": rG, "rP": rP, "rP_mean": rPm, "rE": rE, "h2": h2, "pairs": pairs, "alpha": alpha, "n_boot": n_boot,
            "means": arr.mean(axis=1), "warnings": warns}
