import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from vertex_harness.application import WorkflowService
from vertex_harness.domain import AcceptanceCriterion
from vertex_harness.intelligence import IndexStore
from vertex_harness.interfaces import create_server


@pytest.fixture
def dashboard(tmp_path):
    service = WorkflowService()
    service.initialize(tmp_path, "Observe the project without changing it")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Read status",
        outcome="The dashboard reflects the ledger",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "Status is visible"),),
    )
    (tmp_path / "module.py").write_text("def visible():\n    return 1\n", encoding="utf-8")
    IndexStore(tmp_path).rebuild()
    server = create_server(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield tmp_path, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def read_json(url):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read()), response.headers


def test_dashboard_serves_assets_and_read_only_api(dashboard):
    repository, base = dashboard
    state_path = repository / ".vertex" / "project.json"
    before = state_path.read_bytes()

    with urlopen(base + "/", timeout=5) as response:
        html = response.read().decode()
        assert "Vertex — Project Ledger" in html
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]

    status, headers = read_json(base + "/api/status")
    assert status["objective"] == "Observe the project without changing it"
    assert status["tasks"][0]["id"] == "T-1"
    assert headers["Cache-Control"] == "no-store"

    index, _ = read_json(base + "/api/index")
    assert index["stale"] is False
    assert index["files"][0]["path"] == "module.py"

    with urlopen(base + "/assets/dashboard.js", timeout=5) as response:
        assert response.headers.get_content_type() == "text/javascript"
        assert b"function renderTasks" in response.read()

    assert state_path.read_bytes() == before


def test_dashboard_rejects_state_changing_http_methods(dashboard):
    _, base = dashboard
    request = Request(base + "/api/status", data=b"{}", method="POST")

    with pytest.raises(HTTPError) as error:
        urlopen(request, timeout=5)

    assert error.value.code == 405
    assert error.value.headers["Allow"] == "GET, HEAD"


def test_dashboard_binds_only_to_loopback(tmp_path):
    server = create_server(tmp_path)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()
