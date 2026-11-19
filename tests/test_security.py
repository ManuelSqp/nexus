"""4.52.1: the code-scanning fixes (paths from outside data, HTML from data, redirects, error messages)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.safepath import UnsafePath, inside, safe_join, valid_match_id  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"


# ------------------------------------------------------------------------------------------------ paths
def test_safe_join(tmp_path):
    assert safe_join(tmp_path, "matches", "abc.json") == (tmp_path / "matches" / "abc.json").resolve()
    assert safe_join(tmp_path, 7) == (tmp_path / "7").resolve()
    for bad in (("..",), ("/etc/passwd",), ("a", "../../x"), ("matches", "../../etc.json")):
        with pytest.raises(UnsafePath):
            safe_join(tmp_path, *bad)
    (tmp_path / "out").symlink_to("/")                        # a link out of the folder counts as outside
    with pytest.raises(UnsafePath):
        safe_join(tmp_path, "out", "etc")
    assert inside(tmp_path, tmp_path / "a" / "b") and not inside(tmp_path / "a", tmp_path)
    assert valid_match_id("0f3c-AB12") and not valid_match_id("../x") and not valid_match_id(5)


def test_load_match_only_ids_unless_allowed(tmp_path, synthetic):  # noqa: F811
    from nexus import pipeline
    from nexus.config import Config, PathsCfg
    cfg = Config(paths=PathsCfg(cache_dir=str(tmp_path)), root=tmp_path)
    path = str(synthetic["match"])
    with pytest.raises(ValueError):
        pipeline.load_match(cfg, path)                          # the web app: never a file
    m = pipeline.load_match_from_file(path)                   # the CLI
    assert m.match_id and m.rounds
    from nexus.cli import _load
    assert _load(cfg, path).match_id == m.match_id                # the CLI takes a file or an ID
    with pytest.raises(ValueError):
        pipeline.run(cfg, pipeline.CoachRequest(match=path, no_llm=True), lambda *a: None)   # a request: IDs only
    with pytest.raises(ValueError):
        pipeline.load_match_from_file(tmp_path / "nothing.json")
    with pytest.raises(ValueError):
        pipeline.load_match_from_file(__file__)                # not a .json


def test_henrik_cache_only_ids(tmp_path):
    from nexus.henrik import HenrikClient, HenrikError
    cl = HenrikClient("key", tmp_path)
    (tmp_path / "secret.json").write_text("{}")
    for bad in ("../secret", "a/b", ""):
        with pytest.raises(HenrikError):
            cl.match("eu", bad)
    (tmp_path / "matches").mkdir(exist_ok=True)
    (tmp_path / "matches" / "abc-1.json").write_text('{"data": {"x": 1}}')
    assert cl.match("eu", "abc-1") == {"data": {"x": 1}}


def test_profile_dir_is_a_number(app):  # noqa: F811
    store = app.extensions["nexus"]["store"]
    assert store.profile_dir(3).name == "3" and store.profile_dir("4").name == "4"
    with pytest.raises(ValueError):
        store.profile_dir("../x")


def test_catalog_by_code_only():
    from nexus import i18n
    assert i18n.catalog("de") is not None
    for bad in ("en", "../de", "xx", "de.json"):
        assert i18n.catalog(bad) is None


def test_recordings_folder(app, tmp_path, monkeypatch):  # noqa: F811
    c = setup_admin(app)
    allowed = tmp_path / "vods"
    allowed.mkdir()
    r = c.post("/admin/users", data={"username": "bob", "password": "bob-pass-123", "vod_dir": "/no/such/folder"},
               follow_redirects=True)
    page = r.data.decode()
    assert "Recordings folder not found on this server." in page and "/no/such/folder" not in page
    monkeypatch.setenv("NEXUS_VOD_ROOTS", str(allowed))
    r = c.post("/admin/users", data={"username": "bob", "password": "bob-pass-123", "vod_dir": "/tmp"},
               follow_redirects=True)
    assert "allowed on this server" in r.data.decode()
    store = app.extensions["nexus"]["store"]
    assert store.user_by_name("bob") is None
    c.post("/admin/users", data={"username": "bob", "password": "bob-pass-123", "vod_dir": str(allowed / ".." / "vods")})
    assert store.user_by_name("bob").vod_dir == str(allowed / ".." / "vods")


# ------------------------------------------------------------------------------------------------ links, redirects
def test_youtube_hosts_exactly():
    from nexus.web.lineups import clip_info
    assert clip_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ")["thumb"]
    assert clip_info("https://m.youtube.com/shorts/dQw4w9WgXcQ")["thumb"]
    assert clip_info("https://evilyoutube.com/watch?v=dQw4w9WgXcQ")["thumb"] is None
    assert clip_info("https://youtube.com.evil.io/watch?v=dQw4w9WgXcQ")["thumb"] is None


def test_safe_next():
    from nexus.web.urls import safe_next
    for good in ("/teams/1/plans", "/a?b=c", "/"):
        assert safe_next(good, "/x") == good
    for bad in ("https://evil.io/", "//evil.io", "/\\evil.io", "\\\\evil.io", "javascript:alert(1)", "/\t/evil.io", "", None):
        assert safe_next(bad, "/x") == "/x", bad


def test_next_and_same_page(app):  # noqa: F811
    c = setup_admin(app)
    store = app.extensions["nexus"]["store"]
    tid = store.create_team(1, "Squad")
    r = c.post(f"/teams/{tid}/discord/prep", data={"next": "https://evil.io/"})
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/teams/{tid}/plans")
    r = c.post(f"/teams/{tid}/discord/prep", data={"next": f"/teams/{tid}"})
    assert r.headers["Location"].endswith(f"/teams/{tid}")


# ------------------------------------------------------------------------------------------------ error messages
def test_errors_without_internals(app, monkeypatch):  # noqa: F811
    c = setup_admin(app)
    j = c.post("/api/profiles/order", json={"order": ["x"]})
    assert j.status_code == 400 and "invalid literal" not in j.get_json()["error"]
    from nexus.web import report_tools as rt
    assert rt.clip_message(rt.ClipFailed()) == "ffmpeg couldn't cut the clip (details in the server log)"
    assert "apt install ffmpeg" in rt.clip_message(rt.NoFfmpeg()) and "too long" in rt.clip_message(rt.ClipTimeout())
    store = app.extensions["nexus"]["store"]
    store.set("ollama_url", "http://127.0.0.1:9")                # nothing listens there
    j = c.post("/settings/test/ollama").get_json()
    assert j == {"ok": False, "msg": "Ollama isn't reachable at that URL."}

    def boom(*a, **k):
        raise RuntimeError("/srv/secret/path exploded")
    monkeypatch.setattr("nexus.coach.ollama.Ollama.check", boom)
    j = c.post("/settings/test/ollama").get_json()
    assert j["ok"] is False and "secret" not in j["msg"] and "server log" in j["msg"]


# ------------------------------------------------------------------------------------------------ the scripts
def test_scripts_escape_and_check_urls():
    ev, dr, st = ((STATIC / f).read_text() for f in ("evening.js", "drafts.js", "strat.js"))
    for js in (ev, dr, st):
        assert "const local = u =>" in js and "x.origin === location.origin" in js
    assert "s.src = REPLAY_JS" in ev and "new URL('../replay.js', document.currentScript.src)" in ev and "B.replay_js" not in ev and "${esc(icon(a))}" in ev and "${esc(p.k)}" in ev
    assert "${icon(" not in dr and "${esc(st.n_all)}" in dr
    assert "e.textContent = text" in st and "const hHtml = " in st and "/^on/i.test(k)" in st
    assert "e.innerHTML = html" not in st
    for f in STATIC.glob("*.js"):
        js = f.read_text()
        if "const esc = s =>" in js:
            assert "'\"': '&quot;', \"'\": '&#39;'" in js, f.name           # every copy escapes quotes too


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 52)
    assert "## 4.52.1" in (ROOT / "CHANGELOG.md").read_text()
    assert json.loads((ROOT / "nexus/i18n/de.json").read_text())
