"""Targets 1 + 3, end to end: an oracle-fed episode emitted as a bank-grade VerifiedTrajectory.

`VerifiedTask.emit_trajectory()` hardcodes `actor=Actor.SOLVER` and `LeanTrajectoryArena.
build_trajectory` stamps that on every action.  This runs the whole HC-V0.5 pipeline with a
Solver whose "reasoning" is the LeanDojo record, emits the trajectory, writes it as a bank and
puts it through `verify_bank(relive=True)` -- the strongest check the repository has.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import OUT, emit  # noqa: E402

from arena.trajectory import episode as episode_mod  # noqa: E402
from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, select_candidates, verify_bank  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.solver import OllamaTacticSolver  # noqa: E402
from arena.trajectory.task import TaskBudget, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}


class OracleTransport:
    def __init__(self, tactics: list[str]) -> None:
        self.tactics = list(tactics)
        self.calls = 0

    def __call__(self, url: str, payload: Any) -> dict[str, Any]:
        tactic = self.tactics[min(self.calls, len(self.tactics) - 1)]
        self.calls += 1
        return {"response": json.dumps({"tactic": tactic}), "prompt_eval_count": 200,
                "eval_count": 11, "done_reason": "stop"}


def _runner_emits(task, solver) -> dict[str, Any]:
    """Does the shipped runner leave a task from which a trajectory can be emitted?"""
    result = episode_mod.run_episode(task, solver, max_steps=6)
    try:
        task.emit_trajectory()
        return {"emitted": True, "episode_solved": result.solved}
    except Exception as exc:  # noqa: BLE001
        return {
            "emitted": False,
            "error": f"{type(exc).__name__}: {exc}"[:160],
            "episode_solved": result.solved,
            "why": "run_episode uses `with task as active:` and __exit__ calls close()",
        }


def main() -> None:
    if not check_toolchain().available:
        RESULTS["toolchain"] = False
        emit("emit_trajectory", RESULTS)
        return
    started = time.monotonic()
    config = LeanToolchainConfig.from_env()
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON, min_horizon=1, limit=8, seed=20260908,
        scan_limit=2000, policy=TacticPolicy.record_only(),
    )
    for record, probe in zip(selection.records, selection.probes, strict=True):
        task = VerifiedTask.from_leandojo_record(
            record, probe, config=config, budget=TaskBudget(model_actions=8)
        )
        solver = OllamaTacticSolver(transport=OracleTransport(list(probe.reference_tactics)))
        # NOTE: run_episode() uses `with task as active:` and __exit__ closes the arena, so
        # emit_trajectory() raises TaskStateError after it.  The runner therefore NEVER emits a
        # VerifiedTrajectory.  Drive the task by hand to reach the emission path at all.
        RESULTS["runner_can_emit_a_trajectory"] = _runner_emits(task, solver)
        task = VerifiedTask.from_leandojo_record(
            record, probe, config=config, budget=TaskBudget(model_actions=8)
        )
        solver = OllamaTacticSolver(transport=OracleTransport(list(probe.reference_tactics)))
        projection = task.reset()
        played = []
        for index in range(6):
            if task.is_terminal():
                break
            observation = episode_mod.SolverObservation(index, "?", projection.rendered)
            proposal = solver.propose(observation)
            if proposal.tactic is None:
                break
            outcome = task.step(proposal.tactic)
            played.append(proposal.tactic)
            projection = outcome.observation
        result = type("R", (), {"solved": task.terminal_status().value == "CLOSED_VERIFIED",
                                "steps": [type("S", (), {"tactic": t})() for t in played]})()
        if not result.solved:
            task.close()
            continue
        trajectory = task.emit_trajectory()
        RESULTS["episode"] = {
            "problem_id": probe.problem_id,
            "task_terminal": task.terminal_status().value,
            "task_terminal_outcome": task.terminal_outcome(),
            "reward": task.reward(),
            "tactics_played": [s.tactic for s in result.steps],
            "tactics_recorded_in_the_source": list(probe.reference_tactics),
            "identical": [s.tactic for s in result.steps] == list(probe.reference_tactics),
        }
        RESULTS["emitted_trajectory"] = {
            "trajectory_id": trajectory.trajectory_id,
            "terminal_status": trajectory.terminal_status.value,
            "actors": sorted(a.value for a in trajectory.actors),
            "horizon": trajectory.horizon.to_dict(),
            "kernel_verified": trajectory.kernel_verified,
            "trust_tier": trajectory.provenance.trust_tier,
            "provenance_notes": list(trajectory.provenance.notes),
        }
        directory = OUT / "v05_oracle_emitted_bank"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bank.jsonl").write_text(trajectory.to_json() + "\n", encoding="utf-8")
        structural = verify_bank(directory, relive=False)
        lived = verify_bank(directory, relive=True, config=config, policy=TacticPolicy.record_only())
        RESULTS["verify"] = {
            "structural_passed": structural.passed,
            "structural_failures": structural.failures[:3],
            "relive_passed": lived.passed,
            "relive_matches": lived.relive_matches,
            "relive_failures": [f[:200] for f in lived.failures[:3]],
        }
        task.close()
        break
    RESULTS["verdict"] = (
        "DEFECT"
        if RESULTS.get("verify", {}).get("relive_passed")
        and RESULTS.get("emitted_trajectory", {}).get("actors") == ["SOLVER"]
        else "HELD"
    )
    RESULTS["note"] = (
        "an episode whose every action came from the recorded mathlib proof is emitted with "
        "actor=SOLVER, trust_tier=A_NATIVE_VERIFIED and solver_actions == achieved, and passes "
        "the repository's strongest check. Nothing in the artefact records where the tactics "
        "came from."
    )
    RESULTS["wall_s"] = round(time.monotonic() - started, 1)
    emit("emit_trajectory", RESULTS)


if __name__ == "__main__":
    main()
