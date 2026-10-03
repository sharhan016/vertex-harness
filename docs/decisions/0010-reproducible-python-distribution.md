# 0010: Ship one dependency-free Python distribution with reproducible gates

- Status: accepted
- Date: 2026-10-03

## Context

The first complete Vertex slice needs an installation and release contract that proves
the CLI and packaged dashboard work outside the source checkout. Version drift and
unverified assets would undermine that contract.

## Decision

`vertex_harness.__version__` is the sole version source for package metadata and CLI
output. Setuptools builds a wheel and source distribution; package data explicitly
includes offline dashboard assets. Runtime dependencies remain empty. Development
dependencies contain only the build frontend, pytest, and Ruff.

GitHub Actions runs lint, tests, and byte compilation on Python 3.11 through 3.14, then
builds and installs the wheel in a separate packaging job. `vertex doctor` provides a
read-only local check of Python compatibility, repository existence, state validity,
and index freshness.

Release publication is intentionally manual and unconfigured. No license is added by
default.

## Consequences

- A source checkout and an installed wheel expose the same console command and assets.
- Python 3.11 is the oldest supported interpreter and constrains syntax and standard
  library use.
- CI depends on official `actions/checkout@v7` and `actions/setup-python@v7` releases.
- A future publisher must choose package ownership, credentials, signing, and a license
  explicitly rather than inheriting accidental defaults.
