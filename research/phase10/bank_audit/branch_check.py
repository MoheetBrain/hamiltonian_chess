"""Does branching still hold on the REBUILT anchor bank, through the API the assay drives?

``research/phase10/branching/probe_branching.py`` established the property on freshly selected
theorems using ``LeanReplSession`` directly.  HC-V0.6's assay does not do that: it opens
``arena.trajectory.anchor.open_anchor_session`` on one theorem's anchors and calls
``LiveAnchorSet.step(anchor_id, tactic)`` once per arm at the same anchored state.  This re-runs
the decisive checks through *that* path, on theorems drawn from the committed bank:

* two SUCCESSFUL steps from one anchored live state give **distinct** child state ids,
* the parent's state text is unchanged after both branches,
* the first child's text is unchanged after the second branch was taken from the parent, and
* a **mid-proof** anchor branches as well as an initial one.

A third branch uses the anchor's own next recorded tactic, so at least one branch is a real
proof step rather than ``skip``.  That is oracle-side infrastructure verification: no Solver is
involved, nothing is scored, and the tactic is never rendered into a prompt.

Run:  .venv/bin/python -m research.phase10.bank_audit.branch_check --theorems 15
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any

from arena.trajectory.anchor import Anchor, AnchorBank, open_anchor_session

DEFAULT_BANK = Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
DEFAULT_OUT = Path("research/phase10/bank_audit/out/branching.json")

#: The one tactic that succeeds on any open goal without changing it, so a difference in the
#: child state id is the session's doing and nothing else's.
NEUTRAL = "skip"


def branch_at(live: Any, anchor: Anchor) -> dict[str, Any]:
    """Take three branches from one anchored state and report what the session did."""

    item = live.by_id(anchor.anchor_id)
    parent = item.live_state_id
    parent_before = live.session.state_text(parent)

    first = live.step(anchor.anchor_id, NEUTRAL)
    child_one_after_first = (
        live.session.state_text(first.to_state_id) if first.to_state_id else None
    )
    second = live.step(anchor.anchor_id, NEUTRAL)
    child_one_after_second = (
        live.session.state_text(first.to_state_id) if first.to_state_id else None
    )

    gold = anchor.oracle.remaining_reference
    third = live.step(anchor.anchor_id, gold[0]) if gold else None
    parent_after = live.session.state_text(parent)

    both_ok = bool(first.ok and second.ok)
    return {
        "anchor_id": anchor.anchor_id,
        "depth_class": anchor.sampling.depth_class.value,
        "prefix_length": anchor.sampling.prefix_length,
        "rederived_matched": item.matched,
        "parent_state_id": parent,
        "neutral_1": {
            "ok": first.ok,
            "to": first.to_state_id,
            "error": str(first.error or "")[:120],
        },
        "neutral_2": {
            "ok": second.ok,
            "to": second.to_state_id,
            "error": str(second.error or "")[:120],
        },
        "reference_branch": (
            None
            if third is None
            else {"ok": third.ok, "to": third.to_state_id, "error": str(third.error or "")[:120]}
        ),
        "two_successful_branches": both_ok,
        "children_distinct": both_ok and first.to_state_id != second.to_state_id,
        "parent_text_unchanged": parent_before == parent_after,
        "first_child_text_unchanged": child_one_after_first == child_one_after_second,
        "third_branch_succeeded": bool(third is not None and third.ok),
        "third_child_distinct": bool(
            third is not None
            and third.ok
            and third.to_state_id not in {first.to_state_id, second.to_state_id, parent}
        ),
    }


def sample_theorems(bank: AnchorBank, *, limit: int, seed: int) -> list[list[Anchor]]:
    """Theorems that carry BOTH an initial and a mid-proof anchor, sampled deterministically."""

    by_theorem = bank.by_theorem()
    eligible = [
        problem_id
        for problem_id, anchors in by_theorem.items()
        if any(anchor.sampling.prefix_length == 0 for anchor in anchors)
        and any(anchor.sampling.prefix_length > 0 for anchor in anchors)
    ]
    rng = random.Random(seed)
    chosen = rng.sample(sorted(eligible), k=min(limit, len(eligible)))
    return [list(by_theorem[problem_id]) for problem_id in chosen]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--theorems", type=int, default=15)
    parser.add_argument("--seed", type=int, default=20260909)
    args = parser.parse_args(argv)

    bank = AnchorBank.load(args.bank)
    groups = sample_theorems(bank, limit=args.theorems, seed=args.seed)
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    for group in groups:
        entry: dict[str, Any] = {"problem_id": group[0].oracle.problem_id, "branches": []}
        try:
            with open_anchor_session(group) as live:
                entry["anchors_rederived"] = len(live.live)
                entry["anchors_matched"] = len(live.matched)
                entry["missing"] = [list(item) for item in live.missing]
                initial = [item for item in live.matched if item.anchor.sampling.prefix_length == 0]
                mid = sorted(
                    (item for item in live.matched if item.anchor.sampling.prefix_length > 0),
                    key=lambda item: item.anchor.sampling.prefix_length,
                    reverse=True,
                )
                for item in initial[:1] + mid[:1]:
                    entry["branches"].append(branch_at(live, item.anchor))
        except Exception as error:  # noqa: BLE001 -- reported, never silently dropped
            entry["error"] = f"{type(error).__name__}: {error}"[:300]
        results.append(entry)
        print(json.dumps(entry, ensure_ascii=False))

    branches = [branch for entry in results for branch in entry.get("branches", ())]
    summary = {
        "bank": str(args.bank),
        "content_hash": bank.content_hash,
        "seed": args.seed,
        "theorems_requested": args.theorems,
        "theorems_opened": sum(1 for entry in results if "error" not in entry),
        "theorems_errored": [entry for entry in results if "error" in entry],
        "anchored_states_branched": len(branches),
        "initial_states_branched": sum(1 for b in branches if b["prefix_length"] == 0),
        "mid_proof_states_branched": sum(1 for b in branches if b["prefix_length"] > 0),
        "two_successful_branches": sum(1 for b in branches if b["two_successful_branches"]),
        "children_distinct": sum(1 for b in branches if b["children_distinct"]),
        "parent_text_unchanged": sum(1 for b in branches if b["parent_text_unchanged"]),
        "first_child_text_unchanged": sum(1 for b in branches if b["first_child_text_unchanged"]),
        "reference_branch_succeeded": sum(1 for b in branches if b["third_branch_succeeded"]),
        "reference_child_distinct": sum(1 for b in branches if b["third_child_distinct"]),
        "rederived_matched": sum(1 for b in branches if b["rederived_matched"]),
        "wall_s": round(time.monotonic() - started, 2),
        "detail": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "detail"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
