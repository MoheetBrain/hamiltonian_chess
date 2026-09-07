"""Deep shortcut audit of the ONE configuration that survived the first pass:
premise selection with same-proof (hard) distractors.

Adds the shortcuts that are specific to same-proof distractors -- within-proof
citation frequency, step adjacency, definition locality and definition line --
and measures how many items survive the Fitness-V5-style length-fairness
discipline, in tokens rather than characters.

Run:  python -m research.environments.measure_same_proof_deep
"""

from __future__ import annotations

import json
import os
import random
import statistics
from collections import Counter, defaultdict

from research.environments import common as C

SEED = 20260907
K = 4

# A heuristic only threatens the instrument if the SOLVER can compute it from
# what the prompt actually contains: the proof state and the k candidate names.
# (train_citation_frequency counts as observable: a pretrained model carries a
# familiarity prior over mathlib names in its weights.)  Everything else is a
# construction diagnostic -- it cannot be exploited, but a large value means
# the distractor pool is not exchangeable with the gold and some OBSERVABLE
# correlate of it may exist.
OBSERVABLE = {
    "lex_overlap_count",
    "lex_overlap_jaccard",
    "char3gram_vs_goal",
    "char3gram_vs_full_state",
    "last_component_substring",
    "shortest_name",
    "train_citation_frequency",
}


def base_of(key: str) -> str:
    return key[4:] if key.startswith("NEG_") else key


def load_train_freq() -> Counter:
    path = os.path.join(C.OUT_DIR, "train_premise_citation_counts.json")
    with open(path, encoding="utf-8") as handle:
        return Counter(json.load(handle)["counts"])


def build(split: str):
    steps = []
    for part in ("val", "test"):
        steps.extend(C.iter_steps(iter(C.load_theorems(split, part))))
    proof_premises: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for step in steps:
        for premise in step["premises"]:
            proof_premises[step["theorem_key"]].append((step["step_index"], premise))
    return steps, proof_premises


def main() -> None:
    freq = load_train_freq()
    report = {
        "configuration": (
            "premise selection, k=4, distractors = premises cited at OTHER steps "
            "of the SAME theorem (real, all genuinely relevant to this proof)"
        ),
        "seed": SEED,
        "splits": {},
    }
    for split, policy in (
        ("random", "same_proof"),
        ("random", "same_proof_multiplicity_matched"),
        ("novel_premises", "same_proof"),
        ("novel_premises", "same_proof_multiplicity_matched"),
    ):
        steps, proof_premises = build(split)
        rng = random.Random(SEED)
        heuristics: dict[str, list] = defaultdict(list)
        lengths_before, lengths_gold = [], []
        used = 0
        answer_positions = Counter()
        for step in steps:
            if len(step["premises"]) != 1:
                continue
            gold = step["premises"][0]
            gold_name = gold["full_name"]
            siblings = proof_premises[step["theorem_key"]]
            # IMPORTANT: every per-option feature must be computed WITHOUT the
            # citation made by the step under test, otherwise the gold premise
            # is trivially separable and the audit measures its own bug.
            others = [(i, p) for i, p in siblings if i != step["step_index"]]
            within = Counter(p["full_name"] for _, p in others)
            meta = {p["full_name"]: p for _, p in siblings}
            nearest_step = {}
            for index, premise in others:
                delta = abs(index - step["step_index"])
                name = premise["full_name"]
                if name not in nearest_step or delta < nearest_step[name]:
                    nearest_step[name] = delta
            total = Counter(p["full_name"] for _, p in siblings)
            if policy == "same_proof":
                pool = [name for name in within if name != gold_name]
            else:  # same_proof_multiplicity_matched
                # The plain same-proof pool is NOT exchangeable with the gold:
                # every distractor is cited at some OTHER step by construction,
                # while the gold need not be, so within-proof multiplicity
                # separates them.  Matching total within-proof multiplicity
                # removes that asymmetry.
                pool = [
                    name
                    for name in total
                    if name != gold_name and total[name] == total[gold_name]
                ]
            if len(pool) < K - 1:
                continue
            used += 1
            options = [gold_name] + rng.sample(pool, K - 1)
            order = list(range(K))
            rng.shuffle(order)
            options = [options[i] for i in order]
            answer = options.index(gold_name)
            answer_positions[answer] += 1
            state = step["state_before"]
            st = C.state_tokens(state)
            goal_ng = C.char_ngrams(C.goal_target(state))
            feats = {
                "lex_overlap_count": [],
                "lex_overlap_jaccard": [],
                "char3gram_vs_goal": [],
                "char3gram_vs_full_state": [],
                "train_citation_frequency": [],
                "within_proof_citation_count_excl_this_step": [],
                "cited_at_adjacent_other_step": [],
                "defined_in_theorem_own_file": [],
                "earlier_definition_line": [],
                "shortest_name": [],
                "last_component_substring": [],
            }
            state_ng = C.char_ngrams(state)
            for name in options:
                nt = C.name_tokens(name)
                info = meta[name]
                feats["lex_overlap_count"].append(float(len(nt & st)))
                feats["lex_overlap_jaccard"].append(C.jaccard(nt, st))
                feats["char3gram_vs_goal"].append(C.jaccard(C.char_ngrams(name), goal_ng))
                feats["char3gram_vs_full_state"].append(
                    C.jaccard(C.char_ngrams(name), state_ng)
                )
                feats["train_citation_frequency"].append(float(freq.get(name, 0)))
                feats["within_proof_citation_count_excl_this_step"].append(
                    float(within[name])
                )
                feats["cited_at_adjacent_other_step"].append(
                    1.0 if nearest_step.get(name, 99) <= 1 else 0.0
                )
                feats["defined_in_theorem_own_file"].append(
                    1.0 if info["def_path"] == step["file_path"] else 0.0
                )
                feats["earlier_definition_line"].append(-float(info["def_pos"][0]))
                feats["shortest_name"].append(-float(len(name)))
                feats["last_component_substring"].append(
                    1.0 if name.rsplit(".", 1)[-1] in state else 0.0
                )
            for key, scores in feats.items():
                heuristics[key].append((scores, answer))
            lengths_before.append(
                (
                    len(state),
                    C.tokens_bytes4(state),
                    C.tokens_symbolic(state),
                )
            )
            lengths_gold.append(len(gold_name))

        # Every feature is scored in BOTH polarities: a heuristic that is
        # anti-correlated with the answer is still a heuristic (pick the
        # argmin instead of the argmax), and reporting only argmax would hide
        # it.  This is how within_proof_citation_count at 0.108 was caught.
        accuracy = {}
        for key, rows in sorted(heuristics.items()):
            up = C.argmax_accuracy(rows)
            down = C.argmax_accuracy([([-x for x in sc], a) for sc, a in rows])
            accuracy[key] = round(up, 4)
            accuracy["NEG_" + key] = round(down, 4)
        chars = sorted(l[0] for l in lengths_before)
        bytes4 = sorted(l[1] for l in lengths_before)
        symtok = sorted(l[2] for l in lengths_before)

        def pct(values, q):
            return values[min(len(values) - 1, int(q * len(values)))]

        # Fitness-V5-style length fairness: keep the items whose state length in
        # the Arena token proxy lies inside a narrow band, so length cannot be
        # a cue and the surfaces are comparable across representations.
        median = statistics.median(bytes4)
        for band in (0.25, 0.5, 1.0):
            low, high = median * (1 - band), median * (1 + band)
            survivors = sum(1 for _, b, _ in lengths_before if low <= b <= high)
            accuracy[f"__length_fair_survivors_band_{band}"] = survivors

        report["splits"][f"{split}/{policy}"] = {
            "policy": policy,
            "items_used": used,
            "k": K,
            "chance": 1.0 / K,
            "answer_position_distribution": dict(sorted(answer_positions.items())),
            "largest_answer_share": round(
                max(answer_positions.values()) / used, 4
            ),
            "solver_observable_heuristics": {
                k: v
                for k, v in accuracy.items()
                if not k.startswith("__") and base_of(k) in OBSERVABLE
            },
            "construction_diagnostics_not_in_the_prompt": {
                k: v
                for k, v in accuracy.items()
                if not k.startswith("__") and base_of(k) not in OBSERVABLE
            },
            "best_solver_observable_shortcut": max(
                (
                    (k, v)
                    for k, v in accuracy.items()
                    if not k.startswith("__") and base_of(k) in OBSERVABLE
                ),
                key=lambda kv: kv[1],
            ),
            "worst_construction_imbalance": max(
                (
                    (k, v)
                    for k, v in accuracy.items()
                    if not k.startswith("__") and base_of(k) not in OBSERVABLE
                ),
                key=lambda kv: kv[1],
            ),
            "state_before_length": {
                "chars": {"p10": pct(chars, 0.1), "p50": pct(chars, 0.5), "p90": pct(chars, 0.9), "max": chars[-1]},
                "arena_bytes4_token_proxy": {
                    "p10": pct(bytes4, 0.1), "p50": pct(bytes4, 0.5),
                    "p90": pct(bytes4, 0.9), "max": bytes4[-1],
                },
                "symbolic_tokens": {
                    "p10": pct(symtok, 0.1), "p50": pct(symtok, 0.5),
                    "p90": pct(symtok, 0.9), "max": symtok[-1],
                },
                "over_30000_chars": sum(1 for c in chars if c > 30000),
            },
            "length_fair_survivors": {
                "band_+-25pct_of_median_tokens": accuracy["__length_fair_survivors_band_0.25"],
                "band_+-50pct": accuracy["__length_fair_survivors_band_0.5"],
                "band_+-100pct": accuracy["__length_fair_survivors_band_1.0"],
            },
        }
    print(C.write_json("same_proof_deep_audit.json", report))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
