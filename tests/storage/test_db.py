import hashlib

from arena.storage.artifacts import ArtifactStore
from arena.storage.db import ArenaDatabase


def test_database_initializes_all_required_tables(tmp_path) -> None:
    db = ArenaDatabase(tmp_path / "arena.db")
    db.initialize()
    assert db.summary().tables == {
        "artifacts": 0,
        "evaluations": 0,
        "failures": 0,
        "hall_of_fame": 0,
        "languages": 0,
        "matches": 0,
        "models": 0,
        "mutations": 0,
        "tasks": 0,
        "training_runs": 0,
        "worlds": 0,
    }


def test_database_records_reproducible_language_and_evaluation(tmp_path) -> None:
    db = ArenaDatabase(tmp_path / "arena.db")
    db.initialize()
    genome_hash = db.register_language("L0", "test", {"grammar": "sexpr"})
    evaluation_id = db.record_evaluation(
        "L0", "tasks", 0, {"seed": 0}, "PASSED", {"ok": True}, {"roundtrip": 1}
    )
    assert len(genome_hash) == 64
    assert evaluation_id.startswith("eval:")
    assert db.summary().tables["languages"] == 1
    assert db.summary().tables["evaluations"] == 1

    repeated_id = db.record_evaluation(
        "L0", "tasks", 0, {"seed": 0}, "PASSED", {"ok": True, "run": 2}, {"roundtrip": 1}
    )
    assert repeated_id == evaluation_id
    assert db.summary().tables["evaluations"] == 1


def test_artifact_hash_is_the_actual_file_sha256(tmp_path) -> None:
    artifact = ArtifactStore(tmp_path).write_text("report.txt", "measured\n")
    assert artifact.sha256 == hashlib.sha256(artifact.path.read_bytes()).hexdigest()


def test_artifact_inventory_replaces_stale_content_at_same_path(tmp_path) -> None:
    db = ArenaDatabase(tmp_path / "arena.db")
    db.initialize()
    db.record_artifact("artifact:old", "report", "artifacts/report.json", "old")
    db.record_artifact("artifact:new", "report", "artifacts/report.json", "new")
    rows = db.rows("artifacts")
    assert len(rows) == 1
    assert rows[0]["artifact_id"] == "artifact:new"
