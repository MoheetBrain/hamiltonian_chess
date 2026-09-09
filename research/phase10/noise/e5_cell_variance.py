"""E5 -- per-cell outcome variance: how unanimous is a cell, and how big is its Bernoulli noise?

One **cell** here is (prompt, replicate).  The endpoint is deliberately *response stability*, not
Lean acceptance: the question this wave has to answer is how much of the assay's variance the
runtime contributes before the verifier is involved at all, and that needs no Lean.

Ordering matters and is chosen to be realistic.  The replicates are run **round-robin** -- every
prompt once, then every prompt again -- because that is the order a paired assay over anchors
produces, and E2 shows that ordering, not repetition, is what perturbs an answer.  A blocked
ordering (all replicates of one prompt together) would measure the easy case and understate the
noise the assay will actually meet.

Per prompt the script reports the modal-response rate ``p``, whether the cell is unanimous, and
the within-cell Bernoulli variance ``p(1-p)`` of "the parsed tactic is the modal one".

Run::

    .venv/bin/python -m research.phase10.noise.e5_cell_variance --prompts 15 --replicates 10
"""

from __future__ import annotations

import json
import statistics
import sys

from arena.trajectory.solver import ProposalBudget
from research.phase10.noise.common import (
    JsonlWriter,
    base_parser,
    bernoulli_variance,
    by_length,
    call,
    environment_record,
    load_corpus,
    modal_fraction,
    verified_solver,
    write_meta,
)


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e5_cell_variance.jsonl")
    parser.add_argument("--prompts", type=int, default=15)
    parser.add_argument("--replicates", type=int, default=10)
    args = parser.parse_args(argv)

    solver, served = verified_solver(args.endpoint)
    corpus = by_length(load_corpus(fresh=args.fresh_goals))[: int(args.prompts)]
    if len(corpus) < 2:
        raise SystemExit("need at least two prompts")
    budget = ProposalBudget(timeout_seconds=float(args.timeout))

    responses: dict[str, list[str]] = {goal.prompt_sha256: [] for goal in corpus}
    tactics: dict[str, list[str]] = {goal.prompt_sha256: [] for goal in corpus}

    with JsonlWriter(args.out) as log:
        for replicate in range(int(args.replicates)):
            for goal in corpus:
                row = call(
                    solver,
                    goal,
                    budget=budget,
                    tags={
                        "experiment": "e5_cell_variance",
                        "ordering": "round_robin",
                        "replicate": replicate,
                        "prompt_sha256": goal.prompt_sha256,
                        "global_index": log.rows,
                    },
                )
                log.write(row)
                responses[goal.prompt_sha256].append(row["response_sha256"])
                tactics[goal.prompt_sha256].append(str(row["tactic"]))

    per_cell: dict[str, dict[str, float | int | bool]] = {}
    for goal in corpus:
        digest = goal.prompt_sha256
        _, response_rate = modal_fraction(responses[digest])
        _, tactic_rate = modal_fraction(tactics[digest])
        per_cell[digest] = {
            "prompt_chars": len(goal.prompt),
            "replicates": len(responses[digest]),
            "distinct_responses": len(set(responses[digest])),
            "distinct_tactics": len(set(tactics[digest])),
            "modal_response_rate": round(response_rate, 4),
            "modal_tactic_rate": round(tactic_rate, 4),
            "unanimous_response": len(set(responses[digest])) == 1,
            "unanimous_tactic": len(set(tactics[digest])) == 1,
            "tactic_bernoulli_variance": round(bernoulli_variance(tactics[digest]), 5),
            "response_bernoulli_variance": round(bernoulli_variance(responses[digest]), 5),
        }

    unanimous_tactic = sum(1 for row in per_cell.values() if row["unanimous_tactic"])
    unanimous_response = sum(1 for row in per_cell.values() if row["unanimous_response"])
    tactic_rates = [float(row["modal_tactic_rate"]) for row in per_cell.values()]
    variances = [float(row["tactic_bernoulli_variance"]) for row in per_cell.values()]
    summary = {
        "cells": len(per_cell),
        "replicates_per_cell": int(args.replicates),
        "cells_unanimous_tactic": unanimous_tactic,
        "cells_unanimous_tactic_fraction": round(unanimous_tactic / len(per_cell), 4),
        "cells_unanimous_response": unanimous_response,
        "cells_unanimous_response_fraction": round(unanimous_response / len(per_cell), 4),
        "mean_modal_tactic_rate": round(statistics.fmean(tactic_rates), 4),
        "min_modal_tactic_rate": round(min(tactic_rates), 4),
        "mean_tactic_bernoulli_variance": round(statistics.fmean(variances), 5),
        "max_tactic_bernoulli_variance": round(max(variances), 5),
    }

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e5_cell_variance",
            "question": "what fraction of cells are unanimous, and what is the within-cell variance?",
            "endpoint_note": "response stability, not Lean acceptance; no Lean is involved",
            "environment": environment_record(served),
            "corpus": [goal.to_dict() for goal in corpus],
            "per_cell": per_cell,
            "summary": summary,
        },
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
