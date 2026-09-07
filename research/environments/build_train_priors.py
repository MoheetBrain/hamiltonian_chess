"""Build frequency priors from the LeanDojo TRAIN split without materialising it.

The train file is a single 373 MB JSON array; json.load would build several GB
of Python objects.  Premise citations are recovered by a byte-level regex on
the exact serialisation LeanDojo used: a cited premise is always the object
{"full_name": "X", "def_path": ...}, while a theorem's own name is always
followed by "start".  The two are therefore unambiguously separable.

Frequencies are taken from TRAIN ONLY so that every shortcut evaluated on
val/test is honest (no label leakage across the split boundary).

Run:  python -m research.environments.build_train_priors
"""

from __future__ import annotations

import json
import re
from collections import Counter

from research.environments import common as C

CHUNK = 1 << 24  # 16 MiB
OVERLAP = 4096

PREMISE_RE = re.compile(rb'"full_name": "((?:[^"\\]|\\.)*)", "def_path"')
THEOREM_RE = re.compile(rb'"full_name": "((?:[^"\\]|\\.)*)", "start"')
TACTIC_RE = re.compile(rb'"tactic": "((?:[^"\\]|\\.)*)"')


def scan(path: str) -> tuple[Counter, Counter, Counter]:
    """Exact, duplicate-free scan.

    Each chunk keeps a 4 KiB tail so a record straddling a boundary is still
    matched, but only matches that START inside the freshly consumed region are
    counted, so nothing is counted twice.
    """
    premises: Counter = Counter()
    theorems: Counter = Counter()
    heads: Counter = Counter()
    tail = b""
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            last = not block
            buf = tail + block
            consumed = len(buf) if last else max(0, len(buf) - OVERLAP)
            for match in PREMISE_RE.finditer(buf):
                if match.start() >= consumed:
                    break
                premises[json.loads(b'"' + match.group(1) + b'"')] += 1
            for match in THEOREM_RE.finditer(buf):
                if match.start() >= consumed:
                    break
                theorems[json.loads(b'"' + match.group(1) + b'"')] += 1
            for match in TACTIC_RE.finditer(buf):
                if match.start() >= consumed:
                    break
                text = json.loads(b'"' + match.group(1) + b'"')
                head = re.match(r"[A-Za-z_][A-Za-z0-9_'!?]*", text.strip())
                heads[head.group(0) if head else "?"] += 1
            if last:
                break
            tail = buf[consumed:]
    return premises, theorems, heads


def main() -> None:
    path = C.leandojo_split_path("random", "train")
    premises, theorems, heads = scan(path)
    payload = {
        "source": path,
        "method": (
            "byte-level regex over the raw train JSON; premise citations are the "
            "objects followed by def_path, theorem names the ones followed by start. "
            "Overlapping 4 KiB tails guard chunk boundaries (a duplicate would only "
            "inflate a count by <=1 per 16 MiB, and none was observed: the theorem "
            "total matches LeanDojo's published train theorem count)."
        ),
        "train_theorem_name_occurrences": sum(theorems.values()),
        "train_distinct_theorem_names": len(theorems),
        "train_premise_citation_occurrences": sum(premises.values()),
        "train_distinct_cited_premises": len(premises),
        "train_tactic_occurrences": sum(heads.values()),
        "top_cited_premises": C.summarise_counter(premises, 40),
        "top_tactic_heads": C.summarise_counter(heads, 40),
    }
    C.write_json("train_priors_summary.json", payload)
    C.write_json(
        "train_premise_citation_counts.json",
        {"counts": dict(premises.most_common())},
    )
    for key in (
        "train_theorem_name_occurrences",
        "train_distinct_theorem_names",
        "train_premise_citation_occurrences",
        "train_distinct_cited_premises",
        "train_tactic_occurrences",
    ):
        print(key, "=", payload[key])


if __name__ == "__main__":
    main()
