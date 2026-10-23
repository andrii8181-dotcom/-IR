# sad_assoc_sections.py – S.A.D. v2.1: розділи результатів для зв'язку змінних різних типів
# -*- coding: utf-8 -*-
import math
import numpy as np
import sad_assoc_core as A
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError
from sad_breeding import to_float

ASSOC_HELP = """ЗВ'ЯЗОК ЗМІННИХ РІЗНИХ ТИПІВ – ЯКИЙ КОЕФІЦІЄНТ КОЛИ

Звичайна кореляція Пірсона потребує двох кількісних ознак. Коли одна з ознак номінальна (сорт, варіант, є/немає), потрібні інші міри:

η (кореляційне відношення) – номінальна група × кількісна ознака. η² – частка мінливості ознаки, зумовлена групами (те саме, що частка
SS між групами в однофакторному ANOVA). η² у вибірці ЗАВИЩЕНИЙ, тому поруч наведено ω² і ε², які поправлені на зміщення; довірчий
інтервал η² – через нецентральний F-розподіл. Умовна шкала Cohen: 0,01 – малий, 0,06 – середній, 0,14 – великий ефект.
Непараметричний аналог – ε² за Kruskal–Wallis. η не показує напрямку й не каже, ЯКІ групи відрізняються (для цього – пост-хок тести).

Дві групи × кількісна ознака:
• рангово-бісеріальний r_rb (= δ Кліффа) – різниця між частками пар «перша група більша» та «перша група менша»; стійкий до викидів
  і не потребує нормальності; супровідна ймовірність переваги P(X > Y) – шанс, що випадкове значення першої групи перевищить друге;
• точково-бісеріальний r_pb – це звичайна кореляція Пірсона між ознакою та індикатором групи; його p збігається з t-тестом
  Стьюдента; потребує приблизної нормальності й однакових дисперсій.
Бісеріальний коефіцієнт (для штучно розділеної нормальної ознаки) свідомо не реалізовано: він вимагає припущення про нормальність
прихованої змінної, і його часто застосовують хибно.

Номінальна × номінальна (таблиця спряженості):
• χ² перевіряє незалежність; V Крамера (0–1) – сила зв'язку; T Чупрова – те саме, але менш чутливе до форми таблиці; C Пірсона не досягає 1
  (показано й C, поділений на C_max); для 2×2 додатково φ зі знаком і відношення шансів (OR) з інтервалом;
• V у вибірці завищений, особливо при малому n, тому наведено V зі скоригованим зміщенням (Bergsma 2013) та його бутстреп-інтервал;
• якщо очікувані частоти малі (< 5 у понад 20 % клітинок), χ²-наближення ненадійне – дивіться точний тест (Фішера для 2×2,
  Монте-Карло за таблицями з тими ж сумами для більших таблиць);
• скориговані стандартизовані залишки показують, ЯКІ клітинки створюють зв'язок (* – понад межу Бонферроні для всіх клітинок).

ОБМЕЖЕННЯ
• Усі показники описують зв'язок, а не причинність.
• Для спостережень, що не є незалежними (повторні виміри на тих самих об'єктах), χ²-тест і стандартні інтервали неприйнятні.
• Шкали Cohen (η², V) та Vargha–Delaney (r_rb) – умовні орієнтири, а не закон; тлумачте з огляду на предметну галузь.

Джерела: Cohen J. 1988; Steiger J.H. 2004 (Psychol. Methods 9:164); Bergsma W. 2013 (J. Korean Stat. Soc. 42:323); Cliff N. 1993; Tomczak M., Tomczak E. 2014."""


def _read_groups(rows, label):
    groups = {}
    for i, r in enumerate(rows):
        g = (r[0] if len(r) > 0 else "").strip(); v = (r[1] if len(r) > 1 else "").strip()
        if not g and not v: continue
        if not g: raise BreedingError(f"Рядок {i + 1}: не вказано групу.")
        if not v: raise BreedingError(f"Рядок {i + 1}: немає значення для групи «{g}».")
        groups.setdefault(g, []).append(to_float(v, f"Рядок {i + 1}, «{label}»"))
    return groups


def _group_table(names, gs):
    rows = [[n, len(g), float(np.mean(g)), float(np.std(g, ddof=1)) if len(g) > 1 else float("nan"), float(np.median(g)), float(np.min(g)), float(np.max(g))]
            for n, g in zip(names, gs)]
    return sec_table("Групи: описові показники", ["Група", "n", "Середнє", "SD", "Медіана", "Мін", "Макс"], rows, [None, 0, 3, 3, 3, 3, 3], key="groups")


def sections_eta(rows, value_label="Значення", alpha=0.05):
    groups = _read_groups(rows, value_label)
    names = list(groups); gs = [np.array(groups[n]) for n in names]
    e = A.eta_squared(gs, alpha)
    S = []
    S.append(sec_table("Кореляційне відношення η (група × кількісна ознака)",
                       ["Груп", "n", "η²", "η", f"ДІ η² {100 * (1 - alpha):.0f} % від", "до", "Величина", "ω²", "ε²", "F", "df₁", "df₂", "p (ANOVA)"],
                       [[e["k"], e["n"], e["eta2"], e["eta"], e["ci_lo"], e["ci_hi"], A.eta_strength(e["eta2"]), e["omega2"], e["eps2"], e["F"], e["df1"], e["df2"], e["p"]]],
                       [0, 0, 3, 3, 3, 3, None, 3, 3, 2, 0, 0, "p"],
                       ["η² – частка мінливості, зумовлена групами; ω² і ε² – поправлені на зміщення оцінки (від'ємні значення означають ефект, "
                        "не відмінний від нуля). Шкала Cohen для η²: 0,01 / 0,06 / 0,14.",
                        "Інтервал η² – через нецентральний F-розподіл (Steiger 2004); нижня межа 0 означає, що ефект не відрізняється від нуля."], key="eta"))
    S.append(sec_table("Непараметрична перевірка й однорідність дисперсій", ["Kruskal–Wallis H", "p", "ε² (за H)", "p Левена"],
                       [[e["kw_H"], e["kw_p"], e["kw_eps2"], e["levene_p"]]], [3, "p", 3, "p"],
                       ["ε² за Kruskal–Wallis = H/(n − 1) – розмір ефекту за рангами. Левена: p < 0,05 – дисперсії груп різні, η² і F менш надійні."], key="np"))
    S.append(_group_table(names, gs))
    S.append(sec_fig("Графік: розподіл у групах", lambda f: U.fig_groups(f, names, gs, value_label, f"η² = {e['eta2']:.3f}".replace(".", ",")),
                     size=(max(6.0, 1.0 * len(names) + 3), 5.0), key="fig"))
    S.append(sec_text("Пояснення", ASSOC_HELP, key="help"))
    warns = []
    if e["levene_p"] == e["levene_p"] and e["levene_p"] < 0.05:
        warns.append(f"Дисперсії груп різні (Левена, p = {e['levene_p']:.3f}): η² і F-тест менш надійні; зверніть увагу на Kruskal–Wallis.")
    if min(e["ns"]) < 5: warns.append(f"У найменшій групі лише {min(e['ns'])} спостережень: інтервал η² дуже широкий.")
    if max(e["ns"]) > 3 * min(e["ns"]): warns.append("Групи дуже різні за обсягом (більш ніж у 3 рази) – розподіл помилки нерівний.")
    return S, warns, e


def sections_two_groups(rows, value_label="Значення", alpha=0.05, n_boot=2000):
    groups = _read_groups(rows, value_label)
    if len(groups) != 2: raise BreedingError(f"Для цього аналізу потрібні рівно 2 групи, у таблиці їх {len(groups)}. Для більшої кількості груп оберіть кореляційне відношення η.")
    names = list(groups); x = np.array(groups[names[0]]); y = np.array(groups[names[1]])
    e = A.two_group_effects(x, y, alpha, n_boot)
    S = []
    S.append(sec_table("Ранговий розмір ефекту", ["Група 1", "Група 2", "n₁", "n₂", "P(1 > 2)", "r_rb (δ Кліффа)", f"ДІ {100 * (1 - alpha):.0f} % від", "до", "Величина", "p (Манн–Уітні)"],
                       [[names[0], names[1], e["n1"], e["n2"], e["cles"], e["rrb"], e["rrb_lo"], e["rrb_hi"], A.rrb_strength(e["rrb"]), e["p_mw"]]],
                       [None, None, 0, 0, 3, 3, 3, 3, None, "p"],
                       ["r_rb > 0 – значення першої групи переважно більші; P(1 > 2) – ймовірність, що випадкове значення групи 1 перевищить значення групи 2 "
                        "(нічиї враховано наполовину); r_rb = 2·P − 1.",
                        f"Інтервал – бутстреп (відсотковий, {e['n_boot']} перевибірок; відтворюваний). Величина – за орієнтирами Vargha–Delaney (0,11 / 0,28 / 0,43 для |r_rb|)."], key="rank"))
    S.append(sec_table("Точково-бісеріальний коефіцієнт (параметричний)", ["r_pb", f"ДІ {100 * (1 - alpha):.0f} % від", "до", "p (Стьюдент)", "p (Велч)"],
                       [[e["rpb"], e["rpb_lo"], e["rpb_hi"], e["rpb_p"], e["p_welch"]]], [3, 3, 3, "p", "p"],
                       ["r_pb – кореляція Пірсона між ознакою та індикатором групи (група 1 = 1); його p збігається з t-тестом Стьюдента. "
                        "p Велча не вимагає однакових дисперсій. Для сильно скошених даних орієнтуйтеся на ранговий розмір ефекту."], key="pb"))
    S.append(_group_table(names, [x, y]))
    S.append(sec_fig("Графік: розподіл у групах", lambda f: U.fig_groups(f, names, [x, y], value_label, f"r_rb = {e['rrb']:.2f}".replace(".", ",")), size=(6.2, 5.0), key="fig"))
    S.append(sec_text("Пояснення", ASSOC_HELP, key="help"))
    warns = []
    if min(e["n1"], e["n2"]) < 10: warns.append("Менше 10 спостережень у групі: бутстреп-інтервал для r_rb наближений і, як правило, завузький.")
    if e["p_mw"] == e["p_mw"] and (e["p_mw"] < 0.05) != (e["p_welch"] < 0.05): warns.append("Тести Манна–Уітні та Велча дають різні висновки (за α = 0,05): розподіл імовірно далекий від нормального або містить викиди.")
    return S, warns, e


def _cont_rows(rows):
    A_, B_, W = [], [], []
    for i, r in enumerate(rows):
        a = (r[0] if len(r) > 0 else "").strip(); b = (r[1] if len(r) > 1 else "").strip(); w = (r[2] if len(r) > 2 else "").strip()
        if not a and not b and not w: continue
        if not a or not b: raise BreedingError(f"Рядок {i + 1}: потрібно вказати обидві ознаки.")
        A_.append(a); B_.append(b); W.append(to_float(w, f"Рядок {i + 1}, «Частота»") if w else 1.0)
    if not A_: raise BreedingError("Таблиця порожня.")
    if any(v != v for v in W): raise BreedingError("Частота має бути числом.")
    return A_, B_, W


def sections_contingency(rows, label_a="Ознака A", label_b="Ознака B", alpha=0.05, n_boot=2000, n_mc=20000):
    a, b, w = _cont_rows(rows)
    T, rl, cl = A.crosstab(a, b, w)
    c = A.contingency_analysis(T, alpha, n_boot, n_mc)
    # після виключення порожніх рядків/стовпців підписи треба узгодити
    rkeep = [i for i in range(len(rl)) if T[i].sum() > 0]; ckeep = [j for j in range(len(cl)) if T[:, j].sum() > 0]
    rl = [rl[i] for i in rkeep]; cl = [cl[j] for j in ckeep]; Tm = c["table"]
    S = []
    S.append(sec_table(f"Таблиця спряженості: {label_a} × {label_b}", [f"{label_a} \\ {label_b}"] + cl + ["Усього"],
                       [[rl[i]] + [int(Tm[i, j]) for j in range(len(cl))] + [int(Tm[i].sum())] for i in range(len(rl))] +
                       [["Усього"] + [int(Tm[:, j].sum()) for j in range(len(cl))] + [int(Tm.sum())]],
                       [None] + [0] * (len(cl) + 1), key="table"))
    S.append(sec_table("Частки в рядках, %", [f"{label_a} \\ {label_b}"] + cl, [[rl[i]] + [100 * Tm[i, j] / Tm[i].sum() for j in range(len(cl))] for i in range(len(rl))],
                       [None] + [1] * len(cl), ["Кожен рядок = 100 %: порівнюйте розподіл за стовпцями між рядками."], key="shares"))
    S.append(sec_table("Очікувані частоти (за незалежності)", [f"{label_a} \\ {label_b}"] + cl, [[rl[i]] + [float(c["expected"][i, j]) for j in range(len(cl))] for i in range(len(rl))],
                       [None] + [2] * len(cl), [f"Найменша очікувана частота: {c['min_expected']:.2f}; клітинок із очікуваною частотою < 5: {100 * c['share_small']:.0f} %."], key="expected"))
    S.append(sec_table("Скориговані стандартизовані залишки", [f"{label_a} \\ {label_b}"] + cl,
                       [[rl[i]] + [(float(c["adj_resid"][i, j]), "*" if abs(c["adj_resid"][i, j]) > c["resid_crit"] else "") for j in range(len(cl))] for i in range(len(rl))],
                       [None] + [2] * len(cl),
                       [f"Залишок > 0 – клітинка містить більше спостережень, ніж за незалежності; * – |z| > {c['resid_crit']:.2f} (межа з поправкою Бонферроні на {c['r'] * c['c']} клітинок, α = {alpha})."], key="resid"))
    nan = float("nan"); df_star = min(c["r"], c["c"]) - 1
    st = [["χ² Пірсона", c["chi2"], nan, nan, c["p_chi2"], f"df = {c['dof']}"]]
    if "yates_p" in c: st.append(["χ² із поправкою Єйтса (2×2)", nan, nan, nan, c["yates_p"], "консервативний"])
    st.append([c["exact_kind"], nan, nan, nan, c["p_exact"], "надійний за малих частот"])
    if "phi" in c: st.append(["φ (2×2, зі знаком)", c["phi"], nan, nan, nan, ""])
    st.append(["V Крамера", c["V"], nan, nan, nan, A.v_strength(c["V"], df_star)])
    st.append(["V Крамера, скоригований на зміщення", c["V_corr"], c["V_lo"], c["V_hi"], nan, A.v_strength(c["V_corr"], df_star) + " (інтервал – бутстреп)"])
    st.append(["T Чупрова", c["T"], nan, nan, nan, ""])
    st.append(["C Пірсона", c["C"], nan, nan, nan, f"макс. {c['C_max']:.3f}".replace(".", ",")])
    st.append(["C Пірсона / C_max", c["C_adj"], nan, nan, nan, ""])
    if "OR" in c: st.append(["Відношення шансів (OR)", c["OR"], c["OR_lo"], c["OR_hi"], nan, "з поправкою 0,5" if c["OR_corrected"] else "інтервал Вульфа"])
    S.append(sec_table("Показники зв'язку", ["Показник", "Значення", f"ДІ {100 * (1 - alpha):.0f} % від", "до", "p", "Примітка"], st, [None, 3, 3, 3, "p", None],
                       [f"n = {c['n']}; рядків {c['r']}, стовпців {c['c']}. Шкала для V (за Cohen) залежить від df* = min(r − 1, c − 1) = {df_star}.",
                        "V зі зміщенням скоригований за Bergsma (2013); звичайний V завищений за малих n. Порівнюючи таблиці різного розміру, надавайте перевагу V і T, а не C."], key="stats"))
    S.append(sec_fig("Графік: частки в рядках", lambda f: U.fig_stacked(f, rl, cl, Tm, f"{label_a} × {label_b}: розподіл у рядках"),
                     size=(8.4, max(3.6, 0.6 * len(rl) + 2.4)), key="stack"))
    S.append(sec_fig("Графік: скориговані залишки", lambda f: U.fig_heat(f, c["adj_resid"], rl, cl, "Скориговані стандартизовані залишки", "z"),
                     size=(max(5.5, 1.0 * len(cl) + 3), max(4.2, 0.8 * len(rl) + 2.4)), key="heat"))
    S.append(sec_text("Пояснення", ASSOC_HELP, key="help"))
    return S, c["warnings"], c
