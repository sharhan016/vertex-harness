"""Application services that connect user intent to domain and state rules."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from vertex_harness.domain import AcceptanceCriterion, Project, Task
from vertex_harness.state import ProjectStore, StateSnapshot


class WorkflowError(RuntimeError):
    """Raised when a workflow request cannot be applied to a repository."""


class WorkflowService:
    """Coordinate task lifecycle operations through the repository store."""

    def initialize(self, repository: Path | str, objective: str) -> StateSnapshot:
        root = Path(repository)
        if not root.is_dir():
            raise WorkflowError(f"repository directory does not exist: {root}")
        return ProjectStore(root).initialize(Project(objective=objective))

    def status(self, repository: Path | str) -> StateSnapshot:
        return ProjectStore(repository).load()

    def add_task(
        self,
        repository: Path | str,
        *,
        task_id: str,
        title: str,
        outcome: str,
        acceptance_criteria: Iterable[AcceptanceCriterion],
        dependencies: Iterable[str] = (),
    ) -> StateSnapshot:
        task = Task(
            id=task_id,
            title=title,
            outcome=outcome,
            acceptance_criteria=tuple(acceptance_criteria),
            dependencies=tuple(dependencies),
        )
        return ProjectStore(repository).update(
            lambda project: project.add_task(task)
        )

    def start_task(self, repository: Path | str, task_id: str) -> StateSnapshot:
        return ProjectStore(repository).update(
            lambda project: project.start_task(task_id)
        )

    def block_task(
        self, repository: Path | str, task_id: str, reason: str
    ) -> StateSnapshot:
        return ProjectStore(repository).update(
            lambda project: project.block_task(task_id, reason)
        )

    def resume_task(self, repository: Path | str, task_id: str) -> StateSnapshot:
        return ProjectStore(repository).update(
            lambda project: project.resume_task(task_id)
        )
