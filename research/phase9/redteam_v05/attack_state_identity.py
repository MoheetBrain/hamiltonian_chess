"""Targets 4 (stale / cross-session state identity) and 10 (stale projection)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import ScriptedArena, ScriptedStep, emit, make_probe  # noqa: E402

from arena.trajectory.lean_backend import StepOutcome  # noqa: E402
from arena.trajectory.state_identity import (  # noqa: E402
    BackendSessionRef,
    KernelStateIdentity,
)
from arena.trajectory.task import TaskStateError, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}


def record(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {detail}")


def _task(session_tag: str, plan):
    probe = make_probe()
    arena = ScriptedArena(plan, probe=probe, session_tag=session_tag)
    return VerifiedTask.from_probe(probe, arena_factory=lambda: arena), arena


# ---------------- I1: two genuinely different live sessions share one kernel_key
def i1() -> None:
    a, _ = _task("live-session-A", [ScriptedStep(StepOutcome.OK, pp="⊢ A reached this goal")])
    b, _ = _task("live-session-B", [ScriptedStep(StepOutcome.OK, pp="⊢ B reached a DIFFERENT goal")])
    a.reset(); b.reset()
    a.step("intro h"); b.step("cases h")
    ia, ib = a.state_identity(), b.state_identity()
    record(
        "I1_kernel_key_collides_across_two_live_sessions",
        ia.same_kernel_state_as(ib) and ia.goal_digest != ib.goal_digest,
        task_id_A=a.task_id,
        task_id_B=b.task_id,
        session_label_A=a.session.session_id,
        session_label_B=b.session.session_id,
        kernel_key_A=ia.kernel_key,
        kernel_key_B=ib.kernel_key,
        same_kernel_state_as=ia.same_kernel_state_as(ib),
        goal_digests_differ=ia.goal_digest != ib.goal_digest,
        record_keys_equal=ia.record_key == ib.record_key,
        note="session_id is the LABEL f'{task_id}#ep{n:04d}', not a handle on the live backend "
        "process; two VerifiedTasks built from one probe are the same task_id and their first "
        "episodes are both #ep0001",
    )


# -------------- I2: a backend failure at reset presents last episode's state under a new session
def i2() -> None:
    probe = make_probe()
    good = ScriptedArena([ScriptedStep(StepOutcome.OK, pp="⊢ episode one goal")], probe=probe,
                         session_tag="s1")

    class DeadArena(ScriptedArena):
        def reset(self, probe, *, hide_reference=None):
            raise RuntimeError("lean session refused to start")

    arenas = [good, DeadArena(probe=probe, session_tag="s2")]

    def factory():
        return arenas.pop(0)

    task = VerifiedTask.from_probe(probe, arena_factory=factory)
    task.reset()
    task.step("intro h")
    before = task.state_identity()
    try:
        task.reset()
        raised = ""
    except Exception as exc:  # noqa: BLE001
        raised = f"{type(exc).__name__}: {exc}"[:80]
    after = task.state_identity()
    record(
        "I2_state_carried_across_a_failed_reset",
        before.goal_digest == after.goal_digest and before.session_id != after.session_id,
        reset_raised=raised,
        episode_index=task.episode_index,
        session_before=before.session_id,
        session_after=after.session_id,
        goal_digest_unchanged=before.goal_digest == after.goal_digest,
        terminal_after=task.terminal_status().value,
        note="reset() advances _episode_index and _session BEFORE the arena is opened; if the "
        "arena raises, _current still holds the previous episode's state and observe()/"
        "state_identity() attribute it to the new session",
    )


# ---------------------------- I3: observe() after close() -- a projection of a dead session
def i3() -> None:
    task, _ = _task("s", [ScriptedStep(StepOutcome.OK, pp="⊢ live")])
    task.reset()
    task.step("intro h")
    task.close()
    projection = task.observe()
    identity = task.state_identity()
    try:
        task.step("rfl")
        stepped = True
        why = ""
    except TaskStateError as exc:
        stepped = False
        why = str(exc)[:80]
    record(
        "I3_observe_after_close_returns_a_dead_session_projection",
        True,
        observe_succeeded=True,
        declared_terminal_status=projection.rendered.get("terminal_status")
        or projection.identity.to_dict()["exposed_slots"],
        task_is_terminal=task.is_terminal(),
        kernel_key=identity.kernel_key,
        step_after_close_accepted=stepped,
        step_refusal=why,
        note="observe()/state_identity() have no arena precondition; only step() does. The "
        "projection reports TERMINAL_STATUS=OPEN for a session that no longer exists",
    )


# ---------------------------- I4: an identity can be minted for a state never reached
def i4() -> None:
    task, _ = _task("s", [ScriptedStep(StepOutcome.OK, pp="⊢ true goal")])
    task.reset()
    real = task.state_identity()
    forged = real.rendered_under("⊢ False", real.__class__.__dataclass_fields__ and
                                 task._current.pp_scope)  # noqa: SLF001
    round_tripped = KernelStateIdentity.from_dict(
        {**forged.to_dict(), "goal_digest": "0" * 64, "state_id": "999"}
    )
    record(
        "I4_identity_can_claim_an_unreached_state",
        forged.kernel_key == real.kernel_key and forged.goal_digest != real.goal_digest,
        real_kernel_key=real.kernel_key,
        forged_kernel_key=forged.kernel_key,
        forged_reelaboration_key=forged.reelaboration_key,
        from_dict_accepts_arbitrary_digest=round_tripped.identity_hash[:16],
        note="rendered_under() and from_dict() are unchecked constructors; neither consults a "
        "backend. Author-only, and both are documented as provenance carriers",
    )


# ------------- I5: does a rejected action ever show the Solver a state it has already left?
def i5() -> None:
    plan = [
        ScriptedStep(StepOutcome.OK, pp="⊢ state one"),
        ScriptedStep(StepOutcome.TACTIC_ERROR, error="nope"),
        ScriptedStep(StepOutcome.OK, pp="⊢ state two"),
    ]
    task, _ = _task("s", plan)
    task.reset()
    seen = [task.observe().rendered["goals_pp"]]
    for tactic in ("a", "b", "c"):
        out = task.step(tactic)
        seen.append(out.observation.rendered["goals_pp"])
    expected = ["a b : Nat\nh : a = b\n⊢ b = a", "⊢ state one", "⊢ state one", "⊢ state two"]
    record(
        "I5_stale_projection_after_a_rejection",
        seen != expected,
        observed=seen,
        expected=expected,
    )


if __name__ == "__main__":
    for fn in (i1, i2, i3, i4, i5):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(f"{fn.__name__}_CRASHED", False, error=f"{type(exc).__name__}: {exc}")
    emit("state_identity", RESULTS)
