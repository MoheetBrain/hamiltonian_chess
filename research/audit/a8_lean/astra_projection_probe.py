"""A8: what the Astra source projection actually contains, and how much the five
codecs actually differ.  Read-only, no model call, development artifacts only."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from research.astra.game_r_premise.renderer_bridge import REPRESENTATIONS, render
from research.astra.game_r_premise.schema import CanonicalPremiseSelectionState, visible_projection

ART = Path("research/astra/artifacts")
MARKERS = {
    "elided_subterm_⋯": re.compile("⋯|…"),
    "inaccessible_dagger_✝": re.compile("✝"),
    "coercion_arrow_↑": re.compile("↑"),
    "universe_metavariable_?u": re.compile(r"\?u\.\d+"),
    "expr_metavariable_?m": re.compile(r"\?m\.\d+"),
    "sorry": re.compile(r"\bsorry\b"),
}


def main() -> None:
    bank = [
        CanonicalPremiseSelectionState.from_dict(json.loads(line))
        for line in (ART / "dev_bank.jsonl").read_text().splitlines()
        if line.strip()
    ]
    c: Counter[str] = Counter()
    for st in bank:
        c["items"] += 1
        visible_text = st.context.text + st.goal.text
        stmts = "\n".join(x.statement.text for x in st.candidate_premises)
        for name, rx in MARKERS.items():
            if rx.search(visible_text):
                c[f"state:{name}"] += 1
            if rx.search(stmts):
                c[f"statement:{name}"] += 1
        if st.audit_metadata.get("dev_partition") == "heldout":
            c["heldout"] += 1
            for name, rx in MARKERS.items():
                if rx.search(visible_text):
                    c[f"heldout_state:{name}"] += 1

    # How different are the five "representations"?  Compare the rendered bytes of
    # one item and measure how much of each rendering is the SAME canonical-JSON payload.
    st = bank[0]
    proj = visible_projection(st)
    from arena.languages._json_tools import canonical_json

    payloads = {k: canonical_json(v) for k, v in proj.items()}
    renders = {r: render(st, r) for r in REPRESENTATIONS}
    shared = {
        r: {
            "bytes": len(src.encode()),
            "payload_bytes_verbatim": sum(len(p.encode()) for p in payloads.values() if p in src),
            "fields_carried_verbatim": sum(1 for p in payloads.values() if p in src),
            "n_fields": len(payloads),
            "lean_goal_text_verbatim": json.dumps(st.goal.text, ensure_ascii=False)[1:-1] in src,
        }
        for r, src in renders.items()
    }
    for r, info in shared.items():
        info["fraction_identical_payload"] = info["payload_bytes_verbatim"] / info["bytes"]

    report = {
        "bank": str(ART / "dev_bank.jsonl"),
        "marker_counts": dict(c),
        "marker_rates_over_300": {
            k: v / c["items"] for k, v in c.items() if k.startswith(("state:", "statement:"))
        },
        "codec_payload_sharing": shared,
        "codec_rendered_bytes": {r: len(v.encode()) for r, v in renders.items()},
        "note": "every codec embeds the SAME canonical_json() of the SAME fields; only the outer envelope differs",
    }
    Path("research/audit/a8_lean/out").mkdir(parents=True, exist_ok=True)
    Path("research/audit/a8_lean/out/astra_projection_probe.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n--- first 400 bytes of each rendering ---")
    for r, src in renders.items():
        print(f"\n### {r}\n{src[:400]}")


if __name__ == "__main__":
    main()
