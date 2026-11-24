"""4.69: the weekly letter from the coach (games and drills together), on demand or every Monday."""
import datetime
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.coach import letter as lt  # noqa: E402

ROOT = Path(__file__).parent.parent
NOW = datetime.datetime(2026, 11, 25, 12, 0).timestamp()          # Wednesday, week 48


def row(day, won, agent="Jett", mp="Ascent", acs=200):
    return {"match_id": f"m{day}{agent}", "started_at": f"2026-11-{day:02d}T20:00:00", "won": won, "agent": agent,
            "map": mp, "acs": acs, "kills": 15, "deaths": 12, "assists": 3, "rounds": 20, "queue": "competitive"}


class FakeLLM:
    model = "fake"

    def __init__(self):
        self.calls = []

    def chat_json(self, system, user, schema):
        self.calls.append((system, user))
        return {"letter": "Good week. Your retakes got faster.", "this_week": ["Play 3 retakes", "Trade the entry"],
                "drill": "Retake: your B retakes are still slow."}


def test_facts_and_write():
    rows = [row(24, 1.0), row(23, 0.0, "Omen", "Bind", 180), row(23, 1.0), row(18, 1.0), row(10, 0.0)]
    drills = {"g-retake-cccccccccc": [{"at": NOW - 8 * 86400, "kind": "retake", "reps": [5.0]},
                                      {"at": NOW - 86400, "kind": "retake", "reps": [3.6], "map": "Ascent", "where": "Retake B"}]}
    f = lt.facts("Obi", rows, drills, now=NOW)
    assert f["week"] == "2026-W48" and f["games_this_week"]["games"] == 3 and f["games_this_week"]["won"] == 2
    assert f["games_this_week"]["win_rate"] == "67%" and f["games_last_week"]["games"] == 1
    assert f["maps_this_week"][0]["map"] == "Ascent" and f["agents_this_week"][0]["agent"] == "Jett"
    assert f["drill_practice"]["got_better"]
    assert lt.facts("x", [], {}, now=NOW) == {"player": "x", "week": "2026-W48", "games_this_week": {"games": 0},
                                               "games_last_week": {"games": 0}}
    llm = FakeLLM()
    out = lt.write(llm, "Obi", "English", f)
    assert out["letter"].startswith("Good week") and len(out["this_week"]) == 2 and out["drill"].startswith("Retake")
    assert "Obi's Valorant coach" in llm.calls[0][0] and '"drill_practice"' in llm.calls[0][1]


def test_storage(tmp_path):
    for i in range(10):
        lt.save(tmp_path, f"2026-W{30 + i}", {"letter": f"l{i}", "this_week": [], "drill": ""})
    d = lt.read(tmp_path)
    assert len(d["weeks"]) == lt.WEEKS_KEPT and lt.latest(tmp_path)[0] == "2026-W39"
    lt.set_auto(tmp_path, True)
    assert lt.read(tmp_path)["auto"] is True and len(lt.read(tmp_path)["weeks"]) == lt.WEEKS_KEPT


def _wait(c, pid):
    for _ in range(50):
        if "The coach is writing" not in c.get(f"/profiles/{pid}/ask").data.decode():
            return
        time.sleep(0.1)


def test_page_and_monday(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    pid = add_profile(c)
    sr = app.extensions["nexus"]["stats"]
    llm = FakeLLM()
    monkeypatch.setattr(sr, "_llm", lambda p, choice=None: (llm, {}))
    page = c.get(f"/profiles/{pid}/ask").data.decode()
    assert 'id="letter"' in page and "Write this week&#39;s letter" in page or "Write this week's letter" in page
    assert c.post(f"/profiles/{pid}/letter").status_code == 302
    _wait(c, pid)
    page = c.get(f"/profiles/{pid}/ask").data.decode()
    assert "Good week. Your retakes got faster." in page and "Play 3 retakes" in page and "Write it again" in page
    assert lt.latest(sr.games(pid).path.parent)[1]["model"] == "fake"
    # every Monday: off by default; on, once per week
    tick = next(f for f in app.extensions["nexus"]["ticks"] if f.__name__ == "tick_letters")
    monday = datetime.datetime(2026, 11, 30, 7, 30)
    assert tick(monday) == []
    c.post(f"/profiles/{pid}/letter", data={"auto": "1"})
    assert "Stop the Monday letter" in c.get(f"/profiles/{pid}/ask").data.decode()
    assert tick(datetime.datetime(2026, 11, 30, 6, 0)) == [] and tick(datetime.datetime(2026, 12, 1, 9, 0)) == []
    n = len(llm.calls)
    assert tick(monday) == [pid] and tick(monday) == []
    _wait(c, pid)
    assert len(llm.calls) == n + 1 and "2026-W49" in lt.read(sr.games(pid).path.parent)["weeks"]


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your week from the coach", "Write this week's letter", "Write it again", "Every Monday by itself", "Drill first:"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 69, 0)
    assert "## 4.69.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
