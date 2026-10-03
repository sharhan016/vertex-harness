"""Read-only installation and repository diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from vertex_harness import __version__
from vertex_harness.intelligence import IndexFormatError, IndexNotFoundError, IndexStore
from vertex_harness.state import ProjectStore, StateError, StateNotFoundError
from vertex_harness.workspace import source_fingerprint


def diagnose(repository: Path | str) -> dict[str, Any]:
    root = Path(repository).resolve()
    checks: list[dict[str, str]] = []
    checks.append(
        {
            "name": "python",
            "status": "ok" if sys.version_info >= (3, 11) else "error",
            "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }
    )
    checks.append(
        {
            "name": "repository",
            "status": "ok" if root.is_dir() else "error",
            "detail": str(root),
        }
    )
    if root.is_dir():
        checks.append(_state_check(root))
        checks.append(_index_check(root))
    severity = {"ok": 0, "warning": 1, "error": 2}
    overall = max(checks, key=lambda check: severity[check["status"]])["status"]
    return {"version": __version__, "overall": overall, "checks": checks}


def _state_check(repository: Path) -> dict[str, str]:
    try:
        snapshot = ProjectStore(repository).load()
    except StateNotFoundError:
        return {
            "name": "state",
            "status": "warning",
            "detail": "not initialized; run vertex init",
        }
    except StateError as error:
        return {"name": "state", "status": "error", "detail": str(error)}
    return {
        "name": "state",
        "status": "ok",
        "detail": f"revision {snapshot.revision}, {len(snapshot.project.tasks)} tasks",
    }


def _index_check(repository: Path) -> dict[str, str]:
    try:
        index = IndexStore(repository).load()
    except IndexNotFoundError:
        return {
            "name": "index",
            "status": "warning",
            "detail": "not generated; run vertex index",
        }
    except IndexFormatError as error:
        return {"name": "index", "status": "error", "detail": str(error)}
    stale = source_fingerprint(repository) != index.source_hash
    return {
        "name": "index",
        "status": "warning" if stale else "ok",
        "detail": f"{len(index.files)} Python files; {'stale' if stale else 'current'}",
    }
