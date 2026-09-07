"""A9: could the shortcut cue be REMOVED or BALANCED at generation time, per mechanism?

Measured against the real generator, not hypothesised.

Part 1 -- ``formal_expression_depth``.  Its only prompt-visible leak under V5's rule set is
``more_frequent_in_state``: ``relabel`` (``formal_structural.py:181``) swaps the two identities, so
the *per-identifier* occurrence counts swap with the answer.  The cue vanishes on any source state
where the two identities occur EQUALLY often, because then the rule's prediction is constant across
the twin and the family scores exactly 1 of 2.  ``occurrences`` are already computed by
``identifier_depths`` inside ``structural_features``, so this is a one-predicate eligibility filter.
This script counts how many eligible source states satisfy it, per depth stratum.

Part 2 -- polarity balance.  For each cell and each informative rule, count the opposite-polarity
family pairs available: a 2-of-2 family plus a 0-of-2 family average to exactly 0.5.  This is the
other constructible balancing primitive, and it needs no change to the mathematics at all.

ZERO model calls.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from arena.environments.formal_structural import (
    build_state,
    identifier_depths,
    load_formal_states,
)
from arena.experiments.fitness_v5 import (
    CONTEXT_GUARD,
    POSITIVE_VARIANTS,
    V5Probe,
    v5_founders,
)
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.environments.formal_structural import stratify

from .pairs import RULES, CONSTANT_RULES


def formal_pool_feasibility() -> dict[str, Any]:
    budget = int(CONTEXT_GUARD["probe_selection_max_chars_any_surface"])
    langs = [GenomePhenotypeLanguage(g.surface) for g in v5_founders()]
    eligible = []
    for state in load_formal_states():
        canonical = build_state(state.target, state.context_identities, "deepest_local_reference")
        if max(len(lang.render(canonical)) for lang in langs) <= budget:
            eligible.append(state)
    buckets = stratify(eligible)
    out: dict[str, Any] = {"eligible_states": len(eligible), "strata": {}}
    for name, bucket in buckets.items():
        tie = more = fewer = 0
        for state in bucket:
            occ = identifier_depths(state.target)
            deep = state.features.deepest_identifier
            runner = state.features.runner_up_identifier
            nd, nr = len(occ.get(deep, [])), len(occ.get(runner, []))
            if nd == nr:
                tie += 1
            elif nd > nr:
                more += 1
            else:
                fewer += 1
        out["strata"][name] = {
            "states": len(bucket),
            "count_tie_deepest_eq_runnerup": tie,
            "count_deepest_more_frequent": more,
            "count_deepest_less_frequent": fewer,
            "dev_families_needed": 12,
            "tie_filter_feasible_at_dev_scale": tie >= 12,
            "polarity_balanced_pairs_available": min(more, fewer),
            "polarity_balance_feasible_at_dev_scale": min(more, fewer) >= 6,
        }
    return out


def polarity_pairs(bank: Path) -> dict[str, Any]:
    with bank.open("rb") as handle:
        probes: tuple[V5Probe, ...] = pickle.load(handle)
    cells: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for p in probes:
        if p.variant.value in POSITIVE_VARIANTS:
            cells[(p.mechanism, p.level)].append(p)
    out: dict[str, Any] = {}
    for (mechanism, level), cell in sorted(cells.items()):
        by_family: dict[str, list[V5Probe]] = defaultdict(list)
        for p in cell:
            by_family[p.family_id].append(p)
        entry: dict[str, Any] = {}
        for rule_name, rule in RULES.items():
            if rule_name in CONSTANT_RULES:
                continue
            hits = Counter(
                sum(rule(p) == p.expected_index for p in members)
                for members in by_family.values()
            )
            entry[rule_name] = {
                "families_2of2": hits[2],
                "families_1of2_balanced_by_construction": hits[1],
                "families_0of2": hits[0],
                "opposite_polarity_pairs_available": min(hits[2], hits[0]),
                "max_balanced_families_by_selection": hits[1] + 2 * min(hits[2], hits[0]),
                "families_needed_for_24_positives": 12,
            }
        out[f"{mechanism}/L{level}"] = entry
    return out


def main() -> int:
    bank = Path(sys.argv[1])
    out = Path(sys.argv[2])
    report = {
        "formal_expression_depth_source_pool": formal_pool_feasibility(),
        "polarity_pairs_by_cell": polarity_pairs(bank),
    }
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    pool = report["formal_expression_depth_source_pool"]
    print(f"eligible formal source states: {pool['eligible_states']}")
    for name, s in pool["strata"].items():
        print(
            f"  {name:8s} n={s['states']:4d} tie={s['count_tie_deepest_eq_runnerup']:4d} "
            f"more={s['count_deepest_more_frequent']:4d} fewer={s['count_deepest_less_frequent']:4d} "
            f"tie_filter_ok={s['tie_filter_feasible_at_dev_scale']} "
            f"polarity_ok={s['polarity_balance_feasible_at_dev_scale']}"
        )
    print()
    for cell, entry in report["polarity_pairs_by_cell"].items():
        for rule, v in entry.items():
            if v["families_2of2"] == 0 and v["families_0of2"] == 0:
                continue
            print(
                f"{cell:30s} {rule:26s} 2of2={v['families_2of2']:2d} 1of2={v['families_1of2_balanced_by_construction']:2d} "
                f"0of2={v['families_0of2']:2d} opposite_pairs={v['opposite_polarity_pairs_available']:2d} "
                f"max_balanced_families={v['max_balanced_families_by_selection']:2d}/12"
            )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
