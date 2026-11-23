"""4.57: the coach picks the games a question is about; a renamed player keeps their profile."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.coach import askcoach as ac  # noqa: E402
from nexus.coach import gamepick as gp  # noqa: E402

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 11, 23, 12, tzinfo=timezone.utc)


def _row(i, day, queue, agent, mp="Summit", won=1.0, k=20, d=12, full=True):
    return {"match_id": f"m{i}", "started_at": f"2026-11-{day:02d}T18:00:00Z", "queue": queue, "map": mp,
            "agent": agent, "won": won, "score": "13-9" if won else "9-13", "rounds": 22, "kills": k, "deaths": d,
            "assists": 5, "acs": 250.0, "adr": 150.0, "kast": 16, "fk": 3, "fd": 2, "shots": [30, 60, 10],
            "source": "full" if full else "stored"}


ROWS = [_row(1, 22, "premier", "Clove"), _row(2, 21, "premier", "KAY/O", won=0.0, k=15, d=15),
        _row(3, 20, "competitive", "KAY/O", mp="Haven"), _row(4, 10, "premier", "Omen", mp="Ascent"),
        _row(5, 1, "unrated", "Jett", mp="Bind", full=False)]


class LLM:
    """Answers the pick first, then the coach's answer; keeps what it was asked."""
    def __init__(self, pick):
        self.pick, self.asked = pick, []

    def chat_json(self, system, user, schema):
        self.asked.append((system, user))
        if "use" in schema["properties"]:
            if isinstance(self.pick, Exception):
                raise self.pick
            return self.pick
        return {"answer": "Play KAY/O.", "sources": []}


def _pick(**kw):
    return {"use": "pick", "queues": [], "agents": [], "maps": [], "last": 0, "days": 0, "why": "w", **kw}


def test_index_and_lines():
    ix = gp.index(ROWS)
    assert ix["games"] == 5 and ix["from"] == "2026-11-01" and ix["to"] == "2026-11-22"
    assert ix["modes"] == {"premier": 3, "competitive": 1, "unrated": 1} and ix["agents"]["KAY/O"] == 2
    assert ix["newest"][0] == "2026-11-22 Premier Summit Clove win 13-9, 20/12/5, ACS 250"
    assert gp.last_games(ROWS, 2)[1].startswith("2026-11-21 Premier Summit KAY/O loss 9-13")


def test_select():
    ids = lambda f: [r["match_id"] for r in gp.select(ROWS, dict({"queues": [], "agents": [], "maps": [], "last": 0, "days": 0}, **f), NOW)]  # noqa: E731
    assert ids({"queues": ["Premier"], "last": 2}) == ["m1", "m2"]                 # the last two Premier games
    assert ids({"agents": ["kayo"]}) == ["m2", "m3"]                                # KAY/O, however it's written
    assert ids({"queues": ["premier"], "agents": ["KAY/O", "Clove"]}) == ["m1", "m2"]
    assert ids({"days": 5}) == ["m1", "m2", "m3"] and ids({"maps": ["haven"]}) == ["m3"]
    assert ids({"queues": ["swiftplay"]}) == []


def test_block():
    f = {"queues": ["premier"], "agents": [], "maps": [], "last": 2, "days": 0, "why": "the last two Premier games"}
    b = gp.block(ROWS, f, NOW)
    assert b["which"] == "the last two Premier games" and b["found"] == 2 and "first sign" in b["note"]
    assert b["games"][1] == {"date": "2026-11-21", "mode": "Premier", "map": "Summit", "agent": "KAY/O", "result": "loss",
                             "score": "9-13", "k/d/a": "15/15/5", "acs": 250, "adr": 150, "kast": "73%",
                             "first_kills": 3, "first_deaths": 2, "headshots": "30%"}
    t = b["together"]
    assert t["games"] == 2 and t["win_rate"] == "50%" and t["kd"] == 1.3 and set(t["by_agent"]) == {"Clove", "KAY/O"}
    assert t["by_agent"]["KAY/O"]["win_rate"] == "0%"
    assert gp.block(ROWS, dict(f, queues=["swiftplay"]), NOW)["found"] == 0
    assert "adr" not in gp.block(ROWS, dict(f, queues=["unrated"]), NOW)["games"][0]      # no round data: no ADR


def test_plan():
    out = gp.plan(LLM(_pick(queues=["premier"], last=2, agents="x", days=-4)), "last two premier?", [], ROWS)
    assert out == {"queues": ["premier"], "agents": [], "maps": [], "last": 2, "days": 0, "why": "w"}
    assert gp.plan(LLM({"use": "none"}), "how to counter-strafe?", [], ROWS) is None
    assert gp.plan(LLM(RuntimeError("down")), "q", [], ROWS) is None
    assert gp.plan(LLM(_pick()), "q", [], []) is None


def test_the_coach_gets_the_games():
    llm = LLM(_pick(queues=["premier"], last=2, why="the last two Premier games"))
    steps = []
    out = ac.answer(llm, "adv1ce", "English", "my last two premier games: kayo or clove?", [], {"recent": {}},
                    step=steps.append, rows=ROWS)
    assert out["answer"] == "Play KAY/O." and out["picked"] == "the last two Premier games (2 games)"
    assert "Picking the games" in steps
    user = llm.asked[-1][1]
    assert "selected_games:" in user and "the last two Premier games" in user and "last_games:" in user
    assert "selected_games" in llm.asked[-1][0]                                     # and how to read it
    out = ac.answer(LLM({"use": "none"}), "adv1ce", "English", "aim tips?", [], {"recent": {}}, rows=ROWS)
    assert out["picked"] == ""
    assert ac.answer(LLM(_pick()), "a", "English", "q", [], {})["picked"] == ""        # without rows: as before


class _Client:
    def __init__(self, name, tag, fail=False):
        self.acc, self.fail = {"name": name, "tag": tag}, fail

    def _get(self, path):
        if self.fail:
            raise RuntimeError("HTTP 404")
        assert path == "/valorant/v2/by-puuid/account/PUUID-1"
        return {"data": self.acc}


def _games(sr, pid, puuid="PUUID-1", n=1):
    gs = sr.games(pid)
    d = gs.load()
    d["puuid"] = puuid
    d["games"] = {f"g{i}": {"match_id": f"g{i}"} for i in range(n)}
    gs.save(d)


def test_a_renamed_player_keeps_their_profile(app):  # noqa: F811
    c = setup_admin(app)
    store, sr = app.extensions["nexus"]["store"], app.extensions["nexus"]["stats"]
    pid = add_profile(c, "m1stake", "#2go")
    dup = add_profile(c, "Aki Hayakawa", "#2go")                # added again under the new name, no games
    other = add_profile(c, "BurnTheGoat", "#NOW")
    uid = store.profile(pid).owner_id
    tid = store.create_team(uid, "Peek911")
    store.update_team(tid, members=[{"pid": dup, "kind": "starter"}, {"pid": other, "kind": "starter"}])
    _games(sr, pid)
    logs = []
    p = sr.follow_rename(store.profile(pid), _Client("Aki Hayakawa", "2go"), logs.append)
    assert p.id == pid and p.riot_id == "Aki Hayakawa#2go" and store.profile(pid).name == "Aki Hayakawa"
    assert store.profile(dup) is None and not store.profile_dir(dup).exists()
    assert store.team(tid).member_list == [{"pid": pid, "kind": "starter"}, {"pid": other, "kind": "starter"}]
    assert sr.games(pid).load()["games"] and any("renamed" in x for x in logs) and any("folded" in x for x in logs)
    # same name again: nothing to do; the account lookup failing doesn't stop anything
    assert sr.follow_rename(store.profile(pid), _Client("aki hayakawa", "2GO"), logs.append).name == "Aki Hayakawa"
    assert sr.follow_rename(store.profile(pid), _Client("x", "y", fail=True), logs.append).name == "Aki Hayakawa"
    # both have games: left alone, and the import says so
    _games(sr, other, "PUUID-2")
    logs.clear()
    two = add_profile(c, "adv1ce", "#LFT")
    _games(sr, two)
    p = sr.follow_rename(store.profile(two), _Client("BurnTheGoat", "NOW"), logs.append)
    assert p.riot_id == "adv1ce#LFT" and store.profile(other) is not None and "games of its own" in logs[0]
    # no account id yet (never imported): nothing
    fresh = add_profile(c, "nobody", "#000")
    assert sr.follow_rename(store.profile(fresh), _Client("x", "y"), logs.append).riot_id == "nobody#000"


def test_import_follows_renames():
    js = (ROOT / "nexus/web/statsjobs.py").read_text()
    assert "p = self.follow_rename(p, client, lambda m: self._log(key, m))" in js
    assert js.index("self.follow_rename(p, client") < js.index("res = import_games(client, p.region, p.platform, p.name")


def test_page_shows_the_games():
    html = (ROOT / "nexus/web/templates/ask_coach.html").read_text()
    assert "{% if it.picked %}<span>Games: {{ it.picked }}</span>{% endif %}" in html and "T('Games:')" in html
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    assert de["Games:"] == "Spiele:"


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 57)
    assert "## 4.57.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
