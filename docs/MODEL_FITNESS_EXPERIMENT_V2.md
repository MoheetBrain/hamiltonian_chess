# Model Fitness Experiment V2

> **HISTORICAL DOCUMENT — SUPERSEDED.** This is the Fitness V2 preregistration and result.
> Its "current project sentinel" statement refers to V2 only. The current project sentinel is
> `FITNESS_V4_NOT_QUALIFIED`; see `docs/CURRENT_STATE.md`.

Status at the pre-candidate freeze: **FITNESS_V2_INSTRUMENT_QUALIFIED**.

Experiment ID: `arena-representation-fitness-v2`. Instrument ID:
`arena-semantic-counterfactual-instrument-v2.0.0`. This is a new experiment. Fitness V1,
its cache, reports, and invalid decision are immutable historical evidence.

## Why V2 exists

Fitness V1 was invalidated because gemma3:4b selected A on every Structured English and HML
calibration item. Its apparent accuracy did not show that it read mathematical state. V2 tests
semantic information use before it compares representations. It never interprets a model or
interface failure as evidence against HML, Arena, or representation fitness.

## Counterfactual instrument

Every source is a Gold task from the frozen 676-task Arena World v0. A deterministic domain
transform creates an original state `S` and counterfactual `S'`. The pair retains the same two
semantic options while a decisive operation, binder, role, member, statistic, dimension,
quadratic centre, vector arity, partial-operation boundary, or evidence status changes. The
mathematically correct option flips from index 0 to index 1.

Each family contains six probes:

1. original;
2. counterfactual;
3. relation-destroyed copy carrying the original hidden target;
4. the identical relation-destroyed copy carrying the opposite hidden target;
5. original with option order reversed;
6. counterfactual with option order reversed.

The negative twins are byte-identical after rendering for a fixed candidate and protocol but
have incompatible balanced targets. Their "accuracy" is a diagnostic pseudo-accuracy, not a
mathematical truth claim. A deterministic solver is mechanically capped at 50%. Model-visible
states have a neutral display ID and contain neither legal-action pools nor plausible-invalid
action pools.

The manifest contains 48 source-disjoint pairs and 288 probes. Its hash is
`08ce4d637dc1049d827545922e72c92ae36939d3bdf1a178a13d44ff9974847a`.
Every probe records its source task, source-state hash, transform, transform seed, expected
answer, oracle check, state, and derived hash.

## Validation and truth authority

No LLM labels probes. `arena.experiments.fitness_v2` first runs the Arena native verifier over
every derived state, then a separate bounded domain oracle recomputes each positive answer.
Admission additionally requires exactly one matching semantic option, actual answer inversion,
empty oracle action pools, valid swap identity, identical negative twins, and unique derived
hashes. If any check fails, manifest construction stops.

Native validation establishes structural, scope, type, and definedness integrity. It is not
used alone as a mathematical oracle. The explicit domain replay is the independent truth check.

## Frozen splits and firewall

The V1 group-aware domain/operation partitions remain the upstream firewall. Within each
partition, V2 takes lexicographically first eligible source IDs per mechanism without model
outcomes and never reuses a source across V2 slices.

| V2 slice | Upstream partition | Pairs | Purpose |
|---|---:|---:|---|
| `PROTOCOL_DEV` | DEV | 4 | Response-protocol engineering only |
| `MODEL_QUALIFICATION` | DEV | 8 | Final solver gate |
| `CALIBRATION_DEV` | DEV | 8 | Permanent-control reading/headroom gate |
| `TIER2A_SCOUT` | SCOUT | 6 | Candidate scout |
| `TIER2B_PROMOTION` | PROMOTION | 16 | Fresh promotion |
| `OOD` | OOD | 6 | Held-out structural/domain test |

PROMOTION and OOD results may not redesign candidates, prompts, scorers, or promotion policy.
Historical datasets and scores are excluded.

## Frozen response protocol

Four protocols were compared only on `PROTOCOL_DEV` with gemma3:4b: strict JSON A/B, direct
canonical semantic answer, strict JSON P/Q, and opaque hashed action key. The comparison used
176 calls. JSON A/B was selected because it had 100% Q0 compliance, the highest positive score
(62.5%), the only positive Q1-minus-Q2 gap (+12.5 points), and no malformed output. This choice
did not qualify gemma3 and used no candidate-ranking outcomes.

The frozen prompt asks for exactly `{"choice":"A"}` or `{"choice":"B"}`. The envelope,
question, guide policy, option order, parser, and scorer are common. Only the lossless candidate
state and option renderings vary. Parsing is exact; malformed outputs remain failures.

## Preregistered qualification gate

These thresholds were encoded before the final model ladder calls:

| Check | Threshold |
|---|---:|
| Q0 exact valid response | at least 95% |
| Q1 positive accuracy | at least 70% |
| Q1 over best constant-position baseline | at least 15 percentage points |
| semantic flip consistency | at least 60% |
| Q1 minus relation-destroyed target accuracy | at least 15 percentage points |
| largest position share | at most 85% |

`SEMANTIC_FLIP_CONSISTENCY` counts a pair only when both positive siblings are correct and the
chosen semantic answer changes in the required direction. `CHOICE_FLIP_RATE` ignores
correctness. `POSITION_INVARIANCE` compares the semantic answer before and after option-order
reversal. Position preference is reported separately.

## Frozen model and runtime

The installed-model ladder stopped at the first model that passed every check:

| Model | Q1 | Q2 | Q1-Q2 | Flip consistency | Result |
|---|---:|---:|---:|---:|---|
| gemma3:4b | 43.75% | 50% | -6.25 pp | 0% | fail |
| gemma4:e4b (8B) | 68.75% | 50% | +18.75 pp | 37.5% | fail |
| gemma4:12b | 100% | 50% | +50 pp | 100% | pass |

The selected digest is
`4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`, GGUF Q4_K_M.
Ollama is 0.33.2. Runtime: context 8192, temperature 0, seed 20260905, completion limit 64,
top-k 64, top-p 0.95, and `think=false`. The runtime hash is stored in every new cache
identity.

An initial 8B pilot omitted `think=false`; hidden reasoning exhausted the 64-token output
budget and left an empty visible answer. That result is preserved as
`gemma4_e4b-json_ab-thinking-default-pilot-invalid.json`, excluded, and replaced by the fixed
runtime result. Raw audit of the qualifying run found exact schema-only completions, no leaked
answer text, and identical decisions on each information-identical negative pair.

## Calibration and continuation gates

Fresh calibration evaluates Structured English, current HML, S-expression, and JSON AST on
`CALIBRATION_DEV`. The instrument proceeds only if at least one control passes every
qualification threshold and the control accuracy range is at least 15 points with a minimum
accuracy no higher than 85%. All-controls-at-90%-or-more is a ceiling; no qualifying control is
a floor.

Tier 2A remains the existing 24-candidate roster: all eight seeds plus 16 controlled one-gene
children. It is authorized only by calibration. Before observing SCOUT, the signal rule was
frozen as: at least 95% valid responses for every candidate, at least 15 points of accuracy
range, and at least two parent-child edges with absolute delta of 10 points. Promotion is eight
candidates: four permanent generic controls plus the best four remaining candidates ordered by
flip consistency, positive accuracy, token cost, then stable ID.

Tier 2B uses only fresh PROMOTION probes. A Scout-to-Promotion Spearman correlation of at least
0.60 is required before matched 1K adaptation. Matched adaptation remains unimplemented and
must not run without this gate.

## Actual calibration outcome

The post-freeze calibration made 192 fresh model calls (48 per control). All responses parsed.
The negative-control target score was exactly 50% for every control, as required by the
information-identical construction.

| Control | Q1 | Q1-Q2 | Flip consistency | Position invariance | Qualified |
|---|---:|---:|---:|---:|---|
| Structured English | 87.5% | +37.5 pp | 75% | 75% | yes |
| current HML | 75% | +25 pp | 50% | 75% | no |
| S-expression | 81.25% | +31.25 pp | 62.5% | 81.25% | yes |
| JSON AST | 87.5% | +37.5 pp | 75% | 75% | yes |

This establishes a valid semantic-reading instrument: three permanent controls pass all
qualification checks and every positive arm materially exceeds its destroyed control. It does
not establish representation superiority. The Q1 range is 12.5 points, below the frozen
15-point headroom requirement. The exact verdict is
`FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM`. Consequently Tier 2A, Tier 2B, matched 1K, and
R* were not run. No mutant result or hidden PROMOTION/OOD outcome was observed.

The current project sentinel remains `FITNESS_V2_INSTRUMENT_QUALIFIED`; the immediate blocker is
calibration difficulty, not solver semantic validity. The cheapest next experiment is a
versioned harder DEV-only calibration slice, built and frozen without touching SCOUT,
PROMOTION, or OOD.

## Commands

```bash
.venv/bin/python -m arena.experiments.fitness_v2 materialize --root .
.venv/bin/python -m arena.experiments.fitness_v2 qualify --root . \
  --model gemma4:12b \
  --model-digest 4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c \
  --protocol JSON_AB --slice MODEL_QUALIFICATION
.venv/bin/python -m arena.experiments.fitness_v2 calibrate --root .
.venv/bin/python -m arena.experiments.fitness_v2 tier2a --root .
.venv/bin/python -m arena.experiments.fitness_v2 tier2b --root .
.venv/bin/python -m arena.experiments.fitness_v2 status --root .
```

The authoritative raw artifacts live under `artifacts/experiments/fitness_v2/`. Task-level
model cache entries live under the separate ignored `artifacts/cache/fitness_v2/` namespace.
