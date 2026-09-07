"""Is the winning premise-selection design PORTABLE to the structured
(obfuscatable) HML_V3 canonical corpus?

The LeanDojo trace cannot be identifier-obfuscated without re-running Lean; the
HML_V3 elaborated-Expr corpus can (transcribe() keeps names in .value).  So the
question that decides whether a memorisation control is available is: do the
1,150 structured transitions group into theorems with enough cited premises to
build same-proof distractor pools?

Read-only: the donor corpus is streamed from HML_V3 and never copied.

Run:  python -m research.environments.measure_structured_corpus
"""

from __future__ import annotations

import glob
import gzip
import json
from collections import Counter, defaultdict

from research.environments import common as C


def main() -> None:
    paths = sorted(glob.glob(C.HMLV3_CORPUS_GLOB))
    rows = 0
    per_theorem_steps: Counter = Counter()
    per_theorem_premises: dict[str, set] = defaultdict(set)
    premise_counts: Counter = Counter()
    rows_with_premise: int = 0
    step_premises: list[tuple[str, set]] = []
    theorem_key_field = None
    for path in paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                rows += 1
                ref = record.get("source_specific_reference") or {}
                meta = record.get("corpus_metadata") or {}
                key = (
                    ref.get("theorem_id")
                    or ref.get("declaration_name")
                    or meta.get("theorem_id")
                    or meta.get("declaration")
                    or meta.get("source_file")
                )
                if theorem_key_field is None:
                    theorem_key_field = {
                        "source_specific_reference_keys": sorted(ref.keys()),
                        "corpus_metadata_keys": sorted(meta.keys()),
                    }
                action = record.get("action") or {}
                premises = action.get("external_premise_refs") or []
                names = set()
                for premise in premises:
                    name = (
                        premise.get("name")
                        if isinstance(premise, dict)
                        else str(premise)
                    )
                    if name:
                        names.add(name)
                if names:
                    rows_with_premise += 1
                for name in names:
                    premise_counts[name] += 1
                per_theorem_steps[key] += 1
                per_theorem_premises[key] |= names
                step_premises.append((key, names))
    pools = [len(v) for v in per_theorem_premises.values() if v]
    # The distractor pool for a step is the set of premises cited at OTHER
    # steps of the SAME theorem.  A theorem with a single traced step has an
    # EMPTY pool no matter how many premises that step cites, so the union
    # count above overstates feasibility badly.
    same_proof_ok = 0
    for key, names in step_premises:
        if not names:
            continue
        others = per_theorem_premises[key] - names
        if len(others) >= 3:
            same_proof_ok += 1
    report = {
        "source": C.HMLV3_CORPUS_GLOB,
        "parts": len(paths),
        "rows": rows,
        "rows_with_at_least_one_external_premise_ref": rows_with_premise,
        "field_shape_first_record": theorem_key_field,
        "distinct_theorem_keys": len(per_theorem_steps),
        "steps_per_theorem": {
            "max": max(per_theorem_steps.values()) if per_theorem_steps else 0,
            "mean": round(rows / len(per_theorem_steps), 3)
            if per_theorem_steps
            else 0,
            "theorems_with_ge2_steps": sum(
                1 for v in per_theorem_steps.values() if v >= 2
            ),
        },
        "distinct_premise_names": len(premise_counts),
        "same_proof_pool_feasibility": {
            "theorems_with_ge1_cited_premise": len(pools),
            "theorems_with_ge4_distinct_cited_premises": sum(
                1 for v in pools if v >= 4
            ),
            "steps_whose_OTHER_steps_supply_ge3_distinct_premises": same_proof_ok,
            "verdict": None,
        },
        "top_premises": C.summarise_counter(premise_counts, 15),
    }
    feasible = same_proof_ok
    report["same_proof_pool_feasibility"]["verdict"] = (
        "PORTABLE" if feasible >= 200 else
        "NOT PORTABLE: the structured corpus is essentially one traced step per "
        "theorem (mean %.2f steps/theorem), so same-proof distractor pools do "
        "not exist at usable scale." % (rows / len(per_theorem_steps))
    )
    print(C.write_json("structured_corpus_portability.json", report))
    print(json.dumps(report, indent=1, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
