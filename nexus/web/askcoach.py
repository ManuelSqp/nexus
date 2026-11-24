"""Practice › Ask the coach (per player): a chat with the coach about this player, with web search when it's
set up. Each user has their own conversation per player: data/profiles/<pid>/stats/ask-u<uid>.json.
Answers are written in the background (a local model can take a minute); the page polls for them."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from markupsafe import Markup, escape
from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for

from ..coach import askcoach as ac
from ..coach.llm import ClaudeError, NoAnswer, user_error
from ..coach.ollama import OllamaError
from ..coach import websearch as ws

MAX_ITEMS = 60
log = logging.getLogger(__name__)
_ex = ThreadPoolExecutor(max_workers=2, thread_name_prefix="askcoach")
_state: dict[tuple[int, int], dict] = {}            # (uid, pid) -> {"step": ..., "error": ..., "q": ...}
_lock = threading.Lock()


def _read(path: Path) -> dict:
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) else {"items": []}
    except (OSError, ValueError):
        return {"items": []}


def register(app, store, sr, view_profile, filter_rows) -> None:
    from .aim import player_runs
    from ..stats import kovaaks as kv
    from .trainer import trainer_data

    @app.template_filter("askfmt")
    def askfmt(text) -> Markup:
        """The coach's answer as HTML: paragraphs, line breaks and **bold**; everything else escaped."""
        out = []
        for para in re.split(r"\n{2,}", str(text or "").strip()):
            h = str(escape(para))
            h = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h).replace("\n", "<br>")
            out.append(f"<p>{h}</p>")
        return Markup("".join(out))

    def path(pid: int, uid: int) -> Path:
        return store.profile_dir(pid) / "stats" / f"ask-u{int(uid)}.json"

    @app.get("/profiles/<int:pid>/ask")
    def ask_coach(pid: int):
        p, _ = view_profile(pid)
        items = _read(path(pid, g.user.id)).get("items", [])
        with _lock:
            st = dict(_state.get((g.user.id, pid)) or {})
        return render_template("ask_coach.html", p=p, active_pid=pid, items=items, pending=st if "step" in st else None,
                               letter=letter_state(pid), can_edit=_,
                               search_on=bool(ws.provider(store)), search_name=" → ".join(ws.PROVIDERS[x].split(" (")[0] for x in (ws.provider(store), ws.backup(store)) if x),
                               games=len(sr.games(pid).rows()))

    @app.post("/api/profiles/<int:pid>/ask")
    def ask_coach_post(pid: int):
        from .models import picked
        p, _ = view_profile(pid)
        uid = g.user.id
        b = request.get_json(silent=True) or {}
        q = " ".join(str(b.get("question") or "").split())[:ac.MAX_Q]
        if not q:
            return jsonify(error="Ask a question first."), 400
        key = (uid, pid)
        with _lock:
            if "step" in (_state.get(key) or {}):
                return jsonify(error="The coach is still answering your last question."), 409
            _state[key] = {"step": "Waiting for the model", "q": q, "t": time.time()}
        choice = picked(store)
        search = ws.searcher(store)

        def step(text: str) -> None:
            with _lock:
                if key in _state:
                    _state[key]["step"] = text

        def work():
            try:
                llm, _cfg = sr._llm(p, choice)
                rows = filter_rows(sr.games(pid).rows(), "everything")
                data = ac.facts(p.riot_id, rows, player_runs(sr, pid) if kv.WEB else [], trainer_data(sr, pid))
                data.update(sr.coach_extras(pid, rows, store.data_dir / "cache"))     # 4.15
                f = path(pid, uid)
                hist = _read(f).get("items", [])
                out = ac.answer(llm, p.name, p.language or "English", q, hist, data, search=search, step=step,
                                rows=rows)
                with _lock:
                    d = _read(f)
                    d.setdefault("items", []).append({"q": q, "a": out["answer"], "sources": out["sources"],
                                                      "searched": out["searched"], "search_errors": out["search_errors"],
                                                      "picked": out.get("picked", ""),
                                                      "model": getattr(llm, "model", ""), "t": time.time()})
                    del d["items"][:-MAX_ITEMS]
                    f.parent.mkdir(parents=True, exist_ok=True)
                    tmp = f.with_suffix(".tmp")
                    tmp.write_text(json.dumps(d, ensure_ascii=False))
                    tmp.replace(f)
                    _state.pop(key, None)
            except Exception as e:                       # shown once under the question box
                log.warning("ask the coach: %s", e, exc_info=not isinstance(e, (OllamaError, ClaudeError, NoAnswer)))
                with _lock:
                    _state[key] = {"error": user_error(e), "q": q}
        _ex.submit(work)
        return jsonify(ok=True, pending=True)

    @app.get("/api/profiles/<int:pid>/ask")
    def ask_coach_state(pid: int):
        view_profile(pid)
        key = (g.user.id, pid)
        with _lock:
            st = dict(_state.get(key) or {})
            if "error" in st:
                _state.pop(key, None)
        items = _read(path(pid, g.user.id)).get("items", [])
        return jsonify(items=items[-MAX_ITEMS:], pending="step" in st, step=st.get("step", ""),
                       error=st.get("error", ""), q=st.get("q", ""))

    # ---------------------------------------------------------------- 4.69: the weekly letter from the coach
    from ..coach import letter as lt

    def sdir(pid: int) -> Path:
        return sr.games(pid).path.parent

    def write_letter(p, choice=None, notify: bool = False, now: float | None = None) -> None:
        """In the background: this week's letter for one player (and a push to its owner when notify)."""
        key = ("letter", p.id)
        with _lock:
            if "step" in (_state.get(key) or {}):
                return
            _state[key] = {"step": "Writing", "t": time.time()}

        def work():
            from ..stats import drills as dr
            try:
                llm, _cfg = sr._llm(p, choice if choice is not None else sr.AUTO)   # Monday: the automatic-jobs model
                rows = filter_rows(sr.games(p.id).rows(), "everything")
                f = lt.facts(p.name, rows, dr.read_runs(sdir(p.id)), now)
                out = lt.write(llm, p.name, p.language or "English", f)
                with _lock:
                    lt.save(sdir(p.id), f["week"], out, getattr(llm, "model", ""))
                    _state.pop(key, None)
                if notify and p.owner_id:
                    from . import push
                    push.send(store, p.owner_id, f"Your week from the coach ({p.name})", out["letter"][:140],
                              url=f"/profiles/{p.id}/ask#letter", tag=f"letter-{p.id}", kind="letter")
            except Exception as e:
                log.warning("weekly letter: %s", e, exc_info=not isinstance(e, (OllamaError, ClaudeError, NoAnswer)))
                with _lock:
                    _state[key] = {"error": user_error(e)}
        _ex.submit(work)

    def letter_state(pid: int) -> dict:
        with _lock:
            st = dict(_state.get(("letter", pid)) or {})
            if "error" in st:
                _state.pop(("letter", pid), None)
        cur = lt.latest(sdir(pid))
        d = lt.read(sdir(pid))
        return {"week": cur[0] if cur else "", "letter": cur[1] if cur else None, "auto": bool(d.get("auto")),
                "this_week": lt.week_of(time.time()), "pending": "step" in st, "error": st.get("error", "")}

    @app.post("/profiles/<int:pid>/letter")
    def coach_letter(pid: int):
        p, can_edit = view_profile(pid)
        if not can_edit:
            abort(403)
        f = request.form
        if "auto" in f:
            lt.set_auto(sdir(pid), f.get("auto") == "1")
            flash("Saved: " + ("the coach writes your letter every Monday morning." if f.get("auto") == "1"
                               else "no weekly letter by itself; write it when you want."), "ok")
        else:
            from .models import picked
            write_letter(p, picked(store))
        return redirect(url_for("ask_coach", pid=pid) + "#letter")

    def tick_letters(now=None) -> list[int]:
        """4.69: Mondays from 07:00: this week's letter for every player who asked for it every week."""
        import datetime as _dt
        now = now or _dt.datetime.now()
        if now.weekday() != 0 or now.hour < 7:
            return []
        wk = lt.week_of(now.timestamp())
        done = []
        for u in store.users():
            for p in store.profiles(u.id):
                d = lt.read(sdir(p.id))
                if d.get("auto") and wk not in (d.get("weeks") or {}) and d.get("tried") != wk:
                    d["tried"] = wk
                    lt._write(sdir(p.id), d)
                    write_letter(p, notify=True, now=now.timestamp())
                    done.append(p.id)
        return done

    app.extensions["nexus"].setdefault("ticks", []).append(tick_letters)

    @app.post("/profiles/<int:pid>/ask/clear")
    def ask_coach_clear(pid: int):
        view_profile(pid)
        path(pid, g.user.id).unlink(missing_ok=True)
        flash("New conversation.", "ok")
        return redirect(url_for("ask_coach", pid=pid))
