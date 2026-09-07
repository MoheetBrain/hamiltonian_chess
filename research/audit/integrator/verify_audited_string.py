"""Integrator verification: the V7 shortcut audit reads a string the Solver never receives.

`shortcut_audit` (arena/experiments/fitness_v5.py:798-799) evaluates its rules against
    canonical_json(probe.state.to_dict(include_display_identity=False))
while the Solver receives `build_prompt` (:550-565), whose CURRENT STATE block is
    ModelViewCompiler(genome).compile(...).text
i.e. the *rendered* representation.  These are different strings with different orderings.

Run:  python -m research.audit.integrator.verify_audited_string
No model call is made.  This is a diagnostic of the instrument, NOT a re-scoring of V7.
"""

from __future__ import annotations

import collections
from pathlib import Path

from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    build_dev_pool,
    canonical_json,
    equal_information_genome,
)
from arena.model_view.compiler import ModelViewCompiler


def _names(probe) -> tuple[str, str]:
    return (str(probe.options[0].arguments[0].value), str(probe.options[1].arguments[0].value))


def first_mentioned(text: str, probe) -> int:
    a, b = _names(probe)
    ia, ib = text.find(f'"{a}"'), text.find(f'"{b}"')
    if ia == -1 or ib == -1:  # non-JSON surfaces do not quote identifiers
        ia, ib = text.find(a), text.find(b)
    return 0 if ia <= ib else 1


def last_mentioned(text: str, probe) -> int:
    a, b = _names(probe)
    return 0 if text.rfind(a) >= text.rfind(b) else 1


def main() -> int:
    pool = build_dev_pool(Path.cwd())
    genome = equal_information_genome()
    compiler = ModelViewCompiler(genome)

    cells: dict[tuple[str, int], list[int]] = collections.defaultdict(lambda: [0, 0, 0, 0])
    for probe in pool:
        if probe.variant.value not in POSITIVE_VARIANTS:
            continue
        canon = canonical_json(probe.state.to_dict(include_display_identity=False))
        rendered = compiler.compile(probe.state, options=probe.options).text
        cell = cells[(probe.mechanism, probe.level)]
        cell[0] += int(first_mentioned(canon, probe) == probe.expected_index)
        cell[1] += int(first_mentioned(rendered, probe) == probe.expected_index)
        cell[2] += int(last_mentioned(rendered, probe) == probe.expected_index)
        cell[3] += 1

    print(f"control surface: {genome.surface.candidate_id}   positives: "
          f"{sum(c[3] for c in cells.values())}")
    print(f"\n{'mechanism':26s} L   n   fm(CANON)  fm(RENDER)  lm(RENDER)")
    for key in sorted(cells):
        canon_ok, rend_ok, last_ok, n = cells[key]
        print(f"{key[0]:26s} {key[1]}  {n:3d}   {canon_ok / n:.4f}     "
              f"{rend_ok / n:.4f}      {last_ok / n:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
