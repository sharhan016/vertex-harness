# 0007: Begin repository intelligence with conservative Python facts

- Status: accepted
- Date: 2026-10-03

## Context

Agents and people need more than text search to estimate change impact, but an
approximate graph becomes dangerous when uncertain edges are presented as facts. The
project is Python-first and does not yet justify parser dependencies or a graph
database.

## Decision

Vertex discovers Git-tracked and nonignored files when Git is available, with a
conservative filesystem fallback. It parses Python through the standard-library AST
and generates `.vertex/index.json` containing:

- file and inferred module identity;
- top-level classes, functions, async functions, and immediate class methods;
- import statements and exact internal module resolutions; and
- retained parse issues with path and line information.

The query API supports symbol search, file definitions, direct dependencies, direct
dependents, and transitive import impact. Results carry the index source hash and a
`stale` flag computed against current source. The index is derived, ignored by Git, and
replaceable atomically.

## Consequences

- A missing result is not proof that a relationship does not exist.
- Dynamic imports, runtime dispatch, nested functions, calls, inheritance, and
  non-Python languages are not indexed yet.
- Module inference treats a `src/` directory as the import root and otherwise uses the
  repository-relative path. Unusual import layouts may remain unresolved.
- Syntax errors do not prevent useful files from being indexed, but they remain visible
  as issues.
- Import impact is advisory static information, not executable verification.
