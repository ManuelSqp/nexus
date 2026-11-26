"""4.84: did the prep work? The boards drafted against a scouted team checked against the rounds you tagged with them
(stats/prepresult.py): in the review evening against that team, on the strat book's cards and on their scouting page."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import MATCH_ID, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.parse import parse_match  # noqa: E402
from nexus.stats import evening as ev_stats  # noqa: E402
from nexus.stats import prepresult as pr  # noqa: E402

ROOT = Path(__file__).parent.parent
PREP = {"team_id": "t-1", "team": "Rivals", "tag": "RV"}


def test_result():
    assert pr.against(PREP, "t-1") and pr.against(PREP, "", "Rivals#RV") and pr.against(PREP, "", "rivals")
    assert not pr.against(PREP, "t-2", "Others#OT") and not pr.against(PREP, "", "Rivals#XX") and not pr.against(PREP, "", "their team")
    assert not pr.against("x", "t-1")
    rate = {"rounds": [{"opponent": "Rivals#RV", "won": True}, {"opponent": "Rivals#RV", "won": False},
                       {"opponent": "Others#OT", "won": True}]}
    rec = pr.record(rate, PREP)
    assert rec == {"vs": {"ran": 2, "won": 1}, "other": {"ran": 1, "won": 1}}
    assert pr.record_text(rec, "Rivals") == "Against Rivals: won 1 of 2 rounds · 1 of 1 against others"
    assert pr.record_text(pr.record(None, PREP), "Rivals") == ""
    preps = [{"id": 5, "name": "vs RV: their hit", "side": "defense", "map": "Ascent", **PREP},
             {"id": 6, "name": "vs RV: their setup", "side": "attack", "map": "Ascent", **PREP},
             {"id": 7, "name": "vs RV on Bind", "side": "attack", "map": "Bind", **PREP},
             {"id": 8, "name": "vs OT", "side": "attack", "map": "Ascent", "team_id": "t-2", "team": "Others"}]
    ev = {"map": "Ascent", "opponent": "Rivals#RV", "rounds": [{"n": 1, "won": True}, {"n": 2, "won": False}, {"n": 14, "won": True}],
          "strats": {"14": 5, "2": 5, "1": 8, "x": 5}}
    res = pr.evening(ev, preps, "")
    assert [(x["id"], x["ran"], x["won"], [r["n"] for r in x["rounds"]]) for x in res] == [(5, 2, 1, [2, 14]), (6, 0, 0, [])]
    assert pr.lines(res) == ["vs RV: their hit (defense): ran in 2 rounds (R2, R14), won 1",
                             "vs RV: their setup (attack): not tagged in any round. If you ran it, pick it in those rounds' strat pick"]
    text = ev_stats.discord_text({"map": "Ascent", "score": "13–9", "opponent": "Rivals#RV"},
                                 {"marked_rounds": 0, "rounds": 22, "counts": {"fault": 0, "good": 0, "talk": 0}, "themes": [],
                                  "talk": [], "plan": [], "prep": pr.lines(res)}, "Squad")
    assert "**Our prep against them**\n• vs RV: their hit (defense)" in text


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
    other = store.create_strat(tid, uid, m.map_name, "attack", "A split", {"steps": [{"items": []}]})
    prep = store.create_strat(tid, uid, m.map_name, "attack", "vs RV: their setup",
                              {"steps": [{"items": []}], "prep": {**PREP, "made": "2026-11-20"}})
    ev = c.post(f"/teams/{tid}/review-evening", data={"match_id": MATCH_ID}).headers["Location"].rstrip("/").split("/")[-1]
    path = app.extensions["nexus"]["stats"].team_dir(tid) / "evenings" / f"{ev}.json"
    d = json.loads(path.read_text())
    assert d["opponent_id"] == ""                                            # no Premier review of the match here
    d["opponent"] = "Rivals#RV"
    path.write_text(json.dumps(d))
    page = c.get(f"/teams/{tid}/review-evening/{ev}").data.decode()
    boot = json.loads(page.split('id="ev-boot">')[1].split("</script>")[0])
    assert [(x["id"], x["prep"]) for x in boot["strat_list"]] == [(prep, True), (other, False)]   # the prep first
    assert "Your prep against them" in page and "vs RV: their setup (attack): not tagged in any round" in page
    attack = [r for r in boot["rounds"] if r["side"] == "attack"][:2]
    for r in attack:
        c.post(f"/api/teams/{tid}/review-evening/{ev}", json={"action": "strat", "round": r["n"], "strat": prep})
    won = sum(r["won"] for r in attack)
    summary = c.get(f"/teams/{tid}/review-evening/{ev}/summary").data.decode()
    assert f"vs RV: their setup (attack): ran in 2 rounds (R{attack[0]['n']}, R{attack[1]['n']}), won {won}" in summary
    book = c.get(f"/teams/{tid}/strats").data.decode()
    assert "Prep against <b>Rivals</b> · won " + str(won) + " of 2 rounds" in book
    assert "★ " in (ROOT / "nexus/web/static/evening.js").read_text()


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your prep against them", "Prep against", "not tagged in a review evening yet",
              "not tagged in a review evening against them yet", "against them"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 84)
    assert "## 4.84" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
