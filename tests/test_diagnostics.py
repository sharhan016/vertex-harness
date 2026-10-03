from vertex_harness.application import WorkflowService, diagnose
from vertex_harness.intelligence import IndexStore


def test_doctor_reports_uninitialized_repository_as_warning(tmp_path):
    report = diagnose(tmp_path)

    assert report["overall"] == "warning"
    assert {check["name"]: check["status"] for check in report["checks"]} == {
        "python": "ok",
        "repository": "ok",
        "state": "warning",
        "index": "warning",
    }


def test_doctor_reports_initialized_and_indexed_repository_as_healthy(tmp_path):
    WorkflowService().initialize(tmp_path, "Diagnose the project")
    (tmp_path / "module.py").write_text("value = 1\n", encoding="utf-8")
    IndexStore(tmp_path).rebuild()

    report = diagnose(tmp_path)

    assert report["overall"] == "ok"
    assert all(check["status"] == "ok" for check in report["checks"])
