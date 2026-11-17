"""Line of sight on the maps built from the game's files (4.48), and the death review built on it.

The map's see-through grid (mapmesh.voxelize: every quarter-metre cell a wall, floor or box passes through) says
whether two points can see each other: the straight line between them must not pass a solid cell. Glass and
clutter (plants, cables) don't block; smokes aren't counted (a smoke hides you, but you were still in the open).

death_review(...) per kill, from the replay's positions (ten a second) and view directions:
- who saw whom first: when the killer first had the victim in his field of view with a clear line (and stayed on
  him until the kill), and when the victim first had the killer;
- how many enemies had a clear line to the victim just before he died (swung into several at once);
- how long the victim stood visible to his killer before dying;
- the callout (the game's own zones) where each one stood."""
from __future__ import annotations

import bisect
import math

import numpy as np

EYE = 1.55            # m above the feet: eyes
CHEST = 1.1           # m above the feet: the body (a line to the head or the body counts)
HALF_FOV = math.radians(103 / 2)
WINDOW_S = 6.0        # looked at before each kill
STEP_S = 0.1
SKIP = 0.35           # m at both ends of a line that aren't checked (the player's own spot, a wall he leans on)
GAP_S = 0.3           # a break in sight shorter than this doesn't start a new look


class Sight:
    def __init__(self, vox: dict):
        self.origin = np.asarray(vox["origin"], float)
        self.cell = float(vox["cell"])
        self.nx, self.ny, self.nz = (int(x) for x in vox["shape"])
        self.grid = np.unpackbits(vox["bits"])[: self.nx * self.ny * self.nz].astype(bool)

    def solid(self, P: np.ndarray) -> np.ndarray:
        q = np.floor((P - self.origin) / self.cell).astype(np.int64)
        ok = ((q >= 0) & (q < [self.nx, self.ny, self.nz])).all(-1)
        out = np.zeros(P.shape[:-1], bool)
        qq = q[ok]
        out[ok] = self.grid[qq[:, 0] + self.nx * (qq[:, 2] + self.nz * qq[:, 1])]
        return out

    def clear(self, A: np.ndarray, B: np.ndarray) -> np.ndarray:
        """Rows of points A -> B (frame metres, (n, 3)): True where nothing solid is in between."""
        A, B = np.atleast_2d(A).astype(float), np.atleast_2d(B).astype(float)
        D = B - A
        L = np.linalg.norm(D, axis=1)
        n = int(max(2, math.ceil(L.max() / (self.cell * 0.5)))) if len(L) else 2
        s = np.linspace(0, 1, n)[None, :, None]
        P = A[:, None, :] + D[:, None, :] * s
        along = L[:, None] * s[0, :, 0][None, :]
        check = (along > SKIP) & (along < (L[:, None] - SKIP))
        hit = self.solid(P) & check
        return ~hit.any(1)


# ------------------------------------------------------------------------------------------------ positions
class Tracks:
    """Every player's replay positions in the frame, for lookups by time (ms on the replay clock)."""

    def __init__(self, data: dict, known: dict[str, str], to3d, foot_cm: float):
        self.t: dict[str, list] = {}
        self.p: dict[str, np.ndarray] = {}
        for sub, rows in (data.get("pos") or {}).items():
            puuid = known.get(str(sub).lower())
            if not puuid or not rows:
                continue
            arr = np.array([r[:5] + [0.0] * (5 - len(r[:5])) for r in rows], float)
            pts = np.array([to3d(x, y, z) for x, y, z in arr[:, 1:4]])
            pts[:, 1] -= foot_cm / 100.0
            self.t[puuid] = arr[:, 0].tolist()
            self.p[puuid] = np.column_stack([pts, arr[:, 4]])

    def at(self, puuid: str, t_ms: float):
        ts = self.t.get(puuid)
        if not ts:
            return None
        i = bisect.bisect_right(ts, t_ms) - 1
        if i < 0 or t_ms - ts[i] > 1500:
            return None
        return self.p[puuid][i]


def _in_view(a, b, yaw_world_to_frame) -> bool:
    """b in a's horizontal field of view; a = [x, y, z, world yaw (deg)]."""
    ang = yaw_world_to_frame(a[3])
    fx, fz = math.sin(ang), -math.cos(ang)
    dx, dz = b[0] - a[0], b[2] - a[2]
    d = math.hypot(dx, dz)
    if d < 0.5:
        return True
    return (fx * dx + fz * dz) / d >= math.cos(HALF_FOV)


def death_review(sight: Sight, tracks: Tracks, kill_ms: float, victim: str, killer: str | None,
                 enemies: list[str], alive_at, yaw3d) -> dict:
    """One kill. kill_ms: replay clock. alive_at(puuid, ms) -> bool. yaw3d(world deg) -> frame radians.
    -> {"killer_saw": s before the kill or None, "victim_saw": …, "first": "killer"|"victim"|"same"|None,
        "exposed": s visible to the killer, "open_to": n enemies with a line, "unseen": the victim never had the
        killer in view}"""
    out = {"killer_saw": None, "victim_saw": None, "first": None, "exposed": None, "open_to": None, "unseen": None}
    v_end = tracks.at(victim, kill_ms)
    if v_end is None:
        return out
    # enemies with a clear line to the victim just before the kill
    t_check = kill_ms - 300
    vv = tracks.at(victim, t_check)
    if vv is not None:
        n = 0
        for e in enemies:
            if not alive_at(e, t_check):
                continue
            ee = tracks.at(e, t_check)
            if ee is not None and _sees(sight, ee, vv):
                n += 1
        out["open_to"] = n
    if not killer or killer == victim:
        return out
    steps = int(WINDOW_S / STEP_S)
    pairs = []
    for s in range(steps, -1, -1):
        t = kill_ms - s * STEP_S * 1000
        pairs.append((tracks.at(killer, t), tracks.at(victim, t)))
    have = [k is not None and v is not None for k, v in pairs]
    clear = _sees_many(sight, [p for p, h in zip(pairs, have) if h])
    it = iter(clear)
    line = [bool(next(it)) if h else False for h in have]
    k_sees = [c and _in_view(k, v, yaw3d) for c, (k, v) in zip(line, pairs)]
    v_sees = [c and _in_view(v, k, yaw3d) for c, (k, v) in zip(line, pairs)]
    ks, vs = _last_stretch(k_sees), _last_stretch(v_sees, end_slack=8)
    ex = _last_stretch(line)
    out["killer_saw"] = round(ks, 1) if ks is not None else None
    out["victim_saw"] = round(vs, 1) if vs is not None else None
    out["exposed"] = round(ex, 1) if ex is not None else None
    out["unseen"] = vs is None and ks is not None          # the killer had him, he never had the killer
    if ks is not None and vs is not None:
        out["first"] = "same" if abs(ks - vs) < 0.15 else ("killer" if ks > vs else "victim")
    elif ks is not None:
        out["first"] = "killer"
    elif vs is not None:
        out["first"] = "victim"
    return out


def _sees_many(sight: Sight, pairs: list) -> list[bool]:
    """[(a, b), ...] -> a line from a's eyes to b's head or body, for each pair (one batch of rays)."""
    if not pairs:
        return []
    A, B = [], []
    for a, b in pairs:
        A += [[a[0], a[1] + EYE, a[2]]] * 2
        B += [[b[0], b[1] + EYE, b[2]], [b[0], b[1] + CHEST, b[2]]]
    c = sight.clear(np.array(A), np.array(B)).reshape(-1, 2)
    return c.any(1).tolist()


def _sees(sight: Sight, a, b) -> bool:
    A = np.array([[a[0], a[1] + EYE, a[2]]] * 2)
    B = np.array([[b[0], b[1] + EYE, b[2]], [b[0], b[1] + CHEST, b[2]]])
    return bool(sight.clear(A, B).any())


def _last_stretch(flags: list[bool], end_slack: int = 3) -> float | None:
    """flags: oldest first, the last one at the kill. -> seconds from the start of the last stretch of True (that
    reaches the kill, allowing end_slack steps of False at the end and short gaps) to the kill, or None."""
    n = len(flags)
    i = n - 1
    slack = 0
    while i >= 0 and not flags[i] and slack < end_slack:
        i -= 1
        slack += 1
    if i < 0 or not flags[i]:
        return None
    gap = 0
    start = i
    while i >= 0:
        if flags[i]:
            start = i
            gap = 0
        else:
            gap += 1
            if gap * STEP_S > GAP_S:
                break
        i -= 1
    return (n - 1 - start) * STEP_S


# ------------------------------------------------------------------------------------------------ callouts
class Zones:
    """The game's callout zones (mapmesh meta "zones": polygons in the frame with a height range)."""

    def __init__(self, zones: list[dict]):
        self.z = []
        for z in zones or []:
            poly = np.asarray(z.get("poly") or [], float)
            if len(poly) < 3:
                continue
            area = 0.5 * abs(np.dot(poly[:, 0], np.roll(poly[:, 1], 1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], 1)))
            self.z.append((area, poly, z))
        self.z.sort(key=lambda a: a[0])                    # the smallest zone that has the point wins

    def at(self, x: float, y: float | None, z: float) -> str:
        best = None
        for _a, poly, zz in self.z:
            if _inside(poly, x, z):
                if y is None or zz["y0"] - 1.5 <= y <= zz["y1"] + 1.5:
                    return zz["label"]
                best = best or zz["label"]
        return best or ""


def _inside(poly, x, z) -> bool:
    n, inside = len(poly), False
    j = n - 1
    for i in range(n):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / ((zj - zi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside
