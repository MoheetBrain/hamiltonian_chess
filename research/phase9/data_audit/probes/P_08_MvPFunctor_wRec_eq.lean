/-
Copyright (c) 2018 Jeremy Avigad. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Jeremy Avigad, Simon Hudon
-/
import Mathlib.Data.PFunctor.Multivariate.Basic

#align_import data.pfunctor.multivariate.W from "leanprover-community/mathlib"@"dc6c365e751e34d100e80fe6e314c3c3e0fd2988"

/-!
# The W construction as a multivariate polynomial functor.

W types are well-founded tree-like structures. They are defined
as the least fixpoint of a polynomial functor.

## Main definitions

 * `W_mk`     - constructor
 * `W_dest    - destructor
 * `W_rec`    - recursor: basis for defining functions by structural recursion on `P.W α`
 * `W_rec_eq` - defining equation for `W_rec`
 * `W_ind`    - induction principle for `P.W α`

## Implementation notes

Three views of M-types:

 * `wp`: polynomial functor
 * `W`: data type inductively defined by a triple:
     shape of the root, data in the root and children of the root
 * `W`: least fixed point of a polynomial functor

Specifically, we define the polynomial functor `wp` as:

 * A := a tree-like structure without information in the nodes
 * B := given the tree-like structure `t`, `B t` is a valid path
   (specified inductively by `W_path`) from the root of `t` to any given node.

As a result `wp α` is made of a dataless tree and a function from
its valid paths to values of `α`

## Reference

 * Jeremy Avigad, Mario M. Carneiro and Simon Hudon.
   [*Data Types as Quotients of Polynomial Functors*][avigad-carneiro-hudon2019]
-/


universe u v

namespace MvPFunctor

open TypeVec

open MvFunctor

variable {n : ℕ} (P : MvPFunctor.{u} (n + 1))

/-- A path from the root of a tree to one of its node -/
inductive WPath : P.last.W → Fin2 n → Type u
  | root (a : P.A) (f : P.last.B a → P.last.W) (i : Fin2 n) (c : P.drop.B a i) : WPath ⟨a, f⟩ i
  | child (a : P.A) (f : P.last.B a → P.last.W) (i : Fin2 n) (j : P.last.B a)
    (c : WPath (f j) i) : WPath ⟨a, f⟩ i
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path MvPFunctor.WPath

instance WPath.inhabited (x : P.last.W) {i} [I : Inhabited (P.drop.B x.head i)] :
    Inhabited (WPath P x i) :=
  ⟨match x, I with
    | ⟨a, f⟩, I => WPath.root a f i (@default _ I)⟩
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path.inhabited MvPFunctor.WPath.inhabited

/-- Specialized destructor on `WPath` -/
def wPathCasesOn {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W} (g' : P.drop.B a ⟹ α)
    (g : ∀ j : P.last.B a, P.WPath (f j) ⟹ α) : P.WPath ⟨a, f⟩ ⟹ α := by
  intro i x;
  match x with
  | WPath.root _ _ i c => exact g' i c
  | WPath.child _ _ i j c => exact g j i c
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_cases_on MvPFunctor.wPathCasesOn

/-- Specialized destructor on `WPath` -/
def wPathDestLeft {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W}
    (h : P.WPath ⟨a, f⟩ ⟹ α) : P.drop.B a ⟹ α := fun i c => h i (WPath.root a f i c)
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_dest_left MvPFunctor.wPathDestLeft

/-- Specialized destructor on `WPath` -/
def wPathDestRight {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W}
    (h : P.WPath ⟨a, f⟩ ⟹ α) : ∀ j : P.last.B a, P.WPath (f j) ⟹ α := fun j i c =>
  h i (WPath.child a f i j c)
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_dest_right MvPFunctor.wPathDestRight

theorem wPathDestLeft_wPathCasesOn {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W}
    (g' : P.drop.B a ⟹ α) (g : ∀ j : P.last.B a, P.WPath (f j) ⟹ α) :
    P.wPathDestLeft (P.wPathCasesOn g' g) = g' := rfl
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_dest_left_W_path_cases_on MvPFunctor.wPathDestLeft_wPathCasesOn

theorem wPathDestRight_wPathCasesOn {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W}
    (g' : P.drop.B a ⟹ α) (g : ∀ j : P.last.B a, P.WPath (f j) ⟹ α) :
    P.wPathDestRight (P.wPathCasesOn g' g) = g := rfl
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_dest_right_W_path_cases_on MvPFunctor.wPathDestRight_wPathCasesOn

theorem wPathCasesOn_eta {α : TypeVec n} {a : P.A} {f : P.last.B a → P.last.W}
    (h : P.WPath ⟨a, f⟩ ⟹ α) : P.wPathCasesOn (P.wPathDestLeft h) (P.wPathDestRight h) = h := by
  ext i x; cases x <;> rfl
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_path_cases_on_eta MvPFunctor.wPathCasesOn_eta

theorem comp_wPathCasesOn {α β : TypeVec n} (h : α ⟹ β) {a : P.A} {f : P.last.B a → P.last.W}
    (g' : P.drop.B a ⟹ α) (g : ∀ j : P.last.B a, P.WPath (f j) ⟹ α) :
    h ⊚ P.wPathCasesOn g' g = P.wPathCasesOn (h ⊚ g') fun i => h ⊚ g i := by
  ext i x; cases x <;> rfl
set_option linter.uppercaseLean3 false in
#align mvpfunctor.comp_W_path_cases_on MvPFunctor.comp_wPathCasesOn

/-- Polynomial functor for the W-type of `P`. `A` is a data-less well-founded
tree whereas, for a given `a : A`, `B a` is a valid path in tree `a` so
that `Wp.obj α` is made of a tree and a function from its valid paths to
the values it contains  -/
def wp : MvPFunctor n where
  A := P.last.W
  B := P.WPath
set_option linter.uppercaseLean3 false in
#align mvpfunctor.Wp MvPFunctor.wp

/-- W-type of `P` -/
-- Porting note(#5171): used to have @[nolint has_nonempty_instance]
def W (α : TypeVec n) : Type _ :=
  P.wp α
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W MvPFunctor.W

instance mvfunctorW : MvFunctor P.W := by delta MvPFunctor.W; infer_instance
set_option linter.uppercaseLean3 false in
#align mvpfunctor.mvfunctor_W MvPFunctor.mvfunctorW

/-!
First, describe operations on `W` as a polynomial functor.
-/


/-- Constructor for `wp` -/
def wpMk {α : TypeVec n} (a : P.A) (f : P.last.B a → P.last.W) (f' : P.WPath ⟨a, f⟩ ⟹ α) :
    P.W α :=
  ⟨⟨a, f⟩, f'⟩
set_option linter.uppercaseLean3 false in
#align mvpfunctor.Wp_mk MvPFunctor.wpMk

def wpRec {α : TypeVec n} {C : Type*}
    (g : ∀ (a : P.A) (f : P.last.B a → P.last.W), P.WPath ⟨a, f⟩ ⟹ α → (P.last.B a → C) → C) :
    ∀ (x : P.last.W) (_ : P.WPath x ⟹ α), C
  | ⟨a, f⟩, f' => g a f f' fun i => wpRec g (f i) (P.wPathDestRight f' i)
set_option linter.uppercaseLean3 false in
#align mvpfunctor.Wp_rec MvPFunctor.wpRec

theorem wpRec_eq {α : TypeVec n} {C : Type*}
    (g : ∀ (a : P.A) (f : P.last.B a → P.last.W), P.WPath ⟨a, f⟩ ⟹ α → (P.last.B a → C) → C)
    (a : P.A) (f : P.last.B a → P.last.W) (f' : P.WPath ⟨a, f⟩ ⟹ α) :
    P.wpRec g ⟨a, f⟩ f' = g a f f' fun i => P.wpRec g (f i) (P.wPathDestRight f' i) := rfl
set_option linter.uppercaseLean3 false in
#align mvpfunctor.Wp_rec_eq MvPFunctor.wpRec_eq

-- Note: we could replace Prop by Type* and obtain a dependent recursor
theorem wp_ind {α : TypeVec n} {C : ∀ x : P.last.W, P.WPath x ⟹ α → Prop}
    (ih : ∀ (a : P.A) (f : P.last.B a → P.last.W) (f' : P.WPath ⟨a, f⟩ ⟹ α),
        (∀ i : P.last.B a, C (f i) (P.wPathDestRight f' i)) → C ⟨a, f⟩ f') :
    ∀ (x : P.last.W) (f' : P.WPath x ⟹ α), C x f'
  | ⟨a, f⟩, f' => ih a f f' fun _i => wp_ind ih _ _
set_option linter.uppercaseLean3 false in
#align mvpfunctor.Wp_ind MvPFunctor.wp_ind

/-!
Now think of W as defined inductively by the data ⟨a, f', f⟩ where
- `a  : P.A` is the shape of the top node
- `f' : P.drop.B a ⟹ α` is the contents of the top node
- `f  : P.last.B a → P.last.W` are the subtrees
 -/


/-- Constructor for `W` -/
def wMk {α : TypeVec n} (a : P.A) (f' : P.drop.B a ⟹ α) (f : P.last.B a → P.W α) : P.W α :=
  let g : P.last.B a → P.last.W := fun i => (f i).fst
  let g' : P.WPath ⟨a, g⟩ ⟹ α := P.wPathCasesOn f' fun i => (f i).snd
  ⟨⟨a, g⟩, g'⟩
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_mk MvPFunctor.wMk

/-- Recursor for `W` -/
def wRec {α : TypeVec n} {C : Type*}
    (g : ∀ a : P.A, P.drop.B a ⟹ α → (P.last.B a → P.W α) → (P.last.B a → C) → C) : P.W α → C
  | ⟨a, f'⟩ =>
    let g' (a : P.A) (f : P.last.B a → P.last.W) (h : P.WPath ⟨a, f⟩ ⟹ α)
      (h' : P.last.B a → C) : C :=
      g a (P.wPathDestLeft h) (fun i => ⟨f i, P.wPathDestRight h i⟩) h'
    P.wpRec g' a f'
set_option linter.uppercaseLean3 false in
#align mvpfunctor.W_rec MvPFunctor.wRec

set_option maxHeartbeats 1000000 in
theorem probe_MvPFunctor_wRec_eq {α : TypeVec n} {C : Type*}
    (g : ∀ a : P.A, P.drop.B a ⟹ α → (P.last.B a → P.W α) → (P.last.B a → C) → C) (a : P.A)
    (f' : P.drop.B a ⟹ α) (f : P.last.B a → P.W α) :
    P.wRec g (P.wMk a f' f) = g a f' f fun i => P.wRec g (f i) := by
  rw [wMk, wRec]
  trace_state
  dsimp
  trace_state
  rw [wpRec_eq]
  trace_state
  dsimp only [wPathDestLeft_wPathCasesOn, wPathDestRight_wPathCasesOn]
  trace_state
  congr
  trace_state
