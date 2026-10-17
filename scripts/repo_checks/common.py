"""Shared infrastructure: repository-root resolution and failure reporting.

Every other module reports a failed check through `fail`, which raises `CheckFailure`;
the canonical entry point turns the first one into its `FAIL:` line.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


class CheckFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CheckFailure(message)
