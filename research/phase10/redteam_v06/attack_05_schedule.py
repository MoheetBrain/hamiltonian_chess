"""A5 -- is the within-anchor arm order really a pure function of ``(seed, anchor_id)``?

Run over the REAL 1,127 anchor ids of the frozen bank, in the order the runner actually plays
them (theorem groups sorted, anchors by prefix length), and check:

1. determinism across processes and across ``PYTHONHASHSEED`` (``random.Random`` is seeded with a
   *string*, so this is not free);
2. every arm appears in every position with equal frequency (chi-square on the 4x4 table);
3. an arm's position is uncorrelated with execution order, with anchor depth, and with the
   cluster -- a position effect must not align with an arm;
4. the schedule does not depend on run-time state: it is recomputed after playing thousands of
   fake cells and compared.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit, load_bank_dict  # noqa: E402

from arena.experiments.hc_v0_6.schema import Arm  # noqa: E402
from arena.experiments.hc_v0_6_assay import plan_cells  # noqa: E402

SEED = 20260909


def _orders(anchor_ids: list[str]) -> list[tuple[str, ...]]:
    return [
        tuple(
            str(plan.arm.value)
            for plan in plan_cells(tuple(Arm), replicates=1, seed=SEED, anchor_id=a)
        )
        for a in anchor_ids
    ]


def main() -> int:
    bank = load_bank_dict()
    by_theorem: dict[str, list[dict]] = defaultdict(list)
    for anchor in bank["anchors"]:
        by_theorem[anchor["oracle"]["problem_id"]].append(anchor)
    execution: list[dict] = []
    for problem_id in sorted(by_theorem):
        execution.extend(
            sorted(by_theorem[problem_id], key=lambda a: a["sampling"]["prefix_length"])
        )
    anchor_ids = [a["anchor_id"] for a in execution]
    orders = _orders(anchor_ids)

    # --- 1. determinism -----------------------------------------------------------------------
    same_process = _orders(anchor_ids) == orders
    script = (
        "import sys;sys.path.insert(0,'.');"
        "from arena.experiments.hc_v0_6.schema import Arm;"
        "from arena.experiments.hc_v0_6_assay import plan_cells;"
        f"print([p.arm.value for p in plan_cells(tuple(Arm),replicates=1,seed={SEED},"
        "anchor_id='anchor:d89aa98c5cb6cd2353de4a31')])"
    )
    subprocess_orders = set()
    for hashseed in ("0", "1", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hashseed}
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(Path(__file__).resolve().parents[3]),
            check=True,
        )
        subprocess_orders.add(out.stdout.strip())

    # --- 2. position x arm table --------------------------------------------------------------
    table: dict[str, Counter[int]] = {str(a.value): Counter() for a in Arm}
    for order in orders:
        for position, arm in enumerate(order):
            table[arm][position] += 1
    n = len(orders)
    expected = n / 4.0
    chi2 = sum((table[arm][pos] - expected) ** 2 / expected for arm in table for pos in range(4))

    # --- 3. correlation with execution order, depth, cluster ----------------------------------
    positions = {str(a.value): [order.index(str(a.value)) for order in orders] for a in Arm}
    depths = [a["sampling"]["prefix_length"] for a in execution]
    index = list(range(n))

    def pearson(xs: list[float], ys: list[float]) -> float:
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        dx = sum((x - mx) ** 2 for x in xs) ** 0.5
        dy = sum((y - my) ** 2 for y in ys) ** 0.5
        return num / (dx * dy) if dx and dy else 0.0

    corr_order = {
        arm: pearson([float(i) for i in index], [float(p) for p in ps])
        for arm, ps in positions.items()
    }
    corr_depth = {
        arm: pearson([float(d) for d in depths], [float(p) for p in ps])
        for arm, ps in positions.items()
    }

    # per-cluster mean position spread: an arm systematically early in some file would show here
    cluster_of = [a["cluster"]["file_path"] for a in execution]
    by_cluster: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for cluster, order in zip(cluster_of, orders, strict=True):
        for arm in table:
            by_cluster[cluster][arm].append(order.index(arm))
    worst_cluster_bias = 0.0
    for _cluster, arms in by_cluster.items():
        if len(next(iter(arms.values()))) < 5:
            continue
        for _arm, ps in arms.items():
            worst_cluster_bias = max(worst_cluster_bias, abs(sum(ps) / len(ps) - 1.5))

    # --- 4. schedule after runtime churn ------------------------------------------------------
    import random as _random

    _random.seed(1234)
    _ = [_random.random() for _ in range(100_000)]
    after_churn = _orders(anchor_ids[:200]) == orders[:200]

    distinct_orders = len(set(orders))
    emit(
        "attack_05_schedule",
        {
            "attack": "A5 arm interleaving: pure function of (seed, anchor_id), arm-independent",
            "verdict": "HELD"
            if same_process and len(subprocess_orders) == 1 and after_churn and chi2 < 16.9
            else "BROKEN",
            "anchors": n,
            "deterministic_within_process": same_process,
            "deterministic_across_PYTHONHASHSEED": len(subprocess_orders) == 1,
            "observed_subprocess_orders": sorted(subprocess_orders),
            "unaffected_by_global_random_state": after_churn,
            "distinct_orders_used": distinct_orders,
            "distinct_orders_possible": 24,
            "position_by_arm": {arm: dict(sorted(c.items())) for arm, c in table.items()},
            "chi_square_16_cells": round(chi2, 3),
            "chi_square_df": 9,
            "chi_square_0p05_critical_df9": 16.919,
            "pearson_position_vs_execution_index": {a: round(v, 4) for a, v in corr_order.items()},
            "pearson_position_vs_prefix_depth": {a: round(v, 4) for a, v in corr_depth.items()},
            "worst_per_cluster_mean_position_deviation": round(worst_cluster_bias, 3),
            "note": (
                "plan_cells shuffles a list built from `arms`, so the schedule is a pure function "
                "of (seed, anchor_id, arms-tuple). The primary runs four arms and each secondary "
                "runs three, so a secondary's order is NOT the primary's order restricted -- "
                "declared behaviour, but it means cross-model position effects are not paired."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
