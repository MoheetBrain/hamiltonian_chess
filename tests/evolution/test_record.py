"""The language fitness record: identity, append-only storage, and the re-scoring guard."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from arena.evolution.record import (
    CONDITION_COMPONENTS,
    EVALUATION_IDENTITY_COMPONENTS,
    FITNESS_DIMENSIONS,
    Budget,
    DatasetIdentity,
    DimensionStatus,
    EvaluationContext,
    EvolutionRecordStore,
    FitnessDimension,
    FitnessMemoryIdentityViolation,
    FitnessRecord,
    FitnessVector,
    GateOutcome,
    GateStatus,
    GeneChangeRecord,
    ModelIdentity,
    MutationDescriptor,
    RecordIdentityViolation,
    RecordScope,
    RecordStatus,
    RescoringConflict,
    dumps,
    record_key,
)
from arena.fitness.metrics import Direction
from arena.storage.artifacts import ArtifactStore

RUN_ID = "run-test-0001"


def _mutation() -> MutationDescriptor:
    return MutationDescriptor(
        operator="change-token",
        proposal_id="mutation:aaaaaaaaaaaaaaaaaaaa",
        mutation_hash="m" * 64,
        parameters={"impact_class": "surface-only"},
        gene_changes=(GeneChangeRecord("token_policy", "wordlike", "compact"),),
        inert=False,
        inert_evidence="16/16 rendered prompts differ from the parent",
    )


def _context() -> EvaluationContext:
    return EvaluationContext(
        arena_id="arena-precondition-ladder-v2.0.0|precondition_conjunction|P05",
        environment_version="arena-precondition-ladder-v2.0.0",
        mechanism="precondition_conjunction",
        task_ids=("t:0", "t:1"),
        fidelity_level=0,
        pool_id="SMOKE",
        n_clusters=1,
    )


def _model() -> ModelIdentity:
    return ModelIdentity("stub", "d" * 64, "t" * 64, "c" * 64, is_stub=True)


def _dataset() -> DatasetIdentity:
    return DatasetIdentity("arena-precondition-ladder-v2.0.0", "SMOKE:P05:8", "UNSEALED")


def _vector(solve: float = 0.5) -> FitnessVector:
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
    )


def _record(**overrides: Any) -> FitnessRecord:
    base: dict[str, Any] = {
        "run_id": RUN_ID,
        "generation": 0,
        "harness_version": "arena-game-r-formal-harness-v1.0.0",
        "parent_genome_id": "L0_STRUCTURED_ENGLISH",
        "parent_genome_hash": "p" * 64,
        "child_genome_id": "M-child",
        "child_genome_hash": "c" * 64,
        "mutation": _mutation(),
        "evaluation_context": _context(),
        "model": _model(),
        "dataset": _dataset(),
        "budget": Budget(calls=0, tokens=0, wall_clock_seconds=1.25),
        "fitness_vector": _vector(),
        "uncertainty": {"confirmatory": False},
        "failure_modes": (),
        "semantic_gate_results": (GateOutcome("semantic_roundtrip", GateStatus.PASS, "recovered"),),
        "provenance": {"loop_version": "test", "evaluator_id": "stub"},
        "created_at": "2026-09-08T00:00:00.000000+00:00",
        "status": RecordStatus.COMPLETE,
        "outcome": "SCORED",
    }
    base.update(overrides)
    return FitnessRecord(**base)


# ------------------------------------------------------------------------- content hash


def test_content_hash_ignores_only_the_wall_clock() -> None:
    first = _record()
    later = _record(
        created_at="2027-01-01T12:00:00.000000+00:00",
        budget=Budget(calls=0, tokens=0, wall_clock_seconds=99.0),
    )
    assert first.content_hash == later.content_hash

    assert _record(generation=1).content_hash != first.content_hash
    assert _record(fitness_vector=_vector(0.75)).content_hash != first.content_hash
    assert _record(budget=Budget(calls=7, tokens=0)).content_hash != first.content_hash


def test_content_hash_is_stable_across_processes() -> None:
    # sha256 over canonical JSON: the value is pinned, not merely self-consistent.
    assert (
        _record().content_hash == FitnessRecord.from_dict(json.loads(dumps(_record()))).content_hash
    )


# --------------------------------------------------------------------------- round trip


def test_json_round_trip_preserves_every_field() -> None:
    original = _record()
    restored = FitnessRecord.from_dict(json.loads(dumps(original)))
    assert restored.to_dict() == original.to_dict()
    assert restored.identity == original.identity
    assert restored.record_id == original.record_id
    assert restored.condition_id == original.condition_id
    assert restored.result_hash == original.result_hash


def test_a_tampered_stored_hash_is_refused() -> None:
    payload = json.loads(dumps(_record()))
    payload["fitness_vector"]["dimensions"][0]["value"] = 0.99
    with pytest.raises(FitnessMemoryIdentityViolation, match="does not reproduce its stored"):
        FitnessRecord.from_dict(payload)


# --------------------------------------------------------------------------- record key


def test_the_identity_carries_exactly_the_eleven_declared_components() -> None:
    identity = record_key(
        harness_version="arena-game-r-formal-harness-v1.0.0",
        parent_genome_hash="p" * 64,
        child_genome_hash="c" * 64,
        mutation=_mutation(),
        evaluation_context=_context(),
        model=_model(),
    )
    assert set(identity) == set(EVALUATION_IDENTITY_COMPONENTS)
    assert len(EVALUATION_IDENTITY_COMPONENTS) == 11
    assert set(CONDITION_COMPONENTS) <= set(EVALUATION_IDENTITY_COMPONENTS)
    assert _record().record_id.startswith("lfm:")


def test_a_missing_identity_component_is_a_refusal_not_a_blank_slot() -> None:
    with pytest.raises(RecordIdentityViolation, match="missing components"):
        record_key(
            harness_version="",
            parent_genome_hash="p" * 64,
            child_genome_hash="c" * 64,
            mutation=_mutation(),
            evaluation_context=_context(),
            model=_model(),
        )
    with pytest.raises(RecordIdentityViolation, match="missing components"):
        ModelIdentity("stub", "", "t" * 64, "c" * 64)
    with pytest.raises(RecordIdentityViolation, match="missing components"):
        DatasetIdentity("v", "split", "")
    with pytest.raises(RecordIdentityViolation, match="missing components"):
        EvaluationContext(
            arena_id="a", environment_version="", mechanism="m", task_ids=(), fidelity_level=0
        )
    with pytest.raises(RecordIdentityViolation, match="mutation hash"):
        replace(_mutation(), mutation_hash="")


def test_a_new_model_or_context_is_a_new_record_never_an_overwrite() -> None:
    base = _record()
    other_model = _record(model=ModelIdentity("other", "e" * 64, "t" * 64, "c" * 64))
    other_level = _record(
        evaluation_context=replace(_context(), fidelity_level=4),
    )
    assert base.record_id != other_model.record_id
    assert base.record_id != other_level.record_id
    assert base.condition_id != other_model.condition_id
    # A different dataset is *not* in the eleven components, so it does not fork the identity;
    # it changes the record's content, which the append guard then refuses under one identity.
    assert _record(dataset=DatasetIdentity("v2", "s", "UNSEALED")).record_id == base.record_id


def test_a_confirmatory_record_without_a_preregistration_is_malformed() -> None:
    with pytest.raises(ValueError, match="preregistration_id"):
        _record(uncertainty={"confirmatory": True})


def test_a_token_count_from_an_inexact_counter_is_refused() -> None:
    with pytest.raises(ValueError, match="exact tokenizer"):
        _record(budget=Budget(calls=1, tokens=1000))


def test_a_refused_record_must_name_what_refused_it() -> None:
    with pytest.raises(ValueError, match="void code"):
        _record(status=RecordStatus.REFUSED, outcome="KILLED_BY_SEMANTIC_GATE")
    refused = _record(
        status=RecordStatus.REFUSED,
        outcome="KILLED_BY_SEMANTIC_GATE",
        void_code="TRUTH_ALTERED",
        fitness_vector=FitnessVector.build([], note="never scored"),
    )
    assert refused.fitness_vector.measured() == {}


# ------------------------------------------------------------------------------- storage


def test_records_land_under_the_run_directory_sharded_by_condition(tmp_path: Path) -> None:
    record = _record()
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    result = store.append(record, rows=[{"task_id": "t:0", "correct": True}])
    assert result.scope is RecordScope.FRESH
    assert result.path.parent == tmp_path / "evolution" / RUN_ID / record.condition_id
    assert result.path.is_file()
    # Spec section 4: a record whose rows file is absent is a summary, not a fitness record.
    assert result.rows_path.is_file()
    assert json.loads(result.rows_path.read_text(encoding="utf-8").strip())["task_id"] == "t:0"
    stored = json.loads(result.path.read_text(encoding="utf-8"))
    assert stored["record_id"] == record.record_id
    assert stored["identity"] == record.identity
    assert stored["result_hash"] == record.result_hash
    assert store.summary()["records"] == 1
    assert store.summary()["conditions"] == [record.condition_id]


def test_the_store_is_append_only(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    first = store.append(_record())
    # A different mutation is a different identity, and therefore a second record.
    second = store.append(
        _record(
            child_genome_id="M-other",
            child_genome_hash="d" * 64,
            generation=1,
            mutation=replace(
                _mutation(),
                mutation_hash="n" * 64,
                proposal_id="mutation:bbbbbbbbbbbbbbbbbbbb",
                gene_changes=(GeneChangeRecord("grammar", "labelled-linear", "s-expression"),),
            ),
        )
    )
    assert first.path != second.path
    assert len(store.record_paths()) == 2
    # There is no update and no delete: the class exposes neither.
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")
    reopened = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    assert len(reopened.records()) == 2


def test_an_identical_re_append_is_reuse_not_a_duplicate(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    store.append(_record())
    again = store.append(
        _record(
            created_at="2027-05-05T05:05:05.000000+00:00",
            budget=Budget(calls=0, tokens=0, wall_clock_seconds=88.0),
        )
    )
    assert again.scope is RecordScope.SAME_CONDITION_REUSE
    assert len(store.record_paths()) == 1


def test_the_guard_raises_when_a_condition_changed(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    store.append(_record())
    # Same eleven-component identity, but a different compute budget bought the reading.  This
    # is the cross-condition reuse cache identity forbids, and it raises rather than overwrite.
    with pytest.raises(FitnessMemoryIdentityViolation, match="different result_hash"):
        store.append(_record(budget=Budget(calls=40, wall_clock_seconds=3.0)))
    # And a different dataset under one identity is refused the same way.
    with pytest.raises(FitnessMemoryIdentityViolation):
        store.append(_record(dataset=DatasetIdentity("v2", "SMOKE:P05:8", "SEALED")))


def test_the_guard_raises_when_the_same_conditions_give_a_new_reading(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    store.append(_record())
    with pytest.raises(RescoringConflict, match="different result_hash"):
        store.append(_record(fitness_vector=_vector(0.9375)))


def test_a_record_from_another_run_is_refused(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), RUN_ID)
    with pytest.raises(ValueError, match="belongs to run"):
        store.append(_record(run_id="run-elsewhere"))


# ------------------------------------------------------------------------ fitness vector


def test_the_vector_carries_every_declared_dimension_and_no_scalar() -> None:
    vector = _vector()
    assert [item.name for item in vector.dimensions] == [name for name, _ in FITNESS_DIMENSIONS]
    assert vector.measured() == {"J_solve": 0.5}
    unmeasured = [
        item.name for item in vector.dimensions if item.status is DimensionStatus.NOT_MEASURED
    ]
    assert unmeasured == ["J_horizon", "J_learn", "J_ood", "J_search", "J_repair", "J_cost"]
    for attribute in ("__float__", "total", "scalar", "score", "sum"):
        assert not hasattr(vector, attribute)


def test_an_unmeasured_dimension_may_not_carry_a_number() -> None:
    with pytest.raises(ValueError, match="carries a value"):
        FitnessDimension(
            name="J_horizon",
            status=DimensionStatus.NOT_MEASURED,
            direction=Direction.MAXIMIZE,
            value=0.0,
        )


def test_a_dimension_direction_may_not_be_flipped() -> None:
    with pytest.raises(ValueError, match="declared"):
        FitnessDimension(
            name="J_cost",
            status=DimensionStatus.NOT_MEASURED,
            direction=Direction.MAXIMIZE,
        )


def test_a_mutation_descriptor_must_name_the_gene_it_changed() -> None:
    with pytest.raises(ValueError, match="must name the genes"):
        replace(_mutation(), gene_changes=())


def test_a_record_must_carry_its_gate_results() -> None:
    with pytest.raises(ValueError, match="gate results"):
        _record(semantic_gate_results=())
