"""Practice › 3D maps (per player, the maps are the same for everyone): walk around a map. The page renders and
moves in the browser (static/map3d.js).

4.48: where the game's files are on the server (data/game, web/gamebuild.py) the map is the real one built from
them (stats/mapmesh.py); otherwise it's rebuilt from the replays on the server (stats/map3d.py)."""
from __future__ import annotations

import json
import time
import threading

from flask import abort, jsonify, render_template

from ..maps import MapRegistry
from ..parse import parse_match
from ..stats import agentmesh as am
from ..stats import map3d as m3
from .aim import _read
from .gamebuild import GameBuilder
from .gamebuild import register as register_game

_lock = threading.Lock()


def register(app, store, sr, view_profile, known_maps: list[str]) -> None:
    cache = store.data_dir / "cache"
    reg = MapRegistry(cache)
    out_dir = store.data_dir / "maps3d"
    replays_dir = store.data_dir / "replays"

    def map_of(mid: str) -> str | None:
        idx = _read(out_dir / "index.json", {})
        if mid in idx:
            return idx[mid]
        raw = None
        for name in (mid, mid.lower(), mid.upper()):
            f = cache / "matches" / f"{name}.json"
            if f.is_file():
                raw = _read(f, None)
                break
        if not raw:
            return None
        try:
            name = parse_match(raw).map_name
        except Exception:
            return None
        with _lock:
            idx = _read(out_dir / "index.json", {})
            idx[mid] = name
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.json").write_text(json.dumps(idx))
        return name

    def built(name: str, ids: list[str]) -> dict | None:
        """The rebuilt map, from the cache while the set of replays is the same."""
        f = out_dir / f"{name.lower()}.json"
        d = _read(f, {})
        if d.get("ids") == sorted(ids) and d.get("version") == m3.VERSION and \
                not (d.get("no_minimap") and time.time() - d.get("at", 0) > 3600):     # try the minimap again hourly
            return d
        mi = reg.get(name=name)
        if mi is None:
            return None
        try:                                              # 4.45: the minimap fills what no replay covered
            mm = reg.minimap_image(mi)
            mask = m3.minimap_mask(mm) if mm else None
        except Exception:
            mask = None
        d = m3.rebuild(mi, m3.load_replays(replays_dir, ids), name, walkable=mask)
        d["ids"] = sorted(ids)
        d["at"] = int(time.time())
        d["no_minimap"] = mask is None
        with _lock:
            out_dir.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(d, separators=(",", ":")))
        return d

    warmed: dict[str, list[str]] = {}

    def warm() -> None:
        """Every 5 minutes (the scheduler): rebuild a map whose replays changed, so the page doesn't wait for it
        (a few seconds per map with several full replays)."""
        for name, ids in m3.replays_by_map(replays_dir, map_of).items():
            if warmed.get(name) != sorted(ids):
                built(name, ids)
                warmed[name] = sorted(ids)
    app.extensions["nexus"].setdefault("ticks", []).append(warm)
    app.extensions["nexus"]["maps3d_warm"] = warm          # for tests
    game = GameBuilder(store.data_dir, map_of)
    register_game(app, store, game)

    def agents_boot() -> dict:
        """Agent name -> model URL, for the agents built from the game's files (4.48)."""
        idx = game.agent_index()
        if not idx:
            return {}
        try:
            from ..maps import AgentRegistry
            dev = {a["name"]: a["dev"] for a in AgentRegistry(cache).load() if a.get("dev")}
        except Exception:
            dev = {}
        out = {}
        for name, code in dev.items():
            key = next((k for k in idx if k.lower() == code.lower()), None)
            if key:
                out[name] = f"/api/agents3d/{key}?h={idx[key].get('hash', '')}"
        return out
    app.extensions["nexus"]["agents_boot"] = agents_boot

    def motion_boot() -> dict:
        """4.50: {"anims": URL of the animations or None, "guns": {weapon name (Vandal…): URL of its model}}."""
        meta = game.anims()
        guns = game.gun_index()
        out = {}
        for name, code in am.WEAPONS.items():
            key = next((k for k in guns if k.lower() == code.lower()), None)
            if key:
                out[name] = f"/api/guns3d/{key}?h={guns[key].get('hash', '')}"
        return {"anims": f"/api/anims3d?h={meta.get('hash', '')}" if meta.get("hash") else None, "guns": out}
    app.extensions["nexus"]["motion_boot"] = motion_boot

    @app.get("/profiles/<int:pid>/maps3d")
    def maps3d(pid: int):
        p, can_edit = view_profile(pid)
        by = m3.replays_by_map(replays_dir, map_of)
        maps = [{"name": m, "replays": len(by.get(m, []))} for m in sorted(set(known_maps) | set(by))]
        maps.sort(key=lambda x: (-x["replays"], x["name"]))
        setup = _read(sr.games(pid).path.parent / "trainer.json", {}).get("setup", {})
        boot = {"maps": maps, "api": "/api/maps3d/", "sens": setup.get("sens") or 0.4}
        game_maps = {m["name"] for m in maps if game.meta(m["name"])}
        for m in maps:
            m["game"] = m["name"] in game_maps
        return render_template("maps3d.html", p=p, active_pid=pid, maps=maps, boot=boot,
                               game_files=game.available(), game_maps=game_maps)

    @app.get("/api/maps3d/<name>")
    def maps3d_data(name: str):
        if not name.replace(" ", "").isalnum() or len(name) > 30:
            abort(404)
        by = m3.replays_by_map(replays_dir, map_of)
        real = next((m for m in sorted(set(known_maps) | set(by)) if m.lower() == name.lower()), None)
        if real is None:                                  # a map valorant-api.com knows (a new one, say)
            try:
                mi = reg.get(name=name)
            except Exception:
                mi = None
            real = mi.name if mi is not None else None
        if real is None:
            return jsonify(error="That map isn't known."), 404
        meta = game.meta(real)                            # 4.48: the real map from the game's files
        if meta is not None:
            out = {k: v for k, v in meta.items() if k not in ("source",)}
            out.update(mesh=f"/api/maps3d/{real}/mesh?h={meta.get('hash', '')}", matches=len(by.get(real, [])),
                       game=True)
            return jsonify(out)
        if game.pending(real):                            # 4.53.2: not the map from the replays: wait for the real one
            game.start()
            return jsonify(building=True, error="The map is being built from the game's files (a minute or two)…"), 202
        d = built(real, by.get(real, []))                # 4.45: without replays: flat, from the minimap
        if d is None or not d["cells"]:
            return jsonify(error="The map data isn't loaded yet (valorant-api.com)."), 404
        if game.available():
            d = dict(d, game_status=game.status.get(real) or ("building" if game.running else "waiting"))
        return jsonify(d)
