"""4.47: Custom games: replays of matches that aren't in the stats import get their match details by match id."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_replayfile as trf  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus import replayfile  # noqa: E402
from nexus.henrik import HenrikClient, HenrikError  # noqa: E402
from nexus.parse import parse_match  # noqa: E402
from nexus.web import replays as wr  # noqa: E402

UID = "7a1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e6"


def _custom(app, synthetic, monkeypatch, found=True):  # noqa: F811
    """A Custom game's replay on the server, its match details only at (fake) HenrikDev."""
    store = app.extensions["nexus"]["store"]
    store.set("henrik_api_key", "test-key")
    raw = json.loads(Path(synthetic["match"]).read_text())
    raw["data"]["metadata"]["match_id"] = UID
    q = raw["data"]["metadata"].get("queue")
    if isinstance(q, dict):
        q.update(id="custom", name="Custom Game")
    m = parse_match(raw)
    rep = trf.fake_replay(m)
    rep["match_id"] = UID
    replayfile._write(replayfile.data_file(Path(store.data_dir) / "replays", UID), rep)
    calls = []

    def fake(self, region, match_id, use_cache=True):
        calls.append((region, match_id))
        if not found:
            raise HenrikError("HenrikDev 404 Not Found")
        return raw
    monkeypatch.setattr(HenrikClient, "match", fake)
    return store, m, calls


def test_custom_replay_opens_after_loading_the_match(app, synthetic, monkeypatch):  # noqa: F811
    store, m, calls = _custom(app, synthetic, monkeypatch)
    c = setup_admin(app)
    pid = add_profile(c)
    assert not wr.match_file(store, UID).is_file()
    page = c.get(f"/profiles/{pid}/replay/{UID}")
    assert page.status_code == 200 and "Utility check" in page.data.decode()
    assert calls and calls[0][1] == UID and wr.match_file(store, UID).is_file()
    d = c.get(f"/api/replay/{UID}/round/0?pid={pid}").get_json()
    assert len(d["paths"]) == 10
    files = c.get(f"/profiles/{pid}/replays").data.decode()
    assert "Custom games and other replays" in files and f"/profiles/{pid}/replay/{UID}" in files
    other = files.split("Custom games and other replays")[1]
    assert m.map_name in other and "Watch in 3D" in other and "Coach this match" in other    # adv1ce played in it


def test_brief_of_a_cached_match(app, synthetic, monkeypatch):  # noqa: F811
    store, m, _ = _custom(app, synthetic, monkeypatch)
    assert wr.fetch_match(store, UID)
    b = wr.match_brief(store, UID, "adv1ce#EUW")
    me = m.find_player("adv1ce")
    assert b["map"] == m.map_name and b["started_at"]
    if me is not None and f"{me.name}#{me.tag}".lower() == "adv1ce#euw":
        assert b["played"] and b["agent"] and "–" in b["score"]
    assert wr.match_brief(store, UID, "nobody#000")["played"] is False
    assert wr.match_brief(store, "00000000-0000-4000-8000-000000000000") is None


def test_unknown_match_is_not_asked_again_and_again(app, synthetic, monkeypatch):  # noqa: F811
    store, _m, calls = _custom(app, synthetic, monkeypatch, found=False)
    c = setup_admin(app)
    pid = add_profile(c)
    assert c.get(f"/profiles/{pid}/replay/{UID}").status_code == 404
    n = len(calls)
    assert n >= 1 and UID in json.loads(wr._misses_file(store).read_text())
    assert c.get(f"/profiles/{pid}/replay/{UID}").status_code == 404
    app.extensions["nexus"]["replays_details"]()
    assert len(calls) == n                                         # waits MATCH_RETRY_S before trying again
    page = c.get(f"/profiles/{pid}/replays").data.decode()
    assert "Match details are still loading" in page


def test_background_tick_loads_missing_details(app, synthetic, monkeypatch):  # noqa: F811
    store, _m, calls = _custom(app, synthetic, monkeypatch)
    app.extensions["nexus"]["replays_details"]()
    assert calls and wr.match_file(store, UID).is_file()
    app.extensions["nexus"]["replays_details"]()
    assert len(calls) == 1                                         # cached: not asked again


def test_regions_profile_first(app):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    c = setup_admin(app)
    add_profile(c)
    r = wr.regions(store, "na")
    assert r[0] == "na" and len(r) == len(set(r))


def test_texts_mention_custom_games():
    root = Path(__file__).parent.parent
    de = json.loads((root / "nexus/i18n/de.json").read_text())
    for k in ("Custom games and other replays", "Match details are still loading", "Another match",
              "They don't count in your stats."):
        assert k in de and "ß" not in de[k]
    assert "Custom" in (root / "nexus/replayfile.py").read_text().split('"""')[1].split("(not")[0]
