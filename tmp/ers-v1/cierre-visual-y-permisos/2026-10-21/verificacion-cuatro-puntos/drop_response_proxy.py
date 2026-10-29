"""Isolated response-loss proxy for ERS-FINAL-4P acceptance checks.

For the first two successful responses to a single adjustment-apply or
delivery-confirm URL, this proxy waits for the upstream response (after the
server has completed the command) and then closes the browser connection
without forwarding response bytes. It never logs request bodies or headers.
"""
from __future__ import annotations

from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UPSTREAM = "http://127.0.0.1:8001"
LISTEN = ("127.0.0.1", 8002)
DROP_SUCCESSFUL_RESPONSES = 2
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}
COUNTS: dict[str, int] = defaultdict(int)
LOG_PATH = r"C:\Developer\GESTIONASV_ERP\tmp\ers-v1\cierre-visual-y-permisos\2026-10-20\verificacion-cuatro-puntos\response-loss-proxy.log"


def log(event: dict[str, object]) -> None:
    event["time"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(LOG_PATH, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def droppable(path: str) -> bool:
    path_only = path.split("?", 1)[0]
    pieces = path_only.strip("/").split("/")
    return (
        len(pieces) == 6
        and pieces[:3] == ["api", "v1", "inventory"]
        and pieces[3] == "adjustments"
        and pieces[5] == "apply"
    ) or (
        len(pieces) == 6
        and pieces[:3] == ["api", "v1", "sales"]
        and pieces[3] == "deliveries"
        and pieces[5] == "confirm"
    )


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/__proxy_health":
            body = b"response-loss-proxy-ready\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.forward()

    def do_HEAD(self) -> None:  # noqa: N802
        self.forward()

    def do_POST(self) -> None:  # noqa: N802
        self.forward()

    def do_PUT(self) -> None:  # noqa: N802
        self.forward()

    def do_PATCH(self) -> None:  # noqa: N802
        self.forward()

    def do_DELETE(self) -> None:  # noqa: N802
        self.forward()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.forward()

    def forward(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            key: value for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP
        }
        headers["Accept-Encoding"] = "identity"
        request = Request(UPSTREAM + self.path, data=body, headers=headers, method=self.command)
        try:
            response = urlopen(request, timeout=120)
            status, response_headers, response_body = response.status, response.headers, response.read()
        except HTTPError as error:
            status, response_headers, response_body = error.code, error.headers, error.read()
        except (URLError, TimeoutError, OSError) as error:
            log({"event": "upstream_error", "method": self.command, "path": self.path,
                 "error_type": type(error).__name__})
            self.close_connection = True
            self.connection.close()
            return

        if droppable(self.path) and 200 <= status < 300:
            count_key = self.command + " " + self.path.split("?", 1)[0]
            if COUNTS[count_key] < DROP_SUCCESSFUL_RESPONSES:
                COUNTS[count_key] += 1
                log({"event": "committed_response_dropped", "method": self.command,
                     "path": self.path.split("?", 1)[0], "upstream_status": status,
                     "response_sha256": hashlib.sha256(response_body).hexdigest(),
                     "drop_number": COUNTS[count_key], "idempotency_key": self.headers.get("Idempotency-Key")})
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
                return

        self.send_response(status)
        for key, value in response_headers.items():
            if key.lower() not in HOP_BY_HOP and key.lower() != "content-encoding":
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        if self.command != "HEAD" and response_body:
            self.wfile.write(response_body)


if __name__ == "__main__":
    log({"event": "proxy_started", "listen": f"http://{LISTEN[0]}:{LISTEN[1]}",
         "upstream": UPSTREAM, "drop_successful_responses_per_command": DROP_SUCCESSFUL_RESPONSES})
    ThreadingHTTPServer(LISTEN, Handler).serve_forever()
