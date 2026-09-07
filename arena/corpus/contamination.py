"""The contamination firewall: which sources are burned, and which may be trained on.

Two rules carry all the weight here, and both are computed rather than remembered.

**Exposure is transitive through derivation.**  ``mathlib4`` goal states were read during
Fitness V5 instrument design, so ``mathlib4`` is ``HISTORICALLY_EXPOSED``; every corpus
derived from it inherits that exposure and can never serve as clean OOD.  A human being
asked to recall that chain will eventually get it wrong, so :meth:`ContaminationRegistry.
is_exposed` walks the derivation graph instead.

**Refusal is the default.**  :meth:`ContaminationRegistry.may_train` answers ``False`` for
an unregistered source.  An unknown source is not a permission gap to be filled in later;
it is a source nobody has audited, and training on it is exactly the mistake this module
exists to prevent.

Registry data is loaded from ``artifacts/corpus/source_registry.json``.  ``HML_V3`` also
ships ``data/registry/datasets.yaml`` with trust tier / ``train_allowed`` / contamination
for 27 datasets; that file is *not* duplicated here.  It lives outside this repository, at
``/Users/moheet/Documents/ChatGPT/HML_V3/data/registry/datasets.yaml`` (verified present,
40 KB), and reading YAML would add a third-party dependency, so the reuse path is: convert it to
the ``SourceRecord`` fields below (``trust_tier``, ``never_train`` from ``train_allowed``,
``category`` from its contamination column) and feed the records to
:meth:`ContaminationRegistry.with_sources`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

CORPUS_CONTAMINATION_SCHEMA_VERSION = "arena-corpus-contamination-v1.0.0"

#: The ``schema`` value this loader was written against.
SOURCE_REGISTRY_SCHEMA = "arena-corpus-source-registry-v1.0.0"


class SplitCategory(StrEnum):
    """Split categories as defined in ``artifacts/corpus/source_registry.json``."""

    #: Read, tuned against, iterated on.  Reading it is what burns it.
    DEVELOPMENT = "DEVELOPMENT"
    #: Eligible for SFT/RL subject to licence and the never-train list.
    TRAINING_CANDIDATE = "TRAINING_CANDIDATE"
    #: A small capped slice pulled to answer a structural question about the source.
    SCOUT = "SCOUT"
    #: The single preregistered pool a candidate is scored on, then retired.
    PROMOTION = "PROMOTION"
    #: Distribution-shifted along a named axis; requires no prior reading.
    OOD = "OOD"
    #: Harness smoke tests only; never contributes a scientific number.
    ASSURANCE_ONLY = "ASSURANCE_ONLY"
    #: Already consumed by this project's design history.  Permanently burned.
    HISTORICALLY_EXPOSED = "HISTORICALLY_EXPOSED"
    #: Sealed until a preregistered unsealing condition fires.
    RESERVED_EVAL = "RESERVED_EVAL"


#: Categories whose members have been read by this project and are therefore burned.
EXPOSED_CATEGORIES = frozenset({SplitCategory.DEVELOPMENT, SplitCategory.HISTORICALLY_EXPOSED})

#: Categories that require a source to be unexposed, transitively.
CLEAN_ONLY_CATEGORIES = frozenset(
    {SplitCategory.OOD, SplitCategory.PROMOTION, SplitCategory.RESERVED_EVAL}
)

#: Categories that make a source, and anything derived from it, untrainable.
HELD_OUT_CATEGORIES = frozenset({SplitCategory.OOD, SplitCategory.RESERVED_EVAL})


class ContaminationViolation(RuntimeError):
    """Raised when a firewall rule would be broken, or when the answer is unknown."""


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One registered corpus source and the firewall facts about it."""

    #: Registry-native name, e.g. ``"mathlib4"``.  Used verbatim as the graph node id.
    source_id: str
    #: Split category the registry assigns.
    category: SplitCategory
    #: Explicit never-train marking from the registry.
    never_train: bool = False
    #: Registry trust vocabulary, kept verbatim rather than re-interpreted.
    trust_tier: str = "UNVERIFIED"
    #: Licence text as recorded; may be a description of why the licence is unclear.
    licence: str = ""
    #: True only when a licence file or dataset-card field was actually read.
    licence_verified: bool = False
    #: True when the licence forbids the use this project would make of it.
    licence_blocker: bool = False
    #: Sources this one is derived from.  Exposure flows along these edges.
    derived_from: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "category": self.category.value,
            "never_train": self.never_train,
            "trust_tier": self.trust_tier,
            "licence": self.licence,
            "licence_verified": self.licence_verified,
            "licence_blocker": self.licence_blocker,
            "derived_from": list(self.derived_from),
            "notes": self.notes,
        }


#: Derivation edges the registry states in prose (firewall rule FW-1) but does not encode
#: as data.  Child -> parents.  ``miniCTX-v2`` as a whole is a post-cutoff RESERVED_EVAL
#: set; only its ``mathlib`` configuration inherits mathlib4's exposure, so that
#: configuration is modelled as its own node rather than burning the whole benchmark.
MINICTX_MATHLIB_CONFIG = "miniCTX-v2 :: mathlib config"

DEFAULT_DERIVATION_EDGES: Mapping[str, tuple[str, ...]] = {
    "LeanDojo Benchmark 4 (data release)": ("mathlib4",),
    "FormL4 (Process-Driven Autoformalization in Lean 4)": ("mathlib4",),
    MINICTX_MATHLIB_CONFIG: ("mathlib4", "miniCTX-v2"),
    "Magnushammer premise selection in Isabelle (AFP-derived)": (
        "Isabelle Archive of Formal Proofs (AFP)",
    ),
    "Goedel-Prover Lean-workbook-proofs": ("Lean Workbook",),
    "PRM800K": ("Hendrycks MATH",),
    "ProofNet# (ProofNetSharp)": ("ProofNet (original)",),
    "ProofNet-Verified": ("ProofNet (original)",),
    "ProofNetVerif": ("ProofNet (original)",),
}

#: Nodes FW-1 requires that the registry file does not itself list as a source.
DEFAULT_EXTRA_SOURCES: tuple[SourceRecord, ...] = (
    SourceRecord(
        source_id=MINICTX_MATHLIB_CONFIG,
        category=SplitCategory.HISTORICALLY_EXPOSED,
        never_train=True,
        trust_tier="VERIFIED_FORMAL",
        licence="see miniCTX-v2",
        derived_from=DEFAULT_DERIVATION_EDGES[MINICTX_MATHLIB_CONFIG],
        notes=(
            "FW-1: inherits mathlib4 exposure, so it cannot be clean OOD, and inherits "
            "miniCTX-v2's seal, so it is not trainable."
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class ContaminationRegistry:
    """An immutable source graph that answers firewall questions by computation."""

    sources: Mapping[str, SourceRecord] = field(default_factory=dict)

    # -- construction ----------------------------------------------------------------

    @classmethod
    def from_records(cls, records: Iterable[SourceRecord]) -> Self:
        table: dict[str, SourceRecord] = {}
        for record in records:
            if record.source_id in table:
                raise ContaminationViolation(f"duplicate source id {record.source_id!r}")
            table[record.source_id] = record
        registry = cls(sources=table)
        registry.validate()
        return registry

    def with_sources(self, records: Iterable[SourceRecord]) -> Self:
        """Return a new registry with ``records`` added or replaced.

        Replacing a record goes through :meth:`validate`, so it cannot be used to smuggle
        an exposed source into a clean-only category.
        """

        incoming = list(records)
        replaced = {record.source_id for record in incoming}
        kept = [record for record in self.sources.values() if record.source_id not in replaced]
        return type(self).from_records([*kept, *incoming])

    # -- lookup ----------------------------------------------------------------------

    def require(self, source_id: str) -> SourceRecord:
        record = self.sources.get(source_id)
        if record is None:
            raise ContaminationViolation(
                f"{source_id!r} is not a registered source; it has no audited "
                "contamination status and must be treated as unusable."
            )
        return record

    def derivation_ancestors(self, source_id: str) -> frozenset[str]:
        """Sources ``source_id`` is derived from, transitively."""

        return self._closure(source_id, self._parent_edges())

    def derivation_descendants(self, source_id: str) -> frozenset[str]:
        """Sources derived from ``source_id``, transitively."""

        return self._closure(source_id, self._child_edges())

    # -- firewall rules --------------------------------------------------------------

    def is_exposed(self, source_id: str) -> bool:
        """True when this source, or anything it derives from, has been read."""

        record = self.require(source_id)
        if record.category in EXPOSED_CATEGORIES:
            return True
        return any(
            self.require(parent).category in EXPOSED_CATEGORIES
            for parent in self.derivation_ancestors(source_id)
        )

    def exposure_reasons(self, source_id: str) -> tuple[str, ...]:
        """The burned nodes that make ``source_id`` exposed, nearest first."""

        record = self.require(source_id)
        reasons: list[str] = []
        if record.category in EXPOSED_CATEGORIES:
            reasons.append(f"{source_id} is {record.category.value}")
        reasons.extend(
            f"derived from {parent}, which is {self.require(parent).category.value}"
            for parent in sorted(self.derivation_ancestors(source_id))
            if self.require(parent).category in EXPOSED_CATEGORIES
        )
        return tuple(reasons)

    def training_refusals(self, source_id: str) -> tuple[str, ...]:
        """Every reason training on ``source_id`` is refused.  Empty means allowed."""

        try:
            record = self.require(source_id)
        except ContaminationViolation as error:
            return (str(error),)

        refusals: list[str] = []
        if record.never_train:
            refusals.append(f"{source_id} is on the never-train list")
        if record.licence_blocker:
            refusals.append(f"{source_id} has a licence blocker: {record.licence}")
        if record.category in HELD_OUT_CATEGORIES:
            refusals.append(f"{source_id} is {record.category.value}")

        # Upward: this source's content contains its ancestors' content, so an ancestor's
        # never-train marking and held-out status both apply here.
        for other in sorted(self.derivation_ancestors(source_id)):
            ancestor = self.require(other)
            if ancestor.never_train:
                refusals.append(f"derived from {other}, which is never-train")
            if ancestor.category in HELD_OUT_CATEGORIES:
                refusals.append(f"derived from {other}, which is {ancestor.category.value}")

        # Downward: a sealed evaluation built from this source is contaminated by training
        # on it.  Only held-out status propagates this way; a descendant's never-train
        # marking is a statement about that descendant's own content, not about this one.
        for other in sorted(self.derivation_descendants(source_id)):
            descendant = self.require(other)
            if descendant.category in HELD_OUT_CATEGORIES:
                refusals.append(f"{other} is derived from it and is {descendant.category.value}")
        return tuple(refusals)

    def may_train(self, source_id: str) -> bool:
        """Fail-closed: an unknown source is never trainable."""

        return not self.training_refusals(source_id)

    def require_trainable(self, source_id: str) -> None:
        refusals = self.training_refusals(source_id)
        if refusals:
            raise ContaminationViolation(f"may not train on {source_id!r}: " + "; ".join(refusals))

    def reclassify(self, source_id: str, category: SplitCategory) -> Self:
        """Return a new registry with ``source_id`` moved to ``category``.

        Refuses any move that would launder an exposed source into a category whose whole
        value is that nobody has looked at it.
        """

        record = self.require(source_id)
        if category in CLEAN_ONLY_CATEGORIES and self.is_exposed(source_id):
            raise ContaminationViolation(
                f"cannot reclassify {source_id!r} as {category.value}: "
                + "; ".join(self.exposure_reasons(source_id))
            )
        moved = SourceRecord(
            source_id=record.source_id,
            category=category,
            never_train=record.never_train,
            trust_tier=record.trust_tier,
            licence=record.licence,
            licence_verified=record.licence_verified,
            licence_blocker=record.licence_blocker,
            derived_from=record.derived_from,
            notes=record.notes,
        )
        return self.with_sources([moved])

    def validate(self) -> None:
        """Refuse a registry that already violates the firewall."""

        for source_id, record in self.sources.items():
            for parent in record.derived_from:
                if parent not in self.sources:
                    raise ContaminationViolation(
                        f"{source_id!r} is derived from unregistered source {parent!r}"
                    )
            # Walking the closure of every node also rejects derivation cycles.
            self.derivation_ancestors(source_id)
            if record.category in CLEAN_ONLY_CATEGORIES and self.is_exposed(source_id):
                raise ContaminationViolation(
                    f"{source_id!r} is {record.category.value} but exposed: "
                    + "; ".join(self.exposure_reasons(source_id))
                )

    # -- internals -------------------------------------------------------------------

    def _parent_edges(self) -> Mapping[str, tuple[str, ...]]:
        return {key: record.derived_from for key, record in self.sources.items()}

    def _child_edges(self) -> Mapping[str, tuple[str, ...]]:
        children: dict[str, list[str]] = {key: [] for key in self.sources}
        for key, record in self.sources.items():
            for parent in record.derived_from:
                children.setdefault(parent, []).append(key)
        return {key: tuple(sorted(value)) for key, value in children.items()}

    def _closure(self, source_id: str, edges: Mapping[str, tuple[str, ...]]) -> frozenset[str]:
        self.require(source_id)
        seen: set[str] = set()
        queue = list(edges.get(source_id, ()))
        while queue:
            node = queue.pop()
            if node == source_id:
                raise ContaminationViolation(f"derivation cycle through {source_id!r}")
            if node in seen:
                continue
            self.require(node)
            seen.add(node)
            queue.extend(edges.get(node, ()))
        return frozenset(seen)


def load_source_registry(
    path: str | Path,
    *,
    derivation_edges: Mapping[str, tuple[str, ...]] | None = None,
    extra_sources: Iterable[SourceRecord] = DEFAULT_EXTRA_SOURCES,
) -> ContaminationRegistry:
    """Load ``artifacts/corpus/source_registry.json`` into a registry.

    The JSON records classifications but not derivation edges, so the FW-1 edges are
    supplied separately and default to :data:`DEFAULT_DERIVATION_EDGES`.
    """

    edges = DEFAULT_DERIVATION_EDGES if derivation_edges is None else derivation_edges
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = str(raw.get("schema", ""))
    if schema != SOURCE_REGISTRY_SCHEMA:
        raise ContaminationViolation(
            f"registry schema {schema!r} is not {SOURCE_REGISTRY_SCHEMA!r}"
        )

    records = [
        SourceRecord(
            source_id=str(entry["source"]),
            category=SplitCategory(entry["default_split_category"]),
            never_train=bool(entry["never_train"]),
            trust_tier=str(entry.get("trust_tier", "UNVERIFIED")),
            licence=str(entry.get("licence", "")),
            licence_verified=bool(entry.get("licence_verified", False)),
            licence_blocker=bool(entry.get("licence_blocker", False)),
            derived_from=tuple(edges.get(str(entry["source"]), ())),
            notes=str(entry.get("contamination_notes", "")),
        )
        for entry in raw["sources"]
    ]
    return ContaminationRegistry.from_records([*records, *extra_sources])


__all__ = [
    "CLEAN_ONLY_CATEGORIES",
    "CORPUS_CONTAMINATION_SCHEMA_VERSION",
    "DEFAULT_DERIVATION_EDGES",
    "DEFAULT_EXTRA_SOURCES",
    "EXPOSED_CATEGORIES",
    "HELD_OUT_CATEGORIES",
    "MINICTX_MATHLIB_CONFIG",
    "SOURCE_REGISTRY_SCHEMA",
    "ContaminationRegistry",
    "ContaminationViolation",
    "SourceRecord",
    "SplitCategory",
    "load_source_registry",
]
