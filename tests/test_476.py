"""4.76: the economy review of one match: money against the buys, round by round, and the rounds where the buy
didn't fit (stats/econreview.py), in the review evening and the Premier match review."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent))
from test_web import MATCH_ID, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.parse import parse_match  # noqa: E402
from nexus.stats import econreview as er  # noqa: E402

ROOT = Path(__file__).parent.parent


def match(rounds):
    """rounds: [(won, [(loadout, remaining) x5 for us])]; them always a full buy."""
    players = {f"u{i}": NS(puuid=f"u{i}", name=f"Us{i}", team="Blue") for i in range(5)}
    players.update({f"t{i}": NS(puuid=f"t{i}", name=f"Them{i}", team="Red") for i in range(5)})
    rs = []
    for n, (won, ours) in enumerate(rounds, 1):
        st = {f"u{i}": NS(puuid=f"u{i}", team="Blue", loadout_value=lo, remaining=rem) for i, (lo, rem) in enumerate(ours)}
        st.update({f"t{i}": NS(puuid=f"t{i}", team="Red", loadout_value=4500, remaining=500) for i in range(5)})
        rs.append(NS(number=n, winning_team="Blue" if won else "Red", stats=st))
    return NS(players=players, rounds=rs, other_team=lambda s: "Red" if s == "Blue" else "Blue")


FULL = [(4500, 1000)] * 5
ECO = [(800, 2500)] * 5
FORCE = [(2800, 200)] * 5
RICH_ECO = [(900, 4500)] * 5


def test_review():
    rounds = [(True, [(800, 0)] * 5),                                  # 1 pistol: never flagged
              (True, FULL),                                            # 2 fine
              (True, [(4500, 0)] * 2 + [(500, 1200)] * 3),            # 3 half buy
              (False, FORCE),                                          # 4 a lost force…
              (False, ECO),                                            # 5 …and no full buy after it
              (True, RICH_ECO),                                        # 6 an eco with money for a full buy
              (False, FULL),                                           # 7 a lost full buy…
              (True, [(3000, 500)] * 5),                               # 8 …and only a force after it
              (True, [(4900, 800)] * 4 + [(900, 400)]),               # 9 one saved while the team bought
              (True, [(800, 2000)] * 4 + [(4200, 100)])]              # 10 one bought while the team saved
    rv = er.review(match(rounds), "Blue")
    R = rv["rounds"]
    assert set(R) == {str(n) for n in range(1, 11)}
    assert R["1"]["kind"] == "pistol" and R["1"]["text"] == [] and R["2"]["text"] == []
    assert R["2"]["money"] == 5500 and R["2"]["bought"] == 4500
    assert R["3"]["flags"] == ["half_buy"] and R["3"]["off"] == []        # a half buy names nobody on its own
    assert R["4"]["flags"] == ["broken_force"] and R["5"]["flags"] == []
    assert R["6"]["flags"] == ["could_buy"] and R["7"]["flags"] == ["no_rebuy"]
    assert R["9"]["off"] == ["Us4 saved while the team bought"] and R["10"]["off"] == ["Us4 bought while the team saved"]
    assert rv["summary"]["flagged"] == [3, 4, 6, 7, 9, 10] and rv["summary"]["lost"] == [4, 7]
    assert rv["summary"]["counts"]["broken_force"] == {"rounds": 1, "lost": 1}
    ls = er.lines(json.loads(json.dumps(rv)))                              # as it comes back from the evening's file
    assert ls[0] == "1× half the team bought, half saved (round 3; 0 lost)"
    assert "2× someone off the team's buy (rounds 9, 10; 0 lost)" in ls
    assert er.lines(None) == [] and er.review(NS(players={}, rounds=[], other_team=lambda s: "Red"), "Blue") is None
    # the round after the half's switch starts over: no "broke the next round" into round 13
    r12 = [(True, FULL)] * 11 + [(False, FORCE), (True, [(800, 0)] * 5)]
    assert er.review(match(r12), "Blue")["rounds"]["12"]["flags"] == []


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
    ev = c.post(f"/teams/{tid}/review-evening", data={"match_id": MATCH_ID}).headers["Location"].rstrip("/").split("/")[-1]
    page = c.get(f"/teams/{tid}/review-evening/{ev}").data.decode()
    boot = json.loads(page.split('id="ev-boot">')[1].split("</script>")[0])
    want = er.review(m, side)
    assert boot["econ"] == json.loads(json.dumps(want))
    if er.lines(want):
        assert "<h3>Economy</h3>" in page
    # an evening from before 4.76: worked out from the match
    sr = app.extensions["nexus"]["stats"]
    f = sr.team_dir(tid) / "evenings" / f"{ev}.json"
    d = json.loads(f.read_text())
    d.pop("econ")
    f.write_text(json.dumps(d))
    page = c.get(f"/teams/{tid}/review-evening/{ev}").data.decode()
    assert json.loads(page.split('id="ev-boot">')[1].split("</script>")[0])["econ"] == json.loads(json.dumps(want))
    js = (ROOT / "nexus/web/static/evening.js").read_text()
    assert "const ec = (B.econ && B.econ.rounds || {})[String(r.n)];" in js
    # the Premier match review
    rd = sr.team_dir(tid) / "reviews"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / f"{MATCH_ID}.json").write_text(json.dumps({"match_id": MATCH_ID, "won": True, "score": "13-7", "map": m.map_name,
                                                     "opponent": "Them", "key_rounds": [], "trade_pairs": [], "players": []}))
    page = c.get(f"/teams/{tid}/premier/review/{MATCH_ID}").data.decode()
    assert 'id="econ"' in page and page.count('class="ec ') == len(want["rounds"])
    assert "P pistol · E eco · F force · B full buy" in page


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Economy", "Money", "{x} each · bought {y}", "half the team bought, half saved",
              "a low buy with money for a full buy", "a lost force that broke the next round",
              "a lost full buy and no rebuy the round after", "{name} bought while the team saved",
              "{name} saved while the team bought", "Every buy fit the money."):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 76)
    assert "## 4.76" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
