# 0001: Begin with a dependency-free Python core

- Status: accepted
- Date: 2026-10-03

## Context

Vertex needs a foundation that is easy to inspect, test, install, and extend without
choosing the later workflow and persistence designs prematurely.

## Decision

Vertex supports Python 3.11 and newer, uses a `src` package layout, and exposes one
console command backed by the standard library's `argparse` module. The runtime has no
third-party dependencies in this phase. Pytest is the only development dependency.

Setuptools is used only as the build backend. The package and command are named
`vertex-harness` and `vertex`, respectively.

## Consequences

- Imports in tests reflect an installed package layout rather than the repository root.
- The CLI remains intentionally small until real commands establish stronger needs.
- Later phases must justify every runtime dependency against a concrete requirement.
- Python 3.10 and older are outside the supported compatibility target.
