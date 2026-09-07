"""A8: establish, from the code, WHY alpha-renaming and independent-context
permutation are unsupported on all 300 admitted Astra rows, and verify that all
five codecs carry the mathematical content byte-verbatim."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from research.astra.game_r_premise import invariance as inv
from research.astra.game_r_premise.renderer_bridge import REPRESENTATIONS, render
from research.astra.game_r_premise.schema import CanonicalPremiseSelectionState

ART = Path("research/astra/artifacts")


def main() -> None:
    bank = [
        CanonicalPremiseSelectionState.from_dict(json.loads(line))
        for line in (ART / "dev_bank.jsonl").read_text().splitlines()
        if line.strip()
    ]
    reasons: Counter[str] = Counter()
    line_fail: Counter[str] = Counter()
    n_lines = 0
    n_lines_matching = 0
    for st in bank:
        try:
            inv.alpha_rename_locals(st)
            reasons["SUPPORTED"] += 1
        except inv.UnsupportedTransformation as e:
            reasons[str(e)] += 1
        for line in st.context.text.splitlines(keepends=True):
            n_lines += 1
            if inv._LOCAL.fullmatch(line):
                n_lines_matching += 1
            else:
                # classify the first thing that makes the line non-conforming
                if line.startswith("case "):
                    line_fail["case label line"] += 1
                elif "✝" in line:
                    line_fail["inaccessible ✝ name (not a legal identifier)"] += 1
                elif re.search(r" : (Nat|Int)\n", line):
                    line_fail["Nat/Int but non-conforming binder spelling"] += 1
                elif " : " in line:
                    line_fail["typed local whose type is not Nat/Int"] += 1
                else:
                    line_fail["continuation / wrapped / other"] += 1

    # verbatim carriage of the mathematical content by every codec
    verbatim = Counter()
    for st in bank:
        pieces = [st.context.text, st.goal.text] + [c.name for c in st.candidate_premises] + [
            c.statement.text for c in st.candidate_premises
        ]
        for rep in REPRESENTATIONS:
            src = render(st, rep)
            ok = all(json.dumps(p, ensure_ascii=False)[1:-1] in src for p in pieces if p.strip())
            verbatim[f"{rep}:{'all_verbatim' if ok else 'ALTERED'}"] += 1

    report = {
        "alpha_rename_outcome_over_300": dict(reasons),
        "gate": "research/astra/game_r_premise/invariance.py:31 _LOCAL = "
                r"'([A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z_][A-Za-z0-9_]*)*) : (Nat|Int)\n'"
                " -- applied with re.fullmatch to EVERY context line (invariance.py:46)",
        "context_lines_total": n_lines,
        "context_lines_matching_gate": n_lines_matching,
        "context_line_nonconformance_reasons": dict(line_fail.most_common()),
        "codec_content_verbatim": dict(verbatim),
        "conclusion": "the metamorphic fragment is a binder-free Nat/Int fragment; real mathlib "
                      "contexts are type-universe/instance contexts, so the gate rejects the "
                      "first context line of every admitted row",
    }
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/astra_invariance_cause.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
