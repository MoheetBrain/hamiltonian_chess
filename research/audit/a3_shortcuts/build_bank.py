"""AUDITOR 3 (A3) DIAGNOSTIC -- build and cache the V5/V7 DEV probe bank feature table.

READ-ONLY with respect to the instrument.  This script imports the frozen probe builders
(`arena.experiments.fitness_v5.build_dev_pool`) and dumps, for every POSITIVE probe, a table
of purely SURFACE / FORBIDDEN features plus the oracle label.  It changes no threshold, runs
no model, and its outputs are DIAGNOSTICS OF THE INSTRUMENT -- they may never be used to
re-score, promote or reinterpret any recorded sentinel.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    POSITIVE_VARIANTS,
    V5Probe,
    build_dev_pool,
)

OUT = Path(__file__).resolve().parent / "bank_features.jsonl"
META = Path(__file__).resolve().parent / "bank_meta.json"


def names(p: V5Probe) -> tuple[str, str]:
    return (str(p.options[0].arguments[0].value), str(p.options[1].arguments[0].value))


def state_text(p: V5Probe) -> str:
    """EXACTLY the text V5's shortcut_audit reads (fitness_v5.py:798-799)."""
    return canonical_json(p.state.to_dict(include_display_identity=False))


def prompt_like_text(p: V5Probe) -> str:
    """State text plus the serialized options, i.e. everything the audit could have read."""
    return state_text(p) + canonical_json([o.to_dict() for o in p.options])


def _char_classes(s: str) -> dict[str, int]:
    return {
        "len": len(s),
        "n_digits": sum(c.isdigit() for c in s),
        "n_underscore": s.count("_"),
        "n_upper": sum(c.isupper() for c in s),
        "n_dot": s.count("."),
        "n_alpha": sum(c.isalpha() for c in s),
        "n_nonalnum": sum((not c.isalnum()) for c in s),
    }


def _bracket_depth_at(text: str, pos: int) -> int:
    if pos < 0:
        return -1
    depth = 0
    for c in text[:pos]:
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
    return depth


def _ngrams(s: str, n: int) -> set[str]:
    return {s[i : i + n] for i in range(max(0, len(s) - n + 1))}


def per_option_features(p: V5Probe, which: int) -> dict[str, float]:
    """Surface statistics for ONE option identifier.  No depth, no oracle, no answer."""
    nm = names(p)[which]
    other = names(p)[1 - which]
    text = state_text(p)
    ptext = prompt_like_text(p)
    quoted = f'"{nm}"'
    first = text.find(quoted)
    last = text.rfind(quoted)
    pfirst = ptext.find(quoted)
    feats: dict[str, float] = {}
    feats["first_offset"] = float(first)
    feats["last_offset"] = float(last)
    feats["first_offset_frac"] = float(first) / max(1, len(text))
    feats["last_offset_frac"] = float(last) / max(1, len(text))
    feats["count_quoted"] = float(text.count(quoted))
    feats["count_raw"] = float(text.count(nm))
    feats["span"] = float(last - first)
    feats["n_commas_before_first"] = float(text[: max(first, 0)].count(","))
    feats["n_open_brackets_before_first"] = float(text[: max(first, 0)].count("["))
    feats["n_open_braces_before_first"] = float(text[: max(first, 0)].count("{"))
    feats["n_colons_before_first"] = float(text[: max(first, 0)].count(":"))
    feats["n_quotes_before_first"] = float(text[: max(first, 0)].count('"'))
    # "textual depth": bracket nesting of the JSON string at the first occurrence.
    # FLAGGED: on formal_expression_depth this is a near-transcription of the ORACLE, not a
    # surface cue.  Held in a separate block and never used in the surface-only classifiers.
    feats["SEMANTIC_bracket_depth_at_first"] = float(_bracket_depth_at(text, first))
    feats["SEMANTIC_bracket_depth_at_last"] = float(_bracket_depth_at(text, last))
    for k, v in _char_classes(nm).items():
        feats[f"name_{k}"] = float(v)
    feats["name_lex_rank_vs_other"] = 1.0 if nm < other else (0.0 if nm == other else -1.0)
    feats["name_hash_bucket"] = float(
        int(hashlib.sha256(nm.encode()).hexdigest()[:8], 16) % 97
    )  # identifier identity, coarse and DETERMINISTIC
    feats["prompt_first_offset"] = float(pfirst)
    feats["name_ngram3_overlap_with_state"] = float(
        len(_ngrams(nm, 3) & _ngrams(text[:4000], 3))
    )
    feats["name_token_overlap_with_other"] = float(
        len(set(re.split(r"[^A-Za-z0-9]+", nm)) & set(re.split(r"[^A-Za-z0-9]+", other)))
    )
    return feats


def global_features(p: V5Probe) -> dict[str, float]:
    text = state_text(p)
    return {
        "state_len": float(len(text)),
        "state_n_open_brackets": float(text.count("[")),
        "state_n_open_braces": float(text.count("{")),
        "state_n_commas": float(text.count(",")),
        "state_n_quotes": float(text.count('"')),
        "state_n_lean_nodes": float(text.count('"op":"lean.')),
        "state_n_distinct_ids": float(len(set(re.findall(r'"value":"([^"]+)"', text)))),
        "state_n_local_ref": float(text.count("lean.local_reference")),
        "n_context_objects": float(len(p.state.objects)),
    }


def main() -> int:
    root = Path.cwd()
    probes = build_dev_pool(root)
    rows = []
    for p in probes:
        if p.variant.value not in POSITIVE_VARIANTS:
            continue
        f0 = per_option_features(p, 0)
        f1 = per_option_features(p, 1)
        row = {
            "probe_id": p.probe_id,
            "family_id": p.family_id,
            "mechanism": p.mechanism,
            "level": p.level,
            "variant": p.variant.value,
            "expected_index": p.expected_index,
            "name_0": names(p)[0],
            "name_1": names(p)[1],
            "opt0": f0,
            "opt1": f1,
            "glob": global_features(p),
            "state_sha_text_len": len(state_text(p)),
        }
        rows.append(row)
    with OUT.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    meta = {
        "note": "A3 DIAGNOSTIC ARTIFACT -- not a re-scoring of V7",
        "n_positive_probes": len(rows),
        "n_all_probes": len(probes),
        "cells": sorted({(r["mechanism"], r["level"]) for r in rows}),
        "feature_names_per_option": sorted(rows[0]["opt0"]) if rows else [],
        "global_feature_names": sorted(rows[0]["glob"]) if rows else [],
    }
    meta["cells"] = [list(c) for c in meta["cells"]]
    META.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "feature_names_per_option"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
