# Development guide

## Layer boundaries

```text
CLI / MCP / HTTP
       │
application services and serializable views
       │
domain model ── repository intelligence
       │                │
versioned state      generated index
```

- `domain/` owns values and lifecycle invariants. It performs no I/O.
- `state/` owns schema compatibility, locking, strict decoding, and atomic writes.
- `application/` coordinates use cases without parsing CLI or HTTP details.
- `intelligence/` builds and queries derived, advisory Python facts.
- `agent/`, `interfaces/`, and `cli.py` adapt application behavior to transports.
- `workspace.py` defines shared source discovery and fingerprinting.

An interface must not edit domain fields or JSON directly. A state mutation goes
through a domain operation and `ProjectStore`. Generated views may be deleted and
rebuilt; canonical project state may not.

## Test strategy

The suite progresses from pure domain tests to state compatibility fixtures, service
tests, CLI flows, real subprocess execution, real loopback HTTP, and MCP framing. Tests
use temporary repositories and do not require network services.

For a state-schema change, keep fixtures for every still-supported schema and prove the
next successful write upgrades it without destroying data. Do not contract old readers
in the same phase that introduces a new schema.

## Runtime dependencies

The runtime deliberately uses only the Python standard library. Add a dependency only
when a demonstrated requirement outweighs its installation, compatibility, security,
and maintenance cost.
