"""AUDIT 7 / Part K, Questions 1 and 9 — gate-by-gate Phase 6 vs V7, READ-ONLY.

Reads the two frozen artifacts and reports, per mechanism, exactly which gate each version
evaluated and what value it saw.  It RE-SCORES NOTHING: every number printed is a field that the
run itself wrote into its own artifact.  Zero model calls.  Writes only inside
research/audit/a7_retro/.

Also recounts the Phase-6 `cache_hit == true` rows independently (Q9).

Run:  .venv/bin/python -m research.audit.a7_retro.gate_by_gate_diff
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P6 = ROOT / "artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json"
V5 = ROOT / "artifacts/experiments/fitness_v5/development/result.json"
V7 = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = Path(__file__).resolve().parent / "gate_by_gate_diff.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cache_census(payload: dict) -> dict:
    out: dict[str, object] = {}
    total = 0
    ladder = payload.get("ladder_rows", [])
    hits = sum(1 for r in ladder if r.get("cache_hit"))
    out["ladder_rows"] = {"rows": len(ladder), "cache_hit_true": hits}
    total += hits
    for mechanism, report in payload.get("mechanisms", {}).items():
        rows = report.get("rows", [])
        if not rows:
            continue
        hits = sum(1 for r in rows if r.get("cache_hit"))
        out[f"mechanisms.{mechanism}.rows"] = {"rows": len(rows), "cache_hit_true": hits}
        total += hits
    out["total_cache_hit_true"] = total
    return out


def mechanism_view(payload: dict, mechanism: str) -> dict:
    report = payload["mechanisms"][mechanism]
    view: dict[str, object] = {
        "ladder": {str(e["level"]): e["positive_accuracy"] for e in report["ladder"]},
        "selection": report.get("selection"),
        "selected_level": report.get("selected_level"),
    }
    summary = report.get("full_family_summary")
    if summary:
        view["full_family_summary"] = {
            k: summary[k]
            for k in (
                "positive_accuracy",
                "negative_target_accuracy",
                "positive_negative_gap",
                "largest_answer_share",
                "position_invariance",
                "valid_response_rate",
                "context_truncated_rows",
                "positive_examples",
            )
            if k in summary
        }
    if "shortcut_audit" in report:
        audit = report["shortcut_audit"]
        view["shortcut_audit_at_selected_level_only"] = {
            "items": audit.get("items"),
            "worst_rule": audit.get("worst_rule"),
            "worst_score": audit.get("worst_score"),
            "status": audit.get("status"),
        }
    if "per_level_shortcut" in report:
        view["per_level_shortcut"] = {
            lvl: {
                "best_shortcut_accuracy": cell.get("best_shortcut_accuracy"),
                "best_shortcut_feature": cell.get("best_shortcut_feature"),
                "status": cell.get("status"),
            }
            for lvl, cell in report["per_level_shortcut"].items()
        }
    view["qualification"] = report.get("qualification")
    return view


def main() -> int:
    p6 = json.loads(P6.read_text())
    v7 = json.loads(V7.read_text())
    v5 = json.loads(V5.read_text())

    report: dict[str, object] = {
        "analysis_class": "READ_ONLY_AUDIT_EXTRACTION_ZERO_MODEL_CALLS",
        "auditor": "A7 / Part K questions 1 and 9",
        "model_calls_made": 0,
        "note": (
            "Every value below was written by the run that produced the artifact. Nothing is "
            "re-scored; no verdict is reinterpreted."
        ),
        "artifacts": {
            "phase6_qwen_bare": {"path": str(P6.relative_to(ROOT)), "sha256": sha256(P6)},
            "v5_gemma_framed": {"path": str(V5.relative_to(ROOT)), "sha256": sha256(V5)},
            "v7_qwen_bare": {"path": str(V7.relative_to(ROOT)), "sha256": sha256(V7)},
        },
        "instrument_versions": {
            "phase6": p6.get("instrument_version"),
            "v5": v5.get("instrument_version"),
            "v7": v7.get("instrument_version"),
        },
        "frontier_constants": {
            "phase6_frontier_target": p6["qualification_rule"].get("frontier_target"),
            "phase6_shortcut_rule_max": p6["qualification_rule"].get("shortcut_rule_max"),
            "phase6_shortcut_margin": p6["qualification_rule"].get("shortcut_margin", "ABSENT"),
            "phase6_negative_target_accuracy_max": p6["qualification_rule"].get(
                "negative_target_accuracy_max", "ABSENT"
            ),
            "v7_frontier_target": v7["qualification_rule"].get("frontier_target"),
            "v7_shortcut_rule_max": v7["qualification_rule"].get("shortcut_rule_max"),
            "v7_shortcut_margin": v7["qualification_rule"].get("shortcut_margin", "ABSENT"),
            "v7_effective_window": v7["qualification_rule"].get("effective_qualifying_window"),
            "v7_shortcut_audit_scope": v7["qualification_rule"].get("shortcut_audit_scope"),
        },
        "instrument_qualified": {
            "phase6": p6.get("instrument_qualified"),
            "v7": v7.get("instrument_qualified"),
        },
        "qualified_mechanisms": {
            "phase6": p6.get("qualified_mechanisms"),
            "v7": v7.get("qualified_mechanisms"),
        },
        "mechanisms": {},
        "phase6_cache_census": cache_census(p6),
        "v7_cache_census": cache_census(v7),
    }

    for mechanism in ("formal_expression_depth", "transitive_dependency", "precondition_conjunction"):
        report["mechanisms"][mechanism] = {  # type: ignore[index]
            "phase6": mechanism_view(p6, mechanism),
            "v7": mechanism_view(v7, mechanism),
        }

    OUT.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
