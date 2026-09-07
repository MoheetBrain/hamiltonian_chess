"""Item L: the committed HASHES.json must describe the files that actually ship."""

from __future__ import annotations

import json
from pathlib import Path

from releases.TRAINING_LANGUAGE_V0 import compute_hashes, read_hashes, verify_hashes
from releases.TRAINING_LANGUAGE_V0.hashes import (
    COMPONENTS,
    HASH_SCHEMA_VERSION,
    HASHES_PATH,
    PACKAGE_ROOT,
    hashed_files,
    write_hashes,
)


def test_the_committed_manifest_matches_the_files_on_disk() -> None:
    assert verify_hashes() == (), "regenerate with python -m releases.TRAINING_LANGUAGE_V0.hashes"


def test_the_manifest_covers_every_shipped_module_and_artefact() -> None:
    names = set(hashed_files())
    assert {item.name for item in PACKAGE_ROOT.glob("*.py")} <= names
    assert {"SPEC.md", "VERSION", "ACQUISITION_GUIDE.md"} <= names
    assert set(read_hashes()["files"]) == names


def test_every_named_component_is_hashed() -> None:
    manifest = compute_hashes()
    assert set(manifest["components"]) == set(COMPONENTS)
    assert {"spec", "renderer", "parser", "canonical_adapter", "training_schema"} <= set(COMPONENTS)
    assert len(set(manifest["components"].values())) == len(COMPONENTS)


def test_the_manifest_records_the_evidence_level_and_schema_version() -> None:
    manifest = read_hashes()
    assert manifest["schema_version"] == HASH_SCHEMA_VERSION
    assert manifest["evidence_level"] == "TRAINING_LANGUAGE_V0_BASELINE"
    assert manifest["language_version"] == "0.1.0"


def test_hashing_is_deterministic() -> None:
    assert compute_hashes() == compute_hashes()


def test_a_changed_file_is_detected(tmp_path: Path) -> None:
    stale = json.loads(HASHES_PATH.read_text(encoding="utf-8"))
    stale["files"]["renderer.py"] = "0" * 64
    stale["package_hash"] = "0" * 64
    path = tmp_path / "HASHES.json"
    path.write_text(json.dumps(stale), encoding="utf-8")
    assert verify_hashes(path) == ("renderer.py",)


def test_the_manifest_can_be_regenerated_without_changing(tmp_path: Path) -> None:
    regenerated = write_hashes(tmp_path / "HASHES.json")
    assert regenerated == read_hashes()
