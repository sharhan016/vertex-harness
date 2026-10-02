"""Versioned JSON persistence for the Vertex project aggregate."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vertex_harness.domain import (
    AcceptanceCriterion,
    Project,
    Task,
    TaskStatus,
    ValidationError,
)
from vertex_harness.state.errors import (
    RevisionConflictError,
    StateAlreadyExistsError,
    StateFormatError,
    StateLockedError,
    StateNotFoundError,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """A project value paired with its optimistic-concurrency revision."""

    revision: int
    project: Project


class ProjectStore:
    """Read and atomically update one repository's Vertex state."""

    def __init__(self, repository: Path | str) -> None:
        self.repository = Path(repository)
        self.directory = self.repository / ".vertex"
        self.path = self.directory / "project.json"
        self.lock_path = self.directory / "write.lock"

    def initialize(self, project: Project) -> StateSnapshot:
        """Create the first state snapshot without replacing existing work."""
        self.directory.mkdir(parents=True, exist_ok=True)
        with self._write_lock():
            if self.path.exists():
                raise StateAlreadyExistsError(f"state already exists at {self.path}")
            snapshot = StateSnapshot(revision=0, project=project)
            self._write(snapshot)
            return snapshot

    def load(self) -> StateSnapshot:
        """Load and validate the current state snapshot."""
        if not self.path.is_file():
            raise StateNotFoundError(f"state not found at {self.path}")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise StateFormatError(f"cannot read valid JSON from {self.path}") from error
        return _decode_snapshot(raw)

    def update(
        self,
        transform: Callable[[Project], Project],
        *,
        expected_revision: int | None = None,
    ) -> StateSnapshot:
        """Apply one transformation while holding the repository write lock."""
        if not self.directory.is_dir():
            raise StateNotFoundError(f"state not found at {self.path}")
        with self._write_lock():
            current = self.load()
            if expected_revision is not None and current.revision != expected_revision:
                raise RevisionConflictError(expected_revision, current.revision)

            project = transform(current.project)
            if not isinstance(project, Project):
                raise TypeError("state transform must return a Project")

            updated = StateSnapshot(revision=current.revision + 1, project=project)
            self._write(updated)
            return updated

    @contextmanager
    def _write_lock(self):
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError as error:
            raise StateLockedError(f"state is locked at {self.lock_path}") from error

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                lock_file.write(f"{os.getpid()}\n")
                lock_file.flush()
                os.fsync(lock_file.fileno())
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def _write(self, snapshot: StateSnapshot) -> None:
        payload = json.dumps(_encode_snapshot(snapshot), indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.directory,
            prefix=".project-",
            suffix=".tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.chmod(0o644)
            os.replace(temporary_path, self.path)
            _sync_directory(self.directory)
        finally:
            temporary_path.unlink(missing_ok=True)


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _encode_snapshot(snapshot: StateSnapshot) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": snapshot.revision,
        "project": {
            "objective": snapshot.project.objective,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "outcome": task.outcome,
                    "acceptance_criteria": [
                        {"id": criterion.id, "description": criterion.description}
                        for criterion in task.acceptance_criteria
                    ],
                    "dependencies": list(task.dependencies),
                    "status": task.status.value,
                    "blocker": task.blocker,
                }
                for task in snapshot.project.tasks
            ],
        },
    }


def _decode_snapshot(raw: object) -> StateSnapshot:
    root = _mapping(raw, "state")
    _exact_keys(root, {"schema_version", "revision", "project"}, "state")

    schema_version = root["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise StateFormatError(
            f"unsupported schema version {schema_version!r}; expected {SCHEMA_VERSION}"
        )

    revision = root["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise StateFormatError("state revision must be a non-negative integer")

    project_data = _mapping(root["project"], "project")
    _exact_keys(project_data, {"objective", "tasks"}, "project")
    objective = _text(project_data["objective"], "project objective")
    task_values = _list(project_data["tasks"], "project tasks")

    try:
        tasks = tuple(_decode_task(value, index) for index, value in enumerate(task_values))
        project = Project(objective=objective, tasks=tasks)
    except (ValidationError, ValueError) as error:
        raise StateFormatError(f"stored project violates a domain rule: {error}") from error
    return StateSnapshot(revision=revision, project=project)


def _decode_task(raw: object, index: int) -> Task:
    context = f"task at index {index}"
    data = _mapping(raw, context)
    _exact_keys(
        data,
        {
            "id",
            "title",
            "outcome",
            "acceptance_criteria",
            "dependencies",
            "status",
            "blocker",
        },
        context,
    )

    criteria_values = _list(data["acceptance_criteria"], f"{context} criteria")
    criteria = tuple(
        _decode_criterion(value, criterion_index, context)
        for criterion_index, value in enumerate(criteria_values)
    )
    dependencies = tuple(
        _text(value, f"{context} dependency")
        for value in _list(data["dependencies"], f"{context} dependencies")
    )
    blocker = data["blocker"]
    if blocker is not None:
        blocker = _text(blocker, f"{context} blocker")

    status_value = _text(data["status"], f"{context} status")
    try:
        status = TaskStatus(status_value)
    except ValueError as error:
        raise StateFormatError(f"{context} has unknown status {status_value!r}") from error

    return Task(
        id=_text(data["id"], f"{context} id"),
        title=_text(data["title"], f"{context} title"),
        outcome=_text(data["outcome"], f"{context} outcome"),
        acceptance_criteria=criteria,
        dependencies=dependencies,
        status=status,
        blocker=blocker,
    )


def _decode_criterion(raw: object, index: int, task_context: str) -> AcceptanceCriterion:
    context = f"criterion at index {index} in {task_context}"
    data = _mapping(raw, context)
    _exact_keys(data, {"id", "description"}, context)
    return AcceptanceCriterion(
        id=_text(data["id"], f"{context} id"),
        description=_text(data["description"], f"{context} description"),
    )


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise StateFormatError(f"{context} must be a JSON object")
    return value


def _list(value: object, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise StateFormatError(f"{context} must be a JSON array")
    return value


def _text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateFormatError(f"{context} must be non-empty text")
    return value


def _exact_keys(data: Mapping[str, Any], expected: set[str], context: str) -> None:
    actual = set(data)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing {', '.join(missing)}")
    if unexpected:
        details.append(f"unexpected {', '.join(unexpected)}")
    raise StateFormatError(f"{context} fields are invalid: {'; '.join(details)}")
