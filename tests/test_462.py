"""4.62: comp styles: balanced (as before), aggressive, defensive, utility execute."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_compmodes import _rows  # noqa: E402
from test_web import _premier_team, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.stats import compmodes, compstyle, roles  # noqa: E402
from nexus.stats.comp import Pool, rate  # noqa: E402

ROOT = Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def _roles():
    roles.load(None)


def _pools():
    """flex plays Skye a bit more than Neon and Cypher, all three the same."""
    won = [("Skye", "Ascent", 1, 210, 6), ("Skye", "Ascent", 0, 200, 4), ("Neon", "Ascent", 1, 210, 5),
           ("Neon", "Ascent", 0, 200, 4), ("Cypher", "Ascent", 1, 210, 5), ("Cypher", "Ascent", 0, 200, 4)]
    return [
        Pool.from_rows("ctrl", _rows([("Omen", "Ascent", 1, 200, 8), ("Omen", "Ascent", 0, 200, 6),
                                      ("Brimstone", "Ascent", 1, 200, 5), ("Brimstone", "Ascent", 0, 200, 4)])),
        Pool.from_rows("duel", _rows([("Jett", "Ascent", 1, 250, 12), ("Raze", "Ascent", 1, 230, 3)])),
        Pool.from_rows("init", _rows([("Sova", "Ascent", 1, 210, 12), ("KAY/O", "Ascent", 1, 200, 4)])),
        Pool.from_rows("sent", _rows([("Killjoy", "Ascent", 1, 200, 12), ("Cypher", "Ascent", 1, 190, 3)])),
        Pool.from_rows("flex", _rows(won)),
    ]


def picks(c):
    return {p["player"]: p["agent"] for p in c["picks"]}


def test_styles_change_the_comp():
    base = compmodes.top("stats", _pools(), "Ascent")[0]
    assert picks(base)["flex"] == "Skye"
    assert compmodes.top("stats", _pools(), "Ascent", style=None)[0]["total"] == base["total"]     # balanced: as before
    agg = compmodes.top("stats", _pools(), "Ascent", style="aggressive")[0]
    assert picks(agg)["flex"] == "Neon" and picks(agg)["duel"] == "Jett"
    flex = next(p for p in agg["picks"] if p["player"] == "flex")
    assert "fits an aggressive style" in flex["why"]
    dfn = compmodes.top("stats", _pools(), "Ascent", style="defensive")[0]
    assert picks(dfn)["flex"] == "Cypher" and picks(dfn)["sent"] == "Killjoy"
    exe = compmodes.top("stats", _pools(), "Ascent", style="execute")[0]
    assert picks(exe)["ctrl"] == "Brimstone"
    # the whole plan follows it too (comps at a glance, fill-ins)
    plan = compmodes.plan("stats", _pools(), [], ["Ascent"], {}, {}, style="aggressive")
    assert picks(plan[0]["main"])["flex"] == "Neon"


def test_role_mix_from_the_meta_comes_first():
    meta = {"roles": {"Duelist": 1, "Initiator": 2, "Controller": 1, "Sentinel": 1}}
    agg = compmodes.top("stats", _pools(), "Ascent", meta=meta, style="aggressive")[0]
    assert picks(agg)["flex"] == "Skye"                                   # a second duelist would break the mix


def test_comfort_ignores_styles_and_bonus_numbers():
    a = compmodes.top("comfort", _pools(), "Ascent")[0]
    assert picks(a) == picks(compmodes.top("comfort", _pools(), "Ascent", style="defensive")[0])
    assert compstyle.agent_bonus("Jett", "aggressive") == (20.0, "fits an aggressive style")
    assert compstyle.agent_bonus("Omen", "aggressive") == (8.0, "")
    assert compstyle.agent_bonus("Jett", "balanced") == (0.0, "") and compstyle.agent_bonus("Jett", "nope") == (0.0, "")
    p = _pools()[4]
    assert rate(p, "Neon", "Ascent", style="aggressive")["score"] - rate(p, "Neon", "Ascent")["score"] == 20.0
    for st in ("aggressive", "defensive", "execute"):
        assert set(compstyle.FIT[st]) <= set(roles.all_agents()) | {"Waylay", "Tejo", "Veto"}, st


def test_comps_page_style(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    tid = _premier_team(app, c, monkeypatch)
    page = c.get(f"/teams/{tid}").data.decode()
    assert 'aria-label="Comp style"' in page and ">Aggressive</a>" in page and 'class="on" href' in page
    agg = c.get(f"/teams/{tid}?style=aggressive").data.decode()
    assert re.search(r'class="on" href="[^"]*style=aggressive', agg) and "<span>Aggressive</span>" in agg
    assert 'name="style" value="aggressive"' in agg or "Other options" not in agg
    again = c.get(f"/teams/{tid}").data.decode()                                     # kept for the team
    assert re.search(r'class="on" href="[^"]*style=aggressive', again)
    back = c.get(f"/teams/{tid}?style=nonsense").data.decode()                        # unknown: balanced, not saved
    assert re.search(r'class="on" href="[^"]*style=balanced', back)
    assert re.search(r'class="on" href="[^"]*style=aggressive', c.get(f"/teams/{tid}").data.decode())


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in list(compstyle.STYLES.values()) + list(compstyle.ABOUT.values()) + list(compstyle.WHY.values()) + ["Style"]:
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 62, 0)
    assert "## 4.62.0" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
