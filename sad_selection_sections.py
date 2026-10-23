# sad_selection_sections.py — S.A.D. v2.1: розділи результатів індексів добору
# -*- coding: utf-8 -*-
import math, re
import numpy as np
import sad_selection_core as SC
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError
from sad_breeding import to_float

SELECTION_HELP = """ІНДЕКСИ ДОБОРУ ЗА КІЛЬКОМА ОЗНАКАМИ

Селекція рідко йде за однією ознакою: добирають комплекс (урожайність, якість, стійкість). Якщо відбирати за кожною
ознакою окремо, ознаки з від'ємною генетичною кореляцією «тягнуть» результат у різні боки. Індекс добору об'єднує
ознаки в одне число I = b₁x₁ + b₂x₂ + …; відбір за ним дає найкращу сукупну зміну агрегатного генотипу H = a₁g₁ + a₂g₂ + …

ТРИ ІНДЕКСИ
• Сміт–Хейзел (1936, 1943): b = P⁻¹Ga. Максимізує кореляцію індексу з агрегатним генотипом, тож дає найбільший ΔH.
  Потребує оцінок генетичних (G) і фенотипних (P) коваріацій — вони тим неточніші, чим менше генотипів.
• Базовий (Williams 1962): b = a. Не потребує G і P — стійкий до їхніх похибок; часто майже не поступається SH.
• Песек–Бейкер (1969): b = G⁻¹d. Користувач задає БАЖАНІ прирости d за ознаками (наприклад, +5 ц/га врожаю, 0 за
  висотою), а індекс підбирає коефіцієнти під них. Економічні ваги не потрібні.

ВАГИ a
• Економічні ваги — цінність одиниці приросту ознаки (в тих самих грошових одиницях); знак «−» означає «менше краще».
• Відносні ваги — якщо економічні невідомі: програма ділить вагу на генетичне SD ознаки, тож ознака з вагою 1
  вносить внесок, пропорційний її генетичній мінливості. Знак «−» — менше краще.

ЩО ПОКАЗАНО
ΔG — очікуваний приріст за кожною ознакою при доборі верхньої частки p; ΔH — сумарний приріст агрегату; r_IH — точність
індексу; h²_I — спадковість індексу. Для порівняння — відгук при доборі лише за однією ознакою.

ОБМЕЖЕННЯ
• Оцінки G і P за даними одного досліду — наближені; для надійних індексів потрібно ≳ 30 генотипів і ≥ 3 повторності.
• Якщо матриця G не додатно визначена, її скориговано «вигинанням» — це ознака замало даних.
• Очікуваний відгук — для нормально розподілених ознак і добору в популяції; для невеликого набору номерів — орієнтовний.
• Індекс застосовано до середніх за повторностями; значення індексу — відносні, їх сенс лише у порівнянні номерів.

Джерела: Smith 1936; Hazel 1943; Williams 1962; Pesek & Baker 1969; Falconer & Mackay 1996."""


def parse_vector(text, k, what):
    parts = [p for p in re.split(r"[;\s]+", text.strip()) if p]
    if len(parts) != k:
        raise BreedingError(f"{what}: вкажіть {k} значень (по одному на ознаку), розділених «;» чи пробілом; зараз їх {len(parts)}.")
    return np.array([to_float(p, what) for p in parts], float)


def sections_selection(rows, headers, weights_text, weights_mode="relative", desired_text="", p_percent=10.0):
    gen = [r[0] for r in rows]; rep = [r[1] for r in rows]
    if any(not g for g in gen) or any(not x for x in rep): raise BreedingError("Генотип і повторність мають бути вказані в кожному рядку.")
    cols = [c for c in range(2, len(headers)) if any(r[c].strip() for r in rows if c < len(r))]
    if len(cols) < 2: raise BreedingError("Потрібно щонайменше 2 заповнені стовпці ознак.")
    names = [headers[c].strip() or f"Ознака {c - 1}" for c in cols]
    Y = np.array([[to_float(r[c], f"«{headers[c]}», рядок {i + 1}") for c in cols] for i, r in enumerate(rows)], float)
    if np.isnan(Y).any(): raise BreedingError("У стовпцях ознак є порожні клітинки: дослід має бути збалансованим.")
    k = len(names)
    mt = SC.multitrait_rcbd(gen, rep, Y, names)
    G, P = mt["G"], mt["P_mean"]
    warns = list(mt["warnings"])
    if mt["g"] < 20: warns.append(f"Лише {mt['g']} генотипів: оцінки генетичних коваріацій дуже неточні, тож індекс Сміта–Хейзела може бути нестійким; "
                                  f"базовий індекс надійніший.")
    if mt["r"] < 3: warns.append(f"Лише {mt['r']} повторності: оцінка фенотипних і генетичних коваріацій грубі.")
    gdiag = np.diag(G)
    for j in range(k):
        if gdiag[j] <= 0: warns.append(f"Ознака «{names[j]}»: генетична дисперсія не відрізняється від нуля (σ²g ≤ 0) — добір за нею не дасть приросту.")
    Gb, bent = SC.bend_psd(G); Pb, _ = SC.bend_psd(P)
    w = parse_vector(weights_text, k, "Ваги")
    if np.all(w == 0): raise BreedingError("Усі ваги нульові.")
    if weights_mode == "relative":
        if np.any(gdiag <= 0): raise BreedingError("Відносні ваги неможливі: у деяких ознак немає генетичної мінливості (σ²g ≤ 0). Задайте економічні ваги або приберіть ці ознаки.")
        a = w / np.sqrt(gdiag)
    else:
        a = w
    i_sel = SC.selection_intensity(p_percent / 100.0)
    methods = []   # (назва, b)
    methods.append(("Сміт–Хейзел", SC.index_coefficients("sh", Gb, Pb, a)))
    methods.append(("Базовий", SC.index_coefficients("base", Gb, Pb, a)))
    d = None
    if desired_text.strip():
        d = parse_vector(desired_text, k, "Бажані прирости")
        methods.append(("Песек–Бейкер", SC.index_coefficients("pb", Gb, Pb, None, d)))
    resp = [(nm, b, SC.expected_response(Gb, Pb, a, b, i_sel)) for nm, b in methods]
    single = [(f"Лише «{names[j]}»", SC.single_trait_response(Gb, Pb, a, j, i_sel)) for j in range(k)]
    sh_dH = resp[0][2]["dH"]
    S = []
    sg = np.sqrt(np.maximum(gdiag, 0))
    S.append(sec_table("Генетичні параметри ознак", ["Ознака", "Середнє", "σ²g", "σ²p (на середнє)", "H² (на середнє)", "σg", "CV генотипний, %"],
                       [[names[j], float(mt["grand"][j]), float(G[j, j]), float(P[j, j]), float(mt["h2_mean"][j]), float(sg[j]),
                         100 * float(sg[j]) / float(mt["grand"][j]) if mt["grand"][j] else float("nan")] for j in range(k)],
                       [None, 3, 4, 4, 3, 3, 2],
                       [f"Генотипів: {mt['g']}; повторностей: {mt['r']}. Оцінки G, P — за добутками середніх MANOVA.",
                        "G після «вигинання» (була не додатно визначена)." if bent else "G додатно визначена."], key="par"))
    S.append(sec_table("Генетичні кореляції", [""] + names, [[names[i]] + [float(mt["r_gen"][i, j]) for j in range(k)] for i in range(k)],
                       [None] + [2] * k, ["Кореляції, що за модулем наближаються до 1 або перевищують її, — наслідок похибки оцінювання."], key="rg"))
    S.append(sec_table("Фенотипні кореляції (між середніми)", [""] + names, [[names[i]] + [float(mt["r_phen"][i, j]) for j in range(k)] for i in range(k)],
                       [None] + [2] * k, key="rp"))
    hdr = ["Метод"] + [f"ΔG: {n}" for n in names] + ["ΔH", "r_IH", "h²_I", "ΔH, % від Сміта–Хейзела"]
    rows_r, tags = [], []
    for nm, b, er in resp:
        rows_r.append([nm] + [float(x) for x in er["dG"]] + [er["dH"], er["accuracy"], er["h2_index"], 100 * er["dH"] / sh_dH if sh_dH else float("nan")])
        tags.append("good" if nm == "Сміт–Хейзел" else None)
    for nm, er in single:
        rows_r.append([nm] + [float(x) for x in er["dG"]] + [er["dH"], er["accuracy"], er["h2_index"], 100 * er["dH"] / sh_dH if sh_dH else float("nan")])
        tags.append(None)
    S.append(sec_table(f"Очікуваний відгук на добір (верхні {p_percent:g} %, i = {i_sel:.3f})", hdr, rows_r,
                       [None] + [3] * k + [3, 3, 3, 1],
                       [f"Агрегатний генотип H = Σ aᵢgᵢ; ваги a = {', '.join(f'{x:.4g}' for x in a)} "
                        f"({'відносні, поділені на σg' if weights_mode == 'relative' else 'економічні'}).",
                        "r_IH — кореляція індексу з агрегатним генотипом; h²_I — спадковість індексу. Зелене — індекс Сміта–Хейзела."], tags=tags, key="resp"))
    S.append(sec_table("Коефіцієнти індексів", ["Ознака", "a (вага)"] + [f"b: {nm}" for nm, _, _ in resp],
                       [[names[j], float(a[j])] + [float(b[j]) for _, b, _ in resp] for j in range(k)], [None] + [4] * (1 + len(resp)),
                       ["Індекс I = Σ bⱼ·(xⱼ − x̄ⱼ). Абсолютні величини b залежать від одиниць виміру й зіставні лише в межах одного стовпця."], key="coef"))
    Z = mt["means"] - mt["grand"]
    sc_sh = SC.index_scores(Z, resp[0][1]); sc_b = SC.index_scores(Z, resp[1][1])
    m_sel = max(1, int(round(p_percent / 100.0 * mt["g"])))
    order = np.argsort(-sc_sh); rk_b = np.empty(mt["g"], int); rk_b[np.argsort(-sc_b)] = np.arange(1, mt["g"] + 1)
    S.append(sec_table("Рейтинг генотипів за індексом", ["Місце (СХ)", "Генотип", "Індекс Сміта–Хейзела", "Індекс базовий", "Місце (базовий)"] + names,
                       [[int(n_ + 1), mt["gen_names"][i], float(sc_sh[i]), float(sc_b[i]), int(rk_b[i])] + [float(x) for x in mt["means"][i]] for n_, i in enumerate(order)],
                       [0, None, 3, 3, 0] + [3] * k,
                       [f"Зелене — відібрані ({m_sel} із {mt['g']}, верхні {p_percent:g} %) за індексом Сміта–Хейзела. Якщо місця за двома індексами сильно різняться — "
                        f"оцінки G і P нестійкі, віддайте перевагу базовому."],
                       tags=["good" if n_ < m_sel else None for n_ in range(mt["g"])], key="rank"))
    sdG = np.where(sg > 0, sg, np.nan)
    ser = {nm: [float(x / sdG[j]) for j, x in enumerate(er["dG"])] for nm, _, er in resp}
    S.append(sec_fig("Графік: відгук за ознаками (в одиницях σg)", lambda f: U.fig_bars(
        f, names, ser, "Очікуваний приріст за ознаками, ΔG/σg", "ΔG / σg"), key="fig"))
    S.append(sec_text("Пояснення", SELECTION_HELP, key="help"))
    return S, warns
