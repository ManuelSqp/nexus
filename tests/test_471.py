"""4.71: VALORANT's own sens, crosshair and keys for the aim trainer and the drills, read by the Nexus app on the
player's PC (desktop/nexus_desktop/valsettings.py) and taken over by the server (nexus/stats/gamesettings.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from test_web import ADMIN_PW, add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import gamesettings as gs  # noqa: E402
from nexus.stats import trainer as tr  # noqa: E402
from nexus_desktop import sync, valsettings  # noqa: E402
from nexus_desktop.config import Settings  # noqa: E402

ROOT = Path(__file__).parent.parent

PROFILES = {"currentProfile": 1, "profiles": [
    {"profileName": "Old", "primary": {"color": {"r": 0, "g": 255, "b": 0, "a": 255}}},
    {"profileName": "Main", "primary": {
        "color": {"r": 255, "g": 255, "b": 255, "a": 255}, "bUseCustomColor": True,
        "colorCustom": {"r": 255, "g": 0, "b": 128, "a": 255}, "bHasOutline": False, "outlineThickness": 1,
        "outlineOpacity": 0.5, "bDisplayCenterDot": True, "centerDotSize": 3, "centerDotOpacity": 1,
        "innerLines": {"lineThickness": 1, "lineLength": 4, "lineLengthVertical": 4, "bAllowVertScaling": False,
                       "lineOffset": 2, "opacity": 1, "bShowLines": True},
        "outerLines": {"bShowLines": False}}}]}


def game(**kw):
    d = {"source": "client", "floats": {"MouseSensitivity": 0.35, "MouseSensitivityZoomed": 1.0},
         "strings": {"SavedCrosshairProfileData": json.dumps(PROFILES)},
         "actions": [{"name": "Crouch", "key": "C", "bindIndex": 0, "characterName": "None"},
                     {"name": "Activate_GrenadeAbility", "key": "F", "bindIndex": 0, "characterName": "None"},
                     {"name": "Activate_Ability1", "key": "ThumbMouseButton", "bindIndex": 1, "characterName": "None"},
                     {"name": "Reload", "key": "R", "bindIndex": 0, "ctrl": True, "characterName": "None"},
                     {"name": "Activate_Ability2", "key": "G", "bindIndex": 0, "characterName": "Jett"},
                     {"name": "OpenMegamap", "key": "M", "bindIndex": 0}],
         "axes": [{"name": "MoveForward", "key": "Up", "scale": 1.0}]}
    d.update(kw)
    return d


def test_keys_from_the_game():
    assert [gs.ue_code(k) for k in ("A", "One", "SpaceBar", "LeftControl", "ThumbMouseButton2", "MouseScrollDown",
                                     "NumPadFive", "F5", "Tilde", "None", "Escape", "Gamepad_FaceButton_Bottom")] == \
        ["KeyA", "Digit1", "Space", "ControlLeft", "Mouse4", "WheelDown", "Numpad5", "F5", "Backquote", None, None, None]
    keys, skipped = gs.game_keys(game())
    assert keys["crouch"] == ["KeyC", ""] and keys["ab_c"] == ["KeyF", ""] and keys["ab_q"] == ["KeyQ", "Mouse3"]
    assert keys["forward"] == ["ArrowUp", ""] and keys["shoot"] == ["Mouse0", ""] and keys["walk"] == ["ShiftLeft", ""]
    assert keys["reload"] == ["KeyR", ""] and keys["ab_e"] == ["KeyE", ""]          # Ctrl+R and Jett's own: kept default
    assert any("modifier" in s for s in skipped) and any("one agent" in s for s in skipped)
    assert set(keys) == set(gs.ACTION_NAMES) <= set(dr.ACTIONS)
    # unbound in the game: the drill still needs one
    k2, _ = gs.game_keys(game(actions=[{"name": "Walk", "key": "None", "bindIndex": 0}]))
    assert k2["walk"] == [dr.ACTIONS["walk"][1], ""]
    # the trainer's own actions move off a key the game uses (F is an ability now, so full screen goes to H)
    mine = dr.default_keys()
    merged = gs.merge_keys(mine, keys)
    assert merged["ab_c"] == ["KeyF", ""] and merged["full"] == ["KeyH", ""] and merged["next"] == ["Space", ""]
    assert not dr.clashes(merged)


def test_crosshair_and_sens():
    g = gs.read(gs.clean(game()))
    assert g["sens"] == 0.35 and g["crosshair_name"] == "Main" and g["profiles"] == 2 and g["custom_keys"] == 4
    x = g["crosshair"]
    assert x["color"] == "#ff0080" and x["outline"] is False and x["dot"] is True and x["dt"] == 3
    assert x["il"] == 4 and x["io"] == 2 and x["ia"] == 1 and x["outer"] is False
    assert set(x) == {"color", *tr.CROSSHAIR_NUM, *tr.CROSSHAIR_BOOL}
    # keys in any case (the files and the client don't always agree)
    lower = json.loads(json.dumps(PROFILES).replace("innerLines", "InnerLines").replace("lineLength", "LineLength"))
    assert gs.read(gs.clean(game(strings={"SavedCrosshairProfileData": json.dumps(lower)})))["crosshair"]["il"] == 4
    # the client has everything: no sens means VALORANT's default; the files don't say
    assert gs.read(gs.clean(game(floats={})))["sens"] == gs.VALORANT_DEFAULT_SENS
    assert gs.read(gs.clean(game(floats={}, source="files")))["sens"] is None
    assert gs.read(gs.clean(game(strings={"SavedCrosshairProfileData": "{broken"})))["crosshair"] is None
    assert gs.clean({"floats": {}, "strings": {}}) is None and gs.clean("x") is None
    # what's different from the trainer, in words
    assert gs.changes(g, {"sens": 0.4}, dr.default_keys())[:2] == ["sens 0.4 → 0.35", "crosshair Main"]
    assert gs.digest(g) == gs.digest(dict(g, skipped=["x"])) != gs.digest(dict(g, sens=0.36))


def test_the_app_reads_valorant(tmp_path, monkeypatch):
    base = tmp_path / "Local"
    assert valsettings.lockfile(base) is None and valsettings.from_client(base) is None and valsettings.read(base) is None
    # VALORANT's files: the account used last, Unreal's quoted string, the keybinds file
    cfg = base / "VALORANT" / "Saved" / "Config"
    for acc in ("aaaa-eu", "bbbb-eu"):
        (cfg / acc / "Windows").mkdir(parents=True)
        (cfg / acc / "WindowsClient").mkdir(parents=True)
    quoted = '"' + json.dumps(PROFILES).replace('"', '\\"') + '"'
    (cfg / "aaaa-eu" / "Windows" / "RiotUserSettings.ini").write_text(
        "[Settings]\nEAresFloatSettingName::MouseSensitivity=0.350000\nEAresFloatSettingName::OverallVolume=0.2\n"
        f"EAresStringSettingName::SavedCrosshairProfileData={quoted}\nEAresStringSettingName::LastSeenSeasonalPopup=X\n")
    (cfg / "aaaa-eu" / "WindowsClient" / "BackupKeybinds.json").write_text(json.dumps({"actionMappings": game()["actions"]}))
    (cfg / "bbbb-eu" / "Windows" / "RiotUserSettings.ini").write_text("EAresFloatSettingName::MouseSensitivity=0.9\n")
    (cfg / "WindowsClient").mkdir()
    (cfg / "WindowsClient" / "RiotLocalMachine.ini").write_text("[UserInfo]\nLastKnownUser=aaaa\n")
    d = valsettings.read(base)
    assert d["source"] == "files" and d["floats"] == {"MouseSensitivity": 0.35}            # nothing else of the account
    assert set(d["strings"]) == {"SavedCrosshairProfileData"} and json.loads(d["strings"]["SavedCrosshairProfileData"]) == PROFILES
    assert len(d["actions"]) == 6 and gs.read(gs.clean(d))["crosshair_name"] == "Main"
    # the Riot Client first, while it runs
    lf = base / "Riot Games" / "Riot Client" / "Config"
    lf.mkdir(parents=True)
    (lf / "lockfile").write_text("Riot Client:1234:55555:s3cret:https")
    assert valsettings.lockfile(base) == {"port": 55555, "password": "s3cret", "protocol": "https"}
    seen = {}

    class Conn:
        def __init__(self, host, port, timeout, context):
            seen.update(host=host, port=port)

        def request(self, method, url, headers):
            seen.update(url=url, auth=headers["Authorization"])

        def getresponse(self):
            body = json.dumps({"data": {"floatSettings": [{"settingEnum": "EAresFloatSettingName::MouseSensitivity", "value": 0.5},
                                                          {"settingEnum": "EAresFloatSettingName::SoundEffectsVolume", "value": 1}],
                                        "stringSettings": [], "actionMappings": [], "axisMappings": []}}).encode()
            return type("R", (), {"status": 200, "read": lambda self, n: body})()

        def close(self):
            pass
    monkeypatch.setattr(valsettings.http.client, "HTTPSConnection", Conn)
    d = valsettings.read(base)
    assert d == {"source": "client", "floats": {"MouseSensitivity": 0.5}, "strings": {}, "actions": [], "axes": []}
    assert seen["host"] == "127.0.0.1" and seen["port"] == 55555 and seen["url"] == valsettings.ENDPOINT
    assert seen["auth"] == "Basic " + __import__("base64").b64encode(b"riot:s3cret").decode()
    assert valsettings.digest(d) == valsettings.digest(dict(d, source="files"))

    # one sync: sent once, again only when they change (or after a week)
    sent = []

    class Api:
        def send_game_settings(self, pid, s):
            sent.append((pid, s))
            return {"changed": ["sens 0.4 → 0.5"], "applied": True}
    s = Settings(player_id=7)
    lines = []
    sync.game_settings(s, Api(), lines.append, now=1000, base=base)
    sync.game_settings(s, Api(), lines.append, now=2000, base=base)
    assert len(sent) == 1 and sent[0][0] == 7 and lines == ["VALORANT settings: sens 0.4 → 0.5 (in the trainer now)"]
    sync.game_settings(s, Api(), lines.append, now=1000 + sync.GAME_SETTINGS_RESEND_S + 1, base=base)
    assert len(sent) == 2
    s.send_game_settings = False
    s.game_settings_sent = ""
    sync.game_settings(s, Api(), lines.append, now=10 ** 10, base=base)
    assert len(sent) == 2


def test_server_takes_them_over(app):  # noqa: F811 (fixture)
    c = setup_admin(app)
    pid = add_profile(c)
    anon = app.test_client()
    token = anon.post("/api/companion/login", json={"username": "manuel", "password": ADMIN_PW, "device": "PC"}).get_json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert "can come straight from VALORANT" in page
    assert anon.post(f"/api/companion/players/{pid}/game-settings", json={"floats": {}}, headers=H).status_code == 400
    assert anon.post(f"/api/companion/players/{pid + 99}/game-settings", json=game(), headers=H).status_code == 404
    r = anon.post(f"/api/companion/players/{pid}/game-settings", json=game(), headers=H).get_json()
    assert r["applied"] and r["changed"][0].startswith("sens ")
    store = app.extensions["nexus"]["store"]
    sr = app.extensions["nexus"]["stats"]
    tj = json.loads((sr.games(pid).path.parent / "trainer.json").read_text())
    assert tj["setup"]["sens"] == 0.35 and tj["setup"]["crosshair"]["color"] == "#ff0080" and tj["game"]["source"] == "client"
    keys = c.get("/api/aim/keys").get_json()["keys"]
    assert keys["ab_c"] == ["KeyF", ""] and keys["full"] == ["KeyH", ""] and keys["crouch"] == ["KeyC", ""]
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert "From VALORANT" in page and "Main" in page and "4 changed" in page and "Different here" not in page and "Keep in step with the game" in page
    assert 'value="0.35"' in page
    # changed in the trainer by hand: the same settings again don't overwrite it
    c.post(f"/profiles/{pid}/trainer/setup", json={"sens": 0.4})
    r = anon.post(f"/api/companion/players/{pid}/game-settings", json=game(), headers=H).get_json()
    assert r == {"changed": [], "applied": False}
    page = c.get(f"/profiles/{pid}/trainer").data.decode()
    assert "Different here: sens 0.4 → 0.35" in page
    # don't follow the game: a new sens is kept, not taken over; "Use the game's" takes it
    c.post(f"/profiles/{pid}/trainer/game", data={})
    r = anon.post(f"/api/companion/players/{pid}/game-settings", json=game(floats={"MouseSensitivity": 0.3}), headers=H).get_json()
    assert not r["applied"] and r["changed"][0] == "sens 0.4 → 0.3"
    assert json.loads((sr.games(pid).path.parent / "trainer.json").read_text())["setup"]["sens"] == 0.4
    c.post(f"/profiles/{pid}/trainer/game", data={"do": "take"})
    tj = json.loads((sr.games(pid).path.parent / "trainer.json").read_text())
    assert tj["setup"]["sens"] == 0.3 and tj["follow_game"] is False
    # following again takes the game's at once
    c.post(f"/profiles/{pid}/trainer/setup", json={"sens": 0.5})
    c.post(f"/profiles/{pid}/trainer/game", data={"on": "1"})
    assert json.loads((sr.games(pid).path.parent / "trainer.json").read_text())["setup"]["sens"] == 0.3
    assert store is not None
    # the app's page knows the switch
    html = c.get("/this-pc").data.decode()
    assert 'data-key="send_game_settings"' in html


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Keep in step with the game", "Use the game's", "From VALORANT", "VALORANT settings",
              "Send my VALORANT settings to the trainer"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    from nexus_desktop import __version__ as app_version
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 71) and app_version == nexus.__version__
    assert "## 4.71" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
