"""Tier-0/1 deterministic evaluation over the canonical world."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass

from arena.assurance.fuzz import run_parser_fuzz
from arena.assurance.properties import PropertyStatus, semantic_property_suite
from arena.assurance.side_channels import Observation, audit
from arena.canonical.schema import CanonicalState, stable_hash
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.compiler.validator import validate_roundtrip
from arena.fitness.gates import (
    GateZeroEvidence,
    LexicographicFitness,
    evaluate_lexicographic,
)
from arena.fitness.metrics import CoverageMetrics, EfficiencyMetrics
from arena.languages.base import CandidateLanguage
from arena.tasks.schema import ArenaTask
from arena.verifier.native import NativeVerifier


@dataclass(frozen=True, slots=True)
class StaticEvaluation:
    candidate_id: str
    task_set_hash: str
    tasks: int
    states_checked: int
    exact_roundtrips: int
    mathematical_roundtrips: int
    native_accepts: int
    render_collisions: int
    malformed_cases: int
    malformed_accepts: int
    semantic_mutation_accepts: int
    answer_leaks: int
    coverage: CoverageMetrics
    efficiency: EfficiencyMetrics
    fitness: LexicographicFitness
    failures: tuple[str, ...]

    @property
    def passed_gate_zero(self) -> bool:
        return self.fitness.gate_zero.passed

    def metric_values(self) -> dict[str, float]:
        return {
            "semantic_fidelity": self.mathematical_roundtrips / self.states_checked,
            "exact_roundtrip": self.exact_roundtrips / self.states_checked,
            "native_accept_rate": self.native_accepts / self.states_checked,
            "composition": self.coverage.composition_closure,
            "coverage": self.coverage.canonical_world_coverage,
            "tokens_proxy": self.efficiency.tokens,
            "compiler_latency_ms": self.efficiency.compile_latency_ms,
            "answer_leaks": float(self.answer_leaks),
            "critical_false_accepts": float(self.semantic_mutation_accepts),
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "task_set_hash": self.task_set_hash,
            "tasks": self.tasks,
            "states_checked": self.states_checked,
            "exact_roundtrips": self.exact_roundtrips,
            "mathematical_roundtrips": self.mathematical_roundtrips,
            "native_accepts": self.native_accepts,
            "render_collisions": self.render_collisions,
            "malformed_cases": self.malformed_cases,
            "malformed_accepts": self.malformed_accepts,
            "semantic_mutation_accepts": self.semantic_mutation_accepts,
            "answer_leaks": self.answer_leaks,
            "coverage": asdict(self.coverage),
            "efficiency": asdict(self.efficiency),
            "fitness": {
                "gate_zero": {
                    "status": self.fitness.gate_zero.status.value,
                    "reasons": list(self.fitness.gate_zero.reasons),
                },
                "coverage_gate": {
                    "status": self.fitness.coverage_gate.status.value,
                    "reasons": list(self.fitness.coverage_gate.reasons),
                },
                "eligible": self.fitness.eligible,
                "general_candidate": self.fitness.is_general_candidate,
            },
            "metrics": self.metric_values(),
            "failures": list(self.failures),
            "measurement_notes": {
                "tokens_proxy": "ceil(UTF-8 bytes / 4); not a model tokenizer",
                "compiler_latency_ms": "wall-clock render plus parse mean",
                "model_metrics": "UNMEASURED; Tier 2 matched adaptation required",
                "semantic_mutations": "frozen 16-case verifier mutation suite",
            },
        }


def _ratio(successes: int, total: int) -> float:
    return successes / total if total else 0.0


def _task_hash(tasks: tuple[ArenaTask, ...]) -> str:
    return stable_hash({"task_hashes": sorted(task.content_hash for task in tasks)})


def _states(task: ArenaTask) -> tuple[CanonicalState, CanonicalState]:
    return task.trajectory.initial_state, task.trajectory.final_state


def evaluate_static(
    language: CandidateLanguage, tasks: tuple[ArenaTask, ...], *, fuzz_cases: int = 16
) -> StaticEvaluation:
    """Run lossless roundtrip, native reconstruction, leakage, and efficiency checks."""

    if not tasks:
        raise ValueError("static evaluation requires at least one task")
    verifier = NativeVerifier()
    exact = 0
    mathematical = 0
    native_accepts = 0
    characters: list[float] = []
    token_proxies: list[float] = []
    bits: list[float] = []
    latencies_ms: list[float] = []
    failures: list[str] = []
    task_success: dict[str, bool] = {}
    render_to_hashes: defaultdict[str, set[str]] = defaultdict(set)

    for task in tasks:
        successful = True
        for state in _states(task):
            started = time.perf_counter_ns()
            source = language.render(state)
            check = validate_roundtrip(language, state)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies_ms.append(elapsed_ms)
            characters.append(float(len(source)))
            byte_count = len(source.encode("utf-8"))
            token_proxies.append(float(max(1, math.ceil(byte_count / 4))))
            bits.append(float(byte_count * 8))
            render_to_hashes[stable_hash(source)].add(state.mathematical_hash)
            if check.exact:
                exact += 1
            try:
                decoded = language.parse(source)
            except Exception as error:
                successful = False
                failures.append(f"{task.task_id}: parse failed: {error!r}")
                continue
            if decoded.mathematical_hash == state.mathematical_hash:
                mathematical += 1
            else:
                successful = False
                failures.append(f"{task.task_id}: mathematical roundtrip mismatch")
            if verifier.verify_state(decoded).accepted:
                native_accepts += 1
            else:
                successful = False
                failures.append(f"{task.task_id}: decoded state failed native verification")
        task_success[task.task_id] = successful

    states_checked = len(tasks) * 2
    render_collisions = sum(len(hashes) - 1 for hashes in render_to_hashes.values())
    if render_collisions:
        failures.append(f"render collisions: {render_collisions}")

    domain_total: defaultdict[str, int] = defaultdict(int)
    domain_pass: defaultdict[str, int] = defaultdict(int)
    for task in tasks:
        domain_total[task.dimensions.domain] += 1
        domain_pass[task.dimensions.domain] += int(task_success[task.task_id])

    def subset_rate(predicate: Callable[[ArenaTask], bool]) -> float:
        selected = [task for task in tasks if predicate(task)]
        return _ratio(sum(task_success[task.task_id] for task in selected), len(selected))

    task_passes = sum(task_success.values())
    coverage = CoverageMetrics(
        canonical_world_coverage=_ratio(task_passes, len(tasks)),
        construct_coverage=(
            min(_ratio(domain_pass[name], total) for name, total in domain_total.items())
        ),
        composition_closure=subset_rate(lambda task: task.dimensions.composition_count > 1),
        cross_domain_composition=subset_rate(
            lambda task: task.dimensions.cross_domain_interaction > 0
        ),
        binder_coverage=subset_rate(lambda task: task.dimensions.scope_depth > 0),
        definedness_coverage=subset_rate(lambda task: task.dimensions.partiality > 0),
        transition_coverage=_ratio(task_passes, len(tasks)),
        missing_constructs=tuple(
            sorted(name for name, total in domain_total.items() if domain_pass[name] < total)
        ),
    )

    sample_source = language.render(tasks[0].trajectory.initial_state)
    fuzz = run_parser_fuzz(sample_source, language.parse, seed=0, random_cases=max(0, fuzz_cases))
    malformed_accepts = len(fuzz.unexpected_accepts)

    leakage_observations: list[Observation] = []
    for task in tasks:
        projected = project_state_for_observation(
            task.trajectory.initial_state, ObservationKind.NEXT_ACTION
        )
        source = language.render(projected)
        target = task.trajectory.initial_state.legal_actions[0].action_id
        leakage_observations.append(
            Observation(
                task.task_id,
                language.candidate_id,
                task.dimensions.domain,
                task.trajectory.final_answer.op if task.trajectory.final_answer else "none",
                len(source),
                task_success[task.task_id],
                source,
                target,
            )
        )
    leakage = audit(tuple(leakage_observations))

    mean_characters = sum(characters) / len(characters)
    mean_tokens = sum(token_proxies) / len(token_proxies)
    efficiency = EfficiencyMetrics(
        characters=mean_characters,
        tokens=mean_tokens,
        bits_estimate=sum(bits) / len(bits),
        ast_depth=0.0,
        parse_complexity=1.0,
        compile_latency_ms=sum(latencies_ms) / len(latencies_ms),
        model_latency_ms=0.0,
        error_localization=_ratio(fuzz.expected_rejections - malformed_accepts, fuzz.total),
        edit_robustness=1.0 - _ratio(malformed_accepts, fuzz.total),
        grammar_complexity=float(len(language.genome.genes_dict())),
        training_token_requirement=mean_tokens,
    )
    decoded_base = language.parse(language.render(tasks[0].trajectory.initial_state))
    semantic_properties = semantic_property_suite(decoded_base, verifier)
    semantic_mutation_accepts = sum(
        item.status == PropertyStatus.FAIL
        and item.expected == "accepted=False"
        and item.observed == "accepted=True"
        for item in semantic_properties
    )
    gate_zero = GateZeroEvidence(
        critical_false_accepts=semantic_mutation_accepts,
        canonical_collisions=render_collisions,
        silent_semantic_losses=states_checked - mathematical,
        required_roundtrip_successes=exact,
        required_roundtrip_total=states_checked,
    )
    fitness = evaluate_lexicographic(language.candidate_id, gate_zero, coverage)
    return StaticEvaluation(
        language.candidate_id,
        _task_hash(tasks),
        len(tasks),
        states_checked,
        exact,
        mathematical,
        native_accepts,
        render_collisions,
        fuzz.total,
        malformed_accepts,
        semantic_mutation_accepts,
        len(leakage.literal_answer_leaks),
        coverage,
        efficiency,
        fitness,
        tuple(failures[:100]),
    )
