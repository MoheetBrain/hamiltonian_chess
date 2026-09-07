# Experiment Evidence Ledger

Audit base: `b150ce1c0c758f773ca5e575a3db82928dcb3737`. Machine record:
`research/codex_audit/experiment_evidence.json`.

Evidence authority is, in descending order: canonical/source records plus independent
verification; frozen code/manifests; raw rows; derived decisions; narrative prose. Tags are
`VERIFIED_BY_CODE`, `VERIFIED_BY_ARTIFACT`, `VERIFIED_BY_SOURCE_DATA`,
`REPORTED_NOT_REPRODUCED`, or `HYPOTHESIS`.

## Ledger

| Stage | Question / changed variable | Model and data | Metric and result | Classification | Usable evidence |
|---|---|---|---|---|---|
| V0 | Can a deterministic canonical world and verifier be materialized? | No model; 676 generated trajectories, 13 domains × 52 | 520 GOLD, 104 SILVER, 52 REJECT; world hash `ac16014c…` | `INSTRUMENT_RESULT_ONLY` | Canonical generation, hashes, provenance and verifier plumbing work. It says nothing about representation quality. `[VERIFIED_BY_ARTIFACT]` |
| V1 | Can one solver rank seed representations on a multiple-choice benchmark? | Gemma; synthetic tasks | Gate invalidated by option-position behavior | `INVALIDATED` | Retain the lesson that counterfactual and option-swap controls are mandatory. Candidate scores do not rank R. `[VERIFIED_BY_ARTIFACT]` |
| V2 | Does a calibrated equal-information mechanism provide ranking headroom? | Same solver; five controlled slices | Protocol/Q0 passed, but control range 0.125 missed frozen 0.15 headroom; no ranking | `INSTRUMENT_RESULT_ONLY` | The instrument lacked dynamic range. No equivalence or R conclusion. `[VERIFIED_BY_ARTIFACT]` |
| Matched A100 sprint | Do five concrete surface codecs learn NEXT_ACTION differently under matched examples? | Qwen2.5-7B-Instruct; World-v0 | One-seed Stage-A exact differences followed by saturation | `HISTORICAL_GUIDANCE` | Timing and failure discovery only. Inert split seed, mixed quality, content overlap, metadata-solvable labels, vacuous “verified”, tail truncation, and non-comparable per-token loss defeat a clean R estimate. `[VERIFIED_BY_CODE]` |
| V3 | Can a formal aggregate gate qualify a founder tournament? | Gemma; six mechanisms | Aggregate passed, but five mechanisms were ceilings and state-delta was a floor for 7/8 founders | `INVALIDATED` | Mechanism-level qualification must precede pooling. Founder differences cannot rank R. `[VERIFIED_BY_ARTIFACT]` |
| V4 | Can calibrated ladders identify measurable structural mechanisms? | Gemma; five mechanisms | 0/5 qualified; 89/348 malformed, 59 at output budget, 24 character-guard unsent, 6 true context truncations | `INSTRUMENT_RESULT_ONLY` | Negative instrument result and diagnostic evidence only. It motivated token-aware V5. `[VERIFIED_BY_ARTIFACT]` |
| V5 / Phase 5 | Can the constrained formal instrument qualify at least two mechanisms? | `gemma4:12b`, framed; 3 mechanisms, 432 raw rows | 0/3 qualified. Two explicit arms passed, but selected cells failed/voided | `VALID_NEGATIVE_EVIDENCE` | This solver/task/protocol could not support Game R; no representation was evaluated. Formal depth also leaks shortcuts. `[VERIFIED_BY_ARTIFACT]` |
| Phase 6 Gemma bare | Does removing renderer framing rescue Gemma? | Same Gemma, `raw:true`; 288 ladder rows | Explicit L0 accuracy 0.625 / 0.667 / 0.875; all `VOID_INSTRUMENT_LIMIT` | `VALID_NEGATIVE_EVIDENCE` | Bare bytes do not rescue Gemma and substantially change explicit-arm performance. `[VERIFIED_BY_ARTIFACT]` |
| Phase 6 Qwen bare | Does a different solver escape Gemma degeneracy while the V5 instrument stays frozen? | `qwen38-rvn:latest`, bare; uncommitted external artifact SHA `e753de98…` | One mechanism qualified. Fixed-cell modal count falls 72/72→36/72; exact McNemar p=`2.91e-11`. Artifact contains 61 cache-hit row occurrences | `INVALIDATED` | Descriptive solver-effect evidence only. The literal preregistered cache rule fired and the ≥2-mechanism gate was not met. No founder/R claim. `[VERIFIED_BY_ARTIFACT] [VERIFIED_BY_CODE]` |

## Phase 6 classification boundary

The Qwen rows are internally attributable to the recorded Qwen digest, bare runtime hash,
genome hash, probe hash and prompt hash. Thirteen ladder hits arose because the run was
restarted; 48 full-family hits are the already-evaluated ORIGINAL/COUNTERFACTUAL rows being
reused. That makes the numerical signal scientifically informative, but it does not permit
ignoring the frozen sentence “Phase 6 is `PHASE6_INVALID` if cache hits > 0 for the alternate
solver.” The correct protocol classification is therefore `INVALIDATED`, with a separate
descriptive observation that solver family/scale changes behavior.

## What is not proved

- No experiment identifies `R*`, `R*-v0`, or a founder representation advantage.
- No result shows that representations are equivalent.
- No matched-learning result cleanly isolates R from metadata, quality, split, tokenizer, or
  truncation effects.
- No Phase 6 result authorizes a founder tournament: Qwen has one qualified mechanism, and
  the frozen gate requires at least two.
