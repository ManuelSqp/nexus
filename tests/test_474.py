"""4.74: the scrim review: in a review evening the comp you played against your comp for the map, where each kill
was, each player's utility per round, and per round the strat you ran against the utility used; a scrim in the log
links to its match."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import MATCH_ID, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.parse import parse_match  # noqa: E402
from nexus.stats import evening as ev  # noqa: E402

ROOT = Path(__file__).parent.parent


def test_plan_checks():
    assert ev.util_of({"grenade": 1, "ability_1": 2, "ultimate": 0}) == {"C": 1, "Q": 2, "E": 0, "X": 0}
    c = ev.comp_check(["Omen", "Jett", "Sova", "Killjoy", "Skye"], ["Omen", "Jett", "Fade", "Killjoy", "Skye"])
    assert c["missing"] == ["Fade"] and c["extra"] == ["Sova"] and not c["same"]
    assert ev.comp_check(["Omen", "Jett"], ["Jett", "Omen", ""])["same"] and ev.comp_check(["Omen"], []) is None
    board = {"steps": [
        {"items": [{"t": "ab", "a": "Omen", "s": "Ability2", "id": "1"}, {"t": "ab", "a": "Omen", "s": "Ability2", "id": "2"},
                   {"t": "ab", "a": "Sova", "s": "Ability1", "id": "3"}, {"t": "agent", "a": "Jett"},
                   {"t": "ab", "a": "Viper", "s": "Grenade", "c": "them"}]},              # theirs: not your plan
        {"items": [{"t": "ab", "a": "Omen", "s": "Ability2", "id": "4", "k": "1"},      # the same smoke, one step on
                   {"t": "ab", "a": "Jett", "s": "Ultimate", "id": "5"}]}]}
    plan = ev.strat_util(board)
    assert plan == [{"agent": "Jett", "key": "X", "n": 1}, {"agent": "Omen", "key": "E", "n": 2},
                    {"agent": "Sova", "key": "Q", "n": 1}]
    rnd = {"players": {"Obi": {"agent": "Omen"}, "Ka": {"agent": "Sova"}}, "util": {"Obi": {"E": 2}, "Ka": {"Q": 0}}}
    got = {x["agent"]: (x["used"], x["ok"]) for x in ev.util_check(plan, rnd)}
    assert got == {"Jett": (None, False), "Omen": (2, True), "Sova": (0, False)}
    assert ev.util_check(plan, {"players": {}, "util": None}) is None


def test_round_facts_where_and_util(synthetic):  # noqa: F811 (fixture)
    m = parse_match(json.loads(Path(synthetic["match"]).read_text()))
    side = m.teams[0]
    rounds = ev.round_facts(m, side, lambda x, y: "A Main" if x > 0 else "B Long")
    ks = [k for r in rounds for k in r["kills"]]
    assert ks and all(k.get("vw") in ("A Main", "B Long") for k in ks if k["v"] != "?")
    assert any("kw" in k for k in ks)
    assert all(set(u) == {"C", "Q", "E", "X"} for r in rounds for u in (r["util"] or {}).values())
    assert rounds[0]["util"] is not None and set(rounds[0]["util"]) == set(rounds[0]["players"])
    plain = ev.round_facts(m, side)                                    # no map: no callouts
    assert not any("kw" in k or "vw" in k for r in plain for k in r["kills"])


def test_evening_and_scrims(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    raw = json.loads((store.data_dir / "cache" / "matches" / f"{MATCH_ID}.json").read_text())
    m = parse_match(raw)
    side = m.teams[0]
    ours = [p for p in m.players.values() if p.team == side][:2]
    pids = [add_profile(c, name=p.name, tag="#" + p.tag) for p in ours]
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "puuid": p.puuid, **({"user_id": uid} if i == 0 else {})}
                                    for i, (pid, p) in enumerate(zip(pids, ours))], maps=[m.map_name])
    played = [p.agent for p in m.players_on(side)]
    plan = [{"pid": None, "agent": a} for a in played[:4] + ["Neon"]]
    store.create_draft(tid, uid, m.map_name, "Our comp", {"slots": plan, "status": "main"})
    s_att = store.create_strat(tid, uid, m.map_name, "attack", "A split",
                               {"steps": [{"items": [{"t": "ab", "a": played[0], "s": "Ability1", "id": "a"}]}]})
    store.create_strat(tid, uid, "Elsewhere", "attack", "Not here")
    r = c.post(f"/teams/{tid}/review-evening", data={"match_id": MATCH_ID})
    sid = r.headers["Location"].rstrip("/").split("/")[-1]
    page = c.get(f"/teams/{tid}/review-evening/{sid}").data.decode()
    boot = json.loads(page.split('id="ev-boot">')[1].split("</script>")[0])
    comp = boot["comp"]
    assert comp["name"] == "Our comp" and comp["missing"] == ["Neon"] and comp["extra"] == played[4:]
    assert [x["name"] for x in boot["strat_list"]] == ["A split"]
    assert boot["strat_list"][0]["util"] == [{"agent": played[0], "key": "Q", "n": 1}]
    assert 'id="stratc"' in page and 'id="comp"' in page
    assert boot["rounds"][0]["util"] is not None
    api = f"/api/teams/{tid}/review-evening/{sid}"
    st = c.post(api, json={"action": "strat", "round": 1, "strat": s_att}).get_json()
    assert st["strats"] == {"1": s_att}
    assert c.post(api, json={"action": "strat", "round": 1, "strat": 99999}).status_code == 400
    assert c.post(api, json={"action": "strat", "round": 99, "strat": s_att}).status_code == 400
    assert c.post(api, json={"action": "strat", "round": 1, "strat": ""}).get_json()["strats"] == {}
    js = (ROOT / "nexus/web/static/evening.js").read_text()
    assert "function renderStrat()" in js and "function renderComp()" in js and "at(k.kw)" in js
    # the strat's link: only a whole number from the page goes into it (CodeQL: no text from the page as a URL)
    assert "link.setAttribute('href', '../strats/' + sid)" in js and "strat_url" not in js and "strat_url" not in boot
    assert f"/teams/{tid}/review-evening/{sid}".rsplit("/", 2)[0] + f"/strats/{s_att}" == f"/teams/{tid}/strats/{s_att}"
    # a scrim in the log on the same day and map: "Review it round by round"
    day = (m.started_at or "")[:10]
    c.post(f"/teams/{tid}/scrims", data={"opponent": "Rivals", "map": m.map_name, "us": "7", "them": "5", "date": day})
    page = c.get(f"/teams/{tid}/scrims").data.decode()
    assert "Rivals" in page and "Review it round by round" not in page        # the match isn't in their games yet
    sr = app.extensions["nexus"]["stats"]
    for pid in pids:                                           # their games list the match
        gs = sr.games(pid)
        d = gs.load()
        d["games"][MATCH_ID] = {"match_id": MATCH_ID, "map": m.map_name, "started_at": m.started_at, "score": "7-5"}
        gs.save(d)
    page = c.get(f"/teams/{tid}/scrims").data.decode()
    assert "Review it round by round" in page and f"/review-evening?match={MATCH_ID}" in page


def test_scrim_match_link(app):  # noqa: F811 (fixture)
    from nexus.web import scrims as wscrims
    src = Path(wscrims.__file__).read_text()
    assert "def match_of(t, scrims" in src and "matches=match_of(t, shown)" in src
    tpl = (ROOT / "nexus/web/templates/team_scrims.html").read_text()
    assert "url_for('team_evening', tid=t.id, match=matches[s.id])" in tpl and "Review it round by round" in tpl


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Strat this round", "We ran", "open it", "Review it round by round", "Planned", "Used",
              "Pick the strat you ran: its utility against what was used.", "This strat has no abilities drawn."):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 74)
    assert "## 4.74" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
