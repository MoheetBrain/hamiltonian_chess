"""Machine-readable and human-readable Arena scoreboards."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import cast

from arena.evaluation.static import StaticEvaluation
from arena.fitness.metrics import Direction
from arena.fitness.pareto import Objective, ParetoPoint, pareto_ranks
from arena.languages.base import CandidateLanguage
from arena.storage.artifacts import ArtifactStore, StoredArtifact

STATIC_OBJECTIVES = (
    Objective("semantic_fidelity", Direction.MAXIMIZE),
    Objective("composition", Direction.MAXIMIZE),
    Objective("tokens_proxy", Direction.MINIMIZE),
)


@dataclass(frozen=True, slots=True)
class ScoreboardArtifacts:
    json: StoredArtifact
    csv: StoredArtifact
    markdown: StoredArtifact


def scoreboard_rows(
    evaluations: tuple[StaticEvaluation, ...],
    languages: tuple[CandidateLanguage, ...],
) -> list[dict[str, object]]:
    by_id = {language.candidate_id: language for language in languages}
    points = tuple(
        ParetoPoint(
            item.candidate_id,
            {
                "semantic_fidelity": item.metric_values()["semantic_fidelity"],
                "composition": item.metric_values()["composition"],
                "tokens_proxy": item.metric_values()["tokens_proxy"],
            },
        )
        for item in evaluations
        if item.fitness.eligible
    )
    ranks = pareto_ranks(points, STATIC_OBJECTIVES) if points else {}
    rows: list[dict[str, object]] = []
    for item in evaluations:
        language = by_id[item.candidate_id]
        metrics = item.metric_values()
        rows.append(
            {
                "candidate_id": item.candidate_id,
                "parent": ",".join(language.genome.parent_ids),
                "genome_hash": language.genome.genome_hash,
                "format_id": language.format_id,
                "soundness_gate": item.fitness.gate_zero.status.value,
                "coverage": metrics["coverage"],
                "composition": metrics["composition"],
                "roundtrip": metrics["exact_roundtrip"],
                "state_reconstruction": metrics["semantic_fidelity"],
                "next_action_accuracy": "UNMEASURED",
                "invalid_action_rate": "UNMEASURED",
                "ood": "UNMEASURED",
                "tokens_proxy": metrics["tokens_proxy"],
                "compiler_latency_ms": metrics["compiler_latency_ms"],
                "refuter_failures": metrics["critical_false_accepts"],
                "training_performance": "UNMEASURED",
                "pareto_status": (
                    "INELIGIBLE"
                    if not item.fitness.eligible
                    else "FRONTIER"
                    if ranks[item.candidate_id] == 0
                    else f"PARETO_RANK_{ranks[item.candidate_id]}"
                ),
                "promotion_tier": "TIER_1_STATIC",
            }
        )
    return sorted(rows, key=lambda row: str(row["candidate_id"]))


def _markdown(rows: list[dict[str, object]]) -> str:
    header = (
        "| Candidate | Gate 0 | Coverage | Roundtrip | Token proxy | Pareto | Training |\n"
        "|---|---:|---:|---:|---:|---|---|\n"
    )
    body = "".join(
        f"| {row['candidate_id']} | {row['soundness_gate']} | "
        f"{cast(float, row['coverage']):.4f} | {cast(float, row['roundtrip']):.4f} | "
        f"{cast(float, row['tokens_proxy']):.2f} | {row['pareto_status']} | "
        f"{row['training_performance']} |\n"
        for row in rows
    )
    return (
        "# Arena Scoreboard\n\n"
        "Static semantic and efficiency results only. Token counts are a documented byte "
        "proxy; all solver, OOD, and matched-training metrics remain unmeasured.\n\n"
        + header
        + body
    )


def write_scoreboard(
    store: ArtifactStore,
    evaluations: tuple[StaticEvaluation, ...],
    languages: tuple[CandidateLanguage, ...],
) -> ScoreboardArtifacts:
    rows = scoreboard_rows(evaluations, languages)
    json_artifact = store.write_json(
        "reports/scoreboard.json",
        {
            "schema": "arena-scoreboard-v0.1.0",
            "scope": "static semantic and efficiency evaluation",
            "rows": rows,
        },
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    csv_artifact = store.write_text("reports/scoreboard.csv", buffer.getvalue())
    markdown_artifact = store.write_text("reports/scoreboard.md", _markdown(rows))
    return ScoreboardArtifacts(json_artifact, csv_artifact, markdown_artifact)
