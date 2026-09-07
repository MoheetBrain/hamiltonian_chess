"""A deliberately dumb, deterministic surface-cue detector for reasoning moves.

WHY THIS EXISTS
---------------
Nothing on disk carries operation labels on model-generated reasoning steps.
PRM800K has 733,768 steps and 1,085,590 step ratings, but zero operation
annotations. To say anything at all about whether the operations seen in
human MATH solutions also occur in model-generated chains, some detector is
needed, and no model call is permitted (and none would be verification anyway).

So: a regex cue lexicon, written from the Gold-125 gold spans, then CALIBRATED
against the 769 gold labels so its precision and recall are known numbers
rather than assumptions. Every frequency this detector produces is a LEXICAL
PROXY, not an operation count. Read the calibration table before believing any
of it.

Design notes:
  * Multi-label: a span may fire several cues. That is intentional; steps
    genuinely do several things at once.
  * `PLAN`, `BACKTRACK` and `RETRIEVE` have no counterpart in the
    reasoning_ontology_v1 core_operation axis, so they cannot be calibrated
    against it. They are reported as firing rates only.
  * `let X be ...` (a declaration) is separated from `let's <verb>` (a plan).
    Collapsing them is the single most seductive false match in this data.
"""

from __future__ import annotations

import re

CUES: dict[str, list[str]] = {
    # --- canonical mathematical operations ---------------------------------
    "DECLARE": [
        r"\blet\s+\$?\\?[A-Za-z][^.;]{0,40}?\s+(?:be|denote|represent)\b",
        r"\blet\s+\$[^$]{1,30}\$?\s*=",
        r"\bcall\s+(?:the|this|these|it)\b",
        r"\bdenote\s+by\b",
        r"\bdefine\s+\$?[A-Za-z]",
        r"\bsuppose\s+(?:that\s+)?\$",
    ],
    "CONSTRUCT": [
        r"\bwithout\s+loss\s+of\s+generality\b",
        r"\bwlog\b",
        r"\bconstruct\b",
        r"\bconsider\s+the\s+(?:function|set|sequence|polynomial|triangle|point)",
        r"\bdraw\b",
        r"\bthere\s+(?:exists|is)\s+(?:a|an|some)\b",
    ],
    "SUBSTITUTE": [
        r"\bsubstitut",
        r"\bplug(?:ging)?\s+(?:this|that|in|into|it)\b",
        r"\breplac(?:e|ing)\s+\$",
    ],
    "TRANSFORM": [
        r"\bsolv(?:e|ing)\s+(?:for|this|the)\b",
        r"\bfactor(?:ing|s|ed)?\b",
        r"\bexpand(?:ing)?\b",
        r"\b(?:multiply|divide|add|subtract)(?:ing)?[^.;]{0,25}both\s+sides\b",
        r"\bsquar(?:e|ing)\s+both\s+sides\b",
        r"\bcross[- ]multiply\b",
        r"\brearrang",
        r"\bcombin(?:e|ing)\s+like\s+terms\b",
        r"\bclear(?:ing)?\s+(?:the\s+)?denominator",
    ],
    "APPLY_THEOREM": [
        r"\bby\s+(?:the\s+)?[A-Z][A-Za-z\-]*(?:'s)?\s+"
        r"(?:theorem|inequality|lemma|formula|rule|identity|law)\b",
        r"\bby\s+AM-?GM\b",
        r"\bby\s+(?:Cauchy|Vieta|Fermat|Euler|Pythagoras|Pythagorean|Bezout|"
        r"Wilson|Heron|Ptolemy|Stewart|Menelaus|Ceva)\b",
        r"\b(?:theorem|lemma)\b",
        r"\b(?:quadratic|binomial|distance|midpoint|shoelace)\s+formula\b",
    ],
    "APPLY_DEFINITION": [
        r"\bby\s+definition\b",
        r"\bdefinition\s+of\b",
        r"\bis\s+defined\s+(?:as|to\s+be|by)\b",
        r"\bmeans\s+that\b",
        r"\bin\s+order\s+for\b.{0,60}?\bmust\b",
    ],
    "CASE_SPLIT": [
        r"\bcases?\b",
        r"\beither\b[^.;]{0,80}\bor\b",
        r"\bsplit\b",
        r"\bif\b[^.;]{0,60}\botherwise\b",
        r"\bwe\s+consider\s+two\b",
    ],
    "INDUCT": [
        r"\binduction\b",
        r"\bbase\s+case\b",
        r"\binductive\s+(?:step|hypothesis)\b",
    ],
    "CONTRADICTION": [
        r"\bcontradict",
        r"\bsuppose\s+not\b",
        r"\bfor\s+(?:the\s+sake\s+of\s+)?contradiction\b",
        r"\bimpossible\b",
        r"\bcannot\s+(?:be|happen|occur)\b",
    ],
    "VERIFY": [
        r"\bcheck(?:ing|s)?\b",
        r"\bverif(?:y|ies|ying|ication)\b",
        r"\bplug\b[^.;]{0,40}\bback\b",
        r"\bindeed\b",
        r"\bconfirm",
        r"\bmake\s+sure\b",
    ],
    "DISCHARGE": [
        r"\\d?boxed\{",
        r"\bthe\s+(?:final\s+)?answer\s+is\b",
        r"\bwe\s+are\s+done\b",
        r"\bqed\b",
        r"\bas\s+(?:desired|required|claimed)\b",
    ],
    "EVALUATE": [
        r"\bsimplif",
        r"\bcomput(?:e|ing|ation)\b",
        r"\bevaluat",
        r"\bcalculat",
        r"\bwhich\s+(?:is|gives|equals)\b",
    ],
    "COUNT": [
        r"\bnumber\s+of\b",
        r"\bways\b",
        r"\bcombinations?\b",
        r"\bpermutations?\b",
        r"\bprobability\b",
        r"\\d?binom\b",
        r"\bchoose\s+\d",
    ],
    "BOUND": [
        r"\bat\s+least\b",
        r"\bat\s+most\b",
        r"\b(?:upper|lower)\s+bound\b",
        r"\bmaxim(?:um|al|ize)\b",
        r"\bminim(?:um|al|ize)\b",
        r"\bgreater\s+than\b",
        r"\bless\s+than\b",
    ],
    "SELECT": [
        r"\bthe\s+(?:larger|smaller|largest|smallest|greatest|least)\b",
        r"\bwe\s+(?:choose|pick|take|select)\b",
        r"\bonly\s+(?:possible|valid|one)\b",
        r"\bdiscard\b",
        r"\breject\b",
    ],
    "ENUMERATE": [
        r"\bthere\s+are\s+\d+\s+(?:ways|options|possibilities|choices|values)\b",
        r"\blist(?:ing)?\s+(?:all|the|out)\b",
        r"\bfor\s+each\b",
        r"\benumerat",
    ],
    # --- controller / macro moves (no core_operation counterpart) ----------
    "PLAN": [
        r"\blet'?s\b",
        r"\bwe\s+(?:can|will|should|need\s+to|want\s+to)\s+"
        r"(?:try|start|begin|consider|first|use|apply)\b",
        r"\bfirst,?\s+(?:let'?s|we)\b",
        r"\b(?:now|next|then),?\s+(?:let'?s|we)\b",
        r"\bthe\s+(?:idea|strategy|plan|approach)\s+is\b",
    ],
    "BACKTRACK": [
        r"\bwait\b",
        r"\bactually\b",
        r"\bthat'?s\s+(?:wrong|not\s+right|incorrect|not\s+correct)\b",
        r"\bhmm+\b",
        r"\b(?:i|we)\s+made\s+a\s+mistake\b",
        r"\bstart\s+over\b",
        r"\blet\s+me\s+(?:re|try\s+again)",
        r"\bnever\s+mind\b",
        r"\boops\b",
    ],
    "RETRIEVE": [
        r"\brecall\s+(?:that|the)\b",
        r"\bwe\s+know\s+(?:that\s+)?\b",
        r"\bremember\s+that\b",
        r"\bit\s+is\s+(?:well[- ])?known\b",
        r"\bwe\s+are\s+given\b",
    ],
}

COMPILED: dict[str, list[re.Pattern]] = {
    k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in CUES.items()
}

# Cues with no core_operation counterpart -> cannot be calibrated against
# the Gold-125 gold labels.
UNCALIBRATABLE = {"PLAN", "BACKTRACK", "RETRIEVE"}


def fire(text: str) -> set[str]:
    """Which cues fire on this text."""
    return {k for k, pats in COMPILED.items() if any(p.search(text) for p in pats)}
