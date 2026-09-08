"""Phase 8 preparation: rendered-prompt adversary audit of ``transitive_dependency``.

CPU-only, offline, ZERO model calls.  Nothing here re-scores V7 or reinterprets a recorded
sentinel.  This package prepares a POSSIBLE second mechanism for the founder programme; it may
only be acted on after the precondition founder pilot has completed.

This module holds what every script shares: the salt scheme, the V5Probe -> MaterialisedItem
adapter, the frozen V1 generator entry point, a research-local V2 CANDIDATE generator, the
founder-surface renderer, and the prompt-only option parser the adversary uses.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from arena.canonical.schema import CanonicalAction, CanonicalState, EvidenceNode
from arena.experiments.fitness_v4 import (
    DISTRACTOR_OBJECTS,
    _distractors,
    _h,
    _hex,
    _identifier_objects,
    _relation,
    _shuffled,
    _state,
    ancestors,
)
from arena.experiments.fitness_v5 import (
    LADDERS,
    POSITIVE_VARIANTS,
    SWAPPED_VARIANTS,
    V5Probe,
    V5Slice,
    _option,
    derive_probe_family,
)
from arena.experiments.game_r_formal_v1 import (
    MaterialisedItem,
    SyntaxGuidePolicy,
    build_prompt,
    founder_genome,
)
from arena.genome.seeds import SEED_GENOME_BY_ID

MECHANISM = "transitive_dependency"
LEVELS = (1, 2, 3)
N_FAMILIES = 400
DEV_FAMILIES = range(0, 200)
EVAL_FAMILIES = range(200, 400)
SALT_BASE = 8_000_000
SALT_LEVEL_STRIDE = 100_000
SURFACES = tuple(SEED_GENOME_BY_ID)
GENERATORS = ("v1_frozen", "v2_candidate")
V2_GENERATOR_VERSION = "research-transitive-dependency-v2-candidate-0.1.0"

# Every previously used salt for this mechanism lives in [EXPERIMENT_SEED + 1000, +1000 + 399 +
# 300] = [20261907, 20262606] (V5/V7 DEV: index < 12; A3 audit: index < 400; V4 SCOUT adds
# 100000).  The range below is 8_100_000 .. 8_300_399 -- more than twelve million away.
def family_salt(level: int, index: int) -> int:
    return SALT_BASE + level * SALT_LEVEL_STRIDE + index


def hops_for_level(level: int) -> int:
    return int(LADDERS[MECHANISM][level]["hops"])


@dataclass(frozen=True, slots=True)
class Item:
    generator: str
    level: int
    family_index: int
    family_id: str
    variant: str
    state: CanonicalState
    options: tuple[CanonicalAction, CanonicalAction]
    expected_index: int
    question: str
    salt: int

    @property
    def names(self) -> tuple[str, str]:
        return (str(self.options[0].arguments[0].value), str(self.options[1].arguments[0].value))

    @property
    def split(self) -> str:
        return "dev" if self.family_index in DEV_FAMILIES else "eval"

    @property
    def is_positive(self) -> bool:
        return self.variant in POSITIVE_VARIANTS

    @property
    def is_swapped(self) -> bool:
        return self.variant in SWAPPED_VARIANTS


def to_materialised(item: Item) -> MaterialisedItem:
    """Adapter: what ``game_r_formal_v1.build_prompt`` needs, from a probe-shaped record."""

    return MaterialisedItem(
        task_id=f"{item.family_id}:{item.variant}",
        family_id=item.family_id,
        level=item.level,
        variant=item.variant,
        question=item.question,
        canonical_state=item.state,
        options=item.options,
        correct_index=item.expected_index,
        provenance={"generator": item.generator, "generator_salt": item.salt},
    )


def probe_to_item(probe: V5Probe, index: int, salt: int) -> Item:
    return Item(
        generator="v1_frozen",
        level=probe.level,
        family_id=probe.family_id,
        family_index=index,
        variant=probe.variant.value,
        state=probe.state,
        options=probe.options,
        expected_index=probe.expected_index,
        question=probe.question,
        salt=salt,
    )


# ------------------------------------------------------------ V2 CANDIDATE generator (research)


def dependency_family_v2(hops: int, salt: str) -> dict[str, Any]:
    """Research-local candidate for a balanced-by-construction dependency generator.

    Two changes relative to ``fitness_v4._dependency_family`` (the frozen V1), both aimed at the
    A9 recipe *"build the block that names the candidates once, share it across the twin, carry
    the truth in a block that never mentions them"*:

    1. **Symmetric cross-links.**  V1 lets ``other[0]`` depend on ``attached[junction]``, so the
       attached chain's junction node carries one extra in-reference.  When ``junction == hops-1``
       (probability ``1/hops``) that node IS the answer, and its mention count leaks the label.
       V2 removes that edge and adds two dangling decoy roots, one per chain, each depending on
       that chain's junction node.  Neither decoy is reachable from ``e:leaf``, so the ancestor
       closure is unchanged; both candidates now have identical in-degree, always.
    2. **Counterfactual by re-pointing the leaf, not by swapping chains.**  V1 builds the
       counterfactual as ``build(q_chain, p_chain, ...)`` so every node changes slot; V2 keeps
       every node in place and changes only ``e:leaf``'s single dependency (``p[0]`` -> ``q[0]``).
       The two twins therefore differ in exactly one identifier that is neither candidate.

    The answer set, question, option construction, distractors and shuffle discipline are V1's.
    """

    length = hops + 1

    def chain(label: str) -> list[str]:
        return [f"e:{_hex(f'{salt}|{label}|{index}')}" for index in range(length)]

    p_chain, q_chain = chain("p"), chain("q")
    decoys = [f"e:{_hex(f'{salt}|decoy|{index}')}" for index in range(2)]
    all_ids = [*p_chain, *q_chain, *decoys, "e:leaf"]
    if len(set(all_ids)) != len(all_ids):
        raise ValueError("evidence identifiers collided")
    junction = _h(f"{salt}|junction", hops)

    def build(leaf_target: str | None) -> tuple[EvidenceNode, ...]:
        nodes: list[EvidenceNode] = []
        for chain_nodes, decoy in ((p_chain, decoys[0]), (q_chain, decoys[1])):
            for index, node_id in enumerate(chain_nodes):
                deps: tuple[str, ...] = (
                    (chain_nodes[index + 1],) if index + 1 < len(chain_nodes) else ()
                )
                nodes.append(EvidenceNode(node_id, "VERIFIED", deps, "arena-native", None))
            nodes.append(
                EvidenceNode(decoy, "VERIFIED", (chain_nodes[junction],), "arena-native", None)
            )
        leaf_deps = (leaf_target,) if leaf_target else ()
        nodes.append(EvidenceNode("e:leaf", "UNKNOWN", leaf_deps, "arena-native", None))
        return tuple(_shuffled(nodes, f"{salt}|evidence"))

    a, b = p_chain[hops - 1], q_chain[hops - 1]
    objects = (*_identifier_objects((a, b)), *_distractors(_hex(salt), DISTRACTOR_OBJECTS))
    goal = _relation("transitive_dependency_of", "e:leaf")
    original = _state(goal=goal, objects=objects, evidence=build(p_chain[0]))
    counter = _state(goal=goal, objects=objects, evidence=build(q_chain[0]))
    destroyed = _state(goal=goal, objects=objects, evidence=build(None))

    # Independent truth checks, identical in form to V1's.
    if a not in ancestors(original.evidence_dependencies, "e:leaf"):
        raise ValueError("original answer is not an ancestor of e:leaf")
    if b in ancestors(original.evidence_dependencies, "e:leaf"):
        raise ValueError("original alternate is an ancestor of e:leaf")
    if b not in ancestors(counter.evidence_dependencies, "e:leaf"):
        raise ValueError("counterfactual answer is not an ancestor of e:leaf")
    if a in ancestors(counter.evidence_dependencies, "e:leaf"):
        raise ValueError("counterfactual alternate is an ancestor of e:leaf")
    if ancestors(destroyed.evidence_dependencies, "e:leaf"):
        raise ValueError("destroyed state still has ancestors")
    # Hop distance of the answer must be exactly ``hops`` (same question text as V1).
    if _hop_distance(original.evidence_dependencies, "e:leaf", a) != hops:
        raise ValueError("original answer is not exactly hops steps away")
    if _hop_distance(counter.evidence_dependencies, "e:leaf", b) != hops:
        raise ValueError("counterfactual answer is not exactly hops steps away")
    # Balance-by-construction invariant: the twins differ ONLY in e:leaf's dependency tuple.
    diff = [
        (x, y)
        for x, y in zip(original.evidence_dependencies, counter.evidence_dependencies, strict=True)
        if x != y
    ]
    if len(diff) != 1 or diff[0][0].evidence_id != "e:leaf" or diff[0][1].evidence_id != "e:leaf":
        raise ValueError("V2 twins differ somewhere other than the leaf dependency")
    question = (
        "Which evidence ID is a transitive dependency of e:leaf, reached by following the "
        f"dependencies field {hops} step(s) from e:leaf?"
    )
    return {
        "original": original,
        "counterfactual": counter,
        "destroyed": destroyed,
        "answer_a": a,
        "answer_b": b,
        "question": question,
        "junction": junction,
    }


def _hop_distance(evidence: Iterable[EvidenceNode], start: str, target: str) -> int | None:
    graph = {node.evidence_id: node.dependencies for node in evidence}
    frontier = [start]
    seen = {start}
    distance = 0
    while frontier:
        distance += 1
        nxt: list[str] = []
        for node in frontier:
            for dep in graph.get(node, ()):
                if dep == target:
                    return distance
                if dep not in seen:
                    seen.add(dep)
                    nxt.append(dep)
        frontier = nxt
    return None


def hop_distances(state: CanonicalState, start: str = "e:leaf") -> dict[str, int]:
    """BFS hop distance from ``start`` along the dependencies field (diagnostic use only)."""

    graph = {node.evidence_id: node.dependencies for node in state.evidence_dependencies}
    out: dict[str, int] = {}
    frontier = [start]
    distance = 0
    while frontier:
        distance += 1
        nxt: list[str] = []
        for node in frontier:
            for dep in graph.get(node, ()):
                if dep not in out:
                    out[dep] = distance
                    nxt.append(dep)
        frontier = nxt
    return out


# --------------------------------------------------------------------- population builders


def v1_family(level: int, index: int) -> list[Item]:
    salt = family_salt(level, index)
    probes = derive_probe_family(MECHANISM, level, V5Slice.DEV, salt, None)
    return [
        probe_to_item(p, index, salt)
        for p in probes
        if p.variant.value in POSITIVE_VARIANTS or p.variant.value in SWAPPED_VARIANTS
    ]


def v2_family(level: int, index: int) -> list[Item]:
    salt = family_salt(level, index)
    fam = dependency_family_v2(hops_for_level(level), f"{V2_GENERATOR_VERSION}|{level}|{salt}")
    options = (_option(0, fam["answer_a"], fam["answer_b"]), _option(1, fam["answer_b"], fam["answer_a"]))
    swapped = (options[1], options[0])
    family_id = f"v2cand:{MECHANISM}:l{level}:{salt}"

    def make(variant: str, state: CanonicalState, expected: int, displayed: Any) -> Item:
        return Item(
            generator="v2_candidate",
            level=level,
            family_index=index,
            family_id=family_id,
            variant=variant,
            state=state,
            options=displayed,
            expected_index=expected,
            question=fam["question"],
            salt=salt,
        )

    return [
        make("ORIGINAL", fam["original"], 0, options),
        make("COUNTERFACTUAL", fam["counterfactual"], 1, options),
        make("SWAPPED_ORIGINAL", fam["original"], 1, swapped),
        make("SWAPPED_COUNTERFACTUAL", fam["counterfactual"], 0, swapped),
    ]


def build_population(generator: str, level: int, n_families: int = N_FAMILIES) -> list[Item]:
    builder = {"v1_frozen": v1_family, "v2_candidate": v2_family}[generator]
    items: list[Item] = []
    for index in range(n_families):
        items.extend(builder(level, index))
    return items


# ------------------------------------------------------------------------------- rendering

_GENOMES = {surface: founder_genome(surface) for surface in SURFACES}


def render(item: Item, surface: str) -> str:
    """The exact bytes the harness would send for this item on this founder surface."""

    return build_prompt(
        _GENOMES[surface], to_materialised(item), guide_policy=SyntaxGuidePolicy.SHARED_CONSTANT
    )


# ------------------------------------------------------------- prompt-only option parsing

_TOKEN = re.compile(r"[A-Za-z0-9_:.\-~]+")


@dataclass(frozen=True, slots=True)
class ParsedPrompt:
    """Everything the adversary is allowed to see, derived from the prompt string alone."""

    prompt: str
    question: str
    state: str
    option_texts: tuple[str, ...]
    candidates: tuple[str, ...]


def parse_prompt(prompt: str, n_options: int) -> ParsedPrompt:
    """Locate the fixed envelope slots by their constant labels; no canonical state is used.

    The candidate string of each option is the token that appears in that option's text and in
    no other option's text.  Every founder surface renders the proposed identifier verbatim, so
    this yields exactly one token per option (checked, and asserted by the caller).
    """

    head, sep, tail = prompt.partition("\nOPTIONS:\n")
    if not sep:
        raise ValueError("prompt has no OPTIONS block")
    body = tail[: tail.rfind("\nANSWER:")]
    parts = re.split(r"(?m)^OPTION_([A-Z]): ", body)
    labels = parts[1::2]
    texts = [t.strip() for t in parts[2::2]]
    if len(labels) != n_options:
        raise ValueError(f"expected {n_options} options, parsed {len(labels)}")
    q_start = head.find("QUESTION: ")
    s_start = head.find("CURRENT STATE:\n")
    question = head[q_start + len("QUESTION: ") : s_start].strip()
    state = head[s_start + len("CURRENT STATE:\n") :]
    token_sets = [set(_TOKEN.findall(t)) for t in texts]
    candidates: list[str] = []
    for i, toks in enumerate(token_sets):
        others = set().union(*(token_sets[j] for j in range(n_options) if j != i))
        unique = sorted(toks - others)
        if len(unique) != 1:
            raise ValueError(f"option {i} has {len(unique)} distinguishing tokens: {unique}")
        candidates.append(unique[0])
    return ParsedPrompt(prompt, question, state, tuple(texts), tuple(candidates))


# ------------------------------------------------------------------- shared-module bridge


def shared_adversary_module() -> Any:
    """Lazy import of ``arena.experiments.rendered_prompt_adversary``; ``None`` if unavailable."""

    try:
        from arena.experiments import rendered_prompt_adversary as shared
    except Exception:  # noqa: BLE001 - the module may be mid-edit in a concurrent worktree
        return None
    needed = (
        "extract_surface",
        "Example",
        "FEATURES",
        "RULES",
        "evaluate_rules",
        "develop_and_freeze",
        "evaluate_frozen",
        "twin_invariance_report",
        "rule_predictions",
    )
    return shared if all(hasattr(shared, name) for name in needed) else None


def validate_v1_family(level: int, index: int) -> None:
    """Run V5's own family validator (NativeVerifier + balance/swap assertions) on a V1 family."""

    from arena.experiments.fitness_v5 import validate_probe_family

    salt = family_salt(level, index)
    validate_probe_family(derive_probe_family(MECHANISM, level, V5Slice.DEV, salt, None))


def validate_v2_items(items: Sequence[Item]) -> None:
    """The V2 candidate has no V5 validator; apply the same verifier and leakage checks."""

    from arena.verifier.native import NativeVerifier

    verifier = NativeVerifier()
    for item in items:
        result = verifier.verify_state(item.state)
        if not result.accepted:
            raise ValueError(f"V2 state rejected: {result.issues}")
        if item.state.legal_actions or item.state.plausible_invalid_actions:
            raise ValueError("V2 observation leaks action membership")
        if any(option.expected_usefulness != 0.0 for option in item.options):
            raise ValueError("V2 option leaks oracle usefulness")
    positives = [i for i in items if i.is_positive]
    if len(positives) != 2 or positives[0].expected_index == positives[1].expected_index:
        raise ValueError("V2 positives are not a balanced twin")
    if positives[0].options != positives[1].options:
        raise ValueError("V2 twins do not share one option tuple")
