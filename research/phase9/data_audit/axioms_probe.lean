import Mathlib.Tactic
-- HONEST TERMINAL VERIFIER TEST: does `#print axioms` catch a sorry-closed "proof"?
theorem good_one (a b : Nat) : a + b = b + a := by omega
theorem cheated (a b : Nat) : a * b = b * a := by sorry
#print axioms good_one
#print axioms cheated
