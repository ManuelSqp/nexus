"""4.73: a drill's sessions as a small chart, for its card on Practice › Aim on maps and its result screen: the
median of each session (a dot each, joined by a line), your best session marked, and your goal on that drill as a
dashed line with its day. One series, one axis; the time or percentage on the left, the sessions' days below.
Drawn here as SVG (the pages only put it in), in the page's colours (CSS variables), with a tooltip per session
(<title>: the day, the median, reps won)."""
from __future__ import annotations

import datetime
import html

from .drills import HIGHER, KINDS, _median

MAX_SESSIONS = 20
W, H = 320, 120
PAD_L, PAD_R, PAD_T, PAD_B = 38, 10, 10, 20


def sessions(runs: list[dict], n: int = MAX_SESSIONS) -> list[dict]:
    """The last n sessions, oldest first: {at, med, reps, won} (won: reps not lost)."""
    out = []
    for r in runs:
        if not isinstance(r, dict) or not isinstance(r.get("at"), (int, float)):
            continue
        reps = r.get("reps") or []
        med = _median(reps)
        if med is None:
            continue
        out.append({"at": int(r["at"]), "med": round(med, 3), "reps": len(reps),
                    "won": sum(1 for t in reps if isinstance(t, (int, float)))})
    return out[-n:]


def fmt(v: float, unit: str) -> str:
    return f"{round(v)} %" if unit == "%" else f"{v:.2f} s"


def _day(ts: float) -> str:
    return datetime.date.fromtimestamp(ts).strftime("%d.%m.")


def chart(runs: list[dict], kind: str, goal: dict | None = None) -> str:
    """The SVG, or "" with fewer than 2 sessions (nothing to draw a line through). goal: a drill goal
    (stats/drillgoals.py: target, by, reached)."""
    ss = sessions(runs)
    if len(ss) < 2:
        return ""
    unit = KINDS.get(kind, "s")
    higher = kind in HIGHER
    vals = [s["med"] for s in ss]
    target = goal.get("target") if goal and isinstance(goal.get("target"), (int, float)) else None
    lo, hi = min(vals + ([target] if target is not None else [])), max(vals + ([target] if target is not None else []))
    if unit == "%":
        lo, hi = max(0.0, lo - 5), min(100.0, hi + 5)
    else:
        span = max(hi - lo, 0.2)
        lo, hi = max(0.0, lo - span * 0.15), hi + span * 0.15
    if hi <= lo:
        hi = lo + 1
    pw, ph = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    x = [PAD_L + (i / (len(ss) - 1)) * pw for i in range(len(ss))]

    def y(v: float) -> float:
        return PAD_T + (hi - v) / (hi - lo) * ph
    best_i = max(range(len(ss)), key=lambda i: vals[i]) if higher else min(range(len(ss)), key=lambda i: vals[i])
    e = html.escape
    out = [f'<svg class="dc" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'aria-label="{e(f"{len(ss)} sessions, median per session; best {fmt(vals[best_i], unit)}")}">']
    for v in (lo, hi):                                          # the axis: the bottom and the top value
        out.append(f'<line x1="{PAD_L}" x2="{W - PAD_R}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="dc-grid"/>')
        out.append(f'<text x="{PAD_L - 5}" y="{y(v) + 3.5:.1f}" class="dc-ax" text-anchor="end">{e(fmt(v, unit))}</text>')
    out.append(f'<text x="{PAD_L}" y="{H - 5}" class="dc-ax">{e(_day(ss[0]["at"]))}</text>')
    out.append(f'<text x="{W - PAD_R}" y="{H - 5}" class="dc-ax" text-anchor="end">{e(_day(ss[-1]["at"]))}</text>')
    out.append(f'<text x="{(PAD_L + W - PAD_R) / 2:.0f}" y="{H - 5}" class="dc-ax" text-anchor="middle">'
               f'{e("↑ better" if higher else "↓ better")}</text>')
    if target is not None:                                      # your goal: a dashed line with its day
        reached = bool(goal.get("reached"))
        by = goal.get("by") or ""
        try:
            by = datetime.date.fromisoformat(by).strftime("%d.%m.")
        except ValueError:
            pass
        label = f"goal {fmt(target, unit)}" + (" ✓" if reached else f" by {by}" if by else "")
        ty = y(target)
        out.append(f'<line x1="{PAD_L}" x2="{W - PAD_R}" y1="{ty:.1f}" y2="{ty:.1f}" class="dc-goal{" done" if reached else ""}"/>')
        out.append(f'<text x="{W - PAD_R}" y="{ty - 4:.1f}" class="dc-goal-l" text-anchor="end">{e(label)}</text>')
    pts = " ".join(f"{x[i]:.1f},{y(v):.1f}" for i, v in enumerate(vals))
    out.append(f'<polyline points="{pts}" class="dc-line"/>')
    for i, s in enumerate(ss):
        tip = f"{_day(s['at'])}: {fmt(s['med'], unit)} · {s['won']}/{s['reps']} reps" + (" · your best" if i == best_i else "")
        cls = "dc-dot best" if i == best_i else "dc-dot"
        out.append(f'<g class="dc-pt"><title>{e(tip)}</title><circle cx="{x[i]:.1f}" cy="{y(s["med"]):.1f}" r="10" class="dc-hit"/>'
                   f'<circle cx="{x[i]:.1f}" cy="{y(s["med"]):.1f}" r="{5 if i == best_i else 4}" class="{cls}"/></g>')
    out.append("</svg>")
    return "".join(out)


CSS = """.dc{display:block;max-width:420px;margin:6px 0 2px;overflow:visible}
.dc .dc-grid{stroke:var(--line);stroke-width:1}
.dc .dc-ax{fill:var(--muted);font-size:10px;font-family:var(--font-num,inherit)}
.dc .dc-line{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dc .dc-dot{fill:var(--accent);stroke:var(--panel,#111);stroke-width:2}
.dc .dc-dot.best{fill:var(--good,#5fe0c6)}
.dc .dc-hit{fill:transparent}
.dc .dc-pt:hover .dc-dot{stroke:var(--text)}
.dc .dc-goal{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:5 4}
.dc .dc-goal.done{stroke:var(--good,#5fe0c6)}
.dc .dc-goal-l{fill:var(--muted);font-size:10px;font-family:var(--font-num,inherit)}"""
