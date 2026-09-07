# Formal Expression-Depth Shortcut Audit

Reproduction: `research/codex_audit/scripts/formal_depth_shortcuts.py`. The audit rebuilds the
frozen V5 DEV formal-depth positive bank and applies deterministic rules only.

## Reconciled reported numbers

- Deep L3 first-mentioned accuracy is **22/24 = 0.9167**, which explains the reported “≈0.913”.
- Shallow L1 first-mentioned accuracy is **24/24 = 1.000**.
- Across all four levels it is **78/96 = 0.8125**, not ~0.913.

`[VERIFIED_BY_CODE]`

## Rule accuracy by level

| Rule | L0 explicit | L1 shallow | L2 medium | L3 deep |
|---|---:|---:|---:|---:|
| always A / always B | .500 | .500 | .500 | .500 |
| first mentioned in serialized state | .500 | **1.000** | .833 | **.917** |
| target preorder / source traversal | .833 | **1.000** | .833 | **.917** |
| more frequent identifier | .667 | .875 | .667 | .875 |
| last mentioned | .500 | .500 | .500 | .500 |
| identifier lexical order | .500 | .500 | .500 | .500 |
| identifier length | .500 | .500 | .500 | .500 |
| canonical object declaration order | .500 | .500 | .500 | .500 |

Every level is option-balanced 12/12. Option balancing therefore does not remove traversal and
frequency leakage.

## Cause

`build_state` sorts the local-object declarations, so declaration order itself is balanced.
The true deepest identifier, however, tends to occur earlier in the target's preorder and more
often. Canonical serialization exposes the target traversal directly. Relabelling identifiers
does not alter structural occurrence order; swapping displayed options does not alter it either.
The heuristic can answer without computing maximum nesting depth.

## Repair versus retirement

- Identifier obfuscation alone: **insufficient**; it removes semantic/name priors but not order
  or frequency.
- Object/declaration randomization alone: **insufficient**; the target-expression traversal
  remains predictive.
- Option swapping alone: **insufficient**; already balanced.
- Matched counterfactuals: **required but not sufficient**. Construct pairs where the same two
  identifiers exchange depth while marginal frequency, first/last occurrence, target traversal,
  declaration order, token length and option position are jointly balanced.

Disposition: rebuild the family outside the frozen experiment and rerun all zero-model shortcut
gates before model contact. If a sufficiently large real-state bank cannot satisfy the joint
balancing constraints, retire `formal_expression_depth` as a Game-R mechanism. Do not patch the
current Phase 6 protocol.
