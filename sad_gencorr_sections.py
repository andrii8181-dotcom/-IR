# sad_gencorr_sections.py — S.A.D. v2.1: розділи результатів генотипних і фенотипних кореляцій
# -*- coding: utf-8 -*-
import math
import numpy as np
import sad_gencorr_core as GC
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError
from sad_breeding import to_float

GENCORR_HELP = """ГЕНОТИПНІ Й ФЕНОТИПНІ КОРЕЛЯЦІЇ

rG — генотипна кореляція: зв'язок між «генетичними значеннями» двох ознак; саме вона показує, чи дасть добір за однією
ознакою зсув другої. rP — фенотипна: зв'язок спостережуваних значень, що змішує генетичну й середовищну частини. rE —
середовищна (залишкова). Звичайно |rG| > |rP|, коли спадковість обох ознак менша за 1 (за нульової rE: rG = rP/√(h²₁h²₂)).

ЯК РАХУЄТЬСЯ (збалансований блочний дослід): G = (MP_ген − MP_пох)/r, E = MP_пох, P = G + E (на ділянку) або G + E/r
(на середнє); rG = G₁₂/√(G₁₁G₂₂). «rP (середні)» збігається зі звичайною кореляцією Пірсона між середніми генотипів;
«rP (ділянка)» — фенотипна кореляція на рівні окремої ділянки (формула, поширена в селекційних статтях).

ЗНАЧУЩІСТЬ rG — ПОПЕРЕДЖЕННЯ. У публікаціях rG часто перевіряють як звичайну кореляцію (критичне r за df = g − 2). Це
НАБЛИЖЕННЯ, яке завищує значущість: rG — відношення оцінок компонентів, його похибка більша за похибку простої кореляції
у 1/√(h²₁h²₂) разів. Симуляції (ця програма, r = 3, h² = 0,6, істинна rG = 0) показали, що такий критерій хибно називає
rG істотною у 22 % (g = 15), 27 % (g = 30) і 35 % (g = 60) випадків — замість номінальних 5 %.
Тому висновок тут ґрунтується на довірчому інтервалі бутстрепом за генотипами (перерахунок rG на вибірках генотипів із
поверненням); покриття 95 % інтервалу за симуляціями: 93–95 % при g ≥ 30, ≈ 91 % при g = 25 і лише ≈ 80 % при g = 15.
Традиційний критерій наведено як орієнтир для порівняння з літературою.

ОБМЕЖЕННЯ
• rG визначена, лише якщо обидві ознаки мають додатну генотипну дисперсію; інакше — «не визначено» (а не число).
• rG може випадково вийти за межі ±1 — це ознака похибки оцінювання; інтервал обрізано до [−1; 1].
• Для надійних висновків потрібно ≥ 30 генотипів; при менших вибірках інтервал дуже широкий і ненадійний.
• Метод стосується одного середовища (збалансований блочний дослід); для серії дослідів потрібні змішані моделі.
• Бутстреп-інтервал за відтворюваністю: зерно генератора фіксоване, тож повторний розрахунок дає ті самі межі.

Джерела: Fisher R.A. 1918; Falconer D.S., Mackay T.F.C. 1996; Al-Jibouri H.A., Miller P.A., Robinson H.F. 1958 (Agron. J. 50:633)."""


def _stars_ci(lo95, hi95, lo99, hi99):
    if math.isnan(lo95): return ""
    if not (lo99 <= 0 <= hi99): return "**"
    if not (lo95 <= 0 <= hi95): return "*"
    return ""


def _stars_p(p):
    if p is None or math.isnan(p): return ""
    return "**" if p < 0.01 else ("*" if p < 0.05 else "")


def sections_gencorr(rows, headers, alpha=0.05, n_boot=2000):
    """rows: [Генотип, Повторність, Ознака1, …] (рядки); headers — заголовки стовпців."""
    if not rows: raise BreedingError("Таблиця порожня.")
    gen = [r[0] for r in rows]; rep = [r[1] for r in rows]
    if any(not g for g in gen): raise BreedingError("У деяких рядках немає назви генотипу.")
    if any(not r_ for r_ in rep): raise BreedingError("У деяких рядках немає номера повторності.")
    cols = [c for c in range(2, len(headers)) if any((r[c] if c < len(r) else "").strip() for r in rows)]
    if len(cols) < 2: raise BreedingError("Потрібно щонайменше 2 заповнені стовпці з ознаками.")
    traits = [headers[c].strip() or f"Ознака {c - 1}" for c in cols]
    Y = np.array([[to_float(r[c] if c < len(r) else "", f"«{traits[ci]}», рядок {i + 1}") for ci, c in enumerate(cols)] for i, r in enumerate(rows)])
    if np.any(np.isnan(Y)): raise BreedingError("У даних є порожні клітинки: дослід має бути збалансованим (усі ознаки в усіх ділянках).")
    res = GC.genotypic_correlations(gen, rep, Y, traits, alpha, n_boot)
    g, r, k = res["g"], res["r"], res["k"]
    S = []
    # 1. таблиця пар
    rows_, tags = [], []
    for q in sorted(res["pairs"], key=lambda q: -(abs(q["rG"]) if not math.isnan(q["rG"]) else -1)):
        if math.isnan(q["rG"]):
            verdict, tag = "не визначено", "bad"
        elif math.isnan(q["rG_lo"]):
            verdict, tag = "інтервал ненадійний", "warn"
        else:
            sg = not (q["rG_lo"] <= 0 <= q["rG_hi"])
            verdict = ("істотна додатна" if (sg and q["rG"] > 0) else "істотна від'ємна" if sg else "не істотна")
            tag = "good" if (sg and q["rG"] > 0) else "bad" if sg else None
            if q["out_of_range"]: verdict = "|rG| > 1: похибка оцінки"; tag = "warn"
        rows_.append([q["a"], q["b"], q["rG"], q["rG_lo"], q["rG_hi"], verdict, q["rP_mean"], q["rP_mean_p"], q["rP"], q["rE"], q["rG_p_trad"]])
        tags.append(tag)
    S.append(sec_table("Генотипні й фенотипні кореляції",
                       ["Ознака 1", "Ознака 2", "rG", f"ДІ {100 * (1 - alpha):.0f} % від", "до", "Висновок про rG", "rP (сер.)", "p (rP сер.)",
                        "rP (діл.)", "rE", "p трад."], rows_,
                       [None, None, 3, 3, 3, None, 3, "p", 3, 3, "p"],
                       [f"g = {g} генотипів, r = {r} повторностей. rG: бутстреп-інтервал за генотипами ({res['n_boot']} вибірок); висновок — за ним.",
                        "«p трад.» — перевірка rG як звичайної кореляції (df = g − 2); за симуляціями вона завищує значущість (22–35 % хибних "
                        "спрацювань при номіналі 5 %) — лише орієнтир для порівняння з літературою.",
                        "«не істотна» — інтервал rG містить 0; «не визначено» — немає генотипної мінливості в одній з ознак.",
                        "rP (сер.) — кореляція Пірсона між середніми генотипів, p — звичайний t-тест (df = g − 2), для неї коректний. "
                        "rP (діл.) — на рівні окремих ділянок. rE — середовищна (залишкова).",
                        "Зелене — істотна додатна rG, червоне — істотна від'ємна або не визначена, жовте — потребує обережності."],
                       tags=tags, key="pairs"))
    # 2. матриця у стилі публікацій
    mat = []
    byij = {(q["i"], q["j"]): q for q in res["pairs"]}
    for i in range(k):
        row = [traits[i]]
        for j in range(k):
            if i == j: row.append((res["h2"][i], ""))
            elif i < j:
                q = byij[(i, j)]
                row.append((q["rG"], _stars_ci(q["rG_lo"], q["rG_hi"], q["rG_lo99"], q["rG_hi99"])) if not math.isnan(q["rG"]) else "н/в")
            else:
                q = byij[(j, i)]; row.append((q["rP_mean"], _stars_p(q["rP_mean_p"])))
        mat.append(row)
    S.append(sec_table("Матриця rG / rP (як у публікаціях)", ["Ознака"] + traits, mat, [None] + [3] * k,
                       ["Над діагоналлю — генотипна кореляція rG; під діагоналлю — фенотипна rP (на середніх); на діагоналі — спадковість h² "
                        "(на рівні середніх).",
                        "Зірочки над діагоналлю: * — 95 % (**— 99 %) бутстреп-інтервал для rG не містить 0. Під діагоналлю: * p < 0,05, ** p < 0,01 "
                        "(t-тест кореляції Пірсона між середніми, df = g − 2). «н/в» — не визначено.",
                        "Зірочки для rG навмисно НЕ за традиційним критерієм: він завищує значущість (див. «Пояснення»)."], key="matrix"))
    # 3. компоненти дисперсії
    comp = []
    for i in range(k):
        Gii, Eii = res["G"][i, i], res["E"][i, i]; mean = float(res["means"][:, i].mean())
        pp = Gii + Eii
        gcv = 100 * math.sqrt(Gii) / mean if (Gii > 0 and mean) else float("nan")
        pcv = 100 * math.sqrt(pp) / mean if (pp > 0 and mean) else float("nan")
        comp.append([traits[i], mean, Gii, Eii, pp, res["h2"][i], gcv, pcv])
    S.append(sec_table("Компоненти дисперсії й спадковість", ["Ознака", "Середнє", "σ²g", "σ²e", "σ²p (ділянка)", "h² (середні)", "GCV, %", "PCV, %"], comp,
                       [None, 3, 4, 4, 4, 3, 2, 2], ["σ²g = (MS_ген − MS_пох)/r; σ²e = MS_пох; σ²p = σ²g + σ²e. Від'ємна σ²g — генетичної мінливості не виявлено."], key="comp"))
    # 4. графіки
    H = res["rG"].copy()
    for i in range(k):
        for j in range(i):
            H[i, j] = res["rP_mean"][i, j]
    S.append(sec_fig("Графік: rG (над діагоналлю) і rP (під діагоналлю)", lambda f: U.fig_heat(
        f, np.where(np.isnan(H), 0, H), traits, traits, "Генотипні (верх) і фенотипні (низ) кореляції", "кореляція"),
        size=(max(5.5, 1.0 * k + 3), max(4.6, 0.9 * k + 2.5)), key="heat"))
    pr = [q for q in res["pairs"] if not math.isnan(q["rG"])]
    if pr:
        S.append(sec_fig("Графік: rG і rP — порівняння", lambda f: U.fig_bars(
            f, [f"{q['a']}\n{q['b']}" for q in pr[:15]], {"rG": [q["rG"] for q in pr[:15]], "rP (середні)": [q["rP_mean"] for q in pr[:15]],
                                                          "rE": [q["rE"] for q in pr[:15]]},
            "Генотипна, фенотипна та середовищна кореляції", "кореляція"), size=(max(6.5, 0.8 * len(pr[:15]) + 3), 4.8), key="bars"))
    S.append(sec_text("Пояснення", GENCORR_HELP, key="help"))
    return S, res["warnings"], res
