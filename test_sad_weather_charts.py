# test_sad_weather_charts.py – діаграми «Погоди»: легенди, стиль користувача, збереження налаштувань (без tkinter)
import os, sys, json, tempfile, shutil, math, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import matplotlib.colors as mc
import sad_weather_core as W, sad_weather_charts as CH, sad_weather_export as X
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg)
    if not c: FAIL.append(msg)
rg = np.random.default_rng(3); n = 1461; s0 = dt.date(2021, 1, 1)
dts = [s0 + dt.timedelta(days=i) for i in range(n)]; doy = np.array([d.timetuple().tm_yday for d in dts], float)
t = 9 + 11 * np.sin(2 * np.pi * (doy - 110) / 365) + rg.normal(0, 2, n)
ser = W.DailySeries(dts, {"tmean": t, "tmax": t + 4, "tmin": t - 4, "prec": np.where(rg.random(n) < .3, rg.gamma(2, 3, n), 0.)})
ser.meta.update({"retrieved_at": "2026-10-01T12:00:00"})
rep = W.build_report(ser, W.default_settings())
rep["norm"] = ({"tmean": 14.2, "prec_sum": 380.0}, [2000, 2001], "2000–2001")
def build(kind, style=None):
    f = Figure(dpi=100); r = CH.build_chart(f, kind, rep, "м. Умань", style); return f, r
def legend_text(f): return " | ".join(t.get_text() for a in f.axes if a.get_legend() for t in a.get_legend().get_texts())

print("== 1. Усі діаграми й легенди")
for kind, title in CH.CHARTS:
    f, r = build(kind); check(r is None and len(f.axes) >= 1, f"«{title}» будується")
f, _ = build("climo_decade"); lt = legend_text(f)
check("Середня температура" in lt and "крива" in lt and "ліва вісь" in lt and "Сума опадів" in lt and "стовпчики" in lt and "права вісь" in lt, f"декади: легенда пояснює, що крива – температура, стовпчики – опади: «{lt}»")
f, _ = build("climo_daily"); lt = legend_text(f); check("Опади" in lt and "Середня температура" in lt and "Розмах" in lt, f"добова кліматограма: легенда з трьох складових: «{lt}»")
f, _ = build("years_cmp"); lt = legend_text(f); check("Середня температура" in lt and "Сума опадів" in lt and "Норма" in lt, "порівняння років: легенди пояснюють точки, стовпчики й норму")
f, _ = build("walter"); lt = legend_text(f); check("Вологий" in lt and "Посушливий" in lt and "Температура" in lt and "Опади" in lt, "діаграма Вальтера: легенда")
f, _ = build("htc_month"); check("посуха" in legend_text(f) or "волого" in legend_text(f), "ГТК: легенда класів")
f, _ = build("cum_prec"); check(all(str(y) in legend_text(f) for y in (2021, 2022, 2023, 2024)), "нагромаджені опади: легенда за роками")

print("\n== 2. Стиль: загальні параметри")
G = CH.sanitize_general({})
check(G == CH.DEFAULT_GENERAL, "порожні налаштування = типові")
g2 = CH.sanitize_general({"width_cm": 1000, "height_cm": -5, "font_size": "abc", "legend_loc": "десь", "dpi": 5000, "grid": 1, "bogus": 3})
check(g2["width_cm"] == 60 and g2["height_cm"] == 6 and g2["font_size"] == CH.DEFAULT_GENERAL["font_size"] and g2["legend_loc"] == "авто" and g2["dpi"] == 600 and g2["grid"] is True and "bogus" not in g2,
      "некоректні значення обмежуються допустимими межами або повертаються до типових")
style = {"general": {"width_cm": 20, "height_cm": 12, "font_family": "DejaVu Sans", "font_size": 13, "title_size": 16, "title_bold": True, "tick_size": 11,
                     "legend_size": 12, "grid": True, "line_width": 3.0, "marker_size": 9, "show_subtitle": False}}
f, r = build("climo_decade", style); ax = f.axes[0]
check(abs(f.get_size_inches()[0] - 20 / 2.54) < 1e-9 and abs(f.get_size_inches()[1] - 12 / 2.54) < 1e-9, "розмір 20×12 см → дюйми точно")
check(ax.title.get_fontsize() == 16 and ax.title.get_fontweight() == "bold", "розмір і жирність заголовка")
check(ax.title.get_text().count("\n") == 0 or ax.get_title(loc="left").count("\n") == 0, "без підзаголовка заголовок однорядковий")
f0, _ = build("climo_decade"); check(f0.axes[0].get_title(loc="left").count("\n") == 1, "типово заголовок має підзаголовок (місце, період)")
check(ax.yaxis.get_ticklabels()[0].get_fontsize() == 11 and abs(ax.lines[0].get_linewidth() - 3.0) < 1e-9, "розмір підписів поділок і товщина ліній")
check(any(l.get_visible() for l in ax.xaxis.get_gridlines()) or any(l.get_visible() for l in ax.yaxis.get_gridlines()), "сітка")
lg = [a.get_legend() for a in f.axes if a.get_legend()][0]; check(lg.get_texts()[0].get_fontsize() == 12, "розмір шрифту легенди")
check(f.axes[0].xaxis.label.get_fontname() == "DejaVu Sans" or ax.title.get_fontname() == "DejaVu Sans", "шрифт застосовано")

print("\n== 3. Легенда: положення")
def leg(kind, loc):
    f, _ = build(kind, {"general": {"legend_loc": loc}}); return f, [a.get_legend() for a in f.axes if a.get_legend()]
f, L = leg("climo_decade", "без легенди"); check(L == [], "«без легенди» – легенди немає")
f, L = leg("climo_decade", "під графіком"); check(L and L[0]._loc == 9, "«під графіком» – легенда під віссю (upper center)")
f, L = leg("climo_decade", "внизу праворуч"); check(L and L[0]._loc == 4, "«внизу праворуч» → lower right")
f, L = leg("years_cmp", "угорі ліворуч"); check(len(L) == 2 and all(l._loc == 2 for l in L), "для двох графіків порівняння років положення застосовано до обох легенд")

print("\n== 4. Кольори складових")
cs = {"colors": {"climo_decade": {"tmean": "#006d2c", "prec": "#fd8d3c", "bad": "червоний"}, "walter": {"wet": "#00ff00"}}}
f, _ = build("climo_decade", cs); ax0 = f.axes[0]
check(any(mc.same_color(l.get_color(), "#006d2c") for l in ax0.lines), "колір кривої температури")
check(any(mc.same_color(p.get_facecolor()[:3], "#fd8d3c") for a in f.axes for p in a.patches), "колір стовпчиків опадів")
f, _ = build("walter", cs); check(any(mc.same_color(c.get_facecolor()[0][:3], "#00ff00") for a in f.axes for c in a.collections if len(c.get_facecolor())), "колір заливки вологого періоду")
f, _ = build("climo_daily", cs); check(any(mc.same_color(l.get_color(), "#b2182b") for l in f.axes[0].lines), "кольори іншої діаграми не змінюють цю (типовий колір лишився)")
st = CH.Style({"colors": {"x": {"a": "#fff", "b": "#12345", "c": "red", "d": "#112233"}}}, "x"); check(st.colors == {"a": "#fff", "d": "#112233"}, "некоректні кольори (не #RGB / #RRGGBB) відкидаються")
f, _ = build("htc_month", {"colors": {"htc_month": {"wet": "#ff00ff"}}}); check(any(mc.same_color(p.get_facecolor()[:3], "#ff00ff") for p in f.axes[0].patches), "ГТК: колір класу «надмірно волого» змінено")
check(all(len(CH.components(k, rep)) >= 2 for k, _ in CH.CHARTS), "для кожної діаграми є перелік складових для налаштування кольорів")
check([c[0] for c in CH.components("cum_prec", rep)] == ["y2021", "y2022", "y2023", "y2024"], "нагромаджені криві: окремий колір для кожного року")
f, _ = build("cum_prec", {"colors": {"cum_prec": {"y2022": "#123456"}}}); check(any(mc.same_color(l.get_color(), "#123456") for l in f.axes[0].lines), "колір конкретного року змінено")

print("\n== 5. Власний заголовок")
f, _ = build("walter", {"titles": {"walter": "Мій заголовок"}}); tt = f.axes[0].get_title(loc="left"); check(tt.startswith("Мій заголовок\n"), "власний заголовок, далі підзаголовок із місцем і періодом")
f, _ = build("walter", {"titles": {"walter": "Мій заголовок"}, "general": {"show_subtitle": False}}); check(f.axes[0].get_title(loc="left") == "Мій заголовок", "без підзаголовка")
f, _ = build("climo_daily", {"titles": {"walter": "Мій заголовок"}}); check(not f.axes[0].get_title(loc="left").startswith("Мій заголовок"), "заголовок діє лише для своєї діаграми")

print("\n== 6. Збереження налаштувань і Word")
tmp = tempfile.mkdtemp(); p = os.path.join(tmp, "sub", "st.json")
check(CH.save_style(style, p) and CH.load_style(p) == style, "налаштування записуються (з підтекою) і читаються назад")
check(CH.load_style(os.path.join(tmp, "немає.json")) == {}, "відсутній файл → типові налаштування")
open(os.path.join(tmp, "bad.json"), "w").write("{не json"); check(CH.load_style(os.path.join(tmp, "bad.json")) == {}, "пошкоджений файл → типові налаштування, без помилки")
open(os.path.join(tmp, "list.json"), "w").write("[1,2]"); check(CH.load_style(os.path.join(tmp, "list.json")) == {}, "файл не того формату → типові налаштування")
os.environ["APPDATA"] = tmp; check(CH.style_path().startswith(tmp) and CH.style_path().endswith("weather_chart_style.json"), "шлях налаштувань: %APPDATA%\\SAD\\weather_chart_style.json")
png_def = X.figure_png(rep, "walter", "м. Умань", CH.build_chart); png_sty = X.figure_png(rep, "walter", "м. Умань", CH.build_chart, style={"general": {"width_cm": 12, "height_cm": 8}})
from PIL import Image; import io
a, b = Image.open(io.BytesIO(png_def)).size, Image.open(io.BytesIO(png_sty)).size
check(png_def[:4] == b"\x89PNG" and b[0] < a[0] and b[1] < a[1], f"діаграма для Word будується зі стилем користувача (типова {a}, 12×8 см → {b})")
f, r = build("years_cmp"); ys = rep["years"]; rep_empty = dict(rep); rep_empty["years"] = []
f2 = Figure(); res = CH.build_chart(f2, "years_cmp", rep_empty, "м. Умань"); check(res and "розділі 3" in res, "порожнє порівняння років: повідомлення вказує на розділ 3 (роки й вікно)")
shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 56)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f_) for f_ in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ДІАГРАМ ПРОЙДЕНО")
