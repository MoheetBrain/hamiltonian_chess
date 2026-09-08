# HC-V0.5 red-team attack suite

`attack_suite_version = hc-v0.5-redteam-2026-09-08`

Executable attacks against the **interactive** path added since `hc-v0-redteam-2026-09-08`:
`arena/trajectory/task.py`, `state_identity.py`, `solver.py`, `episode.py`, plus the RT-02/03/04
fixes in `arena_v0.py`/`schema.py` and the RT-13/04/16 fixes in `arena/evolution/record.py`.
Findings are written up in `docs/HC_V0_5_REDTEAM.md`.

## Discipline observed

* Nothing under `arena/`, `tests/`, `spec/` or `artifacts/` was edited, deleted or moved.
  `artifacts/trajectory_bank_v0/h5/bank.jsonl` and `artifacts/trajectory/hc_v0_5_smoke.json`
  were opened **read-only**.
* Every guard bypass is a local subclass or closure **inside an attack script**
  (`ScriptedArena`, `LeakyRenderer`, `DeclaringLeakyRenderer`, `OracleTransport`,
  `DeadArena`, `ExplodingArena`), never a patch to the package.
* No model generation call. Three read-only HTTP calls were made to the local Ollama
  (`/api/version`, `/api/show`, `/api/tags`) to compare the served digest with the recorded one.
  Every "solver" in this suite is a scripted transport.
* The four sealed LeanDojo splits were never opened.
* Forged banks are written under `out/` only.
* Re-running the **previous** suite (as the directive requires) rewrote
  `research/phase9/redteam/out/{relive,native_decide}.json` and its forged banks;
  the pre-run copies are preserved in `out/prior/`.

## Scripts

| script | targets (directive §23) | output | needs Lean |
|---|---|---|---|
| `harness.py` | shared `ScriptedArena` implementing `task.TaskArena` | — | no |
| `attack_seal_and_leakage.py` | 1 source-proof substitution, 2 leakage, projection parity | `out/seal_and_leakage.json` | no |
| `attack_policy_and_budget.py` | 6 retry exploitation, 9 crash/timeout reward, the six cost counters | `out/policy_and_budget.json` | no |
| `attack_state_identity.py` | 4 stale state identity, 10 stale projection | `out/state_identity.json` | no |
| `attack_episode_runner.py` | 7 model digest / condition, artefact binding | `out/episode_runner.json` | no |
| `attack_parser.py` | 8 parser permissiveness (36 hostile wire payloads) | `out/parser.json` | no |
| `attack_record_draws.py` | 6 duplicate draws, 3 actor spoofing (record layer) | `out/record_draws.json` | no |
| `attack_live_lean.py` | live leakage recount, `skip` no-op, unsound tactics, identity | `out/live_lean.json` | **yes** |
| `attack_session_collision.py` | 4, on two concurrent real REPL sessions | `out/session_collision.json` | **yes** |
| `attack_forgery_v05.py` | 5 + 11: a forgery stronger than the previous suite's | `out/forgery_v05.json` | **yes** |
| `attack_same_file_splice.py` | 5: splice two theorems sharing an elaboration scope | `out/same_file_splice.json` | **yes** |
| `attack_legacy_splice.py` | 5: the same splice with the optional session binding dropped | `out/legacy_splice.json` | **yes** |
| `attack_oracle_episode.py` | 1: an oracle-fed episode in the runner's own artefact shape | `out/oracle_episode.json` | **yes** |
| `attack_emit_trajectory.py` | 1 + 3, end to end through `verify_bank(relive=True)` | `out/emit_trajectory.json` | **yes** |
| `attack_disclosures.py` | are the four DISCLOSED limitations enforced in code? | `out/disclosures.json` | **yes** |

## Run everything

```bash
cd /Users/moheet/Documents/ChatGPT/hamiltonian_chess/.claude/worktrees/hamiltonian-phase-8-experiment-691d22
for s in seal_and_leakage policy_and_budget state_identity episode_runner parser record_draws; do
  .venv/bin/python research/phase9/redteam_v05/attack_$s.py
done
for s in live_lean session_collision forgery_v05 same_file_splice legacy_splice \
         oracle_episode emit_trajectory disclosures; do
  .venv/bin/python research/phase9/redteam_v05/attack_$s.py
done
# regression against the previous suite
.venv/bin/python research/phase9/redteam/attack_trajectory_integrity.py    # now dies at the splice
.venv/bin/python research/phase9/redteam/attack_relive.py
.venv/bin/python research/phase9/redteam/attack_native_decide_end_to_end.py
```

Wall time on the target machine: ≈ 3 minutes, of which ≈ 100 s is Lean.

## Environment used

* `Lean (version 4.10.0-rc1, arm64-apple-darwin23.5.0, commit 3b58e0649156, Release)`,
  `leanprover/lean4:v4.10.0-rc1`, built mathlib4 at
  `/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4`
* `.venv/bin/python`; Ollama 0.33.2 serving `qwen3.6:27b-mlx`
  digest `d49fd9e0da45e486918c87318b866e5924e37ad5841db58763900297d9616ee7`
  (equal to `RECORDED_SOLVER.model_digest`)
* `.venv/bin/python -m pytest -p no:cacheprovider` → `1483 passed, 1 skipped in 180.41s`;
  `--junitxml` corroboration: `tests=1484, failures=0, errors=0, skipped=1`
