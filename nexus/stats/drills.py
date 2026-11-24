"""4.51: aim drills on the real maps: your deaths as drills (Practice › Aim on maps).

Every death of a player in a match with a replay (and a map built from the game's files) can be played again: you
stand where you died, looking where you looked; your killer comes out on his real path from the replay with his
agent and his gun, the round's utility where it was. Your time to kill him is measured against his real time to
kill you (stats/sight.py: how long he had you in view before the kill).

drills_of(ctx): the drills of every player of one match (kept per match in data/drills/<match id>.json, built again
when the replay or the map changes). group(): the same spot killing you again is one card ("×3"). The runs (your
times per rep) are kept per player in data/profiles/<pid>/stats/drills.json.

4.54: spots after a plant (retakes()): retake a site (you come in, the spike ticking) and post-plant (you hold, they
come in on their real routes and go for the spike).

GUNS: the weapons' numbers the drills use (magazine, fire rate, reload, damage to head/body/legs at close range,
zoom when aiming down sights). From the game's patch notes as of late 2026; the Bandit and the Warden are newer and
their numbers rougher."""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import time
from pathlib import Path

from ..safepath import safe_join, valid_match_id

VERSION = 5                   # 5 (4.59): who died in a fight (the drills a match suggests);
                              # 2 (4.52): the fights of every match too (the general drills' spots); 3 (4.54): the
                              # spike (post-plant fights: retakes, post-plants); 4 (4.56): the utility around a fight
LEAD_S = 1.5                  # the drill starts this long before the killer first had you in view
MIN_LEAD_S = 2.5              # and at least this long before the kill
SPOT_M = 3.0                  # deaths this close (and from the same callout) are one spot
MAX_RUNS = 30                 # runs kept per drill
HP = 150                      # what a drill's enemy has (full shields)

# name: magazine, rounds per second, reload s, damage head/body/legs, zoom (aim down sights), automatic
GUNS = {
    "Classic": (12, 6.75, 1.75, 78, 26, 22, 1.0, False),
    "Shorty": (2, 3.33, 1.75, 220, 150, 120, 1.0, False),
    "Frenzy": (13, 10.0, 1.5, 78, 26, 22, 1.0, True),
    "Ghost": (15, 6.75, 1.5, 105, 30, 25, 1.0, False),
    "Sheriff": (6, 4.0, 2.25, 159, 55, 46, 1.0, False),
    "Bandit": (8, 5.0, 1.8, 140, 47, 40, 1.0, False),
    "Stinger": (20, 16.0, 2.25, 67, 27, 22, 1.15, True),
    "Spectre": (30, 13.33, 2.25, 78, 26, 22, 1.15, True),
    "Bucky": (5, 1.1, 2.5, 240, 150, 120, 1.0, False),
    "Judge": (7, 3.5, 2.2, 200, 150, 120, 1.0, True),
    "Bulldog": (24, 10.0, 2.5, 116, 35, 30, 1.25, True),
    "Guardian": (12, 5.25, 2.5, 195, 65, 49, 1.5, False),
    "Phantom": (30, 11.0, 2.5, 156, 39, 33, 1.25, True),
    "Vandal": (25, 9.75, 2.5, 160, 40, 34, 1.25, True),
    "Warden": (20, 6.0, 2.5, 160, 52, 44, 1.25, False),
    "Marshal": (5, 1.5, 2.5, 202, 101, 85, 3.5, False),
    "Outlaw": (2, 2.75, 2.5, 238, 140, 119, 3.5, False),
    "Operator": (5, 0.6, 3.7, 255, 150, 127, 2.5, False),
    "Ares": (50, 13.0, 3.25, 72, 30, 25, 1.25, True),
    "Odin": (100, 15.6, 5.0, 95, 38, 32, 1.25, True),
}


def gun(name: str) -> dict:
    g = GUNS.get(name) or GUNS["Classic"]
    return {"name": name if name in GUNS else "Classic", "mag": g[0], "rate": g[1], "reload": g[2],
            "head": g[3], "body": g[4], "legs": g[5], "zoom": g[6], "auto": g[7]}


# ------------------------------------------------------------------------------------------------ paths
def _at(path: list, t: float) -> list | None:
    """[x, y, z, yaw] at time t on a round path ([t, x, y, z, yaw] rows), held at its ends."""
    if not path:
        return None
    if t <= path[0][0]:
        return list(path[0][1:5])
    if t >= path[-1][0]:
        return list(path[-1][1:5])
    lo, hi = 0, len(path) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if path[m][0] <= t:
            lo = m
        else:
            hi = m
    a, b = path[lo], path[hi]
    f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
    dy = b[4] - a[4]
    if dy > math.pi:
        dy -= 2 * math.pi
    if dy < -math.pi:
        dy += 2 * math.pi
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f, a[4] + dy * f]


# ------------------------------------------------------------------------------------------------ building
def drills_of(ctx) -> dict[str, list[dict]]:
    """Every death in a match that can be a drill, per victim (puuid). Needs the map from the game's files (line of
    sight and callouts): without it the match has none."""
    out: dict[str, list[dict]] = {}
    if ctx is None or ctx.zones is None or ctx.mi is None:
        return out
    m = ctx.match
    for r in m.rounds:
        if r.index not in ctx.offsets or not r.kills:
            continue
        view = None
        rv = ctx.reviews(r.index)
        for n, k in enumerate(r.kills):
            if not k.killer or k.killer == k.victim or k.killer not in ctx.index or k.victim not in ctx.index:
                continue
            if m.team_of(k.killer) == m.team_of(k.victim):
                continue
            if view is None:
                view = ctx.round_view(r.index) or {}
            paths = view.get("paths") or {}
            vi, ki = ctx.index[k.victim], ctx.index[k.killer]
            vp, kp = paths.get(vi), paths.get(ki)
            if not vp or not kp:
                continue
            t_kill = round(k.t_round_ms / 1000, 2)
            rev = (rv.get(n) or {}).get("review") or {}
            his = rev.get("killer_saw")
            lead = max(his or 0.0, rev.get("victim_saw") or 0.0)
            t0 = max(vp[0][0], kp[0][0], t_kill - max(MIN_LEAD_S, lead + LEAD_S))
            if t_kill - t0 < 0.8:
                continue
            look = t_kill - (his if his is not None else 0.6)        # where you looked when he had you
            me_end = _at(vp, t_kill)
            me_look = _at(vp, look)
            kstart = _at(kp, t0)
            gseq = (view.get("guns") or {}).get(ki) or []
            weapon = k.weapon if k.weapon in GUNS else (gseq[-1][1] if gseq else "Classic")
            mseq = (view.get("guns") or {}).get(vi) or []
            mine = next((w for t, w in reversed(mseq) if t <= t_kill), "Classic") if mseq else "Classic"
            kpl, vpl = m.players[k.killer], m.players[k.victim]
            d = {"id": f"{m.match_id.lower()}-{r.index}-{n}", "mid": m.match_id.lower(), "round": r.index, "n": n,
                 "map": m.map_name, "t0": round(t0, 2), "t_kill": t_kill,
                 "his": his, "first": rev.get("first"), "unseen": rev.get("unseen"), "open_to": rev.get("open_to"),
                 "where": (rv.get(n) or {}).get("where") or "", "kwhere": (rv.get(n) or {}).get("kwhere") or "",
                 "killer": ki, "killer_name": kpl.name, "killer_agent": kpl.agent, "weapon": weapon,
                 "victim": vi, "agent": vpl.agent, "my_weapon": mine,
                 "me": [round(me_end[0], 2), round(me_end[1], 2), round(me_end[2], 2), round(me_look[3], 4)],
                 "from": [round(kstart[0], 2), round(kstart[1], 2), round(kstart[2], 2)],
                 "started": m.started_at or ""}
            out.setdefault(k.victim, []).append(d)
    return out


# ------------------------------------------------------------------------------------------------ 4.52: fights, spots
ROUTE_S = 15.0                # an attacker's route: this long before the fight (clear a site starts where
ROUTE_STEP = 0.5              # the site can't be seen yet, see drill.js)
PRE_S = 2.0                   # where the attacker came from: this long before
DISTINCT_M = 1.5              # spots closer than this are one
MAX_ANGLE_M = 50.0            # longer fights aren't an angle to hold


ENTRY_WALK_M = 8.0            # clear a site: the attacker walked at least this far in the 15 s
ENTRY_NEAR_M = 20.0           # and fought from this close


def _walked(route: list) -> float:
    return sum(math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in zip(route, route[1:]))


def _spawn(zone: str) -> bool:
    """Fights in a spawn (the round's end, a flank) aren't spots to train."""
    return "spawn" in (zone or "").lower()


def fights_of(ctx) -> list[dict]:
    """Every fight of a match (a kill between the two teams): where the attacker and the defender were, where the
    attacker came from (2 s before) and his route (15 s), the callouts, who won. The general drills' spots."""
    out: list[dict] = []
    if ctx is None or ctx.zones is None or ctx.mi is None:
        return out
    m = ctx.match
    team_of_i = {i: m.team_of(p) for p, i in ctx.index.items()}
    for r in m.rounds:
        if r.index not in ctx.offsets or not r.kills:
            continue
        view = None
        rv = ctx.reviews(r.index)
        for n, k in enumerate(r.kills):
            if not k.killer or k.killer == k.victim or k.killer not in ctx.index or k.victim not in ctx.index:
                continue
            kt, vt = m.team_of(k.killer), m.team_of(k.victim)
            if kt == vt or not kt:
                continue
            if view is None:
                view = ctx.round_view(r.index) or {}
            paths = view.get("paths") or {}
            kp, vp = paths.get(ctx.index[k.killer]), paths.get(ctx.index[k.victim])
            if not kp or not vp:
                continue
            killer_attacks = r.side_of(kt) == "attack"
            ap, dp = (kp, vp) if killer_attacks else (vp, kp)
            t = k.t_round_ms / 1000
            a, d = _at(ap, t), _at(dp, t)
            a0 = _at(ap, t - PRE_S)
            info = rv.get(n) or {}
            kz, vz = info.get("kwhere") or "", info.get("where") or ""
            route = []
            s_ = ROUTE_S
            while s_ >= -1e-9:
                q = _at(ap, t - s_)
                if not route or math.hypot(q[0] - route[-1][0], q[2] - route[-1][2]) > 0.05:
                    route.append([round(q[0], 2), round(q[1], 2), round(q[2], 2)])
                s_ -= ROUTE_STEP
            fight = {"a": [round(v, 2) for v in a[:3]], "d": [round(v, 2) for v in d[:3]],
                     "a0": [round(v, 2) for v in a0[:3]], "az": kz if killer_attacks else vz,
                     "dz": vz if killer_attacks else kz, "won": "attack" if killer_attacks else "defense",
                     "route": route, "round": r.index}
            plant = next((s for s in view.get("spike") or [] if s.get("kind") == "plant"), None)
            if plant and plant.get("site") and t >= plant["t"]:
                # 4.54: after the plant: where the spike was, how long after the plant, and the defender's way in
                # (every half second, standing still too: the retakers come in at their real speed)
                fight.update(post=round(t - plant["t"], 2), site=str(plant["site"]),
                             plant=[round(plant["x"], 2), round(plant["y"] if plant.get("y") is not None else d[1], 2),
                                    round(plant["z"], 2)],
                             droute=_timed(dp, t, ROUTE_S))
            # 4.56: the utility both teams used around it (after a plant: on the site until the spike goes off)
            sides = {i: ("a" if r.side_of(tm) == "attack" else "d") for i, tm in team_of_i.items() if tm}
            post = "post" in fight
            near = fight["plant"] if post else [(a[0] + d[0]) / 2, 0, (a[2] + d[2]) / 2]
            until = t + (SPIKE_S - fight["post"] if post else UTIL_AFTER_S)
            util = _fight_util(view.get("util") or [], sides, t, near, until,
                               UTIL_NEAR_M + (10 if post else math.hypot(a[0] - d[0], a[2] - d[2]) / 2))
            if util:
                fight["util"] = util
            fight["t"] = round(t, 2)
            vic = m.players.get(k.victim)
            if vic is not None:                         # 4.59: whose death it was (Riot ID, lower case)
                fight["victim"] = f"{vic.name}#{vic.tag}".lower()
            out.append(fight)
    return out


UTIL_TYPES = ("smoke", "damage", "slow", "flash", "wall", "recon", "trap")
UTIL_BEFORE_S = 15.0          # utility thrown this long before a fight still counts for it
UTIL_AFTER_S = 5.0            # and this long after
UTIL_NEAR_M = 25.0            # this close to the fight (to the spike after a plant)
UTIL_MAX = 16


def _fight_util(util: list, sides: dict, t: float, near: list, until: float, radius: float) -> list:
    """[[type, agent, side ("a" attackers / "d" defenders), seconds from the fight, how long (None: till the round
    ends), x, y, z], …] of the round's utility near a fight (4.56)."""
    out = []
    for u in util:
        side = sides.get(u.get("owner"))
        if u.get("type") not in UTIL_TYPES or not side or u.get("x") is None or u.get("z") is None:
            continue
        if not t - UTIL_BEFORE_S <= u["t0"] <= until:
            continue
        if math.hypot(u["x"] - near[0], u["z"] - near[2]) > radius:
            continue
        dur = None if u.get("t1") is None else round(max(0.0, u["t1"] - u["t0"]), 2)
        y = None if u.get("y") is None else round(u["y"], 2)
        out.append([u["type"], u.get("agent") or "", side, round(u["t0"] - t, 2), dur, round(u["x"], 2), y,
                    round(u["z"], 2)])
    out.sort(key=lambda x: x[3])
    return out[:UTIL_MAX]


def suggest(riot_id: str, fights: list[dict], sp: dict, n: int = 5) -> list[dict]:
    """4.59: the general drills a match points to: each of this player's deaths in it, as the drill on the spot it
    happened at (after a plant: retake as a defender, post-plant as an attacker; before it: hold the angle as a
    defender, entry onto a site or take the spot as an attacker), the most deaths first.
    -> [{mode, id, dz, az, deaths, rounds}]"""
    me = riot_id.lower()
    near = lambda p, q: math.hypot(p[0] - q[0], p[2] - q[2])      # noqa: E731
    got: dict[tuple, dict] = {}
    for f in fights:
        if f.get("victim") != me:
            continue
        defender = f["won"] == "attack"             # an attacker killed me: I was defending
        spot, mode = None, None
        if f.get("post") is not None:
            mode = "retake" if defender else "postplant"
            spot = next((s for s in sp.get("retakes", []) if s["site"] == f.get("site")), None)
        elif defender:
            mode = "hold"
            cand = [a for a in sp.get("angles", []) if near(a["hold"], f["d"]) <= 8.0]
            spot = min(cand, key=lambda a: near(a["hold"], f["d"])) if cand else None
        else:
            site = next((s for s in sp.get("sites", []) if s["dz"] == f.get("dz")), None)
            if site is not None:
                mode, spot = "entry", site
            else:
                mode = "attack"
                cand = [a for a in sp.get("angles", []) if near(a["hold"], f["d"]) <= 8.0]
                spot = min(cand, key=lambda a: near(a["hold"], f["d"])) if cand else None
        if spot is None:
            continue
        g = got.setdefault((mode, spot["id"]), {"mode": mode, "id": spot["id"], "dz": spot["dz"],
                                               "az": spot.get("az", ""), "deaths": 0, "rounds": []})
        g["deaths"] += 1
        if f.get("round") is not None and f["round"] + 1 not in g["rounds"]:
            g["rounds"].append(f["round"] + 1)
    return sorted(got.values(), key=lambda g: (-g["deaths"], g["rounds"][:1]))[:n]


def _util_sets(fs: list, shift=None, n: int = 10) -> list:
    """The utility of up to n fights (one per round, the most used first): [[item, …], …]; shift(f) moves the times
    (after a plant: from the plant instead of the fight)."""
    out, seen = [], set()
    for f in sorted(fs, key=lambda f: -len(f.get("util") or [])):
        items = f.get("util") or []
        key = (f.get("round"), tuple(items[0][:4]) if items else ())
        if not items or key in seen:
            continue
        seen.add(key)
        dt = shift(f) if shift else 0.0
        out.append([[u[0], u[1], u[2], round(u[3] + dt, 2), *u[4:]] for u in items])
        if len(out) >= n:
            break
    return out


def _timed(path: list, t: float, secs: float) -> list:
    """[x, y, z] every ROUTE_STEP seconds over the secs before t (the time is the place in the list)."""
    out = []
    n = int(round(secs / ROUTE_STEP))
    for i in range(n + 1):
        q = _at(path, t - secs + i * ROUTE_STEP)
        out.append([round(q[0], 2), round(q[1], 2), round(q[2], 2)])
    return out


def _distinct(points: list, n: int, gap: float = DISTINCT_M) -> list:
    out: list = []
    for p in points:
        if all(math.hypot(p[0] - q[0], p[2] - q[2]) >= gap for q in out):
            out.append(p)
        if len(out) >= n:
            break
    return out


def _medoid(points: list) -> list:
    return min(points, key=lambda p: sum(math.hypot(p[0] - q[0], p[2] - q[2]) for q in points))


def _yaw_to(a: list, b: list) -> float:
    """The frame's yaw (0 = -z, + clockwise on the minimap: x = sin, z = -cos) from a looking at b."""
    return round(math.atan2(b[0] - a[0], -(b[2] - a[2])), 4)


def spots(map_name: str, fights: list[dict]) -> dict:
    """The spots of a map from its fights: {"angles": [...], "sites": [...]}.
    angles: per pair of callouts (where the defender was, where the attacker was): where to hold (the defender's
    usual place, looking at the attackers'), the attackers' places (they peek from there), where attackers start
    (2 s before), the defenders' places (attacking: you take them), the distance, a route, how often.
    sites: per defender callout: the defenders' hiding places and the attackers' most used route in (clear a site)."""
    groups: dict[tuple, list] = {}
    for f in fights:
        if f.get("az") and f.get("dz") and not _spawn(f["az"]) and not _spawn(f["dz"]):
            groups.setdefault((f["dz"], f["az"]), []).append(f)
    angles = []
    for (dz, az), fs in groups.items():
        D, A0 = [f["d"] for f in fs], [f["a0"] for f in fs]
        hold = _medoid(D)
        att = next(f["a"] for f in fs if f["d"] == hold)     # a real pair: they saw each other (the medoids may not)
        A = [att] + [f["a"] for f in fs if f["a"] is not att]
        start = _medoid(A0)
        best = min(fs, key=lambda f: math.hypot(f["a0"][0] - start[0], f["a0"][2] - start[2]))
        dist = math.hypot(hold[0] - att[0], hold[2] - att[2])
        if dist > MAX_ANGLE_M:
            continue
        sid = hashlib.sha1(f"{map_name}|{dz}|{az}".encode()).hexdigest()[:10]
        angles.append({"id": sid, "map": map_name, "dz": dz, "az": az, "count": len(fs),
                       "won_def": sum(1 for f in fs if f["won"] == "defense"),
                       "hold": hold, "hold_yaw": _yaw_to(hold, att),
                       "peeks": _distinct(sorted(A, key=lambda p: math.hypot(p[0] - att[0], p[2] - att[2])), 5),
                       "start": start, "start_yaw": _yaw_to(start, hold),
                       "defs": _distinct(sorted(D, key=lambda p: math.hypot(p[0] - hold[0], p[2] - hold[2])), 4),
                       "dist": round(dist, 1), "route": best["route"], "util": _util_sets(fs)})
    angles.sort(key=lambda a: (-a["count"], a["dz"], a["az"]))
    sites = []
    by_dz: dict[str, list] = {}
    for f in fights:
        if f.get("dz") and not _spawn(f["dz"]):
            by_dz.setdefault(f["dz"], []).append(f)
    for dz, fs in by_dz.items():
        # the way in: fights where the attacker walked a few metres and ended up close to the defender
        ins = [f for f in fs if _walked(f["route"]) >= ENTRY_WALK_M
               and math.hypot(f["a"][0] - f["d"][0], f["a"][2] - f["d"][2]) <= ENTRY_NEAR_M]
        if not ins:
            continue
        az_count: dict[str, int] = {}
        for f in ins:
            az_count[f["az"] or "?"] = az_count.get(f["az"] or "?", 0) + 1
        az = max(az_count, key=lambda z: (az_count[z], z))
        ins = [f for f in ins if (f["az"] or "?") == az]
        start = _medoid([f["route"][0] for f in ins])
        best = min(ins, key=lambda f: math.hypot(f["route"][0][0] - start[0], f["route"][0][2] - start[2]))
        hides = _distinct([f["d"] for f in sorted(fs, key=lambda f: f["round"])], 6, 2.0)
        if len(best["route"]) < 2:
            continue
        sid = hashlib.sha1(f"{map_name}|site|{dz}|{az}".encode()).hexdigest()[:10]
        sites.append({"id": sid, "map": map_name, "dz": dz, "az": az, "count": len(fs), "route": best["route"],
                      "hides": hides, "start_yaw": _yaw_to(best["route"][0], best["route"][min(3, len(best["route"]) - 1)]),
                      "util": _util_sets(fs)})
    sites.sort(key=lambda a: (-a["count"], a["dz"]))
    return {"angles": angles, "sites": sites, "retakes": retakes(map_name, fights)}


SPIKE_S = 45.0                # the spike goes off this long after the plant
DEFUSE_S = 7.0                # a defuse (half of it stays: 3.5 s)
POST_NEAR_M = 25.0            # post-plant: attackers this close to the spike play it
RETAKE_FAR_M = 12.0           # a retake: the defender started at least this far from the spike


def _dense(points: list, n: int, gap: float, near: float = 3.0) -> list:
    """Up to n places at least gap apart, the most used first (the most others within near metres)."""
    score = [sum(1 for q in points if math.hypot(p[0] - q[0], p[2] - q[2]) <= near) for p in points]
    order = sorted(range(len(points)), key=lambda i: -score[i])
    return _distinct([points[i] for i in order], n, gap)


def retakes(map_name: str, fights: list[dict]) -> list[dict]:
    """4.54: per site, from the fights after a plant: where the spike usually is, where attackers play it (posts),
    the ways defenders come back in (up to three routes, every half second over 15 s), how long the spike had left
    when they set off. Retake (you come in) and post-plant (you hold, they come)."""
    by_site: dict[str, list] = {}
    for f in fights:
        if f.get("post") is not None and f.get("site") and f.get("plant"):
            by_site.setdefault(f["site"], []).append(f)
    out = []
    for site, fs in by_site.items():
        plant = _medoid([f["plant"] for f in fs])
        near = lambda p: math.hypot(p[0] - plant[0], p[2] - plant[2])       # noqa: E731
        posts = _dense([f["a"] for f in fs if near(f["a"]) <= POST_NEAR_M], 6, 2.0)
        ins = [f for f in fs if f.get("droute") and len(f["droute"]) > 4 and near(f["droute"][0]) >= RETAKE_FAR_M
               and _walked(f["droute"]) >= ENTRY_WALK_M and near(f["d"]) <= POST_NEAR_M + 10]
        if not posts or not ins:
            continue
        starts = _dense([f["droute"][0] for f in ins], 3, 8.0, 6.0)
        routes = []
        for s0 in starts:
            f = min(ins, key=lambda f: math.hypot(f["droute"][0][0] - s0[0], f["droute"][0][2] - s0[2]))
            cnt = sum(1 for g in ins if math.hypot(g["droute"][0][0] - s0[0], g["droute"][0][2] - s0[2]) <= 6.0)
            routes.append({"path": f["droute"], "count": cnt, "left": round(SPIKE_S - max(0.0, f["post"] - ROUTE_S), 1)})
        left = sorted(r["left"] for r in routes)[len(routes) // 2]
        sid = hashlib.sha1(f"{map_name}|retake|{site}".encode()).hexdigest()[:10]
        out.append({"id": sid, "map": map_name, "site": site, "dz": site, "az": "", "count": len(fs),
                    "won_def": sum(1 for f in fs if f["won"] == "defense"), "plant": plant, "posts": posts,
                    "routes": routes, "left": max(20.0, min(SPIKE_S, left)),
                    # 4.56: the utility after the plant, from the plant
                    "util": _util_sets(fs, lambda f: f["post"])})
    out.sort(key=lambda a: (-a["count"], a["site"]))
    return out


def same_spot(a: dict, b: dict) -> bool:
    """Two deaths at the same spot: the same map and killer's callout, a few metres apart."""
    return (a["map"] == b["map"] and (a.get("kwhere") or "") == (b.get("kwhere") or "")
            and math.hypot(a["me"][0] - b["me"][0], a["me"][2] - b["me"][2]) <= SPOT_M)


def group(drills: list[dict], runs: dict | None = None) -> list[dict]:
    """Drills of the same spot together, newest first: [{"drill" (the newest), "count", "ids", "best", "beaten",
    "played"}]. best: your fastest time on any drill of the spot; beaten: faster than his time."""
    runs = runs or {}
    spots: list[dict] = []
    for d in sorted(drills, key=lambda d: (d.get("started") or "", d["round"], d["n"]), reverse=True):
        s = next((x for x in spots if same_spot(x["drill"], d)), None)
        if s is None:
            s = {"drill": d, "count": 0, "ids": [], "best": None, "beaten": False, "played": 0}
            spots.append(s)
        s["count"] += 1
        s["ids"].append(d["id"])
        for run in runs.get(d["id"], []):
            s["played"] += 1
            times = [t for t in run.get("reps", []) if isinstance(t, (int, float))]
            if times:
                b = min(times)
                s["best"] = b if s["best"] is None else min(s["best"], b)
                his = run.get("his")
                if his is not None and b < his:
                    s["beaten"] = True
    return spots


# ------------------------------------------------------------------------------------------------ files
def cache_dir(data_dir) -> Path:
    return Path(data_dir) / "drills"


def cache_file(data_dir, mid: str, suffix: str = ".json") -> Path:
    """4.61.1: data/drills/<match id>.json; a match id only (letters, digits, -), never a path."""
    if not valid_match_id(mid):
        raise ValueError("not a match id")
    return safe_join(cache_dir(data_dir), f"{mid.lower()}{suffix}")


def _read_cache(data_dir, mid: str, sig: str) -> dict | None:
    try:
        d = json.loads(cache_file(data_dir, mid).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    if d.get("v") != VERSION or d.get("sig") != sig:
        return None
    return d


def read_cached(data_dir, mid: str, sig: str) -> dict | None:
    """The drills of a match per player (Riot ID), or None: not worked out (or outdated)."""
    d = _read_cache(data_dir, mid, sig)
    return None if d is None else d.get("players") or {}


def read_fights(data_dir, mid: str, sig: str) -> list | None:
    """4.52: the fights of a match, or None: not worked out (or outdated)."""
    d = _read_cache(data_dir, mid, sig)
    return None if d is None else d.get("fights") or []


def write_cached(data_dir, mid: str, sig: str, players: dict, fights: list | None = None, map_name: str = "") -> None:
    cache_dir(data_dir).mkdir(parents=True, exist_ok=True)
    tmp, final = cache_file(data_dir, mid, ".json.tmp"), cache_file(data_dir, mid)
    tmp.write_text(json.dumps({"v": VERSION, "sig": sig, "built": int(time.time()), "map": map_name,
                               "players": players, "fights": fights or []}))
    os.replace(tmp, final)


def runs_file(stats_dir: Path) -> Path:
    return Path(stats_dir) / "drills.json"


def read_runs(stats_dir: Path) -> dict:
    try:
        d = json.loads(runs_file(stats_dir).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


KINDS = {"death": "s", "hold": "s", "attack": "s", "track": "%", "clear": "%",      # what a rep's number is
         "entry": "s", "retake": "s", "postplant": "s"}                              # 4.54
HIGHER = {"track", "clear"}                     # the bigger the better (the others: times, the smaller the better)


def clean_run(body: dict) -> dict | None:
    """A run as the page sends it -> what's kept, or None when it's no run. reps: a number per rep (seconds, or a
    percentage for tracking and clearing), None for a rep you lost."""
    reps = body.get("reps")
    kind = body.get("kind") if body.get("kind") in KINDS else "death"
    top = (100.0 if KINDS[kind] == "%" else 120.0 if kind in ("attack", "entry", "retake")   # moving: up to a minute
           else 30.0)
    if not isinstance(reps, list) or not 0 < len(reps) <= 50:
        return None
    out_reps = []
    for t in reps:
        if t is None:
            out_reps.append(None)
        elif isinstance(t, (int, float)) and 0 <= t <= top:
            out_reps.append(round(float(t), 3))
        else:
            return None
    his = body.get("his")
    his = round(float(his), 2) if isinstance(his, (int, float)) and 0 <= his < 30 else None
    first = body.get("first") if isinstance(body.get("first"), dict) else {}
    first = {k: int(first.get(k) or 0) for k in ("head", "body", "legs", "miss") if isinstance(first.get(k, 0), int)}
    off = body.get("off")
    off = round(float(off), 1) if isinstance(off, (int, float)) and 0 <= off <= 180 else None
    out = {"at": int(time.time()), "kind": kind, "reps": out_reps, "his": his, "first": first, "off": off}
    for k, n in (("map", 24), ("where", 80)):     # 4.65: what the weekly view calls it
        v = body.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = " ".join(v.split())[:n]
    detail = body.get("detail")
    if isinstance(detail, dict):                 # a few numbers per kind (peek styles, counter-strafing, …)
        out["detail"] = {str(k)[:24]: round(float(v), 3) for k, v in list(detail.items())[:20]
                         if isinstance(v, (int, float)) and math.isfinite(v)}
    return out


def add_run(stats_dir: Path, drill_id: str, run: dict) -> dict:
    data = read_runs(stats_dir)
    lst = data.setdefault(drill_id, [])
    lst.append(run)
    del lst[:-MAX_RUNS]
    f = runs_file(stats_dir)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data))
    os.replace(tmp, f)
    return data


def summary(runs: list[dict], kind: str = "death") -> dict:
    """A drill's history: the median of each session (oldest first), the best, the number of sessions. For
    tracking and clearing (percentages) the best is the highest."""
    meds = []
    for r in runs:
        vals = sorted(t for t in r.get("reps", []) if isinstance(t, (int, float)))
        if vals:
            meds.append(round(vals[len(vals) // 2], 3))
    vals = [t for r in runs for t in r.get("reps", []) if isinstance(t, (int, float))]
    best = (max(vals) if kind in HIGHER else min(vals)) if vals else None
    return {"sessions": len(runs), "medians": meds, "best": best, "kind": kind}


# ------------------------------------------------------------------------------------------------ 4.65: your week
MODE_NAMES = {"death": "Your deaths", "hold": "Hold an angle", "attack": "Take an angle", "track": "Tracking",
              "clear": "Clear a site", "entry": "Entry", "retake": "Retake", "postplant": "Post-plant"}
WEEKS = 8


def _week_start(ts: float) -> datetime.date:
    d = datetime.date.fromtimestamp(ts)
    return d - datetime.timedelta(days=d.weekday())         # Monday


def _median(vals: list) -> float | None:
    v = sorted(x for x in vals if isinstance(x, (int, float)))
    return v[len(v) // 2] if v else None


def _better(kind: str, old, new) -> float | None:
    """How much better new is than old: seconds faster, or percentage points more (track, clear). + is better."""
    if old is None or new is None:
        return None
    return round((new - old) if kind in HIGHER else (old - new), 3)


def weekly(data: dict, now: float | None = None, weeks: int = WEEKS) -> dict:
    """The drills you played, week by week (Monday to Sunday): sessions and reps per week for the last `weeks`
    weeks, this week against last week per kind of drill (the median of your reps), and per drill this week
    against the weeks before (the most improved and the ones that slipped).
    -> {weeks: [{start, sessions, reps}], days, kinds: [{kind, name, unit, sessions, now, before, better}],
        better: [drill], worse: [drill], total}"""
    now = time.time() if now is None else now
    this = _week_start(now)
    starts = [this - datetime.timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    per_week = {w: {"start": w.isoformat(), "sessions": 0, "reps": 0} for w in starts}
    days, kinds, drills = set(), {}, []
    last = this - datetime.timedelta(weeks=1)
    for did, runs in (data or {}).items():
        if not isinstance(runs, list):
            continue
        cur, old, label, kind = [], [], {}, None
        for r in runs:
            if not isinstance(r, dict) or not isinstance(r.get("at"), (int, float)):
                continue
            kind = r.get("kind") if r.get("kind") in KINDS else "death"
            w = _week_start(r["at"])
            reps = [t for t in r.get("reps") or [] if isinstance(t, (int, float))]
            if w in per_week:
                per_week[w]["sessions"] += 1
                per_week[w]["reps"] += len(r.get("reps") or [])
            k = kinds.setdefault(kind, {"now": [], "last": [], "sessions": 0})
            if w == this:
                days.add(datetime.date.fromtimestamp(r["at"]))
                k["now"] += reps
                k["sessions"] += 1
                cur += reps
            else:
                old += reps
                if w == last:
                    k["last"] += reps
            label = {"map": r.get("map", label.get("map", "")), "where": r.get("where", label.get("where", ""))}
        if kind is None:
            continue
        mn, mo = _median(cur), _median(old)
        if mn is not None and mo is not None:
            drills.append({"id": did, "kind": kind, "name": MODE_NAMES.get(kind, kind), "unit": KINDS[kind],
                           "map": label.get("map", ""), "where": label.get("where", ""), "now": mn, "before": mo,
                           "better": _better(kind, mo, mn), "sessions": sum(1 for r in runs if isinstance(r, dict)
                                                                            and isinstance(r.get("at"), (int, float))
                                                                            and _week_start(r["at"]) == this)})
    out_kinds = []
    for kind, k in kinds.items():
        if not k["sessions"]:
            continue
        mn, ml = _median(k["now"]), _median(k["last"])
        out_kinds.append({"kind": kind, "name": MODE_NAMES.get(kind, kind), "unit": KINDS[kind], "sessions": k["sessions"],
                          "now": mn, "before": ml, "better": _better(kind, ml, mn)})
    out_kinds.sort(key=lambda k: -k["sessions"])
    rel = lambda d: d["better"] / max(abs(d["before"]), 1e-6)       # noqa: E731  (relative: s and % alike)
    better = sorted((d for d in drills if d["better"] > 0), key=lambda d: -rel(d))[:3]
    worse = sorted((d for d in drills if d["better"] < 0), key=rel)[:3]
    weeks_out = [per_week[w] for w in starts]
    return {"weeks": weeks_out, "days": len(days), "kinds": out_kinds, "better": better, "worse": worse,
            "total": sum(w["sessions"] for w in weeks_out), "this": weeks_out[-1], "last": weeks_out[-2] if weeks > 1 else None}


# ------------------------------------------------------------------------------------------------ keys
# The actions a player can put on his own keys (4.51; the aim drills, later the trainer). Values: e.code names of
# the keyboard ("KeyR", "Space", "Backspace", …) or "Mouse0".."Mouse4", "WheelUp", "WheelDown".
ACTIONS = {
    "shoot": ("Shoot", "Mouse0"),
    "reload": ("Reload", "KeyR"),
    "ads": ("Aim down sights", "Mouse2"),
    "restart": ("Restart the drill", "Backspace"),
    "next": ("Next rep", "Space"),
    "watch": ("Watch how he did it", "KeyP"),
    "full": ("Full screen", "KeyF"),
    # 4.52: moving (attacking, clearing a site). Crouch isn't on Ctrl: outside full screen Ctrl+W closes the tab.
    "forward": ("Move forward", "KeyW"),
    "back": ("Move back", "KeyS"),
    "left": ("Strafe left", "KeyA"),
    "right": ("Strafe right", "KeyD"),
    "walk": ("Walk", "ShiftLeft"),
    "crouch": ("Crouch", "KeyC"),
    # 4.54: retakes. 4 is the game's own key for the spike (held to defuse).
    "defuse": ("Defuse (hold)", "Digit4"),
    # 4.58: your agent's abilities in Aim on maps (C is crouch here, so its ability starts on Z: change it if you like)
    "ab_c": ("Ability C", "KeyZ"),
    "ab_q": ("Ability Q", "KeyQ"),
    "ab_e": ("Ability E", "KeyE"),
}
FIXED = {"Escape"}           # always stops a drill


def _code_ok(c) -> bool:
    return isinstance(c, str) and 0 < len(c) <= 24 and c.replace("_", "").isalnum() and c not in FIXED


def clean_keys(body: dict) -> dict:
    """{action: [key, second key or ""]} for the known actions, anything else dropped; missing ones: defaults."""
    out = {}
    for a, (_label, default) in ACTIONS.items():
        v = body.get(a) if isinstance(body, dict) else None
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            v = [default]
        keys = [c for c in v[:2] if _code_ok(c)]
        out[a] = (keys + [""])[:2] if keys else [default, ""]
    return out


def default_keys() -> dict:
    return {a: [d, ""] for a, (_l, d) in ACTIONS.items()}


def clashes(keys: dict) -> list[list]:
    """[[key, action, action], …]: a key on two actions."""
    seen: dict[str, str] = {}
    out = []
    for a, ks in keys.items():
        for k in ks:
            if not k:
                continue
            if k in seen and seen[k] != a:
                out.append([k, seen[k], a])
            else:
                seen[k] = a
    return out
