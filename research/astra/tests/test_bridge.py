from dataclasses import replace

import pytest

from research.astra.game_r_premise.schema import (
    BackendText, Candidate, CanonicalPremiseSelectionState, label_to_choice_id,
    order_candidates, verify_response, visible_projection,
)
from research.astra.game_r_premise.renderer_bridge import REPRESENTATIONS, decode, encode_projection, render
from research.astra.game_r_premise.information_inventory import assert_parity, information_inventory
from research.astra.game_r_premise.invariance import (
    UnsupportedTransformation, alpha_rename_locals, obfuscate_option_identities,
    permute_independent_context, permute_options,
)


@pytest.fixture
def item():
    return CanonicalPremiseSelectionState(
        task_id="fixture", provenance={"proof_id": "fixture", "commit": "test"},
        formal_system="Lean4", context=BackendText("x : Nat\ny : Nat\n", "context"),
        goal=BackendText("⊢ x + y = y + x", "goal"),
        candidate_premises=tuple(Candidate(f"id_{i}", name,
            BackendText(statement, "signature", "lean4-source"), {"path": "fixture"})
            for i, (name, statement) in enumerate([
                ("Nat.add_comm", "theorem Nat.add_comm (x y : Nat) : x + y = y + x"),
                ("Nat.add_assoc", "theorem Nat.add_assoc (x y z : Nat) : x + y + z = x + (y + z)"),
                ("Nat.mul_comm", "theorem Nat.mul_comm (x y : Nat) : x * y = y * x"),
            ])),
        target_choice_id="id_0", oracle_evidence={"private_marker": "PRIVATE_ORACLE"},
        source_raw_state="x : Nat\ny : Nat\n⊢ x + y = y + x", audit_metadata={"private": "PRIVATE_AUDIT"},
    )


@pytest.mark.parametrize("representation", REPRESENTATIONS)
def test_decode_actual_bytes_and_no_oracle(item, representation):
    source = render(item, representation)
    assert decode(source, representation) == visible_projection(item)
    assert "PRIVATE_ORACLE" not in source and "PRIVATE_AUDIT" not in source
    poisoned = replace(item, target_choice_id="id_2", provenance={"secret": "SECRET"},
        oracle_evidence={"target": "SECRET"}, audit_metadata={"secret": "SECRET"})
    assert render(poisoned, representation) == source
    with pytest.raises(ValueError):
        decode(source + "\nPRIVATE_ORACLE", representation)


def test_parity_inventory_detects_loss_order_and_multiplicity(item):
    assert assert_parity(item)["status"].endswith("PASS")
    expected = information_inventory(visible_projection(item))
    altered = visible_projection(item)
    altered["candidates"][0]["statement"]["text"] += " extra"
    assert information_inventory(altered) != expected
    altered = visible_projection(item)
    altered["context"]["text"] += "x : Nat\n"
    assert information_inventory(altered) != expected
    assert information_inventory(visible_projection(permute_options(item, (2, 1, 0)))) != expected


@pytest.mark.parametrize("representation", REPRESENTATIONS)
def test_adversarial_string_framing_is_data(item, representation):
    strange = 'x : Nat\n"}; ) ( target_choice_id := LEAK; \\ \u2028'
    changed = replace(item, context=replace(item.context, text=strange), source_raw_state=strange + item.goal.text)
    # JSON escapes normal newlines; Unicode line separator must not become a record delimiter.
    text = render(changed, representation)
    assert decode(text, representation) == visible_projection(changed)


def test_oracle_follows_semantic_identity(item):
    swapped = permute_options(item, (2, 1, 0))
    assert swapped.target_choice_id == item.target_choice_id
    assert verify_response(item, "A") and verify_response(swapped, "C")
    assert not verify_response(swapped, "A")
    for invalid in ("", "a", " A", "AA", "Z", 1):
        with pytest.raises(ValueError):
            label_to_choice_id(item, invalid)
    with pytest.raises(ValueError):
        permute_options(item, (0, 0, 2))


def test_neutral_experiment_ids_do_not_change_projection(item):
    changed = obfuscate_option_identities(item)
    assert changed.target_choice_id != item.target_choice_id
    assert verify_response(changed, "A")
    assert visible_projection(changed) == visible_projection(item)


def test_alpha_and_independent_context_permutation(item):
    renamed = alpha_rename_locals(item)
    assert renamed.goal.text == "⊢ local_000 + local_001 = local_001 + local_000"
    assert renamed.target_choice_id == item.target_choice_id
    assert verify_response(renamed, "A")
    reordered = permute_independent_context(item)
    assert reordered.context.text == "y : Nat\nx : Nat\n"
    assert reordered.goal == item.goal and reordered.target_choice_id == item.target_choice_id
    assert_parity(renamed)
    assert_parity(reordered)


@pytest.mark.parametrize("context,goal", [
    ("x : Nat\nh : x = x\n", "⊢ x = x"),
    ("x : Nat\n", "⊢ ∀ x, x = x"),
    ("x : Nat\n", "⊢ Nat.succ x = x"),
    ("x : Nat\nx : Nat\n", "⊢ x = x"),
    ("x : Nat\n", "⊢ let x := 1; x = x"),
])
def test_scope_transform_fails_closed(item, context, goal):
    changed = replace(item, context=replace(item.context, text=context), goal=replace(item.goal, text=goal), source_raw_state=context + goal)
    with pytest.raises(UnsupportedTransformation):
        alpha_rename_locals(changed)
    with pytest.raises(UnsupportedTransformation):
        permute_independent_context(changed)


def test_deterministic_order_independent_of_oracle_and_source_order(item):
    assert order_candidates(item.task_id, item.candidate_premises, 19) == order_candidates(item.task_id, tuple(reversed(item.candidate_premises)), 19)
    restored = CanonicalPremiseSelectionState.from_dict(item.to_dict())
    assert restored == item and restored.canonical_hash == item.canonical_hash
    with pytest.raises(ValueError):
        replace(item, target_choice_id="missing")
    with pytest.raises(ValueError):
        replace(item, source_raw_state="different")


@pytest.mark.parametrize("representation", REPRESENTATIONS)
def test_projection_allowlist_fails_closed(item, representation):
    projection = visible_projection(item)
    projection["target_choice_id"] = "id_0"
    with pytest.raises(ValueError):
        encode_projection(projection, representation)


def test_json_duplicate_field_rejected(item):
    source = render(item, "json_ast")
    with pytest.raises(ValueError):
        decode('{"question":"oops",' + source[1:], "json_ast")
