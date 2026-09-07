"""A4 audit step 4: clustering, pseudo-replication, effective n, and probe provenance.

READ-ONLY. No model calls. Answers Part F Q11-Q14.
Writes research/audit/a4_power/clustering_provenance.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from arena.experiments import fitness_v5 as v5

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
HERE = Path(__file__).resolve().parent
OUT = HERE / "clustering_provenance.json"


def main() -> None:
    art = json.loads(ART.read_text())
    items = json.loads((HERE / "paired_items.json").read_text())
    probes = v5.build_dev_pool(ROOT)

    # --- Q11: exact N per mechanism x level, by arm
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in art["rows"]:
        counts[f"{r['mechanism']}|L{r['level']}"][r["variant"]] += 1
    n_table = {
        k: {
            "by_variant": dict(sorted(v.items())),
            "total_rows": sum(v.values()),
            "POSITIVE_n_used_for_accuracy_and_the_gate": v["ORIGINAL"] + v["COUNTERFACTUAL"],
        }
        for k, v in sorted(counts.items())
    }

    # --- Q12: what do rows share?
    prov: dict[str, dict] = {}
    by_cell = defaultdict(list)
    for p in probes:
        by_cell[(p.mechanism, p.level)].append(p)
    for (mech, lvl), ps in sorted(by_cell.items()):
        pos = [p for p in ps if p.variant.value in v5.POSITIVE_VARIANTS]
        fams = defaultdict(list)
        for p in pos:
            fams[p.family_id].append(p)
        # source identity behind each family
        src = []
        for fid in fams:
            tail = fid.split(":")[-1]
            src.append(tail)
        oracle_keys: Counter = Counter()
        theorems: Counter = Counter()
        for p in pos:
            o = getattr(p, "oracle", None) or {}
            if isinstance(o, dict):
                oracle_keys.update(o.keys())
                if "theorem_id" in o:
                    theorems[str(o["theorem_id"])] += 1
        prov[f"{mech}|L{lvl}"] = {
            "positive_items": len(pos),
            "families": len(fams),
            "items_per_family": sorted(Counter(len(v) for v in fams.values()).items()),
            "variants_per_family": sorted(
                {tuple(sorted(x.variant.value for x in v)) for v in fams.values()}
            )[0],
            "family_source_ids_sample": sorted(src)[:3],
            "distinct_generator_templates": 1,
            "generator": (
                "arena.experiments.fitness_v5._formal_family over a real theorem pool"
                if mech == "formal_expression_depth"
                else "arena.experiments.fitness_v5._synthetic_family, one template per "
                "(mechanism, level), families differ only by an integer salt"
            ),
            "distinct_theorem_ids": len(theorems) if theorems else None,
            "theorem_id_multiplicity": sorted(theorems.values(), reverse=True) if theorems else None,
        }

    # --- Q13/Q14: constancy within family for EVERY rule, and effective n
    constancy: dict[str, dict] = {}
    for key, cell in sorted(items.items()):
        fams = defaultdict(list)
        for i in cell["items"]:
            fams[i["family_id"]].append(i)
        rules = list(cell["items"][0]["rule_correct"])
        per_rule = {}
        for rule in rules:
            const = sum(1 for v in fams.values() if len({x["rule_correct"][rule] for x in v}) == 1)
            per_rule[rule] = f"{const}/{len(fams)}"
        solver_const = sum(
            1 for v in fams.values() if len({x["solver_correct"] for x in v}) == 1
        )
        constancy[key] = {
            "families": len(fams),
            "rules_constant_within_family": per_rule,
            "all_rules_constant_within_every_family": all(
                v == f"{len(fams)}/{len(fams)}" for v in per_rule.values()
            ),
            "solver_constant_within_family": f"{solver_const}/{len(fams)}",
            "solver_within_family_agreement_rate": solver_const / len(fams),
        }

    unc = json.loads((HERE / "margin_uncertainty.json").read_text())["cells"]
    eff = {
        k: {
            "nominal_n": v["n_items"],
            "independent_units_families": v["n_families"],
            "design_effect": v["design_effect"],
            "effective_n": v["effective_n"],
            "icc_of_difference": v["icc_of_difference_within_family"],
        }
        for k, v in unc.items()
    }

    out = {
        "Q11_exact_N_per_mechanism_level": n_table,
        "Q12_provenance_and_shared_structure": prov,
        "Q12_within_family_constancy": constancy,
        "Q13_Q14_effective_sample_size": eff,
    }
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))

    print("Q11 — EXACT N PER MECHANISM x LEVEL")
    for k, v in n_table.items():
        print(f"  {k:<32} rows={v['total_rows']:>3}  positives(gate n)="
              f"{v['POSITIVE_n_used_for_accuracy_and_the_gate']:>3}  {v['by_variant']}")
    print()
    print("Q12 — SHARED STRUCTURE (probe provenance)")
    for k, v in prov.items():
        print(f"  {k:<32} pos={v['positive_items']} fam={v['families']} "
              f"items/fam={v['items_per_family']} variants={v['variants_per_family']} "
              f"templates={v['distinct_generator_templates']} "
              f"theorems={v['distinct_theorem_ids']} mult={v['theorem_id_multiplicity']}")
    print()
    print("Q12 — ARE THE SHORTCUT RULES CONSTANT WITHIN A FAMILY?")
    for k, v in constancy.items():
        print(f"  {k:<32} all_rules_constant={v['all_rules_constant_within_every_family']}  "
              f"solver_constant={v['solver_constant_within_family']}")
    print("  per-rule detail, transitive_dependency|L3:")
    for rule, s in constancy["transitive_dependency|L3"]["rules_constant_within_family"].items():
        print(f"      {rule:<28} constant in {s} families")
    print()
    print("Q13/Q14 — EFFECTIVE SAMPLE SIZE")
    print(f"{'cell':<32}{'nominal':>9}{'families':>10}{'deff':>8}{'n_eff':>8}{'ICC':>8}")
    for k, v in eff.items():
        d = v["design_effect"]
        ne = v["effective_n"]
        ic = v["icc_of_difference"]
        f = lambda x: "  n/a" if x != x else f"{x:.2f}"  # noqa: E731
        g = lambda x: "  n/a" if x != x else f"{x:.1f}"  # noqa: E731
        print(f"{k:<32}{v['nominal_n']:>9}{v['independent_units_families']:>10}"
              f"{f(d):>8}{g(ne):>8}{f(ic):>8}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
