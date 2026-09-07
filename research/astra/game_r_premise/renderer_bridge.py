"""Research envelope codecs derived from the inspected Arena founder implementations.

These are NOT registered founders and NOT mathematical AST adapters. Inner Lean source
is unchanged. Only the organization of the explicitly frozen source projection varies.
"""
from __future__ import annotations

from typing import Any

from arena.languages._json_tools import canonical_json, strict_json_loads
from arena.languages._notation import sexpr_decode, sexpr_encode
from .schema import CanonicalPremiseSelectionState, PROJECTION_VERSION, QUESTION, visible_projection

REPRESENTATIONS = ("structured_english", "json_ast", "sexpr", "hml", "compact_symbolic")
FIELDS = ("projection_version", "question", "formal_system", "context", "goal", "candidates")
LABELS = ("Projection version", "Question", "Formal system", "Local context", "Goal", "Candidate premises")
ALIASES = ("v", "q", "f", "c", "g", "p")


def _keys(value: Any, keys: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("GAME_R_PARITY_FAIL: missing, duplicate or additional fields")


def validate_projection(p: Any) -> dict[str, Any]:
    _keys(p, FIELDS)
    if p["projection_version"] != PROJECTION_VERSION or p["question"] != QUESTION:
        raise ValueError("unknown projection or changed response question")
    if not isinstance(p["formal_system"], str):
        raise ValueError("formal system must be text")
    for field in ("context", "goal"):
        _keys(p[field], ("backend", "text"))
        if any(not isinstance(v, str) for v in p[field].values()):
            raise ValueError("backend fields must be strings")
    if not isinstance(p["candidates"], list) or not 2 <= len(p["candidates"]) <= 26:
        raise ValueError("invalid candidate multiplicity")
    names = []
    for i, candidate in enumerate(p["candidates"]):
        _keys(candidate, ("option_id", "label", "name", "statement"))
        if candidate["option_id"] != f"option_{i + 1:02d}" or candidate["label"] != chr(65 + i):
            raise ValueError("changed option identity/order")
        if not isinstance(candidate["name"], str) or not candidate["name"]:
            raise ValueError("missing candidate name")
        names.append(candidate["name"])
        _keys(candidate["statement"], ("backend", "text"))
        if any(not isinstance(v, str) for v in candidate["statement"].values()):
            raise ValueError("statement fields must be strings")
        if not candidate["statement"]["text"].strip():
            raise ValueError("empty statement")
    if len(names) != len(set(names)):
        raise ValueError("duplicate candidate names")
    return p


def encode_projection(p: dict[str, Any], representation: str) -> str:
    validate_projection(p)
    if representation == "json_ast":
        return canonical_json(p)
    if representation == "sexpr":
        return "(astra-premise-v1 " + sexpr_encode(p) + ")"
    if representation == "structured_english":
        return "\n".join(["ASTRA PREMISE STRUCTURED ENGLISH/1", *[
            f"{label}: {canonical_json(p[key])}" for key, label in zip(FIELDS, LABELS, strict=True)
        ]])
    if representation == "hml":
        return "\n".join(["ASTRA HML-COMPAT PREMISE/1", "premise_state {", *[
            f"  {key} := {canonical_json(p[key])};" for key in FIELDS
        ], "}"])
    if representation == "compact_symbolic":
        return "ΣAP1|" + canonical_json({a: p[k] for a, k in zip(ALIASES, FIELDS, strict=True)})
    raise ValueError(f"REPRESENTATION_COVERAGE_FAILURE: {representation}")


def render(state: CanonicalPremiseSelectionState, representation: str) -> str:
    return encode_projection(visible_projection(state), representation)


def decode(source: str, representation: str) -> dict[str, Any]:
    """Decode only actual model-facing bytes, with no access to canonical input state."""
    if representation == "json_ast":
        p = strict_json_loads(source)
    elif representation == "sexpr":
        prefix = "(astra-premise-v1 "
        if not source.startswith(prefix) or not source.endswith(")"):
            raise ValueError("bad S-expression envelope")
        p = sexpr_decode(source[len(prefix):-1])
    elif representation == "compact_symbolic":
        if not source.startswith("ΣAP1|"):
            raise ValueError("bad compact envelope")
        raw = strict_json_loads(source[len("ΣAP1|"):])
        _keys(raw, ALIASES)
        p = {k: raw[a] for a, k in zip(ALIASES, FIELDS, strict=True)}
    elif representation in {"structured_english", "hml"}:
        lines = source.split("\n")
        is_hml = representation == "hml"
        if is_hml:
            if len(lines) != len(FIELDS) + 3 or lines[:2] != ["ASTRA HML-COMPAT PREMISE/1", "premise_state {"] or lines[-1] != "}":
                raise ValueError("bad HML envelope")
            lines = lines[2:-1]
        else:
            if len(lines) != len(FIELDS) + 1 or lines[0] != "ASTRA PREMISE STRUCTURED ENGLISH/1":
                raise ValueError("bad English envelope")
            lines = lines[1:]
        p = {}
        for line, key, label in zip(lines, FIELDS, LABELS, strict=True):
            prefix = f"  {key} := " if is_hml else f"{label}: "
            if not line.startswith(prefix) or (is_hml and not line.endswith(";")):
                raise ValueError("bad field role/order")
            p[key] = strict_json_loads(line[len(prefix):-1] if is_hml else line[len(prefix):])
    else:
        raise ValueError(f"REPRESENTATION_COVERAGE_FAILURE: {representation}")
    validate_projection(p)
    # Reject decoder-tolerated invisible extras, whitespace variants and duplicates.
    # Every admitted model input has one deterministic canonical spelling per codec.
    if encode_projection(p, representation) != source:
        raise ValueError("non-canonical renderer bytes")
    return p


def founder_coverage() -> dict[str, Any]:
    return {
        "production_founders": "REPRESENTATION_COVERAGE_FAILURE",
        "missing_constructs": [
            "backend-native Lean proof-state/source-signature atoms with honest assurance",
            "ordered premise-citation choices separate from legal CanonicalAction transitions",
            "frozen premise projection independent of private trace evidence",
            "elaborated dependent types, binders, implicit parameters and universe levels",
        ],
        "supported_research_envelopes": list(REPRESENTATIONS),
        "reuse": {
            "json_ast": "arena.languages._json_tools.canonical_json/strict_json_loads",
            "sexpr": "arena.languages._notation.sexpr_encode/sexpr_decode",
            "structured_english": "field-line pattern from arena/languages/structured_english/__init__.py",
            "hml": "assignment-line pattern from arena/languages/hml/__init__.py",
            "compact_symbolic": "alias-record pattern from arena/languages/symbolic/__init__.py",
        },
        "claim": "Lossless source-envelope serialization, not full mathematical AST representation.",
    }
