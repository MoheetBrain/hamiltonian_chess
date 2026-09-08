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

---

## 2026-09-07 — TRAINING_LANGUAGE_V0 shipped (Deliverable A)

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hours 5–7.
V7 still running.

**Objective of the change.** Ship a complete, executable, training-ready mathematical language
package. This deliverable is **independent of any Game-R result** and was built without waiting on
one.

**Files and systems changed.** New: `releases/TRAINING_LANGUAGE_V0/**` (12 modules plus SPEC,
VERSION, ACQUISITION_GUIDE, HASHES), `tests/releases/**` (13 files),
`docs/TRAINING_LANGUAGE_V0.md`. **Nothing else touched** — `arena/canonical`, `arena/verifier`,
`arena/languages`, `arena/genome`, `GOAL.md` and `artifacts/experiments` are all clean.

**What was completed.** A small extensible core: ten record kinds
(`scope · decl · claim · goal · oblig · evid · subst · dep · ext · lib`) plus an `act` block, with
domains carried as *library values* rather than grammar. A test pins the extension rule: registering
a new library changes what `check_vocabulary` reports and changes **no rendered byte**.

Every REQUIRED gap from `docs/CANONICAL_VNEXT_PILOT.md` is handled **natively**: multi-goal with
per-goal context over a scope forest (G1+N1), `Obligation.scope_id` (N4), one
metavariable/substitution structure (G2≡G6), `Type` as a tree so `[Fun [Nat] [Prop]]` and
`[Fun [Nat [Prop]]]` are distinguished (G3), and `Decl.value` for let-bindings (N2). G4/G5/N3 are
byte-lossless carriers, as the pilot classified them. **G7 is explicitly deferred**, matching the
pilot, and recorded in SPEC §12 rather than papered over.

**Decisions made and why.** (1) Targets are rendered through the **same surface as inputs** via an
`action_envelope`. This removes defect **D3** from `docs/ROUTE_B_PARITY_AUDIT.md` by construction —
the historical sprint always rendered targets as JSON, which gave `L3_JSON_AST` alone
input-grammar = output-grammar, a live alternative explanation for its win. (2) `state_t` *is* the
lossless TL0 text: one serialization, one hashing scheme (`stable_hash`). (3) The acquisition
guide's `PREAMBLE` and `CLOSING` are frozen byte-identical across all ten surfaces and the syntax
section is *generated* from each surface's own descriptor, so no hand-written per-candidate prompt
exists to tune — the §1 failure mode of the historical arms. (4) Default surface is `NativeSurface`
on expressiveness grounds only; a test forbids `RSTAR_*` tokens anywhere in shipped files.

**Tests and verification actually executed.** `python -m pytest tests/releases` → **279 passed,
1 skipped**. Full suite `python -m pytest` → **904 passed, 1 skipped in 61.32s**.
`python -m ruff check .` → All checks passed. `python -m ruff format --check .` → 278 files already
formatted. `python -m mypy arena` → Success, 129 source files. `verify_hashes()` → **no
mismatches**; `package_hash` `443c8f7950147b82…` reproduced independently after consolidation.
Determinism was measured, not asserted: an AST scan of all 12 modules found no
`random/time/datetime/uuid/secrets/os`; attribute insertion order rotated four ways gives one
rendering; rendering under `PYTHONHASHSEED` 0/1/12345 in subprocesses is byte-identical; and
`parse_state(render_state(s)) == s` holds exactly across quotes, newlines, tabs, control
characters, unicode, every value kind, and 0/1/2/5 goals.

**Failures and unresolved uncertainty.** Running the **real frozen** `NativeVerifier`, the
`HONEST` compatibility profile is **rejected** with exactly `UNBOUND_VARIABLE`,
`UNKNOWN_ACTION_TARGET` and `UNKNOWN_SCOPE` — reproducing `arena/verifier/native.py:136`,
`:231-232`, `:82-84`. These are properties of the frozen verifier, already flagged in the vNext
pilot; TL0 carries the truth and does **not** fix them. The default `ARENA_VERIFIER` profile is
accepted with zero issues but trades honesty for acceptance (`binder_kind`→`free`,
goal-targets→`"goal"`, `local_scope` widened) — truth is carried and the reverse map is exact, but a
consumer ignoring carriers sees a less specific state. Carriers perturb `mathematical_hash`, so one
policy must be chosen per experiment. Gap N5 stands: verifier acceptance carries little information
about imported `lean.*` data, and TL0 does not treat it as evidence. Identical guide text
guarantees identical content, not identical helpfulness — pretraining familiarity is uncorrectable
statically.

**Effect on the overall project.** **Deliverable A is met.** The project can now render verified
mathematical trajectories into a versioned, hashed, round-trip-tested language and emit
fine-tuning shards. Evidence level is **`TRAINING_LANGUAGE_V0_BASELINE`** — no training claim is
made anywhere, and `RSTAR_NOT_IDENTIFIED` still stands.

**Next intended step.** Await V7. Wire the selection seam to whichever surface the evidence
supports, if any.

---

## 2026-09-07 — V7 implemented; a Phase-6 claim refuted; a live-cache incident recorded

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hours 5–8.
V7 is running; **this entry contains no V7 result.**

**Objective of the change.** Land the preregistered V7 instrument and record two findings that
arose while building it.

**Files and systems changed.** `arena/experiments/fitness_v7.py` (committed earlier at `cf1b07f`,
sha256 `83a2679646a16eab…`), `tests/experiments/test_fitness_v7.py`, and
`research/v7/{predict_v7_from_frozen_ladders.py, v7_prediction.json, per_level_shortcut_scan.json}`.
No frozen instrument was touched: `git diff` on `fitness_v5.py`, `fitness_v4.py`,
`formal_structural.py` and `artifacts/` is empty.

**FINDING 1 — `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` §11 is refuted.** That document
states that under a corrected frontier target `formal_expression_depth` "would have selected L2
(.792) and passed, giving 2 qualified mechanisms and authorising the founder tournament."
It would not have. Verified directly: V5's own frozen `QUALIFICATION_RULE["shortcut_rule_max"]` is
**0.75** (`arena/experiments/fitness_v5.py:225`), and the per-level shortcut scan gives
`first_mentioned_in_state` = **0.8333 at L2** and **1.0000 at L1** — the two in-window levels.
**Both exceed V5's own threshold, so L2 was already unqualifiable under V5.** V5 never revealed
this because it audits shortcuts only at the *selected* frontier, and because it reported only
`failures[0]` — which is why Phase 6 displayed `VOID_NEGATIVE_CONTROL` and never showed that the
shortcut gate failed too. V7 reports `all_failures`.

**FINDING 2 — a live-cache incident, recorded in full.** While investigating unexpected files under
`artifacts/cache/`, the implementing subagent deleted that directory **three times**, destroying
approximately 55 cache entries belonging to the *running* V7 experiment (PID 3932, started 12:38),
plus an 872-entry dry-run cache and a dry-run artifact. **Assessment: no scientific corruption.**
Within a single run each cache identity is visited exactly once, so nothing was re-called from a
stale entry and no in-flight row was altered; the loss is **resume capability only**. If the run is
interrupted, roughly its first 55 rows plus Q0 must be re-called (≈10 minutes of Solver time). The
run has the final module (module mtime 12:36:26 precedes process start 12:38:56) and was confirmed
progressing. This also explains an earlier integrator observation of a near-empty cache, which was
attributed at the time to model loading; that attribution was incomplete.

**Decisions made and why.** (1) Let the run continue rather than restart: the loss is resumability,
not validity, and restarting would cost the full elapsed Solver time for no scientific gain.
(2) Record the incident rather than quietly regenerate the cache — an undocumented deletion of
experimental state is exactly the kind of event that later makes an artifact unexplainable.
(3) Keep `SHORTCUT_MARGIN = 0.10` untouched. It was frozen in the preregistration **before** the
prediction table below was computed, and it will not be moved.

**Tests and verification actually executed.** `python -m pytest tests/experiments` → 142 passed.
`python -m pytest` → 625 passed at the time of the agent's run; 904 passed, 1 skipped after the
release package landed. `ruff check` / `ruff format --check` / `mypy arena` all clean.
The refutation was re-verified independently by the integrator by reading
`fitness_v5.py:225` and the per-level scan.

**Failures and unresolved uncertainty.** An exploratory prediction — labelled
`EXPLORATORY_PREDICTION_NOT_A_RESULT` in `research/v7/v7_prediction.json`, with a disclaimer
forbidding its use to re-score anything — applies V7's gates to the frozen qwen ladder and expects
**zero mechanisms to qualify**: `formal_expression_depth` L2 margin **−0.042**,
`transitive_dependency` L3 margin **+0.083** (missing the 0.10 gate by 0.017),
`precondition_conjunction` `VOID_CEILING`. If that holds, the only mechanism ever to qualify does
so under V5's rules and **not** under V7's stricter ones. The prediction also inherits the
Phase-6 validity dispute: if Phase 6 is `PHASE6_INVALID`, those accuracies are descriptive only and
the prediction is void. **The running V7 is the confirmatory measurement; the prediction is not.**

**Effect on the overall project.** No representation has been scored. `RSTAR_NOT_IDENTIFIED`
stands.

**Next intended step.** Let V7 finish, report its actual result against the preregistered sentinels,
and run the founder tournament only if it qualifies ≥ 2 mechanisms.

---

## 2026-09-07 — Formal Arena V1 spec and Training Data Factory documented

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hours 8–9.
V7 still running; **no V7 result in this entry.**

**Objective of the change.** Freeze the specification of the three task families and document the
training-data pipeline, both before any Solver is run against them.

**Files changed.** New: `docs/GAME_R_FORMAL_ARENA_V1_SPEC.md`, `docs/TRAINING_DATA_FACTORY.md`.
No code.

**What was completed.** The arena spec records frozen sources, per-family item counts, the
difficulty ladders, the shortcut-gate protocol and every rejection with its measured number. The
factory document records the `tl0-training-record-v1` schema, what can be generated today and at
what trust tier, and the honest cost of Tier-A promotion.

**Decisions made and why.** (1) The arena spec **leads with the blocking constraint** rather than
burying it: the three families carry raw Lean pretty-printed strings and cannot carry Game R,
because a pre-rendered string fixes R. The document keeps its "Game-R" filename only so
cross-references resolve, and says so. (2) The spec fixes "one named control per breached axis,
re-measured once" as the protocol, so the record shows the rule was set before the rejections
rather than after. (3) The factory documents the Tier-A cost as a real number
(≈3,100 replays per 1,000 verified items at the historical 32/100 yield; ≈130 worker-hours for
100k) rather than assuming it away, and names the **built** mathlib path explicitly to prevent the
recurring confusion with the 349 MB source-only checkout that cannot replay.

**Tests and verification actually executed.** None — documentation only. `python -m pytest` was
904 passed, 1 skipped at the previous commit and no code changed since.

**Failures and unresolved uncertainty.** Family C is 100% `TIER_B_CONSTRUCTED` with zero
Lean-verified items; a negative there means "constructed to be invalid", not "the kernel rejects
it". `wrong_rewrite_direction` sits 0.003 under its ceiling with SE ≈ 0.013 and is flagged AT RISK
rather than accepted. Converting any family to Game-R capability requires a canonical projection
that is known to be **lossy**: `docs/CANONICAL_VNEXT_PILOT.md` measured 0 of 368 real Lean states
mapping losslessly into `arena-canonical-v0.1.0`.

**Effect on the overall project.** No representation scored. `RSTAR_NOT_IDENTIFIED` stands.

**Next intended step.** Report V7's actual result against its preregistered sentinels.

---

## 2026-09-07 — V7 CONCLUDED: `V7_SHORTCUT_DOMINATED`, 0 of 3 mechanisms qualified

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, hours 9–13.

**Objective of the change.** Report V7's actual result against its preregistered sentinels, and
integrate the Astra canonical premise bridge research-only.

**Files changed.** New: `docs/FITNESS_V7_RESULT.md`. Merged `astra/canonical-game-r-bridge`
(`5811161`), confined to `docs/astra/` and `research/astra/` — verified by diff to touch no
production file, no `GOAL.md`, no canonical schema, no V7 artifact.

**THE RESULT.** Sentinel **`V7_SHORTCUT_DOMINATED`**; `instrument_qualified: false`;
**0 of 3 mechanisms qualified**. 864 rows, **all `FRESH` — zero cache hits, zero
`CROSS_CONDITION`** (the clean-run property Phase 6 could not claim). Q0 1.000. Every ladder value
reproduced Phase 6 exactly, confirming solver determinism.

| Mechanism | selected | accuracy | best shortcut | margin | verdict |
|---|---|---|---|---|---|
| `formal_expression_depth` | L2 | 0.7917 | **0.8333** `first_mentioned_in_state` | **−0.0417** | `VOID_SHORTCUT` |
| `transitive_dependency` | L3 | 0.7500 | 0.6667 `first_mentioned_in_state` | **+0.0833** | `VOID_SHORTCUT` |
| `precondition_conjunction` | — | ≥0.958 everywhere | 0.500 | — | `VOID_CEILING` |

**The instrument is sound; the mechanisms are not.** `q0`, `valid_response`, `context`,
`answer_share`, `position_invariance`, `negative_collapse` and `sample_size` all **PASS** on both
selected cells. The derived target did exactly what it was registered to do — it moved
`formal_expression_depth` from L3 (0.625) onto L2 (0.792), inside the window — and the per-level
shortcut audit then killed it, because at L2 a one-line string rule **outscores the solver**.

**Phase-6 §11 refuted by measurement.** `formal_expression_depth` at L2 fails
`shortcut_absolute`: 0.8333 exceeds **V5's own frozen** `shortcut_rule_max = 0.75`
(`fitness_v5.py:225`). L2 was already unqualifiable under V5's unmodified rules; V5 never saw it
because it audits only the selected frontier and reported only `failures[0]`. At L1 the shortcut is
**1.000**. Every in-window level of that mechanism is shortcut-dominated; it is not rescuable by
selection.

**The harder finding.** `transitive_dependency` — the only mechanism ever to qualify — passes
`shortcut_absolute` (0.667 ≤ 0.75) and fails **only** the new margin, by 0.017. Stated two-sided:
under V5's frozen rules it qualifies and Phase 6's finding stands on its own terms; under V7's
stricter rule it does not, because beating a first-mention heuristic by 8.3 points on 24 items is
≈1.0 SE and is not evidence of mechanism-specific reading. `SHORTCUT_MARGIN = 0.10` was frozen
before any V7 number existed. Lowering it to 0.08 would qualify this mechanism; that would be
protocol shopping and is refused.

**Decisions made and why.** (1) No founder tournament: the frozen gate needs 2 qualified mechanisms
and got 0. (2) No V8 on this probe bank — the preregistered stopping rule forbids it, and the
evidence says the next move is a task family with a reachable frontier and audited shortcuts.
(3) `precondition_conjunction` is a **ceiling** problem, not a shortcut problem (its best shortcut
is chance, 0.500); it is the one mechanism worth extending upward. (4) The Astra bridge is merged
**research-only**, per its own integration plan, and is not promoted to an instrument.

**Tests and verification actually executed.** `python -m pytest` → **904 passed, 1 skipped**.
`python -m ruff check .` → All checks passed. `python -m mypy arena` → Success, 129 files.
Astra bridge independently re-verified in this worktree: `pytest research/astra/tests` → **37
passed**; `python -m research.astra.game_r_premise.audit` →
`GAME_R_SOURCE_PROJECTION_PARITY_PASS` over 300 items × 5 representations, 1,500 renderings, 1,800
option permutations, 300 private-field noninterference checks, with alpha-rename and
independent-context permutation reported **unsupported (300 each) rather than faked**.

**Failures and unresolved uncertainty.** No representation has been scored at any point in the
programme; V7 measured only the control surface. n = 24 per cell, and the qualifying window is
≈1.76 SE wide — granularity, not the aim point, is now the binding constraint. The shortcut rules
are V5's inherited set; a richer adversary would lower these margins further, not raise them. The
Astra bridge achieves parity at the **source-projection** layer only — its own audit scope says
"not Lean kernel semantics" — so it does not yet support claims about representation effects on
mathematical semantics, and its held-out pool is 60 items drawn from historically exposed LeanDojo.

**Effect on the overall project.** `RSTAR_NOT_IDENTIFIED`. `GAME_R_INSTRUMENT_NOT_QUALIFIED`. No
founder tournament, no mutation campaign, no matched learning. Deliverable A
(`TRAINING_LANGUAGE_V0`) is shipped and unaffected.

**Next intended step.** Write the sprint handoff. The highest-value next experiment is
`precondition_conjunction` with an extended upward ladder, or the premise-selection family once a
canonical projection exists.

---

## 2026-09-07 — Sprint handoff written; state documents reconciled

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint, close-out.

**Objective.** Leave a zero-context handoff and reconcile the state documents with the V7 result.

**Files changed.** New: `docs/72_HOUR_SPRINT_HANDOFF.md`. Rewritten head of
`docs/CURRENT_STATE.md` (prior content preserved below a "Historical state (pre-sprint)" divider —
nothing deleted).

**What was completed.** The handoff records both deliverables, the V7 result and why the two
corrections had to be registered together, the three task families with their measured shortcut
numbers, the constraint that those families cannot carry Game R, the sealing regime, the compute
ledger, the two incidents, and a six-item ordered next-action list.

**Decisions and why.** The handoff leads with the *constraint* rather than the assets: the single
most expensive mistake a successor could make is to run a founder tournament on the three new
families, which would silently compare eight byte-identical inputs. It also states plainly that
lowering `SHORTCUT_MARGIN` from 0.10 to 0.08 would qualify `transitive_dependency`, so that the
temptation is on the record rather than latent.

**Tests actually executed.** `python -m pytest` → 904 passed, 1 skipped. `ruff check .` clean.
`mypy arena` clean, 129 files. `research/astra/tests` → 37 passed. `GOAL.md` sha256 re-verified
`43d8fcdb…0117b`. `gcloud compute instances list` re-checked at close: all three instances
**TERMINATED**; zero cloud spend for the sprint.

**Failures and unresolved uncertainty.** Deliverable B is a negative result: no representation was
scored, and none has been at any point in the programme. The three families are unrun. The Astra
bridge is a source-projection prototype, not a semantic one.

**Effect on the overall project.** `GAME_R_INSTRUMENT_NOT_QUALIFIED`, `RSTAR_NOT_IDENTIFIED`,
`TRAINING_LANGUAGE_V0` shipped at `TRAINING_LANGUAGE_V0_BASELINE`.

**Next intended step.** Extend `precondition_conjunction`'s ladder upward — its shortcut is at
chance, so it is the cheapest credible route to a qualified mechanism.

---

## 2026-09-07 — Consolidate the Game-R tournament harness (recovered from the scratch worktree)

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** 72-hour sprint close-out.

**Objective.** Recover a real asset that was built during the sprint but left behind when work was
consolidated out of the scratch worktree.

**Files changed.** New: `arena/experiments/game_r_formal_v1.py` (1,773 lines) and
`tests/experiments/test_game_r_formal_v1.py` (60 tests).

**What happened.** The sprint originally ran agents in a second worktree
(`.claude/worktrees/arena-72h-sprint`), then consolidated into this one because the
commit-continuity hook resolves the repository from the session working directory, which cannot be
moved. Each agent's output was copied across individually; the tournament harness was missed
because its agent's report focused on a blocking scientific finding rather than on its files. A
close-out check caught it.

**What the harness provides.** An eight-component cache identity (experiment version · model
digest · model revision/tokenizer · runtime condition · decoding hash including `RESPONSE_SCHEMA` ·
qualified task id · candidate id · prompt-byte hash), each component covered by a parametrised test
asserting that mutating it alone misses the cache; a per-row `cache_scope` of
`FRESH`/`SAME_CONDITION_REUSE`/`CROSS_CONDITION`, with `CROSS_CONDITION` unreachable by
construction — the distinction Phase 6 lacked when its artifact accumulated 61 cache hits against a
"cache hits > 0" rule. Parity via `assert_arena_parity`, reusing `assert_game_r_genome`,
`prompt_information_inventory` (which decodes through the **unbound** base codec so a renderer
cannot hide content behind a filtering parser) and `assert_information_parity`; byte-identical arms
are refused, and a single-arm run records the cross-arm checks as `NOT_APPLICABLE_SINGLE_ARM` so it
cannot masquerade as parity-verified. A derived frontier target with a test asserting the literal
`"0.625"` appears nowhere in the code. Fail-closed budget, resumability, and a `--dry-run` stub
solver so every path is testable with no model call.

**Decisions and why.** Commit it despite the tournament never running: it is the infrastructure a
qualified mechanism would need, it is fully tested offline, and leaving it in an untracked scratch
worktree would lose it silently.

**Tests actually executed.** `python -m pytest tests/experiments/test_game_r_formal_v1.py` → 60
passed. Full suite `python -m pytest` → **964 passed, 1 skipped**. `ruff check .` → All checks
passed. `ruff format --check .` → 291 files already formatted. `mypy arena` → Success, **130**
source files.

**Failures and uncertainty.** The harness has never made a model call: `OllamaSolver` is written
but untested against a live endpoint, and grammar-constrained decoding is passed through but
unverified in practice. It also requires an exact token counter and **refuses to send** when one is
unavailable, so a successor must supply one.

**Effect.** No scientific claim changes. `GAME_R_INSTRUMENT_NOT_QUALIFIED` and
`RSTAR_NOT_IDENTIFIED` stand.

**Next intended step.** Unchanged: extend `precondition_conjunction`'s ladder upward.

---

## 2026-09-07 — V7 TOTAL FORENSIC AUDIT: `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Post-V7 forensic audit.
**No experiment was run, no threshold changed, no result re-scored.**

**Objective.** Determine whether "zero qualified mechanisms" means the representation hypothesis
failed, or that the measurement system is wrong. Nine auditors, each briefed to destroy the
argument rather than defend it, plus integrator verification of every load-bearing claim.

**Files changed.** New: `docs/V7_TOTAL_FORENSIC_AUDIT.md`, `research/audit/**` (108 files, 2.0 MB),
`.gitignore` entries for three regenerable intermediates. No existing file modified.

**THE VERDICT.** The representation hypothesis has **not** failed — it has **never been tested**.
In the whole V1→V7 programme no experiment has ever scored two representations against a Solver.
All 864 V7 rows carry one `candidate_id` (`V5E_L3_JSON_AST`); V4's frozen manifest lists an
8-founder roster with `probes: []`; the 120 mutants appear only in a deterministic Gate-0 check.
`Δ = Acc(R_A) − Acc(R_B)` has been computed once in programme history (V3) and was ruled invalid.

**Confirmed, and integrator-verified independently:**
1. `shortcut_audit` scores rules on `canonical_json(state)` (`fitness_v5.py:798-799`) while the
   Solver reads the *rendered* surface (`:550-565`). `first_mentioned_in_state` is **exactly 0.5000
   in all twelve cells** on the string the model actually sees — and it produced **both**
   `VOID_SHORTCUT` verdicts. Three auditors reached this independently with identical corrected
   margins.
2. But `formal_expression_depth` is solvable at **1.000 by bracket-depth counting on the rendered
   prompt at every level** (integrator-verified 24/24 ×4), on all eight surfaces. Under any lossless
   bracketed serialisation "max AST depth" *is* "max delimiter balance", so the optimal strategy is
   **representation-invariant** and a tournament on it could never have detected a representation
   effect. Its void is correct — for a weaker reason than the true one. The leak is intrinsic:
   deepest == first in 79.3% of donor states.
3. `transitive_dependency`'s void is **not supported**. `best_shortcut` is a max over 7 rules × 2
   polarities on the same 24 items; `P(best ≥ 0.6667 | null) = 0.914` and the observed value sits
   *below* the clustered null mean; the winning rule is anti-correlated (0.3333 raw) and 0.6667 is
   its post-hoc negation. McNemar exact p = 0.625 on 4 discordant pairs. One row from qualifying.
4. The 0.10 threshold is **unrepresentable** at n=24 (margins are k/24): the executed gate is 0.125,
   25% stricter than declared. Power to distinguish .083 from .10 is **0.069**; ≈4,000 items would
   be needed. Both values lie inside the project's own equivalence region of 0.125.
5. The dominant error mode is **position anchoring** (56.5% of 69 wrong rows; 95.2% "A" on swapped
   arms; destroyed twins draw "A" 69.4%), and the gates cannot see it — `position_invariance_min` is
   set at chance and the selected cell passes at 0.583. Wrong answers are *anti*-correlated with the
   gated cue: the model is not following it.
6. `relabel()`'s counterfactual is blind to exactly the rules that matter (`cf_blindness = 1.000`
   for every order/position/frequency/depth rule); its docstring claim is refuted by measurement.
7. `DONOR_ROOT` is HML_V3, **not LeanDojo**: 576 of 864 probes (67%) are synthetic but stamped
   `arena-formal-structural-v1.0.0`.
8. **`precondition_conjunction` is balanced BY CONSTRUCTION** — verified in source: `_premise_family`
   builds `objects` and `propositions` once and passes them unchanged to all three arms; only
   `assumptions` varies, so the answer identifiers never move. Best shortcut exactly 0.500 at
   L1–L3. So the other two mechanisms' shortcut domination is a **generator defect, not a fact about
   mathematics** — and the repository already contains the fix, in one of its own mechanisms.

**Self-correction.** `PROJECT_LEDGER.md:747` claims the splits were "sealed before any agent was
spawned". **That is refuted.** `novel_premises/{val,test}` had already been parsed by committed
sprint scripts — `premise_selection_shortcuts.json` reports 3,586 novel_premises items across six
distractor policies — **5h16m before the seal**. Real exposure is 21,632 steps against 8,766
declared, and the *shipped* distractor tiers are the *measured* policies, so the contamination is
design-level. The premise-selection promotion pool is spent.

**Where V7 holds up (`REFUTED` suspicions).** The verdict **recomputes exactly** from the 864 stored
rows with no `arena` import — 252 checks, 0 mismatches. Probe bank bit-exact. Preregistration
discipline was correct and the refusal to drop the margin to 0.08 is endorsed. The derived frontier
target is arithmetically right; labels are not string-generated; closeness-to-target does not select
strong shortcuts (p = 0.889); no cache row was lost or replayed; 872 = 864 + 8 Q0, proved.

**The proposed way forward also falsifies.** Astra's five codecs fail the cheapest falsifier —
*no ≥40-char span of Lean pretty text may appear in more than one arm* — at **300/300 × 5/5**;
four of five are 91–98% identical `canonical_json` behind a different line prefix. Its parity proof
is over a projection measurably missing information (18.9% of candidate statements are not closed
propositions). Constructive finding: the elaborated object **already exists locally** in
`lean_runtime_v2_full.canonical.part-*`, but only 190 transitions are single-premise/single-goal —
**scale, not method, is the gap**.

**Diagnosis.** A (landscape genuinely flat) **0.02** · B (instruments confounded, hypothesis
untested) **0.88** · C (mixed) **0.10**.

**Tests actually executed.** `python -m pytest` → **964 passed, 1 skipped**.
`ruff check arena tests releases` → All checks passed. `mypy arena` → Success, 130 source files.
No model call, no GPU, no cloud — laptop only, as instructed.

**Failures and unresolved uncertainty.** No multi-seed run exists anywhere in the programme;
determinism is asserted from T=0 and identical twin pairs, never from a re-run. Level ladders
confound difficulty with length (ρ = ±1.0), and length-as-cause remains HYPOTHESIS at 3 levels.
Effective n is 14.9 against a declared minimum of 24.

**Next intended step.** One experiment: extend `precondition_conjunction` upward until the control
lands in [0.70, 0.85], then run the programme's **first founder tournament** on it — the only clean
mechanism, clean by construction. Preconditions, all at zero model cost: audit shortcuts **on the
rendered prompt, per representation**; enforce the ≥40-char cross-arm span check; score
`always_first_option` against the model's answers rather than the key; separate selection and
qualification pools; size n for the decision.

---

## 2026-09-07 — Add a straggler audit script left untracked

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Post-audit close-out.

**Objective.** Commit `research/audit/a3_shortcuts/formal_pool_classifiers.py`, written by the
shortcut auditor and missed by the audit commit because it landed after staging.

**Files changed.** That one script. No document or result changes.

**Tests actually executed.** `python -m pytest` → 964 passed, 1 skipped (unchanged; the script is
standalone research code, imported by no production module).

**Failures and uncertainty.** None. The script's outputs were already committed with the audit; only
the generator was missing, which would have made that evidence non-reproducible.

**Effect.** No scientific claim changes. `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` stands.

**Next intended step.** Unchanged: the single recommended experiment in
`docs/V7_TOTAL_FORENSIC_AUDIT.md` §22, pending the owner's decision.

---

## 2026-09-07 — Commit the last audit output file

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Post-audit close-out.

**Objective.** Commit `research/audit/a3_shortcuts/formal_pool_classifiers.json`, the output of the
script committed in the previous entry, so every reported audit number sits beside its generator.

**Files changed.** That one JSON, plus this entry and a one-line status note.

**Tests actually executed.** `python -m pytest` → 964 passed, 1 skipped (unchanged; a data file,
not importable code).

**Failures and uncertainty.** None. The file carries its own disclaimer: a diagnostic at full-pool
n, not a re-scoring, from which no sentinel may be promoted or reinterpreted.

**Effect.** No scientific claim changes. `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` stands.

**Next intended step.** Unchanged: the single recommended experiment in
`docs/V7_TOTAL_FORENSIC_AUDIT.md` §22, pending the owner's decision.

---

## 2026-09-07 — Final audit stragglers; audit tree closed

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Post-audit close-out, final.

**Objective.** Commit the last three files written by the shortcut auditor after its report
returned, closing the audit tree.

**Files changed.** `research/audit/a3_shortcuts/{CONSOLIDATED.json, consolidate.py,
untested_classes.json}`, plus this entry and a one-line status note. All confined to
`research/audit/`; nothing outside it.

**Tests actually executed.** `python -m pytest` → 964 passed, 1 skipped (research data and
standalone scripts, imported by no production module).

**Failures and uncertainty.** These files arrived in several waves as the auditor finished writing,
which is why several close-out commits were needed rather than one. No content was lost:
`docs/V7_TOTAL_FORENSIC_AUDIT.md` was written from the auditors' returned reports, not from these
files, so no conclusion depended on their arrival.

**Effect.** No scientific claim changes. `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` stands.

**Next intended step.** The single recommended experiment in
`docs/V7_TOTAL_FORENSIC_AUDIT.md` §22, pending the owner's decision. **Phase 8 as originally scoped
is not launched**, because the audit falsifies its premise.

---

## 2026-09-07 — Ninth auditor lands: `transitive_dependency`'s void is REFUTED at population scale

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Forensic audit, addendum.
No experiment run, no threshold changed, no result re-scored.

**Objective.** Integrate the shortcut-audit auditor, which returned after the audit document was
committed, and correct two claims — one of them this project's own.

**Files changed.** `docs/V7_TOTAL_FORENSIC_AUDIT.md` (findings C3b–C3f; §22 sharpened),
`docs/FITNESS_V7_RESULT.md` (**correction appended additively** — recorded verdict, sentinel and
artifact untouched), `docs/PROJECT_STATUS.md`, `research/audit/a3_shortcut_audit.md`.

**What changed.** At population scale (400 synthetic families = 800 positives, vs the 24-item cell):
`transitive_dependency`'s voiding rule `first_mentioned_in_state` is at **chance, 0.5175**. The
cell's true best single rule is `more_frequent` at 0.601; the best obtainable surface predictor is
0.640. Margin **0.149** against population and **0.110** against the strongest adversary — **both
clear the 0.10 gate.** Upgraded from "not supported" to **REFUTED**. Conversely
`formal_expression_depth` sits at 1.000/0.882/0.861, so that void is **robust and understated**.

**Self-correction.** `docs/FITNESS_V7_RESULT.md` §6 claimed "a richer adversary would only lower
these margins further, not raise them." **Refuted.** I wrote that sentence; the correction is
appended to that document rather than the text silently edited.

**Three further confirmed defects.** The family is effectively **two rules, not seven** (four
pinned at 0.5000 by the twin construction, `last_mentioned` by key sort; **zero live rules on
`precondition_conjunction`**). A **documented regression**: the cited ancestor used Bonferroni +
Clopper–Pearson with a docstring explaining why; Arena's port added a negation fold (7→14) and
deleted both, leaving 0.75 *below* the null mean of its own max-over-7 statistic (0.744, crossed by
noise 67% of the time). And `first_mentioned_in_state` **is semantic** — 100% agreement with a
preorder walk, because Lean curries.

**Tests actually executed.** `python -m pytest` → 964 passed, 1 skipped. No model call, no GPU, no
cloud.

**Failures and uncertainty.** The population figures for `transitive_dependency` use 400
**synthetic** families; the formal figures use the real 34/34/36 strata. Under V5's in-sample
protocol an unbounded tree reaches 1.000 on transitive L1–L3, so the family cannot be strengthened
without also fixing the evaluation — sample size, not the decision rule, is the binding defect.
`precondition_conjunction`'s clean 0.500 is uninformative on its own.

**Effect.** `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` stands and is strengthened.
`RSTAR_NOT_IDENTIFIED` stands.

**Next intended step.** Unchanged: the single experiment in `docs/V7_TOTAL_FORENSIC_AUDIT.md` §22,
pending the owner's decision.

---

## 2026-09-07 — Add a plain-language "what works, what doesn't" state document

**Branch.** `claude/phase-6-parallel-setup-9c6068`. **Stage.** Post-audit close-out.
No experiment run, no threshold changed, no result re-scored.

**Objective.** The project's state is now spread across a preregistration, three result documents,
a 388-line forensic audit, a sprint handoff and 110 audit working files. A reader cannot answer
"what actually works?" without reading all of it. This adds one page that answers it directly, with
every line traceable to a file or artifact.

**Files changed.** New: `docs/WHAT_WORKS_WHAT_DOESNT.md`. Modified: `docs/PROJECT_STATUS.md`
(pointer), `docs/PROJECT_LEDGER.md` (this entry). No code, no artifact, no sentinel.

**What it records as WORKING.** Canonical world and verifier · representation machinery (pure,
deterministic — AST-verified) · **V7's arithmetic, which recomputes exactly: 252 checks, 0
mismatches** · cache and provenance discipline (864/864 FRESH, 0 orphans, `872 = 864 + 8 Q0`
proved) · preregistration discipline, including the correct refusal to weaken `SHORTCUT_MARGIN` ·
grammar-constrained output (0 malformed in 432) · `TRAINING_LANGUAGE_V0` · three shortcut-gated
formal task families · the tournament harness · `precondition_conjunction`'s by-construction
balance · 964 passing tests with ruff and mypy clean.

**What it records as NOT WORKING.** The shortcut audit reads a string the Solver never receives ·
`transitive_dependency`'s void is refuted at population scale · `formal_expression_depth` is
representation-invariantly solvable at 1.000 · the 0.10 margin is unrepresentable at n=24 (executed
gate is 0.125; power 0.069) · the shortcut family is two rules, not seven, with the ancestor's
Bonferroni + Clopper–Pearson correction deleted · position-invariance is gated at chance while
position anchoring is 56.5% of errors · `relabel()`'s counterfactual is blind · the sealed manifest
under-declares exposure by 60% and the premise promotion pool is spent · the three new families and
the Astra bridge cannot carry Game R · Route B's historical evidence is void.

**What it records as NEVER TESTED.** No representation ever scored; no multi-seed run anywhere; no
OOD claim available; no Lean-verified negatives.

**Decisions and why.** Written as three explicit buckets — WORKS / DOESN'T / NEVER TESTED — because
the audit showed the programme's recurring error is **granularity substitution**, and the specific
form it took here was reporting *failure to demonstrate* as *demonstration of failure*. Keeping
"never tested" as its own bucket, rather than folding it into "doesn't work", is the point of the
document.

**Tests actually executed.** `python -m pytest` → 964 passed, 1 skipped. `ruff check` and
`mypy arena` clean. No model call, no GPU, no cloud — laptop only.

**Failures and uncertainty.** This document is a summary; where it compresses, the audit and the
result documents are authoritative. It creates no new evidence and resolves no open question.

**Effect.** No scientific claim changes. `RSTAR_NOT_IDENTIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and `TRAINING_LANGUAGE_V0_BASELINE` all stand.

**Next intended step.** Unchanged: the single experiment in
`docs/V7_TOTAL_FORENSIC_AUDIT.md` §22, pending the owner's decision.

---

## 2026-09-08 — Phase 8 stood down; salvage its infrastructure as `PHASE8_DIAGNOSTIC_INFRASTRUCTURE`

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`
(worktree, fast-forwarded onto `2047fda`). **Stage.** Mission reset, Phase A (salvage).

**Objective.** Phase 8 was building the programme's first experiment to compare several
representations of identical mathematics against one Solver. Mid-build the project owner reset the
project hierarchy: the controlled representation experiment is now explicitly a *local fitness
assay* inside an open-ended language-discovery system. This commit preserves everything Phase 8
built, records exactly what it did and did not establish, and stops the experiment. It creates no
scientific claim.

**Files and systems changed.** New code: `arena/environments/precondition_ladder.py` (1,132),
`arena/experiments/rendered_prompt_adversary.py` (1,620),
`arena/experiments/precondition_power.py` (1,286),
`arena/experiments/game_r_precondition_founder_v1.py` (1,686),
`arena/experiments/ollama_live.py` (299). New tests: six files, 139 tests. New research scripts:
`research/phase8/{shortcut,parity,transitive}/`. New artifacts:
`artifacts/reports/precondition_rendered_shortcut_audit.json`,
`artifacts/reports/precondition_parity_audit.json`,
`artifacts/manifests/phase8_frozen_adversaries/` (45 frozen adversary sets). New docs:
`docs/PHASE8_SALVAGE_HANDOFF.md`, `docs/PRECONDITION_RENDERED_SHORTCUT_AUDIT.md`. Annotated as
never-enacted: `docs/GAME_R_PRECONDITION_FOUNDER_V1_SPEC.md` (SUSPENDED banner) and §7 of the
shortcut audit. Updated: `docs/PROJECT_STATUS.md`, this ledger. **No frozen instrument was
edited** (`fitness_v1..v7`, `game_r_formal_v1`, `GOAL.md` all untouched; GOAL.md sha256 verified
`43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`).

**What was completed.** Two zero-model-cost measurements, both properties of generators and
renderers rather than of any Solver:

1. *Rendered-prompt shortcut audit* — 45 cells (9 strata × 5 surfaces), adversaries developed and
   frozen on one pool and evaluated on a disjoint fresh pool of 400 items. Best frozen adversary
   anywhere **0.5625** (chance 0.500); ≤ 0.54 at every stratum with premises ≥ 7; every
   candidate-mention and option-text feature pinned at exactly 0.5 on 100% of twin pairs. This
   closes V7 forensic-audit defects C1 (the audit read a string the Solver never receives) and
   C3e (max-over-rules with the ancestor's Bonferroni + Clopper–Pearson correction deleted)
   prospectively, in new code.
2. *Representation parity audit* — harness parity passes everywhere (one envelope signature, one
   answer protocol, exact canonical recovery per arm, distinct bytes, twin differences local to
   the assumptions block). **But `L3_JSON_AST` and `L6_GRAPH_TRIPLES` share 98.6% of their state
   bytes via ≥40-character spans at `P20`, and `L0_STRUCTURED_ENGLISH` vs `L3_JSON_AST` reaches a
   0.82 similarity ratio.** The eight seed surfaces are not eight independent design points. This
   is the E1 failure that killed the Astra bridge, reappearing inside the seed population itself,
   and it is a finding about the *meta-game's founding population*, not about Phase 8.

**Decisions and why.** (a) Stop Phase 8 rather than finish it — the owner's reset is governing,
and independently the preregistered Solver ceased to exist. (b) Commit the work as
*infrastructure*, never as a result, and annotate the unfrozen preregistration in place rather
than deleting it, so the record shows what was designed and never enacted. (c) Do not retro-fit a
replacement Solver into the Phase-8 spec: a Solver substitution is a change of a frozen variable
class and would need its own preregistration, which the reset does not authorise.

**Tests actually executed.** `.venv/bin/python -m pytest` → **1,132 passed, 1 skipped in 85.8 s**
(base commit `2047fda`: 964 passed, 1 skipped; Phase 8 adds 168 tests).
`.venv/bin/python -m ruff check .` → All checks passed. `.venv/bin/python -m ruff format --check .`
→ 306 files already formatted. `.venv/bin/python -m mypy arena` → Success, 135 source files.
Import path verified to resolve inside this worktree before any test run. Dry-run of the founder
runner (`--dry-run`) executes smoke, calibration and tournament stages against a stub solver with
all eleven smoke checks PASS. **No live model call was made through the founder runner.**

**Failures and unresolved uncertainty.** The one live attempt failed at the digest check because
the Solver had been deleted — that is the full extent of the live exercise, so the live path is
**unproven end to end**. `docs/PRECONDITION_POWER_ANALYSIS.md` was never written; the power
numbers exist only in the module and its tests. The transitive-dependency reanalysis is
unfinished: scripts and three JSON outputs exist, no document and no verdict — **do not cite it**.
The Phase-8 preregistration still contains `TBD` at every scientific choice.

**Effect on the overall project.** No sentinel is created, retired or reinterpreted.
`RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and `TRAINING_LANGUAGE_V0_BASELINE` all stand.
`Δ(R_A, R_B)` remains uncomputed. The project's top-level objective moves to
`docs/HAMILTONIAN_CHESS_META_GOAL.md`; `GOAL.md` is retained unmodified as the constitution for
controlled local Game-R experiments.

**Next intended step.** Phase B of the reset: the repository remap, the nested-MDP definition, the
prior-art boundary, and the verified-trajectory data audit — then the smallest executable outer
loop. The Phase-8 founder tournament is **not** authorised.

---

## 2026-09-08 — Mission reset, Phase B: remap the project into the Hamiltonian Chess meta-game

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`.
**Stage.** Mission reset, Phase B (documentation and audit). No experiment run, no model call, no
sentinel changed.

**Objective.** The owner reset the project hierarchy: the controlled representation experiment is
demoted to a local fitness assay, and the top-level mission becomes the open-ended discovery of
machine-facing mathematical languages evaluated by verified long-horizon capability. This commit
delivers the eight documents that define that mission and the audits they rest on. `GOAL.md` is
**not** modified and remains the constitution for controlled local Game-R experiments.

**Files and systems changed.** New: `docs/HAMILTONIAN_CHESS_META_GOAL.md`,
`docs/HAMILTONIAN_CHESS_META_MDP.md`, `docs/HAMILTONIAN_CHESS_REPO_REMAP.md`,
`docs/HAMILTONIAN_PRIOR_ART_BOUNDARY.md`, `docs/LANGUAGE_META_GENOME_V0.md`,
`docs/LONG_HORIZON_FITNESS_V0.md`, `docs/LANGUAGE_FITNESS_MEMORY.md`,
`docs/VERIFIED_TRAJECTORY_ARENA_V0.md`, `research/phase9/data_audit/` (scripts + measured JSON).
Modified: `docs/PROJECT_STATUS.md`, this ledger. **No code changed in this commit.** GOAL.md
sha256 re-verified `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`.

**What was completed.** A 57-component repository remap (KEEP 18 / REFACTOR 13 /
DEMOTE_TO_DIAGNOSTIC 7 / ARCHIVE 12 / MISSING 7); a prior-art boundary with ~70 verified citations;
a language meta-genome specification; a long-horizon fitness design and its record schema; and a
verified-trajectory data audit that settles the arena question by measurement.

**Decisions made and why.**
1. *Live Lean replay is the V0 trajectory world.* Recorded LeanDojo proofs are **trees, not
   chains** — only 67.3% of adjacent pairs chain, and the fully-linear pool yields just 6 theorems
   at horizon >=20 versus 1,605 whose reference proof needs >=20 tactics. Replaying live recovers
   the tree-shaped proofs (5 of 6 probes closed as a flat script). The alternative local corpus
   (HML_V3 `lean_runtime_v2_full`) is unusable for horizon: mean horizon 1.06, **0 of 65 adjacent
   pairs chain** — it is an elaboration-time capture, as its own caveats state.
2. *Truth stays with the backend state id, never a string comparison.* Measured: raw pretty-printed
   Lean state equality scores **40.6%** where real semantic agreement is **98.1%**, so a
   string-comparing verifier would reject 59.4% of correct steps.
3. *The horizon thesis is reframed before anything is built on it.* Under independent per-step
   errors "advantage compounds" is arithmetic, and the absolute accuracy gap is **unimodal** in
   depth, so "the gap widens" is false under one natural metric. Only a **rank reversal** across
   horizon or **super-compounding** is a real result; the metric must be preregistered.
4. *The meta-genome must change payload structure, not skin.* `_grammar_encode` has three branches,
   not eight; five of eight grammar families alias one JSON encoder; `L3_JSON_AST` and
   `L6_GRAPH_TRIPLES` compute a byte-identical role map.

**Tests actually executed.** No code changed, so the suite was not re-run for this commit; the
baseline from the preceding commit stands at **1,132 passed, 1 skipped**, ruff and mypy clean.
Measurements executed for the audits: the LeanDojo corpus counts, the Lean toolchain probe, the
replay probes and the genome-sensitivity sweeps — all recorded under `research/phase9/data_audit/`
and in the documents. **No model call, no GPU, no cloud, no download.**

**Verification performed by the integrator independently of the subagents.** Maximum horizon in the
repository is 1 — the only `CanonicalTrajectory` construction (`world_v0.py:507`) passes a
one-element tuple. The semantic gate accepts all 8 honest surfaces losslessly and **refuses** a
renderer tampered to drop one `holds(...)` assumption. The eight registered seed codecs change
**0 of 44** rendered outputs under one-gene mutation while `GenomePhenotypeLanguage` changes
**24 of 44**. The Lean checkout pins `leanprover/lean4:v4.10.0-rc1` and 5,680 `.olean` are present.
The corpus reproduces exactly: 118,517 records, 59,557 with tactics, 250,814 steps, horizon >=5:
15,275, >=10: 5,892, >=20: 1,605, max 128.

**Failures and unresolved uncertainty.** A path error was made and corrected: the LeanDojo corpus
is under `/Users/moheet/Projects/Hamiltonian-Labs/...`, **not** under `~/Documents/ChatGPT/...`; the
integrator briefed a subagent with a wrongly expanded ellipsis and has recorded the true path in
`HAMILTONIAN_CHESS_META_MDP.md` §7. The semantic gate rests on
`CanonicalState.mathematical_hash`, and the canonical schema maps **0 of 368** real Lean states
losslessly — so the gate's identity cannot reach the target world and must be re-derived against a
backend-native envelope. mathlib4 is `HISTORICALLY_EXPOSED` transitively, so no OOD or
"reasoning" claim is available; only "execution under kernel verification". The sealed splits were
not opened.

**Effect on the overall project.** The top-level objective moves to
`docs/HAMILTONIAN_CHESS_META_GOAL.md`. Game R becomes the local causal assay. No sentinel is
created, retired or reinterpreted: `RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and `TRAINING_LANGUAGE_V0_BASELINE` all stand.

**Next intended step.** Phase C: the verified trajectory arena on live Lean, and the thin outer
loop (`HAMILTONIAN_CHESS_V0`) — targeting end-to-end executability, not discovery.

---

## 2026-09-08 — Mission reset, Phase C: HC-V0 executes; verified trajectory world exists

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`.
**Stage.** Mission reset, Phase C (thin vertical slice). **No scientific claim is made.**

**Objective.** Build the smallest honest outer loop that can eventually discover a language, and
the smallest verifier-backed world with a real horizon. Per the owner-supplied governing manual
(`spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` §0.2, §40) the target is
**end-to-end executability, not discovery**, and no HC-V0 winner is a scientific winner.

**Files and systems changed.** New: `arena/evolution/{__init__,loop,record}.py`,
`arena/trajectory/{__init__,schema,lean_backend,arena_v0}.py`, `tests/evolution/` (50 tests),
`tests/trajectory/` (93 tests), `spec/` (the manual verbatim + the §36.1 minimum authority set),
`artifacts/trajectory_bank_v0/{h5,h12}/`. Modified surgically: `arena/languages/registry.py`
(+31/−2, `get_language` gains a genome-driven fallback; the 8 seeds keep their exact behaviour)
and `arena/pipeline.py` (+37/−4, `_genome` reads `artifacts/candidates/<id>/genome.json`).
**No frozen instrument was edited**; `GOAL.md` re-verified `43d8fcdb…20117b`; the manual stored
unchanged, `f3c04e69…1768cf`.

**What was completed.**
1. *The outer loop runs.* One generation, zero model calls, 0.6 s. Determinism verified by the
   integrator across two runs: `result_hash` and `record_id` identical, only wall-clock and
   timestamp differ. First-ever 80 `MatchObservation` rows written to `arena/league/registry.py`.
2. *A kernel-verified trajectory world exists.* Live Lean replay against the built mathlib4
   checkout (Lean 4.10.0-rc1, 5,680 `.olean`). **11 `CLOSED_VERIFIED` trajectories**, histogram
   `{5:7, 7:1, 12:1, 13:1, 14:1}`, max 14, re-verified from the committed bank by the integrator.
   Verification is the Lean kernel twice: per-step REPL acceptance returning a new state id, and
   whole-script re-elaboration ending in `#print axioms`, rejecting `sorryAx`.
3. *Two manual requirements retrofitted by the integrator:* `InterventionClass` (§6.26/§12.3/§26),
   derived from the changed genes and failing closed on an undeclared gene; and the five-way
   horizon vocabulary (§6.30–§6.34, §17.6) with `MinimalProofLength` and `DependencyDepth`
   returning literal `UNKNOWN`.

**Decisions made and why.** (a) `InterventionClass` is *derived, never stored*, so a record cannot
assert a class its genes do not support. (b) It *fails closed* on an unknown gene: defaulting to
`R_ONLY` would let the first ontology gene be reported as a pure representation effect, which
§26.3 forbids. (c) `DerivedView.canonical_state` is typed `None` rather than `dict | None` — the
type system, not a comment, refuses a canonical projection the pilot measured at 0/368. (d) The
bank's default tactic policy is `record_only` with a hashed policy id, so automation is visible
rather than silently excluded.

**Tests actually executed.** `.venv/bin/python -m pytest` → **1,275 passed, 1 skipped in 116.6 s**
(base `2047fda`: 964/1; salvage: 1,132/1). With the Lean toolchain hidden
(`HAMILTONIAN_MATHLIB_ROOT=/no/such/path`) → 1,260 passed, 10 skipped, i.e. the Lean-dependent
tests skip cleanly. `ruff check .` → All checks passed. `ruff format --check .` → 338 files already
formatted. `mypy arena` → Success, 142 source files. One live-kernel proof recorded: a 5-step
replay closed to `no goals` with `#print axioms` → `[propext, Classical.choice, Quot.sound]`, while
the same probe closed with `sorry` → `[…, sorryAx, …]` → rejected.

**Failures and unresolved uncertainty.**
- **All 120 actions in the bank are `actor=REFERENCE`.** There are **zero solver actions**. The
  bank measures the environment, not a policy. A single-actor guard prevents misreporting.
- **Contamination is unresolved and unresolvable locally.** mathlib4 is `HISTORICALLY_EXPOSED`
  transitively; nothing distinguishes reasoning from recall. Every trajectory carries the note:
  this is **long-horizon execution under kernel verification**, not discovery.
- **Flat replay succeeds at 11/26 = 42%**, not the 5/6 = 83% the six-proof audit sample suggested,
  and it degrades with length (56% at ≥5, **20% at ≥12**). This corrects the prior entry's implied
  yield and must be used for any future bank sizing.
- **`VerifiedTask` (interactive) does not exist in code** — only `VerifiedTrajectory`. Manual
  §40.3's preferred `INTERACTIVE_TASK` mode is therefore unavailable and **autonomous long-horizon
  claims remain blocked**.
- The §21 lifecycle state machine is specified but not yet code-enforced; the spec audit recorded
  17 conformance gaps in `spec/`, of which the integrator closed two after that audit ran.
- The three JSON Schemas were validated as well-formed JSON only; `jsonschema` is not installed and
  installing it needs the network. The meta-schema check is unrun.

**Effect on the overall project.** HC-V0's success criterion (§40.5) is met for the loop and for a
replay-mode world. No sentinel is created, retired or reinterpreted: `RSTAR_NOT_IDENTIFIED`,
`GAME_R_INSTRUMENT_NOT_QUALIFIED`, `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and
`TRAINING_LANGUAGE_V0_BASELINE` all stand. No `RSTAR` or `LSTAR` claim is made or implied.

**Next intended step.** Red-team the loop per manual §47 Step 9 (lineage/provenance, truth
mutation, cache identity, oracle leakage, dead-candidate enforcement, fitness-memory immutability),
then stop and hand off with measured costs. Do **not** continue into Pilot 1.

---

## 2026-09-08 — Red team of HC-V0: 21 exploits, 1 CRITICAL; three fixed

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`.
**Stage.** Mission reset, Phase C close-out (manual §47 Step 9).

**Objective.** Attack HC-V0 before handing it off, per manual §29 (Refuter / Goodhart defence) and
§47 Step 9: lineage/provenance, truth mutation, cache identity, oracle leakage, dead-candidate
enforcement, fitness-memory immutability, and the Lean kernel path.

**Files and systems changed.** New: `docs/HC_V0_RED_TEAM.md`, `research/phase9/redteam/` (9
executable attack scripts + outputs), `tests/trajectory/test_axiom_allow_list.py` (10 tests).
Modified: `arena/trajectory/lean_backend.py` (`TRUSTED_AXIOMS`, `untrusted_axioms`, the verdict,
and a docstring whose claim was false), `arena/trajectory/schema.py`
(`TrajectoryAction.kernel_steps`, `Horizon.kernel_step_count` assignment),
`tests/trajectory/test_horizon_vocabulary.py` (+1 test). Rebuilt:
`artifacts/trajectory_bank_v0/{h5,h12}`.

**What was completed — three fixes.**
1. **RT-01, CRITICAL.** `native_decide` produced `CLOSED_VERIFIED` with full reward. The axiom
   `Lean.ofReduceBool` **was** detected and stored, and then **never read by the verdict**
   (`verified = returncode == 0 and not has_sorry and not errors`). Detection without a gate is
   not a gate. Fixed with an **allow-list**: only `{propext, Classical.choice, Quot.sound}` may
   support a verified closure; everything else fails closed and is named. An allow-list was chosen
   over adding `ofReduceBool` to a deny-list because a deny-list must anticipate the next exotic
   axiom. **Verified against the live kernel**: `by native_decide` →
   `[propext, Lean.ofReduceBool]` → refused; `by decide` → `[propext]` → verified; `by norm_num` →
   `[propext]` → verified. Kernel trust in, compiler trust out.
2. **RT-14, MEDIUM.** `KernelStepCount` was never assigned and read 0 everywhere, so no objective
   could see a macro doing many steps' work (manual §29 macro-cost hiding). Actions now carry
   `kernel_steps`; the horizon sums them.
3. **RT-15, MEDIUM.** The committed bank's horizon block predated the vocabulary retrofit (5 keys,
   not 10). The bank was rebuilt.

**Decisions and why.** (a) Allow-list over deny-list, as above — fail closed on unknown axioms.
(b) `decide` is *kept* verifiable while `native_decide` is refused: the first is kernel-checked,
the second moves trust to the compiler's native evaluation, a materially larger trusted base
(manual §28 requires trust assumptions to be declared). (c) The bank was rebuilt rather than
annotated so the committed artifact is self-consistent and re-proves the fix on real data.
(d) The remaining 18 findings were **not** patched in this pass: they are recorded with
reproductions rather than fixed hastily, and all but one need author/operator write access.

**Tests actually executed.** `.venv/bin/python -m pytest` → **1,286 passed, 1 skipped in 114.7 s**
(Phase C commit: 1,275/1; +11 red-team regressions). `ruff check .` → All checks passed.
`ruff format --check .` → 341 files already formatted. `mypy arena` → Success, 142 source files.
Live kernel probe run directly by the integrator (output in the status document). Bank rebuilt in
49.1 s + 23.3 s and re-read: **11 `CLOSED_VERIFIED`**, histogram `{5:7, 7:1, 12:1, 13:1, 14:1}`
unchanged, **zero untrusted axioms**, `kernel_step_count` summing to 81.

**Failures and unresolved uncertainty.**
- **18 of 21 confirmed findings remain OPEN.** Most load-bearing: RT-02 (two unrelated theorems
  splice into one trajectory that loads clean), RT-03 (`--relive` replays the source record's
  tactics, so a forged action list passes — the net that would catch RT-02 has a hole), RT-04 (one
  episode can yield both a REFERENCE and a SOLVER record), RT-13 (a re-rolled `mutation_hash`
  grants a second `FRESH` record for the same triple — free extra draws, §30.4 winner's curse),
  RT-16 (`league-registry.json` carries `J_solve: 0.75` with no `EXECUTABILITY_ONLY_NOT_A_RESULT`
  stamp).
- **RT-13 is the one an evolutionary search would find on its own**, on the first multi-generation
  run with a stochastic evaluator. The others need write access.
- The red team could not test anything requiring a model, the sealed splits, exhaustive Lean
  unsoundness, `VerifiedTask` (does not exist), scale beyond 2 generations, or concurrency.
- One correction to the trajectory builder's disclosure: its `FULL_NAME_IN_STATE` leakage
  criterion has **never fired**; every drop was `TACTIC_IN_STATE_BEFORE`.

**Effect on the overall project.** The standing assurance wording is now **"0 known critical
exploits under attack_suite_version `hc-v0-redteam-2026-09-08`"**. No sentinel is created, retired
or reinterpreted; `RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and `TRAINING_LANGUAGE_V0_BASELINE` all stand. No
`RSTAR` or `LSTAR` claim is made.

**Next intended step.** Stop and hand off per manual §47 Step 10 with measured costs. Do **not**
continue into Pilot 1. The next engineering priority is the open RT findings, chiefly RT-03 (make
`--relive` replay the trajectory's own actions) and RT-13 (derive `mutation_hash` rather than
accept it), then `VerifiedTask` so an interactive world exists at all.

---

## 2026-09-08 — HC-V0 handoff document; mission-reset session closed

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`.
**Stage.** Mission reset, close-out (manual §47 Step 10: stop and hand off).

**Objective.** Record the measured costs, the open defects and the single highest-value next
action, so the scientific pilot can be designed from evidence rather than from hope. Per §47
Step 10 the session stops here and does **not** continue into Pilot 1.

**Files changed.** New: `docs/HAMILTONIAN_CHESS_V0_HANDOFF.md`. Modified: `docs/PROJECT_STATUS.md`,
this ledger. No code changed.

**What it records.** Sentinel `META_GAME_V0_EXECUTABLE`. What now exists (outer loop,
kernel-verified trajectory world, fitness memory, populated archive, `InterventionClass`, the
`spec/` authority set, a red-team suite) and — at equal length — what HC-V0 is **not**: a stub
evaluator whose `J_solve` is noise, a bank whose 120 actions are all `REFERENCE` with zero solver
actions, five of seven fitness dimensions `NOT_MEASURED`, and `Δ(R_A, R_B)` still uncomputed.

**Measured costs for Pilot-1 sizing.** Outer generation 0.6 s / 0 model calls; Lean startup ~3.2 s
and ~193 steps/s warm; bank builds 3.05 s and 2.29 s per episode; **flat replay 11/26 = 42%**
(56% at reference ≥5, **20% at ≥12**) — which supersedes the 83% a six-proof sample implied;
13 of 35 single-gene children byte-identical; 20 mutants on disk, 10 inert.

**The five constraints carried forward.** (1) The horizon thesis is partly tautological and
metric-dependent — the absolute gap is unimodal, so only a rank reversal or super-compounding is a
real result. (2) Prior art is `NOVEL_ONLY_IN_COMBINATION`. (3) The seed population is narrower than
its roster (98.6% byte overlap; genome-blind codecs). (4) Contamination is unresolved, so the claim
is *execution under kernel verification*, never reasoning. (5) The semantic gate's identity cannot
reach Lean states (0/368 lossless) and has not been re-derived against the backend envelope — the
largest engineering risk in the reset.

**Highest-EV next action, recorded.** Build `VerifiedTask` (the interactive environment) and put a
real Solver in it — but fix RT-03 and RT-13 first, because both corrupt the record the moment an
evaluator makes outcomes stochastic.

**Tests actually executed.** No code changed in this entry; the preceding commit's gates stand at
**1,286 passed, 1 skipped**, ruff clean over 341 files, mypy clean over 142.

**Effect.** No sentinel created, retired or reinterpreted beyond recording
`META_GAME_V0_EXECUTABLE` for the V0 milestone itself. No `RSTAR`/`LSTAR` claim.

**Next intended step.** Owner decision. The session stops here per §47 Step 10.

---

## 2026-09-08 — HC-V0.5: a real Solver played real Lean under kernel verification

**Date/time.** 2026-09-08, Europe/London. **Branch.** `claude/hamiltonian-phase-8-experiment-691d22`.
**Stage.** HC-V0.5 (first real player). **Engineering milestone; no scientific claim.**

**Objective.** Directive HC-V0.5: make one real Solver autonomously play one genuine interactive
Lean episode under kernel verification. No representation comparison, no language winner, no
evolutionary generation. Record-integrity defects were to be fixed **before** any stochastic call.

**Files and systems changed.** New: `arena/trajectory/{task,state_identity,solver,episode}.py`,
`tests/trajectory/test_{task,state_identity,solver,relive_integrity,axiom_allow_list}.py`,
`tests/evolution/test_{evaluation_identity,actor_identity,inadmissible_fitness}.py`,
`research/phase9/{interactive_probe,redteam_v05}/`, docs `HC_V0_5_RESULT.md`,
`HC_V0_5_INTERACTIVE_TASK_SPEC.md`, `HC_V0_5_HANDOFF.md`, `HC_V0_5_REDTEAM.md`,
`LEAN_BACKEND_STATE_IDENTITY_V0.md`. Modified: `arena/trajectory/{arena_v0,schema}.py`
(RT-03/RT-02), `arena/evolution/{record,loop}.py` (RT-13/RT-04/RT-16, schema **v0.1.0 → v0.2.0**).
New artifact: `artifacts/trajectory/hc_v0_5_smoke.json`. `GOAL.md` and the manual re-verified
unchanged.

**What was completed.**
1. *A real player.* `LinearEquiv.snd_comp_prodComm`: **four consecutive Solver-proposed tactics,
   each accepted by the Lean elaborator, terminal `CLOSED_VERIFIED`.** Smoke bank: 30 episodes,
   **4 solved, 16 accepted Solver transitions, 47 rejected, 0 parse failures**, longest chain 4,
   **30/30 trajectories emitted** with states, `pp_sha256` and kernel receipts.
2. *The environment is a game*, established before the task layer existed: across 14 theorems Lean
   accepted a **non-reference** tactic in **10**, and in **2** an alternative closed a goal mathlib
   proves differently.
3. *Five record-integrity defects closed before any stochastic call* — RT-03, RT-02, RT-13
   (identity 11 → 21 components), RT-04 (ledger layer), RT-16 (type-level).
4. *Red team* `hc-v0.5-redteam-2026-09-08`: 25 defects, **0 CRITICAL**, 7 HIGH. Four fixed by the
   integrator during close-out (V05-24, V05-02, V05-10, V05-11).

**Decisions and why.** (a) The sample was widened from 10 to 30 tasks of the **same** distribution,
not to an easier one, because the first ten yielded no accepted transition and §31 forbids moving
the goalposts. (b) `think=False` frozen after measuring that the model's answer is otherwise
diverted to a `thinking` field leaving `response` empty. (c) The Solver was given a **new**
identity with `lineage: UNKNOWN`; the deleted Phase 6/8 model is not assumed to be an ancestor.
(d) Lean is **not** forced through the canonical schema (0/368 lossless); `canonical_state` is
typed `None`.

**Tests actually executed.** `.venv/bin/python -m pytest` → **1,483 passed, 1 skipped in 172.5 s**
(HC-V0 baseline 1,286/1). `ruff check .` → All checks passed. `ruff format --check .` → 359 files
already formatted. `mypy arena` → Success, 146 source files. Live kernel and live model calls were
made throughout; the smoke bank is a real run.

**Failures and unresolved uncertainty.**
- **The runtime is NOT reproducible.** Two runs of an identical 6-task configuration gave different
  `result_hash`. All Lean states and kernel receipts were identical; only Solver output diverged,
  on retries, with **identical `prompt_sha256` and identical prompt token counts**. In isolation
  the same prompt returns the same answer 6/6; divergence appears once other calls pass through the
  same server process. **HC-V0.6 is a paired assay and this breaks its central assumption.**
- **The retry is near-useless**: the backend diagnostic never reaches the Solver, so it re-asks an
  identical question. In the first 10-task bank all ten retries returned the identical tactic.
- **V05-01 and V05-03 remain open**: an oracle-fed episode is byte-shaped like an autonomous one,
  and `build_trajectory` still rewrites every action's actor. **No autonomy or long-horizon claim
  may be made from the smoke artefact until they close.**
- **RT-04 remains open at the trajectory layer** — a relabelled mathlib replay still passes relive.
- 21 further red-team findings open, with reproductions.
- Contamination unresolved: mathlib4 is `HISTORICALLY_EXPOSED` transitively.

**Effect.** Sentinel `HC_V0_5_REAL_PLAYER_EXECUTABLE` recorded for the milestone. No prior sentinel
created, retired or reinterpreted: `RSTAR_NOT_IDENTIFIED`, `GAME_R_INSTRUMENT_NOT_QUALIFIED`,
`V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED`, `TRAINING_LANGUAGE_V0_BASELINE` and
`META_GAME_V0_EXECUTABLE` all stand. No `RSTAR`/`LSTAR` claim.

**Next intended step.** Settle runtime reproducibility, then close V05-01 and V05-03. Do **not**
begin HC-V0.6, Pilot 1, multi-generation evolution, fine-tuning or an RL Architect.
