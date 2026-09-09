"""A8 -- is the cluster unit really the mathlib file everywhere it matters?

Checks, on the frozen bank and on the estimator code:

1. the bank's declared cluster profile (files, theorems, anchors) and its size distribution;
2. that no anchor carries an empty / non-mathlib ``cluster.file_path``;
3. that ``cluster.file_path`` never equals the theorem (which would silently make the theorem the
   unit) and that one file really does carry several theorems;
4. which estimator entry points can be handed the ANCHOR as the resampling / permutation unit,
   and whether anything marks that choice as non-reportable;
5. whether a partially played anchor -- what ``run_assay``'s per-theorem ``except`` leaves behind
   -- silently drops out of a contrast, and whether anything counts it;
6. duplicate ``prefix_length`` inside one theorem, which ``open_anchor_session`` collapses.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.experiments.hc_v0_6.estimators import (  # noqa: E402
    PermutationUnit,
    ResampleUnit,
    estimate_pair,
)
from arena.experiments.hc_v0_6.schema import (  # noqa: E402
    Arm,
    CellOutcome,
    CellTable,
    ParseStatus,
    StepResult,
    extract_pair,
)


def _row(anchor: str, cluster: str, arm: Arm, event: bool) -> CellOutcome:
    return CellOutcome(
        anchor_id=anchor,
        cluster_id=cluster,
        theorem=f"{cluster}::t",
        reelaboration_key="k",
        arm=arm,
        renderer_id=arm.renderer_id,
        intervention_class=arm.intervention_class,
        replicate_index=0,
        step_result=StepResult.ACCEPTED_TRANSITION if event else StepResult.REJECTED_INVALID_ACTION,
        parse_status=ParseStatus.OK,
        closed_all_goals=False,
        prompt_sha256="0" * 64,
        prompt_tokens=1,
        response_tokens=1,
        latency_ms=1,
        solver_digest="d",
        proposed_tactic="simp",
    )


def main() -> int:
    bank = load_bank_dict()
    anchors = bank["anchors"]
    files = Counter(a["cluster"]["file_path"] for a in anchors)
    theorems_per_file: dict[str, set[str]] = defaultdict(set)
    for a in anchors:
        theorems_per_file[a["cluster"]["file_path"]].add(a["cluster"]["theorem_full_name"])

    bad_paths = [
        a["anchor_id"]
        for a in anchors
        if not a["cluster"]["file_path"].endswith(".lean")
        or a["cluster"]["file_path"] == a["cluster"]["theorem_full_name"]
    ]

    depth_collisions = []
    by_problem: dict[str, list[int]] = defaultdict(list)
    for a in anchors:
        by_problem[a["oracle"]["problem_id"]].append(a["sampling"]["prefix_length"])
    for problem, depths in by_problem.items():
        if len(depths) != len(set(depths)):
            depth_collisions.append(problem)

    sizes = Counter(files.values())

    # --- 5. a partially played anchor -------------------------------------------------------
    rows = []
    for i in range(40):
        anchor = f"a{i}"
        cluster = f"Mathlib/F{i % 10}.lean"
        for arm in Arm:
            if i == 3 and arm in (Arm.R_B, Arm.R_ABLATED):
                continue  # the theorem crashed after two of the four arms had been played
            rows.append(_row(anchor, cluster, arm, event=(i % 4 == 0)))
    table = CellTable(rows)
    pair = extract_pair(table, Arm.R_A, Arm.R_B)
    dropped_silently = len(table.anchor_ids) - pair.n_anchors

    # --- 4. can a contrast use the anchor as the unit? --------------------------------------
    effect = estimate_pair(
        table,
        __import__(
            "arena.experiments.hc_v0_6.estimators", fromlist=["Comparison"]
        ).Comparison.PRIMARY_RB_VS_RA,
        resamples=200,
        permutations=500,
    )

    emit(
        "attack_08_clusters",
        {
            "attack": "A8 theorem clustering: is the cluster unit the mathlib file?",
            "verdict": "HELD" if not bad_paths and not depth_collisions else "BROKEN",
            "bank": {
                "anchors": len(anchors),
                "distinct_files": len(files),
                "distinct_theorems": len({a["cluster"]["theorem_full_name"] for a in anchors}),
                "declared_stats": bank["stats"],
                "anchors_per_file_histogram": dict(sorted(sizes.items())),
                "largest_cluster": files.most_common(3),
                "mean_cluster_size": round(len(anchors) / len(files), 4),
                "files_carrying_more_than_one_theorem": sum(
                    1 for v in theorems_per_file.values() if len(v) > 1
                ),
            },
            "anchors_with_a_bad_cluster_path": bad_paths,
            "theorems_with_duplicate_prefix_lengths": depth_collisions,
            "anchor_unit_available_as": {
                "bootstrap": [u.value for u in ResampleUnit],
                "permutation": [u.value for u in PermutationUnit],
            },
            "preregistered_p_is_cluster_level": effect.permutation.unit is PermutationUnit.CLUSTER,
            "anchor_naive_marked_not_reportable": not effect.permutation_anchor_naive.reportable,
            "n_clusters_reported_by_the_contrast": effect.n_clusters,
            "partially_played_anchor": {
                "anchors_in_table": len(table.anchor_ids),
                "anchors_in_the_R_A_vs_R_B_pair": pair.n_anchors,
                "dropped_without_a_record": dropped_silently,
                "note": (
                    "extract_pair drops half-populated anchors silently; run_assay's per-theorem "
                    "`except Exception` is exactly what creates them, and it records only the "
                    "problem_id in theorem_errors -- not which anchors or which arms were lost."
                ),
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
