"""The outer loop, end to end and offline.

The whole file is designed to stay well inside a minute: the arena pools are small, the
adversary's resampling budgets are reduced, and nothing here constructs a Solver.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from arena.canonical.schema import CanonicalState
from arena.evolution.loop import (
    ArenaSpec,
    EvaluationOutcome,
    EvolutionLoop,
    FailureMode,
    LoopConfig,
    Outcome,
    ParentSelection,
    StubLadderEvaluator,
    build_fitness_vector,
    leakage_gate,
    live_gene_families,
    main,
    observations_from_rows,
    rendered_prompts,
    seed_population,
    semantic_gate,
)
from arena.evolution.record import DimensionStatus, GateStatus, RecordStatus
from arena.experiments.game_r_formal_v1 import MaterialisedItem, OllamaSolver
from arena.genome.schema import LanguageGenome
from arena.genome.seeds import SEED_GENOME_BY_ID, SEED_GENOMES
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.languages.registry import SEED_LANGUAGES, get_language, language_for_genome
from arena.pipeline import ArenaRuntime
from arena.storage.artifacts import ArtifactStore

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Small enough to keep the file fast, large enough that every stage does real work.
FAST_ARENA = ArenaSpec(solve_families=3, adversary_families=8)


def fast_config(**overrides: Any) -> LoopConfig:
    base: dict[str, Any] = {
        "seed": 20260908,
        "generations": 1,
        "population": 4,
        "arena": FAST_ARENA,
        "adversary_permutations": 60,
        "adversary_bootstrap": 40,
    }
    base.update(overrides)
    return LoopConfig(**base)


@pytest.fixture(scope="module")
def solve_items() -> tuple[MaterialisedItem, ...]:
    return FAST_ARENA.solve_items()


class CountingEvaluator(StubLadderEvaluator):
    """A stub that records how many times the loop asked it to score something."""

    calls_made: list[str]

    def __init__(self) -> None:
        super().__init__()
        object.__setattr__(self, "calls_made", [])

    def evaluate(self, **kwargs: Any) -> EvaluationOutcome:
        self.calls_made.append(kwargs["genome"].candidate_id)
        return super().evaluate(**kwargs)


class TruthAlteringLanguage(GenomePhenotypeLanguage):
    """A renderer that silently drops one ``holds(...)`` assumption.

    This is the attack the semantic gate exists for: the bytes still parse, the surface still
    looks like a state, and the mathematics on the page is no longer the mathematics in the
    backend.  Layer A is not negotiable (``HAMILTONIAN_CHESS_META_GOAL.md`` section 4).
    """

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        thinned = dict(payload)
        assumptions = list(thinned.get("assumptions", []))
        for index, item in enumerate(assumptions):
            if isinstance(item, dict) and item.get("op") == "holds":
                del assumptions[index]
                break
        thinned["assumptions"] = assumptions
        return super()._encode_payload(thinned)


# ------------------------------------------------------------------------- semantic gate


def test_the_gate_accepts_every_honest_seed_surface(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    parent = SEED_GENOME_BY_ID["L0_STRUCTURED_ENGLISH"]
    for genome in SEED_GENOMES:
        if genome.candidate_id == parent.candidate_id:
            continue
        report = semantic_gate(parent=parent, child=genome, items=solve_items)
        assert report.passed, (genome.candidate_id, [g.detail for g in report.outcomes])
        assert report.inert is False
    # And the round-trip check on its own passes for all eight, including the parent.
    for language in SEED_LANGUAGES:
        for item in solve_items:
            state: CanonicalState = item.canonical_state
            assert language.parse(language.render(state)).mathematical_hash == (
                state.mathematical_hash
            )


def test_the_gate_kills_a_renderer_that_drops_an_assumption(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    parent = SEED_GENOME_BY_ID["L0_STRUCTURED_ENGLISH"]
    child = SEED_GENOME_BY_ID["L2_SEXPR"]
    hostile = TruthAlteringLanguage(child)

    # The attack really does change the mathematics, not merely the bytes.
    state = solve_items[0].canonical_state
    assert hostile.parse(hostile.render(state)).mathematical_hash != state.mathematical_hash

    report = semantic_gate(parent=parent, child=child, items=solve_items, child_language=hostile)
    assert not report.passed
    assert FailureMode.TRUTH_ALTERED.value in report.failure_modes
    assert report.outcomes[0].name == "semantic_roundtrip"
    assert report.outcomes[0].status is GateStatus.FAIL
    # Elimination is non-compensatory: nothing after the failed check is even attempted.
    assert [item.name for item in report.outcomes] == ["semantic_roundtrip"]


def test_a_killed_candidate_is_never_scored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evaluator = CountingEvaluator()
    loop = EvolutionLoop(
        store=ArtifactStore(tmp_path),
        config=fast_config(),
        evaluator=evaluator,
    )
    monkeypatch.setattr(
        "arena.evolution.loop.language_for_genome",
        lambda genome: TruthAlteringLanguage(genome),
    )
    result = loop.run_generation(0)
    child = result.candidates[0]
    assert child.outcome is Outcome.KILLED_BY_SEMANTIC_GATE
    assert child.evaluation is None
    assert FailureMode.TRUTH_ALTERED.value in child.record.failure_modes
    assert child.record.fitness_vector.measured() == {}
    # A refusal is a record, and it names what refused it.
    assert child.record.status is RecordStatus.REFUSED
    assert child.record.void_code == FailureMode.TRUTH_ALTERED.value
    assert child.child_id not in evaluator.calls_made


def test_an_inert_mutation_is_detected_and_recorded_as_inert(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    parent = SEED_GENOME_BY_ID["L0_STRUCTURED_ENGLISH"]
    _, inert_families = live_gene_families(parent, solve_items[0])
    assert inert_families, "the arena must have at least one byte-inert gene family"
    family = sorted(inert_families, key=lambda item: item.value)[0]

    from arena.genome.genes import GENE_ENUMS

    value = next(v.value for v in GENE_ENUMS[family] if v.value != parent.gene(family))
    child = parent.with_gene_values(
        {family: value}, candidate_id="M-inert-probe", parent_ids=(parent.candidate_id,)
    )
    report = semantic_gate(parent=parent, child=child, items=solve_items)
    assert report.inert is True
    assert not report.passed
    assert FailureMode.MUTATION_INERT.value in report.failure_modes
    effective = next(item for item in report.outcomes if item.name == "mutation_effective")
    assert effective.evidence["differing_prompts"] == 0


def test_live_and_inert_families_partition_the_genome(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    from arena.genome.genes import GeneFamily

    live, inert = live_gene_families(SEED_GENOME_BY_ID["L0_STRUCTURED_ENGLISH"], solve_items[0])
    assert live | inert == set(GeneFamily)
    assert not live & inert
    assert live, "no gene family reaches the bytes; the loop would have nothing to search"


# -------------------------------------------------------------------------- leakage gate


def test_the_leakage_gate_costs_no_model_calls_and_reports_its_power() -> None:
    items = FAST_ARENA.adversary_items()
    outcome = leakage_gate(
        SEED_GENOME_BY_ID["L0_STRUCTURED_ENGLISH"],
        items,
        seed=20260908,
        permutations=60,
        bootstrap_samples=40,
    )
    assert outcome.evidence["model_calls"] == 0
    assert outcome.evidence["n_rules"] == 64
    assert outcome.status in {GateStatus.PASS, GateStatus.UNDERPOWERED}
    # An underpowered gate must say so rather than read as a clean pass.
    if outcome.status is GateStatus.UNDERPOWERED:
        assert (
            outcome.evidence["bonferroni_upper"] >= outcome.evidence["declared_target_upper_bound"]
        )
        assert not outcome.eliminated


# -------------------------------------------------------------------------- one generation


def test_one_generation_runs_end_to_end_offline(tmp_path: Path) -> None:
    loop = EvolutionLoop(store=ArtifactStore(tmp_path), config=fast_config())
    summary = loop.run()

    assert summary["model_calls"] == 0
    assert summary["model"]["is_stub"] is True
    assert summary["scientific_status"] == "EXECUTABILITY_ONLY_NOT_A_RESULT"
    assert len(summary["generations"]) == 1
    assert summary["records"]["records"] == 1

    records = loop.records.records()
    assert len(records) == 1
    assert records[0].outcome == Outcome.SCORED.value
    assert records[0].status is RecordStatus.COMPLETE
    assert records[0].record_id.startswith("lfm:")
    assert records[0].provenance["confirmatory"] is False
    assert (tmp_path / "evolution" / loop.config.run_id / "summary.json").is_file()
    assert (tmp_path / "evolution" / loop.config.run_id / "league-registry.json").is_file()


def test_the_archive_receives_rows_and_ranking_returns_a_front(tmp_path: Path) -> None:
    loop = EvolutionLoop(store=ArtifactStore(tmp_path), config=fast_config())
    result = loop.run_generation(0)

    assert loop.registry.observations, "the league registry has never been written to before"
    scored = [item for item in result.candidates if item.outcome is Outcome.SCORED]
    assert scored, "the generation produced no scored candidate"
    child = scored[0].child_id
    assert any(item.candidate_id == child for item in loop.registry.observations)
    assert loop.registry.candidates[child].domain_ratings, "no multi-axis rating was computed"

    assert result.fronts and result.fronts[0], "ranking returned an empty front"
    assert set(result.population_after) <= set(loop.genomes)
    # Every ranked candidate carries the objectives the front was computed from.
    for front in result.fronts:
        for candidate_id in front:
            assert {"J_solve", "J_cost"} <= set(
                loop.registry.candidates[candidate_id].objective_metrics
            )


def test_the_fitness_vector_is_not_collapsed_to_a_scalar(tmp_path: Path) -> None:
    loop = EvolutionLoop(store=ArtifactStore(tmp_path), config=fast_config())
    result = loop.run_generation(0)
    record = result.candidates[0].record
    vector = record.fitness_vector

    names = [item.name for item in vector.dimensions]
    assert names == ["J_solve", "J_horizon", "J_learn", "J_ood", "J_search", "J_repair", "J_cost"]
    assert set(vector.measured()) == {"J_solve", "J_cost"}
    unmeasured = {
        item.name for item in vector.dimensions if item.status is DimensionStatus.NOT_MEASURED
    }
    assert unmeasured == {"J_horizon", "J_learn", "J_ood", "J_search", "J_repair"}
    for attribute in ("__float__", "total", "scalar", "score"):
        assert not hasattr(vector, attribute)
    # And the stored JSON keeps all seven, so a downstream reader cannot mistake absence for zero.
    stored = json.loads(loop.records.record_paths()[0].read_text(encoding="utf-8"))
    assert len(stored["fitness_vector"]["dimensions"]) == 7


def test_two_runs_are_identical_apart_from_timing(tmp_path: Path) -> None:
    def run(where: Path) -> list[dict[str, Any]]:
        loop = EvolutionLoop(store=ArtifactStore(where), config=fast_config())
        loop.run()
        payloads = []
        for path in loop.records.record_paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("created_at")
            payload["budget"].pop("wall_clock_seconds")
            payloads.append(payload)
        return payloads

    first = run(tmp_path / "a")
    second = run(tmp_path / "b")
    assert first == second
    assert [item["content_hash"] for item in first] == [item["content_hash"] for item in second]


def test_a_second_run_into_the_same_store_is_reuse_not_a_second_score(tmp_path: Path) -> None:
    config = fast_config()
    EvolutionLoop(store=ArtifactStore(tmp_path), config=config).run()
    second = EvolutionLoop(store=ArtifactStore(tmp_path), config=config)
    second.run()
    assert len(second.records.record_paths()) == 1


def test_pareto_rank_selection_is_deterministic(tmp_path: Path) -> None:
    config = fast_config(generations=2, strategy=ParentSelection.PARETO_RANK)
    first = EvolutionLoop(store=ArtifactStore(tmp_path / "a"), config=config).run()
    second = EvolutionLoop(store=ArtifactStore(tmp_path / "b"), config=config).run()
    assert first["records"]["manifest_hash"] == second["records"]["manifest_hash"]
    assert first["final_front"] == second["final_front"]


# -------------------------------------------------------------------------------- offline


def test_the_loop_makes_no_network_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the offline loop attempted a network call")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(OllamaSolver, "generate", refuse)
    monkeypatch.delitem(sys.modules, "arena.experiments.ollama_live", raising=False)

    summary = EvolutionLoop(store=ArtifactStore(tmp_path), config=fast_config()).run()

    assert summary["model_calls"] == 0
    assert summary["model"]["is_stub"] is True
    # No live-solver module was imported, and no OllamaSolver was constructed.
    assert "arena.experiments.ollama_live" not in sys.modules


def test_the_stub_evaluator_declares_itself_a_stub() -> None:
    evaluator = StubLadderEvaluator()
    assert evaluator.model.is_stub is True
    assert evaluator.fidelity_level == 0
    outcome = evaluator.evaluate(
        genome=SEED_GENOME_BY_ID["L2_SEXPR"],
        language=get_language("L2_SEXPR"),
        items=FAST_ARENA.solve_items(),
    )
    assert outcome.calls == 0 and outcome.tokens == 0
    assert any("chance-level" in note for note in outcome.notes)


# ----------------------------------------------------------------- the reconnected loop


def _disk_mutants() -> list[LanguageGenome]:
    directory = REPO_ROOT / "artifacts" / "candidates"
    if not directory.is_dir():
        return []
    return [
        LanguageGenome.from_dict(json.loads((path / "genome.json").read_text(encoding="utf-8")))
        for path in sorted(directory.glob("M-*"))
        if (path / "genome.json").is_file()
    ]


def test_every_mutant_on_disk_is_renderable_by_the_fallback(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    mutants = _disk_mutants()
    if not mutants:
        pytest.skip("no mutant genomes are stored in this checkout")
    state = solve_items[0].canonical_state
    for genome in mutants:
        language = language_for_genome(genome)
        assert isinstance(language, GenomePhenotypeLanguage)
        assert language.parse(language.render(state)).mathematical_hash == state.mathematical_hash


def test_a_mutant_from_disk_is_evaluable_by_the_loop(
    solve_items: tuple[MaterialisedItem, ...],
) -> None:
    mutants = _disk_mutants()
    if not mutants:
        pytest.skip("no mutant genomes are stored in this checkout")
    evaluator = StubLadderEvaluator()
    effective = 0
    for genome in mutants:
        parent = SEED_GENOME_BY_ID[genome.parent_ids[0]]
        report = semantic_gate(parent=parent, child=genome, items=solve_items)
        if report.inert:
            continue
        effective += 1
        assert report.passed, (genome.candidate_id, [g.detail for g in report.outcomes])
        outcome = evaluator.evaluate(
            genome=genome, language=language_for_genome(genome), items=solve_items
        )
        vector = build_fitness_vector(outcome)
        assert set(vector.measured()) == {"J_solve", "J_cost"}
        assert observations_from_rows(outcome, arena_id="test", opponent_id=parent.candidate_id)
    assert effective, "every stored mutant was byte-inert; none could be scored"


def test_the_pipeline_evaluates_a_mutant_genome_written_to_the_artifact_store(
    tmp_path: Path,
) -> None:
    """Task 1's claim, through the real ``ArenaRuntime.evaluate`` path.

    Genomes are copied verbatim out of ``artifacts/candidates`` into a scratch artifact root so
    the checkout's own artifacts are neither read-locked nor written to.
    """

    mutants = _disk_mutants()
    if not mutants:
        pytest.skip("no mutant genomes are stored in this checkout")
    candidates = tmp_path / "artifacts" / "candidates"
    for genome in mutants[:4]:
        target = candidates / genome.candidate_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "genome.json").write_text(
            json.dumps(genome.to_dict(), sort_keys=True), encoding="utf-8"
        )

    runtime = ArenaRuntime(tmp_path)
    runtime.build_worlds(total=8, seed=0)
    for genome in mutants[:4]:
        evaluation = runtime.evaluate(genome.candidate_id, tier=1)
        assert evaluation.candidate_id == genome.candidate_id
        assert evaluation.metric_values()["semantic_fidelity"] == 1.0

    with pytest.raises(ValueError, match="no executable renderer"):
        runtime.evaluate("NOT_A_CANDIDATE")


def test_seed_surfaces_keep_their_hand_coded_objects() -> None:
    for language in SEED_LANGUAGES:
        assert get_language(language.candidate_id) is language
        assert language_for_genome(language.genome) is language


# ------------------------------------------------------------------------------------ CLI


def test_the_cli_prints_a_compact_json_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "--generations",
            "1",
            "--population",
            "3",
            "--seed",
            "20260908",
            "--solve-families",
            "3",
            "--adversary-families",
            "8",
            "--out",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["model_calls"] == 0
    assert printed["records"] >= 1
    assert printed["scientific_status"] == "EXECUTABILITY_ONLY_NOT_A_RESULT"
    assert printed["generations"][0]["candidates"][0]["fitness"].keys() >= {"J_solve", "J_cost"}

    # The full summary, including every schema divergence, is on disk.
    stored = json.loads(
        (tmp_path / "evolution" / printed["run_id"] / "summary.json").read_text(encoding="utf-8")
    )
    assert stored["config"]["population"] == 3
    assert stored["schema_divergences"]


def test_the_population_comes_from_the_seed_genomes() -> None:
    population = seed_population(4)
    assert len(population) == 4
    assert [genome.candidate_id for genome in population] == [
        genome.candidate_id for genome in SEED_GENOMES[:4]
    ]
    assert all(
        len(rendered_prompts(genome, FAST_ARENA.solve_items())) == 6 for genome in population
    )
