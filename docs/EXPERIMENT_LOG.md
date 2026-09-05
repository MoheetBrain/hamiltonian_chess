# Experiment Log

## Reconstruction

- Confirmed the target repository had no commits or advertised remote refs.
- Recorded source-repository SHAs, corpus counts, hardware, local models, Lean, and tool state in
  `CURRENT_STATE.md`.
- Observed one HML V3 test failure and one final-signal collection failure; neither was changed.

## Build verification

- Installed the isolated environment with `uv sync --all-extras`.
- Verified all eight candidate surfaces on shared canonical states.
- Verified the 676-task generator balance and quality policy.
- Ran Ruff, mypy, and the 103-test repository suite after integration.
- Built the final world with seed 0 and hash
  `ac16014cd20fbed2dabacd75bff3fd19723e3e96048f82a1ee1a574f59daf256`.
- Ran static match `match:78f6093ba41426a45b4c` over all eight seed languages.

## Assurance smoke

- Semantic properties: 16/16 passed on the frozen base state.
- Canonical expression universe: 2,703/2,703 passed.
- Evidence graph universe: 64/64 passed.
- Differential claims: zero unresolved disagreements across nine supported checker verdicts.
- Required-world roundtrip: 1,352/1,352 states for every seed candidate.

## Interpretation

These are infrastructure and bounded soundness results. No matched model adaptation has run,
so no candidate has earned the R* name. The exact generated tournament values live under
`artifacts/reports/` and in `artifacts/arena.db`.
