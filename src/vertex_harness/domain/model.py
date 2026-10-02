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
class Task:
    """A bounded outcome and the conditions required to finish it."""

    id: str
    title: str
    outcome: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    dependencies: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PLANNED
    blocker: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.id, "task id")
        _require_text(self.title, "task title")
        _require_text(self.outcome, "task outcome")

        criteria = tuple(self.acceptance_criteria)
        dependencies = tuple(self.dependencies)
        object.__setattr__(self, "acceptance_criteria", criteria)
        object.__setattr__(self, "dependencies", dependencies)

        if not criteria:
            raise ValidationError("task must define at least one acceptance criterion")
        if not all(isinstance(criterion, AcceptanceCriterion) for criterion in criteria):
            raise ValidationError("task acceptance criteria must be criterion objects")
        if not isinstance(self.status, TaskStatus):
            raise ValidationError("task status must be a TaskStatus value")
        for dependency in dependencies:
            _require_text(dependency, "dependency id")

        criterion_ids = [criterion.id for criterion in criteria]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValidationError("acceptance criterion ids must be unique within a task")
        if len(dependencies) != len(set(dependencies)):
            raise ValidationError("task dependencies must be unique")
        if self.id in dependencies:
            raise ValidationError("task cannot depend on itself")

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
