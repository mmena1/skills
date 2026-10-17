"""The wizard group: runs the wizard helper's unittest regression suite in a subprocess."""

from __future__ import annotations

import subprocess
import sys

from ..common import ROOT, fail


def validate_wizard() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/test_wizard.py")],
        capture_output=True, text=True,
    )
    if result.returncode:
        fail(f"wizard helper regression checks failed:\n{result.stdout}{result.stderr}")
