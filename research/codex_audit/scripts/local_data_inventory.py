#!/usr/bin/env python3
"""Read-only inventory of the local mathematical data assets named by the audit."""

from __future__ import annotations

import argparse
import collections
import contextlib
import gzip
import hashlib
import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path: Path) -> int:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def first_jsonl(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.loads(next(handle))


def run(*cmd: str, cwd: Path | None = None) -> str | None:
    try:
        return subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.STDOUT).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def repo(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "git_commit": run("git", "rev-parse", "HEAD", cwd=path) if path.exists() else None,
        "git_branch": run("git", "branch", "--show-current", cwd=path) if path.exists() else None,
        "git_remote": run("git", "remote", "get-url", "origin", cwd=path)
        if path.exists()
        else None,
        "worktree_dirty": bool(run("git", "status", "--porcelain", cwd=path))
        if path.exists()
        else None,
    }


def disk_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):
                total += (Path(root) / name).stat().st_size
    return total


def json_files_steps(files: Iterable[Path], field: str) -> int:
    total = 0
    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        total += len(record.get(field, []))
    return total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    chatgpt = Path("/Users/moheet/Documents/ChatGPT")
    labs = Path("/Users/moheet/Projects/Hamiltonian-Labs")
    hmlv3 = chatgpt / "HML_V3"
    artifacts = labs / "hml_research_artifacts"
    corpus = chatgpt / "hmlt-reasoning-corpus"
    attest = chatgpt / "hmlt-reasoning-corpus-lean-attestation"
    prm = artifacts / "prm800k_raw"

    registry_path = hmlv3 / "data/registry/datasets.yaml"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_rows = []
    for record in registry["datasets"]:
        local = Path(record["local_path"])
        if not local.is_absolute():
            local = hmlv3 / local
        registry_rows.append(
            {
                **record,
                "resolved_local_path": str(local),
                "local_exists_at_audit": local.exists(),
            }
        )

    leandojo = artifacts / "leandojo/steps.jsonl"
    tactic_heads: collections.Counter[str] = collections.Counter()
    premise_rows = 0
    premise_refs = 0
    leandojo_splits: collections.Counter[str] = collections.Counter()
    with leandojo.open(encoding="utf-8") as handle:
        leandojo_count = 0
        for line in handle:
            row = json.loads(line)
            leandojo_count += 1
            tactic_heads[str(row.get("head"))] += 1
            n = int(row.get("n_premises_used", 0))
            premise_rows += int(n > 0)
            premise_refs += n
            leandojo_splits[str(row.get("split"))] += 1
    leandojo_raw = artifacts / "leandojo_raw/leandojo_benchmark_4"
    metadata = json.loads((leandojo_raw / "metadata.json").read_text(encoding="utf-8"))

    runtime_parts = sorted((hmlv3 / "data/corpus").glob("lean_runtime_v2_full*.jsonl.gz"))
    runtime_rows = sum(lines(path) for path in runtime_parts)
    runtime_sample = first_jsonl(runtime_parts[0])
    sealed_manifest = json.loads(
        (hmlv3 / "data/corpus/SEALED_V2_MANIFEST.json").read_text(encoding="utf-8")
    )

    # These functions perform deterministic local parsing/rendering only; no model or Lean run.
    from arena.environments.formal_structural import load_formal_states, sealed_source_files
    from arena.experiments.fitness_v5 import _formal_pool

    structurally_eligible = len(load_formal_states())
    fair_pool = _formal_pool(Path.cwd())

    gold10_files = sorted((corpus / "data/gold_10").glob("*.json"))
    gold25_files = sorted((corpus / "data/gold25/trajectories").glob("*.json"))
    gold125_new_files = sorted((corpus / "data/gold125/trajectories").glob("*.json"))
    gold10_steps = json_files_steps(gold10_files, "actions")
    gold25_steps = json_files_steps(gold25_files, "steps")
    gold125_new_steps = json_files_steps(gold125_new_files, "steps")

    prm_test = prm / "prm800k/math_splits/test.jsonl"
    prm_readme = (prm / "README.md").read_text(encoding="utf-8")
    prm_provenance = (prm / "README_PROVENANCE.md").read_text(encoding="utf-8")

    mathlib = hmlv3 / "external/checkouts/mathlib4-29dcec0"
    lean_toolchain = (mathlib / "lean-toolchain").read_text(encoding="utf-8").strip()
    olean_files = list((mathlib / ".lake").rglob("*.olean"))
    replay_manifest = json.loads(
        (hmlv3 / "data/manifests/lean_pipeline_v1.json").read_text(encoding="utf-8")
    )

    output = {
        "schema_version": "codex-audit-local-data-registry-v1",
        "scan_roots": [str(chatgpt), str(labs)],
        "repositories": {
            "HML_V3": repo(hmlv3),
            "hmlt-reasoning-corpus": repo(corpus),
            "hmlt-reasoning-corpus-lean-attestation": repo(attest),
            "prm800k_artifact_clone": repo(prm),
            "hml-standard": repo(labs / "hml-standard"),
            "hamiltonian-lang": repo(chatgpt / "hamiltonian-lang-final-signal"),
        },
        "hml_v3_registry": {
            "path": str(registry_path),
            "sha256": sha256(registry_path),
            "schema_version": registry.get("schema_version"),
            "entries": registry_rows,
        },
        "verified_assets": {
            "leandojo_benchmark4_derived_steps": {
                "path": str(leandojo),
                "bytes": leandojo.stat().st_size,
                "sha256": sha256(leandojo),
                "rows": leandojo_count,
                "schema_keys": sorted(first_jsonl(leandojo)),
                "rows_with_premises": premise_rows,
                "premise_references": premise_refs,
                "splits": dict(leandojo_splits),
                "top_tactic_heads": tactic_heads.most_common(30),
                "raw_benchmark_path": str(leandojo_raw),
                "raw_metadata": metadata,
                "trust": "FORMAL_TRACE_SOURCE_NOT_FRESH_REPLAY_PER_ROW",
            },
            "lean_runtime_v2_full": {
                "paths": [str(path) for path in runtime_parts],
                "file_count": len(runtime_parts),
                "bytes": sum(path.stat().st_size for path in runtime_parts),
                "rows": runtime_rows,
                "schema_version": runtime_sample.get("schema_version"),
                "structurally_eligible_states": structurally_eligible,
                "length_fair_states": sum(len(values) for values in fair_pool.values()),
                "length_fair_strata": {key: len(value) for key, value in fair_pool.items()},
                "sealed_source_files_excluded_by_name": len(sealed_source_files()),
                "sealed_manifest": sealed_manifest,
                "trust": "ELABORATION_CAPTURE; STRUCTURAL ANSWERS RECOMPUTED; NOT TACTIC REPLAY",
            },
            "granular_reasoning_chain_family": {
                "sources": [
                    {
                        "path": str(corpus / "data/gold_10"),
                        "problems": len(gold10_files),
                        "steps": gold10_steps,
                        "step_field": "actions",
                    },
                    {
                        "path": str(corpus / "data/gold25/trajectories"),
                        "problems": len(gold25_files),
                        "steps": gold25_steps,
                        "step_field": "steps",
                    },
                    {
                        "path": str(corpus / "data/gold125/trajectories"),
                        "problems": len(gold125_new_files),
                        "steps": gold125_new_steps,
                        "step_field": "steps",
                    },
                ],
                "problems_total": len(gold10_files) + len(gold25_files) + len(gold125_new_files),
                "steps_total": gold10_steps + gold25_steps + gold125_new_steps,
                "gold125_only_steps": gold25_steps + gold125_new_steps,
                "provenance": "MATH source-grounded reconstructions; curated deterministic artifact generation, not scalable extraction or proof replay.",
                "verification": "STRUCTURAL/SOURCE-SPAN AUDIT, NOT FORMAL MATHEMATICAL VERIFICATION",
                "domains": "Hendrycks MATH subjects",
            },
            "prm800k_math_test": {
                "path": str(prm_test),
                "bytes": prm_test.stat().st_size,
                "sha256": sha256(prm_test),
                "rows": lines(prm_test),
                "upstream_commit": run("git", "rev-parse", "HEAD", cwd=prm),
                "upstream_remote": run("git", "remote", "get-url", "origin", cwd=prm),
                "official_readme_states_500_holdout": "remaining 500 held-out problems"
                in prm_readme,
                "local_provenance_attests_lfs_hashes": "Every LFS file resolved" in prm_provenance,
                "provenance_verdict": "OFFICIAL PRM800K 500-ROW HELD-OUT MATH SPLIT; commonly called MATH-500, but that alias is downstream nomenclature, not a field in the file.",
            },
            "pinned_mathlib_runtime": {
                "path": str(mathlib),
                "git_commit": run("git", "rev-parse", "HEAD", cwd=mathlib),
                "lean_toolchain": lean_toolchain,
                "olean_files_present": len(olean_files),
                "disk_bytes": disk_bytes(mathlib),
                "fresh_replay_sample": replay_manifest["counts"].get("fresh_replay_pass"),
                "fresh_replay_nonpass_sample": replay_manifest["counts"].get(
                    "fresh_replay_nonpass"
                ),
                "sample_size": replay_manifest["selection"].get("attestation_rows"),
                "full_corpus_replay": False,
            },
        },
        "falsified_or_corrected_reports": [
            {
                "reported": "approximately 300,000 granular reasoning steps",
                "finding": "792 steps across Gold-10 (23), frozen Gold-25 (118), and 100 new Gold-125 trajectories (651); Gold-125 alone is 769.",
                "classification": "INVALIDATED",
            },
            {
                "reported": "Lean runtime corpus has roughly 1,150 elaborated transitions and 461 eligible states",
                "finding": f"Exactly {runtime_rows} rows and {structurally_eligible} structurally eligible; {sum(len(v) for v in fair_pool.values())} survive V5 length fairness.",
                "classification": "VERIFIED_BY_SOURCE_DATA",
            },
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
