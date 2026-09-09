# HC-V0.6 — Anchored paired Δ(R_A, R_B): the design brief

**Status: DESIGN, not a result.** This file is the single shared specification every HC-V0.6
work item is built against. It is written before any data exists, so that no design choice can be
made after seeing an outcome.

Governing authority: `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`
(sha256 `f3c04e69…`, unchanged). Predecessor: `docs/HC_V0_5_HANDOFF.md`,
`docs/HC_V0_5_REDTEAM.md`.

---

## 0. The owner's ordered pipeline

```
HC-V0.5 REAL PLAYER (done)
  → close autonomy/provenance defects
  → characterise runtime noise
  → ANCHORED REAL LEAN STATES
  → same state → R_A → Qwen → Lean  |  same state → R_B → Qwen → Lean
  → paired verified outcomes
  → controls prove sensitivity
  → FIRST REAL Δ(R_A,R_B)
  → STOP + inspect
```

Each arrow is a gate. A later stage MUST NOT be run on the strength of an earlier stage that did
not pass.

---

## 1. The unit of observation is an ANCHORED STATE, not an episode

An **anchored state** is a real `BackendStateEnvelope` reached by replaying a prefix of a recorded
mathlib proof inside a live Lean REPL session, at which goals are still open.

It is *anchored* in the sense that it is **re-derivable**: the recipe
`(theorem_full_name, prefix_tactics, toolchain, mathlib commit)` reaches a state with the same
`KernelStateIdentity.reelaboration_key` on every fresh session. The live `sid` is not the anchor;
the recipe plus the re-elaboration key is.

**Why the anchor and not the episode.** An episode confounds the representation with the horizon,
with error recovery, and with the path the policy happened to take. At a single anchored state
everything except the rendering is literally the same object: the same truth state, the same legal
action space, the same verifier, the same budget. This is the only design under which
`InterventionClass.R_ONLY` (manual §26.2) is defensible at V0.

**The bank builder reads the reference proof; the assay does not.** Building an anchor replays
recorded tactics — that is oracle-side work, `actor=REFERENCE`, exactly like `ReplayDriver`. The
Solver is shown the resulting *goal state* and never the prefix that produced it. This separation
must be visible in the code and in the artefact, not only in prose.

**Branching, not restarting.** `LeanReplSession.step(state_id, tactic)` applies a tactic to *any*
state the session has produced. One session per theorem therefore serves every arm and every
replicate at every anchor in that theorem: derive once, branch many times. Do not open one session
per cell.

---

## 2. Representations: bijective re-encoding is the R_ONLY contract

Slot-level declaration alone is too weak (`V05-14`/`V05-15`: a renderer can declare less than it
shows). HC-V0.6 therefore uses a stronger, mechanically checkable contract.

**Every `R_ONLY` renderer in this experiment MUST be a bijective re-encoding of the baseline
rendering.** Concretely, a renderer `R` ships:

* `render(envelope) -> Mapping` — the bytes the Solver sees;
* `invert(rendered) -> Mapping` — recovers the **baseline** rendering exactly.

and the bank-wide test `invert(R.render(s)) == R_A.render(s)` must pass for **every** state in the
anchored bank. A bijection cannot add information (nothing to add it from) and cannot remove
information (it could not be inverted). That is what `R_ONLY` means, checked rather than asserted.

Renderers must additionally be **declaration-derived**: `render` is a pure function of
`declare_information(envelope)`, so the existing `InformationDeclaringRenderer` /
`check_projection_parity` machinery in `arena/trajectory/state_identity.py` reports parity from a
declaration the rendering could not have exceeded.

### The three renderers

| id | class | what |
|---|---|---|
| `R_A` | `R_ONLY` baseline | Lean's native pretty-printed tactic state, as today's `BackendNativeRenderer` shows it |
| `R_B` | `R_ONLY` variant | the same characters re-laid-out: hypotheses as an explicitly enumerated block, the goal under its own heading. An interface/serialization (`I`) gene, per manual §10.9 |
| `R_ABLATED` | **`P_CHANGE`** | goal text withheld; goal *count* and metadata retained |

`R_ABLATED` is **not** a representation and must never be reported as one. It exists solely as the
positive control of §4. The `InterventionClass` machinery must label it `P_CHANGE` on its own,
from its genes — if it has to be labelled by hand, that is a defect.

---

## 3. The measurement

One **cell** is `(anchor s, renderer R, replicate j)`:

1. re-derive `s` (or branch to it in the open session);
2. `R.render(s)` → prompt → the Solver (`qwen3.6:27b-mlx`, `think=False`, frozen decode params);
3. parse a tactic from the response;
4. `session.step(s.state_id, tactic)` — Lean decides;
5. record the `ActionResult`, whether all goals closed, tokens, latency, `prompt_sha256`.

**Primary endpoint:** `p_accept(R)` = P(Lean accepts the proposed tactic at an anchored state).
Binary, kernel-decided, paired by anchor.

**Secondary:** `p_close` (the single action closed every goal); parse-failure rate; token counts.

**Effect:** `Δ(R_A,R_B) = p_accept(R_B) − p_accept(R_A)`, paired within anchor, clustered by
theorem (manual §30.6).

The endpoint is deliberately **one action deep**. Horizon claims are out of scope; HC-V0.5 already
established that a per-step edge does not imply a horizon effect.

---

## 4. Controls prove sensitivity — this is not optional

A Δ near zero is uninterpretable unless the assay is shown to be able to detect a difference at
all, and a Δ away from zero is uninterpretable unless the null arm is shown to sit at zero.

* **C1 — identity/null control.** `R_A` against `R_A`, two independent draws. Expected Δ ≈ 0. This
  is the runtime-noise floor. If C1 is "significant" under the preregistered test, **the assay is
  broken and no other comparison may be reported.**
* **C2 — positive control (sensitivity floor).** `R_ABLATED` against `R_A`. Expected Δ strongly
  negative. If the assay cannot detect the removal of the goal text, it cannot detect anything, and
  a null `Δ(R_A,R_B)` is **uninformative rather than evidence of no effect.** Report the detectable
  effect size the control establishes.
* **C3 — permutation null.** Arm labels permuted within anchor; the empirical null for Δ.

Report all three beside the headline number, always.

---

## 5. Runtime noise comes first

HC-V0.5 measured that two identical runs give different `result_hash`, with identical
`prompt_sha256` and identical prompt token counts, while the same prompt in isolation is
deterministic six times out of six. A paired design assumes exactly the reproducibility this
runtime lacks.

Before the bank is played, answer with data:

1. Is `prompt → response` deterministic when repeated back-to-back in one server process?
2. Does interleaving other prompts change the answer to a fixed prompt? (the observed divergence)
3. Does `options.seed` / `temperature=0` / `top_k=1` restore determinism?
4. What is the within-cell acceptance variance? (this sets the replicate count `k`)
5. Does the divergence rate depend on prompt length or on position in the run?

**Outcome required:** either a call-for-call reproducible configuration, or a measured noise model
plus the number of replicates it forces. `k` is chosen from this measurement and from the power
analysis, and is frozen before the assay runs.

---

## 6. Statistics (manual §30.3)

The preregistration must state, before any assay data exists:

```
primary endpoint            p_accept(R_B) - p_accept(R_A), paired by anchor
minimum practical effect    delta_min  (justified, not conventional)
sample size / precision     n anchors, k replicates, from the power analysis
paired method               exact McNemar on discordant pairs + paired cluster bootstrap CI
multiplicity policy         effect claims: Holm across the FOUR of §9.6
                            {R_B vs R_A, C1, C1b, C2}; certification gates: intersection-union,
                            separate uncorrected level-alpha components (see HC_V0_6_SPEC.md §9)
cluster / grouping unit     theorem file (theorems in one mathlib file are not independent)
stopping rule               fixed n; no interim looks; no extension after seeing the result
allowed outcomes            the exhaustive list, each with what it licenses and forbids
evaluation-universe hash    the anchored bank's content hash
```

Store raw per-cell outcomes, not only means (§30.7).

---

## 7. Hard prohibitions for this milestone

* No HC-V0.7, no Pilot 1, no multi-generation evolution, no fine-tuning, no RL Architect.
* No `RSTAR`/`LSTAR` claim. No "searchable landscape" claim.
* The four sealed splits stay sealed. TRAIN only:
  `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json`
* mathlib4 is `HISTORICALLY_EXPOSED` and exposure is transitive. Nothing here separates a solved
  goal from a recalled one. The defensible phrasing stays **execution under kernel verification**.
* No design choice may be made after seeing an outcome. Preregister, then run, then report.
* Do not select anchors on anything downstream of Solver performance.

---

## 8. Environment (verified 2026-09-08)

```
worktree   .../.claude/worktrees/hamiltonian-phase-8-experiment-691d22
python     .venv/bin/python   (uv sync --all-extras; there is no `python` on PATH)
mathlib    /Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/
           leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4
train      /Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/
           leandojo_benchmark_4/random/train.json
solver     ollama qwen3.6:27b-mlx  digest d49fd9e0da45…  27.8B nvfp4  ctx 262144  lineage UNKNOWN
gates      .venv/bin/python -m pytest      (baseline: 1483 passed, 1 skipped)
           .venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
           .venv/bin/python -m mypy arena
```

---

## 9. Addenda settled during build (2026-09-08)

**9.1 Arm order is randomised within each anchor, and the seed is recorded.** HC-V0.5 observed that
a fixed prompt's answer can change once other calls have passed through the same server process.
If the arms were always played in the order `R_A, R_B, R_ABLATED`, any such position effect would
be confounded with the arm. Randomising the order within each anchor converts that confound into
noise that the paired design already absorbs. The permutation is a pure function of a recorded
seed and the anchor id.

**9.2 The identity control C1 is free, and is constructed inside `R_A`.** With `k ≥ 2` replicates
per arm, `R_A`'s own replicates are two independent draws of the same renderer at the same state.
C1 is the paired comparison of one half of `R_A`'s replicates against the other, using the identical
estimator, cluster unit and test as the headline comparison. It therefore measures the assay's noise
floor under exactly the analysis that will be applied to `Δ(R_A,R_B)` — which is the only way a
noise floor is informative.

**9.3 The truth state is shared by construction, not by re-derivation.** All arms at one anchor are
stepped from the *same* live `state_id` in the *same* session, by branching. There is therefore no
possibility that the arms saw different mathematics, and this does not depend on the re-derivability
rate measured for the bank (which remains the property that makes the bank re-runnable later).

**9.4 A fourth arm: `R_A_PRIME`, the byte-perturbation control.** `R_ABLATED` is a very large
effect (the goal text is gone). If the assay detects it, that proves the rendering pipeline is
causally connected to the outcome at all — necessary, but it does not establish sensitivity at the
scale a representation change plausibly operates. `R_A_PRIME` fills the gap: an `R_ONLY`,
bijective, *semantically null* perturbation of the baseline bytes (whitespace only). It sits
between C1 (byte-identical) and `R_B` (restructured). The reading it enables is the one that
matters:

* `Δ(R_A, R_A′) ≈ 0` and `Δ(R_A, R_B) ≠ 0` → the effect is attributable to **structure**, not to
  the mere fact that bytes changed;
* both non-zero → the model is sensitive to byte perturbation as such, and `R_B`'s effect cannot be
  attributed to its structure. That is a finding about the assay, and it would block a
  representation claim.

Four arms: `R_A`, `R_A_PRIME`, `R_B`, `R_ABLATED`. Holm's family widens to four comparisons.

**9.5 Report the minimum detectable effect, not only the controls.** `R_ABLATED` establishing
detectability of a 40-point drop says nothing about a 5-point one. Every null must be reported
beside the MDE actually achieved at the realised `n` and `k`: "we could detect ≥ X points; we
observed Δ = … (CI …)". A null without an MDE is not a result.

**9.6 Resolution of an inconsistency this brief created.** §9.4 was added after some HC-V0.6 code
had already been written against an earlier reading in which `R_A_PRIME` meant "the baseline
renderer drawn a second time". It does **not** mean that. The authoritative definitions:

| arm | renderer | class | role |
|---|---|---|---|
| `R_A` | baseline | `R_ONLY` | reference arm |
| `R_A_PRIME` | **whitespace-perturbed baseline**, bijective | `R_ONLY` | **C1b**, the byte-perturbation null |
| `R_B` | re-laid-out, bijective | `R_ONLY` | **primary** comparison |
| `R_ABLATED` | goal text withheld | `P_CHANGE` | **C2**, the sensitivity control |

`Arm.R_A_PRIME.renderer_id` is therefore `"R_A_PRIME"`, not `"R_A"`.

**C1**, the identity control and noise floor, is not an arm. It is computed by splitting `R_A`'s
own replicates in half (§9.2). If the Solver proves call-for-call deterministic, C1 is exactly zero
by construction, `k = 1` is correct, and that fact must be *reported* rather than assumed — a noise
floor of zero is a measurement, and it is the one that makes the paired design sound.

The comparison family for Holm is therefore four: `{R_B vs R_A (primary), C1b, C2, C1}`.
