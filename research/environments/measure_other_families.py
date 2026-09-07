"""SHORTCUT AUDITS for the remaining candidate families.

  F2  legal-vs-illegal / successor-state discrimination (real distractors)
  F4  progress: does this step close the goal?
  F5  premise attribution ("was this premise cited?") and the sufficiency defect
  F6  subgoal selection
  F7  quantifier instantiation (`use` witnesses)
  N5  declaration-name <-> statement alignment (a NEW candidate, tested for
      degeneracy before it is proposed)

All numbers come from the local LeanDojo trace.  No model call, no Lean.

Run:  python -m research.environments.measure_other_families
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict

from research.environments import common as C
from research.environments.build_train_priors import CHUNK, OVERLAP, TACTIC_RE

SEED = 20260907
K = 4


def head_of(tactic: str) -> str:
    match = re.match(r"[A-Za-z_][A-Za-z0-9_'!?]*", tactic.strip())
    return match.group(0) if match else "?"


def load_heldout() -> list[dict]:
    steps = []
    for part in ("val", "test"):
        steps.extend(C.iter_steps(iter(C.load_theorems("random", part))))
    return steps


# --------------------------------------------------------------------------
# F4: does this step close the goal?
# --------------------------------------------------------------------------
def train_head_close_prior() -> dict[str, Counter]:
    """P(closes | tactic head) fitted on TRAIN, using state_after == 'no goals'.

    The train file is streamed; tactic and the following state_after are read
    as an adjacent pair in LeanDojo's fixed serialisation order.
    """
    prior: dict[str, Counter] = defaultdict(Counter)
    pair = re.compile(
        rb'"tactic": "((?:[^"\\]|\\.)*)", "annotated_tactic".*?'
        rb'"state_after": "((?:[^"\\]|\\.)*)"',
        re.S,
    )
    path = C.leandojo_split_path("random", "train")
    tail = b""
    with open(path, "rb") as handle:
        while True:
            block = handle.read(CHUNK)
            last = not block
            buf = tail + block
            consumed = len(buf) if last else max(0, len(buf) - OVERLAP)
            for match in pair.finditer(buf):
                if match.start() >= consumed:
                    break
                tactic = json.loads(b'"' + match.group(1) + b'"')
                after = json.loads(b'"' + match.group(2) + b'"')
                prior[head_of(tactic)][after.strip() == "no goals"] += 1
            if last:
                break
            tail = buf[consumed:]
    return prior


def audit_progress(steps, prior) -> dict:
    n = len(steps)
    positives = sum(1 for s in steps if s["state_after"].strip() == "no goals")
    majority = max(positives, n - positives) / n

    head_hits = covered = 0
    for step in steps:
        counts = prior.get(head_of(step["tactic"]))
        label = step["state_after"].strip() == "no goals"
        if not counts:
            continue
        covered += 1
        guess = counts[True] > counts[False]
        head_hits += 1 if guess == label else 0

    def threshold_rule(feature) -> tuple[float, float]:
        values = sorted({feature(s) for s in steps})
        if len(values) > 400:
            step_size = max(1, len(values) // 400)
            values = values[::step_size]
        best_acc, best_t = 0.0, 0.0
        for threshold in values:
            for sign in (1, -1):
                hits = sum(
                    1
                    for s in steps
                    if ((feature(s) > threshold) == (sign > 0))
                    == (s["state_after"].strip() == "no goals")
                )
                if hits / n > best_acc:
                    best_acc, best_t = hits / n, float(threshold)
        return round(best_acc, 4), best_t

    return {
        "question": "Given the state (and the tactic), will this step close the goal?",
        "items": n,
        "positive_rate": round(positives / n, 4),
        "majority_class_baseline": round(majority, 4),
        "shortcuts_with_tactic_shown": {
            "train_fitted_tactic_head_prior": {
                "coverage": round(covered / n, 4),
                "accuracy": round(head_hits / covered, 4) if covered else None,
            }
        },
        "shortcuts_with_tactic_hidden": {
            "best_fitted_threshold_on_state_symbolic_tokens": threshold_rule(
                lambda s: C.tokens_symbolic(s["state_before"])
            ),
            "best_fitted_threshold_on_state_bytes4_proxy": threshold_rule(
                lambda s: C.tokens_bytes4(s["state_before"])
            ),
            "best_fitted_threshold_on_hypothesis_count": threshold_rule(
                lambda s: s["state_before"].count("\n")
            ),
            "best_fitted_threshold_on_goal_symbolic_tokens": threshold_rule(
                lambda s: C.tokens_symbolic(C.goal_target(s["state_before"]))
            ),
        },
        "note": (
            "The threshold rules are FITTED ON THE EVALUATION DATA ITSELF, so "
            "they are optimistic ceilings, not held-out accuracies."
        ),
    }


# --------------------------------------------------------------------------
# F2: pick the real successor state
# --------------------------------------------------------------------------
def audit_successor(steps) -> dict:
    rng = random.Random(SEED)
    by_theorem: dict[str, list[str]] = defaultdict(list)
    for step in steps:
        by_theorem[step["theorem_key"]].append(step["state_after"])
    all_afters = [s["state_after"] for s in steps]

    results = {}
    for policy in ("same_theorem", "length_matched_other_theorem"):
        rows_overlap, rows_len, used = [], [], 0
        for step in steps:
            gold = step["state_after"]
            if gold.strip() == "no goals":
                continue
            if policy == "same_theorem":
                pool = [
                    a
                    for a in by_theorem[step["theorem_key"]]
                    if a != gold and a.strip() != "no goals"
                ]
            else:
                target = C.tokens_symbolic(gold)
                pool = [
                    a
                    for a in rng.sample(all_afters, 600)
                    if a != gold
                    and a.strip() != "no goals"
                    and abs(C.tokens_symbolic(a) - target) <= max(3, target // 20)
                ]
            if len(pool) < K - 1:
                continue
            used += 1
            options = [gold] + rng.sample(pool, K - 1)
            order = list(range(K))
            rng.shuffle(order)
            options = [options[i] for i in order]
            answer = options.index(gold)
            before_tokens = C.state_tokens(step["state_before"])
            before_len = C.tokens_symbolic(step["state_before"])
            rows_overlap.append(
                (
                    [C.jaccard(C.state_tokens(o), before_tokens) for o in options],
                    answer,
                )
            )
            rows_len.append(
                ([-abs(C.tokens_symbolic(o) - before_len) for o in options], answer)
            )
        results[policy] = {
            "items_used": used,
            "chance": 1.0 / K,
            "token_jaccard_with_before_state": round(C.argmax_accuracy(rows_overlap), 4),
            "closest_length_to_before_state": round(C.argmax_accuracy(rows_len), 4),
        }
    return {
        "question": (
            "Given the before-state, which of k candidate after-states is the "
            "real successor?  (Real distractors only; nothing invented.)"
        ),
        "k": K,
        "policies": results,
    }


# --------------------------------------------------------------------------
# F5: is the premise name already visible in the state?
# --------------------------------------------------------------------------
def audit_premise_visibility(steps, by_file) -> dict:
    rng = random.Random(SEED)
    cited_visible = cited_total = 0
    uncited_visible = uncited_total = 0
    multi = 0
    for step in steps:
        premises = step["premises"]
        if len(premises) >= 2:
            multi += 1
        for premise in premises:
            last = premise["full_name"].rsplit(".", 1)[-1]
            cited_total += 1
            cited_visible += 1 if last in step["state_before"] else 0
            pool = by_file.get(premise["def_path"], [])
            if pool:
                other = rng.choice(pool)
                other_last = other.rsplit(".", 1)[-1]
                uncited_total += 1
                uncited_visible += 1 if other_last in step["state_before"] else 0
    return {
        "question": "Was this premise cited by this step?  /  Is this premise set sufficient?",
        "steps_citing_ge2_premises": multi,
        "cited_premise_name_visible_in_state": round(cited_visible / cited_total, 4),
        "same_file_random_premise_name_visible_in_state": round(
            uncited_visible / uncited_total, 4
        ),
        "single_feature_discrimination_accuracy": round(
            0.5 * (cited_visible / cited_total)
            + 0.5 * (1 - uncited_visible / uncited_total),
            4,
        ),
        "ground_truth_defect": (
            "LeanDojo annotates only premises named in the tactic SYNTAX; simp "
            "sets, typeclass instances and definitional unfolding are invisible. "
            "'Sufficient' is therefore unsound without Lean; only 'was cited' is "
            "a fact."
        ),
    }


# --------------------------------------------------------------------------
# F6 / F7
# --------------------------------------------------------------------------
def audit_subgoal_and_witness(steps) -> dict:
    multi = [s for s in steps if s["state_before"].count("⊢") > 1]
    use_steps = [s for s in steps if head_of(s["tactic"]) == "use"]
    witnesses = Counter()
    for step in use_steps:
        body = step["tactic"].strip()[3:].strip()
        witnesses[body.split(",")[0].strip()[:24]] += 1
    top = witnesses.most_common(1)[0] if witnesses else ("", 0)
    return {
        "subgoal_selection": {
            "question": "Which open goal should be attacked next?",
            "multi_goal_states_in_heldout": len(multi),
            "share_of_steps": round(len(multi) / len(steps), 5),
            "why_it_collapses": (
                "LeanDojo reports the FOCUSED goal, and Lean's own focusing "
                "convention makes 'the first goal' correct almost always, so the "
                "answer is a convention rather than a mathematical judgement."
            ),
        },
        "quantifier_instantiation": {
            "question": "Which term witnesses the existential?",
            "use_steps_in_heldout": len(use_steps),
            "distinct_witnesses": len(witnesses),
            "most_common_witness": {"value": top[0], "count": top[1]},
            "constant_answer_baseline": round(top[1] / len(use_steps), 4)
            if use_steps
            else None,
            "top_witnesses": C.summarise_counter(witnesses, 12),
        },
    }


# --------------------------------------------------------------------------
# N5: declaration name <-> statement alignment
# --------------------------------------------------------------------------
def audit_name_statement_alignment() -> dict:
    rng = random.Random(SEED)
    records = []
    path = C.LEANDOJO_ROOT + "/corpus.jsonl"
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if not record["path"].startswith("Mathlib/"):
                continue
            names = [
                (p["full_name"], p["code"])
                for p in record["premises"]
                if p.get("full_name") and p.get("code")
            ]
            if len(names) >= K:
                records.append(names)
    rng.shuffle(records)
    records = records[:1500]
    rows_overlap, rows_len, used = [], [], 0
    for names in records:
        gold_name, gold_code = rng.choice(names)
        pool = [n for n, _ in names if n != gold_name]
        if len(pool) < K - 1:
            continue
        used += 1
        options = [gold_name] + rng.sample(pool, K - 1)
        order = list(range(K))
        rng.shuffle(order)
        options = [options[i] for i in order]
        answer = options.index(gold_name)
        # redact the declaration's own name from its source before scoring
        body = gold_code.replace(gold_name, "_").replace(
            gold_name.rsplit(".", 1)[-1], "_"
        )
        body_tokens = C.state_tokens(body)
        rows_overlap.append(
            ([len(C.name_tokens(o) & body_tokens) for o in options], answer)
        )
        rows_len.append(([-len(o) for o in options], answer))
    return {
        "question": (
            "Given a mathlib declaration's statement (its own name redacted), "
            "which of k candidate names is its real name?  Distractors are other "
            "real declarations from the same file."
        ),
        "k": K,
        "items_used": used,
        "chance": 1.0 / K,
        "name_token_overlap_with_statement": round(C.argmax_accuracy(rows_overlap), 4),
        "shortest_name": round(C.argmax_accuracy(rows_len), 4),
    }


def main() -> None:
    steps = load_heldout()
    _, _, by_file = C.load_premise_corpus()
    prior = train_head_close_prior()
    report = {
        "source": C.LEANDOJO_ROOT,
        "population": "random/val + random/test = 8,766 steps unless stated",
        "seed": SEED,
        "F4_progress_close_goal": audit_progress(steps, prior),
        "F4b_progress_balanced_tactic_hidden": audit_progress_balanced(steps),
        "F2_successor_state_discrimination": audit_successor(steps),
        "F5_premise_attribution": audit_premise_visibility(steps, by_file),
        "F6_F7_subgoal_and_witness": audit_subgoal_and_witness(steps),
        "N5_name_statement_alignment": audit_name_statement_alignment(),
    }
    print(C.write_json("other_families_shortcuts.json", report))
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()


# --------------------------------------------------------------------------
# F4b: the CLASS-BALANCED, tactic-hidden variant (the one actually proposed)
# --------------------------------------------------------------------------
def audit_progress_balanced(steps) -> dict:
    """Balance to 50/50 so chance is exactly 0.5 and the destroyed-twin control
    sits at the same constant, then re-measure every length shortcut."""
    rng = random.Random(SEED)
    positives = [s for s in steps if s["state_after"].strip() == "no goals"]
    negatives = [s for s in steps if s["state_after"].strip() != "no goals"]
    size = min(len(positives), len(negatives))
    pool = rng.sample(positives, size) + rng.sample(negatives, size)
    rng.shuffle(pool)
    n = len(pool)

    def threshold_rule(feature):
        values = sorted({feature(s) for s in pool})
        if len(values) > 400:
            values = values[:: max(1, len(values) // 400)]
        best_acc, best_t = 0.0, 0.0
        for threshold in values:
            for sign in (1, -1):
                hits = sum(
                    1
                    for s in pool
                    if ((feature(s) > threshold) == (sign > 0))
                    == (s["state_after"].strip() == "no goals")
                )
                if hits / n > best_acc:
                    best_acc, best_t = hits / n, float(threshold)
        return round(best_acc, 4), best_t

    return {
        "question": (
            "Tactic HIDDEN.  Given only the proof state, is it closable by the "
            "author's very next step?"
        ),
        "items": n,
        "chance": 0.5,
        "best_fitted_threshold_state_symbolic_tokens": threshold_rule(
            lambda s: C.tokens_symbolic(s["state_before"])
        ),
        "best_fitted_threshold_state_bytes4_proxy": threshold_rule(
            lambda s: C.tokens_bytes4(s["state_before"])
        ),
        "best_fitted_threshold_state_chars": threshold_rule(
            lambda s: len(s["state_before"])
        ),
        "best_fitted_threshold_hypothesis_count": threshold_rule(
            lambda s: s["state_before"].count("\n")
        ),
        "best_fitted_threshold_goal_symbolic_tokens": threshold_rule(
            lambda s: C.tokens_symbolic(C.goal_target(s["state_before"]))
        ),
        "best_fitted_threshold_goal_nesting_depth": threshold_rule(
            lambda s: max(
                0,
                max(
                    (
                        C.goal_target(s["state_before"])[: i + 1].count("(")
                        - C.goal_target(s["state_before"])[: i + 1].count(")")
                    )
                    for i in range(len(C.goal_target(s["state_before"])) or 1)
                )
                if C.goal_target(s["state_before"])
                else 0,
            )
        ),
        "label_defect": (
            "The label is 'the author's next step closed the goal', which is a "
            "LOWER BOUND on one-step closability: a state the author took two "
            "steps on may still have been closable in one.  Negatives are "
            "therefore noisy; positives are sound."
        ),
    }
