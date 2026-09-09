# HC-V0.6 — the four arms, the bijection contract, and what it licenses

> **Superseded numbers, 2026-09-09.** Every measurement in this file was taken against the FIRST
> anchor bank (223 anchors, hash `9fa6b6da…`). That bank was replaced by the frozen one —
> **1,127 anchors · 393 theorems · 330 files**, hash `f13ffee5…`. The contracts and arguments here
> still hold; the counts do not. The authoritative re-measurements on the frozen bank are in
> `docs/HC_V0_6_ANCHOR_BANK.md` (bijection 1127/1127 for `R_A_PRIME` and `R_B`, 0 refusals, parity
> 1127/1127, `R_ABLATED` fails `R_ONLY` parity 1127/1127, 0 leakage hits on rendered bytes,
> `R_B` +36.4% median goal text and +23.0% median prompt characters). §6's `R_A_PRIME` naming
> conflict is **resolved**: `Arm.R_A_PRIME.renderer_id` is now its own id
> (`hc-v0.6-R_A_PRIME-whitespace-v1`), the arm is the whitespace-perturbing renderer, and the
> comparison family is the four of `docs/HC_V0_6_SPEC.md` §11.

**Status: MECHANISM + MEASUREMENT. Not a result.** No Solver has been run against these arms.
Every number below is a property of the *renderers* measured against the committed anchored bank;
nothing here is an acceptance rate, a Δ, or evidence about any model.

* mechanism — `arena/trajectory/representation.py`
* tests — `tests/trajectory/test_representation.py`
* specification — `docs/HC_V0_6_DESIGN_BRIEF.md` §2, §4, §9.4
* governing authority — `spec/SOURCE/HAMILTONIAN_CHESS_ATOMIC_SPECIFICATION_MANUAL_v0.2.md`
* bank under test — `artifacts/trajectory/hc_v0_6_anchor_bank.json`,
  content hash `9fa6b6da12e237a3d8b682aad4346f1416bbe14689298a3cfb8bac805e4605dc`,
  **223 anchors across 78 theorems in 75 mathlib files**

---

## 1. The four arms

| arm | class | what the Solver sees | inverse |
|---|---|---|---|
| `R_A` | `R_ONLY` baseline | Lean's native pretty-printed tactic state, byte-identical to `arena_v0.BackendNativeRenderer` (same `renderer_id`, `backend-native-v0`) | identity |
| `R_A_PRIME` | `R_ONLY` **null** | the identical characters under a different whitespace convention: one extra space after the turnstile, one trailing space on every line | `unperturb_whitespace` |
| `R_B` | `R_ONLY` variant | the same characters re-laid out: `[GOAL i OF n]`, `[CASE] t`, `[HYPOTHESES k]`, numbered hypotheses, the target under `[TARGET]` | `unlayout` |
| `R_ABLATED` | **`P_CHANGE`** | goal *text* withheld; goal count and backend metadata retained | **none — by construction** |

`R_A` reuses the baseline `renderer_id` deliberately, so HC-V0.5's numbers stay comparable and
the equivalence can be tested as complete-mapping equality rather than "equal apart from the id".

### The same real anchor through all four arms

`Real.log_zpow`, after `induction n`, two open goals (`R_A_PRIME` shown with `·` marking each
appended trailing space, which is otherwise invisible):

```
--- R_A (166 chars) -------------------------------------------------------------
case ofNat
x✝ y x : ℝ
a✝ : ℕ
⊢ log (x ^ Int.ofNat a✝) = ↑(Int.ofNat a✝) * log x

case negSucc
x✝ y x : ℝ
a✝ : ℕ
⊢ log (x ^ Int.negSucc a✝) = ↑(Int.negSucc a✝) * log x

--- R_A_PRIME (177 chars) -------------------------------------------------------
case ofNat·
x✝ y x : ℝ·
a✝ : ℕ·
⊢  log (x ^ Int.ofNat a✝) = ↑(Int.ofNat a✝) * log x·
·
case negSucc·
x✝ y x : ℝ·
a✝ : ℕ·
⊢  log (x ^ Int.negSucc a✝) = ↑(Int.negSucc a✝) * log x·

--- R_B (262 chars) -------------------------------------------------------------
[GOAL 1 OF 2]
[CASE] ofNat
[HYPOTHESES 2]
(1) x✝ y x : ℝ
(2) a✝ : ℕ
[TARGET]
⊢ log (x ^ Int.ofNat a✝) = ↑(Int.ofNat a✝) * log x

[GOAL 2 OF 2]
[CASE] negSucc
[HYPOTHESES 2]
(1) x✝ y x : ℝ
(2) a✝ : ℕ
[TARGET]
⊢ log (x ^ Int.negSucc a✝) = ↑(Int.negSucc a✝) * log x

--- R_ABLATED (53 chars) --------------------------------------------------------
[GOAL TEXT WITHHELD BY R_ABLATED]
[GOALS REMAINING 2]
```

Note what `R_A_PRIME` does to the goal separator: a blank line is a line, so Lean's `"\n\n"`
becomes `"\n \n"`. Visually and mathematically that is still nothing; to a BPE tokenizer it is
not, because `"\n\n"` is frequently one token and `"\n \n"` is not. That is the control working,
not the control leaking.

### Why `R_A_PRIME` exists (design brief §9.4)

`R_ABLATED` is an enormous intervention — the goal text is simply gone. Detecting it proves the
rendering pipeline is causally connected to the outcome **at all**; it says nothing about
sensitivity at the scale a representation change plausibly operates. `R_A_PRIME` supplies the
missing rung between control `C1` (byte-identical) and `R_B` (restructured):

* `Δ(R_A, R_A′) ≈ 0` while `Δ(R_A, R_B) ≠ 0` → the effect belongs to the **structure** of the
  rendering, not to the bare fact that the bytes (and hence the token sequence) changed;
* **both** move → the Solver is sensitive to byte perturbation as such, and `R_B`'s effect
  cannot be attributed to its structure. That is a finding about the assay, and it **blocks**
  the representation claim.

The asymmetry is the point. `R_A_PRIME` can only ever subtract from what a positive
`Δ(R_A,R_B)` licenses. It is a control that can embarrass the result, never one that can
manufacture it.

### `R_ABLATED` is not a representation

It is control `C2` of design brief §4, the sensitivity floor. Reporting it beside `Δ(R_A,R_B)`
as if it were a representation effect is exactly the confusion manual §26.3 forbids. Its class is
**derived**, not written down: `derive_intervention_class` compares declared slot sets, finds
`GOAL_TEXT` withheld, and returns `P_CHANGE` from the declaration alone. The arm carries no
`intervention_class` attribute for anyone to set.

---

## 2. The bijection contract, and why declaration alone is not enough

`arena/trajectory/state_identity.py` lets a renderer **declare** which `InformationSlot` values it
exposes, and `check_projection_parity` compares those declarations. HC-V0.5's red team found the
hole and reproduced it:

> **V05-15** (`docs/HC_V0_5_REDTEAM.md`, CONFIRMED, reproduced by
> `research/phase9/redteam_v05/attack_seal_and_leakage.py` → `S12`) — *"a renderer implementing
> `declare_information` is believed: it can render an extra key and still pass
> `check_projection_parity` as `R_ONLY`."* A renderer that emits `coach_note` and declares only
> `{GOAL_TEXT, GOAL_COUNT}` obtains a `projection_hash` equal to an honest renderer's and the
> parity check returns `parity_holds=true, admissible=true`.

> **V05-14** (same file, CONFIRMED, `S6`/`S7`) — the leakage guard has a 6-byte floor and never
> registers `full_name`, `file_path` or `pp_scope`, all of which reach `goals_pp` and therefore
> the prompt. On the live path it did not fire (5 tasks, 14 reference tactics, 0 verbatim leaks),
> but the hole is real.

The red team's own summary states the incentive inversion precisely: the *undeclared* path is
safe, because `from_rendered` conservatively folds every unknown key into an
`UNDECLARED:` slot — and the *declared* path is not, because the declaration is its only
evidence. Nothing inside the declaration machinery can catch a renderer that declares less than
it shows, and V05-14/15 are listed among the defects reachable "the moment a genome supplies its
own `StateRenderer`" — which is exactly what HC-V0.6 does.

HC-V0.6 therefore adds a contract a renderer **cannot lie about**:

> Every `R_ONLY` renderer MUST be a bijective re-encoding of the baseline rendering:
> it ships `render` *and* `invert`, and `invert(R.render(s)) == R_A.render(s)` holds
> byte-for-byte at every state in the bank.

A bijection cannot add information — there is nothing to add it from — and cannot remove
information, or it could not be inverted. The declaration stops being an unverifiable claim: the
bijection is the evidence that the rendering carries exactly the declared bytes and no more. A
`coach_note` in the output is either recoverable from the baseline (in which case it is not extra
information) or it makes `invert` fail.

Three structural properties keep this checkable rather than hoped for.

**Declaration-derived rendering.** `DeclarationDerivedRenderer.render` is fixed as
`self.present(self.declare_information(envelope))`, and `__init_subclass__` raises `TypeError` if
a subclass overrides `render`. `present` never receives the envelope, so a renderer physically
cannot show something it did not declare. `test_a_renderer_that_overrides_render_cannot_be_defined`
asserts the class definition itself fails.

**Never mangle silently.** `parse_tactic_state` refuses to return a parse that does not reproduce
its input; `EnumeratedWorkspaceRenderer.present` re-inverts its own output before returning it. A
shape this module cannot handle raises `UnrenderableStateError` with a named `RefusalReason`. A
Hypothesis property test over arbitrary text asserts there is no third outcome: round-trip, or a
named refusal.

**No hidden copy.** `R_B`'s rendering contains neither the baseline text nor its digest
(`test_r_b_carries_no_hidden_copy_of_the_baseline_bytes`), so `invert` genuinely re-derives the
bytes rather than replaying a stash. `R_A_PRIME` is *deliberately* a near-copy of the baseline
text, so the substring form of that test is meaningless for it and is not asserted; what is
asserted for both arms is that no baseline **digest** is carried
(`test_no_r_only_arm_carries_the_baseline_digest`).

### What the contract still does not cover

* It is a statement about **information**, not about **effort**. Two renderings can carry the
  same information and be very differently easy to read. That is the effect the experiment is
  trying to measure, and the contract is what makes the comparison admissible, not what
  interprets it.
* It binds the four arms in this module. It does not bind a future evolved genome's renderer
  unless that renderer is required to ship an inverse — it should be.
* A bijection with a *pathological* inverse (one that reconstructs the baseline from a
  deliberately obfuscated encoding) would pass. Nothing here forbids a bad representation; it
  forbids an information-changing one.

---

## 3. Measured against the real anchored bank

Bank: `artifacts/trajectory/hc_v0_6_anchor_bank.json`, 223 anchors, 78 theorems, 75 files,
223 distinct pretty-prints (no duplicate states), median 11 lines / 218 characters, range 2–54
lines and 33–2039 characters. Every state is real Lean 4 `pp` text from
`leanprover/lean4:v4.10.0-rc1` against mathlib `29dcec074de168ac2bf835a77ef68bbe069194c5`.

### Round-trip: `invert(R.render(s)) == R_A.render(s)`

| arm | n | checked | round-trips | failures | refusals | rate |
|---|---|---|---|---|---|---|
| `R_A` | 223 | 223 | 223 | 0 | 0 | **100.0 %** |
| `R_A_PRIME` | 223 | 223 | 223 | 0 | 0 | **100.0 %** |
| `R_B` | 223 | 223 | 223 | 0 | 0 | **100.0 %** |
| `R_ABLATED` | 223 | — | 0 | 223 | — | **0 %, as designed** |

`R_ABLATED` fails the check with `GoalWithheldRenderer does not implement invert()`. It is not a
bijection and `isinstance(R_ABLATED, BijectiveRenderer)` is `False` as a structural fact, not as a
comment. The checker refuses to bless it rather than skipping it.

**There are no failing `pp` shapes to report.** Every one of the 223 anchors round-trips
byte-for-byte, including the multi-goal states (21 with 2 goals, 1 with 4), the line-wrapped
hypotheses, and the 2039-character state.

### Refusals

| arm | refuses | why |
|---|---|---|
| `R_A` | 0 / 223 | total: it shows the backend's own text |
| `R_A_PRIME` | 0 / 223 | total by construction: the perturbation is a bijection on all of `str` |
| `R_B` | **0 / 223** | no anchor's pretty-print defeated the decomposition |
| `R_ABLATED` | 0 / 223 | it shows only a count |

**Usable by all four arms: 223 / 223 = 100.00 % of the bank** — 78 / 78 theorems, 75 / 75
clusters survive. The renderers impose **no** sample-size cost on the experiment; `n` is set by
the bank builder's selection rules and the power analysis, not by this module.

Two honesty notes on that number.

1. **It is not a filtering artefact.** `arena/trajectory/anchor.py` never calls `is_renderable`
   or `refusal_reason`; the bank's own `discards` are all selection-side
   (`SELECTION_BELOW_MIN_HORIZON` 31210, `SELECTION_MULTILINE_TACTIC` 3646,
   `SELECTION_ABOVE_MAX_HORIZON` 328, `SELECTION_NO_BY_BLOCK` 387,
   `SELECTION_NOT_THEOREM_OR_LEMMA` 286, `DEPTH_NOT_SELECTED` 99, `NO_OPEN_GOALS` 62,
   `SELECTION_LEAKAGE_FILTER` 29, `PREFIX_REJECTED_BY_LEAN` 16, `SESSION_FAILED_TO_START` 2).
   None is a rendering refusal. The 0 % refusal rate is a measurement, not a tautology.
2. **The refusal machinery is not dead code.** On the other committed real corpus
   (`artifacts/trajectory/hc_v0_5_smoke.json`, 41 distinct states) `R_B` refuses 2: one `EMPTY_PP`
   and one `NO_GOAL_MARKER`. Both are degenerate non-anchor states — a closed proof has no open
   goal to render — so refusing them is correct. The adversarial suite additionally exercises
   every named `RefusalReason` against synthetic shapes (CRLF multi-goal, trailing newline,
   orphan continuation, goal-count mismatch), and a Hypothesis property test over 600 arbitrary
   strings asserts that the only two outcomes are an exact round-trip or a named refusal.

### Parity, and the negative control

Over all 223 usable anchors:

| pair | declared under | parity holds | bytes differ | admissible | derived class |
|---|---|---|---|---|---|
| `R_A` vs `R_A_PRIME` | `R_ONLY` | **223 / 223** | 223 / 223 | 223 / 223 | `R_ONLY` |
| `R_A` vs `R_B` | `R_ONLY` | **223 / 223** | 223 / 223 | 223 / 223 | `R_ONLY` |
| `R_A` vs `R_ABLATED` | `R_ONLY` | **0 / 223** | — | 0 / 223 | `P_CHANGE` (`withheld=('GOAL_TEXT',)`) |
| `R_A` vs `R_ABLATED` | `P_CHANGE` | not required | — | 223 / 223 | `P_CHANGE` |

**The negative control passes: `R_ABLATED` FAILS `R_ONLY` parity at 223 / 223 anchors**, and the
failure names `GOAL_TEXT` in its explanation at every one of them. This is load-bearing. A parity
check that cannot fail proves nothing about the two rows above it; the positive results are only
worth reading because the same machinery, run on an arm that really does withhold information,
rejects it everywhere. The last row is the other half of the discipline: declared under its **own**
class the same difference is admissible, because for `P_CHANGE` a projection difference is the
intervention rather than a fault (manual §26.3).

The intervention classes above are **derived** from the declarations at every anchor, not asserted:
`derive_arm_intervention_class` returns the weakest class the arm has anywhere in the bank, and
raises on an empty bank rather than defaulting to `R_ONLY`.

### Byte deltas (median over the 223 anchors)

| arm | states with changed bytes | median Δ chars | range | median growth |
|---|---|---|---|---|
| `R_A_PRIME` | 223 / 223 | +12 | +3 … +57 | **+5.6 %** |
| `R_B` | 223 / 223 | +80 | +42 … +344 | **+37.1 %** |

Both arms change the bytes at every anchor, so `bytes_differ` in the parity result is never
satisfied by the `renderer_id` alone. The size gap between them is itself a finding — see §5.

---

## 4. What a bijective `R_ONLY` pair does and does not license

**It licenses.** A statement of the form: *at these 223 anchored states, holding the truth state,
the action space, the verifier, the Solver, the decode parameters and the compute budget fixed,
and having shown mechanically that the two renderings carry the same information, the measured
difference in `p_accept` was Δ (CI …).* The bijection is what makes "the same information" a
checked fact rather than the renderer's own testimony, and it is what distinguishes this from
HC-V0.5's `R_ONLY` claim, which rested on a declaration V05-15 showed to be forgeable.

**It does not license.**

* **Not a claim about mathematical ability.** The endpoint is one action deep and kernel-decided.
  mathlib4 is `HISTORICALLY_EXPOSED` and exposure is transitive; nothing in this arena separates a
  solved goal from a recalled one. The defensible phrasing stays *execution under kernel
  verification*.
* **Not a claim about horizons.** HC-V0.5 already established that a per-step edge does not imply
  a horizon effect. `Δ` here is a per-action quantity and generalises to nothing longer.
* **Not a claim about representations in general.** It is a claim about `R_B`'s specific layout
  against Lean's specific pretty-printer, on one model, one tokenizer, one bank, one prompt
  template. `R_B` is *one* point in the interface (`I`) gene space of manual §10.9, not a sample
  from it.
* **Not "no effect" from a null.** A null `Δ(R_A,R_B)` is uninterpretable without the minimum
  detectable effect actually achieved at the realised `n` and `k` (design brief §9.5) and without
  `C2` having fired. If the assay cannot detect the removal of the goal text, it cannot detect
  anything.
* **Not a decomposition of the effect.** Even with `Δ(R_A,R_A′) ≈ 0`, "attributable to structure"
  means "not attributable to the *whitespace* channel of byte perturbation". `R_A_PRIME` bounds
  one channel, not all of them — see §5.
* **Not transportable across models.** Under manual §24 this is a Q-A measurement: *which language
  best exploits a **fixed pretrained model***. Q-A results are properties of the (model, tokenizer,
  language) triple. A different Solver may order the arms differently, and that would not be a
  contradiction.

---

## 5. The tokenizer question, answered explicitly

**The question.** `R_B` changes the byte layout, which under a fixed tokenizer changes the token
sequence the model sees. Does that keep it `R_ONLY`, or is it a `TAU` confound?

**What the manual actually requires.** §26.2 lists what `R_ONLY` holds fixed: truth state, visible
mathematical information, action semantics/cardinality, **tokenizer**, Solver, controller, tools,
training examples, evaluation tasks, verifier, compute regime — *"Only approved
representation/morphology/interface structure differs."* §26.6 says *"changing the tokenizer is
`TAU_CHANGE` or `JOINT`."*

**Verdict: `R_B` is `R_ONLY`. It is not a `TAU` confound in the manual's sense.** The object §26.2
fixes is the tokenizer τ — the vocabulary and merge table — and both arms are served by the
identical `qwen3.6:27b-mlx` tokenizer, byte-for-byte the same function. What differs is its
*input*. Reading "hold the tokenizer fixed" as "produce the same token sequence" would make
`R_ONLY` an empty class for any text-in/text-out model: every change of bytes changes the token
sequence, so no representation intervention could ever be `R_ONLY`, and §26.2's own phrase "only
approved representation/morphology/interface structure differs" would be unsatisfiable. That
cannot be the reading.

**But the confound inside the effect is real, and §26.6 names it.** §26.6: *"A fixed pretrained
tokenizer gives different segmentation/frequency priors to English words and invented symbols…
Q-A may measure language under the incumbent tokenizer; claims about intrinsic morphology require
matched-adaptation and tokenization/frequency controls."* `R_B` introduces `[GOAL 1 OF 2]`,
`[HYPOTHESES 2]`, `(1) `, `[TARGET]` — bracketed English words and digits, which a pretrained BPE
vocabulary segments very differently from Lean's `⊢`. A measured `Δ(R_A,R_B)` therefore contains,
inseparably:

1. whatever the restructuring does to the model's ability to read the state; **and**
2. whatever the incumbent tokenizer's segmentation and frequency priors do for the new byte
   shapes.

This design cannot separate those two. That is admissible **under Q-A**, which is explicitly a
measurement of language against a fixed pretrained model and its incumbent tokenizer. It is not
admissible as a claim about intrinsic morphology or about machine-native structure — that is Q-B,
and Q-B requires matched adaptation and tokenization/frequency controls this experiment does not
have.

**So: a finding, stated as one.**

* `R_B` satisfies `R_ONLY` (§26.2) — the tokenizer is unchanged, the declared information is
  identical, the bijection proves it.
* `Δ(R_A,R_B)` is a **Q-A** quantity and must be reported as one. It confounds structure with
  tokenizer priors, and this design cannot decompose it.
* `R_A_PRIME` **narrows** that confound without eliminating it. A non-zero `Δ(R_A,R_A′)` would be
  direct evidence that bare byte/token perturbation moves the outcome, which would block
  attributing `Δ(R_A,R_B)` to structure. A null `Δ(R_A,R_A′)` shows the *whitespace* channel is
  inert; it does **not** show the *new-vocabulary* channel is, because whitespace perturbation and
  bracketed-English perturbation are different in kind. Anyone reading a null `Δ(R_A,R_A′)` as
  "tokenization is ruled out" is over-claiming.
* Two further asymmetries must be reported beside the headline number rather than assumed away:
  `R_B`'s rendering is **+37 % longer** in characters at the median (`R_A_PRIME`: +5.6 %), so the
  arms do **not** consume equal prompt tokens. §26.2 fixes the compute *regime* (same model,
  decode parameters and budget), which holds; §26.5 nonetheless requires token/compute-matched
  *reporting* where relevant, and it is relevant here. Per-call `prompt_eval_count` must be
  recorded per arm and reported. Note that no local tokenizer is available to pre-count:
  `arena/trajectory/solver.py` documents that Ollama exposes no `/api/tokenize` endpoint for this
  model, so token counts exist only per generating call.
* Closing the confound properly needs an arm whose restructuring uses a *different* vocabulary
  with the same structure, or a matched-adaptation (Q-B) design. Neither is in scope for HC-V0.6,
  and neither should be added after seeing a result.

---

## 6. Known gaps and cross-file inconsistency

* **Name collision on `R_A_PRIME`, unresolved.** `arena/experiments/hc_v0_6/schema.py` declares
  `Arm.R_A_PRIME` meaning *"the baseline renderer drawn a second time"* — design brief §9.2's
  identity control `C1` — with `Arm.R_A_PRIME.renderer_id == "R_A"`, and
  `arena/experiments/hc_v0_6/estimators.py` maps `Comparison.C1_IDENTITY` to
  `(R_A, R_A_PRIME)`. Design brief §9.4 gives the same name to a *distinct renderer*, the
  byte-perturbation control defined here, and §9.2 places `C1` inside `R_A`'s own replicates.
  Those two meanings cannot both stand. This document does not edit those files. **The collision
  must be resolved before the assay runs**, or `C1` and the byte-perturbation control will be
  silently the same column: Holm's family widens to four comparisons under §9.4, and the analysis
  package currently declares three.
* **`R_A_PRIME` is one perturbation, not a family.** Whitespace was chosen because it is the only
  perturbation that is uncontroversially semantically null *and* a total bijection. It is
  therefore a weak probe of the byte-sensitivity channel, and a null result from it is
  correspondingly weak evidence.
* **The AST guard's whitelist is function-name-scoped.** `ALLOWED_STATE_TEXT_SITES` in
  `tests/trajectory/test_arena_v0.py` now whitelists `("representation.py", "present")` and
  `("representation.py", "parse_tactic_state")`. Both are round-trip **self-tests** — a renderer
  checking that its own output inverts to the text it came from — and neither decides whether a
  step was mathematically correct, which is what the guard exists to forbid. But the scan records
  the enclosing *function* name only, so any future `present` in that module inherits the
  exemption. That is a real, if small, loosening of the net.
* **One refusal reason was mis-assigned and is now fixed.** `"a : Nat\n\n\n⊢ True"` was refused as
  `NO_GOAL_MARKER` because its *first* blank-line-separated block has no turnstile, while the
  state plainly carries an open goal. `NO_GOAL_MARKER` means "Lean printed `no goals`; not an
  anchor", and refusal reasons are reported as **counts**, so that mis-assignment would have
  inflated the "not an anchor" tally with states whose real defect was a stray blank line.
  `parse_tactic_state` now tests the turnstile against the whole pretty-print first, then tests
  for empty lines across every block before parsing any of them, so the reported reason names the
  cause rather than the first symptom.
