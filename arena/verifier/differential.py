"""Conservative adjudication across partially overlapping independent verifiers."""

from __future__ import annotations

from dataclasses import dataclass

from arena.canonical.schema import CanonicalExpression
from arena.verifier.external import ExternalStatus, ExternalVerdict
from arena.verifier.numeric import NumericFalsifier
from arena.verifier.sympy_adapter import SympyAdapter
from arena.verifier.z3_adapter import Z3Adapter


@dataclass(frozen=True)
class DifferentialResult:
    claim_hash: str
    verdicts: tuple[ExternalVerdict, ...]
    unresolved_disagreement: bool
    supported_verifiers: int


class DifferentialVerifier:
    def __init__(self) -> None:
        self.sympy = SympyAdapter()
        self.z3 = Z3Adapter()
        self.numeric = NumericFalsifier()

    def check_truth(self, proposition: CanonicalExpression, *, seed: int = 0) -> DifferentialResult:
        verdicts = (
            self.sympy.check_truth(proposition),
            self.z3.check_truth(proposition),
            self.numeric.check_truth(proposition, seed=seed),
        )
        supported = [
            verdict
            for verdict in verdicts
            if verdict.status in {ExternalStatus.AGREE, ExternalStatus.DISAGREE}
        ]
        statuses = {verdict.status for verdict in supported}
        return DifferentialResult(
            proposition.content_hash,
            verdicts,
            len(statuses) > 1,
            len(supported),
        )
