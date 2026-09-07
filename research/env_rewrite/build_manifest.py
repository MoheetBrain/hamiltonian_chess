"""Assemble artifacts/manifests/rewrite_direction_manifest.json from the measured artefacts.

Run:  python -m research.env_rewrite.build_manifest

Reads only what the earlier steps already wrote plus the source files' bytes (for sha256).
No sealed split is opened.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
from typing import Any

from arena.environments import rewrite_direction as rw
from research.env_rewrite.shortcut_gate import CEILING, ITEMS_JSONL, balance_within_lemma
from research.env_rewrite.stream import CORPUS_JSONL, STEPS_JSONL, TRAIN_JSON

HERE = os.path.dirname(os.path.abspath(__file__))
MEASUREMENTS = os.path.join(HERE, "measurements")
REPO = os.path.dirname(os.path.dirname(HERE))
MANIFEST = os.path.join(REPO, "artifacts", "manifests", "rewrite_direction_manifest.json")


def sha256(path: str) -> dict[str, Any]:
    rw.assert_source_permitted(path)
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1 << 22)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return {"path": path, "bytes": size, "sha256": digest.hexdigest()}


def load(name: str) -> dict[str, Any]:
    with open(os.path.join(MEASUREMENTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    census = load("direction_census.json")
    gate_none = load("shortcut_gate.json")
    gate_control = load("shortcut_gate_within_lemma.json")

    records = [json.loads(line) for line in open(ITEMS_JSONL, encoding="utf-8")]
    core = [r for r in records if not r["explicit_positive"]]
    l0_all = [r for r in records if r["explicit_positive"]]
    for record in core:
        record["y"] = 1 if record["direction"] == rw.REVERSE else 0
    controlled = balance_within_lemma(core, "dataset")
    controlled_keys = {
        (r["provenance"]["proof_id"], r["provenance"]["step_index"], r["premise_name"])
        for r in controlled
    }
    l0_kept = [
        r
        for r in l0_all
        if (r["provenance"]["proof_id"], r["provenance"]["step_index"], r["premise_name"])
        in controlled_keys
    ]

    levels = collections.Counter(r["level"] for r in controlled)
    level_directions = collections.Counter(
        (r["level"], r["direction"]) for r in controlled
    )
    discards = census["discards"]
    discard_total = sum(discards.values())
    considered = census["steps_total"]

    manifest: dict[str, Any] = {
        "schema": "arena-rewrite-direction-manifest-v1",
        "family": "rewrite_direction",
        "environment_version": rw.ENVIRONMENT_VERSION,
        "built_by": "claude/phase-6 rewrite-direction environment agent",
        "dataset": {
            "name": rw.DATASET_NAME,
            "version": rw.DATASET_VERSION,
            "mathlib4_commit": rw.MATHLIB4_COMMIT,
            "license": rw.DATASET_LICENSE,
            "split_used": rw.PERMITTED_SPLIT,
            "train_only_filter": (
                "Items are built exclusively from random/train.json. steps.jsonl covers all "
                "splits and is used only as a metadata index for the sealed-exclusion test, "
                "filtered on split == 'train'. The sealed pools "
                "(novel_premises/{val,test}.json, random/{val,test}.json) are never opened; "
                "arena.environments.rewrite_direction.assert_source_permitted raises on them."
            ),
            "sealed_pools_not_read": sorted(rw.SEALED_RELATIVE_PATHS),
            "sealed_manifest": "artifacts/manifests/SEALED_SPLITS.json",
        },
        "sources": {
            "development": sha256(TRAIN_JSON),
            "premise_corpus": sha256(CORPUS_JSONL),
            "metadata_index": sha256(STEPS_JSONL) if os.path.exists(STEPS_JSONL) else None,
        },
        "generator": {
            "environment_version": rw.ENVIRONMENT_VERSION,
            "generator_version": rw.GENERATOR_VERSION,
            "parser_version": rw.PARSER_VERSION,
            "seed": census["seed"],
            "determinism": (
                "item_id = sha256(generator_version|proof_id|step_index|premise|arm); option "
                "order is drawn from Random(seed|item_id). The same seed reproduces "
                "byte-identical rendered items."
            ),
            "item_population_rule": (
                "One item per rewrite tactic, built from the FIRST bracket element. Only the "
                "first element acts on the recorded state_before; later elements act on "
                "intermediate states LeanDojo does not record, so splitting them out would "
                "produce items whose question is not answerable from what is shown. "
                "Mixed-direction brackets are therefore neither excluded nor split: each "
                "contributes exactly one item, labelled by its first element."
            ),
            "heads_in_item_population": sorted(rw.ITEM_HEADS),
            "heads_censused_but_excluded": sorted(rw.CENSUS_HEADS - rw.ITEM_HEADS),
            "state_after_withheld": (
                "Items show state_before only. Showing state_after would make the task a diff "
                "and would reintroduce the 'the goal grew, so it was reversed' shortcut."
            ),
        },
        "direction_distribution": {
            "measured_on": "random/train.json, all rewrite-family tactics",
            "prior_claim_36_9_percent_reverse": False,
            "prior_claim_note": (
                "The 36.9% reverse estimate did NOT reproduce. Measured reverse rate is "
                "19.42% per rewrite element and 25.12% per tactic (first element). The "
                "binary is therefore NOT naturally balanced and must be balanced explicitly."
            ),
            "per_element": census["per_element"],
            "per_element_by_head": census["per_element_by_head"],
            "per_tactic": census["per_tactic"],
            "bracket_size_distribution": census["bracket_size_distribution"],
            "head_counts": census["head_counts"],
            "mixed_direction_brackets": census["per_tactic"]["mixed_direction_bracket"],
            "mixed_direction_rate": census["per_tactic"]["mixed_rate"],
        },
        "items": {
            "train_steps_considered": considered,
            "rewrite_family_tactics_parsed": census["rw_family_tactics_parsed"],
            "items_generated_core": len(core),
            "items_generated_l0_arm": len(l0_all),
            "controlled_pool": len(controlled),
            "controlled_pool_distinct_lemmas": len({r["premise_name"] for r in controlled}),
            "controlled_pool_forward": sum(
                1 for r in controlled if r["direction"] == rw.FORWARD
            ),
            "controlled_pool_reverse": sum(
                1 for r in controlled if r["direction"] == rw.REVERSE
            ),
            "l0_arm_within_controlled_pool": len(l0_kept),
            "control_applied": "balance_within_lemma",
            "control_rationale": (
                "Every lemma contributes equally many forward and reverse items, so every "
                "lemma-constant feature (name, name n-grams, name affixes, the two sides' "
                "lengths and their ratio, side similarity) is uninformative by construction."
            ),
        },
        "difficulty_ladder": {
            "axes": [
                "side similarity (how much vocabulary the two sides share)",
                "decisiveness (how strongly one side's distinctive vocabulary dominates the target)",
                "target nesting depth",
                "number of plausible rewrite sites",
                "distractor equalities in the local context",
            ],
            "scoring": "additive 0-2 per axis, total 0-10; bin edges L1<=2, L2<=4, L3>4",
            "bin_edges": list(rw.LADDER_EDGES),
            "counts": {
                "L0_explicit_positive": len(l0_kept),
                "L1": levels[1],
                "L2": levels[2],
                "L3": levels[3],
            },
            "direction_balance_per_level": {
                f"L{level}": {
                    "forward": level_directions[(level, rw.FORWARD)],
                    "reverse": level_directions[(level, rw.REVERSE)],
                }
                for level in (1, 2, 3)
            },
            "L0_arm": (
                "Explicit-positive control: the item restates the decisive relation outright "
                "('the rewritten subterm is an instance of Side A/B, the side that occurs in "
                "the goal'). Solvable by construction, so it is EXCLUDED from the shortcut "
                "gate and exists only as a floor check that a solver can read the format."
            ),
        },
        "discards": {
            "counts": discards,
            "total": discard_total,
            "rates_over_train_steps": {
                reason: round(count / considered, 6) for reason, count in discards.items()
            },
            "notes": {
                "not_a_rewrite_tactic": "the step is not a rewrite at all; the dominant term",
                "premise_signature_unavailable": (
                    "the tracer resolved a name that corpus.jsonl does not carry a signature "
                    "for (mostly core Lean / Batteries declarations); without the equation "
                    "the item cannot be posed"
                ),
                "premise_not_resolved": (
                    "the first bracket element is a local hypothesis or an unannotated term, "
                    "so no library equation identifies it"
                ),
                "no_top_level_equation": (
                    "the premise's type does not end in a top-level = or IFF, or carries two "
                    "top-level occurrences of the same non-associative relation"
                ),
                "arrow_token_in_rendered_text": (
                    "the state or statement itself contains an arrow token; refused so that "
                    "the no-arrow leakage invariant stays an exact assertion"
                ),
                "leakage_guard_tripped": (
                    "the assembled item failed leakage_violations() and was dropped by the "
                    "generator's last line of defence"
                ),
            },
        },
        "shortcut_gate": {
            "preregistered_ceiling": CEILING,
            "chance": 0.5,
            "protocol": gate_control["protocol"],
            "v1_0_no_control": {
                "verdict": gate_none["verdict"],
                "best_shortcut": gate_none["best_shortcut"],
                "held_out_items": gate_none["sizes"]["dev_held_balanced"],
                "ranked": gate_none["ranked"],
                "responsible_features": [
                    "lemma_name_char_ngram_logistic 0.6748 - pure name recall, no state read",
                    "lemma_name_frequency_prior 0.6376 - per-lemma majority direction",
                    "expression_length_ratio 0.6261 - a lemma constant, not a state fact",
                ],
            },
            "v1_1_within_lemma_control": {
                "verdict": gate_control["verdict"],
                "best_shortcut": gate_control["best_shortcut"],
                "held_out_items": gate_control["sizes"]["dev_held_balanced"],
                "ranked": gate_control["ranked"],
                "lemma_constant_features_collapse_to_chance": [
                    name
                    for name, accuracy in gate_control["ranked"]
                    if abs(accuracy - 0.5) < 1e-9
                ],
                "which_side_appears_in_goal": gate_control["shortcuts"][
                    "which_side_appears_in_goal"
                ],
            },
        },
        "verdict": gate_control["verdict"],
    }

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, ensure_ascii=False)
    print(MANIFEST)
    print(json.dumps(manifest["items"], indent=1))
    print(json.dumps(manifest["difficulty_ladder"]["counts"], indent=1))


if __name__ == "__main__":
    main()
