"""Build the legal/illegal transformation family from train-only LeanDojo data.

READ-ONLY with respect to every corpus.  No model call, no network, no Lean, no GPU.
Writes only into research/env_legal/.

Sources (the only ones permitted for development):
  <LD>/random/train.json   -- transitions and premise citations
  <LD>/corpus.jsonl        -- the library declaration index used for donor premises
"""

from __future__ import annotations

import gzip
import json
import os
import resource
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arena.environments.legal_transform import (  # noqa: E402
    GENERATOR_SEED,
    PremiseIndex,
    build_family,
    group_proofs,
    iter_proof_steps,
)
from environments.common import LEANDOJO_ROOT  # noqa: E402


def stream_train_theorems(chunk_bytes: int = 1 << 24):
    """Stream random/train.json without materialising the whole 373 MB file as one string."""

    decoder = json.JSONDecoder()
    path = os.path.join(LEANDOJO_ROOT, "random", "train.json")
    with open(path, encoding="utf-8") as handle:
        buffer = handle.read(chunk_bytes)
        buffer = buffer[buffer.index("[") + 1 :]
        while True:
            buffer = buffer.lstrip(" \n\r\t,")
            if buffer.startswith("]"):
                return
            while True:
                try:
                    obj, end = decoder.raw_decode(buffer)
                except ValueError:
                    extra = handle.read(chunk_bytes)
                    if not extra:
                        return
                    buffer += extra
                    continue
                break
            buffer = buffer[end:]
            yield obj

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS_PATH = os.path.join(HERE, "items.jsonl.gz")
BUILD_REPORT_PATH = os.path.join(HERE, "build_report.json")
FREQUENCY_PATH = os.path.join(HERE, "train_premise_frequency.json.gz")

RETAINED_THEOREMS = int(os.environ.get("LT_THEOREMS", "40000"))
PER_AXIS_CAP = int(os.environ.get("LT_CAP", "1500"))


def load_corpus_index() -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    by_file: dict[str, list[str]] = {}
    names: list[str] = []
    with open(os.path.join(LEANDOJO_ROOT, "corpus.jsonl"), encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            bucket = by_file.setdefault(record["path"], [])
            for premise in record["premises"]:
                full = premise.get("full_name")
                if full:
                    names.append(full)
                    bucket.append(full)
    return {path: tuple(items) for path, items in by_file.items()}, tuple(names)


def main() -> None:
    start = time.time()
    by_file, all_names = load_corpus_index()
    print(f"corpus.jsonl: {len(all_names)} declarations in {len(by_file)} files", flush=True)

    frequency: Counter[str] = Counter()
    steps: list = []
    retained_theorems = 0
    theorem_total = 0
    for theorem in stream_train_theorems():
        theorem_total += 1
        for tactic in theorem.get("traced_tactics") or []:
            for entry in tactic["annotated_tactic"][1]:
                full = entry.get("full_name")
                if full:
                    frequency[full] += 1
        if theorem_total <= RETAINED_THEOREMS:
            retained_theorems += 1
            steps.extend(iter_proof_steps([theorem], split="train"))
        elif os.environ.get("LT_FAST"):
            break
        if theorem_total % 20000 == 0:
            print(
                f"  ..{theorem_total} theorems, {len(steps)} steps retained, "
                f"rss={resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**30:.2f} GiB "
                f"({time.time()-start:.0f}s)",
                flush=True,
            )
    print(
        f"train.json: {theorem_total} theorems scanned for the citation prior, "
        f"{retained_theorems} retained for construction ({time.time()-start:.0f}s)",
        flush=True,
    )

    index = PremiseIndex(by_file=by_file, all_names=all_names, train_citation_frequency=frequency)
    proofs = group_proofs(steps)
    print(f"steps={len(steps)} proofs={len(proofs)} ({time.time()-start:.0f}s)", flush=True)

    items, report = build_family(
        proofs, index, seed=GENERATOR_SEED, per_axis_cap=PER_AXIS_CAP
    )
    print(f"items={len(items)} ({time.time()-start:.0f}s)", flush=True)

    with gzip.open(ITEMS_PATH, "wt", encoding="utf-8") as handle:
        for item in items:
            payload = item.to_dict()
            payload["state_before"] = item.state_before
            payload["action"] = item.action
            payload["state_after"] = item.state_after
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    with gzip.open(FREQUENCY_PATH, "wt", encoding="utf-8") as handle:
        json.dump(dict(frequency), handle, ensure_ascii=False)

    summary = report.to_dict()
    summary["retained_theorems"] = retained_theorems
    summary["theorems_scanned_for_prior"] = theorem_total
    summary["per_axis_cap"] = PER_AXIS_CAP
    summary["seed"] = GENERATOR_SEED
    summary["items_written"] = len(items)
    summary["distinct_train_cited_premises"] = len(frequency)
    summary["elapsed_seconds"] = round(time.time() - start, 1)
    with open(BUILD_REPORT_PATH, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summary.items() if k != "discards_by_reason"}, indent=1))


if __name__ == "__main__":
    main()
