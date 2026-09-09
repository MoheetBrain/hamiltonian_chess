"""HC-V0.6 baseline preflight: every installed model, ``R_A`` only, identical frozen conditions.

This is **model-eligibility calibration**, not a representation comparison.  Exactly one arm is
played (``Arm.R_A``), so no Δ between renderings exists in this artefact and none can be computed
from it.

Everything except the served weights is held fixed by construction, because it comes from module
constants rather than from this script: the prompt template, the output grammar, the decoding
options, the wire flags and ``num_ctx`` all live in :mod:`arena.trajectory.solver`, and the
anchors come from the same seeded sample of the same frozen bank for every model.

The runner is the repository's own :func:`arena.experiments.hc_v0_6_assay.run_assay`; this module
only chooses the model, checks the served digest against the recorded inventory, and reduces the
resulting :class:`~arena.experiments.hc_v0_6.schema.CellTable` to the reported counts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from arena.experiments.hc_v0_6.schema import Arm, CellTable, ParseStatus, StepResult
from arena.experiments.hc_v0_6_assay import build_manifest, run_assay
from arena.trajectory.anchor import AnchorBank
from arena.trajectory.solver import solver_for

BANK_PATH = Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
INVENTORY_PATH = Path("research/phase10/models/out/inventory.json")
OUT_DIR = Path("research/phase10/models/out")
ARTIFACT_DIR = Path("artifacts/trajectory")

#: Frozen for every model.  ``theorem_sample_seed`` makes the sample a seeded, domain-spread draw
#: of theorem groups rather than an alphabetical slice of mathlib, and the SAME seed is used for
#: every model so every model is asked the same questions.
SEED = 20260909
THEOREM_LIMIT = 15
THEOREM_SAMPLE_SEED = 20260909
ARMS = (Arm.R_A,)
REPLICATES = 1


class ServedDigestMismatch(RuntimeError):
    """The runtime is serving a different blob than the inventory recorded.  Never downgraded."""


def _slug(model: str) -> str:
    return model.replace(":", "_").replace("/", "_").replace(".", "_")


def summarise(table: CellTable, wall_clock_s: float) -> dict[str, Any]:
    """Reduce a one-arm cell table to the reported preflight numbers."""

    rows = list(table)
    steps = Counter(str(row.step_result.value) for row in rows)
    parses = Counter(str(row.parse_status.value) for row in rows)
    latencies = [row.latency_ms for row in rows]
    prompt_tokens = [row.prompt_tokens for row in rows]
    response_tokens = [row.response_tokens for row in rows]

    analysable = [row for row in rows if row.analysable]
    events = sum(1 for row in analysable if row.accepted)
    n = len(analysable)
    p_hat = events / n if n else None
    median_ms = statistics.median(latencies) if latencies else None
    median_s = (median_ms / 1000.0) if median_ms else None
    return {
        "cells": len(rows),
        "analysable_cells": n,
        "endpoint": "KERNEL_ACCEPTED_STATE_CHANGE",
        "events": events,
        "p_hat": round(p_hat, 6) if p_hat is not None else None,
        "accepted_no_op": steps.get(str(StepResult.ACCEPTED_NO_OP.value), 0),
        "rejected_invalid_action": steps.get(str(StepResult.REJECTED_INVALID_ACTION.value), 0),
        "parse_failure_cells": steps.get(str(StepResult.PARSE_FAILURE.value), 0),
        "environment_errors": steps.get(str(StepResult.ENVIRONMENT_ERROR.value), 0),
        "tool_timeouts": steps.get(str(StepResult.TOOL_TIMEOUT.value), 0),
        "unsupported": steps.get(str(StepResult.UNSUPPORTED.value), 0),
        "step_results": dict(sorted(steps.items())),
        "parse_statuses": dict(sorted(parses.items())),
        "parse_failure_rate": (
            round(
                (len(rows) - parses.get(str(ParseStatus.OK.value), 0)) / len(rows),
                6,
            )
            if rows
            else None
        ),
        "median_latency_ms": median_ms,
        "mean_latency_ms": round(statistics.fmean(latencies), 1) if latencies else None,
        "median_call_seconds": round(median_s, 3) if median_s else None,
        "median_prompt_tokens": statistics.median(prompt_tokens) if prompt_tokens else None,
        "median_response_tokens": statistics.median(response_tokens) if response_tokens else None,
        "mean_prompt_tokens": round(statistics.fmean(prompt_tokens), 1) if prompt_tokens else None,
        "mean_response_tokens": (
            round(statistics.fmean(response_tokens), 1) if response_tokens else None
        ),
        "information_rate": (
            round(p_hat * (1 - p_hat) / median_s, 6) if (p_hat is not None and median_s) else None
        ),
        "information_rate_note": (
            "p_hat*(1-p_hat)/median_call_seconds. A VARIANCE-PER-SECOND heuristic only: it says "
            "how much binary-outcome variance a model produces per second of wall clock, which is "
            "what a paired assay's power per unit compute scales with. It does NOT capture "
            "capability (it is maximised at p=0.5, so a better model can score lower), pairing, "
            "clustering, between-anchor correlation, the effect size under test, Lean's cost, or "
            "model load/reload cost. It is not a decision rule."
        ),
        "wall_clock_s": round(wall_clock_s, 1),
    }


def run_one(model: str, bank: AnchorBank, inventory: dict[str, Any]) -> dict[str, Any]:
    recorded = {m["name"]: m["digest"] for m in inventory["models"]}
    solver = solver_for(model)
    served = solver.identity.model_digest
    if model in recorded and served != recorded[model]:
        raise ServedDigestMismatch(
            f"{model}: /api/tags now serves digest {served}, the inventory recorded "
            f"{recorded[model]}. Refusing to run."
        )

    started = time.monotonic()
    run = run_assay(
        bank,
        solver,
        arms=ARMS,
        replicates=REPLICATES,
        seed=SEED,
        theorem_limit=THEOREM_LIMIT,
        theorem_sample_seed=THEOREM_SAMPLE_SEED,
    )
    wall = time.monotonic() - started

    manifest = build_manifest(
        run, bank=bank, solver=solver, arms=ARMS, replicates=REPLICATES, seed=SEED
    )
    table = run.table
    manifest["preflight"] = {
        "purpose": (
            "MODEL ELIGIBILITY CALIBRATION ONLY. One arm (R_A) was played; this artefact contains "
            "no comparison between representations and none can be derived from it."
        ),
        "model": model,
        "model_digest": served,
        "theorem_limit": THEOREM_LIMIT,
        "theorem_sample_seed": THEOREM_SAMPLE_SEED,
        **summarise(table, wall),
    }
    manifest["cell_table"] = table.to_dict()

    out = ARTIFACT_DIR / f"hc_v0_6_preflight_{_slug(model)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"    wrote {out}", flush=True)
    return manifest["preflight"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="*", help="model names; default = every inventoried model")
    args = parser.parse_args()

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    models = args.models or [m["name"] for m in inventory["models"]]
    bank = AnchorBank.load(BANK_PATH)
    print(
        f"bank {bank.content_hash} anchors={bank.stats.anchors} "
        f"theorems={bank.stats.distinct_theorems} files={bank.stats.distinct_files}",
        flush=True,
    )

    summaries: list[dict[str, Any]] = []
    for model in models:
        print(f"=== preflight {model}", flush=True)
        summaries.append(run_one(model, bank, inventory))
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "preflight_summary.json").write_text(
            json.dumps(
                {
                    "schema": "hc-v0.6-model-preflight-summary-v1",
                    "arms": [str(a.value) for a in ARMS],
                    "replicates": REPLICATES,
                    "seed": SEED,
                    "theorem_limit": THEOREM_LIMIT,
                    "theorem_sample_seed": THEOREM_SAMPLE_SEED,
                    "evaluation_universe_hash": bank.content_hash,
                    "models": summaries,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
