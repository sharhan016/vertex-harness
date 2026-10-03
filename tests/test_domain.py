from dataclasses import FrozenInstanceError

import pytest

from vertex_harness.domain import (
    AcceptanceCriterion,
    DomainError,
    DuplicateTaskError,
    InvalidTransitionError,
    Project,
    Task,
    TaskStatus,
    UnknownTaskError,
    UnmetDependenciesError,
    ValidationError,
    VerificationCheck,
    VerificationMismatchError,
)


def criterion(identifier: str = "AC-1") -> AcceptanceCriterion:
    return AcceptanceCriterion(identifier, "The observable result is present")


def task(identifier: str, *, dependencies: tuple[str, ...] = ()) -> Task:
    return Task(
        id=identifier,
        title=f"Implement {identifier}",
        outcome=f"{identifier} has a useful result",
        acceptance_criteria=(criterion(f"{identifier}-AC-1"),),
        dependencies=dependencies,
    )


def test_domain_values_reject_missing_or_inconsistent_contracts():
    with pytest.raises(ValidationError, match="criterion id"):
        AcceptanceCriterion(" ", "Observable")

    with pytest.raises(ValidationError, match="at least one"):
        Task("T-1", "Title", "Outcome", ())

    with pytest.raises(ValidationError, match="criterion ids"):
        Task("T-1", "Title", "Outcome", (criterion(), criterion()))

    with pytest.raises(ValidationError, match="depend on itself"):
        task("T-1", dependencies=("T-1",))

    with pytest.raises(ValidationError, match="TaskStatus"):
        Task("T-1", "Title", "Outcome", (criterion(),), status="active")  # type: ignore[arg-type]


def test_project_requires_unique_ordered_tasks():
    project = Project("Ship a dependable tool").add_task(task("T-1"))

    with pytest.raises(DuplicateTaskError):
        project.add_task(task("T-1"))

    with pytest.raises(ValidationError, match="not defined earlier"):
        Project("Ship a dependable tool", (task("T-2", dependencies=("T-1",)),))


def test_project_and_tasks_are_immutable():
    project = Project("Ship a dependable tool").add_task(task("T-1"))

    with pytest.raises(FrozenInstanceError):
        project.objective = "Changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        project.task("T-1").title = "Changed"  # type: ignore[misc]


def test_available_tasks_follow_completed_dependencies():
    project = Project("Ship a dependable tool")
    project = project.add_task(task("T-1"))
    project = project.add_task(task("T-2", dependencies=("T-1",)))

    assert [item.id for item in project.available_tasks()] == ["T-1"]

    project = project.start_task("T-1")
    project = project.complete_task("T-1", {"T-1-AC-1"})

    assert [item.id for item in project.available_tasks()] == ["T-2"]


def test_start_rejects_incomplete_dependencies_without_mutating_project():
    project = Project("Ship a dependable tool")
    project = project.add_task(task("T-1"))
    project = project.add_task(task("T-2", dependencies=("T-1",)))

    with pytest.raises(UnmetDependenciesError) as error:
        project.start_task("T-2")

    assert error.value.dependencies == ("T-1",)
    assert project.task("T-2").status is TaskStatus.PLANNED


def test_task_can_be_blocked_and_resumed_with_a_reason():
    project = Project("Ship a dependable tool").add_task(task("T-1"))
    project = project.start_task("T-1")
    blocked = project.block_task("T-1", "Waiting for a product decision")

    assert project.task("T-1").status is TaskStatus.ACTIVE
    assert blocked.task("T-1").status is TaskStatus.BLOCKED
    assert blocked.task("T-1").blocker == "Waiting for a product decision"

    resumed = blocked.resume_task("T-1")
    assert resumed.task("T-1").status is TaskStatus.ACTIVE
    assert resumed.task("T-1").blocker is None


def test_completion_requires_exactly_the_declared_criteria():
    project = Project("Ship a dependable tool").add_task(task("T-1"))
    project = project.start_task("T-1")

    with pytest.raises(VerificationMismatchError) as error:
        project.complete_task("T-1", {"UNKNOWN"})

    assert error.value.missing == ("T-1-AC-1",)
    assert error.value.unexpected == ("UNKNOWN",)

    completed = project.complete_task("T-1", {"T-1-AC-1"})
    assert completed.task("T-1").status is TaskStatus.COMPLETED


def test_invalid_transitions_and_unknown_tasks_are_explicit():
    project = Project("Ship a dependable tool").add_task(task("T-1"))

    with pytest.raises(InvalidTransitionError):
        project.complete_task("T-1", {"T-1-AC-1"})
    with pytest.raises(InvalidTransitionError):
        project.resume_task("T-1")
    with pytest.raises(UnknownTaskError):
        project.start_task("T-404")


def test_verification_checks_must_map_to_declared_criteria():
    check = VerificationCheck(
        "tests",
        ("python", "-m", "pytest"),
        ("T-1-AC-1",),
        timeout_seconds=30,
    )
    project = Project("Ship a dependable tool").add_task(task("T-1"))
    configured = project.add_check("T-1", check)

    assert configured.task("T-1").checks == (check,)
    assert project.task("T-1").checks == ()

    with pytest.raises(ValidationError, match="unknown criteria"):
        Task(
            "T-2",
            "Title",
            "Outcome",
            (criterion("AC-2"),),
            checks=(VerificationCheck("bad", ("true",), ("UNKNOWN",)),),
        )


def test_checks_cannot_change_after_work_starts():
    project = Project("Ship a dependable tool").add_task(task("T-1"))
    project = project.start_task("T-1")

    with pytest.raises(DomainError, match="planned tasks"):
        project.add_check(
            "T-1", VerificationCheck("tests", ("true",), ("T-1-AC-1",))
        )
