"""Vercel function: GET /api/schemes -> verified quick facts for the four covered schemes."""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.fund_cards import fund_cards  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        out = json.dumps({"schemes": fund_cards()}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass
