"""4.65: drills: your week (weekly progress), and your team's utility in the drills."""
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
JS = (ROOT / "nexus/web/static/drill.js").read_text()
NOW = datetime.datetime(2026, 11, 25, 12, 0).timestamp()          # a Wednesday
DAY = 86400


def run(at, kind, reps, **kw):
    return {"at": int(at), "kind": kind, "reps": reps, **kw}


def test_clean_run_keeps_names():
    r = dr.clean_run({"kind": "retake", "reps": [3.5], "map": "  Ascent ", "where": "Retake   B " + "x" * 200})
    assert r["map"] == "Ascent" and r["where"].startswith("Retake B x") and len(r["where"]) == 80
    assert "map" not in dr.clean_run({"kind": "hold", "reps": [0.4], "map": 5})


def test_weekly():
    data = {
        "g-hold-aaaaaaaaaa": [run(NOW - 14 * DAY, "hold", [0.50, 0.52, 0.48], map="Ascent", where="A main"),
                              run(NOW - 8 * DAY, "hold", [0.46, 0.47]),
                              run(NOW - DAY, "hold", [0.40, 0.41, None], map="Ascent", where="A main")],
        "g-track-bbbbbbbbbb": [run(NOW - 9 * DAY, "track", [70, 72], map="Bind", where="Hookah"),
                               run(NOW, "track", [60, 62], map="Bind", where="Hookah")],
        "m1-r3": [run(NOW - 30 * DAY, "death", [0.6]), run(NOW - 90 * DAY, "death", [0.7])],   # the 2nd: too old
        "junk": "x",
    }
    w = dr.weekly(data, now=NOW)
    assert len(w["weeks"]) == 8 and w["weeks"][-1]["start"] == "2026-11-23"
    assert w["this"] == {"start": "2026-11-23", "sessions": 2, "reps": 5} and w["last"]["sessions"] == 2
    assert w["days"] == 2 and w["total"] == 6                                            # 8 weeks: the death run too
    kinds = {k["kind"]: k for k in w["kinds"]}
    assert kinds["hold"]["now"] == 0.41 and kinds["hold"]["before"] == 0.47 and kinds["hold"]["better"] == 0.06
    assert kinds["track"]["better"] == -10 and kinds["track"]["unit"] == "%"
    assert "death" not in kinds                                                          # nothing this week
    assert [d["id"] for d in w["better"]] == ["g-hold-aaaaaaaaaa"] and w["better"][0]["where"] == "A main"
    assert [d["id"] for d in w["worse"]] == ["g-track-bbbbbbbbbb"] and w["worse"][0]["map"] == "Bind"
    assert dr.weekly({}, now=NOW)["total"] == 0


def test_page_shows_your_week(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    pid = add_profile(c)
    sd = app.extensions["nexus"]["stats"].games(pid).path.parent
    assert "Your week" not in c.get(f"/profiles/{pid}/aim/maps").data.decode()           # nothing played yet
    now = time.time()
    dr.add_run(sd, "g-retake-1ed2505d5f", run(now - 8 * DAY, "retake", [4.0, 5.0], map="Ascent", where="Retake B"))
    dr.add_run(sd, "g-retake-1ed2505d5f", run(now, "retake", [3.0, 3.5], map="Ascent", where="Retake B"))
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert 'id="am-week"' in page and "Got better" in page and "Retake B" in page
    assert f"/profiles/{pid}/aim/play/retake/Ascent/1ed2505d5f" in page and "s faster" in page
    r = c.post(f"/api/profiles/{pid}/aim/drill/g-hold-aaaaaaaaaa/runs",
               json={"kind": "hold", "reps": [0.4], "map": "Bind", "where": "Hold: Hookah"})
    assert r.status_code == 200
    assert dr.read_runs(sd)["g-hold-aaaaaaaaaa"][-1]["where"] == "Hold: Hookah"


def test_team_utility_in_the_drill():
    assert "const sets = (SP.util || []).filter(s => s.length);" in JS                   # both sides' utility
    assert "if (u[2] !== ENEMY_SIDE) {" in JS and "Object.assign(it, {mine: true, team: true}" in JS
    assert "TEAM_UTIL = {flash: {blind: 1.6}" in JS and "Your team uses theirs too" in JS
    assert "map: C.map || D.map || ''" in JS


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your week", "Got better", "Slipped", "Your team uses theirs too, from the same rounds", "# s faster"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 65, 0)
    assert "## 4.65.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
