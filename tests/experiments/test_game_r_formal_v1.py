"""Tests for the Game-R founder-parity harness.

Every test here is offline, CPU-only and makes **no model call**: the only solver used is
:class:`StubSolver`, which never opens a socket.  Each test is named for the historical
defect it prevents from recurring.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from arena.canonical.schema import stable_hash
from arena.experiments import game_r_formal_v1 as harness
from arena.experiments.game_r_formal_v1 import (
    ANSWER_KEY,
    CACHE_IDENTITY_COMPONENTS,
    GATE_CONSTANTS,
    BudgetExceeded,
    CacheIdentityViolation,
    CacheScope,
    CallBudget,
    ContextBudget,
    FixedTokenCounter,
    HarnessRefusal,
    ItemVariant,
    MaterialisedItem,
    ParityViolation,
    ResponseCache,
    RowStatus,
    RunConfig,
    StubEnvironment,
    StubSolver,
    StubSolverPolicy,
    StubTokenCounter,
    SyntaxGuidePolicy,
    TokenAccountingRefusal,
    build_prompt,
    cache_identity,
    cache_key,
    canonical_answer_ids,
    classify_cache_scope,
    derived_frontier_target,
    destroyed_control_accuracy,
    dry_run,
    effective_frontier_floor,
    envelope_signature,
    founder_genome,
    founder_genomes,
    gate_arithmetic,
    gate_mechanism,
    parse_answer,
    prompt_bytes_hash,
    response_schema,
    rotate_options,
    run_item,
    run_mechanism,
    score_mechanism,
    select_frontier_level,
    verify_destroyed_determinism,
)
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack

MODULE_SOURCE = Path(harness.__file__).read_text(encoding="utf-8")


def _code_only(source: str) -> str:
    """The module with every comment and string literal removed.

    Source-level assertions must read the *code*, not the prose that explains it: this
    module's own docstrings quote the defects it prevents, including "0.625" and the
    chars-per-token constants.
    """

    import io
    import tokenize

    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in {tokenize.COMMENT, tokenize.STRING}:
            continue
        kept.append(token.string)
    return " ".join(kept)


MODULE_CODE = _code_only(MODULE_SOURCE)


# ------------------------------------------------------------------------------ fixtures


def _items(families: int = 3, levels: Sequence[int] = (0, 1)) -> tuple[MaterialisedItem, ...]:
    return tuple(StubEnvironment().items(families=families, levels=levels))  # type: ignore[arg-type]


def _config(tmp_path: Path, **overrides: Any) -> RunConfig:
    base: dict[str, Any] = {
        "experiment_version": "test-experiment",
        "runtime_condition": "bare",
        "decoding": {"temperature": 0.0, "seed": 1, "num_predict": 64},
        "context": ContextBudget(num_ctx=32768, max_output_tokens=64),
        "cache_root": tmp_path / "cache",
        "guide_policy": SyntaxGuidePolicy.OMITTED,
    }
    base.update(overrides)
    return RunConfig(**base)


def _identity_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "experiment_version": "exp-1",
        "model_digest": "digest-a",
        "model_revision": "rev-a",
        "runtime_condition": "bare",
        "decoding": {"temperature": 0.0, "seed": 1},
        "schema": response_schema(2),
        "task_id": "env-v1::mech::task-1",
        "candidate_id": "GRF_L3_JSON_AST",
        "prompt": "PROMPT ONE",
    }
    base.update(overrides)
    return base


# ------------------------------------------------------- 1. cache identity, per component


def test_cache_identity_has_exactly_the_declared_components() -> None:
    identity = cache_identity(**_identity_kwargs())
    assert tuple(sorted(identity)) == tuple(sorted(CACHE_IDENTITY_COMPONENTS))
    assert len(CACHE_IDENTITY_COMPONENTS) == 8


#: One mutation per identity component.  Changing that component *alone* must miss.
_COMPONENT_MUTATIONS: dict[str, dict[str, Any]] = {
    "experiment_version": {"experiment_version": "exp-2"},
    "model_digest": {"model_digest": "digest-b"},
    "model_revision": {"model_revision": "rev-b"},
    "runtime_condition": {"runtime_condition": "framed"},
    "decoding_hash": {"decoding": {"temperature": 0.1, "seed": 1}},
    "task_id": {"task_id": "env-v1::mech::task-2"},
    "candidate_id": {"candidate_id": "GRF_L1_CURRENT_HML"},
    "prompt_hash": {"prompt": "PROMPT TWO"},
}


@pytest.mark.parametrize("component", sorted(_COMPONENT_MUTATIONS))
def test_changing_one_cache_component_alone_misses_the_cache(
    tmp_path: Path, component: str
) -> None:
    base = cache_identity(**_identity_kwargs())
    mutated = cache_identity(**_identity_kwargs(**_COMPONENT_MUTATIONS[component]))
    assert base[component] != mutated[component], component
    assert {k: v for k, v in base.items() if k != component} == {
        k: v for k, v in mutated.items() if k != component
    }, f"{component} mutation moved another component too"
    assert cache_key(base) != cache_key(mutated)

    cache = ResponseCache(tmp_path / "cache")
    cache.store(base, {"text": '{"answer":"OPTION_A"}'})
    hit, scope = cache.load(base)
    assert hit is not None and scope is CacheScope.SAME_CONDITION_REUSE
    miss, miss_scope = cache.load(mutated)
    assert miss is None and miss_scope is CacheScope.FRESH


def test_decoding_hash_covers_the_response_schema_not_only_the_options() -> None:
    base = cache_identity(**_identity_kwargs())
    other = cache_identity(**_identity_kwargs(schema=response_schema(3)))
    assert base["decoding_hash"] != other["decoding_hash"]


def test_cache_key_refuses_an_identity_with_the_wrong_components() -> None:
    identity = dict(cache_identity(**_identity_kwargs()))
    identity.pop("model_digest")
    with pytest.raises(CacheIdentityViolation):
        cache_key(identity)


def test_cross_condition_scope_is_impossible_to_serve(tmp_path: Path) -> None:
    """Phase 6 could not tell benign reuse from contamination.  Here contamination raises."""

    cache = ResponseCache(tmp_path / "cache")
    base = cache_identity(**_identity_kwargs())
    other = cache_identity(**_identity_kwargs(model_digest="digest-b"))
    path = cache.path_for(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"identity": other, "result": {"text": "x"}}), encoding="utf-8")
    with pytest.raises(CacheIdentityViolation):
        cache.load(base)


def test_classify_cache_scope_separates_the_three_cases() -> None:
    base = cache_identity(**_identity_kwargs())
    other = cache_identity(**_identity_kwargs(runtime_condition="framed"))
    assert (
        classify_cache_scope(hit=False, stored_identity=None, requested_identity=base)
        is CacheScope.FRESH
    )
    assert (
        classify_cache_scope(hit=True, stored_identity=base, requested_identity=base)
        is CacheScope.SAME_CONDITION_REUSE
    )
    assert (
        classify_cache_scope(hit=True, stored_identity=other, requested_identity=base)
        is CacheScope.CROSS_CONDITION
    )


def test_transport_errors_are_never_cached(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path / "cache")
    identity = cache_identity(**_identity_kwargs())
    cache.store(identity, {"text": "", "error": "boom"})
    assert cache.load(identity) == (None, CacheScope.FRESH)


def test_every_row_records_cache_hit_and_cache_scope(tmp_path: Path) -> None:
    items, genomes = _items(2, (0,)), [founder_genome("L3_JSON_AST")]
    config = _config(tmp_path)
    kwargs: dict[str, Any] = {
        "mechanism": "m",
        "environment_version": "env-v1",
        "config": config,
        "counter": StubTokenCounter(),
        "cache": ResponseCache(config.cache_root),
    }
    first = run_mechanism(
        items,
        genomes,
        solver=StubSolver(policy=StubSolverPolicy.CONSTANT_FIRST),
        budget=CallBudget(100),
        **kwargs,
    )
    assert {row["cache_scope"] for row in first["rows"]} == {str(CacheScope.FRESH)}
    assert all(row["cache_hit"] is False for row in first["rows"])

    resumed_budget = CallBudget(0)
    second = run_mechanism(
        items,
        genomes,
        solver=StubSolver(policy=StubSolverPolicy.CONSTANT_FIRST),
        budget=resumed_budget,
        **kwargs,
    )
    assert {row["cache_scope"] for row in second["rows"]} == {str(CacheScope.SAME_CONDITION_REUSE)}
    assert resumed_budget.spent == 0, "resumption must not spend budget"
    assert [row["status"] for row in first["rows"]] == [row["status"] for row in second["rows"]]


# --------------------------------------------------------------- 2. information parity


def test_all_eight_founders_agree_on_content_and_differ_in_bytes() -> None:
    item = _items(1, (0,))[0]
    report = harness.assert_arena_parity(item, founder_genomes())
    assert len(set(report.prompt_hashes.values())) == len(SEED_GENOME_BY_ID) == 8
    assert report.checks["v4_cross_check"] == "APPLIED"
    assert set(report.checks.values()) <= {"PASS", "APPLIED"}


def test_parity_refuses_byte_identical_arms() -> None:
    """Route B's five 'representations' ignored the genome.  Identical bytes must refuse."""

    surface = SEED_GENOME_BY_ID["L3_JSON_AST"]
    twins = [
        ModelViewGenome(name, (), SearchTrack.EQUAL_INFORMATION, surface, ContentGenome())
        for name in ("TWIN_A", "TWIN_B")
    ]
    with pytest.raises(ParityViolation, match="byte-identical"):
        harness.assert_arena_parity(_items(1, (0,))[0], twins)


def test_parity_refuses_when_an_arm_shows_different_information(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake(language: Any, state: Any) -> str:
        calls["n"] += 1
        return f"surface-{calls['n']}"

    monkeypatch.setattr(harness, "prompt_information_inventory", fake)
    with pytest.raises(ParityViolation, match="different information on the page"):
        harness.assert_arena_parity(
            _items(1, (0,))[0],
            [founder_genome("L3_JSON_AST"), founder_genome("L1_CURRENT_HML")],
        )


def test_parity_refuses_when_an_arm_recovers_different_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ModelViewCompiler.recover_canonical_state

    def tampered(self: ModelViewCompiler, compiled: Any) -> Any:
        state = original(self, compiled)
        if self.genome.candidate_id.endswith("L1_CURRENT_HML"):
            return dataclasses.replace(state, local_scope=("scope:tampered",))
        return state

    monkeypatch.setattr(ModelViewCompiler, "recover_canonical_state", tampered)
    with pytest.raises(ParityViolation):
        harness.assert_arena_parity(
            _items(1, (0,))[0],
            [founder_genome("L3_JSON_AST"), founder_genome("L1_CURRENT_HML")],
        )


def test_parity_refuses_a_content_projection_candidate() -> None:
    game_p = ModelViewGenome(
        "GAME_P",
        (),
        SearchTrack.CONTENT_PROJECTION,
        SEED_GENOME_BY_ID["L3_JSON_AST"],
        ContentGenome(),
    )
    with pytest.raises(ValueError, match="not a Game-R"):
        harness.assert_arena_parity(_items(1, (0,))[0], [founder_genome("L1_CURRENT_HML"), game_p])


def test_option_order_is_part_of_parity() -> None:
    """OPTION_B must mean the same proposal for every arm; a permutation changes the hash."""

    item = _items(1, (0,))[0]
    rotated = rotate_options(item)
    language = harness.GenomePhenotypeLanguage(SEED_GENOME_BY_ID["L3_JSON_AST"])
    assert harness.rendered_option_inventory(
        language, item.options
    ) != harness.rendered_option_inventory(language, rotated.options)


def test_envelope_and_answer_protocol_are_identical_across_arms() -> None:
    item = _items(1, (0,))[0]
    signatures = {envelope_signature(item) for _ in founder_genomes()}
    assert len(signatures) == 1
    report = harness.assert_arena_parity(item, founder_genomes())
    assert report.envelope_signature in signatures
    assert report.checks["envelope_identical"] == "PASS"


# -------------------------------------------------------------- 3. answer-protocol neutrality


def test_canonical_answer_ids_depend_only_on_the_option_count() -> None:
    assert canonical_answer_ids(2) == ("OPTION_A", "OPTION_B")
    assert canonical_answer_ids(4)[-1] == "OPTION_D"
    for surface in SEED_GENOME_BY_ID:
        assert all(surface not in identifier for identifier in canonical_answer_ids(2))


def test_answer_protocol_is_byte_identical_across_arms() -> None:
    item = _items(1, (0,))[0]
    header_blocks = set()
    for genome in founder_genomes():
        prompt = build_prompt(genome, item)
        header_blocks.add(prompt.split("QUESTION:", 1)[0])
        labels = [
            line.split(":", 1)[0]
            for line in prompt.split("OPTIONS:\n", 1)[1].splitlines()
            if line.startswith("OPTION_")
        ]
        assert labels == list(canonical_answer_ids(len(item.options)))
    assert len(header_blocks) == 1, "the response protocol must not vary by arm"


def test_response_schema_is_a_closed_enum_over_the_canonical_ids() -> None:
    schema = response_schema(3)
    assert schema["properties"][ANSWER_KEY]["enum"] == list(canonical_answer_ids(3))
    assert schema["additionalProperties"] is False
    assert schema["required"] == [ANSWER_KEY]


def test_unparseable_and_out_of_enum_answers_are_none_not_guesses() -> None:
    assert parse_answer('{"answer":"OPTION_B"}', 2) == 1
    assert parse_answer("OPTION_B", 2) is None
    assert parse_answer('{"answer":"OPTION_C"}', 2) is None
    assert parse_answer('{"answer":"OPTION_A","why":"x"}', 2) is None
    assert parse_answer("", 2) is None


def test_the_syntax_guide_is_never_arm_specific() -> None:
    """``acquisition_guide`` names the arm's own gene values, so it is never used here."""

    assert "acquisition_guide" not in MODULE_CODE, "a per-arm guide must never be rendered"
    item = _items(1, (0,))[0]
    for policy in (SyntaxGuidePolicy.OMITTED, SyntaxGuidePolicy.SHARED_CONSTANT):
        guides = {
            build_prompt(genome, item, guide_policy=policy).split("QUESTION:", 1)[0]
            for genome in founder_genomes()
        }
        assert len(guides) == 1


# ----------------------------------------------------------------- 4. derived gate target


def test_no_frontier_target_constant_exists_to_drift() -> None:
    assert not hasattr(harness, "FRONTIER_TARGET")
    assert "frontier_target" not in GATE_CONSTANTS
    assert "0.625" not in MODULE_CODE, "the stranded V5 constant must not exist in code"


def test_destroyed_control_is_a_constant_not_a_measurement() -> None:
    assert destroyed_control_accuracy(2) == 0.5
    assert destroyed_control_accuracy(4) == 0.25
    with pytest.raises(ValueError):
        destroyed_control_accuracy(1)


def test_frontier_target_is_derived_from_the_gate_arithmetic() -> None:
    floor = effective_frontier_floor(gap_min=0.20, n_options=2)
    target = derived_frontier_target(gap_min=0.20, band_high=0.85, n_options=2)
    assert floor == pytest.approx(0.70)
    assert target == pytest.approx(0.775)
    assert target == pytest.approx((0.20 + 0.5 + 0.85) / 2)
    assert floor < target < 0.85


def test_the_v5_defect_cannot_recur_the_target_moves_with_the_gate() -> None:
    """V5 raised ``gap_min`` 0.10 -> 0.20 and left a hand-written 0.625 below its own floor."""

    stranded = 0.5 + 0.125  # V5's declared constant, reconstructed here rather than imported
    assert stranded < effective_frontier_floor(gap_min=0.20, n_options=2)
    loose = derived_frontier_target(gap_min=0.10, band_high=0.85, n_options=2)
    tight = derived_frontier_target(gap_min=0.20, band_high=0.85, n_options=2)
    assert loose == pytest.approx(0.725) and tight == pytest.approx(0.775)
    assert loose != tight, "the target must move when the gate moves"
    for n_options in (2, 3, 4, 5):
        for gap_min in (0.05, 0.10, 0.20, 0.30):
            floor = effective_frontier_floor(gap_min=gap_min, n_options=n_options)
            if floor >= 0.85:
                continue
            assert floor < derived_frontier_target(
                gap_min=gap_min, band_high=0.85, n_options=n_options
            )


def test_gate_arithmetic_drops_the_dead_destroyed_gate() -> None:
    arithmetic = gate_arithmetic(n_options=2)
    assert arithmetic["dead_gates_dropped"] == ["destroyed_accuracy_max"]
    assert arithmetic["effective_window"] == [pytest.approx(0.70), 0.85]


def test_selector_aims_at_the_derived_target_not_the_stranded_constant() -> None:
    ladder = {0: 1.0, 1: 0.60, 2: 0.78, 3: 0.95}
    selected = select_frontier_level(ladder, n_options=2)
    assert selected["selected_level"] == 2 and selected["verdict"] == "SELECTED"
    # Under a target of 0.625 the selector would have chosen level 1, which the gate floor
    # (0.70) then rejects.  That is exactly the V5 stranding, reproduced by lowering gap_min.
    loosened = select_frontier_level(ladder, n_options=2, gap_min=0.10)
    assert loosened["candidate_level"] == 2


def test_selector_voids_on_a_failed_explicit_positive_arm() -> None:
    verdict = select_frontier_level({0: 0.5, 1: 0.78}, n_options=2)
    assert verdict["verdict"] == "VOID_INSTRUMENT_LIMIT" and verdict["selected_level"] is None


# ------------------------------------------------------------------ 5. token accounting


def test_budget_decision_follows_tokens_not_characters(tmp_path: Path) -> None:
    """V3 truncated inputs; V4 voided rows on a chars/token constant.  Neither can recur."""

    item, genome = _items(1, (0,))[0], founder_genome("L3_JSON_AST")
    config = _config(tmp_path)
    common: dict[str, Any] = {
        "mechanism": "m",
        "environment_version": "env-v1",
        "config": config,
        "cache": ResponseCache(config.cache_root),
    }
    solver = StubSolver(policy=StubSolverPolicy.ORACLE)
    long_prompt = build_prompt(genome, item)
    assert len(long_prompt) > 1000

    accepted = run_item(
        item,
        genome,
        solver=solver,
        counter=FixedTokenCounter(tokens=1),
        budget=CallBudget(10),
        **common,
    )
    assert accepted["status"] != str(RowStatus.PROMPT_OVER_BUDGET)
    assert accepted["prompt_tokens_counted"] == 1

    refusing_budget = CallBudget(10)
    refused = run_item(
        item,
        genome,
        solver=solver,
        counter=FixedTokenCounter(tokens=10**6),
        budget=refusing_budget,
        **common,
    )
    assert refused["status"] == str(RowStatus.PROMPT_OVER_BUDGET)
    assert refusing_budget.spent == 0, "an over-budget prompt must never be sent"
    assert refused["raw_output"] == "" and refused["valid"] is False


def test_no_character_heuristic_appears_in_the_module() -> None:
    for forbidden in ("chars_per_token", "chars_per_token_floor", "2.74", "7.43"):
        assert forbidden not in MODULE_CODE, forbidden
    assert "len ( prompt )" not in MODULE_CODE, "prompt length must never drive a decision"
    assert "count_tokens" in MODULE_CODE


def test_an_inexact_token_counter_refuses_to_send_anything(tmp_path: Path) -> None:
    class Inexact:
        tokenizer_id = "guess"
        exact = False

        def count_tokens(self, text: str) -> int:
            return len(text) // 4

    config = _config(tmp_path)
    with pytest.raises(TokenAccountingRefusal):
        run_item(
            _items(1, (0,))[0],
            founder_genome("L3_JSON_AST"),
            mechanism="m",
            environment_version="env-v1",
            config=config,
            solver=StubSolver(),
            counter=Inexact(),
            budget=CallBudget(10),
            cache=ResponseCache(config.cache_root),
        )


def test_reported_token_count_disagreement_voids_the_mechanism(tmp_path: Path) -> None:
    items, genomes = _items(12, (0, 1)), [founder_genome("L3_JSON_AST")]
    config = _config(tmp_path)
    run = run_mechanism(
        items,
        genomes,
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=StubSolver(policy=StubSolverPolicy.ORACLE),
        counter=FixedTokenCounter(tokens=7),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(
        [r for r in run["rows"] if r["candidate_id"] == genomes[0].candidate_id]
    )
    assert score["token_mismatch_rows"] > 0
    assert gate_mechanism(score)["checks"]["token_accounting"] == "VOID_TOKEN_ACCOUNTING"


# ------------------------------------------------------------------------- 6. budget


def test_the_runner_refuses_to_exceed_its_budget(tmp_path: Path) -> None:
    config = _config(tmp_path)
    budget = CallBudget(3)
    with pytest.raises(BudgetExceeded):
        run_mechanism(
            _items(3, (0, 1)),
            founder_genomes(),
            mechanism="m",
            environment_version="env-v1",
            config=config,
            solver=StubSolver(),
            counter=StubTokenCounter(),
            budget=budget,
            cache=ResponseCache(config.cache_root),
        )
    assert budget.spent == 3 and budget.remaining == 0


def test_budget_refusal_preserves_completed_rows_for_resumption(tmp_path: Path) -> None:
    config = _config(tmp_path)
    common: dict[str, Any] = {
        "mechanism": "m",
        "environment_version": "env-v1",
        "config": config,
        "counter": StubTokenCounter(),
        "cache": ResponseCache(config.cache_root),
    }
    items, genomes = _items(2, (0,)), [founder_genome("L3_JSON_AST")]
    with pytest.raises(BudgetExceeded):
        run_mechanism(items, genomes, solver=StubSolver(), budget=CallBudget(2), **common)
    resumed = CallBudget(2)
    run = run_mechanism(items, genomes, solver=StubSolver(), budget=resumed, **common)
    assert sum(row["cache_hit"] for row in run["rows"]) == 2
    assert resumed.spent == 2


# -------------------------------------------------------------------- 7. fail-closed scoring


def test_an_unparseable_response_is_wrong_and_never_skipped(tmp_path: Path) -> None:
    config = _config(tmp_path)
    run = run_mechanism(
        _items(12, (0, 1)),
        [founder_genome("L3_JSON_AST")],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=StubSolver(policy=StubSolverPolicy.UNPARSEABLE),
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(run["rows"])
    assert score["rows_scored"] == score["rows_total"], "invalid rows stay in the denominator"
    assert score["schema_error_rows"] == score["rows_total"]
    assert score["valid_response_rate"] == 0.0
    assert all(accuracy == 0.0 for accuracy in score["accuracy_by_level"].values())
    assert gate_mechanism(score)["checks"]["valid_response"] == "VOID_VALIDITY"


def test_a_transport_failure_voids_rather_than_scores(tmp_path: Path) -> None:
    config = _config(tmp_path)
    run = run_mechanism(
        _items(12, (0, 1)),
        [founder_genome("L3_JSON_AST")],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=StubSolver(policy=StubSolverPolicy.TRANSPORT_ERROR),
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(run["rows"])
    assert score["solver_error_rows"] == score["rows_total"]
    assert gate_mechanism(score)["checks"]["transport"] == "VOID_TRANSPORT"


def test_a_constant_answerer_is_caught_by_answer_share(tmp_path: Path) -> None:
    """The choice-flip gate passes a coin-flipper 65.6% of the time; this one does not."""

    config = _config(tmp_path)
    run = run_mechanism(
        _items(12, (0, 1)),
        [founder_genome("L3_JSON_AST")],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=StubSolver(policy=StubSolverPolicy.CONSTANT_FIRST),
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(run["rows"])
    assert score["largest_answer_share"] == 1.0
    assert gate_mechanism(score)["checks"]["answer_share"] == "VOID_ANSWER_SHARE"
    assert score["position_invariance"] == 0.0, "a position-locked solver is not invariant"
    assert gate_mechanism(score)["checks"]["position_invariance"] == "VOID_POSITION"


def test_an_oracle_is_position_invariant(tmp_path: Path) -> None:
    config = _config(tmp_path)
    items = _items(12, (0, 1))
    genome = founder_genome("L3_JSON_AST")
    solver = StubSolver(policy=StubSolverPolicy.ORACLE)
    for item in items:
        solver.prime(build_prompt(genome, item), item.correct_index)
    run = run_mechanism(
        items,
        [genome],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=solver,
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(run["rows"])
    assert score["position_invariance"] == 1.0
    assert score["valid_response_rate"] == 1.0
    assert all(accuracy == 1.0 for accuracy in score["accuracy_by_level"].values())


def test_scoring_is_never_pooled_across_mechanisms(tmp_path: Path) -> None:
    config = _config(tmp_path)
    rows = []
    for mechanism in ("m1", "m2"):
        run = run_mechanism(
            _items(1, (0,)),
            [founder_genome("L3_JSON_AST")],
            mechanism=mechanism,
            environment_version="env-v1",
            config=config,
            solver=StubSolver(),
            counter=StubTokenCounter(),
            budget=CallBudget(100),
            cache=ResponseCache(config.cache_root),
        )
        rows.extend(run["rows"])
    with pytest.raises(HarnessRefusal, match="never pooled"):
        score_mechanism(rows)


def test_paired_comparison_fails_closed_on_an_empty_common_set() -> None:
    assert harness.compare_arms([], [])["status"] == "NO_COMMON_SET"


def test_paired_comparison_reuses_mcnemar_and_the_clustered_bootstrap(tmp_path: Path) -> None:
    config = _config(tmp_path)
    items = _items(12, (0, 1))
    left, right = founder_genome("L3_JSON_AST"), founder_genome("L1_CURRENT_HML")
    oracle = StubSolver(policy=StubSolverPolicy.ORACLE)
    for item in items:
        oracle.prime(build_prompt(left, item), item.correct_index)
    run = run_mechanism(
        items,
        [left, right],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=oracle,
        counter=StubTokenCounter(),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    rows_left = [r for r in run["rows"] if r["candidate_id"] == left.candidate_id]
    rows_right = [r for r in run["rows"] if r["candidate_id"] == right.candidate_id]
    comparison = harness.compare_arms(rows_left, rows_right)
    assert comparison["status"] == "COMPARED"
    assert comparison["n"] == len(items)
    assert comparison["clusters"] == len({item.family_id for item in items})
    assert comparison["mcnemar_exact_p"] == comparison["mcnemar_exact_p_recomputed"]
    assert comparison["accuracy_a"] == 1.0


def test_destroyed_determinism_check_detects_a_nondeterministic_solver() -> None:
    rows: list[Mapping[str, Any]] = [
        {"prompt_hash": "p1", "raw_output": "a"},
        {"prompt_hash": "p1", "raw_output": "a"},
        {"prompt_hash": "p2", "raw_output": "a"},
    ]
    assert verify_destroyed_determinism(rows)["deterministic"] is True
    rows.append({"prompt_hash": "p2", "raw_output": "b"})
    report = verify_destroyed_determinism(rows)
    assert report["deterministic"] is False and report["nondeterministic_prompt_hashes"] == ["p2"]


# ------------------------------------------------------------------- 8. dry run, determinism


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        (StubSolverPolicy.CONSTANT_FIRST, RowStatus.MODEL_SEMANTIC_ERROR),
        (StubSolverPolicy.UNPARSEABLE, RowStatus.RESPONSE_SCHEMA_ERROR),
        (StubSolverPolicy.OUTPUT_TRUNCATED, RowStatus.OUTPUT_TRUNCATION),
        (StubSolverPolicy.TRANSPORT_ERROR, RowStatus.SOLVER_ERROR),
        (StubSolverPolicy.DETERMINISTIC_MIX, RowStatus.CORRECT),
    ],
)
def test_dry_run_exercises_every_status_path(
    tmp_path: Path, policy: StubSolverPolicy, expected: RowStatus
) -> None:
    report = dry_run(root=tmp_path / str(policy), families=4, levels=(0, 1), policy=policy)
    statuses = {row["status"] for data in report["mechanisms"].values() for row in data["rows"]}
    assert str(expected) in statuses


def test_dry_run_is_end_to_end_and_deterministic(tmp_path: Path) -> None:
    first = dry_run(root=tmp_path / "a", families=4, levels=(0, 1, 2, 3))
    second = dry_run(root=tmp_path / "b", families=4, levels=(0, 1, 2, 3))

    def scrub(report: dict[str, Any]) -> str:
        return stable_hash(
            {
                mechanism: {
                    "rows": [
                        {k: v for k, v in row.items() if k not in {"cache_hit", "cache_scope"}}
                        for row in data["rows"]
                    ],
                    "scores": {
                        candidate: {
                            k: v
                            for k, v in score.items()
                            if k not in {"cache_hits", "cache_scopes"}
                        }
                        for candidate, score in data["scores"].items()
                    },
                    "gates": data["gates"],
                    "parity": data["parity"],
                }
                for mechanism, data in report["mechanisms"].items()
            }
        )

    assert scrub(first) == scrub(second)
    assert first["budget"]["spent"] == second["budget"]["spent"] > 0
    assert first["gate_arithmetic"]["frontier_target"] == pytest.approx(0.775)
    assert first["mechanisms"]["stub_mechanism"]["distinct_envelope_signatures"]
    assert len(first["mechanisms"]["stub_mechanism"]["distinct_answer_protocols"]) == 1


def test_prompts_are_a_pure_function_of_arm_and_item() -> None:
    item, genome = _items(1, (0,))[0], founder_genome("L2_SEXPR")
    assert prompt_bytes_hash(build_prompt(genome, item)) == prompt_bytes_hash(
        build_prompt(genome, item)
    )


def test_cli_refuses_to_run_live_without_explicit_confirmation() -> None:
    with pytest.raises(SystemExit):
        harness.main(["--live"])
    with pytest.raises(SystemExit):
        harness.main([])


def test_rotate_options_preserves_content_and_moves_truth() -> None:
    item = _items(1, (0,))[0]
    rotated = rotate_options(item)
    assert rotated.variant == str(ItemVariant.ORDER_ROTATED)
    assert set(rotated.options) == set(item.options)
    assert rotated.options[rotated.correct_index] == item.options[item.correct_index]
    assert rotated.canonical_state is item.canonical_state
    with pytest.raises(ValueError):
        rotate_options(item, shift=len(item.options))


def test_a_single_arm_run_cannot_masquerade_as_parity_verified() -> None:
    report = harness.assert_arena_parity(_items(1, (0,))[0], [founder_genome("L3_JSON_AST")])
    assert report.checks["rendered_bytes_distinct"] == "NOT_APPLICABLE_SINGLE_ARM"
    assert report.checks["surface_information_identical"] == "NOT_APPLICABLE_SINGLE_ARM"
    assert report.checks["game_r_genome"] == "PASS"


def test_no_row_anywhere_can_carry_a_cross_condition_scope(tmp_path: Path) -> None:
    report = dry_run(root=tmp_path, families=3, levels=(0, 1))
    scopes = {row["cache_scope"] for data in report["mechanisms"].values() for row in data["rows"]}
    assert scopes == {str(CacheScope.FRESH)}
    resumed = dry_run(root=tmp_path, families=3, levels=(0, 1), budget_max=0)
    resumed_scopes = {
        row["cache_scope"] for data in resumed["mechanisms"].values() for row in data["rows"]
    }
    assert resumed_scopes == {str(CacheScope.SAME_CONDITION_REUSE)}
    assert str(CacheScope.CROSS_CONDITION) not in scopes | resumed_scopes
    assert resumed["budget"]["spent"] == 0


def test_over_budget_prompts_void_the_mechanism_instead_of_being_dropped(tmp_path: Path) -> None:
    config = _config(tmp_path)
    solver = StubSolver()
    run = run_mechanism(
        _items(12, (0, 1)),
        [founder_genome("L3_JSON_AST")],
        mechanism="m",
        environment_version="env-v1",
        config=config,
        solver=solver,
        counter=FixedTokenCounter(tokens=10**6),
        budget=CallBudget(1000),
        cache=ResponseCache(config.cache_root),
    )
    score = score_mechanism(run["rows"])
    assert solver.calls == 0, "no over-budget prompt may be sent"
    assert score["over_budget_rows"] == score["rows_total"] > 0
    assert score["rows_scored"] == 0
    assert gate_mechanism(score)["checks"]["context"] == "VOID_CONTEXT"
    assert gate_mechanism(score)["qualified"] is False
