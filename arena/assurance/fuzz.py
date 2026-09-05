"""Deterministic parser fuzzing with stable case identities."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from arena.assurance.mutations import grammar_mutations
from arena.canonical.schema import stable_hash


@dataclass(frozen=True, slots=True)
class FuzzCase:
    case_id: str
    operation: str
    source: str
    should_parse: bool


@dataclass(frozen=True, slots=True)
class FuzzResult:
    seed: int
    total: int
    expected_rejections: int
    unexpected_accepts: tuple[FuzzCase, ...]
    unexpected_rejections: tuple[FuzzCase, ...]


def fuzz_cases(source: str, *, seed: int = 0, random_cases: int = 64) -> tuple[FuzzCase, ...]:
    cases = [
        FuzzCase(item.mutation_id, item.operation, item.source, item.expected_parse)
        for item in grammar_mutations(source)
    ]
    if not source:
        return tuple(cases)
    rng = random.Random(seed)
    for index in range(random_cases):
        position = rng.randrange(len(source))
        operation = ("delete", "duplicate", "replace", "insert-control")[index % 4]
        if operation == "delete":
            mutated = source[:position] + source[position + 1 :]
        elif operation == "duplicate":
            mutated = source[:position] + source[position] + source[position:]
        elif operation == "replace":
            mutated = source[:position] + "@" + source[position + 1 :]
        else:
            mutated = source[:position] + "\x00" + source[position:]
        identity = {"seed": seed, "index": index, "operation": operation, "source": mutated}
        cases.append(
            FuzzCase(f"fuzz:{stable_hash(identity)}", operation, mutated, should_parse=False)
        )
    return tuple(cases)


def run_parser_fuzz(
    source: str,
    parser: Callable[[str], object],
    *,
    seed: int = 0,
    random_cases: int = 64,
) -> FuzzResult:
    unexpected_accepts: list[FuzzCase] = []
    unexpected_rejections: list[FuzzCase] = []
    cases = fuzz_cases(source, seed=seed, random_cases=random_cases)
    for case in cases:
        parsed = True
        try:
            parser(case.source)
        except Exception:
            parsed = False
        if parsed and not case.should_parse:
            unexpected_accepts.append(case)
        elif not parsed and case.should_parse:
            unexpected_rejections.append(case)
    return FuzzResult(
        seed,
        len(cases),
        sum(not case.should_parse for case in cases),
        tuple(unexpected_accepts),
        tuple(unexpected_rejections),
    )
