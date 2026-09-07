from pathlib import Path

import pytest

from research.astra.game_r_premise.source_adapter import (
    source_signature, split_state, validate_source_pin,
)


def test_source_header_is_not_truncated_and_rejects_unsafe_let():
    long_type = "theorem long_name (x : Nat) : " + ("x = x ∧ " * 90) + "x = x"
    assert source_signature(long_type).endswith("x = x")
    with pytest.raises(ValueError):
        source_signature("theorem bad : let x := 1; x = x := by rfl")


def test_source_signature_rejects_nested_assignment_and_keeps_balanced_type():
    with pytest.raises(ValueError):
        source_signature("theorem bad (x : Nat := 1) : x = x := by rfl")
    assert source_signature("theorem good (x : Nat) : (x = x) := by rfl").endswith("(x = x) ")


def test_state_boundary_is_lossless_and_conservative():
    context, goal = split_state("x : Nat\ny : Nat\n⊢ x = y")
    assert context + goal == "x : Nat\ny : Nat\n⊢ x = y"
    with pytest.raises(ValueError):
        split_state("x : Nat\n⊢ a\n⊢ b")


def test_dataset_pin_matches_local_metadata():
    source = Path("/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4")
    pin = validate_source_pin(source)
    assert pin["mathlib_commit"] == "29dcec074de168ac2bf835a77ef68bbe069194c5"
