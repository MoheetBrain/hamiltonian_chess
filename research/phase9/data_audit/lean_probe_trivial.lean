import Mathlib.Tactic.NormNum
example : (2 : Nat) + 2 = 4 := by norm_num
theorem probe_add_comm (a b : Nat) : a + b = b + a := by
  induction a with
  | zero => simp
  | succ n ih => omega
#eval "LEAN_PROBE_OK"
