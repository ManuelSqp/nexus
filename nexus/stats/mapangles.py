"""Map angles (4.28): the aim trainer's duel on a real map layout. You stand at a callout of a site, facing another
one (hold the site looking at its main, or come out of main looking at the site); enemies show up at the other
callouts in front of you, at their real direction and distance on the map.

Where the callouts are comes from valorant-api.com (maps.py): points on the minimap, no walls and no heights. So the
directions and distances are the real ones in a straight line, every enemy is at your height, and each spot gets a
piece of cover to peek from. The page (static/trainer.js, scenario "map_angles") builds the room from this."""
from __future__ import annotations

import math

CONE = 75            # degrees left and right of where you look
NEAR, FAR = 3.0, 34.0
MIN_SPOTS = 3
WIDE_CONE, WIDE_FAR, WIDE_MIN = 100, 50.0, 2     # 4.69.1: big or open maps: a wider look before giving up


def _ang(du: float, dv: float) -> float:
    """Direction on the minimap in degrees: 0 = up, clockwise positive (to the right)."""
    return math.degrees(math.atan2(du, -dv))


def _wrap(a: float) -> float:
    return (a + 180) % 360 - 180


def spots_from(mi, stand, face, cone: float | None = None, far: float | None = None) -> list[dict]:
    """The callouts in front of you from `stand` facing `face`: [{label, yaw (deg, right positive), d (m)}]."""
    per_m = abs(mi.x_mult) * 100 or 0.007           # minimap units per meter (world units are cm)
    su, sv = mi.to_uv(stand.x, stand.y)
    fu, fv = mi.to_uv(face.x, face.y)
    look = _ang(fu - su, fv - sv)
    out, seen = [], {stand.label}
    for c in mi.callouts:
        if c.region.lower() == "spawn" or c.label in seen:
            continue
        seen.add(c.label)
        u, v = mi.to_uv(c.x, c.y)
        d = math.hypot(u - su, v - sv) / per_m
        yaw = _wrap(_ang(u - su, v - sv) - look)
        if NEAR <= d <= (FAR if far is None else far) and abs(yaw) <= (CONE if cone is None else cone):
            out.append({"label": c.label, "yaw": round(yaw, 1), "d": round(d, 1)})
    return sorted(out, key=lambda s: s["yaw"])


def positions(mi) -> list[dict]:
    """Where you can stand on a map: per site, holding the site (facing its main) and taking it from main (facing
    the site). [{id, name, stand, face, spots}] with at least MIN_SPOTS spots."""
    if not mi or not mi.callouts:
        return []
    by = {}
    for c in mi.callouts:
        by.setdefault((_sr(c), c.region.lower()), c)
    out = []
    for site in ("A", "B", "C"):
        s = _site(mi, site, by)
        m = by.get((site, "main")) or by.get((site, "lobby")) or by.get((site, "link")) or _approach(mi, site, s)
        if not s or not m:
            continue
        for stand, face, name, key in ((s, m, f"Hold {site} Site, facing {m.label}", f"{site}-hold"),
                                       (m, s, f"Take {site} from {m.label}", f"{site}-take")):
            sp = spots_from(mi, stand, face)
            if len(sp) < MIN_SPOTS:                      # 4.69.1: a big or open map: look wider and further
                sp = spots_from(mi, stand, face, WIDE_CONE, WIDE_FAR)
                if len(sp) < WIDE_MIN:
                    continue
            out.append({"id": key, "name": name, "stand": stand.label, "face": face.label, "spots": sp})
    return out


def _sr(c) -> str:
    """The site a callout belongs to: its super region ("A", "a", "A Site" -> A), else as it is."""
    v = (getattr(c, "super_region", "") or "").strip().upper()
    return v[:1] if v[:1] in ("A", "B", "C") and (len(v) == 1 or not v[1].isalpha()) else v


def _site(mi, site: str, by: dict):
    """4.69.1: the site's own callout: region "Site", else a callout called "A Site" / "Site A" / "A Plant"."""
    s = by.get((site, "site"))
    if s:
        return s
    for c in mi.callouts:
        lab = (c.label or "").lower()
        if lab in (f"{site.lower()} site", f"site {site.lower()}", f"{site.lower()} plant"):
            return c
    return None


def why_not(mi) -> str:
    """4.69.1: why a map has no positions, in a few words (for the page)."""
    if mi is None:
        return "no map data yet"
    if not mi.callouts:
        return "no callouts in the map data"
    by = {}
    for c in mi.callouts:
        by.setdefault((_sr(c), c.region.lower()), c)
    if not any(_site(mi, x, by) for x in ("A", "B", "C")):
        return "no sites in its callouts"
    return "too few callouts around its sites"


def _approach(mi, site: str, s):
    """4.56.2: a site without a callout called Main, Lobby or Link (newer maps name them otherwise): the way in is
    its callout furthest from the site that's still within reach."""
    if not s:
        return None
    per_m = abs(mi.x_mult) * 100 or 0.007
    su, sv = mi.to_uv(s.x, s.y)
    best, bd = None, 0.0
    for c in mi.callouts:
        if _sr(c) != site or c is s or c.region.lower() in ("site", "spawn"):
            continue
        u, v = mi.to_uv(c.x, c.y)
        d = math.hypot(u - su, v - sv) / per_m
        if bd < d <= FAR:
            best, bd = c, d
    return best


def for_maps(reg, names: list[str], missing: dict | None = None) -> dict[str, list[dict]]:
    """Map name -> positions, for the maps that have any (in the order given). missing (4.69.1): filled with
    name -> why_not for the others."""
    out = {}
    for n in names:
        try:
            mi = reg.get(name=n)
        except Exception:
            mi = None
        ps = positions(mi)
        if ps:
            out[n] = ps
        elif missing is not None:
            missing[n] = why_not(mi)
    return out
