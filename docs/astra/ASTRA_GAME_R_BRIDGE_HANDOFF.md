# Astra Game-R bridge handoff

Status: `CANONICAL_GAME_R_BRIDGE_PARTIAL` pending a future Lean-native semantic adapter and clean promotion partition.

The isolated branch `astra/canonical-game-r-bridge` is based on clean shared ancestor `9f28c0c1b673804648052a54a65cf32eee875b05`. Claude’s active branch was inspected read-only at committed `d026379c08e7da66e374fe01e55c82e4ae9f0d6c`; its V7 process was active during this work. No V7 process, Ollama call, GPU job, founder tournament, mutant tournament, Solver result, frozen artifact, `GOAL.md` or production canonical file was changed.

The primary bridge is premise selection. Each accepted item preserves a real Lean proof context and focused goal, six candidates with complete admitted theorem/lemma source headers, the recorded citation target and provenance. Renderers receive only the allowlisted projection. Candidate ordering is shared by seed and semantic premise ID. The target is never visible.

Coverage is 300 real `random/train.json` development items, one per theorem group, split 240/60 by theorem group. The source adapter scanned 5,000 theorems and admitted 300 after single-citation, single-goal, source-header, scope and distractor checks. No item was fabricated. The held-out `novel_premises` and `random` val/test files were byte-hashed without parsing, but repository measurements show all four have historically been exposed; none is certified hidden.

Supported representations are five scoped codecs: structured English, JSON AST, S-expression, HML-compatible assignment lines and compact symbolic aliases. All five decode to the same ordered visible inventory; the parity artifact reports 1,500 deterministic renderings and 300/300 private-field noninterference checks. Option permutations (1,800 checks) preserve semantic answer identity. The restricted alpha-renaming and independent-context transformations are unsupported for all admitted real rows because the observed contexts do not meet the deliberately narrow binder-free arithmetic fragment; the tests fail closed rather than inventing scope semantics.

Shortcut audit on the 60-item development holdout found chance `0.1667`; strongest visible heuristic was lexical goal/name overlap `0.4167`, followed by token overlap `0.4000`. This is a diagnostic floor, not a future qualification ceiling. The bank’s same-proof and same-module distractor counts are 750 each.

The central gap is semantic: the source adapter carries exact source headers and pretty-printed state, not elaborated Lean terms or kernel replay. Existing Arena founders cannot express the object without losing formal information. The bridge is therefore representation-neutral at the source-projection layer and does not yet support claims about representation effects on mathematical semantics.

See `docs/astra/CLAUDE_INTEGRATION_PLAN.md` for cherry-pick scope and exact next commands. Artifacts and tests are under `research/astra/`.
