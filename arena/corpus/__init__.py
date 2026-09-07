"""Provenance and contamination substrate for heterogeneous reasoning corpora.

Three small, fail-closed modules:

* :mod:`arena.corpus.contamination` -- which sources are burned, and which may be trained
  on, computed over a derivation graph rather than remembered.
* :mod:`arena.corpus.provenance` -- what must be known about an item before it may be
  ingested, and how to prove later that it was not altered.
* :mod:`arena.corpus.trace` -- a source-independent reasoning-trace *research record*.
  It is deliberately not part of canonical Sigma.
"""

from arena.corpus.contamination import (
    CLEAN_ONLY_CATEGORIES,
    EXPOSED_CATEGORIES,
    HELD_OUT_CATEGORIES,
    ContaminationRegistry,
    ContaminationViolation,
    SourceRecord,
    SplitCategory,
    load_source_registry,
)
from arena.corpus.provenance import (
    ARENA_TRUST_TIER_MAP,
    MACHINE_CHECKED_TIERS,
    TRUST_TIER_ORDER,
    CorpusTrustTier,
    IngestionProvenance,
    ProvenanceViolation,
    ingest,
    trust_rank,
    weakest,
)
from arena.corpus.trace import (
    OperationAnnotation,
    ReasoningStep,
    ReasoningTrace,
    require_verified_operation,
)

__all__ = [
    "ARENA_TRUST_TIER_MAP",
    "CLEAN_ONLY_CATEGORIES",
    "EXPOSED_CATEGORIES",
    "HELD_OUT_CATEGORIES",
    "MACHINE_CHECKED_TIERS",
    "TRUST_TIER_ORDER",
    "ContaminationRegistry",
    "ContaminationViolation",
    "CorpusTrustTier",
    "IngestionProvenance",
    "OperationAnnotation",
    "ProvenanceViolation",
    "ReasoningStep",
    "ReasoningTrace",
    "SourceRecord",
    "SplitCategory",
    "ingest",
    "load_source_registry",
    "require_verified_operation",
    "trust_rank",
    "weakest",
]
