"""Founder-tournament preflight: every check that needs no Solver call.

Run after ``fitness_v4 freeze`` and before ``fitness_v4 founders``.  It validates the roster,
re-asserts information parity from the frozen manifest, checks the manifest hash, computes
cache identities and resumability, estimates calls, runtime and disk from DEV latencies, and
reports the context-guard status of every founder prompt so that no probe is voided by
surprise.  Nothing here changes the frozen instrument.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from arena.canonical.schema import canonical_json, stable_hash
from arena.experiments.fitness_v2 import QUALIFIED_MODEL
from arena.experiments.fitness_v4 import (
    EXPERIMENT_VERSION,
    INSTRUMENT_VERSION,
    PROMOTION_RULE,
    RUNTIME_CONFIG_HASH,
    assert_game_r_genome,
    assert_information_parity,
    build_prompt,
    context_status,
    founder_genomes,
    load_frozen,
)
from arena.storage.artifacts import ArtifactStore


def run_preflight(root: Path) -> dict[str, Any]:
    manifest, probes = load_frozen(root)
    founders = founder_genomes()
    for genome in founders:
        assert_game_r_genome(genome)
    roster_ids = [genome.candidate_id for genome in founders]
    if roster_ids != [item["candidate_id"] for item in manifest["founder_roster"]]:
        raise ValueError("founder roster differs from the frozen manifest")
    if str(PROMOTION_RULE["baseline"]) not in roster_ids:
        raise ValueError("baseline candidate is not in the roster")

    development = json.loads(
        (root / "artifacts/experiments/fitness_v4/development/result.json").read_text()
    )
    latency: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in development["ladder_rows"]:
        latency[(row["mechanism"], row["level"])].append(float(row["latency_seconds"]))
    for report in development["mechanisms"].values():
        for row in report.get("rows", []):
            latency[(row["mechanism"], row["level"])].append(float(row["latency_seconds"]))

    cache_dir = root / "artifacts/cache/fitness_v4"
    per_candidate: dict[str, Any] = {}
    guard_flags: dict[str, list[str]] = defaultdict(list)
    parity_mismatch: list[str] = []
    expected_seconds = 0.0
    cached = 0
    for genome in founders:
        chars = 0
        tokens_estimate = 0.0
        for probe in probes:
            prompt = build_prompt(genome, probe)
            chars += len(prompt)
            tokens_estimate += len(prompt) / 2.9
            status = context_status(prompt, None)
            if status != "UNSENT":
                guard_flags[genome.candidate_id].append(probe.probe_id)
            identity = {
                "experiment": EXPERIMENT_VERSION,
                "instrument": INSTRUMENT_VERSION,
                "model_digest": QUALIFIED_MODEL["digest"],
                "runtime_hash": RUNTIME_CONFIG_HASH,
                "genome_hash": genome.genome_hash,
                "probe_hash": probe.derived_hash,
                "prompt_hash": stable_hash(prompt),
            }
            if (cache_dir / f"{stable_hash(identity)}.json").exists():
                cached += 1
            expected_hash = manifest["information_parity_prompt_hashes"][probe.probe_id][
                genome.candidate_id
            ]
            if expected_hash != stable_hash(prompt):
                parity_mismatch.append(f"{genome.candidate_id}:{probe.probe_id}")
            cell = latency.get((probe.mechanism, probe.level)) or [6.0]
            # Scale the control's latency by relative prompt length as a rough estimate.
            expected_seconds += (sum(cell) / len(cell)) * max(0.5, len(prompt) / 15000)
        per_candidate[genome.candidate_id] = {
            "probes": len(probes),
            "total_prompt_chars": chars,
            "estimated_prompt_tokens": int(tokens_estimate),
            "pre_guard_flagged_probes": len(guard_flags[genome.candidate_id]),
        }
    for probe in probes[:3]:
        assert_information_parity(probe, founders)
    calls = len(probes) * len(founders)
    report = {
        "schema_version": "arena-fitness-v4-preflight-v1",
        "manifest_hash": manifest["manifest_hash"],
        "qualified_mechanisms": manifest["qualified_mechanisms"],
        "selected_levels": manifest["selected_levels"],
        "roster": roster_ids,
        "baseline": PROMOTION_RULE["baseline"],
        "probes_per_candidate": len(probes),
        "expected_calls": calls,
        "already_cached": cached,
        "expected_runtime_seconds": int(expected_seconds),
        "expected_runtime_hours": round(expected_seconds / 3600, 2),
        "expected_cache_disk_mb": round(calls * 1.5 / 1024, 2),
        "expected_result_disk_mb": round(calls * 2.5 / 1024, 2),
        "parity_prompt_hash_mismatches": parity_mismatch,
        "pre_guard_flagged_by_candidate": {
            candidate_id: len(flags) for candidate_id, flags in guard_flags.items()
        },
        "pre_guard_flagged_probe_ids": sorted(
            {pid for flags in guard_flags.values() for pid in flags}
        ),
        "per_candidate": per_candidate,
        "resumability": (
            "every call is cached under its full identity; rerunning `founders` reuses cached rows "
            "and only makes the missing calls"
        ),
        "crash_recovery": (
            "kill and rerun; the cache reader validates identity and rejects malformed records"
        ),
        "statistics_pipeline": [
            "paired_against: wins/losses/ties, one-sided exact sign, clustered family bootstrap",
            "holm_decisions across non-baseline founders",
            "promotion checks: valid response, minimum net wins, Holm, practical effect, flip noninferiority",
        ],
        "ready": not parity_mismatch,
    }
    ArtifactStore(root / "artifacts").write_json("reports/fitness-v4-preflight.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    report = run_preflight(args.root)
    print(canonical_json({key: value for key, value in report.items() if key != "per_candidate"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
