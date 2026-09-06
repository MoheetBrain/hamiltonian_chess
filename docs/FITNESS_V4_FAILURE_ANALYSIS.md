# Fitness V4 Failure Analysis

Result: `FITNESS_V4_NOT_QUALIFIED`. Zero of five mechanisms passed the preregistered
per-mechanism gates (`docs/FITNESS_V4_SPEC.md` §7). No founder call was made. Nothing in the
frozen rule was changed after results were read.

Primary artifacts: `artifacts/experiments/fitness_v4/development/result.json` (356 calls,
Q0 1.000), `artifacts/experiments/fitness_v4/frozen_manifest.json` (`qualified=false`, no
SCOUT probes), `artifacts/experiments/fitness_v4/not_qualified.json`, forensics in
`artifacts/reports/fitness-v4-forensics.json` (schema `arena-fitness-v4-forensics-v1`).

## 1. Per-mechanism verdicts

| Mechanism | Ladder L0..L4 | Verdict | Frozen reason |
|---|---|---|---|
| expression_depth_recurrence | .833 .583 .417 .667 .750 | VOID_INSTRUMENT_LIMIT | L0 explicit positive .833 < .90 |
| transitive_dependency | 1.0 1.0 .583 .333 .417 | VOID_VALIDITY | valid-response .528 at L2 (also fails flip .167 and position invariance .417) |
| binder_scope_resolution | .750 .500 .500 .500 (.000 unsent) | VOID_INSTRUMENT_LIMIT | L0 explicit positive .750 < .90 |
| precondition_conjunction | 1.0 .667 .583 .500 .500 | VOID_FLIP | semantic flip .333 ≥ .25 but choice flip .333 < .50 at L1 |
| state_delta | .500 .083 .083 .500 (.000 unsent) | VOID_INSTRUMENT_LIMIT | L0 explicit positive .500 < .90 |

## 2. Diagnostic causes (separate from the frozen verdicts)

Of 348 scored rows: 179 correct, 13 negative-control answers, 67 semantic errors,
59 `REASONING_EXCEEDS_COMPLETION_BUDGET`, 24 `OVER_BUDGET_UNSENT`, 6 `CONTEXT_TRUNCATION`
(the last two are guard false positives, see §3.5).

Every one of the 59 reasoning-overflow rows begins with a prose derivation ("To find the
transitive dependency … Step 1 …") and stops at exactly 64 completion tokens without ever
emitting `"choice"`. They concentrate where the answer is not a single lookup: transitive
dependency L2–L4 (26), state delta L0-L3 (6+11+11+4 = 32; L4 was never sent), depth L1 (1).

A second, independent pattern is a **constant-position policy under uncertainty**. At the
hard levels the parsed answer is "A" on 12 of 12 positives (precondition L3 and L4, binder
scope L1 and L2) and 29 of 36 at precondition L1. Balanced targets make that read as 0.500,
which the frontier selector cannot distinguish from partial reading; the choice-flip gate
(counterfactual must change the answer) is what caught it. This is the V1 failure mode
(`22cab97`) reappearing whenever the task exceeds what the Solver can do in one greedy step.

## 3. The eight questions, per mechanism

### 3.1 expression_depth_recurrence

- Model too weak? Partly: even at depth 3 with a single occurrence per identity it misses
  2 of 12, both counterfactuals answered "A". Ladder is non-monotonic (.42 at L2, .75 at
  L4), consistent with HML_V3's finding that depth and recurrence are not dose–response.
- Too easy? No. Too hard? Not uniformly; L2 sits at chance.
- Relation unnecessary? No: destroyed arms were never run because L0 failed.
- Context bottleneck? No; ≤ 5.9K tokens.
- Response protocol? Minor (1 overflow row).
- Generator artefact? Not detected; truth re-derived by walk; shortcut audit clean.
- Measurable? Only with a reasoning budget or a stronger reader; the L0 gate is the honest
  reason it is void.

### 3.2 transitive_dependency

- Model too weak? No at 1–2 hops (1.000); at 3 hops it *starts* the right procedure.
- Too easy at L0–L1, at chance-with-prose at L2+.
- Relation unnecessary? No: destroyed target accuracy .083 (the model reasons rather than
  guesses when the relation is gone).
- Context bottleneck? No; ≈ 3.1K tokens.
- **Response protocol: yes, decisively.** 17 of 36 rows at L2 are reasoning overflow.
- Generator artefact? Shortcut audit clean (.667 first-mentioned on 12 items is within the
  rule); ids hashed and shuffled.
- Measurable? Yes, given a completion budget that lets a multi-hop trace finish. This is the
  strongest candidate mechanism for V5.

### 3.3 binder_scope_resolution

- Model too weak? Yes for this protocol: .750 with a single binder.
- Too hard from L1 on: constant "A".
- Relation unnecessary? Not tested (L0 failed).
- Context bottleneck? Not for the model; **the guard** blocked L3/L4 because deeply nested
  JSON is whitespace-heavy. The pre-guard assumes 2.0 characters per token; the measured
  maximum on these prompts is 6.12 (binder L3: 45,310 characters / 7,409 tokens), so the
  guard over-estimated tokens by roughly 3x.
- Response protocol? No overflow rows.
- Generator artefact? The nested `forall/exists/lambda` with attributes is heavy; the task may
  also be under-specified for a reader that does not know Arena's binder attribute convention
  (only the syntax guide describes it). Possible `TASK_AMBIGUITY`.
- Measurable? Not with this Solver at one greedy step.

### 3.4 precondition_conjunction

- Model too weak? No at k=1 (1.000); the conjunction of two premises with a near-miss
  already drops to .667 with a strong "A" lean.
- Ladder is monotonic and reaches a constant-position floor by k=5.
- Relation unnecessary? No: gap .167 with destroyed at exactly .500.
- Context bottleneck? No.
- Response protocol? No overflow.
- Generator artefact? None detected; shortcut audit clean at .5.
- Measurable? The gate failure is choice flip .333: the counterfactual changed the answer in
  only 2 of 6 families. The mechanism has headroom but the Solver's answer is mostly
  position-driven at k ≥ 2 under this protocol.

### 3.5 state_delta

- Model too weak? Under this protocol, yes: .500 at four facts, with half the rows overflowing.
- Relation unnecessary? Not testable (L0 failed).
- **Context bottleneck? Two different ones.** Prompts up to 17K tokens were sent and read
  (no true truncation), but the pre-guard voided L4 (66K characters ≈ 23K tokens, inside the
  32K budget) because chars/2.0 over-estimates tokens for indented JSON. L4 was never sent,
  so its true token count is an estimate. This is a defect in the
  V4 guard constants, not in the Solver.
- Response protocol: yes; two-state comparison invites a written diff.
- Generator artefact? The V3 operator-name leak was removed; audit clean.
- Measurable? Only with a reasoning budget, and only at prompt sizes the guard handles
  correctly.

## 4. What is instrument, what is Solver, what is representation

- **Instrument defects found (fix before any V5):** (a) the character-based pre-guard and the
  chars/6 post-check are representation-specific; replace with a model-tokenizer count or
  with a send-then-verify rule that uses the Ollama truncation signature only; (b) level 0 of
  depth, binder and delta is not an explicit-positive control in the sense of
  "relation stated outright" — it is merely the smallest structural size; V5 must add a true
  explicit-positive arm (the answer relation asserted directly in the state) per mechanism.
- **Solver/controller limit found:** a single greedy 64-token JSON answer cannot carry any
  mechanism that needs more than one lookup; the model either overflows into prose or falls
  back to a constant position. This is a property of `C` and `B`, frozen for all candidates,
  so it is not a representation result and must not be reported as one.
- **Representation:** nothing was measured about any representation. All rows are the JSON
  control.

## 5. Next versioned instrument

The failure is not a narrow engineering correction: the response contract (`C`/`B`) must
change and two mechanisms need redesign. Therefore the next instrument is **V5**, preceded by
the DEV-only budget calibration in `docs/V4_1_PROTOCOL_CALIBRATION_PROPOSAL.md` (which may be
run as V4.1 because it changes only `B`/response contract on the control). V5 must:

1. adopt the calibrated output budget and the "reason, then final JSON" contract for every
   candidate identically;
2. add a true explicit-positive arm per mechanism;
3. fix the context guard;
4. keep transitive_dependency and precondition_conjunction as the lead mechanisms (both have
   a working explicit positive and a monotone ladder), re-specify binder scope with a plainer
   binder encoding, and treat depth and delta as secondary;
5. preregister before any founder call, as V4 did.

Route B (low-budget matched learning curves) remains the stronger alternative if V5 also
fails to obtain valid zero-shot headroom; see `docs/ROUTE_B_HISTORICAL_AUDIT.md`.
