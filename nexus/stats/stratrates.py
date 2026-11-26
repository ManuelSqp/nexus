"""4.75: how your strats do. Every round you tag with a strat in a review evening (stats/evening.py, the 4.74
strat pick) counts for that strat: how often you ran it, how many of those rounds you won, and whether the utility
went in as drawn (every ability on the board used by its agent that round), with the rounds won both ways. Shown
on the strat book's cards, the strat's own page and in the evening's strat pick."""
from __future__ import annotations

from . import evening as ev_stats

MIN_ROUNDS = 5          # fewer rounds than this: the numbers are shown as "few rounds", no verdict


def rates(evenings: list[dict], utils: dict[int, list[dict]]) -> dict[int, dict]:
    """strat id -> {ran, won, pct, util_n (rounds with casts to check), util_ok (as drawn), won_ok, won_miss,
    few, last (the newest match's start), rounds: [{ev, n, won, score, opponent, at}] newest first}.
    utils: strat id -> its drawn utility (evening.strat_util)."""
    out: dict[int, dict] = {}
    for ev in evenings:
        rounds = {r.get("n"): r for r in ev.get("rounds") or [] if isinstance(r, dict)}
        for n, sid in (ev.get("strats") or {}).items():
            try:
                r = rounds.get(int(n))
            except (TypeError, ValueError):
                continue
            if r is None or not isinstance(sid, int) or sid not in utils:
                continue
            s = out.setdefault(sid, {"ran": 0, "won": 0, "util_n": 0, "util_ok": 0, "won_ok": 0, "won_miss": 0,
                                     "last": "", "rounds": []})
            won = bool(r.get("won"))
            s["ran"] += 1
            s["won"] += won
            chk = ev_stats.util_check(utils[sid], r) if utils[sid] else None
            if chk:
                s["util_n"] += 1
                ok = all(x["ok"] for x in chk)
                s["util_ok"] += ok
                s["won_ok" if ok else "won_miss"] += won
            at = ev.get("started_at") or ""
            s["last"] = max(s["last"], at)
            s["rounds"].append({"ev": ev.get("id"), "n": int(n), "won": won, "score": r.get("score", ""),
                                "opponent": ev.get("opponent", ""), "at": at})
    for s in out.values():
        s["pct"] = round(100 * s["won"] / s["ran"])
        s["few"] = s["ran"] < MIN_ROUNDS
        s["rounds"].sort(key=lambda x: (x["at"], x["n"]), reverse=True)
    return out


def text(s: dict | None) -> str:
    """One line for a card: "Ran 9 rounds · won 5 (56 %)"."""
    if not s:
        return ""
    return f"Ran {s['ran']} round{'s' if s['ran'] != 1 else ''} · won {s['won']} ({s['pct']} %)"


def util_text(s: dict | None) -> str:
    """"Utility as drawn in 5 of 8 · won 4 of those, 1 of the other 3"."""
    if not s or not s.get("util_n"):
        return ""
    miss = s["util_n"] - s["util_ok"]
    out = f"Utility as drawn in {s['util_ok']} of {s['util_n']}"
    if s["util_ok"] and miss:
        out += f" · won {s['won_ok']} of those, {s['won_miss']} of the other {miss}"
    return out


def best(strats: list[dict], rs: dict[int, dict]) -> dict[str, dict]:
    """Per side, the strat with the best record among those run often enough: {side: {id, name, pct, ran}}."""
    out: dict[str, dict] = {}
    for s in strats:
        r = rs.get(s["id"])
        if not r or r["few"]:
            continue
        cur = out.get(s["side"])
        if cur is None or (r["pct"], r["ran"]) > (cur["pct"], cur["ran"]):
            out[s["side"]] = {"id": s["id"], "name": s["name"], "pct": r["pct"], "ran": r["ran"]}
    return out
