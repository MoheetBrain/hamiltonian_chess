"""A9: what V7's gates would say if the shortcut audit measured the Solver's own bytes.

This is a COUNTERFACTUAL RECOMPUTATION, not a re-score.  No model is called, no threshold is
changed, no V7 file or artifact is touched.  The accuracies are read verbatim from the frozen V7
artifact; only ``best_shortcut_accuracy`` is recomputed, using V5's own seven rules with the three
state-dependent ones evaluated on ``build_prompt(control_genome, probe)`` -- the exact bytes the
Solver received -- instead of on ``canonical_json(state.to_dict(...))``, which no Solver ever saw.

Everything else (rule set, ``worst_score`` best-of-rule-or-negation arithmetic, SHORTCUT_MARGIN,
shortcut_rule_max, frontier derivation, selector) is V7's, imported and unmodified.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    QUALIFICATION_RULE,
    V5Probe,
    build_prompt,
    equal_information_genome,
)
from arena.experiments.fitness_v7 import (
    SHORTCUT_MARGIN,
    qualify_mechanism,
    select_frontier_level,
)

_MISS = 1 << 40
CONTROL = equal_information_genome()  # V5E_L3_JSON_AST -- the ONE candidate V7 renders


def audit_on(bodies: dict[str, str], cell: Sequence[V5Probe]) -> dict[str, Any]:
    """V5's shortcut_audit arithmetic, with the observation text supplied by the caller."""

    def names(p: V5Probe) -> tuple[str, str]:
        return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))

    def find(body: str, needle: str) -> int:
        i = body.find(needle)
        return i if i >= 0 else _MISS

    rules: dict[str, Callable[[V5Probe], int]] = {
        "always_first_option": lambda p: 0,
        "always_second_option": lambda p: 1,
        "first_mentioned_in_state": lambda p: (
            0
            if find(bodies[p.probe_id], f'"{names(p)[0]}"')
            <= find(bodies[p.probe_id], f'"{names(p)[1]}"')
            else 1
        ),
        "last_mentioned_in_state": lambda p: (
            0
            if bodies[p.probe_id].rfind(f'"{names(p)[0]}"')
            >= bodies[p.probe_id].rfind(f'"{names(p)[1]}"')
            else 1
        ),
        "more_frequent_in_state": lambda p: (
            0
            if bodies[p.probe_id].count(f'"{names(p)[0]}"')
            >= bodies[p.probe_id].count(f'"{names(p)[1]}"')
            else 1
        ),
        "shorter_option_text": lambda p: (
            0 if (len(names(p)[0]), names(p)[0]) <= (len(names(p)[1]), names(p)[1]) else 1
        ),
        "alphabetically_first": lambda p: 0 if names(p)[0] <= names(p)[1] else 1,
    }
    scores = {n: sum(r(p) == p.expected_index for p in cell) / len(cell) for n, r in rules.items()}
    worst = max(scores, key=lambda n: abs(scores[n] - 0.5))
    return {
        "items": len(cell),
        "scores": scores,
        "best_shortcut_feature": worst,
        "best_shortcut_accuracy": max(scores[worst], 1.0 - scores[worst]),
    }


def main() -> int:
    with Path(sys.argv[1]).open("rb") as handle:
        probes: tuple[V5Probe, ...] = pickle.load(handle)
    artifact = json.loads(Path(sys.argv[2]).read_text())
    out = Path(sys.argv[3])

    cells: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for p in probes:
        if p.variant.value in POSITIVE_VARIANTS:
            cells[(p.mechanism, p.level)].append(p)

    # frozen, per-level positive accuracy straight out of the V7 artifact rows
    acc: dict[tuple[str, int], float] = {}
    summaries: dict[tuple[str, int], dict[str, Any]] = {}
    ladder = {m: {int(x["level"]): x for x in e["ladder"]} for m, e in artifact["mechanisms"].items()}
    for mechanism, levels in ladder.items():
        for level, entry in levels.items():
            acc[(mechanism, level)] = float(entry["positive_accuracy"])
            summaries[(mechanism, level)] = entry

    report: dict[str, Any] = {
        "control_candidate": CONTROL.candidate_id,
        "shortcut_margin": SHORTCUT_MARGIN,
        "shortcut_rule_max": QUALIFICATION_RULE["shortcut_rule_max"],
        "cells": {},
        "mechanism_counterfactual_verdicts": {},
    }

    audits: dict[tuple[str, int], dict[str, Any]] = {}
    for key, cell in sorted(cells.items()):
        prompts = {p.probe_id: build_prompt(CONTROL, p) for p in cell}
        canon = {
            p.probe_id: canonical_json(p.state.to_dict(include_display_identity=False))
            for p in cell
        }
        as_shipped = audit_on(canon, cell)
        as_seen = audit_on(prompts, cell)
        audits[key] = as_seen
        a = acc[key]
        report["cells"][f"{key[0]}/L{key[1]}"] = {
            "positive_accuracy": a,
            "V7_shipped_audit": as_shipped,
            "prompt_visible_audit": as_seen,
            "shipped_margin": a - as_shipped["best_shortcut_accuracy"],
            "prompt_visible_margin": a - as_seen["best_shortcut_accuracy"],
        }

    for mechanism in sorted({m for m, _ in cells}):
        levels = {lvl: acc[(mechanism, lvl)] for m, lvl in cells if m == mechanism}
        sel = select_frontier_level(levels)
        entry: dict[str, Any] = {"selection": sel}
        chosen = sel.get("selected_level")
        if chosen is not None:
            summary = summaries[(mechanism, chosen)]
            gate_summary = {
                "positive_accuracy": summary["positive_accuracy"],
                "valid_response_rate": summary["valid_response_rate"],
                "context_truncated_rows": 0,
                "positive_examples": summary["positive_examples"],
                "positive_negative_gap": summary["positive_negative_gap"],
                "largest_answer_share": summary["largest_answer_share"],
                "position_invariance": summary["position_invariance"],
            }
            entry["V7_as_shipped"] = qualify_mechanism(
                gate_summary,
                {
                    "best_shortcut_accuracy": summary["best_shortcut_accuracy"],
                    "best_shortcut_feature": summary["best_shortcut_feature"],
                },
                float(artifact["q0"]["rate"]),
            )
            entry["counterfactual_prompt_visible"] = qualify_mechanism(
                gate_summary, audits[(mechanism, chosen)], float(artifact["q0"]["rate"])
            )
        report["mechanism_counterfactual_verdicts"][mechanism] = entry

    out.write_text(json.dumps(report, indent=2, sort_keys=True))

    print(f"{'cell':30s} {'acc':>7s} {'shipped':>8s} {'seen':>7s} {'d_ship':>8s} {'d_seen':>8s}  feature(seen)")
    for name, c in report["cells"].items():
        print(
            f"{name:30s} {c['positive_accuracy']:7.4f} "
            f"{c['V7_shipped_audit']['best_shortcut_accuracy']:8.4f} "
            f"{c['prompt_visible_audit']['best_shortcut_accuracy']:7.4f} "
            f"{c['shipped_margin']:+8.4f} {c['prompt_visible_margin']:+8.4f}  "
            f"{c['prompt_visible_audit']['best_shortcut_feature']}"
        )
    print()
    qualified = 0
    for mechanism, entry in report["mechanism_counterfactual_verdicts"].items():
        sel = entry["selection"]
        if "counterfactual_prompt_visible" not in entry:
            print(f"{mechanism:28s} selector -> {sel['verdict']}")
            continue
        ship = entry["V7_as_shipped"]
        seen = entry["counterfactual_prompt_visible"]
        qualified += int(seen["qualified"])
        print(
            f"{mechanism:28s} L{sel['selected_level']}  as_shipped={ship['verdict']:16s} "
            f"counterfactual={seen['verdict']:16s} (margin {seen['shortcut_margin_observed']:+.4f})"
        )
    print(f"\ncounterfactually qualified mechanisms: {qualified} "
          f"(instrument rule needs {QUALIFICATION_RULE['minimum_qualified_mechanisms']})")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
