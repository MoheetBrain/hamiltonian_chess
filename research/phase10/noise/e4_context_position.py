"""E4 -- context and position: is the divergence *state contamination* or *sampler randomness*?

Two designs, each of which separates the hypotheses rather than merely describing the noise.

**(a) Schedule replay.**  One fixed pseudo-random schedule of ``--length`` calls over the corpus
is executed ``--rounds`` times back to back in one process.  Position *i* of round 2 saw exactly
the same history as position *i* of round 1 -- except for everything that happened in round 1.

* If round 2 reproduces round 1 position-for-position, the runtime is a **deterministic function
  of the call history**: the divergence is carried state (KV cache, prefix reuse, allocator), and
  the fix is to control the history, not the sampler.
* If it does not, some of the variation is **not a function of the history** and no ordering
  discipline can remove it.

**(b) Predecessor dependence.**  For each of ``--predecessors`` distinct prompts *Q*, the pair
``(Q, P)`` is executed ``--pairs`` times.  If *P*'s answer is constant within a *Q* and differs
between *Q*'s, the immediately preceding call is the carrier -- the signature of prefix/KV reuse.
If it varies within a *Q*, the predecessor is not the whole story.

Position, elapsed time and distinct-prompt count are recorded on every row and analysed by
``analyze.py``; they are read off these logs rather than measured by a separate design.

Run::

    .venv/bin/python -m research.phase10.noise.e4_context_position --length 40 --rounds 3
"""

from __future__ import annotations

import json
import random
import sys
import time

from arena.trajectory.solver import ProposalBudget
from research.phase10.noise.common import (
    JsonlWriter,
    base_parser,
    by_length,
    call,
    environment_record,
    load_corpus,
    verified_solver,
    write_meta,
)


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e4_context_position.jsonl")
    parser.add_argument("--length", type=int, default=40, help="calls per schedule round")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--predecessors", type=int, default=6)
    parser.add_argument("--pairs", type=int, default=4)
    parser.add_argument("--schedule-seed", type=int, default=20260908)
    parser.add_argument(
        "--probe-sha256",
        default="",
        help=(
            "prompt_sha256 prefix for the predecessor-dependence probe.  E6 showed that "
            "instability is prompt-specific, so a probe picked by position in the corpus can "
            "be one that never varies, and the design would then be blind by construction."
        ),
    )
    args = parser.parse_args(argv)

    solver, served = verified_solver(args.endpoint)
    corpus = by_length(load_corpus(fresh=args.fresh_goals))
    budget = ProposalBudget(timeout_seconds=float(args.timeout))

    rng = random.Random(int(args.schedule_seed))
    schedule = [rng.choice(corpus) for _ in range(int(args.length))]
    started_wall = time.time()

    rounds: list[list[str]] = []
    with JsonlWriter(args.out) as log:
        # (a) schedule replay -----------------------------------------------------------------
        for round_index in range(int(args.rounds)):
            answers: list[str] = []
            for position, goal in enumerate(schedule):
                row = call(
                    solver,
                    goal,
                    budget=budget,
                    tags={
                        "experiment": "e4_context_position",
                        "design": "schedule_replay",
                        "round": round_index,
                        "position": position,
                        "schedule_seed": int(args.schedule_seed),
                        "elapsed_s": round(time.time() - started_wall, 3),
                        "global_index": log.rows,
                    },
                )
                log.write(row)
                answers.append(row["response_sha256"])
            rounds.append(answers)

        # (b) predecessor dependence ----------------------------------------------------------
        if args.probe_sha256:
            matches = [g for g in corpus if g.prompt_sha256.startswith(args.probe_sha256)]
            if not matches:
                raise SystemExit(f"no corpus prompt starts with {args.probe_sha256!r}")
            probe = matches[0]
        else:
            probe = corpus[len(corpus) // 2]
        predecessors = [goal for goal in corpus if goal.prompt_sha256 != probe.prompt_sha256][
            : int(args.predecessors)
        ]
        by_predecessor: dict[str, list[str]] = {}
        for predecessor in predecessors:
            observed: list[str] = []
            for pair_index in range(int(args.pairs)):
                log.write(
                    call(
                        solver,
                        predecessor,
                        budget=budget,
                        tags={
                            "experiment": "e4_context_position",
                            "design": "predecessor",
                            "role": "predecessor",
                            "predecessor_sha256": predecessor.prompt_sha256,
                            "pair_index": pair_index,
                            "global_index": log.rows,
                        },
                    )
                )
                row = call(
                    solver,
                    probe,
                    budget=budget,
                    tags={
                        "experiment": "e4_context_position",
                        "design": "predecessor",
                        "role": "probe",
                        "predecessor_sha256": predecessor.prompt_sha256,
                        "pair_index": pair_index,
                        "global_index": log.rows,
                    },
                )
                log.write(row)
                observed.append(row["response_sha256"])
            by_predecessor[predecessor.prompt_sha256] = observed

    agreement = []
    for later in range(1, len(rounds)):
        matches = sum(1 for a, b in zip(rounds[0], rounds[later], strict=True) if a == b)
        agreement.append(
            {
                "round": later,
                "positions": len(rounds[0]),
                "identical_to_round_0": matches,
                "rate": round(matches / len(rounds[0]), 4),
            }
        )
    unanimous_positions = sum(
        1
        for position in range(len(schedule))
        if len({answers[position] for answers in rounds}) == 1
    )

    predecessor_summary = {
        digest: {
            "calls": len(values),
            "distinct_probe_responses": len(set(values)),
            "constant_within_predecessor": len(set(values)) == 1,
            "response_sha256": sorted(set(values)),
        }
        for digest, values in by_predecessor.items()
    }
    distinct_across = {
        digest: sorted(set(values))[0] for digest, values in by_predecessor.items() if values
    }

    summary = {
        "schedule_replay": {
            "length": len(schedule),
            "rounds": len(rounds),
            "distinct_prompts_in_schedule": len({goal.prompt_sha256 for goal in schedule}),
            "agreement_with_round_0": agreement,
            "positions_unanimous_across_rounds": unanimous_positions,
            "positions_unanimous_rate": round(unanimous_positions / len(schedule), 4),
        },
        "predecessor": {
            "predecessors": len(predecessor_summary),
            "pairs_each": int(args.pairs),
            "constant_within_every_predecessor": all(
                row["constant_within_predecessor"] for row in predecessor_summary.values()
            ),
            "distinct_probe_answers_across_predecessors": len(set(distinct_across.values())),
            "per_predecessor": predecessor_summary,
        },
    }

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e4_context_position",
            "question": "is divergence a deterministic function of call history, or is it random?",
            "environment": environment_record(served),
            "schedule": [goal.prompt_sha256 for goal in schedule],
            "probe": probe.to_dict(),
            "summary": summary,
        },
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
