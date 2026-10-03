"""Deterministic discovery and fingerprinting of repository source files."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path

EXCLUDED_DIRECTORIES = {
    ".git",
    ".vertex",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "reference",
}


def discover_files(repository: Path | str) -> tuple[Path, ...]:
    """Return sorted relative paths from Git or a conservative filesystem walk."""
    root = Path(repository).resolve()
    paths = _git_paths(root)
    if paths is None:
        paths = _walk_paths(root)
    return tuple(
        sorted(
            (path for path in paths if not _excluded(path)),
            key=lambda path: path.as_posix(),
        )
    )


def source_fingerprint(repository: Path | str) -> str:
    """Hash discovered file paths, modes, contents, and symlink targets."""
    root = Path(repository).resolve()
    digest = hashlib.sha256(b"vertex-source-v1\0")
    for relative in discover_files(root):
        path = root / relative
        digest.update(relative.as_posix().encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            digest.update(b"missing\0")
            continue
        digest.update(str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"link\0")
            digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(131_072), b""):
                    digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _git_paths(root: Path) -> set[Path] | None:
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return {
        Path(value.decode("utf-8", errors="surrogateescape"))
        for value in completed.stdout.split(b"\0")
        if value
    }


def _walk_paths(root: Path) -> set[Path]:
    paths: set[Path] = set()
    for directory, names, files in os.walk(root):
        names[:] = sorted(
            name for name in names if name not in EXCLUDED_DIRECTORIES
        )
        base = Path(directory)
        for name in sorted(files):
            paths.add((base / name).relative_to(root))
    return paths


def _excluded(path: Path) -> bool:
    return bool(path.parts and path.parts[0] in EXCLUDED_DIRECTORIES)
