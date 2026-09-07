from pathlib import Path
from typing import Any

import pytest

from arena.corpus.contamination import SplitCategory
from arena.corpus.provenance import (
    ARENA_TRUST_TIER_MAP,
    TRUST_TIER_ORDER,
    CorpusTrustTier,
    IngestionProvenance,
    ProvenanceViolation,
    content_sha256,
    ingest,
    require_at_least,
    trust_rank,
    weakest,
)
from arena.provenance import TrustTier, TrustViolation, require_oracle_grade

CONTENT = b"theorem foo : 1 + 1 = 2 := by norm_num"


def provenance(**overrides: Any) -> IngestionProvenance:
    fields: dict[str, Any] = {
        "source_id": "mathlib4",
        "source_version": "95e8a26",
        "licence": "Apache-2.0",
        "source_item_id": "Mathlib/Algebra/Foo.lean:12",
        "content_hash": content_sha256(CONTENT),
        "imported_at": "2026-09-07T05:32:06+00:00",
        "extractor": "lean-transition-adapter",
        "extractor_version": "0.1.0",
        "trust_tier": CorpusTrustTier.VERIFIED_FORMAL,
        "contamination_category": SplitCategory.HISTORICALLY_EXPOSED,
        "intended_split": SplitCategory.DEVELOPMENT,
    }
    fields.update(overrides)
    return IngestionProvenance(**fields)


# -- trust tier ordering ---------------------------------------------------------------


def test_trust_tiers_are_strictly_ordered_strongest_first() -> None:
    ranks = [trust_rank(tier) for tier in TRUST_TIER_ORDER]
    assert ranks == sorted(ranks)
    assert (
        trust_rank(CorpusTrustTier.VERIFIED_FORMAL)
        < trust_rank(CorpusTrustTier.DETERMINISTICALLY_CHECKED)
        < trust_rank(CorpusTrustTier.HUMAN_ANNOTATED)
        < trust_rank(CorpusTrustTier.MODEL_GENERATED)
        < trust_rank(CorpusTrustTier.ANNOTATION_UNVERIFIED)
    )


def test_weakest_tier_wins() -> None:
    assert (
        weakest((CorpusTrustTier.VERIFIED_FORMAL, CorpusTrustTier.MODEL_GENERATED))
        is CorpusTrustTier.MODEL_GENERATED
    )


def test_weakest_of_nothing_is_refused() -> None:
    with pytest.raises(TrustViolation):
        weakest(())


def test_require_at_least_refuses_a_weaker_tier() -> None:
    require_at_least(
        CorpusTrustTier.VERIFIED_FORMAL, CorpusTrustTier.HUMAN_ANNOTATED, use="an oracle"
    )
    with pytest.raises(TrustViolation, match="weaker"):
        require_at_least(
            CorpusTrustTier.MODEL_GENERATED,
            CorpusTrustTier.DETERMINISTICALLY_CHECKED,
            use="an oracle",
        )


# -- fail-closed construction ----------------------------------------------------------


def test_a_fully_provenanced_item_is_accepted() -> None:
    assert provenance().content_hash == content_sha256(CONTENT)


@pytest.mark.parametrize("licence", ["", "   ", "UNKNOWN", "unverified", "none", "TBD", "n/a"])
def test_missing_licence_is_refused(licence: str) -> None:
    with pytest.raises(ProvenanceViolation, match="licence"):
        provenance(licence=licence)


@pytest.mark.parametrize(
    "content_hash",
    ["", "deadbeef", "Z" * 64, content_sha256(CONTENT).upper(), content_sha256(CONTENT) + "0"],
)
def test_missing_or_malformed_content_hash_is_refused(content_hash: str) -> None:
    with pytest.raises(ProvenanceViolation, match="SHA-256"):
        provenance(content_hash=content_hash)


@pytest.mark.parametrize(
    "field",
    ["source_id", "source_version", "source_item_id", "extractor", "extractor_version"],
)
def test_every_required_identifier_is_refused_when_blank(field: str) -> None:
    with pytest.raises(ProvenanceViolation, match=field):
        provenance(**{field: "  "})


@pytest.mark.parametrize("stamp", ["", "yesterday", "2026-13-45T00:00:00+00:00"])
def test_unparseable_import_timestamp_is_refused(stamp: str) -> None:
    with pytest.raises(ProvenanceViolation, match="ISO-8601"):
        provenance(imported_at=stamp)


def test_naive_import_timestamp_is_refused() -> None:
    with pytest.raises(ProvenanceViolation, match="timezone"):
        provenance(imported_at="2026-09-07T05:32:06")


def test_never_train_item_cannot_be_imported_for_training() -> None:
    with pytest.raises(ProvenanceViolation, match="never-train"):
        provenance(never_train=True, intended_split=SplitCategory.TRAINING_CANDIDATE)


@pytest.mark.parametrize(
    "intended", [SplitCategory.OOD, SplitCategory.PROMOTION, SplitCategory.RESERVED_EVAL]
)
def test_exposed_source_cannot_be_imported_into_a_clean_split(
    intended: SplitCategory,
) -> None:
    with pytest.raises(ProvenanceViolation, match=intended.value):
        provenance(
            contamination_category=SplitCategory.HISTORICALLY_EXPOSED, intended_split=intended
        )


# -- verification ----------------------------------------------------------------------


def test_verify_content_accepts_the_original_bytes() -> None:
    provenance().verify_content(CONTENT)


def test_verify_content_detects_alteration() -> None:
    with pytest.raises(ProvenanceViolation, match="altered after import"):
        provenance().verify_content(CONTENT + b" -- edited")


def test_verify_file_round_trips_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "item.lean"
    path.write_bytes(CONTENT)
    provenance().verify_file(path)
    path.write_bytes(CONTENT + b"\n")
    with pytest.raises(ProvenanceViolation, match="no longer matches"):
        provenance().verify_file(path)


def test_ingest_hashes_the_actual_bytes() -> None:
    record = ingest(
        CONTENT,
        source_id="mathlib4",
        source_version="95e8a26",
        licence="Apache-2.0",
        source_item_id="item:1",
        extractor="adapter",
        extractor_version="0.1.0",
        trust_tier=CorpusTrustTier.VERIFIED_FORMAL,
        contamination_category=SplitCategory.HISTORICALLY_EXPOSED,
        intended_split=SplitCategory.DEVELOPMENT,
    )
    record.verify_content(CONTENT)
    assert record.content_hash == content_sha256(CONTENT)


# -- relationship to arena/provenance.py ------------------------------------------------


@pytest.mark.parametrize("tier", list(CorpusTrustTier))
def test_every_corpus_tier_projects_onto_a_canonical_tier(tier: CorpusTrustTier) -> None:
    assert isinstance(ARENA_TRUST_TIER_MAP[tier], TrustTier)


def test_verified_formal_projects_to_an_oracle_grade_tier() -> None:
    projected = provenance().to_source_provenance(
        source_path="Mathlib/Algebra/Foo.lean",
        canonicalization_sha256=content_sha256(b"canonical"),
        verifier="lean4-kernel",
    )
    assert projected.trust_tier is TrustTier.A_NATIVE_VERIFIED
    require_oracle_grade(projected, use="a Sigma oracle")


def test_model_generated_projects_to_a_tier_the_canonical_gate_refuses() -> None:
    projected = provenance(trust_tier=CorpusTrustTier.MODEL_GENERATED).to_source_provenance(
        source_path="Mathlib/Algebra/Foo.lean",
        canonicalization_sha256=content_sha256(b"canonical"),
        verifier="none",
    )
    assert projected.trust_tier is TrustTier.C_CANDIDATE_SEMANTICS
    with pytest.raises(TrustViolation, match="may not be used"):
        require_oracle_grade(projected, use="a Sigma oracle")


# -- serialization ---------------------------------------------------------------------


def test_round_trip_preserves_every_field() -> None:
    original = provenance(caveats=("premise counts are lower bounds",))
    assert IngestionProvenance.from_dict(original.to_dict()) == original


def test_round_trip_revalidates_and_refuses_a_tampered_record() -> None:
    payload = provenance().to_dict()
    payload["licence"] = ""
    with pytest.raises(ProvenanceViolation, match="licence"):
        IngestionProvenance.from_dict(payload)
