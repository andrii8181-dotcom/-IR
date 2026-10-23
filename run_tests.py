# run_tests.py — запускач усіх тестів S.A.D. (паралельно).
#   python run_tests.py          — тести без графічного інтерфейсу
#   python run_tests.py --gui    — додатково GUI-тести (потрібен дисплей; на Linux: xvfb-run -a python run_tests.py --gui)
import os, sys, subprocess, glob, re, time
from concurrent.futures import ThreadPoolExecutor
here = os.path.dirname(os.path.abspath(__file__))
gui = "--gui" in sys.argv
files = sorted(os.path.basename(f) for f in glob.glob(os.path.join(here, "test_*.py")))
files = [f for f in files if gui or "_gui" not in f]
env = dict(os.environ, SAD_SRC=here, PYTHONIOENCODING="utf-8")
def run(f):
    t0 = time.time()
    p = subprocess.run([sys.executable, "-u", f], cwd=here, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    out = p.stdout + p.stderr
    return f, out.count("[OK]"), out.count("[FAIL]"), p.returncode, time.time() - t0
workers = 1 if gui else 4          # GUI-тести не запускаємо паралельно
print(f"Запуск {len(files)} наборів тестів…")
tot_ok = tot_fail = bad = 0
with ThreadPoolExecutor(workers) as ex:
    for f, ok, fail, rc, dt in ex.map(run, files):
        tot_ok += ok; tot_fail += fail; bad += (rc != 0)
        print(f"  {'ПРОЙДЕНО' if rc == 0 else 'ПРОВАЛ  '}  {f:<38s} перевірок: {ok:<4d} провалів: {fail:<2d} ({dt:.0f} с)")
print(f"\nУсього перевірок: {tot_ok}, провалів: {tot_fail}, наборів із помилкою: {bad}")
sys.exit(1 if (tot_fail or bad) else 0)
