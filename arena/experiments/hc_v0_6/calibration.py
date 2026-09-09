r"""The control-calibration verdict: whether HC-V0.6's assay may be reported at all.

Design brief §4 states the rule this module exists to make mechanical:

    *"**C1 — identity/null control.** ``R_A`` against ``R_A``, two independent draws. Expected
    Δ ≈ 0. This is the runtime-noise floor. If C1 is 'significant' under the preregistered test,
    **the assay is broken and no other comparison may be reported.**"*

A rule of that shape written only in a docstring is advice, and advice is ignorable.  Here it is a
**typed outcome with a gate**: the primary Δ is not an attribute anyone can read off a verdict, it
is the return value of :meth:`CalibrationVerdict.release`, and ``release`` raises
:class:`AssayBroken` when C1 is significant.  The package offers no other route from a
:class:`~arena.experiments.hc_v0_6.estimators.PairedEffect` to a :class:`ReportableResult`.
Python cannot make the dataclass unconstructible, and that is not the claim: the claim is that the
gate cannot be *forgotten* — only bypassed on purpose, in a line of code that says so.

Three controls, three different jobs
------------------------------------

============  ==============================  ======================================================
control       arms                            what its failure costs
============  ==============================  ======================================================
**C1**        ``R_A`` vs ``R_A``              the assay is BROKEN; nothing may be reported (O1)
**C1b**       ``R_A`` vs ``R_A_PRIME``        the effect may not be attributed to STRUCTURE (§9.4)
**C2**        ``R_A`` vs ``R_ABLATED``        no demonstrated sensitivity; a null is UNINFORMATIVE
============  ==============================  ======================================================

The §9.4 reading rule, verbatim in behaviour
--------------------------------------------
*"``Δ(R_A, R_A′) ≈ 0`` and ``Δ(R_A, R_B) ≠ 0`` → the effect is attributable to **structure**, not
to the mere fact that bytes changed; both non-zero → the model is sensitive to byte perturbation as
such, and ``R_B``'s effect cannot be attributed to its structure. That is a finding about the
assay, and it would block a representation claim."*

:class:`Attribution` is that sentence as an enum, and
:attr:`ReportableResult.may_claim_structure` is that sentence as a boolean.

Certification is an INTERSECTION-UNION test, so no Holm correction belongs here
-------------------------------------------------------------------------------
There are two testing problems in HC-V0.6 and they have opposite shapes.  Conflating them is the
error this section exists to prevent, and "uncorrected liberal alpha" -- the phrase an earlier
draft used -- is not the reason; it is a description of the symptom.

**The problem.**  Certification means *every* required control gate passed.  Write the gates
:math:`j = 1 \dots J` with component nulls :math:`H_j` ("gate *j* is unsafe").  The global null is
their **union**

.. math::  H \;=\; \bigcup_j H_j \qquad\text{("at least one required gate is unsafe")}

and certification is the **intersection** of the component rejections,
:math:`C = \bigcap_j R_j`, where :math:`R_j` is the event that gate *j* rejects :math:`H_j` at its
own level :math:`\alpha_j`.  A decision of that shape is an *intersection-union test* (IUT).

**The proposition.**  For any parameter :math:`\theta \in H` there is at least one index
:math:`j^{*}(\theta)` with :math:`\theta \in H_{j^{*}}` -- that is what belonging to a union
means.  Certification requires :math:`R_{j^{*}}` among the others, so

.. math::  P_{\theta}(C) \;\le\; P_{\theta}(R_{j^{*}}) \;\le\; \alpha_{j^{*}} \;\le\; \max_j \alpha_j .

The false-**certification** rate is therefore at most :math:`\max_j \alpha_j` with **separate,
uncorrected, level-**:math:`\alpha_j` **component tests**.  The conservatism is automatic and is
usually strict, because certification also demands the other :math:`J-1` rejections, none of which
the bound uses.  This is Berger's IUT (Berger 1982, *Technometrics* 24:295-300; Berger & Hsu 1996,
*Statistical Science* 11:283-319) -- the same argument that makes TOST bioequivalence a valid
level-α procedure from two uncorrected one-sided tests.

**Holm would not be conservative here; it would be wrong.**  Holm controls the family-wise error
rate of a *union* decision ("reject if ANY member rejects").  Certification is an *intersection*
decision.  Inflating each component p-value cannot lower a false-certification rate that is
already :math:`\le \alpha`; all it can do is lower the *true*-certification rate -- i.e. raise the
false-**block** rate.  On the governing philosophy (**false block ≫ false certification**) that
trade is acceptable in isolation, but it buys nothing, and on the gates written as
*non*-rejections it is actively harmful: a Holm-inflated p-value is *less* likely to trip C1's
"the assay is broken" verdict, which raises the false-certification rate in the one place the IUT
bound does not reach.

**The bound does not cover every gate, and saying so is the honest part.**  Only a gate whose
component null is the *unsafe* state, and which must **reject** to certify, is an IUT component:

* **C2** (sensitivity) is one.  :math:`H_{C2}`: "the assay cannot detect the removal of the goal
  text", i.e. :math:`\Delta_{C2} = 0`.  Certifying requires rejecting it at
  :data:`ALPHA_SENSITIVITY`, so its contribution to the false-certification rate is
  :math:`\le \alpha`.  :func:`false_certification_bound` is exactly this maximum.
* **C1** (identity) and **C1b** (byte null) are **not**.  Their safe state is :math:`\Delta = 0`,
  so as written they *block* on a rejection and certify on a **failure to reject** -- which is not
  a level-α statement about anything.  What governs them is **power**: the probability of catching
  a broken instrument.  That is why :data:`ALPHA_IDENTITY` and :data:`ALPHA_BYTE_NULL` are set
  *above* the primary α (0.10): raising a blocking gate's α raises its power, which is the only
  knob that lowers false certification through C1.  Turning them into IUT components would mean
  replacing them with equivalence tests (TOST against :math:`\delta_{eq}`), which the design
  already provides for C1b's *licensing* direction and which a later manifest version may adopt
  for the blocking direction as well.  Until it does, C1's contribution to false certification is
  bounded by its power, not by its α, and no report may claim otherwise.

So: the effect claims are Holm-corrected across the four-member family of design brief §9.4
(:data:`~arena.experiments.hc_v0_6.estimators.PREREGISTERED_FAMILY`); the certification gates are
not, and the IUT proposition above -- not liberality, not convention -- is why.  The two rules
never touch: :func:`calibrate` reads no Holm-adjusted p-value anywhere, and
:func:`~arena.experiments.hc_v0_6.estimators.holm_family` is never consulted by a gate.

Determinism
-----------
If the Solver is call-for-call deterministic under the frozen decoding, C1 compares two
byte-identical prompts and its Δ is exactly zero *by construction*.  :class:`ControlReading` detects
that (every per-anchor difference zero) and marks the reading :attr:`~ControlReading.degenerate`.
A degenerate C1 is **not** evidence that the analysis pipeline is calibrated — it is evidence that
the Solver is a function.  The verdict says so in :attr:`CalibrationVerdict.reasons` and
:attr:`CalibrationVerdict.identity_informative` is ``False``, which is exactly the situation in
which C1b carries the whole weight of the null control.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from arena.experiments.hc_v0_6.estimators import ALPHA, Comparison, PairedEffect
from arena.experiments.hc_v0_6.power import MinimumDetectableEffect
from arena.experiments.hc_v0_6.schema import Arm, DesignViolation

__all__ = [
    "ALPHA_BYTE_NULL",
    "ALPHA_IDENTITY",
    "ALPHA_SENSITIVITY",
    "CERTIFICATION_GATES",
    "MIN_CLUSTERS",
    "AssayBroken",
    "AssayStatus",
    "Attribution",
    "CalibrationVerdict",
    "CertificationGate",
    "ControlReading",
    "GateDirection",
    "Outcome",
    "ReportableResult",
    "calibrate",
    "false_certification_bound",
]

#: C1's level.  Uncorrected and deliberately LIBERAL: it must be at least the primary α, because
#: the conservative direction for an instrument check is "easier to declare broken"
#: (``docs/HC_V0_6_PREREGISTRATION.md`` §5).  Experimentalist's slot; frozen here before any data.
ALPHA_IDENTITY: Final = 0.10
#: C1b's level.  Same argument as C1: a byte-sensitivity finding should be easy to reach, because
#: reaching it only ever *blocks* a claim.
ALPHA_BYTE_NULL: Final = 0.10
#: C2's level.  Uncorrected; its *failure* is the conservative outcome, so no correction is needed
#: to make it safe.
ALPHA_SENSITIVITY: Final = ALPHA
#: Below this many contributing clusters, cluster-robust inference is not trustworthy at any α and
#: the run is outcome O6 rather than a result.  The rebuilt bank has 330 files.
MIN_CLUSTERS: Final = 30


class GateDirection(StrEnum):
    """How a certification gate is written, because that decides what its α means.

    This is the distinction the module docstring's IUT section turns on, and it is an enum rather
    than a comment so that a gate cannot be added without declaring which kind it is.
    """

    #: The component null is the UNSAFE state and the gate must REJECT it to certify.  An IUT
    #: component: its contribution to the false-certification rate is bounded by its own α, with
    #: no multiplicity correction (Berger 1982).
    REJECT_TO_CERTIFY = "REJECT_TO_CERTIFY"
    #: The component null is the SAFE state and the gate BLOCKS on a rejection.  **Not** an IUT
    #: component: certifying here is a failure to reject, which bounds nothing.  What governs it
    #: is power, which is why its α is set at or above the primary α.
    BLOCK_ON_REJECTION = "BLOCK_ON_REJECTION"

    @property
    def bounded_by_alpha(self) -> bool:
        """Whether this gate's false-certification contribution is bounded by its own α."""

        return self is GateDirection.REJECT_TO_CERTIFY


@dataclass(frozen=True, slots=True)
class CertificationGate:
    """One required control gate, with the component null it is a test of.

    Declared so the IUT argument is checkable against the code rather than asserted beside it:
    ``tests/experiments/test_hc_v0_6_analysis.py`` asserts that these α values are the ones
    :func:`calibrate` actually uses, so the roster cannot drift away from the gates.
    """

    name: str
    comparison: Comparison
    direction: GateDirection
    alpha: float
    #: The component null H_j, in words.  For a REJECT_TO_CERTIFY gate this is the unsafe state.
    component_null: str


#: The required gates, and the shape of each.  Certification is the INTERSECTION of their passes,
#: so the global null is the UNION of the component nulls below -- "at least one gate is unsafe".
CERTIFICATION_GATES: Final[tuple[CertificationGate, ...]] = (
    CertificationGate(
        name="C2",
        comparison=Comparison.C2_ABLATION,
        direction=GateDirection.REJECT_TO_CERTIFY,
        alpha=ALPHA_SENSITIVITY,
        component_null="the assay cannot detect the removal of the goal text (Delta_C2 = 0)",
    ),
    CertificationGate(
        name="C1",
        comparison=Comparison.C1_IDENTITY,
        direction=GateDirection.BLOCK_ON_REJECTION,
        alpha=ALPHA_IDENTITY,
        component_null="the assay reports no difference where there is none (Delta_C1 = 0)",
    ),
    CertificationGate(
        name="C1b",
        comparison=Comparison.C1B_WHITESPACE,
        direction=GateDirection.BLOCK_ON_REJECTION,
        alpha=ALPHA_BYTE_NULL,
        component_null="a whitespace-only change does not move the outcome (Delta_C1b = 0)",
    ),
)


def false_certification_bound(
    gates: Sequence[CertificationGate] = CERTIFICATION_GATES,
) -> float:
    """The IUT bound on ``P(certify | at least one required gate is unsafe)``.

    ``max_j alpha_j`` over the :attr:`GateDirection.REJECT_TO_CERTIFY` gates, and **only** those:
    a :attr:`GateDirection.BLOCK_ON_REJECTION` gate certifies by failing to reject, which bounds
    nothing, so it contributes no term.  Returning a number that quietly folded C1 in would be the
    exact overclaim this module exists to refuse.

    The bound needs no Holm correction and admits none: certification is an intersection of
    rejections, and inflating the component p-values can only raise the false-*block* rate.
    """

    bounded = [gate.alpha for gate in gates if gate.direction.bounded_by_alpha]
    if not bounded:
        raise DesignViolation(
            "no REJECT_TO_CERTIFY gate: with only blocking gates, certification is a failure to "
            "reject and its error rate is not bounded by any alpha"
        )
    return max(bounded)


class AssayBroken(DesignViolation):
    """An attempt to report a result from an assay its own controls disqualified."""


class Outcome(StrEnum):
    """The exhaustive outcome ladder of ``docs/HC_V0_6_PREREGISTRATION.md`` §8.

    Evaluated **in order**: O1 forecloses everything, O2 forecloses O3.
    """

    O1_INSTRUMENT_INVALID = "O1_INSTRUMENT_INVALID"
    O2_NULL_WITHOUT_SENSITIVITY = "O2_NULL_WITHOUT_SENSITIVITY"
    O3_INFORMATIVE_NULL = "O3_INFORMATIVE_NULL"
    O4_FAVOURS_R_B = "O4_FAVOURS_R_B"
    O5_FAVOURS_R_A = "O5_FAVOURS_R_A"
    O6_UNDERPOWERED = "O6_UNDERPOWERED"
    O7_ARM_DEPENDENT_MISSINGNESS = "O7_ARM_DEPENDENT_MISSINGNESS"

    @property
    def sentinel(self) -> str | None:
        """The §43 sentinel this outcome must be published under, if any."""

        return {
            Outcome.O1_INSTRUMENT_INVALID: "INSTRUMENT_INVALID",
            Outcome.O2_NULL_WITHOUT_SENSITIVITY: "LANDSCAPE_NOT_ESTABLISHED",
            Outcome.O3_INFORMATIVE_NULL: "NO_PRACTICALLY_USEFUL_LANGUAGE_EFFECT_FOUND",
            Outcome.O6_UNDERPOWERED: "LANDSCAPE_NOT_ESTABLISHED",
            Outcome.O7_ARM_DEPENDENT_MISSINGNESS: "INSTRUMENT_INVALID",
        }.get(self)


class AssayStatus(StrEnum):
    """Whether the controls permit anything to be reported, and under what restriction."""

    #: C1 significant.  Outcome O1.  Nothing may be reported.
    BROKEN_IDENTITY_CONTROL = "BROKEN_IDENTITY_CONTROL"
    #: Cells were lost differently by arm.  Outcome O7.  Nothing may be reported.
    ARM_DEPENDENT_MISSINGNESS = "ARM_DEPENDENT_MISSINGNESS"
    #: Too few contributing clusters for cluster-robust inference.  Outcome O6.
    INSUFFICIENT_CLUSTERS = "INSUFFICIENT_CLUSTERS"
    #: C2 failed: no demonstrated sensitivity.  A non-null Δ may still be reported; a null may not
    #: be read as evidence of absence (outcome O2).
    INSENSITIVE = "INSENSITIVE"
    #: C1 passed, C2 passed, but C1b is significant: the Solver responds to byte perturbation as
    #: such, so an effect cannot be attributed to structure (design brief §9.4).
    USABLE_ATTRIBUTION_BLOCKED = "USABLE_ATTRIBUTION_BLOCKED"
    #: Every control behaved.  The full reading is available.
    USABLE = "USABLE"

    @property
    def may_report(self) -> bool:
        """Whether ANY comparison may be reported.  False is the fail-closed direction."""

        return self not in {
            AssayStatus.BROKEN_IDENTITY_CONTROL,
            AssayStatus.ARM_DEPENDENT_MISSINGNESS,
            AssayStatus.INSUFFICIENT_CLUSTERS,
        }

    @property
    def sensitivity_established(self) -> bool:
        """Whether C2 demonstrated the assay can detect anything at all."""

        return self in {AssayStatus.USABLE, AssayStatus.USABLE_ATTRIBUTION_BLOCKED}

    @property
    def may_attribute_to_structure(self) -> bool:
        return self is AssayStatus.USABLE


class Attribution(StrEnum):
    """Design brief §9.4, as a value.  What a non-null primary Δ may be attributed to."""

    #: ``Δ(R_A, R_A′) ≈ 0`` and ``Δ(R_A, R_B) ≠ 0``: attributable to STRUCTURE.
    STRUCTURE = "STRUCTURE"
    #: Both non-zero: the Solver is sensitive to byte perturbation as such.  Blocks the claim.
    BYTE_PERTURBATION = "BYTE_PERTURBATION"
    #: The primary Δ is null, so there is no effect to attribute.
    NO_EFFECT_TO_ATTRIBUTE = "NO_EFFECT_TO_ATTRIBUTE"
    #: The controls did not license any attribution (assay broken, or C2 failed).
    UNDETERMINED = "UNDETERMINED"

    @property
    def licenses_structure_claim(self) -> bool:
        return self is Attribution.STRUCTURE


@dataclass(frozen=True, slots=True)
class ControlReading:
    """One control's numbers, read off a :class:`PairedEffect` and never re-derived by hand."""

    comparison: Comparison
    delta: float
    ci95: tuple[float, float]
    #: The PREREGISTERED cluster permutation p-value, **uncorrected**.  See the module docstring.
    p_value: float
    n_anchors: int
    n_clusters: int
    #: Every per-anchor difference is exactly zero, so Δ is zero by construction rather than by
    #: measurement.  True for C1 whenever the Solver is call-for-call deterministic.
    degenerate: bool

    @classmethod
    def from_effect(cls, effect: PairedEffect) -> ControlReading:
        return cls(
            comparison=effect.comparison,
            delta=effect.delta,
            ci95=effect.delta_ci95,
            p_value=effect.p_value,
            n_anchors=effect.n_anchors,
            n_clusters=effect.n_clusters,
            degenerate=effect.delta == 0.0 and effect.delta_ci95 == (0.0, 0.0),
        )

    def significant(self, alpha: float) -> bool:
        return self.p_value <= alpha

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison": str(self.comparison.value),
            "delta": self.delta,
            "ci95": list(self.ci95),
            "p_value_uncorrected": self.p_value,
            "n_anchors": self.n_anchors,
            "n_clusters": self.n_clusters,
            "degenerate": self.degenerate,
        }


@dataclass(frozen=True, slots=True)
class ReportableResult:
    """The primary Δ, released by a verdict that permitted it, with its reading attached.

    There is no constructor path to this object that skips the calibration gate: it is produced
    only by :meth:`CalibrationVerdict.release`.  ``mde`` has no default because design brief §9.5
    forbids a null without one.
    """

    outcome: Outcome
    delta: float
    ci95: tuple[float, float]
    p_value: float
    p_holm: float
    delta_min: float
    equivalence_bound: float
    mde: MinimumDetectableEffect
    attribution: Attribution
    status: AssayStatus
    sensitivity_floor: float | None
    caveats: tuple[str, ...]

    @property
    def significant(self) -> bool:
        return self.p_holm <= ALPHA

    @property
    def may_claim_structure(self) -> bool:
        """Design brief §9.4 as a boolean.  False whenever C1b fired or C2 did not."""

        return (
            self.significant
            and self.attribution.licenses_structure_claim
            and self.status.may_attribute_to_structure
        )

    @property
    def practically_significant(self) -> bool:
        return self.significant and abs(self.delta) >= self.delta_min

    def headline(self) -> str:
        """One line that cannot omit the MDE (§9.5) or the outcome id."""

        low, high = self.ci95
        return (
            f"{self.outcome.value}: Delta = {self.delta:+.4f} "
            f"(95% CI {low:+.4f} to {high:+.4f}, p_holm = {self.p_holm:.4f}); "
            f"MDE at n={self.mde.n_anchors} anchors / {self.mde.n_clusters} clusters, "
            f"k={self.mde.replicates.replicates} is {self.mde.points:.1f} points; "
            f"attribution = {self.attribution.value}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": str(self.outcome.value),
            "sentinel": self.outcome.sentinel,
            "delta": self.delta,
            "ci95": list(self.ci95),
            "p_value_uncorrected": self.p_value,
            "p_holm": self.p_holm,
            "significant": self.significant,
            "delta_min": self.delta_min,
            "practically_significant": self.practically_significant,
            "equivalence_bound": self.equivalence_bound,
            "mde": self.mde.to_dict(),
            "attribution": str(self.attribution.value),
            "may_claim_structure": self.may_claim_structure,
            "status": str(self.status.value),
            "sensitivity_floor": self.sensitivity_floor,
            "caveats": list(self.caveats),
            "headline": self.headline(),
        }


@dataclass(frozen=True, slots=True)
class CalibrationVerdict:
    """Whether HC-V0.6's assay is usable, decided by its three controls.

    The verdict is the **only** gateway to a reportable primary result: see :meth:`release`.
    """

    status: AssayStatus
    identity: ControlReading
    byte_null: ControlReading
    sensitivity: ControlReading
    alpha_identity: float
    alpha_byte_null: float
    alpha_sensitivity: float
    min_clusters: int
    reasons: tuple[str, ...]
    #: ``|Δ|`` that C2 demonstrably detected; ``None`` when C2 failed.
    sensitivity_floor: float | None
    #: False when C1 is degenerate: a zero C1 then shows determinism, not calibration.
    identity_informative: bool

    # -------------------------------------------------------------------- predicates

    @property
    def usable(self) -> bool:
        return self.status.may_report

    @property
    def broken(self) -> bool:
        return self.status is AssayStatus.BROKEN_IDENTITY_CONTROL

    @property
    def certified(self) -> bool:
        """Every required gate passed: the INTERSECTION the IUT argument is about.

        Deliberately stricter than :attr:`usable`, which permits a report with the structural
        claim withheld (``USABLE_ATTRIBUTION_BLOCKED``).  Certification is the full reading, and
        it is the event whose false-positive rate :func:`false_certification_bound` bounds.
        """

        return self.status is AssayStatus.USABLE

    @property
    def false_certification_bound(self) -> float:
        """``max_j alpha_j`` over the REJECT_TO_CERTIFY gates.  See the module docstring."""

        return false_certification_bound()

    def require_usable(self) -> None:
        """Raise :class:`AssayBroken` unless the controls permit reporting anything."""

        if not self.usable:
            raise AssayBroken(
                f"{self.status.value}: no comparison may be reported. " + "; ".join(self.reasons)
            )

    # -------------------------------------------------------------------- the gate

    def release(
        self,
        primary: PairedEffect,
        mde: MinimumDetectableEffect,
        *,
        delta_min: float,
        equivalence_bound: float,
        p_holm: float | None = None,
    ) -> ReportableResult:
        """Turn the primary effect into something reportable, or refuse.

        Refuses (raises :class:`AssayBroken`) when C1 fired, when missingness was arm-dependent, or
        when too few clusters contributed.  Otherwise classifies the result on the §8 outcome
        ladder and attaches the §9.4 attribution and the §9.5 MDE.
        """

        if primary.comparison is not Comparison.PRIMARY_RB_VS_RA:
            raise DesignViolation(
                f"release() takes the primary comparison, not {primary.comparison.value}"
            )
        if delta_min <= 0.0 or equivalence_bound <= 0.0:
            raise DesignViolation("delta_min and equivalence_bound must both be positive")
        self.require_usable()
        if primary.n_clusters < self.min_clusters:
            # The verdict checked the controls' cluster counts; the primary comparison can still
            # lose clusters of its own to missing cells, so it is checked here rather than assumed.
            raise AssayBroken(
                f"INSUFFICIENT_CLUSTERS: the primary comparison contributes "
                f"{primary.n_clusters} clusters (< {self.min_clusters}); outcome O6"
            )
        holm = primary.p_value if p_holm is None else float(p_holm)
        significant = holm <= ALPHA
        caveats: list[str] = list(self.reasons)
        if not self.identity_informative:
            caveats.append(
                "C1 is degenerate (Delta identically zero): it shows the Solver is deterministic, "
                "not that the pipeline is calibrated; the null control is carried by C1b alone"
            )
        attribution = self._attribution(significant)
        if attribution is Attribution.BYTE_PERTURBATION:
            caveats.append(
                "C1b is significant: the Solver responds to a whitespace-only perturbation, so "
                "R_B's effect cannot be attributed to its structure (design brief 9.4)"
            )
        outcome = self._outcome(primary, significant, delta_min, equivalence_bound)
        if outcome is Outcome.O3_INFORMATIVE_NULL:
            caveats.append(
                f"informative null is scoped to |Delta| < {mde.points:.1f} points, the MDE of this "
                f"design; it licenses nothing about effects below that"
            )
        if outcome is Outcome.O2_NULL_WITHOUT_SENSITIVITY:
            caveats.append(
                "C2 did not establish sensitivity, so this null is uninformative rather than "
                "evidence of no effect (design brief 4)"
            )
        return ReportableResult(
            outcome=outcome,
            delta=primary.delta,
            ci95=primary.delta_ci95,
            p_value=primary.p_value,
            p_holm=holm,
            delta_min=delta_min,
            equivalence_bound=equivalence_bound,
            mde=mde,
            attribution=attribution,
            status=self.status,
            sensitivity_floor=self.sensitivity_floor,
            caveats=tuple(caveats),
        )

    # -------------------------------------------------------------------- internals

    def _attribution(self, significant: bool) -> Attribution:
        if not self.status.sensitivity_established:
            return Attribution.UNDETERMINED
        if not significant:
            return Attribution.NO_EFFECT_TO_ATTRIBUTE
        if self.byte_null.significant(self.alpha_byte_null):
            return Attribution.BYTE_PERTURBATION
        return Attribution.STRUCTURE

    def _outcome(
        self,
        primary: PairedEffect,
        significant: bool,
        delta_min: float,
        equivalence_bound: float,
    ) -> Outcome:
        if significant:
            return Outcome.O4_FAVOURS_R_B if primary.delta > 0.0 else Outcome.O5_FAVOURS_R_A
        if self.status is AssayStatus.INSENSITIVE:
            return Outcome.O2_NULL_WITHOUT_SENSITIVITY
        if primary.equivalent_within(equivalence_bound):
            return Outcome.O3_INFORMATIVE_NULL
        return Outcome.O2_NULL_WITHOUT_SENSITIVITY

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": str(self.status.value),
            "usable": self.usable,
            "broken": self.broken,
            "identity_informative": self.identity_informative,
            "sensitivity_floor": self.sensitivity_floor,
            "alpha_identity": self.alpha_identity,
            "alpha_byte_null": self.alpha_byte_null,
            "alpha_sensitivity": self.alpha_sensitivity,
            "certified": self.certified,
            "false_certification_bound": self.false_certification_bound,
            "multiplicity": (
                "certification gates are an intersection-union test: separate uncorrected "
                "level-alpha component tests, no Holm. Holm applies only to the four-member "
                "effect-claim family in estimators.PREREGISTERED_FAMILY"
            ),
            "min_clusters": self.min_clusters,
            "reasons": list(self.reasons),
            "controls": {
                "C1": self.identity.to_dict(),
                "C1b": self.byte_null.to_dict(),
                "C2": self.sensitivity.to_dict(),
            },
        }


def _missingness_reason(missingness: Mapping[Arm, int] | None) -> str | None:
    """Outcome O7: cells lost to the harness at different rates in different arms."""

    if not missingness:
        return None
    counts = {arm: int(value) for arm, value in missingness.items()}
    if len(set(counts.values())) <= 1:
        return None
    listed = ", ".join(f"{arm.value}={count}" for arm, count in sorted(counts.items()))
    return f"arm-dependent missingness: unanalysable cells differ by arm ({listed})"


def calibrate(
    identity: PairedEffect,
    byte_null: PairedEffect,
    sensitivity: PairedEffect,
    *,
    alpha_identity: float = ALPHA_IDENTITY,
    alpha_byte_null: float = ALPHA_BYTE_NULL,
    alpha_sensitivity: float = ALPHA_SENSITIVITY,
    min_clusters: int = MIN_CLUSTERS,
    missingness: Mapping[Arm, int] | None = None,
) -> CalibrationVerdict:
    """Read the three controls and decide whether the assay may be reported.

    The order is the §8 ladder's order and it is not negotiable: C1 first, because C1 forecloses
    everything; then the structural preconditions (missingness, clusters); then C2, which decides
    whether a null can mean anything; then C1b, which decides what a non-null may be attributed to.
    """

    _require(identity, Comparison.C1_IDENTITY)
    _require(byte_null, Comparison.C1B_WHITESPACE)
    _require(sensitivity, Comparison.C2_ABLATION)
    c1 = ControlReading.from_effect(identity)
    c1b = ControlReading.from_effect(byte_null)
    c2 = ControlReading.from_effect(sensitivity)
    reasons: list[str] = []

    def decide(status: AssayStatus, floor: float | None = None) -> CalibrationVerdict:
        return CalibrationVerdict(
            status=status,
            identity=c1,
            byte_null=c1b,
            sensitivity=c2,
            alpha_identity=alpha_identity,
            alpha_byte_null=alpha_byte_null,
            alpha_sensitivity=alpha_sensitivity,
            min_clusters=min_clusters,
            reasons=tuple(reasons),
            sensitivity_floor=floor,
            identity_informative=not c1.degenerate,
        )

    # 1. C1 forecloses everything (design brief §4).
    if c1.significant(alpha_identity):
        reasons.append(
            f"C1 identity control is significant (Delta={c1.delta:+.4f}, p={c1.p_value:.4f} "
            f"<= alpha_identity={alpha_identity}): the assay reports a difference where there is "
            "none, so no other comparison may be reported (design brief 4)"
        )
        return decide(AssayStatus.BROKEN_IDENTITY_CONTROL)

    # 2. Structural preconditions: the cells must have been lost evenly, and there must be
    #    enough clusters for cluster-robust inference to mean anything.
    missing = _missingness_reason(missingness)
    if missing is not None:
        reasons.append(missing)
        return decide(AssayStatus.ARM_DEPENDENT_MISSINGNESS)

    contributing = min(c1b.n_clusters, c2.n_clusters)
    if contributing < min_clusters:
        reasons.append(
            f"only {contributing} clusters contribute (< {min_clusters}): cluster-robust "
            "inference is not trustworthy at this width, so the run is underpowered (O6)"
        )
        return decide(AssayStatus.INSUFFICIENT_CLUSTERS)

    # 3. C2 decides whether a null can mean anything at all.
    if not (c2.significant(alpha_sensitivity) and c2.delta < 0.0):
        direction = "in the wrong direction" if c2.delta >= 0.0 else "not significant"
        reasons.append(
            f"C2 ablation control is {direction} (Delta={c2.delta:+.4f}, p={c2.p_value:.4f}): the "
            "assay has not been shown to detect the removal of the goal text, so a null primary "
            "Delta is uninformative rather than evidence of no effect (design brief 4)"
        )
        return decide(AssayStatus.INSENSITIVE)

    # 4. C1b decides what a non-null may be attributed to (design brief §9.4).
    floor = abs(c2.delta)
    if c1b.significant(alpha_byte_null):
        reasons.append(
            f"C1b byte-perturbation control is significant (Delta={c1b.delta:+.4f}, "
            f"p={c1b.p_value:.4f}): a whitespace-only change moves the outcome, so an effect "
            "cannot be attributed to structure (design brief 9.4)"
        )
        return decide(AssayStatus.USABLE_ATTRIBUTION_BLOCKED, floor)
    return decide(AssayStatus.USABLE, floor)


def _require(effect: PairedEffect, comparison: Comparison) -> None:
    if effect.comparison is not comparison:
        raise DesignViolation(
            f"expected {comparison.value} in this slot, got {effect.comparison.value}"
        )
