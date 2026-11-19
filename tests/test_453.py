"""4.53: the walkable floors of maps built from the game's files come from the files alone: the navigation mesh
without what's inside objects, plus the geometry's own floors a player can get onto (box tops, bridges)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_448 import write_game  # noqa: E402
from test_web import synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.maps import MapRegistry  # noqa: E402
from nexus.stats import mapmesh as mm  # noqa: E402
from nexus.stats.map3d import CELL, Frame  # noqa: E402

ROOT = Path(__file__).parent.parent


@pytest.fixture()
def built(tmp_path, synthetic):  # noqa: F811
    write_game(tmp_path / "game")
    mi = MapRegistry(synthetic["cache"]).get(name="Testmap")
    said = []
    meta, blob, vox = mm.build(gf.GameFiles(tmp_path / "game"), mi, "Testmap", log=said.append)
    floors = {}
    for i, j, h, _k in meta["cells"]:
        floors.setdefault((i, j), []).append(h)
    fr = Frame(mi)

    def at(x, y):                         # world cm -> the floors of that cell
        a, b = fr.to_m(x, y)
        return floors.get((int(a // CELL), int(b // CELL)), [])
    return meta, at, said


def test_floors_from_the_game_files(built):
    meta, at, said = built
    assert any(abs(h) < 0.05 for h in at(-5000, -4500))                    # the open floor
    top = at(-3950, -1050)                                                  # the 1 m crate: you stand on it
    assert top and all(abs(h - 1.0) < 0.05 for h in top)
    assert not any(abs(h) < 0.5 for h in at(-3550, -1050))                  # the 2 m crate: not through it ...
    assert not any(abs(h - 2.0) < 0.3 for h in at(-3550, -1050))            # ... nor onto it (too high to get up)
    assert not any(abs(h - 4.0) < 0.5 for h in at(-950, 0))                 # not on top of the 4 m wall
    assert meta["geo_cells"] >= 4 and meta["foot_cm"] is None and "samples_from" not in meta
    assert any("inside objects left out" in x for x in said) and any("from the geometry" in x for x in said)


def test_merge_floors_reachable_only():
    nav = {(i, j): [0.0] for i in range(0, 20) for j in range(0, 10)}
    geo = {}
    for i in range(4, 8):                                # a box 1 m high (2 m wide): up from the floor beside it
        for j in range(2, 6):
            geo[(i, j)] = [1.0]
    for i in range(10, 13):                              # stairs (0.4 m steps) up to a bridge at 2.4 m over the floor
        for j in range(2, 5):
            geo[(i, j)] = [0.4 * (i - 9)]
    for i in range(13, 18):
        for j in range(2, 5):
            geo[(i, j)] = [2.4]
    for i in range(0, 4):                                # a roof at 5 m: nothing leads up there
        for j in range(7, 10):
            geo[(i, j)] = [5.0]
    for i in range(14, 19):                              # a strip (railing, wall top) half a metre wide
        geo[(i, 8)] = [0.9]
    cells, floors, added = mm.merge_floors(nav, geo)
    assert floors[(5, 3)] == [1.0]                       # the box's top replaces the floor below it
    assert floors[(15, 3)] == [0.0, 2.4]                 # under the bridge and on it
    assert floors[(1, 8)] == [0.0]                       # no roof
    assert floors[(16, 8)] == [0.0]                      # no strip
    assert added == 5 * 3 and len(cells) == sum(len(v) for v in floors.values())
    far = {(60, 60): [0.0], (60, 61): [0.0], (61, 60): [0.0], (61, 61): [0.0]}
    assert mm.merge_floors(nav, far)[2] == 0             # too far from the navigation mesh
    assert mm.merge_floors({}, geo) == ([], {}, 0)


def test_inside_a_tall_box():
    g = np.zeros((40, 40, 40), bool)                     # a box 2.5 m wide and 3 m high: only its surfaces
    g[0:13, 10:20, 10] = g[0:13, 10:20, 19] = True
    g[0:13, 10, 10:20] = g[0:13, 19, 10:20] = True
    g[12, 10:20, 10:20] = True
    g[0:13, 30, 0:40] = g[0:13, 36, 0:40] = True         # a corridor 1.5 m wide (walls along x) with a roof
    g[12, 30:37, 0:40] = True
    vox = {"origin": [0.0, 0.0, 0.0], "cell": 0.25, "shape": [40, 40, 40], "bits": np.packbits(g.reshape(-1))}
    I, J, H = np.array([7, 7, 2]), np.array([7, 16, 30]), np.zeros(3)
    assert mm.enclosed(I, J, H, vox).tolist() == [True, False, False]   # in the box; the open floor; the corridor


def test_headroom_and_inside_objects():
    g = np.zeros((40, 20, 20), bool)                     # (y, z, x): a 0.25 m grid from 0, 0, 0
    g[8, 4:12, 4:12] = True                              # a lid 2 m up over x/z 1..3 m
    g[4, 14:18, 14:18] = True                            # a box top 1 m up over x/z 3.5..4.5 m
    vox = {"origin": [0.0, 0.0, 0.0], "cell": 0.25, "shape": [20, 40, 20], "bits": np.packbits(g.reshape(-1))}
    I, J = np.array([4, 4, 8, 8, 30]), np.array([4, 4, 8, 8, 30])
    H = np.array([0.0, 2.0, 0.0, 1.0, 0.0])
    assert mm.headroom(I, J, H, vox).tolist() == [True, True, False, True, True]   # outside the grid: free
    fl = mm.inside_objects({(4, 4): [0.0], (8, 8): [0.0, 1.0]}, vox)
    assert fl == {(4, 4): [0.0], (8, 8): [1.0]}           # under the box: left out


def test_built_from_files_alone(tmp_path, synthetic):  # noqa: F811
    import inspect

    from nexus.web.gamebuild import GameBuilder
    assert "samples" not in inspect.signature(mm.build).parameters
    assert "n_replays" not in inspect.signature(GameBuilder.needs).parameters
    assert not hasattr(GameBuilder, "samples") and not hasattr(mm, "foot_cm")


def test_version():
    import nexus
    assert nexus.__version__ == "4.53.0" and mm.VERSION == 6
    assert "## 4.53.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version 4.53.0**" in (ROOT / "README.md").read_text()
