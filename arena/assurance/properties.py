"""Executable semantic properties with explicit pass/fail/unsupported accounting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from arena.assurance.mutations import MutationCase, semantic_mutations
from arena.canonical.schema import CanonicalState
from arena.verifier.base import Verifier


class PropertyStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class PropertyResult:
    property_id: str
    status: PropertyStatus
    expected: str
    observed: str
    details: str


class RoundtripLanguage(Protocol):
    candidate_id: str

    def render(self, state: CanonicalState) -> str: ...

    def parse(self, source: str) -> CanonicalState: ...


def check_mutation(case: MutationCase, verifier: Verifier) -> PropertyResult:
    if not case.witness():
        return PropertyResult(
            case.mutation_id,
            PropertyStatus.UNSUPPORTED,
            str(case.expected_accepted),
            "witness unavailable",
            case.description,
        )
    if isinstance(case.subject, CanonicalState):
        accepted = verifier.verify_state(case.subject).accepted
    else:
        accepted = verifier.verify_transition(case.subject).accepted
    status = PropertyStatus.PASS if accepted == case.expected_accepted else PropertyStatus.FAIL
    return PropertyResult(
        case.mutation_id,
        status,
        f"accepted={case.expected_accepted}",
        f"accepted={accepted}",
        case.description,
    )


def semantic_property_suite(
    state: CanonicalState, verifier: Verifier
) -> tuple[PropertyResult, ...]:
    return tuple(check_mutation(case, verifier) for case in semantic_mutations(state))


def roundtrip_property(state: CanonicalState, language: RoundtripLanguage) -> PropertyResult:
    property_id = f"roundtrip:{language.candidate_id}:{state.mathematical_hash}"
    try:
        parsed = language.parse(language.render(state))
    except Exception as error:
        return PropertyResult(
            property_id,
            PropertyStatus.FAIL,
            state.mathematical_hash,
            "parse-error",
            repr(error),
        )
    observed = parsed.mathematical_hash
    return PropertyResult(
        property_id,
        PropertyStatus.PASS if observed == state.mathematical_hash else PropertyStatus.FAIL,
        state.mathematical_hash,
        observed,
        "canonical mathematical identity after render/parse",
    )
