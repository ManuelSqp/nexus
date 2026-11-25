"""4.75: strat win rates: the rounds tagged with a strat in review evenings count for that strat (stratrates.py),
shown on the strat book, the strat's page and the evening's strat pick."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import MATCH_ID, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.parse import parse_match  # noqa: E402
from nexus.stats import stratrates as sr8  # noqa: E402

ROOT = Path(__file__).parent.parent


def rnd(n, won, util=None, agent="Omen"):
    return {"n": n, "won": won, "score": f"{n}-0", "players": {"Obi": {"agent": agent}}, "util": util}


def test_rates():
    plan = {1: [{"agent": "Omen", "key": "E", "n": 2}], 2: [], 3: [{"agent": "Sova", "key": "Q", "n": 1}]}
    evs = [{"id": "a", "started_at": "2026-11-20T18:00", "opponent": "Rivals",
            "rounds": [rnd(1, True, {"Obi": {"E": 2}}), rnd(2, False, {"Obi": {"E": 1}}), rnd(3, True, None), rnd(4, True)],
            "strats": {"1": 1, "2": 1, "3": 1, "4": 2, "9": 1, "x": 1}},
           {"id": "b", "started_at": "2026-11-22T18:00", "opponent": "Others",
            "rounds": [rnd(1, False, {"Obi": {"E": 0}}), rnd(2, True, {"Obi": {}})], "strats": {"1": 1, "2": 99}}]
    r = sr8.rates(evs, plan)
    a = r[1]
    assert (a["ran"], a["won"], a["pct"], a["few"]) == (4, 2, 50, True)                 # round 9 doesn't exist
    assert (a["util_n"], a["util_ok"], a["won_ok"], a["won_miss"]) == (3, 1, 1, 0)      # no casts in round 3
    assert a["last"] == "2026-11-22T18:00" and [x["ev"] for x in a["rounds"]][0] == "b"
    assert r[2]["ran"] == 1 and r[2]["util_n"] == 0 and 99 not in r and 3 not in r      # 99: not a strat (deleted)
    assert sr8.text(a) == "Ran 4 rounds · won 2 (50 %)" and sr8.text(r[2]) == "Ran 1 round · won 1 (100 %)"
    assert sr8.util_text(a) == "Utility as drawn in 1 of 3 · won 1 of those, 0 of the other 2"
    assert sr8.util_text(r[2]) == "" and sr8.text(None) == ""
    many = sr8.rates([{"id": "c", "started_at": "x", "rounds": [rnd(i, i % 3 != 0) for i in range(1, 8)],
                       "strats": {str(i): 2 for i in range(1, 8)}}], plan)
    best = sr8.best([{"id": 1, "name": "A", "side": "attack"}, {"id": 2, "name": "B", "side": "attack"}], {**r, **many})
    assert best == {"attack": {"id": 2, "name": "B", "pct": 71, "ran": 7}}             # A has too few rounds


def test_pages(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    m = parse_match(json.loads((store.data_dir / "cache" / "matches" / f"{MATCH_ID}.json").read_text()))
    side = m.teams[0]
    ours = [p for p in m.players.values() if p.team == side][:2]
    pids = [add_profile(c, name=p.name, tag="#" + p.tag) for p in ours]
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "puuid": p.puuid, **({"user_id": uid} if i == 0 else {})}
                                    for i, (pid, p) in enumerate(zip(pids, ours))], maps=[m.map_name])
    played = [p.agent for p in m.players_on(side)]
    sid_ = store.create_strat(tid, uid, m.map_name, "attack", "A split",
                              {"steps": [{"items": [{"t": "ab", "a": played[0], "s": "Ability1", "id": "a"}]}]})
    page = c.get(f"/teams/{tid}/strats/{sid_}").data.decode()
    assert "Tag rounds with this strat in a" in page
    ev = c.post(f"/teams/{tid}/review-evening", data={"match_id": MATCH_ID}).headers["Location"].rstrip("/").split("/")[-1]
    boot = json.loads(c.get(f"/teams/{tid}/review-evening/{ev}").data.decode().split('id="ev-boot">')[1].split("</script>")[0])
    attack = [r for r in boot["rounds"] if r["side"] == "attack"][:2]
    assert boot["strat_list"][0]["rate"] is None
    api = f"/api/teams/{tid}/review-evening/{ev}"
    for r in attack:
        c.post(api, json={"action": "strat", "round": r["n"], "strat": sid_})
    won = sum(r["won"] for r in attack)
    boot = json.loads(c.get(f"/teams/{tid}/review-evening/{ev}").data.decode().split('id="ev-boot">')[1].split("</script>")[0])
    assert boot["strat_list"][0]["rate"] == {"ran": 2, "pct": round(100 * won / 2)}
    book = c.get(f"/teams/{tid}/strats").data.decode()
    assert f"Ran 2 rounds · won {won} ({round(100 * won / 2)} %)" in book and "few rounds yet" in book
    page = c.get(f"/teams/{tid}/strats/{sid_}").data.decode()
    assert f"/review-evening/{ev}#r{attack[0]['n']}" in page and 'class="srec small"' in page
    js = (ROOT / "nexus/web/static/evening.js").read_text()
    assert "x.rate ? ` · ${esc(x.rate.pct)} % of ${esc(x.rate.ran)}` : ''" in js


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("few rounds yet", "Ran {n} rounds · won {w} ({p} %)", "best on {side}:",
              "Utility as drawn in {a} of {b}", "Tag rounds with this strat in a", "review evening", "to see how it does."):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 75)
    assert "## 4.75" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
