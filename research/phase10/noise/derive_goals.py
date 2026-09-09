"""Derive fresh real Lean goal states for the noise measurement.  No Solver call is made here.

This is the *preferred* prompt source: states produced by a live Lean REPL in this session, not
replayed from an artefact.  It opens one session per task and closes it, so it is polite to a
concurrently running Lean agent, and it is skippable -- :func:`common.load_corpus` falls back to
the HC-V0.5 recorded states, whose prompts are verified byte-exact against the recorded
``prompt_sha256`` values.

Run::

    .venv/bin/python -m research.phase10.noise.derive_goals --tasks 6 --seed 20260909
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from research.phase10.noise.common import OUT_DIR, build_prompt, sha256


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260909)
    parser.add_argument("--scan-limit", type=int, default=12000)
    parser.add_argument("--out", type=Path, default=OUT_DIR / "fresh_goals.json")
    args = parser.parse_args(argv)

    from arena.trajectory.task import select_verified_tasks

    started = time.time()
    selection = select_verified_tasks(
        limit=int(args.tasks), seed=int(args.seed), scan_limit=int(args.scan_limit)
    )
    goals: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for task in selection.tasks:
        try:
            projection = task.reset()
            text = str(projection.rendered.get("goals_pp", ""))
            if text.strip():
                goals.append(
                    {
                        "state_id": str(getattr(task, "task_id", "")) + "#reset",
                        "problem_id": str(getattr(task, "task_id", "")),
                        "goals_pp": text,
                        "n_goals": int(projection.rendered.get("n_goals", 1) or 1),
                        "prompt_sha256": sha256(build_prompt(text)),
                        "prompt_chars": len(build_prompt(text)),
                    }
                )
        except Exception as error:  # a Lean failure is an outcome, not a crash
            errors.append({"task": str(getattr(task, "task_id", "?")), "error": repr(error)})
        finally:
            with contextlib.suppress(Exception):  # closing a dead session is not a finding
                task.close()

    payload = {
        "schema": "hc-v0.6-noise-fresh-goals-v0",
        "selection": selection.manifest(),
        "goals": goals,
        "errors": errors,
        "wall_seconds": round(time.time() - started, 3),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps({"goals": len(goals), "errors": len(errors), "seconds": payload["wall_seconds"]})
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
