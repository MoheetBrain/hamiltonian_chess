"""A7 -- is ``k = 1`` structural, or a convention some path can escape?

Every route to a second sample for one cell is tried:

R1  a solver whose first answer is unusable -- does anything call it again?
R2  a Lean step that fails -- does anything retry the tactic?
R3  a dead/expired session -- does the harness restart and replay?
R4  the transport -- does it retry on an exception or a bad status?
R5  the runner -- can one ``CellPlan`` be played twice, or a theorem be replayed?
R6  the table -- would a duplicate cell be noticed if one were written?
R7  the streamed file -- does a re-run append (accumulating draws) or truncate?
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit  # noqa: E402

from arena.experiments import hc_v0_6_assay as assay  # noqa: E402
from arena.experiments import ollama_live  # noqa: E402
from arena.experiments.hc_v0_6.schema import Arm, CellTable, DesignViolation  # noqa: E402
from arena.trajectory import lean_backend  # noqa: E402
from arena.trajectory import solver as solver_mod
from arena.trajectory.lean_backend import StepOutcome  # noqa: E402
from tests.experiments.test_hc_v0_6_assay import _FakeLive  # noqa: E402
from tests.trajectory.test_anchor import make_anchor  # noqa: E402


class CountingSolver:
    """Counts calls; always fails, to bait a retry."""

    def __init__(self) -> None:
        self.calls = 0
        self.identity = solver_mod.RECORDED_SOLVER

    def propose(self, observation, *, budget=solver_mod.DEFAULT_BUDGET):  # noqa: ANN001
        self.calls += 1
        return solver_mod.TacticProposal(
            status=solver_mod.ProposalStatus.PARSE_FAILURE,
            tactic=None,
            raw_output="",
            prompt_sha256="0" * 64,
            latency_ms=1,
            solver_digest="d",
            step_index=0,
            state_id="0",
        )


def _source(obj) -> str:  # noqa: ANN001
    return inspect.getsource(obj)


def main() -> int:
    anchor = make_anchor(prefix=(), reference=("simp [Nat.succ_le_iff]",))
    findings: dict[str, object] = {}

    # R1 -- one unusable proposal, one call
    counting = CountingSolver()
    assay._play_cell(
        _FakeLive(anchor), anchor, assay.CellPlan(Arm.R_A, 0), solver=counting, run=assay.AssayRun()
    )
    findings["R1_solver_calls_for_one_failed_cell"] = counting.calls

    # R2 -- a rejected tactic
    class OnceSolver(CountingSolver):
        def propose(self, observation, *, budget=solver_mod.DEFAULT_BUDGET):  # noqa: ANN001
            self.calls += 1
            return solver_mod.TacticProposal(
                status=solver_mod.ProposalStatus.OK,
                tactic="nonsense",
                raw_output='{"tactic":"nonsense"}',
                prompt_sha256="0" * 64,
                latency_ms=1,
                solver_digest="d",
                step_index=0,
                state_id="0",
            )

    once = OnceSolver()
    live = _FakeLive(anchor, StepOutcome.TACTIC_ERROR)
    assay._play_cell(live, anchor, assay.CellPlan(Arm.R_A, 0), solver=once, run=assay.AssayRun())
    findings["R2_solver_calls_for_a_rejected_tactic"] = once.calls
    findings["R2_lean_steps_for_a_rejected_tactic"] = len(live.tactics)

    # R3/R4/R5 -- static: look for any retry construct on the live paths
    sources = {
        "hc_v0_6_assay": _source(assay),
        "solver.OllamaTacticSolver.propose": _source(solver_mod.OllamaTacticSolver.propose),
        "ollama_live.urllib_transport": _source(ollama_live.urllib_transport),
        "lean_backend.LeanReplSession.step": _source(lean_backend.LeanReplSession.step),
    }
    pattern = re.compile(
        r"\bfor\s+\w*\s*in\s+range\(|while\s+|retry|retries|re-?send|backoff", re.I
    )
    findings["R3_R5_retry_constructs_found"] = {
        name: sorted(set(pattern.findall(text))) for name, text in sources.items()
    }
    findings["R3_session_restart_in_step"] = (
        "start(" in sources["lean_backend.LeanReplSession.step"]
    )
    findings["R4_transport_has_no_retry"] = "except" not in sources["ollama_live.urllib_transport"]

    # R6 -- a duplicate cell in the table
    from arena.experiments.hc_v0_6.schema import CellOutcome

    row = CellOutcome(
        anchor_id="a",
        cluster_id="c",
        theorem="t",
        reelaboration_key="k",
        arm=Arm.R_A,
        renderer_id="R_A",
        intervention_class=Arm.R_A.intervention_class,
        replicate_index=0,
        step_result=assay.StepResult.ACCEPTED_TRANSITION,
        parse_status=assay.ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
        proposed_tactic="simp",
    )
    try:
        CellTable([row, row])
        findings["R6_duplicate_cell"] = "ACCEPTED"
    except DesignViolation as error:
        findings["R6_duplicate_cell"] = f"REJECTED -- {error}"

    # R7 -- the stream file mode
    stream_line = [
        line.strip() for line in sources["hc_v0_6_assay"].splitlines() if "stream_to.open(" in line
    ]
    findings["R7_stream_open_mode"] = stream_line
    findings["R7_reruns_truncate_not_append"] = any('"w"' in line for line in stream_line)

    clean = (
        findings["R1_solver_calls_for_one_failed_cell"] == 1
        and findings["R2_solver_calls_for_a_rejected_tactic"] == 1
        and findings["R2_lean_steps_for_a_rejected_tactic"] == 1
        and str(findings["R6_duplicate_cell"]).startswith("REJECTED")
        and findings["R7_reruns_truncate_not_append"]
    )
    emit(
        "attack_07_redraws",
        {
            "attack": "A7 no free redraws: is k=1 structural?",
            "verdict": "HELD" if clean else "BROKEN",
            "findings": findings,
            "note": (
                "The only loop in run_assay is over plans; a CellPlan is consumed once and there "
                "is no path from a failure back to the solver. A per-theorem `except Exception` "
                "abandons the REST of the theorem -- it never replays what was already played, "
                "so it cannot create a second draw, but it does leave a partially played anchor "
                "in the table (see A8)."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
