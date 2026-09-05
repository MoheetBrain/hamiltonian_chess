"""Content-addressed artifact writing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json


@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    path: Path
    sha256: str


class ArtifactStore:
    def __init__(self, root: str | Path = "artifacts") -> None:
        self.root = Path(root)

    def write_json(self, relative: str | Path, value: Any) -> StoredArtifact:
        payload = canonical_json(value) + "\n"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return StoredArtifact(f"artifact:{digest[:20]}", path, digest)

    def write_text(self, relative: str | Path, value: str) -> StoredArtifact:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return StoredArtifact(f"artifact:{digest[:20]}", path, digest)
