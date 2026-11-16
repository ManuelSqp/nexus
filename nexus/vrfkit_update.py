"""vrfkit updates itself (4.43): `nexus vrfkit-update`, run every 3 hours by deploy/nexus-vrfkit-update.timer.

vrfkit reads the game's replay files and needs an update after most VALORANT patches (a new build). This checks
vrfkit's main branch on GitHub; when there's a new commit it

1. builds it into a separate folder (cargo install --root <staging>), so the vrfkit in use isn't touched;
2. tests the new build: it must start, and it must read one of the replay files kept on the server (the newest);
   without a kept replay, starting is the only test;
3. only then puts it in place of the old one, which stays next to it as `vrfkit.prev` (to go back:
   `nexus vrfkit-update --rollback`).

Nexus notices the new program by itself (no restart needed): replays it kept because vrfkit couldn't read their
patch are tried again within 5 minutes (replayfile.retry_pending). Every run is written to
data/vrfkit_update.json (shown in Admin › Server and on the Replay files page) and to the journal.

It runs as its own systemd service, not inside the web app: the web app may not write to the home folder
(ProtectHome in nexus.service), and a build takes a few minutes of CPU.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import replayfile

log_ = logging.getLogger(__name__)

REPO = "https://github.com/yakisoba0728/vrfkit"
BRANCH = "main"
BUILD_TIMEOUT_S = 45 * 60
STATE_FILE = "vrfkit_update.json"


class UpdateError(Exception):
    pass


def state(data_dir: Path) -> dict:
    try:
        return json.loads((Path(data_dir) / STATE_FILE).read_text())
    except (OSError, ValueError):
        return {}


def _save(data_dir: Path, st: dict) -> None:
    p = Path(data_dir) / STATE_FILE
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(st, indent=1))
    os.replace(tmp, p)


def _run(cmd: list[str], timeout: int = 120, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def latest_commit(repo: str = REPO, branch: str = BRANCH) -> str:
    try:
        r = _run(["git", "ls-remote", repo, f"refs/heads/{branch}"], timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise UpdateError(f"GitHub not reachable: {e}")
    sha = (r.stdout.split() or [""])[0]
    if r.returncode != 0 or len(sha) != 40:
        raise UpdateError(f"GitHub not reachable: {(r.stderr or r.stdout).strip()[:200]}")
    return sha


def installed_commit(vrfkit: str) -> str:
    """The commit cargo installed (from ~/.cargo/.crates2.json), '' if unknown."""
    roots = [Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo"))]
    exe = shutil.which(vrfkit) or vrfkit
    if Path(exe).parent.name == "bin":
        roots.insert(0, Path(exe).parent.parent)
    for root in roots:
        try:
            d = json.loads((root / ".crates2.json").read_text())
        except (OSError, ValueError):
            continue
        for key in d.get("installs", {}):
            if key.startswith("vrfkit ") and "#" in key:
                return key.rsplit("#", 1)[1].rstrip(")")
    return ""


def cargo() -> str:
    found = shutil.which("cargo")
    if found:
        return found
    c = Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")) / "bin" / "cargo"
    if c.is_file():
        return str(c)
    raise UpdateError("cargo was not found (install Rust: https://rustup.rs).")


def build(sha: str, root: Path, repo: str = REPO) -> Path:
    """cargo install into root; -> the new program."""
    try:
        r = _run([cargo(), "install", "--git", repo, "--rev", sha, "--locked", "--force", "--root", str(root), "vrfkit"],
                 timeout=BUILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise UpdateError("the build took too long")
    exe = root / "bin" / ("vrfkit.exe" if os.name == "nt" else "vrfkit")
    if r.returncode != 0 or not exe.is_file():
        last = [ln for ln in (r.stderr or r.stdout or "").splitlines() if ln.strip()][-3:]
        raise UpdateError("the build failed: " + " / ".join(x.strip() for x in last)[:300])
    return exe


def test(exe: Path, replays_dir: Path, work_dir: Path) -> str:
    """The new build must start and read the newest kept replay. -> what was tested."""
    problem = replayfile.check_vrfkit(str(exe))
    if problem:
        raise UpdateError(f"the new build doesn't start: {problem}")
    vrfs = sorted(Path(replays_dir).glob("*.vrf"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not vrfs:
        return "starts (no kept replay to test with)"
    vrf = vrfs[0]
    out = Path(work_dir) / f"vrf-test-{os.getpid()}"
    try:
        replayfile.export(str(exe), vrf, out)
        data = replayfile.extract(out, vrf.name)
    except replayfile.ReplayError as e:
        raise UpdateError(f"the new build couldn't read {vrf.name}: {e}")
    finally:
        shutil.rmtree(out, ignore_errors=True)
    if not data.get("pos"):
        raise UpdateError(f"the new build read {vrf.name} but found no player positions")
    return f"starts and reads {vrf.name} ({len(data['pos'])} players)"


def swap(new: Path, target: Path) -> None:
    """Put the new program in place; the old one stays as <name>.prev."""
    target = Path(target)
    if target.exists():
        shutil.copy2(target, target.with_name(target.name + ".prev"))
    tmp = target.with_name(target.name + ".new")
    shutil.copy2(new, tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, target)


def target_path(setting: str) -> Path:
    p = replayfile.vrfkit_path(setting)
    found = shutil.which(p)
    if found:
        return Path(found).resolve()
    if Path(p).is_absolute():
        return Path(p)
    return Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")) / "bin" / "vrfkit"


def run(data_dir: Path, setting: str = "", force: bool = False, dry_run: bool = False) -> dict:
    """One check. -> the state written to data/vrfkit_update.json."""
    data_dir = Path(data_dir)
    st = state(data_dir)
    target = target_path(setting)
    now = int(time.time())
    st.update(checked=now)
    try:
        sha = latest_commit()
        have = st.get("commit") or installed_commit(str(target))
        st.update(latest=sha)
        if have == sha and not force:
            st.update(result="up to date", commit=sha, error="")
            return st
        if dry_run:
            st.update(result=f"new version available ({sha[:7]}), not installed (dry run)")
            return st
        with tempfile.TemporaryDirectory(prefix="vrfkit-build-") as tmp:
            exe = build(sha, Path(tmp))
            tested = test(exe, data_dir / "replays", data_dir / "cache" / "vrf_work")
            swap(exe, target)
        st.update(result=f"updated to {sha[:7]}", previous=have, commit=sha, tested=tested, updated=now, error="")
        log_.info("vrfkit updated to %s (%s)", sha[:7], tested)
    except UpdateError as e:
        st.update(result="failed, the old vrfkit stays in use", error=str(e))
        log_.warning("vrfkit update failed: %s", e)
    finally:
        if not dry_run:
            _save(data_dir, st)
    return st


def rollback(data_dir: Path, setting: str = "") -> str:
    target = target_path(setting)
    prev = target.with_name(target.name + ".prev")
    if not prev.is_file():
        raise UpdateError(f"no previous vrfkit next to {target}")
    os.replace(prev, target)
    st = state(data_dir)
    st.update(result="rolled back to the previous vrfkit", commit=st.get("previous", ""), checked=int(time.time()))
    _save(Path(data_dir), st)
    return str(target)
