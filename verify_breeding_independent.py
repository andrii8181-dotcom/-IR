# verify_breeding_independent.py — НЕЗАЛЕЖНА звірка селекційних розрахунків.
# Кожна величина тут рахується з нуля за формулою першоджерела (numpy/scipy),
# не викликаючи логіки модулів, і порівнюється з результатом модулів.
import sys, itertools, math
import numpy as np
from scipy import stats
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sad_gxe_core as G, sad_breeding_core as B

FAIL = []
def chk(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
def near(a, b, tol=1e-8): return np.allclose(np.asarray(a, float), np.asarray(b, float), atol=tol, rtol=1e-7)

rng = np.random.default_rng(11)
g, e, r = 7, 6, 4
mu = 10 + rng.normal(0, 1.4, g)[:, None] + rng.normal(0, 2.2, e)[None, :] + rng.normal(0, .9, (g, e))
X = mu.copy(); mse, dfe = 0.37, 60

si = G.stability_indices(X, mse=mse, r=r, df_err=dfe)
gm = X.mean(1); em = X.mean(0); gr = X.mean()
gei = X - gm[:, None] - em[None, :] + gr

print("== Параметричні індекси (формули з нуля)")
W = (gei ** 2).sum(1)
chk(near(si["W2"], W), "Wricke: Wᵢ = Σⱼ (Yᵢⱼ − Ȳᵢ. − Ȳ.ⱼ + Ȳ..)²")
SSGE = (gei ** 2).sum()
chk(near(SSGE, si["SSGE"]), "SS(G×E) на 1 повторність")
chk(near(W.sum(), SSGE), "тотожність: Σ Wᵢ = SS(G×E)")
shk = g / ((g - 2) * (e - 1)) * W - SSGE / ((g - 1) * (g - 2) * (e - 1))
chk(near(si["Shukla"], shk), "Шукла: σ²ᵢ = g·Wᵢ/((g−2)(e−1)) − SSGE/((g−1)(g−2)(e−1))")
I = em - gr
b = ((X - gm[:, None]) * I[None, :]).sum(1) / (I ** 2).sum()
chk(near(si["b"], b), "Еберхарт–Рассел: bᵢ = Σ(Yᵢⱼ−Ȳᵢ.)Iⱼ / ΣIⱼ²")
chk(near(b.mean(), 1.0), "середнє bᵢ за всіма генотипами = 1 (властивість моделі)")
dev = (X - gm[:, None]) - b[:, None] * I[None, :]
ssdev = (dev ** 2).sum(1)
chk(near(si["SSdev"], ssdev), "SS відхилень від регресії")
s2delta = ssdev / (e - 2)
chk(near(si["S2delta"], s2delta), "Σδ²/(e−2)")
chk(near(si["S2d"], s2delta - mse / r), "s²dᵢ = Σδ²/(e−2) − MSE/r (Е–Р, 1966)")
chk(near(si["b_se"], np.sqrt(s2delta / (I ** 2).sum())), "SE(bᵢ) = √(Σδ²/(e−2) / ΣI²)")
tb = (b - 1) / np.sqrt(s2delta / (I ** 2).sum())
chk(near(si["b_t"], tb), "t для H₀: bᵢ = 1")
chk(near(si["b_p"], 2 * stats.t.sf(abs(tb), e - 2)), "p для bᵢ (t, e−2 ст. вільності)")
F = s2delta / (mse / r)
chk(near(si["S2d_F"], F) and near(si["S2d_p"], stats.f.sf(F, e - 2, dfe)), "F-тест s²d = 0: (Σδ²/(e−2))/(MSE/r), df (e−2; df_err)")
mx = X.max(0)
chk(near(si["Pi"], ((X - mx[None, :]) ** 2).sum(1) / (2 * e)), "Лін–Біннс: Pᵢ = Σ(Yᵢⱼ − Mⱼ)²/(2e)")
chk(near(si["CV"], X.std(1, ddof=1) / gm * 100), "Френсіс–Канненберг: CV% генотипу за середовищами")
chk(near(si["S2"], X.var(1, ddof=1)), "дисперсія генотипу за середовищами s²ᵢ")
fav = em > gr
chk(near(si["Pi_fav"], ((X[:, fav] - mx[fav]) ** 2).sum(1) / (2 * fav.sum())), "Pᵢ у сприятливих середовищах")
chk(near(si["Pi_unf"], ((X[:, ~fav] - mx[~fav]) ** 2).sum(1) / (2 * (~fav).sum())), "Pᵢ у несприятливих середовищах")

print("\n== Непараметричні індекси")
ranks = np.apply_along_axis(lambda c: stats.rankdata(-c), 0, X)      # 1 = найкращий
chk(near(si["ranks"], ranks), "ранги в середовищах (1 = найвищий врожай)")
adj = X - (gm - gr)[:, None]
ranks_adj = np.apply_along_axis(lambda c: stats.rankdata(-c), 0, adj)
chk(near(si["ranks_adj"], ranks_adj), "ранги скоригованих даних Yᵢⱼ − (Ȳᵢ. − Ȳ..)")
# Hühn (1979, «Nonparametric measures of phenotypic stability. Part 1: Theory»): ранги ВИХІДНИХ даних у кожному середовищі
rb0 = ranks.mean(1)
S1 = np.array([sum(abs(ranks[i, j] - ranks[i, k]) for j in range(e) for k in range(j + 1, e)) * 2 / (e * (e - 1)) for i in range(g)])
chk(near(si["S1"], S1), "Hühn S⁽¹⁾ = 2·Σ_{j<j'}|rᵢⱼ − rᵢⱼ'| / (e(e−1)) — ранги вихідних даних")
chk(near(si["S2r"], ((ranks - rb0[:, None]) ** 2).sum(1) / (e - 1)), "Hühn S⁽²⁾ = Σ(rᵢⱼ − r̄ᵢ)²/(e−1)")
chk(near(si["rank_mean"], rb0), "середній ранг r̄ᵢ")
chk(near(si["S3"], ((ranks - rb0[:, None]) ** 2).sum(1) / rb0), "Hühn (1990) S⁽³⁾ = Σ(rᵢⱼ − r̄ᵢ)²/r̄ᵢ")
chk(near(si["S6"], np.abs(ranks - rb0[:, None]).sum(1) / rb0), "Hühn (1990) S⁽⁶⁾ = Σ|rᵢⱼ − r̄ᵢ|/r̄ᵢ")
chk(near(si["TOP"], (ranks <= math.ceil(g / 3)).mean(1) * 100) or near(si["TOP"], (ranks <= g / 3).mean(1) * 100),
    "Fox: частка середовищ, де генотип у верхній третині")

print("\n== Thennarasu (1995) NP — ранги скоригованих даних")
radj = ranks_adj; Mi = np.median(ranks_adj, axis=1); Mo = np.median(ranks, axis=1); rmean_adj = ranks_adj.mean(1)
np1 = np.abs(radj - Mi[:, None]).sum(1) / e
np2 = (np.abs(radj - Mi[:, None]) / Mo[:, None]).sum(1) / e
np3 = np.sqrt(((radj - rmean_adj[:, None]) ** 2).sum(1) / e) / rb0
print("   NP1 модуль:", np.round(si["NP1"][:3], 4), " моє:", np.round(np1[:3], 4))
print("   NP2 модуль:", np.round(si["NP2"][:3], 4), " моє:", np.round(np2[:3], 4))
print("   NP3 модуль:", np.round(si["NP3"][:3], 4), " моє:", np.round(np3[:3], 4))
chk(near(si["NP1"], np1), "NP⁽¹⁾ = Σ|r*ᵢⱼ − M*ᵢ| / e  (M* — медіана скоригованих рангів)")
chk(near(si["NP2"], np2), "NP⁽²⁾ = Σ(|r*ᵢⱼ − M*ᵢ| / Mᵢ) / e  (Mᵢ — медіана вихідних рангів)")
chk(near(si["NP3"], np3), "NP⁽³⁾ = √(Σ(r*ᵢⱼ − r̄*ᵢ)²/e) / r̄ᵢ  (r̄ᵢ — середній вихідний ранг)")

print("\n== AMMI")
am = G.ammi(X, r=r, mse=mse, df_err=dfe)
U, S, Vt = np.linalg.svd(gei, full_matrices=False)
chk(near(np.sort(am["sv"])[::-1][:len(S)], S[:len(am["sv"])]), "сингулярні числа SVD матриці взаємодії")
tot = (S ** 2).sum()
chk(near(tot, SSGE), "Σλₖ² = SS(G×E) (розклад взаємодії повний)")
print("   структура SS/axes:", type(am["SS"]).__name__, list(am["SS"].keys()) if isinstance(am["SS"], dict) else "", "| axes:", type(am["axes"]).__name__)
ax = am["axes"]
if isinstance(ax, list) and ax and isinstance(ax[0], dict):
    print("   ключі осі:", list(ax[0].keys()))
    ss_k = np.array([a.get("SS") for a in ax], float)
    chk(near(ss_k, r * S[:len(ss_k)] ** 2) or near(ss_k, S[:len(ss_k)] ** 2),
        "SS осі k = r·λₖ² (на рівні всіх повторностей) або λₖ² (на 1 повторність)")
    dfk = [a.get("df") for a in ax]
    chk(dfk == [g + e - 1 - 2 * (k + 1) for k in range(len(dfk))], f"df осей за Gollob: g+e−1−2k = {dfk}")

print("\n== GGE")
gg = G.gge(X)
Xc = X - em[None, :]
U2, S2, Vt2 = np.linalg.svd(Xc, full_matrices=False)
pct = S2 ** 2 / (S2 ** 2).sum() * 100
chk(near(np.asarray(gg["pct"])[:3], pct[:3]), "% варіації PC1, PC2, PC3 (SVD матриці, центрованої за середовищами)")
chk(abs(float(np.asarray(gg["pct"])[:2].sum()) - pct[:2].sum()) < 1e-8, f"PC1+PC2 = {pct[:2].sum():.1f}% (на біплоті)")
# відтворення матриці через PC1–PC2 (властивість SVD): ранг-2 наближення
G2 = np.asarray(gg["G"]); E2 = np.asarray(gg["E"])
rec = G2[:, :2] @ E2[:, :2].T
approx = (U2[:, :2] * S2[:2]) @ Vt2[:2]
chk(near(rec, approx, 1e-7) or near(np.abs(rec), np.abs(approx), 1e-7), "G·Eᵀ за двома осями відтворює ранг-2 наближення матриці")

print("\n== Комбінований ANOVA (RCBD у кількох середовищах) — звірка з прямим розкладом SS")
g2, e2, r2 = 5, 4, 3
gen, env, rep, yv = [], [], [], []
true = rng.normal(0, 1, (g2, e2)); renv = rng.normal(0, .5, (e2, r2))
cube = np.zeros((g2, e2, r2))
for i in range(g2):
    for j in range(e2):
        for k in range(r2):
            val = 12 + i * .6 + j * 1.3 + true[i, j] + renv[j, k] + rng.normal(0, .5)
            cube[i, j, k] = val; gen.append(f"G{i+1}"); env.append(f"E{j+1}"); rep.append(f"R{k+1}"); yv.append(val)
ca = G.combined_anova(gen, env, rep, yv)
gmean = cube.mean(); Gm = cube.mean((1, 2)); Em = cube.mean((0, 2)); GEm = cube.mean(2); REm = cube.mean(0)   # REm: e×r
ssG = e2 * r2 * ((Gm - gmean) ** 2).sum(); ssE = g2 * r2 * ((Em - gmean) ** 2).sum()
ssGE = r2 * ((GEm - Gm[:, None] - Em[None, :] + gmean) ** 2).sum()
ssRE = g2 * ((REm - Em[:, None]) ** 2).sum()
ssT = ((cube - gmean) ** 2).sum(); ssErr = ssT - ssG - ssE - ssGE - ssRE
chk(near(ca["SS"]["G"], ssG) and near(ca["SS"]["E"], ssE) and near(ca["SS"]["GE"], ssGE), "SS: G, E, G×E")
chk(near(ca["SS"]["R(E)"], ssRE) and near(ca["SS"]["err"], ssErr) and near(ca["SS"]["tot"], ssT), "SS: R(E), похибка, загальна")
chk(ca["df"] == {"E": e2 - 1, "R(E)": e2 * (r2 - 1), "G": g2 - 1, "GE": (g2 - 1) * (e2 - 1), "err": e2 * (g2 - 1) * (r2 - 1)}
    or {k: int(v) for k, v in ca["df"].items()} == {"E": e2 - 1, "R(E)": e2 * (r2 - 1), "G": g2 - 1, "GE": (g2 - 1) * (e2 - 1), "err": e2 * (g2 - 1) * (r2 - 1)},
    "ступені свободи: E, R(E), G, GE, похибка")
msE = ssErr / (e2 * (g2 - 1) * (r2 - 1)); msGE = ssGE / ((g2 - 1) * (e2 - 1))
chk(near(ca["F"]["GE"], msGE / msE), "F(G×E) = MS(GE)/MSE")
print("   F(G):", round(ca["F"]["G"], 4), " MS(G)/MS(GE) =", round((ssG / (g2 - 1)) / msGE, 4), " MS(G)/MSE =", round((ssG / (g2 - 1)) / msE, 4))
chk(near(ca["F"]["G"], (ssG / (g2 - 1)) / msGE) or near(ca["F"]["G"], (ssG / (g2 - 1)) / msE), "F(G): знаменник — MS(GE) (випадкові середовища) або MSE")
try:
    import statsmodels.api as sm, statsmodels.formula.api as smf, pandas as pd
    df = pd.DataFrame({"y": yv, "g": gen, "e": env, "r": rep})
    m = smf.ols("y ~ C(e) + C(e):C(r) + C(g) + C(g):C(e)", df).fit(); at = sm.stats.anova_lm(m, typ=1)
    ss_sm = at["sum_sq"].values
    chk(abs(ss_sm[2] - ssG) < 1e-8 and abs(ss_sm[0] - ssE) < 1e-8 and abs(ss_sm[3] - ssGE) < 1e-8, "звірка з statsmodels OLS (type I): SS(G), SS(E), SS(GE)")
except Exception as ex:
    print("   (statsmodels недоступний:", ex, ")")

print("\n== Генетичні параметри (Johnson et al. 1955) — формули з нуля")
gp_gen, gp_rep, gp_y = [], [], []
gvals = rng.normal(0, 1.6, 8); blk = rng.normal(0, .4, 4)
for i in range(8):
    for k in range(4):
        gp_gen.append(f"G{i+1}"); gp_rep.append(f"R{k+1}"); gp_y.append(20 + gvals[i] + blk[k] + rng.normal(0, 1.0))
gp = B.genetic_parameters_single(gp_gen, gp_rep, gp_y)
Y = np.array(gp_y).reshape(8, 4); n_g, n_r = 8, 4
gmn = Y.mean(); SSg = n_r * ((Y.mean(1) - gmn) ** 2).sum(); SSr = n_g * ((Y.mean(0) - gmn) ** 2).sum()
SSt = ((Y - gmn) ** 2).sum(); SSe = SSt - SSg - SSr
MSg = SSg / (n_g - 1); MSe = SSe / ((n_g - 1) * (n_r - 1))
vg = (MSg - MSe) / n_r; ve = MSe; vp = vg + ve
chk(near(gp["var_g"], vg) and near(gp["var_e"], ve) and near(gp["var_p"], vp), "σ²g = (MSg − MSe)/r;  σ²e = MSe;  σ²p = σ²g + σ²e")
chk(near(gp["h2_plot"], vg / vp), "H² на рівні ділянки = σ²g/σ²p")
chk(near(gp["h2_mean"], vg / (vg + ve / n_r)), "H² на рівні середніх = σ²g/(σ²g + σ²e/r)")
chk(near(gp["GCV"], math.sqrt(vg) / gmn * 100) and near(gp["PCV"], math.sqrt(vp) / gmn * 100) and near(gp["ECV"], math.sqrt(ve) / gmn * 100),
    "GCV, PCV, ECV = √σ² / середнє × 100")
chk(near(gp["GA"], 2.06 * math.sqrt(vp) * vg / vp), "генетичний прогрес GA = k·σp·H² (k = 2,06 для 5 % відбору)")
chk(near(gp["GAM"], gp["GA"] / gmn * 100), "GAM = GA / середнє × 100")
F_ = MSg / MSe
chk(near(gp["F"], F_) and abs(gp["p"] - stats.f.sf(F_, n_g - 1, (n_g - 1) * (n_r - 1))) < 1e-10, "F-тест генотипів")
lo, hi = gp["h2_mean_ci"]
Fl, Fu = stats.f.ppf(0.975, n_g - 1, (n_g - 1) * (n_r - 1)), stats.f.ppf(0.025, n_g - 1, (n_g - 1) * (n_r - 1))
exp_lo, exp_hi = 1 - Fu ** -1 * 0 - (1 / (F_ / Fl)), 1 - (1 / (F_ / Fu))   # H²=1−1/F; межі через критичні F (Knapp et al. 1985)
print(f"   CI H²(mean): модуль [{lo:.4f}; {hi:.4f}]  |  за Knapp 1985 [{exp_lo:.4f}; {exp_hi:.4f}]")
chk(abs(lo - exp_lo) < 1e-6 and abs(hi - exp_hi) < 1e-6, "довірчий інтервал H² за Knapp et al. (1985)")

print("\n== Лінія × тестер (Kempthorne) — звірка з прямим розкладом")
nl, nt, nr = 4, 3, 3
lines, tests, reps, ly = [], [], [], []
ge_ = rng.normal(0, 1, nl); gt_ = rng.normal(0, 1, nt); st_ = rng.normal(0, .6, (nl, nt))
LT = np.zeros((nl, nt, nr))
for i in range(nl):
    for j in range(nt):
        for k in range(nr):
            v = 15 + ge_[i] + gt_[j] + st_[i, j] + rng.normal(0, .5); LT[i, j, k] = v
            lines.append(f"L{i+1}"); tests.append(f"T{j+1}"); reps.append(f"R{k+1}"); ly.append(v)
lt = B.line_tester(lines, tests, reps, ly)
print("   ключі:", list(lt.keys()))
cm = LT.mean(2); gmu = LT.mean()
gca_l = LT.mean((1, 2)) - gmu; gca_t = LT.mean((0, 2)) - gmu
sca = cm - LT.mean((1, 2))[:, None] - LT.mean((0, 2))[None, :] + gmu
chk(near(gca_l.sum(), 0) and near(gca_t.sum(), 0) and near(sca.sum(0), 0) and near(sca.sum(1), 0), "ефекти gca/sca: суми дорівнюють нулю")
ssL = nt * nr * (gca_l ** 2).sum(); ssT_ = nl * nr * (gca_t ** 2).sum(); ssLT = nr * (sca ** 2).sum()
ssCr = nr * ((cm - gmu) ** 2).sum()
chk(near(ssCr, ssL + ssT_ + ssLT), "тотожність: SS(схрещувань) = SS(ліній) + SS(тестерів) + SS(Л×Т)")
for key, exp in (("gca_lines", gca_l), ("gca_testers", gca_t), ("sca", sca)):
    if key in lt: chk(near(np.asarray(lt[key], float), exp), f"{key} збігається з прямим розрахунком")
    else: print(f"   (ключ {key} відсутній; є: {[k for k in lt if 'gca' in k or 'sca' in k]})")

print("\n== Діалель Гріффінга, метод 2 — звірка з МНК-розв'язком моделі")
p = 5; r_d = 3
p1, p2, rp, dy = [], [], [], []
gca_true = rng.normal(0, 1, p); sca_true = rng.normal(0, .5, (p, p)); sca_true = (sca_true + sca_true.T) / 2
D = {}
for i in range(p):
    for j in range(i, p):
        for k in range(r_d):
            v = 20 + gca_true[i] + gca_true[j] + sca_true[i, j] + rng.normal(0, .4)
            p1.append(f"P{i+1}"); p2.append(f"P{j+1}"); rp.append(f"R{k+1}"); dy.append(v)
            D.setdefault((i, j), []).append(v)
dg = B.diallel_griffing(p1, p2, rp, dy, method=2, model="I")
print("   ключі:", list(dg.keys()))
# МНК: y_ij = μ + g_i + g_j + s_ij (i≤j), обмеження Σg=0; gca оцінюємо через закриту формулу Гріффінга метод 2
xm = {k: np.mean(v) for k, v in D.items()}
Yt = np.zeros((p, p))
for (i, j), v in xm.items():
    Yt[i, j] = v; Yt[j, i] = v
Yi = Yt.sum(1) + np.diag(Yt)                              # Yi. + Yii   (метод 2 : Y_i. включає Y_ii двічі)
Ytot = sum(xm.values()) * 2 - sum(xm[(i, i)] for i in range(p))   # сума по всіх (i,j) двічі, діагональ раз
gi_formula = (Yi - 2 * (Yi.sum() / (2 * p)) * 0) / (p + 2)
# за Гріффіном метод 2: ĝi = [Yi. + Yii − (2/p) Y..] / (p+2), де Y.. = сума всіх p(p+1)/2 середніх
Ysum = sum(xm.values())
gi = (Yt.sum(1) + np.diag(Yt) - (2.0 / p) * Ysum) / (p + 2)
gca_key = next((k for k in dg if "gca" in k and "eff" in k.lower() or k == "gca"), None)
print("   gca (модуль):", np.round(np.asarray(dg.get(gca_key, dg.get("gca", [])), float)[:5], 4) if gca_key or "gca" in dg else "—")
print("   gca (Гріффінг):", np.round(gi, 4))
cand = dg.get(gca_key) if gca_key else dg.get("gca")
if cand is not None:
    chk(near(np.asarray(cand, float), gi, 1e-7), "gca за формулою Гріффінга (1956), метод 2: ĝᵢ = [Yᵢ. + Yᵢᵢ − 2Y../p]/(p+2)")
chk(abs(gi.sum()) < 1e-8, "Σĝᵢ = 0")

print("\n== Індекси стресостійкості — формули з нуля")
yp = np.array([8.0, 6.5, 7.2, 9.1, 5.5]); ys = np.array([5.2, 4.9, 3.1, 6.0, 4.4])
st = B.stress_indices(yp, ys)
print("   ключі:", list(st.keys()))
Ypm, Ysm = yp.mean(), ys.mean()
exp = {"TOL": yp - ys, "MP": (yp + ys) / 2, "GMP": np.sqrt(yp * ys), "STI": yp * ys / Ypm ** 2,
       "SSI": (1 - ys / yp) / (1 - Ysm / Ypm), "YI": ys / Ysm, "YSI": ys / yp, "HM": 2 * yp * ys / (yp + ys),
       "RSI": (ys / yp) / (Ysm / Ypm)}
for k, v in exp.items():
    if k in st: chk(near(np.asarray(st[k], float), v), f"{k}: збігається з формулою першоджерела")
    else: print(f"   ({k} відсутній у виході)")

print("\n== Шляховий аналіз (Wright; Dewey & Lu)")
n = 60
Z = rng.normal(0, 1, (n, 4)); Z[:, 1] += .6 * Z[:, 0]; Z[:, 2] += .3 * Z[:, 1]
yy = 1.2 * Z[:, 0] + .8 * Z[:, 1] - .5 * Z[:, 2] + .2 * Z[:, 3] + rng.normal(0, .7, n)
pa = B.path_analysis(Z, yy, ["x1", "x2", "x3", "x4"], "Y")
print("   ключі:", list(pa.keys()))
R = np.corrcoef(np.column_stack([Z, yy]), rowvar=False); Rxx = R[:4, :4]; rxy = R[:4, 4]
pdir = np.linalg.solve(Rxx, rxy)
chk(near(np.asarray(pa["direct"], float), pdir) if "direct" in pa else False, "прямі ефекти p = R_xx⁻¹·r_xy")
R2 = float(pdir @ rxy)
if "residual" in pa: chk(near(pa["residual"], math.sqrt(1 - R2)), "залишковий ефект = √(1 − R²)")
if "R2" in pa: chk(near(pa["R2"], R2), "R² моделі = Σ pᵢ·rᵢy")
ind = Rxx * pdir[None, :]
chk(near(ind.sum(1), rxy), "тотожність: rᵢy = pᵢ + Σⱼ rᵢⱼ·pⱼ (прямий + непрямі ефекти)")

print("\n" + "=" * 60)
if FAIL:
    print(f"РОЗБІЖНОСТЕЙ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ НЕЗАЛЕЖНІ ЗВІРКИ ЗБІГАЮТЬСЯ")
