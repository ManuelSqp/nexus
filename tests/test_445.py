"""4.45: the 3D map's gaps filled from the minimap, maps without replays (flat), and the utility shapes."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import map3d as m3  # noqa: E402

STATIC = Path(__file__).parent.parent / "nexus" / "web" / "static"


def _minimap(path: Path, w: int = 200) -> Path:
    """Transparent outside, light floor, a darker box in the middle, a light corridor to the right."""
    import cv2
    img = np.zeros((w, w, 4), np.uint8)
    img[20:180, 20:120] = (220, 220, 220, 255)
    img[90:110, 120:190] = (220, 220, 220, 255)          # the corridor
    img[60:80, 60:80] = (80, 80, 80, 255)                # a box
    cv2.imwrite(str(path), img)
    return path


def test_mask_from_minimap(tmp_path):
    mask = m3.minimap_mask(_minimap(tmp_path / "m.png"))
    assert mask.shape == (200, 200)
    assert mask[30, 30] and mask[100, 150] and not mask[70, 70] and not mask[5, 5] and not mask[150, 150]
    (tmp_path / "x.png").write_bytes(b"not an image")
    assert m3.minimap_mask(tmp_path / "x.png") is None


def test_fill_spreads_the_known_heights(tmp_path):
    mask = m3.minimap_mask(_minimap(tmp_path / "m.png"))
    per_m = 1 / 100.0                                    # the minimap is 100 m wide: one pixel = 0.5 m = one cell
    levels = {(i, j): [2.0] for i in range(10, 50) for j in range(10, 90)}    # the replays know the left part at 2 m
    added = m3.fill_from_minimap(levels, mask, per_m)
    assert added and (95, 50) in added                   # the corridor
    assert levels[(95, 50)] == [2.0]                     # takes the height it connects to
    assert (70, 70) not in levels and (75, 50) in levels # the box stays a hole (a block in 3D), around it is floor
    assert (2, 2) not in levels                          # outside the map stays empty
    flat = {}
    m3.fill_from_minimap(flat, mask, per_m)
    assert flat and set(h for lv in flat.values() for h in lv) == {0.0}   # no replay: flat at 0


def test_map_without_replays_is_flat_from_the_minimap(app):  # noqa: F811 (fixture)
    from nexus.maps import MapRegistry
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c)
    reg = MapRegistry(Path(store.data_dir) / "cache")
    mi = reg.get(name="Testmap")
    (Path(store.data_dir) / "cache" / "minimaps").mkdir(parents=True, exist_ok=True)
    _minimap(Path(store.data_dir) / "cache" / "minimaps" / f"{mi.uuid}.png")
    page = c.get(f"/profiles/{pid}/maps3d").data.decode()
    assert "disabled" not in page.split('class="m3-maps"')[1].split("</div>")[0]       # every map can be opened
    d = c.get("/api/maps3d/Testmap").get_json()
    assert d["matches"] == 0 and d["cells"] and d["guessed"] == len(d["cells"]) and not d["no_minimap"]
    assert all(len(cell) == 5 and cell[4] == 1 and cell[2] == 0.0 for cell in d["cells"][:50])
    assert c.get("/api/maps3d/Nosuchmap").status_code == 404


def test_utility_shapes_in_the_viewer():
    js = (STATIC / "replay.js").read_text() + (STATIC / "motion.js").read_text()   # 4.51: shared code in motion.js
    assert "MIN_LIFE = 0.9" in js and "function live(u, t)" in js and "function drawUtil(" in js
    assert "u.type === 'smoke'" in js and "u.type === 'wall'" in js         # 4.46: drawn as 3D objects (test_446)
    assert "if (!live(u, t)) continue;" in js                        # the radar hides the same flickers
