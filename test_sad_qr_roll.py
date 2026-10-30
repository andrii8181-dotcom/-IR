# test_sad_qr_roll.py – етикетки для принтерів етикеток (рулон): пресети, сітка точок, PDF «одна етикетка – одна сторінка», розпізнавання QR при 203 dpi
import os, sys, io, math, random, itertools, tempfile, shutil, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import sad_qrlabels as Q
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
import zxingcpp, pymupdf
from PIL import Image, ImageFilter
TMP = tempfile.mkdtemp(prefix="sad_roll_")
def area_scheme(factors, reps, seed=1):
    fdefs = [{"name": n, "levels": lv} for n, lv in factors]; combos = list(itertools.product(*[range(1, len(f["levels"]) + 1) for f in fdefs])); rng = random.Random(seed); plants = []
    for b in range(1, reps + 1):
        order = combos[:]; rng.shuffle(order)
        for j, c in enumerate(order, 1): plants.append({"row": b, "position": j, "role": "recorded", "replication": b, "factors": {fdefs[i]["name"]: c[i] for i in range(len(fdefs))}})
    return {"factor_defs": fdefs, "cfg": {"model": "area", "design_used": "rcbd"}, "plants": plants}
FACT = [("Сорт", ["Голден Делішес", "Гала", "Фуджі"]), ("Регулятор росту", ["Контроль", "Регаліс 1,0 кг/га"]), ("Строк обробки", ["ВВСН 69", "ВВСН 71"])]
sch = area_scheme(FACT, 2); ROLLS = [Q.roll_key(w, h) for w, h in Q.ROLL_SIZES]

print("== 1. Рулонні розміри")
check(len(ROLLS) == 11 and all(Q.is_roll(k) and k in Q.LABEL_PRESETS for k in ROLLS) and not any(Q.is_roll(k) for k in ("S", "M", "L")), "11 типових рулонних розмірів зареєстровано; аркушеві – не рулонні")
check(Q.LABEL_PRESETS["R58x40"]["name"] == "Рулон 58×40 мм (принтер етикеток)" and Q.LABEL_PRESETS["R58x40"]["w"] == 58 and Q.LABEL_PRESETS["R58x40"]["h"] == 40, "назва й розмір 58×40")
check(Q.parse_roll_key("R58x40") == (58.0, 40.0) and Q.parse_roll_key("R57.5x33") == (57.5, 33.0) and Q.parse_roll_key("M") is None and Q.parse_roll_key(None) is None, "розбір ключа рулону")
k1 = Q.register_roll(57.5, 33); k2 = Q.register_roll("57.5", "33"); check(k1 == k2 == "R57.5x33" and Q.LABEL_PRESETS[k1]["name"] == "Рулон 57,5×33 мм (принтер етикеток)", "власний розмір: реєстрація ідемпотентна, кома в назві")
for w, h, frag in ((10, 30, "Ширина"), (130, 40, "Ширина"), (58, 5, "Висота"), (58, 400, "Висота")):
    try: Q.register_roll(w, h); check(False, "мало впасти")
    except ValueError as e: check(frag in str(e), f"{w}×{h} мм відхилено: «{e}»")
check({k: Q.LABEL_PRESETS[k]["layout"] for k in ("R58x40", "R100x70", "R100x100", "R100x150")} == {"R58x40": "h", "R100x70": "h", "R100x100": "v", "R100x150": "v"}, "компонування за пропорціями: широкі – горизонтальне, квадратні й видовжені – вертикальне")

print("\n== 2. Геометрія й сітка точок принтера")
data = Q.build_experiment(sch, "K7M2", "Яблуня – регулятор росту", "ряд 1, місце 1")
for key in ROLLS + [k1]:
    P = Q.LABEL_PRESETS[key]; Q.fill_payloads(data, "descriptive", "m", key); pl = data["plots"][0]; mat, ver = Q.qr_matrix(pl["payload"], "m")
    for dpi in (203, 300):
        prims = Q.label_prims(data, pl, key, mat, {"mono": True, "snap_dpi": dpi}); q = [p for p in prims if p[0] == "qr"][0]; dot = 25.4 / dpi; n = len(mat) + 8; mod = q[3] / n
        ok_grid = abs(mod / dot - round(mod / dot)) < 1e-6 and round(mod / dot) >= 2 and abs(q[1] / dot - round(q[1] / dot)) < 1e-6 and abs(q[2] / dot - round(q[2] / dot)) < 1e-6
        inside = q[1] >= 0 and q[2] >= 0 and q[1] + q[3] <= P["w"] + 1e-6 and q[2] + q[3] <= P["h"] + 1e-6
        tb = [Q.text_bbox(p) for p in prims if p[0] == "text"]; txt_in = all(b[0] >= -0.3 and b[2] <= P["w"] + 0.3 and b[1] >= -0.3 and b[3] <= P["h"] + 0.3 for b in tb)
        if dpi == 203: check(ok_grid and inside and txt_in and round(mod / dot) >= 3, f"{P['name'][6:-21]:>9}: QR v{ver}, модуль {round(mod / dot)} точок ({mod:.3f} мм) на сітці 203 dpi; QR і текст у межах етикетки")
        else: assert ok_grid and inside, (key, dpi)
check(True, "для 300 dpi QR так само на сітці точок для всіх розмірів")
q0 = [p for p in Q.label_prims(data, data["plots"][0], "S", Q.qr_matrix(data["plots"][0]["payload"])[0]) if p[0] == "qr"][0]; check(abs(q0[3] - 27.0) < 1e-9, "аркушеві таблички не змінились (QR 27 мм на малій табличці)")
check(abs(Q.module_mm("S", 5) - 27.0 / 45) < 1e-12 and Q.version_cap("S") == 10, "розмір модуля й межа версії для аркушевих табличок – як раніше")

print("\n== 3. PDF для принтера етикеток і розпізнавання QR при 203 dpi")
def decode_page(page, dpi, blur=0.0, rot=0.0):
    pix = page.get_pixmap(dpi=dpi); img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    if rot: img = img.rotate(rot, expand=True, fillcolor=255)
    if blur: img = img.filter(ImageFilter.GaussianBlur(blur))
    r = zxingcpp.read_barcodes(img); return [x.text for x in r]
tot = ok = 0
for key in ROLLS:
    P = Q.LABEL_PRESETS[key]; Q.fill_payloads(data, "descriptive", "m", key); pth = os.path.join(TMP, f"{key}.pdf"); n = Q.render_labels_pdf(pth, data, key, {"mono": True, "printer_dpi": 203})
    doc = pymupdf.open(pth); sizes = {(round(p.rect.width / 72 * 25.4, 2), round(p.rect.height / 72 * 25.4, 2)) for p in doc}
    good = sum(1 for i, pg in enumerate(doc) if decode_page(pg, 203) == [data["plots"][i]["payload"]]); tot += len(doc); ok += good
    rough = sum(1 for i, pg in enumerate(doc[:6]) if decode_page(pg, 203, blur=0.7, rot=3.0) == [data["plots"][i]["payload"]])
    check(n == len(data["plots"]) == len(doc) and sizes == {(float(P["w"]), float(P["h"]))} and good == len(doc) and rough == 6, f"{P['name'][6:-21]:>9}: {len(doc)} сторінок точно {P['w']:g}×{P['h']:g} мм; QR розпізнано {good}/{len(doc)} при 203 dpi, 6/6 із розмиттям і поворотом 3°" if rough == 6 else f"{key}: розмиття → {rough}/6")
check(ok == tot, f"усього розпізнано {ok} із {tot} етикеток (усі 11 розмірів)")
doc = pymupdf.open(os.path.join(TMP, "R58x40.pdf")); arr = np.asarray(Image.open(io.BytesIO(doc[0].get_pixmap(dpi=203).tobytes("png"))).convert("RGB")).astype(int)
check(int(np.max(np.abs(arr[..., 0] - arr[..., 1]) + np.abs(arr[..., 1] - arr[..., 2]))) <= 12, "чорно-білий режим: на етикетці немає кольорових пікселів")
gray = np.mean((arr[..., 0] > 60) & (arr[..., 0] < 195)); check(gray < 0.06, f"майже немає сірих зон (лише згладжування країв): {gray:.1%}")
check(arr[-2, 1].tolist() == [255, 255, 255] and arr[-2, -2].tolist() == [255, 255, 255] and arr[arr.shape[0] // 2, -2].tolist() == [255, 255, 255], "без рамки навколо етикетки (нижні кути й правий край білі; межі задає носій)")
Q.fill_payloads(data, "descriptive", "m", "R58x40"); pc = os.path.join(TMP, "col.pdf"); Q.render_labels_pdf(pc, data, "R58x40", {"mono": False}); a2 = np.asarray(Image.open(io.BytesIO(pymupdf.open(pc)[0].get_pixmap(dpi=100).tobytes("png"))).convert("RGB")).astype(int)
check(int(np.max(np.abs(a2[..., 0] - a2[..., 2]))) > 60, "без чорно-білого режиму кольорова смуга варіанта зберігається")
Q.fill_payloads(data, "descriptive", "m", "R58x40"); p3 = os.path.join(TMP, "300.pdf"); Q.render_labels_pdf(p3, data, "R58x40", {"mono": True, "printer_dpi": 300}); d3 = pymupdf.open(p3)
check(all(decode_page(pg, 300) == [data["plots"][i]["payload"]] for i, pg in enumerate(d3)), "для принтера 300 dpi: усі QR розпізнаються при 300 dpi")
big = Q.build_experiment(area_scheme(FACT, 4), "B7K2"); Q.fill_payloads(big, "descriptive", "m", "R40x30"); pb = os.path.join(TMP, "small.pdf"); Q.render_labels_pdf(pb, big, "R40x30", {"mono": True})
db = pymupdf.open(pb); check(len(db) == 48 and all(decode_page(pg, 203) == [big["plots"][i]["payload"]] for i, pg in enumerate(db)), "найменша етикетка 40×30: 48 ділянок, усі QR розпізнано при 203 dpi")
sm = Q.summary(big, "R40x30", "m", "descriptive"); check(sm["module"] >= 0.375 - 1e-9, f"40×30: модуль {sm['module']:.3f} мм (≥ 3 точки при 203 dpi)")

print("\n== 4. PNG у роздільності принтера")
Q.fill_payloads(data, "descriptive", "m", "R58x40"); img = Q.render_label_png(data, data["plots"][3], "R58x40", {"mono": True}, dpi=203)
check(img.size == (round(58 / 25.4 * 203), round(40 / 25.4 * 203)) and img.mode == "1", f"PNG 58×40 при 203 dpi: {img.size[0]}×{img.size[1]} пікселів, одноколірний (1 біт)")
check([x.text for x in zxingcpp.read_barcodes(img.convert("L"))] == [data["plots"][3]["payload"]], "QR на PNG розпізнається")
fs = Q.save_png_labels(os.path.join(TMP, "png"), data, "R58x40", {"mono": True}, 203); im0 = Image.open(fs[0]); check(len(fs) == len(data["plots"]) and im0.info.get("dpi", (0, 0))[0] in (203, 202.9998, 203.0) or round(im0.info.get("dpi", (0, 0))[0]) == 203, f"PNG усіх етикеток із позначкою 203 dpi ({len(fs)} файлів)")
fa = Q.save_all(os.path.join(TMP, "all"), data, "R58x40", {"mono": True, "printer_dpi": 203}, 203); check(any(f.endswith("_таблички.pdf") for f in fa) and pymupdf.open([f for f in fa if f.endswith("_таблички.pdf")][0]).page_count == len(data["plots"]), "«Зберегти все»: PDF етикеток по одній на сторінці")

print("\n== 5. Аркушеві таблички без змін")
Q.fill_payloads(data, "descriptive", "m", "S"); ps = os.path.join(TMP, "S.pdf"); pages = Q.render_labels_pdf(ps, data, "S", {"cut_lines": True}); dS = pymupdf.open(ps)
check(pages == 2 and len(dS) == 2 and round(dS[0].rect.width / 72 * 25.4) == 210 and round(dS[0].rect.height / 72 * 25.4) == 297, "мала табличка: аркуші A4, 21 на аркуші (24 ділянки → 2 аркуші)")
check(sum(1 for t_ in dS[0].get_text().split("\n") if "ДОСЛІД K7M2" in t_) == 21, "на першому аркуші 21 табличка")

if os.environ.get("DISPLAY"):
    print("\n== 6. Діалог")
    import tkinter as tk
    from tkinter import messagebox, filedialog
    import sad_qr_dialog as D
    LOG = {"warn": [], "info": []}; D.messagebox.showwarning = lambda t="", m="", **k: LOG["warn"].append(m); D.messagebox.showinfo = lambda t="", m="", **k: LOG["info"].append(m)
    root = tk.Tk(); root.withdraw(); got = {}
    dlg = D.QRLabelsDialog(root, sch, {}, lambda s_: got.update(s_)); root.update(); dlg._rebuild(); root.update()
    vals = list(dlg.cb_preset.cget("values")); check(vals[:3] == [Q.LABEL_PRESETS[k]["name"] for k in ("S", "M", "L")] and "Рулон 58×40 мм (принтер етикеток)" in vals and vals[-1] == D.CUSTOM_ROLL and "Рулон 57,5×33 мм (принтер етикеток)" not in vals, "у списку: аркушеві, 11 рулонних і «свій розмір» (зареєстровані власні не захаращують список)")
    check(dlg.roll.winfo_manager() == "" and dlg.cb_cut.winfo_manager() == "grid", "для аркушевих табличок рулонних параметрів не видно")
    dlg.v_preset.set("Рулон 58×40 мм (принтер етикеток)"); root.update(); dlg._rebuild(); root.update()
    check(dlg.key == "R58x40" and dlg.is_roll and dlg.roll.winfo_manager() == "grid" and dlg.cb_cut.winfo_manager() == "" and dlg.roll_custom.winfo_manager() == "", "рулон: показано параметри принтера, сховано лінії різання й поля власного розміру")
    check("58×40 мм" in dlg.roll_hint.cget("text") and "100 %" in dlg.roll_hint.cget("text") and "проміжок" in dlg.roll_hint.cget("text"), "підказка: розмір етикетки, проміжок, масштаб 100 %")
    o = dlg.opts(); check(o["mono"] is True and o["printer_dpi"] == 203 and o["cut_lines"] is False, f"параметри друку: {o}")
    pp = os.path.join(TMP, "dlg.pdf"); D.filedialog.asksaveasfilename = lambda **k: pp; done = []; dlg._done = lambda m, p: done.append(m); dlg.save_labels_pdf()
    check(pymupdf.open(pp).page_count == len(dlg.data["plots"]) and "PDF етикеток" in done[-1] and "по одній на сторінці" in done[-1], f"«Таблички: PDF» для рулону: {done[-1]}")
    dd_ = os.path.join(TMP, "dlgpng"); os.makedirs(dd_); D.filedialog.askdirectory = lambda **k: dd_; dlg.save_png(); f0 = sorted(os.listdir(os.path.join(dd_, os.listdir(dd_)[0])))[0]
    check(Image.open(os.path.join(dd_, os.listdir(dd_)[0], f0)).size == (round(58 / 25.4 * 203), round(40 / 25.4 * 203)), "PNG із діалогу – у роздільності принтера 203 dpi")
    dlg.v_preset.set(D.CUSTOM_ROLL); root.update(); check(dlg.roll_custom.winfo_manager() == "pack", "«свій розмір» показує поля ширини й висоти")
    dlg.v_rw.set("57"); dlg.v_rh.set("33"); check(dlg._apply_custom() and dlg.key == "R57x33" and "57×33 мм" in dlg.roll_hint.cget("text"), "власний розмір 57×33 застосовано")
    dlg.v_rw.set("150"); n_w = len(LOG["warn"]); check(dlg._apply_custom() is False and len(LOG["warn"]) == n_w + 1 and "Ширина" in LOG["warn"][-1] and dlg.key == "R57x33", "ширина 150 мм відхилена, попередній розмір лишається")
    dlg.v_rw.set("115"); dlg.v_rh.set("50"); dlg._apply_custom(); check("ширину друку" in dlg.roll_hint.cget("text") and "108" in dlg.roll_hint.cget("text"), "115 мм: попередження про ширину друку 108 мм")
    dlg.v_rw.set("40"); dlg.v_rh.set("25"); dlg._apply_custom(); check("Етикетка мала" in dlg.roll_hint.cget("text"), "мала етикетка: попередження про дрібний текст")
    dlg.v_dpi.set([k for k, v in D.DPIS.items() if v == 300][0]); dlg.v_mono.set(False); dlg._push(); root.update()
    check(got.get("preset") == "R40x25" and got.get("printer_dpi") == 300 and got.get("mono") is False, f"налаштування для файла схеми: {got.get('preset')}, {got.get('printer_dpi')} dpi, mono={got.get('mono')}")
    dlg.win.destroy(); Q.LABEL_PRESETS.pop("R40x25", None)
    dlg2 = D.QRLabelsDialog(root, sch, dict(got), lambda s_: None); root.update()
    check(dlg2.v_preset.get() == D.CUSTOM_ROLL and dlg2.key == "R40x25" and dlg2.v_rw.get() == "40" and dlg2.v_rh.get() == "25" and dlg2.opts()["printer_dpi"] == 300, "повторне відкриття схеми: власний розмір, 300 dpi відновлено")
    dlg2.win.destroy(); dlg3 = D.QRLabelsDialog(root, sch, {"preset": "R58x40"}, lambda s_: None); root.update(); check(dlg3.v_preset.get() == "Рулон 58×40 мм (принтер етикеток)" and dlg3.is_roll, "збережений типовий рулонний розмір відкривається як є"); dlg3.win.destroy()
    dlg4 = D.QRLabelsDialog(root, sch, {"preset": "Rxx"}, lambda s_: None); root.update(); check(dlg4.key == "M", "пошкоджений ключ розміру → середня табличка"); dlg4.win.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ РУЛОННИХ ЕТИКЕТОК ПРОЙДЕНО")
