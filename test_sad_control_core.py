# test_sad_control_core.py — порівняння зі стандартом (Дуннетт)
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_control_core as C
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(1)

print("== 1. Звірка з scipy.stats.dunnett (однофакторна схема, різні n)")
a = rng.normal(10, 2, 8); b = rng.normal(12, 2, 6); c = rng.normal(10.5, 2, 9); ctl = rng.normal(10, 2, 7)
ent = ["A"] * 8 + ["B"] * 6 + ["C"] * 9 + ["St"] * 7; y = np.concatenate([a, b, c, ctl])
res = C.compare_to_control(ent, y, "St")
ref = stats.dunnett(a, b, c, control=ctl); rci = ref.confidence_interval()
t0 = time.time()
check(np.allclose([r["p_dunnett"] for r in res["rows"]], ref.pvalue, atol=3e-3), f"p-значення Дуннетта збігаються з scipy: {[round(r['p_dunnett'],4) for r in res['rows']]} vs {np.round(ref.pvalue,4)}")
check(np.allclose([r["t"] for r in res["rows"]], ref.statistic, atol=1e-9), "t-статистики збігаються точно")
check(np.allclose([r["ci_lo"] for r in res["rows"]], rci.low, atol=6e-3) and np.allclose([r["ci_hi"] for r in res["rows"]], rci.high, atol=6e-3),
      "одночасні довірчі інтервали збігаються зі scipy")
check(res["df"] == 26 and abs(res["mse"] - np.sum([np.sum((g - g.mean()) ** 2) for g in (a, b, c, ctl)]) / 26) < 1e-10, "MSE і df = N − k")
check(np.allclose([r["mean"] for r in res["rows"]], [a.mean(), b.mean(), c.mean()]) and abs(res["control_mean"] - ctl.mean()) < 1e-12, "середні = звичайні середні (без блоків)")
check(np.allclose([r["pct"] for r in res["rows"]], [100 * m / ctl.mean() for m in (a.mean(), b.mean(), c.mean())]), "% до стандарту = середнє/середнє стандарту ·100")

print("\n== 2. Табличні критичні значення Дуннетта (df = 20, α = 0,05, двобічні)")
for k, tab in ((1, 2.086), (2, 2.38), (3, 2.54), (4, 2.65), (5, 2.73)):
    R = np.full((k, k), 0.5) + np.eye(k) * 0.5
    cv = C.dunnett_critical(R, 20, 0.05)
    check(abs(cv - tab) < 0.01, f"k = {k}: c = {cv:.3f} (таблиця Дуннетта {tab})")
R3 = np.full((3, 3), 0.5) + np.eye(3) * 0.5
check(C.dunnett_critical(R3, 20, 0.05, "greater") < C.dunnett_critical(R3, 20, 0.05) and abs(C.dunnett_critical(np.eye(1), 20, 0.05, "greater") - stats.t.ppf(0.95, 20)) < 1e-9,
      "одностороннє критичне < двостороннього; для k = 1 — звичайний t")

print("\n== 2б. Швидка квадратура ↔ багатовимірний t; запасний метод Монте-Карло; швидкість")
for k in (3, 6):
    n_i = np.array([4, 5, 6, 3, 4, 7][:k]); lam = np.sqrt(n_i / (n_i + 5)); Rk = np.outer(lam, lam) + np.diag(1 - lam ** 2)
    d = max(abs(C._cdf_onefactor(lam, 18, c, "two-sided") - C._mvt_box([-c] * k, [c] * k, Rk, 18)) for c in (1.5, 2.4, 3.1))
    check(d < 5e-5, f"k = {k}, нерівні n: квадратура = багатовимірний t (макс. розбіжність {d:.1e})")
    d1 = abs(C._cdf_onefactor(lam, 18, 2.0, "greater") - C._mvt_box([-60] * k, [2.0] * k, Rk, 18)); check(d1 < 5e-5, f"k = {k}: одностороння ймовірність теж збігається ({d1:.1e})")
Rg = np.corrcoef(np.random.default_rng(3).normal(size=(8, 30))); Rg = 0.6 * Rg + 0.4 * np.eye(8)
check(C._method(Rg)[0] == "mvt" and C._onefactor(Rg) is None, "довільна кореляційна структура розпізнана → багатовимірний t")
Rg20 = np.corrcoef(np.random.default_rng(4).normal(size=(20, 40))); Rg20 = 0.6 * Rg20 + 0.4 * np.eye(20)
mcp = C.dunnett_pvalues([2.0, 3.0], Rg20[:2, :2], 25); mc_big = C._mc_max(Rg20, 25, "two-sided")
mvp = 1 - C._mvt_box([-3.0] * 20, [3.0] * 20, Rg20, 25)
p_mc = 1 - np.searchsorted(mc_big, 3.0) / len(mc_big)
check(C._method(Rg20)[0] == "mc" and abs(p_mc - mvp) < 3e-3, f"k = 20, довільна R: Монте-Карло ≈ багатовимірний t ({p_mc:.4f} vs {mvp:.4f})")
Rb = np.full((200, 200), 0.5) + np.eye(200) * 0.5; t0 = time.time()
cv200 = C.dunnett_critical(Rb, 120, 0.05); p200 = C.dunnett_pvalues(np.linspace(0.5, 4.5, 200), Rb, 120); el = time.time() - t0
check(el < 120 and 3.4 < cv200 < 3.7 and np.all(np.diff(p200) <= 1e-9), f"200 номерів: критичне {cv200:.3f}, 200 p-значень — за {el:.1f} с, монотонні")
big = C.compare_to_control(["St"] * 4 + sum([[f"N{i}"] * 4 for i in range(1, 151)], []), np.random.default_rng(8).normal(50, 3, 4 + 600), "St")
check(len(big["rows"]) == 150 and all(0 <= r["p_dunnett"] <= 1 for r in big["rows"]), "150 номерів проти стандарту — повний аналіз без помилок")

print("\n== 3. Блоки (RCBD): збалансований випадок")
g, r = 6, 4; ge = rng.normal(0, 1.5, g); bl = rng.normal(0, 1, r)
E, Y, B = [], [], []
for i in range(g):
    for k in range(r):
        E.append("St" if i == 0 else f"N{i}"); B.append(f"R{k+1}"); Y.append(20 + ge[i] + bl[k] + rng.normal(0, 1))
Y = np.array(Y); res = C.compare_to_control(E, Y, "St", B)
Ym = Y.reshape(g, r); gm = Ym.mean()
sse = np.sum((Ym - Ym.mean(1, keepdims=True) - Ym.mean(0, keepdims=True) + gm) ** 2); mse = sse / ((g - 1) * (r - 1))
check(abs(res["mse"] - mse) < 1e-9 and res["df"] == 15, "MSE і df збігаються з ANOVA RCBD")
check(np.allclose(res["R"][np.triu_indices(5, 1)], 0.5, atol=1e-9), "кореляція між порівняннями зі стандартом = 0,5 (збалансований план)")
check(np.allclose([x["se_diff"] for x in res["rows"]], math.sqrt(2 * mse / r)), "SE різниці = √(2·MSE/r)")
check(np.allclose([x["mean"] for x in res["rows"]], Ym.mean(1)[1:]), "середні номерів = звичайні (збалансований план)")
k1 = C.compare_to_control(E[:8], Y[:8], "St", B[:8])
check(abs(k1["rows"][0]["p_dunnett"] - k1["rows"][0]["p_lsd"]) < 1e-12, "для одного порівняння (k = 1) поправка не потрібна: p Дуннетта = p t-тесту")
check(all(x["p_dunnett"] >= x["p_lsd"] - 1e-9 for x in res["rows"]), "p за Дуннеттом ≥ p без поправки (НІР)")
check(all(x["dunnett_diff"] > x["lsd"] for x in res["rows"]), "істотна різниця Дуннетта більша за НІР₀₅ при k > 1")

print("\n== 4. Пропущені ділянки: інваріантність до параметризації")
keep = [i for i in range(len(Y)) if i not in (3, 9, 17)]
Eu = [E[i] for i in keep]; Bu = [B[i] for i in keep]; Yu = Y[keep]
ru = C.compare_to_control(Eu, Yu, "St", Bu)
lv = list(dict.fromkeys(Eu)); bs = list(dict.fromkeys(Bu))
X = np.column_stack([np.ones(len(Yu))] + [[1.0 if e == l else 0.0 for e in Eu] for l in lv[1:] if l != "St"] +
                    [[1.0 if x == b_ else 0.0 for x in Bu] for b_ in bs[1:]])
lv2 = [l for l in lv if l != "St"]
X = np.column_stack([np.ones(len(Yu))] + [[1.0 if e == l else 0.0 for e in Eu] for l in lv2] + [[1.0 if x == b_ else 0.0 for x in Bu] for b_ in bs[1:]])
bt, rs, rk, _ = np.linalg.lstsq(X, Yu, rcond=None)
d_alt = {l: bt[1 + i] for i, l in enumerate(lv2)}            # різниця «номер − стандарт» у параметризації зі стандартом як базою
mse_alt = float(np.sum((Yu - X @ bt) ** 2) / (len(Yu) - X.shape[1]))
check(np.allclose([x["diff"] for x in ru["rows"]], [d_alt[x["entry"]] for x in ru["rows"]], atol=1e-8) and abs(ru["mse"] - mse_alt) < 1e-9,
      "різниці й MSE збігаються з незалежною параметризацією (стандарт як базовий рівень)")
check(any("різна" in w for w in ru["warnings"]), "попередження про різну кількість повторностей")
check(len({round(x["se_diff"], 6) for x in ru["rows"]}) > 1, "SE різниці різняться за номерами (різна кількість повторностей)")

print("\n== 5. Кілька стандартів")
E2 = ["S1"] * 4 + ["S2"] * 4 + ["A"] * 4 + ["B"] * 4; Y2 = np.array(list(rng.normal(10, 1, 4)) + list(rng.normal(12, 1, 4)) + list(rng.normal(13, 1, 4)) + list(rng.normal(9, 1, 4)))
rm = C.compare_to_control(E2, Y2, ["S1", "S2"])
cm = (Y2[:4].mean() + Y2[4:8].mean()) / 2
check(abs(rm["control_mean"] - cm) < 1e-12 and np.allclose([x["diff"] for x in rm["rows"]], [Y2[8:12].mean() - cm, Y2[12:].mean() - cm]), "порівняння із СЕРЕДНІМ двох стандартів")
check(any("СЕРЕДНІМ" in w for w in rm["warnings"]), "про це повідомлено")

print("\n== 6. Односторонній тест")
rg = C.compare_to_control(E2[4:], Y2[4:], "S2", alternative="greater"); r2 = C.compare_to_control(E2[4:], Y2[4:], "S2")
check(abs(r2["rows"][0]["p_lsd"] - 2 * rg["rows"][0]["p_lsd"]) < 1e-12 if rg["rows"][0]["t"] > 0 else True, "p двобічний = 2 × p односторонній (за t > 0)")
check(rg["rows"][0]["ci_hi"] == float("inf"), "односторонній інтервал «більше» — без верхньої межі")

print("\n== 7. Частота хибних спрацювань (усі нульові гіпотези істинні, k = 6, 4 повторності)")
sim = np.random.default_rng(77); N = 1500; any_dun = any_lsd = 0; t0 = time.time()
Es = ["St"] * 4 + sum([[f"N{i}"] * 4 for i in range(1, 7)], [])
for _ in range(N):
    yy = sim.normal(50, 3, len(Es)); rr = C.compare_to_control(Es, yy, "St", ci=False)
    any_dun += any(x["p_dunnett"] < 0.05 for x in rr["rows"]); any_lsd += any(x["p_lsd"] < 0.05 for x in rr["rows"])
fd, fl = any_dun / N, any_lsd / N
check(0.035 <= fd <= 0.068, f"Дуннетт: хоча б одне хибне спрацювання у {100 * fd:.1f} % дослідів (номінал 5 %)")
check(fl > 0.17, f"без поправки (НІР): {100 * fl:.1f} % (понад 3× більше за номінал; менше за 26 %, бо порівняння корельовані через спільний стандарт) — саме тому поправка потрібна")
print(f"        (час симуляції {time.time() - t0:.0f} с)")

print("\n== 8. Помилки й попередження")
for args, frag in [((["A", "B"], [1.0, 2.0], "Z"), "немає серед"), ((["A", "A"], [1.0, 2.0], "A"), "окрім стандарту"),
                   ((["A", "B", "St"], [1.0, 2.0, 3.0], "St"), "ступенів свободи"), ((["A", "B"], [1.0, float("nan")], "A"), "порожні")]:
    try: C.compare_to_control(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
Ed = ["St", "St", "A", "A", "A", "A"]; Bd = ["R1", "R1", "R2", "R2", "R3", "R3"]; Yd = [1, 2, 3, 4, 5, 6]
try: C.compare_to_control(Ed, Yd, "St", Bd); check(False, "відокремлений план мав дати помилку")
except BreedingError as ex: check("не пов'язаний" in str(ex), "номер, що не зустрічається зі стандартом в одному блоці → зрозуміла помилка")
w1 = C.compare_to_control(["St", "A", "A", "B", "B", "C", "C"], [5, 6, 7, 5, 6, 8, 9], "St")
check(any("лише 1 спостереження" in w for w in w1["warnings"]), "стандарт без повторностей → попередження")
check(any("ступенів свободи" in w and "малопотужний" in w for w in w1["warnings"]), "мало df → попередження про потужність")

print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ПОРІВНЯННЯ ЗІ СТАНДАРТОМ ПРОЙДЕНО")
