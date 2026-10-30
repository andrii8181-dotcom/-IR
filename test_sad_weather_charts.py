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
    f, r = build(kind)
    if kind in ("vine", "spi", "humidity"): check(r is not None and len(f.axes) == 1, f"«{title}» без широти / без SPI повертає пояснення замість діаграми: «{r[:60]}…»")
    else: check(r is None and len(f.axes) >= 1, f"«{title}» будується")
f, _ = build("climo_decade"); lt = legend_text(f)
check("Середня температура" in lt and "крива" in lt and "ліва вісь" in lt and "Сума опадів" in lt and "стовпчики" in lt and "права вісь" in lt, f"декади: легенда пояснює, що крива – температура, стовпчики – опади: «{lt}»")
f, _ = build("climo_daily"); lt = legend_text(f); check("Опади" in lt and "Середня температура" in lt and "Розмах" in lt, f"добова кліматограма: легенда з трьох складових: «{lt}»")
f, _ = build("years_cmp"); lt = legend_text(f); check("Середня температура" in lt and "Сума опадів" in lt and "Норма" in lt, "порівняння років: легенди пояснюють точки, стовпчики й норму")
f, _ = build("walter"); lt = legend_text(f); check("Вологий" in lt and "Посушливий" in lt and "Температура" in lt and "Опади" in lt, "діаграма Вальтера: легенда")
f, _ = build("htc_month"); check("посуха" in legend_text(f) or "волого" in legend_text(f), "ГТК: легенда класів")
f, _ = build("cum_prec"); check(all(str(y) in legend_text(f) for y in (2021, 2022, 2023, 2024)), "нагромаджені опади: легенда за роками")

print("\n== 1б. Вінклер/Югліна та SPI")
import sad_weather_indices as WI
n2 = 365 * 38 + 10; d02 = dt.date(1988, 1, 1); dts2 = [d02 + dt.timedelta(days=i) for i in range(n2)]; dy2 = np.array([d.timetuple().tm_yday for d in dts2], float)
rg3 = np.random.default_rng(8); t2 = 10.5 + 11.5 * np.sin(2 * np.pi * (dy2 - 110) / 365) + rg3.normal(0, 2.2, n2)
ser2 = W.DailySeries(dts2, {"tmean": t2, "tmax": t2 + 5, "tmin": t2 - 5, "prec": np.where(rg3.random(n2) < .32, rg3.gamma(1.4, 5.5, n2), 0.), "rad": np.full(n2, 15.0), "wind": np.full(n2, 2.5), "rh": np.full(n2, 70.0)})
st2 = W.default_settings(); st2["lat"] = 48.75; sp2 = WI.spi_table(ser2, ref=(1991, 2020), scales=(1, 3, 12), study=(dt.date(2021, 1, 1), dt.date(2024, 12, 31)))
rep2 = W.build_report(ser2.slice(dt.date(2015, 1, 1), dt.date(2024, 12, 31)), st2, spi=sp2)
def build2(kind, style=None): f = Figure(dpi=100); r = CH.build_chart(f, kind, rep2, "м. Умань", style); return f, r
f, r = build2("vine"); check(r is None and len(f.axes) == 2, "діаграма Вінклера й Югліна: 2 панелі"); lt = legend_text(f)
check("Вінклера" in lt and "Югліна" in lt and "Межі класів" in lt, f"легенда: «{lt}»")
check(f.axes[0].get_xlim()[1] > len(rep2["intl"]["vine"]) - 0.4, "праворуч залишено поле для підписів меж класів")
check(len(f.axes[0].patches) == len(rep2["intl"]["vine"]) and len(f.axes[1].patches) == len(rep2["intl"]["vine"]), "стовпчик на кожен сезон в обох панелях")
check(any("→ " in t.get_text() for t in f.axes[1].texts), "підписано межі класів Югліна (→ HI−2 тощо)")
from matplotlib.backends.backend_agg import FigureCanvasAgg
rend = FigureCanvasAgg(f).get_renderer(); overlaps = []
for ax in f.axes:
    lg = ax.get_legend(); lb = lg.get_window_extent(rend)
    for t_ in ax.texts:
        if "→" not in t_.get_text() and lb.overlaps(t_.get_window_extent(rend)): overlaps.append(t_.get_text())
check(not overlaps, f"легенда не перекриває підписи значень над стовпчиками (перекриттів: {len(overlaps)})")
f, r = build2("vine", {"colors": {"vine": {"winkler": "#00aa00", "huglin": "#0000cc"}}})
check(any(mc.same_color(p.get_facecolor()[:3], "#00aa00") for p in f.axes[0].patches) and any(mc.same_color(p.get_facecolor()[:3], "#0000cc") for p in f.axes[1].patches), "кольори стовпчиків Вінклера й Югліна налаштовуються")
f, r = build2("spi"); check(r is None and len(f.axes) == 3, "SPI: окрема панель для кожного з 3 масштабів"); lt = legend_text(f)
check("Вологі" in lt and "Сухі" in lt and "Межі класів" in lt, f"легенда SPI: «{lt}»")
sub_ = f.axes[0].get_title(loc="left"); check("01.2021–12.2024" in sub_ and "1991–2020" in sub_ and "2015" not in sub_, "підзаголовок SPI показує місяці SPI (2021–2024), а не весь завантажений ряд")
z1 = np.array([r_["spi"][1] for r_ in sp2["rows"]]); bars = f.axes[0].patches
check(len(bars) == 2 * len(z1) and sum(1 for p_, z_ in zip(bars[:len(z1)], z1) if z_ >= 0 and p_.get_height() > 0) == int((z1 >= 0).sum()), "додатні SPI – вгору, від'ємні – вниз")
f, r = build2("spi", {"colors": {"spi": {"wet": "#00aa00", "dry": "#aa00aa"}}}); check(any(mc.same_color(p.get_facecolor()[:3], "#00aa00") for p in f.axes[0].patches) and any(mc.same_color(p.get_facecolor()[:3], "#aa00aa") for p in f.axes[0].patches), "кольори вологих і сухих місяців SPI налаштовуються")
f, r = build2("spi", {"general": {"legend_loc": "без легенди"}}); check(legend_text(f) == "", "SPI: легенду можна вимкнути")
sp_none = {"rows": [], "scales": [1], "ref": (1991, 2020), "n_ref": {1: 0}, "warnings": [], "params": {}}; rep_ns = dict(rep2); rep_ns["spi"] = sp_none; fn_ = Figure(); check(CH.build_chart(fn_, "spi", rep_ns, "x") is not None, "порожній SPI → пояснення")
rep_nl = W.build_report(ser2.slice(dt.date(2015, 1, 1), dt.date(2024, 12, 31)), W.default_settings()); fnl = Figure(); res_ = CH.build_chart(fnl, "vine", rep_nl, "x"); check(res_ and "широта" in res_, "Вінклер без широти → пояснення, що обрати місце")
part_ = ser2.slice(dt.date(2022, 6, 1), dt.date(2023, 3, 31)); rep_p = W.build_report(part_, st2); fpp = Figure(); res_ = CH.build_chart(fpp, "vine", rep_p, "x")
check(res_ is not None and "повним покриттям" in res_, "ряд без жодного повного сезону (червень 2022 – березень 2023) → пояснення, чому діаграми немає")
full_ = ser2.slice(dt.date(2022, 6, 1), dt.date(2024, 3, 31)); rep_f = W.build_report(full_, st2); ff_ = Figure()
check(CH.build_chart(ff_, "vine", rep_f, "x") is None and len(rep_f["intl"]["vine"]) == 1 and rep_f["intl"]["vine"][0]["label"] == "2023", "а якщо в ряді є один повний сезон (2023) – діаграма будується з одним стовпчиком")
check(all(len(CH.components(k, rep2)) >= 2 for k in ("vine", "spi")) and [c[0] for c in CH.components("vine")] == ["winkler", "huglin", "bounds"] and [c[0] for c in CH.components("spi")] == ["wet", "dry", "lim"], "складові для налаштування кольорів нових діаграм")

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
print("\n== 7. Вологість повітря")
f, r = build("humidity"); check(r is not None and "немає вологості повітря" in r and "RH2M" in r and len(f.axes) == 1, f"без вологості: пояснення з назвою параметра NASA «{r[:70]}…»")
_dd = [dt.date(2022, 1, 1) + dt.timedelta(days=k) for k in range(730)]; _dy = np.array([x.timetuple().tm_yday for x in _dd], float); _tt = 10 + 12 * np.sin(2 * np.pi * (_dy - 110) / 365); _rr = np.clip(66 + 22 * np.cos(2 * np.pi * (_dy - 15) / 365), 15, 100)
rep_h = W.build_report(W.DailySeries(_dd, {"tmean": _tt, "tmax": _tt + 5, "tmin": _tt - 5, "prec": np.full(730, 1.0), "rh": _rr}), W.default_settings())
def buildh(style=None):
    ff = Figure(dpi=100); rr_ = CH.build_chart(ff, "humidity", rep_h, "м. Умань", style); return ff, rr_
f, r = buildh(); check(r is None and len(f.axes) == 3, f"з вологістю будується: {len(f.axes)} осі (вологість, лічильники діб, VPD)")
bars = [p.get_height() for p in f.axes[0].patches]; mo = [m["rh"] for m in rep_h["months"]]
check(len(bars) == 24 and np.allclose(bars, mo), "стовпчики = середня вологість кожного з 24 місяців")
vp = f.axes[2].lines[0].get_ydata(); check(np.allclose(vp, [m["vpd"] for m in rep_h["months"]]), "лінія VPD = середній VPD місяців")
hl = sorted(round(float(l.get_ydata()[0])) for l in f.axes[0].lines if len(set(l.get_ydata())) == 1); check(hl == [30, 80], "на графіку пунктирні межі 30 % і 80 %")
b3 = [p.get_height() for p in f.axes[1].patches]; check(len(b3) == 48 and sum(b3[:24]) == sum(m["days_rh_hi"] for m in rep_h["months"]) and sum(b3[24:]) == sum(m["days_rh_lo"] for m in rep_h["months"]), "нижня панель: діб ≥80 % і ≤30 % за місяцями (суми збігаються)")
_ymax = max(p.get_height() for p in f.axes[1].patches); check(f.axes[1].get_ylim()[1] >= _ymax * 1.3, f"нижня панель має запас по висоті для легенди (межа {f.axes[1].get_ylim()[1]:.1f} при максимумі {_ymax:.0f})")
lt = legend_text(f); check("Вологість повітря" in lt and "VPD" in lt and "≥ 80 %" in lt and "≤ 30 %" in lt, f"легенда: {lt[:90]}")
check(len(f.axes[1].get_xticklabels()) == 24 and f.axes[1].get_xticklabels()[0].get_text() == rep_h["months"][0]["label"], "підписи місяців на осі X")
f, _ = buildh({"colors": {"humidity": {"rh": "#00aa00", "vpd": "#aa00aa", "hi": "#0000cc"}}})
check(any(mc.same_color(p.get_facecolor()[:3], "#00aa00") for p in f.axes[0].patches) and mc.same_color(f.axes[2].lines[0].get_color(), "#aa00aa") and any(mc.same_color(p.get_facecolor()[:3], "#0000cc") for p in f.axes[1].patches), "кольори складових змінюються зі стилем користувача")
check([c[0] for c in CH.components("humidity")] == ["rh", "vpd", "hi", "lo", "thr"], "перелік складових для налаштування кольорів")
f, _ = buildh({"titles": {"humidity": "Мій заголовок"}}); check(f.axes[0].get_title(loc="left").startswith("Мій заголовок\n"), "власний заголовок для діаграми вологості")
rep_one = W.build_report(W.DailySeries(_dd[:20], {"tmean": _tt[:20], "tmax": _tt[:20] + 5, "tmin": _tt[:20] - 5, "prec": np.zeros(20), "rh": _rr[:20]}), W.default_settings()); f1 = Figure(); r1 = CH.build_chart(f1, "humidity", rep_one, "x")
check(r1 is None and len([p for p in f1.axes[0].patches]) == 1, "один місяць даних – діаграма з одним стовпчиком")
_rr2 = _rr.copy(); _rr2[:365] = np.nan; rep_g = W.build_report(W.DailySeries(_dd, {"tmean": _tt, "tmax": _tt + 5, "tmin": _tt - 5, "prec": np.full(730, 1.0), "rh": _rr2}), W.default_settings()); fg = Figure(); rg_ = CH.build_chart(fg, "humidity", rep_g, "x")
check(rg_ is None and len(fg.axes[0].patches) == 12, "місяці без жодного значення вологості пропускаються (12 із 24)")
import io as _io; _b = _io.BytesIO(); f.savefig(_b, format="png", dpi=80); check(_b.getvalue()[:4] == b"\x89PNG" and len(_b.getvalue()) > 5000, "діаграму можна зберегти як зображення")

print("\n" + "=" * 56)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f_) for f_ in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ДІАГРАМ ПРОЙДЕНО")
