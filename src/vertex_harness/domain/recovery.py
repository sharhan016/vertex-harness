"""Durable records used to resume work after interruption."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vertex_harness.domain.errors import ValidationError


def _text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be non-empty text")


class AttemptStatus(StrEnum):
    RUNNING = "running"
    FINISHED = "finished"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class VerificationAttempt:
    """Lifecycle record for one verification process."""

    id: str
    task_id: str
    check_id: str
    command: tuple[str, ...]
    started_at: str
    status: AttemptStatus = AttemptStatus.RUNNING
    pid: int | None = None
    finished_at: str | None = None
    receipt_id: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        command = tuple(self.command)
        object.__setattr__(self, "command", command)
        for name, value in {
            "attempt id": self.id,
            "task id": self.task_id,
            "check id": self.check_id,
            "started_at": self.started_at,
        }.items():
            _text(value, name)
        if not command or not all(
            isinstance(argument, str) and argument for argument in command
        ):
            raise ValidationError("attempt command must contain non-empty arguments")
        if not isinstance(self.status, AttemptStatus):
            raise ValidationError("attempt status must be an AttemptStatus value")
        if self.pid is not None and (
            not isinstance(self.pid, int) or isinstance(self.pid, bool) or self.pid <= 0
        ):
            raise ValidationError("attempt pid must be a positive integer or null")

        if self.status is AttemptStatus.RUNNING:
            if any(value is not None for value in (self.finished_at, self.receipt_id, self.note)):
                raise ValidationError("running attempt cannot have completion fields")
        elif self.status is AttemptStatus.FINISHED:
            _text(self.finished_at, "attempt finished_at")
            _text(self.receipt_id, "attempt receipt id")
            if self.note is not None:
                raise ValidationError("finished attempt cannot have an interruption note")
        else:
            _text(self.finished_at, "attempt finished_at")
            _text(self.note, "attempt interruption note")
            if self.receipt_id is not None:
                raise ValidationError("interrupted attempt cannot have a receipt")


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A concise handoff note bound to a state revision and optional task."""

    id: str
    created_at: str
    revision: int
    note: str
    task_id: str | None = None

    def __post_init__(self) -> None:
        _text(self.id, "checkpoint id")
        _text(self.created_at, "checkpoint created_at")
        _text(self.note, "checkpoint note")
        if self.task_id is not None:
            _text(self.task_id, "checkpoint task id")
        if (
            not isinstance(self.revision, int)
            or isinstance(self.revision, bool)
            or self.revision < 0
        ):
            raise ValidationError("checkpoint revision must be a non-negative integer")
