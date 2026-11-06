"""Vercel serverless function: POST /api/ask {"question": "...", "context_scheme": "..."}.

The question is processed in memory and never logged or stored.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipeline import answer_question  # noqa: E402
from rag.retriever import load_chunks  # noqa: E402
from rag.schemes import SCHEMES  # noqa: E402

load_chunks()  # load the corpus at import so the first question doesn't pay for it

MAX_BODY = 4096


def handle(body: bytes) -> tuple[int, dict]:
    try:
        payload = json.loads(body or b"{}")
    except ValueError:
        return 400, {"error": "Request body must be JSON."}
    question = payload.get("question", "")
    if not isinstance(question, str):
        return 400, {"error": "question must be a string."}
    ctx = payload.get("context_scheme")
    ctx = ctx if ctx in SCHEMES else None
    try:
        return 200, answer_question(question, ctx)
    except Exception:  # never leak internals
        return 500, {"error": "Something went wrong while answering. Please try again."}


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, data: dict):
        out = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, {"error": "Question is too long."})
        status, data = handle(self.rfile.read(length))
        self._send(status, data)

    def do_GET(self):
        # Warm-up / health check: the page calls this on load so a cold start happens before the first question.
        self._send(200, {"ok": True, "usage": "POST a JSON body: {\"question\": \"...\"}"})

    def log_message(self, *args):  # silence default request logging (no user text in logs)
        pass
