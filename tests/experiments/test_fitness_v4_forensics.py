from __future__ import annotations

from arena.experiments.fitness_v4_forensics import diagnose


def _row(**overrides):
    base = {
        "raw_output": '{"choice":"A"}',
        "context_status": "OK",
        "parsed_index": 0,
        "correct": True,
        "truth_kind": "MATHEMATICAL",
        "completion_tokens": 6,
    }
    return {**base, **overrides}


def test_diagnostic_causes_are_separate_from_void_codes() -> None:
    assert diagnose(_row()) == "CORRECT"
    assert diagnose(_row(correct=False)) == "SEMANTIC_ERROR"
    assert diagnose(_row(truth_kind="NEGATIVE_CONTROL_TARGET")) == "NEGATIVE_CONTROL_RESPONSE"
    assert (
        diagnose(
            _row(
                parsed_index=None, raw_output="To find the dependency, step 1", completion_tokens=64
            )
        )
        == "REASONING_EXCEEDS_COMPLETION_BUDGET"
    )
    assert (
        diagnose(_row(parsed_index=None, raw_output="A", completion_tokens=2))
        == "FORMAT_NONCOMPLIANCE"
    )
    assert diagnose(_row(parsed_index=None, context_status="TRUNCATED")) == "CONTEXT_TRUNCATION"
    assert diagnose(_row(parsed_index=None, context_status="OVER_BUDGET")) == "OVER_BUDGET_UNSENT"
