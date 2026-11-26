"""4.83: the lineups a strat needs. Every ability our side draws on a strat board, step by step, matched with the
team's lineups library (the agent and ability, the site it lands on, the side, the callout in its title), with
the clip; for the ones the library has nothing for, a lineup your team throws in its replay files (lineups.py
suggestions) or a nudge to add one. Pure functions: the web layer passes the library, the callouts and the
ability names."""
from __future__ import annotations

from typing import Callable

SITES = ("A", "B", "C", "Mid")


def uses(data: dict, ab_name: Callable[[str, str], str], place: Callable[[float, float], tuple[str, str]]) -> list[dict]:
    """The abilities of our side per step: [{step, uses: [{agent, ability, slot, site, near, player}]}]. ab_name(agent,
    slot) -> the ability's name (or ""); place(x, y) -> (callout, site) for board units (0..1000). The player is the
    label of our agent token of that agent (any step). Steps without abilities are left out; the same ability
    to the same callout once per step."""
    steps = [s for s in (data or {}).get("steps") or [] if isinstance(s, dict)]
    players: dict[str, str] = {}
    for st in steps:
        for it in st.get("items") or []:
            if isinstance(it, dict) and it.get("t") == "agent" and it.get("c", "us") != "them" and it.get("label") and it.get("a"):
                players.setdefault(it["a"], str(it["label"]))
    out = []
    for n, st in enumerate(steps, 1):
        seen, us = set(), []
        for it in st.get("items") or []:
            if not isinstance(it, dict) or it.get("t") != "ab" or it.get("c", "us") == "them" or not it.get("a"):
                continue
            try:
                x, y = float(it.get("x")), float(it.get("y"))
            except (TypeError, ValueError):
                continue
            near, site = place(x, y)
            ability = ab_name(it["a"], str(it.get("s") or "")) or str(it.get("s") or "")
            key = (it["a"], ability, near)
            if key in seen:
                continue
            seen.add(key)
            us.append({"agent": it["a"], "ability": ability, "slot": str(it.get("s") or ""), "site": site if site in SITES else "",
                       "near": near, "player": players.get(it["a"], "")})
        if us:
            out.append({"step": str(st.get("name") or f"Step {n}")[:40], "uses": us})
    return out


def _score(lu: dict, use: dict, side: str) -> int | None:
    """How well a library lineup fits the use: None if it's for another agent, ability, site or side."""
    if lu.get("agent") != use["agent"]:
        return None
    if lu.get("ability") and use["ability"] and lu["ability"] != use["ability"]:
        return None
    if lu.get("site") and use["site"] and lu["site"] != use["site"]:
        return None
    if lu.get("side") and side and lu["side"] != side:
        return None
    sc = 0
    sc += 4 if lu.get("ability") and lu["ability"] == use["ability"] else 0
    sc += 3 if lu.get("site") and lu["site"] == use["site"] else 0
    sc += 1 if lu.get("side") and lu["side"] == side else 0
    sc += 2 if use["near"] and use["near"].lower() in (lu.get("title") or "").lower() else 0
    sc += 1 if lu.get("url") else 0
    return sc


def match(steps: list[dict], library: list[dict], side: str, ideas: list[dict] | None = None) -> list[dict]:
    """Each use gets lineup (the best library entry: {id, title, url, notes, site}) and more (how many others fit), or
    idea (a replay lineup of that agent and ability on that site: {title, notes}) when the library has none."""
    for st in steps:
        for u in st["uses"]:
            fit = sorted(((sc, lu) for lu in library if (sc := _score(lu, u, side)) is not None),
                         key=lambda p: (-p[0], (p[1].get("title") or "").lower()))
            u["lineup"] = ({k: fit[0][1].get(k, "") for k in ("id", "title", "url", "notes", "site")} if fit else None)
            u["more"] = max(0, len(fit) - 1)
            u["idea"] = None
            if not fit:
                for x in ideas or []:
                    if x.get("agent") == u["agent"] and (not x.get("ability") or x["ability"] == u["ability"]) \
                            and (not u["site"] or not x.get("site") or x["site"] == u["site"]):
                        u["idea"] = {"title": x.get("title", ""), "notes": x.get("notes", "")}
                        break
    return steps


def who(u: dict) -> str:
    return f"{u['agent']} ({u['player']})" if u.get("player") else u["agent"]


def lines(steps: list[dict], step: str = "") -> list[str]:
    """For Discord: one line per ability (of one step, if named), the clip as a link."""
    out = []
    for st in steps:
        if step and st["step"] != step:
            continue
        for u in st["uses"]:
            head = f"{who(u)} · {u['ability']}" + (f" → {u['near']}" if u["near"] else "")
            lu = u.get("lineup")
            if lu and lu.get("url"):
                out.append(f"{head}: [{lu['title'].replace('[', '(').replace(']', ')')}](<{lu['url']}>)")
            elif lu:
                out.append(f"{head}: {lu['title']}")
            elif u.get("idea"):
                out.append(f"{head}: none in the library, you throw “{u['idea']['title']}” in your replays")
            else:
                out.append(f"{head}: no lineup in the library yet")
    return out


def missing(steps: list[dict]) -> int:
    return sum(1 for st in steps for u in st["uses"] if not u.get("lineup"))
