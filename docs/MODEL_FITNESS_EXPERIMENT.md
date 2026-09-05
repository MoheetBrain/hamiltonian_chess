# Model fitness experiment: representation landscape v1

Status: **PRE-REGISTERED — NO SCIENTIFIC MODEL RESPONSE OBSERVED**  
Experiment version: `arena-representation-fitness-v1`  
Start date: 2026-09-05  
Start branch: `codex/arena-v0-fitness`  
Start SHA: `c1dd586db6abb9bd4e72f0048122eb4ddca98739`

## Question and stopping discipline

The primary question is whether controlled, semantics-preserving changes to mathematical
representation create a measurable, reproducible, locally searchable fitness landscape for
one frozen solver. This experiment measures frozen-model acquisition (Q2), not semantic
validity (Q1) and not matched learnability (Q3). It does not select or freeze R*.

The experiment stops after calibration if no existing DEV slice places the strongest control
outside severe ceiling (at least 90%) and severe floor (at most 10%). It stops after Tier 2A if
a bounded replication remains flat/noisy. Tier 2B runs only after behavioral differences are
observed. Matched 1K adaptation runs only after a reproducible searchable signal survives
fresh PROMOTION/OOD tasks. No 5K arm runs unless a 1K result is ambiguous and competitive.

## Frozen Arena baseline

| Object | Frozen identity |
|---|---|
| Arena source | `c1dd586db6abb9bd4e72f0048122eb4ddca98739` |
| Canonical schema | `arena-canonical-v0.1.0` |
| Stored world JSONL SHA-256 | `1669eced75878af09d27606f6d54fd1cff3615a9b62f0be0b0c379e8631ffd1b` |
| Canonical world semantic hash | `ac16014cd20fbed2dabacd75bff3fd19723e3e96048f82a1ee1a574f59daf256` |
| Regenerated world-object hash | `21fdabf9de57a6b28cbce4cc22ed5a9fcb25ecf96e0d3f7721e66e5a6b38d5a9` |
| Gold corpus hash | `eaa9d8a5dc74e3fbaf85a744417f65a6d1cafbd11f73e6e0f6ae9bb9e7bd61be` |
| Gold truth/transition hash | `c776566244e4468f6676ea2f2a9113511e1322f08d052ecf0dc32b8d6bdf2f7d` |
| Seed artifact SHA-256 | `34f0c3da4d42d6668b26092f526cf1750a93c032142c4d14316cecea2774c6c8` |
| Tasks | 676: 520 Gold / 104 Silver / 52 Reject |
| Existing seeds/candidates | 8 executable seeds / 28 database language rows |
| Existing mutations | 20 metadata proposals; no prior mutated model evaluation |
| Baseline tests | 103 passed; Ruff, Ruff format, and mypy passed |
| Assurance | 0 critical defects; 0 false accepts in 2 bounded universes and 2,767 enumerated cases; 9 differential verdicts with 0 unresolved disagreements |

The Gold hash is SHA-256 over the sorted records
`{task_id, task.content_hash, trajectory.content_hash}`. The Gold truth hash additionally
commits to every complete trajectory. Any change to canonical truth, Gold answer/transition,
or verifier invalidates every model observation and requires a new version.

### Frozen seed genome hashes

| Seed | Genome hash |
|---|---|
| `L0_STRUCTURED_ENGLISH` | `9823d4955c8416811632af0656518e84a9e23bc513cc9ce7a037e33c955c0d2f` |
| `L1_CURRENT_HML` | `d888b38a320d50c2c144d779dfb3aa252621e9add8671788d6d885ef4fb0a84e` |
| `L2_SEXPR` | `4e77c1921fd1f7d4a3b982596e3905733c654f19361e9e3a1f241a12e8a080c2` |
| `L3_JSON_AST` | `18e8dd1e64954dfc3531b6486b10d1f86a03a1c6b00cb0224acd9054ccb8b9db` |
| `L4_TYPED_PREFIX` | `fa7ff2917e9625153f55f55331ded6da58e848d013223525318a582def6d1380` |
| `L5_COMPACT_SYMBOLIC` | `a2990983e8ae6f8316b21766b198d4422b78ee6bfad5a547826fae096fc880e5` |
| `L6_GRAPH_TRIPLES` | `76505d77699754d9c28e5585537bb0fce19c60a270519d9d55a6dc91bee2ac5b` |
| `L7_HYBRID_ROLE_LABELLED` | `153580895946a29ae469358ec5a16736f861b23fcae805680729461f7015c063` |

## Reuse audit and prior evidence

The mandatory all-history audit is in `docs/CROSS_REPO_ASSET_AUDIT.md` and
`artifacts/reuse/`. Prior scores are excluded from this experiment. Reused mechanisms are
common-envelope comparisons, group-aware splits, paired task-level statistics, decoded-text
Unicode checks, information-equality tests, and explicit negative-result stopping rules.

## Executable population and Gate 0

Population seed: `20260905`. Population hash:
`815efcc2d913e7338915b1ed656537a9acf8ec85021f53e2810648c2c7a3c075`.

The population contains 120 deterministic children: 15 for each of eight parents. Every child
has mutation distance one and changes exactly one of grammar, binder encoding, type placement,
state/field order, action-option encoding, serialization, role morphology, or compression.
There is no crossover and no semantic mutation. All phenotypes use the same Arena-owned
reversible compiler and strict canonical-wire decoder. The compiler makes each changed gene
observable in emitted bytes on its affected slice.

Gate 0 runs over both initial and final states for all 520 Gold tasks (1,040 states per
candidate). Admission requires byte-deterministic rendering, exact full canonical dictionary
identity after parse, no collision, and the existing strict wire validation. A candidate with
any failure is `DEAD_SEMANTIC` and is forbidden from model evaluation. Full Arena assurance
remains mandatory before any release, but is not conflated with this per-candidate codec gate.

## Frozen partitions

Split manifest: `artifacts/experiments/fitness_v1/task_split.json`.

- DEV: 160 Gold tasks; engineering/calibration only.
- SCOUT: 120 Gold tasks; Tier 2A only.
- PROMOTION: 160 Gold tasks; candidate generation cannot inspect outcomes.
- OOD: 80 Gold tasks from the two highest available structural groups: conditional probability
  and evidence replay (combined dependency/scope/composition/cross-domain score at least five).

The grouping key is `domain|operation`; an entire group belongs to exactly one partition.
Near-identical instances of one domain template never cross a partition. Ordinary random
holdout is not called OOD. World v0 has limited structural depth, so OOD means the deepest
available held-out combinations, not general out-of-distribution mathematics.

Frozen protocol slices are stored and hashed inside the manifest:

- `CALIBRATION_DEV`: 16 balanced DEV tasks.
- `CALIBRATION_HARD_DEV`: 16 disjoint highest-complexity DEV tasks, used only after a ceiling.
- `TIER2A_SCOUT`: 16 balanced SCOUT tasks.
- `TIER2B_PROMOTION`: 64 fresh PROMOTION tasks.
- `OOD`: all 80 OOD tasks, only after promotion is justified.

The total calibration cap is 32 tasks per control across both rungs. Calibration responses are
never promotion observations.

## Frozen model/runtime configuration

No model was downloaded. The selected already-local calibration/scout solver is:

| Setting | Frozen value |
|---|---|
| Ollama model | `gemma3:4b` |
| Ollama list ID | `a2af6cc3eb7f` |
| GGUF blob SHA-256 | `aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25` |
| Architecture/size | Gemma 3, 4.3B parameters |
| Quantization | `Q4_K_M`, GGUF quantization v2 |
| Tokenizer metadata | GGUF `llama` tokenizer, BOS 2, EOS 1 |
| Native context | 131,072; experiment `num_ctx` 8,192 |
| Temperature | 0.0 |
| Seed | 20260905 |
| Maximum completion | 32 tokens |
| Other sampling | Ollama defaults `top_k=64`, `top_p=0.95`; temperature zero |
| Runtime | Ollama 0.33.2, local HTTP generation |
| Hardware | Apple M5 Max, 18 CPU cores, 48 GB unified memory |

The complete model digest, runtime options, candidate genome hash, task hash, and prompt hash
form the response-cache identity. Failed, empty, or malformed responses remain task-level
outcomes and are never silently dropped.

## Frozen acquisition and response protocol

All candidates use the same common envelope and the same mechanically generated information
classes: grammar, fields, binding, types, state/action convention, and two action alternatives.
No hand-written candidate-specific teaching is permitted. The guide template is frozen in
`arena/experiments/fitness_v1.py`.

The exact instruction is:

> Choose the next mathematically correct action. Return exactly one JSON object and nothing
> else: {"choice":"A"} or {"choice":"B"}.

Option order is a SHA-256 function of experiment seed and task ID. It is identical across
candidates. Options are opaque `A`/`B`. The model never receives task ID, task family,
difficulty, language/candidate ID, action ID, `invalid_` operation labels, warrants,
usefulness, requested quality, or legal/invalid pool labels. Candidate options contain only
the mathematical result arguments. The observed state has both oracle action pools empty.

Scoring accepts exactly a one-field JSON object with choice `A` or `B`. Explanations, bare
letters, extra fields, and malformed completions are incorrect. Prompt equality tests assert
that all non-representation protocol text and option order are invariant.

## Calibration and tier decisions

Permanent calibration controls are the representations induced by the frozen
Structured-English, S-expression, JSON-AST, and current-HML seed genomes through the common
fitness-v1 compiler. This isolates genome changes under one compiler; it does not reuse old
model scores. Their legacy seed codecs remain separately covered by Arena assurance.

Run the first 16-task calibration rung for all four controls. If strongest-control accuracy is
at least 90%, run the disjoint 16-task harder rung; if it remains at least 90%, stop with
`MODEL_FITNESS_BENCHMARK_INVALID`. If it is at most 10%, use the easier remainder under the
same total cap; if no useful region exists, stop with the same sentinel. The target is 30–80%;
10–30% and 80–90% are explicitly borderline.

Tier 2A is frozen to 24 candidates: all eight seed controls plus two children for every mutable
family, over 16 SCOUT tasks (384 calls). Tier 2B, if earned, promotes 6–10 candidates using
soundness, paired behavior, and diversity—not token score—over 64 fresh PROMOTION tasks.
Selection rules cannot be revised after seeing candidate results.

## Frozen metrics and statistics

The primary metric is strict next-action accuracy. Secondary task-level fields are malformed
response, invalid-action selection, verified-action selection, prompt/input tokens, tokens per
correct action, latency, domain, and structural dimensions. Aggregates never replace the
outcome matrix.

Every comparison is paired on identical task IDs. It reports accuracy difference, `n10`
(A-only correct), `n01` (B-only correct), a 4,000-resample percentile bootstrap clustered by
domain-operation group, and exact two-sided McNemar/binomial probability. Domain and structural
summaries are descriptive. An interval spanning zero means unresolved, not equivalence.

Landscape code is frozen in `arena/evaluation/landscape.py` (pre-commit file SHA-256
`f5416fa9ba7e843915a95cc1e1195e7854a9586e9d6795ecd560f209ccc607c2`). It reports
valid-neighbor rate, beneficial-mutation rate, parent-child correlation, cross-parent gene
effect consistency, one-edit ruggedness, fresh-set rank stability, static-token/model
correlation, and an explicit L5 verdict. Soundness is eligibility; model fitness, hidden/OOD
stability, then efficiency determine Pareto interpretation. There is no governing scalar
landscape score.

## Invalidation rule

After the first model call, changing canonical semantics, Gold truth, partitions, prompt
template, action ordering, response parser, statistical code, model digest/configuration, or
candidate bytes invalidates affected comparisons. A corrected version receives a new
experiment version and no old responses are relabelled. Raw completions are inspected during
calibration because automated gates have missed prior defects.
