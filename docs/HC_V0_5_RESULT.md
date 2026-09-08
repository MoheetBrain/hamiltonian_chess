# HC-V0.5 Result — a real player entered the game

**Sentinel: `HC_V0_5_REAL_PLAYER_EXECUTABLE`.**

**This is an engineering milestone, not a scientific result.** No representation was compared, no
language was ranked, no `RSTAR`/`LSTAR` claim is made. The run stamps itself
`ENGINEERING_SMOKE_NOT_A_RESULT`.

Artifact: `artifacts/trajectory/hc_v0_5_smoke.json`, `result_hash`
`fcfa47f7d116935001b48946add21b121fa02fb62d675ca38a97a2bbb9b4baa8` (wall-clock and latency are
excluded from the hash, per directive §28). Runner: `arena/trajectory/episode.py`.

---

## 1. What changed

Before HC-V0.5, **every action in the project's trajectory bank carried `actor=REFERENCE`**. The
bank replayed mathlib's own proofs; no policy had ever chosen a move. The world existed and the
outer loop existed, but there was no player.

There is now.

## 2. The headline episode

`Mathlib/LinearAlgebra/Prod.lean::LinearEquiv.snd_comp_prodComm` — **four consecutive
Solver-proposed tactics, each accepted by the Lean elaborator, ending in `CLOSED_VERIFIED`:**

| step | Solver action | Lean |
|---|---|---|
| 0 | `simp [LinearMap.snd, LinearMap.fst, prodComm]` | `ACCEPTED_TRANSITION` |
| 1 | `ext` | `ACCEPTED_TRANSITION` |
| 2 | `simp [LinearMap.comp_apply, Prod.snd, Prod.swap, LinearMap.inl]` | `ACCEPTED_TRANSITION` |
| 3 | `simp [LinearMap.comp_apply, LinearMap.inr_apply, Prod.swap, Prod.snd, Prod.fst]` | `ACCEPTED_TRANSITION` → `CLOSED_VERIFIED` |

No reference tactic was consulted, and none could have been: the task holds only a digest of the
reference proof (§5).

A failure arc is equally informative —
`tendsto_iff_dist_tendsto_zero`: `constructor` accepted, `intro h` accepted, then
`apply tendsto_dist` rejected twice → `UNRECOVERABLE_INVALID_ACTION`. The Solver navigated two
real steps into the proof and then could not continue. That is a game being lost, which is a
result the milestone explicitly permits (directive §31).

## 3. The smoke bank — 30 tasks, one fixed baseline interface

| measure | value |
|---|---|
| episodes | 30 |
| **solved (`CLOSED_VERIFIED`)** | **4** |
| **episodes with ≥1 accepted Solver transition** | **9** |
| **accepted Solver transitions** | **16** |
| rejected actions | 47 |
| **parse failures** | **0** |
| environment errors | 3 |
| longest accepted chain in one episode | **4** |
| Solver calls | 60 |
| prompt / completion tokens | 10,866 / 1,012 |
| mean latency | 832 ms |

Tasks were drawn deterministically (`seed=20260908`, `scan_limit=12000`, recorded reference length
1–4) from the LeanDojo **train** split only. **No task was selected on Solver performance** — the
sample was widened from 10 to 30 of the *same* distribution precisely because the first 10 yielded
no accepted transition, and the directive (§31) forbids quietly choosing easier tasks.

The four solved goals: `List.indexOf_cons_self`, `LinearEquiv.snd_comp_prodComm`,
`ContinuousMap.image_coev`, `cmpUsing_eq_lt`.

## 4. Two honest findings from the run

**The Solver proposes real mathematics, and is weak on hard mathlib goals.** Its rejected proposals
are not garbage — `exact h.measurableSet`, `rw [gcd_eq_one_iff_coprime]`, `apply BddAbove.mono h`
— they are the moves a mathematician would try, with the wrong lemma or hypothesis name. Zero
parse failures in 60 calls. The channel works; the mathematics is hard.

**The retry is near-useless, and the reason is worse than expected.** The declared failure policy is
`ONE_DIAGNOSTIC_RETRY` with `max_retries=1`, but **the backend diagnostic never reaches the
Solver** — the prompt reads one allow-listed field, `goals_pp`. So the retry re-asks an identical
question. In the first 10-task bank all ten retries returned the byte-identical tactic, making
every `rejected=2` really one distinct attempt.

It does not always return the same string, and **that is the more serious finding** (§4a).

### 4a. The runtime is not reproducible, and temperature 0 does not make it so

Two runs of the identical 6-task configuration produced **different `result_hash` values**. I
diagnosed it rather than assuming, and the cause is not where it would be convenient:

- Every Lean state, every `pp_sha256`, every kernel receipt and every terminal status was
  **identical** across the two runs. The task layer and the backend are reproducible.
- The divergence is entirely in the Solver's output, and only on **retry** calls.
- The two diverging calls had **identical `prompt_sha256` and identical `prompt_tokens`** (181 and
  181; 152 and 152) and returned **different tactics**.
- Asked the same prompt six times in isolation, the model returned the byte-identical answer six
  times.

So the model is deterministic for a repeated prompt *in isolation*, and **non-deterministic for
the same prompt once other calls have passed through the same server process** — server-side
batching/KV-cache state, not sampling. Temperature 0 and a fixed seed do not remove it.

**Why this matters more than the solve rate.** HC-V0.6 is a paired parent-versus-child language
assay. A paired design assumes that the same task under the same conditions gives the same answer,
so that a difference between arms is attributable to the arm. **That assumption is false on this
runtime today.** Before any language comparison, either the variance must be measured and carried
into the statistics (repeat each arm and treat the runtime as a random effect), or the Solver must
be run in a configuration that is reproducible call-for-call. This is now the first thing HC-V0.6
must settle, ahead of any representation work.

## 5. Why no reference proof could have leaked

Four independent mechanisms, all in `arena/trajectory/task.py`:

1. `seal_reference_proof()` is the only function that touches the text; it retains counts,
   byte-lengths and digests. No plaintext survives.
2. `VerifiedTask.__init__` **raises `ReferenceProofExposureError`** if the probe still carries
   `reference_tactics`.
3. `VerifiedTask` declares `__slots__`, so reference text cannot be attached later.
4. `HashedLeakageGuard` slides each secret's byte-length window over the observation and compares
   digests — it can *recognise* the answer and can never *produce* it.

Asserted two ways: an AST scan over the transitive closure of `VerifiedTask.step`, and a runtime
object-graph walk through `__dict__`, `__slots__`, closures and defaults — each with a negative
control that catches a deliberately peeking task.

## 6. Solver identity

`qwen3.6:27b-mlx`, digest `d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`,
27.8B, `nvfp4`, family `qwen3_5`, context 262144, Ollama 0.33.2, renderer/parser `qwen3.5`.
Prompt template `hc-v0.5-tactic-json-v1` (sha256 `95a4e049…`), output grammar
`{"tactic": "..."}` (sha256 `9b25cba2…`), decoding frozen at temperature 0, seed 20260908.

**Lineage: `UNKNOWN`, and not inferred.** This is **not** the Phase 6/8 Solver. That model
(`qwen38-rvn`, digest `25eb57cb…`) was deleted from this machine and is unrecoverable; no
ancestry, descent or sibling relation is assumed, and the identity record says so explicitly.

**One finding that would have silently voided the whole run.** This model has a `thinking`
capability the previous Solver lacked. With `think` omitted or `true`, its answer is diverted into
a separate `thinking` field and `response` returns **empty** — every proposal would have been
recorded as a parse failure, and the episode would have read as "the model cannot do Lean" when the
plumbing was at fault. `think=False` is now frozen as a recorded wire flag with the measurement
beside it.

## 7. What HC-V0.5 proves, and what it does not

**Proves.** A real policy interacted with a real mathematical state through kernel-verified
transitions. Lean genuinely adjudicates: measured separately, it accepted a **non-reference**
tactic in **10 of 14** probes and in 2 of those an alternative closed a goal mathlib proves
differently (`research/phase9/interactive_probe/`). The environment is a game, not an imitation
harness.

**Does not prove.** Nothing about representations, languages, horizon effects, or capability.
The 4/30 solve rate is one model, one baseline interface, one prompt, 30 tasks — it is a plumbing
measurement. And because mathlib4 is `HISTORICALLY_EXPOSED` transitively, **nothing here separates
a solved goal from a recalled one**; the defensible phrasing is *long-horizon execution under
kernel verification*, never reasoning or discovery.

## 8. Record-integrity blockers closed first

Per directive §3, no stochastic Solver call was made until the four record-integrity defects were
fixed: **RT-03** (relive verified the source proof, not the artifact's own actions), **RT-02**
(theorem splicing passed at load), **RT-13** (a re-rolled `mutation_hash` bought a free extra
draw), **RT-04** (one episode could be both `REFERENCE` and `SOLVER` evidence), **RT-16** (stub
fitness was persistable as a numeric `J_solve`). All are regression-tested; details in the ledger
and in `docs/HC_V0_5_REDTEAM.md`.
