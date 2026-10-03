"""Provenance-carrying queries over a generated repository index."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

from vertex_harness.intelligence.model import RepositoryIndex
from vertex_harness.intelligence.store import IndexStore
from vertex_harness.workspace import source_fingerprint


class QueryError(RuntimeError):
    """Raised when a query target or query kind is invalid."""


class QueryService:
    def execute(
        self, repository: Path | str, kind: str, value: str
    ) -> dict[str, Any]:
        root = Path(repository)
        index = IndexStore(root).load()
        handlers = {
            "search": self._search,
            "defines": self._defines,
            "dependencies": self._dependencies,
            "dependents": self._dependents,
            "impact": self._impact,
        }
        try:
            results = handlers[kind](index, value)
        except KeyError as error:
            raise QueryError(f"unknown query kind: {kind}") from error
        return {
            "query": kind,
            "value": value,
            "source_hash": index.source_hash,
            "stale": source_fingerprint(root) != index.source_hash,
            "results": results,
        }

    @staticmethod
    def _search(index: RepositoryIndex, term: str) -> list[dict[str, Any]]:
        needle = term.casefold()
        return [
            {
                "path": unit.path,
                "module": unit.module,
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "kind": symbol.kind,
                "line": symbol.line,
            }
            for unit in index.files
            for symbol in unit.symbols
            if needle in symbol.qualified_name.casefold()
        ]

    @staticmethod
    def _defines(index: RepositoryIndex, path: str) -> list[dict[str, Any]]:
        unit = _source(index, path)
        return [
            {
                "path": unit.path,
                "name": symbol.name,
                "qualified_name": symbol.qualified_name,
                "kind": symbol.kind,
                "line": symbol.line,
            }
            for symbol in unit.symbols
        ]

    @staticmethod
    def _dependencies(index: RepositoryIndex, path: str) -> list[dict[str, Any]]:
        unit = _source(index, path)
        return [
            {
                "path": unit.path,
                "module": edge.module,
                "line": edge.line,
                "resolved_path": edge.resolved_path,
            }
            for edge in unit.imports
        ]

    @staticmethod
    def _dependents(index: RepositoryIndex, path: str) -> list[dict[str, Any]]:
        target = _source(index, path).path
        return [
            {"path": unit.path, "module": edge.module, "line": edge.line}
            for unit in index.files
            for edge in unit.imports
            if edge.resolved_path == target
        ]

    @staticmethod
    def _impact(index: RepositoryIndex, path: str) -> list[dict[str, Any]]:
        target = _source(index, path).path
        reverse: dict[str, set[str]] = {}
        for unit in index.files:
            for edge in unit.imports:
                if edge.resolved_path:
                    reverse.setdefault(edge.resolved_path, set()).add(unit.path)
        queue = deque([(target, 0)])
        seen = {target}
        results: list[dict[str, Any]] = []
        while queue:
            current, distance = queue.popleft()
            for dependent in sorted(reverse.get(current, ())):
                if dependent in seen:
                    continue
                seen.add(dependent)
                results.append({"path": dependent, "distance": distance + 1})
                queue.append((dependent, distance + 1))
        return results


def _source(index: RepositoryIndex, path: str):
    unit = index.source(path)
    if unit is None:
        raise QueryError(f"indexed Python file not found: {path}")
    return unit
