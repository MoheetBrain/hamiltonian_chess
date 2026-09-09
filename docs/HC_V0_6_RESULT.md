# HC-V0.6 — result

**Frozen before any outcome:** `docs/HC_V0_6_SPEC.md`, committed at `2624be5`. Nothing below
changed a threshold, an arm, an endpoint or a selection rule after data existed.

---

## 1. What was run

Four renderings of the **same** anchored Lean state, one action each, kernel-decided.

| | |
|---|---|
| evaluation universe | `f13ffee5…` — 1,127 anchors · 393 theorems · 330 mathlib files |
| arms | `R_A` (baseline) · `R_A_PRIME` (whitespace null) · `R_B` (structural) · `R_ABLATED` (`P_CHANGE` control) |
| endpoint | `KERNEL_ACCEPTED_STATE_CHANGE` — accepted **and** (closed **or** the declared state moved) |
| attempts | `k = 1`, no retry, no feedback, no search, no best-of-N |
| schedule | all arms branch from one live Lean `state_id`; arm order randomised within anchor |
| cluster unit | mathlib file |

**Primary model `gemma4:e4b`** (digest `c6eb396dbd59`, 8.0B, Q4_K_M), chosen by the frozen
information-rate rule on baseline-only preflight. 4,508 cells, **0 skipped anchors, 0 theorem
errors**, 4,508 solver calls, 971 s generation, 41 s Lean, 34 min wall clock, 0.215 s/call.

Integrity, checked on the emitted cells: every anchor has exactly four cells; every anchor's four
arms received four **distinct** prompts (0 exceptions); one solver identity throughout;
`verify_served` = `VERIFIED_AGAINST_LIVE_RUNTIME`.

## 2. The primary result

| arm | events | n | rate |
|---|---|---|---|
| `R_A` | 121 | 1,124 | **0.1077** |
| `R_A_PRIME` | 129 | 1,124 | 0.1148 |
| `R_B` | 133 | 1,124 | **0.1183** |
| `R_ABLATED` | 55 | 1,125 | 0.0489 |

| contrast | Δ | 95% cluster CI | permutation p | Holm p | verdict vs `δ_min = 0.05` |
|---|---|---|---|---|---|
| **`R_B` − `R_A`** (primary) | **+0.0107** | **[−0.0089, +0.0294]** | 0.325 | 0.974 | **inside the band, both ends** |
| `R_A′` − `R_A` (null control) | +0.0071 | [−0.0083, +0.0224] | 0.437 | 0.974 | equivalent |
| `R_ABLATED` − `R_A` (sensitivity) | **−0.0587** | **[−0.0848, −0.0339]** | 5.0e-05 | 0.0002 | detected |

**Realised ICC 0.0011; achieved MDE 0.0394.** The bank *does* resolve five points at this baseline —
`δ_min = 0.05` was reachable and was reached, which `docs/HC_V0_6_SPEC.md` §8a showed was not
guaranteed.

**This is a tight null, not an absence of evidence.** The 95% interval for the primary contrast is
[−0.9, +2.9] percentage points: the practical region is excluded at **both** ends, by an assay that
demonstrably detects a 5.9-point effect at p = 5×10⁻⁵.

**The preregistered administrative-move sensitivity analysis is clean: 0 of 438 events** had a tactic
head in `{rotate_left, rotate_right, rename, rename_i, clear, swap, next, case, case', pick_goal,
on_goal}`. The endpoint is not inflated by state-shuffling.

## 3. Two gates did not certify, and neither is softened here

**The sensitivity gate fails on magnitude.** `T_ablate` was fixed at 0.0665 from the *preflight*
baseline of 0.133 (spec §10a). The realised `R_A` baseline was 0.1077, and the ablation cost
0.0587 — a real, decisively detected effect that lands 0.8 points short of a threshold set from a
baseline that turned out to be high. Half the *realised* baseline would have been 0.0539 and would
have cleared. **The threshold is not moved.** What the data show is stated separately from what the
frozen gate says: the ablation is detected with a CI of [−8.5, −3.4] points and p = 5×10⁻⁵, so the
assay's sensitivity is *empirically established* even though the pre-declared magnitude is not met.

**The missingness gate fired, and it is a false block.** 11 cells failed with `ENVIRONMENT_ERROR`,
on **3 anchors**. Two anchors failed on all four arms; one failed on three, with `R_ABLATED`
happening to survive — so the raw per-arm counts are 3/3/3/2 and an exact-equality test calls that
"arm-dependent". It is not: `extract_pair` drops a *pair* when either arm is unanalysable, so every
contrast lost exactly the same 3 anchors and all three ran on **1,124 anchors / 329 clusters**. The
gate is doing what §9 asks of it — *false block ≫ false certification* — and the numbers above are
reported as measurements with the refusal stated, not with the gate retro-fitted.

**C1 is `UNAVAILABLE`, not zero.** `k = 1` leaves nothing to split (spec §10b). It decides no gate,
and its Holm slot is retained at p = 1.0 so a control that could not be measured does not shrink the
correction and make the primary easier to declare.

## 4. The finding the endpoint alone would have hidden

*Exploratory. Not preregistered. Reported because suppressing it would be the larger distortion.*

The representation **changes what the model does** on most states, without changing how often it
succeeds:

| comparison | different tactic | different tactic head |
|---|---|---|
| `R_A` vs `R_B` (structural) | **64.2%** of anchors | 35.7% |
| `R_A` vs `R_A′` (whitespace only) | **45.6%** of anchors | 22.2% |

Tactic-head mix, same 1,127 states: `rfl` 104 → 160, `cases` 41 → 66, `intro` 21 → 41, while `simp`
falls 156 → 120 and `exact` 185 → 150.

Two readings, and the second is the one that matters. First, **structure is causally active on the
policy**: 64.2% divergence against 45.6% for a pure byte perturbation leaves ~19 points of
divergence attributable to structure rather than to bytes changing at all. Second, and more
important, **the whitespace control alone flips the answer on 46% of states while moving the success
rate by 0.7 points**. The model's choice of tactic is extremely sensitive to its input bytes, and
that sensitivity does not convert into verified success — which is precisely why a representation
effect can be real at the level of behaviour and null at the level of outcome.

---

## 5. Cross-model

Four eligible models, one frozen bank, one frozen design. `gemma3:4b` was excluded before any
contrast by the pre-declared floor test (0/45 on the baseline preflight). Every identity was
verified against the live runtime; every pass ran on universe hash `f13ffee5…`.

| model | family | R_A | R_A′ | R_B | **Δ(R_B−R_A)** | 95% cluster CI | perm p | null Δ | ablation Δ |
|---|---|---|---|---|---|---|---|---|---|
| `gemma4:e4b` (primary) | gemma4 | 0.1077 | 0.1148 | 0.1183 | **+0.0107** | [−0.0089, +0.0294] | 0.325 | +0.0071 | **−0.0587** |
| `gemma4:12b` | gemma4 | 0.2724 | 0.2733 | 0.2635 | **−0.0089** | [−0.0261, +0.0087] | 0.377 | +0.0009 | not run |
| `qwen3.6:27b-mlx` | qwen3_5 | 0.2963 | 0.3007 | 0.2989 | **+0.0027** | [−0.0168, +0.0222] | 0.855 | +0.0044 | not run |
| `gemma4:31b` | gemma4 | 0.3861 | 0.3874 | 0.3882 | **+0.0018** | [−0.0210, +0.0241] | 0.941 | +0.0009 | not run |

**Sign consistency: none.** `+, −, +, +` — and the disagreement is *within* the gemma4 family, across
three sizes of one architecture. That is the shape of noise, not of a small consistent effect.

**Magnitude consistency: all four are ≤ 1.1 percentage points**, against an owner-specified practical
region of 5. Every interval lies entirely inside ±5 points; the widest bound in either direction
across all four models is +2.94 / −2.61.

**Family independence.** Three architectures are installed (`gemma3`, `gemma4`, `qwen3_5`) but
`gemma4:{e4b, 12b, 31b}` are one family at three sizes — correlated readers, not independent
replication. The genuinely independent evidence is **two families**: gemma4 and qwen3_5. That is
enough to say the null is not an artefact of one architecture, and not enough to call it universal.

**Precision, two ways.** The analytic MDE at 80% power is 0.039 / 0.054 / 0.056 / 0.063, so three of
the four formally fail to resolve five points. But the realised cluster-bootstrap half-widths are
**1.7 to 2.3 percentage points** — the MDE model assumes far more paired discordance than actually
occurred. The intervals are the operative statement, and they exclude a five-point effect in every
model. Both numbers are reported because the discrepancy is real and a reader should see it.

## 6. Policy divergence, replicated

*Exploratory throughout. Not preregistered. Never fitness.*

| model | different tactic under `R_B` | under whitespace-only | excess attributable to structure |
|---|---|---|---|
| `gemma4:e4b` | 64.2% | 45.6% | +18.5 |
| `gemma4:12b` | 43.2% | 32.4% | +10.8 |
| `qwen3.6:27b-mlx` | 49.6% | 30.4% | +19.2 |
| `gemma4:31b` | 48.8% | 41.3% | +7.5 |

Every model changes its answer on 43–64% of states under a structural re-layout, and on **30–46%
under a change of whitespace alone**. Structure adds 7.5 to 19.2 points of divergence beyond the
byte-perturbation floor, consistently and in every model. None of it reaches verified success.

**This is a diagnostic, not a fitness signal, and the distinction is the main scientific content of
this milestone.** A metric rewarding tactic divergence, head divergence, novelty or behavioural
distance would be optimising a quantity with a 30–46% noise floor that this experiment has shown to
be uncorrelated with kernel-verified outcome. Nothing in Hamiltonian Chess may be scored on it.

## 7. Formal gates

| gate | frozen rule | observed | verdict |
|---|---|---|---|
| null control (C1b) | 95% CI ⊂ ±0.05 | [−0.008, +0.022] | **PASS** |
| sensitivity (C2) | `Δ ≤ −T_ablate`, `T_ablate = 0.0665` | −0.0587, p = 5×10⁻⁵ | **FAIL on magnitude** |
| identity (C1) | split `R_A`'s replicates | `k = 1` — nothing to split | **UNAVAILABLE** |
| missingness | per-arm equality | 3 / 3 / 3 / 2 | **FAIL — false block** |
| cluster floor | ≥ 30 clusters | 329 | PASS |

**Formal certification: NOT GRANTED.** `release()` refused, and no threshold was moved to change
that.

**Scientific information: high, and the two failures are of opposite character.** The missingness
failure is a **false block**: 11 environment errors on 3 anchors, and because a pair is dropped when
either arm is unanalysable, all three contrasts ran on identical samples (1,124 anchors / 329
clusters). The exact-equality rule fired on a difference that never reached the analysis. The
sensitivity failure is a **genuine miss of a badly-chosen threshold**: `T_ablate` was fixed at half
the *preflight* baseline of 0.133, the realised baseline was 0.1077, and the ablation cost 0.0587 —
0.8 points short of a bar set from a number that turned out high. The ablation itself is detected
with a CI of [−8.5, −3.4] points at p = 5×10⁻⁵, so **the assay's sensitivity is empirically
established even though the frozen gate does not certify it**. Both statements are true and neither
is allowed to stand in for the other.

## 8. Verdict

**`HC_V0_6_ONE_STEP_TIGHT_NULL`.**

Four eligible models spanning two independent architecture families give
`Δ(R_B − R_A) ∈ [−0.009, +0.011]`, every interval inside ±5 points, no sign agreement, with null
controls at or below +0.7 points and a decisively detected ablation.

This does **not** refute Hamiltonian Chess. It refutes one specific and previously untested
hypothesis: *that an information-preserving change to the surface form of a Lean goal materially
changes the probability that the next machine-proposed tactic is accepted by the kernel.* It does
not, and the effect is small enough that four models agree it is small.

The mechanism is now visible, and it explains the null rather than merely reporting it: the
representation reliably changes **which** tactic the model proposes, on roughly half of all states,
and the tactics it swaps between are close enough in quality that the exchange rate is zero. The
model is not reading the representation better or worse — it is landing somewhere else in a set of
roughly equally good moves.
