"""Execute project-defined checks and bind their evidence to task completion."""

from __future__ import annotations

import hashlib
import os
import signal
import stat
import subprocess
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vertex_harness.domain import (
    AttemptStatus,
    EvidenceOutcome,
    EvidenceReceipt,
    InvalidTransitionError,
    TaskStatus,
    VerificationCheck,
    VerificationAttempt,
)
from vertex_harness.state import ProjectStore, StateSnapshot

OUTPUT_LIMIT = 16_384


class VerificationError(RuntimeError):
    """Raised when a task does not have a runnable verification contract."""


@dataclass(frozen=True, slots=True)
class VerificationResult:
    snapshot: StateSnapshot
    receipts: tuple[EvidenceReceipt, ...]
    passed: bool


class VerificationService:
    """Run all checks for one active task and persist bounded evidence."""

    def verify(self, repository: Path | str, task_id: str) -> VerificationResult:
        root = Path(repository)
        store = ProjectStore(root)
        initial = store.load()
        task = initial.project.task(task_id)
        if task.status is not TaskStatus.ACTIVE:
            raise InvalidTransitionError(task.id, task.status, TaskStatus.COMPLETED)
        if not task.checks:
            raise VerificationError(f"task {task.id!r} has no verification checks")

        covered = {
            criterion_id
            for check in task.checks
            for criterion_id in check.criterion_ids
        }
        missing = task.criterion_ids - covered
        if missing:
            joined = ", ".join(sorted(missing))
            raise VerificationError(
                f"task {task.id!r} has criteria without checks: {joined}"
            )

        current = initial
        collected: list[EvidenceReceipt] = []
        for check in task.checks:
            receipt, current = self._run_check(
                root, store, current, task.id, check
            )
            collected.append(receipt)
        receipts = tuple(collected)
        passed = all(receipt.passed for receipt in receipts)
        verified = {
            criterion_id
            for receipt in receipts
            if receipt.passed
            for criterion_id in receipt.criterion_ids
        }

        if passed:
            current = store.update(
                lambda project: project.complete_task(task.id, verified),
                expected_revision=current.revision,
            )
        return VerificationResult(snapshot=current, receipts=receipts, passed=passed)

    def _run_check(
        self,
        repository: Path,
        store: ProjectStore,
        snapshot: StateSnapshot,
        task_id: str,
        check: VerificationCheck,
    ) -> tuple[EvidenceReceipt, StateSnapshot]:
        source_before = source_fingerprint(repository)
        started_at = _now()
        attempt = VerificationAttempt(
            id=f"AT-{uuid4().hex}",
            task_id=task_id,
            check_id=check.id,
            command=check.command,
            started_at=started_at,
        )
        current = store.transaction(
            lambda state: replace(state, attempts=(*state.attempts, attempt)),
            expected_revision=snapshot.revision,
        )
        exit_code: int | None = None
        stdout = ""
        stderr = ""
        outcome = EvidenceOutcome.FAILED
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                list(check.command),
                cwd=repository,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=os.name == "posix",
            )
            running = replace(attempt, pid=process.pid)
            try:
                current = store.transaction(
                    lambda state: replace(
                        state,
                        attempts=_replace_attempt(state.attempts, running),
                    ),
                    expected_revision=current.revision,
                )
            except BaseException:
                _terminate(process)
                raise

            try:
                stdout, stderr = process.communicate(timeout=check.timeout_seconds)
            except subprocess.TimeoutExpired:
                _terminate(process)
                stdout, stderr = process.communicate()
                outcome = EvidenceOutcome.TIMED_OUT
            exit_code = process.returncode
            if exit_code == 0:
                outcome = EvidenceOutcome.PASSED
        except OSError as error:
            stderr = str(error)
        finished_at = _now()
        source_after = source_fingerprint(repository)
        if outcome is EvidenceOutcome.PASSED and source_after != source_before:
            outcome = EvidenceOutcome.SOURCE_CHANGED

        receipt = EvidenceReceipt(
            id=f"EV-{uuid4().hex}",
            task_id=task_id,
            check_id=check.id,
            command=check.command,
            criterion_ids=check.criterion_ids,
            started_at=started_at,
            finished_at=finished_at,
            outcome=outcome,
            exit_code=exit_code,
            stdout=_bounded(stdout),
            stderr=_bounded(stderr),
            source_before=source_before,
            source_after=source_after,
        )
        finished = replace(
            attempt,
            status=AttemptStatus.FINISHED,
            pid=process.pid if process is not None else None,
            finished_at=finished_at,
            receipt_id=receipt.id,
        )
        current = store.transaction(
            lambda state: replace(
                state,
                attempts=_replace_attempt(state.attempts, finished),
                evidence=(*state.evidence, receipt),
            ),
            expected_revision=current.revision,
        )
        return receipt, current


def source_fingerprint(repository: Path | str) -> str:
    """Hash version-controlled and nonignored source, excluding Vertex state."""
    root = Path(repository).resolve()
    paths = _git_paths(root)
    if paths is None:
        paths = _walk_paths(root)

    digest = hashlib.sha256(b"vertex-source-v1\0")
    for relative in sorted(paths, key=lambda path: path.as_posix()):
        if relative.parts and relative.parts[0] == ".vertex":
            continue
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            digest.update(b"missing\0")
            continue
        digest.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"link\0")
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(131_072), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _git_paths(root: Path) -> set[Path] | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return {
        Path(value.decode("utf-8", errors="surrogateescape"))
        for value in completed.stdout.split(b"\0")
        if value
    }


def _walk_paths(root: Path) -> set[Path]:
    excluded = {
        ".git",
        ".vertex",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "reference",
    }
    paths: set[Path] = set()
    for directory, names, files in os.walk(root):
        names[:] = sorted(name for name in names if name not in excluded)
        base = Path(directory)
        for name in sorted(files):
            path = base / name
            paths.add(path.relative_to(root))
    return paths


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _bounded(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= OUTPUT_LIMIT:
        return value
    marker = b"\n... output truncated by Vertex ...\n"
    return (encoded[: OUTPUT_LIMIT - len(marker)] + marker).decode(
        "utf-8", errors="replace"
    )


def _replace_attempt(
    attempts: tuple[VerificationAttempt, ...], replacement: VerificationAttempt
) -> tuple[VerificationAttempt, ...]:
    return tuple(
        replacement if attempt.id == replacement.id else attempt
        for attempt in attempts
    )


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        os.killpg(process.pid, signal.SIGKILL)
    else:
        process.kill()
