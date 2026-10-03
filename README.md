# Vertex Harness

Vertex is a Python-first toolkit for making long-running software work understandable,
verifiable, and recoverable. It is being built in small, working phases so the source
and Git history explain both the design and its evolution.

The current implementation provides the project foundation, a dependency-free core
model, guarded repository-local JSON state, CLI-driven task workflows, and executable
verification with durable evidence. Recorded attempts and checkpoints make interrupted
work explicit and recoverable without automatic retries. A conservative Python index
adds symbol discovery and import-impact queries. Agents can consume bounded context and
the same read-only queries through MCP. A loopback-only dashboard presents the same
status, evidence, context, and index as an observational field ledger.

## Requirements

- Python 3.11 or newer

## Installation

Install directly from the Git repository with `pipx`:

```console
pipx install git+https://github.com/sharhan016/vertex-harness.git
vertex --version
```

For development, clone the repository and use an editable virtual environment as shown
below. Vertex has no third-party runtime dependencies.

## Development setup

Create a virtual environment and install the project with its development tools:

```console
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run the checks:

```console
python -m ruff check .
python -m pytest
python -m compileall -q src tests
python -m build
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
vertex checkpoint create . --task T-1 --note "Ready for review"
vertex recover .
vertex index .
vertex query . search WorkflowService
vertex query . impact src/vertex_harness/domain/model.py
vertex context . --task T-1 --bytes 8000
vertex serve . --open
vertex doctor .
vertex status .
```

Verification commands execute directly with the current user's permissions; Vertex is
an evidence recorder and lifecycle guard, not a security sandbox.

If verification is interrupted, run `vertex recover .`. Vertex refuses recovery while
the recorded process is alive. When the process is gone, it marks the attempt
interrupted and blocks the task so side effects can be inspected before `task resume`.

Repository queries are advisory. The current index understands Python declarations and
imports; it does not infer runtime calls or claim coverage for other languages. Query
output says when the generated index is stale.

## MCP integration

Register the local stdio server with an MCP host:

```json
{
  "mcpServers": {
    "vertex": {
      "command": "vertex",
      "args": ["mcp", "/absolute/path/to/repository"]
    }
  }
}
```

The server supports the current stateless MCP lifecycle and legacy initialize clients.
Its tools can read status, context, and the generated Python index; they cannot change
state or execute verification commands.

## Local dashboard

`vertex serve .` prints a loopback URL using an available port. Pass `--port 8765` for
a fixed port or `--open` to launch the default browser. The dashboard is responsive and
read-only: HTTP mutation methods are rejected, and all lifecycle actions remain CLI
commands.

Loopback binding is not user authentication. Do not run the dashboard for a
confidential repository on a shared machine where other local users or processes are
untrusted.

## Project layout

```text
src/vertex_harness/   Python package and CLI
tests/                Automated tests
docs/                 Roadmap and architectural decisions
.github/workflows/    Supported-version and packaging checks
.vertex/project.json  Canonical state after a repository is initialized
```

The local `reference/` directory is intentionally excluded from version control. It is
not part of Vertex's source or distribution.

## Project status

The initial zero-to-one roadmap is complete at version 0.1.0. Vertex remains pre-alpha:
its local contracts are tested, but it does not claim production isolation, hosted
identity, or remote-service guarantees. See [`docs/roadmap.md`](docs/roadmap.md), the
[`development guide`](docs/development.md), and the
[`command reference`](docs/command-reference.md).

## License

No open-source license is currently included. Copyright law therefore reserves reuse
rights by default; choose a license explicitly before distributing Vertex as an
open-source package.
