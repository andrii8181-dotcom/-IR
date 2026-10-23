# sad_design_sections.py — S.A.D. v2.1: розділи результатів генератора схем
# -*- coding: utf-8 -*-
import math
import numpy as np
import matplotlib
from matplotlib.patches import Rectangle
import sad_design_core as D
import sad_breeding_ui as U
from sad_breeding_ui import sec_table, sec_text, sec_fig
from sad_gxe_core import BreedingError

DESIGN_HELP = """СХЕМИ ДЛЯ ВЕЛИКОЇ КІЛЬКОСТІ НОМЕРІВ

Коли номерів багато (десятки й сотні), повний блок (RCBD) стає надто великим і неоднорідним: різниця між початком і кінцем
блоку забирає точність. Неповні блоки зменшують зону, в межах якої порівнюють номери.

АЛЬФА-РЕШІТКА (Patterson & Williams 1976)
• Кількість номерів v = s·k: у кожній повторності s блоків по k ділянок; кожен номер — раз у кожній повторності (щонайменше 2).
• Схему підібрано випадковим пошуком за A-ефективністю E (E = 1 — як повний блок за точності порівнянь; менше — частина інформації
  віддана на поправку блоків). Пошук не гарантує математичного оптимуму; ефективність показано, а для порівняння — середню
  ефективність випадкового розбиття.
• Стандарти (за бажання) додаються в кожен блок: вони дають додаткову інформацію про ґрунтову неоднорідність.
• Аналіз: «Змішана модель» (блок — випадковий ефект у повторності). Решітка не виграє, якщо ґрунт однорідний: ефективність
  відносно RCBD показує розділ «Ефективність неповних блоків» у результатах аналізу.

АУГМЕНТОВАНА СХЕМА (Federer 1956)
• Стандарти (≥ 2) повторені в кожному блоці, нові номери — по одному разу. Підходить, коли матеріалу замало для повторень.
• Помилка оцінюється лише за стандартами: df = (c−1)(b−1); при df < 10 тест слабкий. Нові номери розрізняються гірше, ніж у
  повторних дослідах: критична різниця Дуннетта для нового номера приблизно вдвічі більша, ніж для стандарту.

ЗАСТЕРЕЖЕННЯ
• Схему генерує випадковий процес із зерном: те саме зерно відтворює ту саму схему (збережіть його разом із планом досліду).
• Для кількох ґрунтових градієнтів (рядки й стовпці) потрібні row-column схеми — їх тут не реалізовано."""


def fig_field_map(fig, layout, title):
    """Карта поля: для кожної повторності блоки — рядки, ділянки — клітинки; кольори чергуються за блоками, стандарти заштриховано."""
    reps = sorted({x["rep"] for x in layout})
    n = len(reps)
    axes = fig.subplots(1, n, squeeze=False)[0] if n <= 4 else fig.subplots((n + 2) // 3, 3, squeeze=False).ravel()
    maxk = max(x["plot"] for x in layout)
    for ax, rp in zip(axes, reps):
        cells = [x for x in layout if x["rep"] == rp]; nb = max(x["block"] for x in cells)
        for x in cells:
            col = "#dbe9f6" if x["block"] % 2 else "#f3e5d3"
            ax.add_patch(Rectangle((x["plot"] - 1, nb - x["block"]), 1, 1, fc=col, ec="#666", lw=0.5,
                                   hatch="///" if x["kind"] == "стандарт" else None))
            if nb * maxk <= 150: ax.text(x["plot"] - 0.5, nb - x["block"] + 0.5, x["entry"], ha="center", va="center", fontsize=6)
        ax.set_xlim(0, maxk); ax.set_ylim(0, nb); ax.set_aspect("auto")
        ax.set_xticks([i + 0.5 for i in range(maxk)] if maxk <= 20 else []); ax.set_xticklabels([str(i + 1) for i in range(maxk)] if maxk <= 20 else [], fontsize=6)
        ax.set_yticks([i + 0.5 for i in range(nb)] if nb <= 25 else []); ax.set_yticklabels([str(nb - i) for i in range(nb)] if nb <= 25 else [], fontsize=6)
        ax.set_title(f"Повторність {rp}" if n > 1 else "Блоки", fontsize=9, loc="left")
        ax.set_xlabel("Ділянка в блоці", fontsize=8); ax.set_ylabel("Блок", fontsize=8)
        for sp in ax.spines.values(): sp.set_visible(True)
    for ax in axes[len(reps):]: ax.axis("off")
    fig.suptitle(title + "  (штриховка — стандарти)", x=0.01, ha="left", fontsize=10); fig.tight_layout()


def sections_design(kind, entries, checks, k=None, r=None, n_blocks=None, seed=None):
    """kind: 'alpha' | 'aug'. entries — нові номери, checks — стандарти. Повертає (sections, warnings, layout)."""
    S, warns = [], []
    if kind == "alpha":
        d = D.alpha_design(entries, k, r, seed)
        layout = d["layout"]
        if checks: layout = D.add_checks_to_layout(layout, checks, seed)
        rnd = D.random_blocks_efficiency(d["v"], k, r, n=80)
        title = f"Альфа-решітка: {d['v']} номерів, блок {k}, {r} повторності"
        info = [["Схема", "альфа-решітка"], ["Номерів", d["v"]], ["Розмір блоку (номерів)", k], ["Блоків у повторності", d["s"]],
                ["Повторностей", r], ["Стандартів у кожному блоці", len(checks)], ["Ділянок усього", len(layout)],
                ["A-ефективність E", d["efficiency"]], ["Середня E випадкового розбиття (для порівняння)", rnd],
                ["Спроб пошуку", d["tries"]], ["Зерно рандомізації", "не задано (випадкове)" if seed is None else seed]]
        nd = [None, None]
        if d["efficiency"] < 0.7: warns.append(f"A-ефективність {d['efficiency']:.2f} невисока: частина інформації йде на поправку блоків. "
                                               f"Збільшення кількості повторностей або зменшення розміру блоку зазвичай її підвищує.")
        if d["efficiency"] <= rnd + 1e-9: warns.append("Пошук не покращив випадкове розбиття для цих параметрів.")
        warns.append("Схему підібрано пошуком; математична оптимальність не гарантується. Ефективність показано — оцініть її самі.")
    else:
        d = D.augmented_design(entries, checks, n_blocks, seed)
        layout = d["layout"]; warns += d["warnings"]
        title = f"Аугментована схема: {d['n_new']} нових номерів, {d['n_checks']} стандарти, {d['n_blocks']} блоків"
        info = [["Схема", "аугментована (Federer)"], ["Нових номерів", d["n_new"]], ["Стандартів", d["n_checks"]], ["Блоків", d["n_blocks"]],
                ["Розміри блоків (ділянок)", ", ".join(str(x) for x in d["block_sizes"])], ["Ділянок усього", len(layout)],
                ["df похибки (c−1)(b−1)", d["df"]], ["Зерно рандомізації", "не задано (випадкове)" if seed is None else seed]]
    S.append(sec_table("Підсумок схеми", ["Параметр", "Значення"], info, [None, 3], key="info"))
    rows = [[x["rep"], x["block"], x["plot"], x["entry"], x["kind"]] for x in layout]
    tags = ["info" if x["kind"] == "стандарт" else None for x in layout]
    S.append(sec_table("План досліду", ["Повторність", "Блок", "Ділянка", "Номер", "Тип"], rows, [0, 0, 0, None, None],
                       ["Кожен рядок — одна ділянка. Блакитне — стандарти. Скопіюйте таблицю або експортуйте в Excel для польових робіт."],
                       tags=tags, key="layout"))
    tmpl = [[x["entry"], "", f"R{x['rep']}", f"B{x['block']}", ""] for x in layout]
    S.append(sec_table("Шаблон для внесення даних", ["Генотип", "Середовище", "Повторність", "Блок", "Ознака 1"], tmpl, [None] * 5,
                       ["Стовпці відповідають вікну «Змішана модель (REML / BLUP)». Скопіюйте таблицю, внесіть значення ознаки у "
                        "останній стовпець і вставте у вікно змішаної моделі (оберіть «Один дослід», «Є неповні блоки»)."], key="template"))
    S.append(sec_fig("Карта поля", lambda f: fig_field_map(f, layout, title), size=(9.0, 5.6 if kind == "alpha" else 5.0), key="map"))
    S.append(sec_text("Пояснення", DESIGN_HELP, key="help"))
    return S, warns, layout
