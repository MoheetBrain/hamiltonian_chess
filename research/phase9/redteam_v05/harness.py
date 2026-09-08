"""Shared attack harness for the HC-V0.5 red team.

Nothing here edits the package.  A ``ScriptedArena`` satisfies ``arena.trajectory.task.TaskArena``
so the failure policy, budget, terminal vocabulary and cost ledger can be attacked deterministically
with no Lean process at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from arena.trajectory.arena_v0 import (
    ArenaObservation,
    ArenaStep,
    ActionSpaceSpec,
    BackendNativeRenderer,
)
from arena.trajectory.lean_backend import LeanTheoremProbe, StepOutcome, TacticPolicy
from arena.trajectory.schema import BackendStateEnvelope, PPScope, TerminalStatus

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)


def emit(name: str, payload: dict[str, Any]) -> None:
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(payload, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(payload, indent=1, sort_keys=True, default=str))
    print(f"\n[written] {path}")


def make_probe(
    *,
    problem_id: str = "RT/Probe.lean::rt.probe",
    reference: Sequence[str] = ("intro h", "exact h.symm"),
    statement: str = "theorem probe_rt (a b : Nat) (h : a = b) : b = a",
) -> LeanTheoremProbe:
    return LeanTheoremProbe(
        problem_id=problem_id,
        full_name="rt.probe",
        safe_name="rt_probe",
        file_path="RT/Probe.lean",
        statement=statement,
        prefix_text="import Mathlib\n",
        pp_scope=PPScope(current_namespace="RT", open_declarations=("Nat",)),
        reference_tactics=tuple(reference),
    )


@dataclass
class ScriptedStep:
    """One programmed backend answer."""

    outcome: StepOutcome
    pp: str = ""
    error: str = ""
    closed: bool = False


class ScriptedArena:
    """A ``TaskArena`` whose backend answers are programmed in advance.

    ``plan`` is consulted by attempt index; ``default`` covers everything past the plan.  It
    mirrors ``LeanTrajectoryArena``'s own contract: only ``StepOutcome.OK`` appends a state, a
    rejection leaves the state list alone, ``BACKEND_DEAD``/``TIMEOUT`` set ``ERROR_BACKEND``, and
    the attempt budget trips ``BUDGET_EXHAUSTED``.
    """

    def __init__(
        self,
        plan: Sequence[ScriptedStep] = (),
        *,
        default: ScriptedStep | None = None,
        attempt_budget: int = 32,
        renderer: Any | None = None,
        probe: LeanTheoremProbe | None = None,
        session_tag: str = "scripted",
    ) -> None:
        self.plan = list(plan)
        self.default = default or ScriptedStep(StepOutcome.TACTIC_ERROR, error="scripted refusal")
        self.attempt_budget = attempt_budget
        self.renderer = renderer or BackendNativeRenderer()
        self._probe = probe
        self._session_tag = session_tag
        self._states: list[BackendStateEnvelope] = []
        self._terminal = TerminalStatus.OPEN
        self._attempts = 0
        self.tactics: list[str] = []
        self.abandon_reasons: list[str] = []
        self.closed = False

    # -- TaskArena protocol -------------------------------------------------------
    @property
    def terminal_status(self) -> TerminalStatus:
        return self._terminal

    @property
    def states(self) -> tuple[BackendStateEnvelope, ...]:
        return tuple(self._states)

    @property
    def legal_action_space(self) -> ActionSpaceSpec:
        return ActionSpaceSpec.from_policy(TacticPolicy.record_only())

    def reset(self, probe: LeanTheoremProbe, *, hide_reference: Sequence[str] | None = None):
        self._probe = probe
        self._states = [
            BackendStateEnvelope(
                index=0,
                state_id="0",
                pp="a b : Nat\nh : a = b\n⊢ b = a",
                pp_scope=probe.pp_scope,
                n_goals=1,
                session_id=self._session_tag,
                problem_id=probe.problem_id,
            )
        ]
        self._terminal = TerminalStatus.OPEN
        self._attempts = 0
        return self._observe(self._states[-1])

    def step(self, tactic: str) -> ArenaStep:
        self.tactics.append(tactic)
        if self._terminal.is_terminal:
            return ArenaStep(
                self._observe(self._states[-1]), 0.0, self._terminal,
                {"refused": "episode already terminal"},
            )
        index = self._attempts
        self._attempts += 1
        scripted = self.plan[index] if index < len(self.plan) else self.default
        info: dict[str, Any] = {"outcome": scripted.outcome.value, "wall_ms": 1}
        if scripted.outcome is StepOutcome.OK:
            envelope = BackendStateEnvelope(
                index=len(self._states),
                state_id=str(len(self._states)),
                pp=scripted.pp or f"⊢ goal after {len(self._states)}",
                pp_scope=self._states[-1].pp_scope,
                n_goals=0 if scripted.closed else 1,
                session_id=self._session_tag,
                problem_id=self._states[-1].problem_id,
            )
            self._states.append(envelope)
            info["tactic_head"] = tactic.strip().split()[0] if tactic.strip() else ""
            info["n_goals"] = envelope.n_goals
            info["no_op_suspected"] = envelope.pp_sha256 == self._states[-2].pp_sha256
            if scripted.closed:
                info["kernel"] = {"verified": True, "print_axioms": "[propext]"}
                self._terminal = TerminalStatus.CLOSED_VERIFIED
            elif self._attempts >= self.attempt_budget:
                self._terminal = TerminalStatus.BUDGET_EXHAUSTED
            return ArenaStep(self._observe(self._states[-1]), 0.0, self._terminal, info)
        info["error"] = scripted.error
        if scripted.outcome in {StepOutcome.BACKEND_DEAD, StepOutcome.TIMEOUT}:
            self._terminal = TerminalStatus.ERROR_BACKEND
        elif scripted.outcome is StepOutcome.SESSION_EXPIRED:
            self._terminal = TerminalStatus.ABANDONED
        elif self._attempts >= self.attempt_budget:
            self._terminal = TerminalStatus.BUDGET_EXHAUSTED
        return ArenaStep(self._observe(self._states[-1]), 0.0, self._terminal, info)

    def abandon(self, reason: str) -> TerminalStatus:
        self.abandon_reasons.append(reason)
        if not self._terminal.is_terminal:
            self._terminal = TerminalStatus.ABANDONED
        return self._terminal

    def close(self) -> None:
        self.closed = True

    def _observe(self, envelope: BackendStateEnvelope) -> ArenaObservation:
        return ArenaObservation(
            step_index=len(self._states) - 1,
            state_id=envelope.state_id,
            rendered=self.renderer.render(envelope),
            n_goals=envelope.n_goals,
            attempts_remaining=max(0, self.attempt_budget - self._attempts),
            terminal_status=self._terminal,
        )
