# test_sad_worldmap.py – вбудована карта: дані, проєкція, відсікання, пошук, взаємодія, діалог (Xvfb для частини GUI)
import os, sys, math, time
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import sad_worldmap as M
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
rng = np.random.default_rng(4)
D = M.MapData.get()

print("== 1. Дані")
check(len(D.pop) == 7342 and D.pl.shape == (7342, 2), "7342 населені пункти")
check(all(D.layer("land", l) is not None for l in (0, 1, 2)) and D.layer("adm1", 0) is None and D.layer("adm1", 1) is not None and D.layer("river", 2) is not None, "шари: суша (3 рівні), межі областей і річки (2 рівні)")
check(np.all((D.pl[:, 0] >= -180) & (D.pl[:, 0] <= 180) & (D.pl[:, 1] >= -90) & (D.pl[:, 1] <= 90)), "координати міст у допустимих межах")
check(all(len(str(x)) > 0 for x in D.z["places_uk"]), "у всіх міст є українська назва")
check(D.country_at(30.2109, 48.7543) == "Україна" and D.country_at(2.35, 48.85) == "Франція" and D.country_at(-30, 0) == "", "країна за точкою: Умань → Україна, Париж → Франція, океан → порожньо")
n = D.nearest(30.2109, 48.7543); check(n and "Умань" in D.full_label(n[0]) and n[1] < 3, f"найближче місто до точки в Умані – «{D.full_label(n[0])}» ({n[1]:.1f} км)")
check(D.nearest(-30, 0) is None, "посеред океану найближчого міста в межах 150 км немає")
for q, expect in (("умань", "Умань"), ("УМАНЬ", "Умань"), ("Uman", "Умань"), ("kyiv", "Київ"), ("київ", "Київ"), ("париж", "Париж"), ("paris", "Париж"), ("львів", "Львів")):
    r = D.search(q); check(r and r[0]["label"].startswith(expect), f"пошук «{q}» → «{r[0]['label'] if r else '–'}»")
check(D.search("") == [] and D.search("zzzzqqq") == [], "порожній і безглуздий запит → порожній результат")
pr = D.search("san"); check(len(pr) > 3 and all(any("san" in str(D.z["places_" + k][r["index"]]).lower() for k in ("uk", "en", "loc", "ru")) for r in pr), "часткові збіги: кожен результат справді містить «san» в одній із назв")
r_ = D.search("odes")
tier = lambda r: 2 if any(str(D.z["places_" + k][r["index"]]).lower().startswith("odes") for k in ("uk", "en", "loc", "ru")) else 1
tiers = [tier(r) for r in r_]
check(len(r_) >= 3 and tiers == sorted(tiers, reverse=True) and 1 in tiers and 2 in tiers, "результати впорядковано: спершу назви, що починаються із запиту, потім ті, що його лише містять («Модесто», «Родос»)")
check(all(r_[i]["pop"] >= r_[i + 1]["pop"] for i in range(len(r_) - 1) if tiers[i] == tiers[i + 1]), "усередині кожної групи – за спаданням населення")
ex = D.search("Одеса"); check(ex and ex[0]["label"].startswith("Одеса") and abs(ex[0]["lat"] - 46.48) < 0.1, "«Одеса» знайдена з правильними координатами")
name_, cnt_ = D._dup.most_common(1)[0]; idxs_ = [i for i in range(len(D.pop)) if str(D.z["places_uk"][i]) == name_]
check(cnt_ > 1 and len({D.full_label(i) for i in idxs_}) > 1, f"однойменні міста («{name_}», {cnt_} шт.) розрізняються в підписі областю")

print("\n== 2. Проєкція й відсікання")
lon = rng.uniform(-180, 180, 1000); lat = rng.uniform(-84, 84, 1000); x, y = M.ll_to_m(lon, lat); lo2, la2 = M.m_to_ll(x, y)
check(max(np.abs(lo2 - lon).max(), np.abs(la2 - lat).max()) < 1e-9, "проєкція Web Mercator туди й назад точна")
check(abs(float(M.ll_to_m(0, 0)[0]) - 0.5) < 1e-12 and abs(float(M.ll_to_m(0, 0)[1]) - 0.5) < 1e-12 and float(M.ll_to_m(-180, 85)[0]) == 0.0, "(0°, 0°) – центр світу; −180° – лівий край")
check(M.nice_length(130) == 100 and M.nice_length(260) == 200 and M.nice_length(520) == 500 and M.nice_length(0.7) == 0.5, "«круга» довжина масштабної лінійки: 130→100, 260→200, 520→500")
try:
    from shapely.geometry import Polygon, LineString, box
    R = (0, 0, 100, 80); worst = 0.0; cnt = 0
    for k in range(300):
        n_ = rng.integers(5, 40); ang = np.sort(rng.uniform(0, 2 * np.pi, n_)); rad = rng.uniform(20, 160, n_)
        px = 50 + rad * np.cos(ang); py = 40 + rad * np.sin(ang); P = Polygon(np.column_stack([px, py]))
        if not P.is_valid: continue
        ref = P.intersection(box(*R)); got = M.clip_polygon(px, py, *R)
        a = Polygon(got).area if len(got) >= 3 else 0.0
        if ref.area > 1: worst = max(worst, abs(a - ref.area) / ref.area); cnt += 1
    check(cnt > 100 and worst < 1e-9, f"відсікання полігонів збігається з shapely ({cnt} випадків, розбіжність {worst:.1e})")
    worst = 0.0
    for k in range(300):
        pts = rng.uniform(-80, 180, (rng.integers(2, 30), 2)); ref = LineString(pts).intersection(box(*R)).length
        got = sum(np.sum(np.hypot(*np.diff(sg, axis=0).T)) for sg in M.clip_polyline(pts[:, 0], pts[:, 1], *R)); worst = max(worst, abs(got - ref))
    check(worst < 1e-9, f"відсікання ламаних збігається з shapely (розбіжність довжини {worst:.1e})")
except ImportError:
    print("  (shapely не встановлено – порівняння з еталоном пропущено)")
sq = M.clip_polygon([-1e6, 1e6, 1e6, -1e6], [-1e6, -1e6, 1e6, 1e6], 0, 0, 100, 80)
check(len(sq) == 4 and np.allclose(sorted(map(tuple, sq)), [(0, 0), (0, 80), (100, 0), (100, 80)]), "величезний полігон, що накриває вікно, обрізається рівно до вікна")
check(len(M.clip_polygon([200, 300, 300], [0, 0, 50], 0, 0, 100, 80)) == 0 and M.clip_polyline([200, 300], [0, 0], 0, 0, 100, 80) == [], "контури повністю поза вікном відкидаються")
seg = M.clip_polyline([-50, 150], [40, 40], 0, 0, 100, 80); check(len(seg) == 1 and np.allclose(seg[0], [[0, 40], [100, 40]]), "лінія, що перетинає вікно, обрізається по краях")

print("\n== 3. Віджет: малювання, миша, масштаб")
import tkinter as tk
from tkinter import messagebox
messagebox.showwarning = lambda *a, **k: None
root = tk.Tk(); root.geometry("1000x660+0+0")
picked = []; hov = []
m = M.WorldMap(root, width=1000, height=640, on_pick=lambda lo, la: picked.append((lo, la)), on_hover=lambda lo, la: hov.append((lo, la)))
m.pack(fill="both", expand=True); root.update(); m.fit_world(); root.update()
check(m.z >= 1.0 and m.stats["items"] > 300, f"світовий вигляд: z = {m.z:.2f}, елементів {m.stats['items']}")
for name, lo, la, z in (("Європа", 20, 50, 4.0), ("Україна", 31, 49, 5.6), ("область", 30.5, 49.0, 7.5), ("місто", 30.2109, 48.7543, 10.0)):
    m.goto(lo, la, z); root.update(); t = m.stats["redraw_ms"]
    check(t < 2000 and m.stats["items"] > 0, f"перемальовування «{name}» (z = {z}): {t:.0f} мс, {m.stats['items']} елементів")
m.goto(30.2109, 48.7543, 6.0); root.update(); w, h = m.size()
px, py = m.to_px(30.2109, 48.7543); check(abs(px - w / 2) < 1e-6 and abs(py - h / 2) < 1e-6, "центр карти збігається з центром полотна")
lo, la = m.from_px(px + 120, py - 80); px2, py2 = m.to_px(lo, la); check(abs(px2 - (px + 120)) < 1e-6 and abs(py2 - (py - 80)) < 1e-6, "піксель → координати → піксель точний")
picked.clear(); m.pick_at(px + 120, py - 80); check(len(picked) == 1 and abs(picked[0][0] - lo) < 1e-9 and abs(picked[0][1] - la) < 1e-9 and m.marker == (lo, la), "клік обирає точку: колбек отримує координати, що відповідають пікселю")
check(m.stats["items"] > 0 and any(m.type(i) == "text" and "°" in str(m.itemcget(i, "text")) for i in m.find_all()), "біля маркера підписано координати")
m.pick_at(px, py); lat0 = m.marker[1]
# масштаб коліщатком: точка під курсором лишається на місці
m.goto(30.2109, 48.7543, 5.0); root.update(); cx_, cy_ = 300, 200; lo_b, la_b = m.from_px(cx_, cy_)
m._zoom_at(cx_, cy_, 1.0); root.update(); lo_a, la_a = m.from_px(cx_, cy_)
check(abs(m.z - 6.0) < 1e-9 and abs(lo_a - lo_b) < 1e-9 and abs(la_a - la_b) < 1e-9, "масштабування навколо курсора: точка під курсором не зсувається")
m.z = 9.5; m._zoom_at(100, 100, 5.0); check(m.z == M.ZMAX, f"верхня межа масштабу ({M.ZMAX})")
m._zoom_at(100, 100, -50.0); check(abs(m.z - m.zmin()) < 1e-9, "нижня межа масштабу – світ вміщається у вікно")
# перетягування
m.goto(30, 49, 6.0); root.update(); c0 = (m.cx, m.cy); m._on_press(type("E", (), {"x": 400, "y": 300})()); m._on_drag(type("E", (), {"x": 480, "y": 340})()); m._on_release(type("E", (), {"x": 480, "y": 340})())
check(abs(m.cx - (c0[0] - 80 / m.world)) < 1e-12 and abs(m.cy - (c0[1] - 40 / m.world)) < 1e-12 and m._moved, "перетягування на 80×40 px зсуває центр карти на відповідні частки світу")
n_p = len(picked); m._on_press(type("E", (), {"x": 500, "y": 300})()); m._on_release(type("E", (), {"x": 502, "y": 301})()); check(len(picked) == n_p + 1, "клік із дрібним тремтінням (≤ 4 px) – це вибір точки, а не перетягування")
n_p = len(picked); m._on_press(type("E", (), {"x": 500, "y": 300})()); m._on_drag(type("E", (), {"x": 540, "y": 300})()); m._on_release(type("E", (), {"x": 540, "y": 300})()); check(len(picked) == n_p, "після перетягування точка не обирається")
m.goto(179.9, 0, 6.0); root.update(); check(0 <= m.cx <= 1, "центр не виходить за межі світу")
m.lang = "en"; m.goto(2.35, 48.85, 6.0); root.update(); texts = [str(m.itemcget(i, "text")) for i in m.find_all() if m.type(i) == "text"]
check(any("Paris" in t for t in texts), "англійські назви: «Paris» на карті"); m.lang = "uk"; m.redraw()
texts = [str(m.itemcget(i, "text")) for i in m.find_all() if m.type(i) == "text"]; check(any("Париж" in t for t in texts), "українські назви: «Париж» на карті")
m.goto(30.2, 48.75, 10.5); root.update(); check(m.stats["redraw_ms"] < 2000, "максимальне наближення малюється (великі координати відсічено)")
m.destroy()

print("\n== 4. Пошук і діалог")
fake_online = lambda q: [{"label": "Яблунівка, Черкаська область", "lat": 48.683, "lon": 30.165, "kind": "village"}]
dlg = M.MapPickerDialog(root, None, None, online_search=fake_online); dlg.win.update()
check(dlg.ok_btn.cget("state") == "disabled" and dlg.result is None, "до вибору точки кнопка «Обрати цю точку» вимкнена")
dlg._set_point(30.2109, 48.7543); check(dlg.ok_btn.cget("state") == "normal" and dlg.lat_v.get() == "48.7543" and "Умань" in dlg.near.cget("text") and "Україна" in dlg.near.cget("text"), "після вибору точки: координати, країна й найближче місто, кнопка активна")
dlg._ok(); check(dlg.result and abs(dlg.result["lat"] - 48.7543) < 1e-9 and abs(dlg.result["lon"] - 30.2109) < 1e-9 and dlg.result["label"].startswith("Умань"), f"результат: координати й підказка назви «{dlg.result['label']}»")
dlg2 = M.MapPickerDialog(root, 49.4444, 32.0598); dlg2.win.update(); time.sleep(0.2); root.update()
check(dlg2.lat is not None and abs(dlg2.lat - 49.4444) < 1e-9 and dlg2.map.marker is not None, "якщо координати вже є, діалог відкривається на них із маркером")
dlg2.lat_v.set("48°45'N"); dlg2.lon_v.set("30°13'E"); dlg2._goto_entries(); check(abs(dlg2.lat - 48.75) < 1e-9 and abs(dlg2.lon - 30.21666667) < 1e-6, "перехід за координатами у форматі ГМС")
dlg2.lat_v.set("95"); dlg2.lon_v.set("10"); old = dlg2.lat; dlg2._goto_entries(); check(dlg2.lat == old, "некоректні координати відхилено без зміни точки")
dlg2.win.destroy()
host = tk.Toplevel(root); got = []; calls = []
def online_counting(q):
    calls.append(q); return fake_online(q)
ps = M.PlaceSearch(host, got.append, online_search=online_counting); ps.pack()
def all_w(w):
    out = [w]
    for c in w.winfo_children(): out += all_w(c)
    return out
check(not any(w.winfo_class() == "Button" and "інтернет" in str(w.cget("text")).lower() for w in all_w(host)) and len([w for w in all_w(host) if w.winfo_class() == "Button"]) == 1,
      "у пошуку лише одна кнопка «Знайти»: окремої кнопки для інтернету немає")
ps.qv.set("умань"); ps.search(); check(ps.found and "Умань" in ps.found[0]["label"] and calls == [], "назва є у власній базі → знайдено без звернення до інтернету")
check(ps.info.cget("text") == "" and ps.lb.curselection() == (0,), "для результату з бази жодних пояснень про джерело; перший результат виділено")
ps.lb.selection_clear(0, "end"); ps.lb.selection_set(0); ps.pick(); check(got and abs(got[0]["lat"] - 48.754) < 0.01, "вибір результату повертає координати")
ps.qv.set("Яблунівка"); ps.search()
check(calls == ["Яблунівка"] and ps.found and ps.found[0]["kind"] == "village" and ps.lb.curselection() == (0,), "назви немає в базі → пошук в інтернеті запускається автоматично, одним запитом, без окремої дії користувача")
check("OpenStreetMap" in ps.info.cget("text") and "ODbL" in ps.info.cget("text"), "для результату з інтернету показано лише атрибуцію даних (вимога ліцензії)")
check(host.cget("cursor") == "", "після пошуку курсор очікування знято")
ps.qv.set("умань"); ps.search(); check(len(calls) == 1 and ps.info.cget("text") == "", "наступний пошук за назвою з бази знову не торкається інтернету; примітка про джерело зникає")
ps.qv.set("Умань"); ps.ent.event_generate("<Return>"); root.update(); check(len(calls) == 1 and ps.found and "Умань" in ps.found[0]["label"], "клавіша Enter у полі запускає той самий пошук")
ps3 = M.PlaceSearch(host, got.append, online_search=lambda q: []); ps3.pack(); ps3.qv.set("zzzzqqq"); ps3.search()
check(ps3.found == [] and ps3.lb.get(0) == "Нічого не знайдено" and "Перевірте написання" in ps3.info.cget("text") and "інтернет" not in ps3.info.cget("text").lower(), "немає ні в базі, ні в інтернеті → «Нічого не знайдено», підказка перевірити написання")
def boom(q): raise RuntimeError("Немає з'єднання")
ps2 = M.PlaceSearch(host, got.append, online_search=boom); ps2.pack(); ps2.qv.set("zzzzqqq"); ps2.search()
check(ps2.found == [] and "підключення до інтернету" in ps2.info.cget("text") and "«zzzzqqq»" in ps2.info.cget("text") and host.cget("cursor") == "", "в базі немає, інтернету немає → зрозуміле повідомлення в самому вікні; курсор знято; вікно не руйнується")
ps2.qv.set("київ"); ps2.search(); check(ps2.found and "Київ" in ps2.found[0]["label"], "без інтернету міста з бази знаходяться як і раніше")
ps2.qv.set("   "); n_f = len(ps2.found); ps2.search(); check(len(ps2.found) == n_f, "порожній запит нічого не робить")
check(all("score" in r and r["score"] in (1, 2, 3) for r in M.MapData.get().search("odes")) and M.MapData.get().search("умань")[0]["score"] == 3 and M.MapData.get().search("Ума")[0]["score"] == 2, "результати пошуку мають оцінку збігу: 3 точний, 2 початок назви, 1 лише входження")
calls.clear(); ps.qv.set("Ума"); ps.search(); check(calls == [] and ps.found and ps.found[0]["label"].startswith("Умань"), "початок назви («Ума») – це збіг у власній базі: інтернет не потрібен")
ps.qv.set("Село"); ps.search(); check(calls == ["Село"] and ps.found[0]["kind"] == "village", "«Село» лише входить у назви міст (Барселона…) → це не збіг: перевіряється інтернет, і там знайдено село")
ps4 = M.PlaceSearch(host, got.append, online_search=boom); ps4.pack(); ps4.qv.set("Село"); ps4.search()
check(ps4.found and any("Барселона" in r["label"] for r in ps4.found) and "схожі назви" in ps4.info.cget("text") and ps4.lb.curselection() == (0,), "інтернету немає: показано схожі назви з власної бази з коротким поясненням, а не порожній результат")
ps5 = M.PlaceSearch(host, got.append, online_search=lambda q: []); ps5.pack(); ps5.qv.set("Село"); ps5.search(); check(ps5.found and "схожі назви" in ps5.info.cget("text"), "інтернет нічого не знайшов: показано схожі назви з власної бази")
host.destroy()
if dlg.win.winfo_exists(): dlg.win.destroy()
h2 = tk.Toplevel(root); p2 = M.PlaceSearch(h2, lambda r: None); p2.pack(); root.update(); p2.qv.set("zzzzqqq"); p2.search()
check("Перевірте назву" in p2.info.cget("text") and p2.found == [], "якщо функцію інтернет-пошуку не передано, відсутність результату пояснюється просто («Перевірте назву»)")
h2.destroy(); root.destroy()
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ КАРТИ ПРОЙДЕНО")
