# HC-V0.6 handoff

**Verdict: `HC_V0_6_ONE_STEP_TIGHT_NULL`.** Four eligible models, two independent
architecture families, `Δ(R_B − R_A) ∈ [−0.009, +0.011]`, every interval inside ±5 points, no sign
agreement. **Do not begin morphology search on this assay.** The next milestone is one compact
long-horizon kill/continue experiment (§6 below), not `HC-V0.7 MORPHOGENESIS_V0`.

Assume zero context. Governing authority:
`spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md` (unchanged, sha256
`f3c04e69…`). The frozen assay: `docs/HC_V0_6_SPEC.md`, committed at `2624be5` **before any
representation outcome existed**. The numbers: `docs/HC_V0_6_RESULT.md`.

---

## 1. What HC-V0.6 was

The first comparison of two machine-facing representations of the *same* real Lean state, under
kernel verification, one action deep, across four local models. It is a manual §25 **Gate 1 scout**.
It may not crown a language and it is not confirmatory.

## 2. What is reusable, and what it cost

| asset | what it is |
|---|---|
| `artifacts/trajectory/hc_v0_6_anchor_bank.json` | 1,127 anchored Lean states · 393 theorems · 330 files, hash `f13ffee5…`, re-derived 1,127/1,127 in independent processes, 0 reference-tactic leakage. **32 min of Lean to build.** |
| `arena/trajectory/anchor.py` | derivation, re-derivation, oracle segregation, `open_anchor_session` (one Lean session per theorem; every arm branches from one live `state_id`) |
| `arena/trajectory/representation.py` | four arms under a **bijection contract**: an `R_ONLY` arm ships an inverse recovering the baseline bytes exactly, so it can neither add nor remove information |
| `arena/experiments/hc_v0_6/` | cell schema, paired clustered estimators, power/MDE, intersection–union certification gate |
| `arena/experiments/hc_v0_6_assay.py` | the runner: randomised arm order within anchor, runtime oracle tripwire, streamed rows |
| `arena/experiments/hc_v0_6_report.py` | contrasts, gates, realised ICC and MDE, Holm |

Total live compute for the whole sprint: **~4.5 hours** of local inference and Lean. No cloud, no
fine-tuning.

## 3. The three things that would most easily be got wrong next

**1. Policy divergence is not fitness.** Every model changed its proposed tactic on 43–64% of
states under `R_B` — and a *whitespace-only* change moved it on 30–46%. The noise floor for
behavioural divergence is enormous. Any fitness function, surrogate or Architect reward built on
`different_tactic_rate` would be optimising a quantity this experiment has already shown to be
nearly uncorrelated with verified success. Record divergence as a mechanistic diagnostic only.

**2. `R_ABLATED` is a degenerate policy, not a weak language.** Withholding the goal leaves a
rendering that depends only on goal count, so the model saw **five distinct prompts across 1,127
anchors** and emitted **two distinct tactics** (`assumption` ×975, `intro` ×152). It is a correct
sensitivity floor and it must never be read as an estimate of how an information-poor *language*
would perform, nor enter a league or archive.

**3. The preflight was too small to rank models.** At n=45 the baseline estimates were 0.133 /
0.156 / 0.400 (e4b / 12b / qwen); at n=1,127 they were 0.108 / 0.272 / 0.296. The frozen
information-rate rule therefore selected `gemma4:e4b` on noise — with full-bank rates it would have
picked `gemma4:12b`. This cost nothing here, because every eligible model was run anyway and the
primary designation only chose whose controls gate interpretation. It would cost a great deal in a
design where only the primary runs. **Rank models on ≥300 anchors, or not at all.**

## 4. Open defects

| id | severity | what |
|---|---|---|
| RT-V06-08 (second route) | HIGH | per-session Lean scratch paths still reach `result_hash` through `skipped[].reason` and `theorem_errors[].error` in `build_manifest`. Not fixed during the run, deliberately: the runner was producing live cells. Cell data are unaffected; only the manifest's reproducibility claim is. |
| RT-V06-07 | HIGH (measured harmless) | administrative tactics (`rotate_left`, `rename_i`, `clear`) could score the endpoint without doing mathematics. The preregistered sensitivity check found **0 of 438 events** were of this shape on the primary. Re-check on any new endpoint. |
| missingness gate | — | exact per-arm equality is not a defensible operationalisation of "arm-dependent missingness"; it fires on a single unrelated environment error. It fired here as a **false block** and was not weakened after the fact. Operationalise it properly *before* the next run. |
| `T_ablate` | — | fixing it from a 45-anchor preflight baseline made it 0.0665 when half the realised baseline was 0.0539. Fix such thresholds from a large baseline, or express them relative to the realised rate **in the freeze**. |

The full red-team suite (0 CRITICAL, 8 HIGH, 7 MEDIUM, 7 LOW) is `docs/HC_V0_6_REDTEAM.md`; all
eight HIGH in the analysis layer were closed before any number was read.

## 5. Reproduce

```bash
.venv/bin/python -c "import arena, pathlib; print(pathlib.Path(arena.__file__).resolve())"
.venv/bin/python -m pytest
.venv/bin/python -m arena.trajectory.anchor                      # rebuild the bank (~32 min Lean)
.venv/bin/python -m arena.experiments.hc_v0_6_assay --live --model gemma4:e4b \
    --seed 20260909 --out trajectory/hc_v0_6_primary_gemma4_e4b
.venv/bin/python -m arena.experiments.hc_v0_6_report \
    artifacts/trajectory/hc_v0_6_primary_gemma4_e4b_cells.jsonl --model gemma4:e4b
```

Lean 4.10.0-rc1 at the built mathlib checkout; models served by ollama 0.33.2 at
`localhost:11434`. TRAIN split only; the four sealed splits were never opened.

---

## 6. The constraint that decides the next experiment's design

At the one-step acceptance rates this sprint measured, **a no-retry autonomous episode has no
horizon to study**. An episode that ends at the first rejection has a geometric length, so:

| model | measured `p_accept` | E[accepted transitions before first rejection] | P(≥ 4 in a row) |
|---|---|---|---|
| `gemma4:e4b` | 0.1077 | 0.12 | 0.013 % |
| `gemma4:12b` | 0.2724 | 0.37 | 0.55 % |
| `qwen3.6:27b-mlx` | 0.2963 | 0.42 | 0.77 % |

Across 393 theorems × 2 arms that is **three to six episodes** reaching depth 4. HC-V0.5's longest
autonomous chain was 4, and it used a retry.

So `VERIFIED_LONG_HORIZON_ARENA_V0` cannot simply be "the same assay, but let it run". Horizon is
created by an **attempt budget**, not by permission to continue: the episode must terminate on
budget exhaustion rather than on first failure, and the budget `B` is the parameter that generates
the horizon distribution. That choice is the design, and it brings its own confound — a larger `B`
is more compute, so the arms must be **attempt-matched**, not step-matched (manual §26.2 fixes the
compute regime).

### Sketch, to be specified properly before anything is run

* **Tasks**: the frozen bank's 393 theorems at prefix 0. Already probe-buildable, leakage-filtered
  and re-derivable; no new corpus work.
* **Arms**: `R_A` vs `R_B` only. Two arms keeps it compact and the pair is the one under test.
* **Budget**: `B` attempts per episode, terminating on exhaustion. Pick `B` from a pilot so the
  survival curve has mass past depth 3 — otherwise the experiment measures nothing it does not
  already know.
* **Endpoints**: complete verified solve (primary); conditional next-step hazard `h_k`;
  accepted-transition survival; first-error depth.
* **The analysis that avoids the tautology.** HC-V0.5 measured that a *constant* per-step edge makes
  the absolute completion gap peak around H = 8 and then decay — γ(20) − γ(1) = +0.039 against
  γ(80) − γ(20) = −0.074, both from the same null. So "the gap grows with horizon" is not evidence.
  What must be tested is an **arm × depth interaction in the hazard**: fit `h_k` per arm, project
  the survival curve a constant edge would produce from the depth-1 rates, and ask whether the
  observed long-horizon behaviour departs from that projection *differently by arm*. Plus rank
  reversal between depth buckets, and super-compounding relative to the short-horizon expectation.
* **Precision**: with a complete-solve rate near 0.03, the frozen bank's 330-cluster profile gives
  an MDE near 2 points — enough to detect a doubling. The rare endpoint helps here; it is the
  attempt budget, not the sample, that is the binding constraint.

### The honest prior going in

The one-step per-step edge measured here is **≤ ~2 points and centred on zero**. If the per-step
edge is genuinely zero, nothing compounds and no horizon effect can exist. The long-horizon
experiment is therefore not "the same question with more steps" — it is a **different hypothesis**:
that a representation helps *maintain and manipulate mathematical state across decisions* even when
it does not help pick any single next tactic. That is a real and distinct claim, and it is the last
high-value version of the thesis this project has not tested.
