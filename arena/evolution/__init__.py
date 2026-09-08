"""The outer evolutionary loop: population, mutation, semantic gate, fitness, archive.

``HAMILTONIAN_CHESS_V0`` is an *executability* milestone, not a scientific one.  Nothing this
package produces is a result: its evaluator is a deterministic stub with no reasoning ability
(see :class:`arena.evolution.loop.StubSolver`), and its arena has horizon 1.  What it does
provide is a closed loop with real gates, a durable append-only fitness record conforming to
``docs/LANGUAGE_FITNESS_MEMORY.md``, and real rows in the league archive, so that a Solver and a
trajectory world can be dropped in later without changing the loop.
"""

from .record import (
    GENE_INTERVENTION_CLASS,
    SCHEMA_DIVERGENCES,
    Budget,
    DatasetIdentity,
    EvaluationContext,
    EvolutionRecordStore,
    FitnessDimension,
    FitnessMemoryIdentityViolation,
    FitnessRecord,
    FitnessVector,
    GateOutcome,
    InterventionClass,
    ModelIdentity,
    MutationDescriptor,
    RecordIdentityViolation,
    RecordScope,
    RecordStatus,
    RescoringConflict,
    UnclassifiedGeneError,
    classify_intervention,
    condition_id,
    evaluation_identity,
    record_id,
)

__all__ = [
    "GENE_INTERVENTION_CLASS",
    "SCHEMA_DIVERGENCES",
    "Budget",
    "DatasetIdentity",
    "EvaluationContext",
    "EvolutionRecordStore",
    "FitnessDimension",
    "FitnessMemoryIdentityViolation",
    "FitnessRecord",
    "FitnessVector",
    "GateOutcome",
    "InterventionClass",
    "ModelIdentity",
    "MutationDescriptor",
    "RecordIdentityViolation",
    "RecordScope",
    "RecordStatus",
    "RescoringConflict",
    "UnclassifiedGeneError",
    "classify_intervention",
    "condition_id",
    "evaluation_identity",
    "record_id",
]
