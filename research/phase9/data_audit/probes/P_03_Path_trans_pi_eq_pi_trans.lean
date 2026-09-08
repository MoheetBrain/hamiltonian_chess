/-
Copyright (c) 2020 Patrick Massot. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Patrick Massot
-/
import Mathlib.Topology.Order.ProjIcc
import Mathlib.Topology.CompactOpen
import Mathlib.Topology.UnitInterval

#align_import topology.path_connected from "leanprover-community/mathlib"@"f2ce6086713c78a7f880485f7917ea547a215982"

/-!
# Path connectedness

## Main definitions

In the file the unit interval `[0, 1]` in `ℝ` is denoted by `I`, and `X` is a topological space.

* `Path (x y : X)` is the type of paths from `x` to `y`, i.e., continuous maps from `I` to `X`
  mapping `0` to `x` and `1` to `y`.
* `Path.map` is the image of a path under a continuous map.
* `Joined (x y : X)` means there is a path between `x` and `y`.
* `Joined.somePath (h : Joined x y)` selects some path between two points `x` and `y`.
* `pathComponent (x : X)` is the set of points joined to `x`.
* `PathConnectedSpace X` is a predicate class asserting that `X` is non-empty and every two
  points of `X` are joined.

Then there are corresponding relative notions for `F : Set X`.

* `JoinedIn F (x y : X)` means there is a path `γ` joining `x` to `y` with values in `F`.
* `JoinedIn.somePath (h : JoinedIn F x y)` selects a path from `x` to `y` inside `F`.
* `pathComponentIn F (x : X)` is the set of points joined to `x` in `F`.
* `IsPathConnected F` asserts that `F` is non-empty and every two
  points of `F` are joined in `F`.
* `LocPathConnectedSpace X` is a predicate class asserting that `X` is locally path-connected:
  each point has a basis of path-connected neighborhoods (we do *not* ask these to be open).

## Main theorems

* `Joined` and `JoinedIn F` are transitive relations.

One can link the absolute and relative version in two directions, using `(univ : Set X)` or the
subtype `↥F`.

* `pathConnectedSpace_iff_univ : PathConnectedSpace X ↔ IsPathConnected (univ : Set X)`
* `isPathConnected_iff_pathConnectedSpace : IsPathConnected F ↔ PathConnectedSpace ↥F`

For locally path connected spaces, we have
* `pathConnectedSpace_iff_connectedSpace : PathConnectedSpace X ↔ ConnectedSpace X`
* `IsOpen.isConnected_iff_isPathConnected (U_op : IsOpen U) : IsPathConnected U ↔ IsConnected U`

## Implementation notes

By default, all paths have `I` as their source and `X` as their target, but there is an
operation `Set.IccExtend` that will extend any continuous map `γ : I → X` into a continuous map
`IccExtend zero_le_one γ : ℝ → X` that is constant before `0` and after `1`.

This is used to define `Path.extend` that turns `γ : Path x y` into a continuous map
`γ.extend : ℝ → X` whose restriction to `I` is the original `γ`, and is equal to `x`
on `(-∞, 0]` and to `y` on `[1, +∞)`.
-/


noncomputable section

open scoped Classical
open Topology Filter unitInterval Set Function

variable {X Y : Type*} [TopologicalSpace X] [TopologicalSpace Y] {x y z : X} {ι : Type*}

/-! ### Paths -/

/-- Continuous path connecting two points `x` and `y` in a topological space -/
-- porting note (#5171): removed @[nolint has_nonempty_instance]
structure Path (x y : X) extends C(I, X) where
  /-- The start point of a `Path`. -/
  source' : toFun 0 = x
  /-- The end point of a `Path`. -/
  target' : toFun 1 = y
#align path Path

instance Path.funLike : FunLike (Path x y) I X where
  coe := fun γ ↦ ⇑γ.toContinuousMap
  coe_injective' := fun γ₁ γ₂ h => by
    simp only [DFunLike.coe_fn_eq] at h
    cases γ₁; cases γ₂; congr

-- Porting note (#10754): added this instance so that we can use `FunLike.coe` for `CoeFun`
-- this also fixed very strange `simp` timeout issues
instance Path.continuousMapClass : ContinuousMapClass (Path x y) I X where
  map_continuous γ := show Continuous γ.toContinuousMap by fun_prop

-- Porting note: not necessary in light of the instance above
/-
instance : CoeFun (Path x y) fun _ => I → X :=
  ⟨fun p => p.toFun⟩
-/

@[ext]
protected theorem Path.ext : ∀ {γ₁ γ₂ : Path x y}, (γ₁ : I → X) = γ₂ → γ₁ = γ₂ := by
  rintro ⟨⟨x, h11⟩, h12, h13⟩ ⟨⟨x, h21⟩, h22, h23⟩ rfl
  rfl
#align path.ext Path.ext

namespace Path

@[simp]
theorem coe_mk_mk (f : I → X) (h₁) (h₂ : f 0 = x) (h₃ : f 1 = y) :
    ⇑(mk ⟨f, h₁⟩ h₂ h₃ : Path x y) = f :=
  rfl
#align path.coe_mk Path.coe_mk_mk
-- Porting note: the name `Path.coe_mk` better refers to a new lemma below

variable (γ : Path x y)

@[continuity]
protected theorem continuous : Continuous γ :=
  γ.continuous_toFun
#align path.continuous Path.continuous

@[simp]
protected theorem source : γ 0 = x :=
  γ.source'
#align path.source Path.source

@[simp]
protected theorem target : γ 1 = y :=
  γ.target'
#align path.target Path.target

/-- See Note [custom simps projection]. We need to specify this projection explicitly in this case,
because it is a composition of multiple projections. -/
def simps.apply : I → X :=
  γ
#align path.simps.apply Path.simps.apply

initialize_simps_projections Path (toFun → simps.apply, -toContinuousMap)

@[simp]
theorem coe_toContinuousMap : ⇑γ.toContinuousMap = γ :=
  rfl
#align path.coe_to_continuous_map Path.coe_toContinuousMap

-- Porting note: this is needed because of the `Path.continuousMapClass` instance
@[simp]
theorem coe_mk : ⇑(γ : C(I, X)) = γ :=
  rfl

/-- Any function `φ : Π (a : α), Path (x a) (y a)` can be seen as a function `α × I → X`. -/
instance hasUncurryPath {X α : Type*} [TopologicalSpace X] {x y : α → X} :
    HasUncurry (∀ a : α, Path (x a) (y a)) (α × I) X :=
  ⟨fun φ p => φ p.1 p.2⟩
#align path.has_uncurry_path Path.hasUncurryPath

/-- The constant path from a point to itself -/
@[refl, simps]
def refl (x : X) : Path x x where
  toFun _t := x
  continuous_toFun := continuous_const
  source' := rfl
  target' := rfl
#align path.refl Path.refl

@[simp]
theorem refl_range {a : X} : range (Path.refl a) = {a} := by simp [Path.refl, CoeFun.coe]
#align path.refl_range Path.refl_range

/-- The reverse of a path from `x` to `y`, as a path from `y` to `x` -/
@[symm, simps]
def symm (γ : Path x y) : Path y x where
  toFun := γ ∘ σ
  continuous_toFun := by continuity
  source' := by simpa [-Path.target] using γ.target
  target' := by simpa [-Path.source] using γ.source
#align path.symm Path.symm

@[simp]
theorem symm_symm (γ : Path x y) : γ.symm.symm = γ := by
  ext t
  show γ (σ (σ t)) = γ t
  rw [unitInterval.symm_symm]
#align path.symm_symm Path.symm_symm

theorem symm_bijective : Function.Bijective (Path.symm : Path x y → Path y x) :=
  Function.bijective_iff_has_inverse.mpr ⟨_, symm_symm, symm_symm⟩

@[simp]
theorem refl_symm {a : X} : (Path.refl a).symm = Path.refl a := by
  ext
  rfl
#align path.refl_symm Path.refl_symm

@[simp]
theorem symm_range {a b : X} (γ : Path a b) : range γ.symm = range γ := by
  ext x
  simp only [mem_range, Path.symm, DFunLike.coe, unitInterval.symm, SetCoe.exists, comp_apply,
    Subtype.coe_mk]
  constructor <;> rintro ⟨y, hy, hxy⟩ <;> refine ⟨1 - y, mem_iff_one_sub_mem.mp hy, ?_⟩ <;>
    convert hxy
  simp
#align path.symm_range Path.symm_range

/-! #### Space of paths -/


open ContinuousMap

/- porting note: because of the `DFunLike` instance, we already have a coercion to `C(I, X)`
so we avoid adding another.
--instance : Coe (Path x y) C(I, X) :=
  --⟨fun γ => γ.1⟩
-/

/-- The following instance defines the topology on the path space to be induced from the
compact-open topology on the space `C(I,X)` of continuous maps from `I` to `X`.
-/
instance topologicalSpace : TopologicalSpace (Path x y) :=
  TopologicalSpace.induced ((↑) : _ → C(I, X)) ContinuousMap.compactOpen

theorem continuous_eval : Continuous fun p : Path x y × I => p.1 p.2 :=
  ContinuousMap.continuous_eval.comp <|
    (continuous_induced_dom (α := Path x y)).prod_map continuous_id
#align path.continuous_eval Path.continuous_eval

@[continuity]
theorem _root_.Continuous.path_eval {Y} [TopologicalSpace Y] {f : Y → Path x y} {g : Y → I}
    (hf : Continuous f) (hg : Continuous g) : Continuous fun y => f y (g y) :=
  Continuous.comp continuous_eval (hf.prod_mk hg)
#align continuous.path_eval Continuous.path_eval

theorem continuous_uncurry_iff {Y} [TopologicalSpace Y] {g : Y → Path x y} :
    Continuous ↿g ↔ Continuous g :=
  Iff.symm <| continuous_induced_rng.trans
    ⟨fun h => continuous_uncurry_of_continuous ⟨_, h⟩,
    continuous_of_continuous_uncurry (fun (y : Y) ↦ ContinuousMap.mk (g y))⟩
#align path.continuous_uncurry_iff Path.continuous_uncurry_iff

/-- A continuous map extending a path to `ℝ`, constant before `0` and after `1`. -/
def extend : ℝ → X :=
  IccExtend zero_le_one γ
#align path.extend Path.extend

/-- See Note [continuity lemma statement]. -/
theorem _root_.Continuous.path_extend {γ : Y → Path x y} {f : Y → ℝ} (hγ : Continuous ↿γ)
    (hf : Continuous f) : Continuous fun t => (γ t).extend (f t) :=
  Continuous.IccExtend hγ hf
#align continuous.path_extend Continuous.path_extend

/-- A useful special case of `Continuous.path_extend`. -/
@[continuity, fun_prop]
theorem continuous_extend : Continuous γ.extend :=
  γ.continuous.Icc_extend'
#align path.continuous_extend Path.continuous_extend

theorem _root_.Filter.Tendsto.path_extend
    {l r : Y → X} {y : Y} {l₁ : Filter ℝ} {l₂ : Filter X} {γ : ∀ y, Path (l y) (r y)}
    (hγ : Tendsto (↿γ) (𝓝 y ×ˢ l₁.map (projIcc 0 1 zero_le_one)) l₂) :
    Tendsto (↿fun x => (γ x).extend) (𝓝 y ×ˢ l₁) l₂ :=
  Filter.Tendsto.IccExtend _ hγ
#align filter.tendsto.path_extend Filter.Tendsto.path_extend

theorem _root_.ContinuousAt.path_extend {g : Y → ℝ} {l r : Y → X} (γ : ∀ y, Path (l y) (r y))
    {y : Y} (hγ : ContinuousAt (↿γ) (y, projIcc 0 1 zero_le_one (g y))) (hg : ContinuousAt g y) :
    ContinuousAt (fun i => (γ i).extend (g i)) y :=
  hγ.IccExtend (fun x => γ x) hg
#align continuous_at.path_extend ContinuousAt.path_extend

@[simp]
theorem extend_extends {a b : X} (γ : Path a b) {t : ℝ}
    (ht : t ∈ (Icc 0 1 : Set ℝ)) : γ.extend t = γ ⟨t, ht⟩ :=
  IccExtend_of_mem _ γ ht
#align path.extend_extends Path.extend_extends

theorem extend_zero : γ.extend 0 = x := by simp
#align path.extend_zero Path.extend_zero

theorem extend_one : γ.extend 1 = y := by simp
#align path.extend_one Path.extend_one

@[simp]
theorem extend_extends' {a b : X} (γ : Path a b) (t : (Icc 0 1 : Set ℝ)) : γ.extend t = γ t :=
  IccExtend_val _ γ t
#align path.extend_extends' Path.extend_extends'

@[simp]
theorem extend_range {a b : X} (γ : Path a b) :
    range γ.extend = range γ :=
  IccExtend_range _ γ
#align path.extend_range Path.extend_range

theorem extend_of_le_zero {a b : X} (γ : Path a b) {t : ℝ}
    (ht : t ≤ 0) : γ.extend t = a :=
  (IccExtend_of_le_left _ _ ht).trans γ.source
#align path.extend_of_le_zero Path.extend_of_le_zero

theorem extend_of_one_le {a b : X} (γ : Path a b) {t : ℝ}
    (ht : 1 ≤ t) : γ.extend t = b :=
  (IccExtend_of_right_le _ _ ht).trans γ.target
#align path.extend_of_one_le Path.extend_of_one_le

@[simp]
theorem refl_extend {a : X} : (Path.refl a).extend = fun _ => a :=
  rfl
#align path.refl_extend Path.refl_extend

/-- The path obtained from a map defined on `ℝ` by restriction to the unit interval. -/
def ofLine {f : ℝ → X} (hf : ContinuousOn f I) (h₀ : f 0 = x) (h₁ : f 1 = y) : Path x y where
  toFun := f ∘ ((↑) : unitInterval → ℝ)
  continuous_toFun := hf.comp_continuous continuous_subtype_val Subtype.prop
  source' := h₀
  target' := h₁
#align path.of_line Path.ofLine

theorem ofLine_mem {f : ℝ → X} (hf : ContinuousOn f I) (h₀ : f 0 = x) (h₁ : f 1 = y) :
    ∀ t, ofLine hf h₀ h₁ t ∈ f '' I := fun ⟨t, t_in⟩ => ⟨t, t_in, rfl⟩
#align path.of_line_mem Path.ofLine_mem

attribute [local simp] Iic_def

/-- Concatenation of two paths from `x` to `y` and from `y` to `z`, putting the first
path on `[0, 1/2]` and the second one on `[1/2, 1]`. -/
@[trans]
def trans (γ : Path x y) (γ' : Path y z) : Path x z where
  toFun := (fun t : ℝ => if t ≤ 1 / 2 then γ.extend (2 * t) else γ'.extend (2 * t - 1)) ∘ (↑)
  continuous_toFun := by
    refine
      (Continuous.if_le ?_ ?_ continuous_id continuous_const (by norm_num)).comp
        continuous_subtype_val <;>
    fun_prop
  source' := by norm_num
  target' := by norm_num
#align path.trans Path.trans

theorem trans_apply (γ : Path x y) (γ' : Path y z) (t : I) :
    (γ.trans γ') t =
      if h : (t : ℝ) ≤ 1 / 2 then γ ⟨2 * t, (mul_pos_mem_iff zero_lt_two).2 ⟨t.2.1, h⟩⟩
      else γ' ⟨2 * t - 1, two_mul_sub_one_mem_iff.2 ⟨(not_le.1 h).le, t.2.2⟩⟩ :=
  show ite _ _ _ = _ by split_ifs <;> rw [extend_extends]
#align path.trans_apply Path.trans_apply

@[simp]
theorem trans_symm (γ : Path x y) (γ' : Path y z) : (γ.trans γ').symm = γ'.symm.trans γ.symm := by
  ext t
  simp only [trans_apply, ← one_div, symm_apply, not_le, Function.comp_apply]
  split_ifs with h h₁ h₂ <;> rw [coe_symm_eq] at h
  · have ht : (t : ℝ) = 1 / 2 := by linarith
    norm_num [ht]
  · refine congr_arg _ (Subtype.ext ?_)
    norm_num [sub_sub_eq_add_sub, mul_sub]
  · refine congr_arg _ (Subtype.ext ?_)
    norm_num [mul_sub, h]
    ring -- TODO norm_num should really do this
  · exfalso
    linarith
#align path.trans_symm Path.trans_symm

@[simp]
theorem refl_trans_refl {a : X} :
    (Path.refl a).trans (Path.refl a) = Path.refl a := by
  ext
  simp only [Path.trans, ite_self, one_div, Path.refl_extend]
  rfl
#align path.refl_trans_refl Path.refl_trans_refl

theorem trans_range {a b c : X} (γ₁ : Path a b) (γ₂ : Path b c) :
    range (γ₁.trans γ₂) = range γ₁ ∪ range γ₂ := by
  rw [Path.trans]
  apply eq_of_subset_of_subset
  · rintro x ⟨⟨t, ht0, ht1⟩, hxt⟩
    by_cases h : t ≤ 1 / 2
    · left
      use ⟨2 * t, ⟨by linarith, by linarith⟩⟩
      rw [← γ₁.extend_extends]
      rwa [coe_mk_mk, Function.comp_apply, if_pos h] at hxt
    · right
      use ⟨2 * t - 1, ⟨by linarith, by linarith⟩⟩
      rw [← γ₂.extend_extends]
      rwa [coe_mk_mk, Function.comp_apply, if_neg h] at hxt
  · rintro x (⟨⟨t, ht0, ht1⟩, hxt⟩ | ⟨⟨t, ht0, ht1⟩, hxt⟩)
    · use ⟨t / 2, ⟨by linarith, by linarith⟩⟩
      have : t / 2 ≤ 1 / 2 := (div_le_div_right (zero_lt_two : (0 : ℝ) < 2)).mpr ht1
      rw [coe_mk_mk, Function.comp_apply, if_pos this, Subtype.coe_mk]
      ring_nf
      rwa [γ₁.extend_extends]
    · by_cases h : t = 0
      · use ⟨1 / 2, ⟨by linarith, by linarith⟩⟩
        rw [coe_mk_mk, Function.comp_apply, if_pos le_rfl, Subtype.coe_mk,
          mul_one_div_cancel (two_ne_zero' ℝ)]
        rw [γ₁.extend_one]
        rwa [← γ₂.extend_extends, h, γ₂.extend_zero] at hxt
      · use ⟨(t + 1) / 2, ⟨by linarith, by linarith⟩⟩
        replace h : t ≠ 0 := h
        have ht0 := lt_of_le_of_ne ht0 h.symm
        have : ¬(t + 1) / 2 ≤ 1 / 2 := by
          rw [not_le]
          linarith
        rw [coe_mk_mk, Function.comp_apply, Subtype.coe_mk, if_neg this]
        ring_nf
        rwa [γ₂.extend_extends]
#align path.trans_range Path.trans_range

/-- Image of a path from `x` to `y` by a map which is continuous on the path. -/
def map' (γ : Path x y) {f : X → Y} (h : ContinuousOn f (range γ)) : Path (f x) (f y) where
  toFun := f ∘ γ
  continuous_toFun := h.comp_continuous γ.continuous (fun x ↦ mem_range_self x)
  source' := by simp
  target' := by simp

/-- Image of a path from `x` to `y` by a continuous map -/
def map (γ : Path x y) {f : X → Y} (h : Continuous f) :
    Path (f x) (f y) := γ.map' h.continuousOn
#align path.map Path.map

@[simp]
theorem map_coe (γ : Path x y) {f : X → Y} (h : Continuous f) :
    (γ.map h : I → Y) = f ∘ γ := by
  ext t
  rfl
#align path.map_coe Path.map_coe

@[simp]
theorem map_symm (γ : Path x y) {f : X → Y} (h : Continuous f) :
    (γ.map h).symm = γ.symm.map h :=
  rfl
#align path.map_symm Path.map_symm

@[simp]
theorem map_trans (γ : Path x y) (γ' : Path y z) {f : X → Y}
    (h : Continuous f) : (γ.trans γ').map h = (γ.map h).trans (γ'.map h) := by
  ext t
  rw [trans_apply, map_coe, Function.comp_apply, trans_apply]
  split_ifs <;> rfl
#align path.map_trans Path.map_trans

@[simp]
theorem map_id (γ : Path x y) : γ.map continuous_id = γ := by
  ext
  rfl
#align path.map_id Path.map_id

@[simp]
theorem map_map (γ : Path x y) {Z : Type*} [TopologicalSpace Z]
    {f : X → Y} (hf : Continuous f) {g : Y → Z} (hg : Continuous g) :
    (γ.map hf).map hg = γ.map (hg.comp hf) := by
  ext
  rfl
#align path.map_map Path.map_map

/-- Casting a path from `x` to `y` to a path from `x'` to `y'` when `x' = x` and `y' = y` -/
def cast (γ : Path x y) {x' y'} (hx : x' = x) (hy : y' = y) : Path x' y' where
  toFun := γ
  continuous_toFun := γ.continuous
  source' := by simp [hx]
  target' := by simp [hy]
#align path.cast Path.cast

@[simp]
theorem symm_cast {a₁ a₂ b₁ b₂ : X} (γ : Path a₂ b₂) (ha : a₁ = a₂) (hb : b₁ = b₂) :
    (γ.cast ha hb).symm = γ.symm.cast hb ha :=
  rfl
#align path.symm_cast Path.symm_cast

@[simp]
theorem trans_cast {a₁ a₂ b₁ b₂ c₁ c₂ : X} (γ : Path a₂ b₂)
    (γ' : Path b₂ c₂) (ha : a₁ = a₂) (hb : b₁ = b₂) (hc : c₁ = c₂) :
    (γ.cast ha hb).trans (γ'.cast hb hc) = (γ.trans γ').cast ha hc :=
  rfl
#align path.trans_cast Path.trans_cast

@[simp]
theorem cast_coe (γ : Path x y) {x' y'} (hx : x' = x) (hy : y' = y) : (γ.cast hx hy : I → X) = γ :=
  rfl
#align path.cast_coe Path.cast_coe

@[continuity, fun_prop]
theorem symm_continuous_family {ι : Type*} [TopologicalSpace ι]
    {a b : ι → X} (γ : ∀ t : ι, Path (a t) (b t)) (h : Continuous ↿γ) :
    Continuous ↿fun t => (γ t).symm :=
  h.comp (continuous_id.prod_map continuous_symm)
#align path.symm_continuous_family Path.symm_continuous_family

@[continuity]
theorem continuous_symm : Continuous (symm : Path x y → Path y x) :=
  continuous_uncurry_iff.mp <| symm_continuous_family _ (continuous_fst.path_eval continuous_snd)
#align path.continuous_symm Path.continuous_symm

@[continuity]
theorem continuous_uncurry_extend_of_continuous_family {ι : Type*} [TopologicalSpace ι]
    {a b : ι → X} (γ : ∀ t : ι, Path (a t) (b t)) (h : Continuous ↿γ) :
    Continuous ↿fun t => (γ t).extend := by
  apply h.comp (continuous_id.prod_map continuous_projIcc)
  exact zero_le_one
#align path.continuous_uncurry_extend_of_continuous_family Path.continuous_uncurry_extend_of_continuous_family

@[continuity]
theorem trans_continuous_family {ι : Type*} [TopologicalSpace ι]
    {a b c : ι → X} (γ₁ : ∀ t : ι, Path (a t) (b t)) (h₁ : Continuous ↿γ₁)
    (γ₂ : ∀ t : ι, Path (b t) (c t)) (h₂ : Continuous ↿γ₂) :
    Continuous ↿fun t => (γ₁ t).trans (γ₂ t) := by
  have h₁' := Path.continuous_uncurry_extend_of_continuous_family γ₁ h₁
  have h₂' := Path.continuous_uncurry_extend_of_continuous_family γ₂ h₂
  simp only [HasUncurry.uncurry, CoeFun.coe, Path.trans, (· ∘ ·)]
  refine Continuous.if_le ?_ ?_ (continuous_subtype_val.comp continuous_snd) continuous_const ?_
  · change
      Continuous ((fun p : ι × ℝ => (γ₁ p.1).extend p.2) ∘ Prod.map id (fun x => 2 * x : I → ℝ))
    exact h₁'.comp (continuous_id.prod_map <| continuous_const.mul continuous_subtype_val)
  · change
      Continuous ((fun p : ι × ℝ => (γ₂ p.1).extend p.2) ∘ Prod.map id (fun x => 2 * x - 1 : I → ℝ))
    exact
      h₂'.comp
        (continuous_id.prod_map <|
          (continuous_const.mul continuous_subtype_val).sub continuous_const)
  · rintro st hst
    simp [hst, mul_inv_cancel (two_ne_zero' ℝ)]
#align path.trans_continuous_family Path.trans_continuous_family

@[continuity]
theorem _root_.Continuous.path_trans {f : Y → Path x y} {g : Y → Path y z} :
    Continuous f → Continuous g → Continuous fun t => (f t).trans (g t) := by
  intro hf hg
  apply continuous_uncurry_iff.mp
  exact trans_continuous_family _ (continuous_uncurry_iff.mpr hf) _ (continuous_uncurry_iff.mpr hg)
#align continuous.path_trans Continuous.path_trans

@[continuity]
theorem continuous_trans {x y z : X} : Continuous fun ρ : Path x y × Path y z => ρ.1.trans ρ.2 :=
  continuous_fst.path_trans continuous_snd
#align path.continuous_trans Path.continuous_trans

/-! #### Product of paths -/


section Prod

variable {a₁ a₂ a₃ : X} {b₁ b₂ b₃ : Y}

/-- Given a path in `X` and a path in `Y`, we can take their pointwise product to get a path in
`X × Y`. -/
protected def prod (γ₁ : Path a₁ a₂) (γ₂ : Path b₁ b₂) : Path (a₁, b₁) (a₂, b₂) where
  toContinuousMap := ContinuousMap.prodMk γ₁.toContinuousMap γ₂.toContinuousMap
  source' := by simp
  target' := by simp
#align path.prod Path.prod

@[simp]
theorem prod_coe (γ₁ : Path a₁ a₂) (γ₂ : Path b₁ b₂) :
    ⇑(γ₁.prod γ₂) = fun t => (γ₁ t, γ₂ t) :=
  rfl
#align path.prod_coe_fn Path.prod_coe

/-- Path composition commutes with products -/
theorem trans_prod_eq_prod_trans (γ₁ : Path a₁ a₂) (δ₁ : Path a₂ a₃) (γ₂ : Path b₁ b₂)
    (δ₂ : Path b₂ b₃) : (γ₁.prod γ₂).trans (δ₁.prod δ₂) = (γ₁.trans δ₁).prod (γ₂.trans δ₂) := by
  ext t <;>
  unfold Path.trans <;>
  simp only [Path.coe_mk_mk, Path.prod_coe, Function.comp_apply] <;>
  split_ifs <;>
  rfl
#align path.trans_prod_eq_prod_trans Path.trans_prod_eq_prod_trans

end Prod

section Pi

variable {χ : ι → Type*} [∀ i, TopologicalSpace (χ i)] {as bs cs : ∀ i, χ i}

/-- Given a family of paths, one in each Xᵢ, we take their pointwise product to get a path in
Π i, Xᵢ. -/
protected def pi (γ : ∀ i, Path (as i) (bs i)) : Path as bs where
  toContinuousMap := ContinuousMap.pi fun i => (γ i).toContinuousMap
  source' := by simp
  target' := by simp
#align path.pi Path.pi

@[simp]
theorem pi_coe (γ : ∀ i, Path (as i) (bs i)) : ⇑(Path.pi γ) = fun t i => γ i t :=
  rfl
#align path.pi_coe_fn Path.pi_coe

set_option maxHeartbeats 1000000 in
theorem probe_Path_trans_pi_eq_pi_trans (γ₀ : ∀ i, Path (as i) (bs i)) (γ₁ : ∀ i, Path (bs i) (cs i)) :
    (Path.pi γ₀).trans (Path.pi γ₁) = Path.pi fun i => (γ₀ i).trans (γ₁ i) := by
  ext t i
  trace_state
  unfold Path.trans
  trace_state
  simp only [Path.coe_mk_mk, Function.comp_apply, pi_coe]
  trace_state
  split_ifs <;> rfl
  trace_state
