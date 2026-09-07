"""Integrity: this release must state its evidence level and claim nothing beyond it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from releases.TRAINING_LANGUAGE_V0 import EVIDENCE_LEVEL, read_hashes
from releases.TRAINING_LANGUAGE_V0.hashes import PACKAGE_ROOT

#: The project's actual release-status identifiers.  A packaging release may not carry one.
FORBIDDEN_STATUS_TOKENS = ("RSTAR_V0", "RSTAR_0_1", "RSTAR_RELEASE", "RSTAR_FROZEN")
SHIPPED = sorted([*PACKAGE_ROOT.glob("*.py"), *PACKAGE_ROOT.glob("*.md"), PACKAGE_ROOT / "VERSION"])


def test_the_evidence_level_is_the_baseline_one() -> None:
    assert EVIDENCE_LEVEL == "TRAINING_LANGUAGE_V0_BASELINE"
    assert read_hashes()["evidence_level"] == EVIDENCE_LEVEL
    assert EVIDENCE_LEVEL in (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", SHIPPED, ids=lambda item: item.name)
def test_no_shipped_file_claims_a_release_status_it_does_not_have(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    offenders = [token for token in FORBIDDEN_STATUS_TOKENS if token in text]
    assert not offenders, f"{path.name} claims {offenders}"


def test_the_canonical_substrate_version_is_untouched() -> None:
    from arena.canonical.schema import SCHEMA_VERSION

    assert SCHEMA_VERSION == "arena-canonical-v0.1.0"
    assert SCHEMA_VERSION in (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8")


def test_the_hash_manifest_is_valid_json_with_a_package_hash() -> None:
    manifest = json.loads((PACKAGE_ROOT / "HASHES.json").read_text(encoding="utf-8"))
    assert len(manifest["package_hash"]) == 64
    assert all(len(digest) == 64 for digest in manifest["files"].values())
