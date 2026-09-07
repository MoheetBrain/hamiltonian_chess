"""Ingestion provenance for heterogeneous corpus items.

Relationship to :mod:`arena.provenance`
---------------------------------------
:mod:`arena.provenance` is the *canonical* gate.  Its :class:`~arena.provenance.TrustTier`
(A/B/C/D) answers one question -- may this item ground an oracle? -- and
:func:`~arena.provenance.require_oracle_grade` enforces the answer.  That vocabulary is
deliberately coarse because only A and B may touch canonical semantics.

This module is the *ingestion* record for research corpora, which are mostly Tier C/D and
would all collapse into one bucket under the canonical vocabulary.  It therefore keeps the
registry's finer five-tier vocabulary (:class:`CorpusTrustTier`), and does not replace the
canonical scheme: :meth:`IngestionProvenance.to_source_provenance` projects an ingestion
record onto a :class:`~arena.provenance.SourceProvenance` via :data:`ARENA_TRUST_TIER_MAP`,
so anything crossing into canonical code passes through the existing gate rather than a
parallel one.  :class:`~arena.provenance.TrustViolation` is reused for tier failures.

Everything here is fail-closed.  An item with no licence, no content hash, or an import
timestamp that does not parse cannot be constructed at all, so it can never reach storage
and be discovered later with its provenance missing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Self

from arena.corpus.contamination import CLEAN_ONLY_CATEGORIES, EXPOSED_CATEGORIES, SplitCategory
from arena.provenance import SourceProvenance, TrustTier, TrustViolation
from arena.storage.hashes import file_sha256

CORPUS_PROVENANCE_SCHEMA_VERSION = "arena-corpus-provenance-v1.0.0"

_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")

#: Licence strings that assert nothing.  Any of these is treated as "no licence".
_EMPTY_LICENCES: Final = frozenset({"", "unknown", "unverified", "none", "tbd", "n/a"})


class CorpusTrustTier(StrEnum):
    """Registry trust vocabulary, ordered strongest first by :data:`TRUST_TIER_ORDER`."""

    #: A proof assistant produced or checked the artifact.
    VERIFIED_FORMAL = "VERIFIED_FORMAL"
    #: Checked by an exact mechanical procedure that is not a proof assistant.
    DETERMINISTICALLY_CHECKED = "DETERMINISTICALLY_CHECKED"
    #: Correctness rests on human labelling, with no mechanical check.
    HUMAN_ANNOTATED = "HUMAN_ANNOTATED"
    #: Produced by a language model.  Candidate semantics only.
    MODEL_GENERATED = "MODEL_GENERATED"
    #: No verification path established at all.
    ANNOTATION_UNVERIFIED = "ANNOTATION_UNVERIFIED"


#: Strongest first.  Index is the tier's rank.
TRUST_TIER_ORDER: Final[tuple[CorpusTrustTier, ...]] = (
    CorpusTrustTier.VERIFIED_FORMAL,
    CorpusTrustTier.DETERMINISTICALLY_CHECKED,
    CorpusTrustTier.HUMAN_ANNOTATED,
    CorpusTrustTier.MODEL_GENERATED,
    CorpusTrustTier.ANNOTATION_UNVERIFIED,
)

#: Tiers whose claim rests on a machine, and which therefore owe a verification record.
MACHINE_CHECKED_TIERS: Final = frozenset(
    {CorpusTrustTier.VERIFIED_FORMAL, CorpusTrustTier.DETERMINISTICALLY_CHECKED}
)

#: Projection onto the canonical gate in :mod:`arena.provenance`.
ARENA_TRUST_TIER_MAP: Final[dict[CorpusTrustTier, TrustTier]] = {
    CorpusTrustTier.VERIFIED_FORMAL: TrustTier.A_NATIVE_VERIFIED,
    CorpusTrustTier.DETERMINISTICALLY_CHECKED: TrustTier.B_INDEPENDENTLY_REVERIFIED,
    CorpusTrustTier.HUMAN_ANNOTATED: TrustTier.C_CANDIDATE_SEMANTICS,
    CorpusTrustTier.MODEL_GENERATED: TrustTier.C_CANDIDATE_SEMANTICS,
    CorpusTrustTier.ANNOTATION_UNVERIFIED: TrustTier.D_ANNOTATION,
}


def trust_rank(tier: CorpusTrustTier) -> int:
    """0 is strongest.  Use ranks, never enum member order, to compare tiers."""

    return TRUST_TIER_ORDER.index(tier)


def weakest(tiers: tuple[CorpusTrustTier, ...]) -> CorpusTrustTier:
    """The weakest tier present.  A record is only as trustworthy as its worst part."""

    if not tiers:
        raise TrustViolation("cannot take the weakest tier of an empty sequence")
    return max(tiers, key=trust_rank)


def require_at_least(tier: CorpusTrustTier, floor: CorpusTrustTier, *, use: str) -> None:
    if trust_rank(tier) > trust_rank(floor):
        raise TrustViolation(f"{tier.value} is weaker than {floor.value}; it may not be {use}")


class ProvenanceViolation(RuntimeError):
    """Raised when an item's provenance is missing, malformed, or no longer matches."""


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True, slots=True)
class IngestionProvenance:
    """What must be known about an item before it may enter the corpus.

    Construction validates every field.  There is no partially provenanced item.
    """

    #: Registry-native source name, matching ``SourceRecord.source_id``.
    source_id: str
    #: Commit SHA, release tag or dataset revision pinning the exact bytes.
    source_version: str
    #: Licence of the source material.  A placeholder is not a licence.
    licence: str
    #: The item's identifier in the source's own namespace.
    source_item_id: str
    #: SHA-256 of the exact ingested bytes, lowercase hex.
    content_hash: str
    #: ISO-8601 import timestamp, timezone-aware.
    imported_at: str
    #: Name of the code that read the source, e.g. ``"leandojo-jsonl-adapter"``.
    extractor: str
    #: Version of that code, so a later extraction change is visible.
    extractor_version: str
    #: How much may be believed about the item's content.
    trust_tier: CorpusTrustTier
    #: The source's registry classification at import time.
    contamination_category: SplitCategory
    #: The split this item is being imported *for*.
    intended_split: SplitCategory
    #: Explicit never-train marking carried from the registry.
    never_train: bool = False
    #: Limits a reader must know before using the item.
    caveats: tuple[str, ...] = ()
    schema_version: str = CORPUS_PROVENANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "source_version",
            "source_item_id",
            "extractor",
            "extractor_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ProvenanceViolation(f"{name} is required; refusing to ingest without it")

        if self.licence.strip().lower() in _EMPTY_LICENCES:
            raise ProvenanceViolation(
                f"{self.source_item_id!r} has no usable licence ({self.licence!r}); "
                "an unlicensed item may not be ingested or redistributed"
            )

        if not _SHA256_PATTERN.fullmatch(self.content_hash):
            raise ProvenanceViolation(
                f"{self.source_item_id!r} has content_hash {self.content_hash!r}, which is not "
                "a lowercase hex SHA-256; without it later alteration is undetectable"
            )

        try:
            parsed = datetime.fromisoformat(self.imported_at)
        except ValueError as error:
            raise ProvenanceViolation(
                f"imported_at {self.imported_at!r} is not ISO-8601"
            ) from error
        if parsed.tzinfo is None:
            raise ProvenanceViolation(f"imported_at {self.imported_at!r} has no timezone")

        if self.never_train and self.intended_split is SplitCategory.TRAINING_CANDIDATE:
            raise ProvenanceViolation(
                f"{self.source_item_id!r} is never-train and may not be imported as "
                "TRAINING_CANDIDATE"
            )

        if (
            self.intended_split in CLEAN_ONLY_CATEGORIES
            and self.contamination_category in EXPOSED_CATEGORIES
        ):
            raise ProvenanceViolation(
                f"{self.source_item_id!r} comes from a "
                f"{self.contamination_category.value} source and may not be imported as "
                f"{self.intended_split.value}"
            )

    # -- verification ------------------------------------------------------------------

    def verify_content(self, content: bytes) -> None:
        """Re-derive the hash and refuse if the bytes have changed since import."""

        actual = content_sha256(content)
        if actual != self.content_hash:
            raise ProvenanceViolation(
                f"{self.source_item_id!r} was altered after import: recorded "
                f"{self.content_hash}, recomputed {actual}"
            )

    def verify_file(self, path: str | Path) -> None:
        """Same check against a file on disk, streaming rather than loading it."""

        actual = file_sha256(path)
        if actual != self.content_hash:
            raise ProvenanceViolation(
                f"{self.source_item_id!r} no longer matches {path}: recorded "
                f"{self.content_hash}, recomputed {actual}"
            )

    # -- bridge to the canonical gate ---------------------------------------------------

    def to_source_provenance(
        self, *, source_path: str, canonicalization_sha256: str, verifier: str
    ) -> SourceProvenance:
        """Project onto :mod:`arena.provenance` so canonical code keeps its own gate."""

        return SourceProvenance(
            source_repo=self.source_id,
            source_ref=self.source_version,
            source_sha=self.source_version,
            source_path=source_path,
            source_item_id=self.source_item_id,
            source_record_sha256=self.content_hash,
            license=self.licence,
            trust_tier=ARENA_TRUST_TIER_MAP[self.trust_tier],
            extraction_path=f"{self.extractor}@{self.extractor_version}",
            verifier=verifier,
            adapter_version=self.schema_version,
            canonicalization_sha256=canonicalization_sha256,
            caveats=self.caveats,
        )

    # -- serialization ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_version": self.source_version,
            "licence": self.licence,
            "source_item_id": self.source_item_id,
            "content_hash": self.content_hash,
            "imported_at": self.imported_at,
            "extractor": self.extractor,
            "extractor_version": self.extractor_version,
            "trust_tier": self.trust_tier.value,
            "contamination_category": self.contamination_category.value,
            "intended_split": self.intended_split.value,
            "never_train": self.never_train,
            "caveats": list(self.caveats),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            source_id=str(raw["source_id"]),
            source_version=str(raw["source_version"]),
            licence=str(raw["licence"]),
            source_item_id=str(raw["source_item_id"]),
            content_hash=str(raw["content_hash"]),
            imported_at=str(raw["imported_at"]),
            extractor=str(raw["extractor"]),
            extractor_version=str(raw["extractor_version"]),
            trust_tier=CorpusTrustTier(raw["trust_tier"]),
            contamination_category=SplitCategory(raw["contamination_category"]),
            intended_split=SplitCategory(raw["intended_split"]),
            never_train=bool(raw.get("never_train", False)),
            caveats=tuple(str(item) for item in raw.get("caveats", ())),
            schema_version=str(raw.get("schema_version", CORPUS_PROVENANCE_SCHEMA_VERSION)),
        )


def ingest(
    content: bytes,
    *,
    source_id: str,
    source_version: str,
    licence: str,
    source_item_id: str,
    extractor: str,
    extractor_version: str,
    trust_tier: CorpusTrustTier,
    contamination_category: SplitCategory,
    intended_split: SplitCategory,
    never_train: bool = False,
    caveats: tuple[str, ...] = (),
    imported_at: str | None = None,
) -> IngestionProvenance:
    """Build a provenance record from the actual bytes, hashing them here.

    The hash is never accepted from a caller: a hash supplied alongside content is a hash
    that was never checked against it.
    """

    stamp = imported_at or datetime.now(UTC).isoformat()
    return IngestionProvenance(
        source_id=source_id,
        source_version=source_version,
        licence=licence,
        source_item_id=source_item_id,
        content_hash=content_sha256(content),
        imported_at=stamp,
        extractor=extractor,
        extractor_version=extractor_version,
        trust_tier=trust_tier,
        contamination_category=contamination_category,
        intended_split=intended_split,
        never_train=never_train,
        caveats=caveats,
    )


__all__ = [
    "ARENA_TRUST_TIER_MAP",
    "CORPUS_PROVENANCE_SCHEMA_VERSION",
    "MACHINE_CHECKED_TIERS",
    "TRUST_TIER_ORDER",
    "CorpusTrustTier",
    "IngestionProvenance",
    "ProvenanceViolation",
    "content_sha256",
    "ingest",
    "require_at_least",
    "trust_rank",
    "weakest",
]
