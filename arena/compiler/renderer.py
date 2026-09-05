"""Representation-neutral renderer entry point."""

from arena.canonical.schema import CanonicalState
from arena.languages.base import CandidateLanguage


def render_state(language: CandidateLanguage, state: CanonicalState) -> str:
    rendered = language.render(state)
    if not rendered:
        raise ValueError(f"{language.candidate_id} produced an empty surface")
    return rendered
