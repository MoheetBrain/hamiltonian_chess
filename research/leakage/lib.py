"""Generic, model-free predictors for the Arena World v0 NEXT_ACTION target.

Nothing here is hand-coded per domain: every rule is INDUCED from a fitting split by a
search over a small, generic hypothesis space, then evaluated on held-out examples.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

HOLE = ("__HOLE__",)

# ---------------------------------------------------------------- tree utilities


def walk(node: Any, path: tuple = ()) -> list[tuple[tuple, Any]]:
    """Every (path, subtree) pair inside a canonical expression dict."""
    out = [(path, node)]
    if isinstance(node, dict):
        for i, child in enumerate(node.get("args", ())):
            out.extend(walk(child, path + ("args", i)))
    return out


def scalar_sources(roots: dict[str, Any]) -> dict[tuple, Any]:
    """Every scalar visible inside the named expression roots, keyed by an addressable path."""
    out: dict[tuple, Any] = {}
    for name, root in roots.items():
        if root is None:
            continue
        forest = root if isinstance(root, list) else [root]
        for j, tree in enumerate(forest):
            for path, node in walk(tree):
                if isinstance(node, dict):
                    for key in ("op", "sort", "value"):
                        if key in node and not isinstance(node[key], (dict, list)):
                            out[(name, j) + path + (key,)] = node[key]
    return out


def subtree_sources(roots: dict[str, Any]) -> dict[tuple, Any]:
    out: dict[tuple, Any] = {}
    for name, root in roots.items():
        if root is None:
            continue
        forest = root if isinstance(root, list) else [root]
        for j, tree in enumerate(forest):
            for path, node in walk(tree):
                if isinstance(node, dict):
                    out[(name, j) + path] = node
    return out


# ---------------------------------------------------------------- anti-unification


def antiunify(values: list[Any]) -> Any:
    """Structural anti-unification down to scalar holes. Returns a skeleton with HOLE marks."""
    first = values[0]
    if all(v == first for v in values[1:]):
        return first
    if isinstance(first, dict) and all(isinstance(v, dict) for v in values):
        keys = set(first)
        if all(set(v) == keys for v in values):
            return {k: antiunify([v[k] for v in values]) for k in sorted(keys)}
        return HOLE
    if isinstance(first, list) and all(isinstance(v, list) for v in values):
        n = len(first)
        if all(len(v) == n for v in values):
            return [antiunify([v[i] for v in values]) for i in range(n)]
        return HOLE
    return HOLE


def hole_paths(skel: Any, path: tuple = ()) -> list[tuple]:
    if skel == HOLE:
        return [path]
    if isinstance(skel, dict):
        out = []
        for k in sorted(skel):
            out.extend(hole_paths(skel[k], path + (k,)))
        return out
    if isinstance(skel, list):
        out = []
        for i, item in enumerate(skel):
            out.extend(hole_paths(item, path + (i,)))
        return out
    return []


def get_at(value: Any, path: tuple) -> Any:
    for step in path:
        value = value[step]
    return value


def fill(skel: Any, assignment: dict[tuple, Any], path: tuple = ()) -> Any:
    if skel == HOLE:
        return assignment[path]
    if isinstance(skel, dict):
        return {k: fill(skel[k], assignment, path + (k,)) for k in skel}
    if isinstance(skel, list):
        return [fill(item, assignment, path + (i,)) for i, item in enumerate(skel)]
    return skel


# ---------------------------------------------------------------- affix transforms


def induce_affix(sources: list[str], targets: list[str]) -> tuple[str, str, str, str] | None:
    """Learn t = NP + core + NS given s = OP + core + OS, with cores identical."""
    if not sources:
        return None
    op = common_prefix(sources)
    os_ = common_suffix(sources, len(op))
    np = common_prefix(targets)
    ns = common_suffix(targets, len(np))
    for s, t in zip(sources, targets):
        core = s[len(op): len(s) - len(os_) if os_ else len(s)]
        if np + core + ns != t:
            return None
    return op, os_, np, ns


def apply_affix(rule: tuple[str, str, str, str], s: str) -> str | None:
    op, os_, np, ns = rule
    if not s.startswith(op) or (os_ and not s.endswith(os_)):
        return None
    core = s[len(op): len(s) - len(os_) if os_ else len(s)]
    return np + core + ns


def common_prefix(items: list[str]) -> str:
    if not items:
        return ""
    out = items[0]
    for s in items[1:]:
        i = 0
        while i < min(len(out), len(s)) and out[i] == s[i]:
            i += 1
        out = out[:i]
    return out


def common_suffix(items: list[str], reserve: int = 0) -> str:
    if not items:
        return ""
    out = items[0][reserve:]
    for s in items[1:]:
        i = 0
        while i < min(len(out), len(s)) and out[-1 - i] == s[-1 - i]:
            i += 1
        out = out[len(out) - i:] if i else ""
    return out


def induce_join(s1: list[str], s2: list[str], targets: list[str]) -> tuple[str, str, str] | None:
    """Learn t = A + s1 + B + s2 + C."""
    parts = None
    for a, b, t in zip(s1, s2, targets):
        i = t.find(a)
        if i < 0:
            return None
        j = t.find(b, i + len(a))
        if j < 0:
            return None
        cand = (t[:i], t[i + len(a): j], t[j + len(b):])
        if parts is None:
            parts = cand
        elif parts != cand:
            return None
    return parts


# ---------------------------------------------------------------- arithmetic ops

def _safe(fn):
    def wrapped(*a):
        try:
            r = fn(*a)
        except Exception:
            return None
        if isinstance(r, float) and (math.isnan(r) or math.isinf(r)):
            return None
        return r
    return wrapped


BINARY_OPS: dict[str, Any] = {
    "add": _safe(lambda x, y: x + y),
    "sub": _safe(lambda x, y: x - y),
    "rsub": _safe(lambda x, y: y - x),
    "mul": _safe(lambda x, y: x * y),
    "floordiv": _safe(lambda x, y: x // y if y else None),
    "rfloordiv": _safe(lambda x, y: y // x if x else None),
}
UNARY_OPS: dict[str, Any] = {
    "identity": _safe(lambda x: x),
    "isqrt": _safe(lambda x: math.isqrt(x) if isinstance(x, int) and x >= 0 else None),
    "succ": _safe(lambda x: x + 1),
    "pred": _safe(lambda x: x - 1),
    "neg": _safe(lambda x: -x),
}
