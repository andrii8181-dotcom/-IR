# test_sad_assoc_core.py – η, рангово-/точково-бісеріальний, таблиці спряженості: еталони та симуляції
import os, sys, math, itertools, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
from scipy.stats import contingency
import sad_assoc_core as A
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(12)

print("== 1. Кореляційне відношення η")
h = A.eta_squared([[1, 2, 3], [2, 3, 4], [3, 4, 5]])
check(abs(h["eta2"] - 0.5) < 1e-12 and abs(h["F"] - 3.0) < 1e-12 and h["df1"] == 2 and h["df2"] == 6, "ручний приклад: η² = 6/12 = 0,5; F = 3 (df 2; 6)")
g = [rng.normal(m, 1.5, n) for m, n in ((10, 8), (11.5, 11), (9.4, 9), (12, 7))]
r = A.eta_squared(g); ref = stats.f_oneway(*g)
check(abs(r["F"] - ref.statistic) < 1e-10 and abs(r["p"] - ref.pvalue) < 1e-12, f"F = {r['F']:.4f}, p = {r['p']:.4g} збігаються зі scipy.f_oneway")
check(abs(r["eta2"] - r["df1"] * r["F"] / (r["df1"] * r["F"] + r["df2"])) < 1e-12 and abs(r["ssb"] + r["ssw"] - np.sum((np.concatenate(g) - np.concatenate(g).mean()) ** 2)) < 1e-9,
      "η² = df₁F/(df₁F + df₂); SS між + SS всередині = загальна SS")
msw = r["ssw"] / r["df2"]; sst = r["ssb"] + r["ssw"]
check(abs(r["omega2"] - (r["ssb"] - r["df1"] * msw) / (sst + msw)) < 1e-12 and r["omega2"] < r["eps2"] < r["eta2"], "ω² < ε² < η² (η² завищує ефект у вибірці) за формулами Hays і Kelley")
lam_lo = r["ci_lo"] * r["n"] / (1 - r["ci_lo"]); lam_hi = r["ci_hi"] * r["n"] / (1 - r["ci_hi"])
check(abs(stats.ncf.cdf(r["F"], r["df1"], r["df2"], lam_lo) - 0.975) < 1e-6 and abs(stats.ncf.cdf(r["F"], r["df1"], r["df2"], lam_hi) - 0.025) < 1e-6,
      f"ДІ η² [{r['ci_lo']:.3f}; {r['ci_hi']:.3f}]: інверсія нецентрального F дає ймовірності 0,975 і 0,025")
check(r["ci_lo"] < r["eta2"] < r["ci_hi"], "інтервал містить оцінку")
kw = stats.kruskal(*g); check(abs(r["kw_H"] - kw.statistic) < 1e-12 and abs(r["kw_eps2"] - kw.statistic / (r["n"] - 1)) < 1e-12, "Kruskal–Wallis H збігається зі scipy; ε²_H = H/(n − 1)")
check(abs(r["levene_p"] - stats.levene(*g, center="median").pvalue) < 1e-12, "p Левена збігається зі scipy")
weak = A.eta_squared([[1.0, 2, 3, 2.5], [2.0, 1.5, 3, 2.2], [2.1, 2.9, 1.2, 2.4]]); check(weak["ci_lo"] == 0.0 and weak["p"] > 0.5, "слабкий ефект: нижня межа ДІ = 0 (а не від'ємна)")
# покриття ДІ (k = 3, n = 10 у групі, μ = 0; 0,5; 1; σ = 1): λ = 5, N = 30, η²_ген = 5/35
sim = np.random.default_rng(3); cov = 0; Ns = 1500; truth = 5 / 35
for _ in range(Ns):
    gg = [sim.normal(m, 1, 10) for m in (0, .5, 1)]; q = A.eta_squared(gg); cov += (q["ci_lo"] <= truth <= q["ci_hi"])
check(0.93 <= cov / Ns <= 0.97, f"покриття 95 % ДІ η²: {100 * cov / Ns:.1f} % на {Ns} симуляціях (істинне значення {truth:.4f})")
for fn, frag in [(lambda: A.eta_squared([[1, 2, 3]]), "щонайменше 2 групи"), (lambda: A.eta_squared([[1, 2, 3], [4]]), "щонайменше 2 спостереження"),
                 (lambda: A.eta_squared([[1, 2], [3, float("nan")]]), "порожні"), (lambda: A.eta_squared([[2, 2, 2], [2, 2, 2]]), "однакові")]:
    try: fn(); check(False, f"«{frag}» мало дати помилку")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
check(A.eta_strength(0.005) == "дуже малий" and A.eta_strength(0.03) == "малий" and A.eta_strength(0.1) == "середній" and A.eta_strength(0.3) == "великий", "шкала Cohen для η²")

print("\n== 2. Дві групи: рангово- й точково-бісеріальний")
t2 = A.two_group_effects([1, 2, 3, 4, 5], [3, 4, 5, 6, 7], n_boot=200)
check(abs(t2["U1"] - 4.5) < 1e-12 and abs(t2["cles"] - 0.18) < 1e-12 and abs(t2["rrb"] + 0.64) < 1e-12, "ручний приклад: U₁ = 3 + 0,5·3 = 4,5; P(X>Y) = 0,18; r_rb = −0,64")
x = rng.normal(0.8, 1, 23); y = rng.normal(0, 1.3, 31); e = A.two_group_effects(x, y, n_boot=300); mw = stats.mannwhitneyu(x, y)
check(abs(e["U1"] - mw.statistic) < 1e-9 and abs(e["p_mw"] - mw.pvalue) < 1e-12, f"U і p Манна–Уітні збігаються зі scipy (U = {e['U1']:.1f})")
delta = (sum(1 for a in x for b in y if a > b) - sum(1 for a in x for b in y if a < b)) / (len(x) * len(y))
check(abs(e["rrb"] - delta) < 1e-12 and abs(e["cles"] - (1 + delta) / 2) < 1e-12, "r_rb = δ Кліффа (наївний перебір усіх пар); P(X>Y) = (1 + r_rb)/2")
check(abs(A.two_group_effects(y, x, n_boot=100)["rrb"] + e["rrb"]) < 1e-12, "заміна груп змінює лише знак")
pb = stats.pointbiserialr(np.r_[np.ones(len(x)), np.zeros(len(y))], np.r_[x, y]); tt = stats.ttest_ind(x, y, equal_var=True)
check(abs(e["rpb"] - pb.statistic) < 1e-12 and abs(e["rpb_p"] - pb.pvalue) < 1e-10 and abs(e["rpb_p"] - tt.pvalue) < 1e-10, "точково-бісеріальний = Пірсон; його p = p t-тесту Стьюдента (збігається зі scipy)")
check(abs(e["p_welch"] - stats.ttest_ind(x, y, equal_var=False).pvalue) < 1e-12, "p t-тесту Велча збігається зі scipy")
a1 = A.two_group_effects(x, y, n_boot=300); check(a1["rrb_lo"] == e["rrb_lo"] and a1["rrb_lo"] < e["rrb"] < a1["rrb_hi"], "бутстреп-ДІ відтворюваний (фіксоване зерно) й містить оцінку")
sg = np.random.default_rng(5); cov = 0; Ns = 400; truth = 2 * stats.norm.cdf(0.8 / math.sqrt(2)) - 1; t0 = time.time()
for _ in range(Ns):
    q = A.two_group_effects(sg.normal(0.8, 1, 25), sg.normal(0, 1, 25), n_boot=300); cov += (q["rrb_lo"] <= truth <= q["rrb_hi"])
check(0.90 <= cov / Ns <= 0.98, f"покриття 95 % бутстреп-ДІ r_rb: {100 * cov / Ns:.1f} % на {Ns} симуляціях (істинне {truth:.3f}; {time.time() - t0:.0f} с)")
for fn, frag in [(lambda: A.two_group_effects([1], [2, 3]), "щонайменше 2"), (lambda: A.two_group_effects([1, 2], [float("nan"), 3]), "порожні"),
                 (lambda: A.two_group_effects([4, 4], [4, 4]), "однакові")]:
    try: fn(); check(False, f"«{frag}» мало дати помилку")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
check(A.rrb_strength(0.05) == "дуже малий" and A.rrb_strength(0.2) == "малий" and A.rrb_strength(0.35) == "середній" and A.rrb_strength(0.6) == "великий", "шкала розміру ефекту r_rb")

print("\n== 3. Таблиці спряженості")
c = A.contingency_analysis([[10, 20], [30, 40]], n_boot=200)
check(abs(c["chi2"] - 0.79365079) < 1e-6 and abs(c["V"] - 0.0890871) < 1e-6 and abs(c["phi"] + 0.0890871) < 1e-6 and abs(c["OR"] - 2 / 3) < 1e-12, "ручний приклад: χ² = 0,7937; V = 0,0891; φ = −0,0891; OR = 0,667")
T = rng.integers(2, 30, size=(3, 4)); q = A.contingency_analysis(T, n_boot=100, n_mc=2000); ref = stats.chi2_contingency(T, correction=False)
check(abs(q["chi2"] - ref[0]) < 1e-10 and abs(q["p_chi2"] - ref[1]) < 1e-12 and q["dof"] == ref[2], "χ², p, df збігаються зі scipy.chi2_contingency")
check(abs(q["V"] - contingency.association(T, method="cramer")) < 1e-12 and abs(q["T"] - contingency.association(T, method="tschuprow")) < 1e-12 and abs(q["C"] - contingency.association(T, method="pearson")) < 1e-12,
      "V Крамера, T Чупрова, C Пірсона збігаються зі scipy.stats.contingency.association")
n_ = T.sum(); r_, c_ = T.shape; phi2 = q["chi2"] / n_
phi2c = max(0, phi2 - (r_ - 1) * (c_ - 1) / (n_ - 1)); rc = r_ - (r_ - 1) ** 2 / (n_ - 1); cc = c_ - (c_ - 1) ** 2 / (n_ - 1)
check(abs(q["V_corr"] - math.sqrt(phi2c / min(rc - 1, cc - 1))) < 1e-12 and q["V_corr"] <= q["V"], "V зі зміщенням скоригований за Bergsma (2013) і не перевищує звичайного V")
check(abs(q["C_adj"] - q["C"] / math.sqrt((min(r_, c_) - 1) / min(r_, c_))) < 1e-12 and q["C_adj"] > q["C"], "C скоригований на C_max")
ind = A.contingency_analysis([[20, 30], [40, 60]], n_boot=100)
check(ind["chi2"] < 1e-12 and ind["V"] < 1e-6 and ind["V_corr"] == 0.0, "таблиця незалежності: χ² = 0, V = 0")
tr = A.contingency_analysis(T.T, n_boot=100, n_mc=2000)
check(abs(tr["V"] - q["V"]) < 1e-12 and abs(tr["T"] - q["T"]) < 1e-12 and np.allclose(tr["adj_resid"], q["adj_resid"].T), "транспонування не змінює V, T, залишки (лише транспонуються)")
check(abs(np.sum((q["table"] - q["expected"]) ** 2 / q["expected"]) - q["chi2"]) < 1e-9 and np.all(np.sign(q["adj_resid"]) == np.sign(q["table"] - q["expected"])), "Σ залишків² = χ²; знак скоригованого залишку = знак (O − E)")
f2 = A.contingency_analysis([[3, 1], [1, 3]], n_boot=100); check(abs(f2["p_exact"] - stats.fisher_exact([[3, 1], [1, 3]]).pvalue) < 1e-12 and "Фішера" in f2["exact_kind"], "2×2: точний p збігається зі scipy.fisher_exact")
# повний перебір для r×c (2×3, n = 12) ↔ Монте-Карло
Tt = np.array([[1, 4, 2], [5, 0, 0]]); rs, cs = Tt.sum(1), Tt.sum(0); n12 = Tt.sum()
def chi_of(t): E = np.outer(t.sum(1), t.sum(0)) / n12; return float(np.sum((t - E) ** 2 / E))
obs = chi_of(Tt); pe = 0.0
from math import comb
for a in range(0, min(rs[0], cs[0]) + 1):
    for b in range(0, min(rs[0] - a, cs[1]) + 1):
        cc3 = rs[0] - a - b
        if cc3 < 0 or cc3 > cs[2]: continue
        t = np.array([[a, b, cc3], [cs[0] - a, cs[1] - b, cs[2] - cc3]])
        if (t < 0).any(): continue
        prob = (math.prod(math.factorial(x) for x in rs) * math.prod(math.factorial(x) for x in cs)) / (math.factorial(n12) * math.prod(math.factorial(int(x)) for x in t.ravel()))
        if chi_of(t) >= obs - 1e-9: pe += prob
mc = A.contingency_analysis(Tt, n_boot=100, n_mc=30000)
check(abs(mc["p_exact"] - pe) < 0.012 and "Монте-Карло" in mc["exact_kind"], f"r×c: Монте-Карло p = {mc['p_exact']:.4f} ≈ точний перебір усіх таблиць p = {pe:.4f}")
check(any("Малі очікувані" in w for w in mc["warnings"]), "малі очікувані частоти → попередження")
# покриття бутстреп-ДІ для V (3×3)
P = np.array([[.15, .05, .05], [.05, .20, .05], [.05, .05, .35]]); pr = P.sum(1)[:, None] * P.sum(0)[None, :]; Vpop = math.sqrt(np.sum((P - pr) ** 2 / pr) / 2)
sv = np.random.default_rng(9); cov = 0; Ns = 300
for _ in range(Ns):
    tb = sv.multinomial(200, P.ravel()).reshape(3, 3); z = A.contingency_analysis(tb, n_boot=300, n_mc=500); cov += (z["V_lo"] <= Vpop <= z["V_hi"])
check(0.85 <= cov / Ns <= 0.98, f"покриття бутстреп-ДІ V (n = 200, 3×3): {100 * cov / Ns:.1f} % (істинне V = {Vpop:.3f})")
z0 = A.contingency_analysis([[0, 10], [10, 10]], n_boot=100); check(z0["OR_corrected"] and any("0,5" in w for w in z0["warnings"]) and z0["OR"] > 0, "нульова клітинка: OR із поправкою 0,5 і попередження")
dz = A.contingency_analysis([[5, 0, 3], [0, 0, 0], [2, 4, 6]], n_boot=100, n_mc=500); check(dz["r"] == 2 and dz["c"] == 3 and any("нульовою сумою" in w for w in dz["warnings"]), "нульовий рядок виключено з попередженням")
tc = A.crosstab(["a", "a", "b", "b", "b"], ["x", "y", "x", "x", "y"]); check(tc[0].tolist() == [[1, 1], [2, 1]] and tc[1] == ["a", "b"] and tc[2] == ["x", "y"], "crosstab зі списків спостережень")
tw = A.crosstab(["a", "b", "a"], ["x", "x", "y"], [3, 2, 4]); check(tw[0].tolist() == [[3, 4], [2, 0]], "crosstab із частотами")
for fn, frag in [(lambda: A.contingency_analysis([[1, -2], [3, 4]]), "невід'ємними"), (lambda: A.contingency_analysis([[1.5, 2], [3, 4]]), "цілими"),
                 (lambda: A.contingency_analysis([[5, 6, 7]]), "щонайменше 2 рядки"), (lambda: A.contingency_analysis([[1, 1], [1, 1]]), "Замало"),
                 (lambda: A.crosstab(["a"], ["b"], [-1]), "невід'ємними")]:
    try: fn(); check(False, f"«{frag}» мало дати помилку")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
check(A.v_strength(0.05, 1) == "дуже малий" and A.v_strength(0.2, 1) == "малий" and A.v_strength(0.4, 1) == "середній" and A.v_strength(0.6, 1) == "великий", "шкала Cohen для V")
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ АСОЦІАЦІЇ ЗМІННИХ ПРОЙДЕНО")
