"""4.51: aim drills on the real maps: your deaths as drills (Practice › Aim on maps).

Every death of a player in a match with a replay (and a map built from the game's files) can be played again: you
stand where you died, looking where you looked; your killer comes out on his real path from the replay with his
agent and his gun, the round's utility where it was. Your time to kill him is measured against his real time to
kill you (stats/sight.py: how long he had you in view before the kill).

drills_of(ctx): the drills of every player of one match (kept per match in data/drills/<match id>.json, built again
when the replay or the map changes). group(): the same spot killing you again is one card ("×3"). The runs (your
times per rep) are kept per player in data/profiles/<pid>/stats/drills.json.

GUNS: the weapons' numbers the drills use (magazine, fire rate, reload, damage to head/body/legs at close range,
zoom when aiming down sights). From the game's patch notes as of late 2026; the Bandit and the Warden are newer and
their numbers rougher."""
from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

VERSION = 1
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


def read_cached(data_dir, mid: str, sig: str) -> dict | None:
    try:
        d = json.loads((cache_dir(data_dir) / f"{mid.lower()}.json").read_text())
    except (OSError, ValueError):
        return None
    if d.get("v") != VERSION or d.get("sig") != sig:
        return None
    return d.get("players") or {}


def write_cached(data_dir, mid: str, sig: str, players: dict) -> None:
    d = cache_dir(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{mid.lower()}.json.tmp"
    tmp.write_text(json.dumps({"v": VERSION, "sig": sig, "built": int(time.time()), "players": players}))
    os.replace(tmp, d / f"{mid.lower()}.json")


def runs_file(stats_dir: Path) -> Path:
    return Path(stats_dir) / "drills.json"


def read_runs(stats_dir: Path) -> dict:
    try:
        d = json.loads(runs_file(stats_dir).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def clean_run(body: dict) -> dict | None:
    """A run as the page sends it -> what's kept, or None when it's no run."""
    reps = body.get("reps")
    if not isinstance(reps, list) or not 0 < len(reps) <= 50:
        return None
    out_reps = []
    for t in reps:
        if t is None:
            out_reps.append(None)
        elif isinstance(t, (int, float)) and 0 <= t < 30:
            out_reps.append(round(float(t), 3))
        else:
            return None
    his = body.get("his")
    his = round(float(his), 2) if isinstance(his, (int, float)) and 0 <= his < 30 else None
    first = body.get("first") if isinstance(body.get("first"), dict) else {}
    first = {k: int(first.get(k) or 0) for k in ("head", "body", "legs", "miss") if isinstance(first.get(k, 0), int)}
    off = body.get("off")
    off = round(float(off), 1) if isinstance(off, (int, float)) and 0 <= off <= 180 else None
    return {"at": int(time.time()), "reps": out_reps, "his": his, "first": first, "off": off}


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


def summary(runs: list[dict]) -> dict:
    """A drill's history: the median of each session (oldest first), the best time, the last session's numbers."""
    meds = []
    for r in runs:
        times = sorted(t for t in r.get("reps", []) if isinstance(t, (int, float)))
        if times:
            meds.append(round(times[len(times) // 2], 3))
    best = min((t for r in runs for t in r.get("reps", []) if isinstance(t, (int, float))), default=None)
    return {"sessions": len(runs), "medians": meds, "best": best}


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
