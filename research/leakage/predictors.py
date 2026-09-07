"""Induced, model-free predictors for each field of the NEXT_ACTION target."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from research.leakage.lib import (
    BINARY_OPS,
    HOLE,
    UNARY_OPS,
    antiunify,
    apply_affix,
    fill,
    get_at,
    hole_paths,
    induce_affix,
    induce_join,
    subtree_sources,
    walk,
)


def expression_roots(obs: dict) -> dict[str, Any]:
    return {
        "goal": obs.get("goal"),
        "assumptions": obs.get("assumptions", []),
        "propositions": obs.get("propositions", []),
        "obligations": [o["proposition"] for o in obs.get("obligations", [])],
    }


def scalars(obs: dict) -> dict[tuple, Any]:
    """Every scalar a rule may read out of the projected observation."""
    out: dict[tuple, Any] = {}
    for name, root in expression_roots(obs).items():
        forest = root if isinstance(root, list) else ([] if root is None else [root])
        for j, tree in enumerate(forest):
            for path, node in walk(tree):
                if isinstance(node, dict):
                    for key in ("op", "sort", "value"):
                        if key in node and not isinstance(node[key], (dict, list)):
                            out[(name, j) + path + (key,)] = node[key]
    for j, obj in enumerate(obs.get("objects", [])):
        for key in ("object_id", "type_name", "unit"):
            out[("object", j, key)] = obj.get(key)
    for j, b in enumerate(obs.get("bindings", [])):
        for key in ("binder_id", "variable", "type_name", "scope_id", "binder_kind"):
            out[("binding", j, key)] = b.get(key)
    for j, s in enumerate(obs.get("local_scope", [])):
        out[("scope", j)] = s
    for j, o in enumerate(obs.get("obligations", [])):
        out[("obligation_id", j)] = o.get("obligation_id")
    for j, e in enumerate(obs.get("evidence_dependencies", [])):
        out[("evidence_id", j)] = e.get("evidence_id")
    sid = obs.get("state_id", "")
    out[("state_id",)] = sid
    for j, seg in enumerate(sid.split(":")):
        out[("sid_seg", j)] = seg
    return out


def subtrees(obs: dict) -> dict[tuple, Any]:
    return subtree_sources(expression_roots(obs))


# ------------------------------------------------------------------ field rules


class ConstRule:
    kind = "constant"
    families = frozenset({"constant"})

    def __init__(self, value): self.value = value
    def predict(self, obs): return self.value


class CopyFieldRule:
    kind = "copy_observation_field"
    families = frozenset({"copy"})

    def __init__(self, field): self.field = field
    def predict(self, obs): return obs.get(self.field)


class AffixRule:
    kind = "string_affix_rewrite"
    families = frozenset({"affix"})

    def __init__(self, source_path, rule): self.source_path, self.rule = source_path, rule

    def predict(self, obs):
        s = scalars(obs).get(self.source_path)
        return apply_affix(self.rule, s) if isinstance(s, str) else None


class LookupRule:
    kind = "lookup"

    def __init__(self, key_path, table, families=("lookup",)):
        self.key_path, self.table = key_path, table
        self.families = frozenset(families)

    def predict(self, obs):
        return self.table.get(scalars(obs).get(self.key_path))


class SubtreeCopyRule:
    kind = "subtree_copy"
    families = frozenset({"subtree_copy"})

    def __init__(self, path): self.path = path
    def predict(self, obs):
        node = subtrees(obs).get(self.path)
        return None if node is None else [node]


class SkeletonRule:
    kind = "skeleton_with_induced_holes"

    def __init__(self, skel, fills, families):
        self.skel, self.fills, self.families = skel, fills, frozenset(families)

    def predict(self, obs):
        sc, st = scalars(obs), subtrees(obs)
        assign: dict[tuple, Any] = {}
        for hole, spec in self.fills.items():
            v = _apply_fill(spec, sc, st)
            if v is None and spec[0] != "const":
                return None
            assign[hole] = v
        try:
            return fill(self.skel, assign)
        except Exception:
            return None


def _apply_fill(spec, sc, st):
    tag = spec[0]
    if tag == "const":
        return spec[1]
    if tag == "scalar":
        return sc.get(spec[1])
    if tag == "subtree":
        return st.get(spec[1])
    if tag == "affix":
        s = sc.get(spec[1])
        return apply_affix(spec[2], s) if isinstance(s, str) else None
    if tag == "join":
        a, b = sc.get(spec[1]), sc.get(spec[2])
        if not isinstance(a, str) or not isinstance(b, str):
            return None
        pre, mid, post = spec[3]
        return pre + a + mid + b + post
    if tag == "unary":
        x = sc.get(spec[1])
        return None if not isinstance(x, (int, float)) or isinstance(x, bool) else UNARY_OPS[spec[2]](x)
    if tag == "binary":
        x, y = sc.get(spec[1]), sc.get(spec[2])
        ok = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
        return None if not (ok(x) and ok(y)) else BINARY_OPS[spec[3]](x, y)
    raise ValueError(tag)


# ------------------------------------------------------------------ induction


def induce_hole_fill(values, obs_list, *, allow_arith: bool):
    """Find the simplest generic rule producing `values` from the observations."""
    if all(v == values[0] for v in values):
        return ("const", values[0]), "constant"
    scal = [scalars(o) for o in obs_list]
    sub = [subtrees(o) for o in obs_list]
    keys = set(scal[0])
    for s in scal[1:]:
        keys &= set(s)
    # 1. verbatim scalar copy
    for k in sorted(keys, key=repr):
        if all(s[k] == v for s, v in zip(scal, values)):
            return ("scalar", k), "scalar_copy"
    # 2. whole subtree copy (for structural holes)
    skeys = set(sub[0])
    for s in sub[1:]:
        skeys &= set(s)
    for k in sorted(skeys, key=repr):
        if all(s[k] == v for s, v in zip(sub, values)):
            return ("subtree", k), "subtree_copy"
    # 3. learned string affix rewrite
    if all(isinstance(v, str) for v in values):
        for k in sorted(keys, key=repr):
            src = [s[k] for s in scal]
            if all(isinstance(x, str) for x in src):
                rule = induce_affix(src, list(values))
                if rule:
                    return ("affix", k, rule), "string_rewrite"
        strkeys = [k for k in sorted(keys, key=repr) if all(isinstance(s[k], str) for s in scal)]
        for i, k1 in enumerate(strkeys):
            for k2 in strkeys:
                if k1 == k2:
                    continue
                parts = induce_join([s[k1] for s in scal], [s[k2] for s in scal], list(values))
                if parts:
                    return ("join", k1, k2, parts), "string_join"
    # 4. arithmetic (Tier C only)
    if allow_arith and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        numeric = [k for k in sorted(keys, key=repr)
                   if all(isinstance(s[k], (int, float)) and not isinstance(s[k], bool) for s in scal)]
        for name, fn in UNARY_OPS.items():
            for k in numeric:
                if all(fn(s[k]) == v for s, v in zip(scal, values)):
                    return ("unary", k, name), "arithmetic"
        for name, fn in BINARY_OPS.items():
            for k1 in numeric:
                for k2 in numeric:
                    if k1 == k2:
                        continue
                    if all(fn(s[k1], s[k2]) == v for s, v in zip(scal, values)):
                        return ("binary", k1, k2, name), "arithmetic"
    return None, None


def induce_arguments_rule(obs_list, targets, *, allow_arith: bool):
    """Induce a rule for the `arguments` field over one homogeneous group."""
    if all(t == targets[0] for t in targets):
        return ConstRule(targets[0])
    if all(len(t) == 1 for t in targets):
        sub = [subtrees(o) for o in obs_list]
        keys = set(sub[0])
        for s in sub[1:]:
            keys &= set(s)
        for k in sorted(keys, key=repr):
            if all(s[k] == t[0] for s, t in zip(sub, targets)):
                return SubtreeCopyRule(k)
    skel = antiunify(list(targets))
    if skel == HOLE:
        return None
    holes = hole_paths(skel)
    fills, families = {}, set()
    for h in holes:
        values = [get_at(t, h) for t in targets]
        spec, fam = induce_hole_fill(values, obs_list, allow_arith=allow_arith)
        if spec is None:
            return None
        fills[h] = spec
        families.add(fam)
    return SkeletonRule(skel, fills, families or {"constant"})
