# sad_het_ord_sections.py — S.A.D. v2.1: розділи результатів для гетерозису й бальних ознак
# -*- coding: utf-8 -*-
import math
import numpy as np
from scipy import stats
import sad_heterosis_core as HC
import sad_ordinal_core as OC
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError
from sad_breeding import to_float, sig

HET_HELP = """ГЕТЕРОЗИС ГІБРИДІВ F₁

Гетерозис — перевищення гібридом F₁ батьківських форм. Розрізняють:
• відносно СЕРЕДНЬОГО БАТЬКІВ (MPH, середньопартійний): (F₁ − MP)/MP·100, MP = (P₁ + P₂)/2;
• відносно КРАЩОГО БАТЬКА (BPH, гетеробельтіоз): (F₁ − BP)/BP·100 — найсуворіший критерій господарської цінності;
• відносно СТАНДАРТУ (SH, «стандартний гетерозис»): (F₁ − St)/St·100 — те, що цікавить виробника.

Тест для кожного виду — t-критерій для лінійного контрасту у блоковій моделі. SE(F₁ − MP) = √(1,5·MSE/r), SE(F₁ − BP) = SE(F₁ − St) =
√(2·MSE/r) у збалансованому досліді; за різної кількості повторностей програма рахує SE для кожного порівняння окремо.
Поправка на множинність — Холм (окремо для кожного виду гетерозису по всіх гібридах).

НАПРЯМ. Для ознак, де «менше — краще» (вегетаційний період, висота), оберіть цей напрям: кращим батьком вважається нижчий, а
позитивний відсоток означає збільшення значення ознаки, тобто «небажаний» напрям. Висновок у таблиці враховує напрям.

ОБМЕЖЕННЯ
• Гетерозис — властивість конкретної пари батьків у конкретних умовах; для висновків про стабільність потрібні кілька середовищ.
• Відсотковий гетерозис не має змісту, якщо середнє батьків ≤ 0 (напр. для відхилень).
• Батьки без повторностей мають велику похибку середнього; тест тоді малонадійний.
• Інбредну депресію (F₂ відносно F₁) тут не розглянуто.

Джерела: Fonseca S., Patterson F.L. 1968 Crop Sci. 8:85; Singh R.K., Chaudhary B.D. 1977; Holm S. 1979."""

SCORES_HELP = """БАЛЬНІ ОЗНАКИ

Бали (1–9, 0–5 тощо) — порядкові дані: різниця між балами 3 і 4 не дорівнює різниці між 7 і 8. Тому середнє арифметичне й ANOVA для
них не мають суворого змісту. Програма порівнює генотипи за РАНГАМИ: тест Крускала–Уолліса (чи є різниця взагалі), далі парні
порівняння за Данном (1964) із поправкою на зв'язані ранги й на множинність (Холм — за замовчуванням). Групи з однаковою
літерою не відрізняються.

ІНДЕКС РОЗВИТКУ ХВОРОБИ (McKinney 1923) = 100·Σ(бал − мін)/(n·(макс − мін)), %. Це описова характеристика, що зручна для звітів;
порівнюйте генотипи за рангами, а не за цим індексом.

AUDPC — площа під кривою розвитку хвороби (трапеції між обліками): Σ[(yᵢ + yᵢ₊₁)/2]·(tᵢ₊₁ − tᵢ). Відносна rAUDPC = AUDPC/(y_max·тривалість)
від 0 до 1 і придатна для порівняння дослідів із різною тривалістю. Для порівняння генотипів за AUDPC використано той самий
ранговий підхід на рівні ділянок.

ОБМЕЖЕННЯ
• Для надійного тесту Данна потрібно щонайменше 5–6 спостережень на генотип.
• Рангові тести не враховують блоки; якщо блоковий ефект істотний, використайте змішану модель на значеннях AUDPC.
• Різні оцінювачі дають різні бали: за кількох оцінювачів їх треба калібрувати.

Джерела: Dunn O.J. 1964 Technometrics 6:241; McKinney H.H. 1923; Shaner G., Finney R.E. 1977 Phytopathology 67:1051; Campbell & Madden 1990."""


# ═══════════════════════════════════════════════════════════════
def sections_heterosis(rows, trait_col, trait_name, standard="", direction="higher", alpha=0.05):
    ent = [r[0] for r in rows]
    if any(not e for e in ent): raise BreedingError("У деяких рядках немає назви генотипу.")
    y = [to_float(r[trait_col], f"«{trait_name}», рядок {i + 1}") for i, r in enumerate(rows)]
    if any(v != v for v in y): raise BreedingError(f"У стовпці «{trait_name}» є порожні клітинки.")
    parents = {}
    for r in rows:
        if r[1] or r[2]:
            if not (r[1] and r[2]): raise BreedingError(f"У гібрида «{r[0]}» указано лише одного батька: потрібні обидва.")
            pr = (r[1], r[2])
            if parents.setdefault(r[0], pr) != pr: raise BreedingError(f"Гібрид «{r[0]}» має різних батьків у різних рядках.")
    crosses = [(h, p1, p2) for h, (p1, p2) in parents.items()]
    if not crosses: raise BreedingError("Не вказано жодного гібрида: заповніть стовпці «Батько 1» і «Батько 2» у рядках гібридів.")
    blocks = [r[3] for r in rows] if any(r[3] for r in rows) else None
    if blocks is not None and any(not b for b in blocks): raise BreedingError("Повторність указано не в усіх рядках.")
    res = HC.heterosis(ent, y, crosses, standard.strip() or None, blocks, direction, alpha)
    has_sh = any("sh_pct" in r for r in res["rows"])
    hdr = ["Гібрид", "Батьки", "n", "F₁", "MP", "Кращий батько", "BP", "MPH, %", "p MPH (Холм)", "Висновок MPH", "BPH, %", "p BPH (Холм)", "Висновок BPH"]
    nd = [None, None, 0, 3, 3, None, 3, 1, 4, None, 1, 4, None]
    if has_sh: hdr += ["SH, %", "p SH (Холм)", "Висновок SH"]; nd += [1, 4, None]
    tr, tags = [], []
    for r in res["rows"]:
        row = [r["hybrid"], f"{r['p1']} × {r['p2']}", r["n"], r["F1"], r["MP"], r["BP_name"], r["BP"], r["mph_pct"], (r["mph_p_holm"], sig(r["mph_p_holm"])),
               r["mph_verdict"], r["bph_pct"], (r["bph_p_holm"], sig(r["bph_p_holm"])), r["bph_verdict"]]
        if has_sh:
            row += ([r["sh_pct"], (r["sh_p_holm"], sig(r["sh_p_holm"])), r["sh_verdict"]] if "sh_pct" in r else [float("nan"), float("nan"), "—"])
        tr.append(row)
        verd = [r["mph_verdict"], r["bph_verdict"]] + ([r["sh_verdict"]] if "sh_pct" in r else [])
        tags.append("bad" if any("небажаний" in v for v in verd) else "good" if "— бажаний" in r["bph_verdict"] else "info" if "— бажаний" in r["mph_verdict"] else None)
    S = [sec_table(f"Гетерозис: {trait_name}", hdr, tr, nd,
                   [f"MSE = {res['mse']:.4g}; df = {res['df']}; CV = {res['cv']:.1f} %; α = {alpha}; напрям: {'більше — краще' if direction == 'higher' else 'менше — краще'}."
                    + (f" Стандарт: {res['standard']}." if res["standard"] else ""),
                    "p поправлено за Холмом по всіх гібридах. Зелене — бажаний гетерозис відносно кращого батька; синє — лише відносно середнього батьків; "
                    "червоне — достовірно небажаний у будь-якому порівнянні."], tags=tags, key="het")]
    labels = [r["hybrid"] for r in res["rows"]]
    ser = {"MPH, %": [r["mph_pct"] for r in res["rows"]], "BPH, %": [r["bph_pct"] for r in res["rows"]]}
    if has_sh: ser["SH, %"] = [r.get("sh_pct", float("nan")) for r in res["rows"]]
    S.append(sec_fig("Графік: гетерозис, %", lambda f: U.fig_bars(f, labels, ser, f"Гетерозис гібридів: {trait_name}", "%"),
                     size=(8.6, 5.2), key="fig"))
    S.append(sec_text("Пояснення", HET_HELP, key="help"))
    return S, res["warnings"]


# ═══════════════════════════════════════════════════════════════
def _score_scale(smin, smax):
    try: a, b = float(str(smin).replace(",", ".")), float(str(smax).replace(",", "."))
    except ValueError: raise BreedingError("Межі шкали мають бути числами.")
    if b <= a: raise BreedingError("Максимальний бал шкали має бути більшим за мінімальний.")
    return a, b


def sections_scores(rows, trait_col, trait_name, smin=1, smax=9, adjust="holm", alpha=0.05, lower_better=True):
    smin, smax = _score_scale(smin, smax)
    groups = {}
    for i, r in enumerate(rows):
        if not r[0]: raise BreedingError(f"У рядку {i + 1} немає назви генотипу.")
        groups.setdefault(r[0], []).append(to_float(r[trait_col], f"«{trait_name}», рядок {i + 1}"))
    if len(groups) < 2: raise BreedingError("Потрібно щонайменше 2 генотипи.")
    if any(v != v for g in groups.values() for v in g): raise BreedingError(f"У стовпці «{trait_name}» є порожні клітинки.")
    for nm, g in groups.items():
        if any(v < smin - 1e-12 or v > smax + 1e-12 for v in g): raise BreedingError(f"Генотип «{nm}»: є бали поза шкалою {smin:g}–{smax:g}.")
    dn = OC.dunn_test(groups, adjust)
    names = sorted(groups, key=lambda k: dn["mean_ranks"][k], reverse=not lower_better)    # кращі — першими
    letters = OC.compact_letters(names, dn["pairs"], alpha, order_by=names)
    warns = []
    small = [k for k, g in groups.items() if len(g) < 5]
    if small: warns.append("Менше 5 спостережень у генотипів: " + ", ".join(small[:6]) + (" …" if len(small) > 6 else "") +
                           " — тест Данна для них малопотужний, а літери значущості ненадійні.")
    S = []
    desc_rows = []
    for rank, nm in enumerate(names, 1):
        d = OC.describe_scores(groups[nm])
        desc_rows.append([rank, nm, d["n"], d["median"], d["q1"], d["q3"], d["mode"], dn["mean_ranks"][nm], OC.severity_index(groups[nm], smin, smax), letters[nm]])
    S.append(sec_table(f"Опис за генотипами: {trait_name}", ["№", "Генотип", "n", "Медіана", "Q1", "Q3", "Мода", "Середній ранг", "Індекс розвитку, %", "Літери"],
                       desc_rows, [0, None, 0, 1, 1, 1, 0, 1, 1, None],
                       [f"Шкала {smin:g}–{smax:g}; «{'менше — краще' if lower_better else 'більше — краще'}»: генотипи впорядковано від кращого. "
                        f"Літери — за тестом Данна ({adjust}, α = {alpha}): однакова літера = не відрізняються.",
                        "Індекс розвитку (McKinney) — описовий; порівнюйте за рангами й літерами."],
                       tags=["good" if i == 0 else None for i in range(len(names))], key="desc"))
    k_ = len(names); N = dn["N"]; eta = (dn["kw_H"] - k_ + 1) / (N - k_) if N > k_ else float("nan")
    S.append(sec_table("Тест Крускала–Уолліса", ["Показник", "Значення"],
                       [["H", dn["kw_H"]], ["df", dn["kw_df"]], ["p", (dn["kw_p"], sig(dn["kw_p"]))], ["Розмір ефекту η²_H = (H − k + 1)/(N − k)", eta],
                        ["Спостережень N", N], ["Генотипів k", k_]], [None, 4],
                       ["Якщо p ≥ α, парні порівняння доцільно розглядати лише як описові."], key="kw"))
    prs = [[a_, b_, z, p, pa, "відрізняються" if pa < alpha else "не відрізняються"] for a_, b_, z, p, pa in dn["pairs"]]
    S.append(sec_table(f"Парні порівняння (Данн, поправка: {adjust})", ["Генотип A", "Генотип B", "z", "p", "p (з поправкою)", "Висновок"], prs, [None, None, 3, 4, 4, None],
                       [f"Поправку застосовано до {len(prs)} порівнянь."],
                       tags=["good" if r[4] < alpha else None for r in prs], key="dunn"))
    allc = np.unique(np.concatenate([np.asarray(groups[n], float) for n in names]))
    perc = [[100.0 * float(np.mean(np.asarray(groups[n], float) == c)) for c in allc] for n in names]
    S.append(sec_fig("Графік: розподіл балів", lambda f: U.fig_score_dist(f, names, list(allc), perc, f"Розподіл балів: {trait_name}",
                                                                            "(генотипи — від кращого до гіршого за середнім рангом)"),
                     size=(8.6, max(4.2, 0.36 * len(names) + 2.2)), key="dist"))
    S.append(sec_text("Пояснення", SCORES_HELP, key="help"))
    return S, warns


def sections_audpc(rows, headers, adjust="holm", alpha=0.05, ymax=None):
    tcols = list(range(2, len(headers)))
    tcols = [c for c in tcols if any(len(r) > c and r[c].strip() for r in rows)]
    if len(tcols) < 2: raise BreedingError("Потрібно щонайменше 2 заповнені стовпці обліків (заголовок — момент обліку).")
    first = None; times = []
    for c in tcols:
        t, d = OC.parse_time(headers[c], first)
        if d is not None and first is None: first = d
        times.append(t)
    if first is not None:   # перший облік — датою: перерахувати від першої дати
        times = [OC.parse_time(headers[c], first)[0] for c in tcols]
    if any(b <= a for a, b in zip(times, times[1:])): raise BreedingError("Моменти обліків (заголовки стовпців) мають зростати зліва направо.")
    ymx = None
    if ymax is not None and str(ymax).strip():
        ymx = to_float(ymax, "Максимум шкали")
    per, series = {}, {}
    for i, r in enumerate(rows):
        if not r[0]: raise BreedingError(f"У рядку {i + 1} немає назви генотипу.")
        ys = [to_float(r[c], f"рядок {i + 1}, облік «{headers[c]}»") for c in tcols]
        if any(v != v for v in ys): raise BreedingError(f"Рядок {i + 1}: є порожні значення обліків.")
        a = OC.audpc(times, ys, ymax=ymx)
        per.setdefault(r[0], []).append((a["audpc"], a["raudpc"])); series.setdefault(r[0], []).append(ys)
    if len(per) < 2: raise BreedingError("Потрібно щонайменше 2 генотипи.")
    groups = {k: [x[0] for x in v] for k, v in per.items()}
    dn = OC.dunn_test(groups, adjust)
    names = sorted(groups, key=lambda k: np.mean(groups[k]))
    letters = OC.compact_letters(names, dn["pairs"], alpha, order_by=names)
    warns = []
    small = [k for k, g in groups.items() if len(g) < 5]
    if small: warns.append("Менше 5 ділянок у генотипів: " + ", ".join(small[:6]) + " — літери значущості ненадійні.")
    if len(times) < 4: warns.append(f"Лише {len(times)} обліки: форма кривої розвитку хвороби відновлюється грубо, AUDPC чутлива до моментів обліків.")
    S = []
    rr = []
    for rank, nm in enumerate(names, 1):
        a = np.array([x[0] for x in per[nm]]); ra = np.array([x[1] for x in per[nm]])
        rr.append([rank, nm, len(a), float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else float("nan"), float(ra.mean()), dn["mean_ranks"][nm], letters[nm]])
    S.append(sec_table("AUDPC за генотипами", ["№", "Генотип", "n", "AUDPC (середнє)", "SD", "rAUDPC (середнє)", "Середній ранг", "Літери"], rr,
                       [0, None, 0, 2, 2, 4, 1, None],
                       [f"Облікiв: {len(times)}; тривалість {times[-1] - times[0]:g} діб. Менша AUDPC — стійкіший генотип (кращі першими).",
                        f"Літери — за тестом Данна ({adjust}, α = {alpha}) на значеннях AUDPC ділянок."],
                       tags=["good" if i == 0 else None for i in range(len(names))], key="audpc"))
    S.append(sec_table("Тест Крускала–Уолліса за AUDPC", ["Показник", "Значення"], [["H", dn["kw_H"]], ["df", dn["kw_df"]], ["p", (dn["kw_p"], sig(dn["kw_p"]))]], [None, 4], key="kw"))
    prs = [[a_, b_, z, p, pa, "відрізняються" if pa < alpha else "не відрізняються"] for a_, b_, z, p, pa in dn["pairs"]]
    S.append(sec_table(f"Парні порівняння (Данн, поправка: {adjust})", ["Генотип A", "Генотип B", "z", "p", "p (з поправкою)", "Висновок"], prs, [None, None, 3, 4, 4, None],
                       tags=["good" if r[4] < alpha else None for r in prs], key="dunn"))
    mean_curves = {nm: [float(np.mean([s[j] for s in series[nm]])) for j in range(len(times))] for nm in names}
    S.append(sec_fig("Графік: криві розвитку хвороби", lambda f: U.fig_curves(f, times, mean_curves, "Середній розвиток хвороби за генотипами", "Значення обліку"),
                     size=(8.4, 5.4), key="curves"))
    S.append(sec_text("Пояснення", SCORES_HELP, key="help"))
    return S, warns
