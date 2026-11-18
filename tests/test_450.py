"""4.50: animated agents with guns in the replay viewer, portraits on top, P / Space / Ctrl.

The game's files can't be in the tests: a tiny core skeleton with a few clips is written here in the format FModel
exports (SkelAnimation with time samples), plus a gun (and an attachment that must be left out)."""
import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import UID, _replay  # noqa: E402
from test_448 import _fmt, box, usd_mesh, write_game  # noqa: E402
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

from nexus import gamefiles as gf  # noqa: E402
from nexus.stats import agentanim as aa  # noqa: E402
from nexus.stats import agentmesh as am  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"
TEMPLATES = ROOT / "nexus" / "web" / "templates"

JOINTS = ["Root", "Root/Splitter", "Root/Splitter/Spine1", "Root/Splitter/Spine1/R_Hand",
          "Root/Splitter/Spine1/L_Hand", "Root/Splitter/L_Leg"]
# local rest (cm, files' frame: y mirrored): pelvis 100 up, spine 30, hands in front (left further out), a leg
REST_T = [(0, 0, 0), (0, 0, 100), (0, 0, 30), (20, -15, 20), (50, 10, 25), (0, 10, -50)]


def _mat(t):
    return "(" + ", ".join(_fmt(r) for r in [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (*t, 1)]) + ")"


def write_clip(path: Path, name: str, frames: int, spine_deg=0.0, pelvis=100.0, fps=30.0, static=False):
    """A clip of the core skeleton: the spine turns from 0 to spine_deg about z over the frames, the pelvis at
    `pelvis` cm. `static`: rotations written once (not time-sampled)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    js = ", ".join(f'"{j}"' for j in JOINTS)
    rest = ", ".join(_mat(t) for t in REST_T)

    def rots(k):
        a = math.radians(spine_deg) * (k / max(1, frames - 1)) / 2
        q = [(1, 0, 0, 0)] * len(JOINTS)
        q[2] = (math.cos(a), 0, 0, math.sin(a))
        return "[" + ", ".join(_fmt(x) for x in q) + "]"

    def trans(k):
        t = list(REST_T)
        t[1] = (0, 0, pelvis)
        return "[" + ", ".join(_fmt(x) for x in t) + "]"

    tr = "\n".join(f"            {k}: {trans(k)}," for k in range(frames))
    if static:
        rot = f"        quatf[] rotations = {rots(0)}\n"
    else:
        rot = "        quatf[] rotations.timeSamples = {\n" + "\n".join(
            f"            {k}: {rots(k)}," for k in range(frames)) + "\n        }\n"
    path.write_text(
        f'#usda 1.0\n(\n    defaultPrim = "Core_Skeleton"\n    endTimeCode = {frames - 1}\n    metersPerUnit = 0.01\n'
        f'    startTimeCode = 0\n    timeCodesPerSecond = {fps}\n    upAxis = "Z"\n)\n\n'
        f'def SkelRoot "Core_Skeleton" (\n    prepend apiSchemas = ["SkelBindingAPI"]\n)\n{{\n'
        f'    def Skeleton "Core_Skeleton"\n    {{\n        uniform token[] joints = [{js}]\n'
        f'        uniform matrix4d[] restTransforms = [{rest}]\n        uniform matrix4d[] bindTransforms = [{rest}]\n    }}\n\n'
        f'    def SkelAnimation "{name}"\n    {{\n        uniform token[] joints = [{js}]\n'
        f'        float3[] translations.timeSamples = {{\n{tr}\n        }}\n{rot}'
        f'        half3[] scales = [{", ".join("(1, 1, 1)" for _ in JOINTS)}]\n    }}\n}}\n')


def write_motion(root: Path) -> None:
    """The core clips under an export folder named like the friend's archive, a gun and an attachment."""
    core = root / "Characters_with_animation" / "_Core"
    write_clip(core / "3P" / "Anims" / "TP_Core_Idle_LB.usda", "TP_Core_Idle_LB", 4, static=True)
    write_clip(core / "3P" / "Anims" / "TP_Core_WalkN_LB.usda", "TP_Core_WalkN_LB", 31, spine_deg=90, fps=60)
    write_clip(core / "3P" / "Anims" / "Rifle" / "Core_Rifle_Idle.usda", "Core_Rifle_Idle", 3)
    write_clip(core / "Death" / "3P" / "Anims" / "TP_Core_Death_Body_Front_LG.usda", "TP_Core_Death_Body_Front_LG", 5,
               pelvis=20)
    write_clip(root / "Other" / "TP_Core_RunN_LB.usda", "TP_Core_RunN_LB", 3)          # not a core animation folder
    guns = root / "Export" / "ShooterGame" / "Content" / "Equippables" / "Guns"
    usd_mesh(guns / "Rifles" / "AK" / "S0" / "1P" / "Models" / "GN_AK_S0_Skelmesh.usda", "GN_AK_S0_Skelmesh",
             *box((-40, -3, -10), (90, 3, 15)))
    usd_mesh(guns / "Rifles" / "AK" / "S0" / "1P" / "Models" / "GN_AK_Magazine_S0_Staticmesh.usda", "Mag",
             *box((0, 0, 0), (5, 5, 5)))
    usd_mesh(guns / "Attachments" / "Silencer" / "S0" / "1P" / "Models" / "GN_Silencer_S0_Skelmesh.usda",
             "GN_Silencer_S0_Skelmesh", *box((0, 0, 0), (20, 2, 2)))


# ------------------------------------------------------------------------------------------------ reading
def test_read_anim_samples_and_mirror(tmp_path):
    f = tmp_path / "a.usda"
    write_clip(f, "Walk", 31, spine_deg=90, fps=60)
    a = aa.read_anim(f)
    assert a["name"] == "Walk" and a["fps"] == 60 and a["joints"] == JOINTS
    assert a["T"].shape == (31, 6, 3) and a["R"].shape == (31, 6, 4)
    assert np.allclose(a["T"][0, 3], (20, -15, 20)) and np.allclose(a["rest"][3][:3, 3], (20, -15, 20))
    m = aa.mirror(a)                                     # the game's frame, metres
    assert np.allclose(m["T"][0, 3], (0.2, 0.15, 0.2)) and np.allclose(m["rest"][3][:3, 3], (0.2, 0.15, 0.2))
    q = a["R"][-1, 2]
    assert np.allclose(m["R"][-1, 2], (q[0], -q[1], q[2], -q[3]))   # (w, -x, y, -z)
    r = aa.resample(m)                                   # 0.5 s at 60 fps -> 16 frames at 30
    assert r["fps"] == aa.FPS and len(r["R"]) == 16 and np.allclose(np.linalg.norm(r["R"], axis=-1), 1)
    s = tmp_path / "s.usda"
    write_clip(s, "Still", 4, static=True)
    b = aa.read_anim(s)
    assert b["R"].shape == (4, 6, 4)                     # one rotation for every frame
    assert aa.read_anim(tmp_path / "missing.usda") is None


def test_clips_found_built_and_packed(tmp_path):
    write_motion(tmp_path)
    files = gf.GameFiles(tmp_path)
    found = aa.find_clips(files)
    assert set(found) == {"idle", "walk_N", "hold", "death_front"}         # the run outside _Core isn't taken
    head, blob = aa.build(files)
    assert blob[:4] == b"NXN1" and head["joints"] == [j.rsplit("/", 1)[-1] for j in JOINTS]
    assert head["parents"] == [-1, 0, 1, 2, 2, 1] and head["upper"] == "Spine1" and head["move"] == ["Root", "Splitter"]
    assert head["clips"]["walk_N"]["loop"] and not head["clips"]["death_front"]["loop"]
    u = aa.unpack(blob)
    assert u["clips"]["walk_N"]["R"].shape == (16, 6, 4)
    assert abs(u["clips"]["death_front"]["T"][0, 1, 2] - 0.2) < 1e-6     # the pelvis low (m)
    # the grip: the gun's origin at the right hand (a bit lower), its barrel towards the left hand, its top up
    g = u["grip"]
    W = aa.world_rest(u["rest"], u["parents"])
    G = W[3] @ g
    lh = W[4][:3, 3] - W[3][:3, 3]
    assert np.allclose(G[:3, 0], lh / np.linalg.norm(lh), atol=1e-4)
    assert G[2, 2] > 0.9 and abs(G[2, 3] - (W[3][2, 3] - aa.GRIP_DROP)) < 1e-3
    # saved once, kept while the clips don't change
    info = aa.save(tmp_path / "agents3d", files)
    assert info["clips"] == sorted(found) and (tmp_path / "agents3d" / "anims.bin.gz").is_file()
    assert aa.read_meta(tmp_path / "agents3d")["hash"] == info["hash"]
    mt = (tmp_path / "agents3d" / "anims.bin.gz").stat().st_mtime_ns
    assert aa.save(tmp_path / "agents3d", gf.GameFiles(tmp_path))["hash"] == info["hash"]
    assert (tmp_path / "agents3d" / "anims.bin.gz").stat().st_mtime_ns == mt
    assert aa.save(tmp_path / "none", gf.GameFiles(tmp_path / "nothing")) is None


def test_pose_keeps_the_agents_bones(tmp_path):
    """Rotations from the clip, bone lengths from the agent; the pelvis scaled to the agent's size; the upper body
    from its own clip."""
    write_motion(tmp_path)
    u = aa.unpack(aa.build(gf.GameFiles(tmp_path))[1])
    names = ["Root", "Splitter", "Spine1", "R_Hand", "L_Hand", "L_Leg", "Hair"]
    parents = [-1, 0, 1, 2, 2, 1, 2]
    loc = [(0, 0, 0), (0, 0, 1.2), (0, 0, 0.4), (0.3, 0.2, 0.25), (0.6, -0.1, 0.3), (0, -0.1, -0.6), (0, 0, 0.5)]
    local = np.tile(np.eye(4), (7, 1, 1))
    for j, t in enumerate(loc):
        local[j][:3, 3] = t
    bind = aa.world_rest(local, parents)
    w0 = aa.pose(names, parents, bind, u, "walk_N", 0)
    assert np.allclose(w0[1][:3, 3], (0, 0, 1.2))                         # 1.0 m in the clip x (1.2 / 1.0)
    assert np.allclose(w0[3][:3, 3], (0.3, 0.2, 1.2 + 0.4 + 0.25))         # the agent's own hand position
    w1 = aa.pose(names, parents, bind, u, "walk_N", 15)                    # the spine turned 90° about z
    hand = w1[3][:3, 3] - w1[2][:3, 3]
    assert np.allclose(hand, (0.2, -0.3, 0.25), atol=1e-3)                 # +90° in the files is −90° in the game
    assert np.allclose(w1[6][:3, 3], w0[6][:3, 3])                         # a joint the clips don't have: as bound
    w2 = aa.pose(names, parents, bind, u, "walk_N", 15, upper="hold")       # the upper body holds still
    assert np.allclose(w2[3][:3, 3], w0[3][:3, 3])
    dead = aa.pose(names, parents, bind, u, "death_front", 4)
    assert dead[1][2, 3] < 0.3                                              # on the floor


def test_guns_found_and_built(tmp_path):
    write_motion(tmp_path)
    files = gf.GameFiles(tmp_path)
    assert set(files.gun_models()) == {"AK"}                               # no magazine, no silencer
    idx = am.build_guns(files, tmp_path / "agents3d")
    assert set(idx) == {"AK"} and (tmp_path / "agents3d" / "guns" / "ak.bin.gz").is_file()
    blob = gzip.decompress((tmp_path / "agents3d" / "guns" / "ak.bin.gz").read_bytes())
    n = int.from_bytes(blob[4:8], "little")
    head = json.loads(blob[8:8 + n])
    pos = np.frombuffer(blob, "<i2", head["nv"] * 3, 8 + n + head["sections"]["pos"][0]).reshape(-1, 3)
    assert pos[:, 0].min() == -400 and pos[:, 0].max() == 900 and pos[:, 1].min() == -30   # mm, y mirrored back
    assert am.build_guns(files, tmp_path / "agents3d") == idx               # nothing changed: nothing built
    assert am.WEAPONS["Vandal"] == "AK" and am.WEAPONS["Phantom"] == "Carbine" and am.WEAPONS["Operator"] == "Leversniper"


# ------------------------------------------------------------------------------------------------ the server
def test_builder_routes_and_boot(app):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    game = app.extensions["nexus"]["game"]
    root = Path(store.data_dir) / "game"
    write_game(root)
    write_motion(root)
    game.files = None
    game.build_all()
    assert set(game.gun_index()) == {"AK"} and len(game.anims()["clips"]) == 4
    c = setup_admin(app)
    r = c.get("/api/anims3d")
    assert r.status_code == 200 and r.headers["Content-Encoding"] == "gzip"
    assert gzip.decompress(r.data)[:4] == b"NXN1"
    r = c.get("/api/guns3d/ak")
    assert r.status_code == 200 and gzip.decompress(r.data)[:4] == b"NXA1"
    assert c.get("/api/guns3d/nope").status_code == 404 and c.get("/api/guns3d/a.b").status_code == 404
    st = c.get("/api/game/status").get_json()
    assert st["guns"] == 1 and st["animations"] == 4
    boot = app.extensions["nexus"]["motion_boot"]()
    assert boot["anims"].startswith("/api/anims3d?h=") and boot["guns"]["Vandal"].startswith("/api/guns3d/AK?h=")
    assert "Phantom" not in boot["guns"]


def test_motion_boot_without_files(app):  # noqa: F811
    assert app.extensions["nexus"]["motion_boot"]() == {"anims": None, "guns": {}}


def test_round_guns_from_economy_and_kills(synthetic):  # noqa: F811
    from nexus.parse import parse_match
    from nexus.stats import replayview as rvw
    m = parse_match(json.loads(Path(synthetic["match"]).read_text()))
    ctx = rvw.Ctx({"pos": {}}, m, None)
    r = next(r for r in m.rounds if r.kills)
    p0 = r.kills[0].killer
    for st in r.stats.values():
        st.weapon = "Knife"                                                   # unknown: left out
    r.stats[p0].weapon = "Vandal"
    for k in r.kills:
        if k.killer == p0:
            k.weapon = "Vandal"
    k = next(k for k in r.kills if k.killer == p0)
    k.weapon, k.t_round_ms = "Operator", 20000
    g = ctx.guns(r.index)
    i0 = ctx.index[p0]
    assert g[i0][0] == [0.0, "Vandal"] and [19.0, "Operator"] in g[i0]
    assert all(seq[0][1] != "Knife" for seq in g.values())


def test_replay_page_has_motion(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    page = c.get(f"/profiles/{pid}/replay/{UID}").data.decode()
    assert '"anims":' in page and '"guns":' in page
    assert "Space / Ctrl" in page and "up / down" in page


# ------------------------------------------------------------------------------------------------ the scripts
def test_scripts():
    m3 = (STATIC / "map3d.js").read_text()
    for s in ("function setAnims(url)", "function rig(m)", "function pose(R, spec)", "function skin(m, R)",
              "function animate(o, m)", "uniform float pu;", "gl.DYNAMIC_DRAW", "anims: url => setAnims(url)",
              "function mulAt(", "A.grip"):
        assert s in m3, s
    assert m3.count("function mul(") == 1                                    # the view's matrix product stays
    rj = (STATIC / "replay.js").read_text() + (STATIC / "motion.js").read_text()   # 4.51: shared code in motion.js
    for s in ("c === 'KeyP'", "if (S.mode === 'free') S.keys.add(c); else play();", "'ControlLeft', 'ControlRight'",
              "k.has('Space')", "function motion(path, t, p, hold = 'hold')", "function body(i, path)", "const weaponOf = (i, t)",
              "/agent-icon/", "navigator.keyboard.lock", "prep(d);", "window.nexusMap3D.anims(C.anims)",
              "'death_back'", "'death_left'", "[[hold, t, 1]]"):
        assert s in rj, s
    html = (TEMPLATES / "replay_view.html").read_text()
    assert ".rv-a img{" in html and ".rv-a.dead::after" in html


def test_texts():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("up / down", "Free camera: WASD, Space/Ctrl (or E/Q) up and down, drag to look (V)"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import re
    import nexus
    v = nexus.__version__
    assert f'version = "{v}"' in (ROOT / "pyproject.toml").read_text()
    assert f'__version__ = "{v}"' in (ROOT / "desktop/nexus_desktop/__init__.py").read_text()
    assert f"**Version {v}**" in (ROOT / "README.md").read_text()
    assert re.search(rf"^## {re.escape(v)}$", (ROOT / "CHANGELOG.md").read_text(), re.M)
    assert "## 4.50.0" in (ROOT / "CHANGELOG.md").read_text()
