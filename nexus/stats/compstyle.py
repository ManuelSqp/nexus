"""4.62: comp styles: the comps page makes the comps for the way you want to play a map.

  balanced    as before: the best fit of your players' numbers, the map rules and the role mix
  aggressive  fast hits and early fights: entry duelists, flashes and stuns, a second duelist is fine
  defensive   holding sites and retakes: sentinels with set-ups, recon, a second sentinel is fine
  execute     set-piece site takes with a lot of utility: smokes, walls, flashes and damage, a second controller is fine

A style gives each agent up to STYLE_MAX points (comp.rate adds them to the player's own numbers, so a player is
still put on what he plays well) and a small bonus to a comp with its typical role mix. The role mix you set in the
team's map meta and the map rules still come first. "Most comfortable" doesn't use styles: it only counts games.
"""
from __future__ import annotations

DEFAULT = "balanced"
STYLES = {
    "balanced": "Balanced",
    "aggressive": "Aggressive",
    "defensive": "Defensive",
    "execute": "Utility execute",
}
ABOUT = {
    "balanced": "The best fit of your numbers, the map rules and the role mix",
    "aggressive": "Fast hits and early fights: entry, flashes, stuns",
    "defensive": "Holding sites and retakes: set-ups, recon, flank watch",
    "execute": "Set-piece site takes: smokes, walls, flashes, damage",
}
WHY = {
    "aggressive": "fits an aggressive style",
    "defensive": "fits a defensive style",
    "execute": "fits a utility execute",
}
STYLE_MAX = 20.0          # points for an agent that fits the style best (POOL_BONUS is 15, a 60 % win rate is +10)
MIX_BONUS = 10.0          # the style's role mix (a second duelist / sentinel / controller)
MIX = {"aggressive": "Duelist", "defensive": "Sentinel", "execute": "Controller"}

# how well each agent fits a style, 0-10 (an agent not listed: 0)
FIT = {
    "aggressive": {"Jett": 10, "Raze": 10, "Neon": 10, "Waylay": 9, "Phoenix": 8, "Breach": 8, "Skye": 8, "KAY/O": 8,
                   "Yoru": 7, "Reyna": 7, "Iso": 6, "Gekko": 6, "Clove": 6, "Fade": 5, "Tejo": 5, "Omen": 4,
                   "Chamber": 3, "Brimstone": 3},
    "defensive": {"Killjoy": 10, "Cypher": 10, "Vyse": 10, "Deadlock": 9, "Veto": 9, "Sage": 8, "Viper": 8,
                  "Chamber": 7, "Sova": 7, "Astra": 6, "Fade": 6, "Gekko": 5, "Harbor": 5, "Tejo": 4, "Omen": 3,
                  "Brimstone": 3, "Clove": 3},
    "execute": {"Brimstone": 10, "Breach": 9, "Tejo": 9, "Viper": 8, "KAY/O": 8, "Astra": 7, "Harbor": 7, "Skye": 7,
                "Gekko": 7, "Omen": 6, "Clove": 6, "Fade": 6, "Sova": 6, "Raze": 6, "Phoenix": 5, "Sage": 5,
                "Killjoy": 4, "Deadlock": 4, "Waylay": 4},
}


def clean(style: str | None) -> str:
    return style if style in STYLES else DEFAULT


def agent_bonus(agent: str, style: str | None) -> tuple[float, str]:
    """(points, reason) for an agent in a style; (0, '') for balanced or an agent that doesn't fit."""
    fit = FIT.get(clean(style), {}).get(agent, 0)
    if not fit:
        return 0.0, ""
    return STYLE_MAX * fit / 10, (WHY[clean(style)] if fit >= 7 else "")


def mix_bonus(agents: list[str], style: str | None, role_of) -> float:
    """A small bonus for the style's typical role mix (two of MIX's role)."""
    want = MIX.get(clean(style))
    return MIX_BONUS if want and sum(role_of(a) == want for a in agents) >= 2 else 0.0
