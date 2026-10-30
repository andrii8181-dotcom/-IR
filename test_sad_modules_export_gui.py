# test_sad_modules_export_gui.py – експорт звіту у Word/Excel із РЕАЛЬНИХ запусків усіх аналізів (потрібен дисплей; Xvfb)
# Кожен аналіз виконується в окремому процесі (export_probe.py), щоб модальне вікно чи збій не зупинили решту.
import os, sys, json, subprocess, tempfile, shutil, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.environ.get("SAD_SRC", HERE)
os.environ.setdefault("DISPLAY", ":99")
FAIL = []
def check(c, msg):
    print(("  [OK]   " if c else "  [FAIL] ") + msg, flush=True)
    if not c: FAIL.append(msg)
TMP = tempfile.mkdtemp(prefix="sad_modexp_")
# назва: (мін. таблиць, мін. графіків, людська назва)
EXPECT = {"anova": (8, 7, "ANOVA 2-факторний (RCBD)"), "desc": (1, 2, "Описова статистика"), "ttest": (0, 0, "t-тест"), "reg": (1, 2, "Регресія"), "rm": (3, 1, "Повторні виміри"),
          "mixed": (3, 1, "Змішані повторні виміри"), "manova": (3, 2, "MANOVA"), "cluster": (1, 1, "Кластерний аналіз"), "pca": (2, 3, "PCA"), "stab": (1, 1, "Стабільність (G×E)"),
          "ancova": (3, 1, "ANCOVA"), "corr": (1, 2, "Кореляційний аналіз")}
def run(name):
    p = subprocess.run([sys.executable, os.path.join(SRC, "export_probe.py"), name, TMP], capture_output=True, text=True, timeout=150, env={**os.environ, "SAD_SRC": SRC})
    line = next((l for l in p.stdout.split("\n") if l.startswith("RESULT ")), None)
    return json.loads(line[7:]) if line else {"name": name, "exception": (p.stderr or p.stdout)[-400:]}
with cf.ThreadPoolExecutor(max_workers=6) as ex: results = dict(zip(EXPECT, ex.map(run, EXPECT)))
for name, (mt, mf, human) in EXPECT.items():
    r = results[name]; print(f"\n== {human}")
    if "exception" in r or "fatal" in r: check(False, f"аналіз запустився без винятків: {r.get('exception') or r.get('fatal')}"); continue
    check(r["found_window"] and not r["errors"], f"аналіз виконано, вікно результатів відкрито («{r['title']}»), помилок немає")
    check(r.get("bar") is True, "у вікні є смужка «📄 Word · 📊 Excel»")
    nt = len(r["tables"]); nf = r["figures"]
    check(nt >= mt and nf >= mf, f"у звіті таблиць {nt} (≥ {mt}), графіків {nf} (≥ {mf})")
    check(not r["junk"], "тексти кнопок і службових написів у звіт не потрапили")
    check(r["docx"]["tables"] == nt and r["docx"]["images"] == nf and r["docx"]["grid"], f"Word: {r['docx']['tables']} таблиць (усі з сіткою) і {r['docx']['images']} рисунків відповідають зібраному")
    check(r["xlsx"]["sheets"] == 1 + nt + (1 if nf else 0), f"Excel: {r['xlsx']['sheets']} аркушів (звіт + {nt} таблиць{' + графіки' if nf else ''})")
r = results["reg"]; check(any(t[0][:2] == ["Показник", "Значення"] and t[1] >= 8 for t in r["tables"]), "регресія: пари «мітка + значення» (Модель, R², F, p…) зведено в таблицю «Показник | Значення»")
r = results["anova"]; check(r["kinds"].get("caption") == 8 and len(r["headings"]) == 8 and r["headings"][0] == "Дисперсійний аналіз (ANOVA)", "ANOVA: 8 таблиць із підписами без дублювання нумерації («ТАБЛИЦЯ N.» → «Таблиця N –»)")
r = results["ttest"]; check(r["kinds"].get("text", 0) >= 2 and "table" not in r["kinds"], "t-тест: текстовий результат лишається абзацами (рядки «ключ = значення» не перетворено на таблицю)")
r = results["corr"]; check(r["tables"][0][0][:3] == ["Показник 1", "Показник 2", "n"] and r["tables"][0][1] == 6 and r["headings"] == [], "кореляція: таблиця 6 пар (4 показники) і дві діаграми; підписи осей не потрапили у звіт")
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + "=" * 60)
if FAIL: print(f"ПРОВАЛІВ: {len(FAIL)}"); [print("  -", f) for f in FAIL]; sys.exit(1)
print("УСІ ПЕРЕВІРКИ ЕКСПОРТУ ЗВІТІВ ІЗ УСІХ МОДУЛІВ ПРОЙДЕНО")
