"""Verification of the rebuilt HC-V0.6 anchor bank, run against the committed artefact.

Four things are measured here and nothing is asserted:

1. **Bijection** -- ``invert(R.render(s)) == R_A.render(s)`` for every ``R_ONLY`` arm at every
   anchor in the bank, with every failing pretty-print shape and every refusal reported.
2. **Parity** -- ``check_projection_parity`` for ``R_A``/``R_B`` and ``R_A``/``R_A_PRIME`` under
   ``R_ONLY``, plus the negative control that ``R_ABLATED`` *fails* ``R_ONLY`` parity.
3. **Leakage on the rendered bytes** -- the surface manual section 29 names.  The bank's own check
   scanned ``solver_visible.goals_pp``; this scans the whole rendered payload of every arm, and
   the assembled prompt, for the theorem's own recorded tactics.
4. **Prompt length** -- character counts per arm, a declared confound that must be in the record.

Branching (that two successful steps from one anchored live state give distinct children without
mutating the parent) is measured by ``branch_check.py`` in this directory, because it needs Lean.

Run:  .venv/bin/python -m research.phase10.bank_audit.audit_bank
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from arena.trajectory.anchor import Anchor, AnchorBank
from arena.trajectory.representation import (
    ARMS,
    BIJECTIVE_ARM_IDS,
    UnrenderableStateError,
    bijection_report,
    project_arm,
)
from arena.trajectory.solver import build_prompt
from arena.trajectory.state_identity import (
    BackendStateEnvelope,
    InterventionClass,
    check_projection_parity,
)

DEFAULT_BANK = Path("artifacts/trajectory/hc_v0_6_anchor_bank.json")
DEFAULT_OUT = Path("research/phase10/bank_audit/out/bank_audit.json")

#: The same floor the bank builder and the assay use, so the three figures are comparable.
MIN_NEEDLE = 6


def envelope_of(anchor: Anchor) -> BackendStateEnvelope:
    """The envelope the assay builds, with the derivation handle standing in for the live one."""

    return anchor.solver_visible.envelope(
        state_id=anchor.derivation_state_id or "0",
        session_id="bank-audit",
        problem_id=anchor.oracle.problem_id,
    )


def pp_shape(pp: str) -> dict[str, Any]:
    """Enough of a state's shape to identify a failing family without quoting the state."""

    return {
        "chars": len(pp),
        "lines": pp.count("\n") + 1,
        "goal_markers": pp.count("⊢"),
        "blank_line_blocks": len(pp.split("\n\n")),
        "has_crlf": "\r" in pp,
        "trailing_newline": pp.endswith("\n"),
    }


def audit_bijection(anchors: list[Anchor]) -> dict[str, Any]:
    envelopes = [envelope_of(anchor) for anchor in anchors]
    by_id = {envelope.state_id: anchor for envelope, anchor in zip(envelopes, anchors, strict=True)}
    out: dict[str, Any] = {}
    for arm_id in (*BIJECTIVE_ARM_IDS, "R_ABLATED"):
        report = bijection_report(ARMS[arm_id], envelopes)
        summary = report.to_dict()
        summary["failures"] = summary["failures"][:10]
        summary["failure_details"] = dict(Counter(check.detail for check in report.failures))
        summary["failing_pp_shapes"] = [
            pp_shape(by_id[check.state_id].solver_visible.goals_pp)
            for check in report.failures[:10]
        ]
        summary["refusal_detail"] = [
            {
                "reason": check.refused.value if check.refused else None,
                "detail": check.detail,
                "shape": pp_shape(by_id[check.state_id].solver_visible.goals_pp),
            }
            for check in report.refusals
        ]
        out[arm_id] = summary
    return out


def audit_usability(anchors: list[Anchor]) -> dict[str, Any]:
    """How many anchors every arm can render.  The intersection is the real sample size."""

    refused: dict[str, list[dict[str, str]]] = {arm_id: [] for arm_id in ARMS}
    blocked: set[str] = set()
    for anchor in anchors:
        envelope = envelope_of(anchor)
        for arm_id, renderer in ARMS.items():
            try:
                renderer.render(envelope)
            except UnrenderableStateError as error:
                refused[arm_id].append(
                    {
                        "anchor_id": anchor.anchor_id,
                        "reason": error.reason.value,
                        "detail": error.detail,
                    }
                )
                blocked.add(anchor.anchor_id)
    usable = [anchor for anchor in anchors if anchor.anchor_id not in blocked]
    return {
        "n_anchors": len(anchors),
        "refusals_by_arm": {arm_id: len(items) for arm_id, items in refused.items()},
        "refusal_reasons_by_arm": {
            arm_id: dict(Counter(item["reason"] for item in items))
            for arm_id, items in refused.items()
            if items
        },
        "refusal_detail": {arm_id: items for arm_id, items in refused.items() if items},
        "unusable_by_any_arm": len(blocked),
        "usable_by_all_arms": len(usable),
        "usable_theorems": len({anchor.oracle.problem_id for anchor in usable}),
        "usable_files": len({anchor.cluster.file_path for anchor in usable}),
    }


def audit_parity(anchors: list[Anchor]) -> dict[str, Any]:
    pairs = {
        "R_A_vs_R_A_PRIME": ("R_A_PRIME", InterventionClass.R_ONLY),
        "R_A_vs_R_B": ("R_B", InterventionClass.R_ONLY),
        "R_A_vs_R_ABLATED_as_R_ONLY": ("R_ABLATED", InterventionClass.R_ONLY),
        "R_A_vs_R_ABLATED_as_P_CHANGE": ("R_ABLATED", InterventionClass.P_CHANGE),
    }
    tallies: dict[str, dict[str, Any]] = {
        name: {
            "n": 0,
            "parity_holds": 0,
            "bytes_differ": 0,
            "admissible": 0,
            "derived_classes": Counter(),
            "explanations": Counter(),
        }
        for name in pairs
    }
    for anchor in anchors:
        envelope = envelope_of(anchor)
        left = project_arm(ARMS["R_A"], envelope)
        for name, (arm_id, declared) in pairs.items():
            right = project_arm(ARMS[arm_id], envelope)
            result = check_projection_parity(left.identity, right.identity, declared)
            tally = tallies[name]
            tally["n"] += 1
            tally["parity_holds"] += int(result.parity_holds)
            tally["bytes_differ"] += int(result.bytes_differ)
            tally["admissible"] += int(result.admissible)
            tally["derived_classes"][right.identity.intervention_class] += 1
            tally["explanations"][result.explanation[:80]] += 1
    for tally in tallies.values():
        tally["derived_classes"] = dict(tally["derived_classes"])
        tally["explanations"] = dict(tally["explanations"])
    return tallies


def audit_leakage(anchors: list[Anchor]) -> dict[str, Any]:
    """Scan the bytes the model will actually read for the theorem's own recorded tactics."""

    hits: list[dict[str, Any]] = []
    scanned = 0
    needles_total = 0
    needles_skipped_short = 0
    for anchor in anchors:
        envelope = envelope_of(anchor)
        needles = [tactic.strip() for tactic in anchor.oracle.reference_tactics]
        needles_skipped_short += sum(1 for needle in needles if len(needle) < MIN_NEEDLE)
        needles = [needle for needle in needles if len(needle) >= MIN_NEEDLE]
        for arm_id, renderer in ARMS.items():
            try:
                rendered = dict(renderer.render(envelope))
            except UnrenderableStateError:
                continue
            payload = json.dumps(rendered, ensure_ascii=False)
            prompt = build_prompt(str(rendered["goals_pp"]))
            scanned += 1
            needles_total += len(needles)
            for needle in needles:
                where = [
                    surface
                    for surface, text in (("rendered_payload", payload), ("prompt", prompt))
                    if needle in text
                ]
                if where:
                    hits.append(
                        {
                            "anchor_id": anchor.anchor_id,
                            "arm": arm_id,
                            "needle": needle[:80],
                            "surfaces": where,
                        }
                    )
    return {
        "surfaces_scanned": scanned,
        "arms": sorted(ARMS),
        "min_needle_chars": MIN_NEEDLE,
        "needle_comparisons": needles_total,
        "needles_below_floor": needles_skipped_short,
        "hits": len(hits),
        "hit_detail": hits[:20],
    }


def audit_lengths(anchors: list[Anchor]) -> dict[str, Any]:
    """Rendered goal-text and full-prompt character counts per arm, against ``R_A``."""

    per_arm: dict[str, list[int]] = {arm_id: [] for arm_id in ARMS}
    per_arm_prompt: dict[str, list[int]] = {arm_id: [] for arm_id in ARMS}
    ratios: dict[str, list[float]] = {arm_id: [] for arm_id in ARMS}
    prompt_ratios: dict[str, list[float]] = {arm_id: [] for arm_id in ARMS}
    for anchor in anchors:
        envelope = envelope_of(anchor)
        texts: dict[str, str] = {}
        for arm_id, renderer in ARMS.items():
            try:
                texts[arm_id] = str(dict(renderer.render(envelope))["goals_pp"])
            except UnrenderableStateError:
                continue
        if "R_A" not in texts:
            continue
        base = len(texts["R_A"])
        base_prompt = len(build_prompt(texts["R_A"]))
        for arm_id, text in texts.items():
            per_arm[arm_id].append(len(text))
            per_arm_prompt[arm_id].append(len(build_prompt(text)))
            ratios[arm_id].append(len(text) / base)
            prompt_ratios[arm_id].append(len(build_prompt(text)) / base_prompt)

    def describe(values: list[int]) -> dict[str, Any]:
        return {
            "n": len(values),
            "median": statistics.median(values),
            "mean": round(statistics.fmean(values), 1),
            "min": min(values),
            "max": max(values),
            "total": sum(values),
        }

    return {
        arm_id: {
            "goals_pp_chars": describe(per_arm[arm_id]),
            "prompt_chars": describe(per_arm_prompt[arm_id]),
            "median_pct_change_vs_R_A": round(100 * (statistics.median(ratios[arm_id]) - 1), 2),
            "pct_change_range_vs_R_A": [
                round(100 * (min(ratios[arm_id]) - 1), 2),
                round(100 * (max(ratios[arm_id]) - 1), 2),
            ],
            "median_prompt_pct_change_vs_R_A": round(
                100 * (statistics.median(prompt_ratios[arm_id]) - 1), 2
            ),
            "total_pct_change_vs_R_A": round(
                100 * (sum(per_arm[arm_id]) / sum(per_arm["R_A"]) - 1), 2
            ),
        }
        for arm_id in per_arm
    }


def audit_clusters(anchors: list[Anchor]) -> dict[str, Any]:
    per_theorem = Counter(anchor.oracle.problem_id for anchor in anchors)
    per_file = Counter(anchor.cluster.file_path for anchor in anchors)
    theorems_in_file: dict[str, set[str]] = {}
    for anchor in anchors:
        theorems_in_file.setdefault(anchor.cluster.file_path, set()).add(anchor.oracle.problem_id)
    return {
        "anchors": len(anchors),
        "theorems": len(per_theorem),
        "files": len(per_file),
        "anchors_per_theorem": dict(sorted(Counter(per_theorem.values()).items())),
        "anchors_per_file": dict(sorted(Counter(per_file.values()).items())),
        "theorems_per_file": dict(
            sorted(Counter(len(names) for names in theorems_in_file.values()).items())
        ),
        "depth_class": dict(Counter(anchor.sampling.depth_class.value for anchor in anchors)),
        "prefix_length": dict(
            sorted(Counter(anchor.sampling.prefix_length for anchor in anchors).items())
        ),
        "n_goals": dict(
            sorted(Counter(anchor.solver_visible.n_goals for anchor in anchors).items())
        ),
        "distinct_pp": len({anchor.solver_visible.goals_pp for anchor in anchors}),
        "distinct_reelaboration_keys": len({anchor.reelaboration_key for anchor in anchors}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    started = time.monotonic()
    bank = AnchorBank.load(args.bank)
    anchors = list(bank.anchors)
    report = {
        "bank": str(args.bank),
        "content_hash": bank.content_hash,
        "n_anchors": len(anchors),
        "clusters": audit_clusters(anchors),
        "usability": audit_usability(anchors),
        "bijection": audit_bijection(anchors),
        "parity": audit_parity(anchors),
        "leakage_on_rendered_bytes": audit_leakage(anchors),
        "prompt_lengths": audit_lengths(anchors),
    }
    report["wall_s"] = round(time.monotonic() - started, 2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
