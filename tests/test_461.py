"""4.61: the comps page's other options as cards: what changes from the best comp, why, when you'd pick it; 3 of them;
"Use this comp" makes a draft marked "our comp" for the map."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import _premier_team, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats.compalts import explain, matches  # noqa: E402

ROOT = Path(__file__).parent.parent


def _pk(player, agent, role, n_map=0, n_all=0, wr_map=None, wr_all=None, why=(), low=False):
    return {"player": player, "agent": agent, "role": role, "n_map": n_map, "n_all": n_all, "wr_map": wr_map,
            "wr_all": wr_all, "why": list(why), "low_sample": low}


MAIN = {"ok": True, "total": 120.0, "picks": [
    _pk("A", "Skye", "Initiator", 1, 1, 1.0, 1.0), _pk("B", "Omen", "Controller", 1, 7, 1.0, 0.79),
    _pk("C", "Chamber", "Sentinel", 6, 13, 0.87, 0.62), _pk("D", "Raze", "Duelist", 5, 55, 0.82, 0.51),
    _pk("E", "Sova", "Initiator", 0, 4, None, 1.0)]}


def test_explain_says_what_changes_and_why():
    alt = {"ok": True, "total": 114.0, "picks": [
        MAIN["picks"][0], _pk("B", "Clove", "Controller", 3, 11, 0.67, 0.64, ["#2 in B's agent pool"]),
        _pk("C", "Cypher", "Sentinel", 2, 9, 0.5, 0.67, ["key on Abyss: watches the long lines"]),
        MAIN["picks"][3], MAIN["picks"][4]]}
    x = explain(MAIN, alt, "Abyss")
    assert [c["agent"] for c in x["changes"]] == ["Clove", "Cypher"] and x["same"] == ["A", "D", "E"]
    clove = x["changes"][0]
    assert clove["was"] == "Omen" and clove["facts"][:2] == ["3 games on Abyss, 67 % won", "11 overall, 64 % won"]
    assert "#2 in B's agent pool" in clove["facts"]
    assert x["changes"][1]["facts"][-1] == "key on Abyss: watches the long lines"
    assert x["drop"] == 6.0 and x["level"] == "close to the best"                       # 3 points per swap
    assert explain(MAIN, {**alt, "total": 90.0}, "Abyss")["level"] == "a bit weaker"    # 15 per swap
    assert x["when"][0].startswith("if Omen or Chamber doesn't work out")
    assert not any(w.startswith("when you want") for w in x["when"])                 # same role mix


def test_explain_role_shift_and_practice():
    alt = {"ok": True, "total": 80.0, "picks": [
        MAIN["picks"][0], MAIN["picks"][1], _pk("C", "Neon", "Duelist", 0, 1, None, 0.0, low=True),
        MAIN["picks"][3], MAIN["picks"][4]], "web": {"note": "double duelist rush"}}
    x = explain(MAIN, alt, "Abyss")
    assert x["level"] == "a fallback" and x["changes"][0]["was_role"] == "Sentinel"
    assert "when you want more entry power" in x["when"] and "needs practice first: C on Neon" in x["when"]
    assert x["when"][-1] == "from the web: double duelist rush"
    assert "no Sentinel left: nobody watches the flank alone" in x["when"]
    assert x["changes"][0]["facts"][0] == "not played on Abyss yet"
    assert matches(alt, {"Skye", "Omen", "Neon", "Raze", "Sova"}) and not matches(alt, set())


def test_comps_page_cards_and_use_this_comp(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    tid = _premier_team(app, c, monkeypatch)
    page = c.get(f"/teams/{tid}").data.decode()
    sel = re.search(r'name="map" value="([^"]+)"><input type="hidden" name="from" value="comp:1"', page).group(1)
    n = page.count('<div class="opt ')
    assert 1 <= n <= 3 and "Other options" in page and "When to pick it:" in page and "Use this comp" in page
    assert page.count('class="oc ch') >= 2 * n and "was " in page                        # every option changes 2+
    r = c.post(f"/teams/{tid}/drafts", data={"map": sel, "from": "comp:1", "status": "main"})
    assert r.status_code == 302
    d1 = max(store.drafts(tid, sel), key=lambda d: d["id"])
    assert d1["data"]["status"] == "main" and d1["name"].startswith("Suggestion 2: ")
    page = c.get(f"/teams/{tid}?map={sel}").data.decode()
    assert "Our comp" in page and f"d={d1['id']}" in page and '<div class="opt ours">' in page
    if n >= 2:                                                                           # another one: only one "our comp"
        c.post(f"/teams/{tid}/drafts", data={"map": sel, "from": "comp:2", "status": "main"})
        st = {d["id"]: d["data"]["status"] for d in store.drafts(tid, sel)}
        assert list(st.values()).count("main") == 1 and st[d1["id"]] == "try"
    # a plain suggestion draft (the drafts page) stays an idea
    c.post(f"/teams/{tid}/drafts", data={"map": sel, "from": "comp:0"})
    assert max(store.drafts(tid, sel), key=lambda d: d["id"])["data"]["status"] == "idea"


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Use this comp", "When to pick it:", "close to the best", "# games on {x}, # % won", "was {x}"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 61, 0)
    assert "## 4.61.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
