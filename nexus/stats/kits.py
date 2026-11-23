"""Your own abilities in Aim on maps (4.58): each agent's C, Q and E as one of a few kinds of ability, with the
agent's charges and close-to-the-game numbers. Ultimates aren't in the drills; abilities that don't change a fight
in a drill (heals, decoys, a slow on a path the enemy has to walk anyway) are left out (the drill says so).

Kinds (drill.js casts them where you aim, quick-cast):
  smoke      a smoke where you aim (range m), dur s: blocks sight both ways
  flash      pops where you aim after delay s (range m, not through walls): anyone who sees it is blind for dur s
             (you too, if you look at your own)
  flash_wall the same, through a wall (Breach's Flashpoint)
  damage     a molly where you aim: dps a second for dur s (yours burns you too)
  stun       a concuss / nearsight / tether where you aim (radius r): they can't fight you for dur s
  recon      a dart, a drone, Haunt: everyone it sees within 30 m is revealed for dur s (on the minimap, and they
             can't surprise you)
  trap       a tripwire / alarmbot / sensor where you aim (range m): the first one who walks by is revealed and
             can't fight you for dur s
  wall       a wall across where you aim (range m) for dur s: blocks sight (and you)
  dash       dist m the way you move (or look)
  teleport   to where you aim (range m) after delay s
  anchor     the first press leaves a marker, the second takes you back to it (range m)
  speed      faster by mult for dur s
"""
from __future__ import annotations

S, F, FW, D, ST, R, TR, W, DA, TP, AN, SP = ("smoke", "flash", "flash_wall", "damage", "stun", "recon", "trap",
                                             "wall", "dash", "teleport", "anchor", "speed")


def _a(name, kind, charges=1, **kw):
    return {"name": name, "kind": kind, "charges": charges, **kw}


KITS: dict[str, dict] = {
    "Astra": {"C": _a("Gravity Well", ST, 1, r=4.5, dur=2.5, range=40), "Q": _a("Nova Pulse", ST, 1, r=4.5, dur=3.0, range=40),
              "E": _a("Nebula", S, 2, dur=14, range=40)},
    "Breach": {"C": _a("Aftershock", D, 1, dps=80, dur=1.5, range=12), "Q": _a("Flashpoint", FW, 2, dur=2.0, delay=0.5, range=12),
               "E": _a("Fault Line", ST, 1, r=5, dur=3.5, range=25)},
    "Brimstone": {"Q": _a("Incendiary", D, 1, dps=60, dur=8, range=25), "E": _a("Sky Smoke", S, 3, dur=19, range=50)},
    "Chamber": {"C": _a("Trademark", TR, 1, dur=3.0, range=8), "E": _a("Rendezvous", AN, 1, range=40)},
    "Clove": {"E": _a("Ruse", S, 2, dur=14, range=40)},
    "Cypher": {"C": _a("Trapwire", TR, 2, dur=3.0, range=6), "Q": _a("Cyber Cage", S, 2, dur=7, range=15),
               "E": _a("Spycam", R, 1, dur=4, range=12)},
    "Deadlock": {"C": _a("GravNet", ST, 1, r=5, dur=3.0, range=20), "Q": _a("Sonic Sensor", TR, 1, dur=3.0, range=6),
                 "E": _a("Barrier Mesh", W, 1, dur=30, range=6)},
    "Fade": {"C": _a("Prowler", ST, 2, r=3.5, dur=2.5, range=20), "Q": _a("Seize", ST, 1, r=5, dur=3.0, range=25),
             "E": _a("Haunt", R, 1, dur=3, range=25)},
    "Gekko": {"C": _a("Mosh Pit", D, 1, dps=40, dur=4, range=20), "Q": _a("Wingman", ST, 1, r=4, dur=3.0, range=15),
              "E": _a("Dizzy", F, 1, dur=2.0, delay=0.8, range=20)},
    "Harbor": {"Q": _a("Cove", S, 1, dur=12, range=25), "E": _a("High Tide", W, 1, dur=15, range=15)},
    "Iso": {"C": _a("Contingency", W, 1, dur=8, range=4)},
    "Jett": {"C": _a("Cloudburst", S, 2, dur=4.5, range=15), "E": _a("Tailwind", DA, 1, dist=7)},
    "KAY/O": {"C": _a("FRAG/ment", D, 1, dps=60, dur=3, range=20), "Q": _a("FLASH/drive", F, 2, dur=2.0, delay=0.9, range=15),
              "E": _a("ZERO/point", R, 1, dur=4, range=20)},
    "Killjoy": {"C": _a("Nanoswarm", D, 2, dps=45, dur=4, range=15), "Q": _a("Alarmbot", TR, 1, dur=3.0, range=8),
                "E": _a("Turret", R, 1, dur=60, range=6)},
    "Neon": {"C": _a("Fast Lane", W, 1, dur=6, range=10), "Q": _a("Relay Bolt", ST, 1, r=4.5, dur=3.0, range=20),
             "E": _a("High Gear", SP, 1, mult=1.25, dur=6)},
    "Omen": {"C": _a("Shrouded Step", TP, 2, delay=0.8, range=13), "Q": _a("Paranoia", F, 1, dur=2.0, delay=0.3, range=18),
             "E": _a("Dark Cover", S, 2, dur=15, range=40)},
    "Phoenix": {"C": _a("Blaze", W, 1, dur=8, range=8), "Q": _a("Curveball", F, 2, dur=1.5, delay=0.4, range=10),
                "E": _a("Hot Hands", D, 1, dps=60, dur=4, range=15)},
    "Raze": {"Q": _a("Blast Pack", DA, 2, dist=6), "E": _a("Paint Shells", D, 1, dps=80, dur=1.5, range=20)},
    "Reyna": {"C": _a("Leer", F, 2, dur=2.0, delay=0.4, range=15)},
    "Sage": {"C": _a("Barrier Orb", W, 1, dur=30, range=8)},
    "Skye": {"Q": _a("Trailblazer", ST, 1, r=4, dur=3.0, range=20), "E": _a("Guiding Light", F, 2, dur=2.0, delay=0.7, range=20)},
    "Sova": {"C": _a("Owl Drone", R, 1, dur=4, range=20), "Q": _a("Shock Bolt", D, 2, dps=90, dur=1.0, range=30),
             "E": _a("Recon Bolt", R, 1, dur=3, range=40)},
    "Tejo": {"C": _a("Stealth Drone", R, 1, dur=4, range=20), "Q": _a("Special Delivery", ST, 1, r=4.5, dur=3.0, range=30),
             "E": _a("Guided Salvo", D, 1, dps=70, dur=2, range=40)},
    "Viper": {"C": _a("Snake Bite", D, 2, dps=24, dur=6, range=20), "Q": _a("Poison Cloud", S, 1, dur=15, range=20),
              "E": _a("Toxic Screen", W, 1, dur=15, range=30)},
    "Vyse": {"C": _a("Razorvine", D, 1, dps=30, dur=5, range=15), "Q": _a("Shear", W, 1, dur=6, range=10),
             "E": _a("Arc Rose", F, 2, dur=2.0, delay=0.6, range=12)},
    "Waylay": {"Q": _a("Lightspeed", DA, 1, dist=8), "E": _a("Refract", AN, 1, range=40)},
    "Yoru": {"Q": _a("Blindside", F, 2, dur=2.0, delay=0.6, range=15), "E": _a("Gatecrash", AN, 1, range=50)},
}
SLOTS = ("C", "Q", "E")


def kit(agent: str) -> dict | None:
    """The agent's abilities for the drills, or None (no such agent)."""
    k = KITS.get(agent)
    return {s: dict(k[s]) for s in SLOTS if s in k} if k else None
