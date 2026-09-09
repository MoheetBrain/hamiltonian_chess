"""E1 -- back-to-back determinism.

Question: is ``prompt -> response`` deterministic when one fixed real prompt is repeated
consecutively in one server process, with nothing else in between?

Three prompts are probed rather than one -- the shortest, the median and the longest in the
corpus -- because prompt length is one of the factors HC-V0.6 has to rule in or out, and
back-to-back repetition is the cheapest place to look at it.  Each is repeated ``--repeats``
times (default 40, the brief's floor is 30).

Run::

    .venv/bin/python -m research.phase10.noise.e1_back_to_back --repeats 40
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
    parser = base_parser(__doc__ or "", "e1_back_to_back.jsonl")
    parser.add_argument("--repeats", type=int, default=40)
    args = parser.parse_args(argv)

    solver, served = verified_solver(args.endpoint)
    corpus = by_length(load_corpus(fresh=args.fresh_goals))
    probes = {
        "short": corpus[0],
        "median": corpus[len(corpus) // 2],
        "long": corpus[-1],
    }
    budget = ProposalBudget(timeout_seconds=float(args.timeout))

    summary: dict[str, dict[str, float | int | str]] = {}
    with JsonlWriter(args.out) as log:
        for stratum, goal in probes.items():
            responses: list[str] = []
            tactics: list[str] = []
            for index in range(int(args.repeats)):
                row = call(
                    solver,
                    goal,
                    budget=budget,
                    tags={
                        "experiment": "e1_back_to_back",
                        "stratum": stratum,
                        "repeat_index": index,
                        "global_index": log.rows,
                    },
                )
                log.write(row)
                responses.append(row["response_sha256"])
                tactics.append(str(row["tactic"]))
            modal_response, response_rate = modal_fraction(responses)
            _, tactic_rate = modal_fraction(tactics)
            summary[stratum] = {
                "prompt_sha256": goal.prompt_sha256,
                "prompt_chars": len(goal.prompt),
                "calls": len(responses),
                "distinct_responses": len(set(responses)),
                "distinct_tactics": len(set(tactics)),
                "modal_response_rate": round(response_rate, 4),
                "modal_tactic_rate": round(tactic_rate, 4),
                "first_match_rate": round(
                    sum(1 for value in responses if value == responses[0]) / len(responses), 4
                ),
                "modal_response_sha256": modal_response,
            }

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e1_back_to_back",
            "question": "is prompt->response deterministic back-to-back in one server process?",
            "environment": environment_record(served),
            "repeats": int(args.repeats),
            "goal_source": next(iter(probes.values())).source,
            "probes": {name: goal.to_dict() for name, goal in probes.items()},
            "summary": summary,
        },
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
