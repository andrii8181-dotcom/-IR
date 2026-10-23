# test_sad_heterosis_core.py — гетерозис: ручні розрахунки, тотожності, симуляція
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_heterosis_core as H
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

print("== 1. Ручний розрахунок (збалансований: 3 повторності, відомі середні)")
means = {"P1": 40.0, "P2": 50.0, "F1": 60.0, "F2": 48.0, "St": 45.0}
rg = np.random.default_rng(1); ent, y, blk = [], [], []
dev = rg.normal(0, 1, (5, 3)); dev -= dev.mean(axis=1, keepdims=True); dev -= dev.mean(axis=0, keepdims=True)   # ортогональні до генотипів і блоків
for gi, (nm, mu) in enumerate(means.items()):
    for k in range(3): ent.append(nm); blk.append(f"R{k+1}"); y.append(mu + dev[gi, k] + 0.0)
res = H.heterosis(ent, y, [("F1", "P1", "P2"), ("F2", "P1", "P2")], "St", blk)
a = res["rows"][0]
check(abs(a["MP"] - 45) < 1e-9 and a["BP_name"] == "P2" and abs(a["BP"] - 50) < 1e-9, "середнє батьків 45; кращий батько P2 (50)")
check(abs(a["mph_pct"] - (60 - 45) / 45 * 100) < 1e-9 and abs(a["bph_pct"] - (60 - 50) / 50 * 100) < 1e-9 and abs(a["sh_pct"] - (60 - 45) / 45 * 100) < 1e-9,
      f"MPH = 33,33 %, BPH = 20,00 %, SH = 33,33 % (є {a['mph_pct']:.2f}; {a['bph_pct']:.2f}; {a['sh_pct']:.2f})")
mse = res["mse"]; r = 3
check(abs(a["mph_se"] - math.sqrt(1.5 * mse / r)) < 1e-9 and abs(a["bph_se"] - math.sqrt(2 * mse / r)) < 1e-9 and abs(a["sh_se"] - math.sqrt(2 * mse / r)) < 1e-9,
      "SE(F₁−MP) = √(1,5·MSE/r); SE(F₁−BP) = SE(F₁−St) = √(2·MSE/r)")
check(res["df"] == 8, f"df похибки = 8 (5 генотипів × 3 повторності − 5 − 2) = {res['df']}")
b = res["rows"][1]
check(abs(b["mph_pct"] - (48 - 45) / 45 * 100) < 1e-9 and abs(b["bph_pct"] - (48 - 50) / 50 * 100) < 1e-9, "F2: MPH = +6,67 %, BPH = −4,00 % (нижче кращого батька)")
check(abs(a["mph_p"] - 2 * stats.t.sf(abs(a["mph_diff"] / a["mph_se"]), 8)) < 1e-12, "p = двобічний t-тест із df похибки")
check(res["rows"][1]["mph_p_holm"] >= res["rows"][1]["mph_p"] - 1e-12 and all(0 <= r_["mph_p_holm"] <= 1 for r_ in res["rows"]), "поправлений за Холмом p ≥ непоправленого")

print("\n== 2. Напрям добору («менше — краще»)")
rd = H.heterosis(ent, y, [("F1", "P1", "P2")], "St", blk, direction="lower")["rows"][0]
check(rd["BP_name"] == "P1" and abs(rd["BP"] - 40) < 1e-9 and abs(rd["bph_pct"] - 50.0) < 1e-9, "для «менше — краще» кращий батько — P1 (40); BPH = +50 %")
check("небажаний" in rd["mph_verdict"] or rd["mph_verdict"] == "не відрізняється", f"F₁ вищий за батьків при «менше — краще» оцінено як небажаний: «{rd['mph_verdict']}»")
ru = H.heterosis(ent, y, [("F1", "P1", "P2")], "St", blk, direction="higher")["rows"][0]
check("бажаний" in ru["bph_verdict"] and "небажаний" not in ru["bph_verdict"], f"при «більше — краще» — бажаний: «{ru['bph_verdict']}»")

print("\n== 3. Незбалансовані дані: інваріантність до параметризації")
keep = [i for i in range(len(y)) if i not in (1, 7, 12)]
e2 = [ent[i] for i in keep]; y2 = [y[i] for i in keep]; b2 = [blk[i] for i in keep]
ru2 = H.heterosis(e2, y2, [("F1", "P1", "P2")], "St", b2)["rows"][0]
lv = list(dict.fromkeys(e2)); bs = list(dict.fromkeys(b2)); lvn = [l for l in lv if l != "P1"]
X = np.column_stack([np.ones(len(y2))] + [[1.0 if e == l else 0.0 for e in e2] for l in lvn] + [[1.0 if x == b_ else 0.0 for x in b2] for b_ in bs[1:]])
bt = np.linalg.lstsq(X, np.array(y2), rcond=None)[0]; eff = {l: bt[1 + i] for i, l in enumerate(lvn)}; eff["P1"] = 0.0
d_ref = eff["F1"] - 0.5 * eff["P1"] - 0.5 * eff["P2"]
check(abs(ru2["mph_diff"] - d_ref) < 1e-8, f"різниця F₁ − MP збігається з незалежною параметризацією ({ru2['mph_diff']:.5f} = {d_ref:.5f})")

print("\n== 4. Частота хибних спрацювань при істинному «немає гетерозису» (F₁ = MP)")
sim = np.random.default_rng(5); N = 1500; rej = 0; rej_b = 0
for _ in range(N):
    e_, y_, b_ = [], [], []
    for nm, mu in (("P1", 40.0), ("P2", 50.0), ("F1", 45.0)):
        for k in range(4): e_.append(nm); b_.append(f"R{k}"); y_.append(mu + sim.normal(0, 2))
    rr = H.heterosis(e_, y_, [("F1", "P1", "P2")], None, b_)["rows"][0]
    rej += rr["mph_p"] < 0.05
check(0.035 <= rej / N <= 0.068, f"MPH: {100 * rej / N:.1f} % хибних спрацювань (номінал 5 %)")

print("\n== 5. Помилки й попередження")
base = dict(entries=ent, y=y, crosses=[("F1", "P1", "P2")], blocks=blk)
for kw, frag in [(dict(crosses=[("Х", "P1", "P2")]), "немає в таблиці"), (dict(crosses=[("F1", "P1", "P1")]), "батьки однакові"),
                 (dict(crosses=[("F1", "F1", "P2")]), "власним батьком"), (dict(crosses=[]), "жодного гібрида"),
                 (dict(crosses=[("F1", "P1", "P2"), ("F1", "P1", "P2")]), "двічі"), (dict(standard="Нема"), "Стандарту"),
                 (dict(direction="x"), "Напрям"), (dict(y=y[:-1]), "Довжини")]:
    try: H.heterosis(**{**base, **kw}); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
w2 = H.heterosis(["P1", "P2", "F1", "F1", "P1", "P2", "F1"], [1.0, 2.0, 3.0, 3.5, 1.2, 2.1, 3.2], [("F1", "P1", "P2")])
check(any("малопотужні" in x for x in w2["warnings"]), "мало df → попередження про потужність")
check(any("різна" in x for x in w2["warnings"]), "різна кількість повторностей (F₁ — 3, батьки — по 2) → попередження")
w3 = H.heterosis(["P1", "P1", "P2", "F1", "F1"], [1.0, 1.1, 2.0, 3.0, 3.2], [("F1", "P1", "P2")])
check(any("без повторностей" in x for x in w3["warnings"]), "батько без повторностей → попередження")
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ГЕТЕРОЗИСУ ПРОЙДЕНО")
