"""4.63: the comp sheet's ideal compositions: a drag & drop editor that saves as you go."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, make_user, setup_admin, synthetic  # noqa: E402,F401

ROOT = Path(__file__).parent.parent
TPL = (ROOT / "nexus/web/templates/team_sheet.html").read_text()
COMP = ["Jett", "Sova", "KAY/O", "Omen", "Killjoy"]


def _team(app, c):  # noqa: F811 (fixture)
    store = app.extensions["nexus"]["store"]
    pid = add_profile(c)
    tid = store.create_team(store.user_by_name("manuel").id, "Squad")
    store.update_team(tid, members=[{"pid": pid, "kind": "starter"}], maps=["Ascent", "Bind"])
    c.post(f"/teams/{tid}/sheet/pool/{pid}", data={"order": "Jett,Omen", "no": ""})       # his pool: Jett, Omen
    return store, tid


def test_editor_on_the_page(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    store, tid = _team(app, c)
    page = c.get(f"/teams/{tid}/sheet").data.decode()
    assert 'id="ie"' in page and page.count('class="ie-slot"') == 5 and 'data-ie="Ascent"' in page
    assert 'class="ie-t" tabindex="0" data-agent="Viper" data-role="Controller"' in page
    assert re.search(r'data-agent="Jett" data-role="Duelist" data-tip="adv1ce"', page)      # who has it in his pool
    assert re.search(r'data-agent="Viper"[^>]*>.*?<small class="none">nobody</small>', page, re.S)
    assert '<select name="agent"' not in page                                              # the old dropdowns are gone
    c.post(f"/teams/{tid}/sheet/ideal", data={"map": "Ascent", "agent": COMP})
    page = c.get(f"/teams/{tid}/sheet").data.decode()
    assert f'data-ie="Ascent" data-agents="{",".join(COMP)}">Edit</button>' in page
    mate = make_user(app, c, "mate")
    store.add_team_access(tid, store.user_by_name("mate").id)
    assert 'id="ie"' not in mate.get(f"/teams/{tid}/sheet").data.decode()                  # the owner sets them


def test_quiet_save(app):  # noqa: F811 (fixture)
    from nexus.stats import compsheet
    c = setup_admin(app)
    store, tid = _team(app, c)
    hdr = {"X-Nexus-Save": "1"}
    r = c.post(f"/teams/{tid}/sheet/ideal", data={"map": "Bind", "agent": COMP}, headers=hdr)
    assert r.status_code == 200 and r.get_json() == {"ok": True, "map": "Bind", "agents": COMP}
    assert compsheet.load(app.extensions["nexus"]["stats"].team_dir(tid))["ideal"]["bind"] == COMP
    r = c.post(f"/teams/{tid}/sheet/ideal", data={"map": "Bind", "agent": ["Jett", "Jett", "Sova"]}, headers=hdr)
    assert r.status_code == 400 and r.get_json()["ok"] is False
    assert compsheet.load(app.extensions["nexus"]["stats"].team_dir(tid))["ideal"]["bind"] == COMP
    assert "ideal composition saved" not in c.get(f"/teams/{tid}/sheet").data.decode()          # no flash
    assert c.post(f"/teams/{tid}/sheet/ideal", data={"map": "Haven", "agent": COMP}, headers=hdr).status_code == 400


def test_script_and_german():
    for s in ("pointerdown", "X-Nexus-Save", "ie-filter", "ArrowLeft", "Delete", "location.reload()", "touch-action:none"):
        assert s in TPL, s
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Ideal composition for", "# / 5: saves once all 5 are set", "# players", "Edit"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())


def test_version():
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 63, 0)
    assert "## 4.63.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
