"""Atomic storage for the generated repository index."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from vertex_harness.intelligence.indexer import build_index
from vertex_harness.intelligence.model import (
    ImportEdge,
    IndexIssue,
    RepositoryIndex,
    SourceUnit,
    Symbol,
)

INDEX_VERSION = 1


class IndexNotFoundError(RuntimeError):
    """Raised when repository intelligence has not been generated."""


class IndexFormatError(RuntimeError):
    """Raised when a generated index is unreadable or incompatible."""


class IndexStore:
    def __init__(self, repository: Path | str) -> None:
        self.repository = Path(repository)
        self.directory = self.repository / ".vertex"
        self.path = self.directory / "index.json"

    def rebuild(self) -> RepositoryIndex:
        index = build_index(self.repository)
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(_encode(index), indent=2, sort_keys=True) + "\n"
        descriptor, name = tempfile.mkstemp(
            dir=self.directory, prefix=".index-", suffix=".tmp", text=True
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            temporary.chmod(0o644)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return index

    def load(self) -> RepositoryIndex:
        if not self.path.is_file():
            raise IndexNotFoundError(
                f"repository index not found at {self.path}; run 'vertex index'"
            )
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return _decode(raw)
        except (
            KeyError,
            OSError,
            TypeError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise IndexFormatError(f"invalid repository index at {self.path}") from error


def _encode(index: RepositoryIndex) -> dict[str, Any]:
    return {
        "index_version": INDEX_VERSION,
        "generated_at": index.generated_at,
        "source_hash": index.source_hash,
        "files": [
            {
                "path": unit.path,
                "module": unit.module,
                "symbols": [
                    {
                        "name": symbol.name,
                        "qualified_name": symbol.qualified_name,
                        "kind": symbol.kind,
                        "line": symbol.line,
                    }
                    for symbol in unit.symbols
                ],
                "imports": [
                    {
                        "module": edge.module,
                        "line": edge.line,
                        "resolved_path": edge.resolved_path,
                    }
                    for edge in unit.imports
                ],
            }
            for unit in index.files
        ],
        "issues": [
            {"path": issue.path, "message": issue.message, "line": issue.line}
            for issue in index.issues
        ],
    }


def _decode(raw: object) -> RepositoryIndex:
    if not isinstance(raw, dict) or raw.get("index_version") != INDEX_VERSION:
        raise ValueError("unsupported index version")
    return RepositoryIndex(
        generated_at=str(raw["generated_at"]),
        source_hash=str(raw["source_hash"]),
        files=tuple(_decode_unit(value) for value in raw["files"]),
        issues=tuple(
            IndexIssue(
                path=str(value["path"]),
                message=str(value["message"]),
                line=value["line"],
            )
            for value in raw["issues"]
        ),
    )


def _decode_unit(value: dict[str, Any]) -> SourceUnit:
    return SourceUnit(
        path=str(value["path"]),
        module=str(value["module"]),
        symbols=tuple(
            Symbol(
                name=str(symbol["name"]),
                qualified_name=str(symbol["qualified_name"]),
                kind=str(symbol["kind"]),
                line=int(symbol["line"]),
            )
            for symbol in value["symbols"]
        ),
        imports=tuple(
            ImportEdge(
                module=str(edge["module"]),
                line=int(edge["line"]),
                resolved_path=str(edge["resolved_path"])
                if edge["resolved_path"] is not None
                else None,
            )
            for edge in value["imports"]
        ),
    )
