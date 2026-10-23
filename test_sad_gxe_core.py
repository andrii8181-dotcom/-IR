# test_sad_gxe_core.py — перевірка ядра G×E (стабільність, AMMI, GGE, комбінований ANOVA)
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_gxe_core as G

FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
def close(a, b, tol=1e-9): return bool(np.all(np.abs(np.asarray(a) - np.asarray(b)) <= tol))

rng = np.random.default_rng(7)
g, e = 7, 6
X = 5 + rng.normal(0, 1, (g, 1)) + rng.normal(0, 1.5, (1, e)) + rng.normal(0, 0.6, (g, e))

print("== 1. Підготовка даних")
Xn = X.copy(); Xn[2, 3] = np.nan; Xn[4, 0] = np.nan
try: G.as_matrix(Xn, [f"Сорт{i}" for i in range(g)], [f"Рік{j}" for j in range(e)]); check(False, "NaN мало дати помилку")
except G.BreedingError as ex:
    t = str(ex); check("Сорт2 × Рік3" in t and "Сорт4 × Рік0" in t and "не підставляє" in t, "пропуски: помилка зі списком клітинок і без мовчазної імпутації")
for bad in (np.ones((1, 4)), np.ones((4, 1)), np.ones(5)):
    try: G.as_matrix(bad); check(False, "мало впасти")
    except G.BreedingError: pass
check(True, "замало генотипів/середовищ → зрозуміла помилка")

print("\n== 2. Розклад сум квадратів і тотожності Wricke/Shukla")
ef = G.ge_effects(X)
tot = float(np.sum((X - X.mean()) ** 2))
check(close(ef["SSG"] + ef["SSE"] + ef["SSGE"], tot, 1e-9), "SS_G + SS_E + SS_GE = загальна SS")
si = G.stability_indices(X)
check(close(si["W2"].sum(), ef["SSGE"]), "ΣW²ᵢ = SS_GE (екоцінність розподіляє SS взаємодії)")
msge = ef["SSGE"] / ((g - 1) * (e - 1))
check(close(si["Shukla"].mean(), msge, 1e-9), "середнє σ²ᵢ Шукли = MS_GE (точна властивість формули)")
names, C = G.rank_correlation(si["rank_by"])
i1, i2 = names.index("W² Вріке (↓)"), names.index("σ² Шукли (↓)")
check(abs(C[i1, i2] - 1.0) < 1e-12, "Wricke і Shukla — однакове ранжування (ρ = 1), як у літературі")
# власна «наївна» реалізація Вріке
Wn = [sum((X[i, j] - X[i].mean() - X[:, j].mean() + X.mean()) ** 2 for j in range(e)) for i in range(g)]
check(close(si["W2"], Wn), "W² збігається з наївним обчисленням за визначенням")

print("\n== 3. Регресійні показники (Фінлей–Вілкінсон / Ебергарт–Рассел)")
check(abs(si["b"].mean() - 1.0) < 1e-12, "середнє bᵢ = 1")
I = ef["emeans"] - ef["gm"]
lin = (I @ I) * np.sum((si["b"] - 1) ** 2)
check(close(lin + si["SSdev"].sum(), ef["SSGE"], 1e-9), "SS_GE = (лінійна частина) + Σ відхилень від регресії — точна тотожність")
ok = True
for i in range(g):
    lr = stats.linregress(I, X[i])
    ok &= abs(lr.slope - si["b"][i]) < 1e-10 and abs(lr.stderr - si["b_se"][i]) < 1e-10
    t = (lr.slope - 1) / lr.stderr; ok &= abs(2 * stats.t.sf(abs(t), e - 2) - si["b_p"][i]) < 1e-10
    ok &= abs(si["S2delta"][i] - np.sum((X[i] - (lr.intercept + lr.slope * I)) ** 2) / (e - 2)) < 1e-10
check(ok, "bᵢ, SE(bᵢ), p(bᵢ=1), S²δ збігаються з незалежним scipy.stats.linregress")
mse, r, dfe = 0.30, 3, 40
s2 = G.stability_indices(X, mse=mse, r=r, df_err=dfe)
check(close(s2["S2d"], si["S2delta"] - mse / r), "S²d Ебергарта–Рассела = S²δ − MSE/r")
Fv = si["S2delta"] / (mse / r)
check(close(s2["S2d_p"], stats.f.sf(Fv, e - 2, dfe)), "p-значення тесту S²d = 0 за F(e−2; df похибки)")
check(np.all(np.isnan(si["S2d"])) and np.all(np.isnan(si["S2d_p"])), "без похибки за повторностями тест S²d не виконується (NaN), а не вигадується")
X2 = X[:, :2]; s_e2 = G.stability_indices(X2)
check(np.all(np.isnan(s_e2["S2delta"])) and not np.any(np.isnan(s_e2["b"])), "2 середовища: b є, S²δ і тести — NaN (немає ступенів свободи)")

print("\n== 4. Lin–Binns, CV, S²")
M = X.max(axis=0)
Pn = [sum((X[i, j] - M[j]) ** 2 for j in range(e)) / (2 * e) for i in range(g)]
check(close(si["Pi"], Pn), "Pᵢ за визначенням Ліна–Біннса")
nf, nu = si["n_fav"], si["n_unf"]
check(close((nf * si["Pi_fav"] + nu * si["Pi_unf"]) / e, si["Pi"]), "Pᵢ = (n_спр·P_спр + n_несп·P_несп)/e")
Xb = X.copy(); Xb[0] = Xb.max(axis=0) + 1.0
sb = G.stability_indices(Xb)
check(sb["Pi"].argmin() == 0, "генотип, що перевищує найкращих у всіх середовищах, має мінімальний P")
Xc = X.copy(); Xc[1] = Xc.max(axis=0); sc = G.stability_indices(Xc)
check(abs(sc["Pi"][1]) < 1e-12, "найкращий у всіх середовищах → P = 0 точно")
check(close(si["CV"], 100 * X.std(axis=1, ddof=1) / X.mean(axis=1)) and close(si["S2"], X.var(axis=1, ddof=1)), "CV і S² за визначенням")

print("\n== 5. Непараметричні показники — розрахунок «вручну»")
H = np.array([[10, 10, 10], [8, 9, 7], [6, 5, 8.]])
sh = G.stability_indices(H)
check(close(sh["ranks"], [[1, 1, 1], [2, 2, 3], [3, 3, 2]]), "ранги: 1 = найвищий урожай")
check(close([sh["S1"][0], sh["S2r"][0], sh["S3"][0], sh["S6"][0]], 0), "стабільний генотип (ранги 1,1,1): S(1)=S(2)=S(3)=S(6)=0")
check(close(sh["S1"][1], 2 / 3, 1e-12) and close(sh["S2r"][1], 1 / 3, 1e-12), "генотип 2 (ранги 2,2,3): S(1)=0,6667; S(2)=0,3333")
check(close(sh["S3"][1], 0.6666666667 / (7 / 3), 1e-9) and close(sh["S6"][1], (4 / 3) / (7 / 3), 1e-9), "S(3)=0,2857; S(6)=0,5714 за ручним розрахунком")
# brute-force для випадкових даних
R = si["ranks"]; ok = True
for i in range(g):
    d = [abs(R[i, a] - R[i, b]) for a in range(e) for b in range(a + 1, e)]
    ok &= abs(si["S1"][i] - 2 * sum(d) / (e * (e - 1))) < 1e-12
    rb = R[i].mean(); ok &= abs(si["S3"][i] - sum((R[i] - rb) ** 2) / rb) < 1e-12
check(ok, "S(1), S(3) збігаються з наївним перебором пар")
Xa = X - (X.mean(axis=1) - X.mean())[:, None]
Ra = np.column_stack([stats.rankdata(-Xa[:, j]) for j in range(e)])
ok = True
for i in range(g):
    Mda = np.median(Ra[i]); Md = np.median(R[i]); rb_a = Ra[i].mean(); rb = R[i].mean()
    ok &= abs(si["NP1"][i] - sum(abs(Ra[i] - Mda)) / e) < 1e-12
    ok &= abs(si["NP2"][i] - sum(abs(Ra[i] - Mda)) / (e * Md)) < 1e-12
    ok &= abs(si["NP3"][i] - math.sqrt(sum((Ra[i] - rb_a) ** 2) / e) / rb) < 1e-12
    pairs = [abs(Ra[i, a] - Ra[i, b]) for a in range(e) for b in range(a + 1, e)]
    ok &= abs(si["NP4"][i] - 2 * sum(pairs) / (e * (e - 1)) / rb) < 1e-12
check(ok, "NP(1)–NP(4) Теннарасу: скориговані ранги, медіани/середні оригінальних даних — за формулами огляду")
T6 = np.array([[9, 9, 9, 9], [8, 8, 8, 1], [7, 7, 1, 8], [6, 1, 7, 7], [1, 6, 6, 6], [2, 2, 2, 2.]])
st = G.stability_indices(T6)
check(close(st["TOP"][0], 100.0), "TOP-Fox: генотип, що завжди в першій третині = 100 %")
check(close(st["TOP"][1], 75.0) and close(st["TOP"][5], 0.0), "TOP-Fox: 3 із 4 середовищ = 75 %; ніколи = 0 %")
K = G.stability_indices(H)
check(close(K["Kang_RS"], rank_sum := (G.rank_desc(H.mean(axis=1)) + G.rank_asc(K["Shukla"]))), "ранг-сума Канга = ранг урожаю + ранг варіанси Шукли")
check(K["Kang_rank"].argmin() == 0, "найкращий за рангсумою Канга — стабільний і урожайний генотип")

print("\n== 6. AMMI")
am = G.ammi(X, r=3)
check(close(sum(a["SS"] for a in am["axes"]), 3 * ef["SSGE"], 1e-9), "Σ SS осей IPCA = SS_GE (повний розклад)")
check(sum(a["df"] for a in am["axes"]) == (g - 1) * (e - 1), "Σ ст. свободи осей за Gollob = (g−1)(e−1)")
rec = am["gen_scores"] @ am["env_scores"].T
check(close(rec, ef["gei"], 1e-9), "оцінки осей (симетричне масштабування) точно відновлюють взаємодію")
check(abs(am["axes"][-1]["cum"] - 100.0) < 1e-9, "кумулятивний внесок осей = 100 %")
w = am["axes"][0]["SS"] / am["axes"][1]["SS"]
asv_n = np.sqrt((w * am["gen_scores"][:, 0]) ** 2 + am["gen_scores"][:, 1] ** 2)
check(close(am["ASV"], asv_n), "ASV за формулою Purchase: √[(SS₁/SS₂·IPCA1)² + IPCA2²]")
check(close(np.sort(am["ASV"]), np.sort(G.ammi(X[::-1], r=3)["ASV"])), "ASV не залежить від порядку генотипів (і від довільного знака осей)")
amf = G.ammi(X, r=3, mse=0.4, df_err=36)
a1 = amf["axes"][0]
check(close(a1["F"], a1["SS"] / a1["df"] / 0.4) and close(a1["p"], stats.f.sf(a1["F"], a1["df"], 36)), "F і p осі: MS/MSE, F(df осі; df похибки)")
check(np.isnan(am["axes"][0]["F"]), "без похибки F-тести осей не виконуються")
rt = G.ammi_rank_table(am)
check(close(rt["YSI"], rt["rank_ASV"] + rt["rank_mean"]), "YSI = ранг ASV + ранг середнього")
# Точно двовимірна взаємодія: 2 осі пояснюють 100 %
Z = np.outer(rng.normal(size=g), rng.normal(size=e)) + np.outer(rng.normal(size=g), rng.normal(size=e))
Xr2 = 10 + rng.normal(size=(g, 1)) + rng.normal(size=(1, e)) + Z
a2 = G.ammi(Xr2)
check(a2["axes"][0]["cum"] < 99 and a2["axes"][1]["cum"] > 100 - 1e-8, "взаємодія рангу 2: перші 2 осі = 100 %, 1 вісь — менше")

print("\n== 7. GGE-біплот, переможці, AEC")
Z2 = np.outer(rng.normal(size=g), rng.normal(size=e)) + np.outer(rng.normal(size=g), rng.normal(size=e))
Xg = 8 + 2 * rng.normal(size=(g, 1)) + Z2 + rng.normal(size=(1, e))      # (G + GE) рангу 2 після центрування за середовищами
for svp in ("genotype", "environment", "symmetric"):
    gg = G.gge(Xg, svp)
    check(close(gg["G"] @ gg["E"].T, gg["Xc"], 1e-9), f"GGE ({svp}): G·Eᵀ точно відновлює центровану за середовищами матрицю")
gg = G.gge(Xg, "genotype")
check(abs(gg["pct"].sum() - 100) < 1e-9, "внески PC дають 100 %")
Xg2 = Xg - Xg.mean(axis=0)
U_, S_, Vt_ = np.linalg.svd(Xg2, full_matrices=False)
low = (U_[:, :2] * S_[:2]) @ Vt_[:2] + Xg.mean(axis=0)                     # точно ранг 2
gl = G.gge(low, "genotype")
check(gl["pct"][:2].sum() > 100 - 1e-8, "модельні дані: 2 PC пояснюють 100 %")
ww = G.which_won_where(gl)
actual = {j: int(np.argmax(low[:, j])) for j in range(e)}
check(ww["winners"] == actual, "«who-won-where»: переможці за проекцією = справжні найврожайніші в кожному середовищі")
check(set(ww["winners"].values()) <= set(ww["hull"]), "переможці лежать на вершинах багатокутника")
ae = G.aec_mean_stability(gl)
order_proj = np.argsort(-ae["mean_score"]); order_mean = np.argsort(-low.mean(axis=1))
check(list(order_proj) == list(order_mean), "проекція на вісь AEC впорядковує генотипи за середнім урожаєм (точна властивість для рангу 2)")
ds = G.discriminativeness(gl)
check(ds["length"].shape == (e,) and np.all(np.abs(ds["representativeness"]) <= 1 + 1e-12), "дискримінаційність і репрезентативність визначені")
check(G.which_won_where(G.gge(low[:2], "genotype"))["hull"] == [], "менше 3 генотипів — багатокутник не будується, без помилки")

print("\n== 8. Комбінований ANOVA за повторностями")
gen, env, rep, y = [], [], [], []
gt, et = rng.normal(0, 1.0, 5), rng.normal(0, 2.0, 4)
inter = rng.normal(0, 0.7, (5, 4)); rb = rng.normal(0, 0.4, (4, 3))
for i in range(5):
    for j in range(4):
        for k in range(3):
            gen.append(f"G{i}"); env.append(f"E{j}"); rep.append(f"R{k}")
            y.append(20 + gt[i] + et[j] + inter[i, j] + rb[j, k] + rng.normal(0, 0.5))
ca = G.combined_anova(gen, env, rep, y)
check(close(sum(ca["SS"][k] for k in ("E", "R(E)", "G", "GE", "err")), ca["SS"]["tot"], 1e-8), "SS розкладається точно: E + R(E) + G + GE + похибка = загальна")
check(ca["df"] == {"E": 3, "R(E)": 8, "G": 4, "GE": 12, "err": 32}, f"ступені свободи: {ca['df']}")
check(abs(ca["mse"] - ca["bartlett"]["mse_env"].mean()) < 1e-10, "MSE комбінованого аналізу = середнє MSE окремих середовищ (збалансований випадок)")
Xm = ca["means"]; efm = G.ge_effects(Xm)
check(close(ca["SS"]["GE"], 3 * efm["SSGE"], 1e-9), "SS_GE за повторностями = r · SS_GE за середніми")
check(abs(ca["F"]["G"] - ca["MS"]["G"] / ca["MS"]["GE"]) < 1e-12 and abs(ca["F"]["GE"] - ca["MS"]["GE"] / ca["MS"]["err"]) < 1e-12,
      "G перевіряється проти G×E, G×E — проти похибки (середовища випадкові)")
check(0 <= ca["bartlett"]["p"] <= 1 and ca["bartlett"]["df"] == 3, "тест Бартлетта однорідності похибок")
try: G.combined_anova(gen[:-1], env[:-1], rep[:-1], y[:-1]); check(False, "незбалансовані дані мали дати помилку")
except G.BreedingError as ex: check("збалансованим" in str(ex), "незбалансований дослід → зрозуміла помилка")
keep = [k != "R2" for k in rep]
r2 = G.combined_anova([a for a, m in zip(gen, keep) if m], [a for a, m in zip(env, keep) if m],
                      [a for a, m in zip(rep, keep) if m], [a for a, m in zip(y, keep) if m])
check(r2["r"] == 2 and r2["df"]["err"] == 4 * 4 * 1, "2 повторності — допустимо (df похибки = E·(G−1)(r−1) = 16)")
try: G.combined_anova(gen, env, [1] * len(gen), y); check(False, "мало впасти")
except G.BreedingError: check(True, "одна повторність → помилка (немає похибки)")
# конвеєр: похибка з ANOVA → тести ER й AMMI
sp = G.stability_indices(ca["means"], mse=ca["mse"], r=ca["r"], df_err=ca["df_err"])
am_ = G.ammi(ca["means"], r=ca["r"], mse=ca["mse"], df_err=ca["df_err"])
check(not np.any(np.isnan(sp["S2d_p"])) and not np.isnan(am_["axes"][0]["p"]), "похибка з комбінованого ANOVA вмикає тести S²d й осей AMMI")

print("\n== 9. Попередження")
w1 = G.design_warnings(7, 3); w2 = G.design_warnings(2, 8, mse=0.3)
check(any("середовищ" in t and "орієнтовні" in t for t in w1) and any("Шукли" in t for t in w2) and not any("повторностями" in t for t in w2),
      "попередження про малу кількість середовищ/генотипів і про відсутню похибку")

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}")
    for f in FAIL: print("  -", f)
    sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЯДРА G×E ПРОЙДЕНО")
