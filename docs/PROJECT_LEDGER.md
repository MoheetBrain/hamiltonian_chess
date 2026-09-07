# Project Ledger

Append-only. One chronological entry per commit. Never rewrite or delete an entry except to
correct a demonstrable factual error, and record that correction inside the entry itself.

---

## 2026-09-05 — First Tier-2 matched adaptation: the arena gets a real training runner

**Date and time.** 2026-09-05, 21:00–22:00 UTC. **Branch.** `codex/arena-v0-fitness`.
**Project stage.** `TIER2_MATCHED_ADAPTATION_FIRST_RUN`.

**Objective of the change.** Decide, before investing in open-ended language evolution,
whether matched adaptation produces a representation-dependent machine-fitness signal, or
whether the fitness landscape is flat. `docs/FOUR_DAY_SPRINT.md` Day 3 named this as the
highest-information next action and it was the one unchecked box blocking `R*-V0`.

**Files and systems changed.** New: `arena/training/prepare_matched_data.py` (matched dataset
construction and split), `arena/training/gpu_matched_runner.py` (the explicit Tier-2 runner
that `matched_adaptation.py` delegates to), `arena/training/analyse_sprint.py` (paired
statistics), `docs/PROJECT_STATUS.md`, `docs/PROJECT_LEDGER.md`. No canonical schema, world
generator, language surface or assurance component was touched; Arena truth is unchanged.

**What was completed.** A full five-arm matched NEXT_ACTION adaptation on one A100 80GB under
a hard 55-minute budget, with successive halving across three stages. Results are recorded in
`docs/PROJECT_STATUS.md` and in the run artefacts.

**Decisions made and why.**

- **A runner was written rather than the CLI extended.** `docs/ARENA_PROTOCOL.md` Tier 2 says
  the generic CLI must refuse to imply a Tier-2 run occurred and that a concrete runner must
  supply model and training evidence. The runner records torch/transformers/peft versions,
  CUDA, GPU name, base model revision digest and tokenizer into its own output.
- **Every arm reloads the same base checkpoint.** The base `state_dict` is cloned once and
  restored before each arm, so no arm inherits another's weights. This is the single most
  likely silent invalidator of a multi-arm adaptation and it is enforced in code.
- **EXAMPLE_MATCHED was the primary regime and token counts are reported separately.** The
  arms differ in tokens by construction (S-expression costs 1.39x the compact symbolic arm).
  Equalising them would be a different experiment; conflating the two would be the whole
  result. The protocol's warning against pretending the regimes are equivalent is honoured by
  reporting the token ratios beside every accuracy.
- **The halving rule was fixed before any score was read**, in `HALVING_RULE`, with a 0.06
  minimum margin so an arm is never eliminated on a 1–2 item difference.
- **The split is disjoint and domain-stratified**, so no canonical world is both trained on
  and evaluated on, for any arm.

**Tests and verification actually executed.**

- `python -m arena.training.prepare_matched_data` — 5 arms x 676 worlds, split 580/48/48;
  `assert_matched_semantics` PASS; identical target hashes across arms confirmed; distinct
  input hashes across arms confirmed.
- `nvidia-smi` on the instance — NVIDIA A100-SXM4-80GB, driver 580.173.02, CUDA 13.0.
- `torch.cuda.is_available()` — True, torch 2.9.1+cu129, transformers 5.15.0, peft 0.20.0.
- `gpu_matched_runner.py` — executed; per-stage results in `gpu_sprint_results.json`.
- `analyse_sprint.py` — executed on the results; paired bootstrap and Wilson intervals.
- The repository's own test suite was **not** run in this session.

**Results and failures.** See `docs/PROJECT_STATUS.md` for the table and the verdict. The
dominant limitation is that the adapted task saturates: every arm exceeds 0.83 exact match
after Stage A, so the instrument has little headroom and differences at the top compress into
the noise band of a 48-item slice. This is the same class of problem `docs/CLAUDE_HANDOFF.md`
records for the V2 calibration headroom gate, and it is reported rather than worked around.

**Unresolved uncertainty.**

- One base model, one seed, one adaptation configuration. No replication.
- 48 evaluation items per stage: one item is 2.1 percentage points.
- `assert_matched_semantics` is vacuously true on an empty mapping; the arm count is asserted
  separately in `prepare_matched_data.py`. The guard itself should be strengthened.
- The verified-transition rate here checks that the emitted action is well-formed for the
  oracle (required keys, right shapes). It is **not** a claim that the action is optimal or
  that a domain oracle accepted it.

**Effect on the overall project.** The Day 3 box "execute matched short adaptation against
four strong controls" is now evidenced rather than aspirational, and the decision on whether
to build the evolutionary search engine rests on measured paired comparisons instead of
static compactness. `R*-V0` remains unfrozen.

**Next intended step.** Recorded in `docs/PROJECT_STATUS.md` under Exact Next Actions.

---

## 2026-09-06 — Harden assert_matched_semantics so empty candidate sets fail closed

**Date and time.** 2026-09-06. **Branch.** `codex/arena-v0-fitness`.
**Project stage.** `TIER2_MATCHED_ADAPTATION_FIRST_RUN`.

**Objective of the change.** Close the guard defect recorded in the previous entry before it
can invalidate another matched run.

**Files and systems changed.** `arena/training/render_dataset.py`, `docs/PROJECT_STATUS.md`,
`docs/PROJECT_LEDGER.md`. No canonical schema, world, language surface or verifier touched.

**What was completed.** `assert_matched_semantics` now rejects: fewer than two candidate
surfaces, any empty arm, arms of differing length, and two arms whose rendered inputs are
byte-identical. The original checks on identical canonical trajectories and identical target
hashes are unchanged.

**Decisions made and why.** The byte-identical-inputs check was added beyond the reported
defect because two surfaces that render the same bytes are the same experiment run twice, and
a difference between them could only be noise — the same class of error as the
`DEPTH_ADAPTIVE`/`DUAL_VIEW` duplicate found in the HML hard-regime comparison.

**Tests and verification actually executed.**
- Six degenerate cases (empty mapping, one arm, empty arm, identical inputs, length mismatch,
  target mismatch) — **all six raise**; a valid matched pair is still accepted.
- `python -m arena.training.prepare_matched_data` — the real five-arm pipeline still passes.
- `.venv/bin/python -m pytest` — **122 passed**.

**Failures and unresolved uncertainty.** None introduced. The saturation limitation on the
NEXT_ACTION task is unchanged and remains the blocking issue for ranking representations.

**Effect on the overall project.** A matched-adaptation run can no longer report PASS over
nothing. This does not change any measured result.

**Next intended step.** Governed by the HML kill gate: the arena headroom rebuild proceeds
only if `PATH_TO_ROOT` replicates across two readers.

---

## 2026-09-06 — Takeover: V3 invalidation diagnosed, Fitness V4 preregistered

**Date and time.** 2026-09-06, evening, Europe/London. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb` (worktree from `codex/arena-v0-fitness` at
`3995227`). **Project stage.** `EXPERIMENT_INVALID` (V3) → `FITNESS_V4_PREREGISTERED`.

**Objective of the change.** Build a valid, discriminating, versioned Game-R fitness instrument
that fixes the exact failure of V3, and preregister it before any model call.

**Files and systems changed.** New: `arena/experiments/fitness_v4.py`,
`tests/experiments/test_fitness_v4.py`, `docs/FITNESS_V4_SPEC.md`, `docs/GAME_R_STATUS.md`.
Rewritten: `docs/PROJECT_STATUS.md`, `docs/CURRENT_STATE.md`. Appended: this ledger. No
canonical schema, world generator, verifier, language surface, V1/V2/V3 code or artifact was
touched. `GOAL.md` hash verified equal to `43d8fcdb…20117b` and not modified.

**What was completed.**

- Full read of `GOAL.md`, every listed doc, and all source areas; reconciliation of docs against
  code, artifacts and git history. Found `PROJECT_STATUS.md`/`PROJECT_LEDGER.md` three commits
  stale (Phase-3 commits were made outside the ledger protocol).
- Diagnosis of V3 from its committed rows: every malformed row has `prompt_eval_count=4099`;
  `~/.ollama/logs/server-*.log` shows `truncating input prompt limit=4099 prompt=17072`. The
  JSON-AST state-delta prompt is ≈15.6K tokens against `num_ctx=8192`. The state-delta "floor",
  the complexity-2 "malformed" behaviour and Compact Symbolic's two wins were all context
  truncation. Reproduced: same prompt at 8192 → prose; at 32768 → valid JSON.
- Cross-repository check: HML_V3 local HEAD (`95e8a26`) has since closed its own static thesis
  (`STATIC_REPRESENTATION_THESIS_V1: NOT SUPPORTED`): `PATH_TO_ROOT` failed a two-reader kill
  gate and its original advantage was a bootstrap RNG defect (`FM-057`). Its replicated diagnostic
  result (identity recurrence inside deep expressions causes reading collapse; external clutter
  null) is adopted as V4's first mechanism. The previous Arena ledger entry conditioned the
  headroom rebuild on `PATH_TO_ROOT` replicating; it did not replicate, but `GOAL.md` (frozen
  later) makes Game R the binding first game, so V4 proceeds under GOAL rather than under HML_V3's
  pivot, and this tension is recorded here rather than hidden.
- V4 instrument: five mechanisms × five-level ladders, six-probe balanced families, independent
  truth re-derivation per mechanism, DEV-only frontier selection, per-mechanism qualification with
  void codes, symmetric shortcut audit, context guard, Game-R genome enforcement, information
  parity assertion, paired founder statistics with Holm and clustered bootstrap.

**Decisions made and why.** Recorded in `docs/PROJECT_STATUS.md` (Decisions and Rationale) and
`docs/FITNESS_V4_SPEC.md` §3–§13. Key ones: new version rather than in-place V3 repair; `num_ctx`
32768 because `B` must let every founder be read in full; structure not clutter as the difficulty
axis; explicit-positive level per mechanism; Track-C excluded from Game R; Route A now, Route B
deferred; practical effect required for promotion.

**Tests and verification actually executed.**

- `.venv/bin/python -m pytest -q` — 185 passed.
- `.venv/bin/ruff check .` — All checks passed. `.venv/bin/ruff format --check .` — 179 files
  already formatted. `.venv/bin/mypy arena` — no issues in 111 files.
- `python -m arena.experiments.fitness_v4 materialize` — 150 families, 900 probes, hash
  `0a45154c532a1a61ef77cf107d4d6bc957cb0be46f4719912b784605043dba05`, shortcut audit CLEAN.
- Two diagnostic Ollama calls (above). No V4 DEV or founder call was made.
- Canonical validation and assurance suite: not run (no relevant code changed).

**Results.** Instrument built and preregistered. No fitness measurement exists yet under V4.

**Failures or unresolved uncertainty.** Whether any V4 ladder level lands in the frontier band for
`gemma4:12b` is unknown until DEV runs. Single model family throughout.

**Effect on the overall project.** V3's invalidation now has a mechanistic explanation and a
regression guard. The Game-R programme has a preregistered instrument with per-mechanism gates.

**Next intended step.** Run `develop`; freeze and commit if ≥ 2 mechanisms qualify; then founders.

---

## 2026-09-06 — Fitness V4 DEV complete: 0 of 5 mechanisms qualify; stopping condition recorded

**Date and time.** 2026-09-06, 21:52–22:26 BST run window, entry written afterwards.
**Branch.** `claude/hamiltonian-arena-takeover-caa2eb` → fast-forward to
`codex/arena-v0-fitness`. **Project stage.** `FITNESS_V4_PREREGISTERED` →
`FITNESS_V4_NOT_QUALIFIED`.

**Objective of the change.** Execute the preregistered V4 DEV ladder, apply the frozen gates
exactly, record the outcome, and leave a complete handoff.

**Files and systems changed.** New: `arena/experiments/fitness_v4_forensics.py`,
`arena/experiments/fitness_v4_preflight.py`, `arena/experiments/game_r_mutant_audit.py`,
`tests/experiments/test_fitness_v4_forensics.py`, `tests/experiments/test_game_r_mutant_audit.py`,
`docs/FITNESS_V4_FAILURE_ANALYSIS.md`, `docs/V4_1_PROTOCOL_CALIBRATION_PROPOSAL.md`,
`docs/ROUTE_B_HISTORICAL_AUDIT.md`, `docs/GAME_R_MUTATION_CAMPAIGN_PLAN.md`,
`docs/CANONICAL_VNEXT_GAP_REPORT.md`, `docs/CLAUDE_FINAL_HANDOFF.md`,
`artifacts/experiments/fitness_v4/{development/result.json,frozen_manifest.json,not_qualified.json}`,
`artifacts/reports/{fitness-v4-forensics,game-r-mutant-audit,route-b-loss-curve-audit}.json`.
Rewritten: `docs/PROJECT_STATUS.md`, `docs/CURRENT_STATE.md`, `docs/GAME_R_STATUS.md`. No
change to `arena/experiments/fitness_v4.py` after the preregistration commit `88bacc8`; no
canonical, verifier, language-surface, V1/V2/V3 code or artifact touched; `GOAL.md` unmodified.

**What was completed.** The DEV run (356 calls, Q0 1.000) finished without interruption using
the cache. Per-mechanism verdicts: depth VOID_INSTRUMENT_LIMIT (L0 .833), transitive
dependency VOID_VALIDITY (.528 valid at L2), binder scope VOID_INSTRUMENT_LIMIT (L0 .750),
precondition VOID_FLIP (choice flip .333 at L1), state delta VOID_INSTRUMENT_LIMIT (L0 .500).
`freeze` wrote a manifest with `qualified=false` and `not_qualified.json`. Founders were not
run. Forensics classified all 348 rows; the mutant audit classified all 120 mutants as
`GAME_R_COMPATIBLE`; Route B loss curves were reconstructed at 16/32/64/128/224 examples.

**Decisions made and why.** No gate was relaxed after results. The dominant cause (59 rows of
prose reasoning cut at 64 tokens; constant-"A" at hard levels) is a controller/budget limit,
so the next instrument changes `C`/`B` under a new version (V4.1 calibration, then V5) rather
than adjusting V4. Two V4 instrument defects (character-based context guard; level 0 not a
relation-stated positive) are recorded for V5, not patched in V4.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest -q` — 188 passed.
- `.venv/bin/ruff check .` — All checks passed. `.venv/bin/ruff format --check .` — 193 files
  already formatted. `.venv/bin/mypy arena` — no issues in 114 files.
- `python -m arena.experiments.fitness_v4 develop` / `freeze` / `status` — as above.
- `python -m arena.experiments.fitness_v4_forensics`, `game_r_mutant_audit` — as above.
- Canonical validation and assurance suite: not run (no relevant code changed).

**Results.** `FITNESS_V4_NOT_QUALIFIED`. No representation evidence exists.

**Failures or unresolved uncertainty.** Whether a non-sabotaging output budget exists for
`gemma4:12b` is unknown until the calibration runs. Single model family throughout.

**Effect on the overall project.** Game R still lacks a valid instrument, but the reasons are
now mechanistic and versioned: input truncation (V3), then output-budget/controller limit and
a position policy under uncertainty (V4). The next instrument's requirements are specified.

**Next intended step.** Authorise the DEV-only budget calibration; then V5 preregistration.

---

## 2026-09-07 — Phase 5: the protocol was the artifact; Fitness V5 moves the blocker to the Solver

**Date and time.** 2026-09-07, 00:31–02:30 BST. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb` → fast-forward to `codex/arena-v0-fitness`.
**Project stage.** `FITNESS_V4_NOT_QUALIFIED` →
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`.

**Objective.** Execute the Phase-5 directive: close V4, repair the response protocol, ground
the probes in verified formal states, preregister and run Fitness V5, and stop honestly if the
evidence does not earn a founder tournament.

**Files and systems changed.** New: `arena/provenance.py`, `arena/environments/`
(`formal_structural.py`), `arena/experiments/fitness_v5.py`, `docs/FITNESS_V5_SPEC.md`,
`docs/FITNESS_V5_RESULT.md`, `artifacts/experiments/fitness_v5/development/result.json`.
Modified: `arena/experiments/game_r_mutant_audit.py` (surface-inventory correction),
`tests/experiments/test_game_r_mutant_audit.py`, `tests/canonical/test_schema.py`,
`docs/{CURRENT_STATE,PROJECT_STATUS,GAME_R_STATUS}.md`, supersession banners on three
historical docs. `GOAL.md`, Gold, and all V1–V4 artifacts untouched.

**Ten subagents were used** for parallel read-only investigation (state audit, protocol
forensics, statistical design, two donor-repo miners, formal-data inventory, population audit,
schema audit, pilot design, red team). All writing and integration was done centrally, which
also removed any file-conflict risk.

**What was completed.**

- **Protocol repair, measured.** Ollama's grammar-constrained `format` schema was verified to
  work on this build. It recovers 9 of 9 previously-failed rows, takes parse rate from 15/24
  to 24/24, and is answer-neutral (agreement 1.000). Raising `num_predict` to 512 recovers 0
  of 9 and destabilises two rows. V4's character context guard was shown to be an artifact:
  rows it voided truly used 7,396 / 9,498 / 23,215 tokens against a 32,448 limit, and at
  binder L3 it deleted exactly the counterfactual arm.
- **Formal probe bank.** 1,150 real elaborated Lean 4 transitions were located locally
  (donor HML_V3 @ `95e8a26`); 461 pass structural eligibility; the donor's 126 sealed source
  files are excluded by name and never read. Measured that unrestricted real states render
  6.5x (median) to 23.7x (max) longer across the eight surfaces, so probes are restricted to
  states where every surface fits 30,000 characters, leaving 104 states over 95 mathlib files.
- **Fitness V5 preregistered and run.** 392 calls. 0 of 3 mechanisms qualified; 2 of 3
  explicit-positive arms passed (0.917, 1.000); 0 malformed rows in 432. The preregistered
  abort clause fired.
- **Mutant-audit correction.** Two independent reviews found the earlier audit's
  recovered-state inventory was a strict coarsening of `mathematical_hash`, making
  `GAME_P_ONLY` unreachable. Replaced with an inventory of the rendered surface decoded
  through the base codec, with a regression test proving it fires on a candidate that emits a
  derived relation and drops it on parse. 120/120 still holds, now meaningfully.

**Decisions made and why.** No gate was relaxed after results. The choice-flip gate was
replaced by a largest-answer-share gate *before* the run, on simulation evidence that
choice-flip passes a coin-flipper 65.6% of the time at six families; the new gate is what
caught the constant-answer collapse. The practical-equivalence region was widened from ±0.05
to ±0.125 because ±0.05 needs N>600 and could never fire. The abort clause was preregistered
so that a Solver limit could not be mistaken for a reason to build another instrument.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` — 190 passed.
- `.venv/bin/ruff check .` — clean; `ruff format --check .` — 198 files; `mypy arena` — clean,
  118 files.
- `fitness_v5 materialize` — 864 probes / 144 families, hash `f804e0d998f1cfac…`, audit CLEAN.
- `fitness_v5 develop` — 392 calls; `fitness_v5 status` —
  `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`.
- `game_r_mutant_audit` — 120/120 under the corrected check.
- Canonical validation and assurance suite: not re-run; no canonical, verifier or language
  surface code was changed.

**Failures and unresolved uncertainty.** `formal_expression_depth` leaks
(`first_mentioned_in_state` 0.833 in the selected stratum) and needs an ordering control plus
an identifier-obfuscation arm before reuse. `alpha_normalize` mis-scopes dependent binder
types; not in any measurement path, now pinned by a regression test. Single Solver family
throughout — which is precisely the next thing to change.

**Effect on the overall project.** Three successive invalidations are now explained
mechanistically and guarded by tests: V3 input truncation, V4 output cap plus character guard,
and V5 the Solver itself. The instrument is, for the first time, not the suspect.

**Next intended step.** Re-run the frozen V5 DEV against `gemma4:31b` and `qwen38-rvn`
(~400 calls each). If no installed Solver shows a band, move to Route B matched learning
curves under explicit GPU authorisation. Do not build V6.
