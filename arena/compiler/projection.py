"""Prevent task labels and oracle-only fields from leaking into solver observations."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from arena.canonical.schema import CanonicalAction, CanonicalState


class ObservationKind(StrEnum):
    FULL_DECODE = "FULL_DECODE"
    NEXT_ACTION = "NEXT_ACTION"
    INVALID_ACTION = "INVALID_ACTION"
    NEXT_STATE = "NEXT_STATE"
    COMPLETE = "COMPLETE"


def scrub_action_labels(action: CanonicalAction) -> CanonicalAction:
    """Remove evaluation-only usefulness without changing mathematical action content."""

    return replace(action, expected_usefulness=0.0)


def project_state_for_observation(state: CanonicalState, kind: ObservationKind) -> CanonicalState:
    """Return exactly the information a renderer is allowed to communicate.

    NEXT_ACTION and COMPLETE must not expose the answer sets. FULL_DECODE includes action
    structure but strips the evaluation-only usefulness signal. INVALID_ACTION includes both
    proposal pools without their labels; its caller must randomize/counterbalance presentation.
    """

    base = replace(state, execution_metadata=())
    if kind in {ObservationKind.NEXT_ACTION, ObservationKind.COMPLETE}:
        return replace(base, legal_actions=(), plausible_invalid_actions=())
    if kind == ObservationKind.NEXT_STATE:
        return replace(base, plausible_invalid_actions=())
    return replace(
        base,
        legal_actions=tuple(scrub_action_labels(action) for action in base.legal_actions),
        plausible_invalid_actions=tuple(
            scrub_action_labels(action) for action in base.plausible_invalid_actions
        ),
    )


def assert_no_answer_leakage(observation: CanonicalState, kind: ObservationKind) -> None:
    if kind in {ObservationKind.NEXT_ACTION, ObservationKind.COMPLETE} and (
        observation.legal_actions or observation.plausible_invalid_actions
    ):
        raise ValueError(f"{kind} observation contains action labels")
    for action in (*observation.legal_actions, *observation.plausible_invalid_actions):
        if action.expected_usefulness != 0.0:
            raise ValueError("observation contains oracle usefulness")
