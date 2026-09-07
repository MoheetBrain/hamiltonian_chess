# Phase 6 Forensic Review

## Verdict

`PHASE6_INVALID_LITERAL_CACHE_GATE`.

The Qwen artifact is complete enough for descriptive analysis and shows a large solver effect,
but the preregistration says *any* alternate-solver cache hit invalidates Phase 6. The artifact
has 13 ladder hits from the restart and 48 full-family reuse hits. The frozen ≥2-mechanism Game-R
gate also fails because only `transitive_dependency` qualifies.

## Hazard 1 — model/cache decoupling

The old architecture could use a changed model name for the live call while leaving another
model's digest in the identity. `_cached_call` would then return the existing file before any
call. The corrected path is visible in `arena/experiments/fitness_v5.py`: the `SOLVERS` registry
binds name and digest (lines 102–123); `verify_served_model` checks the served digest (126–164);
`evaluate` places `solver["digest"]` in the identity (737–745) and passes the same solver into
the call (746). Status: **FIXED**. `[VERIFIED_BY_CODE]`

## Hazard 2 — solver renderer asymmetry

Recorded diagnostics show Gemma's default path adds 12 prompt tokens relative to `raw:true`,
and changed one sampled answer; Qwen default and raw token counts agree. `/api/show` returns the
same apparent `{{ .Prompt }}` template for both and is not a neutrality proof. Phase 6 therefore
uses `raw:true` for both and a distinct runtime hash. This is the correct containment. Phase 5
remains an internally consistent framed-Gemma experiment, but it is a third condition rather
than the baseline of a two-condition solver comparison. `[VERIFIED_BY_ARTIFACT] [VERIFIED_BY_CODE]`

## Hazard 3 — artifact write path

The Gemma-bare run initially wrote to hard-coded `result.json`, temporarily replacing Phase 5.
The committed Phase-5 file was restored to SHA-256
`0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`.
The separate Gemma-bare file has SHA-256
`6deead5897cd8756274f45d755b66022bdb0ae58b7fb272661b3fdcc82838418`.
The path function now separates solver/condition outputs. Status: **FIXED**, but add a refusal
test for frozen destinations. `[VERIFIED_BY_ARTIFACT] [VERIFIED_BY_CODE]`

## Hazard 4 — frontier versus negative-control calibration

Each destroyed pair has identical input but opposite target. A deterministic solver necessarily
gets exactly one of each pair correct, so negative accuracy is 0.500. The gate requires:

`positive_accuracy - negative_accuracy >= 0.20`, hence `positive_accuracy >= 0.70`.

The selector instead chooses the level closest to 0.625 inside its frontier band. Therefore a
perfectly selected 0.625 cell is mathematically unable to pass the gap gate. The effective
qualification window is `[0.70, 0.85]`, not the selector's full band. Do not modify frozen Phase
6; align these rules or redesign the negative control in the next preregistration.
`[VERIFIED_BY_CODE]`

## Cache-rule audit

| Region | Row occurrences | `cache_hit=true` | Interpretation |
|---|---:|---:|---|
| Qwen ladder | 288 | 13 | prior same-identity rows from the restarted run |
| Qwen full family | 144 | 48 | ORIGINAL/COUNTERFACTUAL reuse from ladder evaluation |
| Total | 432 | 61 | 384 unique evaluation identities |

The cache records are not evidence of a cross-model collision: identity includes the Qwen
digest and bare runtime hash. Nevertheless, the frozen invalidation condition has no exception
for restart or within-run reuse. A future rule should separately define (a) foreign-identity
contamination, (b) same-identity resume, and (c) planned within-run reuse. `[VERIFIED_BY_CODE]`

## Results, with proper scope

- Gemma framed: three prespecified collapsed cells had modal-position count 72/72.
- Gemma bare: 67/72; exact McNemar discordance 5/0, two-sided p=0.0625.
- Qwen bare: 36/72; discordance 36/0, p=`2.91e-11`.
- Qwen ladder: formal depth `1.000, .833, .792, .625` (void shortcut/negative control);
  transitive dependency `.958, 1.000, .958, .750` (`QUALIFIED`); precondition conjunction
  `1.000, .958, 1.000, 1.000` (`VOID_CEILING`).

The solver effect is a valid descriptive observation about these fixed cells. It does not make
the protocol valid, does not meet the Game-R gate, and does not identify any R effect. The Qwen
artifact was untracked in Claude's worktree at audit time; freeze it before further reporting.
