"""Permanent, content-addressed counterexample records."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from arena.canonical.schema import canonical_json, stable_hash

FAILURE_SCHEMA_VERSION = "arena-failure-v0.1.0"


def _json_value(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class Failure:
    """A stable failure record matching the Arena directive's external schema.

    Python cannot use ``class`` as a field name, so the attribute is
    :attr:`failure_class` while the serialized key remains exactly ``class``.
    """

    id: str
    candidate: str
    source: Any
    minimized_source: Any
    expected: Any
    observed: Any
    failure_class: str
    severity: str
    root_cause: str
    fix_candidate: str
    regression: bool
    schema_version: str = FAILURE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        candidate: str,
        source: Any,
        minimized_source: Any,
        expected: Any,
        observed: Any,
        failure_class: str,
        severity: str = "CRITICAL",
        root_cause: str = "unresolved",
        fix_candidate: str = "",
        regression: bool = False,
    ) -> Self:
        identity = {
            "schema_version": FAILURE_SCHEMA_VERSION,
            "candidate": candidate,
            "minimized_source": _json_value(minimized_source),
            "expected": _json_value(expected),
            "observed": _json_value(observed),
            "class": failure_class,
        }
        return cls(
            id="failure:" + stable_hash(identity),
            candidate=candidate,
            source=_json_value(source),
            minimized_source=_json_value(minimized_source),
            expected=_json_value(expected),
            observed=_json_value(observed),
            failure_class=failure_class,
            severity=severity,
            root_cause=root_cause,
            fix_candidate=fix_candidate,
            regression=regression,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "candidate": self.candidate,
            "source": _json_value(self.source),
            "minimized_source": _json_value(self.minimized_source),
            "expected": _json_value(self.expected),
            "observed": _json_value(self.observed),
            "class": self.failure_class,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "fix_candidate": self.fix_candidate,
            "regression": self.regression,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        return cls(
            id=str(raw["id"]),
            candidate=str(raw["candidate"]),
            source=raw.get("source"),
            minimized_source=raw.get("minimized_source"),
            expected=raw.get("expected"),
            observed=raw.get("observed"),
            failure_class=str(raw["class"]),
            severity=str(raw["severity"]),
            root_cause=str(raw.get("root_cause", "unresolved")),
            fix_candidate=str(raw.get("fix_candidate", "")),
            regression=bool(raw.get("regression", False)),
            schema_version=str(raw.get("schema_version", FAILURE_SCHEMA_VERSION)),
        )


class FailureStore:
    """Append-only JSONL storage with idempotent content-addressed writes."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def all(self) -> tuple[Failure, ...]:
        if not self.path.exists():
            return ()
        records: list[Failure] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid failure JSONL at line {line_number}") from error
            records.append(Failure.from_dict(raw))
        return tuple(records)

    def append(self, failure: Failure) -> bool:
        """Persist ``failure`` once; return whether a new record was appended."""

        known_ids = {item.id for item in self.all()}
        if failure.id in known_ids:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(failure.to_dict()) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return True

    def extend(self, failures: Iterable[Failure]) -> int:
        return sum(self.append(failure) for failure in failures)
