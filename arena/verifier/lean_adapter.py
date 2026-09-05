"""Lean availability/provenance adapter. Translation is never inferred implicitly."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class LeanEnvironment:
    available: bool
    executable: str | None
    version: str | None


def inspect_lean() -> LeanEnvironment:
    executable = shutil.which("lean")
    if executable is None:
        return LeanEnvironment(False, None, None)
    process = subprocess.run(
        [executable, "--version"], check=False, capture_output=True, text=True, timeout=10
    )
    version = process.stdout.strip() if process.returncode == 0 else None
    return LeanEnvironment(process.returncode == 0, executable, version)
