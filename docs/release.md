# Release checklist

Vertex does not publish automatically. A release is an explicit maintainer action.

1. Confirm the working tree is clean and `main` is current.
2. Update `src/vertex_harness/__init__.py` and `CHANGELOG.md`.
3. Run the supported gates:

   ```console
   python -m ruff check .
   python -m pytest
   python -m compileall -q src tests
   python -m build
   ```

4. Inspect both archives. Confirm the wheel contains `interfaces/web/` assets and the
   source archive excludes `reference/`, `.vertex/`, and local caches.
5. Install the wheel into a fresh virtual environment and run:

   ```console
   vertex --version
   vertex --help
   vertex doctor .
   ```

6. Tag the exact tested commit only after deciding where the distribution will be
   published. Publication credentials and signing are intentionally not configured.

No open-source license is currently granted. Choose and add a license before any
public package distribution that requires one.
