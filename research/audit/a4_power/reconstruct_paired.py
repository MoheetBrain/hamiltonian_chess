"""A4 audit step 1: reconstruct per-item PAIRED outcomes (solver vs best shortcut).

READ-ONLY. No model calls. Rebuilds the deterministic V7/V5 probe bank locally and
recomputes each of V5's seven shortcut rules per item, then joins to the solver's
per-row `correct` flags from the frozen artifact.

Writes research/audit/a4_power/paired_items.json
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from arena.experiments import fitness_v5 as v5
from arena.experiments import fitness_v7 as v7
from arena.canonical.schema import canonical_json

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/experiments/fitness_v7/development/result-qwen38-rvn_latest-bare.json"
OUT = Path(__file__).resolve().parent / "paired_items.json"


def shortcut_rules(p) -> dict[str, int]:
    """Byte-for-byte the seven rules from fitness_v5.shortcut_audit (v5:801-817)."""
    n0 = str(p.options[0].arguments[0].value)
    n1 = str(p.options[1].arguments[0].value)
    t = canonical_json(p.state.to_dict(include_display_identity=False))
    return {
        "always_first_option": 0,
        "always_second_option": 1,
        "first_mentioned_in_state": 0 if t.find(f'"{n0}"') <= t.find(f'"{n1}"') else 1,
        "last_mentioned_in_state": 0 if t.rfind(f'"{n0}"') >= t.rfind(f'"{n1}"') else 1,
        "more_frequent_in_state": 0 if t.count(f'"{n0}"') >= t.count(f'"{n1}"') else 1,
        "shorter_option_text": 0 if (len(n0), n0) <= (len(n1), n1) else 1,
        "alphabetically_first": 0 if n0 <= n1 else 1,
    }


def main() -> None:
    art = json.loads(ART.read_text())
    probes = v5.build_dev_pool(ROOT)
    pool_hash = v5.stable_hash([p.to_dict() for p in probes])
    assert pool_hash == art["dev_pool_hash"], (
        f"dev pool hash mismatch: rebuilt {pool_hash} vs artifact {art['dev_pool_hash']}"
    )

    by_probe = {p.probe_id: p for p in probes}
    # solver outcomes, positives only
    rows = [r for r in art["rows"] if r["variant"] in v5.POSITIVE_VARIANTS]

    cells: dict[str, dict] = {}
    for r in rows:
        key = f"{r['mechanism']}|L{r['level']}"
        p = by_probe[r["probe_id"]]
        assert p.mechanism == r["mechanism"] and p.level == r["level"]
        assert p.expected_index == r["expected_index"], "expected_index mismatch"
        preds = shortcut_rules(p)
        cells.setdefault(key, {"mechanism": r["mechanism"], "level": r["level"], "items": []})
        cells[key]["items"].append(
            {
                "probe_id": r["probe_id"],
                "family_id": r["family_id"],
                "variant": r["variant"],
                "expected_index": r["expected_index"],
                "solver_correct": bool(r["correct"]),
                "parsed_index": r["parsed_index"],
                "rule_correct": {k: int(v == p.expected_index) for k, v in preds.items()},
            }
        )

    # Recompute the audit exactly as v5 does, and verify against the artifact.
    for key, cell in sorted(cells.items()):
        items = cell["items"]
        n = len(items)
        cell["n"] = n
        cell["n_families"] = len(Counter(i["family_id"] for i in items))
        scores = {
            rule: sum(i["rule_correct"][rule] for i in items) / n
            for rule in items[0]["rule_correct"]
        }
        worst = max(scores, key=lambda r: abs(scores[r] - 0.5))
        worst_score = max(scores[worst], 1.0 - scores[worst])
        inverted = scores[worst] < 0.5
        cell["rule_scores"] = scores
        cell["best_shortcut_feature"] = worst
        cell["best_shortcut_accuracy"] = worst_score
        cell["best_shortcut_inverted"] = inverted
        cell["solver_accuracy"] = sum(i["solver_correct"] for i in items) / n
        # per-item best-shortcut correctness (with polarity applied)
        for i in items:
            rc = i["rule_correct"][worst]
            i["shortcut_correct"] = (1 - rc) if inverted else rc
        # verify against frozen artifact
        ref = art["shortcut_audit_by_level"][cell["mechanism"]][str(cell["level"])]
        assert abs(ref["best_shortcut_accuracy"] - worst_score) < 1e-12, (key, ref, worst_score)
        assert ref["best_shortcut_feature"] == worst, (key, ref["best_shortcut_feature"], worst)
        for rule, s in scores.items():
            assert abs(ref["scores"][rule] - s) < 1e-12, (key, rule)
        lad = next(
            L for L in art["mechanisms"][cell["mechanism"]]["ladder"] if L["level"] == cell["level"]
        )
        assert abs(lad["positive_accuracy"] - cell["solver_accuracy"]) < 1e-12, key
        # 2x2 discordance table (solver vs best shortcut, same items)
        a = sum(1 for i in items if i["solver_correct"] and i["shortcut_correct"])
        b = sum(1 for i in items if i["solver_correct"] and not i["shortcut_correct"])
        c = sum(1 for i in items if not i["solver_correct"] and i["shortcut_correct"])
        dd = sum(1 for i in items if not i["solver_correct"] and not i["shortcut_correct"])
        cell["table"] = {"both": a, "solver_only": b, "shortcut_only": c, "neither": dd}
        cell["margin"] = (b - c) / n
        # within-family agreement, for the clustering measurement
        fam = defaultdict(list)
        for i in items:
            fam[i["family_id"]].append(i)
        cell["family_sizes"] = sorted(Counter(len(v) for v in fam.values()).items())
        cell["family_solver_concordant"] = sum(
            1 for v in fam.values() if len({x["solver_correct"] for x in v}) == 1
        )
        cell["family_count"] = len(fam)

    OUT.write_text(json.dumps(cells, indent=1, sort_keys=True))
    print(f"dev_pool_hash VERIFIED: {pool_hash}")
    print(f"wrote {OUT} ({len(cells)} cells)")
    hdr = f"{'cell':<40}{'n':>4}{'fam':>5}{'solver':>8}{'short':>8}{'marg':>8}   {'a/b/c/d':>16}  feature"
    print(hdr)
    for key, cl in sorted(cells.items()):
        t = cl["table"]
        print(
            f"{key:<40}{cl['n']:>4}{cl['family_count']:>5}"
            f"{cl['solver_accuracy']:>8.4f}{cl['best_shortcut_accuracy']:>8.4f}"
            f"{cl['margin']:>8.4f}   "
            f"{t['both']:>3}/{t['solver_only']:>3}/{t['shortcut_only']:>3}/{t['neither']:>3}"
            f"  {cl['best_shortcut_feature']}{' (INV)' if cl['best_shortcut_inverted'] else ''}"
        )


if __name__ == "__main__":
    main()
