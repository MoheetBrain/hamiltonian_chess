"""Adversarial assurance primitives.

The package reports finite, reproducible observations.  Nothing in this package treats
passing a bounded campaign as a proof of correctness outside the declared campaign.
"""

from arena.assurance.exhaustive import ExhaustiveResult
from arena.assurance.failures import Failure, FailureStore
from arena.assurance.properties import PropertyResult, PropertyStatus
from arena.assurance.suite import AssuranceReport, run_assurance_suite

__all__ = [
    "ExhaustiveResult",
    "AssuranceReport",
    "Failure",
    "FailureStore",
    "PropertyResult",
    "PropertyStatus",
    "run_assurance_suite",
]
