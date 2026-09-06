# Content Genome V1

`ContentGenome` is the evolvable truth-derived layer inside `ModelViewGenome`. Its exact
machine schema is `arena-model-view-genome-v1.0.0`.

| Gene | Values | Invariant | Primary slices | Cost |
|---|---|---|---|---|
| dependency_projection | IMPLICIT, EXPLICIT_EDGE, EXPLICIT_LOCAL_EDGE | every edge exists in canonical evidence | dependency chain, large context | 1 |
| action_goal_projection | IMPLICIT, TARGET_ID, TARGET_BLOCK | targets come only from displayed actions and canonical objects/goal | assignment, repeated identity | 1 |
| premise_projection | GLOBAL_LIST, ACTION_LOCAL, EXPLICIT_EDGE | premises are canonical assumptions or displayed-option preconditions | attribution, partial operations | 1 |
| obligation_projection | GLOBAL, OWNER_LOCAL, ACTION_LOCAL | obligations and owners are copied from canonical sources | ownership, multiple goals | 1 |
| state_delta_projection | FULL_BEFORE_AFTER, DELTA_PLUS_CONTEXT, EXPLICIT_CHANGED_RELATIONS | delta is recomputed from canonical before/after | delta, large context | 2 |
| evidence_projection | STATUS_ONLY, PROOF_EDGE, LOCAL_PROVENANCE | status/edges/provenance come from canonical evidence | chain, provenance | 1 |

Every value has an executable compiler path. Behavioral novelty tests require all three values
on each axis to produce distinct views on an adversarial fixture while retaining one canonical
mathematical hash. Empty or unavailable relations are declared as omissions; they are never
fabricated. Information accounting records source hashes, relation hashes, omitted relations,
repeated witness count, and UTF-8 byte cost.

Track E uses the same `ModelViewGenome` boundary but emits only the reversible surface. Track C
may add locality and redundancy only through independently derivable statements. Neither track
owns verifier decisions.
