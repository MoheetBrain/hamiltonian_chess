"""Verified long-horizon trajectories: the inner MDP ``M_L`` and its truth kernel ``T_K``.

The maximum horizon anywhere else in this repository is **1**
(``arena/tasks/generators/world_v0.py`` constructs the only ``CanonicalTrajectory`` and passes a
one-element tuple).  This package is the substrate for horizons greater than one.

Three modules, three responsibilities:

``schema``
    The :class:`~arena.trajectory.schema.VerifiedTrajectory` record and its **backend-native state
    envelope**.  Deliberately does *not* project Lean states into ``arena-canonical-v0.1.0``:
    ``docs/CANONICAL_VNEXT_PILOT.md`` measured 0 of 368 real Lean states mapping losslessly.

``lean_backend``
    ``T_K`` — a process-level driver for the already-compiled ``lean_dojo_repl`` tactic against a
    built mathlib4.  Truth is the Lean elaborator's and the Lean kernel's, never a string
    comparison against a recorded transcript.

``arena_v0``
    ``M_L`` — ``reset``/``step`` over live Lean, with the observation function ``Ω_L`` *injected*
    rather than baked in, a leakage filter, a reference-proof replay driver, and a CLI that builds
    and re-verifies a bank of trajectories.

Nothing here calls a model.
"""

from __future__ import annotations

from arena.trajectory.schema import (
    TRAJECTORY_SCHEMA_VERSION,
    Actor,
    BackendStateEnvelope,
    CanonicalProjectionStatus,
    DerivedView,
    EvidenceKind,
    FormalBackend,
    Horizon,
    PPScope,
    SourceVersion,
    TerminalStatus,
    TrajectoryAction,
    TrajectoryProvenance,
    Verdict,
    VerifiedTrajectory,
    VerifierEvidence,
)

__all__ = [
    "TRAJECTORY_SCHEMA_VERSION",
    "Actor",
    "BackendStateEnvelope",
    "CanonicalProjectionStatus",
    "DerivedView",
    "EvidenceKind",
    "FormalBackend",
    "Horizon",
    "PPScope",
    "SourceVersion",
    "TerminalStatus",
    "TrajectoryAction",
    "TrajectoryProvenance",
    "Verdict",
    "VerifiedTrajectory",
    "VerifierEvidence",
]
