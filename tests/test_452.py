"""4.50.2: doors that are open in the game drawn see-through in the 3D maps.

The layouts have the doors closed, but most are open when a round starts: a thin slab standing in a walkable
passage (the navigation mesh runs through it and on both sides) is drawn like glass and doesn't block the view."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from test_web import synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.stats import mapmesh as mm  # noqa: E402

ROOT = Path(__file__).parent.parent


def _slab(x0, x1, y0, y1, z0, z1):
    pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7),
             (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return np.array(pts, float), np.array(faces)


def _mesh(*parts):
    P, T = [], []
    for p, t in parts:
        T.append(t + sum(len(x) for x in P))
        P.append(p)
    return gf.Mesh(points=np.concatenate(P), tris=np.concatenate(T), materials=[])


def _nav(x0=0, x1=1000, z=0.0):
    a, b, c, d = (x0, 0, z), (x1, 0, z), (x1, 1000, z), (x0, 1000, z)
    return np.array([[a, b, c], [a, c, d], [a, a, b]], float)          # and an upright (empty) one


def at(x, y, z=0.0, turn=0.0):
    W = np.eye(4)
    c, s_ = math.cos(turn), math.sin(turn)
    W[:3, :3] = [[c, -s_, 0], [s_, c, 0], [0, 0, 1]]
    W[:3, 3] = (x, y, z)
    return W


def test_doors_in_a_passage_are_open():
    door = _mesh(_slab(-7.5, 7.5, -75, 75, 0, 250))                       # 15 cm thick, 1.5 m wide, 2.5 m high
    d = mm.Doorways(_nav())
    assert d.is_open(door, at(500, 500))
    assert d.is_open(door, at(500, 500, turn=math.pi / 2))                # turned: the same
    assert not d.is_open(door, at(500, 500, 120))                         # a window: above the floor
    assert not mm.Doorways(_nav(0, 480)).is_open(door, at(500, 500))      # floor on one side only: on a wall
    assert not mm.Doorways(_nav(0, 1000, z=400)).is_open(door, at(500, 500))   # the floor is elsewhere
    thick = _mesh(_slab(-25, 25, -75, 75, 0, 250))
    assert not d.is_open(thick, at(500, 500))                             # a wall
    low = _mesh(_slab(-7.5, 7.5, -75, 75, 0, 110))
    assert not d.is_open(low, at(500, 500))                               # cover, not a door
    frame = _mesh(_slab(-7.5, 7.5, -75, -60, 0, 250), _slab(-7.5, 7.5, 60, 75, 0, 250),
                  _slab(-7.5, 7.5, -75, 75, 235, 250))
    assert not d.is_open(frame, at(500, 500))                             # a frame: the passage goes through it
    assert not mm.Doorways(np.zeros((0, 3, 3))).is_open(door, at(500, 500))


def test_build_draws_open_doors_like_glass(tmp_path, synthetic):  # noqa: F811
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from test_448 import box, placed, usd_mesh, write_game
    from nexus.maps import MapRegistry
    root = tmp_path / "game"
    write_game(root)
    c = root / "Export" / "ShooterGame" / "Content"
    usd_mesh(c / "Environment" / "Test" / "Door_0_125w250h.usda", "Door_0_125w250h", *box((-8, -60, 0), (8, 60, 250)))
    art = c / "Maps" / "Testmap" / "Testmap_Art.usda"
    text = art.read_text()
    art.write_text(text[:text.rstrip().rfind("}")] + placed("Door_0", "../../Environment/Test/Door_0_125w250h.usda",
                                                            t=(-3000, 2000, 0)) + "}\n")
    mi = MapRegistry(synthetic["cache"]).get(name="Testmap")
    said = []
    meta, blob, vox = mm.build(gf.GameFiles(root), mi, "Testmap", log=said.append)
    assert meta["version"] == mm.VERSION == 5
    assert any("doors open in the game" in x for x in said), said
    head = mm.unpack_head(blob)
    assert head["gnt"] >= 24                                              # the window and the door: glass


def test_version():
    import nexus
    assert nexus.__version__ == "4.50.2"
    assert "## 4.50.2" in (ROOT / "CHANGELOG.md").read_text()
