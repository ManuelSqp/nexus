"""4.43: replays of a patch vrfkit can't read yet are kept and read later; vrfkit updates itself (tested first)."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_web import add_profile, app, setup_admin, synthetic  # noqa: E402,F401

from nexus import replayfile, vrfkit_update as vu  # noqa: E402
from nexus.web import replays as wr  # noqa: E402

MID = "02b3659c-735e-432a-8f55-91425f8934df"
ERR = ("error: unsupported branch: unsupported replay branch: no payload transform is registered for replay branch "
       "'++Ares-Core+release-13.10'; known branches: ++Ares-Core+release-11.06, ++Ares-Core+release-13.09")


def _fake_vrfkit(tmp_path, stderr=ERR, code=1, name="vrfkit"):
    exe = tmp_path / name
    exe.write_text(f"#!/bin/sh\necho \"{stderr}\" >&2\nexit {code}\n")
    exe.chmod(0o755)
    return str(exe)


@pytest.mark.skipif(os.name == "nt", reason="shell script")
def test_unsupported_patch_is_recognised(tmp_path):
    with pytest.raises(replayfile.UnsupportedBuild) as e:
        replayfile.export(_fake_vrfkit(tmp_path), tmp_path / "x.vrf", tmp_path / "out")
    assert e.value.branch == "++Ares-Core+release-13.10" and e.value.patch == "13.10"
    assert isinstance(e.value, replayfile.ReplayError)          # old callers still see a ReplayError
    with pytest.raises(replayfile.ReplayError) as e2:            # any other failure stays an ordinary error
        replayfile.export(_fake_vrfkit(tmp_path, "error: bad magic", name="vk2"), tmp_path / "x.vrf", tmp_path / "o2")
    assert not isinstance(e2.value, replayfile.UnsupportedBuild)


def test_kept_and_read_once_vrfkit_changes(tmp_path, monkeypatch):
    rd = tmp_path / "replays"
    vk = tmp_path / "vrfkit"
    vk.write_text("v1")
    up = tmp_path / "upload.vrf"
    up.write_bytes(b"REPLAY" * 100)
    err = replayfile.UnsupportedBuild("x", "++Ares-Core+release-13.10")
    meta = replayfile.keep_pending(up, rd, err, name="my match.vrf", uid=1, vrfkit=str(vk))
    assert not up.exists() and meta["patch"] == "13.10"
    again = tmp_path / "again.vrf"                               # the same file twice: kept once
    again.write_bytes(b"REPLAY" * 100)
    replayfile.keep_pending(again, rd, err, name="again.vrf", vrfkit=str(vk))
    assert len(replayfile.pending(rd)) == 1
    calls = []

    def ingest(vrf, rdir, work, vrfkit, keep_vrf=True):
        calls.append(vrfkit)
        if Path(vrfkit).read_text() == "v1":
            raise replayfile.UnsupportedBuild("x", "++Ares-Core+release-13.10")
        dest = replayfile.vrf_file(rdir, MID)
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(vrf, dest)
        return {"match_id": MID}
    monkeypatch.setattr(replayfile, "ingest", ingest)
    res = replayfile.retry_pending(rd, tmp_path / "w", str(vk))
    assert res == {"read": [], "waiting": 1} and calls == []     # same vrfkit as at upload: not tried again
    vk.write_text("v2-new")                                       # vrfkit updated
    res = replayfile.retry_pending(rd, tmp_path / "w", str(vk))
    assert res["read"] == [{"match_id": MID}] and res["waiting"] == 0
    assert replayfile.pending(rd) == [] and replayfile.stored(rd) == [MID]
    assert not list((rd / "pending").glob("*"))


def test_still_unsupported_is_tried_once_per_vrfkit(tmp_path, monkeypatch):
    rd = tmp_path / "replays"
    vk = tmp_path / "vrfkit"
    vk.write_text("v1")
    up = tmp_path / "u.vrf"
    up.write_bytes(b"A" * 10)
    replayfile.keep_pending(up, rd, replayfile.UnsupportedBuild("x", "++Ares-Core+release-13.10"), vrfkit=str(vk))
    vk.write_text("v2-but-still-old")
    n = []

    def ingest(*a, **k):
        n.append(1)
        raise replayfile.UnsupportedBuild("x", "++Ares-Core+release-13.10")
    monkeypatch.setattr(replayfile, "ingest", ingest)
    replayfile.retry_pending(rd, tmp_path / "w", str(vk))
    replayfile.retry_pending(rd, tmp_path / "w", str(vk))
    assert len(n) == 1 and len(replayfile.pending(rd)) == 1


def test_upload_page_keeps_new_patch(app, monkeypatch):  # noqa: F811 (fixture)
    def ingest(vrf, rdir, work, vrfkit, keep_vrf=True):
        raise replayfile.UnsupportedBuild("vrfkit can't read replays of x yet.", "++Ares-Core+release-13.10")
    monkeypatch.setattr(replayfile, "ingest", ingest)
    monkeypatch.setattr(wr, "_rows", lambda _app, pid: [])
    c = setup_admin(app)
    pid = add_profile(c)
    body = b"VRF" * 50
    up = c.post("/api/replays", json={"name": "Lotus 13.10.vrf", "size": len(body)}).get_json()
    c.put(f"/api/uploads/{up['id']}?offset=0", data=body)
    r = c.post(f"/api/replays/{up['id']}/store?pid={pid}")
    assert r.status_code == 202 and r.get_json() == {"ok": True, "pending": True, "patch": "13.10", "name": "Lotus 13.10.vrf"}
    page = c.get(f"/profiles/{pid}/replays").data.decode()
    assert "Waiting for vrfkit" in page and "Lotus 13.10.vrf" in page and "13.10" in page
    rd = wr.replays_dir(app.extensions["nexus"]["store"])
    assert len(replayfile.pending(rd)) == 1
    adm = c.get("/admin/overview").data.decode()
    assert "Waiting for vrfkit" in adm and "vrfkit update" in adm
    tick = app.extensions["nexus"]["replays_retry"]
    assert tick in app.extensions["nexus"]["ticks"]
    tick()                                                       # no vrfkit here: nothing changes, no error
    assert len(replayfile.pending(rd)) == 1


def test_stats_cache_follows_a_reread_replay(tmp_path):
    from nexus.stats import replaystats as rs
    rd = tmp_path / "replays"
    rd.mkdir()
    data = replayfile.data_file(rd, MID)
    data.write_bytes(b"x")
    mf = rs.metrics_file(rd, MID)
    mf.write_text(json.dumps({"v": rs.VERSION, "ok": True, "players": {}}))
    old = time.time() - 100
    os.utime(data, (old, old))
    assert rs.for_match(rd, tmp_path / "cache", MID) == {"v": rs.VERSION, "ok": True, "players": {}}
    os.utime(mf, (old - 50, old - 50))                            # the replay is newer than its numbers
    assert rs.for_match(rd, tmp_path / "cache", MID) is None      # worked out again (no match cached here)


# ------------------------------------------------------------------------------------------- vrfkit updates
def _setup_update(tmp_path, monkeypatch, latest="b" * 40, build_ok=True, test_ok=True):
    target = tmp_path / "bin" / "vrfkit"
    target.parent.mkdir()
    target.write_text("OLD")
    monkeypatch.setattr(vu, "target_path", lambda setting: target)
    monkeypatch.setattr(vu, "latest_commit", lambda *a: latest)
    monkeypatch.setattr(vu, "installed_commit", lambda exe: "a" * 40)

    def build(sha, root, repo=vu.REPO):
        if not build_ok:
            raise vu.UpdateError("the build failed: error[E0308]")
        exe = Path(root) / "bin" / "vrfkit"
        exe.parent.mkdir(parents=True)
        exe.write_text("NEW " + sha)
        return exe

    def test(exe, rdir, work):
        if not test_ok:
            raise vu.UpdateError("the new build couldn't read x.vrf")
        return "starts and reads x.vrf (10 players)"
    monkeypatch.setattr(vu, "build", build)
    monkeypatch.setattr(vu, "test", test)
    return target


def test_update_tested_then_swapped(tmp_path, monkeypatch):
    target = _setup_update(tmp_path, monkeypatch)
    st = vu.run(tmp_path)
    assert st["result"] == "updated to bbbbbbb" and st["commit"] == "b" * 40 and st["previous"] == "a" * 40
    assert target.read_text() == "NEW " + "b" * 40 and target.with_name("vrfkit.prev").read_text() == "OLD"
    assert vu.state(tmp_path)["tested"].startswith("starts and reads")
    assert vu.run(tmp_path)["result"] == "up to date"             # the state remembers the commit
    vu.rollback(tmp_path)
    assert target.read_text() == "OLD" and vu.state(tmp_path)["commit"] == "a" * 40


@pytest.mark.parametrize("build_ok,test_ok,why", [(False, True, "build failed"), (True, False, "couldn't read")])
def test_failed_update_keeps_the_old_vrfkit(tmp_path, monkeypatch, build_ok, test_ok, why):
    target = _setup_update(tmp_path, monkeypatch, build_ok=build_ok, test_ok=test_ok)
    st = vu.run(tmp_path)
    assert st["result"] == "failed, the old vrfkit stays in use" and why in st["error"]
    assert target.read_text() == "OLD" and not target.with_name("vrfkit.prev").exists()
    assert vu.state(tmp_path)["error"]


def test_dry_run_and_up_to_date(tmp_path, monkeypatch):
    target = _setup_update(tmp_path, monkeypatch, latest="a" * 40)
    assert vu.run(tmp_path)["result"] == "up to date" and target.read_text() == "OLD"
    monkeypatch.setattr(vu, "latest_commit", lambda *a: "c" * 40)
    st = vu.run(tmp_path, dry_run=True)
    assert "not installed (dry run)" in st["result"] and target.read_text() == "OLD"


def test_installed_commit_from_cargo(tmp_path, monkeypatch):
    sha = "7c024e7d" + "0" * 32
    (tmp_path / ".crates2.json").write_text(json.dumps({"installs": {
        f"vrfkit 0.5.0 (git+https://github.com/yakisoba0728/vrfkit?rev=7c024e7#{sha})": {}}}))
    (tmp_path / "bin").mkdir()
    exe = tmp_path / "bin" / "vrfkit"
    exe.write_text("")
    assert vu.installed_commit(str(exe)) == sha


def test_real_test_step_uses_a_kept_replay(tmp_path, monkeypatch):
    """vu.test: the new build has to read the newest kept replay and find positions."""
    rd = tmp_path / "replays"
    rd.mkdir()
    (rd / f"{MID}.vrf").write_bytes(b"x")
    monkeypatch.setattr(replayfile, "check_vrfkit", lambda p: None)
    monkeypatch.setattr(replayfile, "export", lambda vk, vrf, out: out)
    monkeypatch.setattr(replayfile, "extract", lambda out, name: {"pos": {"a": [], "b": []}})
    assert vu.test(tmp_path / "vk", rd, tmp_path / "w") == f"starts and reads {MID}.vrf (2 players)"
    monkeypatch.setattr(replayfile, "extract", lambda out, name: {"pos": {}})
    with pytest.raises(vu.UpdateError, match="no player positions"):
        vu.test(tmp_path / "vk", rd, tmp_path / "w")


def test_cli_and_units():
    from nexus import cli
    with pytest.raises(SystemExit):
        cli.main(["vrfkit-update", "--help"])
    root = Path(__file__).parent.parent / "deploy"
    svc = (root / "nexus-vrfkit-update.service").read_text()
    assert "nexus vrfkit-update --data" in svc and "Type=oneshot" in svc and "ProtectHome" not in svc
    assert "OnCalendar=*-*-* 00/3:00:00" in (root / "nexus-vrfkit-update.timer").read_text()   # every 3 hours (4.43.2)


def test_cli_command_runs(tmp_path, monkeypatch, capsys):
    """4.43.1: the command itself (not only --help) runs: it opens the settings store and calls the updater."""
    from nexus import cli
    seen = {}

    def fake_run(data, setting, force=False, dry_run=False):
        seen.update(data=data, setting=setting, dry_run=dry_run)
        return {"result": "up to date", "checked": 1}
    monkeypatch.setattr(vu, "run", fake_run)
    cli.main(["vrfkit-update", "--data", str(tmp_path), "--dry-run"])
    assert seen == {"data": tmp_path.resolve(), "setting": "", "dry_run": True}
    assert "vrfkit: up to date" in capsys.readouterr().out
    monkeypatch.setattr(vu, "run", lambda *a, **k: {"result": "failed, the old vrfkit stays in use", "error": "x"})
    with pytest.raises(SystemExit):
        cli.main(["vrfkit-update", "--data", str(tmp_path)])
    with pytest.raises(SystemExit, match="no previous vrfkit"):
        monkeypatch.setattr(vu, "target_path", lambda s: tmp_path / "vrfkit")
        cli.main(["vrfkit-update", "--data", str(tmp_path), "--rollback"])
