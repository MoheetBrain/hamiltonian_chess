# Project Status

> ## MISSION RESET — 2026-09-08
>
> The project owner has reset the project hierarchy. `GOAL.md` remains the scientific
> constitution **for controlled local Game-R experiments**, but it is no longer the top-level
> objective. The top-level mission is now `docs/HAMILTONIAN_CHESS_META_GOAL.md`: an open-ended
> system in which agents **discover** machine-facing mathematical languages that improve
> **verified long-horizon** mathematical reasoning. **Game R is demoted to the local causal
> fitness assay** used to decide whether a language mutation helped.
>
> Phase 8 (the first multi-representation experiment) was **stood down mid-build**. Its
> infrastructure is preserved and committed as `PHASE8_DIAGNOSTIC_INFRASTRUCTURE`; **no founder
> tournament ran, no preregistration was frozen, no language was ranked**. See
> `docs/PHASE8_SALVAGE_HANDOFF.md`.
>
> No historical result is retracted or reinterpreted by this reset.

## Project Objective

`GOAL.md` (SHA-256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`, unmodified)
is the permanent objective: determine whether the representation of mathematics shown to an
AI is a causal determinant of verified mathematical capability, holding Σ, P, τ, π, C, D, U,
V and B fixed, and if so find the strongest robust representation. Game R (vary only R) is the
first controlled game. No language is assumed to win; a negative result is valid.

## Current Stage

**`PHASE8_DIAGNOSTIC_INFRASTRUCTURE`, and the mission has been reset to the meta-game.**

Phase 8 built the machinery for the programme's first multi-representation experiment and then
stopped without running it, for two independent reasons recorded in
`docs/PHASE8_SALVAGE_HANDOFF.md`: the owner's mission reset (governing), and the deletion of the
preregistered Solver from the local runtime at 11:43 on 2026-09-08 (`qwen38-rvn:latest`, digest
`25eb57cb…`, replaced by `qwen3.6:27b-mlx`, digest `d49fd9e0…`; the manifest is gone and the name
is a local build that cannot be re-pulled).

What Phase 8 established, at zero model cost and independent of any Solver:

- **The precondition mechanism is clean on the bytes a Solver would actually see.** Best frozen
  adversary over 45 (stratum, surface) cells on fresh evaluation data: **0.5625** against a chance
  level of 0.500; ≤ 0.54 at every stratum with premises ≥ 7. Candidate-mention and option-text
  features are pinned at exactly 0.5 on 100% of twin pairs. This closes forensic-audit defects C1
  and C3e prospectively, in new code, without touching a frozen instrument.
- **The eight seed surfaces are not eight independent languages.** `L3_JSON_AST` and
  `L6_GRAPH_TRIPLES` share **98.6%** of their state bytes via ≥40-character spans at `P20`;
  `L0_STRUCTURED_ENGLISH` vs `L3_JSON_AST` reaches a **0.82** similarity ratio. Harness parity
  nevertheless passes everywhere (one envelope, one answer protocol, exact canonical recovery,
  distinct bytes, twin differences local to the assumptions block).

`Δ(R_A, R_B)` remains **uncomputed**, exactly as after V7.

## Current Branch

`claude/hamiltonian-arena-takeover-caa2eb` (worktree from `codex/arena-v0-fitness` at
`3995227`). This commit is fast-forwarded onto `codex/arena-v0-fitness` and pushed there.
No force push, no history rewrite.

## Current System Architecture

| Variable | Implementation |
|---|---|
| Σ | `arena/canonical/schema.py` (`arena-canonical-v0.1.0`); Gold world v0 (676 tasks), frozen |
| P | `arena/model_view/genome.py`, `projection.py`; fixed at Track-E default in Game R |
| R | `arena/genome/` (14 genes, 8 seeds), `arena/languages/phenotype.py`, `arena/model_view/compiler.py` |
| τ | Gemma 4 tokenizer via Ollama |
| π | `gemma4:12b` digest `4eb23ef1…` |
| C | single greedy JSON A/B answer, no reasoning, no search |
| D | V2 Gold counterfactuals; V3/V4 synthetic mechanism families |
| U | none |
| V | `arena/verifier/native.py`, SymPy/Z3/numeric adapters, per-probe generator oracles |
| B | Ollama runtime; V4: `num_ctx` 32768, `num_predict` 64, think off |

Experiments: `fitness_v1.py`, `fitness_v2.py`, `fitness_v3.py` (historical, immutable),
`fitness_v4.py` (instrument), `fitness_v4_forensics.py` (read-only diagnostics),
`fitness_v4_preflight.py` (founder preflight, unused because the gate failed),
`game_r_mutant_audit.py` (Game-R compatibility audit). Training: `arena/training/`.

## Capabilities Implemented

All Arena v0–Phase 3 capabilities, plus: the V4 structural-ladder instrument with
per-mechanism qualification and void codes; the context guard; Game-R genome enforcement and
information-parity assertion; paired founder statistics (exact sign, Holm, clustered
bootstrap, practical effect); a diagnostic-cause forensics pass separate from scientific
verdicts; a five-check Game-R mutant audit (semantic recovery, information inventory, derived
relations, option content, behavioural duplicate) with structural descriptors and distances; a
founder preflight with call/runtime/disk estimates.

## Work Completed to Date

- Arena v0 → Phase 3 (see `docs/FINAL_GPT_HANDOFF.md`).
- Takeover: reconciliation; V3 diagnosed as input truncation; V4 built, tested,
  preregistered (`88bacc8`); V4 DEV run to completion; V4 declared not qualified under its
  frozen rule; forensics; mutant audit (120/120 Game-R compatible); Route B historical audit;
  V4.1 budget-calibration proposal; conditional mutation-campaign plan; canonical vNext gap
  report; final handoff `docs/CLAUDE_FINAL_HANDOFF.md`.

## Important Files and Artifacts

- `docs/CLAUDE_FINAL_HANDOFF.md` — read first.
- `docs/FITNESS_V4_SPEC.md`, `docs/FITNESS_V4_FAILURE_ANALYSIS.md`, `docs/GAME_R_STATUS.md`.
- `docs/V4_1_PROTOCOL_CALIBRATION_PROPOSAL.md`, `docs/ROUTE_B_HISTORICAL_AUDIT.md`,
  `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md`, `docs/CANONICAL_VNEXT_GAP_REPORT.md`.
- `artifacts/experiments/fitness_v4/development/result.json` (sha256 `f20bd25e…`),
  `frozen_manifest.json` (`74726857…`, `qualified=false`), `not_qualified.json`
  (`a6bb4c57…`).
- `artifacts/reports/fitness-v4-forensics.json` (`12889adc…`),
  `game-r-mutant-audit.json` (`0c2e3b93…`), `route-b-loss-curve-audit.json` (`1383f64b…`).
- `artifacts/experiments/fitness_v3/` — immutable invalid run.
- `artifacts/cache/fitness_v4/` — ignored; 356 cached calls; results are self-contained.

## Data Sources and Provenance

Gold world v0 unchanged. V4 DEV pool: 900 probes, hash `0a45154c…3dba05`, seed 20260907,
no model involvement in truth. Depth mechanism adapted from HML_V3 `projection/dense.py`
(`95e8a26`); shortcut audit adapted from HML_V3 `micromath/shortcut_v2.py`. No historical
score, hidden split or trained adapter imported.

## Decisions and Rationale

- V3 not repaired in place; V4 is a new version. `num_ctx` raised because B must let every
  founder be read in full.
- Per-mechanism gates with an explicit-positive level; aggregate pooling banned.
- Gates applied exactly after results: depth (.833), binder (.750) and delta (.500) failed
  the L0 gate; dependency failed validity (.528); precondition failed choice flip (.333).
  None was relaxed.
- The next instrument is V5 with a calibrated output budget, because the dominant failure is
  a controller/budget limit, not a representation or context result.
- Founders were not run because the frozen minimum (2 qualified mechanisms) was not met.

## Verification and Test Results

- `.venv/bin/python -m pytest` — 190 passed.
- `.venv/bin/ruff check .` — clean. `.venv/bin/ruff format --check .` — 198 files already formatted.
- `.venv/bin/mypy arena` — clean, 118 files.
- `fitness_v4 develop` — 356 calls, Q0 1.000, 0 qualified; `fitness_v4 status` —
  `FITNESS_V4_NOT_QUALIFIED`.
- `fitness_v5 develop` — 392 calls, Q0 1.000, 0 of 3 qualified, 2 of 3 explicit arms passing;
  `fitness_v5 status` — `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`.
  Result sha256 `0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`.
- 432 V5 rows: 264 correct, 120 semantic errors, 48 negative-control answers, and **zero**
  schema errors, output truncations, input truncations or parser errors.
- `fitness_v4_forensics` — 348 rows: 179 correct, 13 negative-control, 67 semantic error,
  59 reasoning overflow, 24 unsent (pre-guard), 6 flagged (post-guard).
- `game_r_mutant_audit` — 120/120 `GAME_R_COMPATIBLE`.
- Canonical validation and assurance suite: not re-run (no relevant code changed).

**Parallel next-stage branch `claude/phase-6-parallel-setup-9c6068` (2026-09-07), base `b82f8ed`.**
Run from that worktree with the shared venv, always via `python -m` (a bare `pytest` console
script imports the main checkout instead — see Risks):

- `python -m pytest` — **470 passed** (190 before this branch; 280 added, none regressed).
- `python -m ruff check .` — clean. `python -m ruff format --check .` — 223 files formatted.
- `python -m mypy arena` — clean, 125 files.
- `research/` excluded from the lint gate in `pyproject.toml` (one-off analysis scripts).
- Frozen artifacts re-verified unchanged at end of session: `GOAL.md`
  `43d8fcdb…0117b`; Phase-5 `result.json` `0c5b3271…97579`.
- **No model call, GPU minute, download or training run** was made by this branch.

## Known Failures and Limitations

- Under a sound protocol the Solver still cannot measure any mechanism that needs more than
  one lookup: it answers the same option every time (share 0.83 to 1.00 at hard levels).
- `formal_expression_depth` leaks: `first_mentioned_in_state` reaches 0.833 in the selected
  stratum because real Lean terms tend to mention the deeper identifier first.
- `alpha_normalize` mis-scopes a binder's type if a caller puts it at `args[1]`; not in any
  measurement path, pinned by a regression test.
- Two V4 instrument defects: representation-specific context pre-guard; level 0 is not a
  relation-stated positive.
- One model family, one seed; HML_V3's cross-reader failure is the standing warning.
- Nothing is known about any representation from V4.

## Risks and Technical Debt

- `fitness_v3.py` retains `num_ctx=8192` (historical); do not reuse for measurement.
- Context guard constants in `fitness_v4.py` are frozen with the instrument; V5 must replace
  them, not patch V4.
- Deep JSON nesting reaches 6.12 characters per token (measured maximum), against the guard's
  2.0 assumption; token-exact counting needs the model tokenizer, which Ollama 0.33.2 does not
  expose over its HTTP API.

## Local compute capability (verified 2026-09-07)

Lean `v4.10.0-rc1` installed and mathlib4 @ `29dcec07…` fully built (5,680 `.olean` files,
`Lean4Repl.olean` compiled), so fresh Lean state extraction and kernel-backed replay
attestation are possible offline with no download. Four local Solver families are installed
(`gemma4:12b`, `gemma4:31b`, `qwen38-rvn`, `qwen36-huihui`), which is what the next action
needs.

## Phase 6 complete (2026-09-07) — SOLVER_SPECIFIC_FAILURE_SUPPORTED

Frozen-V5 solver substitution. `qwen38-rvn` escapes the Phase-5 degeneracy completely
(paired exact McNemar p = 2.9e-11), qualifies `transitive_dependency` — the first mechanism
ever to qualify — and passes all three explicit-positive arms. Its two non-qualifying
mechanisms fail for the *opposite* reason to gemma's: one saturates at 1.000 at every level
(`VOID_CEILING`), the other is voided by a frontier-selector miscalibration rather than a
reading failure. The founder tournament is still not authorised (gate needs 2 qualified
mechanisms, got 1), so `GAME_R_NOT_RUN` and `RSTAR_NOT_IDENTIFIED` stand.

Full result: `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md`.

## Parallel next-stage branch (2026-09-07) — preparation, no experiment

Branch `claude/phase-6-parallel-setup-9c6068`, base `b82f8ed`. Built **alongside** the live Phase-6
run, deliberately off its critical path: no model call, no GPU minute, no download, no change to
any frozen artifact. Contamination of the live run was shown structurally impossible (every Arena
output path resolves from CWD; the only hardcoded absolute path in the package is a read-only glob
into `HML_V3` at `arena/environments/formal_structural.py:49`) and confirmed empirically.

**Measured findings** (all reproducible from `research/`, none requiring a model):

1. `WORLD_V0_NEXT_ACTION` is degenerate: model-free whole-target exact **676/676**, held-out
   **96/96**; **0.8195** with zero arithmetic; 7 of 8 target fields fully mechanical; unrepaired by
   identifier obfuscation. The historical `exact ≈ 1.000` is therefore not evidence of
   mathematical learning. `artifacts/reports/next_action_leakage.json`.
2. The five Route-B arms are hand-written codecs that **ignore the genome** — `_encode_payload`
   never reads `self.genome`; only `GenomePhenotypeLanguage` is genome-driven. Changing a gene
   changes nothing for those arms. Five of fourteen gene families are inert.
3. Six further parity defects that would silently bias Route B, including train/eval truncation on
   **opposite sides** (train left, eval right, neither logged) and a label-mask boundary that makes
   the number of supervised target tokens a function of representation length.
   `docs/ROUTE_B_PARITY_AUDIT.md`.
4. The V5 frontier selector aims at 0.625 while the gate requires ≥ 0.70 (the destroyed control is
   a constant 0.5000, verified 24/24 twin pairs byte-identical). Traced to V5 raising `gap_min`
   0.10 → 0.20 without moving the target. **It cost Phase 5 nothing** — the one in-window cell was
   already selected — and both naive fixes score *above* an oracle, i.e. convert noise into passes.
   `artifacts/reports/v5_selector_analysis.json`.
5. Canonical schema vs 368 real Lean states: **0 mapped losslessly**, 79.3% with loss, 20.7%
   unmappable. G1/G2≡G6/G3 confirmed REQUIRED; G7 and G8 **refuted**; four new gaps found.
   No schema change was made. `docs/CANONICAL_VNEXT_PILOT.md`.
6. Corpus reality: the richly-annotated reasoning corpus is **792 steps**, not ~300k; verification
   and richness are anti-correlated (nothing on disk is both); no owner-authored chain corpus
   beyond 10 hand-authored problems exists. A full LeanDojo Benchmark 4 trace (259,580 transitions,
   premise-annotated, same pinned mathlib commit) is **already local and unused**.

**New code, additive and unwired:** `arena/training/{route_b_data,verified_eval,gpu_authorisation}.py`,
`arena/corpus/{trace,contamination,provenance}.py`, additive flags on `prepare_matched_data.py`.

**Documents:** `PARALLEL_NEXT_STAGE_HANDOFF` · `PHASE6_INTEGRATION_MAP` · `ROUTE_B_V1_SPEC` ·
`ROUTE_B_PARITY_AUDIT` · `CORPUS_STRATEGY` · `REASONING_OPERATION_DISCOVERY` ·
`FUTURE_ENVIRONMENT_FAMILIES` · `CANONICAL_VNEXT_PILOT`.

**Not done, deliberately:** no Fitness V6, no founder tournament, no mutation campaign, no Route-B
run, no schema change, no mass ingestion, no reinterpretation of any recorded sentinel.

**Verified discrepancy in the published Phase-6 artifact (recorded, not adjudicated).**
`docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` declares `SOLVER_SPECIFIC_FAILURE_SUPPORTED` and
records `cache hits on the alternate solver | 0`. Counted read-only from
`result-qwen38-rvn_latest-bare.json`, the artifact contains **61** rows with `cache_hit == true`
(13 of 288 `ladder_rows`; 24 of 72 `formal_expression_depth`; 24 of 72 `transitive_dependency`).
An independent forensic audit reports the same 13 + 48 split. The literal preregistered
`INVALIDATION_RULE` ("cache hits > 0") therefore fires, though the hazard it was written to catch
— cache/model decoupling — does not appear present (the artifact carries qwen's digest, the bare
runtime has its own cache namespace, and the counts match the documented 06:16 relaunch plus
within-run reuse). Resolution belongs to the Phase-6 session and the project owner; see
`docs/PHASE6_INTEGRATION_MAP.md` §0b.

## 72-hour sprint (2026-09-07) — branch base reconciliation

This worktree now carries the Phase-6 result (`b3717c3`), the parallel next-stage machinery, and
the forensic-audit namespaces. The append-only ledger conflict was resolved by keeping **both**
sides in wall-clock order; no entry was rewritten.

**Phase 6 outcome, as published:** `SOLVER_SPECIFIC_FAILURE_SUPPORTED`. Substituting `qwen38-rvn`
for `gemma4:12b` on the frozen instrument escapes the degeneracy (paired exact McNemar
p = 2.9e-11 on the preregistered endpoint) and qualifies `transitive_dependency` — **the first
mechanism ever to qualify**. The failure mode inverts from floor to ceiling.

**Contested validity, recorded not resolved:** the qwen artifact carries 61 `cache_hit == true`
rows (13 ladder + 48 within-run reuse) against an invalidation rule of "cache hits > 0", verified
independently by two audits. This sprint therefore uses **no Phase-6 number as confirmatory
input**; the Qwen solver-escape is treated as descriptive evidence that qwen is the right scout
Solver, which is a design choice, not a result.

**The selector defect is now load-bearing.** Both the Phase-6 session and this project's own
frozen-data analysis independently found that the frontier selector minimises |accuracy − 0.625|
while the gap gate (destroyed control a constant 0.5000, `gap ≥ 0.20`) admits only
`positive ∈ [0.70, 0.85]`. The selector therefore prefers levels that cannot qualify. Phase 6
records that under a corrected target `formal_expression_depth` would have selected L2 (0.792) and
passed — giving two qualified mechanisms and authorising the founder tournament.

**This must not be done by re-scoring.** Re-aiming a selector after seeing the data is protocol
shopping, and simulation shows both naive re-aimed selectors score *above* an oracle that knows
the true accuracy — they convert sampling noise into passes
(`artifacts/reports/v5_selector_analysis.json`). The admissible route is: derive the target from
the gate arithmetic, preregister it, and **re-run fresh**.

**Fitness V7 preregistered (before any V7 call).** `docs/FITNESS_V7_PREREGISTRATION.md` corrects
two measured instrument defects as a package: the frontier target becomes a quantity derived from
the gate arithmetic (0.775, inside the [0.70, 0.85] window) instead of a stranded constant at
0.625, and the shortcut audit runs at every level with a new `positive − best_shortcut ≥ 0.10`
gate. V7 is **strictly stricter** than V5 and may qualify fewer mechanisms; the honest expectation
is recorded in the spec. Compute ledger: `docs/SPRINT_COMPUTE_LEDGER.md`.

**Three real formal task families built and shortcut-gated (hours 1–5).** Constructed from
250,814 real Lean transitions in the LeanDojo train split, each gated on a model-free shortcut
attack before any Solver call:

| family | usable items | best shortcut | chance | ceiling | verdict |
|---|---|---|---|---|---|
| premise selection | 63,831 | 0.327 | 0.167 | 0.45 | READY |
| rewrite direction | 3,466 controlled | 0.6026 | 0.50 | 0.65 | READY under within-lemma control |
| legal transformation | 24,000 (12,000 pairs) | 0.5197 graded | 0.50 | 0.65 | READY (graded arm) |

Kills and refutations: the "36.9% reverse rewrites" estimate is wrong (measured **19.4%** per
element / 25.1% per tactic); rewrite direction breached at 0.7085 uncontrolled on lemma-name
features alone; premise-selection rung `L1_cross_module` breached at 0.866 and was **rejected**
after one control attempt reached 0.644; legal transformation killed `violated_precondition`
(0.777) and `wrong_successor` (0.664).

**BLOCKING FINDING — the new families cannot carry Game R.** All three emit **raw Lean
pretty-printed strings** and contain zero `CanonicalState`/`CanonicalAction` references (verified
by grep). Game R requires re-rendering identical canonical content through eight representations;
a pre-rendered string **fixes R**. These families measure *solver capability* on real mathematical
decisions — a different and valuable game — but only the canonical `formal_structural` probe bank
can carry Game R today. Converting them to canonical form is a specified, separable task.

**FITNESS V7 CONCLUDED — `V7_SHORTCUT_DOMINATED`, 0 of 3 mechanisms qualified.** 864 rows, all
`FRESH` (zero cache hits, zero `CROSS_CONDITION`), Q0 1.000, every ladder value reproducing Phase 6
exactly. `formal_expression_depth` L2: accuracy 0.7917 vs shortcut **0.8333** (margin −0.0417) —
and it fails **V5's own frozen** `shortcut_rule_max = 0.75`, refuting Phase-6 §11's claim that a
selector fix alone would have qualified it. `transitive_dependency` L3: accuracy 0.750 vs shortcut
0.667, missing the preregistered 0.10 margin by **0.017** — the only mechanism ever to qualify does
so under V5's rules but not under V7's stricter one. `precondition_conjunction`: `VOID_CEILING`,
best shortcut at chance (0.500) — a ceiling problem, not a shortcut problem, and the one mechanism
worth extending upward. **All other gates PASS: the instrument is sound; the mechanisms are not.**
No founder tournament (gate needs 2, got 0). Full result: `docs/FITNESS_V7_RESULT.md`.

**Astra canonical premise bridge merged research-only** (`docs/astra/`, `research/astra/`).
Independently re-verified here: 37 tests pass; audit `GAME_R_SOURCE_PROJECTION_PARITY_PASS` over
300 items × 5 representations. Parity holds at the **source-projection** layer only — its own scope
states "not Lean kernel semantics" — so it is not yet a Game-R instrument.

**Fitness V7 (superseded note).** Launched 12:38:56 against `qwen38-rvn` bare after digest verification;
872 planned calls / 900 budget; Q0 1.000. Result unknown at time of writing.

**Repository hygiene.** `research/environments/measurements/train_premise_citation_counts.json`
(2.4 MB, derived, regenerable, unvalidated) was swept in by `git add -A` at `cf1b07f` and removed
immediately afterwards; it is now gitignored.

**TRAINING_LANGUAGE_V0 SHIPPED (Deliverable A).** `releases/TRAINING_LANGUAGE_V0/`,
`package_hash` `443c8f7950147b82…`, evidence level **`TRAINING_LANGUAGE_V0_BASELINE`**. Small
extensible core (ten record kinds + an action block); domains are library *values*, not grammar.
Every REQUIRED canonical-vNext gap handled natively (multi-goal with per-goal context, obligation
scope, metavariable/substitution, structured types, let-values); G7 explicitly deferred. Targets
render through the **same surface as inputs**, removing parity defect D3 (JSON's
input-grammar = output-grammar advantage) by construction. 279 release tests pass; determinism
measured by AST scan, attribute-order rotation and `PYTHONHASHSEED` variation; round-trip exact.
The `HONEST` profile is **rejected** by the frozen `NativeVerifier` with `UNBOUND_VARIABLE` /
`UNKNOWN_ACTION_TARGET` / `UNKNOWN_SCOPE` — a property of the verifier, carried not fixed.

**Phase-6 §11 refuted.** `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` claims a corrected
frontier target would have qualified `formal_expression_depth` at L2 and authorised a founder
tournament. It would not: V5's own frozen `shortcut_rule_max` is **0.75**
(`fitness_v5.py:225`), while `first_mentioned_in_state` scores **0.8333 at L2** and **1.0000 at
L1** — both in-window levels already exceeded V5's own threshold. V5 never revealed this because it
audits shortcuts only at the selected frontier and reports only `failures[0]`.

**Live-cache incident (recorded, no scientific corruption).** A subagent deleted
`artifacts/cache/` three times while V7 was running, destroying ~55 live rows. Each identity is
visited once per run, so nothing was re-called from stale state; **resume capability only** was
lost (~10 min of Solver time if interrupted). The run holds the final module and continued.

**Specifications frozen.** `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md` (three families, sources,
ladders, shortcut protocol, every rejection with its number) and `docs/TRAINING_DATA_FACTORY.md`
(the `tl0-training-record-v1` pipeline, per-source trust tiers, and the real Tier-A replay cost).

**Sealed before any sprint work began.** `artifacts/manifests/SEALED_SPLITS.json` records sha256
and byte counts for four held-out LeanDojo splits. Permitted development sources are only
`random/train.json`, `corpus.jsonl`, and `steps.jsonl` filtered to `split == "train"`.

**Forensic audit merged (additive).** `docs/codex_audit/` and `research/codex_audit/` from
`codex/forensic-audit-20260907`, verified to touch no file outside those namespaces. Treated as
REPORT_ONLY input.

**Primary data asset verified.** LeanDojo Benchmark 4, leandojo 2.0.0, mathlib4
`29dcec074de168ac2bf835a77ef68bbe069194c5`. `steps.jsonl` = 259,580 rows (train 250,814 / val
4,260 / test 4,506); 167,779 (64.6%) cite ≥1 premise; `rw` commonest head at 48,991. A built
mathlib at that commit exists locally (18 GB, 5,680 `.olean`).

## Sprint close-out (2026-09-07)

`docs/72_HOUR_SPRINT_HANDOFF.md` is the zero-context handoff. `docs/CURRENT_STATE.md` was
reconciled: a new head reflects the sprint sentinels and all prior content is preserved verbatim
below a "Historical state (pre-sprint)" divider.

**Final sentinels.** `GAME_R_INSTRUMENT_NOT_QUALIFIED` · `RSTAR_NOT_IDENTIFIED` ·
`TRAINING_LANGUAGE_V0_BASELINE` (shipped, `package_hash` `443c8f7950147b82…`).

**Compute.** Zero cloud spend, re-verified at close: `a100-40`, `h3` and `a100` all TERMINATED.
V7 ran locally through Ollama (864 calls, ~1.7 h). Matched fine-tuning would require an A100 —
no `torch` is installed locally and the machine is Apple Silicon.

**Tournament harness consolidated.** `arena/experiments/game_r_formal_v1.py` (+60 tests) was
recovered from the scratch worktree at close-out. It provides an eight-component cache identity
with per-component tests, a `FRESH`/`SAME_CONDITION_REUSE`/`CROSS_CONDITION` scope (the distinction
Phase 6 lacked), arena parity that refuses byte-identical arms, a derived frontier target, and a
`--dry-run` stub solver. **It has never made a model call.**

**The single most expensive successor mistake** would be running a founder tournament on the three
new task families: they emit pre-rendered Lean strings, so eight representation arms would receive
byte-identical inputs. The handoff leads with this.

## V7 Total Forensic Audit (2026-09-07) — `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`

`docs/V7_TOTAL_FORENSIC_AUDIT.md`. Nine auditors briefed to destroy the argument, plus integrator
verification. **No experiment run, no threshold changed, no result re-scored.**

**The representation hypothesis has not failed — it has never been tested.** No experiment in
V1→V7 has ever scored two representations against a Solver. All 864 V7 rows carry one
`candidate_id`; V4's frozen manifest has an 8-founder roster with `probes: []`; the 120 mutants
appear only in a deterministic Gate-0 check.

**V7's three verdicts do not share a fate.** `formal_expression_depth` is **correctly voided** —
solvable at 1.000 by bracket counting on the rendered prompt across all eight surfaces, so its
optimal strategy is *representation-invariant*. `transitive_dependency`'s void is **not supported**
— one row from qualifying, comparator below its own null mean, power 0.069, McNemar p = 0.625.
`precondition_conjunction` is **balanced by construction** (verified in source) and failed on
ceiling alone.

**Sharpened by the ninth auditor, at population scale:** `transitive_dependency`'s voiding rule is
at **chance (0.5175)** on 800 positives; its true margin is 0.149, or 0.110 against the strongest
adversary — **both clear the 0.10 gate**. Conversely `formal_expression_depth` sits at 1.000/0.882/
0.861, so that void is **robust and understated**. The same instrument was simultaneously too
lenient on one mechanism and too harsh on another. The shortcut family is also effectively **two
rules, not seven** (four are structurally pinned at 0.5000), and Arena's port **deleted the
Bonferroni + Clopper–Pearson correction its own cited ancestor used** — leaving a 0.75 threshold
that sits *below* the null mean of a max-over-7 and is crossed by noise 67% of the time.
A correction note has been appended to `docs/FITNESS_V7_RESULT.md`.

**The instrument audits a string the Solver never receives** (`canonical_json` vs the rendered
surface); the gated cue is at exact chance on the real input in all twelve cells. The dominant
error mode is **position anchoring** (56.5%), which the gates cannot detect. 67% of probes are
synthetic but stamped formal. **V7's arithmetic, by contrast, recomputes exactly** — 252 checks,
0 mismatches.

**Correction to an earlier claim in this project's own record:** splits were **not** sealed before
agent reads. `novel_premises/{val,test}` were parsed 5h16m earlier; the premise-selection promotion
pool is spent, at design level.

**Diagnosis:** flat landscape 0.02 · instruments confounded / untested **0.88** · mixed 0.10.

Audit tree closed (110 files, all under `research/audit/`).
Audit tree is complete and self-consistent: every reported number sits beside its generator.
Audit working files are under `research/audit/` (108 files, reproducible, zero model calls); three
large regenerable intermediates are gitignored and named in `research/audit/README.md`.

## Plain-language state

`docs/WHAT_WORKS_WHAT_DOESNT.md` is the one-page answer to "what works, what doesn't", each line
backed by a file or artifact. Summary: **the machinery is real and mostly sound; the scientific
question the project exists to answer has never been asked**, because no experiment has ever scored
two representations against a Solver.

## Mission reset — Phase B documentation set (2026-09-08)

The reset's design documents are complete and committed. Each is grounded in measurement, and the
four findings below changed the plan rather than confirming it.

| Document | What it settles |
|---|---|
| `HAMILTONIAN_CHESS_META_GOAL.md` | The mission, the four layers and which may evolve, the truth-preservation invariant, the novelty boundary, the three standing risks |
| `HAMILTONIAN_CHESS_META_MDP.md` | The nested games: inner `M_L = (S, A, T_K, r, Omega_L)` and the outer language-evolution MDP; what exists vs what is missing |
| `HAMILTONIAN_CHESS_REPO_REMAP.md` | 57 components classified KEEP 18 / REFACTOR 13 / DEMOTE 7 / ARCHIVE 12 / MISSING 7 |
| `HAMILTONIAN_PRIOR_ART_BOUNDARY.md` | `NOVEL_ONLY_IN_COMBINATION`, ~70 verified citations, the narrowest defensible claim |
| `LANGUAGE_META_GENOME_V0.md` | `LanguageMetaGenomeV0`: six gene families, which are ACTIVE in V0, and the cost of each |
| `LONG_HORIZON_FITNESS_V0.md` | The fitness vector, the multi-fidelity ladder, how `J_horizon` is measured |
| `LANGUAGE_FITNESS_MEMORY.md` | The durable record schema that a surrogate is eventually trained on |
| `VERIFIED_TRAJECTORY_ARENA_V0.md` | The trajectory world, resolved by measurement |

**Four findings that changed the plan.**

1. **The prior-art verdict is `NOVEL_ONLY_IN_COMBINATION`.** A hand-designed machine-facing proof
   language already reports +20-29 points of kernel-verified pass@1 in this exact domain, and
   automated search over agent-facing representations is published. The architecture alone is not
   a contribution. Worse for the headline thesis: "language advantage grows with horizon" is
   **partly a tautology** (`p^n` vs `q^n`) and **metric-dependent** — the absolute accuracy gap is
   *unimodal* in depth, so the claim is false under one natural metric. Only a **rank reversal**
   across horizon or **super-compounding** escapes this, and the metric must be preregistered.
2. **The language layer has two distinct defects, both measured.** The eight registered seed codecs
   are genome-blind by construction (pre-instantiated singletons; **0 of 44** one-gene mutations
   change a byte). `GenomePhenotypeLanguage` is genome-driven (**24 of 44**) but its gene-to-byte
   map is narrow: `_grammar_encode` has **three** branches, not eight, so five of eight grammar
   families alias one JSON encoder, and `L3_JSON_AST`/`L6_GRAPH_TRIPLES` compute a byte-identical
   role map. Consequence for the loop: **13 of 35 legal single-gene children of the JSON seed are
   byte-identical clones** — 37% of the mutation neighbourhood is a no-op.
3. **The trajectory world is live Lean replay**, and the toolchain exists today: a complete 18 GB
   mathlib4 build (5,680 `.olean`) pinned to Lean 4.10.0-rc1 with a compiled REPL giving persistent
   addressable state and branching, at ~193 tactic steps/s warm. The corpus
   (`.../Hamiltonian-Labs/hml_research_artifacts/.../random/train.json`, 373 MB, CC BY 2.0) has
   118,517 records, 59,557 with tactics, 250,814 steps, and **1,605 theorems needing >=20 tactics**
   — all independently re-verified. Recorded proofs are **trees, not chains** (only 67.3% of
   adjacent pairs chain), so the arena must replay live.
4. **Two measured traps.** Raw Lean state string equality scores **40.6%** where real semantic
   agreement is **98.1%**, so a string-comparing verifier would reject 59.4% of correct steps —
   truth must stay with the backend state id. And mathlib is transitively exposed to any solver, so
   the defensible phrasing is "long-horizon **execution under kernel verification**", not
   "reasoning".

**Verified independently by the integrator** (not taken on a subagent's word): maximum horizon in
the repository is 1 (the only `CanonicalTrajectory` construction passes a one-element tuple); the
semantic gate accepts all 8 honest surfaces and refuses a renderer that drops a `holds(...)`
assumption; the 0-of-44 and 24-of-44 genome sensitivity figures; the Lean toolchain and the corpus
counts.

## Current Blockers

1. **The meta-game has no verified trajectory world.** Every existing environment is a
   single-step, two-option probe. Long-horizon reasoning — the central quantity of the new
   mission — cannot be measured by anything currently in the repository. This is the top blocker.
2. **The preregistered Phase-8 Solver no longer exists** on this machine and is unrecoverable.
   Any future Solver-facing work must record a new Solver decision from scratch. A replacement
   Qwen was being downloaded as of 2026-09-08.
3. **The seed language population is narrower than assumed** (§ Current Stage): an evolutionary
   search seeded from these eight surfaces starts from fewer independent design points than the
   roster implies.
4. GPU spend remains gated by `arena/training/gpu_authorisation.py` (fail-closed).
5. `WORLD_V0_NEXT_ACTION` remains degenerate — a model-free predictor reproduces the gold target
   on 676/676 tasks. Unchanged by this commit.

## Exact Next Actions

**Superseding all earlier next-action lists in this document.** The Phase-8 and V-series next
actions below are retained for history and are **not** authorised.

1. Complete the mission-reset documentation set: meta-goal, nested-MDP definition, repository
   remap, prior-art boundary, language meta-genome, long-horizon fitness, verified-trajectory
   arena, language-fitness memory.
2. Determine, from **local** assets only, the smallest source of genuine multi-step verified
   mathematical trajectories, and specify the V0 arena on it.
3. Implement the thin outer loop (`HAMILTONIAN_CHESS_V0`): population → choose parent → mutate →
   semantic gate → evaluate → record fitness → archive → next generation. The target is
   **end-to-end executability**, not a scientific discovery.
4. Do **not** run the Phase-8 founder tournament, invent a new hand-designed language, train an
   RL Architect, or run large GPU jobs.

**Superseding detail from the parallel next-stage branch** (`docs/PARALLEL_NEXT_STAGE_HANDOFF.md`
§7, `docs/PHASE6_INTEGRATION_MAP.md`):

6. Item 3 above cannot be executed as written: the historical Route-B task family is degenerate
   (see Blockers). `docs/ROUTE_B_V1_SPEC.md` names a replacement slice and a headroom gate that
   must pass **before** any GPU minute.
7. Item 4 understates the leak. `first_mentioned_in_state` is **1.000** on the shallow stratum,
   **0.9167** at deep L3 and **0.8125** pooled over the four-level bank — not 0.833. Filtering
   alone cannot rescue that mechanism.
8. Adopt the fail-fast shortcut check (`docs/FUTURE_ENVIRONMENT_FAMILIES.md` §5) as a
   precondition on every future task family: fit a bounded model-free predictor on train, evaluate
   held-out against a preregistered ceiling, reject before writing the instrument. Minutes of CPU,
   no model call.
9. Then build premise selection from the LeanDojo trace already on disk (~163,300 items, real
   distractors, a `novel_premises` OOD split, zero download) — **sealing
   `novel_premises/{val,test}.json` first**.
10. Pin `gemma4:12b`'s training cutoff. It is unrecorded, so every temporal-holdout OOD claim in
    the project is currently a hypothesis rather than a holdout.
