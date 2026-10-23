# test_sad_gencorr_core.py — генотипні/фенотипні/середовищні кореляції: тотожності й симуляції
import os, sys, math, time, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_gencorr_core as GC
import sad_selection_core as SC
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

def simulate(g, r, rhoG, h2m, seed, rhoE=0.0, k=2):
    rg = np.random.default_rng(seed)
    sG = np.full((k, k), rhoG) + np.eye(k) * (1 - rhoG); vE = (1 - h2m) / h2m * r
    sE = (np.full((k, k), rhoE) + np.eye(k) * (1 - rhoE)) * vE
    ge = rg.multivariate_normal(np.zeros(k), sG, size=g); gen, rep, Y = [], [], []
    for i in range(g):
        for j in range(r): gen.append(f"G{i}"); rep.append(f"R{j}"); Y.append(ge[i] + rg.multivariate_normal(np.zeros(k), sE))
    return gen, rep, np.array(Y)

print("== 1. Основні величини: незалежний перерахунок")
gen, rep, Y = simulate(24, 3, 0.5, 0.6, 7, rhoE=0.3, k=3)
res = GC.genotypic_correlations(gen, rep, Y, ["A", "B", "C"], n_boot=200)
g, r = 24, 3; arr = np.zeros((g, r, 3))
for a, b, y in zip(gen, rep, Y): arr[int(a[1:]), int(b[1:])] = y
gm = arr.mean((0, 1)); MPg = np.zeros((3, 3)); MPe = np.zeros((3, 3))
for i in range(g):
    d = arr[i].mean(0) - gm; MPg += r * np.outer(d, d)
MPg /= g - 1
for i in range(g):
    for j in range(r):
        d = arr[i, j] - arr[i].mean(0) - arr[:, j].mean(0) + gm; MPe += np.outer(d, d)
MPe /= (g - 1) * (r - 1)
Gn = (MPg - MPe) / r
check(np.allclose(res["G"], Gn) and np.allclose(res["E"], MPe), "G і E збігаються з наївним перебором (G = (MPген − MPпох)/r, E = MPпох)")
rg_ = Gn[0, 1] / math.sqrt(Gn[0, 0] * Gn[1, 1]); rp_ = (Gn[0, 1] + MPe[0, 1]) / math.sqrt((Gn[0, 0] + MPe[0, 0]) * (Gn[1, 1] + MPe[1, 1]))
re_ = MPe[0, 1] / math.sqrt(MPe[0, 0] * MPe[1, 1]); p = res["pairs"][0]
check(abs(p["rG"] - rg_) < 1e-12 and abs(p["rP"] - rp_) < 1e-12 and abs(p["rE"] - re_) < 1e-12, f"rG = {rg_:.4f}, rP(ділянка) = {rp_:.4f}, rE = {re_:.4f} за формулами")
gmeans = arr.mean(1); check(abs(p["rP_mean"] - np.corrcoef(gmeans[:, 0], gmeans[:, 1])[0, 1]) < 1e-12, "rP на середніх = звичайна кореляція Пірсона між середніми генотипів")
Pm = res["P_mean"]; Gxy, Exy = res["G"][0, 1], res["E"][0, 1]
ident = (p["rP_mean"] * math.sqrt(Pm[0, 0] * Pm[1, 1]) - Exy / r) / math.sqrt(res["G"][0, 0] * res["G"][1, 1])
check(abs(ident - p["rG"]) < 1e-12, "тотожність: rG = (rP·√(P₁₁P₂₂) − E₁₂/r)/√(G₁₁G₂₂)")
h2 = res["G"][0, 0] / Pm[0, 0]; check(abs(res["h2"][0] - h2) < 1e-12, "спадковість на рівні середніх h² = G/P")
ref = SC.multitrait_rcbd(gen, rep, Y, ["A", "B", "C"]); check(np.allclose(res["rG"][np.triu_indices(3, 1)], ref["r_gen"][np.triu_indices(3, 1)]), "rG збігається з перевіреним ядром індексів добору (коли дисперсії додатні)")

print("\n== 2. Від'ємна генотипна дисперсія → rG не визначено")
rg2 = np.random.default_rng(3); gen2 = [f"G{i}" for i in range(12) for _ in range(3)]; rep2 = [f"R{j}" for _ in range(12) for j in range(3)]
y = rg2.normal(size=36)
xs = np.tile([0.5, -0.2, 0.7], 12) + np.repeat(rg2.normal(0, 0.0, 12), 3)
Y2 = np.column_stack([xs, y]); r2 = GC.genotypic_correlations(gen2, rep2, Y2, ["x", "y"], n_boot=50)
check(r2["G"][0, 0] < 1e-12 and math.isnan(r2["pairs"][0]["rG"]) and any("НЕ ВИЗНАЧЕНІ" in w for w in r2["warnings"]),
      "ознака без генотипної мінливості: G ≈ 0 (шум 1e-17 не вважається мінливістю), rG = NaN і є попередження")
check(r2["G"][0, 0] < 1e-12 and math.isnan(r2["h2"][0]) or r2["h2"][0] == 0.0, "для такої ознаки h² не оцінюється (NaN або 0), а не довільне число")

print("\n== 3. Попередження про малу кількість генотипів")
w15 = GC.genotypic_correlations(*simulate(15, 3, 0.5, 0.7, 5), ["x", "y"], n_boot=100)["warnings"]
w25 = GC.genotypic_correlations(*simulate(25, 3, 0.5, 0.7, 5), ["x", "y"], n_boot=100)["warnings"]
w40 = GC.genotypic_correlations(*simulate(40, 3, 0.5, 0.7, 5), ["x", "y"], n_boot=100)["warnings"]
check(any("≈ 80 %" in w for w in w15) and any("91–95 %" in w for w in w25) and not any("генотипів:" in w for w in w40), "g = 15 → сильне, g = 25 → м'яке, g = 40 → без попередження")

print("\n== 4. Відтворюваність і межі інтервалів")
d = simulate(30, 3, 0.5, 0.6, 9)
a1 = GC.genotypic_correlations(*d, ["x", "y"], n_boot=300); a2 = GC.genotypic_correlations(*d, ["x", "y"], n_boot=300)
a3 = GC.genotypic_correlations(*d, ["x", "y"], n_boot=300, seed=1)
check(a1["pairs"][0]["rG_lo"] == a2["pairs"][0]["rG_lo"] and a1["pairs"][0]["rG_lo"] != a3["pairs"][0]["rG_lo"], "той самий seed → ті самі інтервали; інший seed → трохи інші")
q = a1["pairs"][0]; check(-1 <= q["rG_lo"] < q["rG_hi"] <= 1 and q["rG_lo99"] <= q["rG_lo"] and q["rG_hi99"] >= q["rG_hi"], "95 % ДІ вкладений у 99 % ДІ, межі в [−1; 1]")

print("\n== 5. Симуляція: покриття бутстреп-ДІ та хибні спрацювання (g = 30, r = 3, h² = 0,6)")
t0 = time.time(); N = 160; B = 250
stats_ = {}
for rho in (0.0, 0.5):
    cov = rt = rb = valid = 0
    for s in range(N):
        pr = GC.genotypic_correlations(*simulate(30, 3, rho, 0.6, 5000 + s), ["x", "y"], n_boot=B)["pairs"][0]
        if math.isnan(pr["rG"]) or math.isnan(pr["rG_lo"]): continue
        valid += 1; cov += pr["rG_lo"] <= rho <= pr["rG_hi"]; rt += pr["rG_p_trad"] < 0.05; rb += not (pr["rG_lo"] <= 0 <= pr["rG_hi"])
    stats_[rho] = (valid, cov / valid, rt / valid, rb / valid)
v0, c0, t_0, b_0 = stats_[0.0]; v5, c5, t_5, b_5 = stats_[0.5]
check(0.88 <= c0 <= 0.99 and 0.88 <= c5 <= 0.99, f"покриття бутстреп-ДІ: {100 * c0:.1f} % (rG = 0) і {100 * c5:.1f} % (rG = 0,5) при номіналі 95 %")
check(t_0 > 0.15, f"«традиційний» критерій (df = g − 2) при істинній rG = 0 хибно відхиляє H₀ у {100 * t_0:.1f} % дослідів (номінал 5 %) — він завищений")
check(b_0 < 0.13 and b_0 < t_0 / 2, f"інтервал без нуля при rG = 0: {100 * b_0:.1f} % — набагато ближче до номіналу")
check(b_5 > 0.25, f"потужність виявлення rG = 0,5 за інтервалом: {100 * b_5:.0f} % (g = 30, h² = 0,6)")
print(f"        (час {time.time() - t0:.0f} с; валідних: {v0}/{N}, {v5}/{N})")

print("\n== 6. Помилки")
for fn, frag in [(lambda: GC.genotypic_correlations(gen[:-1], rep[:-1], Y[:-1], ["A", "B", "C"]), "збалансованим"),
                 (lambda: GC.genotypic_correlations(gen, rep, Y[:, :1], ["A"]), "щонайменше 2"),
                 (lambda: GC.genotypic_correlations(gen[:6], rep[:6], Y[:6], ["A", "B", "C"]), "щонайменше 3")]:
    try: fn(); check(False, f"«{frag}» мало дати помилку")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ГЕНОТИПНИХ КОРЕЛЯЦІЙ ПРОЙДЕНО")
