"""4.48: maps and agents from the game's files (USD export), line of sight and the death review.

The game's files can't be in the tests: a tiny map is written here in the same format (a layout with sublevels, a
wall, crates placed by an instancer, glass, a navigation mesh, a callout zone; an agent with a skeleton)."""
import gzip
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import UID, _replay  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.maps import MapRegistry  # noqa: E402
from nexus.stats import agentmesh as am  # noqa: E402
from nexus.stats import mapmesh as mm  # noqa: E402
from nexus.stats import sight as sg  # noqa: E402

STATIC = Path(__file__).parent.parent / "nexus" / "web" / "static"
TEMPLATES = Path(__file__).parent.parent / "nexus" / "web" / "templates"


# ------------------------------------------------------------------------------------------------ writing USD
def _fmt(v):
    return "(" + ", ".join(f"{x:g}" for x in v) + ")"


def usd_mesh(path: Path, name: str, pts, faces, extra: str = "", materials=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mats = "".join(f'        def Material "{m}"\n        {{\n        }}\n' for m in materials)
    path.write_text(
        f'#usda 1.0\n(\n    defaultPrim = "{name}"\n    metersPerUnit = 0.01\n    upAxis = "Z"\n)\n\ndef Mesh "{name}"\n{{\n'
        f'    int[] faceVertexCounts = [{", ".join(str(len(f)) for f in faces)}]\n'
        f'    int[] faceVertexIndices = [{", ".join(str(i) for f in faces for i in f)}]\n'
        f'    point3f[] points = [{", ".join(_fmt(p) for p in pts)}]\n{extra}'
        f'    def Scope "Materials"\n    {{\n{mats}    }}\n}}\n')


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return pts, faces


def xf(t=(0, 0, 0), q=(1, 0, 0, 0), s=(1, 1, 1), ind="            "):
    return (f'{ind}uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:orient", "xformOp:scale"]\n'
            f'{ind}float3 xformOp:translate = {_fmt(t)}\n{ind}quatf xformOp:orient = {_fmt(q)}\n{ind}float3 xformOp:scale = {_fmt(s)}\n')


def placed(scope: str, ref: str, t=(0, 0, 0), s=(1, 1, 1), invisible=False):
    vis = '            token visibility = "invisible"\n' if invisible else ""
    return (f'    def Scope "{scope}"\n    {{\n        def Mesh "StaticMeshComponent0" (\n'
            f'            prepend references = @{ref}@\n        )\n        {{\n{vis}{xf(t, s=s)}        }}\n    }}\n')


def layer(path: Path, name: str, body: str, sub=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    subl = f"    subLayers = [{', '.join('@./' + s + '@' for s in sub)}]\n" if sub else ""
    path.write_text(f'#usda 1.0\n(\n    defaultPrim = "{name}"\n    metersPerUnit = 0.01\n    upAxis = "Z"\n{subl})\n\n'
                    f'def Scope "{name}"\n{{\n{body}}}\n')


def write_game(root: Path) -> None:
    """Testmap's files as FModel writes them: world y negated (so the files' y = −world y)."""
    c = root / "Export" / "ShooterGame" / "Content"
    m = c / "Maps" / "Testmap"
    layer(m / "Testmap.usda", "Testmap", "", sub=["Testmap_Art.usda", "Testmap_Gameplay.usda", "Testmap_Callout_Volumes.usda",
                                                  "Testmap_Art_Vista.usda", "Testmap_BVPawn.usda"])
    # a 1 m thick wall across the map at world x -1000..-900, 4 m high; crates (an instancer); glass; a lamp (clutter)
    usd_mesh(c / "Environment" / "Test" / "Wall.usda", "Wall", *box((-1000, -3000, 0), (-900, 3000, 400)))
    usd_mesh(c / "Environment" / "Test" / "Crate.usda", "Crate", *box((0, 0, 0), (100, 100, 100)))
    usd_mesh(c / "Environment" / "Test" / "Window.usda", "Window", *box((0, 0, 0), (10, 200, 200)), materials=["M_Glass_Clear"])
    usd_mesh(c / "Environment" / "Test" / "StreetLamp.usda", "StreetLamp", *box((0, 0, 0), (100, 100, 400)))
    usd_mesh(c / "Environment" / "Test" / "Mountain.usda", "Mountain", *box((-20000, -20000, 0), (20000, 20000, 8000)))
    usd_mesh(c / "Environment" / "Test" / "Tower.usda", "Tower", *box((6500, -1000, 0), (7500, 0, 1000)))
    art = placed("Wall_0", "../../Environment/Test/Wall.usda") + placed("Window_0", "../../Environment/Test/Window.usda", t=(2000, 0, 0)) \
        + placed("StreetLamp_0", "../../Environment/Test/StreetLamp.usda", t=(3000, 3000, 0)) \
        + placed("Tower_0", "../../Environment/Test/Tower.usda")
    art += ('    def Scope "Crate_1"\n    {\n        def PointInstancer "InstancedStaticMesh"\n        {\n'
            '            rel prototypes = </Testmap_Art/Crate_1/InstancedStaticMesh/Prototypes/InstancedStaticMesh>\n'
            '            int[] protoIndices = [0, 0]\n            point3f[] positions = [(0, 0, 0), (500, 0, 0)]\n'
            '            quath[] orientations = [(1, 0, 0, 0), (0.7071, 0, 0, 0.7071)]\n'
            '            float3[] scales = [(1, 1, 1), (1, 1, 2)]\n' + xf((-4000, 1000, 0)) +
            '            def Scope "Prototypes"\n            {\n                def Mesh "InstancedStaticMesh" (\n'
            '                    prepend references = @../../Environment/Test/Crate.usda@\n                )\n'
            '                {\n                }\n            }\n        }\n    }\n')
    layer(m / "Testmap_Art.usda", "Testmap_Art", art)
    layer(m / "Testmap_Art_Vista.usda", "Testmap_Art_Vista", placed("Mountain_0", "../../Environment/Test/Mountain.usda"))
    layer(m / "Testmap_BVPawn.usda", "Testmap_BVPawn", placed("BV_0", "../../Environment/Test/Crate.usda", invisible=True))
    # the navigation mesh: flat at z 0 over the playable area
    nav = c / "Characters" / "Global" / "MapMarkup" / "TargetingMeshes" / "Testmap_NavMesh_Targeting.usda"
    usd_mesh(nav, "Testmap_NavMesh_Targeting", [(-9000, -6000, 0), (6000, -6000, 0), (6000, 6000, 0), (-9000, 6000, 0)],
             [(0, 1, 2), (0, 2, 3)])
    layer(m / "Testmap_Gameplay.usda", "Testmap_Gameplay",
          placed("Testmap_NavMesh_Targeting", "../../Characters/Global/MapMarkup/TargetingMeshes/Testmap_NavMesh_Targeting.usda"))
    # the callout zone A Site: world x -6500..-3500, y -6000..-3000 (files y 3000..6000)
    bx = c / "Blueprints" / "Utilities" / "Box_For_Volumes.usda"
    usd_mesh(bx, "Box_For_Volumes", *box((0, -100, 0), (100, 0, 100)))
    zone = ('    def Scope "CalloutRegion_A_Site"\n    {\n        def Xform "RootComponent"\n        {\n' + xf((-6500, 6000, -100)) +
            '            def Mesh "CalloutSubregion_A_Site_01" (\n                prepend references = @../../Blueprints/Utilities/Box_For_Volumes.usda@\n'
            '            )\n            {\n' + xf((0, 0, 0), s=(30, 30, 10), ind="                ") + '            }\n        }\n    }\n')
    layer(m / "Testmap_Callout_Volumes.usda", "Testmap_Callout_Volumes", zone)
    # an agent: two bones, skin weights, the files' y mirrored
    pts, faces = box((-20, -30, 0), (20, 30, 190))
    pts = pts + [(40, 0, 100)]                                   # a nose: forward is +x
    faces = faces + [(5, 6, 8)]
    n = len(pts)
    skel = ('    uniform token[] joints = ["Root", "Root/Spine"]\n'
            '    uniform matrix4d[] bindTransforms = [((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)), '
            '((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 10, 100, 1))]\n'
            f'    int[] primvars:skel:jointIndices = [{", ".join("0, 1" for _ in range(n))}] (\n        elementSize = 2\n    )\n'
            f'    float[] primvars:skel:jointWeights = [{", ".join("0.75, 0.25" for _ in range(n))}] (\n        elementSize = 2\n    )\n')
    usd_mesh(c / "Characters" / "Wushu" / "S0" / "3P" / "Models" / "TP_Wushu_S0_Skelmesh.usda", "TP_Wushu_S0_Skelmesh",
             pts, faces, extra=skel)


# ------------------------------------------------------------------------------------------------ reading
def test_layout_meshes_and_instances(tmp_path):
    write_game(tmp_path)
    files = gf.GameFiles(tmp_path)
    lay = files.layout("Testmap")
    assert lay is not None and lay.name == "Testmap.usda"
    sub, _ = gf.read_layout(lay)
    _, art = gf.read_layout(lay.parent / "Testmap_Art.usda")
    crates = [p for p in art if p.ref.endswith("Crate.usda")]
    assert len(crates) == 1 and len(crates[0].mats) == 2                        # one instancer, two crates
    m1 = crates[0].mats[1]
    assert np.allclose(m1[:3, 3], (-3500, 1000, 0)) and abs(np.linalg.det(m1[:3, :3]) - 2) < 0.01  # rotated, 2x tall
    assert not any(p.ref.endswith("Crate.usda") and p.name == "Prototypes" for p in art)
    _, zones = gf.read_layout(lay.parent / "Testmap_Callout_Volumes.usda")
    z = zones[0]
    assert z.name == "CalloutRegion_A_Site" and np.allclose(z.mats[0][:3, 3], (-6500, 6000, -100))
    assert np.allclose(np.diag(z.mats[0][:3, :3]), (30, 30, 10))               # the Xform and the box's own scale
    f = files.resolve("../../Blueprints/Utilities/Box_For_Volumes.usda", Path("/elsewhere/Maps/Testmap"))
    assert f is not None and f.name == "Box_For_Volumes.usda"                  # found below ShooterGame/Content
    w = gf.read_mesh(f)
    assert w.tris.shape == (12, 3) and w.points.max(0)[2] == 100


def test_flip_follows_the_points():
    nav = np.array([[[0, 0], [1000, 0], [1000, 1000]], [[0, 0], [1000, 1000], [0, 1000]]], float)   # files: y 0..1000
    pts = [(500, -500), (200, -800), (800, -300)]                                # world: y negative -> files mirrored
    assert mm.detect_flip(nav, pts) == "y"
    assert mm.detect_flip(nav, [(500, 500), (300, 700)]) == "none"
    assert mm.detect_flip(nav, []) == "y"                                         # nothing to go by: FModel's usual


# ------------------------------------------------------------------------------------------------ building
@pytest.fixture()
def built(tmp_path, synthetic):  # noqa: F811
    write_game(tmp_path / "game")
    mi = MapRegistry(synthetic["cache"]).get(name="Testmap")
    meta, blob, vox = mm.build(gf.GameFiles(tmp_path / "game"), mi, "Testmap")
    return mi, meta, blob, vox


def test_build_map(built):
    mi, meta, blob, vox = built
    assert meta["version"] == mm.VERSION and meta["tris"] > 20 and meta["flip"] == "y"
    assert meta["objects"] == 5                                  # wall, glass, 2 crates, tower (lamp: clutter; vista, volumes: out)
    head = mm.unpack_head(blob)
    assert blob[:4] == b"NXM1" and head["gnt"] > 0 and head["nt"] == meta["tris"]
    assert head["roof"]["w"] > 10 and head["vox"]["cell"] == mm.VOX_WEB
    hi = head["hi"]
    assert hi[1] < 15                                            # the mountain (vista) isn't in it
    z = meta["zones"][0]
    assert z["label"] == "A Site" and z["kind"] == 1             # named like valorant-api.com
    assert meta["cells"] and all(len(c) == 4 for c in meta["cells"])
    assert any(c[3] == 1 for c in meta["cells"])                 # floor in A Site has A's colour
    assert meta["hand"] == -1 and meta["start"]


def test_roof_map_walkable_and_lids(built):
    mi, meta, blob, _vox = built
    head = mm.unpack_head(blob)
    n = int.from_bytes(blob[4:8], "little")
    o, ln = head["sections"]["roof"]
    R = head["roof"]
    v = np.frombuffer(blob[8 + n + o:8 + n + o + ln], "<u2").reshape(R["h"], R["w"])
    from nexus.stats.map3d import Frame
    fr = Frame(mi)

    def cell(x, y):
        a, b = fr.to_m(x, y)
        return int(v[int((b - R["z0"]) // R["cell"]), int((a - R["x0"]) // R["cell"])])
    assert cell(-5000, -4500) & 1 and not cell(-5000, -4500) & 2           # on the floor: walkable, no lid
    t = cell(7000, 500)                                                    # the tower beyond the walkable area
    assert not t & 1 and t & 2                                             # (files' y −1000..0 = world 0..1000)


def test_objects_simplified_one_by_one():
    big = gf.Mesh(np.random.default_rng(1).random((3000, 3)) * [2000, 2000, 10], np.arange(3000).reshape(-1, 3))
    rng = np.random.default_rng(2)
    pts = rng.normal(size=(800, 3))
    pts = pts / np.linalg.norm(pts, axis=1, keepdims=True) * 50 + 50          # a ball: ~1600 triangles
    from scipy.spatial import ConvexHull
    prop = gf.Mesh(pts, ConvexHull(pts).simplices)
    items = [(big, 1, np.eye(4))] + [(prop, 2, np.eye(4))] * 20
    out = mm.per_object(items, 2000)
    assert 1 not in out                                          # the big piece (floor, wall) stays as it is
    assert 2 in out and len(out[2][1]) < len(prop.tris)          # the prop is simplified, once for all 20


def test_zone_lookup_and_world_frame(built):
    mi, meta, _blob, _vox = built
    zones = sg.Zones(meta["zones"])
    from nexus.stats.map3d import Frame
    fr = Frame(mi)
    x, zz = fr.to_m(-5000, -4500)
    assert zones.at(x, 0.0, zz) == "A Site"
    x, zz = fr.to_m(-5000, 4500)
    assert zones.at(x, 0.0, zz) == ""                            # B isn't a zone in this map


def test_line_of_sight_through_the_wall(built):
    mi, meta, _blob, vox = built
    from nexus.stats.map3d import Frame
    fr = Frame(mi)
    s = sg.Sight(vox)

    def at(x, y):
        a, b = fr.to_m(x, y)
        return [a, 1.5, b]
    across = s.clear(np.array([at(-1500, 0)]), np.array([at(-400, 0)]))[0]
    beside = s.clear(np.array([at(-1500, 0)]), np.array([at(-2500, 500)]))[0]
    over = s.clear(np.array([[*at(-1500, 0)[:1], 6.0, at(-1500, 0)[2]]]), np.array([[*at(-400, 0)[:1], 6.0, at(-400, 0)[2]]]))[0]
    assert not across and beside and over                        # the wall is 4 m high
    glass = s.clear(np.array([at(1800, 50)]), np.array([at(2300, 50)]))[0]
    assert glass                                                 # glass doesn't block


def test_last_stretch():
    T, F = True, False
    assert sg._last_stretch([F, F, T, T, T]) == pytest.approx(0.2)
    assert sg._last_stretch([T, T, F, F, F, F, F, T, T]) == pytest.approx(0.1)   # a long break starts a new look
    assert sg._last_stretch([T, T, T, F, T]) == pytest.approx(0.4)               # a short one doesn't
    assert sg._last_stretch([F, F, F]) is None


def test_agent_model(tmp_path):
    write_game(tmp_path)
    files = gf.GameFiles(tmp_path)
    assert set(files.agent_models()) == {"Wushu"}
    idx = am.build_all(files, tmp_path / "agents3d")
    assert idx["Wushu"]["tris"] == 13 and idx["Wushu"]["height"] == pytest.approx(1.9)
    blob = gzip.decompress((tmp_path / "agents3d" / "wushu.bin.gz").read_bytes())
    n = int.from_bytes(blob[4:8], "little")
    head = json.loads(blob[8:8 + n])
    assert blob[:4] == b"NXA1" and head["joints"] == ["Root", "Spine"] and head["parents"] == [-1, 0]
    o, ln = head["sections"]["bind"]
    bind = np.frombuffer(blob[8 + n + o:8 + n + o + ln], "<f4").reshape(-1, 4, 4)
    assert np.allclose(bind[1][3, :3], (0, -0.1, 1.0))           # the files' y mirrored back, metres
    o, ln = head["sections"]["weight"]
    w = np.frombuffer(blob[8 + n + o:8 + n + o + ln], np.uint8).reshape(-1, 4)
    assert (w[:, 0] == 191).all() and (w[:, 1] == 64).all()
    o, ln = head["sections"]["pos"]
    pos = np.frombuffer(blob[8 + n + o:8 + n + o + ln], "<i2").reshape(-1, 3)
    assert pos[:, 0].max() == 400                                 # the nose: x forward (mm)
    assert am.build_all(files, tmp_path / "agents3d") == idx      # unchanged: not converted again


# ------------------------------------------------------------------------------------------------ the web app
def _game_app(app, synthetic):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    root = Path(store.data_dir) / "game"
    write_game(root)
    cache = Path(store.data_dir) / "cache"
    for f in ("valorant_api_agents.json",):
        d = json.loads((synthetic["cache"] / f).read_text())
        for a in d["data"]:
            a["developerName"] = {"Jett": "Wushu"}.get(a["displayName"], a["displayName"])
        (cache / f).write_text(json.dumps(d))
    b = app.extensions["nexus"]["game"]
    b.build_all()
    return b


def test_maps_page_and_api(app, synthetic):  # noqa: F811
    b = _game_app(app, synthetic)
    assert b.status.get("Testmap") == "built"
    c = setup_admin(app)
    pid = add_profile(c)
    d = c.get("/api/maps3d/Testmap").get_json()
    assert d["game"] and d["mesh"].startswith("/api/maps3d/Testmap/mesh?h=") and d["zones"] and "source" not in d
    r = c.get(d["mesh"])
    assert r.status_code == 200 and r.headers["Content-Encoding"] == "gzip" and "immutable" in r.headers["Cache-Control"]
    assert gzip.decompress(r.data)[:4] == b"NXM1"
    page = c.get(f"/profiles/{pid}/maps3d").data.decode()
    assert "◆" in page and 'id="m3-roofs"' in page and 'value="height"' in page
    r = c.get("/api/agents3d/Wushu?h=x")
    assert r.status_code == 200 and gzip.decompress(r.data)[:4] == b"NXA1" and "no-cache" in r.headers["Cache-Control"]
    assert c.get("/api/agents3d/Nobody").status_code == 404
    assert c.get("/api/game/status").get_json()["maps"]["Testmap"] == "built"
    assert app.extensions["nexus"]["agents_boot"]() == {"Jett": "/api/agents3d/Wushu?h=" + b.agent_index()["Wushu"]["hash"]}


def test_without_game_files_nothing_changes(app):  # noqa: F811
    c = setup_admin(app)
    add_profile(c)
    d = c.get("/api/maps3d/Testmap").get_json()
    assert "game" not in d and "game_status" not in d
    assert c.get("/api/maps3d/Testmap/mesh").status_code == 404


def test_replay_deaths_with_callouts_and_sight(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    ctx = app.extensions["nexus"]["replay_ctx"](UID)
    assert ctx.game is not None and ctx.sight is not None
    d = c.get(f"/api/replay/{UID}/round/0?pid={pid}").get_json()
    assert d["kills"] and all("where" in k for k in d["kills"])
    assert any(k["where"] == "A Site" for r in range(len(ctx.match.rounds)) for k in (ctx.round_view(r) or {"kills": []})["kills"])
    rv = [k["review"] for k in d["kills"] if "review" in k]
    assert rv and all(set(r) >= {"killer_saw", "victim_saw", "first", "open_to", "exposed", "unseen"} for r in rv)
    page = c.get(f"/profiles/{pid}/replay/{UID}").data.decode()
    assert 'id="deaths"' in page and "Your deaths" in page and '"agents": {"Jett"' in page and '"game_map": true' in page
    s = ctx.death_summary(next(p for p, pl in ctx.match.players.items() if pl.name == "adv1ce"))
    assert s["deaths"] >= 1 and s["sight"] and sum(n for _w, n in s["where"]) == s["deaths"]


def test_cli_builds(tmp_path, synthetic, capsys):  # noqa: F811
    data = tmp_path / "data"
    (data / "cache").mkdir(parents=True)
    (data / "cache" / "valorant_api_maps.json").write_text((synthetic["cache"] / "valorant_api_maps.json").read_text())
    write_game(data / "game")
    from nexus.cli import main
    main(["build-game", "--data", str(data), "--no-agents"])
    out = capsys.readouterr().out
    assert "Testmap: built" in out and (data / "maps3d" / "testmap.game.bin.gz").is_file()
    with pytest.raises(SystemExit):
        main(["build-game", "--data", str(tmp_path / "empty")])


# ------------------------------------------------------------------------------------------------ the pages
def test_scripts():
    js = (STATIC / "map3d.js").read_text()
    for s in ("function loadGame(d)", "OES_element_index_uint", "function visible(a, b)", "function drawModels(list)",
              "gl.depthFunc(gl.GREATER)", "function zoneAt(x, y, z)", "if (wp.y > h + rcut) discard;"):
        assert s in js, s
    gvs = re.search(r"const GVS = `(.*?)`;", js, re.S).group(1)
    gfs = re.search(r"const GFS = `(.*?)`;", js, re.S).group(1)
    shared = set(re.findall(r"uniform \w+ (\w+);", gvs)) & set(re.findall(r"uniform (?:\w+ )?\w+ (\w+);", gfs))
    assert not shared, shared
    avs = re.search(r"const AVS = `(.*?)`;", js, re.S).group(1)
    afs = re.search(r"const AFS = `(.*?)`;", js, re.S).group(1)
    assert not set(re.findall(r"uniform \w+ (\w+);", avs)) & set(re.findall(r"uniform (?:\w+ )?\w+ (\w+);", afs))
    rj = (STATIC / "replay.js").read_text()
    assert "function models()" in rj and "models, objects, ready" in rj and "function review(k)" in rj
    for t in ("maps3d.html", "replay_view.html"):
        html = (TEMPLATES / t).read_text()
        assert 'data-legend="game"' in html and 'value="height"' in html, t
    assert 'id="m3-xray"' in (TEMPLATES / "replay_view.html").read_text()


@pytest.mark.skipif(subprocess.run(["which", "node"], capture_output=True).returncode != 0, reason="node missing")
def test_scripts_parse():
    for f in ("map3d.js", "replay.js"):
        assert subprocess.run(["node", "--check", str(STATIC / f)], capture_output=True).returncode == 0, f


def test_texts():
    root = Path(__file__).parent.parent
    de = json.loads((root / "nexus/i18n/de.json").read_text())
    for k in ("Your deaths", "the enemy saw you first", "you never saw your killer", "open to more than one enemy",
              "See through walls", "Roofs", "Height", "never saw the killer", "the enemy saw him first",
              "he saw the killer first", "saw each other at once", "open to", "From the game's files"):
        assert k in de and "ß" not in de[k], k
    assert math.isfinite(len(de))
