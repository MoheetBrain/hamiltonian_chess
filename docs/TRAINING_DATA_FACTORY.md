# Training Data Factory

**Status: PIPELINE SPECIFIED AND EXECUTABLE END-TO-END; NO CORPUS GENERATED.**
Deliberately so — the sprint's brief was to make mass generation *possible next*, not to spend the
sprint generating data.

## 1. The pipeline

```
source problem  →  canonical / TL0 state  →  verified transition
      →  TRAINING_LANGUAGE_V0 renderer  →  validation  →  shard  →  manifest + hash
```

Implemented in `releases/TRAINING_LANGUAGE_V0/training_schema.py`. Record schema
`tl0-training-record-v1`:

```
trajectory_id · problem_id · step_index
state_t · rendered_state_t
candidate_actions[] · rendered_candidate_actions[]
chosen_action · rendered_chosen_action · warrant
next_state · rendered_next_state
verification · outcome · provenance · surface · content_hash
```

## 2. Three design decisions that matter

**Targets render through the same surface as inputs.** Via `action_envelope`. This removes defect
**D3** in `docs/ROUTE_B_PARITY_AUDIT.md` by construction: the historical matched sprint always
rendered targets as canonical JSON, which gave `L3_JSON_AST` alone input-grammar = output-grammar —
a live alternative explanation for its win that no amount of analysis could remove after the fact.

**`state_t` is the lossless TL0 text.** One serialization, one hashing scheme
(`arena.canonical.schema.stable_hash`). There is no second representation of the same state to
drift.

**Writes fail closed.** `write_jsonl` refuses any record that does not assert
`sealed_splits_excluded`. `read_jsonl` refuses on content-hash mismatch and on wrong-surface
shards. A `Transition` *computes* its `StateDelta` and refuses to emit a `VERIFIED` outcome when no
matching record exists in `state_after`.

## 3. What can be generated today, and at what trust tier

| Source | Items available | Tier | Ready? |
|---|---|---|---|
| Premise selection (LeanDojo train) | 63,831 | recorded-transition ground truth | **yes** |
| Rewrite direction (LeanDojo train) | 3,466 controlled | recorded-tactic ground truth | **yes** |
| Legal transformation | 24,000 | `TIER_B_CONSTRUCTED` only | yes, with the tier stated |
| Lean runtime V2 canonical corpus | 1,150 transitions / 461 eligible states | Tier A native-verified | yes |
| Gold-125 / Gold-25 granular chains | 769 steps | `ANNOTATION_UNVERIFIED` | only as annotation |
| Gold-10 | 23 actions, hand-authored | deterministically checked | contamination-free, tiny |

**The binding constraint is unchanged and is not an engineering problem:** verification and
richness are anti-correlated across the whole estate. Everything `VERIFIED_FORMAL` is
single-operation Lean data with no warrants; everything richly annotated is unverified and
MATH-contaminated. Only 32 transitions anywhere have ever been freshly replayed in Lean.

## 4. Scaling — the honest cost

Tier-A promotion requires Lean replay at the historical **32/100** yield: ≈3,100 attempted replays
per 1,000 verified items, ≈1.3 h at four workers against the local built mathlib
(`HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec07…/mathlib4`, 18 GB, 5,680
`.olean`, toolchain v4.10.0-rc1 — **not** the 349 MB source-only checkout at
`external/checkouts/mathlib4-29dcec0`, which has 38 `.olean` and cannot replay).

A 100k-item Tier-A corpus is therefore ≈310k replays ≈ 130 worker-hours. That is a real number and
should be budgeted, not assumed away.

## 5. What must never enter training

Enforced by `arena/corpus/contamination.py`, which computes **transitive** exposure closure over
derivation edges rather than relying on a human to remember:

- The four sealed LeanDojo splits (`artifacts/manifests/SEALED_SPLITS.json`).
- `prm800k/math_splits/test.jsonl` — verified **exactly 500 lines**; it *is* MATH-500, and PRM800K's
  training data contains 4,500 of the 5,000 MATH test problems.
- Anything reachable from a `RESERVED_EVAL` or `OOD` source. An **unknown** source is refused by
  default; `may_train` returns `False` rather than raising, so there is no exception path to
  swallow.

## 6. Next steps, in order

1. Wire an environment → `tl0-training-record-v1` adapter for premise selection (the largest ready
   family) and emit a 1,000-item smoke shard with a manifest.
2. Run the Tier-A replay design in `artifacts/manifests/legal_transform_manifest.json`
   (`lean_tier_a_replay`) on a 1,000-item slice to convert family C off `TIER_B_CONSTRUCTED`.
3. Only then consider volume. Mass generation before step 2 would produce a large corpus whose
   labels are constructed rather than verified.
