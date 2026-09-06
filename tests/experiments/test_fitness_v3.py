from __future__ import annotations

from arena.experiments.fitness_v3 import (
    MECHANISMS,
    V3Slice,
    V3Variant,
    build_pool,
    build_prompt,
    derive_probe_family,
    equal_information_genome,
    exact_sign_pvalue,
    parse_response,
    validate_probe_family,
)


def test_v3_pool_covers_every_content_mechanism_and_control_variant() -> None:
    probes = build_pool(V3Slice.DEV)
    assert {probe.mechanism for probe in probes} == set(MECHANISMS)
    assert {probe.complexity for probe in probes} == {1, 2}
    assert {probe.variant for probe in probes} == set(V3Variant)
    assert len(probes) == len(MECHANISMS) * 2 * 6


def test_v3_family_is_balanced_valid_and_position_invariant() -> None:
    family = derive_probe_family("dependency_chain", 2, V3Slice.DEV, 17)
    assert validate_probe_family(family)["valid"]
    by_variant = {probe.variant: probe for probe in family}
    assert (
        by_variant[V3Variant.DESTROYED_ORIGINAL].state.mathematical_hash
        == by_variant[V3Variant.DESTROYED_COUNTERFACTUAL].state.mathematical_hash
    )
    assert by_variant[V3Variant.DESTROYED_ORIGINAL].expected_index == 0
    assert by_variant[V3Variant.DESTROYED_COUNTERFACTUAL].expected_index == 1


def test_v3_prompt_has_no_correctness_or_usefulness_label() -> None:
    probe = derive_probe_family("premise_attribution", 1, V3Slice.DEV, 19)[0]
    prompt = build_prompt(equal_information_genome(), probe)
    assert "expected_usefulness" not in prompt
    assert '"choice":"A"' in prompt
    assert "answer:19:left" in prompt
    assert "expected_index" not in prompt


def test_v3_response_parser_is_fail_closed() -> None:
    assert parse_response('{"choice":"A"}') == 0
    assert parse_response('{"choice":"B"}') == 1
    assert parse_response("A") is None
    assert parse_response('{"choice":"A","explanation":"x"}') is None


def test_exact_sign_test_rule() -> None:
    assert exact_sign_pvalue(5, 0) == 0.03125
    assert exact_sign_pvalue(4, 1) > 0.05
    assert exact_sign_pvalue(0, 0) == 1.0
