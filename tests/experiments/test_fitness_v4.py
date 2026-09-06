from __future__ import annotations

import json

import pytest

from arena.canonical.schema import stable_hash
from arena.experiments.fitness_v4 import (
    CONTEXT_GUARD,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    RUNTIME_CONFIG,
    RUNTIME_CONFIG_HASH,
    V4Slice,
    V4Variant,
    _cached_call,
    added_facts,
    ancestors,
    assert_game_r_genome,
    assert_information_parity,
    build_dev_pool,
    build_prompt,
    context_status,
    derive_probe_family,
    equal_information_genome,
    expression_depths,
    founder_genomes,
    holm_decisions,
    paired_against,
    parse_response,
    qualify_mechanism,
    resolve_site,
    satisfied_options,
    select_frontier_level,
    shortcut_audit,
    summarize,
    validate_probe_family,
)
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack


def _family(mechanism: str, level: int, salt: int = 41):
    return derive_probe_family(mechanism, level, V4Slice.DEV, salt)


@pytest.mark.parametrize("mechanism", MECHANISMS)
@pytest.mark.parametrize("level", range(5))
def test_every_ladder_cell_builds_a_valid_balanced_family(mechanism: str, level: int) -> None:
    family = _family(mechanism, level)
    assert validate_probe_family(family)["valid"]
    assert len({probe.probe_id for probe in family}) == 6
    assert [probe.expected_index for probe in family] == [0, 1, 0, 1, 1, 0]
    assert all(probe.parameters == LADDERS[mechanism][level] for probe in family)


def test_depth_truth_is_rederived_by_walking_the_tree() -> None:
    original, counter, destroyed, *_ = _family("expression_depth_recurrence", 3)
    for probe in (original, counter):
        depths = expression_depths(probe.state.goal)
        maxima = {name: max(values) for name, values in depths.items()}
        answer = str(probe.options[probe.expected_index].arguments[0].value)
        other = str(probe.options[1 - probe.expected_index].arguments[0].value)
        assert maxima[answer] == probe.parameters["depth"]
        assert maxima[other] == probe.parameters["depth"] - 1
        assert all(value < maxima[answer] for name, value in maxima.items() if name != answer)
        assert all(len(values) == probe.parameters["recurrence"] for values in depths.values())
    tie = {name: max(values) for name, values in expression_depths(destroyed.state.goal).items()}
    names = [str(option.arguments[0].value) for option in destroyed.options]
    assert tie[names[0]] == tie[names[1]]


def test_transitive_dependency_truth_uses_independent_closure() -> None:
    original, counter, destroyed, *_ = _family("transitive_dependency", 3)
    for probe in (original, counter):
        answer = str(probe.options[probe.expected_index].arguments[0].value)
        other = str(probe.options[1 - probe.expected_index].arguments[0].value)
        closure = ancestors(probe.state.evidence_dependencies, "e:leaf")
        assert answer in closure and other not in closure
    assert not ancestors(destroyed.state.evidence_dependencies, "e:leaf")
    ids = [node.evidence_id for node in original.state.evidence_dependencies]
    assert ids != sorted(ids), "evidence order must not reveal chain membership"


def test_binder_scope_truth_is_lexical_and_destroyed_has_no_site() -> None:
    original, counter, destroyed, *_ = _family("binder_scope_resolution", 3)
    for probe in (original, counter):
        answer = str(probe.options[probe.expected_index].arguments[0].value)
        assert resolve_site(probe.state.goal, "use:query") == answer
    assert resolve_site(destroyed.state.goal, "use:query") is None


def test_precondition_truth_is_subset_check_and_near_miss_is_not_a_premise() -> None:
    original, counter, destroyed, *_ = _family("precondition_conjunction", 3)
    for probe in (original, counter):
        answer = str(probe.options[probe.expected_index].arguments[0].value)
        assert satisfied_options(probe.state) == {answer}
    assert satisfied_options(destroyed.state) == set()
    required = {
        str(item.args[1].value) for item in original.state.propositions if item.op == "requires"
    }
    held = {str(item.args[0].value) for item in original.state.assumptions}
    assert held - required, "a near-miss premise must be held but never required"


def test_state_delta_truth_is_set_difference_and_added_fact_is_not_last() -> None:
    original, counter, destroyed, *_ = _family("state_delta", 2)
    for probe in (original, counter):
        answer = str(probe.options[probe.expected_index].arguments[0].value)
        assert probe.previous_state is not None
        assert added_facts(probe.previous_state, probe.state) == {answer}
        ops = {item.op for item in probe.state.established_facts}
        assert ops == {"holds"}, "the added fact must not be revealed by its operator name"
    assert destroyed.previous_state is not None
    assert added_facts(destroyed.previous_state, destroyed.state) == set()


def test_dev_pool_is_deterministic_and_shortcut_clean() -> None:
    first = build_dev_pool(("transitive_dependency",), (1,), 3)
    second = build_dev_pool(("transitive_dependency",), (1,), 3)
    assert [probe.derived_hash for probe in first] == [probe.derived_hash for probe in second]
    audit = shortcut_audit(build_dev_pool(MECHANISMS, (2,), 6))
    assert audit["status"] == "CLEAN", audit
    assert audit["answer_share_index_0"] == 0.5


def test_prompt_has_no_oracle_label_and_common_envelope() -> None:
    probe = _family("precondition_conjunction", 1)[0]
    prompts = {genome.candidate_id: build_prompt(genome, probe) for genome in founder_genomes()}
    for prompt in prompts.values():
        assert "expected_usefulness" not in prompt
        assert "expected_index" not in prompt
        assert prompt.startswith('Return exactly {"choice":"A"} or {"choice":"B"}')
        assert f"QUESTION: {probe.question}" in prompt
    assert len(set(prompts.values())) == len(prompts)


def test_founders_are_equal_information_track_e_only() -> None:
    founders = founder_genomes()
    assert len(founders) == 8
    for genome in founders:
        assert genome.track == SearchTrack.EQUAL_INFORMATION
        assert genome.content == ContentGenome()
        assert_game_r_genome(genome)
    content = ModelViewGenome(
        "V4C_BAD",
        (),
        SearchTrack.CONTENT_PROJECTION,
        founders[3].surface,
        ContentGenome().with_gene("dependency_projection", "EXPLICIT_EDGE"),
    )
    with pytest.raises(ValueError):
        assert_game_r_genome(content)
    with pytest.raises(ValueError):
        build_prompt(content, _family("state_delta", 0)[0])


def test_information_parity_holds_for_every_founder_on_every_mechanism() -> None:
    for mechanism in MECHANISMS:
        for probe in _family(mechanism, 2):
            hashes = assert_information_parity(probe, founder_genomes())
            assert len(hashes) == 8


def test_context_guard_flags_truncation_signature() -> None:
    limit = CONTEXT_GUARD["prompt_token_limit"]
    assert context_status("x" * 1000, 400) == "OK"
    assert context_status("x" * 1000, None) == "UNSENT"
    assert context_status("x" * 45000, 4099) == "TRUNCATED"
    assert context_status("x" * 1000, limit + 1) == "TRUNCATED"
    assert context_status("x" * (limit * 3), None) == "OVER_BUDGET"
    assert RUNTIME_CONFIG["num_ctx"] == 32768
    assert stable_hash(RUNTIME_CONFIG) == RUNTIME_CONFIG_HASH


def test_cache_identity_and_over_budget_prompt_is_never_sent(tmp_path) -> None:
    identity = {"probe": "p1", "prompt_hash": "h1", "runtime_hash": RUNTIME_CONFIG_HASH}
    path = tmp_path / "artifacts/cache/fitness_v4" / f"{stable_hash(identity)}.json"
    path.parent.mkdir(parents=True)
    result = {"response": '{"choice":"B"}', "prompt_eval_count": 7}
    path.write_text(json.dumps({"identity": identity, "result": result}))
    observed, hit = _cached_call(tmp_path, identity, "unused")
    assert hit and observed == result
    huge, hit = _cached_call(
        tmp_path, {"probe": "p2"}, "y" * (CONTEXT_GUARD["prompt_token_limit"] * 3)
    )
    assert not hit and huge["error"].startswith("OVER_BUDGET")


def test_response_parser_is_fail_closed() -> None:
    assert parse_response('{"choice":"A"}') == 0
    assert parse_response('{"choice":"B"}') == 1
    assert parse_response("A") is None
    assert parse_response('{"choice":"A","why":"x"}') is None


def test_frontier_selection_rule() -> None:
    assert select_frontier_level({0: 1.0, 1: 0.9, 2: 0.6, 3: 0.3, 4: 0.1})["selected_level"] == 2
    assert (
        select_frontier_level({0: 1.0, 1: 1.0, 2: 0.95, 3: 0.9, 4: 0.9})["verdict"]
        == "VOID_CEILING"
    )
    assert (
        select_frontier_level({0: 1.0, 1: 0.2, 2: 0.1, 3: 0.1, 4: 0.0})["verdict"] == "VOID_FLOOR"
    )
    assert select_frontier_level({0: 0.7, 1: 0.6})["verdict"] == "VOID_INSTRUMENT_LIMIT"
    tie = select_frontier_level({0: 1.0, 1: 0.75, 2: 0.5, 3: 0.4})
    assert tie["selected_level"] == 1, "ties on distance go to the lower level"


def _rows(mechanism: str, correct_positive: bool, valid: bool = True):
    rows = []
    for family in ("f1", "f2", "f3", "f4"):
        for variant, expected in (
            ("ORIGINAL", 0),
            ("COUNTERFACTUAL", 1),
            ("DESTROYED_ORIGINAL", 0),
            ("DESTROYED_COUNTERFACTUAL", 1),
            ("SWAPPED_ORIGINAL", 1),
            ("SWAPPED_COUNTERFACTUAL", 0),
        ):
            is_positive = variant in POSITIVE_VARIANTS or variant.startswith("SWAPPED")
            chosen = expected if (correct_positive and is_positive) else 0
            swapped = variant.startswith("SWAPPED")
            chosen_identity = 1 - chosen if swapped else chosen
            expected_identity = 1 - expected if swapped else expected
            rows.append(
                {
                    "family_id": family,
                    "mechanism": mechanism,
                    "variant": variant,
                    "truth_kind": "NEGATIVE_CONTROL_TARGET"
                    if "DESTROYED" in variant
                    else "MATHEMATICAL",
                    "expected_index": expected,
                    "parsed_index": chosen if valid else None,
                    "selected_hash": f"h{chosen_identity}" if valid else None,
                    "expected_hash": f"h{expected_identity}",
                    "correct": valid and chosen == expected,
                    "context_status": "OK",
                    "prompt_tokens": 100,
                    "probe_id": f"{family}:{variant}",
                }
            )
    return rows


def test_summary_and_qualification_void_codes() -> None:
    good = summarize(_rows("m", True))
    assert good["positive_accuracy"] == 1.0
    assert good["negative_target_accuracy"] == 0.5
    assert good["semantic_flip_consistency"] == 1.0
    assert good["position_invariance"] == 1.0
    clean = {"status": "CLEAN"}
    assert qualify_mechanism(good, clean, 1.0)["qualified"]
    assert qualify_mechanism(good, {"status": "LEAKS"}, 1.0)["verdict"] == "VOID_SHORTCUT"
    always_a = summarize(_rows("m", False))
    verdict = qualify_mechanism(always_a, clean, 1.0)
    assert not verdict["qualified"]
    assert verdict["checks"]["negative_collapse"] == "VOID_NEGATIVE_CONTROL"
    assert verdict["checks"]["semantic_flip"] == "VOID_FLIP"
    malformed = summarize(_rows("m", True, valid=False))
    assert qualify_mechanism(malformed, clean, 1.0)["verdict"] == "VOID_VALIDITY"


def test_paired_comparison_and_holm() -> None:
    def result(pattern):
        rows = []
        for index, correct in enumerate(pattern):
            rows.append(
                {
                    "probe_id": f"p{index}",
                    "family_id": f"f{index // 2}",
                    "mechanism": "m",
                    "variant": "ORIGINAL" if index % 2 == 0 else "COUNTERFACTUAL",
                    "correct": correct,
                }
            )
        return {"rows": rows}

    baseline = result([True, False] * 6)
    candidate = result([True, True] * 6)
    common = {f"p{index}" for index in range(12)}
    comparison = paired_against(candidate, baseline, common)
    assert comparison["wins"] == 6 and comparison["losses"] == 0
    assert comparison["exact_sign_pvalue_one_sided"] == pytest.approx(1 / 64)
    assert comparison["paired_delta"] == pytest.approx(0.5)
    assert comparison["paired_delta_ci95"][0] > 0.0
    same = paired_against(baseline, baseline, common)
    assert same["net_wins"] == 0 and same["exact_sign_pvalue_one_sided"] == 1.0
    comparisons = {"x": dict(comparison), "y": dict(same)}
    holm_decisions(comparisons)
    assert comparisons["x"]["holm_reject"] and not comparisons["y"]["holm_reject"]


def test_probe_family_variants_are_position_and_information_consistent() -> None:
    family = _family("binder_scope_resolution", 1)
    by_variant = {probe.variant: probe for probe in family}
    assert (
        by_variant[V4Variant.DESTROYED_ORIGINAL].state.mathematical_hash
        == by_variant[V4Variant.DESTROYED_COUNTERFACTUAL].state.mathematical_hash
    )
    assert by_variant[V4Variant.ORIGINAL].options == tuple(
        reversed(by_variant[V4Variant.SWAPPED_ORIGINAL].options)
    )
    control = equal_information_genome()
    assert build_prompt(control, by_variant[V4Variant.ORIGINAL]) != build_prompt(
        control, by_variant[V4Variant.SWAPPED_ORIGINAL]
    )
