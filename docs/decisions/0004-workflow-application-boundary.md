# 0004: Put workflow coordination behind one application service

- Status: accepted
- Date: 2026-10-03

## Context

The domain and state layers are useful only when an interface can coordinate them
without duplicating rules. The first interface is the command line, but later MCP and
HTTP interfaces must invoke the same use cases.

## Decision

`WorkflowService` is the application boundary for repository initialization, status,
task creation, and lifecycle actions. It constructs domain values and submits pure
transformations to `ProjectStore`; it does not alter JSON or task fields directly.

The CLI is an adapter. It parses user input, calls the service, and renders either a
compact human view or JSON. Expected domain, state, and workflow failures produce a
short error with exit code 2.

Task completion is deliberately absent from this phase. It becomes available only
after verification can provide durable evidence for every acceptance criterion.

## Consequences

- Future interfaces can share behavior without importing CLI code.
- A repository path typo cannot create a new directory during initialization.
- CLI output is not canonical state and may evolve independently.
- The current commands operate one-at-a-time; multi-operation transactions are not yet
  a requirement.
