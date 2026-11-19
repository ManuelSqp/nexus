"""4.52: general aim drills on the maps' real spots: hold an angle, attacking (you move), tracking, clear a site."""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"
TEMPLATES = ROOT / "nexus" / "web" / "templates"


# ------------------------------------------------------------------------------------------------ fights and spots
def _ctx(attacking="Blue"):
    """One round: Raze (Blue) kills Sova (Red) at 20 s; Raze walks in along x, Sova stands."""
    me, kp = "p-sova", "p-raze"
    players = {me: SimpleNamespace(name="adv1ce", tag="LFT", agent="Sova", team="Red"),
               kp: SimpleNamespace(name="enemy", tag="EU", agent="Raze", team="Blue")}
    kill = SimpleNamespace(killer=kp, victim=me, t_round_ms=20000, weapon="Vandal")
    rnd = SimpleNamespace(index=0, kills=[kill], side_of=lambda t: "attack" if t == attacking else "defense")
    match = SimpleNamespace(match_id="ABC-1", map_name="Ascent", rounds=[rnd], players=players,
                            team_of=lambda p: players[p].team)
    vpath = [[round(t * 0.2, 2), 10.0, 0.0, 5.0, 0.5] for t in range(0, 110)]
    kpath = [[round(t * 0.2, 2), 30.0 - t * 0.05, 0.0, 5.0, -1.5] for t in range(0, 110)]
    return SimpleNamespace(zones=object(), mi=object(), match=match, offsets={0: 1000}, index={me: 0, kp: 1},
                           reviews=lambda i: {0: {"where": "A Site", "kwhere": "A Main"}},
                           round_view=lambda i: {"paths": {0: vpath, 1: kpath}})


def test_fights_of_a_match():
    f = dr.fights_of(_ctx())[0]
    assert f["won"] == "attack" and f["az"] == "A Main" and f["dz"] == "A Site" and f["round"] == 0
    assert f["d"] == [10.0, 0.0, 5.0] and f["a"] == [25.0, 0.0, 5.0]               # the killer attacks
    assert abs(f["a0"][0] - (25.0 + 2 / 0.2 * 0.05)) < 0.01                          # 2 s before
    assert f["route"][0][0] > f["route"][-1][0] and f["route"][-1] == [25.0, 0.0, 5.0]
    g = dr.fights_of(_ctx(attacking="Red"))[0]                                       # the killer defends
    assert g["won"] == "defense" and g["dz"] == "A Main" and g["az"] == "A Site" and g["d"] == [25.0, 0.0, 5.0]
    assert dr.fights_of(SimpleNamespace(zones=None, mi=None, match=None)) == []


def _fight(d, a, dz="A Site", az="A Main", won="defense", rnd=0):
    route = [[a[0] + 8 - k, 0.0, a[2]] for k in range(9)]
    return {"a": a, "d": d, "a0": [a[0] + 2, 0.0, a[2]], "az": az, "dz": dz, "won": won, "route": route, "round": rnd}


def test_spots_of_a_map():
    fs = [_fight([10.0, 0.0, 5.0], [25.0, 0.0, 5.0]), _fight([10.5, 0.0, 5.2], [25.0, 0.0, 8.0], won="attack", rnd=1),
          _fight([14.0, 0.0, 9.0], [25.0, 0.0, 2.0], rnd=2), _fight([60.0, 0.0, 60.0], [70.0, 0.0, 60.0], "B Site", "B Main")]
    sp = dr.spots("Ascent", fs)
    a = sp["angles"][0]
    assert a["dz"] == "A Site" and a["az"] == "A Main" and a["count"] == 3 and a["won_def"] == 2
    assert a["hold"] == [10.5, 0.0, 5.2] and len(a["peeks"]) == 3 and len(a["defs"]) == 2       # 2 within 1.5 m
    assert a["hold_yaw"] > 0 and a["start_yaw"] < 0                    # looking +x at them, -x back at you
    assert len(a["id"]) == 10 and a["id"] == dr.spots("Ascent", fs)["angles"][0]["id"]          # stable
    assert a["id"] != dr.spots("Bind", fs)["angles"][0]["id"]
    s = next(x for x in sp["sites"] if x["dz"] == "A Site")
    assert s["az"] == "A Main" and len(s["hides"]) == 2 and len(s["route"]) == 9 and s["count"] == 3
    assert {x["dz"] for x in sp["angles"]} == {"A Site", "B Site"}
    far = [_fight([0.0, 0.0, 0.0], [80.0, 0.0, 0.0], "C Site", "C Main"), _fight([5.0, 0.0, 5.0], [9.0, 0.0, 5.0], "Attacker Spawn", "Mid")]
    sp2 = dr.spots("Ascent", fs + far)
    assert {x["dz"] for x in sp2["angles"]} == {"A Site", "B Site"}                 # too far; a spawn
    assert {x["dz"] for x in sp2["sites"]} == {"A Site", "B Site"}               # a spawn; no way in (80 m away)


def test_runs_of_each_kind(tmp_path):
    assert dr.clean_run({"kind": "attack", "reps": [45.2, None]})["reps"] == [45.2, None]
    assert dr.clean_run({"kind": "death", "reps": [45.2]}) is None                    # a death drill is shorter
    t = dr.clean_run({"kind": "track", "reps": [87.5], "detail": {"body": 96.1, "x": "no", "y": float("nan")}})
    assert t["kind"] == "track" and t["detail"] == {"body": 96.1}
    assert dr.clean_run({"kind": "track", "reps": [101]}) is None
    assert dr.clean_run({"kind": "nope", "reps": [0.4]})["kind"] == "death"
    dr.add_run(tmp_path, "g-track-0123456789", t)
    dr.add_run(tmp_path, "g-track-0123456789", dict(t, reps=[60.0]))
    s = dr.summary(dr.read_runs(tmp_path)["g-track-0123456789"], "track")
    assert s["best"] == 87.5 and s["kind"] == "track" and s["medians"] == [87.5, 60.0]
    assert dr.summary([{"reps": [0.5, 0.3]}], "hold")["best"] == 0.3
    k = dr.default_keys()
    assert k["forward"][0] == "KeyW" and k["crouch"][0] == "KeyC" and k["walk"][0] == "ShiftLeft"
    assert not dr.clashes(k)


# ------------------------------------------------------------------------------------------------ the pages
def _spots(c, pid, name=""):
    for _ in range(100):
        d = c.get(f"/api/profiles/{pid}/aim/spots?map={name}").get_json()
        if not d["pending"] and not d["working"]:
            return d
        time.sleep(0.1)
    raise AssertionError("the spots weren't worked out")


def test_spots_and_play(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    for x in ('data-tab="hold"', 'data-tab="attack"', 'data-tab="track"', 'data-tab="clear"', 'id="am-plan"',
              '"spots_api"', '"play"', '"peeks"'):
        assert x in page, x
    d = _spots(c, pid)
    assert d["map"] == "Testmap" and d["maps"][0]["name"] == "Testmap" and d["fights"] >= 1
    assert d["angles"], d
    a = d["angles"][0]
    assert a["best"] == {"hold": None, "attack": None, "track": None}
    for mode in ("hold", "attack", "track"):
        r = c.get(f"/profiles/{pid}/aim/play/{mode}/testmap/{a['id']}?styles=jiggle,two,bad&diff=pro&gun=Sheriff&reps=7")
        assert r.status_code == 200, mode
        view = r.data.decode()
        boot = json.loads(view.split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
        assert boot["mode"] == mode and boot["spot"]["id"] == a["id"] and boot["drill"]["id"] == f"g-{mode}-{a['id']}"
        assert {k: boot["opts"][k] for k in ("styles", "diff", "reps", "react")} == {"styles": ["jiggle", "two"], "diff": "pro", "reps": 7, "react": 0.3}
        assert boot["gun"]["name"] == "Sheriff" and boot["list"].endswith("#" + mode) and 'id="dr-move"' in view
        assert "Watch this death in the replay" not in view
    hold = f"/api/profiles/{pid}/aim/drill/g-hold-{a['id']}/runs"
    r = c.post(hold, json={"kind": "death", "reps": [0.31, None], "detail": {"style_jiggle": 0.31}})
    assert r.status_code == 200 and r.get_json()["history"]["best"] == 0.31
    assert _spots(c, pid)["angles"][0]["best"]["hold"] == 0.31
    runs = dr.read_runs(Path(app.extensions["nexus"]["store"].data_dir) / "profiles" / str(pid) / "stats")
    assert runs[f"g-hold-{a['id']}"][0]["kind"] == "hold"                             # the id decides the kind
    assert c.post(f"/api/profiles/{pid}/aim/drill/g-fly-{a['id']}/runs", json={"reps": [1]}).status_code == 404
    assert c.get(f"/profiles/{pid}/aim/play/fly/testmap/{a['id']}").status_code == 404
    assert c.get(f"/profiles/{pid}/aim/play/hold/nomap/{a['id']}").status_code == 404
    assert c.get(f"/profiles/{pid}/aim/play/hold/testmap/0000000000").status_code == 404
    for s in d["sites"][:1]:
        assert c.get(f"/profiles/{pid}/aim/play/clear/testmap/{s['id']}").status_code == 200


def test_spots_without_maps(app):  # noqa: F811
    c = setup_admin(app)
    pid = add_profile(c)
    d = c.get(f"/api/profiles/{pid}/aim/spots").get_json()
    assert d["maps"] == [] and d["map"] == "" and d["angles"] == [] and d["sites"] == []


# ------------------------------------------------------------------------------------------------ the scripts
def test_scripts():
    dj = (STATIC / "drill.js").read_text()
    for x in ("const MODE = C.mode || 'death'", "function peekPath(P, style, delay)", "function trackPath(P, secs)",
              "function move(dt)", "function seesMe(f)", "function clearTick()", "function trackTick(dt)",
              "RUN = 6.75, WALK = 3.6, CROUCH = 2.4", "ACCURATE = 1.75", "if (sp > ACCURATE)", "function radar(g, toR)",
              "kind: MODE", "detail: details()", "V().blocked(", "'jiggle'", "'jump'", "'crouch'"):
        assert x in dj, x
    m3 = (STATIC / "map3d.js").read_text()
    assert "blocked: (x, z, y) =>" in m3 and "if (OWN) saveOpt();" in m3
    aj = (STATIC / "aim_maps.js").read_text()
    for x in ("C.spots_api", "function plan()", "function spotCard()", "function playUrl(s)", "history.replaceState"):
        assert x in aj, x
    html = (TEMPLATES / "drill_view.html").read_text()
    assert 'id="dr-move"' in html and 'id="dr-his-l"' in html and "{% if boot.watch %}" in html
    assert "'aim_play'" in (TEMPLATES / "base.html").read_text()


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Hold an angle", "Attacking: you peek", "Tracking", "Clear a site", "Wide swing", "Jiggle peek",
              "Crouch peek", "Jump peek", "Two at once", "Still: accurate", "Moving: shots go wide", "Peeks won",
              "Spot taken", "On his head", "Crosshair placement", "Stopped when you shot", "Move forward", "Crouch"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 52)
    assert "## 4.52.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
