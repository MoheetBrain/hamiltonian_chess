/-
Copyright (c) 2019 Anne Baanen. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Anne Baanen
-/
import Mathlib.Algebra.Regular.Basic
import Mathlib.LinearAlgebra.Matrix.MvPolynomial
import Mathlib.LinearAlgebra.Matrix.Polynomial
import Mathlib.RingTheory.Polynomial.Basic

#align_import linear_algebra.matrix.adjugate from "leanprover-community/mathlib"@"a99f85220eaf38f14f94e04699943e185a5e1d1a"

/-!
# Cramer's rule and adjugate matrices

The adjugate matrix is the transpose of the cofactor matrix.
It is calculated with Cramer's rule, which we introduce first.
The vectors returned by Cramer's rule are given by the linear map `cramer`,
which sends a matrix `A` and vector `b` to the vector consisting of the
determinant of replacing the `i`th column of `A` with `b` at index `i`
(written as `(A.update_column i b).det`).
Using Cramer's rule, we can compute for each matrix `A` the matrix `adjugate A`.
The entries of the adjugate are the minors of `A`.
Instead of defining a minor by deleting row `i` and column `j` of `A`, we
replace the `i`th row of `A` with the `j`th basis vector; the resulting matrix
has the same determinant but more importantly equals Cramer's rule applied
to `A` and the `j`th basis vector, simplifying the subsequent proofs.
We prove the adjugate behaves like `det A • A⁻¹`.

## Main definitions

 * `Matrix.cramer A b`: the vector output by Cramer's rule on `A` and `b`.
 * `Matrix.adjugate A`: the adjugate (or classical adjoint) of the matrix `A`.

## References

  * https://en.wikipedia.org/wiki/Cramer's_rule#Finding_inverse_matrix

## Tags

cramer, cramer's rule, adjugate
-/


namespace Matrix

universe u v w

variable {m : Type u} {n : Type v} {α : Type w}
variable [DecidableEq n] [Fintype n] [DecidableEq m] [Fintype m] [CommRing α]

open Matrix Polynomial Equiv Equiv.Perm Finset

section Cramer

/-!
  ### `cramer` section

  Introduce the linear map `cramer` with values defined by `cramerMap`.
  After defining `cramerMap` and showing it is linear,
  we will restrict our proofs to using `cramer`.
-/


variable (A : Matrix n n α) (b : n → α)

/-- `cramerMap A b i` is the determinant of the matrix `A` with column `i` replaced with `b`,
  and thus `cramerMap A b` is the vector output by Cramer's rule on `A` and `b`.

  If `A * x = b` has a unique solution in `x`, `cramerMap A` sends the vector `b` to `A.det • x`.
  Otherwise, the outcome of `cramerMap` is well-defined but not necessarily useful.
-/
def cramerMap (i : n) : α :=
  (A.updateColumn i b).det
#align matrix.cramer_map Matrix.cramerMap

theorem cramerMap_is_linear (i : n) : IsLinearMap α fun b => cramerMap A b i :=
  { map_add := det_updateColumn_add _ _
    map_smul := det_updateColumn_smul _ _ }
#align matrix.cramer_map_is_linear Matrix.cramerMap_is_linear

theorem cramer_is_linear : IsLinearMap α (cramerMap A) := by
  constructor <;> intros <;> ext i
  · apply (cramerMap_is_linear A i).1
  · apply (cramerMap_is_linear A i).2
#align matrix.cramer_is_linear Matrix.cramer_is_linear

/-- `cramer A b i` is the determinant of the matrix `A` with column `i` replaced with `b`,
  and thus `cramer A b` is the vector output by Cramer's rule on `A` and `b`.

  If `A * x = b` has a unique solution in `x`, `cramer A` sends the vector `b` to `A.det • x`.
  Otherwise, the outcome of `cramer` is well-defined but not necessarily useful.
 -/
def cramer (A : Matrix n n α) : (n → α) →ₗ[α] (n → α) :=
  IsLinearMap.mk' (cramerMap A) (cramer_is_linear A)
#align matrix.cramer Matrix.cramer

theorem cramer_apply (i : n) : cramer A b i = (A.updateColumn i b).det :=
  rfl
#align matrix.cramer_apply Matrix.cramer_apply

theorem cramer_transpose_apply (i : n) : cramer Aᵀ b i = (A.updateRow i b).det := by
  rw [cramer_apply, updateColumn_transpose, det_transpose]
#align matrix.cramer_transpose_apply Matrix.cramer_transpose_apply

theorem cramer_transpose_row_self (i : n) : Aᵀ.cramer (A i) = Pi.single i A.det := by
  ext j
  rw [cramer_apply, Pi.single_apply]
  split_ifs with h
  · -- i = j: this entry should be `A.det`
    subst h
    simp only [updateColumn_transpose, det_transpose, updateRow_eq_self]
  · -- i ≠ j: this entry should be 0
    rw [updateColumn_transpose, det_transpose]
    apply det_zero_of_row_eq h
    rw [updateRow_self, updateRow_ne (Ne.symm h)]
#align matrix.cramer_transpose_row_self Matrix.cramer_transpose_row_self

theorem cramer_row_self (i : n) (h : ∀ j, b j = A j i) : A.cramer b = Pi.single i A.det := by
  rw [← transpose_transpose A, det_transpose]
  convert cramer_transpose_row_self Aᵀ i
  exact funext h
#align matrix.cramer_row_self Matrix.cramer_row_self

@[simp]
theorem cramer_one : cramer (1 : Matrix n n α) = 1 := by
  -- Porting note: was `ext i j`
  refine LinearMap.pi_ext' (fun (i : n) => LinearMap.ext_ring (funext (fun (j : n) => ?_)))
  convert congr_fun (cramer_row_self (1 : Matrix n n α) (Pi.single i 1) i _) j
  · simp
  · intro j
    rw [Matrix.one_eq_pi_single, Pi.single_comm]
#align matrix.cramer_one Matrix.cramer_one

theorem cramer_smul (r : α) (A : Matrix n n α) :
    cramer (r • A) = r ^ (Fintype.card n - 1) • cramer A :=
  LinearMap.ext fun _ => funext fun _ => det_updateColumn_smul' _ _ _ _
#align matrix.cramer_smul Matrix.cramer_smul

@[simp]
theorem cramer_subsingleton_apply [Subsingleton n] (A : Matrix n n α) (b : n → α) (i : n) :
    cramer A b i = b i := by rw [cramer_apply, det_eq_elem_of_subsingleton _ i, updateColumn_self]
#align matrix.cramer_subsingleton_apply Matrix.cramer_subsingleton_apply

theorem cramer_zero [Nontrivial n] : cramer (0 : Matrix n n α) = 0 := by
  ext i j
  obtain ⟨j', hj'⟩ : ∃ j', j' ≠ j := exists_ne j
  apply det_eq_zero_of_column_eq_zero j'
  intro j''
  simp [updateColumn_ne hj']
#align matrix.cramer_zero Matrix.cramer_zero

/-- Use linearity of `cramer` to take it out of a summation. -/
theorem sum_cramer {β} (s : Finset β) (f : β → n → α) :
    (∑ x ∈ s, cramer A (f x)) = cramer A (∑ x ∈ s, f x) :=
  (map_sum (cramer A) ..).symm
#align matrix.sum_cramer Matrix.sum_cramer

set_option maxHeartbeats 1000000 in
theorem probe_Matrix_sum_cramer_apply {β} (s : Finset β) (f : n → β → α) (i : n) :
    (∑ x ∈ s, cramer A (fun j => f j x) i) = cramer A (fun j : n => ∑ x ∈ s, f j x) i :=
  calc
    (∑ x ∈ s, cramer A (fun j => f j x) i) = (∑ x ∈ s, cramer A fun j => f j x) i :=
      (Finset.sum_apply i s _).symm
    _ = cramer A (fun j : n => ∑ x ∈ s, f j x) i := by
  rw [sum_cramer, cramer_apply, cramer_apply]
  trace_state
  simp only [updateColumn]
  trace_state
  congr with j
  trace_state
  congr
  trace_state
  apply Finset.sum_apply
  trace_state
