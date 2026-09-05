from __future__ import annotations

from dataclasses import replace

from arena.canonical.schema import GoldStatus
from arena.experiments.fitness_v1 import (
    MUTABLE_FAMILIES,
    action_order,
    build_prompt,
    correct_choice,
    frozen_task_split,
    gate0_candidate,
    materialize_population,
    parse_choice,
)
from arena.genome.seeds import SEED_GENOMES
from arena.tasks.generators.world_v0 import build_world_v0


def test_materialized_population_is_reproducible_balanced_and_one_gene() -> None:
    first = materialize_population()
    second = materialize_population()
    assert [item.to_dict() for item in first] == [item.to_dict() for item in second]
    assert len(first) == 120
    assert len({item.candidate_id for item in first}) == 120
    assert {item.mutation_family for item in first} == {item.value for item in MUTABLE_FAMILIES}

    parents = {seed.candidate_id: seed for seed in SEED_GENOMES}
    assert {parent: sum(item.parent_id == parent for item in first) for parent in parents} == {
        parent: 15 for parent in parents
    }
    for item in first:
        parent = parents[item.parent_id]
        differences = {
            key
            for key, value in item.genome.genes_dict().items()
            if value != parent.genes_dict()[key]
        }
        assert differences == {item.mutation_family}
        assert item.mutation_distance == 1


def test_every_phenotype_roundtrips_representative_gold_states() -> None:
    world = build_world_v0()
    gold = [task for task in world.tasks if task.trajectory.quality == GoldStatus.GOLD]
    sample = tuple(gold[::40])
    for candidate in materialize_population():
        result = gate0_candidate(candidate, sample)
        # gate0's full-corpus cardinality deliberately prevents promotion from this sample,
        # but every sampled state must still decode identically.
        assert result["critical_failures"] == 0


def test_each_mutated_gene_changes_renderer_bytes() -> None:
    world = build_world_v0()
    default_state = world.tasks[1].trajectory.initial_state
    binding_state = next(
        task.trajectory.initial_state
        for task in world.tasks
        if task.trajectory.initial_state.bindings
    )
    parents = {seed.candidate_id: seed for seed in SEED_GENOMES}
    for child in materialize_population():
        state = binding_state if child.mutation_family == "binders" else default_state
        parent_text = type(child.renderer)(parents[child.parent_id]).render(state)
        child_text = child.renderer.render(state)
        if child.mutation_family == "actions":
            action = state.legal_actions[0]
            parent_text = type(child.renderer)(parents[child.parent_id]).render_action_choice(
                action
            )
            child_text = child.renderer.render_action_choice(action)
        assert child_text != parent_text, (child.candidate_id, child.mutation_family)


def test_split_is_frozen_disjoint_gold_only_and_group_aware() -> None:
    world = build_world_v0()
    manifest = frozen_task_split(world)
    assert manifest == frozen_task_split(world)
    partitions = manifest["partitions"]
    assert {key: len(value) for key, value in partitions.items()} == {
        "DEV": 160,
        "SCOUT": 120,
        "PROMOTION": 160,
        "OOD": 80,
    }
    sets = [set(value) for value in partitions.values()]
    assert len(set.union(*sets)) == sum(map(len, sets)) == 520
    task_by_id = {task.task_id: task for task in world.tasks}
    assert all(
        task_by_id[task_id].trajectory.quality == GoldStatus.GOLD
        for task_ids in partitions.values()
        for task_id in task_ids
    )
    for group, partition in manifest["group_assignments"].items():
        domain, operation = group.split("|", 1)
        ids = {
            task.task_id
            for task in world.tasks
            if task.dimensions.domain == domain
            and task.tags[2] == operation
            and task.trajectory.quality == GoldStatus.GOLD
        }
        assert ids <= set(partitions[partition])


def test_prompt_and_action_order_are_deterministic_and_label_clean() -> None:
    task = build_world_v0().tasks[0]
    genome = SEED_GENOMES[0]
    assert action_order(task) == action_order(task)
    assert correct_choice(task) in {"A", "B"}
    prompt = build_prompt(genome, task)
    assert prompt == build_prompt(genome, task)
    forbidden = (
        task.task_id,
        genome.candidate_id,
        "action:",
        "invalid_",
        "plausible distractor",
        "expected_usefulness",
        "requested_quality",
    )
    assert all(token not in prompt for token in forbidden)

    swapped_identity = replace(task, task_id=task.task_id + ":copy")
    assert action_order(swapped_identity) != ()
    # The choice is derived from task identity, never candidate identity.
    assert [label for label, _ in action_order(task)] == ["A", "B"]
    assert correct_choice(task) == correct_choice(task)


def test_choice_parser_is_strict() -> None:
    assert parse_choice('{"choice":"A"}') == "A"
    assert parse_choice('{"choice":"B"}') == "B"
    assert parse_choice("A") is None
    assert parse_choice('{"choice":"A","explanation":"x"}') is None
    assert parse_choice('{"choice":"C"}') is None
