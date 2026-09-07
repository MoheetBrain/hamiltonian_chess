"""A9 headline: what ``_premise_family`` does that the other two generators do not.

For every family in the bank, compare the ORIGINAL and COUNTERFACTUAL siblings on the two
quantities every V5 state-rule is a function of -- the first-occurrence offset and the occurrence
count of each of the two answer identifiers -- in both the canonical record V5 audits and the
rendered prompt the Solver reads.

A generator is BALANCED BY CONSTRUCTION on a rule iff those quantities are INVARIANT across the
twin while the target flips: then the rule predicts the same option for both siblings, is right on
exactly one, and scores exactly 0.5 with no dependence on the content.

ZERO model calls.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    V5Variant,
    V5Probe,
    build_prompt,
    equal_information_genome,
)

CONTROL = equal_information_genome()


def stats(body: str, a: str, b: str) -> dict[str, int]:
    return {
        "first_a": body.find(f'"{a}"'),
        "first_b": body.find(f'"{b}"'),
        "count_a": body.count(f'"{a}"'),
        "count_b": body.count(f'"{b}"'),
    }


def main() -> int:
    with Path(sys.argv[1]).open("rb") as handle:
        probes: tuple[V5Probe, ...] = pickle.load(handle)
    fams: dict[str, dict[str, V5Probe]] = defaultdict(dict)
    for p in probes:
        fams[p.family_id][p.variant.value] = p

    summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "families": 0,
            "canonical_stats_invariant_across_twin": 0,
            "canonical_stats_swapped_across_twin": 0,
            "prompt_stats_invariant_across_twin": 0,
            "prompt_stats_swapped_across_twin": 0,
            "prompt_first_offsets_invariant": 0,
            "prompt_counts_invariant": 0,
        }
    )
    rows = []
    for fid, by_variant in sorted(fams.items()):
        o = by_variant.get(V5Variant.ORIGINAL.value)
        c = by_variant.get(V5Variant.COUNTERFACTUAL.value)
        if o is None or c is None:
            continue
        a = str(o.options[0].arguments[0].value)
        b = str(o.options[1].arguments[0].value)
        key = f"{o.mechanism}/L{o.level}"
        s = summary[key]
        s["families"] += 1
        for label, body_of in (
            ("canonical", lambda p: canonical_json(p.state.to_dict(include_display_identity=False))),
            ("prompt", lambda p: build_prompt(CONTROL, p)),
        ):
            so, sc = stats(body_of(o), a, b), stats(body_of(c), a, b)
            invariant = so == sc
            swapped = (
                so["first_a"] == sc["first_b"]
                and so["first_b"] == sc["first_a"]
                and so["count_a"] == sc["count_b"]
                and so["count_b"] == sc["count_a"]
                and so != sc
            )
            s[f"{label}_stats_invariant_across_twin"] += int(invariant)
            s[f"{label}_stats_swapped_across_twin"] += int(swapped)
            if label == "prompt":
                s["prompt_first_offsets_invariant"] += int(
                    so["first_a"] == sc["first_a"] and so["first_b"] == sc["first_b"]
                )
                s["prompt_counts_invariant"] += int(
                    so["count_a"] == sc["count_a"] and so["count_b"] == sc["count_b"]
                )
                rows.append(
                    {
                        "cell": key,
                        "family": fid,
                        "original": so,
                        "counterfactual": sc,
                    }
                )
    out = Path(sys.argv[2])
    out.write_text(json.dumps({"by_cell": dict(summary), "prompt_rows": rows}, indent=2, sort_keys=True))
    print(
        f"{'cell':30s} {'fams':>4s} {'canon_inv':>9s} {'canon_swap':>10s} "
        f"{'prompt_inv':>10s} {'prompt_swap':>11s} {'p_first_inv':>11s} {'p_count_inv':>11s}"
    )
    for key in sorted(summary):
        s = summary[key]
        print(
            f"{key:30s} {s['families']:4d} {s['canonical_stats_invariant_across_twin']:9d} "
            f"{s['canonical_stats_swapped_across_twin']:10d} "
            f"{s['prompt_stats_invariant_across_twin']:10d} {s['prompt_stats_swapped_across_twin']:11d} "
            f"{s['prompt_first_offsets_invariant']:11d} {s['prompt_counts_invariant']:11d}"
        )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
