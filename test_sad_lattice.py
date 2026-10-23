# test_sad_lattice.py — решітка й аугментована схема: від генерації до аналізу (симуляція з відомою істиною)
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sad_design_core as D, sad_mixed_core as MX, sad_mixed_sections as MS
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

def simulate_alpha(seed, sd_block=1.5, sd_noise=0.7, v=36, k=6, r=3, effects=None):
    rg = np.random.default_rng(seed); ent = [f"N{i+1}" for i in range(v)]
    d = D.alpha_design(ent, k, r, seed=seed)
    truth = rg.normal(0, 1.0, v) if effects is None else effects
    tmap = dict(zip(ent, truth)); bl = {}; repe = rg.normal(0, 0.5, r + 1); rows = []
    for x in d["layout"]:
        key = (x["rep"], x["block"])
        if key not in bl: bl[key] = rg.normal(0, sd_block)
        rows.append([x["entry"], "", f"R{x['rep']}", f"B{x['block']}", f"{20 + tmap[x['entry']] + repe[x['rep']] + bl[key] + rg.normal(0, sd_noise):.4f}"])
    return rows, ent, np.array(truth), d

def rmse_centered(lv, lm, ent, truth):
    idx = {e: i for i, e in enumerate(ent)}
    est = np.array([lm[lv.index(e)] for e in ent]); est -= est.mean(); tr = truth - truth.mean()
    return float(np.sqrt(np.mean((est - tr) ** 2)))

print("== 1. Альфа-решітка: точність скоригованих середніх (15 симуляцій)")
rl, rr, re_list = [], [], []
t0 = time.time()
for sd in range(15):
    rows, ent, truth, d = simulate_alpha(100 + sd)
    S1, w1, res1 = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, rep_random=False, use_blocks=True, lrt=False)
    S0, w0, res0 = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, rep_random=False, use_blocks=False, lrt=False)
    lv1, lm1, _ = MX.lsmeans_fixed(res1, "gen"); lv0, lm0, _ = MX.lsmeans_fixed(res0, "gen")
    rl.append(rmse_centered(lv1, lm1, ent, truth)); rr.append(rmse_centered(lv0, lm0, ent, truth))
    re_list.append(next(s for s in S1 if s["key"] == "re")["rows"][2][1])
check(np.mean(rl) < 0.8 * np.mean(rr), f"RMSE скоригованих середніх: решітка {np.mean(rl):.3f} < RCBD {np.mean(rr):.3f} (у {np.mean(rr) / np.mean(rl):.2f} раза точніше)")
check(sum(a < b for a, b in zip(rl, rr)) >= 14, f"решітка точніша в {sum(a < b for a, b in zip(rl, rr))} із 15 симуляцій")
check(np.mean(re_list) > 1.5 and min(re_list) > 1.0, f"відносна ефективність RE: середня {np.mean(re_list):.2f}, мінімум {min(re_list):.2f}")
print(f"        ({time.time() - t0:.0f} с)")
rows0, ent0, tr0, d0 = simulate_alpha(5, sd_block=0.0)
S0_, _, _ = MS.sections_mixed(rows0, 4, "Y", "single", geno_random=False, use_blocks=True, lrt=False)
re0 = next(s for s in S0_ if s["key"] == "re")["rows"][2][1]
check(0.9 < re0 < 1.1, f"без блокового ефекту RE ≈ 1 ({re0:.3f}): схема не обіцяє виграшу, якого немає")

print("\n== 2. Порівняння зі стандартом у решітці")
eff = np.zeros(36); eff[1] = 2.5; eff[2] = -2.5; eff[3] = 0.0     # N1 — стандарт (ефект 0)
rows, ent, truth, d = simulate_alpha(7, effects=eff + np.random.default_rng(0).normal(0, 0.2, 36) * 0)
S, w, res = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, rep_random=False, use_blocks=True, lrt=False, controls=["N1"])
ctl = next(s for s in S if s["key"] == "control"); vi = ctl["headers"].index("Висновок")
ver = {r_[0]: r_[vi] for r_ in ctl["rows"]}
check(ver["N2"] == "достовірно вище стандарту" and ver["N3"] == "достовірно нижче стандарту", "закладені ефекти ±2,5 виявлено")
check(sum(1 for k_, v_ in ver.items() if v_ != "не відрізняється") <= 4, f"решта номерів без ефекту переважно не позначена істотними ({sum(1 for v_ in ver.values() if v_ != 'не відрізняється')} із 35)")
check(any("внутрішньоблочні" in x for x in w), "про наближення df повідомлено")
check({s["key"] for s in S} >= {"var", "lsm", "re", "control", "rank", "forest"}, "розділи: " + ", ".join(s["key"] for s in S))

print("\n== 3. Аугментована схема: аналіз")
rg = np.random.default_rng(12); new = [f"N{i+1}" for i in range(60)]; chk = ["S1", "S2", "S3", "S4"]
g = D.augmented_design(new, chk, 6, seed=4); tr_new = {n_: rg.normal(0, 1.0) for n_ in new}; tr_new[new[0]] = 5.0; tr_new[new[1]] = -5.0
chk_eff = {"S1": 0.0, "S2": 0.5, "S3": -0.5, "S4": 0.2}; bl = {b: rg.normal(0, 1.5) for b in range(1, 7)}; rows = []
for x in g["layout"]:
    base = tr_new[x["entry"]] if x["kind"] == "новий" else chk_eff[x["entry"]]
    rows.append([x["entry"], "", "", f"B{x['block']}", f"{25 + base + bl[x['block']] + rg.normal(0, 0.6):.4f}"])
S, w, res = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, use_blocks=True, lrt=False, controls=["S1"])
lv, lm, lse = MX.lsmeans_fixed(res, "gen")
raw = {r_[0]: float(r_[4]) for r_ in rows if r_[0] in new}
est = np.array([lm[lv.index(n_)] for n_ in new]); tr = np.array([tr_new[n_] for n_ in new])
rm_adj = np.sqrt(np.mean(((est - est.mean()) - (tr - tr.mean())) ** 2)); rv = np.array([raw[n_] for n_ in new]); rm_raw = np.sqrt(np.mean(((rv - rv.mean()) - (tr - tr.mean())) ** 2))
check(rm_adj < 0.7 * rm_raw, f"скориговані значення нових номерів точніші за сирі: RMSE {rm_adj:.3f} проти {rm_raw:.3f}")
ctl = next(s for s in S if s["key"] == "control"); ver = {r_[0]: r_[ctl["headers"].index("Висновок")] for r_ in ctl["rows"]}
check(ver["N1"] == "достовірно вище стандарту" and ver["N2"] == "достовірно нижче стандарту", "закладені великі ефекти (±5) виявлено серед нових номерів")
cd = {r_[0]: r_[ctl["headers"].index("Істотна різниця Дуннетта")] for r_ in ctl["rows"]}
check(2.3 < cd["N5"] < 3.0 and cd["S2"] < cd["N5"] / 1.5, f"істотна різниця для нового номера {cd['N5']:.2f} (≈ 4·σ); для стандарту {cd['S2']:.2f} — вдвічі менша: невпорядкований номер розрізняється гірше")
check(f"df = {g['df']}" in ctl["notes"][0], f"df порівняння = (c−1)(b−1) = {g['df']} — лише за стандартами")
check(len(ctl["rows"]) == 63, "порівняння виконано для 60 нових номерів і 3 інших стандартів (63 порівняння)")
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ РЕШІТКИ Й АУГМЕНТОВАНОЇ СХЕМИ ПРОЙДЕНО")
