"""RED TEAM: the remaining manual section 29 attack classes and the section 28 trust contract.

* cross-split identifiers  -> `assert_not_sealed`
* verifier crashes/timeouts -> section 28: UNKNOWN != FALSE, TIMEOUT != FALSE,
                               TOOL_ERROR != MATHEMATICAL_INVALID
* macro-cost hiding        -> `KernelStepCount` (manual sections 6.32, 13.1)
* binder renaming / alpha-equivalence / irrelevant reordering -> is there a verification
                               surface for them at all?

Run:  .venv/bin/python research/phase9/redteam/attack_contract_classes.py
Out:  research/phase9/redteam/out/contract_classes.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory.arena_v0 import LeanTrajectoryArena  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    SEALED_SPLIT_PATHS,
    LeanTheoremProbe,
    LeanToolchainConfig,
    SealedSplitError,
    TacticPolicy,
    assert_not_sealed,
    check_toolchain,
    verify_closed_script,
)
from arena.trajectory.schema import PPScope, TerminalStatus  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
BASE = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4"
)


def main() -> int:
    findings: dict[str, Any] = {}

    # ------------------------------------------------------- C1 sealed splits
    sealed: dict[str, str] = {}
    for name in (*SEALED_SPLIT_PATHS, "random/train.json"):
        try:
            assert_not_sealed(BASE / name)
            sealed[name] = "ALLOWED"
        except SealedSplitError as exc:
            sealed[name] = f"REFUSED: {str(exc)[:80]}"
    # evasion attempts: does a path that reaches the same file dodge the endswith() test?
    evasions = {
        "random/./val.json": BASE / "random" / "." / "val.json",
        "random/../random/val.json": BASE / "random" / ".." / "random" / "val.json",
        "absolute-resolved": (BASE / "random" / "val.json").resolve(),
        "symlink-style-alias": Path(
            str(BASE / "random" / "val.json").replace("/random/", "/random//")
        ),
    }
    for label, path in evasions.items():
        try:
            assert_not_sealed(path)
            sealed[f"EVASION::{label}"] = "ALLOWED (guard bypassed)"
        except SealedSplitError:
            sealed[f"EVASION::{label}"] = "REFUSED"
    findings["C1_sealed_split_guard"] = sealed

    # ------------------------------------------------------- C2 timeout / crash semantics
    lean = check_toolchain()
    if lean.available:
        probe = LeanTheoremProbe(
            problem_id="redteam::timeout",
            full_name="redteam.timeout",
            safe_name="redteam_timeout",
            file_path="<synthetic>",
            statement="theorem probe_redteam_timeout : 2 + 2 = 4",
            prefix_text="import Mathlib.Tactic",
            pp_scope=PPScope(),
            reference_tactics=(),
        )
        # a kernel re-elaboration that cannot finish in 1 second
        starved = LeanToolchainConfig.from_env(kernel_timeout_s=1.0)
        timed_out = verify_closed_script(probe, ["norm_num"], config=starved)
        findings["C2_kernel_timeout_is_not_a_falsehood"] = {
            "verified": timed_out.verified,
            "contains_sorry_ax": timed_out.contains_sorry_ax,
            "errors": timed_out.errors[:160],
            "exit_code": timed_out.exit_code,
            "section_28_reading": (
                "TIMEOUT yields verified=False with contains_sorry_ax=False and an explicit "
                "timeout message; it is NOT recorded as a mathematical falsehood"
            ),
        }

        # a session that cannot start: is the episode ERROR_BACKEND, not FAILED?
        broken = LeanTheoremProbe(
            problem_id="redteam::broken",
            full_name="redteam.broken",
            safe_name="redteam_broken",
            file_path="<synthetic>",
            statement="theorem probe_redteam_broken : ThisSymbolDoesNotExist",
            prefix_text="import Mathlib.Tactic",
            pp_scope=PPScope(),
            reference_tactics=(),
        )
        arena = LeanTrajectoryArena(
            config=LeanToolchainConfig.from_env(startup_timeout_s=90.0),
            policy=TacticPolicy.record_only(),
        )
        arena.reset(broken)
        findings["C2b_backend_failure_is_not_candidate_failure"] = {
            "terminal_status": arena.terminal_status.value,
            "is_ERROR_BACKEND": arena.terminal_status is TerminalStatus.ERROR_BACKEND,
            "is_FAILED": arena.terminal_status is TerminalStatus.FAILED,
            "evidence_verdicts": [e.verdict.value for e in arena._evidence],  # noqa: SLF001
        }
        arena.close()
    else:
        findings["C2_kernel_timeout_is_not_a_falsehood"] = {"skipped": "no lean toolchain"}

    # ------------------------------------------------------- C3 macro-cost hiding
    bank_rows = []
    for name in ("h5", "h12"):
        path = ROOT / "artifacts" / "trajectory_bank_v0" / name / "bank.jsonl"
        bank_rows += [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    findings["C3_macro_cost_hiding"] = {
        "field": "Horizon.kernel_step_count (manual sections 6.32, 13.1)",
        "distinct_values_in_committed_bank": sorted(
            {row["horizon"].get("kernel_step_count", "ABSENT") for row in bank_rows}
        ),
        "trajectories": len(bank_rows),
        "serialised_in_bank": "kernel_step_count" in json.dumps(bank_rows[0]["horizon"]),
        "note": (
            "the field exists and is serialised, and is 0 for every trajectory: a one-tactic "
            "`linarith` and a fourteen-tactic hand proof report the same post-lowering cost, "
            "which is exactly the macro-cost hiding manual section 13.1 asks the accounting to "
            "prevent. Nothing in the package ever assigns it a non-zero value."
        ),
        "assigned_anywhere_in_arena_trajectory": any(
            "kernel_step_count=" in (ROOT / "arena" / "trajectory" / f).read_text()
            for f in ("arena_v0.py", "lean_backend.py", "schema.py")
        ),
    }

    # ------------------------------------------------------- C4 alpha-equivalence surface
    findings["C4_alpha_equivalence_has_no_verification_surface"] = {
        "state_vs_state_comparisons_in_arena_trajectory": 0,
        "only_state_text_comparison": "is_no_goals(tactic_state) == 'no goals'",
        "consequence": (
            "binder renaming, alpha-equivalence and irrelevant reordering cannot flip a verdict, "
            "because no verdict is ever computed by comparing two states. The Lean elaborator "
            "decides each transition and the kernel decides closure. This is a genuine "
            "structural defence, and tests/trajectory/test_arena_v0.py enforces it with an AST "
            "scan that has a negative control."
        ),
        "scope_limit_of_that_scan": (
            "the scan globs arena/trajectory/*.py only; it does not cover arena/evolution, "
            "arena/experiments or arena/model_view, and it does not flag "
            "LeakageFilter.assert_observation_clean's `candidate in payload` containment test "
            "because the operand names are not in its STATE_TEXT_NAMES set"
        ),
    }

    (OUT / "contract_classes.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
