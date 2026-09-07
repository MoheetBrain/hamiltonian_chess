| cell | solver | V7 best shortcut | A2 best CHEAP surface rule | A2 cheap | A2 best COUNTING rule | A2 count | V7 margin | A2 cheap margin |
|---|---|---|---|---|---|---|---|---|
| `formal_expression_depth|L0` | 1.000 | 0.667 (`more_frequent_in_state`) | `ast_latest_preorder` | 0.917 | `view_deepest_bracket_nesting` | 1.000 | +0.333 | +0.083 |
| `formal_expression_depth|L1` | 0.833 | 1.000 (`first_mentioned_in_state`) | `first_mentioned_in_state*` | 1.000 | `view_deepest_bracket_nesting` | 1.000 | -0.167 | -0.167 |
| `formal_expression_depth|L2` | 0.792 | 0.833 (`first_mentioned_in_state`) | `last_mentioned_in_view` | 0.917 | `view_deepest_bracket_nesting` | 1.000 | -0.042 | -0.125 |
| `formal_expression_depth|L3` | 0.625 | 0.917 (`first_mentioned_in_state`) | `first_mentioned_in_state*` | 0.917 | `view_deepest_bracket_nesting` | 1.000 | -0.292 | -0.292 |
| `precondition_conjunction|L0` | 1.000 | 1.000 (`first_mentioned_in_state`) | `first_mentioned_in_state*` | 1.000 | `view_greater_mean_bracket_nesting` | 1.000 | +0.000 | +0.000 |
| `precondition_conjunction|L1` | 0.958 | 0.500 (`always_first_option`) | `first_mentioned_in_state*` | 0.500 | `view_deepest_bracket_nesting` | 0.500 | +0.458 | +0.458 |
| `precondition_conjunction|L2` | 1.000 | 0.500 (`always_first_option`) | `first_mentioned_in_state*` | 0.500 | `view_deepest_bracket_nesting` | 0.500 | +0.500 | +0.500 |
| `precondition_conjunction|L3` | 1.000 | 0.500 (`always_first_option`) | `first_mentioned_in_state*` | 0.500 | `view_deepest_bracket_nesting` | 0.500 | +0.500 | +0.500 |
| `transitive_dependency|L0` | 0.958 | 1.000 (`first_mentioned_in_state`) | `first_mentioned_in_state*` | 1.000 | `view_deepest_bracket_nesting` | 1.000 | -0.042 | -0.042 |
| `transitive_dependency|L1` | 1.000 | 0.833 (`more_frequent_in_state`) | `more_frequent_in_state*` | 0.833 | `view_deepest_bracket_nesting` | 0.500 | +0.167 | +0.167 |
| `transitive_dependency|L2` | 0.958 | 0.625 (`more_frequent_in_state`) | `dep_earlier_in_evidence_list` | 0.750 | `view_deepest_bracket_nesting` | 0.500 | +0.333 | +0.208 |
| `transitive_dependency|L3` | 0.750 | 0.667 (`first_mentioned_in_state`) | `first_mentioned_in_state*` | 0.667 | `view_deepest_bracket_nesting` | 0.500 | +0.083 | +0.083 |
