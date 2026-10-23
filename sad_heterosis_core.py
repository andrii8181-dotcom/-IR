# sad_heterosis_core.py — S.A.D. v2.1: гетерозис гібридів F₁ (без tkinter)
# -*- coding: utf-8 -*-
"""
Гетерозис відносно середнього батьків (MPH), кращого батька (BPH, «гетеробельтіоз») і стандарту (SH):
    MPH% = (F₁ − MP)/MP·100,  MP = (P₁ + P₂)/2;   BPH% = (F₁ − BP)/BP·100;   SH% = (F₁ − St)/St·100.
Тести — t-критерій для лінійного контрасту у блоковій моделі (МНК), тож коректні й за різної кількості повторностей:
    SE(F₁ − MP) = √[MSE·(1/n_F + 1/(4n_P1) + 1/(4n_P2))];  SE(F₁ − BP) = √[MSE·(1/n_F + 1/n_BP)].
Для збалансованого досліду з r повторностями це √(1,5·MSE/r) та √(2·MSE/r).
Поправка на множинність — Холм (кожен вид гетерозису поправляється окремо по всіх гібридах).

Джерела: Fonseca S., Patterson F.L. 1968 Crop Sci. 8:85; Singh R.K., Chaudhary B.D. 1977; Holm S. 1979.
"""
import math
import numpy as np
from scipy import stats
from sad_gxe_core import BreedingError

NAN = float("nan")


def holm(p):
    """Поправка Холма на множинні порівняння (зберігає порядок)."""
    p = np.asarray(p, float); m = len(p); order = np.argsort(p); adj = np.empty(m); run = 0.0
    for rank, idx in enumerate(order):
        run = max(run, min(1.0, (m - rank) * p[idx])); adj[idx] = run
    return adj


def heterosis(entries, y, crosses, standard=None, blocks=None, direction="higher", alpha=0.05):
    """entries — мітки генотипів (батьки, гібриди, стандарт) для кожної ділянки; y — значення;
    crosses — [(гібрид, батько1, батько2)]; standard — мітка стандарту (необов'язково);
    direction — 'higher' (більше — краще) чи 'lower'. Повертає dict із таблицею гетерозису й попередженнями."""
    entries = [str(e) for e in entries]; y = np.asarray(y, float)
    if len(entries) != len(y): raise BreedingError("Довжини списків генотипів і значень різні.")
    if np.any(np.isnan(y)): raise BreedingError("У даних є порожні або нечислові значення.")
    if direction not in ("higher", "lower"): raise BreedingError("Напрям має бути «більше — краще» чи «менше — краще».")
    if not crosses: raise BreedingError("Не вказано жодного гібрида з його батьками.")
    levels = list(dict.fromkeys(entries)); idx = {l: i for i, l in enumerate(levels)}; q = len(levels)
    seen = set()
    for h, p1, p2 in crosses:
        if h in seen: raise BreedingError(f"Гібрид «{h}» указано двічі.")
        seen.add(h)
        for nm in (h, p1, p2):
            if nm not in idx: raise BreedingError(f"Генотипу «{nm}» (гібрид чи батько) немає в таблиці з даними.")
        if p1 == p2: raise BreedingError(f"У гібрида «{h}» батьки однакові.")
        if h in (p1, p2): raise BreedingError(f"Гібрид «{h}» не може бути власним батьком.")
    if standard is not None and standard not in idx: raise BreedingError(f"Стандарту «{standard}» немає в таблиці з даними.")
    n = len(y)
    cols = [np.array([1.0 if e == l else 0.0 for e in entries]) for l in levels]
    nb = 0
    if blocks is not None:
        blocks = [str(b) for b in blocks]; bl = list(dict.fromkeys(blocks)); nb = len(bl)
        for b in bl[1:]: cols.append(np.array([1.0 if x == b else 0.0 for x in blocks]))
    X = np.column_stack(cols); XtXp = np.linalg.pinv(X.T @ X); beta = XtXp @ (X.T @ y)
    df = n - int(np.linalg.matrix_rank(X))
    if df < 1: raise BreedingError("Немає ступенів свободи для похибки: потрібні повторності.")
    mse = float(np.sum((y - X @ beta) ** 2) / df)
    proj = np.eye(X.shape[1]) - XtXp @ (X.T @ X)
    cnt = {l: entries.count(l) for l in levels}
    def lv(w):
        v = np.zeros(X.shape[1])
        for e, c in w.items(): v[idx[e]] = c
        return v
    def contrast(w):
        v = lv(w)
        if np.max(np.abs(v @ proj)) > 1e-8: raise BreedingError("Порівняння неможливе: план не пов'язує ці генотипи в спільних блоках.")
        est = float(v @ beta); se = math.sqrt(max(float(v @ XtXp @ v), 0.0) * mse)
        return est, se
    def mean_of(e):
        v = lv({e: 1.0})
        if nb > 1: v[len(levels):] = 1.0 / nb
        return float(v @ beta)
    out = []
    for h, p1, p2 in crosses:
        f, m1, m2 = mean_of(h), mean_of(p1), mean_of(p2)
        mp = (m1 + m2) / 2.0
        bp_name, bp = (p1, m1) if ((m1 >= m2) == (direction == "higher")) else (p2, m2)
        row = {"hybrid": h, "p1": p1, "p2": p2, "n": cnt[h], "F1": f, "P1": m1, "P2": m2, "MP": mp, "BP": bp, "BP_name": bp_name}
        d, se = contrast({h: 1.0, p1: -0.5, p2: -0.5}); row.update(mph_diff=d, mph_se=se)
        row["mph_pct"] = 100.0 * d / mp if mp else NAN
        d, se = contrast({h: 1.0, bp_name: -1.0}); row.update(bph_diff=d, bph_se=se)
        row["bph_pct"] = 100.0 * d / bp if bp else NAN
        if standard is not None and standard != h:
            ms = mean_of(standard); d, se = contrast({h: 1.0, standard: -1.0})
            row.update(sh_diff=d, sh_se=se, sh_pct=100.0 * d / ms if ms else NAN, st_mean=ms)
        out.append(row)
    for kind in ("mph", "bph", "sh"):
        rows_k = [r for r in out if f"{kind}_diff" in r]
        if not rows_k: continue
        for r in rows_k:
            t = r[f"{kind}_diff"] / r[f"{kind}_se"] if r[f"{kind}_se"] > 0 else NAN
            r[f"{kind}_t"] = t; r[f"{kind}_p"] = float(2 * stats.t.sf(abs(t), df)) if t == t else NAN
        adj = holm([r[f"{kind}_p"] for r in rows_k])
        for r, a in zip(rows_k, adj): r[f"{kind}_p_holm"] = float(a)
    def verdict(r, kind):
        if f"{kind}_p" not in r: return "—"
        sig = r[f"{kind}_p_holm"] < alpha; up = r[f"{kind}_diff"] > 0
        if not sig: return "не відрізняється"
        good = up == (direction == "higher")
        return ("достовірно " + ("вищий" if up else "нижчий") + (" — бажаний" if good else " — небажаний"))
    for r in out:
        for kind in ("mph", "bph", "sh"): r[f"{kind}_verdict"] = verdict(r, kind)
    w = []
    if df < 6: w.append(f"Лише {df} ступенів свободи похибки — тести гетерозису малопотужні.")
    single = [l for l in {p for c in crosses for p in c[1:]} if cnt.get(l, 0) < 2]
    if single: w.append("Батьки без повторностей (" + ", ".join(sorted(map(str, single))) + "): їхні середні оцінені з великою похибкою, що "
                        "зміщує тести гетерозису.")
    if len(set(cnt.values())) > 1: w.append("Кількість повторностей генотипів різна: використано МНК-середні й похибки для кожного порівняння окремо.")
    if len(crosses) > 1: w.append("p-значення поправлено за Холмом по всіх гібридах (окремо для кожного виду гетерозису); без поправки "
                                  "кількість «достовірних» гібридів була б завищена.")
    neg = [l for l in levels if mean_of(l) <= 0]
    if neg: w.append("Середнє ≤ 0 для: " + ", ".join(neg[:4]) + " — відсотковий гетерозис за таких значень не має змісту.")
    return {"rows": out, "mse": mse, "df": df, "n": n, "standard": standard, "direction": direction, "alpha": alpha,
            "cv": 100.0 * math.sqrt(mse) / float(np.mean(y)) if np.mean(y) else NAN, "warnings": w}
