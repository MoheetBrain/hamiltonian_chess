"""Wiring smoke test: does each installed model answer at all under the frozen conditions?

HC-V0.5 measured a silent failure mode -- with ``think`` unset the Solver's ``response`` came back
empty and every proposal became a ``PARSE_FAILURE``, so the model looked incapable when it was
misconfigured.  ``WIRE_FLAGS`` sets ``think=False`` for every model, but a model that does not
support that flag, or whose chat renderer differs, could fail in an equally silent way.

This runs the repository's own :func:`arena.trajectory.solver.live_smoke` against each model,
sequentially, on the hand-written goals that are not drawn from the bank.  It makes a claim about
*wiring*, never about capability.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from arena.trajectory.solver import SMOKE_GOALS, live_smoke, solver_for

OUT = Path("research/phase10/models/out/smoke.json")


def smoke_one(model: str) -> dict[str, Any]:
    started = time.monotonic()
    try:
        solver = solver_for(model)
    except Exception as error:  # a model the runtime will not describe is an outcome
        return {
            "model": model,
            "wiring": "SOLVER_CONSTRUCTION_FAILED",
            "error": f"{type(error).__name__}: {error}"[:400],
            "wall_clock_s": round(time.monotonic() - started, 1),
        }
    rows = live_smoke(SMOKE_GOALS, solver=solver)
    statuses = [str(row["status"]) for row in rows]
    return {
        "model": model,
        "solver_digest": solver.identity.digest,
        "model_digest": solver.identity.model_digest,
        "wall_clock_s": round(time.monotonic() - started, 1),
        "statuses": statuses,
        "ok": statuses.count("OK"),
        "n": len(rows),
        "rows": [
            {
                "state_id": row.get("state_id"),
                "status": row.get("status"),
                "tactic": row.get("tactic"),
                "raw_output": (row.get("raw_output") or "")[:300],
                "thinking_chars": len(row.get("thinking") or ""),
                "done_reason": row.get("done_reason"),
                "prompt_tokens": row.get("prompt_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "latency_ms": row.get("latency_ms"),
                "failure_detail": (row.get("failure_detail") or "")[:400],
            }
            for row in rows
        ],
    }


def main(argv: list[str]) -> int:
    models = argv[1:]
    if not models:
        inventory = json.loads(Path("research/phase10/models/out/inventory.json").read_text())
        models = [m["name"] for m in inventory["models"]]
    results = []
    for model in models:
        print(f"--- smoke {model}", flush=True)
        result = smoke_one(model)
        print(
            f"    {result.get('wiring', 'RAN')} ok={result.get('ok')}/{result.get('n')} "
            f"{result['wall_clock_s']}s statuses={result.get('statuses')}",
            flush=True,
        )
        results.append(result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
