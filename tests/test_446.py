"""4.46: smokes and other utility as 3D objects (hidden by walls, agent colours), the map in one colour with a
switch for measured / guessed floors and the old map areas."""
import re
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).parent.parent / "nexus" / "web" / "static"
TEMPLATES = Path(__file__).parent.parent / "nexus" / "web" / "templates"


def test_3d_utility_pass():
    js = (STATIC / "map3d.js").read_text()
    assert "function drawObjects(list)" in js and "if (layer && layer.objects) drawObjects(layer.objects());" in js
    assert "gl.depthMask(false)" in js and "gl.frontFace(gl.CW)" in js and "gl.cullFace(inside ? gl.FRONT : gl.BACK)" in js
    ovs = re.search(r"const OVS = `(.*?)`;", js, re.S).group(1)
    ofs = re.search(r"const OFS = `(.*?)`;", js, re.S).group(1)
    shared = set(re.findall(r"uniform \w+ (\w+);", ovs)) & set(re.findall(r"uniform (?:\w+ )?\w+ (\w+);", ofs))
    assert not shared, f"a uniform in both shaders needs the same precision: {shared}"     # the 4.46 bug: nothing drawn
    assert "getProgramParameter(oprog, gl.LINK_STATUS)" in js


def test_smoke_colours_per_agent():
    js = (STATIC / "replay.js").read_text() + (STATIC / "motion.js").read_text()   # 4.51: shared code in motion.js
    for agent in ("miks", "clove", "omen", "viper", "astra", "harbor", "brimstone"):
        assert f"{agent}: [" in js, agent
    assert "smonk: [" in js and "wraith: [" in js                       # their codenames in the replay file
    assert "objects, ready" in js and "function objects()" in js


def test_floor_colour_switch():
    js = (STATIC / "map3d.js").read_text()
    assert "colors: 'one'" in js and "function recolor(mode)" in js and "l.e ? GUESSED : KNOWN" in js
    assert "const [i, j, h, k, e] of d.cells" in js
    for t in ("maps3d.html", "replay_view.html"):
        html = (TEMPLATES / t).read_text()
        assert 'id="m3-colors"' in html and 'value="known"' in html and 'value="areas"' in html, t


@pytest.mark.skipif(subprocess.run(["which", "node"], capture_output=True).returncode != 0, reason="node missing")
def test_scripts_parse():
    for f in ("map3d.js", "replay.js"):
        assert subprocess.run(["node", "--check", str(STATIC / f)], capture_output=True).returncode == 0, f
