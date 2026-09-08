# Phase 9 — verified-trajectory data audit

Measurement scripts and raw results behind `docs/VERIFIED_TRAJECTORY_ARENA_V0.md`.
Everything here is **read-only** with respect to every corpus and every checkout outside this
worktree. No model was called. Nothing was downloaded.

## Sealed-split discipline actually observed

`artifacts/manifests/SEALED_SPLITS.json` seals four paths. None of them was opened:

| sealed path | opened? |
|---|---|
| `leandojo_benchmark_4/novel_premises/val.json`  | no |
| `leandojo_benchmark_4/novel_premises/test.json` | no |
| `leandojo_benchmark_4/random/val.json`          | no |
| `leandojo_benchmark_4/random/test.json`         | no |
| `HML_V3/data/corpus/sealed_final_v2.part-*.jsonl.gz` | no (skipped by name in `audit_hml_v3_corpus.py`) |

`steps.jsonl` is **not** one of the sealed paths and carries a `split` field, as
`docs/GAME_R_FORMAL_ARENA_V1_SPEC.md` §3 requires. `audit_steps_horizons.py` `json.loads()` every
line — that is unavoidable to reach the `split` key — but reads **no other field** of any
`val`/`test` row and aggregates none of them. Their only appearance in any output is the row count
(`val 4,260`, `test 4,506`). `steps.jsonl` contains no proof-state text at all, only derived
structural features, so no held-out goal state was materialised even transiently.

## Scripts, in the order they were run

| script | what it measures | output |
|---|---|---|
| `audit_steps_horizons.py`        | horizon histogram from the derived LeanDojo step table, train only | `steps_horizons.json` |
| `audit_leandojo_train.py`        | trajectory structure of `random/train.json`: keys, horizons, chain integrity, terminal states, name leakage | `leandojo_train_trajectories.json` |
| `audit_chained_trajectories.py`  | the *linearly chained* sub-pool and maximal chained prefixes | `leandojo_chained.json` |
| `audit_hml_v3_corpus.py`         | verifies the V7 forensic audit's claims about `lean_runtime_v2_full` and measures its horizon | `hml_v3_corpus.json` |
| `build_replay_probes.py`         | constructs re-elaboration probes from real mathlib source + recorded tactics | `probes/`, `replay_probe_manifest.json` |
| `run_replay_probes.sh`           | runs those probes through the real Lean 4 elaborator | `probe_out/` |
| `compare_replay_states.py`       | Lean's own `trace_state` output vs LeanDojo's recorded states | `replay_state_match.json` |
| `drive_repl.py`                  | drives the built `lean_dojo_repl` tactic: interactive, stateful, branchable | `repl_session_log.json` |
| `repl_throughput.py`             | REPL startup / per-step cost, and the `sorry` anti-cheat probe | `repl_throughput.json` |
| `test_tree_replay.py`            | whether tree-shaped recorded proofs replay as a flat tactic script | `tree_replay.json` |
| `lean_probe_trivial.lean`, `axioms_probe.lean` | Lean toolchain smoke test and `#print axioms` sorry-detection test | — |

`probes/`, `probe_out/`, `repl_*.lean`, `*_tmp.lean` are regenerable scratch.

## Reproducing

    MB=/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4
    .venv/bin/python research/phase9/data_audit/audit_steps_horizons.py
    .venv/bin/python research/phase9/data_audit/audit_leandojo_train.py
    .venv/bin/python research/phase9/data_audit/audit_chained_trajectories.py
    .venv/bin/python research/phase9/data_audit/audit_hml_v3_corpus.py
    .venv/bin/python research/phase9/data_audit/build_replay_probes.py 30 4 12
    research/phase9/data_audit/run_replay_probes.sh
    .venv/bin/python research/phase9/data_audit/compare_replay_states.py
    .venv/bin/python research/phase9/data_audit/drive_repl.py
    .venv/bin/python research/phase9/data_audit/repl_throughput.py
    .venv/bin/python research/phase9/data_audit/test_tree_replay.py
    env -C $MB /Users/moheet/.elan/bin/lake env /Users/moheet/.elan/bin/lean \
        $PWD/research/phase9/data_audit/lean_probe_trivial.lean

`lake env` only sets `LEAN_PATH`; it writes nothing into the mathlib checkout.
