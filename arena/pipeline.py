"""Operational control plane for building and evaluating the Arena."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arena.assurance.suite import run_assurance_suite
from arena.canonical.schema import SCHEMA_VERSION, canonical_json, stable_hash
from arena.evaluation.static import StaticEvaluation, evaluate_static
from arena.fitness.metrics import Direction
from arena.fitness.pareto import Objective
from arena.genome.schema import LanguageGenome
from arena.languages.registry import get_language, language_for_genome, seed_languages
from arena.league.hall_of_fame import HallOfFameSuite
from arena.league.registry import DEFAULT_BASELINES, LeagueRegistry
from arena.league.selection import rank_registry
from arena.players.architect import Architect
from arena.players.refuter import Refuter
from arena.release import ReleaseDecision, ReleaseEvidence, freeze_release
from arena.reporting import scoreboard_rows, write_scoreboard
from arena.storage.artifacts import ArtifactStore, StoredArtifact
from arena.storage.db import ArenaDatabase
from arena.tasks.generators.world_v0 import DEFAULT_WORLD_SIZE, WORLD_ID, build_world_v0
from arena.verifier.native import NativeVerifier


class ArenaRuntime:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.artifact_root = self.root / "artifacts"
        self.store = ArtifactStore(self.artifact_root)
        self.db = ArenaDatabase(self.artifact_root / "arena.db")

    def _record_artifact(self, artifact: StoredArtifact, kind: str) -> None:
        self.db.record_artifact(
            artifact.artifact_id,
            kind,
            str(artifact.path.relative_to(self.root)),
            artifact.sha256,
        )

    def initialize(self) -> dict[str, Any]:
        for relative in ("candidates", "worlds", "matches", "failures", "reports"):
            (self.artifact_root / relative).mkdir(parents=True, exist_ok=True)
        self.db.initialize()
        self.db.set_metadata("arena_schema", "arena-control-plane-v0.1.0")
        self.db.set_metadata("canonical_schema", SCHEMA_VERSION)
        return {"root": str(self.root), "database": str(self.db.path), "initialized": True}

    def build_worlds(self, *, total: int = DEFAULT_WORLD_SIZE, seed: int = 0) -> dict[str, Any]:
        self.initialize()
        world = build_world_v0(total=total, seed=seed)
        task_lines: list[str] = []
        for task in world.tasks:
            payload = task.to_dict()
            self.db.register_world(
                task.task_id,
                task.dimensions.domain,
                task.trajectory.quality.value,
                payload,
            )
            self.db.register_task(
                task.task_id,
                task.task_id,
                "canonical_trajectory",
                task.dimensions.to_dict(),
            )
            task_lines.append(canonical_json(payload))
        world_hash = stable_hash({"task_hashes": sorted(task.content_hash for task in world.tasks)})
        summary = {
            "world_id": WORLD_ID,
            "world_hash": world_hash,
            "seed": seed,
            "count": world.summary.count,
            "domain_counts": dict(world.summary.domain_counts),
            "quality_counts": dict(world.summary.quality_counts),
            "transitions": sum(len(task.trajectory.transitions) for task in world.tasks),
        }
        tasks_artifact = self.store.write_text(
            "worlds/arena-world-v0.jsonl", "\n".join(task_lines) + "\n"
        )
        summary_artifact = self.store.write_json("worlds/arena-world-v0-summary.json", summary)
        self._record_artifact(tasks_artifact, "canonical-world-jsonl")
        self._record_artifact(summary_artifact, "canonical-world-summary")
        self.db.set_metadata("world_config", {"total": total, "seed": seed})
        self.db.set_metadata("world_hash", world_hash)
        return summary

    def validate_worlds(
        self, *, total: int | None = None, seed: int | None = None
    ) -> dict[str, Any]:
        config = self.db.get_metadata("world_config", {"total": DEFAULT_WORLD_SIZE, "seed": 0})
        world = build_world_v0(
            total=int(total if total is not None else config["total"]),
            seed=int(seed if seed is not None else config["seed"]),
        )
        verifier = NativeVerifier()
        transition_results = [
            verifier.verify_transition(transition)
            for task in world.tasks
            for transition in task.trajectory.transitions
        ]
        legal_action_failures = sum(
            not task.trajectory.initial_state.legal_actions
            or not task.trajectory.initial_state.plausible_invalid_actions
            for task in world.tasks
        )
        gold_without_two_checks = sum(
            task.trajectory.quality.value == "GOLD"
            and any(len(transition.verification) < 2 for transition in task.trajectory.transitions)
            for task in world.tasks
        )
        result = {
            "valid": (
                all(item.accepted for item in transition_results)
                and legal_action_failures == 0
                and gold_without_two_checks == 0
            ),
            "world_id": WORLD_ID,
            "tasks": len(world.tasks),
            "transitions": len(transition_results),
            "native_transition_failures": sum(not item.accepted for item in transition_results),
            "missing_action_pairs": legal_action_failures,
            "gold_without_two_checks": gold_without_two_checks,
        }
        artifact = self.store.write_json("reports/world-validation.json", result)
        self._record_artifact(artifact, "world-validation")
        return result

    def seed_candidate_languages(self) -> dict[str, Any]:
        self.initialize()
        records = []
        for language in seed_languages():
            genome = language.genome
            self.db.register_language(language.candidate_id, genome.grammar.value, genome.to_dict())
            artifact = self.store.write_json(
                f"candidates/{language.candidate_id}/genome.json", genome.to_dict()
            )
            self._record_artifact(artifact, "seed-genome")
            records.append(
                {
                    "candidate_id": language.candidate_id,
                    "format_id": language.format_id,
                    "genome_hash": genome.genome_hash,
                    "candidate_hash": genome.candidate_hash,
                }
            )
        artifact = self.store.write_json(
            "candidates/seeds.json", {"count": len(records), "seeds": records}
        )
        self._record_artifact(artifact, "seed-registry")
        return {"count": len(records), "seeds": records}

    def _genome(self, candidate_id: str) -> LanguageGenome:
        try:
            return get_language(candidate_id).genome
        except KeyError:
            rows = [row for row in self.db.rows("languages") if row["language_id"] == candidate_id]
            if rows:
                return LanguageGenome.from_dict(json.loads(rows[0]["genome_json"]))
            stored = self._stored_genome(candidate_id)
            if stored is None:
                raise KeyError(f"unknown candidate {candidate_id!r}") from None
            return stored

    def _stored_genome(self, candidate_id: str) -> LanguageGenome | None:
        """A genome written by a previous ``mutate()`` wave, read back from the artifact store.

        Mutation wrote ``artifacts/candidates/<id>/genome.json`` and nothing ever read it back,
        so every mutant on disk was unreachable from ``evaluate``.  The id is checked against
        the record it names, which also rules out a path escaping the candidate directory.
        """

        if (
            not candidate_id
            or "/" in candidate_id
            or "\\" in candidate_id
            or candidate_id[0] == "."
        ):
            return None
        path = self.artifact_root / "candidates" / candidate_id / "genome.json"
        if not path.is_file():
            return None
        genome = LanguageGenome.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if genome.candidate_id != candidate_id:
            raise ValueError(f"stored genome for {candidate_id!r} names {genome.candidate_id!r}")
        return genome

    def mutate(self, parent_id: str, *, count: int = 20, seed: int = 0) -> dict[str, Any]:
        self.seed_candidate_languages()
        parent = self._genome(parent_id)
        proposals = Architect().propose(parent, count=count, seed=seed)
        records = []
        for item in proposals:
            genome = item.genome
            mutation = item.mutation
            self.db.register_language(genome.candidate_id, genome.grammar.value, genome.to_dict())
            self.db.register_language_parents(genome.candidate_id, genome.parent_ids)
            self.db.record_mutation(
                mutation.proposal.proposal_id,
                parent_id,
                genome.candidate_id,
                mutation.proposal.to_dict(),
                "GENOME_VALIDATED_RENDERER_PENDING",
            )
            artifact = self.store.write_json(
                f"candidates/{genome.candidate_id}/genome.json", genome.to_dict()
            )
            self._record_artifact(artifact, "mutated-genome")
            records.append(
                {
                    "candidate_id": genome.candidate_id,
                    "parent_id": parent_id,
                    "proposal_id": mutation.proposal.proposal_id,
                    "affected_tests": list(mutation.proposal.affected_tests),
                    "status": "GENOME_VALIDATED_RENDERER_PENDING",
                }
            )
        result = {"parent_id": parent_id, "proposed": len(records), "candidates": records}
        artifact = self.store.write_json(f"reports/mutations-{parent_id}.json", result)
        self._record_artifact(artifact, "mutation-wave")
        return result

    def _world(self) -> tuple[Any, dict[str, int]]:
        config = self.db.get_metadata("world_config", {"total": DEFAULT_WORLD_SIZE, "seed": 0})
        return build_world_v0(total=int(config["total"]), seed=int(config["seed"])), config

    def evaluate(self, candidate_id: str, *, tier: int = 1) -> StaticEvaluation:
        if tier not in {0, 1}:
            raise ValueError("Tier 2 requires the explicit matched-adaptation runner")
        self.initialize()
        self.seed_candidate_languages()
        try:
            genome = self._genome(candidate_id)
        except KeyError as error:
            raise ValueError(
                "candidate has no executable renderer/parser; it cannot enter evaluation"
            ) from error
        # Seeds keep their hand-coded surfaces; every other genome is rendered by the
        # genome-driven phenotype codec, which is what reconnects mutants to evaluation.
        language = language_for_genome(genome)
        world, _ = self._world()
        evaluation = evaluate_static(language, world.tasks)
        result = evaluation.to_dict()
        evaluation_id = self.db.record_evaluation(
            candidate_id,
            evaluation.task_set_hash,
            tier,
            {"pipeline": "static-v0.1.0", "tier": tier},
            "PASS" if evaluation.passed_gate_zero else "ELIMINATED",
            result,
            evaluation.metric_values(),
        )
        artifact = self.store.write_json(
            f"candidates/{candidate_id}/evaluation-tier-{tier}.json", result
        )
        self._record_artifact(artifact, "candidate-evaluation")
        self.db.set_metadata(f"latest_evaluation:{candidate_id}", evaluation_id)
        return evaluation

    def run_league(self, *, tier: int = 1) -> dict[str, Any]:
        self.initialize()
        self.build_worlds(**self.db.get_metadata("world_config", {"total": 676, "seed": 0}))
        self.seed_candidate_languages()
        languages = seed_languages()
        evaluations = tuple(
            self.evaluate(language.candidate_id, tier=tier) for language in languages
        )
        registry = LeagueRegistry()
        candidate_ids = []
        for language, evaluation in zip(languages, evaluations, strict=True):
            candidate_ids.append(language.candidate_id)
            registry.register(
                language.candidate_id,
                language.format_id,
                baseline=language.candidate_id
                in {candidate_id for candidate_id, _ in DEFAULT_BASELINES},
                parent_ids=language.genome.parent_ids,
            )
            registry.set_objectives(
                language.candidate_id,
                {
                    "semantic_fidelity": evaluation.metric_values()["semantic_fidelity"],
                    "composition": evaluation.metric_values()["composition"],
                    "tokens_proxy": evaluation.metric_values()["tokens_proxy"],
                },
            )
        objectives = (
            Objective("semantic_fidelity", Direction.MAXIMIZE),
            Objective("composition", Direction.MAXIMIZE),
            Objective("tokens_proxy", Direction.MINIMIZE),
        )
        fronts = rank_registry(registry, objectives, candidate_ids=candidate_ids)
        league_path = registry.save(self.artifact_root / "matches/league-registry.json")
        league_artifact = self.store.write_text(
            "matches/league-registry.snapshot.json", league_path.read_text(encoding="utf-8")
        )
        self._record_artifact(league_artifact, "league-registry")

        world, _ = self._world()
        hall = HallOfFameSuite.from_tasks(world.tasks)
        for baseline_id in registry.candidates:
            self.db.admit_hall_of_fame(baseline_id, "frozen Arena v0 baseline")
        scoreboard = write_scoreboard(self.store, evaluations, languages)
        for artifact in (scoreboard.json, scoreboard.csv, scoreboard.markdown):
            self._record_artifact(artifact, "scoreboard")
        rows = scoreboard_rows(evaluations, languages)
        match_id = f"match:{stable_hash({'tasks': hall.content_hash, 'participants': candidate_ids, 'tier': tier, 'pipeline': 'static-v0.1.0'})[:20]}"
        match_result = {
            "tier": tier,
            "fronts": [list(front) for front in fronts],
            "hall_of_fame_hash": hall.content_hash,
            "rows": rows,
        }
        self.db.record_match(match_id, hall.content_hash, candidate_ids, match_result)
        artifact = self.store.write_json("matches/latest.json", match_result)
        self._record_artifact(artifact, "league-match")
        return {
            "match_id": match_id,
            "tier": tier,
            "candidates": len(languages),
            "fronts": [list(front) for front in fronts],
            "scoreboard": str(scoreboard.markdown.path.relative_to(self.root)),
        }

    def assure(self, candidate_id: str) -> dict[str, Any]:
        self.initialize()
        world, _ = self._world()
        get_language(candidate_id)
        report = run_assurance_suite(world.tasks[0].trajectory.initial_state)
        refuter = Refuter(NativeVerifier(), self.artifact_root / "failures/failures.jsonl")
        refuter_report = refuter.run(
            candidate_id,
            world.tasks[0].trajectory.initial_state,
            rendered_source=None,
            parser=None,
        )
        result = {
            **report.to_dict(),
            "candidate_id": candidate_id,
            "refuter": {
                "semantic_attacks": refuter_report.semantic_attacks,
                "false_accepts": len(refuter_report.false_accepts),
                "false_rejects": len(refuter_report.false_rejects),
                "novel_failure_classes": list(refuter_report.novel_failure_classes),
            },
            "parser_robustness": self.evaluate(candidate_id, tier=1).to_dict(),
        }
        artifact = self.store.write_json(f"candidates/{candidate_id}/assurance.json", result)
        self._record_artifact(artifact, "assurance-report")
        return result

    def release_decision(self, candidate_id: str) -> ReleaseDecision:
        evaluation = self.evaluate(candidate_id, tier=1)
        world, _ = self._world()
        assurance = run_assurance_suite(world.tasks[0].trajectory.initial_state)
        evidence = ReleaseEvidence(
            unresolved_critical_defects=assurance.critical_failures,
            false_accepts=assurance.false_accepts,
            exhaustive_complete=assurance.exhaustive_complete,
            exhaustive_cases=assurance.exhaustive_cases,
            differential_disagreements=assurance.differential_disagreements,
            side_channel_failures=evaluation.answer_leaks,
            matched_training_runs=len(self.db.rows("training_runs")),
            strong_controls=4,
            material_machine_improvement=False,
        )
        decision = freeze_release(
            get_language(candidate_id),
            evaluation,
            evidence,
            artifact_root=self.artifact_root,
        )
        artifact = self.store.write_json("reports/release-decision.json", decision.to_dict())
        self._record_artifact(artifact, "release-decision")
        return decision

    def status(self) -> dict[str, Any]:
        self.initialize()
        summary = self.db.summary().tables
        scoreboard_path = self.artifact_root / "reports/scoreboard.json"
        release_path = self.artifact_root / "reports/release-decision.json"
        return {
            "arena": "OPERATIONAL",
            "root": str(self.root),
            "database": str(self.db.path.relative_to(self.root)),
            "records": summary,
            "world_config": self.db.get_metadata("world_config"),
            "world_hash": self.db.get_metadata("world_hash"),
            "scoreboard": (
                json.loads(scoreboard_path.read_text(encoding="utf-8"))
                if scoreboard_path.exists()
                else None
            ),
            "release": (
                json.loads(release_path.read_text(encoding="utf-8"))
                if release_path.exists()
                else {"status": "NO_RSTAR_RELEASE", "released": False}
            ),
        }

    def report(self) -> str:
        status = self.status()
        records = status["records"]
        release = status["release"]
        return (
            "# Hamiltonian Arena Status\n\n"
            f"- Arena: {status['arena']}\n"
            f"- Worlds: {records['worlds']}\n"
            f"- Languages: {records['languages']}\n"
            f"- Evaluations: {records['evaluations']}\n"
            f"- Matches: {records['matches']}\n"
            f"- Critical stored failures: {records['failures']}\n"
            f"- R*-V0: {release['status']}\n"
        )
