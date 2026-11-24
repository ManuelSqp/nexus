"""4.61.1: code scanning: match ids never become paths; the spot card escapes what it shows."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from nexus.safepath import UnsafePath
from nexus.stats import drills as dr
from nexus.web.replays import match_brief, match_file

ROOT = Path(__file__).parent.parent
MID = "12b3659c-735e-432a-8f55-91425f8934df"


def test_match_file_takes_ids_only(tmp_path):
    store = SimpleNamespace(data_dir=tmp_path)
    assert match_file(store, MID.upper()) == (tmp_path / "cache" / "matches" / f"{MID}.json").resolve()
    for bad in ("../../etc/passwd", "a/b", "", "x" * 65, "..", "a.json"):
        with pytest.raises(UnsafePath):
            match_file(store, bad)
        assert match_brief(store, bad) is None


def test_drills_cache_takes_ids_only(tmp_path):
    dr.write_cached(tmp_path, MID, "sig", {"p#1": []}, [], "Ascent")
    assert dr.read_cached(tmp_path, MID, "sig") == {"p#1": []}
    assert (tmp_path / "drills" / f"{MID}.json").is_file()
    assert dr.read_cached(tmp_path, "../" + MID, "sig") is None
    with pytest.raises(ValueError):
        dr.write_cached(tmp_path, "../evil", "sig", {})
    assert not (tmp_path / "evil.json").exists()


def test_spot_card_escaped():
    js = (ROOT / "nexus/web/static/aim_maps.js").read_text()
    card = js[js.index("function spotCard()"):js.index("function", js.index("function spotCard()") + 20)]
    assert "const reps = Math.round(+g.reps[tab]) || C.reps[tab];" in card
    assert "· ${esc(String(reps))} " in card and 'data-style="${esc(k)}"' in card
    assert "${esc(T('Fought over'))} ${esc(String(+s.count))}" in card
    assert "${s.hides.length}" not in card and "${T(" not in card.replace("${T('Defenders won')}", "")


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 61, 1)
    assert "## 4.61.1" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
