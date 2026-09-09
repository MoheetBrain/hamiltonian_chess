"""A9 -- does the manifest's ``result_hash`` change when nothing mathematical changed?

Two defects of this class were already found and fixed (``wall_ms``, a per-session scratch path).
This looks for the next one.  ``build_manifest`` strips ``NON_DETERMINISTIC_FIELDS`` from the
payload before hashing -- so the attack is to find a volatile quantity that reaches the hash by a
route the strip cannot see.

D1  ``cell_table_content_hash`` is computed INSIDE ``CellTable`` from ``row.to_dict()``, which
    carries ``latency_ms``.  By the time ``_strip`` runs it is an opaque 64-character string.
D2  ``skipped[].reason`` and ``theorem_errors[].error`` carry Lean's own text, which names the
    per-session temporary probe file -- the exact shape of the scratch-path defect already fixed.
D3  ``counts.solver_calls`` and the served-verification note.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit  # noqa: E402

from arena.experiments.hc_v0_6.schema import (  # noqa: E402
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
)
from arena.experiments.hc_v0_6_assay import (  # noqa: E402
    NON_DETERMINISTIC_FIELDS,
    AssayRun,
    SkippedAnchor,
    build_manifest,
)
from arena.trajectory.solver import ScriptedSolver  # noqa: E402
from tests.trajectory.test_anchor import make_anchor, make_bank  # noqa: E402


def _row(latency: int = 7, tokens: int = 11) -> CellOutcome:
    return CellOutcome(
        anchor_id="anchor:1",
        cluster_id="Mathlib/A.lean",
        theorem="t",
        reelaboration_key="k",
        arm=Arm.R_A,
        renderer_id=Arm.R_A.renderer_id,
        intervention_class=Arm.R_A.intervention_class,
        replicate_index=0,
        step_result=StepResult.ACCEPTED_TRANSITION,
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=tokens,
        response_tokens=3,
        latency_ms=latency,
        solver_digest="d",
        proposed_tactic="simp",
    )


def _manifest(run: AssayRun) -> dict[str, Any]:
    bank = make_bank([make_anchor()])
    solver = ScriptedSolver(default="simp")
    return build_manifest(
        run, bank=bank, solver=solver, arms=(Arm.R_A,), replicates=1, seed=20260909
    )


def main() -> int:
    findings: dict[str, Any] = {}

    # ---- D1: latency reaches the hash through cell_table_content_hash ------------------------
    fast = CellTable([_row(latency=7)])
    slow = CellTable([_row(latency=9001)])
    findings["D1_cell_table_content_hash_changes_with_latency_only"] = (
        fast.content_hash != slow.content_hash
    )
    findings["D1_latency_is_in_NON_DETERMINISTIC_FIELDS"] = "latency_ms" in NON_DETERMINISTIC_FIELDS
    run_fast, run_slow = AssayRun(rows=[_row(latency=7)]), AssayRun(rows=[_row(latency=9001)])
    m_fast, m_slow = _manifest(run_fast), _manifest(run_slow)
    findings["D1_result_hash_changes_with_latency_only"] = (
        m_fast["result_hash"] != m_slow["result_hash"]
    )
    findings["D1_hashes"] = {
        "fast": m_fast["result_hash"][:16],
        "slow": m_slow["result_hash"][:16],
    }

    # ---- D2: a per-session scratch path inside a skip reason --------------------------------
    tmp_a = "/var/folders/w9/T/hamiltonian-lean-ugot2i12/probe_Foo.lean:12:4: error: unknown id"
    tmp_b = "/var/folders/w9/T/hamiltonian-lean-QQQQQQQQ/probe_Foo.lean:12:4: error: unknown id"
    run_a = AssayRun(rows=[_row()], skipped=[SkippedAnchor("anchor:2", tmp_a)])
    run_b = AssayRun(rows=[_row()], skipped=[SkippedAnchor("anchor:2", tmp_b)])
    findings["D2_result_hash_changes_with_a_scratch_path_in_a_skip_reason"] = (
        _manifest(run_a)["result_hash"] != _manifest(run_b)["result_hash"]
    )
    run_c = AssayRun(rows=[_row()], theorem_errors=[("F.lean::t", tmp_a)])
    run_d = AssayRun(rows=[_row()], theorem_errors=[("F.lean::t", tmp_b)])
    findings["D2_result_hash_changes_with_a_scratch_path_in_a_theorem_error"] = (
        _manifest(run_c)["result_hash"] != _manifest(run_d)["result_hash"]
    )

    # ---- D3: the same run twice, differing only in timing -----------------------------------
    quick = AssayRun(rows=[_row()], solver_seconds=1.0, lean_seconds=2.0, wall_clock_s=3.0, calls=1)
    slowrun = AssayRun(
        rows=[_row()], solver_seconds=999.0, lean_seconds=888.0, wall_clock_s=777.0, calls=1
    )
    findings["D3_result_hash_is_stable_under_pure_timing"] = (
        _manifest(quick)["result_hash"] == _manifest(slowrun)["result_hash"]
    )

    # ---- control: a real mathematical change must move the hash -----------------------------
    moved = AssayRun(rows=[replace(_row(), step_result=StepResult.ACCEPTED_NO_OP)])
    findings["control_a_changed_outcome_moves_the_hash"] = (
        _manifest(quick)["result_hash"] != _manifest(moved)["result_hash"]
    )

    broken = [
        k
        for k in (
            "D1_result_hash_changes_with_latency_only",
            "D2_result_hash_changes_with_a_scratch_path_in_a_skip_reason",
            "D2_result_hash_changes_with_a_scratch_path_in_a_theorem_error",
        )
        if findings[k]
    ]
    emit(
        "attack_09_result_hash",
        {
            "attack": "A9 result-hash stability: does the hash move when the mathematics did not?",
            "verdict": "BROKEN" if broken else "HELD",
            "unstable_routes": broken,
            "findings": findings,
            "non_deterministic_fields": sorted(NON_DETERMINISTIC_FIELDS),
            "note": (
                "_strip removes keys by name at every level of the manifest dict, but "
                "cell_table_content_hash is already a digest by then, and skipped/theorem_errors "
                "carry free text from the backend. Both are the same class as the two defects "
                "already fixed."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
