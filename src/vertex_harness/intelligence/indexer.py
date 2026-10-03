"""Conservative Python AST extraction for repository intelligence."""

from __future__ import annotations

import ast
import tokenize
from datetime import UTC, datetime
from pathlib import Path

from vertex_harness.intelligence.model import (
    ImportEdge,
    IndexIssue,
    RepositoryIndex,
    SourceUnit,
    Symbol,
)
from vertex_harness.workspace import discover_files, source_fingerprint


class IndexingError(RuntimeError):
    """Raised when a stable repository index cannot be produced."""


def build_index(repository: Path | str) -> RepositoryIndex:
    root = Path(repository).resolve()
    if not root.is_dir():
        raise IndexingError(f"repository directory does not exist: {root}")
    before = source_fingerprint(root)
    python_paths = tuple(path for path in discover_files(root) if path.suffix == ".py")
    modules = {_module_name(path): path.as_posix() for path in python_paths}
    files: list[SourceUnit] = []
    issues: list[IndexIssue] = []

    for relative in python_paths:
        try:
            with tokenize.open(root / relative) as source:
                tree = ast.parse(source.read(), filename=relative.as_posix())
        except (OSError, SyntaxError, UnicodeError) as error:
            issues.append(
                IndexIssue(
                    path=relative.as_posix(),
                    message=str(error),
                    line=getattr(error, "lineno", None),
                )
            )
            continue

        module = _module_name(relative)
        imports = tuple(
            _imports(tree, module, relative.name == "__init__.py", modules)
        )
        files.append(
            SourceUnit(
                path=relative.as_posix(),
                module=module,
                symbols=tuple(_symbols(tree)),
                imports=imports,
            )
        )

    after = source_fingerprint(root)
    if after != before:
        raise IndexingError("repository source changed while the index was being built")
    return RepositoryIndex(
        generated_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
        source_hash=after,
        files=tuple(files),
        issues=tuple(issues),
    )


def _module_name(path: Path) -> str:
    parts = list(path.with_suffix("").parts)
    if "src" in parts:
        parts = parts[parts.index("src") + 1 :]
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _symbols(tree: ast.Module) -> list[Symbol]:
    symbols: list[Symbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(
                Symbol(
                    name=node.name,
                    qualified_name=node.name,
                    kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    line=node.lineno,
                )
            )
        elif isinstance(node, ast.ClassDef):
            symbols.append(
                Symbol(node.name, node.name, "class", node.lineno)
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(
                        Symbol(
                            name=child.name,
                            qualified_name=f"{node.name}.{child.name}",
                            kind="async_method"
                            if isinstance(child, ast.AsyncFunctionDef)
                            else "method",
                            line=child.lineno,
                        )
                    )
    return symbols


def _imports(
    tree: ast.Module,
    current_module: str,
    is_package: bool,
    modules: dict[str, str],
) -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(
                    ImportEdge(alias.name, node.lineno, modules.get(alias.name))
                )
        elif isinstance(node, ast.ImportFrom):
            module = _absolute_import(
                node.module or "",
                node.level,
                current_module,
                is_package,
            )
            edges.append(ImportEdge(module, node.lineno, modules.get(module)))
    return edges


def _absolute_import(
    imported: str,
    level: int,
    current_module: str,
    is_package: bool,
) -> str:
    if level == 0:
        return imported
    package = current_module if is_package else current_module.rpartition(".")[0]
    parts = package.split(".") if package else []
    remove = level - 1
    if remove > len(parts):
        return "." * level + imported
    base = parts[: len(parts) - remove] if remove else parts
    return ".".join(part for part in (*base, imported) if part)
