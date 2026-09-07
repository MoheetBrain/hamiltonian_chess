"""Route B budget manifests: nesting, quality, hashing, and the legacy-split defect."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from arena.canonical.schema import GoldStatus
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.prepare_matched_data import (
    ARMS,
    seeded_stratified_split,
    stratified_split,
)
from arena.training.render_dataset import render_matched_datasets, write_jsonl
from arena.training.route_b_data import (
    DEFAULT_BUDGETS,
    BudgetManifest,
    DataSlice,
    ManifestError,
    ManifestVerificationError,
    SplitMode,
    assert_nested_ids,
    build_budget_manifest,
    dataset_hash,
    filter_indices_by_quality,
    verify_manifest,
)

WORLD = 676

#: The exact head of the frozen Tier-2 train split.  Observed from the live splitter, not
#: copied from prose: if the legacy split ever moves, the historical artefact stops being
#: reproducible and this test is the thing that says so.
LEGACY_TRAIN_HEAD = (60, 8, 164, 372, 424)

#: Maximum GOLD-pure train budget for the 676-task world, after dev=48 and fresh=48 are
#: held out first.  Asserted rather than assumed, because every budget above it is a design
#: that cannot be run at GOLD purity.
GOLD_POOL_676 = 424


@pytest.fixture(scope="module")
def gold_manifest() -> BudgetManifest:
    return build_budget_manifest(world_size=WORLD, min_quality=GoldStatus.GOLD)


@pytest.fixture(scope="module")
def world_tasks() -> tuple[object, ...]:
    return generate_tasks(total=WORLD, seed=0)


# --------------------------------------------------------------------------------------
# DEFECT A: the legacy splitter's seed is inert.  Pin it; refuse to let the fix regress.
# --------------------------------------------------------------------------------------


def test_legacy_split_is_pinned_to_its_historical_indices(world_tasks) -> None:
    train, dev, fresh = stratified_split(world_tasks, 600, 48, 48)
    assert tuple(train[:5]) == LEGACY_TRAIN_HEAD
    # The 676-world cannot supply 600 train examples once dev and fresh are held out.
    assert (len(train), len(dev), len(fresh)) == (580, 48, 48)


def test_legacy_split_seed_is_inert_and_that_is_documented(world_tasks) -> None:
    """DEFECT A, pinned deliberately: the legacy path must keep ignoring its seed."""

    assert stratified_split(world_tasks, 224, 48, 48, 0) == stratified_split(
        world_tasks, 224, 48, 48, 999
    )
    assert "INERT" in (stratified_split.__doc__ or "")


def test_seeded_split_is_not_degenerate(world_tasks) -> None:
    """The fix for DEFECT A must actually use its seed, for every bucket."""

    first = seeded_stratified_split(world_tasks, 224, 48, 48, seed=1)
    second = seeded_stratified_split(world_tasks, 224, 48, 48, seed=2)
    for name, left, right in zip(("train", "dev", "fresh"), first, second, strict=True):
        assert left != right, f"seeded split returned identical {name} for two seeds"
    # And it must differ from the frozen legacy path, or it is the legacy path in disguise.
    assert first[0] != stratified_split(world_tasks, 224, 48, 48)[0]


def test_seeded_split_is_reproducible_and_disjoint(world_tasks) -> None:
    train, dev, fresh = seeded_stratified_split(world_tasks, 224, 48, 48, seed=7)
    assert (train, dev, fresh) == seeded_stratified_split(world_tasks, 224, 48, 48, seed=7)
    assert not set(train) & set(dev)
    assert not set(train) & set(fresh)
    assert not set(dev) & set(fresh)
    assert (len(dev), len(fresh)) == (48, 48)


def test_seeded_split_preserves_the_nesting_property(world_tasks) -> None:
    smaller, _, _ = seeded_stratified_split(world_tasks, 32, 48, 48, seed=3)
    larger, _, _ = seeded_stratified_split(world_tasks, 128, 48, 48, seed=3)
    assert larger[: len(smaller)] == smaller


# --------------------------------------------------------------------------------------
# Nesting, checked at runtime rather than assumed from the construction.
# --------------------------------------------------------------------------------------


def test_manifest_budgets_are_nested(gold_manifest: BudgetManifest) -> None:
    assert gold_manifest.budgets == DEFAULT_BUDGETS
    previous: tuple[str, ...] = ()
    for budget in gold_manifest.budgets:
        current = gold_manifest.slice_for(budget).canonical_ids
        assert len(current) == budget
        assert current[: len(previous)] == previous
        assert set(previous) <= set(current)
        previous = current


def test_assert_nested_ids_accepts_a_valid_ladder() -> None:
    assert_nested_ids([(2, ("a", "b")), (4, ("a", "b", "c", "d"))])


@pytest.mark.parametrize(
    ("slices", "reason"),
    [
        ([(2, ("a", "b")), (4, ("b", "a", "c", "d"))], "reordered prefix"),
        ([(2, ("a", "b")), (4, ("c", "d", "e", "f"))], "disjoint sets"),
        ([(4, ("a", "b", "c", "d")), (2, ("a", "b", "c", "d", "e"))], "shrinking"),
        ([(2, ("a", "a")), (4, ("a", "a", "b", "c"))], "repeated id"),
        ([(2, ("a", "b")), (2, ("a", "b"))], "non-increasing budgets"),
        ([], "no slices at all"),
    ],
)
def test_assert_nested_ids_fails_closed(slices, reason: str) -> None:
    with pytest.raises(ManifestError):
        assert_nested_ids(slices)


def test_build_refuses_when_nesting_would_break(monkeypatch: pytest.MonkeyPatch) -> None:
    """The builder must verify nesting, not infer it from how it happens to build slices.

    Today the ladder is prefixes of one ordered pool, so nesting is true by construction.
    That is exactly the situation in which a runtime guard looks redundant and gets deleted.
    Here the slice builder is replaced by one that computes each budget independently -- the
    shape a future refactor would take -- and the manifest must refuse rather than emit it.
    """

    import arena.training.route_b_data as module

    real_build_slice = module._build_slice

    def independent(name, budget, indices, tasks, datasets, arms):
        # A per-budget slice that no longer extends the previous one.
        reordered = tuple(reversed(indices)) if budget == 32 else tuple(indices)
        return real_build_slice(name, budget, reordered, tasks, datasets, arms)

    monkeypatch.setattr(module, "_build_slice", independent)
    with pytest.raises(ManifestError, match="nesting broken"):
        build_budget_manifest(world_size=WORLD, budgets=(16, 32), min_quality=GoldStatus.GOLD)


# --------------------------------------------------------------------------------------
# Quality filter and pool exhaustion.
# --------------------------------------------------------------------------------------


def test_gold_filter_admits_only_gold(gold_manifest: BudgetManifest, world_tasks) -> None:
    for budget in gold_manifest.budgets:
        for index in gold_manifest.slice_for(budget).indices:
            assert world_tasks[index].trajectory.quality is GoldStatus.GOLD


def test_silver_floor_admits_gold_and_silver_but_not_reject(world_tasks) -> None:
    train, _, _ = stratified_split(world_tasks, WORLD, 48, 48)
    kept = filter_indices_by_quality(world_tasks, train, GoldStatus.SILVER)
    qualities = {world_tasks[i].trajectory.quality for i in kept}
    assert GoldStatus.REJECT not in qualities
    assert qualities <= {GoldStatus.GOLD, GoldStatus.SILVER}
    assert len(kept) > len(filter_indices_by_quality(world_tasks, train, GoldStatus.GOLD))


def test_no_filter_is_the_historical_behaviour(world_tasks) -> None:
    train, _, _ = stratified_split(world_tasks, WORLD, 48, 48)
    assert filter_indices_by_quality(world_tasks, train, None) == tuple(train)
    assert GoldStatus.REJECT in {world_tasks[i].trajectory.quality for i in train}


def test_filter_preserves_order(world_tasks) -> None:
    train, _, _ = stratified_split(world_tasks, WORLD, 48, 48)
    kept = filter_indices_by_quality(world_tasks, train, GoldStatus.GOLD)
    assert list(kept) == [i for i in train if i in set(kept)]


def test_gold_pool_for_the_676_world_is_exactly_424(gold_manifest: BudgetManifest) -> None:
    assert gold_manifest.available_pool == GOLD_POOL_676


def test_budget_beyond_the_gold_pool_is_refused() -> None:
    with pytest.raises(ManifestError, match="exceeds the available pool") as error:
        build_budget_manifest(
            world_size=WORLD, budgets=(16, GOLD_POOL_676 + 1), min_quality=GoldStatus.GOLD
        )
    message = str(error.value)
    assert str(GOLD_POOL_676) in message
    assert "GOLD" in message


def test_the_same_budget_is_allowed_without_the_quality_filter() -> None:
    manifest = build_budget_manifest(
        world_size=WORLD, budgets=(16, GOLD_POOL_676 + 1), min_quality=None
    )
    assert manifest.available_pool > GOLD_POOL_676


# --------------------------------------------------------------------------------------
# Hashing: one scheme, stable, and sensitive to content.
# --------------------------------------------------------------------------------------


def test_dataset_hash_is_the_write_jsonl_scheme(tmp_path: Path) -> None:
    """There must be exactly one dataset hashing scheme in this codebase."""

    from arena.languages.registry import LANGUAGE_REGISTRY

    tasks = generate_tasks(total=26, seed=0)
    datasets = render_matched_datasets(
        tuple(task.trajectory for task in tasks),
        tuple(LANGUAGE_REGISTRY.get(arm) for arm in ARMS[:2]),
    )
    examples = datasets[ARMS[0]][:10]
    assert dataset_hash(examples) == write_jsonl(tmp_path / "shard.jsonl", examples)


def test_manifest_hash_is_stable_across_runs(gold_manifest: BudgetManifest) -> None:
    again = build_budget_manifest(world_size=WORLD, min_quality=GoldStatus.GOLD)
    assert again.manifest_hash == gold_manifest.manifest_hash
    assert again.to_dict() == gold_manifest.to_dict()


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_quality": None},
        {"min_quality": GoldStatus.SILVER},
        {"budgets": (16, 32, 64)},
        {"budgets": (8, 32, 64, 128, 224)},
        {"arms": ARMS[:3]},
        {"generator_seed": 1},
        {"dev_size": 24},
        {"fresh_size": 24},
        {"split_mode": SplitMode.SEEDED, "split_seed": 5},
    ],
)
def test_manifest_hash_changes_when_content_changes(
    gold_manifest: BudgetManifest, overrides: dict[str, object]
) -> None:
    kwargs: dict[str, object] = {"world_size": WORLD, "min_quality": GoldStatus.GOLD}
    kwargs.update(overrides)
    changed = build_budget_manifest(**kwargs)  # type: ignore[arg-type]
    assert changed.manifest_hash != gold_manifest.manifest_hash


def test_manifest_hash_changes_with_the_world_size() -> None:
    kwargs = {"budgets": (16, 32), "min_quality": GoldStatus.GOLD}
    small = build_budget_manifest(world_size=338, **kwargs)
    large = build_budget_manifest(world_size=WORLD, **kwargs)
    assert small.manifest_hash != large.manifest_hash
    assert small.available_pool < large.available_pool


def test_seeded_manifests_differ_by_seed() -> None:
    kwargs = {
        "world_size": WORLD,
        "budgets": (16, 32),
        "min_quality": GoldStatus.GOLD,
        "split_mode": SplitMode.SEEDED,
    }
    first = build_budget_manifest(split_seed=1, **kwargs)
    second = build_budget_manifest(split_seed=2, **kwargs)
    assert first.manifest_hash != second.manifest_hash
    assert first.slice_for(16).canonical_ids != second.slice_for(16).canonical_ids


def test_manifest_hash_excludes_the_git_sha(gold_manifest: BudgetManifest) -> None:
    """A commit that changes nothing a model sees must not change the dataset identity."""

    moved = dataclasses.replace(gold_manifest, arena_git_sha="0" * 40)
    assert moved.identity_payload() == gold_manifest.identity_payload()
    verify_manifest(moved)


# --------------------------------------------------------------------------------------
# Provenance and verification.
# --------------------------------------------------------------------------------------


def test_manifest_records_provenance(gold_manifest: BudgetManifest) -> None:
    assert gold_manifest.world_size == WORLD
    assert gold_manifest.generator_seed == 0
    assert gold_manifest.split_mode is SplitMode.LEGACY_DETERMINISTIC
    assert gold_manifest.min_quality is GoldStatus.GOLD
    assert gold_manifest.arm_ids == tuple(ARMS)
    assert gold_manifest.schema_version.startswith("arena-route-b-manifest-")
    assert gold_manifest.token_proxy_units == "characters_not_tokens"
    for arm in gold_manifest.arms:
        assert arm.genome_hash and arm.candidate_hash
    sha = gold_manifest.arena_git_sha
    assert sha is None or len(sha) == 40


def test_train_dev_and_fresh_are_disjoint(gold_manifest: BudgetManifest) -> None:
    train = set(gold_manifest.slice_for(gold_manifest.budgets[-1]).canonical_ids)
    dev = set(gold_manifest.dev.canonical_ids)
    fresh = set(gold_manifest.fresh.canonical_ids)
    assert not train & dev
    assert not train & fresh
    assert not dev & fresh
    assert len(dev) == 48
    assert len(fresh) == 48


def test_every_arm_gets_a_distinct_hash_over_identical_examples(
    gold_manifest: BudgetManifest,
) -> None:
    slice_16 = gold_manifest.slice_for(16)
    digests = [digest for _, digest in slice_16.arm_dataset_hashes]
    assert len(set(digests)) == len(ARMS)
    assert slice_16.hash_for(ARMS[0]) != slice_16.hash_for(ARMS[1])


def test_verify_manifest_round_trips_through_json(gold_manifest: BudgetManifest) -> None:
    revived = BudgetManifest.from_dict(json.loads(json.dumps(gold_manifest.to_dict())))
    assert revived == gold_manifest
    assert verify_manifest(revived).manifest_hash == gold_manifest.manifest_hash


def test_verify_manifest_detects_a_tampered_hash(gold_manifest: BudgetManifest) -> None:
    tampered = dataclasses.replace(gold_manifest, manifest_hash="0" * 64)
    with pytest.raises(ManifestVerificationError, match="manifest hash mismatch"):
        verify_manifest(tampered)


def test_verify_manifest_detects_tampered_indices(gold_manifest: BudgetManifest) -> None:
    original = gold_manifest.slice_for(16)
    swapped = dataclasses.replace(original, indices=tuple(reversed(original.indices)))
    tampered = dataclasses.replace(
        gold_manifest,
        train_slices=(swapped, *gold_manifest.train_slices[1:]),
    )
    with pytest.raises(ManifestVerificationError, match="indices do not re-derive"):
        verify_manifest(tampered)


def test_verify_manifest_detects_tampered_dataset_hashes(
    gold_manifest: BudgetManifest,
) -> None:
    original = gold_manifest.slice_for(16)
    forged = tuple((arm, "0" * 64) for arm, _ in original.arm_dataset_hashes)
    tampered = dataclasses.replace(
        gold_manifest,
        train_slices=(
            dataclasses.replace(original, arm_dataset_hashes=forged),
            *gold_manifest.train_slices[1:],
        ),
    )
    with pytest.raises(ManifestVerificationError, match="dataset hashes do not re-derive"):
        verify_manifest(tampered)


def test_verify_manifest_refuses_a_foreign_schema(gold_manifest: BudgetManifest) -> None:
    alien = dataclasses.replace(gold_manifest, schema_version="arena-route-b-manifest-v9")
    with pytest.raises(ManifestVerificationError, match="schema"):
        verify_manifest(alien)


def test_verify_manifest_reports_an_undeliverable_design(
    gold_manifest: BudgetManifest,
) -> None:
    impossible = dataclasses.replace(gold_manifest, budgets=(16, 9999))
    with pytest.raises(ManifestVerificationError, match="could not be re-derived"):
        verify_manifest(impossible)


def test_data_slice_hash_lookup_rejects_an_unknown_arm(gold_manifest: BudgetManifest) -> None:
    with pytest.raises(KeyError):
        gold_manifest.slice_for(16).hash_for("L9_NOT_AN_ARM")


def test_slice_for_rejects_an_unknown_budget(gold_manifest: BudgetManifest) -> None:
    with pytest.raises(KeyError):
        gold_manifest.slice_for(17)


# --------------------------------------------------------------------------------------
# Design-level refusals.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"budgets": ()},
        {"budgets": (16, 16)},
        {"budgets": (0, 16)},
        {"budgets": (-4, 16)},
        {"arms": ("L2_SEXPR",)},
        {"arms": ("L2_SEXPR", "L2_SEXPR")},
        {"arms": ("L2_SEXPR", "L9_NOT_AN_ARM")},
        {"world_size": 0},
        {"dev_size": -1},
    ],
)
def test_build_budget_manifest_refuses_a_broken_design(kwargs: dict[str, object]) -> None:
    with pytest.raises(ManifestError):
        build_budget_manifest(
            world_size=kwargs.pop("world_size", 130),  # type: ignore[arg-type]
            budgets=kwargs.pop("budgets", (8, 16)),  # type: ignore[arg-type]
            min_quality=GoldStatus.GOLD,
            **kwargs,  # type: ignore[arg-type]
        )


def test_dev_and_fresh_larger_than_the_world_are_refused() -> None:
    with pytest.raises(ManifestError, match="cannot supply"):
        build_budget_manifest(world_size=26, budgets=(4,), dev_size=100, fresh_size=100)


def test_data_slice_json_round_trip(gold_manifest: BudgetManifest) -> None:
    original = gold_manifest.slice_for(32)
    assert DataSlice.from_dict(json.loads(json.dumps(original.to_dict()))) == original


# --------------------------------------------------------------------------------------
# prepare_matched_data CLI: every addition is opt-in, and the default stays historical.
# --------------------------------------------------------------------------------------

#: The exact top-level key set the Tier-2 sprint's matched_next_action.json carried.  A
#: default invocation must still produce precisely these keys and nothing more: the sprint's
#: consumers read this file positionally in places, and a "harmless" extra key is a change to
#: a historical artefact.
HISTORICAL_PAYLOAD_KEYS = frozenset(
    {
        "world_size",
        "seed",
        "arms",
        "split_sizes",
        "domains",
        "splits",
        "token_proxy_mean_input_chars",
    }
)

SMALL_WORLD = ["--world", "130", "--train", "40", "--dev", "12", "--fresh", "12"]


def run_cli(out: Path, *extra: str) -> dict:
    from arena.training.prepare_matched_data import main

    assert main([*SMALL_WORLD, "--out", str(out), *extra]) == 0
    return json.loads((out / "matched_next_action.json").read_text(encoding="utf-8"))


def test_default_invocation_keeps_the_historical_key_set(tmp_path: Path) -> None:
    payload = run_cli(tmp_path / "a")
    assert set(payload) == HISTORICAL_PAYLOAD_KEYS


def test_default_invocation_is_byte_stable(tmp_path: Path) -> None:
    run_cli(tmp_path / "a")
    run_cli(tmp_path / "b")
    first = (tmp_path / "a" / "matched_next_action.json").read_bytes()
    second = (tmp_path / "b" / "matched_next_action.json").read_bytes()
    assert first == second


def test_default_invocation_trains_on_every_quality(tmp_path: Path) -> None:
    """The historical behaviour, stated so a later quality default cannot slip in silently."""

    payload = run_cli(tmp_path / "a")
    tasks = generate_tasks(total=130, seed=0)
    train_ix, _, _ = stratified_split(tasks, 40, 12, 12)
    assert payload["split_sizes"]["train"] == len(train_ix)
    assert GoldStatus.GOLD in {tasks[i].trajectory.quality for i in train_ix}


def test_manifest_flag_emits_a_verifiable_manifest(tmp_path: Path) -> None:
    out = tmp_path / "a"
    manifest_path = tmp_path / "manifests" / "route_b.json"
    payload = run_cli(
        out,
        "--manifest-out",
        str(manifest_path),
        "--budgets",
        "8,16,32",
        "--min-quality",
        "GOLD",
    )
    manifest = BudgetManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    assert manifest.budgets == (8, 16, 32)
    assert manifest.min_quality is GoldStatus.GOLD
    assert payload["manifest_hash"] == manifest.manifest_hash
    verify_manifest(manifest)


def test_extended_output_states_the_token_proxy_units(tmp_path: Path) -> None:
    payload = run_cli(tmp_path / "a", "--min-quality", "GOLD")
    assert payload["token_proxy_units"] == "characters_not_tokens"
    assert "CHARACTERS, not tokens" in payload["token_proxy_note"]
    assert "token_proxy_mean_input_chars" in payload  # name unchanged, as required


def test_min_quality_flag_filters_the_train_split(tmp_path: Path) -> None:
    payload = run_cli(tmp_path / "a", "--min-quality", "GOLD")
    tasks = generate_tasks(total=130, seed=0)
    train_ix, _, _ = stratified_split(tasks, 40, 12, 12)
    gold = filter_indices_by_quality(tasks, train_ix, GoldStatus.GOLD)
    assert payload["split_sizes"]["train"] == len(gold)
    assert payload["min_quality"] == "GOLD"
    canonical = {item["canonical_id"] for item in payload["splits"][ARMS[0]]["train"]}
    assert canonical == {tasks[i].trajectory.trajectory_id for i in gold}


def test_seeded_split_mode_changes_the_emitted_split(tmp_path: Path) -> None:
    legacy = run_cli(tmp_path / "a")
    seeded = run_cli(tmp_path / "b", "--split-mode", "seeded")
    assert seeded["split_mode"] == SplitMode.SEEDED.value
    assert [item["canonical_id"] for item in seeded["splits"][ARMS[0]]["train"]] != [
        item["canonical_id"] for item in legacy["splits"][ARMS[0]]["train"]
    ]


def test_an_impossible_manifest_stops_the_cli(tmp_path: Path) -> None:
    from arena.training.prepare_matched_data import main

    with pytest.raises(SystemExit, match="budget manifest refused"):
        main(
            [
                *SMALL_WORLD,
                "--out",
                str(tmp_path / "a"),
                "--manifest-out",
                str(tmp_path / "m.json"),
                "--budgets",
                "8,9999",
                "--min-quality",
                "GOLD",
            ]
        )


def test_quality_floor_applies_to_held_out_slices_in_every_split_mode() -> None:
    """The quality floor must gate dev and fresh, not only train.

    Regression guard for a real defect: the floor was applied to the train indices alone,
    so under ``SEEDED`` the evaluation slices silently admitted sub-GOLD trajectories --
    measured on the 676-task world at seed 0 as 12 of 48 dev and 15 of 48 fresh items.
    The primary endpoint would then have been scored partly on trajectories the world
    itself marks unsound, in a way no recorded artefact would reveal.

    ``LEGACY_DETERMINISTIC`` was already GOLD-pure by accident of its ordering; this test
    pins that too, so the legacy path cannot regress unnoticed either.
    """

    tasks = generate_tasks(total=676, seed=0)
    quality = {task.trajectory.trajectory_id: task.trajectory.quality for task in tasks}

    for split_mode in (SplitMode.LEGACY_DETERMINISTIC, SplitMode.SEEDED):
        for split_seed in (0, 7):
            manifest = build_budget_manifest(
                world_size=676,
                budgets=(16, 224),
                arms=("L0_STRUCTURED_ENGLISH", "L3_JSON_AST"),
                min_quality=GoldStatus.GOLD,
                split_mode=split_mode,
                split_seed=split_seed,
                dev_size=48,
                fresh_size=48,
            )
            slices = (
                ("train", manifest.train_slices[-1]),
                ("dev", manifest.dev),
                ("fresh", manifest.fresh),
            )
            for name, data_slice in slices:
                grades = [quality[cid] for cid in data_slice.canonical_ids]
                offenders = [g for g in grades if g is not GoldStatus.GOLD]
                assert not offenders, (
                    f"{split_mode.value} seed={split_seed}: {name} holds "
                    f"{len(offenders)} sub-GOLD trajectories"
                )
            # The floor must not be satisfied by quietly shrinking the held-out sets.
            assert len(manifest.dev.canonical_ids) == 48
            assert len(manifest.fresh.canonical_ids) == 48
