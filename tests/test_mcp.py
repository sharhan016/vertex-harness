import json
import os
import subprocess
import sys
from pathlib import Path

from vertex_harness.agent import MCPServer
from vertex_harness.application import WorkflowService
from vertex_harness.domain import AcceptanceCriterion
from vertex_harness.intelligence import IndexStore


def initialized_repository(tmp_path):
    service = WorkflowService()
    service.initialize(tmp_path, "Expose read-only project context")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Serve tools",
        outcome="An agent can inspect Vertex",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "Status is readable"),),
    )
    (tmp_path / "module.py").write_text(
        "def searchable_symbol():\n    return 1\n", encoding="utf-8"
    )
    IndexStore(tmp_path).rebuild()


def request(identifier, method, params=None):
    value = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        value["params"] = params
    return value


def modern_params(**values):
    return {
        **values,
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    }


def test_modern_mcp_discovers_lists_and_calls_tools_without_handshake(tmp_path):
    initialized_repository(tmp_path)
    server = MCPServer(tmp_path)

    discovery = server.handle(request(1, "server/discover", modern_params()))
    assert discovery["result"]["supportedVersions"] == ["2026-07-28"]
    assert discovery["result"]["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "vertex-harness"

    tools = server.handle(request(2, "tools/list", modern_params()))
    names = [tool["name"] for tool in tools["result"]["tools"]]
    assert names == [
        "vertex_status",
        "vertex_context",
        "search_symbols",
        "get_definitions",
        "get_dependencies",
        "get_dependents",
        "get_impact",
    ]
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools["result"]["tools"])

    called = server.handle(
        request(
            3,
            "tools/call",
            modern_params(name="search_symbols", arguments={"query": "searchable"}),
        )
    )
    assert called["result"]["isError"] is False
    assert called["result"]["structuredContent"]["results"][0]["path"] == "module.py"


def test_legacy_mcp_requires_and_accepts_initialize(tmp_path):
    initialized_repository(tmp_path)
    server = MCPServer(tmp_path)

    before = server.handle(request(1, "tools/list"))
    assert before["error"]["code"] == -32002

    initialized = server.handle(
        request(
            2,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
    )
    assert initialized["result"]["protocolVersion"] == "2025-11-25"
    assert server.handle(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    ) is None

    status = server.handle(
        request(
            3,
            "tools/call",
            {"name": "vertex_status", "arguments": {}},
        )
    )
    assert status["result"]["structuredContent"]["objective"] == "Expose read-only project context"


def test_mcp_rejects_unsupported_modern_version_and_reports_tool_errors(tmp_path):
    initialized_repository(tmp_path)
    server = MCPServer(tmp_path)
    unsupported = modern_params()
    unsupported["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2099-01-01"

    response = server.handle(request(1, "tools/list", unsupported))
    assert response["error"]["code"] == -32022

    tool_error = server.handle(
        request(
            2,
            "tools/call",
            modern_params(name="unknown", arguments={}),
        )
    )
    assert tool_error["result"]["isError"] is True
    assert "unknown tool" in tool_error["result"]["content"][0]["text"]


def test_mcp_tools_do_not_change_project_state(tmp_path):
    initialized_repository(tmp_path)
    state_path = tmp_path / ".vertex" / "project.json"
    before = state_path.read_bytes()
    server = MCPServer(tmp_path)

    server.handle(
        request(
            1,
            "tools/call",
            modern_params(name="vertex_context", arguments={}),
        )
    )
    server.handle(
        request(
            2,
            "tools/call",
            modern_params(name="get_definitions", arguments={"path": "module.py"}),
        )
    )

    assert state_path.read_bytes() == before


def test_stdio_transport_emits_one_json_response_per_request(tmp_path):
    initialized_repository(tmp_path)
    initialize = request(
        1,
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    )
    list_tools = request(2, "tools/list")
    input_text = json.dumps(initialize) + "\n" + json.dumps(list_tools) + "\n"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")

    completed = subprocess.run(
        [sys.executable, "-m", "vertex_harness", "mcp", str(tmp_path)],
        input=input_text,
        capture_output=True,
        text=True,
        env=environment,
        timeout=10,
        check=False,
    )

    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert [response["id"] for response in responses] == [1, 2]
    assert responses[1]["result"]["tools"][0]["name"] == "vertex_status"
