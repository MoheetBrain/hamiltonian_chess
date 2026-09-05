"""Frozen representation-fitness v1 population, split, and prompt protocol."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from arena.canonical.schema import CanonicalAction, GoldStatus, stable_hash
from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.genome.genes import GENE_ENUMS, GeneFamily, ImpactClass
from arena.genome.schema import LanguageGenome, derive_candidate_id
from arena.genome.seeds import SEED_GENOME_BY_ID, SEED_GENOMES
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.storage.artifacts import ArtifactStore
from arena.tasks.generators.world_v0 import ArenaWorldV0, build_world_v0
from arena.tasks.schema import ArenaTask

EXPERIMENT_VERSION = "arena-representation-fitness-v1"
EXPERIMENT_SEED = 20260905
MUTABLE_FAMILIES = (
    GeneFamily.GRAMMAR,
    GeneFamily.BINDERS,
    GeneFamily.TYPES,
    GeneFamily.STATE,
    GeneFamily.ACTIONS,
    GeneFamily.SERIALIZATION,
    GeneFamily.MORPHOLOGY,
    GeneFamily.REDUNDANCY,
)
TARGET_CHILDREN_PER_PARENT = 15
TARGET_POPULATION = len(SEED_GENOMES) * TARGET_CHILDREN_PER_PARENT


class CandidateStatus(StrEnum):
    MATERIALIZED = "MATERIALIZED"
    GATE0_PASSED = "GATE0_PASSED"
    DEAD_SEMANTIC = "DEAD_SEMANTIC"


@dataclass(frozen=True, slots=True)
class ExecutableCandidate:
    candidate_id: str
    parent_id: str
    genome: LanguageGenome
    mutation_id: str
    mutation_family: str
    mutation_distance: int
    semantic_impact_class: str
    affected_test_slices: tuple[str, ...]
    creation_seed: int
    status: CandidateStatus = CandidateStatus.MATERIALIZED

    @property
    def renderer(self) -> GenomePhenotypeLanguage:
        return GenomePhenotypeLanguage(self.genome)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "genome": self.genome.to_dict(),
            "genome_hash": self.genome.genome_hash,
            "mutation_id": self.mutation_id,
            "mutation_family": self.mutation_family,
            "mutation_distance": self.mutation_distance,
            "renderer": "arena.languages.phenotype.GenomePhenotypeLanguage",
            "parser": "arena.languages.phenotype.GenomePhenotypeLanguage",
            "canonical_mapping": "strict Arena canonical wire roundtrip",
            "semantic_impact_class": self.semantic_impact_class,
            "affected_test_slices": list(self.affected_test_slices),
            "creation_seed": self.creation_seed,
            "status": self.status.value,
        }


def _candidate_for(parent: LanguageGenome, family: GeneFamily, value: str) -> ExecutableCandidate:
    genes = parent.genes_dict()
    genes[family.value] = value
    candidate_id = derive_candidate_id(parent_ids=(parent.candidate_id,), genes=genes, prefix="RF1")
    genome = parent.with_gene_values(
        {family: value}, candidate_id=candidate_id, parent_ids=(parent.candidate_id,)
    )
    mutation_id = (
        "fitness-mutation:"
        + stable_hash({"parent": parent.candidate_id, "family": family.value, "to": value})[:20]
    )
    impact = (
        ImpactClass.SURFACE_ONLY
        if family
        in {
            GeneFamily.GRAMMAR,
            GeneFamily.SERIALIZATION,
            GeneFamily.MORPHOLOGY,
            GeneFamily.REDUNDANCY,
        }
        else ImpactClass.STRUCTURAL_SEMANTIC
    )
    return ExecutableCandidate(
        candidate_id,
        parent.candidate_id,
        genome,
        mutation_id,
        family.value,
        1,
        "SURFACE" if impact == ImpactClass.SURFACE_ONLY else "STRUCTURAL_REPRESENTATIONAL",
        ("gold-roundtrip", "canonical-identity", f"gene:{family.value}"),
        EXPERIMENT_SEED,
    )


def materialize_population() -> tuple[ExecutableCandidate, ...]:
    """Create 120 deterministic one-gene children, evenly across all eight parents."""

    by_parent: dict[str, list[ExecutableCandidate]] = {
        seed.candidate_id: [] for seed in SEED_GENOMES
    }
    # Round-robin by family ensures every parent and axis is represented before second variants.
    for variant_round in range(8):
        for family in MUTABLE_FAMILIES:
            enum_cls = GENE_ENUMS[family]
            for parent in SEED_GENOMES:
                options = sorted(
                    value.value for value in enum_cls if value.value != parent.gene(family)
                )
                if (
                    variant_round < len(options)
                    and len(by_parent[parent.candidate_id]) < TARGET_CHILDREN_PER_PARENT
                ):
                    by_parent[parent.candidate_id].append(
                        _candidate_for(parent, family, options[variant_round])
                    )
    result = tuple(
        candidate for parent in SEED_GENOMES for candidate in by_parent[parent.candidate_id]
    )
    if len(result) != TARGET_POPULATION or len({item.candidate_id for item in result}) != len(
        result
    ):
        raise AssertionError("fitness-v1 population target or identity invariant failed")
    return result


def gate0_candidate(candidate: ExecutableCandidate, tasks: tuple[ArenaTask, ...]) -> dict[str, Any]:
    language = candidate.renderer
    failures: list[dict[str, str]] = []
    collisions: dict[str, str] = {}
    checked = 0
    for task in tasks:
        if task.trajectory.quality != GoldStatus.GOLD:
            continue
        for state in (task.trajectory.initial_state, task.trajectory.final_state):
            checked += 1
            try:
                rendered = language.render(state)
                decoded = language.parse(rendered)
                if decoded.to_dict() != state.to_dict():
                    raise ValueError("decoded canonical state differs")
                previous = collisions.get(rendered)
                if previous is not None and previous != state.artifact_hash:
                    raise ValueError("canonical collision")
                collisions[rendered] = state.artifact_hash
            except Exception as error:
                failures.append({"task_id": task.task_id, "error": str(error)})
                if len(failures) >= 20:
                    break
        if len(failures) >= 20:
            break
    return {
        "candidate_id": candidate.candidate_id,
        "parent_id": candidate.parent_id,
        "mutation_family": candidate.mutation_family,
        "states_checked": checked,
        "required_gold_states": 1040,
        "roundtrip_rate": (checked - len(failures)) / checked if checked else 0.0,
        "canonical_collisions": 0
        if not failures
        else sum("collision" in x["error"] for x in failures),
        "critical_failures": len(failures),
        "status": "GATE0_PASSED" if not failures and checked == 1040 else "DEAD_SEMANTIC",
        "failures": failures,
    }


def frozen_task_split(world: ArenaWorldV0) -> dict[str, Any]:
    """Group-aware partition with structural OOD and no family/domain group overlap."""

    gold = [task for task in world.tasks if task.trajectory.quality == GoldStatus.GOLD]
    groups: dict[str, list[ArenaTask]] = {}
    for task in gold:
        operation = task.tags[2]
        group = f"{task.dimensions.domain}|{operation}"
        groups.setdefault(group, []).append(task)

    ood_groups = {
        group
        for group, tasks in groups.items()
        if max(
            task.dimensions.dependency_depth
            + task.dimensions.scope_depth
            + task.dimensions.composition_count
            + task.dimensions.cross_domain_interaction
            for task in tasks
        )
        >= 5
    }
    partitions: dict[str, list[str]] = {key: [] for key in ("DEV", "SCOUT", "PROMOTION", "OOD")}
    group_assignments: dict[str, str] = {}
    cycle = ("DEV", "SCOUT", "PROMOTION")
    for group in sorted(groups):
        if group in ood_groups:
            partition = "OOD"
        else:
            selector = int(
                hashlib.sha256(f"{EXPERIMENT_SEED}|{group}".encode()).hexdigest()[:8], 16
            )
            partition = cycle[selector % len(cycle)]
        group_assignments[group] = partition
        partitions[partition].extend(
            task.task_id for task in sorted(groups[group], key=lambda x: x.task_id)
        )
    for values in partitions.values():
        values.sort()
    task_by_id = {task.task_id: task for task in gold}

    def balanced_take(partition: str, count: int, *, hardest: bool = False) -> list[str]:
        by_group: dict[str, list[ArenaTask]] = {}
        for task_id in partitions[partition]:
            task = task_by_id[task_id]
            by_group.setdefault(f"{task.dimensions.domain}|{task.tags[2]}", []).append(task)
        for tasks in by_group.values():
            tasks.sort(
                key=lambda task: (
                    -(
                        task.dimensions.reasoning_depth
                        + task.dimensions.dependency_depth
                        + task.dimensions.scope_depth
                        + task.dimensions.composition_count
                    )
                    if hardest
                    else 0,
                    task.task_id,
                )
            )
        selected: list[str] = []
        cursor = 0
        ordered_groups = sorted(by_group)
        while len(selected) < count:
            for group in ordered_groups:
                tasks = by_group[group]
                if cursor < len(tasks) and len(selected) < count:
                    selected.append(tasks[cursor].task_id)
            cursor += 1
        return selected

    calibration = balanced_take("DEV", 16)
    hard_candidates = sorted(
        (task_by_id[task_id] for task_id in partitions["DEV"] if task_id not in calibration),
        key=lambda task: (
            -(
                task.dimensions.reasoning_depth
                + task.dimensions.dependency_depth
                + task.dimensions.scope_depth
                + task.dimensions.composition_count
            ),
            task.task_id,
        ),
    )
    protocol_slices = {
        "CALIBRATION_DEV": calibration,
        "CALIBRATION_HARD_DEV": [task.task_id for task in hard_candidates[:16]],
        "TIER2A_SCOUT": balanced_take("SCOUT", 16),
        "TIER2B_PROMOTION": balanced_take("PROMOTION", 64),
        "OOD": list(partitions["OOD"]),
    }
    identity = {
        "partitions": partitions,
        "groups": group_assignments,
        "protocol_slices": protocol_slices,
    }
    return {
        "schema_version": "arena-fitness-task-split-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "seed": EXPERIMENT_SEED,
        "gold_only": True,
        "group_key": "domain|operation",
        "ood_rule": "group max(dependency_depth+scope_depth+composition_count+cross_domain_interaction) >= 5",
        "partitions": partitions,
        "group_assignments": group_assignments,
        "partition_hashes": {key: stable_hash(value) for key, value in partitions.items()},
        "protocol_slices": protocol_slices,
        "slice_hashes": {key: stable_hash(value) for key, value in protocol_slices.items()},
        "manifest_hash": stable_hash(identity),
    }


def tier2a_candidate_roster() -> tuple[str, ...]:
    """Eight permanent controls plus two one-edit children for every target family."""

    population = materialize_population()
    selected: list[str] = [seed.candidate_id for seed in SEED_GENOMES]
    for family_index, family in enumerate(MUTABLE_FAMILIES):
        eligible = [item for item in population if item.mutation_family == family.value]
        first_parent = SEED_GENOMES[(2 * family_index) % len(SEED_GENOMES)].candidate_id
        second_parent = SEED_GENOMES[(2 * family_index + 1) % len(SEED_GENOMES)].candidate_id
        selected.append(
            next(item.candidate_id for item in eligible if item.parent_id == first_parent)
        )
        selected.append(
            next(item.candidate_id for item in eligible if item.parent_id == second_parent)
        )
    if len(selected) != 24 or len(set(selected)) != len(selected):
        raise AssertionError("Tier 2A roster must contain 24 unique candidates")
    return tuple(selected)


def action_order(task: ArenaTask) -> tuple[tuple[str, CanonicalAction], ...]:
    legal = task.trajectory.initial_state.legal_actions[0]
    invalid = task.trajectory.initial_state.plausible_invalid_actions[0]
    legal_first = (
        int(hashlib.sha256(f"{EXPERIMENT_SEED}|{task.task_id}|options".encode()).hexdigest(), 16)
        % 2
        == 0
    )
    actions = (legal, invalid) if legal_first else (invalid, legal)
    return tuple((chr(ord("A") + index), action) for index, action in enumerate(actions))


def correct_choice(task: ArenaTask) -> str:
    legal_id = task.trajectory.initial_state.legal_actions[0].action_id
    return next(label for label, action in action_order(task) if action.action_id == legal_id)


def build_prompt(candidate: LanguageGenome, task: ArenaTask) -> str:
    """Universal common envelope; only guide/state/option renderings depend on the genome."""

    language = GenomePhenotypeLanguage(candidate)
    observation = project_state_for_observation(
        task.trajectory.initial_state, ObservationKind.NEXT_ACTION
    )
    options = "\n".join(
        f"{label}: {language.render_action_choice(action)}" for label, action in action_order(task)
    )
    return (
        "Choose the next mathematically correct action. Return exactly one JSON object and "
        'nothing else: {"choice":"A"} or {"choice":"B"}.\n'
        "SYNTAX GUIDE:\n"
        f"{language.acquisition_guide()}\n"
        "STATE:\n"
        f"{language.render(observation)}\n"
        "OPTIONS:\n"
        f"{options}\n"
        "ANSWER:"
    )


def prompt_hash(candidate: LanguageGenome, task: ArenaTask) -> str:
    return stable_hash(build_prompt(candidate, task))


def parse_choice(output: str) -> str | None:
    try:
        value = json.loads(output.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict) or set(value) != {"choice"} or value["choice"] not in {"A", "B"}:
        return None
    return str(value["choice"])


def seed_genome(candidate_id: str) -> LanguageGenome:
    return SEED_GENOME_BY_ID[candidate_id]


def materialize_artifacts(root: Path) -> dict[str, Any]:
    """Run Gate 0 and persist the frozen population and split manifests."""

    world = build_world_v0()
    population = materialize_population()
    gates = [gate0_candidate(candidate, world.tasks) for candidate in population]
    status_by_id = {gate["candidate_id"]: gate["status"] for gate in gates}
    population_payload = {
        "schema_version": "arena-fitness-population-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "creation_seed": EXPERIMENT_SEED,
        "construction": "120 deterministic one-gene children; no crossover",
        "candidates": [
            {**candidate.to_dict(), "status": status_by_id[candidate.candidate_id]}
            for candidate in population
        ],
    }
    population_payload["population_hash"] = stable_hash(population_payload["candidates"])
    gate_payload = {
        "schema_version": "arena-fitness-gate0-v1",
        "experiment_version": EXPERIMENT_VERSION,
        "proposals": len(gates),
        "survivors": sum(gate["status"] == "GATE0_PASSED" for gate in gates),
        "dead_semantic": sum(gate["status"] == "DEAD_SEMANTIC" for gate in gates),
        "results": gates,
    }
    store = ArtifactStore(root / "artifacts")
    stored_population = store.write_json(
        "experiments/fitness_v1/candidate_population.json", population_payload
    )
    stored_gates = store.write_json("experiments/fitness_v1/gate0.json", gate_payload)
    split = frozen_task_split(world)
    stored_split = store.write_json("experiments/fitness_v1/task_split.json", split)
    return {
        "population": str(stored_population.path),
        "population_hash": population_payload["population_hash"],
        "gate0": str(stored_gates.path),
        "survivors": gate_payload["survivors"],
        "dead_semantic": gate_payload["dead_semantic"],
        "task_split": str(stored_split.path),
        "task_split_hash": split["manifest_hash"],
    }


__all__ = [
    "EXPERIMENT_VERSION",
    "ExecutableCandidate",
    "action_order",
    "build_prompt",
    "correct_choice",
    "frozen_task_split",
    "gate0_candidate",
    "materialize_population",
    "materialize_artifacts",
    "parse_choice",
    "prompt_hash",
    "tier2a_candidate_roster",
]
