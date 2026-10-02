# Vertex Harness

Vertex is a Python-first toolkit for making long-running software work understandable,
verifiable, and recoverable. It is being built in small, working phases so the source
and Git history explain both the design and its evolution.

The current implementation provides the project foundation, a dependency-free core
model, guarded repository-local JSON state, CLI-driven task workflows, and executable
verification with durable evidence.

## Requirements

- Python 3.11 or newer

## Development setup

Create a virtual environment and install the project with its development tools:

```console
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the checks:

```console
python -m pytest
python -m compileall -q src tests
```

Try the CLI:

```console
vertex --version
vertex init . --objective "Deliver a useful change"
vertex task add . --id T-1 --title "First task" --outcome "A result exists" \
  --criterion "AC-1=The result can be observed"
vertex check add . T-1 --id tests --criterion AC-1 \
  --command python -m pytest
vertex task start . T-1
vertex verify . T-1
vertex evidence . --task T-1
vertex status .
```

Verification commands execute directly with the current user's permissions; Vertex is
an evidence recorder and lifecycle guard, not a security sandbox.

## Project layout

```text
src/vertex_harness/   Python package and CLI
tests/                Automated tests
docs/                 Roadmap and architectural decisions
.vertex/project.json  Canonical state after a repository is initialized
```

The local `reference/` directory is intentionally excluded from version control. It is
not part of Vertex's source or distribution.

## Project status

Vertex is under active construction and is not ready for production use. See
[`docs/roadmap.md`](docs/roadmap.md) for the intended sequence.
