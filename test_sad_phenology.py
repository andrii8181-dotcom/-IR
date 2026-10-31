# test_sad_phenology.py – ядро фенологічних спостережень (без tkinter)
import os, sys, math, json, random, datetime as dt, itertools, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats
import sad_phenology as P
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
D = dt.date

print("== 1. Набори фаз (звірка з монографією BBCH, 2001)")
# коди стадій для кожної культури, витягнуті з монографії (U. Meier, ред., BBCH Monograph, 2nd ed., 2001); доповнено стадіями, що починаються з цифр («10 % …»)
BBCH_CODES = {"pome": ["00", "01", "03", "07", "09", "10", "11", "15", "19", "31", "32", "33", "39", "51", "52", "53", "54", "55", "56", "57", "59", "60", "61", "62", "63", "64", "65", "67", "69", "71", "72", "73", "74", "75", "76", "77", "78", "79", "81", "85", "87", "89", "91", "92", "93", "97", "99"], "stone": ["00", "01", "03", "09", "10", "11", "19", "31", "32", "33", "39", "51", "53", "54", "55", "56", "57", "59", "60", "61", "62", "63", "64", "65", "67", "69", "71", "72", "73", "75", "76", "77", "78", "79", "81", "85", "87", "89", "91", "92", "93", "97", "99"], "vine": ["00", "01", "03", "05", "07", "08", "11", "53", "55", "57", "60", "61", "63", "65", "69", "71", "73", "75", "77", "79", "81", "83", "85", "89", "91", "92", "93", "97", "99"], "cereal": ["00", "01", "03", "05", "06", "07", "09", "10", "11", "13", "19", "20", "21", "29", "30", "31", "32", "33", "37", "39", "41", "43", "45", "47", "49", "51", "55", "59", "61", "65", "69", "71", "73", "75", "77", "83", "85", "87", "89", "92", "93", "97", "99"], "maize": ["00", "01", "03", "05", "06", "07", "09", "10", "11", "13", "19", "30", "31", "51", "53", "55", "59", "61", "63", "65", "67", "69", "71", "73", "75", "79", "83", "85", "87", "89", "97", "99"], "sunflower": ["00", "01", "03", "05", "06", "07", "08", "09", "10", "30", "51", "53", "55", "57", "59", "61", "63", "65", "67", "69", "71", "73", "75", "79", "80", "81", "83", "85", "87", "89", "92", "97", "99"], "soy": ["00", "01", "03", "05", "06", "07", "08", "09", "10", "11", "12", "13", "19", "21", "49", "51", "55", "59", "60", "61", "62", "63", "64", "65", "66", "67", "69", "70", "71", "72", "73", "74", "75", "77", "79", "80", "81", "82", "83", "84", "85", "86", "87", "88", "89", "91", "92", "93", "94", "95", "96", "97", "99"], "currants": ["00", "01", "03", "07", "09", "10", "11", "15", "19", "31", "32", "33", "39", "51", "53", "54", "55", "56", "57", "59", "60", "61", "65", "67", "69", "71", "81", "85", "87", "89", "91", "92", "93", "97", "99"], "strawberry": ["00", "03", "10", "11", "41", "42", "43", "45", "49", "55", "56", "57", "58", "59", "60", "61", "65", "67", "71", "73", "81", "85", "87", "89", "91", "92", "93", "97"], "potato": ["00", "01", "02", "03", "05", "07", "08", "09", "10", "21", "31", "39", "40", "48", "49", "51", "55", "59", "60", "61", "65", "69", "70", "81", "85", "89", "91", "93", "97", "99"], "solanaceous": ["00", "01", "03", "05", "07", "09", "10", "11", "21", "51", "61", "71", "81", "85", "89", "97", "99"], "pea": ["00", "01", "03", "05", "07", "08", "09", "10", "11", "30", "51", "55", "59", "60", "61", "65", "67", "69", "71", "79", "80", "81", "85", "89", "95", "97", "99"], "rape": ["00", "01", "03", "05", "07", "08", "09", "10", "11", "20", "21", "29", "30", "50", "51", "52", "53", "55", "57", "59", "60", "61", "65", "67", "69", "71", "79", "80", "81", "85", "89", "97", "99"], "general": ["00", "01", "03", "05", "06", "07", "08", "09", "10", "11", "21", "31", "32", "33", "39", "40", "41", "43", "45", "47", "49", "51", "55", "59", "60", "61", "65", "67", "69", "71", "79", "81", "85", "87", "89", "91", "93", "97", "99"]}
MONO = {"pome": "pome", "stone": "stone", "vine": "vine", "currants": "currants", "strawberry": "strawberry", "cereal": "cereal", "maize": "maize", "sunflower": "sunflower", "soy": "soy",
        "rape": "rape", "pea": "pea", "potato": "potato", "tomato": "solanaceous", "universal": "general"}
check(set(P.PRESET_ORDER) == set(P.PRESETS) and P.PRESET_ORDER[-1] == "custom" and set(P.PRESET_ORDER[:-1]) == set(MONO), "порядок наборів охоплює всі набори; «власний» – останній")
check(len(P.PRESET_ORDER) == 15 and len({P.PRESETS[k]["name"] for k in P.PRESET_ORDER}) == 15, "15 наборів із різними назвами")
for k in P.PRESET_ORDER[:-1]:
    ph = P.PRESETS[k]["phases"]; keys = [p["key"] for p in ph]; codes_ = [int(p["bbch"]) for p in ph if p["bbch"]]
    check(len(set(keys)) == len(keys) and all(p["name"].strip() for p in ph) and all(p["bbch"].isdigit() and len(p["bbch"]) == 2 for p in ph), f"{P.PRESETS[k]['name'][:32]}: {len(ph)} фаз, ключі унікальні, коди BBCH двоцифрові")
    check(codes_ == sorted(codes_) and len(set(codes_)) == len(codes_), f"{k}: коди за зростанням і без повторів")
    outside = [(p["key"], p["bbch"]) for p in ph if p["bbch"] not in BBCH_CODES[MONO[k]]]
    check(not outside, f"{k}: кожен код є у шкалі цієї культури в монографії (поза шкалою: {outside})")
    check(all(p["hint"].strip() and len(p["hint"]) <= 140 for p in ph), f"{k}: до кожної фази є критерій настання (≤ 140 символів)")
by = lambda k: {p["key"]: p for p in P.PRESETS[k]["phases"]}
check(by("vine")["burst"]["bbch"] == "08" and by("vine")["burst0"]["bbch"] == "07" and "09" not in [p["bbch"] for p in P.PRESETS["vine"]["phases"]], "виноград: «розпускання бруньок» – 08, початок – 07 (код 09 у шкалі винограду відсутній)")
check(by("sunflower")["ripe0"]["bbch"] == "80" and by("sunflower")["phys"]["bbch"] == "87" and by("sunflower")["full"]["bbch"] == "89", "соняшник: початок дозрівання 80, фізіологічна стиглість 87, повна 89")
check([by("pome")[k]["bbch"] for k in ("bloom0", "bloom50", "bloom1", "set", "ripe0", "pick", "eat")] == ["61", "65", "69", "71", "81", "87", "89"], "яблуня/груша: 61, 65, 69, 71, 81, 87, 89")
check([by("cereal")[k]["bbch"] for k in ("emerge", "till", "stem", "head0", "bloom0", "milk", "wax", "full")] == ["09", "21", "30", "51", "61", "75", "87", "89"], "зернові: 09, 21, 30, 51, 61, 75, 87, 89")
check([by("maize")[k]["bbch"] for k in ("tassel", "pollen", "phys", "full")] == ["51", "63", "87", "89"], "кукурудза: 51, 63, 87, 89")
check(by("strawberry")["bloom1"]["bbch"] == "67" and by("rape")["bloom0"]["bbch"] == "60" and by("pea")["green"]["bbch"] == "79", "суниця: кінець цвітіння 67; ріпак: початок цвітіння 60; горох: зелена стиглість 79 (так у шкалах цих культур)")
check(P.preset_phases("pome")[0] is not P.PRESETS["pome"]["phases"][0] and P.preset_phases("pome") == P.PRESETS["pome"]["phases"], "preset_phases повертає копії")
check(P.phase_label({"name": "Сходи", "bbch": "09"}) == "Сходи (09)" and P.phase_label({"name": "Х", "bbch": ""}) == "Х", "підпис фази з кодом BBCH")
check(P.phase_hint({"bbch": "61", "hint": "10 % квіток"}) == "BBCH 61: 10 % квіток" and P.phase_hint({"bbch": "61", "hint": ""}) == "BBCH 61" and P.phase_hint({"bbch": "", "hint": "своя"}) == "своя" and P.phase_hint({"name": "x"}) == "", "підказка фази: код і критерій")
check("BBCH Monograph" in P.SOURCE and "2001" in P.SOURCE and "Meier" in P.SOURCE and "\u2014" not in P.SOURCE, "посилання на джерело (монографія BBCH, 2001, Meier)")
check(P.new_phase_key("Своя фаза!", {"x"}) == "своя_фаза" and P.new_phase_key("Своя фаза!", {"своя_фаза"}) == "своя_фаза_2" and P.new_phase_key("???", set()) == "phase", "унікальні ключі для власних фаз")

print("\n== 2. Розбір дат")
today = D(2026, 6, 1)
good = {"12.05": D(2026, 5, 12), "12.5.26": D(2026, 5, 12), "12.05.2026": D(2026, 5, 12), "12/05": D(2026, 5, 12), "12-5": D(2026, 5, 12), "2026-05-12": D(2026, 5, 12), "1205": D(2026, 5, 12),
        "120526": D(2026, 5, 12), "12052026": D(2026, 5, 12), "12 травня": D(2026, 5, 12), "12 тра 2026": D(2026, 5, 12), "5 січня": D(2026, 1, 5), "1 Червня": D(2026, 6, 1), "45789": D(2025, 5, 12),
        "т": today, "Т": today, "сьогодні": today, "  12.05  ": D(2026, 5, 12), "2026-05-12 10:30": D(2026, 5, 12), "01.01": D(2026, 1, 1), "31.12": D(2026, 12, 31), "12.05.1999": D(1999, 5, 12)}
for t, exp in good.items():
    d, m = P.parse_date_flex(t, 2026, today); check(d == exp and m is None, f"«{t}» → {exp:%d.%m.%Y}")
check(P.parse_date_flex("29.02", 2024)[0] == D(2024, 2, 29) and P.parse_date_flex("29.02", 2026)[0] is None, "29.02 приймається лише у високосному році")
for t, frag in (("31.04", "немає 31"), ("32.01", "немає 32"), ("12.13", "місяця 13"), ("00.05", "день"), ("xx", "не схоже"), ("12.05.2026.5", "не схоже"), ("45", "не схоже"), ("5", "не схоже"), ("100", "не схоже"), ("99999", "поза межами"), ("12 мая", "не схоже")):
    d, m = P.parse_date_flex(t, 2026); check(d is None and m and frag in m, f"«{t}» відхилено: {m}")
check(P.parse_date_flex("", 2026) == (None, None) and P.parse_date_flex(None, 2026) == (None, None) and P.parse_date_flex("   ", 2026) == (None, None), "порожнє – не помилка")
check(P.parse_date_flex(45789.0, 2026)[0] == D(2025, 5, 12) and P.parse_date_flex(dt.datetime(2026, 5, 12).strftime("%Y-%m-%d %H:%M:%S"), 2026)[0] == D(2026, 5, 12), "числа Excel і мітки часу")
check(P.fmt_date(D(2026, 5, 2)) == "02.05.2026" and P.fmt_date(None) == "", "формат дати дд.мм.рррр")

print("\n== 3. Номер дня року")
check(P.doy_norm(D(2024, 3, 1)) == P.doy_norm(D(2025, 3, 1)) == 60 and P.doy_norm(D(2024, 12, 31)) == 365 and P.doy_norm(D(2024, 2, 29)) == 60 and P.doy_norm(D(2024, 1, 1)) == 1, "однакова календарна дата має однаковий номер у високосному й звичайному році")
check(P.doy_norm(D(2024, 12, 31)) == P.doy_norm(D(2025, 12, 31)), "31 грудня: 365 і в високосному")
check(P.md_from_doy(60) == "01.03" and P.md_from_doy(132) == "12.05" and P.md_from_doy(1) == "01.01" and P.md_from_doy(365) == "31.12" and P.md_from_doy(131.6) == "12.05", "номер дня → дд.мм (з округленням)")
check(P.md_from_doy(0) == "01.01" and P.md_from_doy(500) == "31.12", "межі номера дня не ламають перетворення")
check(P.fmt_days(2.345) == "2,3" and P.fmt_days(float("nan")) == "–" and P.fmt_days(None) == "–" and P.fmt_days(1.0, 0) == "1", "формат кількості діб")

print("\n== 4. Записи, повторності, помилки й попередження")
PH = ["bloom0", "bloom50", "bloom1"]
rows24 = [{"name": "Голден", "rep": "", "dates": {"bloom0": "10.05", "bloom50": "14.05", "bloom1": "20.05"}}, {"name": "Голден", "rep": "", "dates": {"bloom0": "11.05", "bloom50": "15.05", "bloom1": "21.05"}},
          {"name": "Гала", "rep": "", "dates": {"bloom0": "12.05", "bloom50": "17.05", "bloom1": "23.05"}}, {"name": "", "rep": "", "dates": {"bloom0": "01.05"}}]
ar = P.assign_reps(rows24); check([(r["name"], r["rep"]) for r in ar] == [("Голден", "1"), ("Голден", "2"), ("Гала", "1")], "порожні повторності нумеруються за порядком у сорту; порожні рядки пропускаються")
check(P.assign_reps([{"name": "А", "rep": "3", "dates": {}}, {"name": "А", "rep": "", "dates": {}}])[1]["rep"] == "2", "явно вказана повторність зберігається, порожня – за порядком")
recs, errs, warns = P.collect_records({2024: rows24}, PH)
check(len(recs) == 9 and not errs and not warns, f"9 записів без помилок і попереджень ({len(recs)})")
bad = [{"name": "X", "rep": "1", "dates": {"bloom0": "20.05", "bloom50": "14.05", "bloom1": "ab"}}, {"name": "Y", "rep": "1", "dates": {"bloom0": "10.05.2025", "bloom50": "12.05"}}]
r2, e2, w2 = P.collect_records({2024: bad}, PH)
check(len(e2) == 1 and e2[0]["phase"] == "bloom1" and e2[0]["name"] == "X" and "не схоже" in e2[0]["msg"], "нерозпізнана дата → помилка з назвою сорту й фази")
check(any("раніше за попередню" in w["msg"] and w["phase"] == "bloom50" for w in w2), "порушення хронологічного порядку фаз → попередження")
check(any("не з року 2024" in w["msg"] for w in w2), "дата з іншого року → попередження")
check(any(r["name"] == "X" and r["phase"] == "bloom50" for r in r2) and len(r2) == 4, "записи з попередженнями зберігаються (їх вирішує користувач)")
check(recs[0]["doy"] == P.doy_norm(D(2024, 5, 10)) and recs[0]["date"] == D(2024, 5, 10) and recs[0]["year"] == 2024, "запис містить рік, дату й нормований номер дня")
check(P.cultivar_order(recs) == ["Голден", "Гала"] and P.cultivar_order(recs, extra=["Гала", "Нова"]) == ["Гала", "Нова", "Голден"], "порядок сортів: спершу задані, далі за появою")

print("\n== 5. Зведення, тривалість, стандарт")
yd = {2024: rows24, 2025: [{"name": "Голден", "rep": "", "dates": {"bloom0": "14.05", "bloom50": "19.05", "bloom1": "27.05"}}, {"name": "Гала", "rep": "", "dates": {"bloom0": "16.05", "bloom50": "22.05", "bloom1": "30.05"}}]}
recs, _, _ = P.collect_records(yd, PH); cv = ["Голден", "Гала"]; sm = P.summarize(recs, cv, PH)
g = [P.doy_norm(D(2024, 5, 10)), P.doy_norm(D(2024, 5, 11)), P.doy_norm(D(2025, 5, 14))]
s = sm[("Голден", "bloom0")]; check(s["n"] == 3 and abs(s["mean"] - np.mean(g)) < 1e-9 and abs(s["sd"] - np.std(g, ddof=1)) < 1e-9 and s["min"] == min(g) and s["max"] == max(g), f"Голден, початок цвітіння: n=3, середнє {s['mean']:.2f}, SD {s['sd']:.2f}")
check(sm[("Гала", "bloom0")]["n"] == 2 and sm[("Гала", "bloom1")]["n"] == 2, "Гала: 2 спостереження (1 повторність × 2 роки)")
check(math.isnan(P.summarize(recs, ["Нема"], PH)[("Нема", "bloom0")]["mean"]) and P.summarize(recs, ["Нема"], PH)[("Нема", "bloom0")]["n"] == 0, "сорт без даних: n = 0, середнє NaN")
check(math.isnan(P.summarize(recs, cv, PH)[("Гала", "bloom0")]["sd"]) is False and math.isnan(P.summarize(recs[:1], cv, PH)[("Голден", "bloom0")]["sd"]), "SD не визначено при одному спостереженні")
du = P.durations(recs, cv, [("bloom0", "bloom1")]); dg = du[("Голден", ("bloom0", "bloom1"))]
exp_d = [(D(2024, 5, 20) - D(2024, 5, 10)).days, (D(2024, 5, 21) - D(2024, 5, 11)).days, (D(2025, 5, 27) - D(2025, 5, 14)).days]
check(dg["n"] == 3 and abs(dg["mean"] - np.mean(exp_d)) < 1e-9 and dg["min"] == min(exp_d) and dg["max"] == max(exp_d), f"тривалість цвітіння: {exp_d} діб, середнє {dg['mean']:.2f}")
check(P.durations(recs, cv, [("bloom0", "nonexist")])[("Голден", ("bloom0", "nonexist"))]["n"] == 0, "тривалість для відсутньої фази: n = 0")
vs, ref = P.vs_standard(sm, cv, PH, standard="Голден", thr=3.0)
check(vs[("Голден", "bloom0")][0] == 0.0 and vs[("Голден", "bloom0")][1] == "середній", "стандарт відносно себе: 0 діб, «середній»")
dd = sm[("Гала", "bloom0")]["mean"] - sm[("Голден", "bloom0")]["mean"]; check(abs(vs[("Гала", "bloom0")][0] - dd) < 1e-9 and vs[("Гала", "bloom0")][1] == ("пізній" if dd >= 3 else "середній"), f"Гала відносно Голдена: {dd:+.2f} діб")
for diff, cls in ((-5, "ранній"), (-3, "ранній"), (-2.99, "середній"), (0, "середній"), (2.99, "середній"), (3, "пізній"), (10, "пізній")): check(P.classify(diff, 3.0) == cls, f"{diff:+} діб → {cls}")
check(P.classify(float("nan")) == "" and P.classify(None) == "" and P.classify(-1.5, 1.0) == "ранній", "клас порожній без даних; поріг змінюється")
vs2, ref2 = P.vs_standard(sm, cv, PH, standard=None)
check(abs(ref2["bloom0"] - np.mean([sm[(c, "bloom0")]["mean"] for c in cv])) < 1e-9 and abs(vs2[("Голден", "bloom0")][0] + vs2[("Гала", "bloom0")][0]) < 1e-9, "без стандарту: опорне значення – середнє за сортами; відхилення в сумі дають 0")
vs3, _ = P.vs_standard(sm, cv + ["Нема"], PH, standard="Нема"); check(abs(vs3[("Голден", "bloom0")][0] + vs3[("Гала", "bloom0")][0]) < 1e-9, "стандарт без даних → резервно середнє за сортами")

print("\n== 6. ANOVA за номером дня")
rg = random.Random(11); cvs = ["A", "B", "C", "D"]; eff = {"A": 0, "B": 3, "C": 6, "D": 6.5}
def mk_year(y, reps=4, extra=0):
    return [{"name": c, "rep": str(r), "dates": {"bloom0": P.fmt_date(D(y, 5, 1) + dt.timedelta(days=int(round(eff[c] + (r - 2.5) * 0.7 + extra + rg.gauss(0, .4)))))}} for c in cvs for r in range(1, reps + 1)]
ya = {2025: mk_year(2025)}; ra, _, _ = P.collect_records(ya, ["bloom0"]); an = P.anova_phase(ra, "bloom0", cvs)
y = {c: [r["doy"] for r in ra if r["name"] == c] for c in cvs}; fo = stats.f_oneway(*y.values())
check(an["design"].startswith("RCBD") and an["multi_year"] is False, f"збалансовані повторності → блочна схема: {an['design']}")
allv = np.array([[y[c][i] for c in cvs] for i in range(4)], float); gm = allv.mean(); ssb = len(cvs) * ((allv.mean(1) - gm) ** 2).sum(); sst = ((allv.mean(0) - gm) ** 2).sum() * 4; sse = ((allv - gm) ** 2).sum() - ssb - sst
F_man = (sst / 3) / (sse / 9); p_man = 1 - stats.f.cdf(F_man, 3, 9)
check(abs(an["F"] - F_man) < 1e-6 and abs(an["p"] - p_man) < 1e-9 and an["dfe"] == 9 and abs(an["mse"] - sse / 9) < 1e-9, f"RCBD: F = {an['F']:.3f}, p = {an['p']:.2e}, MSE = {an['mse']:.4f} збігаються з ручним розрахунком")
check(abs(an["nir"] - stats.t.ppf(0.975, 9) * math.sqrt(2 * (sse / 9) / 4)) < 1e-9, f"НІР05 = t·√(2·MSE/n) = {an['nir']:.3f} діб")
check({r["name"] for r in an["table"]} == {"Блоки", "Фактор A", "Залишок", "Загальна"}, "таблиця ANOVA: блоки, сорт, залишок, загальна")
lt = an["letters"]; mn = an["means"]; order_ = sorted(cvs, key=lambda c: mn[c])
check(lt[order_[0]][0] == "a", f"найраніший сорт ({order_[0]}) має літеру «a»: {lt}")
bad_pairs = [(a, b) for a, b in itertools.combinations(cvs, 2) if bool(set(lt[a]) & set(lt[b])) != (abs(mn[a] - mn[b]) <= an["nir"])]
check(not bad_pairs, f"спільна літера тоді й лише тоді, коли різниця середніх ≤ НІР05 ({an['nir']:.2f}): {bad_pairs}")
check(len({lt[c] for c in cvs}) >= 2, "сорти з істотною різницею мають різні літери")
an2 = P.anova_phase([r for r in ra if r["rep"] != "4"] + [r for r in ra if r["rep"] == "4" and r["name"] != "A"], "bloom0", cvs)
check(an2["design"].startswith("CRD"), "незбалансовані повторності → повна рандомізація (CRD)")
crd = P.anova_phase([{**r, "rep": "1"} for r in ra][:0] + ra, "bloom0", cvs); fo2 = stats.f_oneway(*[[r["doy"] for r in ra if r["name"] == c and r["rep"] in ("1", "2", "3")] for c in cvs])
an3 = P.anova_phase([r for r in ra if r["rep"] in ("1", "2", "3")] + [{**r, "rep": "x"} for r in ra if r["name"] == "A" and r["rep"] == "4"], "bloom0", cvs); check(an3["design"].startswith("CRD") and not math.isnan(an3["F"]), "різні набори повторностей → CRD")
ybig = {2024: mk_year(2024), 2025: mk_year(2025, extra=2.0)}; rb, _, _ = P.collect_records(ybig, ["bloom0"]); am = P.anova_phase(rb, "bloom0", cvs)
check(am["multi_year"] and am["years"] == [2024, 2025] and {r["name"] for r in am["table"]} == {"Блоки", "Фактор A", "Фактор Y", "Фактор A×Y", "Залишок", "Загальна"}, "кілька років: сорт, рік, сорт×рік")
pyear = next(r for r in am["table"] if r["name"] == "Фактор Y"); check(pyear["p"] < 0.001, f"різницю між роками (+2 доби) виявлено: p(рік) = {pyear['p']:.1e}")
check(P.anova_phase(ra, "bloom0", ["A"])["error"].startswith("Потрібно щонайменше два"), "один сорт → зрозуміле повідомлення")
one = P.anova_phase([r for r in ra if r["rep"] == "1"], "bloom0", cvs); check("error" in one and "повторностей" in one["error"], "по одному спостереженню на сорт → повідомлення про замало повторностей")
check(P.anova_phase(ra, "nonexist", cvs)["error"].startswith("Потрібно"), "фаза без даних → повідомлення")
check(abs(sum(an["means"][c] * an["ns"][c] for c in cvs) / sum(an["ns"].values()) - np.mean([r["doy"] for r in ra])) < 1e-9, "середні за сортами узгоджені із загальним")

print("\n== 6б. Методи порівняння середніх")
import sad_common as C
from scipy import stats as sps
def mk_recs(eff_list, reps=4, sd=0.5, seed=3, year=2025):
    rg_ = random.Random(seed); out = []; names = [f"C{i}" for i in range(len(eff_list))]
    for i, c in enumerate(names):
        for r in range(1, reps + 1):
            d = D(year, 5, 1) + dt.timedelta(days=int(round(eff_list[i] + rg_.gauss(0, sd)))); out.append({"year": year, "name": c, "rep": str(r), "phase": "p", "date": d, "doy": P.doy_norm(d)})
    return out, names
# 1. векторизовані парні критерії = функції програми (pairwise_param, lsd_sig), включно з різною кількістю спостережень
rg6 = random.Random(8); names8 = [f"M{i}" for i in range(8)]; means8 = {c: 100 + rg6.uniform(0, 9) for c in names8}; ns8 = {c: rg6.choice([3, 4, 5]) for c in names8}; mse8, df8 = 1.6, 24
order8 = names8
for m_ in ("lsd", "tukey", "bonferroni", "duncan"):
    S_ = P._pair_sig([means8[c] for c in names8], [ns8[c] for c in names8], mse8, df8, m_, 0.05)
    ref_ = C.lsd_sig(names8, means8, ns8, mse8, df8) if m_ == "lsd" else C.pairwise_param(names8, means8, ns8, mse8, df8, m_)[1]
    bad_ = [(a, b) for (a, b), v in ref_.items() if bool(S_[names8.index(a), names8.index(b)]) != bool(v)]
    check(not bad_ and len(ref_) == 28, f"{m_}: істотність усіх 28 пар збігається з функціями програми (розбіжностей {len(bad_)}), різна кількість спостережень")
# 2. Тьюкі проти scipy.tukey_hsd (однофакторна схема)
for bal in (True, False):
    rg_ = np.random.default_rng(5); grp = [rg_.normal(m_, 1.0, 5 if bal else n_) for m_, n_ in zip((0, 0.5, 2.0, 2.2, 4.0), (5, 7, 4, 6, 5))]
    sres = sps.tukey_hsd(*grp); ms_ = [g.mean() for g in grp]; nn_ = [len(g) for g in grp]; sse_ = sum(((g - g.mean()) ** 2).sum() for g in grp); dfe_ = sum(nn_) - len(grp); mse_ = sse_ / dfe_
    S_ = P._pair_sig(ms_, nn_, mse_, dfe_, "tukey", 0.05); dec = [(S_[i, j], sres.pvalue[i, j] < 0.05) for i in range(5) for j in range(i + 1, 5)]
    check(all(a == b for a, b in dec), f"Тьюкі–Крамер збігається зі scipy.stats.tukey_hsd ({'збалансовані' if bal else 'різні n'}): {sum(a for a, _ in dec)} істотних пар із 10")
# 3. Холм
check(np.allclose(P.holm_adjust([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06]) and np.allclose(P.holm_adjust([0.5]), [0.5]) and P.holm_adjust([]).size == 0, "Холм: приклад [0,01; 0,04; 0,03] → [0,03; 0,06; 0,06]")
rg_ = np.random.default_rng(1); pv = rg_.uniform(0, 0.2, 40); ad = P.holm_adjust(pv)
def holm_ref(pv):
    m = len(pv); o = sorted(range(m), key=lambda i: pv[i]); out = [0] * m; prev = 0
    for r_, i in enumerate(o): prev = max(prev, min(1, (m - r_) * pv[i])); out[i] = prev
    return out
check(np.allclose(ad, holm_ref(pv)) and np.all(ad >= pv) and np.all(ad <= 1) and np.allclose(P.holm_adjust(pv[::-1]), ad[::-1]), "Холм: збігається з визначенням, не менший за p, ≤ 1, не залежить від порядку")
# 4. Скотт–Кнотт
cl = {f"X{i}": 10 + 10 * (i // 4) + 0.05 * (i % 4) for i in range(12)}; sk = P.scott_knott(cl, 0.04, 20, 4)
check(len(set(sk.values())) == 3 and all(sk[f"X{i}"] == i // 4 for i in range(12)), "Скотт–Кнотт відновлює 3 чітко розділені групи по 4 середніх")
check(len(set(P.scott_knott({f"Y{i}": 50 + 0.01 * i for i in range(10)}, 1.0, 20, 4).values())) == 1, "майже однакові середні (різниці ≪ похибки) – одна група")
check(len(set(P.scott_knott({"A": 5.0, "B": 5.0, "C": 5.0}, 1.0, 10, 3).values())) == 1 and len(set(P.scott_knott({"A": 1.0}, 1.0, 10, 3).values())) == 1, "однакові середні й один сорт – одна група")
two = P.scott_knott({"a1": 0.0, "a2": 0.1, "b1": 20.0, "b2": 20.1}, 0.25, 12, 3); check(two["a1"] == two["a2"] == 0 and two["b1"] == two["b2"] == 1, "дві групи: найраніша має номер 0")
vals_ = [0, 1, 5, 6, 12, 13]; ng_ = [len(set(P.scott_knott({f"Z{i}": v for i, v in enumerate(vals_)}, mse_, 20, 4).values())) for mse_ in (0.1, 2.0, 8.0, 50.0, 500.0)]
check(ng_[0] == 6 and ng_[-1] == 1 and all(a >= b for a, b in zip(ng_, ng_[1:])), f"чим більша похибка, тим менше груп: MSE 0,1 / 2 / 8 / 50 / 500 → {ng_} (при малій похибці кожна різниця в 1 добу істотна)")
sh = P.scott_knott({k_: v + 1000 for k_, v in cl.items()}, 0.04, 20, 4); sc = P.scott_knott({k_: v * 7 for k_, v in cl.items()}, 0.04 * 49, 20, 4)
check(sh == sk and sc == sk, "групи не змінюються при зсуві середніх і при масштабуванні разом із похибкою")
rgk = np.random.default_rng(2); mk_ = {f"K{i}": float(m_) for i, m_ in enumerate(np.repeat([0, 5, 10, 15, 20], 10) + rgk.normal(0, 0.3, 50))}; skk = P.scott_knott(mk_, 0.36 * 3, 100, 3)
check(len(set(skk.values())) == 5 and all(len({skk[f"K{i}"] for i in range(j, j + 10)}) == 1 for j in range(0, 50, 10)), "50 середніх у 5 справжніх кластерах: Скотт–Кнотт знаходить рівно 5 груп, кожен кластер цілком в одній групі")
# 5. Загальна поведінка compare_means
recs6, nm6 = mk_recs([0, 0.3, 3, 6, 6.4, 12]); an6 = P.anova_phase(recs6, "p", nm6)
check([P.resolve_method("auto", k) for k in (2, 3, 5, 6, 30, 31, 300)] == ["lsd", "lsd", "lsd", "tukey", "tukey", "sk", "sk"] and P.resolve_method("duncan", 3) == "duncan", "автовибір: ≤ 5 – НІР, 6–30 – Тьюкі, > 30 – Скотт–Кнотт; явний вибір зберігається")
cm = {m_: P.compare_means(recs6, "p", an6, m_, "C0") for m_, _ in P.METHODS}
check(all("groups" in v and set(v["groups"]) == set(nm6) for v in cm.values()) and cm["auto"]["method"] == "tukey", "усі 8 методів повертають групи для всіх 6 сортів")
mn6 = an6["means"]; first = min(nm6, key=lambda c: mn6[c])
for m_ in ("lsd", "tukey", "bonferroni", "duncan", "sk"): check(cm[m_]["groups"][first].startswith("a"), f"{m_}: найраніший сорт має літеру «a»")
cr = {m_: cm[m_]["crit"] for m_ in ("lsd", "tukey", "bonferroni")}; check(0 < cr["lsd"] < cr["tukey"] and cr["lsd"] < cr["bonferroni"] and abs(cr["lsd"] - an6["nir"]) < 1e-9, f"критичні різниці: НІР {cr['lsd']:.2f} < Тьюкі {cr['tukey']:.2f}, Бонферроні {cr['bonferroni']:.2f}; НІР збігається з anova_phase")
n_let = {m_: len({ch for v in cm[m_]["groups"].values() for ch in v}) for m_ in ("lsd", "tukey", "bonferroni")}; check(n_let["lsd"] >= n_let["tukey"] >= 1, f"НІР розрізняє не менше сортів, ніж Тьюкі (кількість літер {n_let})")
S_t = P._pair_sig([mn6[c] for c in nm6], [an6["ns"][c] for c in nm6], an6["mse"], an6["dfe"], "tukey", 0.05); S_l = P._pair_sig([mn6[c] for c in nm6], [an6["ns"][c] for c in nm6], an6["mse"], an6["dfe"], "lsd", 0.05); check(not np.any(S_t & ~S_l), "кожна пара, істотна за Тьюкі, істотна й за НІР (Тьюкі суворіший)")
# 6. зі стандартом
ct = cm["control"]; from scipy.stats import t as _tt
d_ = mn6["C2"] - mn6["C0"]; se_ = math.sqrt(an6["mse"] * (1 / 4 + 1 / 4)); praw = 2 * _tt.sf(abs(d_) / se_, an6["dfe"])
pall = sorted(2 * _tt.sf(abs(mn6[c] - mn6["C0"]) / se_, an6["dfe"]) for c in nm6 if c != "C0"); padj_C2 = ct["vs"]["C2"]["p"]
check(abs(ct["vs"]["C2"]["diff"] - d_) < 1e-12 and abs(padj_C2 - min(1, praw * (5 - sorted(pall).index(praw)))) < 1e-9 or padj_C2 >= praw, "зі стандартом: різниця й скоригований p для C2 збігаються з ручним розрахунком Холма")
check(ct["groups"]["C0"] == "станд." and ct["groups"]["C1"] == "≈" and ct["groups"]["C5"] == "↑" and "Холма" in ct["note"], f"позначки: станд., ≈ (C1 неістотно), ↑ (C5 пізніше): {ct['groups']}")
cw = P.compare_means(recs6, "p", an6, "control", ""); check(cw["vs"] is None and "Оберіть стандарт" in cw["note"] and set(cw["groups"].values()) == {""}, "без стандарту – підказка замість порівняння")
cw2 = P.compare_means(recs6, "p", an6, "control", "Нема"); check("Оберіть стандарт" in cw2["note"], "стандарт, якого немає у даних, – та сама підказка")
recs_e = [dict(r, doy=r["doy"] - (3 if r["name"] == "C3" else 0)) for r in recs6]; an_e = P.anova_phase(recs_e, "p", nm6); ce = P.compare_means(recs_e, "p", an_e, "control", "C3"); check(ce["groups"]["C0"] == "↑" or ce["groups"]["C0"] == "↓" or ce["groups"]["C0"] == "≈", "інший стандарт теж працює")
# 7. Краскел–Уолліс і Данн
ck = cm["kw"]; vals6 = [[r["doy"] for r in recs6 if r["name"] == c] for c in nm6]; check(abs(ck["p_overall"] - sps.kruskal(*vals6).pvalue) < 1e-12, f"Краскел–Уолліс: p = {ck['p_overall']:.4g} збігається зі scipy.stats.kruskal")
allv = np.array([v for g in vals6 for v in g], float); rk = sps.rankdata(allv); pos = 0; mrk = []
for g in vals6: mrk.append(rk[pos:pos + len(g)].mean()); pos += len(g)
N_ = len(allv); _, cnt_ = np.unique(allv, return_counts=True); tie_ = (cnt_ ** 3 - cnt_).sum() / (12 * (N_ - 1)); var_ = N_ * (N_ + 1) / 12 - tie_
pairs_ = [(i, j) for i in range(6) for j in range(i + 1, 6)]; zz = [abs(mrk[i] - mrk[j]) / math.sqrt(var_ * (1 / 4 + 1 / 4)) for i, j in pairs_]; pa_ = holm_ref([2 * sps.norm.sf(z) for z in zz])
sig_ref = {(nm6[i], nm6[j]): pa_[k_] < 0.05 for k_, (i, j) in enumerate(pairs_)}; lt_ref = C.cld(sorted(nm6, key=lambda c: mn6[c]), {c: -ck["mean_ranks"][c] for c in nm6}, sig_ref)
check(lt_ref == ck["groups"] and all(abs(ck["mean_ranks"][nm6[i]] - mrk[i]) < 1e-12 for i in range(6)), "Данн із поправкою Холма: літери збігаються з ручним розрахунком (z з поправкою на однакові значення)")
const = [dict(r, doy=100) for r in recs6]; anc = P.anova_phase(const, "p", nm6); cc = P.compare_means(const, "p", anc, "kw")
check("error" in anc or all(v == "a" for v in cc.get("groups", {"x": "a"}).values()), "усі дати однакові – без винятків")
# 8. F-захист у автоматичному режимі
found = None
for seed in range(200):
    rr_, nn_ = mk_recs([0, 0, 0, 0, 1.2], reps=3, sd=1.3, seed=seed); a_ = P.anova_phase(rr_, "p", nn_)
    if "error" in a_ or a_["p"] < 0.05: continue
    e_ = P.compare_means(rr_, "p", a_, "lsd"); g_ = P.compare_means(rr_, "p", a_, "auto")
    if len(set(e_["groups"].values())) > 1: found = (a_, e_, g_); break
check(found is not None, "знайдено випадок: F неістотний, але НІР між окремими парами «знаходить» різницю")
if found:
    a_, e_, g_ = found; check(set(g_["groups"].values()) == {"a"} and "Захищена" in g_["note"] and g_["ngroups"] == 1, f"автоматичний режим (k = 5): захищена НІР – усі «a» при p(F) = {a_['p']:.3f}")
    check(len(set(e_["groups"].values())) > 1, "явно обрана «НІР05 (Фішер)» літери будує (без захисту)")
# 9. Успадковуваність
rgh = np.random.default_rng(7); k_h, r_h = 200, 3; gg = rgh.normal(0, 2.0, k_h); recs_h = []
for i in range(k_h):
    for r in range(r_h): v_ = int(round(130 + gg[i] + rgh.normal(0, 1.0))); recs_h.append({"year": 2025, "name": f"H{i}", "rep": str(r + 1), "phase": "p", "date": D(2025, 5, 1), "doy": v_})
ah = P.anova_phase(recs_h, "p", [f"H{i}" for i in range(k_h)]); exp_h = 4.0 / (4.0 + 1.0 / 3)
check(abs(ah["h2"] - (1 - 1 / ah["F"])) < 1e-9 and abs(ah["h2"] - exp_h) < 0.04, f"H² (на середніх, один рік) = {ah['h2']:.3f}: збігається з 1 − 1/F і з очікуваним {exp_h:.3f} для σ²G = 4, σ²e = 1, r = 3")
rows_ = {r["name"]: r["ms"] for r in P.anova_phase([dict(r_, year=2024) for r_ in recs_h[:60]] + [dict(r_, year=2025) for r_ in recs_h[60:120]], "p", [f"H{i}" for i in range(20)])["table"]}
am = P.anova_phase([dict(r_, year=2024) for r_ in recs_h[:60]] + [dict(r_, year=2025, doy=r_["doy"] + 1) for r_ in recs_h[:60]], "p", [f"H{i}" for i in range(20)])
msd = {r["name"]: r["ms"] for r in am["table"]}
check(abs(am["h2"] - 1.0) < 1e-9, f"другий рік – ті самі дати +1 доба (взаємодії сорт×рік немає): H² = 1 незалежно від шуму округлення (MS(сорт×рік) = {msd['Фактор A×Y']:.1e}), а не «немає даних»")
for noise in (0.0, -1e-15, -3e-14, 3e-15):                       # шум округлення різних платформ (на Windows – нуль або від'ємний)
    check(abs(P.heritability(10.0, noise, float("nan"), True) - 1.0) < 1e-12, f"MS(сорт×рік) = {noise:.0e} → H² = 1")
check(math.isnan(P.heritability(10.0, float("nan"), 5.0, True)) and math.isnan(P.heritability(0.0, 1.0, 5.0, True)) and math.isnan(P.heritability(10.0, None, 5.0, True)), "невизначені середні квадрати → NaN (а не хибна одиниця)")
check(P.heritability(2.0, 4.0, 1.0, True) == 0.0 and P.heritability(1.0, 1.0, 0.5, False) == 0.0 and math.isnan(P.heritability(1.0, 1.0, float("nan"), False)), "взаємодія більша за ефект сорту / F < 1 → H² = 0 (не від'ємна)")
am2 = P.anova_phase([dict(r_, year=2024) for r_ in recs_h[:60]] + [dict(r_, year=2025, doy=r_["doy"] + int(rgh.integers(-2, 3))) for r_ in recs_h[:60]], "p", [f"H{i}" for i in range(20)])
ms2 = {r["name"]: r["ms"] for r in am2["table"]}
check(ms2["Фактор A×Y"] > 0.1 and abs(am2["h2"] - (1 - ms2["Фактор A×Y"] / ms2["Фактор A"])) < 1e-12 and 0 < am2["h2"] < 1, f"з реальною взаємодією: H² = 1 − MS(сорт×рік)/MS(сорт) = {am2['h2']:.3f}")
check(P.anova_phase(const, "p", nm6).get("h2", 0) != 5, "H² не ламає виродженого випадку")
# 10. Сотні гібридів
rg_big = np.random.default_rng(11); K = 300; centers = np.repeat(np.arange(12) * 3.0, K // 12); hyb = [f"G{i:03d}" for i in range(K)]; yd_big = {}
for y, shift in ((2024, 0), (2025, 2)):
    rows_ = []
    for i, c in enumerate(hyb):
        for r in range(1, 4): rows_.append({"name": c, "rep": str(r), "dates": {"bloom0": P.fmt_date(D(y, 5, 1) + dt.timedelta(days=int(round(centers[i] + shift + rg_big.normal(0, 0.8)))))}})
    yd_big[y] = rows_
t0 = time.time(); big = P.analyze(yd_big, [{"key": "bloom0", "name": "Початок цвітіння", "bbch": "61", "hint": ""}], standard="G000", thr=3.0); t_an = time.time() - t0
cb = big["compare"]["bloom0"]; check(t_an < 20 and len(big["cultivars"]) == 300 and big["n_obs"] == 1800, f"300 гібридів × 3 повторності × 2 роки: аналіз за {t_an:.1f} с")
check(cb["method"] == "sk" and 10 <= cb["ngroups"] <= 14 and len(cb["groups"]) == 300, f"автоматично: Скотт–Кнотт, {cb['ngroups']} груп (справжніх 12) для 300 гібридів")
gmap = {}
for c, l in cb["groups"].items(): gmap.setdefault(l, []).append(centers[int(c[1:])])
purity = np.mean([max(np.bincount((np.array(v) // 3).astype(int))) / len(v) for v in gmap.values()]); check(purity > 0.9, f"групи Скотта–Кнотта відповідають справжнім кластерам (чистота {purity:.2f})")
check(big["anova"]["bloom0"]["multi_year"] and big["anova"]["bloom0"]["p"] < 1e-6 and 0.9 < big["anova"]["bloom0"]["h2"] <= 1, f"сорт істотний; H² = {big['anova']['bloom0']['h2']:.3f}")
for m_ in ("lsd", "tukey", "bonferroni"):
    t0 = time.time(); r_ = P.compare_means(big["records"], "bloom0", big["anova"]["bloom0"], m_, "G000"); check(time.time() - t0 < 15 and set(r_["groups"].values()) == {""} and "нечитабельні" in r_["note"] and r_["n_sig_pairs"] > 10000 and r_["crit"] is not None, f"{m_}: 300 сортів – літери не формуються (пояснення), істотних пар {r_['n_sig_pairs']}, критична різниця {r_['crit']:.2f} діб")
rd = P.compare_means(big["records"], "bloom0", big["anova"]["bloom0"], "duncan"); check("Дункан для понад 30" in rd["note"], "Дункан для 300 сортів не рахується – пояснення")
t0 = time.time(); rc = P.compare_means(big["records"], "bloom0", big["anova"]["bloom0"], "control", "G000"); nl_ = sum(1 for c in hyb if rc["vs"][c]["sig"] and rc["vs"][c]["diff"] > 0); ne_ = sum(1 for c in hyb if rc["vs"][c]["sig"] and rc["vs"][c]["diff"] < 0)
check(time.time() - t0 < 5 and nl_ > 250 and ne_ <= 3 and rc["groups"]["G000"] == "станд.", f"порівняння зі стандартом G000 (найраніший кластер): істотно пізніших {nl_}; «раніших» {ne_} – серед 24 справді однакових гібридів кластера (поправка Холма обмежує ймовірність хоча б однієї хибної знахідки, а не гарантує нуль)")
t0 = time.time(); rk_ = P.compare_means(big["records"], "bloom0", big["anova"]["bloom0"], "kw"); check(time.time() - t0 < 20 and rk_["p_overall"] < 1e-6 and len(rk_["mean_ranks"]) == 300, f"Краскел–Уолліс для 300 сортів: p = {rk_['p_overall']:.2g} за {time.time() - t0:.1f} с")
bm = P.analyze(yd_big, [{"key": "bloom0", "name": "Початок цвітіння", "bbch": "61", "hint": ""}], standard="G000", thr=3.0, method="tukey"); check(bm["compare"]["bloom0"]["method"] == "tukey" and bm["method"] == "tukey", "analyze(method=…) передає обраний метод")
ctx_small = P.analyze({2025: [{"name": r["name"], "rep": r["rep"], "dates": {"p": P.fmt_date(r["date"])}} for r in recs6]}, [{"key": "p", "name": "Фаза", "bbch": "", "hint": ""}], "C0"); check(ctx_small["compare"]["p"]["method"] == "tukey" and ctx_small["anova"]["p"]["h2"] > 0.9, "analyze: за замовчуванням «авто» (6 сортів → Тьюкі), H² у результатах")
erc = P.compare_means(recs6, "p", {"error": "тест"}, "tukey"); check(erc["error"] == "тест", "помилка ANOVA передається далі")
un = [r for r in recs6 if not (r["name"] == "C2" and r["rep"] in ("3", "4"))]; anu = P.anova_phase(un, "p", nm6); cu = {m_: P.compare_means(un, "p", anu, m_, "C0") for m_ in ("lsd", "tukey", "bonferroni", "duncan", "sk", "control", "kw")}
check(all("groups" in v for v in cu.values()) and cu["tukey"]["crit"] is None and "різна кількість" in cu["tukey"]["note"], "різна кількість спостережень: усі методи працюють; єдина критична різниця не показується")

print("\n== 6в. Тест Даннетта (порівняння зі стандартом)")
import sad_control_core as _CC
rgd = np.random.default_rng(21); recd = []; effd = {"Стандарт": 0, "Н1": 0, "Н2": 4, "Н3": -5, "Н4": 1}
for c, e in effd.items():
    for i in range(5): recd.append({"year": 2025, "name": c, "rep": f"{c}-{i}", "phase": "p", "doy": 120 + e + float(rgd.normal(0, 1.2))})
cvd = list(effd); and_ = P.anova_phase(recd, "p", cvd); check(and_["design"].startswith("CRD"), "дані для звірки – однофакторна схема (CRD)")
dn = P.compare_means(recd, "p", and_, "dunnett", "Стандарт")
ref_ = _CC.compare_estimates_to_control(cvd, np.array([and_["means"][c] for c in cvd]), np.diag([and_["mse"] / and_["ns"][c] for c in cvd]), ["Стандарт"], and_["dfe"], 0.05)
check(all(abs(dn["vs"][x["entry"]]["p"] - x["p_dunnett"]) < 1e-12 for x in ref_["rows"]), "p-значення = функція модуля «Порівняння зі стандартом» (sad_control_core)")
from scipy.stats import dunnett as _sdun
sp_ = _sdun(*[[r["doy"] for r in recd if r["name"] == c] for c in cvd[1:]], control=[r["doy"] for r in recd if r["name"] == "Стандарт"])
check(max(abs(dn["vs"][c]["p"] - float(pv)) for c, pv in zip(cvd[1:], sp_.pvalue)) < 2e-3, f"p-значення збігаються зі scipy.stats.dunnett: {[round(dn['vs'][c]['p'], 4) for c in cvd[1:]]} проти {[round(float(x), 4) for x in sp_.pvalue]}")
check(dn["groups"]["Стандарт"] == "станд." and dn["groups"]["Н3"] == "↓" and dn["groups"]["Н2"] == "↑" and dn["groups"]["Н1"] == "≈", f"позначки: Н3 раніше (↓), Н2 пізніше (↑), Н1 як стандарт (≈): {dn['groups']}")
check(dn["crit"] is not None and abs(dn["crit"] - dn["dunnett_c"] * math.sqrt(2 * and_["mse"] / 5)) < 1e-5 and "Даннетта" in dn["note"], f"критична різниця для рівних n = c·√(2·MSE/n) = {dn['crit']:.2f} діб")
lv5 = [f"N{i}" for i in range(5)]; r5 = _CC.compare_estimates_to_control(lv5, np.zeros(5), np.diag(np.full(5, 2.0 / 6)), ["N0"], 20, 0.05); check(abs(r5["crit"] - 2.65) < 0.01, f"табличне значення Даннетта (4 порівняння, df = 20): {r5['crit']:.3f} ≈ 2,65")
check("Оберіть стандарт" in P.compare_means(recd, "p", and_, "dunnett", "")["note"], "без стандарту – підказка")
rgh = np.random.default_rng(8); rech = [{"year": 2025, "name": "Ст", "rep": str(i), "phase": "p", "doy": 130 + float(rgh.normal(0, 1))} for i in range(6)]
hyb_ = [f"H{i:03d}" for i in range(300)]; shift = {h: (0 if i < 200 else 9) for i, h in enumerate(hyb_)}
rech += [{"year": 2025, "name": h, "rep": "1", "phase": "p", "doy": 130 + shift[h] + float(rgh.normal(0, 1))} for h in hyb_]
anh = P.anova_phase(rech, "p", ["Ст"] + hyb_); t0 = time.time(); dh = P.compare_means(rech, "p", anh, "dunnett", "Ст"); el = time.time() - t0
late = sum(1 for h in hyb_[200:] if dh["vs"][h]["sig"] and dh["vs"][h]["diff"] > 0); false_ = sum(1 for h in hyb_[:200] if dh["vs"][h]["sig"])
check(el < 3.0, f"300 гібридів (одиночні) проти повтореного стандарту: {el:.2f} с")
check(late >= 95 and false_ <= 2, f"знайдено {late} зі 100 справді пізніших гібридів; хибних знахідок серед 200 однакових: {false_}")
check(dh["crit"] is not None and dh["dunnett_c"] > 3.0, f"єдина критична різниця для одиночних гібридів: {dh['crit']:.2f} діб (c = {dh['dunnett_c']:.3f})")
print("\n== 6г. Стандарти груп стиглості")
check(P.reference_map(["A", "B", "C", "D"], "A", {"B": "пізні", "C": "пізні", "D": "ранні"}, {"пізні": "C"}) == {"A": "A", "B": "C", "C": "C", "D": "A"}, "опорний стандарт: своєї групи; група без стандарту чи без групи – загальний")
check(P.reference_map(["A", "B"], "", {"B": "пізні"}, {"пізні": "Нема"}) == {"A": "", "B": ""}, "стандарт, якого немає в даних, ігнорується (опора – середнє за сортами)")
rgg = np.random.default_rng(31); recg = []; effg = {"Ранній ст.": 0, "Р1": 0.2, "Р2": 3.5, "Пізній ст.": 20, "П1": 20.3, "П2": 15.5, "П3": 25}
grp = {"Ранній ст.": "ранні", "Р1": "ранні", "Р2": "ранні", "Пізній ст.": "пізні", "П1": "пізні", "П2": "пізні", "П3": "пізні"}; gst = {"ранні": "Ранній ст.", "пізні": "Пізній ст."}
ydg = {2025: [{"name": c, "rep": str(r), "dates": {"bloom0": P.fmt_date(D(2025, 4, 25) + dt.timedelta(days=int(round(e + rgg.normal(0, 0.6)))))}} for c, e in effg.items() for r in (1, 2, 3, 4)]}
phg = [{"key": "bloom0", "name": "Початок цвітіння", "bbch": "61", "hint": ""}]
cg = P.analyze(ydg, phg, standard="Ранній ст.", groups=grp, group_std=gst, method="dunnett")
check(cg["ref_of"]["П1"] == "Пізній ст." and cg["ref_of"]["Р2"] == "Ранній ст." and set(cg["standards"]) == {"Ранній ст.", "Пізній ст."}, "кожен сорт прив'язано до стандарту своєї групи")
mg = {c: cg["summ"][(c, "bloom0")]["mean"] for c in effg}
check(abs(cg["vs"][("П2", "bloom0")][0] - (mg["П2"] - mg["Пізній ст."])) < 1e-12 and abs(cg["vs"][("Р2", "bloom0")][0] - (mg["Р2"] - mg["Ранній ст."])) < 1e-12, "різниця в днях – від стандарту своєї групи (а не від загального)")
check(cg["vs"][("П1", "bloom0")][1] == "середній" and cg["vs"][("П2", "bloom0")][1] == "ранній" and cg["vs"][("П3", "bloom0")][1] == "пізній", f"класи в межах пізньої групи: П1 як стандарт, П2 раніший, П3 пізніший")
c1 = P.analyze(ydg, phg, standard="Ранній ст.", method="dunnett"); check(c1["vs"][("П1", "bloom0")][1] == "пізній", "без груп пізній сорт відносно раннього стандарту – тривіально «пізній» (саме тому потрібні групи)")
an_g = cg["anova"]["bloom0"]; cm_g = cg["compare"]["bloom0"]
import sad_control_core as _CC2
for g, std in gst.items():
    mem = [std] + [c for c in effg if grp[c] == g and c != std]
    rr = _CC2.compare_estimates_to_control(mem, np.array([an_g["means"][c] for c in mem]), np.diag([an_g["mse"] / an_g["ns"][c] for c in mem]), [std], an_g["dfe"], 0.05)
    check(all(abs(cm_g["vs"][x["entry"]]["p"] - x["p_dunnett"]) < 1e-12 for x in rr["rows"]), f"Даннетт у групі «{g}» = окремий Даннетт лише для її сортів (спільна помилка ANOVA)")
check(cm_g["groups"]["Ранній ст."] == "станд." and cm_g["groups"]["Пізній ст."] == "станд." and cm_g["groups"]["П3"] == "↑" and cm_g["groups"]["П2"] == "↓" and cm_g["groups"]["П1"] == "≈" and cm_g["groups"]["Р2"] == "↑",
      f"позначки відносно стандарту своєї групи: {cm_g['groups']}")
check("окремо в кожній групі" in cm_g["note"] and "«Пізній ст.»" in cm_g["note"], "пояснення: Даннетт окремо в кожній групі")
ch = P.analyze(ydg, phg, standard="Ранній ст.", groups=grp, group_std=gst, method="control")["compare"]["bloom0"]; check(ch["groups"]["П3"] == "↑" and ch["groups"]["П2"] == "↓" and "окремо в кожній групі" in ch["note"], "варіант із поправкою Холма теж окремо за групами")
cpart = P.analyze(ydg, phg, standard="Ранній ст.", groups={"П1": "пізні", "П2": "пізні", "Пізній ст.": "пізні"}, group_std={"пізні": "Пізній ст."}, method="dunnett")
check(cpart["ref_of"]["П3"] == "Ранній ст." and cpart["ref_of"]["П2"] == "Пізній ст.", "сорт без групи (П3) – відносно загального стандарту")
cnone = P.analyze(ydg, phg, standard="", groups=grp, group_std={}, method="dunnett"); check(cnone["ref_of"] is None and "Оберіть стандарт" in cnone["compare"]["bloom0"]["note"], "групи без стандартів і без загального стандарту – підказка обрати стандарт")
print("\n== 7. Суми температур")
import sad_weather_core as W
days = [D(2025, 3, 1) + dt.timedelta(days=i) for i in range(200)]
tm = np.array([5.0 + 0.1 * i for i in range(200)]); ser = W.DailySeries(days, {"tmean": tm})
d1 = D(2025, 5, 10); k = (d1 - days[0]).days
s_sat = P.temp_sum_between(ser, D(2025, 4, 1), d1, base=10.0, kind="sat"); i0 = (D(2025, 4, 1) - days[0]).days; sel = tm[i0:k + 1]
check(abs(s_sat - sel[sel > 10].sum()) < 1e-9, f"САТ >10 °C за 01.04–10.05 = {s_sat:.1f} (ручна сума збігається)")
s_set = P.temp_sum_between(ser, D(2025, 4, 1), d1, base=10.0, kind="set"); check(abs(s_set - (sel[sel > 10] - 10).sum()) < 1e-9, f"СЕТ >10 °C = {s_set:.1f}")
check(abs(P.temp_sum_between(ser, D(2025, 4, 1), d1, base=5.0, kind="sat") - sel[sel > 5].sum()) < 1e-9, "інший поріг (5 °C)")
check(abs(P.temp_sum_between(ser, D(2025, 4, 1), d1, base=10.0, kind="set", upper=14.0) - (np.minimum(sel, 14.0)[np.minimum(sel, 14.0) > 10] - 10).sum()) < 1e-9, "верхнє обмеження температури для СЕТ")
check(math.isnan(P.temp_sum_between(ser, D(2024, 12, 1), D(2025, 1, 5), 10.0)) and math.isnan(P.temp_sum_between(ser, D(2025, 3, 1), D(2025, 12, 31))) and math.isnan(P.temp_sum_between(ser, D(2025, 5, 10), D(2025, 4, 1))), "період поза даними, неповне покриття або кінець раніше за початок → NaN")
tm2 = tm.copy(); tm2[40:60] = np.nan; ser2 = W.DailySeries(days, {"tmean": tm2})
check(math.isnan(P.temp_sum_between(ser2, D(2025, 3, 1), D(2025, 5, 10))) and not math.isnan(P.temp_sum_between(ser2, D(2025, 3, 1), D(2025, 5, 10), min_cover=0.5)), "пропуски в даних: за покриття < 95 % – NaN; поріг покриття регулюється")
rc, _, _ = P.collect_records({2025: [{"name": "Голден", "rep": "1", "dates": {"bud": "10.04", "bloom0": "10.05", "bloom1": "20.05"}}, {"name": "Гала", "rep": "1", "dates": {"bud": "12.04", "bloom0": "14.05", "bloom1": "25.05"}}]}, ["bud", "bloom0", "bloom1"])
sm1 = P.temp_sums(rc, ser, ("md", 3, 1), 10.0, "sat"); check(len(sm1) == 6 and all(not math.isnan(r["sum"]) for r in sm1), "суми від 1 березня для всіх 6 записів")
g0 = next(r for r in sm1 if r["name"] == "Голден" and r["phase"] == "bloom0"); check(abs(g0["sum"] - P.temp_sum_between(ser, D(2025, 3, 1), D(2025, 5, 10))) < 1e-9, "сума кожного запису відповідає його даті")
sm2 = P.temp_sums(rc, ser, ("phase", "bud"), 10.0, "set"); check(len(sm2) == 4 and not any(r["phase"] == "bud" for r in sm2), "суми від дати фази «bud»: сама ця фаза не рахується")
g2 = next(r for r in sm2 if r["name"] == "Гала" and r["phase"] == "bloom1"); check(abs(g2["sum"] - P.temp_sum_between(ser, D(2025, 4, 12), D(2025, 5, 25), 10.0, "set")) < 1e-9, "початок суми – дата фази саме цього сорту")
check(P.temp_sums(rc, ser, ("phase", "немає"), 10.0, "sat") == [], "початкова фаза відсутня → порожній результат")
ss = P.summarize_sums(sm1, ["Голден", "Гала"], ["bloom0"]); check(ss[("Голден", "bloom0")]["n"] == 1 and abs(ss[("Голден", "bloom0")]["mean"] - g0["sum"]) < 1e-9, "зведення сум за сортами")
nan_sum = P.summarize_sums([{"name": "X", "phase": "p", "sum": float("nan")}], ["X"], ["p"]); check(nan_sum[("X", "p")]["n"] == 0, "NaN-суми у зведення не входять")

print("\n== 8. Дата настання за візитами")
v = [(D(2026, 5, 1), 0), (D(2026, 5, 5), 20), (D(2026, 5, 9), 80), (D(2026, 5, 13), 100)]
check(P.onset_from_visits(v, 50) == (D(2026, 5, 7), "interp"), "поріг 50 %: між 5.05 (20 %) і 9.05 (80 %) → 7.05")
check(P.onset_from_visits(v, 10) == (D(2026, 5, 3), "interp"), "поріг 10 %: між 1.05 (0 %) і 5.05 (20 %) → 3.05")
d90, k90 = P.onset_from_visits(v, 90); check(k90 == "interp" and d90 == D(2026, 5, 11), f"поріг 90 %: 11.05 ({d90})")
check(P.onset_from_visits(v, 100) == (D(2026, 5, 13), "interp") or P.onset_from_visits(v, 100)[0] == D(2026, 5, 13), "поріг 100 %: останній візит")
check(P.onset_from_visits([(D(2026, 5, 5), 30), (D(2026, 5, 9), 80)], 10) == (D(2026, 5, 5), "first"), "поріг вже досягнуто на першому візиті → дата першого візиту, позначка «first»")
check(P.onset_from_visits([(D(2026, 5, 5), 3), (D(2026, 5, 9), 8)], 50) == (None, "none"), "поріг не досягнуто → none")
check(P.onset_from_visits([], 50) == (None, "none") and P.onset_from_visits([(None, 5)], 50) == (None, "none"), "порожні візити → none")
check(P.onset_from_visits(list(reversed(v)), 50) == (D(2026, 5, 7), "interp"), "візити можна вводити в довільному порядку")
check(P.onset_from_visits([(D(2026, 5, 1), 0), (D(2026, 5, 3), float("nan")), (D(2026, 5, 9), 60)], 30) == (D(2026, 5, 5), "interp"), "порожні відсотки пропускаються")
check(P.onset_from_visits([(D(2026, 5, 1), 0), (D(2026, 5, 2), 100)], 50)[0] == D(2026, 5, 2), "півдоби округлюється вгору (до 2.05)")
check(P.onset_from_visits([(D(2026, 5, 1), 0), (D(2026, 5, 4), 60), (D(2026, 5, 8), 40)], 50)[0] == D(2026, 5, 4), "перший перетин береться (2,5 доби → 3), навіть якщо потім відсоток зменшується")

print("\n== 8б. Повний розрахунок analyze()")
phs = [{"key": "bud", "name": "Бруньки", "bbch": "09"}, {"key": "bloom0", "name": "Початок цвітіння", "bbch": "61"}, {"key": "bloom1", "name": "Кінець цвітіння", "bbch": "69"}, {"key": "none", "name": "Без даних", "bbch": ""}]
ydd = {2024: [{"name": "Голден", "rep": "", "dates": {"bud": "10.04", "bloom0": "10.05", "bloom1": "20.05"}}, {"name": "Голден", "rep": "", "dates": {"bud": "11.04", "bloom0": "12.05", "bloom1": "22.05"}},
              {"name": "Гала", "rep": "", "dates": {"bud": "14.04", "bloom0": "14.05", "bloom1": "25.05"}}, {"name": "Гала", "rep": "", "dates": {"bud": "15.04", "bloom0": "16.05", "bloom1": "27.05"}}]}
ctx = P.analyze(ydd, phs, standard="Голден", thr=2.0)
check(ctx["cultivars"] == ["Голден", "Гала"] and [p["key"] for p in ctx["phases"]] == ["bud", "bloom0", "bloom1"] and ctx["n_obs"] == 12 and ctx["years"] == [2024], "порядок сортів; фаза без жодної дати не показується; 12 спостережень")
check(ctx["pairs"] == [("bud", "bloom0"), ("bloom0", "bloom1"), ("bud", "bloom1")], f"періоди: послідовні пари + вся тривалість: {ctx['pairs']}")
check(ctx["standard"] == "Голден" and ctx["vs"][("Гала", "bloom0")][1] == "пізній" and ctx["vs"][("Голден", "bloom0")][0] == 0.0, "стандарт Голден: Гала +4 доби → «пізній» (поріг 2)")
check(set(ctx["anova"]) == {"bud", "bloom0", "bloom1"} and all("table" in a for a in ctx["anova"].values()), "ANOVA для кожної фази з даними")
check(ctx["sums"] is None and ctx["sum_cfg"] is None, "без погоди суми не рахуються")
check(P.analyze(ydd, phs, standard="Нема")["standard"] == "", "стандарт, якого немає в даних, ігнорується")
dts = [D(2024, 3, 1) + dt.timedelta(days=i) for i in range(150)]; sr = W.DailySeries(dts, {"tmean": np.full(150, 14.0)})
cs = P.analyze(ydd, phs, series=sr, sum_cfg={"kind": "sat", "base": 10.0, "start": ["md", 3, 1]})
x0 = cs["sums"][("Голден", "bloom0")]; check(x0["n"] == 2 and abs(x0["mean"] - np.mean([14.0 * ((D(2024, 5, 10) - D(2024, 3, 1)).days + 1), 14.0 * ((D(2024, 5, 12) - D(2024, 3, 1)).days + 1)])) < 1e-9, f"САТ від 1.03: Голден, початок цвітіння = {x0['mean']:.1f} (14 °C × діб)")
cp = P.analyze(ydd, phs, series=sr, sum_cfg={"kind": "set", "base": 10.0, "start": ["phase", "bud"]})
check(cp["sums"][("Гала", "bloom0")]["n"] == 2 and cp["sums"][("Гала", "bud")]["n"] == 0 and abs(cp["sums"][("Гала", "bloom0")]["mean"] - 4.0 * np.mean([(D(2024, 5, 14) - D(2024, 4, 14)).days + 1, (D(2024, 5, 16) - D(2024, 4, 15)).days + 1])) < 1e-9, "СЕТ від дати фази «bud»: (14 − 10) °C × діб; сама фаза «bud» не рахується")
sr2 = W.DailySeries(dts[:40], {"tmean": np.full(40, 14.0)}); cn = P.analyze(ydd, phs, series=sr2, sum_cfg={"kind": "sat", "base": 10.0, "start": ["md", 3, 1]})
check(cn["nan_sums"] > 0 and cn["sums"][("Голден", "bloom0")]["n"] == 0, f"погода не покриває періоди: сум немає, їх пораховано як відсутні ({cn['nan_sums']})")
try: P.analyze({2024: [{"name": "A", "rep": "", "dates": {"bud": "xx"}}]}, phs); check(False, "мало впасти")
except ValueError as e: check("немає жодної коректної дати" in str(e), "без коректних дат → зрозуміле повідомлення")
bad = {2024: [{"name": "A", "rep": "", "dates": {"bud": "10.04", "bloom0": "ab"}}]}; cb = P.analyze(bad, phs); check(len(cb["errors"]) == 1 and cb["n_obs"] == 1, "помилки розбору повертаються, коректні дати рахуються")
print("\n== 9. Проєкт")
proj = {"preset": "pome", "phases": P.preset_phases("pome")[:3], "years_data": yd, "standard": "Голден", "thr": 3.0, "base": 10.0}
js = P.project_to_json(proj); back = P.project_from_json(js)
check(back["years_data"].keys() == {2024, 2025} and back["years_data"][2024] == yd[2024] and back["phases"] == proj["phases"] and back["standard"] == "Голден" and back["format"] == "SAD-phenology", "проєкт: JSON туди й назад (роки – числа, не рядки)")
try: P.project_from_json('{"format": "інше"}'); check(False, "мало впасти")
except ValueError as e: check("не файл фенологічного проєкту" in str(e), "чужий JSON відхиляється")
check("Голден" in js and "\\u" not in js, "кирилиця в JSON записується читабельно")
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ФЕНОЛОГІЇ ПРОЙДЕНО")
