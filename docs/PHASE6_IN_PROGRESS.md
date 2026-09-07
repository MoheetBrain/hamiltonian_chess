# PHASE 6 IS RUNNING — READ BEFORE TOUCHING ANYTHING

**Written 2026-09-07 ~06:10 BST by the session that started the run.** This file exists so a
concurrent session does not corrupt a live experiment. Delete it only when Phase 6 is complete
and its result document exists.

---

## 1. There is a live experiment. Do not kill it.

A background job is making real model calls right now:

```
/tmp/phase6_run.sh                                   (shell wrapper)
  -> arena.experiments.fitness_v5 develop --solver gemma4:12b  --bare
  -> arena.experiments.fitness_v5 develop --solver qwen38-rvn  --bare
```

Log: `artifacts/tmp/phase6.log`. Started 05:42 BST. Expected finish **~08:45 BST**
(gemma bare ~50 min, then qwen bare ~2.2 h at roughly 20 s per call).

Check whether it is still alive before doing anything:

```bash
pgrep -fl 'fitness_v5|phase6_run'
```

**If it is running:**

- Do **not** `pkill` it, do not reboot Ollama, do not `ollama stop`, do not pull or remove any
  model. Killing it wastes hours of compute and leaves a half-written artifact.
- Do **not** run any other Ollama workload. The machine has 48 GB and the run needs the model
  resident; a competing model load causes eviction thrash and will distort latency and
  possibly time out calls.
- Do **not** edit `arena/experiments/fitness_v5.py`, `arena/environments/formal_structural.py`,
  or anything they import. The running process already imported them, but a later cell re-reads
  nothing — the danger is that you commit a change that no longer matches the artifact it
  produced.
- Do **not** touch `artifacts/cache/fitness_v5/` or
  `artifacts/experiments/fitness_v5/`. The cache is being written continuously.

**If it is NOT running**, check the log tail for `=== PHASE 6 DONE` and whether both result
files exist (§4). If it died early, say so in your report rather than silently restarting; a
partial run must not be analysed as a complete one.

## 2. What is safe to work on concurrently

Safe: anything outside `arena/experiments/fitness_v5.py`, `arena/environments/`,
`arena/provenance.py`, and `artifacts/`. Documentation elsewhere, unrelated modules, reading
any file, running `pytest`/`ruff`/`mypy` (they are read-only and cheap).

Unsafe: model calls of any kind; edits to the V5 instrument or the probe bank; anything that
writes into `artifacts/`.

## 3. Repository state

- Branch `claude/hamiltonian-arena-takeover-caa2eb`, pushed to `codex/arena-v0-fitness`.
- Phase-5 result `artifacts/experiments/fitness_v5/development/result.json` is **frozen**,
  sha256 `0c5b3271c772bcaf304af65ae469d615572022d18ac81f3083b27a88b0097579`. Do not overwrite.
- `GOAL.md` sha256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`, unmodified.
- Preregistration: `docs/PHASE6_PREREGISTRATION.md` (committed **before** the run, as required).

## 4. What Phase 6 will produce

Two new artifacts, neither of which exists yet:

```
artifacts/experiments/fitness_v5/development/result-gemma4_12b-bare.json
artifacts/experiments/fitness_v5/development/result-qwen38-rvn_latest-bare.json
```

Read status with:

```bash
.venv/bin/python -m arena.experiments.fitness_v5 status --solver gemma4:12b  --bare
.venv/bin/python -m arena.experiments.fitness_v5 status --solver qwen38-rvn --bare
```

## 5. The scientific question, in one paragraph

Phase 5 found 0 of 3 mechanisms qualified while 2 of 3 explicit-positive arms passed, and fired
a preregistered abort clause reading `CURRENT_SOLVER_OR_TASK_FAMILY_CANNOT_SUPPORT_GAME_R_MEASUREMENT`.
Phase 6 substitutes the solver, holding the instrument frozen, to separate "this solver cannot
expose the mechanisms" from "this task family has no measurable structure". Alternate solver:
`qwen38-rvn` (family `qwen35`, 27.3B, completion-only, Q4_K_M).

## 6. Two hazards already found and closed — do not reintroduce them

1. **Cache/model decoupling.** The cache key contained the model *digest* while the call used
   the model *name*, unlinked. Changing the name alone would have replayed all 392 Phase-5
   answers as the new solver's at 100% cache hits. Fixed: the digest travels with the solver,
   and `verify_served_model` asserts the live digest before any run. **Any future solver swap
   must go through the `SOLVERS` registry.**
2. **`BUG_FOUND`: the prompt path was not solver-neutral.** Ollama applies gemma's Modelfile
   renderer on `/api/generate` (+12 framing tokens, and it changed an answer) while qwen carries
   none. `ollama show --template` returns `{{ .Prompt }}` for both, so it is **not** a valid
   neutrality test; the authoritative check is the default-versus-`raw:true` prompt-token delta.
   Fixed by running both solvers under a `bare` condition in a separate cache namespace.

## 7. Interim readings (gemma bare, partial — NOT a result)

Do not cite these as findings; the run is incomplete and the artifact is unwritten.

| mechanism | L0 | L1 | L2 | L3 | note |
|---|---|---|---|---|---|
| formal_expression_depth | 0.625 | 0.667 | 0.542 | 0.542 | VOID_INSTRUMENT_LIMIT |
| transitive_dependency | 0.667 | 1.000 | 0.667 | 0.500 | VOID_INSTRUMENT_LIMIT |
| precondition_conjunction | 0.875 | 0.542 | — | — | in progress |

Emerging observation, to be confirmed: gemma's explicit arms are **worse** without its renderer
framing (0.917 → 0.625, 0.875 → 0.667), so the bare condition handicaps gemma while being
byte-identical to qwen's native handling. Because of this the write-up must report **three**
conditions, not two: gemma framed (Phase 5), gemma bare, and qwen bare. The five-hop terminal
collapse (0.500 with every answer on one option) reproduces under both framings, which is
evidence it is not a framing artifact.

## 8. Where to resume when the run finishes

1. Confirm `=== PHASE 6 DONE` in the log and that both result files exist.
2. Compare at **fixed levels**, never at each solver's own selected frontier.
3. Primary endpoint is the degeneracy statistic (answer entropy / largest-answer-share) on the
   cells where gemma collapsed, not per-cell accuracy — at n=24 a 0.500→0.708 shift cannot reach
   two-sided p ≤ 0.05.
4. Write `docs/FITNESS_V6_SOLVER_SUBSTITUTION_RESULT.md` (do **not** overwrite
   `docs/FITNESS_V5_RESULT.md`), update `docs/CLAUDE_FINAL_HANDOFF.md`, then commit and push.
5. Classify as exactly one of `SOLVER_SPECIFIC_FAILURE_SUPPORTED`,
   `SOLVER_EFFECT_PRESENT_BUT_GAME_R_GATE_NOT_MET`, `FAILURE_REPLICATES_ACROSS_SOLVERS`, or
   `PHASE6_INVALID`.

## 9. Corrections to Phase 5 that must survive into any future write-up

- The destroyed-twin negative control is a **mathematical constant** at exactly 0.500 for any
  deterministic solver, so the gap gate reduces to `positive ≥ 0.70` while frontier selection
  targets 0.625. Effective qualifying window is [0.70, 0.85], not the declared [0.35, 0.85].
- "Constant-position collapse" was **not** established in Phase 5. At the only cell where swap
  arms ran, the solver followed *content* 19/24 and position only 5/24. The cells showing a
  single answer never had swap arms evaluated.
