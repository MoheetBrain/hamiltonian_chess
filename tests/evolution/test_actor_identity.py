"""RT-04: REFERENCE evidence and SOLVER evidence can never be pooled or substituted.

``docs/HC_V0_RED_TEAM.md`` RT-04 found that one episode could yield both a ``REFERENCE`` record
and a ``SOLVER`` record, each internally consistent, because the actor was a keyword argument that
overwrote who chose every action.  The team's disclosure - *"ALL 120 bank actions are
actor=REFERENCE"* - was true of the artefact and enforced by nothing.

The trajectory half of that fix (stamping the actor at the moment of choice, and making
``build_trajectory(actor=...)`` an assertion rather than a rewrite) lives in ``arena/trajectory/``.
This module pins the **ledger** half, which is what stops the two bodies of evidence being counted
as one thing whatever the trajectory layer does:

1. the actor is an identity component, so the same episode under two actors is two records with
   different ids, in different condition shards;
2. a ``REFERENCE`` record cannot carry a fitness reading at all, so reference data can never be
   counted as Solver capability; and
3. a query that would return both as one set raises instead.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arena.evolution.record import (
    CONDITION_COMPONENTS,
    EVALUATION_IDENTITY_COMPONENTS,
    ActorPoolingViolation,
    DimensionStatus,
    EvaluationMode,
    EvidenceActor,
    EvolutionRecordStore,
    FitnessDimension,
    FitnessRepresentationError,
    FitnessVector,
    ReferenceFitnessNotRepresentable,
    UnreportableReason,
)
from arena.fitness.metrics import Direction
from arena.storage.artifacts import ArtifactStore
from tests.evolution import factory


def _both(tmp_path: Path) -> EvolutionRecordStore:
    """One run holding both bodies of evidence - the situation RT-04 is about."""

    store = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    store.append(factory.record())
    store.append(factory.reference_record())
    return store


# ------------------------------------------------------------------- actor is identity


def test_actor_is_an_identity_and_a_condition_component() -> None:
    assert "actor" in EVALUATION_IDENTITY_COMPONENTS
    assert "actor" in CONDITION_COMPONENTS


def test_one_episode_under_two_actors_is_two_records_not_one(tmp_path: Path) -> None:
    """Everything else identical; the actor alone forks the id *and* the shard."""

    solver = factory.record()
    reference = factory.reference_record()
    assert solver.record_id != reference.record_id
    assert solver.condition_id != reference.condition_id

    store = _both(tmp_path)
    shards = {path.parent.name for path in store.record_paths()}
    assert len(shards) == 2, "REFERENCE and SOLVER evidence share a directory"


def test_a_reference_record_cannot_be_substituted_for_a_solver_one(tmp_path: Path) -> None:
    """Relabelling the actor does not let reference evidence occupy the solver's identity."""

    store = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    store.append(factory.record())
    # Relabelling the record is not enough, because the vector it carries was licensed for
    # REFERENCE and says so; the record refuses to exist rather than quietly changing hands.
    with pytest.raises(FitnessRepresentationError, match="fitness vector was built"):
        replace(factory.reference_record(), actor=EvidenceActor.SOLVER)
    # Relabelling the vector too is not enough either: it then cannot hold the reading, so the
    # substitution has nothing left to carry.
    with pytest.raises(ReferenceFitnessNotRepresentable):
        FitnessVector.build(
            [
                FitnessDimension(
                    name="J_solve",
                    status=DimensionStatus.MEASURED,
                    direction=Direction.MAXIMIZE,
                    value=1.0,
                    unit_of_analysis="item",
                    estimator="wilson",
                    n=16,
                )
            ],
            note="reference replay relabelled as a solver result",
            evaluation_mode=EvaluationMode.SCIENTIFIC,
            actor=EvidenceActor.REFERENCE,
        )
    assert len(store.record_paths()) == 1


# --------------------------------------------------- reference data is not capability


def test_a_reference_actor_cannot_carry_a_fitness_reading() -> None:
    """The RT-04 acceptance property: reference evidence is never Solver capability."""

    measured = FitnessDimension(
        name="J_solve",
        status=DimensionStatus.MEASURED,
        direction=Direction.MAXIMIZE,
        value=1.0,
        unit_of_analysis="item",
        estimator="wilson",
        n=16,
        reportable=True,
    )
    with pytest.raises(ReferenceFitnessNotRepresentable, match="not a policy under measurement"):
        FitnessVector.build(
            [measured],
            note="the reference proof closes every goal, as it must",
            evaluation_mode=EvaluationMode.SCIENTIFIC,
            actor=EvidenceActor.REFERENCE,
        )


def test_a_reference_record_says_why_its_dimensions_are_empty() -> None:
    """``NOT_MEASURED`` would be a lie: the number exists and is inadmissible."""

    vector = factory.reference_record().fitness_vector
    assert vector.measured() == {}
    assert not vector.admissible_as_fitness
    assert vector["J_solve"].status is DimensionStatus.NOT_REPRESENTABLE
    assert (
        vector["J_solve"].unreportable_reason
        == UnreportableReason.REFERENCE_ACTOR_NOT_A_SOLVER_RESULT.value
    )
    assert not EvidenceActor.REFERENCE.permits_capability_claim
    assert EvidenceActor.SOLVER.permits_capability_claim


# ------------------------------------------------------------ pooling is unexpressible


def test_a_query_that_would_mix_actors_raises(tmp_path: Path) -> None:
    store = _both(tmp_path)
    with pytest.raises(ActorPoolingViolation, match="records\\(\\) spans actors"):
        store.records()
    with pytest.raises(ActorPoolingViolation, match="summary\\(\\) spans actors"):
        store.summary()


def test_one_actor_at_a_time_is_always_answerable(tmp_path: Path) -> None:
    """Refusing to pool must not make a mixed run unreadable - only unpoolable."""

    store = _both(tmp_path)
    assert store.actors() == (EvidenceActor.REFERENCE, EvidenceActor.SOLVER)
    solver = store.records_for_actor(EvidenceActor.SOLVER)
    reference = store.records_for_actor(EvidenceActor.REFERENCE)
    assert [item.actor for item in solver] == [EvidenceActor.SOLVER]
    assert [item.actor for item in reference] == [EvidenceActor.REFERENCE]
    assert store.summary_for_actor(EvidenceActor.SOLVER)["actors"] == ["SOLVER"]
    assert (
        store.summary_for_actor(EvidenceActor.SOLVER)["manifest_hash"]
        != store.summary_for_actor(EvidenceActor.REFERENCE)["manifest_hash"]
    )


def test_appending_reference_evidence_to_a_solver_run_still_works(tmp_path: Path) -> None:
    """The guard protects the read path only: a mixed run must remain writable.

    Reference records are legitimate evidence - source proof, calibration, replay verification -
    so a store that refused to accept them would push them somewhere with no discipline at all.
    """

    store = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    store.append(factory.record())
    store.append(factory.reference_record())
    reopened = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    reopened.append(factory.record())  # resume: reuse, and the mixed run does not brick the index
    assert len(reopened.record_paths()) == 2


def test_the_actor_vocabulary_agrees_with_the_trajectory_layer() -> None:
    """One vocabulary, cross-checked rather than shared by import.

    If ``arena.trajectory.schema.Actor`` gains a member, this fails - and it should: a new kind of
    actor needs a deliberate decision about what its evidence may claim, not a silent inheritance.
    """

    schema = pytest.importorskip("arena.trajectory.schema")
    assert {item.value for item in schema.Actor} <= {item.value for item in EvidenceActor}
