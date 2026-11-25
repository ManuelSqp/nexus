"""4.54: aim on maps: entry, retake (with the spike and a defuse) and post-plant, on spots from the fights after a
plant; the route on the minimap easier to see; the defuse key."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


def _ctx(plant_t=12.0):
    """One round: Raze (Blue, attacking) kills Sova (Red) at 20 s, Sova walking in along x; the spike went down at
    plant_t on B."""
    me, kp = "p-sova", "p-raze"
    players = {me: SimpleNamespace(name="adv1ce", tag="LFT", agent="Sova", team="Red"),
               kp: SimpleNamespace(name="enemy", tag="EU", agent="Raze", team="Blue")}
    kill = SimpleNamespace(killer=kp, victim=me, t_round_ms=20000, weapon="Vandal")
    rnd = SimpleNamespace(index=0, kills=[kill], side_of=lambda t: "attack" if t == "Blue" else "defense")
    match = SimpleNamespace(match_id="ABC-1", map_name="Ascent", rounds=[rnd], players=players,
                            team_of=lambda p: players[p].team)
    vpath = [[round(t * 0.2, 2), 40.0 - t * 0.2, 0.0, 5.0, 0.5] for t in range(0, 110)]
    kpath = [[round(t * 0.2, 2), 10.0, 0.0, 5.0, -1.5] for t in range(0, 110)]
    spike = [{"kind": "plant", "t": plant_t, "site": "B", "who": 1, "x": 12.0, "y": 0.0, "z": 6.0}] if plant_t else []
    return SimpleNamespace(zones=object(), mi=object(), match=match, offsets={0: 1000}, index={me: 0, kp: 1},
                           reviews=lambda i: {0: {"where": "B Site", "kwhere": "B Site"}},
                           round_view=lambda i: {"paths": {0: vpath, 1: kpath}, "spike": spike})


def test_fights_after_a_plant():
    f = dr.fights_of(_ctx())[0]
    assert f["post"] == 8.0 and f["site"] == "B" and f["plant"] == [12.0, 0.0, 6.0]
    assert len(f["droute"]) == 31                                   # every half second over 15 s, standing too
    assert f["droute"][-1] == f["d"] and f["droute"][0][0] > f["droute"][-1][0]     # the defender walked in
    assert "post" not in dr.fights_of(_ctx(plant_t=25.0))[0]        # before the plant
    assert "post" not in dr.fights_of(_ctx(plant_t=None))[0]


def _post(a, start, rnd, site="B", plant=(12.0, 0.0, 6.0), post=20.0, won="defense"):
    """A fight after a plant: the attacker at a, the defender came in from start (30 points, 1 m each)."""
    route = [[start[0] - k * (start[0] - 14.0) / 30, 0.0, start[2] - k * (start[2] - 6.0) / 30] for k in range(31)]
    return {"a": list(a), "d": route[-1], "a0": list(a), "az": "B Site", "dz": "B Site", "won": won, "route": [list(a)],
            "round": rnd, "post": post, "site": site, "plant": list(plant), "droute": route}


def test_retake_spots():
    fs = [_post([8.0, 0.0, 9.0], [50.0, 0.0, 6.0], 0), _post([8.5, 0.0, 9.2], [50.0, 0.0, 7.0], 1, won="attack"),
          _post([15.0, 0.0, 15.0], [12.0, 0.0, 50.0], 2, post=30.0), _post([8.2, 0.0, 9.1], [51.0, 0.0, 6.0], 3),
          _post([80.0, 0.0, 80.0], [13.0, 0.0, 7.0], 4)]               # far off the spike; came from next to it
    r = dr.spots("Ascent", fs)["retakes"]
    assert len(r) == 1
    s = r[0]
    assert s["site"] == "B" and s["dz"] == "B" and s["count"] == 5 and s["won_def"] == 4 and s["plant"] == [12.0, 0.0, 6.0]
    assert s["posts"][0] in ([8.0, 0.0, 9.0], [8.5, 0.0, 9.2], [8.2, 0.0, 9.1])           # the most used first
    assert [80.0, 0.0, 80.0] not in s["posts"] and len(s["posts"]) == 2                    # 25 m; 2 m apart
    assert [len(x["path"]) for x in s["routes"]] == [31, 31] and s["routes"][0]["count"] == 3
    assert s["routes"][0]["path"][0][0] >= 50.0 and s["routes"][1]["path"][0][2] == 50.0
    assert s["routes"][0]["left"] == 40.0 and s["routes"][1]["left"] == 30.0 and s["left"] in (30.0, 40.0)
    assert len(s["id"]) == 10 and s["id"] != dr.spots("Bind", fs)["retakes"][0]["id"]
    assert dr.spots("Ascent", [dict(f, post=None) for f in fs])["retakes"] == []
    assert dr.retakes("Ascent", [_post([8.0, 0.0, 9.0], [13.0, 0.0, 7.0], 0)]) == []        # no way back in


def test_runs_and_keys():
    assert dr.clean_run({"kind": "entry", "reps": [45.2, None]})["kind"] == "entry"
    assert dr.clean_run({"kind": "retake", "reps": [31.5], "detail": {"left": 9.2}})["detail"] == {"left": 9.2}
    assert dr.clean_run({"kind": "postplant", "reps": [0.41]})["reps"] == [0.41]
    assert dr.clean_run({"kind": "postplant", "reps": [45.0]}) is None
    assert dr.summary([{"reps": [20.0, 14.0]}], "retake")["best"] == 14.0
    k = dr.default_keys()
    assert k["defuse"] == ["Digit4", ""] and not dr.clashes(k)
    assert dr.clean_keys({"defuse": "KeyE"})["defuse"] == ["KeyE", ""]


def _with_retakes(the_app, c, pid):
    """The synthetic match's plants are off its map: put fights after a plant into its cache (next to its spots)."""
    d = _spots(c, pid)
    plant = d["angles"][0]["hold"]
    f = next((Path(the_app.extensions["nexus"]["store"].data_dir) / "drills").glob("*.json"))
    data = json.loads(f.read_text())
    route = [[plant[0] + 30 - k, plant[1], plant[2]] for k in range(31)]
    for k in range(4):
        p = [plant[0] + 3 * k, plant[1], plant[2] - 2]
        data["fights"].append({"a": p, "d": route[-1], "a0": p, "az": "X", "dz": "X", "won": "attack", "route": [p],
                               "round": 90 + k, "post": 18.0, "site": "Z", "plant": plant, "droute": route})
    f.write_text(json.dumps(data))
    return d["sites"][0] if d["sites"] else None


def test_entry_retake_postplant_pages(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    for x in ('data-tab="entry"', 'data-tab="retake"', 'data-tab="postplant"', '"foes": [1, 2, 3]'):
        assert x in page, x
    site = _with_retakes(app, c, pid)
    d = _spots(c, pid)
    rt = next(r for r in d["retakes"] if r["site"] == "Z")
    assert rt["best"] == {"retake": None, "postplant": None} and rt["routes"] and rt["posts"]
    if site:
        assert d["sites"][0]["best"] == {"clear": None, "entry": None, "place": None}    # 4.77: place
        r = c.get(f"/profiles/{pid}/aim/play/entry/testmap/{site['id']}?foes=3")
        boot = json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
        assert boot["mode"] == "entry" and boot["opts"]["foes"] == 3 and boot["spot"]["hides"] == site["hides"]
    for mode in ("retake", "postplant"):
        r = c.get(f"/profiles/{pid}/aim/play/{mode}/testmap/{rt['id']}?foes=7&reps=3")
        assert r.status_code == 200, mode
        boot = json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
        assert boot["mode"] == mode and boot["spot"]["plant"] == rt["plant"] and boot["drill"]["id"] == f"g-{mode}-{rt['id']}"
        assert boot["opts"]["foes"] == 2 and boot["opts"]["reps"] == 3 and boot["opts"]["spike"] == 45.0
        assert boot["opts"]["defuse"] == 7.0 and ["defuse", "Defuse (hold)"] in boot["actions"]
    assert c.get(f"/profiles/{pid}/aim/play/retake/testmap/{d['angles'][0]['id']}").status_code == 404   # an angle
    url = f"/api/profiles/{pid}/aim/drill/g-retake-{rt['id']}/runs"
    r = c.post(url, json={"kind": "death", "reps": [21.5, None], "detail": {"left": 11.0}})
    assert r.status_code == 200 and r.get_json()["history"]["best"] == 21.5
    assert next(x for x in _spots(c, pid)["retakes"] if x["site"] == "Z")["best"]["retake"] == 21.5


def test_scripts():
    dj = (STATIC / "drill.js").read_text()
    for x in ("function retakePath(R, delay)", "function swing(f, delay = 0)", "function spikeTick(dt)", "function entryTick()",
              "function fairHides()", "function postStands()", "function routeOnRadar(g, toR, R)", "holds('defuse')",
              "if (S.defusing) { m.vx = 0; m.vz = 0;", "S.phase !== 'run' || S.dead || S.defusing", "sp.half = true",
              "T('The spike went off')", "T('They defused the spike')", "const NFOES = O.foes || 2"):
        assert x in dj, x
    aj = (STATIC / "aim_maps.js").read_text()
    for x in ("case 'entry': return 'entry';", "case 'retake': return 'retake';", "case 'postplant': return 'postplant';",
              "G.retakes", "name=\"am-foes\"", "o.set('foes', String(g.foes))", "own(C.foes || [1, 2, 3], +t.value, g.foes)"):
        assert x in aj, x


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Entry", "Retake", "Post-plant", "Site taken", "Defused", "The spike went off", "They defused the spike",
              "Post-plants won", "Left on the spike", "Defuse (hold)", "defuse (hold)", "retakers left", "attackers left"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 54)
    assert "## 4.54.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
