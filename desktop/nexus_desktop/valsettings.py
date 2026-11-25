"""VALORANT's own settings on this PC (4.71): sensitivity, crosshair profiles and keybinds, so the aim trainer and the
drills on Nexus play with the same ones without setting them up by hand.

Two places, the first that answers wins:
1. The Riot Client, while it runs: it serves the account's settings (the ones Riot keeps online, so always the
   current ones) on this PC only, at https://127.0.0.1:<port>/player-preferences/v1/data-json/Ares.PlayerSettings,
   with the port and password from its lockfile (%LOCALAPPDATA%\\Riot Games\\Riot Client\\Config\\lockfile).
2. VALORANT's files: %LOCALAPPDATA%\\VALORANT\\Saved\\Config\\<account>\\Windows\\RiotUserSettings.ini (sens and the
   crosshair profiles) and ...\\WindowsClient\\BackupKeybinds.json (the keys), the account VALORANT last used.

Only what the trainer uses is sent (sensitivities, the crosshair profiles, the keybinds), nothing else of the account:
no name, no id, no token. Both settings and keybinds list only what was changed from VALORANT's defaults; the server
fills in the rest (nexus/stats/gamesettings.py)."""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import ssl
from pathlib import Path

TIMEOUT = 5
ENDPOINT = "/player-preferences/v1/data-json/Ares.PlayerSettings"
MAX_STRING = 60000                  # the crosshair profiles are a few kB; anything bigger isn't them


def local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))


def lockfile(base: Path | None = None) -> dict | None:
    """The Riot Client's lockfile: name:pid:port:password:protocol, or None while it doesn't run."""
    p = (base or local_appdata()) / "Riot Games" / "Riot Client" / "Config" / "lockfile"
    try:
        parts = p.read_text(encoding="utf-8").strip().split(":")
    except OSError:
        return None
    if len(parts) < 5 or not parts[2].isdigit():
        return None
    return {"port": int(parts[2]), "password": parts[3], "protocol": parts[4]}


def _short(name: str) -> str:
    """"EAresFloatSettingName::MouseSensitivity" -> "MouseSensitivity"."""
    return str(name).rsplit("::", 1)[-1]


def wanted(kind: str, name: str) -> bool:
    """Only the settings the trainer uses."""
    if kind == "floats":
        return "Sensitivity" in name
    if kind == "strings":
        return name in ("SavedCrosshairProfileData", "CrosshairProfileName")
    return False


def _bind(m: dict) -> dict | None:
    if not isinstance(m, dict) or not isinstance(m.get("name"), str) or not isinstance(m.get("key"), str):
        return None
    out = {"name": m["name"][:64], "key": m["key"][:64]}
    for k in ("bindIndex", "scale"):
        if isinstance(m.get(k), (int, float)) and not isinstance(m.get(k), bool):
            out[k] = m[k]
    if isinstance(m.get("characterName"), str):
        out["characterName"] = m["characterName"][:64]
    for k in ("shift", "ctrl", "alt", "cmd"):
        if m.get(k) is True:
            out[k] = True
    return out


def from_data(data: dict, source: str) -> dict:
    """Ares.PlayerSettings (the client's "data") -> what's sent: {source, floats, strings, actions, axes}."""
    out: dict = {"source": source, "floats": {}, "strings": {}, "actions": [], "axes": []}
    for item in data.get("floatSettings") or []:
        if isinstance(item, dict) and isinstance(item.get("value"), (int, float)):
            n = _short(item.get("settingEnum", ""))
            if wanted("floats", n):
                out["floats"][n] = float(item["value"])
    for item in data.get("stringSettings") or []:
        if isinstance(item, dict) and isinstance(item.get("value"), str):
            n = _short(item.get("settingEnum", ""))
            if wanted("strings", n) and len(item["value"]) <= MAX_STRING:
                out["strings"][n] = item["value"]
    for key, dest in (("actionMappings", "actions"), ("axisMappings", "axes")):
        for m in data.get(key) or []:
            b = _bind(m)
            if b:
                out[dest].append(b)
    return out


def from_client(base: Path | None = None) -> dict | None:
    """The settings from the running Riot Client, or None (not running, not logged in, an old client)."""
    lf = lockfile(base)
    if not lf:
        return None
    # the client's own certificate, on this PC only (127.0.0.1): there's no public name to check it against; the
    # password from the lockfile is what keeps other programs out
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    auth = base64.b64encode(f"riot:{lf['password']}".encode()).decode()
    try:
        c = http.client.HTTPSConnection("127.0.0.1", lf["port"], timeout=TIMEOUT, context=ctx)
        c.request("GET", ENDPOINT, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
        r = c.getresponse()
        body = r.read(4 * 1024 * 1024)
        c.close()
    except (OSError, http.client.HTTPException):
        return None
    if r.status != 200:
        return None
    try:
        doc = json.loads(body)
    except ValueError:
        return None
    data = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(data, dict) or not (data.get("floatSettings") or data.get("stringSettings") or data.get("actionMappings")):
        return None
    return from_data(data, "client")


# ---------------------------------------------------------------------------------------------- VALORANT's files
def config_dir(base: Path | None = None) -> Path:
    return (base or local_appdata()) / "VALORANT" / "Saved" / "Config"


def parse_ini(text: str) -> dict:
    """key=value lines; "EAres…SettingName::" taken off the keys."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "[;" or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[_short(k.strip())] = v.strip()
    return out


def unquote_ue(v: str) -> str:
    """An Unreal ini string: "{\\"a\\":1}" -> {"a":1}."""
    v = v.strip()
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v


def account_dir(base: Path | None = None) -> Path | None:
    """The account folder VALORANT used last (RiotLocalMachine.ini's LastKnownUser, else the newest one)."""
    root = config_dir(base)
    try:
        folders = [d for d in root.iterdir() if d.is_dir() and (d / "Windows" / "RiotUserSettings.ini").is_file()]
    except OSError:
        return None
    if not folders:
        return None
    try:
        last = parse_ini((root / "WindowsClient" / "RiotLocalMachine.ini").read_text(encoding="utf-8", errors="replace")).get("LastKnownUser", "")
    except OSError:
        last = ""
    if last:
        for d in folders:
            if d.name.lower().startswith(last.lower()):
                return d
    return max(folders, key=lambda d: (d / "Windows" / "RiotUserSettings.ini").stat().st_mtime)


def from_files(base: Path | None = None) -> dict | None:
    d = account_dir(base)
    if d is None:
        return None
    try:
        ini = parse_ini((d / "Windows" / "RiotUserSettings.ini").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None
    out: dict = {"source": "files", "floats": {}, "strings": {}, "actions": [], "axes": []}
    for k, v in ini.items():
        if wanted("floats", k):
            try:
                out["floats"][k] = float(v)
            except ValueError:
                pass
        elif wanted("strings", k):
            s = unquote_ue(v)
            if len(s) <= MAX_STRING:
                out["strings"][k] = s
    try:
        kb = json.loads((d / "WindowsClient" / "BackupKeybinds.json").read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        kb = {}
    if isinstance(kb, dict):
        for key, dest in (("actionMappings", "actions"), ("axisMappings", "axes")):
            for m in kb.get(key) or []:
                b = _bind(m)
                if b:
                    out[dest].append(b)
    if not (out["floats"] or out["strings"] or out["actions"]):
        return None
    return out


def read(base: Path | None = None) -> dict | None:
    return from_client(base) or from_files(base)


def digest(d: dict) -> str:
    """The same settings give the same digest (where they came from doesn't count)."""
    core = {k: v for k, v in d.items() if k != "source"}
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()[:16]
