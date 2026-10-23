# sad_design_core.py — S.A.D. v2.1: схеми для великої кількості номерів (без tkinter)
# -*- coding: utf-8 -*-
"""
Альфа-решітка (Patterson & Williams 1976): розв'язні схеми з неповними блоками для v = s·k номерів,
r повторностей, s блоків по k ділянок у кожній повторності. Побудова — за генеруючим масивом
A (k × r) над Z_s: у блоці j повторності i на позиції m стоїть номер m·s + ((A[m,i] + j) mod s).
Масив підбирається випадковим пошуком за A-ефективністю.

A-ефективність E = (v − 1)/(r·tr C⁺) відносно повнорандомізованих блоків (E = 1 для RCBD), де
C = R − N K⁻¹ Nᵀ — інформаційна матриця номерів (скоригована на блоки).

Аугментована схема (Federer 1956): стандарти повторені в кожному блоці, нові номери — по одному разу.

Джерела: Patterson H.D., Williams E.R. 1976 Biometrika 63:83; Federer W.T. 1956; John & Williams 1995.
"""
import math
import numpy as np
from sad_gxe_core import BreedingError

NAN = float("nan")


# ═══════════════════════════════════════════════════════════════
# Ефективність
# ═══════════════════════════════════════════════════════════════
def incidence(blocks, v):
    """blocks — список блоків (списки індексів номерів 0..v−1). → N (v × b)."""
    N = np.zeros((v, len(blocks)))
    for j, blk in enumerate(blocks):
        for t in blk: N[t, j] += 1.0
    return N


def a_efficiency(blocks, v, r=None):
    """A-ефективність за інформаційною матрицею номерів. Підтримує нерівні розміри блоків і повторення."""
    N = incidence(blocks, v)
    rep = N.sum(axis=1); kk = N.sum(axis=0)
    if np.any(rep == 0): raise BreedingError("Є номери, що не потрапили в жоден блок.")
    C = np.diag(rep) - N @ np.diag(1.0 / kk) @ N.T
    w = np.linalg.eigvalsh((C + C.T) / 2)
    pos = w[w > 1e-9 * max(w.max(), 1.0)]
    if len(pos) < v - 1: return 0.0, False             # не зв'язна схема
    r_eff = float(np.mean(rep)) if r is None else r
    return float((v - 1) / (r_eff * np.sum(1.0 / pos))), True


def pairwise_variance(blocks, v, sigma2=1.0):
    """Середня дисперсія різниці двох номерів (σ² = 1): 2·tr(C⁺)/(v−1)."""
    N = incidence(blocks, v); rep = N.sum(axis=1); kk = N.sum(axis=0)
    C = np.diag(rep) - N @ np.diag(1.0 / kk) @ N.T
    w = np.linalg.eigvalsh((C + C.T) / 2); pos = w[w > 1e-9 * max(w.max(), 1.0)]
    return float(2 * np.sum(1.0 / pos) / (v - 1) * sigma2)


# ═══════════════════════════════════════════════════════════════
# Альфа-решітка
# ═══════════════════════════════════════════════════════════════
def valid_block_sizes(v, r=None):
    """Допустимі розміри блоку k (v ділиться на k, 2 ≤ k ≤ v/2) та число блоків s = v/k."""
    return [(k, v // k) for k in range(2, v // 2 + 1) if v % k == 0]


def _alpha_blocks(A, k, s, r):
    """Блоки (за індексами) для генеруючого масиву A (k × r)."""
    reps = []
    for i in range(r):
        reps.append([[m * s + ((int(A[m, i]) + j) % s) for m in range(k)] for j in range(s)])
    return reps


def alpha_design(entries, k, r, seed=None, tries=None):
    """Альфа-решітка для списку номерів entries (v), розміру блоку k, r повторностей (r ≥ 2).
    Повертає dict: layout (список рядків), efficiency, A, s, replicates (блоки за мітками)."""
    entries = [str(e) for e in entries]
    v = len(entries)
    if len(set(entries)) != v: raise BreedingError("Назви номерів мають бути унікальними.")
    if r < 2: raise BreedingError("Альфа-решітка потребує щонайменше 2 повторностей (для однієї — використайте блокову схему).")
    if k < 2 or v % k != 0 or v // k < 2:
        ok = valid_block_sizes(v)
        hint = ", ".join(f"{kk} (блоків {ss})" for kk, ss in ok) if ok else "жодного — додайте заповнювачі, щоб кількість номерів мала дільники"
        raise BreedingError(f"Для {v} номерів розмір блоку {k} неможливий: кількість номерів має ділитися на розмір блоку, "
                            f"блоків має бути ≥ 2. Допустимі розміри блоку: {hint}.")
    s = v // k
    rng = np.random.default_rng(seed)
    tries = tries or max(30, min(400, int(3e5 / v)))
    best = None
    for _ in range(tries):
        A = rng.integers(0, s, size=(k, r)); A[:, 0] = 0; A[0, :] = 0
        reps = _alpha_blocks(A, k, s, r)
        blocks = [b for rp in reps for b in rp]
        E, conn = a_efficiency(blocks, v, r)
        if conn and (best is None or E > best[0]): best = (E, A.copy(), reps)
    if best is None: raise BreedingError("Не вдалося побудувати зв'язну схему: збільшіть кількість повторностей або блоків.")
    E, A, reps = best
    perm = rng.permutation(v)                              # випадкова відповідність індексів і назв
    layout = []; rep_order = list(range(r))
    for ri, rep in enumerate(reps):
        order = rng.permutation(s)
        for bi, j in enumerate(order):
            blk = [int(perm[t]) for t in rep[j]]
            pos = rng.permutation(k)
            for pi, p in enumerate(pos):
                layout.append({"rep": ri + 1, "block": bi + 1, "plot": pi + 1, "entry": entries[blk[p]], "kind": "новий"})
    return {"layout": layout, "efficiency": E, "A": A, "v": v, "k": k, "r": r, "s": s, "tries": tries,
            "blocks_idx": [[int(perm[t]) for t in b] for rp in reps for b in rp]}


def random_blocks_efficiency(v, k, r, n=200, seed=0):
    """Середня A-ефективність схем із випадковим розподілом по блоках (для порівняння з пошуком)."""
    rng = np.random.default_rng(seed); s = v // k; out = []
    for _ in range(n):
        blocks = []
        for _r in range(r):
            p = rng.permutation(v); blocks += [list(p[j * k:(j + 1) * k]) for j in range(s)]
        E, conn = a_efficiency(blocks, v, r)
        if conn: out.append(E)
    return float(np.mean(out)) if out else NAN


def add_checks_to_layout(layout, checks, seed=None):
    """Додає кожен стандарт до КОЖНОГО блоку (випадкова позиція); перенумеровує ділянки."""
    rng = np.random.default_rng(seed); out = []
    keys = list(dict.fromkeys((r["rep"], r["block"]) for r in layout))
    for key in keys:
        cells = [r["entry"] for r in layout if (r["rep"], r["block"]) == key]
        kinds = {r["entry"]: r["kind"] for r in layout if (r["rep"], r["block"]) == key}
        items = [(e, "новий") for e in cells] + [(c, "стандарт") for c in checks]
        rng.shuffle(items)
        for pi, (e, kd) in enumerate(items): out.append({"rep": key[0], "block": key[1], "plot": pi + 1, "entry": e, "kind": kd})
    return out


# ═══════════════════════════════════════════════════════════════
# Аугментована схема
# ═══════════════════════════════════════════════════════════════
def augmented_design(new_entries, checks, n_blocks, seed=None):
    """Схема Федерера: кожен стандарт — по разу в кожному з n_blocks блоків; нові номери — по разу, розподілені
    між блоками якнайрівніше. Повертає layout, df похибки (c−1)(b−1) і попередження."""
    new = [str(e) for e in new_entries]; chk = [str(c) for c in checks]
    if len(set(new)) != len(new) or len(set(chk)) != len(chk) or set(new) & set(chk):
        raise BreedingError("Назви номерів і стандартів мають бути унікальними й не повторюватись між списками.")
    c, b, n = len(chk), n_blocks, len(new)
    if c < 2: raise BreedingError("Потрібно щонайменше 2 стандарти (інакше неможливо оцінити похибку).")
    if b < 2: raise BreedingError("Потрібно щонайменше 2 блоки.")
    if n < b: raise BreedingError(f"Нових номерів ({n}) менше, ніж блоків ({b}).")
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n); sizes = [n // b + (1 if i < n % b else 0) for i in range(b)]
    layout = []; a = 0
    order = rng.permutation(b)
    members = {}
    for bi in range(b):
        members[bi] = [new[int(i)] for i in perm[a:a + sizes[bi]]]; a += sizes[bi]
    for pos_b, bi in enumerate(order):
        items = [(e, "новий") for e in members[bi]] + [(x, "стандарт") for x in chk]
        rng.shuffle(items)
        for pi, (e, kd) in enumerate(items): layout.append({"rep": 1, "block": pos_b + 1, "plot": pi + 1, "entry": e, "kind": kd})
    df = (c - 1) * (b - 1)
    w = []
    if df < 10: w.append(f"Ступенів свободи похибки лише {df} ((c−1)(b−1)): оцінка похибки й тест Дуннетта малопотужні. "
                         f"Збільшіть кількість стандартів або блоків (бажано df ≥ 10–12).")
    w.append("Нові номери не повторюються: їх відмінності від стандартів і між собою оцінюються лише за поправкою на блок, "
             "обчисленою зі стандартів, тож точність нижча, ніж у повторних дослідах.")
    return {"layout": layout, "df": df, "n_blocks": b, "n_new": n, "n_checks": c, "block_sizes": [sizes[i] + c for i in range(b)],
            "warnings": w}


# ═══════════════════════════════════════════════════════════════
# Допоміжне
# ═══════════════════════════════════════════════════════════════
def layout_rows(layout):
    return [[r["rep"], r["block"], r["plot"], r["entry"], r["kind"]] for r in layout]


def validate_alpha(layout, entries, k, r):
    """Перевірка інваріантів схеми → список порушень (порожній — усе гаразд)."""
    bad = []
    ent = set(entries)
    for rep in range(1, r + 1):
        seen = [x["entry"] for x in layout if x["rep"] == rep and x["kind"] == "новий"]
        if sorted(seen) != sorted(ent): bad.append(f"повторність {rep} не є розбиттям усіх номерів")
    blocks = {}
    for x in layout: blocks.setdefault((x["rep"], x["block"]), []).append(x["entry"])
    for key, mem in blocks.items():
        news = [m for m in mem]
        if len(set(news)) != len(news): bad.append(f"блок {key}: номер повторюється")
    cnt = {e: sum(1 for x in layout if x["entry"] == e and x["kind"] == "новий") for e in entries}
    if any(c != r for c in cnt.values()): bad.append("не кожен номер зустрічається рівно r разів")
    return bad
