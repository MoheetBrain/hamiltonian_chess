"""Small append-friendly SQLite control plane for Arena experiments."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json, stable_hash

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS languages (
    language_id TEXT PRIMARY KEY,
    genome_hash TEXT NOT NULL,
    genome_json TEXT NOT NULL,
    family TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);
CREATE TABLE IF NOT EXISTS language_parents (
    language_id TEXT NOT NULL REFERENCES languages(language_id),
    parent_id TEXT NOT NULL,
    PRIMARY KEY(language_id, parent_id)
);
CREATE TABLE IF NOT EXISTS mutations (
    mutation_id TEXT PRIMARY KEY,
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    proposal_json TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'PROPOSED',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS worlds (
    world_id TEXT PRIMARY KEY,
    world_hash TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    quality TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL REFERENCES worlds(world_id),
    task_kind TEXT NOT NULL,
    dimensions_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    language_id TEXT NOT NULL,
    task_set_hash TEXT NOT NULL,
    tier INTEGER NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS metrics (
    evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    lower_bound REAL,
    upper_bound REAL,
    PRIMARY KEY(evaluation_id, metric)
);
CREATE TABLE IF NOT EXISTS failures (
    failure_id TEXT PRIMARY KEY,
    language_id TEXT NOT NULL,
    class TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    regression_status TEXT NOT NULL DEFAULT 'OPEN'
);
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    task_set_hash TEXT NOT NULL,
    participants_json TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hall_of_fame (
    language_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    admitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS training_runs (
    run_id TEXT PRIMARY KEY,
    language_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    digest TEXT NOT NULL,
    tokenizer TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class DatabaseSummary:
    tables: dict[str, int]


class ArenaDatabase:
    def __init__(self, path: str | Path = "artifacts/arena.db") -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def set_metadata(self, key: str, value: Any) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata(key, value_json) VALUES (?, ?)",
                (key, canonical_json(value)),
            )

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM metadata WHERE key = ?", (key,)
            ).fetchone()
        return default if row is None else json.loads(row["value_json"])

    def register_language(self, language_id: str, family: str, genome: dict[str, Any]) -> str:
        payload = canonical_json(genome)
        genome_hash = stable_hash(genome)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO languages
                   (language_id, genome_hash, genome_json, family, status)
                   VALUES (?, ?, ?, ?, 'ACTIVE')
                   ON CONFLICT(language_id) DO UPDATE SET
                       genome_hash=excluded.genome_hash,
                       genome_json=excluded.genome_json,
                       family=excluded.family""",
                (language_id, genome_hash, payload, family),
            )
        return genome_hash

    def register_language_parents(self, language_id: str, parent_ids: tuple[str, ...]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM language_parents WHERE language_id = ?", (language_id,))
            connection.executemany(
                "INSERT INTO language_parents(language_id, parent_id) VALUES (?, ?)",
                [(language_id, parent_id) for parent_id in parent_ids],
            )

    def register_world(
        self, world_id: str, domain: str, quality: str, payload: dict[str, Any]
    ) -> str:
        world_hash = stable_hash(payload)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO worlds
                   (world_id, world_hash, domain, quality, payload_json) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(world_id) DO UPDATE SET
                       world_hash=excluded.world_hash,
                       domain=excluded.domain,
                       quality=excluded.quality,
                       payload_json=excluded.payload_json""",
                (world_id, world_hash, domain, quality, canonical_json(payload)),
            )
        return world_hash

    def register_task(
        self,
        task_id: str,
        world_id: str,
        task_kind: str,
        dimensions: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO tasks
                   (task_id, world_id, task_kind, dimensions_json) VALUES (?, ?, ?, ?)""",
                (task_id, world_id, task_kind, canonical_json(dimensions)),
            )

    def record_mutation(
        self,
        mutation_id: str,
        parent_id: str,
        child_id: str,
        proposal: dict[str, Any],
        decision: str = "PROPOSED",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO mutations
                   (mutation_id, parent_id, child_id, proposal_json, decision)
                   VALUES (?, ?, ?, ?, ?)""",
                (mutation_id, parent_id, child_id, canonical_json(proposal), decision),
            )

    def record_failure(
        self,
        failure_id: str,
        language_id: str,
        failure_class: str,
        severity: str,
        payload: dict[str, Any],
        regression_status: str = "OPEN",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO failures
                   (failure_id, language_id, class, severity, payload_json, regression_status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    failure_id,
                    language_id,
                    failure_class,
                    severity,
                    canonical_json(payload),
                    regression_status,
                ),
            )

    def record_match(
        self,
        match_id: str,
        task_set_hash: str,
        participants: list[str],
        result: dict[str, Any],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO matches
                   (match_id, task_set_hash, participants_json, result_json)
                   VALUES (?, ?, ?, ?)""",
                (
                    match_id,
                    task_set_hash,
                    canonical_json(participants),
                    canonical_json(result),
                ),
            )

    def admit_hall_of_fame(self, language_id: str, reason: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO hall_of_fame(language_id, reason) VALUES (?, ?)",
                (language_id, reason),
            )

    def record_artifact(
        self,
        artifact_id: str,
        kind: str,
        path: str,
        sha256: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM artifacts WHERE path = ? AND artifact_id != ?",
                (path, artifact_id),
            )
            connection.execute(
                """INSERT OR REPLACE INTO artifacts
                   (artifact_id, kind, path, sha256, metadata_json) VALUES (?, ?, ?, ?, ?)""",
                (artifact_id, kind, path, sha256, canonical_json(metadata or {})),
            )

    def record_evaluation(
        self,
        language_id: str,
        task_set_hash: str,
        tier: int,
        config: dict[str, Any],
        status: str,
        result: dict[str, Any],
        metrics: dict[str, float],
    ) -> str:
        identity = {
            "language_id": language_id,
            "task_set_hash": task_set_hash,
            "tier": tier,
            "config": config,
        }
        evaluation_id = f"eval:{stable_hash(identity)[:20]}"
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO evaluations
                   (evaluation_id, language_id, task_set_hash, tier, config_hash, status,
                    result_hash, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(evaluation_id) DO UPDATE SET
                       status=excluded.status,
                       result_hash=excluded.result_hash,
                       result_json=excluded.result_json""",
                (
                    evaluation_id,
                    language_id,
                    task_set_hash,
                    tier,
                    stable_hash(config),
                    status,
                    stable_hash(result),
                    canonical_json(result),
                ),
            )
            connection.executemany(
                """INSERT OR REPLACE INTO metrics
                   (evaluation_id, metric, value) VALUES (?, ?, ?)""",
                [(evaluation_id, name, float(value)) for name, value in metrics.items()],
            )
        return evaluation_id

    def rows(self, table: str) -> list[dict[str, Any]]:
        allowed = {
            "metadata",
            "languages",
            "language_parents",
            "mutations",
            "worlds",
            "tasks",
            "evaluations",
            "metrics",
            "failures",
            "matches",
            "hall_of_fame",
            "training_runs",
            "models",
            "artifacts",
        }
        if table not in allowed:
            raise ValueError(f"unknown table {table!r}")
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]

    def summary(self) -> DatabaseSummary:
        self.initialize()
        tables = [
            "languages",
            "mutations",
            "worlds",
            "tasks",
            "evaluations",
            "failures",
            "matches",
            "hall_of_fame",
            "training_runs",
            "models",
            "artifacts",
        ]
        with self.connect() as connection:
            counts = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }
        return DatabaseSummary(counts)


def export_rows(db: ArenaDatabase, table: str, path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(db.rows(table), indent=2, sort_keys=True) + "\n")
