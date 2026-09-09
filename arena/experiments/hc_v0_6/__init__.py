"""HC-V0.6 — the anchored paired Δ(R_A, R_B) analysis, preregistered before any assay data exists.

Four modules, in the order the experiment uses them:

===================  =========================================================================
:mod:`.schema`       the tidy result contract: one row per ``(anchor, arm, replicate)``
:mod:`.power`        design-stage power and the minimum detectable effect (design brief §9.5)
:mod:`.estimators`   the paired estimators and the frozen four-member Holm family
:mod:`.calibration`  the control verdict, and the only gate through which a result may be reported
===================  =========================================================================

Nothing here imports Lean, Ollama or the live trajectory stack: the analysis is runnable, and
testable, with no model and no REPL.  That is deliberate — an analysis that can only be exercised
by re-running the experiment cannot be checked before the experiment runs, which is the only time
checking it is worth anything.

The intended sequence::

    table   = CellTable.read_jsonl(path)
    effects = {c: estimate_pair(table, c) for c in PREREGISTERED_FAMILY}
    holm    = holm_family({c: e.p_value for c, e in effects.items()})
    verdict = calibrate(
        effects[Comparison.C1_IDENTITY],
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
    )
    result  = verdict.release(                       # raises AssayBroken if C1 fired
        effects[Comparison.PRIMARY_RB_VS_RA],
        minimum_detectable_effect(baseline, ClusterProfile.from_anchor_bank()),
        delta_min=...,
        equivalence_bound=...,
        p_holm=holm[Comparison.PRIMARY_RB_VS_RA].p_holm,
    )

``docs/HC_V0_6_ANALYSIS_PLAN.md`` justifies every choice above against manual §30.3.
"""

from __future__ import annotations

from arena.experiments.hc_v0_6.calibration import (
    ALPHA_BYTE_NULL,
    ALPHA_IDENTITY,
    ALPHA_SENSITIVITY,
    MIN_CLUSTERS,
    AssayBroken,
    AssayStatus,
    Attribution,
    CalibrationVerdict,
    ControlReading,
    Outcome,
    ReportableResult,
    calibrate,
)
from arena.experiments.hc_v0_6.estimators import (
    ALPHA,
    BOOTSTRAP_RESAMPLES,
    FAMILY_ARMS,
    PERMUTATIONS,
    PREREGISTERED_FAMILY,
    SEED,
    ArmMarginal,
    Comparison,
    HolmDecision,
    IdentityControlUnavailable,
    McNemarResult,
    PairedEffect,
    PermutationResult,
    PermutationUnit,
    ReplicateCollapse,
    ResampleUnit,
    anchor_deltas,
    arm_marginal,
    delta_hat,
    estimate_pair,
    exact_mcnemar,
    family_widening_guard,
    holm_family,
    pair_for,
    paired_bootstrap_ci,
    permutation_null,
    split_half_identity,
)
from arena.experiments.hc_v0_6.power import (
    DEFAULT_TARGET_POWER,
    DETERMINISTIC_SOLVER,
    HC_V0_6_BANK_RELPATH,
    POWER_VERSION,
    ClusterProfile,
    MinimumDetectableEffect,
    PairedBinaryModel,
    ReplicateModel,
    SampleSizeRequirement,
    SimulationResult,
    analytic_power,
    bootstrap_ci,
    design_summary,
    minimum_detectable_effect,
    required_anchors,
    simulate_anchor_deltas,
    simulate_power,
    simulate_type_i,
)
from arena.experiments.hc_v0_6.schema import (
    ACCEPTING_RESULTS,
    SCHEMA_VERSION,
    Arm,
    CellOutcome,
    CellTable,
    DesignViolation,
    PairedCells,
    ParseStatus,
    StepResult,
    extract_pair,
)

__all__ = [
    "ACCEPTING_RESULTS",
    "ALPHA",
    "ALPHA_BYTE_NULL",
    "ALPHA_IDENTITY",
    "ALPHA_SENSITIVITY",
    "BOOTSTRAP_RESAMPLES",
    "DEFAULT_TARGET_POWER",
    "DETERMINISTIC_SOLVER",
    "FAMILY_ARMS",
    "HC_V0_6_BANK_RELPATH",
    "MIN_CLUSTERS",
    "PERMUTATIONS",
    "POWER_VERSION",
    "PREREGISTERED_FAMILY",
    "SCHEMA_VERSION",
    "SEED",
    "Arm",
    "ArmMarginal",
    "AssayBroken",
    "AssayStatus",
    "Attribution",
    "CalibrationVerdict",
    "CellOutcome",
    "CellTable",
    "ClusterProfile",
    "Comparison",
    "ControlReading",
    "DesignViolation",
    "HolmDecision",
    "IdentityControlUnavailable",
    "McNemarResult",
    "MinimumDetectableEffect",
    "Outcome",
    "PairedBinaryModel",
    "PairedCells",
    "PairedEffect",
    "ParseStatus",
    "PermutationResult",
    "PermutationUnit",
    "ReplicateCollapse",
    "ReplicateModel",
    "ReportableResult",
    "ResampleUnit",
    "SampleSizeRequirement",
    "SimulationResult",
    "StepResult",
    "analytic_power",
    "anchor_deltas",
    "bootstrap_ci",
    "arm_marginal",
    "calibrate",
    "delta_hat",
    "design_summary",
    "estimate_pair",
    "exact_mcnemar",
    "extract_pair",
    "family_widening_guard",
    "holm_family",
    "minimum_detectable_effect",
    "pair_for",
    "paired_bootstrap_ci",
    "permutation_null",
    "required_anchors",
    "simulate_anchor_deltas",
    "simulate_power",
    "simulate_type_i",
    "split_half_identity",
]
