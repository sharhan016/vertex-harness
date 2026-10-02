# Vertex Harness

Vertex is a Python-first toolkit for making long-running software work understandable,
verifiable, and recoverable. It is being built in small, working phases so the source
and Git history explain both the design and its evolution.

The current implementation provides the project foundation and a dependency-free core
model for projects, tasks, acceptance criteria, dependencies, and lifecycle rules.
Durable state and user-facing workflow commands will be introduced in later phases.

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
vertex
```

## Project layout

```text
src/vertex_harness/   Python package and CLI
tests/                Automated tests
docs/                 Roadmap and architectural decisions
```

The local `reference/` directory is intentionally excluded from version control. It is
not part of Vertex's source or distribution.

## Project status

Vertex is under active construction and is not ready for production use. See
[`docs/roadmap.md`](docs/roadmap.md) for the intended sequence.
