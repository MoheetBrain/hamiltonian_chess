from __future__ import annotations

import json

from arena.canonical.schema import stable_hash
from arena.experiments.fitness_v3 import (
    MECHANISMS,
    V3Slice,
    V3Variant,
    _cached_call,
    build_pool,
    build_prompt,
    derive_probe_family,
    equal_information_genome,
    exact_sign_pvalue,
    founder_genomes,
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


def test_founder_roster_is_broad_and_content_children_are_one_gene_mutations() -> None:
    founders = founder_genomes()
    assert len(founders) == 12
    assert sum(founder.track.value.startswith("TRACK_E") for founder in founders) == 8
    base = next(founder for founder in founders if founder.candidate_id == "V3C_JSON_BASE")
    children = [founder for founder in founders if founder.parent_ids == (base.candidate_id,)]
    assert len(children) == 3
    for child in children:
        changes = {
            name
            for name, value in child.content.to_dict().items()
            if value != base.content.to_dict()[name]
        }
        assert len(changes) == 1


def test_v3_cache_resume_unwraps_and_validates_record(tmp_path) -> None:
    identity = {"probe": "p1", "prompt_hash": "h1"}
    path = tmp_path / "artifacts/cache/fitness_v3" / f"{stable_hash(identity)}.json"
    path.parent.mkdir(parents=True)
    result = {"response": '{"choice":"A"}', "prompt_eval_count": 1}
    path.write_text(json.dumps({"identity": identity, "result": result}))
    observed, hit = _cached_call(tmp_path, identity, "unused")
    assert hit
    assert observed == result
