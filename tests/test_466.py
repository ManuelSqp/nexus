"""4.66: the coach knows your drill practice; counter comps from scouting."""
import datetime
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_web import _premier_team, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.coach import askcoach as ac  # noqa: E402
from nexus.stats import counter as ctr  # noqa: E402
from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import roles  # noqa: E402

ROOT = Path(__file__).parent.parent
NOW = datetime.datetime(2026, 11, 25, 12, 0).timestamp()
DAY = 86400


@pytest.fixture(autouse=True)
def _roles():
    roles.load(None)


def test_coach_facts():
    assert dr.coach_facts({}) is None
    data = {"g-retake-1ed2505d5f": [{"at": NOW - 8 * DAY, "kind": "retake", "reps": [4.0, 5.0], "map": "Ascent", "where": "Retake B"},
                                    {"at": NOW - 2 * DAY, "kind": "retake", "reps": [3.0, 3.4], "map": "Ascent", "where": "Retake B"}],
            "g-track-aaaaaaaaaa": [{"at": NOW - 9 * DAY, "kind": "track", "reps": [70]}]}
    f = dr.coach_facts(data, now=NOW)
    assert f["last_drill"] == "2 days ago" and f["this_week"] == {"sessions": 1, "reps": 2, "days": 1}
    assert f["last_week_sessions"] == 2 and f["weeks_with_drills_of_last_8"] == 2
    assert f["sessions_per_kind_all_kept"] == {"Retake": 2, "Tracking": 1}
    assert f["this_week_by_kind"] == [{"drill": "Retake", "sessions": 1, "median": "3.40 s", "vs_last_week": "1.60 s faster"}]
    assert f["got_better"] == ["Retake · Ascent · Retake B: 5.00 s -> 3.40 s"] and "slipped" not in f
    assert "drill_practice" in ac.SYSTEM


def test_coach_gets_it(app):  # noqa: F811 (fixture)
    from test_web import add_profile
    c = setup_admin(app)
    pid = add_profile(c)
    sr = app.extensions["nexus"]["stats"]
    assert "drill_practice" not in sr.coach_extras(pid, [], app.extensions["nexus"]["store"].data_dir / "cache")
    dr.add_run(sr.games(pid).path.parent, "g-hold-aaaaaaaaaa", {"at": int(NOW), "kind": "hold", "reps": [0.4]})
    got = sr.coach_extras(pid, [], app.extensions["nexus"]["store"].data_dir / "cache")
    assert got["drill_practice"]["sessions_per_kind_all_kept"] == {"Hold an angle": 1}


def _scouted(fast=True, weak_retakes=False, comp=("Jett", "Raze", "Omen", "Sova", "Killjoy"), sides=None, entry=None):
    att = {"plant_median_s": 35 if fast else 55, "sites_hit": {"A": {"plants": 7}, "B": {"plants": 3}}}
    dfn = {"enemy_plants": {"B": {"plants": 4, "retakes_won": "25%"}}} if weak_retakes else {}
    return {"matches": 6, "players": [entry] if entry else [],
            "maps": {"Ascent": {"games": 4, "wins": 2, "attack": att, "defense": dfn, "sides": sides or {},
                                "comps": [{"agents": list(comp), "games": 3}]}}}


def test_counter():
    c = ctr.counter(_scouted(), "ascent")
    assert c["style"] == "defensive" and c["their_comp"][0] == "Jett" and c["games"] == 4
    assert any("they hit fast" in r for r in c["reasons"]) and any("two duelists" in r for r in c["reasons"])
    c = ctr.counter(_scouted(fast=False, weak_retakes=True, comp=("Viper", "Omen", "Killjoy", "Cypher", "Sova")), "Ascent")
    assert c["style"] == "execute" and any("retakes on B" in r for r in c["reasons"])
    calm = _scouted(fast=False, comp=("Jett", "Omen", "Sova", "Killjoy", "Skye"))
    calm["maps"]["Ascent"]["attack"]["sites_hit"] = {"A": {"plants": 5}, "B": {"plants": 5}}
    assert ctr.counter(calm, "Ascent")["style"] == "balanced"
    assert ctr.counter(_scouted(), "Bind") is None and ctr.counter(None, "Ascent") is None
    e = {"name": "Boss", "agents": [{"agent": "Jett", "games": 4}], "first_duel_share": .3, "first_duels_won": .6}
    assert any("Boss (Jett) wins 60%" in r for r in ctr.counter(_scouted(entry=e), "Ascent")["reasons"])


def test_comps_page_against_a_team(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    tid = _premier_team(app, c, monkeypatch)
    sd = app.extensions["nexus"]["stats"].team_dir(tid) / "scout"
    sd.mkdir(parents=True, exist_ok=True)
    s = _scouted()
    s["maps"]["Bind"] = s["maps"].pop("Ascent")
    (sd / "t1.json").write_text(json.dumps(s))
    (sd / "index.json").write_text(json.dumps({"teams": {"t1": {"id": "t1", "name": "Rivals", "tag": "RV", "matches": 6}}}))
    page = c.get(f"/teams/{tid}?map=Bind").data.decode()
    assert '<option value="t1" >Rivals#RV (6 matches)</option>' in page and 'class="counter"' not in page
    page = c.get(f"/teams/{tid}?map=Bind&vs=t1").data.decode()
    assert 'class="counter"' in page and "on Bind: Defensive</b>" in page and "they hit fast" in page
    assert re.search(r'class="on" href="[^"]*style=defensive', page)
    again = c.get(f"/teams/{tid}?map=Bind").data.decode()                         # kept
    assert '<option value="t1" selected>' in again
    mine = c.get(f"/teams/{tid}?map=Bind&style=aggressive").data.decode()          # your own pick wins
    assert "you picked Aggressive yourself" in mine and re.search(r'class="on" href="[^"]*style=aggressive', mine)
    other = c.get(f"/teams/{tid}?map=Ascent").data.decode()
    assert "didn't play Ascent in their scouted matches" in other
    off = c.get(f"/teams/{tid}?map=Bind&vs=").data.decode()
    assert 'class="counter"' not in off


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Against", "nobody in particular", "Their usual comp here:", "Their scouting page", "Counter:"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 66, 0)
    assert "## 4.66.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
