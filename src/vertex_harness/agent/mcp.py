"""Read-only Model Context Protocol server over newline-delimited stdio."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from vertex_harness import __version__
from vertex_harness.application import ContextService, WorkflowService
from vertex_harness.application.views import snapshot_view
from vertex_harness.intelligence import QueryService

MODERN_VERSION = "2026-07-28"
LEGACY_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_LINE_BYTES = 4 * 1024 * 1024
SERVER_INFO = {"name": "vertex-harness", "version": __version__}
INSTRUCTIONS = (
    "Read Vertex project status and bounded context before acting. Repository index "
    "answers are advisory and may be stale. This server never changes project state."
)


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = list(required)
    return {
        "name": name,
        "description": description,
        "inputSchema": schema,
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    }


TOOLS = (
    _tool("vertex_status", "Read the current project and task status.", {}),
    _tool(
        "vertex_context",
        "Build bounded context for the active or named task.",
        {
            "task_id": {"type": "string"},
            "max_bytes": {"type": "integer", "minimum": 1024, "maximum": 65536},
        },
    ),
    _tool(
        "search_symbols",
        "Search indexed Python declarations by name.",
        {"query": {"type": "string"}},
        ("query",),
    ),
    _tool(
        "get_definitions",
        "List indexed declarations in a Python file.",
        {"path": {"type": "string"}},
        ("path",),
    ),
    _tool(
        "get_dependencies",
        "List imports made by an indexed Python file.",
        {"path": {"type": "string"}},
        ("path",),
    ),
    _tool(
        "get_dependents",
        "List files with resolved imports of an indexed Python file.",
        {"path": {"type": "string"}},
        ("path",),
    ),
    _tool(
        "get_impact",
        "Find transitive import dependents of an indexed Python file.",
        {"path": {"type": "string"}},
        ("path",),
    ),
)


class MCPServer:
    """Small dual-era MCP dispatcher with no state-changing tools."""

    def __init__(self, repository: Path | str) -> None:
        self.repository = Path(repository)
        self.legacy_initialized = False

    def handle(self, request: object) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return _error(None, -32600, "Invalid Request")
        request_id = request.get("id")
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return _error(request_id, -32600, "Invalid Request")

        method = request["method"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid params")
        modern = _modern_version(params)
        if modern is not None and modern != MODERN_VERSION:
            return _error(
                request_id,
                -32022,
                f"Unsupported protocol version: {modern}",
                {"supported": [MODERN_VERSION]},
            )

        if method == "notifications/initialized" or method == "notifications/cancelled":
            return None
        if method == "initialize":
            response = self._initialize(request_id, params)
        elif method == "server/discover":
            if modern != MODERN_VERSION:
                response = _error(request_id, -32601, "Method not found")
            else:
                response = _result(request_id, self._discover())
        elif modern is None and not self.legacy_initialized:
            response = _error(request_id, -32002, "Server is not initialized")
        elif method == "ping":
            response = _result(request_id, {})
        elif method == "tools/list":
            result: dict[str, Any] = {"tools": list(TOOLS)}
            if modern == MODERN_VERSION:
                result.update(
                    resultType="complete", ttlMs=3_600_000, cacheScope="public"
                )
            response = _result(request_id, result)
        elif method == "tools/call":
            response = self._call_tool(request_id, params)
        else:
            response = _error(request_id, -32601, "Method not found")

        if request_id is None:
            return None
        if modern == MODERN_VERSION and "result" in response:
            response["result"].setdefault("_meta", {})[
                "io.modelcontextprotocol/serverInfo"
            ] = SERVER_INFO
        return response

    def _initialize(self, request_id: object, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        version = requested if requested in LEGACY_VERSIONS else LEGACY_VERSIONS[0]
        self.legacy_initialized = True
        return _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            },
        )

    @staticmethod
    def _discover() -> dict[str, Any]:
        return {
            "resultType": "complete",
            "supportedVersions": [MODERN_VERSION],
            "capabilities": {"tools": {"listChanged": False}},
            "instructions": INSTRUCTIONS,
            "ttlMs": 3_600_000,
            "cacheScope": "public",
        }

    def _call_tool(self, request_id: object, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, -32602, "Invalid tool call params")
        try:
            value = self._invoke(name, arguments)
        except Exception as error:
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"{type(error).__name__}: {error}"}],
                    "isError": True,
                },
            )
        return _result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(value, indent=2, sort_keys=True),
                    }
                ],
                "structuredContent": value,
                "isError": False,
            },
        )

    def _invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "vertex_status":
            _no_extra(arguments, set())
            return snapshot_view(WorkflowService().status(self.repository))
        if name == "vertex_context":
            _no_extra(arguments, {"task_id", "max_bytes"})
            task_id = arguments.get("task_id")
            max_bytes = arguments.get("max_bytes", 8_000)
            if task_id is not None and not isinstance(task_id, str):
                raise ValueError("task_id must be a string")
            if not isinstance(max_bytes, int) or isinstance(max_bytes, bool):
                raise ValueError("max_bytes must be an integer")
            return ContextService().build(
                self.repository, task_id=task_id, max_bytes=max_bytes
            )

        mapping = {
            "search_symbols": ("search", "query"),
            "get_definitions": ("defines", "path"),
            "get_dependencies": ("dependencies", "path"),
            "get_dependents": ("dependents", "path"),
            "get_impact": ("impact", "path"),
        }
        if name not in mapping:
            raise ValueError(f"unknown tool: {name}")
        kind, argument_name = mapping[name]
        _no_extra(arguments, {argument_name})
        value = arguments.get(argument_name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{argument_name} must be non-empty text")
        return QueryService().execute(self.repository, kind, value)


def serve_stdio(repository: Path | str) -> None:
    server = MCPServer(repository)
    while True:
        line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
        if not line:
            return
        if len(line) > MAX_LINE_BYTES:
            while line and not line.endswith(b"\n"):
                line = sys.stdin.buffer.readline(MAX_LINE_BYTES + 1)
            _write(_error(None, -32700, "Request frame exceeds 4 MiB"))
            continue
        try:
            request = json.loads(line)
        except (UnicodeError, json.JSONDecodeError):
            _write(_error(None, -32700, "Parse error"))
            continue
        response = server.handle(request)
        if response is not None:
            _write(response)


def _modern_version(params: dict[str, Any]) -> str | None:
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return None
    value = meta.get("io.modelcontextprotocol/protocolVersion")
    return value if isinstance(value, str) else None


def _no_extra(arguments: dict[str, Any], allowed: set[str]) -> None:
    extra = set(arguments) - allowed
    if extra:
        raise ValueError(f"unexpected arguments: {', '.join(sorted(extra))}")


def _result(request_id: object, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(
    request_id: object,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _write(response: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
    sys.stdout.flush()
