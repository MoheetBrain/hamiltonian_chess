# HC-V0.6 — Runtime noise: is there a call-for-call reproducible configuration?

**Verdict: NO. No configuration tested is call-for-call reproducible, including
`FROZEN_DECODING`.** Under the shipped options dict —

```
num_ctx=32768  num_predict=128  temperature=0.0  seed=20260908
top_k=20  top_p=0.95  min_p=0.0  repeat_penalty=1.0  presence_penalty=0.0
                     (wire: raw=false, think=false, stream=false)
```

— **7 of 56** deeply-probed real Lean prompts (12.5%) returned more than one tactic across
repeats, at a pooled per-call tactic-flip rate of **1.02%** (16 minority calls in 1566) and a
raw-byte flip rate of **1.47%** (23 in 1566). Nine further `options` dicts were tested; none
removed it, and none of `seed`, `top_k=1`, `top_p=1.0` or `temperature=0` is the lever. The
runtime is *near*-deterministic — 89.4% of repeated cells are byte-identical — which is a very
different thing from reproducible, and the difference is exactly what a paired assay trips over.

Every number below was measured in this session against digest
`d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`. Exact commands and
environment: `research/phase10/noise/README.md`. Raw per-call rows: `research/phase10/noise/out/`.

---

## 1. Resolving the HC-V0.5 contradiction

`docs/HC_V0_5_HANDOFF.md` §2(a) said the runtime is not reproducible. E1/E2 said it is, perfectly,
under a config that already contained `seed` and `temperature=0`. **Both were partly right, and
the handoff's *diagnosis* was wrong in a way that matters.**

### 1a. The `result_hash` claim is true, and mostly not about the Solver

Four replays of the HC-V0.5 configuration, back to back:

| run | `result_hash` | notes |
| --- | --- | --- |
| A | `6649b2b14c09051f…` | first run after ~55 min idle |
| B | `a35d97d9fa064ea4…` | |
| C | `0c6192067f6cb73f…` | |
| D | `2968ef41d843f2b0…` | |

**Four runs, four distinct hashes** — the handoff's observation reproduces exactly. But a
recursive diff of the *hashed* payload (`arena.trajectory.episode._strip`) shows what is actually
driving it:

* **B vs C: zero step-field differences, different hash.** The whole difference is
  `trajectory/actions[i]/wall_ms` — Lean's own per-action wall clock, 3 ms vs 6 ms — plus
  `verifier_evidence[0]/backend_error`, whose text embeds a per-run temp path
  (`/var/folders/w9/8f0vxk6120x24s…`).
* At the time these four runs were made, `NON_DETERMINISTIC_FIELDS` stripped only
  `{wall_clock_s, latency_ms, generated_utc}` — not `wall_ms`. **So `result_hash` differed on
  every run even where the Solver was perfectly reproducible.** It is not a
  Solver-reproducibility instrument, and it was read as one.
* Exactly **one** genuine Solver difference exists across all six pairwise comparisons:
  A's `episodes[4] step 0` (`QuadraticForm.polar_sub_right`, prompt `1e9c61ec98…`, 161 prompt
  tokens) returned `completion_tokens=16` where B, C and D all returned 12.

**Status of the instrument as of this writing.** `wall_ms` was added to
`NON_DETERMINISTIC_FIELDS` by concurrent work in `arena/trajectory/episode.py` while this study
was running. Re-hashing the same four stored artefacts under the *current* `_strip` gives **four
distinct hashes still**, because one leaf remains: the per-run temp path inside
`episodes[5]/trajectory/verifier_evidence[0]/backend_error` (a Lean startup failure). Under the
fix, B vs C, B vs D and C vs D now differ by that single leaf and nothing else, and A additionally
carries the real `completion_tokens` difference. **`result_hash` is closer to usable but is still
not yet a valid reproducibility detector**; a backend error message containing a temp path has to
be normalised or excluded before it is one.

### 1b. The "identical `prompt_sha256`, different tactic" claim is true

The first differing cell, in full:

```
episode  QuadraticForm.polar_sub_right   step 0
prompt_sha256   1e9c61ec983c8067…   (identical in both)
prompt_tokens   161                 (identical in both)
tactic          "rw [polar_sub]"    (identical in both)
Lean verdict    REJECTED_INVALID_ACTION, "rewrite failed, equality or iff proof expected"
                                    (identical in both)
completion_tokens   A: 16    B: 12  ← the only difference
```

So for *this* cell the divergence is real but cosmetic: E6 shows the two raw responses are
`{"tactic": "rw [polar_sub]"}` (12 tokens) and `{\n  "tactic": "rw [polar_sub]"\n}` (16 tokens).
Same tactic, same verdict, different JSON whitespace under the `format` grammar.

**But the handoff was not describing only that.** Re-reading `hc_v0_5_smoke.json`, five prompts
were answered two ways within that one run, and four of them changed the *tactic*:

| prompt | answer 1 | answer 2 |
| --- | --- | --- |
| `a0db75effc…` | `constructor` (**accepted**) | `exact Set.eqOn_univ` (**rejected**) |
| `797fa83a92…` | `obtain ⟨k, hk⟩ := exists_weightSpace_le_ker …` | `exact ⟨0, by simp […]⟩` |
| `661366c3c3…` | `ext x; simp [Set.mem_Icc, le_refl]` | `ext x; constructor <;> simp […]` |
| `666a41ab34…` | `ext x; simp [EqOn] at h ⊢; exact h x` | `ext x; simp [EqOn] at h; exact h x` |
| `1e9c61ec98…` | `rw [polar_sub]` (12 tok) | `rw [polar_sub]` (16 tok) |

The first row is an outcome flip: one tactic passes the kernel and the other does not.

### 1c. Why E1/E2 saw nothing — a corpus gap, not a fix

E1 (3 prompts × 40) and E2 (probe × 30, solo and interleaved) drew from
`out/fresh_goals.json`, 18 states derived from a live Lean REPL. **None of the five HC-V0.5
divergent prompts is in that corpus.** E1/E2 were correct about the prompts they used and were
generalised to prompts they had never sent.

E6 closes that gap by replaying the recorded prompts themselves, recovered by verified
`prompt_sha256` so every prompt is byte-identical to one the runtime had already answered. The
suspect/control split is read off the recorded run, not chosen by hand.

| prompt | group | ordering | calls | distinct raw | distinct tactics | modal rate | `completion_tokens` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1e9c61ec98` | suspect | solo | 25 | 1 | 1 | 1.00 | [12] |
| `1e9c61ec98` | suspect | interleaved | 25 | 2 | 1 | 0.80 | [12, 16] |
| `661366c3c3` | suspect | solo | 25 | 2 | 2 | 0.96 | [19, 20] |
| `661366c3c3` | suspect | interleaved | 25 | 2 | 2 | 0.92 | [19, 24] |
| `666a41ab34` | suspect | solo | 25 | 2 | 2 | 0.92 | [20, 22] |
| `666a41ab34` | suspect | interleaved | 25 | 2 | 2 | 0.92 | [20, 22] |
| `797fa83a92` | suspect | solo | 25 | 2 | 2 | 0.96 | [25, 28] |
| `797fa83a92` | suspect | interleaved | 25 | 2 | 2 | 0.96 | [25, 28] |
| `a0db75effc` | suspect | solo | 25 | 2 | 2 | 0.96 | [7, 12] |
| `a0db75effc` | suspect | interleaved | 25 | 2 | 2 | 0.88 | [7, 12] |
| 5 controls | control | solo + interleaved | 25 each | 1 | 1 | 1.00 | single value |

**All five suspects reproduced their instability; all five controls stayed byte-identical
50/50.** Instability is a property of the prompt, not of the corpus or the ordering.

### 1d. So which of (a)/(b)/(c) is it?

Not **(b)**: the decoding options and wire flags recorded inside `hc_v0_5_smoke.json` are
byte-identical to today's `FROZEN_DECODING` and `WIRE_FLAGS`, and `prompt_template_sha256` and
`adapter_version` match too. Nothing changed.

It is **(a) and (c) together, with the emphasis in the wrong place**:

* The *phenomenon* — same `prompt_sha256`, same prompt tokens, different tactic — is **real and
  confirmed**, at roughly 1% of calls concentrated in ~1 prompt in 8.
* The *instrument* was wrong. `result_hash` differing between two runs was offered as the
  evidence, and `result_hash` differs between two runs regardless, because it hashes Lean's
  millisecond timings and a temp path. Of the four hashes above, three (B/C/D) have **no** Solver
  difference at all.
* The claim "in isolation the same prompt returns the same answer six times out of six" is
  consistent with everything here and is simply underpowered: at a ~4–12% flip rate, six repeats
  miss it most of the time.

**The handoff overstated how much of the run-to-run difference is Solver noise, and understated
how specifically it is localised.** The corrected statement: *the Solver is non-reproducible on a
minority of prompts at a ~1% per-call rate; `result_hash` is not a valid detector of that and
should not be used as one.*

---

## 2. Which knobs matter (E3)

Ten `options` dicts, 12 interleaved repeats each, on two probes: one known-unstable
(`a0db75effc`) and one known-stable (`05cb1a6a67`). Testing only a stable probe would have made
"deterministic" unfalsifiable, which is the failure this design exists to avoid.

| config | change from frozen | distinct responses (unstable probe / stable probe) |
| --- | --- | --- |
| `frozen_baseline` | — | 1 / 1 |
| `no_seed` | `seed` removed | 1 / 1 |
| `temp0_only` | only `num_ctx`,`num_predict`,`temperature=0` | 1 / 1 |
| `greedy_strict` | `top_k=1, top_p=1.0` | 1 / 1 |
| `greedy_strict_noseed` | `top_k=1, top_p=1.0`, no seed | 1 / 1 |
| `topk1_seeded` | `top_k=1` | 1 / 1 |
| `topp1_seeded` | `top_p=1.0` | 1 / 1 |
| `seeded_hot` | `temperature=1.0`, seed kept | 1 / 1 |
| **`unseeded_hot`** | **`temperature=1.0`, no seed** | **9 / 3** |
| `greedy_strict_ctx4096` | `num_ctx=4096` + strict greedy | 1 / 1 — *but a different answer* |

Four things follow, and only the first is the expected one:

1. **The positive control fires.** `unseeded_hot` produced 9 distinct tactics in 12 calls. The
   harness detects non-determinism when it is present; "deterministic" elsewhere is falsifiable
   and was not vacuous.
2. **`seed` is honoured, and is doing nothing at `temperature=0`.** `seeded_hot`
   (`temperature=1.0` **with** seed) was 12/12 identical while `unseeded_hot` was 9-of-12
   distinct — so the seed genuinely controls sampling. But removing it at `temperature=0`
   (`no_seed`, `temp0_only`, `greedy_strict_noseed`) changed nothing. **`seed` is not what makes
   the greedy configuration nearly deterministic, and it is not what is failing.**
3. **`top_k=1` / `top_p=1.0` do not help.** They are inert at `temperature=0`, as expected, and
   they do not remove the residual flips.
4. **`num_ctx` is load-bearing for the *output*, not just for capacity.** At `num_ctx=4096` the
   unstable probe returned `exact Set.eqOn_univ` 12/12; at `num_ctx=32768`, with every other
   option identical, it returned `constructor` 12/12. Lean **accepted** `constructor` and
   **rejected** `exact Set.eqOn_univ` in HC-V0.5. A context-size change is therefore a change to
   the measured policy, and `num_ctx` must be frozen and reported like any other decoding
   parameter — it currently is, and must not be tuned for throughput.

---

## 3. Context, position and server state (E4, E7)

**Identical-schedule replay (E4a).** One pseudo-random 40-call schedule over 25 distinct prompts,
executed 3 times back to back in one process — 120 calls, satisfying the "100+ call long-running
sequence" requirement.

* round 1 vs round 0: **37/40** positions identical (92.5%)
* round 2 vs round 0: **38/40** (95.0%)
* unanimous across all three rounds: **37/40** (92.5%)

Only 3 positions moved, and they are 2 prompts: `1e9c61ec98` at positions 7 and 31 (whitespace
only) and `5a3f2f76c1` at position 34, where the tactic changed from `simp` to
`simp [List.indexOf]`. **Replaying an identical call history does not reproduce the answers**, so
the divergence is not a deterministic function of the history and no ordering discipline can
remove it.

**Predecessor dependence (E4b).** For each of 6 distinct preceding prompts, the probe was run 4
times. The probe's answer was constant within every predecessor *and identical across all six*
(24 calls). The immediately preceding call is **not** the carrier. At a ~4–12% flip rate, 24 calls
have low power; this is a weak negative, not a clean one.

**Server state (E7).** One suspect (`1e9c61ec98`) and one control (`0520c8df02`) probe.

| arm | suspect: distinct raw | suspect answer | control |
| --- | --- | --- | --- |
| `warm` (14 calls) | 2 | 13× 12-tok compact, 1× 16-tok pretty | stable |
| `cold` (8 calls, eviction confirmed via `/api/ps` before each) | **1** | **8/8 the 16-tok pretty variant** | stable, equals warm |
| `concurrent` (14 calls, 4 client threads) | 2 | 13× compact, 1× pretty | stable |
| `idle` (5 calls, 20 s gaps, model stays loaded) | 1 | 5/5 compact | stable |

**Model (re)load deterministically changes the answer for this prompt.** Eight consecutive
calls each made immediately after a confirmed unload+reload (evict confirmed in 61–90 ms, reload
latency 2810–3610 ms) all returned the variant that warm calls return only 1 time in 14. The
control prompt was unaffected, so the effect is prompt-specific, like the instability itself.

*What this does and does not explain.* It is tempting to attribute run A's lone divergence to a
cold model — A was the first run after ~55 minutes idle. **That attribution is not supported.**
Run A took 27.3 s total and the divergent call was in episode 5 of 6, ~20 s after the load. So
model reload is a *demonstrated* determinant of which variant a prompt lands on, but it is **not
established** as the cause of the specific A-vs-BCD difference. That cause is not identified.

*Concurrency caveat.* The 28 probe windows all overlapped a load call in wall-clock time and probe
latency rose from 444 ms to 1349 ms median, so requests genuinely overlapped. The server's own
batching policy was **not measured**, so this rules out only this load pattern.

---

## 4. The noise model

Pooled over every call made under the exact frozen options (1830 calls in 189 repeated cells;
1566 calls in the 117 cells with ≥8 repeats):

| quantity | value |
| --- | --- |
| repeated cells byte-identical | 169/189 = **89.4%** |
| per-call **tactic** flip rate | 16/1566 = **1.02%** |
| per-call **raw-byte** flip rate | 23/1566 = **1.47%** |
| distinct prompts probed with ≥8 repeats | 56 |
| of those, prompts showing a tactic flip | 7 = **12.5%** |
| within an unstable cell, minority rate | 4% – 20% (1/25 to 3/25 at k=25; 1/10 at k=10) |

Round-robin ordering, the ordering a paired assay actually produces (E5):

* 18 fresh Lean prompts × 10 replicates → **16/18 unanimous** (88.9%), mean Bernoulli variance of
  "modal tactic" 0.010, max 0.09. The two non-unanimous cells (`3bec5a09b6`, `4b04a5c441`) were
  **not** previously known — E1/E2 had used them only as fillers and never checked them.
* 39 recorded prompts × 8 replicates → **39/39 unanimous**, variance 0.000 — *even though that
  corpus contains all five known-unstable prompts.* This is the clearest statement of how easily
  this noise hides: at k=8 a clean sweep is an unremarkable outcome for a corpus known to be
  dirty.

**The model.** The Solver is a *nearly* deterministic function of (prompt, options, server state).
For ~87% of prompts it is exactly deterministic. For ~13% there are two competing continuations
whose logits are close enough that small numeric differences in the serving path flip the argmax;
which one wins is stable within a server state (E7 cold: 8/8) and changes with server state.
About a third of the flips are cosmetic (JSON whitespace, same tactic); the rest change the tactic
and can change the Lean verdict.

**The unstable fraction is a lower bound.** A prompt flipping with probability *q* is missed after
*k* repeats with probability (1−*q*)ᵏ; at *q*=0.05, *k*=10 misses it 60% of the time. 12.5% is
what was *detected* at these depths, not what exists.

---

## 5. Replicates: what `k` is for, and what it cannot absorb

The Solver is **not** deterministic, so the degenerate case in the brief ("with a deterministic
Solver the only remaining within-cell variation is none at all") does **not** apply. Replicates
carry real information here. But they buy much less than they cost.

Exact two-sided McNemar power, α = 0.05, power 0.80, δ_min = 0.10, computed exactly (not
simulated) in `analyze.py`; anchors *n* shown at three plausible true discordance rates ψ.

| | per-cell error after majority vote | spurious discordance added | *n* at ψ=0.15 | ψ=0.25 | ψ=0.35 | Solver calls per arm (ψ=0.25) |
| --- | --- | --- | --- | --- | --- | --- |
| noise-free ideal | 0 | 0 | 125 | 210 | 290 | 210 |
| **k = 1** | 0.0102 | 0.0202 | 145 | **225** | 305 | **225** |
| k = 3 | 0.00031 | 0.00062 | 125 | 210 | 290 | 630 |
| k = 5 | 0.000011 | 0.000021 | 125 | 210 | 290 | 1050 |

**Required k = 1.** Reasoning, stated so it can be attacked:

* The measured noise is **symmetric** — nothing makes a flip favour R_A or R_B — so it cannot bias
  δ̂. It enters only as spurious discordant pairs that split 50/50, diluting power.
* At k=1 that dilution costs **15 extra anchors** (225 vs 210 at ψ=0.25). Buying those 15 anchors
  costs 15 extra Solver calls per arm. Buying the same protection with k=3 costs **405** extra
  calls per arm and returns the anchor count only to 210. **k=3 is a 2.8× worse use of the same
  budget.**
* So: run **k = 1**, and spend the call budget on anchors. If a replicate budget is wanted anyway,
  k=3 with a majority vote on the parsed tactic drives the per-cell error to 0.03%; it is
  defensible, not efficient, and should be preregistered as such rather than reached for after
  seeing a result.

**What k cannot absorb — the thing that would actually invalidate the design.** Every mechanism
found here is *state-dependent*, not random: model load state changes the answer deterministically
(E7: 8/8), and `num_ctx` changes it deterministically (E3: 12/12 each way). If R_A and R_B are
evaluated in separate passes — all of A, then all of B — any drift in server state between the
passes lands entirely on one arm. **That is a bias, and no value of k removes it.** Replication
averages within a cell; it cannot undo a systematic difference between arms.

The design requirement that follows is an ordering constraint, not a replicate count:

1. **Interleave the arms at the anchor level.** For each anchor emit R_A and R_B adjacently, so
   any state drift hits both arms within milliseconds of each other.
2. **Randomise which arm goes first**, per anchor, under a recorded seed — E6 shows position
   within a local sequence matters (`1e9c61ec98` was 25/25 stable solo and 20/25 interleaved).
3. **Do not evict or reload the model mid-assay**, and record `/api/ps` load state on every call
   so a reload is detectable after the fact rather than assumed absent.
4. **Freeze `num_ctx` with the other decoding parameters** and report it. It is not a throughput
   knob; changing it changes the policy.
5. **Do not use `result_hash` as a reproducibility check until it stops hashing environment
   text.** `wall_ms` has since been excluded (concurrent work in `arena/trajectory/episode.py`),
   which removes most of the spurious variation, but re-hashing the four stored artefacts under
   the current `_strip` still yields four distinct hashes: a Lean startup error message carrying a
   per-run temp path survives into the hash. One more normalisation is needed. Until then, compare
   runs the way §1 does — field-by-field over `steps[]` — rather than by hash.

---

## 6. Cost

| experiment | calls | s/call (median) | s/call (mean) |
| --- | --- | --- | --- |
| e1 back-to-back | 120 | 0.519 | 0.549 |
| e2 interleave | 90 | 0.366 | 0.527 |
| e3 knobs | 480 | 0.417 | 0.447 |
| e4 context/position | 168 | 0.656 | 0.717 |
| e5 cell variance (both corpora) | 492 | 0.803 | 0.883 |
| e6 divergent replay | 750 | 0.672 | 0.730 |
| e7 server state | 166 | 1.375 | 1.627 |
| **all** | **2266** | **0.644** | **0.750** |

Plus 52 Solver calls inside the four episode replays (~27 s per 6-task episode run, Lean
included). 1700.6 s spent inside `/api/generate`; **29 min 06 s** total active wall clock,
2026-09-08 22:30:17Z → 23:04:26Z.

At 0.75 s per call, a k=1 assay of 225 anchors × 2 arms ≈ 450 Solver calls ≈ **5.6 minutes** of
generation. Lean verification, not the Solver, is the cost driver for HC-V0.6.

---

## 7. What was not measured

* **No Lean verdicts in E1–E7.** The endpoint throughout is response stability. The claim "a flip
  can change the verdict" rests on the HC-V0.5 record for `a0db75effc` (`constructor` accepted,
  `exact Set.eqOn_univ` rejected) and on E3's `num_ctx` result, not on a fresh paired Lean run.
  **The rate at which a tactic flip changes a Lean verdict is not measured.**
* **The cause of run A's divergence is not identified** (see §3).
* **Server-side batching policy was not measured**; the concurrency arm rules out one load
  pattern only.
* **Lean was running in another agent's process** during part of this window; its effect on these
  numbers was not measured.
* **No between-machine or between-runtime-version replication.** Everything is one host, ollama
  0.33.2, one digest.
* The 12.5% unstable-prompt fraction is a detection-limited **lower bound**, not an estimate of
  the true fraction.
