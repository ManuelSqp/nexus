"""4.50.1: sidearms held out in front with both hands.

The game's pistol pose for the core skeleton sits in an agent's folder (TP_Core_BasePistol_S0_IdlePose); without it
the pose is made from the rifle pose: the right arm stretched out until the right hand meets the left one."""
import json
import math
from pathlib import Path

import numpy as np

from nexus import gamefiles as gf
from nexus.stats import agentanim as aa

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"

ARM = ["Root", "Root/Splitter", "Root/Splitter/Spine1", "Root/Splitter/Spine1/R_Shoulder",
       "Root/Splitter/Spine1/R_Shoulder/R_Elbow", "Root/Splitter/Spine1/R_Shoulder/R_Elbow/R_Hand",
       "Root/Splitter/Spine1/L_Hand"]
# local rest (cm, files' frame): the right arm hangs from the shoulder, the left hand out in front
REST = [(0, 0, 0), (0, 0, 100), (0, 0, 40), (0, 20, 0), (0, 0, -28), (0, 0, -26), (45, -5, 0)]


def _f(v):
    return "(" + ", ".join(f"{x:g}" for x in v) + ")"


def write_pose(path: Path, name: str, rot_shoulder=(1, 0, 0, 0)):
    """A one-frame pose of the arm skeleton (the files' frame)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    js = ", ".join(f'"{j}"' for j in ARM)
    rest = ", ".join("(" + ", ".join(_f(r) for r in [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (*t, 1)]) + ")"
                     for t in REST)
    q = [(1, 0, 0, 0)] * len(ARM)
    q[3] = rot_shoulder
    rows = "\n".join(f"            {k}: [{', '.join(_f(t) for t in REST)}]," for k in range(2))
    rots = "\n".join(f"            {k}: [{', '.join(_f(x) for x in q)}]," for k in range(2))
    path.write_text(
        f'#usda 1.0\n(\n    timeCodesPerSecond = 30\n)\n\ndef SkelRoot "Core_Skeleton"\n{{\n'
        f'    def Skeleton "Core_Skeleton"\n    {{\n        uniform token[] joints = [{js}]\n'
        f'        uniform matrix4d[] restTransforms = [{rest}]\n    }}\n'
        f'    def SkelAnimation "{name}"\n    {{\n        uniform token[] joints = [{js}]\n'
        f'        float3[] translations.timeSamples = {{\n{rows}\n        }}\n'
        f'        quatf[] rotations.timeSamples = {{\n{rots}\n        }}\n    }}\n}}\n')


def _core(root: Path) -> Path:
    core = root / "Characters_with_animation" / "_Core" / "3P" / "Anims"
    write_pose(core / "TP_Core_Idle_LB.usda", "TP_Core_Idle_LB")
    write_pose(core / "Rifle" / "Core_Rifle_Idle.usda", "Core_Rifle_Idle")
    return core


def _world(u: dict, clip: str) -> np.ndarray:
    W0 = aa.world_rest(u["rest"], u["parents"])
    return aa.pose(u["joints"], u["parents"], W0, u, "idle", 0, upper=clip)


def test_pistol_made_from_the_rifle_pose(tmp_path):
    _core(tmp_path)
    head, blob = aa.build(gf.GameFiles(tmp_path))
    assert head["clips"]["pistol"]["src"] == "made from hold" and head["clips"]["pistol"]["loop"]
    u = aa.unpack(blob)
    W = _world(u, "pistol")
    j = {n: i for i, n in enumerate(u["joints"])}
    rh, lh = W[j["R_Hand"]][:3, 3], W[j["L_Hand"]][:3, 3]
    assert np.linalg.norm(rh - (lh + aa.PISTOL_REACH)) < 0.01                 # the hands meet
    sh, el = W[j["R_Shoulder"]][:3, 3], W[j["R_Elbow"]][:3, 3]
    assert abs(np.linalg.norm(el - sh) - 0.28) < 1e-3 and abs(np.linalg.norm(rh - el) - 0.26) < 1e-3  # same bones
    hold = _world(u, "hold")
    assert np.allclose(hold[j["L_Hand"]], W[j["L_Hand"]], atol=1e-5)          # only the right arm moved
    # the pistol grip: at the right hand, the barrel straight ahead, the top up
    G = W[j["R_Hand"]] @ u["grips"]["pistol"]
    assert np.allclose(G[:3, 0], (1, 0, 0), atol=1e-4) and np.allclose(G[:3, 2], (0, 0, 1), atol=1e-4)
    assert np.allclose(G[:3, 3], rh - np.array([0, 0, aa.GRIP_DROP]), atol=1e-4)
    assert set(head["grips"]) == {"hold", "pistol"} and "Luger" in head["sidearms"]


def test_the_games_pistol_pose_wins(tmp_path):
    _core(tmp_path)
    turn = (math.cos(0.3), 0, math.sin(0.3), 0)
    write_pose(tmp_path / "Characters_with_animation" / "Cashew" / "S0" / "Ability_E" / "3P" / "Anims" /
               "TP_Core_BasePistol_S0_IdlePose.usda", "TP_Core_BasePistol_S0_IdlePose", rot_shoulder=turn)
    found = aa.find_clips(gf.GameFiles(tmp_path))
    assert found["pistol"].name == "TP_Core_BasePistol_S0_IdlePose.usda"     # found outside _Core
    head, blob = aa.build(gf.GameFiles(tmp_path))
    assert head["clips"]["pistol"]["src"] == "TP_Core_BasePistol_S0_IdlePose"
    u = aa.unpack(blob)
    q = u["clips"]["pistol"]["R"][0, u["joints"].index("R_Shoulder")]
    assert np.allclose(q, (turn[0], 0, turn[2], 0), atol=1e-3)               # (w, -x, y, -z): y stays


def test_mat_quat_round_trip():
    for q in ([1, 0, 0, 0], [0.5, 0.5, 0.5, 0.5], [0, 1, 0, 0], [0.1, 0.2, -0.9, 0.3], [0.2, 0.1, 0.1, -0.97]):
        q = np.array(q, float) / np.linalg.norm(q)
        back = aa.mat_quat(aa.quat_mat(q)[:3, :3])
        assert np.allclose(back, q, atol=1e-6) or np.allclose(back, -q, atol=1e-6)


def test_scripts():
    rj = (STATIC / "replay.js").read_text()
    for s in ("const SIDEARMS = new Set(['Classic', 'Shorty', 'Frenzy', 'Ghost', 'Sheriff', 'Bandit']);",
              "window.nexusMap3D.clips().includes('pistol')", "o.hold = holdFor(w);", "[[hold, t, 1]]"):
        assert s in rj, s
    m3 = (STATIC / "map3d.js").read_text()
    assert "const grip = A.grips[o.hold] || A.grip;" in m3


def test_texts_and_version():
    import nexus
    assert nexus.__version__.startswith("4.50.")
    assert "## 4.50.1" in (ROOT / "CHANGELOG.md").read_text()
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    assert "ß" not in json.dumps(de, ensure_ascii=False)
