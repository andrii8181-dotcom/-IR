# test_sad_selection_core.py — індекси добору: точні тотожності, таблиці, симуляція добору
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_selection_core as S, sad_breeding_core as BC
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

print("== 1. Інтенсивність добору: табличні значення")
for p, tab in ((0.01, 2.665), (0.05, 2.063), (0.10, 1.755), (0.20, 1.400), (0.50, 0.798)):
    check(abs(S.selection_intensity(p) - tab) < 0.002, f"p = {p:.2f}: i = {S.selection_intensity(p):.3f} (таблиця {tab})")
for bad in (0, 1, -0.1, 1.5):
    try: S.selection_intensity(bad); check(False, f"p = {bad}: мало впасти")
    except BreedingError: pass
check(True, "частка поза (0; 1) відхилена")

print("\n== 2. Коваріації з багатоознакового RCBD")
rg = np.random.default_rng(3); g, r, k = 40, 4, 3
Gtrue = np.array([[4.0, 2.0, -1.0], [2.0, 3.0, 0.5], [-1.0, 0.5, 2.0]]); Etrue = np.array([[3.0, 0.5, 0.0], [0.5, 2.0, 0.3], [0.0, 0.3, 4.0]])
gv = rg.multivariate_normal(np.zeros(k), Gtrue, g); gen, rep, Y = [], [], []
rb = rg.normal(0, 1, (r, k))
for i in range(g):
    for j in range(r):
        gen.append(f"G{i}"); rep.append(f"R{j}"); Y.append(50 + gv[i] + rb[j] + rg.multivariate_normal(np.zeros(k), Etrue))
Y = np.array(Y); mt = S.multitrait_rcbd(gen, rep, Y, ["A", "B", "C"])
for t in range(k):
    cl = BC.genetic_parameters_single(gen, rep, Y[:, t])
    check(abs(mt["G"][t, t] - cl["var_g_raw"]) < 1e-9 and abs(mt["E"][t, t] - cl["var_e"]) < 1e-9, f"ознака {'ABC'[t]}: G_ii = σ²g і E_ii = σ²e з одноознакового аналізу ({mt['G'][t, t]:.3f})")
ysum = Y[:, 0] + Y[:, 1]; cs = BC.genetic_parameters_single(gen, rep, ysum)
check(abs(mt["G"][0, 0] + mt["G"][1, 1] + 2 * mt["G"][0, 1] - cs["var_g_raw"]) < 1e-9, "точна тотожність: Var_g(A + B) = G_AA + G_BB + 2·G_AB (перевірено окремим аналізом суми)")
yd = Y[:, 0] - 2 * Y[:, 2]; cd = BC.genetic_parameters_single(gen, rep, yd)
check(abs(mt["G"][0, 0] + 4 * mt["G"][2, 2] - 4 * mt["G"][0, 2] - cd["var_g_raw"]) < 1e-9, "те саме для A − 2C")
check(np.allclose(mt["G"], mt["G"].T) and np.allclose(mt["E"], mt["E"].T), "G і E симетричні")
check(np.allclose(mt["P_mean"], mt["G"] + mt["E"] / r) and np.allclose(mt["P_plot"], mt["G"] + mt["E"]), "P(середнє) = G + E/r; P(ділянка) = G + E")
check(np.max(np.abs(mt["G"] - Gtrue)) < 2.0 and np.max(np.abs(mt["E"] - Etrue)) < 0.8, f"оцінки близькі до істинних (макс. |ΔG| = {np.max(np.abs(mt['G'] - Gtrue)):.2f}, |ΔE| = {np.max(np.abs(mt['E'] - Etrue)):.2f})")
check(np.allclose(np.diag(mt["r_gen"]), 1) and np.allclose(mt["h2_mean"], np.diag(mt["G"]) / np.diag(mt["P_mean"])), "діагональ генетичних кореляцій = 1; H² на середнє = G_ii/P_ii")
for args, frag in [((gen[:-1], rep[:-1], Y[:-1], list("ABC")), "збалансованим"), ((gen, rep, Y[:, :1], ["A"]), "щонайменше 2 ознаки"),
                   ((gen, rep, np.where(np.arange(len(Y))[:, None] == 3, np.nan, Y), list("ABC")), "порожні")]:
    try: S.multitrait_rcbd(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")

print("\n== 3. Індекси: властивості, що випливають із теорії")
G = mt["G"]; P = mt["P_mean"]; a = np.array([1.0, 0.5, -0.3]); i10 = S.selection_intensity(0.10)
bsh = S.index_coefficients("sh", G, P, a); bb = S.index_coefficients("base", G, P, a)
check(np.allclose(P @ bsh, G @ a), "Сміт–Хейзел: P·b = G·a (за визначенням b = P⁻¹Ga)")
esh = S.expected_response(G, P, a, bsh, i10); eb = S.expected_response(G, P, a, bb, i10)
sH = math.sqrt(a @ G @ a)
check(abs(esh["dH"] - i10 * sH * esh["accuracy"]) < 1e-9, "ΔH = i·σ_H·r_IH (відгук = інтенсивність × мінливість агрегату × точність)")
check(abs(esh["accuracy"] - math.sqrt(a @ G @ np.linalg.solve(P, G @ a) / (a @ G @ a))) < 1e-9, "точність SH = √(aᵀG P⁻¹ G a / aᵀGa)")
check(abs(esh["h2_index"] - (bsh @ G @ bsh) / (bsh @ P @ bsh)) < 1e-12 and 0 < esh["h2_index"] < 1,
      f"спадковість індексу h²_I = bᵀGb/bᵀPb = {esh['h2_index']:.3f} ∈ (0; 1) (≠ r²_IH: рівність лише для однієї ознаки)")
g1 = np.array([[3.0]]); p1 = np.array([[5.0]]); e1 = S.expected_response(g1, p1, np.array([1.0]), np.array([1.0]), 1.0)
check(abs(e1["h2_index"] - e1["accuracy"] ** 2) < 1e-12 and abs(e1["h2_index"] - 0.6) < 1e-12, "для однієї ознаки h²_I = r²_IH = h² = 0,6")
rng = np.random.default_rng(9); worse = 0
for _ in range(500):
    bR = rng.normal(size=3); er = S.expected_response(G, P, a, bR, i10)
    worse += er["accuracy"] <= esh["accuracy"] + 1e-12
check(worse == 500, "жоден із 500 випадкових індексів не має більшої точності, ніж Сміт–Хейзел (максимізує r_IH)")
check(esh["dH"] >= eb["dH"] - 1e-12 and all(esh["dH"] >= S.single_trait_response(G, P, a, j, i10)["dH"] - 1e-12 for j in range(3)), "ΔH(SH) ≥ ΔH(базовий) і ≥ ΔH при доборі за однією ознакою")
sc = S.expected_response(G, P, a, 7.3 * bsh, i10)
check(abs(sc["dH"] - esh["dH"]) < 1e-9 and np.allclose(sc["dG"], esh["dG"]), "відгук не залежить від масштабу b")
d = np.array([2.0, 1.0, -0.5]); bpb = S.index_coefficients("pb", G, P, a=None, d=d)
epb = S.expected_response(G, P, a, bpb, i10)
check(np.allclose(epb["dG"] / epb["dG"][0], d / d[0]), "Песек–Бейкер: приріст за ознаками пропорційний бажаним d")
es = S.single_trait_response(G, P, a, 1, i10)
check(abs(es["dG"][1] - i10 * (G[1, 1] / math.sqrt(P[1, 1]))) < 1e-9 and abs(es["dG"][1] - i10 * (G[1, 1] / P[1, 1]) * math.sqrt(P[1, 1])) < 1e-9,
      "добір за однією ознакою: ΔG_j = i·h²_j·σ_Pj")
check(np.allclose(S.index_scores(np.array([[1.0, 2.0, 3.0], [0.0, 1.0, 0.0]]), np.array([1.0, 0.5, 2.0])), [8.0, 0.5]), "значення індексу bᵀz")
for fn, frag in [(lambda: S.index_coefficients("sh", G, P, None), "ваги"), (lambda: S.index_coefficients("pb", G, P, None, None), "прирости"),
                 (lambda: S.index_coefficients("xx", G, P, a), "Невідомий"), (lambda: S.index_coefficients("pb", np.ones((3, 3)), P, None, d), "вироджена")]:
    try: fn(); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")

print("\n== 4. Симуляція: чи справджується передбачений відгук при реальному доборі")
rg = np.random.default_rng(77); N = 40000
Gt = np.array([[4.0, 2.0, -1.0], [2.0, 3.0, 0.5], [-1.0, 0.5, 2.0]]); Et = np.array([[6.0, 1.0, 0.0], [1.0, 5.0, 0.5], [0.0, 0.5, 7.0]])
gtrue = rg.multivariate_normal(np.zeros(3), Gt, N); ph = gtrue + rg.multivariate_normal(np.zeros(3), Et, N); Pt = Gt + Et
for lab, b in (("Сміт–Хейзел", S.index_coefficients("sh", Gt, Pt, a)), ("базовий", a)):
    idx = ph @ b; top = idx >= np.quantile(idx, 0.90)
    pred = S.expected_response(Gt, Pt, a, b, S.selection_intensity(0.10))
    real_dG = gtrue[top].mean(axis=0); real_dH = float(a @ real_dG)
    check(abs(real_dH / pred["dH"] - 1) < 0.03 and np.allclose(real_dG, pred["dG"], atol=0.07),
          f"{lab}: передбачений ΔH = {pred['dH']:.3f}, реальний (добір верхніх 10 % із 40 000) = {real_dH:.3f}")
idx_sh = ph @ S.index_coefficients("sh", Gt, Pt, a); idx_b = ph @ a
check(float(a @ gtrue[idx_sh >= np.quantile(idx_sh, .9)].mean(0)) > float(a @ gtrue[idx_b >= np.quantile(idx_b, .9)].mean(0)), "у симуляції індекс Сміта–Хейзела дає більший реальний ΔH за базовий")

print("\n== 5. Одноознаковий добір")
v = np.array([10, 12, 14, 16, 18, 20, 22, 24, 26, 28.0]); sr = S.selection_response(v, 0.2, h2=0.5)
check(sr["n_selected"] == 2 and abs(sr["S"] - (27 - 19)) < 1e-12 and abs(sr["R_expected"] - 4.0) < 1e-12, f"S = 27 − 19 = 8, R = h²·S = 4 (n_відібр. = {sr['n_selected']})")
check(abs(S.realized_heritability(4.0, 8.0) - 0.5) < 1e-12, "реалізована спадковість h² = R/S")
try: S.realized_heritability(1.0, 0.0); check(False, "мало впасти")
except BreedingError: check(True, "S = 0 → зрозуміла помилка")

print("\n== 6. «Вигинання» недодатно визначеної матриці")
Mneg = np.array([[2.0, 3.0], [3.0, 2.0]]); Mb, ch = S.bend_psd(Mneg)
check(ch and np.linalg.eigvalsh(Mb).min() > 0, "матриця з від'ємним власним значенням зроблена додатно визначеною")
Mok = np.array([[2.0, 0.5], [0.5, 1.0]]); Mo, ch2 = S.bend_psd(Mok)
check(not ch2 and np.allclose(Mo, Mok), "додатно визначена матриця не змінюється")
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ІНДЕКСІВ ДОБОРУ ПРОЙДЕНО")
