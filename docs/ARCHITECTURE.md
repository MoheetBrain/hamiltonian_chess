# Architecture

## Trust boundary

The canonical package owns mathematical records and stable identity. The verifier package
owns acceptance. Candidate language packages own only encoding and decoding. The model never
receives the hidden canonical record in a communication-bottleneck evaluation.

Hard gates execute before machine-fitness or efficiency objectives. A critical issue sets the
candidate state to `ELIMINATED`; no weighted score can revive it.

## Dependency direction

```text
canonical <- verifier <- assurance
    ^            ^           ^
    |            |           |
languages <- compiler     refuter
    ^                        |
    +-- genome <- architect-+

tasks -> evaluation -> fitness -> league -> reports/release
storage is used by orchestration but defines no mathematical truth
```

The v0 canonical IR is deliberately small. Type-B or Type-C mutations do not silently mutate
it; they create an explicit schema proposal and invalidate the dependent assurance cache.

## Evaluation tiers

- Tier 0: genome validity, executable codec, canonical roundtrip, reconstruction, coverage,
  syntax diagnostics, and static cost.
- Tier 1: Tier 0 plus the assurance-facing league record and promotion evidence.
- Tier 2: matched short adaptation on identical canonical examples and a declared example or
  token/compute budget. It requires an explicit external training runner.

Frozen-model scouting, Refuter attacks, differential checks, and bounded exhaustive universes
are named campaigns rather than fictitious model-training tiers. Only measured values appear in
the dashboard. Unrun metrics are `UNMEASURED`, never optimistic zeros.
