# test_sad_corr_partial.py — частинна й напівчастинна кореляція: незалежні способи обчислення
import os, sys, math, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_corr_core as CC
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(8)
n = 80
z1 = rng.normal(size=n); z2 = rng.normal(size=n)
x = 0.7 * z1 + 0.3 * z2 + rng.normal(0, 0.8, n); y = 0.6 * z1 - 0.4 * z2 + 0.25 * x + rng.normal(0, 0.8, n)

print("== 1. Частинна кореляція: три незалежні способи")
res1 = CC.partial_correlation(x, y, [z1])
rxy, rxz, ryz = (np.corrcoef(a, b)[0, 1] for a, b in ((x, y), (x, z1), (y, z1)))
formula = (rxy - rxz * ryz) / math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
check(abs(res1["r"] - formula) < 1e-12, f"1 контрольна: r = {res1['r']:.6f} = (r_xy − r_xz·r_yz)/√[(1−r²_xz)(1−r²_yz)]")
res2 = CC.partial_correlation(x, y, [z1, z2])
Rm = np.corrcoef(np.vstack([x, y, z1, z2])); P = np.linalg.inv(Rm); prec = -P[0, 1] / math.sqrt(P[0, 0] * P[1, 1])
check(abs(res2["r"] - prec) < 1e-12, f"2 контрольні: r = {res2['r']:.6f} = −P₁₂/√(P₁₁P₂₂) через обернену кореляційну матрицю")
D = np.column_stack([np.ones(n), x, z1, z2]); beta = np.linalg.lstsq(D, y, rcond=None)[0]
res_ = y - D @ beta; df = n - 4; s2 = res_ @ res_ / df; se_b = math.sqrt(s2 * np.linalg.inv(D.T @ D)[1, 1]); t_b = beta[1] / se_b
check(abs(res2["p"] - 2 * stats.t.sf(abs(t_b), df)) < 1e-12 and res2["df"] == df, "p-значення = p t-тесту коефіцієнта x у регресії y ~ x + Z (df = n − 2 − k)")
check(abs(abs(res2["r"]) - math.sqrt(t_b ** 2 / (t_b ** 2 + df))) < 1e-12 and np.sign(res2["r"]) == np.sign(t_b), "r = ±√[t²/(t² + df)] за знаком коефіцієнта")
check(res2["n"] == n and res2["k"] == 2 and res2["ci_lo"] < res2["r"] < res2["ci_hi"], "n, k, довірчий інтервал містить оцінку")

print("\n== 2. Напівчастинна кореляція")
D0 = np.column_stack([np.ones(n), z1, z2]); b0 = np.linalg.lstsq(D0, y, rcond=None)[0]
R2_full = 1 - (res_ @ res_) / np.sum((y - y.mean()) ** 2); r0_ = y - D0 @ b0; R2_red = 1 - (r0_ @ r0_) / np.sum((y - y.mean()) ** 2)
check(abs(res2["sr_x"] ** 2 - (R2_full - R2_red)) < 1e-12, f"sr² = ΔR² = {R2_full - R2_red:.6f} (унікальний внесок x у дисперсію y) — точна тотожність")
check(abs(res2["sr_x"]) <= abs(res2["r"]) + 1e-12 and abs(res2["sr_y"]) <= abs(res2["r"]) + 1e-12, "|sr| ≤ |частинна r|")
Dx = np.column_stack([np.ones(n), y, z1, z2]); bx_ = np.linalg.lstsq(Dx, x, rcond=None)[0]; rx_ = x - Dx @ bx_
R2x_full = 1 - (rx_ @ rx_) / np.sum((x - x.mean()) ** 2); r0x = x - D0 @ np.linalg.lstsq(D0, x, rcond=None)[0]; R2x_red = 1 - (r0x @ r0x) / np.sum((x - x.mean()) ** 2)
check(abs(res2["sr_y"] ** 2 - (R2x_full - R2x_red)) < 1e-12, "sr² для y відносно x — також ΔR²")

print("\n== 3. Конфаундер: зв'язок зникає після контролю")
g = np.random.default_rng(1); m = 5000; zc = g.normal(size=m)
xc = zc + g.normal(0, 0.5, m); yc = zc + g.normal(0, 0.5, m)
rc = CC.partial_correlation(xc, yc, [zc])
check(rc["r0"] > 0.75 and abs(rc["r"]) < 0.05 and rc["p"] > 0.01, f"спільна причина: r = {rc['r0']:.3f} → частинна r = {rc['r']:.3f} (p = {rc['p']:.2f})")
cc = CC.partial_correlation(xc, yc, [])
check(abs(cc["r"] - cc["r0"]) < 1e-12 and cc["k"] == 0, "без контрольних ознак частинна = звичайна кореляція")

print("\n== 4. Спірмен і пропуски")
rs = CC.partial_correlation(x, y, [z1, z2], "spearman")
rk = [stats.rankdata(a) for a in (x, y, z1, z2)]; ref = CC.partial_correlation(rk[0], rk[1], rk[2:], "pearson")
check(abs(rs["r"] - ref["r"]) < 1e-12, "частинний Спірмен = частинний Пірсон на рангах (за визначенням)")
xm, ym, z1m = x.copy(), y.copy(), z1.copy(); xm[[3, 9]] = np.nan; ym[15] = np.nan; z1m[[3, 40]] = np.nan
rmiss = CC.partial_correlation(xm, ym, [z1m, z2]); mk = ~(np.isnan(xm) | np.isnan(ym) | np.isnan(z1m))
rref = CC.partial_correlation(x[mk], y[mk], [z1[mk], z2[mk]])
check(rmiss["n"] == mk.sum() == n - 4 and abs(rmiss["r"] - rref["r"]) < 1e-12, f"пропуски: спільна вибірка n = {rmiss['n']} (рядки з повними даними за всіма змінними)")

print("\n== 5. Покриття довірчого інтервалу частинної кореляції (симуляція)")
S = np.array([[1, 0.4, 0.5, 0.3], [0.4, 1, 0.3, -0.2], [0.5, 0.3, 1, 0.2], [0.3, -0.2, 0.2, 1]])
Pm = np.linalg.inv(S); truth = -Pm[0, 1] / math.sqrt(Pm[0, 0] * Pm[1, 1]); L = np.linalg.cholesky(S)
sim = np.random.default_rng(21); cov = 0; N = 2500; nn = 40
for _ in range(N):
    d = sim.normal(size=(nn, 4)) @ L.T; c = CC.partial_correlation(d[:, 0], d[:, 1], [d[:, 2], d[:, 3]])
    cov += (c["ci_lo"] <= truth <= c["ci_hi"])
check(0.935 <= cov / N <= 0.965, f"95 % ДІ при двох контрольних ознаках: покриття {100 * cov / N:.1f} % на {N} симуляціях (істинна частинна r = {truth:.4f})")

print("\n== 6. Матриця пар і поправка")
arrs = [x, y, z1, z2, rng.normal(size=n)]; labs = ["X", "Y", "Z1", "Z2", "W"]
M = CC.partial_matrix(arrs, labs, [2, 3], [0, 1, 4], "pearson", 0.05, "holm")
check(len(M["pairs"]) == 3 and M["n"] == n and M["k"] == 2 and M["controls"] == ["Z1", "Z2"], "3 пари серед 3 досліджуваних ознак, контролі Z1, Z2")
q = next(p for p in M["pairs"] if (p["a"], p["b"]) == ("X", "Y")); check(abs(q["r"] - res2["r"]) < 1e-12, "пара X–Y збігається з прямим розрахунком")
check(all(p["p_adj"] >= p["p_raw"] - 1e-15 for p in M["pairs"]), "p з поправкою ≥ сирого")
amiss = [a.copy() for a in arrs]; amiss[0][[2, 5]] = np.nan; amiss[4][7] = np.nan; amiss[2][11] = np.nan
Mm = CC.partial_matrix(amiss, labs, [2, 3], [0, 1, 4]); check(Mm["n"] == n - 4 and Mm["dropped_rows"] == 4 and len({p["n"] for p in Mm["pairs"]}) == 1,
                                                            "одна спільна вибірка для всіх пар (n однакове); кількість відкинутих рядків повідомляється")

print("\n== 7. Помилки")
for fn, frag in [(lambda: CC.partial_correlation(x[:20], y[:20], [z1[:20], z2[:20], z1[:20] * 2 + 1]), "лінійно залежні"),
                 (lambda: CC.partial_correlation(x[:4], y[:4], [z1[:4], z2[:4]]), "Замало"),
                 (lambda: CC.partial_correlation(x, np.full(n, 3.0), [z1]), "стала"),
                 (lambda: CC.partial_correlation(x, y, [z1, z1 + 1e-17 * z2]), "залежні"),
                 (lambda: CC.partial_correlation(x, y, [x * 2 + 3]), "повністю пояснюють"),
                 (lambda: CC.partial_correlation(x, y, [z1], "kendall"), "Пірсона й Спірмена"),
                 (lambda: CC.partial_matrix(arrs, labs, [0], [0, 1]), "не може бути і"),
                 (lambda: CC.partial_matrix(arrs, labs, [2], [0]), "щонайменше 2")]:
    try: fn(); check(False, f"«{frag}» мало дати помилку")
    except CC.PartialError as ex: check(frag in str(ex), f"помилка «{frag}»")
print("\n== 8. Розділи результатів: конфаундер і супресія")
import sad_corr_sections as CS, sad_breeding_ui as U, tempfile, shutil
from matplotlib.figure import Figure
import matplotlib
g = np.random.default_rng(31); m = 300
def _orth(v, *basis):                               # залишок v після регресії на [1, basis…] — точна ортогональність
    D = np.column_stack([np.ones(len(v))] + list(basis)); return v - D @ np.linalg.lstsq(D, v, rcond=None)[0]
zc = g.normal(size=m); e1 = _orth(g.normal(0, 0.6, m), zc); e2 = _orth(g.normal(0, 0.6, m), zc, e1)
xc = zc + e1; yc = zc + e2; wc = g.normal(size=m)      # шум не корелює ні із Z, ні сам із собою → істинна частинна r = 0
S, warns, M = CS.sections_partial([xc, yc, wc, zc], ["X", "Y", "W", "Z"], [3], [0, 1, 2], "pearson", 0.05, "holm")
check([s["key"] for s in S] == ["partial", "semi", "heat", "bars", "help"], "розділи: частинні, напівчастинні, дві діаграми, пояснення")
bad = [s["title"] for s in S if s["kind"] == "table" and (any(len(r) != len(s["headers"]) for r in s["rows"]) or len(s["nd"]) != len(s["headers"]))]
check(not bad, "структура таблиць коректна")
msgs = []
for s in S:
    if s["kind"] == "figure":
        f = Figure(figsize=s["size"])
        with matplotlib.rc_context(U._RC): msgs.append(s["build"](f))
check(not any(msgs), "обидва графіки будуються")
tab = S[0]; hd = tab["headers"]; row = next(r for r in tab["rows"] if r[0] == "X" and r[1] == "Y")
check(row[hd.index("Висновок")] == "зникає після контролю" and tab["tags"][tab["rows"].index(row)] == "warn" and abs(row[4]) < 1e-9,
      f"конфаундер: r = {row[2]:.2f} → частинна {row[4]:.1e}: «зникає після контролю», жовте")
direct = CC.partial_correlation(xc, yc, [zc]); check(abs(row[4] - direct["r"]) < 1e-12 and abs(row[hd.index("Δ")] - (direct["r"] - direct["r0"])) < 1e-12, "значення в таблиці = прямий розрахунок")
# супресія
e1 = g.normal(size=m); zs = g.normal(size=m); xs = zs + e1 * 0.7; ys = xs - 1.5 * zs + g.normal(0, 0.7, m)
S2, w2, M2 = CS.sections_partial([xs, ys, zs], ["X", "Y", "Z"], [2], [0, 1], "pearson", 0.05, "holm")
r2 = S2[0]["rows"][0]; hd2 = S2[0]["headers"]
check(abs(r2[2]) < 0.2 and abs(r2[4]) > 0.6 and r2[hd2.index("Висновок")] == "проявляється лише після контролю" and S2[0]["tags"][0] == "info",
      f"супресія: r = {r2[2]:.2f} → частинна {r2[4]:.2f}: «проявляється лише після контролю», блакитне")
check(w2 == [] , "для великої вибірки без пропусків попереджень немає")
Sw, ww, Mw = CS.sections_partial([xc[:20], yc[:20], zc[:20]], ["X", "Y", "Z"], [2], [0, 1])
check(any("невелика" in x for x in ww), "n = 20: попередження про малу вибірку")
am = [xc.copy(), yc.copy(), wc.copy(), zc.copy()]; am[0][[1, 5]] = np.nan
Sm, wm, Mm = CS.sections_partial(am, ["X", "Y", "W", "Z"], [3], [0, 1, 2], "spearman")
check(any("відкинуто 2" in x for x in wm) and any("наближення" in x for x in wm), "пропуски й Спірмен: попередження про відкинуті рядки та наближення")
# експорт
tmp = tempfile.mkdtemp(); px = os.path.join(tmp, "p.xlsx"); U.export_xlsx(px, S, "Частинна"); import openpyxl; wb = openpyxl.load_workbook(px)
check(set(wb.sheetnames[:2]) == {"Частинні кореляції", "Напівчастинні кореляції"}, f"Excel: аркуші {wb.sheetnames[:3]}")
U.export_docx(os.path.join(tmp, "p.docx"), "Частинна", S, True); import docx; d = docx.Document(os.path.join(tmp, "p.docx"))
cells = [c.text for c in d.tables[0].rows[1].cells]; check(len(d.tables) == 2 and any(c.startswith("<0,0001") or c.startswith("0,") for c in cells), f"Word: 2 таблиці; p у форматі статті: {cells[3]}, {cells[7]}")
shutil.rmtree(tmp, ignore_errors=True)

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЧАСТИННОЇ КОРЕЛЯЦІЇ ПРОЙДЕНО")
