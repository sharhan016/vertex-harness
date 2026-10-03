# 0009: Keep the local web interface observational and loopback-only

- Status: accepted
- Date: 2026-10-03

## Context

People need a fast visual reading of project state, evidence, and repository structure.
Putting lifecycle actions in a browser would add authorization, request-integrity, and
concurrency concerns before they are necessary.

## Decision

`vertex serve` starts a standard-library threaded HTTP server fixed to `127.0.0.1` on
an operating-system-selected port by default. It serves a responsive dashboard and
read-only JSON endpoints for health, status, evidence, bounded context, and the
generated Python index.

Only GET and HEAD are accepted. Mutation methods return 405. Responses include a
restrictive content security policy, frame denial, MIME sniffing protection, no
referrer policy, and no-store caching for project data. The server never rebuilds an
index, writes state, or invokes a verification command.

The interface uses an offline, packaged “engineering field ledger” design. Its task,
evidence, and repository-map views share the same application projections used by the
CLI and MCP rather than interpreting state independently.

## Consequences

- The dashboard can be opened without adding a web framework or runtime dependency.
- Loopback limits network reach but is not authentication. Any process or user able to
  reach the local port can read the exposed project data.
- Confidential repositories on shared hosts should not run the server; CLI output and
  ordinary filesystem permissions are safer there.
- State-changing controls remain in the CLI, where locking and evidence rules already
  exist.
- Static assets must be included in every distribution and are verified during the
  packaging phase.
