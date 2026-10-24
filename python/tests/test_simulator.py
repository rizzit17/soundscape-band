"""Connected simulation tests: exported traces must execute the original policy."""
import csv
import io
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from deda.policy import DEDA, DirObs, Window, run
from deda.simulator import alert_dict, experiment, simulate, summarize
from simulator_server import Handler, csv_result


@pytest.mark.parametrize("sound,angle,motor", [("horn",180,4),("siren",270,8),("shout",90,2),("beep",0,1)])
def test_clean_source_warns_towards_source_or_uses_fallback(sound, angle, motor):
    r = simulate(dict(sound=sound, angle=angle))
    # Tonal beeps may be ambiguous even in free field: preserve actual fallback.
    assert r["deda"]["first_alert"]["motors"] in (motor, 15)
    if sound in ("horn", "siren", "shout"):
        assert r["deda"]["first_alert"]["motors"] == motor
    assert not r["deda"]["wrong_direction"]


def test_trace_replays_original_deda_exactly():
    r = simulate(dict(condition="interference", snr_db=0))
    windows = [Window(f["t_ms"], f["probs"], DirObs(**f["direction"]) if f["direction_available"] else None) for f in r["frames"]]
    assert [alert_dict(a) for a in run(DEDA(), windows)] == r["alerts"]


def test_dropout_fallback_and_ambient_silence():
    r = simulate(dict(condition="dropout"))
    assert r["deda"]["first_alert"]["motors"] == 15
    assert all(not f["direction_available"] for f in r["frames"])
    assert simulate(dict(sound="ambient"))["alerts"] == []


def test_deterministic_trace_and_export():
    a, b = simulate(dict(seed=53)), simulate(dict(seed=53))
    assert a["frames"] == b["frames"]
    json.dumps(a, allow_nan=False)
    rows = list(csv.DictReader(io.StringIO(csv_result(a))))
    assert len(rows) == len(a["frames"])
    assert all(None not in row for row in rows)
    assert float(rows[4]["estimated_angle"]) == a["frames"][4]["direction"]["theta_deg"]


def test_seeded_suite_counts_denominators_and_serialization():
    r = experiment(dict(seeds=1))
    assert len(r["trials"]) == 33
    assert r["policies"]["deda"]["events"] == 32
    assert r["policies"]["deda"]["ambient_trials"] == 1
    assert r["policies"]["deda"]["ambient_hours"] > 0
    # A real computed error is retained, rather than forced to match paper results.
    assert any(t["deda"]["wrong_direction"] for t in r["trials"])
    for key in ("baseline", "deda"):
        assert summarize(r["trials"], key) == r["policies"][key]
    assert len(list(csv.DictReader(io.StringIO(csv_result(r))))) == 66
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("data", [{"seed":-1},{"angle":float("nan")},{"sound":"unknown"},{"confidence":2},{"event_ms":1.5},{"snr_db":True}])
def test_invalid_inputs_rejected(data):
    with pytest.raises(ValueError):
        simulate(data)


def test_server_routes_validation_and_origin():
    server = ThreadingHTTPServer(("127.0.0.1",0),Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        assert json.load(urlopen(url+"/api/health"))["status"] == "ok"
        assert b"SoundScape" in urlopen(url).read()
        request = Request(url+"/api/simulate", data=b'{"condition":"dropout"}', headers={"Content-Type":"application/json"})
        r = json.load(urlopen(request))
        assert r["deda"]["first_alert"]["motors"] == 15 and "csv" in r
        for path, data, headers, code in [
            ("/api/simulate",b'{"angle":-1}',{},400),
            ("/api/simulate",b'{}',{"Origin":"https://example.com"},403),
            ("/api/simulate",b'[]',{},400),
            ("/api/other",b'{}',{},404),
        ]:
            with pytest.raises(HTTPError) as error:
                urlopen(Request(url+path, data=data,headers=headers))
            assert error.value.code == code
        with pytest.raises(HTTPError) as error:
            urlopen(url+"/../README.md")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
