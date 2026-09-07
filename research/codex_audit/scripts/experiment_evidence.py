#!/usr/bin/env python3
"""Reconstruct the Arena V0--V5 and Phase-6 evidence chain without model calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def artifact(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "exists": path.is_file(),
        "sha256": sha256(path) if path.is_file() else None,
        "git_tracked": bool(git(root, "ls-files", "--error-unmatch", relative))
        if path.is_file()
        else False,
    }


def ladder_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        mechanism: {
            "ladder": [
                {"level": row["level"], "positive_accuracy": row["positive_accuracy"]}
                for row in record["ladder"]
            ],
            "selected_level": record.get("selected_level"),
            "selection_verdict": record["selection"]["verdict"],
            "qualification_verdict": record["qualification"]["verdict"],
            "qualified": record["qualification"].get("qualified", False),
            "full_family_summary": {
                key: value
                for key, value in record.get("full_family_summary", {}).items()
                if key != "mechanisms"
            },
        }
        for mechanism, record in sorted(payload["mechanisms"].items())
    }


def cache_audit(payload: dict[str, Any]) -> dict[str, Any]:
    ladder = payload.get("ladder_rows", [])
    full = [
        row
        for mechanism in payload.get("mechanisms", {}).values()
        for row in mechanism.get("rows", [])
    ]
    identity_fields = ("model_digest", "runtime_hash", "genome_hash", "probe_hash", "prompt_hash")
    identities = {tuple(row.get(key) for key in identity_fields) for row in [*ladder, *full]}
    return {
        "ladder_row_occurrences": len(ladder),
        "ladder_cache_hits": sum(bool(row.get("cache_hit")) for row in ladder),
        "full_family_row_occurrences": len(full),
        "full_family_cache_hits": sum(bool(row.get("cache_hit")) for row in full),
        "all_row_occurrences": len(ladder) + len(full),
        "all_cache_hits": sum(bool(row.get("cache_hit")) for row in [*ladder, *full]),
        "unique_evaluation_identities": len(identities),
        "interpretation": (
            "Ladder hits predate the completed run and trigger the literal alternate-solver "
            "invalidation rule. Full-family ORIGINAL/COUNTERFACTUAL hits are deliberate reuse "
            "of ladder identities, so they are not independent calls."
        ),
    }


def fixed_cell_degeneracy(
    baseline: dict[str, Any], alternate: dict[str, Any], cells: tuple[tuple[str, int], ...]
) -> dict[str, Any]:
    positive = {"ORIGINAL", "COUNTERFACTUAL"}
    base_rows = baseline["ladder_rows"]
    alternate_rows = alternate["ladder_rows"]
    base_by_id = {row["probe_id"]: row for row in base_rows}
    alt_by_id = {row["probe_id"]: row for row in alternate_rows}
    paired: list[tuple[bool, bool]] = []
    cell_rows: list[dict[str, Any]] = []
    for mechanism, level in cells:
        rows = [
            row
            for row in base_rows
            if row["mechanism"] == mechanism
            and row["level"] == level
            and row["variant"] in positive
        ]
        modal = Counter(row["parsed_index"] for row in rows).most_common(1)[0][0]
        ids = [row["probe_id"] for row in rows]
        for probe_id in ids:
            paired.append(
                (
                    base_by_id[probe_id]["parsed_index"] == modal,
                    alt_by_id[probe_id]["parsed_index"] == modal,
                )
            )
        cell_rows.append(
            {
                "mechanism": mechanism,
                "level": level,
                "n": len(ids),
                "baseline_modal_index": modal,
                "baseline_modal_count": sum(base_by_id[i]["parsed_index"] == modal for i in ids),
                "alternate_modal_count": sum(alt_by_id[i]["parsed_index"] == modal for i in ids),
            }
        )
    b10 = sum(before and not after for before, after in paired)
    b01 = sum(not before and after for before, after in paired)
    discordant = b10 + b01
    tail = sum(math.comb(discordant, k) for k in range(min(b10, b01) + 1)) / (2**discordant)
    return {
        "cells": cell_rows,
        "n": len(paired),
        "baseline_modal_count": sum(before for before, _ in paired),
        "alternate_modal_count": sum(after for _, after in paired),
        "mcnemar_b10": b10,
        "mcnemar_b01": b01,
        "mcnemar_exact_two_sided_p": min(1.0, 2 * tail),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--qwen-phase6", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()

    v1_gate = load(root / "artifacts/experiments/fitness_v1/gate0.json")
    v2_decision = load(root / "artifacts/experiments/fitness_v2/experiment_decision.json")
    v3_dev = load(root / "artifacts/experiments/fitness_v3/development/result.json")
    v3_founders = load(root / "artifacts/experiments/fitness_v3/founders/result.json")
    v3_invalidity = load(root / "artifacts/experiments/fitness_v3/invalidity.json")
    v4 = load(root / "artifacts/experiments/fitness_v4/development/result.json")
    v4_forensics = load(root / "artifacts/reports/fitness-v4-forensics.json")
    v5 = load(root / "artifacts/experiments/fitness_v5/development/result.json")
    gemma_bare = load(
        root / "artifacts/experiments/fitness_v5/development/result-gemma4_12b-bare.json"
    )
    sprint = load(root / "artifacts/experiments/tier2_sprint/gpu_sprint_results.json")
    world = load(root / "artifacts/worlds/arena-world-v0-summary.json")

    qwen_payload = (
        load(args.qwen_phase6) if args.qwen_phase6 and args.qwen_phase6.is_file() else None
    )
    qwen_observation = None
    if qwen_payload is not None:
        qwen_cache = cache_audit(qwen_payload)
        qwen_observation = {
            "source_path": str(args.qwen_phase6.resolve()),
            "sha256": sha256(args.qwen_phase6),
            "git_tracked_at_audit_base": False,
            "evidence_tag": "VERIFIED_BY_ARTIFACT",
            "commit_status": "UNCOMMITTED_EXTERNAL_WORKTREE_OBSERVATION",
            "model": qwen_payload["model"],
            "prompt_condition": qwen_payload.get("prompt_condition"),
            "q0_rate": qwen_payload["q0"]["rate"],
            "instrument_qualified": qwen_payload["instrument_qualified"],
            "qualified_mechanisms": qwen_payload["qualified_mechanisms"],
            "mechanisms": ladder_summary(qwen_payload),
            "cache_audit": qwen_cache,
            "fixed_cell_degeneracy_vs_gemma_framed": fixed_cell_degeneracy(
                v5,
                qwen_payload,
                (
                    ("precondition_conjunction", 2),
                    ("precondition_conjunction", 3),
                    ("transitive_dependency", 3),
                ),
            ),
        }

    evidence = [
        {
            "stage": "V0",
            "classification": "INSTRUMENT_RESULT_ONLY",
            "sentinel": "ARENA_WORLD_V0_MATERIALIZED",
            "claim_boundary": "Deterministic canonical-world and verifier infrastructure; no representation claim.",
            "facts": world,
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [artifact(root, "artifacts/worlds/arena-world-v0.jsonl")],
        },
        {
            "stage": "V1",
            "classification": "INVALIDATED",
            "sentinel": v1_gate.get("sentinel", "MODEL_FITNESS_BENCHMARK_INVALID"),
            "claim_boundary": "The solver selected by option position; candidate scores are not fitness evidence.",
            "facts": {key: value for key, value in v1_gate.items() if key != "events"},
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [artifact(root, "artifacts/experiments/fitness_v1/gate0.json")],
        },
        {
            "stage": "V2",
            "classification": "INSTRUMENT_RESULT_ONLY",
            "sentinel": v2_decision.get("sentinel"),
            "claim_boundary": "The model/protocol qualified, but 0.125 control range missed the frozen 0.15 headroom gate; no candidate ranking.",
            "facts": v2_decision,
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [
                artifact(root, "artifacts/experiments/fitness_v2/experiment_decision.json"),
                artifact(root, "artifacts/experiments/fitness_v2/calibration/result.json"),
            ],
        },
        {
            "stage": "A100_MATCHED_SPRINT",
            "classification": "HISTORICAL_GUIDANCE",
            "sentinel": "WEAK_CONTINUE_THEN_SATURATION",
            "claim_boundary": "One seed on a shortcut-heavy synthetic world; useful for timing and failure discovery, not causal representation ranking.",
            "facts": {
                "budget_mode": sprint.get("budget_mode"),
                "config": sprint.get("config"),
                "provenance": sprint.get("provenance"),
                "stage_a_exact": {
                    arm: record["stage_a"]["exact"]
                    for arm, record in sprint["results"].items()
                    if "stage_a" in record
                },
            },
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "HISTORICAL_GUIDANCE"],
            "primary_artifacts": [
                artifact(root, "artifacts/experiments/tier2_sprint/gpu_sprint_results.json")
            ],
        },
        {
            "stage": "V3",
            "classification": "INVALIDATED",
            "sentinel": v3_invalidity.get("sentinel", "EXPERIMENT_INVALID"),
            "claim_boundary": "Aggregate DEV pooled five lookup ceilings with a context-truncation floor; founder scores cannot rank R.",
            "facts": {
                "development_pool_hash": v3_dev.get("dev_pool_hash"),
                "founder_candidate_count": len(v3_founders.get("candidates", {})),
                "invalidity": v3_invalidity,
            },
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [
                artifact(root, "artifacts/experiments/fitness_v3/development/result.json"),
                artifact(root, "artifacts/experiments/fitness_v3/founders/result.json"),
                artifact(root, "artifacts/experiments/fitness_v3/invalidity.json"),
            ],
        },
        {
            "stage": "V4",
            "classification": "INSTRUMENT_RESULT_ONLY",
            "sentinel": "FITNESS_V4_NOT_QUALIFIED",
            "claim_boundary": "Valid negative instrument result (0/5 mechanisms), later localized to response-budget and character-context guard defects; no R evaluated.",
            "facts": {
                "q0_rate": v4.get("q0", {}).get("rate"),
                "qualified_mechanisms": v4.get("qualified_mechanisms"),
                "instrument_qualified": v4.get("instrument_qualified"),
                "forensics": v4_forensics,
            },
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [
                artifact(root, "artifacts/experiments/fitness_v4/development/result.json"),
                artifact(root, "artifacts/reports/fitness-v4-forensics.json"),
            ],
        },
        {
            "stage": "V5_PHASE5",
            "classification": "VALID_NEGATIVE_EVIDENCE",
            "sentinel": "CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT",
            "claim_boundary": "Constrained protocol is sound, but Gemma framed qualified 0/3 mechanisms; no representation was scored.",
            "facts": {
                "model": v5["model"],
                "q0_rate": v5["q0"]["rate"],
                "instrument_qualified": v5["instrument_qualified"],
                "qualified_mechanisms": v5["qualified_mechanisms"],
                "mechanisms": ladder_summary(v5),
            },
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [
                artifact(root, "artifacts/experiments/fitness_v5/development/result.json")
            ],
        },
        {
            "stage": "PHASE6_GEMMA_BARE",
            "classification": "VALID_NEGATIVE_EVIDENCE",
            "sentinel": "GEMMA_BARE_EXPLICIT_POSITIVE_FAILURE",
            "claim_boundary": "Bare prompt treatment does not rescue Gemma; all three mechanisms void at the explicit-positive gate.",
            "facts": {
                "model": gemma_bare["model"],
                "q0_rate": gemma_bare["q0"]["rate"],
                "instrument_qualified": gemma_bare["instrument_qualified"],
                "qualified_mechanisms": gemma_bare["qualified_mechanisms"],
                "mechanisms": ladder_summary(gemma_bare),
            },
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"],
            "primary_artifacts": [
                artifact(
                    root,
                    "artifacts/experiments/fitness_v5/development/result-gemma4_12b-bare.json",
                )
            ],
        },
        {
            "stage": "PHASE6_QWEN_BARE",
            "classification": "INVALIDATED" if qwen_payload else "UNKNOWN",
            "sentinel": "PHASE6_INVALID_LITERAL_CACHE_GATE" if qwen_payload else "UNKNOWN",
            "claim_boundary": "Descriptively, Qwen escapes Gemma's fixed-cell degeneracy and qualifies one mechanism. Confirmatory Phase 6 is invalid under its literal cache-hit rule, and the frozen >=2-mechanism Game-R gate is not met; no founder or R claim.",
            "facts": qwen_observation,
            "evidence_tags": ["VERIFIED_BY_ARTIFACT", "VERIFIED_BY_CODE"]
            if qwen_payload
            else ["REPORTED_NOT_REPRODUCED"],
            "primary_artifacts": [],
        },
    ]

    output = {
        "schema_version": "codex-audit-experiment-evidence-v1",
        "audit_base_commit": git(root, "rev-parse", "HEAD"),
        "audit_branch": git(root, "branch", "--show-current"),
        "authority_order": [
            "canonical_records_and_independent_verification",
            "frozen_experiment_code_and_committed_manifests",
            "raw_per_probe_rows",
            "derived_decision_artifacts",
            "narrative_reports",
        ],
        "phase6_qwen_commit_caveat": "Observed in Claude's worktree after completion but not present in the audit base commit.",
        "evidence": evidence,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
