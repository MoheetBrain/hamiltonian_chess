"""Preregistered shortcut gate for the premise-selection family.

Fits model-free predictors on a development-train slice and evaluates them on a held-out
development slice.  Both slices come from LeanDojo ``random/train.json`` only; the split between
them is by ``proof_id`` hash, so no proof contributes to both.

Preregistered ceiling: on a K=6 item set (chance = 1/6 = 0.167), no single shortcut and no
combined shallow model may exceed **0.45** accuracy.  The headline number is the best shortcut.

Every predictor scores each option and picks the argmax; ties break on the lowest option index,
which is the least favourable convention for the predictor.

Usage:
    python -m research.env_premise.shortcut_gate --items <dir> --level L2_standard
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

FEATURE_NAMES = [
    "position",
    "name_length",
    "name_goal_jaccard",
    "name_goal_multiset_overlap",
    "log_global_frequency",
    "same_file",
    "same_module",
    "declaration_order",
]

#: shortcut label -> feature index it is allowed to see.
SINGLE_FEATURE_SHORTCUTS = {
    "option_position": "position",
    "option_string_length": "name_length",
    "lexical_overlap_name_vs_goal": "name_goal_jaccard",
    "token_multiset_overlap": "name_goal_multiset_overlap",
    "premise_global_frequency_prior": "log_global_frequency",
    "same_file_indicator": "same_file",
    "same_module_indicator": "same_module",
    "declaration_order": "declaration_order",
}

HOLDOUT_FRACTION = 0.30
CEILING = 0.45


def dev_bucket(proof_id: str) -> float:
    digest = hashlib.blake2b(proof_id.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") / float(1 << 64)


def load(items_dir: Path, level: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    with (items_dir / "gate_features.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["level"] != level:
                continue
            (holdout if dev_bucket(record["proof_id"]) < HOLDOUT_FRACTION else train).append(record)
    return train, holdout


def tensor(records: list[dict[str, Any]], k: int) -> tuple[np.ndarray, np.ndarray]:
    """Return features shaped ``(n_items, k, n_features)`` and the gold index per item."""
    features = np.asarray([record["opts"] for record in records], dtype=np.float64)
    answers = np.asarray([record["answer_index"] for record in records], dtype=np.int64)
    if features.shape[1] != k:
        raise ValueError(f"expected k={k}, got option count {features.shape[1]}")
    return features, answers


def argmax_accuracy(scores: np.ndarray, answers: np.ndarray) -> float:
    """Accuracy of picking, per item, the highest-scoring option (ties -> lowest option index)."""
    return float(np.mean(np.argmax(scores, axis=1) == answers))


def run_level(items_dir: Path, level: str) -> dict[str, Any]:
    train, holdout = load(items_dir, level)
    if not train or not holdout:
        raise SystemExit(f"no items for level {level!r}")
    k_values = sorted({record["k"] for record in train} | {record["k"] for record in holdout})
    if len(k_values) != 1:
        raise SystemExit(f"level {level!r} mixes option counts {k_values}")
    k = k_values[0]
    f_tr, ans_tr = tensor(train, k)
    f_ho, ans_ho = tensor(holdout, k)
    n_features = f_tr.shape[2]
    x_tr = f_tr.reshape(-1, n_features)
    x_ho = f_ho.reshape(-1, n_features)
    gold_tr = np.zeros((len(train), k), dtype=np.int64)
    gold_tr[np.arange(len(train)), ans_tr] = 1
    gold_tr = gold_tr.reshape(-1)

    results: dict[str, dict[str, float]] = {}

    # 1. constant / majority: always answer the index most often correct on dev-train.
    counts = np.bincount(ans_tr, minlength=k)
    majority = int(np.argmax(counts))
    results["constant_majority_index"] = {
        "dev_train": float(np.mean(ans_tr == majority)),
        "dev_holdout": float(np.mean(ans_ho == majority)),
        "chosen_index": float(majority),
    }

    # 2-9. single-feature shortcuts.  The sign (prefer high or prefer low) is fitted on dev-train.
    for label, feature in SINGLE_FEATURE_SHORTCUTS.items():
        column = FEATURE_NAMES.index(feature)
        best_sign, best_train = 1.0, -1.0
        for sign in (1.0, -1.0):
            acc = argmax_accuracy(sign * f_tr[:, :, column], ans_tr)
            if acc > best_train:
                best_sign, best_train = sign, acc
        results[label] = {
            "dev_train": best_train,
            "dev_holdout": argmax_accuracy(best_sign * f_ho[:, :, column], ans_ho),
            "sign": best_sign,
        }

    # 10. shallow combined models over every feature at once.
    logistic = LogisticRegression(max_iter=2000, C=1.0)
    logistic.fit(x_tr, gold_tr)
    results["combined_logistic_regression"] = {
        "dev_train": argmax_accuracy(logistic.decision_function(x_tr).reshape(-1, k), ans_tr),
        "dev_holdout": argmax_accuracy(logistic.decision_function(x_ho).reshape(-1, k), ans_ho),
    }
    tree = DecisionTreeClassifier(max_depth=6, random_state=0)
    tree.fit(x_tr, gold_tr)
    results["combined_decision_tree_depth6"] = {
        "dev_train": argmax_accuracy(tree.predict_proba(x_tr)[:, 1].reshape(-1, k), ans_tr),
        "dev_holdout": argmax_accuracy(tree.predict_proba(x_ho)[:, 1].reshape(-1, k), ans_ho),
    }

    best_label = max(results, key=lambda key: results[key]["dev_holdout"])
    best = results[best_label]["dev_holdout"]
    chance = 1.0 / k
    return {
        "level": level,
        "k_values": k_values,
        "chance": round(chance, 6),
        "n_dev_train_items": len(train),
        "n_dev_holdout_items": len(holdout),
        "ceiling": CEILING,
        "shortcuts": {
            key: {name: round(value, 6) for name, value in payload.items()}
            for key, payload in results.items()
        },
        "best_shortcut": best_label,
        "best_shortcut_accuracy": round(best, 6),
        "ceiling_breached": bool(best > CEILING),
        "feature_importances_logistic": dict(
            zip(FEATURE_NAMES, [round(float(c), 6) for c in logistic.coef_[0]], strict=True)
        ),
        "feature_importances_tree": dict(
            zip(FEATURE_NAMES, [round(float(v), 6) for v in tree.feature_importances_], strict=True)
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", required=True)
    parser.add_argument("--levels", default="L0_explicit_positive,L1_cross_module,L2_standard,L3_same_module_freq_matched,L4_high_similarity")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    items_dir = Path(args.items)
    report = {level: run_level(items_dir, level) for level in args.levels.split(",")}
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
