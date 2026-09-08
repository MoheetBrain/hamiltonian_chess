/-
Copyright (c) 2020 Joseph Myers. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Joseph Myers
-/
import Mathlib.LinearAlgebra.AffineSpace.AffineEquiv

#align_import linear_algebra.affine_space.affine_subspace from "leanprover-community/mathlib"@"e96bdfbd1e8c98a09ff75f7ac6204d142debc840"

/-!
# Affine spaces

This file defines affine subspaces (over modules) and the affine span of a set of points.

## Main definitions

* `AffineSubspace k P` is the type of affine subspaces. Unlike affine spaces, affine subspaces are
  allowed to be empty, and lemmas that do not apply to empty affine subspaces have `Nonempty`
  hypotheses. There is a `CompleteLattice` structure on affine subspaces.
* `AffineSubspace.direction` gives the `Submodule` spanned by the pairwise differences of points
  in an `AffineSubspace`. There are various lemmas relating to the set of vectors in the
  `direction`, and relating the lattice structure on affine subspaces to that on their directions.
* `AffineSubspace.parallel`, notation `∥`, gives the property of two affine subspaces being
  parallel (one being a translate of the other).
* `affineSpan` gives the affine subspace spanned by a set of points, with `vectorSpan` giving its
  direction. The `affineSpan` is defined in terms of `spanPoints`, which gives an explicit
  description of the points contained in the affine span; `spanPoints` itself should generally only
  be used when that description is required, with `affineSpan` being the main definition for other
  purposes. Two other descriptions of the affine span are proved equivalent: it is the `sInf` of
  affine subspaces containing the points, and (if `[Nontrivial k]`) it contains exactly those points
  that are affine combinations of points in the given set.

## Implementation notes

`outParam` is used in the definition of `AddTorsor V P` to make `V` an implicit argument (deduced
from `P`) in most cases. As for modules, `k` is an explicit argument rather than implied by `P` or
`V`.

This file only provides purely algebraic definitions and results. Those depending on analysis or
topology are defined elsewhere; see `Analysis.NormedSpace.AddTorsor` and `Topology.Algebra.Affine`.

## References

* https://en.wikipedia.org/wiki/Affine_space
* https://en.wikipedia.org/wiki/Principal_homogeneous_space
-/

noncomputable section

open Affine

open Set

section

variable (k : Type*) {V : Type*} {P : Type*} [Ring k] [AddCommGroup V] [Module k V]
variable [AffineSpace V P]

/-- The submodule spanning the differences of a (possibly empty) set of points. -/
def vectorSpan (s : Set P) : Submodule k V :=
  Submodule.span k (s -ᵥ s)
#align vector_span vectorSpan

/-- The definition of `vectorSpan`, for rewriting. -/
theorem vectorSpan_def (s : Set P) : vectorSpan k s = Submodule.span k (s -ᵥ s) :=
  rfl
#align vector_span_def vectorSpan_def

/-- `vectorSpan` is monotone. -/
theorem vectorSpan_mono {s₁ s₂ : Set P} (h : s₁ ⊆ s₂) : vectorSpan k s₁ ≤ vectorSpan k s₂ :=
  Submodule.span_mono (vsub_self_mono h)
#align vector_span_mono vectorSpan_mono

variable (P)

/-- The `vectorSpan` of the empty set is `⊥`. -/
@[simp]
theorem vectorSpan_empty : vectorSpan k (∅ : Set P) = (⊥ : Submodule k V) := by
  rw [vectorSpan_def, vsub_empty, Submodule.span_empty]
#align vector_span_empty vectorSpan_empty

variable {P}

/-- The `vectorSpan` of a single point is `⊥`. -/
@[simp]
theorem vectorSpan_singleton (p : P) : vectorSpan k ({p} : Set P) = ⊥ := by simp [vectorSpan_def]
#align vector_span_singleton vectorSpan_singleton

/-- The `s -ᵥ s` lies within the `vectorSpan k s`. -/
theorem vsub_set_subset_vectorSpan (s : Set P) : s -ᵥ s ⊆ ↑(vectorSpan k s) :=
  Submodule.subset_span
#align vsub_set_subset_vector_span vsub_set_subset_vectorSpan

/-- Each pairwise difference is in the `vectorSpan`. -/
theorem vsub_mem_vectorSpan {s : Set P} {p1 p2 : P} (hp1 : p1 ∈ s) (hp2 : p2 ∈ s) :
    p1 -ᵥ p2 ∈ vectorSpan k s :=
  vsub_set_subset_vectorSpan k s (vsub_mem_vsub hp1 hp2)
#align vsub_mem_vector_span vsub_mem_vectorSpan

/-- The points in the affine span of a (possibly empty) set of points. Use `affineSpan` instead to
get an `AffineSubspace k P`. -/
def spanPoints (s : Set P) : Set P :=
  { p | ∃ p1 ∈ s, ∃ v ∈ vectorSpan k s, p = v +ᵥ p1 }
#align span_points spanPoints

/-- A point in a set is in its affine span. -/
theorem mem_spanPoints (p : P) (s : Set P) : p ∈ s → p ∈ spanPoints k s
  | hp => ⟨p, hp, 0, Submodule.zero_mem _, (zero_vadd V p).symm⟩
#align mem_span_points mem_spanPoints

/-- A set is contained in its `spanPoints`. -/
theorem subset_spanPoints (s : Set P) : s ⊆ spanPoints k s := fun p => mem_spanPoints k p s
#align subset_span_points subset_spanPoints

/-- The `spanPoints` of a set is nonempty if and only if that set is. -/
@[simp]
theorem spanPoints_nonempty (s : Set P) : (spanPoints k s).Nonempty ↔ s.Nonempty := by
  constructor
  · contrapose
    rw [Set.not_nonempty_iff_eq_empty, Set.not_nonempty_iff_eq_empty]
    intro h
    simp [h, spanPoints]
  · exact fun h => h.mono (subset_spanPoints _ _)
#align span_points_nonempty spanPoints_nonempty

/-- Adding a point in the affine span and a vector in the spanning submodule produces a point in the
affine span. -/
theorem vadd_mem_spanPoints_of_mem_spanPoints_of_mem_vectorSpan {s : Set P} {p : P} {v : V}
    (hp : p ∈ spanPoints k s) (hv : v ∈ vectorSpan k s) : v +ᵥ p ∈ spanPoints k s := by
  rcases hp with ⟨p2, ⟨hp2, ⟨v2, ⟨hv2, hv2p⟩⟩⟩⟩
  rw [hv2p, vadd_vadd]
  exact ⟨p2, hp2, v + v2, (vectorSpan k s).add_mem hv hv2, rfl⟩
#align vadd_mem_span_points_of_mem_span_points_of_mem_vector_span vadd_mem_spanPoints_of_mem_spanPoints_of_mem_vectorSpan

set_option maxHeartbeats 1000000 in
theorem probe_vsub_mem_vectorSpan_of_mem_spanPoints_of_mem_spanPoints {s : Set P} {p1 p2 : P}
    (hp1 : p1 ∈ spanPoints k s) (hp2 : p2 ∈ spanPoints k s) : p1 -ᵥ p2 ∈ vectorSpan k s := by
  rcases hp1 with ⟨p1a, ⟨hp1a, ⟨v1, ⟨hv1, hv1p⟩⟩⟩⟩
  trace_state
  rcases hp2 with ⟨p2a, ⟨hp2a, ⟨v2, ⟨hv2, hv2p⟩⟩⟩⟩
  trace_state
  rw [hv1p, hv2p, vsub_vadd_eq_vsub_sub (v1 +ᵥ p1a), vadd_vsub_assoc, add_comm, add_sub_assoc]
  trace_state
  have hv1v2 : v1 - v2 ∈ vectorSpan k s := (vectorSpan k s).sub_mem hv1 hv2
  trace_state
  refine (vectorSpan k s).add_mem ?_ hv1v2
  trace_state
  exact vsub_mem_vectorSpan k hp1a hp2a
  trace_state
