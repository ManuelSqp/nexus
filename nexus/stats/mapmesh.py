"""3D maps from the game's files (4.48): the real walls, floors and boxes of a map, plain and one-coloured.

Input: the map's layout and meshes exported from the game (gamefiles.py, data/game/). Output, per map in
data/maps3d/:
  <map>.game.json      what the page needs besides the mesh: callout zones, the walkable grid (for walking and the
                       radar, from the game's navigation mesh), where to start, the frame, the version
  <map>.game.bin.gz    the mesh for the browser (binary, see pack()), the roof cut height map and a coarse
                       see-through grid
  <map>.game.vox.npz   the fine see-through grid for line of sight on the server (stats/sight.py)

What's left out on purpose: the vista around the map, effects, lights, sound volumes, decals, plants, cables and
other small clutter, and invisible volumes. What remains is merged and simplified (fast-simplification when it's
installed, else a coarser vertex grid) to a few hundred thousand triangles.

The frame is the one of the replay-built maps (map3d.py): metres on the minimap, x right, z down, y up. Heights are
the game's (world z / 100), so the floors are where the game has them; where the replays put players relative to
that (the capsule's centre or the feet) is measured from the replays when the map is built (foot_cm).

The exporter may mirror the world (FModel writes USD's right-handed frame: the game's Y negated). Which way round
the files are is checked against valorant-api.com's callout points and the replays: they must fall on the
walkable floor (detect_flip)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import re
import struct
import time
from pathlib import Path

import numpy as np

from .. import gamefiles as gf
from .map3d import CELL, LEVEL_GAP, Frame, area_kind

VERSION = 1
TARGET_TRIS = 260_000            # after simplifying
MIN_SIZE_CM = 80                 # objects smaller than this (their biggest side) are left out
VOX = 0.25                       # m, the server's see-through grid
VOX_WEB = 0.5                    # m, the browser's
HCELL = 1.0                      # m, the roof cut height map
ROOF = 3.4                       # m above the highest floor below: higher than this is cut away (roofs)
MARGIN_CM = (1200, 1200, 400, 1600)    # around the walkable area: x/y, below, above

SKIP_LAYERS = ("Vista", "Env_VFX", "VFX", "Lighting", "Audio", "Birthday", "Activations", "Camera", "Profiling",
               "Volumes", "KillVolumes", "BVPawn", "BVProjectile", "NavMesh", "Callout", "Mode_", "Lanes",
               "TeamSpawn", "ObserverCameras", "Esports")
CLUTTER = re.compile(r"(Foliage|Plant|Grass|Gravel|Ivy|Vine|Vino|Wire|Cable|Light|Lamp|Sconce|Trash|Plushie|Decal|"
                     r"Rainpipe|Pipe|Fish|Leaves|Leaf|Flower|Moss|Rope|Chain|Scaffold|Debris|Paper|Bottle|Cup|Book|"
                     r"Bird|Butterfl|Insect|Particle|Puddle|Cloud|Sky|Water_?Plane|Banner|Flag|Poster)", re.I)
TECH = re.compile(r"(TargetingMeshes|MapMarkup|/Utilities/|EditorShapes|EditorMeshes|NavMesh)", re.I)   # helpers, not walls
FLIPS = {"none": (1, 1), "y": (1, -1), "x": (-1, 1), "xy": (-1, -1)}


def codename(mi_name: str, map_url: str = "") -> str:
    if map_url:
        return map_url.rstrip("/").rsplit("/", 1)[-1]
    return gf.CODENAMES.get(mi_name, mi_name.replace(" ", ""))


def render_layer(layer: str) -> bool:
    return not any(k.lower() in layer.lower() for k in SKIP_LAYERS)


# ------------------------------------------------------------------------------------------------ reading a map
class Source:
    """A map's layout read once: the objects, the navigation mesh, the callout zones."""

    def __init__(self, files: gf.GameFiles, code: str):
        self.files, self.code = files, code
        self.layout = files.layout(code)
        self.placed: list[gf.Placed] = []
        self.signature = ""
        if self.layout is None:
            return
        sub, top = gf.read_layout(self.layout)
        self.placed += top
        sig = [str(self.layout.stat().st_mtime_ns)]
        for s in sub:
            f = (self.layout.parent / s)
            if f.is_file():
                self.placed += gf.read_layout(f)[1]
                sig.append(f"{f.name}:{f.stat().st_size}")
        self.signature = hashlib.sha1("|".join(sig).encode()).hexdigest()[:12]
        self._meshes: dict[Path, gf.Mesh | None] = {}

    def mesh(self, p: gf.Placed) -> gf.Mesh | None:
        f = self.files.resolve(p.ref, p.base)
        if f is None:
            return None
        if f not in self._meshes:
            self._meshes[f] = gf.read_mesh(f)
        return self._meshes[f]

    def nav(self) -> np.ndarray | None:
        """Triangles of the navigation (targeting) mesh in world cm, (n, 3, 3)."""
        out = []
        for p in self.placed:
            if "navmesh_targeting" in p.ref.lower().replace("navmesh_targetting", "navmesh_targeting"):
                m = self.mesh(p)
                if m is not None:
                    for M in p.mats:
                        out.append(_apply(m.points, M)[m.tris])
        return np.concatenate(out) if out else None

    def callout_boxes(self) -> list[dict]:
        """Callout zones: [{"name": "A_Link", "M": world matrix (4x4), "lo": box min, "hi": box max (box's own)}]"""
        out = []
        for p in self.placed:
            if "callout" not in p.layer.lower() or not p.ref.lower().endswith(".usda"):
                continue
            m = self.mesh(p)
            if m is None or not len(m.tris):
                continue
            lo, hi = m.points.min(0), m.points.max(0)
            for M in p.mats:
                out.append({"name": zone_name(p.name), "actor": p.name, "M": M, "lo": lo, "hi": hi})
        return out


def zone_name(actor: str) -> str:
    """The callout in an actor's name, the way the maps name them: CalloutRegion_A_Link, BP_CalloutRegion_ASite,
    AMain_CalloutRegion, BP_Callout_Defender_Spawn, InfinityCallout_AtkSpawn. '' for a numbered one
    (BP_CalloutRegion7: its name is only in the game's text, found by valorant-api.com's point inside it)."""
    s = re.sub(r"^BP_", "", actor)
    s = re.sub(r"_?Callout_?(Region|Volume)?s?\d*$", "", s)
    s = re.sub(r"^\w*?Callout_?(Region|Volume)?_?", "", s) if "callout" in s.lower() else s
    s = s.strip("_ ")
    return "" if re.fullmatch(r"\d*", s) else s


def _apply(points: np.ndarray, M: np.ndarray) -> np.ndarray:
    return points @ M[:3, :3].T + M[:3, 3]


# ------------------------------------------------------------------------------------------------ which way round
def detect_flip(nav_xy: np.ndarray, points: list[tuple[float, float]]) -> str:
    """nav_xy: (n, 3, 2) navigation triangles (cm, as in the files). points: world (x, y) where players are or that
    are named on the map. -> the flip of the files' axes ('none', 'y', 'x', 'xy') that puts most points on the
    walkable area (within 3 m). 'y' when nothing decides (FModel's usual)."""
    if nav_xy is None or not len(nav_xy) or not points:
        return "y"
    import cv2
    s = 50.0
    lo = nav_xy.reshape(-1, 2).min(0) - 1000
    hi = nav_xy.reshape(-1, 2).max(0) + 1000
    w, h = int((hi[0] - lo[0]) / s) + 1, int((hi[1] - lo[1]) / s) + 1
    if w * h > 40_000_000:
        return "y"
    occ = np.zeros((h, w), np.uint8)
    pts = ((nav_xy - lo) / s).astype(np.int32)
    for t in pts:
        cv2.fillConvexPoly(occ, t, 1)
    occ = cv2.dilate(occ, np.ones((13, 13), np.uint8))
    P = np.asarray(points, float)
    best, score = "y", -1
    for name, (fx, fy) in FLIPS.items():
        q = ((P * [fx, fy] - lo) / s).astype(int)                # files = world * flip (each flip is its own inverse)
        ok = (q[:, 0] >= 0) & (q[:, 0] < w) & (q[:, 1] >= 0) & (q[:, 1] < h)
        hits = int(occ[q[ok, 1], q[ok, 0]].sum())
        if hits > score or (hits == score and name == "y"):
            best, score = name, hits
    return best


# ------------------------------------------------------------------------------------------------ building
def build(files: gf.GameFiles, mi, code: str, samples: list[tuple[float, float, float]] | None = None,
          log=None) -> tuple[dict, bytes, dict] | None:
    """-> (meta, packed mesh for the browser, see-through grid for the server) or None (no layout).
    samples: world (x, y, z) positions of players from replays (to check the axes and measure the foot height)."""
    t0 = time.time()
    say = log or (lambda *_: None)
    src = Source(files, code)
    if src.layout is None:
        return None
    nav = src.nav()
    if nav is None or not len(nav):
        say(f"{code}: no navigation mesh in the export")
        return None
    pts = [(c.x, c.y) for c in getattr(mi, "callouts", [])] + [(x, y) for x, y, _z in (samples or [])[:4000]]
    flip = detect_flip(nav[:, :, :2], pts)
    fx, fy = FLIPS[flip]
    F = np.diag([fx, fy, 1.0, 1.0])                         # files -> world (and world -> files)
    nav_w = nav * [fx, fy, 1]
    lo = nav_w.reshape(-1, 3).min(0) - [MARGIN_CM[0], MARGIN_CM[1], MARGIN_CM[2]]
    hi = nav_w.reshape(-1, 3).max(0) + [MARGIN_CM[0], MARGIN_CM[1], MARGIN_CM[3]]
    say(f"{code}: layout {src.layout.name}, {len(src.placed)} objects, axes flipped: {flip}")

    # ---- the geometry, in world cm
    solid, glass = [], []
    n_obj = 0
    for p in src.placed:
        if p.invisible or not render_layer(p.layer) or CLUTTER.search(p.ref.rsplit("/", 1)[-1]) or TECH.search(p.ref):
            continue
        m = src.mesh(p)
        if m is None or not len(m.tris):
            continue
        ext = m.points.max(0) - m.points.min(0)
        for M in p.mats:
            W = F @ M
            size = ext * np.linalg.norm(W[:3, :3], axis=0)
            c = W[:3, 3]
            if size.max() < MIN_SIZE_CM or not ((c >= lo - 3000) & (c <= hi + 3000)).all():
                continue
            v = _apply(m.points, W)
            (glass if m.glass else solid).append((v, m.tris))
            n_obj += 1
    if not solid:
        say(f"{code}: no meshes found (is the Environment folder exported?)")
        return None
    V, T = _merge(solid)
    keep = _inside(V, T, lo, hi)
    V, T = _compact(V, T[keep])
    say(f"{code}: {n_obj} objects, {len(T):,} triangles before simplifying")

    fr = Frame(mi)
    Vm = _to_frame(V, mi, fr)
    navm = _to_frame(nav_w.reshape(-1, 3), mi, fr).reshape(-1, 3, 3)

    # ---- see-through grids (before simplifying: thin walls stay closed)
    vox = voxelize(Vm, T, VOX)
    say(f"{code}: see-through grid {vox['shape']}")

    # ---- simplify
    Vs, Ts = simplify(Vm, T, TARGET_TRIS)
    if glass:
        G, GT = _merge(glass)
        GT = GT[_inside(G, GT, lo, hi)]
        G, GT = _compact(G, GT)
        Gm, GT = simplify(_to_frame(G, mi, fr), GT, 40_000) if len(GT) else (np.zeros((0, 3)), np.zeros((0, 3), int))
    else:
        Gm, GT = np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    say(f"{code}: {len(Ts):,} triangles after simplifying")

    # ---- callout zones and the walkable grid
    zones = _zones(src, F, mi, fr)
    cells, floors = walk_cells(navm)
    hmap = roof_map(navm)
    area = _area_per_vertex(Vs, zones, mi, fr)
    foot = foot_cm(samples, floors, mi, fr) if samples else None
    callouts = _callout_points(mi, fr, floors, zones)
    if zones and cells:
        cc = np.array([[(c[0] + 0.5) * CELL, c[2] + 0.5, (c[1] + 0.5) * CELL] for c in cells])
        k = zone_index(zones, _frame_to_world(cc, mi, fr))
        for c, kk in zip(cells, k):
            c[3] = zones[kk]["kind"] if kk >= 0 else 0
    blob = pack(Vs, Ts, area, Gm, GT, hmap, coarse(vox, VOX_WEB))
    meta = {"version": VERSION, "map": mi.name, "code": code, "source": src.signature, "flip": flip,
            "cell": CELL, "cells": cells, "callouts": callouts, "zones": [_zone_public(z) for z in zones],
            "palette": [z["color"] for z in zones], "start": _start(zones, cells), "per_m": fr.per_m,
            "foot_cm": foot, "hand": int(np.sign(mi.x_mult) * np.sign(mi.y_mult)) or 1,
            "tris": int(len(Ts)), "objects": n_obj, "built": int(time.time()), "seconds": round(time.time() - t0, 1),
            "bytes": len(blob), "hash": hashlib.sha1(blob).hexdigest()[:12]}
    say(f"{code}: done in {meta['seconds']} s, {len(blob) / 1e6:.1f} MB")
    return meta, blob, vox


def _merge(parts):
    vs, ts, off = [], [], 0
    for v, t in parts:
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(ts)


def _inside(V, T, lo, hi):
    c = V[T].mean(1)
    return ((c >= lo) & (c <= hi)).all(1)


def _compact(V, T):
    if not len(T):
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    used, inv = np.unique(T, return_inverse=True)
    return V[used], inv.reshape(-1, 3)


def _to_frame(V, mi, fr) -> np.ndarray:
    """World cm (x, y, z) -> frame metres (x right, y up, z down on the minimap)."""
    u = V[:, 1] * mi.x_mult + mi.x_add
    v = V[:, 0] * mi.y_mult + mi.y_add
    return np.stack([u / fr.per_m, V[:, 2] / 100.0, v / fr.per_m], 1)


def simplify(V: np.ndarray, T: np.ndarray, target: int) -> tuple[np.ndarray, np.ndarray]:
    V, T = weld(V, T, 0.02)
    if len(T) <= target:
        return V, T
    try:
        import fast_simplification as fs
        v2, f2 = fs.simplify(V.astype(np.float32), T.astype(np.int32), target_reduction=1 - target / len(T))
        return np.asarray(v2, float), np.asarray(f2, np.int64)
    except Exception:
        pass
    g = 0.08
    while True:                                          # without the library: a coarser and coarser vertex grid
        v2, t2 = weld(V, T, g)
        if len(t2) <= target * 1.3 or g > 0.6:
            return v2, t2
        g *= 1.4


def weld(V, T, g):
    q = np.floor(V / g).astype(np.int64)
    q -= q.min(0)
    key = (q[:, 0] * (q[:, 1].max() + 1) + q[:, 1]) * (q[:, 2].max() + 1) + q[:, 2]
    _u, first, inv = np.unique(key, return_index=True, return_inverse=True)
    NT = inv.reshape(-1)[T]
    ok = (NT[:, 0] != NT[:, 1]) & (NT[:, 1] != NT[:, 2]) & (NT[:, 0] != NT[:, 2])
    NT = NT[ok]
    s = np.sort(NT, 1)
    _x, ui = np.unique(s, axis=0, return_index=True)
    NT = NT[np.sort(ui)]
    return _compact(V[first], NT)


# ------------------------------------------------------------------------------------------------ see-through grid
def voxelize(V: np.ndarray, T: np.ndarray, cell: float) -> dict:
    """Every cell a surface passes through is solid (points spread over every triangle, at most half a cell
    apart). -> {"origin": [x, y, z], "cell": m, "shape": [nx, ny, nz], "bits": packed bool (x fastest)}"""
    lo = V.min(0) - cell
    hi = V.max(0) + cell
    shape = np.ceil((hi - lo) / cell).astype(int) + 1
    grid = np.zeros(int(shape[0] * shape[1] * shape[2]), bool)
    step = cell * 0.45
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    longest = np.maximum(np.maximum(np.linalg.norm(B - A, axis=1), np.linalg.norm(C - B, axis=1)),
                         np.linalg.norm(A - C, axis=1))
    k = np.clip(np.ceil(longest / step).astype(int), 1, 400)
    for n in np.unique(k):
        sel = np.nonzero(k == n)[0]
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        m = (i + j) <= n
        a, b = (i[m] / n), (j[m] / n)                         # barycentric points on a triangle
        for s in range(0, len(sel), max(1, 2_000_000 // len(a))):
            idx = sel[s:s + max(1, 2_000_000 // len(a))]
            P = (A[idx, None, :] * (1 - a - b)[None, :, None] + B[idx, None, :] * a[None, :, None]
                 + C[idx, None, :] * b[None, :, None]).reshape(-1, 3)
            q = np.floor((P - lo) / cell).astype(np.int64)
            grid[q[:, 0] + shape[0] * (q[:, 2] + shape[2] * q[:, 1])] = True
    return {"origin": lo.tolist(), "cell": cell, "shape": shape.tolist(), "bits": np.packbits(grid)}


def vox_bool(vox: dict) -> np.ndarray:
    nx, ny, nz = vox["shape"]
    return np.unpackbits(vox["bits"])[: nx * ny * nz].astype(bool)


def coarse(vox: dict, cell: float) -> dict:
    f = int(round(cell / vox["cell"]))
    if f <= 1:
        return vox
    nx, ny, nz = vox["shape"]
    g = vox_bool(vox).reshape(ny, nz, nx)
    pad = [(0, (-s) % f) for s in g.shape]
    g = np.pad(g, pad)
    g = g.reshape(g.shape[0] // f, f, g.shape[1] // f, f, g.shape[2] // f, f).any(axis=(1, 3, 5))
    ny2, nz2, nx2 = g.shape
    return {"origin": vox["origin"], "cell": vox["cell"] * f, "shape": [nx2, ny2, nz2], "bits": np.packbits(g.reshape(-1))}


# ------------------------------------------------------------------------------------------------ floors
def walk_cells(navm: np.ndarray) -> tuple[list, dict]:
    """The navigation mesh on the half-metre grid: [[i, j, h, kind], ...] and {(i, j): [heights]}."""
    hs: dict[tuple[int, int], list[float]] = {}
    for tri in navm:
        xs, ys, zs = tri[:, 0], tri[:, 1], tri[:, 2]
        i0, i1 = int(math.floor(xs.min() / CELL)), int(math.floor(xs.max() / CELL))
        j0, j1 = int(math.floor(zs.min() / CELL)), int(math.floor(zs.max() / CELL))
        (x1, z1), (x2, z2), (x3, z3) = (xs[0], zs[0]), (xs[1], zs[1]), (xs[2], zs[2])
        det = (z2 - z3) * (x1 - x3) + (x3 - x2) * (z1 - z3)
        if abs(det) < 1e-9:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing="ij")
        px, pz = (ii + 0.5) * CELL, (jj + 0.5) * CELL
        l1 = ((z2 - z3) * (px - x3) + (x3 - x2) * (pz - z3)) / det
        l2 = ((z3 - z1) * (px - x3) + (x1 - x3) * (pz - z3)) / det
        l3 = 1 - l1 - l2
        e = -0.08
        inside = (l1 >= e) & (l2 >= e) & (l3 >= e)
        h = l1 * ys[0] + l2 * ys[1] + l3 * ys[2]
        for a, b, y in zip(ii[inside], jj[inside], h[inside]):
            hs.setdefault((int(a), int(b)), []).append(float(y))
    floors: dict[tuple[int, int], list[float]] = {}
    for k, v in hs.items():
        v.sort()
        lv = [v[0]]
        for y in v[1:]:
            if y - lv[-1] >= LEVEL_GAP:
                lv.append(y)
            else:
                lv[-1] = max(lv[-1], y)
        floors[k] = lv
    cells = [[i, j, round(h, 2), 0] for (i, j), lv in sorted(floors.items()) for h in lv]
    return cells, floors


def roof_map(navm: np.ndarray) -> dict:
    """Per square metre: the highest floor (with the floors around it spread outwards into buildings and walls).
    The browser hides what's more than ROOF above it, so the view from above shows the floors, not the roofs."""
    from scipy import ndimage
    P = navm.reshape(-1, 3)
    x0, z0 = math.floor(P[:, 0].min()) - 12, math.floor(P[:, 2].min()) - 12
    w = int(math.ceil(P[:, 0].max() - x0)) + 13
    h = int(math.ceil(P[:, 2].max() - z0)) + 13
    top = np.full((h, w), -np.inf)
    for tri in navm:
        for a in (0.0, 0.25, 0.5, 0.75):                  # corners, edges and inside, cheaply
            for b in (0.0, 0.25, 0.5, 0.75):
                if a + b > 1:
                    continue
                p = tri[0] * (1 - a - b) + tri[1] * a + tri[2] * b
                i, j = int(p[2] - z0), int(p[0] - x0)
                if 0 <= i < h and 0 <= j < w and p[1] > top[i, j]:
                    top[i, j] = p[1]
        c = tri.mean(0)
        i, j = int(c[2] - z0), int(c[0] - x0)
        if 0 <= i < h and 0 <= j < w and c[1] > top[i, j]:
            top[i, j] = c[1]
    known = np.isfinite(top)
    if not known.any():
        return {"x0": x0, "z0": z0, "w": w, "h": h, "cell": 1.0, "ymin": 0.0, "v": np.zeros((h, w), np.uint16)}
    fill = np.where(known, top, -1e6)
    for _ in range(10):                                   # spread 10 m into buildings and over walls
        grown = ndimage.maximum_filter(fill, size=3)
        fill = np.where(fill > -1e5, fill, grown)
    fill[fill < -1e5] = float(np.median(top[known]))
    ymin = float(fill.min()) - 1
    v = np.clip((fill - ymin) * 100, 0, 65535).astype(np.uint16)
    return {"x0": x0, "z0": z0, "w": w, "h": h, "cell": HCELL, "ymin": round(ymin, 2), "v": v}


def foot_cm(samples, floors: dict, mi, fr) -> float | None:
    """How far above the floor the replays put players (cm): the median over positions with a floor below."""
    d = []
    for x, y, z in samples[:20000]:
        u, v = mi.to_uv(x, y)
        i, j = int(math.floor(u / fr.per_m / CELL)), int(math.floor(v / fr.per_m / CELL))
        lv = floors.get((i, j))
        if not lv:
            continue
        zm = z / 100
        below = [h for h in lv if h <= zm + 0.3]
        if below and zm - max(below) < 2.5:
            d.append(zm - max(below))
    if len(d) < 50:
        return None
    return round(float(np.median(d)) * 100, 1)


# ------------------------------------------------------------------------------------------------ callout zones
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


_ZONE_COLORS = {1: (0.84, 0.66, 0.46), 2: (0.66, 0.74, 0.62), 3: (0.82, 0.60, 0.54), 4: (0.60, 0.66, 0.80),
                0: (0.74, 0.72, 0.68)}


def _zones(src: Source, F: np.ndarray, mi, fr) -> list[dict]:
    """The game's callout zones, named like valorant-api.com where the names match."""
    api = {}
    for c in getattr(mi, "callouts", []):
        api.setdefault(_norm(c.super_region + c.region), c)
        api.setdefault(_norm(c.label), c)
        if c.super_region in ("A", "B", "C"):
            api.setdefault(_norm(c.super_region + "site") if c.region == "Site" else "", c)
    out = []
    pts = [(c, np.array([c.x, c.y, 0.0])) for c in getattr(mi, "callouts", [])]
    groups: dict[str, list] = {}
    for b in src.callout_boxes():
        groups.setdefault(b["actor"], []).append(b)
    names = {}
    for actor, bs in groups.items():                         # one name per zone (all its boxes)
        name = bs[0]["name"]
        c = (api.get(_norm(name)) or api.get(_norm(name.replace("_", "")))) if name else None
        if c is None and pts:                                  # valorant-api.com's point inside the zone
            for cc, P in pts:
                if any(_in_box(F @ b["M"], b["lo"], b["hi"], P) for b in bs):
                    c = cc
                    break
        if c is None and not name and pts:                     # else the nearest point, if it's close
            ctr = np.mean([(F @ b["M"] @ np.append((b["lo"] + b["hi"]) / 2, 1))[:2] for b in bs], 0)
            d, cc = min(((float(np.hypot(*(P[:2] - ctr))), cc) for cc, P in pts), key=lambda a: a[0])
            c = cc if d < 1500 else None
        if c is None and not name:
            continue
        names[actor] = c
    for b in src.callout_boxes():
        if b["actor"] not in names:
            continue
        W = F @ b["M"]
        name = b["name"]
        c = names[b["actor"]]
        label = c.label if c else _pretty(name)
        kind = area_kind(c.super_region) if c else _kind_from_name(name)
        corners = np.array([[x, y, z] for x in (b["lo"][0], b["hi"][0]) for y in (b["lo"][1], b["hi"][1])
                            for z in (b["lo"][2], b["hi"][2])])
        wc = _apply(corners, W)
        fc = _to_frame(wc, mi, fr)
        out.append({"name": name, "label": label, "kind": kind, "W": W, "inv": np.linalg.inv(W), "lo": b["lo"],
                    "hi": b["hi"], "corners": fc, "ymin": float(fc[:, 1].min()), "ymax": float(fc[:, 1].max())})
    # one colour per zone: its area's colour, a little different from its neighbours
    for k, z in enumerate(out):
        base = _ZONE_COLORS.get(z["kind"], _ZONE_COLORS[0])
        f = 0.9 + 0.2 * ((k * 0.618) % 1)
        z["color"] = [round(min(1.0, c * f), 3) for c in base]
    return out


def _in_box(W, lo, hi, P) -> bool:
    """World point P (z ignored) inside a box placed with W (its own extent lo..hi)."""
    q = np.linalg.inv(W) @ np.array([P[0], P[1], W[2, 3], 1.0])
    return bool(lo[0] - 1 <= q[0] <= hi[0] + 1 and lo[1] - 1 <= q[1] <= hi[1] + 1)


def _pretty(name: str) -> str:
    s = name.replace("_", " ")
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"\b([ABC])(Site|Main|Link|Lobby|Short|Long)\b", r"\1 \2", s)
    s = re.sub(r"\bAtk\b", "Attacker", s)
    s = re.sub(r"\bDef\b", "Defender", s)
    return " ".join(s.split())


def _kind_from_name(name: str) -> int:
    n = name.lower().replace("_", "")
    if re.match(r"^(atk|attacker)", n):
        return 3
    if re.match(r"^(def|defender)", n):
        return 4
    if re.match(r"^[abc](_|site|main|lobby|link|short|long|$)", n):
        return 1
    if "mid" in n:
        return 2
    if "attacker" in n:
        return 3
    if "defender" in n:
        return 4
    return 0


def _frame_to_world(P: np.ndarray, mi, fr) -> np.ndarray:
    """Frame metres -> world cm (inverse of _to_frame)."""
    u, v = P[:, 0] * fr.per_m, P[:, 2] * fr.per_m
    y = (u - mi.x_add) / mi.x_mult
    x = (v - mi.y_add) / mi.y_mult
    return np.stack([x, y, P[:, 1] * 100], 1)


def zone_index(zones: list[dict], Pw: np.ndarray) -> np.ndarray:
    """World cm points -> index of the zone each is in (-1: none). Smaller zones win where zones overlap."""
    out = np.full(len(Pw), -1)
    size = [float(np.prod(z["hi"] - z["lo"])) for z in zones]
    for k in sorted(range(len(zones)), key=lambda k: -size[k]):
        z = zones[k]
        q = Pw @ z["inv"][:3, :3].T + z["inv"][:3, 3]
        ins = ((q >= z["lo"] - 1) & (q <= z["hi"] + 1)).all(1)
        out[ins] = k
    return out


def _area_per_vertex(Vs, zones, mi, fr) -> np.ndarray:
    if not zones or not len(Vs):
        return np.zeros(len(Vs), np.uint8)
    k = zone_index(zones, _frame_to_world(Vs, mi, fr))
    return np.clip(k + 1, 0, 255).astype(np.uint8)


def _zone_public(z: dict) -> dict:
    c = z["corners"]
    return {"label": z["label"], "kind": z["kind"], "x": round(float(c[:, 0].mean()), 2),
            "z": round(float(c[:, 2].mean()), 2), "y0": round(z["ymin"], 2), "y1": round(z["ymax"], 2),
            "poly": [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in _hull(c[:, [0, 2]])]}


def _hull(P):
    P = sorted(map(tuple, np.round(P, 3)))
    if len(P) <= 2:
        return P

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def _callout_points(mi, fr, floors, zones) -> list[dict]:
    """Labels for the page: one per zone at its middle, on the floor there."""
    out = []
    for z in zones:
        zp = _zone_public(z)
        i, j = int(math.floor(zp["x"] / CELL)), int(math.floor(zp["z"] / CELL))
        lv = None
        for r in range(0, 8):
            for di in range(-r, r + 1):
                for dj in range(-r, r + 1):
                    hs = floors.get((i + di, j + dj))
                    if hs:
                        inz = [h for h in hs if z["ymin"] - 0.5 <= h <= z["ymax"]]
                        lv = (inz or hs)[0]
                        break
                if lv is not None:
                    break
            if lv is not None:
                break
        out.append({"label": z["label"], "x": zp["x"], "z": zp["z"], "y": round(lv, 2) if lv is not None else None,
                    "kind": z["kind"]})
    return out


def _start(zones, cells) -> list[float]:
    sp = next((z for z in zones if "attacker" in z["name"].lower() and "spawn" in z["name"].lower()), None)
    if sp is not None:
        zp = _zone_public(sp)
        best = min(cells, key=lambda c: ((c[0] + 0.5) * CELL - zp["x"]) ** 2 + ((c[1] + 0.5) * CELL - zp["z"]) ** 2,
                   default=None)
        if best:
            return [round((best[0] + 0.5) * CELL, 2), best[2], round((best[1] + 0.5) * CELL, 2)]
    if not cells:
        return [0.0, 0.0, 0.0]
    xs = sorted(c[0] for c in cells)[len(cells) // 2]
    zs = sorted(c[1] for c in cells)[len(cells) // 2]
    c = min(cells, key=lambda c: (c[0] - xs) ** 2 + (c[1] - zs) ** 2)
    return [round((c[0] + 0.5) * CELL, 2), c[2], round((c[1] + 0.5) * CELL, 2)]


# ------------------------------------------------------------------------------------------------ the browser's file
def pack(V, T, area, G, GT, hmap, vox) -> bytes:
    """Little endian: b"NXM1", u32 header length, header JSON, then the sections it lists (each 4-byte aligned):
    pos   u16 x 3 per vertex, between lo and hi          area  u8 per vertex (zone + 1, 0 none)
    idx   u32 x 3 per triangle                            gpos/gidx  the same for glass
    roof  u16 per height map cell (cm above ymin)         vox   the coarse see-through grid, bits, x fastest"""
    allv = np.concatenate([V, G]) if len(G) else V
    lo = allv.min(0) - 0.01
    hi = allv.max(0) + 0.01
    q = lambda P: np.round((P - lo) / (hi - lo) * 65535).clip(0, 65535).astype("<u2")    # noqa: E731
    secs = [("pos", q(V).tobytes()), ("area", area.astype(np.uint8).tobytes()),
            ("idx", T.astype("<u4").tobytes()), ("gpos", q(G).tobytes() if len(G) else b""),
            ("gidx", GT.astype("<u4").tobytes() if len(GT) else b""), ("roof", hmap["v"].astype("<u2").tobytes()),
            ("vox", vox["bits"].tobytes())]
    head = {"nv": int(len(V)), "nt": int(len(T)), "gnv": int(len(G)), "gnt": int(len(GT)),
            "lo": [round(float(x), 4) for x in lo], "hi": [round(float(x), 4) for x in hi],
            "roof": {k: hmap[k] for k in ("x0", "z0", "w", "h", "cell", "ymin")},
            "vox": {"origin": [round(float(x), 4) for x in vox["origin"]], "cell": vox["cell"], "shape": vox["shape"]},
            "sections": {}}
    body = io.BytesIO()
    for name, data in secs:
        head["sections"][name] = [body.tell(), len(data)]
        body.write(data)
        body.write(b"\0" * ((-len(data)) % 4))
    hj = json.dumps(head, separators=(",", ":")).encode()
    hj += b" " * ((-len(hj)) % 4)
    return b"NXM1" + struct.pack("<I", len(hj)) + hj + body.getvalue()


def unpack_head(blob: bytes) -> dict:
    n = struct.unpack("<I", blob[4:8])[0]
    return json.loads(blob[8:8 + n])


# ------------------------------------------------------------------------------------------------ files on disk
def paths(out_dir: Path, name: str) -> dict[str, Path]:
    b = Path(out_dir) / name.lower().replace(" ", "")
    return {"meta": b.with_name(b.name + ".game.json"), "bin": b.with_name(b.name + ".game.bin.gz"),
            "vox": b.with_name(b.name + ".game.vox.npz")}


def save(out_dir: Path, name: str, meta: dict, blob: bytes, vox: dict) -> None:
    p = paths(out_dir, name)
    p["meta"].parent.mkdir(parents=True, exist_ok=True)
    tmp = p["bin"].with_suffix(".tmp")
    with gzip.open(tmp, "wb", compresslevel=6) as fh:
        fh.write(blob)
    tmp.replace(p["bin"])
    tmp = p["vox"].with_name(p["vox"].name + ".tmp.npz")
    np.savez_compressed(tmp, bits=vox["bits"], origin=np.array(vox["origin"]), cell=np.array(vox["cell"]),
                        shape=np.array(vox["shape"]))
    tmp.replace(p["vox"])
    tmp = p["meta"].with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, separators=(",", ":")))
    tmp.replace(p["meta"])


def load_meta(out_dir: Path, name: str) -> dict | None:
    try:
        d = json.loads(paths(out_dir, name)["meta"].read_text())
    except (OSError, ValueError):
        return None
    return d if d.get("version") == VERSION else None


def load_vox(out_dir: Path, name: str) -> dict | None:
    try:
        with np.load(paths(out_dir, name)["vox"]) as z:
            return {"bits": z["bits"], "origin": z["origin"].tolist(), "cell": float(z["cell"]),
                    "shape": [int(x) for x in z["shape"]]}
    except (OSError, ValueError, KeyError):
        return None
