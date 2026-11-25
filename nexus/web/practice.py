"""Team › Practice › Practice plan: this week's practice sessions, made from the team's habits,
the week's map, its strats and lineups, and the newest review. Anyone in the team can tick items off
and add their own; the owner sets days and time, makes it again and posts it to Discord."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from flask import flash, g, jsonify, redirect, render_template, request, url_for

from ..stats import habits as hb
from ..stats import practice as pr
from ..stats.weekly import week_id


def register(app, store, sr, get_team) -> None:
    def cfg_of(t) -> dict:
        c = dict(pr.DEFAULT)
        c.update((t.sync_info.get("practice") or {}))
        return c

    def path(tid: int, week: str):
        return sr.team_dir(tid) / "practice" / f"{week}.json"

    def read(tid: int, week: str) -> dict | None:
        try:
            return json.loads(path(tid, week).read_text())
        except (OSError, ValueError):
            return None

    def write(tid: int, plan: dict) -> None:
        p = path(tid, plan["week"])
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(plan, ensure_ascii=False))
        tmp.replace(p)

    def context(t) -> dict:
        ext = app.extensions["nexus"]
        m = ext["week_map"](t) if "week_map" in ext and t.premier_info.get("tag") else None
        m = m or (list(t.map_list)[0] if t.map_list else None)
        strats = {"attack": [], "defense": []}
        for s in store.strats(t.id):
            if s["map"] == m and s["side"] in strats:
                strats[s["side"]].append(s["name"])
        lineups: dict[str, int] = {}
        for r in (store.lineups(t.id, m) if m else []):
            lineups[r["agent"]] = lineups.get(r["agent"], 0) + 1
        members, personal = {}, {}
        for mm in t.member_list:
            if mm.get("kind") != "starter":
                continue
            p = store.profile(mm["pid"])
            if not p:
                continue
            h = hb.track(sr.games(p.id).rows())
            members[p.name] = h
            personal[p.name] = [{"title": x["title"], "drill": x["drill"], "status": x["status_text"]} for x in h.get("problems", [])[:2]]
        review = None
        pj = ext.get("premier")
        if pj:
            rv = pj.reviews(t.id)
            if rv:
                r = rv[0]
                review = {"title": f"the {r.get('map', '')} review vs {r.get('opponent', '')}".replace("  ", " "),
                          "url": url_for("team_review_page", tid=t.id, match_id=r.get("match_id", ""))}
        f = sr.read_focus(t.id) or {}
        focus = any(v.get("focus") for v in (f.get("players") or {}).values())
        from .availability import DEFAULT_DAYS
        brief = t.sync_info.get("brief") or {}
        return {"map": m, "strats": strats, "lineups": lineups, "habits": pr.team_habits(members), "personal": personal,
                "review": review, "match_days": brief.get("days") or DEFAULT_DAYS, "focus": focus, "evening": evening_items(t),
                "warmup": (ext.get("aim") or {}).get("team_routine", lambda _t: None)(t), "drills": player_drills(t, m)}

    def player_drills(t, m: str | None) -> list[dict]:
        """4.70: each starter's drill for the week: his open goal, else the drill that slipped most, else the match
        warm-up on the week's map, else the daily warm-up."""
        from urllib.parse import quote
        from ..stats import drillgoals as dg, drills as dr
        out = []
        for mm in t.member_list:
            if mm.get("kind") != "starter":
                continue
            p = store.profile(mm["pid"])
            if not p:
                continue
            sd_ = sr.games(p.id).path.parent
            runs_ = dr.read_runs(sd_)
            open_ = [x for x in dg.status(dg.read(sd_), runs_) if not x["reached"]]
            week = dr.weekly(runs_)
            base = f"/profiles/{p.id}/aim"
            if open_:
                x = open_[0]
                out.append({"pid": p.id, "name": p.name, "drill": x["drill"], "label": x["label"],
                            "why": f"his goal: {dg.text(x)}", "link": base + "/maps#am-goals"})
            elif week["worse"]:
                d = week["worse"][0]
                out.append({"pid": p.id, "name": p.name, "drill": d["id"], "label": dr.drill_name(d),
                            "why": f"slipped: {dr.change_text(d)}", "link": base + "/maps#am-week"})
            elif m:
                out.append({"pid": p.id, "name": p.name, "drill": f"*map:{m}", "label": f"Match warm-up on {m}",
                            "why": "the week's map", "link": f"{base}/warmup?map={quote(m)}&tid={t.id}"})
            else:
                out.append({"pid": p.id, "name": p.name, "drill": "*", "label": "Daily warm-up",
                            "why": "10 minutes of his drills", "link": f"{base}/warmup"})
        return out

    def sync_drills(t, plan: dict) -> bool:
        """4.70: the drill items tick themselves: sessions played since the plan's week began. -> changed"""
        from ..stats import drills as dr
        changed = "drills" not in plan
        if changed:                                  # a plan from before 4.70: add them now
            plan["drills"] = pr.drill_items(player_drills(t, plan.get("map")))
        since = datetime.fromisoformat(plan["start"]).timestamp()
        for it in plan["drills"]:
            n = pr.drill_count(dr.read_runs(sr.games(it["pid"]).path.parent), it["drill"], since)
            done = n >= it["sessions"]
            if n != it.get("count") or done != it.get("done"):
                it["count"], it["done"] = n, done
                changed = True
        return changed

    def evening_items(t) -> list[dict]:
        """Items from the newest review evening sent to the plan in the last 8 days (kept when the plan is made again)."""
        fn = ext_evenings()
        if fn is None:
            return []
        now = datetime.now().timestamp()
        for ev in fn(t.id):
            if ev.get("plan_items") and now - float(ev.get("planned_at") or 0) < 8 * 86400:
                return [dict(x, evening=ev["id"], url=url_for("team_evening_session", tid=t.id, sid=ev["id"]) + "#summary")
                        for x in ev["plan_items"]]
        return []

    def ext_evenings():
        return app.extensions["nexus"].get("evenings")

    def add_evening(t, ev: dict) -> int:
        """Put a review evening's items on the next practice day of this week (today counts); returns how many."""
        week = week_id()
        plan = read(t.id, week) or make(t, week)
        today = date.today().isoformat()
        day = next((d for d in plan["days"] if d["date"] >= today), None)
        if day is None:
            return 0
        have = {(it.get("evening"), it["title"]) for d in plan["days"] for it in d["items"]}
        n = 0
        for x in ev.get("plan_items") or []:
            if (ev["id"], x["title"]) in have:
                continue
            day["items"].insert(1 if day["items"] else 0, {
                "id": pr._id(), "kind": "evening", "title": x["title"][:100], "detail": x.get("detail", "")[:400],
                "minutes": int(x.get("minutes") or 15), "who": x.get("who") or "team", "evening": ev["id"],
                "link": url_for("team_evening_session", tid=t.id, sid=ev["id"]) + "#summary", "done": False})
            n += 1
        write(t.id, plan)
        # a plan made just now already has them (the evening's items go into every new plan for 8 days)
        return sum(1 for d in plan["days"] for it in d["items"] if it.get("evening") == ev["id"])

    app.extensions["nexus"]["practice_add"] = add_evening

    def make(t, week: str) -> dict:
        plan = pr.build(week, pr.monday(), cfg_of(t), context(t))
        write(t.id, plan)
        return plan

    def links(t, plan: dict) -> dict:
        m = plan.get("map")
        me = (app.extensions["nexus"].get("aim") or {}).get("card", lambda *_: None)(t, g.user.id)
        return {"brief": url_for("team_match", tid=t.id) if m else "", "habits": "",
                "aim": url_for("aim", pid=me["pid"]) + "#warmup" if me else "",
                "strats": url_for("team_strats", tid=t.id) + (f"#map-{m}" if m else ""),
                "lineups": url_for("team_lineups", tid=t.id, map=m) if m else url_for("team_lineups", tid=t.id)}

    @app.get("/teams/<int:tid>/practice")
    def team_practice(tid: int):
        t = get_team(tid)
        week = week_id()
        plan = read(tid, week) or make(t, week)
        if sync_drills(t, plan):                                     # 4.70: the drills tick themselves
            write(t.id, plan)
        done, total = pr.progress(plan)
        pids = {store.profile(m["pid"]).name: m["pid"] for m in t.member_list if store.profile(m["pid"])}
        return render_template("team_practice.html", t=t, tab="practice", premier_status=None, plan=plan, cfg=cfg_of(t),
                               weekday=pr.WEEKDAY, done=done, total=total, links=links(t, plan), pids=pids, today_iso=date.today().isoformat(),
                               discord=bool(t.discord_info.get("focus_url") or t.discord_info.get("prep_url")),
                               my_pids={p.id for p in store.profiles(g.user.id)})

    @app.post("/api/teams/<int:tid>/practice")
    def team_practice_api(tid: int):
        """Tick an item, add one, remove one (removing: the owner or whoever added it)."""
        t = get_team(tid)
        b = request.get_json(silent=True) or {}
        week = week_id()
        plan = read(tid, week) or make(t, week)
        day = next((d for d in plan["days"] if d["date"] == b.get("day")), None)
        if day is None:
            return jsonify(error="unknown day"), 400
        act = b.get("action")
        if act == "tick":
            it = next((x for x in day["items"] if x["id"] == b.get("id")), None)
            if it is None:
                return jsonify(error="unknown item"), 400
            it["done"] = bool(b.get("done"))
            it["by"] = g.user.display_name or g.user.username
        elif act == "add":
            title = str(b.get("title") or "").strip()[:100]
            if not title:
                return jsonify(error="the item needs a name"), 400
            try:
                minutes = max(0, min(240, int(b.get("minutes") or 15)))
            except ValueError:
                minutes = 15
            day["items"].append({"id": pr._id(), "kind": "own", "title": title, "detail": str(b.get("detail") or "").strip()[:300],
                                 "minutes": minutes, "who": "team", "link": "", "done": False,
                                 "added_by": g.user.id, "by": g.user.display_name or g.user.username})
        elif act == "remove":
            it = next((x for x in day["items"] if x["id"] == b.get("id")), None)
            if it is None:
                return jsonify(error="unknown item"), 400
            if not (g.team_owner or it.get("added_by") == g.user.id):
                return jsonify(error="only the team owner can remove planned items"), 403
            day["items"].remove(it)
        else:
            return jsonify(error="unknown action"), 400
        write(tid, plan)
        done, total = pr.progress(plan)
        return jsonify(ok=True, done=done, total=total)

    @app.post("/teams/<int:tid>/practice")
    def team_practice_settings(tid: int):
        t = get_team(tid, manage=True)
        f = request.form
        if f.get("action") == "remake":
            make(t, week_id())
            flash("Practice plan made again from the team's current numbers.", "ok")
        elif f.get("action") == "post_drills":                # 4.67: the team's drill week
            try:
                post_drills(t)
                flash("Posted this week's drills to Discord.", "ok")
            except Exception as e:
                flash(f"Not posted: {e}", "error")
        elif f.get("action") == "post":
            from ..discord import channel, post as dpost
            url = channel(t.discord_info, "focus")
            plan = read(tid, week_id()) or make(t, week_id())
            try:
                if not url:
                    raise RuntimeError("Add a Discord webhook under Team settings first.")
                dpost(url, pr.discord_text(plan, t.name))
                flash("Posted the practice plan to Discord.", "ok")
            except Exception as e:
                flash(f"Not posted: {e}", "error")
        else:
            days = sorted({int(d) for d in f.getlist("days") if str(d).isdigit() and 0 <= int(d) <= 6})
            time = f.get("time", "19:00")
            if not re.fullmatch(r"\d{1,2}:\d{2}", time):
                time = "19:00"
            try:
                minutes = max(30, min(240, int(f.get("minutes") or 90)))
            except ValueError:
                minutes = 90
            info = t.sync_info
            info["practice"] = {"days": days or pr.DEFAULT_DAYS, "time": time, "minutes": minutes, "post": f.get("post") == "1",
                                "drills_week": f.get("drills_week") == "1"}
            store.update_team(tid, sync=info)
            make(store.team(tid), week_id())
            flash("Practice days saved; this week's plan was made again.", "ok")
        return redirect(url_for("team_practice", tid=tid))

    def drills_of(t) -> dict:
        """4.67: the team's drill week (starters and subs), with this Premier week's map as the focus."""
        from ..stats import drills as dr
        from .stats_views import week_map_of
        players = []
        for mm in t.member_list:
            p = store.profile(mm["pid"])
            if p:
                from ..stats import drillgoals as dg
                sd_ = sr.games(p.id).path.parent
                runs_ = dr.read_runs(sd_)
                players.append((p.name, runs_, dg.status(dg.read(sd_), runs_)))
        focus = week_map_of(app, t) or (list(t.map_list)[0] if t.map_list else None)
        return dr.team_week(players, focus)

    def post_drills(t) -> None:
        from ..discord import channel, drills_embeds, post as dpost
        url = channel(t.discord_info, "focus")
        if not url:
            raise RuntimeError("Add a Discord webhook under Team settings first.")
        dpost(url, "", drills_embeds(t.name, week_id(), drills_of(t)))

    def tick_drills(now: datetime | None = None) -> list[int]:
        """4.67: Sundays from 20:00, once a week: the team's drill week to Discord (if on)."""
        now = now or datetime.now()
        if now.weekday() != 6 or now.hour < 20:
            return []
        done = []
        for t in store.all_teams():
            if not cfg_of(t).get("drills_week") or t.sync_info.get("drills_week_sent") == week_id():
                continue
            info = t.sync_info
            info["drills_week_sent"] = week_id()
            store.update_team(t.id, sync=info)
            try:
                post_drills(t)
                done.append(t.id)
            except Exception:
                pass
        return done

    app.extensions["nexus"].setdefault("ticks", []).append(tick_drills)
    app.extensions["nexus"]["drills_week"] = drills_of

    def tick() -> list[int]:
        """On practice days, 60 min before: a reminder to Discord (if on) and to everyone's devices."""
        from . import push
        now = datetime.now()
        done = []
        for t in store.all_teams():
            c = cfg_of(t)
            if now.weekday() not in (c.get("days") or []):
                continue
            try:
                hh, mm = (int(x) for x in str(c.get("time") or "19:00").split(":"))
            except ValueError:
                continue
            mins = (now.replace(hour=hh, minute=mm, second=0, microsecond=0) - now).total_seconds() / 60
            today = date.today().isoformat()
            if not (0 <= mins <= 60) or (t.sync_info.get("practice_sent") == today):
                continue
            info = t.sync_info
            info["practice_sent"] = today
            store.update_team(t.id, sync=info)
            plan = read(t.id, week_id())
            day = next((d for d in (plan or {}).get("days", []) if d["date"] == today), None)
            what = ", ".join(it["title"] for it in (day or {}).get("items", [])[:4]) or "practice"
            if c.get("post"):
                from ..discord import channel, post as dpost
                url = channel(t.discord_info, "focus")
                if url:
                    try:
                        dpost(url, f"**Practice today at {c['time']}** ({t.name}): {what}")
                    except Exception:
                        pass
            for u in store.users():
                if any(x.id == t.id for x in store.teams_for_user(u.id)):
                    push.send(store, u.id, f"Practice today at {c['time']}", what, url=f"/teams/{t.id}/practice",
                              tag=f"practice-{t.id}", kind="practice")
            done.append(t.id)
        return done

    app.extensions["nexus"].setdefault("ticks", []).append(tick)
