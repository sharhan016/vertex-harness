# 0002: Keep lifecycle rules in an immutable project aggregate

- Status: accepted
- Date: 2026-10-03

## Context

Later storage, workflow, and interface layers need one definition of valid work rather
than each layer interpreting task state independently. This definition must remain
testable before persistence exists.

## Decision

The core model consists of a project objective, ordered tasks, and observable
acceptance criteria. A project owns task identity, dependency ordering, and these
transitions:

```text
planned ──→ active ──→ completed
               │
               ↓
            blocked
               │
               └────→ active
```

Starting requires completed dependencies. Blocking requires a reason. Completion
requires the caller to account for exactly every declared acceptance criterion.

Domain objects are immutable. Every successful operation returns a new project, while
a rejected operation leaves the original value unchanged. Tasks may depend only on
tasks already defined in the project, making cycles impossible by construction.

## Consequences

- Persistence can serialize snapshots without tracking partially mutated objects.
- Interfaces receive explicit domain errors instead of inferring failures from state.
- A future verification service must produce the criterion identifiers used to request
  completion; the current model does not claim that identifiers are proof.
- Forward references between tasks are not supported. Planning must add prerequisites
  before their dependents.
- Reopening completed work is deferred until a concrete recovery requirement defines
  its audit behavior.
