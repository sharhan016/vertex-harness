"""Command-line entry point for Vertex."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vertex_harness import __version__
from vertex_harness.application import WorkflowError, WorkflowService
from vertex_harness.domain import AcceptanceCriterion, DomainError
from vertex_harness.state import StateError, StateSnapshot


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level command parser."""
    parser = argparse.ArgumentParser(
        prog="vertex",
        description="Coordinate verifiable, recoverable software work.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command")

    initialize = commands.add_parser("init", help="initialize Vertex state")
    _repository_argument(initialize)
    initialize.add_argument("--objective", required=True, help="project outcome")
    initialize.set_defaults(handler=_initialize)

    status = commands.add_parser("status", help="show project and task state")
    _repository_argument(status)
    status.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    status.set_defaults(handler=_status)

    task = commands.add_parser("task", help="manage project tasks")
    task_commands = task.add_subparsers(dest="task_command")

    add = task_commands.add_parser("add", help="add a planned task")
    _repository_argument(add)
    add.add_argument("--id", required=True, dest="task_id")
    add.add_argument("--title", required=True)
    add.add_argument("--outcome", required=True)
    add.add_argument(
        "--criterion",
        required=True,
        action="append",
        type=_criterion,
        dest="criteria",
        metavar="ID=DESCRIPTION",
    )
    add.add_argument("--depends", action="append", default=[], metavar="TASK_ID")
    add.set_defaults(handler=_add_task)

    start = task_commands.add_parser("start", help="start an available task")
    _repository_argument(start)
    start.add_argument("task_id")
    start.set_defaults(handler=_start_task)

    block = task_commands.add_parser("block", help="block an active task")
    _repository_argument(block)
    block.add_argument("task_id")
    block.add_argument("--reason", required=True)
    block.set_defaults(handler=_block_task)

    resume = task_commands.add_parser("resume", help="resume a blocked task")
    _repository_argument(resume)
    resume.add_argument("task_id")
    resume.set_defaults(handler=_resume_task)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Vertex command-line interface."""
    parser = build_parser()
    arguments = parser.parse_args(argv)
    handler = getattr(arguments, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    try:
        return handler(arguments)
    except (DomainError, StateError, WorkflowError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "repository",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="repository directory (default: current directory)",
    )


def _criterion(value: str) -> AcceptanceCriterion:
    identifier, separator, description = value.partition("=")
    if not separator or not identifier.strip() or not description.strip():
        raise argparse.ArgumentTypeError("criterion must use ID=DESCRIPTION")
    return AcceptanceCriterion(identifier, description)


def _initialize(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().initialize(arguments.repository, arguments.objective)
    print(f"initialized Vertex at {arguments.repository} (revision {snapshot.revision})")
    return 0


def _status(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().status(arguments.repository)
    if arguments.json:
        print(json.dumps(_snapshot_view(snapshot), sort_keys=True))
    else:
        _print_status(snapshot)
    return 0


def _add_task(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().add_task(
        arguments.repository,
        task_id=arguments.task_id,
        title=arguments.title,
        outcome=arguments.outcome,
        acceptance_criteria=arguments.criteria,
        dependencies=arguments.depends,
    )
    print(f"added task {arguments.task_id} (revision {snapshot.revision})")
    return 0


def _start_task(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().start_task(arguments.repository, arguments.task_id)
    print(f"started task {arguments.task_id} (revision {snapshot.revision})")
    return 0


def _block_task(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().block_task(
        arguments.repository, arguments.task_id, arguments.reason
    )
    print(f"blocked task {arguments.task_id} (revision {snapshot.revision})")
    return 0


def _resume_task(arguments: argparse.Namespace) -> int:
    snapshot = WorkflowService().resume_task(arguments.repository, arguments.task_id)
    print(f"resumed task {arguments.task_id} (revision {snapshot.revision})")
    return 0


def _snapshot_view(snapshot: StateSnapshot) -> dict[str, Any]:
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
            }
            for task in snapshot.project.tasks
        ],
    }


def _print_status(snapshot: StateSnapshot) -> None:
    view = _snapshot_view(snapshot)
    print(f"Objective: {view['objective']}")
    print(f"Revision: {view['revision']}")
    tasks = view["tasks"]
    if not tasks:
        print("Tasks: none")
        return
    print("Tasks:")
    for task in tasks:
        availability = " · available" if task["available"] else ""
        blocker = f" · blocker: {task['blocker']}" if task["blocker"] else ""
        print(f"  {task['id']} [{task['status']}]{availability}{blocker} — {task['title']}")
