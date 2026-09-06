# Fitness V2 calibration

Sentinel: **FITNESS_V2_INSTRUMENT_QUALIFIED**.

The solver/interface demonstrated mathematical semantic reading, but the frozen control-headroom gate did not authorize Tier 2A.

| Control | Q1 | Q2 | Gap | Flip consistency | Position invariance | Malformed | Qualified |
|---|---:|---:|---:|---:|---:|---:|---|
| L0_STRUCTURED_ENGLISH | 0.875 | 0.500 | 0.375 | 0.750 | 0.750 | 0.000 | true |
| L1_CURRENT_HML | 0.750 | 0.500 | 0.250 | 0.500 | 0.750 | 0.000 | false |
| L2_SEXPR | 0.812 | 0.500 | 0.312 | 0.625 | 0.812 | 0.000 | true |
| L3_JSON_AST | 0.875 | 0.500 | 0.375 | 0.750 | 0.750 | 0.000 | true |

Instrument-valid controls: L0_STRUCTURED_ENGLISH, L2_SEXPR, L3_JSON_AST.
Observed Q1 range: 0.125; required: 0.150.
Decision: **FITNESS_V2_CALIBRATION_INSUFFICIENT_HEADROOM**.

Tier 2A: **NOT RUN**. Tier 2B: **NOT RUN**. Matched 1K: **NOT RUN**. R*: **NONE**.

The negative rows use balanced incompatible targets for information-identical prompts. Their 0.500 score is a control diagnostic, not an assertion of mathematical truth.
