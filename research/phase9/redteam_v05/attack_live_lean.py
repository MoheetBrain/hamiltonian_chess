"""Live-Lean attacks on the HC-V0.5 interactive path.

Needs the real toolchain and the 373 MB development split.  No model call is made.
Run: .venv/bin/python research/phase9/redteam_v05/attack_live_lean.py
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import emit  # noqa: E402

from arena.canonical.schema import canonical_json  # noqa: E402
from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, select_candidates  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.task import ActionResult, TaskBudget, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}
N_TASKS = 5
SCAN_LIMIT = 2000


def record(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {str(detail)[:400]}")


def main() -> None:
    report = check_toolchain()
    RESULTS["toolchain"] = {
        "available": report.available,
        "lean": report.lean_version_string,
        "mathlib_root": str(report.mathlib_root),
    }
    if not report.available:
        emit("live_lean", RESULTS)
        return

    started = time.monotonic()
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON,
        min_horizon=1,
        limit=N_TASKS,
        seed=20260908,
        scan_limit=SCAN_LIMIT,
        policy=TacticPolicy.record_only(),
    )
    RESULTS["selection"] = {
        "scanned": selection.scanned,
        "selected": len(selection.probes),
        "leakage_ledger": selection.leakage.to_dict(),
        "scan_wall_s": round(time.monotonic() - started, 1),
    }
    print(RESULTS["selection"])

    config = LeanToolchainConfig.from_env()

    # ---------------- L1: live leakage, recomputed independently with NO length floor
    leaks: list[dict[str, Any]] = []
    per_task: list[dict[str, Any]] = []
    for record_, probe in zip(selection.records, selection.probes, strict=True):
        secrets = [t for t in probe.reference_tactics if t.strip()]
        task = VerifiedTask.from_leandojo_record(
            record_, probe, config=config, budget=TaskBudget(model_actions=8)
        )
        try:
            projection = task.reset()
        except Exception as exc:  # noqa: BLE001
            per_task.append({"problem": probe.problem_id, "reset_error": str(exc)[:120]})
            task.close()
            continue
        payload = canonical_json(dict(projection.rendered))
        found = [s for s in secrets if s.strip() and s.strip() in payload]
        guarded = [s for s in secrets if len(s.strip().encode()) >= 6]
        per_task.append(
            {
                "problem": probe.problem_id,
                "reference_tactics": len(secrets),
                "tactics_under_the_6_byte_floor": [
                    s for s in secrets if len(s.strip().encode()) < 6
                ],
                "guard_registered": len(guarded),
                "verbatim_leaks_at_any_length": found,
                "full_name_in_observation": probe.full_name in payload,
                "file_path_in_observation": probe.file_path in payload,
                "pp_scope_in_observation": "pp_scope" in projection.rendered,
                "goal_bytes": len(projection.rendered.get("goals_pp", "")),
            }
        )
        leaks += found
        task.close()
    RESULTS["L1_live_leakage"] = {
        "verdict": "DEFECT" if leaks else "HELD",
        "tasks": per_task,
        "total_verbatim_leaks": len(leaks),
        "note": "independent recount over the LIVE initial observation with no length floor",
    }
    print("L1_live_leakage:", RESULTS["L1_live_leakage"]["verdict"], len(leaks), "leaks")

    # ---------------- L2: the interactive facts P1/P6 rest on, in real Lean
    record_, probe = selection.records[0], selection.probes[0]
    task = VerifiedTask.from_leandojo_record(
        record_, probe, config=config, budget=TaskBudget(model_actions=24)
    )
    task.reset()
    probes: list[dict[str, Any]] = []
    before = task.state_identity()
    for tactic in ("skip", "skip", "skip"):
        out = task.step(tactic)
        probes.append(
            {
                "tactic": tactic,
                "result": out.result.value,
                "goal_digest_unchanged": out.state_identity.goal_digest == before.goal_digest,
                "kernel_step_count": out.cost.kernel_step_count,
                "retries_remaining": out.retries_remaining,
                "terminal": out.terminal_status.value,
            }
        )
    accepted_noops = [p for p in probes if p["result"] == ActionResult.ACCEPTED_TRANSITION
                      and p["goal_digest_unchanged"]]
    record(
        "L2_skip_is_an_accepted_no_op",
        bool(accepted_noops),
        problem=probe.problem_id,
        probes=probes,
        note="each accepted `skip` costs one model action and one 'kernel step', changes "
        "nothing, and resets the PER_CONSECUTIVE_RUN retry counter",
    )

    # interleave: reject, skip, reject, skip ... under the declared max_retries=1
    rejections = 0
    for i in range(12):
        if task.is_terminal():
            break
        out = task.step("exact rt_red_team_nonexistent_lemma" if i % 2 == 0 else "skip")
        if out.result is ActionResult.REJECTED_INVALID_ACTION:
            rejections += 1
    record(
        "L2b_live_retry_allowance_reset_by_skip",
        rejections > 1,
        rejections_absorbed=rejections,
        declared_max_retries=task.failure_policy.max_retries,
        terminal=task.terminal_status().value,
        model_actions=task.cost.model_action_count,
    )
    task.close()

    # ---------------- L3: unsound / adversarial tactic strings, live
    task = VerifiedTask.from_leandojo_record(
        record_, probe, config=config, budget=TaskBudget(model_actions=24)
    )
    task.reset()
    adversarial = []
    for tactic in ("sorry", "so​rry", "«sorry»", "rfl /-", "exact @sorryAx _ _ true"):
        if task.is_terminal():
            task.reset()
        out = task.step(tactic)
        adversarial.append(
            {
                "tactic": tactic,
                "result": out.result.value,
                "backend_outcome": out.backend_outcome,
                "terminal": out.terminal_status.value,
                "reward": out.reward,
                "diagnostic": out.diagnostic[:110],
            }
        )
        if task.is_terminal():
            task.reset()
    record(
        "L3_unsound_tactic_accepted",
        any(a["reward"] > 0 or a["result"] == ActionResult.ACCEPTED_TRANSITION.value
            for a in adversarial),
        attempts=adversarial,
    )
    task.close()

    # ---------------- L4: two REAL Lean sessions share one kernel_key
    a = VerifiedTask.from_leandojo_record(record_, probe, config=config)
    b = VerifiedTask.from_leandojo_record(record_, probe, config=config)
    a.reset()
    b.reset()
    ia0, ib0 = a.state_identity(), b.state_identity()
    a.step("skip")
    b.step("constructor")
    ia, ib = a.state_identity(), b.state_identity()
    record(
        "L4_two_live_lean_sessions_share_a_kernel_key",
        ia.same_kernel_state_as(ib),
        task_ids_equal=a.task_id == b.task_id,
        session_labels=[a.session.session_id, b.session.session_id],
        kernel_keys=[ia.kernel_key, ib.kernel_key],
        same_kernel_state_as=ia.same_kernel_state_as(ib),
        goal_digests_equal=ia.goal_digest == ib.goal_digest,
        initial_reelaboration_keys_equal=ia0.reelaboration_key == ib0.reelaboration_key,
        note="reelaboration_key agreeing on the two INITIAL states is the documented guarantee "
        "and it holds; kernel_key agreeing on two states of two different live REPL processes "
        "is the guarantee that does not",
    )
    a.close()
    b.close()

    RESULTS["wall_s"] = round(time.monotonic() - started, 1)
    emit("live_lean", RESULTS)


if __name__ == "__main__":
    main()
