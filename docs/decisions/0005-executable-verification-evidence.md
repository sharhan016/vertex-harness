# 0005: Complete tasks only from fresh executable evidence

- Status: accepted
- Date: 2026-10-03

## Context

An acceptance criterion is a statement of intent, not proof. Vertex needs to connect
task completion to commands that actually ran against the repository while preserving
enough information to understand failures later.

Adding verification definitions and receipts expands the persisted state format. State
written by the previous release uses schema 1.

## Decision

A planned task may define checks as argument lists, criterion IDs, and bounded timeouts.
Checks are executed directly without an implicit shell. Vertex fingerprints Git-tracked
and nonignored files before and after each command, excluding its own `.vertex` state.

Every run creates an evidence receipt containing command identity, covered criteria,
UTC timestamps, exit status, bounded output, source fingerprints, and one of four
outcomes: passed, failed, timed out, or source changed. A task completes atomically with
the receipts only when all checks pass without modifying source and their union covers
every criterion.

Schema 2 stores check definitions and evidence. The reader continues to accept schema
1, supplying empty checks and evidence. The next successful write upgrades that state
atomically. Failed reads or writes leave the original file intact.

## Consequences

- An exit code alone cannot complete work if the check changed its own inputs.
- Failed checks remain useful evidence while the task stays active.
- Existing schema-1 repositories remain usable; old binaries cannot read schema 2.
  Rollback therefore means restoring the pre-upgrade `project.json` from version
  control or backup, not attempting a lossy automatic downgrade.
- Checks inherit the invoking user's filesystem, process, environment, and network
  permissions. Vertex records outcomes; it is not a sandbox.
- Output is capped at 16 KiB per stream. Full external logs remain the check owner's
  responsibility.
