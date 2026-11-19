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


# ------------------------------------------------------------------------------------------------ living again
def _view(pos: dict, kills: list, deaths=(), casts=(), keys=None, end=40.0):
    from types import SimpleNamespace

    from nexus.stats.replayview import Ctx as ReplayView
    v = object.__new__(ReplayView)
    rnd = SimpleNamespace(kills=[SimpleNamespace(victim=p, t_round_ms=int(t * 1000)) for p, t in kills])
    v.match = SimpleNamespace(rounds=[rnd], players={"clove": None, "jett": None})
    v.offsets = {0: 100_000}
    v.data = {"pos": pos, "deaths": [[100_000 + int(t * 1000), "", p] for p, t in deaths]}
    v._lives, v._casts, v._keys = {}, {0: [[int(t * 1000), p, s] for t, p, s in casts]}, keys or {}
    v.round_end_s = lambda idx: end
    return v


def _walk(t0, t1, x0=0.0, dx=0.0, every=0.25):
    out, t = [], t0
    while t <= t1 + 1e-9:
        out.append([100_000 + int(t * 1000), x0 + dx * (t - t0), 0.0, 0.0, 0.0])
        t += every
    return out


def test_lives_clove_ult_and_plain_deaths():
    # Clove dies at 10 s, lies there 1.5 s, is back (her ult) and walks off until the round ends; Jett dies at 20 s
    clove = _walk(0, 10.2, 0, 100) + _walk(10.4, 11.5, 1020, 0) + _walk(11.75, 40, 1020, 300)
    jett = _walk(0, 20.3, 0, 50)
    v = _view({"Clove": clove, "Jett": jett}, [("clove", 10.0), ("jett", 20.0)])
    lv = v.lives(0)
    assert lv["jett"] == [[-1.0, 20.0]]
    assert lv["clove"][0] == [-1.0, 10.0] and lv["clove"][1][1] == 40.0 and 11.5 < lv["clove"][1][0] < 12.5
    # her ult cast says exactly when
    v = _view({"Clove": clove, "Jett": jett}, [("clove", 10.0)], casts=[(11.2, "clove", 3)], keys={3: "X"})
    assert v.lives(0)["clove"][1][0] == 11.2
    # parked while dead, then back (Sage's resurrection): a pause in the positions, then he's there again
    sage = _walk(0, 10.3, 0, 0) + _walk(16, 40, 0, 0)
    v = _view({"Clove": sage}, [("clove", 10.0)])
    assert v.lives(0)["clove"] == [[-1.0, 10.0], [16.0, 40.0]]
    # back, then dead for good when the ult runs out (the replay's own death, no kill in the match data)
    v = _view({"Clove": _walk(0, 10.2, 0, 100) + _walk(12, 20.2, 2000, 300)}, [("clove", 10.0)], deaths=[("Clove", 20.0)])
    assert v.lives(0)["clove"] == [[-1.0, 10.0], [12.0, 20.0]]
    # a body that just lies there isn't alive again
    v = _view({"Clove": _walk(0, 10.0, 0, 100) + _walk(10.25, 14, 1000, 0)}, [("clove", 10.0)])
    assert v.lives(0)["clove"] == [[-1.0, 10.0]]


def test_replay_viewer_knows_lives():
    js = (ROOT / "nexus/web/static/replay.js").read_text()
    for x in ("const livesOf = i =>", "function aliveAt(i, t)", "function lastAlive(i, t)", "const deathOf = (i, t) =>",
              "lastAlive(S.follow, S.t)", "!aliveAt(+i, S.t)"):
        assert x in js, x
    assert "S.t > deadAt" not in js and "t > deadAt" not in js
