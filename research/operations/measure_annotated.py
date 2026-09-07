"""Measure operation frequencies in the human-annotated / hand-authored corpora.

Sources measured here (all read-only, all local):
  A. gold125_ontology_v1  -- 769 step records over 125 MATH trajectories.
                             Splits into Gold-25 (MATH-GOLD-001..025) and
                             Gold-125 (MATH-GOLD-026..125).
  B. gold_10              -- 23 hand-authored actions over 10 trivial problems.
  C. synthetic_math       -- 3,978 deterministically extracted transitions.

Run:  python -m research.operations.measure_annotated
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from research.operations import paths as P


def measure_gold125() -> dict:
    """Every s*.json under gold125_ontology_v1. Exact, no sampling."""
    files = sorted(P.GOLD125_ONTOLOGY.glob("MATH-GOLD-*/s*.json"))
    per_split: dict[str, Counter] = defaultdict(Counter)
    axes: dict[str, Counter] = defaultdict(Counter)
    observed = Counter()
    obs_to_core: dict[str, Counter] = defaultdict(Counter)
    core_to_obs: dict[str, Counter] = defaultdict(Counter)
    spans: dict[str, list[str]] = defaultdict(list)
    disagree = Counter()
    n = 0
    trajs = set()
    for f in files:
        r = json.loads(f.read_text())
        n += 1
        tid = r["trajectory_id"]
        trajs.add(tid)
        idx = int(tid.rsplit("-", 1)[1])
        split = "gold25" if idx <= 25 else "gold125_extension"
        core = r["core_operation"]
        per_split[split][core] += 1
        axes["core_operation"][core] += 1
        axes["reasoning_mode"][r["reasoning_mode"]] += 1
        w = r.get("warrant")
        axes["warrant"][w["type"] if isinstance(w, dict) else str(w)] += 1
        for k in (
            "knowledge_layer",
            "goal_effect",
            "scope_effect",
            "epistemic_effect",
            "atomicity",
            "uncertainty",
        ):
            axes[k][r.get(k)] += 1
        prov = r.get("provenance") or {}
        obs = prov.get("observed_operation")
        if obs:
            observed[obs] += 1
            obs_to_core[obs][core] += 1
            core_to_obs[core][obs] += 1
        if prov.get("disagreement"):
            disagree[str(prov["disagreement"])[:80]] += 1
        # structural richness: are the rich schema fields actually populated?
        axes["_has_preconditions"][bool(r.get("preconditions"))] += 1
        axes["_has_obligations_created"][bool(r.get("obligations_created"))] += 1
        axes["_has_obligations_discharged"][
            bool(r.get("obligations_discharged"))
        ] += 1
        axes["_has_dependencies"][bool(r.get("dependencies"))] += 1
        if len(spans[core]) < 4:
            spans[core].append(r.get("source_span", "")[:200])
    return {
        "n_step_records": n,
        "n_trajectories": len(trajs),
        "core_operation_by_split": {k: dict(v.most_common()) for k, v in per_split.items()},
        "axes": {k: dict(v.most_common()) for k, v in axes.items()},
        "observed_operation": dict(observed.most_common()),
        "observed_to_core": {k: dict(v) for k, v in obs_to_core.items()},
        "core_to_observed": {k: dict(v.most_common()) for k, v in core_to_obs.items()},
        "example_spans_by_core_operation": dict(spans),
        "disagreements": dict(disagree),
    }


def measure_gold10() -> dict:
    files = sorted(P.GOLD10.glob("G*.json"))
    ops = Counter()
    stages = Counter()
    warrants = Counter()
    hml_support = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    n = 0
    for f in files:
        d = json.loads(f.read_text())
        for a in d.get("actions", []):
            n += 1
            op = a.get("operation", "?")
            ops[op] += 1
            for s in a.get("reasoning_stages", []):
                stages[s] += 1
            w = a.get("warrant") or {}
            warrants[w.get("kind", "?")] += 1
            hml_support[a.get("hml_support", "?")] += 1
            if len(examples[op]) < 2:
                examples[op].append((w.get("description") or "")[:160])
    return {
        "n_files": len(files),
        "n_actions": n,
        "operations": dict(ops.most_common()),
        "reasoning_stage_coverage": dict(sorted(stages.items())),
        "warrant_kinds": dict(warrants.most_common()),
        "hml_support": dict(hml_support.most_common()),
        "examples": dict(examples),
    }


_OP_HEAD = re.compile(r"^([A-Z_]{3,})")


def measure_synthetic() -> dict:
    ops = Counter()
    mech = Counter()
    status = Counter()
    backend = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    n = 0
    with P.SYNTH_TRANSITIONS.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            act = r.get("action", "")
            m = _OP_HEAD.match(act)
            op = m.group(1) if m else "UNPARSED"
            ops[op] += 1
            mech[r.get("mechanisms", "?")] += 1
            status[r.get("status", "?")] += 1
            backend[str(r.get("backend", "?")).split("`")[0].strip()] += 1
            if len(examples[op]) < 3:
                examples[op].append(act[:140])
    return {
        "n_transitions": n,
        "operations": dict(ops.most_common()),
        "mechanisms": dict(mech.most_common()),
        "status": dict(status.most_common()),
        "backend": dict(backend.most_common(12)),
        "examples": dict(examples),
    }


def main() -> None:
    out = {
        "gold125_ontology_v1": measure_gold125(),
        "gold10": measure_gold10(),
        "synthetic_math": measure_synthetic(),
    }
    P.SCRATCH.mkdir(parents=True, exist_ok=True)
    (P.SCRATCH / "measure_annotated.json").write_text(json.dumps(out, indent=1))
    g = out["gold125_ontology_v1"]
    print(f"gold125_ontology_v1: {g['n_step_records']} steps / {g['n_trajectories']} trajectories")
    print(" core_operation:", g["axes"]["core_operation"])
    print(" splits:", {k: sum(v.values()) for k, v in g["core_operation_by_split"].items()})
    print(" n distinct observed_operation:", len(g["observed_operation"]))
    print(" rich-field population:", {k: v for k, v in g["axes"].items() if k.startswith("_has")})
    print()
    print("gold10:", out["gold10"]["n_actions"], "actions,", len(out["gold10"]["operations"]), "distinct ops")
    print(" ", out["gold10"]["operations"])
    print()
    s = out["synthetic_math"]
    print("synthetic_math:", s["n_transitions"], "transitions")
    print(" ", s["operations"])


if __name__ == "__main__":
    main()
