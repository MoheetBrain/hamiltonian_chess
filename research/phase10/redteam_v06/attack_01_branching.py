"""A1 -- can two arms at one anchor end up acting on DIFFERENT Lean states?

Four routes are tried:

A1.1  mutate the live handle between arms (``LiveAnchor.live_state_id``)
A1.2  play all four arms through a session that RECORDS which sid each step was applied to
A1.3  collide two anchors of one theorem on the same ``prefix_length``
A1.4  overwrite the parent text an arm compares against, from an earlier arm's step

The session stand-in records every ``(sid, tactic)`` it is handed, so "all arms stepped from the
same sid" is measured rather than asserted.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit  # noqa: E402

from arena.experiments.hc_v0_6.schema import Arm  # noqa: E402
from arena.experiments.hc_v0_6_assay import AssayRun, _play_cell, plan_cells  # noqa: E402
from arena.trajectory.anchor import Anchor, LiveAnchor  # noqa: E402
from arena.trajectory.lean_backend import StepOutcome, StepResult  # noqa: E402
from arena.trajectory.solver import ScriptedSolver  # noqa: E402
from tests.trajectory.test_anchor import make_anchor  # noqa: E402


@dataclass
class RecordingSession:
    """A Lean session stand-in that records which sid each step was applied to."""

    parent_text: str
    stepped_from: list[str] = field(default_factory=list)
    states: dict[str, str] = field(default_factory=dict)
    counter: int = 0

    def step(self, state_id: str, tactic: str) -> StepResult:
        self.stepped_from.append(state_id)
        self.counter += 1
        child = f"child{self.counter}"
        self.states[child] = f"y : Nat\n⊢ y + {self.counter} = y"
        return StepResult(
            outcome=StepOutcome.OK,
            tactic=tactic,
            from_state_id=state_id,
            to_state_id=child,
            tactic_state=self.states[child],
        )

    def state_text(self, state_id: str) -> str | None:
        return self.states.get(state_id)


@dataclass
class RecordingLive:
    """The ``LiveAnchorSet`` surface ``_play_cell`` uses, backed by a recording session."""

    item: LiveAnchor
    session: RecordingSession

    def by_id(self, anchor_id: str) -> LiveAnchor:
        return self.item

    def step(self, anchor_id: str, tactic: str) -> StepResult:
        return self.session.step(self.item.live_state_id, tactic)

    def parent_state_text(self, anchor_id: str) -> str | None:
        return self.session.state_text(self.item.live_state_id)


def main() -> int:
    anchor: Anchor = make_anchor(prefix=(), reference=("simp [Nat.succ_le_iff]",))
    findings: dict[str, Any] = {}

    session = RecordingSession(parent_text=anchor.solver_visible.goals_pp)
    session.states["sid-parent"] = anchor.solver_visible.goals_pp
    item = LiveAnchor(
        anchor=anchor,
        live_state_id="sid-parent",
        identity=type("I", (), {"record_session_id": "sess-1"})(),
        matched=True,
    )

    # ------------------------------------------------------------ A1.1 mutate the live handle
    try:
        item.live_state_id = "sid-hijacked"  # type: ignore[misc]
        findings["A1_1_mutate_live_handle"] = "SUCCEEDED -- LiveAnchor is mutable"
    except Exception as error:
        findings["A1_1_mutate_live_handle"] = f"BLOCKED -- {type(error).__name__}: {error}"

    # ------------------------------------------------------------ A1.2 four arms, one parent sid
    live = RecordingLive(item=item, session=session)
    run = AssayRun()
    solver = ScriptedSolver(default="exact rfl")
    plans = plan_cells(tuple(Arm), replicates=1, seed=20260909, anchor_id=anchor.anchor_id)
    rows = [_play_cell(live, anchor, plan, solver=solver, run=run) for plan in plans]
    findings["A1_2_arm_order_played"] = [str(row.arm.value) for row in rows]
    findings["A1_2_state_ids_stepped_from"] = list(session.stepped_from)
    findings["A1_2_all_arms_one_parent"] = len(set(session.stepped_from)) == 1
    findings["A1_2_children_created"] = session.counter
    findings["A1_2_parent_text_unchanged_after_every_step"] = (
        session.states["sid-parent"] == anchor.solver_visible.goals_pp
    )

    # ------------------------------------------------ A1.3 two anchors, one prefix_length
    twin = replace(anchor, goal_digest="00" * 32)
    collided = {a.sampling.prefix_length: a for a in (anchor, twin)}
    findings["A1_3_distinct_anchor_ids"] = anchor.anchor_id != twin.anchor_id
    findings["A1_3_survivors_after_prefix_length_keying"] = len(collided)
    findings["A1_3_note"] = (
        "open_anchor_session builds `wanted = {anchor.sampling.prefix_length: anchor}`. Two "
        "anchors of one theorem at the same prefix_length collapse to one; the loser appears in "
        "neither `live` nor `missing`, so it is dropped without a skip record."
    )

    # ------------------------------------------------ A1.4 can an arm rewrite the parent text?
    findings["A1_4_parent_text_after_three_steps"] = live.parent_state_text(anchor.anchor_id)
    findings["A1_4_parent_text_is_still_the_anchor"] = (
        live.parent_state_text(anchor.anchor_id) == anchor.solver_visible.goals_pp
    )

    verdict = (
        "HELD"
        if findings["A1_2_all_arms_one_parent"] and findings["A1_4_parent_text_is_still_the_anchor"]
        else "BROKEN"
    )
    emit(
        "attack_01_branching",
        {
            "attack": "A1 anchor branching: can two arms act on different Lean states?",
            "verdict": verdict,
            "findings": findings,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
