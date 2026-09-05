"""Static compiler checks used by the semantic survival gate."""

from __future__ import annotations

from dataclasses import dataclass

from arena.canonical.schema import CanonicalState
from arena.languages.base import CandidateLanguage


@dataclass(frozen=True, slots=True)
class RoundtripCheck:
    candidate_id: str
    expected_hash: str
    observed_hash: str | None
    exact: bool
    error: str | None = None


def validate_roundtrip(
    language: CandidateLanguage, state: CanonicalState, *, exact_artifact: bool = True
) -> RoundtripCheck:
    try:
        observed = language.parse(language.render(state))
    except Exception as error:
        return RoundtripCheck(
            language.candidate_id,
            state.artifact_hash if exact_artifact else state.mathematical_hash,
            None,
            False,
            repr(error),
        )
    expected_hash = state.artifact_hash if exact_artifact else state.mathematical_hash
    observed_hash = observed.artifact_hash if exact_artifact else observed.mathematical_hash
    return RoundtripCheck(
        language.candidate_id,
        expected_hash,
        observed_hash,
        expected_hash == observed_hash,
    )
