# Command reference

All commands accept a repository path; when optional, it defaults to the current
directory.

| Command | Purpose | Writes state |
| --- | --- | :---: |
| `vertex init` | Create the first project ledger | Yes |
| `vertex status` | Show project and task status | No |
| `vertex task add` | Add a dependency-valid planned task | Yes |
| `vertex task start` | Start an available task | Yes |
| `vertex task block` | Record an explicit blocker | Yes |
| `vertex task resume` | Resume inspected blocked work | Yes |
| `vertex check add` | Attach an argv-based check to a planned task | Yes |
| `vertex verify` | Run checks, record attempts/evidence, and possibly complete | Yes |
| `vertex evidence` | Read verification receipts | No |
| `vertex checkpoint create` | Record a handoff note | Yes |
| `vertex checkpoint list` | Read handoff notes | No |
| `vertex recover` | Reconcile dead attempts and stale locks | When needed |
| `vertex index` | Rebuild the ignored Python index | Generated file |
| `vertex query` | Query declarations and import relationships | No |
| `vertex context` | Build a bounded agent packet | No |
| `vertex mcp` | Serve read-only agent tools over stdio | No |
| `vertex serve` | Serve the loopback read API and dashboard | No |
| `vertex doctor` | Diagnose installation, state, and index | No |

Use `vertex COMMAND --help` for arguments and examples in the main README.
