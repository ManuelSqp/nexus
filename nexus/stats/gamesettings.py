"""VALORANT's own settings for the trainer and the drills (4.71): the Nexus app reads them on the player's PC
(desktop/nexus_desktop/valsettings.py) and sends what the trainer uses:

    {"source": "client"|"files", "floats": {"MouseSensitivity": 0.35, ...},
     "strings": {"SavedCrosshairProfileData": "{...}", "CrosshairProfileName": "..."},
     "actions": [{"name": "Crouch", "key": "C", "bindIndex": 0, "characterName": "None", "shift": true?}, ...],
     "axes": [{"name": "MoveForward", "key": "W", "scale": 1.0}, ...]}

VALORANT keeps only what was changed from its defaults, so everything missing is VALORANT's default. Here it becomes
the trainer's: sens (setup["sens"]), the crosshair (setup["crosshair"], like stats/trainer.clean_crosshair) and the
keys of the drill actions (stats/drills.ACTIONS, as the browser's e.code names)."""
from __future__ import annotations

import hashlib
import json
import math

from . import drills as dr
from . import trainer as tr

VALORANT_DEFAULT_SENS = 1.0
MAX_BINDS = 400

# ------------------------------------------------------------------------------------------------ keys
# VALORANT's action names (as in its keybinds; several spellings were used over the years) -> the drill action.
ACTION_NAMES = {
    "shoot": ("PrimaryTrigger", "Fire", "PrimaryFire"),
    "ads": ("SecondaryTrigger", "AltFire", "AlternateFire", "Zoom"),
    "reload": ("Reload",),
    "forward": ("MoveForward",),
    "back": ("MoveBackward", "MoveBack"),
    "left": ("StrafeLeft", "MoveLeft"),
    "right": ("StrafeRight", "MoveRight"),
    "walk": ("Walk",),
    "crouch": ("Crouch",),
    "defuse": ("UseChannelObject", "UseSpike", "UseBomb", "Activate_Level", "EquipSpike", "EquipBomb"),
    "ab_c": ("Activate_GrenadeAbility", "EquipGrenadeAbility", "GrenadeAbility"),
    "ab_q": ("Activate_Ability1", "EquipAbility1", "Ability1"),
    "ab_e": ("Activate_Ability2", "EquipAbility2", "Ability2"),
}
_BY_NAME = {n.lower(): a for a, names in ACTION_NAMES.items() for n in names}
# VALORANT's factory keys for those actions (Unreal key names), the second slot empty
GAME_DEFAULTS = {"shoot": "LeftMouseButton", "ads": "RightMouseButton", "reload": "R", "forward": "W", "back": "S",
                 "left": "A", "right": "D", "walk": "LeftShift", "crouch": "LeftControl", "defuse": "Four",
                 "ab_c": "C", "ab_q": "Q", "ab_e": "E"}
# the trainer's own actions (not in the game): if a key from the game is on one of them, the next free one here
OWN_KEYS = {"restart": ["Backspace", "KeyT", "KeyY"], "next": ["Space", "Enter", "KeyN"], "watch": ["KeyP", "KeyO", "KeyI"],
            "full": ["KeyF", "KeyH", "KeyU"]}

_DIGITS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
_UE = {"LeftMouseButton": "Mouse0", "RightMouseButton": "Mouse2", "MiddleMouseButton": "Mouse1",
       "ThumbMouseButton": "Mouse3", "ThumbMouseButton2": "Mouse4", "MouseScrollUp": "WheelUp", "MouseScrollDown": "WheelDown",
       "SpaceBar": "Space", "LeftShift": "ShiftLeft", "RightShift": "ShiftRight", "LeftControl": "ControlLeft",
       "RightControl": "ControlRight", "LeftAlt": "AltLeft", "RightAlt": "AltRight", "Tab": "Tab", "CapsLock": "CapsLock",
       "Enter": "Enter", "BackSpace": "Backspace", "Tilde": "Backquote", "Hyphen": "Minus", "Equals": "Equal",
       "LeftBracket": "BracketLeft", "RightBracket": "BracketRight", "Backslash": "Backslash", "Semicolon": "Semicolon",
       "Apostrophe": "Quote", "Comma": "Comma", "Period": "Period", "Slash": "Slash", "Insert": "Insert",
       "Delete": "Delete", "Home": "Home", "End": "End", "PageUp": "PageUp", "PageDown": "PageDown", "Up": "ArrowUp",
       "Down": "ArrowDown", "Left": "ArrowLeft", "Right": "ArrowRight", "Multiply": "NumpadMultiply", "Add": "NumpadAdd",
       "Subtract": "NumpadSubtract", "Divide": "NumpadDivide", "Decimal": "NumpadDecimal"}


def ue_code(key: str) -> str | None:
    """An Unreal key name ("SpaceBar", "One", "ThumbMouseButton") -> the browser's code ("Space", "Digit1", "Mouse3");
    None: unbound ("None") or a key the browser can't tell apart (Escape, a gamepad button)."""
    k = str(key or "").strip()
    if len(k) == 1 and k.isascii() and k.isalpha():
        return "Key" + k.upper()
    if k in _DIGITS:
        return f"Digit{_DIGITS.index(k)}"
    if k.startswith("NumPad") and k[6:] in _DIGITS:
        return f"Numpad{_DIGITS.index(k[6:])}"
    if len(k) in (2, 3) and k[0] == "F" and k[1:].isdigit() and 1 <= int(k[1:]) <= 12:
        return k
    return _UE.get(k)


def action_of(name: str) -> str | None:
    return _BY_NAME.get(str(name or "").strip().lower())


def _axis_action(name: str, scale) -> str | None:
    """Movement as an axis: MoveForward +1 forward / -1 back, MoveRight +1 right / -1 left."""
    try:
        s = float(scale)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(s) or s == 0:
        return None
    n = str(name or "").lower()
    if "forward" in n:
        return "forward" if s > 0 else "back"
    if "right" in n or "strafe" in n:
        return "right" if s > 0 else "left"
    return None


def game_keys(d: dict) -> tuple[dict, list[str]]:
    """The drill actions' keys as they are in the game: {action: [key, second key]} for the actions the game has,
    and what couldn't be taken over (a key with Shift/Ctrl, a bind for one agent only, a key the browser can't see)."""
    slots = {a: [ue_code(GAME_DEFAULTS[a]) or "", ""] for a in ACTION_NAMES}
    skipped: list[str] = []
    entries = [(_axis_action(m.get("name"), m.get("scale")), m) for m in (d.get("axes") or [])[:MAX_BINDS] if isinstance(m, dict)]
    entries += [(action_of(m.get("name")), m) for m in (d.get("actions") or [])[:MAX_BINDS] if isinstance(m, dict)]
    seen_axis: set[tuple[str, int]] = set()
    for a, m in entries:
        if not a:
            continue
        who = str(m.get("characterName") or "None")
        if who not in ("None", ""):
            skipped.append(f"{m.get('name')} (only for one agent)")
            continue
        i = m.get("bindIndex")
        if i is None:
            i = 1 if "scale" in m and (a, 0) in seen_axis else 0    # an axis may have no index: first key, then second
        elif isinstance(i, bool) or not isinstance(i, (int, float)) or i not in (0, 1):
            continue
        i = int(i)
        seen_axis.add((a, i))
        key = str(m.get("key") or "")
        if key in ("", "None"):
            slots[a][i] = ""
            continue
        if any(m.get(k) is True for k in ("shift", "ctrl", "alt", "cmd")):
            skipped.append(f"{m.get('name')}: {key} with a modifier")
            continue
        code = ue_code(key)
        if not code:
            skipped.append(f"{m.get('name')}: {key}")
            continue
        slots[a][i] = code
    for a, ks in slots.items():
        if not ks[0] and ks[1]:
            slots[a] = [ks[1], ""]
        elif not ks[0]:
            slots[a] = [dr.ACTIONS[a][1], ""]                # unbound in the game: the drill still needs a key
    return slots, skipped


def merge_keys(mine: dict, game: dict) -> dict:
    """The game's keys on its actions; the trainer's own actions keep theirs unless a game key is on them (then the
    next free one of OWN_KEYS)."""
    out = dr.clean_keys({**(mine or {}), **game})
    used = {k for a in game for k in out[a] if k}
    for a, choices in OWN_KEYS.items():
        ks = [k for k in out.get(a, []) if k and k not in used]
        if not ks:
            ks = [next((c for c in choices if c not in used), choices[0])]
        out[a] = (ks + [""])[:2]
        used.update(k for k in out[a] if k)
    return out


# ------------------------------------------------------------------------------------------------ crosshair
def _ci(d, key):
    """A JSON key in any case (the files and the client don't always agree)."""
    if not isinstance(d, dict):
        return None
    if key in d:
        return d[key]
    low = key.lower()
    return next((v for k, v in d.items() if isinstance(k, str) and k.lower() == low), None)


def _f(d, key, default: float) -> float:
    v = _ci(d, key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else default


def _b(d, key, default: bool) -> bool:
    v = _ci(d, key)
    return v if isinstance(v, bool) else default


def _color(c, default: str = "#ffffff") -> str:
    if not isinstance(c, dict):
        return default
    try:
        r, g, b = (max(0, min(255, int(_f(c, ch, 255)))) for ch in ("r", "g", "b"))
    except (TypeError, ValueError):
        return default
    return f"#{r:02x}{g:02x}{b:02x}"


def profiles(d: dict) -> tuple[list[dict], int]:
    """VALORANT's crosshair profiles: ([{"name", "primary": {...}}], index of the one in use)."""
    raw = (d.get("strings") or {}).get("SavedCrosshairProfileData")
    try:
        doc = json.loads(raw) if isinstance(raw, str) else None
    except ValueError:
        return [], 0
    ps = _ci(doc, "profiles")
    if not isinstance(ps, list) or not ps:
        return [], 0
    cur = _ci(doc, "currentProfile")
    cur = int(cur) if isinstance(cur, (int, float)) and not isinstance(cur, bool) and 0 <= cur < len(ps) else 0
    out = []
    for i, p in enumerate(ps[:50]):
        if not isinstance(p, dict):
            out.append({"name": f"Profile {i + 1}", "primary": None})
            continue
        name = _ci(p, "profileName")
        out.append({"name": name.strip()[:40] if isinstance(name, str) and name.strip() else f"Profile {i + 1}",
                    "primary": _ci(p, "primary")})
    return out, cur


def crosshair_of(primary) -> dict | None:
    """VALORANT's primary crosshair (the profile JSON) -> the trainer's crosshair (stats/trainer.clean_crosshair)."""
    if not isinstance(primary, dict):
        return None
    color = _color(_ci(primary, "colorCustom")) if _b(primary, "bUseCustomColor", False) else _color(_ci(primary, "color"))
    inner, outer = _ci(primary, "innerLines") or {}, _ci(primary, "outerLines") or {}
    x = {"color": color, "outline": _b(primary, "bHasOutline", True), "ot": _f(primary, "outlineThickness", 1),
         "oo": _f(primary, "outlineOpacity", 0.5), "dot": _b(primary, "bDisplayCenterDot", False),
         "dt": _f(primary, "centerDotSize", 2), "da": _f(primary, "centerDotOpacity", 1),
         "inner": _b(inner, "bShowLines", True), "it": _f(inner, "lineThickness", 2), "il": _f(inner, "lineLength", 6),
         "iv": _f(inner, "lineLengthVertical", _f(inner, "lineLength", 6)), "ig": _b(inner, "bAllowVertScaling", False),
         "io": _f(inner, "lineOffset", 3), "ia": _f(inner, "opacity", 0.8),
         "outer": _b(outer, "bShowLines", True), "ot2": _f(outer, "lineThickness", 2), "ol": _f(outer, "lineLength", 2),
         "ov": _f(outer, "lineLengthVertical", _f(outer, "lineLength", 2)), "og": _b(outer, "bAllowVertScaling", False),
         "oo2": _f(outer, "lineOffset", 10), "oa": _f(outer, "opacity", 0.35)}
    if _b(primary, "bHideCrosshair", False):
        x.update(outline=False, dot=False, inner=False, outer=False)
    for k, (lo, hi) in tr.CROSSHAIR_NUM.items():                     # the trainer's ranges
        x[k] = round(min(hi, max(lo, x[k])), 3)
    return tr.clean_crosshair(x)


# ------------------------------------------------------------------------------------------------ all of it
def clean(d) -> dict | None:
    """The app's message, only the expected shape and sane sizes."""
    if not isinstance(d, dict):
        return None
    floats = {str(k)[:64]: float(v) for k, v in (d.get("floats") or {}).items()
              if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)} if isinstance(d.get("floats"), dict) else {}
    strings = {str(k)[:64]: v for k, v in (d.get("strings") or {}).items()
               if isinstance(v, str) and len(v) <= 60000} if isinstance(d.get("strings"), dict) else {}
    lists = {k: [m for m in d.get(k)[:MAX_BINDS] if isinstance(m, dict)] if isinstance(d.get(k), list) else [] for k in ("actions", "axes")}
    if not (floats or strings or lists["actions"] or lists["axes"]):
        return None
    return {"source": d.get("source") if d.get("source") in ("client", "files") else "files", "floats": floats,
            "strings": strings, **lists}


def read(d: dict) -> dict:
    """What the trainer takes from the game: {sens, crosshair, crosshair_name, profiles, keys, skipped}."""
    fl = d.get("floats") or {}
    sens = fl.get("MouseSensitivity")
    if sens is None and d.get("source") == "client":       # the client has everything: missing means the default
        sens = VALORANT_DEFAULT_SENS
    sens = round(sens, 4) if isinstance(sens, float) and 0.01 <= sens <= 20 else None
    ps, cur = profiles(d)
    xh = crosshair_of(ps[cur]["primary"]) if ps else None
    keys, skipped = game_keys(d)
    custom = sum(1 for a, ks in keys.items() if ks != [ue_code(GAME_DEFAULTS[a]), ""])
    return {"sens": sens, "crosshair": xh, "crosshair_name": ps[cur]["name"] if ps and xh else "",
            "profiles": len(ps), "keys": keys, "custom_keys": custom, "skipped": skipped[:20]}


def digest(g: dict) -> str:
    """Of what the trainer takes (a change elsewhere in the game's settings doesn't count)."""
    core = {k: g.get(k) for k in ("sens", "crosshair", "keys")}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]


def changes(g: dict, setup: dict, keys: dict) -> list[str]:
    """What's different from the trainer's settings now, in words ("sens 0.4 → 0.35", "crosshair Main", "keys: Crouch")."""
    out = []
    if g.get("sens") is not None and setup.get("sens") != g["sens"]:
        out.append(f"sens {setup.get('sens') or '–'} → {g['sens']}")
    if g.get("crosshair") and setup.get("crosshair") != g["crosshair"]:
        out.append(f"crosshair {g.get('crosshair_name') or ''}".strip())
    diff = [dr.ACTIONS[a][0] for a, ks in (g.get("keys") or {}).items() if a in dr.ACTIONS and (keys or {}).get(a, [""])[0] != ks[0]]
    if diff:
        out.append("keys: " + ", ".join(diff[:4]) + (f" +{len(diff) - 4}" if len(diff) > 4 else ""))
    return out


def apply(g: dict, setup: dict, keys: dict) -> tuple[dict, dict]:
    """The trainer's setup and keys with the game's settings in them."""
    setup = dict(setup or {})
    if g.get("sens") is not None:
        setup["sens"] = g["sens"]
    if g.get("crosshair"):
        setup["crosshair"] = g["crosshair"]
    return setup, merge_keys(keys, g.get("keys") or {})
