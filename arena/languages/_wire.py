"""Strict canonical-state wire validation shared by every candidate surface."""

from __future__ import annotations

import json
import math
from typing import Any, NoReturn

from arena.canonical.schema import SCHEMA_VERSION, CanonicalState


class WireValidationError(ValueError):
    pass


def _fail(path: str, message: str) -> NoReturn:
    raise WireValidationError(f"{path}: {message}")


def _dict(raw: object, path: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        _fail(path, "expected an object")
    if not all(isinstance(key, str) for key in raw):
        _fail(path, "all keys must be strings")
    missing = keys - set(raw)
    extra = set(raw) - keys
    if missing or extra:
        _fail(path, f"field mismatch; missing={sorted(missing)}, unknown={sorted(extra)}")
    return raw


def _list(raw: object, path: str) -> list[Any]:
    if not isinstance(raw, list):
        _fail(path, "expected a list")
    return raw


def _string(raw: object, path: str, *, nullable: bool = False) -> None:
    if nullable and raw is None:
        return
    if not isinstance(raw, str):
        _fail(path, "expected a string")


def _number(raw: object, path: str) -> None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        _fail(path, "expected a finite number")
    if not math.isfinite(float(raw)):
        _fail(path, "number must be finite")


def _expression(raw: object, path: str) -> None:
    if not isinstance(raw, dict):
        _fail(path, "expected an expression object")
    allowed = {"op", "sort", "args", "value", "attributes"}
    if set(raw) - allowed or not {"op", "sort"}.issubset(raw):
        _fail(path, "expression must have op/sort and only canonical expression fields")
    _string(raw["op"], f"{path}.op")
    _string(raw["sort"], f"{path}.sort")
    if "args" in raw:
        for index, item in enumerate(_list(raw["args"], f"{path}.args")):
            _expression(item, f"{path}.args[{index}]")
    if "value" in raw:
        value = raw["value"]
        if value is None or not isinstance(value, (str, int, float, bool)):
            _fail(f"{path}.value", "expected a non-null JSON scalar")
        if isinstance(value, float) and not math.isfinite(value):
            _fail(f"{path}.value", "number must be finite")
    if "attributes" in raw:
        attrs = raw["attributes"]
        if not isinstance(attrs, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in attrs.items()
        ):
            _fail(f"{path}.attributes", "expected a string-to-string object")


def _object(raw: object, path: str) -> None:
    item = _dict(raw, path, {"object_id", "type_name", "value", "shape", "unit"})
    _string(item["object_id"], f"{path}.object_id")
    _string(item["type_name"], f"{path}.type_name")
    if item["value"] is not None:
        _expression(item["value"], f"{path}.value")
    for index, dimension in enumerate(_list(item["shape"], f"{path}.shape")):
        if isinstance(dimension, bool) or not isinstance(dimension, (int, str)):
            _fail(f"{path}.shape[{index}]", "expected an integer or symbolic dimension")
    _string(item["unit"], f"{path}.unit", nullable=True)


def _binding(raw: object, path: str) -> None:
    item = _dict(raw, path, {"binder_id", "variable", "type_name", "scope_id", "binder_kind"})
    for key in item:
        _string(item[key], f"{path}.{key}")


def _obligation(raw: object, path: str) -> None:
    item = _dict(raw, path, {"obligation_id", "proposition", "status", "source"})
    _string(item["obligation_id"], f"{path}.obligation_id")
    _expression(item["proposition"], f"{path}.proposition")
    _string(item["status"], f"{path}.status")
    _string(item["source"], f"{path}.source")


def _evidence(raw: object, path: str) -> None:
    item = _dict(
        raw,
        path,
        {"evidence_id", "status", "dependencies", "authority", "certificate_hash"},
    )
    _string(item["evidence_id"], f"{path}.evidence_id")
    _string(item["status"], f"{path}.status")
    for index, dependency in enumerate(_list(item["dependencies"], f"{path}.dependencies")):
        _string(dependency, f"{path}.dependencies[{index}]")
    _string(item["authority"], f"{path}.authority")
    _string(item["certificate_hash"], f"{path}.certificate_hash", nullable=True)


def _action(raw: object, path: str) -> None:
    item = _dict(
        raw,
        path,
        {
            "action_id",
            "operation",
            "target_ids",
            "arguments",
            "warrant",
            "preconditions",
            "generated_obligations",
            "expected_usefulness",
        },
    )
    _string(item["action_id"], f"{path}.action_id")
    _string(item["operation"], f"{path}.operation")
    for index, target in enumerate(_list(item["target_ids"], f"{path}.target_ids")):
        _string(target, f"{path}.target_ids[{index}]")
    for key in ("arguments", "preconditions"):
        for index, expression in enumerate(_list(item[key], f"{path}.{key}")):
            _expression(expression, f"{path}.{key}[{index}]")
    _string(item["warrant"], f"{path}.warrant")
    for index, obligation in enumerate(
        _list(item["generated_obligations"], f"{path}.generated_obligations")
    ):
        _obligation(obligation, f"{path}.generated_obligations[{index}]")
    _number(item["expected_usefulness"], f"{path}.expected_usefulness")


_STATE_FIELDS = {
    "schema_version",
    "state_id",
    "objects",
    "bindings",
    "assumptions",
    "established_facts",
    "propositions",
    "goal",
    "obligations",
    "evidence_dependencies",
    "local_scope",
    "legal_actions",
    "plausible_invalid_actions",
    "terminal_status",
    "execution_metadata",
}

STATE_FIELD_ORDER = (
    "schema_version",
    "state_id",
    "objects",
    "bindings",
    "assumptions",
    "established_facts",
    "propositions",
    "goal",
    "obligations",
    "evidence_dependencies",
    "local_scope",
    "legal_actions",
    "plausible_invalid_actions",
    "terminal_status",
    "execution_metadata",
)


def validate_state_payload(raw: object) -> dict[str, Any]:
    item = _dict(raw, "$", _STATE_FIELDS)
    _string(item["schema_version"], "$.schema_version")
    if item["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"unsupported schema {item['schema_version']!r}")
    _string(item["state_id"], "$.state_id")

    validators = {
        "objects": _object,
        "bindings": _binding,
        "assumptions": _expression,
        "established_facts": _expression,
        "propositions": _expression,
        "obligations": _obligation,
        "evidence_dependencies": _evidence,
        "legal_actions": _action,
        "plausible_invalid_actions": _action,
    }
    for key, validator in validators.items():
        for index, child in enumerate(_list(item[key], f"$.{key}")):
            validator(child, f"$.{key}[{index}]")
    _expression(item["goal"], "$.goal")
    for index, scope_id in enumerate(_list(item["local_scope"], "$.local_scope")):
        _string(scope_id, f"$.local_scope[{index}]")
    _string(item["terminal_status"], "$.terminal_status")
    metadata = item["execution_metadata"]
    if not isinstance(metadata, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in metadata.items()
    ):
        _fail("$.execution_metadata", "expected a string-to-string object")

    _reject_duplicate_ids(item)
    return item


def _reject_duplicate_ids(raw: dict[str, Any]) -> None:
    for collection, key in (
        ("objects", "object_id"),
        ("bindings", "binder_id"),
        ("obligations", "obligation_id"),
        ("evidence_dependencies", "evidence_id"),
        ("legal_actions", "action_id"),
        ("plausible_invalid_actions", "action_id"),
    ):
        values = [item[key] for item in raw[collection]]
        if len(values) != len(set(values)):
            _fail(f"$.{collection}", f"duplicate {key}")


def payload_to_state(raw: object) -> CanonicalState:
    validated = validate_state_payload(raw)
    state = CanonicalState.from_dict(validated)
    normalized = json.loads(
        json.dumps(state.to_dict(), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    )
    if normalized != validated:
        _fail("$", "payload is not in canonical wire form")
    return state


def state_to_payload(state: CanonicalState) -> dict[str, Any]:
    if not isinstance(state, CanonicalState):
        raise TypeError(f"expected CanonicalState, got {type(state).__name__}")
    normalized = json.loads(
        json.dumps(state.to_dict(), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    )
    return validate_state_payload(normalized)
