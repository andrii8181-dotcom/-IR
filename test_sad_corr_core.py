# test_sad_corr_core.py — кореляційна матриця: вирівнювання рядків, Кендалл, інтервали, поправки
import os, sys, math, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_corr_core as CC
from sad_ordinal_core import p_adjust
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(5)

print("== 1. Вирівнювання за рядками (виправлена помилка зсуву пар)")
X = [str(v) for v in range(1, 9)]; Y = ["1", "2", "", "4", "5", "6", "7", "8"]
arr, bad = CC.arrays_from_cells([X, Y])
check(np.isnan(arr[1][2]) and not np.isnan(arr[0][2]) and bad == [], "порожня клітинка → NaN на своєму місці, довжини однакові")
res = CC.correlate_pair(arr[0], arr[1], "pearson")
check(abs(res["r"] - 1.0) < 1e-12 and res["n"] == 7, f"ідеальна залежність за наявного пропуску: r = {res['r']:.6f}, n = {res['n']} (старий код давав 0,9932)")
a_old = [v for v in range(1, 9)]; b_old = [1, 2, 4, 5, 6, 7, 8]
check(abs(stats.pearsonr(a_old[:7], b_old)[0] - 1.0) > 0.004, "контроль: зсунуті пари справді спотворювали б результат")
arr2, bad2 = CC.arrays_from_cells([["1", "2", "x", "4"], ["1", "2", "3", "4"]])
check(bad2 == [(2, 0, "x")] and np.isnan(arr2[0][2]), "нечислова клітинка не зсуває рядки, а повідомляється окремо: " + str(bad2))
arr3, _ = CC.arrays_from_cells([["1,5", " 2 ", "3.5"], ["2", "4", "6"]])
check(np.allclose(arr3[0], [1.5, 2.0, 3.5]), "десяткова кома, пробіли, крапка розпізнаються")

print("\n== 2. Збіг із scipy та ручні приклади")
x = rng.normal(size=40); y = 0.6 * x + rng.normal(size=40)
for m, fn in (("pearson", stats.pearsonr), ("spearman", stats.spearmanr), ("kendall", lambda a, b: stats.kendalltau(a, b, variant="b"))):
    r = CC.correlate_pair(x, y, m); ref = fn(x, y)
    check(abs(r["r"] - ref[0]) < 1e-12 and abs(r["p"] - ref[1]) < 1e-12, f"{m}: r = {r['r']:.4f}, p = {r['p']:.4g} збігаються зі scipy")
k = CC.correlate_pair([1, 2, 3, 4, 5], [2, 1, 4, 3, 5], "kendall")
check(abs(k["r"] - 0.6) < 1e-12, "Кендалл за ручним розрахунком: (8 узгоджених − 2 неузгоджених)/10 = 0,6")
xt = np.array([1, 1, 2, 3, 3, 3, 4, 5, 5, 6.]); yt = np.array([2, 1, 2, 4, 3, 5, 4, 6, 7, 6.])
C = D = Tx = Ty = 0
for i, j in itertools.combinations(range(len(xt)), 2):
    dx, dy = xt[i] - xt[j], yt[i] - yt[j]
    if dx * dy > 0: C += 1
    elif dx * dy < 0: D += 1
    else:
        if dx == 0 and dy != 0: Tx += 1
        elif dy == 0 and dx != 0: Ty += 1
tau_b = (C - D) / math.sqrt((C + D + Tx) * (C + D + Ty))
check(abs(CC.correlate_pair(xt, yt, "kendall")["r"] - tau_b) < 1e-12, f"τ-b зі зв'язаними рангами = наївний перебір пар ({tau_b:.4f})")

print("\n== 3. Довірчі інтервали")
r = CC.correlate_pair(x, y, "pearson"); sci = stats.pearsonr(x, y).confidence_interval(0.95)
check(abs(r["ci_lo"] - sci.low) < 1e-9 and abs(r["ci_hi"] - sci.high) < 1e-9, f"Пірсон: ДІ [{r['ci_lo']:.4f}; {r['ci_hi']:.4f}] збігається зі scipy")
for m in ("pearson", "spearman", "kendall"):
    rr = CC.correlate_pair(x, y, m); check(rr["ci_lo"] < rr["r"] < rr["ci_hi"], f"{m}: ДІ містить оцінку")
w = lambda n: (lambda c: c["ci_hi"] - c["ci_lo"])(CC.correlate_pair(rng.normal(size=n), rng.normal(size=n), "spearman"))
check(np.mean([w(15) for _ in range(30)]) > np.mean([w(120) for _ in range(30)]), "інтервал звужується зі зростанням n")
check(CC.fisher_ci(1.0, 20) == (1.0, 1.0) and all(math.isnan(v) for v in CC.fisher_ci(0.5, 3)) and all(math.isnan(v) for v in CC.fisher_ci(0.5, 4, "kendall")),
      "|r| = 1 → вироджений інтервал; замале n → NaN")
def coverage(method, n=30, rho=0.5, N=2500, seed=11):
    g = np.random.default_rng(seed); cov = 0
    truth = {"pearson": rho, "spearman": 6 / math.pi * math.asin(rho / 2), "kendall": 2 / math.pi * math.asin(rho)}[method]
    L = np.linalg.cholesky(np.array([[1, rho], [rho, 1]]))
    for _ in range(N):
        s = g.normal(size=(n, 2)) @ L.T; c = CC.correlate_pair(s[:, 0], s[:, 1], method)
        cov += (c["ci_lo"] <= truth <= c["ci_hi"])
    return cov / N, truth
for m in ("pearson", "spearman", "kendall"):
    cv, tr = coverage(m)
    check(0.935 <= cv <= 0.965, f"{m}: покриття 95 % інтервалу на 2500 симуляціях = {100 * cv:.1f} % (істинне значення {tr:.4f})")

print("\n== 4. Матриця, поправки, пропуски")
k = 5; cols = [rng.normal(size=30)]
for _ in range(k - 1): cols.append(0.5 * cols[0] + rng.normal(size=30))
lab = [f"П{i + 1}" for i in range(k)]
for corr in ("holm", "bonferroni", "bh", "none"):
    M = CC.correlation_matrix(cols, lab, "spearman", 0.05, corr)
    check(np.allclose(M["r"], M["r"].T, equal_nan=True) and np.allclose(np.diag(M["r"]), 1) and len(M["pairs"]) == 10, f"{corr}: матриця симетрична, діагональ 1, 10 пар")
Mh = CC.correlation_matrix(cols, lab, "pearson", 0.05, "holm"); Mb = CC.correlation_matrix(cols, lab, "pearson", 0.05, "bonferroni")
Mf = CC.correlation_matrix(cols, lab, "pearson", 0.05, "bh"); Mn = CC.correlation_matrix(cols, lab, "pearson", 0.05, "none")
ph = np.array([p["p_adj"] for p in Mh["pairs"]]); pb = np.array([p["p_adj"] for p in Mb["pairs"]]); pf = np.array([p["p_adj"] for p in Mf["pairs"]])
pr = np.array([p["p_raw"] for p in Mh["pairs"]]); pn = np.array([p["p_adj"] for p in Mn["pairs"]])
check(np.all(pr <= ph + 1e-15) and np.all(ph <= pb + 1e-15) and np.all(pf <= pb + 1e-15) and np.allclose(pn, pr), "p_сирі ≤ Холм ≤ Бонферроні; BH ≤ Бонферроні; «без поправки» = сирі")
check(np.allclose(p_adjust([0.01, 0.04, 0.03], "holm"), [0.03, 0.06, 0.06]), "Холм за ручним прикладом: [0,01; 0,04; 0,03] → [0,03; 0,06; 0,06]")
check(np.allclose(p_adjust([0.01, 0.04, 0.03], "bh"), [0.03, 0.04, 0.04]), "Беньяміні–Хохберг за ручним прикладом → [0,03; 0,04; 0,04]")
# пропуски: кожна пара = ручне попарне виключення
cm = [c.copy() for c in cols]; cm[1][[2, 5, 9]] = np.nan; cm[3][[1, 5, 20]] = np.nan; cm[0][7] = np.nan
Mm = CC.correlation_matrix(cm, lab, "pearson", 0.05, "none")
ok = True
for i, j in itertools.combinations(range(k), 2):
    mk = ~(np.isnan(cm[i]) | np.isnan(cm[j])); ref = stats.pearsonr(cm[i][mk], cm[j][mk])
    ok &= abs(Mm["r"][i, j] - ref[0]) < 1e-12 and Mm["n"][i, j] == mk.sum()
check(ok, "з пропусками кожна пара = попарне виключення на спільних рядках (n різне для різних пар)")
check(len({Mm["n"][i, j] for i, j in itertools.combinations(range(k), 2)}) > 1, "n у парах різні — це видно в матриці n")
cc = [cols[0], np.full(30, 3.0), cols[2], np.array([np.nan] * 28 + [1.0, 2.0])]
Ms = CC.correlation_matrix(cc, ["А", "Б", "В", "Г"], "pearson", 0.05, "holm")
st = {(a, b): s for a, b, s in Ms["skipped"]}
check(st[("А", "Б")] == "один із показників сталий" and "менше 3" in st[("А", "Г")] and len(Ms["pairs"]) == 1, "стала змінна й замале n — пара пропускається з поясненням, без помилки")
try: CC.correlation_matrix([np.zeros(3), np.zeros(4)], ["a", "b"]); check(False, "мало впасти")
except ValueError: check(True, "масиви різної довжини → зрозуміла помилка")
check([CC.strength(v) for v in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95)] == ["дуже слабкий", "слабкий", "помірний", "помітний", "високий", "дуже високий"] and CC.strength(-0.8) == "високий", "словесна шкала сили зв'язку (Чеддок) для |r|")

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ КОРЕЛЯЦІЙНОГО ЯДРА ПРОЙДЕНО")
