"""Hash helpers for files, configurations, prompts, and model records."""

from __future__ import annotations

import hashlib
from pathlib import Path

from arena.canonical.schema import stable_hash


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


__all__ = ["file_sha256", "stable_hash"]
