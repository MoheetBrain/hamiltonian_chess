"""Aggregate every noise experiment into the numbers the report is allowed to quote.

Nothing here calls a model.  It reads the per-call ``.jsonl`` logs and derives, from those rows
only, the four quantities HC-V0.6 needs:

1. **Byte-stability.**  Over every ``(experiment, arm/config, options, prompt)`` cell with at
   least two calls: is the raw response identical in all of them?  The unit is the *raw response*,
   not the parsed tactic, because HC-V0.5's divergence was invisible in the tactic.
2. **Where instability lives.**  Cells are cross-tabulated by options dict, so "the seeded greedy
   configuration is stable and the unseeded hot one is not" is read off the data rather than
   asserted.
3. **Cost.**  Seconds per call and total wall clock, per experiment and overall.
4. **The replicate count ``k``.**  A paired McNemar design is simulated against the *measured*
   per-cell flip probability, so the answer is a consequence of the measurement rather than a
   convention.  Both the anchor count ``n`` and the replicate count ``k`` are reported, because
   with a deterministic Solver they are not interchangeable: ``k`` buys nothing that ``n`` does
   not buy more cheaply.

Run::

    .venv/bin/python -m research.phase10.noise.analyze
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from research.phase10.noise.common import OUT_DIR, read_jsonl

#: Row keys that identify the *condition* a call was made under, in preference order.
ARM_KEYS = ("config", "arm", "stratum", "design")


def cell_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    arm = next((str(row[key]) for key in ARM_KEYS if row.get(key)), "-")
    options = json.dumps(row.get("options", {}), sort_keys=True)
    return (str(row.get("experiment", "?")), arm, options, str(row.get("prompt_sha256", "")))


def load_rows(out_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("*.jsonl")):
        for row in read_jsonl(path):
            row["_file"] = path.name
            rows.append(row)
    return rows


def stability_table(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    cells: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = cell_key(row)
        cell = cells.setdefault(
            key,
            {"responses": [], "tactics": [], "ctok": [], "prompt_chars": row.get("prompt_chars")},
        )
        cell["responses"].append(row.get("response_sha256"))
        cell["tactics"].append(str(row.get("tactic")))
        cell["ctok"].append(row.get("completion_tokens"))
    return cells


def _binom_pmf(n: int, p: float) -> list[float]:
    return [math.comb(n, k) * p**k * (1.0 - p) ** (n - k) for k in range(n + 1)]


def _critical_count(d: int, alpha: float) -> int:
    """Largest ``c`` such that rejecting on ``B <= c or B >= d-c`` keeps size ``<= alpha``.

    ``-1`` means no rejection is possible at this ``d`` (which is why very small discordant
    counts carry no power at all -- an exact test cannot reject on three discordant pairs).
    """

    pmf = _binom_pmf(d, 0.5)
    cumulative = 0.0
    critical = -1
    for c in range(d + 1):
        if 2 * c >= d:
            break
        cumulative += pmf[c]
        if 2 * cumulative <= alpha:
            critical = c
        else:
            break
    return critical


def mcnemar_power(n_pairs: int, discordance: float, delta: float, *, alpha: float = 0.05) -> float:
    """Exact power of the two-sided exact (binomial) McNemar test.

    ``discordance`` is the probability a pair disagrees; ``delta`` is ``p_B - p_A``.  Among
    discordant pairs the probability the pair favours B is ``(discordance + delta) / (2 *
    discordance)``.  Computed exactly -- ``D ~ Binomial(n, discordance)`` and, given ``D = d``,
    ``B ~ Binomial(d, pi)`` -- rather than simulated, because the discordant count is small and
    the exact test's critical region is a step function that a simulation only approximates.
    """

    if discordance <= 0 or discordance > 1:
        return 0.0
    pi = (discordance + delta) / (2 * discordance)
    if not 0.0 <= pi <= 1.0:
        return 0.0
    d_pmf = _binom_pmf(n_pairs, discordance)
    power = 0.0
    for d, p_d in enumerate(d_pmf):
        if p_d < 1e-12 or d < 6:
            continue
        critical = _critical_count(d, alpha)
        if critical < 0:
            continue
        b_pmf = _binom_pmf(d, pi)
        reject = sum(b_pmf[: critical + 1]) + sum(b_pmf[d - critical :])
        power += p_d * reject
    return power


def required_pairs(
    discordance: float, delta: float, *, alpha: float = 0.05, power: float = 0.8
) -> int | None:
    for n in range(10, 2001, 5):
        if mcnemar_power(n, discordance, delta, alpha=alpha) >= power:
            return n
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--report", type=Path, default=OUT_DIR / "analysis.json")
    parser.add_argument("--delta", type=float, default=0.10)
    args = parser.parse_args(argv)

    rows = load_rows(args.out_dir)
    if not rows:
        raise SystemExit(f"no .jsonl rows under {args.out_dir}")

    # -- cost ----------------------------------------------------------------------------------
    per_experiment: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        per_experiment[str(row.get("experiment", "?"))].append(float(row.get("wall_seconds", 0.0)))
    cost = {
        name: {
            "calls": len(values),
            "seconds_per_call_median": round(statistics.median(values), 3),
            "seconds_per_call_mean": round(statistics.fmean(values), 3),
            "seconds_total_in_calls": round(sum(values), 1),
        }
        for name, values in sorted(per_experiment.items())
    }
    all_seconds = [float(row.get("wall_seconds", 0.0)) for row in rows]

    # -- stability -----------------------------------------------------------------------------
    cells = stability_table(rows)
    repeated = {key: cell for key, cell in cells.items() if len(cell["responses"]) >= 2}
    by_arm: dict[str, dict[str, Any]] = {}
    for (experiment, arm, options, _digest), cell in repeated.items():
        key = f"{experiment}::{arm}"
        bucket = by_arm.setdefault(
            key,
            {
                "options": json.loads(options),
                "cells": 0,
                "byte_stable": 0,
                "tactic_stable": 0,
                "calls": 0,
                "unstable_prompts": [],
            },
        )
        bucket["cells"] += 1
        bucket["calls"] += len(cell["responses"])
        if len(set(cell["responses"])) == 1:
            bucket["byte_stable"] += 1
        if len(set(cell["tactics"])) == 1:
            bucket["tactic_stable"] += 1
    for (experiment, arm, _options, digest), cell in repeated.items():
        if len(set(cell["responses"])) > 1:
            by_arm[f"{experiment}::{arm}"]["unstable_prompts"].append(
                {
                    "prompt_sha256": digest,
                    "calls": len(cell["responses"]),
                    "distinct_responses": len(set(cell["responses"])),
                    "distinct_tactics": len(set(cell["tactics"])),
                    "distinct_completion_tokens": sorted(
                        {t for t in cell["ctok"] if t is not None}
                    ),
                }
            )
    for bucket in by_arm.values():
        bucket["byte_stable_fraction"] = round(bucket["byte_stable"] / bucket["cells"], 4)
        bucket["tactic_stable_fraction"] = round(bucket["tactic_stable"] / bucket["cells"], 4)

    # -- the frozen configuration, isolated ----------------------------------------------------
    from arena.trajectory.solver import FROZEN_DECODING

    frozen = json.dumps(dict(FROZEN_DECODING), sort_keys=True)
    frozen_cells = {key: cell for key, cell in repeated.items() if key[2] == frozen}
    frozen_unstable = [
        {
            "experiment": k[0],
            "arm": k[1],
            "prompt_sha256": k[3],
            "calls": len(c["responses"]),
            "distinct_responses": len(set(c["responses"])),
            "distinct_tactics": len(set(c["tactics"])),
            "distinct_completion_tokens": sorted({t for t in c["ctok"] if t is not None}),
        }
        for k, c in sorted(frozen_cells.items())
        if len(set(c["responses"])) > 1
    ]
    frozen_calls = sum(len(c["responses"]) for c in frozen_cells.values())
    frozen_summary = {
        "options": dict(FROZEN_DECODING),
        "repeated_cells": len(frozen_cells),
        "calls_in_those_cells": frozen_calls,
        "byte_stable_cells": len(frozen_cells) - len(frozen_unstable),
        "byte_unstable_cells": len(frozen_unstable),
        "byte_stable_fraction": (
            round((len(frozen_cells) - len(frozen_unstable)) / len(frozen_cells), 4)
            if frozen_cells
            else None
        ),
        "unstable_detail": frozen_unstable,
    }

    # -- k and n -------------------------------------------------------------------------------
    # Only cells with enough repeats to have a chance of catching a rare flip inform the rate.
    deep = {key: cell for key, cell in frozen_cells.items() if len(cell["responses"]) >= 8}
    tactic_minority = 0
    byte_minority = 0
    deep_calls = 0
    for cell in deep.values():
        deep_calls += len(cell["responses"])
        for field, sink in (("tactics", "t"), ("responses", "b")):
            counts: dict[Any, int] = defaultdict(int)
            for value in cell[field]:
                counts[value] += 1
            minority = len(cell[field]) - max(counts.values())
            if sink == "t":
                tactic_minority += minority
            else:
                byte_minority += minority
    q_tactic = tactic_minority / deep_calls if deep_calls else 0.0
    q_byte = byte_minority / deep_calls if deep_calls else 0.0
    prompts_deep = {key[3] for key in deep}
    prompts_unstable = {key[3] for key, cell in deep.items() if len(set(cell["tactics"])) > 1}

    design: dict[str, Any] = {
        "delta_min": args.delta,
        "cells_with_at_least_8_repeats": len(deep),
        "calls_in_those_cells": deep_calls,
        "per_call_tactic_flip_rate": round(q_tactic, 5),
        "per_call_raw_byte_flip_rate": round(q_byte, 5),
        "distinct_prompts_probed_deeply": len(prompts_deep),
        "distinct_prompts_with_a_tactic_flip": len(prompts_unstable),
        "fraction_of_prompts_with_a_tactic_flip": (
            round(len(prompts_unstable) / len(prompts_deep), 4) if prompts_deep else None
        ),
        "detection_caveat": (
            "this is a LOWER bound on the unstable-prompt fraction: at k repeats a prompt that "
            "flips with probability q is missed with probability (1-q)^k, so a 5%-flip prompt "
            "survives 10 repeats undetected 60% of the time"
        ),
    }

    # Noise enters a paired design as extra SYMMETRIC discordance: a truly concordant pair is
    # made to look discordant when exactly one of its two arms flips.  Symmetric noise does not
    # bias delta-hat; it dilutes power by adding discordant pairs that split 50/50.
    def noise_discordance(per_cell_error: float) -> float:
        return 2.0 * per_cell_error * (1.0 - per_cell_error)

    def majority_error(q: float, k: int) -> float:
        """Error of a majority vote over ``k`` independent draws with per-draw error ``q``."""

        need = k // 2 + 1
        return sum(math.comb(k, j) * q**j * (1 - q) ** (k - j) for j in range(need, k + 1))

    ks = {}
    for k in (1, 3, 5):
        err = q_tactic if k == 1 else majority_error(q_tactic, k)
        psi_noise = noise_discordance(err)
        ks[f"k={k}"] = {
            "per_cell_error_after_vote": round(err, 6),
            "spurious_discordance_added": round(psi_noise, 6),
            "anchors_for_80pct_power": {
                f"true_discordance={psi:.2f}": required_pairs(psi + psi_noise, args.delta)
                for psi in (0.15, 0.25, 0.35)
            },
            "solver_calls_per_arm": None,
        }
    for k in (1, 3, 5):
        row = ks[f"k={k}"]
        anchors = row["anchors_for_80pct_power"]["true_discordance=0.25"]
        row["solver_calls_per_arm"] = None if anchors is None else anchors * k
    design["replicates"] = ks
    design["anchors_needed_at_80pct_power_noise_free"] = {
        f"discordance={psi:.2f}": required_pairs(psi, args.delta)
        for psi in (0.15, 0.25, 0.35, 0.50)
    }
    design["replicate_note"] = (
        "k buys down a symmetric, unbiased per-cell error. Because the error is symmetric it "
        "cannot move delta-hat, only dilute power, and the dilution it causes is far smaller "
        "than the power the same call budget buys as extra anchors. k does NOT address the one "
        "failure mode that would invalidate the design -- a systematic difference in call "
        "ORDER or server state between the two arms, which is a bias and must be removed by "
        "interleaving the arms, not by replication."
    )

    report = {
        "schema": "hc-v0.6-noise-analysis-v0",
        "rows_analysed": len(rows),
        "files": sorted({str(row["_file"]) for row in rows}),
        "cost": cost,
        "cost_overall": {
            "calls": len(all_seconds),
            "seconds_per_call_median": round(statistics.median(all_seconds), 3),
            "seconds_per_call_mean": round(statistics.fmean(all_seconds), 3),
            "seconds_total_in_calls": round(sum(all_seconds), 1),
        },
        "stability_by_arm": dict(sorted(by_arm.items())),
        "frozen_configuration": frozen_summary,
        "design": design,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
