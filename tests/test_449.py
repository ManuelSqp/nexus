"""4.49: the replay viewer controlled like the game's replays, and glass per face in the maps from the game's files."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import UID, _replay  # noqa: E402
from test_448 import box, usd_mesh  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.stats import mapmesh as mm  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


def _with_subsets(path: Path, glass_faces: list[int]) -> None:
    """A box whose listed faces are bound to a glass material (GeomSubsets, as FModel writes them)."""
    pts, faces = box((0, 0, 0), (500, 400, 300))
    usd_mesh(path, "Kiosk", pts, faces)
    text = path.read_text()
    other = [i for i in range(len(faces)) if i not in glass_faces]
    subsets = ''.join(
        f'    def GeomSubset "Section_{n}" (\n        prepend apiSchemas = ["MaterialBindingAPI"]\n    )\n    {{\n'
        f'        uniform token elementType = "face"\n        uniform token familyName = "materialBind"\n'
        f'        int[] indices = [{", ".join(map(str, idx))}]\n'
        f'        rel material:binding = </Kiosk/Materials/{mat}>\n    }}\n'
        for n, (idx, mat) in enumerate([(other, "Kiosk_Concrete_MI"), (glass_faces, "Window_Glass_MI")]))
    text = text.replace('    def Scope "Materials"', subsets + '    def Scope "Materials"')
    text = text.replace("    {\n    }\n}", '    {\n        def Material "Kiosk_Concrete_MI"\n        {\n        }\n'
                                            '        def Material "Window_Glass_MI"\n        {\n        }\n    }\n}')
    path.write_text(text)


def test_glass_per_face(tmp_path):
    f = tmp_path / "Kiosk.usda"
    _with_subsets(f, [3])                                # one side of six is a window
    m = gf.read_mesh(f)
    assert m.glass and int(m.glass_tris.sum()) == 2      # its two triangles, not the whole kiosk
    solid, glass = m.split()
    assert len(solid.tris) == 10 and len(glass.tris) == 2
    plain = tmp_path / "Plain.usda"
    usd_mesh(plain, "Plain", *box((0, 0, 0), (100, 100, 100)))
    p = gf.read_mesh(plain)
    assert not p.glass and p.split() == (p, None)
    whole = tmp_path / "Pane.usda"
    usd_mesh(whole, "Pane", *box((0, 0, 0), (10, 200, 200)), materials=["M_Glass_Clear"])
    g = gf.read_mesh(whole)
    assert g.glass and g.glass_tris.all()                # one material, glass: all of it
    assert mm.VERSION >= 4                               # the maps are built again


def test_replay_page_layout(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/replay/{UID}").data.decode()
    for s in ('id="rv"', 'id="rv-report"', 'data-tab="round"', 'data-tab="deaths"', 'data-tab="utility"',
              'data-tab="review"', 'data-mode="player"', 'data-mode="free"', 'id="rv-tl"', 'id="rv-marks"',
              'id="rv-ours"', 'id="rv-theirs"', 'id="rv-s-ours"', 'id="rv-hint"', 'Utility check', 'Combat Report'):
        assert s in page, s
    assert "Click to fly around" not in page and 'data-cam=' not in page


def test_replay_controls_like_the_game():
    js = (STATIC / "replay.js").read_text()
    for s in ("c === 'Space'", "c === 'KeyV'", "c === 'KeyT'", "c === 'KeyN'", "/^Digit[0-9]$/", "'KeyE', 'KeyQ'",
              "function fly(dt)", "function cycle(dir)", "e.button === 3 || e.button === 4", "function showSight(n)",
              "function marks()", "key !== 'X'", "function setReport(on)", "function setUi(on)"):
        assert s in js, s
    m3 = (STATIC / "map3d.js").read_text()
    assert "const OWN = !C.replay" in m3 and "if (OWN && M && document.pointerLockElement !== canvas)" in m3
    assert "if (OWN) canvas.addEventListener('touchstart'" in m3


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Combat Report", "Free camera", "Player view", "Show the sightline", "no line of sight", "Outlines",
              "You didn't die in this round.", "T · show the controls"):
        assert k in de and "ß" not in de[k], k
