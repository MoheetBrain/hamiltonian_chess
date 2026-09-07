"""A2 construct-validity audit: extract surface/structural covariates for every V7 probe.

READ-ONLY with respect to the experiment.  Makes NO model call: the probe bank is
materialised by ``arena.experiments.fitness_v5.build_dev_pool`` (pure construction --
Lean corpus file reads, renderer, NativeVerifier) and the control-surface prompt is
built by ``fitness_v5.build_prompt``.  Real token counts are joined from the FROZEN V7
artifact's own ``prompt_eval_count`` rows (qwen38-rvn's tokenizer), never re-measured.

Outputs (all under research/audit/a2_covariates/):
  probe_covariates.jsonl   one record per probe, every measured covariate
  cell_features.json       per (mechanism, level) aggregate feature table
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from arena.canonical.schema import CanonicalExpression, CanonicalState, canonical_json
from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    V5Probe,
    build_dev_pool,
    build_prompt,
    equal_information_genome,
)

OUT = Path(__file__).resolve().parent
ARTIFACT = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")

# --------------------------------------------------------------------------- helpers


def state_text(probe: V5Probe) -> str:
    """Exactly the text V5/V7's shortcut_audit searches (fitness_v5.py:795)."""
    return canonical_json(probe.state.to_dict(include_display_identity=False))


def option_names(probe: V5Probe) -> tuple[str, str]:
    return (
        str(probe.options[0].arguments[0].value),
        str(probe.options[1].arguments[0].value),
    )


def view_text(prompt: str) -> str:
    """The CURRENT STATE section of the rendered prompt only (excludes the OPTIONS block)."""
    start = prompt.find("CURRENT STATE:\n")
    end = prompt.rfind("\nOPTIONS:\n")
    return prompt[start + len("CURRENT STATE:\n") : end] if start >= 0 and end > start else prompt


def walk(node: CanonicalExpression) -> list[tuple[int, int, str | int | None, str]]:
    """(preorder_index, depth, value, op) for every node of an expression tree."""
    out: list[tuple[int, int, str | int | None, str]] = []
    counter = [0]

    def rec(cur: CanonicalExpression, depth: int) -> None:
        out.append((counter[0], depth, cur.value, cur.op))
        counter[0] += 1
        for child in cur.args:
            rec(child, depth + 1)

    rec(node, 0)
    return out


def ast_stats(nodes: list[tuple[int, int, str | int | None, str]], name: str) -> dict[str, Any]:
    hits = [(i, d) for i, d, v, _ in nodes if isinstance(v, str) and v == name]
    if not hits:
        return {
            "ast_first_preorder": None,
            "ast_last_preorder": None,
            "ast_max_depth": None,
            "ast_min_depth": None,
            "ast_mean_depth": None,
            "ast_count": 0,
        }
    return {
        "ast_first_preorder": hits[0][0],
        "ast_last_preorder": hits[-1][0],
        "ast_max_depth": max(d for _, d in hits),
        "ast_min_depth": min(d for _, d in hits),
        "ast_mean_depth": sum(d for _, d in hits) / len(hits),
        "ast_count": len(hits),
    }


def dep_graph(state: CanonicalState) -> dict[str, tuple[str, ...]]:
    return {n.evidence_id: tuple(n.dependencies) for n in state.evidence_dependencies}


def hop_distance(graph: dict[str, tuple[str, ...]], source: str, target: str) -> int | None:
    seen = {source}
    queue: deque[tuple[str, int]] = deque([(source, 0)])
    while queue:
        node, dist = queue.popleft()
        if node == target:
            return dist
        for nxt in graph.get(node, ()):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, dist + 1))
    return None


def balance_prefix(text: str) -> list[int]:
    """Running bracket nesting depth of the rendered text, one entry per character."""
    out = [0] * (len(text) + 1)
    depth = 0
    for i, ch in enumerate(text):
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        out[i + 1] = depth
    return out


def occurrences(text: str, needle: str) -> list[int]:
    found: list[int] = []
    start = text.find(needle)
    while start >= 0:
        found.append(start)
        start = text.find(needle, start + 1)
    return found


def ngrams(text: str, n: int = 4) -> set[str]:
    return {text[i : i + n] for i in range(max(0, len(text) - n + 1))}


WORD = re.compile(r"[A-Za-z0-9_:./-]+")


def premise_stats(state: CanonicalState, answer: str) -> dict[str, Any]:
    held = {
        str(x.args[0].value) for x in state.assumptions if x.op == "holds" and x.args
    }
    required = [
        str(x.args[1].value)
        for x in state.propositions
        if x.op == "requires" and len(x.args) == 2 and str(x.args[0].value) == answer
    ]
    first_index = next(
        (
            i
            for i, x in enumerate(state.propositions)
            if x.op == "requires" and len(x.args) == 2 and str(x.args[0].value) == answer
        ),
        None,
    )
    matched = sum(p in held for p in required)
    return {
        "prem_required": len(required),
        "prem_matched": matched,
        "prem_unmatched": len(required) - matched,
        "prem_all_matched": int(len(required) > 0 and matched == len(required)),
        "prem_first_prop_index": first_index,
        "prem_mean_held_index": None,
    }


# --------------------------------------------------------------------------- per probe


def covariates(probe: V5Probe, prompt: str) -> dict[str, Any]:
    stext = state_text(probe)
    vtext = view_text(prompt)
    names = option_names(probe)
    goal_nodes = walk(probe.state.goal)
    graph = dep_graph(probe.state)
    per_option: list[dict[str, Any]] = []
    opt_render = [
        prompt.split("\nOPTIONS:\n", 1)[1].split("\nANSWER:")[0].split("\nB: ")[i]
        if "\nB: " in prompt
        else ""
        for i in range(2)
    ]
    view_grams = ngrams(vtext)
    balance = balance_prefix(vtext)
    for i, name in enumerate(names):
        quoted = f'"{name}"'
        rec: dict[str, Any] = {
            "name": name,
            # --- V5/V7 shortcut text (canonical state JSON, sorted keys) ---
            "state_first": stext.find(quoted),
            "state_last": stext.rfind(quoted),
            "state_count": stext.count(quoted),
            "state_first_norm": (stext.find(quoted) / len(stext)) if stext else 0.0,
            # --- the text the SOLVER actually reads (rendered control surface).
            # Quoted search: the bare id is a substring of longer ids ("f3" inside "f33").
            "view_first": vtext.find(quoted),
            "view_last": vtext.rfind(quoted),
            "view_count": vtext.count(quoted),
            "prompt_first": prompt.find(quoted),
            "prompt_last": prompt.rfind(quoted),
            "prompt_count": prompt.count(quoted),
            "view_first_norm": (vtext.find(quoted) / len(vtext)) if vtext else 0.0,
            "view_last_from_end": (len(vtext) - vtext.rfind(quoted)) if vtext else 0,
            # --- rendered-STRING structural proxies for nesting depth ---
            "view_max_brace_depth": (
                max(balance[i] for i in occurrences(vtext, quoted))
                if occurrences(vtext, quoted)
                else None
            ),
            "view_min_brace_depth": (
                min(balance[i] for i in occurrences(vtext, quoted))
                if occurrences(vtext, quoted)
                else None
            ),
            "view_mean_brace_depth": (
                sum(balance[i] for i in occurrences(vtext, quoted))
                / len(occurrences(vtext, quoted))
                if occurrences(vtext, quoted)
                else None
            ),
            "view_open_braces_before_first": (
                vtext[: vtext.find(quoted)].count("{") if vtext.find(quoted) >= 0 else None
            ),
            # --- identifier naming ---
            "name_chars": len(name),
            "name_alpha_rank": name,
            "name_trailing_int": int(m.group()) if (m := re.search(r"\d+$", name)) else -1,
            "name_ws_tokens": len(WORD.findall(name)),
            # --- lexical overlap between the option render and the state view ---
            "opt_view_overlap": (
                len(ngrams(opt_render[i]) & view_grams) / max(1, len(ngrams(opt_render[i])))
                if opt_render[i]
                else 0.0
            ),
            "opt_render_chars": len(opt_render[i]),
        }
        rec.update(ast_stats(goal_nodes, name))
        # --- dependency graph (transitive_dependency) ---
        rec["dep_hops_from_leaf"] = hop_distance(graph, "e:leaf", name)
        rec["dep_is_ancestor"] = int(rec["dep_hops_from_leaf"] is not None)
        rec["dep_node_index"] = next(
            (i for i, n in enumerate(probe.state.evidence_dependencies) if n.evidence_id == name),
            None,
        )
        rec["dep_in_degree"] = sum(name in deps for deps in graph.values())
        rec["dep_out_degree"] = len(graph.get(name, ()))
        leaf_pos = stext.find('"e:leaf"')
        rec["dep_text_dist_to_leaf"] = (
            abs(stext.find(quoted) - leaf_pos) if leaf_pos >= 0 and stext.find(quoted) >= 0 else None
        )
        # --- premise satisfaction (precondition_conjunction) ---
        rec.update(premise_stats(probe.state, name))
        per_option.append(rec)

    delim = {c: stext.count(c) for c in "{}[]()\",:"}
    identifiers = {
        v for _, _, v, _ in goal_nodes if isinstance(v, str)
    }
    depths = [d for _, d, v, _ in goal_nodes if isinstance(v, str)]
    return {
        "probe_id": probe.probe_id,
        "family_id": probe.family_id,
        "mechanism": probe.mechanism,
        "level": probe.level,
        "variant": probe.variant.value,
        "truth_kind": probe.truth_kind,
        "expected_index": probe.expected_index,
        "is_positive": probe.variant.value in POSITIVE_VARIANTS,
        "options": list(names),
        "prompt_chars": len(prompt),
        "state_chars": len(stext),
        "view_chars": len(vtext),
        "option_count": len(probe.options),
        "goal_nodes": len(goal_nodes),
        "goal_max_depth": max((d for _, d, _, _ in goal_nodes), default=0),
        "goal_leaf_identifiers": len(identifiers),
        "goal_identifier_mean_depth": (sum(depths) / len(depths)) if depths else 0.0,
        "state_objects": len(probe.state.objects),
        "state_assumptions": len(probe.state.assumptions),
        "state_propositions": len(probe.state.propositions),
        "state_facts": len(probe.state.established_facts),
        "state_evidence_nodes": len(probe.state.evidence_dependencies),
        "delimiters": delim,
        "delimiter_total": sum(delim.values()),
        "per_option": per_option,
    }


def main() -> int:
    root = Path.cwd()
    probes = build_dev_pool(root)
    genome = equal_information_genome()
    tokens: dict[str, int] = {}
    if ARTIFACT.exists():
        art = json.loads(ARTIFACT.read_text())
        tokens = {r["probe_id"]: int(r["prompt_tokens"]) for r in art["rows"]}
    records = []
    for probe in probes:
        prompt = build_prompt(genome, probe)
        rec = covariates(probe, prompt)
        rec["prompt_tokens_real"] = tokens.get(probe.probe_id)
        records.append(rec)
    with (OUT / "probe_covariates.jsonl").open("w") as handle:
        for rec in records:
            handle.write(json.dumps(rec) + "\n")

    cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if rec["is_positive"]:
            cells[f"{rec['mechanism']}|L{rec['level']}"].append(rec)
    table = {}
    for key, rows in sorted(cells.items()):
        def mean(field: str) -> float:
            vals = [r[field] for r in rows if r[field] is not None]
            return round(sum(vals) / len(vals), 3) if vals else 0.0

        table[key] = {
            "n_positive_probes": len(rows),
            "prompt_tokens_real_mean": mean("prompt_tokens_real"),
            "prompt_tokens_real_min": min(
                (r["prompt_tokens_real"] for r in rows if r["prompt_tokens_real"]), default=0
            ),
            "prompt_tokens_real_max": max(
                (r["prompt_tokens_real"] for r in rows if r["prompt_tokens_real"]), default=0
            ),
            "prompt_chars_mean": mean("prompt_chars"),
            "state_chars_mean": mean("state_chars"),
            "view_chars_mean": mean("view_chars"),
            "option_count": rows[0]["option_count"],
            "goal_nodes_mean": mean("goal_nodes"),
            "goal_max_depth_mean": mean("goal_max_depth"),
            "goal_leaf_identifiers_mean": mean("goal_leaf_identifiers"),
            "goal_identifier_mean_depth": mean("goal_identifier_mean_depth"),
            "state_objects_mean": mean("state_objects"),
            "state_assumptions_mean": mean("state_assumptions"),
            "state_propositions_mean": mean("state_propositions"),
            "state_facts_mean": mean("state_facts"),
            "state_evidence_nodes_mean": mean("state_evidence_nodes"),
            "delimiter_total_mean": mean("delimiter_total"),
            "answer_share_index0": round(
                sum(r["expected_index"] == 0 for r in rows) / len(rows), 3
            ),
            "target_first_mention_norm_mean": round(
                sum(
                    r["per_option"][r["expected_index"]]["state_first_norm"] for r in rows
                )
                / len(rows),
                4,
            ),
            "opt_view_overlap_mean": round(
                sum(o["opt_view_overlap"] for r in rows for o in r["per_option"])
                / (2 * len(rows)),
                4,
            ),
        }
    (OUT / "cell_features.json").write_text(json.dumps(table, indent=2) + "\n")
    print(json.dumps({"probes": len(records), "cells": len(table)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
