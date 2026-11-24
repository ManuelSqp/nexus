"""4.66: counter comps from scouting: which comp style (compstyle.py) fits against a scouted team on a map, and why.

Everything comes from the scouted team's numbers (scouting.summarize): how fast they hit and where, how their
retakes go, their entry player, their comps and their round win rates per side. Each sign gives points to a style;
the style with the most points wins if it has enough of them, else Balanced. Nothing calls a model."""
from __future__ import annotations

from . import roles
from .scouting import _pct

MIN_POINTS = 2.0          # below this: no clear counter, stay balanced


def _roles(agents: list[str]) -> dict:
    n: dict[str, int] = {}
    for a in agents:
        n[roles.role_of(a)] = n.get(roles.role_of(a), 0) + 1
    return n


def counter(s: dict | None, map_name: str) -> dict | None:
    """-> {style, points, reasons: [str], their_comp: [agents] | None, games} for this map, or None when they
    haven't played it (or nothing stands out)."""
    if not s:
        return None
    v = next((x for m, x in (s.get("maps") or {}).items() if m.lower() == map_name.lower()), None)
    if not v or not v.get("games"):
        return None
    pts = {"aggressive": 0.0, "defensive": 0.0, "execute": 0.0}
    why: dict[str, list[str]] = {k: [] for k in pts}

    def add(style, p, text):
        pts[style] += p
        why[style].append(text)

    att, dfn = v.get("attack") or {}, v.get("defense") or {}
    pt = att.get("plant_median_s")
    if pt and pt <= 40:
        add("defensive", 2, f"they hit fast (plant around {pt} s): set-ups and utility for the first 30 seconds")
    elif pt and pt >= 70:
        add("aggressive", 1, f"they hit late (plant around {pt} s): take space early on defense")
    sites = att.get("sites_hit") or {}
    total = sum(x.get("plants", 0) for x in sites.values())
    if total >= 3:
        site, x = max(sites.items(), key=lambda kv: kv[1].get("plants", 0))
        if x.get("plants", 0) / total >= .6:
            add("defensive", 1.5, f"they plant {site} {x['plants'] / total:.0%} of the time: stack it with a sentinel")
    weak = [site for site, x in (dfn.get("enemy_plants") or {}).items()
            if x.get("plants", 0) >= 3 and (_pct(x.get("retakes_won")) or 1) <= .35]
    if weak:
        add("execute", 2, f"they lose most retakes on {', '.join(weak)}: take it with utility and play the post-plant")
    entry = max(s.get("players") or [], key=lambda p: p.get("first_duel_share", 0), default=None)
    if entry and entry.get("first_duel_share", 0) >= .25 and (entry.get("first_duels_won") or 0) >= .55:
        add("defensive", 1.5, f"{entry['name']} ({entry['agents'][0]['agent']}) wins {entry['first_duels_won']:.0%} of "
                              "their first duels: don't take his duels, trap and trade him")
    comps = v.get("comps") or []
    their = comps[0]["agents"] if comps else None
    if their:
        n = _roles(their)
        if n.get("Duelist", 0) >= 2:
            add("defensive", 1, "they play two duelists: hold with set-ups, let them come")
        if n.get("Sentinel", 0) >= 2 or (n.get("Controller", 0) >= 2 and n.get("Duelist", 0) == 0):
            add("execute", 1, "their comp holds sites slowly (" + ", ".join(their) + "): break set-ups with utility")
        if n.get("Initiator", 0) == 0:
            add("aggressive", 1, "they have no initiator: little info, punish them with fast hits")
    sides = v.get("sides") or {}
    a, d = sides.get("attack"), sides.get("defense")
    if a is not None and d is not None:
        if a - d >= .1:
            add("defensive", 1, f"they're better on attack ({a:.0%} of rounds) than on defense ({d:.0%})")
        elif d - a >= .1:
            add("execute", 1, f"they're better on defense ({d:.0%} of rounds) than on attack ({a:.0%}): you need a plan to break their sites")
    best = max(pts, key=lambda k: pts[k])
    if pts[best] < MIN_POINTS:
        return {"style": "balanced", "points": pts[best], "games": v["games"], "their_comp": their,
                "reasons": ["nothing in their games stands out enough for a counter style"]}
    return {"style": best, "points": pts[best], "reasons": why[best], "their_comp": their, "games": v["games"]}
