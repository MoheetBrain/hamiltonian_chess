"""Model-free shortcut audit for the legal/illegal transformation family.

Preregistered ceiling: on a balanced binary problem (chance 0.50) no model-free predictor and no
shallow model over the combined features may exceed **0.65** on held-out data.  The headline is
the *best* shortcut, not the average one, and it is reported per corruption axis as well as
pooled, because a pooled 0.60 can hide a single axis at 0.95.

Discipline
  * every predictor is FITTED on dev-train and SCORED on dev-heldout;
  * the split is by THEOREM, so a matched (positive, negative) pair can never straddle it;
  * inputs are only what a reader sees: state_before, action, state_after.  Nothing reads the
    label, the axis, the tier or the provenance;
  * train-only data throughout.  No model call, no network, no Lean.
"""

from __future__ import annotations

import difflib
import gzip
import json
import math
import os
import re
import sys
from collections import Counter
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from arena.environments.legal_transform import (  # noqa: E402
    GENERATOR_SEED,
    AXIS_LEVEL,
    CorruptionAxis,
    DifficultyLevel,
    symbolic_tokens,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ITEMS_PATH = os.path.join(HERE, "items.jsonl.gz")
FREQUENCY_PATH = os.path.join(HERE, "train_premise_frequency.json.gz")
OUT_PATH = os.path.join(HERE, "shortcut_audit.json")

CEILING = 0.65
CHANCE = 0.50

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_ORIENTATION_RE = re.compile(r"^(?:rw|rwa|erw|simp_rw)\s*\[\s*(?P<arrow>←\s*)?(?P<lemma>[^\[\],]+?)\s*\]$")
_DOTTED_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*")
_TURNSTILE = "⊢"

FEATURE_NAMES = [
    "action_chars",
    "action_tokens",
    "before_chars",
    "after_chars",
    "before_tokens",
    "after_tokens",
    "delta_chars",
    "abs_delta_chars",
    "delta_tokens",
    "abs_delta_tokens",
    "multiset_diff_before_after",
    "multiset_diff_action_before",
    "jaccard_action_before",
    "jaccard_before_after",
    "jaccard_action_goal",
    "edit_ratio_before_after",
    "novel_identifier_count",
    "novel_identifier_fraction",
    "novel_dotted_count",
    "premise_freq_max_log",
    "premise_freq_mean_log",
    "hypothesis_lines_before",
    "arrow_in_action",
]


def orientation_key(action: str) -> tuple[str, bool] | None:
    """(lemma, is_reverse) for a single-lemma rewrite, else None.

    This backs the strongest adversary in the audit, and it is deliberately stronger than the
    brief's mandated list: a sibling audit measured a train-fitted per-lemma direction prior
    answering "forward or reverse?" at 0.79.  Adding an adversary after seeing a result can only
    make the gate harder to pass, never easier, so it is a sound addition rather than tuning.
    """

    match = _ORIENTATION_RE.match(action.strip())
    if match is None:
        return None
    return match.group("lemma").strip(), bool(match.group("arrow"))


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(text))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _multiset_distance(left: str, right: str) -> int:
    counter = Counter(symbolic_tokens(left))
    counter.subtract(Counter(symbolic_tokens(right)))
    return sum(abs(value) for value in counter.values())


def _edit_ratio(left: str, right: str, cap: int = 400) -> float:
    a = symbolic_tokens(left)[:cap]
    b = symbolic_tokens(right)[:cap]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def featurize(record: dict[str, Any], frequency: dict[str, int]) -> list[float]:
    before, action, after = record["state_before"], record["action"], record["state_after"]
    before_tokens = symbolic_tokens(before)
    after_tokens = symbolic_tokens(after)
    action_words = _words(action)
    before_words = _words(before)
    goal = before.rsplit(_TURNSTILE, 1)[1] if _TURNSTILE in before else before
    novel = action_words - before_words
    dotted = [name for name in _DOTTED_RE.findall(action) if "." in name]
    novel_dotted = [name for name in dotted if name not in before]
    freqs = [frequency.get(name, 0) for name in dotted]
    return [
        float(len(action)),
        float(len(symbolic_tokens(action))),
        float(len(before)),
        float(len(after)),
        float(len(before_tokens)),
        float(len(after_tokens)),
        float(len(after) - len(before)),
        float(abs(len(after) - len(before))),
        float(len(after_tokens) - len(before_tokens)),
        float(abs(len(after_tokens) - len(before_tokens))),
        float(_multiset_distance(before, after)),
        float(_multiset_distance(action, before)),
        _jaccard(action_words, before_words),
        _jaccard(_words(before), _words(after)),
        _jaccard(action_words, _words(goal)),
        _edit_ratio(before, after),
        float(len(novel)),
        len(novel) / len(action_words) if action_words else 0.0,
        float(len(novel_dotted)),
        math.log1p(max(freqs)) if freqs else 0.0,
        math.log1p(sum(freqs) / len(freqs)) if freqs else 0.0,
        float(sum(1 for line in before.split("\n") if " : " in line and not line[:1].isspace())),
        float("←" in action),
    ]


def best_threshold(values: np.ndarray, labels: np.ndarray) -> tuple[float, int]:
    """Fit the single split point and polarity that maximise training accuracy."""

    candidates = np.unique(values)
    if candidates.size > 256:
        candidates = np.quantile(candidates, np.linspace(0.0, 1.0, 256))
    best_score, best_cut, best_sign = -1.0, 0.0, 1
    for cut in candidates:
        predicted = values > cut
        for sign in (1, -1):
            guess = predicted if sign == 1 else ~predicted
            score = float(np.mean(guess == labels))
            if score > best_score:
                best_score, best_cut, best_sign = score, float(cut), sign
    return best_cut, best_sign


def lemma_orientation_prior(
    train_actions: list[str],
    train_y: np.ndarray,
    test_actions: list[str],
    test_y: np.ndarray,
    majority: bool,
) -> tuple[float, float]:
    """Train-fitted P(valid | lemma, orientation), with majority backoff.  Returns (accuracy, coverage)."""

    table: dict[tuple[str, bool], list[int]] = {}
    for action, label in zip(train_actions, train_y, strict=True):
        key = orientation_key(action)
        if key is not None:
            table.setdefault(key, []).append(int(label))
    correct = 0
    covered = 0
    for action, label in zip(test_actions, test_y, strict=True):
        key = orientation_key(action)
        guess = majority
        if key is not None:
            if key in table:
                covered += 1
                guess = sum(table[key]) / len(table[key]) >= 0.5
            elif (key[0], not key[1]) in table:
                covered += 1
                other = table[(key[0], not key[1])]
                guess = not (sum(other) / len(other) >= 0.5)
        correct += int(guess == bool(label))
    total = len(test_actions)
    return (correct / total if total else float("nan"), covered / total if total else 0.0)


def evaluate(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    test_y: np.ndarray,
    train_pos: np.ndarray,
    test_pos: np.ndarray,
    train_actions: list[str],
    test_actions: list[str],
) -> dict[str, float]:
    """Every model-free predictor, each fitted on dev-train and scored on dev-heldout."""

    scores: dict[str, float] = {}
    majority = bool(np.mean(train_y) >= 0.5)
    scores["constant_majority"] = float(np.mean(test_y == majority))

    parity_train = (train_pos % 2) == 0
    parity_sign = np.mean(parity_train == train_y) >= 0.5
    parity_test = (test_pos % 2) == 0
    scores["label_position_parity"] = float(
        np.mean((parity_test if parity_sign else ~parity_test) == test_y)
    )
    half_cut = float(np.median(train_pos))
    half_train = train_pos > half_cut
    half_sign = np.mean(half_train == train_y) >= 0.5
    half_test = test_pos > half_cut
    scores["label_position_half"] = float(
        np.mean((half_test if half_sign else ~half_test) == test_y)
    )

    for column, name in enumerate(FEATURE_NAMES):
        cut, sign = best_threshold(train_x[:, column], train_y)
        predicted = test_x[:, column] > cut
        if sign == -1:
            predicted = ~predicted
        scores[f"threshold:{name}"] = float(np.mean(predicted == test_y))

    logistic = make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=2000, random_state=GENERATOR_SEED)
    )
    logistic.fit(train_x, train_y)
    scores["shallow_logistic_all_features"] = float(logistic.score(test_x, test_y))

    for depth in (2, 4, 8):
        tree = DecisionTreeClassifier(max_depth=depth, random_state=GENERATOR_SEED)
        tree.fit(train_x, train_y)
        scores[f"shallow_tree_depth{depth}_all_features"] = float(tree.score(test_x, test_y))

    accuracy, coverage = lemma_orientation_prior(
        train_actions, train_y, test_actions, test_y, majority
    )
    scores["train_fitted_lemma_orientation_prior"] = accuracy
    scores["_coverage_lemma_orientation_prior"] = coverage
    return scores


def summarise(scores: dict[str, float], n_train: int, n_test: int, positive_rate: float) -> dict:
    coverage = scores.pop("_coverage_lemma_orientation_prior", float("nan"))
    best = max(scores.items(), key=lambda item: item[1])
    best_shortcut = max(
        ((k, v) for k, v in scores.items() if not k.startswith("shallow_")),
        key=lambda item: item[1],
        default=("none", float("nan")),
    )
    best_model = max(
        ((k, v) for k, v in scores.items() if k.startswith("shallow_")),
        key=lambda item: item[1],
        default=("none", float("nan")),
    )
    return {
        "n_dev_train": n_train,
        "n_dev_heldout": n_test,
        "heldout_positive_rate": round(positive_rate, 4),
        "chance": CHANCE,
        "ceiling": CEILING,
        "best_single_shortcut": [best_shortcut[0], round(best_shortcut[1], 4)],
        "best_shallow_model": [best_model[0], round(best_model[1], 4)],
        "best_overall": [best[0], round(best[1], 4)],
        "lemma_orientation_prior_coverage": round(coverage, 4),
        "breaches_ceiling": bool(best[1] > CEILING),
        "all_predictors": {k: round(v, 4) for k, v in sorted(scores.items(), key=lambda i: -i[1])},
    }


def main() -> None:
    with gzip.open(FREQUENCY_PATH, "rt", encoding="utf-8") as handle:
        frequency = json.load(handle)
    records: list[dict[str, Any]] = []
    with gzip.open(ITEMS_PATH, "rt", encoding="utf-8") as handle:
        for position, line in enumerate(handle):
            record = json.loads(line)
            record["_position"] = position
            records.append(record)
    print(f"loaded {len(records)} items", flush=True)

    features = np.array([featurize(record, frequency) for record in records], dtype=float)
    labels = np.array([bool(record["valid"]) for record in records])
    positions = np.array([record["_position"] for record in records])
    axes = [record["axis"] for record in records]
    levels = [record["level"] for record in records]
    pair_ids = [record["pair_id"] for record in records]

    keys = sorted({record["theorem_key"] for record in records})
    rng = np.random.default_rng(GENERATOR_SEED)
    order = rng.permutation(len(keys))
    cut = len(keys) // 2
    train_keys = {keys[i] for i in order[:cut]}
    is_train = np.array([record["theorem_key"] in train_keys for record in records])
    print(
        f"group split by theorem: {len(train_keys)} dev-train theorems, "
        f"{len(keys) - len(train_keys)} dev-heldout theorems",
        flush=True,
    )

    pair_axis = {pair_ids[i]: axes[i] for i in range(len(records)) if axes[i] is not None}
    item_axis = np.array([pair_axis.get(pair_ids[i], "") for i in range(len(records))])
    item_level = np.array(levels)

    def run(mask: np.ndarray, name: str) -> dict | None:
        train_mask = mask & is_train
        test_mask = mask & ~is_train
        if train_mask.sum() < 40 or test_mask.sum() < 40:
            return None
        scores = evaluate(
            features[train_mask],
            labels[train_mask],
            features[test_mask],
            labels[test_mask],
            positions[train_mask],
            positions[test_mask],
            [records[i]["action"] for i in np.flatnonzero(train_mask)],
            [records[i]["action"] for i in np.flatnonzero(test_mask)],
        )
        summary = summarise(
            scores,
            int(train_mask.sum()),
            int(test_mask.sum()),
            float(np.mean(labels[test_mask])),
        )
        print(
            f"  {name:<34} n={int(test_mask.sum()):>5}  best={summary['best_overall'][1]:.4f}"
            f" ({summary['best_overall'][0]})"
            f"{'  BREACH' if summary['breaches_ceiling'] else ''}",
            flush=True,
        )
        return summary

    graded_levels = {
        DifficultyLevel.L1_COARSE.value,
        DifficultyLevel.L2_MODERATE.value,
        DifficultyLevel.L3_SUBTLE.value,
    }
    report: dict[str, Any] = {
        "preregistered_ceiling": CEILING,
        "chance": CHANCE,
        "protocol": (
            "predictors fitted on dev-train and scored on dev-heldout; split by theorem so a "
            "matched pair cannot straddle it; train-only source data; no model call"
        ),
        "feature_names": FEATURE_NAMES,
        "n_items": len(records),
        "pooled": {},
        "per_level": {},
        "per_axis": {},
    }
    print("pooled:")
    report["pooled"]["all_levels"] = run(np.ones(len(records), dtype=bool), "all_levels")
    graded_mask = np.array([level in graded_levels for level in levels])
    report["pooled"]["graded_L1_L3"] = run(graded_mask, "graded_L1_L3 (headline)")

    print("per level:")
    for level in DifficultyLevel:
        summary = run(item_level == level.value, level.value)
        if summary is not None:
            report["per_level"][level.value] = summary

    print("per axis:")
    for axis in CorruptionAxis:
        summary = run(item_axis == axis.value, axis.value)
        if summary is not None:
            summary["level"] = AXIS_LEVEL[axis].value
            report["per_axis"][axis.value] = summary

    breaching = sorted(
        axis
        for axis, summary in report["per_axis"].items()
        if summary["breaches_ceiling"]
        and AXIS_LEVEL[CorruptionAxis(axis)] is not DifficultyLevel.L0_EXPLICIT_CONTROL
    )
    report["graded_axes_breaching_ceiling"] = breaching
    report["verdict"] = (
        "FAMILY_REJECTED_SHORTCUT"
        if breaching or (report["pooled"]["graded_L1_L3"] or {}).get("breaches_ceiling")
        else "FAMILY_READY"
    )
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(f"\nverdict: {report['verdict']}  breaching graded axes: {breaching or 'none'}")


if __name__ == "__main__":
    main()
