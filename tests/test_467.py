"""4.67: the daily warm-up (drills in a row), and the team's drill week on Discord."""
import datetime
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_454 import _with_retakes  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus import discord  # noqa: E402
from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
NOW = datetime.datetime(2026, 11, 29, 20, 30).timestamp()        # a Sunday evening
DAY = 86400


def _boot(r):
    return json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])


def test_warmup_plan():
    week = {"worse": [{"id": "g-hold-aaaaaaaaaa", "map": "Ascent"}, {"id": "m1-r3"}, {"id": "g-track-bbbbbbbbbb", "map": "Bind"}],
            "better": [{"id": "g-retake-cccccccccc", "map": "Ascent"}, {"id": "g-hold-aaaaaaaaaa", "map": "Ascent"}]}
    sug = [{"mode": "retake", "id": "dddddddddd"}, {"mode": "hold", "id": "aaaaaaaaaa"}, {"mode": "entry", "id": "eeeeeeeeee"}]
    q = dr.warmup(week, sug, "Ascent", ("ffffffffff", "Ascent"), ["g-hold-gggggggggg@Ascent"] * 3)
    assert q == ["g-hold-aaaaaaaaaa@Ascent", "m1-r3", "g-retake-dddddddddd@Ascent", "g-track-ffffffffff@Ascent",
                 "g-retake-cccccccccc@Ascent", "g-hold-gggggggggg@Ascent"]                       # each once, at most 6
    assert dr.warmup({}, [], "", None) == []
    assert dr.warmup({"worse": [{"id": "g-hold-aaaaaaaaaa", "map": ""}]}, [], "", None) == []     # no map: can't play it


def test_queue_and_warmup_route(app, synthetic):  # noqa: F811 (fixture)
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    _with_retakes(app, c, pid)
    d = _spots(c, pid)
    rt = next(r for r in d["retakes"] if r["site"] == "Z")
    ang = d["angles"][0]["id"]
    nxt = f"g-hold-{ang}@{d['map']}"
    r = c.get(f"/profiles/{pid}/aim/play/retake/{d['map']}/{rt['id']}?wt=3&queue={nxt},bad/../x,m1-r3")
    b = _boot(r)
    assert b["step"] == "1/3" and b["queue"] == [nxt, "m1-r3"]
    u = urlparse(b["next"])
    assert u.path == f"/profiles/{pid}/aim/play/hold/{d['map']}/{ang}"
    assert parse_qs(u.query) == {"queue": ["m1-r3"], "wt": ["3"], "reps": ["10"]}
    b2 = _boot(c.get(b["next"]))
    assert b2["step"] == "2/3" and b2["opts"]["reps"] == 10 and b2["next"].startswith(f"/profiles/{pid}/aim/drill/m1-r3")
    assert _boot(c.get(f"/profiles/{pid}/aim/play/retake/{d['map']}/{rt['id']}"))["step"] == ""      # not in a warm-up
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert "Daily warm-up" in page and f"/profiles/{pid}/aim/warmup" in page
    w = c.get(f"/profiles/{pid}/aim/warmup")
    assert w.status_code == 302 and "wt=" in w.headers["Location"] and "/aim/play/" in w.headers["Location"]


def _runs(at, kind, reps, **kw):
    return {"at": int(at), "kind": kind, "reps": reps, **kw}


def test_team_week_and_embed():
    a = {"g-retake-cccccccccc": [_runs(NOW - 8 * DAY, "retake", [5.0], map="Ascent", where="Retake B"),
                                 _runs(NOW - DAY, "retake", [3.5, 3.6], map="Ascent", where="Retake B")]}
    b = {"g-hold-aaaaaaaaaa": [_runs(NOW - 9 * DAY, "hold", [0.5]), _runs(NOW - 2 * DAY, "hold", [0.48], map="Bind")]}
    tw = dr.team_week([("Obi", a), ("m1", b), ("Luca", {})], "Ascent", now=NOW)
    assert [p["name"] for p in tw["players"]] == ["Obi", "m1", "Luca"] and tw["sessions"] == 2
    assert tw["top"]["name"] == "Obi" and tw["idle"] == ["Luca"]
    assert tw["focus"] == {"map": "Ascent", "sessions": 1, "missing": ["Post-plant", "Entry", "Hold an angle"]}
    e = discord.drills_embeds("Squad", "2026-W48", tw)[0]
    assert "**Obi**: 1 session, 2 reps, 1 day" in e["description"]
    assert "Retake · Ascent · Retake B: 5.00 s → 3.60 s (1.40 s faster)" in e["description"]
    assert "No drills yet this week: Luca" in e["description"] and "Map focus: Ascent" in e["description"]
    assert "Nobody drilled" in discord.drills_embeds("S", "w", dr.team_week([("x", {})], None, now=NOW))[0]["description"]


def test_sunday_post(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c)
    tid = store.create_team(store.user_by_name("manuel").id, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter"}],
                      discord={"focus_url": "https://discord.com/api/webhooks/1/abc"})
    sent = []
    monkeypatch.setattr(discord, "post", lambda url, content="", embeds=None, **kw: sent.append((url, embeds)))
    tick = next(f for f in app.extensions["nexus"]["ticks"] if f.__name__ == "tick_drills")
    sunday = datetime.datetime(2026, 11, 29, 20, 5)
    assert tick(sunday) == []                                                       # off by default
    c.post(f"/teams/{tid}/practice", data={"days": ["1"], "time": "19:00", "minutes": "90", "drills_week": "1"})
    assert tick(datetime.datetime(2026, 11, 29, 19, 0)) == [] and tick(datetime.datetime(2026, 11, 28, 21, 0)) == []
    assert tick(sunday) == [tid] and tick(sunday) == []                             # once a week
    assert sent[0][0].endswith("/abc") and "drills this week" in sent[0][1][0]["title"]
    r = c.post(f"/teams/{tid}/practice", data={"action": "post_drills"})
    assert r.status_code == 302 and len(sent) == 2
    assert "Post this week's drills" in c.get(f"/teams/{tid}/practice").data.decode()


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Daily warm-up", "Start the warm-up", "Warm-up", "Weekly drills summary on Discord", "Post this week's drills"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 67, 0)
    assert "## 4.67.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
