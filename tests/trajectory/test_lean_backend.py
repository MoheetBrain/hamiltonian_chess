"""The truth kernel.  Pure tests run anywhere; Lean tests are marked slow and skip cleanly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arena.trajectory import lean_backend
from arena.trajectory.lean_backend import (
    ALWAYS_REFUSED,
    HEAVY_AUTOMATION,
    SEALED_SPLIT_PATHS,
    DiscardLedger,
    LeanReplSession,
    LeanToolchainConfig,
    ProbeDiscardReason,
    SealedSplitError,
    StepOutcome,
    TacticDecision,
    TacticPolicy,
    ToolchainMissingError,
    assert_not_sealed,
    build_probe,
    check_toolchain,
    extract_pp_scope,
    is_no_goals,
    iter_leandojo_records,
    require_toolchain,
    summarise_tactic_heads,
    verify_closed_script,
)

from . import fake_mathlib_root, find_probe, require_lean, require_train_json

# =============================================================================================
# Pure: no Lean needed
# =============================================================================================


def test_missing_toolchain_names_the_exact_paths() -> None:
    config = LeanToolchainConfig(
        mathlib_root=Path("/definitely/not/here/mathlib4"),
        lean_bin=Path("/definitely/not/here/bin/lean"),
        lake_bin=Path("/definitely/not/here/bin/lake"),
    )
    report = check_toolchain(config)
    assert not report.available
    joined = report.describe()
    assert "/definitely/not/here/bin/lean" in joined
    assert "/definitely/not/here/mathlib4" in joined
    with pytest.raises(ToolchainMissingError) as excinfo:
        require_toolchain(config)
    assert "/definitely/not/here/mathlib4" in str(excinfo.value)


def test_a_source_only_checkout_is_reported_as_unbuilt(tmp_path: Path) -> None:
    """The trap the audit names: two checkouts of one commit, only one of them built."""

    root = tmp_path / "mathlib4"
    (root / ".lake" / "build" / "lib").mkdir(parents=True)
    lean = tmp_path / "lean"
    lean.write_text("#!/bin/sh\n", encoding="utf-8")
    lake = tmp_path / "lake"
    lake.write_text("#!/bin/sh\n", encoding="utf-8")
    report = check_toolchain(LeanToolchainConfig(mathlib_root=root, lean_bin=lean, lake_bin=lake))
    assert not report.available
    assert any("Lean4Repl.olean not built" in item for item in report.missing)
    assert any("Mathlib.olean not built" in item for item in report.missing)


# -- tactic policy ---------------------------------------------------------------------------


def test_default_policy_records_and_restricts_nothing() -> None:
    policy = TacticPolicy.record_only()
    for tactic in ("aesop", "simp [foo]", "omega", "exact?", "rw [bar]"):
        assert policy.classify(tactic)[0] is TacticDecision.ALLOWED, tactic
    assert policy.denied_heads == frozenset()
    assert policy.allowed_heads is None


def test_heavy_automation_can_be_excluded_by_parameter() -> None:
    policy = TacticPolicy.no_heavy_automation()
    for tactic in ("aesop", "omega", "decide", "norm_num", "exact?", "simp?"):
        decision, reason = policy.classify(tactic)
        assert decision is TacticDecision.DENIED_BY_POLICY, tactic
        assert "deny-list" in reason
    assert policy.classify("rw [Nat.add_comm]")[0] is TacticDecision.ALLOWED
    assert policy.denied_heads >= HEAVY_AUTOMATION


def test_an_allow_list_excludes_everything_else() -> None:
    policy = TacticPolicy(name="rw_only", allowed_heads=frozenset({"rw", "intro"}))
    assert policy.classify("rw [h]")[0] is TacticDecision.ALLOWED
    assert policy.classify("intro x")[0] is TacticDecision.ALLOWED
    decision, reason = policy.classify("simp")
    assert decision is TacticDecision.DENIED_BY_POLICY
    assert "allow-list" in reason


def test_sorry_is_refused_under_every_policy() -> None:
    for policy in (
        TacticPolicy.record_only(),
        TacticPolicy.no_heavy_automation(),
        TacticPolicy(name="permissive", allowed_heads=None),
    ):
        for tactic in ("sorry", "  sorry ", "exact sorry", "admit", "refine ⟨sorry, sorry⟩"):
            decision, reason = policy.classify(tactic)
            assert decision is TacticDecision.REFUSED_UNSOUND, (policy.name, tactic)
            assert "refused" in reason
    assert "sorry" in ALWAYS_REFUSED


def test_a_lemma_whose_name_merely_contains_sorry_is_not_refused() -> None:
    assert TacticPolicy.record_only().classify("exact sorry_free_lemma")[0] is (
        TacticDecision.ALLOWED
    )


def test_policy_id_is_stable_and_distinguishes_policies() -> None:
    assert TacticPolicy.record_only().policy_id == TacticPolicy.record_only().policy_id
    assert TacticPolicy.record_only().policy_id != TacticPolicy.no_heavy_automation().policy_id


def test_tactic_heads_are_summarised_for_the_automation_report() -> None:
    counts = summarise_tactic_heads(["simp [a]", "simp", "rw [h]"], TacticPolicy.record_only())
    assert counts == {"simp": 2, "rw": 1}


# -- termination sentinel --------------------------------------------------------------------


def test_no_goals_is_the_only_state_string_comparison() -> None:
    assert is_no_goals("no goals")
    assert is_no_goals("  no goals\n")
    assert not is_no_goals("⊢ False")
    assert not is_no_goals("no goals to prove")


# -- sealed splits ---------------------------------------------------------------------------


@pytest.mark.parametrize("sealed", SEALED_SPLIT_PATHS)
def test_sealed_splits_are_refused(sealed: str) -> None:
    with pytest.raises(SealedSplitError, match="SEALED"):
        assert_not_sealed(Path("/data/leandojo_benchmark_4") / sealed)


def test_the_development_split_is_allowed() -> None:
    assert_not_sealed(Path("/data/leandojo_benchmark_4/random/train.json"))


# -- streaming reader ------------------------------------------------------------------------


def test_streaming_reader_yields_every_record(tmp_path: Path) -> None:
    records = [{"full_name": f"thm_{index}", "traced_tactics": []} for index in range(25)]
    path = tmp_path / "random" / "train.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(records), encoding="utf-8")
    assert [item["full_name"] for item in iter_leandojo_records(path)] == [
        f"thm_{index}" for index in range(25)
    ]
    assert len(list(iter_leandojo_records(path, limit=4))) == 4


def test_streaming_reader_handles_a_pretty_printed_array(tmp_path: Path) -> None:
    path = tmp_path / "train.json"
    path.write_text(json.dumps([{"a": 1}, {"a": 2}], indent=2), encoding="utf-8")
    assert [item["a"] for item in iter_leandojo_records(path)] == [1, 2]


# -- probe construction ----------------------------------------------------------------------


def test_probe_hides_the_theorem_from_itself(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    built = build_probe(records[0], mathlib_root=root, min_reference_horizon=1)
    assert built.ok and built.probe is not None
    probe = built.probe
    assert probe.probe_name == "probe_Fake_fake_0"
    source = probe.repl_source()
    assert source.startswith("import Lean4Repl\n")
    assert "theorem probe_Fake_fake_0" in source
    assert "lean_dojo_repl" in source
    # the original declaration is not in the prefix, so `exact Fake.fake_0` cannot close it
    assert "theorem fake_0" not in source


def test_probe_records_the_pretty_printer_scope(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    probe = build_probe(records[0], mathlib_root=root, min_reference_horizon=1).probe
    assert probe is not None
    assert probe.pp_scope.current_namespace == "Fake"
    assert "Nat" in probe.pp_scope.open_declarations


def test_closed_script_appends_the_kernel_check(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    probe = build_probe(records[0], mathlib_root=root, min_reference_horizon=1).probe
    assert probe is not None
    script = probe.closed_script_source(["intro h", "exact h"])
    assert "import Lean4Repl" not in script
    assert script.rstrip().endswith("#print axioms probe_Fake_fake_0")
    assert "  intro h\n  exact h" in script


def test_extract_pp_scope_closes_namespaces() -> None:
    scope = extract_pp_scope(
        ["namespace A", "open Foo Bar", "namespace B", "end B", "open scoped Baz"]
    )
    assert scope.current_namespace == "A"
    assert scope.open_declarations == ("Foo", "Bar", "Baz")


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"traced_tactics": []}, ProbeDiscardReason.NO_TACTICS),
        ({"file_path": "Mathlib/Missing.lean"}, ProbeDiscardReason.FILE_NOT_FOUND),
        ({"start": [1, 1]}, ProbeDiscardReason.DECL_OUT_OF_RANGE),
        ({"start": [9999, 1], "end": [10000, 1]}, ProbeDiscardReason.DECL_OUT_OF_RANGE),
    ],
)
def test_probe_discards_are_typed(
    tmp_path: Path, mutation: dict[str, object], reason: ProbeDiscardReason
) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    record = dict(records[0])
    record.update(mutation)
    built = build_probe(record, mathlib_root=root, min_reference_horizon=1)
    assert not built.ok
    assert built.discard_reason is reason


def test_probe_discards_horizons_and_multiline_and_banned_tactics(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    record = records[0]
    assert (
        build_probe(record, mathlib_root=root, min_reference_horizon=99).discard_reason
        is ProbeDiscardReason.BELOW_MIN_HORIZON
    )
    assert (
        build_probe(
            record, mathlib_root=root, min_reference_horizon=1, max_reference_horizon=2
        ).discard_reason
        is ProbeDiscardReason.ABOVE_MAX_HORIZON
    )
    multiline = dict(record)
    multiline["traced_tactics"] = [{"tactic": "intro x\n  exact x", "state_before": ""}]
    assert (
        build_probe(multiline, mathlib_root=root, min_reference_horizon=1).discard_reason
        is ProbeDiscardReason.MULTILINE_TACTIC
    )
    automated = dict(record)
    automated["traced_tactics"] = [{"tactic": "aesop", "state_before": ""}]
    assert (
        build_probe(
            automated,
            mathlib_root=root,
            policy=TacticPolicy.no_heavy_automation(),
            min_reference_horizon=1,
        ).discard_reason
        is ProbeDiscardReason.POLICY_BANNED_TACTIC
    )


def test_discard_ledger_counts_and_merges() -> None:
    left = DiscardLedger()
    left.record(ProbeDiscardReason.NO_TACTICS)
    left.record(ProbeDiscardReason.NO_TACTICS)
    right = DiscardLedger()
    right.record("LEAKAGE_FILTER", 3)
    left.merge(right)
    assert left.to_dict() == {"LEAKAGE_FILTER": 3, "NO_TACTICS": 2}
    assert left.total() == 5


def test_a_session_will_not_start_without_a_toolchain(tmp_path: Path) -> None:
    root, records = fake_mathlib_root(tmp_path, declarations=1)
    probe = build_probe(records[0], mathlib_root=root, min_reference_horizon=1).probe
    assert probe is not None
    config = LeanToolchainConfig(
        mathlib_root=root, lean_bin=tmp_path / "nope", lake_bin=tmp_path / "nope"
    )
    with pytest.raises(ToolchainMissingError):
        LeanReplSession(probe, config=config).start()


# =============================================================================================
# Lean-dependent: marked slow, skipped cleanly when the toolchain is absent
# =============================================================================================


@pytest.mark.slow
def test_toolchain_is_the_named_build() -> None:
    report = require_lean()
    assert "4.10.0-rc1" in report.lean_version_string
    assert report.toolchain == "leanprover/lean4:v4.10.0-rc1"
    assert (report.mathlib_root / ".lake" / "build" / "lib" / "Lean4Repl.olean").exists()


@pytest.mark.slow
def test_live_session_steps_branches_and_rejects() -> None:
    require_lean()
    require_train_json()
    _, probe = find_probe(4, 8)
    config = LeanToolchainConfig.from_env()

    with LeanReplSession(probe, config=config) as session:
        root = session.root_state_id
        assert session.state_text(root)
        assert session.startup_wall_s > 0

        # 1. drive the reference proof
        current = root
        accepted: list[str] = []
        for tactic in probe.reference_tactics:
            result = session.step(current, tactic)
            assert result.outcome is StepOutcome.OK, (tactic, result.error)
            assert result.to_state_id is not None and result.to_state_id != current
            current = result.to_state_id
            accepted.append(tactic)
            if result.closed:
                break
        assert accepted, "no tactic was accepted"

        # 2. branching back to an earlier sid works, and re-applying gives a NEW state
        back = session.branch(root)
        assert back.ok and back.to_state_id == root
        assert session.branch_log == [root]
        replayed = session.step(root, probe.reference_tactics[0])
        assert replayed.outcome is StepOutcome.OK
        assert replayed.to_state_id not in {root, None}

        # 3. a bogus tactic is a typed error carrying Lean's own reason, not a crash
        bogus = session.step(root, "exact Nat.zero")
        assert bogus.outcome is StepOutcome.TACTIC_ERROR
        assert bogus.error and bogus.to_state_id is None
        assert session.alive, "one bad tactic must not kill the session"

        # 4. an unknown state id is typed, not an exception
        unknown = session.step("99999", "rfl")
        assert unknown.outcome is StepOutcome.UNKNOWN_STATE_ID

        # 5. every attempt, including the rejected ones, is in the log
        outcomes = [item.outcome for item in session.step_log]
        assert StepOutcome.TACTIC_ERROR in outcomes
        assert StepOutcome.UNKNOWN_STATE_ID in outcomes


@pytest.mark.slow
def test_sorry_is_refused_by_the_policy_and_by_the_repl_itself(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Defence in depth: remove the client-side guard and Lean still refuses."""

    require_lean()
    require_train_json()
    _, probe = find_probe(4, 8)
    config = LeanToolchainConfig.from_env()

    with LeanReplSession(probe, config=config) as session:
        refused = session.step(session.root_state_id, "sorry")
        assert refused.outcome is StepOutcome.SORRY_REFUSED
        assert refused.to_state_id is None

        monkeypatch.setattr(lean_backend, "ALWAYS_REFUSED", frozenset())
        passed_through = session.step(session.root_state_id, "sorry")
        assert passed_through.outcome is StepOutcome.TACTIC_ERROR
        assert "sorry" in (passed_through.error or "")


@pytest.mark.slow
def test_kernel_accepts_a_real_proof_and_rejects_a_sorry_ax_one() -> None:
    require_lean()
    require_train_json()
    _, probe = find_probe(4, 8)
    config = LeanToolchainConfig.from_env()

    with LeanReplSession(probe, config=config) as session:
        current = session.root_state_id
        accepted: list[str] = []
        for tactic in probe.reference_tactics:
            result = session.step(current, tactic)
            if not result.ok:
                pytest.skip(f"reference proof did not replay: {result.error}")
            assert result.to_state_id is not None
            current = result.to_state_id
            accepted.append(tactic)
            if result.closed:
                break
        else:
            pytest.skip("reference proof did not close in this session")

    good = verify_closed_script(probe, accepted, config=config)
    assert good.verified, good.errors
    assert good.contains_sorry_ax is False
    assert "depends on axioms" in good.print_axioms

    cheated = verify_closed_script(probe, ["sorry"], config=config)
    assert cheated.contains_sorry_ax is True
    assert not cheated.verified
    assert "sorryAx" in cheated.print_axioms


@pytest.mark.slow
def test_a_broken_script_is_reported_not_silently_accepted() -> None:
    require_lean()
    require_train_json()
    _, probe = find_probe(4, 8)
    result = verify_closed_script(probe, ["exact Nat.zero"], config=LeanToolchainConfig.from_env())
    assert not result.verified
    assert result.errors


@pytest.mark.slow
def test_a_probe_cannot_close_itself_by_name() -> None:
    """The file prefix stops before the declaration, so the theorem is out of scope."""

    require_lean()
    require_train_json()
    record, probe = find_probe(4, 8)
    config = LeanToolchainConfig.from_env()
    with LeanReplSession(probe, config=config) as session:
        result = session.step(session.root_state_id, f"exact {record['full_name']}")
        assert result.outcome is StepOutcome.TACTIC_ERROR, result.tactic_state
