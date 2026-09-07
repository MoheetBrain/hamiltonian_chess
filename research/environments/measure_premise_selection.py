"""SHORTCUT AUDIT: premise selection.

Builds real k-way multiple-choice premise-selection items from the LeanDojo
held-out splits and measures how far a battery of NON-MATHEMATICAL surface
heuristics gets on them, under four different distractor-sourcing policies.

No model is called.  Every number is computed from the local trace.

Run:  python -m research.environments.measure_premise_selection
"""

from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict

from research.environments import common as C

K = 4
SEED = 20260907


def load_train_freq() -> Counter:
    path = os.path.join(C.OUT_DIR, "train_premise_citation_counts.json")
    with open(path, encoding="utf-8") as handle:
        return Counter(json.load(handle)["counts"])


def build_items(split: str) -> list[dict]:
    steps = []
    for part in ("val", "test"):
        steps.extend(C.iter_steps(iter(C.load_theorems(split, part))))
    by_theorem: dict[str, set[str]] = defaultdict(set)
    for step in steps:
        for premise in step["premises"]:
            by_theorem[step["theorem_key"]].add(premise["full_name"])
    items = []
    for step in steps:
        if len(step["premises"]) != 1:
            continue
        gold = step["premises"][0]
        items.append(
            {
                "gold": gold["full_name"],
                "gold_path": gold["def_path"],
                "state_before": step["state_before"],
                "theorem_key": step["theorem_key"],
                "sibling_premises": by_theorem[step["theorem_key"]],
            }
        )
    return items


def sample_distractors(
    policy: str,
    item: dict,
    rng: random.Random,
    corpus_names: list[str],
    by_file: dict[str, list[str]],
    freq: Counter,
    freq_bands: dict[int, list[str]],
) -> list[str] | None:
    gold = item["gold"]
    if policy == "uniform_corpus":
        pool = corpus_names
    elif policy == "same_file":
        pool = by_file.get(item["gold_path"], [])
    elif policy == "freq_matched":
        band = band_of(freq.get(gold, 0))
        pool = freq_bands.get(band, [])
    elif policy == "same_proof":
        pool = sorted(item["sibling_premises"])
    elif policy == "same_file_freq_matched":
        band = band_of(freq.get(gold, 0))
        pool = [
            name
            for name in by_file.get(item["gold_path"], [])
            if band_of(freq.get(name, 0)) == band
        ]
    elif policy == "overlap_and_freq_matched":
        # THE CONTROL: distractors must share the gold premise's lexical
        # overlap with the state AND its train-frequency band, so neither
        # heuristic can separate them.
        st = C.state_tokens(item["state_before"])
        target_overlap = len(C.name_tokens(gold) & st)
        band = band_of(freq.get(gold, 0))
        pool = [
            name
            for name in item["overlap_pool"]
            if band_of(freq.get(name, 0)) == band
            and len(C.name_tokens(name) & st) == target_overlap
        ]
    else:
        raise ValueError(policy)
    candidates = [name for name in pool if name != gold]
    if len(candidates) < K - 1:
        return None
    if len(candidates) > 4000:
        candidates = rng.sample(candidates, 4000)
    return rng.sample(candidates, K - 1)


def band_of(count: int) -> int:
    if count <= 0:
        return 0
    band = 0
    while (1 << band) <= count:
        band += 1
    return band


def score_options(options, state, goal, freq):
    st = C.state_tokens(state)
    goal_ng = C.char_ngrams(goal)
    rows = {
        "lex_overlap_jaccard": [],
        "lex_overlap_count": [],
        "last_component_substring": [],
        "train_citation_frequency": [],
        "shortest_name": [],
        "longest_name": [],
        "char3gram_vs_goal": [],
        "overlap_then_frequency": [],
    }
    for name in options:
        nt = C.name_tokens(name)
        overlap = len(nt & st)
        rows["lex_overlap_jaccard"].append(C.jaccard(nt, st))
        rows["lex_overlap_count"].append(float(overlap))
        last = name.rsplit(".", 1)[-1]
        rows["last_component_substring"].append(1.0 if last in state else 0.0)
        rows["train_citation_frequency"].append(float(freq.get(name, 0)))
        rows["shortest_name"].append(-float(len(name)))
        rows["longest_name"].append(float(len(name)))
        rows["char3gram_vs_goal"].append(C.jaccard(C.char_ngrams(name), goal_ng))
        rows["overlap_then_frequency"].append(
            overlap * 1e6 + min(freq.get(name, 0), 999_999)
        )
    return rows


def evaluate(policy, items, corpus_names, by_file, freq, freq_bands, sample_pool=None):
    rng = random.Random(SEED)
    per_heuristic: dict[str, list] = defaultdict(list)
    gold_overlap, distractor_overlap = [], []
    used = 0
    for item in items:
        item["overlap_pool"] = sample_pool or []
        distractors = sample_distractors(
            policy, item, rng, corpus_names, by_file, freq, freq_bands
        )
        if distractors is None:
            continue
        used += 1
        options = [item["gold"]] + distractors
        order = list(range(K))
        rng.shuffle(order)
        options = [options[i] for i in order]
        answer = options.index(item["gold"])
        goal = C.goal_target(item["state_before"])
        rows = score_options(options, item["state_before"], goal, freq)
        for name, scores in rows.items():
            per_heuristic[name].append((scores, answer))
        st = C.state_tokens(item["state_before"])
        gold_overlap.append(len(C.name_tokens(item["gold"]) & st))
        distractor_overlap.extend(len(C.name_tokens(d) & st) for d in distractors)
    result = {
        "policy": policy,
        "items_used": used,
        "k": K,
        "chance": 1.0 / K,
        "heuristic_accuracy": {
            name: round(C.argmax_accuracy(rows), 4)
            for name, rows in sorted(per_heuristic.items())
        },
        "mean_name_token_overlap_with_state": {
            "gold": round(sum(gold_overlap) / len(gold_overlap), 3) if gold_overlap else None,
            "distractors": round(
                sum(distractor_overlap) / len(distractor_overlap), 3
            )
            if distractor_overlap
            else None,
        },
    }
    result["best_shortcut"] = max(
        result["heuristic_accuracy"].items(), key=lambda kv: kv[1]
    )
    return result


def main() -> None:
    corpus_names, by_name, by_file = C.load_premise_corpus()
    freq = load_train_freq()
    freq_bands: dict[int, list[str]] = defaultdict(list)
    for name in set(corpus_names):
        freq_bands[band_of(freq.get(name, 0))].append(name)
    report = {
        "question": (
            "Given the proof state, which library premise does this step cite? "
            "k-way forced choice."
        ),
        "sources": {
            "steps": C.LEANDOJO_ROOT + "/{random,novel_premises}/{val,test}.json",
            "candidate_library": C.LEANDOJO_ROOT + "/corpus.jsonl",
            "frequency_prior": "random/train.json only (no split leakage)",
        },
        "corpus_declarations": len(corpus_names),
        "corpus_distinct_names": len(by_name),
        "k": K,
        "seed": SEED,
        "splits": {},
    }
    rng0 = random.Random(SEED)
    unique_names = sorted(set(corpus_names))
    sample_pool = rng0.sample(unique_names, 30000)
    report["overlap_control_pool_size"] = len(sample_pool)
    for split in ("random", "novel_premises"):
        items = build_items(split)
        report["splits"][split] = {
            "single_premise_items": len(items),
            "policies": {
                policy: evaluate(
                    policy, items, corpus_names, by_file, freq, freq_bands,
                    sample_pool,
                )
                for policy in (
                    "uniform_corpus",
                    "same_file",
                    "freq_matched",
                    "same_file_freq_matched",
                    "same_proof",
                    "overlap_and_freq_matched",
                )
            },
        }
    print(C.write_json("premise_selection_shortcuts.json", report))
    for split, block in report["splits"].items():
        print(f"\n== {split}  n_single_premise={block['single_premise_items']}")
        for policy, res in block["policies"].items():
            print(
                f"  {policy:16s} n={res['items_used']:5d} "
                f"best={res['best_shortcut'][0]}={res['best_shortcut'][1]:.4f} "
                f"| overlap gold={res['mean_name_token_overlap_with_state']['gold']} "
                f"distr={res['mean_name_token_overlap_with_state']['distractors']}"
            )
            for name, acc in res["heuristic_accuracy"].items():
                print(f"      {name:28s} {acc:.4f}")


if __name__ == "__main__":
    main()
