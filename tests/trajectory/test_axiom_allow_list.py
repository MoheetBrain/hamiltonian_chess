"""RT-01 regression: the closure verdict consults the axiom allow-list (red team 2026-09-08).

The original defect was not a missing detection. ``ofReduceBool`` WAS detected and stored in
``KernelVerification.contains_of_reduce_bool`` -- and then never read by ``verified``, so
``native_decide`` closed any decidable goal with full reward. An evolutionary search would have
found that within minutes, because the reward paid for closure and charged nothing for it.

The fix is an ALLOW-LIST, not another deny-list entry: a deny-list has to anticipate the next
exotic axiom, an allow-list fails closed on all of them.
"""

from __future__ import annotations

import pytest

from arena.trajectory.lean_backend import TRUSTED_AXIOMS, untrusted_axioms


def test_allow_list_is_leans_standard_classical_base() -> None:
    assert set(TRUSTED_AXIOMS) == {"propext", "Classical.choice", "Quot.sound"}


def test_a_normal_mathlib_proof_is_trusted() -> None:
    assert untrusted_axioms(["propext", "Classical.choice", "Quot.sound"]) == ()


def test_a_proof_with_no_axioms_at_all_is_trusted() -> None:
    """`rfl`-style proofs report none; they must not be penalised (RT-17 fails safe the other way)."""

    assert untrusted_axioms([]) == ()


@pytest.mark.parametrize(
    "axiom",
    ["Lean.ofReduceBool", "sorryAx", "SomeMadeUpAxiom", "Lean.trustCompiler"],
)
def test_anything_outside_the_allow_list_is_refused(axiom: str) -> None:
    """Including axioms no deny-list would have anticipated."""

    assert untrusted_axioms(["propext", axiom]) == (axiom,)


def test_native_decide_is_specifically_refused() -> None:
    """RT-01's exact payload: native_decide moves trust from the kernel to the compiler."""

    assert "Lean.ofReduceBool" in untrusted_axioms(["propext", "Lean.ofReduceBool"])


def test_untrusted_axioms_are_deduplicated_and_ordered() -> None:
    assert untrusted_axioms(["B", "A", "B", "propext", "A"]) == ("B", "A")


def test_whitespace_does_not_smuggle_an_axiom_past_the_list() -> None:
    assert untrusted_axioms(["  propext  "]) == ()
    assert untrusted_axioms(["  sorryAx  "]) == ("sorryAx",)
