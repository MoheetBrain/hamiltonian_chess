"""RED TEAM follow-ups: the seams the first four scripts exposed.

F1  the object the semantic gate validates vs the object that builds the prompt
F2  dead-candidate enforcement, forced (the loop's own proposer never produced a kill)
F3  `verify_closed_script` cannot verify an AXIOM-FREE proof: `_AXIOMS_RE` only matches
    "'X' depends on axioms: [...]", never Lean's "'X' does not depend on any axioms"
F4  how much of the runtime leakage tripwire is inert (tactics shorter than 6 characters)
F5  `build_trajectory(actor=...)` overwrites who chose every action

Run:  .venv/bin/python research/phase9/redteam/attack_followups.py
Out:  research/phase9/redteam/out/followups.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from arena.evolution.loop import (  # noqa: E402
    ArenaSpec,
    EvolutionLoop,
    LoopConfig,
    model_view,
    semantic_gate,
)
from arena.genome.seeds import SEED_GENOMES  # noqa: E402
from arena.languages.phenotype import GenomePhenotypeLanguage  # noqa: E402
from arena.languages.registry import language_for_genome  # noqa: E402
from arena.players.architect import Architect  # noqa: E402
from arena.storage.artifacts import ArtifactStore  # noqa: E402
from arena.trajectory.arena_v0 import LeanTrajectoryArena  # noqa: E402
from arena.trajectory.lean_backend import (  # noqa: E402
    _AXIOMS_RE,
    LeanTheoremProbe,
    LeanToolchainConfig,
    TacticPolicy,
    check_toolchain,
    iter_leandojo_records,
    verify_closed_script,
)
from arena.trajectory.schema import Actor, PPScope, SourceVersion  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)
TRAIN = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/"
    "leandojo_raw/leandojo_benchmark_4/random/train.json"
)


def main() -> int:
    findings: dict[str, Any] = {}
    items = ArenaSpec().solve_items()
    state = items[0].canonical_state

    # ---------------------------------------------------------------- F1 two renderers, one genome
    divergence: dict[str, Any] = {}
    for genome in SEED_GENOMES:
        gate_object = language_for_genome(genome)
        prompt_object = GenomePhenotypeLanguage(model_view(genome).surface)
        try:
            same = gate_object.render(state) == prompt_object.render(state)
        except Exception as exc:  # noqa: BLE001
            same = f"{type(exc).__name__}: {str(exc)[:80]}"
        divergence[genome.candidate_id] = {
            "gate_validates": type(gate_object).__name__,
            "prompt_uses": type(prompt_object).__name__,
            "identical_bytes": same,
        }
    findings["F1_gate_object_vs_prompt_object"] = {
        "per_seed": divergence,
        "note": (
            "semantic_gate check 1 runs render/parse on language_for_genome(child); the prompt "
            "the evaluator scores comes from GenomePhenotypeLanguage(model_view(child).surface). "
            "For the eight seeds these are DIFFERENT CLASSES constructed separately from one "
            "genome. Nothing asserts they agree; this measures whether they do."
        ),
    }

    # ---------------------------------------------------------------- F2 forced dead candidate
    store_path = OUT / "store" / "forced_dead"
    if store_path.exists():
        shutil.rmtree(store_path)
    store_path.mkdir(parents=True)
    store = ArtifactStore(store_path)
    loop = EvolutionLoop(store=store, config=LoopConfig(seed=99, generations=1, population=4))
    parent = SEED_GENOMES[0]

    inert_proposal = None
    for proposal in Architect().propose(parent, count=64, seed=7):
        report = semantic_gate(parent=parent, child=proposal.genome, items=items)
        if not report.passed:
            inert_proposal = (proposal, report)
            break
    if inert_proposal is None:
        findings["F2_dead_candidate"] = {"skipped": "no failing proposal found in 64 draws"}
    else:
        proposal, report = inert_proposal
        result = loop._score(parent, proposal, generation=0)  # noqa: SLF001 - that is the point
        rows_path = next((p for p in store.root.rglob("*.rows.jsonl")), None)
        league_before = set(loop.registry.candidates)
        findings["F2_dead_candidate"] = {
            "child_id": result.child_id,
            "outcome": result.outcome.value,
            "record_status": result.record.status.value,
            "void_code": result.record.void_code,
            "failure_modes": list(result.record.failure_modes),
            "evaluation_ran": result.evaluation is not None,
            "budget_calls": result.record.budget.calls,
            "fitness_measured": result.record.fitness_vector.measured(),
            "rows_file_bytes": rows_path.stat().st_size if rows_path else None,
            "entered_league_registry": result.child_id in league_before,
            "gate_detail": report.outcomes[-1].detail[:140],
        }

    # ---------------------------------------------------------------- F3 axiom-free false negative
    lean_ok = check_toolchain().available
    sample_lines = [
        "'probe_x' depends on axioms: [propext, Classical.choice, Quot.sound]",
        "'probe_x' does not depend on any axioms",
    ]
    findings["F3_axiom_free_proof"] = {
        "regex": _AXIOMS_RE.pattern,
        "regex_matches": {line: bool(_AXIOMS_RE.search(line)) for line in sample_lines},
    }
    if lean_ok:
        config = LeanToolchainConfig.from_env()
        axiom_free = LeanTheoremProbe(
            problem_id="redteam::axiom_free",
            full_name="redteam.axiom_free",
            safe_name="redteam_axiom_free",
            file_path="<synthetic>",
            statement="theorem probe_redteam_axiom_free : 1 = 1",
            prefix_text="import Mathlib.Tactic",
            pp_scope=PPScope(),
            reference_tactics=(),
        )
        result = verify_closed_script(axiom_free, ["rfl"], config=config)
        findings["F3_axiom_free_proof"]["live"] = {
            "statement": "theorem probe_redteam_axiom_free : 1 = 1 := by rfl",
            "verified": result.verified,
            "exit_code": result.exit_code,
            "print_axioms": result.print_axioms,
            "errors": result.errors[:200],
            "note": (
                "a genuinely correct, kernel-checked, axiom-free proof is reported NOT verified "
                "because the parser only understands the 'depends on axioms: [...]' spelling"
            ),
        }

        # ------------------------------------------------------- F5 actor is whatever you say
        arena = LeanTrajectoryArena(config=config, policy=TacticPolicy.record_only())
        probe = LeanTheoremProbe(
            problem_id="redteam::actor",
            full_name="redteam.actor",
            safe_name="redteam_actor",
            file_path="<synthetic>",
            statement="theorem probe_redteam_actor : 2 + 2 = 4",
            prefix_text="import Mathlib.Tactic",
            pp_scope=PPScope(),
            reference_tactics=("norm_num",),
        )
        arena.reset(probe, hide_reference=probe.reference_tactics)
        step = arena.step("norm_num")
        version = SourceVersion(
            dataset="redteam",
            license="n/a",
            split="train",
            file_path="<synthetic>",
            full_name="redteam.actor",
        )
        as_reference = arena.build_trajectory(
            actor=Actor.REFERENCE, source_version=version, reference_horizon=1
        )
        as_solver = arena.build_trajectory(
            actor=Actor.SOLVER, source_version=version, reference_horizon=1
        )
        inflated = arena.build_trajectory(
            actor=Actor.SOLVER, source_version=version, reference_horizon=999
        )
        arena.close()
        findings["F5_actor_and_horizon_are_caller_assertions"] = {
            "same_episode": True,
            "terminal_status": step.terminal_status.value,
            "as_REFERENCE": as_reference.horizon.to_dict(),
            "as_SOLVER": as_solver.horizon.to_dict(),
            "inflated_reference_horizon": inflated.horizon.to_dict(),
            "trajectory_ids_differ": len(
                {as_reference.trajectory_id, as_solver.trajectory_id, inflated.trajectory_id}
            ),
            "note": (
                "one episode, three self-consistent records with different provenance claims. "
                "The arena stamps Actor.SOLVER on every action in step(); build_trajectory then "
                "overwrites all of them with whatever the caller passes."
            ),
        }
    else:
        findings["F3_axiom_free_proof"]["live"] = {"skipped": "no lean toolchain"}

    # ---------------------------------------------------------------- F4 tripwire inertness
    if TRAIN.is_file():
        short = total = 0
        histogram: dict[str, int] = {}
        for record in iter_leandojo_records(TRAIN, limit=6000):
            for step_record in record.get("traced_tactics") or []:
                tactic = str(step_record.get("tactic", "")).strip()
                if not tactic:
                    continue
                total += 1
                if len(tactic) < 6:
                    short += 1
                    histogram[tactic] = histogram.get(tactic, 0) + 1
        findings["F4_runtime_tripwire_inert_fraction"] = {
            "threshold": 6,
            "tactics_scanned": total,
            "shorter_than_threshold": short,
            "fraction": round(short / max(1, total), 4),
            "top_short_tactics": dict(sorted(histogram.items(), key=lambda kv: -kv[1])[:12]),
            "note": (
                "assert_observation_clean skips any remaining reference tactic shorter than 6 "
                "characters, so for this fraction of steps the runtime leakage tripwire is a "
                "no-op by construction"
            ),
        }

    (OUT / "followups.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(findings, indent=2, ensure_ascii=False)[:11000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
