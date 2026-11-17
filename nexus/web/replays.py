"""Replay files (.vrf) on the server (4.9): upload on the coach page, on the Replay files page (4.40, any match,
several at once) or from the Nexus app.

A replay is uploaded in pieces like a VOD (uploads.py), then vrfkit reads it once: the compact data and the
file are kept as data/replays/<match id>.json.gz and .vrf (see nexus/replayfile.py). One file serves every
player of that match, so it is stored per match, not per user; a coaching run of that match uses it when
Settings › Replay files › Positions is "Replay file".
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from flask import abort, g, jsonify, render_template, request, url_for

from .. import pipeline, replayfile, vrfkit_update
from .uploads import CHUNK_BYTES, UploadError

log_ = logging.getLogger(__name__)

_ingest_lock = threading.Lock()      # vrfkit is quick, but one at a time keeps memory use predictable


def replays_dir(store) -> Path:
    return store.data_dir / "replays"


# ---------------------------------------------------------------- 4.47: match details for any replay
# The stats import only loads Competitive, Premier and Unrated, so a replay of a Custom game (or of a teammate's
# match) had no match details: names, teams, rounds and kills come from HenrikDev, not from the replay file.
# They're now loaded by match id: right after the upload, on opening the replay and every few minutes for older
# files. A match HenrikDev doesn't have is tried again after MATCH_RETRY_S.
MATCH_RETRY_S = 6 * 3600
FETCH_PER_TICK = 4
_miss_lock = threading.Lock()


def match_file(store, mid: str) -> Path:
    return Path(store.data_dir) / "cache" / "matches" / f"{mid.lower()}.json"


def _misses_file(store) -> Path:
    return Path(store.data_dir) / "cache" / "replay_match_misses.json"


def _misses(store) -> dict:
    try:
        d = json.loads(_misses_file(store).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _note_miss(store, mid: str, err: str) -> None:
    with _miss_lock:
        d = _misses(store)
        d[mid] = {"t": time.time(), "error": err[:200]}
        f = _misses_file(store)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.replace(tmp, f)


def regions(store, first: str = "") -> list[str]:
    """The regions to try for a match id: the given one, then the players' regions (most used first)."""
    out = [first.lower()] if first else []
    try:
        rows = store._all("SELECT region, COUNT(*) AS n FROM profiles GROUP BY region ORDER BY n DESC")
    except Exception:
        rows = []
    for r in rows:
        reg = str(r["region"] or "").lower()
        if reg and reg not in out:
            out.append(reg)
    return out or ["eu"]


def fetch_match(store, mid: str, region: str = "", force: bool = False) -> bool:
    """Loads the match details of a replay into the match cache. True when they're there (now or already)."""
    mid = mid.lower()
    if not replayfile.UUID_RE.fullmatch(mid):
        return False
    if match_file(store, mid).is_file():
        return True
    if not force:
        last = _misses(store).get(mid)
        if last and time.time() - float(last.get("t") or 0) < MATCH_RETRY_S:
            return False
    key = store.get("henrik_api_key")
    if not key:
        return False
    from ..henrik import HenrikClient, HenrikError
    try:
        cl = HenrikClient(key, Path(store.data_dir) / "cache", store.get("henrik_base_url") or "https://api.henrikdev.xyz",
                          max_retries=1)
    except HenrikError:
        return False
    err = ""
    for reg in regions(store, region):
        try:
            d = cl.match(reg, mid)
        except HenrikError as e:
            err = str(e)
            continue
        except Exception as e:                       # network trouble: try again later
            err = f"{type(e).__name__}: {e}"
            break
        if (d or {}).get("data"):
            if not match_file(store, mid).is_file():     # an unfinished match isn't cached by the client
                match_file(store, mid).write_text(json.dumps(d))
            return True
    _note_miss(store, mid, err or "not found")
    return False


def match_brief(store, mid: str, riot_id: str = "") -> dict | None:
    """Map, mode, date and score of a cached match, and whether riot_id played in it (None: not loaded)."""
    try:
        raw = json.loads(match_file(store, mid).read_text())
    except (OSError, ValueError):
        return None
    d = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
    if not isinstance(d, dict):
        return None
    meta = d.get("metadata") or {}
    q = meta.get("queue") or {}
    mode = (q.get("name") or q.get("id") or meta.get("mode") or "") if isinstance(q, dict) else str(q)
    mp = meta.get("map") or {}
    mapname = mp.get("name", "") if isinstance(mp, dict) else str(mp)
    rid = riot_id.lower()
    me = None
    for pl in d.get("players") or []:
        if isinstance(pl, dict) and f"{pl.get('name', '')}#{pl.get('tag', '')}".lower() == rid:
            me = pl
            break
    score, won = "", None
    teams = d.get("teams") or []
    if me and isinstance(teams, list):
        mine = next((t for t in teams if isinstance(t, dict) and t.get("team_id") == me.get("team_id")), None)
        other = next((t for t in teams if isinstance(t, dict) and t is not mine), None)
        if mine and other:
            a, b = (mine.get("rounds") or {}).get("won"), (other.get("rounds") or {}).get("won")
            if a is not None and b is not None:
                score = f"{a}–{b}"
                won = 1 if a > b else 0 if a < b else None
    agent = ""
    if me:
        ag = me.get("agent") or {}
        agent = ag.get("name", "") if isinstance(ag, dict) else str(ag)
    return {"match_id": mid, "map": mapname, "mode": str(mode), "started_at": meta.get("started_at") or "",
            "played": me is not None, "agent": agent, "score": score, "won": won}


def begin_upload(store, uploads, uid: int, data) -> dict:
    """Checks for starting a .vrf upload; returns {id, chunk}."""
    if not isinstance(data, dict) or type(data.get("size")) is not int or data["size"] <= 0:
        raise UploadError("expected {\"name\": file name, \"size\": bytes}")
    name = os.path.basename(str(data.get("name") or ""))
    if Path(name).suffix.lower() != ".vrf":
        raise UploadError("That isn't a replay file (.vrf).")
    if data["size"] > replayfile.MAX_VRF_BYTES:
        raise UploadError("That file is too big for a replay file.", 413)
    return {"id": uploads.begin(uid, name, data["size"]).id, "chunk": CHUNK_BYTES}


class PendingReplay(UploadError):
    """The file was kept: vrfkit can't read this patch yet (see replayfile.keep_pending)."""
    def __init__(self, meta: dict):
        super().__init__(f"Kept on the server: vrfkit can't read replays of patch {meta['patch']} yet. "
                         "It's read automatically once it can.", 422)
        self.meta = meta


def ingest_upload(store, uploads, uid: int, upload_id: str) -> dict:
    """A finished .vrf upload -> stored replay data. Returns replayfile.summary(); raises UploadError."""
    work = store.data_dir / "cache" / "vrf_work"
    work.mkdir(parents=True, exist_ok=True)
    dest, name = uploads.finish(uid, upload_id, work)
    vk = replayfile.vrfkit_path(store.get("vrfkit_path"))
    try:
        with _ingest_lock:
            return replayfile.ingest(dest, replays_dir(store), work, vk)
    except replayfile.UnsupportedBuild as e:     # 4.43: a brand-new patch: keep the file, read it once vrfkit can
        meta = replayfile.keep_pending(dest, replays_dir(store), e, name=str(name or ""), uid=uid, vrfkit=vk)
        raise PendingReplay(meta)
    except replayfile.ReplayError as e:
        raise UploadError(str(e), 422)
    except Exception as e:                       # 4.42.1: a readable answer instead of "Error 500"; the log has it all
        log_.exception("replay %s could not be read", upload_id)
        raise UploadError(f"This replay file couldn't be read ({type(e).__name__}). The server log has the details.", 422)
    finally:
        Path(dest).unlink(missing_ok=True)       # moved into data/replays on success


def register(app, store, uploads, get_profile) -> None:
    def reread() -> None:
        """Once after an update that fixed reading (replayfile.READER): read the kept .vrf files again, in the
        scheduler's thread. Skipped when vrfkit isn't there (the marker isn't written then, so it runs later)."""
        if (replays_dir(store) / f".reader-{replayfile.READER}").exists():
            return                                       # done (the usual case: nothing to run)
        vk = replayfile.vrfkit_path(store.get("vrfkit_path"))
        if replayfile.check_vrfkit(vk):
            return
        replayfile.reread_all(replays_dir(store), store.data_dir / "cache" / "vrf_work", vk, lock=_ingest_lock)
    app.extensions["nexus"].setdefault("ticks", []).append(reread)

    def retry() -> None:
        """Every 5 minutes: kept files of a patch vrfkit couldn't read are tried again once vrfkit changed."""
        if not replayfile.pending(replays_dir(store)):
            return
        replayfile.retry_pending(replays_dir(store), store.data_dir / "cache" / "vrf_work",
                                 replayfile.vrfkit_path(store.get("vrfkit_path")), lock=_ingest_lock)
    app.extensions["nexus"]["ticks"].append(retry)
    app.extensions["nexus"]["replays_retry"] = retry         # for tests

    def details() -> None:
        """Every 5 minutes: match details for a few kept replays that have none yet (Customs, teammates' matches)."""
        d = replays_dir(store)
        todo = [m for m in reversed(replayfile.stored(d)) if not match_file(store, m).is_file()]
        if not todo or not store.get("henrik_api_key"):
            return
        n = 0
        for mid in todo:
            last = _misses(store).get(mid)
            if last and time.time() - float(last.get("t") or 0) < MATCH_RETRY_S:
                continue
            fetch_match(store, mid)
            n += 1
            if n >= FETCH_PER_TICK:
                break
    app.extensions["nexus"]["ticks"].append(details)
    app.extensions["nexus"]["replays_details"] = details     # for tests
    app.extensions["nexus"]["replays_reread"] = reread      # for tests

    @app.post("/api/replays")
    def replay_upload_begin():
        """Start a replay upload (JSON only, like /api/uploads); the pieces go to PUT /api/uploads/<id>."""
        return jsonify(**begin_upload(store, uploads, g.user.id, request.get_json(silent=True)))

    @app.post("/profiles/<int:pid>/coach/<match_id>/replay")
    def replay_attach(pid: int, match_id: str):
        """The finished upload is this match's replay file."""
        get_profile(pid)
        if not pipeline.valid_match_id(match_id):
            abort(404)
        b = request.get_json(silent=True) or {}
        info = ingest_upload(store, uploads, g.user.id, str(b.get("upload_id") or ""))
        if info["match_id"] != match_id.lower():
            # stored anyway (it's a real replay of another match), but say so
            return jsonify(ok=False, match_id=info["match_id"],
                           error="This replay file is from another match. It was kept for that match."), 409
        return jsonify(ok=True, **info)

    # ------------------------------------------------------------------ 4.40: Replay files page, upload any replay
    @app.post("/api/replays/<upload_id>/store")
    def replay_store(upload_id: str):
        """A finished upload is a replay of whichever match it is: no coaching run needed. -> the summary, the map
        if the match is known, and whether it's one of this player's matches (?pid=)."""
        try:
            info = ingest_upload(store, uploads, g.user.id, upload_id)
        except PendingReplay as e:
            return jsonify(ok=True, pending=True, patch=e.meta["patch"], name=e.meta["name"]), 202
        mine = None
        pid = request.args.get("pid", type=int)
        if pid:
            p, _e = app.extensions["nexus"]["view_profile"](pid)
            rows = {r.get("match_id", "").lower(): r for r in _rows(app, pid)}
            r = rows.get(info["match_id"])
            mine = bool(r)
            if r:
                info["map"] = r.get("map") or ""
                info["started_at"] = r.get("started_at") or ""
            elif fetch_match(store, info["match_id"], p.region, force=True):     # 4.47: a Custom game and the like
                b = match_brief(store, info["match_id"], p.riot_id) or {}
                info.update(map=b.get("map", ""), mode=b.get("mode", ""), started_at=b.get("started_at", ""),
                            played=bool(b.get("played")))
            info["watch"] = url_for("replay_view", pid=pid, match_id=info["match_id"])
        return jsonify(ok=True, mine=mine, **info)

    @app.get("/profiles/<int:pid>/replays")
    def replay_files(pid: int):
        """Upload replay files (several at once, any match) and see which of your matches have one."""
        p, can_edit = app.extensions["nexus"]["view_profile"](pid)     # yours, or a teammate's: a replay is the match's
        d = replays_dir(store)
        have = set(replayfile.stored(d))
        rows = sorted(_rows(app, pid), key=lambda r: r.get("started_at") or "", reverse=True)
        with_replay = [r for r in rows if (r.get("match_id") or "").lower() in have]
        recent_missing = [r for r in rows[:RECENT] if (r.get("match_id") or "").lower() not in have]
        problem = replayfile.check_vrfkit(replayfile.vrfkit_path(store.get("vrfkit_path") or ""))
        waiting = replayfile.pending(d)
        mine_ids = {(r.get("match_id") or "").lower() for r in rows}
        others = []                                      # 4.47: Customs and other matches with a replay
        for mid in [m for m in have if m not in mine_ids]:
            b = match_brief(store, mid, p.riot_id) or {"match_id": mid, "map": "", "mode": "", "started_at": "",
                                                       "played": False, "agent": "", "score": "", "won": None,
                                                       "loading": True}
            others.append(b)
        others.sort(key=lambda b: b["started_at"] or "", reverse=True)          # newest first,
        others.sort(key=lambda b: (not b["played"], bool(b.get("loading"))))     # then the ones you played in on top
        return render_template("replay_files.html", p=p, active_pid=pid, can_edit=can_edit, with_replay=with_replay,
                               missing=recent_missing, total=len(have), others=len(have) - len(with_replay),
                               other_replays=others[:OTHERS_SHOWN], others_more=max(0, len(others) - OTHERS_SHOWN),
                               problem=problem, waiting=waiting, update=vrfkit_update.state(store.data_dir), max_mb=replayfile.MAX_VRF_BYTES // 1024 ** 2, recent=RECENT)


OTHERS_SHOWN = 30
RECENT = 15                         # the Replay files page lists your last this-many matches without a replay


def _rows(app, pid: int) -> list[dict]:
    try:
        return list(app.extensions["nexus"]["stats"].games(pid).rows())
    except Exception:                                    # no stats yet
        return []
