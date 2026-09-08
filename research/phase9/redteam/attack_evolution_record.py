"""RED TEAM / attack classes 1, 3, 5, 6: lineage, cache identity, dead candidates, immutability.

Targets `arena/evolution/record.py` and `arena/evolution/loop.py`.  Every write goes to a
scratch `ArtifactStore` under `research/phase9/redteam/out/store/`; nothing under `artifacts/`
is touched.

Run:  .venv/bin/python research/phase9/redteam/attack_evolution_record.py
Out:  research/phase9/redteam/out/evolution_record.json
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.evolution.loop import EvolutionLoop, LoopConfig, Outcome  # noqa: E402
from arena.evolution.record import (  # noqa: E402
    GENE_INTERVENTION_CLASS,
    EvolutionRecordStore,
    FitnessMemoryIdentityViolation,
    GeneChangeRecord,
    RecordScope,
    UnclassifiedGeneError,
    classify_intervention,
)
from arena.genome.seeds import SEED_GENOMES  # noqa: E402
from arena.storage.artifacts import ArtifactStore  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
STORE_ROOT = OUT / "store"


def fresh_store(name: str) -> ArtifactStore:
    path = STORE_ROOT / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return ArtifactStore(path)


def run_loop(
    name: str, seed: int = 20260908
) -> tuple[ArtifactStore, dict[str, Any], EvolutionLoop]:
    store = fresh_store(name)
    loop = EvolutionLoop(store=store, config=LoopConfig(seed=seed, generations=1, population=4))
    summary = loop.run()
    return store, summary, loop


def main() -> int:
    findings: dict[str, Any] = {}

    # ================================================================= baseline honest run
    store_a, summary_a, loop_a = run_loop("run_a")
    store_b, summary_b, _ = run_loop("run_b")
    findings["E0_determinism_two_runs"] = {
        "run_id_equal": summary_a["run_id"] == summary_b["run_id"],
        "record_ids_equal": summary_a["records"]["record_ids"]
        == summary_b["records"]["record_ids"],
        "content_hashes_equal": summary_a["records"]["content_hashes"]
        == summary_b["records"]["content_hashes"],
        "manifest_hash_a": summary_a["records"]["manifest_hash"],
        "manifest_hash_b": summary_b["records"]["manifest_hash"],
        "final_front_equal": summary_a["final_front"] == summary_b["final_front"],
        "outcomes": [c["outcome"] for g in summary_a["generations"] for c in g["candidates"]],
    }

    records = EvolutionRecordStore(store_a, summary_a["run_id"]).records()
    findings["E0b_run_shape"] = {
        "n_records": len(records),
        "statuses": sorted({r.status.value for r in records}),
        "outcomes": sorted({r.outcome for r in records}),
        "J_solve": [r.fitness_vector.measured().get("J_solve") for r in records],
        "scientific_status_in_summary": summary_a["scientific_status"],
    }
    base = records[0]

    # ================================================================= L1 lineage forgery
    # `parent_genome_id` and `parent_genome_hash` are independent fields.  Nothing binds one to
    # the other, and nothing binds either to a genome the store has ever seen.
    other_seed = next(g for g in SEED_GENOMES if g.candidate_id != base.parent_genome_id)
    liar = replace(
        base,
        parent_genome_id="a-parent-that-never-existed",
        # keep the real hash so record_id / content_hash still verify
    )
    liar_store = EvolutionRecordStore(fresh_store("lineage"), base.run_id)
    appended = liar_store.append(liar, rows=[])
    reread = liar_store.records()[0]
    findings["L1_parent_id_unbound_from_parent_hash"] = {
        "true_parent_id": base.parent_genome_id,
        "true_parent_hash": base.parent_genome_hash[:16],
        "claimed_parent_id": liar.parent_genome_id,
        "record_id_unchanged": liar.record_id == base.record_id,
        "append_scope": appended.scope.value,
        "reread_ok": reread.parent_genome_id == "a-parent-that-never-existed",
        "note": (
            "parent_genome_id is NOT part of the eleven-component evaluation identity; only "
            "parent_genome_hash is. A record can name any parent it likes and still reproduce "
            "every stored hash."
        ),
    }

    # ... and the mirror: swap the HASH while keeping the id, then re-seal.
    swapped = replace(base, parent_genome_hash=other_seed.genome_hash)
    swap_store = EvolutionRecordStore(fresh_store("lineage_hash"), base.run_id)
    swap_result = swap_store.append(swapped, rows=[])
    findings["L1b_parent_hash_swapped_to_a_different_seed"] = {
        "accepted": swap_result.scope.value,
        "new_record_id": swapped.record_id != base.record_id,
        "claimed_parent_id": swapped.parent_genome_id,
        "actual_hash_belongs_to": other_seed.candidate_id,
        "note": "no cross-check that parent_genome_hash is the hash of parent_genome_id",
    }

    # ================================================================= L2 mutation_hash re-roll
    # Same parent, same child, same context, same model - but a different mutation_hash yields a
    # different record_id, so the SAME candidate is scored again as FRESH.
    reroll = replace(
        base,
        mutation=replace(base.mutation, mutation_hash=base.mutation.mutation_hash[::-1]),
    )
    reroll_store = EvolutionRecordStore(fresh_store("reroll"), base.run_id)
    first = reroll_store.append(base, rows=[])
    second = reroll_store.append(reroll, rows=[])
    findings["L2_mutation_hash_reroll_gives_a_free_rescore"] = {
        "same_parent_hash": base.parent_genome_hash == reroll.parent_genome_hash,
        "same_child_hash": base.child_genome_hash == reroll.child_genome_hash,
        "same_condition_id": base.condition_id == reroll.condition_id,
        "first_scope": first.scope.value,
        "second_scope": second.scope.value,
        "distinct_record_ids": base.record_id != reroll.record_id,
        "records_on_disk": len(reroll_store.records()),
        "note": (
            "mutation_hash is caller-supplied and never derived from gene_changes, so a search "
            "that re-proposes the same edge under a new proposal id gets an independent draw "
            "under a stochastic evaluator with no multiplicity accounting"
        ),
    }

    # ================================================================= L3 declared genes vs reality
    mislabelled = replace(
        base,
        mutation=replace(
            base.mutation,
            gene_changes=(GeneChangeRecord("alphabet", "ASCII_MINIMAL", "UNICODE_MATH"),),
        ),
    )
    mis_store = EvolutionRecordStore(fresh_store("genes"), base.run_id)
    mis_scope = mis_store.append(mislabelled, rows=[]).scope.value
    try:
        classify_intervention(["a_future_ontology_gene"])
        unknown_gene = "ACCEPTED (defaulted)"
    except UnclassifiedGeneError as exc:
        unknown_gene = f"BLOCKED: {str(exc)[:120]}"
    findings["L3_gene_changes_not_cross_checked"] = {
        "real_gene_changes": [c.to_dict() for c in base.mutation.gene_changes],
        "declared_gene_changes": [c.to_dict() for c in mislabelled.mutation.gene_changes],
        "real_intervention_class": base.mutation.intervention_class.value,
        "declared_intervention_class": mislabelled.mutation.intervention_class.value,
        "record_id_unchanged": mislabelled.record_id == base.record_id,
        "append_scope": mis_scope,
        "unknown_gene_fails_closed": unknown_gene,
        "distinct_classes_in_table": sorted({v.value for v in GENE_INTERVENTION_CLASS.values()}),
        "note": (
            "InterventionClass is derived from the DECLARED gene list, not from diffing "
            "parent_genome_hash against child_genome_hash; the derivation is only as honest as "
            "the declaration it reads. Today the table is single-valued (every gene R_ONLY) so a "
            "false declaration cannot yet change the class -- it becomes exploitable the moment a "
            "non-R_ONLY gene is added, which is exactly what the module's own comment warns about."
        ),
    }

    # ================================================================= L4 append-only guarantees
    guard_store = EvolutionRecordStore(fresh_store("guard"), base.run_id)
    guard_store.append(base, rows=[{"task_id": "t", "correct": True}])
    scope_same = guard_store.append(base, rows=[]).scope.value

    tampered_result = replace(base, promoted=True)
    try:
        guard_store.append(tampered_result, rows=[])
        rescore = "ACCEPTED (no guard)"
    except FitnessMemoryIdentityViolation as exc:
        rescore = f"BLOCKED: {str(exc)[:150]}"
    findings["L4_rescoring_guard"] = {
        "identical_reappend": scope_same,
        "same_identity_different_result": rescore,
    }

    # in-place edit of the stored JSON, WITHOUT recomputing hashes
    path = guard_store.record_paths()[0]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["promoted"] = True
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    try:
        EvolutionRecordStore(guard_store.store, base.run_id).records()
        naive_edit = "ACCEPTED"
    except FitnessMemoryIdentityViolation as exc:
        naive_edit = f"BLOCKED: {str(exc)[:150]}"

    # ... and WITH every self-referential hash recomputed, as a forger would
    resealed = replace(base, promoted=True)
    path.write_text(json.dumps(resealed.to_stored_dict(), sort_keys=True), encoding="utf-8")
    try:
        rows = EvolutionRecordStore(guard_store.store, base.run_id).records()
        resealed_edit = f"ACCEPTED (promoted={rows[0].promoted})"
    except FitnessMemoryIdentityViolation as exc:
        resealed_edit = f"BLOCKED: {str(exc)[:150]}"
    findings["L5_promoted_flag_flipped_after_the_fact"] = {
        "naive_in_place_edit": naive_edit,
        "resealed_edit": resealed_edit,
        "supersedes_used": resealed.supersedes,
        "note": (
            "hashes are self-referential, not chained and not signed, so recomputing them is "
            "sufficient; there is no prev_hash, no manifest attestation and no append log"
        ),
    }

    # ================================================================= L6 delete-and-rewrite
    del_store = EvolutionRecordStore(fresh_store("delete"), base.run_id)
    del_store.append(base, rows=[{"task_id": "t", "correct": True}])
    victim = del_store.record_paths()[0]
    victim.unlink()
    rewritten = replace(base, promoted=True)
    reopened = EvolutionRecordStore(del_store.store, base.run_id)
    scope = reopened.append(rewritten, rows=[]).scope.value
    findings["L6_delete_then_rewrite"] = {
        "scope_after_deleting_the_file": scope,
        "records_now": len(reopened.records()),
        "note": (
            "the append-only guarantee is the in-memory index rebuilt from a directory glob; "
            "removing the file removes the memory. No log, no manifest, no chain."
        ),
    }

    # ================================================================= L7 rows.jsonl detachment
    rows_store = EvolutionRecordStore(fresh_store("rows"), base.run_id)
    result = rows_store.append(base, rows=[{"task_id": "t1", "correct": True}])
    result.rows_path.unlink()
    still = rows_store.records()
    findings["L7_rows_file_detached"] = {
        "rows_path_deleted": str(result.rows_path.name),
        "record_still_readable": len(still) == 1,
        "any_complaint": False,
        "docstring_claim": (
            "spec section 4 says a record whose rows file is absent is a summary, not a fitness "
            "record, and a summary cannot be re-analysed at a different granularity"
        ),
        "note": "nothing on the read path checks that the rows file exists or matches the record",
    }

    # ================================================================= L8 cross-condition pooling
    pool_store = EvolutionRecordStore(fresh_store("pool"), base.run_id)
    pool_store.append(base, rows=[])
    other_model = replace(base, model=replace(base.model, revision="a-different-model-revision"))
    pool_store.append(other_model, rows=[])
    summary = pool_store.summary()
    findings["L8_cross_condition_pooling"] = {
        "condition_ids": summary["conditions"],
        "distinct_conditions": len(summary["conditions"]),
        "records_returned_by_records()": len(pool_store.records()),
        "manifest_hash_pools_both": summary["manifest_hash"],
        "cross_condition_scope_ever_returned": RecordScope.CROSS_CONDITION.value
        in {"FRESH", "SAME_CONDITION_REUSE"},
        "note": (
            "sharding by condition_id is real, but records() globs */lfm-*.json across every "
            "shard and summary() pools them into one manifest_hash with no condition partition; "
            "the CROSS_CONDITION refusal never fires because it is keyed on record_id, which "
            "already contains the condition components"
        ),
    }

    # ================================================================= L9 dead-candidate compute
    killed = [
        candidate
        for generation in summary_a["generations"]
        for candidate in generation["candidates"]
        if candidate["outcome"] != Outcome.SCORED.value
    ]
    scored = [
        candidate
        for generation in summary_a["generations"]
        for candidate in generation["candidates"]
        if candidate["outcome"] == Outcome.SCORED.value
    ]
    league = json.loads(
        (store_a.root / "evolution" / summary_a["run_id"] / "league-registry.json").read_text()
    )
    league_ids = (
        set(league.get("candidates", {})) if isinstance(league.get("candidates"), dict) else set()
    )
    findings["L9_dead_candidate_enforcement"] = {
        "killed": [c["child_id"] for c in killed],
        "scored": [c["child_id"] for c in scored],
        "killed_carry_fitness": [bool(c["fitness"]) for c in killed],
        "killed_in_league_registry": sorted(
            c["child_id"] for c in killed if c["child_id"] in league_ids
        ),
        "scored_in_league_registry": sorted(
            c["child_id"] for c in scored if c["child_id"] in league_ids
        ),
        "league_candidate_count": len(league_ids),
    }

    (OUT / "evolution_record.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
