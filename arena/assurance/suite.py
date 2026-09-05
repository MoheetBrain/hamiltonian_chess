"""Frozen v0 assurance orchestration with explicit denominators."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from arena.assurance.exhaustive import (
    ExhaustiveResult,
    enumerate_directed_graphs,
    enumerate_scalar_expressions,
    run_universe,
)
from arena.assurance.properties import PropertyStatus, semantic_property_suite
from arena.canonical.schema import CanonicalExpression, CanonicalState, EvidenceNode, stable_hash
from arena.verifier.differential import DifferentialVerifier
from arena.verifier.native import NativeVerifier


@dataclass(frozen=True, slots=True)
class AssuranceReport:
    semantic_properties: int
    semantic_passes: int
    semantic_failures: int
    unsupported_properties: int
    false_accepts: int
    exhaustive: tuple[ExhaustiveResult, ...]
    differential_claims: int
    differential_supported_checks: int
    differential_disagreements: int

    @property
    def exhaustive_cases(self) -> int:
        return sum(item.enumerated_cases for item in self.exhaustive)

    @property
    def exhaustive_complete(self) -> bool:
        return all(item.complete and not item.failed_case_ids for item in self.exhaustive)

    @property
    def critical_failures(self) -> int:
        return (
            self.semantic_failures
            + self.differential_disagreements
            + sum(len(item.failed_case_ids) for item in self.exhaustive)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "arena-assurance-v0.1.0",
            "semantic_properties": self.semantic_properties,
            "semantic_passes": self.semantic_passes,
            "semantic_failures": self.semantic_failures,
            "unsupported_properties": self.unsupported_properties,
            "false_accepts": self.false_accepts,
            "bounded_universes": [asdict(item) for item in self.exhaustive],
            "exhaustive_cases": self.exhaustive_cases,
            "exhaustive_complete": self.exhaustive_complete,
            "differential_claims": self.differential_claims,
            "differential_supported_checks": self.differential_supported_checks,
            "differential_disagreements": self.differential_disagreements,
            "critical_failures": self.critical_failures,
            "claim_boundary": (
                "Results apply only to these versioned properties and finite universes."
            ),
        }


def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
    active: set[str] = set()
    complete: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in complete:
            return False
        active.add(node)
        if any(visit(target) for target in graph[node]):
            return True
        active.remove(node)
        complete.add(node)
        return False

    return any(visit(node) for node in graph)


def _graph_verdict(base: CanonicalState, graph: dict[str, tuple[str, ...]]) -> bool:
    evidence = tuple(
        EvidenceNode(node, "VERIFIED", dependencies, "bounded-exhaustive")
        for node, dependencies in sorted(graph.items())
    )
    accepted = NativeVerifier().verify_state(replace(base, evidence_dependencies=evidence)).accepted
    return accepted == (not _has_cycle(graph))


def _true_claims() -> tuple[CanonicalExpression, ...]:
    def integer(value: int) -> CanonicalExpression:
        return CanonicalExpression("integer", value=value, sort="Int")

    def boolean(value: bool) -> CanonicalExpression:
        return CanonicalExpression("bool", value=value, sort="Bool")

    return (
        CanonicalExpression(
            "eq",
            (CanonicalExpression("add", (integer(1), integer(2)), sort="Int"), integer(3)),
            sort="Bool",
        ),
        CanonicalExpression(
            "eq",
            (CanonicalExpression("mul", (integer(3), integer(4)), sort="Int"), integer(12)),
            sort="Bool",
        ),
        CanonicalExpression("implies", (boolean(True), boolean(True)), sort="Bool"),
    )


def run_assurance_suite(base: CanonicalState) -> AssuranceReport:
    verifier = NativeVerifier()
    properties = semantic_property_suite(base, verifier)
    failures = tuple(item for item in properties if item.status == PropertyStatus.FAIL)
    false_accepts = sum(
        item.expected == "accepted=False" and item.observed == "accepted=True" for item in failures
    )

    expressions = enumerate_scalar_expressions(max_depth=2)
    expression_universe = run_universe(
        "canonical-expression-roundtrip-depth-2",
        expressions,
        lambda item: item.content_hash,
        lambda item: CanonicalExpression.from_dict(item.to_dict()) == item,
        parameters={"atoms": "-1,0,1", "operators": "add,sub,mul", "max_depth": "2"},
    )
    graphs = enumerate_directed_graphs(3)
    graph_universe = run_universe(
        "native-evidence-graphs-n3",
        graphs,
        lambda item: stable_hash(item),
        lambda item: _graph_verdict(base, item),
        parameters={"nodes": "3", "edges": "all loop-free directed subsets"},
    )

    checker = DifferentialVerifier()
    differential = tuple(
        checker.check_truth(claim, seed=index) for index, claim in enumerate(_true_claims())
    )
    return AssuranceReport(
        semantic_properties=len(properties),
        semantic_passes=sum(item.status == PropertyStatus.PASS for item in properties),
        semantic_failures=len(failures),
        unsupported_properties=sum(
            item.status == PropertyStatus.UNSUPPORTED for item in properties
        ),
        false_accepts=false_accepts,
        exhaustive=(expression_universe, graph_universe),
        differential_claims=len(differential),
        differential_supported_checks=sum(item.supported_verifiers for item in differential),
        differential_disagreements=sum(item.unresolved_disagreement for item in differential),
    )
