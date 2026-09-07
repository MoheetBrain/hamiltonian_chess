# Premise bridge semantic firewall

The firewall is an allowlist. A renderer receives `visible_projection(state)` and cannot access the canonical target, trace annotation or private sampler fields.

| Canonical field | Visible? | Reason | Derived? | Same across representations? | Answer-leak risk |
|---|---:|---|---:|---:|---|
| `task_id` | no | identity is not mathematical input | yes | n/a | high if exposed as a lookup key |
| `provenance` | no | repository/theorem/source positions are audit data | no | n/a | high through theorem or module recall |
| `formal_system` | yes | identifies Lean 4 syntax context | no | yes | low alone |
| `context.text` | yes | observed local proof context | no | yes | medium; raw identifiers can correlate with answers |
| `goal.text` | yes | observed focused goal | no | yes | medium; lexical overlap is measured |
| candidate `name` | yes | candidate premise identity is the task input | no | yes | medium; frequency and name heuristics are measured |
| candidate `statement.text` | yes | source-supported declaration header | no | yes | medium; statements can overlap goal |
| candidate `premise_id` | no; neutral option labels replace it | private stable identity must not become a lookup feature | yes | option mapping is shared | high if hash/ID leaks target or corpus order |
| candidate source path/order | no | provenance and declaration-order shortcuts | no | n/a | high |
| candidate tier/frequency | no | sampler diagnostics only | yes | n/a | high |
| `target_choice_id` | no | answer oracle | no | n/a | direct answer leak |
| `oracle_evidence` | no | tactic/annotation/successor hashes certify provenance only | no | n/a | direct/indirect answer leak |
| `source_raw_state` | no | exact audit copy; context+goal already form visible P | no | n/a | duplicate channel and accidental trace leak |
| `audit_metadata` | no | split, sampler and private feature controls | no | n/a | direct shortcut channel |
| question text | yes | common response contract | fixed | yes | low; must be byte-equivalent in meaning |
| option order/labels | yes | candidate identity mapping | deterministically derived from shared seed | yes | position is controlled, not a semantic clue |

The firewall treats raw Lean pretty text as a typed backend-native carrier with an explicit `source-header-not-elaborated` assurance. It is retained because inventing an AST would lose or falsify dependent types, binders, implicit arguments, universes, notation and ambient section context. A future Lean-native adapter may upgrade these fields only after a separately verified parser/elaborator contract.

The parity check decodes each renderer and compares the complete ordered allowlisted inventory, including multiplicity, candidate statement text and option labels. A changed field is `GAME_R_PARITY_FAIL`, not a syntax difference. The target, oracle evidence and audit metadata are tested for renderer noninterference.
