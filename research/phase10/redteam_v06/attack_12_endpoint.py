"""A12 -- score an event without doing mathematics, and lose one that was done.

``KERNEL_ACCEPTED_STATE_CHANGE`` = accepted AND (closed OR the declared state moved), where
"moved" is ``normalize_goal_text(after) != normalize_goal_text(before)``.  ``skip`` is closed off
(measured 0/36).  This looks for the next cheapest fake, and for the reverse error.

FAKES (accepted, zero mathematics, endpoint fires):
  E1  goal permutation -- ``rotate_left`` / ``swap`` / ``pick_goal 2`` reorder the goal list
  E2  hypothesis renaming -- ``rename_i`` changes only a name
  E3  hypothesis deletion -- ``clear h`` removes an unused hypothesis
  E4  a closure with an untrusted axiom -- ``native_decide`` (RT-01's hole), which the assay
      never checks because it never runs ``verify_closed_script``

MISSES (genuine advance, endpoint does not fire):
  E5  the backend returns OK with ``tactic_state=None`` -- scored ACCEPTED_NO_OP
  E6  a real change visible only in trailing whitespace, which the normalisation erases
  E7  a real change the session cannot report, so the parent falls back to the BANK's text
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.experiments.hc_v0_6.schema import Arm, StepResult  # noqa: E402
from arena.experiments.hc_v0_6_assay import (  # noqa: E402
    AssayRun,
    CellPlan,
    _play_cell,
    changed_the_declared_state,
)
from arena.trajectory.lean_backend import ALWAYS_REFUSED, StepOutcome, TacticPolicy  # noqa: E402
from arena.trajectory.solver import ScriptedSolver  # noqa: E402
from tests.experiments.test_hc_v0_6_assay import _FakeLive  # noqa: E402
from tests.trajectory.test_anchor import make_anchor  # noqa: E402

TWO_GOALS = "case inl\nn : Nat\nh : 0 < n\n⊢ n ≠ 0\n\ncase inr\nm : Nat\n⊢ m = m"
TWO_GOALS_ROTATED = "case inr\nm : Nat\n⊢ m = m\n\ncase inl\nn : Nat\nh : 0 < n\n⊢ n ≠ 0"
RENAMED = "n : Nat\nfresh : 0 < n\n⊢ n ≠ 0"
CLEARED = "n : Nat\n⊢ n ≠ 0"
BASE = "n : Nat\nh : 0 < n\n⊢ n ≠ 0"


def _cell(parent: str, reply: str | None, outcome: StepOutcome = StepOutcome.OK, closed=False):
    anchor = make_anchor(prefix=(), goals_pp=parent, reference=("simp [Nat.succ_le_iff]",))
    live = _FakeLive(anchor, outcome)
    live.parent_text = parent
    live.reply_state = reply  # type: ignore[assignment]
    row = _play_cell(
        live,
        anchor,
        CellPlan(Arm.R_A, 0),
        solver=ScriptedSolver(default="rotate_left"),
        run=AssayRun(),
    )
    return row


def main() -> int:
    policy = TacticPolicy.record_only()
    findings: dict[str, Any] = {}

    fakes = {
        "E1_goal_permutation": (TWO_GOALS, TWO_GOALS_ROTATED, "rotate_left"),
        "E2_hypothesis_rename": (BASE, RENAMED, "rename_i fresh"),
        "E3_hypothesis_clear": (BASE, CLEARED, "clear h"),
    }
    for name, (parent, after, tactic) in fakes.items():
        decision, reason = policy.classify(tactic)
        findings[name] = {
            "tactic": tactic,
            "policy": str(decision.value),
            "endpoint_fires": changed_the_declared_state(parent, after),
            "cell_step_result": str(_cell(parent, after).step_result.value),
        }

    findings["E4_untrusted_axiom_closure"] = {
        "tactic": "native_decide",
        "policy": str(policy.classify("native_decide")[0].value),
        "always_refused_tokens": sorted(ALWAYS_REFUSED),
        "assay_runs_verify_closed_script": False,
        "assay_checks_untrusted_axioms": False,
        "note": (
            "closed_all_goals comes straight from the REPL's `no goals` sentinel. RT-01's fix "
            "(the TRUSTED_AXIOMS allow-list) lives in verify_closed_script, which this assay "
            "never calls, so a native_decide closure would score an event with Lean.ofReduceBool "
            "in its trust base and nothing would record it."
        ),
    }

    # --- misses -------------------------------------------------------------------------------
    findings["E5_ok_step_with_no_reported_state"] = {
        "endpoint_fires": changed_the_declared_state(BASE, None),
        "cell_step_result": str(_cell(BASE, None).step_result.value),
        "note": "an OK step whose tactic_state the backend did not report scores 0, not a "
        "harness failure -- a genuine advance would be silently recorded as a no-op",
    }
    findings["E6_change_erased_by_normalisation"] = {
        "endpoint_fires": changed_the_declared_state(BASE, BASE + "   "),
        "note": "normalize_goal_text rstrips each line, so a change that is only trailing "
        "whitespace is invisible. Harmless for real tactics.",
    }
    findings["E7_parent_falls_back_to_the_bank"] = {
        "note": (
            "`live.parent_state_text(...) or anchor.solver_visible.goals_pp` -- if the session "
            "returns None or '' the comparison silently switches from the LIVE parent to the "
            "BANK's recorded text. The two agree only up to the re-elaboration key, which is a "
            "hash of the NORMALISED text, so a live/bank divergence inside the normalisation "
            "would not be caught."
        ),
        "fallback_reached_when_session_is_silent": str(_cell(BASE, BASE).step_result.value),
    }

    # --- how much of the bank is exposed to E1? ----------------------------------------------
    bank = load_bank_dict()
    multi = sum(1 for a in bank["anchors"] if int(a["solver_visible"]["n_goals"]) >= 2)
    findings["E1_exposure"] = {
        "anchors_with_two_or_more_goals": multi,
        "anchors_total": len(bank["anchors"]),
        "share": round(multi / len(bank["anchors"]), 4),
    }

    fired = [
        name
        for name in fakes
        if findings[name]["endpoint_fires"]
        and findings[name]["cell_step_result"] == StepResult.ACCEPTED_TRANSITION.value
    ]
    emit(
        "attack_12_endpoint",
        {
            "attack": "A12 the endpoint: score without mathematics, and lose a genuine advance",
            "verdict": "BROKEN" if fired else "HELD",
            "fakes_that_scored": fired,
            "findings": findings,
            "caveat": (
                "The SCORING half is measured here exactly. Whether Lean accepts rotate_left / "
                "rename_i / clear at a given anchor is not re-measured (Lean is busy); it is "
                "standard Mathlib behaviour but is marked PLAUSIBLE end-to-end, CONFIRMED for "
                "the scoring rule."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
