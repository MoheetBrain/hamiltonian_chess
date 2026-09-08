"""Rendered-prompt adversary audit of ``transitive_dependency`` (Phase 8 preparation).

Run as ``.venv/bin/python -m research.phase8.transitive.audit``.  CPU-only, offline, ZERO model
calls.  Nothing here re-scores V7 or reinterprets a recorded sentinel.

Protocol
--------
* Fresh population: levels 1..3, ``N`` families per level, salts ``8_000_000 + level*100_000 +
  index`` (every prior salt for this mechanism lies in [20261907, ~20362700]).  ORIGINAL +
  COUNTERFACTUAL positives and both SWAPPED variants are kept.
* Every item is rendered through the eight founder surfaces into the exact harness envelope
  (``game_r_formal_v1.build_prompt`` with ``SyntaxGuidePolicy.SHARED_CONSTANT``).
* Adversaries see the prompt string and the option count only, through
  ``arena.experiments.rendered_prompt_adversary`` (lazy import; the research-local fallback in
  ``.adversary`` is used only if the shared module is missing, and the JSON records which ran).
* DEVELOPMENT = families 0..N/2-1, EVALUATION = N/2..N-1.  Per (generator, level, surface) the
  top-3 rules are selected and the shallow models fitted on DEVELOPMENT, frozen (content hash),
  then evaluated on EVALUATION with exact Clopper-Pearson intervals, Holm over the frozen
  adversaries, and a within-family label-permutation null (2000 draws) for the max over the
  frozen family.  Twin invariance per feature is measured on the rendered prompt.

Two generators are audited: ``v1_frozen`` (the V4/V5/V7 ``_dependency_family``, the object of
the brief) and ``v2_candidate`` (a research-local, balanced-by-construction proposal in
``common.py``; it is NOT in ``arena/`` and is reported only as the spec's candidate remedy).
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from .common import (
    GENERATORS,
    LEVELS,
    MECHANISM,
    N_FAMILIES,
    SALT_BASE,
    SALT_LEVEL_STRIDE,
    SURFACES,
    V2_GENERATOR_VERSION,
    Item,
    build_population,
    family_salt,
    hops_for_level,
    render,
    shared_adversary_module,
    validate_v1_family,
    validate_v2_items,
)

HERE = Path(__file__).resolve().parent
SEED = 20260907


def _clean(value: Any) -> Any:
    """JSON-safe: tuples -> lists, numpy scalars -> python, NaN -> None."""

    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


# ----------------------------------------------------------------------------- population


def build_examples(
    shared: Any, generator: str, level: int, n_families: int, *, validate: bool
) -> tuple[list[Item], dict[str, dict[str, list[Any]]], dict[str, Any]]:
    """Materialise one (generator, level) cell and render it through every founder surface.

    Returns the items, ``{surface: {"positives": [...], "swapped": [...]}}`` of shared-module
    ``Example`` objects, and a small statistics record (prompt characters per surface, timing).
    """

    t0 = time.perf_counter()
    items = build_population(generator, level, n_families)
    if validate:
        if generator == "v1_frozen":
            for index in range(n_families):
                validate_v1_family(level, index)
        else:
            for index in range(n_families):
                validate_v2_items([i for i in items if i.family_index == index])
    t_build = time.perf_counter() - t0
    variants = Counter(i.variant for i in items)
    t0 = time.perf_counter()
    examples: dict[str, dict[str, list[Any]]] = {s: {"positives": [], "swapped": []} for s in SURFACES}
    chars: dict[str, list[int]] = {s: [] for s in SURFACES}
    n_render = 0
    for item in items:
        for surface in SURFACES:
            prompt = render(item, surface)
            n_render += 1
            example = shared.Example(
                prompt=prompt,
                n_options=2,
                correct_index=item.expected_index,
                family_id=item.family_id,
                arm_id=surface,
                task_id=f"{surface}:{item.family_id}:{item.variant}",
            )
            bucket = "positives" if item.is_positive else "swapped"
            examples[surface][bucket].append(example)
            if item.is_positive:
                chars[surface].append(len(prompt))
    t_render = time.perf_counter() - t0
    stats = {
        "generator": generator,
        "level": level,
        "hops": hops_for_level(level),
        "n_families": n_families,
        "salts": [family_salt(level, 0), family_salt(level, n_families - 1)],
        "variants": dict(variants),
        "validated": validate,
        "build_seconds": t_build,
        "render_seconds": t_render,
        "n_renders": n_render,
        "prompt_chars_positives": {
            s: {
                "mean": float(np.mean(v)),
                "min": int(np.min(v)),
                "max": int(np.max(v)),
                "std": float(np.std(v)),
            }
            for s, v in chars.items()
        },
    }
    return items, examples, stats


def split(examples: list[Any], dev_families: set[str]) -> tuple[list[Any], list[Any]]:
    dev = [e for e in examples if e.family_id in dev_families]
    ev = [e for e in examples if e.family_id not in dev_families]
    return dev, ev


# ----------------------------------------------------------------------- frozen predictions


def frozen_predictions(shared: Any, frozen: Any, examples: list[Any]) -> dict[str, list[int | None]]:
    views = [shared.extract_surface(e.prompt, e.n_options) for e in examples]
    rows = [shared.rule_predictions(v) for v in views]
    preds: dict[str, list[int | None]] = {}
    for rule in frozen.selected_rules:
        preds[rule] = [row[rule] for row in rows]
    for model in frozen.models:
        preds[model.name] = [model.predict(v) for v in views]
    return preds


def credit_matrix(preds: dict[str, list[int | None]], examples: list[Any]) -> tuple[list[str], np.ndarray]:
    names = list(preds)
    labels = np.asarray([e.correct_index for e in examples])
    P = np.asarray([[-1 if p is None else p for p in preds[n]] for n in names], dtype=np.int64)
    chance = np.asarray([1.0 / e.n_options for e in examples])
    C = (P == labels[None, :]).astype(float) + (P < 0).astype(float) * chance[None, :]
    return names, C


def frozen_permutation_null(
    names: list[str], C: np.ndarray, examples: list[Any], *, n_perm: int, seed: int
) -> dict[str, Any]:
    """Within-family label permutation null for the max credited accuracy over the frozen family.

    Every family here is a twin with opposite labels, so the only within-family permutation is the
    identity or the swap; a swap flips every decided credit in that family and leaves abstentions
    (credit 1/2) unchanged.  That is exactly the null the shared module samples, specialised to
    twins, and it is exact for this bank.
    """

    fam_ids = sorted({e.family_id for e in examples})
    fam_lookup = {f: i for i, f in enumerate(fam_ids)}
    fam_index = np.asarray([fam_lookup[e.family_id] for e in examples])
    rng = np.random.default_rng(seed)
    observed = C.mean(axis=1)
    null_max = np.empty(n_perm)
    null_rule = np.zeros(len(names))
    for t in range(n_perm):
        flip = (rng.random(len(fam_ids)) < 0.5)[fam_index].astype(float)[None, :]
        Cp = C + flip * (1.0 - 2.0 * C)
        acc = Cp.mean(axis=1)
        null_max[t] = acc.max()
        null_rule += acc
    obs_max = float(observed.max())
    return {
        "n_permutations": n_perm,
        "observed_max": obs_max,
        "null_mean_max": float(null_max.mean()),
        "null_sd_max": float(null_max.std(ddof=1)),
        "null_q95_max": float(np.quantile(null_max, 0.95)),
        "null_q99_max": float(np.quantile(null_max, 0.99)),
        "null_max": float(null_max.max()),
        "p_value_max": float((null_max >= obs_max - 1e-12).mean()),
        "null_mean_per_adversary": {n: float(v / n_perm) for n, v in zip(names, null_rule, strict=True)},
    }


def family_hit_histogram(C_row: np.ndarray, examples: list[Any]) -> dict[str, int]:
    per_family: dict[str, float] = {}
    for c, e in zip(C_row, examples, strict=True):
        per_family[e.family_id] = per_family.get(e.family_id, 0.0) + float(c)
    return {str(k): v for k, v in sorted(Counter(per_family.values()).items())}


def position_consistency(
    shared: Any, frozen: Any, base: list[Any], swapped: list[Any]
) -> dict[str, Any]:
    """Frozen adversaries on the option-swapped twins of the EVALUATION items.

    ``content_consistent`` = the adversary picked the same *content* on base and swapped (both
    abstain, or predictions differ by position); ``letter_consistent`` = same letter.  A
    position-blind adversary is content-consistent on every pair.
    """

    # task_id = f"{surface}:{family_id}:{variant}"; the swapped twin's variant is SWAPPED_<variant>.
    base_by = {e.task_id: e for e in base}
    pairs: list[tuple[Any, Any]] = []
    for e in swapped:
        b = base_by.get(e.task_id.replace(":SWAPPED_", ":"))
        if b is None:
            raise ValueError(f"no base item for swapped task {e.task_id}")
        if b.correct_index != 1 - e.correct_index:
            raise ValueError("swapped twin does not invert the target")
        pairs.append((b, e))
    if not pairs:
        return {"n_pairs": 0}
    pb = frozen_predictions(shared, frozen, [p[0] for p in pairs])
    ps = frozen_predictions(shared, frozen, [p[1] for p in pairs])
    out: dict[str, Any] = {"n_pairs": len(pairs), "per_adversary": {}}
    for name in pb:
        content = letter = 0
        correct_sw = 0.0
        for (b, s), x, y in zip(pairs, pb[name], ps[name], strict=True):
            if x is None and y is None:
                content += 1
                letter += 1
            elif x is not None and y is not None:
                content += int(y == 1 - x)
                letter += int(y == x)
            if y is None:
                correct_sw += 0.5
            elif y == s.correct_index:
                correct_sw += 1.0
        out["per_adversary"][name] = {
            "content_consistent": content / len(pairs),
            "letter_consistent": letter / len(pairs),
            "credited_accuracy_on_swapped": correct_sw / len(pairs),
        }
    return out


# -------------------------------------------------------------------------- cell analysis


def analyse_cell(
    shared: Any,
    generator: str,
    level: int,
    surface: str,
    dev: list[Any],
    ev: list[Any],
    ev_swapped: list[Any],
    *,
    n_perm: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    t0 = time.perf_counter()
    frozen = shared.develop_and_freeze(dev, top_k=3, seed=seed)
    t_dev = time.perf_counter() - t0
    t0 = time.perf_counter()
    evaluation = shared.evaluate_frozen(frozen, ev)
    arm = evaluation.arm(surface)
    preds = frozen_predictions(shared, frozen, ev)
    names, C = credit_matrix(preds, ev)
    null = frozen_permutation_null(names, C, ev, n_perm=n_perm, seed=seed + level)
    best_index = names.index(arm.best)
    pos = position_consistency(shared, frozen, ev, ev_swapped)
    # Unfrozen, in-sample max over the FULL family on EVALUATION (what the old audit reported).
    insample = shared.evaluate_rules(ev, seed=seed, bootstrap_samples=200, permutations=n_perm)
    t_eval = time.perf_counter() - t0
    dev_report = frozen.dev_report
    per_adv = []
    for s in arm.adversaries:
        d = s.to_dict()
        decided_n = s.decided_n
        # Clopper-Pearson on the credited count (abstentions as half-successes, floored):
        k_cred = int(math.floor(s.accuracy * s.n))
        lo_c, hi_c = shared.clopper_pearson(k_cred, s.n)
        d["cp_credited_floor"] = [lo_c, hi_c]
        d["reaches_0.60_with_cp_lower_above_0.5"] = bool(
            s.accuracy >= 0.60 and decided_n > 0 and s.cp_lower > 0.5
        )
        d["family_hit_histogram"] = family_hit_histogram(C[names.index(s.name)], ev)
        d["null_mean_credited_accuracy"] = null["null_mean_per_adversary"][s.name]
        per_adv.append(d)
    record = {
        "generator": generator,
        "level": level,
        "hops": hops_for_level(level),
        "surface": surface,
        "adversary_module": shared.__name__,
        "adversary_family_version": shared.ADVERSARY_FAMILY_VERSION,
        "n_dev": len(dev),
        "n_dev_families": len({e.family_id for e in dev}),
        "n_eval": len(ev),
        "n_eval_families": len({e.family_id for e in ev}),
        "frozen_hash": frozen.content_hash,
        "selected_rules": list(frozen.selected_rules),
        "models": [m.name for m in frozen.models],
        "model_backends": [m.backend for m in frozen.models],
        "dev_best_rule": dev_report["best_rule"],
        "dev_best_accuracy": dev_report["best_accuracy"],
        "dev_null_expected_max": dev_report["null_expected_max"],
        "dev_null_p_value": dev_report["null_p_value"],
        "dev_top5": [
            {"rule": r["rule"], "accuracy": r["accuracy"], "abstain_rate": r["abstain_rate"]}
            for r in dev_report["rules"][:5]
        ],
        "dev_model_accuracy": {
            m.name: shared.evaluate_model(m, dev)["accuracy"] for m in frozen.models
        },
        "eval": {
            "best": arm.best,
            "best_accuracy": arm.best_accuracy,
            "best_holm_p": arm.best_holm_p,
            "best_bonferroni_cp": [arm.best_bonferroni_lower, arm.best_bonferroni_upper],
            "significant_holm_0.05": arm.significant,
            "per_adversary": per_adv,
            "frozen_family_permutation_null": null,
            "position_audit_on_swapped_eval": pos,
            "unfrozen_full_family_max_on_eval": {
                "best_rule": insample.best_rule,
                "best_accuracy": insample.best_accuracy,
                "null_expected_max": insample.null_expected_max,
                "null_q95": insample.null_quantiles["q95"],
                "null_p_value": insample.null_p_value,
                "n_rules": insample.n_rules,
            },
        },
        "seconds": {"develop": t_dev, "evaluate": t_eval},
    }
    frozen_json = json.loads(shared.to_json(frozen))
    return record, frozen_json


# ------------------------------------------------------------------------------- main


def run(
    *,
    n_families: int,
    generators: tuple[str, ...],
    levels: tuple[int, ...],
    surfaces: tuple[str, ...],
    n_perm: int,
    validate: bool,
    out_dir: Path,
) -> dict[str, Any]:
    shared = shared_adversary_module()
    fallback_note = None
    if shared is None:  # pragma: no cover - the shared module exists in this worktree
        from . import adversary as fallback

        fallback_note = (
            "arena.experiments.rendered_prompt_adversary unavailable; the research-local "
            "fallback in research/phase8/transitive/adversary.py would be needed and this run "
            "STOPPED rather than silently substituting a different family."
        )
        raise SystemExit(fallback_note)
    started = time.time()
    population: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    twins: list[dict[str, Any]] = []
    frozen_all: dict[str, Any] = {}
    for generator in generators:
        for level in levels:
            items, examples, stats = build_examples(
                shared, generator, level, n_families, validate=validate
            )
            population.append(stats)
            dev_families = {i.family_id for i in items if i.family_index < n_families // 2}
            for surface in surfaces:
                pos_dev, pos_ev = split(examples[surface]["positives"], dev_families)
                _, sw_ev = split(examples[surface]["swapped"], dev_families)
                t0 = time.perf_counter()
                twin = shared.twin_invariance_report(examples[surface]["positives"])
                twins.append(
                    {
                        "generator": generator,
                        "level": level,
                        "surface": surface,
                        "seconds": time.perf_counter() - t0,
                        **twin,
                    }
                )
                record, frozen_json = analyse_cell(
                    shared, generator, level, surface, pos_dev, pos_ev, sw_ev, n_perm=n_perm, seed=SEED
                )
                cells.append(record)
                frozen_all[f"{generator}:L{level}:{surface}"] = frozen_json
                e = record["eval"]
                print(
                    f"{generator:12s} L{level} {surface:24s} dev_best={record['dev_best_accuracy']:.4f} "
                    f"({record['dev_best_rule']}) eval_best={e['best_accuracy']:.4f} ({e['best']}) "
                    f"null_max_mean={e['frozen_family_permutation_null']['null_mean_max']:.4f} "
                    f"p={e['frozen_family_permutation_null']['p_value_max']:.3f} "
                    f"[{record['seconds']['develop']:.1f}s+{record['seconds']['evaluate']:.1f}s]",
                    flush=True,
                )
    elapsed = time.time() - started
    summary = summarise(cells, twins)
    payload = {
        "_disclaimer": (
            "Diagnostic of a POSSIBLE future instrument. Zero model calls. Nothing here re-scores "
            "Fitness V7 or reinterprets any recorded sentinel. Do not run the mechanism before the "
            "precondition founder pilot completes."
        ),
        "mechanism": MECHANISM,
        "adversary_module": shared.__name__,
        "adversary_family_version": shared.ADVERSARY_FAMILY_VERSION,
        "fallback_used": fallback_note,
        "salt_scheme": {
            "base": SALT_BASE,
            "level_stride": SALT_LEVEL_STRIDE,
            "formula": "SALT_BASE + level * SALT_LEVEL_STRIDE + index",
            "prior_ranges_for_this_mechanism": {
                "v5_v7_dev": "EXPERIMENT_SEED + 1000 + level*100 + index, index < 12 -> [20261907, 20262218]",
                "a3_synthetic_population": "same formula with index < 400 -> up to 20262606",
                "v4_scout": "adds 100000 -> ~20362000",
            },
        },
        "protocol": {
            "n_families_per_level": n_families,
            "development_families": f"0..{n_families // 2 - 1}",
            "evaluation_families": f"{n_families // 2}..{n_families - 1}",
            "top_k_rules": 3,
            "models": "logistic (difference mode) + depth-3 tree (sklearn) fitted on development",
            "permutations": n_perm,
            "seed": SEED,
            "guide_policy": "SHARED_CONSTANT",
            "v2_candidate_version": V2_GENERATOR_VERSION,
        },
        "population": population,
        "summary": summary,
        "cells": cells,
        "elapsed_seconds": elapsed,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "adversary_audit.json").write_text(json.dumps(_clean(payload), indent=1))
    (out_dir / "twin_invariance.json").write_text(
        json.dumps(_clean({"_disclaimer": payload["_disclaimer"], "cells": twins}), indent=1)
    )
    (out_dir / "frozen_adversaries.json").write_text(json.dumps(_clean(frozen_all), indent=1))
    print(json.dumps(_clean(summary), indent=1))
    print(f"elapsed {elapsed:.1f}s")
    return payload


def summarise(cells: list[dict[str, Any]], twins: list[dict[str, Any]]) -> dict[str, Any]:
    table: dict[str, Any] = {}
    for c in cells:
        e = c["eval"]
        best = next(a for a in e["per_adversary"] if a["name"] == e["best"])
        table[f"{c['generator']}:L{c['level']}:{c['surface']}"] = {
            "best": e["best"],
            "accuracy": round(e["best_accuracy"], 4),
            "cp_decided": [round(best["cp_lower"], 4), round(best["cp_upper"], 4)],
            "decided_n": best["decided_n"],
            "abstain_rate": round(best["abstain_rate"], 4),
            "holm_p": best["holm_p"],
            "null_mean_max": round(e["frozen_family_permutation_null"]["null_mean_max"], 4),
            "null_q95_max": round(e["frozen_family_permutation_null"]["null_q95_max"], 4),
            "null_p": e["frozen_family_permutation_null"]["p_value_max"],
            "reaches_0.60_cp_lower_above_0.5": any(
                a["reaches_0.60_with_cp_lower_above_0.5"] for a in e["per_adversary"]
            ),
            "family_hits": best["family_hit_histogram"],
        }
    any_surface = {}
    for c in cells:
        key = f"{c['generator']}:L{c['level']}"
        e = c["eval"]
        hit = any(a["reaches_0.60_with_cp_lower_above_0.5"] for a in e["per_adversary"])
        any_surface.setdefault(key, {"surfaces_reaching_0.60_cp_lower_above_0.5": [], "max_eval_accuracy": 0.0})
        if hit:
            any_surface[key]["surfaces_reaching_0.60_cp_lower_above_0.5"].append(c["surface"])
        any_surface[key]["max_eval_accuracy"] = max(any_surface[key]["max_eval_accuracy"], e["best_accuracy"])
    twin_summary: dict[str, Any] = {}
    for t in twins:
        key = f"{t['generator']}:L{t['level']}:{t['surface']}"
        feats = t["features"]
        twin_summary[key] = {
            "n_twin_pairs": t["n_twin_pairs"],
            "pinned_features": sorted(n for n, f in feats.items() if f["pinned"]),
            "unpinned_features": {
                n: {
                    "identical": round(f["identical_fraction"], 4),
                    "reversed": round(f["reversed_fraction"], 4),
                    "twin_acc": {k: round(v, 4) for k, v in f["twin_accuracy"].items()},
                }
                for n, f in feats.items()
                if not f["pinned"]
            },
        }
    return {"per_cell": table, "per_level": any_surface, "twin_invariance": twin_summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-families", type=int, default=N_FAMILIES)
    parser.add_argument("--generators", nargs="+", default=list(GENERATORS), choices=list(GENERATORS))
    parser.add_argument("--levels", nargs="+", type=int, default=list(LEVELS))
    parser.add_argument("--surfaces", nargs="+", default=list(SURFACES), choices=list(SURFACES))
    parser.add_argument("--permutations", type=int, default=2000)
    parser.add_argument("--no-validate", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    if args.n_families % 2:
        raise SystemExit("--n-families must be even (half development, half evaluation)")
    run(
        n_families=args.n_families,
        generators=tuple(args.generators),
        levels=tuple(args.levels),
        surfaces=tuple(args.surfaces),
        n_perm=args.permutations,
        validate=not args.no_validate,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
