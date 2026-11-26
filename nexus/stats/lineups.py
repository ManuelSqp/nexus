"""4.81: your lineups, per player (lineups.json next to the drill runs): where to stand and where to aim for an
ability on a map, recorded in the 3D map (drill.js "lineup" mode) and practised there (stand on the spot, aim, throw:
how far off you stood and aimed). From your team's strat book come the abilities it draws that you have no lineup
for yet, to record."""
from __future__ import annotations

import json
import math
import re
import secrets
import time
from pathlib import Path

MAX = 200
KEYS = ("C", "Q", "E", "X")
SLOT_KEY = {"grenade": "C", "ability1": "Q", "ability2": "E", "ultimate": "X"}
ID = re.compile(r"^[0-9a-f]{10}$")


def path(stats_dir: Path) -> Path:
    return Path(stats_dir) / "lineups.json"


def read(stats_dir: Path) -> list[dict]:
    try:
        d = json.loads(path(stats_dir).read_text())
    except (OSError, ValueError):
        return []
    return [x for x in d if isinstance(x, dict) and ID.match(str(x.get("id", "")))] if isinstance(d, list) else []


def write(stats_dir: Path, xs: list[dict]) -> None:
    p = path(stats_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(xs[-MAX:]))
    tmp.replace(p)


def _num(v, lo: float, hi: float) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and lo <= v <= hi else None


def clean(d, maps: list[str]) -> dict | None:
    """A lineup as the drill page sends it; None if it isn't one."""
    if not isinstance(d, dict) or d.get("map") not in maps:
        return None
    stand = d.get("stand")
    if not (isinstance(stand, list) and len(stand) == 3 and all(_num(v, -1e4, 1e4) is not None for v in stand)):
        return None
    yaw, pitch = _num(d.get("yaw"), -100, 100), _num(d.get("pitch"), -1.6, 1.6)
    if yaw is None or pitch is None:
        return None
    name = str(d.get("name") or "").strip()[:60] or "Lineup"
    agent = str(d.get("agent") or "").strip()[:30]
    ability = d.get("ability") if d.get("ability") in KEYS else ""
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    return {"map": d["map"], "name": name, "agent": agent, "ability": ability,
            "stand": [round(float(v), 2) for v in stand], "yaw": round(yaw, 5), "pitch": round(pitch, 5),
            "crouch": d.get("crouch") is True}


def save(stats_dir: Path, x: dict, lid: str = "") -> str:
    """Adds a lineup, or saves one over (lid); -> its id."""
    xs = read(stats_dir)
    old = next((i for i, y in enumerate(xs) if y["id"] == lid), None) if lid else None
    if old is not None:
        xs[old] = {**xs[old], **x, "id": lid, "at": int(time.time())}
    else:
        lid = secrets.token_hex(5)
        xs.append({**x, "id": lid, "at": int(time.time())})
    write(stats_dir, xs)
    return lid


def delete(stats_dir: Path, lid: str) -> bool:
    xs = read(stats_dir)
    keep = [x for x in xs if x["id"] != lid]
    if len(keep) == len(xs):
        return False
    write(stats_dir, keep)
    return True


def drill_id(map_name: str) -> str:
    """The runs of a map's lineup practice: "l-" + 10 hex digits of the map's name."""
    import hashlib
    return "l-" + hashlib.sha1(map_name.lower().encode()).hexdigest()[:10]


def from_strats(strats: list[dict], have: list[dict], near=None) -> list[dict]:
    """The abilities your strat book draws on a map (strats: [{name, map, data}]) that you have no lineup for:
    [{map, agent, ability, where, strat, name}] (where: the callout it lands at, from near(x, y) on the board's
    0..1000 units, or ""). One per agent, ability and place."""
    mine = {(x["map"], x.get("agent"), x.get("ability")) for x in have}
    out, seen = [], set()
    for s in strats:
        for st in (s.get("data") or {}).get("steps") or []:
            for it in st.get("items") or []:
                if not isinstance(it, dict) or it.get("t") != "ab" or it.get("c") == "them" or it.get("k"):
                    continue
                key = SLOT_KEY.get(str(it.get("s") or "").lower())
                agent = str(it.get("a") or "")
                if not key or not agent or (s["map"], agent, key) in mine:
                    continue
                where = near(it.get("x", 0), it.get("y", 0)) if near else ""
                k = (s["map"], agent, key, where)
                if k in seen:
                    continue
                seen.add(k)
                out.append({"map": s["map"], "agent": agent, "ability": key, "where": where, "strat": s["name"],
                            "name": f"{agent} {key}" + (f" {where}" if where else "")})
    return out[:30]
