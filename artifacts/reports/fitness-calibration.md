# Fitness calibration

Experiment: `arena-representation-fitness-v1`
Model: `gemma3:4b` / `aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25`
Verdict: **INSTRUMENT_INVALID_POSITION_ONLY**

| Rung | Control | Correct | Tasks | Accuracy | Malformed | Mean input tokens |
|---|---|---:|---:|---:|---:|---:|
| CALIBRATION_DEV | L0_STRUCTURED_ENGLISH | 7 | 16 | 0.438 | 0 | 1431.7 |
| CALIBRATION_DEV | L1_CURRENT_HML | 7 | 16 | 0.438 | 0 | 1162.9 |
| CALIBRATION_DEV | L2_SEXPR | 5 | 16 | 0.312 | 0 | 1041.9 |
| CALIBRATION_DEV | L3_JSON_AST | 3 | 16 | 0.188 | 6 | 1699.4 |

Task cells: 64; unique cached model observations: 64; cache hits while rendering this report: 64.

Raw-output inspection sample:

```json
[
  {
    "candidate_id": "L0_STRUCTURED_ENGLISH",
    "correct_choice": "A",
    "parsed_choice": "A",
    "raw_output": "{\"choice\":\"A\"}",
    "task_id": "task:binding:0000:0000"
  },
  {
    "candidate_id": "L0_STRUCTURED_ENGLISH",
    "correct_choice": "A",
    "parsed_choice": "A",
    "raw_output": "{\"choice\":\"A\"}",
    "task_id": "task:optimization:0000:0000"
  },
  {
    "candidate_id": "L0_STRUCTURED_ENGLISH",
    "correct_choice": "B",
    "parsed_choice": "A",
    "raw_output": "{\"choice\":\"A\"}",
    "task_id": "task:sets:0000:0000"
  },
  {
    "candidate_id": "L0_STRUCTURED_ENGLISH",
    "correct_choice": "B",
    "parsed_choice": "A",
    "raw_output": "{\"choice\":\"A\"}",
    "task_id": "task:statistics:0000:0000"
  }
]
```

## Raw-completion instrument audit

Nominal threshold verdict: **USEFUL_HEADROOM**.
Scientific instrument verdict: **INSTRUMENT_INVALID_POSITION_ONLY**.

Always-A accuracy: 0.438; always-B accuracy: 0.562.

| Control | A | B | Malformed | Choice entropy (bits) |
|---|---:|---:|---:|---:|
| L0_STRUCTURED_ENGLISH | 16 | 0 | 0 | 0.000 |
| L1_CURRENT_HML | 16 | 0 | 0 | 0.000 |
| L2_SEXPR | 14 | 2 | 0 | 0.544 |
| L3_JSON_AST | 10 | 0 | 6 | 0.000 |

The strongest controls implemented an always-A policy and no control beat the best constant answer-position policy. The nominal accuracy therefore does not demonstrate that the solver read the mathematical state or alternatives.

Tier 2A was not run. Calibration rows and the nominal heuristic result are preserved; the audit adds an instrument-validity decision without relabelling a model response.
