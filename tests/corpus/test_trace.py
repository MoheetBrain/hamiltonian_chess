from typing import Any

import pytest

from arena.canonical.schema import VerificationRecord, VerificationStatus
from arena.corpus.contamination import SplitCategory
from arena.corpus.provenance import (
    CorpusTrustTier,
    IngestionProvenance,
    ProvenanceViolation,
    content_sha256,
)
from arena.corpus.trace import (
    OperationAnnotation,
    ReasoningStep,
    ReasoningTrace,
    require_verified_operation,
)
from arena.provenance import TrustViolation

RAW_STEP = "intro h\n  -- « unicode, trailing space and tabs » \t "
RAW_PROBLEM = "Prove that $\\sqrt{2}\\notin\\mathbb{Q}$.\n\n  (verbatim, with odd spacing) "

ACCEPTED = VerificationRecord(
    verifier="lean4-kernel",
    verifier_version="4.10.0",
    status=VerificationStatus.VERIFIED,
    accepted=True,
)


def provenance() -> IngestionProvenance:
    return IngestionProvenance(
        source_id="mathlib4",
        source_version="95e8a26",
        licence="Apache-2.0",
        source_item_id="item:1",
        content_hash=content_sha256(RAW_PROBLEM.encode("utf-8")),
        imported_at="2026-09-07T05:32:06+00:00",
        extractor="lean-transition-adapter",
        extractor_version="0.1.0",
        trust_tier=CorpusTrustTier.VERIFIED_FORMAL,
        contamination_category=SplitCategory.HISTORICALLY_EXPOSED,
        intended_split=SplitCategory.DEVELOPMENT,
    )


def verified_step(index: int = 0, raw_text: str = RAW_STEP, **overrides: Any) -> ReasoningStep:
    fields: dict[str, Any] = {
        "step_index": index,
        "raw_text": raw_text,
        "trust_tier": CorpusTrustTier.VERIFIED_FORMAL,
        "verification_status": VerificationStatus.VERIFIED,
        "verifier": "lean4-kernel@4.10.0",
        "verification": ACCEPTED,
    }
    fields.update(overrides)
    return ReasoningStep(**fields)


def annotated_step(index: int = 0, **overrides: Any) -> ReasoningStep:
    fields: dict[str, Any] = {
        "step_index": index,
        "raw_text": RAW_STEP,
        "trust_tier": CorpusTrustTier.HUMAN_ANNOTATED,
        "operation_candidate": OperationAnnotation(
            label="INTRODUCE_HYPOTHESIS",
            annotator="prm800k-labeler-7f3",
            vocabulary="prm800k-rating",
        ),
    }
    fields.update(overrides)
    return ReasoningStep(**fields)


def trace(steps: tuple[ReasoningStep, ...] | None = None, **overrides: Any) -> ReasoningTrace:
    fields: dict[str, Any] = {
        "trace_id": "trace:1",
        "provenance": provenance(),
        "source_type": "lean4-tactic",
        "source_problem_id": "Mathlib/Algebra/Foo.lean:12",
        "raw_problem": RAW_PROBLEM,
        "steps": steps if steps is not None else (verified_step(),),
        "trust_tier": CorpusTrustTier.VERIFIED_FORMAL,
        "final_verification": ACCEPTED,
    }
    fields.update(overrides)
    return ReasoningTrace(**fields)


# -- losslessness ----------------------------------------------------------------------


def test_raw_bytes_survive_a_round_trip_unchanged() -> None:
    original = trace()
    restored = ReasoningTrace.from_dict(original.to_dict())
    assert restored.raw_problem.encode("utf-8") == RAW_PROBLEM.encode("utf-8")
    assert restored.steps[0].raw_text.encode("utf-8") == RAW_STEP.encode("utf-8")
    assert restored == original


def test_normalisation_lands_beside_raw_content_not_over_it() -> None:
    step = verified_step().with_normalization("intro h")
    assert step.normalized_text == "intro h"
    assert step.raw_text == RAW_STEP
    assert step.raw_sha256 == verified_step().raw_sha256


def test_a_step_with_no_raw_content_is_refused() -> None:
    with pytest.raises(ProvenanceViolation, match="raw_text"):
        verified_step(raw_text="")


def test_a_trace_with_no_raw_problem_is_refused() -> None:
    with pytest.raises(ProvenanceViolation, match="raw_problem"):
        trace(raw_problem="")


def test_deserialising_a_step_whose_raw_text_was_edited_is_refused() -> None:
    payload = trace().to_dict()
    payload["steps"][0]["raw_text"] = "intro h"  # digest left at the original value
    with pytest.raises(ProvenanceViolation, match="raw content changed"):
        ReasoningTrace.from_dict(payload)


def test_deserialising_a_trace_whose_problem_was_edited_is_refused() -> None:
    payload = trace().to_dict()
    payload["raw_problem"] = "Prove that sqrt 2 is irrational."
    with pytest.raises(ProvenanceViolation, match="raw problem changed"):
        ReasoningTrace.from_dict(payload)


# -- trust tiers cannot be upgraded ----------------------------------------------------


def test_a_verified_formal_step_needs_a_verifier_identifier() -> None:
    with pytest.raises(TrustViolation, match="names no verifier"):
        verified_step(verifier="  ")


def test_a_verified_formal_step_needs_a_verification_record() -> None:
    with pytest.raises(TrustViolation, match="no verification record"):
        verified_step(verification=None)


@pytest.mark.parametrize(
    "record",
    [
        VerificationRecord("lean4", "4.10.0", VerificationStatus.UNKNOWN, False),
        VerificationRecord("lean4", "4.10.0", VerificationStatus.REFUTED, False),
        VerificationRecord("lean4", "4.10.0", VerificationStatus.VERIFIED, False),
    ],
)
def test_a_verified_formal_step_needs_an_accepted_record(record: VerificationRecord) -> None:
    with pytest.raises(TrustViolation, match="verification record says"):
        verified_step(verification=record)


def test_a_deterministically_checked_step_is_held_to_the_same_bar() -> None:
    with pytest.raises(TrustViolation, match="no verification record"):
        verified_step(trust_tier=CorpusTrustTier.DETERMINISTICALLY_CHECKED, verification=None)


def test_an_annotated_step_needs_no_verifier() -> None:
    assert annotated_step().verifier == ""


def test_a_trace_cannot_claim_more_than_its_weakest_step() -> None:
    steps = (verified_step(0), annotated_step(1))
    with pytest.raises(TrustViolation, match="weakest step"):
        trace(steps)


def test_a_trace_may_claim_its_weakest_step_tier() -> None:
    steps = (verified_step(0), annotated_step(1))
    assert (
        trace(steps, trust_tier=CorpusTrustTier.HUMAN_ANNOTATED, final_verification=None).trust_tier
        is CorpusTrustTier.HUMAN_ANNOTATED
    )


def test_a_verified_formal_trace_needs_a_final_verification_record() -> None:
    with pytest.raises(TrustViolation, match="no final verification record"):
        trace(final_verification=None)


def test_a_verified_formal_trace_needs_a_named_final_verifier() -> None:
    nameless = VerificationRecord("", "4.10.0", VerificationStatus.VERIFIED, True)
    with pytest.raises(TrustViolation, match="names no verifier"):
        trace(final_verification=nameless)


# -- an operation candidate is an annotation -------------------------------------------


def test_an_annotated_operation_may_not_be_read_as_established() -> None:
    with pytest.raises(TrustViolation, match="may not be read as an established operation"):
        require_verified_operation(annotated_step())


def test_a_step_with_no_operation_candidate_refuses() -> None:
    with pytest.raises(TrustViolation, match="no operation candidate"):
        require_verified_operation(verified_step())


def test_an_operation_claiming_a_machine_tier_on_an_unverified_step_refuses() -> None:
    step = annotated_step(
        operation_candidate=OperationAnnotation(
            label="INTRODUCE_HYPOTHESIS",
            annotator="mining-script",
            annotation_tier=CorpusTrustTier.VERIFIED_FORMAL,
        )
    )
    with pytest.raises(TrustViolation, match="no verification record"):
        require_verified_operation(step)


def test_a_verifier_established_operation_reads_back() -> None:
    step = verified_step(
        operation_candidate=OperationAnnotation(
            label="intro",
            annotator="lean4-tactic-head",
            annotation_tier=CorpusTrustTier.DETERMINISTICALLY_CHECKED,
        )
    )
    assert require_verified_operation(step) == "intro"


# -- structural validation --------------------------------------------------------------


def test_step_indices_must_be_contiguous() -> None:
    with pytest.raises(ValueError, match="step indices"):
        trace((verified_step(0), verified_step(2)))


def test_a_trace_needs_at_least_one_step() -> None:
    with pytest.raises(ValueError, match="no steps"):
        trace(())


def test_a_step_cannot_depend_on_a_later_step() -> None:
    with pytest.raises(ValueError, match="not an earlier step"):
        verified_step(1, dependencies=(2,))


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_outside_the_unit_interval_is_refused(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        annotated_step(confidence=confidence)


# -- hashing ----------------------------------------------------------------------------


def test_trace_hash_is_stable_across_equal_content() -> None:
    assert trace().trace_hash == trace().trace_hash


def test_trace_hash_ignores_display_identity_and_import_time() -> None:
    other = trace(
        trace_id="trace:renamed",
        provenance=IngestionProvenance.from_dict(
            {**provenance().to_dict(), "imported_at": "2027-01-01T00:00:00+00:00"}
        ),
    )
    assert other.trace_hash == trace().trace_hash


@pytest.mark.parametrize(
    "overrides",
    [
        {"raw_problem": RAW_PROBLEM + " "},
        {"source_type": "nl-step-solution"},
        {"source_problem_id": "other:1"},
        {"final_answer": "irrational"},
        {"normalized_problem": "sqrt 2 is irrational"},
        {"schema_version": "arena-corpus-trace-v2.0.0"},
    ],
)
def test_trace_hash_changes_when_meaning_could_change(overrides: dict[str, Any]) -> None:
    assert trace(**overrides).trace_hash != trace().trace_hash


def test_trace_hash_changes_when_a_step_changes() -> None:
    edited = trace((verified_step(0, raw_text=RAW_STEP + "\n"),))
    assert edited.trace_hash != trace().trace_hash


def test_trace_hash_changes_when_provenance_changes() -> None:
    other = IngestionProvenance.from_dict({**provenance().to_dict(), "source_version": "deadbee"})
    assert trace(provenance=other).trace_hash != trace().trace_hash


def test_step_raw_digest_is_independent_of_annotation() -> None:
    plain = verified_step()
    annotated = plain.with_normalization(
        "intro h",
        operation_candidate=OperationAnnotation(label="intro", annotator="x"),
    )
    assert annotated.raw_sha256 == plain.raw_sha256
    assert annotated.to_dict()["raw_sha256"] == plain.to_dict()["raw_sha256"]
