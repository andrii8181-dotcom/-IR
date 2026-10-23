# sad_corr_core.py — S.A.D. v2.1: кореляційна матриця (Пірсон, Спірмен, Кендалл), довірчі інтервали, поправки
# -*- coding: utf-8 -*-
"""
Рядки таблиці — спостереження (ділянки), стовпці — показники. Масиви містять NaN на місці порожніх клітинок,
тож ВИРІВНЮВАННЯ ЗА РЯДКАМИ зберігається; для кожної пари виключаються лише ті рядки, де бракує одного зі значень
(попарне виключення). Раніше порожні клітинки пропускалися окремо в кожному стовпці, через що значення з різних
ділянок потрапляли в одну пару.

Довірчі інтервали — через z-перетворення Фішера: z = artanh(r), межі tanh(z ± z₁₋α/₂·SE), де
  Пірсон:  SE = 1/√(n−3);   Спірмен:  SE = √((1 + r²/2)/(n−3))  (Bonett & Wright 2000);
  Кендалл: SE = √(0,437/(n−4))  (Fieller, Hartley & Pearson 1957).
Інтервали наведено БЕЗ поправки на множинність (p-значення — з поправкою).
"""
import math
import numpy as np
from scipy import stats
from sad_ordinal_core import p_adjust

NAN = float("nan")
METHOD_LABEL = {"pearson": "Пірсон r", "spearman": "Спірмен ρ", "kendall": "Кендалл τ-b"}
CORRECTION_LABEL = {"holm": "Холм", "bonferroni": "Бонферроні", "bh": "Беньяміні–Хохберг (FDR)", "none": "без поправки"}


def arrays_from_cells(columns):
    """columns: список стовпців, кожен — список рядків-рядків (клітинок). Повертає (масиви з NaN, нечислові клітинки).
    Порожня клітинка → NaN; нечислова → NaN і запис у список (щоб повідомити користувача, а не мовчки зсунути рядки)."""
    arrays, bad = [], []
    for j, col in enumerate(columns):
        a = np.full(len(col), np.nan)
        for i, s in enumerate(col):
            s = str(s).strip().replace("\u00a0", "").replace(" ", "")
            if not s: continue
            try: a[i] = float(s.replace(",", "."))
            except ValueError: bad.append((i, j, s))
        arrays.append(a)
    return arrays, bad


def fisher_ci(r, n, method="pearson", alpha=0.05):
    """Довірчий інтервал для коефіцієнта кореляції (z-перетворення Фішера). NaN, якщо n замале."""
    if r is None or math.isnan(r) or abs(r) >= 1.0:
        return (r, r) if (r is not None and not math.isnan(r)) else (NAN, NAN)
    if method == "kendall":
        if n <= 4: return NAN, NAN
        se = math.sqrt(0.437 / (n - 4))
    elif method == "spearman":
        if n <= 3: return NAN, NAN
        se = math.sqrt((1.0 + r * r / 2.0) / (n - 3))
    else:
        if n <= 3: return NAN, NAN
        se = 1.0 / math.sqrt(n - 3)
    z = math.atanh(r); c = stats.norm.ppf(1 - alpha / 2)
    return math.tanh(z - c * se), math.tanh(z + c * se)


def correlate_pair(a, b, method="pearson", alpha=0.05):
    """Кореляція двох масивів однакової довжини з NaN. → dict(r, p, n, ci_lo, ci_hi, status)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b)); x, y = a[mask], b[mask]; n = len(x)
    out = {"r": NAN, "p": NAN, "n": n, "ci_lo": NAN, "ci_hi": NAN, "status": "ok"}
    if n < 3: out["status"] = "менше 3 спільних спостережень"; return out
    if np.ptp(x) == 0 or np.ptp(y) == 0: out["status"] = "один із показників сталий"; return out
    if method == "pearson": r, p = stats.pearsonr(x, y)
    elif method == "spearman": r, p = stats.spearmanr(x, y)
    elif method == "kendall": r, p = stats.kendalltau(x, y, variant="b")
    else: raise ValueError(f"Невідомий метод: {method}")
    out["r"] = float(r); out["p"] = float(p)
    out["ci_lo"], out["ci_hi"] = fisher_ci(float(r), n, method, alpha)
    return out


def correlation_matrix(arrays, labels, method="pearson", alpha=0.05, correction="holm"):
    """Попарні кореляції з довірчими інтервалами й поправкою p на множинність (по всіх парах).
    Повертає dict: r, p (з поправкою), p_raw, n, ci_lo, ci_hi (матриці k×k), pairs (список), skipped."""
    k = len(arrays)
    if len(set(len(a) for a in arrays)) > 1: raise ValueError("Масиви мають однакову довжину (рядки = спостереження).")
    R = np.full((k, k), NAN); P = np.full((k, k), NAN); PR = np.full((k, k), NAN); N = np.zeros((k, k), int)
    LO = np.full((k, k), NAN); HI = np.full((k, k), NAN)
    for i in range(k):
        R[i, i] = 1.0; P[i, i] = PR[i, i] = 0.0; N[i, i] = int(np.sum(~np.isnan(arrays[i]))); LO[i, i] = HI[i, i] = 1.0
    pairs, skipped = [], []
    for i in range(k):
        for j in range(i + 1, k):
            res = correlate_pair(arrays[i], arrays[j], method, alpha)
            N[i, j] = N[j, i] = res["n"]
            if res["status"] != "ok":
                skipped.append((labels[i], labels[j], res["status"])); continue
            pairs.append({"i": i, "j": j, "a": labels[i], "b": labels[j], **res})
    ps = [p["p"] for p in pairs]
    adj = p_adjust(ps, correction) if (ps and correction != "none") else list(ps)
    for pr, pa in zip(pairs, adj):
        pr["p_raw"] = pr["p"]; pr["p_adj"] = float(pa)
        i, j = pr["i"], pr["j"]
        R[i, j] = R[j, i] = pr["r"]; PR[i, j] = PR[j, i] = pr["p_raw"]; P[i, j] = P[j, i] = pr["p_adj"]
        LO[i, j] = LO[j, i] = pr["ci_lo"]; HI[i, j] = HI[j, i] = pr["ci_hi"]
    return {"r": R, "p": P, "p_raw": PR, "n": N, "ci_lo": LO, "ci_hi": HI, "pairs": pairs, "skipped": skipped,
            "method": method, "correction": correction, "alpha": alpha}


def strength(r):
    """Словесна оцінка сили зв'язку за |r| (умовна шкала Чеддока)."""
    a = abs(r)
    return ("дуже слабкий" if a < 0.1 else "слабкий" if a < 0.3 else "помірний" if a < 0.5 else
            "помітний" if a < 0.7 else "високий" if a < 0.9 else "дуже високий")


# ═══════════════════════════════════════════════════════════════
# Частинна й напівчастинна кореляція
# ═══════════════════════════════════════════════════════════════
class PartialError(ValueError):
    """Некоректні вхідні дані для частинної кореляції (зрозуміле повідомлення користувачу)."""


def _complete_rows(arrays):
    m = np.ones(len(arrays[0]), bool)
    for a in arrays: m &= ~np.isnan(a)
    return m


def partial_correlation(x, y, Z, method="pearson", alpha=0.05):
    """Частинна кореляція x і y з виключенням лінійного впливу контрольних ознак Z (список масивів).
    Береться ПОВНА вибірка — рядки, де є всі значення (x, y і всіх Z). Для 'spearman' усі змінні спершу
    замінюються рангами (частинний Спірмен — наближення; p й інтервал орієнтовні).
    r — кореляція залишків x і y після регресії на Z; df = n − 2 − k;
    p — t = r·√(df/(1 − r²)); ДІ — Фішер із SE = 1/√(n − 3 − k).
    Напівчастинні: sr_x = corr(y, залишок x | Z) — унікальний внесок x у y; sr_y — навпаки.
    Тест H₀: sr = 0 еквівалентний t-тесту коефіцієнта x у регресії y ~ x + Z, тому p той самий."""
    if method not in ("pearson", "spearman"):
        raise PartialError("Частинна кореляція реалізована для Пірсона й Спірмена.")
    arrs = [np.asarray(a, float) for a in [x, y] + list(Z)]
    if len(set(len(a) for a in arrs)) > 1: raise PartialError("Масиви мають однакову довжину (рядки = спостереження).")
    mask = _complete_rows(arrs); n = int(mask.sum()); k = len(Z)
    v = [a[mask] for a in arrs]
    if method == "spearman": v = [stats.rankdata(a) for a in v]
    if n - 2 - k < 1:
        raise PartialError(f"Замало спостережень: на {n} повних рядків припадає {k} контрольних ознак; потрібно, щоб n > k + 2.")
    if any(np.ptp(a) == 0 for a in v): raise PartialError("Одна зі змінних стала (немає варіації) на спільних рядках.")
    xx, yy = v[0], v[1]
    D = np.column_stack([np.ones(n)] + v[2:]) if k else np.ones((n, 1))
    if np.linalg.matrix_rank(D) < D.shape[1]:
        raise PartialError("Контрольні ознаки лінійно залежні (колінеарні): одну з них слід прибрати.")
    bx = np.linalg.lstsq(D, xx, rcond=None)[0]; by = np.linalg.lstsq(D, yy, rcond=None)[0]
    rx = xx - D @ bx; ry = yy - D @ by
    if np.ptp(rx) < 1e-12 or np.ptp(ry) < 1e-12:
        raise PartialError("Контрольні ознаки повністю пояснюють одну зі змінних — частинна кореляція не визначена.")
    r = float(np.corrcoef(rx, ry)[0, 1]); df = n - 2 - k
    t = r * math.sqrt(df / max(1.0 - r * r, 1e-300)); p = float(2 * stats.t.sf(abs(t), df))
    if n - 3 - k > 0 and abs(r) < 1:
        z = math.atanh(r); se = 1.0 / math.sqrt(n - 3 - k); c = stats.norm.ppf(1 - alpha / 2)
        lo, hi = math.tanh(z - c * se), math.tanh(z + c * se)
    else:
        lo = hi = NAN
    r0 = float(np.corrcoef(xx, yy)[0, 1])
    return {"r": r, "p": p, "n": n, "k": k, "df": df, "ci_lo": lo, "ci_hi": hi, "r0": r0,
            "sr_x": float(np.corrcoef(yy, rx)[0, 1]), "sr_y": float(np.corrcoef(xx, ry)[0, 1])}


def partial_matrix(arrays, labels, control_idx, target_idx, method="pearson", alpha=0.05, correction="holm"):
    """Частинні кореляції між усіма парами ознак target_idx з виключенням ознак control_idx.
    Одна спільна вибірка для всіх пар (рядки з повними даними за ВСІМА задіяними змінними): інакше матриця
    частинних кореляцій може бути суперечливою. Поправка p — по всіх парах."""
    if not target_idx or len(target_idx) < 2: raise PartialError("Оберіть щонайменше 2 ознаки, між якими шукається зв'язок.")
    if set(control_idx) & set(target_idx): raise PartialError("Одна й та сама ознака не може бути і досліджуваною, і контрольною.")
    used = list(target_idx) + list(control_idx)
    mask = _complete_rows([np.asarray(arrays[i], float) for i in used])
    n = int(mask.sum())
    if n < len(control_idx) + 4: raise PartialError(
        f"Спільних рядків із повними даними лише {n} — замало для {len(control_idx)} контрольних ознак (потрібно ≥ k + 4).")
    # усі масиви обрізаємо до СПІЛЬНИХ рядків — тоді n однакове для кожної пари
    sub = {i: np.asarray(arrays[i], float)[mask] for i in used}
    Z = [sub[i] for i in control_idx]
    pairs = []
    for a_pos in range(len(target_idx)):
        for b_pos in range(a_pos + 1, len(target_idx)):
            i, j = target_idx[a_pos], target_idx[b_pos]
            res = partial_correlation(sub[i], sub[j], Z, method, alpha)
            pairs.append({"i": i, "j": j, "a": labels[i], "b": labels[j], **res})
    ps = [q["p"] for q in pairs]
    adj = p_adjust(ps, correction) if (ps and correction != "none") else list(ps)
    for q, pa in zip(pairs, adj): q["p_raw"] = q["p"]; q["p_adj"] = float(pa)
    return {"pairs": pairs, "n": n, "k": len(control_idx), "controls": [labels[i] for i in control_idx],
            "targets": [labels[i] for i in target_idx], "method": method, "alpha": alpha, "correction": correction,
            "dropped_rows": int(len(arrays[0]) - n)}
