# State compatibility and upgrades

Vertex 0.1 writes state schema 3 and reads schemas 1, 2, and 3.

| Schema | Added data | Read by 0.1 | Upgrade behavior |
| --- | --- | --- | --- |
| 1 | Project and task lifecycle | Yes | Empty checks and evidence are supplied |
| 2 | Verification checks and evidence | Yes | Empty attempts and checkpoints are supplied |
| 3 | Verification attempts and checkpoints | Yes | Current format |

Loading an older schema does not rewrite it. The next successful state mutation writes
the full current schema through the same atomic replacement path.

Before upgrading a repository:

1. Commit or back up `.vertex/project.json`.
2. Install the new Vertex version.
3. Run `vertex doctor .` and `vertex status . --json`.
4. Perform the intended mutation and review the state diff before committing it.

Vertex does not provide a lossy downgrade command. To roll back to an older binary,
restore the compatible state file captured before its first newer-schema write.

Generated `.vertex/index.json` is not migrated. Rebuild it with `vertex index .`.
