"""Errors raised when a Vertex domain rule is violated."""

from __future__ import annotations

from collections.abc import Iterable


class DomainError(ValueError):
    """Base class for expected domain-rule failures."""


class ValidationError(DomainError):
    """Raised when a domain object is internally inconsistent."""


class DuplicateTaskError(DomainError):
    """Raised when two tasks use the same identifier."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"task {task_id!r} already exists")
        self.task_id = task_id


class TaskConfigurationError(DomainError):
    """Raised when a task's verification contract cannot be changed safely."""


class UnknownTaskError(DomainError):
    """Raised when a requested task does not exist."""

    def __init__(self, task_id: str) -> None:
        super().__init__(f"task {task_id!r} does not exist")
        self.task_id = task_id


class InvalidTransitionError(DomainError):
    """Raised when a task cannot move between the requested states."""

    def __init__(self, task_id: str, current: str, target: str) -> None:
        super().__init__(f"task {task_id!r} cannot move from {current!r} to {target!r}")
        self.task_id = task_id
        self.current = current
        self.target = target


class UnmetDependenciesError(DomainError):
    """Raised when a task is started before its prerequisites finish."""

    def __init__(self, task_id: str, dependencies: Iterable[str]) -> None:
        self.task_id = task_id
        self.dependencies = tuple(dependencies)
        joined = ", ".join(self.dependencies)
        super().__init__(f"task {task_id!r} has incomplete dependencies: {joined}")


class VerificationMismatchError(DomainError):
    """Raised when completion does not account for every acceptance criterion."""

    def __init__(
        self,
        task_id: str,
        *,
        missing: Iterable[str],
        unexpected: Iterable[str],
    ) -> None:
        self.task_id = task_id
        self.missing = tuple(sorted(missing))
        self.unexpected = tuple(sorted(unexpected))

        details: list[str] = []
        if self.missing:
            details.append(f"missing: {', '.join(self.missing)}")
        if self.unexpected:
            details.append(f"unexpected: {', '.join(self.unexpected)}")
        super().__init__(f"task {task_id!r} verification mismatch ({'; '.join(details)})")
