# HC-V0.5 Handoff — a real player is in the game

**Sentinel: `HC_V0_5_REAL_PLAYER_EXECUTABLE`.**

Assume zero context. Governing spec:
`spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` (sha256 `f3c04e69…`,
unchanged). `GOAL.md` preserved (`43d8fcdb…`). Predecessor: `docs/HAMILTONIAN_CHESS_V0_HANDOFF.md`.

---

## 1. What HC-V0.5 achieved

A real Solver autonomously played real Lean mathematics under kernel verification. The decisive
episode, `LinearEquiv.snd_comp_prodComm`: four consecutive Solver-proposed tactics, each accepted
by the elaborator, terminal `CLOSED_VERIFIED`. No reference tactic was consulted and none could
have been.

Smoke bank (`artifacts/trajectory/hc_v0_5_smoke.json`): **30 episodes · 4 solved · 16 accepted
Solver transitions · 47 rejected · 0 parse failures · longest autonomous chain 4 · all 30
trajectories emitted with states, `pp_sha256` and kernel receipts.**

Acceptance criteria [1]–[17] of the directive: all met. Every Solver transition carries
`actor=SOLVER`; environment failure is typed apart from mathematical failure; provenance is
durable; gates pass.

## 2. The three findings that matter more than the solve rate

**(a) The runtime is not reproducible, and temperature 0 does not fix it.** Two runs of an
identical 6-task configuration gave different `result_hash`. Every Lean state and kernel receipt
was identical; only Solver output diverged, and only on retries — with **identical
`prompt_sha256` and identical prompt token counts**. In isolation the same prompt returns the same
answer six times out of six; the divergence appears once other calls have passed through the same
server process. **HC-V0.6 is a paired assay and paired designs assume exactly the reproducibility
this runtime lacks.** Settle this before any language comparison: measure the variance and carry
it as a random effect, or find a call-for-call reproducible configuration.

**(b) The environment is genuinely a game.** Measured independently before the task layer existed
(`research/phase9/interactive_probe/`): across 14 theorems Lean accepted a **non-reference** tactic
in **10**, and in **2** an alternative closed a goal mathlib proves differently. A policy can take
its own path.

**(c) `thinking` silently voids the Solver.** This model has a capability the previous one lacked.
With `think` omitted or true, its answer is diverted to a separate field and `response` returns
empty — every proposal would be a parse failure and the run would read as "the model cannot do
Lean". `think=False` is frozen with the measurement beside it.

## 3. Red team — `hc-v0.5-redteam-2026-09-08`

**25 confirmed defects, 0 CRITICAL, 7 HIGH.** No critical exploit, so the milestone is not blocked
on soundness: Lean never accepted a false proof, no harness fault paid reward, and no reference
tactic reached the prompt.

**But the attribution is weaker than the mathematics.** The sharpest result: an episode whose every
action came from the LeanDojo record can be emitted as `actor=SOLVER`, kernel-verified, and pass
`verify_bank(relive=True)`. Four findings must close before any autonomy or long-horizon claim is
made from the smoke artefact:

| id | what |
|---|---|
| **V05-01** | an oracle-fed episode is byte-shaped like an autonomous one |
| **V05-02** | the solver digest was a module constant nothing verified — **fixed this session** |
| **V05-03** | `build_trajectory` still rewrites every action's actor; `"actor": "SOLVER"` is a literal |
| **V05-24** | the runner emitted no re-verifiable trajectory — **fixed this session** |

Also fixed here: **V05-10** (`selection` was `{}`), **V05-11** (every `state_id` was `"?"`,
`task_id` was the problem id). The remaining 21 are recorded with reproductions in
`docs/HC_V0_5_REDTEAM.md`.

Previous suite: RT-01, RT-02, RT-03, RT-13 and the stub-fitness defect are genuinely closed with
before/after evidence. **RT-04 is not** — a relabelled mathlib replay still passes relive claiming
`solver_actions=5`; it is closed only at the ledger layer.

## 4. Record-integrity work done before any stochastic call (directive §3)

- **RT-03** — `relive` now executes the **artifact's own actions**, not the source proof, and names
  the offending index. **RT-02** — session, scope and problem identity are bound at load.
- **RT-13** — the evaluation identity went from **11 to 21 components**; proposal bookkeeping
  (`proposal_id`, `mutation_hash`) is excluded, so a re-roll yields `SAME_CONDITION_REUSE`. A
  second draw needs an explicit `ReplicateAuthorisation`.
- **RT-04** — actor is bound into identity *and* condition; `ActorPoolingViolation` on a mixed
  query; a `REFERENCE` actor cannot hold a fitness reading at all.
- **RT-16** — stub fitness is **type-level unrepresentable**: `StubFitnessNotRepresentable` raises
  at construction, and the archive ranks on `EXECUTABILITY_STUB::…` keys with observations written
  `verified=False`.

## 5. What HC-V0.5 does NOT prove

Nothing about representations, languages, horizon effects, or capability. The 4/30 solve rate is
one model, one interface, one prompt. mathlib4 is `HISTORICALLY_EXPOSED` transitively, so nothing
separates a solved goal from a recalled one: the defensible phrasing is **long-horizon execution
under kernel verification**, never reasoning or discovery. No `RSTAR`/`LSTAR` claim.

## 6. Highest-EV next action

**Settle runtime reproducibility (finding (a)), then close V05-01 and V05-03.** In that order.

Reproducibility is first because it silently invalidates the *design* of HC-V0.6, not just its
bookkeeping. V05-01/03 are next because they are what make an episode's attribution auditable —
until they close, the artefact cannot support the claim that a Solver did what it says. The
recommended minimal fixes are in `docs/HC_V0_5_REDTEAM.md` §7: bind the action to the policy that
produced it (prompt hash + solver digest inside `semantic_core`), and make `build_trajectory`'s
actor an assertion via the existing `require_single_actor`.

**Do NOT** begin HC-V0.6, Pilot 1, multi-generation evolution, fine-tuning, or an RL Architect.

## 7. Reproduce

```bash
.venv/bin/python -c "import arena, pathlib; print(pathlib.Path(arena.__file__).resolve())"
.venv/bin/python -m pytest                      # 1,483 passed, 1 skipped
.venv/bin/python -m arena.trajectory.arena_v0 --toolchain-check
.venv/bin/python -m research.phase9.interactive_probe.probe_non_reference_actions
.venv/bin/python -m arena.trajectory.episode --live --tasks 30 --seed 20260908 \
    --scan-limit 12000 --out trajectory/hc_v0_5_smoke.json
```

Lean 4.10.0-rc1 at the built mathlib checkout (`…/runtime_work/…/mathlib4`, 5,680 `.olean`,
**always via `env -C $MB`**). Tasks from the LeanDojo **train** split at
`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/…/random/train.json`. The four
sealed splits sit beside it and were never opened.
