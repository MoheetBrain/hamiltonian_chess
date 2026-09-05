"""Language-independent projection, parsing, rendering, and diagnostics."""

from arena.compiler.canonicalizer import canonicalize
from arena.compiler.diagnostics import CompilationError, CompilerDiagnostic, DiagnosticSeverity
from arena.compiler.parser import parse_state
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.compiler.renderer import render_state
from arena.compiler.validator import RoundtripCheck, validate_roundtrip

__all__ = [
    "CompilationError",
    "CompilerDiagnostic",
    "DiagnosticSeverity",
    "ObservationKind",
    "RoundtripCheck",
    "canonicalize",
    "parse_state",
    "project_state_for_observation",
    "render_state",
    "validate_roundtrip",
]
