"""4.78: how a scouted team plays its rounds, per map and per buy (pistol, eco, force, full buy), from their Premier
matches (the same ones as the rest of the scouting, stats/scouting.py):

  attack    which site they plant (shares), how fast (median plant time), when and where the first fight is, and
            how they're set up at that first fight: spread over the map ("default": two or more zones) or 4 or more
            in one zone ("stack"), and fast hits (a plant in the first 35 s)
  defense   how they stand at the first fight (players per zone: A, B, C, Mid, …) and how often they look for early
            picks (the first fight before 20 s, out of their sites)

Positions come from the kill events (Riot has everyone's position at every kill): the first kill of the round is
the first moment you see them all. Lines (for the "how to play them" box) only with enough rounds behind them."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from ..maps import MapRegistry
from .rounds import kind
from .teamdata import _map_info

BUYS = ("pistol", "eco", "force", "full")
BUY_TEXT = {"pistol": "pistols", "eco": "ecos", "force": "force buys", "full": "full buys"}
MIN_ROUNDS = 4               # a buy with fewer rounds on a map isn't described
FAST_PLANT_S = 35
EARLY_S = 20
SITES = ("A", "B", "C")


def _avg_loadout(rnd, team: str) -> int:
    vals = [s.loadout_value for s in rnd.stats.values() if s.team == team]
    return round(sum(vals) / len(vals)) if vals else 0


def _zones_at(k, team: str, mi) -> Counter:
    """Where a team's alive players stood at a kill: zone -> players (the victim counts where he fell)."""
    c: Counter = Counter()
    if mi is None:
        return c
    for pl in k.player_locations:
        if pl.team == team:
            c[mi.zone(pl.x, pl.y)] += 1
    if k.victim_team == team and (k.victim_x or k.victim_y) and not k.loc_of(k.victim):
        c[mi.zone(k.victim_x, k.victim_y)] += 1
    c.pop("?", None)
    return c


def _blank_att() -> dict:
    return {"rounds": 0, "won": 0, "plants": Counter(), "plant_won": Counter(), "plant_t": [], "first_t": [],
            "first_area": Counter(), "spread": 0, "stack": 0, "stack_zone": Counter(), "fast": 0, "seen": 0}


def _blank_def() -> dict:
    return {"rounds": 0, "won": 0, "zones": defaultdict(int), "seen": 0, "early": 0, "first_area": Counter()}


def analyse(items: list, cache_dir: Path) -> dict:
    """items: [(Match, their team)] -> {map: {"attack": {buy: {...}}, "defense": {buy: {...}}, "lines": [...]}}."""
    reg, mcache = MapRegistry(cache_dir), {}
    raw: dict[str, dict] = defaultdict(lambda: {"attack": defaultdict(_blank_att), "defense": defaultdict(_blank_def)})
    for m, team in items:
        mi = _map_info(reg, m, mcache)
        for rnd in m.rounds:
            if not rnd.stats:
                continue
            buy = kind(rnd.number, _avg_loadout(rnd, team))
            side = rnd.side_of(team)
            won = rnd.winning_team == team
            k0 = rnd.kills[0] if rnd.kills else None
            if side == "attack":
                a = raw[m.map_name]["attack"][buy]
                a["rounds"] += 1
                a["won"] += won
                if rnd.plant and rnd.plant.site:
                    a["plants"][rnd.plant.site] += 1
                    a["plant_won"][rnd.plant.site] += won
                    a["plant_t"].append(rnd.plant.t_round_ms / 1000)
                    a["fast"] += rnd.plant.t_round_ms / 1000 <= FAST_PLANT_S
                if k0:
                    a["first_t"].append(k0.t_round_ms / 1000)
                    if mi:
                        a["first_area"][mi.area(k0.victim_x, k0.victim_y)] += 1
                    z = _zones_at(k0, team, mi)
                    if z:
                        a["seen"] += 1
                        zone, n = z.most_common(1)[0]
                        if n >= 4:
                            a["stack"] += 1
                            a["stack_zone"][zone] += 1
                        elif len(z) >= 2:
                            a["spread"] += 1
            else:
                d = raw[m.map_name]["defense"][buy]
                d["rounds"] += 1
                d["won"] += won
                if k0:
                    z = _zones_at(k0, team, mi)
                    if z:
                        d["seen"] += 1
                        for zone, n in z.items():
                            d["zones"][zone] += n
                    if k0.t_round_ms / 1000 <= EARLY_S and mi:
                        area_zone = mi.zone(k0.victim_x, k0.victim_y)
                        if area_zone not in SITES:            # out of their sites: they went looking for it
                            d["early"] += 1
                            d["first_area"][mi.area(k0.victim_x, k0.victim_y)] += 1
    out = {}
    for mp, sides in raw.items():
        att = {b: _att_out(x) for b, x in sides["attack"].items() if x["rounds"]}
        dfn = {b: _def_out(x) for b, x in sides["defense"].items() if x["rounds"]}
        out[mp] = {"attack": {b: att[b] for b in BUYS if b in att}, "defense": {b: dfn[b] for b in BUYS if b in dfn}}
        out[mp]["lines"] = lines(mp, out[mp])
    return out


def _share(c: Counter) -> list[dict]:
    total = sum(c.values())
    return [{"site": s, "n": n, "share": round(n / total, 2)} for s, n in c.most_common()] if total else []


def _att_out(x: dict) -> dict:
    planted = sum(x["plants"].values())
    return {"rounds": x["rounds"], "won": x["won"], "sites": _share(x["plants"]),
            "site_won": dict(x["plant_won"]), "no_plant": x["rounds"] - planted,
            "plant_s": round(median(x["plant_t"])) if x["plant_t"] else None,
            "first_s": round(median(x["first_t"])) if x["first_t"] else None,
            "first_area": x["first_area"].most_common(1)[0][0] if x["first_area"] else "",
            "fast": x["fast"], "seen": x["seen"], "spread": x["spread"], "stack": x["stack"],
            "stack_zone": x["stack_zone"].most_common(1)[0][0] if x["stack_zone"] else ""}


def _def_out(x: dict) -> dict:
    seen = x["seen"] or 1
    setup = {z: round(n / seen, 1) for z, n in sorted(x["zones"].items(), key=lambda kv: -kv[1]) if n / seen >= 0.5}
    return {"rounds": x["rounds"], "won": x["won"], "seen": x["seen"], "setup": setup if x["seen"] else {},
            "early": x["early"], "early_area": x["first_area"].most_common(1)[0][0] if x["first_area"] else ""}


def setup_text(setup: dict) -> str:
    """{"A": 2.1, "Mid": 1.0, "B": 1.6} -> "2 A · 1 Mid · 2 B" (rounded players per zone, sites first)."""
    order = sorted(setup.items(), key=lambda kv: (kv[0] not in SITES, kv[0] if kv[0] in SITES else "", -kv[1]))
    return " · ".join(f"{round(n)} {z}" for z, n in order if round(n) >= 1)


def lines(mp: str, d: dict) -> list[str]:
    """What stands out, in a few lines (only buys with MIN_ROUNDS rounds or more)."""
    out = []
    for b in BUYS:
        a = d["attack"].get(b)
        if not a or a["rounds"] < MIN_ROUNDS:
            continue
        bits = []
        if a["sites"] and a["sites"][0]["share"] >= 0.6 and a["sites"][0]["n"] >= 3:
            s = a["sites"][0]
            bits.append(f"{s['site']} {round(s['share'] * 100)} % of their plants")
        if a["fast"] >= max(2, a["rounds"] * 0.4):
            bits.append(f"fast hits ({a['fast']} of {a['rounds']} planted in {FAST_PLANT_S} s)")
        elif a["plant_s"] and a["plant_s"] >= 70:
            bits.append(f"late hits (plant ~{a['plant_s']} s)")
        if a["seen"] >= MIN_ROUNDS and a["stack"] >= a["seen"] * 0.5:
            bits.append(f"stacked{' on ' + a['stack_zone'] if a['stack_zone'] else ''} at the first fight")
        elif a["seen"] >= MIN_ROUNDS and a["spread"] >= a["seen"] * 0.6:
            bits.append("a default (spread out) before they hit")
        if bits:
            out.append(f"{mp} attack, {BUY_TEXT[b]}: " + ", ".join(bits) + ".")
    for b in BUYS:
        x = d["defense"].get(b)
        if not x or x["rounds"] < MIN_ROUNDS:
            continue
        bits = []
        st = setup_text(x["setup"])
        if st and b in ("full", "force"):
            bits.append(f"they stand {st}")
        if x["early"] >= max(2, x["rounds"] * 0.35):
            bits.append(f"they look for early picks ({x['early']} of {x['rounds']} rounds"
                        + (f", mostly {x['early_area']}" if x["early_area"] else "") + ")")
        if bits:
            out.append(f"{mp} defense, {BUY_TEXT[b]}: " + ", ".join(bits) + ".")
    return out
