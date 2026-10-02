# 0003: Store one versioned project snapshot with guarded atomic updates

- Status: accepted
- Date: 2026-10-03

## Context

Vertex must survive process and conversation boundaries before workflow commands can
be useful. The first storage design should protect valid project state without adding a
database, migration framework, or background service.

## Decision

Canonical state lives at `.vertex/project.json` as readable, schema-versioned JSON. A
snapshot contains the immutable project aggregate and a monotonically increasing
revision.

Initialization refuses to replace an existing file. Updates acquire a repository-local
single-writer lock, reload current state, optionally compare the caller's expected
revision, apply one domain transformation, and atomically replace the JSON file. The
new file and containing directory are synchronized before success is returned.

Stored input is decoded strictly. Unknown schemas, malformed structures, invalid enum
values, and domain-inconsistent tasks fail explicitly rather than being repaired or
silently ignored.

## Consequences

- Readers see either the previous complete snapshot or the next complete snapshot.
- Cooperative writers cannot unknowingly overwrite a newer revision.
- A crashed writer may leave `write.lock`; automated reconciliation of a stale lock is
  deferred to the recovery phase because deleting it safely requires process evidence.
- JSON remains practical for inspection and version control at the expected early
  project size. A database is not justified yet.
- Schema migration is deferred until a second schema exists. Unsupported versions fail
  closed in the meantime.
