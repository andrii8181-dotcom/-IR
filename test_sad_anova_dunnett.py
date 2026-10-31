# test_sad_anova_dunnett.py – тест Даннетта в основному ANOVA: вибір контролю, розрахунок, звіт, Forest plot, експорт
import os, sys, math, random, time, tempfile, shutil, itertools
sys.path.insert(0, os.environ.get("SAD_SRC", os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DISPLAY", ":99")
import numpy as np
import tkinter as tk
from tkinter import messagebox
import matplotlib; matplotlib.use("Agg")
from scipy import stats
import sad_app as A, sad_report as R
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
msgs = []
for n in ("showinfo", "showwarning", "showerror"): setattr(messagebox, n, lambda t="", m="", _n=n, **k: msgs.append((_n, t, str(m)[:150])))
messagebox.askyesno = lambda *a, **k: True
root = tk.Tk(); root.geometry("200x100+0+0"); TMP = tempfile.mkdtemp(prefix="sad_dun_")
def all_w(x):
    out = [x]
    for c in x.winfo_children(): out += all_w(c)
    return out
SORTS = ["Голден", "Гала", "Фуджі"]; REGS = ["Контроль", "Регаліс"]; REPS = 4
rg = random.Random(11); EFF_S = {"Голден": 0.0, "Гала": 0.6, "Фуджі": 3.0}; EFF_R = {"Контроль": 0.0, "Регаліс": 2.0}; BLK = [0.0, 0.4, -0.3, 0.2]
DATA = {(s, r_): [round(20 + EFF_S[s] + EFF_R[r_] + BLK[b] + rg.gauss(0, 0.7), 3) for b in range(REPS)] for s in SORTS for r_ in REGS}     # як уводиться (3 знаки)
def run_anova(dialog_action=None, choice=None, design="rcbd"):
    app = A.SADTk(root); app.open_table(2); root.update()
    for i, (s, r_) in enumerate((a, b) for a in SORTS for b in REGS):
        row = app.entries[i]; row[0].insert(0, s); row[1].insert(0, r_)
        for c in range(REPS): row[2 + c].insert(0, f"{DATA[(s, r_)][c]:.3f}".replace(".", ","))
    app.ask_params = lambda: {"ok": True, "indicator": "Урожайність", "units": "т/га", "design": design, "split_main": "A", "ss_type": "III"}
    if choice is not None: app.choose_method = lambda *a, **k: choice(app)
    if dialog_action is not None:
        par = app.table_win or app.root; par.wait_window = lambda w, app=app: dialog_action(app, w)
    app.analyze(); root.update(); time.sleep(0.3); root.update(); return app

print("== 1. Діалог вибору методу: Даннетт і контроль")
seen = {}
def dlg_action(app, w):
    rbs = [x for x in all_w(w) if x.winfo_class() == "Radiobutton"]; seen["opts"] = [x.cget("text") for x in rbs]
    cf = [x for x in all_w(w) if x.winfo_class() == "Labelframe" and "Контроль для тесту Даннетта" in str(x.cget("text"))]
    seen["hidden_before"] = bool(cf) and cf[0].winfo_manager() == ""
    [x for x in rbs if "Даннетта" in x.cget("text")][0].invoke(); root.update()
    seen["shown_after"] = bool(cf) and cf[0].winfo_manager() == "pack"
    w.update(); bt_ = [x for x in all_w(w) if x.winfo_class() == "Button" and "Виконати" in x.cget("text")][0]
    seen["visible"] = (cf[0].winfo_ismapped() and cf[0].winfo_height() > 40 and cf[0].winfo_rooty() + cf[0].winfo_height() <= w.winfo_rooty() + w.winfo_height()
                       and cf[0].winfo_rooty() + cf[0].winfo_height() <= bt_.winfo_rooty())
    cbs = [x for x in all_w(cf[0]) if x.winfo_class() == "TCombobox"]; seen["cb_values"] = [list(c.cget("values")) for c in cbs]
    cbs[0].set("Гала"); cbs[1].set("Контроль")
    [x for x in all_w(w) if x.winfo_class() == "Button" and "Виконати" in x.cget("text")][0].invoke()
app = run_anova(dialog_action=dlg_action)
check(any("Даннетта" in o for o in seen.get("opts", [])) and any("Тьюкі" in o for o in seen["opts"]), f"у списку методів поряд із НІР, Тьюкі, Дунканом – Даннетт: {seen.get('opts')}")
check(seen.get("hidden_before") and seen.get("shown_after"), "вибір контролю з'являється лише при виборі Даннетта")
check(seen.get("visible"), "блок вибору контролю справді видимий: над кнопками й у межах вікна (раніше обрізався під кнопками)")
check(seen.get("cb_values", [[]])[0] == SORTS and seen["cb_values"][1] == REGS and len(seen["cb_values"]) == 3, "контроль обирається для кожного фактора (рівні з даних) + тип перевірки")
dn = getattr(app, "_dunnett_res", None); fk = app.factor_keys
check(dn is not None and dn["control"] == {fk[0]: "Гала", fk[1]: "Контроль"} and dn["alternative"] == "two-sided", f"обраний контроль передано в розрахунок: {dn and dn['control']}")

print("\n== 2. Розрахунок: незалежна звірка")
def choice_fn(ctlA, ctlB, alt="two-sided"):
    return lambda app: {"ok": True, "method": "dunnett", "control": {app.factor_keys[0]: ctlA, app.factor_keys[1]: ctlB}, "alternative": alt}
app = run_anova(choice=choice_fn("Голден", "Контроль")); dn = app._dunnett_res; fk = app.factor_keys; rA = dn["factors"][fk[0]]
allv = np.array([[DATA[(s, r_)][b] for s in SORTS for r_ in REGS] for b in range(REPS)])              # блоки × варіанти
mA = {s: np.mean([DATA[(s, r_)] for r_ in REGS]) for s in SORTS}
check(all(abs(row["diff"] - (mA[row["entry"]] - mA["Голден"])) < 1e-9 for row in rA["rows"]) and abs(rA["ctl_mean"] - mA["Голден"]) < 1e-9, "різниці з контролем = різниці середніх, обчислені з даних напряму")
gm = allv.mean(); sst = ((allv - gm) ** 2).sum(); ssb = 6 * ((allv.mean(1) - gm) ** 2).sum(); ssv = REPS * ((allv.mean(0) - gm) ** 2).sum(); mse = (sst - ssb - ssv) / ((6 - 1) * (REPS - 1))
check(all(abs(row["se_diff"] - math.sqrt(2 * mse / (REPS * 2))) < 1e-9 for row in rA["rows"]), f"похибка різниці = √(2·MSE/n) з ручним MSE RCBD ({mse:.4f}), n = 8 на рівень сорту")
check(abs(rA["crit"] - 2.44) < 0.01 and rA["df"] == 15, f"критичне значення {rA['crit']:.3f} = таблиця Даннетта (2 порівняння, df = 15): 2,44")
pt = {row["entry"]: row["p_dunnett"] for row in rA["rows"]}; check(pt["Фуджі"] < 0.001 and pt["Гала"] > 0.05, f"Фуджі (+3) істотно, Гала (+0,6) – ні: p = {pt}")
pv = {row["entry"]: row["p_lsd"] for row in rA["rows"]}; check(all(pt[k] >= pv[k] for k in pt), "p Даннетта ≥ незскоригованого p (поправка на множинність)")
rv = dn["variants"]; check(rv is not None and dn["ctl_variant"] == "Голден | Контроль" and len(rv["rows"]) == 5, "варіанти: контроль – комбінація контрольних рівнів, 5 порівнянь")
check(abs(rv["crit"] - stats.t.ppf(0.975, 15)) > 0.2 and rv["crit"] > rA["crit"], f"для 5 порівнянь критичне значення більше ({rv['crit']:.3f} > {rA['crit']:.3f})")
check(app._dunnett_res["factors"][fk[1]]["rows"][0]["entry"] == "Регаліс" and app._dunnett_res["factors"][fk[1]]["rows"][0]["p_dunnett"] < 0.001, "фактор регулятора: Регаліс істотно відрізняється від контролю")
app1 = run_anova(choice=choice_fn("Голден", "Контроль", "greater")); r1 = app1._dunnett_res["factors"][app1.factor_keys[0]]
check(all(math.isinf(row["ci_hi"]) and row["ci_hi"] > 0 for row in r1["rows"]) and r1["crit"] < rA["crit"], "однобічний «більше контролю»: верхня межа ∞, критичне значення менше")

print("\n== 3. Звіт")
rw = app.report_win; items = R.collect(rw); tx = " ".join(i.get("text", "") for i in items if i["kind"] in ("text", "heading", "caption"))
check("Тест Даннетта (порівняння з контролем)" in tx and "одночасні" in tx, "у звіті – метод і пояснення позначок")
tabs = [i for i in items if i["kind"] == "table"]; dunt = [t for t in tabs if "Різниця з контролем" in t["headers"]]
check(len(dunt) == 3 and all(t["headers"][3] == "% до контролю" and "95 % ДІ" in t["headers"][4] for t in dunt), f"3 таблиці порівнянь із контролем (2 фактори + варіанти): {len(dunt)}")
caps = " ".join(i["text"] for i in items if i["kind"] == "caption"); check("контроль – Голден" in caps and "контроль – Голден | Контроль" in caps, "у назвах таблиць – який рівень є контролем")
tf = next(t for t in dunt if t["headers"][0] != "Варіант"); fr = {r_[0]: r_ for r_ in tf["rows"]}
check(fr["Фуджі"][2].startswith("+") and fr["Фуджі"][6].startswith("істотно більше **") and fr["Гала"][6] == "неістотно", f"рядки: Фуджі «{fr['Фуджі'][6]}», Гала «{fr['Гала'][6]}»")
check(abs(float(fr["Фуджі"][3].replace(",", ".")) - 100 * mA["Фуджі"] / mA["Голден"]) < 0.06, f"% до контролю = 100·середнє/середнє контролю ({fr['Фуджі'][3]})")
cldt = [t for t in tabs if t["headers"][-1] == "Порівняння з контролем"]; mk = {r_[0]: r_[-1] for t in cldt for r_ in t["rows"]}
check(len(cldt) >= 2 and mk.get("Голден") == "К" and mk.get("Фуджі") == "↑**" and mk.get("Гала") == "–", f"колонка позначок замість літер CLD: {mk}")

print("\n== 4. Forest plot")
btns = [b for b in all_w(rw) if b.winfo_class() == "Button" and "Forest" in str(b.cget("text"))]; check(len(btns) == 1, "у графічному звіті є вкладка «🌲 Forest plot»")
fig = app._graph_figs.get("forest"); check(fig is not None and len(fig.axes) == 3, f"Forest plot: 3 панелі (2 фактори + варіанти): {fig and len(fig.axes)}")
ax0 = fig.axes[0]; yt = [t.get_text() for t in ax0.get_yticklabels()]; check(sorted(yt) == ["Гала", "Фуджі"] and "Голден" not in yt, "на панелі – рівні без контролю")
segs = [l for l in ax0.lines if len(l.get_xdata()) == 2 and l.get_ydata()[0] == l.get_ydata()[1] and abs(l.get_xdata()[1] - l.get_xdata()[0]) > 0.5]
ws = sorted(abs(l.get_xdata()[1] - l.get_xdata()[0]) for l in segs); exp_w = 2 * rA["crit"] * rA["rows"][0]["se_diff"]
check(ws and all(abs(w_ - exp_w) < 1e-9 for w_ in ws), f"ширина інтервалу = 2·c·SE = {exp_w:.3f}")
zero = [l for l in ax0.lines if list(l.get_xdata()) == [0, 0]]; check(len(zero) == 1, "вертикальна лінія нуля (немає різниці)")
check(any("%" in t.get_text() for t in ax0.texts) and "Голден" in ax0.get_title(loc="left"), "підписи % до контролю; у заголовку панелі – контроль")
cols = {l.get_color() for l in segs}; check(len(cols) == 2, "істотна й неістотна різниці – різними кольорами")
app._build_forest_tab([w for w in all_w(rw) if w.winfo_class() == "Frame" and any(getattr(c, "_sad_fig", None) is fig for c in all_w(w))][0].master if False else tk.Frame(rw), app.graph_settings, rw)
check(True, "перебудова вкладки Forest plot без помилок")
f1 = app1._graph_figs.get("forest"); check(f1 is not None and len(f1.axes) == 3, "Forest plot і для однобічного тесту (нескінченна межа обрізана до краю осі)")

print("\n== 5. Експорт звіту і без Даннетта")
dp = os.path.join(TMP, "d.docx"); R.export_window(rw, "docx", path=dp, ask_open=False); import docx
dd = docx.Document(dp); heads = [t.rows[0].cells[2].text for t in dd.tables if len(t.columns) >= 7]
check(sum(1 for h in heads if "Різниця з контролем" in h) == 3 and len(dd.inline_shapes) >= 8, f"Word-звіт: 3 таблиці Даннетта й графіки разом із Forest plot ({len(dd.inline_shapes)} рисунків)")
app2 = run_anova(choice=lambda app: {"ok": True, "method": "tukey"}); check(app2._dunnett_for_graph is None and "forest" not in app2._graph_figs, "з Тьюкі вкладки Forest plot немає")
it2 = R.collect(app2.report_win); check(not any("Різниця з контролем" in t["headers"] for t in it2 if t["kind"] == "table") and any(t["headers"][-1] == "Літери CLD" for t in it2 if t["kind"] == "table"), "з Тьюкі – звичні літери CLD, таблиць Даннетта немає")
check(not [m for m in msgs if m[0] == "showerror"], f"жодних помилок: {[m for m in msgs if m[0] == 'showerror'][:2]}")
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ДАННЕТТА В ANOVA ПРОЙДЕНО")
