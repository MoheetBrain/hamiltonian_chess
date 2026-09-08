"""Is the Lean environment a GAME or only a replay?

HC-V0.5's premise is that a Solver may propose an action that is **not** the reference proof
action and have Lean adjudicate it. If the REPL only ever accepted the recorded tactic, the
environment would be an imitation harness and `VerifiedTask` could not be interactive.

This probe answers that question directly, with zero model calls: for each of N theorems it takes
the root state and offers a list of generic tactics that are **not** in that theorem's reference
proof, and records whether Lean accepts any of them.

Run:  .venv/bin/python -m research.phase9.interactive_probe.probe_non_reference_actions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arena.trajectory import lean_backend as lb

TRAIN = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4/random/train.json"
)
#: Generic closers/advancers. None is theorem-specific and none is read from the reference proof.
ALTS = (
    "simp",
    "omega",
    "aesop",
    "norm_num",
    "rfl",
    "decide",
    "tauto",
    "linarith",
    "exact rfl",
    "simp_all",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probes", type=int, default=14)
    parser.add_argument("--scan-limit", type=int, default=20000)
    parser.add_argument("--train-json", type=Path, default=TRAIN)
    parser.add_argument(
        "--out", type=Path, default=Path("research/phase9/interactive_probe/result.json")
    )
    args = parser.parse_args(argv)

    lb.assert_not_sealed(args.train_json)
    config = lb.LeanToolchainConfig.from_env()
    report = lb.check_toolchain(config)

    probes = []
    for record in lb.iter_leandojo_records(args.train_json, limit=args.scan_limit):
        traced = record.get("traced_tactics") or []
        if not 1 <= len(traced) <= 3:
            continue
        built = lb.build_probe(
            record,
            mathlib_root=config.mathlib_root,
            min_reference_horizon=1,
            max_reference_horizon=3,
        )
        if built.probe is not None:
            probes.append(built.probe)
        if len(probes) >= args.probes:
            break

    rows: list[dict[str, Any]] = []
    for probe in probes:
        reference = list(probe.reference_tactics)
        row: dict[str, Any] = {
            "problem_id": probe.problem_id,
            "full_name": probe.full_name,
            "reference_tactics": reference,
            "accepted_alternative": None,
            "closed_goal": None,
            "rejections": [],
        }
        try:
            with lb.LeanReplSession(
                probe, config=config, policy=lb.TacticPolicy.record_only()
            ) as s:
                root = s.root_state_id
                for alt in ALTS:
                    if alt in reference:
                        continue  # must be NON-reference to count
                    result = s.step(root, alt)
                    if result.outcome is lb.StepOutcome.OK:
                        row["accepted_alternative"] = alt
                        row["closed_goal"] = lb.is_no_goals(result.tactic_state or "")
                        break
                    row["rejections"].append({"tactic": alt, "outcome": str(result.outcome)})
        except Exception as error:  # pragma: no cover - live backend
            row["session_error"] = f"{type(error).__name__}: {error}"
        rows.append(row)

    accepted = [r for r in rows if r["accepted_alternative"]]
    closed = [r for r in accepted if r["closed_goal"]]
    payload = {
        "probe": "non-reference-action-acceptance-v1",
        "question": "will Lean accept an action that is not the reference proof action?",
        "toolchain": {
            "lean_version_string": report.lean_version_string,
            "mathlib_root": str(config.mathlib_root),
        },
        "alternatives_offered": list(ALTS),
        "probes": len(rows),
        "accepted_non_reference": len(accepted),
        "closed_by_non_reference": len(closed),
        "verdict": ("INTERACTIVE_GAME" if accepted else "NO_ALTERNATIVE_ACCEPTED_IN_SAMPLE"),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(
        f"{len(accepted)}/{len(rows)} probes accepted a NON-reference tactic; "
        f"{len(closed)} were closed outright. verdict={payload['verdict']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
