"""Agent models from the game's files (4.48) for the 3D replay viewer: the third-person model of every agent,
simplified to a few thousand triangles and drawn in one colour (the team's).

The skeleton and the skin weights are kept in the file, so animations can be added later without converting the
models again; without animations the models stand in the pose they're exported in.

4.50: the guns (the default skin of each, guns/<code>.bin.gz, the same format without a skeleton); the animations
are in agentanim.py.

The model's own frame after reading: metres, x forward, y to the right, z up, the feet at 0 (the game's frame; the
exported files have y mirrored, see gamefiles.py). Stored per agent codename (Wushu = Jett, …) in
data/agents3d/<code>.bin.gz with an index (index.json)."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import struct
import time
from pathlib import Path

import numpy as np

from .. import gamefiles as gf
from .mapmesh import simplify

VERSION = 1
TARGET_TRIS = 5000
GUN_VERSION = 1
GUN_TRIS = 1500

# the weapon's name (match data) -> its folder in Equippables/Guns (the game's codename)
WEAPONS = {
    "Classic": "BasePistol", "Shorty": "Slim", "Frenzy": "AutoPistol", "Ghost": "Luger", "Sheriff": "Revolver",
    "Bandit": "Compact", "Stinger": "Vector", "Spectre": "MP5", "Bucky": "PumpShotgun", "Judge": "AutoShotgun",
    "Bulldog": "Burst", "Guardian": "DMR", "Phantom": "Carbine", "Vandal": "AK", "Warden": "BattleRifle",
    "Marshal": "Boltsniper", "Outlaw": "Doublesniper", "Operator": "Leversniper", "Ares": "LMG", "Odin": "HMG",
}


def convert(mesh: gf.Mesh) -> dict:
    """-> {"V": (n, 3) m, "N": normals, "T": triangles, "J": joint indices (n, 4), "W": weights (n, 4),
    "joints": names, "parents": [i], "bind": (j, 4, 4)} in the model's own frame (y mirrored back)."""
    F = np.diag([1.0, -1.0, 1.0])
    P = mesh.points @ F / 100.0
    V, T = simplify(P, mesh.tris, TARGET_TRIS)
    out = {"V": V, "T": T}
    if mesh.jidx is not None and mesh.jw is not None and len(mesh.joints):
        from scipy.spatial import cKDTree
        _d, near = cKDTree(P).query(V)
        J, W = mesh.jidx[near], mesh.jw[near]
        k = J.shape[1]
        if k < 4:
            J = np.pad(J, ((0, 0), (0, 4 - k)))
            W = np.pad(W, ((0, 0), (0, 4 - k)))
        elif k > 4:
            o = np.argsort(-W, axis=1)[:, :4]
            J, W = np.take_along_axis(J, o, 1), np.take_along_axis(W, o, 1)
        s = W.sum(1, keepdims=True)
        W = np.where(s > 0, W / np.where(s > 0, s, 1), np.array([1.0, 0, 0, 0]))
        out["J"], out["W"] = J.astype(np.uint8), W
        names = mesh.joints
        idx = {n: i for i, n in enumerate(names)}
        out["joints"] = [n.rsplit("/", 1)[-1] for n in names]
        out["parents"] = [idx.get(n.rsplit("/", 1)[0], -1) if "/" in n else -1 for n in names]
        if mesh.bind is not None:
            F4 = np.diag([1.0, -1.0, 1.0, 1.0])
            B = np.einsum("ij,njk,kl->nil", F4, mesh.bind, F4)
            B[:, :3, 3] /= 100.0
            out["bind"] = B
    out["N"] = normals(V, T)
    return out


def normals(V, T):
    N = np.zeros_like(V)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    for k in range(3):
        np.add.at(N, T[:, k], fn)
    n = np.linalg.norm(N, axis=1, keepdims=True)
    return N / np.where(n > 0, n, 1)


def pack(m: dict) -> bytes:
    """b"NXA1", u32 header length, header JSON, sections (4-byte aligned): pos i16 x 3 (mm), nrm i8 x 3 (+pad),
    joint u8 x 4, weight u8 x 4, idx u16 or u32 x 3, bind f32 x 16 per joint (column-major)."""
    V, T = m["V"], m["T"]
    nv = len(V)
    pos = np.round(V * 1000).clip(-32767, 32767).astype("<i2")
    nrm = np.zeros((nv, 4), np.int8)
    nrm[:, :3] = np.round(m["N"] * 127).clip(-127, 127)
    J = m.get("J", np.zeros((nv, 4), np.uint8))
    W = np.round(m.get("W", np.tile([1.0, 0, 0, 0], (nv, 1))) * 255).clip(0, 255).astype(np.uint8)
    big = nv > 65535
    idx = T.astype("<u4" if big else "<u2")
    bind = m.get("bind")
    secs = [("pos", pos.tobytes()), ("nrm", nrm.tobytes()), ("joint", J.astype(np.uint8).tobytes()),
            ("weight", W.tobytes()), ("idx", idx.tobytes()),
            ("bind", np.ascontiguousarray(bind.transpose(0, 2, 1)).astype("<f4").tobytes() if bind is not None else b"")]
    head = {"nv": nv, "nt": int(len(T)), "u32": big, "joints": m.get("joints", []), "parents": m.get("parents", []),
            "height": round(float(V[:, 2].max()), 3), "sections": {}}
    body = io.BytesIO()
    for name, data in secs:
        head["sections"][name] = [body.tell(), len(data)]
        body.write(data)
        body.write(b"\0" * ((-len(data)) % 4))
    hj = json.dumps(head, separators=(",", ":")).encode()
    hj += b" " * ((-len(hj)) % 4)
    return b"NXA1" + struct.pack("<I", len(hj)) + hj + body.getvalue()


def out_dir(data_dir) -> Path:
    return Path(data_dir) / "agents3d"


def build_all(files: gf.GameFiles, dest: Path, log=None, only: set[str] | None = None) -> dict:
    """Converts every agent model that's new or changed. -> the index {code: {"hash", "tris", "height", "src"}}."""
    say = log or (lambda *_: None)
    dest.mkdir(parents=True, exist_ok=True)
    idx = read_index(dest)
    for code, f in sorted(files.agent_models().items()):
        if only and code not in only:
            continue
        sig = f"{VERSION}:{f.name}:{f.stat().st_size}"
        if idx.get(code, {}).get("src") == sig and (dest / f"{code.lower()}.bin.gz").is_file():
            continue
        t0 = time.time()
        mesh = gf.read_mesh(f)
        if mesh is None or not len(mesh.tris):
            say(f"{code}: no model in {f.name}")
            continue
        blob = pack(convert(mesh))
        tmp = dest / f"{code.lower()}.tmp"
        with gzip.open(tmp, "wb", compresslevel=6) as fh:
            fh.write(blob)
        tmp.replace(dest / f"{code.lower()}.bin.gz")
        head = json.loads(blob[8:8 + struct.unpack("<I", blob[4:8])[0]])
        idx[code] = {"hash": hashlib.sha1(blob).hexdigest()[:12], "tris": head["nt"], "height": head["height"],
                     "src": sig}
        say(f"{code}: {head['nt']} triangles, {len(blob) // 1024} KB ({time.time() - t0:.1f} s)")
    (dest / "index.json").write_text(json.dumps(idx, indent=1))
    return idx


def convert_gun(mesh: gf.Mesh) -> dict:
    """A gun: metres, y mirrored back, x along the barrel, z up, the grip at 0 (the game's own origin)."""
    P = mesh.points * np.array([1.0, -1.0, 1.0]) / 100.0
    V, T = simplify(P, mesh.tris, GUN_TRIS)
    return {"V": V, "T": T, "N": normals(V, T)}


def guns_dir(dest: Path) -> Path:
    return Path(dest) / "guns"


def build_guns(files: gf.GameFiles, dest: Path, log=None) -> dict:
    """Converts every gun's default model that's new or changed into <dest>/guns. -> the index
    {code: {"hash", "tris", "src"}}."""
    say = log or (lambda *_: None)
    out = guns_dir(dest)
    idx = read_index(out)
    found = files.gun_models()
    if not found:
        return idx
    out.mkdir(parents=True, exist_ok=True)
    for code, f in sorted(found.items()):
        sig = f"{GUN_VERSION}:{f.name}:{f.stat().st_size}"
        if idx.get(code, {}).get("src") == sig and (out / f"{code.lower()}.bin.gz").is_file():
            continue
        mesh = gf.read_mesh(f)
        if mesh is None or not len(mesh.tris):
            say(f"gun {code}: no model in {f.name}")
            continue
        blob = pack(convert_gun(mesh))
        tmp = out / f"{code.lower()}.tmp"
        with gzip.open(tmp, "wb", compresslevel=6) as fh:
            fh.write(blob)
        tmp.replace(out / f"{code.lower()}.bin.gz")
        head = json.loads(blob[8:8 + struct.unpack("<I", blob[4:8])[0]])
        idx[code] = {"hash": hashlib.sha1(blob).hexdigest()[:12], "tris": head["nt"], "src": sig}
        say(f"gun {code}: {head['nt']} triangles")
    (out / "index.json").write_text(json.dumps(idx, indent=1))
    return idx


def read_index(dest: Path) -> dict:
    try:
        return json.loads((Path(dest) / "index.json").read_text())
    except (OSError, ValueError):
        return {}
