# test_sad_design_core.py — альфа-решітка й аугментована схема
import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sad_design_core as D
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)

print("== 1. Ефективність: еталони")
v = 12; rcbd = [list(range(v)) for _ in range(3)]
E, conn = D.a_efficiency(rcbd, v, 3)
check(conn and abs(E - 1.0) < 1e-9, f"повні блоки (RCBD): E = {E:.6f} = 1 точно")
# пряма перевірка: середня дисперсія різниці за регресією [повторність + блок + номер]
def brute_avg_var(blocks, v):
    n = sum(len(b) for b in blocks); rows = []; blk_of = []; ent_of = []
    for j, b in enumerate(blocks):
        for t in b: blk_of.append(j); ent_of.append(t)
    nb = len(blocks); X = np.zeros((n, nb + v))
    for i, (j, t) in enumerate(zip(blk_of, ent_of)): X[i, j] = 1; X[i, nb + t] = 1
    XtX = np.linalg.pinv(X.T @ X); vs = []
    for a in range(v):
        for b_ in range(a + 1, v):
            c = np.zeros(nb + v); c[nb + a] = 1; c[nb + b_] = -1; vs.append(c @ XtX @ c)
    return float(np.mean(vs))
al = D.alpha_design([f"E{i}" for i in range(12)], 4, 3, seed=1)
blk = al["blocks_idx"]
check(abs(D.pairwise_variance(blk, 12) - brute_avg_var(blk, 12)) < 1e-8, "середня дисперсія різниці за формулою 2·tr(C⁺)/(v−1) = пряма регресія з блоками і номерами")
check(abs(al["efficiency"] - (2 / 3) / D.pairwise_variance(blk, 12)) < 1e-9, "E = (2/r)/середня дисперсія різниці")
disc = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]; disc2 = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]]
E0, c0 = D.a_efficiency(disc + disc2, 12, 2)
check(not c0 and E0 == 0.0, "розірвана схема (однакові блоки в обох повторностях) розпізнана як незв'язна")

print("\n== 2. Альфа-решітка: інваріанти")
for v, k, r in ((48, 6, 3), (24, 4, 2), (100, 10, 4), (30, 5, 2)):
    ent = [f"N{i+1}" for i in range(v)]
    t0 = time.time(); d = D.alpha_design(ent, k, r, seed=7); el = time.time() - t0
    check(not D.validate_alpha(d["layout"], ent, k, r), f"v = {v}, k = {k}, r = {r}: кожна повторність — розбиття, номер ×{r}, без повторів у блоці ({el:.1f} с)")
    check(len(d["layout"]) == v * r and all(sum(1 for x in d["layout"] if x["rep"] == rp and x["block"] == b) == k for rp in range(1, r + 1) for b in range(1, v // k + 1)),
          f"   усі {r * (v // k)} блоків мають по {k} ділянок")
    rnd = D.random_blocks_efficiency(v, k, r, n=60)
    check(d["efficiency"] > rnd, f"   пошук покращує випадкове розбиття: E = {d['efficiency']:.3f} проти {rnd:.3f}")
check(0.8 < D.alpha_design([f"N{i}" for i in range(100)], 10, 4, seed=3)["efficiency"] <= 1.0, "для 100 номерів, блок 10, 4 повторності ефективність висока (> 0,8)")
a1 = D.alpha_design([f"N{i}" for i in range(24)], 4, 2, seed=5); a2 = D.alpha_design([f"N{i}" for i in range(24)], 4, 2, seed=5); a3 = D.alpha_design([f"N{i}" for i in range(24)], 4, 2, seed=6)
check(a1["layout"] == a2["layout"] and a1["layout"] != a3["layout"], "те саме зерно → та сама схема; інше → інша")
ent = [f"N{i}" for i in range(24)]
ac = D.add_checks_to_layout(a1["layout"], ["St1", "St2"], seed=2)
check(all(sum(1 for x in ac if x["rep"] == rp and x["block"] == b and x["entry"] == "St1") == 1 for rp in (1, 2) for b in range(1, 7)), "стандарт додано рівно один раз у кожен блок")
check(len(ac) == len(a1["layout"]) + 2 * 12 and all(max(x["plot"] for x in ac if (x["rep"], x["block"]) == (1, 1)) == 6 for _ in [0]), "блоки стали по 4 + 2 = 6 ділянок")

print("\n== 3. Помилки")
for args, frag in [((["A", "B", "C", "D", "E"], 2, 2), "неможливий"), ((["A", "A", "B", "C"], 2, 2), "унікальними"), (([f"N{i}" for i in range(12)], 4, 1), "щонайменше 2 повторностей"),
                   (([f"N{i}" for i in range(12)], 12, 2), "неможливий")]:
    try: D.alpha_design(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
try: D.alpha_design([f"N{i}" for i in range(30)], 7, 2)
except BreedingError as ex: check("5 (блоків 6)" in str(ex) and "6 (блоків 5)" in str(ex), "поради щодо допустимих розмірів блоку: " + str(ex).split("Допустимі розміри блоку:")[1][:70])
check(D.valid_block_sizes(36) == [(2, 18), (3, 12), (4, 9), (6, 6), (9, 4), (12, 3), (18, 2)], "дільники 36: " + str(D.valid_block_sizes(36)))

print("\n== 4. Аугментована схема")
new = [f"N{i+1}" for i in range(47)]; chk = ["S1", "S2", "S3", "S4"]
g = D.augmented_design(new, chk, 6, seed=3)
lay = g["layout"]
check(all(sum(1 for x in lay if x["block"] == b and x["entry"] == c) == 1 for b in range(1, 7) for c in chk), "кожен стандарт — рівно раз у кожному з 6 блоків")
check(sorted(x["entry"] for x in lay if x["kind"] == "новий") == sorted(new), "кожен новий номер — рівно раз")
sz = [sum(1 for x in lay if x["block"] == b and x["kind"] == "новий") for b in range(1, 7)]
check(max(sz) - min(sz) <= 1 and sum(sz) == 47, f"нові номери розподілено рівномірно: {sz}")
check(g["df"] == 3 * 5 and not any("Ступенів свободи" in w for w in g["warnings"]), "df похибки = (c−1)(b−1) = 15, без попередження про малу df")
check(any("не повторюються" in w for w in g["warnings"]), "попередження про нижчу точність невпорядкованих повторень")
gl = D.augmented_design(new, ["S1", "S2"], 3, seed=1)
check(gl["df"] == 2 and any("лише 2" in w for w in gl["warnings"]), "мало df → попередження")
for args, frag in [((new, ["S1"], 4), "щонайменше 2 стандарти"), ((new, chk, 1), "щонайменше 2 блоки"), ((new[:3], chk, 5), "менше, ніж блоків"), ((new, ["N1", "S2"], 3), "унікальними")]:
    try: D.augmented_design(*args); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ СХЕМ ПРОЙДЕНО")
