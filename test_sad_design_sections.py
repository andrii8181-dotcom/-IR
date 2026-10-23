# test_sad_design_sections.py — розділи генератора схем і кругова перевірка «шаблон → аналіз»
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import sad_design_sections as DS, sad_design_core as D, sad_mixed_sections as MS, sad_breeding_ui as U
from sad_gxe_core import BreedingError
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
def figs_ok(S, label):
    from matplotlib.figure import Figure
    import matplotlib
    m = []
    for s in S:
        if s["kind"] != "figure": continue
        fg = Figure(figsize=s["size"])
        with matplotlib.rc_context(U._RC): r = s["build"](fg)
        if r: m.append(r)
    check(not m, f"{label}: карта поля будується")
def structure_ok(S, label):
    bad = [s["title"] for s in S if s["kind"] == "table" and any(len(r) != len(s["headers"]) for r in s["rows"])]
    check(not bad, f"{label}: структура таблиць коректна")

print("== 1. Альфа-решітка")
ent = [f"N{i+1}" for i in range(48)]
S, w, lay = DS.sections_design("alpha", ent, [], k=6, r=3, seed=11)
check([s["key"] for s in S] == ["info", "layout", "template", "map", "help"], f"розділи: {[s['key'] for s in S]}")
structure_ok(S, "альфа"); figs_ok(S, "альфа")
info = {r[0]: r[1] for r in S[0]["rows"]}
check(info["Ділянок усього"] == 144 and info["Блоків у повторності"] == 8 and 0 < info["A-ефективність E"] <= 1, f"підсумок: {info['Ділянок усього']} ділянок, E = {info['A-ефективність E']:.3f}")
check(any("математична оптимальність не гарантується" in x for x in w), "про відсутність гарантії оптимальності повідомлено")
Sc, wc, layc = DS.sections_design("alpha", ent, ["St1", "St2"], k=6, r=2, seed=3)
check(len(layc) == 48 * 2 + 2 * 16 and sum(1 for t in Sc[1]["tags"] if t == "info") == 32, "зі стандартами: +2 ділянки в кожному з 16 блоків; стандарти позначені кольором")
check(max(int(r[2]) for r in Sc[1]["rows"] if (r[0], r[1]) == (1, 1)) == 8, "блок із двома стандартами має 6 + 2 = 8 ділянок")
figs_ok(Sc, "альфа зі стандартами")

print("\n== 2. Аугментована")
new = [f"N{i+1}" for i in range(50)]
Sa, wa, laya = DS.sections_design("aug", new, ["S1", "S2", "S3"], n_blocks=5, seed=2)
structure_ok(Sa, "аугментована"); figs_ok(Sa, "аугментована")
check(any("не повторюються" in x for x in wa) and Sa[0]["rows"][-2][1] == (3 - 1) * (5 - 1), "попередження про точність; df = (c−1)(b−1) = 8 у підсумку")
check(any("Ступенів свободи похибки лише 8" in x for x in wa), "df = 8 < 10 → попередження про слабкий тест")

print("\n== 3. Кругова перевірка: шаблон → дані → аналіз")
rg = np.random.default_rng(5); ent2 = [f"N{i+1}" for i in range(36)]
S3, w3, lay3 = DS.sections_design("alpha", ent2, [], k=6, r=3, seed=21)
tmpl = S3[2]["rows"]
check(all(len(r) == 5 and r[1] == "" and r[4] == "" for r in tmpl) and tmpl[0][2].startswith("R") and tmpl[0][3].startswith("B"), "шаблон: 5 стовпців, середовище й ознака порожні")
truth = {e: rg.normal(0, 1) for e in ent2}; bl = {}
rows = []
for r in tmpl:
    key = (r[2], r[3]); bl.setdefault(key, rg.normal(0, 1.5))
    rows.append([r[0], "", r[2], r[3], f"{20 + truth[r[0]] + bl[key] + rg.normal(0, 0.6):.3f}"])
Sx, wx, resx = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, rep_random=False, use_blocks=True, lrt=False, controls=[ent2[0]])
check("re" in [s["key"] for s in Sx] and "control" in [s["key"] for s in Sx], "шаблон прийнято змішаною моделлю без змін: є ефективність блоків і порівняння зі стандартом")
reff = next(s for s in Sx if s["key"] == "re")["rows"][2][1]
check(reff > 1.3, f"ефективність блоків за даними шаблону RE = {reff:.2f} (> 1)")
Sa2, _, la2 = DS.sections_design("aug", new, ["S1", "S2", "S3", "S4"], n_blocks=6, seed=9)
rows = []; bl = {}
for r in Sa2[2]["rows"]:
    bl.setdefault(r[3], rg.normal(0, 1.5)); rows.append([r[0], "", "", r[3], f"{25 + bl[r[3]] + rg.normal(0, 0.6):.3f}"])
Sy, wy, _ = MS.sections_mixed(rows, 4, "Y", "single", geno_random=False, use_blocks=True, lrt=False, controls=["S1"])
check("control" in [s["key"] for s in Sy], "шаблон аугментованої схеми теж працює як вхід аналізу")

print("\n== 4. Помилки")
for args, kw, frag in [(("alpha", [f"N{i}" for i in range(30)], []), dict(k=7, r=2), "Допустимі розміри блоку"),
                       (("alpha", ent, []), dict(k=6, r=1), "щонайменше 2 повторностей"),
                       (("aug", new, ["S1"]), dict(n_blocks=4), "щонайменше 2 стандарти")]:
    try: DS.sections_design(*args, **kw); check(False, f"{frag}: мало впасти")
    except BreedingError as ex: check(frag in str(ex), f"помилка «{frag}»")
print("\n" + "=" * 60)
if FAIL:
    print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ РОЗДІЛІВ СХЕМ ПРОЙДЕНО")
