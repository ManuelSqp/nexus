"""4.70.1: drill shots: the wall you see decides (not only the 0.5 m see-through grid); your team's flashes, stuns,
recon and traps aren't drawn as balls."""
from pathlib import Path

ROOT = Path(__file__).parent.parent
JS = (ROOT / "nexus/web/static/drill.js").read_text()
M3 = (ROOT / "nexus/web/static/map3d.js").read_text()


def test_shot_checks_the_drawn_wall():
    assert "function wallAlong(o, d)" in M3 and "visible, wallAlong, roofAt, zoneAt," in M3
    assert "gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);" in M3 and "gl.bindFramebuffer(gl.FRAMEBUFFER, null);" in M3
    assert "for (const [k, cap] of [['depth', gl.DEPTH_TEST]" in M3                    # its GL state put back
    i = JS.index("function shoot()")
    shot = JS[i:JS.index("function startReload()", i)]
    # the grid first (cheap); only when it says blocked, the drawn map along the shot
    assert shot.index("V().visible(o, add(o, d, Math.max(0, hit[2] - 0.05)))") < shot.index("V().wallAlong(o, d)")
    assert "if (wall === null || wall < hit[2] - 0.02) hit = null;" in shot


def test_team_point_utility_not_drawn():
    assert "const AREA_UTIL = new Set(['smoke', 'wall', 'damage', 'slow']);" in JS
    assert "const list = utilList().filter(u => !u.team || AREA_UTIL.has(u.type));" in JS


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 70, 1)
    assert "## 4.70.1" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
