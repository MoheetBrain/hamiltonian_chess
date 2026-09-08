/-
Copyright (c) 2017 Johannes Hölzl. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Johannes Hölzl, Mario Carneiro, Yury Kudryashov
-/
import Mathlib.Order.Filter.Basic
import Mathlib.Topology.Bases
import Mathlib.Data.Set.Accumulate
import Mathlib.Topology.Bornology.Basic
import Mathlib.Topology.LocallyFinite
/-!
# Compact sets and compact spaces

## Main definitions

We define the following properties for sets in a topological space:

* `IsCompact`: a set such that each open cover has a finite subcover. This is defined in mathlib
  using filters. The main property of a compact set is `IsCompact.elim_finite_subcover`.
* `CompactSpace`: typeclass stating that the whole space is a compact set.
* `NoncompactSpace`: a space that is not a compact space.

## Main results

* `isCompact_univ_pi`: **Tychonov's theorem** - an arbitrary product of compact sets
  is compact.
-/

open Set Filter Topology TopologicalSpace Classical Function

universe u v

variable {X : Type u} {Y : Type v} {ι : Type*}
variable [TopologicalSpace X] [TopologicalSpace Y] {s t : Set X}

-- compact sets
section Compact

lemma IsCompact.exists_clusterPt (hs : IsCompact s) {f : Filter X} [NeBot f] (hf : f ≤ 𝓟 s) :
    ∃ x ∈ s, ClusterPt x f := hs hf

lemma IsCompact.exists_mapClusterPt {ι : Type*} (hs : IsCompact s) {f : Filter ι} [NeBot f]
    {u : ι → X} (hf : Filter.map u f ≤ 𝓟 s) :
    ∃ x ∈ s, MapClusterPt x f u := hs hf

/-- The complement to a compact set belongs to a filter `f` if it belongs to each filter
`𝓝 x ⊓ f`, `x ∈ s`. -/
theorem IsCompact.compl_mem_sets (hs : IsCompact s) {f : Filter X} (hf : ∀ x ∈ s, sᶜ ∈ 𝓝 x ⊓ f) :
    sᶜ ∈ f := by
  contrapose! hf
  simp only [not_mem_iff_inf_principal_compl, compl_compl, inf_assoc] at hf ⊢
  exact @hs _ hf inf_le_right
#align is_compact.compl_mem_sets IsCompact.compl_mem_sets

/-- The complement to a compact set belongs to a filter `f` if each `x ∈ s` has a neighborhood `t`
within `s` such that `tᶜ` belongs to `f`. -/
theorem IsCompact.compl_mem_sets_of_nhdsWithin (hs : IsCompact s) {f : Filter X}
    (hf : ∀ x ∈ s, ∃ t ∈ 𝓝[s] x, tᶜ ∈ f) : sᶜ ∈ f := by
  refine hs.compl_mem_sets fun x hx => ?_
  rcases hf x hx with ⟨t, ht, hst⟩
  replace ht := mem_inf_principal.1 ht
  apply mem_inf_of_inter ht hst
  rintro x ⟨h₁, h₂⟩ hs
  exact h₂ (h₁ hs)
#align is_compact.compl_mem_sets_of_nhds_within IsCompact.compl_mem_sets_of_nhdsWithin

/-- If `p : Set X → Prop` is stable under restriction and union, and each point `x`
  of a compact set `s` has a neighborhood `t` within `s` such that `p t`, then `p s` holds. -/
@[elab_as_elim]
theorem IsCompact.induction_on (hs : IsCompact s) {p : Set X → Prop} (he : p ∅)
    (hmono : ∀ ⦃s t⦄, s ⊆ t → p t → p s) (hunion : ∀ ⦃s t⦄, p s → p t → p (s ∪ t))
    (hnhds : ∀ x ∈ s, ∃ t ∈ 𝓝[s] x, p t) : p s := by
  let f : Filter X := comk p he (fun _t ht _s hsub ↦ hmono hsub ht) (fun _s hs _t ht ↦ hunion hs ht)
  have : sᶜ ∈ f := hs.compl_mem_sets_of_nhdsWithin (by simpa [f] using hnhds)
  rwa [← compl_compl s]
#align is_compact.induction_on IsCompact.induction_on

/-- The intersection of a compact set and a closed set is a compact set. -/
theorem IsCompact.inter_right (hs : IsCompact s) (ht : IsClosed t) : IsCompact (s ∩ t) := by
  intro f hnf hstf
  obtain ⟨x, hsx, hx⟩ : ∃ x ∈ s, ClusterPt x f :=
    hs (le_trans hstf (le_principal_iff.2 inter_subset_left))
  have : x ∈ t := ht.mem_of_nhdsWithin_neBot <|
    hx.mono <| le_trans hstf (le_principal_iff.2 inter_subset_right)
  exact ⟨x, ⟨hsx, this⟩, hx⟩
#align is_compact.inter_right IsCompact.inter_right

/-- The intersection of a closed set and a compact set is a compact set. -/
theorem IsCompact.inter_left (ht : IsCompact t) (hs : IsClosed s) : IsCompact (s ∩ t) :=
  inter_comm t s ▸ ht.inter_right hs
#align is_compact.inter_left IsCompact.inter_left

/-- The set difference of a compact set and an open set is a compact set. -/
theorem IsCompact.diff (hs : IsCompact s) (ht : IsOpen t) : IsCompact (s \ t) :=
  hs.inter_right (isClosed_compl_iff.mpr ht)
#align is_compact.diff IsCompact.diff

/-- A closed subset of a compact set is a compact set. -/
theorem IsCompact.of_isClosed_subset (hs : IsCompact s) (ht : IsClosed t) (h : t ⊆ s) :
    IsCompact t :=
  inter_eq_self_of_subset_right h ▸ hs.inter_right ht
#align is_compact_of_is_closed_subset IsCompact.of_isClosed_subset

theorem IsCompact.image_of_continuousOn {f : X → Y} (hs : IsCompact s) (hf : ContinuousOn f s) :
    IsCompact (f '' s) := by
  intro l lne ls
  have : NeBot (l.comap f ⊓ 𝓟 s) :=
    comap_inf_principal_neBot_of_image_mem lne (le_principal_iff.1 ls)
  obtain ⟨x, hxs, hx⟩ : ∃ x ∈ s, ClusterPt x (l.comap f ⊓ 𝓟 s) := @hs _ this inf_le_right
  haveI := hx.neBot
  use f x, mem_image_of_mem f hxs
  have : Tendsto f (𝓝 x ⊓ (comap f l ⊓ 𝓟 s)) (𝓝 (f x) ⊓ l) := by
    convert (hf x hxs).inf (@tendsto_comap _ _ f l) using 1
    rw [nhdsWithin]
    ac_rfl
  exact this.neBot
#align is_compact.image_of_continuous_on IsCompact.image_of_continuousOn

theorem IsCompact.image {f : X → Y} (hs : IsCompact s) (hf : Continuous f) : IsCompact (f '' s) :=
  hs.image_of_continuousOn hf.continuousOn
#align is_compact.image IsCompact.image

theorem IsCompact.adherence_nhdset {f : Filter X} (hs : IsCompact s) (hf₂ : f ≤ 𝓟 s)
    (ht₁ : IsOpen t) (ht₂ : ∀ x ∈ s, ClusterPt x f → x ∈ t) : t ∈ f :=
  Classical.by_cases mem_of_eq_bot fun (this : f ⊓ 𝓟 tᶜ ≠ ⊥) =>
    let ⟨x, hx, (hfx : ClusterPt x <| f ⊓ 𝓟 tᶜ)⟩ := @hs _ ⟨this⟩ <| inf_le_of_left_le hf₂
    have : x ∈ t := ht₂ x hx hfx.of_inf_left
    have : tᶜ ∩ t ∈ 𝓝[tᶜ] x := inter_mem_nhdsWithin _ (IsOpen.mem_nhds ht₁ this)
    have A : 𝓝[tᶜ] x = ⊥ := empty_mem_iff_bot.1 <| compl_inter_self t ▸ this
    have : 𝓝[tᶜ] x ≠ ⊥ := hfx.of_inf_right.ne
    absurd A this
#align is_compact.adherence_nhdset IsCompact.adherence_nhdset

theorem isCompact_iff_ultrafilter_le_nhds :
    IsCompact s ↔ ∀ f : Ultrafilter X, ↑f ≤ 𝓟 s → ∃ x ∈ s, ↑f ≤ 𝓝 x := by
  refine (forall_neBot_le_iff ?_).trans ?_
  · rintro f g hle ⟨x, hxs, hxf⟩
    exact ⟨x, hxs, hxf.mono hle⟩
  · simp only [Ultrafilter.clusterPt_iff]
#align is_compact_iff_ultrafilter_le_nhds isCompact_iff_ultrafilter_le_nhds

alias ⟨IsCompact.ultrafilter_le_nhds, _⟩ := isCompact_iff_ultrafilter_le_nhds
#align is_compact.ultrafilter_le_nhds IsCompact.ultrafilter_le_nhds

theorem isCompact_iff_ultrafilter_le_nhds' :
    IsCompact s ↔ ∀ f : Ultrafilter X, s ∈ f → ∃ x ∈ s, ↑f ≤ 𝓝 x := by
  simp only [isCompact_iff_ultrafilter_le_nhds, le_principal_iff, Ultrafilter.mem_coe]

alias ⟨IsCompact.ultrafilter_le_nhds', _⟩ := isCompact_iff_ultrafilter_le_nhds'

/-- If a compact set belongs to a filter and this filter has a unique cluster point `y` in this set,
then the filter is less than or equal to `𝓝 y`. -/
lemma IsCompact.le_nhds_of_unique_clusterPt (hs : IsCompact s) {l : Filter X} {y : X}
    (hmem : s ∈ l) (h : ∀ x ∈ s, ClusterPt x l → x = y) : l ≤ 𝓝 y := by
  refine le_iff_ultrafilter.2 fun f hf ↦ ?_
  rcases hs.ultrafilter_le_nhds' f (hf hmem) with ⟨x, hxs, hx⟩
  convert ← hx
  exact h x hxs (.mono (.of_le_nhds hx) hf)

/-- If values of `f : Y → X` belong to a compact set `s` eventually along a filter `l`
and `y` is a unique `MapClusterPt` for `f` along `l` in `s`,
then `f` tends to `𝓝 y` along `l`. -/
lemma IsCompact.tendsto_nhds_of_unique_mapClusterPt {l : Filter Y} {y : X} {f : Y → X}
    (hs : IsCompact s) (hmem : ∀ᶠ x in l, f x ∈ s) (h : ∀ x ∈ s, MapClusterPt x l f → x = y) :
    Tendsto f l (𝓝 y) :=
  hs.le_nhds_of_unique_clusterPt (mem_map.2 hmem) h

/-- For every open directed cover of a compact set, there exists a single element of the
cover which itself includes the set. -/
theorem IsCompact.elim_directed_cover {ι : Type v} [hι : Nonempty ι] (hs : IsCompact s)
    (U : ι → Set X) (hUo : ∀ i, IsOpen (U i)) (hsU : s ⊆ ⋃ i, U i) (hdU : Directed (· ⊆ ·) U) :
    ∃ i, s ⊆ U i :=
  hι.elim fun i₀ =>
    IsCompact.induction_on hs ⟨i₀, empty_subset _⟩ (fun _ _ hs ⟨i, hi⟩ => ⟨i, hs.trans hi⟩)
      (fun _ _ ⟨i, hi⟩ ⟨j, hj⟩ =>
        let ⟨k, hki, hkj⟩ := hdU i j
        ⟨k, union_subset (Subset.trans hi hki) (Subset.trans hj hkj)⟩)
      fun _x hx =>
      let ⟨i, hi⟩ := mem_iUnion.1 (hsU hx)
      ⟨U i, mem_nhdsWithin_of_mem_nhds (IsOpen.mem_nhds (hUo i) hi), i, Subset.refl _⟩
#align is_compact.elim_directed_cover IsCompact.elim_directed_cover

/-- For every open cover of a compact set, there exists a finite subcover. -/
theorem IsCompact.elim_finite_subcover {ι : Type v} (hs : IsCompact s) (U : ι → Set X)
    (hUo : ∀ i, IsOpen (U i)) (hsU : s ⊆ ⋃ i, U i) : ∃ t : Finset ι, s ⊆ ⋃ i ∈ t, U i :=
  hs.elim_directed_cover _ (fun _ => isOpen_biUnion fun i _ => hUo i)
    (iUnion_eq_iUnion_finset U ▸ hsU)
    (directed_of_isDirected_le fun _ _ h => biUnion_subset_biUnion_left h)
#align is_compact.elim_finite_subcover IsCompact.elim_finite_subcover

lemma IsCompact.elim_nhds_subcover_nhdsSet' (hs : IsCompact s) (U : ∀ x ∈ s, Set X)
    (hU : ∀ x hx, U x hx ∈ 𝓝 x) : ∃ t : Finset s, (⋃ x ∈ t, U x.1 x.2) ∈ 𝓝ˢ s := by
  rcases hs.elim_finite_subcover (fun x : s ↦ interior (U x x.2)) (fun _ ↦ isOpen_interior)
    fun x hx ↦ mem_iUnion.2 ⟨⟨x, hx⟩, mem_interior_iff_mem_nhds.2 <| hU _ _⟩ with ⟨t, hst⟩
  refine ⟨t, mem_nhdsSet_iff_forall.2 fun x hx ↦ ?_⟩
  rcases mem_iUnion₂.1 (hst hx) with ⟨y, hyt, hy⟩
  refine mem_of_superset ?_ (subset_biUnion_of_mem hyt)
  exact mem_interior_iff_mem_nhds.1 hy

lemma IsCompact.elim_nhds_subcover_nhdsSet (hs : IsCompact s) {U : X → Set X}
    (hU : ∀ x ∈ s, U x ∈ 𝓝 x) : ∃ t : Finset X, (∀ x ∈ t, x ∈ s) ∧ (⋃ x ∈ t, U x) ∈ 𝓝ˢ s :=
  let ⟨t, ht⟩ := hs.elim_nhds_subcover_nhdsSet' (fun x _ => U x) hU
  ⟨t.image (↑), fun x hx =>
    let ⟨y, _, hyx⟩ := Finset.mem_image.1 hx
    hyx ▸ y.2,
    by rwa [Finset.set_biUnion_finset_image]⟩

theorem IsCompact.elim_nhds_subcover' (hs : IsCompact s) (U : ∀ x ∈ s, Set X)
    (hU : ∀ x (hx : x ∈ s), U x ‹x ∈ s› ∈ 𝓝 x) : ∃ t : Finset s, s ⊆ ⋃ x ∈ t, U (x : s) x.2 :=
  (hs.elim_nhds_subcover_nhdsSet' U hU).imp fun _ ↦ subset_of_mem_nhdsSet
#align is_compact.elim_nhds_subcover' IsCompact.elim_nhds_subcover'

theorem IsCompact.elim_nhds_subcover (hs : IsCompact s) (U : X → Set X) (hU : ∀ x ∈ s, U x ∈ 𝓝 x) :
    ∃ t : Finset X, (∀ x ∈ t, x ∈ s) ∧ s ⊆ ⋃ x ∈ t, U x :=
  (hs.elim_nhds_subcover_nhdsSet hU).imp fun _ h ↦ h.imp_right subset_of_mem_nhdsSet
#align is_compact.elim_nhds_subcover IsCompact.elim_nhds_subcover

/-- The neighborhood filter of a compact set is disjoint with a filter `l` if and only if the
neighborhood filter of each point of this set is disjoint with `l`. -/
theorem IsCompact.disjoint_nhdsSet_left {l : Filter X} (hs : IsCompact s) :
    Disjoint (𝓝ˢ s) l ↔ ∀ x ∈ s, Disjoint (𝓝 x) l := by
  refine ⟨fun h x hx => h.mono_left <| nhds_le_nhdsSet hx, fun H => ?_⟩
  choose! U hxU hUl using fun x hx => (nhds_basis_opens x).disjoint_iff_left.1 (H x hx)
  choose hxU hUo using hxU
  rcases hs.elim_nhds_subcover U fun x hx => (hUo x hx).mem_nhds (hxU x hx) with ⟨t, hts, hst⟩
  refine (hasBasis_nhdsSet _).disjoint_iff_left.2
    ⟨⋃ x ∈ t, U x, ⟨isOpen_biUnion fun x hx => hUo x (hts x hx), hst⟩, ?_⟩
  rw [compl_iUnion₂, biInter_finset_mem]
  exact fun x hx => hUl x (hts x hx)
#align is_compact.disjoint_nhds_set_left IsCompact.disjoint_nhdsSet_left

/-- A filter `l` is disjoint with the neighborhood filter of a compact set if and only if it is
disjoint with the neighborhood filter of each point of this set. -/
theorem IsCompact.disjoint_nhdsSet_right {l : Filter X} (hs : IsCompact s) :
    Disjoint l (𝓝ˢ s) ↔ ∀ x ∈ s, Disjoint l (𝓝 x) := by
  simpa only [disjoint_comm] using hs.disjoint_nhdsSet_left
#align is_compact.disjoint_nhds_set_right IsCompact.disjoint_nhdsSet_right

-- Porting note (#11215): TODO: reformulate using `Disjoint`
/-- For every directed family of closed sets whose intersection avoids a compact set,
there exists a single element of the family which itself avoids this compact set. -/
theorem IsCompact.elim_directed_family_closed {ι : Type v} [hι : Nonempty ι] (hs : IsCompact s)
    (t : ι → Set X) (htc : ∀ i, IsClosed (t i)) (hst : (s ∩ ⋂ i, t i) = ∅)
    (hdt : Directed (· ⊇ ·) t) : ∃ i : ι, s ∩ t i = ∅ :=
  let ⟨t, ht⟩ :=
    hs.elim_directed_cover (compl ∘ t) (fun i => (htc i).isOpen_compl)
      (by
        simpa only [subset_def, not_forall, eq_empty_iff_forall_not_mem, mem_iUnion, exists_prop,
          mem_inter_iff, not_and, iff_self_iff, mem_iInter, mem_compl_iff] using hst)
      (hdt.mono_comp _ fun _ _ => compl_subset_compl.mpr)
  ⟨t, by
    simpa only [subset_def, not_forall, eq_empty_iff_forall_not_mem, mem_iUnion, exists_prop,
      mem_inter_iff, not_and, iff_self_iff, mem_iInter, mem_compl_iff] using ht⟩
#align is_compact.elim_directed_family_closed IsCompact.elim_directed_family_closed

-- Porting note (#11215): TODO: reformulate using `Disjoint`
/-- For every family of closed sets whose intersection avoids a compact set,
there exists a finite subfamily whose intersection avoids this compact set. -/
theorem IsCompact.elim_finite_subfamily_closed {ι : Type v} (hs : IsCompact s)
    (t : ι → Set X) (htc : ∀ i, IsClosed (t i)) (hst : (s ∩ ⋂ i, t i) = ∅) :
    ∃ u : Finset ι, (s ∩ ⋂ i ∈ u, t i) = ∅ :=
  hs.elim_directed_family_closed _ (fun t ↦ isClosed_biInter fun _ _ ↦ htc _)
    (by rwa [← iInter_eq_iInter_finset])
    (directed_of_isDirected_le fun _ _ h ↦ biInter_subset_biInter_left h)
#align is_compact.elim_finite_subfamily_closed IsCompact.elim_finite_subfamily_closed

/-- If `s` is a compact set in a topological space `X` and `f : ι → Set X` is a locally finite
family of sets, then `f i ∩ s` is nonempty only for a finitely many `i`. -/
theorem LocallyFinite.finite_nonempty_inter_compact {f : ι → Set X}
    (hf : LocallyFinite f) (hs : IsCompact s) : { i | (f i ∩ s).Nonempty }.Finite := by
  choose U hxU hUf using hf
  rcases hs.elim_nhds_subcover U fun x _ => hxU x with ⟨t, -, hsU⟩
  refine (t.finite_toSet.biUnion fun x _ => hUf x).subset ?_
  rintro i ⟨x, hx⟩
  rcases mem_iUnion₂.1 (hsU hx.2) with ⟨c, hct, hcx⟩
  exact mem_biUnion hct ⟨x, hx.1, hcx⟩
#align locally_finite.finite_nonempty_inter_compact LocallyFinite.finite_nonempty_inter_compact

/-- To show that a compact set intersects the intersection of a family of closed sets,
  it is sufficient to show that it intersects every finite subfamily. -/
theorem IsCompact.inter_iInter_nonempty {ι : Type v} (hs : IsCompact s) (t : ι → Set X)
    (htc : ∀ i, IsClosed (t i)) (hst : ∀ u : Finset ι, (s ∩ ⋂ i ∈ u, t i).Nonempty) :
    (s ∩ ⋂ i, t i).Nonempty := by
  contrapose! hst
  exact hs.elim_finite_subfamily_closed t htc hst
#align is_compact.inter_Inter_nonempty IsCompact.inter_iInter_nonempty

/-- Cantor's intersection theorem for `iInter`:
the intersection of a directed family of nonempty compact closed sets is nonempty. -/
theorem IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed
    {ι : Type v} [hι : Nonempty ι] (t : ι → Set X) (htd : Directed (· ⊇ ·) t)
    (htn : ∀ i, (t i).Nonempty) (htc : ∀ i, IsCompact (t i)) (htcl : ∀ i, IsClosed (t i)) :
    (⋂ i, t i).Nonempty := by
  let i₀ := hι.some
  suffices (t i₀ ∩ ⋂ i, t i).Nonempty by
    rwa [inter_eq_right.mpr (iInter_subset _ i₀)] at this
  simp only [nonempty_iff_ne_empty] at htn ⊢
  apply mt ((htc i₀).elim_directed_family_closed t htcl)
  push_neg
  simp only [← nonempty_iff_ne_empty] at htn ⊢
  refine ⟨htd, fun i => ?_⟩
  rcases htd i₀ i with ⟨j, hji₀, hji⟩
  exact (htn j).mono (subset_inter hji₀ hji)
#align is_compact.nonempty_Inter_of_directed_nonempty_compact_closed IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed

@[deprecated (since := "2024-02-28")]
alias IsCompact.nonempty_iInter_of_directed_nonempty_compact_closed :=
  IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed

/-- Cantor's intersection theorem for `sInter`:
the intersection of a directed family of nonempty compact closed sets is nonempty. -/
theorem IsCompact.nonempty_sInter_of_directed_nonempty_isCompact_isClosed
    {S : Set (Set X)} [hS : Nonempty S] (hSd : DirectedOn (· ⊇ ·) S) (hSn : ∀ U ∈ S, U.Nonempty)
    (hSc : ∀ U ∈ S, IsCompact U) (hScl : ∀ U ∈ S, IsClosed U) : (⋂₀ S).Nonempty := by
  rw [sInter_eq_iInter]
  exact IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed _
    (DirectedOn.directed_val hSd) (fun i ↦ hSn i i.2) (fun i ↦ hSc i i.2) (fun i ↦ hScl i i.2)

/-- Cantor's intersection theorem for sequences indexed by `ℕ`:
the intersection of a decreasing sequence of nonempty compact closed sets is nonempty. -/
theorem IsCompact.nonempty_iInter_of_sequence_nonempty_isCompact_isClosed (t : ℕ → Set X)
    (htd : ∀ i, t (i + 1) ⊆ t i) (htn : ∀ i, (t i).Nonempty) (ht0 : IsCompact (t 0))
    (htcl : ∀ i, IsClosed (t i)) : (⋂ i, t i).Nonempty :=
  have tmono : Antitone t := antitone_nat_of_succ_le htd
  have htd : Directed (· ⊇ ·) t := tmono.directed_ge
  have : ∀ i, t i ⊆ t 0 := fun i => tmono <| zero_le i
  have htc : ∀ i, IsCompact (t i) := fun i => ht0.of_isClosed_subset (htcl i) (this i)
  IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed t htd htn htc htcl
#align is_compact.nonempty_Inter_of_sequence_nonempty_compact_closed IsCompact.nonempty_iInter_of_sequence_nonempty_isCompact_isClosed

@[deprecated (since := "2024-02-28")]
alias IsCompact.nonempty_iInter_of_sequence_nonempty_compact_closed :=
  IsCompact.nonempty_iInter_of_sequence_nonempty_isCompact_isClosed

/-- For every open cover of a compact set, there exists a finite subcover. -/
theorem IsCompact.elim_finite_subcover_image {b : Set ι} {c : ι → Set X} (hs : IsCompact s)
    (hc₁ : ∀ i ∈ b, IsOpen (c i)) (hc₂ : s ⊆ ⋃ i ∈ b, c i) :
    ∃ b', b' ⊆ b ∧ Set.Finite b' ∧ s ⊆ ⋃ i ∈ b', c i := by
  simp only [Subtype.forall', biUnion_eq_iUnion] at hc₁ hc₂
  rcases hs.elim_finite_subcover (fun i => c i : b → Set X) hc₁ hc₂ with ⟨d, hd⟩
  refine ⟨Subtype.val '' d.toSet, ?_, d.finite_toSet.image _, ?_⟩
  · simp
  · rwa [biUnion_image]
#align is_compact.elim_finite_subcover_image IsCompact.elim_finite_subcover_imageₓ

/-- A set `s` is compact if for every open cover of `s`, there exists a finite subcover. -/
theorem isCompact_of_finite_subcover
    (h : ∀ {ι : Type u} (U : ι → Set X), (∀ i, IsOpen (U i)) → (s ⊆ ⋃ i, U i) →
      ∃ t : Finset ι, s ⊆ ⋃ i ∈ t, U i) :
    IsCompact s := fun f hf hfs => by
  contrapose! h
  simp only [ClusterPt, not_neBot, ← disjoint_iff, SetCoe.forall',
    (nhds_basis_opens _).disjoint_iff_left] at h
  choose U hU hUf using h
  refine ⟨s, U, fun x => (hU x).2, fun x hx => mem_iUnion.2 ⟨⟨x, hx⟩, (hU _).1⟩, fun t ht => ?_⟩
  refine compl_not_mem (le_principal_iff.1 hfs) ?_
  refine mem_of_superset ((biInter_finset_mem t).2 fun x _ => hUf x) ?_
  rw [subset_compl_comm, compl_iInter₂]
  simpa only [compl_compl]
#align is_compact_of_finite_subcover isCompact_of_finite_subcover

-- Porting note (#11215): TODO: reformulate using `Disjoint`
/-- A set `s` is compact if for every family of closed sets whose intersection avoids `s`,
there exists a finite subfamily whose intersection avoids `s`. -/
theorem isCompact_of_finite_subfamily_closed
    (h : ∀ {ι : Type u} (t : ι → Set X), (∀ i, IsClosed (t i)) → (s ∩ ⋂ i, t i) = ∅ →
      ∃ u : Finset ι, (s ∩ ⋂ i ∈ u, t i) = ∅) :
    IsCompact s :=
  isCompact_of_finite_subcover fun U hUo hsU => by
    rw [← disjoint_compl_right_iff_subset, compl_iUnion, disjoint_iff] at hsU
    rcases h (fun i => (U i)ᶜ) (fun i => (hUo _).isClosed_compl) hsU with ⟨t, ht⟩
    refine ⟨t, ?_⟩
    rwa [← disjoint_compl_right_iff_subset, compl_iUnion₂, disjoint_iff]
#align is_compact_of_finite_subfamily_closed isCompact_of_finite_subfamily_closed

/-- A set `s` is compact if and only if
for every open cover of `s`, there exists a finite subcover. -/
theorem isCompact_iff_finite_subcover :
    IsCompact s ↔ ∀ {ι : Type u} (U : ι → Set X),
      (∀ i, IsOpen (U i)) → (s ⊆ ⋃ i, U i) → ∃ t : Finset ι, s ⊆ ⋃ i ∈ t, U i :=
  ⟨fun hs => hs.elim_finite_subcover, isCompact_of_finite_subcover⟩
#align is_compact_iff_finite_subcover isCompact_iff_finite_subcover

/-- A set `s` is compact if and only if
for every family of closed sets whose intersection avoids `s`,
there exists a finite subfamily whose intersection avoids `s`. -/
theorem isCompact_iff_finite_subfamily_closed :
    IsCompact s ↔ ∀ {ι : Type u} (t : ι → Set X),
      (∀ i, IsClosed (t i)) → (s ∩ ⋂ i, t i) = ∅ → ∃ u : Finset ι, (s ∩ ⋂ i ∈ u, t i) = ∅ :=
  ⟨fun hs => hs.elim_finite_subfamily_closed, isCompact_of_finite_subfamily_closed⟩
#align is_compact_iff_finite_subfamily_closed isCompact_iff_finite_subfamily_closed

/-- If `s : Set (X × Y)` belongs to `𝓝 x ×ˢ l` for all `x` from a compact set `K`,
then it belongs to `(𝓝ˢ K) ×ˢ l`,
i.e., there exist an open `U ⊇ K` and `t ∈ l` such that `U ×ˢ t ⊆ s`. -/
theorem IsCompact.mem_nhdsSet_prod_of_forall {K : Set X} {l : Filter Y} {s : Set (X × Y)}
    (hK : IsCompact K) (hs : ∀ x ∈ K, s ∈ 𝓝 x ×ˢ l) : s ∈ (𝓝ˢ K) ×ˢ l := by
  refine hK.induction_on (by simp) (fun t t' ht hs ↦ ?_) (fun t t' ht ht' ↦ ?_) fun x hx ↦ ?_
  · exact prod_mono (nhdsSet_mono ht) le_rfl hs
  · simp [sup_prod, *]
  · rcases ((nhds_basis_opens _).prod l.basis_sets).mem_iff.1 (hs x hx)
      with ⟨⟨u, v⟩, ⟨⟨hx, huo⟩, hv⟩, hs⟩
    refine ⟨u, nhdsWithin_le_nhds (huo.mem_nhds hx), mem_of_superset ?_ hs⟩
    exact prod_mem_prod (huo.mem_nhdsSet.2 Subset.rfl) hv

theorem IsCompact.nhdsSet_prod_eq_biSup {K : Set X} (hK : IsCompact K) (l : Filter Y) :
    (𝓝ˢ K) ×ˢ l = ⨆ x ∈ K, 𝓝 x ×ˢ l :=
  le_antisymm (fun s hs ↦ hK.mem_nhdsSet_prod_of_forall <| by simpa using hs)
    (iSup₂_le fun x hx ↦ prod_mono (nhds_le_nhdsSet hx) le_rfl)

theorem IsCompact.prod_nhdsSet_eq_biSup {K : Set Y} (hK : IsCompact K) (l : Filter X) :
    l ×ˢ (𝓝ˢ K) = ⨆ y ∈ K, l ×ˢ 𝓝 y := by
  simp only [prod_comm (f := l), hK.nhdsSet_prod_eq_biSup, map_iSup]

/-- If `s : Set (X × Y)` belongs to `l ×ˢ 𝓝 y` for all `y` from a compact set `K`,
then it belongs to `l ×ˢ (𝓝ˢ K)`,
i.e., there exist `t ∈ l` and an open `U ⊇ K` such that `t ×ˢ U ⊆ s`. -/
theorem IsCompact.mem_prod_nhdsSet_of_forall {K : Set Y} {l : Filter X} {s : Set (X × Y)}
    (hK : IsCompact K) (hs : ∀ y ∈ K, s ∈ l ×ˢ 𝓝 y) : s ∈ l ×ˢ 𝓝ˢ K :=
  (hK.prod_nhdsSet_eq_biSup l).symm ▸ by simpa using hs

-- TODO: Is there a way to prove directly the `inf` version and then deduce the `Prod` one ?
-- That would seem a bit more natural.
theorem IsCompact.nhdsSet_inf_eq_biSup {K : Set X} (hK : IsCompact K) (l : Filter X) :
    (𝓝ˢ K) ⊓ l = ⨆ x ∈ K, 𝓝 x ⊓ l := by
  have : ∀ f : Filter X, f ⊓ l = comap (fun x ↦ (x, x)) (f ×ˢ l) := fun f ↦ by
    simpa only [comap_prod] using congrArg₂ (· ⊓ ·) comap_id.symm comap_id.symm
  simp_rw [this, ← comap_iSup, hK.nhdsSet_prod_eq_biSup]

theorem IsCompact.inf_nhdsSet_eq_biSup {K : Set X} (hK : IsCompact K) (l : Filter X) :
    l ⊓ (𝓝ˢ K) = ⨆ x ∈ K, l ⊓ 𝓝 x := by
  simp only [inf_comm l, hK.nhdsSet_inf_eq_biSup]

/-- If `s : Set X` belongs to `𝓝 x ⊓ l` for all `x` from a compact set `K`,
then it belongs to `(𝓝ˢ K) ⊓ l`,
i.e., there exist an open `U ⊇ K` and `T ∈ l` such that `U ∩ T ⊆ s`. -/
theorem IsCompact.mem_nhdsSet_inf_of_forall {K : Set X} {l : Filter X} {s : Set X}
    (hK : IsCompact K) (hs : ∀ x ∈ K, s ∈ 𝓝 x ⊓ l) : s ∈ (𝓝ˢ K) ⊓ l :=
  (hK.nhdsSet_inf_eq_biSup l).symm ▸ by simpa using hs

/-- If `s : Set S` belongs to `l ⊓ 𝓝 x` for all `x` from a compact set `K`,
then it belongs to `l ⊓ (𝓝ˢ K)`,
i.e., there exist `T ∈ l` and an open `U ⊇ K` such that `T ∩ U ⊆ s`. -/
theorem IsCompact.mem_inf_nhdsSet_of_forall {K : Set X} {l : Filter X} {s : Set X}
    (hK : IsCompact K) (hs : ∀ y ∈ K, s ∈ l ⊓ 𝓝 y) : s ∈ l ⊓ 𝓝ˢ K :=
  (hK.inf_nhdsSet_eq_biSup l).symm ▸ by simpa using hs

/-- To show that `∀ y ∈ K, P x y` holds for `x` close enough to `x₀` when `K` is compact,
it is sufficient to show that for all `y₀ ∈ K` there `P x y` holds for `(x, y)` close enough
to `(x₀, y₀)`.

Provided for backwards compatibility,
see `IsCompact.mem_prod_nhdsSet_of_forall` for a stronger statement.
-/
theorem IsCompact.eventually_forall_of_forall_eventually {x₀ : X} {K : Set Y} (hK : IsCompact K)
    {P : X → Y → Prop} (hP : ∀ y ∈ K, ∀ᶠ z : X × Y in 𝓝 (x₀, y), P z.1 z.2) :
    ∀ᶠ x in 𝓝 x₀, ∀ y ∈ K, P x y := by
  simp only [nhds_prod_eq, ← eventually_iSup, ← hK.prod_nhdsSet_eq_biSup] at hP
  exact hP.curry.mono fun _ h ↦ h.self_of_nhdsSet
#align is_compact.eventually_forall_of_forall_eventually IsCompact.eventually_forall_of_forall_eventually

@[simp]
theorem isCompact_empty : IsCompact (∅ : Set X) := fun _f hnf hsf =>
  Not.elim hnf.ne <| empty_mem_iff_bot.1 <| le_principal_iff.1 hsf
#align is_compact_empty isCompact_empty

@[simp]
theorem isCompact_singleton {x : X} : IsCompact ({x} : Set X) := fun f hf hfa =>
  ⟨x, rfl, ClusterPt.of_le_nhds'
    (hfa.trans <| by simpa only [principal_singleton] using pure_le_nhds x) hf⟩
#align is_compact_singleton isCompact_singleton

theorem Set.Subsingleton.isCompact (hs : s.Subsingleton) : IsCompact s :=
  Subsingleton.induction_on hs isCompact_empty fun _ => isCompact_singleton
#align set.subsingleton.is_compact Set.Subsingleton.isCompact

-- Porting note: golfed a proof instead of fixing it
theorem Set.Finite.isCompact_biUnion {s : Set ι} {f : ι → Set X} (hs : s.Finite)
    (hf : ∀ i ∈ s, IsCompact (f i)) : IsCompact (⋃ i ∈ s, f i) :=
  isCompact_iff_ultrafilter_le_nhds'.2 fun l hl => by
    rw [Ultrafilter.finite_biUnion_mem_iff hs] at hl
    rcases hl with ⟨i, his, hi⟩
    rcases (hf i his).ultrafilter_le_nhds _ (le_principal_iff.2 hi) with ⟨x, hxi, hlx⟩
    exact ⟨x, mem_iUnion₂.2 ⟨i, his, hxi⟩, hlx⟩
#align set.finite.is_compact_bUnion Set.Finite.isCompact_biUnion

theorem Finset.isCompact_biUnion (s : Finset ι) {f : ι → Set X} (hf : ∀ i ∈ s, IsCompact (f i)) :
    IsCompact (⋃ i ∈ s, f i) :=
  s.finite_toSet.isCompact_biUnion hf
#align finset.is_compact_bUnion Finset.isCompact_biUnion

theorem isCompact_accumulate {K : ℕ → Set X} (hK : ∀ n, IsCompact (K n)) (n : ℕ) :
    IsCompact (Accumulate K n) :=
  (finite_le_nat n).isCompact_biUnion fun k _ => hK k
#align is_compact_accumulate isCompact_accumulate

theorem Set.Finite.isCompact_sUnion {S : Set (Set X)} (hf : S.Finite) (hc : ∀ s ∈ S, IsCompact s) :
    IsCompact (⋃₀ S) := by
  rw [sUnion_eq_biUnion]; exact hf.isCompact_biUnion hc

-- Porting note: generalized to `ι : Sort*`
theorem isCompact_iUnion {ι : Sort*} {f : ι → Set X} [Finite ι] (h : ∀ i, IsCompact (f i)) :
    IsCompact (⋃ i, f i) :=
  (finite_range f).isCompact_sUnion <| forall_mem_range.2 h
#align is_compact_Union isCompact_iUnion

theorem Set.Finite.isCompact (hs : s.Finite) : IsCompact s :=
  biUnion_of_singleton s ▸ hs.isCompact_biUnion fun _ _ => isCompact_singleton
#align set.finite.is_compact Set.Finite.isCompact

theorem IsCompact.finite_of_discrete [DiscreteTopology X] (hs : IsCompact s) : s.Finite := by
  have : ∀ x : X, ({x} : Set X) ∈ 𝓝 x := by simp [nhds_discrete]
  rcases hs.elim_nhds_subcover (fun x => {x}) fun x _ => this x with ⟨t, _, hst⟩
  simp only [← t.set_biUnion_coe, biUnion_of_singleton] at hst
  exact t.finite_toSet.subset hst
#align is_compact.finite_of_discrete IsCompact.finite_of_discrete

theorem isCompact_iff_finite [DiscreteTopology X] : IsCompact s ↔ s.Finite :=
  ⟨fun h => h.finite_of_discrete, fun h => h.isCompact⟩
#align is_compact_iff_finite isCompact_iff_finite

theorem IsCompact.union (hs : IsCompact s) (ht : IsCompact t) : IsCompact (s ∪ t) := by
  rw [union_eq_iUnion]; exact isCompact_iUnion fun b => by cases b <;> assumption
#align is_compact.union IsCompact.union

protected theorem IsCompact.insert (hs : IsCompact s) (a) : IsCompact (insert a s) :=
  isCompact_singleton.union hs
#align is_compact.insert IsCompact.insert

-- Porting note (#11215): TODO: reformulate using `𝓝ˢ`
/-- If `V : ι → Set X` is a decreasing family of closed compact sets then any neighborhood of
`⋂ i, V i` contains some `V i`. We assume each `V i` is compact *and* closed because `X` is
not assumed to be Hausdorff. See `exists_subset_nhd_of_compact` for version assuming this. -/
theorem exists_subset_nhds_of_isCompact' [Nonempty ι] {V : ι → Set X}
    (hV : Directed (· ⊇ ·) V) (hV_cpct : ∀ i, IsCompact (V i)) (hV_closed : ∀ i, IsClosed (V i))
    {U : Set X} (hU : ∀ x ∈ ⋂ i, V i, U ∈ 𝓝 x) : ∃ i, V i ⊆ U := by
  obtain ⟨W, hsubW, W_op, hWU⟩ := exists_open_set_nhds hU
  suffices ∃ i, V i ⊆ W from this.imp fun i hi => hi.trans hWU
  by_contra! H
  replace H : ∀ i, (V i ∩ Wᶜ).Nonempty := fun i => Set.inter_compl_nonempty_iff.mpr (H i)
  have : (⋂ i, V i ∩ Wᶜ).Nonempty := by
    refine
      IsCompact.nonempty_iInter_of_directed_nonempty_isCompact_isClosed _ (fun i j => ?_) H
        (fun i => (hV_cpct i).inter_right W_op.isClosed_compl) fun i =>
        (hV_closed i).inter W_op.isClosed_compl
    rcases hV i j with ⟨k, hki, hkj⟩
    refine ⟨k, ⟨fun x => ?_, fun x => ?_⟩⟩ <;> simp only [and_imp, mem_inter_iff, mem_compl_iff] <;>
      tauto
  have : ¬⋂ i : ι, V i ⊆ W := by simpa [← iInter_inter, inter_compl_nonempty_iff]
  contradiction
#align exists_subset_nhds_of_is_compact' exists_subset_nhds_of_isCompact'

lemma eq_finite_iUnion_of_isTopologicalBasis_of_isCompact_open (b : ι → Set X)
    (hb : IsTopologicalBasis (Set.range b)) (U : Set X) (hUc : IsCompact U) (hUo : IsOpen U) :
    ∃ s : Set ι, s.Finite ∧ U = ⋃ i ∈ s, b i := by
  obtain ⟨Y, f, e, hf⟩ := hb.open_eq_iUnion hUo
  choose f' hf' using hf
  have : b ∘ f' = f := funext hf'
  subst this
  obtain ⟨t, ht⟩ :=
    hUc.elim_finite_subcover (b ∘ f') (fun i => hb.isOpen (Set.mem_range_self _)) (by rw [e])
  refine ⟨t.image f', Set.toFinite _, le_antisymm ?_ ?_⟩
  · refine Set.Subset.trans ht ?_
    simp only [Set.iUnion_subset_iff]
    intro i hi
    erw [← Set.iUnion_subtype (fun x : ι => x ∈ t.image f') fun i => b i.1]
    exact Set.subset_iUnion (fun i : t.image f' => b i) ⟨_, Finset.mem_image_of_mem _ hi⟩
  · apply Set.iUnion₂_subset
    rintro i hi
    obtain ⟨j, -, rfl⟩ := Finset.mem_image.mp hi
    rw [e]
    exact Set.subset_iUnion (b ∘ f') j

lemma eq_sUnion_finset_of_isTopologicalBasis_of_isCompact_open (b : Set (Set X))
    (hb : IsTopologicalBasis b) (U : Set X) (hUc : IsCompact U) (hUo : IsOpen U) :
    ∃ s : Finset b, U = s.toSet.sUnion := by
  have hb' : b = range (fun i ↦ i : b → Set X) := by simp
  rw [hb'] at hb
  choose s hs hU using eq_finite_iUnion_of_isTopologicalBasis_of_isCompact_open _ hb U hUc hUo
  have : Finite s := hs
  let _ : Fintype s := Fintype.ofFinite _
  use s.toFinset
  simp [hU]

/-- If `X` has a basis consisting of compact opens, then an open set in `X` is compact open iff
  it is a finite union of some elements in the basis -/
theorem isCompact_open_iff_eq_finite_iUnion_of_isTopologicalBasis (b : ι → Set X)
    (hb : IsTopologicalBasis (Set.range b)) (hb' : ∀ i, IsCompact (b i)) (U : Set X) :
    IsCompact U ∧ IsOpen U ↔ ∃ s : Set ι, s.Finite ∧ U = ⋃ i ∈ s, b i := by
  constructor
  · exact fun ⟨h₁, h₂⟩ ↦ eq_finite_iUnion_of_isTopologicalBasis_of_isCompact_open _ hb U h₁ h₂
  · rintro ⟨s, hs, rfl⟩
    constructor
    · exact hs.isCompact_biUnion fun i _ => hb' i
    · exact isOpen_biUnion fun i _ => hb.isOpen (Set.mem_range_self _)
#align is_compact_open_iff_eq_finite_Union_of_is_topological_basis isCompact_open_iff_eq_finite_iUnion_of_isTopologicalBasis

namespace Filter

theorem hasBasis_cocompact : (cocompact X).HasBasis IsCompact compl :=
  hasBasis_biInf_principal'
    (fun s hs t ht =>
      ⟨s ∪ t, hs.union ht, compl_subset_compl.2 subset_union_left,
        compl_subset_compl.2 subset_union_right⟩)
    ⟨∅, isCompact_empty⟩
#align filter.has_basis_cocompact Filter.hasBasis_cocompact

theorem mem_cocompact : s ∈ cocompact X ↔ ∃ t, IsCompact t ∧ tᶜ ⊆ s :=
  hasBasis_cocompact.mem_iff
#align filter.mem_cocompact Filter.mem_cocompact

theorem mem_cocompact' : s ∈ cocompact X ↔ ∃ t, IsCompact t ∧ sᶜ ⊆ t :=
  mem_cocompact.trans <| exists_congr fun _ => and_congr_right fun _ => compl_subset_comm
#align filter.mem_cocompact' Filter.mem_cocompact'

theorem _root_.IsCompact.compl_mem_cocompact (hs : IsCompact s) : sᶜ ∈ Filter.cocompact X :=
  hasBasis_cocompact.mem_of_mem hs
#align is_compact.compl_mem_cocompact IsCompact.compl_mem_cocompact

theorem cocompact_le_cofinite : cocompact X ≤ cofinite := fun s hs =>
  compl_compl s ▸ hs.isCompact.compl_mem_cocompact
#align filter.cocompact_le_cofinite Filter.cocompact_le_cofinite

theorem cocompact_eq_cofinite (X : Type*) [TopologicalSpace X] [DiscreteTopology X] :
    cocompact X = cofinite := by
  simp only [cocompact, hasBasis_cofinite.eq_biInf, isCompact_iff_finite]
#align filter.cocompact_eq_cofinite Filter.cocompact_eq_cofinite

/-- A filter is disjoint from the cocompact filter if and only if it contains a compact set. -/
theorem disjoint_cocompact_left (f : Filter X) :
    Disjoint (Filter.cocompact X) f ↔ ∃ K ∈ f, IsCompact K := by
  simp_rw [hasBasis_cocompact.disjoint_iff_left, compl_compl]
  tauto

/-- A filter is disjoint from the cocompact filter if and only if it contains a compact set. -/
theorem disjoint_cocompact_right (f : Filter X) :
    Disjoint f (Filter.cocompact X) ↔ ∃ K ∈ f, IsCompact K := by
  simp_rw [hasBasis_cocompact.disjoint_iff_right, compl_compl]
  tauto

@[deprecated "see `cocompact_eq_atTop` with `import Mathlib.Topology.Instances.Nat`"
  (since := "2024-02-07")]
theorem _root_.Nat.cocompact_eq : cocompact ℕ = atTop :=
  (cocompact_eq_cofinite ℕ).trans Nat.cofinite_eq_atTop
#align nat.cocompact_eq Nat.cocompact_eq

theorem Tendsto.isCompact_insert_range_of_cocompact {f : X → Y} {y}
    (hf : Tendsto f (cocompact X) (𝓝 y)) (hfc : Continuous f) : IsCompact (insert y (range f)) := by
  intro l hne hle
  by_cases hy : ClusterPt y l
  · exact ⟨y, Or.inl rfl, hy⟩
  simp only [clusterPt_iff, not_forall, ← not_disjoint_iff_nonempty_inter, not_not] at hy
  rcases hy with ⟨s, hsy, t, htl, hd⟩
  rcases mem_cocompact.1 (hf hsy) with ⟨K, hKc, hKs⟩
  have : f '' K ∈ l := by
    filter_upwards [htl, le_principal_iff.1 hle] with y hyt hyf
    rcases hyf with (rfl | ⟨x, rfl⟩)
    exacts [(hd.le_bot ⟨mem_of_mem_nhds hsy, hyt⟩).elim,
      mem_image_of_mem _ (not_not.1 fun hxK => hd.le_bot ⟨hKs hxK, hyt⟩)]
  rcases hKc.image hfc (le_principal_iff.2 this) with ⟨y, hy, hyl⟩
  exact ⟨y, Or.inr <| image_subset_range _ _ hy, hyl⟩
#align filter.tendsto.is_compact_insert_range_of_cocompact Filter.Tendsto.isCompact_insert_range_of_cocompact

set_option maxHeartbeats 1000000 in
theorem probe_Filter_Tendsto_isCompact_insert_range_of_cofinite {f : ι → X} {x} (hf : Tendsto f cofinite (𝓝 x)) :
    IsCompact (insert x (range f)) := by
  letI : TopologicalSpace ι := ⊥
  trace_state
  haveI h : DiscreteTopology ι := ⟨rfl⟩
  trace_state
  rw [← cocompact_eq_cofinite ι] at hf
  trace_state
  exact hf.isCompact_insert_range_of_cocompact continuous_of_discreteTopology
  trace_state
