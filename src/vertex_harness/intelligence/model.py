"""Data model for the generated Python repository index."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    qualified_name: str
    kind: str
    line: int


@dataclass(frozen=True, slots=True)
class ImportEdge:
    module: str
    line: int
    resolved_path: str | None = None


@dataclass(frozen=True, slots=True)
class SourceUnit:
    path: str
    module: str
    symbols: tuple[Symbol, ...]
    imports: tuple[ImportEdge, ...]


@dataclass(frozen=True, slots=True)
class IndexIssue:
    path: str
    message: str
    line: int | None = None


@dataclass(frozen=True, slots=True)
class RepositoryIndex:
    generated_at: str
    source_hash: str
    files: tuple[SourceUnit, ...]
    issues: tuple[IndexIssue, ...] = ()

    def source(self, path: str) -> SourceUnit | None:
        normalized = path.replace("\\", "/").removeprefix("./")
        return next((unit for unit in self.files if unit.path == normalized), None)
