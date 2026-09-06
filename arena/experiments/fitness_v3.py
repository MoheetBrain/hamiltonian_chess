"""Fitness V3: structural-frontier qualification for model-view genomes.

V3 is independent of V2.  It uses freshly generated relational mechanisms, destructive
negative controls, position swaps, and an absolute DEV-only selection rule.  Candidate
evaluation consumes a frozen manifest written before any founder/evolved-candidate calls.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
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
from arena.experiments.fitness_v2 import QUALIFIED_MODEL, RUNTIME_CONFIG
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.storage.artifacts import ArtifactStore
from arena.verifier.native import NativeVerifier

EXPERIMENT_VERSION = "arena-representation-fitness-v3"
INSTRUMENT_VERSION = "arena-structural-frontier-instrument-v3.0.0"
EXPERIMENT_SEED = 20260906
RUNTIME_CONFIG_HASH = stable_hash(RUNTIME_CONFIG)
RESPONSE_PROTOCOL = "JSON_AB"
MECHANISMS = (
    "dependency_chain",
    "action_goal_assignment",
    "premise_attribution",
    "obligation_ownership",
    "state_delta",
    "evidence_provenance",
)
QUALIFICATION_RULE = {
    "q0_valid_rate_min": 0.95,
    "positive_accuracy_min": 0.40,
    "positive_accuracy_max": 0.85,
    "positive_negative_gap_min": 0.10,
    "semantic_flip_min": 0.50,
    "position_invariance_min": 0.60,
    "mechanisms_represented_min": 6,
    "selection": (
        "DEV only; select one complexity per mechanism by distance to 0.625 positive accuracy, "
        "then freeze independent SCOUT families with the same mechanism/complexity"
    ),
}
PROMOTION_RULE = {
    "valid_response_rate_min": 0.95,
    "paired_test": "one-sided exact sign test on discordant positive outcomes",
    "paired_p_max": 0.05,
    "minimum_net_wins": 4,
    "semantic_flip_noninferiority": -0.05,
    "familywise_policy": "Holm correction across promoted candidates",
    "preregistered_note": "No fixed 15 percentage-point range or advantage is required.",
}


class V3Slice(StrEnum):
    DEV = "DEV"
    SCOUT = "SCOUT"
    PROMOTION = "PROMOTION"
    OOD = "OOD"


class V3Variant(StrEnum):
    ORIGINAL = "ORIGINAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DESTROYED_ORIGINAL = "DESTROYED_ORIGINAL"
    DESTROYED_COUNTERFACTUAL = "DESTROYED_COUNTERFACTUAL"
    SWAPPED_ORIGINAL = "SWAPPED_ORIGINAL"
    SWAPPED_COUNTERFACTUAL = "SWAPPED_COUNTERFACTUAL"


@dataclass(frozen=True, slots=True)
class V3Probe:
    probe_id: str
    family_id: str
    slice_name: V3Slice
    mechanism: str
    complexity: int
    variant: V3Variant
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
            "complexity": self.complexity,
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


def _atom(value: str) -> CanonicalExpression:
    return CanonicalExpression("symbol", value=value, sort="Identifier")


def _relation(name: str, *values: str) -> CanonicalExpression:
    return CanonicalExpression(name, tuple(_atom(value) for value in values), sort="Proposition")


def _distractors(prefix: str, count: int) -> tuple[MathObject, ...]:
    return tuple(
        MathObject(
            f"object:{prefix}:{index:02d}",
            "Distractor",
            _relation("tag", prefix, f"value:{(index * 7 + 3) % 29}"),
        )
        for index in range(count)
    )


def _state(
    *,
    goal: CanonicalExpression,
    facts: tuple[CanonicalExpression, ...] = (),
    assumptions: tuple[CanonicalExpression, ...] = (),
    objects: tuple[MathObject, ...] = (),
    obligations: tuple[Obligation, ...] = (),
    evidence: tuple[EvidenceNode, ...] = (),
    local_scope: tuple[str, ...] = ("scope:root",),
    terminal_status: str = "OPEN",
) -> CanonicalState:
    return CanonicalState(
        state_id="state:fitness-v3:neutral",
        objects=objects,
        bindings=(),
        assumptions=assumptions,
        established_facts=facts,
        propositions=(),
        goal=goal,
        obligations=obligations,
        evidence_dependencies=evidence,
        local_scope=local_scope,
        legal_actions=(),
        plausible_invalid_actions=(),
        terminal_status=terminal_status,
        execution_metadata=(),
    )


def _option(index: int, answer: str, alternate: str) -> CanonicalAction:
    premise = _relation("requires", answer)
    obligation = Obligation(f"obligation:option:{index}", _relation("prove", answer), source=answer)
    return CanonicalAction(
        action_id=f"option:{index}",
        operation="propose_structural_answer",
        target_ids=(f"object:answer:{answer}",),
        arguments=(_atom(answer),),
        warrant=f"evidence-authority:{answer}",
        preconditions=(premise, _relation("exclude", alternate)),
        generated_obligations=(obligation,),
        expected_usefulness=0.0,
    )


def _mechanism_states(
    mechanism: str, complexity: int, salt: int
) -> tuple[
    CanonicalState,
    CanonicalState,
    CanonicalState,
    CanonicalState | None,
    CanonicalState | None,
    CanonicalState | None,
    str,
    str,
    str,
]:
    left = f"answer:{salt}:left"
    right = f"answer:{salt}:right"
    answer_objects = (
        MathObject(f"object:answer:{left}", "AnswerTarget", _atom(left)),
        MathObject(f"object:answer:{right}", "AnswerTarget", _atom(right)),
    )
    objects = (*answer_objects, *_distractors(str(salt), 8 + complexity * 8))
    empty_goal = _relation("relation_destroyed", "query")
    previous_a: CanonicalState | None = None
    previous_b: CanonicalState | None = None
    previous_destroyed: CanonicalState | None = None

    if mechanism == "dependency_chain":
        depth = 3 + complexity * 2

        def chain(parent: str) -> tuple[EvidenceNode, ...]:
            nodes = [EvidenceNode("e:root", "VERIFIED")]
            for index in range(1, depth):
                nodes.append(EvidenceNode(f"e:{index}", "VERIFIED", (nodes[-1].evidence_id,)))
            nodes.append(EvidenceNode("e:leaf", "UNKNOWN", (parent,), "arena-native", None))
            return tuple(nodes)

        anchor = f"e:{depth - 1}"
        evidence_a = chain(anchor)
        evidence_b = tuple(
            [*chain(anchor)[:-1], EvidenceNode("e:alternate", "VERIFIED")]
            + [EvidenceNode("e:leaf", "UNKNOWN", ("e:alternate",), "arena-native", None)]
        )
        # Remove the former leaf before appending the alternate branch.
        evidence_b = tuple(node for node in evidence_b if node.evidence_id != "e:leaf") + (
            EvidenceNode("e:leaf", "UNKNOWN", ("e:alternate",), "arena-native", None),
        )
        a, b = anchor, "e:alternate"
        question = "Which evidence ID is the direct dependency of e:leaf?"
        original = _state(
            goal=_relation("dependency_of", "e:leaf"),
            objects=objects,
            evidence=evidence_a,
            local_scope=("e:leaf",),
        )
        counter = _state(
            goal=_relation("dependency_of", "e:leaf"),
            objects=objects,
            evidence=evidence_b,
            local_scope=("e:leaf",),
        )
        destroyed = _state(
            goal=empty_goal,
            objects=objects,
            evidence=tuple(node for node in evidence_a if node.evidence_id != "e:leaf"),
        )
    elif mechanism == "action_goal_assignment":
        a, b = left, right
        question = "Which answer target is named by the active_goal relation?"
        original = _state(goal=_relation("active_goal", a), objects=objects)
        counter = _state(goal=_relation("active_goal", b), objects=objects)
        destroyed = _state(goal=empty_goal, objects=objects)
    elif mechanism == "premise_attribution":
        a, b = left, right
        question = "Which option has a requires-premise that is present among the assumptions?"
        shared = tuple(
            _relation("irrelevant_premise", f"p:{index}") for index in range(complexity * 5)
        )
        original = _state(
            goal=_relation("select_licensed_option", "query"),
            assumptions=(*shared, _relation("requires", a)),
            objects=objects,
        )
        counter = _state(
            goal=_relation("select_licensed_option", "query"),
            assumptions=(*shared, _relation("requires", b)),
            objects=objects,
        )
        destroyed = _state(goal=empty_goal, assumptions=shared, objects=objects)
    elif mechanism == "obligation_ownership":
        a, b = left, right
        question = "Which owner has the unique OPEN obligation prove(owner)?"

        def owned(owner: str) -> tuple[Obligation, ...]:
            extras = tuple(
                Obligation(
                    f"obligation:closed:{index}",
                    _relation("prove", f"closed:{index}"),
                    "DISCHARGED",
                    f"owner:{index}",
                )
                for index in range(complexity * 4)
            )
            return (
                *extras,
                Obligation("obligation:query", _relation("prove", owner), "OPEN", owner),
            )

        original = _state(
            goal=_relation("open_obligation_owner", "query"), objects=objects, obligations=owned(a)
        )
        counter = _state(
            goal=_relation("open_obligation_owner", "query"), objects=objects, obligations=owned(b)
        )
        destroyed = _state(
            goal=empty_goal,
            objects=objects,
            obligations=tuple(
                item for item in owned(a) if item.obligation_id != "obligation:query"
            ),
        )
    elif mechanism == "state_delta":
        a, b = left, right
        question = (
            "Which answer ID was added to established_facts between PREVIOUS and CURRENT state?"
        )
        base_facts = tuple(
            _relation("retained", f"fact:{index}") for index in range(6 + complexity * 6)
        )
        previous_destroyed = _state(
            goal=_relation("find_added_fact", "query"), facts=base_facts, objects=objects
        )
        previous_a = previous_destroyed
        previous_b = previous_destroyed
        original = _state(
            goal=_relation("find_added_fact", "query"),
            facts=(*base_facts, _relation("added", a)),
            objects=objects,
        )
        counter = _state(
            goal=_relation("find_added_fact", "query"),
            facts=(*base_facts, _relation("added", b)),
            objects=objects,
        )
        destroyed = _state(goal=empty_goal, facts=base_facts, objects=objects)
    elif mechanism == "evidence_provenance":
        a, b = left, right
        question = "Which authority issued the VERIFIED evidence node e:query?"

        def evidence(authority: str) -> tuple[EvidenceNode, ...]:
            extras = tuple(
                EvidenceNode(f"e:distractor:{index}", "UNKNOWN", (), f"authority:{index}")
                for index in range(complexity * 6)
            )
            return (*extras, EvidenceNode("e:query", "VERIFIED", (), authority, f"cert:{salt}"))

        original = _state(
            goal=_relation("authority_of", "e:query"),
            objects=objects,
            evidence=evidence(a),
            local_scope=("e:query",),
        )
        counter = _state(
            goal=_relation("authority_of", "e:query"),
            objects=objects,
            evidence=evidence(b),
            local_scope=("e:query",),
        )
        destroyed = _state(
            goal=empty_goal,
            objects=objects,
            evidence=tuple(item for item in evidence(a) if item.evidence_id != "e:query"),
        )
    else:
        raise ValueError(f"unknown V3 mechanism: {mechanism}")
    return original, counter, destroyed, previous_a, previous_b, previous_destroyed, a, b, question


def derive_probe_family(
    mechanism: str, complexity: int, slice_name: V3Slice, salt: int
) -> tuple[V3Probe, ...]:
    original, counter, destroyed, prev_a, prev_b, prev_destroyed, answer_a, answer_b, question = (
        _mechanism_states(mechanism, complexity, salt)
    )
    options = (_option(0, answer_a, answer_b), _option(1, answer_b, answer_a))
    family_id = f"v3:{slice_name.value.lower()}:{mechanism}:c{complexity}:{salt}"

    def make(
        variant: V3Variant,
        state: CanonicalState,
        previous: CanonicalState | None,
        expected: int,
        truth: str,
        displayed=options,
    ) -> V3Probe:
        identity = {
            "family": family_id,
            "variant": variant.value,
            "state": state.mathematical_hash,
            "options": [item.to_dict() for item in displayed],
        }
        return V3Probe(
            probe_id=f"probe:{stable_hash(identity)[:20]}",
            family_id=family_id,
            slice_name=slice_name,
            mechanism=mechanism,
            complexity=complexity,
            variant=variant,
            state=state,
            previous_state=previous,
            question=question,
            options=displayed,
            expected_index=expected,
            truth_kind=truth,
            oracle_record={
                "rule": mechanism,
                "answer": displayed[expected].arguments[0].to_dict()
                if truth == "MATHEMATICAL"
                else None,
                "generator_salt": salt,
            },
        )

    return (
        make(V3Variant.ORIGINAL, original, prev_a, 0, "MATHEMATICAL"),
        make(V3Variant.COUNTERFACTUAL, counter, prev_b, 1, "MATHEMATICAL"),
        make(V3Variant.DESTROYED_ORIGINAL, destroyed, prev_destroyed, 0, "NEGATIVE_CONTROL_TARGET"),
        make(
            V3Variant.DESTROYED_COUNTERFACTUAL,
            destroyed,
            prev_destroyed,
            1,
            "NEGATIVE_CONTROL_TARGET",
        ),
        make(
            V3Variant.SWAPPED_ORIGINAL,
            original,
            prev_a,
            1,
            "MATHEMATICAL",
            tuple(reversed(options)),
        ),
        make(
            V3Variant.SWAPPED_COUNTERFACTUAL,
            counter,
            prev_b,
            0,
            "MATHEMATICAL",
            tuple(reversed(options)),
        ),
    )


def validate_probe_family(probes: tuple[V3Probe, ...]) -> dict[str, Any]:
    if len(probes) != 6 or len({item.family_id for item in probes}) != 1:
        raise ValueError("V3 family must contain six siblings")
    by_variant = {item.variant: item for item in probes}
    verifier = NativeVerifier()
    for probe in probes:
        result = verifier.verify_state(probe.state)
        if not result.accepted:
            raise ValueError(f"invalid V3 state {probe.probe_id}: {result.issues}")
        if probe.state.legal_actions or probe.state.plausible_invalid_actions:
            raise ValueError("V3 observation leaks action membership")
        if any(option.expected_usefulness != 0.0 for option in probe.options):
            raise ValueError("V3 option leaks oracle usefulness")
    neg_a = by_variant[V3Variant.DESTROYED_ORIGINAL]
    neg_b = by_variant[V3Variant.DESTROYED_COUNTERFACTUAL]
    if (
        neg_a.state.mathematical_hash != neg_b.state.mathematical_hash
        or neg_a.options != neg_b.options
    ):
        raise ValueError("V3 negative siblings are not information-identical")
    if neg_a.expected_index == neg_b.expected_index:
        raise ValueError("V3 negative targets are not balanced")
    for original_name, swapped_name in (
        (V3Variant.ORIGINAL, V3Variant.SWAPPED_ORIGINAL),
        (V3Variant.COUNTERFACTUAL, V3Variant.SWAPPED_COUNTERFACTUAL),
    ):
        base, swapped = by_variant[original_name], by_variant[swapped_name]
        if base.state.mathematical_hash != swapped.state.mathematical_hash:
            raise ValueError("position swap changed V3 state")
        if base.options != tuple(reversed(swapped.options)):
            raise ValueError("position swap changed V3 option set")
        if (
            base.options[base.expected_index].arguments
            != swapped.options[swapped.expected_index].arguments
        ):
            raise ValueError("position swap changed V3 truth")
    return {
        "family_id": probes[0].family_id,
        "valid": True,
        "derived_hashes_unique": len({item.derived_hash for item in probes}) == 6,
    }


def build_pool(slice_name: V3Slice, complexities: tuple[int, ...] = (1, 2)) -> tuple[V3Probe, ...]:
    probes: list[V3Probe] = []
    slice_offset = list(V3Slice).index(slice_name) * 1000
    for mechanism_index, mechanism in enumerate(MECHANISMS):
        for complexity in complexities:
            family = derive_probe_family(
                mechanism,
                complexity,
                slice_name,
                EXPERIMENT_SEED + slice_offset + mechanism_index * 10 + complexity,
            )
            validate_probe_family(family)
            probes.extend(family)
    return tuple(probes)


def _probe_from_dict(raw: dict[str, Any]) -> V3Probe:
    options = tuple(CanonicalAction.from_dict(item) for item in raw["options"])
    if len(options) != 2:
        raise ValueError("frozen V3 probe must contain exactly two options")
    return V3Probe(
        probe_id=str(raw["probe_id"]),
        family_id=str(raw["family_id"]),
        slice_name=V3Slice(raw["slice"]),
        mechanism=str(raw["mechanism"]),
        complexity=int(raw["complexity"]),
        variant=V3Variant(raw["variant"]),
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


def equal_information_genome(surface_id: str = "L3_JSON_AST") -> ModelViewGenome:
    return ModelViewGenome(
        f"V3E_{surface_id}",
        (),
        SearchTrack.EQUAL_INFORMATION,
        SEED_GENOME_BY_ID[surface_id],
        ContentGenome(),
    )


def build_prompt(genome: ModelViewGenome, probe: V3Probe) -> str:
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
        f"{previous}CURRENT STATE AND MODEL VIEW:\n{view.text}\nOPTIONS:\n"
        + "\n".join(rendered_options)
        + "\nANSWER:"
    )


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
    with urlopen(request, timeout=300) as response:  # noqa: S310 - fixed local service
        raw = json.loads(response.read().decode())
    return {
        "response": str(raw.get("response", "")),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "total_duration_ns": int(raw.get("total_duration", 0)),
    }


def _cached_call(root: Path, identity: dict[str, Any], prompt: str) -> tuple[dict[str, Any], bool]:
    path = root / "artifacts/cache/fitness_v3" / f"{stable_hash(identity)}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("identity") != identity or not isinstance(cached.get("result"), dict):
            raise ValueError(f"invalid V3 cache record: {path}")
        return cached["result"], True
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


def summarize(rows: list[dict[str, Any]], q0_rate: float = 1.0) -> dict[str, Any]:
    base = [
        row
        for row in rows
        if row["variant"] in {V3Variant.ORIGINAL.value, V3Variant.COUNTERFACTUAL.value}
    ]
    negative = [row for row in rows if row["truth_kind"] == "NEGATIVE_CONTROL_TARGET"]
    swapped = [
        row
        for row in rows
        if row["variant"]
        in {V3Variant.SWAPPED_ORIGINAL.value, V3Variant.SWAPPED_COUNTERFACTUAL.value}
    ]

    def accuracy(values: list[dict[str, Any]]) -> float:
        return sum(row["correct"] for row in values) / len(values) if values else 0.0

    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_family[row["family_id"]][row["variant"]] = row
    flips = 0
    invariant = 0
    for variants in by_family.values():
        original, counter = variants.get("ORIGINAL"), variants.get("COUNTERFACTUAL")
        flips += bool(
            original
            and counter
            and original["correct"]
            and counter["correct"]
            and original["selected_hash"] != counter["selected_hash"]
        )
        for name, swap in (
            ("ORIGINAL", "SWAPPED_ORIGINAL"),
            ("COUNTERFACTUAL", "SWAPPED_COUNTERFACTUAL"),
        ):
            left, right = variants.get(name), variants.get(swap)
            invariant += bool(
                left
                and right
                and left["selected_hash"] is not None
                and left["selected_hash"] == right["selected_hash"]
            )
    positive_accuracy = accuracy(base)
    negative_accuracy = accuracy(negative)
    family_count = len(by_family)
    summary: dict[str, Any] = {
        "q0_valid_rate": q0_rate,
        "positive_accuracy": positive_accuracy,
        "negative_target_accuracy": negative_accuracy,
        "positive_negative_gap": positive_accuracy - negative_accuracy,
        "semantic_flip_consistency": flips / family_count if family_count else 0.0,
        "position_invariance": invariant / (2 * family_count) if family_count else 0.0,
        "valid_response_rate": sum(row["parsed_index"] is not None for row in rows) / len(rows)
        if rows
        else 0.0,
        "mechanisms": sorted({row["mechanism"] for row in rows}),
        "positive_examples": len(base),
        "negative_examples": len(negative),
        "swapped_examples": len(swapped),
    }
    checks = {
        "q0": q0_rate >= 0.95,
        "above_floor": positive_accuracy >= 0.40,
        "below_ceiling": positive_accuracy <= 0.85,
        "negative_collapse": positive_accuracy - negative_accuracy >= 0.10,
        "semantic_flip": summary["semantic_flip_consistency"] >= 0.50,
        "position_invariance": summary["position_invariance"] >= 0.60,
        "mechanism_coverage": len(summary["mechanisms"]) >= 6,
    }
    summary["checks"] = checks
    summary["qualified"] = all(checks.values())
    return summary


def evaluate(root: Path, genome: ModelViewGenome, probes: tuple[V3Probe, ...]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for probe in probes:
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
        selected = parse_response(raw["response"])
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
                "complexity": probe.complexity,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind,
                "expected_index": probe.expected_index,
                "parsed_index": selected,
                "selected_hash": selected_hash,
                "expected_hash": expected_hash,
                "correct": selected_hash == expected_hash,
                "raw_output": raw["response"],
                "cache_hit": hit,
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "latency_seconds": raw.get("total_duration_ns", 0) / 1e9,
                "error": raw.get("error"),
            }
        )
    return {
        "candidate_id": genome.candidate_id,
        "genome": genome.to_dict(),
        "summary": summarize(rows),
        "rows": rows,
        "calls": len(rows),
        "cache_hits": sum(row["cache_hit"] for row in rows),
    }


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


def run_development(root: Path) -> dict[str, Any]:
    probes = build_pool(V3Slice.DEV)
    q0 = _q0(root)
    result = evaluate(root, equal_information_genome(), probes)
    result["summary"] = summarize(result["rows"], q0["rate"])
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result["rows"]:
        by_family[row["family_id"]].append(row)
    family_summaries = {family: summarize(rows, q0["rate"]) for family, rows in by_family.items()}
    selected: dict[str, int] = {}
    for mechanism in MECHANISMS:
        eligible = [
            (family, summary)
            for family, summary in family_summaries.items()
            if next(row for row in by_family[family])["mechanism"] == mechanism
        ]
        family, _ = min(
            eligible, key=lambda item: (abs(float(item[1]["positive_accuracy"]) - 0.625), item[0])
        )
        selected[mechanism] = int(by_family[family][0]["complexity"])
    payload = {
        "schema_version": "arena-fitness-v3-development-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "qualification_rule": QUALIFICATION_RULE,
        "promotion_rule": PROMOTION_RULE,
        "q0": q0,
        "pool_hash": stable_hash([probe.to_dict() for probe in probes]),
        "pool_families": len(by_family),
        "family_summaries": family_summaries,
        "selected_complexities": selected,
        "aggregate": result["summary"],
        "rows": result["rows"],
    }
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v3/development/result.json", payload
    )
    return payload


def freeze_from_development(root: Path) -> dict[str, Any]:
    development_path = root / "artifacts/experiments/fitness_v3/development/result.json"
    if not development_path.exists():
        raise RuntimeError("V3 development result is absent")
    development = json.loads(development_path.read_text())
    selected = {str(key): int(value) for key, value in development["selected_complexities"].items()}
    dev_selected = tuple(
        probe for probe in build_pool(V3Slice.DEV) if selected[probe.mechanism] == probe.complexity
    )
    qualified_summary = summarize(
        [row for row in development["rows"] if selected[row["mechanism"]] == row["complexity"]],
        development["q0"]["rate"],
    )
    scout = tuple(
        probe
        for probe in build_pool(V3Slice.SCOUT)
        if selected[probe.mechanism] == probe.complexity
    )
    payload = {
        "schema_version": "arena-fitness-v3-frozen-manifest-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "selection_source": "DEV_ONLY",
        "development_result_hash": stable_hash(development),
        "selected_complexities": selected,
        "qualification_summary": qualified_summary,
        "qualified": qualified_summary["qualified"],
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "response_protocol": RESPONSE_PROTOCOL,
        "qualification_rule": QUALIFICATION_RULE,
        "promotion_rule": PROMOTION_RULE,
        "power_sensitivity": {
            "positive_pairs_per_candidate": sum(
                probe.variant in {V3Variant.ORIGINAL, V3Variant.COUNTERFACTUAL} for probe in scout
            ),
            "exact_sign_test_min_all-win_discordances_at_alpha_0_05": 5,
            "warning": "small SCOUT detects only large paired effects; non-significance is not equivalence",
        },
        "probes": [probe.to_dict() for probe in scout],
        "dev_selected_probe_hash": stable_hash([probe.to_dict() for probe in dev_selected]),
    }
    payload["manifest_hash"] = stable_hash(payload)
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v3/frozen_manifest.json", payload
    )
    return payload


def load_frozen(root: Path) -> tuple[dict[str, Any], tuple[V3Probe, ...]]:
    raw = json.loads((root / "artifacts/experiments/fitness_v3/frozen_manifest.json").read_text())
    expected = stable_hash({key: value for key, value in raw.items() if key != "manifest_hash"})
    if raw["manifest_hash"] != expected:
        raise ValueError("V3 frozen manifest hash mismatch")
    if not raw["qualified"]:
        raise RuntimeError("V3 did not qualify on DEV")
    probes = tuple(_probe_from_dict(item) for item in raw["probes"])
    for family in {probe.family_id for probe in probes}:
        validate_probe_family(tuple(probe for probe in probes if probe.family_id == family))
    return raw, probes


def exact_sign_pvalue(wins: int, losses: int) -> float:
    discordant = wins + losses
    if discordant == 0 or wins <= losses:
        return 1.0
    return (
        sum(math.comb(discordant, value) for value in range(wins, discordant + 1)) / 2**discordant
    )


def founder_genomes() -> tuple[ModelViewGenome, ...]:
    """Eight broad Track-E founders and a small one-gene Track-C mini-family."""

    equal = tuple(equal_information_genome(candidate_id) for candidate_id in SEED_GENOME_BY_ID)
    base_content = ContentGenome()
    content_specs = (
        ("V3C_JSON_BASE", (), base_content),
        (
            "V3C_JSON_DEP_EDGE",
            ("V3C_JSON_BASE",),
            base_content.with_gene("dependency_projection", "EXPLICIT_EDGE"),
        ),
        (
            "V3C_JSON_TARGET_BLOCK",
            ("V3C_JSON_BASE",),
            base_content.with_gene("action_goal_projection", "TARGET_BLOCK"),
        ),
        (
            "V3C_JSON_DELTA_CONTEXT",
            ("V3C_JSON_BASE",),
            base_content.with_gene("state_delta_projection", "DELTA_PLUS_CONTEXT"),
        ),
    )
    content = tuple(
        ModelViewGenome(
            candidate_id,
            parents,
            SearchTrack.CONTENT_PROJECTION,
            SEED_GENOME_BY_ID["L3_JSON_AST"],
            genome,
        )
        for candidate_id, parents, genome in content_specs
    )
    return (*equal, *content)


def _positive_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in result["rows"]
        if row["variant"] in {V3Variant.ORIGINAL.value, V3Variant.COUNTERFACTUAL.value}
    ]


def _paired_against(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_by_probe = {row["probe_id"]: row for row in _positive_rows(baseline)}
    candidate_rows = sorted(_positive_rows(candidate), key=lambda row: row["probe_id"])
    wins = sum(
        row["correct"] and not baseline_by_probe[row["probe_id"]]["correct"]
        for row in candidate_rows
    )
    losses = sum(
        not row["correct"] and baseline_by_probe[row["probe_id"]]["correct"]
        for row in candidate_rows
    )
    return {
        "wins": wins,
        "losses": losses,
        "ties": len(candidate_rows) - wins - losses,
        "net_wins": wins - losses,
        "exact_sign_pvalue_one_sided": exact_sign_pvalue(wins, losses),
        "candidate_accuracy": candidate["summary"]["positive_accuracy"],
        "baseline_accuracy": baseline["summary"]["positive_accuracy"],
        "accuracy_delta": candidate["summary"]["positive_accuracy"]
        - baseline["summary"]["positive_accuracy"],
    }


def _holm_decisions(comparisons: dict[str, dict[str, Any]]) -> None:
    ordered = sorted(comparisons.items(), key=lambda item: item[1]["exact_sign_pvalue_one_sided"])
    family_size = len(ordered)
    rejected_so_far = True
    for index, (candidate_id, comparison) in enumerate(ordered):
        threshold = 0.05 / (family_size - index)
        rejected = bool(rejected_so_far and comparison["exact_sign_pvalue_one_sided"] <= threshold)
        comparisons[candidate_id]["holm_threshold"] = threshold
        comparisons[candidate_id]["holm_reject"] = rejected
        rejected_so_far = rejected


def run_founder_tournament(root: Path) -> dict[str, Any]:
    manifest, probes = load_frozen(root)
    frozen_commit = "96166546ab5f0add41f7cf3b6ef58657c1f97747"
    results = [evaluate(root, genome, probes) for genome in founder_genomes()]
    baseline_id = "V3E_L3_JSON_AST"
    by_id = {result["candidate_id"]: result for result in results}
    comparisons = {
        candidate_id: _paired_against(result, by_id[baseline_id])
        for candidate_id, result in by_id.items()
        if candidate_id != baseline_id
    }
    _holm_decisions(comparisons)
    baseline_flip = float(by_id[baseline_id]["summary"]["semantic_flip_consistency"])
    promoted = []
    for candidate_id, comparison in comparisons.items():
        summary = by_id[candidate_id]["summary"]
        checks = {
            "valid_response": float(summary["valid_response_rate"])
            >= cast(float, PROMOTION_RULE["valid_response_rate_min"]),
            "minimum_net_wins": int(comparison["net_wins"])
            >= cast(int, PROMOTION_RULE["minimum_net_wins"]),
            "holm_significant": bool(comparison["holm_reject"]),
            "semantic_flip_noninferior": float(summary["semantic_flip_consistency"]) - baseline_flip
            >= cast(float, PROMOTION_RULE["semantic_flip_noninferiority"]),
        }
        comparison["promotion_checks"] = checks
        comparison["promoted"] = all(checks.values())
        if comparison["promoted"]:
            promoted.append(candidate_id)
    accuracies = {
        candidate_id: float(result["summary"]["positive_accuracy"])
        for candidate_id, result in by_id.items()
    }
    payload = {
        "schema_version": "arena-fitness-v3-founder-tournament-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "frozen_instrument_commit": frozen_commit,
        "frozen_manifest_hash": manifest["manifest_hash"],
        "model": QUALIFIED_MODEL,
        "runtime": RUNTIME_CONFIG,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "roster": [genome.to_dict() for genome in founder_genomes()],
        "summaries": {candidate_id: result["summary"] for candidate_id, result in by_id.items()},
        "paired_vs_json_control": comparisons,
        "promotion_rule": PROMOTION_RULE,
        "promoted": sorted(promoted),
        "accuracy_range": max(accuracies.values()) - min(accuracies.values()),
        "best_accuracy": max(accuracies.values()),
        "worst_accuracy": min(accuracies.values()),
        "calls": sum(result["calls"] for result in results),
        "cache_hits": sum(result["cache_hits"] for result in results),
        "candidate_results": results,
    }
    payload["result_hash"] = stable_hash(payload)
    ArtifactStore(root / "artifacts").write_json(
        "experiments/fitness_v3/founders/result.json", payload
    )
    return payload


def experiment_status_v3(root: Path) -> dict[str, Any]:
    invalidity_path = root / "artifacts/experiments/fitness_v3/invalidity.json"
    founder_path = root / "artifacts/experiments/fitness_v3/founders/result.json"
    manifest_path = root / "artifacts/experiments/fitness_v3/frozen_manifest.json"
    if invalidity_path.exists():
        invalidity = json.loads(invalidity_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": invalidity["sentinel"],
            "reason": invalidity["reason"],
            "tier2a_authorized": False,
            "matched_1k_authorized": False,
        }
    if founder_path.exists():
        founder = json.loads(founder_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": "FITNESS_V3_QUALIFIED_READY_FOR_TIER2A",
            "promoted": founder["promoted"],
        }
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        return {
            "experiment_version": EXPERIMENT_VERSION,
            "sentinel": (
                "FITNESS_V3_QUALIFIED_READY_FOR_TIER2A"
                if manifest["qualified"]
                else "FITNESS_V3_NOT_YET_QUALIFIED"
            ),
        }
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "sentinel": "FITNESS_V3_NOT_YET_QUALIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("materialize", "develop", "freeze", "founders", "status")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.command == "materialize":
        probes = build_pool(V3Slice.DEV)
        print(
            canonical_json(
                {
                    "families": len(probes) // 6,
                    "probes": len(probes),
                    "hash": stable_hash([probe.to_dict() for probe in probes]),
                }
            )
        )
    elif args.command == "develop":
        print(canonical_json(run_development(args.root)))
    elif args.command == "freeze":
        print(canonical_json(freeze_from_development(args.root)))
    elif args.command == "founders":
        result = run_founder_tournament(args.root)
        print(
            canonical_json(
                {
                    "result_hash": result["result_hash"],
                    "promoted": result["promoted"],
                    "accuracy_range": result["accuracy_range"],
                    "calls": result["calls"],
                }
            )
        )
    else:
        print(canonical_json(experiment_status_v3(args.root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
