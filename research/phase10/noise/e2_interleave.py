"""E2 -- interleaving.

Question: does putting *other* prompts between repeats of a fixed prompt change the fixed
prompt's answer?  HC-V0.5 observed exactly this ("in isolation the same prompt returns the same
answer six times out of six; the divergence appears once other calls have passed through the same
server process") and it is the effect that decides whether a paired assay is viable.

Two arms, run one after the other inside a single process against a single server process:

* ``solo``          -- P, P, P, ... ``--repeats`` times, nothing in between.
* ``interleaved``   -- P, F1, P, F2, P, F3, ... with a distinct filler prompt between every
  repeat of P.  Fillers are drawn from the corpus in a fixed order and never repeated.

The arms differ in exactly one thing: what the server saw between two calls to P.

Run::

    .venv/bin/python -m research.phase10.noise.e2_interleave --repeats 30
"""

from __future__ import annotations

import json
import sys

from arena.trajectory.solver import ProposalBudget
from research.phase10.noise.common import (
    JsonlWriter,
    base_parser,
    by_length,
    call,
    environment_record,
    load_corpus,
    modal_fraction,
    verified_solver,
    write_meta,
)


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e2_interleave.jsonl")
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args(argv)

    solver, served = verified_solver(args.endpoint)
    corpus = by_length(load_corpus(fresh=args.fresh_goals))
    probe = corpus[len(corpus) // 2]
    fillers = [goal for goal in corpus if goal.prompt_sha256 != probe.prompt_sha256]
    if not fillers:
        raise SystemExit("the corpus has no second prompt to interleave with")
    budget = ProposalBudget(timeout_seconds=float(args.timeout))
    repeats = int(args.repeats)

    arms: dict[str, list[str]] = {"solo": [], "interleaved": []}
    arm_tactics: dict[str, list[str]] = {"solo": [], "interleaved": []}

    with JsonlWriter(args.out) as log:
        for index in range(repeats):
            row = call(
                solver,
                probe,
                budget=budget,
                tags={
                    "experiment": "e2_interleave",
                    "arm": "solo",
                    "role": "probe",
                    "repeat_index": index,
                    "distinct_prompts_seen_before": 1,
                    "global_index": log.rows,
                },
            )
            log.write(row)
            arms["solo"].append(row["response_sha256"])
            arm_tactics["solo"].append(str(row["tactic"]))

        seen = 1
        for index in range(repeats):
            filler = fillers[index % len(fillers)]
            row = call(
                solver,
                filler,
                budget=budget,
                tags={
                    "experiment": "e2_interleave",
                    "arm": "interleaved",
                    "role": "filler",
                    "repeat_index": index,
                    "filler_sha256": filler.prompt_sha256,
                    "global_index": log.rows,
                },
            )
            log.write(row)
            seen += 1
            row = call(
                solver,
                probe,
                budget=budget,
                tags={
                    "experiment": "e2_interleave",
                    "arm": "interleaved",
                    "role": "probe",
                    "repeat_index": index,
                    "preceded_by_sha256": filler.prompt_sha256,
                    "distinct_prompts_seen_before": seen,
                    "global_index": log.rows,
                },
            )
            log.write(row)
            arms["interleaved"].append(row["response_sha256"])
            arm_tactics["interleaved"].append(str(row["tactic"]))

    summary: dict[str, dict[str, float | int | str]] = {}
    for arm, responses in arms.items():
        modal_response, response_rate = modal_fraction(responses)
        _, tactic_rate = modal_fraction(arm_tactics[arm])
        summary[arm] = {
            "calls": len(responses),
            "distinct_responses": len(set(responses)),
            "distinct_tactics": len(set(arm_tactics[arm])),
            "modal_response_rate": round(response_rate, 4),
            "modal_tactic_rate": round(tactic_rate, 4),
            "modal_response_sha256": modal_response,
        }
    summary["cross_arm"] = {
        "solo_modal_equals_interleaved_modal": str(
            summary["solo"]["modal_response_sha256"]
            == summary["interleaved"]["modal_response_sha256"]
        )
    }

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e2_interleave",
            "question": "does interleaving other prompts change the answer to a fixed prompt?",
            "environment": environment_record(served),
            "repeats": repeats,
            "probe": probe.to_dict(),
            "fillers_available": len(fillers),
            "summary": summary,
        },
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
