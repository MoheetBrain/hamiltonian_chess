"""Version hashes for the shipped package.

Every file that decides what a model sees, or what a canonical consumer receives, is
hashed: the spec, the renderer, the parser, the canonical adapter and the training schema
above all.  ``HASHES.json`` is committed, and ``tests/releases/test_hashes.py`` recomputes
it, so editing any hashed file without regenerating the manifest fails the suite.

File digests are plain SHA-256 over bytes.  The aggregate identity uses
``arena.canonical.schema.stable_hash``, the project's existing primitive -- there is
deliberately no second hashing scheme in this package.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash

from .core import EVIDENCE_LEVEL, LANGUAGE_ID, LANGUAGE_VERSION

PACKAGE_ROOT = Path(__file__).resolve().parent
HASHES_PATH = PACKAGE_ROOT / "HASHES.json"
HASH_SCHEMA_VERSION = "tl0-hashes-v1"

#: Named components, in the order the release notes discuss them.  A file may belong to
#: more than one component: ``syntax.py`` is genuinely shared by renderer and parser.
COMPONENTS: dict[str, tuple[str, ...]] = {
    "spec": ("SPEC.md", "VERSION"),
    "core": ("core.py", "libraries.py"),
    "renderer": ("renderer.py", "syntax.py"),
    "parser": ("parser.py", "syntax.py"),
    "canonical_adapter": ("canonical_adapter.py",),
    "training_schema": ("training_schema.py",),
    "surfaces": ("surfaces.py",),
    "acquisition": ("acquisition.py", "ACQUISITION_GUIDE.md"),
    "human_renderer": ("human.py",),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashed_files() -> tuple[str, ...]:
    """Every shipped module plus every named non-Python artefact, in stable order."""

    names = {name for group in COMPONENTS.values() for name in group}
    names.update(item.name for item in PACKAGE_ROOT.glob("*.py"))
    return tuple(sorted(names))


def compute_hashes() -> dict[str, Any]:
    """Recompute the manifest from the files on disk."""

    files: dict[str, str] = {}
    for name in hashed_files():
        path = PACKAGE_ROOT / name
        if not path.exists():
            raise FileNotFoundError(f"hashed file is missing: {name}")
        files[name] = _sha256(path)
    components = {
        component: stable_hash({name: files[name] for name in sorted(group)})
        for component, group in sorted(COMPONENTS.items())
    }
    manifest: dict[str, Any] = {
        "schema_version": HASH_SCHEMA_VERSION,
        "language_id": LANGUAGE_ID,
        "language_version": LANGUAGE_VERSION,
        "evidence_level": EVIDENCE_LEVEL,
        "files": files,
        "components": components,
    }
    manifest["package_hash"] = stable_hash(manifest)
    return manifest


def write_hashes(path: Path | None = None) -> dict[str, Any]:
    manifest = compute_hashes()
    destination = path or HASHES_PATH
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def read_hashes(path: Path | None = None) -> dict[str, Any]:
    source = path or HASHES_PATH
    loaded: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    return loaded


def verify_hashes(path: Path | None = None) -> tuple[str, ...]:
    """Return the names of every file whose digest no longer matches the manifest."""

    recorded = read_hashes(path)
    current = compute_hashes()
    if recorded.get("package_hash") == current["package_hash"]:
        return ()
    differences = [
        name
        for name in sorted(set(recorded.get("files", {})) | set(current["files"]))
        if recorded.get("files", {}).get(name) != current["files"].get(name)
    ]
    return tuple(differences or ("package_hash",))


if __name__ == "__main__":  # pragma: no cover - regeneration entry point
    print(json.dumps(write_hashes(), indent=2, sort_keys=True))


__all__ = [
    "COMPONENTS",
    "HASHES_PATH",
    "HASH_SCHEMA_VERSION",
    "PACKAGE_ROOT",
    "compute_hashes",
    "hashed_files",
    "read_hashes",
    "verify_hashes",
    "write_hashes",
]
