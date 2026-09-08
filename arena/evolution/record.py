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
   ``record_id = "lfm:" + stable_hash(evaluation_identity)`` over exactly the declared
   components, every one required and non-empty; a missing component is a refusal to write, and
   a duplicate ``record_id`` carrying a different ``result_hash`` is a hard error.  This is
   ``game_r_formal_v1.cache_identity``'s discipline lifted from the call cache to the ledger.
3. **Content hashes everywhere** (spec section 2.3).  ``canonical_json`` is the only serialiser,
   ``result_hash`` covers the result payload, and ``content_hash`` covers the whole record minus
   the wall clock and the proposal bookkeeping, so two runs of one generation agree bit for bit
   on identity.

Schema ``v0.2.0`` closes three red-team findings (``docs/HC_V0_RED_TEAM.md``).  Each is closed at
the level of what a record *can represent*, never by adding a warning string:

* **RT-13 - free stochastic redraws.**  The identity is now *semantic experimental identity*:
  what was evaluated, on what, by whom, under which conditions, as which replicate.  Proposal
  bookkeeping - ``proposal_id``, ``mutation_hash``, ``created_at`` - is named in
  :data:`BOOKKEEPING_FIELDS`, kept out of the identity **and** out of every hash, so re-rolling
  any of it yields the *same* record, absorbed as ``SAME_CONDITION_REUSE``.  A genuine second
  draw requires an authorised :class:`ReplicateAuthorisation`, which is a declaration with an
  authoriser, a reason and a plan - not a nonce.
* **RT-04 - REFERENCE evidence pooled with SOLVER evidence.**  :class:`EvidenceActor` is an
  identity *and* a condition component, so the two land under different ``record_id``s and in
  different ``condition_id`` shards; a query that would mix them raises
  :class:`ActorPoolingViolation`; and a ``REFERENCE`` record cannot carry a fitness reading at
  all, so reference data can never be counted as Solver capability.
* **RT-16 - stub numbers that look like results.**  A :class:`FitnessVector` carries the
  :class:`EvaluationMode` and :class:`EvidenceActor` that produced it, and refuses to hold a
  numeric ``J_*`` under ``EXECUTABILITY_STUB`` or under ``REFERENCE``.  A stub reading is
  therefore *unrepresentable* as fitness; it goes into :class:`DiagnosticReadings`, whose keys
  may never be a fitness dimension name.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from arena.canonical.schema import canonical_json, stable_hash
from arena.fitness.metrics import Direction
from arena.storage.artifacts import ArtifactStore

#: Bumped from ``v0.1.0`` by the RT-13 / RT-04 / RT-16 fixes, which change the identity, add
#: required components and change what a fitness vector may hold.  ``FitnessRecord.from_dict``
#: refuses any other version outright: there is no migration path and no field defaulting, so a
#: ``v0.1.0`` record on disk stays readable only by ``v0.1.0`` code.  Rewriting stored records to
#: look conformant is precisely the thing an append-only ledger exists to prevent.
RECORD_SCHEMA_VERSION = "arena-language-fitness-memory-v0.2.0"

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
    "Proposal bookkeeping (BOOKKEEPING_FIELDS: proposal_id, mutation_hash, created_at, "
    "wall_clock_seconds) is stored but is covered by no hash. That is the RT-13 fix and it is a "
    "real trade: those four fields are editable in place without detection. They are labels, not "
    "measurements - the semantic content of the mutation is covered by the derived "
    "MutationDescriptor.intervention_hash, which is inside content_hash.",
)

#: Fields excluded from :attr:`FitnessRecord.content_hash`.  Everything else is identity, so two
#: runs of one generation differ only in these.
WALL_CLOCK_FIELDS = ("created_at", "wall_clock_seconds")

#: RT-13.  Proposal bookkeeping: who *asked* for the evaluation, not *what was evaluated*.
#:
#: These are excluded from the evaluation identity **and** from ``result_hash`` / ``content_hash``,
#: so re-rolling one cannot produce a second record under any name: two records differing only in
#: bookkeeping are byte-identical after this filter and the store absorbs the second as
#: ``SAME_CONDITION_REUSE``.  Anything *else* that differs under one identity still raises - the
#: worst an arbitrary extra field can do is force a refusal, never buy an independent draw.
PROPOSAL_BOOKKEEPING_FIELDS = ("proposal_id", "mutation_hash")

#: Everything a hash deliberately does not cover, in one place so the trade is checkable.
BOOKKEEPING_FIELDS = WALL_CLOCK_FIELDS + PROPOSAL_BOOKKEEPING_FIELDS

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


class UnauthorisedReplicateError(ValueError):
    """RT-13.  A replicate beyond the primary draw was claimed without an authorisation.

    A second draw of one experiment is legitimate *and must stay possible* - it is how a
    stochastic evaluator's variance is measured at all.  What must not be possible is taking one
    silently, so the price of a replicate is a declaration: who authorised it, why, and under
    which replication plan.  That is auditable; a re-rolled hash is not.
    """


class FitnessRepresentationError(TypeError):
    """A fitness vector claims a reading its mode or actor cannot produce.

    Deliberately a :class:`TypeError`: under ``EXECUTABILITY_STUB`` a numeric ``J_solve`` is not
    a wrong number, it is a value of the wrong kind, and the object refuses to exist.
    """


class StubFitnessNotRepresentable(FitnessRepresentationError):
    """RT-16.  A stub reading is not a scientific fitness reading and cannot be stored as one."""


class ReferenceFitnessNotRepresentable(FitnessRepresentationError):
    """RT-04.  Reference evidence is not Solver capability and cannot be stored as fitness."""


class ActorPoolingViolation(ValueError):
    """RT-04.  A query would have returned ``REFERENCE`` and ``SOLVER`` records as one set."""


class EvaluationMode(StrEnum):
    """What kind of thing produced the readings in a record.

    The mode is an identity component, so a stub record and a scientific record of the same
    (parent, child, condition) are different records that can never be pooled or substituted.
    """

    #: A real evaluator whose readings are admissible as evidence, subject to the usual gates.
    SCIENTIFIC = "SCIENTIFIC"
    #: ``docs/HC_V0_RED_TEAM.md`` RT-16: the loop's plumbing exercised by a deterministic stub.
    #: Executability only.  Under this mode the fitness dimensions are structurally incapable of
    #: holding a number - see :class:`FitnessVector`.
    EXECUTABILITY_STUB = "EXECUTABILITY_STUB"

    @property
    def permits_scientific_fitness(self) -> bool:
        return self is EvaluationMode.SCIENTIFIC


class EvidenceActor(StrEnum):
    """Who chose the actions the readings summarise.

    The same two members, spelled the same way, as ``arena.trajectory.schema.Actor`` - the
    vocabulary is cross-checked by ``tests/evolution/test_actor_identity.py`` rather than shared
    by import, so the fitness ledger does not depend on the trajectory package to load.

    ``REFERENCE`` evidence is legitimate and valuable: it is source proof, calibration,
    demonstration and replay verification.  It is *not* a measurement of a policy, so it may
    never carry a fitness reading and may never be pooled with ``SOLVER`` evidence.
    """

    SOLVER = "SOLVER"
    REFERENCE = "REFERENCE"

    @property
    def permits_capability_claim(self) -> bool:
        return self is EvidenceActor.SOLVER


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
    #: RT-16 / RT-04.  A number *was* produced, and it is not a fitness reading: the evaluator was
    #: a stub, or the actor was the reference proof.  Distinct from ``NOT_MEASURED`` because the
    #: honest statement is "measured, and inadmissible", not "never attempted"; the number itself
    #: lives in :class:`DiagnosticReadings`, under a name that is not a fitness dimension.
    NOT_REPRESENTABLE = "NOT_REPRESENTABLE"


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
    #: RT-16: produced by ``EvaluationMode.EXECUTABILITY_STUB``.
    EXECUTABILITY_STUB = "EXECUTABILITY_STUB"
    #: RT-04: produced by ``EvidenceActor.REFERENCE`` - source proof, not Solver capability.
    REFERENCE_ACTOR_NOT_A_SOLVER_RESULT = "REFERENCE_ACTOR_NOT_A_SOLVER_RESULT"


#: The only reasons a dimension may be ``NOT_REPRESENTABLE``: each names a *structural* reason the
#: reading is inadmissible, so the status can never be used as a general-purpose escape hatch.
NOT_REPRESENTABLE_REASONS: tuple[str, ...] = (
    UnreportableReason.EXECUTABILITY_STUB.value,
    UnreportableReason.REFERENCE_ACTOR_NOT_A_SOLVER_RESULT.value,
)


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
        if (
            self.status is DimensionStatus.NOT_REPRESENTABLE
            and self.unreportable_reason not in NOT_REPRESENTABLE_REASONS
        ):
            raise ValueError(
                f"{self.name} is NOT_REPRESENTABLE without a structural reason; "
                f"expected one of {list(NOT_REPRESENTABLE_REASONS)}"
            )

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

    @classmethod
    def not_representable(cls, name: str, *, reason: UnreportableReason, note: str) -> Self:
        """A reading exists and is inadmissible as fitness (RT-16, RT-04).

        There is no ``value`` parameter, and no overload that takes one: the number cannot be
        carried here even by a caller who wants to.
        """

        return cls(
            name=name,
            status=DimensionStatus.NOT_REPRESENTABLE,
            direction=DIMENSION_DIRECTIONS[name],
            unreportable_reason=reason.value,
            note=note,
        )


@dataclass(frozen=True, slots=True)
class FitnessVector:
    """Seven named dimensions, plus the mode and actor that licence them.

    Deliberately **not** reducible to one number: there is no ``__float__``, no ``total()`` and no
    weighting.  ``measured()`` returns only the dimensions that carry a reading, which is what a
    Pareto front consumes.

    The mode and the actor are *part of the value*, not context a caller remembers to check
    (RT-16, RT-04).  A vector produced by ``EXECUTABILITY_STUB``, or by the ``REFERENCE`` actor,
    cannot hold a number in any dimension - the constructor refuses, so there is no object to
    persist, rank, or read back.  This is why the fix is not a warning string: a reader cannot
    encounter a stub ``J_solve`` of 0.75 because no such vector can be built.
    """

    dimensions: tuple[FitnessDimension, ...]
    evaluation_mode: EvaluationMode
    actor: EvidenceActor

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.dimensions)
        if names != tuple(name for name, _ in FITNESS_DIMENSIONS):
            raise ValueError(
                "a fitness vector must carry every declared dimension, in declared order; "
                f"got {list(names)}"
            )
        numeric = sorted(
            item.name for item in self.dimensions if item.status is DimensionStatus.MEASURED
        )
        if numeric and not self.evaluation_mode.permits_scientific_fitness:
            raise StubFitnessNotRepresentable(
                f"evaluation_mode={self.evaluation_mode.value} cannot produce scientific fitness; "
                f"{numeric} are MEASURED. A stub reading is a diagnostic, not a result: put it in "
                "DiagnosticReadings and mark the dimension NOT_REPRESENTABLE."
            )
        if numeric and not self.actor.permits_capability_claim:
            raise ReferenceFitnessNotRepresentable(
                f"actor={self.actor.value} is not a policy under measurement; {numeric} are "
                "MEASURED. Reference evidence is source proof, calibration, demonstration and "
                "replay verification - never Solver capability."
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

    @property
    def admissible_as_fitness(self) -> bool:
        """Whether this vector may be read as fitness at all - mode and actor, not emptiness."""

        return (
            self.evaluation_mode.permits_scientific_fitness and self.actor.permits_capability_claim
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": [item.to_dict() for item in self.dimensions],
            "evaluation_mode": self.evaluation_mode.value,
            "actor": self.actor.value,
            "admissible_as_fitness": self.admissible_as_fitness,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            tuple(FitnessDimension.from_dict(item) for item in raw["dimensions"]),
            EvaluationMode(raw["evaluation_mode"]),
            EvidenceActor(raw["actor"]),
        )

    @classmethod
    def build(
        cls,
        measured: Sequence[FitnessDimension],
        *,
        note: str,
        evaluation_mode: EvaluationMode,
        actor: EvidenceActor,
    ) -> Self:
        supplied = {item.name: item for item in measured}
        if len(supplied) != len(measured):
            raise ValueError("a dimension was supplied twice")
        return cls(
            tuple(
                supplied.get(name, FitnessDimension.not_measured(name, note))
                for name, _ in FITNESS_DIMENSIONS
            ),
            evaluation_mode,
            actor,
        )

    @classmethod
    def inadmissible(
        cls,
        *,
        evaluation_mode: EvaluationMode,
        actor: EvidenceActor,
        computed: Sequence[str] = (),
        note: str,
    ) -> Self:
        """The whole vector for a run whose readings cannot be fitness (RT-16, RT-04).

        ``computed`` names the dimensions for which a number *was* produced and discarded; they
        become ``NOT_REPRESENTABLE`` rather than ``NOT_MEASURED``, so the record distinguishes
        "inadmissible" from "never attempted".  Passing a mode and actor that *would* permit
        fitness is a caller error and raises, so this constructor cannot be used to hide a real
        measurement behind a status.
        """

        if evaluation_mode.permits_scientific_fitness and actor.permits_capability_claim:
            raise ValueError(
                f"{evaluation_mode.value}/{actor.value} may carry scientific fitness; build the "
                "vector with the readings it actually has instead of declaring it inadmissible"
            )
        reason = (
            UnreportableReason.EXECUTABILITY_STUB
            if not evaluation_mode.permits_scientific_fitness
            else UnreportableReason.REFERENCE_ACTOR_NOT_A_SOLVER_RESULT
        )
        unknown = sorted(set(computed) - set(DIMENSION_DIRECTIONS))
        if unknown:
            raise ValueError(f"unknown fitness dimension(s) {unknown}")
        return cls(
            tuple(
                FitnessDimension.not_representable(name, reason=reason, note=note)
                if name in set(computed)
                else FitnessDimension.not_measured(name, note)
                for name, _ in FITNESS_DIMENSIONS
            ),
            evaluation_mode,
            actor,
        )


#: Names a :class:`DiagnosticReadings` key may never take: exactly the fitness dimensions.  A
#: diagnostic that borrows a fitness name is the RT-16 failure wearing a different hat.
RESERVED_DIAGNOSTIC_NAMES = frozenset(DIMENSION_DIRECTIONS)

#: Separates the basis from the reading name in :meth:`DiagnosticReadings.archive_metrics`, so a
#: number that reaches a downstream archive carries the reason it is not fitness in its own key.
DIAGNOSTIC_KEY_SEPARATOR = "::"


@dataclass(frozen=True, slots=True)
class DiagnosticReadings:
    """Numbers that are **not** fitness, carried where they cannot be mistaken for it (RT-16).

    The loop still needs to exercise Pareto ranking, the archive and frontier selection with a
    stub evaluator; that is the whole point of an executability milestone.  What it must not do is
    put the stub's numbers where a reader looks for results.  So they live here: keyed by names
    that may never be a fitness dimension, stamped with the ``basis`` that produced them, and
    exported to any archive with that basis prefixed onto every key.
    """

    basis: str
    readings: dict[str, float] = field(default_factory=dict)
    note: str = ""

    def __post_init__(self) -> None:
        if not self.basis:
            raise ValueError("diagnostic readings must declare the basis that produced them")
        if DIAGNOSTIC_KEY_SEPARATOR in self.basis:
            raise ValueError(f"a basis may not contain {DIAGNOSTIC_KEY_SEPARATOR!r}")
        reserved = sorted(set(self.readings) & RESERVED_DIAGNOSTIC_NAMES)
        if reserved:
            raise StubFitnessNotRepresentable(
                f"diagnostic readings may not borrow fitness dimension name(s) {reserved}; "
                "a number under a J_* name is a fitness claim however it is stored"
            )
        for name, value in self.readings.items():
            if not name or DIAGNOSTIC_KEY_SEPARATOR in name:
                raise ValueError(f"unusable diagnostic name {name!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"diagnostic {name!r} is not finite")

    def archive_metrics(self) -> dict[str, float]:
        """The form a ranking archive may hold: every key names its own inadmissibility."""

        return {
            f"{self.basis}{DIAGNOSTIC_KEY_SEPARATOR}{name}": float(value)
            for name, value in sorted(self.readings.items())
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis,
            "readings": {name: float(value) for name, value in sorted(self.readings.items())},
            "archive_metrics": self.archive_metrics(),
            "note": self.note,
            "is_scientific_fitness": False,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            basis=str(raw["basis"]),
            readings={str(k): float(v) for k, v in raw.get("readings", {}).items()},
            note=str(raw.get("note", "")),
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

    **RT-13.**  ``proposal_id`` and ``mutation_hash`` are the proposer's bookkeeping.  They are
    still required, still stored and still readable, but they are named in
    :data:`PROPOSAL_BOOKKEEPING_FIELDS` and therefore appear in no identity and no hash: two
    otherwise identical evaluations that differ only in them are one record.  The semantic hash of
    the mutation is :attr:`intervention_hash`, which is *derived* from the operator and the genes
    that changed and so cannot be re-rolled at all.
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
    def intervention_hash(self) -> str:
        """The mutation's own content hash: the operator and the edit, nothing else (RT-13).

        Derived rather than supplied, so unlike ``mutation_hash`` it cannot be re-rolled: two
        proposals of the same edge under different proposal ids agree here by construction.
        """

        return stable_hash(
            {
                "operator": self.operator,
                "gene_changes": sorted(
                    (item.gene, item.from_value, item.to_value) for item in self.gene_changes
                ),
            }
        )

    @property
    def changed_genes(self) -> tuple[str, ...]:
        return tuple(item.gene for item in self.gene_changes)

    @property
    def n_genes_changed(self) -> int:
        return len(self.gene_changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            # RT-13: bookkeeping.  Stored for the audit trail, covered by no hash and by no
            # identity, so re-rolling either buys nothing.
            "proposal_id": self.proposal_id,
            "mutation_hash": self.mutation_hash,
            # ... and the derived hash that *is* covered, and cannot be re-rolled.
            "intervention_hash": self.intervention_hash,
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

    @property
    def evaluation_manifest_hash(self) -> str:
        """The whole manifest of *what was evaluated*, not merely which task ids (RT-13).

        ``task_set_hash`` alone would let the same task ids drawn from a different pool, under a
        different role, at a different fidelity count as the same evaluation.  The identity binds
        this instead, so an evaluation that differs in any of those is a different experiment.
        """

        return stable_hash(
            {
                "arena_id": self.arena_id,
                "environment_version": self.environment_version,
                "mechanism": self.mechanism,
                "task_ids": sorted(self.task_ids),
                "task_set_hash": self.task_set_hash,
                "n_problems": len(self.task_ids),
                "n_clusters": self.n_clusters,
                "fidelity_level": self.fidelity_level,
                "ladder_level": self.ladder_level,
                "pool_id": self.pool_id,
                "pool_role": self.pool_role,
                "horizon_bucket": self.horizon_bucket,
                "pool_disjoint_from": sorted(self.pool_disjoint_from),
            }
        )

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
            "evaluation_manifest_hash": self.evaluation_manifest_hash,
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

    @property
    def tokenizer_condition(self) -> str:
        """Tokenizer identity *and* whether counts taken under it are exact.

        An identity component in its own right: the same tokenizer id with and without exact
        counting supports different claims about ``J_cost``, so they are different conditions.
        """

        return f"{self.tokenizer_id}|exact={str(self.tokenizer_exact).lower()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "model_revision": self.model_revision,
            "tokenizer_condition": self.tokenizer_condition,
        }

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
class ExperimentalCondition:
    """The conditions a reading was taken under, beyond the model weights (RT-13).

    Manual section 26's fairness contract is between *conditions*, not between model names.  A
    candidate scored with a different search controller, a different toolset, a different
    adaptation allowance or a different inference protocol has been measured in a different
    experiment, and pooling the two is the substitution the manual's section 30.4 is about.  Every
    field is required and non-empty: an unstated condition is a refusal, never an assumed default,
    because "we didn't say" and "there wasn't one" are different facts.
    """

    #: The search controller ``C`` (manual section 6.15), frozen in early comparisons.
    controller: str
    #: What the solver could call.  ``"none"`` is a legitimate, and different, toolset.
    toolset: str
    #: Whether the candidate was allowed to adapt at all (e.g. ``"NO_ADAPTATION"``).
    adaptation_condition: str
    #: The adaptation allowance, spelled out.  A string so ``"0"`` and ``"unbounded"`` are both
    #: sayable and neither is a silent default.
    adaptation_budget: str
    #: The inference protocol: passes, sampling, self-consistency width.
    inference_condition: str

    def __post_init__(self) -> None:
        missing = [
            key
            for key in (
                "controller",
                "toolset",
                "adaptation_condition",
                "adaptation_budget",
                "inference_condition",
            )
            if not getattr(self, key)
        ]
        if missing:
            raise RecordIdentityViolation(
                f"experimental condition is missing components: {missing}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "condition_hash": self.identity_hash}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            controller=str(raw["controller"]),
            toolset=str(raw["toolset"]),
            adaptation_condition=str(raw["adaptation_condition"]),
            adaptation_budget=str(raw["adaptation_budget"]),
            inference_condition=str(raw["inference_condition"]),
        )

    @property
    def identity_hash(self) -> str:
        return stable_hash(asdict(self))


#: The only ``replicate_id`` that needs no authorisation: the first, primary draw.
PRIMARY_REPLICATE_ID = "replicate:0000"
#: The authoriser recorded for that primary draw, and reserved to it.
PRIMARY_DRAW_AUTHORISER = "PRIMARY_DRAW"
_REPLICATE_ID_PATTERN = re.compile(r"^replicate:\d{4}$")


@dataclass(frozen=True, slots=True)
class ReplicateAuthorisation:
    """Permission to take a *second* draw of an experiment that already has one (RT-13).

    Replication must stay possible - without it a stochastic evaluator's variance is unmeasurable.
    What must stop is replication *by accident*: re-rolling a proposal id until a favourable
    sample appears is best-of-N sampling reported as a single result, the winner's curse of manual
    section 30.4.  So a replicate beyond the primary is a declaration, not a value: it names an
    authoriser, a reason and the replication plan it belongs to, all of which are stored, hashed
    and auditable.  ``replicate_id`` is the identity component; the justification travels with it
    in the record's content, so re-authorising an existing replicate under a new reason collides
    with the re-scoring guard instead of quietly replacing it.
    """

    replicate_id: str = PRIMARY_REPLICATE_ID
    authorised_by: str = PRIMARY_DRAW_AUTHORISER
    reason: str = ""
    plan_id: str = ""

    def __post_init__(self) -> None:
        if not _REPLICATE_ID_PATTERN.match(self.replicate_id):
            raise UnauthorisedReplicateError(
                f"unusable replicate id {self.replicate_id!r}; expected 'replicate:NNNN'. An "
                "arbitrary string here would be exactly the re-rollable nonce this type exists to "
                "prevent."
            )
        if self.is_primary:
            if self.authorised_by != PRIMARY_DRAW_AUTHORISER or self.reason or self.plan_id:
                raise UnauthorisedReplicateError(
                    f"{PRIMARY_REPLICATE_ID} is the primary draw and carries no authorisation; "
                    "a draw that needed authorising is not the primary one"
                )
            return
        if self.authorised_by == PRIMARY_DRAW_AUTHORISER:
            raise UnauthorisedReplicateError(
                f"{self.replicate_id} claims the reserved primary authoriser "
                f"{PRIMARY_DRAW_AUTHORISER!r}"
            )
        missing = [key for key in ("authorised_by", "reason", "plan_id") if not getattr(self, key)]
        if missing:
            raise UnauthorisedReplicateError(
                f"replicate {self.replicate_id} is not authorised: missing {missing}. A second "
                "draw of one experiment requires an authoriser, a reason and a replication plan; "
                "re-rolling a proposal id is not a replication design."
            )

    @property
    def is_primary(self) -> bool:
        return self.replicate_id == PRIMARY_REPLICATE_ID

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "is_primary": self.is_primary}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        return cls(
            replicate_id=str(raw.get("replicate_id", PRIMARY_REPLICATE_ID)),
            authorised_by=str(raw.get("authorised_by", PRIMARY_DRAW_AUTHORISER)),
            reason=str(raw.get("reason", "")),
            plan_id=str(raw.get("plan_id", "")),
        )

    @classmethod
    def primary(cls) -> Self:
        return cls()


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


#: Spec section 2.2, hardened by RT-13.  **Semantic experimental identity**: what was evaluated,
#: on what, by whom, under which conditions, as which replicate.  All required, all non-empty.
#:
#: What is deliberately **not** here, and why:
#:
#: * ``proposal_id`` / ``mutation_hash`` - proposal bookkeeping.  Including them is the RT-13
#:   defect: re-emitting one parent -> child edge under a new proposal id bought a second
#:   ``FRESH`` record, i.e. a free extra draw from a stochastic evaluator.  The mutation's
#:   *semantic* content reaches the identity as ``intervention_class`` and reaches the record's
#:   content hash as ``MutationDescriptor.intervention_hash``.
#: * ``created_at`` / ``wall_clock_seconds`` - when the run happened is not what was run.
#: * ``run_id`` / ``generation`` - where in a search the evaluation sat.  Two searches that reach
#:   the same edge under the same conditions have performed the *same* experiment.
#: * ``parent_genome_id`` / ``child_genome_id`` - labels.  Lineage is resolved by hash, which is
#:   the thing that cannot be renamed.
#: * ``dataset`` - identified through ``evaluation_manifest_hash``; a dataset change that does not
#:   move the manifest changes the record's content and is caught by the re-scoring guard.
#: * any nonce, counter, timestamp or random field.  There is nowhere to put one that forks the
#:   identity; the worst it can do is force a refusal under the existing guard.
EVALUATION_IDENTITY_COMPONENTS = (
    "schema_version",
    "harness_version",
    "evaluation_mode",
    "actor",
    "parent_genome_hash",
    "child_genome_hash",
    "intervention_class",
    "environment_version",
    "evaluation_manifest_hash",
    "ladder_level",
    "solver_digest",
    "solver_revision",
    "decoding_hash",
    "tokenizer_condition",
    "runtime_condition",
    "controller",
    "toolset",
    "adaptation_condition",
    "adaptation_budget",
    "inference_condition",
    "replicate_id",
)

#: Spec section 2.2's grouping key.  Two records may be compared, differenced or pooled only
#: when their ``condition_id`` matches; a delta computed across two conditions is not a delta.
#:
#: ``evaluation_mode`` and ``actor`` are in here, so stub and scientific records - and
#: ``REFERENCE`` and ``SOLVER`` records - land in different shards on disk and cannot be pooled
#: even by a directory listing (RT-16, RT-04).  ``replicate_id`` is deliberately *out*: replicates
#: of one experiment share a condition, which is what makes them poolable as replicates.
CONDITION_COMPONENTS = (
    "evaluation_mode",
    "actor",
    "solver_digest",
    "solver_revision",
    "decoding_hash",
    "tokenizer_condition",
    "runtime_condition",
    "controller",
    "toolset",
    "adaptation_condition",
    "adaptation_budget",
    "inference_condition",
    "environment_version",
    "evaluation_manifest_hash",
    "ladder_level",
)


def evaluation_identity(
    *,
    harness_version: str,
    evaluation_mode: EvaluationMode,
    actor: EvidenceActor,
    parent_genome_hash: str,
    child_genome_hash: str,
    mutation: MutationDescriptor,
    evaluation_context: EvaluationContext,
    model: ModelIdentity,
    condition: ExperimentalCondition,
    replicate: ReplicateAuthorisation,
    schema_version: str = RECORD_SCHEMA_VERSION,
) -> dict[str, str]:
    """The semantic experimental identity.  A missing component is a refusal, not a blank slot.

    ``intervention_class`` is *derived* from the genes the mutation actually changed
    (:func:`classify_intervention`), so it fails closed on an undeclared gene and cannot be
    asserted independently of the edit it describes.
    """

    identity = {
        "schema_version": schema_version,
        "harness_version": harness_version,
        "evaluation_mode": EvaluationMode(evaluation_mode).value,
        "actor": EvidenceActor(actor).value,
        "parent_genome_hash": parent_genome_hash,
        "child_genome_hash": child_genome_hash,
        "intervention_class": mutation.intervention_class.value,
        "environment_version": evaluation_context.environment_version,
        "evaluation_manifest_hash": evaluation_context.evaluation_manifest_hash,
        "ladder_level": evaluation_context.ladder_level,
        "solver_digest": model.digest,
        "solver_revision": model.model_revision,
        "decoding_hash": model.decoding_hash,
        "tokenizer_condition": model.tokenizer_condition,
        "runtime_condition": model.runtime_condition,
        "controller": condition.controller,
        "toolset": condition.toolset,
        "adaptation_condition": condition.adaptation_condition,
        "adaptation_budget": condition.adaptation_budget,
        "inference_condition": condition.inference_condition,
        "replicate_id": replicate.replicate_id,
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
    evaluation_mode: EvaluationMode
    actor: EvidenceActor
    parent_genome_id: str
    parent_genome_hash: str
    child_genome_id: str
    child_genome_hash: str
    mutation: MutationDescriptor
    evaluation_context: EvaluationContext
    model: ModelIdentity
    condition: ExperimentalCondition
    replicate: ReplicateAuthorisation
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
    diagnostics: DiagnosticReadings | None = None
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
        # RT-16 / RT-04.  The vector carries its own licence; the record must not disagree with
        # it, or a caller could build an admissible vector and file it under a stub record.
        if self.fitness_vector.evaluation_mode is not self.evaluation_mode:
            raise FitnessRepresentationError(
                f"record declares evaluation_mode={self.evaluation_mode.value} but its fitness "
                f"vector was built under {self.fitness_vector.evaluation_mode.value}"
            )
        if self.fitness_vector.actor is not self.actor:
            raise FitnessRepresentationError(
                f"record declares actor={self.actor.value} but its fitness vector was built "
                f"under {self.fitness_vector.actor.value}"
            )
        # RT-16.  A stub run is *required* to say what it computed instead, so "no fitness" cannot
        # be mistaken for "nothing happened".  The rule is keyed on the mode, not on the actor:
        # a stub computes a number by definition, whereas a REFERENCE replay may legitimately
        # produce none - its evidence is the gate results and the provenance, not a statistic.
        if (
            self.status is RecordStatus.COMPLETE
            and not self.evaluation_mode.permits_scientific_fitness
            and self.diagnostics is None
        ):
            raise StubFitnessNotRepresentable(
                f"a COMPLETE {self.evaluation_mode.value} record must carry DiagnosticReadings: "
                "its numbers are not fitness and must be stored where they say so"
            )

    @property
    def identity(self) -> dict[str, str]:
        return evaluation_identity(
            harness_version=self.harness_version,
            evaluation_mode=self.evaluation_mode,
            actor=self.actor,
            parent_genome_hash=self.parent_genome_hash,
            child_genome_hash=self.child_genome_hash,
            mutation=self.mutation,
            evaluation_context=self.evaluation_context,
            model=self.model,
            condition=self.condition,
            replicate=self.replicate,
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
                "diagnostics": None if self.diagnostics is None else self.diagnostics.to_dict(),
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
        # RT-13: proposal bookkeeping is not part of the experiment, so re-rolling it leaves this
        # payload - and therefore the content hash and the append decision - untouched.
        payload["mutation"] = {
            key: value
            for key, value in payload["mutation"].items()
            if key not in PROPOSAL_BOOKKEEPING_FIELDS
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
            "evaluation_mode": self.evaluation_mode.value,
            "actor": self.actor.value,
            "parent_genome_id": self.parent_genome_id,
            "parent_genome_hash": self.parent_genome_hash,
            "child_genome_id": self.child_genome_id,
            "child_genome_hash": self.child_genome_hash,
            "mutation": self.mutation.to_dict(),
            "evaluation_context": self.evaluation_context.to_dict(),
            "model": self.model.to_dict(),
            "condition": self.condition.to_dict(),
            "replicate": self.replicate.to_dict(),
            "dataset": self.dataset.to_dict(),
            "budget": self.budget.to_dict(),
            "fitness_vector": self.fitness_vector.to_dict(),
            "diagnostics": None if self.diagnostics is None else self.diagnostics.to_dict(),
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
            "identity_components": list(EVALUATION_IDENTITY_COMPONENTS),
            "unhashed_bookkeeping_fields": list(BOOKKEEPING_FIELDS),
            "schema_divergences": list(SCHEMA_DIVERGENCES),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> Self:
        stored_version = str(raw.get("schema_version", ""))
        if stored_version != RECORD_SCHEMA_VERSION:
            # No migration, no defaulting: a record written under another schema is read by that
            # schema's code or not at all.  Silently upgrading it would be rewriting the ledger.
            raise ValueError(
                f"unsupported record schema {stored_version!r}; this module reads only "
                f"{RECORD_SCHEMA_VERSION!r} and does not migrate stored records"
            )
        record = cls(
            run_id=str(raw["run_id"]),
            generation=int(raw["generation"]),
            harness_version=str(raw["harness_version"]),
            evaluation_mode=EvaluationMode(raw["evaluation_mode"]),
            actor=EvidenceActor(raw["actor"]),
            parent_genome_id=str(raw["parent_genome_id"]),
            parent_genome_hash=str(raw["parent_genome_hash"]),
            child_genome_id=str(raw["child_genome_id"]),
            child_genome_hash=str(raw["child_genome_hash"]),
            mutation=MutationDescriptor.from_dict(raw["mutation"]),
            evaluation_context=EvaluationContext.from_dict(raw["evaluation_context"]),
            model=ModelIdentity.from_dict(raw["model"]),
            condition=ExperimentalCondition.from_dict(raw["condition"]),
            replicate=ReplicateAuthorisation.from_dict(raw["replicate"]),
            dataset=DatasetIdentity.from_dict(raw["dataset"]),
            budget=Budget.from_dict(raw["budget"]),
            fitness_vector=FitnessVector.from_dict(raw["fitness_vector"]),
            diagnostics=(
                None
                if raw.get("diagnostics") is None
                else DiagnosticReadings.from_dict(raw["diagnostics"])
            ),
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
            schema_version=stored_version,
        )
        for name, computed in (
            ("content_hash", record.content_hash),
            ("result_hash", record.result_hash),
            ("record_id", record.record_id),
            ("condition_id", record.condition_id),
        ):
            stored = raw.get(name)
            if stored is not None and stored != computed:
                raise FitnessMemoryIdentityViolation(
                    f"record {record.child_genome_id} does not reproduce its stored {name}"
                )
        stored_identity = raw.get("identity")
        if stored_identity is not None and dict(stored_identity) != record.identity:
            raise FitnessMemoryIdentityViolation(
                f"record {record.child_genome_id} does not reproduce its stored identity"
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

    **RT-04.**  ``actor`` is a condition component, so ``REFERENCE`` and ``SOLVER`` records are
    already in different shards.  On top of that, the *read* side refuses to hand back a mixed set:
    :meth:`records` and :meth:`summary` raise :class:`ActorPoolingViolation` the moment the run
    holds both, and the only way to get records out of such a run is
    :meth:`records_for_actor`, which must be told which body of evidence is wanted.  Pooling is
    therefore not a discipline a caller has to remember - it is a query that cannot be expressed.
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
        # Deliberately the unfiltered iterator, not ``records()``: appending a REFERENCE record to
        # a run that already holds SOLVER records is legitimate (they are different evidence, not
        # a pool), so the append path must not be brickable by the anti-pooling guard.
        for record in self._all_records():
            self._index[record.record_id] = (record.result_hash, record.content_hash)
        self._loaded = True

    def record_paths(self) -> tuple[Path, ...]:
        if not self.path.is_dir():
            return ()
        return tuple(sorted(self.path.glob("*/lfm-*.json")))

    def _all_records(self) -> tuple[FitnessRecord, ...]:
        return tuple(
            FitnessRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            for path in self.record_paths()
        )

    def actors(self) -> tuple[EvidenceActor, ...]:
        """Which bodies of evidence this run holds.  Cheap, and never pools anything."""

        return tuple(sorted({record.actor for record in self._all_records()}))

    def _refuse_mixed_actors(self, actors: Sequence[EvidenceActor], *, query: str) -> None:
        if len(set(actors)) > 1:
            raise ActorPoolingViolation(
                f"{query} spans actors {sorted(a.value for a in set(actors))}. REFERENCE evidence "
                "is source proof, calibration, demonstration and replay verification; it is not "
                "Solver capability, and the two are never one set. Ask for one actor with "
                "records_for_actor()."
            )

    def records_for_actor(self, actor: EvidenceActor) -> tuple[FitnessRecord, ...]:
        """Every record produced by one actor.  The only query that works on a mixed run."""

        wanted = EvidenceActor(actor)
        return tuple(record for record in self._all_records() if record.actor is wanted)

    def records(self) -> tuple[FitnessRecord, ...]:
        """Every record in this run - and a refusal if that would mix actors (RT-04)."""

        records = self._all_records()
        self._refuse_mixed_actors([record.actor for record in records], query="records()")
        return records

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
        """The run's manifest - and a refusal if that would pool two actors (RT-04)."""

        records = self._all_records()
        self._refuse_mixed_actors([record.actor for record in records], query="summary()")
        return self._summary(records)

    def summary_for_actor(self, actor: EvidenceActor) -> dict[str, Any]:
        """The manifest of one actor's evidence, on a run that holds more than one."""

        return self._summary(self.records_for_actor(actor))

    def _summary(self, records: Sequence[FitnessRecord]) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "directory": str(self.directory),
            "records": len(records),
            "actors": sorted({item.actor.value for item in records}),
            "evaluation_modes": sorted({item.evaluation_mode.value for item in records}),
            "replicates": sorted({item.replicate.replicate_id for item in records}),
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
    "BOOKKEEPING_FIELDS",
    "CONDITION_COMPONENTS",
    "DIAGNOSTIC_KEY_SEPARATOR",
    "DIMENSION_DIRECTIONS",
    "EVALUATION_IDENTITY_COMPONENTS",
    "FITNESS_DIMENSIONS",
    "NOT_REPRESENTABLE_REASONS",
    "PRIMARY_DRAW_AUTHORISER",
    "PRIMARY_REPLICATE_ID",
    "PROPOSAL_BOOKKEEPING_FIELDS",
    "RECORD_SCHEMA_VERSION",
    "RESERVED_DIAGNOSTIC_NAMES",
    "SCHEMA_DIVERGENCES",
    "WALL_CLOCK_FIELDS",
    "ActorPoolingViolation",
    "AppendResult",
    "Budget",
    "DatasetIdentity",
    "DiagnosticReadings",
    "DimensionStatus",
    "EvaluationContext",
    "EvaluationMode",
    "EvidenceActor",
    "EvolutionRecordStore",
    "ExperimentalCondition",
    "FitnessDimension",
    "FitnessMemoryIdentityViolation",
    "FitnessRecord",
    "FitnessRepresentationError",
    "FitnessVector",
    "GateOutcome",
    "GateStatus",
    "GeneChangeRecord",
    "ModelIdentity",
    "MutationDescriptor",
    "RecordIdentityViolation",
    "RecordScope",
    "RecordStatus",
    "ReferenceFitnessNotRepresentable",
    "ReplicateAuthorisation",
    "RescoringConflict",
    "StubFitnessNotRepresentable",
    "UnauthorisedReplicateError",
    "UnreportableReason",
    "condition_id",
    "dumps",
    "evaluation_identity",
    "record_id",
    "record_key",
]
