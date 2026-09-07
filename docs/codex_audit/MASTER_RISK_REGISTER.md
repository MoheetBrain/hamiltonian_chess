# Master Scientific Risk Register

Machine-readable source: `research/codex_audit/risk_register.json`. Counts: 22 risks — 5
critical, 13 high, 4 medium. Evidence tags follow the master directive.

| ID | Severity / status | Risk and evidence | Scientific consequence | Cheapest action / owner |
|---|---|---|---|---|
| R-001 | CRITICAL / FIXED | model name and cache digest were decoupled; guarded in V5 solver registry and preflight `[VERIFIED_BY_CODE]` | another model's cached rows could be misattributed | keep digest preflight and mismatch regression / CLAUDE |
| R-002 | HIGH / CONTAINED | Gemma renderer added 12 tokens; Qwen did not `[VERIFIED_BY_ARTIFACT]` | solver comparison could be framing comparison | retain bare/bare and exact hashes / CLAUDE |
| R-003 | CRITICAL / FIXED | Gemma-bare temporarily overwrote Phase-5 `result.json`; exact SHA restored `[VERIFIED_BY_ARTIFACT]` | frozen primary artifact replacement | refuse writes to frozen destination / CLAUDE |
| R-004 | CRITICAL / OPEN | Qwen artifact has 13 ladder + 48 full-family cache hits `[VERIFIED_BY_CODE]` | literal Phase-6 invalidation rule fired | classify invalid; refine future rule, never retroactively / CLAUDE |
| R-005 | HIGH / OPEN | selector target .625 but gap gate requires ≥.70 `[VERIFIED_BY_CODE]` | selector can choose an incapable cell | align next selector/control / FUTURE_RESEARCH |
| R-006 | HIGH / OPEN | formal depth first-mentioned/preorder = 1.0 shallow, .917 deep `[VERIFIED_BY_CODE]` | depth performance is shortcut-confounded | jointly balance cues or retire / FUTURE_RESEARCH |
| R-007 | MEDIUM / HISTORICAL_ONLY | Route-B seed is inert `[VERIFIED_BY_CODE]` | membership was not randomized | seeded within-domain shuffle / CLAUDE |
| R-008 | HIGH / HISTORICAL_ONLY | Stage B contains 424 GOLD, 104 SILVER, 48 REJECT `[VERIFIED_BY_SOURCE_DATA]` | quality confounds learning curve | GOLD-only baseline / CLAUDE |
| R-009 | HIGH / HISTORICAL_ONLY | 21/48 DEV answers/problems recur; 5 exact problems `[VERIFIED_BY_CODE]` | memorization/template transfer not isolated | group split by normalized problem/template / CLAUDE |
| R-010 | HIGH / HISTORICAL_ONLY | arbitrary wrong keyed JSON scores verified=1 `[VERIFIED_BY_CODE]` | “verified” is not mathematical validity | call actual verifier / CLAUDE |
| R-011 | MEDIUM / HISTORICAL_ONLY | five separate hard-coded codecs `[VERIFIED_BY_CODE]` | no individual gene attribution | one phenotype interpreter for gene claims / FUTURE_RESEARCH |
| R-012 | HIGH / HISTORICAL_ONLY | token totals differ; last 1,536 tokens retained `[VERIFIED_BY_CODE]` | cross-arm loss/input exposure incomparable | no-truncation and token/compute matching / CLAUDE |
| R-013 | CRITICAL / OPEN | state→action ID and domain→operation are 676/676 `[VERIFIED_BY_CODE]` | World-v0 is metadata-solvable | opaque IDs and held-out mappings / CLAUDE |
| R-014 | HIGH / OPEN | one legal action in 676/676; projection removes it only on correct path `[VERIFIED_BY_CODE]` | raw consumers can read gold position | multiple choices + projection assertion / CLAUDE |
| R-015 | HIGH / HISTORICAL_ONLY | V1 option-position invalidation `[VERIFIED_BY_ARTIFACT]` | V1 cannot rank R | retain failure lesson only / NONE |
| R-016 | HIGH / HISTORICAL_ONLY | V3 pooled five ceilings and one floor `[VERIFIED_BY_ARTIFACT]` | founder ranking invalid | mechanism-level gates / NONE |
| R-017 | HIGH / HISTORICAL_ONLY | V4 character guard produced 24 unsent + 6 truncated rows `[VERIFIED_BY_ARTIFACT]` | representation-specific voiding | token-aware guard / NONE |
| R-018 | MEDIUM / HISTORICAL_ONLY | 59/89 V4 malformed rows exhausted output budget while reasoning `[VERIFIED_BY_ARTIFACT]` | format mixed with semantics | separate schema/semantic validity / NONE |
| R-019 | MEDIUM / OPEN | vNext report says 5,680 olean; audited checkout has 38 `[VERIFIED_BY_SOURCE_DATA]` | replay readiness overstated | build/replay preflight / CLAUDE |
| R-020 | HIGH / CONTAINED | shared venv may import main checkout `[VERIFIED_BY_CODE]` | tests may execute wrong code | assert `arena.__file__`, use `PYTHONPATH=$PWD` / CLAUDE |
| R-021 | HIGH / OPEN | Qwen result SHA `e753de98…` is untracked externally `[VERIFIED_BY_ARTIFACT]` | observation remains mutable/unrecoverable | freeze/hash/commit without rerun / CLAUDE |
| R-022 | CRITICAL / CONTAINED | exactly one Qwen mechanism qualifies `[VERIFIED_BY_ARTIFACT]` | founder/R search unauthorized | respect ≥2 gate / CLAUDE |

## Top ten by immediate decision impact

R-004, R-022, R-013, R-003, R-001, R-006, R-005, R-010, R-012 and R-009. Fixed
risks remain in the top ten because regression would silently corrupt attribution.

## Policy

“FIXED” means the observed path is repaired, not that the class of failure can never recur.
“HISTORICAL_ONLY” means do not repair old artifacts or reinterpret them. “CONTAINED” means the
guard exists but the risk still shapes reporting. No threshold or classification may be moved
after seeing results.
