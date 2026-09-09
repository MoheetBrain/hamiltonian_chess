# HC-V0.6 — the frozen assay

**This document is the freeze.** It is written and committed **before any `R_A` / `R_A_PRIME` /
`R_B` outcome exists**, so that no selection rule, threshold or model choice below can have been
made after seeing a result. Governing authority:
`spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` (unchanged, sha256
`f3c04e69…`). Design detail: `docs/HC_V0_6_DESIGN_BRIEF.md`. Analysis:
`docs/HC_V0_6_ANALYSIS_PLAN.md`. Preregistration: `docs/HC_V0_6_PREREGISTRATION.md`.

**Ladder position: manual §25 Gate 1 — a cheap scout.** It MUST NOT crown a language, and nothing
here is a confirmatory result. The source is admitted `TRAIN / DEV / SCOUT` and explicitly **not**
`PROMOTION` or `FINAL` (`spec/world/SOURCE_ADMISSION_leandojo_benchmark_4_random_train.json`).

---

## 1. The question

Does changing the machine-facing representation of the *same real Lean state* causally change
verified Solver behaviour — and does any effect survive across more than one local model?

A positive effect and a negative effect are **both** signals: either shows the representation is
causally active, which is what a fitness landscape requires. Nothing here asks a hand-designed
language to win.

## 2. Evaluation universe — frozen

| | |
|---|---|
| artefact | `artifacts/trajectory/hc_v0_6_anchor_bank.json` |
| content hash | `f13ffee5aae464d6f4717c4f85cd6ec1091eb19d9ca0ab5cd716094a9b583b40` |
| anchors | 1,127 |
| theorems | 393 |
| mathlib files (**the cluster unit**) | 330 |
| re-derivation in independent sessions | 1,127 / 1,127 |
| reference-tactic leakage into solver-visible payload | 0 / 1,127 |
| backend | Lean 4.10.0-rc1, mathlib `29dcec07…`, 5,681 `.olean`, `maxHeartbeats 1000000` |
| source | LeanDojo Benchmark 4, `random/train.json` only; four sealed splits never opened |

The bank is frozen. It will not be rebuilt, extended, filtered or re-sampled for the rest of this
sprint. Anchors are never selected on anything downstream of a Solver outcome.

## 3. Arms — frozen at four, no fifth

| arm | renderer | class | role |
|---|---|---|---|
| `R_A` | Lean's native pretty-printed tactic state | `R_ONLY` | baseline |
| `R_A_PRIME` | whitespace-only perturbation, bijective | `R_ONLY` | **null control**: does merely changing bytes move the outcome? |
| `R_B` | enumerated workspace re-layout, bijective | `R_ONLY` | **the intervention under test** |
| `R_ABLATED` | goal text withheld, goal count retained | `P_CHANGE` | **degraded calibration control** |

`R_A_PRIME` and `R_B` each ship an inverse and satisfy `invert(render(s)) == R_A.render(s)` at
every anchor: no information added, none removed. `R_ABLATED` has no inverse, which is exactly what
disqualifies it as a representation. **`R_ABLATED` is not a candidate language and may never enter
a league or archive.**

## 4. Primary endpoint — frozen

**`KERNEL_ACCEPTED_STATE_CHANGE`** = 1 iff Lean accepts the Solver's **single first action** AND
that action either closes the task or changes the declared backend state. An accepted no-op scores
**0** (`StepResult.ACCEPTED_NO_OP`). `ENVIRONMENT_ERROR` is separately typed and is never a
mathematical zero.

The no-op exclusion is load-bearing rather than fastidious: `skip` is accepted by Lean at every
open goal, so an acceptance-only endpoint is maximised by a policy that never attempts mathematics.
Verified live — a scripted `skip` solver scored 36/36 events under the old endpoint and **0/36**
under this one.

"The state changed" is decided by the project's own declared state identity: normalised goal text
under a fixed elaboration scope (`goal-text-nfc-linewise-rstrip-v0`), the same quantity
`KernelStateIdentity.reelaboration_key` is built from. It never decides whether a proof is correct.

## 5. Runtime contract — frozen

One attempt per anchor per arm. **No retry, no diagnostic feedback, no search, no best-of-N, no
reference action, no retrieval.** `k = 1`.

```
prompt template   hc-v0.5-tactic-json-v1   sha256 95a4e049…
output grammar    json-object-tactic-v1    sha256 9b25cba2…
decoding          num_ctx=32768  num_predict=128  temperature=0.0  seed=20260908
                  top_k=20  top_p=0.95  min_p=0.0  repeat_penalty=1.0  presence_penalty=0.0
wire              raw=false  think=false  stream=false
```

Identical for **every** model. `num_ctx` is pinned rather than scaled per model because it was
measured to change the *policy*, not merely the capacity: 4096 vs 32768 flips one prompt from
`constructor` to `exact Set.eqOn_univ`, 12/12 each way (`docs/HC_V0_6_RUNTIME_NOISE.md`).

`k = 1` is not a compromise. The measured per-call tactic-flip rate is 1.02% and the noise is
**symmetric**, so it cannot bias Δ̂ — only dilute power. Protecting against it costs 15 extra
anchors at `k=1` versus 405 extra calls per arm at `k=3`.

## 6. Execution schedule — frozen

All four arms at one anchor are stepped from the **same live Lean `state_id` in the same session**,
by branching. The arms therefore cannot have seen different mathematics.

Arm order is **randomised within each anchor**, as a pure function of `(seed=20260909, anchor_id)`.
Never all of one arm then all of another. This is not caution: the measured runtime instability is
**state-dependent, not random** — after a model reload, 8/8 calls returned the variant that warm
calls return 1-in-14 — so a blocked order would place drift entirely on one arm, a bias no number
of replicates can remove.

No model is reloaded mid-pass. `num_ctx` is not varied.

## 7. Model selection rules — frozen BEFORE preflight data is read

**Eligibility.** A model is eligible iff, on the baseline `R_A`-only preflight:

* `parse_failure_rate ≤ 0.20` — and only after checking it is not **mis-wired**. HC-V0.5 measured
  that with `think` unset the Solver returned an empty `response` and every proposal became a parse
  failure: the model looked incapable when it was misconfigured. A high parse-failure rate must be
  diagnosed before it is believed.
* `environment_error_rate ≤ 0.10`
* `0.02 ≤ p̂ ≤ 0.90` — not at the floor, not at the ceiling
* `median_call_seconds ≤ 10.0` — the full assay must fit the budget

**Primary model.** Among eligible models, the one maximising

```
information_rate = p̂ (1 − p̂) / median_call_seconds
```

Ties broken by larger parameter count, then by model name ascending. This is a variance-per-second
heuristic — it says which model will produce the most discriminating observations per unit of
compute, and nothing about capability. **Selected on baseline `R_A` data only. The historical
HC-V0.5 solver receives no privilege.**

**Secondary models.** Up to **three**, running `R_A`, `R_A_PRIME`, `R_B` (adding `R_ABLATED` only
if the budget allows): first the highest-information-rate eligible model from each *distinct model
family* other than the primary's, then, if fewer than three, the remaining eligible models by
information rate. If wall clock forces a cut, the cut drops the lowest-information-rate model —
**never** by shrinking the bank, because that would destroy comparability.

### 7a. The rule APPLIED — baseline preflight, 2026-09-09

45 anchors, 15 theorems, 15 clusters, **identical for every model** (`R_A` only, `k=1`, the frozen
runtime contract, run strictly sequentially). Bank hash confirmed `f13ffee5…`; every served digest
matched the inventory; `verify_served()` returned `VERIFIED_AGAINST_LIVE_RUNTIME` for all five.

| model | family | p̂ (events/45) | 95% Wilson | median call | information rate | eligible |
|---|---|---|---|---|---|---|
| `gemma4:e4b` | gemma4 | 0.133 (6) | [0.063, 0.262] | 0.225 s | **0.5136** | yes |
| `gemma4:12b` | gemma4 | 0.156 (7) | [0.077, 0.288] | 0.355 s | 0.3700 | yes |
| `qwen3.6:27b-mlx` | qwen3_5 | 0.400 (18) | [0.270, 0.545] | 0.773 s | 0.3105 | yes |
| `gemma4:31b` | gemma4 | 0.356 (16) | [0.232, 0.502] | 0.975 s | 0.2350 | yes |
| `gemma3:4b` | gemma3 | 0.000 (0) | [0.000, 0.079] | 0.158 s | 0.0000 | **no — floor** |

No model produced a single `PARSE_FAILURE` or `TRANSPORT_FAILURE`, and none was mis-wired: all five
were smoke-tested on the repo's own goals first (5/5 `OK` each, `thinking` empty), which directly
excludes the HC-V0.5 empty-response mode. `gemma3:4b`'s floor is a genuine syntactic/mathematical
failure — 44/45 of its actions reached the kernel and Lean evaluated them — not a wiring fault.

**Primary model, by the §7 rule and nothing else: `gemma4:e4b`.**

This is *not* the historical HC-V0.5 solver, and that is the rule working as intended rather than a
surprise to be argued around. `information_rate` maximises Bernoulli variance per second of
generation: `gemma4:e4b` has the second-lowest event rate but is 3.4× cheaper per call than
`qwen3.6:27b-mlx`, and a lower baseline additionally *shrinks* the paired MDE, since the MDE scales
with `√(p(1−p))`. Two honest caveats recorded now rather than after the outcome: at n=45 the middle
three models are inside the heuristic's own noise, and an 8B model's behaviour may be dominated by
syntactic competence rather than by reading the mathematics, which would make a representation
effect harder to interpret. Neither caveat licenses overriding the frozen rule.

**Secondary models, by the §7 rule:** `gemma4:12b`, `qwen3.6:27b-mlx`, `gemma4:31b` — all three
remaining eligible models, so the primary designation decides only which model's controls gate
interpretation and which gets `R_ABLATED`. `gemma3:4b` is excluded by the pre-declared floor test.

**`T_ablate` for the primary** (§10a, from preflight alone): `p̂_A = 0.133 < 0.20`, so
`T_ablate = 0.5 × 0.133 = 0.067` — the ablation must cost at least **6.7 points**. Whether that
clears the achieved MDE is settled in `docs/HC_V0_6_ANALYSIS_PLAN.md` and reported with the result.

**Realised budget:** primary 1,127 × 4 = 4,508 calls; three secondaries 3 × 1,127 × 3 = 10,143.
Total **14,651**, inside the §12 ceiling of 14,851.

## 8. Statistics — frozen

Cluster unit: **mathlib file** (330). The theorem nests inside the file, so the file is the coarser
and therefore the safe unit. Paired within anchor.

* Δ̂ per contrast, paired by anchor.
* Interval: paired **cluster** bootstrap, resampling files.
* Test: **cluster** permutation, flipping arm labels within anchor by file.
* Marginals: Clopper–Pearson.

A row-level bootstrap is anti-conservative under clustering — measured at ICC 0.5 it rejected a true
null **13.75%** of the time at a nominal 5%, where the clustered test held its level. It is not used.

**`δ_min = 0.05`** — five absolute percentage points on the primary endpoint. Owner-supplied
practical threshold for this development scout. Every null result is reported **beside the minimum
detectable effect actually achieved**; a null without an MDE is not a result.

## 9. Multiplicity — two separate problems, never mixed

**(A) Assay certification gates.** Certification requires *every* required control to pass, so the
global null is "at least one gate is unsafe" and certification means rejecting every component
null. That is an **intersection–union test**, under which separate level-α component tests already
control the false-certification rate; a Holm correction would make each gate *harder* to trip and
would bias the procedure toward "the assay is fine". Governing philosophy: **false block ≫ false
certification.**

**(B) Representation effect claims.** Family-wise control across the contrasts inspected, by Holm,
declared prospectively.

## 10. Control gates — thresholds frozen before any call

| gate | condition | consequence if it fails |
|---|---|---|
| **null control** | `Δ(R_A, R_A′)` inside the equivalence band **±0.05** | attribution of any `R_B` effect to *structure* is **blocked** — the model is sensitive to bytes as such |
| **degraded control** | `Δ(R_A, R_ABLATED) ≤ −T_ablate` (see below) | assay **sensitivity is questionable**; interpretation of `R_B` stops |
| **cluster floor** | ≥ 30 contributing clusters per contrast | contrast not reportable |
| **missingness** | not arm-dependent | run invalid |

### 10a. `T_ablate` — declared before any `R_ABLATED` call

A flat "10 points" threshold is only meaningful if the baseline has 10 points to lose. If the
measured baseline event rate is itself near 0.10, requiring a 10-point drop would require the
ablation to reach exactly zero — a threshold the control is *structurally* incapable of clearing,
which would look like a failed control and actually be a badly chosen number.

So, as a function of the baseline `p̂_A` measured on the **`R_A`-only preflight** — that is,
before any `R_B` or `R_ABLATED` outcome exists anywhere:

```
T_ablate = 0.10                      if  p̂_A ≥ 0.20
T_ablate = 0.5 × p̂_A                 if  p̂_A <  0.20      (half the baseline)
```

and if `T_ablate` falls below the assay's achieved minimum detectable effect, then the degraded
control **cannot be certified at this resolution**. That is reported as such — it contributes to
`INCONCLUSIVE` — and is never resolved by lowering the bar after the fact. The number is fixed by
preflight data alone, which the owner directive explicitly admits for calibration (§8), and cannot
be revisited once an `R_ABLATED` cell exists.

## 11. Signal rule — frozen

**Strong primary signal** iff `|Δ(R_B, R_A)| ≥ 0.05` **and** the frozen interval/test gives credible
evidence against zero **and** both controls pass. Direction is irrelevant to whether it is a signal:
a large negative effect proves representation is causally active just as a positive one does.

**Cross-model classification**, frozen before any secondary-model outcome:

* **`GREEN_SIGNAL`** — the primary model shows a valid effect ≥ 5 points, and at least one
  additional *meaningfully distinct model family* shows a same-direction non-trivial effect with its
  own null control practically small.
* **`AMBER_MODEL_SPECIFIC_SIGNAL`** — the primary shows a real effect, but secondary readers do not
  reproduce it, or only same-family variants do.
* **`NO_H1_SIGNAL_AT_CURRENT_RESOLUTION`** — every eligible model's effect is smaller than the
  practical region with tight enough uncertainty. This does **not** refute the long-horizon thesis;
  it says one-step `R_ONLY` effects are small in this regime.
* **`INCONCLUSIVE`** — power, floor, ceiling, runtime or control problems prevent a decision.

## 12. Call budget — frozen

| pass | arms | anchors | calls |
|---|---|---|---|
| preflight (per model) | 1 | ~40 | ~40 |
| primary | 4 | 1,127 | 4,508 |
| each secondary | 3 | 1,127 | 3,381 |

Ceiling: **preflight + 4,508 + 3 × 3,381 = 14,851 calls** plus preflight. `k = 1` throughout. No
adaptive draws, no extra seeds after an outcome, no repeat of a pass because its result looked
interesting. Exceeding the ceiling requires a new manifest and a new run.

## 13. Invalidation conditions

A run is `RESULT_INVALID`, to be re-run under a new manifest rather than patched, if: a served model
digest does not match the manifest; a reference tactic reaches a rendered prompt; missingness is
arm-dependent; the emitted cells fail structural verification; or any CRITICAL scientific defect is
found after outcomes were seen. **A critical defect discovered after exposure is never silently
fixed and continued.**

## 13a. One measured property of the bank that constrains interpretation

Re-confirming branching on 18 theorems of the frozen bank (36 anchored states, initial and
mid-proof) gave 36/36 distinct children from two successful steps at the same state, with the
parent surviving every time. But at one prefix-8 anchor the theorem's **own next recorded tactic no
longer type-checks** after flat replay, while both neutral branches from that same state succeeded.

That is the proof-tree/flat-script mismatch surfacing inside a *surviving* anchor. It does not touch
the endpoint — a recorded tactic is never played and never scored — but it forbids one tempting
assumption: **at an arbitrary anchor there is no guarantee that "the gold move" is even accepted**,
so no per-anchor ceiling may be inferred from the recorded proof.

## 14. What this design cannot answer

Nothing about horizons — the endpoint is one action deep. Nothing about reasoning or discovery:
mathlib4 is `HISTORICALLY_EXPOSED` and exposure is transitive, so the defensible phrasing stays
**execution under kernel verification**. Nothing about language evolution, and no `RSTAR`/`LSTAR`
claim. `Δ(R_A, R_B)` also mixes structural re-layout with the tokenizer priors of the added markup
vocabulary; `R_A_PRIME` narrows that confound and does not eliminate it.
