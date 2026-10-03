import pytest

from vertex_harness.application import ContextBudgetError, ContextService, WorkflowService
from vertex_harness.domain import AcceptanceCriterion
from vertex_harness.intelligence import IndexStore


def initialized_project(tmp_path, *, description="The task contract is present"):
    service = WorkflowService()
    service.initialize(tmp_path, "Give an agent bounded context")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Build context",
        outcome="An agent receives the current contract",
        acceptance_criteria=(
            AcceptanceCriterion("AC-1", description),
        ),
    )


def test_context_selects_available_task_and_reports_next_action(tmp_path):
    initialized_project(tmp_path)
    (tmp_path / "module.py").write_text("def symbol():\n    return 1\n", encoding="utf-8")
    IndexStore(tmp_path).rebuild()

    packet = ContextService().build(tmp_path, max_bytes=8_000)

    assert packet["task"]["id"] == "T-1"
    assert packet["next_action"] == "Start available task T-1."
    assert packet["index"]["python_files"] == 1
    assert packet["bytes"] <= 8_000
    assert len(packet["fingerprint"]) == 64


def test_context_rejects_invalid_or_insufficient_budget(tmp_path):
    initialized_project(tmp_path, description="observable " * 300)

    with pytest.raises(ContextBudgetError, match="between 1024"):
        ContextService().build(tmp_path, max_bytes=100)

    with pytest.raises(ContextBudgetError, match="required context"):
        ContextService().build(tmp_path, max_bytes=1_024)
