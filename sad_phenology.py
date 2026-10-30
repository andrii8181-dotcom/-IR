# sad_phenology.py – S.A.D. v2.1: фенологічні спостереження (ядро, без tkinter)
# -*- coding: utf-8 -*-
"""
Облік настання фенологічних фаз при сортовивченні: гнучкий розбір дат, номер дня року (з поправкою на високосний рік), зведення за сортами,
тривалість періодів, порівняння зі стандартом, ANOVA та НІР з літерами, суми температур до настання фази (за погодою), дата настання за
візитами (відсоток рослин у фазі).
"""
import re, math, json, calendar, datetime as _dt
import numpy as np
from scipy import stats as _st

_D = _dt.date

# ═══════════════════════════════════════════════════════════════
# 1. Набори фаз за шкалою BBCH
# ═══════════════════════════════════════════════════════════════
SOURCE = ("Коди й критерії фаз – за монографією «Growth stages of mono- and dicotyledonous plants. BBCH Monograph», 2nd ed., 2001, ред. U. Meier "
          "(Federal Biological Research Centre for Agriculture and Forestry). Критерії подано в українському викладі; набір можна змінювати.")


def _ph(key, name, bbch="", hint=""): return {"key": key, "name": name, "bbch": bbch, "hint": hint}


_LEAF_FALL = [_ph("disc", "Початок пожовтіння листя", "92", "Листки починають змінювати забарвлення"), _ph("leaf0", "Початок листопаду", "93", "Початок опадання листя"),
              _ph("leaf1", "Кінець листопаду", "97", "Усе листя опало")]

PRESETS = {
    "pome": {"name": "Яблуня, груша", "phases": [
        _ph("swell", "Початок набрякання бруньок", "01", "Листкові бруньки помітно набухли, луски подовжились, зі світлими плямами"),
        _ph("green", "Розпускання бруньок (зелений конус)", "09", "Зелені кінчики листків приблизно на 5 мм над лусками бруньки"),
        _ph("mouse", "«Мишаче вушко»", "10", "Зелені кінчики листків на 10 мм над лусками, перші листки відокремлюються"),
        _ph("bud55", "Бутони видимі (ще закриті)", "55", "Квіткові бруньки видно, вони ще закриті"),
        _ph("pink", "Рожевий бутон", "57", "Пелюстки видовжуються, чашолистки трохи розкриті, пелюстки щойно видно"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (≥ 50 % квіток)", "65", "Розкрилось щонайменше 50 % квіток, починають опадати перші пелюстки"),
        _ph("bloom1", "Кінець цвітіння", "69", "Усі пелюстки опали"),
        _ph("set", "Зав'язування плодів", "71", "Розмір плодика до 10 мм; осипання зав'язі після цвітіння"),
        _ph("ripe0", "Початок дозрівання", "81", "З'являється сортове забарвлення плодів"),
        _ph("pick", "Знімна стиглість", "87", "Плоди готові до збору"),
        _ph("eat", "Споживча стиглість", "89", "Плоди мають типовий смак і щільність")] + _LEAF_FALL},
    "stone": {"name": "Кісточкові (черешня, вишня, слива, абрикос, персик)", "phases": [
        _ph("swell", "Початок набрякання бруньок", "01", "Листкові бруньки: видно світло-бурі луски зі світлими краями"),
        _ph("green", "Розпускання бруньок (зелені кінчики листків)", "09", "Бурі луски опали, бруньки охоплені світло-зеленими лусками"),
        _ph("bud55", "Окремі бутони видимі (ще закриті)", "55", "Окремі квіткові бруньки на коротких ніжках, зелені луски трохи розкриті"),
        _ph("white", "Бутони з видимими пелюстками (білий/рожевий бутон)", "57", "Чашолистки розкриті, видно верхівки пелюсток (ще закритих)"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (≥ 50 % квіток)", "65", "Розкрилось щонайменше 50 % квіток, починають опадати перші пелюстки"),
        _ph("bloom1", "Кінець цвітіння", "69", "Усі пелюстки опали"),
        _ph("set", "Зав'язування плодів", "71", "Зав'язь росте; осипання зав'язі після цвітіння"),
        _ph("ripe0", "Початок забарвлення плодів", "81", "Початок забарвлення плодів"),
        _ph("pick", "Знімна стиглість", "87", "Плоди готові до збору"),
        _ph("eat", "Споживча стиглість", "89", "Плоди мають типовий смак і щільність")] + _LEAF_FALL},
    "vine": {"name": "Виноград", "phases": [
        _ph("swell", "Початок набрякання бруньок", "01", "Бруньки починають розширюватись під лусками"),
        _ph("wool", "«Вата»", "05", "Чітко видно бурий пух (стадія «вати»)"),
        _ph("burst0", "Початок розпускання бруньок", "07", "Щойно видно перші зелені кінчики пагонів"),
        _ph("burst", "Розпускання бруньок", "08", "Зелені кінчики пагонів чітко видно"),
        _ph("leaf1", "Перший листок розгорнуто", "11", "Перший листок розгорнувся й відхилився від пагона"),
        _ph("infl", "Суцвіття добре видимі", "53", "Суцвіття чітко видно"),
        _ph("infl57", "Суцвіття повністю розвинені", "57", "Суцвіття повністю розвинені, квітки розділяються"),
        _ph("bloom0", "Початок цвітіння (10 % ковпачків опало)", "61", "Опало приблизно 10 % квіткових ковпачків"),
        _ph("bloom50", "Повне цвітіння (50 % ковпачків опало)", "65", "Опало 50 % квіткових ковпачків"),
        _ph("bloom1", "Кінець цвітіння", "69", "Цвітіння завершилось"),
        _ph("set", "Зав'язування ягід", "71", "Молоді ягоди починають набухати, залишки квіток опали"),
        _ph("pea", "Ягоди розміром з горошину", "75", "Ягоди розміром з горошину, грона звисають"),
        _ph("touch", "Ягоди починають торкатися", "77", "Ягоди в гроні починають торкатися одна одної"),
        _ph("veraison", "Початок дозрівання (веразон)", "81", "Ягоди починають набувати сортового забарвлення"),
        _ph("soft", "Розм'якшення ягід", "85", "Ягоди розм'якшуються"),
        _ph("harvest", "Технічна стиглість (ягоди готові до збору)", "89", "Ягоди стиглі для збору"),
        _ph("wood", "Кінець визрівання лози (після збору)", "91", "Після збору; завершення визрівання деревини"),
        _ph("disc", "Початок пожовтіння листя", "92", "Початок знебарвлення листків"),
        _ph("fall0", "Початок листопаду", "93", "Початок опадання листя"),
        _ph("fall1", "Кінець листопаду", "97", "Кінець листопаду")]},
    "currants": {"name": "Смородина (чорна, червона)", "phases": [
        _ph("swell", "Початок набрякання бруньок", "01", "Луски бруньок видовжились"),
        _ph("burst0", "Початок розпускання бруньок", "07", "Щойно видно перші зелені чи червоні кінчики листків"),
        _ph("bud55", "Перші квіткові бруньки видимі", "55", "Перші квіткові бруньки (компактна китиця) видно поряд із розгорнутими листками"),
        _ph("grape", "Стадія «грона»", "59", "Усі квіткові бруньки відокремились"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (≥ 50 % квіток)", "65", "Розкрилось щонайменше 50 % квіток, опадають перші пелюстки"),
        _ph("bloom1", "Кінець цвітіння", "69", "Усі пелюстки опали"),
        _ph("fruit", "Початок росту ягід", "71", "Перші плоди видно біля основи китиці"),
        _ph("ripe0", "Початок дозрівання", "81", "Зміна забарвлення ягід на сортове"),
        _ph("pick", "Знімна стиглість", "87", "Більшість ягід стиглі"),
        ] + _LEAF_FALL},
    "strawberry": {"name": "Суниця", "phases": [
        _ph("swell", "Набрякання головної бруньки", "03", "Набрякання головної бруньки"),
        _ph("leaf1", "Перший листок розгорнуто", "11", "Перший листок розгорнувся"),
        _ph("stolon", "Початок утворення вусів", "41", "Видно вуса завдовжки близько 2 см"),
        _ph("infl", "Перші суцвіття в основі розетки", "55", "Перші суцвіття в основі розетки"),
        _ph("bud57", "Перші квіткові бруньки видимі", "57", "З'явились перші квіткові бруньки (ще закриті)"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння", "65", "Розкриті квітки другого й третього порядків, опадають перші пелюстки"),
        _ph("bloom1", "Кінець цвітіння", "67", "Більшість пелюсток опала"),
        _ph("ripe0", "Початок дозрівання", "81", "Більшість плодів білі"),
        _ph("ripe85", "Перші плоди з сортовим забарвленням", "85", "Перші плоди набули сортового забарвлення"),
        _ph("main", "Основний збір", "87", "Більшість плодів забарвлені")]},
    "cereal": {"name": "Зернові колосові (пшениця, ячмінь, овес, жито)", "phases": [
        _ph("emerge", "Сходи", "09", "Колеоптиль пробиває поверхню ґрунту"),
        _ph("till", "Початок кущення", "21", "Помітний перший пагін кущення"),
        _ph("tillend", "Кінець кущення", "29", "Максимальна кількість пагонів кущення"),
        _ph("stem", "Початок виходу в трубку", "30", "Перше міжвузля починає видовжуватись; верхівка суцвіття щонайменше на 1 см над вузлом кущення"),
        _ph("flag", "Поява прапорцевого листка", "37", "Прапорцевий листок щойно видно, ще скручений"),
        _ph("flag39", "Прапорцевий листок розгорнуто", "39", "Прапорцевий листок повністю розгорнутий, щойно видно язичок"),
        _ph("head0", "Початок колосіння", "51", "Верхівка суцвіття вийшла з піхви, перший колосок щойно видно"),
        _ph("head55", "Середина колосіння", "55", "Вийшла половина суцвіття"),
        _ph("head1", "Кінець колосіння", "59", "Суцвіття повністю вийшло"),
        _ph("bloom0", "Початок цвітіння", "61", "Видно перші пиляки"),
        _ph("bloom50", "Повне цвітіння", "65", "Дозріли 50 % пиляків"),
        _ph("bloom1", "Кінець цвітіння", "69", "Усі колоски відцвіли"),
        _ph("milk", "Молочна стиглість", "75", "Вміст зерна молочний, зерно досягло кінцевого розміру, ще зелене"),
        _ph("dough", "Тістоподібна стиглість (м'яке тісто)", "85", "Вміст зерна м'який, але сухий; відбиток нігтя не утримується"),
        _ph("wax", "Воскова стиглість (тверде тісто)", "87", "Вміст зерна щільний; відбиток нігтя утримується"),
        _ph("full", "Повна стиглість", "89", "Зерно тверде, його важко розділити нігтем")]},
    "maize": {"name": "Кукурудза", "phases": [
        _ph("emerge", "Сходи", "09", "Колеоптиль пробиває поверхню ґрунту"),
        _ph("tassel", "Початок викидання волоті", "51", "Волоть помітна на верхівці стебла"),
        _ph("bloom0", "Початок цвітіння", "61", "♂: видно тичинки в середині волоті; ♀: верхівка качана виходить із піхви"),
        _ph("pollen", "Початок пиляння", "63", "♂: початок пиляння; ♀: видно кінчики приймочок"),
        _ph("bloom50", "Повне цвітіння", "65", "♂: верхня й нижня частини волоті цвітуть; ♀: приймочки повністю виступили"),
        _ph("bloom1", "Кінець цвітіння", "69", "Приймочки повністю засохли"),
        _ph("milk", "Молочна стиглість", "75", "Зерна в середині качана жовтувато-білі, вміст молочний (≈ 40 % сухої речовини)"),
        _ph("dough", "Тістоподібна стиглість", "85", "Зерна жовті, ≈ 55 % сухої речовини"),
        _ph("phys", "Фізіологічна стиглість (чорна точка)", "87", "Біля основи зерна чорна крапка/шар, ≈ 60 % сухої речовини"),
        _ph("full", "Повна стиглість", "89", "Зерна тверді й блискучі, ≈ 65 % сухої речовини")]},
    "sunflower": {"name": "Соняшник", "phases": [
        _ph("emerge", "Сходи", "09", "Сім'ядолі пробили поверхню ґрунту"),
        _ph("bud", "Початок бутонізації", "51", "Суцвіття щойно видно між наймолодшими листками"),
        _ph("ray", "Язичкові квітки видимі", "59", "Язичкові квітки видно між обгортковими листочками, суцвіття ще закрите"),
        _ph("bloom0", "Початок цвітіння", "61", "Язичкові квітки розгорнулись, трубчасті видно у зовнішній третині кошика"),
        _ph("bloom50", "Повне цвітіння", "65", "Трубчасті квітки цвітуть у середній третині кошика"),
        _ph("bloom1", "Кінець цвітіння", "69", "Більшість трубчастих квіток відцвіла, язичкові засохли чи опали"),
        _ph("ripe0", "Початок дозрівання", "80", "Насіння на зовнішній третині кошика темне й тверде; спинка кошика ще зелена"),
        _ph("phys", "Фізіологічна стиглість", "87", "Спинка кошика жовта, обгортка плямисто-бура, ≈ 75–80 % сухої речовини"),
        _ph("full", "Повна стиглість", "89", "Насіння на внутрішній третині темне й тверде, спинка кошика бура, ≈ 85 % сухої речовини")]},
    "soy": {"name": "Соя", "phases": [
        _ph("emerge", "Сходи", "09", "Гіпокотиль із сім'ядолями з'явився над поверхнею ґрунту"),
        _ph("bud", "Перші квіткові бруньки видимі", "51", "З'явились перші квіткові бруньки"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (≈ 50 % квіток)", "65", "Розкрилось приблизно 50 % квіток"),
        _ph("bloom1", "Кінець цвітіння", "69", "З'явились перші боби (≈ 5 мм)"),
        _ph("pod", "Початок формування бобів", "71", "≈ 10 % бобів досягли кінцевої довжини (15–20 мм)"),
        _ph("fill", "Наливання бобів", "75", "≈ 50 % бобів досягли кінцевої довжини; триває наливання"),
        _ph("ripe0", "Початок дозрівання", "81", "≈ 10 % бобів стиглі; насіння кінцевого кольору, сухе й тверде"),
        _ph("full", "Повна стиглість (збиральна)", "89", "Майже всі боби стиглі; насіння кінцевого кольору, сухе й тверде")]},
    "rape": {"name": "Ріпак", "phases": [
        _ph("emerge", "Сходи", "09", "Сім'ядолі пробили поверхню ґрунту"),
        _ph("rosette", "Початок виходу в трубку (розетка)", "30", "Початок видовження стебла; міжвузль ще немає (розетка)"),
        _ph("green", "«Зелений бутон»", "51", "Квіткові бруньки видно зверху"),
        _ph("yellow", "«Жовтий бутон»", "59", "Видно перші пелюстки, бруньки ще закриті"),
        _ph("bloom0", "Початок цвітіння", "60", "Розкрились перші квітки"),
        _ph("bloom50", "Повне цвітіння (≈ 50 % квіток китиці)", "65", "50 % квіток головної китиці розкрито, старі пелюстки опадають"),
        _ph("bloom1", "Кінець цвітіння", "69", "Цвітіння завершилось"),
        _ph("pod", "Початок росту стручків", "71", "≈ 10 % стручків досягли кінцевого розміру"),
        _ph("ripe0", "Початок дозрівання", "81", "≈ 10 % стручків стиглі; насіння темне й тверде"),
        _ph("full", "Повна стиглість", "89", "Майже всі стручки стиглі; насіння темне й тверде")]},
    "pea": {"name": "Горох", "phases": [
        _ph("emerge", "Сходи", "09", "Пагін пробиває поверхню ґрунту"),
        _ph("leaf1", "Перший справжній листок", "11", "Розгорнувся перший справжній листок (з прилистками) або розвинувся перший вусик"),
        _ph("bud", "Перші квіткові бруньки видимі", "51", "Перші квіткові бруньки видно поза листками"),
        _ph("bloom0", "Початок цвітіння (≈ 10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (≈ 50 % квіток)", "65", "Розкрилось приблизно 50 % квіток"),
        _ph("bloom1", "Кінець цвітіння", "69", "Цвітіння завершилось"),
        _ph("green", "Зелена стиглість бобів", "79", "Боби досягли типового розміру, горох повністю сформований"),
        _ph("full", "Повна стиглість (суха)", "89", "Усі боби сухі й бурі, насіння сухе й тверде")]},
    "potato": {"name": "Картопля", "phases": [
        _ph("emerge", "Сходи", "09", "Стебла пробивають поверхню ґрунту"),
        _ph("cover", "Початок змикання рядків", "31", "≈ 10 % рослин змикаються між рядками"),
        _ph("cover90", "Повне змикання рядків", "39", "≈ 90 % рослин змикаються між рядками"),
        _ph("tuber", "Початок бульбоутворення", "40", "Кінчики перших столонів потовщились удвічі порівняно з столоном"),
        _ph("bud", "Перші бутони видимі", "51", "Видно перші окремі бутони (1–2 мм) першого суцвіття"),
        _ph("bloom0", "Початок цвітіння", "61", "Розкрилось ≈ 10 % квіток першого суцвіття"),
        _ph("bloom50", "Повне цвітіння", "65", "Розкрилось ≈ 50 % квіток першого суцвіття"),
        _ph("bloom1", "Кінець цвітіння першого суцвіття", "69", "Цвітіння першого суцвіття завершилось"),
        _ph("yellow", "Початок пожовтіння листя", "91", "Листки починають жовтіти"),
        _ph("yellow2", "Листя здебільшого жовте", "93", "Більшість листя жовтувате"),
        _ph("dead", "Бадилля загинуло", "97", "Листя й стебла відмерли, стебла вибілені й сухі")]},
    "tomato": {"name": "Томат, перець, баклажан", "phases": [
        _ph("emerge", "Сходи", "09", "Сім'ядолі пробивають поверхню ґрунту"),
        _ph("leaf1", "Перший справжній листок", "11", "Повністю розгорнувся перший справжній листок головного пагона"),
        _ph("infl", "Перше суцвіття видимо", "51", "Томат: перше суцвіття видно (перший бутон прямий); перець, баклажан: видно першу квіткову бруньку"),
        _ph("bloom0", "Початок цвітіння", "61", "Розкрилась перша квітка (томат – у першому суцвітті)"),
        _ph("fruit", "Перший плід досяг типового розміру", "71", "Томат: у першій китиці перший плід досяг типового розміру; перець, баклажан: перший плід досяг типового розміру й форми"),
        _ph("ripe0", "Початок дозрівання (10 % плодів)", "81", "10 % плодів мають типове забарвлення стиглості"),
        _ph("ripe50", "Дозрівання 50 % плодів", "85", "50 % плодів мають типове забарвлення стиглості"),
        _ph("full", "Повна стиглість", "89", "Плоди мають типове забарвлення повної стиглості")]},
    "universal": {"name": "Універсальний набір (загальна шкала BBCH)", "phases": [
        _ph("emerge", "Сходи / початок вегетації", "09", "Однодольні: колеоптиль пробиває ґрунт; дводольні: сім'ядолі виходять на поверхню; багаторічні: бруньки мають зелені кінчики"),
        _ph("bud", "Початок бутонізації", "51", "Видно суцвіття або квіткові бруньки"),
        _ph("bloom0", "Початок цвітіння (10 % квіток)", "61", "Розкрилось приблизно 10 % квіток"),
        _ph("bloom50", "Повне цвітіння (50 % квіток)", "65", "Розкрилось 50 % квіток, можуть опадати перші пелюстки"),
        _ph("bloom1", "Кінець цвітіння", "69", "Цвітіння завершилось, видно зав'язь"),
        _ph("fruit", "Розвиток плодів", "71", "10 % плодів досягли кінцевого розміру (або плід досяг 10 % кінцевого розміру)"),
        _ph("ripe0", "Початок дозрівання", "81", "Початок дозрівання або забарвлення плодів"),
        _ph("full", "Повна стиглість", "89", "Плід має забарвлення повної стиглості, починається опадання плодів"),
        _ph("leaf0", "Початок листопаду", "93", "Початок опадання листя")]},
    "custom": {"name": "Власний набір (порожній)", "phases": []},
}
PRESET_ORDER = ["pome", "stone", "vine", "currants", "strawberry", "cereal", "maize", "sunflower", "soy", "rape", "pea", "potato", "tomato", "universal", "custom"]


def preset_phases(key):
    return [dict(p) for p in PRESETS[key]["phases"]]


def phase_label(p):
    return p["name"] + (f" ({p['bbch']})" if p.get("bbch") else "")


def phase_hint(p):
    """Підказка до фази: код BBCH і критерій настання (з монографії); для власних фаз може бути порожньою."""
    h = (p.get("hint") or "").strip()
    if p.get("bbch"): return f"BBCH {p['bbch']}" + (f": {h}" if h else "")
    return h


def new_phase_key(name, existing):
    base = re.sub(r"\W+", "_", name.strip().lower(), flags=re.U).strip("_")[:24] or "phase"; k = base; i = 2
    while k in existing: k = f"{base}_{i}"; i += 1
    return k


# ═══════════════════════════════════════════════════════════════
# 2. Дати: гнучкий розбір, номер дня року
# ═══════════════════════════════════════════════════════════════
MONTHS = {"січня": 1, "січень": 1, "січ": 1, "лютого": 2, "лютий": 2, "лют": 2, "березня": 3, "березень": 3, "бер": 3, "квітня": 4, "квітень": 4, "кві": 4, "кв": 4,
          "травня": 5, "травень": 5, "тра": 5, "червня": 6, "червень": 6, "чер": 6, "липня": 7, "липень": 7, "лип": 7, "серпня": 8, "серпень": 8, "сер": 8,
          "вересня": 9, "вересень": 9, "вер": 9, "жовтня": 10, "жовтень": 10, "жов": 10, "листопада": 11, "листопад": 11, "лис": 11, "грудня": 12, "грудень": 12, "гру": 12}
TODAY_WORDS = {"т", "t", "сьогодні", "сег", "today"}
MONTH_NAMES = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def parse_date_flex(text, year, today=None):
    """→ (date | None, повідомлення | None). Порожнє значення → (None, None). Приймає: 12.05, 12.5.26, 12.05.2026, 12/05, 12-5, 2026-05-12, 1205,
    120526, 12052026, «12 травня», «12 тра 2026», число Excel (45789), «т» – сьогодні."""
    s = str(text if text is not None else "").strip().lower().replace("\u00a0", " ")
    if not s: return None, None
    if s in TODAY_WORDS: return (today or _D.today()), None
    def mk(y, m, d):
        try: return _D(y, m, d), None
        except ValueError:
            if m < 1 or m > 12: return None, f"місяця {m} не існує"
            return None, f"у місяці {m:02d} немає {d}-го числа" if d > 0 else "день має бути 1 або більше"
    m = re.fullmatch(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?:[ t]\d.*)?", s)
    if m: return mk(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if re.fullmatch(r"\d{5}(\.\d+)?", s):
        n = int(float(s))
        if 20000 <= n <= 80000: return _D(1899, 12, 30) + _dt.timedelta(days=n), None
        return None, "число схоже на дату Excel, але поза межами"
    m = re.fullmatch(r"(\d{1,2})[.\-/ ,](\d{1,2})(?:[.\-/ ,](\d{2}|\d{4}))?", s)
    if m:
        y = year if not m.group(3) else (2000 + int(m.group(3)) if len(m.group(3)) == 2 else int(m.group(3)))
        return mk(y, int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2}|\d{4})?", s)
    if m:
        y = year if not m.group(3) else (2000 + int(m.group(3)) if len(m.group(3)) == 2 else int(m.group(3)))
        return mk(y, int(m.group(2)), int(m.group(1)))
    m = re.fullmatch(r"(\d{1,2})\s*([а-яіїєґa-z]+)\.?(?:\s+(\d{4}))?", s)
    if m and m.group(2) in MONTHS: return mk(int(m.group(3)) if m.group(3) else year, MONTHS[m.group(2)], int(m.group(1)))
    return None, f"«{text}» не схоже на дату (приклади: 12.05, 12.05.2026, 12 травня)"


def fmt_date(d):
    return d.strftime("%d.%m.%Y") if d else ""


def doy_norm(d):
    """Номер дня року, нормований до невисокосного року: однакова календарна дата має однаковий номер у різні роки."""
    n = d.timetuple().tm_yday
    return n - 1 if calendar.isleap(d.year) and d.month > 2 else n


def md_from_doy(n):
    """Номер дня (нормований) → «дд.мм»."""
    n = int(round(n)); n = min(365, max(1, n)); d = _D(2001, 1, 1) + _dt.timedelta(days=n - 1); return d.strftime("%d.%m")


def fmt_days(x, nd=1):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{nd}f}".replace(".", ",")


# ═══════════════════════════════════════════════════════════════
# 3. Записи спостережень
# ═══════════════════════════════════════════════════════════════
def assign_reps(rows):
    """rows: [{'name','rep','dates'}] за рік → повторності: заповнене значення береться як є, порожнє – наступний номер за порядком у сорту."""
    cnt = {}; out = []
    for r in rows:
        nm = r["name"].strip()
        if not nm: continue
        cnt[nm] = cnt.get(nm, 0) + 1
        rep = str(r.get("rep", "")).strip() or str(cnt[nm]); out.append({**r, "name": nm, "rep": rep})
    return out


def collect_records(years_data, phase_keys):
    """years_data: {рік: [рядки]}; рядок: {'name','rep','dates': {ключ_фази: текст дати}}. → (records, errors, warnings).
    Помилка – текст не є датою. Попередження – дата поза календарним роком, порушено хронологічний порядок фаз."""
    recs, errs, warns = [], [], []
    for y in sorted(years_data):
        for r in assign_reps(years_data[y]):
            prev = None
            for k in phase_keys:
                txt = r["dates"].get(k, "")
                d, msg = parse_date_flex(txt, y)
                if d is None:
                    if msg: errs.append({"year": y, "name": r["name"], "rep": r["rep"], "phase": k, "text": txt, "msg": msg})
                    continue
                if d.year != y: warns.append({"year": y, "name": r["name"], "rep": r["rep"], "phase": k, "msg": f"дата {fmt_date(d)} не з року {y}"})
                if prev is not None and d < prev[1]:
                    warns.append({"year": y, "name": r["name"], "rep": r["rep"], "phase": k, "msg": f"раніше за попередню фазу ({fmt_date(prev[1])})"})
                prev = (k, d)
                recs.append({"year": y, "name": r["name"], "rep": r["rep"], "phase": k, "date": d, "doy": doy_norm(d)})
    return recs, errs, warns


def cultivar_order(records, extra=()):
    seen = []
    for n in list(extra) + [r["name"] for r in records]:
        if n not in seen: seen.append(n)
    return seen


# ═══════════════════════════════════════════════════════════════
# 4. Зведення, тривалість, порівняння зі стандартом
# ═══════════════════════════════════════════════════════════════
def _stats(vals):
    a = np.asarray(vals, float); n = len(a)
    return {"n": n, "mean": float(np.mean(a)) if n else float("nan"), "sd": float(np.std(a, ddof=1)) if n > 1 else float("nan"),
            "min": float(np.min(a)) if n else float("nan"), "max": float(np.max(a)) if n else float("nan")}


def summarize(records, cultivars, phase_keys):
    """{(сорт, фаза): {n, mean, sd, min, max}} за номером дня року."""
    by = {}
    for r in records: by.setdefault((r["name"], r["phase"]), []).append(r["doy"])
    return {(c, p): _stats(by.get((c, p), [])) for c in cultivars for p in phase_keys}


def durations(records, cultivars, pairs):
    """pairs: [(фаза_a, фаза_b)]. Тривалість (діб) = дата_b − дата_a в межах одного року й повторності. → {(сорт, (a, b)): статистика}."""
    idx = {(r["year"], r["name"], r["rep"], r["phase"]): r["date"] for r in records}
    keys = {(r["year"], r["name"], r["rep"]) for r in records}; out = {}
    for c in cultivars:
        for a, b in pairs:
            vals = [(idx[(y, n, rp, b)] - idx[(y, n, rp, a)]).days for (y, n, rp) in keys if n == c and (y, n, rp, a) in idx and (y, n, rp, b) in idx]
            out[(c, (a, b))] = _stats(vals)
    return out


def classify(diff, thr=3.0):
    if diff is None or (isinstance(diff, float) and math.isnan(diff)): return ""
    return "ранній" if diff <= -thr else ("пізній" if diff >= thr else "середній")


def reference_map(cultivars, standard="", groups=None, group_std=None):
    """Опорний стандарт для кожного сорту: стандарт його групи стиглості (якщо він є серед сортів), інакше загальний стандарт,
    інакше «» – середнє за сортами. groups: {сорт: група}; group_std: {група: сорт-стандарт}. → {сорт: стандарт або «»}."""
    groups = groups or {}; group_std = group_std or {}; cs = set(cultivars); out = {}
    for c in cultivars:
        g = groups.get(c, ""); s_ = group_std.get(g, "") if g else ""
        out[c] = s_ if s_ in cs else (standard if standard in cs else "")
    return out


def vs_standard(summ, cultivars, phase_keys, standard=None, thr=3.0, ref_of=None):
    """Різниця середніх дат (діб) відносно стандарту (або середнього за сортами). Додатне – пізніше. ref_of – {сорт: його стандарт}
    для кількох стандартів (групи стиглості); тоді кожен сорт порівнюється зі своїм. → ({(сорт, фаза): (різниця, клас)}, {фаза: опорний_день})."""
    empty = {"n": 0, "mean": float("nan")}
    get = lambda c, p: summ.get((c, p), empty)
    ref = {}
    for p in phase_keys:
        if standard and get(standard, p)["n"] > 0: ref[p] = get(standard, p)["mean"]
        else:
            ms = [get(c, p)["mean"] for c in cultivars if get(c, p)["n"] > 0]; ref[p] = float(np.mean(ms)) if ms else float("nan")
    out = {}
    for c in cultivars:
        for p in phase_keys:
            s = get(c, p); r_ = (ref_of or {}).get(c)
            rv = get(r_, p)["mean"] if r_ and get(r_, p)["n"] > 0 else ref[p]
            if s["n"] == 0 or math.isnan(rv): out[(c, p)] = (float("nan"), "")
            else: d = s["mean"] - rv; out[(c, p)] = (d, classify(d, thr))
    return out, ref


# ═══════════════════════════════════════════════════════════════
# 5. ANOVA за номером дня (НІР і літери – тими самими функціями, що й решта програми)
# ═══════════════════════════════════════════════════════════════
def anova_phase(records, phase, cultivars, alpha=0.05):
    """Вплив сорту (і року, якщо їх кілька) на дату настання фази. Повторності – блоки, якщо у всіх сортів вони однакові й ≥ 2; інакше CRD.
    Літера «a» – найраніший сорт. → словник або {'error': текст}."""
    import sad_common as C
    rs = [r for r in records if r["phase"] == phase and r["name"] in cultivars]
    cvs = [c for c in cultivars if any(r["name"] == c for r in rs)]
    if len(cvs) < 2: return {"error": "Потрібно щонайменше два сорти з датами цієї фази."}
    years = sorted({r["year"] for r in rs}); multi = len(years) > 1
    reps_by = {c: sorted({r["rep"] for r in rs if r["name"] == c}) for c in cvs}
    n_cell = {}
    for r in rs: n_cell[(r["name"], r["year"])] = n_cell.get((r["name"], r["year"]), 0) + 1
    balanced = len({tuple(v) for v in reps_by.values()}) == 1 and len(next(iter(reps_by.values()))) >= 2
    long = []
    for r in rs:
        row = {"A": r["name"], "value": float(r["doy"])}
        if multi: row["Y"] = str(r["year"])
        if balanced: row["BLOCK"] = r["rep"]                       # блок = повторність, спільна для всіх років (інакше блоки «рік|повторність» поглинають ефект року)
        long.append(row)
    fkeys = ["A", "Y"] if multi else ["A"]; lbf = {"A": cvs}; 
    if multi: lbf["Y"] = [str(y) for y in years]
    try: res = C.anova_rcbd(long, fkeys, lbf, bk="BLOCK") if balanced else C.anova_crd(long, fkeys, lbf)
    except Exception as e: return {"error": f"ANOVA не вдалася: {e}"}
    mse, dfe = res["MS_error"], res["df_error"]
    if dfe is None or dfe <= 0 or (isinstance(mse, float) and (math.isnan(mse))): return {"error": "Замало повторностей для оцінки похибки (потрібно ≥ 2 спостереження в сорті)."}
    means = {c: float(np.mean([r["doy"] for r in rs if r["name"] == c])) for c in cvs}; ns = {c: sum(1 for r in rs if r["name"] == c) for c in cvs}
    sig = C.lsd_sig(cvs, means, ns, mse, dfe, alpha)
    letters = C.cld(sorted(cvs, key=lambda c: means[c]), {c: -means[c] for c in cvs}, sig)
    nh = len(cvs) / sum(1.0 / ns[c] for c in cvs); tc = float(_st.t.ppf(1 - alpha / 2, int(dfe)))
    rows = []
    for row in res["table"]:
        nm, ss, df, ms, F, p = row[:6]; rows.append({"name": nm, "ss": ss, "df": df, "ms": ms, "F": F, "p": p})
    prow = next((r for r in rows if r["name"] == "Фактор A"), None)
    ms_ = {r["name"]: r["ms"] for r in rows}; F_a = prow["F"] if prow else float("nan")
    if multi and "Фактор A×Y" in ms_ and ms_["Фактор A×Y"] > 0: h2 = max(0.0, 1.0 - ms_["Фактор A×Y"] / ms_["Фактор A"])
    elif not multi and F_a == F_a and F_a > 0: h2 = max(0.0, 1.0 - 1.0 / F_a)
    else: h2 = float("nan")
    return {"table": rows, "mse": float(mse), "dfe": int(dfe), "means": means, "ns": ns, "n_harm": float(nh), "h2": h2, "letters": letters, "nir": tc * math.sqrt(2 * mse / nh),
            "design": "RCBD (повторності – блоки)" if balanced else "CRD (повна рандомізація)", "multi_year": multi, "years": years,
            "F": prow["F"] if prow else float("nan"), "p": prow["p"] if prow else float("nan"), "alpha": alpha}


# ═══════════════════════════════════════════════════════════════
# 5б. Порівняння середніх: методи для малої й великої кількості сортів
# ═══════════════════════════════════════════════════════════════
METHODS = [("auto", "Автоматично (за кількістю сортів)"), ("lsd", "НІР05 (Фішер)"), ("tukey", "Тьюкі HSD"), ("bonferroni", "Бонферроні"), ("duncan", "Дункан"),
           ("sk", "Скотт–Кнотт (групи без перекриття)"), ("dunnett", "Порівняння зі стандартом – тест Даннетта"),
           ("control", "Порівняння зі стандартом – t із поправкою Холма"), ("kw", "Краскел–Уолліс + Данн (непараметричний)")]
METHOD_NAME = dict(METHODS)
LETTER_MAX = 60          # понад стільки сортів літери парних порівнянь не формуються (нечитабельні); для таких даних – Скотт–Кнотт або порівняння зі стандартом
DUNCAN_MAX = 30          # Дункан потребує окремого квантиля для кожної довжини діапазону


def resolve_method(method, k):
    """Автоматично: до 5 сортів – НІР05 (із захистом F-тестом), до 30 – Тьюкі, понад 30 – Скотт–Кнотт."""
    if method != "auto": return method
    return "lsd" if k <= 5 else ("tukey" if k <= 30 else "sk")


def holm_adjust(pvals):
    """Поправка Холма (step-down) для вектора p-значень; повертає скориговані p у вихідному порядку."""
    p = np.asarray(pvals, float); m = len(p)
    if m == 0: return p
    order = np.argsort(p); adj = np.empty(m); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, p[i] * (m - rank))); adj[i] = run
    return adj


def _pair_sig(means, ns, mse, dfe, method, alpha):
    """Матриця істотності парних відмінностей (k×k, булева), векторизовано. method: lsd | tukey | bonferroni | duncan."""
    from scipy.stats import t as _t, studentized_range as _sr
    m = np.asarray(means, float); n = np.asarray(ns, float); k = len(m); df = int(dfe)
    se = np.sqrt(mse * (1.0 / n[:, None] + 1.0 / n[None, :])); D = np.abs(m[:, None] - m[None, :]); np.fill_diagonal(D, 0.0)
    if method == "lsd": S = D > float(_t.ppf(1 - alpha / 2, df)) * se
    elif method == "bonferroni": S = D > float(_t.ppf(1 - alpha / (2 * max(1, k * (k - 1) / 2)), df)) * se
    elif method == "tukey": S = D > float(_sr.ppf(1 - alpha, k, df)) / math.sqrt(2) * se
    elif method == "duncan":
        order = np.argsort(-m); rank = np.empty(k, int); rank[order] = np.arange(k); span = np.abs(rank[:, None] - rank[None, :]) + 1; S = np.zeros((k, k), bool); qp = {}
        for p_ in range(2, k + 1):
            a_p = min(1.0 - (1.0 - alpha) ** (p_ - 1), 0.5); qp[p_] = float(_sr.ppf(1 - a_p, p_, df)) / math.sqrt(2)
        crit = np.vectorize(lambda x: qp.get(int(x), 0.0))(span); S = D > crit * se
    else: raise ValueError(method)
    np.fill_diagonal(S, False); return S


def scott_knott(means, mse, dfe, r_harm, alpha=0.05):
    """Групування середніх Скотта–Кнотта (1974): послідовне розбиття впорядкованих середніх на дві групи, що максимізує міжгрупову суму
    квадратів, доки відношення правдоподібності λ перевищує χ² за k/(π−2) ступенів свободи. → {сорт: номер групи 0,1,…} (0 – найраніша)."""
    from scipy.stats import chi2 as _chi2
    names = sorted(means, key=lambda c: means[c]); y = np.array([means[c] for c in names]); s2m = mse / r_harm; groups = [0] * len(names)
    def split(lo, hi):                                            # [lo, hi)
        k = hi - lo
        if k < 2: return [(lo, hi)]
        seg = y[lo:hi]; tot = seg.sum(); best = (-1.0, None)
        for i in range(1, k):
            t1 = seg[:i].sum(); t2 = tot - t1; b0 = t1 * t1 / i + t2 * t2 / (k - i) - tot * tot / k
            if b0 > best[0]: best = (b0, i)
        b0, i = best; sig2 = (np.sum((seg - seg.mean()) ** 2) + dfe * s2m) / (k + dfe)
        lam = math.pi / (2.0 * (math.pi - 2.0)) * b0 / sig2
        if lam > _chi2.ppf(1 - alpha, k / (math.pi - 2.0)): return split(lo, lo + i) + split(lo + i, hi)
        return [(lo, hi)]
    for g, (lo, hi) in enumerate(split(0, len(names))):
        for i in range(lo, hi): groups[i] = g
    return {c: g for c, g in zip(names, groups)}


def _letters(i):
    return "abcdefghijklmnopqrstuvwxyz"[i] if i < 26 else f"g{i}"


def _families(cvs, standard, ref_of):
    """Сорти, згруповані за їхнім стандартом: {стандарт: [сорти]} (стандарт – першим). Сорти без стандарту не потрапляють у жодне сімейство."""
    fam = {}
    for c in cvs:
        s_ = (ref_of or {}).get(c, standard) if ref_of else standard
        if s_ and s_ in cvs: fam.setdefault(s_, [s_])
        if s_ and s_ in cvs and c != s_: fam[s_].append(c)
    return fam


def compare_means(records, phase, an, method="auto", standard="", alpha=0.05, ref_of=None):
    """Порівняння середніх дат сортів для фази після ANOVA (an – результат anova_phase). Повертає:
    {'method', 'label', 'groups': {сорт: літери}, 'crit': критична різниця (діб) або None, 'vs': {сорт: {'diff','p','sig'}} або None,
     'p_overall': p загального критерію, 'note', 'ngroups'}. Літера «a» – найраніша група (за середньою датою)."""
    from sad_common import cld
    if "error" in an: return {"method": method, "label": METHOD_NAME.get(method, method), "error": an["error"]}
    cvs = list(an["means"]); k = len(cvs); key = resolve_method(method, k); out = {"method": key, "requested": method, "label": METHOD_NAME[key], "groups": {}, "crit": None, "vs": None,
                                                                                    "p_overall": an["p"], "note": "", "ngroups": None, "k": k}
    means = [an["means"][c] for c in cvs]; ns = [an["ns"][c] for c in cvs]; mse, dfe = an["mse"], an["dfe"]
    order_e = sorted(cvs, key=lambda c: an["means"][c])
    if key == "sk":
        gr = scott_knott(an["means"], mse, dfe, an["n_harm"], alpha); out["groups"] = {c: _letters(g) for c, g in gr.items()}; out["ngroups"] = len(set(gr.values()))
        out["note"] = f"Скотт–Кнотт: {out['ngroups']} груп без перекриття; «a» – найраніша."
        return out
    if key in ("dunnett", "control"):
        from scipy.stats import t as _t
        fam = _families(cvs, standard, ref_of)
        if not fam:
            out["note"] = "Оберіть стандарт (поле «Стандарт» або «Групи стиглості…» у головному вікні): порівняння зі стандартом без нього неможливе."; out["groups"] = {c: "" for c in cvs}; return out
        ix = {c: i for i, c in enumerate(cvs)}; out["vs"] = {}; crits = []; cvals = []; parts = []
        for std, members in fam.items():
            others = members[1:]
            if not others: out["vs"][std] = {"diff": 0.0, "p": 1.0, "sig": False, "crit_diff": float("nan")}; continue
            if key == "dunnett":
                import sad_control_core as CC
                lv = [std] + others
                try: r = CC.compare_estimates_to_control(lv, np.array([means[ix[c]] for c in lv], float), np.diag([mse / ns[ix[c]] for c in lv]), [std], int(dfe), alpha)
                except Exception as e:
                    out["note"] = f"Тест Даннетта не вдалося виконати: {e}"; out["groups"] = {c: "" for c in cvs}; out["vs"] = None; return out
                for x in r["rows"]: out["vs"][x["entry"]] = {"diff": x["diff"], "p": x["p_dunnett"], "sig": x["sig"], "crit_diff": x["dunnett_diff"]}; crits.append(round(x["dunnett_diff"], 6))
                cvals.append(float(r["crit"]))
            else:
                d = np.array([an["means"][c] - an["means"][std] for c in others]); se = np.array([math.sqrt(mse * (1.0 / an["ns"][c] + 1.0 / an["ns"][std])) for c in others])
                pa = holm_adjust(2 * _t.sf(np.abs(d) / se, int(dfe)))
                for i_, c in enumerate(others): out["vs"][c] = {"diff": float(d[i_]), "p": float(pa[i_]), "sig": bool(pa[i_] < alpha)}
            out["vs"][std] = {"diff": 0.0, "p": 1.0, "sig": False, "crit_diff": float("nan")}
            ne = sum(1 for c in others if out["vs"][c]["sig"] and out["vs"][c]["diff"] < 0); nl = sum(1 for c in others if out["vs"][c]["sig"] and out["vs"][c]["diff"] > 0)
            parts.append((std, len(others), ne, nl))
        stds = set(fam)
        out["groups"] = {c: ("станд." if c in stds else ("" if c not in out["vs"] else ("↓" if out["vs"][c]["sig"] and out["vs"][c]["diff"] < 0 else ("↑" if out["vs"][c]["sig"] else "≈")))) for c in cvs}
        uniq = sorted(set(crits))
        if key == "dunnett":
            if len(uniq) == 1: out["crit"] = uniq[0]
            if len(cvals) == 1: out["dunnett_c"] = cvals[0]
        meth = "Тест Даннетта" if key == "dunnett" else "t-критерій із поправкою Холма"
        if len(parts) == 1:
            std, k_, ne, nl = parts[0]
            extra = ""
            if key == "dunnett":
                cd = (f"критична різниця {uniq[0]:.1f} діб" if len(uniq) == 1 else f"критична різниця від {uniq[0]:.1f} до {uniq[-1]:.1f} діб (залежно від кількості спостережень)") if uniq else ""
                extra = f" (двобічний, α = {alpha:g}; критичне значення {cvals[0]:.3f}; {cd})"
            out["note"] = f"{meth}: кожен із {k_} сортів проти стандарту «{std}»{extra}. Істотно раніші (↓) – {ne}, істотно пізніші (↑) – {nl}, без істотної різниці (≈) – {k_ - ne - nl}."
        else:
            out["note"] = f"{meth} окремо в кожній групі стиглості (кожен сорт – проти стандарту своєї групи): " + "; ".join(f"«{std}» – {k_} сортів: ↓ {ne}, ↑ {nl}, ≈ {k_ - ne - nl}" for std, k_, ne, nl in parts) + "."
        nog = [c for c in cvs if c not in out["vs"]]
        if nog: out["note"] += f" Без стандарту (не порівнювались): {len(nog)}."
        return out
    if key == "kw":
        from scipy.stats import kruskal as _kw, rankdata as _rk, norm as _nm
        vals = {c: [r["doy"] for r in records if r["phase"] == phase and r["name"] == c] for c in cvs}; allv = np.array([v for c in cvs for v in vals[c]], float); N = len(allv)
        rk = _rk(allv); pos = 0; mr = {}; nn = {}
        for c in cvs: nc = len(vals[c]); mr[c] = float(np.mean(rk[pos:pos + nc])); nn[c] = nc; pos += nc
        try: out["p_overall"] = float(_kw(*[vals[c] for c in cvs]).pvalue)
        except ValueError: out["p_overall"] = float("nan"); out["note"] = "Усі значення однакові: критерій Краскела–Уолліса не визначений."; out["groups"] = {c: "a" for c in cvs}; return out
        _, cnt = np.unique(allv, return_counts=True); tie = float(np.sum(cnt ** 3 - cnt)) / (12.0 * (N - 1)) if N > 1 else 0.0; v0 = N * (N + 1) / 12.0 - tie
        mrv = np.array([mr[c] for c in cvs]); nv = np.array([nn[c] for c in cvs], float); se = np.sqrt(max(v0, 1e-12) * (1.0 / nv[:, None] + 1.0 / nv[None, :])); Z = np.abs(mrv[:, None] - mrv[None, :]) / se
        iu = np.triu_indices(k, 1); pa = holm_adjust(2 * _nm.sf(Z[iu])); S = np.zeros((k, k), bool); S[iu] = pa < alpha; S = S | S.T; out["mean_ranks"] = mr
        if k <= LETTER_MAX:
            sig = {(cvs[i], cvs[j]): bool(S[i, j]) for i in range(k) for j in range(i + 1, k)}; out["groups"] = cld(order_e, {c: -mr[c] for c in cvs}, sig)
        else: out["groups"] = {c: "" for c in cvs}
        out["note"] = f"Краскел–Уолліс: p = {out['p_overall']:.4f}; парні порівняння – Данн із поправкою Холма (за середніми рангами)." + ("" if k <= LETTER_MAX else f" Для понад {LETTER_MAX} сортів літери не формуються.")
        return out
    if key == "duncan" and k > DUNCAN_MAX:
        out["note"] = f"Дункан для понад {DUNCAN_MAX} сортів не рахується (окремий квантиль для кожної довжини діапазону); оберіть Тьюкі або Скотт–Кнотт."; out["groups"] = {c: "" for c in cvs}; return out
    S = _pair_sig(means, ns, mse, dfe, key, alpha); balanced = len(set(ns)) == 1
    if balanced and key in ("lsd", "tukey", "bonferroni"):
        from scipy.stats import t as _t, studentized_range as _sr
        se0 = math.sqrt(2 * mse / ns[0]); out["crit"] = se0 * (float(_t.ppf(1 - alpha / 2, int(dfe))) if key == "lsd" else (float(_t.ppf(1 - alpha / (2 * max(1, k * (k - 1) / 2)), int(dfe))) if key == "bonferroni" else float(_sr.ppf(1 - alpha, k, int(dfe))) / math.sqrt(2)))
    if k > LETTER_MAX:
        out["groups"] = {c: "" for c in cvs}; out["note"] = f"{out['label']}: для понад {LETTER_MAX} сортів літери парних порівнянь нечитабельні; скористайтесь Скоттом–Кноттом (групи) або порівнянням зі стандартом."
        out["n_sig_pairs"] = int(S.sum() // 2); return out
    if key == "lsd" and requested_gate(an, alpha, method):
        out["groups"] = {c: "a" for c in cvs}; out["note"] = f"Захищена НІР05: F-тест неістотний (p = {an['p']:.3f}), тож відмінностей між сортами немає."; out["ngroups"] = 1; return out
    sig = {(cvs[i], cvs[j]): bool(S[i, j]) for i in range(k) for j in range(i + 1, k)}; out["groups"] = cld(order_e, {c: -an["means"][c] for c in cvs}, sig)
    out["ngroups"] = len({v for v in out["groups"].values()})
    out["note"] = out["label"] + (f": критична різниця {out['crit']:.2f} діб." if out["crit"] is not None else ": різна кількість спостережень по сортах – критична різниця для кожної пари своя.")
    return out


def requested_gate(an, alpha, requested):
    """Захист НІР F-тестом застосовується лише в автоматичному режимі (для явно обраної «НІР05 (Фішер)» літери будуються завжди)."""
    return requested == "auto" and not math.isnan(an["p"]) and an["p"] >= alpha


# ═══════════════════════════════════════════════════════════════
# 6. Суми температур до настання фази
# ═══════════════════════════════════════════════════════════════
def temp_sum_between(series, d0, d1, base=10.0, kind="sat", upper=None, min_cover=0.95):
    """Сума температур за [d0, d1] включно. kind: 'sat' – активних (Σ t за t > base), 'set' – ефективних (Σ (t − base)). NaN, якщо дані не покривають період."""
    import sad_weather_core as W
    if d1 < d0: return float("nan")
    n = (d1 - d0).days + 1; sl = series.slice(d0, d1)
    if len(sl.dates) == 0: return float("nan")
    t = np.asarray(sl.get("tmean"), float); ok = ~np.isnan(t)
    if len(sl.dates) < n * min_cover or ok.sum() < n * min_cover: return float("nan")
    t = t[ok]
    return W.active_temp_sum(t, base) if kind == "sat" else W.effective_temp_sum(t, base, upper)


def temp_sums(records, series, start=("md", 1, 1), base=10.0, kind="sat", upper=None):
    """start: ('md', місяць, день) – щороку фіксована дата, або ('phase', ключ_фази) – від дати цієї фази в тому ж сорті, році й повторності.
    → список {year, name, rep, phase, sum}."""
    idx = {(r["year"], r["name"], r["rep"], r["phase"]): r["date"] for r in records}; out = []
    for r in records:
        if start[0] == "md":
            try: d0 = _D(r["year"], start[1], start[2])
            except ValueError: continue
        else:
            d0 = idx.get((r["year"], r["name"], r["rep"], start[1]))
            if d0 is None or r["phase"] == start[1]: continue
        out.append({"year": r["year"], "name": r["name"], "rep": r["rep"], "phase": r["phase"], "sum": temp_sum_between(series, d0, r["date"], base, kind, upper)})
    return out


def summarize_sums(sums, cultivars, phase_keys):
    by = {}
    for r in sums:
        if not math.isnan(r["sum"]): by.setdefault((r["name"], r["phase"]), []).append(r["sum"])
    return {(c, p): _stats(by.get((c, p), [])) for c in cultivars for p in phase_keys}


# ═══════════════════════════════════════════════════════════════
# 7. Дата настання за візитами (відсоток рослин у фазі)
# ═══════════════════════════════════════════════════════════════
def onset_from_visits(visits, threshold):
    """visits: [(дата, відсоток 0–100)]. Перший перетин порогу лінійною інтерполяцією між візитами. → (дата | None, 'interp'|'first'|'none').
    'first' – уже на першому візиті поріг досягнуто (дата не пізніша за цей візит)."""
    v = sorted((d, float(p)) for d, p in visits if d is not None and p is not None and not math.isnan(float(p)))
    if not v: return None, "none"
    if v[0][1] >= threshold: return v[0][0], "first"
    for (d0, p0), (d1, p1) in zip(v, v[1:]):
        if p1 >= threshold > p0:
            frac = (threshold - p0) / (p1 - p0); days = (d1 - d0).days * frac
            return d0 + _dt.timedelta(days=int(math.floor(days + 0.5))), "interp"
    return None, "none"


# ═══════════════════════════════════════════════════════════════
# 8. Проєкт (JSON)
# ═══════════════════════════════════════════════════════════════
def project_to_json(proj):
    return json.dumps({"format": "SAD-phenology", "version": 1, **proj}, ensure_ascii=False, indent=1)


def project_from_json(text):
    d = json.loads(text)
    if d.get("format") != "SAD-phenology": raise ValueError("Це не файл фенологічного проєкту S.A.D.")
    d["years_data"] = {int(k): v for k, v in d.get("years_data", {}).items()}
    return d


# ═══════════════════════════════════════════════════════════════
# 9. Повний розрахунок для вікна результатів
# ═══════════════════════════════════════════════════════════════
def analyze(years_data, phases, standard="", thr=3.0, series=None, sum_cfg=None, method="auto", groups=None, group_std=None):
    """Усе, що показує вікно результатів. phases: список словників (key, name, bbch) у порядку настання.
    sum_cfg: {'kind': 'sat'|'set', 'base': °C, 'start': ['md', м, д] | ['phase', ключ]}. Кидає ValueError, якщо немає жодної коректної дати."""
    keys = [p["key"] for p in phases]
    recs, errs, warns = collect_records(years_data, keys)
    if not recs: raise ValueError("У таблиці немає жодної коректної дати. Введіть дати хоча б для однієї фази.")
    first_order = []
    for y in sorted(years_data):
        for r in assign_reps(years_data[y]):
            if r["name"] not in first_order: first_order.append(r["name"])
    cultivars = [c for c in first_order if any(r["name"] == c for r in recs)]
    with_data = [p for p in phases if any(r["phase"] == p["key"] for r in recs)]; wk = [p["key"] for p in with_data]
    summ = summarize(recs, cultivars, wk)
    pairs = list(zip(wk, wk[1:])) + ([(wk[0], wk[-1])] if len(wk) > 2 else [])
    dur = durations(recs, cultivars, pairs)
    std = standard if standard in cultivars else ""
    grp = {c: g for c, g in (groups or {}).items() if c in cultivars and g}; gstd = {g: s_ for g, s_ in (group_std or {}).items() if s_ in cultivars and g in set(grp.values())}
    ref_of = reference_map(cultivars, std, grp, gstd) if gstd else None
    vs, ref = vs_standard(summ, cultivars, wk, std or None, thr, ref_of)
    anovas = {k: anova_phase(recs, k, cultivars) for k in wk}
    compare = {k: compare_means(recs, k, anovas[k], method, std, ref_of=ref_of) for k in wk}
    sums = None; nan_sums = 0
    if series is not None and sum_cfg:
        st = tuple(sum_cfg.get("start", ["md", 1, 1])); lst = temp_sums(recs, series, st, float(sum_cfg.get("base", 10.0)), sum_cfg.get("kind", "sat"))
        nan_sums = sum(1 for r in lst if math.isnan(r["sum"])); sums = summarize_sums(lst, cultivars, wk)
    return {"records": recs, "errors": errs, "warnings": warns, "cultivars": cultivars, "phases": with_data, "all_phases": phases, "summ": summ, "pairs": pairs, "dur": dur,
            "vs": vs, "ref": ref, "standard": std, "thr": thr, "groups": grp, "group_std": gstd, "ref_of": ref_of,
            "standards": sorted(({std} if std else set()) | set(gstd.values())), "anova": anovas, "compare": compare, "method": method, "sums": sums, "sum_cfg": sum_cfg if sums is not None else None, "nan_sums": nan_sums,
            "years": sorted({r["year"] for r in recs}), "n_obs": len(recs)}
