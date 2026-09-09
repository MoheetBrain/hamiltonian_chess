"""A11b -- does the intersection-union gate logic actually block on a failing gate, and does the
code implement the gates the FROZEN SPEC declares?

Half one: drive ``calibrate`` and ``CalibrationVerdict.release`` through every branch with
synthetic ``PairedEffect``s and check the block really happens.

Half two: compare what §10 of ``docs/HC_V0_6_SPEC.md`` says each gate IS against what the code
tests.

  spec null control   : "Delta(R_A, R_A') inside the equivalence band +/-0.05"     -- EQUIVALENCE
  code C1b            : "the cluster permutation p-value is <= 0.10"               -- SIGNIFICANCE
  spec degraded ctrl  : "Delta(R_A, R_ABLATED) <= -T_ablate", T_ablate = 0.067     -- MAGNITUDE
  code C2             : "p <= 0.05 and Delta < 0"                                  -- SIGNIFICANCE

Half three: the C1 identity control at the frozen ``k = 1``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit  # noqa: E402

from arena.experiments.hc_v0_6.calibration import (  # noqa: E402
    ALPHA_BYTE_NULL,
    ALPHA_IDENTITY,
    ALPHA_SENSITIVITY,
    CERTIFICATION_GATES,
    AssayBroken,
    Outcome,
    calibrate,
    false_certification_bound,
)
from arena.experiments.hc_v0_6.estimators import (  # noqa: E402
    ArmMarginal,
    Comparison,
    McNemarResult,
    PairedEffect,
    PermutationResult,
    PermutationUnit,
    holm_family,
    pair_for,
)
from arena.experiments.hc_v0_6.power import (  # noqa: E402
    DETERMINISTIC_SOLVER,
    MinimumDetectableEffect,
)
from arena.experiments.hc_v0_6.schema import (  # noqa: E402
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
)

T_ABLATE_FROM_SPEC = 0.5 * 0.133  # spec 7a / 10a: p_hat_A = 0.133 < 0.20


def _marginal(arm: Arm, rate: float) -> ArmMarginal:
    return ArmMarginal(
        arm=arm,
        n_cells=1127,
        n_events=int(rate * 1127),
        n_anchors=1127,
        n_clusters=330,
        rate=rate,
        anchor_averaged_rate=rate,
        clopper_pearson95=(rate - 0.02, rate + 0.02),
        cluster_bootstrap95=(rate - 0.03, rate + 0.03),
    )


def _effect(
    comparison: Comparison,
    delta: float,
    p_value: float,
    *,
    ci: tuple[float, float] | None = None,
    n_clusters: int = 330,
) -> PairedEffect:
    arm_a, arm_b = {
        Comparison.PRIMARY_RB_VS_RA: (Arm.R_A, Arm.R_B),
        Comparison.C1_IDENTITY: (Arm.R_A, Arm.R_A),
        Comparison.C1B_WHITESPACE: (Arm.R_A, Arm.R_A_PRIME),
        Comparison.C2_ABLATION: (Arm.R_A, Arm.R_ABLATED),
    }[comparison]
    ci = ci if ci is not None else (delta - 0.02, delta + 0.02)
    perm = PermutationResult(
        unit=PermutationUnit.CLUSTER,
        permutations=20000,
        delta=delta,
        p_value=p_value,
        null_mean=0.0,
        null_sd=0.01,
        null_quantiles=(-0.02, 0.02),
        reportable=True,
        note="synthetic",
    )
    return PairedEffect(
        comparison=comparison,
        arm_a=arm_a,
        arm_b=arm_b,
        n_anchors=1127,
        n_clusters=n_clusters,
        replicates=1,
        rate_a=0.133,
        rate_b=0.133 + delta,
        delta=delta,
        delta_ci95=ci,
        delta_ci95_anchor_naive=ci,
        mcnemar=_mcnemar(),
        permutation=perm,
        permutation_anchor_naive=perm,
        marginal_a=_marginal(arm_a, 0.133),
        marginal_b=_marginal(arm_b, 0.133 + delta),
    )


def _mcnemar() -> McNemarResult:
    from arena.experiments.hc_v0_6.estimators import ReplicateCollapse

    return McNemarResult(
        collapse=ReplicateCollapse.FIRST_REPLICATE,
        n_pairs=1127,
        n10=10,
        n01=10,
        p_value=1.0,
        reportable=True,
        note="synthetic",
    )


def _row(anchor: str, arm: Arm, rep: int) -> CellOutcome:
    return CellOutcome(
        anchor_id=anchor,
        cluster_id="Mathlib/A.lean",
        theorem="t",
        reelaboration_key="k",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=rep,
        step_result=StepResult.REJECTED_INVALID_ACTION,
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
    mde = MinimumDetectableEffect(**_mde_kwargs())
    findings: dict[str, Any] = {}

    good = {
        "identity": _effect(Comparison.C1_IDENTITY, 0.0, 1.0, ci=(0.0, 0.0)),
        "byte_null": _effect(Comparison.C1B_WHITESPACE, 0.002, 0.80),
        "sensitivity": _effect(Comparison.C2_ABLATION, -0.10, 0.0001),
    }
    verdict = calibrate(**good)
    findings["G0_all_gates_pass"] = {
        "status": verdict.status.value,
        "certified": verdict.certified,
        "false_certification_bound": verdict.false_certification_bound,
    }

    # --- each gate failing in turn ------------------------------------------------------------
    cases = {
        "G1_C1_fires": {**good, "identity": _effect(Comparison.C1_IDENTITY, 0.04, 0.01)},
        "G2_C1b_fires": {**good, "byte_null": _effect(Comparison.C1B_WHITESPACE, 0.06, 0.001)},
        "G3_C2_not_significant": {
            **good,
            "sensitivity": _effect(Comparison.C2_ABLATION, -0.10, 0.40),
        },
        "G4_C2_wrong_direction": {
            **good,
            "sensitivity": _effect(Comparison.C2_ABLATION, 0.10, 0.0001),
        },
        "G5_too_few_clusters": {
            **good,
            "byte_null": _effect(Comparison.C1B_WHITESPACE, 0.002, 0.8, n_clusters=12),
        },
    }
    for name, kwargs in cases.items():
        v = calibrate(**kwargs)
        entry: dict[str, Any] = {
            "status": v.status.value,
            "usable": v.usable,
            "certified": v.certified,
        }
        primary = _effect(Comparison.PRIMARY_RB_VS_RA, 0.09, 0.001)
        try:
            released = v.release(primary, mde, delta_min=0.05, equivalence_bound=0.05)
            entry["release"] = {
                "outcome": released.outcome.value,
                "attribution": released.attribution.value,
                "may_claim_structure": released.may_claim_structure,
                "headline": released.headline(),
            }
        except AssayBroken as error:
            entry["release"] = f"BLOCKED -- {str(error)[:120]}"
        findings[name] = entry

    # --- G6: arm-dependent missingness --------------------------------------------------------
    v = calibrate(**good, missingness={Arm.R_A: 0, Arm.R_B: 9, Arm.R_A_PRIME: 0, Arm.R_ABLATED: 0})
    findings["G6_arm_dependent_missingness"] = {
        "status": v.status.value,
        "usable": v.usable,
        "outcome_ladder_entry": Outcome.O7_ARM_DEPENDENT_MISSINGNESS.value,
    }

    # --- half two: spec text vs implemented gate ---------------------------------------------
    tiny_ablation = calibrate(
        **{**good, "sensitivity": _effect(Comparison.C2_ABLATION, -0.008, 0.0001)}
    )
    wide_byte_null = calibrate(
        **{
            **good,
            "byte_null": _effect(Comparison.C1B_WHITESPACE, 0.02, 0.55, ci=(-0.15, 0.19)),
        }
    )
    findings["S1_spec_T_ablate_vs_code"] = {
        "spec_requires_delta_at_most": -T_ABLATE_FROM_SPEC,
        "code_condition": "p <= ALPHA_SENSITIVITY and delta < 0 (no magnitude term)",
        "T_ablate_appears_anywhere_in_arena": False,
        "an_ablation_of_only_0.8_points_certifies": tiny_ablation.certified,
        "its_status": tiny_ablation.status.value,
    }
    findings["S2_spec_equivalence_band_vs_code"] = {
        "spec_requires": "Delta(R_A,R_A') INSIDE the equivalence band +/-0.05",
        "code_condition": f"cluster permutation p > {ALPHA_BYTE_NULL} (a failure to reject)",
        "a_null_control_with_CI_[-0.15,0.19]_certifies": wide_byte_null.certified,
        "equivalent_within_0.05": good["byte_null"].equivalent_within(0.05),
        "wide_case_equivalent_within_0.05": _effect(
            Comparison.C1B_WHITESPACE, 0.02, 0.55, ci=(-0.15, 0.19)
        ).equivalent_within(0.05),
        "note": (
            "PairedEffect.equivalent_within exists and is used ONLY for the primary's O3 "
            "decision; no gate calls it, so the frozen equivalence band is never tested."
        ),
    }
    findings["S3_gate_roster"] = [
        {
            "name": g.name,
            "comparison": g.comparison.value,
            "direction": g.direction.value,
            "alpha": g.alpha,
            "bounded_by_alpha": g.direction.bounded_by_alpha,
        }
        for g in CERTIFICATION_GATES
    ]
    findings["S3_false_certification_bound"] = false_certification_bound()
    findings["S3_alphas"] = {
        "identity": ALPHA_IDENTITY,
        "byte_null": ALPHA_BYTE_NULL,
        "sensitivity": ALPHA_SENSITIVITY,
    }

    # --- half three: C1 at the frozen k = 1 ---------------------------------------------------
    k1 = CellTable([_row(f"a{i}", arm, 0) for i in range(5) for arm in Arm])
    try:
        pair_for(k1, Comparison.C1_IDENTITY)
        findings["S4_C1_at_k1"] = "AVAILABLE"
    except Exception as error:
        findings["S4_C1_at_k1"] = f"UNAVAILABLE -- {type(error).__name__}: {str(error)[:160]}"
    try:
        holm_family(
            {
                Comparison.PRIMARY_RB_VS_RA: 0.01,
                Comparison.C1B_WHITESPACE: 0.5,
                Comparison.C2_ABLATION: 0.001,
            }
        )
        findings["S4_holm_without_C1"] = "ACCEPTED"
    except Exception as error:
        findings["S4_holm_without_C1"] = f"REFUSED -- {type(error).__name__}: {str(error)[:200]}"

    blocked_when_it_should = (
        not findings["G1_C1_fires"]["usable"]
        and not findings["G6_arm_dependent_missingness"]["usable"]
        and not findings["G5_too_few_clusters"]["usable"]
    )
    emit(
        "attack_11b_gates",
        {
            "attack": "A11b intersection-union gate logic, and gate-vs-spec agreement",
            "verdict": "MIXED" if blocked_when_it_should else "BROKEN",
            "gates_block_when_they_should": blocked_when_it_should,
            "findings": findings,
        },
    )
    return 0


def _mde_kwargs() -> dict[str, Any]:
    import inspect

    params = inspect.signature(MinimumDetectableEffect).parameters
    guess = {
        "n_anchors": 1127,
        "n_clusters": 330,
        "baseline_rate": 0.133,
        "alpha": 0.05,
        "target_power": 0.8,
        "replicates": DETERMINISTIC_SOLVER,
        "cluster_icc": 0.2,
        "design_effect": 1.5,
        "effective_cluster_size": 4.022,
        "mde_positive": 0.05,
        "mde_negative": -0.05,
        "mde": 0.05,
        "mde_if_independent": 0.042,
    }
    return {name: guess[name] for name in params if name in guess}


if __name__ == "__main__":
    raise SystemExit(main())
