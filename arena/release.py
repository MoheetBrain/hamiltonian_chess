"""Fail-closed R*-V0 release decision and package freezer."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from arena.evaluation.static import StaticEvaluation
from arena.languages.base import CandidateLanguage
from arena.storage.artifacts import ArtifactStore


class ReleaseStatus(StrEnum):
    RELEASED = "RSTAR_V0_FROZEN_READY_FOR_10K_MATCHED_TRAINING"
    NO_WINNER = "ARENA_OPERATIONAL_BUT_NO_RSTAR_WINNER"
    BLOCKED_SOUNDNESS = "RSTAR_BLOCKED_BY_SOUNDNESS"
    BLOCKED_MODEL_FITNESS = "RSTAR_BLOCKED_BY_MODEL_FITNESS"


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    unresolved_critical_defects: int
    false_accepts: int
    exhaustive_complete: bool
    exhaustive_cases: int
    differential_disagreements: int
    side_channel_failures: int
    matched_training_runs: int
    strong_controls: int
    material_machine_improvement: bool


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    candidate_id: str | None
    status: ReleaseStatus
    gates: tuple[tuple[str, bool, str], ...]

    @property
    def released(self) -> bool:
        return self.status == ReleaseStatus.RELEASED

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "released": self.released,
            "gates": [
                {"name": name, "passed": passed, "details": details}
                for name, passed, details in self.gates
            ],
        }


def decide_release(
    evaluation: StaticEvaluation | None, evidence: ReleaseEvidence
) -> ReleaseDecision:
    candidate_id = evaluation.candidate_id if evaluation else None
    gates = (
        (
            "candidate_selected",
            evaluation is not None,
            "a concrete executable candidate must be selected",
        ),
        (
            "static_semantics",
            bool(evaluation and evaluation.passed_gate_zero),
            "Gate 0 and exact required-world roundtrip",
        ),
        (
            "critical_defects",
            evidence.unresolved_critical_defects == 0 and evidence.false_accepts == 0,
            f"unresolved={evidence.unresolved_critical_defects}; false_accepts={evidence.false_accepts}",
        ),
        (
            "bounded_exhaustive",
            evidence.exhaustive_complete and evidence.exhaustive_cases > 0,
            f"complete={evidence.exhaustive_complete}; cases={evidence.exhaustive_cases}",
        ),
        (
            "differential",
            evidence.differential_disagreements == 0,
            f"unresolved_disagreements={evidence.differential_disagreements}",
        ),
        (
            "side_channels",
            evidence.side_channel_failures == 0,
            f"critical_findings={evidence.side_channel_failures}",
        ),
        (
            "matched_learning",
            evidence.matched_training_runs > 0 and evidence.strong_controls >= 4,
            f"runs={evidence.matched_training_runs}; controls={evidence.strong_controls}",
        ),
        (
            "material_machine_improvement",
            evidence.material_machine_improvement,
            "must beat a strong control after matched adaptation",
        ),
    )
    if all(passed for _, passed, _ in gates):
        status = ReleaseStatus.RELEASED
    elif evaluation is None:
        status = ReleaseStatus.NO_WINNER
    elif any(
        not passed
        for name, passed, _ in gates
        if name
        in {
            "static_semantics",
            "critical_defects",
            "bounded_exhaustive",
            "differential",
            "side_channels",
        }
    ):
        status = ReleaseStatus.BLOCKED_SOUNDNESS
    else:
        status = ReleaseStatus.BLOCKED_MODEL_FITNESS
    return ReleaseDecision(candidate_id, status, gates)


def freeze_release(
    language: CandidateLanguage,
    evaluation: StaticEvaluation,
    evidence: ReleaseEvidence,
    *,
    artifact_root: str | Path = "artifacts",
) -> ReleaseDecision:
    """Create a minimal executable release record only when every gate passes."""

    decision = decide_release(evaluation, evidence)
    if not decision.released:
        return decision
    store = ArtifactStore(artifact_root)
    prefix = Path("rstar/v0")
    store.write_json(prefix / "genome.json", language.genome.to_dict())
    store.write_json(prefix / "results/static.json", evaluation.to_dict())
    store.write_json(prefix / "results/release_evidence.json", asdict(evidence))
    store.write_text(
        prefix / "RSTAR_SPEC.md",
        "# R*-V0\n\n"
        f"Frozen executable candidate: `{language.candidate_id}`.\n\n"
        "This release claim applies only to the stored bounded assurance suite.\n",
    )
    store.write_text(
        prefix / "limitations.md",
        "# Limitations\n\nNo claim of mathematical perfection or global optimality is made.\n",
    )
    store.write_json(prefix / "hashes.json", {"candidate_hash": language.genome.candidate_hash})
    return decision
