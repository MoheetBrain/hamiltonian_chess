"""Typed provenance and trust tiers for imported scientific assets.

Every item imported from outside the frozen Arena world must carry one of these records.
The trust tier is mechanically enforced: :func:`require_oracle_grade` refuses to let a
model-or-heuristic-derived item (Tier C) act as canonical truth or as an oracle.

The guarded failure is concrete and historical: formal verification of a *mistranslated*
natural-language statement does not establish semantic equivalence to the original problem,
so "it type-checks" is not "it means the same thing".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self

PROVENANCE_SCHEMA_VERSION = "arena-provenance-v1.0.0"


class TrustTier(StrEnum):
    """Ordered from strongest to weakest.  Only A and B may ground an oracle."""

    #: Deterministically extracted and backed by the source system's own kernel/elaborator.
    A_NATIVE_VERIFIED = "A_NATIVE_VERIFIED"
    #: Derived from a Tier-A record and independently recomputed by Arena code.
    B_INDEPENDENTLY_REVERIFIED = "B_INDEPENDENTLY_REVERIFIED"
    #: Model or heuristic candidate semantics.  Never canonical truth, never an oracle.
    C_CANDIDATE_SEMANTICS = "C_CANDIDATE_SEMANTICS"
    #: Non-authoritative metadata: tags, difficulty labels, explanations.
    D_ANNOTATION = "D_ANNOTATION"


ORACLE_GRADE_TIERS = frozenset({TrustTier.A_NATIVE_VERIFIED, TrustTier.B_INDEPENDENTLY_REVERIFIED})


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Where an imported item came from and what may be believed about it."""

    #: Repository or dataset identity, e.g. "MoheetBrain/HML_V3".
    source_repo: str
    #: Branch, tag or dataset release the item was read from.
    source_ref: str
    #: Commit SHA or dataset version pinning the exact bytes.
    source_sha: str
    #: Path within the source.
    source_path: str
    #: The item's identifier in the source's own namespace.
    source_item_id: str
    #: SHA-256 of the exact source record, so a later drift is detectable.
    source_record_sha256: str
    #: Licence of the source material, required before any redistribution.
    license: str
    #: How much may be believed about this item.
    trust_tier: TrustTier
    #: The system that produced the record, e.g. "LEAN4 v4.10.0-rc1 elaborator".
    extraction_path: str
    #: What checked it, e.g. "arena structural re-derivation" or "lean kernel".
    verifier: str
    #: Identity of the adapter that transcribed it into Arena form.
    adapter_version: str
    #: Hash of the canonicalized Arena-side result, binding source to output.
    canonicalization_sha256: str
    #: Free-text limits a reader must know, e.g. "premise counts are lower bounds".
    caveats: tuple[str, ...] = ()
    schema_version: str = PROVENANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_repo": self.source_repo,
            "source_ref": self.source_ref,
            "source_sha": self.source_sha,
            "source_path": self.source_path,
            "source_item_id": self.source_item_id,
            "source_record_sha256": self.source_record_sha256,
            "license": self.license,
            "trust_tier": self.trust_tier.value,
            "extraction_path": self.extraction_path,
            "verifier": self.verifier,
            "adapter_version": self.adapter_version,
            "canonicalization_sha256": self.canonicalization_sha256,
            "caveats": list(self.caveats),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            source_repo=str(raw["source_repo"]),
            source_ref=str(raw["source_ref"]),
            source_sha=str(raw["source_sha"]),
            source_path=str(raw["source_path"]),
            source_item_id=str(raw["source_item_id"]),
            source_record_sha256=str(raw["source_record_sha256"]),
            license=str(raw["license"]),
            trust_tier=TrustTier(raw["trust_tier"]),
            extraction_path=str(raw["extraction_path"]),
            verifier=str(raw["verifier"]),
            adapter_version=str(raw["adapter_version"]),
            canonicalization_sha256=str(raw["canonicalization_sha256"]),
            caveats=tuple(str(item) for item in raw.get("caveats", ())),
            schema_version=str(raw.get("schema_version", PROVENANCE_SCHEMA_VERSION)),
        )


class TrustViolation(RuntimeError):
    """Raised when an item is asked to carry more authority than its tier allows."""


def require_oracle_grade(provenance: SourceProvenance, *, use: str) -> None:
    """Gate: only Tier A/B may ground truth.  Call this before every oracle use.

    This is deliberately a hard failure rather than a warning.  A Tier-C item silently
    accepted as truth is exactly how a benchmark starts measuring a model's own guesses.
    """

    if provenance.trust_tier not in ORACLE_GRADE_TIERS:
        raise TrustViolation(
            f"{provenance.source_item_id} is {provenance.trust_tier.value}; it may not be used "
            f"as {use}. Only {sorted(item.value for item in ORACLE_GRADE_TIERS)} may ground truth."
        )


__all__ = [
    "ORACLE_GRADE_TIERS",
    "PROVENANCE_SCHEMA_VERSION",
    "SourceProvenance",
    "TrustTier",
    "TrustViolation",
    "require_oracle_grade",
]
