"""CPU-only acceptance evidence. Fail closed on corruption, parity drift or oracle mismatch."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

from arena.environments import premise_selection as ps
from arena.languages._json_tools import canonical_json, strict_json_loads
from .schema import CanonicalPremiseSelectionState, order_candidates, visible_projection, verify_response
from .renderer_bridge import REPRESENTATIONS, founder_coverage, render
from .information_inventory import assert_parity
from .invariance import (UnsupportedTransformation, alpha_rename_locals,
                         obfuscate_option_identities, permute_independent_context, permute_options)


def load_bank(path: Path) -> list[CanonicalPremiseSelectionState]:
    return [CanonicalPremiseSelectionState.from_dict(strict_json_loads(line))
            for line in path.read_text(encoding="utf-8").split("\n") if line]


def recheck_trace(items: list[CanonicalPremiseSelectionState], source: Path, limit: int) -> dict:
    """Recover answers afresh from original TRAIN trace, not stored bank target metadata."""
    wanted = {(s.provenance["proof_id"], s.provenance["trace_step"]): s for s in items}
    checked = set()
    for theorem in ps.stream_traced_theorems(ps.require_permitted_train(source / "random/train.json"), limit=limit):
        for step in ps.raw_steps(theorem):
            key = (step.proof_id, step.step_index)
            if key not in wanted:
                continue
            state = wanted[key]
            if len(step.premises) != 1:
                raise ValueError("oracle source is not single-citation")
            target = next(c for c in state.candidate_premises if c.premise_id == state.target_choice_id)
            evidence = state.oracle_evidence
            if target.name != step.premises[0].full_name or state.source_raw_state != step.state_before:
                raise ValueError("bank target/state differs from source trace")
            if target.provenance["source_path"] != step.premises[0].def_path:
                raise ValueError("target declaration path differs from citation annotation")
            for field, text in (("tactic_sha256", step.tactic), ("annotation_sha256", step.annotated_tactic), ("state_after_sha256", step.state_after)):
                if evidence[field] != hashlib.sha256(text.encode()).hexdigest():
                    raise ValueError(f"source evidence mismatch: {field}")
            checked.add(key)
    if checked != set(wanted):
        raise ValueError("source evidence missing for bank items")
    return {"trace_citations_recovered": len(checked), "kernel_replay": False}


def run_audit(bank: Path, out: Path, source: Path | None = None) -> dict:
    items = load_bank(bank)
    if not items or len({s.task_id for s in items}) != len(items):
        raise ValueError("empty bank or duplicate tasks")
    manifest = strict_json_loads((bank.parent / "development_manifest.json").read_text())
    if hashlib.sha256(bank.read_bytes()).hexdigest() != manifest["bank_sha256"]:
        raise ValueError("bank differs from frozen development manifest")
    if len({s.provenance["proof_id"] for s in items}) != len(items):
        raise ValueError("bank must contain one item per theorem group")
    checks = Counter()
    rows = []
    for state in items:
        if state.candidate_premises != order_candidates(state.task_id, state.candidate_premises, manifest["seed"]):
            raise ValueError("candidate order differs from frozen seed policy")
        rows.append(assert_parity(state))
        changed_target = next(c.premise_id for c in state.candidate_premises if c.premise_id != state.target_choice_id)
        poisoned = replace(state, target_choice_id=changed_target, oracle_evidence={"poison": "PRIVATE_ORACLE"},
                           provenance={"poison": "PRIVATE_PROVENANCE"}, audit_metadata={"poison": "PRIVATE_METADATA"})
        for representation in REPRESENTATIONS:
            if render(poisoned, representation) != render(state, representation):
                raise ValueError("private data affects model-facing bytes")
        checks["private_field_noninterference"] += 1
        original_label = next(chr(65 + i) for i, c in enumerate(state.candidate_premises) if c.premise_id == state.target_choice_id)
        neutral = obfuscate_option_identities(state)
        if visible_projection(neutral) != visible_projection(state) or not verify_response(neutral, original_label):
            raise ValueError("semantic-ID obfuscation changed task")
        checks["experimental_id_obfuscation"] += 1
        # Every cyclic shift, not just a single swap: answer follows semantic identity.
        for offset in range(len(state.candidate_premises)):
            permutation = tuple(range(offset, len(state.candidate_premises))) + tuple(range(offset))
            permuted = permute_options(state, permutation)
            label = next(chr(65 + i) for i, c in enumerate(permuted.candidate_premises) if c.premise_id == state.target_choice_id)
            if not verify_response(permuted, label):
                raise ValueError("option permutation changed citation oracle")
            assert_parity(permuted)
            checks["option_permutations"] += 1
        for name, transform in (("alpha_rename", alpha_rename_locals), ("independent_context_permutation", permute_independent_context)):
            try:
                transformed = transform(state)
            except UnsupportedTransformation:
                checks[name + "_unsupported"] += 1
                continue
            if transformed.target_choice_id != state.target_choice_id:
                raise ValueError("metamorphism changed target identity")
            assert_parity(transformed)
            checks[name + "_supported"] += 1
    source_result = recheck_trace(items, source, manifest["source_theorem_limit"]) if source else {"status": "NOT_RUN"}
    result = {"status": "GAME_R_SOURCE_PROJECTION_PARITY_PASS", "items": len(items),
              "representations": list(REPRESENTATIONS), "original_renderings_checked": len(items) * len(REPRESENTATIONS),
              "invariance": dict(checks), "source_recheck": source_result,
              "scope": "source-envelope serialization and recorded citation identity; not Lean kernel semantics",
              "rows": rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / "parity_report.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    (out / "representation_coverage.json").write_text(json.dumps(founder_coverage(), indent=2, sort_keys=True) + "\n")
    return {key: value for key, value in result.items() if key != "rows"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=Path("research/astra/artifacts/dev_bank.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("research/astra/artifacts"))
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    print(canonical_json(run_audit(args.bank, args.out, args.source)))


if __name__ == "__main__":
    main()
