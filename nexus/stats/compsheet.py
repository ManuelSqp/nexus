"""Comp sheet (4.13): every player's agent pool and the ideal composition per map, on one page.

Agent pool: each player's agents in order, best first, colored from green to red. It starts from the stats
(most played, then win rate) and the player can change it: reorder, add agents he wants to play, and mark
agents he won't play. Agents played later that aren't in the edited list are added at the end, so the list
never goes stale. Saved per team in data/teams/<tid>/compsheet.json:
  {"pools": {"<pid>": {"order": [agents], "no": [agents]}}, "ideal": {"<map lower>": [5 agents]},
   "follow": true}

Follow our agent pools (4.14, "follow"): the comps on the comps page (every mode, drafts, Discord prep) use
each player's pool: no agents he won't play, a bonus for agents he ranked high (comp.py, Pool.pref).

Ideal composition: per map, the comp web sources name most (webcomps.py, the same search as "From the
web"), or 5 agents the team owner typed. Under every agent: who on the team has it in their pool.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import roles
from .aggregate import by_agent

FILE = "compsheet.json"


# ---------------------------------------------------------------------------- storage
def load(team_dir: Path) -> dict:
    try:
        d = json.loads((Path(team_dir) / FILE).read_text())
        return {"pools": dict(d.get("pools") or {}), "ideal": dict(d.get("ideal") or {}),
                "follow": bool(d.get("follow"))}
    except (OSError, ValueError, AttributeError):
        return {"pools": {}, "ideal": {}, "follow": False}


def save(team_dir: Path, data: dict) -> None:
    p = Path(team_dir) / FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"pools": data.get("pools") or {}, "ideal": data.get("ideal") or {},
                               "follow": bool(data.get("follow"))}, ensure_ascii=False))
    tmp.replace(p)


def clean_agents(names, limit: int = 40) -> list[str]:
    """Only real agents, each once, in the given order (names from a form)."""
    key = lambda n: re.sub(r"[^a-z0-9]", "", str(n).lower())   # "kayo" = "KAY/O"
    known = {key(a): a for a in roles.all_agents()}
    out = []
    for n in names or []:
        a = known.get(key(n))
        if a and a not in out:
            out.append(a)
    return out[:limit]


# ---------------------------------------------------------------------------- agent pool
def pool(rows: list[dict], saved: dict | None = None) -> dict:
    """{agents: [{agent, role, games, wr, rank, added}], no: [agents], edited: bool}

    added = in the list without games (the player put it there)."""
    played = sorted(by_agent(rows), key=lambda a: (-a["games"], -a.get("wr", 0), a["agent"]))
    stats = {a["agent"]: a for a in played}
    no = clean_agents((saved or {}).get("no"))
    if saved and saved.get("order") is not None:
        order = [a for a in clean_agents(saved["order"]) if a not in no]
        order += [a["agent"] for a in played if a["agent"] not in order and a["agent"] not in no]
    else:
        order = [a["agent"] for a in played if a["agent"] not in no]
    agents = []
    for i, a in enumerate(order, 1):
        s = stats.get(a)
        agents.append({"agent": a, "role": roles.role_of(a), "games": s["games"] if s else 0,
                       "wr": s["wr"] if s else None, "rank": i, "added": s is None})
    only = clean_maps((saved or {}).get("maps"), order)
    for a in agents:
        a["maps"] = only.get(a["agent"])
    return {"agents": agents, "no": no, "edited": bool(saved), "maps": only}


def clean_maps(maps, agents, known: list[str] | None = None) -> dict[str, list[str]]:
    """4.64: {agent: [maps]}: the maps a player plays an agent on (none listed = every map). Only agents in his
    pool, map names as known (case of `known`), at most 12 maps; an empty list is dropped."""
    if not isinstance(maps, dict):
        return {}
    byk = {m.lower(): m for m in known or []}
    out = {}
    for a in clean_agents(list(maps)):
        if a not in agents:
            continue
        raw = maps.get(a) if a in maps else next((v for k, v in maps.items() if clean_agents([k]) == [a]), None)
        ms = []
        for m in raw if isinstance(raw, list) else []:
            m = str(m).strip()
            if known is not None:
                m = byk.get(m.lower(), "")
            if m and len(m) <= 24 and re.fullmatch(r"[A-Za-z' -]+", m) and m.lower() not in {x.lower() for x in ms}:
                ms.append(m)
        if ms:
            out[a] = ms[:12]
    return out


def prefs(rows: list[dict], saved: dict | None) -> dict:
    """A player's pool as comp.Pool.pref: {"rank": {agent: rank}, "size": n, "no": set, "added": set}."""
    pl = pool(rows, saved)
    return {"rank": {a["agent"]: a["rank"] for a in pl["agents"]}, "size": len(pl["agents"]),
            "no": set(pl["no"]), "added": {a["agent"] for a in pl["agents"] if a["added"]},
            "maps": {a: {m.lower() for m in ms} for a, ms in pl["maps"].items()}}


def hue(rank: int, n: int) -> int:
    """Green (120) for the first agent down to red (0) for the last."""
    return 120 if n <= 1 else round(120 - 120 * (rank - 1) / (n - 1))


# ---------------------------------------------------------------------------- ideal composition
def ideal(map_name: str, typed: list[str] | None, web_entry: dict | None) -> dict | None:
    """The typed comp if there is one, else the first comp from the web; None if neither."""
    typed = clean_agents(typed)
    if len(typed) == 5:
        return {"agents": typed, "source": "typed"}
    comps = (web_entry or {}).get("comps") or []
    if comps:
        c = comps[0]
        return {"agents": list(c["agents"]), "source": "web", "note": c.get("note", ""),
                "sources": c.get("sources", []), "at": web_entry.get("at"), "model": web_entry.get("model", ""),
                "others": len(comps) - 1}
    return None


def who_plays(agent: str, pools: dict[str, dict], top: int = 3) -> list[dict]:
    """Players who have this agent in their pool, best rank first: [{label, rank, games}]."""
    out = []
    for label, pl in pools.items():
        for a in pl["agents"]:
            if a["agent"] == agent:
                out.append({"label": label, "rank": a["rank"], "games": a["games"]})
                break
    return sorted(out, key=lambda x: (x["rank"], -x["games"]))[:top]
