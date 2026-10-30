#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Готує компактний файл вбудованої карти світу (sad_worldmap.npz) із відкритих даних Natural Earth (суспільне надбання,
https://www.naturalearthdata.com/about/terms-of-use/ – дозвіл і атрибуція не потрібні). Запуск – лише розробником,
щоб відтворити файл; програма користувача читає готовий npz (потрібен лише numpy).

  pip install shapely numpy
  python tools/build_worldmap_data.py  [тека_з_geojson]  [вихідний_файл]

Потрібні geojson (https://github.com/nvkelso/natural-earth-vector/tree/master/geojson):
  ne_10m_admin_0_countries, ne_10m_admin_1_states_provinces_lines, ne_10m_lakes, ne_10m_rivers_lake_centerlines,
  ne_10m_populated_places.
Рівні деталізації (LOD) – допуск спрощення Дугласа–Пекера, градусів: LOD0 0,12 (світ), LOD1 0,02 (регіон), LOD2 0,004 (детально).
"""
import json, os, sys
import numpy as np
from shapely.geometry import shape

SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ne"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sad_worldmap.npz")
TOL = {0: 0.12, 1: 0.02, 2: 0.004}
MIN_AREA = {0: 0.06, 1: 0.0006, 2: 0.0}            # відкидаємо дрібні острови на малих масштабах


def load(name): return json.load(open(os.path.join(SRC, name + ".geojson"), encoding="utf-8"))["features"]


class Layer:
    def __init__(self): self.xy, self.off, self.bb, self.ref, self.val = [], [0], [], [], []
    def add(self, coords, ref=0, val=0.0):
        a = np.asarray(coords, dtype=np.float64)[:, :2]
        if len(a) < 2: return
        self.xy.append(a.astype(np.float32)); self.off.append(self.off[-1] + len(a))
        self.bb.append([a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()]); self.ref.append(ref); self.val.append(val)
    def pack(self, d, key):
        d[key + "_xy"] = np.concatenate(self.xy).astype(np.float32) if self.xy else np.zeros((0, 2), np.float32)
        d[key + "_off"] = np.asarray(self.off, np.int32); d[key + "_bb"] = np.asarray(self.bb, np.float32).reshape(-1, 4)
        d[key + "_ref"] = np.asarray(self.ref, np.int32); d[key + "_val"] = np.asarray(self.val, np.float32)


def polys(geom):
    return list(geom.geoms) if geom.geom_type == "MultiPolygon" else ([geom] if geom.geom_type == "Polygon" else [])


def lines(geom):
    return list(geom.geoms) if geom.geom_type == "MultiLineString" else ([geom] if geom.geom_type == "LineString" else [])


def num(v, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default


def main():
    out = {}
    # ── країни: заливка суші й межі (зовнішні контури)
    feats = load("ne_10m_admin_0_countries")
    names = [f["properties"].get("NAME_UK") or f["properties"].get("NAME") or "" for f in feats]
    a3 = [f["properties"].get("ADM0_A3") or "" for f in feats]
    out["countries_names"] = np.array(names, dtype="U60"); out["countries_a3"] = np.array(a3, dtype="U4")
    lab_xy, lab_rank = [], []
    for lod in (0, 1, 2):
        L = Layer()
        for i, f in enumerate(feats):
            g = shape(f["geometry"])
            for p in polys(g):
                if p.area < MIN_AREA[lod]: continue
                s = p.simplify(TOL[lod], preserve_topology=True)
                if s.is_empty: continue
                for q in polys(s): L.add(list(q.exterior.coords), ref=i)
        L.pack(out, f"land{lod}")
    for f in feats:                                                  # підпис країни – у «репрезентативній точці» найбільшого полігона
        g = shape(f["geometry"]); big = max(polys(g), key=lambda p: p.area); pt = big.representative_point()
        lab_xy.append([pt.x, pt.y]); lab_rank.append(num(f["properties"].get("LABELRANK"), 6))
    out["countries_label_xy"] = np.asarray(lab_xy, np.float32); out["countries_label_rank"] = np.asarray(lab_rank, np.float32)
    # ── межі областей, озера, річки
    for key, fn, getg, lods in (("adm1", "ne_10m_admin_1_states_provinces_lines", lines, (1, 2)),
                                ("lake", "ne_10m_lakes", polys, (0, 1, 2)),
                                ("river", "ne_10m_rivers_lake_centerlines", lines, (1, 2))):
        fs = load(fn)
        for lod in lods:
            L = Layer()
            for f in fs:
                if not f.get("geometry"): continue
                g = shape(f["geometry"]); mz = num(f["properties"].get("min_zoom"), 0.0)
                for part in getg(g):
                    if key == "lake":
                        if part.area < MIN_AREA[lod] * 0.2: continue
                        s = part.simplify(TOL[lod], preserve_topology=True)
                        for q in polys(s): L.add(list(q.exterior.coords), val=mz)
                    else:
                        s = part.simplify(TOL[lod], preserve_topology=True)
                        if not s.is_empty: L.add(list(s.coords), val=mz)
            L.pack(out, f"{key}{lod}")
    # ── населені пункти
    ps = load("ne_10m_populated_places")
    iso = {a: n for a, n in zip(a3, names)}
    keep = [f for f in ps if f["geometry"]]
    col = lambda k, f=None: [(f["properties"].get(k) if f is None else f["properties"].get(k)) for f in keep]
    out["places_lonlat"] = np.asarray([f["geometry"]["coordinates"][:2] for f in keep], np.float32)
    out["places_pop"] = np.asarray([num(f["properties"].get("POP_MAX")) for f in keep], np.float32)
    out["places_minzoom"] = np.asarray([num(f["properties"].get("MIN_ZOOM"), 7.0) for f in keep], np.float32)
    for k, fld in (("uk", "NAME_UK"), ("en", "NAME_EN"), ("loc", "NAME"), ("ru", "NAME_RU"), ("adm1", "ADM1NAME")):
        out["places_" + k] = np.array([str(f["properties"].get(fld) or "") for f in keep], dtype="U60")
    out["places_country"] = np.array([iso.get(f["properties"].get("ADM0_A3") or "", f["properties"].get("ADM0NAME") or "") for f in keep], dtype="U60")
    np.savez_compressed(OUT, **out)
    print("записано", os.path.abspath(OUT), round(os.path.getsize(OUT) / 1e6, 2), "МБ")
    for lod in (0, 1, 2): print(f"  суша LOD{lod}: кілець {len(out[f'land{lod}_bb'])}, точок {len(out[f'land{lod}_xy'])}")
    for key in ("adm1", "lake", "river"):
        for lod in (0, 1, 2):
            if f"{key}{lod}_xy" in out: print(f"  {key} LOD{lod}: кілець {len(out[f'{key}{lod}_bb'])}, точок {len(out[f'{key}{lod}_xy'])}")
    print("  міст:", len(keep))


if __name__ == "__main__":
    main()
