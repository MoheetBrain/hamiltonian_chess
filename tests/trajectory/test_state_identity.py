"""The two state identities, and precisely what each one is and is not allowed to claim.

Every test here runs without Lean: identity is a property of the recorded envelope and of the
renderer's declaration, not of a live process.  The Lean-backed checks that the identities behave
this way on *real* states live in ``test_task.py`` and are marked ``slow``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from arena.evolution.record import InterventionClass
from arena.trajectory.arena_v0 import BackendNativeRenderer, GoalTextRenderer
from arena.trajectory.schema import BackendStateEnvelope, PPScope
from arena.trajectory.state_identity import (
    GOAL_TEXT_NORMALIZATION,
    LEAN_TACTIC_WORKSPACE,
    UNDECLARED_SLOT_PREFIX,
    BackendSessionRef,
    InformationDeclaringRenderer,
    InformationSlot,
    KernelStateIdentity,
    WorkspaceProjectionIdentity,
    check_projection_parity,
    goal_digest_of,
    normalize_goal_text,
    project_workspace,
)

FINSET_SCOPE = PPScope(current_namespace="Finset", open_declarations=("Finset",))
BARE_SCOPE = PPScope()


def envelope(
    text: str = "a b : Nat\n⊢ a + b = b + a",
    *,
    state_id: str = "3",
    scope: PPScope = BARE_SCOPE,
) -> BackendStateEnvelope:
    return BackendStateEnvelope(index=0, state_id=state_id, pp=text, pp_scope=scope, n_goals=1)


def session(name: str) -> BackendSessionRef:
    return BackendSessionRef(session_id=name)


# =============================================================================================
# Normalisation: shallow, named, and not a semantic claim
# =============================================================================================


def test_normalisation_is_presentational_only() -> None:
    noisy = "\r\n  a b : Nat   \r\n⊢ a + b = b + a\t\n\n"
    clean = "  a b : Nat\n⊢ a + b = b + a"
    assert normalize_goal_text(noisy) == clean
    # leading indentation inside a line is NOT touched: it may be Lean's own structure
    assert normalize_goal_text("  x") == "  x"


def test_normalisation_does_not_reorder_or_rename_anything() -> None:
    """Anything deeper would be a semantic claim this project cannot support (0/368 lossless)."""

    first = "a : Nat\nb : Nat\n⊢ P a b"
    swapped = "b : Nat\na : Nat\n⊢ P a b"
    assert normalize_goal_text(first) != normalize_goal_text(swapped)
    assert normalize_goal_text("⊢ ∀ x, P x") != normalize_goal_text("⊢ ∀ y, P y")


def test_normalisation_name_travels_in_the_digest() -> None:
    """A future change of normalisation must show up as a different identity, not a silent drift."""

    identity = KernelStateIdentity.from_envelope(envelope(), session=session("s1"))
    assert identity.normalization == GOAL_TEXT_NORMALIZATION
    assert identity.to_dict()["normalization"] == GOAL_TEXT_NORMALIZATION


# =============================================================================================
# KernelStateIdentity
# =============================================================================================


def test_kernel_key_is_independent_of_how_the_state_was_printed() -> None:
    """The identity requirement: a pretty-print change that does not change the state.

    Re-rendering the same backend state -- a different scope, different ``pp`` options, a
    different renderer -- must leave the kernel identity alone.  Only the re-elaboration key,
    which is explicitly a *rendering* fingerprint, moves.
    """

    identity = KernelStateIdentity.from_envelope(
        envelope("⊢ Finset.univ = Finset.univ"), session=session("s1")
    )
    reprinted = identity.rendered_under("⊢ univ = univ", FINSET_SCOPE)

    assert identity.same_kernel_state_as(reprinted)
    assert reprinted.same_kernel_state_as(identity)
    assert identity.kernel_key == reprinted.kernel_key
    assert not identity.same_after_reelaboration_as(reprinted)


def test_reelaboration_key_survives_presentational_noise_that_byte_equality_rejects() -> None:
    """Not a raw string comparison: identity is over normalised text bound to its scope."""

    plain = envelope("a b : Nat\n⊢ a + b = b + a")
    noisy = envelope("a b : Nat  \r\n⊢ a + b = b + a\n\n", state_id="9")
    left = KernelStateIdentity.from_envelope(plain, session=session("s1"))
    right = KernelStateIdentity.from_envelope(noisy, session=session("s2"))

    assert plain.pp != noisy.pp  # raw bytes differ
    assert left.same_after_reelaboration_as(right)
    assert not left.same_kernel_state_as(right)  # different sessions, different live handles


def test_a_state_handle_is_meaningless_across_sessions() -> None:
    left = KernelStateIdentity.from_envelope(envelope(state_id="3"), session=session("ep1"))
    right = KernelStateIdentity.from_envelope(envelope(state_id="3"), session=session("ep2"))
    assert not left.same_kernel_state_as(right)
    assert left.same_after_reelaboration_as(right)


def test_scope_dependence_is_recorded_rather_than_resolved() -> None:
    """The 40.6% / 98.1% trap, made explicit instead of papered over.

    ``univ`` under ``open Finset`` and ``Finset.univ`` without it are the same mathematics and
    have different re-elaboration keys.  ``False`` here means UNKNOWN.  Nothing in this module
    is permitted to turn that into "different states".
    """

    scoped = KernelStateIdentity.from_envelope(
        envelope("⊢ univ = univ", scope=FINSET_SCOPE), session=session("s1")
    )
    bare = KernelStateIdentity.from_envelope(
        envelope("⊢ Finset.univ = Finset.univ", scope=BARE_SCOPE), session=session("s1")
    )
    assert not scoped.same_after_reelaboration_as(bare)
    assert scoped.scope_digest != bare.scope_digest
    assert scoped.goal_digest != bare.goal_digest


def test_identical_goal_text_under_different_scopes_is_not_the_same_identity() -> None:
    """The converse trap: equal ``pp`` under different scopes need not be equal mathematics."""

    left = KernelStateIdentity.from_envelope(
        envelope("⊢ univ = univ", scope=FINSET_SCOPE), session=session("s1")
    )
    right = KernelStateIdentity.from_envelope(
        envelope("⊢ univ = univ", scope=BARE_SCOPE), session=session("s1")
    )
    assert left.goal_digest == right.goal_digest
    assert not left.same_after_reelaboration_as(right)


def test_the_live_session_and_the_record_session_answer_different_questions() -> None:
    """``arena_v0.derive_session_id`` is content-addressed: two live episodes can share it.

    A live handle from a closed session cannot be branched to, so the *live* session is what
    :attr:`kernel_key` uses; the record binding is carried beside it for cross-referencing a
    stored ``VerifiedTrajectory`` and is deliberately not allowed to decide addressability.
    """

    recorded = BackendStateEnvelope(
        index=0, state_id="3", pp="⊢ p", session_id="sess-content-addressed"
    )
    first = KernelStateIdentity.from_envelope(recorded, session=session("ep1"))
    second = KernelStateIdentity.from_envelope(recorded, session=session("ep2"))

    assert first.record_session_id == second.record_session_id == "sess-content-addressed"
    assert first.record_key == second.record_key
    assert not first.same_kernel_state_as(second)
    assert first.identity_hash != second.identity_hash


def test_an_envelope_without_a_record_binding_degrades_to_empty() -> None:
    identity = KernelStateIdentity.from_envelope(envelope(), session=session("ep1"))
    assert identity.record_session_id == ""
    assert identity.kernel_key.endswith("|ep1|3")


def test_identity_hash_is_deterministic_and_round_trips() -> None:
    identity = KernelStateIdentity.from_envelope(envelope(), session=session("s1"))
    twin = KernelStateIdentity.from_envelope(envelope(), session=session("s1"))
    assert identity.identity_hash == twin.identity_hash
    restored = KernelStateIdentity.from_dict(identity.to_dict())
    assert restored == identity
    assert restored.identity_hash == identity.identity_hash


def test_goal_digest_of_separates_the_two_digests() -> None:
    goal_a, scope_a = goal_digest_of("⊢ p", BARE_SCOPE)
    goal_b, scope_b = goal_digest_of("⊢ p", FINSET_SCOPE)
    assert goal_a == goal_b
    assert scope_a != scope_b


def test_scope_identity_is_order_insensitive() -> None:
    left = PPScope(open_declarations=("Finset", "Nat"))
    right = PPScope(open_declarations=("Nat", "Finset"))
    assert goal_digest_of("⊢ p", left)[1] == goal_digest_of("⊢ p", right)[1]


# =============================================================================================
# WorkspaceProjectionIdentity: two R_ONLY languages, different bytes, one identity
# =============================================================================================


class VerboseSlotRenderer:
    """An ``R_ONLY`` candidate: chatty, boxed, verbose key names."""

    renderer_id = "verbose-slots-v0"

    def render(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        return {
            "renderer_id": self.renderer_id,
            "banner": "=== PROOF WORKSPACE ===",
            "current_obligation": state.pp,
            "obligations_open": f"there are {state.n_goals} open obligation(s)",
        }

    def declare_information(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        return {
            InformationSlot.GOAL_TEXT: state.pp,
            InformationSlot.GOAL_COUNT: state.n_goals,
        }


class TerseSlotRenderer:
    """The same declared information as :class:`VerboseSlotRenderer`, in a different alphabet."""

    renderer_id = "terse-slots-v0"

    def render(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"renderer_id": self.renderer_id, "g": state.pp, "n": state.n_goals}

    def declare_information(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        # deliberately the other declaration order, to prove order does not matter
        return {
            InformationSlot.GOAL_COUNT: state.n_goals,
            InformationSlot.GOAL_TEXT: state.pp,
        }


class GoalOnlySlotRenderer:
    """An ``O_CHANGE`` candidate: it withholds the goal count.  Not an ``R_ONLY`` sibling."""

    renderer_id = "goal-only-slots-v0"

    def render(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        return {"renderer_id": self.renderer_id, "g": state.pp}

    def declare_information(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
        return {InformationSlot.GOAL_TEXT: state.pp}


def test_two_r_only_renderers_agree_on_identity_and_disagree_on_bytes() -> None:
    """The property the whole class exists for (manual §12.3)."""

    state = envelope()
    verbose = project_workspace(VerboseSlotRenderer(), state)
    terse = project_workspace(TerseSlotRenderer(), state)

    assert dict(verbose.rendered) != dict(terse.rendered)
    assert verbose.identity.rendered_bytes_digest != terse.identity.rendered_bytes_digest
    assert verbose.identity.projection_hash == terse.identity.projection_hash
    assert verbose.identity.same_declared_information_as(terse.identity)
    assert verbose.identity.differs_only_in_rendering(terse.identity)
    assert verbose.identity.slots_were_declared
    assert verbose.identity.exposed_slots == ("GOAL_COUNT", "GOAL_TEXT")


def test_renderer_id_and_rendered_bytes_are_excluded_from_the_projection_hash() -> None:
    state = envelope()
    identity = project_workspace(VerboseSlotRenderer(), state).identity
    relabelled = WorkspaceProjectionIdentity(
        workspace_kind=identity.workspace_kind,
        exposed_slots=identity.exposed_slots,
        information_digest=identity.information_digest,
        renderer_id="some-other-language",
        rendered_bytes_digest="0" * 64,
    )
    assert relabelled.projection_hash == identity.projection_hash


def test_an_o_change_renderer_legitimately_differs_and_is_not_a_violation() -> None:
    state = envelope()
    full = project_workspace(TerseSlotRenderer(), state).identity
    reduced = project_workspace(
        GoalOnlySlotRenderer(), state, intervention_class=InterventionClass.O_CHANGE
    ).identity

    assert not full.same_declared_information_as(reduced)
    verdict = check_projection_parity(full, reduced, InterventionClass.O_CHANGE)
    assert not verdict.parity_required
    assert verdict.admissible
    assert "does not require visible-information parity" in verdict.explanation


def test_the_same_difference_under_r_only_is_a_violation() -> None:
    state = envelope()
    full = project_workspace(TerseSlotRenderer(), state).identity
    reduced = project_workspace(GoalOnlySlotRenderer(), state).identity
    verdict = check_projection_parity(full, reduced, InterventionClass.R_ONLY)
    assert verdict.parity_required
    assert not verdict.parity_holds
    assert not verdict.admissible
    assert "GOAL_COUNT" in verdict.explanation


def test_r_only_parity_holds_for_the_declared_pair() -> None:
    state = envelope()
    verdict = check_projection_parity(
        project_workspace(VerboseSlotRenderer(), state).identity,
        project_workspace(TerseSlotRenderer(), state).identity,
        InterventionClass.R_ONLY,
    )
    assert verdict.parity_holds
    assert verdict.bytes_differ
    assert verdict.admissible


def test_an_undeclared_renderer_gets_a_conservative_identity() -> None:
    """No declaration, no parity: a renamed key is treated as different information."""

    class UndeclaredRenderer:
        renderer_id = "undeclared-v0"

        def render(self, state: BackendStateEnvelope) -> Mapping[str, Any]:
            return {"renderer_id": self.renderer_id, "goal": state.pp, "count": state.n_goals}

    state = envelope()
    identity = project_workspace(UndeclaredRenderer(), state).identity
    assert not identity.slots_were_declared
    assert f"{UNDECLARED_SLOT_PREFIX}goal" in identity.exposed_slots
    assert not identity.same_declared_information_as(
        project_workspace(TerseSlotRenderer(), state).identity
    )


def test_the_arena_default_renderers_are_projected_without_a_declaration() -> None:
    state = envelope()
    native = project_workspace(BackendNativeRenderer(), state).identity
    text_only = project_workspace(GoalTextRenderer(), state).identity

    assert not native.slots_were_declared
    assert native.workspace_kind == LEAN_TACTIC_WORKSPACE
    assert "GOAL_TEXT" in native.exposed_slots
    assert "GOAL_COUNT" in native.exposed_slots
    # GoalTextRenderer shows strictly less: it is an O_CHANGE contrast arm, not an R_ONLY sibling
    assert text_only.exposed_slots == ("GOAL_TEXT",)
    assert not native.same_declared_information_as(text_only)


def test_a_derived_digest_key_carries_no_information_of_its_own() -> None:
    """``pp_sha256`` is a function of the goal text already in ``GOAL_TEXT``; it adds no slot."""

    identity = project_workspace(BackendNativeRenderer(), envelope()).identity
    assert not any(slot.startswith(UNDECLARED_SLOT_PREFIX) for slot in identity.exposed_slots)


def test_extra_episode_slots_participate_in_the_identity() -> None:
    state = envelope()
    without = project_workspace(TerseSlotRenderer(), state).identity
    with_budget = project_workspace(
        TerseSlotRenderer(), state, extra={"ATTEMPTS_REMAINING": 7}
    ).identity
    other_budget = project_workspace(
        TerseSlotRenderer(), state, extra={"ATTEMPTS_REMAINING": 6}
    ).identity

    assert not without.same_declared_information_as(with_budget)
    assert not with_budget.same_declared_information_as(other_budget)


def test_projection_identity_round_trips() -> None:
    identity = project_workspace(VerboseSlotRenderer(), envelope()).identity
    restored = WorkspaceProjectionIdentity.from_dict(identity.to_dict())
    assert restored == identity
    assert restored.projection_hash == identity.projection_hash


def test_the_declaring_protocol_is_structural() -> None:
    assert isinstance(VerboseSlotRenderer(), InformationDeclaringRenderer)
    assert not isinstance(BackendNativeRenderer(), InformationDeclaringRenderer)
