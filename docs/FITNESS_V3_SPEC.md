# Fitness V3 Preregistration

Version: `arena-representation-fitness-v3` / instrument
`arena-structural-frontier-instrument-v3.0.0`.

## Purpose and construction

V3 measures structural reading at the qualified solver frontier. It is not a modified V2 and
does not reuse V2's 15-point control-range rule. Tasks are freshly generated from canonical
relations and independently determined by generator/oracle records. The six first mechanisms
are dependency chain, action-goal assignment, premise attribution, obligation ownership,
state delta, and evidence provenance. Complexity adds long chains and 16–32 irrelevant or
repeated records rather than reducing model inference quality.

Each family contains original, truth-changing counterfactual, two information-identical
destroyed siblings with opposing balanced targets, and position-swapped copies of both
positive states. Options expose no legality or usefulness label. All states pass the native
verifier. The response schema is exactly `{"choice":"A"}` or `{"choice":"B"}`.

## DEV selection and qualification

The development pool is 12 families / 72 probes: two complexities for every mechanism.
Selection is absolute and representation-blind: for each mechanism select the complexity
whose permanent JSON/typed-AST control positive accuracy is closest to 62.5%, tie-breaking by
stable family ID. It may not select by a candidate's relative win.

The selected instrument qualifies only if all checks pass:

- Q0 format validity ≥95%;
- positive accuracy 40–85% inclusive;
- positive-minus-destroyed gap ≥10 percentage points;
- semantic flip consistency ≥50%;
- position invariance ≥60%;
- all six mechanisms represented.

After DEV selection, independent SCOUT task salts, prompts, response schema, model digest,
runtime, metrics, and rules are frozen before founder/evolved-candidate calls.

## Candidate inference and power

SCOUT contains 12 positive outcomes per candidate. It is intentionally a large-effect scout,
not an equivalence test: five all-win discordances are the smallest pattern reaching one-sided
exact sign-test p<.05. Candidate promotion requires ≥95% valid responses, at least four net
paired wins against the permanent control, one-sided exact sign p≤.05 after Holm correction,
and semantic-flip noninferiority no worse than five points. No fixed accuracy delta is imposed.

Small SCOUT non-significance means “not promoted,” never “representations are equivalent.”
Promotion and OOD must use fresh frozen families. Matched adaptation is forbidden until a
signal replicates beyond SCOUT.

## Frozen result

DEV selected complexity 1 for every mechanism and passed every gate: Q0 100%, positive 83.33%,
destroyed 41.67%, flip 83.33%, position invariance 83.33%. Frozen SCOUT manifest:
`6f1f6c4244d675863402d40536d67270fd8789b050e524bc1fdaa99b6aa09138`.
