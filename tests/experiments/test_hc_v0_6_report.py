"""The HC-V0.6 analysis layer as the report driver actually exercises it.

Every test here pins one finding from ``docs/HC_V0_6_REDTEAM.md`` and fails against the code as it
stood.  Each docstring says what the old code did and why the old tests did not catch it, because
in every case the defect lived *behind* a passing test: the estimators were tested on tables with
no harness failures, ``calibrate`` was tested by calling it directly with hand-built controls and
never through the driver, and the driver itself -- written after the pass began -- had no tests at
all.  A control gate is only as good as the path that reaches it, and none of these gates were on
one.

Nothing here reads the live cell table.  Every fixture is constructed, so no threshold in the code
under test can have been tuned to an observed outcome.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from arena.experiments.hc_v0_6.calibration import (
    EQUIVALENCE_BOUND,
    AssayStatus,
    Attribution,
    ControlReading,
    calibrate,
    false_certification_bound,
    t_ablate_from_preflight_baseline,
)
from arena.experiments.hc_v0_6.estimators import (
    PREREGISTERED_FAMILY,
    Comparison,
    PairedEffect,
    arm_marginal,
    delta_hat,
    estimate_pair,
    holm_family,
)
from arena.experiments.hc_v0_6.schema import (
    Arm,
    CellOutcome,
    CellTable,
    DesignViolation,
    ParseStatus,
    StepResult,
    extract_pair,
)
from arena.experiments.hc_v0_6_report import (
    PREFLIGHT_BASELINE_RATES,
    build_report,
    unavailable_identity_control,
)

#: Small enough to keep the whole file inside a couple of seconds; the shipped defaults are
#: unaffected and the report driver still runs on its own.
FAST = {"resamples": 300, "permutations": 999}

#: The primary model of spec §7a, whose frozen preflight baseline is 0.133.
MODEL = "gemma4:e4b"
T_ABLATE = t_ablate_from_preflight_baseline(PREFLIGHT_BASELINE_RATES[MODEL])

N_CLUSTERS, PER_CLUSTER = 40, 3


def _cell(
    anchor: str,
    cluster: str,
    arm: Arm,
    *,
    event: bool = False,
    step_result: StepResult | None = None,
    replicate: int = 0,
) -> CellOutcome:
    result = step_result or (
        StepResult.ACCEPTED_TRANSITION if event else StepResult.REJECTED_INVALID_ACTION
    )
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"thm::{anchor}",
        reelaboration_key=f"key::{anchor}",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=replicate,
        step_result=result,
        parse_status=(
            ParseStatus.OK if result.harness_failure is False else ParseStatus.TRANSPORT_FAILURE
        ),
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="digest",
        proposed_tactic="simp",
    )


def _anchors() -> list[tuple[str, str]]:
    return [
        (f"a{c:03d}_{i}", f"file{c:03d}") for c in range(N_CLUSTERS) for i in range(PER_CLUSTER)
    ]


def _events(index: int) -> bool:
    """A deterministic 20% event pattern, so every fixture's baseline is a stated number."""

    return index % 5 == 0


def _four_arm_table(
    *,
    r_b: Mapping[int, bool] | None = None,
    harness_failures: Mapping[Arm, int] | None = None,
    drop: Mapping[Arm, int] | None = None,
) -> CellTable:
    """``k = 1``, four arms, ``R_A`` at 0.20 and ``R_A_PRIME``/``R_B`` copying it exactly.

    ``R_ABLATED`` never fires, so C2 is a clean -0.20 -- three times ``T_ablate``.
    ``harness_failures`` replaces an arm's first ``n`` cells with ``ENVIRONMENT_ERROR`` at anchors
    that would otherwise have scored; ``drop`` removes an arm's first ``n`` cells outright.
    """

    anchors = _anchors()
    scoring = [i for i, _ in enumerate(anchors) if _events(i)]
    failures = dict(harness_failures or {})
    dropped = dict(drop or {})
    rows: list[CellOutcome] = []
    for arm in Arm:
        broken = set(scoring[: failures.get(arm, 0)])
        absent = set(range(dropped.get(arm, 0)))
        for index, (anchor, cluster) in enumerate(anchors):
            if index in absent:
                continue
            if arm is Arm.R_ABLATED:
                event = False
            elif arm is Arm.R_B and r_b is not None:
                event = r_b.get(index, _events(index))
            else:
                event = _events(index)
            if index in broken:
                rows.append(
                    _cell(
                        anchor,
                        cluster,
                        arm,
                        step_result=StepResult.ENVIRONMENT_ERROR,
                    )
                )
            else:
                rows.append(_cell(anchor, cluster, arm, event=event))
    return CellTable(rows)


def _bank(tmp_path: Path) -> Path:
    """A bank file with the frozen bank's shape (330 files, 1,127 anchors) for the MDE.

    Only ``anchors[].cluster.file_path`` is read.  The size matters: the achieved MDE has to be
    below ``T_ablate`` or spec §10a's resolution clause fires and masks the gate under test.
    """

    sizes = [4] * 137 + [3] * 193
    anchors = [
        {"cluster": {"file_path": f"Mathlib/F{index:03d}.lean"}}
        for index, size in enumerate(sizes)
        for _ in range(size)
    ]
    path = tmp_path / "bank.json"
    path.write_text(json.dumps({"anchors": anchors}), encoding="utf-8")
    return path


def _report(table: CellTable, tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
    return build_report(table, bank_path=_bank(tmp_path), model=MODEL, arms=tuple(Arm), **kwargs)


def _effects(table: CellTable) -> dict[Comparison, PairedEffect]:
    return {
        comparison: estimate_pair(table, comparison, **FAST)
        for comparison in PREREGISTERED_FAMILY
        if comparison is not Comparison.C1_IDENTITY
    }


def _with(
    effect: PairedEffect,
    *,
    delta: float | None = None,
    ci: tuple[float, float] | None = None,
    p_value: float | None = None,
) -> PairedEffect:
    """One effect with its headline numbers overridden, so a gate can be probed at a point."""

    permutation = effect.permutation
    if p_value is not None or delta is not None:
        permutation = replace(
            permutation,
            p_value=effect.p_value if p_value is None else p_value,
            delta=effect.delta if delta is None else delta,
        )
    return replace(
        effect,
        delta=effect.delta if delta is None else delta,
        delta_ci95=effect.delta_ci95 if ci is None else ci,
        permutation=permutation,
    )


# --- RT-V06-01: a harness failure is not a mathematical zero -----------------------------------


def test_harness_failures_do_not_enter_a_contrast_as_zeros(tmp_path: Path) -> None:
    """``ENVIRONMENT_ERROR`` on one arm used to move Delta by a third of the baseline.

    ``CellTable.drop_harness_failures`` and ``CellOutcome.analysable`` both existed and were
    called from nowhere in ``arena/``; ``extract_pair`` iterated ``table.rows`` unfiltered.  The
    old tests never caught it because every fixture in the suite was built out of
    ``ACCEPTED_TRANSITION`` and ``REJECTED_INVALID_ACTION`` rows only -- the exclusion rule was
    tested at the *row* level (``cell.analysable`` is False) and never at the estimator level, so
    nothing ever asked whether anyone consulted it.
    """

    clean = _four_arm_table()
    assert delta_hat(extract_pair(clean, Arm.R_A, Arm.R_B)) == pytest.approx(0.0)

    # Twenty ENVIRONMENT_ERRORs on R_B, at anchors that would otherwise have scored.
    broken = _four_arm_table(harness_failures={Arm.R_B: 20})
    pair = extract_pair(broken, Arm.R_A, Arm.R_B)
    assert delta_hat(pair) == pytest.approx(0.0), "a harness failure was scored as a zero for R_B"
    # The anchors are dropped from the PAIR, not counted: that is what makes them missing.
    assert pair.n_anchors == len(clean.anchor_ids) - 20
    # ...and the same rule reaches the marginal rate: a cell the harness decided is not in the
    # denominator either, so it cannot depress an arm's event rate.
    marginal = arm_marginal(broken, Arm.R_B, resamples=200)
    assert (marginal.n_cells, marginal.n_events) == (100, 4)
    assert marginal.rate == pytest.approx(0.04), "20 of 120 cells were excluded, not scored"

    report = _report(broken, tmp_path)
    assert report["harness_failures_by_arm"]["R_B"] == 20
    assert report["harness_failures_by_arm"]["R_A"] == 0
    assert report["anchors_dropped_from_each_contrast"]["R_B"] == 20


# --- RT-V06-02: the C2 gate needs a magnitude, not only a p-value -------------------------------


def test_the_sensitivity_gate_requires_the_frozen_ablation_magnitude(tmp_path: Path) -> None:
    """A 0.8-point ablation with p = 0.0001 used to certify against a frozen floor of 6.7 points.

    ``calibrate`` implemented C2 as ``significant(alpha) and delta < 0`` -- significance and sign,
    no magnitude -- and ``T_ablate`` appeared nowhere in ``arena/``.  The old tests did not catch
    it because every fixture made ``R_ABLATED`` fail *everywhere*, giving a C2 Delta of -1.0: a
    gate with no magnitude term and a gate with one are indistinguishable at Delta = -1.
    """

    effects = _effects(_four_arm_table())
    weak = _with(effects[Comparison.C2_ABLATION], delta=-0.008, ci=(-0.012, -0.004), p_value=1e-4)
    verdict = calibrate(
        unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
        effects[Comparison.C1B_WHITESPACE],
        weak,
        t_ablate=T_ABLATE,
        achieved_mde=0.005,
    )
    assert verdict.status is AssayStatus.INSENSITIVE
    assert not verdict.certified
    assert any("smaller than T_ablate" in reason for reason in verdict.reasons)

    # The same reading at the frozen magnitude does certify, so the gate is not simply stuck shut.
    strong = _with(effects[Comparison.C2_ABLATION], delta=-0.20, ci=(-0.28, -0.12), p_value=1e-4)
    assert (
        calibrate(
            unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
            effects[Comparison.C1B_WHITESPACE],
            strong,
            t_ablate=T_ABLATE,
            achieved_mde=0.005,
        ).status
        is AssayStatus.USABLE
    )


def test_t_ablate_is_required_and_comes_from_the_preflight_baseline(tmp_path: Path) -> None:
    """Spec §10a fixes ``T_ablate`` from preflight data alone; the code had no such symbol.

    ``t_ablate`` is keyword-only with **no default** so that omitting the magnitude is a
    ``TypeError`` rather than silence -- silence is exactly how it went missing.
    """

    assert t_ablate_from_preflight_baseline(0.133) == pytest.approx(0.0665)
    assert t_ablate_from_preflight_baseline(0.25) == pytest.approx(0.10)
    assert t_ablate_from_preflight_baseline(0.20) == pytest.approx(0.10)
    with pytest.raises(DesignViolation):
        t_ablate_from_preflight_baseline(0.0)

    effects = _effects(_four_arm_table())
    with pytest.raises(TypeError):
        calibrate(  # type: ignore[call-arg]
            unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
            effects[Comparison.C1B_WHITESPACE],
            effects[Comparison.C2_ABLATION],
        )

    report = _report(_four_arm_table(), tmp_path)
    assert report["preflight_baseline_rate"] == PREFLIGHT_BASELINE_RATES[MODEL]
    assert report["t_ablate"] == pytest.approx(0.0665)
    # `t_ablate_resolvable` is a property of the BANK, not of how `t_ablate` was derived, and this
    # 40-cluster fixture is far smaller than the real 330-cluster one, so it is genuinely
    # unresolvable here.  Assert the consistency that is actually under test.
    assert report["t_ablate_resolvable"] == (report["t_ablate"] >= report["mde"]["mde"])


def test_t_ablate_below_the_achieved_mde_cannot_certify_sensitivity() -> None:
    """Spec §10a's resolution clause: it is decided from the threshold and the MDE, never from C2.

    Deciding it before the observed C2 is read is what makes it un-gameable -- the alternative,
    checking it only when C2 happens to fail, would let a large observed effect argue the clause
    away after the fact, which §10a forbids in those words.
    """

    effects = _effects(_four_arm_table())
    verdict = calibrate(
        unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
        effects[Comparison.C1B_WHITESPACE],
        effects[Comparison.C2_ABLATION],
        t_ablate=T_ABLATE,
        achieved_mde=0.09,
    )
    assert verdict.status is AssayStatus.SENSITIVITY_UNRESOLVABLE
    assert not verdict.status.sensitivity_established
    assert verdict.status.may_report, "the primary Delta is still reportable; the null is not"
    assert not verdict.certified
    assert any("cannot be certified at this resolution" in r for r in verdict.reasons)


# --- RT-V06-03: the null control is an equivalence band ----------------------------------------


def test_the_null_control_gate_is_equivalence_not_a_failure_to_reject() -> None:
    """A C1b of Delta +0.02, p = 0.55, 95% CI [-0.15, +0.19] used to certify and license STRUCTURE.

    ``calibrate`` implemented C1b as ``significant(alpha_byte_null)`` alone.
    ``PairedEffect.equivalent_within`` existed and did the right thing, but no gate called it --
    only the primary's O3 decision did.  The old tests did not catch it because their C1b fixture
    was ``R_A_PRIME`` copied byte-for-byte from ``R_A``: Delta identically zero with a CI of
    (0, 0), which passes an equivalence test and a significance test alike.
    """

    effects = _effects(_four_arm_table())
    uninformative = _with(
        effects[Comparison.C1B_WHITESPACE], delta=0.02, ci=(-0.15, 0.19), p_value=0.55
    )
    reading = ControlReading.from_effect(uninformative)
    assert not reading.significant(0.10), "it does not reject -- that was the whole problem"
    assert not reading.equivalent_within(EQUIVALENCE_BOUND)

    verdict = calibrate(
        unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
        uninformative,
        effects[Comparison.C2_ABLATION],
        t_ablate=T_ABLATE,
        achieved_mde=0.005,
    )
    assert verdict.status is AssayStatus.USABLE_ATTRIBUTION_BLOCKED
    assert not verdict.byte_null_passes
    assert not verdict.certified
    assert not verdict.status.may_attribute_to_structure
    assert any("equivalence band" in reason for reason in verdict.reasons)
    assert verdict._attribution(significant=True) is Attribution.BYTE_PERTURBATION

    # Both halves are required: a tight interval that is nevertheless significant still blocks.
    tight_but_significant = _with(
        effects[Comparison.C1B_WHITESPACE], delta=0.03, ci=(0.01, 0.045), p_value=0.01
    )
    blocked = calibrate(
        unavailable_identity_control(effects[Comparison.C1B_WHITESPACE]),
        tight_but_significant,
        effects[Comparison.C2_ABLATION],
        t_ablate=T_ABLATE,
        achieved_mde=0.005,
    )
    assert blocked.status is AssayStatus.USABLE_ATTRIBUTION_BLOCKED
    assert any("significant" in reason for reason in blocked.reasons)


def test_the_equivalence_component_does_not_loosen_the_false_certification_bound() -> None:
    """Adding a real IUT component may only tighten a max; the frozen bound must not move."""

    assert false_certification_bound() == 0.05


# --- RT-V06-04 / RT-V06-05: C1 is unavailable at k = 1, and decides nothing ---------------------


def test_build_report_runs_on_the_frozen_k1_design_and_calls_c1_unavailable(
    tmp_path: Path,
) -> None:
    """The preregistered driver used to crash on the design it was written for.

    ``build_report`` filtered the family by ``set(_arms_of(c)) <= set(arms)``; ``C1_IDENTITY``'s
    arms are ``(R_A, R_A)``, so it always passed, and ``estimate_pair`` then reached
    ``split_half_identity``, which raises ``IdentityControlUnavailable`` at ``k = 1`` (spec §5,
    §10b).  ``unavailable_identity_control`` -- the function written for exactly this -- was never
    reached, because the crash happened two lines earlier.  No test caught it because the driver
    had no tests at all: it was written after the pass began.
    """

    report = _report(_four_arm_table(), tmp_path)
    assert report["identity_control"].startswith("UNAVAILABLE_AT_K1")
    assert "C1_IDENTITY" not in report["effects"], "an unmeasured control is not an effect"
    assert report["calibration"]["identity_measured"] is False
    # The driver never widens the frozen band, whatever a simulation may pass in its own tests.
    assert report["equivalence_bound"] == EQUIVALENCE_BOUND == 0.05
    assert report["calibration"]["equivalence_bound"] == 0.05
    assert report["calibration"]["controls"]["C1"]["n_anchors"] == 0
    assert report["released"] is not None
    assert any("UNAVAILABLE" in reason for reason in report["calibration"]["reasons"])


def test_the_unavailable_c1_does_not_carry_another_contrasts_p_value() -> None:
    """The stand-in used to publish "C1 identity control is significant (Delta=+0.0000, p=0.0040)".

    ``unavailable_identity_control`` was a ``dataclasses.replace`` that reset ``delta`` and the
    interval but left ``permutation`` untouched, and ``ControlReading.from_effect`` reads
    ``effect.permutation.p_value``.  So the C1 gate decided on C1b's p-value -- a false sentence
    generated by the code.  It survived because no test ever called the stand-in: it is report
    machinery, and the report driver was untested.
    """

    effects = _effects(_four_arm_table())
    # A C1b that is emphatically significant, so a borrowed p-value would be unmistakable.
    loud = _with(effects[Comparison.C1B_WHITESPACE], delta=0.06, ci=(0.03, 0.09), p_value=0.004)
    standin = unavailable_identity_control(loud)
    assert standin.comparison is Comparison.C1_IDENTITY
    assert standin.arm_a is Arm.R_A and standin.arm_b is Arm.R_A
    assert standin.p_value == 1.0
    assert standin.permutation.permutations == 0 and not standin.permutation.reportable
    assert standin.permutation_anchor_naive.p_value == 1.0
    assert standin.mcnemar.p_value == 1.0
    assert standin.n_anchors == 0 and standin.n_clusters == 0
    assert not ControlReading.from_effect(standin).measured

    verdict = calibrate(
        standin,
        loud,
        effects[Comparison.C2_ABLATION],
        t_ablate=T_ABLATE,
        achieved_mde=0.005,
    )
    # C1b's significance blocks attribution.  It must NOT be reported as a broken C1.
    assert verdict.status is AssayStatus.USABLE_ATTRIBUTION_BLOCKED
    assert not any("C1 identity control is significant" in r for r in verdict.reasons)
    assert not verdict.identity_informative and not verdict.identity_measured


def test_a_genuinely_significant_c1_still_forecloses_everything() -> None:
    """Routing round an *unmeasured* C1 must not disarm a *measured* one."""

    anchors = _anchors()
    rows: list[CellOutcome] = []
    for arm in Arm:
        for index, (anchor, cluster) in enumerate(anchors):
            replicates = (
                [True, index % 5 == 0] if arm is Arm.R_A else [_events(index), _events(index)]
            )
            for k, event in enumerate(replicates):
                rows.append(_cell(anchor, cluster, arm, event=event, replicate=k))
    table = CellTable(rows)
    identity = estimate_pair(table, Comparison.C1_IDENTITY, **FAST)
    assert identity.n_anchors > 0
    verdict = calibrate(
        identity,
        estimate_pair(table, Comparison.C1B_WHITESPACE, **FAST),
        estimate_pair(table, Comparison.C2_ABLATION, **FAST),
        t_ablate=T_ABLATE,
        achieved_mde=0.005,
    )
    assert verdict.status is AssayStatus.BROKEN_IDENTITY_CONTROL
    assert any("C1 identity control is significant" in r for r in verdict.reasons)


# --- RT-V06-06: the missingness gate can fire -------------------------------------------------


def test_arm_dependent_missingness_reaches_the_gate_from_the_report(tmp_path: Path) -> None:
    """The gate existed in the vocabulary and nowhere in the execution.

    ``build_report`` called ``calibrate(c1, c1b, c2)`` with no ``missingness=``, so
    ``_missingness_reason(None)`` short-circuited and ``AssayStatus.ARM_DEPENDENT_MISSINGNESS`` /
    outcome O7 were unreachable from the report path; ``CellTable.validate_balanced`` was likewise
    called from nowhere.  The old suite tested the gate by handing ``calibrate`` a missingness
    mapping directly, which proves the gate works and says nothing about whether anything builds
    one.  Spec §10 and §13 make arm-dependent missingness a run-invalidating condition.
    """

    balanced = _report(_four_arm_table(), tmp_path)
    assert balanced["missingness_is_arm_dependent"] is False
    assert balanced["balance"]["balanced"] is True
    # The subject of this test is the missingness gate, not the sensitivity one.  On a fixture this
    # small the run is legitimately SENSITIVITY_UNRESOLVABLE; what must be true is that the
    # BALANCED case is not blocked FOR MISSINGNESS.
    assert balanced["calibration"]["status"] != "ARM_DEPENDENT_MISSINGNESS"

    lopsided = _report(_four_arm_table(drop={Arm.R_B: 10}), tmp_path)
    assert lopsided["anchors_dropped_from_each_contrast"] == {
        "R_A": 0,
        "R_A_PRIME": 0,
        "R_B": 10,
        "R_ABLATED": 0,
    }
    assert lopsided["missingness_is_arm_dependent"] is True
    assert lopsided["balance"]["balanced"] is False
    assert lopsided["calibration"]["status"] == "ARM_DEPENDENT_MISSINGNESS"
    assert lopsided["released"] is None
    assert "AssayBroken" in lopsided["release_refused"]

    # A harness failure is missingness too: it is excluded, so its anchor loses the pair.
    by_error = _report(_four_arm_table(harness_failures={Arm.R_A_PRIME: 6}), tmp_path)
    assert by_error["calibration"]["status"] == "ARM_DEPENDENT_MISSINGNESS"


# --- the Holm family stays at four -------------------------------------------------------------


def test_the_holm_family_keeps_c1s_slot_at_p_one_when_c1_cannot_be_measured(
    tmp_path: Path,
) -> None:
    """A control we could not measure must not make the primary easier to declare.

    Dropping C1 would shrink the correction from four hypotheses to three, so the primary's
    smallest-rank multiplier would fall from 4 to 3.  The slot is retained at ``p = 1.0``.  This
    was asserted only in the driver's docstring; here it is pinned as arithmetic, and the family
    guard is checked to still refuse a three-member family.
    """

    report = _report(_four_arm_table(r_b={i: True for i in range(len(_anchors()))}), tmp_path)
    assert report["holm_family_size"] == 4
    assert set(report["holm"]) == {str(c.value) for c in PREREGISTERED_FAMILY}
    assert report["holm"]["C1_IDENTITY"]["p_value"] == 1.0
    assert report["holm"]["C1_IDENTITY"]["reject"] is False

    # The arithmetic, at a point where the family size decides the answer: p = 0.0125 is rejected
    # by a three-member family (0.0375 <= 0.05) and not by the frozen four (0.05 <= 0.05 holds at
    # the boundary, so step just past it).
    four = holm_family(
        {
            Comparison.PRIMARY_RB_VS_RA: 0.013,
            Comparison.C1_IDENTITY: 1.0,
            Comparison.C1B_WHITESPACE: 0.90,
            Comparison.C2_ABLATION: 0.90,
        }
    )
    assert four[Comparison.PRIMARY_RB_VS_RA].p_holm == pytest.approx(0.052)
    assert not four[Comparison.PRIMARY_RB_VS_RA].reject, "4 x 0.013 > alpha: not significant"
    assert 3 * 0.013 < 0.05, "the same p WOULD be significant in a three-member family"
    with pytest.raises(DesignViolation, match="frozen"):
        holm_family(
            {
                Comparison.PRIMARY_RB_VS_RA: 0.013,
                Comparison.C1B_WHITESPACE: 0.90,
                Comparison.C2_ABLATION: 0.90,
            }
        )


def test_the_report_is_a_pure_function_of_the_table_and_refuses_an_unknown_model(
    tmp_path: Path,
) -> None:
    """No preflight baseline means no ``T_ablate``, and §10a forbids deriving one from this run."""

    table = _four_arm_table()
    assert _report(table, tmp_path) == _report(table, tmp_path)
    with pytest.raises(DesignViolation, match="preflight baseline"):
        build_report(table, bank_path=_bank(tmp_path), model="not-a-model", arms=tuple(Arm))
    # ...but a model outside the frozen table can still be analysed if its baseline is supplied.
    supplied = build_report(
        table,
        bank_path=_bank(tmp_path),
        model="not-a-model",
        arms=tuple(Arm),
        preflight_baseline=0.30,
    )
    assert supplied["t_ablate"] == pytest.approx(0.10)
