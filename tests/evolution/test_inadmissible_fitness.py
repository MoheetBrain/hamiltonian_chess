"""RT-16: a stub reading is unrepresentable as scientific fitness.

``docs/HC_V0_RED_TEAM.md`` RT-16 asked one blunt question - *is ``J_solve = 0.75`` reachable by a
reader who never sees the stamp?* - and answered yes: it was in ``league-registry.json`` and in
every ``lfm-*.json``, while the machine-readable ``EXECUTABILITY_ONLY_NOT_A_RESULT`` stamp lived
only in ``summary.json``.  The registry additionally marked all 256 stub rows ``verified: true``
and computed normal-approximation intervals over them.

The fix asked for was at the type/schema level, not another warning string.  So: under
``EXECUTABILITY_STUB`` the fitness dimensions cannot hold numbers at all, the numbers that were
computed live in a type whose keys may never be a ``J_*`` name, and no archive ranking can be
expressed in fitness terms.  These tests are the acceptance criteria for that.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from arena.evolution.loop import (
    ArenaSpec,
    EvaluationOutcome,
    EvolutionLoop,
    LoopConfig,
    StubLadderEvaluator,
    archive_objectives,
    build_diagnostics,
    build_fitness_vector,
    objectives_for,
)
from arena.evolution.record import (
    RESERVED_DIAGNOSTIC_NAMES,
    DiagnosticReadings,
    DimensionStatus,
    EvaluationMode,
    EvidenceActor,
    EvolutionRecordStore,
    FitnessDimension,
    FitnessVector,
    StubFitnessNotRepresentable,
    UnreportableReason,
)
from arena.fitness.metrics import Direction
from arena.genome.seeds import SEED_GENOMES
from arena.languages.registry import language_for_genome
from arena.storage.artifacts import ArtifactStore
from tests.evolution import factory

FAST = LoopConfig(
    seed=20260908,
    generations=1,
    population=4,
    arena=ArenaSpec(solve_families=3, adversary_families=8),
    adversary_permutations=60,
    adversary_bootstrap=40,
)


def _measured_solve(value: float = 0.75) -> FitnessDimension:
    return FitnessDimension(
        name="J_solve",
        status=DimensionStatus.MEASURED,
        direction=Direction.MAXIMIZE,
        value=value,
        lower=0.5,
        upper=0.9,
        unit_of_analysis="item",
        estimator="wilson",
        n=16,
        n_clusters=8,
        reportable=True,
    )


# ------------------------------ the acceptance test the brief names, at three layers


def test_a_numeric_j_solve_under_the_stub_cannot_be_built() -> None:
    """Layer 1: the vector.  There is no object to persist, so persistence never arises."""

    with pytest.raises(StubFitnessNotRepresentable, match="cannot produce scientific fitness"):
        FitnessVector.build(
            [_measured_solve()],
            note="the exact number RT-16 found in league-registry.json",
            evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
            actor=EvidenceActor.SOLVER,
        )


def test_a_numeric_j_solve_cannot_be_smuggled_into_a_stub_record() -> None:
    """Layer 2: the record.  An admissible vector cannot be filed under a stub record."""

    with pytest.raises(StubFitnessNotRepresentable, match="cannot produce scientific fitness"):
        factory.record(
            evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
            fitness_vector=FitnessVector.build(
                [_measured_solve()],
                note="built under SCIENTIFIC, filed under the stub",
                evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
                actor=EvidenceActor.SOLVER,
            ),
            diagnostics=factory.diagnostics(),
        )
    # ... and the mismatch itself is caught, so relabelling only the vector fails too.
    with pytest.raises(Exception, match="fitness vector was built under SCIENTIFIC"):
        factory.record(
            evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
            fitness_vector=factory.scientific_vector(0.75),
            diagnostics=factory.diagnostics(),
        )


def test_a_stub_reading_cannot_borrow_a_fitness_name_in_the_diagnostics_channel() -> None:
    """Layer 3: the escape hatch.  A number under a ``J_*`` key is a fitness claim regardless."""

    assert {
        "J_solve",
        "J_horizon",
        "J_learn",
        "J_ood",
        "J_search",
        "J_repair",
        "J_cost",
    } == RESERVED_DIAGNOSTIC_NAMES
    with pytest.raises(StubFitnessNotRepresentable, match="may not borrow fitness dimension"):
        DiagnosticReadings(basis="EXECUTABILITY_STUB", readings={"J_solve": 0.75})


def test_a_stub_record_must_say_what_it_computed_instead() -> None:
    """ "No fitness" must not be mistakeable for "nothing was measured"."""

    with pytest.raises(StubFitnessNotRepresentable, match="must carry DiagnosticReadings"):
        factory.stub_record(diagnostics=None)


# ------------------------------------------------- what the stub record does look like


def test_the_stored_record_carries_no_number_in_any_dimension(tmp_path: Path) -> None:
    store = EvolutionRecordStore(ArtifactStore(tmp_path), factory.RUN_ID)
    result = store.append(factory.stub_record())
    stored = json.loads(result.path.read_text(encoding="utf-8"))

    assert stored["evaluation_mode"] == "EXECUTABILITY_STUB"
    assert stored["fitness_vector"]["admissible_as_fitness"] is False
    assert [item["value"] for item in stored["fitness_vector"]["dimensions"]] == [None] * 7
    addressed = {
        item["name"]
        for item in stored["fitness_vector"]["dimensions"]
        if item["status"] == DimensionStatus.NOT_REPRESENTABLE.value
    }
    assert addressed == {"J_solve", "J_cost"}
    assert stored["diagnostics"]["is_scientific_fitness"] is False
    assert set(stored["diagnostics"]["archive_metrics"]) == {
        "EXECUTABILITY_STUB::stub_choice_agreement",
        "EXECUTABILITY_STUB::rendered_prompt_bytes_mean",
    }
    # The number RT-16 objected to is still recoverable - under a name that says what it is.
    assert stored["diagnostics"]["readings"]["stub_choice_agreement"] == 0.75


def test_not_representable_is_not_a_general_escape_hatch() -> None:
    """The status may only be used for a structural reason, so it cannot hide a real reading."""

    with pytest.raises(ValueError, match="without a structural reason"):
        FitnessDimension(
            name="J_solve",
            status=DimensionStatus.NOT_REPRESENTABLE,
            direction=Direction.MAXIMIZE,
            unreportable_reason=UnreportableReason.INSUFFICIENT_N.value,
        )
    with pytest.raises(ValueError, match="carries a value"):
        FitnessDimension(
            name="J_solve",
            status=DimensionStatus.NOT_REPRESENTABLE,
            direction=Direction.MAXIMIZE,
            value=0.75,
            unreportable_reason=UnreportableReason.EXECUTABILITY_STUB.value,
        )


def test_declaring_an_admissible_run_inadmissible_is_refused() -> None:
    """``inadmissible()`` cannot be used to hide a real measurement behind a status."""

    with pytest.raises(ValueError, match="may carry scientific fitness"):
        FitnessVector.inadmissible(
            evaluation_mode=EvaluationMode.SCIENTIFIC,
            actor=EvidenceActor.SOLVER,
            note="hiding a real reading",
        )


# --------------------------------------------- the archive cannot rank on stub fitness


def test_the_archive_refuses_to_rank_a_stub_record_on_fitness() -> None:
    record = factory.stub_record()
    assert archive_objectives(record) == {
        "EXECUTABILITY_STUB::stub_choice_agreement": 0.75,
        "EXECUTABILITY_STUB::rendered_prompt_bytes_mean": 18755.0,
    }
    assert not set(archive_objectives(record)) & RESERVED_DIAGNOSTIC_NAMES
    assert [item.name for item in objectives_for(EvaluationMode.EXECUTABILITY_STUB)] == [
        "EXECUTABILITY_STUB::stub_choice_agreement",
        "EXECUTABILITY_STUB::rendered_prompt_bytes_mean",
    ]
    assert [item.name for item in objectives_for(EvaluationMode.SCIENTIFIC)] == [
        "J_solve",
        "J_cost",
    ]


def test_a_scientific_record_still_ranks_on_fitness() -> None:
    """The guard is about the stub, not about ranking: a real evaluator is unaffected."""

    assert archive_objectives(factory.record()) == {"J_solve": 0.5}


def test_a_forged_diagnostic_block_cannot_reintroduce_a_j_key() -> None:
    """The last door: hand-editing the stored diagnostics to carry ``J_solve`` again."""

    record = factory.stub_record()
    forged = DiagnosticReadings.__new__(DiagnosticReadings)
    object.__setattr__(forged, "basis", "")
    object.__setattr__(forged, "readings", {"J_solve": 0.75})
    object.__setattr__(forged, "note", "")
    with pytest.raises(StubFitnessNotRepresentable, match="refusing to rank"):
        archive_objectives(replace(record, diagnostics=forged))


# ------------------------------------------------------------------ end to end, on disk


def test_no_artefact_the_loop_writes_contains_a_scientific_j_solve(tmp_path: Path) -> None:
    """RT-16's own question, asked of every durable file the loop produces."""

    loop = EvolutionLoop(store=ArtifactStore(tmp_path), config=FAST)
    summary = loop.run()
    run_directory = tmp_path / "evolution" / summary["run_id"]

    league = json.loads((run_directory / "league-registry.json").read_text(encoding="utf-8"))
    metrics = {key for entry in league["candidates"] for key in entry.get("objective_metrics", {})}
    assert metrics, "the archive recorded no objectives at all"
    assert not metrics & RESERVED_DIAGNOSTIC_NAMES
    assert all(key.startswith("EXECUTABILITY_STUB::") for key in metrics)
    # RT-16: 256 stub rows marked verified=true, rated with a normal-approximation interval.
    assert league["observations"], "the archive recorded no rows"
    assert not any(item["verified"] for item in league["observations"])
    assert all(not entry["domain_ratings"] for entry in league["candidates"])

    for path in loop.records.record_paths():
        stored = json.loads(path.read_text(encoding="utf-8"))
        assert all(item["value"] is None for item in stored["fitness_vector"]["dimensions"])

    # And the summary still carries the stamp it always carried.
    stored_summary = json.loads((run_directory / "summary.json").read_text(encoding="utf-8"))
    assert stored_summary["scientific_status"] == "EXECUTABILITY_ONLY_NOT_A_RESULT"
    assert stored_summary["evaluation_mode"] == "EXECUTABILITY_STUB"
    assert stored_summary["observations_verified"] is False


def test_the_stub_loop_still_ranks_selects_and_survives(tmp_path: Path) -> None:
    """Executability is the point of V0: refusing to represent fitness must not stop the loop."""

    loop = EvolutionLoop(store=ArtifactStore(tmp_path), config=replace(FAST, generations=2))
    summary = loop.run()
    assert summary["final_front"], "the frontier collapsed once fitness became unrepresentable"
    assert summary["records"]["records"] >= 1
    assert summary["archive_observations"] > 0
    generation = summary["generations"][-1]
    assert generation["population_after"]


def _stub_outcome() -> EvaluationOutcome:
    genome = SEED_GENOMES[0]
    return StubLadderEvaluator().evaluate(
        genome=genome,
        language=language_for_genome(genome),
        items=FAST.arena.solve_items(),
    )


def test_the_stub_diagnostics_are_deterministic() -> None:
    outcome = _stub_outcome()
    first = build_diagnostics(outcome, basis=EvaluationMode.EXECUTABILITY_STUB)
    second = build_diagnostics(outcome, basis=EvaluationMode.EXECUTABILITY_STUB)
    assert first.to_dict() == second.to_dict()
    assert (
        build_fitness_vector(
            outcome,
            evaluation_mode=EvaluationMode.EXECUTABILITY_STUB,
            actor=EvidenceActor.SOLVER,
        ).measured()
        == {}
    )


# --------------------------------- and the scientific path is untouched by all of this


class PretendScientificEvaluator(StubLadderEvaluator):
    """The same arithmetic, declared ``SCIENTIFIC``.

    Not a claim that the stub becomes a solver by relabelling - it is how these tests check that
    the RT-16 fix suppresses *stub* fitness specifically, rather than fitness in general.  If the
    only passing configuration were "no numbers anywhere", the fix would be indistinguishable
    from deleting the feature.
    """

    @property
    def evaluation_mode(self) -> EvaluationMode:
        return EvaluationMode.SCIENTIFIC


def test_a_scientific_evaluator_still_produces_measured_fitness(tmp_path: Path) -> None:
    loop = EvolutionLoop(
        store=ArtifactStore(tmp_path), config=FAST, evaluator=PretendScientificEvaluator()
    )
    summary = loop.run()
    (record,) = loop.records.records()

    assert set(record.fitness_vector.measured()) == {"J_solve", "J_cost"}
    assert record.fitness_vector.admissible_as_fitness
    assert record.diagnostics is None
    assert summary["ranked_on"] == ["J_solve", "J_cost"]
    assert summary["observations_verified"] is True

    league = json.loads(
        (tmp_path / "evolution" / summary["run_id"] / "league-registry.json").read_text(
            encoding="utf-8"
        )
    )
    assert all(item["verified"] for item in league["observations"])
    assert any(entry["domain_ratings"] for entry in league["candidates"])
    assert any(
        {"J_solve", "J_cost"} <= set(entry["objective_metrics"]) for entry in league["candidates"]
    )
