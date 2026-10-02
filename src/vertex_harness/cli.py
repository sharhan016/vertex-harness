"""Command-line entry point for Vertex."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from vertex_harness import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the top-level command parser."""
    parser = argparse.ArgumentParser(
        prog="vertex",
        description="Coordinate verifiable, recoverable software work.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Vertex command-line interface."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
