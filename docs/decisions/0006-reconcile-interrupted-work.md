# 0006: Treat interrupted processes as uncertain until reconciled

- Status: accepted
- Date: 2026-10-03

## Context

A synchronous command can outlive or be cut off from the process that launched it. A
missing final receipt does not prove that the command did nothing, so silently retrying
could repeat external effects. Durable handoff also needs more than the latest task
status.

Adding attempts and checkpoints expands persisted state from schema 2 to schema 3.

## Decision

Vertex records a running verification attempt before spawning a command, then records
the child PID and later binds the finalized attempt to its evidence receipt. Commands
run in their own process session on POSIX so timeout termination can target the process
group.

`vertex recover` examines running attempts. If any recorded PID is alive, recovery
performs no state transition. Attempts with no live process become interrupted and the
affected active task becomes blocked with an instruction to inspect side effects before
explicitly resuming it.

The same recovery path may remove `write.lock` only when it contains a valid PID that
is no longer alive. Malformed locks and live owners fail closed. Checkpoints are concise
notes tied to the revision they describe and may optionally name a task.

Schema-1 and schema-2 readers remain in Vertex; absent attempt and checkpoint arrays are
expanded to empty values, and the next successful write produces schema 3.

## Consequences

- Interrupted commands are never retried automatically.
- PID liveness is evidence about a local process, not proof of external side effects or
  identity; PID reuse remains an operating-system limitation.
- A user must inspect relevant files, services, and remote systems before resuming a
  recovery-blocked task.
- Checkpoints aid a cold-session handoff but are not executable proof.
- Older Vertex binaries cannot read schema 3. Rollback requires restoring the earlier
  state file from version control or backup.
