# test_sad_breeding_core.py — генетичні параметри, комбінаційна здатність, стрес-індекси, шляховий аналіз
import os, sys, math, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_gxe_core as GX
import sad_breeding_core as B

FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
def close(a, b, tol=1e-9): return bool(np.all(np.abs(np.asarray(a, float) - np.asarray(b, float)) <= tol))
rng = np.random.default_rng(11)

def make_rcbd(g, r, sg2, se2, mu=50.0, rng=rng):
    ga = rng.normal(0, math.sqrt(sg2), g); gen, rep, y = [], [], []
    rb = rng.normal(0, 1.0, r)
    for i in range(g):
        for k in range(r):
            gen.append(f"G{i}"); rep.append(f"R{k}"); y.append(mu + ga[i] + rb[k] + rng.normal(0, math.sqrt(se2)))
    return gen, rep, y

print("== 1. Генетичні параметри (один дослід)")
gen, rep, y = make_rcbd(12, 4, 4.0, 3.0)
gp = B.genetic_parameters_single(gen, rep, y)
check(close(gp["SS"]["gen"] + gp["SS"]["rep"] + gp["SS"]["err"], gp["SS"]["tot"], 1e-8), "SS розкладається точно: генотипи + повторності + похибка = загальна")
check(gp["df"] == {"gen": 11, "rep": 3, "err": 33}, f"ступені свободи {gp['df']}")
if gp["F"] > 1: check(close(gp["h2_mean"], 1 - 1 / gp["F"], 1e-10), "H²(середнє) = 1 − 1/F — точна тотожність")
vg = max((gp["MS"]["gen"] - gp["MS"]["err"]) / 4, 0)
check(close(gp["var_g"], vg) and close(gp["var_p"], vg + gp["MS"]["err"]) and close(gp["h2_plot"], vg / (vg + gp["MS"]["err"])), "σ²g, σ²p, H² за визначенням")
check(close(gp["GCV"], 100 * math.sqrt(vg) / gp["mean"]) and close(gp["PCV"], 100 * math.sqrt(vg + gp["MS"]["err"]) / gp["mean"]), "GCV і PCV за визначенням")
check(close(gp["GA"], 2.06 * gp["h2_plot"] * math.sqrt(gp["var_p"])) and close(gp["GAM"], 100 * gp["GA"] / gp["mean"]), "GA = k·H²·σp (k = 2,06), GAM = 100·GA/x̄")
check(gp["GCV"] <= gp["PCV"] + 1e-12, "GCV ≤ PCV")
# Велика вибірка: оцінки близькі до істинних
gen2, rep2, y2 = make_rcbd(300, 3, 4.0, 3.0, rng=np.random.default_rng(5))
big = B.genetic_parameters_single(gen2, rep2, y2)
check(abs(big["var_g"] - 4.0) / 4.0 < 0.20 and abs(big["var_e"] - 3.0) / 3.0 < 0.12, f"велика вибірка: σ²g = {big['var_g']:.2f} (істинне 4), σ²e = {big['var_e']:.2f} (істинне 3)")
check(abs(big["h2_plot"] - 4 / 7) < 0.06, f"H² на ділянку = {big['h2_plot']:.3f} (істинне 0,571)")
# Покриття довірчого інтервалу Knapp (g=20, r=3, σ²g=1, σ²e=2 → H²(середнє) = 0,6)
sim_rng = np.random.default_rng(2024); cover = 0; N = 2500
for _ in range(N):
    gn, rp, yy = make_rcbd(20, 3, 1.0, 2.0, rng=sim_rng)
    res = B.genetic_parameters_single(gn, rp, yy)
    lo, hi = res["h2_mean_ci"]; cover += (lo <= 0.6 <= hi)
check(0.935 <= cover / N <= 0.965, f"95 % довірчий інтервал Knapp: емпіричне покриття {100 * cover / N:.1f} % (істинне H² = 0,6)")
# Від'ємна оцінка
Y0 = []; g0, r0 = [], []
for i in range(6):
    for k, d in enumerate((-1.0, 0.0, 1.0)):
        g0.append(f"G{i}"); r0.append(f"R{k}"); Y0.append(10 + d + (0.3 if (i + k) % 2 else -0.3))
gz = B.genetic_parameters_single(g0, r0, Y0)
check(gz["var_g_raw"] < 0 and gz["var_g"] == 0 and gz["h2_plot"] == 0 and any("не відрізняється від нуля" in w for w in gz["warnings"]),
      "від'ємна σ²g → 0 і попередження (а не від'ємна спадковість)")
check(any("не відрізняються" in w for w in gz["warnings"]), "F-тест незначущий → попередження про ненадійність H² і GA")
for bad in ((gen[:-1], rep[:-1], y[:-1]), (gen + ["G0"], rep + ["R0"], y + [1.0])):
    try: B.genetic_parameters_single(*bad); check(False, "мало впасти")
    except B.BreedingError: pass
check(True, "незбалансовані/дубльовані дані → зрозуміла помилка")
check(B._cat(65, 30, 60) == "високий" and B._cat(45, 30, 60) == "середній" and B._cat(10, 30, 60) == "низький", "категорії H² (Johnson et al.: <30 / 30–60 / >60 %)")

print("\n== 2. Генетичні параметри за кількома середовищами")
def make_met(g, e, r, sg2, sge2, se2, mu=30.0, seed=3):
    rg = np.random.default_rng(seed); ga = rg.normal(0, math.sqrt(sg2), g); ea = rg.normal(0, 2.0, e)
    ge = rg.normal(0, math.sqrt(sge2), (g, e)); rb = rg.normal(0, 0.5, (e, r))
    G_, E_, R_, Y_ = [], [], [], []
    for i in range(g):
        for j in range(e):
            for k in range(r):
                G_.append(f"G{i}"); E_.append(f"E{j}"); R_.append(f"R{k}")
                Y_.append(mu + ga[i] + ea[j] + ge[i, j] + rb[j, k] + rg.normal(0, math.sqrt(se2)))
    return G_, E_, R_, Y_
gm_, em_, rm_, ym_ = make_met(60, 8, 3, 2.0, 1.0, 1.5)
gmm = B.genetic_parameters_multi(gm_, em_, rm_, ym_)
check(abs(gmm["var_g"] - 2.0) / 2.0 < 0.30 and abs(gmm["var_ge"] - 1.0) / 1.0 < 0.30 and abs(gmm["var_e"] - 1.5) / 1.5 < 0.15,
      f"σ²g = {gmm['var_g']:.2f} (2), σ²ge = {gmm['var_ge']:.2f} (1), σ²e = {gmm['var_e']:.2f} (1,5) — близько до істинних")
vpm = gmm["var_g"] + gmm["var_ge"] / 8 + gmm["var_e"] / 24
check(close(gmm["var_p"], vpm) and close(gmm["h2"], gmm["var_g"] / vpm), "σ²p = σ²g + σ²ge/e + σ²e/(r·e); H² = σ²g/σ²p")
check(0 < gmm["h2"] < 1 and gmm["h2_ci_F"][0] < gmm["h2"] < gmm["h2_ci_F"][1], "H² у межах (0;1) і всередині довірчого інтервалу")
check(close(gmm["GA"], 2.06 * gmm["h2"] * math.sqrt(gmm["var_p"])), "GA за кількома середовищами")

print("\n== 3. Лінія × тестер")
def make_lt(l, t, r, seed=9, noise=0.4):
    rg = np.random.default_rng(seed)
    a = rg.normal(0, 1.2, l); a -= a.mean(); b = rg.normal(0, 0.9, t); b -= b.mean()
    s = rg.normal(0, 0.7, (l, t)); s -= s.mean(axis=0); s -= s.mean(axis=1, keepdims=True)
    rb = rg.normal(0, 0.3, r)
    L_, T_, R_, Y_ = [], [], [], []
    for i in range(l):
        for j in range(t):
            for k in range(r):
                L_.append(f"L{i}"); T_.append(f"T{j}"); R_.append(f"R{k}")
                Y_.append(20 + a[i] + b[j] + s[i, j] + rb[k] + rg.normal(0, noise))
    return (L_, T_, R_, Y_), a, b, s
(args), a_true, b_true, s_true = make_lt(8, 4, 3)
lt = B.line_tester(*args)
check(close(lt["gca_line"].sum(), 0, 1e-9) and close(lt["gca_tester"].sum(), 0, 1e-9), "ΣGCA ліній = 0, ΣGCA тестерів = 0")
check(close(lt["sca"].sum(axis=0), 0, 1e-9) and close(lt["sca"].sum(axis=1), 0, 1e-9), "суми SCA за рядками й стовпцями = 0")
r_, l_, t_ = 3, 8, 4
check(close(lt["SS"]["line"], r_ * t_ * np.sum(lt["gca_line"] ** 2)), "SS ліній = r·t·Σ gᵢ²")
check(close(lt["SS"]["tester"], r_ * l_ * np.sum(lt["gca_tester"] ** 2)), "SS тестерів = r·l·Σ gⱼ²")
check(close(lt["SS"]["lt"], r_ * np.sum(lt["sca"] ** 2)), "SS L×T = r·Σ sᵢⱼ²")
check(close(lt["SS"]["line"] + lt["SS"]["tester"] + lt["SS"]["lt"], lt["SS"]["cross"]), "SS ліній + тестерів + L×T = SS схрещувань")
check(close(lt["SS"]["rep"] + lt["SS"]["cross"] + lt["SS"]["err"], lt["SS"]["tot"]), "SS повторностей + схрещувань + похибки = загальна")
check(lt["df"] == {"rep": 2, "cross": 31, "line": 7, "tester": 3, "lt": 21, "err": 62}, f"ст. свободи {lt['df']}")
check(np.max(np.abs(lt["gca_line"] - a_true)) < 0.45 and np.max(np.abs(lt["sca"] - s_true)) < 0.8, "ефекти GCA/SCA близькі до істинних")
check(lt["p"]["line"] < 0.05 and lt["p"]["lt"] < 0.05, "сильні ефекти ліній і L×T значущі")
check(abs(lt["F"]["line"] - lt["MS"]["line"] / lt["MS"]["lt"]) < 1e-12 and abs(lt["F"]["lt"] - lt["MS"]["lt"] / lt["MS"]["err"]) < 1e-12, "F ліній — проти L×T; F L×T — проти похибки")
ca_ = (7 * (lt["MS"]["line"] - lt["MS"]["lt"]) + 3 * (lt["MS"]["tester"] - lt["MS"]["lt"])) / (3 * (2 * 8 * 4 - 8 - 4))
check(close(lt["cov_hs_avg"], ca_) and close(lt["cov_hs_line"], (lt["MS"]["line"] - lt["MS"]["lt"]) / (3 * 4)), "Cov(HS) за формулами Кемпторна")
check(close(lt["var_sca"], max((lt["MS"]["lt"] - lt["MS"]["err"]) / 3, 0)) and 0 <= lt["baker"] <= 1, "σ²sca = (MS_LT − MSE)/r; коефіцієнт Бейкера в [0;1]")
check(close(sum(lt["contrib"].values()), 100.0), "частки внеску ліній, тестерів і L×T дають 100 %")
check(close(lt["se"]["gca_line"], math.sqrt(lt["mse"] / 12)) and close(lt["se"]["sca"], math.sqrt(lt["mse"] / 3)), "стандартні похибки GCA/SCA")
args_bad = tuple(list(x)[:-1] for x in args)
try: B.line_tester(*args_bad); check(False, "мало впасти")
except B.BreedingError: check(True, "неповна схема → зрозуміла помилка")

print("\n== 4. Діалель за Гріффінгом")
def make_dial(p, r, method, seed=4, noise=0.3, with_parents=None):
    """Дані з параметричними g (Σg = 0) та SCA, що задовольняє обмеження Гріффінга: sᵢⱼ береться як
    залишок проєкції випадкової матриці на простір [1, адитивна частина] — тоді «істинні» ефекти
    точно відповідають параметрам моделі, а відхилення оцінок зумовлені лише шумом."""
    rg = np.random.default_rng(seed)
    g = rg.normal(0, 1.0, p); g -= g.mean()
    need = [(i, j) for i in range(p) for j in range(i, p) if not (method == 4 and i == j)]
    A = np.zeros((len(need), p))
    for n, (i, j) in enumerate(need): A[n, i] += 1; A[n, j] += 1
    Q, _ = np.linalg.qr(np.column_stack([np.ones(len(need)), A[:, :p - 1] - A[:, [p - 1]]]))
    s0 = rg.normal(0, 0.5, len(need)); s_vec = s0 - Q @ (Q.T @ s0)
    s = {k: v for k, v in zip(need, s_vec)}
    P1, P2, R_, Y_ = [], [], [], []
    rb = rg.normal(0, 0.2, r)
    for (i, j) in need:
        for k in range(r):
            P1.append(f"P{i}"); P2.append(f"P{j}"); R_.append(f"R{k}")
            Y_.append(10 + g[i] + g[j] + s[(i, j)] + rb[k] + rg.normal(0, noise))
    return (P1, P2, R_, Y_), g
for method, p in ((2, 6), (4, 7)):
    (args), gtrue = make_dial(p, 3, method)
    d = B.diallel_griffing(*args, method=method)
    cf = B.diallel_closed_form_gca(d["xm"], d["need"], p, method)
    check(close(d["gca"], cf, 1e-10), f"метод {method}: МНК-розв'язок = закрита формула Гріффінга (виведена з нормальних рівнянь)")
    check(close(d["gca"].sum(), 0, 1e-10), f"метод {method}: Σĝᵢ = 0")
    check(close(d["SS_means"]["gca"] + d["SS_means"]["sca"], d["SS_means"]["geno"], 1e-9), f"метод {method}: SS_GCA + SS_SCA = SS генотипів")
    S = d["sca"]
    if method == 2: cons = [S[i, i] * 2 + np.nansum(np.delete(S[i], i)) for i in range(p)]
    else: cons = [np.nansum(np.delete(S[i], i)) for i in range(p)]
    check(close(cons, 0, 1e-9), f"метод {method}: обмеження Гріффінга для SCA виконуються" + (" (Σⱼ sᵢⱼ + sᵢᵢ = 0)" if method == 2 else " (Σ_{j≠i} sᵢⱼ = 0)"))
    exp_df_s = p * (p - 1) // 2 if method == 2 else p * (p - 3) // 2
    check(d["df"]["gca"] == p - 1 and d["df"]["sca"] == exp_df_s, f"метод {method}: ст. свободи GCA = {p-1}, SCA = {exp_df_s}")
    check(np.max(np.abs(d["gca"] - gtrue)) < 0.35, f"метод {method}: ĝᵢ близькі до істинних")
    # SE за ковариаційною матрицею плану
    A = np.zeros((len(d["need"]), p))
    for n, (i, j) in enumerate(d["need"]): A[n, i] += 1; A[n, j] += 1
    C = np.zeros((p, p - 1)); C[:p - 1] = np.eye(p - 1); C[p - 1] = -1.0
    cov = C @ np.linalg.inv((A @ C).T @ (A @ C)) @ C.T
    check(close(math.sqrt(cov[0, 0] * d["Me"]), d["se_gca"], 1e-10), f"метод {method}: SE(ĝᵢ) збігається з МНК-коваріацією")
    check(close(math.sqrt((cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]) * d["Me"]), d["se_gca_diff"], 1e-10), f"метод {method}: SE(ĝᵢ − ĝⱼ) збігається з МНК-коваріацією")
(args_k), _ = make_dial(6, 3, 2)
dk = B.diallel_griffing(*args_k, method=2)
check(dk["n_par"] == 6 and set(dk["p"]) == {"gca", "sca"} and all(0 <= v <= 1 for v in dk["p"].values()),
      "ключі не конфліктують: n_par — кількість батьків, p — словник p-значень GCA/SCA")
# Чисто адитивні дані → SCA = 0, g відновлено точно
p = 5; g = np.array([1.5, -0.5, 0.0, 0.8, -1.8]); P1, P2, R_, Y_ = [], [], [], []
for i in range(p):
    for j in range(i, p):
        for k in range(2):
            P1.append(f"P{i}"); P2.append(f"P{j}"); R_.append(f"R{k}"); Y_.append(10 + g[i] + g[j] + (0.01 if k else -0.01))
dd = B.diallel_griffing(P1, P2, R_, Y_, method=2)
check(close(dd["gca"], g, 1e-9) and close(np.nan_to_num(dd["sca"]), 0, 1e-9), "чисто адитивні дані: ĝ відновлено точно, SCA = 0")
# Моделі I/II
(args), _ = make_dial(6, 3, 2)
d1 = B.diallel_griffing(*args, method=2, model="I"); d2 = B.diallel_griffing(*args, method=2, model="II")
check(close(d1["F"]["gca"], d1["MS"]["gca"] / d1["Me"]) and close(d2["F"]["gca"], d2["MS"]["gca"] / d2["MS"]["sca"]),
      "модель I: F(GCA) = MS_g/MSe′; модель II: F(GCA) = MS_g/MS_s")
check(close(d2["var_raw"][0], (d2["MS"]["gca"] - d2["MS"]["sca"]) / 8) and close(d2["var_raw"][1], d2["MS"]["sca"] - d2["Me"]),
      "σ²g = (MS_g − MS_s)/(p+2), σ²s = MS_s − MSe′ (метод 2)")
(args4), _ = make_dial(7, 3, 4)
d4 = B.diallel_griffing(*args4, method=4, model="II")
check(close(d4["var_raw"][0], (d4["MS"]["gca"] - d4["MS"]["sca"]) / 5), "метод 4: σ²g = (MS_g − MS_s)/(p−2)")
# Помилки й попередження
try: B.diallel_griffing(*args4, method=2); check(False, "метод 2 без батьків мав дати помилку")
except B.BreedingError as ex: check("батьківських форм" in str(ex), "метод 2 без батьківських форм → зрозуміла помилка")
a_i = tuple(list(x)[:-1] for x in args)
try: B.diallel_griffing(*a_i, method=2); check(False, "мало впасти")
except B.BreedingError: check(True, "неповний діалель → зрозуміла помилка")
(args), _ = make_dial(5, 3, 2)
P1, P2, R_, Y_ = [list(x) for x in args]
P1b, P2b, R_b, Y_b = list(P1), list(P2), list(R_), list(Y_)
for a_, b_, c_, v_ in zip(P1, P2, R_, Y_):
    if a_ != b_: P1b.append(b_); P2b.append(a_); R_b.append(c_); Y_b.append(v_ + 0.5)
dr = B.diallel_griffing(P1b, P2b, R_b, Y_b, method=2)
check(any("реципрокні" in w for w in dr["warnings"]), "реципрокні схрещування усереднюються з попередженням")
(args1), _ = make_dial(5, 1, 2)
d_1 = B.diallel_griffing(*args1, method=2)
check(np.isnan(d_1["F"]["gca"]) and any("Одна повторність" in w for w in d_1["warnings"]), "одна повторність: F не вигадується, є попередження")
try: B.diallel_griffing(*make_dial(2, 3, 2)[0], method=2); check(False, "мало впасти")
except B.BreedingError: check(True, "замало батьків → помилка")

print("\n== 5. Індекси стресостійкості — ручний розрахунок")
Yp = np.array([10., 8., 6., 4.]); Ys = np.array([5., 6., 3., 4.])
st = B.stress_indices(Yp, Ys)
check(close(st["SI"], 1 - 4.5 / 7), "SI = 1 − Ȳs/Ȳp = 0,3571")
check(close(st["TOL"], [5, 2, 3, 0]) and close(st["MP"], [7.5, 7, 4.5, 4]), "TOL, MP")
check(close(st["GMP"], np.sqrt([50, 48, 18, 16])) and close(st["HM"], [100 / 15, 96 / 14, 4, 4]), "GMP, HM")
check(close(st["SSI"], np.array([0.5, 0.25, 0.5, 0.0]) / (1 - 4.5 / 7)), "SSI = (1 − Ys/Yp)/SI → 1,4; 0,7; 1,4; 0")
check(close(st["STI"], np.array([50, 48, 18, 16]) / 49) and close(st["YI"], Ys / 4.5), "STI = Yp·Ys/Ȳp², YI = Ys/Ȳs")
check(close(st["YSI"], [0.5, 0.75, 0.5, 1.0]) and close(st["RSI"], np.array([0.5, 0.75, 0.5, 1.0]) / (4.5 / 7)), "YSI, RSI")
check(st["group"] == ["A", "A", "D", "D"], f"групи Фернандеса: {st['group']} (Ȳp = 7: G1, G2 вище; Ȳs = 4,5: G1, G2 вище)")
Yp2 = rng.uniform(5, 12, 30); Ys2 = Yp2 * rng.uniform(0.4, 0.95, 30)
s2 = B.stress_indices(Yp2, Ys2)
check(np.all(s2["HM"] <= s2["GMP"] + 1e-12) and np.all(s2["GMP"] <= s2["MP"] + 1e-12), "нерівність HM ≤ GMP ≤ MP (середні гармонічне ≤ геометричне ≤ арифметичне)")
check(close(s2["GMP"] ** 2, s2["STI"] * s2["mean_Yp"] ** 2), "GMP² = STI·Ȳp²")
check(close(s2["YI"].mean(), 1.0), "середнє YI = 1")
check(close(s2["TOL"], s2["Yp"] - s2["Ys"]) and s2["cors"]["TOL"][0] > 0, "TOL позитивно корелює з Yp")
check(s2["rank_mean"].shape == (30,) and np.all(s2["rank_sd"] >= 0), "середній ранг і SD рангів за всіма індексами")
sw = B.stress_indices([5., 6, 7, 8], [6., 7, 8, 9])
check(sw["SI"] < 0 and any("не проявився" in w for w in sw["warnings"]), "Ys > Yp: попередження «стрес не проявився»")
sw0 = B.stress_indices([5., 6, 7, 8], [5., 6, 7, 8])
check(np.all(np.isnan(sw0["SSI"])), "SI = 0: SSI не визначений (NaN), а не ділення на нуль")
for bad in (([1, 2], [1, 2]), ([1, 2, 3], [1, 2]), ([1, 2, -3], [1, 2, 3]), ([1, 2, np.nan], [1, 2, 3])):
    try: B.stress_indices(*bad); check(False, "мало впасти")
    except B.BreedingError: pass
check(True, "замало/різна довжина/недодатні/порожні значення → зрозуміла помилка")

print("\n== 6. Шляховий аналіз")
n, k = 120, 4
Z = rng.normal(size=(n, k)); Z[:, 1] += 0.6 * Z[:, 0]; Z[:, 3] += 0.5 * Z[:, 2]
yv = Z @ np.array([0.8, -0.3, 0.5, 0.2]) + rng.normal(0, 1.0, n)
pa = B.path_analysis(Z, yv, ["X1", "X2", "X3", "X4"], "Урожай")
zs = (Z - Z.mean(0)) / Z.std(0, ddof=1); ys_ = (yv - yv.mean()) / yv.std(ddof=1)
beta = np.linalg.lstsq(np.column_stack([np.ones(n), zs]), ys_, rcond=None)[0][1:]
check(close(pa["direct"], beta, 1e-10), "прямі ефекти = стандартизовані коефіцієнти МНК")
tot = pa["direct"] + pa["indirect"].sum(axis=1)
check(close(tot, pa["rxy"], 1e-10), "r(Xᵢ,Y) = прямий + Σ непрямих ефектів — точна тотожність")
res = ys_ - zs @ beta
R2_ols = 1 - np.sum(res ** 2) / np.sum(ys_ ** 2)
check(close(pa["R2"], R2_ols, 1e-10) and close(pa["residual"] ** 2, 1 - pa["R2"], 1e-12), "R² збігається з МНК; залишковий ефект² = 1 − R²")
Xd = np.column_stack([np.ones(n), zs]); s2 = np.sum(res ** 2) / (n - k - 1)
se_ols = np.sqrt(np.diag(s2 * np.linalg.inv(Xd.T @ Xd)))[1:]
check(close(pa["se"], se_ols, 1e-9), "SE прямих ефектів збігаються з МНК")
check(close(pa["vif"], np.diag(np.linalg.inv(np.corrcoef(Z, rowvar=False))), 1e-10), "VIF = діагональ R⁻¹")
check(close(pa["p"], 2 * stats.t.sf(np.abs(pa["direct"] / se_ols), n - k - 1), 1e-9), "p-значення t-тестів прямих ефектів")
Zc = Z.copy(); Zc[:, 3] = Zc[:, 0] + Zc[:, 1] + rng.normal(0, 0.05, n)
pc = B.path_analysis(Zc, yv)
check(any("VIF" in w for w in pc["warnings"]) and any("зумовленості" in w for w in pc["warnings"]), "сильна колінеарність → попередження про VIF і число зумовленості")
Zx = Z.copy(); Zx[:, 3] = Zx[:, 0] + Zx[:, 1]
try: B.path_analysis(Zx, yv); check(False, "мало впасти")
except B.BreedingError as ex: check("виродена" in str(ex) or "залежні" in str(ex), "точна лінійна залежність ознак → помилка")
for badargs in ((Z[:5], yv[:5]), (np.column_stack([Z[:, :2], np.ones(n)]), yv)):
    try: B.path_analysis(*badargs); check(False, "мало впасти")
    except B.BreedingError: pass
check(True, "замало спостережень / стала ознака → зрозуміла помилка")
check(any("5 на ознаку" in w for w in B.path_analysis(Z[:15], yv[:15])["warnings"]), "n < 5k → попередження")

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ ПЕРЕВІРКИ СЕЛЕКЦІЙНОГО ЯДРА ПРОЙДЕНО")
