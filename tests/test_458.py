"""4.58: your own abilities in Aim on maps (the agent you pick: C, Q, E quick-cast where you aim)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from test_444 import _replay  # noqa: E402
from test_448 import _game_app  # noqa: E402
from test_454 import _with_retakes  # noqa: E402
from test_general_drills import _spots  # noqa: E402
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import drills as dr  # noqa: E402
from nexus.stats import kits  # noqa: E402

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "nexus" / "web" / "static"
KINDS = {"smoke", "flash", "flash_wall", "damage", "stun", "recon", "trap", "wall", "dash", "teleport", "anchor", "speed"}


def test_kits():
    assert len(kits.KITS) >= 27
    for agent, k in kits.KITS.items():
        assert set(k) <= {"C", "Q", "E"} and k, agent                     # no ultimates
        for slot, a in k.items():
            assert a["kind"] in KINDS and a["charges"] >= 1 and a["name"], (agent, slot)
            need = {"smoke": ("dur", "range"), "flash": ("dur", "delay", "range"), "flash_wall": ("dur", "range"),
                    "damage": ("dps", "dur", "range"), "stun": ("r", "dur", "range"), "recon": ("dur", "range"),
                    "trap": ("dur", "range"), "wall": ("dur", "range"), "dash": ("dist",), "teleport": ("range",),
                    "anchor": ("range",), "speed": ("mult", "dur")}[a["kind"]]
            assert all(x in a for x in need), (agent, slot)
    assert kits.KITS["Jett"]["E"]["kind"] == "dash" and kits.KITS["Omen"]["E"]["kind"] == "smoke"
    assert kits.KITS["Breach"]["Q"]["kind"] == "flash_wall" and kits.KITS["Brimstone"]["E"]["charges"] == 3
    assert list(kits.kit("KAY/O")) == ["C", "Q", "E"] and kits.kit("Nobody") is None
    k = kits.kit("Sova")
    k["Q"]["charges"] = 9
    assert kits.KITS["Sova"]["Q"]["charges"] == 2                         # a copy


def test_keys():
    k = dr.default_keys()
    assert k["ab_c"] == ["KeyZ", ""] and k["ab_q"] == ["KeyQ", ""] and k["ab_e"] == ["KeyE", ""]
    assert k["crouch"] == ["KeyC", ""] and not dr.clashes(k)


def test_play_with_an_agent(app, synthetic):  # noqa: F811
    _replay(app, synthetic)
    _game_app(app, synthetic)
    c = setup_admin(app)
    pid = add_profile(c)
    _with_retakes(app, c, pid)
    d = _spots(c, pid)
    rt = next(r for r in d["retakes"] if r["site"] == "Z")
    page = c.get(f"/profiles/{pid}/aim/maps").data.decode()
    assert '"Jett": {"C": "Cloudburst", "E": "Tailwind"}' in page

    def boot(url):
        r = c.get(url)
        assert r.status_code == 200, url
        return json.loads(r.data.decode().split("window.NEXUS_MAP3D = ", 1)[1].split(";</script>", 1)[0])
    b = boot(f"/profiles/{pid}/aim/play/retake/testmap/{rt['id']}?agent=KAY/O")
    assert b["opts"]["agent"] == "KAY/O" and b["opts"]["kit"]["Q"] == kits.KITS["KAY/O"]["Q"]
    assert ["ab_c", "Ability C"] in b["actions"]
    assert boot(f"/profiles/{pid}/aim/play/retake/testmap/{rt['id']}?agent=Nobody")["opts"]["kit"] is None
    assert boot(f"/profiles/{pid}/aim/play/track/testmap/{d['angles'][0]['id']}?agent=Jett")["opts"]["agent"] == ""


def test_scripts():
    dj = (STATIC / "drill.js").read_text()
    for x in ("const KIT = O.kit || null", "SLOT_OF = {ab_c: 'C', ab_q: 'Q', ab_e: 'E'}", "else if (SLOT_OF[a]) cast(SLOT_OF[a]);",
              "function cast(slot)", "function aimPoint(range, through = false)", "function myTick()", "function kitHtml()",
              "if (S.t < (f.blind || 0) || S.t < (f.daze || 0)) return false;", "case 'dash':", "case 'teleport':",
              "case 'anchor':", "f.blind = S.t + u.blind", "else if (u.mine) continue;", "resetKit();",
              "* (S.t < S.fast ? S.fastMult : 1)", "if ((UTIL || KIT) && S.phase === 'run')"):
        assert x in dj, x
    aj = (STATIC / "aim_maps.js").read_text()
    for x in ("function agentPick()", 'id="am-g-agent"', "if (ENEMY[tab] && g.agent) o.set('agent', g.agent);"):
        assert x in aj, x
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("Your agent", "none (no abilities)", "Ability C", "none left"):
        assert k in de and "ß" not in de[k], k


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:2]) >= (4, 58)
    assert "## 4.58.0" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
