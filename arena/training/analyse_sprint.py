#!/usr/bin/env python
"""Turn the GPU sprint's per-item outcomes into paired comparisons with uncertainty.

`docs/ARENA_PROTOCOL.md` forbids ranking from raw point estimates. Every comparison here is
paired on the same canonical trajectories -- the arms saw identical worlds in identical order,
so item *i* is the same mathematics for every arm -- and every number carries an interval.

    python -m arena.training.analyse_sprint --results gpu_sprint_results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from arena.training.evaluation import paired_bootstrap_difference, wilson_interval

#: Controls are the four established surfaces; L5 is the static compactness frontier under
#: test. "Best control" is chosen by score, so the candidate is never flattered by comparison
#: with a weak baseline.
CONTROLS = ("L0_STRUCTURED_ENGLISH", "L1_CURRENT_HML", "L2_SEXPR", "L3_JSON_AST")
CANDIDATE = "L5_COMPACT_SYMBOLIC"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=None)
    args = parser.parse_args()

    payload = json.loads(args.results.read_text())
    results = payload["results"]

    for stage in ("stage_a", "stage_b", "stage_c"):
        present = {arm: record[stage] for arm, record in results.items() if stage in record}
        if not present:
            continue
        print(f"\n=== {stage.upper()} "
              f"({next(iter(present.values()))['train_examples']} train examples, "
              f"eval split {next(iter(present.values()))['eval_split']})")
        print(f"  {'arm':<24}{'exact':>7}{'95% CI':>18}{'schema':>8}{'verified':>10}"
              f"{'tok/train':>11}{'out tok':>9}{'lat s':>8}{'loss':>9}")
        for arm, record in sorted(present.items(), key=lambda kv: -kv[1]["exact"]):
            interval = wilson_interval(
                round(record["exact"] * record["n"]), record["n"])
            print(f"  {arm:<24}{record['exact']:>7.3f}"
                  f"{f'[{interval.lower:.3f},{interval.upper:.3f}]':>18}"
                  f"{record['schema_valid']:>8.3f}{record['verified']:>10.3f}"
                  f"{record['train_tokens']:>11}{record['mean_output_tokens']:>9.1f}"
                  f"{record['mean_latency_s']:>8.3f}"
                  f"{record['final_loss'] if record['final_loss'] is not None else 0:>9.4f}")

        # Paired comparisons against the strongest control present in this stage.
        controls = {a: r for a, r in present.items() if a in CONTROLS}
        if not controls:
            continue
        best_control = max(controls, key=lambda a: controls[a]["exact"])
        print(f"\n  best control: {best_control} at {controls[best_control]['exact']:.3f}")
        reference = tuple(float(v) for v in present[best_control]["per_item_exact"])
        for arm, record in sorted(present.items(), key=lambda kv: -kv[1]["exact"]):
            if arm == best_control:
                continue
            challenger = tuple(float(v) for v in record["per_item_exact"])
            if len(challenger) != len(reference):
                print(f"    {arm:<24}unpaired (n differs); skipped")
                continue
            delta = paired_bootstrap_difference(challenger, reference, seed=0)
            crosses = delta.lower <= 0.0 <= delta.upper
            print(f"    {arm:<24}delta {delta.estimate:+.4f}  "
                  f"95% CI [{delta.lower:+.4f},{delta.upper:+.4f}]  "
                  f"{'CONTAINS ZERO' if crosses else 'EXCLUDES ZERO'}")

    # Learning-curve separation, reported as final training loss rather than accuracy.
    print("\n=== LEARNING CURVE (final training loss, lower is faster fitting)")
    for stage in ("stage_a", "stage_b"):
        present = {arm: record[stage] for arm, record in results.items() if stage in record}
        if not present:
            continue
        ordered = sorted(present.items(), key=lambda kv: kv[1]["final_loss"] or 9)
        rendered = "  ".join(f"{a.split('_', 1)[1][:12]}:{r['final_loss']}" for a, r in ordered)
        print(f"  {stage}: {rendered}")

    print("\n=== TOKEN COST (EXAMPLE_MATCHED: token counts are NOT equal by construction)")
    for stage in ("stage_a", "stage_b"):
        present = {arm: record[stage] for arm, record in results.items() if stage in record}
        if not present:
            continue
        low = min(r["train_tokens"] for r in present.values())
        for arm, record in sorted(present.items(), key=lambda kv: kv[1]["train_tokens"]):
            print(f"  {stage} {arm:<24}{record['train_tokens']:>8} train tokens  "
                  f"({record['train_tokens'] / low:.2f}x the cheapest arm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
