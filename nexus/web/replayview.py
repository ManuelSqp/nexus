"""Replay page (4.44): a match's replay in the 3D map, round by round, with the team's comments and the
utility check. /profiles/<pid>/replay/<match id>; for anyone who can open the player (owner or team).

The round data comes from stats/replayview.py; the map itself is the same rebuilt 3D map as Practice › 3D maps
(/api/maps3d/<map>). Comments are kept per match in data/reviews/<match id>.json, so a team reviewing a match
together sees each other's notes whichever player's page they opened it from.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from flask import abort, g, jsonify, render_template, request, url_for

from .. import replayfile
from ..maps import AgentRegistry, MapRegistry
from ..parse import parse_match
from ..stats import replayview as rv
from .replays import fetch_match

MAX_COMMENT = 600
KEEP = 3                                   # matches kept lined up in memory (a replay is a few MB)
_lock = threading.Lock()


def reviews_dir(store) -> Path:
    return Path(store.data_dir) / "reviews"


def read_comments(store, mid: str) -> list[dict]:
    try:
        return json.loads((reviews_dir(store) / f"{mid}.json").read_text())
    except (OSError, ValueError):
        return []


def _write_comments(store, mid: str, items: list[dict]) -> None:
    d = reviews_dir(store)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{mid}.json.tmp"
    tmp.write_text(json.dumps(items))
    os.replace(tmp, d / f"{mid}.json")


def register(app, store, view_profile) -> None:
    cache = Path(store.data_dir) / "cache"
    replays = Path(store.data_dir) / "replays"
    ctxs: OrderedDict[str, rv.Ctx] = OrderedDict()

    def match_of(mid: str):
        for name in (mid, mid.lower(), mid.upper()):
            f = cache / "matches" / f"{name}.json"
            if f.is_file():
                try:
                    return parse_match(json.loads(f.read_text()))
                except Exception:
                    return None
        return None

    def ctx(mid: str, region: str = "") -> rv.Ctx | None:
        mid = mid.lower()
        with _lock:
            if mid in ctxs:
                c = ctxs[mid]
                game = app.extensions["nexus"].get("game")
                stale = c.game is None and game is not None and c.mi is not None and game.meta(c.match.map_name)
                if not stale:                            # 4.48: built from the game's files since: line it up again
                    ctxs.move_to_end(mid)
                    return c
                ctxs.pop(mid)
        try:
            if not replayfile.has_replay(replays, mid):      # also refuses anything that isn't a match id
                return None
        except replayfile.ReplayError:
            return None
        m = match_of(mid)
        if m is None and fetch_match(store, mid, region):    # 4.47: Customs aren't in the stats import
            m = match_of(mid)
        if m is None:
            return None
        try:
            data = replayfile.load(replays, mid)
        except replayfile.ReplayError:
            return None
        if not data:
            return None
        try:
            mi = MapRegistry(cache).get(m.map_id, m.map_name)
        except Exception:
            mi = None
        try:
            names = {a["dev"]: a["name"] for a in AgentRegistry(cache).load() if a.get("dev")}
        except Exception:
            names = {}
        game = app.extensions["nexus"].get("game")              # 4.48: the map from the game's files
        try:
            gd = game.game(m.map_name) if game is not None and mi is not None else None
        except Exception:
            gd = None
        c = rv.Ctx(data, m, mi, names, gd)
        with _lock:
            ctxs[mid] = c
            while len(ctxs) > KEEP:
                ctxs.popitem(last=False)
        return c

    def me_in(c: rv.Ctx, p) -> str:
        rid = p.riot_id.lower()
        return next((q for q, pl in c.match.players.items() if f"{pl.name}#{pl.tag}".lower() == rid), "")

    def allowed(pid: int, mid: str):
        p, can_edit = view_profile(pid)                  # 404 for someone who may not open this player
        c = ctx(mid, p.region)
        if c is None:
            abort(404)
        return p, can_edit, c

    @app.get("/profiles/<int:pid>/replay/<match_id>")
    def replay_view(pid: int, match_id: str):
        p, can_edit, c = allowed(pid, match_id)
        me = me_in(c, p)
        rounds = c.rounds(me)
        start = request.args.get("round", type=int)
        if start is None or not any(r["i"] == start and r["has"] for r in rounds):
            start = next((r["i"] for r in rounds if r["has"]), 0)
        boot = {"mid": c.match.match_id.lower(), "pid": pid, "map": c.match.map_name, "api": "/api/maps3d/",
                "round_api": f"/api/replay/{c.match.match_id.lower()}/round/", "comments_api":
                f"/api/replay/{c.match.match_id.lower()}/comments?pid={pid}", "rounds": rounds,
                "players": c.players(me), "start": start, "replay": True, "user": g.user.username,
                "sens": 0.4, "util_col": UTIL_COL,
                "agents": app.extensions["nexus"].get("agents_boot", dict)(), "game_map": c.game is not None}
        util = c.utility_check()
        deaths = c.death_summary(me) if me else None
        ours = {x["i"] for x in boot["players"] if x["ours"]}
        util["players"].sort(key=lambda u: (u["i"] not in ours, u["i"]))      # your team first
        return render_template("replay_view.html", p=p, active_pid=pid, can_edit=can_edit, m=c.match, boot=boot,
                               rounds=rounds, players=boot["players"], util=util,
                               quality=c.quality, has_map=c.mi is not None, deaths=deaths,
                               coach_url=url_for("coach", pid=pid, match_id=c.match.match_id) if can_edit else "")

    @app.get("/api/replay/<match_id>/round/<int:idx>")
    def replay_round(match_id: str, idx: int):
        pid = request.args.get("pid", type=int)
        if not pid:
            abort(400)
        _p, _e, c = allowed(pid, match_id)
        d = c.round_view(idx)
        if d is None:
            return jsonify(error="This round isn't in the replay."), 404
        return jsonify(d)

    @app.get("/api/replay/<match_id>/comments")
    def replay_comments(match_id: str):
        pid = request.args.get("pid", type=int) or abort(400)
        allowed(pid, match_id)
        return jsonify(comments=_public(read_comments(store, match_id.lower())))

    @app.post("/api/replay/<match_id>/comments")
    def replay_comment_add(match_id: str):
        pid = request.args.get("pid", type=int) or abort(400)
        _p, _e, c = allowed(pid, match_id)
        b = request.get_json(silent=True) or {}
        text = " ".join(str(b.get("text") or "").split())[:MAX_COMMENT]
        try:
            rnd, t = int(b.get("round")), round(float(b.get("t") or 0), 1)
        except (TypeError, ValueError):
            return jsonify(error="Round and time are missing."), 400
        if not text:
            return jsonify(error="The comment is empty."), 400
        if not 0 <= rnd < len(c.match.rounds):
            return jsonify(error="That round isn't in the match."), 400
        item = {"id": uuid.uuid4().hex[:12], "round": rnd, "t": max(0.0, t), "text": text,
                "uid": g.user.id, "user": g.user.username, "at": int(time.time())}
        with _lock:
            items = read_comments(store, match_id.lower())
            items.append(item)
            _write_comments(store, match_id.lower(), items)
        return jsonify(ok=True, comment=_public([item])[0])

    @app.delete("/api/replay/<match_id>/comments/<cid>")
    def replay_comment_delete(match_id: str, cid: str):
        pid = request.args.get("pid", type=int) or abort(400)
        allowed(pid, match_id)
        with _lock:
            items = read_comments(store, match_id.lower())
            it = next((x for x in items if x.get("id") == cid), None)
            if it is None:
                return jsonify(error="That comment doesn't exist."), 404
            if it.get("uid") != g.user.id and not getattr(g.user, "is_admin", False):
                return jsonify(error="Only the person who wrote it can delete it."), 403
            _write_comments(store, match_id.lower(), [x for x in items if x.get("id") != cid])
        return jsonify(ok=True)

    app.extensions["nexus"]["replay_ctx"] = ctx              # for tests


def _public(items: list[dict]) -> list[dict]:
    return [{k: v for k, v in it.items() if k != "uid"} | {"mine": it.get("uid") == g.user.id}
            for it in sorted(items, key=lambda x: (x.get("round", 0), x.get("t", 0), x.get("at", 0)))]


UTIL_COL = {"smoke": "#aab3c2", "wall": "#7dd3fc", "slow": "#7fc4ff", "damage": "#ff8a3d", "trap": "#f2b84b",
            "recon": "#c58cff", "orb": "#c58cff", "flash": "#ffffff"}
