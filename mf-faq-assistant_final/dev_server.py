"""Local development server: serves index.html and the /api/ask endpoint.

Run:  python dev_server.py   then open http://localhost:8000
"""
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:  # optional: load .env for local runs
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
except FileNotFoundError:
    pass

from api.ask import handle  # noqa: E402


class Dev(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def do_GET(self):
        if self.path.startswith("/api/ask"):
            out = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        if self.path.startswith("/api/schemes"):
            import json
            from rag.fund_cards import fund_cards
            out = json.dumps({"schemes": fund_cards()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/ask":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        import json
        status, data = handle(self.rfile.read(min(n, 4096)))
        out = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Serving on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Dev).serve_forever()
