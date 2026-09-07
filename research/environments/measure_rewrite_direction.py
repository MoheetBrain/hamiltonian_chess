"""SHORTCUT AUDIT: rewrite direction (forward vs reverse `rw`).

Item: (state_before, state_after, lemma identity) -> was the lemma applied
left-to-right or right-to-left?  The tactic text is never shown, because the
arrow IS the answer.

Measured shortcuts:
  * class prior (majority answer)
  * state size change, in three length units (chars, Arena bytes/4 proxy,
    symbolic tokens) -- a reverse rewrite typically grows the goal
  * per-lemma direction prior fitted on TRAIN and applied to val+test
    (pure name recall, no mathematics)
  * lemma-name morphology cues

Run:  python -m research.environments.measure_rewrite_direction
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from research.environments import common as C
from research.environments.build_train_priors import CHUNK, OVERLAP, TACTIC_RE

RW_HEAD_RE = re.compile(r"^(rw|rewrite)\b")
STRIP_ANCHOR_RE = re.compile(r"<a>|</a>")


def split_top_level(body: str) -> list[str]:
    """Split `a, b, c` on commas that are not nested in brackets/parens."""
    parts, depth, current = [], 0, []
    for char in body:
        if char in "([{⟨":
            depth += 1
        elif char in ")]}⟩":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]


def parse_single_rw(tactic: str):
    """Return (lemma_surface, is_reverse) for a single-lemma rw, else None."""
    text = tactic.strip()
    if not RW_HEAD_RE.match(text):
        return None
    if "[" not in text or "]" not in text:
        return None
    body = text[text.index("[") + 1 : text.rindex("]")]
    # a trailing `at h` location changes the semantics of the item; keep only
    # goal rewrites so the before/after diff is the goal diff.
    after_bracket = text[text.rindex("]") + 1 :].strip()
    if after_bracket:
        return None
    parts = split_top_level(body)
    if len(parts) != 1:
        return None
    lemma = parts[0].strip()
    reverse = lemma.startswith("←") or lemma.startswith("<-")
    lemma = lemma.lstrip("←").lstrip("<-").strip()
    lemma = STRIP_ANCHOR_RE.sub("", lemma)
    head = lemma.split()[0] if lemma.split() else lemma
    return head, reverse


def train_direction_prior() -> dict[str, Counter]:
    """Per-lemma forward/reverse counts, from the TRAIN split only."""
    prior: dict[str, Counter] = defaultdict(Counter)
    path = C.leandojo_split_path("random", "train")
    tail = b""
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            last = not block
            buf = tail + block
            consumed = len(buf) if last else max(0, len(buf) - OVERLAP)
            for match in TACTIC_RE.finditer(buf):
                if match.start() >= consumed:
                    break
                text = json.loads(b'"' + match.group(1) + b'"')
                parsed = parse_single_rw(text)
                if parsed is None:
                    continue
                lemma, reverse = parsed
                prior[lemma]["reverse" if reverse else "forward"] += 1
            if last:
                break
            tail = buf[consumed:]
    return prior


NAME_CUES = ("_symm", "_comm", "_eq_", "_def", "_iff", "_succ", "_assoc")


def main() -> None:
    prior = train_direction_prior()
    items = []
    for part in ("val", "test"):
        for step in C.iter_steps(iter(C.load_theorems("random", part))):
            parsed = parse_single_rw(step["tactic"])
            if parsed is None:
                continue
            lemma, reverse = parsed
            before, after = step["state_before"], step["state_after"]
            items.append(
                {
                    "lemma": lemma,
                    "reverse": reverse,
                    "d_chars": len(after) - len(before),
                    "d_bytes4": C.tokens_bytes4(after) - C.tokens_bytes4(before),
                    "d_symtok": C.tokens_symbolic(after) - C.tokens_symbolic(before),
                    "d_goal_symtok": (
                        C.tokens_symbolic(C.goal_target(after))
                        - C.tokens_symbolic(C.goal_target(before))
                    ),
                    "closes": after.strip() == "no goals",
                }
            )
    n = len(items)
    n_rev = sum(1 for i in items if i["reverse"])
    majority = max(n_rev, n - n_rev) / n

    def rule_acc(key: str, predict_reverse_when_positive: bool) -> float:
        hits = 0
        for item in items:
            delta = item[key]
            if delta == 0:
                hits += 0.5
                continue
            grew = delta > 0
            guess = grew if predict_reverse_when_positive else (not grew)
            hits += 1 if guess == item["reverse"] else 0
        return hits / n

    def best_threshold(key: str) -> tuple[float, float]:
        """Best single threshold, FITTED ON THE SAME DATA (optimistic ceiling)."""
        values = sorted({item[key] for item in items})
        best_acc, best_t = 0.0, 0.0
        for threshold in values:
            for sign in (1, -1):
                hits = sum(
                    1
                    for item in items
                    if ((item[key] > threshold) == (sign > 0)) == item["reverse"]
                )
                if hits / n > best_acc:
                    best_acc, best_t = hits / n, float(threshold)
        return best_acc, best_t

    # per-lemma prior from train, applied to val+test
    covered = hits = 0
    for item in items:
        counts = prior.get(item["lemma"])
        if not counts:
            continue
        covered += 1
        guess_reverse = counts["reverse"] > counts["forward"]
        if counts["reverse"] == counts["forward"]:
            hits += 0.5
        elif guess_reverse == item["reverse"]:
            hits += 1
    name_prior_on_covered = hits / covered if covered else float("nan")
    # back off to the majority class on uncovered items
    name_prior_full = (
        hits + (n - covered) * (majority if n_rev < n / 2 else majority)
    ) / n

    cue_hits = 0
    for item in items:
        cue = any(c in item["lemma"] for c in NAME_CUES)
        cue_hits += 1 if cue == item["reverse"] else 0

    report = {
        "question": (
            "Given before-state, after-state and the lemma identity (tactic text "
            "hidden), was the rewrite applied forward or in reverse?"
        ),
        "population": "random/val+test, `rw [L]` with exactly one lemma and no `at` clause",
        "items": n,
        "reverse": n_rev,
        "reverse_rate": round(n_rev / n, 4),
        "majority_class_baseline": round(majority, 4),
        "train_lemmas_with_direction_evidence": len(prior),
        "shortcuts": {
            "state_grew_chars": round(rule_acc("d_chars", True), 4),
            "state_shrank_chars": round(rule_acc("d_chars", False), 4),
            "state_grew_bytes4_proxy": round(rule_acc("d_bytes4", True), 4),
            "state_grew_symbolic_tokens": round(rule_acc("d_symtok", True), 4),
            "goal_grew_symbolic_tokens": round(rule_acc("d_goal_symtok", True), 4),
            "best_fitted_threshold_symtok": [
                round(best_threshold("d_symtok")[0], 4),
                best_threshold("d_symtok")[1],
            ],
            "best_fitted_threshold_chars": [
                round(best_threshold("d_chars")[0], 4),
                best_threshold("d_chars")[1],
            ],
            "lemma_name_morphology_cue": round(cue_hits / n, 4),
            "train_fitted_per_lemma_direction_prior": {
                "coverage": round(covered / n, 4),
                "accuracy_on_covered": round(name_prior_on_covered, 4),
                "accuracy_with_majority_backoff": round(name_prior_full, 4),
            },
        },
    }
    report["best_shortcut"] = max(
        [
            ("majority_class", report["majority_class_baseline"]),
            ("state_grew_symbolic_tokens", report["shortcuts"]["state_grew_symbolic_tokens"]),
            ("state_shrank_chars", report["shortcuts"]["state_shrank_chars"]),
            ("best_fitted_threshold_symtok", report["shortcuts"]["best_fitted_threshold_symtok"][0]),
            (
                "train_fitted_per_lemma_direction_prior",
                report["shortcuts"]["train_fitted_per_lemma_direction_prior"][
                    "accuracy_with_majority_backoff"
                ],
            ),
        ],
        key=lambda kv: kv[1],
    )
    print(C.write_json("rewrite_direction_shortcuts.json", report))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
