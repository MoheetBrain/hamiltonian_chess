"""Is there a cue in the V1 generator BEYOND the junction edge?  Zero model calls.

Run as ``.venv/bin/python -m research.phase8.transitive.nonjunction_diagnostic``.

The audit's fitted models exceed the mention-count rule at L2/L3 by a few points and their
family-hit histograms contain 1-of-2 families, so they are not simply re-reading the junction edge.
This script loads the FROZEN adversaries (``frozen_adversaries.json``, content-hash verified) and
scores them on the families where the junction edge does NOT touch a candidate
(``junction != hops-1``) -- once on the audit's own EVALUATION split (families 200..399) and once on
a fresh REPLICATION pool (families 400..799, salts still far outside every prior range).  On those
families every single rule of the family abstains or is pinned, so any accuracy above 0.5 with an
exact interval excluding 0.5 on the replication pool is a second, unidentified cue.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .audit import credit_matrix, family_hit_histogram, frozen_predictions
from .common import SURFACES, hops_for_level, render, shared_adversary_module, v1_family
from .structure import v1_junction

HERE = Path(__file__).resolve().parent


def examples_for(shared: Any, level: int, surface: str, indices: range) -> tuple[list[Any], list[Any]]:
    junction: list[Any] = []
    non_junction: list[Any] = []
    hops = hops_for_level(level)
    for index in indices:
        is_junction = v1_junction(level, index) == hops - 1
        for item in v1_family(level, index):
            if not item.is_positive:
                continue
            example = shared.Example(
                prompt=render(item, surface),
                n_options=2,
                correct_index=item.expected_index,
                family_id=item.family_id,
                arm_id=surface,
                task_id=f"{surface}:{item.family_id}:{item.variant}",
            )
            (junction if is_junction else non_junction).append(example)
    return junction, non_junction


def score(shared: Any, frozen: Any, examples: list[Any]) -> dict[str, Any]:
    preds = frozen_predictions(shared, frozen, examples)
    names, C = credit_matrix(preds, examples)
    out: dict[str, Any] = {}
    for j, name in enumerate(names):
        p = preds[name]
        decided = [(x, e) for x, e in zip(p, examples, strict=True) if x is not None]
        k = sum(1 for x, e in decided if x == e.correct_index)
        lo, hi = shared.clopper_pearson(k, len(decided)) if decided else (0.0, 1.0)
        acc = float(C[j].mean())
        k_cred = int(np.floor(acc * len(examples)))
        lo_c, hi_c = shared.clopper_pearson(k_cred, len(examples))
        out[name] = {
            "credited_accuracy": acc,
            "n": len(examples),
            "decided_n": len(decided),
            "decided_correct": k,
            "cp_decided": [lo, hi],
            "cp_credited_floor": [lo_c, hi_c],
            "p_one_sided_decided_vs_0.5": shared.binomial_upper_tail(k, len(decided), 0.5) if decided else 1.0,
            "family_hits": family_hit_histogram(C[j], examples),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", nargs="+", type=int, default=[2, 3])
    parser.add_argument("--surfaces", nargs="+", default=list(SURFACES))
    parser.add_argument("--frozen", type=Path, default=HERE / "frozen_adversaries.json")
    parser.add_argument("--out", type=Path, default=HERE / "nonjunction_diagnostic.json")
    args = parser.parse_args(argv)
    shared = shared_adversary_module()
    if shared is None:
        raise SystemExit("shared adversary module unavailable")
    frozen_all = json.loads(args.frozen.read_text())
    t0 = time.time()
    cells: list[dict[str, Any]] = []
    for level in args.levels:
        for surface in args.surfaces:
            frozen = shared.from_json(json.dumps(frozen_all[f"v1_frozen:L{level}:{surface}"]))
            record: dict[str, Any] = {
                "level": level,
                "hops": hops_for_level(level),
                "surface": surface,
                "frozen_hash": frozen.content_hash,
            }
            for pool, indices in (("evaluation_200_399", range(200, 400)), ("replication_400_799", range(400, 800))):
                overlap = sorted({f"v5:dev:transitive_dependency:l{level}:synthetic:{8_000_000 + level * 100_000 + i}" for i in indices} & set(frozen.dev_family_ids))
                if overlap:
                    raise ValueError(f"pool {pool} overlaps development: {overlap[:3]}")
                junction, non_junction = examples_for(shared, level, surface, indices)
                record[pool] = {
                    "n_families": len(indices),
                    "junction_families": len(junction) // 2,
                    "non_junction_families": len(non_junction) // 2,
                    "junction_only": score(shared, frozen, junction),
                    "non_junction_only": score(shared, frozen, non_junction),
                }
            cells.append(record)
            nj_eval = record["evaluation_200_399"]["non_junction_only"]
            nj_rep = record["replication_400_799"]["non_junction_only"]
            for name in ("model:logistic:difference", "model:tree:difference"):
                e, r = nj_eval[name], nj_rep[name]
                print(
                    f"L{level} {surface:24s} {name:26s} non-junction eval={e['credited_accuracy']:.4f} "
                    f"cp={[round(x, 3) for x in e['cp_decided']]} | replication={r['credited_accuracy']:.4f} "
                    f"cp={[round(x, 3) for x in r['cp_decided']]} p={r['p_one_sided_decided_vs_0.5']:.3f} hits={r['family_hits']}",
                    flush=True,
                )
    payload = {
        "_disclaimer": "Diagnostic only. Zero model calls. No sentinel is re-scored.",
        "cells": cells,
        "elapsed_seconds": time.time() - t0,
    }
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"elapsed {payload['elapsed_seconds']:.1f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
