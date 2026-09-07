"""The informal / model-generated arm, via a CALIBRATED lexical proxy.

Step 1  Calibrate the cue lexicon on the 769 Gold-125/Gold-25 step records,
        where a human operation label exists for every span. Reports per-cue
        precision and recall against `core_operation`. These numbers are the
        licence (or the refusal of a licence) to read anything into step 2.

Step 2  Apply the SAME detector, unchanged, to:
          - HUMAN informal at scale: the 12,500 MATH reference solutions in
            prm800k/math_splits, segmented into sentence-like steps.
          - MODEL informal: PRM800K model completions, from phase1_train and
            phase2_test, split by the human step rating (+1 / 0 / -1).
          - HUMAN written step-by-step: PRM800K `human_completion` steps.

No model call, no network. Everything is regex over local text.

Run:  python -m research.operations.measure_informal_proxy
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict

from research.operations import cues
from research.operations import paths as P

SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\\$])")


def calibrate() -> dict:
    """Cue precision/recall against the 769 gold core_operation labels."""
    files = sorted(P.GOLD125_ONTOLOGY.glob("MATH-GOLD-*/s*.json"))
    gold = Counter()
    fired = Counter()
    hit = Counter()
    mode_of_fire: dict[str, Counter] = defaultdict(Counter)
    confusion: dict[str, Counter] = defaultdict(Counter)
    n = 0
    n_no_cue = 0
    examples_fp: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        r = json.loads(f.read_text())
        n += 1
        span = r.get("source_span", "")
        g = r["core_operation"]
        gold[g] += 1
        f_set = cues.fire(span)
        if not f_set:
            n_no_cue += 1
        for c in f_set:
            fired[c] += 1
            mode_of_fire[c][r["reasoning_mode"]] += 1
            confusion[c][g] += 1
            if c == g:
                hit[c] += 1
            elif len(examples_fp[c]) < 3:
                examples_fp[c].append({"gold": g, "span": span[:150]})
    table = {}
    for c in sorted(cues.CUES):
        fr = fired[c]
        gd = gold.get(c, 0)
        table[c] = {
            "calibratable": c not in cues.UNCALIBRATABLE,
            "gold_n": gd,
            "cue_fired_n": fr,
            "precision": round(hit[c] / fr, 3) if fr else None,
            "recall": round(hit[c] / gd, 3) if gd else None,
            "top_gold_labels_when_fired": dict(confusion[c].most_common(5)),
            "reasoning_mode_when_fired": dict(mode_of_fire[c].most_common(4)),
            "example_misses": examples_fp[c],
        }
    return {
        "n_spans": n,
        "spans_with_no_cue": n_no_cue,
        "gold_core_operation": dict(gold.most_common()),
        "per_cue": table,
    }


def _segment(text: str) -> list[str]:
    parts = [p.strip() for p in SENT.split(text or "") if p.strip()]
    return parts or ([text.strip()] if (text or "").strip() else [])


def scan_math_reference_solutions() -> dict:
    """Human-written MATH reference solutions (the same population Gold-125
    was drawn from), segmented into sentence-like steps."""
    fired = Counter()
    n_steps = 0
    n_problems = 0
    by_subject: dict[str, Counter] = defaultdict(Counter)
    subj_steps = Counter()
    for split in ("train.jsonl", "test.jsonl"):
        p = P.PRM800K / "math_splits" / split
        if not p.exists():
            continue
        with p.open() as fh:
            for line in fh:
                r = json.loads(line)
                n_problems += 1
                subj = r.get("subject", "?")
                for s in _segment(r.get("solution", "")):
                    n_steps += 1
                    subj_steps[subj] += 1
                    for c in cues.fire(s):
                        fired[c] += 1
                        by_subject[subj][c] += 1
    return {
        "n_problems": n_problems,
        "n_steps": n_steps,
        "cue_fired": dict(fired.most_common()),
        "cue_fired_rate": {
            k: round(v / n_steps, 4) for k, v in fired.most_common()
        },
        "steps_per_subject": dict(subj_steps.most_common()),
    }


def scan_prm800k_completions(files: list[str], cap_lines: int | None = None) -> dict:
    """Model-generated steps (and human-written ones) from PRM800K."""
    fired_by_rating: dict[str, Counter] = defaultdict(Counter)
    n_by_rating = Counter()
    n_human = 0
    fired_human = Counter()
    n_records = 0
    n_problems = set()
    for fname in files:
        p = P.PRM800K / "data" / fname
        if not p.exists():
            continue
        with p.open() as fh:
            for i, line in enumerate(fh):
                if cap_lines and i >= cap_lines:
                    break
                r = json.loads(line)
                n_records += 1
                q = (r.get("question") or {}).get("problem")
                if q:
                    n_problems.add(q[:120])
                for st in (r.get("label") or {}).get("steps") or []:
                    for comp in st.get("completions") or []:
                        txt = comp.get("text") or ""
                        if not txt.strip():
                            continue
                        rating = comp.get("rating")
                        key = "unrated" if rating is None else str(rating)
                        n_by_rating[key] += 1
                        for c in cues.fire(txt):
                            fired_by_rating[key][c] += 1
                    hc = st.get("human_completion")
                    if isinstance(hc, dict):
                        hc = hc.get("text")
                    if isinstance(hc, str) and hc.strip():
                        n_human += 1
                        for c in cues.fire(hc):
                            fired_human[c] += 1
    out = {
        "files": files,
        "n_records": n_records,
        "n_distinct_problems": len(n_problems),
        "n_model_steps_by_rating": dict(n_by_rating),
        "n_human_written_steps": n_human,
        "model_cue_fired_by_rating": {
            k: dict(v.most_common()) for k, v in fired_by_rating.items()
        },
        "human_cue_fired": dict(fired_human.most_common()),
    }
    tot = sum(n_by_rating.values())
    allfired = Counter()
    for v in fired_by_rating.values():
        allfired.update(v)
    out["n_model_steps_total"] = tot
    out["model_cue_fired_rate_all"] = {
        k: round(v / tot, 4) for k, v in allfired.most_common()
    }
    out["human_cue_fired_rate"] = {
        k: round(v / n_human, 4) for k, v in fired_human.most_common()
    } if n_human else {}
    # per-rating rates, for the failure/backtracking question
    out["model_cue_fired_rate_by_rating"] = {
        k: {c: round(v / n_by_rating[k], 4) for c, v in vv.most_common()}
        for k, vv in fired_by_rating.items()
        if n_by_rating[k]
    }
    return out


def main() -> None:
    P.SCRATCH.mkdir(parents=True, exist_ok=True)
    out = {}
    print("[1/3] calibrating cue lexicon on 769 gold spans ...", flush=True)
    out["calibration_gold125"] = calibrate()
    cal = out["calibration_gold125"]
    print("   spans", cal["n_spans"], "no cue fired:", cal["spans_with_no_cue"])
    print(f"   {'cue':<18}{'goldN':>6}{'firedN':>8}{'prec':>7}{'rec':>7}")
    for c, v in cal["per_cue"].items():
        if not v["calibratable"]:
            continue
        print(f"   {c:<18}{v['gold_n']:>6}{v['cue_fired_n']:>8}"
              f"{str(v['precision']):>7}{str(v['recall']):>7}")

    print("[2/3] MATH reference solutions (human) ...", flush=True)
    out["math_reference_solutions_human"] = scan_math_reference_solutions()
    m = out["math_reference_solutions_human"]
    print("   ", m["n_problems"], "problems /", m["n_steps"], "steps")
    print("   ", dict(list(m["cue_fired_rate"].items())[:12]))

    print("[3/3] PRM800K completions (model + human) ...", flush=True)
    out["prm800k_completions"] = scan_prm800k_completions(
        ["phase1_train.jsonl", "phase1_test.jsonl", "phase2_test.jsonl"]
    )
    q = out["prm800k_completions"]
    print("   model steps:", q["n_model_steps_total"], q["n_model_steps_by_rating"])
    print("   human steps:", q["n_human_written_steps"])
    print("   ", dict(list(q["model_cue_fired_rate_all"].items())[:12]))

    (P.SCRATCH / "measure_informal.json").write_text(json.dumps(out, indent=1))
    print("written", P.SCRATCH / "measure_informal.json")


if __name__ == "__main__":
    main()
