# 0008: Give agents bounded context through a read-only MCP boundary

- Status: accepted
- Date: 2026-10-03

## Context

Agents need structured access to current work and repository intelligence without being
allowed to bypass the CLI's lifecycle and evidence rules. Context must also be bounded
so a large history cannot silently displace the active task contract.

MCP has two active lifecycle eras. The 2026-07-28 revision is stateless and uses
per-request metadata plus `server/discover`; clients through 2025-11-25 use the
initialize handshake.

## Decision

`vertex context` builds a deterministic packet with the selected task, acceptance
criteria, checks, next action, project summary, source fingerprint, index freshness,
and as much recent evidence and checkpoint history as fits. Required content never
truncates silently; an inadequate budget fails.

`vertex mcp` serves newline-delimited JSON-RPC on stdio with a 4 MiB request-frame cap.
It supports MCP 2026-07-28 discovery and per-request metadata, plus legacy initialize
negotiation through 2025-11-25. The deterministic tool catalog exposes only status,
bounded context, and repository-index queries. Every tool is annotated read-only,
non-destructive, idempotent, and closed-world.

The implementation follows the official protocol lifecycle and tool result shapes:
<https://modelcontextprotocol.io/specification/2026-07-28>.

## Consequences

- MCP cannot initialize projects, mutate tasks, run checks, recover attempts, or write
  checkpoints. Those actions remain explicit CLI operations.
- Both text and structured tool results are returned for host compatibility.
- Tool handler failures return `isError`; protocol-shape failures use JSON-RPC errors.
- Index results remain advisory and report staleness.
- The stdio server has no authentication because its client launches the local process;
  it inherits the invoking user's filesystem visibility.
