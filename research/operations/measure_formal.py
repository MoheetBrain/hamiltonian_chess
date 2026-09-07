"""Measure operation vocabularies on the FORMAL side.

Sources (all read-only, all local; no Lean, no network, no model call):
  A. lean_canonical_records.jsonl   -- 241,265 VERIFIED_FORMAL transitions.
       Carries BOTH `observed_action.effect_class` (8 computed classes) and
       `lean.raw_tactic`, so tactic head x effect class can be crossed at scale.
       Scanned by line-local regex (validated against full json.loads on a
       2,000-line prefix) to keep CPU cost low.
  B. LeanDojo Benchmark 4 v10, random/{val,test}.json -- a uniformly random
       theorem-level sample from the same pool as train. Used as the
       REPRESENTATIVE tactic distribution. Effect classes are recomputed here
       from the pretty-printed states using the rule recovered from (A).
  C. HML_V3 sealed corpus (1,150 transitions) -- spot-check only: confirm the
       row count and that no tactic name / effect class is stored.
  D. MicroMath lab v2 -- relation / stress probe taxonomy counts.

Run:  python -m research.operations.measure_formal
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter, defaultdict

from research.operations import paths as P

# ---------------------------------------------------------------------------
# A. lean_canonical_records.jsonl (241,265 rows)
# ---------------------------------------------------------------------------

_RE_EFFECT = re.compile(r'"effect_class":\s*"([A-Z_]+)"')
_RE_SIG = re.compile(r'"effect_signature":\s*"([^"]+)"')
_RE_TACTIC = re.compile(r'"raw_tactic":\s*"((?:[^"\\]|\\.)*)"')
_RE_SPLIT = re.compile(r'"lean_official_split":\s*"([a-z]+)"')


def tactic_head(text: str) -> str:
    """First token of a Lean tactic, with `<;>` / `·` / `try` peeled minimally."""
    t = text.strip()
    if not t:
        return "<empty>"
    t = t.lstrip("·• \t")
    m = re.match(r"([A-Za-z_][A-Za-z0-9_'!?.]*)", t)
    return m.group(1) if m else t.split()[0][:20]


def scan_lean241k(validate_n: int = 2000) -> dict:
    effects = Counter()
    heads = Counter()
    head_x_effect: dict[str, Counter] = defaultdict(Counter)
    sig_to_class: dict[str, Counter] = defaultdict(Counter)
    splits = Counter()
    n = 0
    mismatch = 0
    with P.LEAN_241K.open(encoding="utf-8") as fh:
        for line in fh:
            n += 1
            me = _RE_EFFECT.search(line)
            ms = _RE_SIG.search(line)
            mt = _RE_TACTIC.search(line)
            mp = _RE_SPLIT.search(line)
            eff = me.group(1) if me else "<none>"
            tac = json.loads('"' + mt.group(1) + '"') if mt else ""
            h = tactic_head(tac)
            effects[eff] += 1
            heads[h] += 1
            head_x_effect[h][eff] += 1
            if ms:
                sig_to_class[ms.group(1).split("|", 1)[1]][eff] += 1
            if mp:
                splits[mp.group(1)] += 1
            if n <= validate_n:
                r = json.loads(line)
                if (
                    r["observed_action"]["effect_class"] != eff
                    or r["lean"]["raw_tactic"] != tac
                ):
                    mismatch += 1
    return {
        "n_records": n,
        "regex_validation": {
            "lines_fully_parsed": min(validate_n, n),
            "mismatches": mismatch,
        },
        "official_splits": dict(splits),
        "effect_class": dict(effects.most_common()),
        "tactic_head_top60": dict(heads.most_common(60)),
        "distinct_tactic_heads": len(heads),
        "head_x_effect_top40": {
            h: dict(head_x_effect[h].most_common())
            for h, _ in heads.most_common(40)
        },
        "signature_tail_to_class": {
            k: dict(v) for k, v in sorted(sig_to_class.items())
        },
    }


# ---------------------------------------------------------------------------
# B. LeanDojo: representative tactic distribution + recomputed effect classes
# ---------------------------------------------------------------------------

_HYP = re.compile(r"^([^\s:⊢][^:]*?)\s:\s", re.MULTILINE)


def parse_state(s: str) -> tuple[int, str, set[str], dict[str, str]]:
    """(n_goals, focused_target, focused_hyp_names, focused_name->type)."""
    s = (s or "").strip()
    if not s or s == "no goals":
        return 0, "", set(), {}
    blocks = [b for b in s.split("\n\n") if b.strip()]
    n_goals = len(blocks)
    first = blocks[0]
    if "⊢" in first:
        ctx, target = first.split("⊢", 1)
    else:
        ctx, target = first, ""
    names: set[str] = set()
    typ: dict[str, str] = {}
    for line in ctx.split("\n"):
        if line.startswith("case "):
            continue
        if " : " not in line:
            continue
        lhs, rhs = line.split(" : ", 1)
        if lhs.startswith(" "):  # continuation of a wrapped type
            continue
        for nm in lhs.split():
            names.add(nm)
            typ[nm] = rhs.strip()
    return n_goals, target.strip(), names, typ


def classify_effect(before: str, after: str) -> tuple[str, str]:
    """Reproduce the 8-class Lean effect vocabulary from two states."""
    gb, tb, nb, typb = parse_state(before)
    ga, ta, na, typa = parse_state(after)
    dg = ga - gb
    added = na - nb
    removed = nb - na
    rebound = {n for n in (na & nb) if typa.get(n) != typb.get(n)}
    target_changed = ta != tb
    sig = (
        f"dg{dg}|T{int(target_changed)}|A{len(added)}"
        f"|R{len(removed)}|B{len(rebound)}"
    )
    return effect_class(ga, target_changed, len(added), len(removed), len(rebound)), sig


def effect_class(n_goals_after: int, T: bool, A: int, R: int, B: int) -> str:
    """The 8-class Lean effect rule, RECOVERED empirically.

    Recovered by tabulating `effect_signature` -> `effect_class` over all
    241,265 records of lean_canonical_records.jsonl: 198 of the 199 distinct
    signature tails map to exactly one class, and the single ambiguous tail
    (dg-1|T0|A0|R0|B0 -> CLOSE 593 / NO_VISIBLE_CHANGE 41) is resolved by
    n_goals_after == 0. See verify_effect_rule().
    """
    if n_goals_after == 0:
        return "CLOSE"
    if B:
        return "REWRITE_CONTEXT_AND_TARGET" if T else "REWRITE_CONTEXT"
    if A:
        return "INTRODUCE_AND_TRANSFORM" if T else "INTRODUCE"
    if R:
        return "ELIMINATE"
    return "TRANSFORM_TARGET" if T else "NO_VISIBLE_CHANGE"


def verify_effect_rule(sig_to_class: dict) -> dict:
    """Replay the recovered rule against every observed signature tail."""
    ok = bad = ambiguous = 0
    failures = []
    for tail, classes in sig_to_class.items():
        m = re.match(r"dg-?\d+\|T(\d)\|A(\d+)\|R(\d+)\|B(\d+)", tail)
        if not m:
            continue
        T, A, R, B = (int(x) for x in m.groups())
        if len(classes) > 1:
            ambiguous += 1
            continue
        got = effect_class(1, bool(T), A, R, B)
        want = next(iter(classes))
        if want == "CLOSE":       # not decidable from the tail alone
            continue
        if got == want:
            ok += 1
        else:
            bad += 1
            failures.append({"tail": tail, "expected": want, "got": got,
                             "n": sum(classes.values())})
    return {"signature_tails_reproduced": ok, "mismatched": bad,
            "ambiguous_tails_skipped": ambiguous, "failures": failures[:10]}


def scan_leandojo(files: list[str]) -> dict:
    heads = Counter()
    effects = Counter()
    effects_matched = Counter()   # goal-creating steps dropped, as in the 241k census
    heads_matched = Counter()
    dgs = Counter()
    head_x_effect: dict[str, Counter] = defaultdict(Counter)
    n_theorems = 0
    n_tactics = 0
    n_goal_creating = 0
    n_with_premise_annot = 0
    n_premise_refs = 0
    for fp in files:
        data = json.loads((P.LEANDOJO / fp).read_text())
        for th in data:
            n_theorems += 1
            for tt in th.get("traced_tactics") or []:
                n_tactics += 1
                h = tactic_head(tt.get("tactic", ""))
                heads[h] += 1
                cls, sig = classify_effect(
                    tt.get("state_before", ""), tt.get("state_after", "")
                )
                dg = int(sig.split("|", 1)[0][2:])
                dgs[dg] += 1
                if dg > 0:
                    n_goal_creating += 1
                else:
                    effects_matched[cls] += 1
                    heads_matched[h] += 1
                effects[cls] += 1
                head_x_effect[h][cls] += 1
                ann = tt.get("annotated_tactic")
                if ann and len(ann) > 1 and ann[1]:
                    n_with_premise_annot += 1
                    n_premise_refs += len(ann[1])
    return {
        "files": files,
        "n_theorems": n_theorems,
        "n_tactics": n_tactics,
        "distinct_tactic_heads": len(heads),
        "tactic_head_all": dict(heads.most_common()),
        "recomputed_effect_class": dict(effects.most_common()),
        "goal_creating_steps_excluded": n_goal_creating,
        "recomputed_effect_class_matched_to_241k_exclusion": dict(
            effects_matched.most_common()
        ),
        "tactic_head_matched_top40": dict(heads_matched.most_common(40)),
        "delta_goals_distribution": dict(sorted(dgs.items())),
        "head_x_effect_top40": {
            h: dict(head_x_effect[h].most_common())
            for h, _ in heads.most_common(40)
        },
        "premise_annotation": {
            "tactics_citing_at_least_one_premise": n_with_premise_annot,
            "total_premise_references": n_premise_refs,
        },
    }


# ---------------------------------------------------------------------------
# C. HML_V3 sealed 1,150 -- spot check only
# ---------------------------------------------------------------------------


def spotcheck_hmlv3_1150() -> dict:
    out = {}
    for stem in ("search_pool_v2", "sealed_final_v2"):
        n = 0
        tf = Counter()
        ec = Counter()
        for part in sorted(P.HMLV3_CORPUS.glob(f"{stem}.part-*.jsonl.gz")):
            with gzip.open(part, "rt", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    n += 1
                    r = json.loads(line)
                    cm = r.get("corpus_metadata", {})
                    tf[str(cm.get("tactic_family"))] += 1
                    ec[str(cm.get("recorded_effect_class"))] += 1
        out[stem] = {
            "rows": n,
            "tactic_family": dict(tf),
            "recorded_effect_class": dict(ec),
        }
    out["partition_a_total"] = (
        out["search_pool_v2"]["rows"] + out["sealed_final_v2"]["rows"]
    )
    return out


# ---------------------------------------------------------------------------
# D. MicroMath lab v2
# ---------------------------------------------------------------------------


def scan_micromath() -> dict:
    rel = Counter()
    stress = Counter()
    split_rel: dict[str, Counter] = defaultdict(Counter)
    n = 0
    for part in sorted(P.MICROMATH.glob("micro_*_v2.part-*.jsonl.gz")):
        split = part.name.split(".")[0]
        with gzip.open(part, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                n += 1
                r = json.loads(line)
                rel[r.get("relation", "?")] += 1
                stress[r.get("stress", "?")] += 1
                split_rel[split][r.get("relation", "?")] += 1
    return {
        "n_items": n,
        "relation": dict(rel.most_common()),
        "stress": dict(stress.most_common()),
        "by_split": {k: dict(v.most_common()) for k, v in split_rel.items()},
    }


def main() -> None:
    P.SCRATCH.mkdir(parents=True, exist_ok=True)
    out: dict = {}

    print("[1/4] micromath ...", flush=True)
    out["micromath_lab_v2"] = scan_micromath()
    print("   ", out["micromath_lab_v2"]["n_items"], out["micromath_lab_v2"]["relation"])

    print("[2/4] hmlv3 1150 spot-check ...", flush=True)
    out["hmlv3_1150_spotcheck"] = spotcheck_hmlv3_1150()
    print("   ", {k: v for k, v in out["hmlv3_1150_spotcheck"].items() if k != "partition_a_total"})

    print("[3/4] leandojo random val+test ...", flush=True)
    out["leandojo_random_val_test"] = scan_leandojo(
        ["random/val.json", "random/test.json"]
    )
    ld = out["leandojo_random_val_test"]
    print("   ", ld["n_theorems"], "theorems", ld["n_tactics"], "tactics",
          ld["distinct_tactic_heads"], "heads")
    print("   ", list(ld["tactic_head_all"].items())[:20])
    print("   ", ld["recomputed_effect_class"])

    print("[4/4] lean 241k census ...", flush=True)
    out["lean_canonical_241k"] = scan_lean241k()
    lc = out["lean_canonical_241k"]
    lc["effect_rule_verification"] = verify_effect_rule(lc["signature_tail_to_class"])
    print("    rule verification:", {k: v for k, v in lc["effect_rule_verification"].items() if k != "failures"})
    print("    failures:", lc["effect_rule_verification"]["failures"])
    print("   ", lc["n_records"], "records; regex validation", lc["regex_validation"])
    print("   ", lc["effect_class"])
    print("   ", list(lc["tactic_head_top60"].items())[:20])

    (P.SCRATCH / "measure_formal.json").write_text(json.dumps(out, indent=1))
    print("written", P.SCRATCH / "measure_formal.json")


if __name__ == "__main__":
    main()
