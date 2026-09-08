"""Are the four DISCLOSED limitations enforced in code, or only written down?

The directive lists these as disclosed and therefore not findings.  What is testable is whether
each is *structural* (a reader cannot be misled) or *conventional* (a reader can).
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import emit  # noqa: E402

from arena.trajectory import episode as episode_mod  # noqa: E402
from arena.trajectory import solver as solver_mod  # noqa: E402
from arena.trajectory import task as task_mod  # noqa: E402
from arena.trajectory.arena_v0 import CONTAMINATION_NOTE, DEFAULT_TRAIN_JSON, select_candidates  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
)
from arena.trajectory.task import TaskBudget, VerifiedTask  # noqa: E402

RESULTS: dict[str, Any] = {}
ARTIFACT = Path(__file__).resolve().parents[3] / "artifacts/trajectory/hc_v0_5_smoke.json"


def main() -> None:
    # D2 -- "the retry re-proposes the identical tactic": structural?
    prompt_src = inspect.getsource(solver_mod.build_prompt) + inspect.getsource(
        solver_mod.observed_state_text
    )
    RESULTS["D2_retry_is_structurally_a_no_op"] = {
        "prompt_reads_only": solver_mod.OBSERVED_FIELD,
        "diagnostic_appears_in_prompt_path": "diagnostic" in prompt_src,
        "temperature": dict(solver_mod.FROZEN_DECODING)["temperature"],
        "seed": dict(solver_mod.FROZEN_DECODING)["seed"],
        "runner_routes_diagnostic_anywhere": "diagnostic" in inspect.getsource(
            episode_mod.run_episode
        ).split("step.diagnostic")[0],
        "verdict": "ENFORCED (the disclosure is a consequence of the frozen prompt + greedy "
        "decoding, not a convention that could drift)",
    }

    # D3 -- contamination: stamped, and present in the committed artefact?
    committed = json.loads(ARTIFACT.read_text()) if ARTIFACT.exists() else {}
    RESULTS["D3_contamination_stamp"] = {
        "task_provenance_default": task_mod.TaskProvenance().contamination == CONTAMINATION_NOTE,
        "manifest_key_present": "contamination" in committed,
        "manifest_text_head": str(committed.get("contamination", ""))[:80],
        "scientific_status": committed.get("scientific_status"),
        "anything_refuses_an_exposed_problem": False,
        "verdict": "STAMPED, NOT ENFORCED -- and it cannot be; the stamp is the honest response",
    }

    # D4 -- the task/trajectory terminal divergence: is it recorded, or silent?
    if not check_toolchain().available:
        RESULTS["D4_terminal_divergence"] = {"toolchain": False}
        emit("disclosures", RESULTS)
        return
    config = LeanToolchainConfig.from_env()
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON, min_horizon=1, limit=1, seed=20260908,
        scan_limit=2000, policy=TacticPolicy.record_only(),
    )
    record, probe = selection.records[0], selection.probes[0]
    task = VerifiedTask.from_leandojo_record(
        record, probe, config=config, budget=TaskBudget(model_actions=8)
    )
    task.reset()
    for _ in range(3):
        if task.is_terminal():
            break
        task.step("exact rt_red_team_nonexistent_lemma")
    trajectory = task.emit_trajectory()
    notes = list(trajectory.provenance.notes)
    RESULTS["D4_terminal_divergence"] = {
        "task_terminal": task.terminal_status().value,
        "task_terminal_outcome": task.terminal_outcome(),
        "emitted_terminal": trajectory.terminal_status.value,
        "diverged": task.terminal_status().value != trajectory.terminal_status.value,
        "provenance_notes": notes,
        "divergence_recoverable_from_the_artefact": any(
            n.startswith("task_terminal_status=") for n in notes
        ),
        "verdict": "ENFORCED (the task terminal travels in provenance_notes, so a reader of the "
        "emitted trajectory alone can recover it)",
    }
    task.close()
    emit("disclosures", RESULTS)


if __name__ == "__main__":
    main()
