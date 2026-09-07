# Hamiltonian Arena Phase 3 — Final GPT Handoff

> **HISTORICAL DOCUMENT — SUPERSEDED.** This is the Phase 3 / Fitness V3 handoff; its
> `EXPERIMENT_INVALID` verdict remains correct **for V3**. The current project sentinel is
> `FITNESS_V4_NOT_QUALIFIED`; see `docs/CLAUDE_FINAL_HANDOFF.md`.

Read this first if you have no conversation context. It is the operational and scientific
handoff for the Phase 3 representation-fitness continuation completed on 2026-09-06.

## 1. Bottom line

Phase 3 successfully separated immutable canonical truth from an evolvable, content-bearing
model-view genome; implemented the first six truth-derived content axes with independent
recomputation and information accounting; built a new structural Fitness V3 instrument; ran
DEV qualification; froze it before candidate calls; and completed a 12-founder tournament.

The final scientific outcome is `EXPERIMENT_INVALID`.

The reason is precise. V3's preregistered aggregate qualification checks passed, but the
founder mechanism audit showed that aggregate accuracy pooled five 100%-ceiling mechanisms
with one 0%-floor mechanism. This violates the governing no-ceiling/no-floor requirement.
Compact symbolic solved the two state-delta positives that JSON missed, but 2 paired wins and
0 losses give one-sided exact sign p=.25, miss the frozen four-net-win rule, and do not survive
Holm correction. No candidate was promoted. No mutation campaign, matched adaptation, or R*
release is authorized.

Do not reinterpret the invalidation as evidence that representations are equivalent. It says
this instrument cannot support the desired inference.

## 2. Repository state and commit chain

- Repository: `https://github.com/MoheetBrain/hamiltonian_chess.git`
- Local path: `/Users/moheet/Documents/ChatGPT/hamiltonian_chess`
- Branch: `codex/arena-v0-fitness`
- V3 qualified/frozen commit:
  `96166546ab5f0add41f7cf3b6ef58657c1f97747`
- V3 founder-result/invalidation commit:
  `b85f98fe9400e72af7ffd58435b6e07e70ce2819`
- The commit containing this file is the final documentation/check commit; use
  `git rev-parse HEAD` because a commit cannot contain its own hash.

Important history, in order:

| SHA | Meaning |
|---|---|
| `c1dd586db6abb9bd4e72f0048122eb4ddca98739` | Arena v0 architecture, canonical world, eight seeds, assurance |
| `f17bb0f73ac942d43b614704e54c019a64284368` | Fitness V1 preregistration |
| `11b73ae6756fa02984b3fecedab117d14ce0a26a` | V1 cached calibration runner |
| `22cab970862ee80cd30ce42b2d885ef52e73b47c` | V1 invalid position-policy stop |
| `99c877f22e0c283be56b369af3101019625c215` | V2 qualified instrument freeze |
| `bf8838b20e35b1daa9052ab964495397db202506` | Separate A100 matched sprint; `WEAK_CONTINUE`, saturation |
| `983298279c058ec67a94b564e6d983423f624612` | V2 calibration result and handoff |
| `a4f7d7f340cd3c4a915d04f19951160c58b49642` | Concurrent fail-closed empty matched-arm fix |
| `96166546ab5f0add41f7cf3b6ef58657c1f97747` | Phase 3 architecture and V3 frozen before founders |
| `b85f98fe9400e72af7ffd58435b6e07e70ce2819` | Founder results and explicit V3 invalidation |

The concurrent `a4f7d7f` commit landed while Phase 3 was starting and is an ancestor of the V3
freeze. Its changes were preserved. Formatting and typing defects in the concurrent sprint
scripts were repaired as part of the V3 freeze; their historical experiment outputs were not
rewritten.

## 3. Governing objective

`GOAL.md` now defines the programme as discovering and validating an AI-native universal
mathematical representation and reasoning protocol R* that improves verified reasoning,
search, learning, and generalization without allowing representation code to own truth.
Current HML, JSON AST, compact symbolic, and every mutation are hypotheses. R* remains withheld.

The authority order is:

1. immutable canonical records and independent verification/oracle records;
2. executable frozen experiment code and committed manifests;
3. raw per-probe rows;
4. derived decision artifacts;
5. reports and this narrative handoff.

If layers disagree, preserve them, stop, and open a new experiment version. Do not repair old
evidence in place.

## 4. Historical V1, V2, and matched-sprint evidence

V1 used Gemma 3 4B and failed because the model selected option A rather than reading the
state. Its final state was `MODEL_FITNESS_BENCHMARK_INVALID`; no V1 candidate inference is
valid.

V2 created 48 counterfactual families / 288 probes. Local Gemma 4 12B qualified at Q0 100%,
Q1 100%, Q2 50%, semantic flip 100%. After the instrument was frozen, the four permanent
controls scored positive accuracy .875, .75, .8125, and .875. The 12.5-point range missed V2's
precommitted 15-point headroom rule. V2 stopped at
`FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM`; do not lower that rule after the fact.

The separate A100/Qwen2.5-7B sprint is historical training evidence. At Stage A (224 examples),
JSON AST scored .979, compact symbolic .958, Structured English .938, HML .896, and
S-expression .833. S-expression trailed JSON by -.1458 with CI [-.25, -.0625]. At Stage B,
JSON and compact symbolic reached 1.0; at fresh Stage C both were 1.0. Verdict: non-flat early
landscape and `WEAK_CONTINUE`, followed by saturation. One model, one seed, and no replication
prevent a representation-advantage claim. The sprint also revealed that its original
`assert_matched_semantics` could pass an empty mapping; commit `a4f7d7f` fixed this and Phase 3
added regression tests for empty, singleton, byte-identical, and valid matched arms.

These histories are priors only. They are not combined with V3 scores.

## 5. Genome audit

The original `LanguageGenome` has 14 axes but zero content-bearing and zero reasoning-protocol
axes. Seven are surface: alphabet, token policy, morphology, grammar, serialization,
redundancy, error locality. Seven are structural: composition, types, binders, state, actions,
obligations, evidence. The legacy label `STRUCTURAL_SEMANTIC` denotes reconstruction burden,
not new mathematical content.

V1 mutated only grammar, binders, types, state, actions, serialization, morphology, and
redundancy. Therefore it searched four surface and four structural axes. All phenotypes encoded
the same canonical wire record and reversed their transforms before validation. The old 120
mutants were not rerun in Phase 3.

Primary audit outputs:

- `docs/GENOME_CONTENT_AUDIT.md`
- `artifacts/reports/genome-content-audit.json`
- file SHA-256:
  `ab2813c93bfac7a6ab7a2ddbd041696d7f66470fc01a9492e8f5a2ebee81d265`

## 6. Dual-layer model-view architecture

New package: `arena/model_view/`.

### `genome.py`

Defines `ModelViewGenome`, `ContentGenome`, and two search tracks:

- `TRACK_E_EQUAL_INFORMATION`: reversible surface/structural changes only;
- `TRACK_C_CONTENT_PROJECTION`: canonical surface plus deterministic truth-derived relations.

The six v1 content axes and values are:

1. dependency projection: `IMPLICIT`, `EXPLICIT_EDGE`, `EXPLICIT_LOCAL_EDGE`;
2. action-goal projection: `IMPLICIT`, `TARGET_ID`, `TARGET_BLOCK`;
3. premise projection: `GLOBAL_LIST`, `ACTION_LOCAL`, `EXPLICIT_EDGE`;
4. obligation projection: `GLOBAL`, `OWNER_LOCAL`, `ACTION_LOCAL`;
5. state-delta projection: `FULL_BEFORE_AFTER`, `DELTA_PLUS_CONTEXT`,
   `EXPLICIT_CHANGED_RELATIONS`;
6. evidence projection: `STATUS_ONLY`, `PROOF_EDGE`, `LOCAL_PROVENANCE`.

`CONTENT_GENE_METADATA` records values, semantic invariant, affected slices, cost tier, and
instrumentation requirement for every gene.

### `projection.py`

`derive_truth_view` accepts an already permitted canonical state, displayed action options,
and optional previous state. It emits `DerivedRelation` records with payload, derivation rule,
canonical witness hashes, and a stable relation hash. It declares unavailable or intentionally
implicit relations as omissions. Displayed option payloads remove `expected_usefulness`.

Important boundary: caller-side observation projection remains responsible for stripping
hidden legal/invalid action pools. V3 states have both pools empty and all option usefulness is
zero. Tests explicitly check that hidden actions are not read.

### `compiler.py`

`ModelViewCompiler` first emits the lossless `GenomePhenotypeLanguage` surface. Track C appends
a canonical JSON truth-derived block. `InformationAccounting` records canonical/previous/option
hashes, derived relation hashes, omissions, repeated witness count, and surface/projection byte
cost. `validate` independently recompiles the complete view, recovers canonical truth, and
rejects any mismatch or serialized projection tampering.

All 18 content-gene values have behavioral novelty coverage on a rich fixture. Every value is
required to change emitted bytes while preserving the canonical mathematical hash. Tampering,
answer leakage, and Track E recovery have direct tests.

Known design flaw revealed by founders: the model currently sees the full witness/accounting
projection. The audit ledger is necessary, but its verbose bytes should not automatically be
the model-facing bytes. V3.1 should compile a compact view and store a hash-bound full ledger
beside it; validation must still reproduce both.

## 7. Fitness V3 design

Module: `arena/experiments/fitness_v3.py`.

Version: `arena-representation-fitness-v3`. Instrument:
`arena-structural-frontier-instrument-v3.0.0`. This is new code; V2 was not modified and its
15-point rule was not reused.

The six mechanisms correspond to the first six content axes:

- long evidence dependency chains;
- action-to-goal assignment among repeated identities;
- premise attribution;
- obligation ownership;
- before/after state delta under irrelevant context;
- evidence status/provenance.

Each family contains six probes: original, truth-changing counterfactual, two
information-identical destroyed siblings with opposing balanced targets, and position-swapped
copies of the two positive states. All states pass `NativeVerifier`; legal/invalid action pools
are empty; option usefulness is zero. Answers are independently fixed by generator/oracle
records. Strict response schema is `{"choice":"A"}` or `{"choice":"B"}`.

DEV contained two complexity levels per mechanism: 12 families / 72 probes. Complexity changes
chain depth and 16 versus 24 repeated/irrelevant objects/facts. Selection used only the
permanent JSON/typed-AST control and chose the family closest to 62.5% positive accuracy within
each mechanism. It did not use any candidate winner. Complexity 1 was selected for all six.

The preregistered aggregate qualification checks were Q0 ≥.95, positive accuracy .40–.85,
positive-minus-destroyed gap ≥.10, semantic flip ≥.50, position invariance ≥.60, and all six
mechanisms. Selected DEV scored 1.0, .8333, .4167, .8333, .8333, and six mechanisms,
respectively. The formal gate passed.

The independent SCOUT families used different salts and were frozen in commit `9616654` before
any founder calls. Frozen manifest has 36 probes and 12 positives per candidate. Candidate
promotion required valid-response rate ≥.95, at least four net wins, one-sided exact sign
p≤.05 with Holm correction, and semantic-flip delta ≥-.05. No arbitrary fixed accuracy delta
was required. The manifest warns that five all-win discordances are the minimum unadjusted
pattern reaching p<.05 and that non-significance is not equivalence.

Primary artifact identities:

| Artifact | Internal identity | File SHA-256 |
|---|---|---|
| DEV result | pool hash `b26bf3d942ce57951428d2a4ca0c1fd4b62de4e90833e0bcae304d6525ffe4fe` | `9540c871a8a42626c167eac2daa21db1284ee1d73c55f808d5aa0dacecdf9dc1` |
| Frozen manifest | `6f1f6c4244d675863402d40536d67270fd8789b050e524bc1fdaa99b6aa09138` | `d94cf7c92cadce1998c28dda5fde54a839bcfddaf0fd4d3693ee4a9655930720` |
| Founder result | `6b1eb4fa2dacd4f027208a2854985de4b3af9ed5c0929f6002293513300d4b09` | `db3aecaa0999fc440bc9d0b855b0adf3afdbf7a6acf03de4e63972d24c016fea` |
| Invalidity decision | sentinel `EXPERIMENT_INVALID` | `328460b14ec9f7520826b30d2d5611b6f99f32abd54980a961d72387716e967e` |

Model/runtime were inherited exactly from qualified V2:

- model label `gemma4:12b`;
- digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`;
- parameter size 11.9B; Q4_K_M;
- Ollama local generation;
- `num_ctx=8192`, temperature 0, seed 20260905, `num_predict=64`, `top_k=64`,
  `top_p=.95`, `think=false`;
- runtime hash `9e82b40f7a0a55259278862cca9fc7ca2148e6a84fa8271c8f247978e46dfcd4`.

## 8. Founder tournament

Roster was frozen conceptually as eight broad Track E seeds plus a small JSON Track C family:

- Structured English, current HML, S-expression, JSON/typed AST, typed prefix, compact
  symbolic, graph triples, role-labelled hybrid;
- Track C JSON baseline;
- explicit-dependency, target-block, and delta-plus-context one-gene children of that baseline.

Exactly 432 calls completed. Each candidate has 36 rows; the union has exactly 36 unique probe
IDs. No model-call error occurred. The result hash independently recomputes when its own
`result_hash` field is omitted.

Positive/destroyed/flip/position/valid results:

- compact symbolic: 1.0/.5/1.0/1.0/1.0;
- seven other Track E founders: .8333/.4167/.8333/.8333/.8333 each;
- Track C JSON baseline and delta-context: same .8333/.4167/.8333/.8333/.8333;
- explicit dependency: .6667/.4167/.6667/.6667/.7222;
- target block: .5/.25/.5/.5/.5.

Against JSON, compact symbolic had 2 wins, 0 losses, 10 ties, p=.25. Its Holm threshold was
.004545 and it missed the four-net-win minimum. Every other equal-information founder tied
JSON exactly. Explicit dependency had 0 wins/2 losses; target block 0/4. Zero candidates passed
all promotion checks.

Mechanism decomposition exposed the invalidity:

- action-goal, dependency, provenance, obligation, and premise: 2/2 positives for every Track E
  founder;
- state delta: 0/2 for seven Track E founders, 2/2 for compact symbolic.

This is not a frontier band. It is a five-ceiling/one-floor mixture. The formal aggregate gate
was underspecified because it did not require per-mechanism dynamic range or validity.

The run was interrupted once after 66 founder rows to consider runtime. The restart exposed a
cache reader defect: `_cached_call` wrote `{identity,result}` but initially returned the entire
wrapper on a hit. No cached result had been aggregated at that point. The reader now validates
identity and returns the nested result; a regression test covers resume. The tournament then
resumed sequentially, reusing 66 validated rows and making the remaining calls. This did not
change prompts, model settings, seeds, targets, or scoring.

## 9. Claims rejected and branches not run

Rejected claims:

- “V3 is valid because its aggregate preregistered checks passed.” Mechanism-level ceiling and
  floor violate the governing requirement.
- “Compact symbolic won.” It had only two discordant wins, p=.25, and no Holm rejection.
- “Content projection helps.” The mini-family tied or harmed JSON; the current verbose block is
  negative engineering evidence.
- “No representation effect exists.” V3 is invalid and SCOUT is underpowered for small effects.
- “The 50-point raw range is a landscape signal.” Much of it is malformed response behavior in
  verbose Track C arms.
- “The old 120 mutants should now be run.” No valid founder promotion exists.
- “The A100 matched sprint releases JSON or L5.” It saturated and lacks replication.
- “R* exists.” Hidden, OOD, matched learning, and release assurance were never earned.

Not run or created:

- 30–60 candidate content/structure campaign;
- Tier 2B fresh promotion;
- Tier 3 OOD/finalist evaluation;
- matched 1K adaptation for V3;
- `RSTAR_0_1/`;
- 10K/1M trajectory generation;
- visual UI/animation.

There is intentionally no `MATCHED_1K` report and no `RSTAR_0_1` directory.

## 10. Known limitations and confounds

1. V3 uses one local model, one model digest, and one generation seed.
2. There are only two positive observations per mechanism per candidate. SCOUT can see only
   very large paired effects.
3. DEV selection had only two complexity points; five mechanisms jumped from ceiling at level
   1 to malformed/floor at level 2.
4. Qualification used aggregate, not per-mechanism, checks. This is the invalidating defect.
5. Overall valid-response rate was not a qualification check, although candidate promotion
   required .95. The selected control had .8333 overall validity.
6. Track C exposes the full audit ledger to the model. Auditability and model-facing brevity
   should be separated without weakening their hash binding.
7. State-delta prompts render previous state separately; Track C full-before/after may duplicate
   it again. This can confound content locality with token burden.
8. V3 tested only three one-gene content children in founders; it did not evaluate all six axes.
9. `NativeVerifier` proves structural conditions, not arbitrary relational answer truth. V3
   therefore relies on deterministic generator/oracle records; these are bounded synthetic
   mechanisms, not a universal math theorem prover.
10. Option metadata is symmetric and has usefulness zero, but some Track C projections may
    expose relations that are trivially derivable from the displayed option itself. Future
    fixtures should measure whether locality, not redundant copying, causes any change.
11. Model call caches live under ignored `artifacts/cache/fitness_v3`; committed primary results
    contain raw outputs and hashes, so the scientific report does not depend on retaining the
    local cache.
12. The old `docs/CLAUDE_HANDOFF.md` describes the V2 stopping point and is historical. This
    document plus Phase 3 artifacts supersede it for current state; do not delete historical
    evidence.

## 11. Exact next decision tree

Do not modify or rerun V3 as though it were still promotable. Open a new version, preferably
`arena-representation-fitness-v3.1` or V4, with new DEV and SCOUT salts.

1. Preserve commits `9616654` and `b85f98f`, all manifests, raw rows, and invalidity JSON.
2. Refactor model-view compilation into two hash-bound outputs:
   - compact model-facing derived relations;
   - complete external information-accounting/witness ledger.
   Independent validation must recompute both and bind the compact bytes to the ledger hash.
3. Build a larger DEV pool with at least four positive pairs per mechanism and finer structural
   difficulty steps. Change genuine structure—chain depth, identity recurrence, scope depth,
   competing goals, premise ambiguity, obligation fan-out, partiality—not inference quality.
4. Predeclare per-mechanism admissibility before calls. Recommended minimum checks:
   - ≥95% strict response validity for every retained mechanism;
   - strong-control positive accuracy within a declared frontier band per mechanism or within a
     prespecified hierarchical band with no mechanism at 0% or 100%;
   - destroyed-control collapse per mechanism with balanced targets;
   - position invariance and semantic flips per mechanism;
   - independent answer/oracle and no option-membership leakage.
5. Select DEV tasks only by absolute reading validity, difficulty, entropy, structural metadata,
   and mechanism coverage. Never use “where L5/content/HML wins.” The present founder outcomes
   are now contaminated for instrument selection and may be used only to diagnose failure
   modes, not choose favorable tasks.
6. Preregister paired sensitivity for the actual number of positive pairs. Use exact sign or
   McNemar/clustered bootstrap as appropriate, multiplicity correction, minimum valid response,
   semantic noninferiority, and explicit “non-significance is not equivalence” language.
7. Run DEV only. If any mechanism remains ceiling/floor/malformed, redesign under the declared
   development process; do not freeze.
8. Commit the qualified freeze before any founder or evolved-candidate call.
9. Run eight broad founders plus a small content mini-family. Require complete paired rows.
10. If and only if the frozen founder gate detects a reproducible mechanism effect, generate
    30–60 one-gene, matched-across-parent content/structure candidates. Record parent, changed
    gene, view delta, derived-information delta, byte/token delta, and test dependencies.
11. Promote 6–10 only through fresh frozen tasks; require rank/effect replication before OOD.
12. Run matched 1K only after stable fresh/OOD evidence. Match examples or tokens according to
    a predeclared estimand, keep identical base checkpoint/optimizer/seed/update budget, and
    replicate model/seed if possible.
13. Create `RSTAR_0_1/` only if semantic assurance, hidden/OOD evidence, matched learning, and
    reproducibility all pass. Otherwise keep R* withheld.

Decision terminals:

- new instrument fails DEV → `FITNESS_V3_NOT_YET_QUALIFIED` or `EXPERIMENT_INVALID`;
- instrument qualifies before candidates → `FITNESS_V3_QUALIFIED_READY_FOR_TIER2A`;
- reproducible candidate behavior passes paired gates → `REPRESENTATION_SIGNAL_FOUND`;
- local effect appears but search/replication is weak →
  `REPRESENTATION_SIGNAL_FOUND_LOCAL_SEARCH_WEAK`;
- a valid, powered landscape finds no effect → `NO_MEASURABLE_REPRESENTATION_SIGNAL`;
- matched adaptation wins → `MATCHED_REPRESENTATION_ADVANTAGE_FOUND`;
- release gates pass → only then an R* candidate/training-ready sentinel.

## 12. Exact commands

From `/Users/moheet/Documents/ChatGPT/hamiltonian_chess`:

```bash
git status --short --branch
git log --format='%H %s' -12
uv run ruff check .
uv run ruff format --check .
uv run mypy arena
uv run pytest
uv run python -m arena.experiments.fitness_v3 status
```

Expected current status output:

```json
{"experiment_version":"arena-representation-fitness-v3","matched_1k_authorized":false,"reason":"aggregate calibration pooled five ceiling mechanisms with one floor mechanism","sentinel":"EXPERIMENT_INVALID","tier2a_authorized":false}
```

To inspect, not alter, historical V3 artifacts:

```bash
shasum -a 256 artifacts/experiments/fitness_v3/development/result.json \
  artifacts/experiments/fitness_v3/frozen_manifest.json \
  artifacts/experiments/fitness_v3/founders/result.json \
  artifacts/experiments/fitness_v3/invalidity.json \
  artifacts/reports/genome-content-audit.json
```

Historical generation commands, for controlled reproduction only:

```bash
uv run python -m arena.experiments.fitness_v3 materialize
uv run python -m arena.experiments.fitness_v3 develop
uv run python -m arena.experiments.fitness_v3 freeze
uv run python -m arena.experiments.fitness_v3 founders
```

Do not use `develop`/`freeze` to overwrite the committed experiment while designing V3.1.
Create new paths and version constants first. Do not run `founders` as a candidate-selection
shortcut; its current output is historical and invalidated.

## 13. Required Phase 3 documents

- `docs/CURRENT_STATE.md`
- `docs/GENOME_CONTENT_AUDIT.md`
- `docs/ARENA_MASTER_ARCHITECTURE.md`
- `docs/FITNESS_V3_SPEC.md`
- `docs/CONTENT_GENOME_V1.md`
- `docs/ARENA_VISUAL_MODEL.md`
- `docs/FOUNDER_TOURNAMENT.md`
- `docs/REPRESENTATION_LANDSCAPE.md`
- this `docs/FINAL_GPT_HANDOFF.md`

No `MATCHED_1K` report or `RSTAR_0_1/` is present because neither was earned.

## 14. Final scientific state

`EXPERIMENT_INVALID`
