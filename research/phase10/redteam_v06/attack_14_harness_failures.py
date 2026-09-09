"""A14 -- is an ENVIRONMENT_ERROR really "never a mathematical zero"?

``docs/HC_V0_6_SPEC.md`` §4 and ``schema.py``'s own docstring both say harness failures are
excluded by ``CellOutcome.analysable`` rather than scored.  The exclusion is a method that a
caller must invoke: ``CellTable.drop_harness_failures()``.  This checks whether the analysis path
actually invokes it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import ROOT, emit  # noqa: E402

from arena.experiments.hc_v0_6.estimators import (  # noqa: E402
    Comparison,
    arm_marginal,
    estimate_pair,
)
from arena.experiments.hc_v0_6.schema import (  # noqa: E402
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
    extract_pair,
)


def _row(anchor: str, cluster: str, arm: Arm, result: StepResult) -> CellOutcome:
    reached = result not in {StepResult.PARSE_FAILURE, StepResult.NOT_ATTEMPTED}
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"{cluster}::t",
        reelaboration_key="k",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=0,
        step_result=result,
        parse_status=ParseStatus.OK if reached else ParseStatus.PARSE_FAILURE,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
        proposed_tactic="simp",
    )


def main() -> int:
    # 60 anchors over 30 files. R_A and R_B both score at 20 of them; R_B additionally loses 20
    # cells to the harness, which is what a flaky session looks like.
    clean_rows, lossy_rows = [], []
    for i in range(60):
        cluster = f"Mathlib/F{i % 30}.lean"
        event = StepResult.ACCEPTED_TRANSITION if i % 3 == 0 else StepResult.REJECTED_INVALID_ACTION
        for arm in (Arm.R_A, Arm.R_B):
            clean_rows.append(_row(f"a{i}", cluster, arm, event))
        lossy_rows.append(_row(f"a{i}", cluster, Arm.R_A, event))
        lossy_rows.append(
            _row(
                f"a{i}",
                cluster,
                Arm.R_B,
                StepResult.ENVIRONMENT_ERROR if i % 3 == 0 else event,
            )
        )
    clean = CellTable(clean_rows)
    lossy = CellTable(lossy_rows)

    findings: dict[str, Any] = {
        "clean_delta": estimate_pair(
            clean, Comparison.PRIMARY_RB_VS_RA, resamples=200, permutations=500
        ).delta,
        "lossy_delta_as_analysed": estimate_pair(
            lossy, Comparison.PRIMARY_RB_VS_RA, resamples=200, permutations=500
        ).delta,
        "lossy_delta_after_drop_harness_failures": estimate_pair(
            lossy.drop_harness_failures(),
            Comparison.PRIMARY_RB_VS_RA,
            resamples=200,
            permutations=500,
        ).delta,
        "extract_pair_filters_on_analysable": len(extract_pair(lossy, Arm.R_A, Arm.R_B).anchor_ids)
        < len(lossy.anchor_ids),
        "arm_marginal_counts_harness_failures_as_non_events": arm_marginal(
            lossy, Arm.R_B, resamples=100
        ).n_cells
        == len(lossy.rows_for(Arm.R_B)),
        "environment_errors_injected_into_R_B": sum(
            1 for r in lossy.rows_for(Arm.R_B) if r.step_result is StepResult.ENVIRONMENT_ERROR
        ),
    }
    source = (ROOT / "arena" / "experiments" / "hc_v0_6_report.py").read_text()
    findings["report_driver_calls_drop_harness_failures"] = "drop_harness_failures" in source
    findings["estimators_call_drop_harness_failures"] = (
        "drop_harness_failures"
        in (ROOT / "arena" / "experiments" / "hc_v0_6" / "estimators.py").read_text()
    )

    scored_as_zero = findings["clean_delta"] != findings["lossy_delta_as_analysed"] and (
        findings["lossy_delta_after_drop_harness_failures"] != findings["lossy_delta_as_analysed"]
    )
    emit(
        "attack_14_harness_failures",
        {
            "attack": "A14 is ENVIRONMENT_ERROR really never a mathematical zero?",
            "verdict": "BROKEN" if scored_as_zero else "HELD",
            "findings": findings,
            "note": (
                "CellOutcome.analysable and CellTable.drop_harness_failures exist and are correct; "
                "nothing on the analysis path calls them, so every harness-decided cell is "
                "scored as a 0 on the primary endpoint -- and, being arm-attached, it moves "
                "Delta directly."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
