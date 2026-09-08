"""Builders for the red-team acceptance tests.

Deliberately not a ``conftest.py`` fixture set: every test in this group varies *one component of
a record's identity* and asserts what that does to the record id, so plain functions with keyword
overrides read better than fixtures, and the file is importable from each test module.

Not named ``test_*``, so pytest does not collect it.
"""

from __future__ import annotations

from typing import Any

from arena.evolution.record import (
    Budget,
    DatasetIdentity,
    DiagnosticReadings,
    DimensionStatus,
    EvaluationContext,
    EvaluationMode,
    EvidenceActor,
    ExperimentalCondition,
    FitnessDimension,
    FitnessRecord,
    FitnessVector,
    GateOutcome,
    GateStatus,
    GeneChangeRecord,
    ModelIdentity,
    MutationDescriptor,
    RecordStatus,
    ReplicateAuthorisation,
)
from arena.fitness.metrics import Direction

RUN_ID = "run-acceptance-0001"


def mutation(**overrides: Any) -> MutationDescriptor:
    base: dict[str, Any] = {
        "operator": "change-token",
        "proposal_id": "mutation:aaaaaaaaaaaaaaaaaaaa",
        # Deliberately not a palindrome: the re-roll tests reverse it.
        "mutation_hash": "ab" * 32,
        "parameters": {"impact_class": "surface-only"},
        "gene_changes": (GeneChangeRecord("token_policy", "wordlike", "compact"),),
        "inert": False,
        "inert_evidence": "16/16 rendered prompts differ from the parent",
    }
    base.update(overrides)
    return MutationDescriptor(**base)


def context(**overrides: Any) -> EvaluationContext:
    base: dict[str, Any] = {
        "arena_id": "arena-precondition-ladder-v2.0.0|precondition_conjunction|P05",
        "environment_version": "arena-precondition-ladder-v2.0.0",
        "mechanism": "precondition_conjunction",
        "task_ids": ("t:0", "t:1"),
        "fidelity_level": 0,
        "pool_id": "SMOKE",
        "n_clusters": 1,
    }
    base.update(overrides)
    return EvaluationContext(**base)


def model(**overrides: Any) -> ModelIdentity:
    base: dict[str, Any] = {
        "name": "solver-under-test",
        "digest": "d" * 64,
        "template_hash": "t" * 64,
        "decoding_hash": "c" * 64,
        "revision": "r1",
        "tokenizer_id": "tok:v1",
        "runtime_condition": "offline",
    }
    base.update(overrides)
    return ModelIdentity(**base)


def condition(**overrides: Any) -> ExperimentalCondition:
    base: dict[str, Any] = {
        "controller": "none:single-shot-choice",
        "toolset": "none",
        "adaptation_condition": "NO_ADAPTATION",
        "adaptation_budget": "0",
        "inference_condition": "single-pass|deterministic|n=1",
    }
    base.update(overrides)
    return ExperimentalCondition(**base)


def scientific_vector(solve: float = 0.5) -> FitnessVector:
    """A vector that *may* carry a number: SCIENTIFIC mode, SOLVER actor."""

    return FitnessVector.build(
        [
            FitnessDimension(
                name="J_solve",
                status=DimensionStatus.MEASURED,
                direction=Direction.MAXIMIZE,
                value=solve,
                lower=0.0,
                upper=1.0,
                unit_of_analysis="item",
                estimator="wilson",
                n=16,
                n_clusters=8,
                reportable=True,
            )
        ],
        note="no trajectory world exists",
        evaluation_mode=EvaluationMode.SCIENTIFIC,
        actor=EvidenceActor.SOLVER,
    )


def diagnostics(basis: EvaluationMode = EvaluationMode.EXECUTABILITY_STUB) -> DiagnosticReadings:
    return DiagnosticReadings(
        basis=basis.value,
        readings={"stub_choice_agreement": 0.75, "rendered_prompt_bytes_mean": 18755.0},
        note="NOT FITNESS",
    )


def record(**overrides: Any) -> FitnessRecord:
    base: dict[str, Any] = {
        "run_id": RUN_ID,
        "generation": 0,
        "harness_version": "arena-game-r-formal-harness-v1.0.0",
        "evaluation_mode": EvaluationMode.SCIENTIFIC,
        "actor": EvidenceActor.SOLVER,
        "parent_genome_id": "L0_STRUCTURED_ENGLISH",
        "parent_genome_hash": "p" * 64,
        "child_genome_id": "M-child",
        "child_genome_hash": "c" * 64,
        "mutation": mutation(),
        "evaluation_context": context(),
        "model": model(),
        "condition": condition(),
        "replicate": ReplicateAuthorisation.primary(),
        "dataset": DatasetIdentity("arena-precondition-ladder-v2.0.0", "SMOKE:P05:8", "UNSEALED"),
        "budget": Budget(calls=0, tokens=0, wall_clock_seconds=1.25),
        "fitness_vector": scientific_vector(),
        "uncertainty": {"confirmatory": False},
        "failure_modes": (),
        "semantic_gate_results": (GateOutcome("semantic_roundtrip", GateStatus.PASS, "recovered"),),
        "provenance": {"loop_version": "test"},
        "created_at": "2026-09-08T00:00:00.000000+00:00",
        "status": RecordStatus.COMPLETE,
        "outcome": "SCORED",
    }
    base.update(overrides)
    return FitnessRecord(**base)


def stub_record(**overrides: Any) -> FitnessRecord:
    """A record whose readings are inadmissible: stub mode, so no ``J_*`` may carry a value."""

    base: dict[str, Any] = {
        "evaluation_mode": EvaluationMode.EXECUTABILITY_STUB,
        "actor": EvidenceActor.SOLVER,
        "fitness_vector": FitnessVector.inadmissible(
            evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
            actor=EvidenceActor.SOLVER,
            computed=("J_solve", "J_cost"),
            note="stub",
        ),
        "diagnostics": diagnostics(),
    }
    base.update(overrides)
    return record(**base)


def reference_record(**overrides: Any) -> FitnessRecord:
    """A record of what the reference proof did: evidence, but never Solver capability."""

    base: dict[str, Any] = {
        "actor": EvidenceActor.REFERENCE,
        "fitness_vector": FitnessVector.inadmissible(
            evaluation_mode=EvaluationMode.SCIENTIFIC,
            actor=EvidenceActor.REFERENCE,
            computed=("J_solve",),
            note="reference replay",
        ),
    }
    base.update(overrides)
    return record(**base)
