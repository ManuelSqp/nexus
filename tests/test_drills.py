"""4.51: Practice › Aim on maps: your deaths as aim drills on the real maps, your own keys."""
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import UID, _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"
TEMPLATES = ROOT / "nexus" / "web" / "templates"


# ------------------------------------------------------------------------------------------------ building drills
def _ctx(his=1.2, first="killer", same_team=False):
    """A match with one round: Raze (killer) kills Sova (victim) at 20 s; their paths every 200 ms."""
    me, kp = "p-sova", "p-raze"
    players = {me: SimpleNamespace(name="adv1ce", tag="LFT", agent="Sova", team="Red"),
               kp: SimpleNamespace(name="enemy", tag="EU", agent="Raze", team="Red" if same_team else "Blue")}
    kill = SimpleNamespace(killer=kp, victim=me, t_round_ms=20000, weapon="Vandal")
    rnd = SimpleNamespace(index=0, kills=[kill])
    match = SimpleNamespace(match_id="ABC-1", map_name="Ascent", started_at="2026-11-01T20:00:00Z", rounds=[rnd],
                            players=players, team_of=lambda p: players[p].team)
    vpath = [[round(t * 0.2, 2), 10.0, 0.0, 5.0, 0.5] for t in range(0, 110)]
    kpath = [[round(t * 0.2, 2), 30.0 - t * 0.05, 0.0, 5.0, -1.5] for t in range(0, 110)]
    view = {"paths": {0: vpath, 1: kpath}, "guns": {1: [[0.0, "Vandal"]], 0: [[0.0, "Phantom"]]}}
    review = {"killer_saw": his, "victim_saw": 0.5, "first": first, "open_to": 1, "unseen": False}
    return SimpleNamespace(zones=object(), mi=object(), match=match, offsets={0: 1000}, index={me: 0, kp: 1},
                           reviews=lambda i: {0: {"where": "A Main", "kwhere": "A Lobby", "review": review}},
                           round_view=lambda i: view)


def test_drills_of_a_death():
    out = dr.drills_of(_ctx(his=0.6))
    d = out["p-sova"][0]
    assert d["id"] == "abc-1-0-0" and d["map"] == "Ascent" and d["where"] == "A Main" and d["kwhere"] == "A Lobby"
    assert d["killer"] == 1 and d["victim"] == 0 and d["killer_agent"] == "Raze" and d["weapon"] == "Vandal"
    assert d["my_weapon"] == "Phantom" and d["his"] == 0.6 and d["first"] == "killer"
    assert d["t_kill"] == 20.0 and d["t0"] == 20.0 - dr.MIN_LEAD_S          # 0.6 s + 1.5 s lead < the minimum
    assert d["me"][:3] == [10.0, 0.0, 5.0] and d["me"][3] == 0.5
    assert abs(d["from"][0] - (30.0 - 17.5 / 0.2 * 0.05)) < 0.01             # where he was when the drill starts
    long = dr.drills_of(_ctx(his=3.0))["p-sova"][0]
    assert long["t0"] == round(20.0 - 3.0 - dr.LEAD_S, 2)
    assert dr.drills_of(_ctx(same_team=True)) == {}                           # team kills aren't drills
    assert dr.drills_of(SimpleNamespace(zones=None, mi=None)) == {}           # no map from the game's files


def test_at_holds_the_ends():
    p = [[0.0, 0, 0, 0, 3.0], [1.0, 10, 0, 0, -3.0]]
    assert dr._at(p, -5) == [0, 0, 0, 3.0] and dr._at(p, 5) == [10, 0, 0, -3.0]
    m = dr._at(p, 0.5)
    assert m[0] == 5 and abs(abs(m[3]) - math.pi) < 0.01                      # turning the short way round


def test_spots_group_and_best():
    a = dr.drills_of(_ctx())["p-sova"][0]
    b = dict(a, id="abc-1-3-1", round=3, n=1, me=[11.0, 0.0, 5.5, 0.4])     # the same spot, another round
    c = dict(a, id="abc-1-4-0", round=4, n=0, me=[40.0, 0.0, 40.0, 0.4])     # elsewhere
    runs = {"abc-1-3-1": [{"reps": [0.9, None, 1.5], "his": 1.2}], "abc-1-4-0": [{"reps": [1.4], "his": 1.2}]}
    spots = dr.group([a, b, c], runs)
    assert len(spots) == 2
    s = next(s for s in spots if s["count"] == 2)
    assert s["drill"]["id"] == "abc-1-3-1" and s["best"] == 0.9 and s["beaten"] and s["played"] == 1
    o = next(s for s in spots if s["count"] == 1)
    assert o["best"] == 1.4 and not o["beaten"]


def test_runs_kept(tmp_path):
    assert dr.clean_run({"reps": []}) is None and dr.clean_run({"reps": ["x"]}) is None
    assert dr.clean_run({"reps": [99]}) is None
    r = dr.clean_run({"reps": [0.41234, None], "his": 0.38, "first": {"head": 1, "miss": 1}, "off": 12.34})
    assert r["reps"] == [0.412, None] and r["his"] == 0.38 and r["first"]["head"] == 1 and r["off"] == 12.3
    for i in range(dr.MAX_RUNS + 5):
        data = dr.add_run(tmp_path, "abc-1-0-0", dict(r, reps=[0.5 - i * 0.001]))
    assert len(data["abc-1-0-0"]) == dr.MAX_RUNS
    s = dr.summary(dr.read_runs(tmp_path)["abc-1-0-0"])
    assert s["sessions"] == dr.MAX_RUNS and abs(s["best"] - (0.5 - (dr.MAX_RUNS + 4) * 0.001)) < 1e-9


def test_guns_and_keys():
    v = dr.gun("Vandal")
    assert v["mag"] == 25 and v["head"] == 160 and v["auto"] and v["zoom"] > 1
    assert dr.gun("Knife")["name"] == "Classic"
    from nexus.stats.agentmesh import WEAPONS
    assert set(WEAPONS) == set(dr.GUNS)                                      # every gun the 3D views know
    k = dr.default_keys()
    assert k["reload"] == ["KeyR", ""] and k["restart"] == ["Backspace", ""] and k["shoot"] == ["Mouse0", ""]
    c = dr.clean_keys({"reload": ["KeyR", "Mouse4"], "restart": "KeyR", "shoot": ["Escape"], "nope": ["KeyX"],
                       "watch": ["bad key!"]})
    assert c["reload"] == ["KeyR", "Mouse4"] and c["restart"] == ["KeyR", ""] and "nope" not in c
    assert c["shoot"] == ["Mouse0", ""] and c["watch"] == ["KeyP", ""]       # Esc can't be taken; junk: the default
    assert dr.clashes(c) == [["KeyR", "reload", "restart"]]


# ------------------------------------------------------------------------------------------------ the pages
def _wait(c, pid):
    for _ in range(100):
        d = c.get(f"/api/profiles/{pid}/aim/drills?from=all").get_json()
        if not d["pending"] and not d["working"]:
            return d
        time.sleep(0.1)
    raise AssertionError("the drills weren't worked out")


def test_list_play_and_save(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert "Your deaths as drills" in page and "NEXUS_DRILLS" in page and "aim_maps.js" in page and "keys.js" in page
    d = _wait(c, pid)
    assert d["deaths"] >= 1 and d["spots"] and d["maps"] == ["Testmap"]
    s = d["spots"][0]
    assert s["url"].startswith(f"/profiles/{pid}/aim/drill/{UID}-") and s["best"] is None
    assert (Path(app.extensions["nexus"]["store"].data_dir) / "drills" / f"{UID}.json").is_file()
    view = c.get(s["url"]).data.decode()
    for x in ('id="m3-canvas"', 'id="dr-panel"', 'id="dr-opts"', "motion.js", "drill.js", "keys.js", '"round_api"',
              '"gun": {', '"hp": 150', '"defaults"'):
        assert x in view, x
    boot = json.loads(view.split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    assert boot["drill"]["id"] == s["id"] and boot["sens"] and boot["actions"][0] == ["shoot", "Shoot"]
    rv = c.get(boot["round_api"])
    assert rv.status_code == 200 and str(boot["drill"]["killer"]) in rv.get_json()["paths"]
    r = c.post(boot["runs_api"], json={"reps": [0.5, None, 0.7], "his": boot["drill"]["his"], "first": {"head": 2}})
    assert r.status_code == 200 and r.get_json()["history"]["best"] == 0.5
    assert c.post(boot["runs_api"], json={"reps": "no"}).status_code == 400
    s2 = next(x for x in _wait(c, pid)["spots"] if x["id"] == s["id"])
    assert s2["best"] == 0.5 and s2["played"] == 1
    assert c.get(f"/profiles/{pid}/aim/drill/{UID}-99-0").status_code == 404
    # queue: "Play all in a row" goes on to the next one
    ids = [x["ids"][0] for x in _wait(c, pid)["spots"]]
    if len(ids) > 1:
        v2 = c.get(f"{s['url']}?queue={ids[1]}").data.decode()
        assert f'/aim/drill/{ids[1]}' in v2


def test_keys_per_user(app):  # noqa: F811
    c = setup_admin(app)
    d = c.get("/api/aim/keys").get_json()
    assert d["keys"] == dr.default_keys()
    r = c.post("/api/aim/keys", json={"reload": ["KeyR", ""], "restart": ["KeyR", ""]}).get_json()
    assert r["clashes"] == [["KeyR", "reload", "restart"]] and r["keys"]["restart"] == ["KeyR", ""]
    assert c.get("/api/aim/keys").get_json()["keys"]["restart"] == ["KeyR", ""]


def test_nav_and_search(app):  # noqa: F811
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert "Aim on maps" in page and "Hold an angle" in page


# ------------------------------------------------------------------------------------------------ the scripts
def test_scripts():
    m3 = (STATIC / "map3d.js").read_text()
    assert "const OWN = !C.replay && !C.drill;" in m3 and "if (C.replay || C.drill)" in m3
    assert "(me.fov || 71)" in m3 and "bones: k =>" in m3 and "const HIT = ['Head'" in m3
    assert m3.count("if (!OWN || document.pointerLockElement !== canvas) return;") == 2
    mo = (STATIC / "motion.js").read_text()
    for x in ("window.NexusMotion =", "function motion(path, t, p, hold = 'hold')", "function deathClip(p, from)",
              "'death_back'", "'death_left'", "function utilObjects(", "block: true"):
        assert x in mo, x
    rj = (STATIC / "replay.js").read_text()
    assert "const NM = window.NexusMotion;" in rj and "NM.deathClip(p, kp)" in rj
    dj = (STATIC / "drill.js").read_text()
    for x in ("function rayCapsule(", "function hitboxes(f)", "function shoot()", "function startReload()",
              "function failRep(label, killer = null)", "function flashes()", "KB.actionsOf(keys", "unadjustedMovement", "const EYE = 1.85",
              "YAW * (+C.sens || 0.4)", "if (wall === null || wall < hit[2] - 0.02) hit = null;", "function throughSmoke("):
        assert x in dj, x
    kj = (STATIC / "keys.js").read_text()
    assert "window.NexusKeys =" in kj and "'WheelUp'" in kj and "Esc always stops" in kj
    for t in ("replay_view.html", "drill_view.html"):
        html = (TEMPLATES / t).read_text()
        assert html.index("map3d.js") < html.index("motion.js"), t


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Aim on maps", "Your deaths as drills", "His time", "He got you", "Faster than him", "Your keys",
              "Options & keys", "Restart the drill", "Watch how he did it", "Play drill", "Count only headshots"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 51)
    assert "## 4.51.0" in (ROOT / "CHANGELOG.md").read_text()
