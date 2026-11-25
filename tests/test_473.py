"""4.73: each drill's sessions as a chart (its card on Aim on maps and its result screen), with your goal on it."""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drillchart as dch  # noqa: E402
from nexus.stats import drillgoals as dg  # noqa: E402
from nexus.stats import drills as dr  # noqa: E402
from nexus.web.drills import goal_of  # noqa: E402

ROOT = Path(__file__).parent.parent
DAY = 86400
HOLD = "g-hold-aaaaaaaaaa"


def run(at, reps, kind="hold"):
    return {"at": int(at), "kind": kind, "reps": reps}


def test_chart():
    now = time.time()
    runs = [run(now - 3 * DAY, [0.6, 0.7, None]), run(now - 2 * DAY, [0.5, 0.52]), run(now - DAY, [0.55, None, 0.58]),
            {"reps": [1]}, run(now, [None, None])]                         # no time / all lost: not a session
    ss = dch.sessions(runs)
    assert [s["med"] for s in ss] == [0.7, 0.52, 0.58] and ss[0] == {"at": int(now - 3 * DAY), "med": 0.7, "reps": 3, "won": 2}
    assert dch.chart(runs[:1], "hold") == "" and dch.chart([], "hold") == ""        # one session: no line to draw
    svg = dch.chart(runs, "hold")
    assert svg.startswith('<svg class="dc"') and svg.endswith("</svg>") and svg.count('class="dc-pt"') == 3
    assert svg.count('class="dc-dot best"') == 1 and "0.52 s · 2/2 reps · your best" in svg   # the fastest session
    assert "↓ better" in svg and "dc-goal" not in svg and 'aria-label="3 sessions' in svg
    goal = {"target": 0.45, "by": "2026-12-06"}
    svg = dch.chart(runs, "hold", goal)
    assert 'class="dc-goal"' in svg and "goal 0.45 s by 06.12." in svg
    ys = [float(m) for m in re.findall(r'y1="([\d.]+)" y2="[\d.]+" class="dc-goal"', svg)]
    assert ys and dch.PAD_T <= ys[0] <= dch.H - dch.PAD_B                          # the goal is inside the chart
    assert "goal 0.45 s ✓" in dch.chart(runs, "hold", dict(goal, reached="2026-11-20"))
    pct = dch.chart([run(now - DAY, [40], "track"), run(now, [70], "track")], "track", {"target": 80})
    assert "↑ better" in pct and "70 %" in pct and "goal 80 %" in pct
    # the goal on a chart: the open one, else the last one reached
    gs = [{"drill": HOLD, "reached": "2026-11-01", "target": 1}, {"drill": HOLD, "target": 2}, {"drill": "x", "target": 3}]
    assert goal_of(gs, HOLD)["target"] == 2 and goal_of(gs[:1], HOLD)["target"] == 1 and goal_of(gs, "y") is None
    css = (ROOT / "nexus/web/static/drills.css").read_text()
    assert ".dc .dc-goal{" in css and ".dc .dc-line{" in css


def test_pages(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    sr = app.extensions["nexus"]["stats"]
    pid = add_profile(c)
    sd = sr.games(pid).path.parent
    dr.add_run(sd, HOLD, run(time.time() - DAY, [0.6, 0.62]))
    dg.add(sd, HOLD, "hold", 0.5)
    r = c.post(f"/api/profiles/{pid}/aim/drill/{HOLD}/runs", json={"kind": "hold", "reps": [0.55, 0.57]}).get_json()
    assert r["ok"] and r["chart"].startswith("<svg") and "goal 0.50 s by" in r["chart"]
    src = (ROOT / "nexus/web/drills.py").read_text()
    assert 'a["chart"] = {k: c for k in sm if (c := dch.chart(' in src            # each spot's card
    assert src.count('"chart": dch.chart(') == 2                                    # both drill pages
    js = (ROOT / "nexus/web/static/aim_maps.js").read_text()
    assert "(s.chart || {})[tab] ? `<div class=\"am-chart\">${s.chart[tab]}</div>`" in js
    dj = (ROOT / "nexus/web/static/drill.js").read_text()
    assert "if (r.ok && d.chart !== undefined) { C.chart = d.chart; if (S.phase === 'done') result(); }" in dj
    assert "!S.histHasMe ? [med] : []" in dj


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("↑ better", "↓ better", "goal {x} by {day}", "goal {x} ✓"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 73)
    assert "## 4.73" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
