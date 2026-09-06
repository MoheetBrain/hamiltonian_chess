# FITNESS_V2_INSTRUMENT_QUALIFIED

# Hamiltonian Arena — Authoritative Claude Handoff

This document is the operational source of truth for a capable engineer/researcher arriving
with no conversation history. Read it before changing code or running model experiments. The
current instrument is valid, but the candidate landscape has **not** been measured: fresh V2
calibration missed its precommitted headroom gate by 2.5 percentage points. Do not cross that
gate by lowering it after the fact.

Conflict precedence is deterministic: executable frozen code plus its committed manifest →
primary raw task rows → derived result/decision JSON → reports → this narrative handoff. If two
layers disagree, stop, preserve both, recompute hashes from the higher-precedence layer, and
open a new experiment version rather than silently repairing historical evidence.

## 1. Project definition

Hamiltonian Arena is an evidence-first system for testing whether the representation of a fixed
mathematical state is a causal, searchable variable in machine reasoning. Its central
hypothesis is not "HML is best." It is: holding mathematical information, task, solver,
instructions, and scoring fixed, some machine-facing representations may reliably improve
verified reasoning, efficiency, or learnability.

`R*` means a discovered representation that has survived semantic release assurance, credible
model-fitness comparison, fresh hidden-set stability, and important regression checks. `R*-V0`
is a release candidate, not a label awarded to the highest noisy scout score.

Keep these layers separate:

- **Canonical mathematical truth:** immutable Arena records and independent domain oracles.
- **Representation:** a reversible rendering/parsing phenotype controlled by a language genome.
- **Solver policy:** the fixed local model acting on a representation.
- **Verifier:** representation-independent checks of states, transitions, obligations, and
  external/differential evidence.
- **Curriculum:** chooses informative tasks without defining truth.
- **Language evolution:** proposes controlled representation mutations after a valid fitness
  signal exists.

The scientific objective is to discover whether representation is a causal variable with a
searchable landscape. The intended sequence is: discover `R*` → verify it → generate verified
trajectories → run matched training → scale only if the advantage persists. HML is one control
and one historical design lineage; it is not privileged.

## 2. Repository history

Repository: `MoheetBrain/hamiltonian_chess`. Active branch:
`codex/arena-v0-fitness`. Starting SHA for this continuation:
`22cab970862ee80cd30ce42b2d885ef52e73b47c`. Earlier important commits:

| Commit | Meaning |
|---|---|
| `c1dd586db6abb9bd4e72f0048122eb4ddca98739` | Complete Arena v0 architecture, frozen world, eight seed representations, verifier/players/league/assurance infrastructure |
| `f17bb0f73ac942d43b614704e54c019a64284368` | Fitness V1 preregistration: population, group-aware split, prompt/scorer decisions |
| `11b73ae6756fa02984b3fecedab117d14ce0a26a` | Cached local-model runner and calibration artifacts |
| `22cab970862ee80cd30ce42b2d885ef52e73b47c` | V1 correctly stopped as `MODEL_FITNESS_BENCHMARK_INVALID` |
| `99c877f22e0c283be56bb369af3101019625c215` | V2 instrument/model/protocol/statistical rules frozen before any candidate comparison |

The final continuation commit is the commit containing this file; obtain it with
`git rev-parse HEAD`. Its exact pushed SHA is also recorded in the user-facing completion
report. A Git commit cannot literally contain its own hash, so this handoff records the stable
pre-candidate freeze hash above rather than a self-referential value.

V1 stopped because its model selected A on every Structured English and HML item and no control
beat the best position-only policy. That was successful scientific invalidation, not a failure
of Arena, HML, or the representation hypothesis.

## 3. Current architecture

```text
Frozen Arena World v0
  CanonicalState + CanonicalAction + independent domain oracle
                         |
                         v
LanguageGenome -> executable phenotype codec -> model-visible state/options
      |                  |                              |
      |                  +-> semantic Gate 0            v
      |                                           fixed Solver model
      v                                                  |
Architect proposes one-gene child                        v
      |                                      raw response + strict scorer
      v                                                  |
Refuter + verifier + assurance                           v
      |                                      paired metrics / landscape
      v                                                  |
Curriculum -> League -> Hall of Fame -> surrogate <------+
                         |
                         v
                  release gate for R*
```

Important modules:

| Path | Purpose, key API, inputs/outputs, scientific role |
|---|---|
| `arena/canonical/schema.py` | Versioned immutable `CanonicalExpression`, `CanonicalState`, `CanonicalAction`, transitions/trajectories, canonical JSON and hashes. Truth container; not a renderer. |
| `arena/tasks/generators/world_v0.py` | `build_world_v0`; deterministic 13-domain task generation and independent domain-template verification. Produces Gold/Silver/Reject trajectories. |
| `arena/genome/genes.py`, `schema.py`, `seeds.py` | Gene enums, `LanguageGenome`, stable candidate identity, and eight permanent seeds. Defines the controlled representation search space. |
| `arena/genome/mutation.py`, `crossover.py` | Deterministic proposal mechanisms and history. V1/V2 use one-gene children only; crossover is implemented but not used here. |
| `arena/languages/phenotype.py` | `GenomePhenotypeLanguage`; reversible genome-driven state and action-option codec plus generated acquisition guide. |
| `arena/compiler/projection.py` | Removes oracle action pools/usefulness before solver observation. `assert_no_answer_leakage` guards projections. |
| `arena/experiments/fitness_v1.py` | Frozen V1 population, Gate 0, split, A/B prompt, and 24-candidate roster. Historical; do not modify. |
| `arena/experiments/model_fitness.py` | Frozen V1 Ollama runner and invalidation audit. Historical; do not reuse its observations in V2. |
| `arena/experiments/fitness_v2.py` | V2 pair derivation, independent bounded oracle, validators, protocol/model qualification, frozen runtime, calibration/Tier gates, task cache, and status. |
| `arena/players/solver.py` | Solver request/response contract; representation consumer, never truth authority. |
| `arena/players/architect.py` | Proposes controlled genomes/candidates using observations permitted by the protocol. Must not inspect hidden PROMOTION/OOD outcomes. |
| `arena/players/refuter.py` | Searches for semantic failures/counterexamples and stores minimized failures. |
| `arena/players/curriculum.py`, `arena/tasks/curriculum.py` | Disagreement/information-oriented task selection without relabeling truth. |
| `arena/league/*` | Multi-objective match registry, selection, and persistent Hall of Fame. No scalar Elo determines scientific truth. |
| `arena/surrogate/*` | Optional calibrated sklearn surrogate plus deterministic fallback. It predicts expensive observations; it does not replace them. |
| `arena/verifier/native.py` | Structural/type/scope/partiality/evidence/transition checks. Important limitation: it does not prove arbitrary mathematical answer correctness by itself. |
| `arena/verifier/{sympy,z3,numeric,lean_adapter,differential}.py` | External/differential backends and disagreement handling. Unrun checks are never reported as proof. |
| `arena/assurance/*` | Exhaustive bounded cases, fuzz/properties, side-channel checks, reducers, and fail-closed release suite. |
| `arena/evaluation/landscape.py` | Paired comparison, exact McNemar, clustered bootstrap, correlations, gene consistency, ruggedness, and rank stability. |
| `arena/training/matched_adaptation.py`, `render_dataset.py`, `evaluation.py` | Contracts and statistics for matched training. No runnable V2 1K trainer is implemented or authorized. |
| `arena/storage/db.py`, `artifacts.py` | SQLite control plane and content-hashed artifact writing. Model-call caches are separate and ignored by Git. |
| `arena/cli.py` | Existing Arena world, candidate, league, assurance, status, and legacy V1 commands. V2 commands currently use the module CLI documented below. |
| `arena/reporting.py` | Scoreboard/status/report generation; generated summaries never supersede raw task rows. |

## 4. Canonical world

Schema version: `arena-canonical-v0.1.0`. World ID: `arena-world-v0`. Generation is deterministic
at seed 0. There are 676 trajectories: 52 in each of arithmetic, algebra, logic, binding, sets,
probability, statistics, calculus, linear algebra, physical dimensions, optimization, partial
operations, and reasoning evidence. Quality counts are 520 Gold, 104 Silver, 52 Reject.

Hashes recomputed at this handoff:

- all-task artifact hash: `5c6179159b77c323bca7c37609a724d0cbe1301debd23475892786aafca5085a`;
- all-trajectory truth hash: `424e416a13c4843ed4d13a53f98d3d840668644acbebb08094b1541d0e407550`;
- Gold-task hash: `df056956c92964abe9ac53ec98c09fb08c3701787a8eefab9aba1e365989ffe4`.

A state contains objects, bindings, assumptions, established facts, propositions, one goal,
obligations, evidence dependencies, local scopes, legal actions, plausible-invalid actions,
terminal status, and nonmathematical execution metadata. An action contains its operation,
targets, arguments, warrant, preconditions, generated obligations, and evaluation-only
usefulness. Model projections remove action membership and usefulness when those fields would
leak the answer.

Gold means native checks and the independently accepted deterministic domain-template replay
both ran. Silver means structural/native evidence exists but the independent check is unknown.
Reject contains a planted/refuted answer. Every initial world state has one intended legal and
one tempting invalid action; independent expected-versus-observed expression hashes determine
Gold/Reject. V2 adds its own explicit bounded oracle because `NativeVerifier` alone cannot prove
arbitrary answer mathematics.

Frozen items include schema semantics, world generator seed/logic, task identities, oracle,
quality meanings, and V1/V2 manifests. Changing any after model calls invalidates affected
experiments and requires a new version. Display-only execution metadata does not change
`mathematical_hash`; changing mathematical fields does.

## 5. Language population

Eight permanent seeds and genome hashes:

| Seed | Representation | Genome hash |
|---|---|---|
| `L0_STRUCTURED_ENGLISH` | explicit labelled-linear, wordlike, high redundancy | `9823d4955c8416811632af0656518e84a9e23bc513cc9ce7a037e33c955c0d2f` |
| `L1_CURRENT_HML` | compatibility-only hybrid symbolic/tree HML control | `d888b38a320d50c2c144d779dfb3aa252621e9add8671788d6d885ef4fb0a84e` |
| `L2_SEXPR` | typed structural S-expression | `4e77c1921fd1f7d4a3b982596e3905733c654f19361e9e3a1f241a12e8a080c2` |
| `L3_JSON_AST` | explicit typed JSON AST | `18e8dd1e64954dfc3531b6486b10d1f86a03a1c6b00cb0224acd9054ccb8b9db` |
| `L4_TYPED_PREFIX` | explicit typed prefix/tree | `fa7ff2917e9625153f55f55331ded6da58e848d013223525318a582def6d1380` |
| `L5_COMPACT_SYMBOLIC` | compact symbolic code | `a2990983e8ae6f8316b21766b198d4422b78ee6bfad5a547826fae096fc880e5` |
| `L6_GRAPH_TRIPLES` | graph-oriented structural-role representation | `76505d77699754d9c28e5585537bb0fce19c60a270519d9d55a6dc91bee2ac5b` |
| `L7_HYBRID_ROLE_LABELLED` | hybrid role-labelled tree | `153580895946a29ae469358ec5a16736f861b23fcae805680729461f7015c063` |

The full genome has 14 families. Fitness V1 mutates eight presentation axes one at a time:
grammar, binders, types, state organization, actions, serialization, morphology, and redundancy.
It deterministically materialized 15 children per parent, 120 total, with no crossover.
Stored population hash:
`815efcc2d913e7338915b1ed656537a9acf8ec85021f53e2810648c2c7a3c075`.
All 120 passed Gate 0 over 1,040 Gold states each: 124,800 roundtrips, zero collisions, zero dead
phenotypes.

`L5_COMPACT_SYMBOLIC` is not a winner. Its demonstrated property is static compactness. No V2
Tier 2A candidate call was made, so no model-fitness claim exists for L5 or any mutant.

## 6. Soundness

Gate 0 requires lossless render/parse identity against canonical states, absence of canonical
collisions, valid genome dependencies, and fail-closed outcomes. The verifier checks duplicate
IDs, unbound variables/scopes, evidence graphs, partial-operation definedness, arities/types,
matrix shapes, probability roles, exactness laundering, action targets, legal transition action,
obligation disappearance, and goal laundering.

Current assurance evidence before this continuation was preserved:

- 120/120 V1 mutation phenotypes survive Gate 0;
- 0 canonical collisions and 0 known critical semantic defects;
- 0 false accepts in the Refuter suite;
- 2,767/2,767 bounded exhaustive cases pass;
- 0/9 unresolved differential disagreements;
- fuzz/property, malformed-input, duplicate-key/ID, side-channel, reducer, and external-verifier
  tests pass.

V2 additionally validates all 288 derived states, 48 oracle inversions, unique positive options,
negative-twin information identity, position swap identity, neutral display IDs, and empty oracle
action pools. Its manifest hash is
`08ce4d637dc1049d827545922e72c92ae36939d3bdf1a178a13d44ff9974847a`.

"0 known defects" is bounded evidence, not a universal proof of correctness. Release language
must say exactly that. New semantics, unverified adapters, unresolved differential disagreement,
or a false accept blocks R* release.

## 7. Cross-repository reuse

Read `docs/REUSE_SUMMARY_FOR_CLAUDE.md` for the repository-by-repository account of what existed,
what was adapted, what was refused, exact paths, destinations, classifications, and tests.
Machine records are under `artifacts/reuse/`.

Exact primary historical states:

- `MoheetBrain/HML_V3`, `codex/open-ended-search-v2`,
  `4395a8c717a334be58b29d53b43c0c842d0e03ac`: failure memory, one-axis search,
  counterfactual and calibration lessons.
- `MoheetBrain/hml-reasoning-corpus`, `claude/max-ev-representation-experiment-v1`,
  `bf2cd75a0676afdb73ab15fe5963cb6138e27060`: 5,619-row corpus, group splits, paired
  statistics, common-envelope and Unicode failure evidence.
- `MoheetBrain/hml-reasoning-corpus`, `codex/reasoning-layer-discovery`,
  `8d7cc1d99dc6748fd4d6dac174d251671d403678`: representation/truth separation.
- `MoheetBrain/hml-standard`, `main`,
  `e879f5f5fe55ad2dc4ab15eb1c10a15de91aa59c`: terminology and conformance reference.
- `MoheetBrain/hamiltonian-lang`, `codex/final-hml-signal`,
  `273a5145fb4128daf37493de396126aa8cc84d97`: executable experiment history, common
  envelope, position/projection failures, soundness exploit memory.
- `MoheetBrain/hamiltonian-lang`, `feature/hml-reasoning-kernel-v2`,
  `3b7fe893609c2ce39c8088c1cb0c3fe2e45d6af4`: historical executable semantic kernel.

The authority split is: Arena is truth here; `hamiltonian-lang` is historical executable HML;
`hml-standard` is documentation; `hml-reasoning-corpus` is empirical method/data;
`HML_V3` is later experimental work. Reused mechanisms include controlled mutations,
model-visible information audits, common envelopes, group splitting, paired statistics,
relation-destroyed controls, semantic-role transposition, and failure regressions. Deferred
assets include the historical corpora, richer semantic kernel, and broad V3 compiler.

Old model scores cannot be pooled because models, prompts, schemas, oracles, tasks, exposure,
and response protocols differ. The 5,619 rows remain DEV/import-test candidates pending a
proved adapter; they are not hidden Arena evidence.

## 8. Experiment V1

Experiment: `arena-representation-fitness-v1`. Model: `gemma3:4b`; Ollama list digest
`a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`; model blob SHA-256
`aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25`; GGUF Q4_K_M;
Ollama 0.33.2; context 8192; temperature 0; seed 20260905; completion limit 32; top-k 64;
top-p 0.95. Response protocol was strict JSON A/B next-action choice.

V1 split hash: `1f0092338d0c93aaaf92ad2ac3ae906c20c783c2365a8602fc5e50ea76a46717`.
Partitions: DEV 160, SCOUT 120, PROMOTION 160, structural OOD 80. Calibration used 16 DEV
tasks per permanent control, 64 cells total.

Raw outcome summary: Structured English 7/16 and A on 16/16; current HML 7/16 and A on 16/16;
S-expression 5/16 and mostly A; JSON AST 3/16 with six malformed. Always A was 7/16; always B
was 9/16. No control beat the best position policy. Exact decision:
`MODEL_FITNESS_BENCHMARK_INVALID`. Tier 2A, Tier 2B, and matched adaptation were not run.

This says the selected player/interface did not demonstrate mathematical reading. It does not
say Arena failed, HML failed, representations have no fitness, or the underlying hypothesis is
false.

## 9. Fitness V2

Experiment: `arena-representation-fitness-v2`; instrument:
`arena-semantic-counterfactual-instrument-v2.0.0`. Full design and commands are in
`docs/MODEL_FITNESS_EXPERIMENT_V2.md`.

Key content identities: probe-manifest logical hash
`08ce4d637dc1049d827545922e72c92ae36939d3bdf1a178a13d44ff9974847a` (file SHA-256
`851cba9f566f42071b05f8242dc6e4ac1b406330fdf288ab58afa8d4907453e7`), protocol-selection
logical hash `7d00d5a1a466aa9465719757acaad5b46093ca9faa0655344ca8a870c3363aca`, model-qualification
logical hash `3b9f5ba85a219026676fa092e17d4fa40bee2da70ed92abc23432dde4b3a970a`, and final decision
logical hash `cb596ccecf43288050989e5d36a495d9c8eef4de6a2491faab093ba2c1f6c3e2`. The primary
runtime-config hash is `9e82b40f7a0a55259278862cca9fc7ca2148e6a84fa8271c8f247978e46dfcd4`.
Calibration result file SHA-256 is
`f01434890846bc84fa6a57541a2eb43dfb965efc6baa8a89a39ba2e5d4654616`; primary row file
SHA-256 is `450b19823286058f71e0701f79ea1824205145999ca7b600654457746c72ff23`;
decision file SHA-256 is `c914612010dd675590a52bfda1b9427a947009ccea66497379eb60d490aa26b6`.
These artifacts are governed by pre-candidate freeze commit
`99c877f22e0c283be56bb369af3101019625c215` and the manifest/qualification identities above.

Each source yields original/counterfactual positive probes with correct semantic options 0/1,
two information-identical relation-destroyed probes with incompatible balanced control targets,
and two option-order swaps. Q0 is trivial protocol copying. Q1 positive reading spans binders,
sets, statistics, optimization and held-out domain mechanisms. Q2 destroys the decisive
relation. Metrics include exact response validity, Q1/Q2, gap, constant baseline, semantic flip
consistency, choice flip rate, position invariance/preference, malformed rate, tokens, and
latency.

Four DEV protocols were tested with gemma3:4b: JSON A/B, canonical answer, JSON P/Q, and opaque
action key. JSON A/B was selected before model qualification: Q0 100%, Q1 62.5%, gap +12.5,
flip 25%, zero malformed. It was the best interface pilot, not a model pass.

Qualification thresholds were Q0 ≥95%, Q1 ≥70%, Q1 at least 15 points above constant, flip
consistency ≥60%, Q1-Q2 ≥15 points, and no position above 85%. The model ladder:

| Model | Q0 | Q1 | Q2 | Gap | Flip | Qualified |
|---|---:|---:|---:|---:|---:|---|
| gemma3:4b | 100% | 43.75% | 50% | -6.25 | 0% | no |
| gemma4:e4b 8B | 100% | 68.75% | 50% | +18.75 | 37.5% | no |
| gemma4:12b | 100% | 100% | 50% | +50 | 100% | yes |

Selected model digest:
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`.
Frozen runtime: Ollama, 8192 context, temperature 0, seed 20260905, 64 output tokens, top-k 64,
top-p 0.95, `think=false`. An 8B default-thinking pilot exhausted its output budget; it is
preserved and excluded. Raw audit showed exact schema-only outputs and no obvious shortcut.

Fresh post-freeze calibration used 192 cells. Results:

| Control | Q1 | Q2 | Gap | Flip | Position invariance | Qualified |
|---|---:|---:|---:|---:|---:|---|
| Structured English | 87.5% | 50% | +37.5 | 75% | 75% | yes |
| current HML | 75% | 50% | +25 | 50% | 75% | no |
| S-expression | 81.25% | 50% | +31.25 | 62.5% | 81.25% | yes |
| JSON AST | 87.5% | 50% | +37.5 | 75% | 75% | yes |

The instrument is qualified. Calibration verdict:
`FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM`: Q1 range 12.5 points versus frozen required 15.
Tier 2A, Tier 2B, matched 1K, landscape inference, and R* are **NOT RUN/NONE**. No mutant or
hidden result was observed.

## 10. Scientific firewall

Glossary: DEV means visible development material; SCOUT is the first candidate-comparison
stage; PROMOTION is a fresh hidden confirmation stage; OOD means out-of-distribution by held-out
domain/structure. GGUF is the local model-file format used by Ollama. `RSTAR_BLOCKED` means an
R* candidate failed or has not reached a mandatory gate; `RSTAR_V0_CANDIDATE_READY` means it may
enter release assurance, not that it is released.

- **DEV:** `PROTOCOL_DEV`, `MODEL_QUALIFICATION`, and `CALIBRATION_DEV`; all are spent engineering
  or control-calibration material. Historical adapted data, if ever admitted, stays here.
- **SCOUT:** `TIER2A_SCOUT`; frozen source IDs exist but no model outcomes were requested.
- **PROMOTION:** `TIER2B_PROMOTION`; hidden and untouched.
- **OOD:** V1 structural/domain OOD and V2 OOD; hidden and untouched.
- **Assurance-only:** malformed/fuzz/exhaustive/refuter/differential counterexamples; never
  leaderboard training examples.
- **Historical exposure:** all four external repository datasets/results and every V2 DEV source.

V1 group key is `domain|operation`; groups never cross partitions. V2 source IDs never repeat
across slices and inherit their upstream V1 partition. Candidate comparison changes only
lossless state/option rendering. The common envelope, question, response schema, parser,
scorer, model, runtime, task order, and semantic information remain fixed. Candidate guides are
generated mechanically from genomes; no candidate-specific teaching is allowed.

Cache identity includes experiment/instrument, full model digest, runtime hash, protocol,
candidate/genome hash, slice, probe/derived hash, and prompt hash. Cache namespaces are V1/V2
separate. Malformed and error rows stay in denominators. PROMOTION/OOD cannot redesign a
candidate or prompt. Architect sees SCOUT summaries only after a gate authorizes them.

## 11. Statistics

Every candidate comparison is task-paired on the same probe IDs. For candidates A and B,
`n10` counts A-correct/B-wrong and `n01` counts B-correct/A-wrong. Exact McNemar uses the
two-sided binomial tail on only discordant pairs. The clustered bootstrap resamples whole
mechanism/domain groups so siblings or repeated templates are not treated as independent.
Report effect size, interval, discordances, and raw denominators; `p < .05` alone is not a
developmental decision rule because sample size, practical magnitude, stability, cost, and
falsifiers matter.

Candidate ordering uses predeclared lexicographic fields, not post-hoc scalar reward. Pareto
treatment preserves correctness, semantic survival, cost/latency, and other objectives rather
than pretending they are interchangeable.

Landscape metrics in `arena/evaluation/landscape.py` mean:

- valid-neighbor rate = Gate-0 survivors / proposals;
- beneficial-mutation rate = qualifying positive child deltas subject to promotion/cost guards;
- parent-child correlation = Pearson correlation of paired parent and child fitness;
- gene-effect consistency = fraction of repeated mutations sharing the dominant delta direction;
- ruggedness = mean/median/max absolute neighbor delta;
- rank stability = Spearman Scout-versus-Promotion rank correlation;
- static/model correlation = Spearman token cost versus Promotion fitness.

No V2 landscape metrics exist because Tier 2A was not authorized. Do not infer them from the
four calibration controls.

## 12. Model and compute

Installed local inventory at 2026-09-05 (no downloads):

| Model | Full digest | Parameters | Quantization | Size |
|---|---|---:|---|---:|
| `gemma3:4b` | `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` | 4.3B | Q4_K_M | 3.3 GB |
| `gemma4:e4b` | `c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb` | 8.0B | Q4_K_M | 9.6 GB |
| `gemma4:12b` | `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` | 11.9B | Q4_K_M | 7.6 GB |
| `gemma4:31b` | `6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7` | 31.3B | Q4_K_M | 19.9 GB |
| `qwen38-rvn:latest` | `25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae` | 27.3B | Q4_K_M | 16.8 GB |
| `qwen38-huihui:latest` | `4852447c7bdfd10454e14154168f2acdc1f057e2b90f401285b8d6be10c0596a` | 27.3B | Q6_K | 24.9 GB |
| `qwen36-huihui:latest` | `53a7c5ba0d2a085ae6363f32ff854dbaf0663c02931203ff46c8c0cb923e66db` | 35.5B | Q6_K | 29.2 GB |

Accepted V2 evidence contains 176 logical protocol-DEV cells, 204 logical final ladder cells
(68/model), and 192 calibration cells: 572 total. The preserved invalid 8B thinking pilot adds
68 excluded cells. An earlier pre-runtime-hash gemma3 qualification pilot was rerun under the
frozen identity and is excluded. Cache hits mean logical cells and physical generation requests
are not identical; use each artifact's row-level `cache_hit` field for exact accounting.

gemma3:4b was insufficient in V1 because it never demonstrated state reading; V2 independently
confirmed 0% qualification flip consistency. Gemma 4 12B is the smallest installed model that
passed all gates, so 31B/Qwen models were not spent. Current compute is local CPU/GPU-memory
bound Ollama inference; prompt lengths vary materially by representation and are retained as
outcomes.

## 13. Artifact map

| Artifact | Path | Purpose | Authoritative? | Generated? | Committed? | When to read |
|---|---|---|---|---|---|---|
| This handoff | `docs/CLAUDE_HANDOFF.md` | Complete continuation state | yes | no | yes | first |
| V2 design | `docs/MODEL_FITNESS_EXPERIMENT_V2.md` | Frozen protocol, gates, actual result | yes | no | yes | before V2 work |
| Reuse summary | `docs/REUSE_SUMMARY_FOR_CLAUDE.md` | Human cross-repo decisions | yes | no | yes | before imports |
| Machine reuse inventory | `artifacts/reuse/cross_repo_assets.json` | Asset-level provenance/decision | yes | yes | yes | before imports |
| Reuse conflicts | `artifacts/reuse/conflicts.json` | Resolved authority/evidence conflicts | yes | yes | yes | when claims conflict |
| Reuse provenance | `artifacts/reuse/provenance.jsonl` | Transformation records | yes | yes | yes | audit |
| V2 probe manifest | `artifacts/experiments/fitness_v2/probe_manifest.json` | All states/options/oracles/splits/hashes | yes | yes | yes | reproduce instrument |
| Protocol selection | `artifacts/experiments/fitness_v2/protocol_selection.json` | Four DEV protocols and decision | yes | yes | yes | inspect interface choice |
| Model inventory | `artifacts/experiments/fitness_v2/model_inventory.json` | Installed model digests/sizes | snapshot | yes | yes | model ladder |
| Qualification summary | `artifacts/experiments/fitness_v2/model_qualification.json` | Ladder, thresholds, selected model | yes | yes | yes | before model calls |
| Qualification rows | `artifacts/experiments/fitness_v2/qualification/*.json` | Q0/Q1/Q2 raw outputs and metrics | yes | yes | yes | forensic audit |
| V2 calibration result | `artifacts/experiments/fitness_v2/calibration/result.json` | Gate result and summaries | yes | yes | yes | current decision |
| V2 calibration rows | `artifacts/experiments/fitness_v2/calibration/task_rows.jsonl` | Every task-level outcome | yes, primary | yes | yes | analysis/reanalysis |
| V2 decision | `artifacts/experiments/fitness_v2/experiment_decision.json` | Sentinel and downstream non-run status | yes | yes | yes | automation/status |
| V2 report JSON/CSV/MD | `artifacts/reports/fitness-v2-calibration.*` | Human/machine summaries | derivative | yes | yes | quick review |
| V2 cache | `artifacts/cache/fitness_v2/*.json` | Task-level resumability and raw runtime metadata | operational primary | yes | no, ignored | reruns/forensics |
| V1 population | `artifacts/experiments/fitness_v1/candidate_population.json` | 120 frozen children | yes for V1/V2 roster | yes | yes | candidate identity |
| V1 Gate 0 | `artifacts/experiments/fitness_v1/gate0.json` | 120-survivor evidence | yes | yes | yes | semantic admission |
| V1 split | `artifacts/experiments/fitness_v1/task_split.json` | DEV/SCOUT/PROMOTION/OOD firewall | yes | yes | yes | any model experiment |
| V1 calibration/decision | `artifacts/reports/fitness-calibration.*`, `experiment-decision.json` | Preserved invalid benchmark | yes historical | yes | yes | avoid repeating failure |
| World records | `artifacts/worlds/arena-world-v0.jsonl`, summary JSON | Frozen generated world | yes | yes | yes | oracle/task audit |
| SQLite | `artifacts/arena.db` | Runtime control plane | operational | yes | intentionally uncommitted/ignored | local CLI state |
| Scoreboards/matches | `artifacts/reports/scoreboard.*`, `artifacts/matches/*` | Existing static/league state | derivative | yes | yes | architecture context only |
| Tier 2A/B artifacts | `artifacts/experiments/fitness_v2/tier2a/`, `tier2b/` | Would hold raw outcomes/results | absent | yes if run | no | do not create until gated |

## 14. Exact commands

Run from repository root. The project supports Python 3.12 or newer. This continuation was
actually validated with `.venv/bin/python` 3.14.7. Reproduce the checked environment with the
same interpreter when available; a minimum-version setup is:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Verification:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy arena
.venv/bin/arena worlds validate
.venv/bin/arena assure L5_COMPACT_SYMBOLIC
```

World, population, Gate 0, and V1 status:

```bash
.venv/bin/arena worlds build --count 676 --seed 0
.venv/bin/arena mutations materialize
.venv/bin/arena fitness decision
.venv/bin/arena experiment status
```

V2 instrument/model commands:

```bash
.venv/bin/python -m arena.experiments.fitness_v2 materialize --root .
.venv/bin/python -m arena.experiments.fitness_v2 qualify --root . \
  --model gemma4:12b \
  --model-digest 4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c \
  --protocol JSON_AB --slice MODEL_QUALIFICATION
.venv/bin/python -m arena.experiments.fitness_v2 calibrate --root .
.venv/bin/python -m arena.experiments.fitness_v2 status --root .
```

`calibrate` is cache-resumable and reproduces the current insufficient-headroom verdict. Do not
run `tier2a` now; it exists and fails closed because calibration did not authorize it. If a new
versioned DEV calibration later authorizes it, existing exact commands are:

```bash
.venv/bin/python -m arena.experiments.fitness_v2 tier2a --root .
.venv/bin/python -m arena.experiments.fitness_v2 tier2b --root .
.venv/bin/arena landscape report
```

There is no runnable V2 matched-1K adaptation command. `.venv/bin/arena training scout
--examples 1000` intentionally refuses while the representation-signal gate is closed. Do not
claim matched training is available. Release assurance exists through `arena assure`, but no
R* candidate exists to submit.

## 15. Known failure modes

| Failure | What happened / why it matters | Current guard |
|---|---|---|
| Unequal prompt envelopes | Earlier HML advantage reversed under equal scaffolding; measured teaching, not representation | common fixed envelope; generated guides; prompt hashes |
| Literal Unicode escape confound | A 50K run put literal `\\uXXXX` only in HML payloads | decoded-prompt/serialization audits and information-equality tests |
| Constant answer position | V1 gemma3 chose A regardless of state | exact balance, semantic flip consistency, negative twins, swap diagnostics |
| Re-sorted options | Audit assumptions no longer matched actual presentation | probe manifest stores order/expected index; derived prompt hash |
| Distant calibration header | Model ignored relation information far from the question | relation is in the model-visible state; raw audit; positive-versus-destroyed gap |
| Minimal-pair saturation | Prior probes scored 0.96–0.99 and could not discriminate | reading validity first, then explicit headroom gate; current gate stopped at 12.5-point range |
| False static locality | Line-count metric rewarded formatting artifacts | character/token distance and measured prompt tokens |
| Compression called quality | Compact L5 looked efficient without model evidence | multi-objective Pareto treatment; no winner without hidden model results |
| Flat S-expression corruption blindness | Some record-order mutations preserved a misleading flat view | canonical roundtrip plus structural/semantic and model-visible checks |
| Task leakage | Identifiers/action pools can encode answers or expose held-out material | neutral display ID, empty action pools, source-disjoint split manifest |
| Candidate-specific teaching | Hand-tuned guides can manufacture a winner | mechanically generated guide and fixed envelope |
| Ceiling/floor | Aggregate accuracy can be uninformative | explicit Q0/Q1/Q2, calibration ladder, and frozen headroom gate |
| Malformed dropping | Removing failed rows inflates scores | exact parser; malformed rows remain incorrect in every denominator |
| Post-hoc scorer change | Threshold/scorer tuning after outcomes Goodharts the result | pre-candidate commit `99c877f...`; version bump required for changes |
| Source-only roundtrip | A historical model view omitted decisive relations despite codec tests | V2 validates rendered-information behavior with negative twins and oracle action stripping |
| Hidden thinking exhausts output | 8B returned empty output after 64 hidden-thinking tokens | frozen `think=false`, runtime hash in cache identity, invalid pilot preserved |

## 16. Do not do

- DO NOT crown HML.
- DO NOT crown L5 because it is compact.
- DO NOT import old model scores as new evidence.
- DO NOT change frozen truth after model calls without invalidating/versioning the run.
- DO NOT lower the 15-point calibration headroom threshold after observing 12.5 points.
- DO NOT run Tier 2A by editing its gate or fabricating authorization.
- DO NOT generate 1M trajectories yet.
- DO NOT activate full self-play before a stable model-fitness signal exists.
- DO NOT hide malformed outputs or errors.
- DO NOT tune prompts candidate by candidate.
- DO NOT optimize against PROMOTION/OOD.
- DO NOT equate zero known semantic bugs with universal zero error.
- DO NOT interpret benchmark invalidity or insufficient headroom as hypothesis falsification.
- DO NOT use `NativeVerifier` alone as proof that a counterfactual answer is mathematically true.

## 17. Open questions, in priority order

| Question | Why it matters | Current evidence | Cheapest discriminating experiment | Decision threshold | Consequence |
|---|---|---|---|---|---|
| Can calibration provide useful representation headroom? | Candidate effects cannot be resolved on a narrow/near-ceiling control range | Instrument valid; range 12.5pp vs frozen 15pp | Build a versioned harder DEV-only pair slice, validate/freeze, rerun four controls | ≥15pp range, ≥1 qualified control, min Q1 ≤85% | pass → Tier 2A; fail → measurement redesign |
| Which local model can read state? | Solver failure must not masquerade as language failure | Gemma 4 12B passed all gates; smaller two failed | No more model work now; only retest if instrument version changes materially | all six qualification checks | pass → calibration; fail → next installed rung |
| Does representation fitness exist? | Core thesis | No V2 candidate comparison exists | Gated 24-candidate Tier 2A on fresh SCOUT | frozen range/edge/valid-response signal rule | signal → assess searchability; none → stop/diagnose |
| Is the landscape locally searchable? | Determines mutation versus broader search | 120 sound neighbors; no model fitness | Parent-child paired Tier 2A deltas | ≥2 large edges plus reproducible structure | local → Tier 2B; rugged → change search strategy |
| Do gene effects replicate across parents? | A one-off child win is not a causal gene effect | Not measured | same one-gene change across multiple parents | directional consistency with paired uncertainty | consistent → targeted mutation; inconsistent → contextual model |
| Does rank survive fresh PROMOTION? | Scout winner may be noise | Not run | 8-candidate Tier 2B only if authorized | Spearman ≥0.60 plus paired evidence | stable → matched 1K; collapse → stop |
| Does matched adaptation preserve differences? | Inference readability need not imply learnability | Contracts only | matched 1K, same base/data/optimizer, fresh PROMOTION/OOD | predeclared accuracy/token/GPU-hour advantage | advantage → release assurance; none → weaken thesis |
| Does any custom candidate beat generic AST/SE? | Custom language must justify complexity | Calibration is not candidate evidence | Tier 2A/B with permanent controls | stable paired advantage without regressions | yes → possible R*; no → prefer generic control |

## 18. Exact next decision tree

```text
CURRENT: FITNESS_V2_INSTRUMENT_QUALIFIED
    |
    v
versioned harder DEV calibration (do not touch SCOUT/PROMOTION/OOD)
    |
    +-- no model/control qualifies
    |      -> measurement/model redesign; no candidate calls
    |
    +-- valid reading but insufficient headroom/ceiling
    |      -> redesign DEV difficulty again; no candidate calls
    |
    +-- valid reading + frozen useful headroom
           -> commit new freeze
           -> Tier 2A: 24 candidates on fresh SCOUT
                 |
                 +-- no reproducible signal
                 |      -> STOP; NO_MEASURABLE_REPRESENTATION_FITNESS_SIGNAL
                 |
                 +-- signal is rugged/nonlocal
                 |      -> STOP local mutation; redesign search strategy
                 |
                 +-- searchable signal
                        -> choose 8 by frozen promotion rule
                        -> Tier 2B on fresh PROMOTION
                              |
                              +-- rank collapse / unstable effects
                              |      -> STOP and diagnose
                              |
                              +-- stable rank and paired effects
                                     -> implement + freeze matched 1K
                                           |
                                           +-- controls dominate/no stable gain
                                           |      -> no R*; weaken specialized-language thesis
                                           |
                                           +-- custom candidate wins per example,
                                               training token, and GPU-hour
                                                  -> fresh PROMOTION/OOD
                                                  -> release assurance
                                                        |
                                                        +-- any critical failure/regression
                                                        |      -> RSTAR_BLOCKED
                                                        |
                                                        +-- all gates pass
                                                               -> RSTAR_V0_CANDIDATE_READY
```

The immediate next action is deliberately narrow: create a harder, versioned DEV calibration
slice using unseen DEV source IDs or a fully verified historical adapter; validate its oracle
and information equality; freeze it in a new commit; rerun only the four controls. Do not reuse
the current calibration cells as new observations or inspect SCOUT/PROMOTION/OOD.

## 19. Current sentinel

Exact sentinel: **FITNESS_V2_INSTRUMENT_QUALIFIED**.

Meaning: the JSON A/B response interface plus Gemma 4 12B demonstrably reads decisive
mathematical relations (100% qualification Q1, 100% flip consistency, Q2 50%), and fresh
calibration replicates semantic information use in three controls. It does not authorize Tier
2A because the frozen control-headroom range was 12.5 rather than 15 percentage points.

Tier 2A: NOT RUN. Tier 2B: NOT RUN. Matched training: NOT RUN. Representation landscape: NOT
MEASURED. R*: NONE.

A fresh read-only reviewer with no inherited conversation audited this handoff after drafting.
It confirmed all 19 sections, both sentinels, V2 counts/outcomes, commands, and paths; it flagged
recoverability, authority precedence, artifact/runtime identities, reuse traceability,
Python-version accuracy, and unexplained acronyms. Those findings were corrected before the
final tracked commit. The final Git/status checks below are the recoverability proof.

# FITNESS_V2_INSTRUMENT_QUALIFIED
