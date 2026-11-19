"""4.53.1: Haven's missing floors (objects left out as clutter by a word inside their name), the glowing border round
the spike sites, and floors behind thin walls."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from nexus.stats import mapmesh as mm  # noqa: E402

ROOT = Path(__file__).parent.parent


def test_clutter_by_words():
    keep = [("Floor_8_BirdHouseB.usda", 2100), ("Shell_8_BirdHouseLongA.usda", 2900), ("Roof_6_BirdHouseLongA.usda", 3268),
            ("Stairs_4_BirdHouse.usda", 800), ("Brick_0_GardenPlanter.usda", 300),
            ("ROOK_Shell_MapUpdate2026_DefPathA_Ext_CastleWallCUpper.usda", 1973),
            ("Shell_9_DefSpawnGateBuildingPlantersA.usda", 1891), ("Floor_1_CemeteryGrass.usda", 3446),
            ("Shell_9_ASitePrimaryTowerScaffolding.usda", 11542), ("AScaffold_10_PlatformBaseB.usda", 2094),
            ("Conduit_2_PipeStraight.usda", 2484), ("Crate.usda", 100), ("Tower.usda", 1000)]
    out = [("Foliage_5_ShrubberyWeedsClump.usda", 200), ("Plant_0_GroundLeavesB.usda", 300), ("Pot_1_PlantB.usda", 80),
           ("Ascent_0_LightLeakGeo.usda", 14004), ("Shell_0_ASiteShipDecalA.usda", 5709), ("TelephonePole_7_WireB.usda", 1998),
           ("StreetLamp.usda", 400), ("Cloud_0_ShadowBlocker.usda", 25031),
           ("PLUM_Shell_Garden_AMain_Gate01LightStrips.usda", 3360), ("Zipline_0_ZipRopeB.usda", 7919)]
    for name, size in keep:
        assert not mm.clutter(name, size), name
    for name, size in out:
        assert mm.clutter(name, size), name
    assert mm._words("Floor_8_BirdHouseB.usda") == ["floor", "bird", "house", "b"]


def test_spike_site_border_left_out():
    assert mm.TECH.search("../../Characters/Rift/S0/VFX/X/Rift_Bombsite_wall.usda")
    assert mm.TECH.search("../../Characters/Rift/S0/VFX/X/Rift_Bombsite_plane.usda")
    assert not mm.TECH.search("../../VFX/Meshes/SM_Bonsai_Sewer_VertexColors.usda")     # Split's sewer water: a floor


def test_no_floor_behind_a_thin_wall():
    nav = {(i, j): [0.0] for i in range(0, 6) for j in range(0, 8)}
    geo = {(i, j): [0.0] for i in range(6, 12) for j in range(0, 8)}      # floor beyond the navigation mesh
    g = np.zeros((20, 20, 30), bool)                                     # (y, z, x), 0.25 m: a wall at x = 3 m
    g[:, :, 12] = True
    vox = {"origin": [0.0, -1.0, 0.0], "cell": 0.25, "shape": [30, 20, 20], "bits": np.packbits(g.reshape(-1))}
    _, fl, _ = mm.merge_floors(nav, geo)
    assert (8, 3) in fl                                                  # without the wall: one floor
    _, fl, _ = mm.merge_floors(nav, geo, vox=vox)
    assert (8, 3) not in fl and (5, 3) in fl                             # the wall stops it
    p = mm._passable(vox)
    assert p(4, 3, 5, 3, 0.0) and not p(5, 3, 6, 3, 0.0)


def test_version():
    import nexus
    assert nexus.__version__ == "4.53.1" and mm.VERSION == 7
    assert "## 4.53.1" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.53.1**" in (ROOT / "README.md").read_text()
    assert json.loads((ROOT / "nexus/i18n/de.json").read_text())
