"""Simulated operating characteristics of the Fitness-V5 frontier selector.

============================== READ THIS FIRST ==============================
EXPLORATORY, POST-HOC INSTRUMENT-PROPERTY SIMULATION.

Nothing here re-scores V5, licenses a new threshold, or promotes anything.
It measures a property of the frozen instrument's SELECTION RULE under an
explicit generative model of a solver. No model call is made; no frozen
artifact is modified.
=============================================================================

Generative model (per simulated mechanism, per replicate)
--------------------------------------------------------
Each level L in {0,1,2,3} runs 12 ORIGINAL probes (target = option index 0)
and 12 COUNTERFACTUAL probes (target = option index 1); n = 24 positives.

A solver with true per-level accuracy p answers each positive probe correctly
independently with probability p, and otherwise picks the other option
(binary forced choice). Therefore, per level:

    co ~ Binomial(12, p)      correct ORIGINALs      -> answered index 0
    cc ~ Binomial(12, p)      correct COUNTERFACTUALs -> answered index 1
    accuracy               = (co + cc) / 24
    index-0 answer count   = co + (12 - cc)
    largest_answer_share   = max(k0, 24 - k0) / 24

This couples accuracy and answer share exactly as the instrument does: an
honest independent-error reader has share concentrated near 0.5 whatever its
accuracy, while a constant answerer has share 1.0 at accuracy exactly 0.5.

Position invariance uses 24 (base, swapped) pairs; under the same independent-
error model the same CONTENT is chosen under option reversal with probability
q = p^2 + (1-p)^2, so invariance ~ Binomial(24, q) / 24.

The destroyed negative control is fixed at exactly 0.5000. That is not an
assumption: destroyed twins are byte-identical prompts with opposite targets
(arena/experiments/fitness_v5.py:485-486, asserted at :505-509), so any
deterministic solver scores exactly half. Verified against the frozen Phase-5
rows in frozen_ladder_analysis.py.

Gates assumed to PASS and therefore NOT simulated: Q0, valid-response rate,
input/output truncation, and the shortcut audit. The first four were 1.000 /
0 everywhere in Phase 5 under grammar-constrained decoding. The shortcut audit
is a property of the probe SET, not of the solver, so it is orthogonal to the
selector and would apply identically to every selector compared here.
"""

from __future__ import annotations

import bisect
import json
import math
import random
from pathlib import Path
from typing import Any

# --- frozen gate constants, transcribed from arena/experiments/fitness_v5.py:208-247
EXPLICIT_MIN = 0.90  # :212
FRONTIER_TARGET = 0.625  # :213
BAND_LOW, BAND_HIGH = 0.35, 0.85  # :214
GAP_MIN = 0.20  # :219
DESTROYED_MAX = 0.60  # :220
SHARE_MAX = 0.75  # :221
INVARIANCE_MIN = 0.50  # :224

DESTROYED = 0.5000  # structural constant, verified in frozen_ladder_analysis.py

# Effective positive-accuracy window implied by the implementation:
#   gap >= 0.20 with destroyed == 0.5  <=>  accuracy >= 0.70
#   frontier band ceiling              <=>  accuracy <= 0.85
WINDOW_LOW, WINDOW_HIGH = GAP_MIN + DESTROYED, BAND_HIGH
WINDOW_MID = (WINDOW_LOW + WINDOW_HIGH) / 2  # 0.775

N_POSITIVES = 24
N_HALF = 12
SEED = 20260905  # the instrument's own seed, reused for reproducibility


# ------------------------------------------------------------ binomial sampling


class Binom:
    """Inverse-CDF sampler for a fixed (n, p). Exact, and fast enough in pure Python."""

    _cache: dict[tuple[int, float], "Binom"] = {}

    def __init__(self, n: int, p: float) -> None:
        self.n, self.p = n, p
        cdf, total = [], 0.0
        for k in range(n + 1):
            total += math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))
            cdf.append(total)
        cdf[-1] = 1.0
        self.cdf = cdf

    @classmethod
    def get(cls, n: int, p: float) -> "Binom":
        key = (n, round(p, 12))
        if key not in cls._cache:
            cls._cache[key] = cls(n, key[1])
        return cls._cache[key]

    def draw(self, rng: random.Random) -> int:
        return bisect.bisect_left(self.cdf, rng.random())


# ------------------------------------------------------------------- one cell


def draw_cell(p: float, rng: random.Random) -> dict[str, float]:
    """Draw one (mechanism, level) cell for an independent-error reader."""
    co = Binom.get(N_HALF, p).draw(rng)
    cc = Binom.get(N_HALF, p).draw(rng)
    k0 = co + (N_HALF - cc)
    q = p * p + (1 - p) * (1 - p)
    inv = Binom.get(N_POSITIVES, q).draw(rng)
    return {
        "accuracy": (co + cc) / N_POSITIVES,
        "share": max(k0, N_POSITIVES - k0) / N_POSITIVES,
        "invariance": inv / N_POSITIVES,
    }


def constant_cell() -> dict[str, float]:
    """A solver that always answers option index 0, deterministically."""
    return {"accuracy": 0.5, "share": 1.0, "invariance": 0.0}


def cell_passes_gates(cell: dict[str, float], gap_min: float = GAP_MIN) -> tuple[bool, str]:
    acc = cell["accuracy"]
    if acc < BAND_LOW:
        return False, "VOID_FLOOR"
    if acc > BAND_HIGH:
        return False, "VOID_CEILING"
    if acc - DESTROYED < gap_min or DESTROYED > DESTROYED_MAX:
        return False, "VOID_NEGATIVE_CONTROL"
    if cell["share"] > SHARE_MAX:
        return False, "VOID_POSITION_SHARE"
    if cell["invariance"] < INVARIANCE_MIN:
        return False, "VOID_POSITION"
    return True, "QUALIFIED"


# -------------------------------------------------------------------- selectors


def select_nearest(cells: dict[int, dict[str, float]], target: float) -> int:
    """Minimise |accuracy - target| over L1..L3, ties to the LOWER level.

    target = 0.625 reproduces the frozen selector (fitness_v5.py:932-933).
    """
    return min(
        sorted(cells),
        key=lambda lvl: (abs(cells[lvl]["accuracy"] - target), lvl),
    )


# name -> (target accuracy the selector aims at, gap_min it then applies)
# gap_min 0.20 with destroyed == 0.5 means "accuracy >= 0.70";
# gap_min 0.25 means "accuracy >= 0.75" and is the FP-calibrated variant.
SELECTOR_SPEC: dict[str, dict[str, Any]] = {
    "current_target_0.625": {"target": FRONTIER_TARGET, "gap_min": GAP_MIN, "mode": "nearest"},
    "window_midpoint_0.775": {"target": WINDOW_MID, "gap_min": GAP_MIN, "mode": "nearest"},
    "highest_qualifying": {"target": FRONTIER_TARGET, "gap_min": GAP_MIN, "mode": "highest"},
    "midpoint_0.80_gap0.25_calibrated": {"target": 0.80, "gap_min": 0.25, "mode": "nearest"},
}
SELECTORS = (*SELECTOR_SPEC, "oracle_knows_true_p")


def run_oracle(
    explicit_acc: float,
    cells: dict[int, dict[str, float]],
    profile: tuple[float, float, float],
) -> dict[str, Any]:
    """Sensitivity CEILING: a selector with perfect knowledge of the true profile.

    It picks the level whose TRUE accuracy is nearest the effective window
    midpoint, then applies the ordinary observed-data gates. Any real selector
    scoring ABOVE this is not selecting better - it is harvesting sampling noise
    by selecting on the outcome.
    """
    if explicit_acc < EXPLICIT_MIN:
        return {"selector": "oracle_knows_true_p", "level": None,
                "verdict": "VOID_INSTRUMENT_LIMIT", "qualified": False}
    lvl = min((1, 2, 3), key=lambda i: (abs(profile[i - 1] - WINDOW_MID), i))
    ok, verdict = cell_passes_gates(cells[lvl], GAP_MIN)
    return {"selector": "oracle_knows_true_p", "level": lvl, "verdict": verdict, "qualified": ok}


def run_selector(
    name: str, explicit_acc: float, cells: dict[int, dict[str, float]]
) -> dict[str, Any]:
    spec = SELECTOR_SPEC[name]
    gap_min = float(spec["gap_min"])
    if explicit_acc < EXPLICIT_MIN:
        return {"selector": name, "level": None, "verdict": "VOID_INSTRUMENT_LIMIT", "qualified": False}
    if spec["mode"] == "highest":
        # Maximally permissive: pick the DEEPEST level that passes every gate.
        # This selects on the qualification statistic itself.
        for lvl in sorted(cells, reverse=True):
            ok, verdict = cell_passes_gates(cells[lvl], gap_min)
            if ok:
                return {"selector": name, "level": lvl, "verdict": verdict, "qualified": True}
        lvl = select_nearest(cells, FRONTIER_TARGET)
        return {
            "selector": name,
            "level": lvl,
            "verdict": cell_passes_gates(cells[lvl], gap_min)[1],
            "qualified": False,
        }
    lvl = select_nearest(cells, float(spec["target"]))
    ok, verdict = cell_passes_gates(cells[lvl], gap_min)
    return {"selector": name, "level": lvl, "verdict": verdict, "qualified": ok}


# ---------------------------------------------------------------------- sweep


def simulate_profile(
    p0: float,
    profile: tuple[float, float, float],
    replicates: int,
    rng: random.Random,
    constant_answerer: bool = False,
) -> dict[str, Any]:
    counts = {s: 0 for s in SELECTORS}
    verdicts: dict[str, dict[str, int]] = {s: {} for s in SELECTORS}
    agree_level = agree_verdict = 0
    level_choice: dict[str, dict[int, int]] = {s: {1: 0, 2: 0, 3: 0} for s in SELECTORS}
    explicit_binom = Binom.get(N_POSITIVES, p0)
    for _ in range(replicates):
        explicit_acc = explicit_binom.draw(rng) / N_POSITIVES
        if constant_answerer:
            cells = {lvl: constant_cell() for lvl in (1, 2, 3)}
        else:
            cells = {lvl: draw_cell(profile[lvl - 1], rng) for lvl in (1, 2, 3)}
        outs = {s: run_selector(s, explicit_acc, cells) for s in SELECTOR_SPEC}
        outs["oracle_knows_true_p"] = run_oracle(
            explicit_acc, cells, (0.5, 0.5, 0.5) if constant_answerer else profile
        )
        for s, out in outs.items():
            counts[s] += bool(out["qualified"])
            verdicts[s][out["verdict"]] = verdicts[s].get(out["verdict"], 0) + 1
            if out["level"] is not None:
                level_choice[s][out["level"]] += 1
        a, b = outs["current_target_0.625"], outs["window_midpoint_0.775"]
        agree_level += a["level"] == b["level"]
        agree_verdict += a["qualified"] == b["qualified"]
    true_band_levels = [lvl for lvl in (1, 2, 3) if WINDOW_LOW <= profile[lvl - 1] <= WINDOW_HIGH]
    return {
        "explicit_p0": p0,
        "true_profile_L1_L3": list(profile),
        "true_levels_inside_effective_window": true_band_levels,
        "has_true_band": bool(true_band_levels) and p0 >= EXPLICIT_MIN,
        "replicates": replicates,
        "p_qualified": {s: counts[s] / replicates for s in SELECTORS},
        "verdict_mix": verdicts,
        "selected_level_mix": level_choice,
        "selector_agreement_same_level": agree_level / replicates,
        "selector_agreement_same_verdict": agree_verdict / replicates,
    }


def main() -> dict[str, Any]:
    rng = random.Random(SEED)
    replicates = 20_000
    null_replicates = 200_000

    # --- sensitivity sweep: solvers with a genuine, declining band ------------
    # p_l = 0.5 + (p1 - 0.5) * decay^(l-1), a monotone decline toward chance.
    sweep: list[dict[str, Any]] = []
    p1_grid = [0.95, 0.90, 0.85, 0.80, 0.775, 0.75, 0.70, 0.65, 0.625, 0.60, 0.55]
    decay_grid = [0.90, 0.70, 0.50, 0.30]
    for p1 in p1_grid:
        for decay in decay_grid:
            profile = tuple(0.5 + (p1 - 0.5) * decay ** (lvl - 1) for lvl in (1, 2, 3))
            row = simulate_profile(0.98, profile, replicates, rng)  # L0 competent
            row["decay"] = decay
            row["p1"] = p1
            sweep.append(row)

    with_band = [r for r in sweep if r["has_true_band"]]
    without_band = [r for r in sweep if not r["has_true_band"]]

    def mean(rows: list[dict[str, Any]], selector: str) -> float:
        return sum(r["p_qualified"][selector] for r in rows) / len(rows) if rows else 0.0

    sensitivity = {
        "profiles_with_a_true_in_window_level": len(with_band),
        "profiles_without": len(without_band),
        "mean_p_qualified_given_true_band": {s: mean(with_band, s) for s in SELECTORS},
        "mean_p_qualified_no_true_band": {s: mean(without_band, s) for s in SELECTORS},
        "max_sensitivity_gain_over_current": max(
            (
                {
                    "p1": r["p1"],
                    "decay": r["decay"],
                    "true_profile": r["true_profile_L1_L3"],
                    "current": r["p_qualified"]["current_target_0.625"],
                    "window_midpoint": r["p_qualified"]["window_midpoint_0.775"],
                    "highest_qualifying": r["p_qualified"]["highest_qualifying"],
                    "calibrated": r["p_qualified"]["midpoint_0.80_gap0.25_calibrated"],
                    "gain_midpoint": r["p_qualified"]["window_midpoint_0.775"]
                    - r["p_qualified"]["current_target_0.625"],
                }
                for r in with_band
            ),
            key=lambda d: d["gain_midpoint"],
        )
        if with_band
        else None,
    }

    # --- false-positive rates against nulls ----------------------------------
    nulls: dict[str, Any] = {}
    for label, p0 in (("L0_competent(p0=1.0)", 1.0), ("L0_null(p0=0.5)", 0.5)):
        nulls[f"coin_flipper|{label}"] = simulate_profile(
            p0, (0.5, 0.5, 0.5), null_replicates, rng
        )
        nulls[f"constant_answerer|{label}"] = simulate_profile(
            p0, (0.5, 0.5, 0.5), 2000, rng, constant_answerer=True
        )
    # A "lucky reader" null that is genuinely at chance but not position-locked
    # is the coin flipper; a partially-competent decoy sits just under the window.
    nulls["sub_window_reader(p=0.65 flat)|L0_competent"] = simulate_profile(
        1.0, (0.65, 0.65, 0.65), null_replicates, rng
    )

    # --- deterministic counterfactual on the FROZEN Phase-5 ladder ------------
    frozen = json.loads(
        (Path(__file__).with_name("frozen_ladder_analysis.json")).read_text()
    )
    frozen_counterfactual: dict[str, Any] = {}
    for mechanism, block in frozen["grid"].items():
        levels = block["levels"]
        explicit = block["explicit_positive_accuracy_L0"]
        cells = {
            int(lvl): {
                "accuracy": levels[lvl]["positive_accuracy"],
                "share": levels[lvl]["largest_answer_share"],
                # off-frontier invariance was never measured; give the
                # alternative selectors the benefit of the doubt (assume PASS)
                # so the comparison cannot be biased against them.
                "invariance": (
                    levels[lvl]["position_invariance"]
                    if levels[lvl]["position_invariance"] is not None
                    else 1.0
                ),
            }
            for lvl in levels
            if int(lvl) >= 1
        }
        frozen_counterfactual[mechanism] = {
            s: run_selector(s, explicit, cells) for s in SELECTOR_SPEC
        }
    frozen_counterfactual["_note"] = (
        "Off-frontier position invariance and the shortcut audit were never measured in "
        "Phase 5 (only positive arms ran off-frontier). Invariance is set to PASS and the "
        "shortcut audit is omitted, which can only FAVOUR the alternative selectors. "
        "EXPLORATORY: this does not re-score V5."
    )
    frozen_counterfactual["_qualified_mechanism_count"] = {
        s: sum(
            1
            for m, v in frozen_counterfactual.items()
            if not m.startswith("_") and v[s]["qualified"]
        )
        for s in SELECTOR_SPEC
    }

    return {
        "ANALYSIS_CLASS": "EXPLORATORY_POST_HOC_INSTRUMENT_PROPERTY",
        "model_calls_made_by_this_analysis": 0,
        "seed": SEED,
        "effective_positive_accuracy_window": [WINDOW_LOW, WINDOW_HIGH],
        "window_width_in_standard_errors_at_n24": round(
            (WINDOW_HIGH - WINDOW_LOW)
            / math.sqrt(WINDOW_MID * (1 - WINDOW_MID) / N_POSITIVES),
            3,
        ),
        "window_midpoint": WINDOW_MID,
        "frontier_target_in_window": WINDOW_LOW <= FRONTIER_TARGET <= WINDOW_HIGH,
        "selectors": list(SELECTORS),
        "sensitivity_summary": sensitivity,
        "sweep": sweep,
        "false_positive_nulls": nulls,
        "frozen_phase5_counterfactual": frozen_counterfactual,
    }


if __name__ == "__main__":
    out = main()
    dest = Path(__file__).with_name("selector_simulation.json")
    dest.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Selector sweep - EXPLORATORY / POST-HOC instrument-property simulation",
        "",
        "NOT a re-scoring of V5. Measures the frozen frontier selector, not any representation.",
        "",
        "`P(qualified)` per selector; n = 24 positives per level; destroyed control fixed at",
        "the structural constant 0.5000; 20,000 replicates per profile; L0 explicit p = 0.98.",
        "`band?` marks profiles that genuinely have a level inside the effective window [0.70, 0.85].",
        "",
        "| p(L1) | p(L2) | p(L3) | band? | current 0.625 | midpoint 0.775 | highest-qual | calibrated 0.80/0.25 | oracle |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in out["sweep"]:
        q = r["p_qualified"]
        lines.append(
            "| {:.3f} | {:.3f} | {:.3f} | {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |".format(
                *r["true_profile_L1_L3"],
                "YES" if r["has_true_band"] else "no",
                q["current_target_0.625"],
                q["window_midpoint_0.775"],
                q["highest_qualifying"],
                q["midpoint_0.80_gap0.25_calibrated"],
                q["oracle_knows_true_p"],
            )
        )
    lines += ["", "## False-positive rates against null and near-null solvers", "",
              "| null solver | " + " | ".join(out["selectors"]) + " |",
              "|---" * (len(out["selectors"]) + 1) + "|"]
    for label, row in out["false_positive_nulls"].items():
        lines.append(
            "| " + label + " | "
            + " | ".join(f"{row['p_qualified'][k]:.5f}" for k in out["selectors"]) + " |"
        )
    table = Path(__file__).with_name("selector_sweep.md")
    table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {dest}")
    print(f"wrote {table}\n")
    print(f"effective window {out['effective_positive_accuracy_window']}, "
          f"selector target 0.625 inside window: {out['frontier_target_in_window']}")
    s = out["sensitivity_summary"]
    print("\nMEAN P(qualified) over sweep profiles that DO have a true in-window level:")
    for k, v in s["mean_p_qualified_given_true_band"].items():
        print(f"  {k:34s} {v:.4f}")
    print("MEAN P(qualified) over sweep profiles with NO true in-window level:")
    for k, v in s["mean_p_qualified_no_true_band"].items():
        print(f"  {k:34s} {v:.4f}")
    print(f"\nlargest single-profile gain (midpoint over current): {s['max_sensitivity_gain_over_current']}")
    print("\nFALSE POSITIVES (P(qualified) under a null solver):")
    for label, row in out["false_positive_nulls"].items():
        vals = "  ".join(f"{k}={row['p_qualified'][k]:.5f}" for k in out["selectors"])
        print(f"  {label:46s}\n      {vals}")
    print("\nFROZEN PHASE-5 COUNTERFACTUAL (exploratory):")
    fc = out["frozen_phase5_counterfactual"]
    for m, v in fc.items():
        if m.startswith("_"):
            continue
        print(f"  {m}")
        for sel in out["selectors"]:
            if sel not in v:
                continue
            print(f"    {sel:34s} -> level {v[sel]['level']}  {v[sel]['verdict']}")
    print(f"  qualified mechanism count: {fc['_qualified_mechanism_count']}")
