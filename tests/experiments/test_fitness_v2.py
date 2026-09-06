from __future__ import annotations

import json
from pathlib import Path

import pytest

from arena.experiments.fitness_v2 import (
    ProbeSlice,
    ProbeVariant,
    ResponseProtocol,
    TruthKind,
    build_probe_manifest,
    build_probe_prompt,
    derive_probe_family,
    experiment_status_v2,
    parse_response,
    probes_for_slice,
    run_tier2a,
    summarize_probe_rows,
    validate_probe_family,
)
from arena.genome.seeds import L0_STRUCTURED_ENGLISH
from arena.tasks.generators.world_v0 import build_world_v0


def test_probe_manifest_is_deterministic_source_disjoint_and_validated() -> None:
    first = build_probe_manifest()
    second = build_probe_manifest()
    assert first == second
    assert (
        first["manifest_hash"] == "08ce4d637dc1049d827545922e72c92ae36939d3bdf1a178a13d44ff9974847a"
    )
    assert len(first["probes"]) == 288
    assert len(first["validations"]) == 48
    sources = [task_id for values in first["slice_sources"].values() for task_id in values]
    assert len(sources) == len(set(sources))
    assert all(
        all(value for key, value in row.items() if key.endswith("_valid"))
        for row in first["validations"]
    )


def test_each_family_has_exact_balance_and_information_destroyed_twins() -> None:
    task = next(
        task
        for task in build_world_v0().tasks
        if task.dimensions.domain == "sets" and task.trajectory.quality.value == "GOLD"
    )
    family = derive_probe_family(task, ProbeSlice.PROTOCOL_DEV)
    assert validate_probe_family(family)["oracle_inversion_valid"] is True
    by_variant = {probe.variant: probe for probe in family}
    positives = [
        by_variant[ProbeVariant.ORIGINAL],
        by_variant[ProbeVariant.COUNTERFACTUAL],
    ]
    assert [probe.expected_index for probe in positives] == [0, 1]
    negatives = [
        by_variant[ProbeVariant.DESTROYED_ORIGINAL],
        by_variant[ProbeVariant.DESTROYED_COUNTERFACTUAL],
    ]
    assert negatives[0].state.to_dict() == negatives[1].state.to_dict()
    assert [probe.expected_index for probe in negatives] == [0, 1]
    assert all(probe.truth_kind == TruthKind.NEGATIVE_CONTROL_TARGET for probe in negatives)
    assert not negatives[0].state.legal_actions
    assert not negatives[0].state.plausible_invalid_actions


def test_all_supported_mechanisms_pass_independent_family_validation() -> None:
    seen = set()
    for probe in probes_for_slice(ProbeSlice.TIER2B_PROMOTION):
        if probe.pair_id in seen:
            continue
        seen.add(probe.pair_id)
        family = tuple(
            item
            for item in probes_for_slice(ProbeSlice.TIER2B_PROMOTION)
            if item.pair_id == probe.pair_id
        )
        assert validate_probe_family(family)["unique_positive_answer"] is True
    assert len(seen) == 16


def test_prompt_has_common_envelope_and_no_oracle_action_labels() -> None:
    probe = probes_for_slice(ProbeSlice.PROTOCOL_DEV)[0]
    prompt = build_probe_prompt(L0_STRUCTURED_ENGLISH, probe, ResponseProtocol.JSON_AB)
    assert "Read the mathematical state" in prompt
    assert "SYNTAX GUIDE:" in prompt
    assert "STATE:" in prompt
    assert "OPTIONS:" in prompt
    assert "expected_usefulness" not in prompt
    assert "plausible distractor" not in prompt
    assert "invalid_" not in prompt
    assert probe.source_task_id not in prompt
    assert probe.pair_id not in prompt


def test_protocol_parsers_are_strict_and_semantically_decode_options() -> None:
    probe = probes_for_slice(ProbeSlice.PROTOCOL_DEV)[0]
    cases = {
        ResponseProtocol.JSON_AB: '{"choice":"A"}',
        ResponseProtocol.JSON_PQ: '{"choice":"P"}',
        ResponseProtocol.CANONICAL_ANSWER: "integer:17",
    }
    for protocol in (ResponseProtocol.JSON_AB, ResponseProtocol.JSON_PQ):
        index, semantic_hash = parse_response(cases[protocol], protocol, probe)
        assert index == 0
        assert semantic_hash == probe.options[0].content_hash
        assert parse_response("A", protocol, probe) == (None, None)
        assert parse_response(json.dumps({"choice": "A", "why": "x"}), protocol, probe) == (
            None,
            None,
        )


def test_metrics_reject_constant_policy_and_reward_semantic_reader() -> None:
    probes = probes_for_slice(ProbeSlice.PROTOCOL_DEV)

    def rows(mode: str) -> list[dict[str, object]]:
        result = []
        for probe in probes:
            selected_index = probe.expected_index if mode == "oracle" else 0
            result.append(
                {
                    "pair_id": probe.pair_id,
                    "variant": probe.variant.value,
                    "truth_kind": probe.truth_kind.value,
                    "expected_index": probe.expected_index,
                    "parsed_index": selected_index,
                    "selected_semantic_hash": probe.options[selected_index].content_hash,
                    "correct": selected_index == probe.expected_index,
                }
            )
        return result

    constant = summarize_probe_rows(rows("constant"), q0_valid_rate=1.0)
    assert constant["q1_positive_accuracy"] == 0.5
    assert constant["semantic_flip_consistency"] == 0.0
    assert constant["qualified"] is False

    oracle = summarize_probe_rows(rows("oracle"), q0_valid_rate=1.0)
    assert oracle["q1_positive_accuracy"] == 1.0
    assert oracle["semantic_flip_consistency"] == 1.0
    # Negative siblings have incompatible targets but a synthetic oracle row follows those
    # targets.  Qualification's Q1-Q2 test correctly rejects that non-natural construction.
    assert oracle["qualified"] is False


def test_status_preserves_instrument_qualification_when_headroom_blocks_tier2(
    tmp_path: Path,
) -> None:
    calibration = tmp_path / "artifacts/experiments/fitness_v2/calibration/result.json"
    calibration.parent.mkdir(parents=True)
    calibration.write_text(
        json.dumps(
            {
                "instrument_valid": True,
                "tier2a_authorized": False,
                "verdict": "FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM",
            }
        )
    )
    status = experiment_status_v2(tmp_path)
    assert status["sentinel"] == "FITNESS_V2_INSTRUMENT_QUALIFIED"
    assert status["next_action"] == "redesign DEV calibration"
    with pytest.raises(RuntimeError, match="not authorized"):
        run_tier2a(tmp_path)
