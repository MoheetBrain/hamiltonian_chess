"""The HC-V0.6 runner's own guarantees, checked rather than documented.

Three of these are load-bearing for the result and not for the code: the within-anchor order is a
recorded pure function (so a position effect cannot align with an arm), the oracle tripwire fires on
the *rendered* bytes (manual §29's "model-visible surface", the audit's F5), and the outcome
vocabularies are TOTAL -- an unmapped backend outcome would silently become an
``ENVIRONMENT_ERROR``, which is excluded from the analysis, so a Solver failure would vanish from
the denominator instead of counting against it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import pytest

from arena.evolution.record import InterventionClass
from arena.experiments.hc_v0_6.schema import Arm, ParseStatus, StepResult
from arena.experiments.hc_v0_6_assay import (
    _OUTCOME_TO_RESULT,
    _PROPOSAL_TO_PARSE,
    AssayRun,
    CellPlan,
    OracleLeakInPrompt,
    _play_cell,
    assert_prompt_is_oracle_free,
    build_manifest,
    plan_cells,
)
from arena.trajectory.anchor import Anchor
from arena.trajectory.lean_backend import StepOutcome
from arena.trajectory.lean_backend import StepResult as LeanStepResult
from arena.trajectory.solver import ProposalStatus, ScriptedSolver
from tests.trajectory.test_anchor import make_anchor, make_bank

REFERENCE = ("simp [Nat.succ_le_iff]", "exact ne_of_gt_witness")


def _anchor(**kwargs: Any) -> Anchor:
    """Reuse the anchor bank's own test builder so this suite cannot drift from that schema."""

    return make_anchor(prefix=(), reference=REFERENCE, **kwargs)


# --- the within-anchor schedule -------------------------------------------------------------


def test_the_schedule_is_a_pure_function_of_seed_and_anchor() -> None:
    first = plan_cells(tuple(Arm), replicates=2, seed=7, anchor_id="a1")
    assert first == plan_cells(tuple(Arm), replicates=2, seed=7, anchor_id="a1")
    assert first != plan_cells(tuple(Arm), replicates=2, seed=7, anchor_id="a2")
    assert first != plan_cells(tuple(Arm), replicates=2, seed=8, anchor_id="a1")


def test_the_schedule_plays_every_arm_and_replicate_exactly_once() -> None:
    plans = plan_cells(tuple(Arm), replicates=3, seed=1, anchor_id="a1")
    assert sorted(plans, key=lambda c: (c.arm.value, c.replicate_index)) == sorted(
        (CellPlan(arm, i) for arm in Arm for i in range(3)),
        key=lambda c: (c.arm.value, c.replicate_index),
    )


def test_the_schedule_is_not_the_arm_declaration_order() -> None:
    """A fixed order would confound any position effect with the arm (design brief §9.1)."""

    fixed = list(Arm)
    orders = {
        tuple(c.arm for c in plan_cells(tuple(Arm), replicates=1, seed=3, anchor_id=f"a{i}"))
        for i in range(40)
    }
    assert len(orders) > 1
    assert any(order != tuple(fixed) for order in orders)


# --- the oracle tripwire ---------------------------------------------------------------------


def test_a_rendered_payload_carrying_a_recorded_tactic_is_refused() -> None:
    anchor = _anchor()
    with pytest.raises(OracleLeakInPrompt, match="recorded tactic"):
        assert_prompt_is_oracle_free({"goals_pp": f"⊢ True\n-- hint: {REFERENCE[0]}"}, anchor)


def test_a_clean_payload_passes_the_tripwire() -> None:
    """The negative control: without it the test above passes for a tripwire that always fires."""

    assert_prompt_is_oracle_free({"goals_pp": "n : ℕ\n⊢ n = n"}, _anchor())


def test_a_short_tactic_is_not_matched_as_a_substring() -> None:
    """``exact h`` is 7 characters; a 3-character tactic would match half of mathlib's goals."""

    anchor = replace(_anchor(), oracle=replace(_anchor().oracle, reference_tactics=("rfl",)))
    assert_prompt_is_oracle_free({"goals_pp": "⊢ rfl_lemma x"}, anchor)


# --- the outcome vocabularies are total ------------------------------------------------------


def test_every_backend_outcome_is_mapped() -> None:
    assert {o.value for o in StepOutcome} == set(_OUTCOME_TO_RESULT)


def test_every_proposal_status_is_mapped() -> None:
    assert {s.value for s in ProposalStatus} == set(_PROPOSAL_TO_PARSE)


def test_a_policy_refusal_is_a_solver_failure_not_a_harness_failure() -> None:
    """``sorry`` is the cheapest fake proof there is; losing it from the denominator would pay."""

    for outcome in (StepOutcome.POLICY_REJECTED, StepOutcome.SORRY_REFUSED):
        assert not _OUTCOME_TO_RESULT[outcome.value].harness_failure


def test_a_dead_backend_is_a_harness_failure() -> None:
    for outcome in (StepOutcome.BACKEND_DEAD, StepOutcome.SESSION_EXPIRED, StepOutcome.TIMEOUT):
        assert _OUTCOME_TO_RESULT[outcome.value].harness_failure


# --- one played cell, without Lean -----------------------------------------------------------


@dataclass
class _FakeLiveAnchor:
    anchor: Anchor
    live_state_id: str = "0"
    matched: bool = True

    @property
    def identity(self) -> Any:
        # ``_play_cell`` reads exactly one field off the identity; a real one would need a live
        # session and would test nothing extra here.
        return SimpleNamespace(record_session_id="sess-1")

    @property
    def anchor_id(self) -> str:
        return self.anchor.anchor_id


class _FakeLive:
    """Only what ``_play_cell`` uses: ``by_id`` and ``step``."""

    def __init__(self, anchor: Anchor, outcome: StepOutcome = StepOutcome.OK) -> None:
        self._item = _FakeLiveAnchor(anchor)
        self._outcome = outcome
        self.tactics: list[str] = []
        #: What Lean reports back as the state after the step.  Defaults to a genuinely different
        #: goal so that a test which does not care about the endpoint still scores an event.
        self.reply_state: str = "MOVED"
        #: What the live session says the anchored state is.  ``None`` exercises the fallback.
        self.parent_text: str | None = anchor.solver_visible.goals_pp

    def by_id(self, anchor_id: str) -> _FakeLiveAnchor:
        assert anchor_id == self._item.anchor_id
        return self._item

    def parent_state_text(self, anchor_id: str) -> str | None:
        return self.parent_text

    def step(self, anchor_id: str, tactic: str) -> LeanStepResult:
        self.tactics.append(tactic)
        return LeanStepResult(
            self._outcome,
            tactic,
            "0",
            to_state_id="1" if self._outcome is StepOutcome.OK else None,
            tactic_state=self.reply_state if self._outcome is StepOutcome.OK else None,
        )


def test_a_played_cell_records_the_derived_class_not_a_declared_one() -> None:
    anchor = _anchor()
    solver = ScriptedSolver(default="skip")
    run = AssayRun()
    ablated = _play_cell(
        _FakeLive(anchor), anchor, CellPlan(Arm.R_ABLATED, 0), solver=solver, run=run
    )
    baseline = _play_cell(_FakeLive(anchor), anchor, CellPlan(Arm.R_A, 0), solver=solver, run=run)
    assert ablated.intervention_class is InterventionClass.P_CHANGE
    assert baseline.intervention_class is InterventionClass.R_ONLY


def test_arms_send_different_bytes_to_the_solver_at_one_state() -> None:
    """If two arms produced the same prompt hash the comparison would be vacuous."""

    anchor = _anchor()
    solver = ScriptedSolver(default="skip")
    run = AssayRun()
    hashes = {
        arm: _play_cell(
            _FakeLive(anchor), anchor, CellPlan(arm, 0), solver=solver, run=run
        ).prompt_sha256
        for arm in Arm
    }
    assert len(set(hashes.values())) == len(Arm), hashes


def test_a_rejected_tactic_is_recorded_as_a_mathematical_failure() -> None:
    anchor = _anchor()
    run = AssayRun()
    cell = _play_cell(
        _FakeLive(anchor, StepOutcome.TACTIC_ERROR),
        anchor,
        CellPlan(Arm.R_A, 0),
        solver=ScriptedSolver(default="nonsense"),
        run=run,
    )
    assert cell.step_result is StepResult.REJECTED_INVALID_ACTION
    assert cell.analysable and not cell.accepted


def test_an_unparseable_proposal_never_reaches_lean() -> None:
    anchor = _anchor()
    live = _FakeLive(anchor)
    cell = _play_cell(
        live, anchor, CellPlan(Arm.R_A, 0), solver=ScriptedSolver(default=None), run=AssayRun()
    )
    assert cell.parse_status is ParseStatus.PARSE_FAILURE
    assert cell.step_result is StepResult.PARSE_FAILURE
    assert live.tactics == []


# --- the manifest ----------------------------------------------------------------------------


def test_the_result_hash_ignores_wall_clock() -> None:
    """Two runs that differed only in how long they took must hash identically."""

    bank = make_bank([_anchor()])
    solver = ScriptedSolver(default="skip")
    fast = AssayRun(rows=[], wall_clock_s=1.0, solver_seconds=1.0)
    slow = AssayRun(rows=[], wall_clock_s=900.0, solver_seconds=900.0)
    kwargs = {"bank": bank, "solver": solver, "arms": tuple(Arm), "replicates": 1, "seed": 1}
    assert (
        build_manifest(fast, **kwargs)["result_hash"]
        == build_manifest(slow, **kwargs)["result_hash"]
    )


# --- the primary endpoint: KERNEL_ACCEPTED_STATE_CHANGE ---------------------------------------


def test_an_accepted_tactic_that_moved_nothing_is_not_an_event() -> None:
    """``skip`` is accepted at every open goal. An acceptance endpoint would be maximised by it."""

    anchor = _anchor()
    live = _FakeLive(anchor)
    live.reply_state = anchor.solver_visible.goals_pp  # unchanged
    cell = _play_cell(
        live, anchor, CellPlan(Arm.R_A, 0), solver=ScriptedSolver(default="skip"), run=AssayRun()
    )
    assert cell.step_result is StepResult.ACCEPTED_NO_OP
    assert not cell.accepted
    assert cell.analysable, "a no-op is a Solver outcome, not a harness failure"


def test_an_accepted_tactic_that_moved_the_goal_is_an_event() -> None:
    anchor = _anchor()
    live = _FakeLive(anchor)
    live.reply_state = "n : ℕ\n⊢ True"
    cell = _play_cell(
        live, anchor, CellPlan(Arm.R_A, 0), solver=ScriptedSolver(default="simp"), run=AssayRun()
    )
    assert cell.step_result is StepResult.ACCEPTED_TRANSITION
    assert cell.accepted


def test_whitespace_alone_is_not_a_state_change() -> None:
    """The comparison is on the project's declared state identity, not on raw bytes."""

    from arena.experiments.hc_v0_6_assay import changed_the_declared_state

    assert not changed_the_declared_state("n : ℕ\n⊢ n = n", "n : ℕ  \n⊢ n = n")
    assert changed_the_declared_state("n : ℕ\n⊢ n = n", "n : ℕ\n⊢ True")
    assert not changed_the_declared_state("n : ℕ\n⊢ n = n", None)


def test_the_no_op_check_uses_the_live_parent_not_the_recorded_one() -> None:
    """A silent re-derivation drift must not be scored as a change of mathematics."""

    anchor = _anchor()
    live = _FakeLive(anchor)
    live.parent_text = "DRIFTED PARENT"
    live.reply_state = "DRIFTED PARENT"  # unchanged w.r.t. the LIVE parent
    cell = _play_cell(
        live, anchor, CellPlan(Arm.R_A, 0), solver=ScriptedSolver(default="skip"), run=AssayRun()
    )
    assert cell.step_result is StepResult.ACCEPTED_NO_OP


def test_the_no_op_check_falls_back_to_the_bank_when_the_session_is_silent() -> None:
    anchor = _anchor()
    live = _FakeLive(anchor)
    live.parent_text = None
    live.reply_state = anchor.solver_visible.goals_pp
    cell = _play_cell(
        live, anchor, CellPlan(Arm.R_A, 0), solver=ScriptedSolver(default="skip"), run=AssayRun()
    )
    assert cell.step_result is StepResult.ACCEPTED_NO_OP
