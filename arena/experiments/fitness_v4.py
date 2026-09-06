"""Fitness V4: a Game-R structural-ladder instrument with per-mechanism qualification.

V4 replaces the invalidated V3 instrument.  V3 failed for two separable reasons that this
module is built around:

1. Every V3 "floor" row was a context-window artifact.  Prompts of 16K-20K tokens were
   silently truncated by Ollama to 4,099 tokens under ``num_ctx=8192``; the instruction
   header was cut and the model answered in prose.  V4 raises the frozen context budget,
   pre-checks prompt length, post-checks the reported prompt token count, and voids any
   probe that is over budget for *any* candidate rather than scoring it as a failure.
2. Every V3 mechanism that fit the context was a single-field lookup and scored 100%.  V4
   mechanisms require multi-step structural reading (depth comparison with identity
   recurrence, multi-hop dependency, binder scope resolution, conjunctive premise
   satisfaction, and set difference across two states) and each mechanism carries its own
   difficulty ladder.  Level 0 is the explicit-positive control; the frontier level is
   selected DEV-only from the permanent JSON/typed-AST control and every mechanism is
   qualified or voided on its own.

Game-R discipline: only ``R`` varies.  Every founder is a Track-E equal-information
phenotype over the same canonical state; the content genome is fixed at its default and no
Track-C projection is emitted.  ``P``, ``tau``, ``pi``, ``C``, ``D``, ``U``, ``V`` and ``B``
are frozen in this module's constants and in the frozen manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from arena.canonical.schema import (
    CanonicalAction,
    CanonicalExpression,
    CanonicalState,
    EvidenceNode,
    MathObject,
    Obligation,
    canonical_json,
    stable_hash,
)
from arena.experiments.fitness_v2 import QUALIFIED_MODEL
from arena.experiments.fitness_v3 import exact_sign_pvalue
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.storage.artifacts import ArtifactStore
from arena.verifier.native import NativeVerifier

EXPERIMENT_VERSION = "arena-representation-fitness-v4"
INSTRUMENT_VERSION = "arena-game-r-structural-ladder-instrument-v4.0.0"
EXPERIMENT_SEED = 20260907
RESPONSE_PROTOCOL = "JSON_AB"
CONTROL_SURFACE = "L3_JSON_AST"

# B is frozen here.  Only ``num_ctx`` differs from the qualified V2/V3 runtime, and it
# differs because the V3 floor was an input-truncation artifact, not a reasoning result.
RUNTIME_CONFIG: dict[str, Any] = {
    "engine": "ollama",
    "num_ctx": 32768,
    "temperature": 0.0,
    "seed": 20260905,
    "num_predict": 64,
    "top_k": 64,
    "top_p": 0.95,
    "think": False,
}
RUNTIME_CONFIG_HASH = stable_hash(RUNTIME_CONFIG)
CONTEXT_GUARD: dict[str, Any] = {
    "prompt_token_limit": int(RUNTIME_CONFIG["num_ctx"]) - int(RUNTIME_CONFIG["num_predict"]) - 256,
    "pre_call_chars_per_token_floor": 2.0,
    "post_call_chars_per_token_ceiling": 6.0,
    "rule": (
        "a prompt whose chars/2.0 exceeds the limit is never sent; a returned prompt_eval_count "
        "above the limit or below chars/6.0 marks the row TRUNCATED; any probe over budget for "
        "any candidate is void for every candidate"
    ),
}

MECHANISMS = (
    "expression_depth_recurrence",
    "transitive_dependency",
    "binder_scope_resolution",
    "precondition_conjunction",
    "state_delta",
)
# Difficulty ladders.  Level 0 is the explicit-positive control for the mechanism.
LADDERS: dict[str, tuple[dict[str, int], ...]] = {
    "expression_depth_recurrence": (
        {"depth": 3, "recurrence": 1},
        {"depth": 5, "recurrence": 2},
        {"depth": 7, "recurrence": 3},
        {"depth": 10, "recurrence": 4},
        {"depth": 12, "recurrence": 4},
    ),
    "transitive_dependency": (
        {"hops": 1},
        {"hops": 2},
        {"hops": 3},
        {"hops": 5},
        {"hops": 7},
    ),
    "binder_scope_resolution": (
        {"rebinds": 1},
        {"rebinds": 2},
        {"rebinds": 3},
        {"rebinds": 5},
        {"rebinds": 7},
    ),
    "precondition_conjunction": (
        {"premises": 1},
        {"premises": 2},
        {"premises": 3},
        {"premises": 5},
        {"premises": 8},
    ),
    "state_delta": (
        {"facts": 4},
        {"facts": 12},
        {"facts": 24},
        {"facts": 40},
        {"facts": 60},
    ),
}
DEV_FAMILIES_PER_LEVEL = 6
SCOUT_FAMILIES_PER_MECHANISM = 8
DISTRACTOR_OBJECTS = 4

QUALIFICATION_RULE: dict[str, Any] = {
    "selection_source": "DEV only; permanent JSON/typed-AST control only; no candidate outcome",
    "explicit_positive_level": 0,
    "explicit_positive_min": 0.90,
    "frontier_target": 0.625,
    "frontier_selection": (
        "among levels 1..4 choose the level minimising |positive accuracy - 0.625|; ties go to "
        "the lower level"
    ),
    "frontier_band": [0.35, 0.85],
    "q0_valid_rate_min": 0.95,
    "valid_response_rate_min": 0.95,
    "context_truncated_rows_max": 0,
    "positive_negative_gap_min": 0.10,
    "negative_target_accuracy_max": 0.60,
    "semantic_flip_min": 0.25,
    "choice_flip_min": 0.50,
    "position_invariance_min": 0.50,
    "shortcut_rule_max": 0.75,
    "minimum_qualified_mechanisms": 2,
    "void_codes": [
        "VOID_INSTRUMENT_LIMIT",
        "VOID_CEILING",
        "VOID_FLOOR",
        "VOID_VALIDITY",
        "VOID_CONTEXT",
        "VOID_NEGATIVE_CONTROL",
        "VOID_FLIP",
        "VOID_POSITION",
        "VOID_SHORTCUT",
    ],
}
PROMOTION_RULE: dict[str, Any] = {
    "baseline": "V4E_L3_JSON_AST",
    "valid_response_rate_min": 0.95,
    "paired_unit": "positive probe (ORIGINAL and COUNTERFACTUAL) on the common in-budget set",
    "paired_test": "one-sided exact sign test on discordant positive outcomes",
    "paired_p_max": 0.05,
    "familywise_policy": "Holm correction across all non-baseline founders",
    "minimum_net_wins": "max(4, ceil(0.075 * positives))",
    "practical_effect_min": 0.10,
    "practical_equivalence_region": 0.05,
    "semantic_flip_noninferiority": -0.05,
    "interval": "clustered (family) paired bootstrap, 95%, 4000 resamples, seeded",
    "note": (
        "non-significance is not equivalence; a candidate is called practically equivalent to "
        "the control only if its 95% interval lies within +/-0.05"
    ),
}
MODEL_CALL_BUDGET = {"development_max": 800, "scout_max": 2400}


class V4Slice(StrEnum):
    DEV = "DEV"
    SCOUT = "SCOUT"


class V4Variant(StrEnum):
    ORIGINAL = "ORIGINAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DESTROYED_ORIGINAL = "DESTROYED_ORIGINAL"
    DESTROYED_COUNTERFACTUAL = "DESTROYED_COUNTERFACTUAL"
    SWAPPED_ORIGINAL = "SWAPPED_ORIGINAL"
    SWAPPED_COUNTERFACTUAL = "SWAPPED_COUNTERFACTUAL"


POSITIVE_VARIANTS = {V4Variant.ORIGINAL.value, V4Variant.COUNTERFACTUAL.value}
SWAPPED_VARIANTS = {V4Variant.SWAPPED_ORIGINAL.value, V4Variant.SWAPPED_COUNTERFACTUAL.value}


@dataclass(frozen=True, slots=True)
class V4Probe:
    probe_id: str
    family_id: str
    slice_name: V4Slice
    mechanism: str
    level: int
    parameters: dict[str, int]
    variant: V4Variant
    state: CanonicalState
    previous_state: CanonicalState | None
    question: str
    options: tuple[CanonicalAction, CanonicalAction]
    expected_index: int
    truth_kind: str
    oracle_record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "family_id": self.family_id,
            "slice": self.slice_name.value,
            "mechanism": self.mechanism,
            "level": self.level,
            "parameters": dict(self.parameters),
            "variant": self.variant.value,
            "state": self.state.to_dict(),
            "previous_state": self.previous_state.to_dict() if self.previous_state else None,
            "question": self.question,
            "options": [item.to_dict() for item in self.options],
            "expected_index": self.expected_index,
            "truth_kind": self.truth_kind,
            "oracle_record": self.oracle_record,
        }

    @property
    def derived_hash(self) -> str:
        return stable_hash(self.to_dict())


# ----------------------------------------------------------------------------- helpers


def _h(seed: str, modulus: int) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16) % max(1, modulus)


def _hex(seed: str, length: int = 5) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:length]


def _shuffled(items: Sequence[Any], seed: str) -> list[Any]:
    order = sorted(range(len(items)), key=lambda index: _hex(f"{seed}|order|{index}", 16))
    return [items[index] for index in order]


def _atom(value: str) -> CanonicalExpression:
    return CanonicalExpression("symbol", value=value, sort="Identifier")


def _literal(value: int) -> CanonicalExpression:
    return CanonicalExpression("literal", value=value, sort="Integer")


def _relation(name: str, *values: str) -> CanonicalExpression:
    return CanonicalExpression(name, tuple(_atom(value) for value in values), sort="Proposition")


def _apply(left: CanonicalExpression, right: CanonicalExpression) -> CanonicalExpression:
    return CanonicalExpression("apply", (left, right), sort="Term")


def _distractors(prefix: str, count: int) -> tuple[MathObject, ...]:
    return tuple(
        MathObject(
            f"object:{prefix}:{index:02d}",
            "Distractor",
            _relation("tag", prefix, f"value:{(index * 7 + 3) % 29}"),
        )
        for index in range(count)
    )


def _identifier_objects(names: Sequence[str]) -> tuple[MathObject, ...]:
    return tuple(MathObject(f"object:id:{name}", "Identifier", _atom(name)) for name in names)


def _state(
    *,
    goal: CanonicalExpression,
    facts: tuple[CanonicalExpression, ...] = (),
    assumptions: tuple[CanonicalExpression, ...] = (),
    propositions: tuple[CanonicalExpression, ...] = (),
    objects: tuple[MathObject, ...] = (),
    obligations: tuple[Obligation, ...] = (),
    evidence: tuple[EvidenceNode, ...] = (),
    local_scope: tuple[str, ...] = ("scope:root",),
) -> CanonicalState:
    return CanonicalState(
        state_id="state:fitness-v4:neutral",
        objects=objects,
        bindings=(),
        assumptions=assumptions,
        established_facts=facts,
        propositions=propositions,
        goal=goal,
        obligations=obligations,
        evidence_dependencies=evidence,
        local_scope=local_scope,
        legal_actions=(),
        plausible_invalid_actions=(),
        terminal_status="OPEN",
        execution_metadata=(),
    )


def _option(index: int, answer: str, alternate: str) -> CanonicalAction:
    """A symmetric option: only the proposed identity differs between A and B."""

    obligation = Obligation(f"obligation:option:{index}", _relation("prove", answer), source=answer)
    return CanonicalAction(
        action_id=f"option:{index}",
        operation="propose_structural_answer",
        target_ids=(f"object:id:{answer}",),
        arguments=(_atom(answer),),
        warrant=f"evidence-authority:{answer}",
        preconditions=(_relation("requires", answer), _relation("exclude", alternate)),
        generated_obligations=(obligation,),
        expected_usefulness=0.0,
    )


@dataclass(frozen=True, slots=True)
class _Family:
    original: CanonicalState
    counterfactual: CanonicalState
    destroyed: CanonicalState
    previous_original: CanonicalState | None
    previous_counterfactual: CanonicalState | None
    previous_destroyed: CanonicalState | None
    answer_a: str
    answer_b: str
    question: str
    truth_check: dict[str, Any]


# ------------------------------------------------ mechanism 1: expression depth/recurrence


def expression_depths(
    node: CanonicalExpression, depth: int = 0, out: dict[str, list[int]] | None = None
) -> dict[str, list[int]]:
    """Every occurrence depth of every symbol identifier, re-derived from the built tree."""

    out = {} if out is None else out
    if node.op == "symbol" and isinstance(node.value, str):
        out.setdefault(node.value, []).append(depth)
    for argument in node.args:
        expression_depths(argument, depth + 1, out)
    return out


def _hanger(leaves: list[CanonicalExpression], height: int, seed: str) -> CanonicalExpression:
    if len(leaves) == 1:
        return leaves[0]
    if height < 1 or len(leaves) > 2**height:
        raise ValueError("hanger cannot fit its leaves within the height bound")
    capacity = 2 ** (height - 1)
    low = max(1, len(leaves) - capacity)
    high = min(capacity, len(leaves) - 1)
    split = low + _h(f"{seed}|split|{len(leaves)}", high - low + 1)
    left = _hanger(leaves[:split], height - 1, seed + "L")
    right = _hanger(leaves[split:], height - 1, seed + "R")
    return _apply(left, right)


def build_depth_tree(
    *,
    target: str,
    runner_up: str,
    others: Sequence[str],
    depth: int,
    recurrence: int,
    seed: str,
    tie: bool = False,
) -> CanonicalExpression:
    """A term tree whose unique deepest identifier is ``target`` at ``depth`` (lead 1).

    Adapted from HML_V3 ``src/hml_v3/projection/dense.py`` (``generate_dense_v2``): every
    identity recurs ``recurrence`` times, the runner-up is pinned one level above the
    target, the association direction of every spine level is hashed so the answer is not a
    string-end token, and the truth is re-derived by walking the finished tree.  With
    ``tie`` the runner-up shares the target's depth, which destroys the relation.
    """

    if depth < 3 or recurrence < 1:
        raise ValueError("depth must be at least 3 and recurrence at least 1")
    identities = [target, runner_up, *others]
    requests = [target] * (recurrence - 1) + [runner_up] * (recurrence - 1)
    for other in others:
        requests.extend([other] * recurrence)
    # Levels are spine positions; a hanger attached at level L has its leaves at depths
    # L+1 .. depth-1 at most, so nothing but the target can reach ``depth``.
    levels = list(range(0, depth - 2))
    per_level: dict[int, list[str]] = {level: [] for level in range(depth)}
    for position, identity in enumerate(requests):
        if not levels:
            raise ValueError("no level can host a recurrence at this depth")
        choice = levels[_h(f"{seed}|level|{position}|{identity}", len(levels))]
        if len(per_level[choice]) >= 2 ** (depth - 2 - choice):
            for alternative in levels:
                if len(per_level[alternative]) < 2 ** (depth - 2 - alternative):
                    choice = alternative
                    break
            else:
                raise ValueError("no capacity for the requested recurrence at this depth")
        per_level[choice].append(identity)

    if tie:
        node: CanonicalExpression = _apply(_atom(target), _atom(runner_up))
        spine_levels = list(range(depth - 2, -1, -1))
    else:
        node = _atom(target)
        spine_levels = list(range(depth - 1, -1, -1))
    for level in spine_levels:
        if level == depth - 2 and not tie:
            free: CanonicalExpression = _atom(runner_up)
        elif per_level.get(level):
            leaves = [_atom(identity) for identity in per_level[level]]
            free = _hanger(leaves, depth - 2 - level, f"{seed}|hanger|{level}")
        else:
            free = _literal(_h(f"{seed}|lit|{level}", 97))
        spin = _h(f"{seed}|assoc|{level}", 2)
        node = _apply(node, free) if spin == 0 else _apply(free, node)
    walked = expression_depths(node)
    maxima = {identity: max(values) for identity, values in walked.items()}
    counts = {identity: len(values) for identity, values in walked.items()}
    if set(maxima) != set(identities):
        raise ValueError("depth tree lost or invented an identity")
    if tie:
        if maxima[target] != maxima[runner_up]:
            raise ValueError("tie construction failed")
    else:
        if maxima[target] != depth or maxima[runner_up] != depth - 1:
            raise ValueError("depth tree does not pin target and runner-up as requested")
        if any(value >= depth for identity, value in maxima.items() if identity != target):
            raise ValueError("target is not the unique deepest identifier")
    if any(counts[identity] != recurrence for identity in identities):
        raise ValueError(f"occurrence counts {counts} are not all {recurrence}")
    return node


def _depth_family(params: dict[str, int], salt: str) -> _Family:
    depth, recurrence = params["depth"], params["recurrence"]
    names = [f"v{_hex(f'{salt}|name|{index}', 4)}" for index in range(4)]
    if len(set(names)) != 4:
        names = [f"v{index}{_hex(f'{salt}|name2|{index}', 3)}" for index in range(4)]
    a, b, x, y = names
    objects = (*_identifier_objects(names), *_distractors(_hex(salt), DISTRACTOR_OBJECTS))
    original_tree = build_depth_tree(
        target=a, runner_up=b, others=(x, y), depth=depth, recurrence=recurrence, seed=salt
    )
    counter_tree = build_depth_tree(
        target=b, runner_up=a, others=(x, y), depth=depth, recurrence=recurrence, seed=salt
    )
    destroyed_tree = build_depth_tree(
        target=a,
        runner_up=b,
        others=(x, y),
        depth=depth,
        recurrence=recurrence,
        seed=salt,
        tie=True,
    )
    question = (
        "Which identifier occurs at the greatest nesting depth inside the goal expression? "
        "Depth counts nested argument levels from the goal's root."
    )
    return _Family(
        original=_state(goal=original_tree, objects=objects),
        counterfactual=_state(goal=counter_tree, objects=objects),
        destroyed=_state(goal=destroyed_tree, objects=objects),
        previous_original=None,
        previous_counterfactual=None,
        previous_destroyed=None,
        answer_a=a,
        answer_b=b,
        question=question,
        truth_check={"rule": "unique maximum symbol depth by tree walk"},
    )


# ------------------------------------------------------ mechanism 2: transitive dependency


def ancestors(evidence: Sequence[EvidenceNode], start: str) -> set[str]:
    graph = {node.evidence_id: node.dependencies for node in evidence}
    seen: set[str] = set()
    frontier = list(graph.get(start, ()))
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        frontier.extend(graph.get(current, ()))
    return seen


def _dependency_family(params: dict[str, int], salt: str) -> _Family:
    hops = params["hops"]
    length = hops + 1

    def chain(label: str) -> list[str]:
        return [f"e:{_hex(f'{salt}|{label}|{index}')}" for index in range(length)]

    p_chain, q_chain = chain("p"), chain("q")
    if len(set(p_chain) | set(q_chain)) != 2 * length:
        raise ValueError("evidence identifiers collided")
    junction = _h(f"{salt}|junction", hops)

    def build(attached: list[str], other: list[str], leaf_dep: bool) -> tuple[EvidenceNode, ...]:
        nodes: list[EvidenceNode] = []
        for chain_nodes in (attached, other):
            for index, node_id in enumerate(chain_nodes):
                deps: tuple[str, ...] = (
                    (chain_nodes[index + 1],) if index + 1 < len(chain_nodes) else ()
                )
                if chain_nodes is other and index == 0:
                    deps = (*deps, attached[junction])
                nodes.append(EvidenceNode(node_id, "VERIFIED", deps, "arena-native", None))
        leaf_deps = (attached[0],) if leaf_dep else ()
        nodes.append(EvidenceNode("e:leaf", "UNKNOWN", leaf_deps, "arena-native", None))
        return tuple(_shuffled(nodes, f"{salt}|evidence"))

    # e:leaf depends on chain[0]; chain[i] is therefore i+1 steps from e:leaf.
    a, b = p_chain[hops - 1], q_chain[hops - 1]
    objects = (*_identifier_objects((a, b)), *_distractors(_hex(salt), DISTRACTOR_OBJECTS))
    goal = _relation("transitive_dependency_of", "e:leaf")
    original = _state(goal=goal, objects=objects, evidence=build(p_chain, q_chain, True))
    counter = _state(goal=goal, objects=objects, evidence=build(q_chain, p_chain, True))
    destroyed = _state(goal=goal, objects=objects, evidence=build(p_chain, q_chain, False))
    if a not in ancestors(original.evidence_dependencies, "e:leaf"):
        raise ValueError("original answer is not an ancestor of e:leaf")
    if b in ancestors(original.evidence_dependencies, "e:leaf"):
        raise ValueError("original alternate is an ancestor of e:leaf")
    if b not in ancestors(counter.evidence_dependencies, "e:leaf"):
        raise ValueError("counterfactual answer is not an ancestor of e:leaf")
    if a in ancestors(counter.evidence_dependencies, "e:leaf"):
        raise ValueError("counterfactual alternate is an ancestor of e:leaf")
    if ancestors(destroyed.evidence_dependencies, "e:leaf"):
        raise ValueError("destroyed state still has ancestors")
    question = (
        "Which evidence ID is a transitive dependency of e:leaf, reached by following the "
        f"dependencies field {hops} step(s) from e:leaf?"
    )
    return _Family(
        original=original,
        counterfactual=counter,
        destroyed=destroyed,
        previous_original=None,
        previous_counterfactual=None,
        previous_destroyed=None,
        answer_a=a,
        answer_b=b,
        question=question,
        truth_check={"rule": "independent ancestor closure over the dependencies field"},
    )


# ------------------------------------------------ mechanism 3: binder scope resolution


def resolve_site(node: CanonicalExpression, site: str) -> str | None:
    """Independent lexical scope resolution: the binder ID that binds the tagged variable."""

    def visit(current: CanonicalExpression, stack: dict[str, list[str]]) -> str | None:
        if current.op == "var" and dict(current.attributes).get("site") == site:
            name = str(current.value)
            return stack[name][-1] if stack.get(name) else "UNBOUND"
        if current.op in {"forall", "exists", "lambda"} and current.args:
            binder = current.args[0]
            name = str(binder.value)
            binder_id = dict(current.attributes)["binder"]
            stack.setdefault(name, []).append(binder_id)
            for argument in current.args[1:]:
                found = visit(argument, stack)
                if found is not None:
                    stack[name].pop()
                    return found
            stack[name].pop()
            return None
        for argument in current.args:
            found = visit(argument, stack)
            if found is not None:
                return found
        return None

    return visit(node, {})


def _var(name: str, site: str | None = None) -> CanonicalExpression:
    attributes = (("site", site),) if site else ()
    return CanonicalExpression("var", value=name, sort="Term", attributes=attributes)


def _binder(kind: str, name: str, binder_id: str, body: CanonicalExpression) -> CanonicalExpression:
    return CanonicalExpression(
        kind, (_var(name), body), sort="Proposition", attributes=(("binder", binder_id),)
    )


def _scope_family(params: dict[str, int], salt: str) -> _Family:
    rebinds = params["rebinds"]
    variable = "x"
    decoy_variable = "y"
    path_ids = [f"b:{_hex(f'{salt}|path|{index}')}" for index in range(rebinds)]
    side_ids = [f"b:{_hex(f'{salt}|side|{index}')}" for index in range(rebinds)]
    shade_ids = [f"b:{_hex(f'{salt}|shade|{index}')}" for index in range(rebinds)]
    if len(set(path_ids) | set(side_ids) | set(shade_ids)) != 3 * rebinds:
        raise ValueError("binder identifiers collided")
    kinds = ("forall", "exists", "lambda")

    def build(site_level: int | None, site_on_side: bool) -> CanonicalExpression:
        # ``site_level`` is the path binder whose scope carries the tagged use; ``site_on_side``
        # puts the tag inside the sibling binder attached at the innermost level instead.
        node: CanonicalExpression = _apply(
            _var(variable, "use:query" if site_level == rebinds - 1 and not site_on_side else None),
            _var(decoy_variable),
        )
        for level in range(rebinds - 1, -1, -1):
            kind = kinds[_h(f"{salt}|kind|{level}", len(kinds))]
            side_site = "use:query" if site_on_side and level == rebinds - 1 else None
            side = _binder(
                kinds[_h(f"{salt}|sidekind|{level}", len(kinds))],
                variable,
                side_ids[level],
                _apply(_var(variable, side_site), _literal(_h(f"{salt}|sidelit|{level}", 89))),
            )
            body = (
                _apply(node, side)
                if _h(f"{salt}|sideassoc|{level}", 2) == 0
                else _apply(side, node)
            )
            body = _binder(
                kinds[_h(f"{salt}|shadekind|{level}", len(kinds))],
                decoy_variable,
                shade_ids[level],
                body,
            )
            node = _binder(kind, variable, path_ids[level], body)
            if site_level is not None and level - 1 == site_level and not site_on_side:
                node = _apply(node, _var(variable, "use:query"))
        return node

    answer_a = path_ids[-1]
    if rebinds > 1:
        original = build(rebinds - 1, False)
        counter = build(rebinds - 2, False)
        answer_b = path_ids[-2]
    else:
        original = build(0, False)
        counter = build(None, True)
        answer_b = side_ids[-1]
    destroyed = build(None, False)
    if resolve_site(original, "use:query") != answer_a:
        raise ValueError("original site does not resolve to the expected binder")
    if resolve_site(counter, "use:query") != answer_b:
        raise ValueError("counterfactual site does not resolve to the alternate binder")
    if resolve_site(destroyed, "use:query") is not None:
        raise ValueError("destroyed state still carries the tagged site")
    if rebinds > 1:
        outer = _apply(_binder("forall", variable, "b:outer", original), _literal(1))
        if resolve_site(outer, "use:query") != answer_a:
            raise ValueError("scope resolution is not lexical")
    objects = (
        *_identifier_objects((answer_a, answer_b)),
        *_distractors(_hex(salt), DISTRACTOR_OBJECTS),
    )
    goal_original = _relation("binder_of_site", "use:query")
    question = (
        "Which binder ID binds the variable occurrence tagged site=use:query in the goal "
        "expression, under lexical scoping where the innermost enclosing binder of the same "
        "variable name wins?"
    )
    return _Family(
        original=_state(goal=original, objects=objects),
        counterfactual=_state(goal=counter, objects=objects),
        destroyed=_state(goal=destroyed, objects=objects),
        previous_original=None,
        previous_counterfactual=None,
        previous_destroyed=None,
        answer_a=answer_a,
        answer_b=answer_b,
        question=question,
        truth_check={
            "rule": "independent lexical scope resolution",
            "goal_relation": goal_original.op,
        },
    )


# ------------------------------------------- mechanism 4: conjunctive premise satisfaction


def satisfied_options(state: CanonicalState) -> set[str]:
    held = {
        str(item.args[0].value) for item in state.assumptions if item.op == "holds" and item.args
    }
    required: dict[str, set[str]] = defaultdict(set)
    for item in state.propositions:
        if item.op == "requires" and len(item.args) == 2:
            required[str(item.args[0].value)].add(str(item.args[1].value))
    return {owner for owner, premises in required.items() if premises <= held}


def _near_miss(premise: str, salt: str, forbidden: set[str]) -> str:
    """A confusable premise id: an adjacent-digit transposition that is not a real premise."""

    digits = premise.split(":")[1]
    start = _h(f"{salt}|swap", len(digits) - 1)
    for offset in range(len(digits) - 1):
        index = (start + offset) % (len(digits) - 1)
        swapped = list(digits)
        swapped[index], swapped[index + 1] = swapped[index + 1], swapped[index]
        candidate = "p:" + "".join(swapped)
        if candidate != premise and candidate not in forbidden:
            return candidate
    candidate = "p:" + digits[::-1]
    if candidate != premise and candidate not in forbidden:
        return candidate
    return "p:" + digits + str(_h(f"{salt}|extra", 9) + 1)


def _premise_family(params: dict[str, int], salt: str) -> _Family:
    count = params["premises"]
    pool: list[str] = []
    seen: set[str] = set()
    probe = 0
    while len(pool) < 2 * count + 6:
        digits = "".join(
            str(_h(f"{salt}|digit|{probe}|{position}", 9) + 1) for position in range(4)
        )
        candidate = f"p:{digits}"
        probe += 1
        if candidate in seen or candidate[::-1] in seen:
            continue
        seen.add(candidate)
        pool.append(candidate)
    a_premises, b_premises = pool[:count], pool[count : 2 * count]
    extras = pool[2 * count :]
    a, b = f"answer:{_hex(f'{salt}|A')}", f"answer:{_hex(f'{salt}|B')}"
    missing_b = b_premises[_h(f"{salt}|missing", count)]
    missing_a = a_premises[_h(f"{salt}|missing_a", count)]
    near_b = _near_miss(missing_b, salt + "b", seen)
    near_a = _near_miss(missing_a, salt + "a", seen | {near_b})
    if near_b in seen or near_a in seen or near_a == near_b:
        raise ValueError("near-miss premise collides with a real premise")
    propositions = tuple(
        _shuffled(
            [
                *(_relation("requires", a, premise) for premise in a_premises),
                *(_relation("requires", b, premise) for premise in b_premises),
            ],
            f"{salt}|props",
        )
    )

    def held(a_full: bool, b_full: bool) -> tuple[CanonicalExpression, ...]:
        items = [_relation("holds", premise) for premise in extras]
        for premise in a_premises:
            if a_full or premise != missing_a:
                items.append(_relation("holds", premise))
        for premise in b_premises:
            if b_full or premise != missing_b:
                items.append(_relation("holds", premise))
        if not a_full:
            items.append(_relation("holds", near_a))
        if not b_full:
            items.append(_relation("holds", near_b))
        return tuple(_shuffled(items, f"{salt}|held|{a_full}|{b_full}"))

    objects = (*_identifier_objects((a, b)), *_distractors(_hex(salt), DISTRACTOR_OBJECTS))
    goal = _relation("fully_licensed_answer", "query")
    original = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=held(True, False)
    )
    counter = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=held(False, True)
    )
    destroyed = _state(
        goal=goal, objects=objects, propositions=propositions, assumptions=held(False, False)
    )
    if satisfied_options(original) != {a} or satisfied_options(counter) != {b}:
        raise ValueError("premise satisfaction truth does not match construction")
    if satisfied_options(destroyed):
        raise ValueError("destroyed state still licenses an option")
    question = (
        "Which answer ID has every one of its requires(answer, premise) propositions matched "
        "by an identical holds(premise) assumption?"
    )
    return _Family(
        original=original,
        counterfactual=counter,
        destroyed=destroyed,
        previous_original=None,
        previous_counterfactual=None,
        previous_destroyed=None,
        answer_a=a,
        answer_b=b,
        question=question,
        truth_check={"rule": "independent subset check of required premises against held premises"},
    )


# ------------------------------------------------------------- mechanism 5: state delta


def added_facts(previous: CanonicalState, current: CanonicalState) -> set[str]:
    before = {item.content_hash for item in previous.established_facts}
    return {
        str(item.args[0].value)
        for item in current.established_facts
        if item.content_hash not in before and item.args
    }


def _delta_family(params: dict[str, int], salt: str) -> _Family:
    count = params["facts"]
    a, b = f"answer:{_hex(f'{salt}|A')}", f"answer:{_hex(f'{salt}|B')}"
    base = [_relation("holds", f"fact:{_hex(f'{salt}|fact|{index}')}") for index in range(count)]

    def facts(present: Sequence[str], seed: str) -> tuple[CanonicalExpression, ...]:
        items = list(base)
        for name in present:
            position = _h(f"{salt}|insert|{seed}|{name}", len(items) + 1)
            items.insert(position, _relation("holds", name))
        return tuple(items)

    objects = (*_identifier_objects((a, b)), *_distractors(_hex(salt), DISTRACTOR_OBJECTS))
    goal = _relation("find_added_fact", "query")
    previous_original = _state(goal=goal, objects=objects, facts=facts((b,), "prev"))
    original = _state(goal=goal, objects=objects, facts=facts((b, a), "prev"))
    previous_counter = _state(goal=goal, objects=objects, facts=facts((a,), "prev"))
    counter = _state(goal=goal, objects=objects, facts=facts((a, b), "prev"))
    previous_destroyed = _state(goal=goal, objects=objects, facts=facts((b, a), "prev"))
    destroyed = previous_destroyed
    if added_facts(previous_original, original) != {a} or added_facts(
        previous_counter, counter
    ) != {b}:
        raise ValueError("state delta truth does not match construction")
    if added_facts(previous_destroyed, destroyed):
        raise ValueError("destroyed delta is not empty")
    question = (
        "Which answer ID has a holds(answer) established fact that is present in the CURRENT "
        "state but absent from the PREVIOUS state?"
    )
    return _Family(
        original=original,
        counterfactual=counter,
        destroyed=destroyed,
        previous_original=previous_original,
        previous_counterfactual=previous_counter,
        previous_destroyed=previous_destroyed,
        answer_a=a,
        answer_b=b,
        question=question,
        truth_check={"rule": "independent set difference over established_facts content hashes"},
    )


FAMILY_BUILDERS: dict[str, Callable[[dict[str, int], str], _Family]] = {
    "expression_depth_recurrence": _depth_family,
    "transitive_dependency": _dependency_family,
    "binder_scope_resolution": _scope_family,
    "precondition_conjunction": _premise_family,
    "state_delta": _delta_family,
}


# ---------------------------------------------------------------------- probe families


def derive_probe_family(
    mechanism: str, level: int, slice_name: V4Slice, salt: int
) -> tuple[V4Probe, ...]:
    params = LADDERS[mechanism][level]
    family = FAMILY_BUILDERS[mechanism](params, f"{EXPERIMENT_VERSION}|{mechanism}|{level}|{salt}")
    options = (
        _option(0, family.answer_a, family.answer_b),
        _option(1, family.answer_b, family.answer_a),
    )
    family_id = f"v4:{slice_name.value.lower()}:{mechanism}:l{level}:{salt}"

    def make(
        variant: V4Variant,
        state: CanonicalState,
        previous: CanonicalState | None,
        expected: int,
        truth: str,
        displayed: tuple[CanonicalAction, CanonicalAction] = options,
    ) -> V4Probe:
        identity = {
            "family": family_id,
            "variant": variant.value,
            "state": state.mathematical_hash,
            "previous": previous.mathematical_hash if previous else None,
            "options": [item.to_dict() for item in displayed],
        }
        return V4Probe(
            probe_id=f"probe:{stable_hash(identity)[:20]}",
            family_id=family_id,
            slice_name=slice_name,
            mechanism=mechanism,
            level=level,
            parameters=dict(params),
            variant=variant,
            state=state,
            previous_state=previous,
            question=family.question,
            options=displayed,
            expected_index=expected,
            truth_kind=truth,
            oracle_record={
                "rule": mechanism,
                "truth_check": family.truth_check,
                "answer": displayed[expected].arguments[0].to_dict()
                if truth == "MATHEMATICAL"
                else None,
                "generator_salt": salt,
                "parameters": dict(params),
            },
        )

    swapped = cast(tuple[CanonicalAction, CanonicalAction], tuple(reversed(options)))
    return (
        make(V4Variant.ORIGINAL, family.original, family.previous_original, 0, "MATHEMATICAL"),
        make(
            V4Variant.COUNTERFACTUAL,
            family.counterfactual,
            family.previous_counterfactual,
            1,
            "MATHEMATICAL",
        ),
        make(
            V4Variant.DESTROYED_ORIGINAL,
            family.destroyed,
            family.previous_destroyed,
            0,
            "NEGATIVE_CONTROL_TARGET",
        ),
        make(
            V4Variant.DESTROYED_COUNTERFACTUAL,
            family.destroyed,
            family.previous_destroyed,
            1,
            "NEGATIVE_CONTROL_TARGET",
        ),
        make(
            V4Variant.SWAPPED_ORIGINAL,
            family.original,
            family.previous_original,
            1,
            "MATHEMATICAL",
            swapped,
        ),
        make(
            V4Variant.SWAPPED_COUNTERFACTUAL,
            family.counterfactual,
            family.previous_counterfactual,
            0,
            "MATHEMATICAL",
            swapped,
        ),
    )


def validate_probe_family(probes: tuple[V4Probe, ...]) -> dict[str, Any]:
    if len(probes) != 6 or len({item.family_id for item in probes}) != 1:
        raise ValueError("V4 family must contain six siblings")
    by_variant = {item.variant: item for item in probes}
    verifier = NativeVerifier()
    for probe in probes:
        for state in (probe.state, probe.previous_state):
            if state is None:
                continue
            result = verifier.verify_state(state)
            if not result.accepted:
                raise ValueError(f"invalid V4 state {probe.probe_id}: {result.issues}")
            if state.legal_actions or state.plausible_invalid_actions:
                raise ValueError("V4 observation leaks action membership")
        if any(option.expected_usefulness != 0.0 for option in probe.options):
            raise ValueError("V4 option leaks oracle usefulness")
    neg_a = by_variant[V4Variant.DESTROYED_ORIGINAL]
    neg_b = by_variant[V4Variant.DESTROYED_COUNTERFACTUAL]
    if (
        neg_a.state.mathematical_hash != neg_b.state.mathematical_hash
        or neg_a.options != neg_b.options
        or (neg_a.previous_state is None) != (neg_b.previous_state is None)
        or (
            neg_a.previous_state is not None
            and neg_b.previous_state is not None
            and neg_a.previous_state.mathematical_hash != neg_b.previous_state.mathematical_hash
        )
    ):
        raise ValueError("V4 negative siblings are not information-identical")
    if neg_a.expected_index == neg_b.expected_index:
        raise ValueError("V4 negative targets are not balanced")
    for original_name, swapped_name in (
        (V4Variant.ORIGINAL, V4Variant.SWAPPED_ORIGINAL),
        (V4Variant.COUNTERFACTUAL, V4Variant.SWAPPED_COUNTERFACTUAL),
    ):
        base, swapped = by_variant[original_name], by_variant[swapped_name]
        if base.state.mathematical_hash != swapped.state.mathematical_hash:
            raise ValueError("position swap changed V4 state")
        if base.options != tuple(reversed(swapped.options)):
            raise ValueError("position swap changed V4 option set")
        if (
            base.options[base.expected_index].arguments
            != swapped.options[swapped.expected_index].arguments
        ):
            raise ValueError("position swap changed V4 truth")
    positives = [by_variant[V4Variant.ORIGINAL], by_variant[V4Variant.COUNTERFACTUAL]]
    if {item.expected_index for item in positives} != {0, 1}:
        raise ValueError("V4 positive targets are not balanced")
    return {
        "family_id": probes[0].family_id,
        "valid": True,
        "derived_hashes_unique": len({item.derived_hash for item in probes}) == 6,
    }


def family_salt(slice_name: V4Slice, mechanism: str, level: int, family_index: int) -> int:
    slice_offset = {V4Slice.DEV: 0, V4Slice.SCOUT: 100000}[slice_name]
    return (
        EXPERIMENT_SEED
        + slice_offset
        + MECHANISMS.index(mechanism) * 1000
        + level * 100
        + family_index
    )


def build_dev_pool(
    mechanisms: Sequence[str] = MECHANISMS,
    levels: Sequence[int] = (0, 1, 2, 3, 4),
    families: int = DEV_FAMILIES_PER_LEVEL,
) -> tuple[V4Probe, ...]:
    probes: list[V4Probe] = []
    for mechanism in mechanisms:
        for level in levels:
            for family_index in range(families):
                family = derive_probe_family(
                    mechanism,
                    level,
                    V4Slice.DEV,
                    family_salt(V4Slice.DEV, mechanism, level, family_index),
                )
                validate_probe_family(family)
                probes.extend(family)
    return tuple(probes)


def build_scout_pool(
    selected_levels: dict[str, int], families: int = SCOUT_FAMILIES_PER_MECHANISM
) -> tuple[V4Probe, ...]:
    probes: list[V4Probe] = []
    for mechanism in MECHANISMS:
        if mechanism not in selected_levels:
            continue
        level = selected_levels[mechanism]
        for family_index in range(families):
            family = derive_probe_family(
                mechanism,
                level,
                V4Slice.SCOUT,
                family_salt(V4Slice.SCOUT, mechanism, level, family_index),
            )
            validate_probe_family(family)
            probes.extend(family)
    return tuple(probes)


def _probe_from_dict(raw: dict[str, Any]) -> V4Probe:
    options = tuple(CanonicalAction.from_dict(item) for item in raw["options"])
    if len(options) != 2:
        raise ValueError("frozen V4 probe must contain exactly two options")
    return V4Probe(
        probe_id=str(raw["probe_id"]),
        family_id=str(raw["family_id"]),
        slice_name=V4Slice(raw["slice"]),
        mechanism=str(raw["mechanism"]),
        level=int(raw["level"]),
        parameters={str(key): int(value) for key, value in raw["parameters"].items()},
        variant=V4Variant(raw["variant"]),
        state=CanonicalState.from_dict(raw["state"]),
        previous_state=CanonicalState.from_dict(raw["previous_state"])
        if raw["previous_state"]
        else None,
        question=str(raw["question"]),
        options=cast(tuple[CanonicalAction, CanonicalAction], options),
        expected_index=int(raw["expected_index"]),
        truth_kind=str(raw["truth_kind"]),
        oracle_record=dict(raw["oracle_record"]),
    )


# ------------------------------------------------------------ genomes, prompts, calls


def equal_information_genome(surface_id: str = CONTROL_SURFACE) -> ModelViewGenome:
    """A Track-E founder: reversible surface only, content genome fixed at its default."""

    return ModelViewGenome(
        f"V4E_{surface_id}",
        (),
        SearchTrack.EQUAL_INFORMATION,
        SEED_GENOME_BY_ID[surface_id],
        ContentGenome(),
    )


def founder_genomes() -> tuple[ModelViewGenome, ...]:
    """Eight equal-information founders.  No Track-C candidate enters Game R."""

    return tuple(equal_information_genome(candidate_id) for candidate_id in SEED_GENOME_BY_ID)


def assert_game_r_genome(genome: ModelViewGenome) -> None:
    if genome.track != SearchTrack.EQUAL_INFORMATION:
        raise ValueError(f"{genome.candidate_id} is not a Game-R equal-information candidate")
    if genome.content != ContentGenome():
        raise ValueError(f"{genome.candidate_id} varies the projection policy P inside Game R")


def build_prompt(genome: ModelViewGenome, probe: V4Probe) -> str:
    assert_game_r_genome(genome)
    compiler = ModelViewCompiler(genome)
    language = GenomePhenotypeLanguage(genome.surface)
    view = compiler.compile(probe.state, options=probe.options, previous_state=probe.previous_state)
    rendered_options = [
        f"{label}: {language.render_action_choice(option)}"
        for label, option in zip(("A", "B"), probe.options, strict=True)
    ]
    previous = (
        f"PREVIOUS STATE:\n{language.render(probe.previous_state)}\n"
        if probe.previous_state
        else ""
    )
    return (
        'Return exactly {"choice":"A"} or {"choice":"B"}; no explanation.\n'
        "Read identifiers exactly. Do not choose by option position.\n"
        f"QUESTION: {probe.question}\nSYNTAX GUIDE:\n{language.acquisition_guide()}\n"
        f"{previous}CURRENT STATE:\n{view.text}\nOPTIONS:\n"
        + "\n".join(rendered_options)
        + "\nANSWER:"
    )


def assert_information_parity(probe: V4Probe, genomes: Sequence[ModelViewGenome]) -> dict[str, Any]:
    """Every founder must recover the identical canonical state and render distinct bytes."""

    rendered: dict[str, str] = {}
    for genome in genomes:
        assert_game_r_genome(genome)
        compiler = ModelViewCompiler(genome)
        for state in (probe.state, probe.previous_state):
            if state is None:
                continue
            compiled = compiler.compile(state, options=probe.options)
            compiler.validate(compiled, state, options=probe.options)
        rendered[genome.candidate_id] = build_prompt(genome, probe)
    if len(set(rendered.values())) != len(rendered):
        raise ValueError("two founders rendered byte-identical prompts")
    return {candidate_id: stable_hash(text) for candidate_id, text in rendered.items()}


def parse_response(output: str) -> int | None:
    try:
        value = json.loads(output.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or set(value) != {"choice"} or value["choice"] not in {"A", "B"}:
        return None
    return 0 if value["choice"] == "A" else 1


def _call_ollama(model: str, prompt: str) -> dict[str, Any]:
    options = {
        key: value for key, value in RUNTIME_CONFIG.items() if key not in {"engine", "think"}
    }
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": RUNTIME_CONFIG["think"],
                "options": options,
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=600) as response:  # noqa: S310 - fixed local service
        raw = json.loads(response.read().decode())
    return {
        "response": str(raw.get("response", "")),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "total_duration_ns": int(raw.get("total_duration", 0)),
    }


def context_status(prompt: str, prompt_eval_count: int | None) -> str:
    limit = int(CONTEXT_GUARD["prompt_token_limit"])
    if len(prompt) / float(CONTEXT_GUARD["pre_call_chars_per_token_floor"]) > limit:
        return "OVER_BUDGET"
    if prompt_eval_count is None:
        return "UNSENT"
    if prompt_eval_count > limit:
        return "TRUNCATED"
    if prompt_eval_count < len(prompt) / float(CONTEXT_GUARD["post_call_chars_per_token_ceiling"]):
        return "TRUNCATED"
    return "OK"


def _cached_call(root: Path, identity: dict[str, Any], prompt: str) -> tuple[dict[str, Any], bool]:
    path = root / "artifacts/cache/fitness_v4" / f"{stable_hash(identity)}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("identity") != identity or not isinstance(cached.get("result"), dict):
            raise ValueError(f"invalid V4 cache record: {path}")
        return cached["result"], True
    if context_status(prompt, None) == "OVER_BUDGET":
        raw: dict[str, Any] = {
            "response": "",
            "error": "OVER_BUDGET: prompt not sent",
            "prompt_eval_count": 0,
            "eval_count": 0,
            "total_duration_ns": 0,
        }
    else:
        started = time.monotonic()
        try:
            raw = _call_ollama(str(QUALIFIED_MODEL["name"]), prompt)
        except Exception as error:
            raw = {
                "response": "",
                "error": repr(error),
                "prompt_eval_count": 0,
                "eval_count": 0,
                "total_duration_ns": int((time.monotonic() - started) * 1e9),
            }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json({"identity": identity, "result": raw}), encoding="utf-8")
    return raw, False


def evaluate(
    root: Path,
    genome: ModelViewGenome,
    probes: Sequence[V4Probe],
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    assert_game_r_genome(genome)
    rows: list[dict[str, Any]] = []
    for index, probe in enumerate(probes):
        prompt = build_prompt(genome, probe)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "instrument": INSTRUMENT_VERSION,
            "model_digest": QUALIFIED_MODEL["digest"],
            "runtime_hash": RUNTIME_CONFIG_HASH,
            "genome_hash": genome.genome_hash,
            "probe_hash": probe.derived_hash,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, prompt)
        status = context_status(prompt, None if raw.get("error") else raw["prompt_eval_count"])
        selected = parse_response(raw["response"]) if status == "OK" else None
        selected_hash = (
            probe.options[selected].arguments[0].content_hash if selected is not None else None
        )
        expected_hash = probe.options[probe.expected_index].arguments[0].content_hash
        rows.append(
            {
                **identity,
                "probe_id": probe.probe_id,
                "family_id": probe.family_id,
                "mechanism": probe.mechanism,
                "level": probe.level,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind,
                "expected_index": probe.expected_index,
                "parsed_index": selected,
                "selected_hash": selected_hash,
                "expected_hash": expected_hash,
                "correct": selected_hash == expected_hash,
                "context_status": status,
                "prompt_chars": len(prompt),
                "raw_output": raw["response"],
                "cache_hit": hit,
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "latency_seconds": raw.get("total_duration_ns", 0) / 1e9,
                "error": raw.get("error"),
            }
        )
        if progress is not None:
            progress(index + 1, len(probes))
    return {
        "candidate_id": genome.candidate_id,
        "genome": genome.to_dict(),
        "summary": summarize(rows),
        "rows": rows,
        "calls": len(rows),
        "cache_hits": sum(row["cache_hit"] for row in rows),
    }


# ------------------------------------------------------------------ summaries, audits


def summarize(rows: Sequence[dict[str, Any]], q0_rate: float = 1.0) -> dict[str, Any]:
    base = [row for row in rows if row["variant"] in POSITIVE_VARIANTS]
    negative = [row for row in rows if row["truth_kind"] == "NEGATIVE_CONTROL_TARGET"]
    swapped = [row for row in rows if row["variant"] in SWAPPED_VARIANTS]

    def accuracy(values: Sequence[dict[str, Any]]) -> float:
        return sum(row["correct"] for row in values) / len(values) if values else 0.0

    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_family[row["family_id"]][row["variant"]] = row
    flips = choice_flips = invariant = invariant_pairs = negative_consistent = 0
    for variants in by_family.values():
        original, counter = variants.get("ORIGINAL"), variants.get("COUNTERFACTUAL")
        if original and counter:
            choice_flips += bool(
                original["selected_hash"] is not None
                and counter["selected_hash"] is not None
                and original["selected_hash"] != counter["selected_hash"]
            )
            flips += bool(original["correct"] and counter["correct"])
        neg_a, neg_b = variants.get("DESTROYED_ORIGINAL"), variants.get("DESTROYED_COUNTERFACTUAL")
        if neg_a and neg_b:
            negative_consistent += bool(neg_a["parsed_index"] == neg_b["parsed_index"])
        for name, swap in (
            ("ORIGINAL", "SWAPPED_ORIGINAL"),
            ("COUNTERFACTUAL", "SWAPPED_COUNTERFACTUAL"),
        ):
            left, right = variants.get(name), variants.get(swap)
            if left and right:
                invariant_pairs += 1
                invariant += bool(
                    left["selected_hash"] is not None
                    and left["selected_hash"] == right["selected_hash"]
                )
    family_count = len(by_family)
    positive_accuracy = accuracy(base)
    negative_accuracy = accuracy(negative)
    return {
        "q0_valid_rate": q0_rate,
        "positive_accuracy": positive_accuracy,
        "negative_target_accuracy": negative_accuracy,
        "positive_negative_gap": positive_accuracy - negative_accuracy,
        "semantic_flip_consistency": flips / family_count if family_count else 0.0,
        "choice_flip_rate": choice_flips / family_count if family_count else 0.0,
        "position_invariance": invariant / invariant_pairs if invariant_pairs else 0.0,
        "negative_twin_consistency": negative_consistent / family_count if family_count else 0.0,
        "valid_response_rate": sum(row["parsed_index"] is not None for row in rows) / len(rows)
        if rows
        else 0.0,
        "context_truncated_rows": sum(row["context_status"] != "OK" for row in rows),
        "mechanisms": sorted({row["mechanism"] for row in rows}),
        "families": family_count,
        "positive_examples": len(base),
        "negative_examples": len(negative),
        "swapped_examples": len(swapped),
        "mean_prompt_tokens": sum(row["prompt_tokens"] for row in rows) / len(rows)
        if rows
        else 0.0,
    }


def shortcut_audit(probes: Sequence[V4Probe]) -> dict[str, Any]:
    """Dumb rules over the representation-neutral canonical text; run before inference.

    Adapted from HML_V3 ``src/hml_v3/micromath/shortcut_v2.py``.  Rules read the option
    strings and the canonical state text only; any rule that beats chance measures a
    construction defect, not a representation.
    """

    positives = [probe for probe in probes if probe.variant.value in POSITIVE_VARIANTS]
    if not positives:
        return {"items": 0, "status": "EMPTY"}

    def texts(probe: V4Probe) -> tuple[str, str, str]:
        state_text = canonical_json(probe.state.to_dict(include_display_identity=False))
        previous_text = (
            canonical_json(probe.previous_state.to_dict(include_display_identity=False))
            if probe.previous_state
            else ""
        )
        return state_text, previous_text, state_text + previous_text

    def names(probe: V4Probe) -> tuple[str, str]:
        return (str(probe.options[0].arguments[0].value), str(probe.options[1].arguments[0].value))

    def first_mentioned(probe: V4Probe) -> int:
        text = texts(probe)[0]
        left, right = names(probe)
        return 0 if text.find(f'"{left}"') <= text.find(f'"{right}"') else 1

    def last_mentioned(probe: V4Probe) -> int:
        text = texts(probe)[0]
        left, right = names(probe)
        return 0 if text.rfind(f'"{left}"') >= text.rfind(f'"{right}"') else 1

    def more_frequent(probe: V4Probe) -> int:
        text = texts(probe)[0]
        left, right = names(probe)
        return 0 if text.count(f'"{left}"') >= text.count(f'"{right}"') else 1

    def shorter(probe: V4Probe) -> int:
        left, right = names(probe)
        return 0 if (len(left), left) <= (len(right), right) else 1

    def alphabetical(probe: V4Probe) -> int:
        left, right = names(probe)
        return 0 if left <= right else 1

    rules: dict[str, Callable[[V4Probe], int]] = {
        "always_first_option": lambda probe: 0,
        "always_second_option": lambda probe: 1,
        "first_mentioned_in_state": first_mentioned,
        "last_mentioned_in_state": last_mentioned,
        "more_frequent_in_state": more_frequent,
        "shorter_option_text": shorter,
        "alphabetically_first": alphabetical,
    }
    scores = {
        name: sum(rule(probe) == probe.expected_index for probe in positives) / len(positives)
        for name, rule in rules.items()
    }
    answers = Counter(probe.expected_index for probe in positives)
    # A rule at 0% is the same leak as one at 100%: its negation reads nothing either.
    worst = max(scores, key=lambda name: abs(scores[name] - 0.5))
    worst_score = max(scores[worst], 1.0 - scores[worst])
    return {
        "items": len(positives),
        "answer_share_index_0": answers[0] / len(positives),
        "scores": scores,
        "worst_rule": worst,
        "worst_score": worst_score,
        "status": "CLEAN"
        if worst_score <= float(QUALIFICATION_RULE["shortcut_rule_max"])
        else "LEAKS",
    }


def _positive_accuracy(rows: Sequence[dict[str, Any]]) -> float:
    positives = [row for row in rows if row["variant"] in POSITIVE_VARIANTS]
    return sum(row["correct"] for row in positives) / len(positives) if positives else 0.0


def select_frontier_level(level_accuracies: dict[int, float]) -> dict[str, Any]:
    """Preregistered DEV-only selection.  Level 0 is the explicit positive, never selected."""

    rule = QUALIFICATION_RULE
    explicit = level_accuracies.get(0, 0.0)
    if explicit < float(rule["explicit_positive_min"]):
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
        }
    candidates = [(level, acc) for level, acc in sorted(level_accuracies.items()) if level >= 1]
    if not candidates:
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
        }
    level, accuracy = min(
        candidates, key=lambda item: (abs(item[1] - float(rule["frontier_target"])), item[0])
    )
    low, high = rule["frontier_band"]
    if accuracy > high:
        verdict = "VOID_CEILING"
    elif accuracy < low:
        verdict = "VOID_FLOOR"
    else:
        verdict = "FRONTIER_SELECTED"
    return {
        "selected_level": level if verdict == "FRONTIER_SELECTED" else None,
        "candidate_level": level,
        "candidate_accuracy": accuracy,
        "verdict": verdict,
        "explicit_positive_accuracy": explicit,
    }


def qualify_mechanism(
    summary: dict[str, Any], audit: dict[str, Any], q0_rate: float
) -> dict[str, Any]:
    rule = QUALIFICATION_RULE
    checks = {
        "q0": ("PASS" if q0_rate >= float(rule["q0_valid_rate_min"]) else "VOID_VALIDITY"),
        "valid_response": (
            "PASS"
            if summary["valid_response_rate"] >= float(rule["valid_response_rate_min"])
            else "VOID_VALIDITY"
        ),
        "context": (
            "PASS"
            if summary["context_truncated_rows"] <= int(rule["context_truncated_rows_max"])
            else "VOID_CONTEXT"
        ),
        "negative_collapse": (
            "PASS"
            if summary["positive_negative_gap"] >= float(rule["positive_negative_gap_min"])
            and summary["negative_target_accuracy"] <= float(rule["negative_target_accuracy_max"])
            else "VOID_NEGATIVE_CONTROL"
        ),
        "semantic_flip": (
            "PASS"
            if summary["semantic_flip_consistency"] >= float(rule["semantic_flip_min"])
            and summary["choice_flip_rate"] >= float(rule["choice_flip_min"])
            else "VOID_FLIP"
        ),
        "position_invariance": (
            "PASS"
            if summary["position_invariance"] >= float(rule["position_invariance_min"])
            else "VOID_POSITION"
        ),
        "shortcut": "PASS" if audit.get("status") == "CLEAN" else "VOID_SHORTCUT",
    }
    failures = [code for code in checks.values() if code != "PASS"]
    return {
        "checks": checks,
        "qualified": not failures,
        "verdict": failures[0] if failures else "QUALIFIED",
    }


# -------------------------------------------------------------------- DEV and freeze


def _q0(root: Path) -> dict[str, Any]:
    rows = []
    for index in range(8):
        expected = "A" if index % 2 == 0 else "B"
        prompt = f'This is only a format check. Return exactly {{"choice":"{expected}"}} and nothing else.\nANSWER:'
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "kind": "Q0",
            "model_digest": QUALIFIED_MODEL["digest"],
            "runtime_hash": RUNTIME_CONFIG_HASH,
            "case": index,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, prompt)
        parsed = parse_response(raw["response"])
        rows.append(
            {
                **identity,
                "expected": expected,
                "parsed": parsed,
                "correct": parsed == (0 if expected == "A" else 1),
                "raw_output": raw["response"],
                "cache_hit": hit,
            }
        )
    return {"rate": sum(row["correct"] for row in rows) / len(rows), "rows": rows}


def _log(message: str) -> None:
    print(f"[fitness_v4 {time.strftime('%H:%M:%S')}] {message}", flush=True)


def run_development(root: Path) -> dict[str, Any]:
    """Ladder positives, frontier selection, full-family qualification: control only."""

    control = equal_information_genome()
    q0 = _q0(root)
    _log(f"Q0 valid rate {q0['rate']:.3f}")
    ladder_rows: list[dict[str, Any]] = []
    mechanism_reports: dict[str, Any] = {}
    selected: dict[str, int] = {}
    total_calls = len(q0["rows"])
    for mechanism in MECHANISMS:
        level_accuracies: dict[int, float] = {}
        level_rows: dict[int, list[dict[str, Any]]] = {}
        for level in range(len(LADDERS[mechanism])):
            probes = [
                probe
                for probe in build_dev_pool((mechanism,), (level,))
                if probe.variant.value in POSITIVE_VARIANTS
            ]
            result = evaluate(root, control, probes)
            total_calls += result["calls"]
            level_rows[level] = result["rows"]
            level_accuracies[level] = _positive_accuracy(result["rows"])
            truncated = sum(row["context_status"] != "OK" for row in result["rows"])
            _log(
                f"{mechanism} L{level} positives {level_accuracies[level]:.3f} "
                f"({len(probes)} rows, {truncated} over budget, "
                f"mean prompt tokens {result['summary']['mean_prompt_tokens']:.0f})"
            )
            ladder_rows.extend(result["rows"])
        selection = select_frontier_level(level_accuracies)
        report: dict[str, Any] = {
            "ladder": [
                {
                    "level": level,
                    "parameters": LADDERS[mechanism][level],
                    "positive_accuracy": acc,
                    "context_truncated_rows": sum(
                        row["context_status"] != "OK" for row in level_rows[level]
                    ),
                }
                for level, acc in sorted(level_accuracies.items())
            ],
            "selection": selection,
        }
        if selection["selected_level"] is not None:
            level = int(selection["selected_level"])
            full = build_dev_pool((mechanism,), (level,))
            result = evaluate(root, control, full)
            total_calls += sum(not row["cache_hit"] for row in result["rows"])
            audit = shortcut_audit(full)
            qualification = qualify_mechanism(result["summary"], audit, q0["rate"])
            report.update(
                {
                    "selected_level": level,
                    "full_family_summary": result["summary"],
                    "shortcut_audit": audit,
                    "qualification": qualification,
                    "rows": result["rows"],
                }
            )
            _log(f"{mechanism} L{level} qualification: {qualification['verdict']}")
            if qualification["qualified"]:
                selected[mechanism] = level
        else:
            report.update(
                {
                    "selected_level": None,
                    "qualification": {"qualified": False, "verdict": selection["verdict"]},
                }
            )
            _log(f"{mechanism} {selection['verdict']}")
        mechanism_reports[mechanism] = report
    pool_hash = stable_hash([probe.to_dict() for probe in build_dev_pool()])
    payload = {
        "schema_version": "arena-fitness-v4-development-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "control_candidate": control.candidate_id,
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "context_guard": CONTEXT_GUARD,
        "qualification_rule": QUALIFICATION_RULE,
        "promotion_rule": PROMOTION_RULE,
        "ladders": {name: list(levels) for name, levels in LADDERS.items()},
        "q0": q0,
        "dev_pool_hash": pool_hash,
        "mechanisms": mechanism_reports,
        "qualified_mechanisms": sorted(selected),
        "selected_levels": selected,
        "instrument_qualified": len(selected)
        >= int(QUALIFICATION_RULE["minimum_qualified_mechanisms"]),
        "ladder_rows": ladder_rows,
        "model_calls_recorded": total_calls,
    }
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v4/development/result.json", payload
    )
    return payload


def freeze_from_development(root: Path) -> dict[str, Any]:
    development_path = root / "artifacts/experiments/fitness_v4/development/result.json"
    if not development_path.exists():
        raise RuntimeError("V4 development result is absent")
    development = json.loads(development_path.read_text())
    selected = {str(key): int(value) for key, value in development["selected_levels"].items()}
    qualified = bool(development["instrument_qualified"])
    founders = founder_genomes()
    scout = build_scout_pool(selected) if qualified else ()
    parity = {probe.probe_id: assert_information_parity(probe, founders) for probe in scout}
    audit = shortcut_audit(scout) if scout else {"items": 0, "status": "EMPTY"}
    positives = sum(probe.variant.value in POSITIVE_VARIANTS for probe in scout)
    minimum_net_wins = max(4, math.ceil(0.075 * positives))
    payload = {
        "schema_version": "arena-fitness-v4-frozen-manifest-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "selection_source": "DEV_ONLY",
        "development_result_hash": stable_hash(development),
        "qualified": qualified,
        "qualified_mechanisms": sorted(selected),
        "selected_levels": selected,
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "context_guard": CONTEXT_GUARD,
        "response_protocol": RESPONSE_PROTOCOL,
        "qualification_rule": QUALIFICATION_RULE,
        "promotion_rule": PROMOTION_RULE,
        "founder_roster": [genome.to_dict() for genome in founders],
        "information_parity_prompt_hashes": parity,
        "scout_shortcut_audit": audit,
        "power_sensitivity": {
            "positive_pairs_per_candidate": positives,
            "minimum_net_wins": minimum_net_wins,
            "exact_sign_test_min_all_win_discordances_at_alpha_0_05": 5,
            "warning": "SCOUT detects large paired effects only; non-significance is not equivalence",
        },
        "probes": [probe.to_dict() for probe in scout],
    }
    payload["manifest_hash"] = stable_hash(payload)
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v4/frozen_manifest.json", payload
    )
    if not qualified:
        ArtifactStore(root / "artifacts").write_json(
            "experiments/fitness_v4/not_qualified.json",
            {
                "experiment_version": EXPERIMENT_VERSION,
                "sentinel": "FITNESS_V4_NOT_QUALIFIED",
                "qualified_mechanisms": sorted(selected),
                "reason": "fewer than the preregistered minimum of qualified mechanisms",
            },
        )
    return payload


def load_frozen(root: Path) -> tuple[dict[str, Any], tuple[V4Probe, ...]]:
    raw = json.loads((root / "artifacts/experiments/fitness_v4/frozen_manifest.json").read_text())
    expected = stable_hash({key: value for key, value in raw.items() if key != "manifest_hash"})
    if raw["manifest_hash"] != expected:
        raise ValueError("V4 frozen manifest hash mismatch")
    if not raw["qualified"]:
        raise RuntimeError("V4 did not qualify on DEV")
    if raw["scout_shortcut_audit"].get("status") != "CLEAN":
        raise RuntimeError("V4 SCOUT shortcut audit is not clean")
    probes = tuple(_probe_from_dict(item) for item in raw["probes"])
    for family in {probe.family_id for probe in probes}:
        validate_probe_family(tuple(probe for probe in probes if probe.family_id == family))
    return raw, probes


# ----------------------------------------------------------------- founder tournament


def clustered_paired_bootstrap(
    deltas: Sequence[float],
    clusters: Sequence[str],
    *,
    seed: int = EXPERIMENT_SEED,
    resamples: int = 4000,
) -> tuple[float, float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        grouped[cluster].append(index)
    ids = sorted(grouped)
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(resamples):
        chosen = [index for _ in ids for index in grouped[rng.choice(ids)]]
        draws.append(sum(deltas[index] for index in chosen) / len(chosen))
    draws.sort()
    return draws[max(0, int(0.025 * resamples))], draws[
        min(resamples - 1, int(0.975 * resamples) - 1)
    ]


def paired_against(
    candidate: dict[str, Any], baseline: dict[str, Any], common: set[str]
) -> dict[str, Any]:
    baseline_by_probe = {
        row["probe_id"]: row for row in baseline["rows"] if row["variant"] in POSITIVE_VARIANTS
    }
    rows = sorted(
        (
            row
            for row in candidate["rows"]
            if row["variant"] in POSITIVE_VARIANTS and row["probe_id"] in common
        ),
        key=lambda row: row["probe_id"],
    )
    wins = sum(row["correct"] and not baseline_by_probe[row["probe_id"]]["correct"] for row in rows)
    losses = sum(
        not row["correct"] and baseline_by_probe[row["probe_id"]]["correct"] for row in rows
    )
    deltas = [
        float(row["correct"]) - float(baseline_by_probe[row["probe_id"]]["correct"]) for row in rows
    ]
    clusters = [row["family_id"] for row in rows]
    interval = clustered_paired_bootstrap(deltas, clusters) if rows else (0.0, 0.0)
    by_mechanism: dict[str, dict[str, int]] = {}
    for row in rows:
        entry = by_mechanism.setdefault(row["mechanism"], {"wins": 0, "losses": 0, "ties": 0})
        base_correct = baseline_by_probe[row["probe_id"]]["correct"]
        if row["correct"] and not base_correct:
            entry["wins"] += 1
        elif base_correct and not row["correct"]:
            entry["losses"] += 1
        else:
            entry["ties"] += 1
    delta = sum(deltas) / len(deltas) if deltas else 0.0
    return {
        "positives": len(rows),
        "wins": wins,
        "losses": losses,
        "ties": len(rows) - wins - losses,
        "net_wins": wins - losses,
        "exact_sign_pvalue_one_sided": exact_sign_pvalue(wins, losses),
        "exact_sign_pvalue_one_sided_losses": exact_sign_pvalue(losses, wins),
        "paired_delta": delta,
        "paired_delta_ci95": list(interval),
        "practical_effect": abs(delta) >= float(PROMOTION_RULE["practical_effect_min"]),
        "practically_equivalent": (
            interval[0] >= -float(PROMOTION_RULE["practical_equivalence_region"])
            and interval[1] <= float(PROMOTION_RULE["practical_equivalence_region"])
        ),
        "by_mechanism": by_mechanism,
        "candidate_accuracy": sum(row["correct"] for row in rows) / len(rows) if rows else 0.0,
        "baseline_accuracy": sum(baseline_by_probe[row["probe_id"]]["correct"] for row in rows)
        / len(rows)
        if rows
        else 0.0,
    }


def holm_decisions(
    comparisons: dict[str, dict[str, Any]], key: str = "exact_sign_pvalue_one_sided"
) -> None:
    ordered = sorted(comparisons.items(), key=lambda item: item[1][key])
    family_size = len(ordered)
    rejected_so_far = True
    for index, (candidate_id, comparison) in enumerate(ordered):
        threshold = 0.05 / (family_size - index)
        rejected = bool(rejected_so_far and comparison[key] <= threshold)
        comparisons[candidate_id]["holm_threshold"] = threshold
        comparisons[candidate_id]["holm_reject"] = rejected
        rejected_so_far = rejected


def run_founder_tournament(root: Path, frozen_commit: str) -> dict[str, Any]:
    manifest, probes = load_frozen(root)
    founders = founder_genomes()
    results = []
    for genome in founders:
        _log(f"founder {genome.candidate_id}: {len(probes)} probes")
        candidate_id = genome.candidate_id

        def progress(done: int, total: int, cid: str = candidate_id) -> None:
            if done % 48 == 0 or done == total:
                _log(f"  {cid} {done}/{total}")

        result = evaluate(root, genome, probes, progress=progress)
        _log(
            f"  {genome.candidate_id} positives {result['summary']['positive_accuracy']:.3f} "
            f"valid {result['summary']['valid_response_rate']:.3f} "
            f"over budget {result['summary']['context_truncated_rows']}"
        )
        results.append(result)
    by_id = {result["candidate_id"]: result for result in results}
    baseline_id = str(PROMOTION_RULE["baseline"])
    # Any probe over budget for any candidate is void for every candidate.
    voided = {
        row["probe_id"]
        for result in results
        for row in result["rows"]
        if row["context_status"] != "OK"
    }
    common = {probe.probe_id for probe in probes} - voided
    comparisons = {
        candidate_id: paired_against(result, by_id[baseline_id], common)
        for candidate_id, result in by_id.items()
        if candidate_id != baseline_id
    }
    holm_decisions(comparisons)
    positives = comparisons[next(iter(comparisons))]["positives"] if comparisons else 0
    minimum_net_wins = max(4, math.ceil(0.075 * positives))
    baseline_flip = float(by_id[baseline_id]["summary"]["semantic_flip_consistency"])
    promoted = []
    for candidate_id, comparison in comparisons.items():
        summary = by_id[candidate_id]["summary"]
        checks = {
            "valid_response": float(summary["valid_response_rate"])
            >= float(PROMOTION_RULE["valid_response_rate_min"]),
            "minimum_net_wins": int(comparison["net_wins"]) >= minimum_net_wins,
            "holm_significant": bool(comparison["holm_reject"]),
            "semantic_flip_noninferior": float(summary["semantic_flip_consistency"]) - baseline_flip
            >= float(PROMOTION_RULE["semantic_flip_noninferiority"]),
            "practical_effect": float(comparison["paired_delta"])
            >= float(PROMOTION_RULE["practical_effect_min"]),
        }
        comparison["promotion_checks"] = checks
        comparison["promoted"] = all(checks.values())
        if comparison["promoted"]:
            promoted.append(candidate_id)
    penalised = sorted(
        candidate_id
        for candidate_id, comparison in comparisons.items()
        if comparison["paired_delta_ci95"][1] < 0.0
    )
    per_mechanism = {
        mechanism: {
            candidate_id: sum(
                row["correct"]
                for row in result["rows"]
                if row["mechanism"] == mechanism
                and row["variant"] in POSITIVE_VARIANTS
                and row["probe_id"] in common
            )
            / max(
                1,
                sum(
                    row["mechanism"] == mechanism
                    and row["variant"] in POSITIVE_VARIANTS
                    and row["probe_id"] in common
                    for row in result["rows"]
                ),
            )
            for candidate_id, result in by_id.items()
        }
        for mechanism in manifest["qualified_mechanisms"]
    }
    accuracies = {
        candidate_id: comparison["candidate_accuracy"]
        for candidate_id, comparison in comparisons.items()
    }
    accuracies[baseline_id] = (
        next(iter(comparisons.values()))["baseline_accuracy"] if comparisons else 0.0
    )
    if promoted:
        sentinel = "GAME_R_FOUNDER_SIGNAL_FOUND"
    elif penalised:
        sentinel = "GAME_R_FOUNDER_PENALTY_ONLY"
    else:
        sentinel = "GAME_R_NO_MEASURABLE_SIGNAL"
    payload = {
        "schema_version": "arena-fitness-v4-founder-tournament-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "frozen_instrument_commit": frozen_commit,
        "frozen_manifest_hash": manifest["manifest_hash"],
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "roster": [genome.to_dict() for genome in founders],
        "voided_probe_ids": sorted(voided),
        "common_probe_count": len(common),
        "summaries": {candidate_id: result["summary"] for candidate_id, result in by_id.items()},
        "paired_vs_json_control": comparisons,
        "per_mechanism_positive_accuracy": per_mechanism,
        "promotion_rule": {**PROMOTION_RULE, "minimum_net_wins_resolved": minimum_net_wins},
        "promoted": sorted(promoted),
        "penalised_vs_control": penalised,
        "accuracy_range": max(accuracies.values()) - min(accuracies.values())
        if accuracies
        else 0.0,
        "calls": sum(result["calls"] for result in results),
        "cache_hits": sum(result["cache_hits"] for result in results),
        "sentinel": sentinel,
        "candidate_results": results,
    }
    payload["result_hash"] = stable_hash(payload)
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v4/founders/result.json", payload
    )
    return payload


def experiment_status_v4(root: Path) -> dict[str, Any]:
    base = root / "artifacts/experiments/fitness_v4"
    founder_path = base / "founders/result.json"
    manifest_path = base / "frozen_manifest.json"
    development_path = base / "development/result.json"
    if founder_path.exists():
        founder = json.loads(founder_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": founder["sentinel"],
            "promoted": founder["promoted"],
            "penalised_vs_control": founder["penalised_vs_control"],
            "mutation_campaign_authorized": bool(
                founder["promoted"] or founder["penalised_vs_control"]
            ),
            "matched_learning_authorized": False,
            "rstar_authorized": False,
        }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": "FITNESS_V4_QUALIFIED"
            if manifest["qualified"]
            else "FITNESS_V4_NOT_QUALIFIED",
            "qualified_mechanisms": manifest["qualified_mechanisms"],
        }
    if development_path.exists():
        development = json.loads(development_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": "FITNESS_V4_DEV_COMPLETE_NOT_FROZEN",
            "qualified_mechanisms": development["qualified_mechanisms"],
        }
    return {"experiment_version": EXPERIMENT_VERSION, "sentinel": "FITNESS_V4_NOT_QUALIFIED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("materialize", "develop", "freeze", "founders", "status")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--frozen-commit", type=str, default="UNRECORDED")
    args = parser.parse_args()
    if args.command == "materialize":
        probes = build_dev_pool()
        print(
            canonical_json(
                {
                    "families": len(probes) // 6,
                    "probes": len(probes),
                    "hash": stable_hash([probe.to_dict() for probe in probes]),
                    "shortcut_audit": shortcut_audit(probes),
                }
            )
        )
    elif args.command == "develop":
        result = run_development(args.root)
        print(
            canonical_json(
                {
                    "qualified_mechanisms": result["qualified_mechanisms"],
                    "selected_levels": result["selected_levels"],
                    "instrument_qualified": result["instrument_qualified"],
                }
            )
        )
    elif args.command == "freeze":
        result = freeze_from_development(args.root)
        print(
            canonical_json(
                {
                    "manifest_hash": result["manifest_hash"],
                    "qualified": result["qualified"],
                    "probes": len(result["probes"]),
                }
            )
        )
    elif args.command == "founders":
        result = run_founder_tournament(args.root, args.frozen_commit)
        print(
            canonical_json(
                {
                    "result_hash": result["result_hash"],
                    "sentinel": result["sentinel"],
                    "promoted": result["promoted"],
                    "penalised": result["penalised_vs_control"],
                    "calls": result["calls"],
                }
            )
        )
    else:
        print(canonical_json(experiment_status_v4(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
