"""4.56.1: smokes are solid in the drills; someone behind a smoke isn't drawn."""
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


def test_solid_smokes():
    dj = (STATIC / "drill.js").read_text()
    assert "SOLID_A = 1.8" in dj
    assert ".map(o => (o.block ? {...o, a: SOLID_A} : o))" in dj
    assert "function smoked(f)" in dj and "if (!f.url || hiding(f) || smoked(f)) continue;" in dj
    assert "throughSmoke(eye(), hd[1]) && (!chest || throughSmoke(eye(), chest[2]))" in dj
    # the replay viewer keeps them see-through
    assert "SOLID_A" not in (STATIC / "replay.js").read_text()


def test_version():
    import nexus
    assert nexus.__version__ == "4.56.1"
    assert "## 4.56.1" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.56.1**" in (ROOT / "README.md").read_text()
