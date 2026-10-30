# test_sad_scheme_gui.py – конструктор схеми досліду: послідовність кроків для обох моделей (потрібен дисплей; Xvfb)
import os, sys, json, tempfile, shutil
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import tkinter as tk
from tkinter import ttk
import sad_scheme_constructor as SC
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
LOG = {"warn": [], "info": [], "ask": []}; ASK = {"ans": True}
SC.messagebox.showwarning = lambda t="", m="", **k: LOG["warn"].append((t, m))
SC.messagebox.showinfo = lambda t="", m="", **k: LOG["info"].append((t, m))
SC.messagebox.askyesno = lambda t="", m="", **k: (LOG["ask"].append((t, m)), ASK["ans"])[1]
TMP = tempfile.mkdtemp(prefix="sad_scheme_")
SAVE = {"path": None}
SC.filedialog.asksaveasfilename = lambda **k: SAVE["path"]
SC.filedialog.askopenfilename = lambda **k: SAVE["path"]
root = tk.Tk(); root.withdraw()
def all_w(x):
    out = [x]
    for c in x.winfo_children(): out += all_w(c)
    return out
def bstates(frame): return {c.cget("text"): str(c.cget("state")) for c in all_w(frame) if c.winfo_class() == "Button"}
def btn(frame, sub):
    r = [c for c in all_w(frame) if c.winfo_class() == "Button" and sub in c.cget("text")]; return r[0] if r else None
def set_entry(e, text): e.delete(0, "end"); e.insert(0, text); root.update()
def dialogs(win): return [c for c in win.win.winfo_children() if isinstance(c, tk.Toplevel)]
def fill_factors(win, factors, reps=None, plot=None):
    win._edit_factors(); root.update(); dlg = dialogs(win)[-1]
    spins = [x for x in all_w(dlg) if x.winfo_class() == "Spinbox"]
    set_entry(spins[0], str(len(factors)))
    if reps is not None and len(spins) > 1: set_entry(spins[1], str(reps))
    if plot is not None and len(spins) > 2: set_entry(spins[2], str(plot))
    frames = [f for f in all_w(dlg) if f.winfo_class() == "Labelframe" and f.cget("text").startswith("Фактор ")]
    for f, (nm, lv) in zip(frames, factors):
        es = [c for c in f.winfo_children() if c.winfo_class() == "Entry"]; set_entry(es[0], nm); set_entry(es[1], lv)
    btn(dlg, "Зберегти").invoke(); root.update()
    return dlg
def step3_open(win): return bstates(win._step3_area_content)["▶ Сформувати план"] == "normal"
FACT = [("Сорт", "A, B, C"), ("Добриво", "0, N60")]

print("== 0. Відмінювання")
for n, forms in ((1, 0), (2, 1), (4, 1), (5, 2), (11, 2), (12, 2), (14, 2), (21, 0), (22, 1), (25, 2), (101, 0), (111, 2)):
    check(SC._pl(n, "а", "б", "в") == "авб"[0] if forms == 0 else SC._pl(n, "а", "б", "в") == ("б" if forms == 1 else "в"), f"{n} → {SC._pl(n, 'ділянка', 'ділянки', 'ділянок')}")

print("\n== 1. Початковий стан: кроки 2–4 заблоковані")
w = SC.SchemeConstructorWindow(root, {}); root.update()
check(all(("спочатку" in f.cget("text")) for f in (w._step2_frame, w._step3_frame, w._step4_frame)), "заголовки кроків 2–4 просять спершу виконати попередні")
check(bstates(w._step3_area_content)["▶ Сформувати план"] == "disabled" and bstates(w._step4_frame)["💾 Зберегти схему"] == "disabled", "кнопки кроків 3 і 4 вимкнені")
w._model_var.set("area"); w._on_model_change(); root.update()
check(len(LOG["ask"]) == 0, "перемикання моделі без заданих факторів не питає підтвердження")

print("\n== 2. Площинна модель: фактори → Крок 2 → Крок 3")
w._edit_factors(); root.update(); d0 = dialogs(w)[-1]
check(any("задається на Кроці 2" in c.cget("text") for c in all_w(d0) if c.winfo_class() == "Label"), "діалог факторів каже, що повторності задаються на Кроці 2")
d0.destroy()
fill_factors(w, FACT)
check(len(w.factor_defs) == 2 and w._step2_frame.cget("text") == "Крок 2 — Розміри", "Крок 1 завершено, Крок 2 відкрито")
st = w._area_size_status.cget("text")
check(step3_open(w) and w._step3_frame.cget("text") == "Крок 3 — Заповнення", "ключове: Крок 3 відкрито одразу, коли введення коректне (типові значення)")
check("6 комбінацій × 3 повторності = 18 ділянок" in st and "5.00×10.00 м = 50.0 м²" in st and "облікова 36.0 м²" in st and "≈ 1044 м²" in st and "Крок 3 доступний" in st, f"підсумок Кроку 2 за ручним розрахунком (1044 м²): «{st[:110]}…»")
check(w._area_size_status.cget("fg") == "#1a6b1a", "підсумок зеленим кольором")
combos = [c for c in all_w(w._step3_area_content) if c.winfo_class() == "TCombobox"]
check(combos and all(str(c.cget("state")) == "readonly" for c in combos), "списки в Кроці 3 лишаються «лише вибір» (раніше розблокування робило їх вільно редагованими)")
check(all(str(c.cget("state")) == "normal" for c in all_w(w._step3_area_content) if c.winfo_class() == "Entry"), "поле seed активне")
check(bstates(w._step4_frame)["💾 Зберегти схему"] == "disabled" and "спочатку" in w._step4_frame.cget("text"), "Крок 4 лишається заблокованим, доки не сформовано план")

print("\n== 3. Введення кількості повторностей (сценарій зі скарги)")
ent_reps = [c for c in all_w(w._step2_area_content) if c.winfo_class() == "Entry"][0]
set_entry(ent_reps, "4")
check(step3_open(w) and "6 комбінацій × 4 повторності = 24 ділянки" in w._area_size_status.cget("text"), "після введення «4» Крок 3 доступний, підсумок: 24 ділянки")
set_entry(ent_reps, "5"); check("5 повторностей = 30 ділянок" in w._area_size_status.cget("text"), "«5 повторностей = 30 ділянок» (правильне відмінювання)")
for bad, frag in (("", "ціле число"), ("abc", "ціле число"), ("2.5", "ціле число"), ("1", "від 2 до 50"), ("0", "від 2 до 50"), ("51", "від 2 до 50"), ("-3", "від 2 до 50")):
    set_entry(ent_reps, bad)
    check(not step3_open(w) and w._area_size_status.cget("text").startswith("⚠") and frag in w._area_size_status.cget("text") and w._area_size_status.cget("fg") == "#c62828",
          f"повторності «{bad}» → Крок 3 заблоковано, причина: «{w._area_size_status.cget('text')[2:50]}…»")
check("виправте розміри" in w._step3_frame.cget("text"), "заголовок Кроку 3 підказує, що виправляти")
set_entry(ent_reps, "2"); check(step3_open(w), "мінімальне допустиме значення 2 – Крок 3 знову відкрито")
set_entry(ent_reps, "50"); check(step3_open(w) and "300 ділянок" in w._area_size_status.cget("text"), "максимальне допустиме значення 50 – 300 ділянок")
set_entry(ent_reps, "4")

print("\n== 4. Розміри ділянки, смуги, площа, дизайни")
pw_e = [c for c in all_w(w._area_wh_frame) if c.winfo_class() == "Entry"]
set_entry(pw_e[0], "5,5"); check(step3_open(w) and "5.50×10.00 м" in w._area_size_status.cget("text"), "десяткова кома у розмірах приймається («5,5»)")
set_entry(pw_e[0], "0"); check(not step3_open(w) and "додатні числа" in w._area_size_status.cget("text"), "нульова ширина → блокування з поясненням")
set_entry(pw_e[0], "abc"); check(not step3_open(w), "нечислова ширина → блокування"); set_entry(pw_e[0], "5")
border_e = [c for c in all_w(w._step2_area_content) if c.winfo_class() == "Entry"]
w._av["border"].set("3"); check(not step3_open(w) and "завелика" in w._area_size_status.cget("text"), "захисна смуга 3 м на ділянці 5×10 → «завелика», Крок 3 заблоковано")
w._av["border"].set("-1"); check(not step3_open(w) and "не менші за нуль" in w._area_size_status.cget("text") or "від'ємними" in w._area_size_status.cget("text"), "від'ємна смуга → блокування"); w._av["border"].set("0.5")
w._av["buffer"].set("-2"); check(not step3_open(w), "від'ємний буфер → блокування"); w._av["buffer"].set("0.5")
w._av["avail_area"].set("500"); t = w._area_avail_status.cget("text")
check(step3_open(w) and "⚠ Площі не вистачає: потрібно ≈ 1392 м², доступно 500 м² (бракує 892 м²)" in t and w._area_avail_status.cget("fg") == "#c62828", "площі не вистачає → окреме червоне попередження, Крок 3 лишається доступним")
check(w._area_size_status.cget("fg") == "#1a6b1a" and "Крок 3 доступний" in w._area_size_status.cget("text"), "а підсумок розмірів лишається зеленим (нестача площі не означає, що крок заблоковано)")
w._av["avail_area"].set("5000"); check("✓ Доступної площі достатньо (запас" in w._area_avail_status.cget("text") and w._area_avail_status.cget("fg") == "#1a6b1a", "площі достатньо → зелений рядок із запасом")
w._av["avail_area"].set(""); check(w._area_avail_status.cget("text") == "", "поле площі порожнє → рядка про площу немає")
w._av["avail_area"].set("500"); set_entry(ent_reps, "x"); check(w._area_avail_status.cget("text") == "" and not step3_open(w), "при некоректному введенні рядок про площу прибрано")
set_entry(ent_reps, "4"); w._av["avail_area"].set("")
w._av["reps"].set("3"); w._area_size_mode_var.set("rep_area"); w._on_area_size_mode(); root.update()
check(step3_open(w) and "2.00×1.25 м" in w._area_size_status.cget("text"), "режим «площею повторності»: 15 м², ширина 2 м, 6 комбінацій → ділянка 2.00×1.25 м")
w._av["rep_area"].set("6"); check(not step3_open(w) and "завелика" in w._area_size_status.cget("text"), "замала площа повторності → смуга завелика, блокування")
w._av["rep_area"].set("15"); w._area_size_mode_var.set("wh"); w._on_area_size_mode(); root.update(); check(step3_open(w), "повернення до «шириною і довжиною» – Крок 3 відкрито")
w._area_design_disp.set("Латинський квадрат"); root.update()
check(step3_open(w) and "латинський квадрат 6×6 = 36 ділянок" in w._area_size_status.cget("text"), "латинський квадрат: 6×6 = 36 ділянок")
w._av["reps"].set("abc"); check(step3_open(w), "для латинського квадрата поле повторностей не потрібне й не блокує")
w._av["reps"].set("3")
saved_defs = w.factor_defs; w.factor_defs = [{"name": "Сорт", "levels": list("ABC")}, {"name": "Х", "levels": list("abc")}]; w._on_area_inputs_changed()
check(not step3_open(w) and "максимум 8" in w._area_size_status.cget("text"), "латинський квадрат із 9 комбінацій → блокування «максимум 8»")
w.factor_defs = saved_defs; w._area_design_disp.set("RCBD (рекомендується)"); root.update(); check(step3_open(w), "повернення до RCBD – Крок 3 відкрито")

print("\n== 5. Формування плану; зміна параметрів робить план застарілим")
set_entry(ent_reps, "4")
btn(w._step3_area_content, "Сформувати план").invoke(); root.update()
check(w._area_plan is not None and len(w._area_plan["plan"]) == 24 and bstates(w._step4_frame)["💾 Зберегти схему"] == "normal", "план сформовано: 24 ділянки, Крок 4 відкрито")
check("Сформовано" in w._area_plan_status_lbl.cget("text") and "24 ділянок" in w._area_plan_status_lbl.cget("text") or "24" in w._area_plan_status_lbl.cget("text"), "статус плану показано")
set_entry(ent_reps, "5")
check(w._area_plan is None and bstates(w._step4_frame)["💾 Зберегти схему"] == "disabled" and "змінено" in w._area_plan_status_lbl.cget("text") and step3_open(w), "зміна повторностей після плану → план застарів, Крок 4 заблоковано, Крок 3 доступний")
btn(w._step3_area_content, "Сформувати план").invoke(); root.update(); check(len(w._area_plan["plan"]) == 30, "новий план: 30 ділянок")
w._av_seed.set("7"); check(w._area_plan is None, "зміна seed теж робить план застарілим")
btn(w._step3_area_content, "Сформувати план").invoke(); w._area_design_disp.set("CRD"); root.update(); check(w._area_plan is None and bstates(w._step4_frame)["💾 Зберегти схему"] == "disabled", "зміна способу рандомізації теж")
w._area_design_disp.set("RCBD (рекомендується)"); w._av_seed.set("2024")
n_w = len(LOG["warn"]); set_entry(ent_reps, "1"); w._generate_area_plan()
check(len(LOG["warn"]) == n_w + 1 and "від 2 до 50" in LOG["warn"][-1][1] and w._area_plan is None, "формування плану з некоректними повторностями → пояснення, плану немає")
set_entry(ent_reps, "5"); btn(w._step3_area_content, "Сформувати план").invoke(); root.update()
check(len(w._area_plan["plan"]) == 30 and {p["rep"] for p in w._area_plan["plan"]} == {1, 2, 3, 4, 5}, "після виправлення план будується: 30 ділянок у 5 повторностях")

print("\n== 6. Збереження й відкриття збереженої схеми")
SAVE["path"] = os.path.join(TMP, "area_scheme.json"); w._save_scheme(); root.update()
check(os.path.exists(SAVE["path"]) and len(json.load(open(SAVE["path"], encoding="utf-8"))["plants"]) == 30, "схему збережено: 30 ділянок")
w2 = SC.SchemeConstructorWindow(root, {}); root.update(); w2._load_scheme(); root.update()
check(w2._model_var.get() == "area" and w2._area_plan is not None and len(w2._area_plan["plan"]) == 30 and w2._av["reps"].get() == "5", "відкрито: площинна модель, 30 ділянок, повторностей 5")
check(bstates(w2._step4_frame)["💾 Зберегти схему"] == "normal" and step3_open(w2), "після відкриття доступні Крок 3 (можна сформувати план ще раз) і Крок 4 (можна зберегти)")
check("Параметри змінено" not in w2._area_plan_status_lbl.cget("text") and "Відкрито" in w2._area_plan_status_lbl.cget("text"), "відновлений план не позначено застарілим")
set_entry([c for c in all_w(w2._step2_area_content) if c.winfo_class() == "Entry"][0], "6"); check(w2._area_plan is None and step3_open(w2), "після відкриття повторності можна змінити: план застарілий, можна формувати знову")
w2.win.destroy()

print("\n== 7. Скидання при зміні моделі")
ASK["ans"] = False; n_a = len(LOG["ask"]); w._model_var.set("plant"); w._on_model_change(); root.update()
check(len(LOG["ask"]) == n_a + 1 and w._model_var.get() == "area" and len(w.factor_defs) == 2, "відмова від зміни моделі повертає попередній вибір, фактори збережено")
ASK["ans"] = True; w._model_var.set("plant"); w._on_model_change(); root.update()
check(w.factor_defs == [] and not w._step2_open and w._area_size_status.cget("text") == "" and w._area_avail_status.cget("text") == "" and "спочатку" in w._step2_frame.cget("text"), "підтвердження: фактори скинуто, кроки заблоковано, підсумок розмірів очищено")
w._av["reps"].set("7"); check(w._area_size_status.cget("text") == "" and "спочатку" in w._step3_frame.cget("text"), "у моделі «за рослинами» зміна площинних полів нічого не розблоковує")
w._model_var.set("area"); w._on_model_change(); fill_factors(w, FACT); check(step3_open(w), "повторний прохід у площинній моделі: Крок 3 відкрито знову")
w.win.destroy()

print("\n== 8. Модель «за рослинами»: Крок 1 → Крок 2 → Крок 3")
wp = SC.SchemeConstructorWindow(root, {}); root.update()
fill_factors(wp, FACT, reps=3, plot=2)
check("× 3 повт." in wp._factors_status.cget("text") and wp._step2_frame.cget("text") == "Крок 2 — Розміри", "повторності задано в діалозі факторів; Крок 2 відкрито")
check("спочатку" in wp._step3_frame.cget("text") and bstates(wp._step3_plant_content)["➡ Заповнити комбінації факторів"] == "disabled", "Крок 3 ще заблоковано (потрібна таблиця)")
wp._n_rows_setup_var.set("2"); btn(wp._step2_plant_content, "Задати довжину").invoke(); root.update()
for e in wp._rowlen_entries: set_entry(e, "6")
btn(wp._step2_plant_content, "Побудувати таблицю").invoke(); root.update()
check(wp._table_built and bstates(wp._step3_plant_content)["➡ Заповнити комбінації факторів"] == "normal" and wp._step3_frame.cget("text") == "Крок 3 — Заповнення таблиці", "після побудови таблиці Крок 3 відкрито")
check(len(wp.entries) == 2 and all(len(r) == 6 for r in wp.entries), "таблиця 2 ряди × 6 позицій")

print("\n== 8б. Повторність для введених кодів враховує кількість рослин на варіант")
wr = SC.SchemeConstructorWindow(root, {}); root.update(); fill_factors(wr, [("Сорт", "Голден, Гала"), ("Підщепа", "М9, М26")], reps=2, plot=1)
wr._n_rows_setup_var.set("1"); btn(wr._step2_plant_content, "Задати довжину").invoke(); root.update(); set_entry(wr._rowlen_entries[0], "8"); btn(wr._step2_plant_content, "Побудувати таблицю").invoke(); root.update()
for j, code in enumerate(["A1B1", "A1B2", "A2B1", "A2B2", "A1B2", "A1B1", "A2B2", "A2B1"]): set_entry(wr.entries[0][j], code)
rmap = wr._infer_replications(); check([rmap[(1, j)] for j in range(1, 9)] == [1, 1, 1, 1, 2, 2, 2, 2], "1 рослина на варіант (як раніше): кожні 4 клітинки – нова повторність")
wr.plot_size = 2; rmap = wr._infer_replications(); check([rmap[(1, j)] for j in range(1, 9)] == [1] * 8, "2 рослини на варіант: усі 8 клітинок – одна повторність (раніше ділилися на дві)")
wr.plot_size = 4; rmap = wr._infer_replications(); check([rmap[(1, j)] for j in range(1, 9)] == [1] * 8, "неповна повторність (8 з 16 клітинок) лишається однією повторністю")
wr.win.destroy()

print("\n== 9. QR-таблички: кнопка, діалог, файли (площинна модель)")
import sad_qrlabels as QL, sad_qr_dialog as QD
try:
    import zxingcpp; from PIL import Image
except Exception: zxingcpp = None
SC.filedialog.askdirectory = lambda **k: SAVE["dir"]
SAVE["dir"] = None
wq = SC.SchemeConstructorWindow(root, {}); wq._model_var.set("area"); wq._refresh_model_panels(); root.update()
check(bstates(wq._step4_frame)["🏷 QR-таблички для ділянок…"] == "disabled", "до формування плану кнопка QR-табличок вимкнена")
fill_factors(wq, FACT); set_entry([c for c in all_w(wq._step2_area_content) if c.winfo_class() == "Entry"][0], "4")
n_w = len(LOG["warn"]); wq._open_qr_dialog(); check(len(LOG["warn"]) == n_w + 1 and "сформуйте план" in LOG["warn"][-1][1] and not dialogs(wq), "без плану діалог не відкривається – пояснення")
btn(wq._step3_area_content, "Сформувати план").invoke(); root.update()
check(bstates(wq._step4_frame)["🏷 QR-таблички для ділянок…"] == "normal" and bstates(wq._step4_frame)["💾 Зберегти схему"] == "normal", "після плану кнопки «Зберегти» і «QR-таблички» активні")
btn(wq._step4_frame, "QR-таблички").invoke(); root.update(); dq = wq._qr_dialog; dq._rebuild(); root.update()
check(dq.win.winfo_exists() and dq.data is not None and len(dq.data["plots"]) == 24 and dq.data["exp"]["n_variants"] == 6, "діалог відкрито: 24 ділянки, 6 варіантів")
check(dq.v_name.get().startswith("Дослід: Сорт × Добриво") and QL.valid_exp_id(dq.v_id.get()) and dq.v_id.get() == QL.suggest_exp_id(dq.v_name.get(), str(__import__("datetime").date.today().year)), f"назва за замовчуванням із факторів, код запропоновано автоматично: {dq.v_id.get()}")
check(dq.err.cget("text") == "" and all(str(b.cget("state")) == "normal" for b in dq.buttons), "усі кнопки дій активні")
check(dq._photo is not None and dq.lbl_img.cget("image"), "попередній перегляд таблички показано")
dq.win.update()
vis = [(b.cget("text"), b.winfo_ismapped(), b.winfo_rootx(), b.winfo_rooty(), b.winfo_width(), b.winfo_height()) for b in dq.buttons]
check(len(vis) == 8 and all(v[1] and v[4] > 20 and v[5] > 10 for v in vis), f"усі 8 кнопок дій видно на екрані: {[v[0][:18] for v in vis]}")
ovl = [(a[0][:14], b[0][:14]) for i, a in enumerate(vis) for b in vis[i + 1:] if not (a[2] + a[4] <= b[2] or b[2] + b[4] <= a[2] or a[3] + a[5] <= b[3] or b[3] + b[5] <= a[3])]
check(not ovl, f"кнопки не накладаються одна на одну (перекриттів: {len(ovl)} {ovl[:2]})")
want = {"Таблички: PDF", "Розкладка: PDF", "PNG кожної", "Список ділянок", "Маніфест", "Зберегти все", "Друкувати таблички", "Друкувати розкладку"}
check(all(any(w in v[0] for v in vis) for w in want), "є всі дії: PDF табличок, PDF розкладки, PNG, Excel, маніфест, комплект, два друки")
panel_right = max(c.winfo_rootx() + c.winfo_width() for c in all_w(dq.win) if c.winfo_class() == "Labelframe" and c.cget("text") in ("Дослід", "Таблички й QR", "Зберегти і друкувати"))
cbs_ = [c for c in all_w(dq.win) if c.winfo_class() == "TCombobox"]
check(cbs_ and all(c.winfo_rootx() + c.winfo_width() <= panel_right + 1 for c in cbs_), "списки вибору не виходять за межі своєї панелі")
check(all(max(len(v) for v in c.cget("values")) <= int(c.cget("width")) + 6 for c in cbs_ if c.cget("values")), "тексти варіантів у списках вміщуються в поле")
check("Ділянок: 24" in dq.info.cget("text") and "6" in dq.info.cget("text") and "підпис схеми: " + dq.data["exp"]["signature"] in dq.info.cget("text") and "QR: версія" in dq.info.cget("text") and "≈" in dq.info.cget("text"), f"зведення: {dq.info.cget('text').splitlines()[0]}")
sm = QL.summary(dq.data, dq.key, dq.ecc, dq.style); check(f"модуль {sm['module']:.2f} мм" in dq.info.cget("text") and f"≈ {sm['scan_cm']:.0f} см" in dq.info.cget("text") and f"Аркушів A4: {sm['sheets']}" in dq.info.cget("text"), "числа у зведенні збігаються з розрахунком ядра")
check(wq._qr_settings.get("exp_id") == dq.v_id.get() and wq._qr_settings["preset"] == "M", "налаштування одразу передано конструктору (потраплять у файл схеми)")
dq.v_id.set("BAD!"); dq.win.update(); dq._rebuild(); check(dq.data is None and "3–6 символів" in dq.err.cget("text") and all(str(b.cget("state")) == "disabled" for b in dq.buttons), "некоректний код досліду → помилка, усі кнопки дій вимкнено")
dq.v_id.set("k7m2"); dq._rebuild(); check(dq.data is not None and dq.data["exp"]["id"] == "K7M2" and dq.v_id.get() == "K7M2", "малі літери приймаються й у полі одразу стають великими")
dq.v_name.set("Інша назва"); check(dq.v_id.get() == "K7M2", "після ручного введення коду зміна назви його не перезаписує")
dq._suggest(); check(dq.v_id.get() == QL.suggest_exp_id("Інша назва", str(__import__("datetime").date.today().year)), "кнопка «Запропонувати» знову виводить код із назви")
dq.v_id.set("K7M2"); dq.v_origin.set("північно-західний кут поля"); dq.v_name.set("Яблуня-Регаліс-2026"); dq._rebuild()
dq.v_preset.set(QL.LABEL_PRESETS["S"]["name"]); dq._rebuild(); s_info = dq.info.cget("text")
dq.v_preset.set(QL.LABEL_PRESETS["L"]["name"]); dq._rebuild(); l_info = dq.info.cget("text")
check(s_info != l_info and "Аркушів A4: 2" in s_info and "Аркушів A4: 6" in l_info, "розмір таблички змінює зведення: мала 2 аркуші, велика 6")
dq.v_preset.set(QL.LABEL_PRESETS["M"]["name"]); dq.v_style.set(next(k for k, v in QD.STYLES.items() if v == "compact")); dq._rebuild()
check("Компактний QR" in dq.warn.cget("text") and dq.data["plots"][0]["tier"] == "min", "компактний вміст: попередження, що звичайна камера покаже технічний текст")
dq.v_style.set(next(k for k, v in QD.STYLES.items() if v == "descriptive")); dq.v_preset.set(QL.LABEL_PRESETS["S"]["name"]); dq.v_ecc.set(next(k for k, v in QD.ECCS.items() if v == "q")); dq._rebuild()
check("скорочений опис" in dq.warn.cget("text"), "мала табличка зі стійкістю Q: попередження про скорочений опис у QR")
dq.v_ecc.set(next(k for k, v in QD.ECCS.items() if v == "m")); dq.v_preset.set(QL.LABEL_PRESETS["M"]["name"]); dq._rebuild(); dq.v_prev.set("7"); dq._preview(); check(dq._photo is not None, "перегляд іншої ділянки (№7)")
dq.v_prev.set("999"); dq._preview(); dq.v_prev.set("abc"); dq._preview(); check(True, "некоректний номер ділянки для перегляду не ламає вікно")
out = tempfile.mkdtemp(prefix="sad_qrout_")
SAVE["path"] = os.path.join(out, "lab.pdf"); dq.save_labels_pdf(); check(os.path.getsize(SAVE["path"]) > 5000 and "PDF табличок" in LOG["info"][-1][1], "PDF табличок збережено")
SAVE["path"] = os.path.join(out, "lay.pdf"); dq.save_layout_pdf(); check(os.path.getsize(SAVE["path"]) > 5000 and "PDF розкладки" in LOG["info"][-1][1], "PDF розкладки збережено")
SAVE["path"] = os.path.join(out, "l.xlsx"); dq.save_xlsx(); check(os.path.getsize(SAVE["path"]) > 3000, "Excel збережено")
SAVE["path"] = os.path.join(out, "m.json"); dq.save_manifest(); mj = json.load(open(SAVE["path"], encoding="utf-8")); check(mj["experiment"]["id"] == "K7M2" and mj["experiment"]["name"] == "Яблуня-Регаліс-2026" and mj["experiment"]["origin"] == "північно-західний кут поля" and len(mj["plots"]) == 24, "маніфест збережено з назвою й описом початку")
SAVE["dir"] = out; dq.save_png(); pngs = os.listdir(os.path.join(out, "K7M2_png")); check(len(pngs) == 24, f"PNG: 24 файли ({len(pngs)})")
dq.save_everything(); fold = os.path.join(out, "K7M2_QR"); allf = os.listdir(fold); check(len(allf) == 5 and len(os.listdir(os.path.join(fold, "K7M2_png"))) == 24 and "комплект" in LOG["info"][-1][1].lower(), f"«Зберегти все»: у теці {sorted(allf)}")
if zxingcpp:
    got = [zxingcpp.read_barcodes(Image.open(os.path.join(out, "K7M2_png", n)))[0].text for n in sorted(pngs)]
    prs = [QL.parse_payload(g) for g in got]
    check(all(p["valid"] and p["E"] == "K7M2" and p["S"] == dq.data["exp"]["signature"] for p in prs) and sorted(p["P"] for p in prs) == list(range(1, 25)), "QR зі збережених PNG розпізнано: усі 24 ділянки, коди й підпис коректні")
    plan_by_no = {p["plot"]: p for p in dq.data["plots"]}
    check(all(plan_by_no[p["P"]]["rep"] == p["R"] and plan_by_no[p["P"]]["variant"] == p["V"] for p in prs), "повторність і варіант у QR збігаються зі схемою для кожної ділянки")
    check(all("Яблуня-Регаліс-2026" in g and "Повторність" in g for g in got), "звичайна камера покаже читабельний текст (дослід, повторність, варіант)")
calls = []; orig_open = QL.open_for_print; QL.open_for_print = lambda p: calls.append(p)
dq.print_pdf("labels"); dq.print_pdf("layout"); QL.open_for_print = orig_open
check(len(calls) == 2 and calls[0].endswith("K7M2_таблички.pdf") and calls[1].endswith("K7M2_розкладка.pdf") and all(os.path.getsize(c) > 5000 for c in calls), "«Друкувати» створює PDF у тимчасовій теці й відкриває його")
QL.open_for_print = lambda p: (_ for _ in ()).throw(OSError("немає програми")); n_e = len(LOG["warn"]); LOGE = []
SC.messagebox.showerror = lambda t="", m="", **k: LOGE.append((t, m)); dq.print_pdf("labels"); QL.open_for_print = orig_open
check(len(LOGE) == 1 and "немає програми" in LOGE[0][1], "помилка відкриття файла для друку – повідомлення, вікно не падає")
print("\n== 10. QR: налаштування зберігаються у схемі й відновлюються")
dq.v_id.set("K7M2"); dq._rebuild(); dq._push(); SAVE["path"] = os.path.join(out, "scheme.sadp"); wq._save_scheme()
cfg = json.load(open(SAVE["path"], encoding="utf-8"))["cfg"]
check(cfg["qr"]["exp_id"] == "K7M2" and cfg["qr"]["exp_name"] == "Яблуня-Регаліс-2026" and cfg["qr"]["preset"] == "M" and cfg["qr"]["origin"] == "північно-західний кут поля", f"у файлі схеми збережено налаштування QR: {cfg['qr']}")
dq.win.destroy(); wq.win.destroy()
wl = SC.SchemeConstructorWindow(root, {}); wl._load_scheme(); root.update()
check(wl._qr_settings.get("exp_id") == "K7M2" and wl._qr_settings.get("exp_name") == "Яблуня-Регаліс-2026", "після відкриття схеми налаштування QR відновлено")
btn(wl._step4_frame, "QR-таблички").invoke(); root.update(); d2 = wl._qr_dialog; d2._rebuild()
check(d2.v_id.get() == "K7M2" and d2.v_name.get() == "Яблуня-Регаліс-2026" and d2.id_manual and d2.data["exp"]["signature"] == QL.build_experiment(json.load(open(SAVE["path"], encoding="utf-8")), "K7M2")["exp"]["signature"], "повторне відкриття: той самий код досліду й той самий підпис схеми – таблички відтворюються ідентично")
d2.win.destroy(); wl.win.destroy()
# старі файли без налаштувань QR
old = json.load(open(SAVE["path"], encoding="utf-8")); old["cfg"].pop("qr"); json.dump(old, open(SAVE["path"], "w", encoding="utf-8"), ensure_ascii=False)
wo = SC.SchemeConstructorWindow(root, {}); wo._load_scheme(); root.update(); btn(wo._step4_frame, "QR-таблички").invoke(); root.update()
check(wo._qr_dialog.data is not None and QL.valid_exp_id(wo._qr_dialog.v_id.get()), "файл схеми без налаштувань QR відкривається, код пропонується")
wo._qr_dialog.win.destroy(); wo.win.destroy()

print("\n== 11. QR: модель «за рослинами»")
wpq = SC.SchemeConstructorWindow(root, {}); root.update(); fill_factors(wpq, [("Сорт", "Голден, Гала"), ("Підщепа", "М9, М26")], reps=2, plot=3)
wpq._n_rows_setup_var.set("2"); btn(wpq._step2_plant_content, "Задати довжину").invoke(); root.update()
for e in wpq._rowlen_entries: set_entry(e, "14")
btn(wpq._step2_plant_content, "Побудувати таблицю").invoke(); root.update()
n_w = len(LOG["warn"]); wpq._open_qr_dialog(); check(len(LOG["warn"]) == n_w + 1 and not dialogs(wpq), "порожня таблиця (без облікових рослин): діалог не відкривається, пояснення є")
order = [["A1B1"] * 3 + ["A1B2"] * 3 + ["A2B1"] * 3 + ["A2B2"] * 3, ["A2B2"] * 3 + ["A2B1"] * 3 + ["A1B2"] * 3 + ["A1B1"] * 3]
for r, codes in enumerate(order):
    set_entry(wpq.entries[r][0], "К"); set_entry(wpq.entries[r][13], "К")
    for j, code in enumerate(codes): set_entry(wpq.entries[r][1 + j], code) if 1 + j < 13 else None
wpq.entries[0][12].delete(0, "end"); wpq.entries[0][12].insert(0, "A2B2")
rm_ = wpq._infer_replications(); check(wpq.plot_size == 3 and {rm_[(1, j)] for j in range(2, 14)} == {1} and {rm_[(2, j)] for j in range(2, 14)} == {2}, "повторність при 3 рослинах на варіант: усі 12 рослин ряду – одна повторність (а не три)")
btn(wpq._step4_frame, "QR-таблички").invoke(); root.update(); dp2 = wpq._qr_dialog; dp2._rebuild()
check(dp2.data is not None and dp2.data["exp"]["model"] == "plant" and len(dp2.data["plots"]) == 8 and dp2.data["exp"]["n_reps"] == 2, f"модель «за рослинами»: 2 повторності × 4 варіанти = 8 ділянок (груп рослин): {len(dp2.data['plots']) if dp2.data else None}")
pp = dp2.data["plots"][0]; check(pp["units"] == 3 and pp["pos_text"].startswith("ряд 1: рослини 2–4"), f"перша ділянка – група з 3 рослин: «{pp['pos_text']}»")
SAVE["dir"] = out; os.makedirs(os.path.join(out, "plant"), exist_ok=True); SAVE["dir"] = os.path.join(out, "plant"); dp2.save_everything()
check(len(os.listdir(os.path.join(SAVE["dir"], dp2.data["exp"]["id"] + "_QR"))) == 5, "комплект для моделі «за рослинами» збережено")
if zxingcpp:
    pn = sorted(os.listdir(os.path.join(SAVE["dir"], dp2.data["exp"]["id"] + "_QR", dp2.data["exp"]["id"] + "_png"))); gs = [zxingcpp.read_barcodes(Image.open(os.path.join(SAVE["dir"], dp2.data["exp"]["id"] + "_QR", dp2.data["exp"]["id"] + "_png", n)))[0].text for n in pn]
    check(len(gs) == 8 and all(QL.parse_payload(g)["valid"] for g in gs) and "рослини" in gs[0], "QR для груп рослин розпізнано, у тексті вказано рослини ряду")
dp2.win.destroy(); wpq.win.destroy(); shutil.rmtree(out, ignore_errors=True)
wp.win.destroy(); shutil.rmtree(TMP, ignore_errors=True); root.destroy()
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ КОНСТРУКТОРА ПРОЙДЕНО")
