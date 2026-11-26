"""4.78: the opponent scouting report: how a scouted team plays its rounds, per map and buy (stats/roundplay.py),
on its Premier scouting page and in the "how to play them" lines."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent))
from test_466 import _scouted  # noqa: E402
from test_web import _premier_team, app, setup_admin, synthetic  # noqa: E402,F401

from nexus.models import PlayerLoc  # noqa: E402
from nexus.stats import roundplay as rp  # noqa: E402
from nexus.stats import scouting  # noqa: E402

ROOT = Path(__file__).parent.parent


class MI:
    """A map: x < -10 is A, x > 10 is B, else Mid; y > 50 is their spawn side."""
    def zone(self, x, y):
        return "Attacker Side" if y > 50 else "A" if x < -10 else "B" if x > 10 else "Mid"

    def area(self, x, y):
        return {"A": "A Main", "B": "B Long", "Mid": "Mid Top", "Attacker Side": "T Spawn"}[self.zone(x, y)]


def kill(t, victim_team, vx, them_at, us_at=()):
    locs = [PlayerLoc(f"t{i}", "Red", x, y) for i, (x, y) in enumerate(them_at)] + \
           [PlayerLoc(f"u{i}", "Blue", x, y) for i, (x, y) in enumerate(us_at)]
    return NS(t_round_ms=t * 1000, victim_team=victim_team, victim="v", victim_x=vx, victim_y=0, player_locations=locs,
              loc_of=lambda pu: next((p for p in locs if p.puuid == pu), None))


def rnd(n, attack, won, load, plant=None, k0=None):
    st = {f"t{i}": NS(team="Red", loadout_value=load) for i in range(5)}
    return NS(number=n, attacking_team="Red" if attack else "Blue", winning_team="Red" if won else "Blue", stats=st,
              plant=NS(site=plant[0], t_round_ms=plant[1] * 1000) if plant else None, kills=[k0] if k0 else [],
              side_of=lambda team, a=attack: "attack" if (team == "Red") == a else "defense")


STACK_B = [(20, 0)] * 4 + [(0, 0)]
SPREAD = [(-20, 0), (-20, 0), (0, 0), (20, 0), (20, 0)]
DEF_SETUP = [(-20, 0), (-20, 0), (0, 0), (20, 0), (20, 0)]


def test_analyse(monkeypatch):
    monkeypatch.setattr(rp, "_map_info", lambda reg, m, cache: MI())
    rounds = [rnd(1, True, True, 800, ("B", 30), kill(12, "Blue", 20, STACK_B))]          # pistol
    rounds += [rnd(n, True, n % 2 == 0, 4500, ("B", 28 if n < 6 else 40), kill(15, "Blue", 20, STACK_B)) for n in range(2, 8)]
    rounds += [rnd(8, True, False, 4500, ("A", 80), kill(40, "Red", -20, SPREAD))]
    rounds += [rnd(n, False, True, 4500, None, kill(30, "Blue", -20, DEF_SETUP)) for n in range(13, 18)]
    rounds += [rnd(n, False, False, 900, None, kill(12, "Blue", 0, [(0, 0)] * 5)) for n in range(18, 22)]    # eco: early, Mid
    m = NS(map_name="Ascent", map_id="x", rounds=rounds)
    out = rp.analyse([(m, "Red")], Path("."))
    a = out["Ascent"]["attack"]["full"]
    assert a["rounds"] == 7 and a["sites"][0] == {"site": "B", "n": 6, "share": 0.86} and a["no_plant"] == 0
    assert a["fast"] == 4 and a["stack"] == 6 and a["stack_zone"] == "B" and a["spread"] == 1 and a["seen"] == 7
    assert a["first_area"] == "B Long" and a["plant_s"] == 28 and a["first_s"] == 15
    assert out["Ascent"]["attack"]["pistol"]["rounds"] == 1
    d = out["Ascent"]["defense"]
    assert d["full"]["setup"] == {"A": 2.0, "B": 2.0, "Mid": 1.0} and d["full"]["early"] == 0
    assert d["eco"]["early"] == 4 and d["eco"]["early_area"] == "Mid Top" and d["eco"]["won"] == 0
    assert rp.setup_text(d["full"]["setup"]) == "2 A · 2 B · 1 Mid"
    ls = out["Ascent"]["lines"]
    assert ls[0] == "Ascent attack, full buys: B 86 % of their plants, fast hits (4 of 7 planted in 35 s), stacked on B at the first fight."
    assert "Ascent defense, full buys: they stand 2 A · 2 B · 1 Mid." in ls
    assert "Ascent defense, ecos: they look for early picks (4 of 4 rounds, mostly Mid Top)." in ls
    assert not any("pistols" in x for x in ls)                                    # one pistol round: too few
    # into the "how to play them" lines
    s = _scouted()
    s["play"] = out
    assert ls[0] in scouting.map_lines(s, "Ascent")


def test_page(app, monkeypatch):  # noqa: F811 (fixture)
    c = setup_admin(app)
    tid = _premier_team(app, c, monkeypatch)
    sd = app.extensions["nexus"]["stats"].team_dir(tid) / "scout"
    sd.mkdir(parents=True, exist_ok=True)
    s = _scouted()
    s.update({"wins": 3, "losses": 3, "pistols": {"played": 0, "won": 0}, "comps": [], "economy": {}, "name": "Rivals", "tag": "RV"})
    s["maps"]["Ascent"].update({"rounds": 80, "rounds_won": 40})
    s["maps"]["Ascent"]["attack"]["sites_hit"] = {"A": {"plants": 7, "rounds_won": 4}, "B": {"plants": 3, "rounds_won": 1}}
    (sd / "t1.json").write_text(json.dumps(s))
    page = c.get(f"/teams/{tid}/premier/team/t1").data.decode()
    assert "to see how they play their rounds" in page and 'class="rplay"' not in page        # scouted before 4.78
    s["play"] = {"Ascent": {"attack": {"full": {"rounds": 7, "won": 3, "sites": [{"site": "B", "n": 6, "share": 0.86}],
                                                "site_won": {"B": 3}, "no_plant": 1, "plant_s": 40, "first_s": 15,
                                                "first_area": "B Long", "fast": 4, "seen": 7, "spread": 1, "stack": 6,
                                                "stack_zone": "B"}},
                            "defense": {"full": {"rounds": 5, "won": 5, "seen": 5, "setup": {"A": 2.0, "B": 2.0, "Mid": 1.0},
                                                 "early": 0, "early_area": ""}},
                            "lines": ["Ascent attack, full buys: B 86 % of their plants."]}}
    (sd / "t1.json").write_text(json.dumps(s))
    page = c.get(f"/teams/{tid}/premier/team/t1").data.decode()
    assert 'class="rplay"' in page and "B 86%" in page and "stack 6/7 (B)" in page and "2 A · 2 B · 1 Mid" in page
    assert "~40 s / ~15 s" in page and "Ascent attack, full buys: B 86 % of their plants." in page


def test_german_and_version():
    de = json.loads((ROOT / "nexus/i18n/de.json").read_text())
    for k in ("How they play their rounds", "per buy, from the first fight of each round", "Plants", "Plant / first fight",
              "At the first fight", "They stand", "Early picks", "Full buy"):
        assert k in de, k
    assert not any("ß" in v for v in de.values())
    import nexus
    assert tuple(map(int, nexus.__version__.split("."))) >= (4, 78)
    assert "## 4.78" in (ROOT / "CHANGELOG.md").read_text()
    assert f"**Version {nexus.__version__}**" in (ROOT / "README.md").read_text()
