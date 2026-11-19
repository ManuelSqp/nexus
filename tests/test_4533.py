"""4.53.3: the last code scanning alerts (see test_security.py for the scripts)."""
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_version():
    import nexus
    assert nexus.__version__ == "4.53.3"
    assert "## 4.53.3" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.53.3**" in (ROOT / "README.md").read_text()
