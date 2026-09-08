"""RED TEAM / attack class 4: oracle and answer leakage.

Two jobs.

1. INDEPENDENTLY RECOUNT the builder's claim.  `artifacts/trajectory_bank_v0/{h5,h12}/manifest.json`
   report `leaking_steps` 7 and 9 and `problems_dropped` 6 and 8.  This re-derives those numbers
   from `random/train.json` with an implementation written here, not by calling `LeakageFilter`.

2. ATTACK THE CHANNELS THE FILTER DOES NOT CHECK.  `LeakageFilter` has exactly two criteria, both
   applied to the RECORDED LeanDojo `state_before`.  The observation a Solver actually receives is
   the LIVE REPL pretty-print, which the project's own audit measured as differing from the
   recorded text 40.6% of the time.  The runtime tripwire (`assert_observation_clean`) checks only
   *remaining reference tactics* and only those of length >= 6.

   This measures, on the COMMITTED bank, how often a not-yet-played reference tactic is already
   visible in the live state the Solver would be shown.

Run:  .venv/bin/python research/phase9/redteam/attack_leakage.py
Out:  research/phase9/redteam/out/leakage.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.trajectory.arena_v0 import (  # noqa: E402
    AnswerLeakageError,
    BackendNativeRenderer,
    GoalTextRenderer,
    LeakageFilter,
)
from arena.trajectory.lean_backend import DEFAULT_MATHLIB_ROOT, iter_leandojo_records  # noqa: E402
from arena.trajectory.schema import BackendStateEnvelope, PPScope  # noqa: E402

TRAIN = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4/random/train.json"
)
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


def independent_recount(scan_limit: int, min_horizon: int) -> dict[str, Any]:
    """Re-derive the manifest's leakage numbers WITHOUT calling LeakageFilter."""

    scanned = below = problems_scanned = steps_scanned = 0
    leaking_steps = problems_dropped = 0
    reasons: dict[str, int] = {}
    tactic_only = name_only = both = 0
    for record in iter_leandojo_records(TRAIN, limit=scan_limit):
        scanned += 1
        tactics = record.get("traced_tactics") or []
        if len(tactics) < min_horizon:
            below += 1
            continue
        problems_scanned += 1
        steps_scanned += len(tactics)
        full_name = str(record.get("full_name", ""))
        hits: list[str] = []
        for step in tactics:
            before = str(step.get("state_before", ""))
            tac = str(step.get("tactic", ""))
            if tac and tac in before:
                hits.append("TACTIC_IN_STATE_BEFORE")
            if full_name and full_name in before:
                hits.append("FULL_NAME_IN_STATE")
        if hits:
            problems_dropped += 1
            leaking_steps += len(hits)
            for reason in hits:
                reasons[reason] = reasons.get(reason, 0) + 1
            kinds = set(hits)
            if kinds == {"TACTIC_IN_STATE_BEFORE"}:
                tactic_only += 1
            elif kinds == {"FULL_NAME_IN_STATE"}:
                name_only += 1
            else:
                both += 1
    return {
        "records_scanned": scanned,
        "below_min_horizon": below,
        "problems_scanned": problems_scanned,
        "steps_scanned": steps_scanned,
        "leaking_steps": leaking_steps,
        "problems_dropped": problems_dropped,
        "reasons": reasons,
        "dropped_by_kind": {"tactic_only": tactic_only, "name_only": name_only, "both": both},
    }


def live_state_leakage(bank_dir: Path) -> dict[str, Any]:
    """On the COMMITTED bank: is a not-yet-played reference tactic visible in the live state?

    This is the channel the record-level filter cannot see, because it scanned the RECORDED
    LeanDojo `state_before`, not the live REPL pp that the arena actually renders.
    """

    filt = LeakageFilter()
    renderer = BackendNativeRenderer()
    total_steps = 0
    leaks_any_len: list[dict[str, Any]] = []
    leaks_tripwire_would_catch = 0
    leaks_below_tripwire_len = 0
    trajectories = 0
    for line in (bank_dir / "bank.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        trajectories += 1
        tactics = [a["tactic"] for a in row["actions"]]
        for index, state in enumerate(row["states"]):
            remaining = tactics[index:]
            if not remaining:
                continue
            total_steps += 1
            envelope = BackendStateEnvelope(
                index=state["index"],
                state_id=state["state_id"],
                pp=state["backend_native"]["pp"],
                pp_scope=PPScope.from_dict(state["backend_native"]["pp_scope"]),
                n_goals=state["backend_native"]["n_goals"],
            )
            rendered = renderer.render(envelope)
            payload = json.dumps(rendered, ensure_ascii=False)
            for tactic in remaining:
                candidate = tactic.strip()
                if candidate and candidate in payload:
                    entry = {
                        "problem_id": row["problem_id"],
                        "state_index": index,
                        "leaked_tactic": candidate,
                        "len": len(candidate),
                        "tripwire_len_threshold": filt.min_runtime_secret_len,
                        "tripwire_fires": len(candidate) >= filt.min_runtime_secret_len,
                    }
                    leaks_any_len.append(entry)
                    if entry["tripwire_fires"]:
                        leaks_tripwire_would_catch += 1
                    else:
                        leaks_below_tripwire_len += 1
    return {
        "trajectories": trajectories,
        "non_terminal_states_scanned": total_steps,
        "live_state_leaks_total": len(leaks_any_len),
        "caught_by_runtime_tripwire": leaks_tripwire_would_catch,
        "BELOW_TRIPWIRE_LENGTH_UNCAUGHT": leaks_below_tripwire_len,
        "examples": leaks_any_len[:12],
    }


def channel_probes() -> dict[str, Any]:
    """Channels `assert_observation_clean` never inspects."""

    filt = LeakageFilter()
    results: dict[str, Any] = {}

    def check(name: str, pp: str, remaining: list[str], scope: PPScope | None = None) -> None:
        envelope = BackendStateEnvelope(index=0, state_id="0", pp=pp, pp_scope=scope or PPScope())
        for renderer_name, renderer in (
            ("backend-native-v0", BackendNativeRenderer()),
            ("goal-text-v0", GoalTextRenderer()),
        ):
            try:
                filt.assert_observation_clean(renderer.render(envelope), remaining)
                verdict = "PASSED (no leak reported)"
            except AnswerLeakageError as exc:
                verdict = f"BLOCKED: {exc}"
            results.setdefault(name, {})[renderer_name] = verdict

    # C1: a short remaining tactic sitting verbatim in the goal text
    check("C1_short_tactic_below_len_threshold", "h : p = q\n⊢ rfl = rfl", ["rfl"])
    check(
        "C1b_long_tactic_in_goal",
        "⊢ foo\n-- exact my_long_lemma_name",
        ["exact my_long_lemma_name"],
    )
    # C2: the theorem's own name in the live state (the record-level criterion, absent at runtime)
    check("C2_full_name_in_live_state", "⊢ MeasureTheory.weightedSMul_add_measure μ ν", [])
    # C3: pp_scope discloses the home namespace/opens of the theorem
    check(
        "C3_pp_scope_namespace_channel",
        "⊢ True",
        [],
        PPScope(current_namespace="MeasureTheory", open_declarations=("ENNReal", "Filter")),
    )
    # C4: a paraphrase of the remaining tactic (whitespace / alpha variation) defeats the
    #     substring test entirely
    check(
        "C4_whitespace_variant",
        "⊢ foo\nhint: exact  my_long_lemma_name",
        ["exact my_long_lemma_name"],
    )
    return results


def main() -> int:
    findings: dict[str, Any] = {}
    if TRAIN.is_file():
        findings["R1_independent_recount_h5"] = {
            "manifest_claim": {
                "leaking_steps": 7,
                "problems_dropped": 6,
                "reasons": {"TACTIC_IN_STATE_BEFORE": 7},
            },
            "recount": independent_recount(scan_limit=6000, min_horizon=5),
        }
        findings["R2_independent_recount_h12"] = {
            "manifest_claim": {
                "leaking_steps": 9,
                "problems_dropped": 8,
                "reasons": {"TACTIC_IN_STATE_BEFORE": 9},
            },
            "recount": independent_recount(scan_limit=12000, min_horizon=12),
        }
    else:
        findings["R1_independent_recount_h5"] = {"skipped": f"{TRAIN} not present"}

    for name in ("h5", "h12"):
        directory = ROOT / "artifacts" / "trajectory_bank_v0" / name
        findings[f"R3_live_state_leakage_{name}"] = live_state_leakage(directory)

    findings["R4_unchecked_channels"] = channel_probes()
    findings["R5_filter_source_of_truth"] = {
        "record_level_criteria": ["tactic in state_before", "full_name in state_before"],
        "record_level_object": "LeanDojo recorded state_before",
        "runtime_object": "live lean_dojo_repl pretty-print",
        "audit_measured_divergence": "40.6% of replayed successor states differ textually",
        "runtime_criteria": ["remaining reference tactic, verbatim, len >= 6"],
        "never_checked_at_runtime": [
            "full_name",
            "file_path",
            "premise names",
            "pp_scope.current_namespace / open_declarations",
            "state_after of any recorded step",
            "any non-verbatim paraphrase of a remaining tactic",
        ],
        "mathlib_root_used_for_probes": str(DEFAULT_MATHLIB_ROOT),
    }

    (OUT / "leakage.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:9000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
