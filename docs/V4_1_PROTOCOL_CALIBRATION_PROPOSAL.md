# Fitness V4.1 Proposal — Solver/Controller Output-Budget Calibration (NOT RUN)

Status: PROPOSAL ONLY. Nothing here has been executed. It may run only after Fitness V4
reaches its preregistered stopping condition and a new experiment version is explicitly
authorised.

## 1. Why this proposal exists

V4 DEV forensics (`artifacts/reports/fitness-v4-forensics.json`) show one dominant failure
class in the multi-step mechanisms: the Solver begins a correct-looking step-by-step
derivation in prose, consumes the entire 64-token completion allowance, and never emits the
`{"choice":"A"}` JSON. Every such row is scored malformed. This is not a representation effect
and not a context-window effect (those prompts are ≈ 3,100 tokens against a 32K budget). It is
an interaction between the frozen controller `C` (single greedy response, no reasoning) and
the frozen budget `B` (`num_predict=64`, `think=false`) and mechanisms that genuinely need
more than one lookup.

`GOAL.md` §13 requires a universal response protocol; it does not require a reasoning budget
of zero. The takeover directive forbids *reducing* reasoning budget to manufacture spread; the
present configuration is the reduced regime.

## 2. Purpose (and non-purpose)

Purpose: determine the **minimum non-sabotaging output budget** under which the qualified
Solver can carry out the intended structural reasoning and still return the universal
response protocol reliably (≥ 95% valid) on the explicit-positive and frontier levels.

Non-purpose: this calibration must not create representation score spread, must not select
on any candidate representation's result, and must not touch Σ, P, τ, π, D, U, V or the
control R.

## 3. Frozen variables

Σ, P (Track E default), τ, π (`gemma4:12b` digest `4eb23ef1…`), D (the V4 DEV ladders,
same salts), U, V, and R = `V4E_L3_JSON_AST` only. Context `num_ctx=32768` unchanged.

## 4. Factorial (DEV only, control only)

| Factor | Levels |
|---|---|
| `num_predict` | 64 (baseline), 128, 256, 512 |
| `think` | false (baseline), true with a think prefill if the served model supports a separate channel (HML_V3 `FM-056` found `gemma4` needs a prefill; otherwise this level is dropped and recorded as not technically meaningful) |
| response contract | "reason briefly, then end with exactly the JSON" versus baseline "JSON only" |

Cells: 4 × 2 × 2 = 16, minus infeasible `think` cells. Two mechanisms passed L0 in V4
(transitive_dependency, precondition_conjunction); each cell runs their L0 and frontier
positives. The three mechanisms voided at L0 — depth (.833), binder scope (.750) and state
delta (.500) — are included at L0 only, to test whether their explicit positive was itself a
budget artifact. Approximate cost: 16 cells × (2 × 2 + 3 × 1) × 12 positives ≈ 1,344 calls at 64–512 completion tokens; the 512-token cells dominate wall-clock.

Parser: the JSON object must be the last non-whitespace content of the response; anything
before it is ignored but recorded. Malformed remains malformed.

## 5. Preregistered selection rule

Choose the **smallest** budget cell such that, for every mechanism not void at L0:

- valid-response rate ≥ 0.95 at L0 and at the DEV frontier level (frontier levels exist only
  for the two mechanisms that passed L0 in V4);
- L0 positive accuracy ≥ 0.90;
- frontier positive accuracy within [0.35, 0.85];
- destroyed-twin decisions remain identical (determinism) and destroyed target ≤ 0.60.

Ties go to the smaller `num_predict`, then to `think=false`, then to the baseline contract.
If no cell satisfies all conditions for at least two mechanisms, the result is
`V4_1_NO_VALID_BUDGET` and the next step is a Solver-family change, not a rule change.

## 6. What changes downstream

The selected cell becomes the frozen `C`/`B` of V5 (or V4.1 if only `num_predict` changes).
Because `B` changes, the runtime hash changes, Q0 is re-run, and every V4 number is retained
as historical. Token cost per candidate must then be reported including completion tokens,
since a longer reasoning budget lets verbose surfaces spend more.

## 7. Explicit risks

- Enabling reasoning re-introduces controller variance: the same representation may be read
  differently by different reasoning traces. Temperature stays 0 and the seed is fixed, but
  rank stability across two seeds must be measured before any founder result is believed.
- A longer output budget raises latency roughly linearly; founder tournaments become
  2–4× slower.
- Reasoning text can leak option position ("Option A …"); the position-swap invariance check
  remains mandatory.
