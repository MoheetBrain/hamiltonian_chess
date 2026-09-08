"""Target 8: parser permissiveness, and what the tactic policy does with what gets through."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import emit  # noqa: E402

from arena.trajectory.lean_backend import TacticPolicy  # noqa: E402
from arena.trajectory.solver import parse_tactic_response  # noqa: E402
from arena.trajectory.task import decode_action  # noqa: E402

RESULTS: dict[str, Any] = {}
POLICY = TacticPolicy.record_only()

# (label, raw model output)
WIRE_CASES = [
    ("plain", '{"tactic": "rfl"}'),
    ("fenced", '```json\n{"tactic": "rfl"}\n```'),
    ("preamble", 'Here you go: {"tactic": "rfl"}'),
    ("two_objects", '{"tactic": "rfl"}{"tactic": "simp"}'),
    ("extra_key", '{"tactic": "rfl", "why": "because"}'),
    ("cyrillic_key", '{"taсtic": "rfl"}'),                    # U+0441 in 'tactic'
    ("fullwidth_key", '{"ｔactic": "rfl"}'),
    ("empty_tactic", '{"tactic": ""}'),
    ("whitespace_tactic", '{"tactic": "   \\n  "}'),
    ("null_tactic", '{"tactic": null}'),
    ("list_tactic", '{"tactic": ["rfl"]}'),
    ("nested", '{"tactic": {"tactic": "rfl"}}'),
    ("array_root", '[{"tactic": "rfl"}]'),
    ("bare_string", 'rfl'),
    ("bom", '﻿{"tactic": "rfl"}'),
    ("nbsp_around", ' {"tactic": "rfl"} '),
    ("escaped_sorry", '{"tactic": "\\u0073orry"}'),
    ("guillemet_sorry", '{"tactic": "«sorry»"}'),
    ("nested_sorry", '{"tactic": "exact (by sorry : True)"}'),
    ("first_alt_sorry", '{"tactic": "first | rfl | sorry"}'),
    ("all_goals_sorry", '{"tactic": "all_goals sorry"}'),
    ("sorryAx", '{"tactic": "exact @sorryAx _ _ true"}'),
    ("have_sorry", '{"tactic": "have h : True := by sorry"}'),
    ("zwsp_sorry", '{"tactic": "so\\u200brry"}'),
    ("sorry_comment", '{"tactic": "sorry -- close it"}'),
    ("semicolon_chain", '{"tactic": "intro h; exact h.symm; rfl"}'),
    ("seq_focus", '{"tactic": "constructor <;> simp <;> omega"}'),
    ("newline_tactic", '{"tactic": "rfl\\nexact foo"}'),
    ("nul_tactic", '{"tactic": "rfl\\u0000"}'),
    ("block_comment_open", '{"tactic": "rfl /- "}'),
    ("line_comment", '{"tactic": "-- nothing"}'),
    ("native_decide", '{"tactic": "native_decide"}'),
    ("decide", '{"tactic": "decide"}'),
    ("stop", '{"tactic": "stop"}'),
    ("admit", '{"tactic": "admit"}'),
    ("huge", '{"tactic": "%s"}' % ("simp;" * 500)),
]


def main() -> None:
    rows = []
    for label, raw in WIRE_CASES:
        parsed = parse_tactic_response(raw)
        row: dict[str, Any] = {
            "case": label,
            "parsed": parsed.tactic,
            "parse_detail": parsed.detail,
        }
        if parsed.tactic is not None:
            lowered, err = decode_action(parsed.tactic)
            row["decode"] = "OK" if lowered is not None else f"REFUSED: {err}"
            decision, reason = POLICY.classify(parsed.tactic)
            row["policy"] = decision.value
            row["policy_reason"] = reason[:90]
            row["head"] = POLICY.head_of(parsed.tactic)
        rows.append(row)
        print(row)

    got_through = [r for r in rows if r.get("policy") == "ALLOWED"]
    unsound_through = [
        r for r in got_through
        if any(tok in (r["parsed"] or "") for tok in ("sorry", "admit", "​"))
    ]
    RESULTS["cases"] = rows
    RESULTS["summary"] = {
        "wire_cases": len(rows),
        "reached_a_tactic": sum(1 for r in rows if r["parsed"] is not None),
        "allowed_by_default_policy": len(got_through),
        "sorry_like_strings_allowed_by_policy": [r["case"] for r in unsound_through],
        "refused_unsound": [r["case"] for r in rows if r.get("policy") == "REFUSED_UNSOUND"],
        "decode_refusals": [r["case"] for r in rows if str(r.get("decode", "")).startswith("REF")],
    }
    print("\nSUMMARY:", RESULTS["summary"])
    emit("parser", RESULTS)


if __name__ == "__main__":
    main()
