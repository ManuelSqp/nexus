"""4.61: the other options on the comps page, explained: what changes from the best comp, why each swap could make
sense (the player's numbers, his agent pool, the map rules) and when you'd pick it.

explain(main, alt) only reads the two comps (comp.best_comp / top_comps / webcomps.assign), nothing else."""
from __future__ import annotations

ROLE_GAIN = {                     # what one more agent of a role brings
    "Duelist": "more entry power",
    "Initiator": "more info and flashes",
    "Controller": "more smokes",
    "Sentinel": "holds sites and flanks better",
}
LOST = {
    "Duelist": "someone else takes first contact",
    "Initiator": "less info before you go in",
    "Controller": "no smokes",
    "Sentinel": "nobody watches the flank alone",
}
CLOSE, WEAKER = 6.0, 17.0         # points behind the best comp per changed agent: close / a bit weaker / a fallback
COMFORT_SCALE = 4.0               # "most comfortable" scores games played: a bigger scale


def _pct(x) -> str:
    return f"{round(x * 100)} %"


def facts(pick: dict, map_name: str) -> list[str]:
    """The numbers behind one pick, then the reasons the comp maker gave (pool rank, map rules, meta)."""
    out = []
    if pick.get("n_map"):
        out.append(f"{pick['n_map']} {'game' if pick['n_map'] == 1 else 'games'} on {map_name}"
                   + (f", {_pct(pick['wr_map'])} won" if pick.get("wr_map") is not None else ""))
    else:
        out.append(f"not played on {map_name} yet")
    if pick.get("n_all"):
        out.append(f"{pick['n_all']} overall" + (f", {_pct(pick['wr_all'])} won" if pick.get("wr_all") is not None else ""))
    elif not pick.get("new"):
        out.append("no games on it yet")
    for w in pick.get("why") or []:
        if w and not w[0].isdigit() and w not in out:     # comfort mode's own "n games on …" is already said
            out.append(w)
    return out


def _roles(picks: list[dict]) -> dict:
    n: dict[str, int] = {}
    for p in picks:
        n[p.get("role") or "?"] = n.get(p.get("role") or "?", 0) + 1
    return n


def explain(main: dict, alt: dict, map_name: str) -> dict:
    """-> {changes: [{player, agent, role, was, was_role, facts}], same: [players], drop, level, when: [lines]}"""
    before = {p["player"]: p for p in main.get("picks") or []}
    changes, same = [], []
    for p in alt.get("picks") or []:
        b = before.get(p["player"])
        if b and b["agent"] == p["agent"]:
            same.append(p["player"])
            continue
        changes.append({"player": p["player"], "agent": p["agent"], "role": p.get("role"),
                        "was": b["agent"] if b else None, "was_role": b.get("role") if b else None,
                        "facts": facts(p, map_name), "low": bool(p.get("low_sample")), "new": bool(p.get("new"))})
    drop = round(max(0.0, (main.get("total") or 0) - (alt.get("total") or 0)), 1)
    per = drop / max(1, len(changes)) / (COMFORT_SCALE if alt.get("method") == "comfort" else 1.0)
    level = "close to the best" if per < CLOSE else ("a bit weaker" if per < WEAKER else "a fallback")
    when = []
    gone = [b for b in main.get("picks") or [] if b["agent"] not in {p["agent"] for p in alt.get("picks") or []}]
    if gone:
        names = " or ".join(b["agent"] for b in gone[:2])
        who = gone[0]["player"] if len(gone) == 1 else "a player"
        when.append(f"if {names} doesn't work out: the other team plays around it, or {who} isn't comfortable on it that day")
    a, m = _roles(alt.get("picks") or []), _roles(main.get("picks") or [])
    gains = [ROLE_GAIN[r] for r in ROLE_GAIN if a.get(r, 0) > m.get(r, 0)]
    if gains:
        when.append("when you want " + " and ".join(gains))
    for r in ROLE_GAIN:
        if m.get(r, 0) and not a.get(r, 0):
            when.append(f"no {r} left: " + LOST[r])
    low = [c for c in changes if c["low"] or c["new"]]
    if low:
        when.append("needs practice first: " + ", ".join(f"{c['player']} on {c['agent']}" for c in low))
    note = ((alt.get("web") or {}).get("note") or "").strip()
    if note:
        when.append(f"from the web: {note}")
    return {"changes": changes, "same": same, "drop": drop, "level": level, "when": when}


def matches(comp: dict, agents: set[str]) -> bool:
    """The comp has exactly these 5 agents (e.g. the team's "our comp" draft)."""
    return bool(agents) and {p["agent"] for p in comp.get("picks") or []} == agents
