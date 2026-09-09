"""The HC-V0.6 runner's own guarantees, checked rather than documented.

Three of these are load-bearing for the result and not for the code: the within-anchor order is a
recorded pure function (so a position effect cannot align with an arm), the oracle tripwire fires on
the *rendered* bytes (manual §29's "model-visible surface", the audit's F5), and the outcome
vocabularies are TOTAL -- an unmapped backend outcome would silently become an
``ENVIRONMENT_ERROR``, which is excluded from the analysis, so a Solver failure would vanish from
the denominator instead of counting against it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arena.evolution.record import InterventionClass
from arena.experiments.hc_v0_6.schema import (
    NON_REPRODUCIBLE_CELL_FIELDS,
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
)
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


def _row(arm: Arm, *, latency_ms: int = 7, step_result: StepResult | None = None) -> CellOutcome:
    """One populated cell.  ``latency_ms`` is the field the hash must not see."""

    return CellOutcome(
        anchor_id="anchor-0",
        cluster_id="Mathlib/Order/Basic.lean",
        theorem="thm",
        reelaboration_key="key",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=0,
        step_result=StepResult.ACCEPTED_TRANSITION if step_result is None else step_result,
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="a" * 64,
        prompt_tokens=11,
        response_tokens=3,
        latency_ms=latency_ms,
        solver_digest="digest",
        proposed_tactic="simp",
    )


def _manifest_hash(rows: list[CellOutcome]) -> str:
    return build_manifest(
        AssayRun(rows=rows, wall_clock_s=1.0, solver_seconds=1.0),
        bank=make_bank([_anchor()]),
        solver=ScriptedSolver(default="skip"),
        arms=tuple(Arm),
        replicates=1,
        seed=1,
    )["result_hash"]


def test_the_result_hash_ignores_wall_clock_and_per_cell_latency() -> None:
    """Two runs that differed only in how long they took must hash identically.

    **This test used to hash an empty table** (``AssayRun(rows=[])``), so it exercised only the
    manifest's own ``cost`` block -- which ``_strip`` already removed -- and could not fail.  The
    route that was actually open ran underneath it: ``latency_ms`` is carried on every *row*, the
    table reaches the manifest as one opaque ``cell_table_content_hash``, and by the time
    ``_strip`` runs there is nothing left for it to strip.  Two manifests differing only in one
    row's ``latency_ms`` (7 vs 9001) produced two different ``result_hash`` values
    (``docs/HC_V0_6_REDTEAM.md`` RT-V06-08).  Every row below is therefore populated, and the
    latency assertion is checked against a NON-empty table.
    """

    fast = [_row(arm) for arm in Arm]
    slow = [_row(arm, latency_ms=9001) for arm in Arm]
    assert _manifest_hash([]) == _manifest_hash([]), "the hash must at least be deterministic"
    assert _manifest_hash(fast) == _manifest_hash(slow), (
        "per-cell latency reached result_hash through cell_table_content_hash"
    )
    # ...and the hash must still MOVE when the mathematics does, or it is not a result hash.
    moved = [_row(arm) for arm in Arm]
    moved[0] = _row(Arm.R_A, step_result=StepResult.ACCEPTED_NO_OP)
    assert _manifest_hash(moved) != _manifest_hash(fast)
    assert _manifest_hash([]) != _manifest_hash(fast)


def test_the_cell_content_hash_covers_the_mathematics_and_nothing_else() -> None:
    """``CellTable.content_hash`` is where the exclusion has to happen, so it is pinned here.

    The old ``content_hash`` hashed ``to_dict()`` whole.  Nothing caught it because the only
    regression test hashed an empty table; the fields are asserted individually here so a future
    edit that puts a volatile field back has to delete an assertion to do it.
    """

    base = CellTable([_row(Arm.R_A)])
    assert base.content_hash == CellTable([_row(Arm.R_A)]).content_hash
    for field, value in (("latency_ms", 9001), ("prompt_tokens", 999), ("response_tokens", 999)):
        moved = CellTable([replace(_row(Arm.R_A), **{field: value})])
        assert moved.content_hash == base.content_hash, f"{field} must not move the content hash"
    assert set(NON_REPRODUCIBLE_CELL_FIELDS) == {"latency_ms", "prompt_tokens", "response_tokens"}
    moves: tuple[tuple[str, dict[str, Any]], ...] = (
        ("step_result", {"step_result": StepResult.ACCEPTED_NO_OP}),
        (
            "parse_status",
            {
                "parse_status": ParseStatus.PARSE_FAILURE,
                "step_result": StepResult.PARSE_FAILURE,
            },
        ),
        ("proposed_tactic", {"proposed_tactic": "rfl"}),
        ("prompt_sha256", {"prompt_sha256": "b" * 64}),
        ("solver_digest", {"solver_digest": "other-model"}),
    )
    for field, patch in moves:
        row = replace(_row(Arm.R_A), **patch)
        assert CellTable([row]).content_hash != base.content_hash, f"{field} must move it"


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


@pytest.mark.slow
def test_rows_are_streamed_as_they_are_produced(tmp_path: Path) -> None:
    """A pass is thousands of live calls over hours; a crash must not cost the work already done.

    This test exists because the streaming was once wired in the docstring and not in the loop: the
    runner reported 72 cells while the file it was supposedly streaming to was 0 bytes. A claim
    about durability that nothing checks is worse than no durability at all. It drives the real
    Lean path with a scripted Solver -- the bug was in the loop, so a fake loop would not have
    caught it.
    """

    from arena.experiments.hc_v0_6.schema import CellTable
    from arena.experiments.hc_v0_6_assay import run_assay
    from arena.trajectory.anchor import AnchorBank

    bank_path = Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
    if not bank_path.exists():
        pytest.skip("the anchored bank has not been built on this machine")
    out = tmp_path / "cells.jsonl"
    run = run_assay(
        AnchorBank.load(bank_path),
        ScriptedSolver(default="skip"),
        arms=(Arm.R_A, Arm.R_B),
        replicates=1,
        seed=1,
        theorem_limit=1,
        stream_to=out,
        progress=False,
    )
    assert out.exists() and out.stat().st_size > 0, "nothing was streamed"
    streamed = CellTable.read_jsonl(out)
    assert len(streamed) == len(run.table), "the streamed file lost rows"
    assert {r.cell_key for r in streamed} == {r.cell_key for r in run.table}


def test_a_scratch_path_in_a_skipped_reason_does_not_change_the_result_hash() -> None:
    """RT-V06-08's second route: free text is inside ``result_hash``, and Lean writes paths into it.

    The first route (``latency_ms``) was closed in the cell content hash. This one runs through
    ``skipped[].reason`` and ``theorem_errors[].error``, which carry Lean's per-session scratch
    directory verbatim. Left raw, two runs of identical mathematics produce different manifests --
    the exact defect that made HC-V0.5 conclude the runtime was not reproducible.
    """

    from arena.experiments.hc_v0_6_assay import AssayRun, SkippedAnchor, build_manifest

    def manifest(scratch: str) -> dict[str, Any]:
        run = AssayRun()
        run.skipped.append(
            SkippedAnchor(
                "anchor:1",
                f"/var/folders/w9/x/T/hamiltonian-lean-{scratch}/probe_Foo.lean: not reached",
            )
        )
        run.theorem_errors.append(
            (
                "Mathlib/T.lean::t",
                f"/var/folders/w9/x/T/hamiltonian-lean-{scratch}/probe.lean: boom",
            )
        )
        return build_manifest(
            run,
            bank=make_bank([_anchor()]),
            solver=ScriptedSolver(default="skip"),
            arms=tuple(Arm),
            replicates=1,
            seed=1,
        )

    first, second = manifest("aaa111"), manifest("bbb222")
    assert first["result_hash"] == second["result_hash"]
    assert "hamiltonian-lean-aaa111" not in json.dumps(first)
    assert "probe_Foo.lean" in json.dumps(first), "the diagnostic itself must survive"
    assert "not reached" in json.dumps(first)
