"""Rendered-prompt adversary family (v1).

The previous shortcut audit (``fitness_v5.shortcut_audit``) scored its rules on
``canonical_json(state)`` while the Solver read the *rendered* prompt; audit item C1 measured the
rule that voided two mechanisms at exact chance on the string the Solver actually saw.  This
module is the replacement.  Every adversary here receives **exactly** what the Solver receives,
``(prompt, n_options)``, and nothing else: no canonical state, no answer metadata, no probe.

Three defects from ``docs/V7_TOTAL_FORENSIC_AUDIT.md`` are closed structurally rather than by
policy:

C1   The only input is the rendered prompt string.  :func:`extract_surface` recovers the
     envelope slots from the literal markers of ``game_r_formal_v1._assemble`` and nothing else.
C3d  The family is wide (both polarities of every feature plus every constant position), and
     :func:`twin_invariance_report` documents which features are pinned at chance by
     construction so that a "clean" verdict cannot silently rest on dead rules.
C3e  The max-over-family statistic is reported with a Bonferroni-adjusted Clopper-Pearson bound,
     a family-clustered bootstrap error, and a within-family permutation null; and development
     (:func:`develop_and_freeze`) is separated from evaluation (:func:`evaluate_frozen`), which
     refuses any family it has already seen.
C6   Constant-position rules are members of the family and abstentions are never resolved by
     position: a tie is an abstention worth ``1/n_options``.

Boundary rule.  An adversary is a *surface* strategy.  It may compute any statistic of the
option texts, of the occurrences of candidate identifier tokens in the state text, of global
string properties of the state text, or of fixed-width windows around candidate mentions.  It
must not parse the representation's grammar to pair premises with answers or otherwise
re-implement the task's defining relation.  That boundary is enforced by construction: every
feature is a function of :class:`SurfaceView` alone, and the test module asserts by AST scan
that this file never imports the canonical, environment, fitness or language machinery.
"""

from __future__ import annotations

import functools
import hashlib
import json
import math
import re
import zlib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

ADVERSARY_FAMILY_VERSION = "arena-rendered-prompt-adversary-v1.0.0"

MAX_OPTIONS = 26
DEFAULT_SEED = 20260907
DEFAULT_ALPHA = 0.05
DEFAULT_BOOTSTRAP_SAMPLES = 1000
DEFAULT_PERMUTATIONS = 2000
WINDOW_HALF_WIDTH = 16  # the 32-character window is [pos - 16, pos + 16)
NGRAM_ORDER = 3

# --------------------------------------------------------------------------------- envelope
#
# These are the literal markers of ``game_r_formal_v1._assemble``.  Nothing else about the
# envelope is assumed; in particular the option text may span lines and may contain the word
# OPTIONS, and the parser never looks at anything but these strings.

QUESTION_MARKER = "\nQUESTION: "
STATE_MARKER = "\nCURRENT STATE:\n"
OPTIONS_MARKER = "\nOPTIONS:\n"
ANSWER_MARKER = "\nANSWER:"


def option_labels(n_options: int) -> tuple[str, ...]:
    if not 2 <= n_options <= MAX_OPTIONS:
        raise ValueError(f"n_options must be in [2, {MAX_OPTIONS}], got {n_options}")
    return tuple(f"OPTION_{chr(ord('A') + index)}" for index in range(n_options))


_TOKEN = re.compile(r"[A-Za-z0-9_:.\-]{3,}")
#: Punctuation the token class admits but that never begins or ends an identifier.
_TOKEN_TRIM = ":.-"

#: Envelope vocabulary.  Removed from every option's token set before candidates are chosen.
ENVELOPE_STOPLIST: frozenset[str] = frozenset(
    {"OPTION", "OPTIONS", "ANSWER", "QUESTION", "CURRENT", "STATE", "GUIDE", "GRAMMAR"}
    | set(option_labels(MAX_OPTIONS))
)


@dataclass(frozen=True)
class SurfaceView:
    """The rendered prompt, cut at the envelope markers.  Nothing here is canonical.

    ``candidate_tokens[i]`` are the identifier-like tokens (maximal runs of
    ``[A-Za-z0-9_:.\\-]{3,}``, trimmed of leading and trailing ``:``, ``.`` and ``-``) of option
    ``i`` minus :data:`ENVELOPE_STOPLIST` minus the tokens shared by *every* option (the
    representation's own boilerplate carries no information about which option is which),
    ordered longest-first then lexically.  An option whose text is identical to every other
    option has no candidates.
    """

    header: str
    question: str
    state_text: str
    option_texts: tuple[str, ...]
    candidate_tokens: tuple[tuple[str, ...], ...]

    @property
    def n_options(self) -> int:
        return len(self.option_texts)


def _split_options(text: str, labels: Sequence[str]) -> tuple[str, ...] | None:
    first = f"{labels[0]}: "
    if not text.startswith(first):
        return None
    starts = [0]
    contents_start = [len(first)]
    cursor = len(first)
    for label in labels[1:]:
        marker = f"\n{label}: "
        position = text.find(marker, cursor)
        if position < 0:
            return None
        starts.append(position)
        contents_start.append(position + len(marker))
        cursor = position + len(marker)
    texts: list[str] = []
    for index in range(len(labels)):
        end = starts[index + 1] if index + 1 < len(labels) else len(text)
        texts.append(text[contents_start[index] : end])
    return tuple(texts)


def _option_tokens(text: str) -> set[str]:
    trimmed = (token.strip(_TOKEN_TRIM) for token in _TOKEN.findall(text))
    return {token for token in trimmed if len(token) >= 3} - ENVELOPE_STOPLIST


def _candidate_tokens(option_texts: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    token_sets = [_option_tokens(text) for text in option_texts]
    shared: set[str] = set.intersection(*token_sets) if token_sets else set()
    return tuple(
        tuple(sorted(tokens - shared, key=lambda token: (-len(token), token)))
        for tokens in token_sets
    )


def extract_surface(prompt: str, n_options: int) -> SurfaceView:
    """Cut ``prompt`` at the envelope markers.  Raises ``ValueError`` if they are absent."""

    labels = option_labels(n_options)
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")
    question_at = prompt.find(QUESTION_MARKER)
    if question_at < 0:
        raise ValueError("envelope marker QUESTION: not found")
    state_at = prompt.find(STATE_MARKER, question_at + len(QUESTION_MARKER))
    if state_at < 0:
        raise ValueError("envelope marker CURRENT STATE: not found")
    if not prompt.endswith(ANSWER_MARKER):
        raise ValueError("envelope must end with the ANSWER: marker")
    header = prompt[:question_at]
    question = prompt[question_at + len(QUESTION_MARKER) : state_at]
    body = prompt[state_at + len(STATE_MARKER) : len(prompt) - len(ANSWER_MARKER)]
    cursor = 0
    while True:
        options_at = body.find(OPTIONS_MARKER, cursor)
        if options_at < 0:
            raise ValueError(
                f"envelope marker OPTIONS: with {n_options} labelled options not found"
            )
        texts = _split_options(body[options_at + len(OPTIONS_MARKER) :], labels)
        if texts is not None:
            return SurfaceView(
                header=header,
                question=question,
                state_text=body[:options_at],
                option_texts=texts,
                candidate_tokens=_candidate_tokens(texts),
            )
        cursor = options_at + 1


# ---------------------------------------------------------------------------------- examples


@dataclass(frozen=True)
class Example:
    """One rendered item.  ``correct_index`` is used only for scoring, never shown to a rule."""

    prompt: str
    n_options: int
    correct_index: int
    family_id: str
    arm_id: str
    task_id: str

    def __post_init__(self) -> None:
        if not 2 <= self.n_options <= MAX_OPTIONS:
            raise ValueError(f"n_options must be in [2, {MAX_OPTIONS}]")
        if not 0 <= self.correct_index < self.n_options:
            raise ValueError("correct_index out of range")


# ---------------------------------------------------------------------------------- features
#
# Every feature maps a SurfaceView to one score per option.  Higher = more likely under the "+"
# polarity.  Sentinels for "never mentioned" are explicit constants so that a rule's behaviour on
# an unmentioned candidate is a documented surface strategy rather than an accident.

FeatureFn = Callable[[SurfaceView], tuple[float, ...]]


@functools.lru_cache(maxsize=512)
def _mention_positions(view: SurfaceView) -> tuple[tuple[int, ...], ...]:
    """Start offsets (sorted) of every candidate token occurrence in the state text."""

    result: list[tuple[int, ...]] = []
    for tokens in view.candidate_tokens:
        positions: set[int] = set()
        for token in tokens:
            for match in re.finditer(re.escape(token), view.state_text):
                positions.add(match.start())
        result.append(tuple(sorted(positions)))
    return tuple(result)


def _windows(view: SurfaceView, index: int) -> list[str]:
    state = view.state_text
    return [
        state[max(0, position - WINDOW_HALF_WIDTH) : position + WINDOW_HALF_WIDTH]
        for position in _mention_positions(view)[index]
    ]


def _ngrams(text: str) -> set[str]:
    return {text[i : i + NGRAM_ORDER] for i in range(len(text) - NGRAM_ORDER + 1)}


def _common_prefix(a: str, b: str) -> int:
    count = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        count += 1
    return count


def _f_option_text_length(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(len(text)) for text in view.option_texts)


def _f_option_token_count(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(len(_TOKEN.findall(text))) for text in view.option_texts)


def _f_candidate_token_count(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(len(tokens)) for tokens in view.candidate_tokens)


def _f_candidate_first_mention_pos(view: SurfaceView) -> tuple[float, ...]:
    never = float(len(view.state_text) + 1)
    return tuple(
        float(positions[0]) if positions else never for positions in _mention_positions(view)
    )


def _f_candidate_last_mention_pos(view: SurfaceView) -> tuple[float, ...]:
    return tuple(
        float(positions[-1]) if positions else -1.0 for positions in _mention_positions(view)
    )


def _f_candidate_mention_count(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(len(positions)) for positions in _mention_positions(view))


def _f_candidate_mention_spread(view: SurfaceView) -> tuple[float, ...]:
    return tuple(
        float(positions[-1] - positions[0]) if len(positions) >= 2 else 0.0
        for positions in _mention_positions(view)
    )


def _f_candidate_lexical_rank(view: SurfaceView) -> tuple[float, ...]:
    keys = ["\x1f".join(tokens) for tokens in view.candidate_tokens]
    order = sorted(set(keys))
    return tuple(float(order.index(key)) for key in keys)


def _f_candidate_digit_sum(view: SurfaceView) -> tuple[float, ...]:
    return tuple(
        float(sum(int(ch) for token in tokens for ch in token if ch.isdigit()))
        for tokens in view.candidate_tokens
    )


def _f_candidate_id_length(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(sum(len(token) for token in tokens)) for tokens in view.candidate_tokens)


def _f_first_mention_line_index(view: SurfaceView) -> tuple[float, ...]:
    never = float(view.state_text.count("\n") + 1)
    return tuple(
        float(view.state_text.count("\n", 0, positions[0])) if positions else never
        for positions in _mention_positions(view)
    )


def _f_mention_bracket_depth(view: SurfaceView) -> tuple[float, ...]:
    state = view.state_text
    scores: list[float] = []
    for positions in _mention_positions(view):
        if not positions:
            scores.append(-1.0)
            continue
        prefix = state[: positions[0]]
        openers = prefix.count("(") + prefix.count("[") + prefix.count("{")
        closers = prefix.count(")") + prefix.count("]") + prefix.count("}")
        scores.append(float(openers - closers))
    return tuple(scores)


def _f_window_ngram_overlap(view: SurfaceView) -> tuple[float, ...]:
    state_grams = _ngrams(view.state_text)
    if not state_grams:
        return tuple(0.0 for _ in view.option_texts)
    scores: list[float] = []
    for index in range(view.n_options):
        window_grams: set[str] = set()
        for window in _windows(view, index):
            window_grams |= _ngrams(window)
        scores.append(len(window_grams & state_grams) / len(state_grams))
    return tuple(scores)


def _f_window_punctuation_density(view: SurfaceView) -> tuple[float, ...]:
    scores: list[float] = []
    for index in range(view.n_options):
        joined = "".join(_windows(view, index))
        if not joined:
            scores.append(0.0)
            continue
        punctuation = sum(1 for ch in joined if not ch.isalnum() and not ch.isspace())
        scores.append(punctuation / len(joined))
    return tuple(scores)


def _primary(view: SurfaceView) -> list[str]:
    return [tokens[0] if tokens else "" for tokens in view.candidate_tokens]


def _f_candidate_prefix_shared(view: SurfaceView) -> tuple[float, ...]:
    primary = _primary(view)
    scores: list[float] = []
    for i, token in enumerate(primary):
        others = [_common_prefix(token, other) for j, other in enumerate(primary) if j != i]
        scores.append(sum(others) / len(others) / max(1, len(token)))
    return tuple(scores)


def _f_candidate_suffix_shared(view: SurfaceView) -> tuple[float, ...]:
    primary = [token[::-1] for token in _primary(view)]
    scores: list[float] = []
    for i, token in enumerate(primary):
        others = [_common_prefix(token, other) for j, other in enumerate(primary) if j != i]
        scores.append(sum(others) / len(others) / max(1, len(token)))
    return tuple(scores)


def _f_gzip_delta(view: SurfaceView) -> tuple[float, ...]:
    """Compressed-length change when the candidate's tokens are deleted from the state text.

    ``zlib`` (the deflate stream inside gzip) at level 6, so the value carries no timestamp.
    """

    base = len(zlib.compress(view.state_text.encode("utf-8"), 6))
    scores: list[float] = []
    for tokens in view.candidate_tokens:
        if not tokens:
            scores.append(0.0)
            continue
        stripped = view.state_text
        for token in tokens:
            stripped = stripped.replace(token, "")
        scores.append(float(base - len(zlib.compress(stripped.encode("utf-8"), 6))))
    return tuple(scores)


def _f_position_of_option_in_prompt(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(index) for index in range(view.n_options))


def _f_state_text_length(view: SurfaceView) -> tuple[float, ...]:
    return tuple(float(len(view.state_text)) for _ in view.option_texts)


FEATURES: dict[str, FeatureFn] = {
    "option_text_length": _f_option_text_length,
    "option_token_count": _f_option_token_count,
    "candidate_token_count": _f_candidate_token_count,
    "candidate_first_mention_pos": _f_candidate_first_mention_pos,
    "candidate_last_mention_pos": _f_candidate_last_mention_pos,
    "candidate_mention_count": _f_candidate_mention_count,
    "candidate_mention_spread": _f_candidate_mention_spread,
    "candidate_lexical_rank": _f_candidate_lexical_rank,
    "candidate_digit_sum": _f_candidate_digit_sum,
    "candidate_id_length": _f_candidate_id_length,
    "first_mention_line_index": _f_first_mention_line_index,
    "mention_bracket_depth": _f_mention_bracket_depth,
    "window_ngram_overlap": _f_window_ngram_overlap,
    "window_punctuation_density": _f_window_punctuation_density,
    "candidate_prefix_shared": _f_candidate_prefix_shared,
    "candidate_suffix_shared": _f_candidate_suffix_shared,
    "gzip_delta": _f_gzip_delta,
    "position_of_option_in_prompt": _f_position_of_option_in_prompt,
    "state_text_length": _f_state_text_length,
}

FEATURE_NAMES: tuple[str, ...] = tuple(FEATURES)

#: Features whose score depends on the candidate's mentions in the state text.
CANDIDATE_MENTION_FEATURES: tuple[str, ...] = (
    "candidate_first_mention_pos",
    "candidate_last_mention_pos",
    "candidate_mention_count",
    "candidate_mention_spread",
    "first_mention_line_index",
    "mention_bracket_depth",
    "window_punctuation_density",
)

POLARITIES: tuple[int, ...] = (1, -1)
CONSTANT_RULES: tuple[str, ...] = tuple(f"always_option_{k}" for k in range(MAX_OPTIONS))
POLAR_RULES: tuple[str, ...] = tuple(
    f"{name}:{'+' if polarity > 0 else '-'}" for name in FEATURE_NAMES for polarity in POLARITIES
)
RULES: tuple[str, ...] = POLAR_RULES + CONSTANT_RULES

#: Features whose score is a function of option position alone.
POSITIONAL_FEATURES: frozenset[str] = frozenset({"position_of_option_in_prompt"})

#: Rules whose prediction is a function of option position alone.
POSITIONAL_RULES: frozenset[str] = frozenset(
    CONSTANT_RULES
    + tuple(f"{name}:{sign}" for name in sorted(POSITIONAL_FEATURES) for sign in "+-")
)

#: The shallow models' design columns.  Position is excluded so that two options with identical
#: text produce identical rows and the model *ties* (abstains) instead of resolving by position;
#: position anchoring is measured by the constant rules of the family instead.
MODEL_FEATURE_NAMES: tuple[str, ...] = tuple(
    name for name in FEATURE_NAMES if name not in POSITIONAL_FEATURES
)


def _unique_extreme(scores: Sequence[float], polarity: int) -> int | None:
    if not scores or any(not math.isfinite(score) for score in scores):
        return None
    target = max(scores) if polarity > 0 else min(scores)
    hits = [index for index, score in enumerate(scores) if score == target]
    return hits[0] if len(hits) == 1 else None


def feature_scores(view: SurfaceView) -> dict[str, tuple[float, ...]]:
    return {name: fn(view) for name, fn in FEATURES.items()}


def feature_matrix(view: SurfaceView, names: Sequence[str] = FEATURE_NAMES) -> list[list[float]]:
    """Rows = options, columns = ``names`` (default: every feature, in :data:`FEATURE_NAMES` order)."""

    scores = {name: FEATURES[name](view) for name in names}
    return [[scores[name][index] for name in names] for index in range(view.n_options)]


def rule_predictions(view: SurfaceView) -> dict[str, int | None]:
    """Every rule's prediction; ``None`` is an abstention (a tie is never broken by position)."""

    scores = feature_scores(view)
    predictions: dict[str, int | None] = {}
    for name in FEATURE_NAMES:
        for polarity in POLARITIES:
            rule = f"{name}:{'+' if polarity > 0 else '-'}"
            predictions[rule] = _unique_extreme(scores[name], polarity)
    for k, rule in enumerate(CONSTANT_RULES):
        predictions[rule] = k if k < view.n_options else None
    return predictions


# --------------------------------------------------------------------------------- statistics
#
# Exact, scipy-free.  The regularised incomplete beta is evaluated by Lentz's continued fraction
# (Numerical Recipes ``betacf``); quantiles are found by bisection.


def _betacf(a: float, b: float, x: float) -> float:
    max_iterations, eps, tiny = 400, 1e-15, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """``I_x(a, b)`` for ``a, b > 0``."""

    if a <= 0 or b <= 0:
        raise ValueError("beta parameters must be positive")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(q: float, a: float, b: float) -> float:
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if regularized_incomplete_beta(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13:
            break
    return 0.5 * (lo + hi)


def binomial_upper_tail(k: int, n: int, p: float) -> float:
    """``P(X >= k)`` for ``X ~ Binomial(n, p)``."""

    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return regularized_incomplete_beta(float(k), float(n - k + 1), p)


def binomial_lower_tail(k: int, n: int, p: float) -> float:
    """``P(X <= k)`` for ``X ~ Binomial(n, p)``."""

    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return regularized_incomplete_beta(float(n - k), float(k + 1), 1.0 - p)


def poisson_binomial_upper_tail(k: int, probabilities: Sequence[float]) -> float:
    """``P(S >= k)`` for a sum of independent Bernoulli variables with the given probabilities.

    Used when the decided examples do not all share one option count, so that "chance" is a
    mixture; with a single shared probability this is the binomial tail.
    """

    n = len(probabilities)
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    distinct = set(probabilities)
    if len(distinct) == 1:
        return binomial_upper_tail(k, n, next(iter(distinct)))
    pmf = np.zeros(n + 1, dtype=np.float64)
    pmf[0] = 1.0
    for index, p in enumerate(probabilities):
        shifted = np.zeros_like(pmf)
        shifted[1 : index + 2] = pmf[: index + 1] * p
        pmf[: index + 1] *= 1.0 - p
        pmf += shifted
    return float(min(1.0, max(0.0, pmf[k:].sum())))


def clopper_pearson(
    successes: int, trials: int, alpha: float = DEFAULT_ALPHA
) -> tuple[float, float]:
    """Exact two-sided ``1 - alpha`` interval.  ``trials == 0`` gives ``(0, 1)``."""

    if trials < 0 or not 0 <= successes <= trials:
        raise ValueError("successes must be in [0, trials]")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if trials == 0:
        return (0.0, 1.0)
    lower = 0.0 if successes == 0 else beta_quantile(alpha / 2, successes, trials - successes + 1)
    upper = (
        1.0
        if successes == trials
        else beta_quantile(1.0 - alpha / 2, successes + 1, trials - successes)
    )
    return (lower, upper)


def bonferroni_alpha(alpha: float, hypotheses: int) -> float:
    if hypotheses < 1:
        raise ValueError("at least one hypothesis is required")
    return alpha / hypotheses


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, in the input order."""

    m = len(p_values)
    order = sorted(range(m), key=lambda index: (p_values[index], index))
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        candidate = (m - rank) * p_values[index]
        running = max(running, candidate)
        adjusted[index] = min(1.0, running)
    return adjusted


# ------------------------------------------------------------------------- prediction tables


@dataclass(frozen=True)
class _Table:
    """Predictions of every rule on every example, with the labels needed to score them."""

    rules: tuple[str, ...]
    predictions: NDArray[np.int64]  # (rules, examples); -1 = abstain
    labels: NDArray[np.int64]
    n_options: NDArray[np.int64]
    family_index: NDArray[np.int64]
    family_ids: tuple[str, ...]

    @property
    def n_examples(self) -> int:
        return int(self.labels.shape[0])

    def credit(self, labels: NDArray[np.int64] | None = None) -> NDArray[np.float64]:
        target = self.labels if labels is None else labels
        chance = 1.0 / self.n_options.astype(np.float64)
        correct = (self.predictions == target[None, :]).astype(np.float64)
        abstained = (self.predictions < 0).astype(np.float64)
        return correct + abstained * chance[None, :]


def _encode_prediction(prediction: int | None) -> int:
    return -1 if prediction is None else prediction


def _build_table(examples: Sequence[Example]) -> _Table:
    if not examples:
        raise ValueError("at least one example is required")
    rows: list[list[int]] = []
    family_ids = sorted({example.family_id for example in examples})
    family_lookup = {family_id: index for index, family_id in enumerate(family_ids)}
    for example in examples:
        view = extract_surface(example.prompt, example.n_options)
        predictions = rule_predictions(view)
        rows.append([_encode_prediction(predictions[rule]) for rule in RULES])
    return _Table(
        rules=RULES,
        predictions=np.asarray(rows, dtype=np.int64).T,
        labels=np.asarray([example.correct_index for example in examples], dtype=np.int64),
        n_options=np.asarray([example.n_options for example in examples], dtype=np.int64),
        family_index=np.asarray(
            [family_lookup[example.family_id] for example in examples], dtype=np.int64
        ),
        family_ids=tuple(family_ids),
    )


def _family_bootstrap_se(
    credit: NDArray[np.float64],
    family_index: NDArray[np.int64],
    *,
    n_families: int,
    samples: int,
    seed: int,
) -> NDArray[np.float64]:
    """Standard error of each row's mean under resampling of families with replacement."""

    members = [np.flatnonzero(family_index == family) for family in range(n_families)]
    rng = np.random.default_rng(seed)
    means = np.empty((samples, credit.shape[0]), dtype=np.float64)
    for sample in range(samples):
        drawn = rng.integers(0, n_families, size=n_families)
        columns = np.concatenate([members[family] for family in drawn])
        means[sample] = credit[:, columns].mean(axis=1)
    return np.asarray(means.std(axis=0, ddof=1), dtype=np.float64)


def _permute_within_families(
    labels: NDArray[np.int64],
    family_index: NDArray[np.int64],
    rng: np.random.Generator,
) -> NDArray[np.int64]:
    family_key = family_index.astype(np.float64)
    base = np.lexsort(np.vstack([np.arange(labels.shape[0], dtype=np.float64), family_key]))
    keys = rng.random(labels.shape[0])
    order = np.lexsort(np.vstack([keys, family_key]))
    permuted = np.empty_like(labels)
    permuted[base] = labels[order]
    return permuted


def _permutation_null(
    table: _Table, *, permutations: int, seed: int, chunk: int = 100
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Max-over-family credited accuracy under label permutation within each family.

    Returns the null distribution of the max and of every rule's own accuracy (mean over the
    permutations), so a reader can see both selection noise and where each rule sits under it.
    """

    rng = np.random.default_rng(seed)
    chance = 1.0 / table.n_options.astype(np.float64)
    abstained = (table.predictions < 0).astype(np.float64) * chance[None, :]
    maxima = np.empty(permutations, dtype=np.float64)
    rule_sum = np.zeros(table.predictions.shape[0], dtype=np.float64)
    done = 0
    while done < permutations:
        size = min(chunk, permutations - done)
        permuted = np.stack(
            [_permute_within_families(table.labels, table.family_index, rng) for _ in range(size)]
        )
        correct = (table.predictions[None, :, :] == permuted[:, None, :]).astype(np.float64)
        accuracy = (correct + abstained[None, :, :]).mean(axis=2)
        maxima[done : done + size] = accuracy.max(axis=1)
        rule_sum += accuracy.sum(axis=0)
        done += size
    return maxima, rule_sum / permutations


# ------------------------------------------------------------------------------- rule report


@dataclass(frozen=True)
class RuleStats:
    rule: str
    accuracy: float  # abstentions credited 1/n_options
    n: int
    decided_n: int
    decided_correct: int
    abstain_rate: float
    decided_accuracy: float | None
    cp_lower: float  # Clopper-Pearson on the decided subset
    cp_upper: float
    clustered_se: float
    null_mean_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class RuleReport:
    version: str
    n_examples: int
    n_families: int
    n_rules: int
    alpha: float
    seed: int
    bootstrap_samples: int
    permutations: int
    rules: tuple[RuleStats, ...]  # sorted by accuracy desc, decided_n desc, name
    best_rule: str
    best_accuracy: float
    bonferroni_alpha: float
    bonferroni_lower: float  # Clopper-Pearson at alpha / n_rules on the best rule's decided subset
    bonferroni_upper: float
    null_expected_max: float
    null_sd_max: float
    null_p_value: float  # P(max over family under the null >= observed max)
    null_quantiles: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["rules"] = [stats.to_dict() for stats in self.rules]
        return payload

    def stats(self, rule: str) -> RuleStats:
        for stats in self.rules:
            if stats.rule == rule:
                return stats
        raise KeyError(rule)


def _rule_stats(
    rule: str,
    predictions: NDArray[np.int64],
    labels: NDArray[np.int64],
    n_options: NDArray[np.int64],
    *,
    alpha: float,
    clustered_se: float,
    null_mean: float,
) -> RuleStats:
    decided = predictions >= 0
    decided_n = int(decided.sum())
    decided_correct = int((predictions[decided] == labels[decided]).sum())
    n = int(labels.shape[0])
    credited = decided_correct + float((1.0 / n_options[~decided]).sum())
    lower, upper = clopper_pearson(decided_correct, decided_n, alpha)
    return RuleStats(
        rule=rule,
        accuracy=credited / n,
        n=n,
        decided_n=decided_n,
        decided_correct=decided_correct,
        abstain_rate=1.0 - decided_n / n,
        decided_accuracy=decided_correct / decided_n if decided_n else None,
        cp_lower=lower,
        cp_upper=upper,
        clustered_se=clustered_se,
        null_mean_accuracy=null_mean,
    )


def _rank_key(stats: RuleStats) -> tuple[float, int, str]:
    return (-stats.accuracy, -stats.decided_n, stats.rule)


def evaluate_rules(
    examples: Sequence[Example],
    *,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    permutations: int = DEFAULT_PERMUTATIONS,
) -> RuleReport:
    """Score every rule of the family on ``examples`` with family-wise statistics."""

    table = _build_table(examples)
    credit = table.credit()
    ses = _family_bootstrap_se(
        credit,
        table.family_index,
        n_families=len(table.family_ids),
        samples=bootstrap_samples,
        seed=seed,
    )
    null_max, null_rule_means = _permutation_null(table, permutations=permutations, seed=seed + 1)
    stats = tuple(
        _rule_stats(
            rule,
            table.predictions[index],
            table.labels,
            table.n_options,
            alpha=alpha,
            clustered_se=float(ses[index]),
            null_mean=float(null_rule_means[index]),
        )
        for index, rule in enumerate(table.rules)
    )
    ordered = tuple(sorted(stats, key=_rank_key))
    best = ordered[0]
    adjusted_alpha = bonferroni_alpha(alpha, len(table.rules))
    bonf_lower, bonf_upper = clopper_pearson(best.decided_correct, best.decided_n, adjusted_alpha)
    observed_max = best.accuracy
    quantiles = {
        f"q{int(q * 100):02d}": float(np.quantile(null_max, q)) for q in (0.5, 0.9, 0.95, 0.99)
    }
    return RuleReport(
        version=ADVERSARY_FAMILY_VERSION,
        n_examples=table.n_examples,
        n_families=len(table.family_ids),
        n_rules=len(table.rules),
        alpha=alpha,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
        permutations=permutations,
        rules=ordered,
        best_rule=best.rule,
        best_accuracy=observed_max,
        bonferroni_alpha=adjusted_alpha,
        bonferroni_lower=bonf_lower,
        bonferroni_upper=bonf_upper,
        null_expected_max=float(null_max.mean()),
        null_sd_max=float(null_max.std(ddof=1)) if permutations > 1 else 0.0,
        null_p_value=float((null_max >= observed_max - 1e-12).mean()),
        null_quantiles=quantiles,
    )


# ----------------------------------------------------------------------------- shallow models


def _sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass(frozen=True)
class ShallowModel:
    """A fitted surface model as pure data, so it can be frozen, hashed and re-run anywhere.

    ``mode == "difference"`` (all dev items have two options): trained on ``phi_0 - phi_1``
    with the option-swapped copy added, so the fit is position-antisymmetric.  ``mode ==
    "one_vs_rest"``: trained on per-option rows with the label "is the correct option".  In
    both cases prediction is the unique argmax of a per-option score; a tie abstains.
    """

    kind: str  # "logistic" | "tree"
    mode: str  # "difference" | "one_vs_rest"
    backend: str  # "sklearn" | "numpy"
    feature_names: tuple[str, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    params: dict[str, Any]

    @property
    def name(self) -> str:
        return f"model:{self.kind}:{self.mode}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "mode": self.mode,
            "backend": self.backend,
            "feature_names": list(self.feature_names),
            "scaler_mean": list(self.scaler_mean),
            "scaler_scale": list(self.scaler_scale),
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ShallowModel:
        feature_names = tuple(str(name) for name in payload["feature_names"])
        unknown = [name for name in feature_names if name not in FEATURES]
        if unknown:
            raise ValueError(f"unknown model features {unknown!r}")
        if any(name in POSITIONAL_FEATURES for name in feature_names):
            raise ValueError("a shallow model may not read option position")
        return cls(
            kind=str(payload["kind"]),
            mode=str(payload["mode"]),
            backend=str(payload["backend"]),
            feature_names=feature_names,
            scaler_mean=tuple(float(value) for value in payload["scaler_mean"]),
            scaler_scale=tuple(float(value) for value in payload["scaler_scale"]),
            params=dict(payload["params"]),
        )

    def _scaled(self, view: SurfaceView) -> NDArray[np.float64]:
        raw = np.asarray(feature_matrix(view, self.feature_names), dtype=np.float64)
        return (raw - np.asarray(self.scaler_mean)) / np.asarray(self.scaler_scale)

    def _tree_probability(self, x: NDArray[np.float64]) -> float:
        left = self.params["children_left"]
        right = self.params["children_right"]
        feature = self.params["feature"]
        threshold = self.params["threshold"]
        node = 0
        while left[node] != -1:
            node = left[node] if x[feature[node]] <= threshold[node] else right[node]
        return float(self.params["positive_fraction"][node])

    def scores(self, view: SurfaceView) -> tuple[float, ...]:
        phi = self._scaled(view)
        if self.kind == "logistic":
            coef = np.asarray(self.params["coef"], dtype=np.float64)
            return tuple(float(value) for value in phi @ coef)
        if self.kind == "tree":
            if self.mode == "difference":
                if view.n_options != 2:
                    return tuple(0.0 for _ in range(view.n_options))
                p0 = self._tree_probability(phi[0] - phi[1])
                p1 = self._tree_probability(phi[1] - phi[0])
                # antisymmetrised: score of option 0 is P(0) - P(1) from both orderings
                return (p0 - p1, p1 - p0)
            return tuple(self._tree_probability(row) for row in phi)
        raise ValueError(f"unknown model kind {self.kind!r}")

    def predict(self, view: SurfaceView) -> int | None:
        return _unique_extreme(self.scores(view), 1)


def _design(examples: Sequence[Example]) -> tuple[list[NDArray[np.float64]], list[int]]:
    matrices = [
        np.asarray(
            feature_matrix(extract_surface(example.prompt, example.n_options), MODEL_FEATURE_NAMES)
        )
        for example in examples
    ]
    return matrices, [example.correct_index for example in examples]


def _scaler(
    matrices: Sequence[NDArray[np.float64]],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    stacked = np.concatenate(matrices, axis=0)
    mean = stacked.mean(axis=0)
    scale = stacked.std(axis=0)
    scale[scale == 0.0] = 1.0
    return mean, scale


def _numpy_logistic(
    x: NDArray[np.float64], y: NDArray[np.float64], *, l2: float = 1.0, iterations: int = 100
) -> NDArray[np.float64]:
    """Ridge-penalised logistic regression by Newton-Raphson.  Deterministic."""

    weights = np.zeros(x.shape[1], dtype=np.float64)
    for _ in range(iterations):
        z = x @ weights
        p = 1.0 / (1.0 + np.exp(-z))
        gradient = x.T @ (p - y) + l2 * weights
        curvature = (x * (p * (1.0 - p))[:, None]).T @ x + l2 * np.eye(x.shape[1])
        step = np.linalg.solve(curvature, gradient)
        weights = weights - step
        if float(np.abs(step).max()) < 1e-10:
            break
    return weights


def _fit_logistic(
    x: NDArray[np.float64], y: NDArray[np.float64], *, intercept: bool, backend: str, seed: int
) -> tuple[dict[str, Any], str]:
    if backend == "sklearn":
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(
            C=1.0, fit_intercept=intercept, max_iter=2000, solver="lbfgs", random_state=seed
        )
        model.fit(x, y.astype(np.int64))
        coef = np.asarray(model.coef_[0], dtype=np.float64)
        bias = float(model.intercept_[0]) if intercept else 0.0
        return {"coef": [float(v) for v in coef], "intercept": bias}, "sklearn"
    design = np.concatenate([x, np.ones((x.shape[0], 1))], axis=1) if intercept else x
    weights = _numpy_logistic(design, y)
    coef = weights[:-1] if intercept else weights
    bias = float(weights[-1]) if intercept else 0.0
    return {"coef": [float(v) for v in coef], "intercept": bias}, "numpy"


def _fit_tree(x: NDArray[np.float64], y: NDArray[np.float64], *, seed: int) -> dict[str, Any]:
    from sklearn.tree import DecisionTreeClassifier

    tree = DecisionTreeClassifier(max_depth=3, random_state=seed)
    tree.fit(x, y.astype(np.int64))
    inner = tree.tree_
    classes = [int(c) for c in tree.classes_]
    values = np.asarray(inner.value, dtype=np.float64)[:, 0, :]
    totals = values.sum(axis=1)
    if 1 in classes:
        positive = values[:, classes.index(1)] / np.where(totals == 0, 1.0, totals)
    else:
        positive = np.zeros(values.shape[0], dtype=np.float64)
    return {
        "max_depth": 3,
        "children_left": [int(v) for v in inner.children_left],
        "children_right": [int(v) for v in inner.children_right],
        "feature": [int(v) for v in inner.feature],
        "threshold": [float(v) for v in inner.threshold],
        "positive_fraction": [float(v) for v in positive],
    }


def fit_shallow_model(
    dev: Sequence[Example],
    *,
    kind: str = "logistic",
    backend: str = "auto",
    seed: int = DEFAULT_SEED,
) -> ShallowModel:
    """Fit one shallow surface model on the development split.

    ``backend`` is ``"auto"`` (scikit-learn when importable, else numpy), ``"sklearn"`` or
    ``"numpy"``.  The decision tree requires scikit-learn.
    """

    if kind not in {"logistic", "tree"}:
        raise ValueError(f"unknown model kind {kind!r}")
    if backend == "auto":
        backend = "sklearn" if _sklearn_available() else "numpy"
    if backend not in {"sklearn", "numpy"}:
        raise ValueError(f"unknown backend {backend!r}")
    if kind == "tree" and backend != "sklearn":
        raise ValueError("the decision tree requires scikit-learn")
    if not dev:
        raise ValueError("at least one development example is required")
    matrices, labels = _design(dev)
    mean, scale = _scaler(matrices)
    scaled = [(matrix - mean) / scale for matrix in matrices]
    mode = "difference" if all(matrix.shape[0] == 2 for matrix in scaled) else "one_vs_rest"
    if mode == "difference":
        diffs = np.stack([matrix[0] - matrix[1] for matrix in scaled])
        target = np.asarray([1.0 if label == 0 else 0.0 for label in labels])
        x = np.concatenate([diffs, -diffs], axis=0)
        y = np.concatenate([target, 1.0 - target], axis=0)
        intercept = False
    else:
        x = np.concatenate(scaled, axis=0)
        y = np.concatenate(
            [
                np.asarray([1.0 if i == label else 0.0 for i in range(matrix.shape[0])])
                for matrix, label in zip(scaled, labels, strict=True)
            ]
        )
        intercept = True
    if kind == "logistic":
        params, used = _fit_logistic(x, y, intercept=intercept, backend=backend, seed=seed)
    else:
        params, used = _fit_tree(x, y, seed=seed), "sklearn"
    return ShallowModel(
        kind=kind,
        mode=mode,
        backend=used,
        feature_names=MODEL_FEATURE_NAMES,
        scaler_mean=tuple(float(v) for v in mean),
        scaler_scale=tuple(float(v) for v in scale),
        params=params,
    )


def fit_shallow_models(
    dev: Sequence[Example], *, seed: int = DEFAULT_SEED
) -> tuple[ShallowModel, ...]:
    models = [fit_shallow_model(dev, kind="logistic", seed=seed)]
    if _sklearn_available():
        models.append(fit_shallow_model(dev, kind="tree", seed=seed))
    return tuple(models)


def _score_predictions(
    predictions: Sequence[int | None], examples: Sequence[Example], *, alpha: float
) -> dict[str, Any]:
    n = len(examples)
    decided = [(p, e) for p, e in zip(predictions, examples, strict=True) if p is not None]
    decided_correct = sum(1 for p, e in decided if p == e.correct_index)
    abstain_credit = sum(
        1.0 / e.n_options for p, e in zip(predictions, examples, strict=True) if p is None
    )
    lower, upper = clopper_pearson(decided_correct, len(decided), alpha)
    return {
        "accuracy": (decided_correct + abstain_credit) / n,
        "n": n,
        "decided_n": len(decided),
        "decided_correct": decided_correct,
        "decided_accuracy": decided_correct / len(decided) if decided else None,
        "abstain_rate": 1.0 - len(decided) / n,
        "abstain_credit": abstain_credit / n,
        "cp_lower": lower,
        "cp_upper": upper,
    }


def evaluate_model(
    model: ShallowModel, examples: Sequence[Example], *, alpha: float = DEFAULT_ALPHA
) -> dict[str, Any]:
    if not examples:
        raise ValueError("at least one example is required")
    predictions = [
        model.predict(extract_surface(example.prompt, example.n_options)) for example in examples
    ]
    return {"model": model.name, **_score_predictions(predictions, examples, alpha=alpha)}


# ------------------------------------------------------------------------- develop / freeze


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _content_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenAdversaries:
    """The adversaries selected and fitted on DEVELOPMENT, frozen before EVALUATION.

    ``dev_family_ids`` is carried so :func:`evaluate_frozen` can refuse any family the
    adversaries were selected on.  ``content_hash`` covers every other field.
    """

    version: str
    seed: int
    top_k: int
    selected_rules: tuple[str, ...]
    dev_report: dict[str, Any]
    models: tuple[ShallowModel, ...]
    dev_family_ids: tuple[str, ...]
    dev_task_ids: tuple[str, ...]
    content_hash: str = field(default="")

    @property
    def adversary_names(self) -> tuple[str, ...]:
        return self.selected_rules + tuple(model.name for model in self.models)

    def payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seed": self.seed,
            "top_k": self.top_k,
            "selected_rules": list(self.selected_rules),
            "dev_report": self.dev_report,
            "models": [model.to_dict() for model in self.models],
            "dev_family_ids": list(self.dev_family_ids),
            "dev_task_ids": list(self.dev_task_ids),
        }

    def with_hash(self) -> FrozenAdversaries:
        return FrozenAdversaries(**{**self.__dict__, "content_hash": _content_hash(self.payload())})

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "content_hash": self.content_hash}


def to_json(frozen: FrozenAdversaries) -> str:
    if frozen.content_hash != _content_hash(frozen.payload()):
        raise ValueError("content hash does not match the frozen payload")
    return _canonical_json(frozen.to_dict())


def from_json(text: str) -> FrozenAdversaries:
    payload = json.loads(text)
    frozen = FrozenAdversaries(
        version=str(payload["version"]),
        seed=int(payload["seed"]),
        top_k=int(payload["top_k"]),
        selected_rules=tuple(str(rule) for rule in payload["selected_rules"]),
        dev_report=dict(payload["dev_report"]),
        models=tuple(ShallowModel.from_dict(model) for model in payload["models"]),
        dev_family_ids=tuple(str(family) for family in payload["dev_family_ids"]),
        dev_task_ids=tuple(str(task) for task in payload["dev_task_ids"]),
        content_hash=str(payload["content_hash"]),
    )
    expected = _content_hash(frozen.payload())
    if frozen.content_hash != expected:
        raise ValueError("content hash mismatch: the frozen adversaries were altered")
    for rule in frozen.selected_rules:
        if rule not in RULES:
            raise ValueError(f"unknown rule {rule!r} in frozen adversaries")
    return frozen


def develop_and_freeze(
    dev: Sequence[Example],
    *,
    top_k: int = 3,
    seed: int = DEFAULT_SEED,
    alpha: float = DEFAULT_ALPHA,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    permutations: int = DEFAULT_PERMUTATIONS,
) -> FrozenAdversaries:
    """Select the ``top_k`` rules by DEV accuracy and fit the shallow models; then freeze.

    The full DEV table is recorded so the selection is auditable.  Ranking is by credited
    accuracy, then by the number of decided examples (a live rule beats an always-abstaining one
    at equal accuracy), then by name.
    """

    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    report = evaluate_rules(
        dev,
        seed=seed,
        alpha=alpha,
        bootstrap_samples=bootstrap_samples,
        permutations=permutations,
    )
    selected = tuple(stats.rule for stats in report.rules[:top_k])
    models = fit_shallow_models(dev, seed=seed)
    frozen = FrozenAdversaries(
        version=ADVERSARY_FAMILY_VERSION,
        seed=seed,
        top_k=top_k,
        selected_rules=selected,
        dev_report=report.to_dict(),
        models=models,
        dev_family_ids=tuple(sorted({example.family_id for example in dev})),
        dev_task_ids=tuple(sorted({example.task_id for example in dev})),
    )
    return frozen.with_hash()


# --------------------------------------------------------------------------- frozen evaluation


@dataclass(frozen=True)
class AdversaryStats:
    name: str
    kind: str  # "rule" | "model"
    accuracy: float
    n: int
    decided_n: int
    decided_correct: int
    decided_accuracy: float | None
    abstain_rate: float
    abstain_credit: float
    cp_lower: float
    cp_upper: float
    chance: float | None  # mean 1/n_options over the decided examples; None if none decided
    p_value: float  # one-sided, decided examples only, against chance (1.0 if none decided)
    holm_p: float

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ArmEvaluation:
    arm_id: str
    n_examples: int
    n_families: int
    n_adversaries: int
    adversaries: tuple[AdversaryStats, ...]
    best: str
    best_accuracy: float
    best_holm_p: float
    best_bonferroni_lower: float
    best_bonferroni_upper: float
    significant: bool

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["adversaries"] = [stats.to_dict() for stats in self.adversaries]
        return payload

    def stats(self, name: str) -> AdversaryStats:
        for stats in self.adversaries:
            if stats.name == name:
                return stats
        raise KeyError(name)


@dataclass(frozen=True)
class FrozenEvaluation:
    version: str
    frozen_hash: str
    alpha: float
    n_adversaries: int
    arms: tuple[ArmEvaluation, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.__dict__)
        payload["arms"] = [arm.to_dict() for arm in self.arms]
        return payload

    def arm(self, arm_id: str) -> ArmEvaluation:
        for arm in self.arms:
            if arm.arm_id == arm_id:
                return arm
        raise KeyError(arm_id)


def _chance_p_value(
    predictions: Sequence[int | None], examples: Sequence[Example]
) -> tuple[float | None, float]:
    decided = [(p, e) for p, e in zip(predictions, examples, strict=True) if p is not None]
    if not decided:
        return (None, 1.0)
    probabilities = [1.0 / e.n_options for _, e in decided]
    correct = sum(1 for p, e in decided if p == e.correct_index)
    return (
        sum(probabilities) / len(probabilities),
        poisson_binomial_upper_tail(correct, probabilities),
    )


def _evaluate_arm(
    arm_id: str,
    examples: Sequence[Example],
    frozen: FrozenAdversaries,
    *,
    alpha: float,
) -> ArmEvaluation:
    views = [extract_surface(example.prompt, example.n_options) for example in examples]
    rule_rows = [rule_predictions(view) for view in views]
    predictions: dict[str, tuple[str, list[int | None]]] = {}
    for rule in frozen.selected_rules:
        predictions[rule] = ("rule", [row[rule] for row in rule_rows])
    for model in frozen.models:
        predictions[model.name] = ("model", [model.predict(view) for view in views])
    raw: list[tuple[str, str, dict[str, Any], float | None, float]] = []
    for name, (kind, preds) in predictions.items():
        scored = _score_predictions(preds, examples, alpha=alpha)
        chance, p_value = _chance_p_value(preds, examples)
        raw.append((name, kind, scored, chance, p_value))
    holm = holm_adjust([entry[4] for entry in raw])
    stats = tuple(
        AdversaryStats(
            name=name,
            kind=kind,
            accuracy=scored["accuracy"],
            n=scored["n"],
            decided_n=scored["decided_n"],
            decided_correct=scored["decided_correct"],
            decided_accuracy=scored["decided_accuracy"],
            abstain_rate=scored["abstain_rate"],
            abstain_credit=scored["abstain_credit"],
            cp_lower=scored["cp_lower"],
            cp_upper=scored["cp_upper"],
            chance=chance,
            p_value=p_value,
            holm_p=adjusted,
        )
        for (name, kind, scored, chance, p_value), adjusted in zip(raw, holm, strict=True)
    )
    best = min(stats, key=lambda s: (-s.accuracy, s.holm_p, -s.decided_n, s.name))
    adjusted_alpha = bonferroni_alpha(alpha, len(stats))
    lower, upper = clopper_pearson(best.decided_correct, best.decided_n, adjusted_alpha)
    return ArmEvaluation(
        arm_id=arm_id,
        n_examples=len(examples),
        n_families=len({example.family_id for example in examples}),
        n_adversaries=len(stats),
        adversaries=stats,
        best=best.name,
        best_accuracy=best.accuracy,
        best_holm_p=best.holm_p,
        best_bonferroni_lower=lower,
        best_bonferroni_upper=upper,
        significant=best.holm_p < alpha,
    )


def evaluate_frozen(
    frozen: FrozenAdversaries,
    eval_examples: Sequence[Example],
    *,
    alpha: float = DEFAULT_ALPHA,
) -> FrozenEvaluation:
    """Evaluate the frozen adversaries per ``arm_id`` on families never seen in development."""

    if not eval_examples:
        raise ValueError("at least one evaluation example is required")
    if frozen.content_hash != _content_hash(frozen.payload()):
        raise ValueError("frozen adversaries do not match their content hash")
    seen = set(frozen.dev_family_ids)
    overlap = sorted({example.family_id for example in eval_examples} & seen)
    if overlap:
        raise ValueError(
            f"{len(overlap)} evaluation families were used in development: {overlap[:5]}"
        )
    by_arm: dict[str, list[Example]] = {}
    for example in eval_examples:
        by_arm.setdefault(example.arm_id, []).append(example)
    arms = tuple(
        _evaluate_arm(arm_id, by_arm[arm_id], frozen, alpha=alpha) for arm_id in sorted(by_arm)
    )
    return FrozenEvaluation(
        version=ADVERSARY_FAMILY_VERSION,
        frozen_hash=frozen.content_hash,
        alpha=alpha,
        n_adversaries=len(frozen.adversary_names),
        arms=arms,
    )


# ------------------------------------------------------------------------- twin invariance


def _group_by_family(examples: Iterable[Example]) -> dict[str, list[Example]]:
    groups: dict[str, list[Example]] = {}
    for example in examples:
        groups.setdefault(example.family_id, []).append(example)
    return groups


def twin_invariance_report(examples: Sequence[Example]) -> dict[str, Any]:
    """Which features are pinned at chance by the twin construction (audit item C3d).

    A twin family has exactly two items with two options each.  For every feature the report
    gives the fraction of twin pairs on which the per-option score vector is identical across
    the pair (and, separately, reversed, for option-rotated twins).  On an identical-score pair
    with flipped truth either polarity of the feature scores exactly one of the two items
    right, so its accuracy on such pairs is 0.5 by construction; ``identical_pair_accuracy``
    is that value measured, and ``pinned`` says whether the feature is pinned on every twin.
    """

    groups = _group_by_family(examples)
    pairs = [
        (group[0], group[1])
        for _, group in sorted(groups.items())
        if len(group) == 2 and all(example.n_options == 2 for example in group)
    ]
    features: dict[str, dict[str, Any]] = {}
    if not pairs:
        return {
            "n_families": len(groups),
            "n_twin_pairs": 0,
            "flipped_truth_fraction": None,
            "features": features,
        }
    views = [
        (extract_surface(a.prompt, a.n_options), extract_surface(b.prompt, b.n_options))
        for a, b in pairs
    ]
    flipped = [a.correct_index != b.correct_index for a, b in pairs]
    for name, fn in FEATURES.items():
        identical = 0
        reversed_count = 0
        pinned_credit = {1: 0.0, -1: 0.0}
        pinned_pairs = 0
        credit = {1: 0.0, -1: 0.0}
        for (view_a, view_b), (a, b), flip in zip(views, pairs, flipped, strict=True):
            scores_a, scores_b = fn(view_a), fn(view_b)
            same = scores_a == scores_b
            identical += same
            reversed_count += scores_a == tuple(reversed(scores_b))
            for polarity in POLARITIES:
                pair_credit = 0.0
                for scores, example in ((scores_a, a), (scores_b, b)):
                    prediction = _unique_extreme(scores, polarity)
                    if prediction is None:
                        pair_credit += 0.5
                    elif prediction == example.correct_index:
                        pair_credit += 1.0
                credit[polarity] += pair_credit
                if same and flip:
                    pinned_credit[polarity] += pair_credit
            if same and flip:
                pinned_pairs += 1
        total = 2 * len(pairs)
        features[name] = {
            "identical_fraction": identical / len(pairs),
            "reversed_fraction": reversed_count / len(pairs),
            "pinned": identical == len(pairs) and all(flipped),
            "identical_pair_accuracy": (
                {
                    "+": pinned_credit[1] / (2 * pinned_pairs),
                    "-": pinned_credit[-1] / (2 * pinned_pairs),
                }
                if pinned_pairs
                else None
            ),
            "twin_accuracy": {"+": credit[1] / total, "-": credit[-1] / total},
        }
    return {
        "n_families": len(groups),
        "n_twin_pairs": len(pairs),
        "flipped_truth_fraction": sum(flipped) / len(pairs),
        "features": features,
    }


__all__ = [
    "ADVERSARY_FAMILY_VERSION",
    "ANSWER_MARKER",
    "CANDIDATE_MENTION_FEATURES",
    "CONSTANT_RULES",
    "DEFAULT_ALPHA",
    "DEFAULT_SEED",
    "ENVELOPE_STOPLIST",
    "FEATURES",
    "FEATURE_NAMES",
    "MAX_OPTIONS",
    "MODEL_FEATURE_NAMES",
    "OPTIONS_MARKER",
    "POLAR_RULES",
    "POSITIONAL_FEATURES",
    "POSITIONAL_RULES",
    "QUESTION_MARKER",
    "RULES",
    "STATE_MARKER",
    "AdversaryStats",
    "ArmEvaluation",
    "Example",
    "FrozenAdversaries",
    "FrozenEvaluation",
    "RuleReport",
    "RuleStats",
    "ShallowModel",
    "SurfaceView",
    "beta_quantile",
    "binomial_lower_tail",
    "binomial_upper_tail",
    "bonferroni_alpha",
    "clopper_pearson",
    "develop_and_freeze",
    "evaluate_frozen",
    "evaluate_model",
    "evaluate_rules",
    "extract_surface",
    "feature_matrix",
    "feature_scores",
    "fit_shallow_model",
    "fit_shallow_models",
    "from_json",
    "holm_adjust",
    "option_labels",
    "poisson_binomial_upper_tail",
    "regularized_incomplete_beta",
    "rule_predictions",
    "to_json",
    "twin_invariance_report",
]
