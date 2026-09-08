# HAMILTONIAN_CHESS_V0 — Handoff

**Sentinel: `META_GAME_V0_EXECUTABLE`.**

Assume zero context. This is the state after the mission reset of 2026-09-08, in which Game R was
demoted from mission to local causal assay and the project became the outer game that designs
mathematical languages.

**Governing authority:** `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`,
owner-supplied, stored unchanged per its §47 Step 2, sha256 `f3c04e69…1768cf`. `GOAL.md` is
preserved unmodified (`43d8fcdb…20117b`) and still governs local Game-R assays.

---

## 1. What now exists that did not

| Thing | Where | Evidence |
|---|---|---|
| An outer loop that runs | `arena/evolution/` | one generation, 0 model calls, 0.6 s; `result_hash`/`record_id` identical across two runs |
| A kernel-verified trajectory world | `arena/trajectory/` | **11 `CLOSED_VERIFIED`**, horizons `{5:7, 7:1, 12:1, 13:1, 14:1}`, max 14 |
| A durable fitness memory | `arena/evolution/record.py` | append-only, 11-component identity, re-scoring guard |
| A populated archive | `arena/league/registry.py` | **80 `MatchObservation` rows — the first ever written** |
| `InterventionClass` | `arena/evolution/record.py` | derived, fails closed on an undeclared gene |
| The minimum authority set | `spec/` | constitution, glossary, claim ledger, contracts, 3 schemas |
| A red-team suite | `research/phase9/redteam/` | 9 executable attacks; 21 confirmed exploits |

## 2. What HC-V0 is NOT

**No HC-V0 winner is a scientific winner** (manual §0.2, §40). Specifically:

- The evaluator is a **deterministic stub** (`sha256(prompt) mod n_options`). Its `J_solve = 0.75`
  is **noise**. The run stamps itself `EXECUTABILITY_ONLY_NOT_A_RESULT`.
- **All 120 bank actions are `actor=REFERENCE`.** There are **zero solver actions**. The bank
  measures the environment, not any policy.
- Five of seven fitness dimensions are present and `NOT_MEASURED`.
- `Δ(R_A, R_B)` — the quantity the programme has never computed — is **still uncomputed**.
- No sentinel was created, retired or reinterpreted. `RSTAR_NOT_IDENTIFIED`,
  `GAME_R_INSTRUMENT_NOT_QUALIFIED`, `V7_PARTIALLY_VALID_INSTRUMENT_CONFOUNDED` and
  `TRAINING_LANGUAGE_V0_BASELINE` all stand. **No `RSTAR` or `LSTAR` claim is made.**

## 3. Measured costs (for sizing Pilot 1, per manual §41.2)

| Quantity | Measured |
|---|---|
| Outer generation, stub evaluator | 0.6 s, 0 model calls |
| Lean session startup | ~3.2 s; warm throughput ~193 tactic steps/s |
| Bank build, 16 episodes ≥5 | 49.1 s (3.05 s/episode) |
| Bank build, 10 episodes ≥12 | 23.3 s (2.29 s/episode) |
| **Flat replay success** | **11/26 = 42%** — 56% at reference ≥5, **20% at ≥12** |
| Solver latency (deleted model) | `seconds ≈ −2.9 + 2.1 × tokens/1000`, 12–18k tokens → 15–36 s |
| Mutation neighbourhood | **13 of 35** single-gene children of the JSON seed are byte-identical |
| Mutants on disk | **20**, not 120; **10 of them byte-inert** |

**The 42% figure supersedes the 83% (5/6) a six-proof sample suggested.** Size any future bank
from 42%, and from 20% if targeting horizon ≥12.

## 4. The five facts that most constrain what comes next

1. **The horizon thesis is partly a tautology.** Under independent per-step errors, "advantage
   compounds" is `p^n` vs `q^n`, and the absolute gap is **unimodal** — with a *constant* +3.5-point
   per-step edge it peaks at horizon 8 and decays to zero, so comparing horizons 1→20 says
   "advantage grows" (+0.039) while 20→80 says "advantage shrinks" (−0.074), **from the same null**.
   Only a **rank reversal** or **super-compounding** is a real result, and the metric must be
   preregistered. See `docs/HAMILTONIAN_CHESS_META_GOAL.md` §5.1.
2. **Prior art returns `NOVEL_ONLY_IN_COMBINATION`.** A hand-designed machine-facing proof language
   already reports +20–29 points of kernel-verified pass@1 in this domain. The architecture alone
   is not a contribution.
3. **The seed population is narrower than it looks.** Two of eight surfaces share **98.6%** of
   their state bytes; the eight registered codecs are genome-blind (0/44 one-gene mutations change
   a byte); the working phenotype path changes 24/44.
4. **Contamination is unresolved and locally unresolvable.** mathlib4 is `HISTORICALLY_EXPOSED`
   transitively. The defensible phrasing is **long-horizon execution under kernel verification**,
   never "reasoning" or "discovery".
5. **The semantic gate's identity cannot reach the target world.** It compares
   `CanonicalState.mathematical_hash`, and the canonical schema maps **0 of 368** real Lean states
   losslessly. The trajectory world already uses a backend-native envelope; the gate has not been
   re-derived against it. **This is the largest engineering risk in the reset.**

## 5. Open red-team findings — 18 of 21

Fixed: **RT-01** (CRITICAL — `native_decide` verified with full reward because `ofReduceBool` was
detected but never gated; now a fail-closed axiom allow-list), **RT-14** (`KernelStepCount` never
assigned), **RT-15** (stale horizon block).

Highest-priority open, in order:

1. **RT-03** — `--relive` replays the *source record's* tactics, not the trajectory's own, so a
   forged action list passes. This also removes the net that would catch **RT-02** (two unrelated
   theorems spliced into one trajectory that loads clean).
2. **RT-13** — a re-rolled `mutation_hash` grants the same (parent, child, condition) a second
   `FRESH` record: free extra draws, the §30.4 winner's curse. **The one an evolutionary search
   finds unaided**, on the first multi-generation run with a stochastic evaluator.
3. **RT-04** — one episode can yield both a `REFERENCE` and a `SOLVER` record, both self-consistent.
4. **RT-16** — `league-registry.json` carries `J_solve: 0.75` with no
   `EXECUTABILITY_ONLY_NOT_A_RESULT` stamp; the stamp lives only in `summary.json`.

Standing assurance wording (manual §29): **"0 known critical exploits under attack_suite_version
`hc-v0-redteam-2026-09-08`"** — never "unexploitable".

## 6. The single highest-EV next action

**Build `VerifiedTask` — the interactive environment — and put a real Solver in it.**

Everything else is downstream of this. Today the world is `TRAJECTORY_REPLAY` only: the bank
replays mathlib's own proofs with zero solver actions, so manual §40.3's preferred
`INTERACTIVE_TASK` mode does not exist and **autonomous long-horizon claims remain blocked**. A
real Solver on the current arena buys nothing, because `precondition_ladder` has horizon 1 and the
trajectory world has no policy in it.

Order: (a) `VerifiedTask` over the existing Lean REPL — the state, action-lowering and verifier
interfaces already exist; (b) fix RT-03 and RT-13 first, since both corrupt the record the moment a
real evaluator makes outcomes stochastic; (c) then a Solver, and only then measure anything.

**Do NOT** continue into Pilot 1, resume the Phase-8 founder tournament, hand-design a language,
train an RL Architect, or make any `RSTAR`/`LSTAR` claim (manual §48).

## 7. Reproduce

```bash
uv sync --all-extras
.venv/bin/python -c "import arena, pathlib; print(pathlib.Path(arena.__file__).resolve())"   # must be THIS worktree
.venv/bin/python -m pytest                       # 1,286 passed, 1 skipped
.venv/bin/python -m ruff check . && .venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy arena                   # 142 source files
.venv/bin/python -m arena.evolution.loop --generations 1 --population 4 --seed 20260908 --out /tmp/hcv0
.venv/bin/python -m arena.trajectory.arena_v0 --toolchain-check
.venv/bin/python -m arena.trajectory.arena_v0 --verify artifacts/trajectory_bank_v0/h5 --relive
```

Lean lives at
`/Users/moheet/Documents/ChatGPT/HML_V3/external/runtime_work/leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4`
(5,680 `.olean`, pinned `leanprover/lean4:v4.10.0-rc1` — **always invoke via `env -C $MB`**, the
bare binary reports 4.33.1). Problems at
`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json`
(**not** under `~/Documents/ChatGPT`). The four sealed splits sit beside it and must not be opened.
