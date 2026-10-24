"""Offline browser UI served on loopback with the existing Python simulation."""
from __future__ import annotations

import argparse
import csv
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from deda.simulator import experiment, simulate

STATIC = Path(__file__).resolve().parents[1] / "simulator"
LOCK = threading.Lock()


def csv_result(result):
    out = io.StringIO(newline="")
    w = csv.writer(out)
    if "trials" in result:
        w.writerow(["sound", "condition", "angle", "snr_db", "confidence", "seed", "policy",
                    "missed", "missed_or_late", "wrong_direction", "nondirectional", "latency_ms", "false_alerts"])
        for trial in result["trials"]:
            o = trial["options"]
            for p in ("baseline", "deda"):
                m = trial[p]
                w.writerow([o[k] for k in ("sound", "condition", "angle", "snr_db", "confidence", "seed")] +
                           [p] + [m[k] for k in ("missed", "missed_or_late", "wrong_direction", "nondirectional", "latency_ms", "false_alerts")])
    else:
        w.writerow(["t_ms", "source_active", "estimated_angle", "closure_samples", "plane_wave_norm", "coherence", "direction_available", "reliable",
                    "p_horn", "p_siren", "p_shout", "p_beep", "p_ambient", "deda_alerts", "baseline_alerts", "decision"])
        for f in result["frames"]:
            d = f["direction"]
            w.writerow([f["t_ms"], f["source_active"], d["theta_deg"], d["closure"], d["norm"], d["coherence"], f["direction_available"], f["reliable"]] +
                       f["probs"] + [json.dumps(f["alerts"]), json.dumps(f["baseline_alerts"]), f["decision"]])
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data, kind="application/json; charset=utf-8"):
        if not isinstance(data, bytes):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self.reply(200, json.dumps({"status": "ok", "engine": "Python DEDA + GCC-PHAT", "classification": "simulated"}))
        files = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
        if path not in files:
            return self.reply(404, json.dumps({"error": "Not found"}))
        name, mime = files[path]
        self.reply(200, (STATIC / name).read_bytes(), mime + "; charset=utf-8")

    def do_POST(self):
        # The app is a loopback-only tool. Reject cross-origin browser submissions.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
            return self.reply(403, json.dumps({"error": "Use the local simulator page"}))
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 4096:
                raise ValueError("Request must contain a JSON object under 4 KB")
            raw = json.loads(self.rfile.read(size))
            if not isinstance(raw, dict):
                raise ValueError("Request must be a JSON object")
            path = urlsplit(self.path).path
            if path not in ("/api/simulate", "/api/experiment"):
                return self.reply(404, json.dumps({"error": "Not found"}))
            if not LOCK.acquire(blocking=False):
                return self.reply(409, json.dumps({"error": "An experiment is already running; wait for it to finish"}))
            try:
                result = simulate(raw) if path == "/api/simulate" else experiment(raw)
            finally:
                LOCK.release()
            result["csv"] = csv_result(result)
            self.reply(200, json.dumps(result, allow_nan=False))
        except (ValueError, TypeError) as exc:
            self.reply(400, json.dumps({"error": str(exc)}))
        except Exception:
            import traceback
            traceback.print_exc()
            self.reply(500, json.dumps({"error": "Simulation failed. See the server terminal for details."}))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"SoundScape simulation: http://127.0.0.1:{server.server_port}", flush=True)
    print("Keep this terminal open. Press Ctrl+C to stop. No network services or hardware required.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
