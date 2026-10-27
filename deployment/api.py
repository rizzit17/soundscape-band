"""Stateless Vercel HTTP adapter for the unchanged Python simulation engine."""
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from deda.simulator import simulate, experiment
from simulator_server import csv_result

class handler(BaseHTTPRequestHandler):
    def reply(self, code, data, mime='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def route(self):
        parsed = urlsplit(self.path)
        return parse_qs(parsed.query).get('route', [parsed.path.removeprefix('/api/')])[0].strip('/')

    def do_GET(self):
        if self.route() == 'health':
            return self.reply(200, json.dumps(dict(status='ok', engine='Python DEDA + GCC-PHAT', classification='simulated', execution='serverless')))
        # Exact allowlist also provides a local preview of the deployed adapter.
        files = {'/':('index.html','text/html'), '/app.js':('app.js','text/javascript'), '/style.css':('style.css','text/css'), '/favicon.svg':('favicon.svg','image/svg+xml')}
        path = urlsplit(self.path).path
        if path in files:
            name,mime=files[path]
            return self.reply(200,(ROOT/'public'/name).read_bytes(),mime+'; charset=utf-8')
        self.reply(404,json.dumps(dict(error='Not found')))

    def do_POST(self):
        origin = self.headers.get('Origin')
        # Match the platform-provided request host, never reflect arbitrary origins.
        host = self.headers.get('Host', '')
        if origin and (urlsplit(origin).netloc != host or urlsplit(origin).scheme not in ('http','https')):
            return self.reply(403,json.dumps(dict(error='Use the simulation page on this host.')))
        if self.route() not in ('simulate','experiment'):
            return self.reply(404,json.dumps(dict(error='Not found')))
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0 < size <= 4096:
                raise ValueError('Request must be a JSON object under 4 KB')
            raw=json.loads(self.rfile.read(size))
            if not isinstance(raw,dict):
                raise ValueError('Request must be a JSON object')
            result=simulate(raw) if self.route()=='simulate' else experiment(raw)
            result['csv']=csv_result(result)
            self.reply(200,json.dumps(result,allow_nan=False))
        except (ValueError,TypeError) as exc:
            self.reply(400,json.dumps(dict(error=str(exc))))
        except Exception:
            import traceback
            traceback.print_exc()
            self.reply(500,json.dumps(dict(error='Calculation failed. Try a smaller experiment or retry the scene.')))
