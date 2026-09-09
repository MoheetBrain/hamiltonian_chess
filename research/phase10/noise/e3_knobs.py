"""E3 -- determinism knobs: does any ``options`` dict give a reproducible configuration?

This is the single most valuable output of the noise wave, so it is deliberately tested under the
condition that *breaks* things rather than the one that flatters them.  Certifying a configuration
on back-to-back repeats would be worthless: E1/E2 establish that back-to-back repetition is the
easy case.  Every configuration here is therefore probed **interleaved** -- a distinct filler
prompt between every repeat of the fixed probe -- which is the ordering a real assay produces.

Configurations (only ``options`` differs; the prompt, the ``format`` grammar and ``WIRE_FLAGS``
are the shipped ones in every arm):

``frozen_baseline``   what ``FROZEN_DECODING`` ships today.
``no_seed``           baseline with ``seed`` removed -- is the seed doing anything at all?
``temp0_only``        only ``num_ctx``/``num_predict``/``temperature=0``; no seed, no truncation.
``greedy_strict``     ``temperature=0, top_k=1, top_p=1.0, min_p=0.0, repeat_penalty=1.0`` + seed.
``greedy_strict_noseed``  the same without a seed: isolates the seed's contribution under greedy.
``topk1_seeded``      baseline + ``top_k=1``.
``topp1_seeded``      baseline + ``top_p=1.0``.
``seeded_hot``        ``temperature=1.0`` with a fixed seed -- is the seed honoured *at all*?
``unseeded_hot``      ``temperature=1.0``, no seed -- the positive control for "sampling varies".
``greedy_strict_ctx4096``  greedy_strict at a smaller ``num_ctx``: does KV allocation matter?

Run::

    .venv/bin/python -m research.phase10.noise.e3_knobs --repeats 12
"""

from __future__ import annotations

import json
import sys
from typing import Any

from arena.trajectory.solver import ProposalBudget
from research.phase10.noise.common import (
    JsonlWriter,
    base_parser,
    by_length,
    call,
    environment_record,
    load_corpus,
    modal_fraction,
    solver_with,
    variant_identity,
    verified_solver,
    write_meta,
)

#: ``(overrides, dropped_keys)`` against ``FROZEN_DECODING``.  ``None`` overrides means "start
#: from an empty options dict and use exactly what is listed", which is how ``temp0_only`` is
#: expressed without silently inheriting the frozen values.
CONFIGS: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {
    "frozen_baseline": ({}, ()),
    "no_seed": ({}, ("seed",)),
    "temp0_only": (
        {"num_ctx": 32768, "num_predict": 128, "temperature": 0.0},
        ("seed", "top_k", "top_p", "min_p", "repeat_penalty", "presence_penalty"),
    ),
    "greedy_strict": (
        {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0},
        (),
    ),
    "greedy_strict_noseed": (
        {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0},
        ("seed",),
    ),
    "topk1_seeded": ({"top_k": 1}, ()),
    "topp1_seeded": ({"top_p": 1.0}, ()),
    "seeded_hot": ({"temperature": 1.0}, ()),
    "unseeded_hot": ({"temperature": 1.0}, ("seed",)),
    "greedy_strict_ctx4096": (
        {
            "num_ctx": 4096,
            "temperature": 0.0,
            "top_k": 1,
            "top_p": 1.0,
            "min_p": 0.0,
            "repeat_penalty": 1.0,
        },
        (),
    ),
}


def main(argv: list[str] | None = None) -> int:
    parser = base_parser(__doc__ or "", "e3_knobs.jsonl")
    parser.add_argument("--repeats", type=int, default=12)
    parser.add_argument("--configs", default="", help="comma-separated subset of config names")
    parser.add_argument(
        "--probes",
        default="",
        help=(
            "comma-separated prompt_sha256 prefixes to use as probes.  E6 showed instability is "
            "prompt-specific, so a probe chosen by position in the corpus can be blind to it; "
            "naming a known-unstable prompt AND a known-stable one is what gives this design "
            "the power to tell a knob that fixes instability from a probe that never had any."
        ),
    )
    args = parser.parse_args(argv)

    _, served = verified_solver(args.endpoint)
    corpus = by_length(load_corpus(fresh=args.fresh_goals))
    wanted_probes = [p.strip() for p in args.probes.split(",") if p.strip()]
    if wanted_probes:
        probes = []
        for prefix in wanted_probes:
            matches = [goal for goal in corpus if goal.prompt_sha256.startswith(prefix)]
            if not matches:
                raise SystemExit(f"no corpus prompt starts with {prefix!r}")
            probes.append(matches[0])
    else:
        probes = [corpus[len(corpus) // 2]]
    probe_digests = {goal.prompt_sha256 for goal in probes}
    fillers = [goal for goal in corpus if goal.prompt_sha256 not in probe_digests]
    budget = ProposalBudget(timeout_seconds=float(args.timeout))
    repeats = int(args.repeats)
    wanted = [name.strip() for name in args.configs.split(",") if name.strip()] or list(CONFIGS)

    summary: dict[str, dict[str, Any]] = {}
    with JsonlWriter(args.out) as log:
        for name in wanted:
            overrides, dropped = CONFIGS[name]
            identity = variant_identity(overrides, drop=dropped)
            solver = solver_with(identity, endpoint=args.endpoint)
            for probe in probes:
                responses: list[str] = []
                tactics: list[str] = []
                for index in range(repeats):
                    filler = fillers[index % len(fillers)]
                    log.write(
                        call(
                            solver,
                            filler,
                            budget=budget,
                            tags={
                                "experiment": "e3_knobs",
                                "config": name,
                                "probe_sha256": probe.prompt_sha256,
                                "role": "filler",
                                "repeat_index": index,
                                "global_index": log.rows,
                            },
                        )
                    )
                    row = call(
                        solver,
                        probe,
                        budget=budget,
                        tags={
                            "experiment": "e3_knobs",
                            "config": name,
                            "probe_sha256": probe.prompt_sha256,
                            "role": "probe",
                            "repeat_index": index,
                            "preceded_by_sha256": filler.prompt_sha256,
                            "global_index": log.rows,
                        },
                    )
                    log.write(row)
                    responses.append(row["response_sha256"])
                    tactics.append(str(row["tactic"]))
                modal_response, response_rate = modal_fraction(responses)
                _, tactic_rate = modal_fraction(tactics)
                summary[f"{name}::{probe.prompt_sha256[:10]}"] = {
                    "config": name,
                    "probe_sha256": probe.prompt_sha256,
                    "options": identity.decoding_options(),
                    "calls": len(responses),
                    "modal_response_sha256": modal_response,
                    "distinct_responses": len(set(responses)),
                    "distinct_tactics": len(set(tactics)),
                    "modal_response_rate": round(response_rate, 4),
                    "modal_tactic_rate": round(tactic_rate, 4),
                    "reproducible": len(set(responses)) == 1,
                }
                key = f"{name}::{probe.prompt_sha256[:10]}"
                print(json.dumps({key: summary[key]}, sort_keys=True))

    # A configuration counts as reproducible only if it was reproducible on **every** probe.
    per_config: dict[str, list[bool]] = {}
    for row in summary.values():
        per_config.setdefault(str(row["config"]), []).append(bool(row["reproducible"]))

    write_meta(
        args.out.with_suffix(".meta.json"),
        {
            "experiment": "e3_knobs",
            "question": "which options dict, if any, gives a reproducible configuration?",
            "protocol": "interleaved: a distinct filler prompt between every repeat of the probe",
            "environment": environment_record(served),
            "repeats": repeats,
            "probes": [goal.to_dict() for goal in probes],
            "summary": summary,
            "reproducible_on_every_probe": sorted(
                name for name, flags in per_config.items() if all(flags)
            ),
            "not_reproducible_on_some_probe": sorted(
                name for name, flags in per_config.items() if not all(flags)
            ),
        },
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
