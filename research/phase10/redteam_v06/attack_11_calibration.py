"""A11 -- does the preregistered clustered test hold its nominal level on THIS bank's clusters?

The cluster-size profile is read from the frozen bank (330 files, 1,127 anchors, sizes 1..12) and
null data are generated on exactly that profile: a cluster random effect ``u_g`` with the target
intra-cluster correlation, then two INDEPENDENT Bernoulli(``u_g``) draws per anchor, one per arm.
The arm label carries no effect, so every rejection is a type-I error.

Four procedures are measured, through the real functions:
  * ``permutation_null(unit=CLUSTER)``  -- the preregistered test
  * ``permutation_null(unit=ANCHOR)``   -- its declared negative control
  * ``paired_bootstrap_ci(unit=CLUSTER)`` -- the preregistered interval (non-coverage of 0)
  * ``paired_bootstrap_ci(unit=ANCHOR)``  -- its declared negative control

Run: python attack_11_calibration.py [sims] [permutations] [resamples]
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
    sizes = Counter(a["cluster"]["file_path"] for a in bank["anchors"])
    return sorted(sizes.values(), reverse=True)


def make_null_pair(rng: np.random.Generator, sizes: list[int], p: float, icc: float) -> PairedCells:
    anchor_ids: list[str] = []
    cluster_ids: list[str] = []
    a_out: list[tuple[bool, ...]] = []
    b_out: list[tuple[bool, ...]] = []
    index = 0
    for g, size in enumerate(sizes):
        if icc <= 0.0:
            u = np.full(size, p)
        else:
            # Beta(alpha, beta) with mean p and Var = icc * p(1-p): the standard
            # beta-binomial parameterisation of an intra-cluster correlation.
            nu = (1.0 - icc) / icc
            u = np.full(size, rng.beta(p * nu, (1.0 - p) * nu))
        draws = rng.random((2, size)) < u
        for j in range(size):
            anchor_ids.append(f"a{index}")
            cluster_ids.append(f"c{g}")
            a_out.append((bool(draws[0, j]),))
            b_out.append((bool(draws[1, j]),))
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
    grid = [(0.133, 0.0), (0.133, 0.2), (0.133, 0.5), (0.25, 0.2), (0.40, 0.5)]

    results = []
    started = time.monotonic()
    for p, icc in grid:
        rng = np.random.default_rng(20260909)
        counts = dict(perm_cluster=0, perm_anchor=0, boot_cluster=0, boot_anchor=0)
        for s in range(sims):
            pair = make_null_pair(rng, sizes, p, icc)
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
                "icc": icc,
                "sims": sims,
                "type_I_cluster_permutation": counts["perm_cluster"] / sims,
                "type_I_anchor_permutation": counts["perm_anchor"] / sims,
                "non_coverage_cluster_bootstrap": counts["boot_cluster"] / sims,
                "non_coverage_anchor_bootstrap": counts["boot_anchor"] / sims,
                "monte_carlo_se_at_nominal_5pc": round(se, 4),
                "cluster_permutation_within_2se_of_nominal": abs(
                    counts["perm_cluster"] / sims - 0.05
                )
                <= 2 * se,
            }
        )
        print(results[-1], flush=True)

    worst = max(r["type_I_cluster_permutation"] for r in results)
    emit(
        "attack_11_calibration",
        {
            "attack": "A11 statistical calibration on the frozen bank's real cluster profile",
            "verdict": "HELD" if worst <= 0.08 else "BROKEN",
            "clusters": len(sizes),
            "anchors": sum(sizes),
            "cluster_size_histogram": dict(sorted(Counter(sizes).items())),
            "nominal_alpha": ALPHA,
            "permutations_per_test": permutations,
            "bootstrap_resamples": resamples,
            "grid": results,
            "worst_cluster_permutation_type_I": worst,
            "seconds": round(time.monotonic() - started, 1),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
