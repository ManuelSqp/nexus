"""4.70.2: glass boxes (crates) are solid in maps built from the game's files: drawn opaque, they block sight, shots
and the way; thin glass (windows, doors, railings, glass floors) stays see-through."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from test_448 import box, write_game  # noqa: E402
from test_453 import _with_glass_crate  # noqa: E402
from test_web import synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.maps import MapRegistry  # noqa: E402
from nexus.stats import mapmesh as mm  # noqa: E402
from nexus.stats import sight as sg  # noqa: E402
from nexus.stats.map3d import Frame  # noqa: E402


def _mesh(lo, hi):
    pts, faces = box(lo, hi)
    tris = [(f[0], f[k], f[k + 1]) for f in faces for k in (1, 2)]
    return gf.Mesh(np.asarray(pts, float), np.asarray(tris, np.int64))


def test_glass_box_rule():
    eye = np.eye(4)
    assert mm.glass_box(_mesh((-100, -100, 0), (100, 100, 120)), eye)            # Abyss's crate
    assert not mm.glass_box(_mesh((0, 0, 0), (10, 200, 200)), eye)              # a window pane
    assert not mm.glass_box(_mesh((0, 0, 0), (600, 600, 300)), eye)             # a glass room
    assert not mm.glass_box(_mesh((0, 0, 0), (800, 100, 5)), eye)               # a glass floor or bridge
    big = np.diag([3.0, 3.0, 3.0, 1.0])
    assert not mm.glass_box(_mesh((-100, -100, 0), (100, 100, 120)), big)        # scaled up past 4 m: not a box
    assert not mm.glass_box(None, eye) and mm.VERSION >= 9


def test_built_map(tmp_path, synthetic):  # noqa: F811
    write_game(tmp_path / "game")
    _with_glass_crate(tmp_path / "game")
    mi = MapRegistry(synthetic["cache"]).get(name="Testmap")
    said = []
    meta, blob, vox = mm.build(gf.GameFiles(tmp_path / "game"), mi, "Testmap", log=said.append)
    assert any("1 glass boxes made solid" in x for x in said)
    fr = Frame(mi)
    s = sg.Sight(vox)

    def at(x, y, h=0.8):
        a, b = fr.to_m(x, y)
        return [a, h, b]
    assert not s.clear(np.array([at(0, 2600)]), np.array([at(0, 3400)]))[0]     # through the crate: blocked now
    assert s.clear(np.array([at(0, 2600, 2.0)]), np.array([at(0, 3400, 2.0)]))[0]   # over it: clear
    assert s.clear(np.array([at(1800, 50, 1.5)]), np.array([at(2300, 50, 1.5)]))[0]  # the window: still see-through
