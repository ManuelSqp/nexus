"""4.77: the crosshair placement drill: walked along the attackers' route, a head on every hiding place the moment
it comes into view, and where your crosshair was right then (degrees off, above or below)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drillchart as dch  # noqa: E402
from nexus.stats import drillgoals as dg  # noqa: E402
from nexus.stats import drills as dr  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus/web/static"
AI = STATIC / "drillai.js"
NODE = shutil.which("node")


def run(code: str):
    out = subprocess.run([NODE, "-e", f"const AI = require({json.dumps(str(AI))});\n{code}"], capture_output=True,
                         text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="needs node")
def test_error_and_route():
    got = run("""
      const eye = [0, 1.6, 0], head = [0, 1.6, -10];                    // straight ahead (yaw 0 looks along -z)
      const r = {
        on: AI.placeError(eye, 0, 0, head),
        low: AI.placeError(eye, 0, -2 * Math.PI / 180, head),         // aiming 2° under it
        side: AI.placeError(eye, 5 * Math.PI / 180, 0, head),         // 5° to the side
        sum: AI.placeSummary([{off: 1, up: -1}, {off: 3, up: -2}, {off: 10, up: 0}, null, {off: NaN, up: 0}]),
        none: AI.placeSummary([]),
        route: [AI.routeAt([[0, 0, 0], [0, 0, -10], [10, 0, -10]], 0), AI.routeAt([[0, 0, 0], [0, 0, -10], [10, 0, -10]], 15),
                AI.routeAt([[0, 0, 0], [0, 0, -10], [10, 0, -10]], 99)]};
      console.log(JSON.stringify(r));
    """)
    assert got["on"]["off"] < 1e-6 and abs(got["on"]["up"]) < 1e-6
    assert abs(got["low"]["off"] - 2) < 1e-6 and abs(got["low"]["up"] + 2) < 1e-6        # below: negative
    assert abs(got["side"]["off"] - 5) < 1e-6 and abs(got["side"]["side"] - 5) < 1e-6 and abs(got["side"]["up"]) < 1e-6
    s = got["sum"]
    assert s == {"n": 3, "median": 3, "up": -1, "on": 1, "worst": 10}
    assert got["none"]["median"] is None and got["none"]["n"] == 0
    r0, r1, r2 = got["route"]
    assert r0[:3] == [0, 0, 0] and abs(r0[3]) < 1e-9 and r0[4] is False                   # walking along -z: yaw 0
    assert r1[:3] == [5, 0, -10] and abs(r1[3] - 3.14159265 / 2) < 1e-6                     # 5 m into the second leg
    assert r2[:3] == [10, 0, -10] and r2[4] is True                                       # past the end: the end


def test_unit_and_stats():
    assert dr.KINDS["place"] == "°" and "place" not in dr.HIGHER and dr.MODE_NAMES["place"] == "Crosshair placement"
    assert dr.fmt_value(3.44, "°") == "3.4°" and dr.fmt_value(62.4, "%") == "62 %" and dr.fmt_value(0.4812, "s") == "0.48 s"
    assert dr._diff(0.8, "°") == "0.8° closer" and dr._diff(-1.2, "°") == "1.2° further off" and dr._diff(0.01, "°") == "about the same"
    run_ = dr.clean_run({"kind": "place", "reps": [3.2, None, 12.5, 170]})
    assert run_ and run_["reps"] == [3.2, None, 12.5, 170] and dr.clean_run({"kind": "place", "reps": [181]}) is None
    svg = dch.chart([{"at": 1_700_000_000, "reps": [4.0, 5.0]}, {"at": 1_700_090_000, "reps": [3.0]}], "place", {"target": 2.5})
    assert "goal 2.5°" in svg and "↓ better" in svg and "3.0°" in svg
    assert dg.fmt(2.5, "°") == "2.5°"


def test_pages(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert 'data-tab="place"' in page
    d = _spots(c, pid)
    s = d["sites"][0]
    assert "place" in s["best"]
    r = c.get(f"/profiles/{pid}/aim/play/place/testmap/{s['id']}")
    assert r.status_code == 200
    boot = json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    assert boot["mode"] == "place" and boot["drill"]["id"] == f"g-place-{s['id']}" and boot["title"].startswith("Crosshair placement: ")
    assert boot["opts"]["reps"] == 5
    r = c.post(f"/api/profiles/{pid}/aim/drill/g-place-{s['id']}/runs", json={"kind": "place", "reps": [4.2, 2.8, None]})
    assert r.status_code == 200 and r.get_json()["history"]["best"] == 2.8
    assert _spots(c, pid)["sites"][0]["best"]["place"] == 2.8
    dj = (STATIC / "drill.js").read_text()
    for x in ("const PLACE = MODE === 'place';", "if (PLACE && S.phase === 'run') placeTick(dt);",
              "const e = AI.placeError(eye(), S.yaw, S.pitch, head);", "{fov: 0, harmless: true, hide: i, appear: Infinity}",
              "(f.gone !== undefined && S.t >= f.gone && !f.dead)", "const ROUTE = MODE === 'clear' || MODE === 'entry' || PLACE;"):
        assert x in dj, x
    am = (STATIC / "aim_maps.js").read_text()
    assert "case 'place': return 'place';" in am and "tab === 'place' ? (+v).toFixed(1) + '°'" in am
    assert "const SITES = new Set(['clear', 'entry', 'place'])" in am


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Crosshair placement", "Crosshair placement:", "off their heads (median)", "Off their heads", "Height, on average",
              "too low", "too high", "at head height", "On the head (within 2°)", "worst", "No hiding place came into view"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 77)
    assert "## 4.77" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
