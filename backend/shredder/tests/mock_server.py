"""
Mock HTTP server for the integration tests. Run it in a background thread of the test
process so the tests can read the callbacks it receives directly from memory.

Endpoints:
- GET  /example.pdf  Serves tests/static/example.pdf as the document to convert.
- POST /webhook      Records Shredder's multipart callback, keyed by its job_id field.
"""

import threading
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_PORT = 1234


def parse_multipart(content_type: str, body: bytes) -> tuple[dict, dict]:
    """Split a multipart/form-data body into (fields, files)."""
    message = BytesParser(policy=policy.HTTP).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode() + body
    )
    fields, files = {}, {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = bytes(part.get_payload(decode=True)) or b""
        filename = part.get_filename()
        if filename is None:
            fields[name] = payload.decode()
        else:
            files[name] = {"filename": filename, "content": payload}
    return fields, files


class MockServerHandler(BaseHTTPRequestHandler):
    server: "MockServer"

    def do_GET(self):
        if self.path == "/example.pdf":
            self._send(200, (STATIC_DIR / "example.pdf").read_bytes(), "application/pdf")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/webhook":
            self._send(404, b"not found", "text/plain")
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        fields, files = parse_multipart(self.headers.get("Content-Type", ""), body)
        self.server.record_callback(
            fields.get("job_id", ""),
            {
                "authorization": self.headers.get("Authorization"),
                "fields": fields,
                "files": files,
            },
        )
        self._send(200, b"ok", "text/plain")

    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class MockServer(ThreadingHTTPServer):
    """
    Each request is handled on its own thread, so callbacks are shared through a
    lock-protected dict, with a threading.Event per job_id to wake up waiting tests.
    """

    def __init__(self, port: int = DEFAULT_PORT, host: str = "0.0.0.0"):  # noqa: S104
        super().__init__((host, port), MockServerHandler)
        self._lock = threading.Lock()
        self._callbacks: dict[str, dict] = {}
        self._events: dict[str, threading.Event] = {}

    def _event_for(self, job_id: str) -> threading.Event:
        with self._lock:
            return self._events.setdefault(job_id, threading.Event())

    def record_callback(self, job_id: str, record: dict) -> None:
        with self._lock:
            self._callbacks[job_id] = record
        self._event_for(job_id).set()

    def wait_for_callback(self, job_id: str, timeout: float) -> dict | None:
        """Block until the callback for job_id arrives; None if it doesn't within timeout."""
        if not self._event_for(job_id).wait(timeout):
            return None
        with self._lock:
            return self._callbacks[job_id]
