"""Team review evening: click through one match round by round together. Everyone marks his own rounds
("my fault", "good", "talk about it", with a short note); at the end a summary shows the rounds to talk about,
each player's rounds, and the themes behind the flagged rounds, which go into the practice plan.

No model is needed. The round facts come from the match data (kills, plant, buys) and are worked out once,
when the evening is started.

4.74 (the scrim review): where each kill happened (the killer's and the victim's callout), each player's utility
per round (C, Q, E, X casts, when Riot's data has them), the comp you played against your comp for the map (the
draft marked "our comp"), and per round the strat you ran (picked in the evening) against the utility used."""
from __future__ import annotations

from collections import Counter, defaultdict

from ..models import Match
from .games import casts as _casts
from .rounds import kind

KEYS = {"grenade": "C", "ability1": "Q", "ability2": "E", "ultimate": "X"}
STRAT_SLOTS = {"grenade": "C", "ability1": "Q", "ability2": "E", "ultimate": "X"}   # the strat book's slot names

MARKS = {"fault": "My fault", "good": "Good", "talk": "Talk about it"}
TRADE_MS = 3000
RESULTS = {"Elimination": "everyone killed", "Bomb detonated": "spike exploded", "Bomb defused": "spike defused",
           "Round timer expired": "time ran out", "Surrendered": "surrendered"}

# round tag -> (what it means, practice item title, practice item text)
THEMES = {
    "lead_lost": ("lost with a man advantage", "Closing out rounds",
                  "Customs from 5v3 and 4v2: group up, trade, play for the plant or the time. "
                  "Nobody chases a kill alone when you're ahead."),
    "first_kill_lost": ("lost after taking the first kill", "Playing after the first kill",
                        "After the opening kill: say where the space is, take it together, trade the next fight. "
                        "Run it 5 times on attack and 5 on defense in a custom."),
    "opening_lost": ("lost the opening duel", "First-duel drill",
                     "1v1 peeks in a custom game, first with utility (flash, recon, smoke) before the duel, "
                     "then dry peeks only when a teammate can trade."),
    "untraded": ("a death wasn't traded", "Trade drill",
                 "2v2 and 3v3 in a custom game: entry + trader pairs, the trader 1 to 2 seconds behind. "
                 "Swap roles every 3 rounds."),
    "postplant_lost": ("lost the post-plant", "Post-plant customs",
                       "Plant on both sites and hold it: everyone says his spot and his job before the round, "
                       "utility saved for the defuse."),
    "retake_lost": ("lost the retake", "Retake customs",
                    "Retake both sites from 3v3 and 4v4: wait for each other, utility first, one call for the entry."),
    "pistol_lost": ("lost the pistol round", "Pistol plan",
                    "Agree on the pistol buy and the plan per side, then run it 3 times in a custom game."),
    "anti_eco_lost": ("lost against a saving team", "Anti-eco rounds",
                      "Against saving teams: keep distance, no wide peeks into shotguns, trade every fight."),
    "force_lost": ("lost a force buy", "When to force",
                   "Talk through the buy rules: when the team forces, when it saves, and who drops whom."),
}


def _fmt(ms: int) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def our_side(m: Match, puuids: set[str]) -> str | None:
    """The team id with most of our players (at least two)."""
    c = Counter(p.team for p in m.players.values() if p.puuid in puuids)
    if not c:
        return None
    team, n = c.most_common(1)[0]
    return team if n >= 2 else None


def util_of(ac: dict) -> dict[str, int]:
    """Riot's casts of one player in one round -> {"C": n, "Q": n, "E": n, "X": n}."""
    return {KEYS[k]: v for k, v in _casts(ac).items()}


def round_facts(m: Match, side: str, area=None) -> list[dict]:
    """Every round in plain facts for the evening (the numbers people need to remember the round).
    area(x, y): the callout at a map position (4.74: where each kill was), or None."""
    other = m.other_team(side)
    name = {p.puuid: p.name for p in m.players.values()}
    agent = {p.puuid: p.agent for p in m.players.values()}
    ours = [p for p in m.players_on(side)]
    out = []
    for rnd in m.rounds:
        won = rnd.winning_team == side
        us_avg = [s.loadout_value for s in rnd.stats.values() if s.team == side]
        them_avg = [s.loadout_value for s in rnd.stats.values() if s.team == other]
        us_buy = round(sum(us_avg) / len(us_avg)) if us_avg else 0
        them_buy = round(sum(them_avg) / len(them_avg)) if them_avg else 0
        has_buy = bool(us_avg and them_avg)
        kus, kthem = (kind(rnd.number, us_buy), kind(rnd.number, them_buy)) if has_buy else ("", "")
        alive = {side: len(ours) or 5, other: len(m.players_on(other)) or 5}
        lead = 0
        kills, deaths = [], {}
        for k in rnd.kills:
            if k.victim_team in alive:
                alive[k.victim_team] -= 1
            lead = max(lead, alive[side] - alive[other])
            kills.append({"t": _fmt(k.t_round_ms), "ms": k.t_round_ms, "k": name.get(k.killer, "spike" if not k.killer else "?"),
                          "ka": agent.get(k.killer, ""), "v": name.get(k.victim, "?"), "va": agent.get(k.victim, ""),
                          "ours": k.killer_team == side, "w": k.weapon or ("ability" if k.killer else ""),
                          **_where(k, area)})
            if k.victim_team == side:
                deaths[k.victim] = k
        # deaths of ours that a teammate paid back within 3 s
        untraded = []
        for pu, d in deaths.items():
            paid = any(k2.victim == d.killer and k2.killer_team == side and 0 <= k2.t_round_ms - d.t_round_ms <= TRADE_MS
                       for k2 in rnd.kills)
            if not paid and d.killer:
                untraded.append(name.get(pu, "?"))
        tags = []
        first = rnd.kills[0] if rnd.kills else None
        if not won and lead >= 2:
            tags.append("lead_lost")
        if first is not None:
            if first.killer_team == side and not won and "lead_lost" not in tags:
                tags.append("first_kill_lost")
            if first.victim_team == side and not won:
                tags.append("opening_lost")
        if untraded and not won:
            tags.append("untraded")
        planted = rnd.plant is not None
        planted_by_us = planted and (rnd.plant.team == side if rnd.plant.team else rnd.attacking_team == side)
        if planted and planted_by_us and not won:
            tags.append("postplant_lost")
        if planted and not planted_by_us and not won and alive[side] > 0 and rnd.defuse is None:
            tags.append("retake_lost")
        if kus == "pistol" and not won:
            tags.append("pistol_lost")
        if kus == "full" and kthem == "eco" and not won:
            tags.append("anti_eco_lost")
        if kus == "force" and not won:
            tags.append("force_lost")
        players = {}
        for p in ours:
            st = rnd.stats.get(p.puuid)
            players[p.name] = {"agent": p.agent, "k": st.kills if st else 0, "dmg": st.damage_dealt if st else 0,
                               "died": p.puuid in deaths, "loadout": st.loadout_value if st else 0,
                               "weapon": st.weapon if st else "", "first": bool(first and p.puuid in (first.killer, first.victim)),
                               "afk": bool(st and (st.was_afk or st.stayed_in_spawn))}
        own, opp = m.score_before(rnd.index + 1, side)
        out.append({
            "n": rnd.number, "side": rnd.side_of(side), "won": won, "result": RESULTS.get(rnd.result, rnd.result or ""),
            "score": f"{own}–{opp}", "buy": {"us": kus, "them": kthem, "us_avg": us_buy, "them_avg": them_buy} if has_buy else None,
            "first": ({"ours": first.killer_team == side, "k": name.get(first.killer, "?"), "v": name.get(first.victim, "?"),
                       "t": _fmt(first.t_round_ms)} if first else None),
            "plant": ({"site": rnd.plant.site, "ours": planted_by_us, "t": _fmt(rnd.plant.t_round_ms)} if planted else None),
            "defused": rnd.defuse is not None, "alive": [alive[side], alive[other]], "lead": lead, "untraded": untraded,
            "tags": tags, "why": [THEMES[t][0] for t in tags], "kills": kills, "players": players,
            "util": ({p.name: util_of(rnd.stats[p.puuid].ability_casts) for p in ours if p.puuid in rnd.stats}
                     if m.has_utility else None),
        })
    return out


def _where(k, area) -> dict:
    """4.74: the killer's and the victim's callout at the kill."""
    if area is None:
        return {}
    out = {}
    try:
        if k.victim_x or k.victim_y:
            out["vw"] = area(k.victim_x, k.victim_y)
        kl = k.loc_of(k.killer) if k.killer else None
        if kl is not None:
            out["kw"] = area(kl.x, kl.y)
    except Exception:
        return {}
    return {a: b for a, b in out.items() if b and not b.startswith("(")}


# ------------------------------------------------------------------------------------------------ 4.74: the plan
def comp_check(played: list[str], plan: list[str]) -> dict | None:
    """The agents you played against your comp for the map. None without a plan."""
    plan = [a for a in plan if a]
    if not plan:
        return None
    left = list(plan)
    same = []
    for a in played:
        if a in left:
            left.remove(a)
            same.append(a)
    extra = list(played)
    for a in same:
        extra.remove(a)
    return {"plan": plan, "played": list(played), "missing": left, "extra": extra, "same": not left and not extra}


def strat_util(data: dict) -> list[dict]:
    """The utility a strat board draws, per agent and key: [{agent, key, n}] (a thing carried over from the step
    before counts once)."""
    c: Counter = Counter()
    for st in (data or {}).get("steps") or []:
        for it in st.get("items") or []:
            if not isinstance(it, dict) or it.get("t") != "ab" or it.get("k"):
                continue
            key = STRAT_SLOTS.get(str(it.get("s") or "").lower())
            if key and it.get("a") and it.get("c", "us") != "them":
                c[(str(it["a"]), key)] += 1
    return [{"agent": a, "key": k, "n": n} for (a, k), n in sorted(c.items())]


def util_check(plan: list[dict], rnd: dict) -> list[dict] | None:
    """A strat's utility against what was used in the round: [{agent, key, planned, used, ok}], None when the
    match has no casts or nobody played that agent. A strat's agent nobody played: used None."""
    util = rnd.get("util")
    if not util:
        return None
    by_agent = {p["agent"]: util.get(n) or {} for n, p in (rnd.get("players") or {}).items()}
    out = []
    for x in plan:
        got = by_agent.get(x["agent"])
        used = None if got is None else int(got.get(x["key"], 0))
        out.append({**{"agent": x["agent"], "key": x["key"]}, "planned": x["n"], "used": used,
                    "ok": used is not None and used >= x["n"]})
    return out


def key_rounds(rounds: list[dict], limit: int = 8) -> list[int]:
    """Rounds worth stopping at when time is short: thrown leads, pistols, lost post-plants, swing rounds."""
    weight = {"lead_lost": 4, "postplant_lost": 3, "first_kill_lost": 2, "pistol_lost": 2, "anti_eco_lost": 2, "retake_lost": 1}
    scored = []
    for r in rounds:
        s = sum(weight.get(t, 0) for t in r["tags"])
        if r["buy"] and r["buy"]["us"] == "pistol":
            s += 1
        if r["won"] and r["buy"] and r["buy"]["us"] in ("eco", "force") and r["buy"]["them"] == "full":
            s += 2                                   # stolen rounds: worth seeing what went right
        if s:
            scored.append((s, r["n"]))
    return sorted(n for _, n in sorted(scored, reverse=True)[:limit])


def summarize(ev: dict) -> dict:
    """The evening's summary from the marks: counts, rounds to talk about, every player's rounds, themes and
    the practice items they lead to."""
    rounds = {r["n"]: r for r in ev.get("rounds", [])}
    marks: dict = ev.get("marks") or {}
    counts = Counter()
    per: dict[str, dict] = defaultdict(lambda: {"fault": [], "good": [], "talk": [], "notes": []})
    talk = []
    flagged_tags = Counter()
    flagged_by: dict[str, Counter] = defaultdict(Counter)
    marked_rounds = set()
    for n_s, by in marks.items():
        try:
            n = int(n_s)
        except ValueError:
            continue
        r = rounds.get(n)
        if r is None or not by:
            continue
        marked_rounds.add(n)
        talkers, notes = [], []
        flagged = False
        for player, mk in by.items():
            m = mk.get("m")
            if m not in MARKS:
                continue
            counts[m] += 1
            per[player][m].append(n)
            if mk.get("note"):
                per[player]["notes"].append({"n": n, "m": m, "note": mk["note"]})
                notes.append({"who": player, "m": m, "note": mk["note"]})
            if m == "talk":
                talkers.append(player)
            if m in ("fault", "talk"):
                flagged = True
            if m == "fault":
                for t in r["tags"]:
                    flagged_by[player][t] += 1
        if flagged:
            for t in r["tags"]:
                flagged_tags[t] += 1
        if talkers or any(x["m"] == "fault" for x in notes):
            talk.append({"n": n, "won": r["won"], "side": r["side"], "score": r["score"], "who": talkers,
                         "notes": notes, "why": r["why"]})
    themes = [{"tag": t, "rounds": c, "text": THEMES[t][0], "title": THEMES[t][1], "detail": THEMES[t][2]}
              for t, c in flagged_tags.most_common() if c >= 2 and t in THEMES]
    plan = [{"title": f"From the review evening: {x['title'].lower()}", "detail": x["detail"] +
             f" ({x['rounds']} of the rounds you flagged: {x['text']}.)", "who": "team", "minutes": 15} for x in themes[:2]]
    players = []
    for name, v in sorted(per.items(), key=lambda kv: (-len(kv[1]["fault"]), kv[0].lower())):
        top = flagged_by[name].most_common(1)
        focus = None
        if len(v["fault"]) >= 2 and top and top[0][1] >= 2:
            t = top[0][0]
            focus = {"title": THEMES[t][1], "text": THEMES[t][0], "rounds": top[0][1]}
            if not any(p["title"].endswith(THEMES[t][1].lower()) for p in plan) and len(plan) < 4:
                plan.append({"title": f"{THEMES[t][1]} for {name}", "detail": THEMES[t][2] +
                             f" ({top[0][1]} of {name}'s own rounds: {THEMES[t][0]}.)", "who": [name], "minutes": 10})
        players.append({"name": name, "fault": sorted(v["fault"]), "good": sorted(v["good"]), "talk": sorted(v["talk"]),
                        "notes": sorted(v["notes"], key=lambda x: x["n"]), "focus": focus})
    from .econreview import lines as econ_lines           # 4.76
    return {"econ": econ_lines(ev.get("econ")),
            "counts": {k: counts.get(k, 0) for k in MARKS}, "marked_rounds": len(marked_rounds), "rounds": len(rounds),
            "talk": sorted(talk, key=lambda x: x["n"]), "players": players, "themes": themes, "plan": plan}


def discord_text(ev: dict, s: dict, team: str) -> str:
    lines = [f"**Review evening ({team}): {ev['map']} {ev['score']} vs {ev['opponent']}**",
             f"{s['marked_rounds']} of {s['rounds']} rounds marked · {s['counts']['fault']}× my fault, "
             f"{s['counts']['good']}× good, {s['counts']['talk']}× talk about it"]
    if s["themes"]:
        lines.append("\n**What keeps coming up**")
        lines += [f"• {x['text'].capitalize()} ({x['rounds']} rounds)" for x in s["themes"][:3]]
    if s["talk"]:
        lines.append("\n**Rounds we talked about:** " + ", ".join(f"R{x['n']}" for x in s["talk"][:10]))
    if s["plan"]:
        lines.append("\n**Into the practice plan**")
        lines += [f"• {p['title']}" for p in s["plan"]]
    if s.get("prep"):                                        # 4.84: the boards drafted against them
        lines.append("\n**Our prep against them**")
        lines += [f"• {x}" for x in s["prep"]]
    return "\n".join(lines)[:1900]
