from __future__ import annotations

from arena.experiments.fitness_v4 import MECHANISMS, V4Slice, derive_probe_family
from arena.experiments.game_r_mutant_audit import audit_genome, classify
from arena.genome.seeds import SEED_GENOME_BY_ID


def test_seeds_share_information_and_derived_inventories_but_not_bytes() -> None:
    probes = [derive_probe_family(mechanism, 1, V4Slice.DEV, 3)[0] for mechanism in MECHANISMS]
    rows = {
        seed_id: audit_genome(genome, f"V4E_{seed_id}", probes)
        for seed_id, genome in SEED_GENOME_BY_ID.items()
    }
    reference = rows["L3_JSON_AST"]
    for row in rows.values():
        assert row["semantic_recovery"]
        assert row["information_inventory_hash"] == reference["information_inventory_hash"]
        assert row["derived_relation_hash"] == reference["derived_relation_hash"]
        assert row["option_inventory_hash"] == reference["option_inventory_hash"]
    assert len({row["render_signature"] for row in rows.values()}) == len(rows)


def test_classifier_separates_r_p_mixed_duplicate_and_obsolete() -> None:
    reference = {
        "information_inventory_hash": "i",
        "derived_relation_hash": "d",
        "option_inventory_hash": "o",
        "surface_information_hash": "s",
    }
    base = {**reference, "semantic_recovery": True, "render_signature": "s1", "candidate_id": "x"}
    signatures = {"s1": ["x"], "s2": ["y", "z"]}
    assert classify(base, reference, signatures) == "GAME_R_COMPATIBLE"
    assert classify({**base, "semantic_recovery": False}, reference, signatures) == "OBSOLETE"
    assert (
        classify({**base, "surface_information_hash": "other"}, reference, signatures)
        == "GAME_P_ONLY"
    )
    assert (
        classify({**base, "derived_relation_hash": "other"}, reference, signatures)
        == "MIXED_CONFOUNDED"
    )
    assert (
        classify({**base, "render_signature": "s2"}, reference, signatures) == "DUPLICATE_BEHAVIOUR"
    )


def test_surface_inventory_detects_a_real_game_p_violation() -> None:
    """The old recovered-state inventory could not fire; this one must.

    A candidate that renders a derived relation and silently drops it on parse still
    recovers the canonical state, so every semantic check passes. Only an inventory of what
    was actually put on the page can see it.
    """

    from dataclasses import replace

    from arena.canonical.schema import CanonicalExpression
    from arena.experiments.fitness_v4 import V4Slice as _Slice
    from arena.experiments.fitness_v4 import derive_probe_family as _family
    from arena.experiments.game_r_mutant_audit import (
        information_inventory,
        prompt_information_inventory,
    )
    from arena.languages.phenotype import GenomePhenotypeLanguage

    probe = _family("transitive_dependency", 2, _Slice.DEV, 7)[0]
    genome = SEED_GENOME_BY_ID["L3_JSON_AST"]
    honest = GenomePhenotypeLanguage(genome)

    class SmuggleIntoField(GenomePhenotypeLanguage):
        def render(self, state):  # type: ignore[no-untyped-def]
            edges = tuple(
                CanonicalExpression(
                    "depends_on",
                    (
                        CanonicalExpression("symbol", value=node.evidence_id, sort="Identifier"),
                        CanonicalExpression("symbol", value=dep, sort="Identifier"),
                    ),
                    sort="Proposition",
                )
                for node in state.evidence_dependencies
                for dep in node.dependencies
            )
            return super().render(
                replace(state, established_facts=(*state.established_facts, *edges))
            )

        def parse(self, source):  # type: ignore[no-untyped-def]
            state = super().parse(source)
            return replace(
                state,
                established_facts=tuple(
                    item for item in state.established_facts if item.op != "depends_on"
                ),
            )

    smuggler = SmuggleIntoField(genome)
    recovered = smuggler.parse(smuggler.render(probe.state))

    assert recovered.mathematical_hash == probe.state.mathematical_hash
    assert information_inventory(recovered) == information_inventory(probe.state)
    assert prompt_information_inventory(honest, probe.state) != prompt_information_inventory(
        smuggler, probe.state
    )
