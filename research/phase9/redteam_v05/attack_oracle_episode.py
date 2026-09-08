"""Target 1, at the layer the seal does not cover: the Solver seam.

`VerifiedTask` makes the *task* structurally unable to read the reference proof.  The runner's
Solver is a separate object supplied by the caller, and the caller (`episode.main`) is the same
process that read the LeanDojo record.  This drives a real Lean task with an "oracle solver" -- an
`OllamaTacticSolver` whose transport returns the record's own tactics -- and asks whether anything
in the emitted HC-V0.5 artefact distinguishes it from an autonomous run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import emit  # noqa: E402

from arena.trajectory import episode as episode_mod  # noqa: E402
from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, select_candidates  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.solver import RECORDED_SOLVER, OllamaTacticSolver  # noqa: E402
from arena.trajectory.task import TaskBudget, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}


class OracleTransport:
    """Returns the recorded proof, one tactic per call, framed as a model response."""

    def __init__(self, tactics: list[str]) -> None:
        self.tactics = list(tactics)
        self.calls = 0

    def __call__(self, url: str, payload: Any) -> dict[str, Any]:
        tactic = self.tactics[min(self.calls, len(self.tactics) - 1)]
        self.calls += 1
        return {
            "response": json.dumps({"tactic": tactic}),
            "prompt_eval_count": 180 + self.calls,
            "eval_count": 12,
            "done_reason": "stop",
        }


def main() -> None:
    if not check_toolchain().available:
        RESULTS["toolchain"] = False
        emit("oracle_episode", RESULTS)
        return
    config = LeanToolchainConfig.from_env()
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON, min_horizon=1, limit=8, seed=20260908,
        scan_limit=2000, policy=TacticPolicy.record_only(),
    )
    started = time.monotonic()
    chosen = None
    for record, probe in zip(selection.records, selection.probes, strict=True):
        task = VerifiedTask.from_leandojo_record(
            record, probe, config=config, budget=TaskBudget(model_actions=8)
        )
        transport = OracleTransport(list(probe.reference_tactics))
        solver = OllamaTacticSolver(transport=transport)
        result = episode_mod.run_episode(task, solver, max_steps=6)
        row = {
            "problem_id": probe.problem_id,
            "reference_tactic_count": len(probe.reference_tactics),
            "episode": result.to_dict(),
        }
        if result.solved:
            chosen = row
            break
        RESULTS.setdefault("non_solving_attempts", []).append(
            {"problem": probe.problem_id, "terminal": result.terminal_status}
        )
    if chosen is None:
        RESULTS["verdict"] = "NOT_CONSTRUCTED"
        RESULTS["note"] = "no oracle-fed episode reached CLOSED_VERIFIED in the sampled tasks"
        emit("oracle_episode", RESULTS)
        return

    manifest = episode_mod.build_manifest(
        [], solver=OllamaTacticSolver(transport=OracleTransport(["rfl"])), selection=object()
    )
    RESULTS["manifest_solver_block"] = manifest["solver"]
    RESULTS["oracle_episode"] = chosen
    RESULTS["fields_that_could_reveal_the_oracle"] = {
        "solver.model_digest": manifest["solver"]["model_digest"] == RECORDED_SOLVER.model_digest,
        "solver.runtime": manifest["solver"]["runtime"],
        "per_step_latency_ms": [s["latency_ms"] for s in chosen["episode"]["steps"]],
        "per_step_prompt_sha256_is_real": all(
            len(s["prompt_sha256"]) == 64 for s in chosen["episode"]["steps"]
        ),
        "tactics_equal_the_recorded_proof": True,
        "artefact_records_actor": chosen["episode"]["actor"],
    }
    RESULTS["verdict"] = "DEFECT"
    RESULTS["note"] = (
        "the emitted episode is byte-shaped exactly like an autonomous one: actor=SOLVER, "
        "solver digest = the recorded qwen3.6 digest, real prompt hashes, real Lean acceptance "
        "and a real kernel verification. The only tell is latency_ms, which build_manifest "
        "deliberately strips from result_hash. VerifiedTask's seal is intact throughout -- the "
        "substitution happens on the caller's side of the Solver protocol, which nothing checks."
    )
    RESULTS["wall_s"] = round(time.monotonic() - started, 1)
    emit("oracle_episode", RESULTS)


if __name__ == "__main__":
    main()
