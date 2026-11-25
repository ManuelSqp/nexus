"""4.76: the economy of one match, round by round: your team's money against what it bought, and the rounds where
the buy didn't fit (for the review evening and the Premier match review).

Per round and player, Riot's data has the loadout value (what he played the round with) and the credits left
after buying. Loadout + credits left is what he had to spend ("money"; a weapon kept from the round before counts
as if bought, so it's what he was worth, the same thing the buy menu shows). Flags, our team only:

  half_buy      2+ bought (3000+) and 2+ saved (under 1500) in the same round: half a team on rifles
  could_buy     an eco or a force while 4 or more had the money for a full buy (3900 and a bit over)
  broken_force  a lost force, and the round after wasn't a full buy (it cost two rounds)
  no_rebuy      a lost full buy with no full buy the round after (nobody kept enough for a rebuy)
  off_buy       one player bought while the team saved, or saved while the team bought (named)

Pistol rounds and the rounds right after a half's switch don't get flags (everyone starts over)."""
from __future__ import annotations

from .rounds import FULL, kind

BOUGHT, SAVED = 3000, 1500
RICH = FULL + 600          # money per player that's a full buy with something over
LAST_FIRST_HALF = 12

TEXT = {
    "half_buy": "half the team bought, half saved",
    "could_buy": "a low buy with money for a full buy",
    "broken_force": "a lost force that broke the next round",
    "no_rebuy": "a lost full buy and no rebuy the round after",
}


def _first_of_half(n: int) -> bool:
    return n in (1, 13) or n >= 25


def review(m, side: str, names: dict[str, str] | None = None) -> dict | None:
    """{rounds: {"n": {money, bought, kind, them, won, flags: [key], off: [text], text: [text]}}, summary: {...}}
    or None without buy data."""
    names = names or {p.puuid: p.name for p in m.players.values()}
    other = m.other_team(side)
    rounds = sorted(m.rounds, key=lambda r: r.number)
    rows = []
    for r in rounds:
        ours = [s for s in r.stats.values() if s.team == side]
        theirs = [s for s in r.stats.values() if s.team == other]
        if not ours:
            rows.append(None)
            continue
        load = sum(s.loadout_value for s in ours) / len(ours)
        money = sum(s.loadout_value + max(0, s.remaining) for s in ours) / len(ours)
        tload = sum(s.loadout_value for s in theirs) / len(theirs) if theirs else 0
        rows.append({"n": r.number, "won": r.winning_team == side, "kind": kind(r.number, int(load)),
                     "them": kind(r.number, int(tload)) if theirs else "", "money": round(money), "bought": round(load),
                     "stats": ours})
    if not any(rows):
        return None
    out: dict[str, dict] = {}                                    # by round number as text (it goes into JSON)
    count = {k: [0, 0] for k in (*TEXT, "off_buy")}             # [rounds, of them lost]
    for i, x in enumerate(rows):
        if x is None:
            continue
        n, flags, off = x["n"], [], []
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if not _first_of_half(n):
            st = x["stats"]
            bought = sum(1 for s in st if s.loadout_value >= BOUGHT)
            saved = sum(1 for s in st if s.loadout_value < SAVED)
            rich = sum(1 for s in st if s.loadout_value + max(0, s.remaining) >= RICH)
            if bought >= 2 and saved >= 2:
                flags.append("half_buy")
            elif x["kind"] in ("eco", "force") and rich >= 4:
                flags.append("could_buy")
            next_full = nxt is not None and not _first_of_half(nxt["n"]) and nxt["kind"] == "full"
            next_counts = nxt is not None and not _first_of_half(nxt["n"])
            if x["kind"] == "force" and not x["won"] and next_counts and not next_full:
                flags.append("broken_force")
            if x["kind"] == "full" and not x["won"] and next_counts and not next_full:
                flags.append("no_rebuy")
            if "half_buy" not in flags:
                for s in st:
                    if x["kind"] == "eco" and s.loadout_value >= FULL:
                        off.append(f"{names.get(s.puuid, '?')} bought while the team saved")
                    elif x["kind"] == "full" and s.loadout_value < SAVED:
                        off.append(f"{names.get(s.puuid, '?')} saved while the team bought")
        for f in flags + (["off_buy"] if off else []):
            count[f][0] += 1
            count[f][1] += not x["won"]
        out[str(n)] = {"money": x["money"], "bought": x["bought"], "kind": x["kind"], "them": x["them"], "won": x["won"],
                  "flags": flags, "off": off, "text": [TEXT[f] for f in flags] + off}
    bad = [int(n) for n, x in out.items() if x["text"]]
    summary = {"flagged": bad, "lost": [n for n in bad if not out[str(n)]["won"]],
               "counts": {k: {"rounds": v[0], "lost": v[1]} for k, v in count.items() if v[0]}}
    return {"rounds": out, "summary": summary}


def lines(rv: dict | None) -> list[str]:
    """The summary in a few lines: "2× a lost force that broke the next round (rounds 4, 15)"."""
    if not rv:
        return []
    out = []
    for key, label in (*TEXT.items(), ("off_buy", "someone off the team's buy")):
        rs = sorted(int(n) for n, x in rv["rounds"].items() if (key in x["flags"] if key != "off_buy" else x["off"]))
        if rs:
            lost = sum(1 for n in rs if not rv["rounds"][str(n)]["won"])
            out.append(f"{len(rs)}× {label} (round{'s' if len(rs) > 1 else ''} {', '.join(map(str, rs))}; {lost} lost)")
    return out
