# Phase 6 Preregistration — Frozen V5, Substituted Solver

> **AMENDED BEFORE ANY EXPERIMENTAL CALL.** A pre-run audit found a genuine comparability
> defect in the prompt path (see "BUG_FOUND" below). The design was corrected and re-registered
> *before* the run, rather than repaired silently. The smoke test (2 probes) is the only model
> contact that preceded this amendment.

Written and committed **before** any Phase-6 experimental call. Ten read-only subagents
audited the design; all writes are the integrator's.

## SELECTED_SOLVER

`qwen38-rvn:latest`, digest `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`,
family `qwen35`, 27.3B, Q4_K_M, capabilities `["completion"]`, template `{{ .Prompt }}`.

## CURRENT_SOLVER

`gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`,
family `gemma4`, 11.9B, Q4_K_M, template `{{ .Prompt }}`.

## WHY_THIS_SOLVER

Four candidates were measured. `qwen38-rvn` is chosen on four verified properties:

1. **Materially different family.** `qwen35` versus `gemma4`. Scale-only substitution
   (`gemma4:31b`) would leave "a different family might still work" untested.
2. **Prompt treatment can be equalised.** Under the corrected `bare` condition (see BUG_FOUND)
   both models receive exactly the bytes `build_prompt` constructs, and this model's default and
   raw token counts are already identical, so equalisation costs it nothing.
   `qwen36-huihui` was rejected here instead: it carries a 7,764-character chat template, so any
   difference it showed could be "the prompt was finally in the model's turn format" rather than
   reasoning.
3. **No thinking-mode hazard.** Its capabilities are `["completion"]` only. This matters
   because `num_predict=64` counts thinking tokens, and V5 scores an unparsed row as *wrong*
   rather than voiding it. A thinking model would therefore produce a protocol failure
   disguised as a task-family result. Both gemma models declare `thinking`; this one does not.
4. **Quantisation matched** at Q4_K_M, unlike `qwen36-huihui` (Q6_K).

Prior cross-programme evidence also identifies this exact model as the most *sensitive*
reader tested: on a structural re-rendering of identical content it moved 0.3047 → 0.8750
(+0.5703) where `gemma4:31b` moved −0.0547. Sensitivity, not accuracy, is what this
experiment needs.

**Declared confounds:** it is a fine-tuned checkpoint ("rvn"), not stock, and it is 27.3B
versus 11.9B, so family and scale move together. A *positive* result (collapse escaped) is
therefore clean evidence that some solver can expose the mechanisms; a *null* result is
weaker, because the fine-tune is an alternative explanation. `gemma4:31b` is the designated
follow-up if the outcome is ambiguous.

## BUG_FOUND — the prompt path is not solver-neutral

**The defect.** Ollama's `/api/generate` applies a model's built-in `RENDERER` when its
Modelfile declares one. `gemma4:12b` declares `RENDERER`/`PARSER`; `qwen38-rvn` declares
neither. Measured: for an identical prompt gemma reports 12 more prompt tokens than the same
call with `raw:true`, while qwen's default and raw counts are identical. On one probe gemma
answered `A` framed and `B` bare. `ollama show --template` returns `{{ .Prompt }}` for **both**
models, so the template string is not a valid discriminator and my first version of
`verify_served_model` was blind to this.

**Why it matters.** Phase 5 ran gemma *with* chat framing. Running qwen without it would mean
the two solvers receive different inputs, so a difference could be framing rather than solver.
That is a semantic difference, not transport, and it would have invalidated the headline claim.

**Affected files.** `arena/experiments/fitness_v5.py` (`_call_ollama`), and by inheritance
every V5 row. Not the probes, gates or scoring.

**Does Phase 5 remain valid?** **Yes.** Every Phase-5 comparison is within one solver under one
framing; all eight representations were treated identically. Game-R comparability inside
Phase 5 is untouched, and its artifact and sentinel stand unchanged.

**Magnitude, measured before deciding.** On the three cells where solver A reached answer share
1.000, framed and bare answers agree **67/72 = 0.931**, and bare still collapses (67 of 72 on
one option versus 72 of 72 framed). So framing perturbs ~7% of answers but does **not** explain
the collapse.

**Correction, registered here.** Phase 6 runs **both** solvers with `raw: true`, delivering
exactly the bytes `build_prompt` constructs. This changes the runtime, therefore the runtime
hash, therefore the cache namespace — Phase-5 rows are preserved untouched and never mixed in.
Phase 6 therefore compares **bare versus bare**, and Phase 5's framed gemma numbers are
reported separately as a third condition rather than as the baseline.

**Consequence for cost.** Both solvers must be run: gemma bare (392 calls, ~0.9 h) and qwen
bare (392 calls, ~2.2 h).

## FROZEN_COMPONENTS

Everything in `docs/FITNESS_V5_SPEC.md` §2–§5 and the DEV pool hash
`f804e0d998f1cfac20559728cae29733602990ed801430c1398db798b84a9c8b`: probe construction and
salts, the three mechanisms and their family builders, the four-level ladder, explicit-positive
/ counterfactual / destroyed / swap arms, prompt template, answer options, `RESPONSE_SCHEMA`,
`RUNTIME_CONFIG` (and therefore `RUNTIME_CONFIG_HASH`), context guard, scoring, failure
taxonomy, `QUALIFICATION_RULE`, frontier selection, and the abort clause.

## ALLOWED_ADAPTER_CHANGES

Transport-level only, all verified not to alter any prompt byte or any gate:

- a `bare` condition (`raw: true`) applied identically to both solvers, with its own runtime
  hash and cache namespace, to remove the renderer asymmetry above;
- a `SOLVERS` registry and a `solver` parameter threaded through `_call_ollama`,
  `_cached_call`, `evaluate`, `_q0`, `run_development`, defaulting to the Phase-5 solver;
- `identity["model_digest"]` now reads `solver["digest"]` instead of the imported constant;
- a separate artifact path per non-default solver, so Phase 5's `result.json` cannot be
  overwritten;
- `verify_served_model`, which refuses to run unless the live digest matches the recorded one.
  Its `template_is_passthrough` field is reported but is **not** a valid neutrality test, since
  `/api/show` returns `{{ .Prompt }}` even for a model that carries a renderer; the authoritative
  discriminator is the default-versus-raw prompt-token delta, measured above.

**Why the digest change is mandatory.** The cache key contained the model *digest* while the
call used the model *name*, and nothing linked them. Editing the name alone would have made
every Phase-6 identity collide with an existing Phase-5 file: the run would finish in seconds
at 100% cache hits and report gemma's answers as the new solver's. Verified: default-solver
identities still hash to existing Phase-5 filenames, so Phase 5 is preserved.

## DECODING_CONFIGURATION

Unchanged and frozen: `num_ctx` 32768, `temperature` 0.0, `seed` 20260905, `num_predict` 64,
`top_k` 64, `top_p` 0.95, `think` false, `format` = the JSON schema. Verified that these
override the alternate model's Modelfile defaults (`num_ctx` 16384, `temperature` 0.7).
Worst-case prompt is 32,334 characters ≈ 6,700 tokens for this tokenizer, far below both the
32,448-token limit and the model's own 16,384 default, so input truncation is unreachable.

No search over decoding settings will be performed.

## EXPECTED_CALL_COUNT

392 per solver per condition (8 Q0 + 288 ladder positives + 96 full-family rows), matching
Phase 5's structure exactly. Phase 6 runs two: gemma bare (~0.9 h) and qwen bare (~2.2 h),
784 calls total, plus the 72 framing-diagnostic calls already spent. Budget: 900 DEV calls per
condition.

## PRIMARY ENDPOINT AND DECISION_RULE

Two Phase-5 measurements that my own Phase-5 prose over-claimed must be corrected first, and
they shape the analysis:

- **The negative control is a mathematical constant.** Destroyed twins are information-
  identical with opposite targets, so any deterministic solver scores exactly 0.5000 (verified:
  24/24 twin pairs identical, 24/48 correct). The gap gate therefore reduces to
  `positive_accuracy ≥ 0.70`, while frontier selection targets 0.625 — so the selector prefers
  levels that cannot qualify. Effective window is [0.70, 0.85], not [0.35, 0.85].
- **"Constant-position collapse" was not established.** At the only cell where swap arms ran
  (`precondition_conjunction` L1) the Solver picked the same *content* under option reversal
  19/24 = 0.792 and the same *position* only 5/24 = 0.208. It is content-locked, not
  position-locked. The cells with answer share 1.000 never had swap arms run at all.

Accordingly:

- **Primary (confirmatory):** paired exact McNemar on the *degeneracy indicator* — whether the
  solver's answer equals solver A's modal answer — pooled over the three cells where solver A
  reached answer share 1.000 (`precondition_conjunction` L2 and L3, `transitive_dependency` L3),
  n = 72. Reject at p ≤ 0.05, two-sided, no multiplicity correction (single prespecified test).
- **Secondary (Holm across 3):** per-mechanism ladder accuracy pooled over levels, n = 96 each.
- **Descriptive only, no p-values:** the 12-cell accuracy grid, per-cell answer entropy and
  share, per-variant accuracy, qualification verdicts, cause taxonomy, token and latency counts.
- **Comparisons are made at FIXED levels**, never at each solver's own selected frontier, since
  frontier selection on a statistic with SE ≈ 0.10 could otherwise compare different tasks.

Per-cell accuracy at n = 24 is formally underpowered: 0.500 → 0.708 cannot reach two-sided
p ≤ 0.05 (floor 0.0625). No per-cell significance claim will be made, and no equivalence claim
will be made at cell level (the achievable interval is ±0.38 against a ±0.125 region).

## DIAGNOSTIC ADDENDUM (declared in advance)

The three collapsed cells never had swap arms evaluated, so "position-locked" versus
"content-locked but wrong" is currently undecidable. For **both** solvers I will evaluate the
already-existing swap variants of those three cells: 3 cells × 12 families × 2 swap variants =
72 calls per solver. This evaluates more of the existing frozen probe pool; it changes no
probe, prompt, gate or score.

## INVALIDATION_RULE

Phase 6 is `PHASE6_INVALID` if any holds: cache hits > 0 for the alternate solver; the served
digest does not match; the template hashes differ between solvers; any row records
`INPUT_CONTEXT_TRUNCATION`; `OUTPUT_TRUNCATION` exceeds 5% of rows for either solver; or Q0
falls below 0.95.

## STOPPING_RULE

One alternate solver, then stop and classify as `SOLVER_SPECIFIC_FAILURE_SUPPORTED`,
`SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET`, `FAILURE_REPLICATES_ACROSS_SOLVERS`, or
`PHASE6_INVALID`. A third solver is only *recommended*, never launched automatically. The
founder tournament runs only if `founder_tournament_authorized` is true under the unmodified
frozen gate. No threshold will be reinterpreted, and `RSTAR_NOT_IDENTIFIED` stands unless the
existing protocol genuinely establishes otherwise.
