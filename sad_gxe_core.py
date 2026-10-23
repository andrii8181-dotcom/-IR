# sad_gxe_core.py — S.A.D. v2.1: аналізи G×E для селекції (без tkinter)
# -*- coding: utf-8 -*-
"""
Показники стабільності й адаптивності генотипів, AMMI, GGE, комбінований ANOVA.

Формули: Wricke (1962); Shukla (1972); Eberhart & Russell (1966); Finlay & Wilkinson (1963);
Lin & Binns (1988); Francis & Kannenberg (1978); Kang (1988); Hühn (1979), Nassar & Hühn (1987);
Thennarasu (1995); Fox et al. (1990); Gollob (1968); Purchase et al. (2000); Yan et al. (2000).
Огляд: Pour-Aboughadareh A. et al. Plants 2022, 11(3):414, doi:10.3390/plants11030414.
"""
import math
import numpy as np
from scipy import stats

NAN = float("nan")


class BreedingError(Exception):
    """Помилка вхідних даних із зрозумілим для користувача текстом."""


# ═══════════════════════════════════════════════════════════════
# 1. Підготовка таблиці «генотип × середовище»
# ═══════════════════════════════════════════════════════════════
def as_matrix(data, gen_names=None, env_names=None):
    """→ np.ndarray (g×e). Пропуски (NaN) НЕ імпутуються мовчки: помилка зі списком клітинок."""
    X = np.asarray(data, dtype=float)
    if X.ndim != 2: raise BreedingError("Дані мають бути таблицею «генотипи × середовища».")
    g, e = X.shape
    if g < 2 or e < 2: raise BreedingError("Потрібно щонайменше 2 генотипи і 2 середовища.")
    bad = np.argwhere(np.isnan(X))
    if len(bad):
        gn = gen_names or [f"G{i+1}" for i in range(g)]
        en = env_names or [f"E{j+1}" for j in range(e)]
        cells = ", ".join(f"{gn[i]} × {en[j]}" for i, j in bad[:8])
        more = f" … і ще {len(bad) - 8}" if len(bad) > 8 else ""
        raise BreedingError(
            f"У таблиці {len(bad)} порожніх клітинок ({cells}{more}). Для цих методів потрібна повна "
            f"таблиця: заповніть пропуски або приберіть генотип чи середовище з пропусками. "
            f"Програма не підставляє значення замість відсутніх.")
    return X


def ge_effects(X):
    """Головні ефекти й взаємодія за середніми: gm, gmeans, emeans, gei та суми квадратів на 1 повторність."""
    g, e = X.shape
    gm = float(X.mean()); gmeans = X.mean(axis=1); emeans = X.mean(axis=0)
    gei = X - gmeans[:, None] - emeans[None, :] + gm
    return {"g": g, "e": e, "gm": gm, "gmeans": gmeans, "emeans": emeans, "gei": gei,
            "SSG": float(e * np.sum((gmeans - gm) ** 2)),
            "SSE": float(g * np.sum((emeans - gm) ** 2)),
            "SSGE": float(np.sum(gei ** 2))}


def rank_desc(v):
    """Ранги: 1 = найбільше значення; рівні значення — середній ранг."""
    return stats.rankdata(-np.asarray(v, float), method="average")


def rank_asc(v):
    return stats.rankdata(np.asarray(v, float), method="average")



def bartlett_equal_df(variances, nu):
    """Тест Бартлетта однорідності дисперсій похибки з однаковою кількістю ст. свободи ν
    в кожній групі: χ² = [Nν·ln s²_пул − ν·Σ ln s²_j] / C,
    C = 1 + (1/(3(k−1)))·(k/ν − 1/(kν)); k груп. Повертає dict(chi2, p, df)."""
    v = np.asarray(variances, float); k = len(v)
    if k < 2 or np.any(v <= 0): return {"chi2": NAN, "p": NAN, "df": max(k - 1, 0)}
    num = k * nu * math.log(float(v.mean())) - nu * float(np.sum(np.log(v)))
    C = 1 + (1.0 / (3 * (k - 1))) * (k / nu - 1.0 / (k * nu))
    chi2 = num / C
    return {"chi2": float(chi2), "p": float(stats.chi2.sf(chi2, k - 1)), "df": k - 1}

# ═══════════════════════════════════════════════════════════════
# 2. Комбінований дисперсійний аналіз за повторностями
# ═══════════════════════════════════════════════════════════════
def combined_anova(gen, env, rep, y):
    """Комбінований ANOVA серії дослідів RCBD у кількох середовищах (збалансований).
    Модель: y = μ + E + R(E) + G + G×E + похибка. Генотипи — фіксовані, середовища — випадкові:
    F(G) = MS_G / MS_GE;  F(G×E) = MS_GE / MS_похибки;  F(E) = MS_E / MS_R(E).
    Повертає dict із таблицею, матрицею середніх, MSE, df похибки, r і тестом Бартлетта."""
    gen = np.asarray(gen, dtype=object); env = np.asarray(env, dtype=object)
    rep = np.asarray(rep, dtype=object); y = np.asarray(y, dtype=float)
    if np.any(np.isnan(y)): raise BreedingError("У довгій таблиці є нечислові значення — приберіть або заповніть їх.")
    gl = list(dict.fromkeys(gen)); el = list(dict.fromkeys(env))
    g, e = len(gl), len(el)
    cell = {}
    for a, b, c, v in zip(gen, env, rep, y):
        cell.setdefault((a, b), {})[c] = v
    counts = {len(v) for v in cell.values()}
    if len(cell) != g * e or len(counts) != 1:
        raise BreedingError("Дослід має бути збалансованим: кожен генотип у кожному середовищі з однаковою "
                            "кількістю повторностей. Перевірте відсутні або зайві рядки.")
    r = counts.pop()
    if r < 2: raise BreedingError("Для оцінки похибки потрібно щонайменше 2 повторності.")
    arr = np.zeros((g, e, r))
    for (a, b), d in cell.items():
        reps = sorted(d, key=str)
        arr[gl.index(a), el.index(b), :] = [d[k] for k in reps]
    # блоки в різних середовищах — окремі (R вкладені в E); порядок у межах клітинки не важливий
    # для сум квадратів, якщо повторності позначені однаково в усіх генотипів середовища:
    for j in range(e):
        names = [sorted(cell[(a, el[j])], key=str) for a in gl]
        if any(n != names[0] for n in names):
            raise BreedingError(f"У середовищі «{el[j]}» набори повторностей різні в різних генотипів.")
    gm = arr.mean()
    gmeans = arr.mean(axis=(1, 2)); emeans = arr.mean(axis=(0, 2)); gemeans = arr.mean(axis=2)
    remeans = arr.mean(axis=0)                     # e × r  — середні блоків усередині середовища
    SSE = g * r * np.sum((emeans - gm) ** 2)
    SSG = e * r * np.sum((gmeans - gm) ** 2)
    SSGE = r * np.sum((gemeans - gmeans[:, None] - emeans[None, :] + gm) ** 2)
    SSR = g * np.sum((remeans - emeans[:, None]) ** 2)
    SST = np.sum((arr - gm) ** 2)
    SSerr = SST - SSE - SSG - SSGE - SSR
    df = {"E": e - 1, "R(E)": e * (r - 1), "G": g - 1, "GE": (g - 1) * (e - 1), "err": e * (g - 1) * (r - 1)}
    ms = {"E": SSE / df["E"], "R(E)": SSR / df["R(E)"], "G": SSG / df["G"],
          "GE": SSGE / df["GE"], "err": SSerr / df["err"]}
    F = {"E": ms["E"] / ms["R(E)"], "G": ms["G"] / ms["GE"], "GE": ms["GE"] / ms["err"]}
    dfd = {"E": df["R(E)"], "G": df["GE"], "GE": df["err"]}
    p = {k: float(stats.f.sf(F[k], df[k], dfd[k])) for k in F}
    # похибки окремих середовищ (для Бартлетта)
    mse_env = []
    for j in range(e):
        sub = arr[:, j, :]
        m = sub.mean()
        ss = np.sum((sub - m) ** 2) - r * np.sum((sub.mean(axis=1) - m) ** 2) - g * np.sum((sub.mean(axis=0) - m) ** 2)
        mse_env.append(ss / ((g - 1) * (r - 1)))
    nu = (g - 1) * (r - 1)
    mse_env = np.array(mse_env)
    bart = bartlett_equal_df(mse_env, nu)
    bart["mse_env"] = mse_env
    return {"gen_names": gl, "env_names": el, "g": g, "e": e, "r": r, "means": gemeans,
            "SS": {"E": SSE, "R(E)": SSR, "G": SSG, "GE": SSGE, "err": SSerr, "tot": SST},
            "df": df, "MS": ms, "F": F, "p": p, "mse": float(ms["err"]), "df_err": df["err"],
            "bartlett": bart}


# ═══════════════════════════════════════════════════════════════
# 3. Індекси стабільності та адаптивності
# ═══════════════════════════════════════════════════════════════
def stability_indices(X, mse=None, r=1, df_err=None):
    """Усі параметричні й непараметричні індекси для таблиці середніх X (g×e).
    mse, r, df_err (необов'язково) — похибка серед повторностей із комбінованого ANOVA:
    вони потрібні для строгих тестів Ебергарта–Рассела; без них тести не виконуються.
    Повертає dict масивів по генотипах + ранги."""
    g, e = X.shape
    eff = ge_effects(X)
    gm, gmeans, emeans, gei = eff["gm"], eff["gmeans"], eff["emeans"], eff["gei"]
    out = {"g": g, "e": e, "mean": gmeans, "env_mean": emeans, "grand_mean": gm, "gei": gei,
           "SSGE": eff["SSGE"], "SSG": eff["SSG"], "SSE": eff["SSE"]}

    # Параметричні
    out["S2"] = X.var(axis=1, ddof=1)                                 # Roemer: дисперсія по середовищах
    out["CV"] = 100.0 * np.sqrt(out["S2"]) / np.where(gmeans != 0, gmeans, NAN)   # Francis & Kannenberg
    W = np.sum(gei ** 2, axis=1)                                      # Wricke: екоцінність
    out["W2"] = W
    if g >= 3:
        out["Shukla"] = (g * (g - 1) * W - eff["SSGE"]) / ((g - 1) * (g - 2) * (e - 1))
    else:
        out["Shukla"] = np.full(g, NAN)

    # Регресійні (Finlay–Wilkinson, Eberhart–Russell)
    I = emeans - gm; SI2 = float(np.sum(I ** 2))
    b = (X @ I) / SI2 if SI2 > 0 else np.full(g, NAN)
    out["b"] = b; out["env_index"] = I
    ssdev = np.array([np.sum((X[i] - gmeans[i] - b[i] * I) ** 2) for i in range(g)])   # Σδ²
    out["SSdev"] = ssdev
    if e >= 3:
        s2delta = ssdev / (e - 2)                                     # без поправки на похибку
        out["S2delta"] = s2delta
        se_b = np.sqrt(s2delta / SI2) if SI2 > 0 else np.full(g, NAN)
        out["b_se"] = se_b
        t = (b - 1.0) / np.where(se_b > 0, se_b, NAN)
        out["b_t"] = t; out["b_p"] = 2 * stats.t.sf(np.abs(t), e - 2)
    else:
        for k in ("S2delta", "b_se", "b_t", "b_p"): out[k] = np.full(g, NAN)
    if mse is not None and e >= 3:
        mse_mean = mse / r
        out["S2d"] = out["S2delta"] - mse_mean                       # Eberhart & Russell: S²d
        Fv = out["S2delta"] / mse_mean
        out["S2d_F"] = Fv
        out["S2d_p"] = stats.f.sf(Fv, e - 2, df_err) if df_err else np.full(g, NAN)
    else:
        out["S2d"] = np.full(g, NAN); out["S2d_F"] = np.full(g, NAN); out["S2d_p"] = np.full(g, NAN)

    # Lin & Binns (індекс переваги) та його складові за сприятливими/несприятливими середовищами
    M = X.max(axis=0)
    D2 = (X - M[None, :]) ** 2
    out["Pi"] = D2.sum(axis=1) / (2.0 * e)
    fav = emeans > gm; unf = ~fav
    out["Pi_fav"] = D2[:, fav].sum(axis=1) / (2.0 * fav.sum()) if fav.any() else np.full(g, NAN)
    out["Pi_unf"] = D2[:, unf].sum(axis=1) / (2.0 * unf.sum()) if unf.any() else np.full(g, NAN)
    out["n_fav"] = int(fav.sum()); out["n_unf"] = int(unf.sum())

    # Непараметричні: ранги (1 = найвищий урожай) у кожному середовищі
    R = np.column_stack([rank_desc(X[:, j]) for j in range(e)])      # g×e
    out["ranks"] = R
    rbar = R.mean(axis=1)
    out["rank_mean"] = rbar
    iu = np.triu_indices(e, 1)
    out["S1"] = np.array([2.0 * np.sum(np.abs(R[i][:, None] - R[i][None, :])[iu]) / (e * (e - 1))
                          for i in range(g)])                         # середня абсолютна різниця рангів
    out["S2r"] = R.var(axis=1, ddof=1)
    out["S3"] = np.sum((R - rbar[:, None]) ** 2, axis=1) / rbar
    out["S6"] = np.sum(np.abs(R - rbar[:, None]), axis=1) / rbar
    # Thennarasu: ранги скоригованих даних (прибрано ефект генотипу)
    Xadj = X - (gmeans - gm)[:, None]
    Ra = np.column_stack([rank_desc(Xadj[:, j]) for j in range(e)])
    out["ranks_adj"] = Ra
    Md = np.median(R, axis=1); Mda = np.median(Ra, axis=1); rbar_a = Ra.mean(axis=1)
    out["NP1"] = np.sum(np.abs(Ra - Mda[:, None]), axis=1) / e
    out["NP2"] = np.sum(np.abs(Ra - Mda[:, None]), axis=1) / (e * Md)
    out["NP3"] = np.sqrt(np.sum((Ra - rbar_a[:, None]) ** 2, axis=1) / e) / rbar
    out["NP4"] = np.array([2.0 * np.sum(np.abs(Ra[i][:, None] - Ra[i][None, :])[iu]) / (e * (e - 1))
                           for i in range(g)]) / rbar
    # TOP-Fox: частка середовищ, де генотип у верхній третині
    third = g / 3.0
    out["TOP"] = 100.0 * np.sum(R <= third + 1e-12, axis=1) / e

    # Ранги за кожним індексом (1 = найкраще) та узгодженість
    rk = {}
    rk["Середнє (↑)"] = rank_desc(gmeans)
    for key, lab in (("S2", "S² (↓)"), ("CV", "CV (↓)"), ("W2", "W² Вріке (↓)"), ("Shukla", "σ² Шукли (↓)"),
                     ("Pi", "Pi Ліна–Біннса (↓)"), ("S1", "S(1) (↓)"), ("S2r", "S(2) (↓)"),
                     ("S3", "S(3) (↓)"), ("S6", "S(6) (↓)"), ("NP1", "NP(1) (↓)"), ("NP2", "NP(2) (↓)"),
                     ("NP3", "NP(3) (↓)"), ("NP4", "NP(4) (↓)")):
        v = out[key]
        if not np.all(np.isnan(v)): rk[lab] = rank_asc(v)
    rk["|b − 1| (↓)"] = rank_asc(np.abs(b - 1.0))
    if not np.all(np.isnan(out["S2delta"])): rk["S²δ (↓)"] = rank_asc(out["S2delta"])
    rk["TOP (↑)"] = rank_desc(out["TOP"])
    out["rank_by"] = rk
    # Канг: ранг-сума «середнє + стабільність Шукли»
    if g >= 3:
        out["Kang_RS"] = rank_desc(gmeans) + rank_asc(out["Shukla"])
        out["Kang_rank"] = rank_asc(out["Kang_RS"])
    else:
        out["Kang_RS"] = np.full(g, NAN); out["Kang_rank"] = np.full(g, NAN)
    return out


def rank_correlation(rank_by):
    """Матриця кореляції Спірмена між рангами за різними індексами → (імена, матриця)."""
    names = list(rank_by)
    M = np.column_stack([rank_by[n] for n in names])
    k = len(names); C = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            a, b = M[:, i], M[:, j]
            if np.ptp(a) == 0 or np.ptp(b) == 0: c = NAN
            else: c = float(stats.spearmanr(a, b)[0])
            C[i, j] = C[j, i] = c
    return names, C


def design_warnings(g, e, mse=None):
    """Попередження про обмеження даних (щоб не інтерпретувати ненадійне)."""
    w = []
    if e < 4: w.append(f"Лише {e} середовищ(а): регресійні показники (b, S²δ) і AMMI мають дуже мало ступенів "
                       f"свободи — трактувати їх можна лише як орієнтовні. Для надійних висновків потрібно ≥ 5–6 "
                       f"середовищ (локацій × років).")
    elif e < 6: w.append(f"{e} середовищ: регресійні тести малопотужні; висновки про b і S²δ орієнтовні.")
    if g < 3: w.append("Менше 3 генотипів: варіанса Шукли й ранг-сума Канга не визначені.")
    if g < 5: w.append("Мало генотипів: ранги й кореляція між індексами нестійкі.")
    if mse is None:
        w.append("Похибка за повторностями не задана (дані — лише середні): тести S²d (Ебергарт–Рассел) і F-тести "
                 "осей AMMI не виконуються. Для цього імпортуйте довгу таблицю (Генотип, Середовище, Повторність, "
                 "Значення) — програма сама порахує похибку.")
    return w


# ═══════════════════════════════════════════════════════════════
# 4. AMMI
# ═══════════════════════════════════════════════════════════════
def ammi(X, r=1, mse=None, df_err=None):
    """AMMI: SVD матриці взаємодії. Ступені свободи осей за Gollob: g + e − 1 − 2k.
    SS осі k = r·σ_k². Оцінки (симетричне масштабування): g_ik = u_ik·√σ_k, e_jk = v_jk·√σ_k.
    ASV (Purchase 2000) = √[ (SS_IPCA1/SS_IPCA2 · IPCA1)² + IPCA2² ]."""
    g, e = X.shape
    eff = ge_effects(X)
    U, S, Vt = np.linalg.svd(eff["gei"], full_matrices=False)
    k_all = min(g - 1, e - 1)
    S = S[:k_all]; U = U[:, :k_all]; V = Vt.T[:, :k_all]
    ss_ax = r * S ** 2
    SSGE = r * eff["SSGE"]
    rows = []
    cum = 0.0
    for k in range(k_all):
        df_k = g + e - 1 - 2 * (k + 1)
        pct = 100 * ss_ax[k] / SSGE if SSGE > 0 else NAN
        cum += pct
        ms = ss_ax[k] / df_k if df_k > 0 else NAN
        Fv = ms / mse if (mse and df_k > 0) else NAN
        pv = float(stats.f.sf(Fv, df_k, df_err)) if (mse and df_k > 0 and df_err) else NAN
        rows.append({"axis": k + 1, "SS": float(ss_ax[k]), "df": df_k, "MS": float(ms) if df_k > 0 else NAN,
                     "pct": float(pct), "cum": float(cum), "F": float(Fv), "p": pv})
    gs = U * np.sqrt(S); es = V * np.sqrt(S)
    asv = np.full(g, NAN)
    if k_all >= 2 and ss_ax[1] > 0:
        w = ss_ax[0] / ss_ax[1]
        asv = np.sqrt((w * gs[:, 0]) ** 2 + gs[:, 1] ** 2)
    elif k_all == 1:
        asv = np.abs(gs[:, 0])
    return {"g": g, "e": e, "r": r, "axes": rows, "gen_scores": gs, "env_scores": es, "sv": S,
            "ASV": asv, "means": eff["gmeans"], "env_means": eff["emeans"], "grand_mean": eff["gm"],
            "SS": {"G": r * eff["SSG"], "E": r * eff["SSE"], "GE": SSGE},
            "k_all": k_all}


def ammi_rank_table(am):
    """ASV, ранги ASV і середнього, YSI = ранг(ASV) + ранг(середнього) (менше — краще)."""
    asv = am["ASV"]
    r_asv = rank_asc(asv); r_mean = rank_desc(am["means"])
    return {"ASV": asv, "rank_ASV": r_asv, "rank_mean": r_mean, "YSI": r_asv + r_mean}


# ═══════════════════════════════════════════════════════════════
# 5. GGE-біплот
# ═══════════════════════════════════════════════════════════════
def gge(X, svp="genotype", standardize=False):
    """GGE: SVD матриці, центрованої за середовищами. svp: 'genotype' (G=U·S, E=V),
    'environment' (G=U, E=V·S), 'symmetric' (G=U√S, E=V√S)."""
    g, e = X.shape
    Xc = X - X.mean(axis=0)
    if standardize:
        sd = Xc.std(axis=0, ddof=1); sd[sd == 0] = 1.0; Xc = Xc / sd
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    k = min(g, e)
    U, S, V = U[:, :k], S[:k], Vt.T[:, :k]
    if svp == "genotype": G, E = U * S, V
    elif svp == "environment": G, E = U, V * S
    else: G, E = U * np.sqrt(S), V * np.sqrt(S)
    pct = 100 * S ** 2 / np.sum(S ** 2)
    return {"G": G, "E": E, "S": S, "pct": pct, "svp": svp, "Xc": Xc}


def which_won_where(res):
    """Багатокутник (опукла оболонка генотипів у PC1×PC2) і переможець у кожному середовищі
    за проекцією на вектор середовища. → dict(hull, winners{env_idx: gen_idx}, sectors)."""
    G = res["G"][:, :2]; E = res["E"][:, :2]
    g = G.shape[0]
    hull = []
    if g >= 3:
        try:
            from scipy.spatial import ConvexHull
            hull = [int(i) for i in ConvexHull(G).vertices]
        except Exception:
            hull = []
    winners = {j: int(np.argmax(G @ E[j])) for j in range(E.shape[0])}
    sectors = {}
    for j, i in winners.items(): sectors.setdefault(i, []).append(j)
    return {"hull": hull, "winners": winners, "sectors": sectors}


def aec_mean_stability(res):
    """Середовище-«еталон» (AEC): вісь через середню точку середовищ. Повертає
    mean_score (проекція на вісь — продуктивність) і stability (|перпендикуляр| — нестабільність)."""
    G = res["G"][:, :2]; E = res["E"][:, :2]
    a = E.mean(axis=0)
    n = float(np.linalg.norm(a))
    if n == 0: a = np.array([1.0, 0.0]); n = 1.0
    u = a / n
    perp = np.array([-u[1], u[0]])
    return {"axis": u, "mean_score": G @ u, "instability": np.abs(G @ perp), "env_point": a}


def discriminativeness(res):
    """Дискримінаційність середовища = довжина вектора; репрезентативність = cos кута з віссю AEC."""
    E = res["E"][:, :2]
    a = E.mean(axis=0)
    na = np.linalg.norm(a) or 1.0
    length = np.linalg.norm(E, axis=1)
    cosang = (E @ a) / (np.where(length > 0, length, 1.0) * na)
    return {"length": length, "representativeness": cosang}
