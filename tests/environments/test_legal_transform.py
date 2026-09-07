"""Contract tests for the legal/illegal transformation family.

Offline, CPU-only and fast: the fixture is a hand-written mini proof, never the 373 MB LeanDojo
split.  The tests assert the properties the family's honesty rests on -- determinism, exact label
balance, no oracle leakage into the rendered text, no sealed-split item, a declared axis and tier
on every negative, and mechanical verification of each corruption operator's surface claims.
"""

from __future__ import annotations

import pytest

from arena.canonical.schema import CanonicalExpression
from arena.environments.formal_structural import relabel
from arena.environments.legal_transform import (
    AXIS_INVALIDITY,
    AXIS_LEVEL,
    AXIS_PROPERTIES,
    AXIS_RESIDUAL_RISK,
    ITEM_TEMPLATE,
    LEAN_TIER_A_REPLAY,
    PERMITTED_SPLIT,
    CorruptionAxis,
    DifficultyLevel,
    Discard,
    DiscardKind,
    GroundTruthTier,
    PremiseIndex,
    ProofStep,
    SealedSplitViolation,
    build_family,
    corrupt_wrong_premise,
    group_proofs,
    group_split,
    hypothesis_types,
    label_balance,
    parse_hypotheses,
    render,
    successor_derangement,
    swap_identifiers,
    token_multiset,
)

THEOREM = "Fixture/Test.lean::Fixture.thm"

_REWRITE_BEFORE = "n : ℕ\nm : ℕ\nh : n = m\n⊢ n + 0 = m"
_REWRITE_AFTER = "n : ℕ\nm : ℕ\nh : n = m\n⊢ n = m"
_AT_BEFORE = "n : ℕ\nm : ℕ\ng : n ≤ m\nh : n + 0 = m\n⊢ True"
_AT_AFTER = "n : ℕ\nm : ℕ\ng : n ≤ m\nh : n = m\n⊢ True"
_INTRO_BEFORE = "s : Set ℕ\n⊢ ∀ x y, x ∈ s → y ∈ s → True"
_INTRO_AFTER = "s : Set ℕ\na : ℕ\nb : ℤ\n⊢ a ∈ s → b ∈ s → True"
_ARG_BEFORE = "p : Nat\nq : Bool\n⊢ Goal"
_ARG_AFTER = "⊢ Goal"
_OTHER_BEFORE = "n : ℕ\nk : ℕ\nh : n = k\n⊢ Other"


def _step(
    index: int,
    tactic: str,
    before: str,
    after: str,
    *,
    annotated: str | None = None,
    premises: tuple[str, ...] = (),
    split: str = PERMITTED_SPLIT,
) -> ProofStep:
    return ProofStep(
        split=split,
        file_path="Fixture/Test.lean",
        full_name="Fixture.thm",
        step_index=index,
        n_steps=7,
        tactic=tactic,
        annotated=annotated if annotated is not None else tactic,
        premises=premises,
        state_before=before,
        state_after=after,
    )


@pytest.fixture
def steps() -> list[ProofStep]:
    return [
        _step(
            0,
            "rw [add_zero]",
            _REWRITE_BEFORE,
            _REWRITE_AFTER,
            annotated="rw [<a>add_zero</a>]",
            premises=("add_zero",),
        ),
        _step(
            1,
            "rw [← sub_self]",
            _REWRITE_AFTER,
            _REWRITE_BEFORE,
            annotated="rw [← <a>sub_self</a>]",
            premises=("sub_self",),
        ),
        _step(2, "rw [add_zero] at h", _AT_BEFORE, _AT_AFTER),
        _step(3, "intro a b", _INTRO_BEFORE, _INTRO_AFTER),
        _step(4, "exact foo p q", _ARG_BEFORE, _ARG_AFTER),
        _step(5, "simp at h", _OTHER_BEFORE, "n : ℕ\nk : ℕ\n⊢ Other"),
        _step(6, "simp at k", _OTHER_BEFORE, "n : ℕ\nh : n = k\n⊢ Other"),
    ]


@pytest.fixture
def index() -> PremiseIndex:
    names = ("add_zero", "mul_zero", "sub_self", "one_mul", "Nat.succ_le")
    return PremiseIndex(
        by_file={"Fixture/Test.lean": names},
        all_names=names,
        train_citation_frequency=dict.fromkeys(names, 5),
    )


@pytest.fixture
def built(steps: list[ProofStep], index: PremiseIndex):
    return build_family(group_proofs(steps), index)


# --------------------------------------------------------------------------- parsing


def test_parse_hypotheses_reads_names_and_types() -> None:
    entries = parse_hypotheses(_AT_BEFORE)
    assert [entry.names for entry in entries] == [("n",), ("m",), ("g",), ("h",)]
    assert hypothesis_types(_AT_BEFORE)["h"] == "n + 0 = m"
    assert "True" not in hypothesis_types(_AT_BEFORE)


def test_parse_hypotheses_joins_indented_continuations() -> None:
    block = "h : a =\n    b\n⊢ c"
    assert parse_hypotheses(block)[0].type_text == "a =\nb"


# --------------------------------------------------------------------------- coverage


def test_every_axis_produces_items(built) -> None:
    items, report = built
    produced = {item.axis for item in items if item.axis is not None}
    assert produced == set(CorruptionAxis), f"axes never fired: {set(CorruptionAxis) - produced}"


def test_every_axis_declares_a_level_an_argument_a_residual_risk_and_properties() -> None:
    for axis in CorruptionAxis:
        assert AXIS_LEVEL[axis] in set(DifficultyLevel)
        assert AXIS_INVALIDITY[axis].strip()
        assert AXIS_RESIDUAL_RISK[axis].strip()
        assert axis in AXIS_PROPERTIES


def test_the_ladder_has_an_explicit_control_arm() -> None:
    controls = [a for a, lvl in AXIS_LEVEL.items() if lvl is DifficultyLevel.L0_EXPLICIT_CONTROL]
    assert controls, "the ladder needs a visible floor"


# --------------------------------------------------------------------------- determinism


def test_build_is_deterministic(steps: list[ProofStep], index: PremiseIndex) -> None:
    first, _ = build_family(group_proofs(steps), index)
    second, _ = build_family(group_proofs(steps), index)
    assert [item.item_id for item in first] == [item.item_id for item in second]
    assert [render(item) for item in first] == [render(item) for item in second]


def test_a_different_seed_changes_at_least_the_order(
    steps: list[ProofStep], index: PremiseIndex
) -> None:
    first, _ = build_family(group_proofs(steps), index, seed=1)
    second, _ = build_family(group_proofs(steps), index, seed=2)
    assert {item.item_id for item in first} and {item.item_id for item in second}
    assert [item.item_id for item in first] != [item.item_id for item in second]


# --------------------------------------------------------------------------- labels


def test_labels_are_exactly_balanced(built) -> None:
    items, _ = built
    assert label_balance(items) == pytest.approx(0.5)


def test_every_pair_is_one_positive_and_one_negative(built) -> None:
    items, _ = built
    pairs: dict[str, list[bool]] = {}
    for item in items:
        pairs.setdefault(item.pair_id, []).append(item.valid)
    assert pairs
    for labels in pairs.values():
        assert sorted(labels) == [False, True]


def test_pair_members_share_the_state_before(built) -> None:
    items, _ = built
    by_pair: dict[str, list] = {}
    for item in items:
        by_pair.setdefault(item.pair_id, []).append(item)
    for members in by_pair.values():
        assert members[0].state_before == members[1].state_before


# --------------------------------------------------------------------------- oracle hygiene


def test_render_is_only_the_three_reader_visible_fields(built) -> None:
    items, _ = built
    for item in items:
        assert render(item) == ITEM_TEMPLATE.format(
            before=item.state_before, action=item.action, after=item.state_after
        )


def test_render_leaks_no_label_axis_tier_or_provenance(built) -> None:
    items, _ = built
    for item in items:
        text = render(item)
        forbidden = [
            item.item_id,
            item.pair_id,
            item.theorem_key,
            item.provenance.source_record_sha256,
            item.provenance.source_item_id,
            item.tier.value,
            item.level.value,
            ".lean",
            "TIER_",
            "valid",
            "INVALID",
        ]
        if item.axis is not None:
            forbidden.extend([item.axis.value, item.constructed_invalidity])
        for token in forbidden:
            assert token not in text, f"{token!r} leaked into a rendered item"


def test_positive_and_negative_renders_differ(built) -> None:
    items, _ = built
    by_pair: dict[str, list] = {}
    for item in items:
        by_pair.setdefault(item.pair_id, []).append(item)
    for members in by_pair.values():
        assert render(members[0]) != render(members[1])


# --------------------------------------------------------------------------- sealed splits


def test_a_non_train_step_is_refused(steps: list[ProofStep], index: PremiseIndex) -> None:
    poisoned = [*steps, _step(7, "rfl", _REWRITE_BEFORE, _REWRITE_AFTER, split="test")]
    with pytest.raises(SealedSplitViolation, match="only 'train'"):
        build_family(group_proofs(poisoned), index)


def test_every_item_is_provenanced_to_the_train_split(built) -> None:
    items, _ = built
    for item in items:
        assert item.provenance.source_path.startswith(f"{PERMITTED_SPLIT}:")


# --------------------------------------------------------------------------- tiers


def test_every_negative_carries_an_axis_a_tier_and_an_argument(built) -> None:
    items, _ = built
    for item in items:
        if item.valid:
            assert item.axis is None
            assert item.constructed_invalidity == ""
        else:
            assert item.axis is not None
            assert item.tier is GroundTruthTier.B_CONSTRUCTED
            assert item.constructed_invalidity == AXIS_INVALIDITY[item.axis]


def test_no_item_claims_tier_a_because_lean_was_never_run(built) -> None:
    items, _ = built
    assert all(item.tier is GroundTruthTier.B_CONSTRUCTED for item in items)
    assert LEAN_TIER_A_REPLAY["status"] == "DESIGNED_NOT_RUN"


# --------------------------------------------------------------------------- surface claims


def _negatives_by_axis(items):
    by_pair: dict[str, list] = {}
    for item in items:
        by_pair.setdefault(item.pair_id, []).append(item)
    grouped: dict[CorruptionAxis, list[tuple]] = {}
    for members in by_pair.values():
        positive = next(item for item in members if item.valid)
        negative = next(item for item in members if not item.valid)
        assert negative.axis is not None
        grouped.setdefault(negative.axis, []).append((positive, negative))
    return grouped


def test_each_axis_keeps_the_surface_promises_it_declares(built, steps: list[ProofStep]) -> None:
    items, _ = built
    recorded_successors = {step.state_after for step in steps}
    for axis, pairs in _negatives_by_axis(items).items():
        properties = AXIS_PROPERTIES[axis]
        for positive, negative in pairs:
            if properties.corrupts_action:
                assert negative.state_after == positive.state_after
                original, corrupted = positive.action, negative.action
            else:
                assert negative.action == positive.action
                original, corrupted = positive.state_after, negative.state_after
            assert original != corrupted
            if properties.preserves_token_multiset:
                assert token_multiset(original) == token_multiset(corrupted), axis
            if properties.preserves_length:
                assert len(original) == len(corrupted), axis
            if properties.permutes_within_axis:
                assert corrupted in recorded_successors, axis


def test_the_direction_axis_is_polarity_balanced(built) -> None:
    """The arrow is visible, so it must appear equally often under each label."""

    items, _ = built
    pairs = _negatives_by_axis(items).get(CorruptionAxis.WRONG_REWRITE_DIRECTION, [])
    assert pairs
    positives = sum(1 for positive, _ in pairs if "←" in positive.action)
    negatives = sum(1 for _, negative in pairs if "←" in negative.action)
    assert positives == negatives


def test_the_successor_axis_shows_only_real_same_proof_result_states(
    built, steps: list[ProofStep]
) -> None:
    """A derangement, not a sample: every shown result state is a recorded one from this proof."""

    items, _ = built
    recorded = {step.state_after for step in steps}
    pairs = _negatives_by_axis(items).get(CorruptionAxis.WRONG_SUCCESSOR, [])
    assert pairs
    for positive, negative in pairs:
        assert negative.state_after in recorded
        assert negative.state_after != positive.state_after


def test_successor_derangement_is_a_fixed_point_free_permutation(
    steps: list[ProofStep],
) -> None:
    """The property that makes every marginal statistic of the result state uninformative."""

    mapping = successor_derangement(steps)
    assert mapping
    for index, substitute in mapping.items():
        original = next(step for step in steps if step.step_index == index)
        assert substitute != original.state_after
    sources = sorted(
        next(step for step in steps if step.step_index == index).state_after for index in mapping
    )
    assert sorted(mapping.values()) == sources


def test_successor_derangement_of_a_single_step_proof_is_empty(steps: list[ProofStep]) -> None:
    assert successor_derangement(steps[:1]) == {}


# --------------------------------------------------------------------------- relabel reuse


def test_swap_identifiers_is_the_text_counterpart_of_relabel() -> None:
    expression = CanonicalExpression(
        "lean.application",
        (
            CanonicalExpression("lean.local_reference", value="a", sort="LeanTerm"),
            CanonicalExpression("lean.local_reference", value="b", sort="LeanTerm"),
        ),
        sort="LeanTerm",
    )
    swapped = relabel(expression, "a", "b")
    assert [child.value for child in swapped.args] == ["b", "a"]
    text = "exact f a b"
    assert swap_identifiers(text, "a", "b") == "exact f b a"
    assert token_multiset(text) == token_multiset(swap_identifiers(text, "a", "b"))
    assert len(text) == len(swap_identifiers(text, "a", "b"))


def test_swap_identifiers_respects_token_boundaries() -> None:
    assert swap_identifiers("exact ab a", "a", "b") == "exact ab b"
    assert swap_identifiers("h1 h2", "h1", "h1") == "h1 h2"


# --------------------------------------------------------------------------- discards


def test_a_refused_corruption_is_a_discard_not_a_guess(
    steps: list[ProofStep], index: PremiseIndex
) -> None:
    from random import Random

    starved = PremiseIndex(
        by_file={"Fixture/Test.lean": ("add_zero",)},
        all_names=("add_zero",),
        train_citation_frequency={"add_zero": 5},
    )
    surface = corrupt_wrong_premise(steps[0], steps, starved, Random(0), matched=True)
    assert isinstance(surface, Discard)
    assert surface.kind is DiscardKind.SURFACE
    assert surface.label == "surface:no_length_frequency_overlap_matched_donor"

    alone = corrupt_wrong_premise(steps[0], steps[:1], starved, Random(0), matched=True)
    assert isinstance(alone, Discard)
    assert alone.kind is DiscardKind.INVALIDITY
    assert alone.label == "invalidity:no_donor_with_a_distinct_final_component"


def test_every_attempt_is_either_a_candidate_or_a_counted_discard(built) -> None:
    _, report = built
    for axis in report.attempts:
        discarded = sum(
            count for label, count in report.discards.items() if label.startswith(f"{axis}|")
        )
        assert report.attempts[axis] == report.candidates[axis] + discarded


def test_discard_kinds_are_separated_so_the_honest_rate_is_visible(built) -> None:
    _, report = built
    for axis in report.attempts:
        assert report.eligible_attempts(axis) <= report.attempts[axis]
        rate = report.invalidity_discard_rate(axis)
        assert rate != rate or 0.0 <= rate <= 1.0


# --------------------------------------------------------------------------- splitting


def test_group_split_never_straddles_a_pair(built) -> None:
    items, _ = built
    train, heldout = group_split(items)
    assert len(train) + len(heldout) == len(items)
    train_pairs = {item.pair_id for item in train}
    heldout_pairs = {item.pair_id for item in heldout}
    assert not (train_pairs & heldout_pairs)


def test_per_axis_cap_is_respected(steps: list[ProofStep], index: PremiseIndex) -> None:
    items, report = build_family(group_proofs(steps), index, per_axis_cap=1)
    assert all(count <= 1 for count in report.accepted.values())
    assert len(items) == 2 * sum(report.accepted.values())
