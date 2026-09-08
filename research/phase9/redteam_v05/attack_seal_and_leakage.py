"""Targets 1 and 2: source-proof substitution and reference/future-action leakage.

Every check prints VERDICT=DEFECT (the attack worked) or VERDICT=HELD (the defence stopped it).
Nothing here edits the package; the only monkeypatching is inside this file.
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import ScriptedArena, ScriptedStep, emit, make_probe  # noqa: E402

from arena.trajectory import episode as episode_mod  # noqa: E402
from arena.trajectory import task as task_mod  # noqa: E402
from arena.trajectory.arena_v0 import AnswerLeakageError, BackendNativeRenderer  # noqa: E402
from arena.trajectory.lean_backend import StepOutcome  # noqa: E402
from arena.trajectory.schema import BackendStateEnvelope  # noqa: E402
from arena.trajectory.solver import (  # noqa: E402
    OBSERVED_FIELD,
    ScriptedSolver,
    build_prompt,
    observed_state_text,
)
from arena.trajectory.state_identity import check_projection_parity, project_workspace  # noqa: E402
from arena.evolution.record import InterventionClass  # noqa: E402
from arena.trajectory.task import (  # noqa: E402
    ReferenceProofExposureError,
    VerifiedTask,
    seal_reference_proof,
)

RESULTS: dict[str, Any] = {}
LONG = "nlinarith [sq_nonneg (a - b), sq_nonneg (a + b)]"   # 44 bytes, >= 6
SHORT = "ring"                                              # 4 bytes,  < 6


def record(key: str, defect: bool, **detail: Any) -> None:
    RESULTS[key] = {"verdict": "DEFECT" if defect else "HELD", **detail}
    print(f"{key}: VERDICT={'DEFECT' if defect else 'HELD'}  {detail}")


# ---------------------------------------------------------------- S1: constructor refuses text
def s1() -> None:
    probe = make_probe(reference=(LONG, SHORT))
    seal, guard = seal_reference_proof(probe.reference_tactics)
    try:
        VerifiedTask(probe=probe, reference_seal=seal, leakage_guard=guard)
        record("S1_constructor_accepts_reference_text", True, note="probe with tactics accepted")
    except ReferenceProofExposureError as exc:
        record("S1_constructor_accepts_reference_text", False, refusal=str(exc)[:120])


# --------------------------------------------- S2: deep object-graph scan of a *live* task
def _walk(obj: Any, seen: set[int], depth: int = 0, path: str = "task") -> list[str]:
    """Every string reachable from a live task, including closures and cell contents."""

    found: list[str] = []
    if depth > 7 or id(obj) in seen:
        return found
    seen.add(id(obj))
    if isinstance(obj, str):
        return [f"{path}={obj!r}"] if (LONG in obj or obj.strip() == SHORT) else []
    if isinstance(obj, (bytes, bytearray)):
        return []
    if isinstance(obj, Mapping):
        for key, value in obj.items():
            found += _walk(value, seen, depth + 1, f"{path}[{key!r}]")
        return found
    if isinstance(obj, (list, tuple, set, frozenset)):
        for i, item in enumerate(obj):
            found += _walk(item, seen, depth + 1, f"{path}[{i}]")
        return found
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        for i, cell in enumerate(getattr(obj, "__closure__", None) or ()):
            try:
                found += _walk(cell.cell_contents, seen, depth + 1, f"{path}.<cell {i}>")
            except ValueError:
                pass
        return found
    for attr in list(getattr(obj, "__slots__", ())) + list(
        getattr(obj, "__dict__", {}) or {}
    ):
        try:
            found += _walk(getattr(obj, attr), seen, depth + 1, f"{path}.{attr}")
        except Exception:  # noqa: BLE001
            pass
    return found


def s2() -> None:
    # (a) the SHIPPED construction path: no injected factory, so `_lean_arena_factory` is used.
    probe = make_probe(reference=(LONG, SHORT))
    shipped = VerifiedTask.from_probe(probe)
    hits_shipped = _walk(shipped, set())
    record(
        "S2_reference_text_reachable_from_shipped_task",
        bool(hits_shipped),
        hits=hits_shipped[:5],
        note="default _lean_arena_factory closure captures config/policy/renderer/budget only",
    )
    # (b) the same scan through the PUBLIC arena_factory seam, which a caller may close over
    #     anything at all.  This is the seam, not the shipped path.
    injected = VerifiedTask.from_probe(probe, arena_factory=lambda: ScriptedArena(probe=probe))
    injected.reset()
    injected.step("simp")
    hits_injected = _walk(injected, set())
    record(
        "S2b_reference_text_reachable_through_injected_arena_factory",
        bool(hits_injected),
        hits=hits_injected[:3],
        note="arena_factory is a public constructor parameter and is not scanned",
    )
    # (c) the whole selection object
    from arena.trajectory.task import TaskSelection
    sel = TaskSelection(tasks=(shipped,), scanned=1, discards={}, leakage={}, seed=0,
                        scan_limit=1, min_reference_length=1, max_reference_length=None,
                        train_json="x")
    record("S2c_reference_text_reachable_from_selection", bool(_walk(sel, set())),
           hits=_walk(sel, set())[:3])


def s11() -> None:
    """Does the static leakage filter DROP a leaking task, or only annotate it?"""
    from arena.trajectory.arena_v0 import LeakageFilter, select_candidates

    leaking_record = {
        "full_name": "rt.probe",
        "file_path": "RT/Probe.lean",
        "traced_tactics": [
            {"tactic": LONG, "state_before": f"a b : Nat\n-- {LONG}\n\u22a2 b = a",
             "state_after": "no goals"}
        ],
    }
    reasons = LeakageFilter().scan_record(leaking_record)
    probe = make_probe(reference=(LONG,))
    task = VerifiedTask.from_leandojo_record(leaking_record, probe)
    record(
        "S11_from_leandojo_record_enforces_its_own_leak_filter",
        True,
        scan_reasons=[r.value for r in reasons],
        task_built=bool(task.task_id),
        provenance_static_leakage_filters=list(task.provenance.static_leakage_filters),
        note="the filter's verdict is RECORDED in provenance and the task is built anyway; "
        "select_candidates() is the layer that actually drops (verified separately)",
    )


# ---------------------------------------------------------------- S3: the __slots__ claim
def s3() -> None:
    probe = make_probe(reference=(LONG,))
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: ScriptedArena(probe=probe))
    try:
        task.smuggled_reference = LONG  # type: ignore[attr-defined]
        new_attr = True
    except AttributeError:
        new_attr = False
    # ... but every declared slot is writable, including the probe itself.
    task._probe = probe  # noqa: SLF001  (probe still carries reference_tactics)
    reattached = tuple(task._probe.reference_tactics)  # noqa: SLF001
    hits = _walk(task, set())
    record(
        "S3_slots_prevent_reattachment",
        bool(reattached) or new_attr,
        new_attribute_accepted=new_attr,
        declared_slot_reassignment_accepted=bool(reattached),
        reachable_after_reassignment=hits[:3],
        note="__slots__ blocks a NEW name; it does not freeze the declared slots",
    )


# ------------------------------------------- S4: is there any fallback-to-source code path?
def s4() -> None:
    src_task = inspect.getsource(task_mod)
    src_ep = inspect.getsource(episode_mod)
    uses = [
        line.strip()
        for line in (src_task + "\n" + src_ep).splitlines()
        if "reference_tactics" in line and not line.strip().startswith(("#", "*", '"'))
    ]
    # live check: every action rejected; nothing from the reference is ever played
    probe = make_probe(reference=(LONG, SHORT))
    arena = ScriptedArena(probe=probe, default=ScriptedStep(StepOutcome.TACTIC_ERROR, error="no"))
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    solver = ScriptedSolver(default="exact foo")
    result = episode_mod.run_episode(task, solver, max_steps=8)
    leaked = [t for t in arena.tactics if t in (LONG, SHORT)]
    record(
        "S4_runner_falls_back_to_reference",
        bool(leaked),
        reference_tactics_played=leaked,
        tactics_played=arena.tactics,
        terminal=result.terminal_status,
        reference_tactics_mentions_in_source=uses,
    )


# ------------------------------------------------- S5/S6: the hashed guard's length floor
@dataclass(frozen=True)
class LeakyRenderer:
    """Appends a sealed tactic to the goal text -- the one field the Solver is allowed to read."""

    secret: str
    renderer_id: str = "leaky-v0"

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        base = dict(BackendNativeRenderer().render(envelope))
        base["goals_pp"] = f"{base['goals_pp']}\n-- hint: {self.secret}"
        return base


def _leak_attempt(secret: str, reference: tuple[str, ...]) -> tuple[bool, str]:
    probe = make_probe(reference=reference)
    task = VerifiedTask.from_probe(
        probe,
        renderer=LeakyRenderer(secret=secret),
        arena_factory=lambda: ScriptedArena(probe=probe, renderer=LeakyRenderer(secret=secret)),
    )
    try:
        projection = task.reset()
    except AnswerLeakageError as exc:
        return False, str(exc)[:100]
    return True, build_prompt(observed_state_text(
        episode_mod.SolverObservation(0, "?", projection.rendered)
    ))


def s5_s6() -> None:
    leaked, detail = _leak_attempt(LONG, (LONG, SHORT))
    record("S5_long_reference_tactic_into_goals_pp", leaked, detail=detail[:200])
    leaked, detail = _leak_attempt(SHORT, (LONG, SHORT))
    record(
        "S6_short_reference_tactic_into_goals_pp",
        leaked,
        secret=SHORT,
        secret_bytes=len(SHORT.encode()),
        min_secret_len=task_mod.HashedLeakageGuard().min_secret_len,
        prompt_tail=detail[-160:],
    )


# ------------------------------------- S7: identifiers the guard never registers at all
def s7() -> None:
    probe = make_probe(reference=(LONG,))
    for label, secret in (
        ("full_name", probe.full_name),
        ("file_path", probe.file_path),
        ("pp_scope_namespace", probe.pp_scope.current_namespace),
    ):
        leaked, detail = _leak_attempt(secret, (LONG,))
        record(f"S7_{label}_into_goals_pp", leaked, secret=secret, prompt_tail=detail[-120:])


# --------------------------------------------- S8: the Solver prompt's one-key allow-list
def s8() -> None:
    hostile = {
        OBSERVED_FIELD: "⊢ 1 = 1",
        "reference_proof": LONG,
        "remaining_tactics": [LONG, SHORT],
        "full_name": "Mathlib.Real.secret",
        "pp_scope": {"current_namespace": "Secret"},
    }
    prompt = build_prompt(observed_state_text(episode_mod.SolverObservation(0, "s", hostile)))
    leaked = any(bad in prompt for bad in (LONG, "Mathlib.Real.secret", "Secret"))
    record("S8_prompt_allowlist_bypass", leaked, prompt=prompt)


# ---------------------------------- S9: leakage through the backend diagnostic channel
def s9() -> None:
    probe = make_probe(reference=(LONG,))
    padded = "x" * 500
    arena = ScriptedArena(
        probe=probe,
        default=ScriptedStep(StepOutcome.TACTIC_ERROR, error=f"{padded} {LONG}"),
    )
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    task.reset()
    try:
        out = task.step("foo")
        record(
            "S9_diagnostic_leak_past_truncation",
            LONG in out.diagnostic,
            diagnostic_len=len(out.diagnostic),
            leaked=LONG in out.diagnostic,
            note="the guard runs AFTER truncation, so a secret past the cap is cut, not shown",
        )
    except AnswerLeakageError as exc:
        record("S9_diagnostic_leak_past_truncation", False, refusal=str(exc)[:100])

    # second variant: the secret inside the FIRST line, under the cap
    arena2 = ScriptedArena(probe=probe, default=ScriptedStep(StepOutcome.TACTIC_ERROR,
                                                            error=f"try {LONG} instead"))
    task2 = VerifiedTask.from_probe(probe, arena_factory=lambda: arena2)
    task2.reset()
    try:
        out2 = task2.step("foo")
        record("S9b_diagnostic_leak_short_line", LONG in out2.diagnostic, diagnostic=out2.diagnostic)
    except AnswerLeakageError as exc:
        record("S9b_diagnostic_leak_short_line", False, refusal=str(exc)[:100])


# ------------------------------- S10: TaskStepResult.info is forwarded without a leak check
def s10() -> None:
    probe = make_probe(reference=(LONG,))

    class NoisyArena(ScriptedArena):
        def step(self, tactic: str):
            out = super().step(tactic)
            out.info["kernel"] = {"verified": True, "script": LONG}
            return out

    arena = NoisyArena(probe=probe, plan=[ScriptedStep(StepOutcome.OK, pp="⊢ done")])
    task = VerifiedTask.from_probe(probe, arena_factory=lambda: arena)
    task.reset()
    out = task.step("intro h")
    payload = repr(dict(out.info))
    record(
        "S10_step_info_not_leak_checked",
        LONG in payload,
        info_keys=sorted(out.info),
        note="info is returned to the caller; the guard only covers projection.rendered and "
        "the diagnostic",
    )


# -------------- S12: a DECLARING renderer hides a smuggled key from the projection identity
@dataclass(frozen=True)
class DeclaringLeakyRenderer:
    secret: str
    renderer_id: str = "declaring-leaky-v0"

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        base = dict(BackendNativeRenderer().render(envelope))
        base["coach_note"] = self.secret
        return base

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"GOAL_TEXT": envelope.pp, "GOAL_COUNT": envelope.n_goals}


@dataclass(frozen=True)
class HonestDeclaringRenderer:
    renderer_id: str = "declaring-honest-v0"

    def render(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"renderer_id": self.renderer_id, "goals_pp": envelope.pp,
                "n_goals": envelope.n_goals}

    def declare_information(self, envelope: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"GOAL_TEXT": envelope.pp, "GOAL_COUNT": envelope.n_goals}


def s12() -> None:
    envelope = BackendStateEnvelope(index=0, state_id="0", pp="⊢ 1 = 1", n_goals=1)
    leaky = project_workspace(DeclaringLeakyRenderer(secret="THE WHOLE ANSWER"), envelope)
    honest = project_workspace(HonestDeclaringRenderer(), envelope)
    parity = check_projection_parity(leaky.identity, honest.identity, InterventionClass.R_ONLY)
    record(
        "S12_declared_parity_hides_extra_information",
        parity.parity_holds and "coach_note" in leaky.rendered,
        projection_hashes_equal=parity.parity_holds,
        parity_admissible=parity.admissible,
        leaky_rendered_keys=sorted(leaky.rendered),
        honest_rendered_keys=sorted(honest.rendered),
        note="from_information trusts declare_information; only the from_rendered FALLBACK "
        "folds undeclared keys in",
    )
    # control: the same smuggling through a NON-declaring renderer
    nd_leaky = project_workspace(LeakyRenderer(secret="X"), envelope)
    nd_honest = project_workspace(BackendNativeRenderer(), envelope)
    parity_nd = check_projection_parity(
        nd_leaky.identity, nd_honest.identity, InterventionClass.R_ONLY
    )
    record(
        "S12b_undeclared_renderer_fallback_catches_it",
        parity_nd.parity_holds,
        note="control: the conservative fallback path",
    )


if __name__ == "__main__":
    for fn in (s1, s2, s3, s4, s5_s6, s7, s8, s9, s10, s11, s12):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            record(f"{fn.__name__}_CRASHED", False, error=f"{type(exc).__name__}: {exc}")
    emit("seal_and_leakage", RESULTS)
