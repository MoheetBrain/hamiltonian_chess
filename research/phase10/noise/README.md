# HC-V0.6 runtime-noise measurement

Every number in `docs/HC_V0_6_RUNTIME_NOISE.md` comes from the raw per-call logs in `out/`.
Nothing here is estimated, extrapolated or carried over from an earlier phase.

**Verdict in one line:** under `FROZEN_DECODING` the runtime is *near*-deterministic but **not**
call-for-call reproducible — 7 of 56 deeply-probed prompts (12.5%) returned more than one tactic,
at a pooled per-call flip rate of 1.02%. No tested `options` dict removed it.

## Environment

Captured programmatically into every `*.meta.json` under `environment` by
`common.environment_record`; reproduced here for convenience.

```
host          Mac17,6 / Apple M5 Max / 51539607552 bytes / arm64 / macOS 26.6.2
python        3.14.7  (.venv/bin/python — there is no `python` on PATH)
worktree      .../.claude/worktrees/hamiltonian-phase-8-experiment-691d22
runtime       ollama 0.33.2 at http://127.0.0.1:11434
model         qwen3.6:27b-mlx
digest        d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7
              27.8B / nvfp4 / arch qwen3_5 / renderer qwen3.5 / parser qwen3.5 / ctx limit 262144
prompt tmpl   95a4e049fca802876995f8b235573ddaa22e55964d74f4efb14579f4f5cee6ef  (hc-v0.5-tactic-json-v1)
out schema    9b25cba2450affa8cae91c864b059aeadc3bb0ed5ab2766a962495e2ed4f3e0b
wire flags    raw=false  think=false  stream=false
options       num_ctx=32768 num_predict=128 temperature=0.0 seed=20260908
              top_k=20 top_p=0.95 min_p=0.0 repeat_penalty=1.0 presence_penalty=0.0
dates         2026-09-08T22:30Z .. 2026-09-08T23:04Z (UTC)
```

`common.verified_solver` refuses to run unless `/api/show` reports that digest, and
`RECORDED_SOLVER.assert_matches` then compares every served field. No model was ever substituted.

## Exact commands, in the order they were run

All commands are run from the worktree root.

### 0. Reproducibility of the HC-V0.5 configuration (4 replays)

```bash
.venv/bin/python -m arena.trajectory.episode --live --tasks 6 --seed 20260908 \
    --scan-limit 12000 --out trajectory/noise_repro_A.json      # and _B, _C, _D
```

Writes `artifacts/trajectory/noise_repro_{A,B,C,D}.json`. `hc_v0_5_smoke.json` is never touched.

### 1–2. Back-to-back and interleaved determinism (run by the preceding agent)

```bash
.venv/bin/python -m research.phase10.noise.derive_goals --tasks 6 --seed 20260909
.venv/bin/python -m research.phase10.noise.e1_back_to_back            # 3 prompts x 40
.venv/bin/python -m research.phase10.noise.e2_interleave              # probe x 30, solo + interleaved
```

### 3. Which `options` matter

```bash
.venv/bin/python -m research.phase10.noise.e3_knobs --repeats 12 \
    --fresh-goals research/phase10/noise/out/NO_FRESH_GOALS.json \
    --probes a0db75effc,05cb1a6a67
```

`--fresh-goals <path that does not exist>` is the documented way to force `common.load_corpus`
onto the **recorded** corpus (`hc_v0_5_smoke.json` states, recovered by verified
`prompt_sha256`). That corpus is the one that contains the prompts HC-V0.5 actually diverged on;
the fresh corpus does not, which is why E1/E2 saw none. `--probes` names one known-unstable and
one known-stable prompt, so a knob that *fixes* instability is distinguishable from a probe that
never had any.

### 4. Context and position

```bash
.venv/bin/python -m research.phase10.noise.e4_context_position --length 40 --rounds 3 \
    --predecessors 6 --pairs 4 \
    --fresh-goals research/phase10/noise/out/NO_FRESH_GOALS.json --probe-sha256 a0db75effc
```

120 calls of identical-schedule replay (the 100+-call long-running sequence) plus 48 calls of
predecessor-dependence.

### 5. Per-cell variance, round-robin ordering

```bash
.venv/bin/python -m research.phase10.noise.e5_cell_variance --prompts 18 --replicates 10 \
    --out research/phase10/noise/out/e5_cell_variance_fresh.jsonl
.venv/bin/python -m research.phase10.noise.e5_cell_variance --prompts 39 --replicates 8 \
    --fresh-goals research/phase10/noise/out/NO_FRESH_GOALS.json \
    --out research/phase10/noise/out/e5_cell_variance_recorded.jsonl
```

### 6. Replay of the exact prompts HC-V0.5 diverged on

```bash
.venv/bin/python -m research.phase10.noise.e6_divergent_replay --repeats 25 --controls 5
```

`suspect` / `control` are read off the recorded run, not chosen by hand: a suspect is a
`prompt_sha256` that `hc_v0_5_smoke.json` answered two ways; a control is one it answered one way.

### 7. Server state: cold / warm / concurrent / idle

```bash
.venv/bin/python -m research.phase10.noise.e7_server_state \
    --repeats 14 --workers 4 --cold-repeats 8 --idle-repeats 5 --idle-seconds 20
```

The `cold` arm evicts the model with `keep_alive=0` and **confirms** the eviction against
`/api/ps` before each probe, so "cold" is an observed server state rather than an assumption.

### 8. Aggregate

```bash
.venv/bin/python -m research.phase10.noise.analyze          # writes out/analysis.json
```

No model calls. Every figure in the report is read from `out/analysis.json` or from a
`*.meta.json`.

## Files

| file | what it is |
| --- | --- |
| `common.py` | drives the **production** `OllamaTacticSolver`; only `SolverIdentity.decoding` is ever varied |
| `derive_goals.py` | fresh Lean states via a live REPL (no Solver call) → `out/fresh_goals.json` |
| `e1_back_to_back.py` … `e7_server_state.py` | the seven experiments |
| `analyze.py` | cross-experiment aggregation + exact McNemar power |
| `out/*.jsonl` | **one JSON object per model call**, flushed per row |
| `out/*.meta.json` | environment + per-experiment summary derived from those rows |
| `out/analysis.json` | the consolidated figures the report quotes |

`out/NO_FRESH_GOALS.json` deliberately does not exist; it is a sentinel path, not a missing file.

## Cost actually measured

2266 model calls inside the seven experiment scripts plus 52 inside the four episode replays.
Median 0.644 s per call, mean 0.750 s; 1700.6 s spent inside `/api/generate`. Total wall clock
across all runs, 2026-09-08 22:30:17Z → 23:04:26Z, was **29 min 06 s** of active running
(the span includes analysis gaps).

## Caveats that limit these numbers

* The unstable-prompt fraction is a **lower bound**. A prompt that flips with probability *q* is
  missed after *k* repeats with probability (1−*q*)ᵏ, so a 5%-flip prompt survives 10 repeats
  undetected 60% of the time. E5 on the recorded corpus reported 39/39 unanimous at *k*=8 even
  though that corpus is known to contain 5 unstable prompts.
* The `concurrent` arm of E7 achieved wall-clock overlap (28/28 probe windows overlapped a load
  call; probe latency rose from 444 ms to 1349 ms median) but the server's own batching policy was
  **not measured**, so "concurrency does not move the answer" is a statement about this load
  pattern, not about batched execution in general.
* Lean was running in another agent's process during part of this window. Its effect on these
  numbers was **not measured**.
* No Lean verdict was collected for E1–E7; the endpoint there is response stability. Only the four
  episode replays carry Lean verdicts.
