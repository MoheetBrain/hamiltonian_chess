# Route B — Audit of Historical Matched-Learning Data

Source: `artifacts/experiments/tier2_sprint/gpu_sprint_results.json` and `sprint.log`
(commit `bf8838b`). Machine-readable extraction: `artifacts/reports/route-b-loss-curve-audit.json`.
No model was trained for this audit.

## 1. What the historical run recorded

| Field | Value |
|---|---|
| base model / revision | `Qwen/Qwen2.5-7B-Instruct` @ `a09a35458c702b33eeacc393d103063234e8bc28` |
| adaptation | LoRA r=16, α=32, dropout 0, targets q/k/v/o; AdamW 1e-4; batch 4; context 1536; bf16; seed 0 |
| budget mode | EXAMPLE_MATCHED |
| stages | A: 5 arms × 224 examples (56 updates), dev 48; B: 3 arms × 576, dev 48; C: 2 arms × 576, fresh 48 |
| per-arm records | `loss_curve` (one value per update), `final_loss`, `train_tokens`, `exact`, `schema_valid`, `verified`, `per_item_exact` (48 booleans), output tokens, latency |
| seeds | one |
| task split | 580 train / 48 dev / 48 fresh, domain-stratified, disjoint |

Held-out accuracy exists only at 224 (dev) and 576 (dev and fresh) examples. There is no
checkpoint or evaluation at 16, 32, 64 or 128 examples.

## 2. What can be reconstructed

Only the training-batch loss trajectory. Because batch = 4, the loss after update k is the
loss after 4k examples; the table reports the mean of the four updates ending at each budget.

| Arm | 16 | 32 | 64 | 128 | 224 | dev exact @224 | train tokens @224 |
|---|---|---|---|---|---|---|---|
| L3_JSON_AST | 1.966 | 1.359 | 0.583 | 0.084 | 0.0049 | 0.979 | 101,920 |
| L0_STRUCTURED_ENGLISH | 2.081 | 1.386 | 0.617 | 0.084 | 0.0053 | 0.938 | 101,850 |
| L1_CURRENT_HML | 2.084 | 1.397 | 0.654 | 0.088 | 0.0085 | 0.896 | 103,642 |
| L2_SEXPR | 2.203 | 1.416 | 0.632 | 0.093 | 0.0134 | 0.833 | 130,507 |
| L5_COMPACT_SYMBOLIC | 2.301 | 1.531 | 0.722 | 0.102 | 0.0071 | 0.958 | 94,080 |

Loss rank at 16/32/64 examples: JSON < Structured English < HML ≈ S-expression < Compact
Symbolic. Accuracy rank at 224: JSON > Compact Symbolic > Structured English > HML >
S-expression.

## 3. Test of the "signal is strongest before saturation" hypothesis

- **Supported in part.** The loss curves separate most at 16–64 examples (a 0.34 spread at
  16, 0.14 at 64) and collapse to < 0.02 by 128. Whatever representation dependence exists in
  learning is visible early and gone by 224–576, where every arm is ≥ 0.83 and the finalists
  are at 1.000. This matches the directive's prior.
- **Not usable as a ranking.** The early loss order contradicts the only held-out accuracy
  order: Compact Symbolic has the worst loss at every budget yet the second-best accuracy at
  224. Per-token training loss is computed over sequences whose tokenisation differs by
  representation (Compact Symbolic packs more information per token, so its per-token loss
  starts higher), so cross-arm loss comparison confounds representation with token density.
  Loss curves are therefore diagnostic of *when* learning happens, not of *which*
  representation learns better.
- The `per_item_exact` vectors allow paired comparison only at 224 and 576, where the task is
  at or near ceiling; they cannot recover a low-budget learning curve.

## 4. Recommendation

If Fitness V4 cannot obtain valid zero-shot headroom, a **low-budget matched learning-curve
instrument** is scientifically stronger than another zero-shot instrument, for three reasons:
it targets the regime where the only prior representation signal lived; its evaluation metric
is held-out verified accuracy (not loss), removing the tokenisation confound; and it measures
learnability, which `GOAL.md` §14 names as the principal causal object.

Design constraints, to be preregistered before any GPU minute is spent:

- evaluate held-out accuracy at 16, 32, 64, 128 and 224 examples (checkpoint per budget, same
  48-item dev slice, fresh 48-item slice only at the end);
- two seeds minimum; identical base checkpoint reloaded per arm (the runner already does
  this);
- report example-matched and token-matched curves side by side; never pool them;
- use a NEXT_ACTION slice with headroom (the 676-world slice saturates at 576); the V4
  mechanism families, once a non-void mechanism exists, are candidates for that slice;
- budget: five arms × five checkpoints × two seeds ≈ 10 short runs; on an A100 this is
  under two hours and requires explicit authorisation for GPU spend.

The dependency between the two routes is explicit: Route B needs a task family that is not at
ceiling for the *adapted* model, and the V4 frontier levels are the current best candidates
for that family.
