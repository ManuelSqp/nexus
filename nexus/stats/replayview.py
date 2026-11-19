"""The 3D replay viewer and the post-match utility check (4.44), from a match's replay file.

Everything here is in the 3D maps' frame (stats/map3d.py): metres on the minimap, x right, z down, y up (height
above the map's zero, the same height the rebuilt floors use), so players stand on the floors of the 3D map.

round_view(...)    one round for the viewer: every player's path (every PATH_MS, with view direction), the
                   kills, the spike, the placed utility and the ability casts, all in round time (seconds)
utility_check(...) per player: casts per ability key (C, Q, E, X), rounds with utility, deaths without having
                   used any, when the first ability of a round comes

Which ability key a cast in the replay is: the replay numbers its ability slots, and nothing documents which
number is which key. The match data counts each player's casts per key (C/Q/E/X) over the whole match, so the
numbering is worked out by comparing the two for all ten players (slot_keys). If they don't fit well enough the
casts are shown per slot number instead of being given a wrong key.
"""
from __future__ import annotations

import itertools
import math
import statistics

from .. import replayfile
from ..models import Match
from . import sight as sg
from .map3d import CELL, FOOT_CM, Frame

PATH_MS = 200                     # one point per player every 200 ms (the viewer moves smoothly between them)
REVIVE_AFTER = 1.0                # s after a death: from then on the replay having him again means he lives again
REVIVE_GAP = 1.0                  # s without positions (parked off the map while dead), then positions again
REVIVE_AWAY_CM = 150              # or moving this far from where he fell
REVIVE_FOR = 1.0                  # and his positions go on at least this long
KEYS = ("C", "Q", "E", "X")
MATCH_KEY = {"grenade": "C", "ability1": "Q", "ability_1": "Q", "ability2": "E", "ability_2": "E", "ultimate": "X"}
FIT_SHARE = 0.25                  # the slot numbering is used when it misses at most this share of all casts


class Ctx:
    """A match with its replay, lined up: built once per match and kept (web/replayview.py caches a few)."""

    def __init__(self, data: dict, match: Match, mi, agent_names: dict[str, str] | None = None,
                 game: dict | None = None):
        self.data, self.match, self.mi = data, match, mi
        # 4.48: the map built from the game's files: {"meta": mapmesh meta, "vox": see-through grid or None}
        self.game = game if game and game.get("meta") else None
        self.zones = sg.Zones(self.game["meta"].get("zones")) if self.game else None
        self.sight = sg.Sight(self.game["vox"]) if self.game and self.game.get("vox") else None
        self.foot_cm = FOOT_CM
        self.offsets, self.quality = replayfile.align(data, match)
        self.frame = Frame(mi) if mi is not None else None
        self.agent_names = agent_names or {}
        self.order = sorted(match.players, key=lambda p: (match.players[p].team, match.players[p].name.lower()))
        self.index = {p: i for i, p in enumerate(self.order)}
        self.starts = {int(n): int(t) for n, t in data.get("rounds") or []}
        self._casts = None
        self._lives: dict[int, dict] = {}
        self._effects = None
        if mi is not None:
            # view direction: the world -> minimap transform is linear for directions
            self._du = (0.0, mi.x_mult)            # d(u)/d(x), d(u)/d(y)
            self._dv = (mi.y_mult, 0.0)
        if self.game and mi is not None:
            f = self.game["meta"].get("foot_cm")
            self.foot_cm = f if f is not None else (self._measure_foot() or FOOT_CM)
        self._tracks = None
        self._reviews: dict[int, dict] = {}

    # -------------------------------------------------------------------------------------------- frame
    def to3d(self, x: float, y: float, z: float | None) -> tuple[float, float, float]:
        mx, mz = self.frame.to_m(x, y)
        return round(mx, 2), round(((z or 0.0) - self.foot_cm) / 100, 2), round(mz, 2)

    def _measure_foot(self) -> float | None:
        """4.48: how far above the game's floor this replay puts players (cm), when the map's build had no replays."""
        floors: dict = {}
        for i, j, h, *_ in self.game["meta"].get("cells") or []:
            floors.setdefault((i, j), []).append(h)
        d = []
        for rows in list((self.data.get("pos") or {}).values())[:10]:
            for r in rows[::25]:
                if len(r) < 4:
                    continue
                mx, mz = self.frame.to_m(r[1], r[2])
                lv = floors.get((math.floor(mx / CELL), math.floor(mz / CELL)))
                if not lv:
                    continue
                zm = r[3] / 100
                below = [h for h in lv if h <= zm + 0.3]
                if below and zm - max(below) < 2.5:
                    d.append(zm - max(below))
        return round(statistics.median(d) * 100, 1) if len(d) >= 50 else None

    def yaw3d(self, yaw_deg: float) -> float:
        a = math.radians(yaw_deg or 0.0)
        dx, dy = math.cos(a), math.sin(a)
        du = self._du[0] * dx + self._du[1] * dy
        dv = self._dv[0] * dx + self._dv[1] * dy
        return round(math.atan2(du, -dv), 2)              # 0 = up the minimap, like the 3D maps' camera

    # -------------------------------------------------------------------------------------------- meta
    def players(self, me: str = "") -> list[dict]:
        my_team = self.match.team_of(me) if me else ""
        out = []
        for p in self.order:
            pl = self.match.players[p]
            out.append({"i": self.index[p], "name": pl.name, "tag": pl.tag, "agent": pl.agent, "team": pl.team,
                        "ours": bool(my_team) and pl.team == my_team, "me": p == me})
        return out

    def rounds(self, me: str = "") -> list[dict]:
        my_team = self.match.team_of(me) if me else ""
        score: dict[str, int] = {t: 0 for t in self.match.teams}
        out = []
        for r in self.match.rounds:
            if r.winning_team:
                score[r.winning_team] = score.get(r.winning_team, 0) + 1
            ours = score.get(my_team, 0) if my_team else None
            theirs = (sum(score.values()) - ours) if ours is not None else None
            out.append({"i": r.index, "n": r.index + 1, "won": (r.winning_team == my_team) if my_team else None,
                        "result": r.result, "side": r.side_of(my_team) if my_team else "",
                        "score": f"{ours}–{theirs}" if ours is not None else "",
                        "has": r.index in self.offsets})
        return out

    # -------------------------------------------------------------------------------------------- one round
    def round_end_s(self, idx: int) -> float:
        return replayfile._round_end(self.match, idx, self.offsets, self.starts)

    # -------------------------------------------------------------------------------------------- 4.53.1: lives
    def lives(self, idx: int) -> dict[str, list[list[float]]]:
        """Per player: when he's alive in a round, [[from s, to s], …] in round time. Usually one stretch up to his
        death, but a player can live again: Clove's ult (she comes back after dying), Sage's resurrection. He's
        back when, after a death, the replay has him again after a pause (dead players are parked off the map),
        or moving away from where he fell, or (Clove) casting his ult; and his positions go on for a while."""
        if idx in self._lives:
            return self._lives[idx]
        r = self.match.rounds[idx]
        off = self.offsets.get(idx)
        out: dict[str, list[list[float]]] = {}
        if off is None:
            return out
        end = self.round_end_s(idx)
        known = {p.lower(): p for p in self.match.players}
        deaths: dict[str, list[float]] = {}
        for k in r.kills:
            deaths.setdefault(k.victim, []).append(k.t_round_ms / 1000)
        for t_ms, _killer, victim in self.data.get("deaths") or []:      # the replay's own (Clove's ult running out)
            p = known.get(str(victim).lower())
            t = (t_ms - off) / 1000
            if p and 0 <= t <= end and not any(abs(t - x) < 2.0 for x in deaths.get(p, [])):
                deaths.setdefault(p, []).append(t)
        ults: dict[str, list[float]] = {}
        keys = self.slot_keys()
        for t_ms, p, s in self.cast_events().get(idx) or []:
            if keys and keys.get(int(s)) == "X":
                ults.setdefault(p, []).append(t_ms / 1000)            # round time (ms)
        pos = {known.get(sub.lower()): pts for sub, pts in (self.data.get("pos") or {}).items()}
        for p in self.match.players:
            ds = sorted(deaths.get(p, []))
            pts = [((row[0] - off) / 1000, row[1], row[2]) for row in pos.get(p) or []]
            pts = [q for q in pts if -1 <= q[0] <= end]
            spans, start = [], -1.0
            for n, d in enumerate(ds):
                if start is None or d < start:
                    continue
                spans.append([start, d])
                start = None
                nxt = ds[n + 1] if n + 1 < len(ds) else end
                fell = next(((x, y) for t, x, y in reversed(pts) if t <= d), None)
                after = [q for q in pts if d + REVIVE_AFTER < q[0] < nxt]
                back = None
                prev = next((t for t, _x, _y in reversed(pts) if t <= d + REVIVE_AFTER), d)
                for t, x, y in after:
                    away = fell is not None and math.hypot(x - fell[0], y - fell[1]) > REVIVE_AWAY_CM
                    if t - prev >= REVIVE_GAP or away:
                        back = t
                        break
                    prev = t
                ult = next((u for u in sorted(ults.get(p, [])) if d < u < nxt), None)
                if ult is not None and (back is None or ult < back):
                    back = ult
                if back is not None and sum(1 for q in after if q[0] >= back) >= 3 and \
                        max(q[0] for q in after) - back >= REVIVE_FOR:
                    start = round(back, 2)
            if start is not None:
                spans.append([start, end])
            out[p] = [[round(a, 2), round(b, 2)] for a, b in spans]
        self._lives[idx] = out
        return out

    def round_view(self, idx: int) -> dict | None:
        if self.mi is None or idx not in self.offsets or not 0 <= idx < len(self.match.rounds):
            return None
        r = self.match.rounds[idx]
        off = self.offsets[idx]
        end = self.round_end_s(idx)
        known = {p.lower(): p for p in self.match.players}
        lives = self.lives(idx)
        paths: dict[int, list] = {}
        for sub, pts in (self.data.get("pos") or {}).items():
            puuid = known.get(sub.lower())
            if puuid is None:
                continue
            spans = lives.get(puuid) or [[-1.0, end]]
            stop = min(end, spans[-1][1] + 0.3)
            seq, last_b = [], None
            for row in pts:
                t_ms = row[0]
                t = (t_ms - off) / 1000
                if t < -1:
                    continue
                if t > stop:
                    break
                if not any(a - 0.05 <= t <= b + 0.3 for a, b in spans):
                    continue                              # dead in between (before living again)
                b = int(t_ms // PATH_MS)
                if b == last_b:
                    continue
                last_b = b
                x, y, z = self.to3d(row[1], row[2], row[3] if len(row) > 3 else 0.0)
                seq.append([round(t, 2), x, y, z, self.yaw3d(row[4] if len(row) > 4 else 0.0)])
            if seq:
                paths[self.index[puuid]] = seq
        kills = []
        reviews = self.reviews(idx)
        for n, k in enumerate(r.kills):
            if k.victim not in self.index:
                continue
            x, y, z = self.to3d(k.victim_x, k.victim_y, self._z_at(k.victim, off + k.t_round_ms))
            kd = {"t": round(k.t_round_ms / 1000, 2), "victim": self.index[k.victim],
                  "killer": self.index.get(k.killer), "weapon": k.weapon, "x": x, "y": y, "z": z}
            if n in reviews:
                kd.update(reviews[n])
            kills.append(kd)
        spike = []
        for ev in (r.plant, r.defuse):
            if ev is None:
                continue
            x, y, z = self.to3d(ev.x, ev.y, self._z_at(ev.player, off + ev.t_round_ms) if ev.player else None)
            spike.append({"kind": ev.kind, "t": round(ev.t_round_ms / 1000, 2), "site": ev.site,
                          "who": self.index.get(ev.player), "x": x, "y": y, "z": z})
        util = []
        for e in self.effects().get(idx) or []:
            x, y, z = self.to3d(e["x"], e["y"], None)
            owner = e.get("owner")
            util.append({"t0": round(e["t0"] / 1000, 2), "t1": round(e["t1"] / 1000, 2) if e.get("t1") is not None else None,
                         "type": e.get("type") or "", "agent": e.get("agent") or "", "slot": e.get("slot") or "",
                         "owner": self.index.get(owner) if owner else None, "x": x, "z": z,
                         "y": self._owner_floor(owner, off + e["t0"]) if owner else None})
        keys = self.slot_keys()
        casts = [[round(t / 1000, 2), self.index[p], keys.get(int(s), f"#{s}") if keys else f"#{s}"]
                 for t, p, s in self.cast_events().get(idx) or [] if p in self.index]
        again = {self.index[p]: v for p, v in lives.items() if p in self.index and len(v) > 1}
        return {"i": idx, "n": idx + 1, "end": round(end, 2), "paths": paths, "kills": kills, "spike": spike,
                "util": util, "casts": casts, "result": r.result, "winner": r.winning_team, "guns": self.guns(idx),
                "lives": {i: lives[p] for p in lives if p in self.index for i in [self.index[p]] if lives[p]} if again else {}}

    def guns(self, idx: int) -> dict[int, list]:
        """4.50: which gun each player holds in a round: {player: [[from s, weapon name], …]}: what he bought (the
        round's economy), then the weapon of each of his kills (picked up guns). Names the 3D viewer doesn't know
        (abilities, "Melee") are left out."""
        from .agentmesh import WEAPONS
        r = self.match.rounds[idx]
        out: dict[int, list] = {}
        for p, st in (r.stats or {}).items():
            if p in self.index and st.weapon in WEAPONS:
                out[self.index[p]] = [[0.0, st.weapon]]
        for k in sorted(r.kills, key=lambda k: k.t_round_ms):
            if k.killer not in self.index or k.weapon not in WEAPONS:
                continue
            seq = out.setdefault(self.index[k.killer], [])
            if not seq:
                seq.append([0.0, k.weapon])
            elif seq[-1][1] != k.weapon:
                seq.append([round(max(0.0, k.t_round_ms / 1000 - 1.0), 2), k.weapon])
        return out

    # -------------------------------------------------------------------------------------------- 4.48: deaths
    def tracks(self) -> sg.Tracks:
        if self._tracks is None:
            known = {p.lower(): p for p in self.match.players}
            self._tracks = sg.Tracks(self.data, known, lambda x, y, z: self.to3d(x, y, z), 0.0)
        return self._tracks

    def reviews(self, idx: int) -> dict[int, dict]:
        """Per kill of a round (by its place in the round's kills): where it happened (the game's callouts) and,
        with the see-through grid, who saw whom first, how many had a line to the victim, how long he was in the
        open (stats/sight.py)."""
        if idx in self._reviews:
            return self._reviews[idx]
        out: dict[int, dict] = {}
        if self.zones is None or idx not in self.offsets or self.mi is None:
            self._reviews[idx] = out
            return out
        r, off = self.match.rounds[idx], self.offsets[idx]
        tr = self.tracks()
        lives = self.lives(idx)

        def alive(p, ms):                                 # 4.53.1: alive again after Clove's ult or Sage's res
            t = (ms - off) / 1000
            spans = lives.get(p)
            return True if not spans else any(a <= t < b or (b >= self.round_end_s(idx) and t >= a) for a, b in spans)
        for n, k in enumerate(r.kills):
            t = off + k.t_round_ms
            d = {}
            x, y, z = self.to3d(k.victim_x, k.victim_y, self._z_at(k.victim, t))
            d["where"] = self.zones.at(x, y, z)
            kp = tr.at(k.killer, t) if k.killer else None
            if kp is not None:
                d["kwhere"] = self.zones.at(float(kp[0]), float(kp[1]), float(kp[2]))
            if self.sight is not None and k.victim in self.index:
                team = self.match.team_of(k.victim)
                enemies = [p for p in self.match.players if self.match.players[p].team != team]
                d["review"] = sg.death_review(self.sight, tr, t, k.victim, k.killer, enemies, alive,
                                              lambda deg: self.yaw3d(deg))
            out[n] = d
        self._reviews[idx] = out
        return out

    def death_summary(self, me: str) -> dict | None:
        """4.48: the player's deaths over the whole match: where (callouts) and, with line of sight, how often the
        enemy saw him first, how often he was open to more than one enemy, how often he never saw his killer."""
        if self.zones is None or not me:
            return None
        where: dict[str, int] = {}
        n = first = multi = unseen = known = 0
        for r in self.match.rounds:
            if r.index not in self.offsets:
                continue
            rv = self.reviews(r.index)
            for i, k in enumerate(r.kills):
                if k.victim != me or i not in rv:
                    continue
                n += 1
                w = rv[i].get("where") or "?"
                where[w] = where.get(w, 0) + 1
                rev = rv[i].get("review")
                if rev:
                    known += rev.get("first") is not None or rev.get("unseen") is not None
                    first += rev.get("first") == "killer" and not rev.get("unseen")
                    unseen += bool(rev.get("unseen"))
                    multi += (rev.get("open_to") or 0) > 1
        if not n:
            return {"deaths": 0, "where": [], "reviewed": 0}
        return {"deaths": n, "where": sorted(where.items(), key=lambda a: (-a[1], a[0])), "reviewed": known,
                "seen_first": first, "unseen": unseen, "open_many": multi, "sight": self.sight is not None}

    def _z_at(self, puuid: str, t_ms: float) -> float | None:
        sub = puuid.lower()
        pts = next((v for k, v in (self.data.get("pos") or {}).items() if k.lower() == sub), None)
        if not pts:
            return None
        best = None
        for row in pts:
            if row[0] > t_ms:
                break
            best = row
        best = best or pts[0]
        return best[3] if len(best) > 3 else None

    def _owner_floor(self, puuid: str, t_ms: float) -> float | None:
        z = self._z_at(puuid, t_ms)
        return None if z is None else round((z - self.foot_cm) / 100, 2)

    # -------------------------------------------------------------------------------------------- casts
    def cast_events(self) -> dict[int, list]:
        if self._casts is None:
            self._casts = replayfile.round_cast_events(self.data, self.match, self.offsets)
        return self._casts

    def effects(self) -> dict[int, list]:
        if self._effects is None:
            self._effects = replayfile.round_effects(self.data, self.match, self.offsets, self.agent_names)
        return self._effects

    def slot_keys(self) -> dict[int, str]:
        """Replay slot number -> ability key, worked out from the match's cast totals ({} if they don't fit)."""
        if hasattr(self, "_keys"):
            return self._keys
        self._keys = slot_keys(self.data.get("casts") or [], self.match)
        return self._keys

    def utility_check(self) -> dict:
        return utility_check(self)


def slot_keys(casts: list, match: Match) -> dict[int, str]:
    """casts: [[t, subject, slot], ...] of the whole replay. -> {slot number: "C"/"Q"/"E"/"X"} or {}."""
    known = {p.lower(): p for p in match.players}
    rep: dict[str, dict[int, int]] = {}
    for _t, sub, slot in casts:
        p = known.get(str(sub).lower())
        if p:
            rep.setdefault(p, {}).setdefault(int(slot), 0)
            rep[p][int(slot)] += 1
    api: dict[str, dict[str, int]] = {}
    for p, pl in match.players.items():
        d = {}
        for k, v in (pl.ability_casts or {}).items():
            key = MATCH_KEY.get(k.lower())
            if key:
                d[key] = d.get(key, 0) + int(v or 0)
        api[p] = d
    slots = sorted({s for d in rep.values() for s in d})
    total = sum(sum(d.values()) for d in api.values())
    if not slots or not total or len(slots) > 6:
        return {}
    best, best_err = None, math.inf
    for keys in itertools.permutations(KEYS + ("",) * max(0, len(slots) - len(KEYS)), len(slots)):
        err = 0
        for p in api:
            got: dict[str, int] = {}
            for s, n in (rep.get(p) or {}).items():
                k = keys[slots.index(s)]
                if k:
                    got[k] = got.get(k, 0) + n
            err += sum(abs(got.get(k, 0) - api[p].get(k, 0)) for k in KEYS)
        if err < best_err:
            best, best_err = keys, err
    if best is None or best_err > FIT_SHARE * total:
        return {}
    return {s: k for s, k in zip(slots, best) if k}


def utility_check(ctx: Ctx) -> dict:
    """{"keys_known": bool, "players": [{i, name, agent, team, per_key: {C: n, ...}, rounds, used_rounds,
    dry_deaths, deaths, first_s: {attack: s, defense: s}}], "rounds": n}."""
    m = ctx.match
    keys = ctx.slot_keys()
    ev = ctx.cast_events()
    per: dict[str, dict] = {}
    for p in ctx.order:
        pl = m.players[p]
        per[p] = {"i": ctx.index[p], "name": pl.name, "agent": pl.agent, "team": pl.team, "per_key": {}, "rounds": 0,
                  "used_rounds": 0, "deaths": 0, "dry_deaths": 0, "first": {"attack": [], "defense": []}}
    for r in m.rounds:
        if r.index not in ctx.offsets:
            continue
        casts = ev.get(r.index) or []
        died = {}
        for k in r.kills:
            died.setdefault(k.victim, k.t_round_ms)
        for p, o in per.items():
            mine = sorted(t for t, q, _s in casts if q == p)          # buy-phase casts (setups) count too
            o["rounds"] += 1
            o["used_rounds"] += int(bool(mine))
            if p in died:
                o["deaths"] += 1
                o["dry_deaths"] += int(not any(t <= died[p] for t in mine))
            live = [t for t in mine if t >= 0]                            # after the barriers drop
            if live:
                side = r.side_of(m.team_of(p))
                if side in o["first"]:
                    o["first"][side].append(live[0] / 1000)
        for _t, q, s in casts:
            if q in per:
                k = keys.get(int(s), f"#{s}") if keys else f"#{s}"
                per[q]["per_key"][k] = per[q]["per_key"].get(k, 0) + 1
    out = []
    for p, o in per.items():
        if not keys:                                    # keys unknown: the match totals per key, which are known
            totals = {}
            for k, v in (m.players[p].ability_casts or {}).items():
                key = MATCH_KEY.get(k.lower())
                if key:
                    totals[key] = totals.get(key, 0) + int(v or 0)
            o["per_key_match"] = totals
        o["first_s"] = {side: round(statistics.median(v), 1) if v else None for side, v in o.pop("first").items()}
        out.append(o)
    return {"keys_known": bool(keys), "players": out, "rounds": sum(1 for r in m.rounds if r.index in ctx.offsets)}
