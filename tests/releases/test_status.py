"""Item D: VERIFIED must be unrepresentable without a named verifier and a record."""

from __future__ import annotations

import pytest

from releases.TRAINING_LANGUAGE_V0 import (
    Action,
    Claim,
    ClaimRole,
    Evidence,
    Goal,
    Obligation,
    Scope,
    State,
    Status,
    StatusError,
    Term,
    VerificationOutcome,
    parse_state,
    render_state,
)

from .conftest import PROP

VERIFIER = Evidence("e.ok", Status.VERIFIED, "arena.native", "0.1.0", details="accepted")
UNVERIFIED = Evidence("e.no", Status.DERIVED, "arena.native", "0.1.0")


def test_verified_claim_without_evidence_raises() -> None:
    with pytest.raises(StatusError, match="without a verification record"):
        Claim("c", ClaimRole.FACT, "r", Term("p", PROP), Status.VERIFIED)


def test_verified_goal_without_evidence_raises() -> None:
    with pytest.raises(StatusError):
        Goal("g", "r", Term("p", PROP), Status.VERIFIED)


def test_verified_obligation_without_evidence_raises() -> None:
    with pytest.raises(StatusError):
        Obligation("o", "r", Term("p", PROP), Status.VERIFIED)


def test_verified_action_without_evidence_raises() -> None:
    with pytest.raises(StatusError):
        Action("a", "close", status=Status.VERIFIED)


@pytest.mark.parametrize("verifier,version", [("", "0.1.0"), ("arena.native", ""), ("", "")])
def test_verified_evidence_without_a_named_verifier_raises(verifier: str, version: str) -> None:
    with pytest.raises(StatusError, match="named"):
        Evidence("e", Status.VERIFIED, verifier, version)


def test_state_refuses_a_verified_claim_pointing_at_unverified_evidence() -> None:
    with pytest.raises(StatusError, match="is DERIVED"):
        State(
            state_id="s",
            scopes=(Scope("r"),),
            claims=(Claim("c", ClaimRole.FACT, "r", Term("p", PROP), Status.VERIFIED, "e.no"),),
            evidence=(UNVERIFIED,),
        )


def test_state_accepts_a_verified_claim_backed_by_a_verified_record() -> None:
    state = State(
        state_id="s",
        scopes=(Scope("r"),),
        claims=(Claim("c", ClaimRole.FACT, "r", Term("p", PROP), Status.VERIFIED, "e.ok"),),
        evidence=(VERIFIER,),
    )
    assert parse_state(render_state(state)) == state


def test_parser_refuses_a_verified_claim_with_no_evidence_link() -> None:
    document = "TL0 0.1.0 s\nscope r _\nclaim c fact r VERIFIED _ (p [Prop] _)\nstatus OPEN\n"
    with pytest.raises(StatusError):
        parse_state(document)


def test_parser_refuses_a_verified_claim_backed_by_unverified_evidence() -> None:
    document = (
        "TL0 0.1.0 s\nscope r _\n"
        "claim c fact r VERIFIED e.no (p [Prop] _)\n"
        'evid e.no DERIVED "arena.native" "0.1.0" _ ""\n'
        "status OPEN\n"
    )
    with pytest.raises(StatusError):
        parse_state(document)


def test_parser_refuses_verified_evidence_with_an_empty_verifier() -> None:
    document = 'TL0 0.1.0 s\nscope r _\nevid e VERIFIED "" "" _ ""\nstatus OPEN\n'
    with pytest.raises(StatusError):
        parse_state(document)


def test_training_outcome_obeys_the_same_rule() -> None:
    with pytest.raises(StatusError):
        VerificationOutcome("", "", Status.VERIFIED, True)
    with pytest.raises(StatusError):
        VerificationOutcome("arena.native", "0.1.0", Status.VERIFIED, accepted=False)
    assert VerificationOutcome("arena.native", "0.1.0", Status.VERIFIED, True).accepted


def test_every_status_is_spelled_exactly_once() -> None:
    assert [item.value for item in Status] == [
        "ASSUMED",
        "PROPOSED",
        "DERIVED",
        "VERIFIED",
        "REFUTED",
        "OPEN",
    ]
