"""3D maps from the game's files (4.48): the real walls, floors and boxes of a map, plain and one-coloured.

Input: the map's layout and meshes exported from the game (gamefiles.py, data/game/). Output, per map in
data/maps3d/:
  <map>.game.json      what the page needs besides the mesh: callout zones, the walkable grid (for walking and the
                       radar: the game's navigation mesh, and 4.53 the floors of the geometry itself near it: box
                       tops, bridges, ledges), where to start, the frame, the version
  <map>.game.bin.gz    the mesh for the browser (binary, see pack()), the roof cut height map and a coarse
                       see-through grid
  <map>.game.vox.npz   the fine see-through grid for line of sight on the server (stats/sight.py)

What's left out on purpose: the vista around the map, effects, lights, sound volumes, decals, plants, cables and
other small clutter, and invisible volumes. What remains is merged and simplified (fast-simplification when it's
installed, else a coarser vertex grid) to a few hundred thousand triangles.

The frame is the one of the replay-built maps (map3d.py): metres on the minimap, x right, z down, y up. Heights are
the game's (world z / 100), so the floors are where the game has them; where the replays put players relative to
that (the capsule's centre or the feet) is measured when a replay is shown (replayview.py).

The exporter may mirror the world (FModel writes USD's right-handed frame: the game's Y negated). Which way round
the files are is checked against valorant-api.com's callout points: they must fall on the walkable floor
(detect_flip)."""
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

VERSION = 6                      # 6 (4.53): floors from the geometry too, nothing from replays; 5 (4.50.2): doors that are open in the game see-through; 4 (4.49): glass per face; 3 (4.48.2): gentler simplifying (no shards); 2 (4.48.1): objects one by one, lids
TARGET_TRIS = 450_000            # after simplifying (a soft target: see per_object)
MIN_KEEP = 0.35                  # a simplified object keeps at least this share of its triangles
SIMPLIFY_MIN = 300               # objects with fewer triangles aren't simplified
BIG_CM = 600                     # objects bigger than this (their own size) aren't simplified
MIN_SIZE_CM = 80                 # objects smaller than this (their biggest side) are left out
VOX = 0.25                       # m, the server's see-through grid
VOX_WEB = 0.5                    # m, the browser's
HCELL = 1.0                      # m, the roof cut height map
ROOF = 3.4                       # m above the highest floor below: higher than this is cut away (roofs)
UP_SLOPE = 50                    # degrees: a surface at most this steep is a floor (4.53)
CLEAR_FROM, HEADROOM = 0.35, 1.5   # m above a floor: nothing solid in between, or it's not one (a crouching player)
NAV_CLEAR_FROM = 0.65            # the same for the navigation mesh's floors (it runs below the steps of stairs)
ENCLOSED_M, BOX_TOP_M = 1.5, 4.0   # inside a big box: its sides this close all round, its top at most this high
NEAR_NAV_M = 3.0                 # the geometry's floors count this close to the navigation mesh (box tops, bridges)
CLIMB = 1.3                      # m a player gets up onto from the floor beside it (a step, or jumping onto a box)
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
        self._parts: dict[int, tuple] = {}

    def mesh(self, p: gf.Placed) -> gf.Mesh | None:
        f = self.files.resolve(p.ref, p.base)
        if f is None:
            return None
        if f not in self._meshes:
            self._meshes[f] = gf.read_mesh(f)
        return self._meshes[f]

    def parts(self, m: gf.Mesh):
        """A mesh without its glass, and its glass (each made once)."""
        hit = self._parts.get(id(m))
        if hit is None:
            hit = self._parts[id(m)] = m.split()
        return hit

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
def build(files: gf.GameFiles, mi, code: str, log=None) -> tuple[dict, bytes, dict] | None:
    """-> (meta, packed mesh for the browser, see-through grid for the server) or None (no layout).
    4.53: from the game's files alone (and valorant-api.com's callouts for the axes): no replays. Where replays put
    the feet is measured when a replay is shown (replayview.py)."""
    t0 = time.time()
    say = log or (lambda *_: None)
    src = Source(files, code)
    if src.layout is None:
        return None
    nav = src.nav()
    if nav is None or not len(nav):
        say(f"{code}: no navigation mesh in the export")
        return None
    pts = [(c.x, c.y) for c in getattr(mi, "callouts", [])]
    flip = detect_flip(nav[:, :, :2], pts)
    fx, fy = FLIPS[flip]
    F = np.diag([fx, fy, 1.0, 1.0])                         # files -> world (and world -> files)
    nav_w = nav * [fx, fy, 1]
    lo = nav_w.reshape(-1, 3).min(0) - [MARGIN_CM[0], MARGIN_CM[1], MARGIN_CM[2]]
    hi = nav_w.reshape(-1, 3).max(0) + [MARGIN_CM[0], MARGIN_CM[1], MARGIN_CM[3]]
    say(f"{code}: layout {src.layout.name}, {len(src.placed)} objects, axes flipped: {flip}")

    # ---- the geometry, in world cm: which objects, and how many triangles they'd be
    solid, glass = [], []                                 # (mesh, its file, world matrix)
    doors, n_doors = Doorways(nav_w), 0
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
            if doors.is_open(m, W):                         # 4.50.2: drawn like glass, don't block the view
                glass.append((m, id(m), W))
                n_doors += 1
                continue
            sm, gm = src.parts(m)
            if sm is not None:
                solid.append((sm, id(sm), W))
            if gm is not None:
                glass.append((gm, id(gm), W))
    if not solid:
        say(f"{code}: no meshes found (is the Environment folder exported?)")
        return None
    n_obj = len(solid) + len(glass)
    if n_doors:
        say(f"{code}: {n_doors} doors open in the game (drawn see-through)")
    fr = Frame(mi)
    navm = _to_frame(nav_w.reshape(-1, 3), mi, fr).reshape(-1, 3, 3)

    # ---- see-through grid from the full geometry (thin walls stay closed)
    V, T = _place(solid, lo, hi, mi, fr)
    say(f"{code}: {n_obj} objects, {len(T):,} triangles before simplifying")
    vox = voxelize(V, T, VOX)
    say(f"{code}: see-through grid {vox['shape']}")
    geo = geo_floors(V, T, vox)                          # 4.53: box tops, bridges, ledges (full detail)
    del V, T

    # ---- simplify each object on its own (simplifying the whole map at once tears holes into floors where
    # separate objects meet), as much as needed to stay near TARGET_TRIS
    Vs, Ts = _place(solid, lo, hi, mi, fr, simple=per_object(solid, TARGET_TRIS))
    Vs, Ts = weld(Vs, Ts, 0.005)
    if glass:
        Gm, GT = _place(glass, lo, hi, mi, fr, simple=per_object(glass, 40_000))
    else:
        Gm, GT = np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    say(f"{code}: {len(Ts):,} triangles after simplifying")

    # ---- callout zones and the walkable grid
    zones = _zones(src, F, mi, fr)
    _, nav_floors = walk_cells(navm)
    nav_in = sum(len(v) for v in nav_floors.values())
    nav_floors = inside_objects(nav_floors, vox)
    say(f"{code}: {nav_in - sum(len(v) for v in nav_floors.values()):,} navigation mesh cells inside objects left out")
    cells, floors, added = merge_floors(nav_floors, geo)
    say(f"{code}: walkable: {len(cells):,} cells, {added:,} of them from the geometry (box tops, bridges)")
    hmap = roof_map(floors, vox)
    area = _area_per_vertex(Vs, zones, mi, fr)
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
            "foot_cm": None, "geo_cells": added, "hand": int(np.sign(mi.x_mult) * np.sign(mi.y_mult)) or 1,
            "tris": int(len(Ts)), "objects": n_obj, "built": int(time.time()), "seconds": round(time.time() - t0, 1),
            "bytes": len(blob), "hash": hashlib.sha1(blob).hexdigest()[:12]}
    say(f"{code}: done in {meta['seconds']} s, {len(blob) / 1e6:.1f} MB")
    return meta, blob, vox


class Doorways:
    """4.50.2: doors that stand in a passage. The layouts have the game's doors in their closed place, but most are
    open when a round starts (Ascent's and Sunset's mechanical doors, Breeze's and Fracture's, Bind's teleporter
    doors, Abyss's breakable ones), and players walk through them. Found by their shape and the navigation mesh: a
    slab standing on the floor (thin, at least a person's height) whose middle and both sides are walkable."""
    MIN_H, MAX_H = 150, 700          # cm
    MAX_THICK = 30
    MIN_W, MAX_W = 70, 650
    SIDE = 70                         # how far in front of and behind it the floor is checked
    ZTOL = 40

    def __init__(self, nav_w: np.ndarray):
        A, B, C = nav_w[:, 0], nav_w[:, 1], nav_w[:, 2]
        v0, v1 = C[:, :2] - A[:, :2], B[:, :2] - A[:, :2]
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1.0                            # upright and broken triangles cover no floor
        self.A, self.B, self.C = A[ok], B[ok], C[ok]
        self.v0, self.v1, self.d00, self.d01, self.d11, self.den = v0[ok], v1[ok], d00[ok], d01[ok], d11[ok], den[ok]

    def walkable(self, p: np.ndarray, z0: float) -> bool:
        """Is there walkable floor at p (x, y) within ZTOL of height z0?"""
        if not len(self.A):
            return False
        v2 = p[None, :2] - self.A[:, :2]
        d20, d21 = (v2 * self.v0).sum(1), (v2 * self.v1).sum(1)
        u = (self.d11 * d20 - self.d01 * d21) / self.den
        v = (self.d00 * d21 - self.d01 * d20) / self.den
        inside = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6)
        z = self.A[:, 2] + u * (self.C[:, 2] - self.A[:, 2]) + v * (self.B[:, 2] - self.A[:, 2])
        return bool((inside & (np.abs(z - z0) <= self.ZTOL)).any())

    def is_open(self, m: gf.Mesh, W: np.ndarray) -> bool:
        lo, hi = m.points.min(0), m.points.max(0)
        R = W[:3, :3]
        ax = np.linalg.norm(R, axis=0)
        size = (hi - lo) * ax
        dirs = R / np.where(ax > 0, ax, 1)
        up = int(np.argmax(np.abs(dirs[2])))
        if abs(dirs[2, up]) < 0.9:
            return False
        th, wi = sorted((i for i in range(3) if i != up), key=lambda i: size[i])
        if not (self.MIN_H <= size[up] <= self.MAX_H and size[th] <= self.MAX_THICK and self.MIN_W <= size[wi] <= self.MAX_W):
            return False
        c = (W @ np.r_[(lo + hi) / 2, 1.0])[:3]
        base = c[2] - size[up] / 2
        along = sum(self.walkable(c + dirs[:, wi] * f * size[wi], base) for f in (-0.15, 0.0, 0.15))
        if along < 2 or not all(self.walkable(c + dirs[:, th] * s * self.SIDE, base) for s in (-1, 1)):
            return False
        # it fills its own middle (a door frame doesn't: the passage goes through it anyway)
        P2 = m.points[:, [wi, up]]
        mid = ((lo + hi) / 2)[[wi, up]]
        a, b, cc = P2[m.tris[:, 0]], P2[m.tris[:, 1]], P2[m.tris[:, 2]]

        def side(p1, p2):
            return (p1[:, 0] - mid[0]) * (p2[:, 1] - mid[1]) - (p2[:, 0] - mid[0]) * (p1[:, 1] - mid[1])
        s1, s2, s3 = side(a, b), side(b, cc), side(cc, a)
        neg, pos = (s1 < 0) | (s2 < 0) | (s3 < 0), (s1 > 0) | (s2 > 0) | (s3 > 0)
        return bool((~(neg & pos)).any())


def per_object(items, target: int) -> dict:
    """Each mesh simplified once (it's placed many times): the same share of triangles kept for every mesh with
    more than a few, chosen so the whole map lands near target. -> {id(mesh): (points, triangles)}"""
    uses: dict[int, list] = {}
    for m, key, _W in items:
        uses.setdefault(key, [m, 0])[1] += 1
    total = sum(len(m.tris) * n for m, n in uses.values())
    out: dict[int, tuple] = {}
    if total <= target:
        return out
    # big pieces (floors, walls, buildings: more than BIG_CM across) stay as they are: simplified, open surfaces
    # shrink at their edges and leave gaps. The props and details take the cut.
    # Detailed props keep at least MIN_KEEP of their triangles (cut harder, they turn into spiky shards); small
    # ones aren't touched. So a busy map ends up above target rather than torn.
    fixed = lambda m: len(m.tris) <= SIMPLIFY_MIN or (m.points.max(0) - m.points.min(0)).max() > BIG_CM   # noqa: E731
    small = sum(len(m.tris) * n for m, n in uses.values() if fixed(m))
    ratio = min(1.0, max(MIN_KEEP, (target - small) / max(1, total - small)))
    for key, (m, _n) in uses.items():
        if fixed(m):
            continue
        keep = max(SIMPLIFY_MIN, int(len(m.tris) * ratio))
        if keep >= len(m.tris):
            continue
        out[key] = _simplify_one(m.points, m.tris, keep)
    return out


def _simplify_one(P, T, keep):
    P, T = weld(P, T, 0.5)                                 # cm: one object, its seams closed
    if len(T) <= keep:
        return P, T
    try:
        import fast_simplification as fs
        v2, f2 = fs.simplify(P.astype(np.float32), T.astype(np.int32), target_reduction=1 - keep / len(T))
        if len(f2):
            return np.asarray(v2, float), np.asarray(f2, np.int64)
    except Exception:
        pass
    return P, T


def _place(items, lo, hi, mi, fr, simple: dict | None = None):
    """The objects at their places, in the frame (metres): (vertices, triangles)."""
    vs, ts, off = [], [], 0
    for m, key, W in items:
        P, T = (simple or {}).get(key, (m.points, m.tris))
        v = _apply(P, W)
        c = v[T].mean(1)
        k = ((c >= lo) & (c <= hi)).all(1)
        if not k.any():
            continue
        vs.append(v)
        ts.append(T[k] + off)
        off += len(v)
    if not vs:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64)
    V, T = _compact(np.concatenate(vs), np.concatenate(ts))
    return _to_frame(V, mi, fr), T


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


def geo_floors(V: np.ndarray, T: np.ndarray, vox: dict, cell: float = CELL) -> dict[tuple[int, int], list[float]]:
    """4.53: the floors of the geometry itself, on the half-metre grid: every surface facing up (at most UP_SLOPE
    steep) at a cell's centre, with room for a crouching player above it (nothing solid in the see-through grid from
    just above the surface up to HEADROOM). Box tops, bridges, ledges: the navigation mesh leaves many of them out.
    -> {(i, j): [heights]}"""
    if not len(T):
        return {}
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    n = np.cross(B - A, C - A)
    ln = np.linalg.norm(n, axis=1)
    up = np.where(ln > 0, n[:, 1] / np.where(ln > 0, ln, 1), 0)
    keep = np.abs(up) >= math.cos(math.radians(UP_SLOPE))          # either winding: meshes aren't all the same way
    A, B, C = A[keep], B[keep], C[keep]
    xs = np.stack([A[:, 0], B[:, 0], C[:, 0]], 1)
    zs = np.stack([A[:, 2], B[:, 2], C[:, 2]], 1)
    i0 = np.floor(xs.min(1) / cell - 0.5).astype(np.int64) + 1          # first centre at or right of the left edge
    i1 = np.floor(xs.max(1) / cell - 0.5).astype(np.int64)
    j0 = np.floor(zs.min(1) / cell - 0.5).astype(np.int64) + 1
    j1 = np.floor(zs.max(1) / cell - 0.5).astype(np.int64)
    ni, nj = i1 - i0 + 1, j1 - j0 + 1
    ok = (ni > 0) & (nj > 0) & (ni <= 400) & (nj <= 400)
    out_i, out_j, out_h = [], [], []
    for a, b in set(zip(ni[ok].tolist(), nj[ok].tolist())):       # triangles by how many centres their box holds
        sel = np.nonzero(ok & (ni == a) & (nj == b))[0]
        di, dj = np.meshgrid(np.arange(a), np.arange(b), indexing="ij")
        di, dj = di.reshape(-1), dj.reshape(-1)
        chunk = max(1, 2_000_000 // len(di))
        for s in range(0, len(sel), chunk):
            idx = sel[s:s + chunk]
            ii = i0[idx, None] + di[None, :]
            jj = j0[idx, None] + dj[None, :]
            px, pz = (ii + 0.5) * cell, (jj + 0.5) * cell
            x1, x2, x3 = xs[idx, 0, None], xs[idx, 1, None], xs[idx, 2, None]
            z1, z2, z3 = zs[idx, 0, None], zs[idx, 1, None], zs[idx, 2, None]
            det = (z2 - z3) * (x1 - x3) + (x3 - x2) * (z1 - z3)
            det = np.where(np.abs(det) < 1e-12, np.nan, det)
            l1 = ((z2 - z3) * (px - x3) + (x3 - x2) * (pz - z3)) / det
            l2 = ((z3 - z1) * (px - x3) + (x1 - x3) * (pz - z3)) / det
            l3 = 1 - l1 - l2
            inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
            h = l1 * A[idx, 1, None] + l2 * B[idx, 1, None] + l3 * C[idx, 1, None]
            out_i.append(ii[inside])
            out_j.append(jj[inside])
            out_h.append(h[inside])
    if not out_i:
        return {}
    I, J, H = np.concatenate(out_i), np.concatenate(out_j), np.concatenate(out_h)
    free = headroom(I, J, H, vox, cell)
    floors: dict[tuple[int, int], list[float]] = {}
    for a, b, y in zip(I[free].tolist(), J[free].tolist(), H[free].tolist()):
        floors.setdefault((a, b), []).append(y)
    for k, v in floors.items():
        floors[k] = _group_levels(v)
    return floors


def headroom(I: np.ndarray, J: np.ndarray, H: np.ndarray, vox: dict, cell: float = CELL,
             dx: float = 0.0, dz: float = 0.0, start: float = CLEAR_FROM) -> np.ndarray:
    """Per floor (cell i, j at height h): room for a crouching player above it? (nothing solid in the see-through
    grid from start to HEADROOM above it, at the cell's centre moved by dx, dz)"""
    nx, ny, nz = vox["shape"]
    g = vox_bool(vox).reshape(ny, nz, nx)
    ox, oy, oz = vox["origin"]
    vc = vox["cell"]
    ix = np.floor(((I + 0.5) * cell + dx - ox) / vc).astype(np.int64)
    iz = np.floor(((J + 0.5) * cell + dz - oz) / vc).astype(np.int64)
    inb = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)          # outside the grid there's nothing solid
    free = np.ones(len(I), bool)
    lo_y = np.floor((H + start - oy) / vc).astype(np.int64)
    hi_y = np.floor((H + HEADROOM - oy) / vc).astype(np.int64)
    for k in range(int(math.ceil((HEADROOM - start) / vc)) + 1):
        y = lo_y + k
        chk = free & inb & (y <= hi_y) & (y >= 0) & (y < ny)
        hit = np.zeros_like(free)
        hit[chk] = g[y[chk], iz[chk], ix[chk]]
        free &= ~hit
    return free


def inside_objects(floors: dict, vox: dict) -> dict:
    """The navigation mesh's floors without the ones inside something solid (it runs under some boxes, which made
    them walk-through): no room above at the centre and around it. A wall only beside the centre (the cells along
    the walls) doesn't count, nor what's less than NAV_CLEAR_FROM above (stairs: the mesh runs below the steps)."""
    items = [(i, j, h) for (i, j), hs in floors.items() for h in hs]
    if not items:
        return {}
    a = np.array(items)
    I, J, H = a[:, 0].astype(np.int64), a[:, 1].astype(np.int64), a[:, 2]
    d = CELL * 0.4
    n_free = sum(headroom(I, J, H, vox, dx=x, dz=z, start=NAV_CLEAR_FROM).astype(int)
                 for x, z in ((0, 0), (d, 0), (-d, 0), (0, d), (0, -d)))
    free = (n_free >= 2) & ~enclosed(I, J, H, vox)
    out: dict[tuple[int, int], list[float]] = {}
    for (i, j, h), ok in zip(items, free.tolist()):
        if ok:
            out.setdefault((i, j), []).append(h)
    return out


def enclosed(I: np.ndarray, J: np.ndarray, H: np.ndarray, vox: dict, cell: float = CELL) -> np.ndarray:
    """Per floor: inside a big box? (the see-through grid has only an object's surfaces: a box taller than HEADROOM
    is empty inside.) Its sides close to the centre all round, at knee height, within ENCLOSED_M, and a lid above
    within BOX_TOP_M."""
    nx, ny, nz = vox["shape"]
    g = vox_bool(vox).reshape(ny, nz, nx)
    ox, oy, oz = vox["origin"]
    vc = vox["cell"]
    ix = np.floor(((I + 0.5) * cell - ox) / vc).astype(np.int64)
    iz = np.floor(((J + 0.5) * cell - oz) / vc).astype(np.int64)

    def solid(x, y, z):
        ok = (x >= 0) & (x < nx) & (y >= 0) & (y < ny) & (z >= 0) & (z < nz)
        out = np.zeros(len(x), bool)
        out[ok] = g[y[ok], z[ok], x[ok]]
        return out
    knee = np.floor((H + 0.8 - oy) / vc).astype(np.int64)
    n = int(math.ceil(ENCLOSED_M / vc))
    shut = np.ones(len(I), bool)
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        hit = np.zeros(len(I), bool)
        for k in range(1, n + 1):
            hit |= solid(ix + dx * k, knee, iz + dz * k)
        shut &= hit
    lid = np.zeros(len(I), bool)
    for k in range(int(math.ceil((BOX_TOP_M - NAV_CLEAR_FROM) / vc)) + 1):
        lid |= solid(ix, np.floor((H + NAV_CLEAR_FROM - oy) / vc).astype(np.int64) + k, iz)
    return shut & lid


def _group_levels(v: list[float]) -> list[float]:
    """Heights in one cell -> its floors: closer than LEVEL_GAP is one floor (the higher one)."""
    v = sorted(v)
    lv = [v[0]]
    for y in v[1:]:
        if y - lv[-1] >= LEVEL_GAP:
            lv.append(y)
        else:
            lv[-1] = max(lv[-1], y)
    return lv


def merge_floors(nav: dict, geo: dict, near_m: float = NEAR_NAV_M) -> tuple[list, dict, int]:
    """The walkable floors: the navigation mesh's, and the geometry's that a player can get onto from them (each step
    at most CLIMB up, jumping included: a box top, a bridge up its stairs; not a roof, not the top of a wall), no
    further than near_m from the navigation mesh and not a strip a player can't stand on (railings, wall tops).
    Where both have a floor at about the same height, the geometry's height counts (the navigation mesh floats a bit
    above it). -> (cells [[i, j, h, 0], ...], floors {(i, j): [heights]}, how many floors the geometry added)"""
    from collections import deque

    from scipy import ndimage
    if not nav:
        return [], {}, 0
    keys = np.array(list(nav.keys()) + list(geo.keys()))
    i_lo, j_lo = keys.min(0)
    i_hi, j_hi = keys.max(0)
    m = np.zeros((int(i_hi - i_lo + 1), int(j_hi - j_lo + 1)), bool)
    for (i, j) in nav:
        m[i - i_lo, j - j_lo] = True
    r = int(round(near_m / CELL))
    yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
    near = ndimage.binary_dilation(m, structure=(xx * xx + yy * yy) <= r * r)

    def same(a, b, h):
        return any(abs(x - h) <= 0.45 for x in geo.get((a, b), ()))     # a step of a stair counts

    cand: dict[tuple[int, int], list[float]] = {}
    for (i, j), hs in geo.items():
        if not near[i - i_lo, j - j_lo]:
            continue
        for h in hs:                     # not a strip: a neighbour at the same height across x and one across z
            if (same(i - 1, j, h) or same(i + 1, j, h)) and (same(i, j - 1, h) or same(i, j + 1, h)):
                cand.setdefault((i, j), []).append(h)
    # from the navigation mesh's floors onto the geometry's: one cell at a time, up at most CLIMB, down any height
    seen: set[tuple[int, int, float]] = set()
    todo = deque((i, j, h) for (i, j), hs in nav.items() for h in hs)
    while todo:
        i, j, h = todo.popleft()
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            for h2 in cand.get((a, b), ()):
                if h2 - h <= CLIMB and (a, b, h2) not in seen:
                    seen.add((a, b, h2))
                    todo.append((a, b, h2))
    out = {k: list(v) for k, v in nav.items()}
    added = 0
    for (i, j, h) in seen:
        lv = out.setdefault((i, j), [])
        close = [x for x in lv if abs(x - h) < LEVEL_GAP]
        if close:                                          # the same floor: the geometry's height
            for x in close:
                lv.remove(x)
            lv.append(h if all(abs(x - h) <= 0.5 for x in close) else max(close + [h]))
        else:
            lv.append(h)
            added += 1
        lv.sort()
    cells = [[i, j, round(h, 2), 0] for (i, j), lv in sorted(out.items()) for h in lv]
    return cells, out, added


def roof_map(floors: dict, vox: dict | None = None) -> dict:
    """Per square metre: the highest floor of the navigation mesh (where there's none, inside buildings and behind
    walls, the floors around spread outwards 10 m). The browser hides what's more than ROOF above it, so the view
    from above shows the floors, and covers the closed-off spots where something was cut away (a building) with a
    dark lid at the cut, like the blocks on the minimap.
    v: u16 cm above ymin; the lowest bit 1 = walkable, the next bit 1 = lid."""
    from scipy import ndimage
    if not floors:
        return {"x0": 0, "z0": 0, "w": 1, "h": 1, "cell": HCELL, "ymin": 0.0, "v": np.zeros((1, 1), np.uint16)}
    k = int(round(HCELL / CELL))
    ij = np.array(list(floors.keys()))
    top_h = np.array([max(v) for v in floors.values()])
    ci, cj = np.floor_divide(ij[:, 0], k), np.floor_divide(ij[:, 1], k)    # 1 m cells: x -> column, z -> row
    x0, z0 = int(ci.min()) - 12, int(cj.min()) - 12
    w, h = int(ci.max()) - x0 + 13, int(cj.max()) - z0 + 13
    top = np.full((h, w), -np.inf)
    np.maximum.at(top, (cj - z0, ci - x0), top_h)
    known = np.isfinite(top)
    fill = np.where(known, top, -1e6)
    for _ in range(10):                                   # spread 10 m into buildings and over walls
        grown = ndimage.maximum_filter(fill, size=3)
        fill = np.where(fill > -1e5, fill, grown)
    fill[fill < -1e5] = float(np.median(top[known]))
    ymin = float(fill.min()) - 1
    lid = np.zeros_like(known)
    if vox is not None:                                    # something solid rises above the cut there
        nx, ny, nz = vox["shape"]
        g = vox_bool(vox).reshape(ny, nz, nx)
        has = g.any(0)
        top_iy = np.where(has, ny - 1 - np.argmax(g[::-1], axis=0), -1)          # (nz, nx)
        ox, oy, oz = vox["origin"]
        top_y = np.where(top_iy >= 0, oy + (top_iy + 1) * vox["cell"], -np.inf)
        rows, cols = np.nonzero(~known)
        cx = (cols + x0 + 0.5) * HCELL
        cz = (rows + z0 + 0.5) * HCELL
        r = int(round(0.5 * HCELL / vox["cell"]))
        ix = np.floor((cx - ox) / vox["cell"]).astype(int)
        iz = np.floor((cz - oz) / vox["cell"]).astype(int)
        best = np.full(len(rows), -np.inf)
        for dx in range(-r, r):
            for dz in range(-r, r):
                a, b = ix + dx, iz + dz
                ok = (a >= 0) & (a < nx) & (b >= 0) & (b < nz)
                best[ok] = np.maximum(best[ok], top_y[b[ok], a[ok]])
        lid[rows, cols] = best > fill[rows, cols] + ROOF
    v = (np.clip((fill - ymin) * 100, 0, 65532).astype(np.int64) & ~3) | known.astype(np.int64) | (lid.astype(np.int64) << 1)
    return {"x0": x0 * HCELL, "z0": z0 * HCELL, "w": w, "h": h, "cell": HCELL, "ymin": round(ymin, 2),
            "v": v.astype(np.uint16)}


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
    return np.clip(k + 1, 0, 254).astype(np.uint8)               # 255: the lids (browser)


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
