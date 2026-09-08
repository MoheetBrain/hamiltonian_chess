"""Target 4, sharpened on real Lean: two concurrent live sessions of one task are indistinguishable.

`KernelStateIdentity.kernel_key`'s docstring: *"Two identities with equal kernel keys name the
same saved backend state: the backend itself says so, the state can be re-entered with branch()."*
This drives two real Lean REPL processes on one task and asks whether that holds.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import emit  # noqa: E402

from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, select_candidates  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.task import TaskBudget, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}


def main() -> None:
    if not check_toolchain().available:
        RESULTS["toolchain"] = False
        emit("session_collision", RESULTS)
        return
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON, min_horizon=1, limit=6, seed=20260908,
        scan_limit=2000, policy=TacticPolicy.record_only(),
    )
    config = LeanToolchainConfig.from_env()
    attempts = []
    for record_, probe in zip(selection.records, selection.probes, strict=True):
        reference_first = probe.reference_tactics[0]
        a = VerifiedTask.from_leandojo_record(record_, probe, config=config,
                                              budget=TaskBudget(model_actions=4))
        b = VerifiedTask.from_leandojo_record(record_, probe, config=config,
                                              budget=TaskBudget(model_actions=4))
        a.reset(); b.reset()
        # A does nothing; B plays the theorem's own first tactic.  Two live REPL processes.
        oa = a.step("skip")
        ob = b.step(reference_first)
        ia, ib = a.state_identity(), b.state_identity()
        row = {
            "problem": probe.problem_id,
            "A_tactic": "skip",
            "B_tactic": reference_first,
            "A_result": oa.result.value,
            "B_result": ob.result.value,
            "task_ids_equal": a.task_id == b.task_id,
            "kernel_key_A": ia.kernel_key,
            "kernel_key_B": ib.kernel_key,
            "same_kernel_state_as": ia.same_kernel_state_as(ib),
            "record_keys_equal": ia.record_key == ib.record_key,
            "goal_digests_equal": ia.goal_digest == ib.goal_digest,
            "reelaboration_keys_equal": ia.reelaboration_key == ib.reelaboration_key,
            "A_terminal": a.terminal_status().value,
            "B_terminal": b.terminal_status().value,
            "A_goal_bytes": len(a.observe().rendered.get("goals_pp", "")),
            "B_goal_bytes": len(b.observe().rendered.get("goals_pp", "")),
        }
        a.close(); b.close()
        attempts.append(row)
        print(row["problem"], row["same_kernel_state_as"], row["goal_digests_equal"],
              row["A_terminal"], row["B_terminal"])
        if row["same_kernel_state_as"] and not row["goal_digests_equal"]:
            break
    hits = [r for r in attempts
            if r["same_kernel_state_as"] and not r["goal_digests_equal"]]
    RESULTS["attempts"] = attempts
    RESULTS["verdict"] = "DEFECT" if hits else "HELD"
    RESULTS["collisions"] = hits
    RESULTS["note"] = (
        "kernel_key = backend_kind|session_id|state_id, and session_id is the LABEL "
        "f'{task_id}#ep{episode_index:04d}'.  record_session_id is content-addressed from the "
        "probe/policy/seed and collides too.  No field in KernelStateIdentity distinguishes two "
        "concurrent live sessions of one task, so equal kernel keys can name two states in two "
        "different REPL processes -- one still OPEN, one CLOSED_VERIFIED -- with different goals."
    )
    emit("session_collision", RESULTS)


if __name__ == "__main__":
    main()
