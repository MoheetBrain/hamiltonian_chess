"""Executable, lossless phenotypes for controlled one-gene representation mutations.

The codec deliberately operates on Arena's canonical wire payload.  Its transformations are
presentation changes only: parsing reverses them before the existing strict wire validator is
called.  No phenotype owns mathematical truth.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from arena.canonical.schema import CanonicalAction
from arena.genome.genes import (
    ActionPolicy,
    BinderPolicy,
    GrammarFamily,
    Morphology,
    RedundancyPolicy,
    SerializationPolicy,
    StatePolicy,
    TokenPolicy,
    TypePolicy,
)
from arena.genome.schema import LanguageGenome

from ._json_tools import strict_json_loads
from ._notation import sexpr_decode, sexpr_encode, typed_prefix_decode, typed_prefix_encode
from ._wire import STATE_FIELD_ORDER
from .base import CandidateLanguage

PHENOTYPE_CODEC_VERSION = "arena-genome-phenotype-v1"

_KNOWN_KEYS = (
    *STATE_FIELD_ORDER,
    "object_id",
    "type_name",
    "value",
    "shape",
    "unit",
    "binder_id",
    "variable",
    "scope_id",
    "binder_kind",
    "op",
    "sort",
    "args",
    "attributes",
    "obligation_id",
    "proposition",
    "status",
    "source",
    "evidence_id",
    "dependencies",
    "authority",
    "certificate_hash",
    "action_id",
    "operation",
    "target_ids",
    "arguments",
    "warrant",
    "preconditions",
    "generated_obligations",
    "expected_usefulness",
    "__type_form",
    "__sort",
    "__body",
    "__binding_form",
    "__fields",
)


def _role_map(genome: LanguageGenome) -> dict[str, str]:
    compact = genome.redundancy == RedundancyPolicy.COMPRESSED
    symbolic = genome.token_policy in {TokenPolicy.SYMBOLIC, TokenPolicy.COMPACT}
    result: dict[str, str] = {}
    for index, key in enumerate(_KNOWN_KEYS):
        neutral_key = {
            "legal_actions": "available_moves",
            "plausible_invalid_actions": "reserved_moves",
        }.get(key, key)
        if compact:
            base = f"r{index:x}"
        elif symbolic:
            base = f"@{index:x}"
        else:
            base = neutral_key
        if genome.morphology == Morphology.PREFIX_ROLE:
            label = f"role_{base}"
        elif genome.morphology == Morphology.SUFFIX_ROLE:
            label = f"{base}_role"
        elif genome.morphology == Morphology.TYPED_AFFIX:
            label = f"{base}:field"
        elif genome.morphology == Morphology.STRUCTURAL_ROLE:
            label = f"field/{index}/{base}"
        else:
            label = base
        result[key] = label
    if len(set(result.values())) != len(result):
        raise ValueError("phenotype role map is not injective")
    return result


def _map_keys(value: Any, mapping: Mapping[str, str]) -> Any:
    if isinstance(value, dict):
        return {mapping.get(key, key): _map_keys(child, mapping) for key, child in value.items()}
    if isinstance(value, list):
        return [_map_keys(child, mapping) for child in value]
    return value


def _type_encode(value: Any, policy: TypePolicy) -> Any:
    if isinstance(value, list):
        return [_type_encode(child, policy) for child in value]
    if not isinstance(value, dict):
        return value
    encoded = {key: _type_encode(child, policy) for key, child in value.items()}
    if "op" not in encoded or "sort" not in encoded:
        return encoded
    sort = encoded.pop("sort")
    if policy == TypePolicy.EXPLICIT_EVERY_USE:
        form = "typed"
    elif policy == TypePolicy.DECLARATION_ONLY:
        form = "declared"
    elif policy == TypePolicy.INFERRED:
        form = "hint"
    else:
        form = "refinement"
    return {"__type_form": form, "__sort": sort, "__body": encoded}


def _type_decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_type_decode(child) for child in value]
    if not isinstance(value, dict):
        return value
    decoded = {key: _type_decode(child) for key, child in value.items()}
    markers = {"__type_form", "__sort", "__body"}
    if markers.issubset(decoded):
        if set(decoded) != markers or decoded["__type_form"] not in {
            "typed",
            "declared",
            "hint",
            "refinement",
        }:
            raise ValueError("malformed phenotype type form")
        body = decoded["__body"]
        if not isinstance(body, dict):
            raise ValueError("phenotype type body must be a record")
        return {"op": body.pop("op"), "sort": decoded["__sort"], **body}
    return decoded


def _binding_encode(payload: dict[str, Any], policy: BinderPolicy) -> None:
    encoded = []
    for binding in payload["bindings"]:
        fields = [
            binding["binder_id"],
            binding["variable"],
            binding["type_name"],
            binding["scope_id"],
            binding["binder_kind"],
        ]
        if policy == BinderPolicy.NAMED_LEXICAL:
            encoded.append(binding)
        elif policy == BinderPolicy.STRUCTURAL_ID:
            encoded.append({"__binding_form": "structural", "__fields": fields})
        elif policy == BinderPolicy.LOCALLY_NAMELESS:
            encoded.append({"__binding_form": "nameless", "__fields": fields[1:] + fields[:1]})
        else:
            encoded.append({"__binding_form": "validated", "__fields": list(reversed(fields))})
    payload["bindings"] = encoded


def _binding_decode(payload: dict[str, Any]) -> None:
    decoded = []
    keys = ("binder_id", "variable", "type_name", "scope_id", "binder_kind")
    for binding in payload["bindings"]:
        if "__binding_form" not in binding:
            decoded.append(binding)
            continue
        if set(binding) != {"__binding_form", "__fields"}:
            raise ValueError("malformed phenotype binding")
        fields = binding["__fields"]
        form = binding["__binding_form"]
        if not isinstance(fields, list) or len(fields) != 5:
            raise ValueError("phenotype binding needs five fields")
        if form == "structural":
            ordered = fields
        elif form == "nameless":
            ordered = fields[-1:] + fields[:-1]
        elif form == "validated":
            ordered = list(reversed(fields))
        else:
            raise ValueError("unknown phenotype binding form")
        decoded.append(dict(zip(keys, ordered, strict=True)))
    payload["bindings"] = decoded


def _ordered_payload(payload: dict[str, Any], policy: StatePolicy) -> dict[str, Any]:
    order = list(STATE_FIELD_ORDER)
    if policy == StatePolicy.FLAT_LIST:
        order = sorted(order)
    elif policy == StatePolicy.DAG:
        priority = ["bindings", "objects", "assumptions", "evidence_dependencies", "goal"]
        order = priority + [key for key in order if key not in priority]
    elif policy == StatePolicy.GRAPH:
        order = list(reversed(order))
    return {key: payload[key] for key in order}


def _grammar_encode(value: Any, grammar: GrammarFamily, redundancy: RedundancyPolicy) -> str:
    if grammar == GrammarFamily.S_EXPRESSION:
        body = sexpr_encode(value)
    elif grammar in {GrammarFamily.PREFIX, GrammarFamily.HYBRID}:
        body = typed_prefix_encode(value)
    else:
        indent = 2 if redundancy == RedundancyPolicy.HIGH_EXPLICIT else None
        separators = (
            None if indent else (",", ":" if redundancy == RedundancyPolicy.COMPRESSED else ": ")
        )
        body = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=False,
            indent=indent,
            separators=separators,
        )
    # The marker is a grammar declaration, not a candidate/language identity.  It also makes
    # otherwise JSON-shaped grammar families observably distinct.
    return f"GRAMMAR={grammar.value}\n{body}"


def _grammar_decode(source: str, grammar: GrammarFamily) -> Any:
    marker = f"GRAMMAR={grammar.value}\n"
    if not source.startswith(marker):
        raise ValueError("phenotype grammar declaration mismatch")
    source = source[len(marker) :]
    if grammar == GrammarFamily.S_EXPRESSION:
        return sexpr_decode(source)
    if grammar in {GrammarFamily.PREFIX, GrammarFamily.HYBRID}:
        return typed_prefix_decode(source)
    return strict_json_loads(source)


def _wrap(body: str, policy: SerializationPolicy) -> str:
    if policy == SerializationPolicy.LINE_ORIENTED:
        return f"ARENA STATE 1\n{body}"
    if policy == SerializationPolicy.TREE:
        return f"ARENA_TREE[\n{body}\n]"
    if policy == SerializationPolicy.COMPACT_CODE:
        return f"Σ1|{body}"
    return f"STATE ROOT ->\n{body}"


def _unwrap(source: str, policy: SerializationPolicy) -> str:
    if policy == SerializationPolicy.LINE_ORIENTED:
        prefix, suffix = "ARENA STATE 1\n", ""
    elif policy == SerializationPolicy.TREE:
        prefix, suffix = "ARENA_TREE[\n", "\n]"
    elif policy == SerializationPolicy.COMPACT_CODE:
        prefix, suffix = "Σ1|", ""
    else:
        prefix, suffix = "STATE ROOT ->\n", ""
    if not source.startswith(prefix) or (suffix and not source.endswith(suffix)):
        raise ValueError("phenotype serialization envelope mismatch")
    return source[len(prefix) : -len(suffix) if suffix else None]


class GenomePhenotypeLanguage(CandidateLanguage):
    """An executable phenotype whose emitted bytes are determined by its genome."""

    format_id = PHENOTYPE_CODEC_VERSION

    def __init__(self, genome: LanguageGenome) -> None:
        self.genome = genome
        self._roles = _role_map(genome)
        self._inverse_roles = {value: key for key, value in self._roles.items()}

    def _encode_value(self, value: Any) -> str:
        typed = _type_encode(value, self.genome.types)
        roles = _map_keys(typed, self._roles)
        return _grammar_encode(roles, self.genome.grammar, self.genome.redundancy)

    def _decode_value(self, source: str) -> Any:
        raw = _grammar_decode(source, self.genome.grammar)
        roles = _map_keys(raw, self._inverse_roles)
        return _type_decode(roles)

    def _encode_payload(self, payload: dict[str, Any]) -> str:
        transformed = json.loads(json.dumps(payload, ensure_ascii=False))
        _binding_encode(transformed, self.genome.binders)
        transformed = _ordered_payload(transformed, self.genome.state)
        return _wrap(self._encode_value(transformed), self.genome.serialization)

    def _decode_payload(self, source: str) -> dict[str, Any]:
        raw = self._decode_value(_unwrap(source, self.genome.serialization))
        if not isinstance(raw, dict):
            raise ValueError("phenotype state root must be a record")
        _binding_decode(raw)
        return raw

    def render_action_choice(self, action: CanonicalAction) -> str:
        """Render only candidate mathematical results, excluding every oracle-only action field."""

        arguments = [item.to_dict() for item in action.arguments]
        if self.genome.actions == ActionPolicy.FREE_TEXT:
            view: Any = {"candidate_result": arguments}
        elif self.genome.actions == ActionPolicy.TYPED_ACTION:
            view = {"action": {"arguments": arguments}}
        elif self.genome.actions == ActionPolicy.VERB_TARGET_ARGUMENTS:
            view = {"apply": {"target_role": "goal", "arguments": arguments}}
        else:
            view = {"rule": {"premises": [], "conclusion": arguments}}
        return self._encode_value(view)

    def acquisition_guide(self) -> str:
        """Mechanically generated, fixed-budget syntax guide with no candidate identity."""

        return (
            "The state is a lossless typed record. Read its goal, assumptions, bindings, "
            "obligations, evidence dependencies, and propositions. Types use the "
            f"{self.genome.types.value} convention; binders use {self.genome.binders.value}; "
            f"records use {self.genome.grammar.value} grammar and {self.genome.serialization.value} "
            "serialization. Each option contains only a proposed mathematical result. "
            "Select the result that correctly advances the displayed goal."
        )


__all__ = ["GenomePhenotypeLanguage", "PHENOTYPE_CODEC_VERSION"]
