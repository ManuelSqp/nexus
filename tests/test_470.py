"""4.70: drill goals; one drill per player in the team's practice plan, ticked by itself."""
import datetime
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus import discord  # noqa: E402
from nexus.stats import drillgoals as dg  # noqa: E402
from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import practice as pr  # noqa: E402

ROOT = Path(__file__).parent.parent
DAY = 86400
RT = "g-retake-cccccccccc"


def run(at, reps, kind="retake", **kw):
    return {"at": int(at), "kind": kind, "reps": reps, **kw}


def test_add_and_rules(tmp_path):
    g = dg.add(tmp_path, RT, "retake", "3.5", None, "Ascent", "Retake  B")
    assert g["target"] == 3.5 and g["by"] == dg.next_sunday().isoformat() and g["where"] == "Retake B"
    g2 = dg.add(tmp_path, RT, "retake", 3.2)                        # one open goal per drill: replaces it
    assert [x["id"] for x in dg.read(tmp_path)] == [g2["id"]]
    for bad in [("x", "nope", 3), (RT, "retake", "fast"), (RT, "retake", 0), ("g-track-a", "track", 120)]:
        with pytest.raises(ValueError):
            dg.add(tmp_path, *bad)
    with pytest.raises(ValueError):
        dg.add(tmp_path, RT, "retake", 3, "2020-01-01")
    for i in range(dg.MAX_OPEN - 1):
        dg.add(tmp_path, f"g-hold-{i:010d}", "hold", 0.5)
    with pytest.raises(ValueError):
        dg.add(tmp_path, "g-hold-zzzzzzzzzz", "hold", 0.5)
    assert dg.remove(tmp_path, g2["id"]) and not dg.remove(tmp_path, g2["id"])


def test_status_and_sync(tmp_path):
    now = time.time()
    g = dg.add(tmp_path, RT, "retake", 3.5, map_name="Ascent", where="Retake B")
    set_at = g["set"]
    runs = {RT: [run(set_at - 3 * DAY, [5.0, 4.0]), run(set_at + 60, [4.2]), run(set_at + 120, [3.4, 3.5, 3.6])]}
    st = dg.sync(tmp_path, runs, now)[0]
    assert st["start"] == 5.0 and st["best"] == 3.5 and st["reached"] == datetime.date.fromtimestamp(set_at + 120).isoformat()
    assert st["progress"] == 1.0 and st["label"] == "Retake · Ascent · Retake B" and st["sessions"] == 2
    runs[RT].append(run(set_at + 180, [4.5]))                       # slower later: stays reached
    assert dg.sync(tmp_path, runs, now)[0]["reached"] and dg.read(tmp_path)[0]["reached"]
    half = dg.status([{**g, "target": 3.0}], {RT: runs[RT][:2]}, now)[0]
    assert half["reached"] is None and round(half["progress"], 2) == 0.4                  # 5.0 -> 4.2 of 5.0 -> 3.0
    assert dg.text(st) == f"Retake · Ascent · Retake B: under 3.50 s by {g['by']}"
    tr = dg.status([{**g, "kind": "track", "drill": "t", "target": 80}], {"t": [run(set_at + 1, [85], "track")]}, now)[0]
    assert tr["reached"] and dg.text(tr).startswith("Tracking · Ascent · Retake B: at least 80 %")


def test_suggest():
    week = {"worse": [{"id": RT, "kind": "retake", "name": "Retake", "map": "Ascent", "where": "B", "unit": "s", "before": 3.6, "now": 4.1}],
            "better": [{"id": "g-track-aaaaaaaaaa", "kind": "track", "name": "Tracking", "map": "", "where": "", "unit": "%", "before": 60, "now": 70}]}
    s = dg.suggest(week, [])
    assert [(x["drill"], x["target"], x["why"]) for x in s] == [(RT, 3.6, "back to where it was"),
                                                                ("g-track-aaaaaaaaaa", 73, "keep it going")]
    assert [x["drill"] for x in dg.suggest(week, [{"drill": RT}])] == ["g-track-aaaaaaaaaa"]


def test_coach_and_sunday_post(tmp_path):
    now = time.time()
    g = dg.add(tmp_path, RT, "retake", 3.5, map_name="Ascent")
    runs = {RT: [run(g["set"] + 10, [3.4])]}
    st = dg.status(dg.read(tmp_path), runs, now)
    f = dr.coach_facts(runs, now, st)
    assert f["goals"][0]["goal"].startswith("Retake · Ascent: under 3.50 s") and f["goals"][0]["reached"] != "not yet"
    tw = dr.team_week([("Obi", runs, st), ("m1", {})], None, now)
    assert tw["players"][0]["goals_reached"][0]["id"] == g["id"]
    assert "🎯 **Goals reached**: Obi, Retake · Ascent: under 3.50 s" in discord.drills_embeds("S", "w", tw)[0]["description"]


def test_plan_drill_items():
    start = time.time() - DAY
    items = pr.drill_items([{"pid": 1, "name": "Obi", "drill": RT, "label": "Retake · Ascent", "why": "his goal", "link": "/x"}])
    assert items[0]["kind"] == "drill" and items[0]["sessions"] == pr.DRILL_SESSIONS and items[0]["title"] == "Obi: Retake · Ascent"
    runs = {RT: [run(start - DAY, [1]), run(start + 10, [1]), run(start + 20, [1])],
            "g-hold-aaaaaaaaaa": [run(start + 5, [1], "hold", map="Ascent")]}
    assert pr.drill_count(runs, RT, start) == 2 and pr.drill_count(runs, "*", start) == 3
    assert pr.drill_count(runs, "*map:ascent", start) == 1
    assert pr.progress({"days": [], "drills": items}) == (0, 1)


def test_pages(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    sr = app.extensions["nexus"]["stats"]
    pid = add_profile(c)
    sd = sr.games(pid).path.parent
    now = time.time()
    dr.add_run(sd, RT, run(now - 8 * DAY, [3.6], map="Ascent", where="Retake B"))
    dr.add_run(sd, RT, run(now - 60, [4.1, 4.2], map="Ascent", where="Retake B"))
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert 'id="am-goals"' in page and "back to where it was" in page and 'name="target"' in page
    r = c.post(f"/profiles/{pid}/aim/goals", data={"drill": RT, "kind": "retake", "target": "3.6", "map": "Ascent",
                                                   "where": "Retake B", "label": "Retake · Ascent · Retake B", "source": "suggested"})
    assert r.status_code == 302 and dg.read(sd)[0]["source"] == "suggested"
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert "under 3.60 s" in page and "/aim/play/retake/Ascent/cccccccccc" in page
    assert "Not saved: the target needs to be a number" in c.post(f"/profiles/{pid}/aim/goals", data={"drill": RT, "kind": "retake", "target": "x"},
                                                                    follow_redirects=True).data.decode()
    # the team's plan: his goal is his drill for the week, and it ticks itself
    tid = store.create_team(store.user_by_name("manuel").id, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter"}])
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert "Drills this week" in page and "his goal: Retake · Ascent · Retake B: under 3.60 s" in page and "1 / 3 sessions" in page   # the run of a minute ago
    assert "Play it</a>" in page
    for i in range(2):
        dr.add_run(sd, RT, run(time.time(), [3.0]))
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert "3 / 3 sessions" in page and 'class="pi k-drill done"' in page
    gid = dg.read(sd)[0]["id"]
    c.post(f"/profiles/{pid}/aim/goals", data={"remove": gid})
    assert dg.read(sd) == []


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your goals", "Add the goal", "Drills this week", "Ideas", "back to where it was", "keep it going"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 70, 0)
    assert "## 4.70.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
