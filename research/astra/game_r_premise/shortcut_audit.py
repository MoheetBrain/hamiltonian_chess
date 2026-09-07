"""Deterministic, model-free shortcut audit of an Astra DEVELOPMENT bank.

Nothing here opens a source split or fits on the evaluation labels. Every learned
counter, lookup, and MDL choice is fitted on theorem-group-disjoint development
training. Private controls are explicitly segregated from attacks using frozen P.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Sequence

SPLIT_SEED = "astra-shortcut-theorem-split-v1"
IDENT = re.compile(r"[^\W\d]\w*'?", re.UNICODE)
TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else str((value or {}).get("text", ""))


def _dict(item: Any) -> dict:
    if isinstance(item, dict):
        return item
    if is_dataclass(item):
        return asdict(item)
    return item.to_dict()


def group_id(item: dict) -> str:
    provenance = item["provenance"]
    return str(provenance.get("proof_id") or provenance["theorem_id"])


def development_split(items: Sequence[dict]) -> tuple[list[dict], list[dict]]:
    """Rank unique theorem groups by seeded SHA256; reserve ceil(30%) groups."""
    declared = [i.get("audit_metadata", {}).get("dev_partition") for i in items]
    if any(d is not None for d in declared):
        if any(d not in {"train", "heldout"} for d in declared):
            raise ValueError("Incomplete or invalid declared DEVELOPMENT partitions")
        train = [i for i, d in zip(items, declared) if d == "train"]
        evaluation = [i for i, d in zip(items, declared) if d == "heldout"]
        if not train or not evaluation:
            raise ValueError("Both declared DEVELOPMENT partitions must be nonempty")
        if {group_id(i) for i in train} & {group_id(i) for i in evaluation}:
            raise ValueError("Theorem group crosses declared DEVELOPMENT partitions")
        return train, evaluation
    groups = sorted({group_id(i) for i in items}, key=lambda g: hashlib.sha256(
        f"{SPLIT_SEED}|{g}".encode()).hexdigest())
    if len(groups) < 2:
        raise ValueError("Shortcut audit requires at least two independent theorem groups")
    heldout = set(groups[: min(len(groups)-1, math.ceil(.3 * len(groups)))])
    return ([i for i in items if group_id(i) not in heldout],
            [i for i in items if group_id(i) in heldout])


def _answer(item: dict) -> int:
    return next(n for n, c in enumerate(item["candidate_premises"])
                if c["premise_id"] == item["target_choice_id"])


def _words(text: str) -> list[str]:
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).replace("_", " ")
    return [s.lower() for s in IDENT.findall(text)]


def _tokens(text: str) -> list[str]:
    return TOKEN.findall(text)


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    x, y = set(a), set(b)
    return len(x & y) / len(x | y) if x | y else 0.


def _skeleton(text: str) -> tuple[str, ...]:
    """Surface anti-unification proxy, not a Lean parser: preserve repeated names."""
    mapping: dict[str, str] = {}
    return tuple(mapping.setdefault(t, f"v{len(mapping)}") if IDENT.fullmatch(t)
                 else t for t in _tokens(text))


def _goal_key(item: dict, skeleton: bool = False) -> str:
    goal = _text(item["goal"])
    return json.dumps(_skeleton(goal)) if skeleton else " ".join(goal.split())


def _path(candidate: dict) -> str:
    p = candidate.get("provenance", {})
    return str(p.get("source_path") or p.get("def_path") or p.get("path") or "")


def _module(candidate: dict) -> str:
    path = _path(candidate)
    return path.rsplit("/", 1)[0] if "/" in path else path


def _source_file(item: dict) -> str:
    p = item["provenance"]
    return str(p.get("file_path") or p.get("source_path") or "")


def _order(candidate: dict) -> int | None:
    p = candidate.get("provenance", {})
    value = p.get("declaration_order", p.get("source_order", p.get("order")))
    return value if isinstance(value, int) else None


def _pick(scores: Sequence[float]) -> int:
    # All ties use the first frozen option. Tie fraction is reported, not hidden.
    return max(range(len(scores)), key=lambda n: scores[n])


class ShortcutSuite:
    """Fit a deliberately small family without consulting evaluation examples."""
    def __init__(self, train: Sequence[dict]):
        self.name_frequency: Counter[str] = Counter()
        self.module_frequency: Counter[str] = Counter()
        self.proof_frequency: dict[str, Counter] = defaultdict(Counter)
        self.metadata_lookup: dict[str, Counter] = defaultdict(Counter)
        self.exact_lookup: dict[str, Counter] = defaultdict(Counter)
        self.skeleton_lookup: dict[str, Counter] = defaultdict(Counter)
        self.label_frequency: Counter[int] = Counter()
        for item in train:
            answer = _answer(item)
            gold = item["candidate_premises"][answer]
            name = gold["name"]
            self.name_frequency[name] += 1
            self.module_frequency[_module(gold)] += 1
            self.proof_frequency[group_id(item)][name] += 1
            self.metadata_lookup[_source_file(item)][name] += 1
            self.exact_lookup[_goal_key(item)][name] += 1
            self.skeleton_lookup[_goal_key(item, True)][name] += 1
            self.label_frequency[answer] += 1
        self.majority_label = max(self.label_frequency, key=lambda k: (
            self.label_frequency[k], -k))
        # Two-part description length: log2(number of rules) + encoded mistakes.
        # Correct/mistake positions cost log2 binomial(N, mistakes); incorrect
        # alternatives cost mistakes*log2(K-1). Same fixed codebook for each rule.
        rules = sorted(self.visible_scores(train[0]))
        self.mdl_costs = {}
        for rule in rules:
            errors = sum(_pick(self.visible_scores(i)[rule]) != _answer(i) for i in train)
            n = len(train)
            location_bits = (math.lgamma(n+1)-math.lgamma(errors+1)-math.lgamma(n-errors+1))/math.log(2)
            alternative_bits = sum(math.log2(max(1,len(i["candidate_premises"])-1))
                                   for i in train if _pick(self.visible_scores(i)[rule]) != _answer(i))
            self.mdl_costs[rule] = math.log2(len(rules)) + math.log2(n+1) + location_bits + alternative_bits
        self.mdl_rule = min(rules, key=lambda r: (self.mdl_costs[r], r))

    def visible_scores(self, item: dict) -> dict[str, list[float]]:
        candidates = item["candidate_premises"]
        k = len(candidates)
        goal, context = _text(item["goal"]), _text(item["context"])
        whole = context + "\n" + goal
        names = [c["name"] for c in candidates]
        statements = [_text(c["statement"]) for c in candidates]
        scores: dict[str, list[float]] = {
            **{f"constant_label_{n}": [float(j == n) for j in range(k)] for n in range(k)},
            "first_premise": [float(n == 0) for n in range(k)],
            "last_premise": [float(n == k-1) for n in range(k)],
            "train_majority_label": [float(n == self.majority_label) for n in range(k)],
            "premise_name_frequency_train": [self.name_frequency[n] for n in names],
            "lexical_name_goal_overlap": [_jaccard(_words(goal), _words(n)) for n in names],
            "lexical_statement_goal_overlap": [_jaccard(_words(goal), _words(s)) for s in statements],
            "token_overlap": [_jaccard(_tokens(goal), _tokens(s)) for s in statements],
            "identifier_overlap": [_jaccard(IDENT.findall(whole), IDENT.findall(s)) for s in statements],
            "shortest_premise": [-len(s) for s in statements],
            "longest_premise": [len(s) for s in statements],
            "shortest_name": [-len(n) for n in names],
            "longest_name": [len(n) for n in names],
            "lexicographic_name_order": [-sorted(names).index(n) for n in names],
            "exact_goal_lookup_train": [self.exact_lookup.get(_goal_key(item), {}).get(n,0) for n in names],
            "anti_unification_lookup_train": [self.skeleton_lookup.get(_goal_key(item,True),{}).get(n,0) for n in names],
            "anti_unification_overlap": [_jaccard(_skeleton(goal), _skeleton(s)) for s in statements],
            "field_copy_goal_in_statement": [float(bool(goal.strip()) and " ".join(goal.split()) in " ".join(s.split())) for s in statements],
        }
        mentions = []
        for name in names:
            hits = [m.start() for n in {name, name.rsplit(".",1)[-1]} for m in re.finditer(
                rf"(?<![\w.]){re.escape(n)}(?![\w'])", whole)]
            mentions.append(-min(hits) if hits else -len(whole)-1)
        scores["first_mentioned_premise"] = mentions
        return scores

    def private_scores(self, item: dict) -> dict[str, list[float] | None]:
        candidates = item["candidate_premises"]
        names = [c["name"] for c in candidates]
        orders = [_order(c) for c in candidates]
        source = _source_file(item)
        thm = str(item["provenance"].get("theorem_id", ""))
        proof_counts = self.proof_frequency.get(group_id(item))
        return {
            "theorem_name_clue": [_jaccard(_words(thm),_words(n)) for n in names] if thm else None,
            "declaration_order_earliest": [-o for o in orders] if all(o is not None for o in orders) else None,
            "declaration_order_latest": orders if all(o is not None for o in orders) else None,
            "source_position_same_file": [float(_path(c)==source) for c in candidates] if source and all(_path(c) for c in candidates) else None,
            "same_proof_frequency_train": [proof_counts.get(n,0) for n in names] if proof_counts else None,
            "module_frequency_train": [self.module_frequency[_module(c)] for c in candidates] if all(_path(c) for c in candidates) else None,
            "simple_metadata_lookup_train": [self.metadata_lookup.get(source,{}).get(n,0) for n in names] if source else None,
        }


def _summarise(rows: list[tuple[dict, list[float] | None]]) -> dict:
    usable = [(item,scores) for item,scores in rows if scores is not None]
    if not usable:
        return {"status":"NOT_APPLICABLE", "accuracy":None, "evaluated":0,
                "reason":"Required metadata or train-fitted group history unavailable; theorem-disjoint fitting intentionally removes same-proof lookup coverage."}
    correct = sum(_pick(s) == _answer(i) for i,s in usable)
    ties = sum(sum(x==max(s) for x in s)>1 for _,s in usable)
    return {"status":"MEASURED", "correct":correct, "evaluated":len(usable),
            "total_eval_items":len(rows), "accuracy":correct/len(usable),
            "chance":sum(1/len(s) for _,s in usable)/len(usable),
            "ties":ties, "tie_fraction":ties/len(usable),
            "informative_score_items":sum(len(set(s))>1 for _,s in usable)}


def run_shortcut_audit(items: Sequence[Any]) -> dict:
    bank = [_dict(i) for i in items]
    if len({i["task_id"] for i in bank}) != len(bank):
        raise ValueError("Duplicate task identities in audit bank")
    for item in bank:
        p = item.get("provenance",{})
        split = str(p.get("split", "train")).lower()
        source_relpath = str(p.get("source_relpath", ""))
        if split not in {"train","development","dev"} or source_relpath.endswith(("/val.json", "/test.json")):
            raise ValueError("Only DEVELOPMENT/training source items are allowed")
        if len(item["candidate_premises"]) < 2:
            raise ValueError("At least two choices required")
        _answer(item)
    train, evaluation = development_split(bank)
    suite = ShortcutSuite(train)
    visible: dict[str,list] = defaultdict(list)
    private: dict[str,list] = defaultdict(list)
    for item in evaluation:
        scores = suite.visible_scores(item)
        scores["train_only_mdl_rule"] = scores[suite.mdl_rule]
        for name, values in scores.items(): visible[name].append((item,values))
        for name, values in suite.private_scores(item).items(): private[name].append((item,values))
    visible_report = {k:_summarise(v) for k,v in sorted(visible.items())}
    strongest = max(visible_report, key=lambda k: (visible_report[k]["accuracy"], k))
    # Descriptive feature separation, never candidate rejection or a learned test rule.
    feature_gaps = {}
    for name,rows in {**visible,**private}.items():
        gold, negatives = [], []
        for item,scores in rows:
            if scores is None: continue
            answer = _answer(item)
            gold.append(scores[answer]); negatives.extend(v for n,v in enumerate(scores) if n != answer)
        if gold:
            feature_gaps[name] = {"gold_mean":sum(gold)/len(gold),
                                  "distractor_mean":sum(negatives)/len(negatives)}
    return {
        "audit_version":"astra-shortcuts-v1", "status":"DEVELOPMENT_DIAGNOSTIC_ONLY",
        "model_calls":0,
        "split":{"seed":SPLIT_SEED if not bank[0].get("audit_metadata",{}).get("dev_partition") else "bank-declared; see development manifest",
                 "method":"bank-declared partitions honored" if bank[0].get("audit_metadata",{}).get("dev_partition") else "seeded rank; 30% groups held out",
                 "unit":"theorem/proof group","train_items":len(train),
                 "eval_items":len(evaluation),"train_groups":len({group_id(i) for i in train}),
                 "eval_groups":len({group_id(i) for i in evaluation}),
                 "train_task_ids":[i["task_id"] for i in train],"eval_task_ids":[i["task_id"] for i in evaluation],
                 "group_overlap":sorted({group_id(i) for i in train}&{group_id(i) for i in evaluation})},
        "k_histogram":dict(sorted(Counter(len(i["candidate_premises"]) for i in evaluation).items())),
        "chance":sum(1/len(i["candidate_premises"]) for i in evaluation)/len(evaluation),
        "fit_policy":"All outcome-conditioned counters, goal lookups, and MDL rule selection use only development training. No validation/test source is loaded.",
        "sampler_scope_note":"Source-pool frequencies/same-proof membership may have been used by the upstream distractor sampler before development partitioning. These are not reused to fit any audit rule; this audit diagnoses the supplied bank, not an independently sampled promotion distribution.",
        "tie_policy":"First candidate in frozen shared order; report tie rate and informative-score coverage.",
        "visible_information_rules":visible_report,
        "private_metadata_controls":{k:_summarise(v) for k,v in sorted(private.items())},
        "mdl":{"selected_rule":suite.mdl_rule,"training_description_bits":suite.mdl_costs,
               "code":"uniform rule ID + mistake count + log2 binomial(n,e) + sum mistakes log2(K-1)"},
        "feature_separation":feature_gaps,
        "strongest_visible_rule":{"name":strongest,**visible_report[strongest]},
        "qualification_gate_applied":False,
        "future_preregistration_recommendation":{
            "numeric_ceiling":None,
            "reason":"These exploratory results cannot retroactively define a qualifying ceiling. Freeze a new sampler and practical effect delta before an independent calibration and model evaluation.",
            "proposed_rule":"Require the solver to exceed max(chance, simultaneous upper confidence bound for strongest frozen plausible visible dumb rule) + preregistered delta; reject an instrument without headroom below 1-delta.",
            "delta_guidance":"Specify delta by practical discrimination, e.g. additional verified choices per 100 decisions, before evaluation; no delta is selected here.",
            "uncertainty":"Theorem-group uncertainty and multiplicity across rules must be addressed on fresh calibration. Point accuracies here are not qualification evidence."},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # CLI admits only local bridge banks, not arbitrary source split JSON.
    if args.bank.suffix != ".jsonl" or not ("development" in args.bank.name or args.bank.name == "dev_bank.jsonl"):
        parser.error("--bank must name dev_bank.jsonl or a development*.jsonl bridge bank")
    items = [json.loads(line) for line in args.bank.read_text().splitlines() if line.strip()]
    report = run_shortcut_audit(items)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"output":str(args.out),"split":{k:v for k,v in report["split"].items() if not k.endswith("task_ids")},"strongest":report["strongest_visible_rule"]},indent=2))


if __name__ == "__main__":
    main()
