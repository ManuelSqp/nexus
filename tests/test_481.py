"""4.81: the lineup trainer: lineups recorded in the 3D map (where you stand and aim for an ability) and practised
there (stats/lineups.py, web/drills.py, drill.js "lineup")."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import lineups as lu  # noqa: E402

ROOT = Path(__file__).parent.parent
DJ = (ROOT / "nexus/web/static/drill.js").read_text()


def test_store(tmp_path):
    maps = ["Ascent"]
    x = lu.clean({"map": "Ascent", "name": " Sova Q A ", "agent": "Sova", "ability": "Q", "stand": [1, 2, 3.456],
                  "yaw": 7.0, "pitch": 0.3, "crouch": True}, maps)
    assert x == {"map": "Ascent", "name": "Sova Q A", "agent": "Sova", "ability": "Q", "stand": [1.0, 2.0, 3.46],
                 "yaw": round(7.0 - 2 * 3.141592653589793, 5), "pitch": 0.3, "crouch": True}
    for bad in ({"map": "Bind", "stand": [0, 0, 0], "yaw": 0, "pitch": 0}, {"map": "Ascent", "stand": [0, 0], "yaw": 0, "pitch": 0},
                {"map": "Ascent", "stand": [0, 0, 0], "yaw": 0, "pitch": 2}, {"map": "Ascent", "stand": [0, "x", 0], "yaw": 0, "pitch": 0}, "x"):
        assert lu.clean(bad, maps) is None
    assert lu.clean({"map": "Ascent", "stand": [0, 0, 0], "yaw": 0, "pitch": 0, "ability": "Z"}, maps)["ability"] == ""
    a = lu.save(tmp_path, x)
    b = lu.save(tmp_path, dict(x, name="Other"))
    assert a != b and [y["name"] for y in lu.read(tmp_path)] == ["Sova Q A", "Other"]
    assert lu.save(tmp_path, dict(x, name="Renamed"), a) == a and lu.read(tmp_path)[0]["name"] == "Renamed"
    assert lu.delete(tmp_path, b) and not lu.delete(tmp_path, b) and len(lu.read(tmp_path)) == 1
    assert lu.drill_id("Ascent") == lu.drill_id("ascent") and lu.drill_id("Ascent").startswith("l-") and len(lu.drill_id("Bind")) == 12
    assert dr.KINDS["lineup"] == "°" and dr.MODE_NAMES["lineup"] == "Lineups"
    # from the strat book: abilities without a lineup, one per agent, key and place
    strats = [{"name": "A split", "map": "Ascent", "data": {"steps": [{"items": [
        {"t": "ab", "a": "Sova", "s": "Ability1", "x": 100, "y": 100}, {"t": "ab", "a": "Sova", "s": "Ability1", "x": 110, "y": 100},
        {"t": "ab", "a": "Viper", "s": "Ability2", "x": 900, "y": 900}, {"t": "ab", "a": "Omen", "s": "Grenade", "c": "them"},
        {"t": "ab", "a": "Omen", "s": "Ability2", "k": "1"}]}]}}]
    ideas = lu.from_strats(strats, [{"map": "Ascent", "agent": "Viper", "ability": "E"}], lambda x, y: "A Main" if x < 500 else "B")
    assert ideas == [{"map": "Ascent", "agent": "Sova", "ability": "Q", "where": "A Main", "strat": "A split", "name": "Sova Q A Main"}]


def test_pages(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    _spots(c, pid)                                                     # the spots for the map are built
    page = c.get(f"/profiles/{pid}/aim/lineups").data.decode()
    assert "Record a lineup" in page and "<option>testmap</option>" in page.lower() and "No lineups yet" in page
    assert f"/profiles/{pid}/aim/lineups" in c.get(f"/profiles/{pid}/aim/maps").data.decode()
    r = c.get(f"/profiles/{pid}/aim/lineups/record?map=testmap&agent=Sova&ability=Q&name=Sova+Q")
    assert r.status_code == 302
    r = c.get(r.headers["Location"])
    assert r.status_code == 200
    boot = json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    assert boot["mode"] == "lineup" and boot["record"] == {"name": "Sova Q", "agent": "Sova", "ability": "Q"}
    assert boot["spot"] is None and len(boot["start"]) == 4 and boot["can_save"] is False
    name = boot["map"]
    save = boot["lineups_api"]
    assert c.post(save, json={"map": "Nope", "stand": [0, 0, 0], "yaw": 0, "pitch": 0}).status_code == 400
    lid = c.post(save, json={"map": name, "name": "Sova Q", "agent": "Sova", "ability": "Q", "stand": boot["start"][:3],
                             "yaw": 0.5, "pitch": 0.1}).get_json()["id"]
    assert c.post(save, json={"id": lid, "map": name, "name": "Sova Q", "agent": "Sova", "ability": "Q",
                              "stand": boot["start"][:3], "yaw": 0.6, "pitch": 0.1}).get_json()["id"] == lid
    # practice: every lineup of the map, or one
    r = c.get(f"/profiles/{pid}/aim/lineups/{name}")
    boot = json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    assert boot["record"] is None and [x["id"] for x in boot["lineups"]] == [lid] and boot["lineups"][0]["yaw"] == 0.6
    assert boot["drill"]["id"] == lu.drill_id(name) and boot["can_save"] is True
    assert c.get(f"/profiles/{pid}/aim/lineups/{name}?ids=0000000000").status_code == 404
    r = c.post(boot["runs_api"], json={"kind": "whatever", "reps": [1.2, None, 0.8]})
    assert r.status_code == 200 and r.get_json()["history"]["best"] == 0.8
    page = c.get(f"/profiles/{pid}/aim/lineups").data.decode()
    assert "Practise them" in page and "best session 0.8° off" in page
    assert c.post(f"/profiles/{pid}/aim/lineups/{lid}/delete").status_code == 302
    assert c.get(f"/profiles/{pid}/aim/lineups/{name}").status_code == 404           # none left to practise


def test_drill_js():
    for x in ("const LINEUP = MODE === 'lineup', RECORD = LINEUP && !!C.record;", "if (LINEUP && S.phase === 'run') { lineupThrow(); return; }",
              "if (pos > LU_POS) { S.reps.push(null);", "if (LINEUP) return RECORD || !LU.length ? C.start : lineupStart(curLU());",
              "const r = await fetch(C.lineups_api, {method: 'POST'", "if (LINEUP) return C.title || T('Lineups');"):
        assert x in DJ, x
    tpl = (ROOT / "nexus/web/templates/aim_maps.html").read_text()
    assert "{% elif unit == '°' %}{{ '%.1f'|format(x) }}°" in tpl                 # the weekly view in degrees (4.77 too)


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Lineups", "Record a lineup", "Practise them", "off the lineup", "off the spot", "Off your lineups",
              "Your lineups", "From your strat book", "record it", "stand and aim, then your shoot key saves it"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 81)
    assert "## 4.81" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
