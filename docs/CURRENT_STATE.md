# Current State

Recorded: 2026-09-06, Europe/London.

## Repository and evidence chain

- Repository: `/Users/moheet/Documents/ChatGPT/hamiltonian_chess`
- Branch: `codex/arena-v0-fitness`
- Arena v0: `c1dd586db6abb9bd4e72f0048122eb4ddca98739`
- V1 preregistration: `f17bb0f73ac942d43b614704e54c019a64284368`
- V1 runner: `11b73ae6756fa02984b3fecedab117d14ce0a26a`
- V1 invalid stop: `22cab970862ee80cd30ce42b2d885ef52e73b47c`
- V2 instrument freeze: `99c877f22e0c283be56b369af3101019625c215`
- Independent Tier-2 sprint: `bf8838b20e35b1daa9052ab964495397db202506`
- V2 final handoff: `983298279c058ec67a94b564e6d983423f624612`

V1 failed because the solver used option position. V2 fixed that failure and qualified local
Gemma 4 12B, but its frozen control calibration had only 12.5 percentage points of headroom,
below V2's preregistered 15-point rule. No V2 mutants were run and that rule remains intact.

The separate A100/Qwen2.5-7B matched sprint found a penalty for S-expression at Stage A and
saturation of JSON AST and compact symbolic by Stage C. Its `WEAK_CONTINUE` result is useful
historical evidence, not a V3 authorization or an R* result. Its formerly vacuous empty-arm
matching assertion is now fail-closed and regression-tested.

## Phase 3 state

Canonical truth and evolvable model views are separate modules. Track E changes reversible
surface/structure with equal recoverable information. Track C projects only deterministic,
truth-derived relations and emits witness hashes, omissions, redundancy, and byte cost.

Fitness V3 is a new instrument. Its DEV pool contains 12 families / 72 probes across six
mechanisms. The pool hash is
`b26bf3d942ce57951428d2a4ca0c1fd4b62de4e90833e0bcae304d6525ffe4fe`.
The DEV-only selector chose complexity 1 for all mechanisms. On the selected DEV set, the
permanent JSON/typed-AST control achieved:

- format validity 100%;
- positive accuracy 83.33%;
- destroyed-control target accuracy 41.67%;
- semantic flip consistency 83.33%;
- position invariance 83.33%.

All predeclared V3 qualification checks passed. The frozen independent SCOUT manifest has 36
probes and hash `6f1f6c4244d675863402d40536d67270fd8789b050e524bc1fdaa99b6aa09138`.
No founder or evolved candidate had been observed when this manifest was frozen.

## Model and runtime

- model: `gemma4:12b`
- digest: `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c`
- Ollama; context 8192; temperature 0; seed 20260905; `num_predict=64`;
  `top_k=64`; `top_p=0.95`; thinking disabled.

The complexity-2 DEV cases frequently produced long, malformed responses within the frozen
completion budget. This is a measured floor/protocol interaction, not candidate evidence.
