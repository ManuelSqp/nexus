"""Ask the coach (4.57): the coach picks the games a question is about.

Before it answers, the model sees what games there are (how many per mode, agent, map, from when to when, and the
last few one by one) and picks the ones the question needs: "my last two Premier games", "my KAY/O games", "Summit
this month", or none in particular (then it has the usual picture: recent form and the whole history). Those games
go into its data one by one with their numbers, plus what they add up to."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

import yaml

from .prompts import field_guide

QUEUE_NAMES = {"competitive": "Competitive", "premier": "Premier", "unrated": "Unrated", "swiftplay": "Swiftplay",
               "deathmatch": "Deathmatch", "teamdeathmatch": "Team Deathmatch", "spikerush": "Spike Rush"}
MAX_GAMES = 15                   # one by one in the answer's data (more are only added up)
INDEX_LAST = 12                  # the last games one by one for the picker

SYSTEM = """You help a Valorant coach answer a player's question. Below is a list of the player's stored games.
Decide which games the question is about:
- "none": the question isn't about particular games (general advice, the game itself, their aim, overall form):
  the coach uses its usual picture (recent form and the whole history).
- "pick": particular games: say which with the filters (all of them must match; leave a filter empty for "any").
  queues: from the modes listed. agents / maps: names as listed. last: only the newest N of those (0 = all).
  days: only games of the last N days (0 = any).
Examples: "my last two Premier games" -> pick, queues [premier], last 2. "how am I on KAY/O" -> pick, agents
[KAY/O]. "KAY/O or Clove in Premier lately?" -> pick, queues [premier], agents [KAY/O, Clove], days 30.
"how do I counter-strafe" -> none.
"why": one short sentence in English saying which games and why."""
SCHEMA = {"type": "object", "properties": {
    "use": {"type": "string", "enum": ["none", "pick"]},
    "queues": {"type": "array", "items": {"type": "string"}},
    "agents": {"type": "array", "items": {"type": "string"}},
    "maps": {"type": "array", "items": {"type": "string"}},
    "last": {"type": "integer"},
    "days": {"type": "integer"},
    "why": {"type": "string"}},
    "required": ["use", "queues", "agents", "maps", "last", "days", "why"]}


def _date(r: dict) -> str:
    return str(r.get("started_at") or "")[:10]


def _when(r: dict) -> datetime | None:
    s = str(r.get("started_at") or "")
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def newest_first(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: str(r.get("started_at") or ""), reverse=True)


def _result(r: dict) -> str:
    w = r.get("won")
    return "win" if w == 1.0 else "loss" if w == 0.0 else "draw"


def line(r: dict) -> str:
    """One game in a line: 2026-11-22 Premier Summit Clove win 13-9, 18/12/5, ACS 252."""
    q = QUEUE_NAMES.get(r.get("queue") or "", (r.get("queue") or "?").title())
    return (f"{_date(r)} {q} {r.get('map', '?')} {r.get('agent', '?')} {_result(r)} {r.get('score', '')}, "
            f"{r.get('kills', 0)}/{r.get('deaths', 0)}/{r.get('assists', 0)}, ACS {round(r.get('acs') or 0)}")


def index(rows: list[dict]) -> dict:
    """What there is to pick from."""
    rs = newest_first(rows)
    cnt = lambda key: dict(Counter(str(r.get(key) or "?") for r in rs).most_common())    # noqa: E731
    return {"games": len(rs), "from": _date(rs[-1]) if rs else "", "to": _date(rs[0]) if rs else "",
            "modes": cnt("queue"), "agents": cnt("agent"), "maps": cnt("map"),
            "newest": [line(r) for r in rs[:INDEX_LAST]]}


def plan(llm, question: str, history: list[dict], rows: list[dict]) -> dict | None:
    """The model's pick, or None (nothing in particular / it failed: the coach goes on as before)."""
    if not rows:
        return None
    convo = "\n".join(f"Q: {h['q']}\nA: {str(h.get('a', ''))[:200]}" for h in history[-2:])
    user = ("The player's games:\n" + yaml.safe_dump(index(rows), sort_keys=False, allow_unicode=True, width=120) +
            (f"\nThe conversation so far:\n{convo}\n" if convo else "") + f"\nQuestion: {question}")
    try:
        out = llm.chat_json(SYSTEM + field_guide(SCHEMA), user, SCHEMA)
    except Exception:
        return None
    if not isinstance(out, dict) or out.get("use") != "pick":
        return None
    clean = lambda xs: [str(x).strip() for x in (xs if isinstance(xs, list) else []) if str(x).strip()][:8]  # noqa: E731
    num = lambda v: max(0, min(500, int(v))) if isinstance(v, (int, float)) else 0                          # noqa: E731
    return {"queues": clean(out.get("queues")), "agents": clean(out.get("agents")), "maps": clean(out.get("maps")),
            "last": num(out.get("last")), "days": num(out.get("days")), "why": str(out.get("why") or "")[:200]}


def _norm(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def select(rows: list[dict], f: dict, now: datetime | None = None) -> list[dict]:
    """The games the pick names, newest first. Names are matched loosely (kayo = KAY/O, "Premier" = premier)."""
    qs = {_norm(q) for q in f.get("queues") or []}
    ags = {_norm(a) for a in f.get("agents") or []}
    mps = {_norm(m) for m in f.get("maps") or []}
    since = None
    if f.get("days"):
        since = (now or datetime.now(timezone.utc)) - timedelta(days=int(f["days"]))
    out = []
    for r in newest_first(rows):
        if qs and _norm(r.get("queue") or "") not in qs and _norm(QUEUE_NAMES.get(r.get("queue") or "", "")) not in qs:
            continue
        if ags and _norm(r.get("agent") or "") not in ags:
            continue
        if mps and _norm(r.get("map") or "") not in mps:
            continue
        if since is not None:
            w = _when(r)
            if w is None or w < since:
                continue
        out.append(r)
    return out[:f["last"]] if f.get("last") else out


def _game(r: dict) -> dict:
    n = max(1, int(r.get("rounds") or 0))
    shots = r.get("shots") or [0, 0, 0]
    hs = shots[0] / sum(shots) if sum(shots) else None
    g = {"date": _date(r), "mode": QUEUE_NAMES.get(r.get("queue") or "", r.get("queue") or "?"), "map": r.get("map"),
         "agent": r.get("agent"), "result": _result(r), "score": r.get("score"),
         "k/d/a": f"{r.get('kills', 0)}/{r.get('deaths', 0)}/{r.get('assists', 0)}", "acs": round(r.get("acs") or 0)}
    if r.get("source") == "full":
        g.update({"adr": round(r.get("adr") or 0), "kast": f"{(r.get('kast') or 0) / n:.0%}",
                  "first_kills": r.get("fk", 0), "first_deaths": r.get("fd", 0),
                  "headshots": None if hs is None else f"{hs:.0%}"})
    return {k: v for k, v in g.items() if v is not None}


def _sum(rs: list[dict]) -> dict:
    if not rs:
        return {}
    k = sum(r.get("kills", 0) for r in rs)
    d = sum(r.get("deaths", 0) for r in rs)
    full = [r for r in rs if r.get("source") == "full"]
    rounds = sum(max(1, int(r.get("rounds") or 0)) for r in full)
    out = {"games": len(rs), "win_rate": f"{sum(r.get('won') or 0 for r in rs) / len(rs):.0%}",
           "kd": round(k / max(1, d), 2), "acs": round(sum(r.get("acs") or 0 for r in rs) / len(rs))}
    if full:
        out.update({"adr": round(sum((r.get("adr") or 0) * max(1, int(r.get("rounds") or 0)) for r in full) / rounds),
                    "kast": f"{sum(r.get('kast') or 0 for r in full) / rounds:.0%}",
                    "first_kills_per_game": round(sum(r.get("fk", 0) for r in full) / len(full), 1),
                    "first_deaths_per_game": round(sum(r.get("fd", 0) for r in full) / len(full), 1)})
    agents = Counter(r.get("agent") for r in rs)
    if len(agents) > 1:                        # by agent too, when they're comparing
        out["by_agent"] = {a: _sum([r for r in rs if r.get("agent") == a]) for a, _ in agents.most_common(4)}
        for v in out["by_agent"].values():
            v.pop("by_agent", None)
    return out


def block(rows: list[dict], f: dict, now: datetime | None = None) -> dict:
    """What goes into the coach's data: which games, each one, and what they add up to."""
    sel = select(rows, f, now)
    out = {"which": f.get("why") or "the games the question is about", "found": len(sel)}
    if not sel:
        out["note"] = "no stored games match: say so, and what the player could check"
        return out
    out["games"] = [_game(r) for r in sel[:MAX_GAMES]]
    out["together"] = _sum(sel)
    if len(sel) <= 3:
        out["note"] = "only a few games: a first sign, not a fact"
    return out


def last_games(rows: list[dict], n: int = 8) -> list[str]:
    """The newest games, one line each (always in the coach's data, 4.57)."""
    return [line(r) for r in newest_first(rows)[:n]]
