"""Targets 6 (retry exploitation), 9 (crash/timeout reward) and the six cost counters."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import ScriptedArena, ScriptedStep, emit, make_probe  # noqa: E402

from arena.trajectory.lean_backend import StepOutcome, TacticPolicy  # noqa: E402
from arena.trajectory.schema import TerminalStatus  # noqa: E402
from arena.trajectory.task import (  # noqa: E402
    ActionResult,
    FailurePolicySpec,
    TaskBudget,
    VerifiedTask,
)

RESULTS: dict[str, Any] = {}


def record(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {detail}")


def build(plan, *, budget=None, policy=None, default=None, attempt_budget=32):
    probe = make_probe()
    arena = ScriptedArena(
        plan, probe=probe, attempt_budget=attempt_budget,
        default=default or ScriptedStep(StepOutcome.TACTIC_ERROR, error="rejected"),
    )
    task = VerifiedTask.from_probe(
        probe,
        arena_factory=lambda: arena,
        budget=budget or TaskBudget(),
        failure_policy=policy or FailurePolicySpec(),
    )
    return task, arena


# ---------------------------------------------------------------- P1: the retry allowance
def p1() -> None:
    """max_retries=1, but PER_CONSECUTIVE_RUN resets on any accepted transition."""
    # baseline: consecutive rejections
    task, _ = build([])
    task.reset()
    rejected = 0
    while not task.is_terminal() and rejected < 40:
        task.step("bogus")
        rejected += 1
    baseline = {"rejections_absorbed": rejected, "terminal": task.terminal_status().value}

    # attack: interleave one accepted no-op ("skip" in Lean 4 always succeeds and does nothing)
    plan = []
    for _ in range(40):
        plan.append(ScriptedStep(StepOutcome.TACTIC_ERROR, error="rejected"))
        plan.append(ScriptedStep(StepOutcome.OK, pp="⊢ b = a"))  # a no-op, state unchanged
    task2, arena2 = build(plan, budget=TaskBudget(model_actions=200), attempt_budget=200)
    task2.reset()
    n_rej = n_ok = 0
    while not task2.is_terminal() and (n_rej + n_ok) < 80:
        out = task2.step("bogus" if (n_rej + n_ok) % 2 == 0 else "skip")
        if out.result is ActionResult.REJECTED_INVALID_ACTION:
            n_rej += 1
        else:
            n_ok += 1
    record(
        "P1_retry_allowance_reset_by_no_op",
        n_rej > 2,
        declared_policy=task2.failure_policy.to_dict(),
        baseline_consecutive=baseline,
        rejections_absorbed_with_interleaved_no_op=n_rej,
        accepted_no_ops=n_ok,
        terminal=task2.terminal_status().value,
        no_op_suspected_gates_nothing=True,
        note="ONE_DIAGNOSTIC_RETRY/max_retries=1 bounds a RUN of failures, not an episode; "
        "any accepted tactic (Lean's `skip` is always accepted and is a no-op) restores it",
    )


# ------------------------------------------ P2: the model-action budget is not enforced
def p2() -> None:
    """A PARSE_FAILURE never reaches the arena, so the two budgets do not agree."""
    plan = []
    for _ in range(40):
        plan.append(ScriptedStep(StepOutcome.OK, pp="⊢ b = a"))
    task, arena = build(plan, budget=TaskBudget(model_actions=4), attempt_budget=4)
    task.reset()
    attempts = 0
    log = []
    while not task.is_terminal() and attempts < 30:
        # alternate: an action the harness cannot lower (NUL byte, legal JSON from the grammar)
        # with an accepted no-op.  Only the second reaches the arena.
        action = "rfl\x00" if attempts % 2 == 0 else "skip"
        out = task.step(action)
        log.append((action.replace("\x00", "\\0"), out.result.value, task.attempts_remaining))
        attempts += 1
    record(
        "P2_model_action_budget_overrun",
        task.cost.model_action_count > task.budget.model_actions,
        budget_model_actions=task.budget.model_actions,
        model_actions_charged=task.cost.model_action_count,
        arena_attempts=arena._attempts,  # noqa: SLF001
        attempts_remaining_reported=task.attempts_remaining,
        terminal=task.terminal_status().value,
        log=log,
        note="task.attempts_remaining clamps at 0 and terminates nothing; only the ARENA's "
        "attempt_budget can end the episode, and an action that never reached the backend "
        "does not consume one",
    )


# ------------------------------- P3: three of the five declared budget caps are never read
def p3() -> None:
    import inspect

    from arena.trajectory import task as task_mod

    src = inspect.getsource(task_mod)
    reads = {
        field: sum(1 for line in src.splitlines() if f"budget.{field}" in line)
        for field in ("model_actions", "wall_clock_s", "kernel_steps", "verifier_calls",
                      "tool_calls")
    }
    task, _ = build([ScriptedStep(StepOutcome.OK, pp="⊢ x")] * 10,
                    budget=TaskBudget(model_actions=100, kernel_steps=1, verifier_calls=1,
                                      tool_calls=1),
                    attempt_budget=100)
    task.reset()
    for _ in range(5):
        if not task.is_terminal():
            task.step("skip")
    record(
        "P3_unenforced_budget_counters",
        task.cost.kernel_step_count > 1,
        source_references_to_each_cap=reads,
        cap_kernel_steps=1,
        spent_kernel_steps=task.cost.kernel_step_count,
        spent_verifier_calls=task.cost.verifier_call_count,
        spent_tool_calls=task.cost.tool_call_count,
        terminal=task.terminal_status().value,
    )


# --------------------------------- P4: a harness fault must never be a mathematical failure
def p4() -> None:
    for name, outcome, expected_outcome_name in (
        ("timeout", StepOutcome.TIMEOUT, "TOOL_TIMEOUT"),
        ("backend_dead", StepOutcome.BACKEND_DEAD, "ENVIRONMENT_ERROR"),
        ("session_expired", StepOutcome.SESSION_EXPIRED, "EPISODE_ABANDONED"),
    ):
        task, _ = build([ScriptedStep(outcome, error="boom")])
        task.reset()
        out = task.step("simp")
        bad = (
            out.reward != 0.0
            or out.terminal_status is TerminalStatus.CLOSED_VERIFIED
            or out.result.is_mathematical_failure
            or out.result.attributable_to_solver
            or task.retries_remaining != task.failure_policy.effective_retries
        )
        record(
            f"P4_{name}_scored_as_solver_failure",
            bad,
            result=out.result.value,
            reward=out.reward,
            terminal=out.terminal_status.value,
            terminal_outcome=out.terminal_outcome,
            expected_outcome_name=expected_outcome_name,
            is_mathematical_failure=out.result.is_mathematical_failure,
            charged_to_solver=out.result.attributable_to_solver,
            retries_remaining=out.retries_remaining,
            model_actions_charged=task.cost.model_action_count,
        )


# --------------------------------- P5: can a finished episode be relabelled to solved?
def p5() -> None:
    task, arena = build([ScriptedStep(StepOutcome.TIMEOUT, error="boom"),
                         ScriptedStep(StepOutcome.OK, pp="no goals", closed=True)])
    task.reset()
    task.step("simp")
    first = task.terminal_status()
    try:
        task.step("native_decide")
        stepped_after_terminal = True
    except Exception as exc:  # noqa: BLE001
        stepped_after_terminal = False
        why = f"{type(exc).__name__}: {exc}"[:100]
    record(
        "P5_terminal_relabelled_to_solved",
        task.terminal_status() is TerminalStatus.CLOSED_VERIFIED,
        first_terminal=first.value,
        final_terminal=task.terminal_status().value,
        reward=task.reward(),
        step_after_terminal_accepted=stepped_after_terminal,
        refusal=None if stepped_after_terminal else why,
    )


# ------------------------------------------------ P6: macro-cost hiding in the action cost
def p6() -> None:
    policy = TacticPolicy.record_only()
    combos = [
        "constructor <;> simp <;> omega",
        "intro h; exact h.symm; rfl",
        "repeat (first | rfl | simp | ring | omega | aesop)",
        "all_goals (simp; ring)",
        "native_decide",
        "decide",
    ]
    decisions = {c: policy.classify(c)[0].value for c in combos}
    task, _ = build([ScriptedStep(StepOutcome.OK, pp="⊢ y")], attempt_budget=32)
    task.reset()
    out = task.step(combos[0])
    record(
        "P6_macro_cost_hiding",
        out.cost.kernel_step_count == 1 and decisions[combos[0]] == "ALLOWED",
        default_policy=policy.name,
        classifications=decisions,
        one_combinator_action_cost=out.cost.to_dict(),
        note="ActionCost.kernel_step_count is `1 if accepted else 0`; a `<;>`/`repeat`/"
        "`all_goals` action bundles many elaborator steps and still costs 1",
    )


# ------------------------------------------------------------- P7: wall-clock cap
def p7() -> None:
    task, _ = build([ScriptedStep(StepOutcome.OK, pp="⊢ z")] * 5,
                    budget=TaskBudget(model_actions=32, wall_clock_s=1e-9))
    task.reset()
    out = task.step("skip")
    record(
        "P7_wall_clock_cap_not_enforced",
        out.terminal_status is not TerminalStatus.BUDGET_EXHAUSTED,
        terminal=out.terminal_status.value,
        terminal_outcome=out.terminal_outcome,
    )


# ------------------------------- P8: abandon() must never be filed as a failure or a solve
def p8() -> None:
    task, _ = build([ScriptedStep(StepOutcome.OK, pp="⊢ q")])
    task.reset()
    task.abandon("red team")
    record(
        "P8_abandon_filed_as_failure_or_solve",
        task.terminal_status() in {TerminalStatus.FAILED, TerminalStatus.CLOSED_VERIFIED}
        or task.reward() != 0.0,
        terminal=task.terminal_status().value,
        terminal_outcome=task.terminal_outcome(),
        reward=task.reward(),
    )


if __name__ == "__main__":
    for fn in (p1, p2, p3, p4, p5, p6, p7, p8):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(f"{fn.__name__}_CRASHED", False, error=f"{type(exc).__name__}: {exc}")
    emit("policy_and_budget", RESULTS)
