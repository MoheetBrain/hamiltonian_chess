"""Contract tests for the precondition-conjunction ladder v2.

Offline, CPU-only and fast.  They pin the properties the instrument's honesty rests on:
determinism, pool disjointness, exact twin balance, an independently re-derived truth, verified
canonical states, the harness protocol, and that a deliberately broken family is refused.
"""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from arena.canonical.schema import CanonicalExpression
from arena.environments import precondition_ladder as pl
from arena.environments.precondition_ladder import (
    ENVIRONMENT_VERSION,
    LADDER,
    MECHANISM,
    PRIMARY_LADDER,
    QUESTION,
    LadderParams,
    Pool,
    PreconditionFamily,
    Variant,
    build_family,
    build_pool,
    family_invariants,
    family_salt,
    held_premises,
    independent_truth,
    licensed_answers,
    premise_digits,
    stratum_params,
    surface_length_summary,
    transposition_neighbours,
)
from arena.experiments.fitness_v4 import _option as v4_option
from arena.experiments.fitness_v4 import _premise_family as v4_premise_family
from arena.experiments.fitness_v4 import satisfied_options as v4_satisfied_options
from arena.experiments.game_r_formal_v1 import ItemVariant, MaterialisedItem, rotate_options
from arena.verifier.native import NativeVerifier

DOCUMENTED_STRATA = (
    "P05_EXPLICIT",
    "P05",
    "P07",
    "P09",
    "P12",
    "P16",
    "P20",
    "P05_X16",
    "P05_X32",
    "P05_M2_D2",
    "P05_M3_D4",
    "P12_M2_D2",
)
FAMILIES_PER_STRATUM = 5
#: Pinned so that any change to the generator is a visible instrument change.
GOLDEN_P05_DEV_0 = {
    "original": "f9aa6cf3df9783a66dfc059b847a21f5fb8158d5dfd16302834dbc56592df68e",
    "counterfactual": "d67af3ba1e397e1ecc7f7bcfb52db1f7cac617a3ff022ae39f46ff7ea8bf08bc",
}


def _holds(premise: str) -> CanonicalExpression:
    return CanonicalExpression(
        "holds",
        (CanonicalExpression("symbol", value=premise, sort="Identifier"),),
        sort="Proposition",
    )


@pytest.fixture(scope="module")
def families() -> dict[str, tuple[PreconditionFamily, ...]]:
    return {
        stratum: tuple(
            build_family(stratum, Pool.DEV, index) for index in range(FAMILIES_PER_STRATUM)
        )
        for stratum in LADDER
    }


# ------------------------------------------------------------------------------ ladder


def test_ladder_keys_are_exactly_the_documented_set() -> None:
    assert tuple(LADDER) == DOCUMENTED_STRATA
    assert set(pl.STRATUM_ROLE) == set(LADDER)
    for stratum in LADDER:
        assert stratum_params(stratum) is LADDER[stratum]
    assert ENVIRONMENT_VERSION == "arena-precondition-ladder-v2.0.0"
    assert MECHANISM == "precondition_conjunction"


def test_primary_ladder_is_strictly_monotone_in_premises() -> None:
    counts = [LADDER[stratum].premises for stratum in PRIMARY_LADDER]
    assert counts == [5, 7, 9, 12, 16, 20]
    assert all(left < right for left, right in zip(counts, counts[1:], strict=False))
    for stratum in PRIMARY_LADDER:
        params = LADDER[stratum]
        assert (params.extras, params.missing_near_misses, params.decoy_near_misses) == (6, 1, 0)
        assert params.distractor_objects == 4 and not params.explicit
        assert params.level == params.premises


def test_control_strata_declare_their_parameters() -> None:
    assert LADDER["P05_EXPLICIT"] == LadderParams(premises=5, explicit=True)
    assert LADDER["P05_EXPLICIT"].level == 0
    assert LADDER["P05_X16"].extras == 16 and LADDER["P05_X32"].extras == 32
    assert (LADDER["P05_M2_D2"].missing_near_misses, LADDER["P05_M2_D2"].decoy_near_misses) == (
        2,
        2,
    )
    assert (LADDER["P05_M3_D4"].missing_near_misses, LADDER["P05_M3_D4"].decoy_near_misses) == (
        3,
        4,
    )
    assert LADDER["P12_M2_D2"].premises == 12


def test_ladder_params_validation() -> None:
    with pytest.raises(ValueError):
        LadderParams(premises=0)
    with pytest.raises(ValueError):
        LadderParams(premises=5, extras=-1)
    with pytest.raises(ValueError):
        LadderParams(premises=2, decoy_near_misses=3)
    assert LadderParams(premises=5).held_per_twin == 16
    assert LadderParams(premises=5, missing_near_misses=3, decoy_near_misses=4).held_per_twin == 22


def test_unknown_stratum_is_refused() -> None:
    with pytest.raises(ValueError):
        stratum_params("P99")
    with pytest.raises(ValueError):
        family_salt("P99", Pool.DEV, 0)
    with pytest.raises(ValueError):
        build_family("P05", Pool.DEV, -1)


def test_module_uses_no_nondeterministic_sources() -> None:
    source = Path(inspect.getsourcefile(pl) or "").read_text()
    tree = ast.parse(source)
    forbidden = {"random", "time", "uuid", "os", "secrets", "datetime"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "__import__"
    assert not imported & forbidden, imported & forbidden


# -------------------------------------------------------------------------- determinism


def test_build_family_is_deterministic_within_and_across_processes() -> None:
    first, second = build_family("P05", Pool.DEV, 0), build_family("P05", Pool.DEV, 0)
    assert first.to_dict() == second.to_dict()
    assert [item.to_dict() for item in first.items()] == [item.to_dict() for item in second.items()]
    assert first.original.mathematical_hash == GOLDEN_P05_DEV_0["original"]
    assert first.counterfactual.mathematical_hash == GOLDEN_P05_DEV_0["counterfactual"]
    script = (
        "from arena.environments.precondition_ladder import build_family, Pool; "
        "f = build_family('P05', Pool.DEV, 0); "
        "print(f.original.mathematical_hash, f.counterfactual.mathematical_hash)"
    )
    output = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    ).stdout.split()
    assert output == [GOLDEN_P05_DEV_0["original"], GOLDEN_P05_DEV_0["counterfactual"]]


def test_different_index_gives_a_different_family() -> None:
    zero, one = build_family("P05", Pool.DEV, 0), build_family("P05", Pool.DEV, 1)
    assert zero.family_id != one.family_id
    assert zero.original.mathematical_hash != one.original.mathematical_hash
    assert {zero.answer_a, zero.answer_b}.isdisjoint({one.answer_a, one.answer_b})


def test_family_salt_carries_version_stratum_pool_and_index() -> None:
    salt = family_salt("P07", Pool.SMOKE, 3)
    for part in (ENVIRONMENT_VERSION, "P07", "SMOKE", "3"):
        assert part in salt
    assert family_salt("P07", "SMOKE", 3) == salt
    assert len({family_salt("P07", pool, 3) for pool in Pool}) == len(Pool)


def test_pools_are_disjoint_by_construction() -> None:
    for stratum in ("P05", "P12_M2_D2"):
        ids: dict[str, str] = {}
        hashes: dict[str, str] = {}
        for pool in Pool:
            for index in range(3):
                family = build_family(stratum, pool, index)
                assert family.family_id not in ids
                ids[family.family_id] = pool.value
                for state in (family.original, family.counterfactual, family.destroyed):
                    assert state.mathematical_hash not in hashes
                    hashes[state.mathematical_hash] = family.family_id


def test_build_pool_is_balanced_family_major_and_offsettable() -> None:
    for pool in Pool:
        items = build_pool("P05", pool, 4)
        assert len(items) == 8
        assert [item.correct_index for item in items] == [0, 1] * 4
        assert [item.variant for item in items] == ["ORIGINAL", "COUNTERFACTUAL"] * 4
        for original, counter in zip(items[::2], items[1::2], strict=True):
            assert original.family_id == counter.family_id
            assert original.options is counter.options
            assert original.provenance["twin_of"] == counter.task_id
            assert counter.provenance["twin_of"] == original.task_id
        assert len({item.task_id for item in items}) == 8
    offset = build_pool("P05", Pool.DEV, 2, start=2)
    assert [item.family_id for item in offset] == [
        item.family_id for item in build_pool("P05", Pool.DEV, 4)[4:]
    ]


# ---------------------------------------------------------------------------- invariants


def test_family_invariants_pass_for_every_stratum(families) -> None:
    for stratum, built in families.items():
        params = LADDER[stratum]
        for family in built:
            record = family_invariants(family)
            assert record["requires"] == 2 * params.premises
            assert record["holds_per_twin"] == params.held_per_twin
            assert record["holds_destroyed"] == params.held_destroyed
            assert record["extras"] == params.extras
            assert record["twin_differing_slots"] == 1 + params.missing_near_misses
            assert record["explicit"] is params.explicit
            assert record["premise_digits"] == 4
            assert family.attempt == 0


def test_independent_truth_agrees_with_construction(families) -> None:
    for built in families.values():
        for family in built:
            assert independent_truth(family.original, family.options) == 0
            assert independent_truth(family.counterfactual, family.options) == 1
            assert licensed_answers(family.original) == {family.answer_a}
            assert licensed_answers(family.counterfactual) == {family.answer_b}
            assert not licensed_answers(family.destroyed)
            with pytest.raises(ValueError):
                independent_truth(family.destroyed, family.options)
            # the frozen V4 oracle reads the same states the same way
            assert v4_satisfied_options(family.original) == {family.answer_a}
            assert v4_satisfied_options(family.counterfactual) == {family.answer_b}


def test_near_misses_never_collide_with_real_premises(families) -> None:
    for built in families.values():
        for family in built:
            real = {str(item.args[1].value) for item in family.propositions} | held_premises(
                family.original
            ) & held_premises(family.counterfactual) & held_premises(family.destroyed)
            real -= set(family.decoys)
            planted = [*family.near_misses_a, *family.near_misses_b, *family.decoys]
            assert len(set(planted)) == len(planted)
            assert not set(planted) & real
            for near in family.near_misses_a:
                assert near in transposition_neighbours(family.missing_a)
            for near in family.near_misses_b:
                assert near in transposition_neighbours(family.missing_b)
            for near, source in zip(family.decoys, family.decoy_sources, strict=True):
                assert near in transposition_neighbours(source)
                assert source in held_premises(family.original)
                assert source in held_premises(family.counterfactual)
            for premise in real:
                assert not transposition_neighbours(premise) & real


def test_twins_share_structure_and_differ_only_at_substituted_slots(families) -> None:
    for built in families.values():
        for family in built:
            original, counter, destroyed = family.original, family.counterfactual, family.destroyed
            assert original.objects is counter.objects is destroyed.objects is family.objects
            assert original.propositions is counter.propositions is destroyed.propositions
            assert original.goal is counter.goal is destroyed.goal is family.goal
            assert len(original.assumptions) == len(counter.assumptions)
            differing = [
                (str(left.args[0].value), str(right.args[0].value))
                for left, right in zip(original.assumptions, counter.assumptions, strict=True)
                if left != right
            ]
            assert len(differing) == 1 + family.params.missing_near_misses
            assert (family.missing_a, family.missing_b) in differing
            near_pairs = [
                pair for pair in differing if pair != (family.missing_a, family.missing_b)
            ]
            assert {pair[0] for pair in near_pairs} == set(family.near_misses_b)
            assert {pair[1] for pair in near_pairs} == set(family.near_misses_a)
            assert held_premises(original) ^ held_premises(counter) == (
                {family.missing_a, family.missing_b}
                | set(family.near_misses_a)
                | set(family.near_misses_b)
            )


def test_every_state_is_verifier_accepted(families) -> None:
    verifier = NativeVerifier()
    for built in families.values():
        for family in built:
            for state in (family.original, family.counterfactual, family.destroyed):
                assert verifier.verify_state(state).accepted
                assert not state.legal_actions and not state.plausible_invalid_actions
            assert all(option.expected_usefulness == 0.0 for option in family.options)


def test_explicit_stratum_adds_the_answer_is_and_nothing_else() -> None:
    explicit = LADDER["P05_EXPLICIT"]
    plain = replace(explicit, explicit=False)
    salt = family_salt("P05_EXPLICIT", Pool.DEV, 0)
    kwargs = {
        "family_id": "x",
        "stratum": "P05_EXPLICIT",
        "pool": Pool.DEV,
        "family_index": 0,
        "attempt": 0,
    }
    with_fact = pl._construct(explicit, salt, **kwargs)
    without = pl._construct(plain, salt, **kwargs)
    for left, right, answer in (
        (with_fact.original, without.original, with_fact.answer_a),
        (with_fact.counterfactual, without.counterfactual, with_fact.answer_b),
        (with_fact.destroyed, without.destroyed, with_fact.answer_a),
    ):
        assert left.established_facts == (pl._relation("the_answer_is", answer),)
        assert right.established_facts == ()
        assert replace(left, established_facts=()).mathematical_hash == right.mathematical_hash
    assert with_fact.options == without.options
    assert with_fact.items()[0].level == 0 and without.items()[0].level == 5
    assert (
        build_family("P05_EXPLICIT", Pool.DEV, 0).original.established_facts[0].op
        == "the_answer_is"
    )


def test_encoding_matches_the_frozen_v4_instrument() -> None:
    family = build_family("P05", Pool.DEV, 0)
    assert v4_premise_family({"premises": 5}, "any-salt").question == QUESTION
    assert family.options == (
        v4_option(0, family.answer_a, family.answer_b),
        v4_option(1, family.answer_b, family.answer_a),
    )
    v4 = v4_premise_family({"premises": 5}, "any-salt")
    assert {item.op for item in family.propositions} == {
        item.op for item in v4.original.propositions
    }
    assert {item.op for item in family.original.assumptions} == {
        item.op for item in v4.original.assumptions
    }
    assert family.goal == v4.original.goal
    assert [item.type_name for item in family.objects] == [
        item.type_name for item in v4.original.objects
    ]
    assert len(family.original.assumptions) == len(v4.original.assumptions)


# ------------------------------------------------------------------------------ protocol


def test_items_satisfy_the_task_item_protocol_and_rotate() -> None:
    family = build_family("P07", Pool.TOURNAMENT, 2)
    for item in (*family.items(), family.destroyed_item(0), family.destroyed_item(1)):
        assert isinstance(item, MaterialisedItem)
        for name in (
            "task_id",
            "family_id",
            "level",
            "variant",
            "question",
            "canonical_state",
            "options",
            "correct_index",
            "provenance",
        ):
            assert hasattr(item, name)
        assert item.task_id.startswith(item.family_id)
        assert item.question == QUESTION
        assert item.options is family.options
        json.dumps(item.to_dict())
        for key in ("stratum", "pool", "params", "generator_version", "twin_of", "premise_digits"):
            assert key in item.provenance
        assert item.provenance["generator_version"] == ENVIRONMENT_VERSION
        rotated = rotate_options(item)
        assert rotated.variant == str(ItemVariant.ORDER_ROTATED)
        assert rotated.canonical_state is item.canonical_state
        assert rotated.correct_index == (item.correct_index + 1) % 2
        assert rotated.options[rotated.correct_index] is item.options[item.correct_index]
        if item.variant in {"ORIGINAL", "COUNTERFACTUAL"}:
            assert (
                independent_truth(rotated.canonical_state, rotated.options) == rotated.correct_index
            )
    original, counter = family.items()
    assert (original.variant, counter.variant) == ("ORIGINAL", "COUNTERFACTUAL")
    assert (original.correct_index, counter.correct_index) == (0, 1)
    assert original.task_id == f"{family.family_id}:ORIGINAL"


def test_destroyed_items_are_a_shared_state_negative_control() -> None:
    family = build_family("P05", Pool.SMOKE, 0)
    zero, one = family.destroyed_item(0), family.destroyed_item(1)
    assert zero.canonical_state is one.canonical_state is family.destroyed
    assert (zero.correct_index, one.correct_index) == (0, 1)
    assert (zero.variant, one.variant) == (
        Variant.DESTROYED_ORIGINAL.value,
        Variant.DESTROYED_COUNTERFACTUAL.value,
    )
    assert zero.provenance["truth_kind"] == "NEGATIVE_CONTROL_TARGET"
    assert zero.provenance["twin_of"] == one.task_id
    with pytest.raises(ValueError):
        family.destroyed_item(2)


# ------------------------------------------------------------------------------ mutation


def _with_original_assumptions(
    family: PreconditionFamily, assumptions: tuple[CanonicalExpression, ...]
) -> PreconditionFamily:
    return replace(family, original=replace(family.original, assumptions=assumptions))


def test_broken_families_are_rejected() -> None:
    family = build_family("P05_M2_D2", Pool.DEV, 1)
    original = family.original
    # the unlicensed answer's missing premise re-added: both answers licensed
    relicensed = _with_original_assumptions(
        family, (*original.assumptions, _holds(family.missing_b))
    )
    with pytest.raises(ValueError):
        family_invariants(relicensed)
    assert licensed_answers(relicensed.original) == {family.answer_a, family.answer_b}
    with pytest.raises(ValueError, match="exactly one licensed"):
        independent_truth(relicensed.original, family.options)
    # same count, both licensed: a near-miss slot replaced by the missing premise itself
    with pytest.raises(ValueError):
        family_invariants(
            _with_original_assumptions(
                family,
                tuple(
                    _holds(family.missing_b) if item == _holds(family.near_misses_b[0]) else item
                    for item in original.assumptions
                ),
            )
        )
    # the licensed answer's would-be-missing premise dropped: nothing licensed
    with pytest.raises(ValueError):
        family_invariants(
            _with_original_assumptions(
                family,
                tuple(item for item in original.assumptions if item != _holds(family.missing_a)),
            )
        )
    # a near-miss dropped: hold counts no longer match
    with pytest.raises(ValueError):
        family_invariants(
            _with_original_assumptions(
                family,
                tuple(
                    item for item in original.assumptions if item != _holds(family.near_misses_b[0])
                ),
            )
        )
    # a near-miss replaced by an unrelated held premise: same count, wrong difference
    with pytest.raises(ValueError):
        family_invariants(
            _with_original_assumptions(
                family,
                tuple(
                    _holds("p:9999") if item == _holds(family.near_misses_b[0]) else item
                    for item in original.assumptions
                ),
            )
        )
    # the twin order reshuffled: same set, substituted slots no longer aligned
    with pytest.raises(ValueError, match="slot"):
        family_invariants(_with_original_assumptions(family, tuple(reversed(original.assumptions))))
    # a copied (equal but not identical) propositions tuple breaks shared identity
    with pytest.raises(ValueError, match="not shared"):
        family_invariants(
            replace(
                family, original=replace(original, propositions=tuple(list(original.propositions)))
            )
        )
    # an option that leaks usefulness
    with pytest.raises(ValueError, match="usefulness"):
        family_invariants(
            replace(
                family,
                options=(replace(family.options[0], expected_usefulness=1.0), family.options[1]),
            )
        )
    # explicit fact on a non-explicit stratum
    with pytest.raises(ValueError, match="established"):
        family_invariants(
            replace(
                family,
                original=replace(
                    original, established_facts=(pl._relation("the_answer_is", family.answer_a),)
                ),
            )
        )
    # the untouched family still passes
    family_invariants(family)


# ------------------------------------------------------------------------------ surfaces


def test_premise_digits_grow_only_when_the_id_space_is_exhausted() -> None:
    assert premise_digits(1) == 4
    assert premise_digits(max(params.premise_ids_needed for params in LADDER.values())) == 4
    assert premise_digits(300) == 5
    assert premise_digits(3000) == 6


def test_surface_length_summary_reports_every_requested_surface() -> None:
    summary = surface_length_summary("P05", Pool.DEV, 1, ("L3_JSON_AST", "L5_COMPACT_SYMBOLIC"))
    assert summary["items"] == 2 and summary["stratum"] == "P05"
    assert set(summary["surfaces"]) == {"L3_JSON_AST", "L5_COMPACT_SYMBOLIC"}
    for record in summary["surfaces"].values():
        assert 0 < record["min"] <= record["mean"] <= record["max"]
        assert set(record["by_variant"]) == {"ORIGINAL", "COUNTERFACTUAL"}
        # the twins differ only in a handful of substituted identifiers of equal length
        assert (
            record["by_variant"]["ORIGINAL"]["mean"]
            == record["by_variant"]["COUNTERFACTUAL"]["mean"]
        )
    json.dumps(summary)
