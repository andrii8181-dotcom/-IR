# sad_mixed_sections.py — S.A.D. v2.1: розділи результатів змішаної моделі (REML/BLUP)
# -*- coding: utf-8 -*-
import math
import numpy as np
import sad_mixed_core as MX
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError
from sad_breeding import to_float, sig, control_tables
import sad_control_core as CC

MIXED_HELP = """ЗМІШАНА МОДЕЛЬ (REML / BLUP) — ЩО ЦЕ І НАВІЩО

Класичний дисперсійний аналіз потребує збалансованого досліду. У селекції дані майже ніколи не збалансовані:
номери випадають між роками, ділянки гинуть, нові форми з'являються пізніше. Змішана модель аналізує такі дані
без викидання спостережень.

КОМПОНЕНТИ ДИСПЕРСІЇ оцінено методом REML (обмежена максимальна правдоподібність). SE — асимптотичні (за
гессіаном); поблизу нуля вони ненадійні. Тест відношення правдоподібностей (LRT) перевіряє, чи потрібен ефект у
моделі; p — за сумішшю χ²₀/χ²₁, бо нульова гіпотеза (σ² = 0) лежить на межі.

BLUP (найкращий лінійний незміщений прогноз) — оцінка генотипного ефекту з усадкою до середнього: чим менше даних
про номер (і чим менша генетична мінливість), тим сильніше значення стягується до середнього. Це коректніше за
звичайне середнє для вибору кращих номерів, коли повторностей мало чи вони різні.
• SE — похибка прогнозу (PEV); надійність = 1 − PEV/σ²g (чим ближче до 1, тим точніший прогноз).
• Спадковість за Каллісом та ін. (2006): H² = 1 − v̄Δ/(2σ²g), де v̄Δ — середня дисперсія різниці двох BLUP.
  У збалансованих дослідах збігається з класичною спадковістю на рівні середніх.

ФІКСОВАНИЙ ЧИ ВИПАДКОВИЙ ГЕНОТИП
• Випадковий — коли номери є вибіркою з ширшої сукупності й потрібна оцінка мінливості та відбір (BLUP).
• Фіксований — коли цікавлять саме ці номери, порівняння між ними й зі стандартом (скориговані середні).

ОБМЕЖЕННЯ
• Припускається нормальність і однорідність залишків; перевіряйте залишки окремо.
• Для надійних оцінок потрібно ≥ 10 генотипів (краще ≥ 30) і, для серії дослідів, ≥ 3 середовищ.
• Якщо компонент дисперсії дорівнює нулю (на межі) — відповідний ефект у даних не виявлено.

Джерела: Patterson & Thompson 1971; Henderson 1975; Cullis, Smith, Coombes 2006 (JABES 11:381)."""


def mixed_factors(rows, trait_col, mode, use_blocks, rep_given):
    gen = [r[0] for r in rows]
    if any(not g for g in gen): raise BreedingError("У деяких рядках немає назви генотипу.")
    f = {"gen": gen}
    if mode == "met":
        env = [r[1] for r in rows]
        if any(not e for e in env): raise BreedingError("Режим «кілька середовищ» вимагає назви середовища в кожному рядку.")
        f["env"] = env; f["ge"] = [f"{g}|{e}" for g, e in zip(gen, env)]
        base = env
    else:
        base = ["·"] * len(rows)
    if rep_given:
        rep = [r[2] for r in rows]
        if any(not x for x in rep): raise BreedingError("Повторність указано не в усіх рядках.")
        f["rep"] = [f"{b}|{x}" for b, x in zip(base, rep)]
    if use_blocks:
        blk = [r[3] for r in rows]
        if any(not x for x in blk): raise BreedingError("Блок указано не в усіх рядках.")
        rp = f.get("rep", [f"{b}|" for b in base])
        f["blk"] = [f"{a}|{x}" for a, x in zip(rp, blk)]
    return f


def mixed_spec(mode, geno_random, rep_random, use_blocks, rep_given):
    fixed, random = [], []
    if mode == "met": fixed.append("env")
    if rep_given: (random if rep_random else fixed).append("rep")
    if geno_random:
        random.append("gen")
        if mode == "met": random.append("ge")
    else:
        fixed.append("gen")
        if mode == "met": random.append("ge")
    if use_blocks: random.append("blk")
    return fixed, random


TERM_LABEL = {"gen": "Генотип (σ²g)", "ge": "Генотип × середовище (σ²ge)", "rep": "Повторності", "blk": "Блок у повторності", "Залишок": "Залишок (σ²e)"}


def env_means(res):
    """Середнє по кожному середовищу з фіксованої частини (перетин + ефект середовища)."""
    meta = res["x_meta"]; beta = res["beta"]; fl = res["fixed_levels"].get("env")
    if not fl: return None
    out = {fl[0]: float(beta[0])}
    for i, (t, l) in enumerate(meta):
        if t == "env": out[l] = float(beta[0] + beta[i])
    return out


def avg_pair_var(res, term="gen"):
    """Середня дисперсія різниці двох скоригованих середніх: [q·tr(S) − 1ᵀS1]/(q(q−1)/2), S = V Cβ Vᵀ."""
    lv, V = MX.lsmeans_matrix(res, term)
    S = V @ res["beta_cov"] @ V.T; q = len(lv)
    return float((q * np.trace(S) - np.sum(S)) / (q * (q - 1) / 2.0))


def sections_mixed(rows, trait_col, trait_name, mode="met", geno_random=True, rep_random=False, use_blocks=False,
                   lrt=True, y_override=None, controls=None, alpha=0.05, alternative="two-sided"):
    rep_given = any(r[2] for r in rows)
    y = [to_float(r[trait_col], f"«{trait_name}», рядок {i + 1}") for i, r in enumerate(rows)] if y_override is None else y_override
    if any(v != v for v in y): raise BreedingError(f"У стовпці «{trait_name}» є порожні клітинки: змішана модель допускає пропущені "
                                                  f"ДІЛЯНКИ (приберіть рядок), але не порожні значення в рядках.")
    fac = mixed_factors(rows, trait_col, mode, use_blocks, rep_given)
    fixed, random = mixed_spec(mode, geno_random, rep_random, use_blocks, rep_given)
    pev = ["gen"] if geno_random else []
    res = MX.fit_mixed(y, fac, fixed, random, pev_terms=pev)
    warns = []
    ngen = len(set(fac["gen"])); n = len(y)
    if ngen < 10: warns.append(f"Лише {ngen} генотипів: оцінки компонентів дисперсії й BLUP дуже неточні.")
    if mode == "met" and len(set(fac["env"])) < 3: warns.append("Менше 3 середовищ: компонента «генотип × середовище» оцінюється неточно.")
    if not res["converged"]: warns.append("Оптимізація не досягла повної збіжності — оцінки орієнтовні; перевірте дані.")
    for t in res["boundary"]:
        warns.append(f"Компонент «{TERM_LABEL.get(t, t)}» практично дорівнює нулю (на межі): відповідний ефект у даних не виявлено; "
                     f"його SE ненадійні.")
    S = []
    # 1. компоненти дисперсії
    tot = sum(res["sigma2"].values())
    lrts = {}
    if lrt:
        for t in res["term_names"][:-1]:
            try:
                red = MX.refit_without(res, y, fac, fixed, random, t)
                lrts[t] = MX.lrt_random_term(res, red)
            except BreedingError:
                lrts[t] = (float("nan"), float("nan"))
    rows_v = []
    for t in res["term_names"]:
        v = res["sigma2"][t]; lr, pl = lrts.get(t, (float("nan"), float("nan")))
        rows_v.append([TERM_LABEL.get(t, t), v, res["sigma2_se"].get(t, float("nan")), 100 * v / tot, lr, (pl, sig(pl)) if pl == pl else float("nan")])
    S.append(sec_table(f"Компоненти дисперсії: {trait_name}", ["Ефект", "σ²", "SE", "% від суми", "LRT χ²", "p (LRT)"], rows_v,
                       [None, 4, 4, 1, 2, 4],
                       [f"n = {n}; генотипів {ngen}; фіксованих параметрів {res['p']}; ℓ_REML = {res['loglik']:.2f}.",
                        "LRT перевіряє, чи потрібен випадковий ефект у моделі (p — за сумішшю χ²₀/χ²₁)."], key="var"))
    # 2. спадковість і BLUP / скориговані середні
    if geno_random:
        ch = MX.cullis_heritability(res, "gen"); bt = MX.blup_table(res, "gen")
        S.append(sec_table("Спадковість", ["Показник", "Значення"],
                           [["H² за Каллісом (на рівні середніх номерів)", ch["h2"]],
                            ["Середня надійність BLUP", float(np.mean(bt["reliability"]))],
                            ["σ²g", res["sigma2"]["gen"]],
                            ["Генотипна мінливість GCV, %", 100 * math.sqrt(res["sigma2"]["gen"]) / bt["mu"] if bt["mu"] else float("nan")]],
                           [None, 4], ["H² за Каллісом коректно враховує незбалансованість; у збалансованому досліді дорівнює "
                                       "класичній спадковості на рівні середніх."], key="h2"))
        order = np.argsort(bt["rank"], kind="stable")
        top = max(1, int(round(0.1 * len(order))))
        tg = ["good" if i < top else None for i in range(len(order))]
        S.append(sec_table("BLUP генотипів", ["Місце", "Генотип", "BLUP", "SE", "Надійність", "Прогноз (μ + BLUP)"],
                           [[int(bt["rank"][i]), bt["levels"][i], bt["blup"][i], bt["se"][i], bt["reliability"][i], bt["value"][i]] for i in order],
                           [0, None, 3, 3, 3, 3],
                           [f"μ = {bt['mu']:.3f}. Зелене — кращі 10 % за BLUP. BLUP стягнуті до середнього: чим менше даних про номер, тим сильніша усадка."],
                           tags=tg, key="blup"))
        S.append(sec_fig("Графік: BLUP із SE", lambda f: U.fig_caterpillar(f, bt, trait_name), size=(8.2, max(4.2, 0.18 * len(order) + 1.8)), key="cat"))
        # 3. прогноз у середовищах
        if mode == "met":
            em = env_means(res); ge = res["u"]["ge"]; gidx = {l: i for i, l in enumerate(ge["levels"])}
            envs = list(em)
            M = []
            for gi, g in enumerate(bt["levels"]):
                row = [g]
                for e in envs:
                    k = gidx.get(f"{g}|{e}")
                    row.append(em[e] + bt["blup"][gi] + (ge["blup"][k] if k is not None else 0.0))
                M.append(row)
            S.append(sec_table("Прогноз у середовищах (BLUP)", ["Генотип"] + envs, M, [None] + [3] * len(envs),
                               ["Прогноз = середнє середовища + BLUP генотипу + BLUP взаємодії (для відсутніх комбінацій — без взаємодії). "
                                "Таблицю можна копіювати у вікно стабільності (AMMI, GGE)."], key="pred"))
    else:
        lv, lm, lse = MX.lsmeans_fixed(res, "gen")
        order = np.argsort(-lm); rk = np.empty(len(lm), int); rk[order] = np.arange(1, len(lm) + 1)
        S.append(sec_table("Скориговані середні генотипів", ["Місце", "Генотип", "Скориговане середнє", "SE"],
                           [[int(rk[i]), lv[i], lm[i], lse[i]] for i in order], [0, None, 3, 3],
                           ["Скориговані середні враховують блоки й незбалансованість; SE — з урахуванням випадкових ефектів."], key="lsm"))
    # 3б. ефективність неповних блоків і порівняння зі стандартом (лише для фіксованого генотипу)
    if not geno_random and use_blocks and mode == "single":
        try:
            fac_r = {k: v for k, v in fac.items() if k != "blk"}
            fx_r, rn_r = [t for t in fixed], [t for t in random if t != "blk"]
            res_r = MX.fit_mixed(y, fac_r, fx_r, rn_r, hessian=False)
            v_lat, v_rcbd = avg_pair_var(res), avg_pair_var(res_r)
            re_ = v_rcbd / v_lat if v_lat > 0 else float("nan")
            S.append(sec_table("Ефективність неповних блоків", ["Показник", "Значення"],
                               [["Середня дисперсія різниці двох середніх — з блоками", v_lat],
                                ["Те саме — без урахування блоків (RCBD)", v_rcbd],
                                ["Відносна ефективність RE = RCBD / з блоками", re_],
                                ["Виграш у точності, %", 100 * (re_ - 1) if re_ == re_ else float("nan")]],
                               [None, 4], ["RE > 1 — облік неповних блоків підвищив точність порівнянь; RE ≈ 1 — блоки не дали виграшу; "
                                           "RE < 1 — схема не виправдалась."], key="re"))
            if re_ == re_ and re_ < 1.0:
                warns.append(f"Облік неповних блоків не підвищив точності (RE = {re_:.2f}): ефект блоків малий.")
        except BreedingError:
            pass
    if controls and not geno_random:
        lv, V = MX.lsmeans_matrix(res, "gen")
        means = V @ res["beta"]; cov = V @ res["beta_cov"] @ V.T
        extra = ["blk"] if use_blocks else []
        d2 = MX.build_design(np.asarray(y, float), fac, fixed + extra, [])
        df_ib = n - d2["X"].shape[1]
        cres = CC.compare_estimates_to_control(lv, means, cov, controls, df_ib, alpha, alternative)
        S += [s_ for s_ in control_tables(cres, trait_name, alpha, alternative)]
        warns.append(f"Порівняння зі стандартом: середні й SE — зі змішаної моделі; ступені свободи ({df_ib}) — внутрішньоблочні "
                     f"(консервативне наближення).")
    elif controls and geno_random:
        warns.append("Порівняння зі стандартом виконується для ФІКСОВАНОГО генотипу; для випадкового (BLUP) оберіть фіксований.")
    # 4. фіксовані ефекти
    fx = [[res["x_names"][i], float(res["beta"][i]), float(res["beta_se"][i])] for i in range(res["p"])]
    S.append(sec_table("Фіксовані ефекти", ["Ефект", "Оцінка", "SE"], fx, [None, 4, 4],
                       ["Ефекти рівнів — відносно першого (базового) рівня."], key="fixed"))
    S.append(sec_text("Пояснення", MIXED_HELP, key="help"))
    return S, warns, res
