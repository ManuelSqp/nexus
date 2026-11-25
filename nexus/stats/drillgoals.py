"""4.70: drill goals: "Retake B under 3.5 s by Sunday". A goal is one drill (its id in drills.json), a target (seconds:
at or under; % for tracking and clearing: at or over) and a day to reach it by. Set by the player, often from a
suggestion (suggest(): get back to where a slipped drill was, or a step further on one that got better).

A goal is reached by the first session after it was set whose median meets the target. Stored per player next to
his drills (drill_goals.json)."""
from __future__ import annotations

import datetime
import json
import os
import secrets
import time
from pathlib import Path

from .drills import HIGHER, KINDS, MODE_NAMES, _median

FILE = "drill_goals.json"
MAX_OPEN = 6
KEEP_DONE_DAYS = 56


def read(stats_dir: Path) -> list[dict]:
    try:
        d = json.loads((Path(stats_dir) / FILE).read_text())
        return [g for g in d.get("goals", []) if isinstance(g, dict) and g.get("id")]
    except (OSError, ValueError, AttributeError):
        return []


def _write(stats_dir: Path, goals: list[dict]) -> None:
    f = Path(stats_dir) / FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"goals": goals}, ensure_ascii=False))
    os.replace(tmp, f)


def next_sunday(today: datetime.date | None = None) -> datetime.date:
    today = today or datetime.date.today()
    return today + datetime.timedelta(days=(6 - today.weekday()) or 7)


def add(stats_dir: Path, drill: str, kind: str, target, by: str | None = None, map_name: str = "", where: str = "",
        source: str = "you") -> dict:
    """A new goal; ValueError when it doesn't make sense."""
    if kind not in KINDS or not isinstance(drill, str) or not (0 < len(drill) <= 80):
        raise ValueError("not a drill")
    try:
        target = float(target)
    except (TypeError, ValueError):
        raise ValueError("the target needs to be a number") from None
    if not (0 < target <= (100 if KINDS[kind] == "%" else 60)):
        raise ValueError("that target can't be reached")
    try:
        day = datetime.date.fromisoformat(by) if by else next_sunday()
    except ValueError:
        raise ValueError("the day isn't a date") from None
    if day < datetime.date.today() or day > datetime.date.today() + datetime.timedelta(days=90):
        raise ValueError("pick a day in the next 90 days")
    goals = read(stats_dir)
    if sum(1 for g in goals if not g.get("reached")) >= MAX_OPEN:
        raise ValueError(f"at most {MAX_OPEN} open goals")
    g = {"id": secrets.token_hex(4), "drill": drill, "kind": kind, "map": str(map_name or "")[:24],
         "where": " ".join(str(where or "").split())[:80], "target": round(target, 3 if KINDS[kind] == "s" else 1),
         "by": day.isoformat(), "set": int(time.time()), "source": source if source in ("you", "suggested") else "you"}
    goals = [x for x in goals if not (x["drill"] == drill and not x.get("reached"))] + [g]   # one open goal per drill
    _write(stats_dir, goals)
    return g


def remove(stats_dir: Path, gid: str) -> bool:
    goals = read(stats_dir)
    left = [g for g in goals if g["id"] != gid]
    if len(left) == len(goals):
        return False
    _write(stats_dir, left)
    return True


def meets(kind: str, value, target) -> bool:
    if value is None:
        return False
    return value >= target if kind in HIGHER else value <= target


def status(goals: list[dict], runs: dict, now: float | None = None) -> list[dict]:
    """Each goal with: start (the drill's median before it was set), now (the newest session's), best (the best
    session since), reached (the day), left (days to go), late, progress 0..1, label, unit. Stores nothing:
    sync() keeps "reached" in the file. Old reached goals (> KEEP_DONE_DAYS) are left out."""
    now = time.time() if now is None else now
    today = datetime.date.fromtimestamp(now)
    out = []
    for g in goals:
        kind, unit = g["kind"], KINDS.get(g["kind"], "s")
        rs = [r for r in runs.get(g["drill"], []) if isinstance(r, dict) and isinstance(r.get("at"), (int, float))]
        before = [t for r in rs if r["at"] < g["set"] for t in r.get("reps") or [] if isinstance(t, (int, float))]
        after = [(r["at"], _median(r.get("reps") or [])) for r in rs if r["at"] >= g["set"]]
        after = [(a, m) for a, m in after if m is not None]
        start = _median(before) if before else (after[0][1] if after else None)
        cur = after[-1][1] if after else None
        best = (max if kind in HIGHER else min)((m for _a, m in after), default=None)
        reached = g.get("reached")
        if not reached:
            hit = next((a for a, m in after if meets(kind, m, g["target"])), None)
            reached = datetime.date.fromtimestamp(hit).isoformat() if hit else None
        if reached and (today - datetime.date.fromisoformat(reached)).days > KEEP_DONE_DAYS:
            continue
        by = datetime.date.fromisoformat(g["by"])
        prog = None
        if start is not None and best is not None and start != g["target"]:
            prog = max(0.0, min(1.0, (best - start) / (g["target"] - start)))
        if reached:
            prog = 1.0
        label = " · ".join(x for x in (MODE_NAMES.get(kind, kind), g.get("map"), g.get("where")) if x)
        out.append({**g, "unit": unit, "start": start, "now": cur, "best": best, "reached": reached,
                    "left": (by - today).days, "late": not reached and by < today, "progress": prog, "label": label,
                    "sessions": len(after)})
    return sorted(out, key=lambda x: (bool(x["reached"]), x["by"]))


def sync(stats_dir: Path, runs: dict, now: float | None = None) -> list[dict]:
    """status(), and the newly reached goals written back (so a slower session later doesn't undo them)."""
    goals = read(stats_dir)
    st = status(goals, runs, now)
    by = {s["id"]: s for s in st}
    changed = False
    for g in goals:
        s = by.get(g["id"])
        if s and s["reached"] and not g.get("reached"):
            g["reached"] = s["reached"]
            changed = True
    if changed:
        _write(stats_dir, goals)
    return st


def suggest(week: dict, goals: list[dict], n: int = 3) -> list[dict]:
    """Goals worth setting, from your week (drills.weekly): back to where a slipped drill was; a step further on one
    that got better (5 % faster, or 3 points). Not for drills that already have an open goal."""
    taken = {g["drill"] for g in goals if not g.get("reached")}
    out = []
    for d, why in [(d, "back to where it was") for d in week.get("worse", [])] + \
                  [(d, "keep it going") for d in week.get("better", [])]:
        if d["id"] in taken or d["now"] is None:
            continue
        unit = d["unit"]
        if why == "back to where it was":
            target = d["before"]
        else:
            target = d["now"] + 3 if unit == "%" else d["now"] * 0.95
        target = round(min(100, target), 1) if unit == "%" else round(target, 2)
        out.append({"drill": d["id"], "kind": d["kind"], "map": d.get("map", ""), "where": d.get("where", ""),
                    "label": " · ".join(x for x in (d["name"], d.get("map"), d.get("where")) if x),
                    "now": d["now"], "target": target, "unit": unit, "why": why, "by": next_sunday().isoformat()})
        taken.add(d["id"])
        if len(out) >= n:
            break
    return out


def fmt(x, unit: str) -> str:
    return "–" if x is None else (f"{round(x)} %" if unit == "%" else f"{x:.2f} s")


def text(g: dict) -> str:
    """"Retake · Ascent · Retake B: under 3.50 s by 2026-11-29"."""
    cmp = "at least" if g["kind"] in HIGHER else "under"
    return f"{g.get('label') or g['drill']}: {cmp} {fmt(g['target'], KINDS.get(g['kind'], 's'))} by {g['by']}"
