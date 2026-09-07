"""A9 decisive measurement: V7 audits a serialization the Solver is never shown.

``fitness_v5.shortcut_audit`` (``arena/experiments/fitness_v5.py:790-834``) evaluates every
positional / frequency rule against
``canonical_json(probe.state.to_dict(include_display_identity=False))`` -- the canonical record.

The Solver is shown ``build_prompt(genome, probe)`` (``fitness_v5.py:550-565``), whose state block
is ``ModelViewCompiler(genome).compile(state).text`` =
``GenomePhenotypeLanguage(genome.surface).render(state)`` (``arena/model_view/compiler.py:66,75``).

``canonical_json`` sorts object keys, so ``"goal"`` precedes ``"objects"``.  Every phenotype
renderer emits its own field order, and several put the ``objects`` block first.  Because the two
candidate identifiers are context identities they appear in that block in a *sorted, answer-
independent* order, so a positional rule computed on the rendered bytes can be pinned to a
constant while the same rule computed on the canonical record tracks the answer perfectly.

This script recomputes the three positional/frequency rules on
  (a) the canonical record  -- exactly V5's own computation, as a control;
  (b) each founder's rendered STATE;
  (c) each founder's full PROMPT, i.e. the bytes actually sent to the Solver,
for every (mechanism, level) cell.  Read-only rendering; ZERO model calls.
"""

from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    V5Probe,
    build_prompt,
    equal_information_genome,
    v5_founders,
)
from arena.languages.phenotype import GenomePhenotypeLanguage

RULE_NAMES = ("first_mentioned_in_state", "last_mentioned_in_state", "more_frequent_in_state")
_MISS = 1 << 40


def rules_on_text(body: str, a: str, b: str) -> dict[str, int]:
    fa, fb = body.find(a), body.find(b)
    return {
        "first_mentioned_in_state": 0 if (fa if fa >= 0 else _MISS) <= (fb if fb >= 0 else _MISS) else 1,
        "last_mentioned_in_state": 0 if body.rfind(a) >= body.rfind(b) else 1,
        "more_frequent_in_state": 0 if body.count(a) >= body.count(b) else 1,
    }


def score(cell: Sequence[V5Probe], body_of, quote: bool) -> dict[str, float]:
    hits = dict.fromkeys(RULE_NAMES, 0)
    for p in cell:
        a = str(p.options[0].arguments[0].value)
        b = str(p.options[1].arguments[0].value)
        if quote:
            a, b = f'"{a}"', f'"{b}"'
        for rule, idx in rules_on_text(body_of(p), a, b).items():
            hits[rule] += int(idx == p.expected_index)
    return {r: v / len(cell) for r, v in hits.items()}


def main() -> int:
    with Path(sys.argv[1]).open("rb") as handle:
        probes: tuple[V5Probe, ...] = pickle.load(handle)
    out = Path(sys.argv[2])
    founders = v5_founders()

    cells: dict[tuple[str, int], list[V5Probe]] = defaultdict(list)
    for p in probes:
        if p.variant.value in POSITIVE_VARIANTS:
            cells[(p.mechanism, p.level)].append(p)

    table: dict[str, Any] = {}
    for (mechanism, level), cell in sorted(cells.items()):
        key = f"{mechanism}/L{level}"
        entry: dict[str, Any] = {
            "V5_AUDIT_canonical_record": score(
                cell,
                lambda p: canonical_json(p.state.to_dict(include_display_identity=False)),
                quote=True,
            )
        }
        for genome in founders:
            lang = GenomePhenotypeLanguage(genome.surface)
            entry[f"{genome.candidate_id}|rendered_state"] = score(
                cell, lambda p, L=lang: L.render(p.state), quote=True
            )
            entry[f"{genome.candidate_id}|full_prompt"] = score(
                cell, lambda p, G=genome: build_prompt(G, p), quote=True
            )
            entry[f"{genome.candidate_id}|full_prompt_bare"] = score(
                cell, lambda p, G=genome: build_prompt(G, p), quote=False
            )
        table[key] = entry

    out.write_text(json.dumps(table, indent=2, sort_keys=True))

    control = equal_information_genome().candidate_id  # V5E_L3_JSON_AST -- V7's only candidate
    print(f"V7's ONE candidate = {control}\n")
    print(f"{'cell':28s} {'rule':26s} {'V5_audit':>9s} {'ctrl_state':>11s} {'ctrl_prompt':>12s}")
    for key, entry in table.items():
        for rule in RULE_NAMES:
            print(
                f"{key:28s} {rule:26s} "
                f"{entry['V5_AUDIT_canonical_record'][rule]:9.4f} "
                f"{entry[f'{control}|rendered_state'][rule]:11.4f} "
                f"{entry[f'{control}|full_prompt'][rule]:12.4f}"
            )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
