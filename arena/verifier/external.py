"""Shared result type for partial independent verifier adapters."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExternalStatus(StrEnum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"
    UNSUPPORTED = "UNSUPPORTED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ExternalVerdict:
    verifier: str
    version: str
    status: ExternalStatus
    claim: str
    details: str
