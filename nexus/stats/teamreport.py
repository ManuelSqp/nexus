"""4.80: the Sunday team report for Discord: the week in one post. Strats (the rounds you tagged in review evenings
this week, the best and the struggling strats so far), the economy of the week's matches (the rounds where the buy
didn't fit, stats/econreview.py), everyone's drills (stats/drills.team_week) and what's next (the next match day,
the map and the boards drafted against opponents for it).

Everything comes in already gathered (web/practice.py); this only decides what's worth a line."""
from __future__ import annotations

from .econreview import TEXT as ECON_TEXT

STRUGGLE_PCT = 35           # a strat run 5 times or more that wins this little is worth a look


def strat_section(week_rounds: list[dict], rates: dict[int, dict], strats: list[dict]) -> list[str]:
    """week_rounds: [{strat (id), won}] tagged this week; rates: stratrates.rates (all time); strats: [{id, name,
    map, side}]."""
    names = {s["id"]: s for s in strats}
    out = []
    if week_rounds:
        won = sum(1 for r in week_rounds if r["won"])
        by: dict[int, list] = {}
        for r in week_rounds:
            by.setdefault(r["strat"], []).append(r["won"])
        top = sorted(by.items(), key=lambda kv: -len(kv[1]))[:3]
        out.append(f"{len(week_rounds)} rounds tagged this week, {won} won: " + ", ".join(
            f"{names[s]['name']} {sum(w)}/{len(w)}" for s, w in top if s in names))
    good = [(names[s], r) for s, r in rates.items() if s in names and not r["few"]]
    if good:
        best = max(good, key=lambda x: (x[1]["pct"], x[1]["ran"]))
        out.append(f"Best so far: **{best[0]['name']}** ({best[0]['map']} {best[0]['side']}), "
                   f"{best[1]['pct']} % of {best[1]['ran']} rounds")
        bad = [x for x in good if x[1]["pct"] <= STRUGGLE_PCT and x[0]["id"] != best[0]["id"]]
        for s, r in sorted(bad, key=lambda x: x[1]["pct"])[:2]:
            ut = f", utility as drawn in {r['util_ok']} of {r['util_n']}" if r.get("util_n") else ""
            out.append(f"Struggling: **{s['name']}** ({s['map']} {s['side']}), {r['pct']} % of {r['ran']} rounds{ut}")
    return out


def econ_section(matches: list[dict]) -> list[str]:
    """matches: [{label, econ (econreview.review)}] of the week."""
    counts: dict[str, list] = {}
    for m in matches:
        for n, x in (m["econ"] or {}).get("rounds", {}).items():
            for f in x.get("flags") or []:
                counts.setdefault(f, []).append((m["label"], int(n), x["won"]))
            if x.get("off"):
                counts.setdefault("off_buy", []).append((m["label"], int(n), x["won"]))
    if not matches:
        return []
    if not counts:
        return [f"Every buy fit the money in {len(matches)} {'match' if len(matches) == 1 else 'matches'}."]
    out = []
    order = list(ECON_TEXT) + ["off_buy"]
    for f in sorted(counts, key=lambda k: (-len(counts[k]), order.index(k))):
        xs = counts[f]
        lost = sum(1 for x in xs if not x[2])
        label = ECON_TEXT.get(f, "someone off the team's buy")
        where = "; ".join(f"{lab} R{n}" for lab, n, _ in xs[:3]) + (" …" if len(xs) > 3 else "")
        out.append(f"{len(xs)}× {label} ({lost} lost): {where}")
    return out[:4]


def drills_section(tw: dict) -> list[str]:
    """A short version of the drill week (the full one is its own post, 4.67)."""
    ps = [p for p in tw.get("players") or [] if p.get("sessions")]
    if not ps:
        return ["Nobody drilled this week."]
    out = [", ".join(f"{p['name']} {p['sessions']}×" for p in sorted(ps, key=lambda p: -p["sessions"]))]
    top = tw.get("top")
    if top:
        from .drills import change_text, drill_name
        out.append(f"Biggest step: {top['name']}, {drill_name(top['drill'])}: {change_text(top['drill'])}")
    reached = sum(len(p.get("goals_reached") or []) for p in tw.get("players") or [])
    if reached:
        out.append(f"{reached} drill goal{'s' if reached != 1 else ''} reached")
    if tw.get("idle"):
        out.append(f"No drills: {', '.join(tw['idle'])}")
    return out


def next_section(nxt: dict | None) -> list[str]:
    """nxt: {day (e.g. "Thu 3.12. 20:00"), map, where (the map's source), prep: [names]}."""
    if not nxt:
        return []
    out = []
    if nxt.get("day"):
        out.append(f"Next match: **{nxt['day']}**" + (f" on **{nxt['map']}**" if nxt.get("map") else ""))
    elif nxt.get("map"):
        out.append(f"This week's map: **{nxt['map']}**")
    if nxt.get("prep"):
        out.append("Boards against opponents: " + ", ".join(nxt["prep"][:4]))
    elif nxt.get("map"):
        out.append("No boards against opponents yet: scout them and press *Draft a plan in the strat book*.")
    return out


def embeds(team: str, week: str, strats: list[str], econ: list[str], drills: list[str], nxt: list[str]) -> list[dict]:
    from ..discord import TEAL, _cut
    fields = [(n, v) for n, v in (("📒 Strats", strats), ("💰 Economy", econ), ("🎯 Drills", drills), ("🗓️ Next", nxt)) if v]
    if not fields:
        fields = [("📒 This week", ["Nothing to report: no reviewed rounds, matches or drills this week."])]
    return [{"title": _cut(f"{team}: the week", 256), "color": TEAL,
             "fields": [{"name": n, "value": _cut("\n".join(v), 1024), "inline": False} for n, v in fields],
             "footer": {"text": f"{team} · week {week} · Nexus"}}]
