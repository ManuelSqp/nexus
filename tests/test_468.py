"""4.68: match-day warm-up (this week's map, the scouted opponent's sites); strats for the counter style."""
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_454 import _with_retakes  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import _premier_team, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import stratstyle as ss  # noqa: E402

ROOT = Path(__file__).parent.parent


def test_sites_and_match_plan():
    assert [dr.site_of(x) for x in ("B Main", "Back B", "A Site", "Mid", "", "Market")] == ["B", "B", "A", None, None, None]
    s = {"maps": {"Ascent": {"attack": {"sites_hit": {"A": {"plants": 2}, "B": {"plants": 6}}},
                             "defense": {"enemy_plants": {"A": {"plants": 4, "retakes_won": "25%"}, "B": {"plants": 2, "retakes_won": "0%"}}}}}}
    assert dr.opponent_sites(s, "ascent") == ("B", "A") and dr.opponent_sites(None, "Ascent") == (None, None)
    sp = {"angles": [{"id": "a1", "dz": "Mid", "az": "Market", "count": 9}, {"id": "a2", "dz": "B Site", "az": "B Main", "count": 3},
                     {"id": "a3", "dz": "B Lobby", "az": "B Site", "count": 2}, {"id": "a4", "dz": "A Site", "az": "A Main", "count": 1}],
          "sites": [{"id": "s1", "dz": "B Site", "count": 5}, {"id": "s2", "dz": "A Site", "count": 2}],
          "retakes": [{"id": "r1", "site": "B", "dz": "B", "count": 4}, {"id": "r2", "site": "A", "dz": "A", "count": 1}]}
    q = dr.match_warmup(sp, "Ascent", "B", "A")
    assert q == ["g-hold-a2@Ascent", "g-hold-a3@Ascent", "g-track-a1@Ascent", "g-retake-r1@Ascent",
                 "g-entry-s2@Ascent", "g-postplant-r2@Ascent"]
    q = dr.match_warmup(sp, "Ascent")                                         # nobody scouted: the most fought spots
    assert q[:3] == ["g-hold-a1@Ascent", "g-hold-a2@Ascent", "g-track-a1@Ascent"] and "g-entry-s1@Ascent" in q
    assert len(q) <= dr.WARM_MAX and dr.match_warmup({}, "Ascent") == []


def test_match_warmup_route(app, synthetic):  # noqa: F811 (fixture)
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    _with_retakes(app, c, pid)
    d = _spots(c, pid)
    r = c.get(f"/profiles/{pid}/aim/warmup?map={d['map']}")
    loc = urlparse(r.headers["Location"])
    assert r.status_code == 302 and "/aim/play/" in loc.path and f"/{d['map']}/" in loc.path
    assert int(parse_qs(loc.query)["wt"][0]) == len(parse_qs(loc.query).get("queue", [""])[0].split(",")) + 1
    r = c.get(f"/profiles/{pid}/aim/warmup?map=Nowhere")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/profiles/{pid}/aim/maps")


def test_strat_styles():
    assert ss.guess("B rush") == "aggressive" and ss.guess("A anchor stack") == "defensive"
    assert ss.guess("Split A with util") == "execute" and ss.guess("Plan 3") is None
    util = {"steps": [{"items": [{"t": "smoke"}] * 4 + [{"t": "molly"}] * 2}]}
    assert ss.guess("Plan 4", "", util) == "execute"
    assert ss.style_of({"name": "B rush", "data": {"style": "defensive"}}) == ("defensive", True)
    assert ss.style_of({"name": "B rush", "data": {}}) == ("aggressive", False)
    strats = [{"id": 1, "map": "Ascent", "side": "defense", "name": "B stack", "style": "defensive"},
              {"id": 2, "map": "Ascent", "side": "attack", "name": "rush", "style": "aggressive"}]
    w = ss.for_counter("aggressive", "ascent", strats)["wants"]
    assert [(x["side"], x["missing"]) for x in w] == [("attack", False), ("defense", True)]
    assert ss.for_counter("defensive", "Ascent", strats)["wants"][0]["strats"][0]["id"] == 1


def test_strat_book_against_a_team(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    tid = _premier_team(app, c, monkeypatch)
    store = app.extensions["nexus"]["store"]
    sd = app.extensions["nexus"]["stats"].team_dir(tid) / "scout"
    sd.mkdir(parents=True, exist_ok=True)
    scouted = {"matches": 6, "players": [], "maps": {"Bind": {"games": 4, "wins": 2, "sides": {},
               "attack": {"plant_median_s": 35, "sites_hit": {"A": {"plants": 7}, "B": {"plants": 3}}}, "defense": {},
               "comps": [{"agents": ["Jett", "Raze", "Omen", "Sova", "Killjoy"], "games": 3}]}}}
    (sd / "t1.json").write_text(json.dumps(scouted))
    (sd / "index.json").write_text(json.dumps({"teams": {"t1": {"id": "t1", "name": "Rivals", "tag": "RV", "matches": 6}}}))
    page = c.get(f"/teams/{tid}/strats").data.decode()
    assert 'id="vs"' in page and "Bind: Defensive" not in page
    page = c.get(f"/teams/{tid}/strats?vs=t1").data.decode()
    assert "Bind: Defensive" in page and "No defensive defense strat yet." in page and "Draw one" in page
    r = c.post(f"/teams/{tid}/strats", data={"map": "Bind", "side": "defense", "style": "defensive", "name": "Rivals: Defensive defense"})
    sid = int(r.headers["Location"].rstrip("/").split("/")[-1])
    assert store.strat(sid)["data"]["style"] == "defensive"
    page = c.get(f"/teams/{tid}/strats?vs=t1").data.decode()
    assert "No defensive defense strat yet." not in page and "Rivals: Defensive defense</a>" in page
    # the editor's save keeps the style; the card's select changes it
    c.post(f"/teams/{tid}/strats/{sid}/save", json={"data": {"steps": [{"name": "Setup", "items": []}], "notes": ""}})
    assert store.strat(sid)["data"]["style"] == "defensive"
    c.post(f"/teams/{tid}/strats/{sid}/style", data={"style": "nonsense"})
    assert "style" not in store.strat(sid)["data"]
    sid2 = store.create_strat(tid, 1, "Bind", "attack", "B rush")
    page = c.get(f"/teams/{tid}/strats").data.decode()
    assert "looks aggressive" in page and f"/strats/{sid2}/style" in page


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Match warm-up: {x}", "Draw one", "no style", "looks {x}"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 68, 0)
    assert "## 4.68.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
