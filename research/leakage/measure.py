"""Measure how much of the NEXT_ACTION gold target is derivable by model-free rules."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from arena.compiler.projection import ObservationKind, project_state_for_observation
from arena.languages.registry import SEED_LANGUAGES
from arena.tasks.generators.world_v0 import generate_tasks
from arena.training.prepare_matched_data import ARMS, stratified_split
from arena.training.render_dataset import render_next_action_example

from research.leakage.predictors import (
    ConstRule,
    CopyFieldRule,
    LookupRule,
    induce_arguments_rule,
    scalars,
)
from research.leakage.lib import apply_affix, induce_affix

FIELDS = (
    "action_id", "operation", "target_ids", "arguments",
    "warrant", "preconditions", "generated_obligations", "expected_usefulness",
)


def build_records(total=676, seed=0, with_inputs=True):
    tasks = generate_tasks(total=total, seed=seed)
    langs = {l.candidate_id: l for l in SEED_LANGUAGES}
    records = []
    for i, task in enumerate(tasks):
        tr = task.trajectory.transitions[0]
        obs = project_state_for_observation(tr.state_before, ObservationKind.NEXT_ACTION).to_dict()
        rec = {
            "index": i,
            "domain": task.dimensions.domain,
            "state_id": tr.state_before.state_id,
            "obs": obs,
            "target": tr.action.to_dict(),
        }
        if with_inputs:
            rec["inputs"] = {
                arm: render_next_action_example(task.trajectory, langs[arm]).input_text
                for arm in ARMS
            }
        records.append(rec)
    return tasks, records


# ------------------------------------------------------------- obfuscation


def opaque(prefix: str) -> str:
    return "op" + hashlib.sha256(prefix.encode()).hexdigest()[:12]


def case_prefix(state_id: str) -> str:
    return state_id[len("state:"): -len(":initial")]


def sub_strings(value, mapping):
    if isinstance(value, str):
        for a, b in mapping:
            value = value.replace(a, b)
        return value
    if isinstance(value, dict):
        return {k: sub_strings(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [sub_strings(v, mapping) for v in value]
    return value


def obfuscate(records, mode: str):
    """mode: 'none' | 'state_id_only' | 'all_ids'"""
    out = []
    for rec in records:
        rec = copy.deepcopy(rec)
        pre = case_prefix(rec["state_id"])
        tok = opaque(pre)
        if mode == "state_id_only":
            rec["obs"]["state_id"] = f"state:{tok}:initial"
        elif mode == "all_ids":
            rec["obs"] = sub_strings(rec["obs"], [(pre, tok)])
            rec["obs"]["state_id"] = tok
        out.append(rec)
    return out


# ------------------------------------------------------------- field fitting


def fit_scalar_field(field, train, *, allow_lookup=True):
    """Constant or minimal-table lookup on any visible scalar. MDL: fewest table entries."""
    targets = [r["target"][field] for r in train]
    best = (Counter(map(json.dumps, targets)).most_common(1)[0][0])
    const = ConstRule(json.loads(best))
    cands = [(sum(json.dumps(t) == best for t in targets) / len(train), 1, "constant", const)]
    if allow_lookup:
        keysets = [set(scalars(r["obs"])) for r in train]
        common = set.intersection(*keysets) if keysets else set()
        for k in sorted(common, key=repr):
            table, ok = {}, True
            for r in train:
                key = scalars(r["obs"])[k]
                if not isinstance(key, (str, int, float, bool)) or key is None:
                    ok = False
                    break
                tv = json.dumps(r["target"][field])
                if key in table and table[key] != tv:
                    ok = False
                    break
                table[key] = tv
            if not ok:
                continue
            rule = LookupRule(k, {kk: json.loads(vv) for kk, vv in table.items()})
            acc = sum(rule.predict(r["obs"]) == r["target"][field] for r in train) / len(train)
            cands.append((acc, len(table), f"lookup{k}", rule))
    cands.sort(key=lambda c: (-c[0], c[1]))
    return cands[0][3], cands[0][2], cands[0][0], cands[0][1]


def fit_affix_field(field, train):
    """Learn target = affix-rewrite of some visible string scalar (plus constant fallback)."""
    targets = [r["target"][field] for r in train]
    if not all(isinstance(t, str) for t in targets):
        return None, None
    keysets = [set(scalars(r["obs"])) for r in train]
    common = set.intersection(*keysets) if keysets else set()
    best = None
    for k in sorted(common, key=repr):
        src = [scalars(r["obs"])[k] for r in train]
        if not all(isinstance(s, str) for s in src):
            continue
        rule = induce_affix(src, targets)
        if rule is None:
            continue
        pred = [apply_affix(rule, s) for s in src]
        acc = sum(p == t for p, t in zip(pred, targets)) / len(train)
        if best is None or acc > best[0]:
            best = (acc, k, rule)
    if best is None:
        return None, None

    class _R:
        kind = "string_affix_rewrite"
        families = frozenset({"string_rewrite"})

        def __init__(self, k, rule): self.k, self.rule = k, rule

        def predict(self, obs):
            s = scalars(obs).get(self.k)
            return apply_affix(self.rule, s) if isinstance(s, str) else None

    return _R(best[1], best[2]), f"affix_from{best[1]}"


def fit_list_field(field, train):
    cands = []
    targets = [r["target"][field] for r in train]
    best = Counter(map(json.dumps, targets)).most_common(1)[0][0]
    cands.append((sum(json.dumps(t) == best for t in targets) / len(train), 0,
                  "constant", ConstRule(json.loads(best))))
    for src in ("assumptions", "propositions", "established_facts", "local_scope"):
        rule = CopyFieldRule(src)
        acc = sum(rule.predict(r["obs"]) == r["target"][field] for r in train) / len(train)
        cands.append((acc, 1, f"copy_observation.{src}", rule))
    cands.sort(key=lambda c: (-c[0], c[1]))
    return cands[0][3], cands[0][2]


def fit_arguments(train, *, allow_arith):
    groups = defaultdict(list)
    for r in train:
        groups[r["obs"]["goal"]["op"]].append(r)
    rules, info = {}, {}
    for key, rs in groups.items():
        rule = induce_arguments_rule([r["obs"] for r in rs],
                                     [r["target"]["arguments"] for r in rs],
                                     allow_arith=allow_arith)
        rules[key] = rule
        info[key] = {
            "n_train": len(rs),
            "domain": sorted({r["domain"] for r in rs}),
            "rule": None if rule is None else rule.kind,
            "families": [] if rule is None else sorted(rule.families),
            "train_exact": 0.0 if rule is None else round(
                sum(rule.predict(r["obs"]) == r["target"]["arguments"] for r in rs) / len(rs), 4),
        }
    return rules, info


class ArgumentsRule:
    kind = "grouped_by_goal_op"

    def __init__(self, rules): self.rules = rules

    def predict(self, obs):
        rule = self.rules.get(obs["goal"]["op"])
        return None if rule is None else rule.predict(obs)


def fit_all(train, *, allow_arith):
    rules, described = {}, {}
    r, name = fit_affix_field("action_id", train)
    if r is not None:
        acc = sum(r.predict(x["obs"]) == x["target"]["action_id"] for x in train) / len(train)
    else:
        acc = -1.0
    r2, name2, acc2, _ = fit_scalar_field("action_id", train)
    if acc >= acc2:
        rules["action_id"], described["action_id"] = r, name
    else:
        rules["action_id"], described["action_id"] = r2, name2
    for f in ("operation", "warrant", "expected_usefulness"):
        rule, name, _, size = fit_scalar_field(f, train)
        rules[f], described[f] = rule, f"{name}[{size} entries]"
    for f in ("target_ids", "preconditions", "generated_obligations"):
        rules[f], described[f] = fit_list_field(f, train)
    arg_rules, arg_info = fit_arguments(train, allow_arith=allow_arith)
    rules["arguments"] = ArgumentsRule(arg_rules)
    described["arguments"] = "per-goal-op induced template"
    return rules, described, arg_info


def evaluate(rules, records, *, drop_action_id=False):
    per_field = {f: 0 for f in FIELDS}
    whole = 0
    fields = [f for f in FIELDS if not (drop_action_id and f == "action_id")]
    fails = defaultdict(list)
    for r in records:
        allok = True
        for f in FIELDS:
            try:
                pred = rules[f].predict(r["obs"])
            except Exception:
                pred = None
            ok = pred == r["target"][f]
            per_field[f] += ok
            if f in fields and not ok:
                allok = False
                fails[f].append(r["index"])
        whole += allok
    n = len(records)
    return {
        "n": n,
        "per_field_exact": {f: round(per_field[f] / n, 6) for f in FIELDS},
        "whole_target_exact": round(whole / n, 6),
        "failures": {f: v for f, v in fails.items()},
    }
