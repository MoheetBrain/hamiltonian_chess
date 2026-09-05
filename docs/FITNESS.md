# Fitness and Promotion

Fitness is lexicographic. No efficiency or model score can compensate for a semantic failure.

1. Gate 0: zero known critical false accepts, canonical collisions, scope corruption, proof
   cycles, definedness escapes, silent semantic losses, or required-world roundtrip failures.
2. Coverage: required constructs, composition, binders, definedness, transitions, and
   cross-domain cases.
3. Machine fitness: reconstruction, next action, legal-action recall, invalid-action rate,
   verified next state, sample efficiency, OOD/depth/cross-domain generalization, and search
   efficiency.
4. Efficiency: characters, tokenizer-specific tokens, bits, parser/model latency, error
   locality, edit robustness, grammar cost, and training budget.

Gate 0 is fail-closed. Coverage may classify a useful partial language as a niche candidate,
but a niche cannot masquerade as a general winner. Surviving candidates are compared on a
Pareto front; the league does not compress all behavior into one Elo scalar.

## Measurement rules

Rates use explicit denominators and confidence intervals where sampling is involved. Static
scoreboards label `ceil(UTF-8 bytes / 4)` as a token proxy, never as a tokenizer measurement.
Unrun model metrics are `UNMEASURED`, never zero. Zero-shot scouts measure acquisition only.
Release requires matched adaptation over the same canonical examples, model digest, optimizer,
updates, seed, and either matched examples or matched token/compute budget.

## Stop conditions

A candidate stops immediately on critical soundness failure, semantic roundtrip failure,
answer leakage, or an unresolved canonical collision. A model scout stops on clear domination,
token explosion, acquisition failure, or poor compatibility without compensating semantic
value.
