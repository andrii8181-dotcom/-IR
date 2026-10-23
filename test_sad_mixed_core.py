# test_sad_mixed_core.py — REML/BLUP: незалежні еталони (щільна V, аналітичні формули, симуляція)
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import optimize, stats
import sad_mixed_core as M
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(2)

def oneway(g=12, r=4, sg=2.0, se=1.5, seed=2):
    rg = np.random.default_rng(seed); ga = rg.normal(0, sg, g); gen, rep, y = [], [], []
    for i in range(g):
        for k in range(r): gen.append(f"G{i}"); rep.append(f"R{k}"); y.append(50 + ga[i] + rg.normal(0, se))
    return gen, rep, np.array(y)

print("== 1. Функція правдоподібності: рівняння Гендерсона ↔ пряма щільна V")
rg = np.random.default_rng(5); n = 48
gen = [f"G{rg.integers(0, 8)}" for _ in range(n)]; blk = [f"B{rg.integers(0, 5)}" for _ in range(n)]; rep = [f"R{rg.integers(0, 3)}" for _ in range(n)]
y = 10 + rg.normal(0, 2, n)
fac = {"gen": gen, "blk": blk, "rep": rep}
des = M.build_design(y, fac, fixed=["rep"], random=["gen", "blk"])
mme = M._MME(y, des); Zs = [Z.toarray() for _, Z, _ in des["Zs"]]
diffs = []
for _ in range(6):
    s2 = np.exp(rg.normal(0, 0.8, 3))
    diffs.append(mme.negll(s2) - M.reml_negll_dense(y, des["X"], Zs, s2))
check(np.ptp(diffs) < 1e-8, f"−2ℓ (MME) − (ln|V| + ln|X'V⁻¹X| + y'Py) = {diffs[0]:.6f} однакове при 6 різних σ² (розбіжність {np.ptp(diffs):.1e})")
check(abs(diffs[0] - 0.0) < 1e-6, "різниця = 0: формулу виведено без зайвої сталої")

print("\n== 2. Збалансований випадок: REML = ANOVA")
gen, rep, y = oneway(); g, r = 12, 4
res = M.fit_mixed(y, {"gen": gen, "rep": rep}, fixed=[], random=["gen"], pev_terms=["gen"])
Y = y.reshape(g, r); msg = r * np.sum((Y.mean(1) - Y.mean()) ** 2) / (g - 1); mse = np.sum((Y - Y.mean(1, keepdims=True)) ** 2) / (g * (r - 1))
check(res["converged"] and abs(res["sigma2"]["gen"] - (msg - mse) / r) < 1e-4 and abs(res["sigma2"]["Залишок"] - mse) < 1e-4,
      f"σ²g = {res['sigma2']['gen']:.5f} (ANOVA {(msg - mse) / r:.5f}); σ²e = {res['sigma2']['Залишок']:.5f} (ANOVA {mse:.5f})")
# RCBD: фіксовані повторності, випадковий генотип
rb = np.random.default_rng(3).normal(0, 1, r); y2 = y + np.tile(rb, g)
res2 = M.fit_mixed(y2, {"gen": gen, "rep": rep}, fixed=["rep"], random=["gen"], pev_terms=["gen"])
Y2 = y2.reshape(g, r); sse = np.sum((Y2 - Y2.mean(1, keepdims=True) - Y2.mean(0, keepdims=True) + Y2.mean()) ** 2); mse2 = sse / ((g - 1) * (r - 1))
msg2 = r * np.sum((Y2.mean(1) - Y2.mean()) ** 2) / (g - 1)
check(abs(res2["sigma2"]["gen"] - (msg2 - mse2) / r) < 1e-4 and abs(res2["sigma2"]["Залишок"] - mse2) < 1e-4, "RCBD з фіксованими повторностями: REML = ANOVA")

print("\n== 3. BLUP, PEV і спадковість: точні формули збалансованого випадку")
sg, se_ = res2["sigma2"]["gen"], res2["sigma2"]["Залишок"]; h = sg / (sg + se_ / r)
bt = M.blup_table(res2, "gen")
check(np.allclose(bt["blup"], h * (Y2.mean(1) - Y2.mean()), atol=1e-6), f"BLUP = h·(ȳᵢ − ȳ), h = σ²g/(σ²g + σ²e/r) = {h:.4f}")
pev_exact = sg * (1 - h) + h * sg / g          # σ²g(1−h) + hσ²g/g: другий доданок — наслідок оцінювання μ
check(np.allclose(bt["se"] ** 2, pev_exact, atol=1e-6), "PEV = σ²g(1−h) + h·σ²g/g (точна формула; другий доданок — оцінювання середнього μ)")
check(np.allclose(bt["reliability"], h - h / g, atol=1e-6), "надійність = h − h/g; спадковість Каллісу (на різницях BLUP) цей додаток скорочує")
ch = M.cullis_heritability(res2, "gen")
check(abs(ch["h2"] - h) < 1e-6 and ch["kind"] == "Каллісу", f"спадковість за Каллісом = h у збалансованому плані ({ch['h2']:.4f})")
check(np.all(np.abs(bt["blup"]) <= np.abs(Y2.mean(1) - Y2.mean()) + 1e-12), "BLUP стягнуті до середнього (усадка)")
check(abs(bt["blup"].sum()) < 1e-6, "Σ BLUP = 0")

print("\n== 4. Незбалансовані дані: порівняння з прямою оптимізацією щільного REML")
rg = np.random.default_rng(9); g, b = 10, 6
gt = rg.normal(0, 1.5, g); bt_ = rg.normal(0, 1.0, b)
gen, blk, y = [], [], []
for i in range(g):
    for j in rg.choice(b, size=rg.integers(2, 5), replace=False):
        for _ in range(rg.integers(1, 3)):
            gen.append(f"G{i}"); blk.append(f"B{j}"); y.append(20 + gt[i] + bt_[j] + rg.normal(0, 1.0))
y = np.array(y); fac = {"gen": gen, "blk": blk}
des = M.build_design(y, fac, fixed=[], random=["gen", "blk"]); Zs = [Z.toarray() for _, Z, _ in des["Zs"]]
yc = y.copy()
f = lambda th: M.reml_negll_dense(yc, des["X"], Zs, np.exp(th))
best = min((optimize.minimize(f, x0, method="Nelder-Mead", options={"xatol": 1e-8, "fatol": 1e-11, "maxiter": 4000})
            for x0 in (np.zeros(3), np.array([0.5, 0.5, -0.5]), np.array([-1.0, 0.0, 0.0]))), key=lambda r_: r_.fun)
ref = np.exp(best.x)
res = M.fit_mixed(y, fac, fixed=[], random=["gen", "blk"], scale_y=False)
got = np.array([res["sigma2"]["gen"], res["sigma2"]["blk"], res["sigma2"]["Залишок"]])
check(np.allclose(got, ref, rtol=2e-3), f"σ² рушія {np.round(got, 4)} = незалежна оптимізація щільного REML {np.round(ref, 4)} (n = {len(y)}, незбалансовано)")
s2 = got; V = s2[2] * np.eye(len(y)) + s2[0] * Zs[0] @ Zs[0].T + s2[1] * Zs[1] @ Zs[1].T
Vi = np.linalg.inv(V); X = des["X"]
bgls = np.linalg.solve(X.T @ Vi @ X, X.T @ Vi @ y); ugls = [s2[k] * Zs[k].T @ Vi @ (y - X @ bgls) for k in range(2)]
check(np.allclose(res["beta"], bgls, atol=1e-6) and np.allclose(res["u"]["gen"]["blup"], ugls[0], atol=1e-6) and np.allclose(res["u"]["blk"]["blup"], ugls[1], atol=1e-6),
      "β̂ і BLUP збігаються з прямим GLS/BLUP за щільною V")
check(np.allclose(res["beta_cov"], np.linalg.inv(X.T @ Vi @ X), atol=1e-6), "коваріація β̂ = (X'V⁻¹X)⁻¹")
Pfull = np.diag(s2[0] * np.eye(Zs[0].shape[1]) - s2[0] ** 2 * Zs[0].T @ (Vi - Vi @ X @ np.linalg.inv(X.T @ Vi @ X) @ X.T @ Vi) @ Zs[0])
check(np.allclose(res["u"]["gen"]["pev"], Pfull, atol=1e-6), "PEV збігається з прямою формулою G − G Z'PZ G")
perm = np.random.default_rng(1).permutation(len(y))
resp = M.fit_mixed(y[perm], {k: [v[i] for i in perm] for k, v in fac.items()}, fixed=[], random=["gen", "blk"], scale_y=False)
check(np.allclose([resp["sigma2"][k] for k in ("gen", "blk", "Залишок")], got, rtol=1e-3), "результат не залежить від порядку рядків")

print("\n== 5. Стандартні похибки компонентів: Гессіан ↔ аналітична дисперсія")
gen, rep, y = oneway(g=40, r=4, seed=11); res = M.fit_mixed(y, {"gen": gen, "rep": rep}, fixed=[], random=["gen"])
sgh, seh = res["sigma2"]["gen"], res["sigma2"]["Залишок"]; r = 4; g = 40
var_g = 2 / r ** 2 * ((seh + r * sgh) ** 2 / (g - 1) + seh ** 2 / (g * (r - 1))); var_e = 2 * seh ** 2 / (g * (r - 1))
check(abs(res["sigma2_se"]["gen"] / math.sqrt(var_g) - 1) < 0.12 and abs(res["sigma2_se"]["Залишок"] / math.sqrt(var_e) - 1) < 0.12,
      f"SE(σ²g) = {res['sigma2_se']['gen']:.3f} (аналітично {math.sqrt(var_g):.3f}); SE(σ²e) = {res['sigma2_se']['Залишок']:.3f} ({math.sqrt(var_e):.3f})")

print("\n== 6. Тест відношення правдоподібностей для випадкового терму")
rg = np.random.default_rng(21); g, b, r = 20, 8, 3
gen, blk, y = [], [], []
bs = rg.normal(0, 0.0, b); gs = rg.normal(0, 1.5, g)
for i in range(g):
    for j in range(b):
        for k in range(r if j < 3 else 1):
            gen.append(f"G{i}"); blk.append(f"B{j}"); y.append(30 + gs[i] + bs[j] + rg.normal(0, 1.0))
fac = {"gen": gen, "blk": blk}; y = np.array(y)
full = M.fit_mixed(y, fac, fixed=[], random=["gen", "blk"], hessian=False)
rg_ = M.refit_without(full, y, fac, [], ["gen", "blk"], "gen"); lr, p_g = M.lrt_random_term(full, rg_)
rb_ = M.refit_without(full, y, fac, [], ["gen", "blk"], "blk"); lr2, p_b = M.lrt_random_term(full, rb_)
check(p_g < 1e-6 and lr > 20, f"генотипний ефект (σ² = 2,25) виявлено: LR = {lr:.1f}, p = {p_g:.1e}")
check(p_b > 0.05, f"блоковий ефект, якого немає (σ² = 0): LR = {lr2:.2f}, p = {p_b:.2f} — не значущий")
check(abs(M.lrt_random_term(full, full)[1] - 1.0) < 1e-12, "LRT для однакових моделей: p = 1")
bd = M.fit_mixed(y, fac, fixed=[], random=["gen", "blk"], hessian=False)
check("blk" in bd["boundary"] and bd["sigma2"]["blk"] < 0.05, f"σ²blk на межі (≈ {bd['sigma2']['blk']:.4f}) — це позначено в результаті")

print("\n== 7. Незбалансована серія середовищ (20 % комірок відсутні)")
def make_met(seed, g=60, e=5, r=2, miss=0.2):
    rg = np.random.default_rng(seed); ga = rg.normal(0, 1.5, g); ea = rg.normal(0, 2, e); ge = rg.normal(0, 1.0, (g, e))
    gen, env, y = [], [], []
    for i in range(g):
        for j in range(e):
            if rg.random() < miss: continue
            for k in range(r): gen.append(f"G{i}"); env.append(f"E{j}"); y.append(40 + ga[i] + ea[j] + ge[i, j] + rg.normal(0, 1.2))
    return {"gen": gen, "env": env, "ge": [f"{a}|{b}" for a, b in zip(gen, env)]}, np.array(y), ga
fac, y, ga = make_met(31)
t0 = time.time(); rm = M.fit_mixed(y, fac, fixed=["env"], random=["gen", "ge"], pev_terms=["gen"]); el = time.time() - t0
s = rm["sigma2"]; se_ = rm["sigma2_se"]
des = M.build_design(y, fac, fixed=["env"], random=["gen", "ge"]); Zd = [Z.toarray() for _, Z, _ in des["Zs"]]
fd = lambda th: M.reml_negll_dense(y, des["X"], Zd, np.exp(th))
bd_ = optimize.minimize(fd, np.log([s["gen"], s["ge"], s["Залишок"]]) + 0.3, method="Nelder-Mead", options={"xatol": 1e-7, "fatol": 1e-10, "maxiter": 3000})
ref = np.exp(bd_.x); got = np.array([s["gen"], s["ge"], s["Залишок"]])
check(np.allclose(got, ref, rtol=3e-3), f"n = {len(y)}: оцінки рушія {np.round(got, 3)} = щільний REML {np.round(ref, 3)}")
truth = {"gen": 2.25, "ge": 1.0, "Залишок": 1.44}
check(all(abs(s[k] - truth[k]) < 3 * se_[k] for k in truth), "кожна оцінка в межах 3 SE від істинного значення: " + "; ".join(f"{k} {s[k]:.2f}±{se_[k]:.2f}" for k in truth))
check(el < 5, f"швидкодія: {len(y)} спостережень, {len(set(fac['ge']))} рівнів G×E — {el:.2f} с")
est = {"gen": [], "ge": [], "Залишок": []}
for sd in range(100, 140):
    f_, y_, _ = make_met(sd, g=40, e=4, r=2)
    r_ = M.fit_mixed(y_, f_, fixed=["env"], random=["gen", "ge"], hessian=False)
    for k in est: est[k].append(r_["sigma2"][k])
mean_est = {k: float(np.mean(v)) for k, v in est.items()}
check(all(abs(mean_est[k] / truth[k] - 1) < tol for k, tol in (("gen", 0.15), ("ge", 0.15), ("Залишок", 0.06))),
      "незміщеність REML на 40 повторних наборах: " + "; ".join(f"{k} {mean_est[k]:.2f} (істинне {truth[k]})" for k in truth))
bt = M.blup_table(rm, "gen"); gl = [int(l[1:]) for l in bt["levels"]]
check(np.corrcoef(bt["blup"], ga[gl])[0, 1] > 0.85, f"BLUP генотипів корелюють з істинними ефектами: r = {np.corrcoef(bt['blup'], ga[gl])[0, 1]:.3f}")
ch = M.cullis_heritability(rm, "gen"); check(0.5 < ch["h2"] < 1 and ch["kind"] == "Каллісу", f"спадковість за Каллісом = {ch['h2']:.3f}")
check(np.all(bt["se"] > 0) and np.all((bt["reliability"] > 0) & (bt["reliability"] < 1)), "SE > 0, надійність у (0; 1)")

print("\n== 8. Скориговані (МНК) середні для фіксованого генотипу")
rg = np.random.default_rng(41); g, b = 8, 6
gt = rg.normal(0, 1.5, g); bt_ = rg.normal(0, 1.0, b); gen, blk, y = [], [], []
for i in range(g):
    for j in rg.choice(b, 3, replace=False):
        gen.append(f"G{i}"); blk.append(f"B{j}"); y.append(20 + gt[i] + bt_[j] + rg.normal(0, 0.5))
y = np.array(y); fac = {"gen": gen, "blk": blk}
rf = M.fit_mixed(y, fac, fixed=["gen"], random=["blk"], scale_y=False)
lv, lm, lse = M.lsmeans_fixed(rf, "gen")
des = M.build_design(y, fac, fixed=["gen"], random=["blk"]); Zb = des["Zs"][0][1].toarray(); X = des["X"]
V = rf["sigma2"]["Залишок"] * np.eye(len(y)) + rf["sigma2"]["blk"] * Zb @ Zb.T; Vi = np.linalg.inv(V)
bg = np.linalg.solve(X.T @ Vi @ X, X.T @ Vi @ y); Cb = np.linalg.inv(X.T @ Vi @ X)
ref_m, ref_se = [], []
for li in range(g):
    c = np.zeros(X.shape[1]); c[0] = 1.0
    if li > 0: c[li] = 1.0
    ref_m.append(c @ bg); ref_se.append(math.sqrt(c @ Cb @ c))
check(lv == [f"G{i}" for i in range(g)] and np.allclose(lm, ref_m, atol=1e-6) and np.allclose(lse, ref_se, atol=1e-6), "скориговані середні й SE збігаються з прямим GLS")

print("\n== 9. Помилки й крайні випадки")
g_, r_, y_ = oneway(g=5, r=3)
for kw, frag in [(dict(y=np.full(15, 3.0), factors={"gen": g_}, random=["gen"]), "однакові"),
                 (dict(y=np.append(y_[:-1], np.nan), factors={"gen": g_}, random=["gen"]), "порожні"),
                 (dict(y=y_, factors={"gen": ["A"] * 15}, random=["gen"]), "лише один рівень"),
                 (dict(y=y_[:3], factors={"gen": g_[:3]}, random=["gen"]), "Замало"),
                 (dict(y=y_, factors={"gen": g_[:-1]}, random=["gen"]), "довжину")]:
    try: M.fit_mixed(**kw); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
try: M.lsmeans_fixed(res, "gen"); check(False, "мало впасти")
except BreedingError as ex: check("не є фіксованим" in str(ex), "МНК-середні для випадкового терму → зрозуміла помилка")

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЗМІШАНИХ МОДЕЛЕЙ ПРОЙДЕНО")
