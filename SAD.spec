# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pyinstaller SAD.spec --noconfirm --clean       (результат: dist/SAD/SAD.exe + тека _internal)
import glob, os, sys
from PyInstaller.utils.hooks import collect_submodules

here = os.path.abspath(SPECPATH)

# Усі модулі програми (sad_*.py) — явно, щоб ліниві імпорти всередині функцій гарантовано потрапили в пакет
mods = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(here, "sad_*.py")))

# Ресурси: логотип та іконка (якщо лежать поруч зі скриптом) — програма шукає їх у sys._MEIPASS
datas = []
for fn in ("Logo.png", "logo.png", "SAD_logo.png", "icon.ico"):
    p = os.path.join(here, fn)
    if os.path.exists(p):
        datas.append((p, "."))
icon = os.path.join(here, "icon.ico")
icon = icon if (sys.platform == "win32" and os.path.exists(icon)) else None

hidden = mods + [
    "tkinter.messagebox", "tkinter.filedialog", "tkinter.ttk", "tkinter.scrolledtext", "tkinter.font", "tkinter.colorchooser",
    "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_agg", "PIL._tkinter_finder",
    "scipy.special.cython_special", "scipy.sparse.linalg._dsolve", "scipy.spatial.transform",
] + collect_submodules("scipy.stats") + collect_submodules("openpyxl.styles") + collect_submodules("docx")

# Те, чого програма не використовує (зменшує розмір пакета)
excludes = ["pandas", "pytest", "IPython", "jupyter", "notebook", "PyQt5", "PyQt6", "PySide2", "PySide6", "sphinx",
            "numba", "tensorflow", "torch", "sklearn", "statsmodels", "matplotlib.tests", "scipy.tests", "numpy.tests"]

a = Analysis(["main.py"], pathex=[here], binaries=[], datas=datas, hiddenimports=hidden, hookspath=[], runtime_hooks=[],
             excludes=excludes, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="SAD", debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SAD")
