"""Canonicalization boundary for candidate surfaces."""

from arena.canonical.schema import CanonicalState
from arena.languages.base import CandidateLanguage

from .parser import parse_state


def canonicalize(language: CandidateLanguage, source: str) -> CanonicalState:
    """Decode a candidate surface without granting it any truth authority."""

    return parse_state(language, source).without_execution_metadata()
