"""Compiler diagnostics shared by every candidate-language adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DiagnosticSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class CompilerDiagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    offset: int | None = None


class CompilationError(ValueError):
    """A surface could not be converted to the canonical world."""

    def __init__(self, diagnostic: CompilerDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.code}: {diagnostic.message}")
