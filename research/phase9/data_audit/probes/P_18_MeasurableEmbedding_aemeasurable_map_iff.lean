/-
Copyright (c) 2021 Sébastien Gouëzel. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Sébastien Gouëzel
-/
import Mathlib.MeasureTheory.Measure.Trim
import Mathlib.MeasureTheory.MeasurableSpace.CountablyGenerated

#align_import measure_theory.measure.ae_measurable from "leanprover-community/mathlib"@"3310acfa9787aa171db6d4cba3945f6f275fe9f2"

/-!
# Almost everywhere measurable functions

A function is almost everywhere measurable if it coincides almost everywhere with a measurable
function. This property, called `AEMeasurable f μ`, is defined in the file `MeasureSpaceDef`.
We discuss several of its properties that are analogous to properties of measurable functions.
-/

open scoped Classical
open MeasureTheory MeasureTheory.Measure Filter Set Function ENNReal

variable {ι α β γ δ R : Type*} {m0 : MeasurableSpace α} [MeasurableSpace β] [MeasurableSpace γ]
  [MeasurableSpace δ] {f g : α → β} {μ ν : Measure α}

section

@[nontriviality, measurability]
theorem Subsingleton.aemeasurable [Subsingleton α] : AEMeasurable f μ :=
  Subsingleton.measurable.aemeasurable
#align subsingleton.ae_measurable Subsingleton.aemeasurable

@[nontriviality, measurability]
theorem aemeasurable_of_subsingleton_codomain [Subsingleton β] : AEMeasurable f μ :=
  (measurable_of_subsingleton_codomain f).aemeasurable
#align ae_measurable_of_subsingleton_codomain aemeasurable_of_subsingleton_codomain

@[simp, measurability]
theorem aemeasurable_zero_measure : AEMeasurable f (0 : Measure α) := by
  nontriviality α; inhabit α
  exact ⟨fun _ => f default, measurable_const, rfl⟩
#align ae_measurable_zero_measure aemeasurable_zero_measure

@[fun_prop]
theorem aemeasurable_id'' (μ : Measure α) {m : MeasurableSpace α} (hm : m ≤ m0) :
    @AEMeasurable α α m m0 id μ :=
  @Measurable.aemeasurable α α m0 m id μ (measurable_id'' hm)
#align probability_theory.ae_measurable_id'' aemeasurable_id''

lemma aemeasurable_of_map_neZero {mβ : MeasurableSpace β} {μ : Measure α}
    {f : α → β} (h : NeZero (μ.map f)) :
    AEMeasurable f μ := by
  by_contra h'
  simp [h'] at h

namespace AEMeasurable

lemma mono_ac (hf : AEMeasurable f ν) (hμν : μ ≪ ν) : AEMeasurable f μ :=
  ⟨hf.mk f, hf.measurable_mk, hμν.ae_le hf.ae_eq_mk⟩

theorem mono_measure (h : AEMeasurable f μ) (h' : ν ≤ μ) : AEMeasurable f ν :=
  mono_ac h h'.absolutelyContinuous
#align ae_measurable.mono_measure AEMeasurable.mono_measure

theorem mono_set {s t} (h : s ⊆ t) (ht : AEMeasurable f (μ.restrict t)) :
    AEMeasurable f (μ.restrict s) :=
  ht.mono_measure (restrict_mono h le_rfl)
#align ae_measurable.mono_set AEMeasurable.mono_set

@[fun_prop]
protected theorem mono' (h : AEMeasurable f μ) (h' : ν ≪ μ) : AEMeasurable f ν :=
  ⟨h.mk f, h.measurable_mk, h' h.ae_eq_mk⟩
#align ae_measurable.mono' AEMeasurable.mono'

theorem ae_mem_imp_eq_mk {s} (h : AEMeasurable f (μ.restrict s)) :
    ∀ᵐ x ∂μ, x ∈ s → f x = h.mk f x :=
  ae_imp_of_ae_restrict h.ae_eq_mk
#align ae_measurable.ae_mem_imp_eq_mk AEMeasurable.ae_mem_imp_eq_mk

theorem ae_inf_principal_eq_mk {s} (h : AEMeasurable f (μ.restrict s)) : f =ᶠ[ae μ ⊓ 𝓟 s] h.mk f :=
  le_ae_restrict h.ae_eq_mk
#align ae_measurable.ae_inf_principal_eq_mk AEMeasurable.ae_inf_principal_eq_mk

@[measurability]
theorem sum_measure [Countable ι] {μ : ι → Measure α} (h : ∀ i, AEMeasurable f (μ i)) :
    AEMeasurable f (sum μ) := by
  nontriviality β
  inhabit β
  set s : ι → Set α := fun i => toMeasurable (μ i) { x | f x ≠ (h i).mk f x }
  have hsμ : ∀ i, μ i (s i) = 0 := by
    intro i
    rw [measure_toMeasurable]
    exact (h i).ae_eq_mk
  have hsm : MeasurableSet (⋂ i, s i) :=
    MeasurableSet.iInter fun i => measurableSet_toMeasurable _ _
  have hs : ∀ i x, x ∉ s i → f x = (h i).mk f x := by
    intro i x hx
    contrapose! hx
    exact subset_toMeasurable _ _ hx
  set g : α → β := (⋂ i, s i).piecewise (const α default) f
  refine ⟨g, measurable_of_restrict_of_restrict_compl hsm ?_ ?_, ae_sum_iff.mpr fun i => ?_⟩
  · rw [restrict_piecewise]
    simp only [s, Set.restrict, const]
    exact measurable_const
  · rw [restrict_piecewise_compl, compl_iInter]
    intro t ht
    refine ⟨⋃ i, (h i).mk f ⁻¹' t ∩ (s i)ᶜ, MeasurableSet.iUnion fun i ↦
      (measurable_mk _ ht).inter (measurableSet_toMeasurable _ _).compl, ?_⟩
    ext ⟨x, hx⟩
    simp only [mem_preimage, mem_iUnion, Subtype.coe_mk, Set.restrict, mem_inter_iff,
      mem_compl_iff] at hx ⊢
    constructor
    · rintro ⟨i, hxt, hxs⟩
      rwa [hs _ _ hxs]
    · rcases hx with ⟨i, hi⟩
      rw [hs _ _ hi]
      exact fun h => ⟨i, h, hi⟩
  · refine measure_mono_null (fun x (hx : f x ≠ g x) => ?_) (hsμ i)
    contrapose! hx
    refine (piecewise_eq_of_not_mem _ _ _ ?_).symm
    exact fun h => hx (mem_iInter.1 h i)
#align ae_measurable.sum_measure AEMeasurable.sum_measure

@[simp]
theorem _root_.aemeasurable_sum_measure_iff [Countable ι] {μ : ι → Measure α} :
    AEMeasurable f (sum μ) ↔ ∀ i, AEMeasurable f (μ i) :=
  ⟨fun h _ => h.mono_measure (le_sum _ _), sum_measure⟩
#align ae_measurable_sum_measure_iff aemeasurable_sum_measure_iff

@[simp]
theorem _root_.aemeasurable_add_measure_iff :
    AEMeasurable f (μ + ν) ↔ AEMeasurable f μ ∧ AEMeasurable f ν := by
  rw [← sum_cond, aemeasurable_sum_measure_iff, Bool.forall_bool, and_comm]
  rfl
#align ae_measurable_add_measure_iff aemeasurable_add_measure_iff

@[measurability]
theorem add_measure {f : α → β} (hμ : AEMeasurable f μ) (hν : AEMeasurable f ν) :
    AEMeasurable f (μ + ν) :=
  aemeasurable_add_measure_iff.2 ⟨hμ, hν⟩
#align ae_measurable.add_measure AEMeasurable.add_measure

@[measurability]
protected theorem iUnion [Countable ι] {s : ι → Set α}
    (h : ∀ i, AEMeasurable f (μ.restrict (s i))) : AEMeasurable f (μ.restrict (⋃ i, s i)) :=
  (sum_measure h).mono_measure <| restrict_iUnion_le
#align ae_measurable.Union AEMeasurable.iUnion

@[simp]
theorem _root_.aemeasurable_iUnion_iff [Countable ι] {s : ι → Set α} :
    AEMeasurable f (μ.restrict (⋃ i, s i)) ↔ ∀ i, AEMeasurable f (μ.restrict (s i)) :=
  ⟨fun h _ => h.mono_measure <| restrict_mono (subset_iUnion _ _) le_rfl, AEMeasurable.iUnion⟩
#align ae_measurable_Union_iff aemeasurable_iUnion_iff

@[simp]
theorem _root_.aemeasurable_union_iff {s t : Set α} :
    AEMeasurable f (μ.restrict (s ∪ t)) ↔
      AEMeasurable f (μ.restrict s) ∧ AEMeasurable f (μ.restrict t) := by
  simp only [union_eq_iUnion, aemeasurable_iUnion_iff, Bool.forall_bool, cond, and_comm]
#align ae_measurable_union_iff aemeasurable_union_iff

@[measurability]
theorem smul_measure [Monoid R] [DistribMulAction R ℝ≥0∞] [IsScalarTower R ℝ≥0∞ ℝ≥0∞]
    (h : AEMeasurable f μ) (c : R) : AEMeasurable f (c • μ) :=
  ⟨h.mk f, h.measurable_mk, ae_smul_measure h.ae_eq_mk c⟩
#align ae_measurable.smul_measure AEMeasurable.smul_measure

theorem comp_aemeasurable {f : α → δ} {g : δ → β} (hg : AEMeasurable g (μ.map f))
    (hf : AEMeasurable f μ) : AEMeasurable (g ∘ f) μ :=
  ⟨hg.mk g ∘ hf.mk f, hg.measurable_mk.comp hf.measurable_mk,
    (ae_eq_comp hf hg.ae_eq_mk).trans (hf.ae_eq_mk.fun_comp (mk g hg))⟩
#align ae_measurable.comp_ae_measurable AEMeasurable.comp_aemeasurable

@[fun_prop]
theorem comp_aemeasurable' {f : α → δ} {g : δ → β} (hg : AEMeasurable g (μ.map f))
    (hf : AEMeasurable f μ) : AEMeasurable (fun x ↦ g (f x)) μ := comp_aemeasurable hg hf

theorem comp_measurable {f : α → δ} {g : δ → β} (hg : AEMeasurable g (μ.map f))
    (hf : Measurable f) : AEMeasurable (g ∘ f) μ :=
  hg.comp_aemeasurable hf.aemeasurable
#align ae_measurable.comp_measurable AEMeasurable.comp_measurable

theorem comp_quasiMeasurePreserving {ν : Measure δ} {f : α → δ} {g : δ → β} (hg : AEMeasurable g ν)
    (hf : QuasiMeasurePreserving f μ ν) : AEMeasurable (g ∘ f) μ :=
  (hg.mono' hf.absolutelyContinuous).comp_measurable hf.measurable
#align ae_measurable.comp_quasi_measure_preserving AEMeasurable.comp_quasiMeasurePreserving

theorem map_map_of_aemeasurable {g : β → γ} {f : α → β} (hg : AEMeasurable g (Measure.map f μ))
    (hf : AEMeasurable f μ) : (μ.map f).map g = μ.map (g ∘ f) := by
  ext1 s hs
  rw [map_apply_of_aemeasurable hg hs, map_apply₀ hf (hg.nullMeasurable hs),
    map_apply_of_aemeasurable (hg.comp_aemeasurable hf) hs, preimage_comp]
#align ae_measurable.map_map_of_ae_measurable AEMeasurable.map_map_of_aemeasurable

@[fun_prop, measurability]
theorem prod_mk {f : α → β} {g : α → γ} (hf : AEMeasurable f μ) (hg : AEMeasurable g μ) :
    AEMeasurable (fun x => (f x, g x)) μ :=
  ⟨fun a => (hf.mk f a, hg.mk g a), hf.measurable_mk.prod_mk hg.measurable_mk,
    EventuallyEq.prod_mk hf.ae_eq_mk hg.ae_eq_mk⟩
#align ae_measurable.prod_mk AEMeasurable.prod_mk

theorem exists_ae_eq_range_subset (H : AEMeasurable f μ) {t : Set β} (ht : ∀ᵐ x ∂μ, f x ∈ t)
    (h₀ : t.Nonempty) : ∃ g, Measurable g ∧ range g ⊆ t ∧ f =ᵐ[μ] g := by
  let s : Set α := toMeasurable μ { x | f x = H.mk f x ∧ f x ∈ t }ᶜ
  let g : α → β := piecewise s (fun _ => h₀.some) (H.mk f)
  refine ⟨g, ?_, ?_, ?_⟩
  · exact Measurable.piecewise (measurableSet_toMeasurable _ _) measurable_const H.measurable_mk
  · rintro _ ⟨x, rfl⟩
    by_cases hx : x ∈ s
    · simpa [g, hx] using h₀.some_mem
    · simp only [g, hx, piecewise_eq_of_not_mem, not_false_iff]
      contrapose! hx
      apply subset_toMeasurable
      simp (config := { contextual := true }) only [hx, mem_compl_iff, mem_setOf_eq, not_and,
        not_false_iff, imp_true_iff]
  · have A : μ (toMeasurable μ { x | f x = H.mk f x ∧ f x ∈ t }ᶜ) = 0 := by
      rw [measure_toMeasurable, ← compl_mem_ae_iff, compl_compl]
      exact H.ae_eq_mk.and ht
    filter_upwards [compl_mem_ae_iff.2 A] with x hx
    rw [mem_compl_iff] at hx
    simp only [g, hx, piecewise_eq_of_not_mem, not_false_iff]
    contrapose! hx
    apply subset_toMeasurable
    simp only [hx, mem_compl_iff, mem_setOf_eq, false_and_iff, not_false_iff]
#align ae_measurable.exists_ae_eq_range_subset AEMeasurable.exists_ae_eq_range_subset

theorem exists_measurable_nonneg {β} [Preorder β] [Zero β] {mβ : MeasurableSpace β} {f : α → β}
    (hf : AEMeasurable f μ) (f_nn : ∀ᵐ t ∂μ, 0 ≤ f t) : ∃ g, Measurable g ∧ 0 ≤ g ∧ f =ᵐ[μ] g := by
  obtain ⟨G, hG_meas, hG_mem, hG_ae_eq⟩ := hf.exists_ae_eq_range_subset f_nn ⟨0, le_rfl⟩
  exact ⟨G, hG_meas, fun x => hG_mem (mem_range_self x), hG_ae_eq⟩
#align ae_measurable.exists_measurable_nonneg AEMeasurable.exists_measurable_nonneg

theorem subtype_mk (h : AEMeasurable f μ) {s : Set β} {hfs : ∀ x, f x ∈ s} :
    AEMeasurable (codRestrict f s hfs) μ := by
  nontriviality α; inhabit α
  obtain ⟨g, g_meas, hg, fg⟩ : ∃ g : α → β, Measurable g ∧ range g ⊆ s ∧ f =ᵐ[μ] g :=
    h.exists_ae_eq_range_subset (eventually_of_forall hfs) ⟨_, hfs default⟩
  refine ⟨codRestrict g s fun x => hg (mem_range_self _), Measurable.subtype_mk g_meas, ?_⟩
  filter_upwards [fg] with x hx
  simpa [Subtype.ext_iff]
#align ae_measurable.subtype_mk AEMeasurable.subtype_mk

end AEMeasurable

theorem aemeasurable_const' (h : ∀ᵐ (x) (y) ∂μ, f x = f y) : AEMeasurable f μ := by
  rcases eq_or_ne μ 0 with (rfl | hμ)
  · exact aemeasurable_zero_measure
  · haveI := ae_neBot.2 hμ
    rcases h.exists with ⟨x, hx⟩
    exact ⟨const α (f x), measurable_const, EventuallyEq.symm hx⟩
#align ae_measurable_const' aemeasurable_const'

theorem aemeasurable_uIoc_iff [LinearOrder α] {f : α → β} {a b : α} :
    (AEMeasurable f <| μ.restrict <| Ι a b) ↔
      (AEMeasurable f <| μ.restrict <| Ioc a b) ∧ (AEMeasurable f <| μ.restrict <| Ioc b a) := by
  rw [uIoc_eq_union, aemeasurable_union_iff]
#align ae_measurable_uIoc_iff aemeasurable_uIoc_iff

theorem aemeasurable_iff_measurable [μ.IsComplete] : AEMeasurable f μ ↔ Measurable f :=
  ⟨fun h => h.nullMeasurable.measurable_of_complete, fun h => h.aemeasurable⟩
#align ae_measurable_iff_measurable aemeasurable_iff_measurable

set_option maxHeartbeats 1000000 in
theorem probe_MeasurableEmbedding_aemeasurable_map_iff {g : β → γ} (hf : MeasurableEmbedding f) :
    AEMeasurable g (μ.map f) ↔ AEMeasurable (g ∘ f) μ := by
  refine ⟨fun H => H.comp_measurable hf.measurable, ?_⟩
  trace_state
  rintro ⟨g₁, hgm₁, heq⟩
  trace_state
  rcases hf.exists_measurable_extend hgm₁ fun x => ⟨g x⟩ with ⟨g₂, hgm₂, rfl⟩
  trace_state
  exact ⟨g₂, hgm₂, hf.ae_map_iff.2 heq⟩
  trace_state
