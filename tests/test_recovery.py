import os
from dataclasses import replace

from vertex_harness.application import (
    CheckpointService,
    RecoveryService,
    WorkflowService,
)
from vertex_harness.domain import (
    AcceptanceCriterion,
    AttemptStatus,
    TaskStatus,
    VerificationAttempt,
)
from vertex_harness.state import ProjectStore


def initialized_active_project(tmp_path):
    service = WorkflowService()
    service.initialize(tmp_path, "Recover safely")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Run work",
        outcome="Work is reconciled",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "Work is checked"),),
    )
    service.start_task(tmp_path, "T-1")


def running_attempt(pid):
    return VerificationAttempt(
        id="AT-1",
        task_id="T-1",
        check_id="check",
        command=("python", "-c", "pass"),
        started_at="2026-10-03T00:00:00+00:00",
        pid=pid,
    )


def test_recovery_marks_dead_attempt_interrupted_and_blocks_task(tmp_path):
    initialized_active_project(tmp_path)
    store = ProjectStore(tmp_path)
    store.transaction(
        lambda snapshot: replace(snapshot, attempts=(running_attempt(99_999_999),))
    )

    report = RecoveryService().recover(tmp_path)

    assert report.interrupted_attempt_ids == ("AT-1",)
    assert report.snapshot.attempts[0].status is AttemptStatus.INTERRUPTED
    assert report.snapshot.project.task("T-1").status is TaskStatus.BLOCKED
    assert "inspect side effects" in report.snapshot.project.task("T-1").blocker


def test_recovery_refuses_to_reconcile_a_live_attempt(tmp_path):
    initialized_active_project(tmp_path)
    store = ProjectStore(tmp_path)
    original = store.transaction(
        lambda snapshot: replace(snapshot, attempts=(running_attempt(os.getpid()),))
    )

    report = RecoveryService().recover(tmp_path)

    assert report.live_attempt_ids == ("AT-1",)
    assert report.snapshot == original
    assert store.load().project.task("T-1").status is TaskStatus.ACTIVE


def test_recovery_removes_a_lock_owned_by_a_dead_process(tmp_path):
    initialized_active_project(tmp_path)
    store = ProjectStore(tmp_path)
    store.lock_path.write_text("99999999\n", encoding="utf-8")

    report = RecoveryService().recover(tmp_path)

    assert report.stale_lock_removed is True
    assert not store.lock_path.exists()


def test_checkpoint_records_handoff_against_current_revision(tmp_path):
    initialized_active_project(tmp_path)
    before = ProjectStore(tmp_path).load()

    checkpoint, after = CheckpointService().create(
        tmp_path,
        "Implementation paused after reproducing the failure",
        task_id="T-1",
    )

    assert checkpoint.revision == before.revision
    assert checkpoint.task_id == "T-1"
    assert after.revision == before.revision + 1
    assert after.checkpoints == (checkpoint,)
