# Genome Content Audit

## Finding

The original 14-gene `LanguageGenome` is a strong reversible codec search space, but it has
zero content-bearing and zero reasoning-protocol axes. Every phenotype serializes the same
canonical wire record, and parsing reverses the transformation before strict validation.
The legacy name `STRUCTURAL_SEMANTIC` describes reconstruction burden, not a change in
mathematical information.

The V1 population mutated only eight axes: grammar, binders, types, state, actions,
serialization, morphology, and redundancy. Of those, four are surface and four structural.
Consequently the 120-candidate population was mostly a search over spelling, ordering,
bracketing, binder identity, and type locality—not over what true relations are made explicit.

## Classification

| Existing gene | Class | What it actually changes |
|---|---|---|
| alphabet | SURFACE | character repertoire |
| token_policy | SURFACE | word/symbol/role token spelling |
| morphology | SURFACE | field-label morphology |
| grammar | SURFACE | JSON/prefix/S-expression envelope |
| composition | STRUCTURAL | application/tree form |
| types | STRUCTURAL | type-marker locality |
| binders | STRUCTURAL | recoverable binder identity form |
| state | STRUCTURAL | field ordering/frame/DAG/graph layout |
| actions | STRUCTURAL | recoverable option-result wrapper |
| obligations | STRUCTURAL | recoverable obligation placement policy |
| evidence | STRUCTURAL | recoverable evidence layout policy |
| serialization | SURFACE | line/tree/code/graph envelope |
| redundancy | SURFACE | whitespace and key compression |
| error_locality | SURFACE | delimiter/marker convention |

No existing axis changes canonical truth, derives new facts, omits declared information, or
specifies a reasoning procedure. The machine-readable audit is
`artifacts/reports/genome-content-audit.json`.

## Phase 3 correction

The serious first genome is now two-layered:

- eight retained high-value surface/structural concepts: syntax family, role labelling,
  compression, type explicitness, binder identity, scope/state encoding, action structure,
  and dependency locality;
- six Track C content axes: dependency, action-goal, premise, obligation, state-delta, and
  evidence projection.

Each Track C output includes its canonical witnesses and derivation rule. An independent
recompilation must reproduce the exact view. A content compiler cannot modify or bless
canonical truth, and solver observations contain no legality or usefulness labels.
