"""4.59.1: the spot card and the suggestions box put everything into the page escaped (code scanning)."""
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_escaped():
    aj = (ROOT / "nexus/web/static/aim_maps.js").read_text()
    assert "`${k} <span" not in aj and 'value="${k}"' not in aj and 'value="${n}"' not in aj
    assert "`${esc(k)} <span translate=\"no\">${esc(n)}</span>`" in aj
    assert 'name="am-foes" value="${esc(String(n))}"' in aj and "${esc(String(+it.deaths))}×" in aj


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 59, 1)
    assert "## 4.59.1" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
