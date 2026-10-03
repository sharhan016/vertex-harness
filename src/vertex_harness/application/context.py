"""Bounded, task-oriented context packets for coding agents."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vertex_harness.application.views import evidence_view
from vertex_harness.domain import Task, TaskStatus
from vertex_harness.intelligence import IndexNotFoundError, IndexStore
from vertex_harness.state import ProjectStore
from vertex_harness.workspace import source_fingerprint


class ContextBudgetError(RuntimeError):
    """Raised when required task context cannot fit the requested budget."""


class ContextService:
    def build(
        self,
        repository: Path | str,
        *,
        task_id: str | None = None,
        max_bytes: int = 8_000,
    ) -> dict[str, Any]:
        if not 1_024 <= max_bytes <= 65_536:
            raise ContextBudgetError("context budget must be between 1024 and 65536 bytes")
        root = Path(repository)
        snapshot = ProjectStore(root).load()
        task = (
            snapshot.project.task(task_id)
            if task_id is not None
            else _select_task(snapshot.project.tasks, snapshot.project.available_tasks())
        )
        packet: dict[str, Any] = {
            "objective": snapshot.project.objective,
            "revision": snapshot.revision,
            "source_hash": source_fingerprint(root),
            "task": _task_context(task) if task else None,
            "next_action": _next_action(task),
            "task_summary": [
                {"id": value.id, "title": value.title, "status": value.status.value}
                for value in snapshot.project.tasks
            ],
            "evidence": [],
            "checkpoints": [],
            "index": _index_context(root),
            "omitted": {"evidence": 0, "checkpoints": 0},
            "fingerprint": "0" * 64,
            "bytes": 0,
        }
        if _size(packet) > max_bytes:
            raise ContextBudgetError(
                f"required context needs {_size(packet)} bytes; budget is {max_bytes}"
            )

        evidence = [
            evidence_view(receipt)
            for receipt in reversed(snapshot.evidence)
            if task is None or receipt.task_id == task.id
        ]
        checkpoints = [
            {
                "id": checkpoint.id,
                "created_at": checkpoint.created_at,
                "revision": checkpoint.revision,
                "task_id": checkpoint.task_id,
                "note": checkpoint.note,
            }
            for checkpoint in reversed(snapshot.checkpoints)
            if task is None or checkpoint.task_id in {None, task.id}
        ]
        _include_bounded(packet, "evidence", evidence, max_bytes - 8)
        _include_bounded(packet, "checkpoints", checkpoints, max_bytes - 8)
        packet["omitted"]["evidence"] = len(evidence) - len(packet["evidence"])
        packet["omitted"]["checkpoints"] = len(checkpoints) - len(packet["checkpoints"])

        canonical = {**packet, "fingerprint": "", "bytes": 0}
        content = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        packet["fingerprint"] = hashlib.sha256(content).hexdigest()
        packet["bytes"] = _size(packet)
        packet["bytes"] = _size(packet)
        if packet["bytes"] > max_bytes:
            raise ContextBudgetError(
                f"context metadata exceeded the {max_bytes}-byte budget"
            )
        return packet


def _select_task(tasks: tuple[Task, ...], available: tuple[Task, ...]) -> Task | None:
    active = next((task for task in tasks if task.status is TaskStatus.ACTIVE), None)
    if active:
        return active
    blocked = next((task for task in tasks if task.status is TaskStatus.BLOCKED), None)
    if blocked:
        return blocked
    return available[0] if available else None


def _task_context(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "outcome": task.outcome,
        "status": task.status.value,
        "blocker": task.blocker,
        "dependencies": list(task.dependencies),
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


def _next_action(task: Task | None) -> str:
    if task is None:
        return "Add the next bounded task or confirm that the project is complete."
    if task.status is TaskStatus.PLANNED:
        return f"Start available task {task.id}."
    if task.status is TaskStatus.BLOCKED:
        return f"Resolve and inspect the blocker for {task.id}, then resume explicitly."
    if task.status is TaskStatus.ACTIVE and not task.checks:
        return f"Add checks covering every acceptance criterion for {task.id}."
    if task.status is TaskStatus.ACTIVE:
        return f"Implement {task.id}, then run its verification checks."
    return "Select the next available task."


def _index_context(repository: Path) -> dict[str, Any] | None:
    try:
        index = IndexStore(repository).load()
    except IndexNotFoundError:
        return None
    return {
        "generated_at": index.generated_at,
        "source_hash": index.source_hash,
        "stale": source_fingerprint(repository) != index.source_hash,
        "python_files": len(index.files),
        "issues": len(index.issues),
    }


def _include_bounded(
    packet: dict[str, Any], key: str, values: list[dict[str, Any]], max_bytes: int
) -> None:
    for value in values:
        packet[key].append(value)
        if _size(packet) > max_bytes:
            packet[key].pop()
            break


def _size(value: object) -> int:
    return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
