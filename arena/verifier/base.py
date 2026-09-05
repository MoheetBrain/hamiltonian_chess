"""Verifier contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from arena.canonical.schema import CanonicalState, CanonicalTransition


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class VerificationIssue:
    code: str
    severity: Severity
    message: str
    path: str = ""


@dataclass(frozen=True)
class VerificationResult:
    verifier: str
    version: str
    accepted: bool
    issues: tuple[VerificationIssue, ...]

    @property
    def critical_count(self) -> int:
        return sum(issue.severity == Severity.CRITICAL for issue in self.issues)


class Verifier(Protocol):
    name: str
    version: str

    def verify_state(self, state: CanonicalState) -> VerificationResult: ...

    def verify_transition(self, transition: CanonicalTransition) -> VerificationResult: ...
