"""Preregistered shortcut gate for the rewrite-direction family.

Ceiling, fixed before any number was produced: **no model-free shortcut and no combined
shallow model may exceed 0.65 held-out accuracy on a balanced binary (chance = 0.50).**
Breaching it means the family is solvable without reading the mathematics, and the family is
reported as FAMILY_AT_RISK with the responsible feature.

Protocol.  Items come from `random/train.json` only.  They are split **by source file** so a
predictor cannot memorise a file it was fitted on, then each side is balanced independently
by downsampling the majority direction, so held-out chance is exactly 0.50.  Every predictor
is fitted on dev-train and scored once on dev-held-out.

The explicit-positive L0 control arm is excluded: it states the deciding relation outright,
so it is trivially solvable by construction and would flatter every predictor.

Run:  python -m research.env_rewrite.shortcut_gate
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from arena.environments import rewrite_direction as rw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "measurements")
SCRATCH = os.environ.get(
    "RWDIR_SCRATCH",
    "/private/tmp/claude-501/-Users-moheet-Documents-ChatGPT-hamiltonian-chess--claude-"
    "worktrees-phase-6-parallel-setup-9c6068/c625765c-0962-49c6-b99b-560f570581b8/scratchpad",
)
ITEMS_JSONL = os.path.join(SCRATCH, "rewrite_direction_items.jsonl")

SEED = 20260907
CEILING = 0.65
HOLDOUT_FRACTION = 0.30

#: Numeric features offered to the combined shallow models.  Every one is computable without
#: understanding the mathematics; that is the point.
NUMERIC_FEATURES = (
    "side_similarity",
    "lhs_signature_hits",
    "rhs_signature_hits",
    "decisive_side_margin",
    "target_depth",
    "plausible_sites",
    "context_equations",
    "length_ratio",
    "lhs_len",
    "rhs_len",
    "state_len",
    "goal_len",
    "option0_is_forward",
    "lhs_token_overlap",
    "rhs_token_overlap",
    "overlap_margin",
)


def load_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with open(ITEMS_JSONL, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["explicit_positive"]:
                continue  # L0 control arm: solvable by construction, excluded from the gate
            items.append(record)
    return items


def enrich(record: dict[str, Any]) -> dict[str, Any]:
    """Add the derived lexical features the gate probes."""

    features = dict(record["features"])
    goal = rw.goal_target(record["state"])
    goal_tokens = rw.word_tokens(goal)
    lhs_tokens = rw.word_tokens(record["side_a"])
    rhs_tokens = rw.word_tokens(record["side_b"])
    features["lhs_len"] = len(record["side_a"])
    features["rhs_len"] = len(record["side_b"])
    features["state_len"] = len(record["state"])
    features["goal_len"] = len(goal)
    features["option0_is_forward"] = 1.0 if record["options"][0] == rw.FORWARD else 0.0
    features["lhs_token_overlap"] = rw.jaccard(lhs_tokens, goal_tokens)
    features["rhs_token_overlap"] = rw.jaccard(rhs_tokens, goal_tokens)
    features["overlap_margin"] = features["lhs_token_overlap"] - features["rhs_token_overlap"]
    record["x"] = features
    record["y"] = 1 if record["direction"] == rw.REVERSE else 0
    return record


def split_by_file(items: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    files = sorted({item["provenance"]["file_path"] for item in items})
    rng = random.Random(f"split|{SEED}")
    rng.shuffle(files)
    cut = int(len(files) * (1.0 - HOLDOUT_FRACTION))
    train_files = set(files[:cut])
    train = [i for i in items if i["provenance"]["file_path"] in train_files]
    held = [i for i in items if i["provenance"]["file_path"] not in train_files]
    return train, held


def balance(items: list[dict[str, Any]], tag: str) -> list[dict[str, Any]]:
    positive = [i for i in items if i["y"] == 1]
    negative = [i for i in items if i["y"] == 0]
    keep = min(len(positive), len(negative))
    rng = random.Random(f"balance|{tag}|{SEED}")
    rng.shuffle(positive)
    rng.shuffle(negative)
    merged = positive[:keep] + negative[:keep]
    merged.sort(key=lambda i: i["item_id"])
    return merged


def balance_within_lemma(items: list[dict[str, Any]], tag: str) -> list[dict[str, Any]]:
    """CONTROL v1.1: every lemma contributes equally many forward and reverse items.

    Mirrors :func:`arena.environments.rewrite_direction.balance_within_lemma` over the cached
    dicts.  Applied independently to each side of the file split, so the guarantee holds
    exactly on the held-out set the gate scores.
    """

    by_lemma: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for item in items:
        by_lemma.setdefault(item["premise_name"], {0: [], 1: []})[item["y"]].append(item)
    rng = random.Random(f"within-lemma|{tag}|{SEED}")
    kept: list[dict[str, Any]] = []
    for name in sorted(by_lemma):
        bucket = by_lemma[name]
        take = min(len(bucket[0]), len(bucket[1]))
        if take == 0:
            continue
        for label in (0, 1):
            group = sorted(bucket[label], key=lambda i: i["item_id"])
            rng.shuffle(group)
            kept.extend(group[:take])
    kept.sort(key=lambda i: i["item_id"])
    return kept


CONTROLS = {
    "none": balance,
    "within_lemma": balance_within_lemma,
}


def matrix(items: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([[float(i["x"][name]) for name in NUMERIC_FEATURES] for i in items])
    y = np.array([i["y"] for i in items])
    return x, y


# ---------------------------------------------------------------------------
# single-feature predictors, each fitted on dev-train and scored once held-out
# ---------------------------------------------------------------------------
def best_threshold_rule(
    train: list[dict], held: list[dict], feature: str
) -> tuple[float, dict[str, Any]]:
    """Fit the single best (threshold, polarity) on dev-train; score it held-out."""

    values = sorted({item["x"][feature] for item in train})
    if len(values) > 400:  # keep the sweep bounded on continuous features
        step = len(values) / 400.0
        values = [values[int(k * step)] for k in range(400)]
    train_y = np.array([i["y"] for i in train])
    train_v = np.array([float(i["x"][feature]) for i in train])
    best = (-1.0, 0.0, 1)
    for threshold in values:
        predicted = (train_v > threshold).astype(int)
        for polarity in (1, 0):
            guess = predicted if polarity else 1 - predicted
            accuracy = float((guess == train_y).mean())
            if accuracy > best[0]:
                best = (accuracy, float(threshold), polarity)
    _, threshold, polarity = best
    held_y = np.array([i["y"] for i in held])
    held_v = np.array([float(i["x"][feature]) for i in held])
    predicted = (held_v > threshold).astype(int)
    guess = predicted if polarity else 1 - predicted
    return float((guess == held_y).mean()), {
        "fitted_threshold": threshold,
        "polarity": polarity,
        "dev_train_accuracy": round(best[0], 4),
    }


def which_side_rule(train: list[dict], held: list[dict]) -> tuple[float, dict[str, Any]]:
    """The obvious near-solution: whichever side's vocabulary actually shows up in the goal.

    Polarity is fitted on dev-train rather than assumed, and ties (margin 0) fall back to the
    dev-train majority class.  This is NOT a cheat feature - it is close to the real
    mathematical content of the question - so it is reported plainly whatever it scores.
    """

    train_y = np.array([i["y"] for i in train])
    majority = int(round(float(train_y.mean())))

    def apply(items: list[dict], polarity: int) -> np.ndarray:
        out = []
        for item in items:
            margin = item["x"]["decisive_side_margin"]
            if margin == 0:
                out.append(majority)
            elif margin > 0:
                out.append(0 if polarity else 1)
            else:
                out.append(1 if polarity else 0)
        return np.array(out)

    scores = {p: float((apply(train, p) == train_y).mean()) for p in (1, 0)}
    polarity = max(scores, key=lambda p: scores[p])
    held_y = np.array([i["y"] for i in held])
    accuracy = float((apply(held, polarity) == held_y).mean())
    decided = sum(1 for i in held if i["x"]["decisive_side_margin"] != 0)
    return accuracy, {
        "polarity": polarity,
        "dev_train_accuracy": round(scores[polarity], 4),
        "held_out_items_with_nonzero_margin": decided,
        "held_out_coverage": round(decided / len(held), 4) if held else None,
        "accuracy_on_decided_subset": round(
            float(
                (
                    apply([i for i in held if i["x"]["decisive_side_margin"] != 0], polarity)
                    == np.array(
                        [i["y"] for i in held if i["x"]["decisive_side_margin"] != 0]
                    )
                ).mean()
            ),
            4,
        )
        if decided
        else None,
    }


def lemma_prior_rule(train: list[dict], held: list[dict]) -> tuple[float, dict[str, Any]]:
    """Pure name recall: per-lemma majority direction from dev-train, majority backoff."""

    counts: dict[str, Counter] = defaultdict(Counter)
    for item in train:
        counts[item["premise_name"]][item["y"]] += 1
    train_y = np.array([i["y"] for i in train])
    majority = int(round(float(train_y.mean())))
    hits = 0.0
    covered = 0
    covered_hits = 0.0
    for item in held:
        bucket = counts.get(item["premise_name"])
        if not bucket:
            hits += 1.0 if majority == item["y"] else 0.0
            continue
        covered += 1
        if bucket[0] == bucket[1]:
            hits += 0.5
            covered_hits += 0.5
        else:
            guess = 1 if bucket[1] > bucket[0] else 0
            scored = 1.0 if guess == item["y"] else 0.0
            hits += scored
            covered_hits += scored
    return hits / len(held), {
        "lemmas_with_dev_train_evidence": len(counts),
        "held_out_coverage": round(covered / len(held), 4) if held else None,
        "accuracy_on_covered": round(covered_hits / covered, 4) if covered else None,
    }


def affix_rule(train: list[dict], held: list[dict]) -> tuple[float, dict[str, Any]]:
    """A depth-limited tree over lemma-name affix indicators only."""

    def encode(items: list[dict]) -> np.ndarray:
        return np.array(
            [
                [1.0 if cue in item["premise_name"].lower() else 0.0 for cue in rw.NAME_AFFIX_CUES]
                for item in items
            ]
        )

    model = DecisionTreeClassifier(max_depth=4, random_state=SEED)
    model.fit(encode(train), [i["y"] for i in train])
    accuracy = float(model.score(encode(held), [i["y"] for i in held]))
    return accuracy, {"cues": list(rw.NAME_AFFIX_CUES), "max_depth": 4}


def name_ngram_rule(train: list[dict], held: list[dict]) -> tuple[float, dict[str, Any]]:
    """The strongest name-only shortcut we can build: char n-gram logistic on the name."""

    pipeline = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2),
        LogisticRegression(max_iter=2000, C=1.0),
    )
    pipeline.fit([i["premise_name"] for i in train], [i["y"] for i in train])
    accuracy = float(pipeline.score([i["premise_name"] for i in held], [i["y"] for i in held]))
    return accuracy, {"vectoriser": "char_wb 2-5grams", "model": "logistic"}


def combined_models(train: list[dict], held: list[dict]) -> dict[str, dict[str, Any]]:
    x_train, y_train = matrix(train)
    x_held, y_held = matrix(held)
    out: dict[str, dict[str, Any]] = {}
    models = {
        "combined_shallow_logistic": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=5000)
        ),
        "combined_shallow_tree_depth4": DecisionTreeClassifier(max_depth=4, random_state=SEED),
        "combined_gradient_boosted_depth3": GradientBoostingClassifier(
            max_depth=3, n_estimators=200, random_state=SEED
        ),
    }
    for name, model in models.items():
        model.fit(x_train, y_train)
        out[name] = {
            "accuracy": round(float(model.score(x_held, y_held)), 4),
            "dev_train_accuracy": round(float(model.score(x_train, y_train)), 4),
        }
    tree = models["combined_gradient_boosted_depth3"]
    importances = getattr(tree, "feature_importances_", None)
    if importances is not None:
        out["combined_gradient_boosted_depth3"]["top_features"] = [
            [NUMERIC_FEATURES[k], round(float(importances[k]), 4)]
            for k in np.argsort(importances)[::-1][:6]
        ]
    return out


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    control = sys.argv[1] if len(sys.argv) > 1 else "none"
    if control not in CONTROLS:
        raise SystemExit(f"unknown control {control!r}; choose from {sorted(CONTROLS)}")
    balancer = CONTROLS[control]

    raw = [enrich(item) for item in load_items()]
    dev_train_raw, dev_held_raw = split_by_file(raw)
    dev_train = balancer(dev_train_raw, "train")
    dev_held = balancer(dev_held_raw, "held")
    if not dev_train or not dev_held:
        raise SystemExit("empty split; nothing to measure")

    results: dict[str, dict[str, Any]] = {}

    train_y = np.array([i["y"] for i in dev_train])
    held_y = np.array([i["y"] for i in dev_held])
    majority = int(round(float(train_y.mean())))
    results["constant_majority_class"] = {
        "accuracy": round(float((np.full_like(held_y, majority) == held_y).mean()), 4)
    }

    position_guess = np.array(
        [0 if i["options"][0] == rw.FORWARD else 1 for i in dev_train]
    )
    polarity = 1 if float((position_guess == train_y).mean()) >= 0.5 else 0
    held_position = np.array([0 if i["options"][0] == rw.FORWARD else 1 for i in dev_held])
    guess = held_position if polarity else 1 - held_position
    results["option_position"] = {"accuracy": round(float((guess == held_y).mean()), 4)}

    accuracy, detail = lemma_prior_rule(dev_train, dev_held)
    results["lemma_name_frequency_prior"] = {"accuracy": round(accuracy, 4), **detail}

    accuracy, detail = affix_rule(dev_train, dev_held)
    results["lemma_name_affixes"] = {"accuracy": round(accuracy, 4), **detail}

    accuracy, detail = name_ngram_rule(dev_train, dev_held)
    results["lemma_name_char_ngram_logistic"] = {"accuracy": round(accuracy, 4), **detail}

    accuracy, detail = which_side_rule(dev_train, dev_held)
    results["which_side_appears_in_goal"] = {"accuracy": round(accuracy, 4), **detail}

    for feature, label in (
        ("overlap_margin", "lexical_overlap_margin"),
        ("lhs_token_overlap", "lexical_overlap_side_a"),
        ("rhs_token_overlap", "lexical_overlap_side_b"),
        ("length_ratio", "expression_length_ratio"),
        ("plausible_sites", "number_of_plausible_sites"),
        ("lhs_signature_hits", "side_a_occurrence_count"),
        ("rhs_signature_hits", "side_b_occurrence_count"),
        ("side_similarity", "side_similarity"),
        ("state_len", "state_length"),
        ("target_depth", "target_nesting_depth"),
    ):
        accuracy, detail = best_threshold_rule(dev_train, dev_held, feature)
        results[label] = {"accuracy": round(accuracy, 4), "feature": feature, **detail}

    results.update(combined_models(dev_train, dev_held))

    ranked = sorted(
        ((name, float(value["accuracy"])) for name, value in results.items()),
        key=lambda kv: -kv[1],
    )
    best_name, best_accuracy = ranked[0]
    breached = best_accuracy > CEILING

    report = {
        "protocol": {
            "source": "LeanDojo random/train.json only (sealed pools never read)",
            "split": "by source file, 70/30",
            "control": control,
            "balancing": (
                "majority direction downsampled independently on each side"
                if control == "none"
                else "every lemma contributes equally many forward and reverse items, "
                "applied independently on each side of the file split"
            ),
            "chance": 0.5,
            "preregistered_ceiling": CEILING,
            "seed": SEED,
            "l0_explicit_positive_arm": "excluded from the gate (solvable by construction)",
        },
        "sizes": {
            "items_available": len(raw),
            "dev_train_before_balance": len(dev_train_raw),
            "dev_held_before_balance": len(dev_held_raw),
            "dev_train_balanced": len(dev_train),
            "dev_held_balanced": len(dev_held),
            "dev_held_reverse_rate": round(float(held_y.mean()), 4),
            "distinct_lemmas_dev_held": len({i["premise_name"] for i in dev_held}),
        },
        "shortcuts": results,
        "ranked": [[name, round(value, 4)] for name, value in ranked],
        "best_shortcut": [best_name, round(best_accuracy, 4)],
        "ceiling": CEILING,
        "verdict": "FAMILY_AT_RISK" if breached else "FAMILY_READY",
    }
    suffix = "" if control == "none" else f"_{control}"
    path = os.path.join(OUT_DIR, f"shortcut_gate{suffix}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=1, ensure_ascii=False)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    print(path, file=sys.stderr)


if __name__ == "__main__":
    main()
