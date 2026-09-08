/-
Copyright (c) 2017 Scott Morrison. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Scott Morrison, Adam Topaz
-/
import Mathlib.CategoryTheory.ConcreteCategory.Basic
import Mathlib.CategoryTheory.Limits.Preserves.Basic
import Mathlib.CategoryTheory.Limits.TypesFiltered
import Mathlib.CategoryTheory.Limits.Yoneda
import Mathlib.Tactic.ApplyFun

#align_import category_theory.limits.concrete_category from "leanprover-community/mathlib"@"c3019c79074b0619edb4b27553a91b2e82242395"

/-!
# Facts about (co)limits of functors into concrete categories
-/


universe t w v u r

open CategoryTheory

namespace CategoryTheory.Limits

attribute [local instance] ConcreteCategory.instFunLike ConcreteCategory.hasCoeToSort

section Limits

/-- If a functor `G : J ⥤ C` to a concrete category has a limit and that `forget C`
is corepresentable, then `G ⋙ forget C).sections` is small. -/
lemma Concrete.small_sections_of_hasLimit
    {C : Type u} [Category.{v} C] [ConcreteCategory.{v} C]
    [(forget C).Corepresentable] {J : Type w} [Category.{t} J] (G : J ⥤ C) [HasLimit G] :
    Small.{v} (G ⋙ forget C).sections := by
  rw [← Types.hasLimit_iff_small_sections]
  infer_instance

variable {C : Type u} [Category.{v} C] [ConcreteCategory.{max w v} C] {J : Type w} [Category.{t} J]
  (F : J ⥤ C) [PreservesLimit F (forget C)]

theorem Concrete.to_product_injective_of_isLimit {D : Cone F} (hD : IsLimit D) :
    Function.Injective fun (x : D.pt) (j : J) => D.π.app j x := by
  let E := (forget C).mapCone D
  let hE : IsLimit E := isLimitOfPreserves _ hD
  let G := Types.limitCone.{w, v} (F ⋙ forget C)
  let hG := Types.limitConeIsLimit.{w, v} (F ⋙ forget C)
  let T : E.pt ≅ G.pt := hE.conePointUniqueUpToIso hG
  change Function.Injective (T.hom ≫ fun x j => G.π.app j x)
  have h : Function.Injective T.hom := by
    intro a b h
    suffices T.inv (T.hom a) = T.inv (T.hom b) by simpa
    rw [h]
  suffices Function.Injective fun (x : G.pt) j => G.π.app j x by exact this.comp h
  apply Subtype.ext
#align category_theory.limits.concrete.to_product_injective_of_is_limit CategoryTheory.Limits.Concrete.to_product_injective_of_isLimit

theorem Concrete.isLimit_ext {D : Cone F} (hD : IsLimit D) (x y : D.pt) :
    (∀ j, D.π.app j x = D.π.app j y) → x = y := fun h =>
  Concrete.to_product_injective_of_isLimit _ hD (funext h)
#align category_theory.limits.concrete.is_limit_ext CategoryTheory.Limits.Concrete.isLimit_ext

theorem Concrete.limit_ext [HasLimit F] (x y : ↑(limit F)) :
    (∀ j, limit.π F j x = limit.π F j y) → x = y :=
  Concrete.isLimit_ext F (limit.isLimit _) _ _
#align category_theory.limits.concrete.limit_ext CategoryTheory.Limits.Concrete.limit_ext

end Limits

section Colimits

section

variable {C : Type u} [Category.{v} C] [ConcreteCategory.{t} C] {J : Type w} [Category.{r} J]
  (F : J ⥤ C) [PreservesColimit F (forget C)]

set_option maxHeartbeats 1000000 in
theorem probe_CategoryTheory_Limits_Concrete_from_union_surjective_of_isColimit {D : Cocone F} (hD : IsColimit D) :
    let ff : (Σj : J, F.obj j) → D.pt := fun a => D.ι.app a.1 a.2
    Function.Surjective ff := by
  intro ff x
  trace_state
  let E : Cocone (F ⋙ forget C) := (forget C).mapCocone D
  trace_state
  let hE : IsColimit E := isColimitOfPreserves (forget C) hD
  trace_state
  obtain ⟨j, y, hy⟩ := Types.jointly_surjective_of_isColimit hE x
  trace_state
  exact ⟨⟨j, y⟩, hy⟩
  trace_state
