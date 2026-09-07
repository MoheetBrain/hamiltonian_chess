"""Exact ordered inventory recovered from rendered bytes; no semantic normalization guesses."""
from __future__ import annotations

import hashlib
from typing import Any

from arena.languages._json_tools import canonical_json
from .renderer_bridge import REPRESENTATIONS, decode, render, validate_projection
from .schema import CanonicalPremiseSelectionState, visible_projection


def information_inventory(projection: dict[str, Any]) -> tuple[tuple[str, str, str], ...]:
    validate_projection(projection)
    records = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            records.append((path, "object", canonical_json(sorted(value))))
            for key in sorted(value):
                walk(value[key], f"{path}/{key}")
        elif isinstance(value, list):
            records.append((path, "list-length", str(len(value))))
            for i, item in enumerate(value):
                walk(item, f"{path}/{i}")
        else:
            records.append((path, type(value).__name__, canonical_json(value)))
    walk(projection, "")
    return tuple(records)


def assert_parity(state: CanonicalPremiseSelectionState) -> dict[str, Any]:
    expected = information_inventory(visible_projection(state))
    outputs = {}
    for representation in REPRESENTATIONS:
        source = render(state, representation)
        if source != render(state, representation):
            raise ValueError("renderer is nondeterministic")
        actual = information_inventory(decode(source, representation))
        if actual != expected:
            raise ValueError(f"GAME_R_PARITY_FAIL: {representation}")
        outputs[representation] = {"sha256": hashlib.sha256(source.encode()).hexdigest(), "bytes": len(source.encode())}
    if len({o["sha256"] for o in outputs.values()}) != len(REPRESENTATIONS):
        raise ValueError("representations have identical bytes")
    return {"task_id": state.task_id, "projection_sha256": hashlib.sha256(canonical_json(expected).encode()).hexdigest(), "renderers": outputs, "status": "GAME_R_SOURCE_PROJECTION_PARITY_PASS"}
