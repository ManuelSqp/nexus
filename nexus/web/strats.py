"""Strat book: boards on the minimap with agents, every ability, smokes, walls, arrows and text,
in steps (setup -> execute -> ...), saved per team and map. Everyone in the team can view and
edit boards; deleting is for the author and the team owner."""
from __future__ import annotations

import json
import re
import time

from flask import abort, flash, g, jsonify, redirect, render_template, request, send_file, url_for

from ..maps import AgentRegistry, MapRegistry
from ..stats import roles
from .abilityshapes import color_for, shape_for

SIDES = ("attack", "defense")
MAX_BOARD_BYTES = 400_000          # JSON of one board (items are tiny; this is plenty)
ITEM_NUMBERS = ("x", "y", "x2", "y2", "r", "len", "ang", "n", "size")
ITEM_STRINGS = {"t": 20, "id": 20, "a": 40, "s": 80, "label": 40, "c": 10, "k": 20}   # k: same thing in the step before (playback)


def _number(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) < 1e6 else None          # no NaN / inf


def clean_board(data: dict) -> dict:
    """Board JSON as saved by any team member: keep only well-typed item fields, so another
    member's browser never gets text where the editor expects a number (it builds HTML from them)."""
    steps = []
    for st in data.get("steps") or []:
        if not isinstance(st, dict):
            continue
        items = []
        for it in st.get("items") or []:
            if not isinstance(it, dict):
                continue
            out = {}
            for k in ITEM_NUMBERS:
                if k in it and (x := _number(it[k])) is not None:
                    out[k] = x
            for k, n in ITEM_STRINGS.items():
                if isinstance(it.get(k), str):
                    out[k] = it[k][:n]
            if "dash" in it:
                out["dash"] = bool(it["dash"])
            if isinstance(it.get("pts"), list):
                pts = [[_number(p[0]), _number(p[1])] for p in it["pts"][:2000] if isinstance(p, list) and len(p) >= 2]
                out["pts"] = [p for p in pts if None not in p]
            if "t" in out:
                items.append(out)
        steps.append({"name": str(st.get("name") or "")[:40], "call": str(st.get("call") or "")[:200], "items": items})
    out = dict(data)
    out["steps"] = steps
    if "notes" in out:
        out["notes"] = str(out["notes"] or "")[:5000]
    if "style" in out:                                 # 4.68: the comp style it fits, set by hand
        from ..stats.compstyle import STYLES
        if out["style"] not in STYLES:
            out.pop("style")
    return out
MAX_PNG_BYTES = 8_000_000
FROM_REPLAY_TYPES = ("agent", "ab", "smoke", "molly", "zone", "pen", "text", "arrow")
SLOT_ORDER = {"grenade": 0, "ability1": 1, "ability2": 2, "ultimate": 3}


def register(app, store, sr, get_team, known_maps: list[str]) -> None:
    cache_dir = store.data_dir / "cache"
    agents_reg = AgentRegistry(cache_dir)
    maps_reg = MapRegistry(cache_dir)
    misses: dict[str, float] = {}

    def missing(key: str) -> bool:
        return time.time() - misses.get(key, 0) < 600

    # ------------------------------------------------------------------ assets
    @app.get("/map-image/<path:name>")
    def map_image(name: str):
        if missing("map:" + name):
            abort(404)
        try:
            mi = maps_reg.get(name=name)
            f = maps_reg.minimap_image(mi) if mi else None
        except Exception:
            f = None
        if not f or not f.exists():
            misses["map:" + name] = time.time()
            abort(404)
        return send_file(f, mimetype="image/png", max_age=86400)

    @app.get("/ability-icon/<path:agent>/<slot>")
    def ability_icon(agent: str, slot: str):
        key = f"ab:{agent}:{slot}"
        if missing(key):
            abort(404)
        try:
            a = agents_reg.find(name=agent)
            f = agents_reg.ability_icon_file(a, slot) if a else None
        except Exception:
            f = None
        if not f or not f.exists():
            misses[key] = time.time()
            abort(404)
        return send_file(f, mimetype="image/png", max_age=86400)

    def assets(map_name: str) -> dict:
        roles.load(cache_dir)
        try:
            agents = agents_reg.load()
        except Exception:
            agents = []
        names = {a["name"] for a in agents}
        out_agents = []
        for a in agents:
            if not a.get("name"):
                continue
            role = a.get("role") or roles.role_of(a["name"])
            abl = [{"slot": ab["slot"], "name": ab["name"], "shape": shape_for(ab["name"])} for ab in a.get("abilities", [])]
            out_agents.append({"name": a["name"], "role": role, "color": color_for(a["name"], role),
                               "abilities": sorted(abl, key=lambda x: SLOT_ORDER.get(x["slot"].lower(), 9))})
        for n in roles.all_agents():            # offline / not in the cached list: still placeable as a portrait
            if n not in names:
                out_agents.append({"name": n, "role": roles.role_of(n), "color": color_for(n, roles.role_of(n)), "abilities": []})
        out_agents.sort(key=lambda a: (roles.ROLES.index(a["role"]) if a["role"] in roles.ROLES else 9, a["name"]))
        mp = {"name": map_name, "callouts": [], "m": 7.0}      # m = board units (of 1000) per meter
        try:
            mi = maps_reg.get(name=map_name)
        except Exception:
            mi = None
        if mi:
            seen = set()
            for c in mi.callouts:
                if c.region.lower() == "spawn" or c.label in seen:
                    continue
                seen.add(c.label)
                u, v = mi.to_uv(c.x, c.y)
                mp["callouts"].append({"label": c.label, "u": round(u, 4), "v": round(v, 4)})
            mp["m"] = round(abs(mi.x_mult) * 100 * 1000, 3) or 7.0
        return {"agents": out_agents, "map": mp}

    def strat_lineups(t, s: dict, ideas: list[dict] | None = None, library: list[dict] | None = None) -> list[dict]:
        """4.83: the lineups the strat needs, step by step (stats/stratlineups), matched with the library and, for the
        ones it has nothing for, the lineups your team throws in its replays (ideas: pass them to save the work when
        doing several strats of a map)."""
        from ..stats import stratlineups as sl
        try:
            names = {a["name"]: {ab["slot"].lower(): ab["name"] for ab in a.get("abilities", [])} for a in agents_reg.load() if a.get("name")}
        except Exception:
            names = {}
        try:
            mi = maps_reg.get(name=s["map"])
        except Exception:
            mi = None
        pts = []
        if mi:
            for c in mi.callouts:
                u, v = mi.to_uv(c.x, c.y)
                pts.append((c.label, c.super_region, u * 1000, v * 1000))

        def place(x: float, y: float) -> tuple[str, str]:
            if not pts:
                return "", ""
            c = min(pts, key=lambda p: (p[2] - x) ** 2 + (p[3] - y) ** 2)
            return c[0], c[1]

        steps = sl.uses(s.get("data") or {}, lambda a, slot: names.get(a, {}).get(slot.lower(), ""), place)
        if not steps:
            return []
        if ideas is None:
            fn = app.extensions["nexus"].get("lineup_ideas")
            try:
                ideas = fn(t, s["map"]) if fn else []
            except Exception:
                ideas = []
        lib = library if library is not None else store.lineups(t.id, s["map"])
        return sl.match(steps, lib, s.get("side") or "", ideas)
    app.extensions["nexus"]["strat_lineups"] = strat_lineups

    # ------------------------------------------------------------------ helpers
    def get_strat(tid: int, sid: int):
        t = get_team(tid)
        s = store.strat(sid)
        if s is None or s["team_id"] != tid:
            abort(404)
        return t, s

    def team_rates(tid: int, strats: list[dict] | None = None) -> dict[int, dict]:
        """4.75: how each strat did in the rounds tagged with it in review evenings (stats/stratrates.py)."""
        from ..stats import evening as ev_stats
        from ..stats import stratrates
        evs = app.extensions["nexus"].get("evenings")
        if evs is None:
            return {}
        strats = strats if strats is not None else store.strats(tid)
        utils = {s["id"]: ev_stats.strat_util((store.strat(s["id"]) or {}).get("data") or {}) for s in strats}
        return stratrates.rates(evs(tid), utils)
    app.extensions["nexus"]["strat_rates"] = team_rates

    def maps_for(t) -> list[str]:
        return sorted(set(t.map_list) | set(known_maps))

    # ------------------------------------------------------------------ pages
    @app.route("/teams/<int:tid>/strats", methods=["GET", "POST"])
    def team_strats(tid: int):
        t = get_team(tid)
        if request.method == "POST":
            f = request.form
            m = f.get("map", "")
            side = f.get("side", "attack")
            if m not in maps_for(t) or side not in SIDES:
                abort(400)
            name = (f.get("name") or "").strip() or f"{m} {side}"
            data = {"steps": [{"name": "Setup", "items": []}], "notes": ""}
            plan_ref = f.get("from_plan", "")
            if plan_ref:                              # "Draw it" from a game plan: its steps become the notes
                plans = sr.read_plans(tid, m) or {}
                try:
                    p = plans.get("plans", [])[int(plan_ref)]
                except (ValueError, IndexError):
                    p = None
                if p:
                    name = p.get("title") or name
                    side = p.get("side") if p.get("side") in SIDES else side
                    lines = [p.get("idea", "")] + [f"{s['player']}: {s['what']}" for s in p.get("steps", []) if s.get("what")]
                    if p.get("timing"):
                        lines.append(f"Timing: {p['timing']}")
                    lines += [f"If: {x}" for x in p.get("if_then", [])]
                    data["notes"] = "\n".join(x for x in lines if x)
                    data["steps"] = [{"name": "Setup", "items": []}, {"name": "Execute", "items": []}]
            from ..stats.compstyle import STYLES
            if f.get("style") in STYLES and f.get("style") != "balanced":    # 4.68
                data["style"] = f["style"]
            sid = store.create_strat(tid, g.user.id, m, side, name, data)
            return redirect(url_for("strat_edit", tid=tid, sid=sid))
        from ..stats import compstyle, stratstyle
        strats = store.strats(tid)
        by_map: dict[str, list] = {}
        for s in strats:
            data = (store.strat(s["id"]) or {}).get("data")
            data = data if isinstance(data, dict) else {}
            s["style"], s["style_set"] = stratstyle.style_of({**s, "data": data})
            by_map.setdefault(s["map"], []).append(s)
        counters = counter_box(t, strats)
        from ..stats import stratrates
        rates = team_rates(tid, strats)                      # 4.75
        for s in strats:
            r = rates.get(s["id"])
            s["rate"], s["rate_util"] = stratrates.text(r), stratrates.util_text(r)
            s["pct"], s["few"] = (r["pct"], r["few"]) if r else (None, True)
        best = {m: stratrates.best(ss, rates) for m, ss in by_map.items()}
        return render_template("team_strats.html", t=t, tab="strats", by_map=by_map, maps=maps_for(t),
                               sel=request.args.get("map", ""), premier_status=sr.status(f"premier:{tid}"),
                               styles=compstyle.STYLES, **counters, best=best)

    def counter_box(t, strats: list[dict]) -> dict:
        """4.68: against the team picked on the comps page (Against): per map the counter style, the strats of
        yours that fit it, and what's missing."""
        from ..stats import counter as ctr, stratstyle
        from flask import session
        pj = app.extensions["nexus"].get("premier")
        if pj is None:
            return {"vs_team": None, "counter_maps": []}
        teams = {k: x for k, x in (pj.scout_index(t.id).get("teams") or {}).items() if x.get("matches")}
        vs = request.args.get("vs", (session.get("compvs") or {}).get(str(t.id)))
        if not vs or vs not in teams:
            return {"vs_team": None, "counter_maps": [], "scouted_teams": sorted(teams.items(), key=lambda kv: (kv[1].get("name") or "").lower())}
        s = pj.scouted(t.id, vs)
        out = []
        for m in maps_for(t):
            c = ctr.counter(s, m)
            if c and c["style"] != "balanced":
                out.append({"map": m, "counter": c, **stratstyle.for_counter(c["style"], m, strats)})
        return {"vs_team": {"id": vs, **teams[vs]}, "counter_maps": out,
                "scouted_teams": sorted(teams.items(), key=lambda kv: (kv[1].get("name") or "").lower())}

    @app.post("/teams/<int:tid>/strats/<int:sid>/style")
    def strat_style(tid: int, sid: int):
        """4.68: the comp style a strat fits (or back to the guess)."""
        from ..stats.compstyle import STYLES
        _t, s = get_strat(tid, sid)
        data = dict(s["data"]) if isinstance(s.get("data"), dict) else {}
        st = request.form.get("style", "")
        if st in STYLES and st != "balanced":
            data["style"] = st
        else:
            data.pop("style", None)
        store.update_strat(sid, g.user.id, data=data)
        return redirect(url_for("team_strats", tid=tid) + f"#map-{s['map']}")

    @app.get("/teams/<int:tid>/strats/<int:sid>")
    def strat_edit(tid: int, sid: int):
        t, s = get_strat(tid, sid)
        lineup = []
        for m in t.member_list:
            p = store.profile(m["pid"])
            if p and m.get("kind") == "starter":
                lineup.append(p.name)
        boot = {"strat": {k: s[k] for k in ("id", "name", "map", "side", "data", "updated_at")},
                "assets": assets(s["map"]), "lineup": lineup,
                "save_url": url_for("strat_save", tid=tid, sid=sid),
                "discord_url": url_for("strat_discord", tid=tid, sid=sid)
                if (t.discord_info.get("prep_url") or t.discord_info.get("focus_url")) else None,
                "map_image": url_for("map_image", name=s["map"]),
                "lineups": [{"agent": x["agent"], "ability": x["ability"], "title": x["title"], "url": x["url"], "side": x["side"]}
                            for x in store.lineups(tid, s["map"])],
                "lineups_url": url_for("team_lineups", tid=tid, map=s["map"]),
                "agent_icon": url_for("agent_icon", name="__A__"), "ability_icon": url_for("ability_icon", agent="__A__", slot="__S__")}
        can_delete = g.team_owner or s["author_id"] == g.user.id
        from ..stats import stratrates
        rate = team_rates(tid).get(sid)                      # 4.75: how it did in your reviewed rounds
        try:                                                 # 4.83: the lineups it needs, from the library (not in the
            needs = [] if request.args.get("embed") == "1" else strat_lineups(t, s)     # match screen's player)
        except Exception:
            app.logger.exception("lineups for a strat")
            needs = []
        from .lineups import clip_info
        for st in needs:
            for u in st["uses"]:
                if u["lineup"] and u["lineup"].get("url"):
                    u["lineup"]["clip"] = clip_info(u["lineup"]["url"])
        return render_template("strat_edit.html", t=t, s=s, tab="strats", can_delete=can_delete, needs=needs,
                               boot=json.dumps(boot).replace("</", "<\\/"), premier_status=None,
                               rate=rate, rate_text=stratrates.text(rate), rate_util=stratrates.util_text(rate))

    @app.post("/api/teams/<int:tid>/strats/<int:sid>")
    def strat_save(tid: int, sid: int):
        _t, old = get_strat(tid, sid)
        body = request.get_json(silent=True)                 # JSON only: a cross-site form can't send this
        if not isinstance(body, dict):
            return jsonify(error="expected JSON"), 400
        fields = {}
        if "name" in body:
            fields["name"] = str(body["name"]).strip()[:80] or "Untitled"
        if body.get("side") in SIDES:
            fields["side"] = body["side"]
        if "data" in body:
            data = body["data"]
            if not isinstance(data, dict) or not isinstance(data.get("steps"), list) or not data["steps"]:
                return jsonify(error="data.steps must be a non-empty list"), 400
            data = clean_board(data)
            if not data["steps"]:
                return jsonify(error="data.steps must be a non-empty list"), 400
            if "style" not in data:                       # 4.68: the editor doesn't send it: keep the style set
                st = old["data"].get("style") if isinstance(old.get("data"), dict) else None
                if st:
                    data["style"] = st
            raw = json.dumps(data)
            if len(raw) > MAX_BOARD_BYTES:
                return jsonify(error="board too big"), 413
            fields["data"] = raw
        if "data" in fields:
            store.keep_strat_version(sid, g.user.id)        # the board before this save, for History
        store.update_strat(sid, g.user.id, **fields)
        return jsonify(ok=True, saved_at=time.strftime("%H:%M:%S"))

    # ---- 4.79: a plan against a scouted team, drafted from their scouting
    def zone_centres(map_name: str) -> dict:
        from ..stats.stratprep import zone_centres as zc
        try:
            mi = maps_reg.get(name=map_name)
        except Exception:
            mi = None
        if not mi:
            return {}
        pts = [(c.super_region, *mi.to_uv(c.x, c.y)) for c in mi.callouts if c.region.lower() != "spawn"]
        return zc(pts)

    def prep_strats(tid: int, map_name: str | None = None) -> list[dict]:
        """The drafts made against scouted teams (newest first): {id, name, side, map, team, made}."""
        out = []
        for row in store.strats(tid):
            if map_name and row["map"] != map_name:
                continue
            full = store.strat(row["id"]) or {}
            pr = (full.get("data") or {}).get("prep")
            if isinstance(pr, dict):
                out.append({"id": row["id"], "name": row["name"], "side": row["side"], "map": row["map"],
                            "team": pr.get("team", ""), "made": pr.get("made", "")})
        return sorted(out, key=lambda x: x["made"], reverse=True)
    app.extensions["nexus"]["prep_strats"] = prep_strats

    @app.post("/teams/<int:tid>/strats/prep")
    def strat_prep(tid: int):
        """4.79: draft boards against a scouted team (one map, or all their maps), from its scouting."""
        from ..stats import scouting as sc
        from ..stats import stratprep
        t = get_team(tid)
        pj = app.extensions["nexus"].get("premier")
        team_id = str(request.form.get("team_id") or "")
        s = pj.scouted(tid, team_id) if pj and team_id else None
        if not s:
            abort(404)
        want = request.form.get("map") or ""
        maps = [m for m in (s.get("play") or {}) if m in maps_for(t) and (not want or m == want)]
        have = {(x["map"], x["name"]) for x in store.strats(tid)}
        made, kept = [], 0
        for m in maps:
            for p in stratprep.plans(s, m, zone_centres(m), sc.map_lines(s, m)):
                if (m, p["name"]) in have:
                    kept += 1
                    continue
                data = clean_board({"steps": [{"name": "Their " + ("setup" if p["side"] == "attack" else "hit"),
                                               "call": p["call"], "items": p["items"]}], "notes": p["notes"],
                                    "prep": {"team_id": team_id, "team": s.get("name") or team_id, "tag": s.get("tag") or "",
                                             "made": time.strftime("%Y-%m-%d")}})
                made.append(store.create_strat(tid, g.user.id, m, p["side"], p["name"], data))
        if made:
            flash(f"Drafted {len(made)} board{'s' if len(made) != 1 else ''} against {s.get('name') or team_id}"
                  + (f" ({kept} already there)" if kept else "") + ". Edit them like any strat.", "ok")
        elif kept:
            flash(f"The boards against {s.get('name') or team_id} are already in your strat book.", "ok")
        else:
            flash("Not enough of their rounds scouted to draft a plan. Scout them again or later.", "error")
        if len(made) == 1:
            return redirect(url_for("strat_edit", tid=tid, sid=made[0]))
        return redirect(url_for("team_strats", tid=tid, map=want or None))

    @app.post("/api/teams/<int:tid>/strats/from-replay")
    def strat_from_replay(tid: int):
        """4.18: a moment of the round playback (positions, utility, drawings) as a new strat board."""
        t = get_team(tid)
        body = request.get_json(silent=True)                 # JSON only: a cross-site form can't send this
        if not isinstance(body, dict):
            return jsonify(error="expected JSON"), 400
        m = str(body.get("map") or "")
        side = body.get("side") if body.get("side") in SIDES else "attack"
        if m not in maps_for(t):
            return jsonify(error="unknown map"), 400
        items = []
        for i, it in enumerate(body.get("items") or []):
            if isinstance(it, dict) and it.get("t") in FROM_REPLAY_TYPES and len(items) < 120:
                items.append({**it, "id": f"r{i}"})
        name = str(body.get("name") or "").strip()[:80] or f"{m} {side}"
        data = clean_board({"steps": [{"name": "Setup", "call": str(body.get("call") or "")[:200], "items": items}],
                            "notes": str(body.get("notes") or "")[:5000]})
        if len(json.dumps(data)) > MAX_BOARD_BYTES:
            return jsonify(error="board too big"), 413
        sid = store.create_strat(tid, g.user.id, m, side, name, data)
        return jsonify(ok=True, url=url_for("strat_edit", tid=tid, sid=sid))

    @app.get("/api/teams/<int:tid>/strats/<int:sid>/versions")
    def strat_versions(tid: int, sid: int):
        get_strat(tid, sid)
        return jsonify(versions=store.strat_versions(sid))

    @app.post("/api/teams/<int:tid>/strats/<int:sid>/versions/<int:vid>/restore")
    def strat_restore(tid: int, sid: int, vid: int):
        get_strat(tid, sid)
        v = store.strat_version(vid)
        if v is None or v["strat_id"] != sid:
            abort(404)
        store.keep_strat_version(sid, g.user.id, force=True)     # what's there now stays in History
        store.update_strat(sid, g.user.id, data=v["data"])
        return jsonify(ok=True)

    @app.post("/teams/<int:tid>/strats/<int:sid>/delete")
    def strat_delete(tid: int, sid: int):
        t, s = get_strat(tid, sid)
        if not (g.team_owner or s["author_id"] == g.user.id):
            abort(403)
        store.delete_strat(sid)
        flash(f"Deleted {s['name']}.", "ok")
        return redirect(url_for("team_strats", tid=tid, map=s["map"]))

    @app.post("/teams/<int:tid>/strats/<int:sid>/copy")
    def strat_copy(tid: int, sid: int):
        t, s = get_strat(tid, sid)
        nid = store.create_strat(tid, g.user.id, s["map"], s["side"], f"{s['name']} (copy)", s["data"])
        return redirect(url_for("strat_edit", tid=tid, sid=nid))

    @app.post("/api/teams/<int:tid>/strats/<int:sid>/discord")
    def strat_discord(tid: int, sid: int):
        from ..discord import post_file
        t, s = get_strat(tid, sid)
        url = t.discord_info.get("prep_url") or t.discord_info.get("focus_url")
        f = request.files.get("png")
        if not url:
            return jsonify(error="no Discord webhook set for this team"), 400
        if f is None:
            return jsonify(error="no image"), 400
        data = f.read(MAX_PNG_BYTES + 1)
        if len(data) > MAX_PNG_BYTES or not data.startswith(b"\x89PNG"):
            return jsonify(error="not a PNG or too big"), 400
        step = re.sub(r"[^\w .-]", "", request.form.get("step", ""))[:40]
        notes = (s["data"].get("notes") or "").strip()
        text = f"**{s['name']}** · {s['map']} {s['side']}{' · ' + step if step else ''}"
        if notes:
            text += "\n" + notes[:1200]
        try:                                                  # 4.83: the lineups of the step (or the strat), with their clips
            from ..stats import stratlineups as sl
            needs = strat_lineups(t, s, ideas=[])
            lu = sl.lines(needs, step if any(x["step"] == step for x in needs) else "")
        except Exception:
            lu = []
        if lu:
            add = "\n**Lineups**\n" + "\n".join(f"- {x}" for x in lu)
            text += add if len(text) + len(add) <= 1990 else add[: max(0, 1990 - len(text))].rsplit("\n", 1)[0]
        try:
            post_file(url, text, f"{re.sub(r'[^A-Za-z0-9]+', '-', s['name'])[:40] or 'strat'}.png", data)
        except Exception:
            app.logger.exception("posting a strat to Discord")
            return jsonify(error="Discord didn't take the picture (details in the server log)."), 502
        return jsonify(ok=True)
