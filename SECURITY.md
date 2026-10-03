# Security policy

## Supported version

Vertex is pre-alpha. Security fixes currently target the latest commit on `main`.

## Reporting a vulnerability

Use GitHub's private security-advisory flow for
[`sharhan016/vertex-harness`](https://github.com/sharhan016/vertex-harness/security/advisories/new).
Do not publish exploit details in a public issue before a fix is available.

## Security boundaries

- Verification commands inherit the invoking user's filesystem, process, environment,
  credential, and network permissions. Vertex is not a sandbox.
- `.vertex/project.json` is an audit-oriented coordination record, not tamper-proof
  storage. A writer with repository access can alter code and state.
- The dashboard binds to loopback and has no authentication. Other local users or
  processes may be able to reach it.
- The MCP server is launched locally over stdio and exposes read-only tools, but it can
  reveal repository state and index content to its host.
- Source fingerprints cover Git-tracked and nonignored paths, excluding Vertex's own
  state. They do not attest to remote services or ignored build inputs.
