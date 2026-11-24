"""4.69.1: every map in Map prep, more maps in Map angles (and why not the rest); normal scenarios for the
perfect sens, if you want."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_4562 import payload  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.maps import _parse_maps  # noqa: E402
from nexus.stats import mapangles as ma  # noqa: E402
from nexus.stats import trainer as tr  # noqa: E402

ROOT = Path(__file__).parent.parent


def _ascent(edit):
    pay = payload()
    for c in pay["data"][1]["callouts"]:
        edit(c)
    return next(m for m in _parse_maps(pay) if m.name == "Ascent")


def test_sites_named_otherwise():
    base = {p["id"] for p in ma.positions(_ascent(lambda c: None))}
    assert base

    def lower_and_renamed(c):                       # "a" instead of "A", the site's region not called "Site"
        c["superRegionName"] = c["superRegionName"].lower() if c["superRegionName"] in ("A", "B") else c["superRegionName"]
        if c["regionName"] == "Site":
            c["regionName"] = "Plant"
            c["superRegionName"] = c["superRegionName"]
    mi = _ascent(lower_and_renamed)
    assert {p["id"] for p in ma.positions(mi)} == base
    assert ma.why_not(None) == "no map data yet"
    mi.callouts = []
    assert ma.why_not(mi) == "no callouts in the map data" and ma.positions(mi) == []


def test_wider_look_on_open_maps(monkeypatch):
    mi = _ascent(lambda c: None)
    n = len(ma.positions(mi))
    monkeypatch.setattr(ma, "FAR", 4.0)               # as if every callout were far away
    wide = ma.positions(mi)
    assert wide and len(wide) <= n and all(len(p["spots"]) >= ma.WIDE_MIN for p in wide)
    monkeypatch.setattr(ma, "WIDE_FAR", 4.0)
    assert ma.positions(mi) == [] and ma.why_not(mi) == "too few callouts around its sites"


def test_normal_points_and_recommend():
    now = time.time()
    run = lambda s, sens, score, **kw: {"s": s, "sens": sens, "score": score, "t": now - 3600, **kw}   # noqa: E731
    runs = [run("gridshot", 0.30, 80), run("gridshot", 0.40, 100), run("gridshot", 0.40, 90), run("gridshot", 0.50, 70),
            run("tracking", 0.40, 50),                                   # one sens only: no help
            run("gridshot", 0.35, 999, k=[1.2, 1]),                      # made harder: left out
            run("map_angles", 0.30, 50), run("map_angles", 0.5, 60),     # left out
            {"s": "gridshot", "score": 50, "t": now}]                    # no sens (before 4.69.1)
    pts, wts, used = tr.normal_points(runs, now)
    assert [(p[0], round(p[1], 3)) for p in pts] == [(0.3, 0.8), (0.4, 0.95), (0.5, 0.7)] and used == 4
    assert wts == [tr.NORMAL_WEIGHT / 3, tr.NORMAL_WEIGHT * 2 / 3, tr.NORMAL_WEIGHT / 3]
    rec = tr.recommend([], now, runs)                                    # no sens test: the runs alone (3 sens)
    assert 0.3 < rec["sens"] < 0.5 and rec["sure"] == "low" and rec["normal"] == {"runs": 4, "points": 3}
    assert tr.recommend([], now) is None and tr.recommend([], now, runs[:1]) is None
    assert tr.clean_run({"scenario": "onetap_heads", "score": 50, "seconds": 60, "hits": 5, "shots": 6, "sens": 0.41})["sens"] == 0.41
    assert "sens" not in tr.clean_run({"scenario": "onetap_heads", "score": 50, "seconds": 60, "hits": 5, "shots": 6, "sens": 99})


def test_page(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert "Count my normal scenarios too" in page and 'name="on" value="1"' in page
    assert page.count('<option value="prep_') >= 13                       # every map in Map prep
    c.post(f"/profiles/{pid}/trainer/sens-normal", data={"on": "1"})
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert 'name="on" value="0"' in page and "runs remember their sens from now on" in page
    js = (ROOT / "nexus/web/static/trainer.js").read_text()
    assert "seconds: st.seconds, sens: sens()}" in js


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Count my normal scenarios too", "Not here yet: {x}", "no sites in its callouts"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 69, 1)
    assert "## 4.69.1" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
