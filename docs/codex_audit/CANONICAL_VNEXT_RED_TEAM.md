# Canonical-vNext Red-Team Review

## Bottom line

The current schema is adequate for World-v0 and the narrow V5 structural probes, but not a
lossless Lean tactic-state substrate. vNext should be driven by the first selected real task
family, not by a universal-foundation ambition.

## Gap classification

| Proposed gap | Classification | Code evidence / scope |
|---|---|---|
| multiple goals with stable IDs | `PROVEN_REQUIRED` | `CanonicalState.goal` is singular; real tactic states can have multiple metavariables |
| metavariable assignments/shared context | `PROVEN_REQUIRED` | no metavariable map exists; required for faithful before/after Lean state identity |
| dependent binding types | `PROVEN_REQUIRED` | `Binding.type_name` is a string, not an expression, so types cannot refer structurally to earlier bindings |
| implicit and instance arguments | `LIKELY_REQUIRED` | expression attributes can carry strings but no typed argument role; needed for information-parity audits and Lean replay |
| substitutions | `PROVEN_REQUIRED` | no explicit substitution/environment record; expression rewrite alone loses assignment provenance |
| definitional equality/reducibility | `BACKEND_SPECIFIC` | native verifier lacks defeq; Lean kernel can remain authoritative without reimplementing reduction canonically |
| universes | `BACKEND_SPECIFIC` | necessary for lossless Lean term import, not for every Arena environment |
| distinct-variable constraints | `BACKEND_SPECIFIC` | essential for Metamath/set.mm, not demonstrated as an immediate Lean pilot blocker |
| typed tactic/premise references | `LIKELY_REQUIRED` | `CanonicalAction.operation` and warrant are free strings; tactic and external premise identities need typed provenance |
| typed import provenance | `PROVEN_REQUIRED` | trajectory provenance is a free string map; scientific identity requires repo/ref/SHA/adapter/split/hash |
| failed alternatives/search history | `NOT_CANONICAL` | belongs in controller/trajectory records unless it changes mathematical state |
| universal tactic microsteps | `DEFER` | operation audit shows tactic heads do not map one-to-one to semantic effects |

`[VERIFIED_BY_CODE]`

## Corrections to the existing gap report

The audited pinned Mathlib checkout has 38 `.olean` files, not 5,680, and the available fresh
sample is 32 replay passes / 68 nonpass. Therefore “fully built” and immediate full replay are
`REPORTED_NOT_REPRODUCED`. Re-run a target-specific build and attestation preflight before using
that claim in estimates. `[VERIFIED_BY_SOURCE_DATA]`

## Architecture critiques

### Typed e-graph

An e-graph is useful only if the task requires large equivalence classes and a trusted typed
rewrite relation. It does not by itself represent metavariable context, proof obligations,
universe constraints or tactic-state provenance. Adopting it now would add canonicalization and
extraction choices that themselves become P/R confounds. `DEFER`.

### MMT/OMDoc

MMT/OMDoc can provide cross-library interchange and theory morphisms. Current evidence is one
Lean-backed near-term task, not a cross-foundation requirement. Mapping Lean definitional
equality and elaboration into a universal interchange layer would be a separate research
programme. `DEFER` until a second backend supplies a concrete failing use case.

### Universal tactic microsteps

The operation audit finds controller commands, mathematical effects and backend automation at
different granularities. Forcing `simp`, `rw`, `linarith` and a hand-authored algebra sentence
into one universal primitive loses evidence. Preserve raw actions plus verified semantic deltas;
derive common operations only where adapters agree. `DEFER`.

## Minimal vNext for the recommended pilot

Add versioned `goals[]` with IDs; ordered context entries whose types are expressions; typed
metavariable/assignment and substitution maps; explicit argument roles; external premise refs;
and typed provenance. Keep Lean kernel acceptance in `VerificationRecord`. Do not add universes,
e-graphs or other proof-assistant semantics to the common core until the chosen tasks require
them. Migration must change the schema version and hashes between experiments, never during one.
