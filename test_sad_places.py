# test_sad_places.py – місце досліду: перелік раніше обраних місць, конструктор схеми → журнал → фенологія (погода NASA), модуль «Погода»
import os, sys, json, tempfile, shutil, time, datetime as dt
TMP = tempfile.mkdtemp(prefix="sad_places_"); os.environ["APPDATA"] = TMP
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import sad_weather_core as W
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
print("== 1. Перелік раніше обраних місць")
check(W.load_places() == [] and W.places_path().startswith(TMP), "спочатку перелік порожній (файл – у налаштуваннях користувача)")
W.remember_place("Умань, Україна", 48.754, 30.211); W.remember_place("Біла Церква", 49.796, 30.131); W.remember_place("Умань, Україна", 48.754, 30.211)
pl = W.load_places(); check([p["label"] for p in pl] == ["Умань, Україна", "Біла Церква"], f"останнє – першим, без повторів: {[p['label'] for p in pl]}")
W.remember_place("", 47.1, 33.2); check(W.load_places()[0]["label"] == "47.1000; 33.2000", "місце без назви – підписується координатами")
for i in range(45): W.remember_place(f"Місце {i}", 45 + i * 0.01, 30)
check(len(W.load_places()) == 40, "перелік обмежено 40 місцями")
check("Біла Церква" not in [p["label"] for p in W.load_places()], "найстаріші місця витісняються"); W.remember_place("Біла Церква", 49.796, 30.131)
sp = os.path.join(TMP, "s.sadp"); json.dump({"cfg": {"location": {"label": "Умань", "lat": 48.75, "lon": 30.22}}}, open(sp, "w", encoding="utf-8"))
check(W.location_from_file(sp) == {"label": "Умань", "lat": 48.75, "lon": 30.22} and W.location_from_file(os.path.join(TMP, "нема.sadp")) is None, "місце досліду читається з файла схеми")
json.dump({"cfg": {}}, open(os.path.join(TMP, "n.sadp"), "w")); check(W.location_from_file(os.path.join(TMP, "n.sadp")) is None, "схема без місця → None")

if os.environ.get("DISPLAY"):
    import tkinter as tk
    import matplotlib; matplotlib.use("Agg")
    import sad_weather as SW, sad_scheme_constructor as SC, sad_phenology as P, sad_phenology_win as PW, sad_phenology_dialogs as PD, sad_phenology_journal as PJ
    LOG = []
    for m in (SC.messagebox, SW.messagebox, PW.messagebox, PD.messagebox):
        m.showinfo = lambda t="", msg="", **k: LOG.append(("info", msg)); m.showwarning = lambda t="", msg="", **k: LOG.append(("warn", msg)); m.askyesno = lambda *a, **k: True
    root = tk.Tk(); root.withdraw()
    def all_w(x):
        out = [x]
        for c in x.winfo_children(): out += all_w(c)
        return out
    print("\n== 2. Конструктор схеми: місце досліду")
    sc = SC.SchemeConstructorWindow(root, {}); root.update()
    check(sc._loc_lbl.cget("text") == "(не задано)" and any("За назвою" in str(b.cget("text")) for b in all_w(sc._step1_frame) if b.winfo_class() == "Button"), "у Кроці 1 – «Місце досліду» з пошуком за назвою")
    check(any(isinstance(x, SW.SavedPlaces) for x in all_w(sc._step1_frame)), "і перелік раніше обраних місць")
    dlg = sc._loc_search(); root.update(); dlg._ps.qv.set("Умань"); dlg._ps.search(); root.update(); dlg._ps.lb.selection_set(0); dlg._ps.pick(); root.update()
    check(sc._location and sc._location["label"].startswith("Умань") and abs(sc._location["lat"] - 48.754) < 0.01, f"пошук за назвою: {sc._location}")
    check(W.load_places()[0]["label"].startswith("Умань"), "знайдене місце потрапило в перелік раніше обраних")
    sc._loc_coords("49,0; 31,5"); check(sc._location["lat"] == 49.0 and sc._location["lon"] == 31.5 and "49.0000" in sc._loc_lbl.cget("text"), "координати вручну (через «;», з комою)")
    n_w = len(LOG); check(sc._loc_coords("abc") is None and len(LOG) == n_w + 1, "некоректні координати – пояснення")
    sv = [x for x in all_w(sc._step1_frame) if isinstance(x, SW.SavedPlaces)][0]; sv.refresh(); vals = list(sv.cget("values")); i_bc = vals.index("Біла Церква")
    sv.current(i_bc); sv._sel(); check(sc._location["label"] == "Біла Церква" and abs(sc._location["lat"] - 49.796) < 1e-9, "вибір із переліку раніше обраних")
    sc._set_location({"label": "Умань, Україна", "lat": 48.754, "lon": 30.211})
    def set_entry(e, t_): e.delete(0, tk.END); e.insert(0, t_); e.event_generate("<KeyRelease>"); root.update()
    sc._model_var.set("area"); sc._on_model_change(); root.update(); sc._edit_factors(); root.update(); fd = [x for x in sc.win.winfo_children() if isinstance(x, tk.Toplevel)][-1]
    set_entry([x for x in all_w(fd) if x.winfo_class() == "Spinbox"][0], "1"); fr = [f_ for f_ in all_w(fd) if f_.winfo_class() == "Labelframe" and f_.cget("text").startswith("Фактор ")][0]
    es = [c for c in fr.winfo_children() if c.winfo_class() == "Entry"]; set_entry(es[0], "Сорт"); set_entry(es[1], "А, Б, В")
    [b for b in all_w(fd) if b.winfo_class() == "Button" and "Зберегти" in b.cget("text")][0].invoke(); root.update()
    [b for b in all_w(sc._step3_area_content) if b.winfo_class() == "Button" and "Сформувати план" in b.cget("text")][0].invoke(); root.update()
    d = sc._build_scheme_dict(); check(d["cfg"].get("location") == {"label": "Умань, Україна", "lat": 48.754, "lon": 30.211}, "місце зберігається у файлі схеми (cfg.location)")
    folder = os.path.join(TMP, "Дослід"); os.makedirs(folder); spath = os.path.join(folder, "схема.sadp")
    plants = [{"row": 1, "position": i + 1, "role": "recorded", "replication": 1, "factors": {"Сорт": i % 2 + 1}} for i in range(4)]
    sch = {"type": "multi_factor_scheme", "factor_defs": [{"name": "Сорт", "levels": ["А", "Б"]}], "variant_names": [], "cfg": dict(d["cfg"], model="area"), "plants": plants}
    json.dump(sch, open(spath, "w", encoding="utf-8"), ensure_ascii=False)
    SC.filedialog.askopenfilename = lambda **k: spath; sc2 = SC.SchemeConstructorWindow(root, {}); root.update(); sc2._load_scheme(); root.update()
    check(sc2._location and sc2._location["label"] == "Умань, Україна" and "Умань" in sc2._loc_lbl.cget("text"), "відкриття схеми відновлює місце досліду"); sc.win.destroy(); sc2.win.destroy()

    print("\n== 3. Журнал → фенологія: місце підставляється само")
    jj = dict(sch, type="field_journal", records={"Ф": {"kind": "date", "preset": "pome", "phase_key": "bloom0", "phase_name": "Початок цвітіння", "values": {f"1:{i + 1}": "05.05.2025" for i in range(4)}}})
    res = PJ.from_journal_years({"2025": jj}); check(res["location"] == {"label": "Умань, Україна", "lat": 48.754, "lon": 30.211}, "дані журналу містять місце досліду")
    pw = PW.PhenologyWindow(root); root.update(); pw.import_journal({"2025": jj}, quiet=True)
    check(pw.weather_coords == (48.754, 30.211) and pw.weather_place == "Умань, Україна", "фенологія з журналу: координати й назва місця досліду")
    wd = PD.WeatherDialog(pw.win, pw); root.update()
    check(wd.lat.get() == "48.754" and wd.lon.get() == "30.211" and wd.place_lbl.cget("text") == "Умань, Україна", "у діалозі погоди – місце досліду, лишається натиснути «Отримати з NASA»")
    check(any("Знайти за назвою" in str(b.cget("text")) for b in all_w(wd.win) if b.winfo_class() == "Button") and any(isinstance(x, SW.SavedPlaces) for x in all_w(wd.win)), "у діалозі погоди – пошук за назвою й перелік раніше обраних")
    sv2 = [x for x in all_w(wd.win) if isinstance(x, SW.SavedPlaces)][0]; sv2.refresh(); vals = list(sv2.cget("values")); sv2.current(vals.index("Біла Церква")); sv2._sel()
    check(wd.lat.get() == "49.7960" and pw.weather_place == "Біла Церква" and wd.place_lbl.cget("text") == "Біла Церква", "вибір із переліку раніше обраних змінює місце")
    dlg2 = wd.search_place(); root.update(); dlg2._ps.qv.set("Lviv"); dlg2._ps.search(); root.update(); dlg2._ps.lb.selection_set(0); dlg2._ps.pick(); root.update()
    check(pw.weather_place.startswith("Львів") and abs(float(wd.lat.get()) - 49.835) < 0.01, f"пошук за назвою в діалозі погоди: {pw.weather_place}")
    calls = []
    def fake(lat, lon, d0, d1, progress=None, **k):
        calls.append((lat, lon)); days = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
        return W.DailySeries(days, {"tmean": np.full(len(days), 12.0)})
    real = W.fetch_nasa; W.fetch_nasa = fake; wd.from_nasa()
    for _ in range(40):
        root.update(); time.sleep(0.05)
        if pw.series is not None: break
    W.fetch_nasa = real
    check(calls and abs(calls[0][0] - 49.835) < 0.01 and "Львів" in pw.weather_note, f"дані NASA для обраного місця: {pw.weather_note}")
    check(W.load_places()[0]["label"].startswith("Львів"), "місце, для якого отримано погоду, – першим у переліку")
    pj = os.path.join(TMP, "p.sadph"); pw.save_project(pj); pw2 = PW.PhenologyWindow(root); pw2.open_project(pj); check(pw2.weather_place.startswith("Львів") and pw2.weather_coords == pw.weather_coords, "проєкт фенології зберігає місце й координати")
    wd.win.destroy(); pw.win.destroy(); pw2.win.destroy()

    print("\n== 4. Модуль «Погода»: перелік і «📂 З досліду…»")
    ww = SW.WeatherWindow(root); root.update()
    check(any(isinstance(x, SW.SavedPlaces) for x in all_w(ww.win)) and any("З досліду" in str(b.cget("text")) for b in all_w(ww.win) if b.winfo_class() == "Button"), "у блоці «Місце досліду» – перелік раніше обраних і «📂 З досліду…»")
    loc = ww._place_from_scheme(spath); root.update()
    check(loc and ww.lat_var.get() == "48.7540" and ww.lon_var.get() == "30.2110" and ww.place_var.get() == "Умань, Україна", "«З досліду…»: місце й координати з файла схеми")
    n_i = len(LOG); check(ww._place_from_scheme(os.path.join(TMP, "n.sadp")) is None and len(LOG) == n_i + 1 and "конструкторі" in LOG[-1][1], "дослід без місця – пояснення, де його задати")
    sv3 = [x for x in all_w(ww.win) if isinstance(x, SW.SavedPlaces)][0]; sv3.refresh(); vals = list(sv3.cget("values")); sv3.current(vals.index("Біла Церква")); sv3._sel(); root.update()
    check(ww.place_var.get() == "Біла Церква" and ww.lat_var.get() == "49.7960", "вибір із переліку раніше обраних у «Погоді»")
    ww.win.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ МІСЦЯ ДОСЛІДУ ПРОЙДЕНО")
