"""A13 -- the analysis driver ``arena/experiments/hc_v0_6_report.py``.

This module is UNTRACKED and was written at 05:14 on 2026-09-09, after the primary pass began at
04:59 -- i.e. after outcomes existed.  It is the thing that will actually produce the result, so it
is audited here as part of the instrument.

D1  ``unavailable_identity_control`` builds the C1 stand-in with ``dataclasses.replace`` and
    replaces ``delta``/``ci``/``n_anchors`` but **not** ``permutation``.  ``ControlReading`` reads
    ``effect.p_value``, which is ``permutation.p_value`` -- so the C1 gate is decided by C1b's
    p-value wearing C1's name.
D2  ``calibrate`` is called with no ``missingness=`` argument, so spec §10's "missingness: not
    arm-dependent -> run invalid" gate (outcome O7) can never fire.
D3  nothing calls ``CellTable.validate_balanced``, so a partial table is analysed silently.
D4  the MDE's ``ClusterProfile`` comes from the BANK, not from the table that was played, so a run
    that lost anchors reports the resolution of a design it did not run.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import ROOT, emit  # noqa: E402
from attack_11b_gates import _effect  # noqa: E402

from arena.experiments import hc_v0_6_report as report  # noqa: E402
from arena.experiments.hc_v0_6.calibration import ControlReading, calibrate  # noqa: E402
from arena.experiments.hc_v0_6.estimators import Comparison  # noqa: E402
from arena.experiments.hc_v0_6.schema import (  # noqa: E402
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
)


def _row(anchor: str, cluster: str, arm: Arm, event: bool, rep: int = 0) -> CellOutcome:
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"{cluster}::t",
        reelaboration_key="k",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=rep,
        step_result=StepResult.ACCEPTED_TRANSITION if event else StepResult.REJECTED_INVALID_ACTION,
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
        proposed_tactic="simp",
    )


def main() -> int:
    findings: dict[str, Any] = {}
    source = Path(ROOT / "arena" / "experiments" / "hc_v0_6_report.py").read_text()

    # --- D1 ------------------------------------------------------------------------------------
    c1b_significant = _effect(Comparison.C1B_WHITESPACE, 0.06, 0.004)
    stand_in = report.unavailable_identity_control(c1b_significant)
    reading = ControlReading.from_effect(stand_in)
    findings["D1_c1_standin"] = {
        "declared_delta": stand_in.delta,
        "declared_n_anchors": stand_in.n_anchors,
        "p_value_the_C1_gate_will_read": reading.p_value,
        "p_value_of_the_C1b_effect_it_was_built_from": c1b_significant.p_value,
        "they_are_the_same_number": reading.p_value == c1b_significant.p_value,
        "degenerate_flag_set": reading.degenerate,
    }
    verdict = calibrate(
        stand_in,
        c1b_significant,
        _effect(Comparison.C2_ABLATION, -0.10, 0.0001),
    )
    findings["D1_effect_on_the_verdict"] = {
        "status": verdict.status.value,
        "usable": verdict.usable,
        "reason": verdict.reasons[0] if verdict.reasons else "",
        "note": (
            "a significant BYTE-PERTURBATION control is reported as a broken IDENTITY control. "
            "Conservative in the blocking direction, but the recorded reason names the wrong "
            "control and quotes Delta=+0.0000 beside a p-value that belongs to a different "
            "contrast."
        ),
    }
    # the same construction with a benign C1b, to show the coupling both ways
    benign = _effect(Comparison.C1B_WHITESPACE, 0.001, 0.9)
    findings["D1_benign_case"] = {
        "p_value_the_C1_gate_will_read": ControlReading.from_effect(
            report.unavailable_identity_control(benign)
        ).p_value,
        "status": calibrate(
            report.unavailable_identity_control(benign),
            benign,
            _effect(Comparison.C2_ABLATION, -0.10, 0.0001),
        ).status.value,
    }

    # --- D2 / D3 --------------------------------------------------------------------------------
    findings["D2_calibrate_called_with_missingness"] = (
        "missingness" in source.split("calibrate(")[1].split(")")[0]
    )
    findings["D2_O7_can_fire"] = findings["D2_calibrate_called_with_missingness"]
    findings["D3_validate_balanced_called"] = "validate_balanced" in source
    findings["D3_drop_harness_failures_called"] = "drop_harness_failures" in source

    bank_path = ROOT / "artifacts" / "trajectory" / "hc_v0_6_anchor_bank.json"

    # --- D0: the driver on the design that is ACTUALLY running (k = 1) -----------------------
    k1 = CellTable(
        [
            _row(f"a{i}", f"Mathlib/F{i % 30}.lean", arm, event=(i % 5 == 0))
            for i in range(60)
            for arm in Arm
        ]
    )
    try:
        report.build_report(k1, bank_path=bank_path, model="redteam", arms=k1.arms)
        findings["D0_build_report_at_k1"] = "COMPLETED"
    except Exception as error:
        findings["D0_build_report_at_k1"] = f"CRASHED -- {type(error).__name__}: {str(error)[:220]}"
    findings["D0_note"] = (
        "build_report puts C1_IDENTITY in `available` because set(_arms_of(C1)) == {R_A} is a "
        "subset of the played arms, then calls estimate_pair on it. At the frozen k = 1 that is "
        "exactly the call unavailable_identity_control exists to avoid, and it is never reached."
    )

    # a deliberately unbalanced k=2 table, to show the rest of the driver runs without complaint
    rows = []
    for i in range(60):
        for arm in Arm:
            if i < 10 and arm is Arm.R_B:
                continue
            for rep in (0, 1):
                rows.append(
                    _row(f"a{i}", f"Mathlib/F{i % 30}.lean", arm, event=(i % 5 == 0), rep=rep)
                )
    table = CellTable(rows)
    built = report.build_report(table, bank_path=bank_path, model="redteam", arms=table.arms)
    findings["D3_unbalanced_table_analysed"] = {
        "anchors_in_table": built["anchors"],
        "anchors_in_the_primary_contrast": built["effects"]["PRIMARY_RB_VS_RA"]["n_anchors"],
        "dropped": built["anchors"] - built["effects"]["PRIMARY_RB_VS_RA"]["n_anchors"],
        "report_flags_the_loss": any(
            "missing" in k or "balance" in k or "dropped" in k for k in built
        ),
    }

    # --- D4 --------------------------------------------------------------------------------------
    findings["D4_mde_cluster_profile_source"] = (
        "ClusterProfile.from_anchor_bank(bank_path)" in source
    )
    findings["D4_mde_reported"] = {
        "n_anchors": built["mde"]["n_anchors"],
        "n_clusters": built["mde"]["n_clusters"],
        "table_anchors": built["anchors"],
        "table_clusters": built["clusters"],
        "profile_matches_what_was_played": built["mde"]["n_anchors"] == built["anchors"],
    }

    broken = [
        k
        for k, v in (
            ("D0", findings["D0_build_report_at_k1"].startswith("CRASHED")),
            ("D1", findings["D1_c1_standin"]["they_are_the_same_number"]),
            ("D2", not findings["D2_O7_can_fire"]),
            ("D3", not findings["D3_validate_balanced_called"]),
            ("D4", not findings["D4_mde_reported"]["profile_matches_what_was_played"]),
        )
        if v
    ]
    emit(
        "attack_13_report_driver",
        {
            "attack": "A13 the post-freeze analysis driver hc_v0_6_report.py",
            "verdict": "BROKEN" if broken else "HELD",
            "defects": broken,
            "provenance": {
                "tracked_in_git": False,
                "written_after_the_primary_pass_began": True,
                "note": "created 2026-09-09 05:14; the primary pass started 04:59",
            },
            "findings": findings,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
