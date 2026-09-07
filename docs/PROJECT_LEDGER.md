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

---

## 2026-09-07 (later) — Correction: mathlib is built locally; Lean attestation is available offline

**Date and time.** 2026-09-07, after the Phase-5 commit `2c61fdb`. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb`. **Project stage.** unchanged
(`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`).

**Objective.** Resolve a contradiction between two subagent reports about local Lean
capability, because it changes what the next agent can do without a download.

**Files and systems changed.** `docs/CLAUDE_FINAL_HANDOFF.md`,
`docs/CANONICAL_VNEXT_GAP_REPORT.md`, `docs/PROJECT_STATUS.md`, this ledger. No code,
experiment, artifact or frozen object touched.

**What was completed.** Direct verification: mathlib4 @
`29dcec074de168ac2bf835a77ef68bbe069194c5` is fully built at
`HML_V3/external/runtime_work/…/mathlib4` with 5,680 `.olean` files, `.lake/` present,
`lean-toolchain` pinned to `leanprover/lean4:v4.10.0-rc1` (installed), and `Lean4Repl.olean`
compiled. One subagent had reported mathlib absent; its search used `-maxdepth 4` against a
path at depth 7, so that negative was a search artifact. The other subagent was correct.

**Decisions made and why.** Recorded in the handoff, gap report and status rather than left in
a subagent transcript, because it is decision-relevant: fresh extraction and genuine Tier-A
replay certificates are available offline, which is the route that would raise imported probe
items from Tier B to Tier A. The donor's own attestation gate reported `passed=false` at about
44% reproducible execution, so that yield is stated alongside the capability.

**Tests and verification actually executed.** `ls`/`find` over the mathlib build directory and
`~/.elan/toolchains`; `cat lean-toolchain`. `.venv/bin/ruff format --check .` — 199 files
already formatted. No model call was made. The pytest/ruff/mypy suite was not re-run because
no code changed since the previous entry, where it passed at 190 tests.

**Failures or unresolved uncertainty.** Whether the attestation bridge's toolchain pin matches
the installed toolchain is untested; the ~44% historical replay yield is the planning number.

**Effect on the overall project.** No scientific result changes. The next agent gains a
verified offline path to kernel-backed attestation.

**Next intended step.** Unchanged: re-run the frozen V5 DEV against a second Solver family.

---

## 2026-09-07 — Phase 6 preregistration: frozen V5, substituted solver, prompt path equalised

**Date and time.** 2026-09-07, early morning BST. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb`. **Project stage.** unchanged
(`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`) pending the Phase-6 run.

**Objective.** Distinguish "this Solver cannot expose the Game-R mechanisms" from "this task
family has no measurable Game-R structure", by running the frozen V5 instrument against a
materially different competent solver and changing nothing else.

**Files and systems changed.** `arena/experiments/fitness_v5.py` (solver registry, solver and
bare parameters threaded through, served-model verification, per-condition artifact paths),
`docs/PHASE6_PREREGISTRATION.md` (new), `docs/PROJECT_STATUS.md`, this ledger. No probe, gate,
prompt template, schema or scoring rule was touched. Phase-5 artifacts untouched
(`result.json` still sha256 `0c5b3271…`).

**What was completed.** Ten read-only subagents audited the freeze boundary, solver inventory,
methodology, statistics, the Phase-5 collapse fingerprint, the adapter, template equivalence,
gates, cross-programme reader priors, and a red-team pass. Two hazards were found and fixed
before any experimental call, and one Phase-5 interpretation was corrected.

**Decisions made and why.**
- **Solver: `qwen38-rvn`.** Different family from gemma4, completion-only (so the 64-token cap
  cannot be consumed by thinking tokens, which V5 would score as wrong rather than void),
  Q4_K_M matched, and the most structurally sensitive reader in the programme's history.
  Declared confounds: it is a fine-tune and it is 27.3B versus 11.9B, so family and scale move
  together; a null is therefore weaker evidence than a positive.
- **BUG_FOUND: the prompt path was not solver-neutral.** Ollama applies gemma's Modelfile
  renderer on `/api/generate` (+12 tokens, and it changed the answer on a probe) while
  qwen carries no renderer. `ollama show --template` returns `{{ .Prompt }}` for both, so it is
  not a valid discriminator. Rather than repair silently, the defect was documented and the
  design re-registered: both solvers now run under a `bare` condition delivering exactly the
  instrument's bytes, in a separate cache namespace.
- **Cache hazard closed.** The cache key contained the model digest while the call used the
  model name, and nothing linked them; changing the name alone would have replayed all 392
  Phase-5 rows as the new solver's at 100% cache hits. The digest now travels with the solver
  and the served model is verified before any run.
- **Analysis corrected.** Comparisons will be made at fixed levels, never at each solver's own
  selected frontier, and the primary endpoint is a degeneracy statistic rather than per-cell
  accuracy, which at n=24 cannot reach two-sided p<=0.05.

**Tests and verification actually executed.**
- `.venv/bin/python -m pytest` — 190 passed. `ruff check` / `ruff format --check` / `mypy arena`
  — all clean.
- Determinism: 24/24 information-identical destroyed twin pairs returned the same answer;
  negative accuracy exactly 24/48 = 0.5000.
- Framing magnitude: on the three collapsed cells, framed versus bare agreement 67/72 = 0.931;
  bare still collapses (67/72 on one option). Framing does not explain the collapse.
- Smoke test: 2 probes, qwen bare, both correct, `cache_hit=False`, clean stop.
- Phase-5 artifact hash and sentinel re-verified unchanged.

**Failures and unresolved uncertainty.** A Phase-5 interpretation was wrong and is corrected in
the preregistration: at the only cell where swap arms ran, the Solver followed *content* 19/24
and position only 5/24, so "constant-position collapse" was not established; the cells with
answer share 1.000 never had swap arms evaluated. Also recorded: the destroyed-twin negative
control is a mathematical constant at 0.500, which makes the effective qualifying window
[0.70, 0.85] rather than the declared [0.35, 0.85].

**Effect on the overall project.** Phase 6 can now run as a genuine controlled substitution.
Phase 5 remains valid: all its comparisons were within one solver under one framing.

**Next intended step.** Run gemma bare and qwen bare (392 calls each), then classify.

---

## 2026-09-07 — Phase 6 run launched; concurrency notice committed

**Date and time.** 2026-09-07, 06:10 BST. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb`. **Project stage.** unchanged
(`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`) until Phase 6 completes.

**Objective.** Commit and push mid-experiment so that a concurrent session can work without
corrupting a live run, and so the run's design is on the remote before its results exist.

**Files and systems changed.** New `docs/PHASE6_IN_PROGRESS.md`; `docs/PROJECT_STATUS.md` and
this ledger updated to point at it. No code, probe, gate or artifact changed.

**What was completed.** The Phase-6 dual-condition run was launched at 05:42 BST
(`/tmp/phase6_run.sh`, log `artifacts/tmp/phase6.log`): gemma4:12b bare, then qwen38-rvn bare,
392 calls each. At the time of this commit gemma bare has finished two of three mechanisms and
the qwen run has not started. Expected completion ~08:45 BST.

**Decisions made and why.** Committing mid-run rather than waiting, because the user is opening
a parallel session and an uninformed edit to the V5 instrument, the artifact tree, or the
Ollama server would destroy hours of compute and silently invalidate the comparison. The notice
states explicitly what is safe to touch and what is not, and records the two hazards already
closed so they are not reintroduced.

**Tests and verification actually executed.** None new in this commit; it is documentation
only. The last full verification was at commit `cbf811e` (pytest 190 passed; ruff, format and
mypy clean). Interim gemma-bare ladder readings are recorded in the notice and explicitly
labelled as not results.

**Failures and unresolved uncertainty.** The run may still fail or be interrupted; the notice
tells the next reader to report a partial run rather than analyse it as complete. An emerging
observation, not yet a finding: gemma's explicit arms score lower without its renderer framing,
so the write-up will have to report three conditions (gemma framed, gemma bare, qwen bare)
rather than two.

**Effect on the overall project.** No scientific claim changes. The design and its two closed
hazards are now on the remote ahead of the results.

**Next intended step.** When the run finishes, compare at fixed levels, write
`docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md`, update the handoff, commit and push.

---

## 2026-09-07 — Phase 6 write-path defect: Phase 5's artifact was overwritten and restored

**Date and time.** 2026-09-07, 06:14–06:16 BST. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb`. **Project stage.** unchanged.

**Objective.** Record a defect that fired during the Phase-6 run, the damage, and the recovery.

**What happened.** `ArtifactStore.write_json` overwrites unconditionally, and
`run_development`'s write call was still hardcoded to
`experiments/fitness_v5/development/result.json`. The intended parameterisation had been
applied by string substitution, but a `ruff format` pass had already split that call across two
lines, so the match silently failed and the edit was never applied. The gemma-bare run
therefore **overwrote Phase 5's frozen `result.json` on disk** (on-disk hash
`c35a316f…`, `prompt_condition: "bare"`).

**Damage and recovery.** No data was lost. Phase 5's artifact was committed at `2c61fdb`; it
was restored with `git checkout --` and re-verified at its exact hash
`0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`, with its sentinel
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` intact. Every gemma-bare row
was already in the model-call cache, so the correct artifact regenerated in 5.7 s with zero
model calls. The in-flight qwen run was stopped three minutes in (a restart is nearly free
because of the cache), the write path was fixed to
`development_artifact_path(solver, bare)`, the fix was verified by reading the emitted line,
and qwen was relaunched at 06:16.

**Decisions made and why.** Stopping the qwen run was chosen over letting it finish, because it
would otherwise have overwritten the restored Phase-5 artifact a second time, and because the
cache made the restart cost negligible. This is recorded rather than quietly repaired, since a
silently overwritten frozen artifact is exactly the class of error the project's protocol
exists to prevent.

**Tests and verification actually executed.** `ruff check` / `ruff format --check` / `mypy
arena` clean after the fix; the emitted write line was re-read to confirm the substitution
applied; Phase-5 hash and sentinel re-verified; gemma-bare artifact regenerated and its
sentinel read (`FITNESS_V5_NOT_QUALIFIED`, zero explicit arms passing).

**Failures and unresolved uncertainty.** The generalisable lesson: a patch applied by string
substitution must be verified by re-reading the target line, because a formatter can defeat the
match and leave the change unapplied while every other check still passes.

**Effect on the overall project.** No scientific result changed. Gemma bare is complete and
recorded; the qwen run is in flight.

**Next intended step.** On qwen completion, compare at fixed levels across three conditions
(gemma framed, gemma bare, qwen bare) and write the Phase-6 result document.

---

## 2026-09-07 — Phase 6 complete: the Phase-5 blocker was the Solver

**Date and time.** 2026-09-07, 05:42–07:07 BST. **Branch.**
`claude/hamiltonian-arena-takeover-caa2eb`. **Project stage.**
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT` →
`SOLVER_SPECIFIC_FAILURE_SUPPORTED`.

**Objective.** Run the frozen V5 instrument against a materially different competent solver,
changing nothing else, to separate "this Solver cannot expose the mechanisms" from "this task
family has no measurable structure".

**Files and systems changed.** New: `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md`,
`artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json`. Updated:
`docs/GAME_R_STATUS.md`, `docs/PROJECT_STATUS.md`. Removed: `docs/PHASE6_IN_PROGRESS.md` (the
run is over). Phase-5 artifact unchanged at `0c5b3271…`; no probe, gate, prompt or scoring rule
altered.

**What was completed.** Three conditions, 392 calls each for gemma-framed (Phase 5) and
qwen-bare, 288 scored rows for gemma-bare: gemma with its renderer, gemma bare, and qwen bare.
Ten read-only subagents audited the design beforehand; all writes were the integrator's.

**Results.** On the preregistered primary endpoint — paired exact McNemar on the degeneracy
indicator over the three cells where gemma reached answer share 1.000, n=72 — qwen goes from
72/72 degenerate to 36/72, b=36, c=0, **p = 2.9e-11**. 36/72 is exactly chance against a fixed
modal answer, so qwen shows no residual degeneracy. Answer entropy on those cells: gemma 0.00
bits at all three, qwen 1.00 at all three. Accuracy there: gemma .500/.500/.500, qwen
1.000/1.000/.750. Pooled positive accuracy over 288 rows: gemma-framed .7118, gemma-bare .6319,
qwen .9062. `transitive_dependency` **QUALIFIED** for qwen at L3 — the first mechanism ever to
qualify in this programme. All three explicit arms passed for qwen (gemma: two, then zero bare).

**Decisions made and why.** Two defects were found and handled before or during the run rather
than silently. First, `BUG_FOUND`: Ollama applies gemma's Modelfile renderer on
`/api/generate` (+12 tokens, and it changed an answer) while qwen carries none, so the design
was re-preregistered to run both solvers bare. Second, the artifact write path was still
hardcoded because a formatter had defeated an earlier patch's string match; the gemma-bare run
overwrote Phase 5's artifact, which was restored from git to its exact hash and regenerated
from cache with zero model calls.

**Tests and verification actually executed.** `pytest` 190 passed; `ruff check`,
`ruff format --check` (201 files) and `mypy arena` (118 files) clean. Zero schema errors, parser
errors or truncations across all 1,056 scored rows; Q0 1.000 in every condition; zero cache hits
for the alternate solver; digest verified against the live model before the run.

**Failures and unresolved uncertainty.** The frozen abort clause still labels qwen
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`, which is wrong for this
solver; it was written for a floor failure and cannot recognise a ceiling one. Reported as
computed, and interpreted correctly alongside. Two instrument defects are now demonstrable: the
destroyed-twin negative control is a mathematical constant at 0.500, making the effective
qualifying window [0.70, 0.85] while the selector targets 0.625, so it prefers unqualifiable
levels — this alone cost `formal_expression_depth` its qualification, since its L1 (.833) and
L2 (.792) would both have passed. One alternate solver only; it is a fine-tune and larger than
the baseline, so family and scale move together.

**Effect on the overall project.** The central Phase-5 ambiguity is resolved: the failure was
the Solver, not the task family. Two of three mechanisms are demonstrably measurable by a
competent solver. Game R is still not authorised (the gate needs two qualified mechanisms and
got one), so `GAME_R_NOT_RUN` and `RSTAR_NOT_IDENTIFIED` stand.

**Next intended step.** Fix the frontier target into the achievable [0.70, 0.85] window, extend
the ladder upward, and re-run qwen only (~400 calls). Under that correction alone two
mechanisms would qualify and the founder tournament would be authorised.
## 2026-09-07 — Parallel next-stage preparation while Phase 6 ran

**Branch.** `claude/phase-6-parallel-setup-9c6068`, based on `b82f8ed` (the pushed tip of
`codex/arena-v0-fitness` at the time Phase 6 started). The worktree was originally created from
the stale `codex/arena-v0` (`c1dd586`) and was reset onto `b82f8ed` before any work began.

**Project stage.** Game R blocked at
`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`. Phase 6 (solver substitution)
was executing throughout this session and finished at 07:07:17 BST; **its classification belongs
to the Phase-6 session and is not made here.**

**Objective of the change.** Build the next layer of work that is useful under *either* Phase-6
outcome, without duplicating, interrupting or contaminating the live experiment. Explicitly: no
model call, no GPU minute, no download, no change to any frozen artifact.

**Files and systems changed.** All additive. New: `arena/training/route_b_data.py`,
`arena/training/verified_eval.py`, `arena/training/gpu_authorisation.py`,
`arena/corpus/{__init__,trace,contamination,provenance}.py`, `tests/corpus/*`,
`tests/training/test_{route_b_data,gpu_authorisation,verified_eval}.py`, eight documents under
`docs/`, four reports under `artifacts/reports/`, four inventories under `artifacts/corpus/`, and
reproduction scripts under `research/`. Modified: `arena/training/prepare_matched_data.py`
(additive flags only; CLI defaults reproduce the historical output byte-for-byte) and
`pyproject.toml` (excludes `research/` from the lint gate).

**What was completed.** Sixteen subagents were dispatched (fifteen completed; one was terminated
by a session rate limit and its deliverable was written directly instead, using only measurements
made by other agents). Principal measured results:

- `WORLD_V0_NEXT_ACTION` is degenerate: a model-free predictor fitted on train reproduces the whole
  gold target on 676/676 tasks and 96/96 held out; 0.8195 with zero arithmetic; 7 of 8 fields
  mechanical; identifier obfuscation does not repair it. `assert_no_answer_leakage` could not have
  caught this — its signature never receives the gold target.
- The five Route-B arms are hand-written codecs that ignore the genome; five of fourteen gene
  families are inert. Six further parity defects recorded, including opposite-side train/eval
  truncation and a length-dependent label mask.
- The V5 frontier selector aims at 0.625 while the gate requires ≥ 0.70. Traced to `gap_min` rising
  0.10 → 0.20 in V5 without moving the target. It changed nothing about the Phase-5 outcome, and
  both naive repairs score above an oracle (they convert noise into passes).
- Canonical schema against 368 real Lean states: 0 lossless, 20.7% unmappable; G7 and G8 refuted;
  four new gaps found; no schema change made.
- The richly-annotated reasoning corpus is 792 steps, not ~300k; verification and richness are
  anti-correlated. A full LeanDojo Benchmark 4 trace is already local and unused.
- Two defects were found and fixed in this branch's own new code before commit: the quality floor
  was applied to train only (leaving 12 of 48 dev and 15 of 48 fresh sub-GOLD under the seeded
  split — now filtered before splitting, with a regression test), and a docstring wrongly asserted
  that `HML_V3/data/registry/datasets.yaml` was absent (it exists, 40 KB).

**Decisions made and why.** (1) Do not duplicate Phase 6 — two sessions editing the same instrument
and caches would make it impossible to say which experiment was frozen. (2) Do not create Fitness
V6 — the preregistered rule admits a new version only for a change of frozen variable class.
(3) Do not re-score V5 under any alternative selector — that is protocol shopping; the analysis is
labelled exploratory and is admissible only as a preregistration input to a future version.
(4) Preserve the inert-seed `stratified_split` as an explicit legacy path rather than fixing it in
place, because `artifacts/experiments/tier2_sprint/` depends on its exact ordering. (5) Exclude
`research/` from the lint gate rather than lint one-off analysis scripts, so `ruff check .`
continues to mean "the shipped code is clean".

**Tests and verification actually executed.** From the worktree with the shared venv, via
`python -m` (a bare `pytest` console script imports the main checkout instead, because the editable
`.pth` points there — verified): `python -m pytest` → **470 passed in 13.77s** (baseline 190);
`python -m ruff check .` → **All checks passed!**; `python -m ruff format --check .` → **223 files
already formatted**; `python -m mypy arena` → **Success: no issues found in 125 source files**.
Frozen artifacts re-verified unchanged: `GOAL.md` sha256 `43d8fcdb…0117b`, Phase-5 `result.json`
sha256 `0c5b3271…97579`. Canonical validation and the assurance suite were **not** re-run: no
canonical, verifier, language-surface or experiment code changed.

**Failures and unresolved uncertainty.** One subagent (future-environment ranking) was terminated
by a session rate limit; its document was written from other agents' measurements only, and this is
stated in the document. The `gpu_authorisation` gate is **inert** — it is not wired into
`gpu_matched_runner.py`, which was out of scope for this branch. `verified ≡ exact` on both
candidate Route-B slices, because World v0 offers exactly one legal action per state; the verifier
alone accepts a hollow legal-id action on 676/676 tasks, so a content-match guard was added and its
non-verifier status documented. Route B's replacement task slice has **not** passed a headroom
check, so Route B is not launchable today. No claim is made about whether the historical sprint's
models actually exploited the leak — only that the task permits it.

**Effect on the overall project.** No scientific claim changes and no sentinel is reinterpreted.
`RSTAR_NOT_IDENTIFIED` stands. The practical effect is that the previously-planned "if Phase 6
fails, run Route B" path is now known to be blocked on a degenerate task family, and a better-
evidenced alternative (premise selection from a local, premise-annotated, OOD-split corpus) is
specified and costs no download.

**Next intended step.** Let the Phase-6 session publish its own classification. Do not launch the
founder tournament — the frozen gate requires ≥ 2 qualified mechanisms and nothing has met it, and
the threshold must not be lowered. Then adopt the fail-fast shortcut check as a precondition on
every future task family, and build premise selection from the local LeanDojo trace, sealing
`novel_premises/{val,test}.json` first.

---

## 2026-09-07 — Cache-hit discrepancy recorded in the published Phase-6 artifact

**Branch.** `claude/phase-6-parallel-setup-9c6068` (parallel next-stage preparation), following
commit `a6e8ddf`.

**Project stage.** Phase 6 published `SOLVER_SPECIFIC_FAILURE_SUPPORTED` at
`b3717c3` on `claude/hamiltonian-arena-takeover-caa2eb` after this branch's main commit. This
branch remains preparation only and makes no Phase-6 classification.

**Objective of the change.** Record, without adjudicating, a factual discrepancy between the
Phase-6 result document and the artifact it describes, on the single field that determines
Phase-6 validity. Leaving it unrecorded was not acceptable; resolving it here would have usurped
the Phase-6 session's own preregistered decision.

**Files and systems changed.** `docs/PHASE6_INTEGRATION_MAP.md` (new §0b), plus this ledger entry
and the corresponding paragraph in `docs/PROJECT_STATUS.md`. No code changed. Nothing in the
Phase-6 worktree was touched; it was read read-only throughout.

**What was completed.** `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` records `cache hits on the
alternate solver | 0`. Counting directly from
`artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json` gives **61** rows
with `cache_hit == true`: 13 of 288 in `ladder_rows`, 24 of 72 in `formal_expression_depth`, 24 of
72 in `transitive_dependency`. An independent forensic audit (`codex/forensic-audit-20260907`)
reports the same 13 + 48 split by a different route; two independent counts agree.

**Decisions made and why.** Record both readings rather than pick one. The literal preregistered
`INVALIDATION_RULE` ("cache hits > 0 for the alternate solver") fires at 61. But the hazard that
rule was written to catch — cache/model decoupling replaying gemma's answers as qwen's — does not
appear present: the artifact's `model.digest` is qwen's `25eb57cb…`, the bare condition has its own
cache namespace, the 13 ladder hits are consistent with the documented 06:16 relaunch resuming the
same solver's own rows, and the 48 mechanism hits are consistent with full-family rows reusing
ladder answers for identical (model, prompt) pairs inside one run. This reads as a reporting error
plus a rule stricter than its rationale, not as contaminated science. Choosing between "correct the
table and argue intent" and "accept the literal reading and classify `PHASE6_INVALID` with the
solver effect retained descriptively" is the Phase-6 session's and the owner's call.

**Tests and verification actually executed.** `python -m pytest` — 470 passed (unchanged; this is a
documentation-only change). The cache-hit count was produced by a read-only JSON traversal of the
artifact; the per-location breakdown is recorded in `docs/PHASE6_INTEGRATION_MAP.md` §0b. No model
call, no write to the Phase-6 worktree.

**Failures and unresolved uncertainty.** The characterisation of the 61 hits as benign is
*inference* from the digest, the runtime cache namespace and the documented relaunch — no
append-only per-call ledger exists that could prove each row's provenance directly. That
uncertainty is stated in the document rather than resolved. Whether Phase 6 stands is not
determined here.

**Effect on the overall project.** No scientific claim on this branch changes; every deliverable
here is independent of any Phase-6 number by construction. The practical effect is that the
discrepancy is now on the record before any downstream decision is taken on the strength of
`SOLVER_SPECIFIC_FAILURE_SUPPORTED`.

**Next intended step.** The Phase-6 session resolves the discrepancy under its own
preregistration. The rule must not be reinterpreted after seeing a favourable result. Regardless of
outcome, do not launch the founder tournament: the frozen gate requires ≥ 2 qualified mechanisms
and one was qualified.

---

## 2026-09-07 — 72-hour sprint base: Phase-6 result and forensic audit reconciled

**Branch.** `claude/phase-6-parallel-setup-9c6068` (continuing as the sprint working branch;
the working directory is pinned to this worktree, so sprint work is consolidated here rather than
in a second worktree). **Project stage.** 72-hour sprint, hour 0–4.

**Objective of the change.** One base carrying the Phase-6 experimental record, the parallel
next-stage machinery already on this branch, and the independent forensic audit, without rewriting
any of them.

**Files and systems changed.** Merges only. `docs/PROJECT_LEDGER.md` conflicted exactly as
predicted in `docs/PHASE6_INTEGRATION_MAP.md` §9 and was resolved by keeping **both** sides in
wall-clock order (12 entries after resolution, none rewritten or deleted).
`docs/PROJECT_STATUS.md` auto-merged and gained a sprint section.

**What was completed.** `GOAL.md` re-verified at
`43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`. Four held-out LeanDojo splits
sealed by sha256 into `artifacts/manifests/SEALED_SPLITS.json` **before any agent was spawned**.
LeanDojo assets verified directly: 259,580 rows (train 250,814 / val 4,260 / test 4,506), 167,779
rows citing ≥1 premise, `rw` head 48,991, mathlib4 commit `29dcec07…`. GCP inventory taken: three
instances exist (`h3-standard-88`, `a2-ultragpu-1g`, `a2-highgpu-1g`), **all TERMINATED**; none
started, because the sprint's current work is CPU-and-Ollama bound and starting an idle GPU would
be pure cost.

**Decisions made and why.** (1) Consolidate the sprint into this worktree: the commit-continuity
hook resolves the repository from the session's working directory, which cannot be moved, so a
second worktree could not be committed from. (2) Treat Phase 6 as formally contested and use no
Phase-6 number as confirmatory input, while accepting `qwen38-rvn` as the scout Solver — a design
choice, not a result. (3) Any selector correction must be preregistered and **re-run**, never used
to re-score frozen data.

**Tests and verification actually executed.** None for this commit beyond the merge checks: it is a
merge introducing no new importable code. The audit merge was verified additive
(`docs/codex_audit/`, `research/codex_audit/` only). The full suite is run and recorded once sprint
code lands.

**Failures and unresolved uncertainty.** Phase 6's formal status is contested (61 cache-hit rows
against a "cache hits > 0" rule). Whether a corrected-selector re-run will qualify two mechanisms
is unknown and must not be assumed from the post-hoc observation that it would have.

**Effect on the overall project.** No scientific claim changes. `RSTAR_NOT_IDENTIFIED` stands.

**Next intended step.** Preregister the selector correction as a derived quantity, re-run the
frozen instrument against qwen fresh, and in parallel build premise-selection, rewrite-direction
and legal-transformation families behind a model-free shortcut gate.

---

## 2026-09-07 — Forensic audit namespaces merged (additive)

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hour 0–4.

**Objective.** Make the independent forensic audit available as sprint reference without importing
any production change.

**Files changed.** Merge only, verified additive: confined to `docs/codex_audit/` and
`research/codex_audit/`. No file outside those namespaces touched. The audit's author labelled
these namespaces `SAFE_TO_CHERRY_PICK`; the branch carries no production patch, which the diff
confirms.

**Decisions and why.** Merge over cherry-pick: clean, additive, preserves the audit's history. Its
conclusions are REPORT_ONLY. Several were independently reproduced by this project's own agents
(inert split seed, GOLD/SILVER/REJECT mix, key-presence `verified` metric, codec-not-gene problem,
World-v0 676/676 solvability, 792-step chain count); one correction was adopted (stratified
`first_mentioned_in_state`: 1.000 shallow / 0.9167 deep-L3 / 0.8125 pooled). Its mathlib
disagreement was resolved: two checkouts of the same commit exist, one built (18 GB, 5,680
`.olean`), one source-only (349 MB, 38 `.olean`).

**Tests actually executed.** `git diff --cached --name-only` confirmed the change set is confined
to the two audit namespaces. Full suite run after staging and recorded in the commit message.

**Failures and uncertainty.** The audit and the Phase-6 session disagree on Phase 6's formal
status; the conservative reading is adopted.

**Effect.** No scientific claim changes. `RSTAR_NOT_IDENTIFIED` stands.

**Next intended step.** Preregister the derived-target selector correction; re-run the frozen
instrument against qwen fresh; build the three formal task families behind a shortcut gate.

---

## 2026-09-07 — Fitness V7 preregistered: derived frontier target + per-level shortcut audit

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hour 0–4.
**Committed BEFORE any V7 model call.**

**Objective of the change.** Correct two measured defects in the frozen instrument, as a package,
and register the correction before running so it cannot be mistaken for post-hoc tuning.

**Files and systems changed.** `docs/FITNESS_V7_PREREGISTRATION.md` (new),
`docs/SPRINT_COMPUTE_LEDGER.md` (new), `artifacts/manifests/SEALED_SPLITS.json` (new). No code in
this commit; `arena/experiments/fitness_v7.py` is being implemented separately and lands only after
this spec is frozen.

**What was completed.** Defect 1: the frontier selector minimises `|accuracy − 0.625|` while the
destroyed control is a mathematical constant at 0.5000, so `gap ≥ 0.20` reduces to
`positive ≥ 0.70` and the qualifying window is [0.70, 0.85] — the selector aims 0.075 below its own
floor, and `destroyed ≤ 0.60` is a dead gate. Traced to V5 raising `gap_min` 0.10 → 0.20 without
moving the target. Defect 2: the shortcut audit runs only at the selected frontier, leaving every
other level unmeasured. V7 derives the target from the gate arithmetic
(`(0.70 + 0.85)/2 = 0.775`), drops the dead gate, runs the shortcut audit at every level, and adds
`positive − best_shortcut ≥ 0.10` as a qualification gate.

**Decisions made and why.** (1) The two corrections are registered as a **package**: correcting the
selector alone would move `formal_expression_depth` onto L2 (.792) where the measured shortcut
`first_mentioned_in_state` is ≈ 0.8125 pooled — that would manufacture a qualification, so the
shortcut gate is mandatory. (2) `SHORTCUT_MARGIN = 0.10` is justified independently of outcome: at
n = 24 the binomial SE near 0.8 is ≈ 0.082, so a smaller margin cannot separate a solver from its
own shortcut. (3) Phase 6's cache rule is replaced by a `cache_scope` distinction
(FRESH / SAME_CONDITION_REUSE / CROSS_CONDITION) because a rule that cannot distinguish benign
same-solver reuse from cross-condition contamination is wrong on its own stated rationale — this is
registered before V7 runs, not adopted after a result. (4) No cloud instance was started: the
sprint's current work is CPU-and-Ollama bound and an idle 88-vCPU or A100 box is pure cost.

**Tests and verification actually executed.** `GOAL.md` sha256 re-verified
`43d8fcdb…0117b`. Solver availability and identity verified read-only: `ollama list` shows
`qwen38-rvn:latest` ID `25eb57cb8173`, matching the digest recorded in the preregistration. No
model call was made. `python -m pytest`: 470 passed (recorded at the previous commit; no code
changed here).

**Failures and unresolved uncertainty.** V7 is **strictly stricter** than V5 and may qualify fewer
mechanisms. The preregistration records the honest expectation: `transitive_dependency` should
re-qualify, `precondition_conjunction` should return `VOID_CEILING`, and
`formal_expression_depth` **may void on the new shortcut gate**, giving
`V7_ONE_MECHANISM_QUALIFIED` and no founder tournament. That is a legitimate outcome and no
threshold may be reinterpreted to avoid it. The dominant limitation is unfixed: at n = 24 the
qualifying window is ≈ 1.76 standard errors wide and both ladders step across it in one move, so
granularity — not the aim point — is the binding constraint.

**Effect on the overall project.** No scientific claim changes yet; V7 has not run.
`RSTAR_NOT_IDENTIFIED` stands.

**Next intended step.** Land `arena/experiments/fitness_v7.py` with its offline tests, verify it
cannot touch any V5 or Phase-6 artifact, then run 392 calls against `qwen38-rvn` bare.

---

## 2026-09-07 — Three real formal task families built and shortcut-gated; V7 launched

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hours 1–5.

**Objective of the change.** Build Game-R-candidate task families from real verifier-backed formal
data, gate each on a model-free shortcut attack *before* any Solver call, and launch the
preregistered V7 instrument.

**Files and systems changed.** New: `arena/environments/{premise_selection,rewrite_direction,
legal_transform}.py` with tests; `arena/experiments/fitness_v7.py` with tests;
`arena/experiments/game_r_formal_v1.py` (tournament harness) with tests;
`research/env_{premise,rewrite,legal}/`; `artifacts/manifests/*_manifest.json`.

**What was completed — all three families pass their preregistered shortcut ceilings.**

| family | usable items | best model-free shortcut | ceiling | verdict |
|---|---|---|---|---|
| premise selection | 63,831 (24,718 distinct gold premises) | **0.327** (depth-6 tree), chance 0.167 | 0.45 | READY |
| rewrite direction | 3,466 controlled (16,414 raw) | **0.6026** (GB depth-3), chance 0.50 | 0.65 | READY *under control* |
| legal transformation | 24,000 (12,000 matched pairs) | **0.5197** graded pooled, chance 0.50 | 0.65 | READY (graded arm) |

**Refutations and kills, recorded because they matter more than the passes.**
(1) The "36.9% of `rw` steps are reverse" estimate is **wrong**: measured 19.42% per rewrite element
and 25.12% per tactic first-element over 250,814 train steps. The binary is *not* naturally
balanced and needs explicit balancing.
(2) Rewrite direction **breached at 0.7085** without control, driven entirely by lemma-name
features (char-n-gram logistic 0.6748 alone). A within-lemma direction-balancing control makes
every lemma-constant feature uninformative by construction — they collapse to exactly 0.5000 — at
the cost of shrinking the pool 16,414 → 3,466.
(3) Premise selection rung `L1_cross_module` **breached at 0.866**; one named control brought it to
0.644, still breached, so it was **rejected, not tuned**, and retained in `REJECTED_LEVELS` so the
rejection stays reproducible.
(4) Legal transformation killed two axes: `violated_precondition` (0.777 — the only textually
checkable violation raises novel-identifier count by +0.92) and `wrong_successor` (0.664 after one
repair). `wrong_rewrite_direction` is flagged AT RISK at 0.6472, under ceiling by 0.003 with
SE ≈ 0.013.
(5) Premise selection excluded 6,877 transitions where the gold premise name is already printed in
`state_before` — a real leak, not hygiene.

**The blocking scientific finding.** All three families carry **raw Lean pretty-printed strings**
(`state: str`, `options: tuple[str, ...]`) and contain **zero** references to `CanonicalState` or
`CanonicalAction` (verified by grep; `formal_structural` has 3). **They therefore cannot support a
Game-R tournament**: Game R requires re-rendering the same canonical content through eight
representations, and a pre-rendered string fixes R at "Lean's pretty-printer". They measure solver
capability on real mathematical decisions, which is a different and also valuable game. Only the
canonical `formal_structural` probe bank can carry Game R today.

**Decisions made and why.** (1) Pursue V7 on `formal_structural` as the Game-R path, because it is
the only canonical substrate available. (2) Keep all three new families: they are the honest
long-term answer to "the probes are a poor proxy for mathematical reasoning", and converting them
to canonical form is a specified, separable task. (3) Exclude `research/env_legal/items.jsonl.gz`
(9.4 MB, regenerable in 45 s) from the commit.

**Tests and verification actually executed.** `python -m pytest` → **625 passed in 63.51s**
(190 before this sprint). `python -m ruff check arena tests` → All checks passed.
`python -m ruff format --check arena tests` → 179 files already formatted.
`python -m mypy arena` → Success, no issues in 129 source files. Import path confirmed inside this
worktree. V7 launched at 12:38:56 after `verify` confirmed the live digest
`25eb57cb8173332b43f8f07f6214e6b74f9e11afac5242392da751458fb024ae`; 872 planned calls against a
900 budget; Q0 1.000. A `--dry-run` with a stub solver exercised every path first and made no call.

**Failures and unresolved uncertainty.** V7 is **still running** and its result is unknown; nothing
here anticipates it. The dry run surfaced that `formal_expression_depth`'s real per-level shortcut
is 0.833 at L2 against qwen's measured 0.792 there, so `VOID_SHORTCUT` is the likely outcome for
that mechanism — as the preregistration predicted. Legal transformation is 100% `TIER_B_CONSTRUCTED`
with zero Lean-verified items; the Tier-A replay is designed but **not run** (≈3,100 replays for
1,000 items at the historical 32/100 yield). Rewrite direction's equation sides are a textual parse
of recorded signatures, not elaboration.

**Effect on the overall project.** No representation has been scored. `RSTAR_NOT_IDENTIFIED`
stands. The project now has three shortcut-audited task families built from 250,814 real verified
Lean transitions, where before it had synthetic mechanism probes.

**Next intended step.** Await V7. If it qualifies ≥2 mechanisms, run the founder tournament on
`formal_structural`. Regardless, ship `TRAINING_LANGUAGE_V0`.

---

## 2026-09-07 — Remove a regenerable 2.4 MB derived dump committed in error

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hour ~5.

**Objective.** Restore consistency between the repository and its own documentation.

**Files changed.** `research/environments/measurements/train_premise_citation_counts.json` removed
from tracking and added to `.gitignore`.

**What happened.** `git add -A` in the previous commit (`cf1b07f`) swept up a 2,424,793-byte
derived premise-frequency dump that `research/environments/README.md` explicitly states was **not**
committed because it is regenerable by `build_train_priors.py`. The repository therefore
contradicted its own README. The file is also unvalidated output from a subagent terminated
mid-run, which is precisely the material the README quarantines.

**Decisions and why.** Remove rather than amend the README: the file is derived, regenerable in
seconds, and unvalidated. Keeping 2.4 MB of unchecked numbers where a reader might cite them is the
worse option. Added to `.gitignore` so it cannot recur.

**Tests actually executed.** `python -m pytest` → 625 passed (unchanged; no code touched).

**Failures and uncertainty.** None. The previous commit stands as recorded; this is a follow-up
correction, not a rewrite of it.

**Effect.** No scientific claim changes.

**Next intended step.** Await V7; ship `TRAINING_LANGUAGE_V0`.
