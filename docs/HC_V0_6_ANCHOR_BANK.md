# The HC-V0.6 anchored state bank

**Artefact:** `artifacts/trajectory/hc_v0_6_anchor_bank.json`
**Content hash:** `f13ffee5aae464d6f4717c4f85cd6ec1091eb19d9ca0ab5cd716094a9b583b40`
**Built:** 2026-09-08T23:30:49Z by `arena/trajectory/anchor.py@v0`
**Schema:** `arena-anchored-state-bank-v0`

This is HC-V0.6's evaluation universe. Each entry is a real Lean tactic state, reached by replaying
a prefix of a recorded mathlib proof in a live REPL, at which goals are still open. See
`docs/HC_V0_6_DESIGN_BRIEF.md` §1 for why the unit of observation is a state and not an episode.

Every figure below is read out of the committed artefact, not carried over from an earlier build.
The bank was **rebuilt larger** on 2026-09-08; the previous 223-anchor bank
(`9fa6b6da12e237a3d8b682aad4346f1416bbe14689298a3cfb8bac805e4605dc`) is superseded and no number
from it should be quoted. `docs/HC_V0_6_REPRESENTATIONS.md` still cites the old bank and the old
hash throughout; that file is not edited here and its §3 numbers are stale.

## What is in it

| | |
|---|---|
| anchors | **1,127** |
| distinct theorems | **393** |
| distinct mathlib files | **330** |
| anchors per theorem | 3 for 357 theorems, 2 for 20, 1 for 16 |
| theorems per file | 1 for 279 files, 2 for 43, 3 for 4, 4 for 4 |
| depth class | 393 `INITIAL` (prefix 0) · 734 `MID_PROOF` |
| prefix length | 0:393 · 1:377 · 2:134 · 3:71 · 4:57 · 5:29 · 6:15 · 7:18 · 8:7 · 9:4 · 10:8 · 11:5 · 12:9 |
| open goals at the anchor | 1:975 · 2:129 · 3:17 · 4:5 · 5:1 |
| distinct pretty-prints | 1,127 — **no two anchors are the same state** |
| distinct re-elaboration keys | 1,127 |
| state size | median 12 lines / 240 characters; range 2–101 lines and 23–2,394 characters |

Selection is a pure function of the train JSON, `scan_limit=120000`, `seed=0`, min/max reference
length 3/24, `max_prefix_length=12`, `max_anchors_per_theorem=3`, `theorem_limit=400`,
`allow_multiline_tactics=False`, and tactic policy `record_only:54954a450e6c9c5b`. 118,517 LeanDojo
records were scanned and **400 theorems were selected; 393 of them yielded anchors** — the other 7
never reached the REPL (`SESSION_FAILED_TO_START`, Lean exited during the 180 s startup cap).
Depth is chosen by a fixed rule — depth 0 when open, then evenly spaced quantiles of the remaining
open depths — with no RNG and **no dependence on any Solver outcome**.

Source: the LeanDojo **train** split only
(`/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/leandojo_benchmark_4/random/train.json`).
The four sealed splits were refused before any I/O and were never opened.

Backend: Lean 4.10.0-rc1 (`leanprover/lean4:v4.10.0-rc1`, commit `3b58e064`), mathlib
`29dcec074de168ac2bf835a77ef68bbe069194c5`, 5,681 `.olean`, `maxHeartbeats 1000000`.

## Re-derivability — measured, not assumed

Every anchor was re-derived in a **second, independent Lean process** and its fresh
`KernelStateIdentity.reelaboration_key` compared with the stored one.

**1,127 / 1,127 matched. 393 / 393 theorems. Zero mismatches, zero unreachable, zero errors.**

Mismatches would have been reported, never filtered out of the bank. This is what makes the bank a
re-runnable evaluation universe rather than a snapshot of one process's handles.

Independently re-loading the artefact and recomputing `AnchorBank.content_hash` reproduces
`f13ffee5…` exactly, so the hash above is a check and not a label.

## The oracle firewall

Building an anchor requires reading the recorded proof — that is oracle-side work, `actor=REFERENCE`,
exactly like `ReplayDriver`. Each anchor therefore separates:

* `oracle` — the prefix tactics, the full recorded proof, the declaration span. REFERENCE material.
* `solver_visible` — `goals_pp`, `n_goals`, `backend_kind`, `pp_scope`, `pp_sha256`. The only
  sub-object a prompt may be built from.

Two checks were run outside the builder, both scanning for any reference tactic of the anchor's own
theorem, verbatim, at ≥ 6 characters:

| surface scanned | scope | hits |
|---|---|---|
| serialised `solver_visible` payload | 1,127 anchors | **0** |
| the **rendered payload** of every arm, and the assembled prompt | 1,127 anchors × 4 arms = 4,508 payloads, 22,800 needle comparisons | **0** |

The second is the stronger one and is the surface manual §29 actually names: the bytes the model
reads, after `R_A` / `R_A_PRIME` / `R_B` / `R_ABLATED` have each re-encoded the state. 458
reference-tactic occurrences across the bank fall below the 6-character floor and are not counted in
either figure; that
floor is the known limitation `V05-14` recorded against the leakage guard, unchanged here.
`assert_no_oracle_leak()` ships as a tripwire and fired 0 times over the bank;
`arena/experiments/hc_v0_6_assay.py::assert_prompt_is_oracle_free` re-runs the rendered-payload
check at run time and raises rather than counting.

## Leakage filtering

The existing `LeakageFilter` criteria (`TACTIC_IN_STATE_BEFORE`, `FULL_NAME_IN_STATE`) plus one
conservative extra filter on already-played prefix tactics
(`LEAKS_PREFIX_TACTIC_IN_STATE`). At record level: **191 leaking steps of 204,324 scanned
(`FULL_NAME_IN_STATE` 105, `TACTIC_IN_STATE_BEFORE` 86); 73 problems dropped of 25,911.** The
criterion is unchanged from the audit's baseline (92 of 250,814 steps; 2 of 59,557 proofs), so the
record-level figures are directly comparable. At anchor level — the same criteria applied to the
live state a Solver would see — **0 anchors were discarded for any `LEAKS_*` reason**
(`leakage.anchor_level` is empty in the artefact). The two measurements are different and must not
be pooled.

## Discards

| reason | count |
|---|---|
| `SELECTION_BELOW_MIN_HORIZON` | 92,606 |
| `SELECTION_MULTILINE_TACTIC` | 10,773 |
| `SELECTION_NO_BY_BLOCK` | 1,217 |
| `SELECTION_ABOVE_MAX_HORIZON` | 954 |
| `SELECTION_NOT_THEOREM_OR_LEMMA` | 806 |
| `DEPTH_NOT_SELECTED` | 691 |
| `NO_OPEN_GOALS` | 318 |
| `SELECTION_LEAKAGE_FILTER` | 73 |
| `PREFIX_REJECTED_BY_LEAN` | 64 |
| `SESSION_FAILED_TO_START` | 7 |
| `DUPLICATE_REELABORATION_KEY` | 1 |

None of these is a *rendering* refusal: `arena/trajectory/anchor.py` never calls `is_renderable` or
`refusal_reason`, so the 0 % refusal rate measured in the next section is a measurement rather than
a tautology. `DUPLICATE_REELABORATION_KEY` is why the bank contains 1,127 anchors and 1,127
distinct pretty-prints: one anchor that would have duplicated an existing state was dropped.
1,744 prefix steps were accepted and 64 rejected during derivation.

## Cost

| | |
|---|---|
| selection | 7.5 s |
| derivation | 1,025.9 s (**0.91 s / anchor**, 2.56 s / theorem) |
| re-derivation check | 909.7 s |
| total | 1,943.1 s (32.4 min) |

Lean is not the bottleneck. Session startup averaged 2.48 s (max 18.6 s). One session per theorem
serves every anchor in it, and every arm can then branch from the same live `state_id` — so the
assay's Lean cost is roughly one session per theorem, not one per cell.

## Verified on this bank

Run as `research/phase10/bank_audit/audit_bank.py` and `research/phase10/bank_audit/branch_check.py`;
raw output in `research/phase10/bank_audit/out/`. Measured 2026-09-09, 0.4 s + 64.0 s.

**Bijection — `invert(R.render(s)) == R_A.render(s)`, all 1,127 anchors.**

| arm | checked | round-trips | failures | refusals |
|---|---|---|---|---|
| `R_A` | 1,127 | **1,127** | 0 | 0 |
| `R_A_PRIME` | 1,127 | **1,127** | 0 | 0 |
| `R_B` | 1,127 | **1,127** | 0 | 0 |
| `R_ABLATED` | 1,127 | 0 | 1,127 | 0 |

There are **no failing `pp` shapes and no refusals to report**: every anchor round-trips
byte-for-byte through both `R_ONLY` arms, including the multi-goal states (129 with 2 goals, 17 with
3, 5 with 4, 1 with 5), the 101-line state and the 2,394-character state. `R_ABLATED` fails at every
anchor with the same single reason, `GoalWithheldRenderer does not implement invert()`; it is not a
bijection and the checker refuses to bless it rather than skipping it.

**All four arms can render all 1,127 anchors**, so the usable intersection is **1,127 / 1,127 =
100 % — 393 / 393 theorems, 330 / 330 files.** The renderers impose no sample-size cost; `n` is set
by the bank builder's selection rules and the power analysis.

**Parity, and the negative control.**

| pair | declared under | parity holds | bytes differ | admissible | derived class |
|---|---|---|---|---|---|
| `R_A` vs `R_A_PRIME` | `R_ONLY` | **1,127 / 1,127** | 1,127 / 1,127 | 1,127 / 1,127 | `R_ONLY` |
| `R_A` vs `R_B` | `R_ONLY` | **1,127 / 1,127** | 1,127 / 1,127 | 1,127 / 1,127 | `R_ONLY` |
| `R_A` vs `R_ABLATED` | `R_ONLY` | **0 / 1,127** | 1,127 / 1,127 | 0 / 1,127 | `P_CHANGE` |
| `R_A` vs `R_ABLATED` | `P_CHANGE` | not required | 1,127 / 1,127 | 1,127 / 1,127 | `P_CHANGE` |

The negative control passes: `R_ABLATED` **fails** `R_ONLY` parity at 1,127 / 1,127 anchors, and the
explanation names `GOAL_TEXT` as the differing slot at every one of them. Declared under its own
class the same difference is admissible, because for `P_CHANGE` a projection difference is the
intervention rather than a fault (manual §26.3). The intervention class is *derived* from the
declarations at every anchor, never asserted.

**Branching, re-confirmed through the API the assay drives.** 18 theorems drawn deterministically
(seed 20260909) from the theorems that carry both an initial and a mid-proof anchor, opened with
`arena.trajectory.anchor.open_anchor_session`, and branched with `LiveAnchorSet.step`:

| property | result |
|---|---|
| theorems opened | 18 / 18, no errors |
| anchored states branched | 36 (18 `INITIAL`, 18 `MID_PROOF` at prefix 2–12) |
| re-derived state matched the stored key | 36 / 36 |
| two successful steps from one anchored state | 36 / 36 |
| the two children are **distinct** state ids | 36 / 36 |
| the parent's state text is unchanged afterwards | 36 / 36 |
| the first child's text is unchanged after the second branch | 36 / 36 |
| a third branch on the anchor's own next recorded tactic succeeded | **35 / 36** |

The one failure is not a branching failure: at a prefix-8 anchor in
`Mathlib/LinearAlgebra/QuadraticForm/Prod.lean::QuadraticForm.posDef_pi_iff` the theorem's *next
recorded tactic* no longer type-checks after flat replay, while both neutral branches from that same
state succeeded and the parent survived. It is a direct instance of limitation 3 below, and it means
**no "the gold move is accepted here" baseline may be assumed to exist at every anchor.** Nothing in
the assay scores the recorded tactic — `remaining_reference` is read only by the leakage guard — so
this does not affect the endpoint.

**Rendered size per arm — a declared confound, over all 1,127 anchors.** `goals_pp` is the only key
the Solver reads (`arena/trajectory/solver.py::OBSERVED_FIELD`); the prompt column is the frozen
template with that text substituted in, which is what the model actually consumes.

| arm | median `goals_pp` chars | range | median % vs `R_A` | median prompt chars | median prompt % vs `R_A` |
|---|---|---|---|---|---|
| `R_A` | 240 | 23–2,394 | — | 377 | — |
| `R_A_PRIME` | 253 | 26–2,473 | **+5.5 %** | 390 | +3.4 % |
| `R_B` | 327 | 65–2,816 | **+36.4 %** (range +13.4 % … +182.6 %) | 464 | +23.0 % |
| `R_ABLATED` | 53 | 53–53 | −77.9 % | 190 | −49.6 % |

`R_B`'s +36.4 % median confirms the ~+37 % measured on the old bank. Over the whole bank the totals
are +33.3 % (`R_B`) and +5.2 % (`R_A_PRIME`) more characters than `R_A`. The arms therefore do
**not** consume equal prompt tokens, and per-call `prompt_eval_count` must be recorded and reported
per arm (manual §26.5); no local tokenizer exists to pre-count. `R_ABLATED`'s range reaches
+130.4 % because its fixed 53-character marker is longer than the shortest real state.

## Five honest limitations

**1. The independent unit is the theorem — arguably the file — not the anchor.** 1,127 anchors sit
in 393 theorems in 330 files, and 357 of the 393 theorems contribute three anchors each. Clustered
inference therefore has an effective sample size near **393** (theorems), and nearer **330** if
same-file theorems are treated as correlated — not 1,127. Extra anchors per theorem buy precision
within a theorem and almost nothing across theorems. Every power and MDE statement must use the
cluster count. The rebuild raised the cluster count from 78 theorems / 75 files to 393 / 330, which
is the whole point of it; it did not make the anchor a valid unit.

**2. The depth distribution is shallow.** 770 of 1,127 anchors (68 %) sit at prefix length 0 or 1.
Anchors at depth ≥ 2 number 357, and the tail now reaches prefix 12 (9 anchors). The bank is still
a bank of *early* proof states, with a longer tail than the 223-anchor build had.

**3. Mid-proof anchors are selected on flat-replay chaining.** A recorded LeanDojo proof is a
traversal of a proof *tree*; replaying it as a flat script does not always chain (64 anchors were
lost to `PREFIX_REJECTED_BY_LEAN`, and the branching check above found one surviving prefix-8 anchor
at which the next recorded tactic no longer applies). Deep anchors therefore over-represent proofs
whose prefixes happen to chain flatly. This is a selection effect on the *states*, not on any
outcome, so it does not bias the paired comparison — but it does limit what the bank is a sample
*of*, and it forbids assuming a reference-move baseline at an arbitrary anchor.

**4. Prefix length is a sampling proxy and nothing else.** `MinimalProofLength` is `UNKNOWN` and
nothing in this arena could establish it — a shorter proof may always exist. `DependencyDepth` is
`UNKNOWN` for this backend. `EpisodeLength` is 0 at an anchor because an anchor is a state, not an
episode. `KernelStepCount` is not measured at derivation time. Reporting prefix length as reasoning
difficulty would be exactly the granularity substitution the manual's §6.30–6.34 and §17.6 exist to
prevent.

**5. Equal information does not mean equal prompt length.** The bijection and the parity check
establish that `R_A`, `R_A_PRIME` and `R_B` carry the same information; the size table above shows
they do not carry it in the same number of characters. That asymmetry is inside the measured
`Δ(R_A,R_B)` and this design cannot remove it — see `docs/HC_V0_6_REPRESENTATIONS.md` §5.

## Contamination

mathlib4 is `HISTORICALLY_EXPOSED` and exposure is transitive. No LeanDojo split establishes
pretraining-cleanliness. Nothing measured on this bank separates a solved goal from a recalled one;
the defensible phrasing stays **execution under kernel verification**.

## Reproduce

```bash
# rebuild the bank (32 min of Lean)
.venv/bin/python -m arena.trajectory.anchor

# re-run the verification above (0.4 s, no Lean)
.venv/bin/python -m research.phase10.bank_audit.audit_bank

# re-run the branching re-confirmation (64 s, 18 Lean sessions)
.venv/bin/python -m research.phase10.bank_audit.branch_check --theorems 18
```
