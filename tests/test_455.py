"""4.55: your keys in the aim trainer; movement abilities in the replay viewer (teleports, dashes, sprinting)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import agentanim as aa  # noqa: E402
from nexus.web import trainer as wt  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"
HAVE_NODE = subprocess.run(["which", "node"], capture_output=True).returncode == 0


def _boot(page):
    return json.loads(re.search(r"window.NEXUS_TRAINER = (\{.*?\});\s*</script>", page, re.S).group(1))


def test_trainer_has_your_keys(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert 'id="tr-kpanel"' in page and 'id="tr-kbox"' in page and 'data-a="kdone"' in page
    assert page.index("keys.js") < page.index("trainer.js")
    b = _boot(page)
    assert b["keys"]["shoot"] == ["Mouse0", ""] and b["defaults"]["full"] == ["KeyF", ""] and b["keys_api"] == "/api/aim/keys"
    assert [a for a, _ in b["actions"]] == ["shoot", "next", "restart", "full"] == [a for a, _ in wt.TRAINER_KEYS]
    r = c.post("/api/aim/keys", json={"shoot": ["Mouse0", "KeyJ"], "full": ["KeyG", ""]})
    assert r.status_code == 200
    b = _boot(c.get(f"/profiles/{pid}/trainer").data.decode())
    assert b["keys"]["shoot"] == ["Mouse0", "KeyJ"] and b["keys"]["full"] == ["KeyG", ""]
    assert b["keys"]["defuse"] == ["Digit4", ""]                  # all your keys: saving here keeps the drills'


def test_trainer_script():
    js = (STATIC / "trainer.js").read_text()
    for x in ("const KB = window.NexusKeys;", "isKey('shoot', 'Mouse' + e.button)", "isKey('shoot', e.code)",
              "isKey('full', e.code) && plain", "isKey('next', e.code) && st.phase === 'ready'",
              "isKey('restart', e.code) && st.phase === 'done'", "data-a=\"keys\"", "function openKeys()",
              "KB.editor($('tr-kbox')", "onSave: k => { keys = k; }", "e.deltaY < 0 ? 'WheelUp' : 'WheelDown'",
              "keys: () => keys"):
        assert x in js, x
    assert "(e.key === 'f' || e.key === 'F')" not in js and "if (e.button === 0) { firing = true; shoot(); }" not in js


def test_sprint_clips():
    assert aa.VERSION == 3
    for d in ("N", "NE", "E", "SE", "S", "SW", "W", "NW"):
        assert aa.CLIPS[f"sprint_{d}"] == ((f"TP_Core_Sprint{d}_LB",), "lb") and f"sprint_{d}" in aa.LOOP


def test_motion_script():
    mj = (STATIC / "motion.js").read_text()
    for x in ("if (a[7] === TELEPORT) f = f < 0.5 ? 0 : 1;", "function moves(paths, casts, agentOf)",
              "function moveObjects(fx, t)", "sprint: 6.4", "Omen: {C: 'teleport', X: 'teleport'}",
              "Chamber: {E: 'teleport'}", "Yoru: {E: 'teleport'}", "Jett: {E: 'dash', Q: 'up'}", "Raze: {Q: 'up'}",
              "['sprint', gd * wFast * wSprint]"):
        assert x in mj, x
    rj = (STATIC / "replay.js").read_text()
    assert "d._fx = NM.moves(d.paths, d.casts" in rj and "NM.moveObjects(S.d._fx, S.t)" in rj
    assert rj.index("d._fx = NM.moves(") < rj.index("NM.prep(d.paths);")


@pytest.mark.skipif(not HAVE_NODE, reason="node missing")
def test_moves_in_node(tmp_path):
    js = """
global.window = {nexusMap3D: {clips: () => ['idle', 'run_N', 'sprint_N', 'sprint_W', 'sprint_E', 'walk_N', 'fall', 'hold'], map: () => ({hand: 1})}};
require(%s);
const NM = window.NexusMotion, P = pts => pts.map(([t, x, z]) => [t, x, 0, z, 0]);
const om = [], je = [], so = [], ne = [];
for (let k = 0; k <= 30; k++) { const t = k * 0.2; om.push([t, t < 3.0 ? t : 8 + t, 0]); }
for (let k = 0; k <= 20; k++) { const t = k * 0.2; je.push([t, t * 5 + (t > 1 ? Math.min(7, (t - 1) / 0.4 * 7) : 0), 5]); }
for (let k = 0; k <= 20; k++) { const t = k * 0.2; so.push([t, t < 2 ? 0 : 12, 10]); }
for (let k = 0; k <= 20; k++) { const t = k * 0.2; ne.push([t, 0, 20 - t * 8]); }
const paths = {0: P(om), 1: P(je), 2: P(so), 3: P(ne)}, ag = {0: 'Omen', 1: 'Jett', 2: 'Sova', 3: 'Neon'};
const fx = NM.moves(paths, [[2.0, 0, 'C'], [1.0, 1, 'E'], [0.5, 3, 'E']], i => ag[i]);
NM.prep(paths);
const flags = i => paths[i].map(r => r[7] || 0).join('');
const lb = (i, t) => NM.motion(paths[i], t, NM.at(paths[i], t)).anim.lb.map(x => x[0]);
console.log(JSON.stringify({omen: flags(0), jett: flags(1), sova: flags(2), neon: flags(3), fx: fx.length,
  at: [2.85, 2.95].map(t => NM.at(paths[0], t)[0]), om: lb(0, 2.9), je: lb(1, 1.3), ne: lb(3, 1.0),
  live: NM.moveObjects(fx, 2.9).length, gone: NM.moveObjects(fx, 5).length}));
""" % json.dumps(str(STATIC / "motion.js"))
    f = tmp_path / "t.js"
    f.write_text(js)
    out = json.loads(subprocess.run(["node", str(f)], capture_output=True, text=True, check=True).stdout)
    assert out["omen"] == "0" * 14 + "1" + "0" * 16          # the jump right after the cast: a teleport
    assert out["jett"] == "00000220000000000000" + "0"        # the two fast samples after Tailwind: a dash
    assert out["sova"] == "000000000100000000000"             # no casts, 12 m in 0.2 s: still a teleport
    assert out["neon"] == "0" * 21                            # sprinting isn't marked: it's just fast
    assert [round(v, 2) for v in out["at"]] == [2.8, 11.0]      # no sliding through the wall
    assert out["om"] == ["idle"] and out["je"] == ["sprint_W"] and out["ne"] == ["sprint_N"]
    assert out["fx"] == 2 + 2 + 8 and out["live"] == 2 and out["gone"] == 0


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Keys", "Start, go on, next scenario", "Play it again"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 55)
    assert "## 4.55.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
