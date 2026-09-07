"""Item G: the canonical seam, and what it actually costs.

Nothing here modifies the substrate.  Every claim about the frozen verifier is made by
running it.
"""

from __future__ import annotations

import pytest

from arena.canonical.schema import (
    SCHEMA_VERSION,
    Binding,
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    EvidenceNode,
    MathObject,
)
from arena.canonical.schema import Obligation as CanonicalObligation
from arena.languages._wire import state_to_payload
from arena.languages.registry import SEED_LANGUAGES
from arena.verifier.native import NativeVerifier
from releases.TRAINING_LANGUAGE_V0 import (
    CanonicalMappingError,
    CompatibilityProfile,
    LossKind,
    LossPolicy,
    State,
    from_canonical,
    parse_state,
    render_state,
    to_canonical,
)
from releases.TRAINING_LANGUAGE_V0.canonical_adapter import ABSENT_GOAL_OP

from .conftest import build_minimal_state, build_rich_state, build_single_goal_state

STATES = (build_rich_state(), build_minimal_state(), build_single_goal_state())


@pytest.mark.parametrize("state", STATES, ids=lambda item: item.state_id)
def test_the_emitted_canonical_state_passes_the_strict_wire_validator(state: State) -> None:
    payload = state_to_payload(to_canonical(state).canonical)
    assert payload["schema_version"] == SCHEMA_VERSION


@pytest.mark.parametrize("state", STATES, ids=lambda item: item.state_id)
def test_round_trip_through_the_canonical_substrate_is_exact(state: State) -> None:
    mapping = to_canonical(state)
    assert from_canonical(mapping.canonical).state == state


@pytest.mark.parametrize("language", SEED_LANGUAGES, ids=lambda item: item.candidate_id)
def test_every_seed_surface_round_trips_the_adapted_state(language: object) -> None:
    canonical = to_canonical(build_rich_state()).canonical
    text = language.render(canonical)  # type: ignore[attr-defined]
    assert language.parse(text) == canonical  # type: ignore[attr-defined]


def test_the_loss_report_records_carrying_rather_than_hiding_it() -> None:
    losses = to_canonical(build_rich_state()).losses
    assert losses.is_lossless
    assert not losses.is_native
    carried = set(losses.features(LossKind.CARRIED))
    assert {
        "multi_goal",
        "obligation_scope",
        "let_values",
        "metavariable_substitution",
        "scope_forest",
        "binder_kind",
        "claim_identity",
    } <= carried
    assert losses.features(LossKind.ENCODED) == ("structured_types",)
    assert losses.to_dict()["is_lossless"] is True


def test_native_only_refuses_rather_than_pretending() -> None:
    with pytest.raises(CanonicalMappingError, match="cannot be expressed"):
        to_canonical(build_rich_state(), policy=LossPolicy.NATIVE_ONLY)


def test_drop_policy_reports_every_casualty() -> None:
    mapping = to_canonical(build_rich_state(), policy=LossPolicy.DROP)
    assert not mapping.losses.is_lossless
    assert "multi_goal" in mapping.losses.features(LossKind.DROPPED)
    state_to_payload(mapping.canonical)
    assert not any(key.startswith("tl0.") for key, _ in mapping.canonical.goal.attributes)


def test_a_zero_goal_state_records_the_synthesised_goal() -> None:
    state = build_minimal_state()
    mapping = to_canonical(state)
    assert mapping.canonical.goal.op == ABSENT_GOAL_OP
    assert "goal" in mapping.losses.features(LossKind.SYNTHESIZED)
    assert from_canonical(mapping.canonical).state == state


def test_obligation_scope_survives_as_an_expression_attribute() -> None:
    canonical = to_canonical(build_rich_state()).canonical
    attributes = dict(canonical.obligations[0].proposition.attributes)
    assert attributes["tl0.scope_id"] == "s2"


def test_the_frozen_verifier_accepts_the_compatible_profile() -> None:
    canonical = to_canonical(build_rich_state()).canonical
    result = NativeVerifier().verify_state(canonical)
    assert result.accepted, sorted({issue.code for issue in result.issues})


def test_the_honest_profile_trips_exactly_the_known_frozen_verifier_rules() -> None:
    canonical = to_canonical(build_rich_state(), profile=CompatibilityProfile.HONEST).canonical
    result = NativeVerifier().verify_state(canonical)
    assert not result.accepted
    assert sorted({issue.code for issue in result.issues}) == [
        "UNBOUND_VARIABLE",
        "UNKNOWN_ACTION_TARGET",
        "UNKNOWN_SCOPE",
    ]


def _foreign_state() -> CanonicalState:
    """A canonical state TL0 did not produce, built directly against the frozen schema."""

    return CanonicalState(
        state_id="foreign:1",
        objects=(
            MathObject(
                "m", "Matrix", CanonicalExpression("lit", value=2, sort="Nat"), (2, "n"), "kg"
            ),
        ),
        bindings=(Binding("b1", "x", "Nat", "ctx", "forall"),),
        assumptions=(CanonicalExpression("gt", sort="Prop"),),
        established_facts=(CanonicalExpression("eq", sort="Prop"),),
        propositions=(),
        goal=CanonicalExpression("even", sort="Prop"),
        obligations=(CanonicalObligation("ob", CanonicalExpression("pos", sort="Prop")),),
        evidence_dependencies=(EvidenceNode("ev", "OPEN", (), "lean", None),),
        local_scope=("ctx",),
        legal_actions=(CanonicalAction("act", "lean.tactic", ("goal",), expected_usefulness=0.5),),
        plausible_invalid_actions=(),
    )


def test_a_foreign_canonical_state_imports_with_its_inventions_recorded() -> None:
    imported = from_canonical(_foreign_state())
    assert set(imported.losses.features(LossKind.SYNTHESIZED)) == {
        "scope_forest",
        "claim_epistemics",
        "verifier_version",
    }
    assert parse_state(render_state(imported.state)) == imported.state
    assert imported.state.goals[0].goal_id == "goal.0"
    assert imported.state.declarations[1].kind.value == "forall"
    assert dict(imported.state.declarations[0].attributes)["canonical.unit"] == "kg"


def test_an_imported_foreign_state_can_be_pushed_back_through_the_substrate() -> None:
    imported = from_canonical(_foreign_state()).state
    state_to_payload(to_canonical(imported).canonical)
    assert from_canonical(to_canonical(imported).canonical).state == imported


def test_carriers_perturb_the_mathematical_hash_as_documented() -> None:
    state = build_rich_state()
    carried = to_canonical(state).canonical.mathematical_hash
    dropped = to_canonical(state, policy=LossPolicy.DROP).canonical.mathematical_hash
    assert carried != dropped
