"""Compose artifacts/manifests/legal_transform_manifest.json from the measured artefacts.

Reads only research/env_legal/{build_report,shortcut_audit}.json, the item file, the module's own
declared metadata, and the on-disk size/sha256 of the two permitted sources.  Invents nothing.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arena.environments.legal_transform import (  # noqa: E402
    ADAPTER_VERSION,
    AXIS_INVALIDITY,
    AXIS_LEVEL,
    AXIS_PROPERTIES,
    AXIS_RESIDUAL_RISK,
    DONOR_CAVEATS,
    ENVIRONMENT_VERSION,
    GENERATOR_SEED,
    LEAN_TIER_A_REPLAY,
    PERMITTED_SPLIT,
    CorruptionAxis,
    DifficultyLevel,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LD = (
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4"
)
OUT = os.path.join(ROOT, "artifacts", "manifests", "legal_transform_manifest.json")


def digest(path: str) -> dict[str, object]:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            sha.update(block)
    return {"path": path, "bytes": os.path.getsize(path), "sha256": sha.hexdigest()}


def main() -> None:
    with open(os.path.join(HERE, "build_report.json"), encoding="utf-8") as handle:
        build = json.load(handle)
    with open(os.path.join(HERE, "shortcut_audit.json"), encoding="utf-8") as handle:
        audit = json.load(handle)

    stream = hashlib.sha256()
    tiers: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    with gzip.open(os.path.join(HERE, "items.jsonl.gz"), "rt", encoding="utf-8") as handle:
        for line in handle:
            stream.update(line.encode("utf-8"))
            record = json.loads(line)
            tiers[record["tier"]] += 1
            levels[record["level"]] += 1
            labels["valid" if record["valid"] else "invalid"] += 1

    axes: dict[str, object] = {}
    for axis in CorruptionAxis:
        summary = audit["per_axis"].get(axis.value, {})
        properties = AXIS_PROPERTIES[axis]
        top = list(summary.get("all_predictors", {}).items())[:5]
        axes[axis.value] = {
            "difficulty_level": AXIS_LEVEL[axis].value,
            "graded": AXIS_LEVEL[axis] is not DifficultyLevel.L0_EXPLICIT_CONTROL,
            "pairs_emitted": build["accepted_per_axis"].get(axis.value, 0),
            "items_emitted": 2 * build["accepted_per_axis"].get(axis.value, 0),
            "attempts": build["attempts_per_axis"].get(axis.value, 0),
            "shape_eligible_attempts": build["eligible_attempts_per_axis"].get(axis.value, 0),
            "candidates_constructed": build["candidates_per_axis"].get(axis.value, 0),
            "invalidity_discard_rate": build["invalidity_discard_rate_per_axis"].get(axis.value),
            "surface_discard_rate": build["surface_discard_rate_per_axis"].get(axis.value),
            "attempt_window_truncated_by_cap": axis.value
            in build["axes_whose_attempt_window_was_truncated_by_the_cap"],
            "ground_truth_tier": "TIER_B_CONSTRUCTED",
            "constructed_invalidity_argument": AXIS_INVALIDITY[axis],
            "residual_risk": AXIS_RESIDUAL_RISK[axis],
            "surface_claims": {
                "corrupts_action": properties.corrupts_action,
                "preserves_token_multiset": properties.preserves_token_multiset,
                "preserves_length": properties.preserves_length,
                "balanced_by_design": properties.balanced_by_design,
                "permutes_within_axis": properties.permutes_within_axis,
            },
            "shortcut_audit": {
                "n_dev_heldout": summary.get("n_dev_heldout"),
                "best_overall": summary.get("best_overall"),
                "best_single_shortcut": summary.get("best_single_shortcut"),
                "best_shallow_model": summary.get("best_shallow_model"),
                "breaches_ceiling": summary.get("breaches_ceiling"),
                "top_predictors": {name: score for name, score in top},
            },
        }

    manifest = {
        "schema": "arena-legal-transform-manifest-v1",
        "environment_version": ENVIRONMENT_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "generator_seed": GENERATOR_SEED,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator_module": "arena/environments/legal_transform.py",
        "build_script": "research/env_legal/build_family.py",
        "audit_script": "research/env_legal/shortcut_gate.py",
        "decision": (
            "Given a proof state, a proposed action and a proposed result state, is this a "
            "transition that actually occurred?  Balanced binary, chance 0.50."
        ),
        "sources": {
            "used": [
                dict(digest(os.path.join(LD, "random", "train.json")), role="transitions"),
                dict(digest(os.path.join(LD, "corpus.jsonl")), role="donor premise index"),
            ],
            "permitted_but_unused": [
                {
                    "path": "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
                    "leandojo/steps.jsonl",
                    "reason": "carries derived step features but no state text; the citation "
                    "prior and every eligibility check are computed from random/train.json "
                    "directly, so it added nothing and was not opened",
                },
                {
                    "path": "/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus/"
                    "lean_runtime_v2_full.canonical.part-{000..004}.jsonl.gz",
                    "reason": "AST-shaped and only 1,150 transitions with no tactic text; this "
                    "family needs the tactic and its premise annotations, which only LeanDojo "
                    "carries.  Not opened by this environment",
                },
            ],
            "sealed_never_read": {
                "manifest": "artifacts/manifests/SEALED_SPLITS.json",
                "paths": [
                    "novel_premises/val.json",
                    "novel_premises/test.json",
                    "random/val.json",
                    "random/test.json",
                ],
                "note": "not opened, not hashed here, not sampled",
            },
        },
        "train_only_filter": {
            "permitted_split": PERMITTED_SPLIT,
            "enforcement": "arena.environments.legal_transform.build_family raises "
            "SealedSplitViolation on any step whose split is not 'train'; every emitted item's "
            "provenance.source_path is prefixed 'train:'",
            "theorems_scanned_for_the_citation_prior": build["theorems_scanned_for_prior"],
            "theorems_retained_for_construction": build["retained_theorems"],
            "steps_considered": build["steps_considered"],
        },
        "counts": {
            "items": build["items_written"],
            "item_stream_sha256": stream.hexdigest(),
            "item_stream_note": "sha256 of research/env_legal/items.jsonl.gz decompressed; the "
            "gzip container embeds an mtime so the compressed file's own hash is not stable",
            "pairs": build["items_written"] // 2,
            "label_distribution": dict(labels),
            "tier_distribution": dict(tiers),
            "ladder": {level.value: levels.get(level.value, 0) for level in DifficultyLevel},
            "per_axis_pairs": build["accepted_per_axis"],
            "per_axis_cap": build["per_axis_cap"],
            "dropped_for_polarity_balance": build["dropped_for_polarity_balance"],
        },
        "discards": {
            "definition": "attempts are counted per axis over every step; 'eligibility' means "
            "the step's shape does not match the axis at all, 'invalidity' means the recorded "
            "transition did not support an argument that the corruption is invalid and the item "
            "was thrown away rather than guessed at, 'surface' means no donor existed that keeps "
            "the surface statistics matched",
            "headline_invalidity_discard_rate_over_shape_eligible_attempts": round(
                build["total_invalidity_discards"] / build["total_eligible_attempts"], 6
            ),
            "surface_discard_rate_over_shape_eligible_attempts": round(
                build["total_surface_discards"] / build["total_eligible_attempts"], 6
            ),
            "shape_eligible_attempts": build["total_eligible_attempts"],
            "invalidity_discards": build["total_invalidity_discards"],
            "surface_discards": build["total_surface_discards"],
            "per_axis_invalidity_discard_rate": build["invalidity_discard_rate_per_axis"],
            "per_axis_surface_discard_rate": build["surface_discard_rate_per_axis"],
            "by_reason": build["discards_by_reason"],
        },
        "shortcut_audit": {
            "preregistered_ceiling": audit["preregistered_ceiling"],
            "chance": audit["chance"],
            "protocol": audit["protocol"],
            "predictors": audit["feature_names"],
            "headline_graded_L1_L3": audit["pooled"]["graded_L1_L3"]["best_overall"],
            "headline_graded_L1_L3_best_single_shortcut": audit["pooled"]["graded_L1_L3"][
                "best_single_shortcut"
            ],
            "pooled_all_levels_including_controls": audit["pooled"]["all_levels"]["best_overall"],
            "per_level_best": {
                level: summary["best_overall"] for level, summary in audit["per_level"].items()
            },
            "per_axis_best": {
                axis: summary["best_overall"] for axis, summary in audit["per_axis"].items()
            },
            "graded_axes_breaching_ceiling": audit["graded_axes_breaching_ceiling"],
            "verdict": audit["verdict"],
            "axes_demoted_to_the_L0_control_arm_after_measurement": {
                "violated_precondition": "identifier-novelty separable at 0.777; the only "
                "textually checkable form of a precondition violation raises the action's "
                "novel-identifier count, which is structural rather than tunable",
                "wrong_successor": "before/after token Jaccard separable at 0.644 after the one "
                "permitted repair (nearest-donor sampling replaced by a within-proof successor "
                "derangement, which removed a +80-character length tell and took the axis from "
                "0.700 to 0.664); a state one tactic-step away simply resembles the goal state "
                "more than one two steps away, and no textual donor policy removes that",
                "wrong_premise_uniform": "designed as a control from the outset; separable at "
                "0.775, which is the point of a visible floor",
            },
            "closest_graded_axis_to_the_ceiling": {
                "axis": "wrong_rewrite_direction",
                "best": audit["per_axis"]["wrong_rewrite_direction"]["best_overall"],
                "warning": "under the ceiling but by a small margin, and only a depth-4 tree "
                "reaches it while no single feature exceeds 0.53, which points to a "
                "lemma-identity by orientation interaction reached through premise frequency.  A "
                "sibling audit (research/environments/measurements/rewrite_direction_shortcuts."
                "json) measured a train-fitted per-lemma direction prior at 0.793 on the same "
                "decision.  Here that adversary is weak because both orientations of the same "
                "lemma are emitted, so the prior sees mixed labels; that defence is a property "
                "of this construction and would not survive a different sampling policy.  Treat "
                "this axis as AT RISK and defer to the rewrite_direction family owner.",
            },
        },
        "ground_truth": {
            "tiers_present": sorted(tiers),
            "tier_a_items": 0,
            "note": "no item is TIER_A_VERIFIED: Lean was not run.  Every negative is invalid by "
            "a construction argument recorded per axis, and every positive is a recorded "
            "LeanDojo transition that Arena has not itself replayed.",
        },
        "axes": axes,
        "lean_tier_a_replay": LEAN_TIER_A_REPLAY,
        "caveats": list(DONOR_CAVEATS),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, ensure_ascii=False)
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
