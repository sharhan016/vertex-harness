"""Checkpoint creation and conservative interrupted-work reconciliation."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vertex_harness.domain import (
    AttemptStatus,
    Checkpoint,
    TaskStatus,
    VerificationAttempt,
)
from vertex_harness.state import ProjectStore, StateSnapshot


class RecoveryError(RuntimeError):
    """Raised when recovery cannot safely determine ownership."""


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    snapshot: StateSnapshot
    interrupted_attempt_ids: tuple[str, ...]
    live_attempt_ids: tuple[str, ...]
    stale_lock_removed: bool = False


class CheckpointService:
    """Persist concise handoff notes against the current state revision."""

    def create(
        self,
        repository: Path | str,
        note: str,
        *,
        task_id: str | None = None,
    ) -> tuple[Checkpoint, StateSnapshot]:
        store = ProjectStore(repository)
        current = store.load()
        if task_id is not None:
            current.project.task(task_id)
        checkpoint = Checkpoint(
            id=f"CP-{uuid4().hex}",
            created_at=_now(),
            revision=current.revision,
            task_id=task_id,
            note=note,
        )
        updated = store.transaction(
            lambda snapshot: replace(
                snapshot, checkpoints=(*snapshot.checkpoints, checkpoint)
            ),
            expected_revision=current.revision,
        )
        return checkpoint, updated


class RecoveryService:
    """Reconcile attempts only when their recorded processes are no longer alive."""

    def recover(self, repository: Path | str) -> RecoveryReport:
        store = ProjectStore(repository)
        stale_lock_removed = self._reconcile_lock(store)
        current = store.load()
        running = tuple(
            attempt
            for attempt in current.attempts
            if attempt.status is AttemptStatus.RUNNING
        )
        live = tuple(
            attempt for attempt in running if attempt.pid and _pid_alive(attempt.pid)
        )
        if live:
            return RecoveryReport(
                snapshot=current,
                interrupted_attempt_ids=(),
                live_attempt_ids=tuple(attempt.id for attempt in live),
                stale_lock_removed=stale_lock_removed,
            )
        if not running:
            return RecoveryReport(
                snapshot=current,
                interrupted_attempt_ids=(),
                live_attempt_ids=(),
                stale_lock_removed=stale_lock_removed,
            )

        finished_at = _now()
        interrupted_ids = {attempt.id for attempt in running}
        affected_tasks = {attempt.task_id for attempt in running}

        def reconcile(snapshot: StateSnapshot) -> StateSnapshot:
            attempts = tuple(
                _interrupt(attempt, finished_at)
                if attempt.id in interrupted_ids
                else attempt
                for attempt in snapshot.attempts
            )
            project = snapshot.project
            for task_id in sorted(affected_tasks):
                task = project.task(task_id)
                if task.status is TaskStatus.ACTIVE:
                    project = project.block_task(
                        task_id,
                        "verification was interrupted; inspect side effects before resuming",
                    )
            return replace(snapshot, project=project, attempts=attempts)

        updated = store.transaction(reconcile, expected_revision=current.revision)
        return RecoveryReport(
            snapshot=updated,
            interrupted_attempt_ids=tuple(sorted(interrupted_ids)),
            live_attempt_ids=(),
            stale_lock_removed=stale_lock_removed,
        )

    @staticmethod
    def _reconcile_lock(store: ProjectStore) -> bool:
        if not store.lock_path.exists():
            return False
        try:
            raw = store.lock_path.read_text(encoding="utf-8").strip()
            pid = int(raw)
        except (OSError, UnicodeError, ValueError) as error:
            raise RecoveryError(
                f"cannot determine owner of lock {store.lock_path}"
            ) from error
        if pid <= 0:
            raise RecoveryError(f"lock {store.lock_path} contains an invalid pid")
        if _pid_alive(pid):
            raise RecoveryError(f"state writer process {pid} is still alive")
        store.lock_path.unlink()
        return True


def _interrupt(attempt: VerificationAttempt, finished_at: str) -> VerificationAttempt:
    return replace(
        attempt,
        status=AttemptStatus.INTERRUPTED,
        finished_at=finished_at,
        note="recorded process is no longer running; side effects are unknown",
    )


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")
