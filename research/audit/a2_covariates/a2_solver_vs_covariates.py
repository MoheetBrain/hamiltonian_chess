"""A2: the solver's measured accuracy against the best single covariate, per cell.

Solver accuracy is READ from the FROZEN V7 artifact
(``artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json``);
nothing is re-scored and no model is called.  Covariate accuracy comes from
``predictability_matrix.json``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parent
ART = Path("artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json")
POSITIVE = {"ORIGINAL", "COUNTERFACTUAL"}
TRUTH = ("ast_greatest_depth[", "dep_is_ancestor[", "prem_all_matched[")
#: Covariate families that require NO domain operation at all -- position, order, counting
#: of identifier occurrences, naming, option slot.  A reader using one of these has not
#: performed the mechanism's operation in any sense.
CHEAP_SURFACE = {
    "string_position",
    "frequency",
    "naming",
    "option_order",
    "length",
    "lexical_overlap",
    "field_order",
    "traversal_order",
    "delimiter_count",
}
#: A character-counting rule over the rendered bracketed serialisation.  Not "reasoning",
#: but not free either: it requires scanning the whole string.
COUNTING_SURFACE = {"rendered_string_depth"}


def main() -> int:
    art = json.loads(ART.read_text())
    acc: dict[str, list[int]] = defaultdict(list)
    for row in art["rows"]:
        if row["variant"] in POSITIVE:
            acc[f"{row['mechanism']}|L{row['level']}"].append(int(row["correct"]))
    matrix = json.loads((OUT / "predictability_matrix.json").read_text())["matrix"]
    v7_audit = art["shortcut_audit_by_level"]

    table = {}
    for cell, hits in sorted(acc.items()):
        mech, lvl = cell.split("|L")
        solver = sum(hits) / len(hits)
        def rank(families: set[str]) -> list[tuple[str, float]]:
            return sorted(
                (
                    (cid, e[cell]["best"])
                    for cid, e in matrix.items()
                    if e[cell]["best"] is not None
                    and not cid.startswith(TRUTH)
                    and e["family"] in families
                ),
                key=lambda t: -t[1],
            )

        ranked = rank(CHEAP_SURFACE | COUNTING_SURFACE)
        cheap = rank(CHEAP_SURFACE)
        counting = rank(COUNTING_SURFACE)
        best_cid, best_val = ranked[0]
        v7_best = float(v7_audit[mech][lvl]["best_shortcut_accuracy"])
        table[cell] = {
            "solver_accuracy_frozen_v7": round(solver, 4),
            "n_positive": len(hits),
            "v7_best_shortcut": round(v7_best, 4),
            "v7_best_shortcut_feature": v7_audit[mech][lvl]["best_shortcut_feature"],
            "a2_best_covariate": best_cid,
            "a2_best_covariate_accuracy": best_val,
            "a2_margin_solver_minus_covariate": round(solver - best_val, 4),
            "v7_margin_solver_minus_shortcut": round(solver - v7_best, 4),
            "a2_understated_by_v7": round(best_val - v7_best, 4),
            "solver_beats_best_covariate": bool(solver - best_val >= 0.10),
            "a2_best_cheap_surface": cheap[0][0] if cheap else None,
            "a2_best_cheap_surface_accuracy": cheap[0][1] if cheap else None,
            "a2_margin_solver_minus_cheap": round(solver - cheap[0][1], 4) if cheap else None,
            "a2_best_counting_surface": counting[0][0] if counting else None,
            "a2_best_counting_surface_accuracy": counting[0][1] if counting else None,
            "a2_top5": [{"covariate": c, "best": b} for c, b in ranked[:5]],
        }
    (OUT / "solver_vs_covariates.json").write_text(json.dumps(table, indent=2) + "\n")
    header = (
        "| cell | solver | V7 best shortcut | A2 best CHEAP surface rule | A2 cheap | "
        "A2 best COUNTING rule | A2 count | V7 margin | A2 cheap margin |"
    )
    lines = [header, "|" + "---|" * 9]
    for cell, r in table.items():
        lines.append(
            f"| `{cell}` | {r['solver_accuracy_frozen_v7']:.3f} | "
            f"{r['v7_best_shortcut']:.3f} (`{r['v7_best_shortcut_feature']}`) | "
            f"`{r['a2_best_cheap_surface']}` | {r['a2_best_cheap_surface_accuracy']:.3f} | "
            f"`{r['a2_best_counting_surface']}` | {r['a2_best_counting_surface_accuracy']:.3f} | "
            f"{r['v7_margin_solver_minus_shortcut']:+.3f} | "
            f"{r['a2_margin_solver_minus_cheap']:+.3f} |"
        )
    (OUT / "solver_vs_covariates.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
