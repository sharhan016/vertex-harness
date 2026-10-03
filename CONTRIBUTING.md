# Contributing to Vertex

Vertex is intentionally built in small, teachable phases. A change should make one
architectural or functional idea easy to understand from its diff and commit.

## Setup

```console
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Before a commit

```console
python -m ruff check .
python -m pytest
python -m compileall -q src tests
python -m build
```

Add focused tests for changed behavior and update an architectural decision when an
invariant, boundary, or compatibility promise changes.

## Commit discipline

- Keep each commit in a working state.
- Describe the outcome of the files in the commit.
- Avoid unrelated cleanup in a functional change.
- Do not add `Co-authored-by` trailers.
- Treat state-schema changes as compatibility migrations with old-reader fixtures.

## Scope boundaries

Vertex state and evidence are coordination records, not a security sandbox. Avoid
changes that imply stronger isolation, authentication, or exactly-once guarantees than
the operating system and repository can provide.
