# Project Status

## Project Objective

`GOAL.md` (SHA-256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`, unmodified)
is the permanent objective. Hamiltonian Arena tests whether the representation of mathematics
shown to an AI is a causal determinant of its verified mathematical capability, holding
canonical truth, projection policy, tokenizer, solver, controller, tasks, tools, verifier and
budget fixed. The first controlled game is **Game R**: vary only the representation `R`.
Neither HML nor any custom language is assumed to win; "strong generic representations remain
unbeatable" is a valid outcome.

## Current Stage

`FITNESS_V4_PREREGISTERED`. Fitness V3 is `EXPERIMENT_INVALID` and its invalidation has been
diagnosed to a specific instrument defect (input truncation at `num_ctx=8192`). Fitness V4 — a
Game-R structural-ladder instrument with per-mechanism qualification and a context guard — is
implemented, tested, and preregistered in `docs/FITNESS_V4_SPEC.md`. No V4 model call has been
made at this commit.

## Current Branch

Work is on the worktree branch `claude/hamiltonian-arena-takeover-caa2eb`, created from
`codex/arena-v0-fitness` at `39952276a24462be8d0c8bce58bc3d106fd1dd2c` (the GOAL freeze
commit, identical to `origin/codex/arena-v0-fitness`). The intent is a fast-forward push to
`codex/arena-v0-fitness` at the end of the takeover; no force push.

## Current System Architecture

| Variable | Implementation |
|---|---|
| Σ canonical truth | `arena/canonical/schema.py` (`arena-canonical-v0.1.0`); Gold world v0 `arena/tasks/generators/world_v0.py`, 676 tasks / 13 domains, frozen |
| P projection | `arena/model_view/genome.py` (`ContentGenome`, six Track-C genes) and `projection.py`; fixed at default / Track E during Game R |
| R representation | `arena/genome/schema.py` (14 genes), `arena/genome/seeds.py` (8 seeds), lossless codec `arena/languages/phenotype.py`, `ModelViewCompiler` in `arena/model_view/compiler.py` |
| τ tokenizer | Gemma 4 via Ollama, implicit |
| π solver | `gemma4:12b` digest `4eb23ef1…` (qualified in V2) |
| C controller | single greedy JSON A/B response, no search |
| D tasks | V2 counterfactual probes over Gold; V3 and V4 synthetic mechanism families (not Gold) |
| U tools | none |
| V verifier | `arena/verifier/native.py` plus SymPy/Z3/numeric adapters; generator oracles per probe |
| B budget | Ollama runtime config; V4 raises `num_ctx` to 32768 with a prompt-token guard |

Experiments: `arena/experiments/fitness_v1.py` (invalid, position policy), `fitness_v2.py`
(qualified, insufficient headroom), `fitness_v3.py` (invalid, truncation + ceiling),
`fitness_v4.py` (preregistered). Training: `arena/training/` (matched LoRA runner, A100
sprint). League, curriculum, refuter, architect, assurance and storage packages are unchanged
since v0.

## Capabilities Implemented

Everything from Arena v0 through Phase 3 (see `docs/FINAL_GPT_HANDOFF.md`), plus this
takeover's V4 instrument:

- five structural mechanisms with five-level difficulty ladders, each with an independent
  truth re-derivation (tree walk, ancestor closure, lexical scope resolver, subset check,
  content-hash set difference);
- six-probe families (original, counterfactual, two byte-identical destroyed twins with
  opposite targets, two position swaps) with balanced answer targets;
- preregistered DEV-only frontier selection and per-mechanism qualification with explicit
  void codes; aggregate pooling is never used to qualify;
- a representation-neutral pre-inference shortcut audit (adapted from HML_V3
  `micromath/shortcut_v2.py`), symmetric so a rule at 0% is treated as the same leak as 100%;
- a context guard that refuses to send over-budget prompts, detects the truncation signature
  on returned token counts, and voids an over-budget probe for every candidate;
- Game-R enforcement: any Track-C or non-default content genome is rejected at prompt time;
  information parity (identical recovered canonical hash, distinct bytes) is asserted for every
  SCOUT probe across all eight founders at freeze;
- paired founder statistics: exact sign test, Holm correction, clustered (family) paired
  bootstrap, per-mechanism win/loss/tie, practical-effect and equivalence flags.

## Work Completed to Date

- Arena v0 (`c1dd586`): canonical world, eight seeds, assurance, league, CLI.
- V1 (`f17bb0f`…`22cab97`): invalidated, solver chose by position.
- V2 (`99c877f`, `9832982`): qualified `gemma4:12b`; 12.5-point control range below the 15-point
  headroom rule; stopped.
- A100 matched sprint (`bf8838b`): five-arm LoRA; `WEAK_CONTINUE`; task saturated; S-expression
  penalty only.
- `assert_matched_semantics` fail-closed fix (`a4f7d7f`).
- Phase 3 (`9616654`, `b85f98f`): dual-layer model view, six content genes, V3 instrument,
  12-founder/432-call tournament, `EXPERIMENT_INVALID`.
- GOAL freeze (`3995227`).
- This takeover: V3 diagnosis from committed rows and Ollama logs; V4 instrument, tests, and
  preregistration; status/state/ledger reconciliation.

## Important Files and Artifacts

- `GOAL.md` — frozen objective.
- `docs/FITNESS_V4_SPEC.md` — preregistration (this commit).
- `docs/GAME_R_STATUS.md` — Game-R gate tracker.
- `docs/CURRENT_STATE.md` — reconciled state.
- `docs/FINAL_GPT_HANDOFF.md` — Phase 3 handoff (historical, accurate for V3).
- `artifacts/experiments/fitness_v3/` — frozen V3 manifest, DEV result, founder result,
  `invalidity.json`; immutable.
- `artifacts/experiments/fitness_v4/` — will hold `development/result.json`,
  `frozen_manifest.json`, `founders/result.json`; absent at this commit.
- `artifacts/cache/fitness_v4/` — ignored model-call cache keyed by experiment, instrument,
  model digest, runtime hash, genome hash, probe hash and prompt hash.

## Data Sources and Provenance

- Gold world v0: deterministic generator, seed 0, unchanged.
- V4 DEV pool: 5 mechanisms × 5 levels × 6 families × 6 probes = 900 probes, hash
  `0a45154c532a1a61ef77cf107d4d6bc957cb0be46f4719912b784605043dba05`, generated from
  `EXPERIMENT_SEED=20260907`; no model involvement in any truth.
- `expression_depth_recurrence` adapts HML_V3 `src/hml_v3/projection/dense.py`
  (`MoheetBrain/HML_V3`, `codex/open-ended-search-v2`, local HEAD
  `95e8a26f6519f226a149f4d7507d47f90bea9932`): hashed per-level association, pinned runner-up,
  truth by walk. The code was reimplemented over Arena `CanonicalExpression`; no HML_V3 data
  or score is imported.
- Shortcut audit adapts HML_V3 `src/hml_v3/micromath/shortcut_v2.py` rules.
- No historical hidden data, prior score or trained adapter enters V4.

## Decisions and Rationale

- **V3 is not repaired in place.** Its artifacts are immutable; V4 is a new version with new
  salts, a new runtime hash and new artifact paths.
- **`num_ctx` is raised to 32768.** The V3 floor was input truncation; the budget variable `B`
  must be large enough for every founder to be read in full, otherwise the instrument measures
  token cost, not reading. Token cost is still reported separately.
- **Difficulty comes from structure, not clutter.** HML_V3's 32-cell factorial found external
  clutter null and identity recurrence causal; V4 ladders vary depth/recurrence, hops, rebinds,
  premise count and delta size, with distractor objects held at four.
- **Per-mechanism qualification with an explicit-positive level.** This is the exact defect
  that invalidated V3 (aggregate pooling of ceilings and a floor).
- **Track-C genes are excluded from Game R.** They remain implemented for Game P.
- **Route A before Route B.** Zero-shot structural headroom is testable locally now; learning
  curves need GPU and must be earned by a founder signal.
- **Practical effect (≥ 0.10 paired delta) is a promotion requirement**, in addition to Holm
  significance and minimum net wins, so statistical significance alone cannot promote.

## Verification and Test Results

Executed in this worktree at this commit:

- `.venv/bin/python -m pytest -q` — **185 passed** (144 pre-existing + 41 new V4 tests).
- `.venv/bin/ruff check .` — All checks passed.
- `.venv/bin/ruff format --check .` — 179 files already formatted.
- `.venv/bin/mypy arena` — Success: no issues found in 111 source files.
- `python -m arena.experiments.fitness_v4 materialize` — 150 families / 900 probes, hash
  above, shortcut audit CLEAN (worst rule 0.567).
- `python -m arena.experiments.fitness_v3 status` — `EXPERIMENT_INVALID` (unchanged).
- Truncation diagnosis: one JSON-AST state-delta prompt re-sent at `num_ctx=8192` returned
  prose with `prompt_eval_count=4099`; at `num_ctx=32768` it returned `{"choice":"A"}` with
  `prompt_eval_count=15611`.
- Canonical validation and the assurance suite were **not** re-run in this session; no
  canonical, verifier or language-surface code was changed.

## Known Failures and Limitations

- V3's only favourable signal (Compact Symbolic on state delta) is a context-budget artifact;
  it is not evidence for or against any representation.
- V4 has made no model call yet; every ladder level may still turn out ceiling or floor for
  `gemma4:12b`. That outcome is a valid instrument result and voids the mechanism.
- One local model, one digest, one seed. Nothing generalises to another Solver family without
  re-measurement; HML_V3's cross-reader replication failure (`PATH_TO_ROOT`) is the standing
  warning.
- SCOUT is a large-effect scout (≈ +0.20 paired advantage at 80 positives under Holm).
- The Ollama server has no tokenizer endpoint; the context guard is character-based before the
  call and token-count-based after it.

## Risks and Technical Debt

- `arena/experiments/fitness_v3.py` keeps `num_ctx=8192` for reproducibility of the invalid
  run; it must not be reused for new measurements.
- V2's `RUNTIME_CONFIG` is imported by V3; V4 defines its own. The three runtimes differ only in
  `num_ctx` and are distinguished by runtime hash.
- Prompt length is dominated by the JSON/typed-AST rendering of `CanonicalExpression` trees;
  L4 of `expression_depth_recurrence` and `state_delta` may approach 10–15K tokens for verbose
  surfaces. They remain within the 32K budget but are slow (≈ 15 s per call).
- The docs `PROJECT_STATUS.md` and `PROJECT_LEDGER.md` lagged three commits behind the code at
  takeover (the Phase-3 commits were made outside the ledger protocol); this commit
  re-synchronises them.

## Current Blockers

None for running DEV. The founder tournament is blocked until DEV qualifies at least two
mechanisms and the frozen manifest is committed.

## Exact Next Actions

1. `python -m arena.experiments.fitness_v4 develop` — control-only ladder and qualification
   (≤ 800 calls). Record per-mechanism verdicts in `docs/GAME_R_STATUS.md`.
2. If ≥ 2 mechanisms qualify: `freeze`, commit the manifest, then `founders` with the frozen
   commit SHA (≤ 2,400 calls).
3. If < 2 qualify: record `FITNESS_V4_NOT_QUALIFIED`, redesign ladders under a new instrument
   version, do not run founders.
4. After founders: `docs/GAME_R_FOUNDER_TOURNAMENT.md`, `docs/REPRESENTATION_LANDSCAPE.md`,
   `docs/CLAUDE_FINAL_HANDOFF.md`; push.
