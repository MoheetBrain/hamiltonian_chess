# Hamiltonian Arena — Claude Final Handoff (Phases 4-5, 2026-09-06/07)

Read this first. It assumes no chat history, no knowledge of HML, and no knowledge of the
Arena. Every number below is taken from a committed artifact named beside it. Where a claim
could not be verified, it says so.

Current sentinel: **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`**.

---

## 1. Permanent goal

`GOAL.md` is the constitution. SHA-256
`43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`; verified at takeover and
at the end of this session; **not modified**. It may be changed only with explicit owner
authorisation, which this session did not have.

In one paragraph: Hamiltonian Arena tests whether the way mathematics is represented to an AI
causally changes its verified mathematical capability. Truth lives in a versioned canonical
substrate (Σ) with independent verifiers (V). Ten variables are kept distinct — Σ truth,
P visibility/projection, R representation, τ tokenizer, π solver, C controller, D tasks,
U tools, V verifier, B budget — and only one class is varied per "game". Game R (vary only R)
comes first; Game P (which true relations to expose), Game C (controller), Game T
(curriculum) and Game J (joint) come later. Winners are named by evidence level
(VALID → FITNESS → LEARNABILITY → ROBUST → RSTAR_0_1), never by a leaderboard. Valid outcomes
include "generic representations remain unbeatable" and "representation matters but local
search does not work".

## 2. Repository state

| Item | Value |
|---|---|
| Repository | `https://github.com/MoheetBrain/hamiltonian_chess.git` |
| Working tree used | worktree `/Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/hamiltonian-arena-takeover-caa2eb`, branch `claude/hamiltonian-arena-takeover-caa2eb` |
| Start SHA | `39952276a24462be8d0c8bce58bc3d106fd1dd2c` (`codex/arena-v0-fitness` = `origin/codex/arena-v0-fitness` at takeover) |
| V4 preregistration commit | `88bacc83277837cc53aebe02e8104736c835fa07` |
| Final commit | the commit containing this file: run `git rev-parse HEAD`; it is a descendant of `88bacc8` |
| Push | `codex/arena-v0-fitness` fast-forwarded to the final commit; no force push; remote SHA must equal local after `git fetch` |
| Worktree status | clean except ignored `.venv/`, `artifacts/cache/`, `artifacts/tmp/` |

## 3. Project history

| Commit | Stage | Outcome |
|---|---|---|
| `c1dd586` | Arena v0 | canonical world (676 tasks), 8 seed languages, assurance, league, CLI |
| `f17bb0f`, `11b73ae`, `22cab97` | Fitness V1 | `MODEL_FITNESS_BENCHMARK_INVALID`: gemma3:4b chose option A regardless of state |
| `99c877f`, `9832982` | Fitness V2 | instrument qualified with gemma4:12b; control range 12.5 points < frozen 15 → stopped |
| `bf8838b` | A100 matched sprint | Qwen2.5-7B LoRA, 5 arms; Stage A JSON .979 > CS .958 > SE .938 > HML .896 > S-expr .833; saturates at 576; `WEAK_CONTINUE` |
| `a4f7d7f` | guard fix | `assert_matched_semantics` fails closed on empty/duplicate arms |
| `9616654`, `b85f98f`, `997acaa` | Phase 3 / V3 | dual-layer model view, six Track-C content genes, V3 frozen, 12-founder/432-call tournament, `EXPERIMENT_INVALID` |
| `3995227` | GOAL freeze | `GOAL.md` committed |
| `88bacc8` | Phase 4 | V3 diagnosed as input truncation; Fitness V4 preregistered |
| `2f1cf89` | Phase 4 | V4 DEV complete, `FITNESS_V4_NOT_QUALIFIED`, forensics, mutant audit |
| final | Phase 5 | protocol repaired and proven; formal probe bank; Fitness V5 run; abort clause fired |

## 4. Canonical world

- Schema `arena-canonical-v0.1.0` (`arena/canonical/schema.py`): `CanonicalExpression`
  (op/args/value/sort/attributes), `MathObject`, `Binding`, `Obligation`, `EvidenceNode`,
  `CanonicalAction`, `CanonicalState`, `CanonicalTransition`, `CanonicalTrajectory`.
  Mathematical hashes exclude display ids and execution metadata.
- Gold world v0: 676 one-transition tasks, 13 domains × 52, seed 0, generator
  `arena/tasks/generators/world_v0.py`; quality 520 Gold / 104 Silver / 52 Reject; world hash
  `ac16014cd20fbed2dabacd75bff3fd19723e3e96048f82a1ee1a574f59daf256` (`docs/EXPERIMENT_LOG.md`).
- Frozen for the whole programme. V2 probes derive from Gold; V3 and V4 probes are synthetic
  mechanism families outside Gold, provenance-labelled, never called Gold.

## 5. Architecture by variable

| Variable | Frozen value in Game R | Code |
|---|---|---|
| Σ | canonical v0.1.0 | `arena/canonical/`, `arena/tasks/generators/world_v0.py` |
| P | Track E, `ContentGenome()` default, no projection | `arena/model_view/genome.py`, `projection.py` |
| R | 14-gene `LanguageGenome`; 8 seeds; lossless codec | `arena/genome/schema.py`, `seeds.py`, `arena/languages/phenotype.py`, `arena/model_view/compiler.py` |
| τ | Gemma 4 tokenizer via Ollama | implicit |
| π | `gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`, Q4_K_M | `arena/experiments/fitness_v2.py::QUALIFIED_MODEL` |
| C | one greedy response, JSON `{"choice":"A"|"B"}`, no reasoning | `fitness_v4.build_prompt`, `parse_response` |
| D | V4 mechanism families | `fitness_v4.LADDERS`, `derive_probe_family` |
| U | none | — |
| V | `NativeVerifier` + per-mechanism independent truth re-derivation | `arena/verifier/native.py`, `fitness_v4.{expression_depths,ancestors,resolve_site,satisfied_options,added_facts}` |
| B | Ollama; `num_ctx` 32768, temperature 0, seed 20260905, `num_predict` 64, `top_k` 64, `top_p` .95, think off | `fitness_v4.RUNTIME_CONFIG` (hash in every cache identity) |

## 6. Agent roles (as implemented)

| Role | Implementation | Boundary |
|---|---|---|
| Architect | `arena/players/architect.py` (deterministic legal neighbours); no LLM Architect used this session | cannot touch truth, verifier, sealed answers |
| Builder | `GenomePhenotypeLanguage` + `ModelViewCompiler` | deterministic |
| Solver | `gemma4:12b` via `fitness_v4._call_ollama` | sees only the candidate view; never the oracle |
| Experimentalist | `fitness_v4.run_development`, `select_frontier_level`, `qualify_mechanism`, `shortcut_audit` | DEV only, control only, rules frozen before calls |
| Refuter | `arena/players/refuter.py`, `arena/assurance/` | not exercised this session |
| Curriculum | `arena/tasks/curriculum.py` | disabled for Game R |
| League | `arena/league/` | frozen promotion rules in `fitness_v4.PROMOTION_RULE` |
| Verifier | `arena/verifier/` | never strategic |

## 7. Cross-repository reuse (this session)

| Donor | Branch / SHA | Path | Used how | Rejected |
|---|---|---|---|---|
| `MoheetBrain/HML_V3` | `codex/open-ended-search-v2` @ `95e8a26f6519f226a149f4d7507d47f90bea9932` (local clone; audited SHA `4395a8c` is an ancestor) | `src/hml_v3/projection/dense.py` | design of `build_depth_tree` (hashed association, pinned runner-up, truth by walk); reimplemented over Arena expressions | no data, no scores |
| same | same | `src/hml_v3/micromath/shortcut_v2.py` | dumb-rule audit design, made symmetric | — |
| same | same | `src/hml_v3/micromath/calibration_v2.py` | corrected paired bootstrap principle (`random.Random`, no LCG); Arena already used `random.Random` | — |
| same | same | `HML_PIVOT_HANDOFF.md`, ledger entries `REAL_LEAN_GAP_V1`, `FINAL_HML_KILL_GATE` | failure memory; recurrence-not-clutter finding; two-reader replication warning | its "static thesis closed" verdict is recorded, not adopted as an Arena result |
| `MoheetBrain/hml-reasoning-corpus`, `hamiltonian-lang`, `hml-standard` | as in `docs/CROSS_REPO_ASSET_AUDIT.md` | — | inspected in prior sessions; nothing new imported | — |
| A100 sprint artifact (this repo) | `bf8838b` | `artifacts/experiments/tier2_sprint/` | loss curves re-read for Route B audit | not used as fitness evidence |

## 8. Experimental firewall

- Splits: V4 DEV salts `EXPERIMENT_SEED + mechanism*1000 + level*100 + family`; SCOUT salts
  +100000; PROMOTION/OOD not materialised. No historical data as hidden data.
- Prompt matching: one common envelope; only the lossless state and option renderings vary;
  syntax guide generated from the genome; `assert_game_r_genome` rejects any Track-C genome.
- Information parity: `assert_information_parity` (identical recovered mathematical hash,
  distinct bytes) is applied to every SCOUT probe × founder at freeze. Because V4 did not
  qualify, the frozen manifest holds zero SCOUT probes, so this control is implemented and
  unit-tested but **was never exercised on real probes**. The five-check mutant audit was
  exercised in full.
- Cache identity: experiment, instrument, model digest, runtime hash, genome hash, probe hash,
  prompt hash.
- Context fairness: pre-call and post-call guard; any over-budget probe void for all
  candidates (see §12 for its defect).
- Selection: DEV only, JSON control only, rules frozen in code before the first call.

## 9. Fitness V4

**Construction.** Five mechanisms × five-level ladders × six-probe families (original,
counterfactual, two byte-identical destroyed twins with opposite targets, two position swaps);
targets balanced by construction; four distractor objects; truth re-derived independently per
mechanism. DEV pool 900 probes, hash `0a45154c532a1a61ef77cf107d4d6bc957cb0be46f4719912b784605043dba05`;
pre-inference shortcut audit CLEAN (worst dumb rule .567).

**Qualification rule** (`docs/FITNESS_V4_SPEC.md` §7): L0 ≥ .90; frontier = level nearest .625
in [.35, .85]; at the frontier: valid ≥ .95, no truncation, positive − destroyed ≥ .10,
semantic flip ≥ .25 and choice flip ≥ .50, position invariance ≥ .50, shortcut clean; ≥ 2
mechanisms to qualify.

**Result** (`artifacts/experiments/fitness_v4/development/result.json`, sha256
`f20bd25ece0bf9266c465b3376be5d716cea1b05058093b72797392c3e30e137`; 356 calls; Q0 1.000):

| Mechanism | L0 | L1 | L2 | L3 | L4 | Verdict |
|---|---|---|---|---|---|---|
| expression_depth_recurrence | .833 | .583 | .417 | .667 | .750 | VOID_INSTRUMENT_LIMIT |
| transitive_dependency | 1.000 | 1.000 | .583 | .333 | .417 | VOID_VALIDITY (valid .528 at L2) |
| binder_scope_resolution | .750 | .500 | .500 | .500 | unsent | VOID_INSTRUMENT_LIMIT |
| precondition_conjunction | 1.000 | .667 | .583 | .500 | .500 | VOID_FLIP (choice flip .333 at L1) |
| state_delta | .500 | .083 | .083 | .500 | unsent | VOID_INSTRUMENT_LIMIT |

Frozen manifest `artifacts/experiments/fitness_v4/frozen_manifest.json` (sha256
`74726857dc80ae1fb38a29fd44fb2cb85a9c7f1b334ff4ed5d7e5de33fa42e61`, internal manifest hash
`41efd033bc21d6bb3bec4c6b5c8d925262366b9e835f53920dfc21fa117f65d8`, `qualified=false`, 0 SCOUT
probes); `not_qualified.json` sha256 `a6bb4c5725518a1ee34ce58d866e7a9b47ddb2471eae607f7fe50540517ed4f9`.

**Validity.** V4 is a valid *negative instrument result*: the gates worked, and nothing about
any representation was measured. Diagnostics (`artifacts/reports/fitness-v4-forensics.json`,
sha256 `12889adc37fed963c9514fd2e3cd3d971fbdc9eade81ab511a3db3730affc09d`): 348 rows → 179
correct, 13 negative-control answers, 67 semantic errors, 59 reasoning-overflow rows (prose
derivation cut at 64 tokens, no JSON), 24 unsent and 6 flagged by the context guard (false
positives on whitespace-heavy JSON). Constant-"A" at hard levels (12/12 on precondition L3/L4,
binder L1/L2). Full analysis: `docs/FITNESS_V4_FAILURE_ANALYSIS.md`.

## 10. Game R

- Founder tournament: **NOT RUN** (gate not met). Preflight tool exists
  (`arena/experiments/fitness_v4_preflight.py`), unused.
- Candidate results: none.
- Mutation landscape: not measured. Plan: `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md`, gated by
  `AUTHORIZED = founder_promoted OR founder_penalised` (currently false).
- Mutant audit (`artifacts/reports/game-r-mutant-audit.json`, sha256
  `0c2e3b9320848d28e464f3f5ff77eaefe010354ebcb0648dd5edbf18c23f01f6`): 120/120
  `GAME_R_COMPATIBLE`; 0 behavioural duplicates; 0 structural near-duplicates; clusters by
  grammar family, organisation, serialization, binder encoding, type placement, role labels,
  identifier system, compression, option structure.
- Paired statistics: implemented and unit-tested (`paired_against`, `holm_decisions`,
  `clustered_paired_bootstrap`), unused on real data.
- Local search verdict: none.

## 11. Matched learning

Not run this session. Historical A100 sprint audited in `docs/ROUTE_B_HISTORICAL_AUDIT.md`
(`artifacts/reports/route-b-loss-curve-audit.json`, sha256
`1383f64bd172688451ab19a95e847bb0c8cc873ca5c007d7866c1a44e2aa2379`): loss curves at
16/32/64/128/224 examples separate early and collapse by 128; their order contradicts the
224-example accuracy order, so per-token loss is not a cross-representation learning signal.
Recommendation: a preregistered low-budget learning-curve instrument (held-out accuracy at
16–224, two seeds, example- and token-matched) is stronger than another zero-shot instrument
if V5 also fails; it needs GPU authorisation.

## 12. Soundness

- Tests: 188 passing (`pytest -q`); ruff and mypy clean.
- Assurance suite and canonical validation: not re-run this session (no relevant code
  changed); last recorded results in `docs/EXPERIMENT_LOG.md` (2,703/2,703, 64/64,
  1,352/1,352).
- Defects found this session: (1) V3 input truncation at `num_ctx=8192` (all 66 malformed
  founder rows at 4,099 tokens; Ollama log `truncating input prompt limit=4099`); (2) V3
  mechanisms were single-field lookups; (3) V3 state-delta answer op name (`added`) leaked
  the answer (fixed in V4); (4) V4 context pre-guard (chars/2.0) and post-check (chars/6.0)
  are representation-specific and voided 30 rows (24 refused before sending, 6 flagged after)
  that the measured token ratios indicate would have fit; (5) V4 level 0 is a minimal-size
  control, not a relation-stated explicit positive.
- No false accepts, bounded-universe failures or verifier disagreements were introduced; no
  verifier code changed.

## 13. Candidate hierarchy

| Level | Members |
|---|---|
| VALID_CANDIDATE | 8 seeds; 120 one-gene mutants (Gate 0 in V1; Game-R audit in this session) |
| FITNESS_CANDIDATE | none |
| LEARNABILITY_CANDIDATE | none |
| ROBUST_CANDIDATE | none |
| RSTAR_0_1 | none — `RSTAR_NOT_IDENTIFIED` |

## 14. Known failures and guards

| Failure | Guard |
|---|---|
| Position policy (V1; V4 hard levels) | balanced targets, position swaps, choice-flip gate |
| Input truncation (V3) | `num_ctx` 32768, token-count post-check, over-budget probes void for all |
| Lookup-only mechanisms at ceiling (V3) | difficulty ladders with explicit-positive L0 and frontier band |
| Aggregate pooling hiding ceilings/floors (V3) | per-mechanism verdicts, no aggregate score |
| Reasoning overflow at 64 tokens (V4) | recorded; requires `C`/`B` recalibration (V4.1 proposal) |
| Whitespace-heavy prompts mis-flagged by char guard (V4) | recorded; V5 must count tokens or verify by truncation signature |
| Unequal prompt envelopes, Unicode-escape asymmetry, candidate-specific guides (historical) | common envelope, generated guide, prompt hashes, information-equality tests |
| Degenerate bootstrap RNG (HML_V3 FM-057) | `random.Random` seeded; clustered resampling |
| Single-reader effects (HML_V3 kill gate) | no representation claim without a second Solver family |

## 15. Open questions, ranked by expected value

1. Does a non-sabotaging output budget exist for `gemma4:12b` under which multi-step
   structural mechanisms return valid JSON ≥ 95% of the time? (V4.1 calibration; ≈ 1,500
   calls; decides whether zero-shot Game R is measurable with this Solver.)
2. With that budget, do transitive_dependency and precondition_conjunction reach the
   frontier band with a working destroyed control and choice flip? (V5 DEV.)
3. Is low-budget matched learning a better instrument than zero-shot reading? (Route B;
   needs GPU.)
4. Does any founder differ from JSON under a valid V5? (founders.)
5. Is the R landscape locally searchable? (mutation campaign, conditional.)
6. Does any effect replicate on a second Solver family? (mandatory before any
   FITNESS_CANDIDATE is called robust.)

## 16. Exact next decision tree

```text
CURRENT: FITNESS_V4_NOT_QUALIFIED
    |
    v
authorise V4.1 DEV-only output-budget calibration (docs/V4_1_PROTOCOL_CALIBRATION_PROPOSAL.md)
    |
    +-- no cell reaches valid >= .95 with L0 >= .90 on >= 2 mechanisms
    |      -> V4_1_NO_VALID_BUDGET
    |      -> choose: Route B (docs/ROUTE_B_HISTORICAL_AUDIT.md §4, GPU authorisation)
    |                 or second Solver family (rerun Q0 + L0 ladder first)
    |
    +-- a valid budget exists
           -> preregister V5 (docs/FITNESS_V4_FAILURE_ANALYSIS.md §5): new runtime hash,
              true explicit-positive arm, fixed context guard, lead mechanisms
              transitive_dependency + precondition_conjunction
           -> commit spec; run DEV; apply frozen gates
                 |
                 +-- < 2 mechanisms qualify -> FITNESS_V5_NOT_QUALIFIED; failure analysis; Route B
                 |
                 +-- >= 2 qualify -> freeze; commit; preflight; founders (8 Track-E)
                        |
                        +-- no promotion, no penalty -> GAME_R_NO_MEASURABLE_SIGNAL (at that power)
                        |
                        +-- promotion or penalty -> mutation campaign (docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md)
                               |
                               +-- searchable -> controlled local evolution; fresh PROMOTION; OOD
                               +-- not searchable -> GAME_R_SIGNAL_FOUND_LOCAL_SEARCH_WEAK; Architect/QD
                                      |
                                      v (any surviving candidate)
                               matched learning (2 seeds, example- and token-matched)
                               second Solver family
                               only then LEARNABILITY / ROBUST / RSTAR_0_1 naming
```

Game P starts only after Game R reaches a documented stopping point. No 10K/100K/1M
trajectory generation, no solver training, no self-play, no curriculum co-evolution before a
representation result exists.

## 17. Exact commands

From the repository root (main checkout or this worktree):

```bash
uv sync --all-extras
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy arena
shasum -a 256 GOAL.md            # expect 43d8fcdb...20117b
```

Instrument status and artifacts (read-only):

```bash
.venv/bin/python -m arena.experiments.fitness_v3 status     # EXPERIMENT_INVALID
.venv/bin/python -m arena.experiments.fitness_v4 status     # FITNESS_V4_NOT_QUALIFIED
.venv/bin/python -m arena.experiments.fitness_v4 materialize
.venv/bin/python -m arena.experiments.fitness_v4_forensics
.venv/bin/python -m arena.experiments.game_r_mutant_audit
shasum -a 256 artifacts/experiments/fitness_v4/development/result.json \
  artifacts/experiments/fitness_v4/frozen_manifest.json \
  artifacts/experiments/fitness_v4/not_qualified.json
```

Historical V4 generation (reproduces from cache; do not use to overwrite V4 while designing
V5 — create new version constants and paths first):

```bash
.venv/bin/python -m arena.experiments.fitness_v4 develop
.venv/bin/python -m arena.experiments.fitness_v4 freeze
```

Founder tournament (only after a qualified freeze of a new version):

```bash
.venv/bin/python -m arena.experiments.fitness_v4_preflight
.venv/bin/python -m arena.experiments.fitness_v4 founders --frozen-commit <sha of the freeze commit>
```

Matched adaptation (GPU; only after a founder signal and explicit authorisation):

```bash
.venv/bin/python -m arena.training.prepare_matched_data
.venv/bin/python -m arena.training.gpu_matched_runner   # see docs/PROJECT_STATUS.md history
.venv/bin/python -m arena.training.analyse_sprint
```

Ollama must be running locally with `gemma4:12b` at the digest above; the runner refuses
nothing else automatically, so check `ollama show gemma4:12b` before any run.

---

Final sentinel: **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`**.

---

# PHASE 5 ADDENDUM (2026-09-07)

Everything above describes Phase 4 and remains accurate for V4. This addendum supersedes its
"current sentinel", "open questions" and "next decision tree" sections.

## 18. What Phase 5 did

Ten subagents ran read-only investigations in parallel (state audit, protocol forensics,
statistical design, two donor-repo miners, formal-data inventory, population audit, canonical
schema audit, pilot design, red team). All writing and integration was central, which also
eliminated file-conflict risk. Where two agents disagreed the disagreement was resolved from
artifacts, not by majority: their claims about whether local Lean data is "independently
verified" were both partly right, and the resolution is recorded in §21 below.

## 19. The protocol was the artifact (measured, not argued)

| | V4 | V5 |
|---|---|---|
| rows scored | 348 | 432 |
| malformed / unusable | 89 (25.6%) | **0** |
| valid-response rate | .53–1.00 by level | **1.000 everywhere** |

Grammar-constrained decoding (`format` = JSON schema with `choice` enum) is supported by
Ollama 0.33.2, recovers 9 of 9 rows that V4 lost to prose overflow, and is **answer-neutral**
(agreement 1.000 wherever V4 also answered). Raising `num_predict` to 512 recovers 0 of 9.

V4's character context guard was an artifact: rows it voided truly used 7,396 / 9,498 /
23,215 tokens against a 32,448-token limit, and at binder-scope L3 it deleted precisely the
counterfactual arm, so that mechanism's published `.500` was "originals correct, counterfactuals
deleted by a rounding constant". V4's verdict stands as recorded — it applied its own frozen
rule — but it measured its instrument, not any representation.

## 20. Fitness V5: instrument sound, Solver insufficient

Spec `docs/FITNESS_V5_SPEC.md` (committed before the run). Result
`artifacts/experiments/fitness_v5/development/result.json`, sha256
`0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`. 392 calls, Q0 1.000.

| Mechanism | L0 explicit | L1 | L2 | L3 | Verdict |
|---|---|---|---|---|---|
| `formal_expression_depth` (real Lean) | **0.917** | 0.875 | 0.542 | 0.542 | `VOID_NEGATIVE_CONTROL` + `VOID_SHORTCUT` |
| `transitive_dependency` | 0.875 | 0.917 | 0.667 | 0.500 | `VOID_INSTRUMENT_LIMIT` |
| `precondition_conjunction` | **1.000** | 0.708 | 0.500 | 0.500 | `VOID_POSITION_SHARE` |

**The finding: answer collapse, not partial reading.** Largest single-answer share rises to
0.83, 1.00, 1.00 at the harder levels. Every cell reading ≈ 0.500 is the Solver answering one
option every time while balanced targets disguise it as chance. The new
`largest_answer_share ≤ 0.75` gate caught this; V4's choice-flip gate passes a coin-flipper
65.6% of the time at six families and would not have.

Two of three explicit-positive arms pass (0.917, 1.000) while zero mechanisms qualify, so the
**preregistered abort clause** fired: the limit is the Solver or the task family, not the
protocol. V6 is therefore not authorised — that would be protocol shopping. Full analysis:
`docs/FITNESS_V5_RESULT.md`.

## 21. Formal probe bank (new infrastructure)

`arena/environments/formal_structural.py` + `arena/provenance.py`. 1,150 real elaborated
Lean 4 transitions exist locally (donor `MoheetBrain/HML_V3` @ `95e8a26`,
`data/corpus/lean_runtime_v2_full.canonical.part-*.jsonl.gz`); 461 pass structural
eligibility. The donor's 126 sealed source files are excluded by name and never read.

Trust tiering is explicit and enforced (`require_oracle_grade`): the **states** are Tier A
(Lean's elaborator produced them); the **structural answers** are Tier B (Arena recomputes
them by walking the transcribed tree). Nothing claims the tactic step was replayed — the
donor's own attestation gate reports `passed=false` — and a depth question does not need that.

**Length fairness is a first-class constraint and a real finding.** On unrestricted real
states the eight surfaces differ in rendered length by a median factor of 6.5 and a maximum
of 23.7. Probes are restricted to states where every surface renders under 30,000 characters,
bounding the ratio to ~4.6 and leaving 104 states over 95 mathlib files (75% with a one-level
lead). Without that filter any accuracy comparison would measure token cost.

**Local Lean capability, verified directly (decision-relevant).** Lean toolchains
`v4.10.0-rc1` and `4.33.1` are installed under `~/.elan/toolchains`, and mathlib4 @
`29dcec074de168ac2bf835a77ef68bbe069194c5` is **fully built** at
`HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec07…/mathlib4` — 5,680
`.olean` files, `.lake/` present, `lean-toolchain` pinned to the installed `v4.10.0-rc1`, and
`Lean4Repl.olean` compiled, so LeanDojo-style interactive replay runs offline. One subagent
reported mathlib absent; that was a search-depth artifact (it scanned to depth 4, the path is
at depth 7) and is superseded by this direct check. Consequence: fresh state extraction and
genuine Tier-A replay certificates are available with **no download**, via
`HML_V3/scripts/extract/LeanRuntimeExtractV2.lean` and the pinned attestation bridge in
`hmlt-reasoning-corpus-lean-attestation` (`b4e2d98`). Note the donor's own attestation gate
reported `passed=false` at ~44% reproducible execution, so budget for that yield.

**Do not reuse `formal_expression_depth` as-is**: `first_mentioned_in_state` reaches 0.833 in
the selected stratum, because real Lean terms tend to mention the deeper identifier first. It
needs an option-ordering control and an identifier-obfuscation arm (to quantify mathlib
memorisation) before any promotion.

## 22. Corrections to Phase-4 work

- **Mutant audit was partly vacuous.** Its recovered-state inventory is a strict coarsening
  of `mathematical_hash`, so `GAME_P_ONLY` was unreachable and the option inventory was
  constant across candidates. Replaced with an inventory of the **rendered surface** decoded
  through the base codec (unbound, so a candidate cannot hide behind its own parser), with a
  regression test proving it fires on a candidate that emits a derived relation and drops it
  on parse. 120/120 `GAME_R_COMPATIBLE` still holds, now meaningfully.
- **`alpha_normalize` mis-scopes dependent binder types** (a binder's type at `args[1]` is
  scoped under its own binder, so two alpha-equivalent terms normalise differently). Not in
  any measurement path; pinned by a regression test so no future generator adopts it as an
  oracle for dependent types.
- Three historical docs now carry supersession banners instead of advertising stale sentinels.

## 23. Canonical vNext (parallel track, nothing implemented)

`docs/CANONICAL_VNEXT_GAP_REPORT.md`. Measured gaps in `arena-canonical-v0.1.0`: single
mandatory `goal` (no goal list, no metavariable assignment map), `Binding.type_name` is a
string so dependent hypothesis types collapse, no universe levels, no implicit/instance
argument kinds, no substitution map or distinct-variable conditions, no definitional-equality
step kind. Rejected now, for lack of measured need: OMDoc/MMT, a typed e-graph core, and
universal tactic microsteps. Deferred: Metamath as a cheap second Tier-A cross-check.
Lean-first remains the only plausible Tier-A substrate and is the one to pilot. **No canonical
schema change was made.**

## 24. Exact next decision tree (supersedes §16)

```text
CURRENT: CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT
    |
    v
re-run the FROZEN V5 DEV against a second Solver family (~400 calls each)
  installed locally: gemma4:31b, qwen38-rvn, qwen36-huihui, qwen38-huihui
    |
    +-- some Solver gives >=2 qualified mechanisms
    |      -> freeze SCOUT, commit, run the 8-founder Game-R tournament
    |      -> if founders discriminate: 40-mutant campaign
    |         (docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md), then landscape verdict
    |
    +-- no installed Solver gives a band
           -> the task family cannot support this measurement with local models
           -> Route B: low-budget matched learning curves at 16/32/64/128/224
              examples, two seeds (docs/ROUTE_B_HISTORICAL_AUDIT.md section 4).
              REQUIRES EXPLICIT GPU AUTHORISATION.
           -> if Route B also flat: report GAME_R_NO_MEASURABLE_SIGNAL under the
              declared universe and stop Game R. That is a valid GOAL.md outcome.
```

Do **not** build V6 unless a frozen variable class named in the failure analysis changes.
Budget remaining under the preregistered cap: 2 versions, ~24,600 calls.

## 25. Exact commands (Phase 5)

```bash
.venv/bin/python -m arena.experiments.fitness_v5 status
.venv/bin/python -m arena.experiments.fitness_v5 materialize
.venv/bin/python -m arena.experiments.game_r_mutant_audit
shasum -a 256 artifacts/experiments/fitness_v5/development/result.json
```

To re-run the frozen V5 DEV against another Solver, change only `QUALIFIED_MODEL` in
`arena/experiments/fitness_v2.py` (or parameterise it), which changes the cache identity and
so forces fresh calls without touching probes, gates or prompts:

```bash
.venv/bin/python -m arena.experiments.fitness_v5 develop
```

Final sentinel: **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`**.
