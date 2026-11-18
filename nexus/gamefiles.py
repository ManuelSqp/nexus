"""The game's own files, exported with FModel (4.48): map layouts, meshes and agent models as USD text (.usda).

Nexus never ships these files. They're exported on a PC that has VALORANT installed (FModel, meshes as USD, LOD0, no
textures) and copied to the server under data/game/ (README › 3D maps from the game files). From them Nexus builds
plain one-colour maps and agent models (stats/mapmesh.py, stats/agentmesh.py); the built files stay in data/ too.

What's read:
- a map's layout: the top level file (<codename>.usda, e.g. Duality.usda for Bind) with its sublevels, every object
  in them with its place, rotation and size, and a reference to the object's mesh file;
- mesh files: points and faces (and for agents the skeleton and skin weights).

The layout points to meshes with paths relative to the game's folders (../../Environment/Asset/…). The exports may
sit anywhere under data/game, so a reference is looked up below the export's ShooterGame/Content (or Engine/Content),
and by file name as the last resort.

Coordinates are the game's: centimetres, Z up (metersPerUnit 0.01). USD stores rotations as (w, x, y, z)."""
from __future__ import annotations

import os
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# map codenames (the layout's file name; valorant-api.com's mapUrl ends in it)
CODENAMES = {
    "Ascent": "Ascent", "Bind": "Duality", "Haven": "Triad", "Split": "Bonsai", "Icebox": "Port",
    "Breeze": "Foxtrot", "Fracture": "Canyon", "Pearl": "Pitt", "Lotus": "Jam", "Sunset": "Juliett",
    "Abyss": "Infinity", "Corrode": "Rook", "Summit": "Plummet", "The Range": "Range",
}


def game_dir(data_dir) -> Path:
    return Path(data_dir) / "game"


# ------------------------------------------------------------------------------------------------ small math
def quat_matrix(w: float, x: float, y: float, z: float) -> np.ndarray:
    n = (w * w + x * x + y * y + z * z) ** 0.5 or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def trs(t=(0, 0, 0), q=(1, 0, 0, 0), s=(1, 1, 1)) -> np.ndarray:
    """4x4 matrix (column vectors) for translate · orient · scale, the order every layout uses."""
    m = np.eye(4)
    m[:3, :3] = quat_matrix(*q) * np.asarray(s, float)[None, :]
    m[:3, 3] = t
    return m


# ------------------------------------------------------------------------------------------------ number arrays
_NUM_SPLIT = re.compile(r"[()\[\]\s]+")


def _floats(text: str) -> np.ndarray:
    s = _NUM_SPLIT.sub(" ", text).replace(",", " ").strip()
    if not s:
        return np.zeros(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            a = np.fromstring(s, sep=" ")
            if a.size:
                return a
        except Exception:
            pass
    return np.array(s.split(), float)


def _array(text: str, name: str) -> str | None:
    """The text of `<type> name = [ ... ]` (arrays never nest brackets in these files)."""
    m = re.search(r"\b" + re.escape(name) + r"\s*=\s*\[", text)
    if not m:
        return None
    end = text.find("]", m.end())
    return text[m.end():end] if end > 0 else None


# ------------------------------------------------------------------------------------------------ meshes
@dataclass
class Mesh:
    points: np.ndarray                 # (n, 3) float, cm
    tris: np.ndarray                   # (m, 3) int
    materials: list[str] = field(default_factory=list)
    # agents (skinned meshes): joint names, their bind matrices, per-vertex joint indices and weights
    joints: list[str] = field(default_factory=list)
    bind: np.ndarray | None = None     # (j, 4, 4) world matrices of the joints in the bind pose
    jidx: np.ndarray | None = None     # (n, k) int
    jw: np.ndarray | None = None       # (n, k) float
    glass_tris: np.ndarray | None = None   # (m,) bool: the triangle's material is glass (4.49: per face, not per mesh)

    @property
    def glass(self) -> bool:
        return bool(self.glass_tris is not None and self.glass_tris.any())

    def split(self) -> tuple["Mesh | None", "Mesh | None"]:
        """-> (the mesh without its glass, its glass) — a building with one window is a wall, not glass."""
        if self.glass_tris is None or not self.glass_tris.any():
            return self, None
        g = self.glass_tris
        solid = Mesh(self.points, self.tris[~g], self.materials) if (~g).any() else None
        return solid, Mesh(self.points, self.tris[g], self.materials)


def triangulate(counts: np.ndarray, idx: np.ndarray, faces: bool = False):
    """Faces with any number of corners -> triangles (fans); with faces: also each triangle's face."""
    counts = counts.astype(np.int64)
    if counts.size and (counts == 3).all():
        t = idx.reshape(-1, 3)
        return (t, np.arange(len(t))) if faces else t
    out, fid = [], []
    pos = 0
    for n, c in enumerate(counts):
        f = idx[pos:pos + c]
        for k in range(1, c - 1):
            out.append((f[0], f[k], f[k + 1]))
            fid.append(n)
        pos += c
    t = np.array(out, np.int64).reshape(-1, 3)
    return (t, np.array(fid, np.int64)) if faces else t


_SUBSET = re.compile(r'def GeomSubset "[^"]*"(.*?)rel material:binding = <[^>]*/([^/>]+)>', re.S)


def _glass_faces(text: str, n_faces: int) -> np.ndarray | None:
    """Faces bound to a glass material (GeomSubsets), or None when nothing is glass."""
    if "glass" not in text.lower():
        return None
    out = np.zeros(n_faces, bool)
    for body, mat in _SUBSET.findall(text):
        if "glass" not in mat.lower():
            continue
        ix = _array(body, "indices")
        if ix is None:
            continue
        i = _floats(ix).astype(np.int64)
        out[i[(i >= 0) & (i < n_faces)]] = True
    if not _SUBSET.search(text) and any("glass" in m.lower() for m in re.findall(r'def Material "([^"]+)"', text)):
        out[:] = True                                    # one material for the whole mesh, and it's glass
    return out if out.any() else None


def read_mesh(path: Path) -> Mesh | None:
    try:
        text = Path(path).read_text(errors="ignore")
    except OSError:
        return None
    pts, counts, idx = _array(text, "points"), _array(text, "faceVertexCounts"), _array(text, "faceVertexIndices")
    if pts is None or counts is None or idx is None:
        return None
    p = _floats(pts)
    if p.size < 9 or p.size % 3:
        return None
    p = p.reshape(-1, 3)
    c, i = _floats(counts).astype(np.int64), _floats(idx).astype(np.int64)
    if not c.size or c.sum() != i.size:
        return None
    tris, fid = triangulate(c, i, faces=True)
    ok = (tris >= 0).all(1) & (tris < len(p)).all(1)
    tris, fid = tris[ok], fid[ok]
    mats = re.findall(r'def Material "([^"]+)"', text)
    m = Mesh(p, tris, mats)
    gf_ = _glass_faces(text, len(c))
    if gf_ is not None:
        m.glass_tris = gf_[fid]
    if "skel:jointIndices" in text:
        _read_skin(text, m)
    return m


def _read_skin(text: str, m: Mesh) -> None:
    joints = _array(text, "uniform token[] joints") or _array(text, "joints")
    if joints is None:
        return
    m.joints = re.findall(r'"([^"]+)"', joints)
    bt = _array(text, "bindTransforms")
    if bt is not None:
        a = _floats(bt)
        if a.size == 16 * len(m.joints):
            m.bind = a.reshape(-1, 4, 4).transpose(0, 2, 1)      # USD writes rows: row-vector convention
    ji, jw = _array(text, "primvars:skel:jointIndices"), _array(text, "primvars:skel:jointWeights")
    k = re.search(r"primvars:skel:jointIndices\s*=\s*\[[^\]]*\]\s*\(\s*elementSize\s*=\s*(\d+)", text)
    if ji is not None and jw is not None:
        i, w = _floats(ji).astype(np.int64), _floats(jw)
        n = len(m.points)
        es = int(k.group(1)) if k else (i.size // n if n else 0)
        if es and i.size == n * es and w.size == n * es:
            m.jidx, m.jw = i.reshape(n, es), w.reshape(n, es)


# ------------------------------------------------------------------------------------------------ layouts
@dataclass
class Placed:
    """One object of a layout: its mesh file and where it is (a 4x4 matrix, or many for an instanced mesh)."""
    ref: str                           # the reference as written in the layout
    base: Path                         # the layout file's folder (references are relative to it)
    mats: np.ndarray                   # (k, 4, 4)
    layer: str                         # the sublevel's file name
    name: str                          # the actor's name (Scope above the mesh)
    invisible: bool = False


_DEF = re.compile(r'^\s*(def|over|class)\s+(\w+)\s+"([^"]*)"')
_REF = re.compile(r"references\s*=\s*@([^@]+)@")
_VEC = re.compile(r"\(([^)]*)\)")


def _vec(line: str) -> list[float]:
    m = _VEC.search(line.split("=", 1)[1])
    return [float(x) for x in m.group(1).split(",")] if m else []


def read_layout(path: Path) -> tuple[list[str], list[Placed]]:
    """A layout file: its sublevel files (relative paths) and the objects placed in it."""
    text = Path(path).read_text(errors="ignore")
    sub = []
    head = text[:text.find("\ndef ")] if "\ndef " in text else text[:4000]
    m = re.search(r"subLayers\s*=\s*\[([^\]]*)\]", head)
    if m:
        sub = re.findall(r"@([^@]+)@", m.group(1))
    return sub, _placed(text, Path(path))


def _placed(text: str, path: Path) -> list[Placed]:
    out: list[Placed] = []
    # a stack of prims: [kind, name, matrix (local), world matrix, ref, invisible, instancer data]
    stack: list[dict] = []
    pending: dict | None = None         # a prim whose "(" metadata or "{" hasn't started yet
    lines = text.split("\n")
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        i += 1
        if not s:
            continue
        d = _DEF.match(line)
        if d:
            pending = {"spec": d.group(1), "kind": d.group(2), "name": d.group(3), "ref": None, "local": None,
                       "t": None, "q": None, "s": None, "inv": False, "pi": None}
            if s.endswith("("):                          # metadata until a line that is just ")"
                while i < n:
                    ml = lines[i].strip()
                    i += 1
                    r = _REF.search(ml)
                    if r:
                        pending["ref"] = r.group(1)
                    if ml == ")":
                        break
            continue
        if s == "{":
            if pending is None:
                pending = {"spec": "?", "kind": "?", "name": "", "ref": None, "t": None, "q": None, "s": None,
                           "inv": False, "pi": None}
            stack.append(pending)
            pending = None
            continue
        if s == "}":
            if stack:
                _close(stack, out, path)
            continue
        if not stack:
            continue
        top = stack[-1]
        if "xformOp:translate =" in s:
            top["t"] = _vec(s)
        elif "xformOp:orient =" in s:
            top["q"] = _vec(s)
        elif "xformOp:scale =" in s:
            top["s"] = _vec(s)
        elif s.startswith("token visibility") and '"invisible"' in s:
            top["inv"] = True
        elif top["kind"] == "PointInstancer":
            pi = top["pi"] = top["pi"] or {}
            for key in ("protoIndices", "positions", "orientations", "scales"):
                if re.match(r"[\w\[\]]+\s+" + key + r"\s*=", s):
                    body = s.split("=", 1)[1]
                    while body.count("[") > body.count("]") and i < n:       # long arrays may wrap
                        body += lines[i]
                        i += 1
                    pi[key] = body
            if s.startswith("rel prototypes"):
                pi["protos"] = re.findall(r"<([^>]+)>", s)
    return out


def _local(p: dict) -> np.ndarray:
    if p["t"] is None and p["q"] is None and p["s"] is None:
        return np.eye(4)
    q = p["q"] or [1, 0, 0, 0]
    return trs(p["t"] or (0, 0, 0), q if len(q) == 4 else (1, 0, 0, 0), p["s"] or (1, 1, 1))


def _close(stack: list[dict], out: list, path: Path) -> None:
    p = stack.pop()
    parents = stack
    world = np.eye(4)
    for a in parents:
        if a["kind"] in ("Xform", "Mesh", "PointInstancer"):
            world = world @ _local(a)
    actor = next((a["name"] for a in reversed(parents) if a["kind"] == "Scope" and a["name"] not in
                  ("Prototypes", "OverrideMaterials")), p["name"])
    inv = p["inv"] or any(a["inv"] for a in parents)
    in_proto = any(a["name"] == "Prototypes" and a["kind"] == "Scope" for a in parents)
    if p["kind"] == "Mesh" and p["ref"] and not in_proto:
        out.append(Placed(p["ref"], path.parent, (world @ _local(p))[None], path.name, actor, inv))
    elif p["kind"] == "PointInstancer" and p.get("pi"):
        pi = p["pi"]
        protos = []
        # the prototypes are the Mesh prims under this instancer (in order of `rel prototypes`)
        for key in pi.get("protos", []):
            protos.append(key.rsplit("/", 1)[-1])
        refs = p.get("proto_refs") or {}
        mats_by_proto: dict[int, list] = {}
        try:
            idx = _floats(pi.get("protoIndices", "")).astype(int)
            pos = _floats(pi.get("positions", "")).reshape(-1, 3)
            ori = _floats(pi.get("orientations", "")).reshape(-1, 4)
            sc = _floats(pi.get("scales", "")).reshape(-1, 3) if "scales" in pi else np.ones((len(pos), 3))
        except ValueError:
            return
        base = world @ _local(p)
        for k in range(min(len(idx), len(pos), len(ori))):
            mats_by_proto.setdefault(int(idx[k]), []).append(base @ trs(pos[k], ori[k], sc[k] if k < len(sc) else (1, 1, 1)))
        for pk, ms in mats_by_proto.items():
            name = protos[pk] if pk < len(protos) else None
            ref = refs.get(name) if name else None
            if ref is None and len(refs) == 1:
                ref = next(iter(refs.values()))
            if ref:
                out.append(Placed(ref, path.parent, np.array(ms), path.name, actor, inv))
    # a prototype mesh tells its instancer which file it is
    if p["kind"] == "Mesh" and p["ref"] and in_proto:
        for a in reversed(parents):
            if a["kind"] == "PointInstancer":
                a.setdefault("proto_refs", {})[p["name"]] = p["ref"]
                break


# ------------------------------------------------------------------------------------------------ the export
class GameFiles:
    """Finds files in the exports under data/game."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._content: list[Path] | None = None
        self._engine: list[Path] | None = None
        self._by_name: dict[str, list[Path]] | None = None

    def exists(self) -> bool:
        return self.root.is_dir() and any(self.root.iterdir())

    def _roots(self) -> None:
        if self._content is not None:
            return
        self._content, self._engine = [], []
        for dirpath, dirnames, _files in os.walk(self.root, followlinks=True):
            p = Path(dirpath)
            if p.name == "Content" and p.parent.name == "ShooterGame":
                self._content.append(p)
                dirnames[:] = []
            elif p.name == "Content" and p.parent.name == "Engine":
                self._engine.append(p)
                dirnames[:] = []
            elif dirpath.count(os.sep) - str(self.root).count(os.sep) > 4:
                dirnames[:] = []

    def _index(self) -> dict[str, list[Path]]:
        if self._by_name is None:
            self._by_name = {}
            for dirpath, _d, files in os.walk(self.root, followlinks=True):
                for f in files:
                    if f.endswith(".usda"):
                        self._by_name.setdefault(f.lower(), []).append(Path(dirpath) / f)
        return self._by_name

    def resolve(self, ref: str, base: Path) -> Path | None:
        direct = Path(os.path.normpath(Path(base) / ref))
        if direct.is_file() and str(direct).startswith(str(self.root)):
            return direct
        parts = [x for x in ref.replace("\\", "/").split("/") if x not in ("", ".", "..")]
        if not parts:
            return None
        self._roots()
        if parts[0] == "Engine":
            rest = parts[2:] if len(parts) > 2 and parts[1] == "Content" else parts[1:]
            for e in self._engine:
                f = e.joinpath(*rest)
                if f.is_file():
                    return f
        else:
            rest = parts[2:] if parts[0] == "ShooterGame" and len(parts) > 2 else parts
            for c in self._content:
                f = c.joinpath(*rest)
                if f.is_file():
                    return f
        cands = self._index().get(parts[-1].lower(), [])
        if not cands:
            return None
        tail = "/".join(parts[-3:]).lower()                 # the same name in several folders: the closest path
        for c in cands:
            if str(c).replace("\\", "/").lower().endswith(tail):
                return c
        return cands[0]

    def layout(self, codename: str) -> Path | None:
        """The top layout file of a map: <codename>.usda that lists sublevels (the most complete one)."""
        best, score = None, -1
        for f in self._index().get(f"{codename.lower()}.usda", []):
            try:
                sub, _ = read_layout_head(f)
            except OSError:
                continue
            if not sub:
                continue
            have = sum(1 for s in sub if (f.parent / s).is_file())
            if have > score:
                best, score = f, have
        return best

    def agent_models(self) -> dict[str, Path]:
        """codename (Wushu, Clay, …) -> its third-person model."""
        out: dict[str, Path] = {}
        self._roots()
        for c in self._content:
            ch = c / "Characters"
            if not ch.is_dir():
                continue
            for d in sorted(ch.iterdir()):
                models = d / "S0" / "3P" / "Models"
                if not models.is_dir():
                    continue
                files = sorted(models.glob("TP_*Skelmesh*.usda"))
                if not files:
                    continue
                exact = [f for f in files if f.stem == f"TP_{d.name}_S0_Skelmesh"]
                plain = [f for f in files if not re.search(r"(Mannequin|Sym|Prototype|Old)", f.stem)]
                out.setdefault(d.name, (exact or plain or files)[0])
        return out


    def gun_models(self) -> dict[str, Path]:
        """Gun codename (AK, Carbine, …: the folder under Equippables/Guns/<kind>/) -> its default model (the S0 skin,
        "GN_<code>_S0_Skelmesh"). The first-person model: the game shows the same one in third person."""
        out: dict[str, Path] = {}
        pat = re.compile(r"^gn_([a-z0-9]+)_s0_skelmesh\.usda$")
        for name, paths in self._index().items():
            if not pat.match(name):
                continue
            for f in sorted(paths):
                parts = f.parts
                if "Guns" not in parts or "Attachments" in parts or len(parts) < 5 or parts[-3:-1] != ("1P", "Models") or parts[-4] != "S0":
                    continue
                code = parts[-5]
                if code.lower() == pat.match(name).group(1):
                    out.setdefault(code, f)
        return out

    def find(self, stem: str, *needles: str) -> Path | None:
        """A .usda file by its name (without .usda) whose path contains all `needles` (the first one, sorted)."""
        for f in sorted(self._index().get(f"{stem.lower()}.usda", [])):
            s = str(f).replace("\\", "/")
            if all(n in s for n in needles):
                return f
        return None


def read_layout_head(path: Path) -> tuple[list[str], int]:
    with open(path, errors="ignore") as fh:
        head = fh.read(20000)
    m = re.search(r"subLayers\s*=\s*\[([^\]]*)\]", head)
    return (re.findall(r"@([^@]+)@", m.group(1)) if m else []), 0
