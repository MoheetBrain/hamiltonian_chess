# World-v0 Leakage Audit

## Verdict

World-v0 is a sound deterministic fixture but is unsuitable as evidence of mathematical
next-action learning. Zero-model metadata policies recover its labels exactly.

Dataset: 676 trajectories, 13 domains × 52, SHA-256 of JSONL
`1669eced75878af09d27606f6d54fd1cff3615a9b62f0be0b0c379e8631ffd1`.
Reproduction: `research/codex_audit/scripts/world_v0_baselines.py`.

## Exact baselines

| Policy | Accuracy |
|---|---:|
| `state_id -> action_id` rewrite | 676/676 = 1.000 |
| `domain -> operation` lookup | 676/676 = 1.000 |
| one canonical legal action | 676/676 = 1.000 |
| raw first legal action | 676/676 = 1.000 |
| target IDs constant | 676/676 = 1.000 |
| warrant constant | 676/676 = 1.000 |
| expected usefulness constant | 676/676 = 1.000 |
| exactly one transition | 676/676 = 1.000 |
| global-majority operation | 52/676 = 0.076923 |

The exact rewrite is:

`state:<domain-slug>:<seed4>:<index4>:initial`

→ `action:<domain-slug>:<seed4>:<index4>:valid`.

Generator lines 440–475 construct both from the same `prefix`.
`[VERIFIED_BY_CODE] [VERIFIED_BY_ARTIFACT]`

## Domain/operation contingency

Each domain has exactly one operation and 52 rows:

| Domain | Operation |
|---|---|
| algebra | isolate_variable |
| arithmetic | evaluate |
| binding | alpha_rename |
| calculus | differentiate_power |
| linear_algebra | infer_shape |
| logic | modus_ponens |
| optimization | minimize_convex_quadratic |
| partial_operations | evaluate_with_definedness |
| physical_dimensions | infer_dimension |
| probability | expand_conditional_probability |
| reasoning_evidence | replay_verified_derivation |
| sets | check_membership |
| statistics | estimate_sample_mean |

## Projection boundary

The NEXT_ACTION projection removes `legal_actions` in all 676 audited rows. Thus
`unique_legal_action` is not a direct leak **when that projection is used correctly**. It is a
real leak for any consumer that renders raw canonical state or bypasses the projection. The
state/action ID and domain mappings remain concerns wherever those fields survive rendering.

## Scientific consequence

The matched sprint may have learned task-family, ID, and serialization mappings. Good benchmark
performance remains an engineering fact about World-v0, but it is not evidence that a model
performed mathematical reasoning. This does not show the model *only* used shortcuts; it shows
the benchmark cannot rule them out.

## Required replacement properties

- opaque randomized identifiers with no shared prefixes;
- held-out domain-to-operation mappings or operation labels absent from inputs;
- multiple plausible actions whose validity depends on mathematical relations;
- adversarial counterfactuals preserving all metadata while changing the correct action;
- group-disjoint task templates and explicit zero-model leakage gates;
- end-to-end assertion that only the declared projection reaches each renderer.
