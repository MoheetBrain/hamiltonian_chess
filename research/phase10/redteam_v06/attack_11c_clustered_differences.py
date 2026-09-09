"""A11c -- the null that actually stresses the clustered test: correlated PAIRED DIFFERENCES.

A11's null draws the two arms independently inside a cluster, so the per-anchor differences it
produces are conditionally independent and BOTH the cluster and the anchor test hold their level.
That is the wrong stress test: what the cluster unit exists for is dependence in the differences
themselves -- anchors of one mathlib file responding to the arm the same way.

This generates exactly that, under a null the sign-flip test is still exact for: inside each
cluster, a fraction ``v_g`` of anchors are discordant and they all discord in the SAME direction
``s_g``, with ``s_g`` a fair coin per cluster.  Marginally ``E[d_i] = 0``; within a cluster the
differences are perfectly correlated.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.experiments.hc_v0_6.estimators import (  # noqa: E402
    ALPHA,
    PermutationUnit,
    ResampleUnit,
    paired_bootstrap_ci,
    permutation_null,
)
from arena.experiments.hc_v0_6.schema import Arm, PairedCells  # noqa: E402


def cluster_profile() -> list[int]:
    bank = load_bank_dict()
    return sorted(
        Counter(a["cluster"]["file_path"] for a in bank["anchors"]).values(), reverse=True
    )


def make_pair(rng: np.random.Generator, sizes: list[int], p: float, discord: float) -> PairedCells:
    anchor_ids, cluster_ids, a_out, b_out = [], [], [], []
    index = 0
    for g, size in enumerate(sizes):
        sign = 1 if rng.random() < 0.5 else -1
        base = rng.random(size) < p
        discordant = rng.random(size) < discord
        for j in range(size):
            a = bool(base[j])
            b = a
            if discordant[j]:
                a, b = (True, False) if sign > 0 else (False, True)
            anchor_ids.append(f"a{index}")
            cluster_ids.append(f"c{g}")
            a_out.append((a,))
            b_out.append((b,))
            index += 1
    return PairedCells(
        arm_a=Arm.R_A,
        arm_b=Arm.R_B,
        anchor_ids=tuple(anchor_ids),
        cluster_ids=tuple(cluster_ids),
        a_outcomes=tuple(a_out),
        b_outcomes=tuple(b_out),
    )


def main() -> int:
    sims = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    permutations = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    resamples = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    sizes = cluster_profile()
    results = []
    started = time.monotonic()
    for p, discord in [
        (0.133, 0.02),
        (0.133, 0.05),
        (0.133, 0.10),
        (0.25, 0.10),
        (0.133, 0.50),
        (0.133, 1.00),
    ]:
        rng = np.random.default_rng(20260909)
        counts = dict(perm_cluster=0, perm_anchor=0, boot_cluster=0, boot_anchor=0)
        for s in range(sims):
            pair = make_pair(rng, sizes, p, discord)
            if (
                permutation_null(
                    pair, unit=PermutationUnit.CLUSTER, permutations=permutations, seed=s
                ).p_value
                <= ALPHA
            ):
                counts["perm_cluster"] += 1
            if (
                permutation_null(
                    pair, unit=PermutationUnit.ANCHOR, permutations=permutations, seed=s
                ).p_value
                <= ALPHA
            ):
                counts["perm_anchor"] += 1
            lo, hi = paired_bootstrap_ci(
                pair, unit=ResampleUnit.CLUSTER, seed=s, resamples=resamples
            )
            if not (lo <= 0.0 <= hi):
                counts["boot_cluster"] += 1
            lo, hi = paired_bootstrap_ci(
                pair, unit=ResampleUnit.ANCHOR, seed=s, resamples=resamples
            )
            if not (lo <= 0.0 <= hi):
                counts["boot_anchor"] += 1
        se = (0.05 * 0.95 / sims) ** 0.5
        results.append(
            {
                "baseline_p": p,
                "within_cluster_discordance": discord,
                "sims": sims,
                "type_I_cluster_permutation": counts["perm_cluster"] / sims,
                "type_I_anchor_permutation": counts["perm_anchor"] / sims,
                "non_coverage_cluster_bootstrap": counts["boot_cluster"] / sims,
                "non_coverage_anchor_bootstrap": counts["boot_anchor"] / sims,
                "monte_carlo_se_at_nominal_5pc": round(se, 4),
            }
        )
        print(results[-1], flush=True)
    worst_cluster = max(r["type_I_cluster_permutation"] for r in results)
    worst_anchor = max(r["type_I_anchor_permutation"] for r in results)
    emit(
        "attack_11c_clustered_differences",
        {
            "attack": "A11c level of the clustered test when the PAIRED DIFFERENCES are clustered",
            "verdict": "HELD" if worst_cluster <= 0.08 else "BROKEN",
            "clusters": len(sizes),
            "anchors": sum(sizes),
            "nominal_alpha": ALPHA,
            "grid": results,
            "worst_cluster_permutation_type_I": worst_cluster,
            "worst_anchor_permutation_type_I": worst_anchor,
            "seconds": round(time.monotonic() - started, 1),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
