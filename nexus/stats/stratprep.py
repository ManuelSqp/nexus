"""4.79: a plan against a scouted team, drafted into your strat book: per map one board for your attack (their
defense drawn as enemies where they stand at the first fight, the site with fewer of them marked) and one for your
defense (their attack: where they plant on full buys, stacked or spread, how fast). Each comes with a call and
notes from their scouting (stats/scouting.py, stats/roundplay.py). You edit them from there; on match day the
brief lists them.

Positions on the board are the zones' middles (the average of the map's callouts in a zone, as board units 0-1000,
like the editor's)."""
from __future__ import annotations

import math

S = 1000
SITES = ("A", "B", "C")


def zone_centres(callouts: list[tuple[str, float, float]]) -> dict[str, tuple[float, float]]:
    """[(zone, u, v)] (u, v 0..1) -> {zone: (x, y)} in board units."""
    acc: dict[str, list] = {}
    for z, u, v in callouts:
        acc.setdefault(z, []).append((u, v))
    return {z: (round(sum(p[0] for p in ps) / len(ps) * S), round(sum(p[1] for p in ps) / len(ps) * S)) for z, ps in acc.items()}


def _spread(x: float, y: float, n: int, r: float = 38) -> list[tuple[int, int]]:
    """n tokens around a point, so they don't sit on each other."""
    if n <= 1:
        return [(round(x), round(y))][:n]
    return [(round(x + r * math.cos(2 * math.pi * k / n)), round(y + r * math.sin(2 * math.pi * k / n))) for k in range(n)]


def _agents(s: dict, map_name: str) -> list[str]:
    """Their five on this map (their most played comp there, else overall)."""
    for c in ((s.get("maps") or {}).get(map_name) or {}).get("comps") or []:
        if len(c.get("agents") or []) >= 5:
            return list(c["agents"])[:5]
    for c in s.get("comps") or []:
        if len(c.get("agents") or []) >= 5:
            return list(c["agents"])[:5]
    return []


def _tokens(agents: list[str], where: list[tuple[str, int]], centres: dict, start: int = 0) -> list[dict]:
    """Enemy tokens: where = [(zone, players)], their agents in order (no agent known: a numbered enemy)."""
    out, k = [], 0
    for zone, n in where:
        if zone not in centres or n <= 0:
            continue
        for x, y in _spread(*centres[zone], n):
            a = agents[k] if k < len(agents) else ""
            it = {"id": f"p{start + k}", "x": x, "y": y, "c": "them"}
            it.update({"t": "agent", "a": a} if a else {"t": "num", "n": k + 1})
            out.append(it)
            k += 1
    return out


def _mark(centres: dict, zone: str, label: str, i: int) -> list[dict]:
    if zone not in centres:
        return []
    x, y = centres[zone]
    return [{"id": f"m{i}", "t": "mark", "s": "!", "x": x, "y": y - 70},
            {"id": f"l{i}", "t": "text", "s": label[:80], "x": x, "y": y - 110, "c": "them", "size": 20}]


def _site_share(att: dict) -> list[dict]:
    return att.get("sites") or []


def plans(s: dict, map_name: str, centres: dict, lines: list[str] | None = None) -> list[dict]:
    """[{side, name, call, notes, items}] for one map; empty without enough to say."""
    play = (s.get("play") or {}).get(map_name) or {}
    who = s.get("tag") or s.get("name") or "them"
    agents = _agents(s, map_name)
    notes = "\n".join(f"- {x}" for x in (lines or []))
    out = []

    # your defense: their attack on full buys (else whatever buy has the most rounds)
    att = play.get("attack") or {}
    a = att.get("full") or max(att.values(), key=lambda x: x["rounds"], default=None)
    if a and a.get("rounds", 0) >= 3:
        sites = _site_share(a)
        main = sites[0]["site"] if sites else ""
        if a.get("stack") and a.get("stack_zone") and a["stack"] >= (a.get("seen") or 1) * 0.5:
            where = [(a["stack_zone"], 4)] + [("Mid" if a["stack_zone"] != "Mid" else (main or "A"), 1)]
            shape = f"stacked {a['stack_zone']}"
        else:
            others = [x["site"] for x in sites[1:2]]
            where = [(main or "A", 3), ("Mid", 1)] + [(others[0] if others else ("B" if main == "A" else "A"), 1)]
            shape = "spread, then hit"
        share = f"{main} {round(sites[0]['share'] * 100)} %" if sites else "no clear site"
        fast = a.get("fast", 0) >= max(2, a["rounds"] * 0.4)
        call = (f"They hit {share} of plants, {'fast' if fast else 'plant ~' + str(a['plant_s']) + ' s' if a.get('plant_s') else ''}"
                f" ({shape}). " + (f"Stack {main}, rotate from the other site on contact." if sites and sites[0]["share"] >= 0.6
                                   else "Play your default; info on Mid decides the rotate.")).replace(" ,", ",")
        items = _tokens(agents, where, centres) + (_mark(centres, main, f"{share} of their plants", 0) if main else [])
        out.append({"side": "defense", "name": f"vs {who}: their hit", "call": call[:200], "items": items,
                    "notes": f"Their attack on {map_name} (from their Premier matches):\n{notes}".strip()})

    # your attack: their defense at the first fight
    dfn = play.get("defense") or {}
    d = dfn.get("full") or max(dfn.values(), key=lambda x: x["rounds"], default=None)
    if d and d.get("setup"):
        setup = d["setup"]
        where = [(z, round(n)) for z, n in setup.items() if round(n) >= 1]
        sites = [(z, setup.get(z, 0)) for z in SITES if z in centres]
        weak = min(sites, key=lambda x: x[1])[0] if sites else ""
        retake_weak = ""
        from .scouting import _pct
        for site, x in ((((s.get("maps") or {}).get(map_name) or {}).get("defense") or {}).get("enemy_plants") or {}).items():
            w = _pct(x.get("retakes_won"))
            if x.get("plants", 0) >= 3 and w is not None and w <= .35:
                retake_weak = site
        early = d.get("early", 0) >= max(2, d["rounds"] * 0.35)
        bits = [f"They stand {' · '.join(f'{round(n)} {z}' for z, n in where)}."]
        if weak:
            bits.append(f"Hit {weak} (the fewest of them).")
        if retake_weak:
            bits.append(f"They lose retakes on {retake_weak}: plant {retake_weak} and play post-plant.")
        if early:
            bits.append(f"They look for early picks{' at ' + d['early_area'] if d.get('early_area') else ''}: "
                        "don't take that fight first, hit late.")
        items = _tokens(agents, where, centres) + (_mark(centres, weak, "fewest of them", 1) if weak else [])
        out.append({"side": "attack", "name": f"vs {who}: their setup", "call": " ".join(bits)[:200], "items": items,
                    "notes": f"Their defense on {map_name} (from their Premier matches):\n{notes}".strip()})
    return out
