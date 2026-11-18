"""Agent animations from the game's files (4.50) for the 3D replay viewer.

The game's third-person animations are made for the core skeleton (Characters/_Core), which every agent shares by
joint name. A handful of them is enough for a replay: standing, walking and running in eight directions, crouching,
jumping, falling and a few deaths. They're read from the exported .usda files (FModel, SkelAnimation prims), cut down
to the joints the agents have, resampled to 30 frames a second and stored together in one small file
(data/agents3d/anims.bin.gz, with anims.json), which the browser loads once and plays on every agent (skinning on the CPU).

The frame is the game's own after reading (y mirrored back, see gamefiles.py), metres. Rotations are the joints'
local rotations; translations are kept only for the root and the pelvis ("Splitter"), the other joints keep the
agent's own bone lengths (the browser takes them from the model's bind pose), so a short agent isn't stretched to the
core skeleton's size.

The lower body (legs, pelvis) and the upper body (spine up) come from different clips, like in the game: the legs
walk or run, the upper body holds the gun. The split is the joint "Spine1": it and everything under it is upper
body, unless the clip is a full-body one (deaths, jumps)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import struct
from pathlib import Path

import numpy as np

from .. import gamefiles as gf

VERSION = 2
FPS = 30.0
# which joints carry translations from the clip (the rest keep the agent's own)
MOVE = ("Root", "Splitter")
SCALED = ("Root", "Splitter")            # MOVE joints whose translation is scaled to the agent's size
GUN = "R_Hand"                           # the gun is held by this joint (at "grip" in its frame)
GRIP_DROP = 0.04                         # the grip sits this far below the hand joint (m)
UPPER = "Spine1"

# clip -> (file stem, part): "lb" lower body, "ub" upper body, "full" whole body. The first stem found wins.
CLIPS: dict[str, tuple[tuple[str, ...], str]] = {
    "idle": (("TP_Core_Idle_LB", "TP_Core_IdlePose_LB"), "lb"),
    "hold": (("Core_Rifle_Idle", "TP_Core_Idle_UB", "TP_Core_IdlePose_UB"), "ub"),
    # 4.50.1: sidearms held with both hands, arms stretched out (the core pose sits in an agent's folder; without
    # it the pose is made from "hold", see pistol_from_hold)
    "pistol": (("TP_Core_BasePistol_S0_IdlePose",), "ub"),
    "crouch": (("TP_Core_CrouchIdle_LB", "TP_Core_CrouchPose_LB"), "lb"),
    **{f"walk_{d}": ((f"TP_Core_Walk{d}_LB",), "lb") for d in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")},
    **{f"run_{d}": ((f"TP_Core_Run{d}_LB",), "lb") for d in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")},
    **{f"cwalk_{d}": ((f"TP_Core_CrouchWalk{d}_LB",), "lb") for d in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")},
    "fall": (("TP_Core_Falling_LB",), "lb"),
    "death_front": (("TP_Core_Death_Body_Front_LG", "TP_Core_Death_Body_Front_SM"), "full"),
    "death_back": (("TP_Core_Death_Body_Back_LG", "TP_Core_Death_Body_Back_SM"), "full"),
    "death_left": (("TP_Core_Death_Body_Left_LG", "TP_Core_Death_Body_Left_SM"), "full"),
    "death_right": (("TP_Core_Death_Body_Right_LG", "TP_Core_Death_Body_Right_SM"), "full"),
    "death_head": (("TP_Core_Death_Headshot01", "TP_Core_Death_Head_Front_LG"), "full"),
}
LOOP = {"idle", "hold", "pistol", "crouch", "fall"} | {k for k in CLIPS if k.startswith(("walk_", "run_", "cwalk_"))}
ANYWHERE = {"pistol"}                     # clips found outside the _Core folders too (by their TP_Core_ name)
SIDEARMS = ("BasePistol", "Slim", "AutoPistol", "Luger", "Revolver", "Compact")     # held like a pistol

_HEAD = re.compile(r"timeCodesPerSecond\s*=\s*([\d.eE+-]+)")
_SAMPLES = re.compile(r"(\w+)\[\]\s+(translations|rotations|scales)\.timeSamples\s*=\s*\{")
_STATIC = re.compile(r"(\w+)\[\]\s+(translations|rotations|scales)\s*=\s*\[")
_FRAME = re.compile(r"^\s*([\d.]+)\s*:\s*\[", re.M)


def _samples(text: str, start: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    """The `{ t: [...], … }` block starting at `start` -> (times, values (F, J, width))."""
    end = text.find("\n        }", start)
    block = text[start:end if end > 0 else len(text)]
    times, vals = [], []
    for m in _FRAME.finditer(block):
        stop = block.find("]", m.end())
        times.append(float(m.group(1)))
        vals.append(gf._floats(block[m.end():stop]))
    if not vals:
        return np.zeros(0), np.zeros((0, 0, width))
    n = min(v.size for v in vals) // width
    return np.array(times), np.stack([v[:n * width].reshape(n, width) for v in vals])


def read_anim(path: Path) -> dict | None:
    """-> {"name", "fps", "joints": [full paths], "T": (F, J, 3) cm, "R": (F, J, 4) quats (w, x, y, z),
    "rest": (J, 4, 4) local rest transforms} in the file's frame (y mirrored), or None."""
    try:
        text = Path(path).read_text(errors="replace")
    except OSError:
        return None
    a = text.find('def SkelAnimation "')
    if a < 0:
        return None
    sk = text[:a]
    body = text[a:]
    jt = gf._array(body, "uniform token[] joints")
    if jt is None:
        return None
    joints = re.findall(r'"([^"]+)"', jt)
    m = _HEAD.search(text)
    fps = float(m.group(1)) if m else 30.0
    nm = re.match(r'def SkelAnimation "([^"]+)"', body)
    out = {"name": nm.group(1) if nm else Path(path).stem, "fps": fps, "joints": joints}
    nj = len(joints)
    for key, width in (("translations", 3), ("rotations", 4)):
        s = next((x for x in _SAMPLES.finditer(body) if x.group(2) == key), None)
        if s is not None:
            t, v = _samples(body, s.end(), width)
            if v.shape[1] != nj:
                return None
            out["t" if key == "translations" else "tr"] = t
            out["T" if key == "translations" else "R"] = v
            continue
        s = next((x for x in _STATIC.finditer(body) if x.group(2) == key), None)
        if s is None:
            return None
        stop = body.find("]", s.end())
        v = gf._floats(body[s.end():stop])
        if v.size != nj * width:
            return None
        out["T" if key == "translations" else "R"] = v.reshape(1, nj, width)
    rest = gf._array(sk, "uniform matrix4d[] restTransforms") or gf._array(sk, "restTransforms")
    sk_j = gf._array(sk, "uniform token[] joints")
    if rest is not None and sk_j is not None:
        names = re.findall(r'"([^"]+)"', sk_j)
        r = gf._floats(rest)
        if r.size == 16 * len(names):
            r = r.reshape(-1, 4, 4).transpose(0, 2, 1)
            idx = {n: i for i, n in enumerate(names)}
            out["rest"] = np.stack([r[idx[j]] if j in idx else np.eye(4) for j in joints])
    if "rest" not in out:
        out["rest"] = np.tile(np.eye(4), (nj, 1, 1))
    # unify frame counts (translations and rotations usually share their times)
    f = min(len(out["T"]), len(out["R"]))
    if len(out["T"]) == 1 and f == 1:
        pass
    T, R = out["T"], out["R"]
    if len(T) == 1 and len(R) > 1:
        T = np.repeat(T, len(R), 0)
    if len(R) == 1 and len(T) > 1:
        R = np.repeat(R, len(T), 0)
    f = min(len(T), len(R))
    out["T"], out["R"] = T[:f], R[:f]
    return out


def mirror(anim: dict) -> dict:
    """The file's frame (y mirrored) -> the game's frame, metres: t -> (x, -y, z) / 100, q -> (w, -x, y, -z)."""
    T = anim["T"] * np.array([1, -1, 1]) / 100.0
    R = anim["R"] * np.array([1, -1, 1, -1])
    F4 = np.diag([1.0, -1.0, 1.0, 1.0])
    rest = np.einsum("ij,njk,kl->nil", F4, anim["rest"], F4)
    rest[:, :3, 3] /= 100.0
    return {**anim, "T": T, "R": R, "rest": rest}


def resample(anim: dict, fps: float = FPS) -> dict:
    """Resamples to `fps` (nearest frame for translations, normalised lerp for rotations)."""
    n = len(anim["R"])
    if n <= 1:
        return {**anim, "fps": fps}
    dur = (n - 1) / anim["fps"]
    k = max(2, int(round(dur * fps)) + 1)
    src = np.linspace(0, n - 1, k)
    i0 = np.floor(src).astype(int).clip(0, n - 1)
    i1 = np.minimum(i0 + 1, n - 1)
    w = (src - i0)[:, None, None]
    T = anim["T"][i0] * (1 - w) + anim["T"][i1] * w
    q0, q1 = anim["R"][i0], anim["R"][i1]
    q1 = np.where((q0 * q1).sum(-1, keepdims=True) < 0, -q1, q1)
    R = q0 * (1 - w) + q1 * w
    R /= np.maximum(np.linalg.norm(R, axis=-1, keepdims=True), 1e-9)
    return {**anim, "T": T, "R": R, "fps": fps}


def find_clips(files: gf.GameFiles) -> dict[str, Path]:
    """Every clip of CLIPS found in the export: {clip: file}. Only the core skeleton's third-person clips
    (…/_Core/3P/Anims, …/_Core/Death/3P/Anims), whatever the export's top folder is called."""
    found: dict[str, Path] = {}
    for clip, (names, _part) in CLIPS.items():
        for n in names:
            f = files.find(n, "/3P/") if clip in ANYWHERE else files.find(n, "/_Core/", "/3P/")
            if f is not None:
                found[clip] = f
                break
    return found


def build(files: gf.GameFiles, log=None) -> tuple[dict, bytes] | None:
    """Reads the clips -> (head, blob) of the shared animation file, or None without clips."""
    say = log or (lambda *_: None)
    files = find_clips(files)
    if not files:
        return None
    clips, joints, rest = {}, None, None
    for clip, f in files.items():
        a = read_anim(f)
        if a is None or not len(a["R"]):
            say(f"animation {clip}: can't read {f.name}")
            continue
        a = resample(mirror(a))
        names = [j.rsplit("/", 1)[-1] for j in a["joints"]]
        if joints is None:
            joints, rest = names, a["rest"]
            pidx = {n: i for i, n in enumerate(a["joints"])}
            parents = [pidx.get(n.rsplit("/", 1)[0], -1) if "/" in n else -1 for n in a["joints"]]
        pos = {n: i for i, n in enumerate(names)}
        sel = [pos.get(n, -1) for n in joints]
        R = np.stack([a["R"][:, i] if i >= 0 else np.tile([1.0, 0, 0, 0], (len(a["R"]), 1)) for i in sel], 1)
        T = np.stack([a["T"][:, i] if i >= 0 else np.zeros((len(a["T"]), 3)) for i in sel], 1)
        clips[clip] = {"R": R, "T": T, "part": CLIPS[clip][1], "loop": clip in LOOP, "src": f.stem}
    if not clips:
        return None
    if "pistol" not in clips and "hold" in clips:
        made = pistol_from_hold(joints, parents, rest, clips)
        if made is not None:
            clips["pistol"] = made
    return pack(joints, rest, clips, parents)


def world_rest(rest: np.ndarray, parents: list[int]) -> np.ndarray:
    W = np.zeros_like(rest)
    for j, p in enumerate(parents):
        W[j] = W[p] @ rest[j] if p >= 0 else rest[j]
    return W


def _anim(joints, parents, rest, clips, names) -> dict:
    """The clips in the shape pose() takes (as unpack() gives them)."""
    mj = [joints.index(j) for j in MOVE if j in joints]
    return {"joints": joints, "move": [joints[i] for i in mj], "rest": rest, "parents": parents,
            "clips": {n: {"R": clips[n]["R"], "T": clips[n]["T"][:, mj], "frames": len(clips[n]["R"])}
                      for n in names if n in clips}}


def grip(joints: list[str], parents: list[int], rest: np.ndarray, clips: dict, clip: str = "hold") -> np.ndarray:
    """Where the gun sits in the right hand's frame (4x4, metres), found from a pose of the core skeleton: its
    origin (the grip) at the right hand, its top (z) up, its barrel (x) towards the left hand ("hold": a rifle) or
    straight ahead ("pistol": both hands on the grip)."""
    G = np.eye(4)
    if clip not in clips or "R_Hand" not in joints or "L_Hand" not in joints:
        return G
    W = pose(joints, parents, world_rest(rest, parents), _anim(joints, parents, rest, clips, [clip]), clip, 0)
    R, L = W[joints.index("R_Hand")], W[joints.index("L_Hand")]
    x = L[:3, 3] - R[:3, 3] if clip == "hold" else np.array([1.0, 0, 0])
    if np.linalg.norm(x) < 0.05:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    z = np.array([0, 0, 1.0]) - x * x[2]
    z /= max(np.linalg.norm(z), 1e-9)
    y = np.cross(z, x)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = x, y, z, R[:3, 3] - z * GRIP_DROP
    return np.linalg.inv(R) @ M


def _turn(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The smallest rotation (3x3) turning direction a into direction b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(np.dot(a, b))
    if c < -0.9999:
        return -np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def mat_quat(m: np.ndarray) -> np.ndarray:
    """3x3 rotation -> quaternion (w, x, y, z)."""
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = np.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = np.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = np.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


PISTOL_REACH = np.array([-0.04, 0.02, -0.02])   # the right hand next to the left one (m, the model's frame)


def pistol_from_hold(joints: list[str], parents: list[int], rest: np.ndarray, clips: dict) -> dict | None:
    """A pistol pose made from the rifle pose (first frame): the right arm stretched out so that the right hand
    meets the left one (two-bone IK, the elbow stays on its side). Only the right shoulder and elbow change."""
    need = ("R_Shoulder", "R_Elbow", "R_Hand", "L_Hand")
    if any(n not in joints for n in need):
        return None
    sh, el, ha, lh = (joints.index(n) for n in need)
    anim = _anim(joints, parents, rest, clips, ["hold", "idle"])
    W = pose(joints, parents, world_rest(rest, parents), anim, "idle" if "idle" in clips else "hold", 0, upper="hold")
    S, E, H = W[sh][:3, 3], W[el][:3, 3], W[ha][:3, 3]
    T = W[lh][:3, 3] + PISTOL_REACH
    a, b = np.linalg.norm(E - S), np.linalg.norm(H - E)
    d = min(np.linalg.norm(T - S), a + b - 1e-3)
    u = (T - S) / np.linalg.norm(T - S)
    side = (E - S) - u * np.dot(E - S, u)
    if np.linalg.norm(side) < 1e-6:
        side = np.array([0, 0, -1.0]) - u * u[2]
    v = side / np.linalg.norm(side)
    ca = np.clip((a * a + d * d - b * b) / (2 * a * d), -1, 1)
    E2 = S + a * (ca * u + np.sqrt(1 - ca * ca) * v)
    r1 = _turn(E - S, E2 - S)
    H1 = E2 + r1 @ (H - E)
    r2 = _turn(H1 - E2, S + u * d - E2)
    rsh = r1 @ W[sh][:3, :3]
    rel = r2 @ r1 @ W[el][:3, :3]
    R = clips["hold"]["R"][:1].copy()
    R[0, sh] = mat_quat(W[parents[sh]][:3, :3].T @ rsh)
    R[0, el] = mat_quat(rsh.T @ rel)
    return {"R": R, "T": clips["hold"]["T"][:1].copy(), "part": "ub", "loop": True, "src": "made from hold"}


def pack(joints: list[str], rest: np.ndarray, clips: dict, parents: list[int] | None = None) -> tuple[dict, bytes]:
    """b"NXN1", u32 header length, header JSON, then per clip: rotations i16 x 4 per joint per frame (x 32767),
    translations f32 x 3 of the MOVE joints per frame. Header: joints, the core rest (f32 x 16 per joint,
    column-major, its own section), fps, clips {name: {frames, part, loop, rot: [off, len], move: [off, len]}}."""
    mj = [joints.index(j) for j in MOVE if j in joints]
    head = {"v": VERSION, "fps": FPS, "joints": joints, "move": [joints[i] for i in mj], "upper": UPPER,
            "scaled": list(SCALED), "gun": GUN, "parents": parents or [],
            "grip": np.round(grip(joints, parents, rest, clips).T.reshape(-1), 5).tolist() if parents else None,
            "grips": {c: np.round(grip(joints, parents, rest, clips, c).T.reshape(-1), 5).tolist()
                      for c in ("hold", "pistol") if c in clips and parents},
            "sidearms": list(SIDEARMS),
            "clips": {}, "sections": {}}
    body = io.BytesIO()

    def put(name, data, where):
        where[name] = [body.tell(), len(data)]
        body.write(data)
        body.write(b"\0" * ((-len(data)) % 4))

    put("rest", np.ascontiguousarray(rest.transpose(0, 2, 1)).astype("<f4").tobytes(), head["sections"])
    for name in sorted(clips):
        c = clips[name]
        R = np.round(c["R"] * 32767).clip(-32767, 32767).astype("<i2")
        info = {"frames": int(len(R)), "part": c["part"], "loop": c["loop"], "src": c["src"]}
        put("rot", R.tobytes(), info)
        put("move", c["T"][:, mj].astype("<f4").tobytes(), info)
        head["clips"][name] = info
    hj = json.dumps(head, separators=(",", ":")).encode()
    hj += b" " * ((-len(hj)) % 4)
    blob = b"NXN1" + struct.pack("<I", len(hj)) + hj + body.getvalue()
    return head, blob


def unpack(blob: bytes) -> dict:
    """For tests and tools: the file -> {"joints", "rest", "clips": {name: {"R", "T", …}}}."""
    n = struct.unpack("<I", blob[4:8])[0]
    head = json.loads(blob[8:8 + n])
    base = 8 + n
    nj = len(head["joints"])

    def sec(o_l, dt):
        o, l = o_l
        return np.frombuffer(blob, dt, l // np.dtype(dt).itemsize, base + o)

    out = {"joints": head["joints"], "move": head["move"], "fps": head["fps"], "parents": head.get("parents", []),
           "grip": np.array(head["grip"]).reshape(4, 4).T if head.get("grip") else np.eye(4),
           "grips": {k: np.array(v).reshape(4, 4).T for k, v in (head.get("grips") or {}).items()},
           "rest": sec(head["sections"]["rest"], "<f4").reshape(nj, 4, 4).transpose(0, 2, 1), "clips": {}}
    for name, c in head["clips"].items():
        f = c["frames"]
        out["clips"][name] = {**c, "R": sec(c["rot"], "<i2").reshape(f, nj, 4) / 32767.0,
                              "T": sec(c["move"], "<f4").reshape(f, len(head["move"]), 3)}
    return out


def save(dest: Path, files: gf.GameFiles, log=None) -> dict | None:
    """Builds <dest>/anims.bin.gz (dest: data/agents3d) when the clips changed. -> its meta or None."""
    say = log or (lambda *_: None)
    dest = Path(dest)
    clips = find_clips(files)
    if not clips:
        return None
    sig = hashlib.sha1(json.dumps([VERSION] + sorted(f"{k}:{p.name}:{p.stat().st_size}" for k, p in clips.items()))
                       .encode()).hexdigest()[:12]
    meta = dest / "anims.json"
    try:
        old = json.loads(meta.read_text())
    except (OSError, ValueError):
        old = {}
    if old.get("src") == sig and (dest / "anims.bin.gz").is_file():
        return old
    res = build(files, log)
    if res is None:
        return None
    head, blob = res
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / "anims.tmp"
    with gzip.open(tmp, "wb", compresslevel=6) as fh:
        fh.write(blob)
    tmp.replace(dest / "anims.bin.gz")
    info = {"src": sig, "hash": hashlib.sha1(blob).hexdigest()[:12], "clips": sorted(head["clips"]),
            "kb": len(blob) // 1024}
    meta.write_text(json.dumps(info, indent=1))
    say(f"animations: {len(head['clips'])} clips, {len(blob) // 1024} KB")
    return info


def read_meta(dest: Path) -> dict:
    try:
        return json.loads((Path(dest) / "anims.json").read_text())
    except (OSError, ValueError):
        return {}


# ------------------------------------------------------------------------------------------------ posing (tests/tools)
def quat_mat(q) -> np.ndarray:
    w, x, y, z = q
    return gf.quat_matrix(w, x, y, z)


def pose(model_joints: list[str], parents: list[int], bind: np.ndarray, anim: dict, clip: str, frame: int,
         upper: str | None = None) -> np.ndarray:
    """World matrices (J, 4, 4) of a model's joints in one frame of a clip (the same retargeting the browser does):
    rotations from the clip, translations from the model's bind pose except MOVE joints (scaled by the pelvis
    height). Mirrors replay.js/map3d.js and is what the tests check."""
    c = anim["clips"][clip]
    u = anim["clips"].get(upper) if upper else None
    aj = {n: i for i, n in enumerate(anim["joints"])}
    mv = {n: i for i, n in enumerate(anim["move"])}
    inv = np.linalg.inv(bind)
    local = np.stack([inv[p] @ bind[j] if p >= 0 else bind[j] for j, p in enumerate(parents)])
    sc = _pelvis_scale(model_joints, parents, local, anim)
    up = upper_set(model_joints, parents)
    W = np.zeros_like(bind)
    for j, name in enumerate(model_joints):
        L = local[j].copy()
        i = aj.get(name)
        if i is not None:
            src = u if (u is not None and j in up) else c
            q = src["R"][min(frame, src["frames"] - 1), i]
            L[:3, :3] = quat_mat(q / max(np.linalg.norm(q), 1e-9))[:3, :3]
            if name in mv:
                L[:3, 3] = src["T"][min(frame, src["frames"] - 1), mv[name]] * (sc if name in SCALED else 1.0)
        W[j] = W[parents[j]] @ L if parents[j] >= 0 else L
    return W


def upper_set(names: list[str], parents: list[int]) -> set[int]:
    """Indices of UPPER and every joint under it."""
    out = set()
    for j, n in enumerate(names):
        p = j
        while p >= 0:
            if names[p] == UPPER:
                out.add(j)
                break
            p = parents[p]
    return out


def _pelvis_scale(names, parents, local, anim) -> float:
    if "Splitter" not in names or "Splitter" not in anim["joints"]:
        return 1.0
    a = local[names.index("Splitter")][:3, 3]
    b = anim["rest"][anim["joints"].index("Splitter")][:3, 3]
    nb = np.linalg.norm(b)
    return float(np.linalg.norm(a) / nb) if nb > 1e-6 else 1.0
