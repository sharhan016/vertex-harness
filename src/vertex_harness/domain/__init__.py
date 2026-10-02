"""Public domain API for Vertex."""

from vertex_harness.domain.errors import (
    DomainError,
    DuplicateTaskError,
    InvalidTransitionError,
    UnknownTaskError,
    UnmetDependenciesError,
    ValidationError,
    VerificationMismatchError,
)
from vertex_harness.domain.model import AcceptanceCriterion, Project, Task, TaskStatus

__all__ = [
    "AcceptanceCriterion",
    "DomainError",
    "DuplicateTaskError",
    "InvalidTransitionError",
    "Project",
    "Task",
    "TaskStatus",
    "UnknownTaskError",
    "UnmetDependenciesError",
    "ValidationError",
    "VerificationMismatchError",
]
