"""E6 -- replay the exact prompts on which HC-V0.5 diverged.

E1 and E2 established that ``prompt -> response`` is byte-stable for the prompts they used.  They
did **not** establish that it is byte-stable for *every* prompt, because they used a corpus of
fresh Lean states that happens to contain none of the prompts on which HC-V0.5 actually diverged.
That is the gap this script closes, and it is the difference between "the runtime is
deterministic" and "the runtime was deterministic on the prompts we happened to try".

The corpus here is therefore **not** the fresh one.  It is the HC-V0.5 smoke artefact's own
states, recovered by verified ``prompt_sha256`` so that every prompt sent is byte-identical to one
the runtime demonstrably saw during the divergent run.  Prompts are split into two groups, and the
grouping is read off the *recorded* run rather than chosen by hand:

``suspect``   a ``prompt_sha256`` that occurred more than once in ``hc_v0_5_smoke.json`` with more
              than one distinct ``(tactic, completion_tokens)`` pair -- i.e. the runtime already
              answered it two ways.
``control``   a ``prompt_sha256`` that occurred more than once with a single distinct answer.

Both groups are replayed under the same two orderings, so "suspect diverges / control does not"
cannot be an artefact of how each group was run:

``solo``          ``--repeats`` back-to-back calls, nothing in between.
``interleaved``   a distinct filler prompt between every repeat.

Every row carries the **verbatim** ``raw_output``.  That matters: HC-V0.5's divergence was visible
in ``completion_tokens`` while the parsed ``tactic`` was unchanged, so a script that recorded only
the tactic would have reported perfect determinism on a run that was not.

Run::

    .venv/bin/python -m research.phase10.noise.e6_divergent_replay --repeats 30
"""

from __future__ import annotations

import collections
import json
import sys
from typing import Any

from arena.trajectory.solver import ProposalBudget
from research.phase10.noise.common import (
    SMOKE_ARTIFACT,
    Goal,
    JsonlWriter,
    base_parser,
    call,
    environment_record,
    modal_fraction,
    read_jsonl,
    solver_with,
    variant_identity,
    verified_solver,
    write_meta,
)
from research.phase10.noise.common import _recorded_goals as recorded_goals


def recorded_answers(path: Any = SMOKE_ARTIFACT) -> dict[str, list[dict[str, Any]]]:
    """Every step of the recorded run, grouped by the prompt that produced it."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for episode in payload["episodes"]:
        for step in episode["steps"]:
            grouped[str(step["prompt_sha256"])].append(
                {
                    "task_id": str(episode.get("task_id", "")),
                    "index": int(step.get("index", -1)),
                    "tactic": step.get("tactic"),
                    "completion_tokens": step.get("completion_tokens"),
                    "prompt_tokens": step.get("prompt_tokens"),
                    "action_result": step.get("action_result"),
                }
            )
    return dict(grouped)


def classify(recorded: dict[str, list[dict[str, Any]]]) -> tuple[list[str], list[str]]:
    """``(suspect, control)``: repeated prompts that did, and did not, answer two ways."""

    suspect: list[str] = []
    control: list[str] = []
    for digest, steps in sorted(recorded.items()):
        if len(steps) < 2:
            continue
        answers = {(str(step["tactic"]), step["completion_tokens"]) for step in steps}
        (suspect if len(answers) > 1 else control).append(digest)
    return suspect, control


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e6_divergent_replay.jsonl")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--controls", type=int, default=5, help="control prompts to replay")
    args = parser.parse_args(argv)

    _, served = verified_solver(args.endpoint)
    recorded = recorded_answers()
    suspect_digests, control_digests = classify(recorded)
    by_digest: dict[str, Goal] = {
        goal.prompt_sha256: goal for goal in recorded_goals(SMOKE_ARTIFACT)
    }

    selected: list[tuple[str, Goal]] = []
    missing: list[str] = []
    for digest in suspect_digests:
        if digest in by_digest:
            selected.append(("suspect", by_digest[digest]))
        else:
            missing.append(digest)
    for digest in control_digests[: int(args.controls)]:
        if digest in by_digest:
            selected.append(("control", by_digest[digest]))
    if not selected:
        raise SystemExit("no replayable prompts recovered from the smoke artefact")

    chosen = {goal.prompt_sha256 for _, goal in selected}
    fillers = [goal for goal in by_digest.values() if goal.prompt_sha256 not in chosen]
    budget = ProposalBudget(timeout_seconds=float(args.timeout))
    solver = solver_with(variant_identity(), endpoint=args.endpoint)
    repeats = int(args.repeats)

    with JsonlWriter(args.out) as log:
        for arm in ("solo", "interleaved"):
            for group, goal in selected:
                for index in range(repeats):
                    if arm == "interleaved" and fillers:
                        filler = fillers[index % len(fillers)]
                        log.write(
                            call(
                                solver,
                                filler,
                                budget=budget,
                                tags={
                                    "experiment": "e6_divergent_replay",
                                    "arm": arm,
                                    "group": "filler",
                                    "role": "filler",
                                    "repeat_index": index,
                                    "global_index": log.rows,
                                },
                            )
                        )
                    log.write(
                        call(
                            solver,
                            goal,
                            budget=budget,
                            tags={
                                "experiment": "e6_divergent_replay",
                                "arm": arm,
                                "group": group,
                                "role": "probe",
                                "repeat_index": index,
                                "global_index": log.rows,
                            },
                        )
                    )

    rows = [row for row in read_jsonl(args.out) if row.get("role") == "probe"]
    per_prompt: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row['arm']}::{row['prompt_sha256']}"
        per_prompt.setdefault(
            key,
            {
                "arm": row["arm"],
                "group": row["group"],
                "prompt_sha256": row["prompt_sha256"],
                "prompt_chars": row["prompt_chars"],
                "raw": [],
                "tactics": [],
                "completion_tokens": [],
            },
        )
        per_prompt[key]["raw"].append(row["response_sha256"])
        per_prompt[key]["tactics"].append(str(row["tactic"]))
        per_prompt[key]["completion_tokens"].append(row["completion_tokens"])

    summary: dict[str, Any] = {}
    for key, cell in sorted(per_prompt.items()):
        _, raw_rate = modal_fraction(cell["raw"])
        _, tactic_rate = modal_fraction(cell["tactics"])
        summary[key] = {
            "arm": cell["arm"],
            "group": cell["group"],
            "prompt_chars": cell["prompt_chars"],
            "calls": len(cell["raw"]),
            "distinct_raw_responses": len(set(cell["raw"])),
            "distinct_tactics": len(set(cell["tactics"])),
            "distinct_completion_tokens": sorted(set(cell["completion_tokens"])),
            "modal_raw_rate": round(raw_rate, 4),
            "modal_tactic_rate": round(tactic_rate, 4),
            "byte_stable": len(set(cell["raw"])) == 1,
            "tactic_stable": len(set(cell["tactics"])) == 1,
            "recorded_answers": recorded.get(cell["prompt_sha256"], []),
        }

    headline = {
        "prompts_replayed": len(selected),
        "suspect_prompts": sum(1 for group, _ in selected if group == "suspect"),
        "control_prompts": sum(1 for group, _ in selected if group == "control"),
        "repeats_each_arm": repeats,
        "cells_byte_stable": sum(1 for row in summary.values() if row["byte_stable"]),
        "cells_total": len(summary),
        "cells_tactic_stable": sum(1 for row in summary.values() if row["tactic_stable"]),
        "byte_unstable_cells": sorted(
            key for key, row in summary.items() if not row["byte_stable"]
        ),
        "tactic_unstable_cells": sorted(
            key for key, row in summary.items() if not row["tactic_stable"]
        ),
        "unrecovered_suspect_digests": missing,
    }

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e6_divergent_replay",
            "question": "are the prompts on which HC-V0.5 diverged still non-deterministic?",
            "corpus": "hc_v0_5_smoke.json states, recovered by verified prompt_sha256",
            "environment": environment_record(served),
            "suspect_digests": suspect_digests,
            "control_digests": control_digests[: int(args.controls)],
            "per_cell": summary,
            "summary": headline,
        },
    )
    print(json.dumps(headline, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
