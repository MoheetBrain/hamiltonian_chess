"""A2: can the target label be predicted from each covariate ALONE?

Reads ``probe_covariates.jsonl`` (produced by ``a2_extract.py``) and, for every
covariate and every (mechanism, level) cell, scores a one-line decision rule
"choose the option with the {min,max} value of this covariate" against the
preregistered truth.  Chance is exactly 0.500 because the positive arm is balanced
by construction (ORIGINAL expects index 0, COUNTERFACTUAL expects index 1).

``best`` is ``max(acc, 1 - acc)`` -- V5/V7's own ``worst_score`` semantics: a rule
scoring 0.10 is a shortcut scoring 0.90 for anyone willing to negate it.

Also reports COUNTERFACTUAL BLINDNESS: the fraction of families on which a rule is
either right on both siblings or wrong on both.  A rule with blindness 1.000 is
completely untouched by the relabel counterfactual control.

NO model call.  NO existing file is modified.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scipy.stats import binomtest

OUT = Path(__file__).resolve().parent

#: (covariate id, per-option field, direction, family). direction "min" => predict the
#: option with the smaller value; "max" => the larger.  Ties score 0.5.
COVARIATES: list[tuple[str, str, str, str]] = [
    # ---- V5/V7's own inherited rule set, for cross-checking this harness ----
    ("first_mentioned_in_state*", "state_first", "min", "string_position"),
    ("last_mentioned_in_state*", "state_last", "max", "string_position"),
    ("more_frequent_in_state*", "state_count", "max", "frequency"),
    ("shorter_option_text*", "name_chars", "min", "naming"),
    ("alphabetically_first*", "name", "min", "naming"),
    # ---- string position in the text the SOLVER ACTUALLY READS (rendered surface) ----
    ("first_mentioned_in_view", "view_first", "min", "string_position"),
    ("last_mentioned_in_view", "view_last", "max", "string_position"),
    ("nearest_to_view_end", "view_last_from_end", "min", "string_position"),
    ("more_frequent_in_view", "view_count", "max", "frequency"),
    ("first_mentioned_in_prompt", "prompt_first", "min", "string_position"),
    ("more_frequent_in_prompt", "prompt_count", "max", "frequency"),
    # ---- rendered-STRING structural proxies (bracket nesting in the visible text) ----
    ("view_deepest_bracket_nesting", "view_max_brace_depth", "max", "rendered_string_depth"),
    ("view_greater_mean_bracket_nesting", "view_mean_brace_depth", "max", "rendered_string_depth"),
    ("view_greater_min_bracket_nesting", "view_min_brace_depth", "max", "rendered_string_depth"),
    ("view_more_open_braces_before_first", "view_open_braces_before_first", "max", "delimiter_count"),
    ("view_fewer_open_braces_before_first", "view_open_braces_before_first", "min", "delimiter_count"),
    # ---- identifier naming ----
    ("larger_numeric_suffix", "name_trailing_int", "max", "naming"),
    ("smaller_numeric_suffix", "name_trailing_int", "min", "naming"),
    # ---- AST / traversal order (goal expression) ----
    ("ast_greatest_depth[TRUTH:fed]", "ast_max_depth", "max", "structural"),
    ("ast_earliest_preorder", "ast_first_preorder", "min", "traversal_order"),
    ("ast_latest_preorder", "ast_last_preorder", "max", "traversal_order"),
    ("ast_more_occurrences", "ast_count", "max", "frequency"),
    ("ast_greater_mean_depth", "ast_mean_depth", "max", "structural"),
    ("ast_greater_min_depth", "ast_min_depth", "max", "structural"),
    # ---- dependency graph ----
    ("dep_is_ancestor[TRUTH:td]", "dep_is_ancestor", "max", "structural"),
    ("dep_earlier_in_evidence_list", "dep_node_index", "min", "field_order"),
    ("dep_later_in_evidence_list", "dep_node_index", "max", "field_order"),
    ("dep_higher_in_degree", "dep_in_degree", "max", "frequency"),
    ("dep_closer_textually_to_leaf", "dep_text_dist_to_leaf", "min", "string_position"),
    ("dep_farther_textually_from_leaf", "dep_text_dist_to_leaf", "max", "string_position"),
    ("dep_shorter_path_from_leaf", "dep_hops_from_leaf", "min", "structural"),
    # ---- premise satisfaction ----
    ("prem_all_matched[TRUTH:pc]", "prem_all_matched", "max", "structural"),
    ("prem_fewer_unmatched", "prem_unmatched", "min", "structural"),
    ("prem_more_matched", "prem_matched", "max", "structural"),
    ("prem_earlier_first_proposition", "prem_first_prop_index", "min", "field_order"),
    ("prem_later_first_proposition", "prem_first_prop_index", "max", "field_order"),
    # ---- option render / lexical overlap ----
    ("greater_option_state_overlap", "opt_view_overlap", "max", "lexical_overlap"),
    ("shorter_option_render", "opt_render_chars", "min", "length"),
]

CONSTANT_COVARIATES = [("always_first_option*", 0), ("always_second_option*", 1)]


def predict(rec: dict[str, Any], field: str, direction: str) -> float | None:
    """Return 0.0, 1.0 (a definite pick) or 0.5 (a tie); None if the feature is absent."""
    a, b = rec["per_option"][0].get(field), rec["per_option"][1].get(field)
    if a is None or b is None:
        return None
    if a == b:
        return 0.5
    if direction == "min":
        return 0.0 if a < b else 1.0
    return 0.0 if a > b else 1.0


def score(rows: list[dict[str, Any]], field: str, direction: str) -> dict[str, Any]:
    hits: list[float] = []
    ties = 0
    for rec in rows:
        pick = predict(rec, field, direction)
        if pick is None:
            continue
        if pick == 0.5:
            ties += 1
            hits.append(0.5)
        else:
            hits.append(float(int(pick) == rec["expected_index"]))
    if not hits:
        return {"n": 0, "acc": None, "best": None, "tie_rate": None, "p": None}
    acc = sum(hits) / len(hits)
    definite = [h for h in hits if h in (0.0, 1.0)]
    p = (
        binomtest(int(sum(definite)), len(definite), 0.5).pvalue if definite else 1.0
    )
    return {
        "n": len(hits),
        "acc": round(acc, 4),
        "best": round(max(acc, 1.0 - acc), 4),
        "tie_rate": round(ties / len(hits), 4),
        "p": round(float(p), 6),
    }


def constant_score(rows: list[dict[str, Any]], index: int) -> dict[str, Any]:
    hits = [float(rec["expected_index"] == index) for rec in rows]
    acc = sum(hits) / len(hits) if hits else 0.0
    return {
        "n": len(hits),
        "acc": round(acc, 4),
        "best": round(max(acc, 1.0 - acc), 4),
        "tie_rate": 0.0,
        "p": round(float(binomtest(int(sum(hits)), len(hits), 0.5).pvalue), 6) if hits else None,
    }


def blindness(rows: list[dict[str, Any]], field: str, direction: str) -> float | None:
    """Fraction of ORIGINAL/COUNTERFACTUAL family pairs on which the rule agrees with itself.

    1.000 means the relabel counterfactual control has ZERO power against this rule.
    """
    by_family: dict[str, dict[str, float]] = defaultdict(dict)
    for rec in rows:
        pick = predict(rec, field, direction)
        if pick is None or pick == 0.5:
            continue
        by_family[rec["family_id"]][rec["variant"]] = float(
            int(pick) == rec["expected_index"]
        )
    pairs = [
        v for v in by_family.values() if "ORIGINAL" in v and "COUNTERFACTUAL" in v
    ]
    if not pairs:
        return None
    return round(sum(v["ORIGINAL"] == v["COUNTERFACTUAL"] for v in pairs) / len(pairs), 4)


def main() -> int:
    records = [json.loads(line) for line in (OUT / "probe_covariates.jsonl").read_text().splitlines()]
    positives = [r for r in records if r["is_positive"]]

    cells: dict[tuple[str, int | str], list[dict[str, Any]]] = defaultdict(list)
    for rec in positives:
        cells[(rec["mechanism"], rec["level"])].append(rec)
        cells[(rec["mechanism"], "ALL")].append(rec)

    matrix: dict[str, dict[str, Any]] = {}
    for cid, field, direction, family in COVARIATES:
        entry: dict[str, Any] = {"field": field, "direction": direction, "family": family}
        for (mech, lvl), rows in sorted(cells.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            key = f"{mech}|L{lvl}" if lvl != "ALL" else f"{mech}|ALL"
            entry[key] = score(rows, field, direction)
            entry[key]["cf_blindness"] = blindness(rows, field, direction)
        matrix[cid] = entry
    for cid, index in CONSTANT_COVARIATES:
        entry = {"field": "-", "direction": f"constant:{index}", "family": "option_order"}
        for (mech, lvl), rows in sorted(cells.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            key = f"{mech}|L{lvl}" if lvl != "ALL" else f"{mech}|ALL"
            entry[key] = constant_score(rows, index)
            entry[key]["cf_blindness"] = 0.0
        matrix[cid] = entry

    # per-cell headline: the strongest single covariate
    headline: dict[str, Any] = {}
    for (mech, lvl) in sorted(cells, key=lambda k: (k[0], str(k[1]))):
        key = f"{mech}|L{lvl}" if lvl != "ALL" else f"{mech}|ALL"
        ranked = sorted(
            (
                (cid, e[key]["best"], e[key]["acc"], e["family"])
                for cid, e in matrix.items()
                if e[key]["best"] is not None and not cid.startswith(("ast_greatest_depth[",
                                                                     "dep_is_ancestor[",
                                                                     "prem_all_matched["))
            ),
            key=lambda t: -t[1],
        )
        headline[key] = [
            {"covariate": c, "best": b, "acc": a, "family": matrix[c]["family"]}
            for c, b, a, _ in ranked[:6]
        ]

    (OUT / "predictability_matrix.json").write_text(
        json.dumps({"matrix": matrix, "top_non_truth_covariates_per_cell": headline}, indent=2)
        + "\n"
    )

    # ---- markdown rendering of the headline matrix ----
    cols = [
        f"{m}|L{l}"
        for m in ("formal_expression_depth", "transitive_dependency", "precondition_conjunction")
        for l in (0, 1, 2, 3)
    ]
    short = {
        "formal_expression_depth": "FED",
        "transitive_dependency": "TD",
        "precondition_conjunction": "PC",
    }
    header = "| covariate | family | " + " | ".join(
        f"{short[c.split('|')[0]]} {c.split('|')[1]}" for c in cols
    ) + " |"
    lines = [header, "|" + "---|" * (len(cols) + 2)]
    for cid, entry in matrix.items():
        cells_txt = []
        for col in cols:
            s = entry[col]
            cells_txt.append("--" if s["best"] is None else f"{s['best']:.3f}")
        lines.append(f"| `{cid}` | {entry['family']} | " + " | ".join(cells_txt) + " |")
    (OUT / "predictability_matrix.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
