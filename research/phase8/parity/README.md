# Phase 8 — representation-parity audit of the precondition ladder

Offline, CPU-only, **zero model calls**. Measures how the eight founder surfaces render the
SAME precondition-conjunction items (`arena.environments.precondition_ladder`, pool `DEV`,
3 families per stratum) through the tournament harness's own envelope
(`arena.experiments.game_r_formal_v1.build_prompt`, `SyntaxGuidePolicy.SHARED_CONSTANT`).

The V7 forensic audit (docs/V7_TOTAL_FORENSIC_AUDIT.md §14–15, E1) killed the Astra arm set
because every arm carried the same ≥40-character spans of source text — "five envelopes around
one string". Here the founder surfaces are genuinely different grammars, so E1 is reported as a
**measurement**, not applied as a gate; an arm pair that shares a large fraction of its bytes is
still a parity concern worth knowing before the tournament runs.

## Files

| path | role |
|---|---|
| `research/phase8/parity/span_audit.py` | the measurement script (this directory) |
| `tests/experiments/test_precondition_parity.py` | the pinned parity contract (< 40 s, part of the suite) |
| `artifacts/reports/precondition_parity_audit.json` | the committed output of the script |

## Exact commands (from the repository root)

```bash
# 1. the pinned contract (P05, P12, P05_M2_D2; all eight founders; base + order-rotated items)
.venv/bin/python -m pytest tests/experiments/test_precondition_parity.py -q

# 2. the measurement (P05/P07/P09/P12/P16/P20, DEV, 3 families, all 28 arm pairs)
.venv/bin/python -m research.phase8.parity.span_audit \
    --workers 12 \
    --out artifacts/reports/precondition_parity_audit.json

# smaller / faster variants
.venv/bin/python -m research.phase8.parity.span_audit --strata P05,P12 --families 1 --workers 4 \
    --seqmatch-cap 5000 --out /tmp/parity-smoke.json
.venv/bin/python -m research.phase8.parity.span_audit --help
```

`research/` is excluded from the repository lint gate by `pyproject.toml`; the script is
nevertheless kept `ruff check` / `ruff format` clean when passed explicitly.

## What is measured

All text is the prompt the Solver would receive. "State text" is the `CURRENT STATE:` block
(between `CURRENT STATE:\n` and `\nOPTIONS:\n`).

Per arm, per stratum:

* `prompt_chars`, `prompt_utf8_bytes`, `state_chars` (min/mean/max over the six items; they are
  identical across items within a stratum for every arm, and the JSON records that);
* `estimated_tokens` — **an estimate**: mean prompt chars divided by an assumed chars-per-token
  ratio per surface class (`json_like` 3.0, `structured_english` 3.4 for `L0`, `compact` 2.3 for
  `L5`). The ratios are the ones the audit brief reports as measured on the live tokenizer; this
  script never tokenises. The class assignment is recorded per arm in `surface_classes` so it
  can be challenged;
* `assumptions_block_start_fraction` / `propositions_block_start_fraction` — offset of the arm's
  quoted `assumptions` / `propositions` role label divided by prompt length (the label occurs
  exactly once per prompt; asserted). `first_holds_token_fraction` is the codec-independent
  cross-check (first `"holds"` after the state marker);
* `twin_difference` — number of character (and UTF-8 byte) positions at which the ORIGINAL and
  COUNTERFACTUAL prompts differ, and the page fraction of the first and last differing
  character. Twins have equal length by construction; the declared bound is
  `(1 + missing_near_misses) × premise_digits`;
* `identifier_tokens` — matches of `[A-Za-z]+:[A-Za-z0-9:]+|p:\d{4,5}` in the state text, as a
  set and a multiset, versus the `L3_JSON_AST` baseline. Tokens that also match inside the arm's
  own fixed role-label table (`role_label_fragments`) are reported verbatim and discounted
  before the multiset comparison; every other disagreement is reported as a divergence.

Per arm pair (all 28), per stratum, on state text:

* `lcs_chars` — exact longest common substring (suffix automaton), min/mean/max over items,
  plus the family-0 ORIGINAL example string (truncated to 200 chars, flagged);
* `e1_coverage_a_in_b` / `e1_coverage_b_in_a` — fraction of one arm's state characters lying
  inside a ≥40-character window that occurs verbatim in the other arm (V7's E1 statistic);
* `seqmatch_ratio` — `difflib.SequenceMatcher(None, a[:30000], b[:30000], autojunk=False).ratio()`
  on the family-0 ORIGINAL item only (the algorithm is quadratic; `seqmatch_cap_applied` says
  whether the 30,000-character cap truncated either text). With `autojunk=True` the ratio is
  meaningless on JSON (popular-character junking), which is why it is disabled;
* `same_grammar_family` (`GrammarFamily` equality from `arena/genome/seeds.py`) and
  `same_encoder_class` (which of the three `_grammar_encode` branches — `json`, `sexpr`,
  `typed_prefix` — the arm uses).

Also recorded: the harness's `assert_arena_parity` verdict for every item and its
`rotate_options(item, 1)` twin under all eight founders, the envelope-signature and
answer-protocol-hash sets, `roster_matrix_P12` (the five Phase-8 arms), and the worst pair per
stratum and overall by each similarity metric.

## Findings

See the end of this file (filled from the committed artifact).
