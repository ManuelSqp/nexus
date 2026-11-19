"""4.53.2: the maps from the game's files stay up while they're built again (a new version), and a map that's still
being built isn't replaced by the one from the replays."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_448 import _game_app, write_game  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import mapmesh as mm  # noqa: E402

ROOT = Path(__file__).parent.parent


def test_an_older_build_is_shown_until_the_new_one(app, synthetic):  # noqa: F811
    b = _game_app(app, synthetic)
    out = Path(app.extensions["nexus"]["store"].data_dir) / "maps3d"
    f = mm.paths(out, "Testmap")["meta"]
    meta = json.loads(f.read_text())
    meta["version"] = mm.VERSION - 1                              # built by the version before
    f.write_text(json.dumps(meta))
    assert mm.load_meta(out, "Testmap") is None                  # so it's built again …
    assert mm.load_meta(out, "Testmap", any_version=True)["cells"]
    assert b.needs(type("M", (), {"name": "Testmap"})())
    c = setup_admin(app)
    add_profile(c)
    d = c.get("/api/maps3d/Testmap").get_json()
    assert d["game"] and d["mesh"]                                # … and the pages show the older one meanwhile
    mm.paths(out, "Testmap")["bin"].unlink()
    assert mm.load_meta(out, "Testmap", any_version=True) is None   # no mesh: nothing to show


def test_waiting_for_the_map_from_the_game_files(app, synthetic):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    write_game(Path(store.data_dir) / "game")
    b = app.extensions["nexus"]["game"]
    b.last = 10 ** 12                                              # no background build in the test
    c = setup_admin(app)
    add_profile(c)
    assert b.pending("Testmap")
    r = c.get("/api/maps3d/Testmap")
    assert r.status_code == 202 and r.get_json()["building"] and "game's files" in r.get_json()["error"]
    b.status["Testmap"] = "error: ValueError: x"                  # it can't be built: the one from the replays
    assert not b.pending("Testmap")
    assert c.get("/api/maps3d/Testmap").status_code in (200, 404)
    assert not b.pending("Nomap")                                  # not in the export at all
    js = (ROOT / "nexus/web/static/map3d.js").read_text()
    assert "if (d.building)" in js and "setTimeout(() => load(name), 15000)" in js


def test_site_frames_and_spawn_barriers_left_out():
    for ref in ("../../Environment/Triad/Asset/Props/BombsiteMarker/0/BombsiteMarker_0_BombsiteC.usda",
                "../../Environment/Triad/Asset/Props/BombsiteMarker/0/BombsiteMarker_0_BombsiteC_Glow.usda",
                "../../Environment/Ascent/Asset/Props/BombsiteMarker/0/BombsiteMarker_0_BombsiteB.usda",
                "../../VFX/Barrier/Meshes/SM_Barrier.usda", "../../VFX/Barrier/Meshes/SM_Barrier_Back_VisionBlocker.usda"):
        assert mm.TECH.search(ref), ref
    assert not mm.TECH.search("../../Environment/Asset/Props/Gameplay/1/Gameplay_1_ArmorPlateGarage.usda")   # a wall
    assert mm.VERSION == 8


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 53)
    assert "## 4.53.2" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
