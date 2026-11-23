"""4.60: the comp sheet's agent pool: a drag & drop editor for your own pool (every agent shown), saving as you go;
each player edits only his own pool, the team owner only those of players nobody is linked to; the team's pools
behind a switch."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

ROOT = Path(__file__).parent.parent
TPL = (ROOT / "nexus/web/templates/team_sheet.html").read_text()


def _team(app, c):  # noqa: F811 (fixture)
    store = app.extensions["nexus"]["store"]
    a, b = add_profile(c), add_profile(c, "other", "#EUW")
    owner = store.user_by_name("manuel").id
    tid = store.create_team(owner, "Squad")
    store.update_team(tid, members=[{"pid": a, "kind": "starter"}, {"pid": b, "kind": "starter"}])
    mate = make_user(app, c, "mate")
    uid = store.user_by_name("mate").id
    store.add_team_access(tid, uid)
    c.post(f"/teams/{tid}/access", data={"link": str(uid), "pid": str(a)})
    return store, tid, a, b, mate


def test_who_edits_what(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store, tid, a, b, mate = _team(app, c)
    assert store.team(tid).member_list[0]["user_id"] == store.user_by_name("mate").id
    # the linked player: his own pool, big, every agent; he can't touch the other one
    page = mate.get(f"/teams/{tid}/sheet").data.decode()
    assert "Your agent pool" in page and 'class="pe"' in page and f'/sheet/pool/{a}"' in page
    assert 'data-zone="pool"' in page and 'data-zone="can"' in page and 'data-zone="no"' in page
    assert 'data-agent="Viper"' in page and 'data-agent="Clove"' in page                   # all agents, no adding
    assert 'id="show-team"' in page and "Edit for them" not in page
    assert mate.post(f"/teams/{tid}/sheet/pool/{b}", data={"order": "Jett", "no": ""}).status_code == 403
    assert mate.get(f"/teams/{tid}/sheet?edit={b}").data.decode().count('class="pe"') == 1      # still only his own
    # the owner: not the linked player's pool any more, but the unlinked one's
    assert c.post(f"/teams/{tid}/sheet/pool/{a}", data={"order": "Jett", "no": ""}).status_code == 403
    own = c.get(f"/teams/{tid}/sheet").data.decode()
    assert 'class="pe"' not in own and "Edit for them" in own and f"edit={b}" in own and "Not linked" in own
    assert 'id="show-team" checked' in own                                                   # nothing of his own: shown
    ed = c.get(f"/teams/{tid}/sheet?edit={b}").data.decode()
    assert "Agent pool of" in ed and f'/sheet/pool/{b}"' in ed and ">Done</a>" in ed
    assert 'class="pe"' not in c.get(f"/teams/{tid}/sheet?edit={a}").data.decode()          # linked: not his


def test_saves_as_you_go(app):  # noqa: F811 (fixture)
    from nexus.stats import compsheet
    c = setup_admin(app)
    store, tid, a, b, mate = _team(app, c)
    r = mate.post(f"/teams/{tid}/sheet/pool/{a}", data={"order": "Omen,Jett,Nobody", "no": "Sova,Jett"},
                  headers={"X-Nexus-Save": "1"})
    assert r.status_code == 200 and r.is_json
    j = r.get_json()
    assert j["ok"] and j["order"][0] == "Omen" and "Jett" not in j["order"] and j["no"] == ["Sova", "Jett"]
    assert j["edited"]
    saved = compsheet.load(app.extensions["nexus"]["stats"].team_dir(tid))["pools"][str(a)]
    assert saved == {"order": ["Omen"], "no": ["Sova", "Jett"]}
    page = mate.get(f"/teams/{tid}/sheet").data.decode()
    assert "Agent pool saved." not in page                                                  # quiet: no flash
    assert page.index('data-zone="no"') < page.index('data-agent="Sova"')                  # in won't play
    assert "Back to the stats" in page
    r = mate.post(f"/teams/{tid}/sheet/pool/{a}", data={"order": "Omen", "no": ""})            # the plain form still works
    assert r.status_code == 302 and r.headers["Location"].endswith("#pool")


def test_page_parts():
    for s in ("pointerdown", "pointermove", "pointerup", "X-Nexus-Save", "nexus.sheet.team", "ArrowLeft", "Delete"):
        assert s in TPL, s
    assert "poolform" not in TPL and "addsel" not in TPL                                     # the old ▲▼✕ editor is gone
    assert "touch-action:none" in TPL
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your agent pool", "Can play", "Edit for them", "The team's pools (#)", "drag into the pool"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 60, 0)
    assert "## 4.60.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
