"""4.59: the drills a match points to (practice what cost you rounds); your progress on each spot."""
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
ME = "adv1ce#lft"


def _f(won, a, d, dz="B Main", victim=ME, rnd=0, **kw):
    return dict({"a": list(a), "d": list(d), "a0": list(a), "az": "Mid", "dz": dz, "won": won, "route": [list(a)],
                 "round": rnd, "victim": victim}, **kw)


SP = {"angles": [{"id": "ang1", "dz": "B Main", "az": "Mid", "hold": [10.0, 0.0, 10.0]},
                 {"id": "ang2", "dz": "A Short", "az": "A Lobby", "hold": [50.0, 0.0, 50.0]}],
      "sites": [{"id": "site1", "dz": "B Site", "az": "B Main"}],
      "retakes": [{"id": "rt1", "site": "B", "dz": "B"}]}


def test_suggest():
    fs = [_f("attack", [5, 0, 5], [11, 0, 10], rnd=2),                     # defending near ang1: hold
          _f("attack", [5, 0, 5], [10.5, 0, 9.5], rnd=7),                   # again
          _f("defense", [12, 0, 12], [9, 0, 10], dz="B Site", rnd=4),       # attacking onto B Site: entry
          _f("defense", [48, 0, 48], [50.5, 0, 50.5], dz="A Short", rnd=5),  # attacking elsewhere: take ang2
          _f("attack", [5, 0, 5], [20, 0, 20], post=10.0, site="B", rnd=9),  # defending after a plant: retake
          _f("defense", [5, 0, 5], [20, 0, 20], post=5.0, site="B", rnd=11),  # attacking after a plant: post-plant
          _f("attack", [5, 0, 5], [90, 0, 90], rnd=12),                     # nowhere near a spot
          _f("attack", [5, 0, 5], [11, 0, 10], victim="someone#else", rnd=3)]
    got = dr.suggest("adv1ce#LFT", fs, SP)
    assert got[0] == {"mode": "hold", "id": "ang1", "dz": "B Main", "az": "Mid", "deaths": 2, "rounds": [3, 8]}
    assert [(g["mode"], g["id"], g["rounds"]) for g in got[1:]] == [
        ("entry", "site1", [5]), ("attack", "ang2", [6]), ("retake", "rt1", [10]), ("postplant", "rt1", [12])]
    assert dr.suggest("nobody#x", fs, SP) == [] and len(dr.suggest(ME, fs, SP, n=2)) == 2


def test_fights_say_whose_death():
    me, kp = "p-sova", "p-raze"
    players = {me: SimpleNamespace(name="adv1ce", tag="LFT", agent="Sova", team="Red"),
               kp: SimpleNamespace(name="enemy", tag="EU", agent="Raze", team="Blue")}
    kill = SimpleNamespace(killer=kp, victim=me, t_round_ms=20000, weapon="Vandal")
    rnd = SimpleNamespace(index=0, kills=[kill], side_of=lambda t: "attack" if t == "Blue" else "defense")
    match = SimpleNamespace(match_id="ABC-1", map_name="Ascent", rounds=[rnd], players=players, team_of=lambda p: players[p].team)
    vpath = [[round(t * 0.2, 2), 40.0 - t * 0.2, 0.0, 5.0, 0.5] for t in range(0, 110)]
    kpath = [[round(t * 0.2, 2), 10.0, 0.0, 5.0, -1.5] for t in range(0, 110)]
    ctx = SimpleNamespace(zones=object(), mi=object(), match=match, offsets={0: 1000}, index={me: 0, kp: 1},
                          reviews=lambda i: {0: {"where": "B Site", "kwhere": "B Site"}},
                          round_view=lambda i: {"paths": {0: vpath, 1: kpath}, "spike": [], "util": []})
    assert dr.fights_of(ctx)[0]["victim"] == "adv1ce#lft" and dr.VERSION == 5


def test_suggest_api_and_trend(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    d = _spots(c, pid)
    s = c.get(f"/api/profiles/{pid}/aim/suggest").get_json()
    assert s["map"].lower() == "testmap" and s["pending"] is False and isinstance(s["items"], list)
    for it in s["items"]:
        assert it["mode"] in ("hold", "attack", "entry", "retake", "postplant") and it["deaths"] >= 1
    assert c.get(f"/api/profiles/{pid}/aim/suggest?match=nope").get_json()["items"] == []
    a = d["angles"][0]
    for reps in ([0.9, 0.8], [0.6, 0.7, 0.5]):
        assert c.post(f"/api/profiles/{pid}/aim/drill/g-hold-{a['id']}/runs", json={"kind": "hold", "reps": reps}).status_code == 200
    a2 = next(x for x in _spots(c, pid)["angles"] if x["id"] == a["id"])
    assert a2["trend"] == {"hold": [0.9, 0.6]} and a2["best"]["hold"] == 0.5
    page = c.get(f"/profiles/{pid}/aim/maps?match=abc").data.decode()
    assert f'"suggest_api": "/api/profiles/{pid}/aim/suggest"' in page and '"match": "abc"' in page
    assert 'id="am-suggest"' in page


def test_scripts():
    aj = (STATIC / "aim_maps.js").read_text()
    for x in ("async function loadSuggest(", "function renderSuggest()", "function openSpot(mode, mapName, id)",
              "function spark(meds, higher)", "function trendText(meds, higher)", "loadSuggest();",
              "spark((s.trend || {})[tab], pctTab())", "`${esc(k)} <span translate=\"no\">${esc(n)}</span>`",
              'name="am-diff" value="${esc(k)}"', "esc(it.rounds.map(Number).join(', '))",
              "<h3>${esc(T('Practice what cost you rounds'))}</h3>"):
        assert x in aj, x
    job = (ROOT / "nexus/web/templates/job.html").read_text()
    assert "url_for('aim_maps', pid=p.id, match=j.match_id)" in job
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Practice what cost you rounds", "Your last match", "better", "worse", "about the same"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 59)
    assert "## 4.59.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
