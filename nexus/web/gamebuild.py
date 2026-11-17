"""4.48: maps and agent models built from the game's files on the server (stats/mapmesh.py, stats/agentmesh.py).

The exported files are copied to data/game/ (README › 3D maps from the game files). A background thread builds what's
missing or outdated, one map after the other, at startup and every 10 minutes (a map takes 15–60 s and a few hundred
MB of memory; the agents take a few seconds together); `nexus build-game` does the same from the command line.
A map is built again when its layout files change, when mapmesh.VERSION changes, and once when the first replays of
it arrive (they check the axes and measure where the replays put the feet).

Routes: /api/maps3d/<map>/mesh (the browser's binary mesh, gzipped, cached for a year by its hash) and
/api/agents3d/<code> (an agent model)."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from flask import abort, jsonify, make_response, request

from .. import gamefiles as gf
from ..maps import MapRegistry
from ..stats import agentmesh as am
from ..stats import map3d as m3
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

    def available(self) -> bool:
        return self.root.is_dir() and any(self.root.iterdir())

    def _files(self) -> gf.GameFiles:
        if self.files is None:
            self.files = gf.GameFiles(self.root)
        return self.files

    def samples(self, name: str) -> tuple[list, int]:
        by = m3.replays_by_map(self.data / "replays", self.map_of)
        ids = sorted(by.get(name, []))[-SAMPLE_REPLAYS:]
        pts = []
        for d in m3.load_replays(self.data / "replays", ids):
            for rows in (d.get("pos") or {}).values():
                for r in rows[::20]:
                    if len(r) >= 4:
                        pts.append((r[1], r[2], r[3]))
        return pts, len(ids)

    def needs(self, mi, code: str, n_replays: int) -> bool:
        meta = mm.load_meta(self.out, mi.name)
        if meta is None or not mm.paths(self.out, mi.name)["bin"].is_file():
            return True
        if meta.get("samples_from", 0) == 0 and n_replays > 0:
            return True
        return False

    def build_map(self, mi, force: bool = False, say=None) -> dict | None:
        code = mm.codename(mi.name, getattr(mi, "map_url", ""))
        files = self._files()
        if files.layout(code) is None:
            self.status[mi.name] = "missing"
            return None
        pts, n = self.samples(mi.name)
        if not force and not self.needs(mi, code, n):
            self.status[mi.name] = "built"
            return mm.load_meta(self.out, mi.name)
        self.status[mi.name] = "building"
        try:
            r = mm.build(files, mi, code, pts, log=say or log.info)
        except Exception as e:                       # one bad map doesn't stop the others
            log.exception("building %s from the game files", mi.name)
            self.status[mi.name] = f"error: {type(e).__name__}: {e}"
            return None
        if r is None:
            self.status[mi.name] = "missing"
            return None
        meta, blob, vox = r
        meta["samples_from"] = n
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
            hit = (mt, mm.load_meta(self.out, name))
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

    @app.get("/api/game/status")
    def game_status():
        return jsonify(available=builder.available(), running=builder.running, maps=builder.status,
                       agents=len(builder.agent_index()))
