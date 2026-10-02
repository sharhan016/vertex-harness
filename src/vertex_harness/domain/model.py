"""Dependency-free domain model for planned and verifiable work."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum

from vertex_harness.domain.errors import (
    DuplicateTaskError,
    InvalidTransitionError,
    UnknownTaskError,
    UnmetDependenciesError,
    TaskConfigurationError,
    ValidationError,
    VerificationMismatchError,
)


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be non-empty text")


class TaskStatus(StrEnum):
    """The durable lifecycle states a task may occupy."""

    PLANNED = "planned"
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    """An observable condition that must be accounted for at completion."""

    id: str
    description: str

    def __post_init__(self) -> None:
        _require_text(self.id, "criterion id")
        _require_text(self.description, "criterion description")


@dataclass(frozen=True, slots=True)
class VerificationCheck:
    """An executable command mapped to one or more acceptance criteria."""

    id: str
    command: tuple[str, ...]
    criterion_ids: tuple[str, ...]
    timeout_seconds: int = 300

    def __post_init__(self) -> None:
        _require_text(self.id, "check id")
        command = tuple(self.command)
        criterion_ids = tuple(self.criterion_ids)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "criterion_ids", criterion_ids)

        if not command:
            raise ValidationError("verification command cannot be empty")
        for argument in command:
            _require_text(argument, "verification command argument")
        if not criterion_ids:
            raise ValidationError("verification check must cover at least one criterion")
        for criterion_id in criterion_ids:
            _require_text(criterion_id, "verification criterion id")
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValidationError("verification criterion ids must be unique")
        if (
            not isinstance(self.timeout_seconds, int)
            or isinstance(self.timeout_seconds, bool)
            or not 1 <= self.timeout_seconds <= 3600
        ):
            raise ValidationError("verification timeout must be between 1 and 3600 seconds")


@dataclass(frozen=True, slots=True)
class Task:
    """A bounded outcome and the conditions required to finish it."""

    id: str
    title: str
    outcome: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    dependencies: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PLANNED
    blocker: str | None = None
    checks: tuple[VerificationCheck, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.id, "task id")
        _require_text(self.title, "task title")
        _require_text(self.outcome, "task outcome")

        criteria = tuple(self.acceptance_criteria)
        dependencies = tuple(self.dependencies)
        checks = tuple(self.checks)
        object.__setattr__(self, "acceptance_criteria", criteria)
        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "checks", checks)

        if not criteria:
            raise ValidationError("task must define at least one acceptance criterion")
        if not all(isinstance(criterion, AcceptanceCriterion) for criterion in criteria):
            raise ValidationError("task acceptance criteria must be criterion objects")
        if not isinstance(self.status, TaskStatus):
            raise ValidationError("task status must be a TaskStatus value")
        if not all(isinstance(check, VerificationCheck) for check in checks):
            raise ValidationError("task checks must be verification check objects")
        for dependency in dependencies:
            _require_text(dependency, "dependency id")

        criterion_ids = [criterion.id for criterion in criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValidationError("acceptance criterion ids must be unique within a task")
        if len(dependencies) != len(set(dependencies)):
            raise ValidationError("task dependencies must be unique")
        if self.id in dependencies:
            raise ValidationError("task cannot depend on itself")
        check_ids = [check.id for check in checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValidationError("verification check ids must be unique within a task")
        unknown_criteria = {
            criterion_id
            for check in checks
            for criterion_id in check.criterion_ids
            if criterion_id not in set(criterion_ids)
        }
        if unknown_criteria:
            joined = ", ".join(sorted(unknown_criteria))
            raise ValidationError(f"verification checks reference unknown criteria: {joined}")

        if self.status is TaskStatus.BLOCKED:
            _require_text(self.blocker, "blocker")
        elif self.blocker is not None:
            raise ValidationError("only a blocked task may have a blocker")

    @property
    def criterion_ids(self) -> frozenset[str]:
        """Return the acceptance criterion identifiers for completion checks."""
        return frozenset(criterion.id for criterion in self.acceptance_criteria)


@dataclass(frozen=True, slots=True)
class Project:
    """The aggregate that owns task identity, dependencies, and transitions."""

    objective: str
    tasks: tuple[Task, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.objective, "project objective")
        tasks = tuple(self.tasks)
        object.__setattr__(self, "tasks", tasks)

        if not all(isinstance(task, Task) for task in tasks):
            raise ValidationError("project tasks must be task objects")

        task_ids = [task.id for task in tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValidationError("task ids must be unique within a project")

        known: set[str] = set()
        for task in tasks:
            unknown = set(task.dependencies) - known
            if unknown:
                joined = ", ".join(sorted(unknown))
                raise ValidationError(
                    f"task {task.id!r} depends on tasks not defined earlier: {joined}"
                )
            known.add(task.id)

    def task(self, task_id: str) -> Task:
        """Return a task by identifier."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise UnknownTaskError(task_id)

    def add_task(self, task: Task) -> Project:
        """Return a project with a new, dependency-valid task."""
        if any(existing.id == task.id for existing in self.tasks):
            raise DuplicateTaskError(task.id)
        return replace(self, tasks=(*self.tasks, task))

    def available_tasks(self) -> tuple[Task, ...]:
        """Return planned tasks whose dependencies have completed."""
        completed = {
            task.id for task in self.tasks if task.status is TaskStatus.COMPLETED
        }
        return tuple(
            task
            for task in self.tasks
            if task.status is TaskStatus.PLANNED
            and set(task.dependencies).issubset(completed)
        )

    def start_task(self, task_id: str) -> Project:
        """Start a planned task after all dependencies complete."""
        task = self.task(task_id)
        self._require_status(task, TaskStatus.PLANNED, TaskStatus.ACTIVE)
        incomplete = tuple(
            dependency
            for dependency in task.dependencies
            if self.task(dependency).status is not TaskStatus.COMPLETED
        )
        if incomplete:
            raise UnmetDependenciesError(task.id, incomplete)
        return self._replace_task(replace(task, status=TaskStatus.ACTIVE))

    def add_check(self, task_id: str, check: VerificationCheck) -> Project:
        """Add a verification check while a task is still planned."""
        task = self.task(task_id)
        if task.status is not TaskStatus.PLANNED:
            raise TaskConfigurationError(
                f"checks can only be added to planned tasks; {task.id!r} is {task.status}"
            )
        if any(existing.id == check.id for existing in task.checks):
            raise TaskConfigurationError(
                f"check {check.id!r} already exists on task {task.id!r}"
            )
        return self._replace_task(replace(task, checks=(*task.checks, check)))

    def block_task(self, task_id: str, reason: str) -> Project:
        """Pause active work with an explicit blocker."""
        task = self.task(task_id)
        self._require_status(task, TaskStatus.ACTIVE, TaskStatus.BLOCKED)
        _require_text(reason, "blocker")
        return self._replace_task(
            replace(task, status=TaskStatus.BLOCKED, blocker=reason)
        )

    def resume_task(self, task_id: str) -> Project:
        """Resume a blocked task after its blocker is addressed."""
        task = self.task(task_id)
        self._require_status(task, TaskStatus.BLOCKED, TaskStatus.ACTIVE)
        return self._replace_task(
            replace(task, status=TaskStatus.ACTIVE, blocker=None)
        )

    def complete_task(
        self, task_id: str, verified_criteria: Iterable[str]
    ) -> Project:
        """Complete active work when every declared criterion is verified."""
        task = self.task(task_id)
        self._require_status(task, TaskStatus.ACTIVE, TaskStatus.COMPLETED)
        verified = frozenset(verified_criteria)
        missing = task.criterion_ids - verified
        unexpected = verified - task.criterion_ids
        if missing or unexpected:
            raise VerificationMismatchError(
                task.id,
                missing=missing,
                unexpected=unexpected,
            )
        return self._replace_task(replace(task, status=TaskStatus.COMPLETED))

    def _replace_task(self, replacement: Task) -> Project:
        tasks = tuple(
            replacement if task.id == replacement.id else task for task in self.tasks
        )
        return replace(self, tasks=tasks)

    @staticmethod
    def _require_status(task: Task, current: TaskStatus, target: TaskStatus) -> None:
        if task.status is not current:
            raise InvalidTransitionError(task.id, task.status, target)
