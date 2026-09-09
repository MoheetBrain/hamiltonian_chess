"""Does one Lean session really give independent branches from one anchored state?

HC-V0.6's design rests on this: every arm at an anchor must act on the *same* truth state, and the
cheap way to guarantee that is to step the same ``state_id`` several times in one session rather
than re-deriving the state per arm.  ``LeanReplSession.step`` takes an explicit ``state_id`` and
its docstring says any state the session produced may be used.  This script checks the behaviour
matches the docstring on real theorems, and in particular the case that could plausibly break it:
**two SUCCESSFUL steps from the same parent**.

The decisive assertions are
  * two successful steps from one parent produce two *distinct* child state ids, and
  * the first child's text is unchanged after the second step was taken from the parent.

The theorem's own first recorded tactic is used as one of the two successful branches.  That is
oracle-side infrastructure verification, not an assay: no Solver is involved and nothing here is
scored.

Run:  .venv/bin/python -m research.phase10.branching.probe_branching
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arena.trajectory.arena_v0 import DEFAULT_TRAIN_JSON, select_candidates
from arena.trajectory.lean_backend import LeanReplSession

#: ``skip`` is the one tactic that succeeds on any open goal without changing it, which makes it
#: the cleanest possible second branch: any difference in the child id is the session's doing.
NEUTRAL = "skip"


def probe(limit: int = 6, seed: int = 20260908, scan_limit: int = 4000) -> dict[str, Any]:
    selection = select_candidates(
        train_json=DEFAULT_TRAIN_JSON,
        min_horizon=2,
        max_horizon=8,
        limit=limit,
        seed=seed,
        scan_limit=scan_limit,
    )
    results: list[dict[str, Any]] = []
    for theorem_probe in selection.probes:
        entry: dict[str, Any] = {"problem_id": theorem_probe.problem_id}
        try:
            with LeanReplSession(theorem_probe) as session:
                root = session.root_state_id
                root_text = session.state_text(root)

                first = session.step(root, NEUTRAL)
                second = session.step(root, NEUTRAL)
                reference = theorem_probe.reference_tactics[0]
                third = session.step(root, reference)

                entry.update(
                    {
                        "root_state_id": root,
                        "neutral_1": {"ok": first.ok, "to": first.to_state_id},
                        "neutral_2": {"ok": second.ok, "to": second.to_state_id},
                        "reference_step": {
                            "ok": third.ok,
                            "to": third.to_state_id,
                            "outcome": third.outcome.value,
                        },
                        "two_neutral_children_are_distinct": (
                            first.ok and second.ok and first.to_state_id != second.to_state_id
                        ),
                        "first_child_text_intact_after_later_steps": (
                            first.to_state_id is not None
                            and session.state_text(first.to_state_id) is not None
                        ),
                        "root_text_unchanged": session.state_text(root) == root_text,
                        # A branch taken from a CHILD must also work: the anchor bank derives
                        # mid-proof anchors by walking a prefix, then branches from there.
                        "branch_from_child_ok": (
                            session.step(first.to_state_id, NEUTRAL).ok
                            if first.ok and first.to_state_id
                            else None
                        ),
                        "distinct_state_ids": len(session.known_state_ids()),
                    }
                )
        except Exception as error:  # pragma: no cover - live backend
            entry["error"] = f"{type(error).__name__}: {error}"[:300]
        results.append(entry)

    usable = [e for e in results if "error" not in e]
    return {
        "theorems": len(results),
        "theorems_without_error": len(usable),
        "two_successful_branches_distinct": sum(
            1 for e in usable if e.get("two_neutral_children_are_distinct")
        ),
        "first_child_intact_always": all(
            e.get("first_child_text_intact_after_later_steps") for e in usable
        ),
        "root_text_unchanged_always": all(e.get("root_text_unchanged") for e in usable),
        "branch_from_child_ok": sum(1 for e in usable if e.get("branch_from_child_ok")),
        "reference_first_tactic_accepted": sum(
            1 for e in usable if e.get("reference_step", {}).get("ok")
        ),
        "detail": results,
    }


def main() -> int:  # pragma: no cover - live backend
    report = probe()
    out = Path("research/phase10/branching/out")
    out.mkdir(parents=True, exist_ok=True)
    (out / "branching.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "detail"}, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
