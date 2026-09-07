"""Fitness V5: a Game-R instrument with a constrained response protocol.

V5 changes exactly two things relative to the invalidated V4, and both are instrument
repairs rather than task redesign for its own sake:

1. **Response protocol.**  V4 asked for a bare JSON object under a 64-token completion cap
   with no reasoning.  59 of its rows began a prose derivation and hit the cap before
   emitting any JSON, and at hard levels the Solver fell back to answering "A" every time.
   V5 uses Ollama's grammar-constrained ``format`` schema, so the decode alphabet cannot
   produce prose at all.  This removes an artifact; it does not make the mathematics easier.
2. **Task grounding.**  V4's mechanisms were synthetic.  V5's lead mechanism is built from
   *real elaborated Lean 4 goal states* (see :mod:`arena.environments.formal_structural`),
   filtered so that every one of the eight candidate representations renders it within the
   frozen context budget.  That filter is a first-class part of the design: on unrestricted
   real states the eight surfaces differ in length by up to 24x, which would confound
   organisation with token cost.

Every mechanism carries a genuine **explicit-positive** arm in which the decisive relation is
asserted outright in the state.  V4's level 0 was merely its smallest structural size, which
is a different and weaker control; a Solver that fails a relation-stated arm cannot do the
mechanism at any readability and the mechanism is an instrument limit, not a language result.

Game-R discipline is unchanged: only ``R`` varies, ``assert_game_r_genome`` rejects any
content-projection candidate, and information parity is asserted before any founder call.
"""

from __future__ import annotations

import argparse
import json
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
    Obligation,
    canonical_json,
    stable_hash,
)
from arena.environments.formal_structural import (
    ENVIRONMENT_VERSION,
    FormalState,
    build_state,
    destroy_depth_relation,
    load_formal_states,
    relabel,
)
from arena.experiments.fitness_v4 import (
    _dependency_family,
    _premise_family,
    assert_game_r_genome,
)
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ContentGenome, ModelViewGenome, SearchTrack
from arena.storage.artifacts import ArtifactStore
from arena.verifier.native import NativeVerifier

EXPERIMENT_VERSION = "arena-representation-fitness-v5"
INSTRUMENT_VERSION = "arena-game-r-constrained-formal-instrument-v5.0.0"
EXPERIMENT_SEED = 20260907
CONTROL_SURFACE = "L3_JSON_AST"
BASELINE_CANDIDATE = "V5E_L3_JSON_AST"

#: The decisive protocol repair: a grammar-constrained answer alphabet.
RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"choice": {"type": "string", "enum": ["A", "B"]}},
    "required": ["choice"],
}
RUNTIME_CONFIG: dict[str, Any] = {
    "engine": "ollama",
    "num_ctx": 32768,
    "temperature": 0.0,
    "seed": 20260905,
    "num_predict": 64,
    "top_k": 64,
    "top_p": 0.95,
    "think": False,
    "format": "json_schema:choice_ab",
}
RUNTIME_CONFIG_HASH = stable_hash(RUNTIME_CONFIG)

#: Phase-6 "bare prompt" condition.  Ollama's /api/generate applies a model's built-in
#: RENDERER when one exists: gemma4 carries one and gains 12 framing tokens (and can change
#: its answer), while qwen38-rvn carries none and receives the prompt verbatim.  Comparing a
#: framed solver against a bare one is not a solver substitution, so Phase 6 sets ``raw`` for
#: BOTH solvers, which delivers exactly the bytes ``build_prompt`` constructed.  This changes
#: the runtime, hence the hash, hence the cache namespace: Phase-5 rows are preserved
#: untouched and are never mixed with Phase-6 rows.
RUNTIME_CONFIG_BARE: dict[str, Any] = {**RUNTIME_CONFIG, "raw": True}
RUNTIME_CONFIG_BARE_HASH = stable_hash(RUNTIME_CONFIG_BARE)

#: Solver registry for Phase 6 substitution.  The cache identity keys on the DIGEST, while the
#: HTTP call uses the NAME, and nothing linked them: editing the name alone would have made
#: every Phase-6 identity collide with a Phase-5 file and silently replay gemma's answers as
#: the new solver's.  `verify_served_model` closes that hole by asserting the served digest
#: before any run, so name and digest can no longer drift apart.
SOLVERS: dict[str, dict[str, str]] = {
    "gemma4:12b": {
        "name": "gemma4:12b",
        "digest": "4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c",
        "family": "gemma4",
        "parameter_size": "11.9B",
        "quantization": "Q4_K_M",
    },
    "qwen38-rvn": {
        "name": "qwen38-rvn:latest",
        "digest": "25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae",
        "family": "qwen35",
        "parameter_size": "27.3B",
        "quantization": "Q4_K_M",
    },
}
DEFAULT_SOLVER = SOLVERS["gemma4:12b"]


def verify_served_model(solver: dict[str, str]) -> dict[str, Any]:
    """Assert the locally served model matches the solver's recorded digest and template.

    Two things are checked because both can silently invalidate a substitution experiment:
    the digest (so cached rows cannot be attributed to the wrong model) and the prompt
    template (a model whose Modelfile wraps the prompt in chat markers is not receiving the
    same bytes as one with a pass-through template, which would change the input, not just
    the solver).
    """

    request = Request(
        "http://127.0.0.1:11434/api/show",
        data=json.dumps({"model": solver["name"]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed local service
        shown = json.loads(response.read().decode())
    tags_request = Request("http://127.0.0.1:11434/api/tags", method="GET")
    with urlopen(tags_request, timeout=120) as response:  # noqa: S310 - fixed local service
        tags = json.loads(response.read().decode())
    served = next((m for m in tags["models"] if m["name"] == solver["name"]), None)
    if served is None:
        raise RuntimeError(f"solver {solver['name']} is not served by the local runtime")
    if served["digest"] != solver["digest"]:
        raise RuntimeError(
            f"digest mismatch for {solver['name']}: served {served['digest']} != "
            f"recorded {solver['digest']}. Refusing to run: cached rows key on the digest."
        )
    template = str(shown.get("template", ""))
    return {
        "name": solver["name"],
        "digest": served["digest"],
        "template": template,
        "template_hash": stable_hash(template),
        "template_is_passthrough": template.strip() == "{{ .Prompt }}",
        "capabilities": shown.get("capabilities", []),
        "details": served.get("details", {}),
    }


#: Context accounting.  V4's character heuristics were representation-specific and voided 30
#: rows that measured token counts say would have fit.  V5 refuses only absurd prompts and
#: decides truncation from the model's own reported prompt token count.
CONTEXT_GUARD: dict[str, Any] = {
    "method": "preflight_prompt_eval_count",
    "prompt_token_limit": int(RUNTIME_CONFIG["num_ctx"]) - int(RUNTIME_CONFIG["num_predict"]) - 256,
    "rule": (
        "true token count comes from a num_predict=1 preflight at the production num_ctx; a row "
        "is INPUT_CONTEXT_TRUNCATION iff true_tokens exceed the limit or the production call "
        "reports a different prompt_eval_count. Character heuristics are never scientific truth: "
        "measured chars/token on these prompts spans 2.74 to 7.43, and V4's chars/2.0 rule voided "
        "30 rows that in fact used about a quarter of the window."
    ),
    "probe_selection_max_chars_any_surface": 30000,
}

MECHANISMS = ("formal_expression_depth", "transitive_dependency", "precondition_conjunction")
LADDERS: dict[str, tuple[dict[str, Any], ...]] = {
    # level 0 is the explicit-positive arm for every mechanism.
    "formal_expression_depth": (
        {"explicit": True, "stratum": "medium"},
        {"explicit": False, "stratum": "shallow"},
        {"explicit": False, "stratum": "medium"},
        {"explicit": False, "stratum": "deep"},
    ),
    "transitive_dependency": (
        {"explicit": True, "hops": 3},
        {"explicit": False, "hops": 2},
        {"explicit": False, "hops": 3},
        {"explicit": False, "hops": 5},
    ),
    "precondition_conjunction": (
        {"explicit": True, "premises": 3},
        {"explicit": False, "premises": 2},
        {"explicit": False, "premises": 3},
        {"explicit": False, "premises": 5},
    ),
}
DEV_FAMILIES = 12
SCOUT_FAMILIES = 16  # 32 positives per mechanism per candidate

QUALIFICATION_RULE: dict[str, Any] = {
    "selection_source": "DEV only; permanent JSON/typed-AST control only; no candidate outcome",
    "explicit_positive_level": 0,
    "explicit_positive_min": 0.90,
    "explicit_positive_meaning": "the decisive relation is asserted outright in the state",
    "frontier_target": 0.625,
    "frontier_band": [0.35, 0.85],
    "frontier_selection": "among levels 1..3 minimise |accuracy - 0.625|, ties to the lower level",
    "q0_valid_rate_min": 0.95,
    "valid_response_rate_min": 0.95,
    "context_truncated_rows_max": 0,
    "positive_negative_gap_min": 0.20,
    "negative_target_accuracy_max": 0.60,
    "largest_answer_share_max": 0.75,
    "min_positives_for_gates": 24,
    "semantic_flip_reported_not_gated": True,
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
        "VOID_POSITION_SHARE",
        "VOID_POSITION",
        "VOID_SHORTCUT",
    ],
}
PROMOTION_RULE: dict[str, Any] = {
    "baseline": BASELINE_CANDIDATE,
    "valid_response_rate_min": 0.95,
    "paired_unit": "positive probe on the common in-budget set",
    "paired_test": "one-sided exact sign test on discordant positive outcomes",
    "paired_p_max": 0.05,
    "familywise_policy": "Holm across all non-baseline founders",
    "minimum_net_wins": "max(4, ceil(0.075 * positives))",
    "practical_effect_min": 0.10,
    "smallest_effect_of_interest": 0.15,
    "practical_equivalence_region": 0.125,
    "semantic_flip_noninferiority": -0.05,
    "covariate_reported": "mean rendered prompt tokens per candidate; length is a Pareto axis, not a defect",
    "note": "non-significance is not equivalence",
}
MODEL_CALL_BUDGET = {"development_max": 900, "scout_max": 3000}


class V5Slice(StrEnum):
    DEV = "DEV"
    SCOUT = "SCOUT"


class V5Variant(StrEnum):
    ORIGINAL = "ORIGINAL"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    DESTROYED_ORIGINAL = "DESTROYED_ORIGINAL"
    DESTROYED_COUNTERFACTUAL = "DESTROYED_COUNTERFACTUAL"
    SWAPPED_ORIGINAL = "SWAPPED_ORIGINAL"
    SWAPPED_COUNTERFACTUAL = "SWAPPED_COUNTERFACTUAL"


POSITIVE_VARIANTS = {V5Variant.ORIGINAL.value, V5Variant.COUNTERFACTUAL.value}
SWAPPED_VARIANTS = {V5Variant.SWAPPED_ORIGINAL.value, V5Variant.SWAPPED_COUNTERFACTUAL.value}

#: Diagnostic causes.  These never collapse into a single "wrong" label.
FAILURE_TAXONOMY = (
    "CORRECT",
    "NEGATIVE_CONTROL_RESPONSE",
    "MODEL_SEMANTIC_ERROR",
    "RESPONSE_SCHEMA_ERROR",
    "OUTPUT_TRUNCATION",
    "INPUT_CONTEXT_TRUNCATION",
    "PARSER_ERROR",
)


@dataclass(frozen=True, slots=True)
class V5Probe:
    probe_id: str
    family_id: str
    slice_name: V5Slice
    mechanism: str
    level: int
    parameters: dict[str, Any]
    variant: V5Variant
    state: CanonicalState
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
    return CanonicalExpression(name, tuple(_atom(v) for v in values), sort="Proposition")


def _option(index: int, answer: str, alternate: str) -> CanonicalAction:
    return CanonicalAction(
        action_id=f"option:{index}",
        operation="propose_structural_answer",
        target_ids=(f"object:id:{answer}",),
        arguments=(_atom(answer),),
        warrant=f"evidence-authority:{answer}",
        preconditions=(_relation("requires", answer), _relation("exclude", alternate)),
        generated_obligations=(
            Obligation(f"obligation:option:{index}", _relation("prove", answer), source=answer),
        ),
        expected_usefulness=0.0,
    )


# ------------------------------------------------------- mechanism: formal expression depth


def _with_explicit_depths(
    state: CanonicalState, left: str, right: str, left_depth: int, right_depth: int
) -> CanonicalState:
    """Explicit-positive arm: assert each identifier's depth outright in the state.

    This is an INSTRUMENT control, not a candidate variation: it is applied identically to
    every representation, so it never changes what one candidate sees relative to another.
    """

    from dataclasses import replace

    facts = (
        CanonicalExpression(
            "occurs_at_depth",
            (_atom(left), CanonicalExpression("literal", value=left_depth, sort="Integer")),
            sort="Proposition",
        ),
        CanonicalExpression(
            "occurs_at_depth",
            (_atom(right), CanonicalExpression("literal", value=right_depth, sort="Integer")),
            sort="Proposition",
        ),
    )
    return replace(state, established_facts=facts)


def _formal_family(formal: FormalState, explicit: bool) -> tuple[Any, ...]:
    features = formal.features
    left = cast(str, features.deepest_identifier)
    right = cast(str, features.runner_up_identifier)
    goal_op = "deepest_local_reference"
    original = build_state(formal.target, formal.context_identities, goal_op)
    counter = build_state(relabel(formal.target, left, right), formal.context_identities, goal_op)
    destroyed = build_state(destroy_depth_relation(left, right), formal.context_identities, goal_op)
    if explicit:
        deep, shallow = features.max_depth, features.max_depth - features.depth_lead
        original = _with_explicit_depths(original, left, right, deep, shallow)
        counter = _with_explicit_depths(counter, left, right, shallow, deep)
        destroyed = _with_explicit_depths(destroyed, left, right, 1, 1)
    question = (
        "Which identifier occurs at the greatest nesting depth inside the goal expression? "
        "Depth counts nested argument levels from the goal's root."
    )
    return original, counter, destroyed, left, right, question


# ------------------------------------------------------------------ family construction


def _synthetic_family(mechanism: str, params: dict[str, Any], salt: str) -> tuple[Any, ...]:
    builder = {
        "transitive_dependency": _dependency_family,
        "precondition_conjunction": _premise_family,
    }[mechanism]
    numeric = {k: v for k, v in params.items() if isinstance(v, int)}
    family = builder(numeric, salt)
    original, counter, destroyed = family.original, family.counterfactual, family.destroyed
    if params.get("explicit"):
        from dataclasses import replace

        def assert_answer(state: CanonicalState, answer: str) -> CanonicalState:
            return replace(
                state,
                established_facts=(*state.established_facts, _relation("the_answer_is", answer)),
            )

        original = assert_answer(original, family.answer_a)
        counter = assert_answer(counter, family.answer_b)
        destroyed = assert_answer(destroyed, family.answer_a)
    return original, counter, destroyed, family.answer_a, family.answer_b, family.question


def derive_probe_family(
    mechanism: str,
    level: int,
    slice_name: V5Slice,
    salt: int,
    formal: FormalState | None = None,
) -> tuple[V5Probe, ...]:
    params = dict(LADDERS[mechanism][level])
    if mechanism == "formal_expression_depth":
        if formal is None:
            raise ValueError("formal_expression_depth requires a source state")
        original, counter, destroyed, left, right, question = _formal_family(
            formal, bool(params["explicit"])
        )
        source_id = formal.item_id
        oracle_extra: dict[str, Any] = {
            "provenance": formal.provenance.to_dict(),
            "features": formal.features.to_dict(),
            "theorem_id": formal.theorem_id,
        }
    else:
        original, counter, destroyed, left, right, question = _synthetic_family(
            mechanism, params, f"{EXPERIMENT_VERSION}|{mechanism}|{level}|{salt}"
        )
        source_id = f"synthetic:{salt}"
        oracle_extra = {"generator_salt": salt}

    options = (_option(0, left, right), _option(1, right, left))
    swapped = cast(tuple[CanonicalAction, CanonicalAction], tuple(reversed(options)))
    family_id = f"v5:{slice_name.value.lower()}:{mechanism}:l{level}:{source_id}"

    def make(
        variant: V5Variant,
        state: CanonicalState,
        expected: int,
        truth: str,
        displayed: tuple[CanonicalAction, CanonicalAction] = options,
    ) -> V5Probe:
        identity = {
            "family": family_id,
            "variant": variant.value,
            "state": state.mathematical_hash,
            "options": [item.to_dict() for item in displayed],
        }
        return V5Probe(
            probe_id=f"probe:{stable_hash(identity)[:20]}",
            family_id=family_id,
            slice_name=slice_name,
            mechanism=mechanism,
            level=level,
            parameters=params,
            variant=variant,
            state=state,
            question=question,
            options=displayed,
            expected_index=expected,
            truth_kind=truth,
            oracle_record={"rule": mechanism, "source_item": source_id, **oracle_extra},
        )

    return (
        make(V5Variant.ORIGINAL, original, 0, "MATHEMATICAL"),
        make(V5Variant.COUNTERFACTUAL, counter, 1, "MATHEMATICAL"),
        make(V5Variant.DESTROYED_ORIGINAL, destroyed, 0, "NEGATIVE_CONTROL_TARGET"),
        make(V5Variant.DESTROYED_COUNTERFACTUAL, destroyed, 1, "NEGATIVE_CONTROL_TARGET"),
        make(V5Variant.SWAPPED_ORIGINAL, original, 1, "MATHEMATICAL", swapped),
        make(V5Variant.SWAPPED_COUNTERFACTUAL, counter, 0, "MATHEMATICAL", swapped),
    )


def validate_probe_family(probes: tuple[V5Probe, ...]) -> dict[str, Any]:
    if len(probes) != 6 or len({p.family_id for p in probes}) != 1:
        raise ValueError("V5 family must contain six siblings")
    by_variant = {p.variant: p for p in probes}
    verifier = NativeVerifier()
    for probe in probes:
        result = verifier.verify_state(probe.state)
        if not result.accepted:
            raise ValueError(f"invalid V5 state {probe.probe_id}: {result.issues}")
        if probe.state.legal_actions or probe.state.plausible_invalid_actions:
            raise ValueError("V5 observation leaks action membership")
        if any(option.expected_usefulness != 0.0 for option in probe.options):
            raise ValueError("V5 option leaks oracle usefulness")
    a, b = by_variant[V5Variant.DESTROYED_ORIGINAL], by_variant[V5Variant.DESTROYED_COUNTERFACTUAL]
    if a.state.mathematical_hash != b.state.mathematical_hash or a.options != b.options:
        raise ValueError("V5 negative siblings are not information-identical")
    if a.expected_index == b.expected_index:
        raise ValueError("V5 negative targets are not balanced")
    for base_v, swap_v in (
        (V5Variant.ORIGINAL, V5Variant.SWAPPED_ORIGINAL),
        (V5Variant.COUNTERFACTUAL, V5Variant.SWAPPED_COUNTERFACTUAL),
    ):
        base, swap = by_variant[base_v], by_variant[swap_v]
        if base.state.mathematical_hash != swap.state.mathematical_hash:
            raise ValueError("position swap changed V5 state")
        if base.options != tuple(reversed(swap.options)):
            raise ValueError("position swap changed V5 option set")
        if (
            base.options[base.expected_index].arguments
            != swap.options[swap.expected_index].arguments
        ):
            raise ValueError("position swap changed V5 truth")
    if {
        by_variant[V5Variant.ORIGINAL].expected_index,
        by_variant[V5Variant.COUNTERFACTUAL].expected_index,
    } != {0, 1}:
        raise ValueError("V5 positive targets are not balanced")
    return {"family_id": probes[0].family_id, "valid": True}


def equal_information_genome(surface_id: str = CONTROL_SURFACE) -> ModelViewGenome:
    return ModelViewGenome(
        f"V5E_{surface_id}",
        (),
        SearchTrack.EQUAL_INFORMATION,
        __import__("arena.genome.seeds", fromlist=["SEED_GENOME_BY_ID"]).SEED_GENOME_BY_ID[
            surface_id
        ],
        ContentGenome(),
    )


def v5_founders() -> tuple[ModelViewGenome, ...]:
    from arena.genome.seeds import SEED_GENOME_BY_ID

    return tuple(equal_information_genome(cid) for cid in SEED_GENOME_BY_ID)


def build_prompt(genome: ModelViewGenome, probe: V5Probe) -> str:
    assert_game_r_genome(genome)
    compiler = ModelViewCompiler(genome)
    language = GenomePhenotypeLanguage(genome.surface)
    view = compiler.compile(probe.state, options=probe.options)
    rendered = [
        f"{label}: {language.render_action_choice(option)}"
        for label, option in zip(("A", "B"), probe.options, strict=True)
    ]
    return (
        'Answer with the JSON object {"choice":"A"} or {"choice":"B"}.\n'
        "Read identifiers exactly. Do not choose by option position.\n"
        f"QUESTION: {probe.question}\nSYNTAX GUIDE:\n{language.acquisition_guide()}\n"
        f"CURRENT STATE:\n{view.text}\nOPTIONS:\n" + "\n".join(rendered) + "\nANSWER:"
    )


def parse_response(output: str) -> int | None:
    try:
        value = json.loads(output.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or set(value) != {"choice"} or value["choice"] not in {"A", "B"}:
        return None
    return 0 if value["choice"] == "A" else 1


def _call_ollama(model: str, prompt: str, *, bare: bool = False) -> dict[str, Any]:
    config = RUNTIME_CONFIG_BARE if bare else RUNTIME_CONFIG
    options = {
        key: value
        for key, value in config.items()
        if key not in {"engine", "think", "format", "raw"}
    }
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": RESPONSE_SCHEMA,
        "options": options,
    }
    if bare:
        # raw bypasses the model's renderer; `think` is a renderer-level control and is
        # rejected alongside it, so it is omitted rather than set.
        payload["raw"] = True
    else:
        payload["think"] = config["think"]
    request = Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=900) as response:  # noqa: S310 - fixed local service
        raw = json.loads(response.read().decode())
    return {
        "response": str(raw.get("response", "")),
        "prompt_eval_count": int(raw.get("prompt_eval_count", 0)),
        "eval_count": int(raw.get("eval_count", 0)),
        "done_reason": str(raw.get("done_reason", "")),
        "total_duration_ns": int(raw.get("total_duration", 0)),
    }


def classify_row(raw: dict[str, Any], prompt: str, probe: V5Probe, parsed: int | None) -> str:
    limit = int(CONTEXT_GUARD["prompt_token_limit"])
    tokens = int(raw.get("prompt_eval_count", 0))
    if raw.get("error"):
        return "INPUT_CONTEXT_TRUNCATION" if "OVER_BUDGET" in str(raw["error"]) else "PARSER_ERROR"
    if tokens > limit:
        return "INPUT_CONTEXT_TRUNCATION"
    if parsed is None:
        if int(raw.get("eval_count", 0)) >= int(RUNTIME_CONFIG["num_predict"]):
            return "OUTPUT_TRUNCATION"
        return "RESPONSE_SCHEMA_ERROR" if raw.get("response", "").strip() else "PARSER_ERROR"
    if probe.truth_kind == "NEGATIVE_CONTROL_TARGET":
        return "NEGATIVE_CONTROL_RESPONSE"
    expected = probe.options[probe.expected_index].arguments[0].content_hash
    chosen = probe.options[parsed].arguments[0].content_hash
    return "CORRECT" if chosen == expected else "MODEL_SEMANTIC_ERROR"


def _cached_call(
    root: Path,
    identity: dict[str, Any],
    prompt: str,
    solver: dict[str, str] = DEFAULT_SOLVER,
    bare: bool = False,
) -> tuple[dict[str, Any], bool]:
    path = root / "artifacts/cache/fitness_v5" / f"{stable_hash(identity)}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("identity") != identity or not isinstance(cached.get("result"), dict):
            raise ValueError(f"invalid V5 cache record: {path}")
        return cached["result"], True
    # No character pre-guard: V5 probes are pre-filtered by rendered size, so at the measured
    # floor of 2.74 characters per token no prompt can reach the token limit. Truncation is
    # verified after the call from the model's own reported prompt_eval_count.
    started = time.monotonic()
    try:
        raw: dict[str, Any] = _call_ollama(str(solver["name"]), prompt, bare=bare)
    except Exception as error:  # pragma: no cover - network/runtime failure path
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


def summarize(rows: Sequence[dict[str, Any]], q0_rate: float = 1.0) -> dict[str, Any]:
    base = [r for r in rows if r["variant"] in POSITIVE_VARIANTS]
    negative = [r for r in rows if r["truth_kind"] == "NEGATIVE_CONTROL_TARGET"]

    def acc(values: Sequence[dict[str, Any]]) -> float:
        return sum(r["correct"] for r in values) / len(values) if values else 0.0

    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_family[row["family_id"]][row["variant"]] = row
    flips = choice_flips = invariant = invariant_pairs = 0
    for variants in by_family.values():
        o, c = variants.get("ORIGINAL"), variants.get("COUNTERFACTUAL")
        if o and c:
            flips += bool(o["correct"] and c["correct"])
            choice_flips += bool(
                o["selected_hash"] is not None
                and c["selected_hash"] is not None
                and o["selected_hash"] != c["selected_hash"]
            )
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
    families = len(by_family)
    positive, negative_acc = acc(base), acc(negative)
    return {
        "q0_valid_rate": q0_rate,
        "positive_accuracy": positive,
        "negative_target_accuracy": negative_acc,
        "positive_negative_gap": positive - negative_acc,
        "semantic_flip_consistency": flips / families if families else 0.0,
        "choice_flip_rate": choice_flips / families if families else 0.0,
        "position_invariance": invariant / invariant_pairs if invariant_pairs else 0.0,
        "largest_answer_share": (
            max(Counter(r["parsed_index"] for r in base if r["parsed_index"] is not None).values())
            / max(1, sum(r["parsed_index"] is not None for r in base))
            if any(r["parsed_index"] is not None for r in base)
            else 1.0
        ),
        "valid_response_rate": sum(r["parsed_index"] is not None for r in rows) / len(rows)
        if rows
        else 0.0,
        "context_truncated_rows": sum(r["cause"] == "INPUT_CONTEXT_TRUNCATION" for r in rows),
        "output_truncated_rows": sum(r["cause"] == "OUTPUT_TRUNCATION" for r in rows),
        "cause_totals": dict(Counter(r["cause"] for r in rows)),
        "mechanisms": sorted({r["mechanism"] for r in rows}),
        "families": families,
        "positive_examples": len(base),
        "mean_prompt_tokens": sum(r["prompt_tokens"] for r in rows) / len(rows) if rows else 0.0,
    }


def evaluate(
    root: Path,
    genome: ModelViewGenome,
    probes: Sequence[V5Probe],
    *,
    progress: Callable[[int, int], None] | None = None,
    solver: dict[str, str] = DEFAULT_SOLVER,
    bare: bool = False,
) -> dict[str, Any]:
    assert_game_r_genome(genome)
    rows: list[dict[str, Any]] = []
    for index, probe in enumerate(probes):
        prompt = build_prompt(genome, probe)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "instrument": INSTRUMENT_VERSION,
            "model_digest": solver["digest"],
            "runtime_hash": RUNTIME_CONFIG_BARE_HASH if bare else RUNTIME_CONFIG_HASH,
            "genome_hash": genome.genome_hash,
            "probe_hash": probe.derived_hash,
            "prompt_hash": stable_hash(prompt),
        }
        raw, hit = _cached_call(root, identity, prompt, solver, bare)
        parsed = parse_response(raw["response"])
        cause = classify_row(raw, prompt, probe, parsed)
        selected_hash = (
            probe.options[parsed].arguments[0].content_hash if parsed is not None else None
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
                "parsed_index": parsed,
                "selected_hash": selected_hash,
                "expected_hash": expected_hash,
                "correct": selected_hash == expected_hash,
                "cause": cause,
                "prompt_chars": len(prompt),
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "done_reason": raw.get("done_reason", ""),
                "raw_output": raw["response"],
                "cache_hit": hit,
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
        "cache_hits": sum(r["cache_hit"] for r in rows),
    }


def shortcut_audit(probes: Sequence[V5Probe]) -> dict[str, Any]:
    positives = [p for p in probes if p.variant.value in POSITIVE_VARIANTS]
    if not positives:
        return {"items": 0, "status": "EMPTY"}

    def names(p: V5Probe) -> tuple[str, str]:
        return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))

    def text(p: V5Probe) -> str:
        return canonical_json(p.state.to_dict(include_display_identity=False))

    rules: dict[str, Callable[[V5Probe], int]] = {
        "always_first_option": lambda p: 0,
        "always_second_option": lambda p: 1,
        "first_mentioned_in_state": lambda p: (
            0 if text(p).find(f'"{names(p)[0]}"') <= text(p).find(f'"{names(p)[1]}"') else 1
        ),
        "last_mentioned_in_state": lambda p: (
            0 if text(p).rfind(f'"{names(p)[0]}"') >= text(p).rfind(f'"{names(p)[1]}"') else 1
        ),
        "more_frequent_in_state": lambda p: (
            0 if text(p).count(f'"{names(p)[0]}"') >= text(p).count(f'"{names(p)[1]}"') else 1
        ),
        "shorter_option_text": lambda p: (
            0 if (len(names(p)[0]), names(p)[0]) <= (len(names(p)[1]), names(p)[1]) else 1
        ),
        "alphabetically_first": lambda p: 0 if names(p)[0] <= names(p)[1] else 1,
    }
    scores = {
        n: sum(r(p) == p.expected_index for p in positives) / len(positives)
        for n, r in rules.items()
    }
    worst = max(scores, key=lambda n: abs(scores[n] - 0.5))
    worst_score = max(scores[worst], 1.0 - scores[worst])
    answers = Counter(p.expected_index for p in positives)
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


__all__ = [
    "CONTEXT_GUARD",
    "EXPERIMENT_VERSION",
    "FAILURE_TAXONOMY",
    "INSTRUMENT_VERSION",
    "LADDERS",
    "MECHANISMS",
    "PROMOTION_RULE",
    "QUALIFICATION_RULE",
    "RESPONSE_SCHEMA",
    "RUNTIME_CONFIG",
    "V5Probe",
    "V5Slice",
    "V5Variant",
    "build_prompt",
    "classify_row",
    "derive_probe_family",
    "equal_information_genome",
    "evaluate",
    "parse_response",
    "shortcut_audit",
    "summarize",
    "v5_founders",
    "validate_probe_family",
]


# --------------------------------------------------------------------- probe construction


def _formal_pool(root: Path) -> dict[str, list[FormalState]]:
    """Length-fair real Lean states, bucketed by depth stratum.

    The length filter is the point.  On unrestricted real states the eight candidate
    surfaces differ in rendered length by a median factor of 6.5 and a maximum of 23.7, so
    an accuracy comparison would be dominated by token cost.  Requiring every surface to
    render under a fixed character budget bounds that ratio to about 4.6 and, at the same
    time, guarantees no prompt can approach the context limit: at the measured floor of
    2.74 characters per token a 30,000-character prompt is under 11,000 tokens against a
    32,448-token budget, so INPUT_CONTEXT_TRUNCATION is structurally unreachable and is
    asserted rather than preflighted.
    """

    from arena.environments.formal_structural import stratify

    budget = int(CONTEXT_GUARD["probe_selection_max_chars_any_surface"])
    founders = v5_founders()
    languages = [GenomePhenotypeLanguage(g.surface) for g in founders]
    eligible: list[FormalState] = []
    for state in load_formal_states():
        canonical = build_state(state.target, state.context_identities, "deepest_local_reference")
        if max(len(lang.render(canonical)) for lang in languages) <= budget:
            eligible.append(state)
    return stratify(eligible)


def build_dev_pool(
    root: Path, mechanisms: Sequence[str] = MECHANISMS, levels: Sequence[int] = (0, 1, 2, 3)
) -> tuple[V5Probe, ...]:
    pool = _formal_pool(root)
    probes: list[V5Probe] = []
    for mechanism in mechanisms:
        for level in levels:
            params = LADDERS[mechanism][level]
            for index in range(DEV_FAMILIES):
                salt = EXPERIMENT_SEED + MECHANISMS.index(mechanism) * 1000 + level * 100 + index
                formal = None
                if mechanism == "formal_expression_depth":
                    bucket = pool.get(str(params["stratum"]), [])
                    if index >= len(bucket):
                        continue
                    formal = bucket[index]
                family = derive_probe_family(mechanism, level, V5Slice.DEV, salt, formal)
                validate_probe_family(family)
                probes.extend(family)
    return tuple(probes)


def select_frontier_level(level_accuracies: dict[int, float]) -> dict[str, Any]:
    rule = QUALIFICATION_RULE
    explicit = level_accuracies.get(0, 0.0)
    if explicit < float(rule["explicit_positive_min"]):
        return {
            "selected_level": None,
            "verdict": "VOID_INSTRUMENT_LIMIT",
            "explicit_positive_accuracy": explicit,
        }
    candidates = [(lvl, acc) for lvl, acc in sorted(level_accuracies.items()) if lvl >= 1]
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
    verdict = (
        "VOID_CEILING"
        if accuracy > high
        else "VOID_FLOOR"
        if accuracy < low
        else "FRONTIER_SELECTED"
    )
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
        "q0": "PASS" if q0_rate >= float(rule["q0_valid_rate_min"]) else "VOID_VALIDITY",
        "valid_response": "PASS"
        if summary["valid_response_rate"] >= float(rule["valid_response_rate_min"])
        else "VOID_VALIDITY",
        "context": "PASS"
        if summary["context_truncated_rows"] <= int(rule["context_truncated_rows_max"])
        else "VOID_CONTEXT",
        "sample_size": "PASS"
        if summary["positive_examples"] >= int(rule["min_positives_for_gates"])
        else "VOID_VALIDITY",
        "negative_collapse": (
            "PASS"
            if summary["positive_negative_gap"] >= float(rule["positive_negative_gap_min"])
            and summary["negative_target_accuracy"] <= float(rule["negative_target_accuracy_max"])
            else "VOID_NEGATIVE_CONTROL"
        ),
        "answer_share": "PASS"
        if summary["largest_answer_share"] <= float(rule["largest_answer_share_max"])
        else "VOID_POSITION_SHARE",
        "position_invariance": "PASS"
        if summary["position_invariance"] >= float(rule["position_invariance_min"])
        else "VOID_POSITION",
        "shortcut": "PASS" if audit.get("status") == "CLEAN" else "VOID_SHORTCUT",
    }
    failures = [code for code in checks.values() if code != "PASS"]
    return {
        "checks": checks,
        "qualified": not failures,
        "verdict": failures[0] if failures else "QUALIFIED",
    }


def _q0(root: Path, solver: dict[str, str] = DEFAULT_SOLVER, bare: bool = False) -> dict[str, Any]:
    rows = []
    for index in range(8):
        expected = "A" if index % 2 == 0 else "B"
        prompt = f'Format check only. Answer with {{"choice":"{expected}"}}.\nANSWER:'
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "kind": "Q0",
            "model_digest": solver["digest"],
            "runtime_hash": RUNTIME_CONFIG_BARE_HASH if bare else RUNTIME_CONFIG_HASH,
            "case": index,
            "prompt_hash": stable_hash(prompt),
        }
        raw, _ = _cached_call(root, identity, prompt, solver, bare)
        parsed = parse_response(raw["response"])
        rows.append(
            {
                **identity,
                "expected": expected,
                "parsed": parsed,
                "correct": parsed == (0 if expected == "A" else 1),
                "raw_output": raw["response"],
            }
        )
    return {"rate": sum(r["correct"] for r in rows) / len(rows), "rows": rows}


def _log(message: str) -> None:
    print(f"[fitness_v5 {time.strftime('%H:%M:%S')}] {message}", flush=True)


def development_artifact_path(solver: dict[str, str], bare: bool = False) -> str:
    """Phase-5's artifact keeps its exact path; every other condition writes beside it."""

    if solver["digest"] == DEFAULT_SOLVER["digest"] and not bare:
        return "experiments/fitness_v5/development/result.json"
    key = solver["name"].replace(":", "_").replace("/", "_")
    suffix = "-bare" if bare else ""
    return f"experiments/fitness_v5/development/result-{key}{suffix}.json"


def run_development(
    root: Path, solver: dict[str, str] = DEFAULT_SOLVER, bare: bool = False
) -> dict[str, Any]:
    served = verify_served_model(solver)
    _log(
        f"solver {solver['name']} digest verified; template passthrough={served['template_is_passthrough']}"
    )
    control = equal_information_genome()
    q0 = _q0(root, solver, bare)
    _log(f"Q0 valid rate {q0['rate']:.3f}")
    all_probes = build_dev_pool(root)
    by_cell: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for probe in all_probes:
        by_cell[(probe.mechanism, probe.level)].append(probe)

    mechanism_reports: dict[str, Any] = {}
    selected: dict[str, int] = {}
    ladder_rows: list[dict[str, Any]] = []
    for mechanism in MECHANISMS:
        accuracies: dict[int, float] = {}
        for level in range(len(LADDERS[mechanism])):
            cell = [p for p in by_cell[(mechanism, level)] if p.variant.value in POSITIVE_VARIANTS]
            if not cell:
                continue
            result = evaluate(root, control, cell, solver=solver, bare=bare)
            ladder_rows.extend(result["rows"])
            accuracies[level] = result["summary"]["positive_accuracy"]
            _log(
                f"{mechanism} L{level} positives {accuracies[level]:.3f} ({len(cell)} rows, "
                f"valid {result['summary']['valid_response_rate']:.3f}, "
                f"share {result['summary']['largest_answer_share']:.2f}, "
                f"tok {result['summary']['mean_prompt_tokens']:.0f})"
            )
        selection = select_frontier_level(accuracies)
        report: dict[str, Any] = {
            "ladder": [
                {"level": lvl, "parameters": LADDERS[mechanism][lvl], "positive_accuracy": acc}
                for lvl, acc in sorted(accuracies.items())
            ],
            "selection": selection,
        }
        if selection["selected_level"] is not None:
            level = int(selection["selected_level"])
            full = by_cell[(mechanism, level)]
            result = evaluate(root, control, full, solver=solver, bare=bare)
            audit = shortcut_audit(tuple(full))
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

    payload = {
        "schema_version": "arena-fitness-v5-development-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "instrument_version": INSTRUMENT_VERSION,
        "environment_version": ENVIRONMENT_VERSION,
        "control_candidate": control.candidate_id,
        "model": solver,
        "served_model": served,
        "runtime": RUNTIME_CONFIG_BARE if bare else RUNTIME_CONFIG,
        "prompt_condition": "bare" if bare else "framed",
        "response_schema": RESPONSE_SCHEMA,
        "runtime_config_hash": RUNTIME_CONFIG_HASH,
        "context_guard": CONTEXT_GUARD,
        "qualification_rule": QUALIFICATION_RULE,
        "promotion_rule": PROMOTION_RULE,
        "ladders": {k: list(v) for k, v in LADDERS.items()},
        "q0": q0,
        "dev_pool_hash": stable_hash([p.to_dict() for p in all_probes]),
        "dev_pool_probes": len(all_probes),
        "mechanisms": mechanism_reports,
        "qualified_mechanisms": sorted(selected),
        "selected_levels": selected,
        "instrument_qualified": len(selected)
        >= int(QUALIFICATION_RULE["minimum_qualified_mechanisms"]),
        "ladder_rows": ladder_rows,
    }
    ArtifactStore(root / "artifacts").write_json(development_artifact_path(solver, bare), payload)
    return payload


def experiment_status_v5(
    root: Path, solver: dict[str, str] = DEFAULT_SOLVER, bare: bool = False
) -> dict[str, Any]:
    path = root / "artifacts" / development_artifact_path(solver, bare)
    if not path.exists():
        return {"experiment_version": EXPERIMENT_VERSION, "sentinel": "FITNESS_V5_NOT_RUN"}
    development = json.loads(path.read_text())
    qualified = bool(development["instrument_qualified"])
    explicit_passes = sum(
        1
        for report in development["mechanisms"].values()
        if float(report["selection"]["explicit_positive_accuracy"])
        >= float(QUALIFICATION_RULE["explicit_positive_min"])
    )
    # Preregistered abort clause (docs/FITNESS_V5_SPEC.md section 9): if the instrument fails
    # while the Solver demonstrably CAN do the mechanisms once the relation is stated outright,
    # then the limit is the Solver or the task family, not the response protocol, and building
    # another instrument version would be protocol shopping.
    aborted = not qualified and explicit_passes >= int(
        QUALIFICATION_RULE["minimum_qualified_mechanisms"]
    )
    if qualified:
        sentinel = "FITNESS_V5_QUALIFIED"
    elif aborted:
        sentinel = "CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT"
    else:
        sentinel = "FITNESS_V5_NOT_QUALIFIED"
    return {
        "experiment_version": EXPERIMENT_VERSION,
        "solver": solver["name"],
        "sentinel": sentinel,
        "qualified_mechanisms": development["qualified_mechanisms"],
        "selected_levels": development["selected_levels"],
        "explicit_positive_arms_passing": explicit_passes,
        "abort_clause_triggered": aborted,
        "founder_tournament_authorized": qualified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("materialize", "develop", "status", "verify"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--solver", choices=tuple(SOLVERS), default="gemma4:12b")
    parser.add_argument(
        "--bare", action="store_true", help="send the prompt verbatim (no model renderer)"
    )
    args = parser.parse_args()
    if args.command == "materialize":
        probes = build_dev_pool(args.root)
        print(
            canonical_json(
                {
                    "probes": len(probes),
                    "families": len(probes) // 6,
                    "hash": stable_hash([p.to_dict() for p in probes]),
                    "shortcut_audit": shortcut_audit(probes),
                }
            )
        )
    elif args.command == "verify":
        print(canonical_json(verify_served_model(SOLVERS[args.solver])))
    elif args.command == "develop":
        result = run_development(args.root, SOLVERS[args.solver], args.bare)
        print(
            canonical_json(
                {
                    k: result[k]
                    for k in ("qualified_mechanisms", "selected_levels", "instrument_qualified")
                }
            )
        )
    else:
        print(canonical_json(experiment_status_v5(args.root, SOLVERS[args.solver], args.bare)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
