"""Lexicographic semantic and expressiveness gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from arena.fitness.metrics import CoverageMetrics, EfficiencyMetrics, MachineMetrics


class GateStatus(StrEnum):
    PASS = "PASS"
    NICHE = "NICHE"
    ELIMINATED = "ELIMINATED"


@dataclass(frozen=True, slots=True)
class GateZeroEvidence:
    critical_false_accepts: int = 0
    canonical_collisions: int = 0
    unresolved_scope_corruptions: int = 0
    proof_cycles: int = 0
    untracked_definedness_escapes: int = 0
    silent_semantic_losses: int = 0
    required_roundtrip_successes: int = 0
    required_roundtrip_total: int = 0

    def __post_init__(self) -> None:
        for value in (
            self.critical_false_accepts,
            self.canonical_collisions,
            self.unresolved_scope_corruptions,
            self.proof_cycles,
            self.untracked_definedness_escapes,
            self.silent_semantic_losses,
            self.required_roundtrip_successes,
            self.required_roundtrip_total,
        ):
            if value < 0:
                raise ValueError("Gate 0 counts must be non-negative")
        if self.required_roundtrip_successes > self.required_roundtrip_total:
            raise ValueError("roundtrip successes cannot exceed total")


SemanticSurvivalEvidence = GateZeroEvidence


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: int
    status: GateStatus
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASS

    @property
    def eliminated(self) -> bool:
        return self.status == GateStatus.ELIMINATED


def evaluate_gate_zero(evidence: GateZeroEvidence) -> GateResult:
    reasons: list[str] = []
    count_checks = (
        ("known critical false accepts", evidence.critical_false_accepts),
        ("canonical collisions", evidence.canonical_collisions),
        ("unresolved scope corruptions", evidence.unresolved_scope_corruptions),
        ("proof cycles", evidence.proof_cycles),
        ("untracked definedness escapes", evidence.untracked_definedness_escapes),
        ("silent semantic losses", evidence.silent_semantic_losses),
    )
    reasons.extend(f"{label}: {count}" for label, count in count_checks if count)
    if evidence.required_roundtrip_total <= 0:
        reasons.append("required-world canonical roundtrip checks are absent")
    elif evidence.required_roundtrip_successes != evidence.required_roundtrip_total:
        failures = evidence.required_roundtrip_total - evidence.required_roundtrip_successes
        reasons.append(f"canonical roundtrip failures: {failures}")
    return GateResult(
        0,
        GateStatus.ELIMINATED if reasons else GateStatus.PASS,
        tuple(reasons),
    )


def evaluate_coverage_gate(
    metrics: CoverageMetrics,
    *,
    required_minimum: float = 1.0,
    allow_niche: bool = True,
) -> GateResult:
    if not 0.0 <= required_minimum <= 1.0:
        raise ValueError("required_minimum must lie in [0, 1]")
    failures = tuple(
        f"{name}={value:.6g} below {required_minimum:.6g}"
        for name, value in metrics.as_mapping().items()
        if value < required_minimum
    )
    if not failures:
        return GateResult(1, GateStatus.PASS, ())
    if allow_niche and metrics.canonical_world_coverage > 0 and metrics.construct_coverage > 0:
        return GateResult(1, GateStatus.NICHE, failures)
    return GateResult(1, GateStatus.ELIMINATED, failures)


@dataclass(frozen=True, slots=True)
class LexicographicFitness:
    candidate_id: str
    gate_zero: GateResult
    coverage_gate: GateResult
    coverage: CoverageMetrics
    machine: MachineMetrics | None = None
    efficiency: EfficiencyMetrics | None = None

    @property
    def eligible(self) -> bool:
        """Only full semantic survivors may enter Pareto competition."""

        return self.gate_zero.passed and not self.coverage_gate.eliminated

    @property
    def is_general_candidate(self) -> bool:
        return self.gate_zero.passed and self.coverage_gate.passed


def evaluate_lexicographic(
    candidate_id: str,
    gate_zero_evidence: GateZeroEvidence,
    coverage: CoverageMetrics,
    *,
    machine: MachineMetrics | None = None,
    efficiency: EfficiencyMetrics | None = None,
    required_coverage: float = 1.0,
    allow_niche: bool = True,
) -> LexicographicFitness:
    gate_zero = evaluate_gate_zero(gate_zero_evidence)
    # Later gates are recorded for diagnosis, but cannot compensate for Gate 0.
    coverage_result = evaluate_coverage_gate(
        coverage, required_minimum=required_coverage, allow_niche=allow_niche
    )
    return LexicographicFitness(
        candidate_id, gate_zero, coverage_result, coverage, machine, efficiency
    )


evaluate_gate0 = evaluate_gate_zero
