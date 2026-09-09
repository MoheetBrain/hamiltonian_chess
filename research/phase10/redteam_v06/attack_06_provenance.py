"""A6 -- can a cell claim an outcome it did not earn?

Two halves.

**Forgery.**  Hand-written rows are pushed through ``CellOutcome`` / ``CellTable.from_dict`` to see
which lies the schema catches and which it accepts:
  F1 an event with a parse status that never reached Lean
  F2 ``closed_all_goals`` against a non-event step result
  F3 a stored ``kernel_accepted_state_change`` contradicting ``step_result``
  F4 an arm wearing another arm's ``renderer_id`` / ``intervention_class``
  F5 an ACCEPTED_TRANSITION with ``parse_status=OK`` and **no tactic at all**
  F6 an arbitrary ``solver_digest`` and ``prompt_sha256``
  F7 an R_B row whose ``prompt_sha256`` is R_A's -- i.e. a row claiming bytes it was not shown

**Re-derivation.**  ``prompt_sha256`` is a pure function of (bank goal text, arm renderer, frozen
template), so every cell's claimed prompt can be recomputed offline.  The table is built for all
four arms at all 1,127 anchors and, where the in-flight primary cell file exists, its rows are
checked against it.  Only ``anchor_id``, ``arm``, ``replicate_index``, ``renderer_id``,
``intervention_class`` and ``prompt_sha256`` are read from that file -- no outcome field.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import ROOT, emit, load_bank_dict  # noqa: E402

from arena.experiments.hc_v0_6.schema import CellOutcome  # noqa: E402
from arena.trajectory.representation import ARMS  # noqa: E402
from arena.trajectory.schema import BackendStateEnvelope, PPScope  # noqa: E402
from arena.trajectory.solver import _sha256, build_prompt  # noqa: E402

LIVE = ROOT / "artifacts" / "trajectory" / "hc_v0_6_primary_gemma4_e4b_cells.jsonl"
READ_FIELDS = (
    "anchor_id",
    "arm",
    "replicate_index",
    "renderer_id",
    "intervention_class",
    "prompt_sha256",
    "solver_digest",
)

BASE = {
    "anchor_id": "anchor:1",
    "cluster_id": "Mathlib/A.lean",
    "theorem": "t",
    "reelaboration_key": "K",
    "arm": "R_B",
    "renderer_id": "R_B",
    "intervention_class": "R_ONLY",
    "replicate_index": 0,
    "step_result": "ACCEPTED_TRANSITION",
    "parse_status": "OK",
    "closed_all_goals": False,
    "prompt_sha256": "0" * 64,
    "prompt_tokens": 10,
    "response_tokens": 5,
    "latency_ms": 1,
    "solver_digest": "d",
    "proposed_tactic": "simp",
}


def _try(name: str, row: dict[str, Any], results: dict[str, str]) -> None:
    try:
        CellOutcome.from_dict(row)
        results[name] = "ACCEPTED -- the forgery was not caught"
    except Exception as error:
        results[name] = f"REJECTED -- {type(error).__name__}: {str(error)[:140]}"


def main() -> int:
    results: dict[str, str] = {}
    _try("F1_event_without_reaching_lean", {**BASE, "parse_status": "PARSE_FAILURE"}, results)
    _try(
        "F2_closed_against_a_non_event",
        {**BASE, "step_result": "ACCEPTED_NO_OP", "closed_all_goals": True},
        results,
    )
    _try(
        "F3_stored_endpoint_contradicts_step_result",
        {**BASE, "step_result": "ACCEPTED_NO_OP", "kernel_accepted_state_change": True},
        results,
    )
    _try("F4_arm_wearing_another_arms_renderer", {**BASE, "renderer_id": "R_A"}, results)
    _try(
        "F4b_arm_wearing_another_arms_class",
        {**BASE, "intervention_class": "P_CHANGE"},
        results,
    )
    _try("F5_event_with_no_tactic", {**BASE, "proposed_tactic": None}, results)
    _try("F6_arbitrary_solver_digest", {**BASE, "solver_digest": "not-a-model"}, results)

    # --- re-derive every prompt hash from the frozen bank -------------------------------------
    bank = load_bank_dict()
    expected: dict[tuple[str, str], str] = {}
    for anchor in bank["anchors"]:
        visible = anchor["solver_visible"]
        env = BackendStateEnvelope(
            index=0,
            state_id="0",
            pp=visible["goals_pp"],
            backend_kind=visible["backend_kind"],
            pp_scope=PPScope.from_dict(visible["pp_scope"]),
            n_goals=int(visible["n_goals"]),
        )
        for arm_id, renderer in ARMS.items():
            prompt = build_prompt(str(renderer.render(env)["goals_pp"]))
            expected[(anchor["anchor_id"], arm_id)] = _sha256(prompt)

    collisions = len(expected) - len(set(expected.values()))
    per_anchor_arm_collisions = 0
    by_anchor: dict[str, set[str]] = {}
    for (anchor_id, _arm_id), digest in expected.items():
        by_anchor.setdefault(anchor_id, set()).add(digest)
    per_anchor_arm_collisions = sum(1 for v in by_anchor.values() if len(v) != len(ARMS))

    # F7: an R_B row carrying R_A's prompt hash is structurally legal
    sample_anchor = bank["anchors"][0]["anchor_id"]
    forged = {
        **BASE,
        "anchor_id": sample_anchor,
        "prompt_sha256": expected[(sample_anchor, "R_A")],
    }
    _try("F7_R_B_row_carrying_R_A_prompt_hash", forged, results)

    # --- check the in-flight cell file against the re-derived table ----------------------------
    live_report: dict[str, Any] = {"file_present": LIVE.exists()}
    if LIVE.exists():
        seen = 0
        mismatched: list[dict[str, str]] = []
        arms_seen: dict[str, int] = {}
        bad_class: list[str] = []
        with LIVE.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                raw = json.loads(line)
                row = {k: raw.get(k) for k in READ_FIELDS}
                seen += 1
                arms_seen[str(row["arm"])] = arms_seen.get(str(row["arm"]), 0) + 1
                key = (str(row["anchor_id"]), str(row["arm"]))
                want = expected.get(key)
                if want is None:
                    mismatched.append({"anchor": key[0], "arm": key[1], "why": "not in the bank"})
                elif want != row["prompt_sha256"]:
                    mismatched.append(
                        {"anchor": key[0], "arm": key[1], "why": "prompt hash is not this arm's"}
                    )
                declared = str(row["intervention_class"])
                if (row["arm"] == "R_ABLATED") != (declared == "P_CHANGE"):
                    bad_class.append(str(row["anchor_id"]))
        live_report.update(
            {
                "rows_read": seen,
                "fields_read": list(READ_FIELDS),
                "cells_by_arm": arms_seen,
                "prompt_hash_mismatches": len(mismatched),
                "prompt_hash_mismatch_examples": mismatched[:5],
                "intervention_class_mismatches": len(bad_class),
            }
        )

    accepted = [k for k, v in results.items() if v.startswith("ACCEPTED")]
    emit(
        "attack_06_provenance",
        {
            "attack": "A6 actor provenance: can a cell claim an outcome it did not earn?",
            "verdict": "BROKEN" if accepted else "HELD",
            "forgeries_accepted": accepted,
            "forgery_results": results,
            "prompt_hash_table": {
                "entries": len(expected),
                "global_hash_collisions": collisions,
                "anchors_where_two_arms_share_a_prompt_hash": per_anchor_arm_collisions,
            },
            "in_flight_cell_file": live_report,
            "note": (
                "prompt_sha256 is a pure function of (bank goal text, arm renderer, frozen "
                "template), so it CAN be re-derived offline -- but nothing in the pipeline does "
                "it, and CellOutcome accepts any 64-character string. The re-derivation above is "
                "the missing check, not an existing one."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
