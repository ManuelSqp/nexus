"""4.86: the team calendar: a private iCalendar link (works in Apple Calendar, Google, Outlook, any calendar app) with
the practice and match days (stats/teamcal.py, web/practice.py)."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import teamcal as tc  # noqa: E402

ROOT = Path(__file__).parent.parent


def test_ics():
    assert tc.esc("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    long = "DESCRIPTION:" + "ä" * 60
    parts = tc.fold(long)
    assert all(len(p.encode()) <= 75 for p in parts) and parts[1].startswith(" ") and "".join(p[1:] if i else p for i, p in enumerate(parts)) == long
    mon = datetime.date(2026, 11, 30)
    ev = tc.events(mon, 7, {"days": [2], "time": "19:00", "minutes": 90}, {"days": [3, 5], "time": "20:30", "minutes": 90},
                   lambda d: ("Lotus", d.weekday() == 5), "Squad")
    assert [(e["uid"], e["title"]) for e in ev] == [("practice-2026-12-02", "🏋️ Squad practice"), ("match-2026-12-03", "🏆 Squad match: Lotus"),
                                                     ("match-2026-12-05", "🏆 Squad playoffs: Lotus")]
    assert ev[0]["start"] == datetime.datetime(2026, 12, 2, 19, 0) and ev[0]["end"] == datetime.datetime(2026, 12, 2, 20, 30)
    assert tc.events(mon, 7, None, {"days": [3], "time": "x"}) == []
    body = tc.ics(ev, "Squad (Nexus)", "t1", datetime.datetime(2026, 11, 26, 10), "https://n/p")
    assert body.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 3 and "UID:practice-2026-12-02-t1@nexus" in body and "X-WR-CALNAME:Squad (Nexus)" in body
    start = tc.utc(datetime.datetime(2026, 12, 2, 19, 0))
    assert f"DTSTART:{start}" in body and start.endswith("Z")
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


def test_feed(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c, name="Ka", tag="#EUW")
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter", "user_id": uid}], maps=["Lotus"])
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert "In your calendar" in page and "Make a calendar link" in page
    assert c.post(f"/teams/{tid}/calendar").status_code == 302
    tok = store.team(tid).sync_info["calendar"]["token"]
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert f"/teams/{tid}/calendar/{tok}.ics" in page and "webcal://" in page and "Copy link" in page
    c.post(f"/teams/{tid}/calendar")                                   # again: the same link
    assert store.team(tid).sync_info["calendar"]["token"] == tok
    anon = app.test_client()                                           # calendar apps don't log in
    r = anon.get(f"/teams/{tid}/calendar/{tok}.ics")
    assert r.status_code == 200 and r.headers["Content-Type"].startswith("text/calendar")
    body = r.data.decode()
    assert "BEGIN:VCALENDAR" in body and "BEGIN:VEVENT" not in body     # nothing set yet: no invented days
    assert anon.get(f"/teams/{tid}/calendar/wrong.ics").status_code == 404
    assert anon.get(f"/teams/{tid}/practice").status_code == 302         # the rest still needs a login
    c.post(f"/teams/{tid}/practice", data={"days": ["2"], "time": "19:00", "minutes": "90"})
    info = store.team(tid).sync_info
    info["brief"] = {"days": [3], "time": "20:30"}
    store.update_team(tid, sync=info)
    body = anon.get(f"/teams/{tid}/calendar/{tok}.ics").data.decode()
    assert body.count("SUMMARY:🏋️ Squad practice") >= 11 and body.count("SUMMARY:🏆 Squad match") >= 11
    # a new link: the old one stops working
    c.post(f"/teams/{tid}/calendar", data={"action": "reset"})
    new = store.team(tid).sync_info["calendar"]["token"]
    assert new != tok and anon.get(f"/teams/{tid}/calendar/{tok}.ics").status_code == 404
    assert anon.get(f"/teams/{tid}/calendar/{new}.ics").status_code == 200


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("📅 In your calendar", "Make a calendar link", "Copy link", "Open in my calendar app", "New link",
              "Calendar link made: add it to your calendar app."):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 86)
    assert "## 4.86" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
