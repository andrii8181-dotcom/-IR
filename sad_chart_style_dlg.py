# sad_chart_style_dlg.py – S.A.D. v2.1: діалог налаштувань діаграм «Погоди» (розмір, шрифти, кольори, заголовок, легенда)
# -*- coding: utf-8 -*-
import copy
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import tkinter.font as tkfont
import sad_weather_charts as CH

RF = ("Times New Roman", 11)
RB = ("Times New Roman", 11, "bold")
PREFERRED_FONTS = ["Times New Roman", "Arial", "Calibri", "Cambria", "Verdana", "Tahoma", "Georgia", "Segoe UI", "Courier New",
                   "DejaVu Sans", "DejaVu Serif"]


def font_choices():
    try: fams = {f for f in tkfont.families() if not f.startswith("@")}
    except Exception: fams = set()
    pref = [f for f in PREFERRED_FONTS if f in fams]
    return pref + sorted(fams - set(pref)) if fams else PREFERRED_FONTS


def parse_float(text, name, lo=None, hi=None):
    try: v = float(str(text).replace(",", ".").strip())
    except ValueError: raise ValueError(f"«{name}»: потрібне число.")
    if lo is not None and v < lo or hi is not None and v > hi: raise ValueError(f"«{name}»: значення має бути від {lo:g} до {hi:g}.")
    return v


FIELDS = [("width_cm", "Ширина діаграми, см", 8, 60), ("height_cm", "Висота діаграми, см", 6, 45),
          ("font_size", "Основний шрифт, пт", 5, 30), ("title_size", "Заголовок, пт", 5, 36), ("label_size", "Підписи осей, пт", 5, 30),
          ("tick_size", "Поділки осей, пт", 4, 28), ("legend_size", "Легенда, пт", 4, 28), ("line_width", "Товщина ліній, пт", 0.3, 8),
          ("marker_size", "Розмір маркерів", 1, 20), ("dpi", "Роздільність при збереженні, dpi", 72, 600)]


class ChartStyleDialog:
    """Редагує стиль діаграми. Загальні параметри діють на всі діаграми; кольори й заголовок – лише на поточну."""
    def __init__(self, parent, kind, kind_title, rep, style, on_apply):
        self.parent, self.kind, self.rep, self.on_apply = parent, kind, rep, on_apply
        self.style = copy.deepcopy(style) if style else {}
        self.win = tk.Toplevel(parent); self.win.title("Налаштування діаграм"); self.win.transient(parent)
        try:
            from sad_common import set_icon; set_icon(self.win)
        except Exception: pass
        g = CH.sanitize_general(self.style.get("general"))
        self.gv = {}
        f = tk.Frame(self.win, padx=14, pady=10); f.pack(fill=tk.BOTH, expand=True)
        lf = tk.LabelFrame(f, text="Розмір і шрифти – для всіх діаграм", font=RB, padx=8, pady=6); lf.pack(fill=tk.X)
        r = 0
        tk.Label(lf, text="Шрифт:", font=RF).grid(row=r, column=0, sticky="w")
        self.gv["font_family"] = tk.StringVar(value=g["font_family"])
        ttk.Combobox(lf, textvariable=self.gv["font_family"], values=font_choices(), width=26).grid(row=r, column=1, columnspan=3, sticky="w", pady=2)
        for i, (key, label, lo, hi) in enumerate(FIELDS):
            rr, cc = 1 + i // 2, (i % 2) * 2
            tk.Label(lf, text=label + ":", font=RF).grid(row=rr, column=cc, sticky="w", padx=(0 if cc == 0 else 14, 4), pady=1)
            self.gv[key] = tk.StringVar(value=f"{g[key]:g}")
            tk.Entry(lf, textvariable=self.gv[key], width=8, font=RF).grid(row=rr, column=cc + 1, sticky="w")
        r2 = 2 + len(FIELDS) // 2
        cbf = tk.Frame(lf); cbf.grid(row=r2, column=0, columnspan=4, sticky="w", pady=(2, 0))
        for key, label in (("title_bold", "Заголовок жирним"), ("show_subtitle", "Підзаголовок (місце, період)"), ("grid", "Сітка")):
            self.gv[key] = tk.BooleanVar(value=bool(g[key]))
            tk.Checkbutton(cbf, text=label, variable=self.gv[key], font=RF).pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(lf, text="Положення легенди:", font=RF).grid(row=r2 + 1, column=0, sticky="w", pady=(4, 0))
        self.gv["legend_loc"] = tk.StringVar(value=g["legend_loc"])
        ttk.Combobox(lf, textvariable=self.gv["legend_loc"], values=list(CH.LEGEND_LOCS), state="readonly", width=22).grid(row=r2 + 1, column=1, columnspan=3, sticky="w", pady=(4, 0))
        lt = tk.LabelFrame(f, text=f"Ця діаграма: {kind_title}", font=RB, padx=8, pady=6); lt.pack(fill=tk.X, pady=(8, 0))
        tk.Label(lt, text="Заголовок (порожньо – стандартний):", font=RF).grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value=str((self.style.get("titles") or {}).get(kind) or ""))
        tk.Entry(lt, textvariable=self.title_var, width=46, font=RF).grid(row=0, column=1, sticky="we", padx=6, pady=2)
        self.colors = {}; self.cbtn = {}
        saved = (self.style.get("colors") or {}).get(kind) or {}
        tk.Label(lt, text="Кольори складових:", font=RF).grid(row=1, column=0, sticky="nw", pady=(6, 0))
        cf = tk.Frame(lt); cf.grid(row=1, column=1, sticky="w", pady=(6, 0))
        comps = CH.components(kind, rep)
        for i, (key, label, default) in enumerate(comps):
            self.colors[key] = saved.get(key) or default
            tk.Label(cf, text=label, font=("Times New Roman", 10)).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6) if i % 2 == 0 else (14, 6))
            b = tk.Button(cf, text="      ", relief=tk.RAISED, bd=2, bg=self.colors[key], command=lambda k=key: self._choose(k))
            b.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", pady=1); self.cbtn[key] = b
        self.defaults = {key: default for key, _, default in comps}
        if not comps: tk.Label(cf, text="(для цієї діаграми кольори не налаштовуються)", font=("Times New Roman", 10), fg="#666").grid(row=0, column=0)
        bt = tk.Frame(f); bt.pack(fill=tk.X, pady=(12, 0))
        tk.Button(bt, text="✔ Застосувати", bg="#1a6b1a", fg="white", font=RF, command=self.apply).pack(side=tk.LEFT)
        tk.Button(bt, text="Застосувати й закрити", font=RF, command=lambda: self.apply(close=True)).pack(side=tk.LEFT, padx=6)
        tk.Button(bt, text="Кольори до типових", font=("Times New Roman", 10), command=self.reset_colors).pack(side=tk.LEFT, padx=(14, 0))
        tk.Button(bt, text="Усе до типових", font=("Times New Roman", 10), command=self.reset_all).pack(side=tk.LEFT, padx=6)
        tk.Button(bt, text="Закрити", font=RF, command=self.win.destroy).pack(side=tk.RIGHT)
        try:
            from sad_common import center_win; center_win(self.win)
        except Exception: pass

    def _choose(self, key):
        c = colorchooser.askcolor(color=self.colors[key], parent=self.win, title="Колір складової")
        if c and c[1]: self.set_color(key, c[1])

    def set_color(self, key, color):
        self.colors[key] = color; self.cbtn[key].configure(bg=color)

    def reset_colors(self):
        for k, d in self.defaults.items(): self.set_color(k, d)

    def reset_all(self):
        d = CH.DEFAULT_GENERAL
        for k, v in d.items():
            var = self.gv[k]; var.set(v if isinstance(v, (bool, str)) else f"{v:g}")
        self.title_var.set(""); self.reset_colors()

    def collect(self):
        """Читає значення з форми й повертає повний словник стилю (або кидає ValueError з поясненням)."""
        gen = {}
        for key, label, lo, hi in FIELDS: gen[key] = parse_float(self.gv[key].get(), label, lo, hi)
        gen["dpi"] = int(gen["dpi"])
        gen["font_family"] = self.gv["font_family"].get().strip() or CH.DEFAULT_GENERAL["font_family"]
        for key in ("title_bold", "show_subtitle", "grid"): gen[key] = bool(self.gv[key].get())
        gen["legend_loc"] = self.gv["legend_loc"].get()
        st = copy.deepcopy(self.style)
        st["general"] = CH.sanitize_general(gen)
        cols = {k: v for k, v in self.colors.items() if v.lower() != self.defaults.get(k, "").lower()}
        st.setdefault("colors", {})
        if cols: st["colors"][self.kind] = cols
        else: st["colors"].pop(self.kind, None)
        st.setdefault("titles", {})
        t = self.title_var.get().strip()
        if t: st["titles"][self.kind] = t
        else: st["titles"].pop(self.kind, None)
        return st

    def apply(self, close=False):
        try: st = self.collect()
        except ValueError as e:
            messagebox.showwarning("Перевірте значення", str(e), parent=self.win); return None
        self.style = st; CH.save_style(st); self.on_apply(st)
        if close: self.win.destroy()
        return st
