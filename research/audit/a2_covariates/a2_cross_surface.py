"""A2: is the leak a property of the CONTROL surface, or of the task?

Re-measures three surface rules on the rendered state text of ALL EIGHT seed
representations, for the 96 positive ``formal_expression_depth`` probes.  If every
candidate surface carries the same rule at the same accuracy, then no founder
tournament on this mechanism could ever have measured representation: the winning
strategy is surface-independent.

NO model call.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from arena.experiments.fitness_v5 import POSITIVE_VARIANTS, build_dev_pool, equal_information_genome
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler

OUT = Path(__file__).resolve().parent
OPEN, CLOSE = "{[(", "}])"
import sys
MECHANISM = sys.argv[1] if len(sys.argv) > 1 else "formal_expression_depth"


def depth_profile(text: str, needle: str) -> tuple[int | None, int | None, int | None, int]:
    """(first index, last index, max delimiter depth at an occurrence, occurrences)."""
    depth = 0
    best: int | None = None
    first = last = None
    count = 0
    n = len(needle)
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth -= 1
        if text.startswith(needle, i):
            count += 1
            if first is None:
                first = i
            last = i
            best = depth if best is None else max(best, depth)
        i += 1
    return first, last, best, count


def main() -> int:
    all_probes = build_dev_pool(Path.cwd())
    mechanism = MECHANISM
    probes = [p for p in all_probes if p.mechanism == mechanism]
    positives = [p for p in probes if p.variant.value in POSITIVE_VARIANTS]
    results: dict[str, dict[str, object]] = {}
    for surface_id in SEED_GENOME_BY_ID:
        genome = equal_information_genome(surface_id)
        compiler = ModelViewCompiler(genome)
        GenomePhenotypeLanguage(genome.surface)
        hits: dict[str, list[float]] = defaultdict(list)
        chars: list[int] = []
        for probe in positives:
            text = compiler.compile(probe.state, options=probe.options).text
            chars.append(len(text))
            names = [str(o.arguments[0].value) for o in probe.options]
            profiles = []
            for name in names:
                for needle in (f'"{name}"', name):
                    prof = depth_profile(text, needle)
                    if prof[3] > 0:
                        break
                profiles.append(prof)
            (f0, l0, d0, c0), (f1, l1, d1, c1) = profiles

            def sc(a, b, direction: str) -> float:
                if a is None or b is None:
                    return 0.5
                if a == b:
                    return 0.5
                pick = (0 if a < b else 1) if direction == "min" else (0 if a > b else 1)
                return float(pick == probe.expected_index)

            hits["first_mentioned"].append(sc(f0, f1, "min"))
            hits["last_mentioned"].append(sc(l0, l1, "max"))
            hits["max_delimiter_depth"].append(sc(d0, d1, "max"))
            hits["more_frequent"].append(sc(c0, c1, "max"))
        results[surface_id] = {
            "n": len(positives),
            "mean_rendered_state_chars": round(sum(chars) / len(chars), 1),
            **{
                rule: {
                    "acc": round(sum(v) / len(v), 4),
                    "best": round(max(sum(v) / len(v), 1 - sum(v) / len(v)), 4),
                }
                for rule, v in hits.items()
            },
        }
    (OUT / f"cross_surface_leak_{MECHANISM}.json").write_text(json.dumps(results, indent=2) + "\n")
    header = "| surface | mean state chars | first_mentioned | last_mentioned | max_delimiter_depth | more_frequent |"
    lines = [header, "|" + "---|" * 6]
    for sid, r in results.items():
        lines.append(
            f"| `{sid}` | {r['mean_rendered_state_chars']:.0f} | "
            + " | ".join(
                f"{r[k]['best']:.3f}"
                for k in ("first_mentioned", "last_mentioned", "max_delimiter_depth", "more_frequent")
            )
            + " |"
        )
    (OUT / f"cross_surface_leak_{MECHANISM}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
