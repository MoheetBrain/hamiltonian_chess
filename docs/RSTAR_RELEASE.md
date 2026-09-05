# R*-V0 Release Gate

No R*-V0 package is present. Static compactness is not a language win, and zero-shot behavior
would not satisfy the directive.

| Gate | Current basis |
|---|---|
| executable parser/renderer | available for all eight seeds |
| required-world semantic roundtrip | measured by Tier 0/1 tournament |
| critical assurance defects | measured by frozen v0 suite |
| bounded exhaustive universes | 2,767 enumerated cases |
| differential agreement | three claims, three checker families |
| side-channel audit | action labels withheld by observation projection |
| matched adaptation | **not run** |
| material machine improvement | **not established** |

`arena rstar freeze <candidate>` writes an auditable release decision first. It creates
`artifacts/rstar/v0` only if every gate passes. The current expected decision is
`RSTAR_BLOCKED_BY_MODEL_FITNESS`; this is an honest scientific outcome, not a failed Arena
build.

Allowed future release wording is bounded: zero unresolved critical defects in the frozen
suite, zero false accepts in declared bounded universes, and zero unresolved differential
disagreements on the supported subset. It must not claim perfection or global optimality.
