"""Anchored real Lean states.

Two tiers, following this package's existing convention:

* everything that does not need Lean runs anywhere -- the prefix-segregation property, the
  leakage filters, the depth rule, determinism of selection, the content hash;
* everything that drives a real Lean process is ``@pytest.mark.slow`` and skips with the exact
  missing paths when the toolchain is absent.  There is no mock Lean here for the same reason
  there is none in ``test_lean_backend.py``: a mock kernel would verify nothing, and a mocked
  re-derivability check would prove nothing about re-derivability.

The built bank at ``artifacts/trajectory/hc_v0_6_anchor_bank.json`` is treated as a *fixture when
present*: the bank-wide properties (no anchor's Solver-visible payload contains oracle text; every
anchor has open goals; the content hash is stable) are asserted over the real artefact, and those
tests skip rather than fail on a machine that has not built it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from arena.trajectory.anchor import (
    ANCHOR_SCHEMA,
    DEFAULT_ANCHOR_BANK_RELPATH,
    Anchor,
    AnchorBank,
    AnchorCluster,
    AnchorDepthClass,
    AnchorDiscardReason,
    AnchorLedger,
    AnchorRecipe,
    AnchorRederivationError,
    AnchorSampling,
    SolverVisibleState,
    assert_no_oracle_leak,
    build_anchor_bank,
    count_open_goals,
    derive_theorem_anchors,
    open_anchor_session,
    scan_anchor_state,
    select_depths,
    solver_visible_payload,
    summarise_anchors,
    verify_rederivability,
)
from arena.trajectory.arena_v0 import (
    AnswerLeakageError,
    LeakageFilter,
    LeakReason,
    select_candidates,
)
from arena.trajectory.lean_backend import LeanToolchainConfig, SealedSplitError, TacticPolicy
from arena.trajectory.schema import Actor, PPScope

from . import fake_mathlib_root, find_probe, require_lean, require_train_json

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILT_BANK = REPO_ROOT / "artifacts" / DEFAULT_ANCHOR_BANK_RELPATH


# =============================================================================================
# Fixtures: a hand-built anchor, no Lean required
# =============================================================================================


def make_anchor(
    *,
    prefix: Sequence[str] = ("intro hypothesis_name", "rcases witness_pair"),
    reference: Sequence[str] | None = None,
    goals_pp: str = "n : Nat\nh : 0 < n\n⊢ n ≠ 0",
    full_name: str = "Nat.pos_iff_ne_zero_example",
    file_path: str = "Mathlib/Data/Nat/Basic.lean",
) -> Anchor:
    tactics = tuple(reference if reference is not None else (*prefix, "exact ne_of_gt_witness"))
    recipe = AnchorRecipe(
        problem_id=f"{file_path}::{full_name}",
        theorem_full_name=full_name,
        file_path=file_path,
        prefix_tactics=tuple(prefix),
        reference_tactics=tactics,
        decl_start=(10, 1),
        decl_end=(13, 20),
        mathlib_commit="29dcec074de168ac2bf835a77ef68bbe069194c5",
        mathlib_url="https://github.com/leanprover-community/mathlib4",
        toolchain="leanprover/lean4:v4.10.0-rc1",
        lean_version_string="Lean (version 4.10.0-rc1)",
        probe_source_sha256="0" * 64,
    )
    visible = SolverVisibleState(
        backend_kind="LEAN4_TACTIC_STATE_PP",
        goals_pp=goals_pp,
        n_goals=count_open_goals(goals_pp),
        pp_scope=PPScope(current_namespace="Nat", open_declarations=("Finset",)),
    )
    return Anchor(
        oracle=recipe,
        solver_visible=visible,
        sampling=AnchorSampling(
            prefix_length=len(prefix),
            observed_trace_length=len(tactics),
            depth_class=AnchorDepthClass.INITIAL if not prefix else AnchorDepthClass.MID_PROOF,
        ),
        cluster=AnchorCluster(
            file_path=file_path, theorem_full_name=full_name, problem_id=recipe.problem_id
        ),
        reelaboration_key="LEAN4_TACTIC_STATE_PP|abcd|deadbeef",
        goal_digest="deadbeef",
        scope_digest="abcd",
        normalization="goal-text-nfc-linewise-rstrip-v0",
        derivation_state_id="7",
    )


# =============================================================================================
# The prefix is segregated from what the Solver sees
# =============================================================================================


def test_solver_visible_payload_contains_no_prefix_tactic_text() -> None:
    """The property the whole design rests on, asserted on the payload's bytes."""

    anchor = make_anchor()
    payload = solver_visible_payload(anchor)
    text = json.dumps(payload, ensure_ascii=False)
    for tactic in anchor.oracle.prefix_tactics:
        assert tactic not in text, tactic
    for tactic in anchor.oracle.remaining_reference:
        assert tactic not in text, tactic
    assert anchor.cluster.theorem_full_name not in text
    assert anchor.cluster.file_path not in text


def test_solver_visible_payload_carries_only_the_goal_state_and_the_join_key() -> None:
    payload = solver_visible_payload(make_anchor())
    assert set(payload) == {
        "anchor_id",
        "backend_kind",
        "goals_pp",
        "n_goals",
        "pp_scope",
        "pp_sha256",
    }
    assert payload["anchor_id"].startswith("anchor:")


def test_the_oracle_block_really_does_hold_the_prefix() -> None:
    """The segregation is a separation, not a deletion: the recipe must still be there."""

    anchor = make_anchor()
    oracle = anchor.oracle.to_dict()
    assert oracle["prefix_tactics"] == ["intro hypothesis_name", "rcases witness_pair"]
    assert oracle["actor"] == Actor.REFERENCE.value
    assert anchor.oracle.remaining_reference == ("exact ne_of_gt_witness",)


def test_the_tripwire_fires_when_a_prefix_tactic_reaches_the_payload() -> None:
    leaky = make_anchor(goals_pp="n : Nat\n⊢ after rcases witness_pair we are done")
    with pytest.raises(AnswerLeakageError, match="oracle material"):
        assert_no_oracle_leak(solver_visible_payload(leaky), leaky)


def test_the_tripwire_fires_when_the_next_reference_tactic_reaches_the_payload() -> None:
    leaky = make_anchor(goals_pp="⊢ finish with exact ne_of_gt_witness")
    with pytest.raises(AnswerLeakageError, match="oracle material"):
        assert_no_oracle_leak(solver_visible_payload(leaky), leaky)


def test_the_tripwire_fires_when_the_theorem_name_reaches_the_payload() -> None:
    leaky = make_anchor(goals_pp="⊢ this is Nat.pos_iff_ne_zero_example restated")
    with pytest.raises(AnswerLeakageError, match="oracle material"):
        assert_no_oracle_leak(solver_visible_payload(leaky), leaky)


def test_a_clean_anchor_passes_the_tripwire() -> None:
    anchor = make_anchor()
    assert_no_oracle_leak(solver_visible_payload(anchor), anchor)


# =============================================================================================
# Leakage filtering reuses the measured criteria
# =============================================================================================


def test_scan_anchor_state_names_each_criterion_separately() -> None:
    filter_ = LeakageFilter()
    payload = {"goals_pp": "⊢ apply Nat.succ_le_of_lt and we are done"}
    assert scan_anchor_state(
        filter_,
        payload=payload,
        full_name="Nat.other",
        remaining_reference=["apply Nat.succ_le_of_lt"],
        prefix_tactics=[],
    ) == (LeakReason.TACTIC_IN_STATE_BEFORE.value,)
    assert scan_anchor_state(
        filter_,
        payload={"goals_pp": "⊢ Nat.other holds"},
        full_name="Nat.other",
        remaining_reference=[],
        prefix_tactics=[],
    ) == (LeakReason.FULL_NAME_IN_STATE.value,)
    assert scan_anchor_state(
        filter_,
        payload={"goals_pp": "⊢ rcases witness_pair happened"},
        full_name="Nat.other",
        remaining_reference=[],
        prefix_tactics=["rcases witness_pair"],
    ) == (AnchorDiscardReason.LEAKS_PREFIX_TACTIC_IN_STATE.value,)


def test_scan_anchor_state_inherits_the_short_tactic_exemption() -> None:
    """``rfl`` inside goal text is a coincidence, not a leak -- the measured criterion's rule."""

    assert (
        scan_anchor_state(
            LeakageFilter(),
            payload={"goals_pp": "⊢ rfl-ish"},
            full_name="Nat.other",
            remaining_reference=["rfl"],
            prefix_tactics=["rfl"],
        )
        == ()
    )


def test_a_clean_state_produces_no_reasons() -> None:
    assert (
        scan_anchor_state(
            LeakageFilter(),
            payload={"goals_pp": "n : Nat\n⊢ n = n"},
            full_name="Nat.example",
            remaining_reference=["exact congrArg something"],
            prefix_tactics=["intro n_hypothesis"],
        )
        == ()
    )


def test_the_ledger_counts_drops_by_reason() -> None:
    ledger = AnchorLedger()
    ledger.record(AnchorDiscardReason.NO_OPEN_GOALS, 3)
    ledger.record(AnchorDiscardReason.LEAKS_FULL_NAME_IN_STATE)
    other = AnchorLedger()
    other.record(AnchorDiscardReason.NO_OPEN_GOALS)
    ledger.merge(other)
    assert ledger.to_dict() == {"LEAKS_FULL_NAME_IN_STATE": 1, "NO_OPEN_GOALS": 4}
    assert ledger.total() == 5


# =============================================================================================
# Depth selection: varied, recorded, and a fixed rule
# =============================================================================================


def test_depth_zero_is_always_kept_when_it_is_open() -> None:
    assert select_depths([0, 1, 2, 3, 4, 5], max_per_theorem=3)[0] == 0


def test_depth_selection_spans_the_proof_rather_than_clustering_early() -> None:
    kept = select_depths(list(range(11)), max_per_theorem=3)
    assert kept == (0, 1, 10), kept
    assert len(set(kept)) == 3


def test_depth_selection_keeps_everything_when_there_is_room() -> None:
    assert select_depths([0, 1, 2], max_per_theorem=5) == (0, 1, 2)


def test_depth_selection_is_a_pure_function() -> None:
    depths = [0, 2, 3, 5, 8, 13]
    assert select_depths(depths, max_per_theorem=4) == select_depths(depths, max_per_theorem=4)


def test_depth_selection_handles_a_chain_with_no_open_root() -> None:
    """A theorem whose root closed immediately still contributes its open mid-proof states."""

    assert select_depths([2, 3], max_per_theorem=2) == (2, 3)
    assert select_depths([], max_per_theorem=3) == ()
    assert select_depths([0, 1], max_per_theorem=0) == ()


def test_sampling_block_keeps_the_horizon_vocabulary_distinct() -> None:
    """Manual 6.30-6.34 / 17.6: a prefix length is a sampling proxy and nothing else."""

    payload = make_anchor().sampling.to_dict()
    assert payload["prefix_length"] == 2
    assert payload["observed_trace_length"] == 3
    assert payload["episode_length"] == 0, "an anchor is a state, not an episode"
    assert payload["minimal_proof_length"] == "UNKNOWN"
    assert payload["dependency_depth"] == "UNKNOWN"
    assert payload["kernel_step_count"] == 0
    assert "SAMPLING PROXIES" in payload["note"]


def test_depth_class_distinguishes_the_initial_state() -> None:
    assert make_anchor(prefix=()).sampling.depth_class is AnchorDepthClass.INITIAL
    assert make_anchor().sampling.depth_class is AnchorDepthClass.MID_PROOF


# =============================================================================================
# Identity, serialisation and the evaluation-universe hash
# =============================================================================================


def test_anchor_id_is_a_function_of_the_recipe_not_of_the_derived_state() -> None:
    """A re-derivation that lands somewhere else must look like a FAILURE, not a new anchor."""

    anchor = make_anchor()
    moved = Anchor(
        oracle=anchor.oracle,
        solver_visible=anchor.solver_visible,
        sampling=anchor.sampling,
        cluster=anchor.cluster,
        reelaboration_key="LEAN4_TACTIC_STATE_PP|abcd|something-else",
        goal_digest="something-else",
        scope_digest="abcd",
        normalization=anchor.normalization,
        derivation_state_id="99",
    )
    assert moved.anchor_id == anchor.anchor_id
    assert moved.reelaboration_key != anchor.reelaboration_key


def test_a_different_prefix_is_a_different_anchor() -> None:
    assert make_anchor(prefix=("intro hypothesis_name",)).anchor_id != make_anchor().anchor_id


def test_anchor_round_trips_through_json() -> None:
    anchor = make_anchor()
    restored = Anchor.from_dict(json.loads(json.dumps(anchor.to_dict())))
    assert restored.anchor_id == anchor.anchor_id
    assert restored.oracle.prefix_tactics == anchor.oracle.prefix_tactics
    assert restored.solver_visible.goals_pp == anchor.solver_visible.goals_pp
    assert restored.content_core == anchor.content_core


def make_bank(anchors: Sequence[Anchor], **overrides: Any) -> AnchorBank:
    payload: dict[str, Any] = {
        "anchors": tuple(anchors),
        "selection": {"seed": 0, "scan_limit": 10},
        "toolchain": {"toolchain": "leanprover/lean4:v4.10.0-rc1", "olean_count": 5680},
        "leakage": {},
        "discards": {},
        "rederivation": {"matched": 1, "anchors_checked": 1},
        "cost": {"total_s": 1.0},
        "generated_utc": "2026-09-08T00:00:00+00:00",
    }
    payload.update(overrides)
    return AnchorBank(**payload)


def test_the_content_hash_excludes_wall_clock_and_measured_cost() -> None:
    anchors = [make_anchor(), make_anchor(prefix=())]
    first = make_bank(anchors)
    second = make_bank(
        anchors,
        generated_utc="2027-01-01T12:00:00+00:00",
        cost={"total_s": 999.0},
        rederivation={"matched": 0, "anchors_checked": 2},
    )
    assert first.content_hash == second.content_hash


def test_the_content_hash_changes_when_an_anchor_changes() -> None:
    base = make_bank([make_anchor()])
    changed = make_bank([make_anchor(goals_pp="n : Nat\n⊢ n = n")])
    assert base.content_hash != changed.content_hash


def test_the_content_hash_changes_when_the_selection_changes() -> None:
    anchors = [make_anchor()]
    assert (
        make_bank(anchors).content_hash
        != make_bank(anchors, selection={"seed": 1, "scan_limit": 10}).content_hash
    )


def test_the_content_hash_excludes_the_live_sid() -> None:
    """A ``sid`` names a process that no longer exists; it cannot be part of an identity."""

    anchor = make_anchor()
    relabelled = Anchor(
        oracle=anchor.oracle,
        solver_visible=anchor.solver_visible,
        sampling=anchor.sampling,
        cluster=anchor.cluster,
        reelaboration_key=anchor.reelaboration_key,
        goal_digest=anchor.goal_digest,
        scope_digest=anchor.scope_digest,
        normalization=anchor.normalization,
        derivation_state_id="4242",
    )
    assert make_bank([anchor]).content_hash == make_bank([relabelled]).content_hash


def test_bank_round_trips_and_groups_by_theorem() -> None:
    bank = make_bank([make_anchor(), make_anchor(prefix=()), make_anchor(full_name="Other.thm")])
    restored = AnchorBank.from_dict(json.loads(json.dumps(bank.to_dict())))
    assert restored.content_hash == bank.content_hash
    grouped = restored.by_theorem()
    assert len(grouped) == 2
    assert all(len({a.oracle.problem_id for a in group}) == 1 for group in grouped.values())


def test_bank_statistics_cluster_on_the_file() -> None:
    stats = summarise_anchors(
        [
            make_anchor(),
            make_anchor(prefix=()),
            make_anchor(full_name="Other.thm", file_path="Mathlib/Order/Basic.lean"),
        ]
    )
    assert stats.anchors == 3
    assert stats.distinct_theorems == 2
    assert stats.distinct_files == 2
    assert stats.depth_class_counts == {"INITIAL": 1, "MID_PROOF": 2}
    assert stats.prefix_length_histogram == {"0": 1, "2": 2}


def test_bank_exposes_only_solver_visible_payloads_to_an_assay() -> None:
    bank = make_bank([make_anchor(), make_anchor(prefix=())])
    payloads = bank.solver_visible_payloads()
    text = json.dumps(payloads, ensure_ascii=False)
    assert "intro hypothesis_name" not in text
    assert "Nat.pos_iff_ne_zero_example" not in text
    assert len(payloads) == 2


def test_bank_write_and_load_round_trip(tmp_path: Path) -> None:
    from arena.storage.artifacts import ArtifactStore

    bank = make_bank([make_anchor()])
    stored = bank.write(store=ArtifactStore(tmp_path), relative=Path("anchors.json"))
    assert stored.path.exists()
    reloaded = AnchorBank.load(stored.path)
    assert reloaded.content_hash == bank.content_hash
    assert json.loads(stored.path.read_text(encoding="utf-8"))["schema"] == ANCHOR_SCHEMA


# =============================================================================================
# The re-derivation API refuses what it cannot honour
# =============================================================================================


def test_open_anchor_session_refuses_a_mixed_theorem_group() -> None:
    with (
        pytest.raises(ValueError, match="ONE session on ONE theorem"),
        open_anchor_session([make_anchor(), make_anchor(full_name="Other.thm")]),
    ):
        pass


def test_open_anchor_session_refuses_an_empty_group() -> None:
    with pytest.raises(ValueError, match="at least one anchor"), open_anchor_session([]):
        pass


def test_recipe_rebuilds_the_leandojo_record_from_the_sources_own_keys() -> None:
    record = make_anchor().oracle.leandojo_record()
    assert record["file_path"] == "Mathlib/Data/Nat/Basic.lean"
    assert record["full_name"] == "Nat.pos_iff_ne_zero_example"
    assert record["start"] == [10, 1]
    assert [step["tactic"] for step in record["traced_tactics"]] == [
        "intro hypothesis_name",
        "rcases witness_pair",
        "exact ne_of_gt_witness",
    ]


def test_a_recipe_that_cannot_be_rebuilt_says_so_loudly(tmp_path: Path) -> None:
    with pytest.raises(AnchorRederivationError, match="cannot rebuild the probe"):
        make_anchor().oracle.build(mathlib_root=tmp_path / "not-a-checkout")


def test_rederivability_on_an_empty_bank_is_reported_not_divided_by_zero() -> None:
    report = verify_rederivability([])
    assert report.anchors_checked == 0
    assert report.rate == 0.0
    assert report.to_dict()["theorems_checked"] == 0


# =============================================================================================
# Selection is deterministic and reads only the development split
# =============================================================================================


def make_train_file(tmp_path: Path, declarations: int = 12) -> tuple[Path, Path]:
    root, records = fake_mathlib_root(tmp_path, declarations=declarations)
    train = tmp_path / "train.json"
    train.write_text(json.dumps(records), encoding="utf-8")
    return train, root


def test_anchor_selection_is_the_same_pure_function_the_bank_builder_uses(
    tmp_path: Path,
) -> None:
    train, root = make_train_file(tmp_path)
    kwargs: dict[str, Any] = {
        "train_json": train,
        "min_horizon": 3,
        "limit": 5,
        "scan_limit": 100,
        "mathlib_root": root,
    }
    first = select_candidates(seed=7, **kwargs)
    second = select_candidates(seed=7, **kwargs)
    assert [probe.problem_id for probe in first.probes] == [
        probe.problem_id for probe in second.probes
    ]
    assert [probe.problem_id for probe in select_candidates(seed=8, **kwargs).probes] != [
        probe.problem_id for probe in first.probes
    ]


def test_building_a_bank_from_a_sealed_split_is_refused_before_any_io(tmp_path: Path) -> None:
    sealed = tmp_path / "random" / "val.json"
    sealed.parent.mkdir(parents=True)
    with pytest.raises(SealedSplitError):
        build_anchor_bank(train_json=sealed, verbose=False)


def test_count_open_goals_matches_the_backends_own_sentinel() -> None:
    assert count_open_goals("no goals") == 0
    assert count_open_goals("") == 0
    assert count_open_goals("n : Nat\n⊢ n = n") == 1
    assert count_open_goals("case a\n⊢ p\n\ncase b\n⊢ q") == 2


# =============================================================================================
# The built artefact: bank-wide properties, skipped when it has not been built
# =============================================================================================


def load_built_bank() -> AnchorBank:
    if not BUILT_BANK.exists():
        pytest.skip(
            f"the anchored bank has not been built at {BUILT_BANK}; run "
            "`python -m arena.trajectory.anchor`"
        )
    return AnchorBank.load(BUILT_BANK)


def test_built_bank_has_no_oracle_text_in_any_solver_visible_payload() -> None:
    """The design brief's segregation requirement, checked over every anchor that exists."""

    bank = load_built_bank()
    for anchor in bank.anchors:
        payload = solver_visible_payload(anchor)
        assert_no_oracle_leak(payload, anchor)
        text = json.dumps(payload, ensure_ascii=False)
        for tactic in anchor.oracle.prefix_tactics:
            if len(tactic.strip()) >= LeakageFilter().min_runtime_secret_len:
                assert tactic.strip() not in text, (anchor.anchor_id, tactic)


def test_built_bank_anchors_all_have_open_goals() -> None:
    for anchor in load_built_bank().anchors:
        assert anchor.solver_visible.n_goals >= 1, anchor.anchor_id
        assert anchor.solver_visible.goals_pp.strip() not in {"", "no goals"}


def test_built_bank_records_prefix_depth_and_recorded_proof_length_on_every_anchor() -> None:
    for anchor in load_built_bank().anchors:
        assert anchor.sampling.prefix_length >= 0
        assert anchor.sampling.observed_trace_length >= anchor.sampling.prefix_length
        assert anchor.sampling.to_dict()["minimal_proof_length"] == "UNKNOWN"


def test_built_bank_contains_depth_zero_and_mid_proof_anchors() -> None:
    stats = load_built_bank().stats
    assert stats.depth_class_counts.get("INITIAL", 0) > 0
    assert stats.depth_class_counts.get("MID_PROOF", 0) > 0
    assert len(stats.prefix_length_histogram) > 1, "prefix depth must be varied"


def test_built_bank_anchor_ids_are_unique() -> None:
    anchors = load_built_bank().anchors
    assert len({anchor.anchor_id for anchor in anchors}) == len(anchors)


def test_built_bank_content_hash_is_reproducible_from_the_file() -> None:
    bank = load_built_bank()
    stored = json.loads(BUILT_BANK.read_text(encoding="utf-8"))["content_hash"]
    assert bank.content_hash == stored


def test_built_bank_spans_many_theorems_and_files() -> None:
    stats = load_built_bank().stats
    assert stats.distinct_theorems >= 2
    assert stats.distinct_files >= 2
    assert stats.anchors >= stats.distinct_theorems


# =============================================================================================
# Lean-dependent: marked slow, skipped cleanly when the toolchain is absent
# =============================================================================================


@pytest.mark.slow
def test_live_derivation_produces_open_anchors_at_varied_depths() -> None:
    report = require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    result = derive_theorem_anchors(record, probe, report=report, max_anchors_per_theorem=3)
    assert result.anchors, result.error
    assert result.prefix_steps_accepted >= 1
    depths = {anchor.sampling.prefix_length for anchor in result.anchors}
    assert 0 in depths, "the theorem's initial state must be anchorable"
    for anchor in result.anchors:
        assert anchor.solver_visible.n_goals >= 1
        assert anchor.reelaboration_key
        assert (
            anchor.oracle.prefix_tactics == probe.reference_tactics[: anchor.sampling.prefix_length]
        )
        assert_no_oracle_leak(solver_visible_payload(anchor), anchor)


@pytest.mark.slow
def test_an_anchor_is_rederivable_in_a_second_independent_session() -> None:
    """The anchoring claim itself: same recipe, fresh process, same re-elaboration key."""

    report = require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    first = derive_theorem_anchors(record, probe, report=report, max_anchors_per_theorem=3)
    assert first.anchors, first.error

    rederived = verify_rederivability(first.anchors, every=1)
    assert rederived.anchors_checked == len(first.anchors), rederived.to_dict()
    assert rederived.mismatched == (), rederived.to_dict()
    assert rederived.rate == 1.0


@pytest.mark.slow
def test_the_open_session_branches_many_tactics_from_one_anchor_without_restarting() -> None:
    """The efficiency the assay depends on: one startup, many candidate tactics."""

    report = require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    derived = derive_theorem_anchors(record, probe, report=report, max_anchors_per_theorem=3)
    assert derived.anchors, derived.error

    with open_anchor_session(derived.anchors) as live:
        assert live.live, live.missing
        target = live.live[0]
        for tactic in ("this_is_not_a_tactic", "skip", "exact trivial"):
            result = live.step(target.anchor_id, tactic)
            assert result.from_state_id == target.live_state_id
        # every anchor is still addressable after the failures: nothing was restarted
        for item in live.live:
            assert live.session.state_text(item.live_state_id) is not None
        payload = live.solver_payload(target.anchor_id)
        assert payload["goals_pp"] == target.anchor.solver_visible.goals_pp


@pytest.mark.slow
def test_a_live_anchor_reports_the_same_state_the_bank_stored() -> None:
    report = require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    derived = derive_theorem_anchors(record, probe, report=report, max_anchors_per_theorem=2)
    assert derived.anchors, derived.error
    with open_anchor_session(derived.anchors) as live:
        for item in live.live:
            assert item.matched, (item.anchor_id, item.identity.reelaboration_key)
            assert item.identity.goal_digest == item.anchor.goal_digest
            assert item.identity.scope_digest == item.anchor.scope_digest


@pytest.mark.slow
def test_open_anchor_session_refuses_a_checkout_that_no_longer_matches() -> None:
    report = require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    derived = derive_theorem_anchors(record, probe, report=report, max_anchors_per_theorem=1)
    assert derived.anchors, derived.error
    anchor = derived.anchors[0]
    tampered = Anchor(
        oracle=AnchorRecipe(
            **{**anchor.oracle.__getstate__()[1], "probe_source_sha256": "f" * 64}  # type: ignore[dict-item]
        )
        if False
        else AnchorRecipe(
            problem_id=anchor.oracle.problem_id,
            theorem_full_name=anchor.oracle.theorem_full_name,
            file_path=anchor.oracle.file_path,
            prefix_tactics=anchor.oracle.prefix_tactics,
            reference_tactics=anchor.oracle.reference_tactics,
            decl_start=anchor.oracle.decl_start,
            decl_end=anchor.oracle.decl_end,
            mathlib_commit=anchor.oracle.mathlib_commit,
            mathlib_url=anchor.oracle.mathlib_url,
            toolchain=anchor.oracle.toolchain,
            lean_version_string=anchor.oracle.lean_version_string,
            probe_source_sha256="f" * 64,
            max_heartbeats=anchor.oracle.max_heartbeats,
        ),
        solver_visible=anchor.solver_visible,
        sampling=anchor.sampling,
        cluster=anchor.cluster,
        reelaboration_key=anchor.reelaboration_key,
        goal_digest=anchor.goal_digest,
        scope_digest=anchor.scope_digest,
        normalization=anchor.normalization,
    )
    with (
        pytest.raises(AnchorRederivationError, match="no longer produces the probe"),
        open_anchor_session([tampered]),
    ):
        pass


@pytest.mark.slow
def test_a_small_live_bank_builds_end_to_end(tmp_path: Path) -> None:
    from arena.storage.artifacts import ArtifactStore

    require_lean()
    require_train_json()
    bank = build_anchor_bank(
        theorem_limit=2,
        scan_limit=2000,
        min_reference_length=3,
        max_anchors_per_theorem=2,
        rederive_every=1,
        config=LeanToolchainConfig.from_env(),
        policy=TacticPolicy.record_only(),
        verbose=False,
    )
    assert bank.anchors
    assert bank.rederivation["anchors_checked"] == len(bank.anchors)
    assert bank.rederivation["rate"] == 1.0, bank.rederivation
    assert bank.stats.distinct_theorems >= 1
    assert bank.cost["seconds_per_anchor_derivation"] > 0
    stored = bank.write(store=ArtifactStore(tmp_path), relative=Path("small.json"))
    assert AnchorBank.load(stored.path).content_hash == bank.content_hash
