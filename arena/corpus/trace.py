"""Source-independent reasoning-trace records.

**These are research records, not canonical mathematics.**  A :class:`ReasoningTrace` is
deliberately not part of canonical Sigma and nothing in :mod:`arena.canonical` may treat
one as ground truth.  It exists so that heterogeneous step-level data -- Lean tactic
transitions, PRM800K human step ratings, natural-language solutions -- can be held in one
shape long enough to be counted and compared, with the difference in what is actually
*known* about each one preserved rather than flattened.

Three properties are enforced in code, not asserted in prose.

**Losslessness.**  ``raw_text`` and ``raw_problem`` hold the source's own bytes.  Any
normalisation lands in a separate field beside the raw one, never over it:
:meth:`ReasoningStep.with_normalization` cannot touch ``raw_text``, and
:meth:`ReasoningTrace.from_dict` recomputes every raw digest and refuses a record whose
raw content changed in transit.

**Trust tiers do not upgrade.**  A step at a machine-checked tier must name a verifier and
carry an accepted :class:`~arena.canonical.schema.VerificationRecord`, and a trace can
never claim a tier stronger than its weakest step.  A prior audit of the estate found that
the richest step annotations are all unverified while everything verified is
single-operation; the two must not be able to borrow each other's authority.

**An operation label is an annotation.**  ``operation_candidate`` is an
:class:`OperationAnnotation`, and the only way to read one as established is
:func:`require_verified_operation`, which refuses unless a verifier actually established
it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Any, Self

from arena.canonical.schema import VerificationRecord, VerificationStatus, stable_hash
from arena.corpus.provenance import (
    MACHINE_CHECKED_TIERS,
    CorpusTrustTier,
    IngestionProvenance,
    ProvenanceViolation,
    trust_rank,
    weakest,
)
from arena.provenance import TrustViolation

CORPUS_TRACE_SCHEMA_VERSION = "arena-corpus-trace-v1.0.0"


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OperationAnnotation:
    """A claimed reasoning operation.  An annotation, never canonical truth.

    The label is kept beside the evidence for it, so a reader can never see the label
    without also seeing who asserted it and on what basis.
    """

    #: The claimed operation, in whatever vocabulary the annotator used.
    label: str
    #: Who or what asserted it: a human labeller id, a model name, a mining script.
    annotator: str
    #: How much may be believed about the *label*, independent of the step's own tier.
    annotation_tier: CorpusTrustTier = CorpusTrustTier.ANNOTATION_UNVERIFIED
    #: The annotator's vocabulary, e.g. ``"prm800k-rating"`` or ``"lean-tactic-head"``.
    vocabulary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "annotator": self.annotator,
            "annotation_tier": self.annotation_tier.value,
            "vocabulary": self.vocabulary,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            label=str(raw["label"]),
            annotator=str(raw["annotator"]),
            annotation_tier=CorpusTrustTier(
                raw.get("annotation_tier", CorpusTrustTier.ANNOTATION_UNVERIFIED)
            ),
            vocabulary=str(raw.get("vocabulary", "")),
        )


@dataclass(frozen=True, slots=True)
class ReasoningStep:
    """One step of a trace, with its raw content and everything claimed about it."""

    step_index: int
    #: The source's own bytes for this step.  Never normalised in place.
    raw_text: str
    #: How much may be believed about this step's content.
    trust_tier: CorpusTrustTier
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    #: Identifier of what checked the step, e.g. ``"lean4-kernel@4.10.0"``.
    verifier: str = ""
    verification: VerificationRecord | None = None
    #: Annotator confidence in [0, 1] where the source supplies one.
    confidence: float | None = None
    #: Opaque reference into whatever state store holds the pre-state, if any.
    state_before_ref: str | None = None
    state_after_ref: str | None = None
    operation_candidate: OperationAnnotation | None = None
    #: Objects the step claims to act on, in the source's own identifiers.
    target: tuple[str, ...] = ()
    arguments: tuple[str, ...] = ()
    #: The justification the source gives, verbatim.
    warrant: str | None = None
    #: Indices of earlier steps this one depends on.
    dependencies: tuple[int, ...] = ()
    #: Normalised rendering, stored *beside* ``raw_text``.
    normalized_text: str | None = None

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError(f"step_index must be non-negative, got {self.step_index}")
        if not self.raw_text:
            raise ProvenanceViolation(
                f"step {self.step_index} has no raw_text; a step with no source content "
                "cannot be recorded losslessly"
            )
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        for dependency in self.dependencies:
            if not 0 <= dependency < self.step_index:
                raise ValueError(
                    f"step {self.step_index} depends on {dependency}, which is not an earlier step"
                )
        if self.trust_tier in MACHINE_CHECKED_TIERS:
            self._require_verification_evidence()

    def _require_verification_evidence(self) -> None:
        if not self.verifier.strip():
            raise TrustViolation(
                f"step {self.step_index} claims {self.trust_tier.value} but names no "
                "verifier; a machine-checked tier requires the machine's identity"
            )
        if self.verification is None:
            raise TrustViolation(
                f"step {self.step_index} claims {self.trust_tier.value} but carries no "
                "verification record"
            )
        if not (
            self.verification.accepted and self.verification.status is VerificationStatus.VERIFIED
        ):
            raise TrustViolation(
                f"step {self.step_index} claims {self.trust_tier.value} but its "
                f"verification record says {self.verification.status.value} / "
                f"accepted={self.verification.accepted}"
            )

    @property
    def raw_sha256(self) -> str:
        """Digest of the raw content alone.  Normalisation cannot change it."""

        return _text_sha256(self.raw_text)

    def with_normalization(
        self, normalized_text: str, *, operation_candidate: OperationAnnotation | None = None
    ) -> ReasoningStep:
        """Attach normalised content beside the raw content.

        ``raw_text`` is not a parameter, so no caller can overwrite it through this path;
        the digest is re-checked afterwards so no subclass or future edit can either.
        """

        updated = replace(
            self,
            normalized_text=normalized_text,
            operation_candidate=(
                self.operation_candidate if operation_candidate is None else operation_candidate
            ),
        )
        if updated.raw_sha256 != self.raw_sha256:
            raise ProvenanceViolation(
                f"normalisation altered the raw content of step {self.step_index}"
            )
        return updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "raw_text": self.raw_text,
            "raw_sha256": self.raw_sha256,
            "trust_tier": self.trust_tier.value,
            "verification_status": self.verification_status.value,
            "verifier": self.verifier,
            "verification": (
                None
                if self.verification is None
                else {
                    "verifier": self.verification.verifier,
                    "verifier_version": self.verification.verifier_version,
                    "status": self.verification.status.value,
                    "accepted": self.verification.accepted,
                    "details": self.verification.details,
                    "certificate_hash": self.verification.certificate_hash,
                }
            ),
            "confidence": self.confidence,
            "state_before_ref": self.state_before_ref,
            "state_after_ref": self.state_after_ref,
            "operation_candidate": (
                None if self.operation_candidate is None else self.operation_candidate.to_dict()
            ),
            "target": list(self.target),
            "arguments": list(self.arguments),
            "warrant": self.warrant,
            "dependencies": list(self.dependencies),
            "normalized_text": self.normalized_text,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        record = raw.get("verification")
        step = cls(
            step_index=int(raw["step_index"]),
            raw_text=str(raw["raw_text"]),
            trust_tier=CorpusTrustTier(raw["trust_tier"]),
            verification_status=VerificationStatus(
                raw.get("verification_status", VerificationStatus.UNKNOWN)
            ),
            verifier=str(raw.get("verifier", "")),
            verification=(
                None
                if record is None
                else VerificationRecord(
                    verifier=str(record["verifier"]),
                    verifier_version=str(record["verifier_version"]),
                    status=VerificationStatus(record["status"]),
                    accepted=bool(record["accepted"]),
                    details=str(record.get("details", "")),
                    certificate_hash=record.get("certificate_hash"),
                )
            ),
            confidence=None if raw.get("confidence") is None else float(raw["confidence"]),
            state_before_ref=raw.get("state_before_ref"),
            state_after_ref=raw.get("state_after_ref"),
            operation_candidate=(
                None
                if raw.get("operation_candidate") is None
                else OperationAnnotation.from_dict(raw["operation_candidate"])
            ),
            target=tuple(str(item) for item in raw.get("target", ())),
            arguments=tuple(str(item) for item in raw.get("arguments", ())),
            warrant=raw.get("warrant"),
            dependencies=tuple(int(item) for item in raw.get("dependencies", ())),
            normalized_text=raw.get("normalized_text"),
        )
        recorded = raw.get("raw_sha256")
        if recorded is not None and recorded != step.raw_sha256:
            raise ProvenanceViolation(
                f"step {step.step_index} raw content changed since serialization: "
                f"recorded {recorded}, recomputed {step.raw_sha256}"
            )
        return step


def require_verified_operation(step: ReasoningStep) -> str:
    """Return the step's operation label only when a verifier established it.

    This is the sole sanctioned reader of ``operation_candidate``.  It refuses for every
    annotated-but-unchecked step, which is most of the estate.
    """

    if step.operation_candidate is None:
        raise TrustViolation(f"step {step.step_index} has no operation candidate")
    annotation = step.operation_candidate
    if annotation.annotation_tier not in MACHINE_CHECKED_TIERS:
        raise TrustViolation(
            f"step {step.step_index} operation {annotation.label!r} is "
            f"{annotation.annotation_tier.value} from {annotation.annotator!r}; it is an "
            "annotation and may not be read as an established operation"
        )
    if step.trust_tier not in MACHINE_CHECKED_TIERS or step.verification is None:
        raise TrustViolation(
            f"step {step.step_index} operation {annotation.label!r} claims "
            f"{annotation.annotation_tier.value} but the step itself is "
            f"{step.trust_tier.value} with no verification record"
        )
    return annotation.label


@dataclass(frozen=True, slots=True)
class ReasoningTrace:
    """A whole reasoning trace as imported.  A research record, never canonical Sigma."""

    trace_id: str
    provenance: IngestionProvenance
    #: Free-form family label, e.g. ``"lean4-tactic"`` or ``"nl-step-solution"``.
    source_type: str
    #: The problem's identifier in the source's own namespace.
    source_problem_id: str
    #: The problem statement's own bytes.
    raw_problem: str
    steps: tuple[ReasoningStep, ...]
    #: The declared tier for the trace as a whole.  Can never exceed the weakest step.
    trust_tier: CorpusTrustTier
    final_answer: str | None = None
    final_verification: VerificationRecord | None = None
    #: Normalised problem statement, stored *beside* ``raw_problem``.
    normalized_problem: str | None = None
    schema_version: str = CORPUS_TRACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.raw_problem:
            raise ProvenanceViolation(
                f"{self.trace_id!r} has no raw_problem; the source statement must be kept"
            )
        if not self.steps:
            raise ValueError(f"{self.trace_id!r} has no steps")
        expected = tuple(range(len(self.steps)))
        actual = tuple(step.step_index for step in self.steps)
        if actual != expected:
            raise ValueError(f"{self.trace_id!r} step indices are {actual}, expected {expected}")

        floor = weakest(tuple(step.trust_tier for step in self.steps))
        if trust_rank(self.trust_tier) < trust_rank(floor):
            raise TrustViolation(
                f"{self.trace_id!r} claims {self.trust_tier.value} but its weakest step is "
                f"{floor.value}; a trace is only as trustworthy as its weakest step"
            )
        if self.trust_tier in MACHINE_CHECKED_TIERS and self.final_verification is None:
            raise TrustViolation(
                f"{self.trace_id!r} claims {self.trust_tier.value} but carries no final "
                "verification record"
            )
        if self.trust_tier in MACHINE_CHECKED_TIERS and not self.final_verification.verifier:  # type: ignore[union-attr]
            raise TrustViolation(
                f"{self.trace_id!r} claims {self.trust_tier.value} but its final "
                "verification record names no verifier"
            )

    @property
    def raw_problem_sha256(self) -> str:
        return _text_sha256(self.raw_problem)

    @property
    def trace_hash(self) -> str:
        """Deterministic hash of the content that could change the trace's meaning.

        Excludes ``trace_id`` (a display identity, matching
        :attr:`arena.canonical.schema.CanonicalTrajectory.content_hash`) and the ingestion
        timestamp, and includes ``schema_version`` so a schema change cannot silently
        produce a colliding hash.
        """

        payload = self.to_dict()
        payload.pop("trace_id", None)
        provenance = dict(payload["provenance"])
        provenance.pop("imported_at", None)
        payload["provenance"] = provenance
        return stable_hash(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "provenance": self.provenance.to_dict(),
            "source_type": self.source_type,
            "source_problem_id": self.source_problem_id,
            "raw_problem": self.raw_problem,
            "raw_problem_sha256": self.raw_problem_sha256,
            "steps": [step.to_dict() for step in self.steps],
            "trust_tier": self.trust_tier.value,
            "final_answer": self.final_answer,
            "final_verification": (
                None
                if self.final_verification is None
                else {
                    "verifier": self.final_verification.verifier,
                    "verifier_version": self.final_verification.verifier_version,
                    "status": self.final_verification.status.value,
                    "accepted": self.final_verification.accepted,
                    "details": self.final_verification.details,
                    "certificate_hash": self.final_verification.certificate_hash,
                }
            ),
            "normalized_problem": self.normalized_problem,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        record = raw.get("final_verification")
        trace = cls(
            trace_id=str(raw["trace_id"]),
            provenance=IngestionProvenance.from_dict(raw["provenance"]),
            source_type=str(raw["source_type"]),
            source_problem_id=str(raw["source_problem_id"]),
            raw_problem=str(raw["raw_problem"]),
            steps=tuple(ReasoningStep.from_dict(item) for item in raw["steps"]),
            trust_tier=CorpusTrustTier(raw["trust_tier"]),
            final_answer=raw.get("final_answer"),
            final_verification=(
                None
                if record is None
                else VerificationRecord(
                    verifier=str(record["verifier"]),
                    verifier_version=str(record["verifier_version"]),
                    status=VerificationStatus(record["status"]),
                    accepted=bool(record["accepted"]),
                    details=str(record.get("details", "")),
                    certificate_hash=record.get("certificate_hash"),
                )
            ),
            normalized_problem=raw.get("normalized_problem"),
            schema_version=str(raw.get("schema_version", CORPUS_TRACE_SCHEMA_VERSION)),
        )
        recorded = raw.get("raw_problem_sha256")
        if recorded is not None and recorded != trace.raw_problem_sha256:
            raise ProvenanceViolation(
                f"{trace.trace_id!r} raw problem changed since serialization: recorded "
                f"{recorded}, recomputed {trace.raw_problem_sha256}"
            )
        return trace


__all__ = [
    "CORPUS_TRACE_SCHEMA_VERSION",
    "OperationAnnotation",
    "ReasoningStep",
    "ReasoningTrace",
    "require_verified_operation",
]
