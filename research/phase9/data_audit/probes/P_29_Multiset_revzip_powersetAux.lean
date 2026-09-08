/-
Copyright (c) 2018 Mario Carneiro. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Mario Carneiro
-/
import Mathlib.Data.List.Sublists
import Mathlib.Data.Multiset.Bind

#align_import data.multiset.powerset from "leanprover-community/mathlib"@"9003f28797c0664a49e4179487267c494477d853"

/-!
# The powerset of a multiset
-/

namespace Multiset

open List

variable {α : Type*}

/-! ### powerset -/

-- Porting note (#11215): TODO: Write a more efficient version
/-- A helper function for the powerset of a multiset. Given a list `l`, returns a list
of sublists of `l` as multisets. -/
def powersetAux (l : List α) : List (Multiset α) :=
  (sublists l).map (↑)
#align multiset.powerset_aux Multiset.powersetAux

theorem powersetAux_eq_map_coe {l : List α} : powersetAux l = (sublists l).map (↑) :=
  rfl
#align multiset.powerset_aux_eq_map_coe Multiset.powersetAux_eq_map_coe

@[simp]
theorem mem_powersetAux {l : List α} {s} : s ∈ powersetAux l ↔ s ≤ ↑l :=
  Quotient.inductionOn s <| by simp [powersetAux_eq_map_coe, Subperm, and_comm]
#align multiset.mem_powerset_aux Multiset.mem_powersetAux

/-- Helper function for the powerset of a multiset. Given a list `l`, returns a list
of sublists of `l` (using `sublists'`), as multisets. -/
def powersetAux' (l : List α) : List (Multiset α) :=
  (sublists' l).map (↑)
#align multiset.powerset_aux' Multiset.powersetAux'

theorem powersetAux_perm_powersetAux' {l : List α} : powersetAux l ~ powersetAux' l := by
  rw [powersetAux_eq_map_coe]; exact (sublists_perm_sublists' _).map _
#align multiset.powerset_aux_perm_powerset_aux' Multiset.powersetAux_perm_powersetAux'

@[simp]
theorem powersetAux'_nil : powersetAux' (@nil α) = [0] :=
  rfl
#align multiset.powerset_aux'_nil Multiset.powersetAux'_nil

@[simp]
theorem powersetAux'_cons (a : α) (l : List α) :
    powersetAux' (a :: l) = powersetAux' l ++ List.map (cons a) (powersetAux' l) := by
  simp only [powersetAux', sublists'_cons, map_append, List.map_map, append_cancel_left_eq]; rfl
#align multiset.powerset_aux'_cons Multiset.powersetAux'_cons

theorem powerset_aux'_perm {l₁ l₂ : List α} (p : l₁ ~ l₂) : powersetAux' l₁ ~ powersetAux' l₂ := by
  induction' p with a l₁ l₂ p IH a b l l₁ l₂ l₃ _ _ IH₁ IH₂
  · simp
  · simp only [powersetAux'_cons]
    exact IH.append (IH.map _)
  · simp only [powersetAux'_cons, map_append, List.map_map, append_assoc]
    apply Perm.append_left
    rw [← append_assoc, ← append_assoc,
      (by funext s; simp [cons_swap] : cons b ∘ cons a = cons a ∘ cons b)]
    exact perm_append_comm.append_right _
  · exact IH₁.trans IH₂
#align multiset.powerset_aux'_perm Multiset.powerset_aux'_perm

theorem powersetAux_perm {l₁ l₂ : List α} (p : l₁ ~ l₂) : powersetAux l₁ ~ powersetAux l₂ :=
  powersetAux_perm_powersetAux'.trans <|
    (powerset_aux'_perm p).trans powersetAux_perm_powersetAux'.symm
#align multiset.powerset_aux_perm Multiset.powersetAux_perm

--Porting note (#11083): slightly slower implementation due to `map ofList`
/-- The power set of a multiset. -/
def powerset (s : Multiset α) : Multiset (Multiset α) :=
  Quot.liftOn s
    (fun l => (powersetAux l : Multiset (Multiset α)))
    (fun _ _ h => Quot.sound (powersetAux_perm h))
#align multiset.powerset Multiset.powerset

theorem powerset_coe (l : List α) : @powerset α l = ((sublists l).map (↑) : List (Multiset α)) :=
  congr_arg ((↑) : List (Multiset α) → Multiset (Multiset α)) powersetAux_eq_map_coe
#align multiset.powerset_coe Multiset.powerset_coe

@[simp]
theorem powerset_coe' (l : List α) : @powerset α l = ((sublists' l).map (↑) : List (Multiset α)) :=
  Quot.sound powersetAux_perm_powersetAux'
#align multiset.powerset_coe' Multiset.powerset_coe'

@[simp]
theorem powerset_zero : @powerset α 0 = {0} :=
  rfl
#align multiset.powerset_zero Multiset.powerset_zero

@[simp]
theorem powerset_cons (a : α) (s) : powerset (a ::ₘ s) = powerset s + map (cons a) (powerset s) :=
  Quotient.inductionOn s fun l => by
    simp only [quot_mk_to_coe, cons_coe, powerset_coe', sublists'_cons, map_append, List.map_map,
      map_coe, coe_add, coe_eq_coe]; rfl
#align multiset.powerset_cons Multiset.powerset_cons

@[simp]
theorem mem_powerset {s t : Multiset α} : s ∈ powerset t ↔ s ≤ t :=
  Quotient.inductionOn₂ s t <| by simp [Subperm, and_comm]
#align multiset.mem_powerset Multiset.mem_powerset

theorem map_single_le_powerset (s : Multiset α) : s.map singleton ≤ powerset s :=
  Quotient.inductionOn s fun l => by
    simp only [powerset_coe, quot_mk_to_coe, coe_le, map_coe]
    show l.map (((↑) : List α → Multiset α) ∘ pure) <+~ (sublists l).map (↑)
    rw [← List.map_map]
    exact ((map_pure_sublist_sublists _).map _).subperm
#align multiset.map_single_le_powerset Multiset.map_single_le_powerset

@[simp]
theorem card_powerset (s : Multiset α) : card (powerset s) = 2 ^ card s :=
  Quotient.inductionOn s <| by simp
#align multiset.card_powerset Multiset.card_powerset

set_option maxHeartbeats 1000000 in
theorem probe_Multiset_revzip_powersetAux {l : List α} ⦃x⦄ (h : x ∈ revzip (powersetAux l)) : x.1 + x.2 = ↑l := by
  rw [revzip, powersetAux_eq_map_coe, ← map_reverse, zip_map, ← revzip, List.mem_map] at h
  trace_state
  simp only [Prod.map_apply, Prod.exists] at h
  trace_state
  rcases h with ⟨l₁, l₂, h, rfl, rfl⟩
  trace_state
  exact Quot.sound (revzip_sublists _ _ _ h)
  trace_state
