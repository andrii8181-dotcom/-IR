# sad_breeding.py — S.A.D. v2.1: розділ «Селекція та генетика» (вікна й побудова розділів результатів)
# -*- coding: utf-8 -*-
from sad_common import *
import re, math
import numpy as np
from scipy import stats as _st
import sad_gxe_core as GX
import sad_breeding_core as BC
import sad_control_core as CC
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig, ResultsViewer, render_section, do_export
from sad_stability_ancova import StabilityWindow

RF = ("Times New Roman", 11)
RB = ("Times New Roman", 11, "bold")


# ═══════════════════════════════════════════════════════════════
# Допоміжне
# ═══════════════════════════════════════════════════════════════
def to_float(s, where=""):
    s = str(s).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if s == "": return float("nan")
    try: return float(s)
    except ValueError: raise BC.BreedingError(f"{where}: «{s}» — не число.")


def sig(p):
    if p is None or (isinstance(p, float) and math.isnan(p)): return ""
    return "**" if p < 0.01 else ("*" if p < 0.05 else "")


GLOSSARY_STAB = """ЯК ЧИТАТИ ПОКАЗНИКИ СТАБІЛЬНОСТІ

Усі показники «менше — стабільніше», крім P (Лін–Бінс — менше краще, враховує й продуктивність) і TOP.
• S², CV — мінливість генотипу між середовищами (статичний підхід: чим менша, тим стабільніше).
• W² Вріке, σ² Шукли — внесок генотипу у взаємодію G×E (динамічний підхід). W² і σ² дають ОДНАКОВЕ
  ранжування (σ² — лінійна функція W²), тож їх не слід вважати двома незалежними доказами.
• bᵢ (регресія Фінлея–Вілкінсона/Ебергарта–Рассела): bᵢ = 1 — реакція як у середньому по набору; bᵢ > 1 —
  чутливий до покращення умов; bᵢ < 1 — слабо реагує. p(b=1) — t-тест (n−2 ст. свободи).
• S²d (Ебергарт–Рассел) — відхилення від регресії з поправкою на похибку; тест S²d = 0 потребує похибки за
  повторностями (імпорт «довгої таблиці»). Без неї показано S²δ — без поправки й без тесту.
• P (Лін–Бінс) — середній квадрат відстані до найкращого генотипу в кожному середовищі: об'єднує продуктивність
  і стабільність; Pf / Pu — окремо для сприятливих і несприятливих середовищ.
• S(1), S(2), S(3), S(6) (Хюн), NP(1–4) (Теннарасу), TOP (Фокс) — за рангами. Ранг 1 = найвищий показник.
  S(1), S(2) не залежать від напряму рангів; S(3), S(6) і NP(2–4) нормовані на середній ранг, тож залежать.
• Канг (RS): ранг продуктивності + ранг σ² Шукли; менше — краще (одночасно висока продуктивність і стабільність).
• ASV (AMMI): √[(SS₁/SS₂·IPCA1)² + IPCA2²]; YSI = ранг ASV + ранг середнього.

ВАЖЛИВО
• Різні індекси часто дублюють один одного — див. «Кореляція рангів». Обирайте 2–3 різнотипні (наприклад,
  ER + AMMI, як рекомендують порівняльні дослідження), а не рахуйте всі.
• Висновки про стабільність надійні лише за достатньої кількості середовищ (≥ 5–6) і генотипів.
• Для відомих генотипів у кожному середовищі потрібні повні дані: програма не підставляє пропущені значення.

Джерела: Pour-Aboughadareh A. et al. Plants 2022, 11(3):414; Wricke 1962; Shukla 1972; Eberhart & Russell 1966;
Lin & Binns 1988; Hühn 1979; Thennarasu 1995; Kang 1988; Purchase et al. 2000; Gollob 1968; Yan et al. 2000."""


# ═══════════════════════════════════════════════════════════════
# Розділи: стабільність (G×E)
# ═══════════════════════════════════════════════════════════════
def build_stability_sections(X, gn, en, r=1, mse=None, df_err=None, ca=None, svp="genotype"):
    """Додаткові розділи для вікна стабільності. Повертає (sections, warnings)."""
    X = GX.as_matrix(X, gn, en)
    g, e = X.shape
    warns = GX.design_warnings(g, e, mse)
    si = GX.stability_indices(X, mse, r, df_err)
    am = GX.ammi(X, r, mse, df_err)
    gg = GX.gge(X, svp); ww = GX.which_won_where(gg); ae = GX.aec_mean_stability(gg); ds = GX.discriminativeness(gg)
    S = []
    if ca is not None and ca["bartlett"]["p"] == ca["bartlett"]["p"] and ca["bartlett"]["p"] < 0.05:
        warns.append(f"Похибки в середовищах неоднорідні (Бартлетт, p = {ca['bartlett']['p']:.3f}): комбінований "
                     f"аналіз і тести можуть бути зміщені.")
    S.append(sec_text("⚠ Обмеження й пояснення",
                      ("ПОПЕРЕДЖЕННЯ\n" + "\n".join("• " + w for w in warns) + "\n\n" if warns else "") + GLOSSARY_STAB,
                      key="warn"))

    # 1. ANOVA
    if ca is not None:
        rows = []
        for k, lab in (("E", "Середовища (E)"), ("R(E)", "Повторності в середовищах"), ("G", "Генотипи (G)"),
                       ("GE", "Взаємодія G × E"), ("err", "Похибка")):
            rows.append([lab, ca["df"][k], ca["SS"][k], ca["MS"][k], ca["F"].get(k, float("nan")),
                         (ca["p"].get(k, float("nan")), sig(ca["p"].get(k))) if k in ca["p"] else float("nan")])
        rows.append(["Загальна", sum(ca["df"].values()), ca["SS"]["tot"], float("nan"), float("nan"), float("nan")])
        notes = ["Генотипи — фіксований фактор, середовища — випадковий: F(G) = MS_G/MS_GE; F(G×E) = MS_GE/MS_похибки; "
                 "F(E) = MS_E/MS_R(E).",
                 f"Тест Бартлетта однорідності похибок середовищ: χ² = {ca['bartlett']['chi2']:.2f}; "
                 f"p = {ca['bartlett']['p']:.3f}. Якщо p < 0,05 — комбінований аналіз ненадійний."]
        S.append(sec_table("ANOVA (за повторностями)", ["Джерело", "df", "SS", "MS", "F", "p"], rows,
                           [None, 0, 3, 3, 2, 4], notes, key="anova"))
    else:
        ef = GX.ge_effects(X)
        rows = [["Генотипи (G)", g - 1, r * ef["SSG"], r * ef["SSG"] / (g - 1)],
                ["Середовища (E)", e - 1, r * ef["SSE"], r * ef["SSE"] / (e - 1)],
                ["Взаємодія G × E", (g - 1) * (e - 1), r * ef["SSGE"], r * ef["SSGE"] / ((g - 1) * (e - 1))]]
        S.append(sec_table("ANOVA (за середніми)", ["Джерело", "df", "SS", "MS"], rows, [None, 0, 3, 3],
                           ["Розрахунок за середніми: F-тести неможливі без похибки за повторностями. "
                            "Використайте «Довга таблиця» для повного аналізу."], key="anova"))

    # 2. Параметричні
    rows = []
    for i in range(g):
        rows.append([gn[i], si["mean"][i], si["rank_by"]["Середнє (↑)"][i], si["S2"][i], si["CV"][i], si["W2"][i],
                     si["Shukla"][i], si["Pi"][i], si["Pi_fav"][i], si["Pi_unf"][i], si["b"][i], si["b_se"][i],
                     si["b_p"][i], si["S2delta"][i], si["S2d"][i], si["S2d_p"][i]])
    S.append(sec_table("Параметричні індекси",
                       ["Генотип", "Середнє", "Ранг сер.", "S²", "CV, %", "W²", "σ² Шукли", "P Ліна–Біннса", "Pf", "Pu",
                        "bᵢ", "SE(b)", "p(b=1)", "S²δ", "S²d", "p(S²d=0)"], rows,
                       [None, 3, 0, 4, 2, 4, 4, 4, 4, 4, 3, 3, 3, 4, 4, 3],
                       [f"Середовищ: {e}; сприятливих (середнє вище загального): {si['n_fav']}, несприятливих: {si['n_unf']}.",
                        "S²δ — відхилення від регресії без поправки на похибку; S²d = S²δ − MSE/r (потребує похибки)."],
                       key="param"))

    # 3. Непараметричні
    rows = [[gn[i], si["rank_mean"][i], si["S1"][i], si["S2r"][i], si["S3"][i], si["S6"][i], si["NP1"][i], si["NP2"][i],
             si["NP3"][i], si["NP4"][i], si["TOP"][i]] for i in range(g)]
    S.append(sec_table("Непараметричні індекси",
                       ["Генотип", "Сер. ранг", "S(1)", "S(2)", "S(3)", "S(6)", "NP(1)", "NP(2)", "NP(3)", "NP(4)", "TOP, %"],
                       rows, [None, 2, 3, 3, 3, 3, 3, 3, 3, 3, 0],
                       ["Ранг 1 — найвищий показник у середовищі. S — за рангами середніх; NP — за рангами значень, "
                        "скоригованих на ефект генотипу.",
                        "Тести значущості Z₁, Z₂ (Nassar–Hühn) не реалізовано: порівняння за величиною індексів орієнтовне."],
                       key="nonpar"))

    # 4. Кореляція рангів
    names, C = GX.rank_correlation(si["rank_by"])
    S.append(sec_table("Кореляція рангів між індексами", ["Індекс"] + names,
                       [[names[i]] + [float(C[i, j]) for j in range(len(names))] for i in range(len(names))],
                       [None] + [2] * len(names),
                       ["Кореляція Спірмена між рангами генотипів за різними індексами. ρ ≈ 1 — індекси дублюють один одного.",
                        *(_redundant_pairs(names, C))], key="rankcorr"))

    # 5. Зведення
    stab_keys = [k for k in si["rank_by"] if k not in ("Середнє (↑)", "TOP (↑)", "W² Вріке (↓)", "Pi Ліна–Біннса (↓)")]
    cons = np.mean([si["rank_by"][k] for k in stab_keys], axis=0)
    ymed = float(np.median(si["rank_by"]["Середнє (↑)"])); smed = float(np.median(cons))
    rows, tags = [], []
    rt = GX.ammi_rank_table(am)
    for i in range(g):
        good_y = si["rank_by"]["Середнє (↑)"][i] <= ymed; good_s = cons[i] <= smed
        typ, tag = (("стабільний і урожайний", "good") if good_y and good_s else
                    ("урожайний, але нестабільний", "warn") if good_y else
                    ("стабільний, але маловрожайний", "info") if good_s else ("нестабільний і маловрожайний", "bad"))
        rows.append([gn[i], si["mean"][i], si["rank_by"]["Середнє (↑)"][i], float(cons[i]), si["Kang_RS"][i],
                     rt["ASV"][i], rt["YSI"][i], typ]); tags.append(tag)
    S.append(sec_table("Зведення: продуктивність × стабільність",
                       ["Генотип", "Середнє", "Ранг сер.", "Сер. ранг стабільності", "Канг (RS)", "ASV", "YSI", "Тип"],
                       rows, [None, 3, 0, 2, 1, 4, 0, None],
                       [f"«Сер. ранг стабільності» — середній ранг за {len(stab_keys)} показниками стабільності "
                        f"(без W², що дублює σ², і без показників, де враховано продуктивність).",
                        "Тип: поділ за медіанами рангу продуктивності й рангу стабільності — орієнтовна класифікація, "
                        "не статистичний тест."], tags=tags, key="summary"))

    # 6. AMMI
    rows = [[f"IPCA{a['axis']}", a["SS"], a["df"], a["MS"], a["pct"], a["cum"], a["F"], (a["p"], sig(a["p"]))]
            for a in am["axes"]]
    S.append(sec_table("AMMI: осі взаємодії", ["Вісь", "SS", "df (Gollob)", "MS", "% взаємодії", "Накопич., %", "F", "p"], rows,
                       [None, 3, 0, 3, 1, 1, 2, 4],
                       ["Ступені свободи осі k за Gollob: g + e − 1 − 2k. F = MS осі / MSE; тест потребує похибки за повторностями." if mse
                        else "F-тести осей не виконано: немає похибки за повторностями (дані — середні)."], key="ammi_axes"))
    k2 = min(2, am["k_all"])
    hdr = ["Генотип", "Середнє"] + [f"IPCA{k + 1}" for k in range(k2)] + ["ASV", "Ранг ASV", "Ранг сер.", "YSI"]
    rows = [[gn[i], am["means"][i]] + [float(am["gen_scores"][i, k]) for k in range(k2)] +
            [rt["ASV"][i], rt["rank_ASV"][i], rt["rank_mean"][i], rt["YSI"][i]] for i in range(g)]
    S.append(sec_table("AMMI: генотипи й ASV", hdr, rows, [None, 3] + [3] * k2 + [4, 1, 1, 1],
                       ["ASV — AMMI stability value (Purchase et al. 2000): менше — стабільніше. Оцінки осей — "
                        "симетричне масштабування (u·√σ)."], key="ammi_gen"))
    rows = [[en[j], am["env_means"][j]] + [float(am["env_scores"][j, k]) for k in range(k2)] for j in range(e)]
    S.append(sec_table("AMMI: середовища", ["Середовище", "Середнє"] + [f"IPCA{k + 1}" for k in range(k2)], rows,
                       [None, 3] + [3] * k2, key="ammi_env"))
    S.append(sec_fig("AMMI1-біплот", lambda f: U.fig_ammi1(f, am, gn, en), size=(8.6, 5.8),
                     hint="Вісь X — середнє, вісь Y — IPCA1. Генотипи ближче до горизонталі 0 — стабільніші.", key="ammi1"))
    S.append(sec_fig("AMMI2-біплот", lambda f: U.fig_ammi2(f, am, gn, en), size=(7.2, 6.6), key="ammi2",
                     hint="IPCA1 × IPCA2: генотип поблизу стрілки середовища адаптований до нього."))
    # 7. GGE
    S.append(sec_fig("GGE: хто де переміг", lambda f: U.fig_gge_www(f, gg, ww, gn, en), size=(7.2, 6.6), key="www",
                     hint=f"GGE (SVP: {svp}); PC1 + PC2 = {gg['pct'][:2].sum():.1f} % GGE. Якщо менше ~60 % — біплот спрощує дані."))
    rows = []
    for j in range(e):
        rows.append([en[j], gn[ww["winners"][j]], float(ds["length"][j]), float(ds["representativeness"][j])])
    S.append(sec_table("GGE: переможці й середовища", ["Середовище", "Переможець (за PC1+PC2)", "Дискримінаційність", "Репрезентативність (cos)"],
                       rows, [None, None, 3, 3],
                       ["Дискримінаційність — довжина вектора середовища (здатність розрізняти генотипи); "
                        "репрезентативність — косинус кута з віссю середнього середовища (чим ближче до 1 — тим "
                        "типовіше середовище)."], key="www_tab"))
    S.append(sec_fig("GGE: продуктивність і стабільність", lambda f: U.fig_gge_aec(f, gg, ae, gn, en), size=(7.2, 6.6), key="aec",
                     hint="Вісь AEC (стрілка): праворуч — вища продуктивність; відстань від осі — нестабільність."))
    order = np.argsort(-ae["mean_score"])
    S.append(sec_table("GGE: ранги за AEC", ["Генотип", "Проекція (продуктивність)", "Нестабільність (відстань до осі)"],
                       [[gn[i], float(ae["mean_score"][i]), float(ae["instability"][i])] for i in order], [None, 3, 3],
                       ["Відсортовано за продуктивністю (спаданням)."], key="aec_tab"))
    return S, warns


def _redundant_pairs(names, C, thr=0.95):
    out = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = C[i, j]
            if v == v and abs(v) >= thr and not (names[i].startswith("Середнє") or names[j].startswith("Середнє")):
                out.append(f"Практично дублюють один одного: {names[i]} і {names[j]} (ρ = {v:.2f}).".replace(".", ","))
    return out[:12]


# ═══════════════════════════════════════════════════════════════
# Розділи: генетичні параметри
# ═══════════════════════════════════════════════════════════════
GENPAR_HELP = """ГЕНЕТИЧНІ ПАРАМЕТРИ — ЩО ЦЕ Й ЯК ЧИТАТИ

σ²g — генетична дисперсія, σ²e — дисперсія похибки, σ²p = σ²g + σ²e — фенотипова.
H² (широкосмугова спадковість) = σ²g/σ²p — частка фенотипової мінливості, зумовлена генотипом (на ділянку);
H² на середнє = σ²g/(σ²g + σ²e/r) — на рівні середніх за r повторностями (показано з 95 % довірчим інтервалом Кнаппа).
GCV, PCV — генотипний і фенотипний коефіцієнти варіації, %; GA = k·H²·σp — очікуваний генетичний прогрес
при доборі з інтенсивністю k (5 % → k = 2,06); GAM = GA/x̄·100 — у % до середнього.

Умовні категорії (Johnson та ін. 1955; Deshmukh та ін. 1986): H² — низька <30 %, середня 30–60 %, висока >60 %;
GAM — <10 %, 10–20 %, >20 %; GCV/PCV — <10 %, 10–20 %, >20 %. Це загальноприйняті, але ЕМПІРИЧНІ межі.

ОБМЕЖЕННЯ
• Оцінки стосуються цього середовища й цього набору генотипів, а не «спадковості ознаки взагалі».
• Високий H² без достатнього GA не гарантує прогрес (потрібні обидва).
• Від'ємна оцінка σ²g означає відсутність виявної генетичної мінливості — програма приймає її за 0.
• За кількома середовищами: σ²e = MSE; σ²ge = (MS_GE − MSE)/r; σ²g = (MS_G − MS_GE)/(r·e);
  σ²p = σ²g + σ²ge/e + σ²e/(r·e); H² = σ²g/σ²p.

Джерела: Johnson H.W., Robinson H.F., Comstock R.E. 1955; Knapp S.J., Stroup W.W., Ross W.M. 1985 (Crop Sci. 25:192)."""


def sections_genpar(rows, headers, multi, k_name="5 %"):
    """rows: list[list[str]] з колонками [Генотип, Середовище, Повторність, Ознака1, ...]."""
    k = BC.SELECTION_K[k_name]
    gen = [r[0] for r in rows]; env = [r[1] for r in rows]; rep = [r[2] for r in rows]
    traits = []
    for c in range(3, len(headers)):
        vals = [r[c] if c < len(r) else "" for r in rows]
        if any(v.strip() for v in vals): traits.append((c, headers[c].strip() or f"Ознака {c - 2}", vals))
    if not traits: raise BC.BreedingError("Немає жодного заповненого стовпця з ознакою.")
    results, banner = [], []
    for c, name, vals in traits:
        y = [to_float(v, f"«{name}», рядок {i + 1}") for i, v in enumerate(vals)]
        if any(v != v for v in y): raise BC.BreedingError(f"У стовпці «{name}» є порожні клітинки — дослід має бути збалансованим.")
        res = (BC.genetic_parameters_multi(gen, env, rep, y, k) if multi else BC.genetic_parameters_single(gen, rep, y, k))
        results.append((name, res))
        banner += [f"{name}: {w}" for w in res["warnings"]]
    S = []
    nanv = float("nan")
    if multi:
        hdr = ["Ознака", "Середнє", "σ²g", "σ²ge", "σ²e", "σ²p", "H²", "H² 95 % ДІ (від)", "(до)", "GCV, %", "PCV, %", "GA", "GAM, %", "H²", "GAM"]
        rows_ = [[nm, r["mean"], r["var_g"], r["var_ge"], r["var_e"], r["var_p"], r["h2"], r["h2_ci_F"][0], r["h2_ci_F"][1],
                  r["GCV"], r["PCV"], r["GA"], r["GAM"], r["cat_h2"], r["cat_gam"]] for nm, r in results]
        nd = [None, 3, 4, 4, 4, 4, 3, 3, 3, 2, 2, 3, 2, None, None]
        hdr[-2:] = ["Категорія H²", "Категорія GAM"]
    else:
        hdr = ["Ознака", "Середнє", "F", "p", "σ²g", "σ²e", "σ²p", "H² (ділянка)", "H² (середнє)", "H² сер. ДІ від", "ДІ до",
               "GCV, %", "PCV, %", "GA", "GAM, %", "Категорія H²", "Категорія GAM"]
        rows_ = [[nm, r["mean"], r["F"], (r["p"], sig(r["p"])), r["var_g"], r["var_e"], r["var_p"], r["h2_plot"], r["h2_mean"],
                  r["h2_mean_ci"][0], r["h2_mean_ci"][1], r["GCV"], r["PCV"], r["GA"], r["GAM"], r["cat_h2"], r["cat_gam"]]
                 for nm, r in results]
        nd = [None, 3, 2, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 3, 2, None, None]
    tags = [("good" if r["cat_h2"] == "високий" and r["cat_gam"] == "високий" else
             "warn" if r["cat_h2"] == "високий" else "bad" if r["var_g"] == 0 else None) for _, r in results]
    S.append(sec_table("Генетичні параметри", hdr, rows_, nd,
                       [f"Інтенсивність добору {k_name} (k = {k}).", "Зелене — високі H² і GAM; жовте — високий H², але малий GA; "
                        "червоне — генетична дисперсія не виявлена.",
                        "Категорії умовні: див. «Пояснення»."], tags=tags, key="genpar"))
    for nm, r in results:
        if multi:
            ca = r["ca"]; ro = []
            for kk, lab in (("E", "Середовища"), ("R(E)", "Повторності в середовищах"), ("G", "Генотипи"), ("GE", "G × E"), ("err", "Похибка")):
                ro.append([lab, ca["df"][kk], ca["SS"][kk], ca["MS"][kk], ca["F"].get(kk, nanv),
                           (ca["p"].get(kk, nanv), sig(ca["p"].get(kk))) if kk in ca["p"] else nanv])
        else:
            ro = [["Генотипи", r["df"]["gen"], r["SS"]["gen"], r["MS"]["gen"], r["F"], (r["p"], sig(r["p"]))],
                  ["Повторності", r["df"]["rep"], r["SS"]["rep"], r["MS"]["rep"], nanv, nanv],
                  ["Похибка", r["df"]["err"], r["SS"]["err"], r["MS"]["err"], nanv, nanv]]
        S.append(sec_table(f"ANOVA: {nm}", ["Джерело", "df", "SS", "MS", "F", "p"], ro, [None, 0, 3, 3, 2, 4], key=f"anova_{nm}"))
    labels = [nm for nm, _ in results]
    S.append(sec_fig("Графік: GCV, PCV і H²", lambda f: U.fig_bars(
        f, labels, {"GCV, %": [r["GCV"] for _, r in results], "PCV, %": [r["PCV"] for _, r in results],
                    "H², %": [100 * (r["h2"] if multi else r["h2_plot"]) for _, r in results]},
        "Генотипна й фенотипна мінливість та спадковість", "%"), key="genpar_fig"))
    S.append(sec_text("Пояснення", GENPAR_HELP, key="help"))
    return S, banner


# ═══════════════════════════════════════════════════════════════
# Розділи: комбінаційна здатність
# ═══════════════════════════════════════════════════════════════
LT_HELP = """КОМБІНАЦІЙНА ЗДАТНІСТЬ: ЛІНІЯ × ТЕСТЕР (Kempthorne 1957)

GCA (загальна комбінаційна здатність) — відхилення середнього лінії (тестера) за всіма схрещуваннями від загального
середнього; відображає переважно адитивну дію генів. SCA (специфічна) — відхилення конкретного схрещування від
очікуваного за GCA обох батьків; відображає домінування та епістаз.
F ліній і тестерів перевіряється проти взаємодії «лінії × тестери», а F L×T — проти похибки.
σ²gca = Cov(HS)сер; σ²sca = (MS_LT − MSE)/r. Для повністю інбредних ліній (F = 1): σ²A = 2σ²gca, σ²D = σ²sca.
Коефіцієнт Бейкера = 2σ²gca/(2σ²gca + σ²sca) — наближення до 1 означає переважно адитивну спадковість.
Знак «бажаного» ефекту залежить від ознаки: для врожайності — додатний, для висоти рослини чи вмісту білка в
певних селекційних завданнях — може бути від'ємним. Позначки * (p<0,05) і ** (p<0,01) — t-тест ефекту проти 0.

Обмеження: тестери зазвичай нечисленні, тому F-тести ліній/тестерів мають мало ступенів свободи (df = (l−1)(t−1))."""

DIALLEL_HELP = """ДІАЛЕЛЬНИЙ АНАЛІЗ ЗА ГРІФФІНГОМ (1956)

Метод 2: батьківські форми + F₁ (без реципроків), p(p+1)/2 генотипів. Метод 4: лише F₁, p(p−1)/2.
Модель xᵢⱼ = μ + gᵢ + gⱼ + sᵢⱼ + e. Ефекти знайдено методом найменших квадратів з обмеженням Σg = 0
(метод 2: Σⱼ sᵢⱼ + sᵢᵢ = 0; метод 4: Σ_{j≠i} sᵢⱼ = 0).
Модель I (фіксована): висновки лише про ці батьківські форми; F = MS/MSe′. Модель II (випадкова): батьки — вибірка
з популяції; F(GCA) = MS_gca/MS_sca; σ²g = (MS_g − MS_s)/(p+2) [метод 2] чи /(p−2) [метод 4]; σ²s = MS_s − MSe′.
MSe′ = MSE/r — похибка середнього. Реципрокні схрещування усереднюються (реципрокні ефекти — методи 1, 3 — не аналізуються).
Позначки * (p<0,05) і ** (p<0,01) — t-тест GCA проти 0 (SE за Гріффінгом)."""


def _gca_rows(names, g, se, df, means=None):
    rows, tags = [], []
    for i, n in enumerate(names):
        t = g[i] / se; p = float(2 * _st.t.sf(abs(t), df))
        row = [n] + ([means[i]] if means is not None else []) + [(float(g[i]), sig(p)), se, float(t), p]
        rows.append(row); tags.append("good" if (p < 0.05 and g[i] > 0) else "bad" if (p < 0.05 and g[i] < 0) else None)
    return rows, tags


def sections_line_tester(rows, trait_col, trait_name):
    L = [r[0] for r in rows]; T = [r[1] for r in rows]; R = [r[2] for r in rows]
    y = [to_float(r[trait_col], f"«{trait_name}», рядок {i + 1}") for i, r in enumerate(rows)]
    res = BC.line_tester(L, T, R, y)
    nanv = float("nan"); S = []; df = res["df"]
    an = []
    for kk, lab in (("rep", "Повторності"), ("cross", "Схрещування"), ("line", "Лінії"), ("tester", "Тестери"),
                    ("lt", "Лінії × тестери"), ("err", "Похибка")):
        an.append([lab, df[kk], res["SS"][kk], res["MS"][kk], res["F"].get(kk, nanv),
                   (res["p"][kk], sig(res["p"][kk])) if kk in res["p"] else nanv])
    an.append(["Загальна", df["rep"] + df["cross"] + df["err"], res["SS"]["tot"], nanv, nanv, nanv])
    S.append(sec_table(f"ANOVA: {trait_name}", ["Джерело", "df", "SS", "MS", "F", "p"], an, [None, 0, 3, 3, 2, 4],
                       ["F ліній і тестерів — проти «лінії × тестери»; F L×T і схрещувань — проти похибки."], key="anova"))
    meanl = res["cross_means"].mean(axis=1); meant = res["cross_means"].mean(axis=0)
    rl, tl = _gca_rows(res["lines"], res["gca_line"], res["se"]["gca_line"], df["err"], meanl)
    S.append(sec_table("GCA ліній", ["Лінія", "Середнє", "GCA", "SE", "t", "p"], rl, [None, 3, 3, 3, 2, 4],
                       [f"Позначки: * p<0,05, ** p<0,01. Зелене — значущий додатний ефект, червоне — значущий від'ємний. "
                        f"SE(gᵢ − gₖ) = {res['se']['diff_line']:.3f}."], tags=tl, key="gca_l"))
    rt, tt = _gca_rows(res["testers"], res["gca_tester"], res["se"]["gca_tester"], df["err"], meant)
    S.append(sec_table("GCA тестерів", ["Тестер", "Середнє", "GCA", "SE", "t", "p"], rt, [None, 3, 3, 3, 2, 4],
                       [f"SE(gⱼ − gₖ) = {res['se']['diff_tester']:.3f}."], tags=tt, key="gca_t"))
    sc_rows = []
    for i, ln in enumerate(res["lines"]):
        row = [ln]
        for j in range(len(res["testers"])):
            t_ = res["sca"][i, j] / res["se"]["sca"]; p_ = float(2 * _st.t.sf(abs(t_), df["err"]))
            row.append((float(res["sca"][i, j]), sig(p_)))
        sc_rows.append(row)
    S.append(sec_table("SCA (лінії × тестери)", ["Лінія \\ тестер"] + list(res["testers"]), sc_rows,
                       [None] + [3] * len(res["testers"]),
                       [f"SE(SCA) = {res['se']['sca']:.3f}; * p<0,05, ** p<0,01."], key="sca"))
    vr = [["σ²gca (середня Cov(HS))", res["var_gca"]], ["Cov(HS) ліній", res["cov_hs_line"]], ["Cov(HS) тестерів", res["cov_hs_tester"]],
          ["σ²sca = (MS_LT − MSE)/r", res["var_sca"]], ["Коефіцієнт Бейкера 2σ²gca/(2σ²gca + σ²sca)", res["baker"]],
          ["Внесок ліній у SS схрещувань, %", res["contrib"]["line"]], ["Внесок тестерів, %", res["contrib"]["tester"]],
          ["Внесок «лінії × тестери», %", res["contrib"]["lt"]]]
    S.append(sec_table("Компоненти дисперсії й внески", ["Показник", "Значення"], vr, [None, 4],
                       ["Від'ємні оцінки компонентів приймаються за 0 (див. попередження)."], key="var"))
    S.append(sec_fig("Графік: GCA ліній і тестерів", lambda f: U.fig_effects(
        f, [("Лінії", [str(x) for x in res["lines"]], list(res["gca_line"]), [res["se"]["gca_line"]] * len(res["lines"])),
            ("Тестери", [str(x) for x in res["testers"]], list(res["gca_tester"]), [res["se"]["gca_tester"]] * len(res["testers"]))],
        f"Ефекти GCA (±SE): {trait_name}", "GCA"), key="fig_gca"))
    S.append(sec_fig("Графік: SCA (теплова карта)", lambda f: U.fig_heat(
        f, res["sca"], [str(x) for x in res["lines"]], [str(x) for x in res["testers"]], f"SCA: {trait_name}", "SCA"), key="fig_sca"))
    S.append(sec_text("Пояснення", LT_HELP, key="help"))
    return S, res["warnings"]


def sections_diallel(rows, trait_col, trait_name, method=2, model="I"):
    P1 = [r[0] for r in rows]; P2 = [r[1] for r in rows]; R = [r[2] for r in rows]
    y = [to_float(r[trait_col], f"«{trait_name}», рядок {i + 1}") for i, r in enumerate(rows)]
    res = BC.diallel_griffing(P1, P2, R, y, method=method, model=model)
    nanv = float("nan"); S = []; df = res["df"]; p = res["p"]; F = res["F"]
    an = [["GCA", df["gca"], res["SS"]["gca"], res["MS"]["gca"], F["gca"], (p["gca"], sig(p["gca"]))],
          ["SCA", df["sca"], res["SS"]["sca"], res["MS"]["sca"], F["sca"], (p["sca"], sig(p["sca"]))],
          ["Генотипи (GCA + SCA)", df["geno"], res["SS"]["geno"], nanv, nanv, nanv],
          ["Повторності", df["rep"], res["SS"]["rep"], nanv, nanv, nanv],
          ["Похибка", df["err"], res["SS"]["err"], res["MSE_plot"], nanv, nanv]]
    note = ("Модель I: F = MS/MSe′ (MSe′ = MSE/r). SS наведено для повних даних (× r), MS GCA і SCA — за середніми."
            if model == "I" else
            "Модель II: F(GCA) = MS_gca/MS_sca; F(SCA) = MS_sca/MSe′. SS — для повних даних (× r), MS GCA і SCA — за середніми.")
    S.append(sec_table(f"ANOVA: {trait_name} (метод {res['method']}, модель {model})",
                       ["Джерело", "df", "SS", "MS", "F", "p"], an, [None, 0, 3, 4, 2, 4], [note], key="anova"))
    gr, tg = _gca_rows(res["parents"], res["gca"], res["se_gca"], df["err"])
    S.append(sec_table("GCA батьківських форм", ["Батьківська форма", "GCA", "SE", "t", "p"], gr, [None, 3, 3, 2, 4],
                       [f"SE(ĝᵢ − ĝⱼ) = {res['se_gca_diff']:.3f}. Зелене — значущий додатний ефект, червоне — від'ємний."],
                       tags=tg, key="gca"))
    pn = res["parents"]; sc_rows = []
    for i in range(len(pn)):
        row = [pn[i]]
        for j in range(len(pn)):
            v = res["sca"][i, j]
            row.append(float("nan") if v != v else float(v))
        sc_rows.append(row)
    S.append(sec_table("SCA (матриця)", ["Батько \\ Батько"] + [str(x) for x in pn], sc_rows, [None] + [3] * len(pn),
                       ["Діагональ — SCA батьківських форм (лише метод 2)."], key="sca"))
    vr = [["σ²gca", res["var_gca"]], ["σ²sca", res["var_sca"]], ["Коефіцієнт Бейкера", res["baker"]],
          ["Похибка середнього MSe′", res["Me"]]]
    S.append(sec_table("Компоненти дисперсії", ["Показник", "Значення"], vr, [None, 4],
                       ["Для моделі I компоненти — лише орієнтовні (ефекти фіксовані); для генетичної інтерпретації обирайте модель II."
                        if model == "I" else "Від'ємні оцінки приймаються за 0."], key="var"))
    S.append(sec_fig("Графік: GCA батьківських форм", lambda f: U.fig_effects(
        f, [("GCA", [str(x) for x in pn], list(res["gca"]), [res["se_gca"]] * len(pn))], f"GCA (±SE): {trait_name}", "GCA"), key="fig_gca"))
    S.append(sec_fig("Графік: SCA (теплова карта)", lambda f: U.fig_heat(
        f, res["sca"], [str(x) for x in pn], [str(x) for x in pn], f"SCA: {trait_name}", "SCA"), key="fig_sca"))
    S.append(sec_text("Пояснення", DIALLEL_HELP, key="help"))
    return S, res["warnings"]


# ═══════════════════════════════════════════════════════════════
# Розділи: стресостійкість
# ═══════════════════════════════════════════════════════════════
STRESS_HELP = """ІНДЕКСИ СТРЕСОСТІЙКОСТІ

Yp — урожай у сприятливих умовах, Ys — у стресових (посуха, засолення, холод тощо); Ȳp, Ȳs — середні по набору;
SI = 1 − Ȳs/Ȳp — інтенсивність стресу.
TOL = Yp − Ys (менше — стійкіше); MP = (Yp + Ys)/2; GMP = √(Yp·Ys); HM = 2·Yp·Ys/(Yp + Ys);
SSI = (1 − Ys/Yp)/SI (менше — стійкіше); STI = Yp·Ys/Ȳp²; YI = Ys/Ȳs; YSI = Ys/Yp; RSI = (Ys/Yp)/(Ȳs/Ȳp).
Критерій Фернандеса (1992): найкорисніший індекс — той, що корелює і з Yp, і з Ys; він відбирає генотипи групи A
(високі в обох умовах). TOL і SSI відбирають генотипи, стабільні, але не обов'язково урожайні.

ОБМЕЖЕННЯ
• Індекси мають змістовну інтерпретацію лише за вираженого стресу (SI помітно > 0).
• Усі індекси — функції двох чисел на генотип; вони не замінюють багатосередовищних випробувань.
• Висновки про стійкість потребують повторення в кількох роках/локаціях.

Джерела: Rosielle & Hamblin 1981; Fischer & Maurer 1978; Fischer & Wood 1979; Bouslama & Schapaugh 1984;
Fernandez 1992; Gavuzzi et al. 1997; Jafari et al. 2009."""


def sections_stress(rows, trait_name="Урожайність"):
    names = [r[0] or f"G{i + 1}" for i, r in enumerate(rows)]
    yp = [to_float(r[1], f"Yp, рядок {i + 1}") for i, r in enumerate(rows)]
    ys = [to_float(r[2], f"Ys, рядок {i + 1}") for i, r in enumerate(rows)]
    st = BC.stress_indices(yp, ys)
    nanv = float("nan"); S = []
    keys = [k for k, *_ in BC.STRESS_INFO]
    rr = [[names[i], st["Yp"][i], st["Ys"][i]] + [float(st[k][i]) for k in keys] + [st["group"][i]] for i in range(st["n"])]
    tg = [("good" if st["group"][i] == "A" else "info" if st["group"][i] == "C" else "warn" if st["group"][i] == "B" else "bad")
          for i in range(st["n"])]
    S.append(sec_table("Індекси стресостійкості", ["Генотип", "Yp", "Ys"] + keys + ["Група"], rr,
                       [None, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, None],
                       [f"Інтенсивність стресу SI = {st['SI']:.3f}; Ȳp = {st['mean_Yp']:.3f}; Ȳs = {st['mean_Ys']:.3f}.",
                        "Група: A — високі Yp і Ys; B — високий лише Yp; C — високий лише Ys; D — низькі в обох (за порівнянням із середніми)."],
                       tags=tg, key="idx"))
    rk = st["ranks"]; rlab = list(rk)
    rr = [[names[i]] + [float(rk[k][i]) for k in rlab] + [float(st["rank_mean"][i]), float(st["rank_sd"][i])] for i in range(st["n"])]
    order = np.argsort(st["rank_mean"]); top = set(order[:3].tolist())
    S.append(sec_table("Ранги й середній ранг", ["Генотип"] + rlab + ["Сер. ранг", "SD рангів"], rr,
                       [None] + [1] * len(rlab) + [2, 2],
                       ["Ранг 1 — найкращий (для TOL і SSI — найменше значення, для решти — найбільше). Зелене — три найкращі за середнім рангом."],
                       tags=["good" if i in top else None for i in range(st["n"])], key="ranks"))
    cr = [[k, st["cors"][k][0], st["cors"][k][1], min(st["cors"][k])] for k in st["cors"]]
    cr.sort(key=lambda r: -r[3])
    S.append(sec_table("Кореляція індексів з Yp та Ys", ["Індекс", "r з Yp", "r з Ys", "min(r)"], cr, [None, 3, 3, 3],
                       ["Критерій Фернандеса: найкорисніший індекс корелює і з Yp, і з Ys (перший у списку — найбільше min(r)). "
                        "Для 8–10 генотипів кореляції дуже нестійкі."],
                       tags=["good"] + [None] * (len(cr) - 1), key="cors"))
    S.append(sec_fig("Графік: групи Фернандеса", lambda f: U.fig_stress(f, st, names), size=(8.4, 6.2), key="fig"))
    S.append(sec_text("Пояснення", STRESS_HELP, key="help"))
    return S, st["warnings"]


# ═══════════════════════════════════════════════════════════════
# Розділи: шляховий аналіз
# ═══════════════════════════════════════════════════════════════
PATH_HELP = """ШЛЯХОВИЙ АНАЛІЗ (Wright 1921; Dewey & Lu 1959)

Розкладає кореляцію між ознакою-причиною X і результатом Y на ПРЯМИЙ ефект p (стандартизований коефіцієнт регресії)
і НЕПРЯМІ ефекти через інші ознаки (r(X,Xⱼ)·pⱼ): r(X,Y) = p + Σ непрямих.
Залишковий ефект √(1 − R²) показує частку мінливості Y, не пояснену ознаками в моделі.

ЧОМУ ЦЕ ПОТРЕБУЄ ОБЕРЕЖНОСТІ
• Шляховий аналіз — не доказ причинності: напрям зв'язків задає дослідник, а не дані.
• Колінеарність (VIF > 10) робить прямі ефекти нестійкими, можуть з'явитися «хибні» від'ємні ефекти.
• Потрібно щонайменше ~5 спостережень на кожну ознаку; ознаки мають бути змістовно причинними щодо Y.
• SE і p — за стандартизованою регресією; для малих вибірок вони орієнтовні.

Джерела: Wright S. 1921 J. Agric. Res. 20:557; Dewey D.R., Lu K.H. 1959 Agron. J. 51:515."""


def sections_path(rows, headers):
    k = len(headers) - 1
    names = [h.strip() or f"X{i + 1}" for i, h in enumerate(headers[:k])]; yname = headers[-1].strip() or "Y"
    X = [[to_float(r[j], f"«{names[j]}», рядок {i + 1}") for j in range(k)] for i, r in enumerate(rows)]
    y = [to_float(r[k], f"«{yname}», рядок {i + 1}") for i, r in enumerate(rows)]
    pa = BC.path_analysis(X, y, names, yname)
    S = []
    hdr = ["Ознака", "Прямий ефект p", "SE", "t", "p-значення", "VIF"] + [f"через {n}" for n in names] + ["Сума непрямих", "r(X, Y)"]
    rr = []
    for i in range(k):
        ind = [float(pa["indirect"][i, j]) if i != j else float("nan") for j in range(k)]
        rr.append([names[i], float(pa["direct"][i]), float(pa["se"][i]), float(pa["t"][i]), float(pa["p"][i]), float(pa["vif"][i])]
                  + ind + [float(pa["indirect"][i].sum()), float(pa["rxy"][i])])
    tg = ["bad" if pa["vif"][i] > 10 else None for i in range(k)]
    S.append(sec_table("Прямі й непрямі ефекти", hdr, rr, [None, 3, 3, 2, 4, 2] + [3] * k + [3, 3],
                       [f"n = {pa['n']}; R² = {pa['R2']:.3f}; залишковий ефект = {pa['residual']:.3f}; число зумовленості = {pa['cond']:.1f}.",
                        "Червоне — VIF > 10 (сильна колінеарність: прямий ефект нестійкий)."], tags=tg, key="effects"))
    S.append(sec_table("Кореляційна матриця ознак", [""] + names + [yname],
                       [[names[i]] + [float(pa["Rxx"][i, j]) for j in range(k)] + [float(pa["rxy"][i])] for i in range(k)],
                       [None] + [3] * (k + 1), key="corr"))
    S.append(sec_fig("Діаграма шляхів", lambda f: U.fig_path_diagram(f, pa), size=(8.4, 5.8), key="diag"))
    S.append(sec_fig("Кореляція та прямий ефект", lambda f: U.fig_path_bars(f, pa), key="bars"))
    S.append(sec_text("Пояснення", PATH_HELP, key="help"))
    return S, pa["warnings"]


# ═══════════════════════════════════════════════════════════════
# Розділи: порівняння зі стандартом (Дуннетт)
# ═══════════════════════════════════════════════════════════════
CONTROL_HELP = """ПОРІВНЯННЯ ЗІ СТАНДАРТОМ (тест Дуннетта)

Кожен номер (сорт, лінію) порівнюють зі стандартом (контролем). Номерів багато, тому окремі t-тести (НІР) дають
забагато «істотно кращих» випадково: при 6 порівняннях імовірність хоча б одного хибного спрацювання сягає
близько 20 % замість 5 %. Тест Дуннетта (1955) тримає цю імовірність на рівні α для всього набору порівнянь.

ЩО ПОКАЗАНО
• Середнє — МНК-середнє з урахуванням повторностей (блоків); за збалансованого плану збігається зі звичайним.
• % до стандарту = середнє номера / середнє стандарту × 100.
• p (Дуннетт) — поправлене p-значення; p (без поправки) — для порівняння з НІР.
• Інтервал — одночасний довірчий інтервал Дуннетта для різниці «номер − стандарт».
• Істотна різниця Дуннетта = c·SE(різниці) — найменша різниця, яку можна визнати достовірною.

КІЛЬКА СТАНДАРТІВ. Вкажіть їх через «;» — порівняння виконується із СЕРЕДНІМ стандартів.
ОДНОСТОРОННІЙ ТЕСТ («більше стандарту») доречний лише тоді, коли ви заздалегідь, до експерименту, цікавитесь
виключно перевищенням стандарту; інакше обирайте двобічний.

ОБМЕЖЕННЯ
• Номер і стандарт мають зустрічатися хоча б в одному блоці; повторності стандарту підвищують надійність.
• Стандарт без повторностей: похибка оцінюється за іншими номерами — висновки менш надійні.
• Однорідність дисперсій і нормальність залишків припускаються — перевіряйте їх у блоці ANOVA.

Джерело: Dunnett C.W. 1955 JASA 50:1096."""


def control_tables(res, trait_name, alpha, alternative):
    """Таблиці й графік порівняння зі стандартом за готовим результатом (спільні для МНК і змішаної моделі)."""
    S = []
    tags = ["good" if (r["sig"] and r["diff"] > 0) else "bad" if (r["sig"] and r["diff"] < 0) else None for r in res["rows"]]
    tr = [[r["entry"], r["n"], r["mean"], r["se"], r["pct"], r["diff"], r["se_diff"], r["t"],
           (r["p_dunnett"], sig(r["p_dunnett"])), r["p_lsd"], r["ci_lo"], r["ci_hi"], r["dunnett_diff"], r["verdict"]] for r in res["rows"]]
    alt_txt = {"two-sided": "двобічний", "greater": "односторонній (більше стандарту)", "less": "односторонній (менше стандарту)"}[alternative]
    head = (f"Стандарт: {', '.join(res['control'])}; середнє = {res['control_mean']:.3f} (SE {res['control_se']:.3f}). "
            + (f"MSE = {res['mse']:.4g}; df = {res['df']}; CV = {res['cv']:.1f} %; " if res["mse"] == res["mse"] else f"df = {res['df']}; ")
            + f"α = {alpha}; тест {alt_txt}.")
    S.append(sec_table(f"Порівняння зі стандартом: {trait_name}",
                       ["Номер", "n", "Середнє", "SE", "% до стандарту", "Різниця", "SE різниці", "t", "p (Дуннетт)", "p (без поправки)",
                        "ДІ від", "ДІ до", "Істотна різниця Дуннетта", "Висновок"], tr,
                       [None, 0, 3, 3, 1, 3, 3, 2, 4, 4, 3, 3, 3, None],
                       [head, "* p < 0,05, ** p < 0,01 (поправлені за Дуннеттом). Зелене — достовірно вище стандарту, червоне — нижче."],
                       tags=tags, key="control"))
    order = sorted(res["rows"], key=lambda r: -r["pct"])
    S.append(sec_table("Рейтинг за % до стандарту", ["Місце", "Номер", "% до стандарту", "Різниця", "Висновок"],
                       [[i + 1, r["entry"], r["pct"], r["diff"], r["verdict"]] for i, r in enumerate(order)], [0, None, 1, 3, None],
                       ["Рейтинг лише описовий; про достовірність судіть за стовпцем «Висновок»."],
                       tags=["good" if (r["sig"] and r["diff"] > 0) else "bad" if (r["sig"] and r["diff"] < 0) else None for r in order], key="rank"))
    S.append(sec_fig("Графік: різниця від стандарту", lambda f: U.fig_forest(f, res, f"{trait_name}: номер − стандарт"),
                     size=(8.4, max(4.0, 0.34 * len(res["rows"]) + 1.8)), key="forest"))
    return S


def sections_control(rows, value_col, trait_name, controls, use_blocks=True, alpha=0.05, alternative="two-sided"):
    ent = [r[0] for r in rows]
    if any(not e for e in ent): raise BC.BreedingError("У деяких рядках немає назви номера.")
    y = [to_float(r[value_col], f"«{trait_name}», рядок {i + 1}") for i, r in enumerate(rows)]
    if any(v != v for v in y): raise BC.BreedingError(f"У стовпці «{trait_name}» є порожні клітинки.")
    blocks = [r[1] for r in rows] if use_blocks and any(r[1] for r in rows) else None
    if blocks is not None and any(not b for b in blocks): raise BC.BreedingError("Повторність/блок указано не в усіх рядках.")
    res = CC.compare_to_control(ent, y, controls, blocks, alpha, alternative)
    S = control_tables(res, trait_name, alpha, alternative)
    S.append(sec_text("Пояснення", CONTROL_HELP, key="help"))
    return S, res["warnings"]
