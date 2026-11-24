"""4.64: the agent pool editor's role filter, and agents played on some maps only."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_compmodes import _rows  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import compmodes, compsheet, roles  # noqa: E402
from nexus.stats.comp import Pool, rate  # noqa: E402

ROOT = Path(__file__).parent.parent
TPL = (ROOT / "nexus/web/templates/team_sheet.html").read_text()


@pytest.fixture(autouse=True)
def _roles():
    roles.load(None)


def test_clean_maps():
    known = ["Ascent", "Breeze", "Icebox"]
    got = compsheet.clean_maps({"viper": ["breeze", "ICEBOX", "Haven", "breeze"], "Jett": ["Ascent"],
                                "Omen": [], "Sova": "Ascent", "KAY/O": ["../x"]}, ["Viper", "Omen", "Sova", "KAY/O"], known)
    assert got == {"Viper": ["Breeze", "Icebox"]}                       # Jett isn't in his pool, the rest is junk
    assert compsheet.clean_maps(["x"], ["Viper"]) == {}
    assert compsheet.clean_maps({"Viper": ["Lotus"]}, ["Viper"]) == {"Viper": ["Lotus"]}   # no list: any map name
    pl = compsheet.pool([], {"order": ["Viper", "Omen"], "no": [], "maps": {"Viper": ["Breeze"]}})
    assert pl["maps"] == {"Viper": ["Breeze"]} and pl["agents"][0]["maps"] == ["Breeze"] and pl["agents"][1]["maps"] is None
    assert compsheet.prefs([], {"order": ["Viper"], "no": [], "maps": {"Viper": ["Breeze"]}})["maps"] == {"Viper": {"breeze"}}


def _five(viper_maps):
    ps = [Pool.from_rows("ctrl", _rows([("Omen", "Ascent", 1, 200, 5), ("Viper", "Ascent", 1, 240, 12),
                                        ("Omen", "Breeze", 1, 200, 5), ("Viper", "Breeze", 1, 240, 12)])),
          Pool.from_rows("duel", _rows([("Jett", "Ascent", 1, 250, 12), ("Jett", "Breeze", 1, 250, 12)])),
          Pool.from_rows("init", _rows([("Sova", "Ascent", 1, 210, 12), ("Sova", "Breeze", 1, 210, 12)])),
          Pool.from_rows("sent", _rows([("Killjoy", "Ascent", 1, 200, 12), ("Killjoy", "Breeze", 1, 200, 12)])),
          Pool.from_rows("flex", _rows([("Skye", "Ascent", 1, 205, 10), ("Skye", "Breeze", 1, 205, 10)]))]
    ps[0].pref = compsheet.prefs([], {"order": ["Viper", "Omen"], "no": [], "maps": {"Viper": viper_maps}})
    return ps


def test_comps_keep_agents_to_their_maps():
    ps = _five(["Breeze"])
    assert "Viper" not in ps[0].agents("Ascent") and "Viper" in ps[0].agents("Breeze") and "Viper" in ps[0].agents()
    on_ascent = compmodes.top("stats", ps, "Ascent")[0]
    assert {p["player"]: p["agent"] for p in on_ascent["picks"]}["ctrl"] == "Omen"
    on_breeze = compmodes.top("stats", ps, "Breeze")[0]
    assert {p["player"]: p["agent"] for p in on_breeze["picks"]}["ctrl"] == "Viper"
    r = rate(ps[0], "Viper", "Ascent")
    assert "ctrl plays it on other maps only (agent pool)" in r["why"] and r["score"] < rate(ps[0], "Viper", "Breeze")["score"]
    plan = compmodes.plan("stats", ps, [], ["Ascent", "Breeze"], {}, {})
    assert [{p["player"]: p["agent"] for p in m["main"]["picks"]}["ctrl"] for m in plan] == ["Omen", "Viper"]


def test_route_saves_maps(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c)
    tid = store.create_team(store.user_by_name("manuel").id, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter"}], maps=["Ascent", "Breeze", "Icebox"])
    tdir = app.extensions["nexus"]["stats"].team_dir(tid)
    r = c.post(f"/teams/{tid}/sheet/pool/{pid}", headers={"X-Nexus-Save": "1"},
               data={"order": "Viper,Omen", "no": "", "maps": json.dumps({"Viper": ["breeze", "Haven"], "Jett": ["Ascent"]})})
    assert r.get_json()["maps"] == {"Viper": ["Breeze"]}                               # Haven isn't a team map
    assert compsheet.load(tdir)["pools"][str(pid)]["maps"] == {"Viper": ["Breeze"]}
    c.post(f"/teams/{tid}/sheet/pool/{pid}", data={"order": "Omen,Viper", "no": ""})   # an old form: maps stay
    assert compsheet.load(tdir)["pools"][str(pid)]["maps"] == {"Viper": ["Breeze"]}
    c.post(f"/teams/{tid}/sheet/pool/{pid}", data={"order": "Omen", "no": "Viper"})    # not in the pool: gone
    assert compsheet.load(tdir)["pools"][str(pid)].get("maps") == {}
    c.post(f"/teams/{tid}/sheet/pool/{pid}", headers={"X-Nexus-Save": "1"},
           data={"order": "Viper,Omen", "no": "", "maps": json.dumps({"Viper": ["Icebox"]})})
    page = c.get(f"/teams/{tid}/sheet?edit={pid}").data.decode()
    assert 'class="pe-mp" data-maps="Icebox"' in page and '<input type="checkbox" value="Breeze">' in page
    mate = make_user(app, c, "mate")
    store.add_team_access(tid, store.user_by_name("mate").id)
    other = mate.get(f"/teams/{tid}/sheet").data.decode()
    assert 'data-tip="Only on Icebox">1 map</span>' in other                            # the team's pools


def test_page_parts_and_version():
    for s in ("pe-filter", "pe-pop", "pe-changed", "fd.set('maps'", "data-role=\"{{ agent_roles[a] }}\""):
        assert s in TPL, s
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("All maps", "only on these maps:", "filters Can play and Won't play", "{x} plays it on other maps only (agent pool)"):
        assert k in de, k
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 64, 0)
    assert "## 4.64.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
