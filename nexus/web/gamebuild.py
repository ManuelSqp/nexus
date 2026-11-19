"""4.48: maps and agent models built from the game's files on the server (stats/mapmesh.py, stats/agentmesh.py).

The exported files are copied to data/game/ (README › 3D maps from the game files). A background thread builds what's
missing or outdated, one map after the other, at startup and every 10 minutes (a map takes 15–60 s and a few hundred
MB of memory; the agents take a few seconds together); `nexus build-game` does the same from the command line.
A map is built again when its layout files change and when mapmesh.VERSION changes; 4.53: from the game's files
alone (replays don't change it).

Routes: /api/maps3d/<map>/mesh (the browser's binary mesh, gzipped, cached for a year by its hash),
/api/agents3d/<code> (an agent model), 4.50: /api/guns3d/<code> (a gun) and /api/anims3d (the animations)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from flask import abort, jsonify, make_response, request

from .. import gamefiles as gf
from ..maps import MapRegistry
from ..stats import agentanim as aa
from ..stats import agentmesh as am
from ..stats import mapmesh as mm

log = logging.getLogger(__name__)
SAMPLE_REPLAYS = 6
RECHECK_S = 600


def map_of_files(data_dir: Path):
    """match id -> map name from the files alone (the command line has no web app): the 3D maps' index, else the
    cached match details."""
    import json

    from ..parse import parse_match
    data_dir = Path(data_dir)

    def map_of(mid: str):
        try:
            idx = json.loads((data_dir / "maps3d" / "index.json").read_text())
        except (OSError, ValueError):
            idx = {}
        if mid in idx:
            return idx[mid]
        f = data_dir / "cache" / "matches" / f"{mid.lower()}.json"
        try:
            return parse_match(json.loads(f.read_text())).map_name
        except Exception:
            return None
    return map_of


class GameBuilder:
    def __init__(self, data_dir: Path, map_of):
        self.data = Path(data_dir)
        self.root = gf.game_dir(self.data)
        self.out = self.data / "maps3d"
        self.agents = am.out_dir(self.data)
        self.map_of = map_of
        self.files: gf.GameFiles | None = None
        self.status: dict[str, str] = {}             # map name -> "building" | "built" | "missing" | "error: …"
        self.lock = threading.Lock()
        self.running = False
        self.last = 0.0
        self._vox: dict[str, tuple[str, dict]] = {}   # map -> (hash, grid) for line of sight
        self._meta: dict[str, tuple[int, dict | None]] = {}
        self._has: dict[str, bool] = {}

    def available(self) -> bool:
        return self.root.is_dir() and any(self.root.iterdir())

    def _files(self) -> gf.GameFiles:
        if self.files is None:
            self.files = gf.GameFiles(self.root)
        return self.files

    def needs(self, mi) -> bool:
        """Not built yet, or built by an older version (load_meta: None). 4.53: replays don't matter."""
        meta = mm.load_meta(self.out, mi.name)
        return meta is None or not mm.paths(self.out, mi.name)["bin"].is_file()

    def pending(self, name: str) -> bool:
        """4.53.2: is this map going to be built from the game's files (no build yet, not missing, no error)?"""
        if not self.available() or self.meta(name) is not None:
            return False
        st = self.status.get(name, "")
        if st == "missing" or st.startswith("error"):
            return False
        if name not in self._has:                      # its layout is in the export
            try:
                mi = MapRegistry(self.data / "cache").get(name=name)
                code = mm.codename(mi.name, getattr(mi, "map_url", "")) if mi else None
                self._has[name] = bool(code) and self._files().layout(code) is not None
            except Exception:
                self._has[name] = False
        return self._has[name]

    def build_map(self, mi, force: bool = False, say=None) -> dict | None:
        code = mm.codename(mi.name, getattr(mi, "map_url", ""))
        files = self._files()
        if files.layout(code) is None:
            self.status[mi.name] = "missing"
            return None
        if not force and not self.needs(mi):
            self.status[mi.name] = "built"
            return mm.load_meta(self.out, mi.name)
        self.status[mi.name] = "building"
        try:
            r = mm.build(files, mi, code, log=say or log.info)
        except Exception as e:                       # one bad map doesn't stop the others
            log.exception("building %s from the game files", mi.name)
            self.status[mi.name] = f"error: {type(e).__name__}: {e}"
            return None
        if r is None:
            self.status[mi.name] = "missing"
            return None
        meta, blob, vox = r
        mm.save(self.out, mi.name, meta, blob, vox)
        self._vox.pop(mi.name, None)
        self.status[mi.name] = "built"
        return meta

    def build_all(self, force: bool = False, only: str = "", say=None, agents: bool = True) -> None:
        if not self.available():
            return
        try:
            maps = MapRegistry(self.data / "cache").load()
        except Exception:
            maps = []
        for mi in maps:
            if only and mi.name.lower() != only.lower():
                continue
            self.build_map(mi, force=force, say=say)
        if agents and not only:
            try:
                am.build_all(self._files(), self.agents, log=say or log.info)
            except Exception:
                log.exception("building the agent models")
            try:                                     # 4.50: the guns and the animations
                am.build_guns(self._files(), self.agents, log=say or log.info)
            except Exception:
                log.exception("building the gun models")
            try:
                aa.save(self.agents, self._files(), log=say or log.info)
            except Exception:
                log.exception("building the animations")

    def start(self) -> None:
        """Builds in the background (one thread at a time)."""
        if not self.available() or time.time() - self.last < RECHECK_S:
            return
        with self.lock:
            if self.running:
                return
            self.running = True
            self.last = time.time()

        def run():
            try:
                self.build_all()
            finally:
                self.running = False
        threading.Thread(target=run, name="nexus-gamebuild", daemon=True).start()

    # ---------------------------------------------------------------- for the pages
    def meta(self, name: str) -> dict | None:
        f = mm.paths(self.out, name)["meta"]
        try:
            mt = f.stat().st_mtime_ns
        except OSError:
            return None
        hit = self._meta.get(name)
        if hit is None or hit[0] != mt:
            hit = (mt, mm.load_meta(self.out, name, any_version=True))     # 4.53.2: an older build until the new one
            self._meta[name] = hit
        return hit[1]

    def game(self, name: str) -> dict | None:
        """{"meta", "vox"} for the replay viewer (line of sight), or None."""
        meta = self.meta(name)
        if meta is None:
            return None
        h = meta.get("hash", "")
        hit = self._vox.get(name)
        if hit is None or hit[0] != h:
            vox = mm.load_vox(self.out, name)
            hit = (h, vox)
            self._vox[name] = hit
        return {"meta": meta, "vox": hit[1]}

    def agent_index(self) -> dict:
        return am.read_index(self.agents)

    def gun_index(self) -> dict:
        return am.read_index(am.guns_dir(self.agents))

    def anims(self) -> dict:
        return aa.read_meta(self.agents)


def _gz_file(path: Path, h: str):
    if not path.is_file():
        abort(404)
    resp = make_response(path.read_bytes())
    resp.headers["Content-Type"] = "application/octet-stream"
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Cache-Control"] = "private, max-age=31536000, immutable" if request.args.get("h") == h \
        else "private, no-cache"
    resp.headers["ETag"] = f'"{h}"'
    return resp


def register(app, store, builder: GameBuilder) -> None:
    app.extensions["nexus"]["game"] = builder
    app.extensions["nexus"].setdefault("ticks", []).append(builder.start)
    if builder.available():
        builder.start()

    @app.get("/api/maps3d/<name>/mesh")
    def maps3d_mesh(name: str):
        if not name.replace(" ", "").isalnum() or len(name) > 30:
            abort(404)
        meta = builder.meta(name)
        if meta is None:
            abort(404)
        return _gz_file(mm.paths(builder.out, name)["bin"], meta.get("hash", ""))

    @app.get("/api/agents3d/<code>")
    def agents3d(code: str):
        if not code.isalnum() or len(code) > 30:
            abort(404)
        idx = builder.agent_index()
        key = next((k for k in idx if k.lower() == code.lower()), None)
        if key is None:
            abort(404)
        return _gz_file(builder.agents / f"{key.lower()}.bin.gz", idx[key].get("hash", ""))

    @app.get("/api/guns3d/<code>")
    def guns3d(code: str):
        if not code.isalnum() or len(code) > 30:
            abort(404)
        idx = builder.gun_index()
        key = next((k for k in idx if k.lower() == code.lower()), None)
        if key is None:
            abort(404)
        return _gz_file(am.guns_dir(builder.agents) / f"{key.lower()}.bin.gz", idx[key].get("hash", ""))

    @app.get("/api/anims3d")
    def anims3d():
        meta = builder.anims()
        if not meta:
            abort(404)
        return _gz_file(builder.agents / "anims.bin.gz", meta.get("hash", ""))

    @app.get("/api/game/status")
    def game_status():
        return jsonify(available=builder.available(), running=builder.running, maps=builder.status,
                       agents=len(builder.agent_index()), guns=len(builder.gun_index()),
                       animations=len(builder.anims().get("clips", [])))
