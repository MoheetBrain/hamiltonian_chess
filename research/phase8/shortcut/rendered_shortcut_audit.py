"""Phase 8 rendered-prompt shortcut audit for the precondition ladder.

For every candidate stratum and every founder arm this script:

1. renders the ADV_DEV pool through the arm and DEVELOPS + FREEZES adversaries on it
   (``rendered_prompt_adversary.develop_and_freeze``);
2. renders the disjoint SHORTCUT_EVAL pool and evaluates the FROZEN adversaries on it
   (``evaluate_frozen``) -- the number that matters for the gate;
3. evaluates the full rule family on the fresh pool with a within-family permutation null
   (``evaluate_rules``) -- the descriptive "how big is the family's selection noise" view;
4. reports twin invariance per feature on the fresh pool.

The adversary receives ONLY the prompt string and the option count.  Nothing here touches a
Solver.  Zero model calls.

Run:  .venv/bin/python -m research.phase8.shortcut.rendered_shortcut_audit [--strata ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from arena.canonical.schema import stable_hash
from arena.environments.precondition_ladder import ENVIRONMENT_VERSION, Pool, build_pool
from arena.experiments import rendered_prompt_adversary as rpa
from arena.experiments.game_r_formal_v1 import SyntaxGuidePolicy, build_prompt, founder_genome

AUDIT_VERSION = "phase8-rendered-shortcut-audit-v1"
DEFAULT_STRATA = ("P05", "P07", "P09", "P12", "P16", "P20", "P05_M2_D2", "P05_M3_D4", "P12_M2_D2")
ARMS = ("L3_JSON_AST", "L0_STRUCTURED_ENGLISH", "L1_CURRENT_HML", "L2_SEXPR", "L5_COMPACT_SYMBOLIC")
DEV_FAMILIES = 100
EVAL_FAMILIES = 200
GUIDE = SyntaxGuidePolicy.SHARED_CONSTANT


def examples_for(stratum: str, pool: Pool, families: int, arm: str) -> list[rpa.Example]:
    genome = founder_genome(arm)
    out: list[rpa.Example] = []
    for item in build_pool(stratum, pool, families):
        prompt = build_prompt(genome, item, guide_policy=GUIDE)
        out.append(
            rpa.Example(
                prompt=prompt,
                n_options=len(item.options),
                correct_index=item.correct_index,
                family_id=item.family_id,
                arm_id=genome.candidate_id,
                task_id=item.task_id,
            )
        )
    return out


def audit_cell(
    stratum: str,
    arm: str,
    *,
    dev_families: int,
    eval_families: int,
    bootstrap: int,
    permutations: int,
    frozen_dir: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    dev = examples_for(stratum, Pool.ADV_DEV, dev_families, arm)
    evl = examples_for(stratum, Pool.SHORTCUT_EVAL, eval_families, arm)
    frozen = rpa.develop_and_freeze(
        dev, top_k=3, bootstrap_samples=bootstrap, permutations=permutations
    )
    frozen_path = frozen_dir / f"{stratum}__{arm}.json"
    frozen_path.parent.mkdir(parents=True, exist_ok=True)
    frozen_path.write_text(rpa.to_json(frozen), encoding="utf-8")
    evaluation = rpa.evaluate_frozen(frozen, evl)
    full = rpa.evaluate_rules(evl, bootstrap_samples=bootstrap, permutations=permutations)
    twins = rpa.twin_invariance_report(evl)
    arm_eval = evaluation.arm(founder_genome(arm).candidate_id)
    full_dict = full.to_dict()
    return {
        "stratum": stratum,
        "arm": arm,
        "candidate_id": founder_genome(arm).candidate_id,
        "dev_families": dev_families,
        "dev_examples": len(dev),
        "eval_families": eval_families,
        "eval_examples": len(evl),
        "dev_task_hash": stable_hash([e.task_id for e in dev]),
        "eval_task_hash": stable_hash([e.task_id for e in evl]),
        "eval_prompt_hash": stable_hash([__import__("hashlib").sha256(e.prompt.encode()).hexdigest() for e in evl]),
        "frozen_hash": frozen.content_hash,
        "frozen_path": str(frozen_path),
        "frozen_selected_rules": list(frozen.selected_rules),
        "frozen_models": [m.name for m in frozen.models],
        "frozen_eval": arm_eval.to_dict(),
        "gate_view": {
            "best_adversary": arm_eval.best,
            "best_accuracy": arm_eval.best_accuracy,
            "best_holm_p": arm_eval.best_holm_p,
            "best_bonferroni_upper": arm_eval.best_bonferroni_upper,
            "significant": arm_eval.significant,
        },
        "full_family_on_eval": {
            k: v for k, v in full_dict.items() if k != "rules"
        },
        "full_family_top5_on_eval": sorted(
            (
                {"rule": r["rule"], "accuracy": r["accuracy"], "cp_upper": r.get("cp_upper")}
                for r in full_dict.get("rules", [])
            ),
            key=lambda r: -float(r["accuracy"]),
        )[:5],
        "twin_invariance": twins,
        "seconds": round(time.monotonic() - started, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strata", default=",".join(DEFAULT_STRATA))
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--dev-families", type=int, default=DEV_FAMILIES)
    parser.add_argument("--eval-families", type=int, default=EVAL_FAMILIES)
    parser.add_argument("--bootstrap", type=int, default=300)
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--out", default="artifacts/reports/precondition_rendered_shortcut_audit.json")
    parser.add_argument("--frozen-dir", default="artifacts/manifests/phase8_frozen_adversaries")
    args = parser.parse_args(argv)
    cells: list[dict[str, Any]] = []
    for stratum in args.strata.split(","):
        for arm in args.arms.split(","):
            cell = audit_cell(
                stratum,
                arm,
                dev_families=args.dev_families,
                eval_families=args.eval_families,
                bootstrap=args.bootstrap,
                permutations=args.permutations,
                frozen_dir=Path(args.frozen_dir),
            )
            g = cell["gate_view"]
            print(
                f"{stratum:10s} {arm:24s} best={g['best_adversary']:34s} acc={g['best_accuracy']:.4f} "
                f"bonf_upper={g['best_bonferroni_upper']:.4f} holm_p={g['best_holm_p']:.3f} "
                f"fullmax={cell['full_family_on_eval'].get('best_accuracy', float('nan')):.4f} "
                f"({cell['seconds']}s)",
                file=sys.stderr,
                flush=True,
            )
            cells.append(cell)
    payload = {
        "audit_version": AUDIT_VERSION,
        "adversary_family_version": rpa.ADVERSARY_FAMILY_VERSION,
        "environment_version": ENVIRONMENT_VERSION,
        "guide_policy": str(GUIDE),
        "design": {
            "development_pool": "ADV_DEV",
            "evaluation_pool": "SHORTCUT_EVAL",
            "dev_families": args.dev_families,
            "eval_families": args.eval_families,
            "top_k_rules": 3,
            "bootstrap_samples": args.bootstrap,
            "permutations": args.permutations,
            "input_to_adversary": "prompt string + option count only",
        },
        "cells": cells,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {out} ({len(cells)} cells)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
