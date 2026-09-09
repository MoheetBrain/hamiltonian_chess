"""The HC-V0.6 representations, and the contract that makes ``R_ONLY`` checkable.

Four things are under test, in decreasing order of how much they matter:

1. **the bijection** — ``invert(R.render(s)) == R_A.render(s)``, byte-for-byte, for both
   ``R_ONLY`` variants (``R_B`` and ``R_A_PRIME``), over every real Lean tactic state this
   repository holds plus adversarial synthetic ones.  A bijection cannot add or remove
   information, which is what ``R_ONLY`` means;
2. **never mangle silently** — for *arbitrary* text, the renderer either round-trips or raises a
   named :class:`RefusalReason`.  There is no third outcome;
3. **parity, and the sensitivity of the parity check** — ``R_A``/``R_B`` and ``R_A``/``R_A_PRIME``
   pass ``R_ONLY`` parity with differing bytes, and ``R_ABLATED``/``R_A`` *fail* it.  A check that
   cannot fail proves nothing, so the negative control is as load-bearing as the positive result;
4. **declaration-derivation** — rendering is a pure function of the declaration, structurally: a
   renderer that overrides ``render`` to peek at the envelope cannot be defined.

``R_A_PRIME`` carries one obligation the others do not: it must be a *null*.  Changing bytes is
not enough — it must change **only** whitespace, so that ``Δ(R_A,R_A′)`` isolates the byte-level
component of ``Δ(R_A,R_B)`` (design brief §9.4).  ``test_r_a_prime_changes_whitespace_and_nothing
_else`` is what makes that a checked property rather than an intention.

None of this needs Lean.  The real states come from committed artefacts: the HC-V0.5 smoke run and
the 223-anchor HC-V0.6 bank.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from arena.evolution.record import (
    GENE_INTERVENTION_CLASS,
    InterventionClass,
    UnclassifiedGeneError,
    classify_intervention,
)
from arena.trajectory.arena_v0 import BackendNativeRenderer
from arena.trajectory.representation import (
    ARMS,
    BASELINE_RENDERER_ID,
    BIJECTIVE_ARM_IDS,
    GOAL_MARKER,
    GOAL_VISIBILITY_GENE,
    NULL_PERTURBATION_ARM_IDS,
    PERTURBATION_ID,
    RENDERED_STATE_FIELD,
    REPRESENTATION_ARM_IDS,
    WITHHELD_MARKER,
    BaselineNative,
    BijectiveRenderer,
    DeclarationDerivedRenderer,
    EnumeratedWorkspaceRenderer,
    GoalWithheldRenderer,
    MalformedLayoutError,
    RefusalReason,
    UnrenderableStateError,
    WhitespacePerturbedNative,
    bijection_report,
    check_bijection,
    derive_arm_intervention_class,
    derive_intervention_class,
    is_renderable,
    layout,
    parse_tactic_state,
    perturb_whitespace,
    project_arm,
    refusal_reason,
    unlayout,
    unperturb_whitespace,
)
from arena.trajectory.schema import BackendStateEnvelope, PPScope
from arena.trajectory.state_identity import (
    InformationSlot,
    WorkspaceProjectionIdentity,
    check_projection_parity,
    normalize_goal_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_ARTEFACT = REPO_ROOT / "artifacts" / "trajectory" / "hc_v0_5_smoke.json"
ANCHOR_BANK = REPO_ROOT / "artifacts" / "trajectory" / "hc_v0_6_anchor_bank.json"

SCOPE = PPScope(
    current_namespace="LinearMap",
    open_declarations=("Finset", "Nat"),
    options=(("pp.unicode.fun", "true"),),
)

R_A = ARMS["R_A"]
R_A_PRIME = ARMS["R_A_PRIME"]
R_B = ARMS["R_B"]
R_ABLATED = ARMS["R_ABLATED"]

#: The arms that claim ``R_ONLY``, so that every bijection and parity assertion below runs over
#: both of them rather than over ``R_B`` alone.
R_ONLY_VARIANTS = [R_A_PRIME, R_B]


# ---------------------------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------------------------


#: The two key names the repository's committed artefacts use for a pretty-printed tactic state.
#: ``hc_v0_5_smoke.json`` stores a raw ``BackendStateEnvelope`` (``pp``); the anchored bank stores
#: the Solver-visible rendered payload (``goals_pp``).  Reading only the first spelling is exactly
#: how 223 real anchors would sit in the repository untested while every assertion below passed.
STATE_TEXT_KEYS = ("pp", "goals_pp")


def _iter_pretty_prints(payload: Any) -> list[tuple[str, int]]:
    """Every ``(pretty-print, n_goals)`` pair anywhere in a committed artefact.

    Structure-agnostic on purpose — it looks for the pair, not for a path — because the two
    artefacts nest it differently and a third will nest it differently again.
    """

    found: list[tuple[str, int]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key in STATE_TEXT_KEYS:
                text = node.get(key)
                if isinstance(text, str) and isinstance(node.get("n_goals"), int):
                    found.append((text, int(node["n_goals"])))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


def _states_in(path: Path) -> list[tuple[str, int]]:
    """Deduplicated real Lean tactic states from one committed artefact."""

    if not path.exists():
        return []
    return sorted(set(_iter_pretty_prints(json.loads(path.read_text(encoding="utf-8")))))


def _real_states() -> list[tuple[str, int]]:
    """Deduplicated real Lean tactic states from every committed artefact that has any."""

    pairs: set[tuple[str, int]] = set()
    for path in (SMOKE_ARTEFACT, ANCHOR_BANK):
        pairs.update(_states_in(path))
    return sorted(pairs)


def _envelope(pp: str, n_goals: int = 1, *, state_id: str = "0") -> BackendStateEnvelope:
    return BackendStateEnvelope(
        index=0,
        state_id=state_id,
        pp=pp,
        n_goals=n_goals,
        pp_scope=SCOPE,
        session_id="sess-1",
        problem_id="Mathlib/Test.lean::theorem",
    )


ANCHOR_BANK_STATES = _states_in(ANCHOR_BANK)
REAL_STATES = _real_states()
REAL_ENVELOPES = [
    _envelope(pp, n_goals, state_id=str(index)) for index, (pp, n_goals) in enumerate(REAL_STATES)
]
RENDERABLE_REAL_ENVELOPES = [env for env in REAL_ENVELOPES if is_renderable(env)]


def test_the_real_corpus_is_actually_present() -> None:
    """Guard the guard: an empty corpus would make every round-trip test vacuously pass."""

    assert SMOKE_ARTEFACT.exists(), f"missing committed real states at {SMOKE_ARTEFACT}"
    assert len(REAL_STATES) >= 30, f"only {len(REAL_STATES)} real states found"
    assert len(RENDERABLE_REAL_ENVELOPES) >= 30
    # The anchored bank is the corpus the experiment will actually be run on.  Asserting it
    # separately is the difference between "the round-trip tests passed" and "the round-trip
    # tests passed on the states the assay will use": the bank spells the key `goals_pp`, and a
    # walker that only looked for `pp` would have left every one of these untested.
    assert ANCHOR_BANK.exists(), f"missing the anchored bank at {ANCHOR_BANK}"
    assert len(ANCHOR_BANK_STATES) >= 200, f"only {len(ANCHOR_BANK_STATES)} anchored states found"
    assert set(ANCHOR_BANK_STATES) <= set(REAL_STATES)
    assert any("⊢" in pp and "\n" in pp for pp, _ in REAL_STATES)
    # The multi-goal and line-wrapped shapes are the ones a naive parser gets wrong.
    assert any(n > 1 for _, n in REAL_STATES), "no multi-goal real state in the corpus"
    assert any(any(line[:1] == " " for line in pp.split("\n")) for pp, _ in REAL_STATES), (
        "no line-wrapped real state in the corpus"
    )


# ---------------------------------------------------------------------------------------------
# 1. The bijection, on real states
# ---------------------------------------------------------------------------------------------


def test_r_a_is_byte_identical_to_the_shipped_backend_native_renderer() -> None:
    """``R_A`` *is* ``BackendNativeRenderer``, so HC-V0.5's numbers stay comparable."""

    native = BackendNativeRenderer()
    assert R_A.renderer_id == native.renderer_id == BASELINE_RENDERER_ID
    for envelope in REAL_ENVELOPES:
        assert dict(R_A.render(envelope)) == dict(native.render(envelope))


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
@pytest.mark.parametrize(
    "envelope", RENDERABLE_REAL_ENVELOPES, ids=lambda env: f"state-{env.state_id}"
)
def test_every_r_only_arm_round_trips_every_renderable_real_state(
    arm: DeclarationDerivedRenderer, envelope: BackendStateEnvelope
) -> None:
    check = check_bijection(arm, envelope)
    assert check.holds, check.detail
    assert dict(arm.invert(arm.render(envelope))) == dict(R_A.render(envelope))  # type: ignore[attr-defined]


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_bijection_report_over_the_whole_real_bank(arm: DeclarationDerivedRenderer) -> None:
    """The measured round-trip rate, with refusals separated from failures."""

    report = bijection_report(arm, REAL_ENVELOPES)
    assert report.failures == ()
    assert report.holds_everywhere
    assert report.n_states == len(REAL_ENVELOPES)
    assert report.n_holds == report.n_checked
    # Every refusal is a degenerate, non-anchor state: no open goal to render.
    assert set(report.refusal_counts) <= {
        RefusalReason.EMPTY_PP.value,
        RefusalReason.NO_GOAL_MARKER.value,
    }
    for check in report.refusals:
        assert check.refused is not None


def test_r_a_prime_never_refuses_a_state_at_all() -> None:
    """The null arm is total; only the re-layout can refuse.

    This is the asymmetry that decides the usable bank: ``R_A_PRIME`` is defined wherever ``R_A``
    is, so the states the four-arm assay can play are exactly the states ``R_B`` accepts.
    """

    report = bijection_report(R_A_PRIME, REAL_ENVELOPES)
    assert report.refusals == ()
    assert report.n_checked == report.n_states == len(REAL_ENVELOPES)
    assert report.n_holds == report.n_states
    # ... including every state R_B refuses.
    refused = [env for env in REAL_ENVELOPES if not is_renderable(env)]
    for envelope in refused:
        assert check_bijection(R_A_PRIME, envelope).holds
    for pp, n_goals, _ in REFUSED:
        assert check_bijection(R_A_PRIME, _envelope(pp, n_goals)).holds


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_every_r_only_arm_actually_changes_the_bytes_the_solver_sees(
    arm: DeclarationDerivedRenderer,
) -> None:
    """``bytes_differ`` must not be satisfiable by the renderer id alone."""

    for envelope in RENDERABLE_REAL_ENVELOPES:
        assert (
            arm.render(envelope)[RENDERED_STATE_FIELD] != R_A.render(envelope)[RENDERED_STATE_FIELD]
        )


def test_r_a_prime_changes_whitespace_and_nothing_else() -> None:
    """The null must be *null*: strip the whitespace convention and the states are identical.

    Checked against a comparison this module does not control — ``normalize_goal_text``, the
    arena's own presentational normalisation — plus a whitespace-free character census, so the
    claim does not rest on inverting the perturbation with the perturbation's own inverse.
    """

    for envelope in RENDERABLE_REAL_ENVELOPES:
        perturbed = str(R_A_PRIME.render(envelope)[RENDERED_STATE_FIELD])
        baseline = str(R_A.render(envelope)[RENDERED_STATE_FIELD])
        assert perturbed != baseline
        assert "".join(perturbed.split()) == "".join(baseline.split())
        assert perturbed.count("\n") == baseline.count("\n")
        # The trailing half of the convention is absorbed by the arena's own normalisation; the
        # interior half is not, and is deliberately not, so a trimming layer cannot silently
        # collapse this arm into the byte-identical control C1.
        assert normalize_goal_text(perturbed) != normalize_goal_text(baseline)
        assert normalize_goal_text(perturbed).replace(f"{GOAL_MARKER}  ", f"{GOAL_MARKER} ") == (
            normalize_goal_text(baseline)
        )


def test_r_a_prime_moves_nothing_structural() -> None:
    """Line count, line order and per-line content (modulo whitespace) are all preserved."""

    for envelope in RENDERABLE_REAL_ENVELOPES:
        perturbed = str(R_A_PRIME.render(envelope)[RENDERED_STATE_FIELD]).split("\n")
        baseline = str(R_A.render(envelope)[RENDERED_STATE_FIELD]).split("\n")
        assert len(perturbed) == len(baseline)
        for after, before in zip(perturbed, baseline, strict=True):
            assert "".join(after.split()) == "".join(before.split())


def test_r_b_carries_no_hidden_copy_of_the_baseline_bytes() -> None:
    """The inverse must re-derive the state, not replay a stashed copy of it.

    Asserted for ``R_B`` only, and the asymmetry is honest rather than an oversight: ``R_A_PRIME``
    is *deliberately* a near-copy of the baseline text, so a substring test would be meaningless
    for it.  What must hold for both is that no digest of the baseline is carried, which is
    checked separately below.
    """

    for envelope in RENDERABLE_REAL_ENVELOPES:
        rendered = R_B.render(envelope)
        assert envelope.pp not in json.dumps(dict(rendered), ensure_ascii=False)
        assert envelope.pp_sha256 not in json.dumps(dict(rendered), ensure_ascii=False)


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_no_r_only_arm_carries_the_baseline_digest(arm: DeclarationDerivedRenderer) -> None:
    """A stashed baseline digest would let ``invert`` cheat.  Every digest is of what is shown."""

    for envelope in RENDERABLE_REAL_ENVELOPES:
        rendered = dict(arm.render(envelope))
        assert envelope.pp_sha256 not in json.dumps(rendered, ensure_ascii=False)
        assert envelope.pp_sha256 != rendered.get("pp_sha256")


# ---------------------------------------------------------------------------------------------
# 2. Adversarial shapes: fix them or refuse them, never mangle them
# ---------------------------------------------------------------------------------------------

TWO_GOALS = (
    "case left\np q : Prop\nhp : p\n⊢ p\n\ncase right\np q : Prop\nhp : p\n⊢ q",
    2,
)
NO_HYPOTHESES = ("⊢ True", 1)
CASE_ONLY = ("case h\n⊢ True", 1)
TURNSTILE_INSIDE_A_HYPOTHESIS = ("h : Judgement ⊢ Γ\nk : α → ⊢\n⊢ h = k", 1)
UNICODE_HEAVY = ("𝔽 : Type u_1\nι✝ : ⨆ i, ↑(f i)\nx✝¹ : α ≃ₗ[ℝ] β\n⊢ ∑ i ∈ s, ‖x‖₊ ≤ ⨅ j, ⋯", 1)
VERY_LONG_LINE = ("h : " + "Foo " * 4000 + "Bar\n⊢ " + "Baz " * 4000 + "Qux", 1)
TRAILING_WHITESPACE = ("a : Nat   \nb : Nat\t\n⊢ a = b  ", 1)
WRAPPED_HYPOTHESIS = ("h :\n    a very long type that\n      wrapped twice\nk : Nat\n⊢ h = h", 1)
WRAPPED_TARGET = ("a : Nat\n⊢ f a =\n    g a +\n        h a", 1)
LOOKS_LIKE_THE_LAYOUT = ("[TARGET] : Nat\n(1) x : Nat\n[HYPOTHESES 9] : Nat\n⊢ True", 1)
CASE_KEYWORD_AS_HYPOTHESIS = ("case : Nat\nx : Nat\n⊢ True", 1)
TAB_INDENTED_CONTINUATION = ("h :\n\tNat\n⊢ h = h", 1)

ROUND_TRIPPABLE: tuple[tuple[str, int], ...] = (
    TWO_GOALS,
    NO_HYPOTHESES,
    CASE_ONLY,
    TURNSTILE_INSIDE_A_HYPOTHESIS,
    UNICODE_HEAVY,
    VERY_LONG_LINE,
    TRAILING_WHITESPACE,
    WRAPPED_HYPOTHESIS,
    WRAPPED_TARGET,
    LOOKS_LIKE_THE_LAYOUT,
    CASE_KEYWORD_AS_HYPOTHESIS,
    TAB_INDENTED_CONTINUATION,
    ("a b : Nat\n⊢ a + b = b + a", 1),
    ("⊢", 1),
    ("x : α\n⊢ \n    indented target continuation", 1),
)


@pytest.mark.adversarial
@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
@pytest.mark.parametrize("pp,n_goals", ROUND_TRIPPABLE, ids=lambda value: str(value)[:40])
def test_adversarial_states_that_must_round_trip(
    pp: str, n_goals: int, arm: DeclarationDerivedRenderer
) -> None:
    envelope = _envelope(pp, n_goals)
    assert refusal_reason(envelope) is None
    recovered = dict(arm.invert(arm.render(envelope)))  # type: ignore[attr-defined]
    assert recovered == dict(R_A.render(envelope))
    assert recovered["goals_pp"] == pp


REFUSED: tuple[tuple[str, int, RefusalReason], ...] = (
    ("", 0, RefusalReason.EMPTY_PP),
    ("no goals", 0, RefusalReason.NO_GOAL_MARKER),
    ("a : Nat\nb : Nat", 1, RefusalReason.NO_GOAL_MARKER),
    # CRLF: with two goals the blank-line split no longer separates them, so one block carries
    # two turnstiles.  Refused rather than silently treated as a single goal.
    ("h : p\r\n⊢ p\r\n\r\nh : q\r\n⊢ q", 2, RefusalReason.MULTIPLE_GOAL_MARKERS_IN_BLOCK),
    ("h : p\n⊢ p\n⊢ q", 1, RefusalReason.MULTIPLE_GOAL_MARKERS_IN_BLOCK),
    # A trailing newline puts an empty line inside the last block, so hypothesis grouping would
    # be a guess.
    ("a : Nat\n⊢ True\n", 1, RefusalReason.EMPTY_LINE_IN_GOAL_BLOCK),
    ("a : Nat\n\n\n⊢ True", 1, RefusalReason.EMPTY_LINE_IN_GOAL_BLOCK),
    ("    indented : Nat\n⊢ True", 1, RefusalReason.ORPHAN_CONTINUATION_LINE),
    ("a : Nat\n⊢ True", 2, RefusalReason.GOAL_COUNT_MISMATCH),
    ("h : p\n⊢ p\n\nh : q\n⊢ q", 1, RefusalReason.GOAL_COUNT_MISMATCH),
)


@pytest.mark.adversarial
@pytest.mark.parametrize("pp,n_goals,reason", REFUSED, ids=lambda value: str(value)[:40])
def test_adversarial_states_that_must_be_refused(
    pp: str, n_goals: int, reason: RefusalReason
) -> None:
    envelope = _envelope(pp, n_goals)
    assert refusal_reason(envelope) is reason
    assert not is_renderable(envelope)
    with pytest.raises(UnrenderableStateError) as caught:
        R_B.render(envelope)
    assert caught.value.reason is reason
    # A refusal is a refusal in the report too, never a silent pass and never a failure.
    check = check_bijection(R_B, envelope)
    assert not check.checked
    assert check.refused is reason


@pytest.mark.adversarial
@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_crlf_single_goal_round_trips_because_the_carriage_returns_are_preserved(
    arm: DeclarationDerivedRenderer,
) -> None:
    """The one CRLF shape that is unambiguous.  Bytes, including ``\\r``, come back exactly."""

    pp = "a : Nat\r\nb : Nat\r\n⊢ a = b"
    envelope = _envelope(pp, 1)
    assert arm.invert(arm.render(envelope))["goals_pp"] == pp  # type: ignore[attr-defined]


@pytest.mark.adversarial
def test_r_a_renders_everything_including_states_r_b_refuses() -> None:
    """Only the re-layout can refuse.  ``R_A`` and ``R_A_PRIME`` are total, so refusals are
    ``R_B``'s alone and the usable bank is exactly ``R_B``'s."""

    for pp, n_goals, _ in REFUSED:
        envelope = _envelope(pp, n_goals)
        assert R_A.render(envelope)["goals_pp"] == pp
        assert unperturb_whitespace(str(R_A_PRIME.render(envelope)["goals_pp"])) == pp


# ---------------------------------------------------------------------------------------------
# Property tests: the never-mangle invariant
# ---------------------------------------------------------------------------------------------

_IDENT = st.text(
    alphabet=st.sampled_from(list("abcxyzΓΔαβγ✝¹²ₗ_'0123456789")), min_size=1, max_size=6
)
_TYPE_TEXT = st.text(
    alphabet=st.sampled_from(list("abcNat →∀∃⊢λ()[]{}:=,. ✝⋯≃ₗℝ𝔽∑⨆")), min_size=0, max_size=40
)


@st.composite
def _hypothesis_entry(draw: st.DrawFn) -> list[str]:
    first = f"{draw(_IDENT)} : {draw(_TYPE_TEXT)}"
    assume(not first.startswith(("case ", " ", "\t")))
    continuations = draw(st.lists(_TYPE_TEXT, max_size=2))
    return [first] + [f"    {text}" for text in continuations]


@st.composite
def _goal_block(draw: st.DrawFn) -> str:
    lines: list[str] = []
    if draw(st.booleans()):
        lines.append(f"case {draw(_IDENT)}")
    for entry in draw(st.lists(_hypothesis_entry(), max_size=4)):
        lines.extend(entry)
    lines.append(f"⊢ {draw(_TYPE_TEXT)}")
    lines.extend(f"    {text}" for text in draw(st.lists(_TYPE_TEXT, max_size=2)))
    return "\n".join(lines)


@st.composite
def _tactic_state(draw: st.DrawFn) -> tuple[str, int]:
    blocks = draw(st.lists(_goal_block(), min_size=1, max_size=3))
    return "\n\n".join(blocks), len(blocks)


@pytest.mark.adversarial
@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
@settings(max_examples=400, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(_tactic_state())
def test_property_well_shaped_states_always_round_trip(
    arm: DeclarationDerivedRenderer, state: tuple[str, int]
) -> None:
    pp, n_goals = state
    envelope = _envelope(pp, n_goals)
    try:
        rendered = arm.render(envelope)
    except UnrenderableStateError as error:  # pragma: no cover - documents a real refusal
        pytest.fail(f"well-shaped state refused as {error.reason.value}: {pp!r}")
    assert dict(arm.invert(rendered)) == dict(R_A.render(envelope))  # type: ignore[attr-defined]


_ARBITRARY = st.text(
    alphabet=st.sampled_from(list("ab ⊢\n\r\t:()[]0123✝→case ")), min_size=0, max_size=120
)


@pytest.mark.adversarial
@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
@settings(max_examples=600, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(_ARBITRARY)
def test_property_arbitrary_text_either_round_trips_or_is_refused(
    arm: DeclarationDerivedRenderer, pp: str
) -> None:
    """There is no third outcome.  A silent mangle is the failure this whole design exists to stop."""

    envelope = _envelope(pp, len(pp.split("\n\n")))
    try:
        rendered = arm.render(envelope)
    except UnrenderableStateError as error:
        assert isinstance(error.reason, RefusalReason)
        return
    recovered = dict(arm.invert(rendered))  # type: ignore[attr-defined]
    assert recovered == dict(R_A.render(envelope))
    assert recovered["goals_pp"] == pp


@pytest.mark.adversarial
@settings(max_examples=600, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(_ARBITRARY)
def test_property_the_whitespace_perturbation_is_a_total_bijection(pp: str) -> None:
    """``R_A_PRIME`` has no refusal branch at all, so the property is unconditional."""

    perturbed = perturb_whitespace(pp)
    assert unperturb_whitespace(perturbed) == pp
    assert "".join(perturbed.split()) == "".join(pp.split())


def test_unperturb_rejects_text_it_did_not_produce() -> None:
    for text in ("", "no trailing space", "a \nb", "⊢ x"):
        with pytest.raises(MalformedLayoutError):
            unperturb_whitespace(text)


@pytest.mark.adversarial
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(_ARBITRARY)
def test_property_the_parse_never_returns_a_lossy_decomposition(pp: str) -> None:
    try:
        parsed = parse_tactic_state(pp)
    except UnrenderableStateError:
        return
    assert parsed.unparse() == pp
    assert unlayout(layout(parsed)) == parsed


def test_unlayout_rejects_text_it_did_not_produce() -> None:
    for text in ("", "not a layout", "[GOAL 1 OF 1]\nnope", "[GOAL 2 OF 1]\n[HYPOTHESES 0]"):
        with pytest.raises(MalformedLayoutError):
            unlayout(text)


# ---------------------------------------------------------------------------------------------
# 3. Parity — and the negative control that proves the check can fail
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_r_only_parity_holds_against_the_baseline_at_every_real_state(
    arm: DeclarationDerivedRenderer,
) -> None:
    for envelope in RENDERABLE_REAL_ENVELOPES:
        left = project_arm(R_A, envelope).identity
        right = project_arm(arm, envelope).identity
        result = check_projection_parity(left, right, InterventionClass.R_ONLY)
        assert result.parity_required
        assert result.parity_holds, result.explanation
        assert result.bytes_differ
        assert result.admissible
        assert left.slots_were_declared and right.slots_were_declared
        assert left.differs_only_in_rendering(right)


def test_the_null_arm_and_the_variant_are_distinguishable_from_each_other() -> None:
    """``R_A_PRIME`` must not accidentally *be* ``R_B``: same declaration, different bytes.

    Without this the two ``R_ONLY`` arms could coincide and ``Δ(R_A,R_A′)`` would be the same
    measurement as ``Δ(R_A,R_B)`` rather than a control on it.
    """

    for envelope in RENDERABLE_REAL_ENVELOPES:
        null_text = R_A_PRIME.render(envelope)[RENDERED_STATE_FIELD]
        variant_text = R_B.render(envelope)[RENDERED_STATE_FIELD]
        assert null_text != variant_text
    identity_null = project_arm(R_A_PRIME, RENDERABLE_REAL_ENVELOPES[0]).identity
    identity_variant = project_arm(R_B, RENDERABLE_REAL_ENVELOPES[0]).identity
    assert identity_null.same_declared_information_as(identity_variant)
    assert identity_null.rendered_bytes_digest != identity_variant.rendered_bytes_digest


def test_negative_control_r_ablated_fails_r_only_parity() -> None:
    """The check can fail.  Without this the positive result above is worth nothing."""

    failures = 0
    for envelope in RENDERABLE_REAL_ENVELOPES:
        left = project_arm(R_A, envelope).identity
        right = project_arm(R_ABLATED, envelope).identity
        result = check_projection_parity(left, right, InterventionClass.R_ONLY)
        assert not result.parity_holds
        assert not result.admissible
        assert "GOAL_TEXT" in result.explanation
        failures += 1
    assert failures == len(RENDERABLE_REAL_ENVELOPES)


def test_the_ablation_is_reported_under_its_own_class_and_is_then_not_a_violation() -> None:
    """Under ``P_CHANGE`` the same difference is the intervention, not a fault (manual §26.3)."""

    envelope = _envelope(*TWO_GOALS)
    left = project_arm(R_A, envelope).identity
    right = project_arm(R_ABLATED, envelope).identity
    result = check_projection_parity(left, right, InterventionClass.P_CHANGE)
    assert not result.parity_required
    assert result.admissible
    assert not result.parity_holds


def test_identity_control_c1_r_a_against_itself_is_byte_identical() -> None:
    """Control ``C1``'s renderer side: the null arm differs in nothing at all."""

    envelope = _envelope(*TWO_GOALS)
    left = project_arm(R_A, envelope).identity
    right = project_arm(BaselineNative(), envelope).identity
    result = check_projection_parity(left, right, InterventionClass.R_ONLY)
    assert result.parity_holds
    assert not result.bytes_differ


# ---------------------------------------------------------------------------------------------
# The intervention class is derived, not written down
# ---------------------------------------------------------------------------------------------


def test_the_gene_table_cannot_express_a_visibility_change_today() -> None:
    """Precisely what is missing in ``arena/evolution/record.py``, asserted rather than claimed."""

    assert set(GENE_INTERVENTION_CLASS.values()) == {InterventionClass.R_ONLY}
    assert len(GENE_INTERVENTION_CLASS) == 14
    assert GOAL_VISIBILITY_GENE not in GENE_INTERVENTION_CLASS
    with pytest.raises(UnclassifiedGeneError):
        classify_intervention([GOAL_VISIBILITY_GENE])
    # And the fourteen that do exist would type the ablation as a representation change.
    assert classify_intervention(["serialization"]) is InterventionClass.R_ONLY


def test_r_ablated_is_classified_p_change_from_its_declaration_alone() -> None:
    derived = derive_arm_intervention_class(R_ABLATED, RENDERABLE_REAL_ENVELOPES)
    assert derived.intervention_class is InterventionClass.P_CHANGE
    assert derived.withheld_slots == (InformationSlot.GOAL_TEXT.value,)
    assert not derived.permits_representation_claim
    # Nothing anywhere labelled it: the arm carries no intervention_class attribute at all.
    assert not hasattr(R_ABLATED, "intervention_class")


@pytest.mark.parametrize("arm", R_ONLY_VARIANTS, ids=lambda arm: str(arm.arm_id))
def test_r_only_arms_are_classified_r_only_from_their_declaration_at_every_real_state(
    arm: DeclarationDerivedRenderer,
) -> None:
    derived = derive_arm_intervention_class(arm, RENDERABLE_REAL_ENVELOPES)
    assert derived.intervention_class is InterventionClass.R_ONLY
    assert derived.withheld_slots == () and derived.added_slots == ()
    assert derived.permits_representation_claim


def test_a_renderer_that_adds_a_slot_is_also_not_r_only() -> None:
    """Withholding is not the only way to break parity; adding is caught symmetrically."""

    class Chatty(DeclarationDerivedRenderer):
        arm_id = "R_CHATTY"
        renderer_id = "test-chatty"

        def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
            return {
                **dict(R_A.declare_information(envelope)),
                InformationSlot.LAST_DIAGNOSTIC: "a diagnostic R_A never showed",
            }

        def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
            return {"renderer_id": self.renderer_id, "goals_pp": "irrelevant"}

    derived = derive_arm_intervention_class(Chatty(), [_envelope(*TWO_GOALS)])
    assert derived.intervention_class is InterventionClass.P_CHANGE
    assert derived.added_slots == (InformationSlot.LAST_DIAGNOSTIC.value,)


def test_derivation_fails_closed_on_an_empty_bank() -> None:
    with pytest.raises(ValueError):
        derive_arm_intervention_class(R_B, [])


def test_derive_intervention_class_notices_a_changed_value_under_equal_slots() -> None:
    baseline = WorkspaceProjectionIdentity.from_information(
        {InformationSlot.GOAL_TEXT: "⊢ p"}, slots_were_declared=True
    )
    altered = WorkspaceProjectionIdentity.from_information(
        {InformationSlot.GOAL_TEXT: "⊢ q"}, slots_were_declared=True
    )
    derived = derive_intervention_class(baseline, altered)
    assert derived.intervention_class is InterventionClass.P_CHANGE
    assert derived.values_differ
    assert derived.withheld_slots == () and derived.added_slots == ()


def test_project_arm_stamps_the_derived_class_and_takes_no_class_argument() -> None:
    envelope = _envelope(*TWO_GOALS)
    for arm in (R_A, R_A_PRIME, R_B):
        identity = project_arm(arm, envelope).identity
        assert identity.intervention_class == InterventionClass.R_ONLY.value
    ablated = project_arm(R_ABLATED, envelope).identity
    assert ablated.intervention_class == InterventionClass.P_CHANGE.value


# ---------------------------------------------------------------------------------------------
# 4. Declaration-derivation, structurally
# ---------------------------------------------------------------------------------------------


def test_a_renderer_that_overrides_render_cannot_be_defined() -> None:
    """The peek is impossible, not merely discouraged."""

    with pytest.raises(TypeError, match="overrides render"):

        class Peeker(DeclarationDerivedRenderer):
            arm_id = "R_PEEK"
            renderer_id = "test-peeker"

            def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
                return {InformationSlot.GOAL_COUNT: envelope.n_goals}

            def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
                return {}

            def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
                return {"renderer_id": "test-peeker", "goals_pp": envelope.pp}


def test_equal_declarations_render_equally_across_different_envelopes() -> None:
    """Two envelopes that differ only outside the declaration must render identically."""

    left = BackendStateEnvelope(
        index=0, state_id="9", pp=TWO_GOALS[0], n_goals=2, pp_scope=SCOPE, session_id="A"
    )
    right = BackendStateEnvelope(
        index=41, state_id="9", pp=TWO_GOALS[0], n_goals=2, pp_scope=SCOPE, session_id="B"
    )
    for arm in ARMS.values():
        assert dict(arm.declare_information(left)) == dict(arm.declare_information(right))
        assert dict(arm.render(left)) == dict(arm.render(right))


def test_present_cannot_mutate_the_declaration_it_was_handed() -> None:
    class Mutator(DeclarationDerivedRenderer):
        arm_id = "R_MUT"
        renderer_id = "test-mutator"

        def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
            return {InformationSlot.GOAL_COUNT: envelope.n_goals}

        def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
            information["injected"] = "x"  # type: ignore[index]
            return {}

    with pytest.raises(TypeError):
        Mutator().render(_envelope(*NO_HYPOTHESES))


def test_every_arm_declares_and_is_seen_to_declare() -> None:
    envelope = _envelope(*TWO_GOALS)
    for arm in ARMS.values():
        projection = project_arm(arm, envelope)
        assert projection.identity.slots_were_declared
        assert projection.identity.renderer_id == arm.renderer_id
        assert RENDERED_STATE_FIELD in projection.rendered


def test_only_the_bijective_arms_implement_the_bijection_protocol() -> None:
    assert BIJECTIVE_ARM_IDS == ("R_A", "R_A_PRIME", "R_B")
    for arm_id in BIJECTIVE_ARM_IDS:
        assert isinstance(ARMS[arm_id], BijectiveRenderer)
    assert set(ARMS) - set(BIJECTIVE_ARM_IDS) == {"R_ABLATED"}
    assert not isinstance(R_ABLATED, BijectiveRenderer)
    # And the checker refuses to bless a non-bijective arm rather than skipping it.
    check = check_bijection(R_ABLATED, _envelope(*TWO_GOALS))
    assert not check.holds
    assert "invert" in check.detail


# ---------------------------------------------------------------------------------------------
# The ablation shows what it says it shows
# ---------------------------------------------------------------------------------------------


def test_r_ablated_withholds_the_goal_text_and_keeps_the_count() -> None:
    envelope = _envelope(*TWO_GOALS)
    rendered = R_ABLATED.render(envelope)
    text = str(rendered[RENDERED_STATE_FIELD])
    assert WITHHELD_MARKER in text
    assert "GOALS REMAINING 2" in text
    assert rendered["n_goals"] == 2
    assert rendered["backend_kind"] == envelope.backend_kind
    assert rendered["state_id"] == envelope.state_id
    for fragment in ("case left", "hp : p", "⊢ p", "⊢ q"):
        assert fragment not in text
    assert envelope.pp not in json.dumps(dict(rendered), ensure_ascii=False)


def test_the_registry_names_exactly_the_four_arms_of_the_brief() -> None:
    assert set(ARMS) == {"R_A", "R_A_PRIME", "R_B", "R_ABLATED"}
    assert REPRESENTATION_ARM_IDS == ("R_A", "R_B")
    assert NULL_PERTURBATION_ARM_IDS == ("R_A", "R_A_PRIME")
    assert isinstance(ARMS["R_A"], BaselineNative)
    assert isinstance(ARMS["R_A_PRIME"], WhitespacePerturbedNative)
    assert isinstance(ARMS["R_B"], EnumeratedWorkspaceRenderer)
    assert isinstance(ARMS["R_ABLATED"], GoalWithheldRenderer)
    assert {arm.arm_id for arm in ARMS.values()} == set(ARMS)
    assert len({arm.renderer_id for arm in ARMS.values()}) == 4
    # R_A_PRIME is a *distinct renderer*, not a second draw through R_A.  The distinction matters
    # because `arena/experiments/hc_v0_6/schema.py` currently uses the same name for the latter.
    assert ARMS["R_A_PRIME"].renderer_id != ARMS["R_A"].renderer_id
    assert PERTURBATION_ID in str(ARMS["R_A_PRIME"].render(_envelope(*TWO_GOALS)).values())
    with pytest.raises(TypeError):
        ARMS["R_A"] = ARMS["R_B"]  # type: ignore[index]
