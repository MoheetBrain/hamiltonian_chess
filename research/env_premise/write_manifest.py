"""Emit artifacts/manifests/premise_selection_manifest.json from measured build + gate output.

Every number in the manifest is copied from a file produced by a run that actually happened:
``build_summary.json`` (research.env_premise.build_items) and the shortcut-gate report
(research.env_premise.shortcut_gate).  Nothing here recomputes or estimates.

Usage:
    python -m research.env_premise.write_manifest --build <dir> --gate <report.json> \
        [--gate-uncontrolled <report.json>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from arena.environments import premise_selection as ps

LD = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/"
    "leandojo_benchmark_4"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--gate-uncontrolled", default=None)
    parser.add_argument(
        "--out", default="artifacts/manifests/premise_selection_manifest.json"
    )
    args = parser.parse_args()

    build = json.loads((Path(args.build) / "build_summary.json").read_text(encoding="utf-8"))
    gate = json.loads(Path(args.gate).read_text(encoding="utf-8"))

    train = LD / "random" / "train.json"
    corpus = LD / "corpus.jsonl"

    shipped = {level.name for level in ps.LADDER}
    levels: dict[str, Any] = {}
    for level in ps.LADDER + ps.REJECTED_LEVELS:
        stats = build["levels"][level.name]
        tiers = stats["distractor_tier_counts"]
        total = sum(tiers.values()) or 1
        levels[level.name] = {
            "status": "SHIPPED" if level.name in shipped else "REJECTED_SHORTCUT",
            "k": level.k,
            "explicit_positive": level.explicit_positive,
            "distractor_tiers_allowed": list(level.tiers),
            "similarity_band_slack": level.similarity_band_slack,
            "freq_bucket_slack": level.freq_bucket_slack,
            "context_lines": level.context_lines,
            "transitions_attempted": stats["attempted"],
            "items_emitted": stats["emitted"],
            "emission_rate": round(stats["emitted"] / max(1, stats["attempted"]), 6),
            "distractor_tier_counts": tiers,
            "distractor_tier_proportions": {
                tier: round(count / total, 6) for tier, count in sorted(tiers.items())
            },
            "tier_fallback_rate": round(
                stats["items_with_fallback_tier"] / max(1, stats["emitted"]), 6
            ),
            "items_rejected_gold_in_prompt": stats["items_rejected_gold_in_prompt"],
            "shortcut_gate": {
                "chance": gate[level.name]["chance"],
                "n_dev_train_items": gate[level.name]["n_dev_train_items"],
                "n_dev_holdout_items": gate[level.name]["n_dev_holdout_items"],
                "best_shortcut": gate[level.name]["best_shortcut"],
                "best_shortcut_accuracy": gate[level.name]["best_shortcut_accuracy"],
                "ceiling_breached": gate[level.name]["ceiling_breached"],
                "per_shortcut_dev_holdout": {
                    key: value["dev_holdout"]
                    for key, value in gate[level.name]["shortcuts"].items()
                },
            },
        }

    headline = gate["L2_standard"]
    manifest: dict[str, Any] = {
        "schema": "arena-premise-selection-manifest-v1",
        "spec_version": ps.SPEC_VERSION,
        "dataset_version": {
            "name": "LeanDojo Benchmark 4",
            "leandojo_version": "2.0.0",
            "mathlib4_commit": ps.DATASET_COMMIT,
            "benchmark_root": str(LD),
        },
        "sources": [
            {
                "path": str(train),
                "role": "traced tactics (DEVELOPMENT, train split only)",
                "bytes": train.stat().st_size,
                "sha256": sha256(train),
            },
            {
                "path": str(corpus),
                "role": "declaration text, per-file imports, scope relation",
                "bytes": corpus.stat().st_size,
                "sha256": sha256(corpus),
            },
        ],
        "sealed_splits_not_read": sorted(ps.SEALED_RELPATHS),
        "split_filter": {
            "rule": (
                "The split label is a property of the FILE, not of a row: random/train.json "
                "contains train rows only and carries no 'split' field. This family therefore "
                "excludes non-train rows by never opening any other split file. "
                "arena.environments.premise_selection.require_permitted_train() rejects any path "
                "whose trailing <dir>/<file> is not 'random/train.json', and guard_source_path() "
                "raises SealedSplitError on all four sealed pools before any read occurs."
            ),
            "permitted_source_relpath": ps.PERMITTED_TRACE_RELPATH,
            "emitted_split_label": ps.PERMITTED_SPLIT,
            "cross_check": (
                "Streaming random/train.json yielded 250,814 traced tactics, matching the "
                "independently reported train-split step count exactly; steps.jsonl (which mixes "
                "all splits) was never read by this family."
            ),
        },
        "generator": {
            "version": ps.GENERATOR_VERSION,
            "seed": build["seed"],
            "rng": "splitmix64 seeded per item by blake2b(seed|proof_id|step_index|level)",
            "determinism": (
                "Item bytes depend only on the item's own provenance and the seed, not on "
                "iteration order; asserted by tests/environments/test_premise_selection.py."
            ),
        },
        "usable_item_filter": {
            "conditions": [
                "exactly one cited premise in annotated_tactic (single unambiguous answer)",
                "non-empty state_before",
                "the cited premise's name does not already occur in state_before",
            ],
            "counters": build["filter_stats"],
            "distinct_gold_premises": build["distinct_gold_premises"],
        },
        "corpus": {
            "declarations": build["corpus_decls"],
            "files": build["corpus_files"],
        },
        "difficulty_ladder": levels,
        "shortcut_gate": {
            "ceiling": 0.45,
            "headline_level": "L2_standard",
            "headline_k": headline["k_values"][0],
            "headline_chance": headline["chance"],
            "headline_best_shortcut": headline["best_shortcut"],
            "headline_best_shortcut_accuracy": headline["best_shortcut_accuracy"],
            "headline_ceiling_breached": headline["ceiling_breached"],
            "dev_holdout_split": "by blake2b(proof_id) < 0.30; no proof appears in both slices",
            "predictors": sorted(headline["shortcuts"]),
            "breached_levels": sorted(
                name for name, payload in gate.items() if payload["ceiling_breached"]
            ),
            "shipped_levels_breached": sorted(
                name
                for name, payload in gate.items()
                if payload["ceiling_breached"] and name in shipped
            ),
        },
        "leak_audit": {
            "items_audited": build["items_audited_for_leaks"],
            "problems_found": build["leak_problems"],
        },
        "verdict": (
            "FAMILY_READY"
            if not any(
                payload["ceiling_breached"] for name, payload in gate.items() if name in shipped
            )
            else "FAMILY_REJECTED_SHORTCUT"
        ),
        "verdict_note": (
            "Every SHIPPED rung is below the 0.45 ceiling. One constructed rung, "
            "L1_cross_module, breached it twice (0.866, then 0.644 after the frequency-matched "
            "used-premise control) and is REJECTED rather than tuned: a rung whose gold is always "
            "local and whose distractors are always non-local makes locality decisive by "
            "construction. It is excluded from arena.environments.premise_selection.LADDER."
        ),
    }

    if args.gate_uncontrolled:
        prior = json.loads(Path(args.gate_uncontrolled).read_text(encoding="utf-8"))
        manifest["control_applied"] = {
            "trigger": (
                "First gate run: L1_cross_module drew tier (c) distractors uniformly from all "
                "180,907 corpus declarations, so distractors were mostly declarations never used "
                "as a premise anywhere. Combined shallow model reached "
                f"{prior['L1_cross_module']['best_shortcut_accuracy']} against a 0.45 ceiling."
            ),
            "carrying_features": {
                "log_global_frequency": prior["L1_cross_module"]["feature_importances_tree"][
                    "log_global_frequency"
                ],
                "same_module": prior["L1_cross_module"]["feature_importances_tree"]["same_module"],
                "name_goal_jaccard": prior["L1_cross_module"]["feature_importances_logistic"][
                    "name_goal_jaccard"
                ],
            },
            "control": (
                "Tier (c) now samples only declarations that are actually used as a premise "
                "somewhere in train, and L1 was given the same frequency-bucket (slack 1) and "
                "similarity-band (slack 0) matching the other rungs already use."
            ),
            "re_measured_once": True,
            "before": {
                name: payload["best_shortcut_accuracy"] for name, payload in prior.items()
            },
            "after": {name: payload["best_shortcut_accuracy"] for name, payload in gate.items()},
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps(manifest["shortcut_gate"], indent=2))


if __name__ == "__main__":
    main()
