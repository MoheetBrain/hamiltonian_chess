"""Frozen-model scout runner. This measures acquisition, not matched learnability."""

from __future__ import annotations

from dataclasses import dataclass

from arena.players.solver import OllamaSolver, SolverRequest, SolverResponse


@dataclass(frozen=True)
class ScoutConfig:
    model: str
    seed: int = 0
    temperature: float = 0.0
    num_predict: int = 512


def run_scout(
    requests: tuple[SolverRequest, ...], config: ScoutConfig
) -> tuple[SolverResponse, ...]:
    solver = OllamaSolver(config.model)
    return tuple(
        solver.solve(
            request,
            seed=config.seed,
            temperature=config.temperature,
            num_predict=config.num_predict,
        )
        for request in requests
    )
