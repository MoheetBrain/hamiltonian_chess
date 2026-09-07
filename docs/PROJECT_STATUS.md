# Project Status

## Project Objective

`GOAL.md` (SHA-256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`, unmodified)
is the permanent objective: determine whether the representation of mathematics shown to an
AI is a causal determinant of verified mathematical capability, holding Σ, P, τ, π, C, D, U,
V and B fixed, and if so find the strongest robust representation. Game R (vary only R) is the
first controlled game. No language is assumed to win; a negative result is valid.

## Current Stage

`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`. Fitness V5 repaired the two
instrument defects that invalidated V3 and V4 (input truncation, then a 64-token output cap
plus a representation-specific character guard) using grammar-constrained decoding and real
Lean-derived probe states. The repair is complete and measured: 0 malformed rows in 432,
against 89 of 348 in V4. With the instrument sound, 0 of 3 mechanisms qualified while 2 of 3
explicit-positive arms passed at 0.917 and 1.000, so the preregistered abort clause fired.
The blocker is the Solver, not the protocol; no founder, mutant or candidate has been scored
and V6 is not authorised.

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

## Current Blockers

A new experiment version (V4.1 calibration or V5) requires explicit authorisation before any
model call. GPU spend for Route B requires explicit authorisation.

## Exact Next Actions

1. **Change the Solver, not the instrument.** Re-run the frozen V5 DEV against a second and
   third installed model family (`gemma4:31b`, `qwen38-rvn`); ~400 calls each. This also
   addresses the cross-reader replication failure that closed HML_V3's own thesis.
2. If any Solver shows a usable band, resume the frozen pipeline at the founder tournament.
3. If none does, preregister Route B low-budget matched learning curves
   (`docs/ROUTE_B_HISTORICAL_AUDIT.md` §4). Requires GPU authorisation.
4. Before `formal_expression_depth` is reused, add an option-ordering control and an
   identifier-obfuscation arm; it leaked at 0.833 on `first_mentioned_in_state` in the
   selected stratum.
5. Do **not** build V6 on this evidence: the preregistered rule admits a new version only for
   a change of frozen variable class, and the indicated change is the Solver.
