# Fitness V3 Founder Tournament

Frozen instrument commit: `96166546ab5f0add41f7cf3b6ef58657c1f97747`  
Manifest: `6f1f6c4244d675863402d40536d67270fd8789b050e524bc1fdaa99b6aa09138`  
Result: `6b1eb4fa2dacd4f027208a2854985de4b3af9ed5c0929f6002293513300d4b09`

The tournament completed 432 calls: 12 candidates × 36 identical frozen probes. Every arm has
all 36 rows and all 12 candidates share the same 36 probe IDs. There were no runtime errors.
The runner was sequential; 66 rows were resumed from identity-validated cache after an
interruption exposed and fixed the cache reader's wrapper handling.

## Results

| Candidate | Positive | Destroyed | Flip | Position invariant | Valid |
|---|---:|---:|---:|---:|---:|
| Compact symbolic | 100.0% | 50.0% | 100.0% | 100.0% | 100.0% |
| Structured English | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| Current HML | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| S-expression | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| JSON/typed AST | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| Typed prefix | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| Graph triples | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| Role-labelled hybrid | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| JSON Track C baseline | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| JSON delta-context child | 83.3% | 41.7% | 83.3% | 83.3% | 83.3% |
| JSON explicit-dependency child | 66.7% | 41.7% | 66.7% | 66.7% | 72.2% |
| JSON target-block child | 50.0% | 25.0% | 50.0% | 50.0% | 50.0% |

Compact symbolic had two paired wins and zero losses against JSON, both on state delta. The
one-sided exact sign p-value was .25; net wins 2 missed the frozen minimum 4 and Holm threshold
.00455. No candidate passed all promotion checks. The content children did not help; two were
strictly worse through malformed output/extra context.

## Invalidity finding

The aggregate 50-point range is not a qualified landscape. At mechanism level, dependency,
action-goal, premise, obligation, and provenance were each 100% for all equal-information
founders. State delta was 0% for seven founders and 100% only for compact symbolic. Thus V3
combined five ceiling tasks with one floor task and its aggregate DEV qualification rule hid
that bimodality.

This violates the governing V3 requirement that useful tasks avoid ceiling and floor. The
formal preregistered aggregate check passed, but the instrument is substantively invalid for
candidate promotion. No founder is promoted, no 30–60 mutation campaign is authorized, and no
matched adaptation is authorized.
