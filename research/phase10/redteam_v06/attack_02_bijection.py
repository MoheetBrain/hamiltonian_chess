"""A2 -- build a renderer that passes the bijection AND parity checks while showing more or less.

The module docstring of ``arena/trajectory/representation.py`` states the contract as:

    "A bijection cannot add information -- there is nothing to add it from -- and cannot remove
    information, or it could not be inverted."

Two adversarial renderers test that claim.  Both subclass ``DeclarationDerivedRenderer``, both
declare EXACTLY the baseline's slots with EXACTLY the baseline's values (so ``project_arm`` types
them ``R_ONLY``), and both ship an ``invert`` that reconstructs ``R_A``'s mapping byte for byte.

``HintedWorkspace``   -- shows MORE than R_A: an oracle-grade hint computed from the declaration.
``SplitWorkspace``    -- shows LESS than R_A: half the goal text is moved out of ``goals_pp``,
                         the ONLY key the Solver reads, into a sibling key it never reads.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _common import emit  # noqa: E402

from arena.evolution.record import InterventionClass  # noqa: E402
from arena.trajectory.representation import (  # noqa: E402
    ARMS,
    BASELINE_RENDERER_ID,
    BijectiveRenderer,
    DeclarationDerivedRenderer,
    _declare_full,
    _scope_dict,
    bijection_report,
    project_arm,
)
from arena.trajectory.schema import BackendStateEnvelope, PPScope, content_sha256  # noqa: E402
from arena.trajectory.solver import OBSERVED_FIELD, observed_state_text  # noqa: E402
from arena.trajectory.state_identity import InformationSlot  # noqa: E402


def _cheap_hint(pp: str) -> str:
    """An 'oracle' computed from nothing but the declared goal text."""

    target = pp.rsplit("⊢", 1)[-1].strip()
    if " = " in target:
        left, right = target.split(" = ", 1)
        if left.strip() == right.strip():
            return "rfl"
        return "ring_nf"
    if target.startswith("∀") or target.startswith("("):
        return "intro"
    return "simp"


@dataclass(frozen=True, slots=True)
class HintedWorkspace(DeclarationDerivedRenderer):
    """Declares exactly the baseline's slots and values; SHOWS a derived hint as well."""

    arm_id: str = "R_HINT"
    renderer_id: str = "redteam-R_HINT-v1"

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return _declare_full(envelope)

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        pp = str(information[InformationSlot.GOAL_TEXT])
        text = f"{pp}\n[SUGGESTED TACTIC] {_cheap_hint(pp)}"
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": text,
            "n_goals": information[InformationSlot.GOAL_COUNT],
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "pp_sha256": content_sha256(text),
        }

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]:
        pp = str(rendered["goals_pp"]).rsplit("\n[SUGGESTED TACTIC] ", 1)[0]
        return {
            "renderer_id": BASELINE_RENDERER_ID,
            "backend_kind": rendered["backend_kind"],
            "state_id": rendered["state_id"],
            "goals_pp": pp,
            "n_goals": rendered["n_goals"],
            "pp_scope": dict(rendered["pp_scope"]),
            "pp_sha256": content_sha256(pp),
        }


@dataclass(frozen=True, slots=True)
class SplitWorkspace(DeclarationDerivedRenderer):
    """Declares exactly the baseline's slots and values; SHOWS only half of the goal text.

    The other half rides in ``context_appendix``, which ``invert`` reads and the Solver does not:
    ``arena.trajectory.solver.OBSERVED_FIELD`` is ``goals_pp`` and nothing else is ever read.
    """

    arm_id: str = "R_HALF"
    renderer_id: str = "redteam-R_HALF-v1"

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return _declare_full(envelope)

    def present(self, information: Mapping[str, Any]) -> Mapping[str, Any]:
        pp = str(information[InformationSlot.GOAL_TEXT])
        lines = pp.split("\n")
        cut = len(lines) // 2
        return {
            "renderer_id": self.renderer_id,
            "backend_kind": information[InformationSlot.BACKEND_KIND],
            "state_id": information[InformationSlot.BACKEND_STATE_ID],
            "goals_pp": "\n".join(lines[cut:]),
            "context_appendix": "\n".join(lines[:cut]),
            "n_goals": information[InformationSlot.GOAL_COUNT],
            "pp_scope": _scope_dict(information[InformationSlot.PP_SCOPE]),
            "pp_sha256": content_sha256(pp),
        }

    def invert(self, rendered: Mapping[str, Any]) -> Mapping[str, Any]:
        head = str(rendered["context_appendix"])
        tail = str(rendered["goals_pp"])
        pp = f"{head}\n{tail}" if head else tail
        return {
            "renderer_id": BASELINE_RENDERER_ID,
            "backend_kind": rendered["backend_kind"],
            "state_id": rendered["state_id"],
            "goals_pp": pp,
            "n_goals": rendered["n_goals"],
            "pp_scope": dict(rendered["pp_scope"]),
            "pp_sha256": content_sha256(pp),
        }


def _envelopes() -> list[BackendStateEnvelope]:
    states = [
        "n : Nat\nh : 0 < n\n⊢ n ≠ 0",
        "x : Nat\n⊢ x + 0 = x + 0",
        "s : Set α\nf : α → ℝ\nhf : Summable f\n⊢ ∀ a, s.indicator f a ≤ f a",
    ]
    return [
        BackendStateEnvelope(
            index=i,
            state_id=f"sid{i}",
            pp=pp,
            backend_kind="LEAN4_TACTIC_STATE_PP",
            pp_scope=PPScope(current_namespace="Nat", open_declarations=("Finset",)),
            n_goals=1,
            session_id="sess",
            problem_id="F.lean::t",
        )
        for i, pp in enumerate(states)
    ]


def main() -> int:
    envelopes = _envelopes()
    findings: dict[str, Any] = {}
    for name, renderer in (("R_HINT", HintedWorkspace()), ("R_HALF", SplitWorkspace())):
        report = bijection_report(renderer, envelopes)
        projected = project_arm(renderer, envelopes[0])
        rendered = renderer.render(envelopes[0])
        baseline_seen = observed_state_text(
            type(
                "O",
                (),
                {"step_index": 0, "state_id": "s", "rendered": ARMS["R_A"].render(envelopes[0])},
            )()
        )
        arm_seen = observed_state_text(
            type("O", (), {"step_index": 0, "state_id": "s", "rendered": rendered})()
        )
        findings[name] = {
            "satisfies_BijectiveRenderer_protocol": isinstance(renderer, BijectiveRenderer),
            "bijection_holds_everywhere": report.holds_everywhere,
            "n_checked": report.n_checked,
            "n_holds": report.n_holds,
            "derived_intervention_class": str(projected.identity.intervention_class),
            "typed_R_ONLY": (
                InterventionClass(projected.identity.intervention_class) is InterventionClass.R_ONLY
            ),
            "observed_field": OBSERVED_FIELD,
            "chars_shown_baseline": len(baseline_seen),
            "chars_shown_arm": len(arm_seen),
            "sample_shown_to_model": arm_seen,
        }
    passed_both = [
        n for n, f in findings.items() if f["bijection_holds_everywhere"] and f["typed_R_ONLY"]
    ]
    emit(
        "attack_02_bijection",
        {
            "attack": "A2 projection bijection: pass the checks while showing more or less",
            "verdict": "BROKEN" if passed_both else "HELD",
            "renderers_that_passed_every_check": passed_both,
            "findings": findings,
            "note": (
                "check_bijection tests invert(render(s)) == R_A.render(s) over the WHOLE rendered "
                "mapping, and derive_intervention_class reads only the DECLARATION. Neither "
                "constrains the single key the Solver actually reads (solver.OBSERVED_FIELD = "
                "'goals_pp'), and neither notices content that is a deterministic FUNCTION of the "
                "declaration rather than new information."
            ),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
