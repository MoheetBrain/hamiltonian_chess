"""Span / similarity / locality audit of the precondition ladder across the eight founders.

Offline and deterministic; no model, no network.  Run from the repository root:

    .venv/bin/python -m research.phase8.parity.span_audit \\
        --out artifacts/reports/precondition_parity_audit.json

What is measured (all on prompts built by the tournament harness's own ``build_prompt`` with
``SyntaxGuidePolicy.SHARED_CONSTANT``):

* per arm: prompt characters and UTF-8 bytes, an ESTIMATED token count (characters divided by
  an assumed chars-per-token ratio per surface class -- the ratios are the ones the brief
  reports as measured on the live tokenizer; nothing here tokenises), the character-offset
  fraction at which the assumptions (``holds``) block and the propositions (``requires``) block
  start, and how many bytes separate the ORIGINAL and COUNTERFACTUAL twin prompts and where on
  the page those bytes sit;
* per pair of arms, on the ``CURRENT STATE`` block only: the longest common substring (exact,
  suffix automaton), the fraction of each arm's state characters covered by >= 40-character
  spans that also occur verbatim in the other arm (the V7 audit's E1 measure, here a
  measurement rather than a gate), and ``difflib.SequenceMatcher(autojunk=False).ratio()`` on
  the first 30,000 characters (the cap is recorded);
* per arm: the identifier tokens (``[A-Za-z]+:[A-Za-z0-9:]+|p:\\d{4,5}``) on the state page
  compared with the ``L3_JSON_AST`` baseline, as sets and as multisets after discounting
  tokens that are fragments of the arm's own fixed role labels;
* the harness's ``assert_arena_parity`` verdict for every base and order-rotated item under
  all eight founders.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import signal
import sys
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path
from typing import Any

from arena.environments.precondition_ladder import (
    ENVIRONMENT_VERSION,
    Pool,
    PreconditionFamily,
    build_family,
)
from arena.experiments.game_r_formal_v1 import (
    ANSWER_PROTOCOL_VERSION,
    ENVELOPE_VERSION,
    HARNESS_VERSION,
    HarnessRefusal,
    MaterialisedItem,
    SyntaxGuidePolicy,
    assert_arena_parity,
    build_prompt,
    founder_genome,
    rotate_options,
)
from arena.genome.genes import GrammarFamily
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage

REPORT_VERSION = "precondition-parity-audit-v1"
DEFAULT_STRATA = ("P05", "P07", "P09", "P12", "P16", "P20")
DEFAULT_FAMILIES = 3
POOL = Pool.DEV
GUIDE = SyntaxGuidePolicy.SHARED_CONSTANT
SURFACES: tuple[str, ...] = tuple(SEED_GENOME_BY_ID)
PHASE8_ROSTER = (
    "L3_JSON_AST",
    "L0_STRUCTURED_ENGLISH",
    "L1_CURRENT_HML",
    "L2_SEXPR",
    "L5_COMPACT_SYMBOLIC",
)
BASELINE = "L3_JSON_AST"
SPAN = 40
SEQMATCH_CAP = 30_000
#: A second, always-computed ratio at a cap small enough to be tractable for every pair.
SEQMATCH_FAST_CAP = 8_000
#: Wall-clock guard per pair for the capped ratio (difflib is super-quadratic on this text).
SEQMATCH_TIMEOUT_S = 120
LCS_EXAMPLE_CHARS = 200

ID_TOKEN = re.compile(r"[A-Za-z]+:[A-Za-z0-9:]+|p:\d{4,5}")
STATE_MARKER = "CURRENT STATE:\n"
OPTIONS_MARKER = "\nOPTIONS:\n"

#: Chars-per-token ratios per surface class, as reported in the brief (measured on the live
#: tokenizer elsewhere).  Every token figure derived from them is labelled an ESTIMATE.
TOKEN_RATIOS: dict[str, float] = {"json_like": 3.0, "structured_english": 3.4, "compact": 2.3}
TOKEN_CLASS: dict[str, str] = {
    "L0_STRUCTURED_ENGLISH": "structured_english",
    "L5_COMPACT_SYMBOLIC": "compact",
}
#: The three encoder branches of ``arena.languages.phenotype._grammar_encode``.
ENCODER_CLASS: dict[GrammarFamily, str] = {
    GrammarFamily.S_EXPRESSION: "sexpr",
    GrammarFamily.PREFIX: "typed_prefix",
    GrammarFamily.HYBRID: "typed_prefix",
}


# ------------------------------------------------------------------------------ text helpers


def state_block(prompt: str) -> str:
    start = prompt.index(STATE_MARKER) + len(STATE_MARKER)
    return prompt[start : prompt.index(OPTIONS_MARKER)]


def stats(values: Sequence[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "mean": sum(values) / len(values),
        "max": max(values),
        "n": len(values),
    }


class SuffixAutomaton:
    """Exact longest-common-substring queries against one fixed text."""

    def __init__(self, text: str) -> None:
        self.length = [0]
        self.link = [-1]
        self.next: list[dict[str, int]] = [{}]
        last = 0
        for ch in text:
            cur = len(self.length)
            self.length.append(self.length[last] + 1)
            self.link.append(-1)
            self.next.append({})
            p = last
            while p != -1 and ch not in self.next[p]:
                self.next[p][ch] = cur
                p = self.link[p]
            if p == -1:
                self.link[cur] = 0
            else:
                q = self.next[p][ch]
                if self.length[p] + 1 == self.length[q]:
                    self.link[cur] = q
                else:
                    clone = len(self.length)
                    self.length.append(self.length[p] + 1)
                    self.link.append(self.link[q])
                    self.next.append(dict(self.next[q]))
                    while p != -1 and self.next[p].get(ch) == q:
                        self.next[p][ch] = clone
                        p = self.link[p]
                    self.link[q] = clone
                    self.link[cur] = clone
            last = cur

    def longest_common_substring(self, other: str) -> tuple[int, str]:
        v = length = best = best_end = 0
        for index, ch in enumerate(other):
            while v and ch not in self.next[v]:
                v = self.link[v]
                length = self.length[v]
            if ch in self.next[v]:
                v = self.next[v][ch]
                length += 1
            else:
                v = length = 0
            if length > best:
                best, best_end = length, index
        return best, other[best_end - best + 1 : best_end + 1]


def longest_common_substring(a: str, b: str) -> tuple[int, str]:
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return SuffixAutomaton(short).longest_common_substring(long_)


def span_coverage(a: str, b: str, span: int = SPAN) -> float:
    """Fraction of ``a``'s characters lying inside some ``span``-character window of ``a``
    that occurs verbatim somewhere in ``b`` (E1's statistic, per arm)."""

    if len(a) < span or len(b) < span:
        return 0.0
    windows = {b[i : i + span] for i in range(len(b) - span + 1)}
    covered = 0
    covered_until = 0  # exclusive end of the covered prefix so far
    for i in range(len(a) - span + 1):
        if a[i : i + span] in windows:
            start = max(i, covered_until)
            covered += i + span - start
            covered_until = i + span
    return covered / len(a)


def seqmatch_ratio(a: str, b: str, cap: int) -> float:
    return difflib.SequenceMatcher(None, a[:cap], b[:cap], autojunk=False).ratio()


def timed_seqmatch(a: str, b: str, cap: int, timeout_s: int) -> dict[str, Any]:
    """``seqmatch_ratio`` under a SIGALRM wall-clock guard.  On this text difflib's cost is
    super-quadratic and pair-dependent (a single pair stalled a 12-worker run for minutes), so a
    pair that exceeds the guard is recorded as timed out rather than left to run for hours."""

    def _alarm(signum: int, frame: Any) -> None:
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, _alarm) if timeout_s > 0 else None
    if timeout_s > 0:
        signal.alarm(timeout_s)
    started = time.perf_counter()
    try:
        ratio: float | None = seqmatch_ratio(a, b, cap)
        timed_out = False
    except TimeoutError:
        ratio, timed_out = None, True
    finally:
        if timeout_s > 0:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    return {
        "ratio": ratio,
        "timed_out": timed_out,
        "seconds": round(time.perf_counter() - started, 3),
        "cap_chars": cap,
        "cap_applied": len(a) > cap or len(b) > cap,
        "timeout_s": timeout_s,
    }


# ----------------------------------------------------------------------------- pair worker


def pair_metrics(job: dict[str, Any]) -> dict[str, Any]:
    """One (stratum, arm pair) job over every item's state text.  Pure; runs in a worker."""

    texts_a: dict[str, str] = job["texts_a"]
    texts_b: dict[str, str] = job["texts_b"]
    lcs: list[int] = []
    cov_a: list[float] = []
    cov_b: list[float] = []
    example = ""
    for item_id in job["item_ids"]:
        a, b = texts_a[item_id], texts_b[item_id]
        size, snippet = longest_common_substring(a, b)
        lcs.append(size)
        if item_id == job["seqmatch_item"]:
            example = snippet
        cov_a.append(span_coverage(a, b))
        cov_b.append(span_coverage(b, a))
    seq_item = job["seqmatch_item"]
    a, b = texts_a[seq_item], texts_b[seq_item]
    capped = timed_seqmatch(a, b, job["seqmatch_cap"], job["seqmatch_timeout"])
    fast = timed_seqmatch(a, b, job["seqmatch_fast_cap"], 0)
    return {
        "stratum": job["stratum"],
        "pair": job["pair"],
        "lcs_chars": stats(lcs),
        "lcs_example": example[:LCS_EXAMPLE_CHARS],
        "lcs_example_truncated": len(example) > LCS_EXAMPLE_CHARS,
        "e1_coverage_a_in_b": stats(cov_a),
        "e1_coverage_b_in_a": stats(cov_b),
        "seqmatch_ratio": capped["ratio"],
        "seqmatch_timed_out": capped["timed_out"],
        "seqmatch_seconds": capped["seconds"],
        "seqmatch_cap_chars": capped["cap_chars"],
        "seqmatch_cap_applied": capped["cap_applied"],
        "seqmatch_timeout_s": capped["timeout_s"],
        "seqmatch_ratio_fast": fast["ratio"],
        "seqmatch_fast_cap_chars": fast["cap_chars"],
        "seqmatch_fast_seconds": fast["seconds"],
        "seqmatch_item": seq_item,
        "seqmatch_autojunk": False,
    }


# --------------------------------------------------------------------------- per-arm metrics


def _quoted_label_offset(prompt: str, label: str) -> int:
    needle = f'"{label}"'
    count = prompt.count(needle)
    if count != 1:
        raise ValueError(f"label {needle!r} occurs {count} times; locator is ambiguous")
    return prompt.index(needle)


def role_label_fragments(surface: str) -> frozenset[str]:
    """Identifier-pattern matches inside the arm's own fixed key labels (item-independent)."""

    language = GenomePhenotypeLanguage(SEED_GENOME_BY_ID[surface])
    return frozenset(ID_TOKEN.findall("\n".join(language._roles.values())))


def arm_metrics(
    surface: str,
    families: Sequence[PreconditionFamily],
    prompts: dict[str, dict[str, str]],
    baseline_counts: dict[str, Counter[str]],
) -> dict[str, Any]:
    genome = SEED_GENOME_BY_ID[surface]
    language = GenomePhenotypeLanguage(genome)
    fragments = role_label_fragments(surface)
    ratio_class = TOKEN_CLASS.get(surface, "json_like")
    ratio = TOKEN_RATIOS[ratio_class]

    chars: list[int] = []
    utf8: list[int] = []
    state_chars: list[int] = []
    assumptions_start: list[float] = []
    propositions_start: list[float] = []
    first_holds: list[float] = []
    raw_minus_baseline: set[str] = set()
    baseline_minus_raw: set[str] = set()
    multiset_identical = True
    for item_id, by_surface in prompts.items():
        prompt = by_surface[surface]
        chars.append(len(prompt))
        utf8.append(len(prompt.encode("utf-8")))
        block = state_block(prompt)
        state_chars.append(len(block))
        assumptions_start.append(
            _quoted_label_offset(prompt, language._roles["assumptions"]) / len(prompt)
        )
        propositions_start.append(
            _quoted_label_offset(prompt, language._roles["propositions"]) / len(prompt)
        )
        first_holds.append(prompt.index('"holds"', prompt.index(STATE_MARKER)) / len(prompt))
        counts = Counter(ID_TOKEN.findall(block))
        reference = baseline_counts[item_id]
        raw_minus_baseline |= set(counts) - set(reference)
        baseline_minus_raw |= set(reference) - set(counts)
        discounted = Counter({k: n for k, n in counts.items() if k not in fragments})
        multiset_identical &= discounted == reference

    twin_chars: list[int] = []
    twin_bytes: list[int] = []
    first_diff: list[float] = []
    last_diff: list[float] = []
    equal_length = True
    for family in families:
        original, counter = family.items()
        left, right = prompts[original.task_id][surface], prompts[counter.task_id][surface]
        if len(left) != len(right):
            equal_length = False
            continue
        positions = [i for i, (x, y) in enumerate(zip(left, right, strict=True)) if x != y]
        twin_chars.append(len(positions))
        lb, rb = left.encode("utf-8"), right.encode("utf-8")
        twin_bytes.append(sum(1 for x, y in zip(lb, rb, strict=True) if x != y))
        first_diff.append(positions[0] / len(left))
        last_diff.append(positions[-1] / len(left))
    params = families[0].params
    slots = 1 + params.missing_near_misses
    return {
        "surface": surface,
        "grammar": genome.grammar.value,
        "encoder_class": ENCODER_CLASS.get(genome.grammar, "json"),
        "state_policy": genome.state.value,
        "prompt_chars": stats(chars),
        "prompt_utf8_bytes": stats(utf8),
        "state_chars": stats(state_chars),
        "prompt_length_identical_across_items": min(chars) == max(chars),
        "estimated_tokens": {
            "value": round(stats(chars)["mean"] / ratio),
            "basis": "ESTIMATE: mean prompt chars / assumed chars-per-token; not tokenised here",
            "chars_per_token_assumed": ratio,
            "ratio_class": ratio_class,
        },
        "assumptions_block_start_fraction": stats(assumptions_start),
        "propositions_block_start_fraction": stats(propositions_start),
        "first_holds_token_fraction": stats(first_holds),
        "twin_difference": {
            "twins_equal_length": equal_length,
            "differing_chars": stats(twin_chars) if twin_chars else None,
            "differing_utf8_bytes": stats(twin_bytes) if twin_bytes else None,
            "differing_slots_declared": slots,
            "max_differing_chars_if_local": slots * families[0].premise_digits,
            "first_differing_char_fraction": stats(first_diff) if first_diff else None,
            "last_differing_char_fraction": stats(last_diff) if last_diff else None,
        },
        "identifier_tokens": {
            "pattern": ID_TOKEN.pattern,
            "role_label_fragments": sorted(fragments),
            "raw_minus_baseline": sorted(raw_minus_baseline),
            "baseline_minus_raw": sorted(baseline_minus_raw),
            "raw_set_identical_to_baseline": not raw_minus_baseline and not baseline_minus_raw,
            "multiset_identical_after_discounting_fragments": multiset_identical,
        },
    }


# ------------------------------------------------------------------------ harness parity


def harness_parity(items: Iterable[MaterialisedItem]) -> dict[str, Any]:
    genomes = [founder_genome(surface) for surface in SURFACES]
    checks: Counter[str] = Counter()
    signatures: set[str] = set()
    protocols: set[str] = set()
    failures: list[dict[str, str]] = []
    count = 0
    for item in items:
        for concrete in (item, rotate_options(item, 1)):
            count += 1
            try:
                report = assert_arena_parity(concrete, genomes, guide_policy=GUIDE)
            except HarnessRefusal as error:
                failures.append({"task_id": concrete.task_id, "error": str(error)})
                continue
            signatures.add(report.envelope_signature)
            protocols.add(report.answer_protocol_hash)
            for name, verdict in report.checks.items():
                checks[f"{name}={verdict}"] += 1
    return {
        "items_checked_including_rotated": count,
        "arms": [f"GRF_{surface}" for surface in SURFACES],
        "all_pass": not failures and all(k.endswith(("=PASS", "=APPLIED")) for k in checks),
        "check_tallies": dict(sorted(checks.items())),
        "envelope_signatures": sorted(signatures),
        "answer_protocol_hashes": sorted(protocols),
        "failures": failures,
    }


# ---------------------------------------------------------------------------- per stratum


def _pair_key(a: str, b: str) -> str:
    return f"{a}|{b}"


def audit_stratum(
    stratum: str,
    n_families: int,
    executor: ProcessPoolExecutor | None,
    seqmatch_cap: int,
    seqmatch_timeout: int,
    seqmatch_fast_cap: int,
) -> dict[str, Any]:
    families = [build_family(stratum, POOL, index) for index in range(n_families)]
    items = [item for family in families for item in family.items()]
    genomes = {surface: founder_genome(surface) for surface in SURFACES}
    prompts: dict[str, dict[str, str]] = {
        item.task_id: {
            surface: build_prompt(genome, item, guide_policy=GUIDE)
            for surface, genome in genomes.items()
        }
        for item in items
    }
    states = {
        surface: {
            item_id: state_block(by_surface[surface]) for item_id, by_surface in prompts.items()
        }
        for surface in SURFACES
    }
    baseline_counts = {
        item_id: Counter(ID_TOKEN.findall(states[BASELINE][item_id])) for item_id in prompts
    }
    arms = {
        surface: arm_metrics(surface, families, prompts, baseline_counts) for surface in SURFACES
    }
    seqmatch_item = items[0].task_id  # family 0, ORIGINAL
    jobs = [
        {
            "stratum": stratum,
            "pair": [a, b],
            "texts_a": states[a],
            "texts_b": states[b],
            "item_ids": list(prompts),
            "seqmatch_item": seqmatch_item,
            "seqmatch_cap": seqmatch_cap,
            "seqmatch_timeout": seqmatch_timeout,
            "seqmatch_fast_cap": seqmatch_fast_cap,
        }
        for a, b in combinations(SURFACES, 2)
    ]
    results = (
        list(executor.map(pair_metrics, jobs)) if executor else [pair_metrics(j) for j in jobs]
    )
    pairs: dict[str, Any] = {}
    for result in results:
        a, b = result["pair"]
        ga, gb = SEED_GENOME_BY_ID[a], SEED_GENOME_BY_ID[b]
        result["same_grammar_family"] = ga.grammar == gb.grammar
        result["grammar_families"] = [ga.grammar.value, gb.grammar.value]
        result["same_encoder_class"] = ENCODER_CLASS.get(ga.grammar, "json") == ENCODER_CLASS.get(
            gb.grammar, "json"
        )
        result["both_in_phase8_roster"] = a in PHASE8_ROSTER and b in PHASE8_ROSTER
        result["e1_coverage_max_direction"] = max(
            result["e1_coverage_a_in_b"]["max"], result["e1_coverage_b_in_a"]["max"]
        )
        pairs[_pair_key(a, b)] = result

    def worst(metric: str, roster_only: bool) -> dict[str, Any]:
        candidates = [
            (key, value)
            for key, value in pairs.items()
            if not roster_only or value["both_in_phase8_roster"]
        ]
        key, value = max(candidates, key=lambda kv: _score(kv[1], metric))
        return {"pair": key, metric: _score(value, metric)}

    return {
        "params": families[0].params.to_dict(),
        "premise_digits": families[0].premise_digits,
        "families": [family.family_id for family in families],
        "items": list(prompts),
        "harness_parity": harness_parity(items),
        "arms": arms,
        "pairs": pairs,
        "worst_pairs": {
            "all_eight": {
                "by_e1_coverage": worst("e1_coverage_max_direction", False),
                "by_lcs_chars": worst("lcs_chars", False),
                "by_seqmatch_ratio": worst("seqmatch_ratio", False),
                "by_seqmatch_ratio_fast": worst("seqmatch_ratio_fast", False),
            },
            "phase8_roster": {
                "by_e1_coverage": worst("e1_coverage_max_direction", True),
                "by_lcs_chars": worst("lcs_chars", True),
                "by_seqmatch_ratio": worst("seqmatch_ratio", True),
                "by_seqmatch_ratio_fast": worst("seqmatch_ratio_fast", True),
            },
        },
    }


def _score(value: dict[str, Any], metric: str) -> float:
    """Ranking score for a pair record; a timed-out capped ratio ranks below every real one."""

    if metric == "lcs_chars":
        return float(value["lcs_chars"]["max"])
    score = value[metric]
    return -1.0 if score is None else float(score)


def roster_matrix(stratum_report: dict[str, Any]) -> dict[str, Any]:
    pairs = stratum_report["pairs"]
    out: dict[str, dict[str, Any]] = {}
    for a, b in combinations(PHASE8_ROSTER, 2):
        key = _pair_key(a, b) if _pair_key(a, b) in pairs else _pair_key(b, a)
        value = pairs[key]
        cell = {
            "lcs_chars_max": value["lcs_chars"]["max"],
            "e1_coverage_max_direction": round(value["e1_coverage_max_direction"], 4),
            "seqmatch_ratio": None
            if value["seqmatch_ratio"] is None
            else round(value["seqmatch_ratio"], 4),
            "seqmatch_timed_out": value["seqmatch_timed_out"],
            "seqmatch_ratio_fast": round(value["seqmatch_ratio_fast"], 4),
            "same_grammar_family": value["same_grammar_family"],
        }
        out.setdefault(a, {})[b] = cell
        out.setdefault(b, {})[a] = cell
    return out


# ------------------------------------------------------------------------------------ main


def build_report(
    strata: Sequence[str],
    n_families: int,
    seqmatch_cap: int,
    workers: int,
    seqmatch_timeout: int = SEQMATCH_TIMEOUT_S,
    seqmatch_fast_cap: int = SEQMATCH_FAST_CAP,
) -> dict[str, Any]:
    per_stratum: dict[str, Any] = {}
    executor = ProcessPoolExecutor(max_workers=workers) if workers > 1 else None
    try:
        for stratum in strata:
            print(f"[span_audit] {stratum} ...", file=sys.stderr, flush=True)
            per_stratum[stratum] = audit_stratum(
                stratum, n_families, executor, seqmatch_cap, seqmatch_timeout, seqmatch_fast_cap
            )
    finally:
        if executor:
            executor.shutdown()
    surface_classes = {
        surface: {
            "grammar": SEED_GENOME_BY_ID[surface].grammar.value,
            "encoder_class": ENCODER_CLASS.get(SEED_GENOME_BY_ID[surface].grammar, "json"),
            "token_ratio_class": TOKEN_CLASS.get(surface, "json_like"),
            "chars_per_token_assumed": TOKEN_RATIOS[TOKEN_CLASS.get(surface, "json_like")],
            "role_label_fragments": sorted(role_label_fragments(surface)),
            "in_phase8_roster": surface in PHASE8_ROSTER,
        }
        for surface in SURFACES
    }
    overall_worst = {}
    for metric in (
        "e1_coverage_max_direction",
        "seqmatch_ratio",
        "seqmatch_ratio_fast",
        "lcs_chars",
    ):
        best = max(
            (
                (s, k, _score(v, metric))
                for s, r in per_stratum.items()
                for k, v in r["pairs"].items()
            ),
            key=lambda t: t[2],
        )
        overall_worst[metric] = {"stratum": best[0], "pair": best[1], metric: best[2]}
    timed_out = [
        {"stratum": s, "pair": k, "seconds": v["seqmatch_seconds"]}
        for s, r in per_stratum.items()
        for k, v in r["pairs"].items()
        if v["seqmatch_timed_out"]
    ]
    return {
        "report": REPORT_VERSION,
        "generated_by": "research/phase8/parity/span_audit.py",
        "generator_version": ENVIRONMENT_VERSION,
        "harness_version": HARNESS_VERSION,
        "envelope_version": ENVELOPE_VERSION,
        "answer_protocol_version": ANSWER_PROTOCOL_VERSION,
        "pool": POOL.value,
        "families_per_stratum": n_families,
        "strata": list(strata),
        "surfaces": list(SURFACES),
        "phase8_roster": list(PHASE8_ROSTER),
        "baseline": BASELINE,
        "guide_policy": GUIDE.value,
        "method": {
            "prompt": "arena.experiments.game_r_formal_v1.build_prompt with the shared constant guide",
            "state_text": "the CURRENT STATE block of the prompt (between 'CURRENT STATE:\\n' and '\\nOPTIONS:\\n')",
            "lcs": "exact longest common substring of the two state texts (suffix automaton), per item",
            "e1_coverage": f"fraction of arm X's state characters inside a {SPAN}-char window that occurs verbatim in arm Y (V7 audit E1 statistic; a measurement here, not a gate)",
            "seqmatch": f"difflib.SequenceMatcher(None, a[:{seqmatch_cap}], b[:{seqmatch_cap}], autojunk=False).ratio() on the family-0 ORIGINAL item only; 'seqmatch_cap_applied' says whether the cap truncated either text; a pair exceeding {seqmatch_timeout} s wall-clock is recorded as seqmatch_ratio=null with seqmatch_timed_out=true (difflib is super-quadratic on this text). 'seqmatch_ratio_fast' is the same statistic at a {seqmatch_fast_cap}-char cap, computed for every pair. CAUTION: the ratio is an ORDERED-alignment score and is cap-sensitive on pairs whose state blocks are re-ordered (e.g. L3|L6: 0.63 at 4k, 0.34 at 8k, 0.18 at 12k on P09); prefer e1_coverage and lcs_chars for similarity.",
            "tokens": "ESTIMATES only: chars / assumed chars-per-token by surface class; see token_estimate_ratios",
            "identifier_tokens": ID_TOKEN.pattern,
            "identifier_discount": "tokens matched inside the arm's own fixed role-label table are discounted before the multiset comparison; they are reported verbatim",
            "assumptions_block_start": "offset of the arm's quoted 'assumptions' role label divided by prompt length (the label occurs exactly once per prompt)",
            "twin_difference": "count of character (and UTF-8 byte) positions at which the ORIGINAL and COUNTERFACTUAL prompts differ; twins have equal length by construction",
            "harness_parity": "assert_arena_parity on every item and its rotate_options(item, 1) twin under all eight founders",
        },
        "token_estimate_ratios": {
            **TOKEN_RATIOS,
            "note": "ratios as reported measured on the live tokenizer in the brief; this script does not tokenise",
        },
        "surface_classes": surface_classes,
        "per_stratum": per_stratum,
        "roster_matrix_P12": roster_matrix(per_stratum["P12"]) if "P12" in per_stratum else None,
        "overall_worst_pairs_all_eight": overall_worst,
        "seqmatch_timeouts": timed_out,
        "summary": {
            "harness_parity_all_pass": all(
                r["harness_parity"]["all_pass"] for r in per_stratum.values()
            ),
            "one_envelope_signature": len(
                {
                    sig
                    for r in per_stratum.values()
                    for sig in r["harness_parity"]["envelope_signatures"]
                }
            )
            == 1,
            "one_answer_protocol": len(
                {
                    h
                    for r in per_stratum.values()
                    for h in r["harness_parity"]["answer_protocol_hashes"]
                }
            )
            == 1,
            "identifier_multisets_identical_after_discount": all(
                a["identifier_tokens"]["multiset_identical_after_discounting_fragments"]
                for r in per_stratum.values()
                for a in r["arms"].values()
            ),
            "arms_with_raw_identifier_divergence": sorted(
                {
                    a["surface"]
                    for r in per_stratum.values()
                    for a in r["arms"].values()
                    if not a["identifier_tokens"]["raw_set_identical_to_baseline"]
                }
            ),
            "twin_differences_local_everywhere": all(
                a["twin_difference"]["twins_equal_length"]
                and a["twin_difference"]["differing_chars"]["max"]
                <= a["twin_difference"]["max_differing_chars_if_local"]
                for r in per_stratum.values()
                for a in r["arms"].values()
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--out", type=Path, default=Path("artifacts/reports/precondition_parity_audit.json")
    )
    parser.add_argument("--strata", default=",".join(DEFAULT_STRATA))
    parser.add_argument("--families", type=int, default=DEFAULT_FAMILIES)
    parser.add_argument("--seqmatch-cap", type=int, default=SEQMATCH_CAP)
    parser.add_argument("--seqmatch-timeout", type=int, default=SEQMATCH_TIMEOUT_S)
    parser.add_argument("--seqmatch-fast-cap", type=int, default=SEQMATCH_FAST_CAP)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    strata = tuple(s for s in args.strata.split(",") if s)
    report = build_report(
        strata,
        args.families,
        args.seqmatch_cap,
        args.workers,
        seqmatch_timeout=args.seqmatch_timeout,
        seqmatch_fast_cap=args.seqmatch_fast_cap,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"[span_audit] wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
