"""A SURFACE adversary family over the rendered prompt only.

Inputs to every adversary: the prompt string and the option count.  No canonical state, no
metadata, no oracle.  Ties abstain (credit 1/2) and are never broken by position.

If ``arena.experiments.rendered_prompt_adversary`` exists at import time (another agent is
writing it) its ``extract_surface`` / ``FEATURES`` / ``evaluate_rules`` / ``develop_and_freeze``
/ ``evaluate_frozen`` are preferred; see :func:`resolve_family`.  Otherwise this module's own
implementation is used.  The caller records which one ran.

Numerics are numpy only (no scipy, no sklearn): exact binomial tails, exact Clopper-Pearson by
bisection, a depth-<=3 CART tree and an intercept-free logistic regression, both made
antisymmetric in the option pair so that no model can encode "always A".
"""

from __future__ import annotations

import gzip
import hashlib
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .common import ParsedPrompt, parse_prompt

WINDOW = 32
NGRAM = 3
_COLON_TOKEN = re.compile(r"[A-Za-z]+:[A-Za-z0-9_]+")
_OPEN, _CLOSE = "[{(", "]})"


# ------------------------------------------------------------------------------ features


def _ngrams(text: str, n: int = NGRAM) -> set[str]:
    return {text[i : i + n] for i in range(max(0, len(text) - n + 1))}


def _mentions(text: str, needle: str) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        i = text.find(needle, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1


def _bracket_depth_before(text: str, pos: int) -> int:
    seg = text[:pos]
    return sum(seg.count(c) for c in _OPEN) - sum(seg.count(c) for c in _CLOSE)


def _windows(text: str, positions: Sequence[int], width: int) -> str:
    return "\n".join(text[max(0, p - WINDOW) : p + width + WINDOW] for p in positions)


def _gzip_len(text: str) -> int:
    return len(gzip.compress(text.encode("utf-8"), compresslevel=6))


def per_option_features(parsed: ParsedPrompt, which: int) -> dict[str, float]:
    """Surface statistics of ONE candidate as it appears in the prompt.  No structure walk."""

    cand = parsed.candidates[which]
    other = parsed.candidates[1 - which] if len(parsed.candidates) == 2 else ""
    state, question = parsed.state, parsed.question
    n = max(1, len(state))
    pos = _mentions(state, cand)
    first = pos[0] if pos else n
    last = pos[-1] if pos else n
    second = pos[1] if len(pos) > 1 else n
    f: dict[str, float] = {}
    f["first_pos"] = float(first)
    f["first_frac"] = first / n
    f["second_pos"] = float(second)
    f["last_pos"] = float(last)
    f["mean_frac"] = float(np.mean(pos)) / n if pos else 1.0
    f["span"] = float(last - first)
    f["count_state"] = float(len(pos))
    f["count_prompt"] = float(parsed.prompt.count(cand))
    f["n_lines_mentioning"] = float(len({state.count("\n", 0, p) for p in pos}))
    f["line_index_first"] = float(state.count("\n", 0, first)) if pos else float(state.count("\n"))
    f["bracket_depth_first"] = float(_bracket_depth_before(state, first)) if pos else 0.0
    f["bracket_depth_max"] = float(max((_bracket_depth_before(state, p) for p in pos), default=0))
    f["option_len"] = float(len(parsed.option_texts[which]))
    f["cand_len"] = float(len(cand))
    f["alpha_first"] = 1.0 if cand < other else 0.0
    f["digit_sum"] = float(sum(int(c) for c in cand if c.isdigit()))
    f["n_digits"] = float(sum(c.isdigit() for c in cand))
    f["hash_bucket"] = float(int(hashlib.sha256(cand.encode()).hexdigest()[:8], 16) % 97)
    win = _windows(state, pos, len(cand))
    wg = _ngrams(win)
    f["window_ngram_diversity"] = float(len(wg))
    f["window_overlap_question"] = float(len(wg & _ngrams(question)))
    anchors = [t for t in _COLON_TOKEN.findall(question) if t not in (cand, other)]
    anchor_pos = [p for t in anchors for p in _mentions(state, t)]
    anchor_win = _windows(state, anchor_pos, max((len(t) for t in anchors), default=0))
    f["window_overlap_anchor"] = float(len(wg & _ngrams(anchor_win)))
    if pos and anchor_pos:
        f["min_dist_to_anchor"] = float(min(abs(p - q) for p in pos for q in anchor_pos))
    else:
        f["min_dist_to_anchor"] = float(n)
    f["gzip_delta"] = float(_gzip_len(state) - _gzip_len(state.replace(cand, "")))
    return f


FEATURES: tuple[str, ...] = (
    "first_pos",
    "first_frac",
    "second_pos",
    "last_pos",
    "mean_frac",
    "span",
    "count_state",
    "count_prompt",
    "n_lines_mentioning",
    "line_index_first",
    "bracket_depth_first",
    "bracket_depth_max",
    "option_len",
    "cand_len",
    "alpha_first",
    "digit_sum",
    "n_digits",
    "hash_bucket",
    "window_ngram_diversity",
    "window_overlap_question",
    "window_overlap_anchor",
    "min_dist_to_anchor",
    "gzip_delta",
)


def extract_surface(prompt: str, n_options: int) -> np.ndarray:
    """(n_options, F) feature matrix from the prompt string alone."""

    parsed = parse_prompt(prompt, n_options)
    rows = [per_option_features(parsed, i) for i in range(n_options)]
    return np.asarray([[r[k] for k in FEATURES] for r in rows], dtype=float)


# --------------------------------------------------------------------------------- rules

# A rule maps the per-option feature matrix to a predicted index or None (abstain).
Rule = Callable[[np.ndarray], int | None]


def _argmax_rule(j: int, sign: float) -> Rule:
    def rule(x: np.ndarray) -> int | None:
        v = sign * x[:, j]
        best = np.flatnonzero(v == v.max())
        return int(best[0]) if len(best) == 1 else None

    return rule


def rule_family() -> dict[str, Rule]:
    rules: dict[str, Rule] = {
        "const_first_option": lambda x: 0,
        "const_last_option": lambda x: int(x.shape[0] - 1),
    }
    for j, name in enumerate(FEATURES):
        rules[f"max:{name}"] = _argmax_rule(j, +1.0)
        rules[f"min:{name}"] = _argmax_rule(j, -1.0)
    return rules


RULES = rule_family()


def credit(pred: int | None, label: int) -> float:
    if pred is None:
        return 0.5
    return 1.0 if pred == label else 0.0


def evaluate_rules(
    X: Sequence[np.ndarray], y: Sequence[int], rules: dict[str, Rule] | None = None
) -> dict[str, dict[str, float]]:
    rules = RULES if rules is None else rules
    out: dict[str, dict[str, float]] = {}
    for name, rule in rules.items():
        preds = [rule(x) for x in X]
        c = np.asarray([credit(p, l) for p, l in zip(preds, y, strict=True)])
        decided = np.asarray([p is not None for p in preds])
        out[name] = {
            "credited_accuracy": float(c.mean()),
            "n": int(len(c)),
            "n_decided": int(decided.sum()),
            "n_correct_decided": int(c[decided].sum()),
            "abstain_rate": float(1.0 - decided.mean()),
        }
    return out


# -------------------------------------------------------------------------------- models


def pair_difference(x: np.ndarray) -> np.ndarray:
    """Antisymmetric representation of a two-option pair: f(opt0) - f(opt1)."""

    if x.shape[0] != 2:
        raise ValueError("models are defined for two-option items")
    return x[0] - x[1]


@dataclass
class Standardiser:
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, D: np.ndarray) -> Standardiser:
        # Mirrored training data has zero mean by construction; scale only.
        scale = D.std(axis=0)
        scale[scale == 0] = 1.0
        return cls(np.zeros(D.shape[1]), scale)

    def __call__(self, D: np.ndarray) -> np.ndarray:
        return (D - self.mean) / self.scale


class LogisticNoIntercept:
    """L2-regularised logistic regression without intercept: antisymmetric by construction."""

    def __init__(self, l2: float = 1e-2, iters: int = 300) -> None:
        self.l2, self.iters = l2, iters
        self.w: np.ndarray | None = None
        self.std: Standardiser | None = None

    def fit(self, D: np.ndarray, y: np.ndarray) -> LogisticNoIntercept:
        Dm = np.vstack([D, -D])
        ym = np.concatenate([y, 1 - y]).astype(float)
        self.std = Standardiser.fit(Dm)
        Z = self.std(Dm)
        w = np.zeros(Z.shape[1])
        for _ in range(self.iters):  # Newton steps with L2 ridge
            p = 1.0 / (1.0 + np.exp(-Z @ w))
            g = Z.T @ (p - ym) / len(ym) + self.l2 * w
            W = p * (1 - p)
            H = (Z * W[:, None]).T @ Z / len(ym) + self.l2 * np.eye(Z.shape[1])
            step = np.linalg.solve(H, g)
            w = w - step
            if np.abs(step).max() < 1e-8:
                break
        self.w = w
        return self

    def score(self, D: np.ndarray) -> np.ndarray:
        assert self.w is not None and self.std is not None
        return self.std(D) @ self.w

    def predict(self, D: np.ndarray) -> list[int | None]:
        s = self.score(D)
        return [None if abs(v) < 1e-12 else int(v < 0) for v in s]


class Tree:
    """Greedy CART (gini), depth <= 3, made antisymmetric at prediction time."""

    def __init__(self, max_depth: int = 3, min_leaf: int = 8, n_thresholds: int = 32) -> None:
        self.max_depth, self.min_leaf, self.n_thresholds = max_depth, min_leaf, n_thresholds
        self.root: dict[str, Any] | None = None

    @staticmethod
    def _gini(y: np.ndarray) -> float:
        if len(y) == 0:
            return 0.0
        p = y.mean()
        return float(2 * p * (1 - p))

    def _grow(self, D: np.ndarray, y: np.ndarray, depth: int) -> dict[str, Any]:
        leaf = {"leaf": True, "p": float(y.mean()) if len(y) else 0.5, "n": int(len(y))}
        if depth >= self.max_depth or len(y) < 2 * self.min_leaf or y.min() == y.max():
            return leaf
        best: tuple[float, int, float] | None = None
        parent = self._gini(y) * len(y)
        for j in range(D.shape[1]):
            col = D[:, j]
            uniq = np.unique(col)
            if len(uniq) < 2:
                continue
            qs = np.quantile(uniq, np.linspace(0, 1, self.n_thresholds + 2)[1:-1])
            for t in np.unique(qs):
                left = col <= t
                nl, nr = int(left.sum()), int((~left).sum())
                if nl < self.min_leaf or nr < self.min_leaf:
                    continue
                gain = parent - self._gini(y[left]) * nl - self._gini(y[~left]) * nr
                if best is None or gain > best[0] + 1e-12:
                    best = (gain, j, float(t))
        if best is None or best[0] <= 1e-12:
            return leaf
        _, j, t = best
        left = D[:, j] <= t
        return {
            "leaf": False,
            "feature": j,
            "threshold": t,
            "left": self._grow(D[left], y[left], depth + 1),
            "right": self._grow(D[~left], y[~left], depth + 1),
        }

    def fit(self, D: np.ndarray, y: np.ndarray) -> Tree:
        Dm = np.vstack([D, -D])
        ym = np.concatenate([y, 1 - y]).astype(int)
        self.root = self._grow(Dm, ym, 0)
        return self

    def _prob(self, d: np.ndarray) -> float:
        node = self.root
        assert node is not None
        while not node["leaf"]:
            node = node["left"] if d[node["feature"]] <= node["threshold"] else node["right"]
        return float(node["p"])

    def predict(self, D: np.ndarray) -> list[int | None]:
        out: list[int | None] = []
        for d in D:
            p = 0.5 * (self._prob(d) + (1.0 - self._prob(-d)))  # antisymmetrised P(label = 1)
            out.append(None if abs(p - 0.5) < 1e-9 else int(p > 0.5))
        return out

    def describe(self) -> Any:
        def walk(node: dict[str, Any]) -> Any:
            if node["leaf"]:
                return {"leaf": True, "p": round(node["p"], 4), "n": node["n"]}
            return {
                "feature": FEATURES[node["feature"]],
                "threshold": round(node["threshold"], 6),
                "left": walk(node["left"]),
                "right": walk(node["right"]),
            }

        assert self.root is not None
        return walk(self.root)


# ------------------------------------------------------------------------ exact statistics


def _log_binom_pmf(n: int, p: float) -> np.ndarray:
    k = np.arange(n + 1)
    logc = math.lgamma(n + 1) - np.array([math.lgamma(i + 1) + math.lgamma(n - i + 1) for i in k])
    if p <= 0.0:
        out = np.full(n + 1, -np.inf)
        out[0] = 0.0
        return out
    if p >= 1.0:
        out = np.full(n + 1, -np.inf)
        out[n] = 0.0
        return out
    return logc + k * math.log(p) + (n - k) * math.log1p(-p)


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) exactly."""

    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    lp = _log_binom_pmf(n, p)[k:]
    m = lp.max()
    return float(np.exp(m) * np.exp(lp - m).sum())


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) exactly."""

    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    lp = _log_binom_pmf(n, p)[: k + 1]
    m = lp.max()
    return float(np.exp(m) * np.exp(lp - m).sum())


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided (1 - alpha) interval by bisection on the binomial tails."""

    if n == 0:
        return (0.0, 1.0)

    def solve(f: Callable[[float], float], target: float, lo: float, hi: float) -> float:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if f(mid) > target:
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)

    lower = 0.0 if k == 0 else solve(lambda p: binom_sf(k, n, p), alpha / 2, 0.0, 1.0)
    upper = 1.0 if k == n else solve(lambda p: 1.0 - binom_cdf(k, n, p), 1.0 - alpha / 2, 0.0, 1.0)
    # the upper solve above finds p with P(X<=k|p) = alpha/2
    return (lower, upper)


def holm(pvals: Sequence[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        val = min(1.0, (m - rank) * pvals[idx])
        running = max(running, val)
        adjusted[idx] = running
    return adjusted


def bonferroni(pvals: Sequence[float]) -> list[float]:
    m = len(pvals)
    return [min(1.0, m * p) for p in pvals]


# --------------------------------------------------------------- develop / freeze / evaluate


@dataclass
class FrozenFamily:
    rule_names: list[str]
    tree: Tree
    logistic: LogisticNoIntercept
    dev_rule_scores: dict[str, dict[str, float]]
    surface: str
    level: int

    @property
    def names(self) -> list[str]:
        return [*self.rule_names, "model:tree_d3", "model:logistic"]

    def predictions(self, X: Sequence[np.ndarray]) -> dict[str, list[int | None]]:
        D = np.asarray([pair_difference(x) for x in X])
        preds = {name: [RULES[name](x) for x in X] for name in self.rule_names}
        preds["model:tree_d3"] = self.tree.predict(D)
        preds["model:logistic"] = self.logistic.predict(D)
        return preds


def develop_and_freeze(
    X_dev: Sequence[np.ndarray], y_dev: Sequence[int], *, top_k: int = 3, surface: str, level: int
) -> FrozenFamily:
    """Select the top-k rules (polarity included) and fit both models on DEVELOPMENT only."""

    scores = evaluate_rules(X_dev, y_dev)
    ranked = sorted(scores, key=lambda n: (-scores[n]["credited_accuracy"], n))
    chosen = ranked[:top_k]
    D = np.asarray([pair_difference(x) for x in X_dev])
    y = np.asarray(y_dev, dtype=int)
    return FrozenFamily(
        rule_names=chosen,
        tree=Tree().fit(D, y),
        logistic=LogisticNoIntercept().fit(D, y),
        dev_rule_scores=scores,
        surface=surface,
        level=level,
    )


def credit_matrix(preds: dict[str, list[int | None]], y: Sequence[int]) -> tuple[list[str], np.ndarray]:
    names = list(preds)
    C = np.asarray(
        [[credit(p, l) for p, l in zip(preds[n], y, strict=True)] for n in names], dtype=float
    ).T
    return names, C


def evaluate_frozen(
    frozen: FrozenFamily,
    X_eval: Sequence[np.ndarray],
    y_eval: Sequence[int],
    families: Sequence[str],
    *,
    n_perm: int = 2000,
    seed: int = 20260907,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Evaluate the FROZEN family on the evaluation split with exact intervals, Holm and
    Bonferroni over the frozen adversaries, and a within-family label-permutation null for the
    max-over-family credited accuracy."""

    preds = frozen.predictions(X_eval)
    names, C = credit_matrix(preds, y_eval)
    y = np.asarray(y_eval, dtype=int)
    per: dict[str, Any] = {}
    pvals: list[float] = []
    for j, name in enumerate(names):
        p = preds[name]
        decided = np.asarray([v is not None for v in p])
        n_dec = int(decided.sum())
        k_dec = int(C[decided, j].sum())
        acc = float(C[:, j].mean())
        n = len(y)
        p_one_sided = binom_sf(k_dec, n_dec, 0.5) if n_dec else 1.0
        pvals.append(p_one_sided)
        lo_d, hi_d = clopper_pearson(k_dec, n_dec, alpha) if n_dec else (0.0, 1.0)
        k_cred = int(math.floor(C[:, j].sum()))
        lo_c, hi_c = clopper_pearson(k_cred, n, alpha)
        per[name] = {
            "credited_accuracy": acc,
            "n": n,
            "n_decided": n_dec,
            "n_correct_decided": k_dec,
            "decided_accuracy": (k_dec / n_dec) if n_dec else None,
            "abstain_rate": float(1.0 - decided.mean()),
            "cp95_decided": [lo_d, hi_d],
            "cp95_credited_floor": [lo_c, hi_c],
            "p_one_sided_exact_decided_vs_0.5": p_one_sided,
        }
    holm_adj, bonf_adj = holm(pvals), bonferroni(pvals)
    for j, name in enumerate(names):
        per[name]["p_holm"] = holm_adj[j]
        per[name]["p_bonferroni"] = bonf_adj[j]
        per[name]["significant_holm_0.05"] = bool(holm_adj[j] <= alpha)

    # Within-family label permutation null for the max over the frozen family.
    fam_index = {f: i for i, f in enumerate(sorted(set(families)))}
    fam_of = np.asarray([fam_index[f] for f in families])
    rng = np.random.default_rng(seed)
    observed_max = float(C.mean(axis=0).max())
    null = np.empty(n_perm)
    for t in range(n_perm):
        flip_fam = rng.random(len(fam_index)) < 0.5
        f = flip_fam[fam_of].astype(float)[:, None]
        Cp = C + f * (1.0 - 2.0 * C)
        null[t] = Cp.mean(axis=0).max()
    best = max(names, key=lambda n: per[n]["credited_accuracy"])
    return {
        "frozen_family": names,
        "per_adversary": per,
        "best": best,
        "best_credited_accuracy": per[best]["credited_accuracy"],
        "permutation_null_max": {
            "n_permutations": n_perm,
            "observed_max": observed_max,
            "null_mean": float(null.mean()),
            "null_q95": float(np.quantile(null, 0.95)),
            "null_max": float(null.max()),
            "p_value": float((null >= observed_max - 1e-12).mean()),
        },
    }


def resolve_family() -> tuple[str, dict[str, Any]]:
    """Prefer a shared arena module if it exists; fall back to this implementation."""

    try:  # lazy: the module may or may not exist in this worktree
        from arena.experiments import rendered_prompt_adversary as shared  # type: ignore

        needed = ("extract_surface", "FEATURES", "evaluate_rules", "develop_and_freeze", "evaluate_frozen")
        if all(hasattr(shared, n) for n in needed):
            return "arena.experiments.rendered_prompt_adversary", {n: getattr(shared, n) for n in needed}
        return "research.phase8.transitive.adversary (shared module present but incomplete)", {}
    except ImportError:
        return "research.phase8.transitive.adversary", {}
