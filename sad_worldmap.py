# sad_worldmap.py – S.A.D. v2.1: вбудована карта світу для вибору місця досліду (офлайн; дані Natural Earth, суспільне надбання)
# -*- coding: utf-8 -*-
"""
Інтерактивна карта: переміщення мишею, масштаб коліщатком, клік – вибір точки. Показує кордони країн і областей, озера, річки,
міста (з українськими назвами), координатну сітку, масштабну лінійку. Працює без інтернету: потрібен лише файл sad_worldmap.npz
(готується tools/build_worldmap_data.py). Для комірки сітки NASA POWER (≈ 50 км) цієї деталізації достатньо.
"""
import os, sys, math
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

OCEAN, LAND, BORDER = "#bcd8ec", "#f4f0e3", "#7d7d7d"
TILE = 256.0
ZMAX = 10.0
FILE = "sad_worldmap.npz"


# ═══════════════════════════════════════════════════════════════
# Проєкція Web Mercator
# ═══════════════════════════════════════════════════════════════
def ll_to_m(lon, lat):
    """lon, lat (градуси) → частки світу x, y ∈ [0, 1] (y зверху донизу)."""
    lon = np.asarray(lon, float); lat = np.clip(np.asarray(lat, float), -85.0511, 85.0511)
    return (lon + 180.0) / 360.0, (1.0 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2.0


def m_to_ll(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    return x * 360.0 - 180.0, np.degrees(np.arctan(np.sinh(math.pi * (1.0 - 2.0 * y))))


# ═══════════════════════════════════════════════════════════════
# Відсікання контурів по межах вікна (Tk/X11 некоректно малює координати за ±32767)
# ═══════════════════════════════════════════════════════════════
def clip_polygon(px, py, x0, y0, x1, y1):
    """Сазерленд–Ходжмен для прямокутника (векторизовано). Повертає масив (k, 2)."""
    pts = np.column_stack([np.asarray(px, float), np.asarray(py, float)])
    for axis, bound, keep_ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        if len(pts) == 0: break
        c = pts[:, axis]; inside = (c >= bound) if keep_ge else (c <= bound)
        if inside.all(): continue
        if not inside.any(): return np.zeros((0, 2))
        nxt = np.roll(pts, -1, axis=0); inside_n = np.roll(inside, -1)
        d = nxt[:, axis] - c
        t = np.where(d != 0, (bound - c) / np.where(d != 0, d, 1.0), 0.0)
        inter = pts + (nxt - pts) * t[:, None]
        out = np.empty((len(pts), 2, 2)); out[:, 0] = inter; out[:, 1] = nxt
        pts = out[np.stack([inside != inside_n, inside_n], axis=1)]
    return pts


def clip_polyline(px, py, x0, y0, x1, y1):
    """Ліанг–Барскі для ламаної (векторизовано). Повертає список масивів (k, 2) – видимі шматки."""
    p = np.column_stack([np.asarray(px, float), np.asarray(py, float)])
    if len(p) < 2: return []
    a, b = p[:-1], p[1:]; d = b - a
    t0 = np.zeros(len(a)); t1 = np.ones(len(a)); ok = np.ones(len(a), bool)
    for pv, qv in ((-d[:, 0], a[:, 0] - x0), (d[:, 0], x1 - a[:, 0]), (-d[:, 1], a[:, 1] - y0), (d[:, 1], y1 - a[:, 1])):
        par = pv == 0
        ok &= ~(par & (qv < 0))
        with np.errstate(divide="ignore", invalid="ignore"): r = np.where(par, 0.0, qv / np.where(par, 1.0, pv))
        t0 = np.where((pv < 0) & ~par, np.maximum(t0, r), t0)
        t1 = np.where((pv > 0) & ~par, np.minimum(t1, r), t1)
    ok &= t0 <= t1
    out, cur, prev, prev_exit = [], [], -2, False
    for i in np.nonzero(ok)[0]:
        s = a[i] + d[i] * t0[i]; e = a[i] + d[i] * t1[i]
        if i == prev + 1 and not prev_exit and t0[i] == 0.0: cur.append(e)
        else:
            if cur: out.append(np.array(cur))
            cur = [s, e]
        prev = i; prev_exit = t1[i] < 1.0
    if cur: out.append(np.array(cur))
    return out


# ═══════════════════════════════════════════════════════════════
# Дані карти
# ═══════════════════════════════════════════════════════════════
def data_path():
    cands = [os.path.join(os.path.dirname(os.path.abspath(__file__)), FILE)]
    if getattr(sys, "_MEIPASS", None): cands.insert(0, os.path.join(sys._MEIPASS, FILE))
    cands.append(os.path.join(os.getcwd(), FILE))
    for c in cands:
        if os.path.exists(c): return c
    return None


class MapData:
    _inst = None

    def __init__(self, path=None):
        path = path or data_path()
        if not path: raise FileNotFoundError(f"Не знайдено файл карти {FILE}.")
        z = np.load(path, allow_pickle=False)
        self.z = {k: z[k] for k in z.files}
        self.pl = self.z["places_lonlat"]; self.pop = self.z["places_pop"]
        self._lower = {k: np.char.lower(self.z["places_" + k]) for k in ("uk", "en", "loc", "ru")}
        from collections import Counter
        self._dup = Counter(str(x) for x in self.z["places_uk"])           # однойменні міста – щоб вказувати область лише за потреби

    @classmethod
    def get(cls):
        if cls._inst is None: cls._inst = cls()
        return cls._inst

    def layer(self, key, lod):
        k = f"{key}{lod}"
        if f"{k}_xy" not in self.z: return None
        return tuple(self.z[f"{k}_{s}"] for s in ("xy", "off", "bb", "ref", "val"))

    def country_at(self, lon, lat):
        """Назва країни під точкою (грубий контур LOD1) або ''."""
        xy, off, bb, ref, _ = self.layer("land", 1)
        idx = np.nonzero((bb[:, 0] <= lon) & (bb[:, 2] >= lon) & (bb[:, 1] <= lat) & (bb[:, 3] >= lat))[0]
        from matplotlib.path import Path
        for i in idx:
            if Path(xy[off[i]:off[i + 1]]).contains_point((lon, lat)): return str(self.z["countries_names"][ref[i]])
        return ""

    def nearest(self, lon, lat, max_km=150.0):
        """Найближче місто: (індекс, відстань, км) або None."""
        dlat = np.radians(self.pl[:, 1] - lat); dlon = np.radians(self.pl[:, 0] - lon)
        a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat)) * np.cos(np.radians(self.pl[:, 1])) * np.sin(dlon / 2) ** 2
        dist = 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        i = int(np.argmin(dist))
        return (i, float(dist[i])) if dist[i] <= max_km else None

    def label(self, i, lang="uk"):
        z = self.z
        nm = str(z["places_uk"][i] if lang == "uk" else z["places_en"][i]) or str(z["places_loc"][i])
        return nm

    def full_label(self, i):
        z = self.z; parts = [str(z["places_uk"][i]) or str(z["places_loc"][i])]
        if self._dup.get(parts[0], 0) > 1 and str(z["places_adm1"][i]) and str(z["places_adm1"][i]) != parts[0]: parts.append(str(z["places_adm1"][i]))
        if str(z["places_country"][i]): parts.append(str(z["places_country"][i]))
        return ", ".join(parts)

    def search(self, query, limit=30):
        """Пошук міст за назвою (укр., англ., місцева, рос.): точний збіг → початок → входження; за населенням."""
        q = " ".join(str(query).lower().split())
        if not q: return []
        score = np.zeros(len(self.pop), int)
        for k, arr in self._lower.items():
            score = np.maximum(score, np.where(arr == q, 3, np.where(np.char.startswith(arr, q), 2, np.where(np.char.find(arr, q) >= 0, 1, 0))))
        idx = np.nonzero(score > 0)[0]
        idx = idx[np.lexsort((-self.pop[idx], -score[idx]))][:limit]
        return [{"label": self.full_label(i), "lat": float(self.pl[i, 1]), "lon": float(self.pl[i, 0]), "pop": float(self.pop[i]), "index": int(i)} for i in idx]


def nice_length(max_m):
    """Найбільше «кругле» число 1/2/5·10ⁿ, що не перевищує max_m."""
    if max_m <= 0: return 1.0
    e = 10 ** math.floor(math.log10(max_m))
    for m in (5, 2, 1):
        if m * e <= max_m: return m * e
    return e


# ═══════════════════════════════════════════════════════════════
# Віджет карти
# ═══════════════════════════════════════════════════════════════
class WorldMap(tk.Canvas):
    def __init__(self, master, on_pick=None, on_hover=None, lang="uk", **kw):
        kw.setdefault("bg", OCEAN); kw.setdefault("highlightthickness", 0); kw.setdefault("width", 880); kw.setdefault("height", 600)
        super().__init__(master, **kw)
        self.data = MapData.get(); self.on_pick = on_pick; self.on_hover = on_hover; self.lang = lang
        self.z = 2.0; self.cx = 0.56; self.cy = 0.34; self.marker = None
        self._press = None; self._moved = False; self._job = None
        self.f_place = tkfont.Font(family="Times New Roman", size=9); self.f_bold = tkfont.Font(family="Times New Roman", size=10, weight="bold")
        self.f_ctry = tkfont.Font(family="Times New Roman", size=10, slant="italic"); self.f_small = tkfont.Font(family="Times New Roman", size=8)
        self.bind("<Configure>", lambda e: self._schedule())
        self.bind("<ButtonPress-1>", self._on_press); self.bind("<B1-Motion>", self._on_drag); self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<MouseWheel>", self._on_wheel); self.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 0.5))
        self.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, -0.5)); self.bind("<Double-Button-1>", lambda e: self._zoom_at(e.x, e.y, 1.0))
        self.bind("<Motion>", self._on_motion)
        self.stats = {"redraw_ms": 0.0, "items": 0}

    # ── геометрія ──
    @property
    def world(self): return TILE * 2.0 ** self.z
    def size(self): return max(self.winfo_width(), 2), max(self.winfo_height(), 2)
    def zmin(self):
        w, h = self.size(); return max(1.0, math.log2(max(min(w, h), 256) / TILE))

    def to_px(self, lon, lat):
        mx, my = ll_to_m(lon, lat); w, h = self.size(); W = self.world
        return (mx - self.cx) * W + w / 2.0, (my - self.cy) * W + h / 2.0

    def from_px(self, px, py):
        w, h = self.size(); W = self.world
        lon, lat = m_to_ll(self.cx + (px - w / 2.0) / W, self.cy + (py - h / 2.0) / W)
        return float(lon), float(lat)

    def _clamp(self):
        self.z = min(max(self.z, self.zmin()), ZMAX)
        self.cx = min(max(self.cx, 0.0), 1.0); self.cy = min(max(self.cy, 0.0), 1.0)

    # ── керування ──
    def goto(self, lon, lat, z=None, redraw=True):
        self.cx, self.cy = (float(v) for v in ll_to_m(lon, lat))
        if z is not None: self.z = z
        self._clamp()
        if redraw: self.redraw()

    def fit_world(self):
        self.z = self.zmin(); self.cx, self.cy = 0.55, 0.38; self._clamp(); self.redraw()

    def set_marker(self, lon, lat, center=False, z=None):
        self.marker = (float(lon), float(lat))
        if center: self.goto(lon, lat, z)
        else: self.redraw()

    def _zoom_at(self, px, py, dz):
        lon, lat = self.from_px(px, py); w, h = self.size()
        self.z = min(max(self.z + dz, self.zmin()), ZMAX)
        mx, my = ll_to_m(lon, lat); W = self.world                       # точка під курсором лишається на місці
        self.cx = float(mx - (px - w / 2.0) / W); self.cy = float(my - (py - h / 2.0) / W); self._clamp(); self._schedule()

    def zoom_in(self): self._zoom_at(self.size()[0] / 2, self.size()[1] / 2, 1.0)
    def zoom_out(self): self._zoom_at(self.size()[0] / 2, self.size()[1] / 2, -1.0)

    def _on_wheel(self, e): self._zoom_at(e.x, e.y, 0.5 if e.delta > 0 else -0.5)

    def _on_press(self, e): self._press = (e.x, e.y, self.cx, self.cy); self._moved = False; self.focus_set()

    def _on_drag(self, e):
        """Під час перетягування лише зсуваємо вже намальоване (швидко); нову ділянку домальовуємо після відпускання кнопки."""
        if not self._press: return
        x0, y0, cx0, cy0 = self._press
        if not self._moved and abs(e.x - x0) + abs(e.y - y0) > 4:
            self._moved = True; self.scan_mark(x0, y0)
        if self._moved: self.scan_dragto(e.x, e.y, gain=1)

    def _on_release(self, e):
        if self._press and not self._moved: self.pick_at(e.x, e.y)
        elif self._press:
            x0, y0, cx0, cy0 = self._press
            self.cx = cx0 - (e.x - x0) / self.world; self.cy = cy0 - (e.y - y0) / self.world; self._clamp(); self.redraw()
        self._press = None

    def pick_at(self, px, py):
        lon, lat = self.from_px(px, py)
        if not (-180 <= lon <= 180 and -85.05 <= lat <= 85.05): return
        self.marker = (lon, lat); self.redraw()
        if self.on_pick: self.on_pick(lon, lat)

    def _on_motion(self, e):
        if self.on_hover:
            lon, lat = self.from_px(e.x, e.y)
            self.on_hover(lon, lat)

    def _schedule(self):
        if self._job is None: self._job = self.after(18, self._do_redraw)
    def _do_redraw(self): self._job = None; self.redraw()

    # ── малювання ──
    def _lod(self): return 0 if self.z < 3.3 else (1 if self.z < 6.2 else 2)

    def _view_bbox(self):
        w, h = self.size(); lon0, lat1 = self.from_px(0, 0); lon1, lat0 = self.from_px(w, h)
        return min(lon0, lon1), lat0, max(lon0, lon1), lat1

    def _project(self, ring):
        mx, my = ll_to_m(ring[:, 0], ring[:, 1]); w, h = self.size(); W = self.world
        return (mx - self.cx) * W + w / 2.0, (my - self.cy) * W + h / 2.0

    def _visible(self, bb, vb):
        return np.nonzero((bb[:, 2] >= vb[0]) & (bb[:, 0] <= vb[2]) & (bb[:, 3] >= vb[1]) & (bb[:, 1] <= vb[3]))[0]

    def _rings(self, layer, vb, fill=None, line=None, width=1.0, dash=None, min_val=None, minpx=1.2, closed_fill=False):
        if layer is None: return 0
        xy, off, bb, ref, val = layer; w, h = self.size(); m = 20; n = 0
        for i in self._visible(bb, vb):
            if min_val is not None and val[i] > min_val: continue
            px, py = self._project(xy[off[i]:off[i + 1]])
            if (px.max() - px.min()) < minpx and (py.max() - py.min()) < minpx: continue
            if fill:
                poly = clip_polygon(px, py, -m, -m, w + m, h + m)
                if len(poly) >= 3: self.create_polygon(poly.ravel().tolist(), fill=fill, outline=""); n += 1
            if line:
                for seg in clip_polyline(px, py, -m, -m, w + m, h + m):
                    if len(seg) >= 2:
                        kw = dict(fill=line, width=width)
                        if dash: kw["dash"] = dash
                        self.create_line(seg.ravel().tolist(), **kw); n += 1
        return n

    def _graticule(self, w, h):
        span = 360.0 / (2.0 ** self.z)                              # градусів на 256 px
        step = next(s for s in (30, 10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01) if s <= span * 1.3 or s == 0.01)
        lon0, lat0, lon1, lat1 = self._view_bbox()
        lo = math.floor(lon0 / step) * step
        while lo <= lon1 + step:
            x, _ = self.to_px(lo, 0); self.create_line(x, 0, x, h, fill="#a9c6dc", width=1)
            if 0 <= x <= w: self.create_text(x + 3, h - 28, text=f"{lo:g}°", anchor="sw", font=self.f_small, fill="#4f7390")
            lo += step
        la = math.floor(lat0 / step) * step
        while la <= lat1 + step:
            _, y = self.to_px(0, la); self.create_line(0, y, w, y, fill="#a9c6dc", width=1)
            if 0 <= y <= h: self.create_text(4, y - 2, text=f"{la:g}°", anchor="sw", font=self.f_small, fill="#4f7390")
            la += step

    def redraw(self):
        import time as _t
        t0 = _t.perf_counter(); self.delete("all"); w, h = self.size(); self._clamp(); z = self.z; lod = self._lod(); vb = self._view_bbox(); D = self.data; n = 0
        self.create_rectangle(0, 0, w, h, fill=OCEAN, outline="")
        land = D.layer("land", lod)
        n += self._rings(land, vb, fill=LAND, line=None, minpx=0.8)
        if z >= 2.2: self._graticule(w, h)
        lakes = D.layer("lake", lod); n += self._rings(lakes, vb, fill=OCEAN, line="#8db4d6", width=0.8, min_val=z + 0.5)
        if lod >= 1 and z >= 4.4: n += self._rings(D.layer("adm1", lod), vb, line="#a8a8a8", width=0.8, dash=(4, 3))
        if lod >= 1 and z >= 4.6: n += self._rings(D.layer("river", lod), vb, line="#6fa8dc", width=1.0, min_val=z + 0.3, minpx=2.0)
        n += self._rings(land, vb, line=BORDER, width=1.0, minpx=0.8)
        labels = []
        lat_c = self.from_px(w / 2, h / 2)[1]; mpp = 40075016.686 * math.cos(math.radians(lat_c)) / self.world
        L = nice_length(mpp * 130); px_len = L / mpp; x0, y0 = 12, h - 12
        sb_text = f"{L / 1000:g} км" if L >= 1000 else f"{L:g} м"; sb_w = px_len + 14 + self.f_place.measure(sb_text)
        labels.append((0, h - 34, x0 + sb_w + 12, h))                             # зарезервовано під лінійку
        # назви країн
        if 2.2 <= z <= 7.0:
            cx_, cr = D.z["countries_label_xy"], D.z["countries_label_rank"]; names = D.z["countries_names"]
            for i in np.argsort(cr):
                if z < 1.6 + 0.45 * (cr[i] - 1.0): continue
                px, py = self.to_px(cx_[i][0], cx_[i][1])
                if not (0 <= px <= w and 0 <= py <= h): continue
                t = str(names[i]); tw = self.f_ctry.measure(t); box = (px - tw / 2, py - 7, px + tw / 2, py + 7)
                if self._free(labels, box): labels.append(box); self.create_text(px, py, text=t, font=self.f_ctry, fill="#6d6d6d"); n += 1
        # міста
        pl, pop, mz = D.pl, D.pop, D.z["places_minzoom"]
        inview = np.nonzero((pl[:, 0] >= vb[0]) & (pl[:, 0] <= vb[2]) & (pl[:, 1] >= vb[1]) & (pl[:, 1] <= vb[3]) & (mz <= z + 0.6))[0]
        order = inview[np.argsort(-pop[inview])][:260]
        for i in order:
            px, py = self.to_px(pl[i, 0], pl[i, 1]); r = 3.4 if pop[i] >= 1e6 else (2.6 if pop[i] >= 1e5 else 2.0)
            name = D.label(int(i), self.lang); tw = self.f_place.measure(name); box = (px + r + 2, py - 7, px + r + 4 + tw, py + 7)
            self.create_oval(px - r, py - r, px + r, py + r, fill="#333", outline="white"); n += 1
            if self._free(labels, box):
                labels.append(box); self.create_text(px + r + 3, py, text=name, anchor="w", font=self.f_bold if pop[i] >= 1e6 else self.f_place, fill="#222"); n += 1
        # масштабна лінійка (на світлій підкладці)
        self.create_rectangle(4, h - 32, x0 + sb_w + 6, h - 4, fill="#f8fafc", outline="#c5d3df")
        self.create_line(x0, y0, x0 + px_len, y0, width=3, fill="#222"); self.create_line(x0, y0 - 5, x0, y0 + 1, width=2, fill="#222"); self.create_line(x0 + px_len, y0 - 5, x0 + px_len, y0 + 1, width=2, fill="#222")
        self.create_text(x0 + px_len + 6, y0 - 3, anchor="w", text=sb_text, font=self.f_place, fill="#222")
        self.create_text(w - 6, h - 4, anchor="se", text="Natural Earth (суспільне надбання)", font=self.f_small, fill="#6b8aa3")
        if self.marker: self._draw_marker()
        self.stats = {"redraw_ms": (_t.perf_counter() - t0) * 1000.0, "items": n}

    @staticmethod
    def _free(placed, box):
        for b in placed:
            if box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1]: return False
        return True

    def _draw_marker(self):
        px, py = self.to_px(*self.marker); w, h = self.size()
        if not (-30 <= px <= w + 30 and -30 <= py <= h + 30): return
        self.create_line(px - 14, py, px + 14, py, fill="#d62728", width=1); self.create_line(px, py - 14, px, py + 14, fill="#d62728", width=1)
        self.create_oval(px - 8, py - 8, px + 8, py + 8, outline="#d62728", width=2, fill="")
        self.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5, fill="#d62728", outline="white")
        txt = f"{self.marker[1]:.4f}°, {self.marker[0]:.4f}°"; tw = self.f_small.measure(txt)
        self.create_rectangle(px - tw / 2 - 3, py - 33, px + tw / 2 + 3, py - 19, fill="white", outline="#d62728")
        self.create_text(px, py - 26, text=txt, font=self.f_small, fill="#a01010")


# ═══════════════════════════════════════════════════════════════
# Пошук за назвою (офлайн за містами + необов'язково онлайн, OpenStreetMap)
# ═══════════════════════════════════════════════════════════════
class PlaceSearch(tk.Frame):
    def __init__(self, master, on_pick, online_search=None, width=34, lines=9, **kw):
        super().__init__(master, **kw)
        self.on_pick = on_pick; self.online_search = online_search; self.found = []
        RF = ("Times New Roman", 11)
        row = tk.Frame(self); row.pack(fill=tk.X)
        self.qv = tk.StringVar(); self.ent = tk.Entry(row, textvariable=self.qv, font=RF, width=width); self.ent.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Знайти", font=RF, command=self.search).pack(side=tk.LEFT, padx=(4, 0))
        self.lb = tk.Listbox(self, height=lines, font=("Times New Roman", 10), exportselection=False); self.lb.pack(fill=tk.BOTH, expand=True, pady=4)
        self.info = tk.Label(self, text="", font=("Times New Roman", 9), fg="#666", justify="left", wraplength=300, anchor="w"); self.info.pack(fill=tk.X)
        if online_search:
            tk.Button(self, text="🌐 Шукати в інтернеті (села, малі пункти)", font=("Times New Roman", 10), command=self.search_online).pack(fill=tk.X, pady=(3, 0))
            tk.Label(self, text="Онлайн-пошук: OpenStreetMap Nominatim, один запит на натискання; © учасники OpenStreetMap (ODbL).",
                     font=("Times New Roman", 8), fg="#777", wraplength=300, justify="left").pack(fill=tk.X)
        self.ent.bind("<Return>", lambda e: self.search()); self.lb.bind("<Double-Button-1>", lambda e: self.pick()); self.lb.bind("<Return>", lambda e: self.pick())
        self.lb.bind("<<ListboxSelect>>", lambda e: None)

    def _show(self, res, note=""):
        self.found = res; self.lb.delete(0, tk.END)
        for r in res: self.lb.insert(tk.END, f"{r['label']}  ({r['lat']:.3f}, {r['lon']:.3f})")
        if not res: self.lb.insert(tk.END, "Нічого не знайдено")
        self.info.configure(text=note)

    def search(self):
        q = self.qv.get().strip()
        if not q: return
        try: res = MapData.get().search(q)
        except Exception as e: self._show([], f"Помилка пошуку: {e}"); return
        self._show(res, "Знайдено в довіднику міст світу. Для сіл і малих пунктів скористайтесь онлайн-пошуком." if res else
                   "У довіднику міст немає такої назви. Спробуйте онлайн-пошук (села, малі пункти) або оберіть місце на карті.")
        if res: self.lb.selection_set(0)

    def search_online(self):
        q = self.qv.get().strip()
        if not q: return
        self.winfo_toplevel().configure(cursor="watch"); self.update_idletasks()
        try: res = self.online_search(q)
        except Exception as e:
            self.winfo_toplevel().configure(cursor=""); messagebox.showwarning("Онлайн-пошук", str(e), parent=self.winfo_toplevel())
            self._show(self.found, "Онлайн-пошук недоступний: перевірте інтернет."); return
        self.winfo_toplevel().configure(cursor="")
        self._show(res, "Результати OpenStreetMap." if res else "OpenStreetMap нічого не знайшов за цією назвою.")
        if res: self.lb.selection_set(0)

    def pick(self):
        sel = self.lb.curselection()
        if not sel or sel[0] >= len(self.found): return
        self.on_pick(self.found[sel[0]])


# ═══════════════════════════════════════════════════════════════
# Діалог вибору місця на карті
# ═══════════════════════════════════════════════════════════════
class MapPickerDialog:
    def __init__(self, parent, lat=None, lon=None, online_search=None, title="Оберіть місце досліду на карті"):
        from sad_common import set_icon, center_win
        self.result = None; self.lat = lat; self.lon = lon; self.label = ""
        self.win = tk.Toplevel(parent); self.win.title(title); set_icon(self.win); self.win.geometry("1240x760"); self.win.transient(parent)
        RF = ("Times New Roman", 11)
        body = tk.Frame(self.win); body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        left = tk.Frame(body); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tb = tk.Frame(left); tb.pack(fill=tk.X, pady=(0, 4))
        self.map = WorldMap(left, on_pick=self._picked, on_hover=self._hover); 
        tk.Button(tb, text="＋", font=("Times New Roman", 13, "bold"), width=3, command=lambda: self.map.zoom_in()).pack(side=tk.LEFT)
        tk.Button(tb, text="－", font=("Times New Roman", 13, "bold"), width=3, command=lambda: self.map.zoom_out()).pack(side=tk.LEFT, padx=2)
        tk.Button(tb, text="🌍 Весь світ", font=RF, command=lambda: self.map.fit_world()).pack(side=tk.LEFT, padx=6)
        self.lang_var = tk.StringVar(value="uk")
        for v, t in (("uk", "Назви: укр."), ("en", "англ.")):
            tk.Radiobutton(tb, text=t, variable=self.lang_var, value=v, font=("Times New Roman", 10), command=self._lang).pack(side=tk.LEFT)
        self.hover = tk.Label(tb, text="Рухайте карту мишею, масштабуйте коліщатком, клікніть, щоб обрати точку.", font=("Times New Roman", 10), fg="#1a4b8c", anchor="e")
        self.hover.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        self.map.pack(fill=tk.BOTH, expand=True)
        right = tk.Frame(body, width=330, padx=10); right.pack(side=tk.LEFT, fill=tk.Y); right.pack_propagate(False)
        lf = tk.LabelFrame(right, text="Знайти за назвою", font=("Times New Roman", 11, "bold"), padx=6, pady=4); lf.pack(fill=tk.X)
        PlaceSearch(lf, self._search_pick, online_search=online_search, width=22, lines=7).pack(fill=tk.X)
        cf = tk.LabelFrame(right, text="Обрана точка", font=("Times New Roman", 11, "bold"), padx=6, pady=4); cf.pack(fill=tk.X, pady=(8, 0))
        self.lat_v, self.lon_v = tk.StringVar(), tk.StringVar()
        for r, (t, v) in enumerate((("Широта, °N:", self.lat_v), ("Довгота, °E:", self.lon_v))):
            tk.Label(cf, text=t, font=RF).grid(row=r, column=0, sticky="w"); tk.Entry(cf, textvariable=v, font=RF, width=14).grid(row=r, column=1, sticky="w", pady=1)
        tk.Button(cf, text="Перейти до координат", font=("Times New Roman", 10), command=self._goto_entries).grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.near = tk.Label(cf, text="", font=("Times New Roman", 10), fg="#333", justify="left", wraplength=290, anchor="w"); self.near.grid(row=3, column=0, columnspan=2, sticky="we", pady=(6, 0))
        tk.Label(right, text="Для NASA POWER точність до кількох кілометрів достатня: сітка даних ≈ 55 × 46 км. Координати можна ввести й вручну (градуси або ГМС).",
                 font=("Times New Roman", 9), fg="#666", wraplength=300, justify="left").pack(fill=tk.X, pady=8)
        bt = tk.Frame(right); bt.pack(side=tk.BOTTOM, fill=tk.X, pady=6)
        self.ok_btn = tk.Button(bt, text="✔ Обрати цю точку", bg="#1a6b1a", fg="white", font=("Times New Roman", 12), command=self._ok, state="disabled"); self.ok_btn.pack(fill=tk.X)
        tk.Button(bt, text="Скасувати", font=RF, command=self.win.destroy).pack(fill=tk.X, pady=(4, 0))
        self.win.update_idletasks()
        if lat is not None and lon is not None: self.win.after(60, lambda: self._set_point(lon, lat, center=True, z=7.0))
        else: self.win.after(60, self.map.fit_world)
        center_win(self.win); self.win.grab_set()

    # ── події ──
    def _lang(self): self.map.lang = self.lang_var.get(); self.map.redraw()

    def _hover(self, lon, lat):
        c = MapData.get().country_at(lon, lat) if self.map.z < 9 else ""
        self.hover.configure(text=f"{lat:.4f}° пн. ш., {lon:.4f}° сх. д." + (f"   ·   {c}" if c else ""))

    def _picked(self, lon, lat): self._set_point(lon, lat, center=False)

    def _set_point(self, lon, lat, center=False, z=None, label=""):
        self.lat, self.lon = float(lat), float(lon); self.label = label
        self.lat_v.set(f"{lat:.4f}"); self.lon_v.set(f"{lon:.4f}")
        self.map.set_marker(lon, lat, center=center, z=z)
        D = MapData.get(); nb = D.nearest(lon, lat); country = D.country_at(lon, lat)
        txt = (f"Країна: {country}\n" if country else "")
        if nb: txt += f"Найближче місто: {D.full_label(nb[0])} – {nb[1]:.0f} км"
        else: txt += "Найближче місто з довідника – далі 150 км"
        self.near.configure(text=txt); self.ok_btn.configure(state="normal")
        self._suggest = (D.label(nb[0], "uk") + (f", {D.z['places_country'][nb[0]]}" if str(D.z['places_country'][nb[0]]) else "")) if nb and nb[1] < 40 else ""

    def _search_pick(self, r):
        self._set_point(r["lon"], r["lat"], center=True, z=9.0 if r.get("pop", 0) < 5e5 else 8.0, label=r["label"])

    def _goto_entries(self):
        import sad_weather_core as W
        try: lat = W.parse_coord(self.lat_v.get(), "lat"); lon = W.parse_coord(self.lon_v.get(), "lon")
        except Exception as e: messagebox.showwarning("Координати", str(e), parent=self.win); return
        self._set_point(lon, lat, center=True, z=max(self.map.z, 7.0))

    def _ok(self):
        if self.lat is None: return
        self.result = {"lat": self.lat, "lon": self.lon, "label": self.label or getattr(self, "_suggest", "")}
        self.win.destroy()

    def show(self):
        self.win.wait_window(); return self.result
