"""Loopback-only read API and dashboard server."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from vertex_harness.application import ContextService, WorkflowService
from vertex_harness.application.views import evidence_view, snapshot_view
from vertex_harness.intelligence import IndexNotFoundError, IndexStore
from vertex_harness.workspace import source_fingerprint

LOOPBACK = "127.0.0.1"


class VertexHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(repository: Path | str, port: int = 0) -> VertexHTTPServer:
    """Create a read-only server bound to IPv4 loopback."""
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65_535:
        raise ValueError("port must be between 0 and 65535")
    root = Path(repository).resolve()
    if not root.is_dir():
        raise ValueError(f"repository directory does not exist: {root}")
    handler = _handler_for(root)
    return VertexHTTPServer((LOOPBACK, port), handler)


def serve(repository: Path | str, port: int = 0, *, open_browser: bool = False) -> None:
    server = create_server(repository, port)
    url = f"http://{LOOPBACK}:{server.server_port}/"
    print(f"Vertex dashboard: {url}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _handler_for(repository: Path):
    class Handler(BaseHTTPRequestHandler):
        server_version = "VertexDashboard/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._asset("dashboard.html")
            elif parsed.path == "/assets/dashboard.css":
                self._asset("dashboard.css")
            elif parsed.path == "/assets/dashboard.js":
                self._asset("dashboard.js")
            elif parsed.path == "/api/health":
                self._json({"status": "ok", "mode": "read-only"})
            elif parsed.path == "/api/status":
                self._api(lambda: snapshot_view(WorkflowService().status(repository)))
            elif parsed.path == "/api/evidence":
                self._api(
                    lambda: [
                        evidence_view(receipt)
                        for receipt in WorkflowService().status(repository).evidence[-50:]
                    ]
                )
            elif parsed.path == "/api/context":
                query = parse_qs(parsed.query)
                task_id = query.get("task", [None])[0]
                self._api(
                    lambda: ContextService().build(repository, task_id=task_id)
                )
            elif parsed.path == "/api/index":
                self._api(lambda: _index_view(repository), not_found=(IndexNotFoundError,))
            else:
                self._json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

        def do_HEAD(self) -> None:
            self._json({}, include_body=False)

        def do_POST(self) -> None:
            self._method_not_allowed()

        def do_PUT(self) -> None:
            self._method_not_allowed()

        def do_PATCH(self) -> None:
            self._method_not_allowed()

        def do_DELETE(self) -> None:
            self._method_not_allowed()

        def _method_not_allowed(self) -> None:
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "GET, HEAD")
            self._security_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _api(self, operation, *, not_found=()) -> None:
            try:
                value = operation()
            except not_found as error:
                self._json({"error": str(error)}, status=HTTPStatus.NOT_FOUND)
            except Exception as error:
                self._json(
                    {"error": f"{type(error).__name__}: {error}"},
                    status=HTTPStatus.CONFLICT,
                )
            else:
                self._json(value)

        def _asset(self, name: str) -> None:
            resource = files("vertex_harness.interfaces.web").joinpath(name)
            try:
                payload = resource.read_bytes()
            except (FileNotFoundError, OSError):
                self._json({"error": "asset not found"}, status=HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if name.endswith(".js"):
                content_type = "text/javascript"
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _json(
            self,
            value: Any,
            *,
            status: HTTPStatus = HTTPStatus.OK,
            include_body: bool = True,
        ) -> None:
            payload = json.dumps(value, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self._security_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload) if include_body else 0))
            self.end_headers()
            if include_body:
                self.wfile.write(payload)

        def _security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'",
            )

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def _index_view(repository: Path) -> dict[str, Any]:
    index = IndexStore(repository).load()
    return {
        "generated_at": index.generated_at,
        "source_hash": index.source_hash,
        "stale": source_fingerprint(repository) != index.source_hash,
        "files": [
            {
                "path": unit.path,
                "module": unit.module,
                "symbols": len(unit.symbols),
                "imports": len(unit.imports),
            }
            for unit in index.files
        ],
        "issues": [
            {"path": issue.path, "message": issue.message, "line": issue.line}
            for issue in index.issues
        ],
    }
