"""4.51: Practice › Aim on maps (per player): your deaths as aim drills on the real maps (stats/drills.py).

/profiles/<pid>/aim/maps lists them (one card per spot); /profiles/<pid>/aim/drill/<id> plays one (static/drill.js
in the 3D map of map3d.js, with the animated agents and guns of 4.50); the runs go to data/profiles/<pid>/stats/
drills.json. The drills of a match are worked out once in the background (it needs the replay lined up, line of
sight and callouts: a few seconds per match) and kept in data/drills/<match id>.json.

Your keys (Settings in a drill, or the Keys button on the list): per user in data/aim/keys-<uid>.json.

4.52: general drills on the map's real spots: /profiles/<pid>/aim/play/<mode>/<map>/<spot> (hold an angle, attacking,
tracking, clear a site); the spots come from the fights in all replays of the map (stats/drills.py spots()).
4.54: entry (first onto a site), retake (the spike is down, you come in), post-plant (you hold, they retake)."""
from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for

from .. import replayfile
from ..stats import drills as dr
from ..stats import kits
from ..stats import map3d as m3
from .aim import _lock, _read, _write
from .replays import match_brief, replays_dir

log = logging.getLogger(__name__)
MATCHES = {"10": 10, "30": 30, "all": 400}     # "From" on the page: the last this-many matches with a replay
SPOT_MATCHES = 60                               # 4.52: the spots of a map come from its last this-many replays
MODES = ("hold", "attack", "track", "clear", "entry", "retake", "postplant")    # 4.54: entry, retake, post-plant
GENERAL_ID = re.compile(r"^g-(" + "|".join(MODES) + r")-[0-9a-f]{10}$")
QUEUE_G = re.compile(r"^g-(" + "|".join(MODES) + r")-([0-9a-f]{10})@([A-Za-z' ]{2,24})$")   # 4.67: a general drill in a queue
PEEKS = ("wide", "jiggle", "crouch", "jump", "two")
DIFFS = {"easy": 0.9, "medium": 0.6, "hard": 0.42, "pro": 0.3}   # the enemies' reaction time (s)
DEFAULT_REPS = {"hold": 20, "attack": 5, "track": 1, "clear": 3, "entry": 5, "retake": 5, "postplant": 10}
LISTS = {"hold": "angles", "attack": "angles", "track": "angles", "clear": "sites", "entry": "sites",
         "retake": "retakes", "postplant": "retakes"}      # which of a map's spots each kind of drill is played on
FOES = (1, 2, 3)                                # entry, retake, post-plant: how many enemies (2 by default)
UTIL_MODES = ("hold", "attack", "entry", "retake", "postplant")   # 4.56: the enemies use their utility


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
        dr.write_cached(data_dir, mid, signature(mid, c.match.map_name), players, dr.fights_of(c), c.match.map_name)

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
                "keys_api": url_for("aim_keys"), "pid": pid,
                # 4.52: the general drills
                "spots_api": url_for("aim_spots_api", pid=pid),
                "play": url_for("aim_play", pid=pid, mode="MODE", map_name="MAP", sid="SID"),
                "guns": list(dr.GUNS), "diffs": list(DIFFS), "peeks": list(PEEKS), "reps": DEFAULT_REPS,
                "foes": list(FOES), "util_modes": list(UTIL_MODES),
                "suggest_api": url_for("aim_suggest_api", pid=pid), "match": request.args.get("match", "")[:80],
                "agents": {k: {s: v["name"] for s, v in kits.kit(k).items()} for k in sorted(kits.KITS)}}
        week = dr.weekly(dr.read_runs(stats_dir(pid)))          # 4.65: your week
        for d in week["better"] + week["worse"]:
            gm = GENERAL_ID.match(d["id"])
            if gm and d["map"]:
                d["url"] = url_for("aim_play", pid=pid, mode=gm.group(1), map_name=d["map"], sid=d["id"].rsplit("-", 1)[1])
            elif not gm:
                d["url"] = url_for("aim_drill", pid=pid, drill_id=d["id"])
        return render_template("aim_maps.html", p=p, active_pid=pid, can_edit=can_edit, boot=boot, week=week,
                               match_teams=match_teams(p))

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
        nxt = queue_of(drill_id)
        ext = app.extensions["nexus"]
        boot = {"map": d["map"], "api": "/api/maps3d/", "drill": d, "pid": pid, "replay": False, "mode": "death",
                "round_api": f"/api/replay/{d['mid']}/round/{d['round']}?pid={pid}",
                "runs_api": url_for("aim_drill_runs", pid=pid, drill_id=drill_id), "can_save": can_edit,
                "sens": setup.get("sens") or 0.4, "dpi": setup.get("dpi") or 800, "scale": setup.get("scale") or 1,
                "keys": read_keys(data_dir, g.user.id), "actions": [[a, lbl] for a, (lbl, _d) in dr.ACTIONS.items()],
                "keys_api": url_for("aim_keys"), "defaults": dr.default_keys(), "gun": dr.gun(d["my_weapon"]), "his_gun": dr.gun(d["weapon"]),
                "guns": {n: dr.gun(n) for n in dr.GUNS}, "hp": dr.HP, "history": dr.summary(runs),
                "list": url_for("aim_maps", pid=pid), "queue": nxt, "next": item_url(pid, nxt), "step": step(nxt),
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
        g_id = GENERAL_ID.match(drill_id)
        if not g_id and find_drill(p, drill_id) is None:
            abort(404)
        run = dr.clean_run(request.get_json(silent=True) or {})
        if run is None:
            return jsonify(error="That's no run."), 400
        if g_id:
            run["kind"] = g_id.group(1)
        with _lock:
            data = dr.add_run(stats_dir(pid), drill_id, run)
        return jsonify(ok=True, history=dr.summary(data.get(drill_id, []), run["kind"]))

    # ---------------------------------------------------------------- 4.67: drills in a row (the warm-up)
    def queue_of(current: str) -> list[str]:
        """?queue=: the drills still to come (death drill ids, or general ones as g-<mode>-<spot>@<map>)."""
        out = []
        for x in (request.args.get("queue") or "").split(",")[:40]:
            x = x.strip()
            if x and x != current and (QUEUE_G.match(x) or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", x)) and x not in out:
                out.append(x)
        return out

    def step(rest: list[str]) -> str:
        """"2/5" in a warm-up (?wt= the number of drills in it)."""
        try:
            total = int(request.args.get("wt") or 0)
        except ValueError:
            return ""
        return f"{total - len(rest)}/{total}" if 0 < total <= 40 and len(rest) < total else ""

    def item_url(pid: int, items: list[str], total: int | None = None) -> str:
        """The page of the first drill in items, with the rest as its queue."""
        if not items:
            return ""
        total = total or request.args.get("wt", type=int)
        q = {"queue": ",".join(items[1:])} if items[1:] else {}
        if total:
            q["wt"] = total
        m = QUEUE_G.match(items[0])
        if m:
            mode, sid, name = m.groups()
            return url_for("aim_play", pid=pid, mode=mode, map_name=name, sid=sid, reps=dr.WARM_REPS[mode], **q)
        return url_for("aim_drill", pid=pid, drill_id=items[0], **q)

    @app.get("/profiles/<int:pid>/aim/warmup")
    def aim_warmup(pid: int):
        """4.67: the daily warm-up: what slipped this week, what your newest match points to, a tracking drill."""
        p, _e = view_profile(pid)
        if request.args.get("map"):                               # 4.68: a warm-up for a match on one map
            return match_warmup(p, request.args["map"], request.args.get("tid", type=int))
        runs = dr.read_runs(stats_dir(pid))
        week = dr.weekly(runs)
        mid, name, items, sp = newest_suggest(p)
        by = map_matches()
        if sp is None and by:                                    # no suggestions: your most played map
            name = max(by, key=lambda m: len(by[m]))
            sp, _pending = map_spots(p, name, by[name], False)
        track = None
        if sp and sp.get("angles"):                              # the angle you tracked least
            a = min(sp["angles"], key=lambda a: (len(runs.get(f"g-track-{a['id']}", [])), -a.get("count", 0)))
            track = (a["id"], name)
        fallback = []
        if sp:
            fallback = [dr.token("hold", a["id"], name) for a in sp.get("angles", [])[:3]]
            fallback += [dr.token("retake", r["id"], name) for r in sp.get("retakes", [])[:1]]
        q = dr.warmup(week, items, name or "", track, fallback)
        if not q:
            flash("Nothing to warm up with yet: Nexus needs your replays to make drills on the maps (Replays).", "error")
            return redirect(url_for("aim_maps", pid=pid))
        return redirect(item_url(pid, q, len(q)))

    def match_teams(p) -> list[dict]:
        """4.68: the player's teams with this Premier week's map (and the scouted team picked on their comps
        page): [{tid, team, map, vs}] for the match warm-up."""
        from flask import session
        from .stats_views import week_map_of
        by = map_matches()
        pj = app.extensions["nexus"].get("premier")
        out = []
        for t in store.all_teams():
            if not any(m.get("pid") == p.id for m in t.member_list):
                continue
            m = week_map_of(app, t)
            name = next((x for x in by if m and x.lower() == m.lower()), None)
            if not name:
                continue
            vs = (session.get("compvs") or {}).get(str(t.id))
            vt = ((pj.scout_index(t.id).get("teams") or {}).get(vs) if pj and vs else None) or None
            out.append({"tid": t.id, "team": t.name, "map": name, "vs": vt.get("name") if vt else None})
        return out

    def match_warmup(p, map_name: str, tid: int | None):
        from flask import session
        by = map_matches()
        name = next((x for x in by if x.lower() == map_name.lower()), None)
        if name is None:
            flash(f"No drills on {map_name} yet: Nexus needs your replays on it (Replays).", "error")
            return redirect(url_for("aim_maps", pid=p.id))
        sp, _pending = map_spots(p, name, by[name], False)
        their = weak = None
        pj = app.extensions["nexus"].get("premier")
        t = store.team(tid) if tid else None
        if pj and t and any(m.get("pid") == p.id for m in t.member_list):
            vs = (session.get("compvs") or {}).get(str(t.id))
            if vs:
                their, weak = dr.opponent_sites(pj.scouted(t.id, vs), name)
        q = dr.match_warmup(sp, name, their, weak)
        if not q:
            flash(f"No drills on {name} yet: Nexus needs more of your replays on it.", "error")
            return redirect(url_for("aim_maps", pid=p.id))
        return redirect(item_url(p.id, q, len(q)))

    def newest_suggest(p) -> tuple[str, str, list, dict | None]:
        """The newest match whose drills are worked out: (match, map, suggestions, spots of the map)."""
        by = map_matches()
        for mid in my_matches(p, 8):
            brief = match_brief(store, mid, p.riot_id) or {}
            name = brief.get("map") or ""
            fights = dr.read_fights(data_dir, mid, signature(mid, name)) if name else None
            if fights is None or name not in by:
                continue
            sp, _pending = map_spots(p, name, by[name], False)
            return mid, name, dr.suggest(p.riot_id, fights, sp), sp
        return "", "", [], None

    # ---------------------------------------------------------------- 4.52: general drills on the map's real spots
    def map_matches() -> dict[str, list[str]]:
        game = app.extensions["nexus"].get("game")
        if game is None:
            return {}
        try:
            by = m3.replays_by_map(replays_dir(store), game.map_of)
        except Exception:
            return {}
        return {m: ids for m, ids in by.items() if game.meta(m)}

    def map_spots(p, name: str, mids: list[str], build_missing: bool) -> tuple[dict, int]:
        fights, todo = [], []
        for mid in sorted(mids)[-SPOT_MATCHES:]:
            got = dr.read_fights(data_dir, mid, signature(mid, name))
            if got is None:
                todo.append(mid)
            else:
                fights += got
        if todo and build_missing:
            start_job(p, todo)
        return dict(dr.spots(name, fights), fights=len(fights)), len(todo)

    @app.get("/api/profiles/<int:pid>/aim/spots")
    def aim_spots_api(pid: int):
        p, _e = view_profile(pid)
        by = map_matches()
        maps = sorted(by, key=lambda m: (-len(by[m]), m))
        name = request.args.get("map") or (maps[0] if maps else "")
        if name not in by:
            return jsonify(maps=[{"name": m, "matches": len(by[m])} for m in maps], map="", angles=[], sites=[],
                           retakes=[], fights=0, pending=0, working=False)
        sp, pending = map_spots(p, name, by[name], True)
        runs = dr.read_runs(stats_dir(pid))
        for lst in ("angles", "sites", "retakes"):
            for a in sp[lst]:
                sm = {k: dr.summary(runs.get(f"g-{k}-{a['id']}", []), k) for k in MODES if LISTS[k] == lst}
                a["best"] = {k: v["best"] for k, v in sm.items()}
                a["trend"] = {k: v["medians"][-12:] for k, v in sm.items() if v["medians"]}     # 4.59
        j = jobs.get(p.id) or {}
        return jsonify(maps=[{"name": m, "matches": len(by[m])} for m in maps], map=name, pending=pending,
                       working=bool(j.get("running")), **sp)

    @app.get("/api/profiles/<int:pid>/aim/suggest")
    def aim_suggest_api(pid: int):
        """4.59: the drills a match points to (?match=, else the newest one whose drills are worked out)."""
        p, _e = view_profile(pid)
        want = (request.args.get("match") or "").lower()
        mids = [want] if want else my_matches(p, 8)
        for mid in mids:
            brief = match_brief(store, mid, p.riot_id) or {}
            name = brief.get("map") or ""
            fights = dr.read_fights(data_dir, mid, signature(mid, name)) if name else None
            if fights is None:
                if want and name:
                    start_job(p, [mid])
                    return jsonify(match=mid, map=name, pending=True, items=[])
                continue
            by = map_matches()
            if name not in by:
                continue
            sp, _pending = map_spots(p, name, by[name], False)
            items = dr.suggest(p.riot_id, fights, sp)
            return jsonify(match=mid, map=name, pending=False, started=brief.get("started_at") or "",
                           score=brief.get("score") or "", items=items)
        return jsonify(match="", map="", pending=False, items=[])

    @app.get("/profiles/<int:pid>/aim/play/<mode>/<map_name>/<sid>")
    def aim_play(pid: int, mode: str, map_name: str, sid: str):
        p, can_edit = view_profile(pid)
        if mode not in MODES or not sid.isalnum() or len(sid) > 20:
            abort(404)
        by = map_matches()
        name = next((m for m in by if m.lower() == map_name.lower()), None)
        if name is None:
            abort(404)
        sp, _pending = map_spots(p, name, by[name], False)
        spot = next((a for a in sp[LISTS[mode]] if a["id"] == sid), None)
        if spot is None:
            abort(404)
        a = request.args
        styles = [x for x in (a.get("styles") or "wide,jiggle,crouch").split(",") if x in PEEKS] or ["wide"]
        diff = a.get("diff") if a.get("diff") in DIFFS else "medium"
        gun_name = a.get("gun") if a.get("gun") in dr.GUNS else "Vandal"
        try:
            reps = max(1, min(40, int(a.get("reps") or DEFAULT_REPS[mode])))
        except ValueError:
            reps = DEFAULT_REPS[mode]
        try:
            foes = int(a.get("foes") or 2)
        except ValueError:
            foes = 2
        foes = foes if foes in FOES else 2
        util = mode in UTIL_MODES and a.get("util", "1") != "0"     # 4.56: their utility from your replays
        agent = a.get("agent") if mode in UTIL_MODES and a.get("agent") in kits.KITS else ""   # 4.58: your abilities
        did = f"g-{mode}-{sid}"
        setup = _read(stats_dir(pid) / "trainer.json", {}).get("setup", {})
        runs = dr.read_runs(stats_dir(pid)).get(did, [])
        ext = app.extensions["nexus"]
        def frm(a: str, b: str) -> str:
            return a if a == b else f"{a} from {b}"
        title = {"hold": f"Hold: {frm(spot['az'], spot['dz'])}", "attack": f"Take: {frm(spot['dz'], spot['az'])}",
                 "track": f"Tracking at {spot['az']}", "clear": f"Clear: {frm(spot['dz'], spot['az'])}",
                 "entry": f"Entry: {frm(spot['dz'], spot['az'])}", "retake": f"Retake {spot['dz']}",
                 "postplant": f"Post-plant {spot['dz']}"}[mode]
        boot = {"map": name, "api": "/api/maps3d/", "pid": pid, "mode": mode, "spot": spot, "title": title,
                "drill": {"id": did, "map": name, "mode": mode, "where": spot["dz"]},
                "opts": {"styles": styles, "diff": diff, "reps": reps, "react": DIFFS[diff], "foes": foes, "util": util,
                         "agent": agent, "kit": kits.kit(agent) if agent else None,
                         "spike": dr.SPIKE_S, "defuse": dr.DEFUSE_S},
                "runs_api": url_for("aim_drill_runs", pid=pid, drill_id=did), "can_save": can_edit,
                "sens": setup.get("sens") or 0.4, "dpi": setup.get("dpi") or 800, "scale": setup.get("scale") or 1,
                "keys": read_keys(data_dir, g.user.id), "actions": [[k, lbl] for k, (lbl, _d) in dr.ACTIONS.items()],
                "keys_api": url_for("aim_keys"), "defaults": dr.default_keys(), "gun": dr.gun(gun_name),
                "guns": {n: dr.gun(n) for n in dr.GUNS}, "hp": dr.HP, "history": dr.summary(runs, mode),
                "list": url_for("aim_maps", pid=pid) + f"#{mode}", "util_col": COLS,
                "queue": queue_of(dr.token(mode, sid, name)), "next": item_url(pid, queue_of(dr.token(mode, sid, name))),
                "step": step(queue_of(dr.token(mode, sid, name))),
                "agents": ext.get("agents_boot", dict)(),
                **ext.get("motion_boot", lambda: {"anims": None, "guns": {}})()}
        return render_template("drill_view.html", p=p, active_pid=pid, d={"map": name, "where": title}, boot=boot)

    @app.route("/api/aim/keys", methods=["GET", "POST"])
    def aim_keys():
        if request.method == "GET":
            return jsonify(keys=read_keys(data_dir, g.user.id), defaults=dr.default_keys())
        keys = dr.clean_keys(request.get_json(silent=True) or {})
        with _lock:
            _write(keys_file(data_dir, g.user.id), keys)
        return jsonify(ok=True, keys=keys, clashes=dr.clashes(keys))
