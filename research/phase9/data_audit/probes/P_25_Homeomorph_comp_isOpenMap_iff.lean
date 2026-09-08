/-
Copyright (c) 2019 Reid Barton. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Johannes Hölzl, Patrick Massot, Sébastien Gouëzel, Zhouhang Zhou, Reid Barton
-/
import Mathlib.Logic.Equiv.Fin
import Mathlib.Topology.DenseEmbedding
import Mathlib.Topology.Support
import Mathlib.Topology.Connected.LocallyConnected

#align_import topology.homeomorph from "leanprover-community/mathlib"@"4c3e1721c58ef9087bbc2c8c38b540f70eda2e53"

/-!
# Homeomorphisms

This file defines homeomorphisms between two topological spaces. They are bijections with both
directions continuous. We denote homeomorphisms with the notation `≃ₜ`.

# Main definitions

* `Homeomorph X Y`: The type of homeomorphisms from `X` to `Y`.
  This type can be denoted using the following notation: `X ≃ₜ Y`.

# Main results

* Pretty much every topological property is preserved under homeomorphisms.
* `Homeomorph.homeomorphOfContinuousOpen`: A continuous bijection that is
  an open map is a homeomorphism.

-/

open Set Filter

open Topology

variable {X : Type*} {Y : Type*} {Z : Type*}

-- not all spaces are homeomorphic to each other
/-- Homeomorphism between `X` and `Y`, also called topological isomorphism -/
structure Homeomorph (X : Type*) (Y : Type*) [TopologicalSpace X] [TopologicalSpace Y]
    extends X ≃ Y where
  /-- The forward map of a homeomorphism is a continuous function. -/
  continuous_toFun : Continuous toFun := by continuity
  /-- The inverse map of a homeomorphism is a continuous function. -/
  continuous_invFun : Continuous invFun := by continuity
#align homeomorph Homeomorph

@[inherit_doc]
infixl:25 " ≃ₜ " => Homeomorph

namespace Homeomorph

variable [TopologicalSpace X] [TopologicalSpace Y] [TopologicalSpace Z]
  {X' Y' : Type*} [TopologicalSpace X'] [TopologicalSpace Y']

theorem toEquiv_injective : Function.Injective (toEquiv : X ≃ₜ Y → X ≃ Y)
  | ⟨_, _, _⟩, ⟨_, _, _⟩, rfl => rfl
#align homeomorph.to_equiv_injective Homeomorph.toEquiv_injective

instance : EquivLike (X ≃ₜ Y) X Y where
  coe := fun h => h.toEquiv
  inv := fun h => h.toEquiv.symm
  left_inv := fun h => h.left_inv
  right_inv := fun h => h.right_inv
  coe_injective' := fun _ _ H _ => toEquiv_injective <| DFunLike.ext' H

instance : CoeFun (X ≃ₜ Y) fun _ ↦ X → Y := ⟨DFunLike.coe⟩

@[simp] theorem homeomorph_mk_coe (a : X ≃ Y) (b c) : (Homeomorph.mk a b c : X → Y) = a :=
  rfl
#align homeomorph.homeomorph_mk_coe Homeomorph.homeomorph_mk_coe

/-- The unique homeomorphism between two empty types. -/
protected def empty [IsEmpty X] [IsEmpty Y] : X ≃ₜ Y where
  __ := Equiv.equivOfIsEmpty X Y

/-- Inverse of a homeomorphism. -/
@[symm]
protected def symm (h : X ≃ₜ Y) : Y ≃ₜ X where
  continuous_toFun := h.continuous_invFun
  continuous_invFun := h.continuous_toFun
  toEquiv := h.toEquiv.symm
#align homeomorph.symm Homeomorph.symm

@[simp] theorem symm_symm (h : X ≃ₜ Y) : h.symm.symm = h := rfl
#align homeomorph.symm_symm Homeomorph.symm_symm

theorem symm_bijective : Function.Bijective (Homeomorph.symm : (X ≃ₜ Y) → Y ≃ₜ X) :=
  Function.bijective_iff_has_inverse.mpr ⟨_, symm_symm, symm_symm⟩

/-- See Note [custom simps projection] -/
def Simps.symm_apply (h : X ≃ₜ Y) : Y → X :=
  h.symm
#align homeomorph.simps.symm_apply Homeomorph.Simps.symm_apply

initialize_simps_projections Homeomorph (toFun → apply, invFun → symm_apply)

@[simp]
theorem coe_toEquiv (h : X ≃ₜ Y) : ⇑h.toEquiv = h :=
  rfl
#align homeomorph.coe_to_equiv Homeomorph.coe_toEquiv

@[simp]
theorem coe_symm_toEquiv (h : X ≃ₜ Y) : ⇑h.toEquiv.symm = h.symm :=
  rfl
#align homeomorph.coe_symm_to_equiv Homeomorph.coe_symm_toEquiv

@[ext]
theorem ext {h h' : X ≃ₜ Y} (H : ∀ x, h x = h' x) : h = h' :=
  DFunLike.ext _ _ H
#align homeomorph.ext Homeomorph.ext

/-- Identity map as a homeomorphism. -/
@[simps! (config := .asFn) apply]
protected def refl (X : Type*) [TopologicalSpace X] : X ≃ₜ X where
  continuous_toFun := continuous_id
  continuous_invFun := continuous_id
  toEquiv := Equiv.refl X
#align homeomorph.refl Homeomorph.refl

/-- Composition of two homeomorphisms. -/
@[trans]
protected def trans (h₁ : X ≃ₜ Y) (h₂ : Y ≃ₜ Z) : X ≃ₜ Z where
  continuous_toFun := h₂.continuous_toFun.comp h₁.continuous_toFun
  continuous_invFun := h₁.continuous_invFun.comp h₂.continuous_invFun
  toEquiv := Equiv.trans h₁.toEquiv h₂.toEquiv
#align homeomorph.trans Homeomorph.trans

@[simp]
theorem trans_apply (h₁ : X ≃ₜ Y) (h₂ : Y ≃ₜ Z) (x : X) : h₁.trans h₂ x = h₂ (h₁ x) :=
  rfl
#align homeomorph.trans_apply Homeomorph.trans_apply

@[simp]
theorem symm_trans_apply (f : X ≃ₜ Y) (g : Y ≃ₜ Z) (z : Z) :
    (f.trans g).symm z = f.symm (g.symm z) := rfl

@[simp]
theorem homeomorph_mk_coe_symm (a : X ≃ Y) (b c) :
    ((Homeomorph.mk a b c).symm : Y → X) = a.symm :=
  rfl
#align homeomorph.homeomorph_mk_coe_symm Homeomorph.homeomorph_mk_coe_symm

@[simp]
theorem refl_symm : (Homeomorph.refl X).symm = Homeomorph.refl X :=
  rfl
#align homeomorph.refl_symm Homeomorph.refl_symm

@[continuity, fun_prop]
protected theorem continuous (h : X ≃ₜ Y) : Continuous h :=
  h.continuous_toFun
#align homeomorph.continuous Homeomorph.continuous

-- otherwise `by continuity` can't prove continuity of `h.to_equiv.symm`
@[continuity]
protected theorem continuous_symm (h : X ≃ₜ Y) : Continuous h.symm :=
  h.continuous_invFun
#align homeomorph.continuous_symm Homeomorph.continuous_symm

@[simp]
theorem apply_symm_apply (h : X ≃ₜ Y) (y : Y) : h (h.symm y) = y :=
  h.toEquiv.apply_symm_apply y
#align homeomorph.apply_symm_apply Homeomorph.apply_symm_apply

@[simp]
theorem symm_apply_apply (h : X ≃ₜ Y) (x : X) : h.symm (h x) = x :=
  h.toEquiv.symm_apply_apply x
#align homeomorph.symm_apply_apply Homeomorph.symm_apply_apply

@[simp]
theorem self_trans_symm (h : X ≃ₜ Y) : h.trans h.symm = Homeomorph.refl X := by
  ext
  apply symm_apply_apply
#align homeomorph.self_trans_symm Homeomorph.self_trans_symm

@[simp]
theorem symm_trans_self (h : X ≃ₜ Y) : h.symm.trans h = Homeomorph.refl Y := by
  ext
  apply apply_symm_apply
#align homeomorph.symm_trans_self Homeomorph.symm_trans_self

protected theorem bijective (h : X ≃ₜ Y) : Function.Bijective h :=
  h.toEquiv.bijective
#align homeomorph.bijective Homeomorph.bijective

protected theorem injective (h : X ≃ₜ Y) : Function.Injective h :=
  h.toEquiv.injective
#align homeomorph.injective Homeomorph.injective

protected theorem surjective (h : X ≃ₜ Y) : Function.Surjective h :=
  h.toEquiv.surjective
#align homeomorph.surjective Homeomorph.surjective

/-- Change the homeomorphism `f` to make the inverse function definitionally equal to `g`. -/
def changeInv (f : X ≃ₜ Y) (g : Y → X) (hg : Function.RightInverse g f) : X ≃ₜ Y :=
  haveI : g = f.symm := (f.left_inv.eq_rightInverse hg).symm
  { toFun := f
    invFun := g
    left_inv := by convert f.left_inv
    right_inv := by convert f.right_inv using 1
    continuous_toFun := f.continuous
    continuous_invFun := by convert f.symm.continuous }
#align homeomorph.change_inv Homeomorph.changeInv

@[simp]
theorem symm_comp_self (h : X ≃ₜ Y) : h.symm ∘ h = id :=
  funext h.symm_apply_apply
#align homeomorph.symm_comp_self Homeomorph.symm_comp_self

@[simp]
theorem self_comp_symm (h : X ≃ₜ Y) : h ∘ h.symm = id :=
  funext h.apply_symm_apply
#align homeomorph.self_comp_symm Homeomorph.self_comp_symm

@[simp]
theorem range_coe (h : X ≃ₜ Y) : range h = univ :=
  h.surjective.range_eq
#align homeomorph.range_coe Homeomorph.range_coe

theorem image_symm (h : X ≃ₜ Y) : image h.symm = preimage h :=
  funext h.symm.toEquiv.image_eq_preimage
#align homeomorph.image_symm Homeomorph.image_symm

theorem preimage_symm (h : X ≃ₜ Y) : preimage h.symm = image h :=
  (funext h.toEquiv.image_eq_preimage).symm
#align homeomorph.preimage_symm Homeomorph.preimage_symm

@[simp]
theorem image_preimage (h : X ≃ₜ Y) (s : Set Y) : h '' (h ⁻¹' s) = s :=
  h.toEquiv.image_preimage s
#align homeomorph.image_preimage Homeomorph.image_preimage

@[simp]
theorem preimage_image (h : X ≃ₜ Y) (s : Set X) : h ⁻¹' (h '' s) = s :=
  h.toEquiv.preimage_image s
#align homeomorph.preimage_image Homeomorph.preimage_image

lemma image_compl (h : X ≃ₜ Y) (s : Set X) : h '' (sᶜ) = (h '' s)ᶜ :=
  h.toEquiv.image_compl s

protected theorem inducing (h : X ≃ₜ Y) : Inducing h :=
  inducing_of_inducing_compose h.continuous h.symm.continuous <| by
    simp only [symm_comp_self, inducing_id]
#align homeomorph.inducing Homeomorph.inducing

theorem induced_eq (h : X ≃ₜ Y) : TopologicalSpace.induced h ‹_› = ‹_› :=
  h.inducing.1.symm
#align homeomorph.induced_eq Homeomorph.induced_eq

protected theorem quotientMap (h : X ≃ₜ Y) : QuotientMap h :=
  QuotientMap.of_quotientMap_compose h.symm.continuous h.continuous <| by
    simp only [self_comp_symm, QuotientMap.id]
#align homeomorph.quotient_map Homeomorph.quotientMap

theorem coinduced_eq (h : X ≃ₜ Y) : TopologicalSpace.coinduced h ‹_› = ‹_› :=
  h.quotientMap.2.symm
#align homeomorph.coinduced_eq Homeomorph.coinduced_eq

protected theorem embedding (h : X ≃ₜ Y) : Embedding h :=
  ⟨h.inducing, h.injective⟩
#align homeomorph.embedding Homeomorph.embedding

/-- Homeomorphism given an embedding. -/
noncomputable def ofEmbedding (f : X → Y) (hf : Embedding f) : X ≃ₜ Set.range f where
  continuous_toFun := hf.continuous.subtype_mk _
  continuous_invFun := hf.continuous_iff.2 <| by simp [continuous_subtype_val]
  toEquiv := Equiv.ofInjective f hf.inj
#align homeomorph.of_embedding Homeomorph.ofEmbedding

protected theorem secondCountableTopology [SecondCountableTopology Y]
    (h : X ≃ₜ Y) : SecondCountableTopology X :=
  h.inducing.secondCountableTopology
#align homeomorph.second_countable_topology Homeomorph.secondCountableTopology

/-- If `h : X → Y` is a homeomorphism, `h(s)` is compact iff `s` is. -/
@[simp]
theorem isCompact_image {s : Set X} (h : X ≃ₜ Y) : IsCompact (h '' s) ↔ IsCompact s :=
  h.embedding.isCompact_iff.symm
#align homeomorph.is_compact_image Homeomorph.isCompact_image

/-- If `h : X → Y` is a homeomorphism, `h⁻¹(s)` is compact iff `s` is. -/
@[simp]
theorem isCompact_preimage {s : Set Y} (h : X ≃ₜ Y) : IsCompact (h ⁻¹' s) ↔ IsCompact s := by
  rw [← image_symm]; exact h.symm.isCompact_image
#align homeomorph.is_compact_preimage Homeomorph.isCompact_preimage

/-- If `h : X → Y` is a homeomorphism, `s` is σ-compact iff `h(s)` is. -/
@[simp]
theorem isSigmaCompact_image {s : Set X} (h : X ≃ₜ Y) :
    IsSigmaCompact (h '' s) ↔ IsSigmaCompact s :=
  h.embedding.isSigmaCompact_iff.symm

/-- If `h : X → Y` is a homeomorphism, `h⁻¹(s)` is σ-compact iff `s` is. -/
@[simp]
theorem isSigmaCompact_preimage {s : Set Y} (h : X ≃ₜ Y) :
    IsSigmaCompact (h ⁻¹' s) ↔ IsSigmaCompact s := by
  rw [← image_symm]; exact h.symm.isSigmaCompact_image

@[simp]
theorem isPreconnected_image {s : Set X} (h : X ≃ₜ Y) :
    IsPreconnected (h '' s) ↔ IsPreconnected s :=
  ⟨fun hs ↦ by simpa only [image_symm, preimage_image]
    using hs.image _ h.symm.continuous.continuousOn,
    fun hs ↦ hs.image _ h.continuous.continuousOn⟩

@[simp]
theorem isPreconnected_preimage {s : Set Y} (h : X ≃ₜ Y) :
    IsPreconnected (h ⁻¹' s) ↔ IsPreconnected s := by
  rw [← image_symm, isPreconnected_image]

@[simp]
theorem isConnected_image {s : Set X} (h : X ≃ₜ Y) :
    IsConnected (h '' s) ↔ IsConnected s :=
  image_nonempty.and h.isPreconnected_image

@[simp]
theorem isConnected_preimage {s : Set Y} (h : X ≃ₜ Y) :
    IsConnected (h ⁻¹' s) ↔ IsConnected s := by
  rw [← image_symm, isConnected_image]

theorem image_connectedComponentIn {s : Set X} (h : X ≃ₜ Y) {x : X} (hx : x ∈ s) :
    h '' connectedComponentIn s x = connectedComponentIn (h '' s) (h x) := by
  refine (h.continuous.image_connectedComponentIn_subset hx).antisymm ?_
  have := h.symm.continuous.image_connectedComponentIn_subset (mem_image_of_mem h hx)
  rwa [image_subset_iff, h.preimage_symm, h.image_symm, h.preimage_image, h.symm_apply_apply]
    at this

@[simp]
theorem comap_cocompact (h : X ≃ₜ Y) : comap h (cocompact Y) = cocompact X :=
  (comap_cocompact_le h.continuous).antisymm <|
    (hasBasis_cocompact.le_basis_iff (hasBasis_cocompact.comap h)).2 fun K hK =>
      ⟨h ⁻¹' K, h.isCompact_preimage.2 hK, Subset.rfl⟩
#align homeomorph.comap_cocompact Homeomorph.comap_cocompact

@[simp]
theorem map_cocompact (h : X ≃ₜ Y) : map h (cocompact X) = cocompact Y := by
  rw [← h.comap_cocompact, map_comap_of_surjective h.surjective]
#align homeomorph.map_cocompact Homeomorph.map_cocompact

protected theorem compactSpace [CompactSpace X] (h : X ≃ₜ Y) : CompactSpace Y where
  isCompact_univ := h.symm.isCompact_preimage.2 isCompact_univ
#align homeomorph.compact_space Homeomorph.compactSpace

protected theorem t0Space [T0Space X] (h : X ≃ₜ Y) : T0Space Y :=
  h.symm.embedding.t0Space
#align homeomorph.t0_space Homeomorph.t0Space

protected theorem t1Space [T1Space X] (h : X ≃ₜ Y) : T1Space Y :=
  h.symm.embedding.t1Space
#align homeomorph.t1_space Homeomorph.t1Space

protected theorem t2Space [T2Space X] (h : X ≃ₜ Y) : T2Space Y :=
  h.symm.embedding.t2Space
#align homeomorph.t2_space Homeomorph.t2Space

protected theorem t3Space [T3Space X] (h : X ≃ₜ Y) : T3Space Y :=
  h.symm.embedding.t3Space
#align homeomorph.t3_space Homeomorph.t3Space

protected theorem denseEmbedding (h : X ≃ₜ Y) : DenseEmbedding h :=
  { h.embedding with dense := h.surjective.denseRange }
#align homeomorph.dense_embedding Homeomorph.denseEmbedding

@[simp]
theorem isOpen_preimage (h : X ≃ₜ Y) {s : Set Y} : IsOpen (h ⁻¹' s) ↔ IsOpen s :=
  h.quotientMap.isOpen_preimage
#align homeomorph.is_open_preimage Homeomorph.isOpen_preimage

@[simp]
theorem isOpen_image (h : X ≃ₜ Y) {s : Set X} : IsOpen (h '' s) ↔ IsOpen s := by
  rw [← preimage_symm, isOpen_preimage]
#align homeomorph.is_open_image Homeomorph.isOpen_image

protected theorem isOpenMap (h : X ≃ₜ Y) : IsOpenMap h := fun _ => h.isOpen_image.2
#align homeomorph.is_open_map Homeomorph.isOpenMap

@[simp]
theorem isClosed_preimage (h : X ≃ₜ Y) {s : Set Y} : IsClosed (h ⁻¹' s) ↔ IsClosed s := by
  simp only [← isOpen_compl_iff, ← preimage_compl, isOpen_preimage]
#align homeomorph.is_closed_preimage Homeomorph.isClosed_preimage

@[simp]
theorem isClosed_image (h : X ≃ₜ Y) {s : Set X} : IsClosed (h '' s) ↔ IsClosed s := by
  rw [← preimage_symm, isClosed_preimage]
#align homeomorph.is_closed_image Homeomorph.isClosed_image

protected theorem isClosedMap (h : X ≃ₜ Y) : IsClosedMap h := fun _ => h.isClosed_image.2
#align homeomorph.is_closed_map Homeomorph.isClosedMap

protected theorem openEmbedding (h : X ≃ₜ Y) : OpenEmbedding h :=
  openEmbedding_of_embedding_open h.embedding h.isOpenMap
#align homeomorph.open_embedding Homeomorph.openEmbedding

protected theorem closedEmbedding (h : X ≃ₜ Y) : ClosedEmbedding h :=
  closedEmbedding_of_embedding_closed h.embedding h.isClosedMap
#align homeomorph.closed_embedding Homeomorph.closedEmbedding

protected theorem normalSpace [NormalSpace X] (h : X ≃ₜ Y) : NormalSpace Y :=
  h.symm.closedEmbedding.normalSpace

protected theorem t4Space [T4Space X] (h : X ≃ₜ Y) : T4Space Y :=
  h.symm.closedEmbedding.t4Space
#align homeomorph.normal_space Homeomorph.t4Space

theorem preimage_closure (h : X ≃ₜ Y) (s : Set Y) : h ⁻¹' closure s = closure (h ⁻¹' s) :=
  h.isOpenMap.preimage_closure_eq_closure_preimage h.continuous _
#align homeomorph.preimage_closure Homeomorph.preimage_closure

theorem image_closure (h : X ≃ₜ Y) (s : Set X) : h '' closure s = closure (h '' s) := by
  rw [← preimage_symm, preimage_closure]
#align homeomorph.image_closure Homeomorph.image_closure

theorem preimage_interior (h : X ≃ₜ Y) (s : Set Y) : h ⁻¹' interior s = interior (h ⁻¹' s) :=
  h.isOpenMap.preimage_interior_eq_interior_preimage h.continuous _
#align homeomorph.preimage_interior Homeomorph.preimage_interior

theorem image_interior (h : X ≃ₜ Y) (s : Set X) : h '' interior s = interior (h '' s) := by
  rw [← preimage_symm, preimage_interior]
#align homeomorph.image_interior Homeomorph.image_interior

theorem preimage_frontier (h : X ≃ₜ Y) (s : Set Y) : h ⁻¹' frontier s = frontier (h ⁻¹' s) :=
  h.isOpenMap.preimage_frontier_eq_frontier_preimage h.continuous _
#align homeomorph.preimage_frontier Homeomorph.preimage_frontier

theorem image_frontier (h : X ≃ₜ Y) (s : Set X) : h '' frontier s = frontier (h '' s) := by
  rw [← preimage_symm, preimage_frontier]
#align homeomorph.image_frontier Homeomorph.image_frontier

@[to_additive]
theorem _root_.HasCompactMulSupport.comp_homeomorph {M} [One M] {f : Y → M}
    (hf : HasCompactMulSupport f) (φ : X ≃ₜ Y) : HasCompactMulSupport (f ∘ φ) :=
  hf.comp_closedEmbedding φ.closedEmbedding
#align has_compact_mul_support.comp_homeomorph HasCompactMulSupport.comp_homeomorph
#align has_compact_support.comp_homeomorph HasCompactSupport.comp_homeomorph

@[simp]
theorem map_nhds_eq (h : X ≃ₜ Y) (x : X) : map h (𝓝 x) = 𝓝 (h x) :=
  h.embedding.map_nhds_of_mem _ (by simp)
#align homeomorph.map_nhds_eq Homeomorph.map_nhds_eq

@[simp]
theorem map_punctured_nhds_eq (h : X ≃ₜ Y) (x : X) : map h (𝓝[≠] x) = 𝓝[≠] (h x) := by
  convert h.embedding.map_nhdsWithin_eq ({x}ᶜ) x
  rw [h.image_compl, Set.image_singleton]

theorem symm_map_nhds_eq (h : X ≃ₜ Y) (x : X) : map h.symm (𝓝 (h x)) = 𝓝 x := by
  rw [h.symm.map_nhds_eq, h.symm_apply_apply]
#align homeomorph.symm_map_nhds_eq Homeomorph.symm_map_nhds_eq

theorem nhds_eq_comap (h : X ≃ₜ Y) (x : X) : 𝓝 x = comap h (𝓝 (h x)) :=
  h.inducing.nhds_eq_comap x
#align homeomorph.nhds_eq_comap Homeomorph.nhds_eq_comap

@[simp]
theorem comap_nhds_eq (h : X ≃ₜ Y) (y : Y) : comap h (𝓝 y) = 𝓝 (h.symm y) := by
  rw [h.nhds_eq_comap, h.apply_symm_apply]
#align homeomorph.comap_nhds_eq Homeomorph.comap_nhds_eq

/-- If the codomain of a homeomorphism is a locally connected space, then the domain is also
a locally connected space. -/
theorem locallyConnectedSpace [i : LocallyConnectedSpace Y] (h : X ≃ₜ Y) :
    LocallyConnectedSpace X := by
  have : ∀ x, (𝓝 x).HasBasis (fun s ↦ IsOpen s ∧ h x ∈ s ∧ IsConnected s)
      (h.symm '' ·) := fun x ↦ by
    rw [← h.symm_map_nhds_eq]
    exact (i.1 _).map _
  refine locallyConnectedSpace_of_connected_bases _ _ this fun _ _ hs ↦ ?_
  exact hs.2.2.2.image _ h.symm.continuous.continuousOn

/-- The codomain of a homeomorphism is a locally compact space if and only if
the domain is a locally compact space. -/
theorem locallyCompactSpace_iff (h : X ≃ₜ Y) :
    LocallyCompactSpace X ↔ LocallyCompactSpace Y := by
  exact ⟨fun _ => h.symm.openEmbedding.locallyCompactSpace,
    fun _ => h.closedEmbedding.locallyCompactSpace⟩

/-- If a bijective map `e : X ≃ Y` is continuous and open, then it is a homeomorphism. -/
def homeomorphOfContinuousOpen (e : X ≃ Y) (h₁ : Continuous e) (h₂ : IsOpenMap e) : X ≃ₜ Y where
  continuous_toFun := h₁
  continuous_invFun := by
    rw [continuous_def]
    intro s hs
    convert ← h₂ s hs using 1
    apply e.image_eq_preimage
  toEquiv := e
#align homeomorph.homeomorph_of_continuous_open Homeomorph.homeomorphOfContinuousOpen

@[simp]
theorem comp_continuousOn_iff (h : X ≃ₜ Y) (f : Z → X) (s : Set Z) :
    ContinuousOn (h ∘ f) s ↔ ContinuousOn f s :=
  h.inducing.continuousOn_iff.symm
#align homeomorph.comp_continuous_on_iff Homeomorph.comp_continuousOn_iff

@[simp]
theorem comp_continuous_iff (h : X ≃ₜ Y) {f : Z → X} : Continuous (h ∘ f) ↔ Continuous f :=
  h.inducing.continuous_iff.symm
#align homeomorph.comp_continuous_iff Homeomorph.comp_continuous_iff

@[simp]
theorem comp_continuous_iff' (h : X ≃ₜ Y) {f : Y → Z} : Continuous (f ∘ h) ↔ Continuous f :=
  h.quotientMap.continuous_iff.symm
#align homeomorph.comp_continuous_iff' Homeomorph.comp_continuous_iff'

theorem comp_continuousAt_iff (h : X ≃ₜ Y) (f : Z → X) (z : Z) :
    ContinuousAt (h ∘ f) z ↔ ContinuousAt f z :=
  h.inducing.continuousAt_iff.symm
#align homeomorph.comp_continuous_at_iff Homeomorph.comp_continuousAt_iff

theorem comp_continuousAt_iff' (h : X ≃ₜ Y) (f : Y → Z) (x : X) :
    ContinuousAt (f ∘ h) x ↔ ContinuousAt f (h x) :=
  h.inducing.continuousAt_iff' (by simp)
#align homeomorph.comp_continuous_at_iff' Homeomorph.comp_continuousAt_iff'

theorem comp_continuousWithinAt_iff (h : X ≃ₜ Y) (f : Z → X) (s : Set Z) (z : Z) :
    ContinuousWithinAt f s z ↔ ContinuousWithinAt (h ∘ f) s z :=
  h.inducing.continuousWithinAt_iff
#align homeomorph.comp_continuous_within_at_iff Homeomorph.comp_continuousWithinAt_iff

set_option maxHeartbeats 1000000 in
theorem probe_Homeomorph_comp_isOpenMap_iff (h : X ≃ₜ Y) {f : Z → X} : IsOpenMap (h ∘ f) ↔ IsOpenMap f := by
  refine ⟨?_, fun hf => h.isOpenMap.comp hf⟩
  trace_state
  intro hf
  trace_state
  rw [← Function.id_comp f, ← h.symm_comp_self, Function.comp.assoc]
  trace_state
  exact h.symm.isOpenMap.comp hf
  trace_state
