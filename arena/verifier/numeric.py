"""Deterministic numerical falsifier; never treated as a proof of symbolic equality."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from typing import Any

from arena.canonical.schema import CanonicalExpression
from arena.verifier.external import ExternalStatus, ExternalVerdict


class UnsupportedNumericExpression(ValueError):
    pass


def evaluate(node: CanonicalExpression, environment: dict[str, float]) -> float | bool:
    if node.op in {"integer", "nat", "real"}:
        return float(node.value)  # type: ignore[arg-type]
    if node.op == "bool":
        return bool(node.value)
    if node.op == "var" and isinstance(node.value, str):
        return environment[node.value]
    args = [evaluate(item, environment) for item in node.args]
    operations: dict[str, Callable[..., Any]] = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b,
        "pow": lambda a, b: a**b,
        "neg": lambda a: -a,
        "sqrt": math.sqrt,
        "log": math.log,
        "sin": math.sin,
        "cos": math.cos,
        "eq": lambda a, b: math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9),
        "lt": lambda a, b: a < b,
        "le": lambda a, b: a <= b,
        "and": lambda *xs: all(bool(x) for x in xs),
        "or": lambda *xs: any(bool(x) for x in xs),
        "not": lambda x: not bool(x),
        "implies": lambda a, b: (not bool(a)) or bool(b),
    }
    try:
        return operations[node.op](*args)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
        raise UnsupportedNumericExpression(f"{node.op}: {error}") from error


def variables(node: CanonicalExpression) -> set[str]:
    found: set[str] = set()
    if node.op == "var" and isinstance(node.value, str):
        found.add(node.value)
    for child in node.args:
        found.update(variables(child))
    return found


class NumericFalsifier:
    name = "numeric-falsifier"
    version = "0.1.0"

    def check_truth(
        self, proposition: CanonicalExpression, *, samples: int = 32, seed: int = 0
    ) -> ExternalVerdict:
        claim = proposition.content_hash
        rng = random.Random(seed)
        names = sorted(variables(proposition))
        successful = 0
        for _ in range(samples):
            environment = {name: rng.uniform(-8.0, 8.0) for name in names}
            try:
                result = evaluate(proposition, environment)
            except UnsupportedNumericExpression:
                continue
            if not bool(result):
                return ExternalVerdict(
                    self.name,
                    self.version,
                    ExternalStatus.DISAGREE,
                    claim,
                    f"counterexample {environment}",
                )
            successful += 1
        status = ExternalStatus.AGREE if successful else ExternalStatus.UNSUPPORTED
        details = f"{successful}/{samples} defined deterministic samples; not a proof"
        return ExternalVerdict(self.name, self.version, status, claim, details)
