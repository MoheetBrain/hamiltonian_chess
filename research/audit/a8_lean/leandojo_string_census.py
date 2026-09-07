"""A8: what truth-relevant information is ABSENT from the LeanDojo strings.

Bounded census over the first N theorems of the permitted development source
(random/train.json).  Never opens a sealed split -- it goes through
arena.environments.premise_selection.require_permitted_train, which raises on all four.

Read-only, no model call.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from arena.environments import premise_selection as ps

SOURCE = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4"
)

INACCESSIBLE = re.compile("✝")          # the `h✝` dagger: name is NOT a usable identifier
UNIV_MVAR = re.compile(r"\?u\.\d+")           # unassigned universe metavariable
EXPR_MVAR = re.compile(r"\?m\.\d+|\?[a-zA-Z_][\w']*\b")
ELIDED = re.compile("⋯|…")          # `⋯` / `…` : pretty-printer truncation
CASE = re.compile(r"(?m)^case\s")
GOAL = re.compile(r"(?m)^⊢")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-theorems", type=int, default=5000)
    ap.add_argument("--out", type=Path, default=Path("research/audit/a8_lean/out/leandojo_string_census.json"))
    args = ap.parse_args()

    train = ps.require_permitted_train(SOURCE / "random/train.json")
    c: Counter[str] = Counter()
    short_name_owners: dict[str, set[str]] = {}
    premise_names: Counter[str] = Counter()

    for theorem in ps.stream_traced_theorems(train, limit=args.limit_theorems):
        c["theorems"] += 1
        for step in ps.raw_steps(theorem):
            c["steps"] += 1
            s = step.state_before
            if not s.strip():
                c["empty_state_before"] += 1
                continue
            n_goals = len(GOAL.findall(s))
            c[f"goals_{min(n_goals, 5)}"] += 1
            if n_goals != 1:
                c["state_not_single_goal"] += 1
            if INACCESSIBLE.search(s):
                c["state_has_inaccessible_dagger_names"] += 1
            if UNIV_MVAR.search(s):
                c["state_has_universe_metavariable"] += 1
            if EXPR_MVAR.search(s):
                c["state_has_any_metavariable_marker"] += 1
            if ELIDED.search(s):
                c["state_has_elided_subterm"] += 1
            if CASE.search(s):
                c["state_has_case_labels"] += 1
            if ps.is_usable(step):
                c["usable_by_production_filter"] += 1
                if INACCESSIBLE.search(s):
                    c["usable_and_inaccessible_names"] += 1
                if UNIV_MVAR.search(s):
                    c["usable_and_universe_mvar"] += 1
                if ELIDED.search(s):
                    c["usable_and_elided"] += 1
            for ref in step.premises:
                premise_names[ref.full_name] += 1
                short = ref.full_name.rsplit(".", 1)[-1]
                short_name_owners.setdefault(short, set()).add(ref.full_name)

    ambiguous = {k: sorted(v) for k, v in short_name_owners.items() if len(v) > 1}
    report = {
        "source": str(train),
        "theorems_scanned": c["theorems"],
        "counters": dict(c),
        "rates": {
            k: c[k] / c["steps"]
            for k in (
                "state_has_inaccessible_dagger_names",
                "state_has_universe_metavariable",
                "state_has_any_metavariable_marker",
                "state_has_elided_subterm",
                "state_has_case_labels",
                "state_not_single_goal",
            )
            if c["steps"]
        },
        "premise_short_name_collisions": {
            "distinct_full_names": len(premise_names),
            "distinct_short_names": len(short_name_owners),
            "short_names_owned_by_more_than_one_full_name": len(ambiguous),
            "examples": dict(list(ambiguous.items())[:10]),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "premise_short_name_collisions"}, indent=2))
    print("collisions:", json.dumps({k: v for k, v in report["premise_short_name_collisions"].items() if k != "examples"}, indent=2))


if __name__ == "__main__":
    main()
