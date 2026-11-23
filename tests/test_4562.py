"""4.56.2: the map list from valorant-api.com is fetched again when it's old (Summit was missing); map angles on
sites without a Main / Lobby / Link callout."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402
from test_427 import payload  # noqa: E402

from nexus import maps as mp  # noqa: E402
from nexus.maps import MapRegistry, _parse_maps  # noqa: E402
from nexus.stats import mapangles as ma  # noqa: E402

ROOT = Path(__file__).parent.parent


class _Resp:
    def __init__(self, data):
        self.text = json.dumps(data)
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _with_summit():
    pay = synth.maps_payload()
    extra = json.loads(json.dumps(pay["data"][1]))
    extra["uuid"], extra["displayName"] = "summit-uuid", "Summit"
    pay["data"].append(extra)
    return pay


def _old(f, days=8):
    t = time.time() - days * 86400
    os.utime(f, (t, t))


class _Calls(list):
    fake = None


@pytest.fixture
def calls(monkeypatch):
    got = _Calls()

    def fake(url, timeout=0):
        got.append(url)
        if isinstance(fake.answer, Exception):
            raise fake.answer
        return _Resp(fake.answer)
    fake.answer = _with_summit()
    monkeypatch.setattr(mp.requests, "get", fake)
    got.fake = fake
    return got


def test_an_old_list_is_fetched_again(tmp_path, calls):
    f = tmp_path / "valorant_api_maps.json"
    f.write_text(json.dumps(synth.maps_payload()))
    assert MapRegistry(tmp_path).get(name="Summit") is None and calls == []          # a fresh list: as it is
    _old(f)
    assert MapRegistry(tmp_path).get(name="Summit").uuid == "summit-uuid" and calls == [mp.VALORANT_API_MAPS]
    assert MapRegistry(tmp_path).get(name="Summit") is not None and len(calls) == 1    # and now it's fresh again


def test_offline_keeps_the_old_list_and_waits(tmp_path, calls):
    f = tmp_path / "valorant_api_maps.json"
    f.write_text(json.dumps(synth.maps_payload()))
    _old(f)
    calls.fake.answer = OSError("offline")
    assert MapRegistry(tmp_path).get(name="Summit") is None and len(calls) == 1
    assert MapRegistry(tmp_path).load() and len(calls) == 1                           # not again within the hour
    _old(tmp_path / "valorant_api_maps.tried", days=0.1)
    calls.fake.answer = {"data": "broken"}                                             # a list that doesn't read
    assert MapRegistry(tmp_path).get(name="Summit") is None and len(calls) == 2
    assert json.loads(f.read_text()) == synth.maps_payload()                           # never replaced by it
    _old(tmp_path / "valorant_api_maps.tried", days=0.1)
    calls.fake.answer = _with_summit()
    assert MapRegistry(tmp_path).get(name="Summit") is not None and len(calls) == 3


def test_a_site_named_otherwise():
    pay = payload()
    for c in pay["data"][1]["callouts"]:
        if (c["superRegionName"], c["regionName"]) == ("B", "Main"):
            c["regionName"] = "Triples"                    # no B Main, Lobby or Link
    mi = next(m for m in _parse_maps(pay) if m.name == "Ascent")
    ps = {p["id"]: p for p in ma.positions(mi)}
    assert ps["B-hold"]["face"] in ("B Triples", "B Back") and ps["B-take"]["stand"] == ps["B-hold"]["face"]
    assert ma._approach(mi, "B", None) is None


def test_version():
    import nexus
    assert tuple(int(x) for x in nexus.__version__.split(".")[:3]) >= (4, 56, 2)
    assert "## 4.56.2" in (ROOT / "CHANGELOG.md").read_text()
    assert "**Version " in (ROOT / "README.md").read_text()
