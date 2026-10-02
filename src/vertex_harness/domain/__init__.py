"""Public domain API for Vertex."""

from vertex_harness.domain.errors import (
    DomainError,
    DuplicateTaskError,
    InvalidTransitionError,
    TaskConfigurationError,
    UnknownTaskError,
    UnmetDependenciesError,
    ValidationError,
    VerificationMismatchError,
)
from vertex_harness.domain.evidence import EvidenceOutcome, EvidenceReceipt
from vertex_harness.domain.model import (
    AcceptanceCriterion,
    Project,
    Task,
    TaskStatus,
    VerificationCheck,
)

__all__ = [
    "AcceptanceCriterion",
    "DomainError",
    "DuplicateTaskError",
    "EvidenceOutcome",
    "EvidenceReceipt",
    "InvalidTransitionError",
    "Project",
    "Task",
    "TaskConfigurationError",
    "TaskStatus",
    "UnknownTaskError",
    "UnmetDependenciesError",
    "ValidationError",
    "VerificationMismatchError",
    "VerificationCheck",
]
