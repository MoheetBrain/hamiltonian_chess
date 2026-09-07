# Current State

Recorded: 2026-09-07, Europe/London, at the end of the Phase-5 session. Reconciled
against code, committed artifacts, git history and the Ollama server logs.

## Repository and evidence chain

- Repository: `https://github.com/MoheetBrain/hamiltonian_chess.git`
- Takeover start: `39952276a24462be8d0c8bce58bc3d106fd1dd2c` (`codex/arena-v0-fitness`,
  GOAL freeze). Work on worktree branch `claude/hamiltonian-arena-takeover-caa2eb`,
  fast-forwarded onto `codex/arena-v0-fitness` and pushed there without force.
- `GOAL.md` SHA-256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`,
  verified, unmodified.
- History: v0 `c1dd586`; V1 `f17bb0f`/`11b73ae`/`22cab97`; V2 `99c877f`/`9832982`; A100
  sprint `bf8838b`; matched-guard fix `a4f7d7f`; Phase 3 `9616654`/`b85f98f`/`997acaa`;
  GOAL freeze `3995227`; V4 preregistration `88bacc8`; V4 result and handoff: the commit
  containing this file (`git rev-parse HEAD`).

## Scientific state

| Instrument | Sentinel | Why |
|---|---|---|
| V1 | `MODEL_FITNESS_BENCHMARK_INVALID` | solver chose by position |
| V2 | `FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM` | 12.5-point control range < 15 |
| A100 matched sprint | `WEAK_CONTINUE` then saturation | one seed, task at ceiling |
| V3 | `EXPERIMENT_INVALID` | five lookup-ceiling mechanisms plus an input-truncation floor |
| V4 | `FITNESS_V4_NOT_QUALIFIED` | 0 of 5 mechanisms; later shown to be two instrument defects |
| **V5** | **`CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`** | instrument sound (0 malformed / 432 rows); Solver has no measurable band |

No founder, mutant or candidate has been scored under V4 or V5. No representation claim
exists. `RSTAR_NOT_IDENTIFIED`.

## What V5 established

The protocol repair is complete and measured: grammar-constrained decoding produced 0
malformed rows in 432 (V4: 89 of 348), is answer-neutral on rows where V4 also answered
(agreement 1.000), and V4's character-based context guard is confirmed an artifact (rows it
voided truly used 7,396 / 9,498 / 23,215 tokens against a 32,448 limit).

With that fixed, 0 of 3 mechanisms qualified while 2 of 3 explicit-positive arms passed
(0.917 and 1.000). The Solver answers correctly when the relation is stated outright and
otherwise collapses to a constant option: largest-answer share reaches 0.83, 1.00 and 1.00 at
the harder levels. Every cell reading about 0.500 is constant answering, not partial reading.
The preregistered abort clause therefore fired: the limit is the Solver or the task family,
not the protocol, so V6 is not authorised and the indicated change is the Solver.

Full analysis: `docs/FITNESS_V5_RESULT.md`.

## What V3 actually measured

All malformed V3 rows have `prompt_eval_count == 4099`; the Ollama server log records
`truncating input prompt limit=4099 prompt=17072 keep=5 new=4099`. The JSON state-delta prompt
is ≈ 15,600 tokens against `num_ctx=8192`. The instruction header was dropped and the model
answered in prose. The state-delta floor, the complexity-2 "malformed" cells and Compact
Symbolic's only wins were context overflow. V3 artifacts are unchanged.

## What V4 actually measured

356 control-only calls under `num_ctx=32768`, Q0 1.000, no true truncation. Two failure
classes dominate: (1) 59 rows where the Solver begins a correct-looking prose derivation and
exhausts `num_predict=64` before emitting JSON (multi-hop dependency, state delta); (2) a
constant-"A" policy at hard levels (12 of 12 on precondition L3/L4 and binder L1/L2), which
reads as 0.500 under balanced targets and was caught by the choice-flip gate. Two instrument
defects: the character-based context pre-guard voids whitespace-heavy JSON prompts that fit
(30 rows), and level 0 is a minimal-size control rather than a relation-stated-outright
positive. Full analysis: `docs/FITNESS_V4_FAILURE_ANALYSIS.md`.

## Cross-repository state

HML_V3 (`codex/open-ended-search-v2` at `95e8a26`) closed its own static thesis
(`STATIC_REPRESENTATION_THESIS_V1: NOT SUPPORTED`): `PATH_TO_ROOT` failed a two-reader gate
and its original advantage was a degenerate-RNG bootstrap (`FM-057`). Its replicated
diagnostic (`REAL_LEAN_GAP_V1`) informed V4's depth mechanism. Its Lean runtime corpus is the
first import target for a future canonical vNext (`docs/CANONICAL_VNEXT_GAP_REPORT.md`).

## Model and runtime

- `gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`,
  Ollama 0.33.2, Apple M5 Max 48 GB.
- V4 runtime: `num_ctx` 32768, temperature 0, seed 20260905, `num_predict` 64, `top_k` 64,
  `top_p` 0.95, thinking off. Latency ≈ 5–7 s at 6K prompt tokens, ≈ 15 s at 15K.

## Verification at this state

`pytest -q` 188 passed; `ruff check` clean; `ruff format --check` 193 files; `mypy arena`
clean (114 files). Canonical validation and the assurance suite were not re-run: no
canonical, verifier or language-surface code changed in this session.
