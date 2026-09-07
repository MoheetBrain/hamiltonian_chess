# Phase 6 Result — Frozen V5, Substituted Solver

**Status: `SOLVER_SPECIFIC_FAILURE_SUPPORTED`**

The Phase-5 failure was the Solver, not the task family. A materially different solver escapes
the degeneracy completely (p = 2.9e-11), qualifies the first mechanism in the programme's
history, and inverts the instrument's failure mode from floor to ceiling.

Preregistration: `docs/PHASE6_PREREGISTRATION.md`, committed before any experimental call.

## 1. Scientific question and competing hypotheses

Phase 5 returned 0 of 3 mechanisms qualified with 2 of 3 explicit-positive arms passing, and
fired an abort clause naming two candidates:

- **H_S** — this Solver cannot expose the Game-R mechanisms.
- **H_T** — this task family generates no measurable Game-R structure.

H_I (the instrument is malformed) had already been weakened by Phase 5, which repaired the
response protocol and still returned zero qualifying mechanisms.

**Result: H_S is supported. H_T is refuted for two of three mechanisms.**

## 2. Conditions

Three, not two. The prompt path is not solver-neutral (see §3), so the comparison is reported
under both framings.

| Condition | Solver | Prompt | Artifact sha256 |
|---|---|---|---|
| gemma-framed | `gemma4:12b` 11.9B Q4_K_M | model renderer applied (Phase 5) | `0c5b3271…0097579` |
| gemma-bare | `gemma4:12b` | verbatim instrument bytes | `6deead58…2838418` |
| qwen-bare | `qwen38-rvn` 27.3B Q4_K_M, family `qwen35` | verbatim (its native handling) | `e753de98…8be4916a` |

For qwen, bare and framed are byte-identical (measured default-vs-raw token delta = 0), so one
run covers both. Frozen throughout: probes (DEV pool hash `f804e0d9…`), mechanisms, ladder,
arms, prompt template, `RESPONSE_SCHEMA`, sampling, gates, scoring, abort clause.

## 3. BUG_FOUND — the prompt path was not solver-neutral

Ollama's `/api/generate` applies a model's built-in `RENDERER` when its Modelfile declares one.
`gemma4:12b` declares one; `qwen38-rvn` does not. Gemma gains 12 framing tokens and, on a test
probe, **changed its answer** (A framed, B bare). `ollama show --template` returns
`{{ .Prompt }}` for both, so the template string is not a valid neutrality test; the
authoritative check is the default-versus-`raw:true` prompt-token delta.

This was found before the run, declared, and corrected by running both solvers bare rather than
repaired silently. **Phase 5 remains valid**: all its comparisons were within one solver under
one framing.

A second defect fired *during* the run: `run_development`'s write path was still hardcoded to
`result.json` because a formatter had split the call across two lines and defeated an earlier
patch's string match. The gemma bare run overwrote Phase 5's artifact on disk. Nothing was
lost — it was restored from git to its exact hash and the gemma bare artifact regenerated from
cache with zero model calls.

## 4. Ladder — accuracy / largest-answer-share / answer-entropy (bits), n = 24 per cell

| Mechanism | Condition | L0 explicit | L1 | L2 | L3 |
|---|---|---|---|---|---|
| formal_expression_depth | gemma-framed | .917/.58/.98 | .875/.54/.99 | .542/.62/.95 | .542/.71/.87 |
| | gemma-bare | .625/.79/.74 | .667/.83/.65 | .542/.88/.54 | .542/.79/.74 |
| | **qwen-bare** | **1.000/.50/1.00** | .833/.67/.92 | .792/.54/.99 | .625/.54/.99 |
| transitive_dependency | gemma-framed | .875/.62/.95 | .917/.58/.98 | .667/.83/.65 | **.500/1.00/0.00** |
| | gemma-bare | .667/.75/.81 | 1.000/.50/1.00 | .667/.83/.65 | **.500/1.00/0.00** |
| | **qwen-bare** | .958/.54/.99 | 1.000/.50/1.00 | .958/.54/.99 | **.750/.50/1.00** |
| precondition_conjunction | gemma-framed | 1.000/.50/1.00 | .708/.79/.74 | **.500/1.00/0.00** | **.500/1.00/0.00** |
| | gemma-bare | .875/.62/.95 | .542/.96/.25 | .458/.88/.54 | .500/.92/.41 |
| | **qwen-bare** | 1.000/.50/1.00 | .958/.54/.99 | **1.000/.50/1.00** | **1.000/.50/1.00** |

## 5. Primary endpoint (preregistered)

Paired exact McNemar on the degeneracy indicator — whether the solver's answer equals gemma's
modal answer — pooled over the three cells where gemma reached answer share 1.000
(`precondition_conjunction` L2/L3, `transitive_dependency` L3), n = 72.

| Comparison | degenerate rows | b | c | exact p |
|---|---|---|---|---|
| gemma-framed vs **qwen-bare** | 72/72 → **36/72** | 36 | 0 | **2.9e-11** |
| gemma-framed vs gemma-bare | 72/72 → 67/72 | 5 | 0 | 0.0625 |

36/72 is exactly what a balanced answerer produces by chance against a fixed modal answer, so
qwen shows **no residual degeneracy at all**. Removing gemma's framing does not rescue it.

Answer entropy on those three cells: gemma 0.00, 0.00, 0.00 bits; qwen **1.00, 1.00, 1.00**.
Accuracy there: gemma .500/.500/.500 (chance); qwen **1.000/1.000/.750**.

**Secondary**, pooled positive accuracy over all 12 cells (n = 288): gemma-framed .7118,
gemma-bare .6319, **qwen-bare .9062**.

## 6. Mechanism qualification

| Mechanism | gemma-framed | gemma-bare | qwen-bare |
|---|---|---|---|
| formal_expression_depth | VOID_NEGATIVE_CONTROL | VOID_INSTRUMENT_LIMIT | VOID_NEGATIVE_CONTROL |
| transitive_dependency | VOID_INSTRUMENT_LIMIT | VOID_INSTRUMENT_LIMIT | **QUALIFIED** (L3) |
| precondition_conjunction | VOID_POSITION_SHARE | VOID_INSTRUMENT_LIMIT | **VOID_CEILING** |
| explicit arms passing | 2/3 | 0/3 | **3/3** |
| qualified | 0 | 0 | **1** |

`transitive_dependency` is **the first mechanism ever to qualify in this programme**: explicit
arm .958, frontier .750, share .50, negative control collapsing, position invariance and
shortcut audit clean.

**The failure mode inverted.** Gemma failed at the floor (constant answers, chance accuracy).
Qwen's two non-qualifying mechanisms fail for the opposite reasons:

- `precondition_conjunction` is `VOID_CEILING` — 1.000 at *every* level. The ladder never
  reaches this solver's frontier.
- `formal_expression_depth` is `VOID_NEGATIVE_CONTROL` through a **selector miscalibration, not
  a reading failure**. Destroyed twins are information-identical with opposite targets, so any
  deterministic solver scores exactly 0.500 on them, making the gap gate equivalent to
  `positive ≥ 0.70`. But frontier selection targets 0.625. Qwen landed L3 at exactly .625 — the
  target — and was therefore voided, while its L1 (.833) and L2 (.792) would both have passed
  the gap and share gates. The selector actively chose the one level that cannot qualify.

## 7. Sentinel, reported as computed and as interpreted

The frozen code emits `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` for
qwen, because the abort clause fires whenever fewer than 2 mechanisms qualify while ≥2 explicit
arms pass. **That label is now demonstrably wrong for this solver** and is reported here only
because the rule is frozen. Qwen did not fail to support measurement: it qualified a mechanism,
saturated another, and was voided on a third by a selector defect. The abort clause was written
for a floor failure and does not distinguish a ceiling one.

Phase-6 classification under the preregistered options is **`SOLVER_SPECIFIC_FAILURE_SUPPORTED`**:
qwen materially escapes gemma's collapse **and** one preregistered mechanism qualified.

## 8. Validity

| | gemma-framed | gemma-bare | qwen-bare |
|---|---|---|---|
| rows | 384 | 288 | 384 |
| schema errors | 0 | 0 | 0 |
| parser errors | 0 | 0 | 0 |
| input/output truncations | 0 | 0 | 0 |
| Q0 | 1.000 | 1.000 | 1.000 |
| cache hits on the alternate solver | — | — | 0 |

No invalidation condition fired. Digest verified against the live model before the run;
template hashes recorded; both solvers deterministic at temperature 0 (24/24 information-
identical twin pairs agree).

## 9. Game R and R*

`founder_tournament_authorized = false` — the frozen gate needs 2 qualified mechanisms and got
1. **`GAME_R_NOT_RUN`.** No threshold was reinterpreted to force it. **`RSTAR_NOT_IDENTIFIED`.**
No representation has been scored at any point; Phase 6 measured only the control surface.

## 10. Limitations

- One alternate solver. It is a fine-tuned checkpoint with no recorded lineage, and it is 27.3B
  against 11.9B, so family and scale move together. A *positive* result is nonetheless clean:
  we found a solver that exposes the mechanisms.
- Per-cell accuracy at n = 24 is underpowered; only the pooled degeneracy endpoint is
  confirmatory. The per-cell grid is descriptive.
- Gemma's bare condition handicaps it (all three explicit arms drop below gate), so gemma-bare
  is a lower bound on gemma, not a fair characterisation of it.
- The negative-control constant and the frontier-target miscalibration are properties of the
  frozen instrument that now demonstrably cost a qualification.

## 11. Highest-EV next experiment

**Fix the frontier selector and re-run qwen only.** Two changes, both justified by measurement
rather than by taste, and both requiring a new instrument version:

1. Set the frontier target inside the *achievable* window. With the negative control pinned at
   0.500 and `gap ≥ 0.20`, only `positive ∈ [0.70, 0.85]` can qualify; targeting 0.625
   guarantees selection of unqualifiable levels. Target ~0.775.
2. Extend the ladder upward. `precondition_conjunction` is at 1.000 for qwen at every level and
   `transitive_dependency` needs 5 hops before it leaves ceiling; the ladder was calibrated to a
   weaker solver.

Under fix (1) alone, `formal_expression_depth` would have selected L2 (.792) and passed the gap
and share gates — giving 2 qualified mechanisms and authorising the founder tournament. That is
the single highest-value next run, at ~400 calls.

Do **not** run a third solver: the question this phase asked is answered.
