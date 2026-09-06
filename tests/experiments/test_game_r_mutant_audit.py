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
    }
    base = {**reference, "semantic_recovery": True, "render_signature": "s1", "candidate_id": "x"}
    signatures = {"s1": ["x"], "s2": ["y", "z"]}
    assert classify(base, reference, signatures) == "GAME_R_COMPATIBLE"
    assert classify({**base, "semantic_recovery": False}, reference, signatures) == "OBSOLETE"
    assert (
        classify({**base, "information_inventory_hash": "other"}, reference, signatures)
        == "GAME_P_ONLY"
    )
    assert (
        classify({**base, "derived_relation_hash": "other"}, reference, signatures)
        == "MIXED_CONFOUNDED"
    )
    assert (
        classify({**base, "render_signature": "s2"}, reference, signatures) == "DUPLICATE_BEHAVIOUR"
    )
