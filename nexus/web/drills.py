"""4.51: Practice › Aim on maps (per player): your deaths as aim drills on the real maps (stats/drills.py).

/profiles/<pid>/aim/maps lists them (one card per spot); /profiles/<pid>/aim/drill/<id> plays one (static/drill.js
in the 3D map of map3d.js, with the animated agents and guns of 4.50); the runs go to data/profiles/<pid>/stats/
drills.json. The drills of a match are worked out once in the background (it needs the replay lined up, line of
sight and callouts: a few seconds per match) and kept in data/drills/<match id>.json.

Your keys (Settings in a drill, or the Keys button on the list): per user in data/aim/keys-<uid>.json."""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from flask import abort, g, jsonify, render_template, request, url_for

from .. import replayfile
from ..stats import drills as dr
from .aim import _lock, _read, _write
from .replays import match_brief, replays_dir

log = logging.getLogger(__name__)
MATCHES = {"10": 10, "30": 30, "all": 400}     # "From" on the page: the last this-many matches with a replay


def keys_file(data_dir, uid: int) -> Path:
    return Path(data_dir) / "aim" / f"keys-{int(uid)}.json"


def read_keys(data_dir, uid: int) -> dict:
    d = _read(keys_file(data_dir, uid), {})
    return dr.clean_keys(d) if d else dr.default_keys()


def register(app, store, sr, view_profile) -> None:
    from .replayview import UTIL_COL as COLS
    data_dir = Path(store.data_dir)
    jobs: dict[int, dict] = {}                  # pid -> {"running", "done", "total"}
    jobs_lock = threading.Lock()

    def ctx_of(mid: str, region: str):
        return app.extensions["nexus"]["replay_ctx"](mid, region)

    def stats_dir(pid: int) -> Path:
        return sr.games(pid).path.parent

    def my_matches(p, limit: int) -> list[str]:
        """Match ids with a replay that this player played in, newest first."""
        have = set(replayfile.stored(replays_dir(store)))
        try:
            rows = list(sr.games(p.id).rows())
        except Exception:
            rows = []
        started: dict[str, str] = {}
        for r in rows:
            mid = (r.get("match_id") or "").lower()
            if mid in have:
                started[mid] = r.get("started_at") or ""
        for mid in have - set(started):          # Customs and others the stats import doesn't have
            b = match_brief(store, mid, p.riot_id)
            if b and b.get("played"):
                started[mid] = b.get("started_at") or ""
        return sorted(started, key=lambda m: started[m], reverse=True)[:limit]

    def signature(mid: str, map_name: str) -> str:
        f = replayfile.data_file(replays_dir(store), mid)
        try:
            st = f.stat()
            rep = f"{st.st_size}:{int(st.st_mtime)}"
        except OSError:
            rep = "?"
        game = app.extensions["nexus"].get("game")
        meta = game.meta(map_name) if game is not None and map_name else None
        return f"{rep}:{(meta or {}).get('hash', '')}"

    def drills_for(mid: str, p) -> list[dict] | None:
        """This player's drills in a match (from the cache, or None: not worked out yet)."""
        brief = match_brief(store, mid, p.riot_id) or {}
        cached = dr.read_cached(data_dir, mid, signature(mid, brief.get("map") or ""))
        if cached is None:
            return None
        return cached.get(p.riot_id.lower(), [])

    def build(mid: str, p) -> None:
        """Works out the drills of every player of the match (kept by Riot ID: a teammate's page finds his)."""
        c = ctx_of(mid, p.region)
        if c is None:
            dr.write_cached(data_dir, mid, signature(mid, ""), {})
            return
        by = dr.drills_of(c)
        players = {f"{pl.name}#{pl.tag}".lower(): by.get(q, []) for q, pl in c.match.players.items()}
        dr.write_cached(data_dir, mid, signature(mid, c.match.map_name), players)

    def start_job(p, mids: list[str]) -> None:
        with jobs_lock:
            j = jobs.get(p.id)
            if j and j.get("running"):
                return
            j = jobs[p.id] = {"running": True, "done": 0, "total": len(mids)}

        def run():
            try:
                for mid in mids:
                    try:
                        build(mid, p)
                    except Exception:
                        log.exception("aim drills of %s", mid)
                        dr.write_cached(data_dir, mid, "error", {})
                    j["done"] += 1
            finally:
                j["running"] = False
        threading.Thread(target=run, name="nexus-drills", daemon=True).start()

    def card(s: dict, pid: int) -> dict:
        d = s["drill"]
        return {**{k: d[k] for k in ("id", "map", "where", "kwhere", "killer_name", "killer_agent", "weapon", "his",
                                     "first", "unseen", "open_to", "started", "round")},
                "count": s["count"], "ids": s["ids"], "best": s["best"], "beaten": s["beaten"], "played": s["played"],
                "url": url_for("aim_drill", pid=pid, drill_id=d["id"])}

    def collect(p, limit: int) -> tuple[list[dict], list[str], list[str]]:
        """-> (drills, matches still to work out, matches whose map isn't built from the game's files)"""
        out, todo, no_map = [], [], []
        game = app.extensions["nexus"].get("game")
        for mid in my_matches(p, limit):
            brief = match_brief(store, mid, p.riot_id) or {}
            if game is None or not game.meta(brief.get("map") or ""):
                no_map.append(brief.get("map") or "?")
                continue
            got = drills_for(mid, p)
            if got is None:
                todo.append(mid)
            else:
                out += got
        return out, todo, no_map

    @app.get("/profiles/<int:pid>/aim/maps")
    def aim_maps(pid: int):
        p, can_edit = view_profile(pid)
        boot = {"api": url_for("aim_drills_api", pid=pid), "keys": read_keys(data_dir, g.user.id),
                "actions": [[a, lbl] for a, (lbl, _d) in dr.ACTIONS.items()], "defaults": dr.default_keys(),
                "keys_api": url_for("aim_keys"), "pid": pid}
        return render_template("aim_maps.html", p=p, active_pid=pid, can_edit=can_edit, boot=boot)

    @app.get("/api/profiles/<int:pid>/aim/drills")
    def aim_drills_api(pid: int):
        p, _e = view_profile(pid)
        limit = MATCHES.get(request.args.get("from", "10"), 10)
        drills, todo, no_map = collect(p, limit)
        if todo:
            start_job(p, todo)
        runs = dr.read_runs(stats_dir(pid))
        spots = dr.group(drills, runs)
        maps = sorted({d["map"] for d in drills})
        j = jobs.get(p.id) or {}
        return jsonify(spots=[card(s, pid) for s in spots], deaths=len(drills), maps=maps,
                       pending=len(todo), working=bool(j.get("running")), no_map=sorted(set(no_map)))

    def find_drill(p, drill_id: str) -> dict | None:
        mid = drill_id.rsplit("-", 2)[0]
        if not mid or len(drill_id) > 80:
            return None
        got = drills_for(mid, p)
        if got is None:
            build(mid, p)
            got = drills_for(mid, p) or []
        return next((d for d in got if d["id"] == drill_id), None)

    @app.get("/profiles/<int:pid>/aim/drill/<drill_id>")
    def aim_drill(pid: int, drill_id: str):
        p, can_edit = view_profile(pid)
        d = find_drill(p, drill_id)
        if d is None:
            abort(404)
        setup = _read(stats_dir(pid) / "trainer.json", {}).get("setup", {})
        runs = dr.read_runs(stats_dir(pid)).get(drill_id, [])
        nxt = [x for x in (request.args.get("queue") or "").split(",") if x and x != drill_id][:40]
        ext = app.extensions["nexus"]
        boot = {"map": d["map"], "api": "/api/maps3d/", "drill": d, "pid": pid, "replay": False,
                "round_api": f"/api/replay/{d['mid']}/round/{d['round']}?pid={pid}",
                "runs_api": url_for("aim_drill_runs", pid=pid, drill_id=drill_id), "can_save": can_edit,
                "sens": setup.get("sens") or 0.4, "dpi": setup.get("dpi") or 800, "scale": setup.get("scale") or 1,
                "keys": read_keys(data_dir, g.user.id), "actions": [[a, lbl] for a, (lbl, _d) in dr.ACTIONS.items()],
                "keys_api": url_for("aim_keys"), "defaults": dr.default_keys(), "gun": dr.gun(d["my_weapon"]), "his_gun": dr.gun(d["weapon"]),
                "guns": {n: dr.gun(n) for n in dr.GUNS}, "hp": dr.HP, "history": dr.summary(runs),
                "list": url_for("aim_maps", pid=pid), "queue": nxt,
                "next": url_for("aim_drill", pid=pid, drill_id=nxt[0]) + ("?queue=" + ",".join(nxt[1:]) if nxt[1:] else "")
                if nxt else "",
                "util_col": COLS,
                "watch": url_for("replay_view", pid=pid, match_id=d["mid"]) + f"?round={d['round']}",
                "agents": ext.get("agents_boot", dict)(),
                **ext.get("motion_boot", lambda: {"anims": None, "guns": {}})()}
        return render_template("drill_view.html", p=p, active_pid=pid, d=d, boot=boot)

    @app.post("/api/profiles/<int:pid>/aim/drill/<drill_id>/runs")
    def aim_drill_runs(pid: int, drill_id: str):
        p, can_edit = view_profile(pid)
        if not can_edit:
            abort(403)
        if find_drill(p, drill_id) is None:
            abort(404)
        run = dr.clean_run(request.get_json(silent=True) or {})
        if run is None:
            return jsonify(error="That's no run."), 400
        with _lock:
            data = dr.add_run(stats_dir(pid), drill_id, run)
        return jsonify(ok=True, history=dr.summary(data.get(drill_id, [])))

    @app.route("/api/aim/keys", methods=["GET", "POST"])
    def aim_keys():
        if request.method == "GET":
            return jsonify(keys=read_keys(data_dir, g.user.id), defaults=dr.default_keys())
        keys = dr.clean_keys(request.get_json(silent=True) or {})
        with _lock:
            _write(keys_file(data_dir, g.user.id), keys)
        return jsonify(ok=True, keys=keys, clashes=dr.clashes(keys))
