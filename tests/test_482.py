"""4.82: the week ahead: every practice and match day of the next 7 days, in the Sunday team report and on the
practice page (stats/teamreport.week_section, web/practice.week_of, web/availability.days_of)."""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import teamreport as trp  # noqa: E402

ROOT = Path(__file__).parent.parent
SUNDAY = datetime.datetime(2026, 11, 29, 20, 5)


def test_week_section():
    days = [{"label": "Mon 30.11.", "practice": None, "match": None},
            {"label": "Wed 02.12.", "practice": {"time": "19:00", "end": "20:30", "focus": ["Lotus: attack strats", "Lotus lineups",
                                                                                          "Crossfire drill", "x"]}, "match": None},
            {"label": "Thu 03.12.", "practice": {"time": "18:00", "end": "19:00", "focus": []},
             "match": {"time": "20:00", "map": "Lotus", "playoffs": False, "avail": "4/5 confirmed · no answer: Obi"}},
            {"label": "Sun 06.12.", "practice": None, "match": {"time": "20:00", "map": None, "playoffs": True, "avail": ""}}]
    assert trp.week_section(days, {"Lotus": ["vs RV: their hit"]}) == [
        "**Wed 02.12.** 🏋️ Practice 19:00–20:30: Lotus: attack strats, Lotus lineups, Crossfire drill",
        "**Thu 03.12.** 🏋️ Practice 18:00–19:00 · 🏆 Match 20:00 on **Lotus** · 4/5 confirmed · no answer: Obi",
        "**Sun 06.12.** 🏆 Playoffs 20:00",
        "Boards against opponents on Lotus: vs RV: their hit"]
    assert "Draft a plan in the strat book" in trp.week_section(days[1:3], {"Lotus": []})[-1]
    assert trp.week_section([days[0]])[0].startswith("Nothing planned in the next 7 days")
    emb = trp.embeds("Squad", "2026-W48", [], [], [], ["x"])[0]
    assert [f["name"] for f in emb["fields"]] == ["🗓️ The week ahead"]


def test_week_of(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pids = [add_profile(c, name=n, tag="#EUW") for n in ("Ka", "Obi")]
    uid = store.user_by_name("manuel").id
    tid = store.create_team(uid, "Squad")
    store.update_team(tid, members=[{"pid": p, "kind": "starter"} for p in pids], maps=["Lotus"])
    c.post(f"/teams/{tid}/practice", data={"days": ["2"], "time": "19:00", "minutes": "90"})     # practice Wednesdays
    info = store.team(tid).sync_info
    info["brief"] = {"days": [3], "time": "20:30"}                                              # match day Thursday
    store.update_team(tid, sync=info)
    store.set_availability(tid, pids[0], "2026-12-03", "yes", "", uid)
    t = store.team(tid)
    week = app.extensions["nexus"]["week_ahead"](t, SUNDAY)
    assert [d["label"] for d in week] == ["Mon 30.11.", "Tue 01.12.", "Wed 02.12.", "Thu 03.12.", "Fri 04.12.", "Sat 05.12.", "Sun 06.12."]
    assert [d["date"] for d in week if d["practice"]] == ["2026-12-02"]
    assert week[2]["practice"] == {"time": "19:00", "end": "20:30", "minutes": 90, "focus": []}
    assert [d["date"] for d in week if d["match"]] == ["2026-12-03"]
    m = week[3]["match"]
    assert m["time"] == "20:30" and m["map"] == "Lotus" and m["yes"] == 1 and m["avail"].startswith("1/5 confirmed")
    rep = app.extensions["nexus"]["team_report"](t, SUNDAY)
    assert rep["next"][:2] == ["**Wed 02.12.** 🏋️ Practice 19:00–20:30",
                               f"**Thu 03.12.** 🏆 Match 20:30 on **Lotus** · {m['avail'][:160]}"]
    assert rep["next"][2].startswith("No boards against opponents on Lotus yet")
    # the practice page: today and the 6 days after
    page = c.get(f"/teams/{tid}/practice").data.decode()
    assert "The week ahead" in page and page.count('<div class="today"><b>') == 1 and "🏋️ Practice" in page


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("The week ahead", "Strats, economy, drills and the week ahead, in one post", "Playoffs"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 82)
    assert "## 4.82" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
