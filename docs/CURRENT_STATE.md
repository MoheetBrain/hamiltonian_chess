# Current State

Recorded: 2026-09-06, Europe/London, at the Fitness V4 preregistration commit. Reconciled
against code, committed artifacts, git history and the Ollama server logs; where prose and
artifacts disagreed, the artifacts win and the disagreement is stated.

## Repository and evidence chain

- Repository: `https://github.com/MoheetBrain/hamiltonian_chess.git`
- Takeover start: `39952276a24462be8d0c8bce58bc3d106fd1dd2c` on `codex/arena-v0-fitness`
  (= `origin/codex/arena-v0-fitness`); work continues on worktree branch
  `claude/hamiltonian-arena-takeover-caa2eb` from that commit.
- `GOAL.md` SHA-256 `43d8fcdb5db39b1841b9f620d939e13c47014d98ecba0d09fdd84f699d20117b`,
  verified, unmodified.
- History: v0 `c1dd586`; V1 `f17bb0f`/`11b73ae`/`22cab97`; V2 `99c877f`/`9832982`; A100
  sprint `bf8838b`; matched-guard fix `a4f7d7f`; Phase 3 `9616654`/`b85f98f`; Phase-3
  handoff `997acaa`; GOAL freeze `3995227`.

## Verified claims at takeover

Every Phase-3 claim in `docs/FINAL_GPT_HANDOFF.md` was checked against artifacts:

| Claim | Verified |
|---|---|
| dual-layer model view, six content genes, genome audit, information accounting | yes (`arena/model_view/`, `artifacts/reports/genome-content-audit.json`) |
| V3 frozen before founders; manifest hash `6f1f6c42…` | yes |
| 12 founders × 36 probes = 432 calls, no runtime errors | yes (`founders/result.json`) |
| five ceiling mechanisms, state delta floor for 7 of 8 | yes, and now explained (below) |
| Compact Symbolic 2 wins / 0 losses, p = .25, not promoted | yes |
| 144 tests, lint/format/typing clean | yes at `3995227`; 185 tests now |
| `EXPERIMENT_INVALID` | yes (`invalidity.json`, `fitness_v3 status`) |

Documentation lag: `docs/PROJECT_STATUS.md` and `docs/PROJECT_LEDGER.md` described the A100
sprint stage and had no entries for `9616654`, `b85f98f`, `997acaa`, `3995227`. Corrected.

## What V3 actually measured

All 66 malformed V3 rows (7 Track-E founders × 6 state-delta rows, plus Track-C and
complexity-2 DEV rows) report `prompt_eval_count == 4099`. The Ollama server log records
`truncating input prompt limit=4099 prompt=17072 keep=5 new=4099` for that run. The JSON
state-delta prompt is 45,027 characters ≈ 15,600 tokens; `num_ctx` was 8192. The instruction
header was discarded and the model answered in prose. Re-sending the same prompt at
`num_ctx=32768` returns `{"choice":"A"}`.

Therefore: the state-delta floor, the complexity-2 malformed behaviour, and Compact Symbolic's
only wins were an input-truncation artifact. V3 measured context budget, not reading. It
stays `EXPERIMENT_INVALID`; its artifacts are unchanged.

## Cross-repository state

HML_V3 (`codex/open-ended-search-v2`) advanced past the audited `4395a8c` to `95e8a26`
(`FINAL_HML_KILL_GATE`). It closed its static representation thesis: `PATH_TO_ROOT` scored
+0.57 on `qwen38-rvn` and −0.05 on `gemma4:31b` on 128 fresh paired items, failing a
preregistered two-reader rule, and its original "advantage" came from a degenerate LCG
bootstrap (`FM-057`). Its replicated diagnostic (`REAL_LEAN_GAP_V1`: identity recurrence at
several depths with a one-level lead causes the collapse; external clutter null; effects
non-monotonic in depth and recurrence) is the basis of V4's first mechanism. Its pivot handoff
instructs the Arena not to depend on HML being better; `GOAL.md` already does not.

## Phase 4 state

Fitness V4 (`arena/experiments/fitness_v4.py`, `docs/FITNESS_V4_SPEC.md`) is implemented and
preregistered. DEV pool: 900 probes, hash
`0a45154c532a1a61ef77cf107d4d6bc957cb0be46f4719912b784605043dba05`, shortcut audit CLEAN.
No V4 model call has been made. Sentinel: `FITNESS_V4_NOT_QUALIFIED` (not yet run).

## Model and runtime

- model `gemma4:12b`, digest `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`
- Ollama 0.33.2 on Apple M5 Max, 48 GB; V4 runtime: `num_ctx` 32768, temperature 0, seed
  20260905, `num_predict` 64, `top_k` 64, `top_p` 0.95, thinking disabled.
- Measured latency: ≈ 5–7 s for a 6K-token prompt, ≈ 15 s for a 15.6K-token prompt.
