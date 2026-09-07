# Local Mathematical Data Atlas

Scanned roots: `/Users/moheet/Documents/ChatGPT` and
`/Users/moheet/Projects/Hamiltonian-Labs`. Machine inventory:
`research/codex_audit/local_data_registry.json`. No corpus was downloaded or modified.

## Highest-value verified assets

### LeanDojo Benchmark 4 derived transitions

- Derived file: `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo/steps.jsonl`
- 259,580 rows; 271,038,884 bytes; SHA-256 `ddd90685d94ac1792b95d699a8d10e667bf30ada7d3150010402aedf7ac33120`.
- Splits: train 250,814; validation 4,260; test 4,506.
- 167,779 rows contain premises; 418,704 premise references.
- 3,606 source files. Dominant tactic heads: `rw` 48,991, `simp` 33,298, `exact`
  30,785, `have` 16,876, `refine` 14,293, `apply` 10,032.
- Raw benchmark: `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4`.
- Metadata: LeanDojo 2.0.0, Mathlib commit
  `29dcec074de168ac2bf835a77ef68bbe069194c5`, creation timestamp 2024-07-02.
- Trust boundary: formally sourced traces, but this audit did not freshly replay every row.

`[VERIFIED_BY_SOURCE_DATA]`

### Lean runtime V2 corpus

- Five gzip JSONL parts under `/Users/moheet/Documents/ChatGPT/HML_V3/data/corpus/`.
- Exactly 1,150 rows; 17,042,127 compressed bytes; schema
  `canonical-math-transition-v2.0.0`.
- Exactly 461 structurally eligible states under the V5 eligibility rule.
- Exactly 104 survive the all-surface length-fair filter: shallow 34, medium 34, deep 36.
- 126 sealed source files are excluded by name; sealed final has 232 transitions and the search
  shard 918. The old sealed V1 split is retired.
- Trust boundary: Lean elaboration-time capture and independent structural-answer
  recomputation, not tactic replay.

`[VERIFIED_BY_SOURCE_DATA] [VERIFIED_BY_CODE]`

### Granular reasoning chains

| Source | Problems | Steps | Authoring / verification |
|---|---:|---:|---|
| `hmlt-reasoning-corpus/data/gold_10` | 10 | 23 | hand-authored; 21 verified, 2 verified-as-undetermined |
| `.../data/gold25/trajectories` | 25 | 118 | curated MATH reconstructions; manual semantic checks |
| `.../data/gold125/trajectories` | 100 new | 651 | deterministic source-grounded extraction; structural/source-span audit |
| **Union** | **135** | **792** | not formal proof certificates |

Gold-125 as a 125-problem union is 769 steps (Gold-25 plus the 100 new trajectories). The
previous “~300,000 granular reasoning steps” description is falsified; 259,580 refers to
LeanDojo tactic transitions, not the granular informal chains. `[VERIFIED_BY_SOURCE_DATA]`

### PRM800K and its held-out MATH split

- Official clone: `/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/prm800k_raw`,
  upstream commit `7ecc794703b2877f63226f2477a49b34f9b25163`.
- `prm800k/math_splits/test.jsonl`: exactly 500 rows, 446,564 bytes, SHA-256
  `35dc41080a3680858b27fa7e0533d2d547825316fc5dafe5d316f4ccc5a06132`.
- The official README says the remaining 500 uniformly sampled MATH test problems form the
  held-out set. “MATH-500” is common downstream nomenclature, not a file field.
- PRM800K contains 101,599 solution records / about 800k step labels. Those labels concern
  process correctness/progress, not Lean validity.

`[VERIFIED_BY_SOURCE_DATA]`

### Pinned Mathlib runtime

- Path: `/Users/moheet/Documents/ChatGPT/HML_V3/external/checkouts/mathlib4-29dcec0`.
- Commit `29dcec074de168ac2bf835a77ef68bbe069194c5`.
- Toolchain `leanprover/lean4:v4.10.0-rc1`; disk 352,733,938 bytes (~349 MiB).
- Only 38 `.olean` files are present in this audited checkout.
- Existing fresh-replay sample: 32 pass / 68 nonpass of 100; no full replay.

The shared gap report's claim of 5,680 `.olean` files and full replay readiness is not true of
this checkout. A precise build target and replay preflight are required before planning a
kernel-backed import. `[VERIFIED_BY_SOURCE_DATA]`

## HML_V3 registry

`/Users/moheet/Documents/ChatGPT/HML_V3/data/registry/datasets.yaml` exists (JSON-compatible
syntax) and contains 27 registered entries. Locally present highlights include:

- Hendrycks MATH: 12,500 rows; unverified informal solutions, licence unresolved locally.
- AMPS-Khan: 103,059 rows; 721 topics, 3,293 visual rows, 1,666 duplicate problems.
- PRM800K: 101,599 records.
- LeanDojo: 122,517 theorems / 259,580 transitions.
- Lean-Domino canonical records: 241,265 transitions.
- Lean pipeline V1: 1,000 transitions, with official split mixture requiring filtering.
- NuminaMath-Lean local: 104,155 rows; statements/proofs require replay policy.
- Herald proofs: 44,553 rows.
- State-tactic pairs: 56,407 rows.
- STP Lean 0320: 3,262,558 rows.
- Pythagoras SFT: 126,113 rows.
- GSM8K: 8,792 rows.

Trust tiers and exact paths are preserved in the machine inventory. Presence is not permission
to train: evaluation splits, source licences, source mixing, and proof replay must be resolved.

## Repository pins

| Repository | Branch | SHA | State |
|---|---|---|---|
| HML_V3 | `codex/open-ended-search-v2` | `95e8a26f…` | clean |
| hmlt-reasoning-corpus | `claude/max-ev-representation-experiment-v1` | `bf2cd75a…` | clean |
| Lean attestation worktree | `codex/lean-attestation-v1` | `b4e2d985…` | clean |
| hml-standard | `main` | `e879f5f5…` | clean |
| hamiltonian-lang | `claude/model-language-representation-freeze` | `b011511e…` | clean |
| official PRM800K clone | `main` | `7ecc7947…` | dirty from local provenance additions; read only |

## Immediate use order

1. LeanDojo transitions for task-family discovery and premise/rewrite/state-progress pilots.
2. The 1,150 runtime records for a small, source-file-disjoint, kernel-preflighted instrument.
3. The 792 granular steps for a human-readable operation codebook, never as proof truth.
4. PRM800K for controller/dead-end concepts, not mathematical validity.
5. Large local generated corpora only after licence, split and replay audits.
