import pytest

from vertex_harness.application import WorkflowError, WorkflowService
from vertex_harness.domain import AcceptanceCriterion, TaskStatus, UnmetDependenciesError


def test_service_persists_a_dependency_ordered_workflow(tmp_path):
    service = WorkflowService()
    service.initialize(tmp_path, "Deliver the product")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Build foundation",
        outcome="Foundation exists",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "Foundation is usable"),),
    )
    service.add_task(
        tmp_path,
        task_id="T-2",
        title="Build feature",
        outcome="Feature exists",
        acceptance_criteria=(AcceptanceCriterion("AC-2", "Feature is usable"),),
        dependencies=("T-1",),
    )

    with pytest.raises(UnmetDependenciesError):
        service.start_task(tmp_path, "T-2")

    service.start_task(tmp_path, "T-1")
    service.block_task(tmp_path, "T-1", "Need a decision")
    snapshot = service.resume_task(tmp_path, "T-1")

    assert snapshot.revision == 5
    assert snapshot.project.task("T-1").status is TaskStatus.ACTIVE
    assert snapshot.project.task("T-2").status is TaskStatus.PLANNED


def test_initialize_requires_an_existing_repository_directory(tmp_path):
    missing = tmp_path / "typo"

    with pytest.raises(WorkflowError, match="does not exist"):
        WorkflowService().initialize(missing, "Deliver the product")

    assert not missing.exists()
