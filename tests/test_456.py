"""4.56: the enemies use their utility in Aim on maps (what their side threw around these fights in your replays)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_454 import _with_retakes  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


def _ctx(plant_t=None, util=()):
    """Raze (Blue, attacking, index 1) kills Sova (Red, index 0) at 20 s; Sova walks in along x from 40 to 18."""
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
                           round_view=lambda i: {"paths": {0: vpath, 1: kpath}, "spike": spike, "util": list(util)})


def _u(typ, t0, t1, x, z, owner=1, agent="Brimstone", y=0.0):
    return {"t0": t0, "t1": t1, "type": typ, "agent": agent, "slot": "", "owner": owner, "x": x, "z": z, "y": y}


def test_the_utility_around_a_fight():
    util = [_u("smoke", 12.0, 27.0, 14.0, 6.0, agent="Omen", y=None),       # 8 s before, near: kept (y unknown)
            _u("flash", 19.0, 19.5, 15.0, 5.0, owner=0, agent="Sova"),       # the defenders' (side d)
            _u("damage", 21.0, 28.0, 12.0, 5.0),                             # 1 s after
            _u("damage", 27.0, 34.0, 12.0, 5.0),                             # 7 s after: too late
            _u("smoke", 2.0, 17.0, 14.0, 6.0),                               # 18 s before: too early
            _u("smoke", 18.0, 33.0, 80.0, 80.0),                             # far away
            _u("orb", 18.0, None, 12.0, 5.0), _u("smoke", 18.0, 30.0, 12.0, 5.0, owner=None)]   # not kept
    f = dr.fights_of(_ctx(util=util))[0]
    assert f["t"] == 20.0
    assert f["util"] == [["smoke", "Omen", "a", -8.0, 15.0, 14.0, None, 6.0], ["flash", "Sova", "d", -1.0, 0.5, 15.0, 0.0, 5.0],
                         ["damage", "Brimstone", "a", 1.0, 7.0, 12.0, 0.0, 5.0]]
    assert "util" not in dr.fights_of(_ctx())[0]
    # after a plant: on the site until the spike goes off (45 s), around the spike
    f = dr.fights_of(_ctx(plant_t=12.0, util=util + [_u("damage", 50.0, 57.0, 12.5, 6.0), _u("damage", 58.0, 60.0, 12.0, 6.0)]))[0]
    assert ["damage", "Brimstone", "a", 7.0, 7.0, 12.0, 0.0, 5.0] in f["util"]            # 27 s: 15 s after the plant
    assert ["damage", "Brimstone", "a", 30.0, 7.0, 12.5, 0.0, 6.0] in f["util"]           # 50 s: still before 57
    assert not any(u[3] == 38.0 for u in f["util"])                                         # 58 s: the spike went off


def test_the_utility_on_the_spots():
    def fight(rnd, util, **kw):
        return dict({"a": [10.0, 0.0, 5.0], "d": [18.0, 0.0, 5.0], "a0": [8.0, 0.0, 5.0], "az": "B Main", "dz": "B Site",
                     "won": "attack", "route": [[2.0, 0.0, 5.0], [6.0, 0.0, 5.0], [10.0, 0.0, 5.0]], "round": rnd,
                     "util": util}, **kw)
    smoke = ["smoke", "Omen", "a", -5.0, 15.0, 14.0, None, 6.0]
    flash = ["flash", "Breach", "a", -1.0, 0.5, 15.0, 0.0, 5.0]
    fs = [fight(0, [smoke, flash]), fight(0, [smoke, flash]), fight(1, [smoke]), fight(2, [])]
    sp = dr.spots("Ascent", fs)
    assert sp["angles"][0]["util"] == [[smoke, flash], [smoke]]          # one per round, the most first; none left out
    assert sp["sites"][0]["util"] == [[smoke, flash], [smoke]]
    assert dr._util_sets(fs, lambda f: 10.0)[1] == [["smoke", "Omen", "a", 5.0, 15.0, 14.0, None, 6.0]]
    assert len(dr._util_sets([fight(k, [smoke]) for k in range(20)])) == 10


def test_play_has_the_utility_switch(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    _with_retakes(app, c, pid)
    d = _spots(c, pid)
    rt = next(r for r in d["retakes"] if r["site"] == "Z")
    assert "util" in rt and "util" in d["angles"][0]
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert '"util_modes": ["hold", "attack", "entry", "retake", "postplant"]' in page

    def boot(url):
        r = c.get(url)
        assert r.status_code == 200, url
        return json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    assert boot(f"/profiles/{pid}/aim/play/retake/testmap/{rt['id']}")["opts"]["util"] is True
    assert boot(f"/profiles/{pid}/aim/play/postplant/testmap/{rt['id']}?util=0")["opts"]["util"] is False
    assert boot(f"/profiles/{pid}/aim/play/hold/testmap/{d['angles'][0]['id']}")["opts"]["util"] is True
    assert boot(f"/profiles/{pid}/aim/play/track/testmap/{d['angles'][0]['id']}")["opts"]["util"] is False


def test_scripts():
    dj = (STATIC / "drill.js").read_text()
    for x in ("const UTIL = !!O.util && MODE !== 'death';", "function chooseUtil()", "function lead(set)",
              "function placeUtil(set)", "function utilTick(dt)", "const wallAt = (x, z) =>", "Math.random() < 0.15",
              "ENEMY_SIDE = {hold: 'a', attack: 'd', entry: 'd', retake: 'a', postplant: 'd'}",
              "it.t0 = SPIKE ? u[3] - (SPIKE_S - SP.left)", "react * (S.t < S.revealed ? REVEAL_REACT : 1)",
              "if (f.fov && !(S.t < S.revealed))", "* (S.slowed ? SLOW : 1)", "!V().blocked(x, z, m.y) && !wallAt(x, z)",
              "T('Burnt in their utility')", "const utilList = () => (S.R ? S.R.util || [] : S.U);",
              "Viper: 24", "Brimstone: 60"):
        assert x in dj, x
    assert "if (S.R) flashes();" not in dj
    aj = (STATIC / "aim_maps.js").read_text()
    for x in ("const ENEMY = {hold: 'a', attack: 'd', entry: 'd', retake: 'a', postplant: 'd'};", 'name="am-util"',
              "if (ENEMY[tab] && !g.util) o.set('util', '0');", "g.util = g.util !== false;"):
        assert x in aj, x


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Burnt in their utility", "revealed", "slowed", "Their utility", "mollies", "None in your replays here yet."):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert nexus.__version__ == "4.56.0" and dr.VERSION == 4
    assert "## 4.56.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.56.0**" in (ROOT / "README.md").read_text()
