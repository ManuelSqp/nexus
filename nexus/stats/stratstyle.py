"""4.68: which comp style a strat fits (compstyle.py), and which strats a counter style asks for on a map.

A strat's style is the one set on it (Strat book, "Style"), else a guess from its name and notes ("rush", "fast"
-> aggressive; "stack", "anchor", "retake", "setup" -> defensive; "execute", "split", "util" -> utility execute) or
from how much utility it draws (many smokes, mollies and abilities -> utility execute)."""
from __future__ import annotations

import re

from .compstyle import STYLES

WORDS = {
    "aggressive": r"\b(rush|fast|push|aggro|aggressive|swing|peek|contact|early|hunt|w\s*key)\b",
    "defensive": r"\b(stack|anchor|retake|setup|set-up|hold|passive|defensive|default|crossfire|lurk)\b",
    "execute": r"\b(execute|exec|split|util|utility|take|full|smoke\s*wall|post-?plant)\b",
}
UTIL_TYPES = {"smoke", "molly", "ab", "wall", "zone"}
UTIL_EXECUTE = 6                          # this many utility items in a strat: an execute
# what a counter style asks for: (side, the strats' style)
WANTS = {
    "defensive": [("defense", "defensive")],
    "execute": [("attack", "execute")],
    "aggressive": [("attack", "aggressive"), ("defense", "aggressive")],
}


def guess(name: str, notes: str = "", data: dict | None = None) -> str | None:
    """The style a strat looks like, or None."""
    text = f"{name} {notes}".lower()
    hits = {k: len(re.findall(rx, text)) for k, rx in WORDS.items()}
    best = max(hits, key=lambda k: hits[k])
    if hits[best]:
        return best
    n = sum(1 for st in (data or {}).get("steps") or [] for it in st.get("items") or [] if it.get("t") in UTIL_TYPES)
    return "execute" if n >= UTIL_EXECUTE else None


def style_of(s: dict) -> tuple[str | None, bool]:
    """(style, set by hand) of a strat row (store.strats + its data)."""
    data = s.get("data") if isinstance(s.get("data"), dict) else {}
    if data.get("style") in STYLES and data["style"] != "balanced":
        return data["style"], True
    return guess(s.get("name") or "", data.get("notes") or "", data), False


def for_counter(style: str, map_name: str, strats: list[dict]) -> dict:
    """The strats on a map that fit a counter style, and what's missing.
    -> {wants: [{side, style, strats: [strat], missing: bool}]}"""
    out = []
    for side, st in WANTS.get(style, []):
        got = [s for s in strats if s["map"].lower() == map_name.lower() and s["side"] == side and s.get("style") == st]
        out.append({"side": side, "style": st, "strats": got, "missing": not got})
    return {"wants": out}
