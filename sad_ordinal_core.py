# sad_ordinal_core.py — S.A.D. v2.1: бальні ознаки (стійкість до хвороб, вилягання, зимостійкість) без tkinter
# -*- coding: utf-8 -*-
"""
Бали (1–9, 0–5 тощо) — порядкові дані: відстань між балами 3 і 4 не дорівнює відстані між 7 і 8, тому середнє арифметичне
й ANOVA для них не мають суворого змісту. Тут: порівняння груп за рангами (Крускал–Уолліс + тест Данна з поправкою на
множинність), опис порядкових даних, індекс розвитку хвороби (McKinney 1923) і площа під кривою розвитку хвороби
(AUDPC, Shaner & Finney 1977; Campbell & Madden 1990).
"""
import math, re, datetime as _dt
import numpy as np
from scipy import stats
from sad_gxe_core import BreedingError

NAN = float("nan")


def p_adjust(p, method="holm"):
    """Поправка p-значень: 'holm', 'bonferroni', 'bh' (Беньяміні–Хохберга, контроль FDR)."""
    p = np.asarray(p, float); m = len(p); order = np.argsort(p)
    if method == "bonferroni": return np.minimum(1.0, p * m)
    adj = np.empty(m)
    if method == "holm":
        run = 0.0
        for rank, idx in enumerate(order):
            run = max(run, min(1.0, (m - rank) * p[idx])); adj[idx] = run
        return adj
    if method == "bh":
        run = 1.0
        for rank in range(m - 1, -1, -1):
            idx = order[rank]; run = min(run, p[idx] * m / (rank + 1)); adj[idx] = min(run, 1.0)
        return adj
    raise BreedingError("Невідомий метод поправки.")


def dunn_test(groups, adjust="holm"):
    """Тест Данна (Dunn 1964) для парних порівнянь після Крускала–Уолліса, з поправкою на зв'язані ранги:
        z_ij = (R̄_i − R̄_j)/√{[N(N+1)/12 − Σ(t³−t)/(12(N−1))]·(1/n_i + 1/n_j)}.
    groups — dict {назва: значення}. Повертає dict: kw (H, p, df), pairs [(a, b, z, p, p_adj)], mean_ranks, n."""
    names = list(groups); arrs = [np.asarray(groups[k], float) for k in names]
    if len(names) < 2: raise BreedingError("Потрібно щонайменше 2 групи.")
    for k, a in zip(names, arrs):
        if len(a) < 1: raise BreedingError(f"Група «{k}» порожня.")
        if np.any(np.isnan(a)): raise BreedingError(f"У групі «{k}» є порожні або нечислові значення.")
    allv = np.concatenate(arrs); N = len(allv)
    if np.ptp(allv) == 0: raise BreedingError("Усі значення однакові — порівнювати групи немає змісту.")
    ranks = stats.rankdata(allv); mr, ns, pos = {}, {}, 0
    for k, a in zip(names, arrs):
        mr[k] = float(np.mean(ranks[pos:pos + len(a)])); ns[k] = len(a); pos += len(a)
    _, counts = np.unique(allv, return_counts=True)
    tie = float(np.sum(counts ** 3 - counts)) / (12.0 * (N - 1))
    var0 = N * (N + 1) / 12.0 - tie
    pairs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a_, b_ = names[i], names[j]
            z = (mr[a_] - mr[b_]) / math.sqrt(var0 * (1.0 / ns[a_] + 1.0 / ns[b_]))
            pairs.append([a_, b_, float(z), float(2 * stats.norm.sf(abs(z)))])
    padj = p_adjust([p[3] for p in pairs], adjust)
    for p_, pa in zip(pairs, padj): p_.append(float(pa))
    kw = stats.kruskal(*arrs) if len(names) > 1 else None
    return {"kw_H": float(kw.statistic), "kw_p": float(kw.pvalue), "kw_df": len(names) - 1, "pairs": pairs, "mean_ranks": mr, "n": ns, "N": N,
            "adjust": adjust}


def compact_letters(names, pairs, alpha=0.05, order_by=None):
    """Літери значущості: групи зі спільною літерою не відрізняються за поправленим p, з різними — відрізняються.
    Літера = максимальна кліка графа «не відрізняються» (алгоритм Бронна–Кербоша), тож правило виконується для
    будь-якої конфігурації значущих пар (кожна пара «не відрізняються» лежить у принаймні одній максимальній кліці,
    а пара «відрізняються» не може потрапити в одну кліку)."""
    order = list(order_by) if order_by else list(names)
    sig = {frozenset((a_, b_)) for a_, b_, _, _, p_adj in pairs if p_adj < alpha}
    nb = {n: {m for m in names if m != n and frozenset((n, m)) not in sig} for n in names}
    cliques = []
    def bk(R, P, X):
        if not P and not X: cliques.append(sorted(R, key=order.index)); return
        for v in list(P):
            bk(R | {v}, P & nb[v], X & nb[v]); P = P - {v}; X = X | {v}
    bk(set(), set(names), set())
    cliques.sort(key=lambda c: (order.index(c[0]), len(c) * -1))
    letters = {n: "" for n in names}
    for li, c in enumerate(cliques):
        for n in c: letters[n] += chr(ord("a") + li)
    return letters


def describe_scores(values, smin=None, smax=None):
    """Опис порядкових даних: n, медіана, квартилі, мода, розподіл за балами (%)."""
    v = np.asarray(values, float)
    if len(v) == 0: raise BreedingError("Немає значень.")
    cls, cnt = np.unique(v, return_counts=True)
    return {"n": len(v), "median": float(np.median(v)), "q1": float(np.percentile(v, 25)), "q3": float(np.percentile(v, 75)),
            "mode": float(cls[np.argmax(cnt)]), "min": float(v.min()), "max": float(v.max()), "classes": cls, "counts": cnt,
            "percent": 100.0 * cnt / len(v)}


def severity_index(values, smin, smax):
    """Індекс розвитку хвороби (McKinney 1923), %: 100·Σ(бал − min)/(n·(max − min)). Для шкали 0–9 — Σ(n_c·c)/(N·9)·100."""
    v = np.asarray(values, float)
    if smax <= smin: raise BreedingError("Максимальний бал шкали має бути більшим за мінімальний.")
    if np.any(v < smin - 1e-12) or np.any(v > smax + 1e-12): raise BreedingError(f"Є бали поза шкалою {smin:g}–{smax:g}.")
    return float(100.0 * np.mean((v - smin) / (smax - smin)))


def audpc(times, values, relative=True, ymax=None):
    """AUDPC за трапеціями: Σ [(yᵢ + yᵢ₊₁)/2]·(tᵢ₊₁ − tᵢ). Відносна rAUDPC = AUDPC/(y_max·(t_n − t₁)) ∈ [0; 1]."""
    t = np.asarray(times, float); y = np.asarray(values, float)
    if len(t) != len(y) or len(t) < 2: raise BreedingError("Для AUDPC потрібно щонайменше 2 обліки (час і значення).")
    if np.any(np.diff(t) <= 0): raise BreedingError("Моменти обліків мають зростати.")
    if np.any(np.isnan(y)): raise BreedingError("У ряду обліків є пропуски.")
    a = float(np.sum((y[:-1] + y[1:]) / 2.0 * np.diff(t)))
    top = float(ymax) if ymax is not None else float(np.max(y))
    return {"audpc": a, "raudpc": a / (top * (t[-1] - t[0])) if top > 0 else NAN, "span": float(t[-1] - t[0]), "ymax": top}


def parse_time(label, first=None):
    """Мітка обліку → число (дні). Приймає число або дату ДД.ММ.РРРР / РРРР-ММ-ДД (відлік від першої дати)."""
    s = str(label).strip().replace(",", ".")
    try: return float(s), None
    except ValueError: pass
    for f in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = _dt.datetime.strptime(s, f).date()
            return (float((d - first).days) if first else 0.0), d
        except ValueError: continue
    raise BreedingError(f"Не вдалося розпізнати момент обліку «{label}»: вкажіть число (днів) або дату ДД.ММ.РРРР.")
