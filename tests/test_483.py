"""4.83: the lineups a strat needs, step by step, matched with the team's lineups library (stats/stratlineups.py): on
the strat page, under each strat on the match screen (yours first) and in the strat's Discord post."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import stratlineups as sl  # noqa: E402

ROOT = Path(__file__).parent.parent
NAMES = {("Sova", "Ability1"): "Recon Bolt", ("Viper", "Ability2"): "Toxic Screen", ("Omen", "Ability2"): "Dark Cover"}


def place(x, y):
    return ("A Main", "A") if x < 500 else ("B Long", "B")


def board(me="Manuel"):
    return {"steps": [
        {"name": "Default", "items": [{"t": "agent", "a": "Sova", "c": "us", "label": me, "x": 100, "y": 100}]},
        {"name": "Execute A", "items": [
            {"t": "ab", "a": "Sova", "s": "Ability1", "c": "us", "x": 200, "y": 300},
            {"t": "ab", "a": "Sova", "s": "Ability1", "c": "us", "x": 210, "y": 300},        # same callout: once
            {"t": "ab", "a": "Omen", "s": "Ability2", "c": "them", "x": 200, "y": 300},      # theirs: not ours to throw
            {"t": "ab", "a": "Viper", "s": "Ability2", "c": "us", "x": 800, "y": 300},
            {"t": "ab", "a": "Omen", "s": "Ability2", "c": "us", "x": 220, "y": 320},
            {"t": "mark", "s": "!", "x": 1, "y": 1}]}]}


def test_match():
    steps = sl.uses(board(), lambda a, s: NAMES.get((a, s), ""), place)
    assert [s["step"] for s in steps] == ["Execute A"]
    us = steps[0]["uses"]
    assert [(u["agent"], u["ability"], u["near"], u["site"], u["player"]) for u in us] == [
        ("Sova", "Recon Bolt", "A Main", "A", "Manuel"), ("Viper", "Toxic Screen", "B Long", "B", ""), ("Omen", "Dark Cover", "A Main", "A", "")]
    lib = [{"id": 1, "agent": "Sova", "ability": "Recon Bolt", "side": "attack", "site": "B", "title": "B dart", "url": "https://x.y/1"},  # other site
           {"id": 2, "agent": "Sova", "ability": "Recon Bolt", "side": "", "site": "A", "title": "Dart A Main", "url": "https://x.y/2"},
           {"id": 3, "agent": "Sova", "ability": "", "side": "attack", "site": "", "title": "Any Sova", "url": ""},
           {"id": 4, "agent": "Viper", "ability": "Toxic Screen", "side": "defense", "site": "", "title": "Wall", "url": ""}]  # other side
    ideas = [{"agent": "Viper", "ability": "Toxic Screen", "site": "B", "title": "Wall B Long from B Lobby", "notes": "Thrown 5×"}]
    sl.match(steps, lib, "attack", ideas)
    sova, viper, omen = steps[0]["uses"]
    assert sova["lineup"]["title"] == "Dart A Main" and sova["more"] == 1
    assert viper["lineup"] is None and viper["idea"]["title"] == "Wall B Long from B Lobby"
    assert omen["lineup"] is None and omen["idea"] is None and sl.missing(steps) == 2
    assert sl.lines(steps) == ["Sova (Manuel) · Recon Bolt → A Main: [Dart A Main](<https://x.y/2>)",
                               "Viper · Toxic Screen → B Long: none in the library, you throw “Wall B Long from B Lobby” in your replays",
                               "Omen · Dark Cover → A Main: no lineup in the library yet"]
    assert sl.lines(steps, "Default") == []
    assert sl.uses({}, lambda a, s: "", place) == [] and sl.uses({"steps": "x"}, lambda a, s: "", place) == []


def test_pages(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c, name="Manuel", tag="#EUW")
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "user_id": uid}], maps=["Lotus"])
    sid = store.create_strat(tid, uid, "Lotus", "attack", "A split", board("Manuel"))
    store.add_lineup(tid, uid, map="Lotus", agent="Sova", ability="", side="attack", title="Dart A Main", url="https://youtu.be/abcdefghijk")
    page = c.get(f"/teams/{tid}/strats/{sid}").data.decode()
    assert 'id="lineups"' in page and "Lineups for this strat" in page and "Execute A" in page
    assert "▶ Dart A Main" in page and "https://youtu.be/abcdefghijk" in page and page.count("No lineup in the library yet") == 2
    m = c.get(f"/teams/{tid}/match?map=Lotus").data.decode()
    assert '<div class="mine">' in m and "▶ Dart A Main" in m and "3 lineups · 2 not in the library" in m
    # a strat without abilities: no card
    sid2 = store.create_strat(tid, uid, "Lotus", "defense", "Empty", {"steps": [{"name": "x", "items": []}]})
    assert 'id="lineups"' not in c.get(f"/teams/{tid}/strats/{sid2}").data.decode()
    # the Discord post: the lineups of the step
    from nexus import discord as dc
    sent = []

    class Resp:
        status_code = 204
        text = ""
    monkeypatch.setattr(dc.requests, "post", lambda url, data=None, files=None, timeout=None, json=None: sent.append((url, data, files)) or Resp())
    store.update_team(tid, discord={"prep_url": "https://discord.com/api/webhooks/1/x"})
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = c.post(f"/api/teams/{tid}/strats/{sid}/discord", data={"png": (io.BytesIO(png), "b.png"), "step": "Execute A"},
               content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    text = json.loads(sent[-1][1]["payload_json"])["content"]
    assert "**Lineups**" in text and "[Dart A Main](<https://youtu.be/abcdefghijk>)" in text and "Sova (Manuel)" in text


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Lineups for this strat", "No lineup in the library yet:", "add one", "Not in the library.", "practise in 3D", "record in 3D",
              "not in the library", "on the strat page", "Lineups library"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 83)
    assert "## 4.83" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
