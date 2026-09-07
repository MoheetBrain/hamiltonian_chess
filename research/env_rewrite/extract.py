"""One streaming pass over LeanDojo `random/train.json`: direction census + item cache.

Run:  python -m research.env_rewrite.extract

Writes the census to research/env_rewrite/measurements/direction_census.json and the
generated items to a scratch JSONL that the shortcut gate reads, so the 373 MB source is
streamed exactly once.

TRAIN ONLY.  The sealed pools are never opened; arena.environments.rewrite_direction
refuses them by path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter

from arena.environments import rewrite_direction as rw
from research.env_rewrite.stream import CORPUS_JSONL, TRAIN_JSON, iter_train_steps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "measurements")
SCRATCH = os.environ.get(
    "RWDIR_SCRATCH",
    "/private/tmp/claude-501/-Users-moheet-Documents-ChatGPT-hamiltonian-chess--claude-"
    "worktrees-phase-6-parallel-setup-9c6068/c625765c-0962-49c6-b99b-560f570581b8/scratchpad",
)
ITEMS_JSONL = os.path.join(SCRATCH, "rewrite_direction_items.jsonl")

SEED = 20260907
#: One explicit-positive L0 control twin for every N accepted items.
EXPLICIT_POSITIVE_EVERY = 10


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SCRATCH, exist_ok=True)

    started = time.time()
    signatures = rw.load_signatures(CORPUS_JSONL)
    print(f"[{time.time() - started:6.1f}s] signatures: {len(signatures)}", file=sys.stderr)

    census = {
        "steps_total": 0,
        "rw_family_tactics": 0,
        "head_counts": Counter(),
        "elements_total": Counter(),  # direction -> count, over every bracket element
        "elements_by_head": {},
        "bracket_size": Counter(),
        "tactic_first_element_direction": Counter(),
        "tactic_uniform_forward": 0,
        "tactic_uniform_reverse": 0,
        "tactic_mixed": 0,
        "with_at_location": 0,
        "rejected_trailer": 0,
    }
    discards: dict[str, int] = {}

    def steps():
        for step in iter_train_steps():
            census["steps_total"] += 1
            head = rw.tactic_head(step["tactic"])
            if head in rw.CENSUS_HEADS:
                parsed = rw.parse_rewrite_tactic(step["tactic"], step["annotated_tactic"])
                if parsed is None:
                    census["rejected_trailer"] += 1
                else:
                    census["rw_family_tactics"] += 1
                    census["head_counts"][parsed.head] += 1
                    census["bracket_size"][len(parsed.element_directions)] += 1
                    bucket = census["elements_by_head"].setdefault(parsed.head, Counter())
                    for direction in parsed.element_directions:
                        census["elements_total"][direction] += 1
                        bucket[direction] += 1
                    census["tactic_first_element_direction"][parsed.direction] += 1
                    if parsed.is_mixed:
                        census["tactic_mixed"] += 1
                    elif parsed.direction == rw.REVERSE:
                        census["tactic_uniform_reverse"] += 1
                    else:
                        census["tactic_uniform_forward"] += 1
                    if parsed.location is not None:
                        census["with_at_location"] += 1
            yield step

    written = 0
    with open(ITEMS_JSONL, "w", encoding="utf-8") as handle:
        for item in rw.generate_items(
            steps(), signatures, seed=SEED, explicit_positive_every=EXPLICIT_POSITIVE_EVERY, discards=discards
        ):
            record = item.to_dict()
            record["state"] = item.state
            record["rendered_sha256"] = hashlib.sha256(
                item.render().encode("utf-8")
            ).hexdigest()
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if written % 5000 == 0:
                print(
                    f"[{time.time() - started:6.1f}s] items {written}",
                    file=sys.stderr,
                )

    elements = census["elements_total"]
    n_elements = sum(elements.values())
    n_tactics = census["rw_family_tactics"]
    report = {
        "source": TRAIN_JSON,
        "split": "train",
        "seed": SEED,
        "explicit_positive_every": EXPLICIT_POSITIVE_EVERY,
        "environment_version": rw.ENVIRONMENT_VERSION,
        "generator_version": rw.GENERATOR_VERSION,
        "steps_total": census["steps_total"],
        "rw_family_tactics_parsed": n_tactics,
        "rw_family_tactics_rejected_trailer": census["rejected_trailer"],
        "head_counts": dict(census["head_counts"].most_common()),
        "bracket_size_distribution": dict(sorted(census["bracket_size"].items())),
        "per_element": {
            "total": n_elements,
            "forward": elements[rw.FORWARD],
            "reverse": elements[rw.REVERSE],
            "reverse_rate": round(elements[rw.REVERSE] / n_elements, 6) if n_elements else None,
        },
        "per_element_by_head": {
            head: {
                "forward": counts[rw.FORWARD],
                "reverse": counts[rw.REVERSE],
                "reverse_rate": round(
                    counts[rw.REVERSE] / (counts[rw.FORWARD] + counts[rw.REVERSE]), 6
                ),
            }
            for head, counts in sorted(census["elements_by_head"].items())
        },
        "per_tactic": {
            "total": n_tactics,
            "uniform_forward": census["tactic_uniform_forward"],
            "uniform_reverse": census["tactic_uniform_reverse"],
            "mixed_direction_bracket": census["tactic_mixed"],
            "mixed_rate": round(census["tactic_mixed"] / n_tactics, 6) if n_tactics else None,
            "first_element_forward": census["tactic_first_element_direction"][rw.FORWARD],
            "first_element_reverse": census["tactic_first_element_direction"][rw.REVERSE],
            "first_element_reverse_rate": round(
                census["tactic_first_element_direction"][rw.REVERSE] / n_tactics, 6
            )
            if n_tactics
            else None,
            "with_at_location": census["with_at_location"],
        },
        "items_written": written,
        "discards": dict(sorted(discards.items(), key=lambda kv: -kv[1])),
        "items_path": ITEMS_JSONL,
        "elapsed_seconds": round(time.time() - started, 1),
    }
    path = os.path.join(OUT_DIR, "direction_census.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    print(path, file=sys.stderr)


if __name__ == "__main__":
    main()
