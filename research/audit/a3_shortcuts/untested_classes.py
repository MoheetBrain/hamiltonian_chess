"""AUDITOR 3 (A3) DIAGNOSTIC -- the shortcut CLASSES V5/V7 never test, measured.

For every class named in the audit brief this script either (a) implements it as a concrete
single rule over the frozen probe bank and reports its folded accuracy, or (b) records why it is
not computable on this bank (the field does not reach the model, or it is the ORACLE rather than
a shortcut).  Folding is V5's own convention: `max(s, 1 - s)`.

Measured on the ENLARGED bank -- the whole length-filtered formal pool (34/34/36 states) and 200
generated families per synthetic cell -- so these are population estimates, not 24-item ones.

No tokenizer package is installed in this venv (tiktoken / transformers / tokenizers /
sentencepiece all absent, checked), so `tokenizer_length` is reported as an explicit
CHARACTER-CLASS PROXY and labelled as such rather than silently faked.

Zero model calls.  DIAGNOSTIC ONLY -- never a re-scoring of V7.
"""

from __future__ import annotations

import json
import re
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline

from arena.canonical.schema import canonical_json
from arena.experiments.fitness_v5 import (
    EXPERIMENT_SEED,
    LADDERS,
    MECHANISMS,
    POSITIVE_VARIANTS,
    V5Slice,
    _formal_pool,
    derive_probe_family,
)

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
OUT = HERE / "untested_classes.json"
N_SYNTH = 200

NOT_COMPUTABLE = {
    "module_identity": "no module field is placed in CanonicalState; the model never sees one",
    "theorem_identity": "theorem_id lives in `oracle_record`, not in the state; never rendered",
    "source_file": "source_file lives in `provenance`, not in the state; never rendered",
    "tactic_family": "the bank carries goal states only; no tactic is present in any probe",
    "global_dependency_degree": (
        "no cross-item graph exists: each probe is a standalone state, so a global degree is "
        "undefined on this bank"
    ),
    "ast_depth": (
        "THIS IS THE ORACLE for formal_expression_depth, not a shortcut. Reported in the "
        "`oracle_reference` block below so the distinction is explicit."
    ),
}


def _toks(s):
    return [t for t in re.split(r"[^A-Za-z0-9]+", s) if t]


def _ngrams(s, n=3):
    return {s[i:i + n] for i in range(max(0, len(s) - n + 1))}


def _jac(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a | b) else 0.0


def occurrence_depths(text: str, quoted: str):
    """Bracket nesting depth of every occurrence of `quoted` in the serialized state."""
    out, depth, i = [], 0, 0
    while i < len(text):
        c = text[i]
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        if text.startswith(quoted, i):
            out.append(depth)
        i += 1
    return out or [-1]


def class_predictions(p):
    n0 = str(p.options[0].arguments[0].value)
    n1 = str(p.options[1].arguments[0].value)
    t = canonical_json(p.state.to_dict(include_display_identity=False))
    q0, q1 = f'"{n0}"', f'"{n1}"'
    goal_pos = t.find('"goal":')
    d0, d1 = occurrence_depths(t, q0), occurrence_depths(t, q1)
    f0, f1 = t.find(q0), t.find(q1)
    l0, l1 = t.rfind(q0), t.rfind(q1)

    def cmp(a, b, prefer_larger=True):
        if a == b:
            return 0
        return 0 if ((a > b) == prefer_larger) else 1

    return {
        # --- already implemented in V5 (listed for completeness) ---
        "IMPLEMENTED_first_mention": 0 if f0 <= f1 else 1,
        "IMPLEMENTED_last_mention": 0 if l0 >= l1 else 1,
        "IMPLEMENTED_identifier_frequency": cmp(t.count(q0), t.count(q1)),
        "IMPLEMENTED_length": 0 if (len(n0), n0) <= (len(n1), n1) else 1,
        "IMPLEMENTED_option_position": 0,
        # --- NOT implemented in V5 ---
        "nearest_to_goal_marker": cmp(-abs(f0 - goal_pos), -abs(f1 - goal_pos)),
        "farthest_from_goal_marker": cmp(abs(f0 - goal_pos), abs(f1 - goal_pos)),
        "lexical_overlap_name_vs_state": cmp(
            _jac(_toks(n0), _toks(t[:6000])), _jac(_toks(n1), _toks(t[:6000]))
        ),
        "token_overlap_name_vs_other_name": cmp(
            len(set(_toks(n0)) & set(_toks(n1))), 0
        ),
        "character_overlap_3gram_vs_state": cmp(
            len(_ngrams(n0) & _ngrams(t[:6000])), len(_ngrams(n1) & _ngrams(t[:6000]))
        ),
        "identifier_name_lexical": 0 if n0 <= n1 else 1,
        "identifier_name_digit_suffix": cmp(
            int(re.sub(r"\D", "", n0) or -1), int(re.sub(r"\D", "", n1) or -1)
        ),
        "punctuation_before_first_occurrence": cmp(
            t[: max(f0, 0)].count(","), t[: max(f1, 0)].count(",")
        ),
        "delimiter_count_before_first_occurrence": cmp(
            t[: max(f0, 0)].count("[") + t[: max(f0, 0)].count("{"),
            t[: max(f1, 0)].count("[") + t[: max(f1, 0)].count("{"),
        ),
        "textual_bracket_depth_max": cmp(max(d0), max(d1)),
        "textual_bracket_depth_min": cmp(min(d0), min(d1)),
        "local_dependency_degree_occurrences": cmp(len(d0), len(d1)),
        "candidate_rank_in_option_tuple": 0,
        "prompt_position_first_in_options": 0,
        "tokenizer_length_PROXY_charclass": cmp(
            -(len(n0) + sum(not c.isalnum() for c in n0)),
            -(len(n1) + sum(not c.isalnum() for c in n1)),
        ),
        "regex_underscore_prefix": cmp(n0.count("_"), n1.count("_")),
        "span_between_first_and_last": cmp(l0 - f0, l1 - f1),
        # --- oracle reference, NOT a shortcut ---
        "ORACLE_ast_depth": cmp(max(d0), max(d1)),
    }


def bank():
    pool = _formal_pool(Path.cwd())
    out = defaultdict(list)
    for level, params in enumerate(LADDERS["formal_expression_depth"]):
        for index, formal in enumerate(pool[str(params["stratum"])]):
            salt = EXPERIMENT_SEED + MECHANISMS.index("formal_expression_depth") * 1000 \
                + level * 100 + index
            for p in derive_probe_family(
                "formal_expression_depth", level, V5Slice.DEV, salt, formal
            ):
                if p.variant.value in POSITIVE_VARIANTS:
                    out[f"formal_expression_depth|L{level}"].append(p)
    for mech in ("transitive_dependency", "precondition_conjunction"):
        for level in range(len(LADDERS[mech])):
            for index in range(N_SYNTH):
                salt = EXPERIMENT_SEED + MECHANISMS.index(mech) * 1000 + level * 100 + index
                for p in derive_probe_family(mech, level, V5Slice.DEV, salt, None):
                    if p.variant.value in POSITIVE_VARIANTS:
                        out[f"{mech}|L{level}"].append(p)
    return out


def ngram_model(probes):
    """Char 2-5 gram logistic over the two option names -- the `n-grams` class, grouped-CV."""
    X = [f"{str(p.options[0].arguments[0].value)} || {str(p.options[1].arguments[0].value)}"
         for p in probes]
    y = np.array([p.expected_index for p in probes])
    g = np.array([p.family_id for p in probes])
    if len(set(y)) < 2 or len(set(g)) < 6:
        return None
    pipe = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2),
        LogisticRegression(max_iter=3000),
    )
    preds = np.empty_like(y)
    for tr, te in GroupKFold(n_splits=6).split(X, y, groups=g):
        pipe.fit([X[i] for i in tr], y[tr])
        preds[te] = pipe.predict([X[i] for i in te])
    s = float((preds == y).mean())
    return max(s, 1 - s)


def main() -> int:
    cells = bank()
    results = {}
    for cell, probes in sorted(cells.items()):
        n = len(probes)
        acc = defaultdict(int)
        for p in probes:
            for k, v in class_predictions(p).items():
                acc[k] += int(v == p.expected_index)
        folded = {k: max(c / n, 1 - c / n) for k, c in acc.items()}
        results[cell] = {
            "n_positives": n,
            "folded_accuracy": folded,
            "n_grams_char2_5_logistic_groupedCV_folded": ngram_model(probes),
            "best_UNIMPLEMENTED_class": max(
                (k for k in folded if not k.startswith(("IMPLEMENTED_", "ORACLE_"))),
                key=lambda k: folded[k],
            ),
        }
        results[cell]["best_UNIMPLEMENTED_value"] = folded[results[cell]["best_UNIMPLEMENTED_class"]]
        results[cell]["best_IMPLEMENTED_value"] = max(
            v for k, v in folded.items() if k.startswith("IMPLEMENTED_")
        )
    out = {
        "_disclaimer": (
            "A3 DIAGNOSTIC. Measures shortcut CLASSES the frozen family never tests. NOT a "
            "re-scoring of V7; no sentinel may be promoted, re-scored or reinterpreted from it."
        ),
        "not_computable_on_this_bank": NOT_COMPUTABLE,
        "tokenizer_note": (
            "no tokenizer package is installed in this venv (tiktoken, transformers, tokenizers, "
            "sentencepiece all absent); `tokenizer_length_PROXY_charclass` is a character-class "
            "proxy, explicitly not a real BPE length"
        ),
        "n_synthetic_families_per_cell": N_SYNTH,
        "cells": results,
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"{'cell':34s} {'n':>5s} {'bestIMPL':>9s} {'bestUNIMPL':>11s} {'ngramCV':>8s}  class")
    for k, c in results.items():
        ng = c["n_grams_char2_5_logistic_groupedCV_folded"]
        print(f"{k:34s} {c['n_positives']:5d} {c['best_IMPLEMENTED_value']:9.4f} "
              f"{c['best_UNIMPLEMENTED_value']:11.4f} "
              f"{(f'{ng:.4f}' if ng is not None else 'n/a'):>8s}  "
              f"{c['best_UNIMPLEMENTED_class']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
