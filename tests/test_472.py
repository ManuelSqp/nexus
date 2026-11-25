"""4.72: retakes like in the game (a crossfire on the spike, one attacker shifts, a defuse is heard) and the death
replay after a lost duel in every drill (drillai.js, drill.js)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus/web/static"
JS = (STATIC / "drill.js").read_text()
AI = STATIC / "drillai.js"
NODE = shutil.which("node")


def run(code: str):
    out = subprocess.run([NODE, "-e", f"const AI = require({json.dumps(str(AI))});\n{code}"], capture_output=True,
                         text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="needs node")
def test_crossfire_and_shift():
    # the spike at 0,0; attackers' places around it (most used first); every place sees it
    got = run("""
      const posts = [[10, 0, 0], [9, 0, 2], [0, 0, 10], [-8, 0, -1], [12, 0, 6], [30, 0, 30]];
      let k = 0; const rnd = () => [0.1, 0.5, 0.2, 0.7, 0.3][k++ % 5];
      const plan = AI.retakePlan(posts, [0, 0, 0], 2, () => true, rnd);
      const three = AI.retakePlan(posts, [0, 0, 0], 3, () => true, () => 0);
      // only two places see the spike: those two
      const blind = AI.retakePlan(posts, [0, 0, 0], 2, (a, b) => a[0] === 0 || a[0] === -8, () => 0);
      console.log(JSON.stringify({plan, three, blind, none: AI.retakePlan([], [0, 0, 0], 2, () => true),
                                  one: AI.retakePlan(posts.slice(0, 1), [0, 0, 0], 2, () => true, () => 0)}));
    """)
    p = got["plan"]
    assert p[0]["post"] == [10, 0, 0]                                     # one of the most used places
    assert p[1]["post"] == [-8, 0, -1] and p[0]["cross"] and p[1]["cross"]   # the widest angle on the spike
    assert p[0]["shift"] is None                                           # the first keeps his angle
    assert p[1]["shift"] is not None and 3 <= p[1]["at"] <= 8              # the other shifts after a few seconds
    sx = p[1]["shift"]
    assert 3 <= ((sx[0] + 8) ** 2 + (sx[2] + 1) ** 2) ** 0.5 <= 15
    assert len(got["three"]) == 3 and len({tuple(x["post"]) for x in got["three"]}) == 3
    assert sum(1 for x in got["three"] if x["cross"]) == 2
    assert sorted(x["post"][0] for x in got["blind"]) == [-8, 0]
    assert got["none"] == [] and len(got["one"]) == 1 and got["one"][0]["shift"] is None


@pytest.mark.skipif(not NODE, reason="needs node")
def test_replay_path_and_why():
    got = run("""
      const trail = [[0, 0, 0, 0, 0, 0], [0.5, 1, 0, 0, 0, 1], [1, 2, 0, 0, 0, 0]];
      console.log(JSON.stringify({
        path: AI.trailPath(trail), at: AI.trailAt(trail, 0.7), first: AI.trailAt(trail, -1),
        a: AI.deathFacts({moving: 5, accurate: 1.75, defusing: false, youSaw: null, heSaw: 1}),
        b: AI.deathFacts({moving: 0, accurate: 1.75, defusing: true, youSaw: 2, heSaw: 1.5, reloading: true}),
        c: AI.deathFacts({moving: null, accurate: 1.75, youSaw: 1, heSaw: 1.02})}));
    """)
    assert got["path"][1] == [0.5, 1, -0.45, 0, 0, 0, 0] and got["path"][0][2] == 0     # crouched: a bit lower
    assert got["at"][0] == 0.5 and got["first"][0] == 0
    assert got["a"] == ["you were moving", "you never saw him"]
    assert got["b"] == ["you were on the spike", "you were reloading", "he saw you first"]
    assert got["c"] == []                                                  # you saw each other at the same time


def test_drill_uses_it():
    assert "const NM = window.NexusMotion, KB = window.NexusKeys, AI = window.NexusDrillAI;" in JS
    i = JS.index("} else if (MODE === 'retake') {")
    rt = JS[i:JS.index("} else if (MODE === 'postplant') {", i)]
    assert "AI.retakePlan(SP.posts.slice(0, 6), SP.plant" in rt and "shiftPath(x.post, x.shift, x.at, R, false)" in rt
    # a defuse is heard: whoever can't see you peeks, after a moment
    assert "if (S.defusing && !S.heard) heard();" in JS
    assert "if (!f.dead && f.swing !== 'done' && !seesMe(f)) swing(f, 0.25 + Math.random() * 0.45);" in JS
    # the killer goes to failRep; the replay from his eyes, skippable, paused like a rep
    assert "failRep(null, f); break;" in JS and "if (killer && opt.replay && AI) startReplay(killer, onSpike);" in JS
    assert "if (S.phase === 'replay' && S.rp) { replayCam(); return; }" in JS
    assert "['run', 'count', 'watch', 'between', 'replay'].includes(S.phase)" in JS
    assert "if (S.phase === 'replay') endReplay();" in JS
    assert "const dead = f.dead && !(replay && S.t < f.dead.t);" in JS
    tpl = (ROOT / "nexus/web/templates/drill_view.html").read_text()
    assert tpl.index("drillai.js") < tpl.index("drill.js") and 'id="dr-o-replay"' in tpl
    assert JS.count("const dead = f.dead") == 1


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("His view", "he had you for", "you were moving", "you never saw him", "he saw you first",
              "you were on the spike", "you were reloading", "Killed on the spike", "skip",
              "After a lost duel: his view (a few seconds)"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 72)
    assert "## 4.72" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
