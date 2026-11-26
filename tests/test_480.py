"""4.80: the Sunday team report on Discord: strats, economy, drills and what's next in one post
(stats/teamreport.py, web/practice.py)."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import MATCH_ID, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus import discord  # noqa: E402
from nexus.parse import parse_match  # noqa: E402
from nexus.stats import teamreport as trp  # noqa: E402

ROOT = Path(__file__).parent.parent
STRATS = [{"id": 1, "name": "A split", "map": "Ascent", "side": "attack"}, {"id": 2, "name": "B rush", "map": "Ascent", "side": "attack"},
          {"id": 3, "name": "Retake A", "map": "Bind", "side": "defense"}]


def rate(ran, won, few=False, util_n=0, util_ok=0):
    return {"ran": ran, "won": won, "pct": round(100 * won / ran), "few": few, "util_n": util_n, "util_ok": util_ok}


def test_sections():
    s = trp.strat_section([{"strat": 1, "won": True}, {"strat": 1, "won": False}, {"strat": 2, "won": True}],
                          {1: rate(8, 6), 2: rate(6, 2, util_n=5, util_ok=1), 3: rate(2, 0, few=True)}, STRATS)
    assert s == ["3 rounds tagged this week, 2 won: A split 1/2, B rush 1/1",
                 "Best so far: **A split** (Ascent attack), 75 % of 8 rounds",
                 "Struggling: **B rush** (Ascent attack), 33 % of 6 rounds, utility as drawn in 1 of 5"]
    assert trp.strat_section([], {}, STRATS) == []
    econ = {"rounds": {"4": {"flags": ["broken_force"], "off": [], "won": False}, "9": {"flags": [], "off": ["x"], "won": True},
                       "12": {"flags": ["broken_force"], "off": [], "won": True}}}
    e = trp.econ_section([{"label": "Ascent vs RV", "econ": econ}])
    assert e == ["2× a lost force that broke the next round (1 lost): Ascent vs RV R4; Ascent vs RV R12",
                 "1× someone off the team's buy (0 lost): Ascent vs RV R9"]
    assert trp.econ_section([{"label": "x", "econ": {"rounds": {"1": {"flags": [], "off": [], "won": True}}}}]) == \
        ["Every buy fit the money in 1 match."] and trp.econ_section([]) == []
    d = trp.drills_section({"players": [{"name": "Obi", "sessions": 2, "goals_reached": [1]}, {"name": "Ka", "sessions": 3}],
                            "idle": ["Luca"]})
    assert d == ["Ka 3×, Obi 2×", "1 drill goal reached", "No drills: Luca"]
    assert trp.drills_section({"players": []}) == ["Nobody drilled this week."]
    n = trp.next_section({"day": "Thu 03.12. 20:00", "map": "Ascent", "prep": ["vs RV: their hit"]})
    assert n == ["Next match: **Thu 03.12. 20:00** on **Ascent**", "Boards against opponents: vs RV: their hit"]
    assert "Draft a plan in the strat book" in trp.next_section({"map": "Ascent"})[1]
    emb = trp.embeds("Squad", "2026-W48", s, e, d, n)[0]
    assert emb["title"] == "Squad: the week" and [f["name"] for f in emb["fields"]] == ["📒 Strats", "💰 Economy", "🎯 Drills", "🗓️ The week ahead"]
    assert trp.embeds("S", "w", [], [], [], [])[0]["fields"][0]["value"].startswith("Nothing to report")


def test_post_and_tick(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    m = parse_match(json.loads((store.data_dir / "cache" / "matches" / f"{MATCH_ID}.json").read_text()))
    side = m.teams[0]
    ours = [p for p in m.players.values() if p.team == side][:2]
    pids = [add_profile(c, name=p.name, tag="#" + p.tag) for p in ours]
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "puuid": p.puuid, **({"user_id": uid} if i == 0 else {})}
                                    for i, (pid, p) in enumerate(zip(pids, ours))], maps=[m.map_name],
                      discord={"focus_url": "https://discord.com/api/webhooks/1/abc"})
    sid_ = store.create_strat(tid, uid, m.map_name, "attack", "A split", {"steps": [{"items": []}]})
    ev = c.post(f"/teams/{tid}/review-evening", data={"match_id": MATCH_ID}).headers["Location"].rstrip("/").split("/")[-1]
    boot = json.loads(c.get(f"/teams/{tid}/review-evening/{ev}").data.decode().split('id="ev-boot">')[1].split("</script>")[0])
    att = [r for r in boot["rounds"] if r["side"] == "attack"][:2]
    for r in att:
        c.post(f"/api/teams/{tid}/review-evening/{ev}", json={"action": "strat", "round": r["n"], "strat": sid_})
    rep = app.extensions["nexus"]["team_report"](store.team(tid))
    assert rep["strats"][0].startswith(f"2 rounds tagged this week, {sum(r['won'] for r in att)} won: A split")
    assert rep["econ"] and rep["drills"] and "🏆 Match" in "\n".join(rep["next"])      # 4.82: the week ahead
    sent = []
    monkeypatch.setattr(discord, "post", lambda url, content="", embeds=None, **kw: sent.append((url, embeds)))
    tick = next(f for f in app.extensions["nexus"]["ticks"] if f.__name__ == "tick_report")
    sunday = datetime.datetime(2026, 11, 29, 20, 5)
    assert tick(sunday) == []                                                       # off by default
    c.post(f"/teams/{tid}/practice", data={"days": ["1"], "time": "19:00", "minutes": "90", "team_report": "1"})
    assert tick(datetime.datetime(2026, 11, 29, 19, 0)) == [] and tick(datetime.datetime(2026, 11, 28, 21, 0)) == []
    assert tick(sunday) == [tid] and tick(sunday) == []                             # once a week
    assert sent[0][0].endswith("/abc") and sent[0][1][0]["title"] == "Squad: the week"
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert "Post the team report" in page and 'name="team_report" value="1" checked' in page
    assert c.post(f"/teams/{tid}/practice", data={"action": "post_report"}).status_code == 302 and len(sent) == 2


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Sunday team report on Discord", "Post the team report", "Posted the team report to Discord."):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 80)
    assert "## 4.80" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
