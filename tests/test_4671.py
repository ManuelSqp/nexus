"""4.67.1: the drag & drop editors on a phone: smaller tiles, swipe to scroll, hold to drag, edge scroll, tap."""
from pathlib import Path

ROOT = Path(__file__).parent.parent
TPL = (ROOT / "nexus/web/templates/team_sheet.html").read_text()


def test_phone_parts():
    assert "@media(max-width:600px)" in TPL and "minmax(72px,1fr)" in TPL and "#ie{scroll-margin-top:80px}" in TPL
    assert TPL.count("if (drag.pan) { window.scrollBy(0, drag.ly - e.clientY); drag.ly = e.clientY; return; }") == 2
    assert TPL.count("performance.now() - drag.t0 < 300") == 2                    # both editors: hold to drag
    assert "function edgeScroll(y)" in TPL and TPL.count("edgeScroll(null);") == 2
    assert "// 4.67.1: a tap: into the pool" in TPL


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 67, 1)
    assert "## 4.67.1" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
