"""Immutable records produced by executable verification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vertex_harness.domain.errors import ValidationError


class EvidenceOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    SOURCE_CHANGED = "source_changed"


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    """The bounded, attributable result of one verification command."""

    id: str
    task_id: str
    check_id: str
    command: tuple[str, ...]
    criterion_ids: tuple[str, ...]
    started_at: str
    finished_at: str
    outcome: EvidenceOutcome
    exit_code: int | None
    stdout: str
    stderr: str
    source_before: str
    source_after: str

    def __post_init__(self) -> None:
        command = tuple(self.command)
        criterion_ids = tuple(self.criterion_ids)
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "criterion_ids", criterion_ids)
        text_fields = {
            "evidence id": self.id,
            "task id": self.task_id,
            "check id": self.check_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "source_before": self.source_before,
            "source_after": self.source_after,
        }
        for name, value in text_fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{name} must be non-empty text")
        if not isinstance(self.outcome, EvidenceOutcome):
            raise ValidationError("evidence outcome must be an EvidenceOutcome value")
        if not command or not all(
            isinstance(value, str) and value for value in command
        ):
            raise ValidationError("evidence command must contain non-empty arguments")
        if not criterion_ids or not all(
            isinstance(value, str) and value for value in criterion_ids
        ):
            raise ValidationError("evidence must name covered criteria")
        if self.exit_code is not None and (
            not isinstance(self.exit_code, int) or isinstance(self.exit_code, bool)
        ):
            raise ValidationError("evidence exit code must be an integer or null")
        if not isinstance(self.stdout, str) or not isinstance(self.stderr, str):
            raise ValidationError("evidence output must be text")

    @property
    def passed(self) -> bool:
        return self.outcome is EvidenceOutcome.PASSED
