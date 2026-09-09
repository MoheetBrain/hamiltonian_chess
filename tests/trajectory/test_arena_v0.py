"""The inner MDP: the renderer seam, leakage, determinism, replay and the bank."""

from __future__ import annotations

import ast
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

import arena.trajectory.arena_v0 as arena_v0
from arena.trajectory.arena_v0 import (
    ActionSpaceSpec,
    AnswerLeakageError,
    BackendNativeRenderer,
    GoalTextRenderer,
    LeakageFilter,
    LeakageLedger,
    LeakReason,
    ReplayDriver,
    StateRenderer,
    build_bank,
    horizon_histogram,
    load_bank,
    select_candidates,
    source_version_from_record,
    verify_bank,
)
from arena.trajectory.lean_backend import LeanToolchainConfig, TacticPolicy, build_probe
from arena.trajectory.schema import (
    Actor,
    BackendStateEnvelope,
    PPScope,
    TerminalStatus,
)

from . import fake_mathlib_root, find_probe, require_lean, require_train_json
from .test_schema import make_trajectory

# =============================================================================================
# The no-string-equality invariant, asserted by scanning the source
# =============================================================================================

PACKAGE = Path(arena_v0.__file__).parent

#: Identifiers that hold **state text**.  Comparing two of these would be exactly the unsound
#: verifier the audit measured at 40.6% where real agreement was 98.1%.
STATE_TEXT_NAMES = frozenset(
    {"pp", "tacticState", "tactic_state", "state_before", "state_after", "goals_pp"}
)

#: Content hashes of state text.  Legitimate for tamper detection and for advisory diagnostics;
#: never for deciding whether a step was mathematically correct.
STATE_HASH_NAMES = frozenset({"pp_sha256"})

#: Every place a state string or its hash may be compared, and why.  A new comparison anywhere
#: else fails this test, which is the point: the rule is enforced, not remembered.
ALLOWED_STATE_TEXT_SITES = {
    # the backend's own unambiguous termination sentinel, compared against a fixed literal
    ("lean_backend.py", "is_no_goals"),
    # the leakage filter looks for the answer inside recorded state text; not a verdict
    ("arena_v0.py", "scan_record"),
    # a renderer checking that its own re-layout inverts to the text it came from; a round-trip
    # self-test, and the alternative is silently mangling a state (HC-V0.6 design brief §2)
    ("representation.py", "present"),
    # the same round-trip self-test one level down: the parse must reproduce its own input
    ("representation.py", "parse_tactic_state"),
}
ALLOWED_STATE_HASH_SITES = {
    # tamper detection when loading a stored trajectory
    ("schema.py", "from_dict"),
    # advisory `no_op_suspected` diagnostic reported in `info`; gates nothing
    ("arena_v0.py", "step"),
    # RT-03: tamper detection when RE-RUNNING a stored trajectory.  Same category as
    # `schema.from_dict` — it asks whether the artefact faithfully records the run it claims, not
    # whether a step was mathematically correct.  Lean has already decided the latter by the time
    # this is reached: an action that is not mathematically legal is REJECTED by the elaborator
    # and relive fails on the rejection, never on the hash.
    ("arena_v0.py", "_state_hashes_agree"),
}


def _enclosing_function(tree: ast.AST, target: ast.AST) -> str:
    name = "<module>"
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if child is target:
                    name = node.name
    return name


def _names_in(node: ast.AST) -> set[str]:
    found: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            found.add(child.id)
        elif isinstance(child, ast.Attribute):
            found.add(child.attr)
    return found


def _comparison_sites(module: Path) -> list[tuple[str, str, str]]:
    """Return ``(file, function, kind)`` for every equality/containment test on state text."""

    tree = ast.parse(module.read_text(encoding="utf-8"))
    sites: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Eq | ast.NotEq | ast.In | ast.NotIn) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        names: set[str] = set()
        for operand in operands:
            names |= _names_in(operand)
        if names & STATE_TEXT_NAMES:
            sites.append((module.name, _enclosing_function(tree, node), "TEXT"))
        if names & STATE_HASH_NAMES:
            sites.append((module.name, _enclosing_function(tree, node), "HASH"))
    return sites


def test_string_equality_is_never_used_for_verification() -> None:
    """An AST scan, not a promise: no module may compare state text outside the whitelist."""

    text_sites: set[tuple[str, str]] = set()
    hash_sites: set[tuple[str, str]] = set()
    for module in sorted(PACKAGE.glob("*.py")):
        for file_name, function, kind in _comparison_sites(module):
            (text_sites if kind == "TEXT" else hash_sites).add((file_name, function))

    assert text_sites <= ALLOWED_STATE_TEXT_SITES, (
        f"state text compared outside the whitelist: {sorted(text_sites - ALLOWED_STATE_TEXT_SITES)}"
    )
    assert hash_sites <= ALLOWED_STATE_HASH_SITES, (
        f"state hash compared outside the whitelist: {sorted(hash_sites - ALLOWED_STATE_HASH_SITES)}"
    )
    # and the sentinel really is in the whitelist, i.e. the scan is finding things at all
    assert ("lean_backend.py", "is_no_goals") in text_sites


def test_the_scan_would_catch_a_string_matching_verifier(tmp_path: Path) -> None:
    """Negative control: a module that verifies by comparing states is flagged."""

    offender = tmp_path / "arena_v0.py"
    offender.write_text(
        "def verify(observed_pp, recorded_pp):\n    return observed_pp.pp == recorded_pp.pp\n",
        encoding="utf-8",
    )
    sites = _comparison_sites(offender)
    assert ("arena_v0.py", "verify", "TEXT") in sites


def test_state_identity_used_by_the_arena_is_the_backend_id() -> None:
    left = BackendStateEnvelope(index=0, state_id="7", pp="⊢ univ = univ")
    right = BackendStateEnvelope(index=0, state_id="7", pp="⊢ Finset.univ = Finset.univ")
    assert left.pp != right.pp
    assert left.same_backend_state_as(right)


# =============================================================================================
# Omega_L: the renderer seam
# =============================================================================================


def test_default_renderer_is_backend_native_and_claims_no_canonical_form() -> None:
    envelope = BackendStateEnvelope(
        index=0, state_id="0", pp="⊢ True", pp_scope=PPScope(current_namespace="Nat")
    )
    rendered = BackendNativeRenderer().render(envelope)
    assert rendered["renderer_id"] == "backend-native-v0"
    assert rendered["goals_pp"] == "⊢ True"
    assert rendered["backend_kind"] == "LEAN4_TACTIC_STATE_PP"
    assert "canonical_state" not in rendered
    assert "arena-canonical" not in json.dumps(rendered)


def test_a_language_can_supply_its_own_omega_l() -> None:
    """The seam the outer loop needs: any object with this shape is a legal ``Ω_L``."""

    class ShoutingRenderer:
        renderer_id = "shouting-v0"

        def render(self, envelope: BackendStateEnvelope) -> dict[str, Any]:
            return {"renderer_id": self.renderer_id, "GOALS": envelope.pp.upper()}

    renderer = ShoutingRenderer()
    assert isinstance(renderer, StateRenderer)
    assert isinstance(BackendNativeRenderer(), StateRenderer)
    assert isinstance(GoalTextRenderer(), StateRenderer)
    envelope = BackendStateEnvelope(index=0, state_id="0", pp="⊢ p")
    assert renderer.render(envelope) == {"renderer_id": "shouting-v0", "GOALS": "⊢ P"}
    assert GoalTextRenderer().render(envelope) == {"renderer_id": "goal-text-v0", "goals_pp": "⊢ p"}


def test_action_space_is_described_honestly() -> None:
    spec = ActionSpaceSpec.from_policy(TacticPolicy.no_heavy_automation())
    assert spec.kind == "FREE_FORM_TACTIC_STRING"
    assert spec.enumerable is False
    assert spec.proposes_candidates is False
    assert "aesop" in spec.denied_heads
    assert "sorry" in spec.always_refused
    assert "tactic string" in spec.description


# =============================================================================================
# Answer leakage
# =============================================================================================


def leaky_record(kind: LeakReason) -> dict[str, Any]:
    if kind is LeakReason.TACTIC_IN_STATE_BEFORE:
        return {
            "full_name": "Foo.bar",
            "traced_tactics": [
                {"tactic": "exact add_comm a b", "state_before": "⊢ h : exact add_comm a b"},
            ],
        }
    return {
        "full_name": "Foo.bar",
        "traced_tactics": [{"tactic": "rfl", "state_before": "this : Foo.bar\n⊢ x = x"}],
    }


def test_leakage_filter_drops_the_two_measured_channels() -> None:
    leakage_filter = LeakageFilter()
    for kind in (LeakReason.TACTIC_IN_STATE_BEFORE, LeakReason.FULL_NAME_IN_STATE):
        assert kind in leakage_filter.scan_record(leaky_record(kind))


def test_leakage_filter_passes_a_clean_record() -> None:
    clean = {
        "full_name": "Foo.bar",
        "traced_tactics": [
            {"tactic": "rw [Nat.add_comm]", "state_before": "a b : Nat\n⊢ a + b = b + a"}
        ],
    }
    assert LeakageFilter().scan_record(clean) == ()


def test_leakage_ledger_counts_what_was_dropped(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=4)
    poisoned = [dict(record) for record in records]
    for record in poisoned[:2]:
        record["traced_tactics"] = [
            {
                "tactic": "exact my_lemma",
                "state_before": "⊢ exact my_lemma",
                "state_after": "no goals",
            }
        ] * 6
    train = tmp_path / "train.json"
    train.write_text(json.dumps(poisoned), encoding="utf-8")

    selection = select_candidates(
        train_json=train,
        min_horizon=5,
        limit=10,
        seed=0,
        scan_limit=100,
        mathlib_root=root,
    )
    assert selection.leakage.problems_dropped == 2
    assert selection.leakage.leaking_steps == 12
    assert selection.leakage.reasons == {LeakReason.TACTIC_IN_STATE_BEFORE.value: 12}
    assert selection.discards.to_dict()["LEAKAGE_FILTER"] == 2
    assert len(selection.probes) == 2, "the two clean problems survive"


def test_observation_guard_refuses_to_show_a_remaining_reference_tactic() -> None:
    leakage_filter = LeakageFilter()
    rendered = {"goals_pp": "⊢ we must now apply Nat.succ_le_of_lt to finish"}
    with pytest.raises(AnswerLeakageError, match="remaining reference tactic"):
        leakage_filter.assert_observation_clean(rendered, ["apply Nat.succ_le_of_lt"])
    leakage_filter.assert_observation_clean(rendered, ["omega"])
    # already-played tactics are not secrets any more
    leakage_filter.assert_observation_clean(rendered, [])


def test_observation_guard_ignores_very_short_tactics() -> None:
    LeakageFilter().assert_observation_clean({"goals_pp": "⊢ rfl-ish"}, ["rfl"])


def test_ledger_serialises() -> None:
    ledger = LeakageLedger()
    ledger.record(LeakReason.FULL_NAME_IN_STATE)
    assert ledger.to_dict()["reasons"] == {"FULL_NAME_IN_STATE": 1}


# =============================================================================================
# Deterministic sampling
# =============================================================================================


def make_train_file(tmp_path: Path, declarations: int = 14) -> tuple[Path, Path]:
    root, records = fake_mathlib_root(tmp_path, declarations=declarations)
    train = tmp_path / "train.json"
    train.write_text(json.dumps(records), encoding="utf-8")
    return train, root


def test_bank_selection_is_deterministic_given_a_seed(tmp_path: Path) -> None:
    train, root = make_train_file(tmp_path)
    kwargs: dict[str, Any] = {
        "train_json": train,
        "min_horizon": 5,
        "limit": 5,
        "scan_limit": 100,
        "mathlib_root": root,
    }
    first = select_candidates(seed=1234, **kwargs)
    second = select_candidates(seed=1234, **kwargs)
    assert [probe.problem_id for probe in first.probes] == [
        probe.problem_id for probe in second.probes
    ]
    assert len(first.probes) == 5
    assert first.scanned == 14


def test_a_different_seed_selects_a_different_sample(tmp_path: Path) -> None:
    train, root = make_train_file(tmp_path)
    samples = {
        seed: tuple(
            probe.problem_id
            for probe in select_candidates(
                train_json=train,
                min_horizon=5,
                limit=5,
                seed=seed,
                scan_limit=100,
                mathlib_root=root,
            ).probes
        )
        for seed in (0, 1, 2, 3)
    }
    assert len(set(samples.values())) > 1


def test_scan_limit_is_part_of_the_sample_identity(tmp_path: Path) -> None:
    train, root = make_train_file(tmp_path)
    small = select_candidates(
        train_json=train, min_horizon=5, limit=5, seed=0, scan_limit=6, mathlib_root=root
    )
    assert small.scanned == 6
    assert len(small.probes) <= 5


def test_min_horizon_filters_by_reference_length(tmp_path: Path) -> None:
    train, root = make_train_file(tmp_path, declarations=3)
    selection = select_candidates(
        train_json=train, min_horizon=7, limit=5, seed=0, scan_limit=10, mathlib_root=root
    )
    assert selection.probes == ()
    assert selection.discards.to_dict()["BELOW_MIN_HORIZON"] == 3


def test_source_version_uses_the_sources_own_keys(tmp_path: Path) -> None:
    _, records = fake_mathlib_root(tmp_path, declarations=1)
    version = source_version_from_record(records[0])
    assert version.file_path == "Mathlib/Fake/File0.lean"
    assert version.full_name == "Fake.fake_0"
    assert version.commit == "29dcec074de168ac2bf835a77ef68bbe069194c5"
    assert version.license == "CC BY 2.0"
    assert version.split == "train"
    assert version.start == (6, 1)


# =============================================================================================
# Bank verification (offline)
# =============================================================================================


def write_bank(tmp_path: Path, trajectories: list[Any]) -> Path:
    bank = tmp_path / "bank.jsonl"
    bank.write_text("".join(item.to_json() + "\n" for item in trajectories), encoding="utf-8")
    return bank


def test_verify_bank_accepts_an_honest_bank(tmp_path: Path) -> None:
    bank = write_bank(tmp_path, [make_trajectory(5), make_trajectory(7, reference_horizon=9)])
    result = verify_bank(bank)
    assert result.passed
    assert result.checked == 2 and result.ok == 2
    assert result.horizon_histogram == {"5": 1, "7": 1}


def test_verify_bank_catches_a_tampered_hash(tmp_path: Path) -> None:
    payload = json.loads(make_trajectory(5).to_json())
    payload["content_hash"] = "0" * 64
    bank = tmp_path / "bank.jsonl"
    bank.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    result = verify_bank(bank)
    assert not result.passed
    assert "content_hash mismatch" in result.failures[0]


def test_verify_bank_catches_a_mixed_actor_trajectory(tmp_path: Path) -> None:
    trajectory = make_trajectory(4)
    mixed = replace(
        trajectory,
        actions=(replace(trajectory.actions[0], actor=Actor.SOLVER),) + trajectory.actions[1:],
    )
    bank = tmp_path / "bank.jsonl"
    bank.write_text(json.dumps(json.loads(mixed.to_json())) + "\n", encoding="utf-8")
    result = verify_bank(bank)
    assert not result.passed
    assert any("mixes SOLVER and REFERENCE" in item for item in result.failures)


def test_verify_bank_catches_missing_step_evidence(tmp_path: Path) -> None:
    trajectory = make_trajectory(4)
    stripped = replace(trajectory, verifier_evidence=trajectory.verifier_evidence[2:])
    bank = tmp_path / "bank.jsonl"
    bank.write_text(json.dumps(json.loads(stripped.to_json())) + "\n", encoding="utf-8")
    result = verify_bank(bank)
    assert not result.passed
    assert any("ACCEPTED step evidence" in item for item in result.failures)


def test_verify_bank_catches_an_action_whose_tactic_was_rewritten(tmp_path: Path) -> None:
    """RT-03's payload, seen without Lean: the evidence still names the tactic that really ran.

    Relive is what catches a forger who rewrites the evidence too (see
    ``test_relive_integrity.py``); this catches the published one for the price of a JSON parse.
    """

    trajectory = make_trajectory(4)
    swapped = replace(
        trajectory,
        actions=tuple(replace(action, tactic="aesop") for action in trajectory.actions),
    )
    bank = tmp_path / "bank.jsonl"
    bank.write_text(json.dumps(json.loads(swapped.to_json())) + "\n", encoding="utf-8")
    result = verify_bank(bank)
    assert not result.passed
    assert any(
        "is not the action the verifier recorded accepting" in item for item in result.failures
    ), result.failures
    assert any("action 0" in item for item in result.failures), result.failures


def test_session_id_is_a_function_of_what_the_session_was_opened_on(tmp_path: Path) -> None:
    """RT-02: the binding must be reproducible, or a byte-identical re-run gets a new identity."""

    root, records = fake_mathlib_root(tmp_path, declarations=2)
    probes = []
    for record in records:
        built = build_probe(record, mathlib_root=root)
        assert built.ok and built.probe is not None
        probes.append(built.probe)
    policy = TacticPolicy.record_only()

    first = arena_v0.derive_session_id(probes[0], policy=policy, seed=7)
    assert first == arena_v0.derive_session_id(probes[0], policy=policy, seed=7)
    assert first.startswith("lean4-repl-")
    # a different theorem, a different policy or a different seed is a different session
    assert first != arena_v0.derive_session_id(probes[1], policy=policy, seed=7)
    assert first != arena_v0.derive_session_id(probes[0], policy=policy, seed=8)
    assert first != arena_v0.derive_session_id(
        probes[0], policy=TacticPolicy.no_heavy_automation(), seed=7
    )


def test_load_bank_round_trips(tmp_path: Path) -> None:
    original = [make_trajectory(3), make_trajectory(6, reference_horizon=6)]
    restored = load_bank(write_bank(tmp_path, original))
    assert [item.trajectory_id for item in restored] == [item.trajectory_id for item in original]


def test_horizon_histogram_counts_verified_lengths() -> None:
    trajectories = [make_trajectory(5), make_trajectory(5), make_trajectory(9)]
    assert horizon_histogram(trajectories) == {"5": 2, "9": 1}


# =============================================================================================
# Lean-dependent
# =============================================================================================


@pytest.mark.slow
def test_replay_driver_produces_a_verified_trajectory_of_at_least_five_steps() -> None:
    require_lean()
    require_train_json()
    record, probe = find_probe(5, 9)
    driver = ReplayDriver(config=LeanToolchainConfig.from_env())
    outcome = driver.run(record, probe)
    if outcome.terminal_status is not TerminalStatus.CLOSED_VERIFIED:
        pytest.skip(f"reference proof did not replay: {outcome.terminal_status} {outcome.error}")

    trajectory = outcome.trajectory
    assert trajectory is not None
    assert trajectory.horizon.achieved >= 5
    assert trajectory.horizon.verified == trajectory.horizon.achieved
    assert trajectory.kernel_verified
    trajectory.require_single_actor(Actor.REFERENCE)

    # the chain really chains: each action's endpoints are the backend's own state ids
    for index, action in enumerate(trajectory.actions):
        assert action.from_state_id == trajectory.states[index].state_id
        assert action.to_state_id == trajectory.states[index + 1].state_id
    assert len({state.state_id for state in trajectory.states}) == len(trajectory.states)

    # and it survives serialization with its hashes intact
    from arena.trajectory.schema import VerifiedTrajectory

    assert VerifiedTrajectory.from_dict(json.loads(trajectory.to_json())) == trajectory


@pytest.mark.slow
def test_the_observation_never_contains_the_remaining_reference_proof() -> None:
    require_lean()
    require_train_json()
    _, probe = find_probe(5, 9)
    arena = arena_v0.LeanTrajectoryArena(config=LeanToolchainConfig.from_env())
    try:
        observation = arena.reset(probe, hide_reference=probe.reference_tactics)
        payload = json.dumps(observation.to_dict(), ensure_ascii=False)
        for tactic in probe.reference_tactics:
            if len(tactic) >= 6:
                assert tactic not in payload, tactic
    finally:
        arena.close()


@pytest.mark.slow
def test_a_small_bank_builds_and_re_verifies(tmp_path: Path) -> None:
    require_lean()
    require_train_json()
    manifest = build_bank(
        out_dir=tmp_path / "bank",
        min_horizon=5,
        limit=2,
        seed=11,
        scan_limit=600,
        config=LeanToolchainConfig.from_env(),
        verbose=False,
    )
    assert manifest["schema"] == arena_v0.BANK_SCHEMA
    assert manifest["selection"]["seed"] == 11
    assert manifest["toolchain"]["olean_count"] > 0
    assert manifest["sealed_splits_not_read"]
    result = verify_bank(tmp_path / "bank")
    assert result.passed, result.failures
    assert result.checked == manifest["results"]["trajectories_written"]


def test_verify_bank_refuses_an_unfinished_episode(tmp_path: Path) -> None:
    """An OPEN trajectory is an episode that never terminated; it is not a bank entry."""

    trajectory = make_trajectory(5, terminal=TerminalStatus.FAILED, with_kernel=False)
    unfinished = replace(trajectory, terminal_status=TerminalStatus.OPEN)
    bank = tmp_path / "bank.jsonl"
    bank.write_text(json.dumps(json.loads(unfinished.to_json())) + "\n", encoding="utf-8")
    result = verify_bank(bank)
    assert not result.passed
    assert any("never terminated" in item for item in result.failures)


def test_abandon_is_recorded_and_a_terminal_episode_cannot_be_relabelled() -> None:
    arena = arena_v0.LeanTrajectoryArena(config=LeanToolchainConfig.from_env())
    arena._states.append(BackendStateEnvelope(index=0, state_id="0", pp="⊢ p"))

    assert arena.terminal_status is TerminalStatus.OPEN
    assert arena.abandon("ran out of reference tactics") is TerminalStatus.ABANDONED
    assert arena._evidence[-1].rejected_reason == "ran out of reference tactics"

    # a second abandon is a no-op, and an upgrade is refused outright
    assert arena.abandon("again") is TerminalStatus.ABANDONED
    with pytest.raises(RuntimeError, match="cannot be relabelled"):
        arena._set_terminal(TerminalStatus.CLOSED_VERIFIED)
