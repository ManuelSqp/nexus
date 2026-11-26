"""4.84: did the prep work? The boards drafted against a scouted team (4.79, a strat's data.prep = {team_id, team,
tag, made}) checked against the rounds you tagged with them in review evenings (the 4.74 strat pick): in the
evening of a match against that team (ran in which rounds, won how many, or not tagged at all), and over every
evening on the strat book's cards and the team's scouting page (against them, against others)."""
from __future__ import annotations


def _name(opp: str) -> str:
    return (opp or "").split("#", 1)[0].strip().lower()


def _tag(opp: str) -> str:
    return (opp or "").split("#", 1)[1].strip().lower() if "#" in (opp or "") else ""


def against(prep: dict, opp_id: str = "", opp: str = "") -> bool:
    """Is the board for this opponent? By the scouted team's id, else by "Name#TAG" (the review's opponent)."""
    if not isinstance(prep, dict):
        return False
    if opp_id and str(prep.get("team_id") or "") == str(opp_id):
        return True
    n, t = _name(opp), _tag(opp)
    if not n or n == "their team":
        return False
    pn, pt = (prep.get("team") or "").strip().lower(), (prep.get("tag") or "").strip().lower()
    return n == pn and (not t or not pt or t == pt)


def record(rate: dict | None, prep: dict) -> dict:
    """A board's rounds (stats/stratrates) split: {vs: {ran, won}, other: {ran, won}}."""
    out = {"vs": {"ran": 0, "won": 0}, "other": {"ran": 0, "won": 0}}
    for r in (rate or {}).get("rounds") or []:
        k = "vs" if against(prep, "", r.get("opponent", "")) else "other"
        out[k]["ran"] += 1
        out[k]["won"] += bool(r.get("won"))
    return out


def record_text(rec: dict, team: str) -> str:
    """"Against Rivals: won 3 of 4 rounds" (+ " · 1 of 2 against others"), or "" when never tagged."""
    vs, ot = rec["vs"], rec["other"]
    parts = []
    if vs["ran"]:
        parts.append(f"Against {team or 'them'}: won {vs['won']} of {vs['ran']} round{'s' if vs['ran'] != 1 else ''}")
    if ot["ran"]:
        parts.append(f"{ot['won']} of {ot['ran']} against others")
    return " · ".join(parts)


def evening(ev: dict, preps: list[dict], opp_id: str = "") -> list[dict]:
    """The boards against this evening's opponent on its map: [{id, name, side, ran, won, rounds: [{n, won}]}]."""
    rounds = {r.get("n"): r for r in ev.get("rounds") or [] if isinstance(r, dict)}
    tagged: dict[int, list] = {}
    for n, sid in (ev.get("strats") or {}).items():
        try:
            r = rounds.get(int(n))
        except (TypeError, ValueError):
            continue
        if r is not None and isinstance(sid, int):
            tagged.setdefault(sid, []).append({"n": int(n), "won": bool(r.get("won"))})
    out = []
    for p in preps:
        if p.get("map") != ev.get("map") or not against(p, opp_id, ev.get("opponent", "")):
            continue
        rs = sorted(tagged.get(p["id"], []), key=lambda x: x["n"])
        out.append({"id": p["id"], "name": p["name"], "side": p.get("side", ""), "ran": len(rs),
                    "won": sum(x["won"] for x in rs), "rounds": rs})
    return out


def lines(res: list[dict]) -> list[str]:
    out = []
    for x in res:
        side = f" ({x['side']})" if x["side"] else ""
        if x["ran"]:
            out.append(f"{x['name']}{side}: ran in {x['ran']} round{'s' if x['ran'] != 1 else ''} "
                       f"(R{', R'.join(str(r['n']) for r in x['rounds'])}), won {x['won']}")
        else:
            out.append(f"{x['name']}{side}: not tagged in any round. If you ran it, pick it in those rounds' strat pick")
    return out
