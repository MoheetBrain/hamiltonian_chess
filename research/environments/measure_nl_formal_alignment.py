"""SHORTCUT AUDIT: natural-language <-> formal statement alignment.

ProofNetVerif (PAug/ProofNetVerif, 3,752 items) is NOT present on this machine
and cannot be fetched (no network).  ProofNet itself IS local, at
HML_V3/external/checkouts/proofnet-lean4/data/proofnet.jsonl, with 371
(informal English, formal Lean) pairs.

That lets the FAMILY be shortcut-audited even though the specific dataset
cannot: if English<->Lean alignment is solvable by lexical overlap on genuine
matched pairs, it will also be partly solvable on ProofNetVerif, whose
negatives are near-miss formalisations of the SAME English statement and are
therefore lexically even closer.

Two constructions are measured:
  A. k-way: pick the Lean statement that matches this English statement, with
     distractors drawn (i) at random and (ii) from the same source text.
  B. binary near-miss: the hardest available lexical distractor, which is the
     closest structural analogue of a ProofNetVerif negative.

Run:  python -m research.environments.measure_nl_formal_alignment
"""

from __future__ import annotations

import json
import random
import re

from research.environments import common as C

PROOFNET = (
    "/Users/moheet/Documents/ChatGPT/HML_V3/external/checkouts/"
    "proofnet-lean4/data/proofnet.jsonl"
)
SEED = 20260907
K = 4


def redact(row: dict) -> str:
    """Remove the exercise name so it cannot be matched to the English text."""
    text = row["formal_statement"]
    return text.replace(row["name"], "thm")


def source_of(row: dict) -> str:
    """The local ProofNet variant carries no book field; every name is
    `exercise_...`.  The nearest available proxy for "same source text" is the
    file header, whose `open` lines differ per textbook, combined with the
    leading chapter number of the exercise id."""
    chapter = re.match(r"exercise_(\d+)", row["name"])
    return f"{hash(row['header']) & 0xffff}:{chapter.group(1) if chapter else '?'}"


def main() -> None:
    rows = [json.loads(line) for line in open(PROOFNET, encoding="utf-8")]
    rng = random.Random(SEED)
    for row in rows:
        row["nl"] = re.sub(r"^/--\s*|\s*-/\s*$", "", row["informal_prefix"].strip())
        row["lean"] = redact(row)
        row["lean_tokens"] = C.state_tokens(row["lean"])
        row["nl_tokens"] = C.state_tokens(row["nl"])
        row["source"] = source_of(row)

    report = {
        "source": PROOFNET,
        "note": (
            "PROXY MEASUREMENT.  PAug/ProofNetVerif is not on this machine and "
            "no network call was made; these numbers characterise the FAMILY "
            "using the local ProofNet pairs, not that dataset."
        ),
        "items": len(rows),
        "splits": {r["split"]: sum(1 for x in rows if x["split"] == r["split"]) for r in rows},
        "sources": len({r["source"] for r in rows}),
    }

    # ---- A. k-way alignment -------------------------------------------
    kway = {}
    for policy in ("random_distractors", "same_source_distractors"):
        rows_overlap, rows_len, used = [], [], 0
        rng = random.Random(SEED)
        for row in rows:
            if policy == "random_distractors":
                pool = [r for r in rows if r is not row]
            else:
                pool = [
                    r for r in rows if r is not row and r["source"] == row["source"]
                ]
            if len(pool) < K - 1:
                continue
            used += 1
            options = [row] + rng.sample(pool, K - 1)
            order = list(range(K))
            rng.shuffle(order)
            options = [options[i] for i in order]
            answer = options.index(row)
            rows_overlap.append(
                (
                    [C.jaccard(o["lean_tokens"], row["nl_tokens"]) for o in options],
                    answer,
                )
            )
            target = C.tokens_symbolic(row["nl"])
            rows_len.append(
                (
                    [-abs(C.tokens_symbolic(o["lean"]) - target) for o in options],
                    answer,
                )
            )
        kway[policy] = {
            "items_used": used,
            "chance": 1.0 / K,
            "nl_lean_token_jaccard": round(C.argmax_accuracy(rows_overlap), 4),
            "closest_length_to_english": round(C.argmax_accuracy(rows_len), 4),
        }
    report["A_kway_alignment"] = {"k": K, "policies": kway}

    # ---- B. binary near-miss ------------------------------------------
    # For each English statement, the negative is the Lean statement (from a
    # different problem) with the HIGHEST lexical similarity to it -- the
    # hardest possible surface distractor drawn from real data.
    correct = 0
    margins = []
    for row in rows:
        best, best_score = None, -1.0
        for other in rows:
            if other is row:
                continue
            score = C.jaccard(other["lean_tokens"], row["nl_tokens"])
            if score > best_score:
                best, best_score = other, score
        gold_score = C.jaccard(row["lean_tokens"], row["nl_tokens"])
        margins.append(gold_score - best_score)
        if gold_score > best_score:
            correct += 1
        elif gold_score == best_score:
            correct += 0.5
    margins.sort()
    report["B_binary_hardest_lexical_negative"] = {
        "items": len(rows),
        "chance": 0.5,
        "lexical_overlap_accuracy": round(correct / len(rows), 4),
        "gold_minus_hardest_negative_jaccard": {
            "p10": round(margins[int(0.1 * len(margins))], 4),
            "p50": round(margins[int(0.5 * len(margins))], 4),
            "p90": round(margins[int(0.9 * len(margins))], 4),
        },
        "interpretation": (
            "This is the ceiling for a purely lexical solver when the negative "
            "is the most confusable REAL Lean statement available.  A "
            "ProofNetVerif negative is a near-miss formalisation of the SAME "
            "English statement, so its lexical overlap is higher still and this "
            "number is an OVER-estimate of how far lexical overlap gets there."
        ),
    }
    print(C.write_json("nl_formal_alignment_shortcuts.json", report))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
