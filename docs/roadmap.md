# Vertex build roadmap

The implementation will grow through narrow vertical phases. Every phase must define
observable behavior, include tests, pass the repository checks, and end in a focused
commit.

- [x] **Foundation** — package layout, CLI entry point, tests, and project conventions.
- [x] **Core concepts** — explicit domain types and lifecycle rules without persistence.
- [x] **State** — durable repository-local storage with validation and safe updates.
- [ ] **Workflows** — a small task lifecycle driven by the core rules.
- [ ] **Verification and evidence** — executable checks and durable proof tied to inputs.
- [ ] **Recovery** — checkpoints and reconciliation of interrupted work.
- [ ] **Repository intelligence** — useful, conservative source discovery and queries.
- [ ] **Agent integration** — read-only MCP tools and bounded agent-facing context.
- [ ] **Interfaces** — local API and dashboard built on the same application services.
- [ ] **Packaging** — installation, release checks, and supported upgrade paths.

The ordering may change when an earlier phase reveals a simpler boundary. Features are
not pulled forward merely to make later architecture appear complete.

## Current non-goals

- Hosted services or accounts
- Automatic execution of agent or shell commands
- A plugin/provider framework
- Multiple storage backends
- Authentication or remote collaboration
- Production deployment guarantees
