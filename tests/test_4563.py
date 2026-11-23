"""4.56.3: the replay viewer's Outlines (players behind walls) never show in a drill."""
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


def test_no_outlines_in_drills():
    js = (STATIC / "map3d.js").read_text()
    assert "const NO_XRAY = !!(C && C.drill);" in js
    assert "if (opt.xray && !NO_XRAY) {" in js and "if (opt.xray) {" not in js
    # the drills' boot has "drill", the replay viewer's doesn't
    assert '"drill": d,' in (ROOT / "nexus/web/drills.py").read_text()
    assert '"drill": {"id": did,' in (ROOT / "nexus/web/drills.py").read_text()


def test_version():
    import nexus
    assert nexus.__version__ == "4.56.3"
    assert "## 4.56.3" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.56.3**" in (ROOT / "README.md").read_text()
