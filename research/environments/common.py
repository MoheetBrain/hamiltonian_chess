"""Shared read-only loaders and shortcut primitives for the future-environment audit.

READ-ONLY.  No model call, no network, no Lean, no writes outside
research/environments/.  All corpora are opened from their canonical on-disk
locations and never copied into the Arena repository.
"""

from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from typing import Any, Iterator

LEANDOJO_ROOT = (
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4"
)
HMLV3_CORPUS_GLOB = (
    "/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus/"
    "lean_runtime_v2_full.canonical.part-*.jsonl.gz"
)
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "measurements")


# --------------------------------------------------------------------------
# length / token proxies
# --------------------------------------------------------------------------
# The Arena's own proxy (arena/cli.py:381) is ceil(UTF-8 bytes / 4).  A real
# model tokenizer is NOT available offline (no `transformers` / `tokenizers`
# in the venv), so every "token" number in this audit is one of these two
# deterministic proxies and is labelled as such.
_SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?]*|\d+|[^\sA-Za-z0-9_]")


def tokens_bytes4(text: str) -> int:
    """Arena token proxy: ceil(UTF-8 bytes / 4)."""
    return math.ceil(len(text.encode("utf-8")) / 4)


def tokens_symbolic(text: str) -> int:
    """Regex symbol-token proxy (identifiers, numerals, single punctuation)."""
    return len(_SYMBOL_RE.findall(text))


# --------------------------------------------------------------------------
# LeanDojo loading
# --------------------------------------------------------------------------
def leandojo_split_path(split: str, part: str) -> str:
    return os.path.join(LEANDOJO_ROOT, split, f"{part}.json")


def load_theorems(split: str, part: str) -> list[dict[str, Any]]:
    """Load a small LeanDojo split file (val/test) fully into memory."""
    with open(leandojo_split_path(split, part), encoding="utf-8") as handle:
        return json.load(handle)


def stream_theorems(split: str, part: str) -> Iterator[dict[str, Any]]:
    """Stream a large LeanDojo split file (train) one theorem at a time.

    The file is a single-line JSON array; json.load would materialise several
    GB of Python objects.  raw_decode keeps only the text plus one record.
    """
    path = leandojo_split_path(split, part)
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    decoder = json.JSONDecoder()
    index = text.index("[") + 1
    length = len(text)
    while True:
        while index < length and text[index] in " \n\r\t,":
            index += 1
        if index >= length or text[index] == "]":
            return
        obj, index = decoder.raw_decode(text, index)
        yield obj


def iter_steps(theorems: Iterator[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Flatten theorems into steps, carrying the parent theorem identity."""
    for thm in theorems:
        tactics = thm.get("traced_tactics") or []
        for position, tac in enumerate(tactics):
            yield {
                "file_path": thm["file_path"],
                "full_name": thm["full_name"],
                "theorem_key": f"{thm['file_path']}::{thm['full_name']}",
                "step_index": position,
                "n_steps": len(tactics),
                "tactic": tac["tactic"],
                "annotated": tac["annotated_tactic"][0],
                "premises": tac["annotated_tactic"][1],
                "state_before": tac["state_before"],
                "state_after": tac["state_after"],
            }


# --------------------------------------------------------------------------
# premise corpus (corpus.jsonl)
# --------------------------------------------------------------------------
def load_premise_corpus() -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    """Return (all_names, name -> def_path, def_path -> [names])."""
    names: list[str] = []
    by_name: dict[str, str] = {}
    by_file: dict[str, list[str]] = {}
    path = os.path.join(LEANDOJO_ROOT, "corpus.jsonl")
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            file_path = record["path"]
            bucket = by_file.setdefault(file_path, [])
            for premise in record["premises"]:
                full = premise.get("full_name")
                if not full:
                    continue
                names.append(full)
                by_name.setdefault(full, file_path)
                bucket.append(full)
    return names, by_name, by_file


# --------------------------------------------------------------------------
# shortcut primitives
# --------------------------------------------------------------------------
_CAMEL_RE = re.compile(r"[A-Z]?[a-z0-9']+|[A-Z]+(?![a-z])")


def name_tokens(full_name: str) -> set[str]:
    """Decompose a mathlib name into lowercase word tokens.

    Finset.sum_Ico_eq_sub -> {finset, sum, ico, eq, sub}
    """
    out: set[str] = set()
    for chunk in re.split(r"[._]+", full_name):
        for piece in _CAMEL_RE.findall(chunk):
            if piece:
                out.add(piece.lower())
    return out


def state_tokens(state: str) -> set[str]:
    """Word tokens appearing anywhere in a pretty-printed proof state."""
    out: set[str] = set()
    for chunk in re.split(r"[^A-Za-z0-9_']+", state):
        for piece in _CAMEL_RE.findall(chunk):
            if piece:
                out.add(piece.lower())
    return out


def goal_target(state: str) -> str:
    """The text after the last turnstile: the goal the tactic must discharge."""
    if "⊢" in state:
        return state.rsplit("⊢", 1)[1].strip()
    return state.strip()


def char_ngrams(text: str, n: int = 3) -> set[str]:
    text = text.lower()
    return {text[i : i + n] for i in range(max(0, len(text) - n + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def argmax_accuracy(items: list[tuple[list[float], int]]) -> float:
    """Accuracy of picking the argmax score, ties split uniformly at random.

    Ties are credited fractionally (1/#tied) rather than being broken by
    option order, so a heuristic never profits from the option ordering.
    """
    total = 0.0
    for scores, answer in items:
        best = max(scores)
        tied = [i for i, s in enumerate(scores) if s == best]
        total += (1.0 / len(tied)) if answer in tied else 0.0
    return total / len(items) if items else float("nan")


def write_json(name: str, payload: Any) -> str:
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, ensure_ascii=False, sort_keys=False)
    return path


def summarise_counter(counter: Counter[str], top: int = 25) -> dict[str, int]:
    return dict(counter.most_common(top))
