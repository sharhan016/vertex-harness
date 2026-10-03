"""Stable serializable views shared by CLI, MCP, and HTTP adapters."""

from __future__ import annotations

from typing import Any

from vertex_harness.domain import EvidenceReceipt
from vertex_harness.state import StateSnapshot


def snapshot_view(snapshot: StateSnapshot) -> dict[str, Any]:
    available = {task.id for task in snapshot.project.available_tasks()}
    return {
        "revision": snapshot.revision,
        "objective": snapshot.project.objective,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "outcome": task.outcome,
                "status": task.status.value,
                "blocker": task.blocker,
                "dependencies": list(task.dependencies),
                "available": task.id in available,
                "acceptance_criteria": [
                    {"id": criterion.id, "description": criterion.description}
                    for criterion in task.acceptance_criteria
                ],
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
        "evidence_count": len(snapshot.evidence),
        "running_attempts": sum(
            attempt.status.value == "running" for attempt in snapshot.attempts
        ),
        "checkpoint_count": len(snapshot.checkpoints),
    }


def evidence_view(receipt: EvidenceReceipt) -> dict[str, Any]:
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
