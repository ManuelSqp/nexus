"""4.44: replay in 3D with the team's comments, the utility check, and the PC app sending every replay."""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_replayfile as trf  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus import replayfile  # noqa: E402
from nexus.parse import parse_match  # noqa: E402
from nexus.stats import replayview as rv  # noqa: E402

UID = "5f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5"
SLOTS = {3: "grenade", 1: "ability1", 2: "ability2", 4: "ultimate"}      # how this fake replay numbers the keys


def _replay(app, synthetic, fit=True):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    raw = json.loads(Path(synthetic["match"]).read_text())
    raw["data"]["metadata"]["match_id"] = UID
    (Path(store.data_dir) / "cache" / "matches" / f"{UID}.json").write_text(json.dumps(raw))
    m = parse_match(raw)
    rep = trf.fake_replay(m)
    rnd, casts = random.Random(1), []
    for p, pl in m.players.items():
        for slot, key in SLOTS.items():
            n = int(pl.ability_casts.get(key, pl.ability_casts.get(key.replace("ability", "ability_"), 0)) or 0)
            if not fit:
                n = rnd.randrange(0, 9)
            for _ in range(n):
                r = rnd.randrange(len(m.rounds))
                casts.append([5000 + r * trf.GAP_MS + trf.BUY_MS + rnd.randrange(2000, 40000), p, slot])
    rep["casts"] = sorted(casts)
    x, y = rep["pos"][next(iter(rep["pos"]))][40][1:3]
    rep["effects"] = [[5000 + trf.BUY_MS + 15000, 5000 + trf.BUY_MS + 30000, "wraith", "E", "smoke", "zone", x, y]]
    rep["match_id"] = UID
    replayfile._write(replayfile.data_file(Path(store.data_dir) / "replays", UID), rep)
    return m


def test_replay_page_round_and_utility(app, synthetic):  # noqa: F811
    m = _replay(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/replay/{UID}").data.decode()
    assert "Utility check" in page and "replay.js" in page and "map3d.css" in page and 'id="rv-rounds"' in page
    assert page.count('data-r="') == len(m.rounds)
    d = c.get(f"/api/replay/{UID}/round/0?pid={pid}").get_json()
    assert len(d["paths"]) == 10 and d["kills"] and d["end"] > 0 and d["util"][0]["type"] == "smoke"
    t, x, y, z, yaw = d["paths"]["0"][5]
    assert t >= -1 and isinstance(yaw, float) and -3.15 <= yaw <= 3.15
    assert {k for _t, _p, k in d["casts"]} <= {"C", "Q", "E", "X"}
    assert c.get(f"/api/replay/{UID}/round/99?pid={pid}").status_code == 404
    ctx = app.extensions["nexus"]["replay_ctx"](UID)
    assert ctx.slot_keys() == {3: "C", 1: "Q", 2: "E", 4: "X"}
    u = ctx.utility_check()
    one = u["players"][0]
    pl = m.players[ctx.order[0]]
    assert u["keys_known"] and one["per_key"]["Q"] == int(pl.ability_casts.get("ability1", pl.ability_casts.get("ability_1", 0)))
    assert 0 <= one["dry_deaths"] <= one["deaths"] and one["rounds"] == len(m.rounds)
    me_row = page.split('class="ours"')[1].split("</tr>")[0]
    assert "adv1ce" in me_row                                               # your team first in the table
    assert f"/profiles/{pid}/replay/{UID}" in c.get(f"/profiles/{pid}/coach/{UID}").data.decode()


def test_slot_numbers_not_guessed_when_they_dont_fit(app, synthetic):  # noqa: F811
    _replay(app, synthetic, fit=False)
    c = setup_admin(app)
    pid = add_profile(c)
    ctx = app.extensions["nexus"]["replay_ctx"](UID)
    assert ctx.slot_keys() == {}
    u = ctx.utility_check()
    assert not u["keys_known"] and "per_key_match" in u["players"][0]
    page = c.get(f"/profiles/{pid}/replay/{UID}").data.decode()
    assert "didn't allow working it out" in page
    d = c.get(f"/api/replay/{UID}/round/0?pid={pid}").get_json()
    assert all(str(k).startswith("#") for _t, _p, k in d["casts"])


def test_team_comments(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c)
    api = f"/api/replay/{UID}/comments?pid={pid}"
    r = c.post(api, json={"round": 2, "t": 34.26, "text": "  Rotate   earlier  "})
    item = r.get_json()["comment"]
    assert r.status_code == 200 and item["text"] == "Rotate earlier" and item["t"] == 34.3 and item["mine"]
    assert c.post(api, json={"round": 2, "t": 1, "text": " "}).status_code == 400
    assert c.post(api, json={"round": 99, "t": 1, "text": "x"}).status_code == 400
    owner = store.user_by_name("manuel").id
    tid = store.create_team(owner, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "user_id": owner}])
    mate = make_user(app, c, "mate")
    store.add_team_access(tid, store.user_by_name("mate").id)
    seen = mate.get(api).get_json()["comments"]
    assert len(seen) == 1 and seen[0]["user"] == "manuel" and not seen[0]["mine"] and "uid" not in seen[0]
    assert mate.post(api, json={"round": 2, "t": 40, "text": "agreed"}).status_code == 200
    assert mate.delete(f"/api/replay/{UID}/comments/{item['id']}?pid={pid}").status_code == 403
    assert c.delete(f"/api/replay/{UID}/comments/{item['id']}?pid={pid}").status_code == 200
    assert [x["text"] for x in c.get(api).get_json()["comments"]] == ["agreed"]
    stranger = make_user(app, c, "stranger")
    assert stranger.get(f"/profiles/{pid}/replay/{UID}").status_code == 404
    assert stranger.get(api).status_code == 404
    assert c.get(f"/profiles/{pid}/replay/not-a-match").status_code == 404


def test_app_upload_of_a_new_patch_is_kept(app, monkeypatch):  # noqa: F811
    """The PC app's upload of a replay vrfkit can't read yet: 202 "pending" (kept), not an error."""
    def ingest(vrf, rdir, work, vrfkit, keep_vrf=True):
        raise replayfile.UnsupportedBuild("x", "++Ares-Core+release-13.11")
    monkeypatch.setattr(replayfile, "ingest", ingest)
    from test_web import ADMIN_PW
    setup_admin(app)
    token = app.test_client().post("/api/companion/login", json={"username": "manuel", "password": ADMIN_PW}).get_json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    c = app.test_client()
    body = b"VRF" * 40
    upid = c.post("/api/companion/uploads", json={"name": "a.vrf", "size": len(body)}, headers=H).get_json()["id"]
    c.put(f"/api/companion/uploads/{upid}?offset=0", data=body, headers=H)
    r = c.post("/api/companion/replays", json={"upload_id": upid}, headers=H)
    assert r.status_code == 202 and r.get_json()["pending"] and r.get_json()["patch"] == "13.11"


def test_slot_keys_unit():
    class P:
        def __init__(self, team, ac):
            self.team, self.ability_casts, self.name, self.tag, self.agent = team, ac, "n", "t", "a"

    class M:
        players = {"a": P("Red", {"grenade": 2, "ability1": 0, "ability2": 1, "ultimate": 0}),
                   "b": P("Blue", {"grenade": 0, "ability1": 3, "ability2": 0, "ultimate": 1})}
    casts = [[1, "a", 7], [2, "a", 7], [3, "a", 9], [4, "b", 5], [5, "b", 5], [6, "b", 5], [7, "b", 8]]
    assert rv.slot_keys(casts, M) == {7: "C", 9: "E", 5: "Q", 8: "X"}
    assert rv.slot_keys([], M) == {}
