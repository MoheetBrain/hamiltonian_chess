"""Fitness-v2 semantic-reading instrument and local-model qualification.

This module is deliberately versioned separately from fitness-v1.  It derives
counterfactual minimal pairs from Arena Gold states, validates their truth with a
domain-specific oracle, and measures whether a solver changes its answer when the
decisive mathematical relation changes.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    GoldStatus,
    Obligation,
    canonical_json,
    stable_hash,
)
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.evaluation.landscape import paired_comparison, spearman
from arena.experiments.fitness_v1 import (
    frozen_task_split,
    materialize_population,
    tier2a_candidate_roster,
)
from arena.genome.schema import LanguageGenome
from arena.genome.seeds import L0_STRUCTURED_ENGLISH, SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.storage.artifacts import ArtifactStore
from arena.tasks.generators.world_v0 import build_world_v0
from arena.tasks.schema import ArenaTask
from arena.verifier.native import NativeVerifier

EXPERIMENT_VERSION = "arena-representation-fitness-v2"
INSTRUMENT_VERSION = "arena-semantic-counterfactual-instrument-v2.0.0"
EXPERIMENT_SEED = 20260905


class ProbeSlice(StrEnum):
    PROTOCOL_DEV = "PROTOCOL_DEV"
    MODEL_QUALIFICATION = "MODEL_QUALIFICATION"
    CALIBRATION_DEV = "CALIBRATION_DEV"
    TIER2A_SCOUT = "TIER2A_SCOUT"
    TIER2B_PROMOTION = "TIER2B_PROMOTION"
    OOD = "OOD"


class ProbeVariant(StrEnum):
    ORIGINAL = "ORIGINAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DESTROYED_ORIGINAL = "DESTROYED_ORIGINAL"
    DESTROYED_COUNTERFACTUAL = "DESTROYED_COUNTERFACTUAL"
    SWAPPED_ORIGINAL = "SWAPPED_ORIGINAL"
    SWAPPED_COUNTERFACTUAL = "SWAPPED_COUNTERFACTUAL"


class TruthKind(StrEnum):
    MATHEMATICAL = "MATHEMATICAL"
    NEGATIVE_CONTROL_TARGET = "NEGATIVE_CONTROL_TARGET"


class ResponseProtocol(StrEnum):
    JSON_AB = "JSON_AB"
    CANONICAL_ANSWER = "CANONICAL_ANSWER"
    JSON_PQ = "JSON_PQ"
    ACTION_KEY = "ACTION_KEY"


@dataclass(frozen=True, slots=True)
class QualificationThresholds:
    q0_valid_rate: float = 0.95
    q1_accuracy: float = 0.70
    margin_over_constant: float = 0.15
    semantic_flip_consistency: float = 0.60
    positive_negative_gap: float = 0.15
    max_position_preference: float = 0.85

    def to_dict(self) -> dict[str, float]:
        return {
            "q0_valid_rate": self.q0_valid_rate,
            "q1_accuracy": self.q1_accuracy,
            "margin_over_constant": self.margin_over_constant,
            "semantic_flip_consistency": self.semantic_flip_consistency,
            "positive_negative_gap": self.positive_negative_gap,
            "max_position_preference": self.max_position_preference,
        }


THRESHOLDS = QualificationThresholds()
RUNTIME_CONFIG: dict[str, Any] = {
    "engine": "ollama",
    "num_ctx": 8192,
    "temperature": 0.0,
    "seed": EXPERIMENT_SEED,
    "num_predict": 64,
    "top_k": 64,
    "top_p": 0.95,
    "think": False,
}
RUNTIME_CONFIG_HASH = stable_hash(RUNTIME_CONFIG)
QUALIFIED_MODEL = {
    "name": "gemma4:12b",
    "digest": "4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c",
    "parameter_size": "11.9B",
    "quantization": "Q4_K_M",
}
FROZEN_PROTOCOL = ResponseProtocol.JSON_AB
CALIBRATION_RULE = {
    "instrument": "at least one permanent control passes every model-qualification threshold",
    "headroom": "positive-accuracy range >= 0.15 and minimum positive accuracy <= 0.85",
    "ceiling": "every control positive accuracy >= 0.90",
    "floor": "no control passes qualification",
}
TIER2A_SIGNAL_RULE = {
    "accuracy_range": 0.15,
    "minimum_large_parent_child_edges": 2,
    "large_parent_child_delta": 0.10,
    "minimum_candidate_valid_response_rate": 0.95,
    "promotion_count": 8,
}


@dataclass(frozen=True, slots=True)
class SemanticProbe:
    probe_id: str
    pair_id: str
    slice_name: ProbeSlice
    mechanism: str
    source_task_id: str
    source_state_hash: str
    transformation_type: str
    transformation_seed: int
    variant: ProbeVariant
    state: CanonicalState
    question: str
    options: tuple[CanonicalExpression, CanonicalExpression]
    expected_index: int
    expected_answer: CanonicalExpression
    truth_kind: TruthKind
    oracle_check: str
    derived_hash: str

    def to_dict(self, *, include_state: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "probe_id": self.probe_id,
            "pair_id": self.pair_id,
            "slice": self.slice_name.value,
            "mechanism": self.mechanism,
            "source_task_id": self.source_task_id,
            "source_state_hash": self.source_state_hash,
            "transformation_type": self.transformation_type,
            "transformation_seed": self.transformation_seed,
            "variant": self.variant.value,
            "question": self.question,
            "options": [item.to_dict() for item in self.options],
            "expected_index": self.expected_index,
            "expected_answer": self.expected_answer.to_dict(),
            "truth_kind": self.truth_kind.value,
            "oracle_check": self.oracle_check,
            "derived_hash": self.derived_hash,
        }
        if include_state:
            payload["state"] = self.state.to_dict()
        return payload


def _expr(
    op: str,
    *args: CanonicalExpression,
    value: str | int | float | bool | None = None,
    sort: str = "Unknown",
    attributes: tuple[tuple[str, str], ...] = (),
) -> CanonicalExpression:
    return CanonicalExpression(op, tuple(args), value, sort, attributes)


def _integer(value: int) -> CanonicalExpression:
    return _expr("integer", value=value, sort="Integer")


def _real(value: int | float) -> CanonicalExpression:
    return _expr("real", value=value, sort="Real")


def _symbol(value: str, *, sort: str = "Unknown") -> CanonicalExpression:
    return _expr("symbol", value=value, sort=sort)


def _as_int(expression: CanonicalExpression) -> int:
    if not isinstance(expression.value, int) or isinstance(expression.value, bool):
        raise ValueError(f"expected integer literal, received {expression.to_dict()}")
    return expression.value


def _as_float(expression: CanonicalExpression) -> float:
    if not isinstance(expression.value, (int, float)) or isinstance(expression.value, bool):
        raise ValueError(f"expected numeric literal, received {expression.to_dict()}")
    return float(expression.value)


def _short_answer(expression: CanonicalExpression) -> str:
    """Candidate-neutral, exact response spelling for the semantic-answer protocol."""

    if expression.op in {"integer", "real", "boolean", "symbol"}:
        return f"{expression.op}:{json.dumps(expression.value, ensure_ascii=False)}"
    return canonical_json(expression)


def _base_state(source: CanonicalState, goal: CanonicalExpression) -> CanonicalState:
    """Remove every oracle/action label while retaining the source's mathematical context."""

    visible = project_state_for_observation(source, ObservationKind.NEXT_ACTION)
    return replace(
        visible,
        state_id="state:fitness-v2:neutral",
        established_facts=(),
        propositions=(),
        goal=goal,
        execution_metadata=(),
    )


def _single_arg(action: CanonicalAction) -> CanonicalExpression:
    if len(action.arguments) != 1:
        raise ValueError("fitness-v2 source action must have exactly one result argument")
    return action.arguments[0]


def _counterfactual_spec(
    task: ArenaTask,
) -> tuple[CanonicalState, CanonicalExpression, CanonicalState, CanonicalExpression, str, str]:
    """Return independently replayable original/counterfactual state-answer pairs."""

    source = task.trajectory.initial_state
    goal = source.goal
    domain = task.dimensions.domain
    original_answer = _single_arg(source.legal_actions[0])

    if domain == "arithmetic":
        a, b = goal.args
        counter_goal = replace(goal, op="sub")
        counter_answer = _integer(_as_int(a) - _as_int(b))
        question = "Evaluate the displayed arithmetic goal exactly."
        transform = "replace_addition_with_subtraction"
    elif domain == "algebra":
        lhs, rhs = goal.args
        variable, offset = lhs.args
        counter_lhs = replace(lhs, op="sub")
        counter_goal = replace(goal, args=(counter_lhs, rhs))
        counter_answer = _expr(
            "eq",
            variable,
            _real(_as_float(rhs) + _as_float(offset)),
            sort="Bool",
        )
        if isinstance(rhs.value, int) and isinstance(offset.value, int):
            counter_answer = replace(
                counter_answer, args=(variable, _real(rhs.value + offset.value))
            )
        question = "Solve the displayed equality for its bound variable."
        transform = "replace_addition_with_subtraction"
    elif domain == "logic":
        implication, premise = goal.args
        antecedent, consequent = implication.args
        counter_implication = replace(implication, args=(consequent, antecedent))
        counter_goal = replace(goal, args=(counter_implication, consequent))
        counter_answer = antecedent
        question = "Apply the displayed implication to its matching premise."
        transform = "transpose_implication_roles"
    elif domain == "binding":
        variable, predicate = goal.args
        counter_goal = replace(goal, op="exists")
        original_answer = _single_arg(source.legal_actions[0])
        answer_variable, answer_predicate = original_answer.args
        counter_answer = _expr("exists", answer_variable, answer_predicate, sort="Proposition")
        question = "Select the alpha-renamed statement with the same quantifier."
        transform = "replace_universal_with_existential_binder"
    elif domain == "sets":
        element, finite_set = goal.args
        values = [_as_int(item) for item in finite_set.args]
        absent = max(values) + 1
        counter_goal = replace(goal, args=(_integer(absent), finite_set))
        counter_answer = _expr("boolean", value=False, sort="Bool")
        question = "Decide whether the displayed element belongs to the displayed finite set."
        transform = "replace_member_with_absent_element"
    elif domain == "probability":
        event_a, event_b = goal.args
        counter_goal = replace(goal, args=(event_b, event_a))
        numerator = _expr(
            "probability",
            _expr("intersection", event_b, event_a, sort="Event"),
            sort="Probability",
        )
        counter_answer = _expr(
            "ratio",
            numerator,
            _expr("probability", event_a, sort="Probability"),
            sort="Probability",
        )
        question = "Expand the displayed conditional probability with the correct denominator."
        transform = "transpose_conditional_probability_roles"
    elif domain == "statistics":
        counter_goal = replace(goal, op="sample_max")
        counter_answer = max(goal.args[0].args, key=_as_int)
        question = "Evaluate the statistic named by the displayed goal."
        transform = "replace_sample_mean_with_sample_maximum"
    elif domain == "calculus":
        power, variable = goal.args
        base, exponent = power.args
        exponent_value = _as_int(exponent) + 1
        counter_power = replace(power, args=(base, _integer(exponent_value)))
        counter_goal = replace(goal, args=(counter_power, variable))
        counter_answer = _expr(
            "mul",
            _real(exponent_value),
            _expr("power", variable, _integer(exponent_value - 1), sort="Real"),
            sort="Real",
        )
        question = "Differentiate the displayed power with respect to its displayed variable."
        transform = "increment_power_exponent"
    elif domain == "linear_algebra":
        vector = goal.args[0]
        extra = _integer(max(_as_int(item) for item in vector.args) + 1)
        counter_vector = replace(vector, args=(*vector.args, extra), sort="Vector[3]")
        counter_goal = replace(goal, args=(counter_vector,))
        counter_answer = _integer(3)
        question = "Return the dimension of the displayed vector."
        transform = "append_vector_coordinate"
    elif domain == "physical_dimensions":
        counter_goal = replace(goal, op="quantity_mul")
        counter_answer = _symbol("length*time", sort="PhysicalDimension")
        question = "Infer the physical dimension of the displayed quantity operation."
        transform = "replace_quantity_division_with_multiplication"
    elif domain == "optimization":
        variable, objective = goal.args
        subtraction, exponent = objective.args
        inner_variable, center = subtraction.args
        next_center = _real(_as_float(center) + 1)
        if isinstance(center.value, int):
            next_center = _real(center.value + 1)
        counter_objective = replace(
            objective,
            args=(replace(subtraction, args=(inner_variable, next_center)), exponent),
        )
        counter_goal = replace(goal, args=(variable, counter_objective))
        counter_answer = next_center
        question = "Find the minimizer of the displayed convex quadratic."
        transform = "shift_quadratic_center_by_one"
    elif domain == "partial_operations":
        if goal.op == "condition":
            raise ValueError("conditional-event definedness has no deterministic negative sibling")
        args = list(goal.args)
        if goal.op == "div":
            args[1] = _integer(0)
        elif goal.op in {"sqrt", "log"}:
            args[0] = _real(-1 if goal.op == "sqrt" else 0)
        elif goal.op == "inverse":
            args[0] = _integer(0)
        elif goal.op == "index":
            args[1] = _integer(len(goal.args[0].args))
        else:
            raise ValueError(f"unsupported partial operator {goal.op}")
        counter_goal = replace(goal, args=tuple(args))
        counter_answer = _symbol("undefined", sort=original_answer.sort)
        question = "Evaluate the displayed partial operation, or select undefined."
        transform = "replace_defined_argument_with_undefined_boundary"
    elif domain == "reasoning_evidence":
        conclusion = original_answer
        counter_answer = _expr("not", conclusion, sort="Proposition")
        counter_goal = goal
        question = "Select the conclusion licensed by the displayed evidence status."
        transform = "replace_verified_evidence_status_with_refuted"
    else:
        raise ValueError(f"no fitness-v2 counterfactual for domain {domain}")

    original_state = _base_state(source, goal)
    counter_state = _base_state(source, counter_goal)
    if domain == "logic":
        counter_state = replace(counter_state, assumptions=counter_goal.args)
        original_state = replace(original_state, assumptions=goal.args)
    elif domain == "partial_operations":
        obligation = Obligation(
            "obligation:fitness-v2:defined",
            _expr("defined", counter_goal, sort="Proposition"),
            "OPEN",
            "fitness-v2-domain-oracle",
        )
        counter_state = replace(counter_state, obligations=(obligation,))
    elif domain == "reasoning_evidence":
        counter_state = replace(
            counter_state,
            evidence_dependencies=tuple(
                replace(item, status="REFUTED") for item in counter_state.evidence_dependencies
            ),
        )
        original_answer = _symbol("verified", sort="EvidenceStatus")
        counter_answer = _symbol("refuted", sort="EvidenceStatus")

    if original_answer.content_hash == counter_answer.content_hash:
        raise ValueError("counterfactual answers must differ")
    return original_state, original_answer, counter_state, counter_answer, question, transform


def _oracle_answer(domain: str, state: CanonicalState) -> CanonicalExpression | None:
    """Independent bounded oracle for V2 probe mechanisms; ``None`` means information destroyed."""

    goal = state.goal
    if goal.op == "masked_relation":
        return None
    if domain == "arithmetic":
        left, right = (_as_int(item) for item in goal.args)
        return _integer(left + right if goal.op == "add" else left - right)
    if domain == "algebra":
        lhs, rhs = goal.args
        _variable, offset = lhs.args
        answer = (
            _as_float(rhs) - _as_float(offset)
            if lhs.op == "add"
            else _as_float(rhs) + _as_float(offset)
        )
        if isinstance(rhs.value, int) and isinstance(offset.value, int):
            answer = int(answer)
        return _expr("eq", lhs.args[0], _real(answer), sort="Bool")
    if domain == "logic":
        implication, premise = goal.args
        antecedent, consequent = implication.args
        return consequent if premise.content_hash == antecedent.content_hash else None
    if domain == "binding":
        _variable, predicate = goal.args
        renamed = CanonicalExpression.from_dict(predicate.to_dict())
        new_variable = _expr("var", value="y_oracle", sort="Element")
        renamed = replace(renamed, args=(new_variable,))
        return _expr(goal.op, new_variable, renamed, sort="Proposition")
    if domain == "sets":
        element, finite_set = goal.args
        present = any(element.content_hash == item.content_hash for item in finite_set.args)
        return _expr("boolean", value=present, sort="Bool")
    if domain == "probability":
        event_a, event_b = goal.args
        numerator = _expr(
            "probability", _expr("intersection", event_a, event_b, sort="Event"), sort="Probability"
        )
        return _expr(
            "ratio",
            numerator,
            _expr("probability", event_b, sort="Probability"),
            sort="Probability",
        )
    if domain == "statistics":
        values = [_as_int(item) for item in goal.args[0].args]
        if goal.op == "sample_mean":
            return _integer(sum(values) // len(values))
        return _integer(max(values))
    if domain == "calculus":
        power, variable = goal.args
        exponent = _as_int(power.args[1])
        if exponent == 2:
            return _expr("mul", _real(2), variable, sort="Real")
        return _expr(
            "mul",
            _real(exponent),
            _expr("power", variable, _integer(exponent - 1), sort="Real"),
            sort="Real",
        )
    if domain == "linear_algebra":
        return _integer(len(goal.args[0].args))
    if domain == "physical_dimensions":
        return _symbol(
            "length/time" if goal.op == "quantity_divide" else "length*time",
            sort="PhysicalDimension",
        )
    if domain == "optimization":
        return goal.args[1].args[0].args[1]
    if domain == "partial_operations":
        if goal.op == "div":
            return (
                _symbol("undefined", sort="Integer")
                if _as_int(goal.args[1]) == 0
                else _integer(_as_int(goal.args[0]) // _as_int(goal.args[1]))
            )
        if goal.op == "sqrt":
            value = _as_float(goal.args[0])
            return (
                _symbol("undefined", sort="Integer")
                if value < 0
                else _integer(math.isqrt(int(value)))
            )
        if goal.op == "log":
            return (
                _symbol("undefined", sort="Integer")
                if _as_float(goal.args[0]) <= 0
                else _integer(0)
            )
        if goal.op == "inverse":
            return (
                _symbol("undefined", sort="Integer") if _as_int(goal.args[0]) == 0 else _integer(1)
            )
        if goal.op == "index":
            vector, index = goal.args
            return (
                _symbol("undefined", sort="Integer")
                if _as_int(index) >= len(vector.args)
                else vector.args[_as_int(index)]
            )
    if domain == "reasoning_evidence":
        statuses = {item.status for item in state.evidence_dependencies}
        return _symbol("verified" if statuses == {"VERIFIED"} else "refuted", sort="EvidenceStatus")
    return None


def _alpha_equivalent(left: CanonicalExpression, right: CanonicalExpression) -> bool:
    if left.op != right.op or len(left.args) != 2 or len(right.args) != 2:
        return left.content_hash == right.content_hash
    if left.op not in {"forall", "exists"}:
        return left.content_hash == right.content_hash
    left_var, left_body = left.args
    right_var, right_body = right.args
    normalized_left = replace(left_body, args=(replace(left_var, value="_BOUND"),))
    normalized_right = replace(right_body, args=(replace(right_var, value="_BOUND"),))
    return normalized_left.content_hash == normalized_right.content_hash


def _answer_matches(observed: CanonicalExpression, expected: CanonicalExpression) -> bool:
    return _alpha_equivalent(observed, expected)


def _masked_state(state: CanonicalState) -> CanonicalState:
    # Do not retain variable-bearing children after destroying a binder relation: without
    # ``forall``/``exists`` those children would become genuinely unbound rather than neutral.
    masked = _expr("masked_relation", value="relation_hidden", sort=state.goal.sort)
    return replace(
        state,
        goal=masked,
        assumptions=(),
        obligations=(),
        evidence_dependencies=(),
    )


def _make_probe(
    *,
    pair_id: str,
    slice_name: ProbeSlice,
    task: ArenaTask,
    mechanism: str,
    transform: str,
    variant: ProbeVariant,
    state: CanonicalState,
    question: str,
    options: tuple[CanonicalExpression, CanonicalExpression],
    expected_index: int,
    truth_kind: TruthKind,
    oracle_check: str,
) -> SemanticProbe:
    seed = int(stable_hash({"seed": EXPERIMENT_SEED, "pair": pair_id})[:16], 16)
    identity = {
        "instrument_version": INSTRUMENT_VERSION,
        "pair_id": pair_id,
        "slice": slice_name.value,
        "source_task_id": task.task_id,
        "source_state_hash": task.trajectory.initial_state.artifact_hash,
        "transformation_type": transform,
        "transformation_seed": seed,
        "variant": variant.value,
        "state_hash": state.artifact_hash,
        "question": question,
        "option_hashes": [item.content_hash for item in options],
        "expected_index": expected_index,
        "truth_kind": truth_kind.value,
        "oracle_check": oracle_check,
    }
    derived_hash = stable_hash(identity)
    return SemanticProbe(
        f"probe:{derived_hash[:20]}",
        pair_id,
        slice_name,
        mechanism,
        task.task_id,
        task.trajectory.initial_state.artifact_hash,
        transform,
        seed,
        variant,
        state,
        question,
        options,
        expected_index,
        options[expected_index],
        truth_kind,
        oracle_check,
        derived_hash,
    )


def derive_probe_family(task: ArenaTask, slice_name: ProbeSlice) -> tuple[SemanticProbe, ...]:
    """Derive positive, relation-destroyed, and position-swapped siblings."""

    if task.trajectory.quality != GoldStatus.GOLD:
        raise ValueError("fitness-v2 probes require a Gold source task")
    original_state, original_answer, counter_state, counter_answer, question, transform = (
        _counterfactual_spec(task)
    )
    pair_id = (
        "pair:"
        + stable_hash(
            {"instrument": INSTRUMENT_VERSION, "source": task.task_id, "slice": slice_name.value}
        )[:20]
    )
    options = (original_answer, counter_answer)
    masked = _masked_state(original_state)
    oracle_name = f"fitness-v2-domain-oracle:{task.dimensions.domain}:{transform}"
    return (
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.ORIGINAL,
            state=original_state,
            question=question,
            options=options,
            expected_index=0,
            truth_kind=TruthKind.MATHEMATICAL,
            oracle_check=oracle_name,
        ),
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.COUNTERFACTUAL,
            state=counter_state,
            question=question,
            options=options,
            expected_index=1,
            truth_kind=TruthKind.MATHEMATICAL,
            oracle_check=oracle_name,
        ),
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.DESTROYED_ORIGINAL,
            state=masked,
            question=question,
            options=options,
            expected_index=0,
            truth_kind=TruthKind.NEGATIVE_CONTROL_TARGET,
            oracle_check="information-destroyed; balanced source target, not mathematical truth",
        ),
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.DESTROYED_COUNTERFACTUAL,
            state=masked,
            question=question,
            options=options,
            expected_index=1,
            truth_kind=TruthKind.NEGATIVE_CONTROL_TARGET,
            oracle_check="information-destroyed; balanced source target, not mathematical truth",
        ),
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.SWAPPED_ORIGINAL,
            state=original_state,
            question=question,
            options=(counter_answer, original_answer),
            expected_index=1,
            truth_kind=TruthKind.MATHEMATICAL,
            oracle_check=oracle_name,
        ),
        _make_probe(
            pair_id=pair_id,
            slice_name=slice_name,
            task=task,
            mechanism=task.dimensions.domain,
            transform=transform,
            variant=ProbeVariant.SWAPPED_COUNTERFACTUAL,
            state=counter_state,
            question=question,
            options=(counter_answer, original_answer),
            expected_index=0,
            truth_kind=TruthKind.MATHEMATICAL,
            oracle_check=oracle_name,
        ),
    )


def validate_probe_family(probes: tuple[SemanticProbe, ...]) -> dict[str, Any]:
    """Fail closed on structure, oracle inversion, negative identity, and label balance."""

    if len(probes) != 6 or len({item.pair_id for item in probes}) != 1:
        raise ValueError("a fitness-v2 family must contain exactly six siblings")
    by_variant = {item.variant: item for item in probes}
    verifier = NativeVerifier()
    for probe in probes:
        result = verifier.verify_state(probe.state)
        if not result.accepted:
            raise ValueError(f"native state rejection for {probe.probe_id}: {result.issues}")
        if probe.state.legal_actions or probe.state.plausible_invalid_actions:
            raise ValueError("model-visible V2 state leaks action membership")
        if probe.state.state_id != "state:fitness-v2:neutral":
            raise ValueError("variant-specific display identity could leak the target")

    for variant in (ProbeVariant.ORIGINAL, ProbeVariant.COUNTERFACTUAL):
        probe = by_variant[variant]
        observed = _oracle_answer(probe.mechanism, probe.state)
        if observed is None or not _answer_matches(observed, probe.expected_answer):
            raise ValueError(f"independent oracle disagreement for {probe.probe_id}")
        matches = sum(_answer_matches(observed, option) for option in probe.options)
        if matches != 1:
            raise ValueError("positive probe must have exactly one correct semantic option")

    negative_a = by_variant[ProbeVariant.DESTROYED_ORIGINAL]
    negative_b = by_variant[ProbeVariant.DESTROYED_COUNTERFACTUAL]
    if negative_a.state.artifact_hash != negative_b.state.artifact_hash:
        raise ValueError("negative siblings must be information-identical")
    if _oracle_answer(negative_a.mechanism, negative_a.state) is not None:
        raise ValueError("destroyed relation unexpectedly retains an oracle answer")
    if negative_a.expected_index == negative_b.expected_index:
        raise ValueError("negative targets must be balanced and mutually incompatible")

    for base_variant, swapped_variant in (
        (ProbeVariant.ORIGINAL, ProbeVariant.SWAPPED_ORIGINAL),
        (ProbeVariant.COUNTERFACTUAL, ProbeVariant.SWAPPED_COUNTERFACTUAL),
    ):
        base = by_variant[base_variant]
        swapped = by_variant[swapped_variant]
        if base.state.artifact_hash != swapped.state.artifact_hash:
            raise ValueError("position swap changed mathematical state")
        if base.options != tuple(reversed(swapped.options)):
            raise ValueError("position swap changed semantic option set")
        if base.expected_answer.content_hash != swapped.expected_answer.content_hash:
            raise ValueError("position swap changed semantic truth")

    return {
        "pair_id": probes[0].pair_id,
        "source_task_id": probes[0].source_task_id,
        "mechanism": probes[0].mechanism,
        "canonical_states_valid": True,
        "scope_types_definedness_valid": True,
        "oracle_inversion_valid": True,
        "unique_positive_answer": True,
        "negative_information_identity": True,
        "position_swap_valid": True,
        "derived_hashes_unique": len({item.derived_hash for item in probes}) == 6,
    }


def _eligible_by_partition() -> dict[str, list[ArenaTask]]:
    world = build_world_v0()
    manifest = frozen_task_split(world)
    task_by_id = {task.task_id: task for task in world.tasks}
    result: dict[str, list[ArenaTask]] = {}
    for partition, task_ids in manifest["partitions"].items():
        eligible = []
        for task_id in task_ids:
            task = task_by_id[task_id]
            try:
                _counterfactual_spec(task)
            except ValueError:
                continue
            eligible.append(task)
        result[partition] = eligible
    return result


def build_probe_manifest() -> dict[str, Any]:
    """Construct a frozen, source-disjoint V2 split without using model outcomes."""

    eligible = _eligible_by_partition()
    allocations = {
        ProbeSlice.PROTOCOL_DEV: ("DEV", 1),
        ProbeSlice.MODEL_QUALIFICATION: ("DEV", 2),
        ProbeSlice.CALIBRATION_DEV: ("DEV", 2),
        ProbeSlice.TIER2A_SCOUT: ("SCOUT", 2),
        ProbeSlice.TIER2B_PROMOTION: ("PROMOTION", 4),
        ProbeSlice.OOD: ("OOD", 3),
    }
    used: set[str] = set()
    all_probes: list[SemanticProbe] = []
    validations: list[dict[str, Any]] = []
    slice_sources: dict[str, list[str]] = {}
    for slice_name, (partition, per_mechanism) in allocations.items():
        groups: dict[str, list[ArenaTask]] = defaultdict(list)
        for task in eligible[partition]:
            if task.task_id not in used:
                groups[task.dimensions.domain].append(task)
        selected: list[ArenaTask] = []
        for mechanism in sorted(groups):
            selected.extend(
                sorted(groups[mechanism], key=lambda item: item.task_id)[:per_mechanism]
            )
        if not selected:
            raise ValueError(f"no eligible probes for {slice_name}")
        slice_sources[slice_name.value] = [item.task_id for item in selected]
        used.update(item.task_id for item in selected)
        for task in selected:
            family = derive_probe_family(task, slice_name)
            validations.append(validate_probe_family(family))
            all_probes.extend(family)

    payload = {
        "schema_version": "arena-fitness-v2-probe-manifest-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "seed": EXPERIMENT_SEED,
        "source_world": "arena-world-v0",
        "source_split_manifest_hash": frozen_task_split(build_world_v0())["manifest_hash"],
        "allocation_rule": "source-disjoint deterministic first task IDs per mechanism within frozen v1 partitions",
        "slice_sources": slice_sources,
        "slice_source_hashes": {key: stable_hash(value) for key, value in slice_sources.items()},
        "probes": [item.to_dict() for item in all_probes],
        "validations": validations,
        "thresholds": THRESHOLDS.to_dict(),
    }
    payload["manifest_hash"] = stable_hash(
        {key: value for key, value in payload.items() if key != "manifest_hash"}
    )
    return payload


def probes_for_slice(slice_name: ProbeSlice) -> tuple[SemanticProbe, ...]:
    manifest = build_probe_manifest()
    return tuple(
        _probe_from_dict(raw) for raw in manifest["probes"] if raw["slice"] == slice_name.value
    )


def _probe_from_dict(raw: dict[str, Any]) -> SemanticProbe:
    return SemanticProbe(
        probe_id=str(raw["probe_id"]),
        pair_id=str(raw["pair_id"]),
        slice_name=ProbeSlice(raw["slice"]),
        mechanism=str(raw["mechanism"]),
        source_task_id=str(raw["source_task_id"]),
        source_state_hash=str(raw["source_state_hash"]),
        transformation_type=str(raw["transformation_type"]),
        transformation_seed=int(raw["transformation_seed"]),
        variant=ProbeVariant(raw["variant"]),
        state=CanonicalState.from_dict(raw["state"]),
        question=str(raw["question"]),
        options=tuple(CanonicalExpression.from_dict(item) for item in raw["options"]),  # type: ignore[arg-type]
        expected_index=int(raw["expected_index"]),
        expected_answer=CanonicalExpression.from_dict(raw["expected_answer"]),
        truth_kind=TruthKind(raw["truth_kind"]),
        oracle_check=str(raw["oracle_check"]),
        derived_hash=str(raw["derived_hash"]),
    )


def _action_keys(probe: SemanticProbe) -> tuple[str, str]:
    return tuple(
        "K_"
        + stable_hash(
            {"instrument": INSTRUMENT_VERSION, "pair": probe.pair_id, "answer": item.content_hash}
        )[:10]
        for item in probe.options
    )  # type: ignore[return-value]


def _labels(protocol: ResponseProtocol, probe: SemanticProbe) -> tuple[str, str]:
    if protocol == ResponseProtocol.JSON_AB:
        return ("A", "B")
    if protocol == ResponseProtocol.JSON_PQ:
        return ("P", "Q")
    if protocol == ResponseProtocol.ACTION_KEY:
        return _action_keys(probe)
    return tuple(_short_answer(item) for item in probe.options)  # type: ignore[return-value]


def build_probe_prompt(
    genome: LanguageGenome, probe: SemanticProbe, protocol: ResponseProtocol
) -> str:
    """Common candidate-neutral envelope; only lossless state/option encodings vary."""

    language = GenomePhenotypeLanguage(genome)
    labels = _labels(protocol, probe)
    rendered_options = []
    for index, option in enumerate(probe.options):
        action = CanonicalAction(
            f"action:fitness-v2:{index}",
            "propose_result",
            ("goal",),
            (option,),
            "",
            expected_usefulness=0.0,
        )
        rendered_options.append(f"{labels[index]}: {language.render_action_choice(action)}")
    if protocol == ResponseProtocol.JSON_AB:
        response = 'Return exactly {"choice":"A"} or {"choice":"B"}; no explanation.'
    elif protocol == ResponseProtocol.JSON_PQ:
        response = 'Return exactly {"choice":"P"} or {"choice":"Q"}; no explanation.'
    elif protocol == ResponseProtocol.ACTION_KEY:
        response = f"Return exactly one action key: {labels[0]} or {labels[1]}; no explanation."
    else:
        response = (
            f"Return exactly one canonical answer: {labels[0]} or {labels[1]}; no explanation."
        )
    return (
        f"{response}\n"
        "Read the mathematical state; do not choose by option position.\n"
        f"QUESTION: {probe.question}\n"
        "SYNTAX GUIDE:\n"
        f"{language.acquisition_guide()}\n"
        "STATE:\n"
        f"{language.render(probe.state)}\n"
        "OPTIONS:\n" + "\n".join(rendered_options) + "\nANSWER:"
    )


def parse_response(
    output: str, protocol: ResponseProtocol, probe: SemanticProbe
) -> tuple[int | None, str | None]:
    labels = _labels(protocol, probe)
    stripped = output.strip()
    if protocol in {ResponseProtocol.JSON_AB, ResponseProtocol.JSON_PQ}:
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return None, None
        if not isinstance(value, dict) or set(value) != {"choice"}:
            return None, None
        selected = value["choice"]
    else:
        selected = stripped
    if selected not in labels:
        return None, None
    index = labels.index(selected)
    return index, probe.options[index].content_hash


def build_q0_prompt(protocol: ResponseProtocol, target_index: int, case_index: int) -> str:
    labels = {
        ResponseProtocol.JSON_AB: ("A", "B"),
        ResponseProtocol.JSON_PQ: ("P", "Q"),
        ResponseProtocol.ACTION_KEY: ("K_LEFT", "K_RIGHT"),
        ResponseProtocol.CANONICAL_ANSWER: ("integer:11", "integer:29"),
    }[protocol]
    target = labels[target_index]
    if protocol in {ResponseProtocol.JSON_AB, ResponseProtocol.JSON_PQ}:
        required = json.dumps({"choice": target}, separators=(",", ":"))
    else:
        required = target
    return (
        "This is a response-format check, not a mathematics test. "
        f"Case {case_index}: copy the target exactly and output nothing else.\n"
        f"TARGET: {required}\nANSWER:"
    )


def parse_q0(output: str, protocol: ResponseProtocol) -> str | None:
    stripped = output.strip()
    if protocol in {ResponseProtocol.JSON_AB, ResponseProtocol.JSON_PQ}:
        allowed = ("A", "B") if protocol == ResponseProtocol.JSON_AB else ("P", "Q")
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if (
            not isinstance(value, dict)
            or set(value) != {"choice"}
            or value["choice"] not in allowed
        ):
            return None
        return str(value["choice"])
    allowed = (
        ("K_LEFT", "K_RIGHT")
        if protocol == ResponseProtocol.ACTION_KEY
        else ("integer:11", "integer:29")
    )
    return stripped if stripped in allowed else None


def summarize_probe_rows(rows: list[dict[str, Any]], *, q0_valid_rate: float) -> dict[str, Any]:
    base_positive = [
        row
        for row in rows
        if row["variant"] in {ProbeVariant.ORIGINAL.value, ProbeVariant.COUNTERFACTUAL.value}
    ]
    negative = [row for row in rows if row["truth_kind"] == TruthKind.NEGATIVE_CONTROL_TARGET.value]
    swapped = [
        row
        for row in rows
        if row["variant"]
        in {ProbeVariant.SWAPPED_ORIGINAL.value, ProbeVariant.SWAPPED_COUNTERFACTUAL.value}
    ]

    def accuracy(values: list[dict[str, Any]]) -> float:
        return sum(bool(item["correct"]) for item in values) / len(values) if values else 0.0

    by_pair: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_pair[row["pair_id"]][row["variant"]] = row
    flip_successes = 0
    choice_flips = 0
    position_matches = 0
    position_total = 0
    pair_total = 0
    for variants in by_pair.values():
        original = variants.get(ProbeVariant.ORIGINAL.value)
        counter = variants.get(ProbeVariant.COUNTERFACTUAL.value)
        if original and counter:
            pair_total += 1
            different = original["selected_semantic_hash"] != counter["selected_semantic_hash"]
            choice_flips += bool(
                different
                and original["selected_semantic_hash"] is not None
                and counter["selected_semantic_hash"] is not None
            )
            flip_successes += bool(original["correct"] and counter["correct"] and different)
        for base_name, swap_name in (
            (ProbeVariant.ORIGINAL.value, ProbeVariant.SWAPPED_ORIGINAL.value),
            (ProbeVariant.COUNTERFACTUAL.value, ProbeVariant.SWAPPED_COUNTERFACTUAL.value),
        ):
            base = variants.get(base_name)
            swap = variants.get(swap_name)
            if base and swap:
                position_total += 1
                position_matches += bool(
                    base["selected_semantic_hash"] is not None
                    and base["selected_semantic_hash"] == swap["selected_semantic_hash"]
                )
    valid = [row for row in rows if row["parsed_index"] is not None]
    position_counts = Counter(row["parsed_index"] for row in valid)
    max_position = max(position_counts.values(), default=0) / len(valid) if valid else 1.0
    q1 = accuracy(base_positive)
    q2 = accuracy(negative)
    constant_baseline = (
        max(Counter(row["expected_index"] for row in base_positive).values(), default=0)
        / len(base_positive)
        if base_positive
        else 1.0
    )
    flip = flip_successes / pair_total if pair_total else 0.0
    summary = {
        "q0_valid_rate": q0_valid_rate,
        "q1_positive_accuracy": q1,
        "q2_destroyed_target_accuracy": q2,
        "positive_negative_gap": q1 - q2,
        "best_constant_position_baseline": constant_baseline,
        "margin_over_constant": q1 - constant_baseline,
        "semantic_flip_consistency": flip,
        "choice_flip_rate": choice_flips / pair_total if pair_total else 0.0,
        "position_invariance": position_matches / position_total if position_total else 0.0,
        "position_preference": {
            str(key): value / len(valid) for key, value in sorted(position_counts.items())
        }
        if valid
        else {},
        "max_position_preference": max_position,
        "malformed_rate": 1 - len(valid) / len(rows) if rows else 1.0,
        "positive_examples": len(base_positive),
        "negative_examples": len(negative),
        "swapped_examples": len(swapped),
        "counterfactual_pairs": pair_total,
    }
    checks = {
        "q0_protocol": q0_valid_rate >= THRESHOLDS.q0_valid_rate,
        "q1_reading": q1 >= THRESHOLDS.q1_accuracy,
        "beats_constant": q1 - constant_baseline >= THRESHOLDS.margin_over_constant,
        "semantic_sensitivity": flip >= THRESHOLDS.semantic_flip_consistency,
        "negative_control_gap": q1 - q2 >= THRESHOLDS.positive_negative_gap,
        "position_balance": max_position <= THRESHOLDS.max_position_preference,
    }
    summary["threshold_checks"] = checks
    summary["qualified"] = all(checks.values())
    return summary


def _call_ollama(
    model: str, prompt: str, *, base_url: str = "http://127.0.0.1:11434"
) -> dict[str, Any]:
    options = {
        key: value for key, value in RUNTIME_CONFIG.items() if key not in {"engine", "think"}
    }
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": RUNTIME_CONFIG["think"],
            "options": options,
        }
    ).encode()
    request = Request(
        f"{base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=300) as response:  # noqa: S310 - fixed local runtime
        raw = json.loads(response.read().decode())
    return {
        "response": str(raw.get("response", "")),
        "done": bool(raw.get("done", False)),
        "done_reason": raw.get("done_reason"),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "total_duration_ns": int(raw.get("total_duration", 0)),
    }


def _cached_call(
    root: Path, identity: dict[str, Any], model: str, prompt: str
) -> tuple[dict[str, Any], bool]:
    cache_key = stable_hash(identity)
    path = root / "artifacts" / "cache" / "fitness_v2" / f"{cache_key}.json"
    if path.exists():
        return json.loads(path.read_text()), True
    started = time.monotonic()
    try:
        raw = _call_ollama(model, prompt)
        raw["error"] = None
    except Exception as error:
        raw = {
            "response": "",
            "done": False,
            "done_reason": None,
            "prompt_eval_count": 0,
            "eval_count": 0,
            "total_duration_ns": 0,
            "error": repr(error),
        }
    raw["wall_seconds"] = time.monotonic() - started
    raw["cache_identity"] = identity
    ArtifactStore(root / "artifacts").write_json(f"cache/fitness_v2/{cache_key}.json", raw)
    return raw, False


def run_model_qualification(
    root: Path,
    *,
    model: str,
    model_digest: str,
    protocol: ResponseProtocol,
    slice_name: ProbeSlice = ProbeSlice.MODEL_QUALIFICATION,
    genome: LanguageGenome = L0_STRUCTURED_ENGLISH,
) -> dict[str, Any]:
    q0_rows = []
    for index in range(20):
        target_index = index % 2
        prompt = build_q0_prompt(protocol, target_index, index)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "kind": "Q0",
            "model_digest": model_digest,
            "runtime_config_hash": RUNTIME_CONFIG_HASH,
            "protocol": protocol.value,
            "case": index,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, model, prompt)
        parsed = parse_q0(raw["response"], protocol)
        expected = {
            ResponseProtocol.JSON_AB: ("A", "B"),
            ResponseProtocol.JSON_PQ: ("P", "Q"),
            ResponseProtocol.ACTION_KEY: ("K_LEFT", "K_RIGHT"),
            ResponseProtocol.CANONICAL_ANSWER: ("integer:11", "integer:29"),
        }[protocol][target_index]
        q0_rows.append(
            {
                **identity,
                "raw_output": raw["response"],
                "parsed": parsed,
                "expected": expected,
                "valid": parsed is not None,
                "correct": parsed == expected,
                "cache_hit": hit,
                "error": raw.get("error"),
            }
        )
    q0_valid = sum(row["valid"] and row["correct"] for row in q0_rows) / len(q0_rows)

    probe_rows = []
    for probe in probes_for_slice(slice_name):
        prompt = build_probe_prompt(genome, probe, protocol)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "instrument": INSTRUMENT_VERSION,
            "kind": "Q1_Q2",
            "model_digest": model_digest,
            "runtime_config_hash": RUNTIME_CONFIG_HASH,
            "protocol": protocol.value,
            "candidate_id": genome.candidate_id,
            "candidate_genome_hash": genome.genome_hash,
            "probe_id": probe.probe_id,
            "derived_hash": probe.derived_hash,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, model, prompt)
        parsed_index, semantic_hash = parse_response(raw["response"], protocol, probe)
        probe_rows.append(
            {
                **identity,
                "pair_id": probe.pair_id,
                "slice": slice_name.value,
                "mechanism": probe.mechanism,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind.value,
                "expected_index": probe.expected_index,
                "expected_answer_hash": probe.expected_answer.content_hash,
                "raw_output": raw["response"],
                "parsed_index": parsed_index,
                "selected_semantic_hash": semantic_hash,
                "correct": semantic_hash == probe.expected_answer.content_hash,
                "malformed": parsed_index is None,
                "cache_hit": hit,
                "error": raw.get("error"),
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "latency_seconds": raw.get("total_duration_ns", 0) / 1_000_000_000,
            }
        )
    summary = summarize_probe_rows(probe_rows, q0_valid_rate=q0_valid)
    return {
        "schema_version": "arena-fitness-v2-model-qualification-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "model": model,
        "model_digest": model_digest,
        "candidate_id": genome.candidate_id,
        "candidate_genome_hash": genome.genome_hash,
        "protocol": protocol.value,
        "slice": slice_name.value,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "thresholds": THRESHOLDS.to_dict(),
        "summary": summary,
        "q0_rows": q0_rows,
        "probe_rows": probe_rows,
        "model_calls": len(q0_rows) + len(probe_rows),
        "unique_model_observations": len({row["prompt_hash"] for row in q0_rows + probe_rows}),
        "raw_audit_sample": [
            {
                "probe_id": row.get("probe_id", row.get("case")),
                "variant": row.get("variant", "Q0"),
                "raw_output": row["raw_output"],
            }
            for row in (q0_rows[:4] + probe_rows[:12])
        ],
    }


def _candidate_genomes() -> dict[str, LanguageGenome]:
    result = dict(SEED_GENOME_BY_ID)
    result.update(
        {candidate.candidate_id: candidate.genome for candidate in materialize_population()}
    )
    return result


def evaluate_candidate_slice(
    root: Path,
    *,
    candidate_id: str,
    slice_name: ProbeSlice,
    model: str = str(QUALIFIED_MODEL["name"]),
    model_digest: str = str(QUALIFIED_MODEL["digest"]),
    protocol: ResponseProtocol = FROZEN_PROTOCOL,
) -> dict[str, Any]:
    """Evaluate one representation on one frozen V2 slice with task-level caching."""

    genome = _candidate_genomes()[candidate_id]
    rows: list[dict[str, Any]] = []
    for probe in probes_for_slice(slice_name):
        prompt = build_probe_prompt(genome, probe, protocol)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "instrument": INSTRUMENT_VERSION,
            "kind": "CANDIDATE_SLICE",
            "model_digest": model_digest,
            "runtime_config_hash": RUNTIME_CONFIG_HASH,
            "protocol": protocol.value,
            "candidate_id": genome.candidate_id,
            "candidate_genome_hash": genome.genome_hash,
            "slice": slice_name.value,
            "probe_id": probe.probe_id,
            "derived_hash": probe.derived_hash,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, model, prompt)
        parsed_index, semantic_hash = parse_response(raw["response"], protocol, probe)
        rows.append(
            {
                **identity,
                "pair_id": probe.pair_id,
                "source_task_id": probe.source_task_id,
                "source_state_hash": probe.source_state_hash,
                "mechanism": probe.mechanism,
                "transformation_type": probe.transformation_type,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind.value,
                "expected_index": probe.expected_index,
                "expected_answer_hash": probe.expected_answer.content_hash,
                "raw_output": raw["response"],
                "parsed_index": parsed_index,
                "selected_semantic_hash": semantic_hash,
                "correct": semantic_hash == probe.expected_answer.content_hash,
                "malformed": parsed_index is None,
                "cache_hit": hit,
                "error": raw.get("error"),
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "latency_seconds": raw.get("total_duration_ns", 0) / 1_000_000_000,
            }
        )
    summary = summarize_probe_rows(rows, q0_valid_rate=1.0)
    positive = [
        row
        for row in rows
        if row["variant"] in {ProbeVariant.ORIGINAL.value, ProbeVariant.COUNTERFACTUAL.value}
    ]
    summary.update(
        {
            "invalid_action_rate": sum(
                row["parsed_index"] is not None and not row["correct"] for row in positive
            )
            / len(positive),
            "verified_action_rate": sum(row["correct"] for row in positive) / len(positive),
            "valid_response_rate": sum(row["parsed_index"] is not None for row in rows) / len(rows),
            "mean_prompt_tokens": sum(row["prompt_tokens"] for row in rows) / len(rows),
            "mean_completion_tokens": sum(row["completion_tokens"] for row in rows) / len(rows),
            "mean_latency_seconds": sum(row["latency_seconds"] for row in rows) / len(rows),
        }
    )
    return {
        "candidate_id": candidate_id,
        "candidate_genome_hash": genome.genome_hash,
        "slice": slice_name.value,
        "model": model,
        "model_digest": model_digest,
        "protocol": protocol.value,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "summary": summary,
        "rows": rows,
        "calls": len(rows),
        "cache_hits": sum(row["cache_hit"] for row in rows),
    }


def _write_rows(store: ArtifactStore, relative: str, results: list[dict[str, Any]]) -> str:
    lines = [canonical_json(row) for result in results for row in result["rows"]]
    return str(store.write_text(relative, "\n".join(lines) + "\n").path)


def run_calibration_v2(root: Path) -> dict[str, Any]:
    """Run fresh V2 controls and apply the precommitted instrument/headroom gate."""

    controls = ("L0_STRUCTURED_ENGLISH", "L1_CURRENT_HML", "L2_SEXPR", "L3_JSON_AST")
    results = [
        evaluate_candidate_slice(
            root, candidate_id=candidate_id, slice_name=ProbeSlice.CALIBRATION_DEV
        )
        for candidate_id in controls
    ]
    summaries = {result["candidate_id"]: result["summary"] for result in results}
    qualified_controls = [
        candidate_id for candidate_id, summary in summaries.items() if summary["qualified"]
    ]
    accuracies = [float(summary["q1_positive_accuracy"]) for summary in summaries.values()]
    instrument_valid = bool(qualified_controls)
    if not instrument_valid:
        verdict = "FITNESS_V2_CALIBRATION_FLOOR"
    elif all(value >= 0.90 for value in accuracies):
        verdict = "FITNESS_V2_CALIBRATION_CEILING"
    elif max(accuracies) - min(accuracies) >= 0.15 and min(accuracies) <= 0.85:
        verdict = "FITNESS_V2_CALIBRATION_VALID_WITH_HEADROOM"
    else:
        verdict = "FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM"
    proceed = verdict == "FITNESS_V2_CALIBRATION_VALID_WITH_HEADROOM"
    result = {
        "schema_version": "arena-fitness-v2-calibration-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "model": QUALIFIED_MODEL,
        "protocol": FROZEN_PROTOCOL.value,
        "runtime": RUNTIME_CONFIG,
        "rules": CALIBRATION_RULE,
        "controls": controls,
        "summaries": summaries,
        "qualified_controls": qualified_controls,
        "instrument_valid": instrument_valid,
        "headroom_range": max(accuracies) - min(accuracies),
        "verdict": verdict,
        "tier2a_authorized": proceed,
        "calls": sum(result["calls"] for result in results),
        "raw_audit_sample": [
            {
                "candidate_id": result["candidate_id"],
                "probe_id": row["probe_id"],
                "variant": row["variant"],
                "raw_output": row["raw_output"],
            }
            for result in results
            for row in result["rows"][:8]
        ],
    }
    store = ArtifactStore(root / "artifacts")
    result["task_rows_path"] = _write_rows(
        store, "experiments/fitness_v2/calibration/task_rows.jsonl", results
    )
    store.write_json("experiments/fitness_v2/calibration/result.json", result)
    return result


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _paired_candidate_comparisons(
    results: list[dict[str, Any]], baseline_id: str = "L0_STRUCTURED_ENGLISH"
) -> dict[str, Any]:
    by_id = {result["candidate_id"]: result for result in results}
    baseline_rows = [
        row
        for row in by_id[baseline_id]["rows"]
        if row["variant"] in {ProbeVariant.ORIGINAL.value, ProbeVariant.COUNTERFACTUAL.value}
    ]
    baseline_by_probe = {row["probe_id"]: row for row in baseline_rows}
    comparisons = {}
    for candidate_id, result in sorted(by_id.items()):
        if candidate_id == baseline_id:
            continue
        candidate_rows = [
            row
            for row in result["rows"]
            if row["variant"] in {ProbeVariant.ORIGINAL.value, ProbeVariant.COUNTERFACTUAL.value}
        ]
        ordered = sorted(candidate_rows, key=lambda row: row["probe_id"])
        baseline = [baseline_by_probe[row["probe_id"]] for row in ordered]
        comparisons[candidate_id] = paired_comparison(
            [bool(row["correct"]) for row in ordered],
            [bool(row["correct"]) for row in baseline],
            [str(row["mechanism"]) for row in ordered],
            seed=EXPERIMENT_SEED,
        ).to_dict()
    return comparisons


def _tier2_signal(results: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = {result["candidate_id"]: result["summary"] for result in results}
    accuracies = {
        candidate_id: float(summary["q1_positive_accuracy"])
        for candidate_id, summary in summaries.items()
    }
    children = {item.candidate_id: item for item in materialize_population()}
    edges = []
    for child_id, child in children.items():
        if child_id not in accuracies or child.parent_id not in accuracies:
            continue
        delta = accuracies[child_id] - accuracies[child.parent_id]
        edges.append(
            {
                "parent_id": child.parent_id,
                "child_id": child_id,
                "changed_gene": child.mutation_family,
                "parent_accuracy": accuracies[child.parent_id],
                "child_accuracy": accuracies[child_id],
                "delta": delta,
                "large": abs(delta) >= float(TIER2A_SIGNAL_RULE["large_parent_child_delta"]),
            }
        )
    valid_response = all(
        float(summary["valid_response_rate"])
        >= float(TIER2A_SIGNAL_RULE["minimum_candidate_valid_response_rate"])
        for summary in summaries.values()
    )
    accuracy_range = max(accuracies.values()) - min(accuracies.values())
    large_edges = sum(bool(edge["large"]) for edge in edges)
    signal = (
        valid_response
        and accuracy_range >= float(TIER2A_SIGNAL_RULE["accuracy_range"])
        and large_edges >= int(TIER2A_SIGNAL_RULE["minimum_large_parent_child_edges"])
    )
    return {
        "rules": TIER2A_SIGNAL_RULE,
        "valid_response_gate": valid_response,
        "accuracy_range": accuracy_range,
        "large_parent_child_edges": large_edges,
        "edges": edges,
        "representation_behavior_signal": signal,
    }


def _promotion_roster(results: list[dict[str, Any]]) -> list[str]:
    permanent = [
        candidate_id
        for candidate_id in (
            "L0_STRUCTURED_ENGLISH",
            "L1_CURRENT_HML",
            "L2_SEXPR",
            "L3_JSON_AST",
        )
        if any(result["candidate_id"] == candidate_id for result in results)
    ]
    ranked = sorted(
        (result for result in results if result["candidate_id"] not in permanent),
        key=lambda result: (
            -float(result["summary"]["semantic_flip_consistency"]),
            -float(result["summary"]["q1_positive_accuracy"]),
            float(result["summary"]["mean_prompt_tokens"]),
            result["candidate_id"],
        ),
    )
    return [*permanent, *(result["candidate_id"] for result in ranked[: 8 - len(permanent)])]


def run_tier2a(root: Path) -> dict[str, Any]:
    calibration_path = root / "artifacts/experiments/fitness_v2/calibration/result.json"
    if not calibration_path.exists():
        raise RuntimeError("V2 calibration result is absent")
    calibration = _load_json(calibration_path)
    if not calibration.get("tier2a_authorized"):
        raise RuntimeError(f"Tier 2A not authorized: {calibration.get('verdict')}")
    roster = tier2a_candidate_roster()
    results = [
        evaluate_candidate_slice(root, candidate_id=item, slice_name=ProbeSlice.TIER2A_SCOUT)
        for item in roster
    ]
    signal = _tier2_signal(results)
    promotion = _promotion_roster(results) if signal["representation_behavior_signal"] else []
    result = {
        "schema_version": "arena-fitness-v2-tier2a-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "model": QUALIFIED_MODEL,
        "protocol": FROZEN_PROTOCOL.value,
        "slice": ProbeSlice.TIER2A_SCOUT.value,
        "roster": roster,
        "summaries": {item["candidate_id"]: item["summary"] for item in results},
        "paired_vs_l0": _paired_candidate_comparisons(results),
        "signal": signal,
        "promotion_roster": promotion,
        "tier2b_authorized": bool(promotion),
        "calls": sum(item["calls"] for item in results),
    }
    store = ArtifactStore(root / "artifacts")
    result["task_rows_path"] = _write_rows(
        store, "experiments/fitness_v2/tier2a/task_rows.jsonl", results
    )
    store.write_json("experiments/fitness_v2/tier2a/result.json", result)
    return result


def run_tier2b(root: Path) -> dict[str, Any]:
    tier2a_path = root / "artifacts/experiments/fitness_v2/tier2a/result.json"
    if not tier2a_path.exists():
        raise RuntimeError("Tier 2A result is absent")
    tier2a = _load_json(tier2a_path)
    if not tier2a.get("tier2b_authorized"):
        raise RuntimeError("Tier 2B not authorized by the precommitted Tier 2A signal gate")
    roster = tuple(tier2a["promotion_roster"])
    results = [
        evaluate_candidate_slice(root, candidate_id=item, slice_name=ProbeSlice.TIER2B_PROMOTION)
        for item in roster
    ]
    scout_scores = [float(tier2a["summaries"][item]["q1_positive_accuracy"]) for item in roster]
    promotion_scores = [float(result["summary"]["q1_positive_accuracy"]) for result in results]
    rank_stability = spearman(scout_scores, promotion_scores)
    stable = rank_stability is not None and rank_stability >= 0.60
    result = {
        "schema_version": "arena-fitness-v2-tier2b-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "model": QUALIFIED_MODEL,
        "protocol": FROZEN_PROTOCOL.value,
        "slice": ProbeSlice.TIER2B_PROMOTION.value,
        "roster": roster,
        "summaries": {item["candidate_id"]: item["summary"] for item in results},
        "paired_vs_l0": _paired_candidate_comparisons(results),
        "rank_stability_spearman": rank_stability,
        "rank_stability_threshold": 0.60,
        "representation_signal_stable": stable,
        "matched_1k_authorized": stable,
        "calls": sum(item["calls"] for item in results),
    }
    store = ArtifactStore(root / "artifacts")
    result["task_rows_path"] = _write_rows(
        store, "experiments/fitness_v2/tier2b/task_rows.jsonl", results
    )
    store.write_json("experiments/fitness_v2/tier2b/result.json", result)
    return result


def experiment_status_v2(root: Path) -> dict[str, Any]:
    paths = {
        "calibration": root / "artifacts/experiments/fitness_v2/calibration/result.json",
        "tier2a": root / "artifacts/experiments/fitness_v2/tier2a/result.json",
        "tier2b": root / "artifacts/experiments/fitness_v2/tier2b/result.json",
    }
    loaded = {key: _load_json(path) if path.exists() else None for key, path in paths.items()}
    if loaded["tier2b"]:
        sentinel = (
            "REPRESENTATION_EVOLUTION_SIGNAL_FOUND"
            if loaded["tier2b"]["representation_signal_stable"]
            else "NO_MEASURABLE_REPRESENTATION_FITNESS_SIGNAL"
        )
        next_action = (
            "implement and run matched 1K adaptation"
            if loaded["tier2b"]["matched_1k_authorized"]
            else "stop and diagnose promotion rank collapse"
        )
    elif loaded["tier2a"]:
        sentinel = (
            "FITNESS_V2_TIER2B_AUTHORIZED"
            if loaded["tier2a"]["tier2b_authorized"]
            else "NO_MEASURABLE_REPRESENTATION_FITNESS_SIGNAL"
        )
        next_action = "run Tier 2B" if loaded["tier2a"]["tier2b_authorized"] else "stop"
    elif loaded["calibration"]:
        sentinel = (
            "FITNESS_V2_INSTRUMENT_QUALIFIED"
            if loaded["calibration"]["instrument_valid"]
            else loaded["calibration"]["verdict"]
        )
        next_action = (
            "run Tier 2A"
            if loaded["calibration"]["tier2a_authorized"]
            else "redesign DEV calibration"
        )
    else:
        sentinel = "FITNESS_V2_INSTRUMENT_QUALIFIED"
        next_action = "run V2 calibration"
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "sentinel": sentinel,
        "qualified_model": QUALIFIED_MODEL,
        "protocol": FROZEN_PROTOCOL.value,
        "calibration": loaded["calibration"]["verdict"] if loaded["calibration"] else "NOT_RUN",
        "tier2a": "RUN" if loaded["tier2a"] else "NOT_RUN",
        "tier2b": "RUN" if loaded["tier2b"] else "NOT_RUN",
        "matched_1k": "NOT_IMPLEMENTED_OR_RUN",
        "next_action": next_action,
    }


def materialize_instrument(root: Path) -> dict[str, Any]:
    manifest = build_probe_manifest()
    stored = ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v2/probe_manifest.json", manifest
    )
    return {
        "path": str(stored.path),
        "sha256": stored.sha256,
        "manifest_hash": manifest["manifest_hash"],
        "probes": len(manifest["probes"]),
        "pairs": len(manifest["validations"]),
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("materialize", "qualify", "calibrate", "tier2a", "tier2b", "status"),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--model-digest", default="unknown")
    parser.add_argument(
        "--protocol",
        choices=[item.value for item in ResponseProtocol],
        default=ResponseProtocol.CANONICAL_ANSWER.value,
    )
    parser.add_argument(
        "--slice",
        choices=[item.value for item in ProbeSlice],
        default=ProbeSlice.MODEL_QUALIFICATION.value,
    )
    args = parser.parse_args()
    if args.command == "materialize":
        print(json.dumps(materialize_instrument(args.root), indent=2))
        return
    if args.command == "calibrate":
        print(json.dumps(run_calibration_v2(args.root), indent=2))
        return
    if args.command == "tier2a":
        print(json.dumps(run_tier2a(args.root), indent=2))
        return
    if args.command == "tier2b":
        print(json.dumps(run_tier2b(args.root), indent=2))
        return
    if args.command == "status":
        print(json.dumps(experiment_status_v2(args.root), indent=2))
        return
    result = run_model_qualification(
        args.root,
        model=args.model,
        model_digest=args.model_digest,
        protocol=ResponseProtocol(args.protocol),
        slice_name=ProbeSlice(args.slice),
    )
    relative = f"experiments/fitness_v2/qualification/{args.model.replace(':', '_')}-{args.protocol.lower()}-{args.slice.lower()}.json"
    stored = ArtifactStore(args.root / "artifacts").write_json(relative, result)
    print(
        json.dumps(
            {
                "path": str(stored.path),
                "summary": result["summary"],
                "model_calls": result["model_calls"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()


__all__ = [
    "EXPERIMENT_VERSION",
    "INSTRUMENT_VERSION",
    "ProbeSlice",
    "ProbeVariant",
    "QualificationThresholds",
    "ResponseProtocol",
    "SemanticProbe",
    "THRESHOLDS",
    "TruthKind",
    "build_probe_manifest",
    "build_probe_prompt",
    "derive_probe_family",
    "evaluate_candidate_slice",
    "experiment_status_v2",
    "materialize_instrument",
    "parse_response",
    "probes_for_slice",
    "run_model_qualification",
    "run_calibration_v2",
    "run_tier2a",
    "run_tier2b",
    "summarize_probe_rows",
    "validate_probe_family",
]
