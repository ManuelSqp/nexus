"""4.85: the match-day ping on Discord: on the match days, from a set time until the match, once a day: the time and
map, who's playing, the ones who haven't answered pinged, the boards against opponents and when the brief comes."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.web.availability import morning_text  # noqa: E402

ROOT = Path(__file__).parent.parent
THU = datetime.datetime(2026, 12, 3, 12, 30)            # a Thursday


def test_text():
    s = {"map": "Lotus", "playoffs": False, "yes": [{"pid": 1, "name": "Ka"}], "maybe": [], "no": [], "missing": [], "notes": [],
         "unknown": [{"pid": 2, "name": "Obi"}, {"pid": 3, "name": "Zed"}]}
    text, ping = morning_text(s, {2: "1234567890"}, "Squad", "20:00", ["**Boards:** x"], "https://n/av")
    assert text.split("\n") == ["🏆 **Squad: Match day today**, 20:00 on **Lotus**", "**Who's playing:** 1/5 confirmed",
                                "**No answer yet:** <@1234567890>, Zed (can you play? Mark it under Premier › Availability: https://n/av)",
                                "**Boards:** x"]
    assert ping == ["1234567890"]
    text, ping = morning_text({**s, "unknown": [], "playoffs": True, "map": None}, {}, "Squad", "20:00")
    assert text.split("\n") == ["🏆 **Squad: Playoffs today**, 20:00", "**Who's playing:** 1/5 confirmed"] and ping == []


def test_tick(app, monkeypatch):  # noqa: F811 (fixture)
    from nexus import discord as dc
    sent = []
    monkeypatch.setattr(dc, "post", lambda url, content="", embeds=None, session=None, mentions=None: sent.append((url, content, mentions)))
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pids = [add_profile(c, name=n, tag="#EUW") for n in ("Ka", "Obi")]
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pids[0], "kind": "starter", "user_id": uid},
                                    {"pid": pids[1], "kind": "starter", "discord_id": "1234567890"}], maps=["Lotus"],
                      discord={"prep_url": "https://discord.com/api/webhooks/1/x"})
    r = c.post(f"/teams/{tid}/premier/settings", data={"on": "1", "days": ["3"], "time": "20:00", "before": "60", "ping": "1", "ping_at": "12:00"})
    assert r.status_code == 302
    b = store.team(tid).sync_info["brief"]
    assert b["ping"] is True and b["ping_at"] == "12:00" and b["days"] == [3]
    c.post(f"/teams/{tid}/premier/settings", data={"days": ["3"], "time": "20:00", "ping_at": "25:99"})
    assert store.team(tid).sync_info["brief"]["ping_at"] == "12:00" and store.team(tid).sync_info["brief"]["ping"] is False
    c.post(f"/teams/{tid}/premier/settings", data={"on": "1", "days": ["3"], "time": "20:00", "before": "60", "ping": "1", "ping_at": "12:00"})
    store.set_availability(tid, pids[0], "2026-12-03", "yes", "", uid)
    sid = store.create_strat(tid, uid, "Lotus", "attack", "vs RV: their setup", {"steps": [], "prep": {"team": "Rivals", "made": "x"}})
    assert sid
    tick = next(f for f in app.extensions["nexus"]["ticks"] if f.__name__ == "tick_ping")
    assert tick(THU.replace(hour=11, minute=59)) == [] and tick(THU.replace(hour=20, minute=0)) == []      # before / at match time
    assert tick(THU - datetime.timedelta(days=1)) == []                                                    # Wednesday: no match day
    store.set("site_url", "https://nexus.example")
    assert tick(THU) == [tid] and tick(THU.replace(hour=13)) == []                                        # once a day
    url, text, mentions = sent[-1]
    assert url == "https://discord.com/api/webhooks/1/x" and mentions == ["1234567890"]
    assert "Match day today**, 20:00 on **Lotus**" in text and "<@1234567890>" in text and "1/5 confirmed" in text
    assert f"https://nexus.example/teams/{tid}/premier/availability" in text
    assert "**Boards against opponents on Lotus:** vs RV: their setup" in text and "The brief (comp, game plans, focus) comes at 19:00." in text
    # by hand, and the settings card
    n = len(sent)
    assert c.post(f"/teams/{tid}/premier/ping").status_code == 302 and len(sent) == n + 1
    assert "/premier/availability" in sent[-1][1]
    tpl = (ROOT / "nexus/web/templates/premier.html").read_text()       # (the page shows for Premier teams)
    assert 'name="ping_at"' in tpl and "Send the match-day ping now" in tpl


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Match-day ping", "Ping at", "Send the match-day ping now", "Match day today", "Playoffs today", "No answer yet:",
              "Who's playing:"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 85)
    assert "## 4.85" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
