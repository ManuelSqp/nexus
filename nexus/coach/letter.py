"""4.69: the weekly letter from the coach: once a week, a short note for one player that ties his games and his
drills together ("your B retakes got faster, and you won 3 of 4 retakes on Ascent this week").

facts() reads the player's games of this week and the week before (rows from stats.games) and his drill practice
(stats.drills.coach_facts); write() asks the model for the letter. Stored per player and week (letters.json, the
last WEEKS_KEPT weeks), next to his other stats."""
from __future__ import annotations

import datetime
import json
import os
import time
from pathlib import Path

from ..stats import drills as dr
from ..stats.aggregate import by_agent, by_map
from .prompts import field_guide

WEEKS_KEPT = 8
FILE = "letters.json"
SYSTEM = """You are {player}'s Valorant coach. Once a week you write them a short letter in {language}: 4-7 sentences,
warm but direct, like a coach who watched their week.
- Use only the facts below. Tie their games and their drills together where the facts allow it (a drill that got
  faster and a part of the game that went better; a problem in their games and the drill that trains it).
- Quote the numbers a sentence rests on. Few games ("games_this_week" under 3) are a first sign, not a trend.
- If they played no games or no drills this week, say so plainly in one sentence, without nagging.
- "this_week": 2-3 short, concrete things to do in the coming week. "drill": the one Nexus drill to play first
  (its name as in the facts: "Retake", "Hold an angle", "Entry", "Tracking", …) and why, in one sentence."""
SCHEMA = {"type": "object", "properties": {
    "letter": {"type": "string", "description": "the letter, 4-7 sentences"},
    "this_week": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    "drill": {"type": "string", "description": "the drill to play first, and why (one sentence)"}},
    "required": ["letter", "this_week", "drill"]}


def week_of(ts: float) -> str:
    """ISO week, e.g. 2026-W48."""
    y, w, _d = datetime.date.fromtimestamp(ts).isocalendar()
    return f"{y}-W{w:02d}"


def _start(ts: float) -> datetime.date:
    d = datetime.date.fromtimestamp(ts)
    return d - datetime.timedelta(days=d.weekday())


def _when(r: dict) -> datetime.date | None:
    s = str(r.get("started_at") or "")[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def _sum(rows: list[dict]) -> dict:
    if not rows:
        return {"games": 0}
    n = len(rows)
    wins = sum(1 for r in rows if (r.get("won") or 0) >= 1)
    k, d = sum(r.get("kills") or 0 for r in rows), sum(r.get("deaths") or 0 for r in rows)
    acs = [r["acs"] for r in rows if isinstance(r.get("acs"), (int, float))]
    out = {"games": n, "won": wins, "win_rate": f"{wins / n:.0%}", "kd": round(k / max(1, d), 2)}
    if acs:
        out["acs"] = round(sum(acs) / len(acs))
    return out


def facts(name: str, rows: list[dict], drills: dict | None, now: float | None = None) -> dict:
    """The week in numbers: this week's games against last week's, its maps and agents, and the drills."""
    now = time.time() if now is None else now
    this = _start(now)
    last = this - datetime.timedelta(weeks=1)
    cur = [r for r in rows if (_when(r) or datetime.date.min) >= this]
    prev = [r for r in rows if last <= (_when(r) or datetime.date.min) < this]
    out: dict = {"player": name, "week": week_of(now), "games_this_week": _sum(cur), "games_last_week": _sum(prev)}
    if cur:
        out["maps_this_week"] = [{"map": m["map"], "games": m["games"], "win_rate": f"{m['wr']:.0%}"} for m in by_map(cur)[:4]]
        out["agents_this_week"] = [{"agent": a["agent"], "games": a["games"], "win_rate": f"{a['wr']:.0%}",
                                    "acs": round(a["acs"])} for a in by_agent(cur)[:3]]
    dp = dr.coach_facts(drills or {}, now)
    if dp:
        out["drill_practice"] = dp
    return out


def write(llm, player: str, language: str, f: dict) -> dict:
    out = llm.chat_json(SYSTEM.format(player=player, language=language) + field_guide(SCHEMA),
                        "The player's week (YAML-like JSON):\n" + json.dumps(f, ensure_ascii=False, indent=1), SCHEMA)
    letter = str(out.get("letter") or "").strip()[:3000]
    if not letter:
        from .llm import NoAnswer
        raise NoAnswer("the model wrote no letter")
    return {"letter": letter, "this_week": [str(x).strip()[:300] for x in (out.get("this_week") or []) if str(x).strip()][:3],
            "drill": str(out.get("drill") or "").strip()[:400]}


# ------------------------------------------------------------------------------------------------ storage
def read(stats_dir: Path) -> dict:
    try:
        d = json.loads((Path(stats_dir) / FILE).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save(stats_dir: Path, week: str, letter: dict, model: str = "") -> dict:
    d = read(stats_dir)
    weeks = d.setdefault("weeks", {})
    weeks[week] = {**letter, "at": int(time.time()), "model": model}
    for k in sorted(weeks)[:-WEEKS_KEPT]:
        weeks.pop(k)
    _write(stats_dir, d)
    return d


def set_auto(stats_dir: Path, on: bool) -> None:
    d = read(stats_dir)
    d["auto"] = bool(on)
    _write(stats_dir, d)


def _write(stats_dir: Path, d: dict) -> None:
    f = Path(stats_dir) / FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False))
    os.replace(tmp, f)


def latest(stats_dir: Path) -> tuple[str, dict] | None:
    weeks = read(stats_dir).get("weeks") or {}
    if not weeks:
        return None
    k = max(weeks)
    return k, weeks[k]
