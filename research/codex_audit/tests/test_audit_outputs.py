"""Regression checks for the deterministic Codex audit outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "research/codex_audit"


def load(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_world_v0_shortcuts_are_exact() -> None:
    result = load("world_v0_baselines.json")
    assert len(result["rows"]) == 676
    assert result["baseline_accuracy"]["state_id_rewrite_action_id"] == 1.0
    assert result["baseline_accuracy"]["domain_codebook_operation"] == 1.0
    assert result["baseline_accuracy"]["one_canonical_legal_action"] == 1.0
    assert result["baseline_accuracy"]["visible_has_no_legal_action"] == 1.0


def test_route_b_reproduces_reported_defects() -> None:
    result = load("route_b_audit.json")
    assert result["split_audit"]["seed_argument_loaded_inside_stratified_split"] is False
    assert result["split_audit"]["quality_counts"]["stage_b_first_576"] == {
        "GOLD": 424,
        "REJECT": 48,
        "SILVER": 104,
    }
    assert result["headline_overlap"]["at_224_answer_or_problem"]["count"] == 21
    assert result["metric_audit"]["wrong_action_demo"]["score"] == {
        "exact": 0,
        "schema_valid": 1,
        "verified": 1,
    }


def test_formal_depth_shortcuts_are_reconciled() -> None:
    result = load("formal_depth_shortcuts.json")
    assert result["reported_numbers_reconciled"]["shallow_1_0"] == {
        "accuracy": 1.0,
        "correct": 24,
        "n": 24,
    }
    deep = result["reported_numbers_reconciled"]["approximately_0_913"]
    assert deep["correct"] == 22
    assert deep["n"] == 24


def test_operation_and_data_inventory_counts() -> None:
    operations = load("operation_inventory.json")
    assert operations["cross_source"]["granular_reasoning_steps"] == 792
    assert operations["cross_source"]["formal_tactic_transitions"] == 259580
    assert operations["sources"]["leandojo"]["premise_references"] == 418704
    registry = load("local_data_registry.json")
    assert registry["verified_assets"]["lean_runtime_v2_full"]["rows"] == 1150
    assert (
        registry["verified_assets"]["lean_runtime_v2_full"]["structurally_eligible_states"] == 461
    )


def test_phase6_is_not_promoted_past_literal_rule() -> None:
    result = load("experiment_evidence.json")
    qwen = next(item for item in result["evidence"] if item["stage"] == "PHASE6_QWEN_BARE")
    assert qwen["classification"] == "INVALIDATED"
    assert qwen["sentinel"] == "PHASE6_INVALID_LITERAL_CACHE_GATE"
    assert qwen["facts"]["cache_audit"]["all_cache_hits"] == 61
    assert qwen["facts"]["fixed_cell_degeneracy_vs_gemma_framed"]["alternate_modal_count"] == 36


def test_risk_register_is_complete() -> None:
    result = load("risk_register.json")
    assert result["risk_count"] == 22
    assert len({item["id"] for item in result["risks"]}) == 22
    assert result["severity_counts"]["CRITICAL"] == 5
