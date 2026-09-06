"""Read-only forensics over Fitness V4 DEV rows.

This module never calls the Solver and never writes into the experiment's artifact tree.  It
reads the committed development result (or, before it exists, the model-call cache) and
assigns every row a diagnostic cause that is deliberately separate from the frozen scientific
void code.  A diagnostic cause explains; it does not change any verdict.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json, stable_hash
from arena.experiments.fitness_v2 import QUALIFIED_MODEL
from arena.experiments.fitness_v4 import (
    EXPERIMENT_VERSION,
    INSTRUMENT_VERSION,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    RUNTIME_CONFIG,
    RUNTIME_CONFIG_HASH,
    build_dev_pool,
    build_prompt,
    context_status,
    equal_information_genome,
    parse_response,
)
from arena.storage.artifacts import ArtifactStore

FORENSICS_VERSION = "arena-fitness-v4-forensics-v1"
CAUSES = (
    "CORRECT",
    "NEGATIVE_CONTROL_RESPONSE",
    "SEMANTIC_ERROR",
    "REASONING_EXCEEDS_COMPLETION_BUDGET",
    "FORMAT_NONCOMPLIANCE",
    "CONTEXT_TRUNCATION",
    "OVER_BUDGET_UNSENT",
    "UNKNOWN",
)


def diagnose(row: dict[str, Any]) -> str:
    response = str(row.get("raw_output", ""))
    status = row.get("context_status", "OK")
    if status == "OVER_BUDGET":
        return "OVER_BUDGET_UNSENT"
    if status != "OK":
        return "CONTEXT_TRUNCATION"
    if row.get("parsed_index") is not None:
        if row.get("truth_kind") == "NEGATIVE_CONTROL_TARGET":
            return "NEGATIVE_CONTROL_RESPONSE"
        return "CORRECT" if row.get("correct") else "SEMANTIC_ERROR"
    budget = int(RUNTIME_CONFIG["num_predict"])
    if int(row.get("completion_tokens", 0)) >= budget and '"choice"' not in response:
        return "REASONING_EXCEEDS_COMPLETION_BUDGET"
    if response.strip():
        return "FORMAT_NONCOMPLIANCE"
    return "UNKNOWN"


def _looks_like_reasoning(response: str) -> bool:
    head = response.lstrip()[:80].lower()
    return head.startswith(("to ", "we ", "let", "first", "the ", "1.", "step", "looking", "analy"))


def _rows_from_cache(root: Path) -> list[dict[str, Any]]:
    """Rebuild DEV rows from the cache when the development result is not yet written."""

    control = equal_information_genome()
    rows: list[dict[str, Any]] = []
    for probe in build_dev_pool():
        prompt = build_prompt(control, probe)
        identity = {
            "experiment": EXPERIMENT_VERSION,
            "instrument": INSTRUMENT_VERSION,
            "model_digest": QUALIFIED_MODEL["digest"],
            "runtime_hash": RUNTIME_CONFIG_HASH,
            "genome_hash": control.genome_hash,
            "probe_hash": probe.derived_hash,
            "prompt_hash": stable_hash(prompt),
        }
        path = root / "artifacts/cache/fitness_v4" / f"{stable_hash(identity)}.json"
        if not path.exists():
            continue
        raw = json.loads(path.read_text())["result"]
        status = context_status(prompt, None if raw.get("error") else raw["prompt_eval_count"])
        selected = parse_response(raw["response"]) if status == "OK" else None
        expected_hash = probe.options[probe.expected_index].arguments[0].content_hash
        selected_hash = (
            probe.options[selected].arguments[0].content_hash if selected is not None else None
        )
        rows.append(
            {
                "probe_id": probe.probe_id,
                "family_id": probe.family_id,
                "mechanism": probe.mechanism,
                "level": probe.level,
                "variant": probe.variant.value,
                "truth_kind": probe.truth_kind,
                "expected_index": probe.expected_index,
                "parsed_index": selected,
                "correct": selected_hash == expected_hash,
                "context_status": status,
                "prompt_chars": len(prompt),
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "raw_output": raw["response"],
                "error": raw.get("error"),
            }
        )
    return rows


def _rows_from_result(root: Path) -> list[dict[str, Any]] | None:
    path = root / "artifacts/experiments/fitness_v4/development/result.json"
    if not path.exists():
        return None
    development = json.loads(path.read_text())
    rows: list[dict[str, Any]] = list(development["ladder_rows"])
    seen = {(row["probe_id"]) for row in rows}
    for report in development["mechanisms"].values():
        for row in report.get("rows", []):
            if row["probe_id"] not in seen:
                rows.append(row)
                seen.add(row["probe_id"])
    return rows


def run_forensics(root: Path) -> dict[str, Any]:
    rows = _rows_from_result(root)
    source = "development/result.json"
    if rows is None:
        rows = _rows_from_cache(root)
        source = "artifacts/cache/fitness_v4 (development result absent)"
    records = []
    for row in rows:
        cause = diagnose(row)
        records.append(
            {
                "mechanism": row["mechanism"],
                "level": row["level"],
                "family_id": row["family_id"],
                "variant": row["variant"],
                "truth_kind": row["truth_kind"],
                "prompt_chars": row.get("prompt_chars"),
                "prompt_eval_count": row.get("prompt_tokens"),
                "completion_tokens": row.get("completion_tokens"),
                "stop_reason": (
                    "completion_budget"
                    if int(row.get("completion_tokens", 0)) >= int(RUNTIME_CONFIG["num_predict"])
                    else "eos_or_stop"
                ),
                "response_prefix": str(row.get("raw_output", ""))[:120],
                "response_valid": row.get("parsed_index") is not None,
                "json_ever_emitted": '"choice"' in str(row.get("raw_output", "")),
                "begins_like_reasoning": _looks_like_reasoning(str(row.get("raw_output", ""))),
                "correct_if_parsable": bool(row.get("correct"))
                if row.get("parsed_index") is not None
                else None,
                "expected_index": row.get("expected_index"),
                "parsed_index": row.get("parsed_index"),
                "context_status": row.get("context_status"),
                "diagnostic_cause": cause,
            }
        )
    by_mechanism: dict[str, dict[str, Any]] = {}
    for mechanism in MECHANISMS:
        subset = [record for record in records if record["mechanism"] == mechanism]
        if not subset:
            continue
        by_level: dict[int, dict[str, Any]] = {}
        for level in range(len(LADDERS[mechanism])):
            cell = [record for record in subset if record["level"] == level]
            if not cell:
                continue
            positives = [record for record in cell if record["variant"] in POSITIVE_VARIANTS]
            by_level[level] = {
                "rows": len(cell),
                "causes": dict(Counter(record["diagnostic_cause"] for record in cell)),
                "malformed_rate": sum(not record["response_valid"] for record in cell) / len(cell),
                "reasoning_prefix_among_malformed": sum(
                    record["begins_like_reasoning"]
                    for record in cell
                    if not record["response_valid"]
                ),
                "completion_budget_hits": sum(
                    record["stop_reason"] == "completion_budget" for record in cell
                ),
                "answer_distribution": dict(
                    Counter(str(record["parsed_index"]) for record in cell)
                ),
                "positive_accuracy": (
                    sum(bool(record["correct_if_parsable"]) for record in positives)
                    / len(positives)
                    if positives
                    else None
                ),
                "prompt_tokens": {
                    "min": min(int(record["prompt_eval_count"] or 0) for record in cell),
                    "max": max(int(record["prompt_eval_count"] or 0) for record in cell),
                },
                "prompt_chars_max": max(int(record["prompt_chars"] or 0) for record in cell),
            }
        by_mechanism[mechanism] = {
            "causes": dict(Counter(record["diagnostic_cause"] for record in subset)),
            "by_level": by_level,
        }
    unusual = [
        record
        for record in records
        if record["diagnostic_cause"] not in {"CORRECT", "NEGATIVE_CONTROL_RESPONSE"}
    ]
    report = {
        "schema_version": FORENSICS_VERSION,
        "source": source,
        "runtime": RUNTIME_CONFIG,
        "rows_examined": len(records),
        "cause_totals": dict(Counter(record["diagnostic_cause"] for record in records)),
        "malformed_total": sum(not record["response_valid"] for record in records),
        "malformed_with_reasoning_prefix": sum(
            record["begins_like_reasoning"] for record in records if not record["response_valid"]
        ),
        "malformed_at_completion_budget": sum(
            record["stop_reason"] == "completion_budget"
            for record in records
            if not record["response_valid"]
        ),
        "by_mechanism": by_mechanism,
        "unusual_rows": unusual,
    }
    ArtifactStore(root / "artifacts").write_json("reports/fitness-v4-forensics.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = run_forensics(args.root)
    print(
        canonical_json(
            {
                "source": report["source"],
                "rows": report["rows_examined"],
                "causes": report["cause_totals"],
                "malformed_with_reasoning_prefix": report["malformed_with_reasoning_prefix"],
                "malformed_at_completion_budget": report["malformed_at_completion_budget"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
