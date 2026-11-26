"""4.79: a plan against a scouted team, drafted into the strat book from its scouting (stats/stratprep.py): their
setup (your attack) and their hit (your defense), with a call and notes; listed in the match-day brief."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_466 import _scouted  # noqa: E402
from test_web import _premier_team, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import stratprep as sp  # noqa: E402

ROOT = Path(__file__).parent.parent
CENTRES = {"A": (200, 300), "B": (800, 300), "Mid": (500, 500), "Attacker Side": (500, 900)}
PLAY = {"Ascent": {
    "attack": {"full": {"rounds": 7, "won": 3, "sites": [{"site": "B", "n": 6, "share": 0.86}, {"site": "A", "n": 1, "share": 0.14}],
                        "site_won": {}, "no_plant": 0, "plant_s": 28, "first_s": 15, "first_area": "B Long", "fast": 4,
                        "seen": 7, "spread": 1, "stack": 6, "stack_zone": "B"}},
    "defense": {"full": {"rounds": 5, "won": 2, "seen": 5, "setup": {"A": 2.2, "B": 1.4, "Mid": 1.2}, "early": 3,
                         "early_area": "Mid Top"}},
    "lines": ["Ascent attack, full buys: B 86 % of their plants."]}}


def scouted():
    s = _scouted()
    s.update({"wins": 3, "losses": 3, "pistols": {"played": 0, "won": 0}, "economy": {}, "name": "Rivals", "tag": "RV",
              "comps": [{"agents": ["Jett", "Sova", "Omen", "Killjoy", "Skye"], "games": 4}], "play": PLAY})
    s["maps"]["Ascent"].update({"rounds": 80, "rounds_won": 40, "comps": []})
    s["maps"]["Ascent"]["attack"]["sites_hit"] = {"A": {"plants": 7, "rounds_won": 4}}
    s["maps"]["Ascent"]["defense"]["enemy_plants"] = {"A": {"plants": 4, "retakes_won": "25%"}}
    return s


def test_plans():
    assert sp.zone_centres([("A", 0.1, 0.2), ("A", 0.3, 0.4), ("B", 0.8, 0.5)]) == {"A": (200, 300), "B": (800, 500)}
    ps = sp.plans(scouted(), "Ascent", CENTRES, ["line one"])
    d, a = ps
    assert d["side"] == "defense" and d["name"] == "vs RV: their hit"
    assert d["call"].startswith("They hit B 86 % of plants, fast (stacked B). Stack B, rotate")
    them = [i for i in d["items"] if i.get("c") == "them" and i["t"] == "agent"]
    assert [i["a"] for i in them] == ["Jett", "Sova", "Omen", "Killjoy", "Skye"]
    assert sum(1 for i in them if abs(i["x"] - 800) < 50) == 4                          # 4 stacked on B
    assert any(i["t"] == "mark" for i in d["items"]) and "- line one" in d["notes"]
    assert a["side"] == "attack" and a["name"] == "vs RV: their setup"
    assert a["call"] == ("They stand 2 A · 1 B · 1 Mid. Hit B (the fewest of them). They lose retakes on A: plant A and play "
                         "post-plant. They look for early picks at Mid Top: don't take that fight first, hit late.")[:200]
    assert len([i for i in a["items"] if i["t"] == "agent"]) == 4
    # nothing scouted on a map: nothing to draft; no agents known: numbered enemies
    assert sp.plans(scouted(), "Bind", CENTRES) == []
    s = scouted()
    s["comps"] = []
    assert all(i["t"] != "agent" for i in sp.plans(s, "Ascent", CENTRES)[0]["items"])


def test_strat_book_and_brief(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    tid = _premier_team(app, c, monkeypatch)
    store = app.extensions["nexus"]["store"]
    sd = app.extensions["nexus"]["stats"].team_dir(tid) / "scout"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "t1.json").write_text(json.dumps(scouted()))
    page = c.get(f"/teams/{tid}/premier/team/t1").data.decode()
    assert "Draft a plan in the strat book" in page and 'name="team_id" value="t1"' in page
    assert c.post(f"/teams/{tid}/strats/prep", data={"team_id": "nope"}).status_code == 404
    r = c.post(f"/teams/{tid}/strats/prep", data={"team_id": "t1", "map": "Ascent"})
    assert r.status_code == 302 and "/strats" in r.headers["Location"]
    rows = [x for x in store.strats(tid) if x["name"].startswith("vs RV")]
    assert sorted((x["name"], x["side"], x["map"]) for x in rows) == [("vs RV: their hit", "defense", "Ascent"),
                                                                      ("vs RV: their setup", "attack", "Ascent")]
    data = store.strat(rows[0]["id"])["data"]
    data = json.loads(data) if isinstance(data, str) else data
    assert data["prep"]["team"] == "Rivals" and data["steps"][0]["call"] and "items" in data["steps"][0]   # no map data here: no tokens
    # again: nothing doubled
    c.post(f"/teams/{tid}/strats/prep", data={"team_id": "t1", "map": "Ascent"})
    assert len([x for x in store.strats(tid) if x["name"].startswith("vs RV")]) == 2
    # the editor opens it; the brief lists it
    assert c.get(f"/teams/{tid}/strats/{rows[0]['id']}").status_code == 200
    page = c.get(f"/teams/{tid}/premier/brief?map=Ascent").data.decode()
    assert "Against your opponents" in page and "vs RV: their" in page and "from their scouting" in page


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Draft a plan in the strat book", "Against your opponents", "drafted {day} from their scouting",
              "Their setup", "Their hit"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 79)
    assert "## 4.79" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
