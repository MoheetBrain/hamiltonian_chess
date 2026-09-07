"""Tests for the rewrite-direction task family.

CPU-only, offline, no Lean, no model call.  The tests that touch the real LeanDojo corpus
skip cleanly when it is not present, so the suite still runs on a machine without it.
"""

from __future__ import annotations

import itertools
import json
import os

import pytest

from arena.environments import rewrite_direction as rw

LEANDOJO_ROOT = (
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4"
)
TRAIN_JSON = os.path.join(LEANDOJO_ROOT, "random", "train.json")
CORPUS_JSONL = os.path.join(LEANDOJO_ROOT, "corpus.jsonl")

requires_corpus = pytest.mark.skipif(
    not (os.path.exists(TRAIN_JSON) and os.path.exists(CORPUS_JSONL)),
    reason="LeanDojo Benchmark 4 not present on this machine",
)


# ---------------------------------------------------------------------------
# synthetic fixtures: everything that does not need the 373 MB corpus
# ---------------------------------------------------------------------------
SIGNATURES = {
    "Nat.mul_comm": "protected theorem mul_comm : ∀ (n m : Nat), n * m = m * n",
    "Set.image_id": "theorem image_id (s : Set α) : id '' s = s",
    "LinearMap.range_eq_top": (
        "theorem range_eq_top [RingHomSurjective τ₁₂] {f : F} : range f = ⊤ ↔ Surjective f"
    ),
    "Foo.not_an_equation": "theorem not_an_equation (a : α) : P a",
    "Foo.with_proof_body": (
        "theorem with_proof_body (a b : Nat) : a + b = b + a := by\n  rw [Nat.add_comm]"
    ),
}


def _step(tactic: str, annotated: str, *, state: str = "n m : Nat\n⊢ n * m = 6", index: int = 0):
    return {
        "file_path": "Mathlib/Fake/File.lean",
        "thm": "fake_theorem",
        "proof_id": "Mathlib/Fake/File.lean::fake_theorem",
        "step_index": index,
        "tactic": tactic,
        "annotated_tactic": annotated,
        "state_before": state,
        "state_after": "",
    }


FORWARD_STEP = _step("rw [Nat.mul_comm]", "rw [<a>Nat.mul_comm</a>]")
REVERSE_STEP = _step("rw [← Nat.mul_comm]", "rw [← <a>Nat.mul_comm</a>]", index=1)
ASCII_REVERSE_STEP = _step("rw [<- Set.image_id]", "rw [<- <a>Set.image_id</a>]", index=2)
AT_STEP = _step("rw [← Set.image_id] at hs", "rw [← <a>Set.image_id</a>] at hs", index=3)


# ---------------------------------------------------------------------------
# tactic parsing
# ---------------------------------------------------------------------------
def test_parses_forward_and_both_reverse_spellings() -> None:
    assert rw.parse_rewrite_tactic("rw [Nat.mul_comm]").direction == rw.FORWARD
    assert rw.parse_rewrite_tactic("rw [← Nat.mul_comm]").direction == rw.REVERSE
    assert rw.parse_rewrite_tactic("rw [<- Nat.mul_comm]").direction == rw.REVERSE


def test_parses_multi_element_bracket_and_flags_mixed_direction() -> None:
    parsed = rw.parse_rewrite_tactic("rw [a, ← b, c]")
    assert parsed.element_directions == (rw.FORWARD, rw.REVERSE, rw.FORWARD)
    assert parsed.is_mixed is True
    # the population rule: the item is labelled by the FIRST element, the only one that acts
    # on the recorded state_before.
    assert parsed.direction == rw.FORWARD

    uniform = rw.parse_rewrite_tactic("rw [← a, ← b]")
    assert uniform.is_mixed is False
    assert uniform.direction == rw.REVERSE


def test_parses_at_location_and_other_rewrite_heads() -> None:
    assert rw.parse_rewrite_tactic("rw [← h] at hn").location == "hn"
    assert rw.parse_rewrite_tactic("rw [h]").location is None
    for head in ("rewrite", "erw", "rwa", "simp_rw", "rw_mod_cast"):
        assert rw.parse_rewrite_tactic(f"{head} [← foo]").head == head
    assert rw.parse_rewrite_tactic("nth_rw 2 [← foo]").direction == rw.REVERSE


def test_rejects_non_rewrites_and_unsafe_trailers() -> None:
    assert rw.parse_rewrite_tactic("simp [foo]") is None
    assert rw.parse_rewrite_tactic("exact foo") is None
    # a combinator after the bracket means state_before no longer isolates the rewrite
    assert rw.parse_rewrite_tactic("rw [foo] <;> simp") is None


def test_bracket_split_respects_nesting() -> None:
    parsed = rw.parse_rewrite_tactic("rw [foo (a, b), ← bar]")
    assert parsed.element_directions == (rw.FORWARD, rw.REVERSE)


# ---------------------------------------------------------------------------
# equation extraction
# ---------------------------------------------------------------------------
def test_equation_parsing_handles_quantifiers_iff_precedence_and_proof_bodies() -> None:
    equation = rw.parse_equation(SIGNATURES["Nat.mul_comm"])
    assert (equation.lhs, equation.relation, equation.rhs) == ("n * m", "=", "m * n")

    # `↔` binds looser than `=`, so this is an iff whose left side is an equation
    iff = rw.parse_equation(SIGNATURES["LinearMap.range_eq_top"])
    assert (iff.lhs, iff.relation, iff.rhs) == ("range f = ⊤", "↔", "Surjective f")

    # a stored proof body must never reach the statement
    body = rw.parse_equation(SIGNATURES["Foo.with_proof_body"])
    assert ":=" not in body.statement
    assert "rw [" not in body.statement

    assert rw.parse_equation(SIGNATURES["Foo.not_an_equation"]) is None


# ---------------------------------------------------------------------------
# leakage: the single most likely way to give the answer away
# ---------------------------------------------------------------------------
def test_no_arrow_or_tactic_text_in_rendered_synthetic_items() -> None:
    items = list(
        rw.generate_items([FORWARD_STEP, REVERSE_STEP, ASCII_REVERSE_STEP, AT_STEP], SIGNATURES)
    )
    assert items, "fixtures should produce items"
    for item in items:
        rendered = item.render()
        assert "←" not in rendered
        assert "<-" not in rendered
        assert "<a>" not in rendered and "</a>" not in rendered
        assert "rw [" not in rendered
        assert rw.leakage_violations(item) == []


def test_rendered_item_never_contains_the_recorded_tactic_text() -> None:
    for step in (FORWARD_STEP, REVERSE_STEP, AT_STEP):
        for item in rw.generate_items([step], SIGNATURES):
            assert step["tactic"] not in item.render()
            assert step["annotated_tactic"] not in item.render()


def test_leakage_detector_actually_fires_on_a_planted_leak() -> None:
    """A leakage test that cannot fail open: plant a leak and require it to be caught."""

    item = next(iter(rw.generate_items([FORWARD_STEP], SIGNATURES)))
    leaked = rw.RewriteDirectionItem(
        item_id=item.item_id,
        state=item.state + "\n-- applied as rw [← Nat.mul_comm]",
        premise_name=item.premise_name,
        equation=item.equation,
        location_label=item.location_label,
        options=item.options,
        answer_index=item.answer_index,
        direction=item.direction,
        level=item.level,
        explicit_positive=item.explicit_positive,
        features=item.features,
        provenance=item.provenance,
    )
    problems = rw.leakage_violations(leaked)
    assert any("reverse marker" in problem for problem in problems)
    assert any("tactic text" in problem for problem in problems)


def test_generator_drops_items_that_would_leak() -> None:
    poisoned = _step(
        "rw [Nat.mul_comm]",
        "rw [<a>Nat.mul_comm</a>]",
        state="h : a ← b\n⊢ n * m = 6",
        index=9,
    )
    discards: dict[str, int] = {}
    items = list(rw.generate_items([poisoned], SIGNATURES, discards=discards))
    assert items == []
    assert discards["arrow_token_in_rendered_text"] == 1


def test_explicit_positive_arm_is_level_zero_and_states_the_relation() -> None:
    items = list(rw.generate_items([FORWARD_STEP], SIGNATURES, explicit_positive_every=1))
    l0 = [item for item in items if item.explicit_positive]
    assert len(l0) == 1
    assert l0[0].level == 0
    assert "Given fact:" in l0[0].render()
    assert rw.leakage_violations(l0[0]) == []
    # and the non-L0 twin must not carry the hint
    core = [item for item in items if not item.explicit_positive]
    assert "Given fact:" not in core[0].render()
    # an L0 twin is a distinct item from its base and must not reuse its id
    assert l0[0].item_id != core[0].item_id
    assert len({item.item_id for item in items}) == len(items)


# ---------------------------------------------------------------------------
# determinism and labelling
# ---------------------------------------------------------------------------
def test_same_seed_reproduces_byte_identical_items() -> None:
    steps = [FORWARD_STEP, REVERSE_STEP, AT_STEP]
    first = [i.render() for i in rw.generate_items(steps, SIGNATURES, seed=7)]
    second = [i.render() for i in rw.generate_items(steps, SIGNATURES, seed=7)]
    assert first == second
    ids_first = [i.item_id for i in rw.generate_items(steps, SIGNATURES, seed=7)]
    ids_second = [i.item_id for i in rw.generate_items(steps, SIGNATURES, seed=7)]
    assert ids_first == ids_second


def test_a_different_seed_can_permute_the_options_but_not_the_answer() -> None:
    steps = [FORWARD_STEP, REVERSE_STEP, ASCII_REVERSE_STEP, AT_STEP]
    for seed in (1, 2, 3, 4, 5):
        for item in rw.generate_items(steps, SIGNATURES, seed=seed):
            assert item.options[item.answer_index] == item.direction
            assert set(item.options) == {rw.FORWARD, rw.REVERSE}
            assert item.answer == item.direction


def test_answer_matches_the_recorded_direction() -> None:
    by_index = {
        item.provenance["step_index"]: item
        for item in rw.generate_items(
            [FORWARD_STEP, REVERSE_STEP, ASCII_REVERSE_STEP, AT_STEP], SIGNATURES
        )
    }
    assert by_index[0].direction == rw.FORWARD
    assert by_index[1].direction == rw.REVERSE
    assert by_index[2].direction == rw.REVERSE
    assert by_index[3].direction == rw.REVERSE


# ---------------------------------------------------------------------------
# provenance and sealed-split discipline
# ---------------------------------------------------------------------------
def test_every_item_carries_full_provenance_from_the_train_split() -> None:
    for item in rw.generate_items([FORWARD_STEP, AT_STEP], SIGNATURES):
        provenance = item.provenance
        for key in ("proof_id", "file_path", "thm", "step_index", "split", "mathlib4_commit"):
            assert provenance[key] not in (None, "")
        assert provenance["split"] == "train"
        assert provenance["source_file"] == "random/train.json"
        assert provenance["mathlib4_commit"] == rw.MATHLIB4_COMMIT
        assert provenance["environment_version"] == rw.ENVIRONMENT_VERSION


@pytest.mark.parametrize("sealed", sorted(rw.SEALED_RELATIVE_PATHS))
def test_sealed_splits_are_refused(sealed: str) -> None:
    with pytest.raises(rw.SealedSplitError):
        rw.assert_source_permitted(sealed)
    with pytest.raises(rw.SealedSplitError):
        rw.assert_source_permitted(os.path.join(LEANDOJO_ROOT, sealed))


def test_permitted_sources_are_accepted() -> None:
    rw.assert_source_permitted("random/train.json")
    rw.assert_source_permitted("corpus.jsonl")


def test_load_signatures_refuses_a_sealed_path() -> None:
    with pytest.raises(rw.SealedSplitError):
        rw.load_signatures(os.path.join(LEANDOJO_ROOT, "random", "val.json"))


# ---------------------------------------------------------------------------
# balancing and the ladder
# ---------------------------------------------------------------------------
def _fake_items(pairs: list[tuple[str, str]]) -> list[rw.RewriteDirectionItem]:
    steps = []
    for index, (name, direction) in enumerate(pairs):
        arrow = "← " if direction == rw.REVERSE else ""
        steps.append(_step(f"rw [{arrow}{name}]", f"rw [{arrow}<a>{name}</a>]", index=index))
    return list(rw.generate_items(steps, SIGNATURES))


def test_balance_items_makes_chance_exactly_one_half() -> None:
    items = _fake_items([("Nat.mul_comm", rw.FORWARD)] * 5 + [("Nat.mul_comm", rw.REVERSE)] * 2)
    balanced = rw.balance_items(items)
    directions = [item.direction for item in balanced]
    assert directions.count(rw.FORWARD) == directions.count(rw.REVERSE) == 2


def test_within_lemma_control_equalises_every_lemma_and_drops_one_sided_ones() -> None:
    items = _fake_items(
        [("Nat.mul_comm", rw.FORWARD)] * 3
        + [("Nat.mul_comm", rw.REVERSE)] * 1
        + [("Set.image_id", rw.FORWARD)] * 2  # never reversed -> dropped entirely
    )
    controlled = rw.balance_within_lemma(items)
    names = {item.premise_name for item in controlled}
    assert names == {"Nat.mul_comm"}
    directions = [item.direction for item in controlled]
    assert directions.count(rw.FORWARD) == directions.count(rw.REVERSE) == 1


def test_balancing_is_deterministic_under_a_fixed_seed() -> None:
    items = _fake_items([("Nat.mul_comm", rw.FORWARD)] * 6 + [("Nat.mul_comm", rw.REVERSE)] * 3)
    first = [i.item_id for i in rw.balance_within_lemma(items, seed=11)]
    second = [i.item_id for i in rw.balance_within_lemma(items, seed=11)]
    assert first == second


def test_difficulty_score_moves_with_each_axis_and_bins_into_three_levels() -> None:
    easy = rw.DifficultyFeatures(
        side_similarity=0.0,
        lhs_signature_hits=3,
        rhs_signature_hits=0,
        decisive_side_margin=3,
        target_depth=0,
        plausible_sites=0,
        context_equations=0,
        length_ratio=1.0,
    )
    hard = rw.DifficultyFeatures(
        side_similarity=1.0,
        lhs_signature_hits=0,
        rhs_signature_hits=0,
        decisive_side_margin=0,
        target_depth=6,
        plausible_sites=9,
        context_equations=5,
        length_ratio=1.0,
    )
    assert rw.difficulty_score(easy) == 0
    assert rw.difficulty_score(hard) == 10
    assert rw.difficulty_level(easy) == 1
    assert rw.difficulty_level(hard) == 3
    middling = rw.DifficultyFeatures(
        side_similarity=0.5,  # cost 1
        lhs_signature_hits=2,
        rhs_signature_hits=0,
        decisive_side_margin=2,  # cost 0
        target_depth=2,  # cost 1
        plausible_sites=2,  # cost 1
        context_equations=0,  # cost 0
        length_ratio=1.0,
    )
    assert rw.difficulty_score(middling) == 3
    assert rw.difficulty_level(middling) == 2


def test_split_dev_partitions_by_source_file() -> None:
    items = _fake_items([("Nat.mul_comm", rw.FORWARD)] * 4)
    train, held = rw.split_dev(items, holdout_fraction=0.0)
    assert held == []
    assert len(train) == len(items)


# ---------------------------------------------------------------------------
# real-corpus checks
# ---------------------------------------------------------------------------
@requires_corpus
def test_real_items_are_clean_deterministic_and_train_only() -> None:
    from research.env_rewrite.stream import iter_train_steps

    signatures = rw.load_signatures(CORPUS_JSONL)
    items = list(rw.generate_items(itertools.islice(iter_train_steps(), 4000), signatures))
    assert len(items) > 50, "the first 4000 train steps should yield a usable sample"

    for item in items:
        assert rw.leakage_violations(item) == []
        assert item.provenance["split"] == "train"
        assert item.provenance["proof_id"]
        assert item.direction in (rw.FORWARD, rw.REVERSE)
        assert item.options[item.answer_index] == item.direction
        assert item.level in (1, 2, 3)

    again = list(rw.generate_items(itertools.islice(iter_train_steps(), 4000), signatures))
    assert [i.render() for i in items] == [i.render() for i in again]


@requires_corpus
def test_no_item_comes_from_a_sealed_split() -> None:
    """Cross-check every generated proof_id against the val/test theorem identities.

    The sealed *files* are never opened.  ``steps.jsonl`` is a metadata index that carries a
    ``split`` field for all splits, so the val/test identities can be read from it and used as
    an exclusion list without touching a sealed pool.
    """

    from research.env_rewrite.stream import STEPS_JSONL, iter_train_steps

    if not os.path.exists(STEPS_JSONL):
        pytest.skip("steps.jsonl metadata index not present")

    sealed_ids = set()
    with open(STEPS_JSONL, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            split = record.get("split") or record.get("prov", {}).get("split")
            if split != "train":
                sealed_ids.add(record["proof_id"])

    signatures = rw.load_signatures(CORPUS_JSONL)
    items = list(rw.generate_items(itertools.islice(iter_train_steps(), 20000), signatures))
    assert items
    offending = [i.item_id for i in items if i.provenance["proof_id"] in sealed_ids]
    assert offending == [], f"{len(offending)} items came from a non-train proof"


@requires_corpus
def test_manifest_matches_the_shipped_generator() -> None:
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "artifacts",
        "manifests",
        "rewrite_direction_manifest.json",
    )
    if not os.path.exists(manifest_path):
        pytest.skip("manifest not built yet")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["generator"]["environment_version"] == rw.ENVIRONMENT_VERSION
    assert manifest["generator"]["generator_version"] == rw.GENERATOR_VERSION
    assert manifest["dataset"]["mathlib4_commit"] == rw.MATHLIB4_COMMIT
    assert manifest["dataset"]["split_used"] == "train"
    assert set(manifest["discards"]["counts"]) <= set(rw.DISCARD_REASONS)
