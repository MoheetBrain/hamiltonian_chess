"""Representation-neutral parser entry point."""

from __future__ import annotations

from arena.canonical.schema import CanonicalState
from arena.languages.base import CandidateLanguage, LanguageParseError

from .diagnostics import CompilationError, CompilerDiagnostic, DiagnosticSeverity


def parse_state(language: CandidateLanguage, source: str) -> CanonicalState:
    try:
        return language.parse(source)
    except LanguageParseError as error:
        raise CompilationError(
            CompilerDiagnostic("SURFACE_PARSE_ERROR", DiagnosticSeverity.ERROR, str(error))
        ) from error
