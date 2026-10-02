"""Versioned JSON persistence for the Vertex project aggregate."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from vertex_harness.domain import (
    AcceptanceCriterion,
    EvidenceOutcome,
    EvidenceReceipt,
    Project,
    Task,
    TaskStatus,
    ValidationError,
    VerificationCheck,
)
from vertex_harness.state.errors import (
    RevisionConflictError,
    StateAlreadyExistsError,
    StateFormatError,
    StateLockedError,
    StateNotFoundError,
)

SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """A project value paired with its optimistic-concurrency revision."""

    revision: int
    project: Project
    evidence: tuple[EvidenceReceipt, ...] = ()

    def __post_init__(self) -> None:
        evidence = tuple(self.evidence)
        object.__setattr__(self, "evidence", evidence)
        if not isinstance(self.project, Project):
            raise TypeError("state project must be a Project")
        if not all(isinstance(receipt, EvidenceReceipt) for receipt in evidence):
            raise TypeError("state evidence must contain EvidenceReceipt values")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            raise ValueError("state revision must be a non-negative integer")


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
        def update_project(snapshot: StateSnapshot) -> StateSnapshot:
            project = transform(snapshot.project)
            if not isinstance(project, Project):
                raise TypeError("state transform must return a Project")
            return replace(snapshot, project=project)

        return self.transaction(update_project, expected_revision=expected_revision)

    def transaction(
        self,
        transform: Callable[[StateSnapshot], StateSnapshot],
        *,
        expected_revision: int | None = None,
    ) -> StateSnapshot:
        """Atomically transform the full snapshot under the write lock."""
        if not self.directory.is_dir():
            raise StateNotFoundError(f"state not found at {self.path}")
        with self._write_lock():
            current = self.load()
            if expected_revision is not None and current.revision != expected_revision:
                raise RevisionConflictError(expected_revision, current.revision)

            transformed = transform(current)
            if not isinstance(transformed, StateSnapshot):
                raise TypeError("state transaction must return a StateSnapshot")
            updated = replace(transformed, revision=current.revision + 1)
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
        "evidence": [_encode_evidence(receipt) for receipt in snapshot.evidence],
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
                    "checks": [
                        {
                            "id": check.id,
                            "command": list(check.command),
                            "criterion_ids": list(check.criterion_ids),
                            "timeout_seconds": check.timeout_seconds,
                        }
                        for check in task.checks
                    ],
                }
                for task in snapshot.project.tasks
            ],
        },
    }


def _decode_snapshot(raw: object) -> StateSnapshot:
    root = _mapping(raw, "state")
    if "schema_version" not in root:
        raise StateFormatError("state fields are invalid: missing schema_version")
    schema_version = root["schema_version"]
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise StateFormatError("schema version must be an integer")
    if schema_version not in {1, SCHEMA_VERSION}:
        raise StateFormatError(
            f"unsupported schema version {schema_version!r}; expected 1 or {SCHEMA_VERSION}"
        )
    if schema_version == 1:
        _exact_keys(root, {"schema_version", "revision", "project"}, "state")
        evidence_values: list[Any] = []
    else:
        _exact_keys(
            root, {"schema_version", "revision", "project", "evidence"}, "state"
        )
        evidence_values = _list(root["evidence"], "state evidence")

    revision = root["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise StateFormatError("state revision must be a non-negative integer")

    project_data = _mapping(root["project"], "project")
    _exact_keys(project_data, {"objective", "tasks"}, "project")
    objective = _text(project_data["objective"], "project objective")
    task_values = _list(project_data["tasks"], "project tasks")

    try:
        tasks = tuple(
            _decode_task(value, index, schema_version=schema_version)
            for index, value in enumerate(task_values)
        )
        project = Project(objective=objective, tasks=tasks)
        evidence = tuple(
            _decode_evidence(value, index)
            for index, value in enumerate(evidence_values)
        )
    except (ValidationError, ValueError) as error:
        raise StateFormatError(f"stored project violates a domain rule: {error}") from error
    return StateSnapshot(revision=revision, project=project, evidence=evidence)


def _decode_task(raw: object, index: int, *, schema_version: int) -> Task:
    context = f"task at index {index}"
    data = _mapping(raw, context)
    task_fields = {
            "id",
            "title",
            "outcome",
            "acceptance_criteria",
            "dependencies",
            "status",
            "blocker",
    }
    if schema_version >= 2:
        task_fields.add("checks")
    _exact_keys(data, task_fields, context)

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

    checks = ()
    if schema_version >= 2:
        checks = tuple(
            _decode_check(value, check_index, context)
            for check_index, value in enumerate(
                _list(data["checks"], f"{context} checks")
            )
        )

    return Task(
        id=_text(data["id"], f"{context} id"),
        title=_text(data["title"], f"{context} title"),
        outcome=_text(data["outcome"], f"{context} outcome"),
        acceptance_criteria=criteria,
        dependencies=dependencies,
        status=status,
        blocker=blocker,
        checks=checks,
    )


def _decode_check(raw: object, index: int, task_context: str) -> VerificationCheck:
    context = f"check at index {index} in {task_context}"
    data = _mapping(raw, context)
    _exact_keys(
        data,
        {"id", "command", "criterion_ids", "timeout_seconds"},
        context,
    )
    timeout = data["timeout_seconds"]
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise StateFormatError(f"{context} timeout must be an integer")
    return VerificationCheck(
        id=_text(data["id"], f"{context} id"),
        command=tuple(
            _text(value, f"{context} command argument")
            for value in _list(data["command"], f"{context} command")
        ),
        criterion_ids=tuple(
            _text(value, f"{context} criterion id")
            for value in _list(data["criterion_ids"], f"{context} criterion ids")
        ),
        timeout_seconds=timeout,
    )


def _encode_evidence(receipt: EvidenceReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "task_id": receipt.task_id,
        "check_id": receipt.check_id,
        "command": list(receipt.command),
        "criterion_ids": list(receipt.criterion_ids),
        "started_at": receipt.started_at,
        "finished_at": receipt.finished_at,
        "outcome": receipt.outcome.value,
        "exit_code": receipt.exit_code,
        "stdout": receipt.stdout,
        "stderr": receipt.stderr,
        "source_before": receipt.source_before,
        "source_after": receipt.source_after,
    }


def _decode_evidence(raw: object, index: int) -> EvidenceReceipt:
    context = f"evidence at index {index}"
    data = _mapping(raw, context)
    fields = {
        "id",
        "task_id",
        "check_id",
        "command",
        "criterion_ids",
        "started_at",
        "finished_at",
        "outcome",
        "exit_code",
        "stdout",
        "stderr",
        "source_before",
        "source_after",
    }
    _exact_keys(data, fields, context)
    outcome_value = _text(data["outcome"], f"{context} outcome")
    try:
        outcome = EvidenceOutcome(outcome_value)
    except ValueError as error:
        raise StateFormatError(f"{context} has unknown outcome {outcome_value!r}") from error
    exit_code = data["exit_code"]
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool)
    ):
        raise StateFormatError(f"{context} exit code must be an integer or null")
    return EvidenceReceipt(
        id=_text(data["id"], f"{context} id"),
        task_id=_text(data["task_id"], f"{context} task id"),
        check_id=_text(data["check_id"], f"{context} check id"),
        command=tuple(
            _text(value, f"{context} command argument")
            for value in _list(data["command"], f"{context} command")
        ),
        criterion_ids=tuple(
            _text(value, f"{context} criterion id")
            for value in _list(data["criterion_ids"], f"{context} criterion ids")
        ),
        started_at=_text(data["started_at"], f"{context} started_at"),
        finished_at=_text(data["finished_at"], f"{context} finished_at"),
        outcome=outcome,
        exit_code=exit_code,
        stdout=_string(data["stdout"], f"{context} stdout"),
        stderr=_string(data["stderr"], f"{context} stderr"),
        source_before=_text(data["source_before"], f"{context} source_before"),
        source_after=_text(data["source_after"], f"{context} source_after"),
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


def _string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise StateFormatError(f"{context} must be text")
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
