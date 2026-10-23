# test_sad_ordinal_core.py — бальні ознаки: Данн (звірка з Крускалом–Уолліcом), поправки, літери, AUDPC, індекс
import os, sys, math, itertools, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_ordinal_core as O
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

print("== 1. Тест Данна: незалежні еталони")
rg = np.random.default_rng(3)
a = rg.integers(1, 10, 15).astype(float); b = rg.integers(3, 10, 12).astype(float)       # багато зв'язаних рангів
res = O.dunn_test({"A": a, "B": b})
kw = stats.kruskal(a, b)
check(abs(res["pairs"][0][2] ** 2 - kw.statistic) < 1e-9 and abs(res["pairs"][0][3] - kw.pvalue) < 1e-9,
      f"для двох груп z² = H Крускала–Уолліса з поправкою на зв'язані ранги ({res['pairs'][0][2] ** 2:.5f} = {kw.statistic:.5f}), p збігається")
c_ = rg.integers(1, 8, 10).astype(float); r3 = O.dunn_test({"A": a, "B": b, "C": c_}, "bonferroni")
allv = np.concatenate([a, b, c_]); N = len(allv); rk = stats.rankdata(allv)
R = {"A": rk[:15].mean(), "B": rk[15:27].mean(), "C": rk[27:].mean()}; n = {"A": 15, "B": 12, "C": 10}
_, tc = np.unique(allv, return_counts=True); var0 = N * (N + 1) / 12 - np.sum(tc ** 3 - tc) / (12 * (N - 1))
ok = True
for (x, y_, z, p, pa) in r3["pairs"]:
    zr = (R[x] - R[y_]) / math.sqrt(var0 * (1 / n[x] + 1 / n[y_]))
    ok &= abs(z - zr) < 1e-12 and abs(p - 2 * stats.norm.sf(abs(zr))) < 1e-12 and abs(pa - min(1, 3 * p)) < 1e-12
check(ok, "z, p і p за Бонферроні для 3 груп збігаються з розрахунком за визначенням")
check(abs(r3["kw_H"] - stats.kruskal(a, b, c_).statistic) < 1e-12 and r3["kw_df"] == 2, "загальний тест Крускала–Уолліса")
check(abs(sum(r3["mean_ranks"][k] * r3["n"][k] for k in "ABC") - N * (N + 1) / 2) < 1e-9, "Σ(nᵢ·R̄ᵢ) = N(N+1)/2 — ранги розподілено коректно")

print("\n== 2. Поправки на множинність")
p = [0.01, 0.04, 0.03]
check(np.allclose(O.p_adjust(p, "holm"), [0.03, 0.06, 0.06]) and np.allclose(O.p_adjust(p, "bonferroni"), [0.03, 0.12, 0.09]) and np.allclose(O.p_adjust(p, "bh"), [0.03, 0.04, 0.04]),
      "Холм [0,03; 0,06; 0,06]; Бонферроні [0,03; 0,12; 0,09]; Беньяміні–Хохберг [0,03; 0,04; 0,04] — ручні еталони")
pr = np.random.default_rng(1).uniform(0, 0.2, 25)
check(np.allclose(O.p_adjust(pr, "bh"), stats.false_discovery_control(pr)), "Беньяміні–Хохберг збігається з scipy.stats.false_discovery_control")
check(np.all(O.p_adjust(pr, "holm") >= pr - 1e-12) and np.all(O.p_adjust(pr, "holm") <= O.p_adjust(pr, "bonferroni") + 1e-12), "p ≤ p_Холма ≤ p_Бонферроні")
try: O.p_adjust(p, "xx"); check(False, "мало впасти")
except BreedingError: check(True, "невідомий метод → помилка")

print("\n== 3. Частота хибних спрацювань (усі групи з одного розподілу, бали 1–9)")
sim = np.random.default_rng(8); N_ = 1500; kw_rej = 0; any_dunn = 0; p_probs = np.array([.05, .1, .15, .2, .2, .15, .1, .05, 0.0]); p_probs /= p_probs.sum()
for _ in range(N_):
    gr = {f"G{i}": sim.choice(np.arange(1, 10), 12, p=p_probs).astype(float) for i in range(4)}
    rr = O.dunn_test(gr, "holm"); kw_rej += rr["kw_p"] < 0.05; any_dunn += any(q[4] < 0.05 for q in rr["pairs"])
check(0.035 <= kw_rej / N_ <= 0.07, f"Крускал–Уолліс: {100 * kw_rej / N_:.1f} % хибних спрацювань (номінал 5 %)")
check(any_dunn / N_ <= 0.065, f"Данн з поправкою Холма: хоча б одна хибна пара у {100 * any_dunn / N_:.1f} % дослідів (≤ 5 %)")

print("\n== 4. Літери значущості (максимальні кліки)")
def letters_ok(names, sigpairs):
    pairs = [[a_, b_, 0, 0, 0.001 if frozenset((a_, b_)) in sigpairs else 0.5] for a_, b_ in itertools.combinations(names, 2)]
    L = O.compact_letters(names, pairs)
    return all((bool(set(L[a_]) & set(L[b_]))) == (frozenset((a_, b_)) not in sigpairs) for a_, b_ in itertools.combinations(names, 2)), L
okA, LA = letters_ok(["A", "B", "C"], {frozenset("AC")})
check(okA and LA == {"A": "a", "B": "ab", "C": "b"}, f"A–C відрізняються, решта ні → {LA}")
okB, LB = letters_ok(["A", "B", "C"], set()); check(okB and set(LB.values()) == {"a"}, f"нічого не відрізняється → усі «a»: {LB}")
okC, LC = letters_ok(["A", "B", "C"], {frozenset("AB"), frozenset("AC"), frozenset("BC")}); check(okC and sorted(LC.values()) == ["a", "b", "c"], f"усі відрізняються → різні літери: {LC}")
bad = 0; rg2 = np.random.default_rng(4)
for _ in range(300):
    nm = [f"G{i}" for i in range(rg2.integers(3, 8))]
    sp = {frozenset(pr_) for pr_ in itertools.combinations(nm, 2) if rg2.random() < 0.5}
    bad += not letters_ok(nm, sp)[0]
check(bad == 0, "300 випадкових конфігурацій: спільна літера ⇔ різниця не значуща (для кожної пари)")

print("\n== 5. Опис, індекс розвитку хвороби")
d = O.describe_scores([1, 2, 2, 3, 3, 3, 4, 9])
check(d["median"] == 3.0 and d["mode"] == 3.0 and d["q1"] == 2.0 and abs(d["percent"].sum() - 100) < 1e-9 and d["n"] == 8, f"медіана 3, мода 3, Q1 2; розподіл дає 100 %")
check(abs(O.severity_index([0, 3, 9], 0, 9) - 100 * 12 / 27) < 1e-12, "McKinney 0–9: (0 + 3 + 9)/(3·9)·100 = 44,44 %")
check(abs(O.severity_index([1, 1, 1], 1, 9)) < 1e-12 and abs(O.severity_index([9, 9], 1, 9) - 100) < 1e-12 and abs(O.severity_index([1, 9], 1, 9) - 50) < 1e-12, "шкала 1–9: 1 → 0 %, 9 → 100 %, суміш 1 і 9 → 50 %")
for args, frag in [(([1, 12], 1, 9), "поза шкалою"), (([1, 2], 5, 5), "більшим")]:
    try: O.severity_index(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")

print("\n== 6. AUDPC")
r_ = O.audpc([0, 7, 14], [0, 10, 30])
check(abs(r_["audpc"] - 175.0) < 1e-12, "класичний приклад: (0+10)/2·7 + (10+30)/2·7 = 35 + 140 = 175")
check(abs(r_["raudpc"] - 175 / (30 * 14)) < 1e-12, f"відносна rAUDPC = 175/(30·14) = {r_['raudpc']:.4f}")
tt = np.array([0, 3, 10, 12, 20.0]); yy = np.array([1, 4, 9, 15, 22.0])
check(abs(O.audpc(tt, yy)["audpc"] - (getattr(np, "trapezoid", None) or np.trapz)(yy, tt)) < 1e-12, "збігається з numpy (трапеції) для нерівних інтервалів")
check(abs(O.audpc([0, 10], [50, 50], ymax=100)["raudpc"] - 0.5) < 1e-12, "стала 50 % при шкалі до 100 %: rAUDPC = 0,5")
for args, frag in [(([0], [1]), "щонайменше 2"), (([0, 5, 3], [1, 2, 3]), "зростати"), (([0, 5], [1, float("nan")]), "пропуски")]:
    try: O.audpc(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")

print("\n== 7. Розпізнавання моментів обліку")
t0, d0 = O.parse_time("01.06.2024", None); t1, d1 = O.parse_time("15.06.2024", d0)
check(O.parse_time("7")[0] == 7.0 and O.parse_time("7,5")[0] == 7.5 and t1 == 14.0 and O.parse_time("2024-06-22", d0)[0] == 21.0, "числа (з комою) й дати → дні від першого обліку")
try: O.parse_time("вчора"); check(False, "мало впасти")
except BreedingError as ex: check("вчора" in str(ex), "нерозпізнана мітка → помилка з її текстом")
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ БАЛЬНИХ ОЗНАК ПРОЙДЕНО")
