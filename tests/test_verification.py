import sys

from vertex_harness.application import VerificationService, WorkflowService
from vertex_harness.domain import AcceptanceCriterion, EvidenceOutcome, TaskStatus


def active_task(tmp_path, command, *, criteria=("AC-1",)):
    service = WorkflowService()
    service.initialize(tmp_path, "Deliver verified behavior")
    service.add_task(
        tmp_path,
        task_id="T-1",
        title="Prove behavior",
        outcome="Behavior is proven",
        acceptance_criteria=(AcceptanceCriterion("AC-1", "The check passes"),),
    )
    service.add_check(
        tmp_path,
        "T-1",
        check_id="check",
        command=command,
        criterion_ids=criteria,
        timeout_seconds=10,
    )
    service.start_task(tmp_path, "T-1")


def test_passing_check_persists_evidence_and_completes_task(tmp_path):
    active_task(tmp_path, (sys.executable, "-c", "print('verified')"))

    result = VerificationService().verify(tmp_path, "T-1")

    assert result.passed is True
    assert result.snapshot.project.task("T-1").status is TaskStatus.COMPLETED
    assert result.receipts[0].outcome is EvidenceOutcome.PASSED
    assert result.receipts[0].stdout == "verified\n"
    assert result.snapshot.evidence == result.receipts


def test_failing_check_records_evidence_and_leaves_task_active(tmp_path):
    active_task(
        tmp_path,
        (sys.executable, "-c", "import sys; print('no'); sys.exit(3)"),
    )

    result = VerificationService().verify(tmp_path, "T-1")

    assert result.passed is False
    assert result.snapshot.project.task("T-1").status is TaskStatus.ACTIVE
    assert result.receipts[0].outcome is EvidenceOutcome.FAILED
    assert result.receipts[0].exit_code == 3


def test_source_mutating_check_cannot_complete_task(tmp_path):
    active_task(
        tmp_path,
        (sys.executable, "-c", "from pathlib import Path; Path('changed.py').write_text('x')"),
    )

    result = VerificationService().verify(tmp_path, "T-1")

    assert result.passed is False
    assert result.receipts[0].outcome is EvidenceOutcome.SOURCE_CHANGED
    assert result.receipts[0].source_before != result.receipts[0].source_after
    assert result.snapshot.project.task("T-1").status is TaskStatus.ACTIVE
