"""Turn one HC-V0.6 cell table into the frozen report: contrasts, gates, resolution, verdict.

Every choice here was fixed in ``docs/HC_V0_6_SPEC.md`` before any outcome existed.  This module
does the arithmetic; it decides nothing.  Two points where it could quietly have decided something,
and does not:

* **The Holm family stays at four members even though C1 cannot be measured.**  ``k = 1`` forecloses
  the identity control (§10b): there is one draw per anchor, so ``R_A``'s replicates cannot be split.
  Dropping it from the family would shrink the correction from four hypotheses to three and make the
  primary *easier* to declare significant -- a relaxation bought by a missing control.  Its slot is
  therefore retained with ``p = 1.0``, which under Holm gives the remaining three exactly the
  multipliers they would have had in the frozen family.
* **A cell the harness decided is excluded, not scored.**  Spec §4 types ``ENVIRONMENT_ERROR``
  separately and says it is never a mathematical zero.  The exclusion is structural, inside
  ``extract_pair`` and ``arm_marginal``, so no analysis path can forget it; what was dropped is
  reported per arm, and the same per-arm count feeds the missingness gate, whose failure
  invalidates the run (spec §10, §13).
* **A control that was not measured decides nothing and is not a zero.**  ``k = 1`` forecloses C1
  (§10b).  It is reported ``UNAVAILABLE``, it carries ``p = 1.0`` rather than any other contrast's
  p-value, and the C1 gate is routed round rather than fed a borrowed number.
* **``T_ablate`` comes from the preflight baseline and from nothing in this run** (§10a).  It is a
  required argument to ``calibrate``, so the C2 magnitude requirement cannot be omitted by
  silence, and it is checked against the achieved MDE before the observed C2 is read.
* **The realised ICC is estimated from the data, not assumed.**  The minimum detectable effect is a
  function of it, and ``docs/HC_V0_6_SPEC.md`` §8a shows the answer to "does this bank resolve five
  points" flips inside the plausible ICC band.  Assuming a favourable value would decide the
  headline question by assumption.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arena.experiments.hc_v0_6.calibration import (
    EQUIVALENCE_BOUND,
    CalibrationVerdict,
    calibrate,
    t_ablate_from_preflight_baseline,
)
from arena.experiments.hc_v0_6.estimators import (
    PREREGISTERED_FAMILY,
    Comparison,
    IdentityControlUnavailable,
    McNemarResult,
    PairedEffect,
    PermutationResult,
    PermutationUnit,
    ReplicateCollapse,
    arm_marginal,
    estimate_pair,
    holm_family,
)
from arena.experiments.hc_v0_6.power import ClusterProfile, minimum_detectable_effect
from arena.experiments.hc_v0_6.schema import Arm, CellTable, DesignViolation, StepResult

REPORT_VERSION = "arena-hc-v0.6-report-v1"

#: The owner-supplied practical threshold for this development scout (spec §8).
DELTA_MIN = 0.05

#: Preflight ``R_A``-only event rates, spec §7a table, measured 2026-09-09 on 45 anchors **before
#: any ``R_B`` or ``R_ABLATED`` outcome existed anywhere**.  ``T_ablate`` is a function of these
#: and of nothing in the assay itself (spec §10a), which is why they are frozen here rather than
#: recomputed from the run: a threshold derived from the data it judges is not a threshold.
PREFLIGHT_BASELINE_RATES: dict[str, float] = {
    "gemma4:e4b": 0.133,
    "gemma4:12b": 0.156,
    "qwen3.6:27b-mlx": 0.400,
    "gemma4:31b": 0.356,
}


def realised_icc(table: CellTable, comparison: Comparison) -> float:
    """A one-way ANOVA estimate of the intra-cluster correlation of the paired differences.

    Clusters are mathlib files.  The quantity that matters for the interval is not the correlation
    of the *outcomes* but of the per-anchor **differences** the paired test actually consumes, so
    that is what is estimated.  Returned clamped to ``[0, 1]``: a negative moment estimate means
    "no detectable positive clustering", and reporting it as negative would invite reading it as
    evidence of anti-correlation.
    """

    from arena.experiments.hc_v0_6.estimators import anchor_deltas, extract_pair

    pair = extract_pair(table, *_arms_of(comparison))
    deltas = anchor_deltas(pair)
    clusters: dict[str, list[float]] = {}
    for cluster_id, delta in zip(pair.cluster_ids, deltas, strict=True):
        clusters.setdefault(cluster_id, []).append(float(delta))
    groups = [g for g in clusters.values() if g]
    n = sum(len(g) for g in groups)
    k = len(groups)
    if k < 2 or n <= k:
        return 0.0
    grand = sum(sum(g) for g in groups) / n
    ss_between = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in groups)
    ss_within = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in groups)
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (n - k)
    m0 = (n - sum(len(g) ** 2 for g in groups) / n) / (k - 1)
    if ms_within <= 0 or m0 <= 0:
        return 0.0
    icc = (ms_between - ms_within) / (ms_between + (m0 - 1) * ms_within)
    return max(0.0, min(1.0, icc))


def _arms_of(comparison: Comparison) -> tuple[Arm, Arm]:
    from arena.experiments.hc_v0_6.estimators import FAMILY_ARMS

    return FAMILY_ARMS[comparison]


def unavailable_identity_control(reference: PairedEffect) -> PairedEffect:
    """A stand-in for C1 that is **not a measurement** and must never be reported as one.

    ``k = 1`` makes the identity control unconstructible (spec §10b).  The calibration machinery
    needs a C1 slot to produce its verdict, and it already has the right behaviour for one that
    was never measured: :attr:`ControlReading.measured` is ``False``, the C1 gate is routed round
    entirely, and ``identity_informative`` reports the truth.  This builds exactly that reading,
    with **zero anchors**, so no reader can mistake it for an estimate of anything.

    Every statistic is rebuilt degenerate.  It used to be a ``dataclasses.replace`` of the C1b
    effect that reset ``delta`` and the interval but left ``permutation`` alone -- so the C1 gate
    decided on C1b's p-value, and the reason string the run would have published was "C1 identity
    control is significant (Delta=+0.0000, p=0.0040)": a delta of exactly zero beside a p-value
    from a different contrast (``docs/HC_V0_6_REDTEAM.md`` RT-V06-05).  Nothing inferential is
    inherited here; only ``R_A``'s own marginal, which is ``R_A``'s under either name because both
    arms of C1 are ``R_A``.

    The runtime noise floor C1 would have estimated is measured directly instead: 1.02% per-call
    tactic flips over 1,566 calls, implying a standard error near 0.4 percentage points at this
    sample size -- an order of magnitude under ``delta_min``.
    """

    from dataclasses import replace

    note = (
        "C1 is structurally UNAVAILABLE at k=1 (spec 10b): not measured, not zero, decides nothing"
    )
    return replace(
        reference,
        comparison=Comparison.C1_IDENTITY,
        arm_a=Arm.R_A,
        arm_b=Arm.R_A,
        n_anchors=0,
        n_clusters=0,
        rate_a=reference.rate_a,
        rate_b=reference.rate_a,
        delta=0.0,
        delta_ci95=(0.0, 0.0),
        delta_ci95_anchor_naive=(0.0, 0.0),
        mcnemar=McNemarResult(
            collapse=ReplicateCollapse.FIRST_REPLICATE,
            n_pairs=0,
            n10=0,
            n01=0,
            p_value=1.0,
            reportable=False,
            note=note,
        ),
        permutation=_unavailable_permutation(PermutationUnit.CLUSTER, note),
        permutation_anchor_naive=_unavailable_permutation(PermutationUnit.ANCHOR, note),
        marginal_a=reference.marginal_a,
        marginal_b=reference.marginal_a,
    )


def _unavailable_permutation(unit: PermutationUnit, note: str) -> PermutationResult:
    """A permutation result for a test that was never run: ``p = 1.0``, nothing borrowed."""

    return PermutationResult(
        unit=unit,
        permutations=0,
        delta=0.0,
        p_value=1.0,
        null_mean=0.0,
        null_sd=0.0,
        null_quantiles=(0.0, 0.0),
        reportable=False,
        note=note,
    )


def build_report(
    table: CellTable,
    *,
    bank_path: Path,
    model: str,
    arms: Sequence[Arm],
    preflight_baseline: float | None = None,
    seed: int = 20260908,
) -> dict[str, Any]:
    """The frozen report for one cell table.  Arithmetic only; every threshold came from the spec.

    ``preflight_baseline`` is the ``R_A``-only preflight event rate this model was selected on
    (spec §7a), and it is the *sole* input to ``T_ablate`` (§10a).  It defaults to the frozen
    :data:`PREFLIGHT_BASELINE_RATES` entry for ``model`` and must be supplied for a model not in
    that table; there is no path that lets the C2 magnitude threshold be skipped.
    """

    baseline_preflight = (
        PREFLIGHT_BASELINE_RATES.get(model) if preflight_baseline is None else preflight_baseline
    )
    if baseline_preflight is None:
        raise DesignViolation(
            f"no frozen preflight baseline for {model!r} (spec 7a) and none supplied: T_ablate "
            "cannot be computed, and spec 10a forbids deriving it from this run's own outcomes"
        )
    t_ablate = t_ablate_from_preflight_baseline(baseline_preflight)

    # C1 is excluded from the subset filter rather than tested by it.  Its arms are (R_A, R_A), so
    # ``set(_arms_of(C1)) <= set(arms)`` is true whenever R_A was played and the driver went on to
    # call ``estimate_pair`` -> ``split_half_identity``, which raises at k = 1 -- the frozen design
    # (spec §5).  The result was that the preregistered analysis crashed on the run it was written
    # for (``docs/HC_V0_6_REDTEAM.md`` RT-V06-04).  C1 is now attempted separately and, when it is
    # unconstructible, reported UNAVAILABLE rather than as a measurement or as a zero (§10b).
    available = [
        c
        for c in PREREGISTERED_FAMILY
        if c is not Comparison.C1_IDENTITY and set(_arms_of(c)) <= set(arms)
    ]
    effects: dict[Comparison, PairedEffect] = {
        c: estimate_pair(table, c, seed=seed) for c in available
    }
    identity_status = "NOT_PLAYED"
    if Arm.R_A in set(arms):
        try:
            effects[Comparison.C1_IDENTITY] = estimate_pair(
                table, Comparison.C1_IDENTITY, seed=seed
            )
            identity_status = "MEASURED"
        except IdentityControlUnavailable as error:
            identity_status = f"UNAVAILABLE_AT_K1 (spec 10b): {error}"

    # The family size stays 4: a control we could not measure must not make the primary easier.
    p_values = {c: 1.0 for c in PREREGISTERED_FAMILY}
    p_values.update({c: e.permutation.p_value for c, e in effects.items()})
    holm = holm_family(p_values)

    marginals = {
        str(arm.value): arm_marginal(table, arm).to_dict()
        for arm in arms
        if any(row.analysable for row in table.rows_for(arm))
    }
    baseline = float(marginals.get("R_A", {}).get("rate", 0.0))
    profile = ClusterProfile.from_anchor_bank(bank_path)

    # Spec §4: a harness-decided cell is never a mathematical zero.  The estimators drop them
    # structurally; this is the count a reader needs in order to see what was dropped, and the
    # same count feeds the missingness gate below (RT-V06-01, RT-V06-06).
    excluded = table.harness_failures_by_arm()
    missing = table.unanalysable_by_arm(arms)

    payload: dict[str, Any] = {
        "schema": REPORT_VERSION,
        "model": model,
        "arms": [str(a.value) for a in arms],
        "evaluation_universe_hash": table.anchor_universe_hash,
        "cell_table_content_hash": table.content_hash,
        "cells": len(table),
        "anchors": len(table.anchor_ids),
        "clusters": len(table.cluster_ids),
        "step_result_counts": _counts(table),
        "harness_failures_by_arm": {str(a.value): n for a, n in excluded.items()},
        "anchors_dropped_from_each_contrast": {str(a.value): n for a, n in missing.items()},
        "missingness_is_arm_dependent": len(set(missing.values())) > 1,
        "balance": _balance(table, arms),
        "marginals": marginals,
        "delta_min": DELTA_MIN,
        "equivalence_bound": EQUIVALENCE_BOUND,
        "preflight_baseline_rate": baseline_preflight,
        "t_ablate": t_ablate,
        "effects": {str(c.value): e.to_dict() for c, e in effects.items()},
        "holm": {str(c.value): d.to_dict() for c, d in holm.items()},
        "holm_family_size": len(PREREGISTERED_FAMILY),
        "identity_control": identity_status,
    }

    if Comparison.PRIMARY_RB_VS_RA in effects:
        icc = realised_icc(table, Comparison.PRIMARY_RB_VS_RA)
        # RT-V06-13: the MDE must describe the contrast that was ACTUALLY analysed, not the bank
        # it was drawn from.  Any anchor lost to a harness failure leaves the bank profile
        # optimistic, which would make the §10a resolution clause less likely to fire than it
        # should -- the direction that quietly certifies a run it should have blocked.
        from arena.experiments.hc_v0_6.estimators import extract_pair

        realised_pair = extract_pair(table, *_arms_of(Comparison.PRIMARY_RB_VS_RA))
        realised_profile = ClusterProfile.from_cluster_ids(
            realised_pair.cluster_ids, label="realised-primary-contrast"
        )
        mde = minimum_detectable_effect(baseline, realised_profile, cluster_icc=icc)
        payload["cluster_profile_bank"] = profile.to_dict()
        payload["cluster_profile_analysed"] = realised_profile.to_dict()
        payload["realised_icc"] = round(icc, 4)
        payload["mde"] = mde.to_dict()
        payload["resolves_delta_min"] = bool(mde.mde <= DELTA_MIN)
        payload["t_ablate_resolvable"] = bool(t_ablate >= mde.mde)
        if Comparison.C1B_WHITESPACE in effects and Comparison.C2_ABLATION in effects:
            identity = effects.get(Comparison.C1_IDENTITY) or unavailable_identity_control(
                effects[Comparison.C1B_WHITESPACE]
            )
            verdict: CalibrationVerdict = calibrate(
                identity,
                effects[Comparison.C1B_WHITESPACE],
                effects[Comparison.C2_ABLATION],
                t_ablate=t_ablate,
                achieved_mde=mde.mde,
                missingness=missing,
            )
            payload["calibration"] = verdict.to_dict()
            try:
                released = verdict.release(
                    effects[Comparison.PRIMARY_RB_VS_RA],
                    mde,
                    delta_min=DELTA_MIN,
                    equivalence_bound=EQUIVALENCE_BOUND,
                    p_holm=holm[Comparison.PRIMARY_RB_VS_RA].p_holm,
                )
                payload["released"] = released.to_dict()
            except Exception as error:
                payload["released"] = None
                payload["release_refused"] = f"{type(error).__name__}: {error}"[:400]
    return payload


def _balance(table: CellTable, arms: Sequence[Arm]) -> dict[str, Any]:
    """Whether every anchor carried every arm exactly once, said out loud rather than assumed.

    ``CellTable.validate_balanced`` existed and was called from nowhere (RT-V06-06).  It is a
    diagnostic, not the gate -- the gate is arm-dependent missingness, which is what invalidates a
    run (spec §10, §13) -- but an unbalanced table means cells were lost, and silence about that
    is the defect.
    """

    replicates = max(
        (count for arm in arms for count in table.replicate_counts(arm).values()), default=0
    )
    if replicates < 1:
        return {"balanced": False, "detail": "no cells"}
    try:
        table.validate_balanced(tuple(arms), replicates=replicates)
    except DesignViolation as error:
        return {"balanced": False, "replicates": replicates, "detail": str(error)[:400]}
    return {"balanced": True, "replicates": replicates}


def _counts(table: CellTable) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in table:
        arm = out.setdefault(str(row.arm.value), dict.fromkeys((s.value for s in StepResult), 0))
        arm[str(row.step_result.value)] += 1
    return out


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cells", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--bank", type=Path, default=Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--preflight-baseline",
        type=float,
        default=None,
        help="the model's R_A-only preflight event rate (spec 7a); T_ablate comes from this "
        "and from nothing in the run. Defaults to the frozen table for known models.",
    )
    args = parser.parse_args(argv)

    table = CellTable.read_jsonl(args.cells)
    arms = table.arms
    report = build_report(
        table,
        bank_path=args.bank,
        model=args.model,
        arms=arms,
        preflight_baseline=args.preflight_baseline,
    )
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
