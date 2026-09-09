"""A10 -- can ``R_ABLATED`` leak into anything that reads like a candidate language?

``R_ABLATED`` is a ``P_CHANGE`` positive control, not a representation. Spec §3: "not a candidate
language and may never enter a league or archive."  This attack looks for every route by which it
could be treated as one:

L1  is it in the registries that name representations (``REPRESENTATION_ARM_IDS``,
    ``BIJECTIVE_ARM_IDS``, ``NULL_PERTURBATION_ARM_IDS``)?
L2  does it satisfy ``BijectiveRenderer`` structurally?
L3  can ``project_arm`` ever type it ``R_ONLY``?
L4  can a ``CellOutcome`` carry it with an ``R_ONLY`` class?
L5  is it in the gene table, or can ``classify_intervention`` type it?
L6  does any league / archive / promotion path in ``arena/`` accept an arm id or a renderer id?
L7  does the assay's own manifest declare it as a representation?
L8  does ``permits_representation_claim`` hold for its derived class?
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import ROOT, emit  # noqa: E402

from arena.evolution.record import InterventionClass  # noqa: E402
from arena.experiments.hc_v0_6.schema import Arm  # noqa: E402
from arena.experiments.hc_v0_6_assay import build_manifest  # noqa: E402
from arena.trajectory.representation import (  # noqa: E402
    ARMS,
    BIJECTIVE_ARM_IDS,
    GOAL_VISIBILITY_GENE,
    NULL_PERTURBATION_ARM_IDS,
    REPRESENTATION_ARM_IDS,
    BijectiveRenderer,
    declared_gene_classes,
    project_arm,
)
from arena.trajectory.schema import BackendStateEnvelope, PPScope  # noqa: E402
from arena.trajectory.solver import ScriptedSolver  # noqa: E402
from tests.trajectory.test_anchor import make_anchor, make_bank  # noqa: E402


def main() -> int:
    ablated = ARMS["R_ABLATED"]
    envelope = BackendStateEnvelope(
        index=0,
        state_id="sid",
        pp="n : Nat\n⊢ n = n",
        backend_kind="LEAN4_TACTIC_STATE_PP",
        pp_scope=PPScope(),
        n_goals=1,
    )
    projected = project_arm(ablated, envelope)
    findings: dict[str, Any] = {
        "L1_in_REPRESENTATION_ARM_IDS": "R_ABLATED" in REPRESENTATION_ARM_IDS,
        "L1_in_BIJECTIVE_ARM_IDS": "R_ABLATED" in BIJECTIVE_ARM_IDS,
        "L1_in_NULL_PERTURBATION_ARM_IDS": "R_ABLATED" in NULL_PERTURBATION_ARM_IDS,
        "L2_satisfies_BijectiveRenderer": isinstance(ablated, BijectiveRenderer),
        "L2_has_invert": hasattr(ablated, "invert"),
        "L3_derived_class": str(projected.identity.intervention_class),
        "L8_permits_representation_claim": InterventionClass(
            projected.identity.intervention_class
        ).permits_representation_claim,
        "L5_gene_in_table": GOAL_VISIBILITY_GENE in declared_gene_classes(),
    }

    # L4 -- a row that claims R_ABLATED is R_ONLY
    from arena.experiments.hc_v0_6.schema import CellOutcome, ParseStatus, StepResult

    try:
        CellOutcome(
            anchor_id="a",
            cluster_id="c",
            theorem="t",
            reelaboration_key="k",
            arm=Arm.R_ABLATED,
            renderer_id="R_ABLATED",
            intervention_class=InterventionClass.R_ONLY,
            replicate_index=0,
            step_result=StepResult.ACCEPTED_TRANSITION,
            parse_status=ParseStatus.OK,
            closed_all_goals=False,
            prompt_sha256="0" * 64,
            prompt_tokens=1,
            response_tokens=1,
            latency_ms=1,
            solver_digest="d",
        )
        findings["L4_row_claiming_R_ONLY"] = "ACCEPTED"
    except Exception as error:
        findings["L4_row_claiming_R_ONLY"] = f"REJECTED -- {type(error).__name__}: {error}"

    # L5 -- can classify_intervention type it?
    try:
        from arena.evolution.record import classify_intervention

        findings["L5_classify_intervention"] = str(classify_intervention([GOAL_VISIBILITY_GENE]))
    except Exception as error:
        findings["L5_classify_intervention"] = f"FAILS CLOSED -- {type(error).__name__}: {error}"

    # L6 -- does any league / archive / promotion path anywhere accept an arm or renderer id?
    grep = subprocess.run(
        [
            "grep",
            "-rn",
            "-e",
            "R_ABLATED",
            "-e",
            "goal-withheld",
            "--include=*.py",
            "arena",
            "tests",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    hits = [line for line in grep.stdout.splitlines() if line.strip()]
    modules = sorted({line.split(":", 1)[0] for line in hits})
    league_like = subprocess.run(
        [
            "grep",
            "-rln",
            "-e",
            "class .*League",
            "-e",
            "def .*archive",
            "-e",
            "def .*promote",
            "--include=*.py",
            "arena",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    findings["L6_modules_mentioning_R_ABLATED"] = modules
    findings["L6_league_or_archive_modules"] = sorted(
        line for line in league_like.stdout.splitlines() if line.strip()
    )
    findings["L6_overlap"] = sorted(set(modules) & set(findings["L6_league_or_archive_modules"]))

    # L7 -- what the manifest says about it
    manifest = build_manifest(
        __import__("arena.experiments.hc_v0_6_assay", fromlist=["AssayRun"]).AssayRun(),
        bank=make_bank([make_anchor()]),
        solver=ScriptedSolver(default="skip"),
        arms=tuple(Arm),
        replicates=1,
        seed=1,
    )
    findings["L7_manifest_renderer_declaration"] = manifest["renderers"]["R_ABLATED"]

    leaked = (
        findings["L1_in_REPRESENTATION_ARM_IDS"]
        or findings["L1_in_BIJECTIVE_ARM_IDS"]
        or findings["L2_satisfies_BijectiveRenderer"]
        or findings["L8_permits_representation_claim"]
        or findings["L4_row_claiming_R_ONLY"] == "ACCEPTED"
        or bool(findings["L6_overlap"])
    )
    emit(
        "attack_10_control_exclusion",
        {
            "attack": "A10 control exclusion: can R_ABLATED read as a candidate language?",
            "verdict": "BROKEN" if leaked else "HELD",
            "findings": findings,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
