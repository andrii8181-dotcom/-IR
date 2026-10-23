# sad_breeding_core.py — S.A.D. v2.1: селекційно-генетичні аналізи (без tkinter)
# -*- coding: utf-8 -*-
"""
Генетичні параметри (Johnson et al. 1955; Knapp et al. 1985), комбінаційна здатність:
лінія × тестер (Kempthorne 1957) і діалель за Гріффінгом (Griffing 1956, методи 2 і 4),
індекси стресостійкості (Rosielle & Hamblin 1981; Fischer & Maurer 1978; Fernandez 1992 та ін.),
шляховий аналіз (Wright 1921; Dewey & Lu 1959).
"""
import math
import numpy as np
from scipy import stats
from sad_gxe_core import BreedingError, rank_desc, rank_asc, combined_anova

NAN = float("nan")


def _group(vals):
    return list(dict.fromkeys(vals))


# ═══════════════════════════════════════════════════════════════
# 1. Генетичні параметри
# ═══════════════════════════════════════════════════════════════
SELECTION_K = {"1 %": 2.67, "5 %": 2.06, "10 %": 1.76, "20 %": 1.40}   # інтенсивність добору k (Falconer)


def _cat(v, lo, hi, names=("низький", "середній", "високий")):
    if v is None or (isinstance(v, float) and math.isnan(v)): return "н/д"
    return names[0] if v < lo else (names[1] if v <= hi else names[2])


def genetic_parameters_single(gen, rep, y, k=2.06, alpha=0.05):
    """Блоковий дослід RCBD в одному середовищі → ANOVA, компоненти дисперсії, H², GCV, PCV, GA.
    σ²e = MSE; σ²g = (MS_G − MSE)/r; σ²p = σ²g + σ²e;  H² (на ділянку) = σ²g/σ²p;
    H² (на середнє) = σ²g/(σ²g + σ²e/r) = 1 − 1/F;  GCV/PCV = 100·√σ²/x̄;
    GA = k·H²·√σ²p;  GAM = 100·GA/x̄.  Довірчий інтервал H²(середнє) — Knapp et al. 1985."""
    gen = np.asarray(gen, dtype=object); rep = np.asarray(rep, dtype=object); y = np.asarray(y, float)
    if np.any(np.isnan(y)): raise BreedingError("У даних є нечислові значення.")
    gl, rl = _group(gen), _group(rep)
    g, r = len(gl), len(rl)
    if g < 3 or r < 2: raise BreedingError("Потрібно щонайменше 3 генотипи й 2 повторності.")
    arr = np.full((g, r), np.nan)
    for a, b, v in zip(gen, rep, y):
        i, j = gl.index(a), rl.index(b)
        if not np.isnan(arr[i, j]): raise BreedingError(f"Дублікат: генотип «{a}», повторність «{b}».")
        arr[i, j] = v
    if np.any(np.isnan(arr)):
        raise BreedingError("Дослід має бути збалансованим: кожен генотип у кожній повторності.")
    gm = arr.mean(); gmean = arr.mean(axis=1); rmean = arr.mean(axis=0)
    SSg = r * np.sum((gmean - gm) ** 2); SSr = g * np.sum((rmean - gm) ** 2)
    SSt = np.sum((arr - gm) ** 2); SSe = SSt - SSg - SSr
    dfg, dfr, dfe = g - 1, r - 1, (g - 1) * (r - 1)
    MSg, MSr, MSe = SSg / dfg, SSr / dfr, SSe / dfe
    F = MSg / MSe; p = float(stats.f.sf(F, dfg, dfe))
    vg_raw = (MSg - MSe) / r
    vg = max(vg_raw, 0.0); ve = MSe; vp = vg + ve
    out = {"g": g, "r": r, "mean": float(gm), "gen_means": gmean,
           "SS": {"gen": SSg, "rep": SSr, "err": SSe, "tot": SSt}, "df": {"gen": dfg, "rep": dfr, "err": dfe},
           "MS": {"gen": MSg, "rep": MSr, "err": MSe}, "F": float(F), "p": p,
           "var_g": vg, "var_g_raw": vg_raw, "var_e": ve, "var_p": vp,
           "h2_plot": vg / vp if vp > 0 else NAN,
           "h2_mean": vg / (vg + ve / r) if (vg + ve / r) > 0 else NAN}
    fq_hi = stats.f.ppf(1 - alpha / 2, dfg, dfe); fq_lo = stats.f.ppf(alpha / 2, dfg, dfe)
    out["h2_mean_ci"] = (float(max(0.0, 1 - fq_hi / F)), float(min(1.0, 1 - fq_lo / F)))
    m = gm if gm != 0 else NAN
    out["GCV"] = 100 * math.sqrt(vg) / m; out["PCV"] = 100 * math.sqrt(vp) / m; out["ECV"] = 100 * math.sqrt(ve) / m
    out["k"] = k
    out["GA"] = k * out["h2_plot"] * math.sqrt(vp)
    out["GAM"] = 100 * out["GA"] / m
    out["cat_h2"] = _cat(100 * out["h2_plot"], 30, 60)           # Johnson et al. 1955 (умовні межі)
    out["cat_gam"] = _cat(out["GAM"], 10, 20)
    out["cat_gcv"] = _cat(out["GCV"], 10, 20); out["cat_pcv"] = _cat(out["PCV"], 10, 20)
    w = []
    if vg_raw < 0:
        w.append("MS генотипів менша за MS похибки: генетична дисперсія не відрізняється від нуля (σ²g прийнято 0). "
                 "Відбір за цією ознакою на основі цих даних даватиме нульовий ефект.")
    if p > alpha: w.append(f"Генотипи статистично не відрізняються (F-тест, p = {p:.3f}) — оцінки H², GA слід вважати "
                           f"ненадійними.")
    if g < 10: w.append(f"Лише {g} генотипів: оцінки генетичної дисперсії й H² дуже неточні; дивіться довірчий інтервал.")
    w.append("H² і GA відносяться до цього середовища й цього набору генотипів; для висновків про селекційний "
             "прогрес потрібні дані кількох середовищ (див. «Генетичні параметри за кількома середовищами»).")
    out["warnings"] = w
    return out


def genetic_parameters_multi(gen, env, rep, y, k=2.06):
    """Серія дослідів RCBD у кількох середовищах: σ²e = MSE; σ²ge = (MS_GE − MSE)/r;
    σ²g = (MS_G − MS_GE)/(r·e); σ²p (на середнє) = σ²g + σ²ge/e + σ²e/(r·e); H² = σ²g/σ²p."""
    ca = combined_anova(gen, env, rep, y)
    g, e, r = ca["g"], ca["e"], ca["r"]
    MS = ca["MS"]
    ve = MS["err"]
    vge_raw = (MS["GE"] - MS["err"]) / r
    vg_raw = (MS["G"] - MS["GE"]) / (r * e)
    vge, vg = max(vge_raw, 0.0), max(vg_raw, 0.0)
    vp = vg + vge / e + ve / (r * e)
    gm = float(np.mean(ca["means"]))
    out = {"ca": ca, "g": g, "e": e, "r": r, "mean": gm, "var_e": ve, "var_ge": vge, "var_g": vg,
           "var_ge_raw": vge_raw, "var_g_raw": vg_raw, "var_p": vp,
           "h2": vg / vp if vp > 0 else NAN}
    # Knapp-подібний інтервал за F = MS_G / MS_GE
    F = MS["G"] / MS["GE"]; d1, d2 = ca["df"]["G"], ca["df"]["GE"]
    out["h2_ci_F"] = (float(max(0.0, 1 - stats.f.ppf(0.975, d1, d2) / F)), float(min(1.0, 1 - stats.f.ppf(0.025, d1, d2) / F)))
    m = gm if gm != 0 else NAN
    out["GCV"] = 100 * math.sqrt(vg) / m; out["PCV"] = 100 * math.sqrt(vp) / m
    out["k"] = k; out["GA"] = k * out["h2"] * math.sqrt(vp); out["GAM"] = 100 * out["GA"] / m
    out["cat_h2"] = _cat(100 * out["h2"], 30, 60); out["cat_gam"] = _cat(out["GAM"], 10, 20)
    w = []
    if vg_raw < 0: w.append("MS генотипів менша за MS взаємодії G×E: σ²g прийнято 0.")
    if vge_raw < 0: w.append("MS взаємодії G×E менша за MS похибки: σ²ge прийнято 0.")
    if ca["bartlett"]["p"] == ca["bartlett"]["p"] and ca["bartlett"]["p"] < 0.05:
        w.append(f"Похибки в різних середовищах неоднорідні (Бартлетт, p = {ca['bartlett']['p']:.3f}): комбінований "
                 f"аналіз може давати зміщені оцінки — розгляньте трансформацію або виключення середовища.")
    if e < 3: w.append("Менше 3 середовищ: компонента G×E оцінюється дуже неточно.")
    out["warnings"] = w
    return out


# ═══════════════════════════════════════════════════════════════
# 2. Лінія × тестер
# ═══════════════════════════════════════════════════════════════
def line_tester(line, tester, rep, y):
    """Схема «лінія × тестер» (Kempthorne 1957), збалансована, r повторностей (без батьківських форм).
    ANOVA: повторності, схрещування → лінії, тестери, лінії×тестери; F для ліній і тестерів проти L×T,
    для L×T — проти похибки. Ефекти: GCA, SCA. Компоненти: Cov(HS), σ²gca, σ²sca."""
    line = np.asarray(line, dtype=object); tester = np.asarray(tester, dtype=object)
    rep = np.asarray(rep, dtype=object); y = np.asarray(y, float)
    if np.any(np.isnan(y)): raise BreedingError("У даних є нечислові значення.")
    ll, tl, rl = _group(line), _group(tester), _group(rep)
    l, t, r = len(ll), len(tl), len(rl)
    if l < 3 or t < 2 or r < 2:
        raise BreedingError("Потрібно ≥ 3 ліній, ≥ 2 тестерів і ≥ 2 повторності.")
    arr = np.full((l, t, r), np.nan)
    for a, b, c, v in zip(line, tester, rep, y):
        i, j, k = ll.index(a), tl.index(b), rl.index(c)
        if not np.isnan(arr[i, j, k]): raise BreedingError(f"Дублікат: {a} × {b}, повторність {c}.")
        arr[i, j, k] = v
    if np.any(np.isnan(arr)):
        raise BreedingError("Схема має бути повною: кожне схрещування лінія × тестер у кожній повторності.")
    gm = arr.mean()
    xij = arr.mean(axis=2); xi = arr.mean(axis=(1, 2)); xj = arr.mean(axis=(0, 2)); xk = arr.mean(axis=(0, 1))
    SSt = np.sum((arr - gm) ** 2)
    SSrep = l * t * np.sum((xk - gm) ** 2)
    SScr = r * np.sum((xij - gm) ** 2)
    SSl = r * t * np.sum((xi - gm) ** 2)
    SSt_ = r * l * np.sum((xj - gm) ** 2)
    SSlt = SScr - SSl - SSt_
    SSe = SSt - SSrep - SScr
    df = {"rep": r - 1, "cross": l * t - 1, "line": l - 1, "tester": t - 1, "lt": (l - 1) * (t - 1),
          "err": (r - 1) * (l * t - 1)}
    SS = {"rep": SSrep, "cross": SScr, "line": SSl, "tester": SSt_, "lt": SSlt, "err": SSe, "tot": SSt}
    MS = {k: SS[k] / df[k] for k in df}
    F = {"cross": MS["cross"] / MS["err"], "line": MS["line"] / MS["lt"], "tester": MS["tester"] / MS["lt"],
         "lt": MS["lt"] / MS["err"]}
    dfd = {"cross": df["err"], "line": df["lt"], "tester": df["lt"], "lt": df["err"]}
    p = {k: float(stats.f.sf(F[k], df[k], dfd[k])) for k in F}
    gl = xi - gm; gt = xj - gm
    sca = xij - xi[:, None] - xj[None, :] + gm
    mse = MS["err"]
    se = {"gca_line": math.sqrt(mse / (r * t)), "gca_tester": math.sqrt(mse / (r * l)), "sca": math.sqrt(mse / r),
          "diff_line": math.sqrt(2 * mse / (r * t)), "diff_tester": math.sqrt(2 * mse / (r * l)),
          "diff_sca": math.sqrt(2 * mse / r)}
    def tp(v, s): 
        tt = v / s; return tt, 2 * stats.t.sf(abs(tt), df["err"])
    # Компоненти дисперсії
    Ml, Mt, Mlt, Me = MS["line"], MS["tester"], MS["lt"], MS["err"]
    cov_l = (Ml - Mlt) / (r * t); cov_t = (Mt - Mlt) / (r * l)
    cov_avg = ((l - 1) * (Ml - Mlt) + (t - 1) * (Mt - Mlt)) / (r * (2 * l * t - l - t))
    s_gca = max(cov_avg, 0.0); s_sca = max((Mlt - Me) / r, 0.0)
    baker = 2 * s_gca / (2 * s_gca + s_sca) if (2 * s_gca + s_sca) > 0 else NAN
    contrib = {k: 100 * SS[k] / SScr for k in ("line", "tester", "lt")}
    w = []
    if cov_avg < 0: w.append("Оцінка σ²gca від'ємна — прийнято 0 (внесок адитивних ефектів не виявлено).")
    if (Mlt - Me) / r < 0: w.append("MS «лінії × тестери» менша за похибку: σ²sca прийнято 0.")
    if l < 5 or t < 3: w.append("Мало ліній/тестерів: F-тести для GCA мають мало ступенів свободи (df = (l−1)(t−1)), "
                                 "оцінки компонентів дисперсії неточні.")
    return {"l": l, "t": t, "r": r, "lines": ll, "testers": tl, "mean": float(gm), "cross_means": xij,
            "SS": SS, "df": df, "MS": MS, "F": F, "p": p, "gca_line": gl, "gca_tester": gt, "sca": sca,
            "se": se, "tp": tp, "cov_hs_line": cov_l, "cov_hs_tester": cov_t, "cov_hs_avg": cov_avg,
            "var_gca": s_gca, "var_sca": s_sca, "baker": baker, "contrib": contrib, "warnings": w,
            "mse": mse}


# ═══════════════════════════════════════════════════════════════
# 3. Діалель (Гріффінг, методи 2 і 4)
# ═══════════════════════════════════════════════════════════════
def diallel_griffing(p1, p2, rep, y, method=2, model="I"):
    """Діалельний аналіз за Гріффінгом. method 2 — батьківські форми + F₁ (без реципроків): p(p+1)/2
    генотипів; method 4 — лише F₁: p(p−1)/2. model 'I' — фіксований, 'II' — випадковий.
    Ефекти знайдено методом найменших квадратів за моделлю xᵢⱼ = μ + gᵢ + gⱼ + sᵢⱼ з обмеженням Σg = 0
    (для методу 2 це відповідає обмеженню Σⱼ sᵢⱼ + sᵢᵢ = 0).
    Реципрокні схрещування усереднюються (реципрокні ефекти методами 1 і 3 не аналізуються)."""
    p1 = np.asarray(p1, dtype=object); p2 = np.asarray(p2, dtype=object)
    rep = np.asarray(rep, dtype=object); y = np.asarray(y, float)
    if method not in (2, 4): raise BreedingError("Реалізовано методи Гріффінга 2 і 4.")
    if np.any(np.isnan(y)): raise BreedingError("У даних є нечислові значення.")
    parents = _group(list(p1) + list(p2))
    p = len(parents)
    minp = 3 if method == 2 else 4
    if p < minp: raise BreedingError(f"Для методу {method} потрібно щонайменше {minp} батьківських форм.")
    reps = _group(rep); r = len(reps)
    idx = {n: i for i, n in enumerate(parents)}
    cells, warn = {}, []
    recip = False
    for a, b, c, v in zip(p1, p2, rep, y):
        i, j = idx[a], idx[b]
        key = (min(i, j), max(i, j))
        if (i > j): recip = True
        cells.setdefault(key, {}).setdefault(c, []).append(v)
    parents_present = [(i, i) in cells for i in range(p)]
    if method == 4:
        if any(parents_present):
            warn.append("Метод 4 не використовує батьківські форми — вони виключені з аналізу.")
        cells = {k: v for k, v in cells.items() if k[0] != k[1]}
        need = [(i, j) for i in range(p) for j in range(i + 1, p)]
    else:
        if not all(parents_present):
            miss = [parents[i] for i in range(p) if not parents_present[i]]
            raise BreedingError("Метод 2 потребує всіх батьківських форм (схрещування «сама з собою»). "
                                "Немає: " + ", ".join(map(str, miss)) + ". Оберіть метод 4 або додайте батьків.")
        need = [(i, j) for i in range(p) for j in range(i, p)]
    missing = [(parents[i], parents[j]) for i, j in need if (i, j) not in cells]
    if missing:
        raise BreedingError("Неповний діалель — немає схрещувань: " +
                            ", ".join(f"{a}×{b}" for a, b in missing[:8]) + (" …" if len(missing) > 8 else ""))
    if recip: warn.append("У даних є реципрокні схрещування — їх усереднено; реципрокні ефекти не аналізуються.")
    v = len(need)
    arr = np.zeros((v, r))
    for n, key in enumerate(need):
        d = cells[key]
        if any(c not in d for c in reps):
            raise BreedingError(f"Схрещування {parents[key[0]]}×{parents[key[1]]} є не в усіх повторностях.")
        arr[n] = [float(np.mean(d[c])) for c in reps]
    xm = arr.mean(axis=1)                       # середні генотипів
    # матриця плану для g₁…g_{p−1} (g_p = −Σ решти)
    A = np.zeros((v, p))
    for n, (i, j) in enumerate(need):
        A[n, i] += 1; A[n, j] += 1              # для i = j отримуємо 2
    C = np.zeros((p, p - 1)); C[:p - 1] = np.eye(p - 1); C[p - 1] = -1.0
    Ad = A @ C
    mu = xm.mean()
    gam, *_ = np.linalg.lstsq(Ad, xm - mu, rcond=None)
    gca = C @ gam
    fitted = A @ gca
    sca_vec = xm - mu - fitted
    SSg_m = float(np.sum(fitted ** 2)); SSs_m = float(np.sum(sca_vec ** 2)); SSgeno_m = float(np.sum((xm - mu) ** 2))
    gm = arr.mean()
    SSgeno = r * SSgeno_m
    SSrep = v * float(np.sum((arr.mean(axis=0) - gm) ** 2))
    SStot = float(np.sum((arr - gm) ** 2))
    SSerr = SStot - SSgeno - SSrep
    df_g, df_geno = p - 1, v - 1
    df_s = df_geno - df_g
    df_e = (v - 1) * (r - 1)
    MSg, MSs = SSg_m / df_g, SSs_m / df_s
    MSe_plot = SSerr / df_e if df_e > 0 else NAN
    Me = MSe_plot / r                           # похибка середнього
    out = {"n_par": p, "v": v, "r": r, "method": method, "model": model, "parents": parents, "mean": float(mu),
           "gca": gca, "need": need, "xm": xm, "sca_vec": sca_vec,
           "SS_means": {"gca": SSg_m, "sca": SSs_m, "geno": SSgeno_m},
           "SS": {"gca": r * SSg_m, "sca": r * SSs_m, "geno": SSgeno, "rep": SSrep, "err": SSerr, "tot": SStot},
           "df": {"gca": df_g, "sca": df_s, "geno": df_geno, "err": df_e, "rep": r - 1},
           "MS": {"gca": MSg, "sca": MSs}, "Me": Me, "MSE_plot": MSe_plot}
    S = np.full((p, p), np.nan)
    for n, (i, j) in enumerate(need):
        S[i, j] = S[j, i] = sca_vec[n]
    out["sca"] = S
    k_ = (p + 2) if method == 2 else (p - 2)
    out["se_gca"] = math.sqrt((p - 1) / (p * k_) * Me) if Me == Me else NAN
    out["se_gca_diff"] = math.sqrt(2.0 / k_ * Me) if Me == Me else NAN
    if r >= 2 and df_e > 0:
        if model == "I":
            Fg, Fs = MSg / Me, MSs / Me
            pg = float(stats.f.sf(Fg, df_g, df_e)); ps = float(stats.f.sf(Fs, df_s, df_e))
            out["F"] = {"gca": Fg, "sca": Fs}; out["p"] = {"gca": pg, "sca": ps}
        else:
            Fg = MSg / MSs; Fs = MSs / Me
            out["F"] = {"gca": Fg, "sca": Fs}
            out["p"] = {"gca": float(stats.f.sf(Fg, df_g, df_s)), "sca": float(stats.f.sf(Fs, df_s, df_e))}
        vg_raw = (MSg - MSs) / k_
        vs_raw = MSs - Me
        out["var_gca"] = max(vg_raw, 0.0); out["var_sca"] = max(vs_raw, 0.0)
        out["var_raw"] = (vg_raw, vs_raw); out["var_e"] = Me
        d = 2 * out["var_gca"] + out["var_sca"]
        out["baker"] = 2 * out["var_gca"] / d if d > 0 else NAN
        if vg_raw < 0: warn.append("Оцінка σ²gca від'ємна — прийнято 0.")
        if vs_raw < 0: warn.append("Оцінка σ²sca від'ємна — прийнято 0.")
    else:
        out["F"] = {"gca": NAN, "sca": NAN}; out["p"] = {"gca": NAN, "sca": NAN}
        out["var_gca"] = out["var_sca"] = out["baker"] = NAN
        warn.append("Одна повторність: F-тести й компоненти дисперсії неможливі (немає оцінки похибки).")
    if method == 4 and p < 5: warn.append("Метод 4 при p = 4 має лише 2 ст. свободи для SCA.")
    out["warnings"] = warn
    return out


def diallel_closed_form_gca(xm, need, p, method):
    """Закриті формули Гріффінга для ĝᵢ (виведені з нормальних рівнянь): метод 2 —
    ĝᵢ = [Yᵢ. + Yᵢᵢ − (2/p)Y..]/(p+2); метод 4 — ĝᵢ = [Yᵢ. − (2/p)Y..]/(p−2). Для перевірки МНК-розв'язку."""
    X = np.zeros((p, p))
    for val, (i, j) in zip(xm, need):
        X[i, j] = X[j, i] = val
    if method == 2:
        Yi = X.sum(axis=1)
        Yd = np.diag(X)
        Y = sum(xm)
        return (Yi + Yd - 2.0 / p * Y) / (p + 2)
    Yi = X.sum(axis=1)
    Y = sum(xm)
    return (Yi - 2.0 / p * Y) / (p - 2)


# ═══════════════════════════════════════════════════════════════
# 4. Індекси стресостійкості
# ═══════════════════════════════════════════════════════════════
STRESS_INFO = [
    ("TOL", "Толерантність TOL = Yp − Ys", "Rosielle & Hamblin 1981", "мін.", False),
    ("MP", "Середня продуктивність MP = (Yp + Ys)/2", "Rosielle & Hamblin 1981", "макс.", True),
    ("GMP", "Геометрична середня GMP = √(Yp·Ys)", "Fernandez 1992", "макс.", True),
    ("HM", "Гармонічна середня HM = 2·Yp·Ys/(Yp + Ys)", "Jafari et al. 2009", "макс.", True),
    ("SSI", "Індекс чутливості до стресу SSI = (1 − Ys/Yp)/SI", "Fischer & Maurer 1978", "мін.", False),
    ("STI", "Індекс толерантності до стресу STI = Yp·Ys/Ȳp²", "Fernandez 1992", "макс.", True),
    ("YI", "Індекс урожайності YI = Ys/Ȳs", "Gavuzzi et al. 1997", "макс.", True),
    ("YSI", "Індекс стабільності врожайності YSI = Ys/Yp", "Bouslama & Schapaugh 1984", "макс.", True),
    ("RSI", "Відносний індекс стресу RSI = (Ys/Yp)/(Ȳs/Ȳp)", "Fischer & Wood 1979", "макс.", True),
]


def stress_indices(yp, ys):
    """Індекси стресостійкості за врожаєм у сприятливих (Yp) і стресових (Ys) умовах.
    SI = 1 − Ȳs/Ȳp — інтенсивність стресу. Групи Фернандеса: A (високий Yp і Ys), B (лише Yp),
    C (лише Ys), D (низькі в обох) — за порівнянням із середніми."""
    yp = np.asarray(yp, float); ys = np.asarray(ys, float)
    if yp.shape != ys.shape or yp.ndim != 1: raise BreedingError("Yp і Ys мають бути однакової довжини.")
    if len(yp) < 3: raise BreedingError("Потрібно щонайменше 3 генотипи.")
    if np.any(np.isnan(yp)) or np.any(np.isnan(ys)): raise BreedingError("У даних є порожні або нечислові значення.")
    if np.any(yp <= 0) or np.any(ys <= 0):
        raise BreedingError("Індекси GMP, HM, SSI, YSI визначені лише для додатних значень врожаю (Yp > 0, Ys > 0).")
    mp_, ms_ = yp.mean(), ys.mean()
    SI = 1.0 - ms_ / mp_
    out = {"n": len(yp), "Yp": yp, "Ys": ys, "mean_Yp": float(mp_), "mean_Ys": float(ms_), "SI": float(SI)}
    out["TOL"] = yp - ys
    out["MP"] = (yp + ys) / 2
    out["GMP"] = np.sqrt(yp * ys)
    out["HM"] = 2 * yp * ys / (yp + ys)
    out["SSI"] = (1 - ys / yp) / SI if abs(SI) > 1e-12 else np.full(len(yp), NAN)
    out["STI"] = yp * ys / mp_ ** 2
    out["YI"] = ys / ms_
    out["YSI"] = ys / yp
    out["RSI"] = (ys / yp) / (ms_ / mp_)
    grp = []
    for a, b in zip(yp, ys):
        grp.append("A" if (a >= mp_ and b >= ms_) else "B" if a >= mp_ else "C" if b >= ms_ else "D")
    out["group"] = grp
    ranks = {"Yp": rank_desc(yp), "Ys": rank_desc(ys)}
    for key, _, _, direction, higher in STRESS_INFO:
        v = out[key]
        if np.all(np.isnan(v)): continue
        ranks[key] = rank_desc(v) if higher else rank_asc(v)
    out["ranks"] = ranks
    R = np.column_stack(list(ranks.values()))
    out["rank_mean"] = R.mean(axis=1); out["rank_sd"] = R.std(axis=1, ddof=1)
    # кореляції індексів з Yp та Ys (критерій Фернандеса — обирати індекс, що корелює з обома)
    cors = {}
    for key, *_ in STRESS_INFO:
        v = out[key]
        if np.all(np.isnan(v)) or np.ptp(v) == 0: continue
        cors[key] = (float(stats.pearsonr(v, yp)[0]), float(stats.pearsonr(v, ys)[0]))
    out["cors"] = cors
    w = []
    if SI <= 0.0: w.append("Середній врожай у стресі не нижчий, ніж у сприятливих умовах (SI ≤ 0): стрес не проявився, "
                           "SSI не визначений, інтерпретація індексів не має змісту.")
    elif SI < 0.10: w.append(f"Інтенсивність стресу низька (SI = {SI:.2f}); індекси мало розрізняють генотипи.")
    if len(yp) < 8: w.append("Мало генотипів: кореляції індексів нестійкі.")
    out["warnings"] = w
    return out


# ═══════════════════════════════════════════════════════════════
# 5. Шляховий аналіз
# ═══════════════════════════════════════════════════════════════
def path_analysis(X, y, x_names=None, y_name="Y"):
    """Шляховий аналіз (Wright; Dewey & Lu): прямі ефекти p = R_xx⁻¹·r_xy, непрямі ефекти
    через інші ознаки r_ij·p_j, залишковий ефект √(1 − R²), VIF і число зумовленості.
    SE(p_i) = √[(1 − R²)·VIF_i/(n − k − 1)] — за стандартизованою регресією."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    if X.ndim != 2: raise BreedingError("X має бути таблицею ознак (рядки — спостереження).")
    n, k = X.shape
    if len(y) != n: raise BreedingError("Довжини X і Y різні.")
    if np.any(np.isnan(X)) or np.any(np.isnan(y)): raise BreedingError("У даних є порожні або нечислові значення.")
    if k < 2: raise BreedingError("Потрібно щонайменше 2 пояснювальні ознаки.")
    if n <= k + 1: raise BreedingError(f"Спостережень ({n}) замало для {k} ознак: потрібно щонайменше {k + 2}.")
    if np.any(np.ptp(X, axis=0) == 0) or np.ptp(y) == 0:
        raise BreedingError("Одна з ознак стала (немає варіації) — кореляція не визначена.")
    names = x_names or [f"X{i+1}" for i in range(k)]
    Z = np.column_stack([X, y])
    Rall = np.corrcoef(Z, rowvar=False)
    Rxx, rxy = Rall[:k, :k], Rall[:k, k]
    cond = float(np.linalg.cond(Rxx))
    if cond > 1e12: raise BreedingError("Матриця кореляцій пояснювальних ознак виродена (ознаки лінійно залежні).")
    Ri = np.linalg.inv(Rxx)
    pcoef = Ri @ rxy
    R2 = float(pcoef @ rxy)
    resid = math.sqrt(max(1.0 - R2, 0.0))
    vif = np.diag(Ri)
    se = np.sqrt(max(1.0 - R2, 0.0) * vif / (n - k - 1))
    tt = pcoef / np.where(se > 0, se, NAN)
    pv = 2 * stats.t.sf(np.abs(tt), n - k - 1)
    indirect = Rxx * pcoef[None, :]
    np.fill_diagonal(indirect, 0.0)                     # indirect[i, j] = r_ij·p_j (через j)
    w = []
    if np.any(vif > 10): w.append("VIF > 10 для: " + ", ".join(names[i] for i in range(k) if vif[i] > 10) +
                                  ". Ознаки сильно колінеарні — прямі ефекти нестійкі, можуть мати «хибний» знак.")
    if cond > 30: w.append(f"Число зумовленості матриці кореляцій = {cond:.0f} (> 30): шляхові коефіцієнти чутливі до "
                           f"малих змін у даних.")
    if n < 5 * k: w.append(f"Спостережень ({n}) менше ніж 5 на ознаку ({5 * k}): оцінки ненадійні.")
    if R2 < 0.3: w.append(f"Пояснено лише {100 * R2:.0f} % варіації {y_name}; залишковий ефект великий ({resid:.2f}) — "
                          f"суттєві чинники не враховані.")
    return {"n": n, "k": k, "names": names, "y_name": y_name, "Rxx": Rxx, "rxy": rxy, "direct": pcoef,
            "indirect": indirect, "R2": R2, "residual": resid, "vif": vif, "cond": cond, "se": se, "t": tt, "p": pv,
            "df": n - k - 1, "warnings": w}
