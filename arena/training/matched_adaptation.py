"""Contracts for fair short adaptation; execution is delegated to an explicit runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from arena.canonical.schema import stable_hash


class BudgetMode(StrEnum):
    EXAMPLE_MATCHED = "EXAMPLE_MATCHED"
    TOKEN_COMPUTE_MATCHED = "TOKEN_COMPUTE_MATCHED"


@dataclass(frozen=True)
class AdaptationConfig:
    base_model: str
    base_model_digest: str
    tokenizer: str
    learning_rate: float
    optimizer: str
    seed: int
    update_count: int
    effective_token_budget: int
    example_count: int
    context_length: int
    budget_mode: BudgetMode
    runner: str

    @property
    def config_hash(self) -> str:
        return stable_hash(asdict(self))


@dataclass(frozen=True)
class AdaptationRun:
    run_id: str
    candidate_id: str
    dataset_hash: str
    config: AdaptationConfig
    status: str
    metrics: tuple[tuple[str, float], ...] = ()
    checkpoint_hash: str | None = None
    error: str | None = None


def validate_matched_configs(configs: dict[str, AdaptationConfig]) -> None:
    if len(configs) < 2:
        raise ValueError("matched comparison requires at least two candidate surfaces")
    ignored = {"effective_token_budget", "example_count"}
    references: set[tuple[tuple[str, object], ...]] = set()
    modes = {config.budget_mode for config in configs.values()}
    if len(modes) != 1:
        raise ValueError("all candidates must use the same budget mode")
    for config in configs.values():
        raw = asdict(config)
        if config.budget_mode == BudgetMode.EXAMPLE_MATCHED:
            ignored_for_mode = ignored - {"example_count"}
        else:
            ignored_for_mode = ignored - {"effective_token_budget"}
        comparable = tuple(
            sorted((key, value) for key, value in raw.items() if key not in ignored_for_mode)
        )
        references.add(comparable)
    if len(references) != 1:
        raise ValueError("adaptation configurations are not matched")
