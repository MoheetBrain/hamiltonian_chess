"""The durable, append-only language fitness record.

Written against ``docs/LANGUAGE_FITNESS_MEMORY.md`` (record schema V0).  That document is
``DESIGN_ONLY`` and specifies a SQLite index plus a content-addressed payload directory; this
module implements the **payload half and the identity discipline**, because
``arena/storage/db.py`` is outside this change's ownership.  Every divergence is listed in
:data:`SCHEMA_DIVERGENCES` rather than left for a reader to discover.

The three rules the document calls load-bearing are implemented here, not paraphrased:

1. **Append-only** (spec section 2.1).  One file per record, never overwritten.  There is no
   update and no delete; a correction is a new record carrying ``supersedes`` and
   ``supersede_reason``.  A refused or killed candidate **is a record** - failure is recorded,
   never quietly regenerated.
2. **Keying so that cross-condition reuse is impossible by construction** (spec section 2.2).
   ``record_id = "lfm:" + stable_hash(evaluation_identity)`` over exactly the eleven declared
   components, every one required and non-empty; a missing component is a refusal to write, and
   a duplicate ``record_id`` carrying a different ``result_hash`` is a hard error.  This is
   ``game_r_formal_v1.cache_identity``'s discipline lifted from the call cache to the ledger.
3. **Content hashes everywhere** (spec section 2.3).  ``canonical_json`` is the only serialiser,
   ``result_hash`` covers the result payload, and ``content_hash`` covers the whole record minus
   the wall clock, so two runs of one generation agree bit for bit on identity.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from arena.canonical.schema import canonical_json, stable_hash
from arena.fitness.metrics import Direction
from arena.storage.artifacts import ArtifactStore

RECORD_SCHEMA_VERSION = "arena-language-fitness-memory-v0.1.0"

#: Read this before trusting a record to conform.  Each entry names a spec requirement this
#: module does **not** meet, and why - a divergence that is written down is checkable; one that
#: is not is a silent claim of conformance.
SCHEMA_DIVERGENCES: tuple[str, ...] = (
    "Spec section 4 puts the index in new SQLite tables in arena/storage/db.py. This module "
    "writes only the content-addressed payload half; arena/storage/db.py is unchanged, so the "
    "database is not yet the index and the queries of spec section 5 are directory scans.",
    "Spec section 3.10 stores failure modes as rows with counts, severities and exemplars over "
    "the FailureClass / RowStatus vocabulary. V0's offline path has no Solver and therefore no "
    "solver-caused failure classes; failure_modes is a tuple of loop-level class names.",
    "Spec sections 3.4 and 3.9 require trajectory fields (trajectory_mode, risk_set_by_depth, "
    "beta_hat, hazard_by_depth). No trajectory world exists, so those fields are absent rather "
    "than filled with placeholders.",
    "Spec section 3.11 requires the full GateZeroEvidence, FrozenAdversaries and ParityReport "
    "field sets per gate. GateOutcome.evidence carries what the V0 gates actually computed and "
    "no more; an unmeasured gate field is absent, never defaulted.",
)

#: Fields excluded from :attr:`FitnessRecord.content_hash`.  Everything else is identity, so two
#: runs of one generation differ only in these.
WALL_CLOCK_FIELDS = ("created_at", "wall_clock_seconds")

#: ``docs/LONG_HORIZON_FITNESS_V0.md`` section 2.1, with its declared directions.  ``J_search``
#: and ``J_cost`` are MINIMIZE; the rest are MAXIMIZE.  A dimension with no reading is present
#: and ``NOT_MEASURED`` - never absent, and never defaulted to a number, because an unmeasured
#: dimension that reads as 0.0 or 1.0 is a lie about coverage.
FITNESS_DIMENSIONS: tuple[tuple[str, Direction], ...] = (
    ("J_solve", Direction.MAXIMIZE),
    ("J_horizon", Direction.MAXIMIZE),
    ("J_learn", Direction.MAXIMIZE),
    ("J_ood", Direction.MAXIMIZE),
    ("J_search", Direction.MINIMIZE),
    ("J_repair", Direction.MAXIMIZE),
    ("J_cost", Direction.MINIMIZE),
)
DIMENSION_DIRECTIONS: dict[str, Direction] = dict(FITNESS_DIMENSIONS)


class RecordIdentityViolation(ValueError):
    """An identity component is missing or empty.  Fail closed, as cache identity does."""


class FitnessMemoryIdentityViolation(ValueError):
    """Spec section 2.2 consequence 2: one identity, two different readings."""


#: The directive names this guard "the re-scoring guard"; the spec names the exception
#: ``FitnessMemoryIdentityViolation``.  They are the same object under both names.
RescoringConflict = FitnessMemoryIdentityViolation


class RecordScope(StrEnum):
    """Mirrors :class:`arena.experiments.game_r_formal_v1.CacheScope`.

    ``CROSS_CONDITION`` is never returned: it raises.  It is in the vocabulary so that the
    refusal can name the thing it refused.
    """

    FRESH = "FRESH"
    SAME_CONDITION_REUSE = "SAME_CONDITION_REUSE"
    CROSS_CONDITION = "CROSS_CONDITION"


class RecordStatus(StrEnum):
    """Spec section 3.1.  A refusal is a record, not a gap in the ledger."""

    COMPLETE = "COMPLETE"
    REFUSED = "REFUSED"
    ABORTED = "ABORTED"
    VOID = "VOID"


class DimensionStatus(StrEnum):
    MEASURED = "MEASURED"
    NOT_MEASURED = "NOT_MEASURED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class GateStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNDERPOWERED = "UNDERPOWERED"


class UnreportableReason(StrEnum):
    """Spec section 3.8's ``unreportable_reason`` vocabulary."""

    INSUFFICIENT_N = "INSUFFICIENT_N"
    VOID_FLOOR = "VOID_FLOOR"
    VOID_CEILING = "VOID_CEILING"
    THRESHOLD_UNREPRESENTABLE = "THRESHOLD_UNREPRESENTABLE"
    INSUFFICIENT_FAILURES = "INSUFFICIENT_FAILURES"
    NOT_MEASURED = "NOT_MEASURED"


# ------------------------------------------------------------------------------ components


@dataclass(frozen=True, slots=True)
class FitnessDimension:
    """One named dimension with the columns spec section 3.8 makes mandatory.

    ``unit_of_analysis`` and ``n_clusters`` are the two that make the programme's recurring
    failure - a statistic computed at a coarser granularity than the claim drawn from it - a
    thing a reader can query for instead of having to reconstruct.
    """

    name: str
    status: DimensionStatus
    direction: Direction
    metric: str = ""
    value: float | None = None
    lower: float | None = None
    upper: float | None = None
    confidence: float = 0.95
    estimator: str = ""
    n: int = 0
    n_clusters: int | None = None
    unit_of_analysis: str = ""
    reportable: bool = False
    unreportable_reason: str = UnreportableReason.NOT_MEASURED.value
    note: str = ""

    def __post_init__(self) -> None:
        if self.name not in DIMENSION_DIRECTIONS:
            raise ValueError(f"unknown fitness dimension {self.name!r}")
        if self.direction is not DIMENSION_DIRECTIONS[self.name]:
            raise ValueError(f"{self.name} is declared {DIMENSION_DIRECTIONS[self.name].value}")
        if self.name == "J_horizon" and self.status is DimensionStatus.MEASURED and not self.metric:
            # Spec section 3.8: an undeclared horizon metric is disqualifying.
            raise ValueError("J_horizon must declare which metric it reports")
        if self.status is DimensionStatus.MEASURED:
            if self.value is None:
                raise ValueError(f"{self.name} is MEASURED without a value")
            if self.n <= 0:
                raise ValueError(f"{self.name} is MEASURED without a sample size")
            if not self.estimator or not self.unit_of_analysis:
                raise ValueError(f"{self.name} is MEASURED without an estimator or unit")
        elif self.value is not None:
            raise ValueError(f"{self.name} is {self.status.value} but carries a value")
        if self.reportable and self.status is not DimensionStatus.MEASURED:
            raise ValueError(f"{self.name} is reportable without being measured")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "direction": self.direction.value,
            "metric": self.metric,
            "value": self.value,
            "lower": self.lower,
            "upper": self.upper,
            "confidence": self.confidence,
            "estimator": self.estimator,
            "n": self.n,
            "n_clusters": self.n_clusters,
            "unit_of_analysis": self.unit_of_analysis,
            "reportable": self.reportable,
            "unreportable_reason": self.unreportable_reason,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            name=str(raw["name"]),
            status=DimensionStatus(raw["status"]),
            direction=Direction(raw["direction"]),
            metric=str(raw.get("metric", "")),
            value=None if raw.get("value") is None else float(raw["value"]),
            lower=None if raw.get("lower") is None else float(raw["lower"]),
            upper=None if raw.get("upper") is None else float(raw["upper"]),
            confidence=float(raw.get("confidence", 0.95)),
            estimator=str(raw.get("estimator", "")),
            n=int(raw.get("n", 0)),
            n_clusters=None if raw.get("n_clusters") is None else int(raw["n_clusters"]),
            unit_of_analysis=str(raw.get("unit_of_analysis", "")),
            reportable=bool(raw.get("reportable", False)),
            unreportable_reason=str(
                raw.get("unreportable_reason", UnreportableReason.NOT_MEASURED.value)
            ),
            note=str(raw.get("note", "")),
        )

    @classmethod
    def not_measured(cls, name: str, note: str) -> Self:
        return cls(
            name=name,
            status=DimensionStatus.NOT_MEASURED,
            direction=DIMENSION_DIRECTIONS[name],
            unreportable_reason=UnreportableReason.NOT_MEASURED.value,
            note=note,
        )


@dataclass(frozen=True, slots=True)
class FitnessVector:
    """Seven named dimensions.  Deliberately **not** reducible to one number.

    There is no ``__float__``, no ``total()`` and no weighting.  ``measured()`` returns only the
    dimensions that carry a reading, which is what a Pareto front consumes.
    """

    dimensions: tuple[FitnessDimension, ...]

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.dimensions)
        if names != tuple(name for name, _ in FITNESS_DIMENSIONS):
            raise ValueError(
                "a fitness vector must carry every declared dimension, in declared order; "
                f"got {list(names)}"
            )

    def __getitem__(self, name: str) -> FitnessDimension:
        for item in self.dimensions:
            if item.name == name:
                return item
        raise KeyError(name)

    def measured(self) -> dict[str, float]:
        return {
            item.name: float(item.value)
            for item in self.dimensions
            if item.status is DimensionStatus.MEASURED and item.value is not None
        }

    def to_dict(self) -> dict[str, Any]:
        return {"dimensions": [item.to_dict() for item in self.dimensions]}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(tuple(FitnessDimension.from_dict(item) for item in raw["dimensions"]))

    @classmethod
    def build(cls, measured: Sequence[FitnessDimension], *, note: str) -> Self:
        supplied = {item.name: item for item in measured}
        if len(supplied) != len(measured):
            raise ValueError("a dimension was supplied twice")
        return cls(
            tuple(
                supplied.get(name, FitnessDimension.not_measured(name, note))
                for name, _ in FITNESS_DIMENSIONS
            )
        )


class InterventionClass(StrEnum):
    """Manual section 6.26.  Every candidate comparison SHALL be typed as exactly one of these.

    The class is not decoration: it determines the *fairness contract* (manual section 26) and
    therefore which causal claims the comparison is permitted to support.

    * ``R_ONLY`` holds the visible mathematical information fixed and varies only approved
      representation / morphology / interface structure.  It is the only class that may support a
      pure representation claim, and the only class for which visible-information parity is
      mandatory (section 12.3).  ``RSTAR`` is reserved for it (section 6.36).
    * ``P_CHANGE`` / ``O_CHANGE`` / ``T_CHANGE`` / ``A_CHANGE`` deliberately alter the cognitive
      interface, so strict visible-information parity is *not* required and MUST NOT be asserted.
      They estimate the system-level value of that intervention (section 26.3).
    * ``TAU_CHANGE`` and ``C_CHANGE`` move the tokenizer or the search controller -- both frozen
      in early comparisons (sections 6.13, 6.15).
    * ``JOINT`` changes more than one component.  It may be searched and even promoted as a system
      candidate, but component-level causal attribution requires later ablation (section 26.4).

    **Truth fidelity is universal and is never relaxed by any class** (manual correction 6).
    """

    R_ONLY = "R_ONLY"
    P_CHANGE = "P_CHANGE"
    O_CHANGE = "O_CHANGE"
    T_CHANGE = "T_CHANGE"
    A_CHANGE = "A_CHANGE"
    TAU_CHANGE = "TAU_CHANGE"
    C_CHANGE = "C_CHANGE"
    JOINT = "JOINT"

    @property
    def requires_visible_information_parity(self) -> bool:
        """Only ``R_ONLY`` claims to hold visible information fixed (manual sections 12.3, 26.2)."""

        return self is InterventionClass.R_ONLY

    @property
    def permits_representation_claim(self) -> bool:
        return self is InterventionClass.R_ONLY


#: Which intervention class a single gene family belongs to.
#:
#: The present fourteen-family genome is entirely surface/serialisation (Layer D), so every gene
#: here maps to ``R_ONLY``.  That is a **fact about the current genome, not a licence**: when the
#: meta-genome's O/P/S/A families land (docs/LANGUAGE_META_GENOME_V0.md) their genes MUST be added
#: here with their true class, or ``classify_intervention`` will silently mislabel an ontology
#: change as a representation change -- exactly the confusion manual section 26.3 forbids.
GENE_INTERVENTION_CLASS: dict[str, InterventionClass] = {
    "alphabet": InterventionClass.R_ONLY,
    "token_policy": InterventionClass.R_ONLY,
    "morphology": InterventionClass.R_ONLY,
    "grammar": InterventionClass.R_ONLY,
    "composition": InterventionClass.R_ONLY,
    "types": InterventionClass.R_ONLY,
    "binders": InterventionClass.R_ONLY,
    "state": InterventionClass.R_ONLY,
    "actions": InterventionClass.R_ONLY,
    "obligations": InterventionClass.R_ONLY,
    "evidence": InterventionClass.R_ONLY,
    "serialization": InterventionClass.R_ONLY,
    "redundancy": InterventionClass.R_ONLY,
    "error_locality": InterventionClass.R_ONLY,
}


class UnclassifiedGeneError(ValueError):
    """A gene changed whose intervention class is not declared.  Fail closed, never guess."""


def classify_intervention(genes: Sequence[str]) -> InterventionClass:
    """Type a mutation by the genes it actually changed (manual sections 6.26, 12.3).

    Fails closed on an unknown gene rather than defaulting to ``R_ONLY``: defaulting would let a
    future ontology or projection gene be reported as a pure representation effect.
    """

    if not genes:
        raise ValueError("a comparison with no changed gene has no intervention class")
    unknown = sorted({gene for gene in genes if gene not in GENE_INTERVENTION_CLASS})
    if unknown:
        raise UnclassifiedGeneError(
            f"no declared InterventionClass for gene(s) {unknown}. Add them to "
            "GENE_INTERVENTION_CLASS with their true class; refusing to assume R_ONLY."
        )
    classes = {GENE_INTERVENTION_CLASS[gene] for gene in genes}
    if len(classes) > 1:
        return InterventionClass.JOINT
    return classes.pop()


@dataclass(frozen=True, slots=True)
class GeneChangeRecord:
    gene: str
    from_value: str
    to_value: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MutationDescriptor:
    """Spec section 3.3: operator, parameters, and *which gene actually changed*.

    ``inert`` is measured on the rendered bytes of the evaluation pool, not inferred from the
    gene table: five of the fourteen gene families never reach the bytes at all, and which of
    the rest are live is a property of the arena's states, not of the genome.
    """

    operator: str
    proposal_id: str
    mutation_hash: str
    parameters: dict[str, Any] = field(default_factory=dict)
    gene_changes: tuple[GeneChangeRecord, ...] = ()
    evaluation_tier: str = ""
    soundness_risk: str = ""
    layer: str = "D"
    decision: str = "pending"
    inert: bool | None = None
    inert_evidence: str = ""

    def __post_init__(self) -> None:
        if not self.operator or not self.proposal_id or not self.mutation_hash:
            raise RecordIdentityViolation(
                "a mutation descriptor needs an operator, a proposal id and a mutation hash"
            )
        if not self.gene_changes:
            raise ValueError("a mutation descriptor must name the genes it changed")
        if self.layer == "A":
            raise ValueError("Layer A is the truth kernel and is never evolvable")

    @property
    def intervention_class(self) -> InterventionClass:
        """Manual section 6.26: derived from the genes actually changed, never asserted.

        Deriving rather than storing means a descriptor cannot claim ``R_ONLY`` while carrying an
        ontology gene, and an undeclared gene raises instead of defaulting.
        """

        return classify_intervention(self.changed_genes)

    @property
    def changed_genes(self) -> tuple[str, ...]:
        return tuple(item.gene for item in self.gene_changes)

    @property
    def n_genes_changed(self) -> int:
        return len(self.gene_changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "proposal_id": self.proposal_id,
            "mutation_hash": self.mutation_hash,
            "parameters": dict(self.parameters),
            "gene_changes": [item.to_dict() for item in self.gene_changes],
            "changed_genes": list(self.changed_genes),
            "n_genes_changed": self.n_genes_changed,
            # Manual section 6.26: mandatory on every comparison.  Derived, so it cannot drift
            # from the genes it describes.
            "intervention_class": self.intervention_class.value,
            "requires_visible_information_parity": (
                self.intervention_class.requires_visible_information_parity
            ),
            "permits_representation_claim": self.intervention_class.permits_representation_claim,
            "evaluation_tier": self.evaluation_tier,
            "soundness_risk": self.soundness_risk,
            "layer": self.layer,
            "decision": self.decision,
            "inert": self.inert,
            "inert_evidence": self.inert_evidence,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            operator=str(raw["operator"]),
            proposal_id=str(raw["proposal_id"]),
            mutation_hash=str(raw["mutation_hash"]),
            parameters=dict(raw.get("parameters", {})),
            gene_changes=tuple(
                GeneChangeRecord(str(i["gene"]), str(i["from_value"]), str(i["to_value"]))
                for i in raw.get("gene_changes", ())
            ),
            evaluation_tier=str(raw.get("evaluation_tier", "")),
            soundness_risk=str(raw.get("soundness_risk", "")),
            layer=str(raw.get("layer", "D")),
            decision=str(raw.get("decision", "pending")),
            inert=raw.get("inert"),
            inert_evidence=str(raw.get("inert_evidence", "")),
        )


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Spec section 3.4, restricted to the fields a horizon-1 diagnostic can honestly fill.

    ``pool_role`` and ``pool_disjoint_from`` are what make "selection and evaluation are
    separate" checkable after the fact instead of merely asserted at the time.
    """

    arena_id: str
    environment_version: str
    mechanism: str
    task_ids: tuple[str, ...]
    fidelity_level: int
    pool_id: str = ""
    pool_role: str = "DEV"
    horizon_bucket: str = "H1"
    n_clusters: int = 0
    pool_disjoint_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        missing = [
            key
            for key in ("arena_id", "environment_version", "mechanism")
            if not getattr(self, key)
        ]
        if missing:
            raise RecordIdentityViolation(f"evaluation context is missing components: {missing}")
        if self.fidelity_level < 0:
            raise ValueError("fidelity level must be non-negative")
        if len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("task ids must be unique")

    @property
    def task_set_hash(self) -> str:
        return stable_hash(sorted(self.task_ids))

    @property
    def ladder_level(self) -> str:
        return f"L{self.fidelity_level}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "arena_id": self.arena_id,
            "environment_version": self.environment_version,
            "mechanism": self.mechanism,
            "task_ids": list(self.task_ids),
            "task_set_hash": self.task_set_hash,
            "n_problems": len(self.task_ids),
            "n_clusters": self.n_clusters,
            "fidelity_level": self.fidelity_level,
            "ladder_level": self.ladder_level,
            "pool_id": self.pool_id,
            "pool_role": self.pool_role,
            "horizon_bucket": self.horizon_bucket,
            "pool_disjoint_from": list(self.pool_disjoint_from),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            arena_id=str(raw["arena_id"]),
            environment_version=str(raw["environment_version"]),
            mechanism=str(raw["mechanism"]),
            task_ids=tuple(str(item) for item in raw["task_ids"]),
            fidelity_level=int(raw["fidelity_level"]),
            pool_id=str(raw.get("pool_id", "")),
            pool_role=str(raw.get("pool_role", "DEV")),
            horizon_bucket=str(raw.get("horizon_bucket", "H1")),
            n_clusters=int(raw.get("n_clusters", 0)),
            pool_disjoint_from=tuple(str(item) for item in raw.get("pool_disjoint_from", ())),
        )

    @property
    def identity_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Spec section 3.5.  A stub declares itself a stub, by name and by flag.

    ``available``/``last_seen`` are not bureaucracy: the Solver named in a live preregistration
    was deleted from the local Ollama on 2026-09-08, and every measurement taken against it is
    permanently unreproducible.  The store must be able to answer which records those are.
    """

    name: str
    digest: str
    template_hash: str
    decoding_hash: str
    revision: str = "unversioned"
    tokenizer_id: str = "none:no-tokenizer-bound"
    tokenizer_exact: bool = False
    response_schema_hash: str = ""
    runtime_condition: str = "offline"
    available: bool = True
    is_stub: bool = False

    def __post_init__(self) -> None:
        missing = [
            key
            for key in (
                "name",
                "digest",
                "template_hash",
                "decoding_hash",
                "revision",
                "tokenizer_id",
                "runtime_condition",
            )
            if not getattr(self, key)
        ]
        if missing:
            raise RecordIdentityViolation(f"model identity is missing components: {missing}")

    @property
    def model_revision(self) -> str:
        """The form ``run_item`` already builds: solver revision plus tokenizer identity."""

        return f"{self.revision}|{self.tokenizer_id}"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "model_revision": self.model_revision}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            name=str(raw["name"]),
            digest=str(raw["digest"]),
            template_hash=str(raw["template_hash"]),
            decoding_hash=str(raw["decoding_hash"]),
            revision=str(raw.get("revision", "unversioned")),
            tokenizer_id=str(raw.get("tokenizer_id", "none:no-tokenizer-bound")),
            tokenizer_exact=bool(raw.get("tokenizer_exact", False)),
            response_schema_hash=str(raw.get("response_schema_hash", "")),
            runtime_condition=str(raw.get("runtime_condition", "offline")),
            available=bool(raw.get("available", True)),
            is_stub=bool(raw.get("is_stub", False)),
        )

    @property
    def identity_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    """Spec section 3.6.  Both exposure fields are required, and for the stated reason.

    V7's C10: a seal declared 8,766 exposed steps where the real figure was 21,632.  A single
    ``sealed: true`` boolean is exactly the field that hid it; two fields that must be
    reconciled cannot.
    """

    version: str
    split: str
    seal_state: str
    generator_version: str = ""
    declared_exposure_steps: int = 0
    measured_exposure_steps: int = 0

    def __post_init__(self) -> None:
        missing = [k for k in ("version", "split", "seal_state") if not getattr(self, k)]
        if missing:
            raise RecordIdentityViolation(f"dataset identity is missing components: {missing}")
        if self.declared_exposure_steps < 0 or self.measured_exposure_steps < 0:
            raise ValueError("exposure step counts must be non-negative")

    @property
    def exposure_reconciled(self) -> bool:
        return self.declared_exposure_steps == self.measured_exposure_steps

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "exposure_reconciled": self.exposure_reconciled}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            version=str(raw["version"]),
            split=str(raw["split"]),
            seal_state=str(raw["seal_state"]),
            generator_version=str(raw.get("generator_version", "")),
            declared_exposure_steps=int(raw.get("declared_exposure_steps", 0)),
            measured_exposure_steps=int(raw.get("measured_exposure_steps", 0)),
        )

    @property
    def identity_hash(self) -> str:
        return stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class Budget:
    """Spec section 3.7.  ``wall_clock_seconds`` is the only field that may vary between runs.

    ``cross_condition_calls`` must always be 0: a non-zero value means the harness raised and
    the record should not exist.
    """

    calls: int = 0
    tokens: int = 0
    wall_clock_seconds: float = 0.0
    cached_calls: int = 0
    fresh_calls: int = 0
    cross_condition_calls: int = 0
    completion_tokens: int = 0
    verifier_calls: int = 0
    budget_exceeded: bool = False

    def __post_init__(self) -> None:
        negative = [
            name
            for name in (
                "calls",
                "tokens",
                "wall_clock_seconds",
                "cached_calls",
                "fresh_calls",
                "cross_condition_calls",
                "completion_tokens",
                "verifier_calls",
            )
            if getattr(self, name) < 0
        ]
        if negative:
            raise ValueError(f"budget components must be non-negative: {negative}")
        if self.cross_condition_calls:
            raise ValueError("a cross-condition call means the harness should have raised")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            calls=int(raw.get("calls", 0)),
            tokens=int(raw.get("tokens", 0)),
            wall_clock_seconds=float(raw.get("wall_clock_seconds", 0.0)),
            cached_calls=int(raw.get("cached_calls", 0)),
            fresh_calls=int(raw.get("fresh_calls", 0)),
            cross_condition_calls=int(raw.get("cross_condition_calls", 0)),
            completion_tokens=int(raw.get("completion_tokens", 0)),
            verifier_calls=int(raw.get("verifier_calls", 0)),
            budget_exceeded=bool(raw.get("budget_exceeded", False)),
        )


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """One non-compensatory gate, storing its evidence rather than a verdict alone."""

    name: str
    status: GateStatus
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a gate outcome needs a name")

    @property
    def eliminated(self) -> bool:
        return self.status is GateStatus.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            name=str(raw["name"]),
            status=GateStatus(raw["status"]),
            detail=str(raw.get("detail", "")),
            evidence=dict(raw.get("evidence", {})),
        )


# ------------------------------------------------------------------------ record identity


#: Spec section 2.2, exactly eleven components, all required and all non-empty.
EVALUATION_IDENTITY_COMPONENTS = (
    "schema_version",
    "harness_version",
    "parent_genome_hash",
    "child_genome_hash",
    "mutation_hash",
    "environment_version",
    "task_set_hash",
    "model_digest",
    "model_revision",
    "decoding_hash",
    "ladder_level",
)

#: Spec section 2.2's grouping key.  Two records may be compared, differenced or pooled only
#: when their ``condition_id`` matches; a delta computed across two conditions is not a delta.
CONDITION_COMPONENTS = (
    "model_digest",
    "model_revision",
    "decoding_hash",
    "environment_version",
    "task_set_hash",
    "ladder_level",
)


def evaluation_identity(
    *,
    harness_version: str,
    parent_genome_hash: str,
    child_genome_hash: str,
    mutation: MutationDescriptor,
    evaluation_context: EvaluationContext,
    model: ModelIdentity,
    schema_version: str = RECORD_SCHEMA_VERSION,
) -> dict[str, str]:
    """The eleven-component identity.  A missing component is a refusal, not a blank slot."""

    identity = {
        "schema_version": schema_version,
        "harness_version": harness_version,
        "parent_genome_hash": parent_genome_hash,
        "child_genome_hash": child_genome_hash,
        "mutation_hash": mutation.mutation_hash,
        "environment_version": evaluation_context.environment_version,
        "task_set_hash": evaluation_context.task_set_hash,
        "model_digest": model.digest,
        "model_revision": model.model_revision,
        "decoding_hash": model.decoding_hash,
        "ladder_level": evaluation_context.ladder_level,
    }
    missing = [name for name in EVALUATION_IDENTITY_COMPONENTS if not identity.get(name)]
    if missing:
        raise RecordIdentityViolation(f"evaluation identity is missing components: {missing}")
    return identity


def record_id(identity: Mapping[str, str]) -> str:
    if tuple(sorted(identity)) != tuple(sorted(EVALUATION_IDENTITY_COMPONENTS)):
        raise RecordIdentityViolation(
            f"evaluation identity has the wrong components: {sorted(identity)}"
        )
    return f"lfm:{stable_hash(dict(identity))}"


def condition_id(identity: Mapping[str, str]) -> str:
    missing = [name for name in CONDITION_COMPONENTS if not identity.get(name)]
    if missing:
        raise RecordIdentityViolation(f"condition identity is missing components: {missing}")
    return stable_hash({name: identity[name] for name in CONDITION_COMPONENTS})


#: The directive calls this "the record key"; the spec calls it the evaluation identity.
record_key = evaluation_identity


# ---------------------------------------------------------------------------------- record


@dataclass(frozen=True, slots=True)
class FitnessRecord:
    """One (parent, mutation, environment, condition, level), scored or refused."""

    run_id: str
    generation: int
    harness_version: str
    parent_genome_id: str
    parent_genome_hash: str
    child_genome_id: str
    child_genome_hash: str
    mutation: MutationDescriptor
    evaluation_context: EvaluationContext
    model: ModelIdentity
    dataset: DatasetIdentity
    budget: Budget
    fitness_vector: FitnessVector
    uncertainty: dict[str, Any]
    failure_modes: tuple[str, ...]
    semantic_gate_results: tuple[GateOutcome, ...]
    provenance: dict[str, Any]
    created_at: str
    status: RecordStatus
    outcome: str
    void_code: str | None = None
    promoted: bool = False
    supersedes: str | None = None
    supersede_reason: str | None = None
    schema_version: str = RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.run_id or self.generation < 0:
            raise ValueError("a record needs a run id and a non-negative generation")
        if not self.harness_version:
            raise RecordIdentityViolation("a record needs a harness version")
        if self.parent_genome_id == self.child_genome_id:
            raise ValueError("a child cannot be its own parent")
        if self.schema_version != RECORD_SCHEMA_VERSION:
            raise ValueError(f"unsupported record schema {self.schema_version!r}")
        if not self.semantic_gate_results:
            raise ValueError("a record must carry its gate results, even when they all passed")
        if self.status is not RecordStatus.COMPLETE and not self.void_code:
            raise ValueError(f"a {self.status.value} record must carry a void code")
        if bool(self.supersedes) != bool(self.supersede_reason):
            raise ValueError("supersedes and supersede_reason are required together")
        # Spec section 3.9: a confirmatory record without a preregistration is malformed.
        if self.uncertainty.get("confirmatory") and not self.uncertainty.get("preregistration_id"):
            raise ValueError("a confirmatory record requires a preregistration_id")
        # Spec section 3.5: a token count from an inexact counter is not a measurement.
        if self.budget.tokens and not self.model.tokenizer_exact:
            raise ValueError("token counts require an exact tokenizer")

    @property
    def identity(self) -> dict[str, str]:
        return evaluation_identity(
            harness_version=self.harness_version,
            parent_genome_hash=self.parent_genome_hash,
            child_genome_hash=self.child_genome_hash,
            mutation=self.mutation,
            evaluation_context=self.evaluation_context,
            model=self.model,
            schema_version=self.schema_version,
        )

    @property
    def record_id(self) -> str:
        return record_id(self.identity)

    @property
    def condition_id(self) -> str:
        return condition_id(self.identity)

    @property
    def result_hash(self) -> str:
        """Spec section 2.3: the hash of the result payload, so an in-place edit is detectable."""

        return stable_hash(
            {
                "fitness_vector": self.fitness_vector.to_dict(),
                "uncertainty": dict(self.uncertainty),
                "failure_modes": list(self.failure_modes),
                "semantic_gate_results": [item.to_dict() for item in self.semantic_gate_results],
                "status": self.status.value,
                "void_code": self.void_code,
                "promoted": self.promoted,
                "budget": {
                    key: value
                    for key, value in self.budget.to_dict().items()
                    if key not in WALL_CLOCK_FIELDS
                },
            }
        )

    def _identity_payload(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("created_at")
        payload["budget"] = {
            key: value for key, value in payload["budget"].items() if key not in WALL_CLOCK_FIELDS
        }
        return payload

    @property
    def content_hash(self) -> str:
        """Deterministic over everything except the wall clock."""

        return stable_hash(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "generation": self.generation,
            "harness_version": self.harness_version,
            "parent_genome_id": self.parent_genome_id,
            "parent_genome_hash": self.parent_genome_hash,
            "child_genome_id": self.child_genome_id,
            "child_genome_hash": self.child_genome_hash,
            "mutation": self.mutation.to_dict(),
            "evaluation_context": self.evaluation_context.to_dict(),
            "model": self.model.to_dict(),
            "dataset": self.dataset.to_dict(),
            "budget": self.budget.to_dict(),
            "fitness_vector": self.fitness_vector.to_dict(),
            "uncertainty": dict(self.uncertainty),
            "failure_modes": list(self.failure_modes),
            "semantic_gate_results": [item.to_dict() for item in self.semantic_gate_results],
            "provenance": dict(self.provenance),
            "status": self.status.value,
            "outcome": self.outcome,
            "void_code": self.void_code,
            "promoted": self.promoted,
            "supersedes": self.supersedes,
            "supersede_reason": self.supersede_reason,
            "created_at": self.created_at,
        }

    def to_stored_dict(self) -> dict[str, Any]:
        """The on-disk form: the record plus every derived identity a reader needs."""

        return {
            **self.to_dict(),
            "record_id": self.record_id,
            "condition_id": self.condition_id,
            "identity": self.identity,
            "result_hash": self.result_hash,
            "content_hash": self.content_hash,
            "schema_divergences": list(SCHEMA_DIVERGENCES),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        record = cls(
            run_id=str(raw["run_id"]),
            generation=int(raw["generation"]),
            harness_version=str(raw["harness_version"]),
            parent_genome_id=str(raw["parent_genome_id"]),
            parent_genome_hash=str(raw["parent_genome_hash"]),
            child_genome_id=str(raw["child_genome_id"]),
            child_genome_hash=str(raw["child_genome_hash"]),
            mutation=MutationDescriptor.from_dict(raw["mutation"]),
            evaluation_context=EvaluationContext.from_dict(raw["evaluation_context"]),
            model=ModelIdentity.from_dict(raw["model"]),
            dataset=DatasetIdentity.from_dict(raw["dataset"]),
            budget=Budget.from_dict(raw["budget"]),
            fitness_vector=FitnessVector.from_dict(raw["fitness_vector"]),
            uncertainty=dict(raw.get("uncertainty", {})),
            failure_modes=tuple(str(item) for item in raw.get("failure_modes", ())),
            semantic_gate_results=tuple(
                GateOutcome.from_dict(item) for item in raw["semantic_gate_results"]
            ),
            provenance=dict(raw.get("provenance", {})),
            created_at=str(raw["created_at"]),
            status=RecordStatus(raw["status"]),
            outcome=str(raw["outcome"]),
            void_code=raw.get("void_code"),
            promoted=bool(raw.get("promoted", False)),
            supersedes=raw.get("supersedes"),
            supersede_reason=raw.get("supersede_reason"),
            schema_version=str(raw.get("schema_version", RECORD_SCHEMA_VERSION)),
        )
        for name, computed in (
            ("content_hash", record.content_hash),
            ("result_hash", record.result_hash),
            ("record_id", record.record_id),
        ):
            stored = raw.get(name)
            if stored is not None and stored != computed:
                raise FitnessMemoryIdentityViolation(
                    f"record {record.child_genome_id} does not reproduce its stored {name}"
                )
        return record


# ----------------------------------------------------------------------------------- store


@dataclass(frozen=True, slots=True)
class AppendResult:
    record: FitnessRecord
    scope: RecordScope
    path: Path
    rows_path: Path


class EvolutionRecordStore:
    """Append-only records under ``artifacts/evolution/<run_id>/<condition_id>/``.

    Sharding by ``condition_id`` (spec section 4) makes "all records comparable to this one" a
    directory listing, and makes an accidental cross-condition read visible in a path.  Storage
    goes through the existing :class:`~arena.storage.artifacts.ArtifactStore`; this class adds
    only the append-only guarantee and the re-scoring guard.  There is no update method and no
    delete method: a correction is a new record that names what it supersedes.
    """

    RELATIVE_ROOT = "evolution"

    def __init__(self, store: ArtifactStore, run_id: str) -> None:
        if not run_id or "/" in run_id or run_id.startswith("."):
            raise ValueError(f"unusable run id {run_id!r}")
        self.store = store
        self.run_id = run_id
        self.directory = Path(self.RELATIVE_ROOT) / run_id
        self._index: dict[str, tuple[str, str]] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return self.store.root / self.directory

    def _load(self) -> None:
        if self._loaded:
            return
        for record in self.records():
            self._index[record.record_id] = (record.result_hash, record.content_hash)
        self._loaded = True

    def record_paths(self) -> tuple[Path, ...]:
        if not self.path.is_dir():
            return ()
        return tuple(sorted(self.path.glob("*/lfm-*.json")))

    def records(self) -> tuple[FitnessRecord, ...]:
        return tuple(
            FitnessRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in self.record_paths()
        )

    @staticmethod
    def _stem(record: FitnessRecord) -> str:
        return "lfm-" + record.record_id.removeprefix("lfm:")

    def append(
        self, record: FitnessRecord, *, rows: Sequence[Mapping[str, Any]] = ()
    ) -> AppendResult:
        """Store one record and its per-item rows, or refuse.

        * an unseen ``record_id`` is ``FRESH``;
        * an identical re-append (same identity, same ``result_hash``, same content) is
          ``SAME_CONDITION_REUSE`` and writes nothing new - resuming a run is legitimate;
        * anything else raises :class:`FitnessMemoryIdentityViolation`.

        ``rows`` is written even when empty: spec section 4 says a record whose rows file is
        absent is a summary, not a fitness record, and a summary cannot be re-analysed at a
        different granularity - which is the precondition for catching granularity substitution
        at all.
        """

        if record.run_id != self.run_id:
            raise ValueError(f"record belongs to run {record.run_id!r}, not {self.run_id!r}")
        self._load()
        shard = self.directory / record.condition_id
        stem = self._stem(record)
        json_path = shard / f"{stem}.json"
        rows_path = shard / f"{stem}.rows.jsonl"

        previous = self._index.get(record.record_id)
        if previous is not None:
            stored_result, stored_content = previous
            if stored_result != record.result_hash:
                raise FitnessMemoryIdentityViolation(
                    f"{record.child_genome_id} already has a record under this identity with a "
                    f"different result_hash ({stored_result[:16]} vs {record.result_hash[:16]}); "
                    f"the pipeline is not deterministic under a fully specified identity "
                    f"({RecordScope.CROSS_CONDITION.value} is impossible by construction, so this "
                    "is a bug, not a reuse)"
                )
            if stored_content != record.content_hash:
                raise FitnessMemoryIdentityViolation(
                    f"{record.child_genome_id} reproduces its result but not its record content "
                    f"({stored_content[:16]} vs {record.content_hash[:16]})"
                )
            return AppendResult(
                record,
                RecordScope.SAME_CONDITION_REUSE,
                self.store.root / json_path,
                self.store.root / rows_path,
            )

        if (self.store.root / json_path).exists():
            raise FitnessMemoryIdentityViolation(f"record file already exists: {json_path}")
        artifact = self.store.write_json(json_path, record.to_stored_dict())
        rows_text = "".join(canonical_json(dict(row)) + "\n" for row in rows)
        rows_artifact = self.store.write_text(rows_path, rows_text)
        self._index[record.record_id] = (record.result_hash, record.content_hash)
        return AppendResult(record, RecordScope.FRESH, artifact.path, rows_artifact.path)

    def summary(self) -> dict[str, Any]:
        records = self.records()
        return {
            "run_id": self.run_id,
            "directory": str(self.directory),
            "records": len(records),
            "conditions": sorted({item.condition_id for item in records}),
            "record_ids": [item.record_id for item in records],
            "content_hashes": [item.content_hash for item in records],
            "manifest_hash": stable_hash([item.content_hash for item in records]),
            "schema_version": RECORD_SCHEMA_VERSION,
        }


def dumps(record: FitnessRecord) -> str:
    """Canonical JSON for one record; the same spelling the store writes."""

    return canonical_json(record.to_stored_dict())


__all__ = [
    "CONDITION_COMPONENTS",
    "DIMENSION_DIRECTIONS",
    "EVALUATION_IDENTITY_COMPONENTS",
    "FITNESS_DIMENSIONS",
    "RECORD_SCHEMA_VERSION",
    "SCHEMA_DIVERGENCES",
    "WALL_CLOCK_FIELDS",
    "AppendResult",
    "Budget",
    "DatasetIdentity",
    "DimensionStatus",
    "EvaluationContext",
    "EvolutionRecordStore",
    "FitnessDimension",
    "FitnessMemoryIdentityViolation",
    "FitnessRecord",
    "FitnessVector",
    "GateOutcome",
    "GateStatus",
    "GeneChangeRecord",
    "ModelIdentity",
    "MutationDescriptor",
    "RecordIdentityViolation",
    "RecordScope",
    "RecordStatus",
    "RescoringConflict",
    "UnreportableReason",
    "condition_id",
    "dumps",
    "evaluation_identity",
    "record_id",
    "record_key",
]
