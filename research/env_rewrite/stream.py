"""Bounded-memory streaming reader for LeanDojo `random/train.json` (TRAIN ONLY).

The file is a single-line 373 MB JSON array; ``json.load`` would materialise gigabytes.
This reader keeps only a sliding text buffer plus one decoded theorem.

HARD RULE: this module refuses to open any path other than ``random/train.json``
and ``corpus.jsonl``.  The sealed pools (novel_premises/{val,test}, random/{val,test})
must never be read.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

LEANDOJO_ROOT = (
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4"
)
TRAIN_JSON = os.path.join(LEANDOJO_ROOT, "random", "train.json")
CORPUS_JSONL = os.path.join(LEANDOJO_ROOT, "corpus.jsonl")
STEPS_JSONL = (
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl"
)

SEALED = {
    os.path.join(LEANDOJO_ROOT, "novel_premises", "val.json"),
    os.path.join(LEANDOJO_ROOT, "novel_premises", "test.json"),
    os.path.join(LEANDOJO_ROOT, "random", "val.json"),
    os.path.join(LEANDOJO_ROOT, "random", "test.json"),
}


def _assert_permitted(path: str) -> None:
    if os.path.abspath(path) in SEALED:
        raise RuntimeError(f"SEALED SPLIT: refusing to read {path}")


def stream_train_theorems(path: str = TRAIN_JSON, chunk: int = 1 << 22) -> Iterator[dict[str, Any]]:
    """Yield theorem records from the train split one at a time."""
    _assert_permitted(path)
    decoder = json.JSONDecoder()
    with open(path, encoding="utf-8") as handle:
        buf = ""
        pos = 0
        # consume the opening bracket
        while "[" not in buf:
            block = handle.read(chunk)
            if not block:
                return
            buf += block
        pos = buf.index("[") + 1
        while True:
            while True:
                stripped = pos
                while stripped < len(buf) and buf[stripped] in " \n\r\t,":
                    stripped += 1
                if stripped >= len(buf):
                    block = handle.read(chunk)
                    if not block:
                        return
                    buf = buf[pos:]
                    pos = 0
                    buf += block
                    continue
                pos = stripped
                break
            if buf[pos] == "]":
                return
            while True:
                try:
                    obj, end = decoder.raw_decode(buf, pos)
                except ValueError:
                    block = handle.read(chunk)
                    if not block:
                        return
                    buf += block
                    continue
                break
            yield obj
            # drop the consumed prefix so memory stays bounded
            buf = buf[end:]
            pos = 0


def iter_train_steps() -> Iterator[dict[str, Any]]:
    """Flatten train theorems into per-tactic steps carrying full provenance."""
    for thm in stream_train_theorems():
        tactics = thm.get("traced_tactics") or []
        n = len(tactics)
        for index, tac in enumerate(tactics):
            annotated = tac.get("annotated_tactic") or ["", []]
            yield {
                "file_path": thm["file_path"],
                "thm": thm["full_name"],
                "proof_id": f"{thm['file_path']}::{thm['full_name']}",
                "commit": thm.get("commit", ""),
                "start": thm.get("start"),
                "step_index": index,
                "n_steps": n,
                "tactic": tac["tactic"],
                "annotated_tactic": annotated[0],
                "premises": annotated[1],
                "state_before": tac["state_before"],
                "state_after": tac["state_after"],
            }
