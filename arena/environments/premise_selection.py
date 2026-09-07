"""Premise-selection task family (auxiliary measurement environment, NOT Gold).

The decision under test: given a Lean 4 proof state (goal + local context) and ``K`` candidate
premise names, select the premise that the valid next transition actually cites.

Provenance
----------
Source of every item: LeanDojo Benchmark 4 (``leandojo 2.0.0``), mathlib4 commit
``29dcec074de168ac2bf835a77ef68bbe069194c5``.  The **only** permitted trace source is
``<benchmark>/random/train.json``; ``corpus.jsonl`` supplies declaration text, per-file imports
and the scope relation.  The four sealed evaluation pools are refused at load time by
:func:`guard_source_path` -- reading them would invalidate the experiment, so this module makes
that mechanically impossible rather than merely discouraged.

Leak discipline
---------------
:class:`Transition` is a *sanitised* record.  It structurally cannot carry the tactic text or the
``annotated_tactic`` markup: those live only on :class:`RawStep`, which the item generator never
sees.  A rendered item therefore cannot leak the answer through the tactic even by programming
mistake.  :func:`audit_item_leaks` re-checks the rendered strings against the raw step.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SPEC_VERSION = "premise-selection-v1"
GENERATOR_VERSION = "premise_selection.generator.v1"
DATASET_COMMIT = "29dcec074de168ac2bf835a77ef68bbe069194c5"

#: Split-bearing files that must never be opened.  Keyed by the two trailing path components so a
#: different benchmark root cannot smuggle them past the guard.
SEALED_RELPATHS: frozenset[str] = frozenset(
    {
        "novel_premises/val.json",
        "novel_premises/test.json",
        "random/val.json",
        "random/test.json",
    }
)

#: The single permitted trace source.  Its split label is implied by the file, not stored in it.
PERMITTED_TRACE_RELPATH = "random/train.json"
PERMITTED_SPLIT = "train"

#: Redaction token substituted for the gold premise's own name inside an L0 explicit-positive hint.
REDACTION = "<PREMISE>"

OPTION_LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_DECL_KEYWORD_RE = re.compile(
    r"\b(theorem|lemma|def|abbrev|instance|structure|inductive|class|axiom|opaque)\b"
)
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class SealedSplitError(RuntimeError):
    """Raised when a sealed promotion/OOD pool is about to be read."""


def guard_source_path(path: str | Path) -> Path:
    """Return ``path`` unless it names one of the sealed evaluation pools.

    The check is on the trailing ``<dir>/<file>`` pair, so it fires regardless of benchmark root
    and regardless of whether the path is relative or absolute.
    """
    resolved = Path(path)
    parts = resolved.parts
    if len(parts) >= 2:
        tail = f"{parts[-2]}/{parts[-1]}"
        if tail in SEALED_RELPATHS:
            raise SealedSplitError(
                f"refusing to read sealed split {tail!r}: it is a PROMOTION/OOD pool "
                "(see artifacts/manifests/SEALED_SPLITS.json)"
            )
    return resolved


# --------------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PremiseRef:
    """A premise citation as recorded in ``annotated_tactic[1]``."""

    full_name: str
    def_path: str


@dataclass(frozen=True, slots=True)
class RawStep:
    """The unsanitised traced tactic.  Audit-only: never reaches the generator."""

    proof_id: str
    step_index: int
    tactic: str
    annotated_tactic: str
    state_before: str
    state_after: str
    premises: tuple[PremiseRef, ...]


@dataclass(frozen=True, slots=True)
class Transition:
    """Sanitised transition.  Carries no tactic text and no oracle marker."""

    proof_id: str
    file_path: str
    thm: str
    step_index: int
    state_before: str
    premises: tuple[PremiseRef, ...]
    split: str = PERMITTED_SPLIT


@dataclass(frozen=True, slots=True)
class CorpusDecl:
    """A declaration from ``corpus.jsonl``."""

    full_name: str
    path: str
    kind: str
    decl_keyword: str
    signature: str
    order: int


@dataclass(frozen=True, slots=True)
class PremiseOption:
    """One rendered option.  ``tier`` is ``"gold"`` for the correct option."""

    full_name: str
    def_path: str
    tier: str


@dataclass(frozen=True, slots=True)
class PremiseItem:
    """A generated item.  ``answer_index`` is metadata; it never enters :attr:`prompt`."""

    item_id: str
    level: str
    prompt: str
    options: tuple[PremiseOption, ...]
    answer_index: int
    k: int
    provenance: dict[str, Any]
    features: dict[str, Any]

    @property
    def answer_label(self) -> str:
        return OPTION_LABELS[self.answer_index]

    def to_json(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "level": self.level,
            "prompt": self.prompt,
            "options": [
                {"full_name": o.full_name, "def_path": o.def_path, "tier": o.tier}
                for o in self.options
            ],
            "answer_index": self.answer_index,
            "k": self.k,
            "provenance": self.provenance,
            "features": self.features,
        }


# --------------------------------------------------------------------------------------------
# Streaming reader
# --------------------------------------------------------------------------------------------


def stream_traced_theorems(path: str | Path, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Yield top-level theorem objects from a LeanDojo split file without loading it whole.

    ``random/train.json`` is 373 MB; ``json.load`` on it is wasteful.  The file is one JSON array,
    so successive elements are decoded with :meth:`json.JSONDecoder.raw_decode` over a sliding
    buffer.
    """
    source = guard_source_path(path)
    decoder = json.JSONDecoder()
    buffer = ""
    pos = 0
    emitted = 0
    eof = False
    separators = " \n\r\t,"
    with source.open(encoding="utf-8") as handle:
        while True:
            char = handle.read(1)
            if char == "":
                return
            if char == "[":
                break
        while True:
            while pos < len(buffer) and buffer[pos] in separators:
                pos += 1
            if pos < len(buffer) and buffer[pos] == "]":
                return
            try:
                obj, end = decoder.raw_decode(buffer, pos)
            except ValueError:
                if eof:
                    return
                chunk = handle.read(1 << 22)
                if not chunk:
                    eof = True
                    continue
                if pos:
                    buffer = buffer[pos:]
                    pos = 0
                buffer += chunk
                continue
            pos = end
            yield obj
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def raw_steps(theorem: dict[str, Any]) -> Iterator[RawStep]:
    """Yield every traced tactic of one theorem object as a :class:`RawStep`."""
    file_path = theorem["file_path"]
    thm = theorem["full_name"]
    proof_id = f"{file_path}::{thm}"
    for step_index, tac in enumerate(theorem.get("traced_tactics") or []):
        annotated = tac.get("annotated_tactic") or ["", []]
        refs = tuple(
            PremiseRef(full_name=p["full_name"], def_path=p.get("def_path", ""))
            for p in (annotated[1] if len(annotated) > 1 else [])
        )
        yield RawStep(
            proof_id=proof_id,
            step_index=step_index,
            tactic=tac.get("tactic", ""),
            annotated_tactic=annotated[0] if annotated else "",
            state_before=tac.get("state_before", ""),
            state_after=tac.get("state_after", ""),
            premises=refs,
        )


def sanitise(theorem: dict[str, Any], step: RawStep) -> Transition:
    """Project a :class:`RawStep` onto the leak-safe :class:`Transition`."""
    return Transition(
        proof_id=step.proof_id,
        file_path=theorem["file_path"],
        thm=theorem["full_name"],
        step_index=step.step_index,
        state_before=step.state_before,
        premises=step.premises,
        split=PERMITTED_SPLIT,
    )


_NAME_RE_CACHE: dict[str, tuple[re.Pattern[str], re.Pattern[str] | None]] = {}


def _name_patterns(full_name: str) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
    cached = _NAME_RE_CACHE.get(full_name)
    if cached is None:
        full = re.compile(rf"(?<![A-Za-z0-9_.']){re.escape(full_name)}(?![A-Za-z0-9_'])")
        short_name = full_name.rsplit(".", 1)[-1]
        # The short pattern deliberately allows a preceding ``.`` so that a goal printing
        # ``M.Indep X`` counts as an occurrence of ``Matroid.Indep``.
        short = (
            re.compile(rf"(?<![A-Za-z0-9_']){re.escape(short_name)}(?![A-Za-z0-9_'])")
            if short_name and short_name != full_name
            else None
        )
        cached = (full, short)
        _NAME_RE_CACHE[full_name] = cached
    return cached


def name_occurs_in(text: str, full_name: str) -> bool:
    """True when ``full_name`` or its final component occurs as a standalone token in ``text``.

    Token-anchored on both sides: a bare substring test would fire on ``em`` inside "statement"
    and ``id`` inside "elided", which are not occurrences of the premise at all.
    """
    full, short = _name_patterns(full_name)
    if full.search(text):
        return True
    return bool(short and short.search(text))


def is_usable(step: RawStep) -> bool:
    """A transition is usable when it yields a well-formed single-answer item.

    Three preregistered well-formedness conditions, all fixed before any shortcut measurement:

    1. Exactly one cited premise.  With two or more, the item has no single correct answer, and
       any other cited premise used as a distractor would be a second correct option.
    2. A non-empty proof state.
    3. The cited premise's name (full, or its final component) does not already occur in the
       proof state.  When it does -- common for definitions, e.g. gold ``homology'.pi`` against a
       goal that prints ``pi f g w`` -- the answer is literally printed in the prompt and the item
       degenerates into string matching rather than premise selection.
    """
    if len(step.premises) != 1 or not step.state_before.strip():
        return False
    return not name_occurs_in(step.state_before, step.premises[0].full_name)


# --------------------------------------------------------------------------------------------
# Lexical helpers
# --------------------------------------------------------------------------------------------


def name_tokens(full_name: str) -> tuple[str, ...]:
    """Lower-cased identifier tokens of a Lean name: namespace parts, ``_`` parts, camel splits."""
    out: list[str] = []
    for chunk in full_name.replace(".", "_").split("_"):
        if not chunk:
            continue
        for piece in _CAMEL_SPLIT_RE.split(chunk):
            if piece:
                out.append(piece.lower())
    return tuple(out)


def state_tokens(state: str) -> list[str]:
    return [m.group(0).lower() for m in _IDENT_RE.finditer(state)]


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def multiset_overlap(left: Sequence[str], right: Sequence[str]) -> float:
    """Normalised bag-of-tokens overlap: shared multiplicity / size of the smaller bag."""
    if not left or not right:
        return 0.0
    la, lb = Counter(left), Counter(right)
    shared = sum((la & lb).values())
    return shared / min(len(left), len(right))


def module_of(path: str) -> str:
    """Module = the file's parent directory; ``""`` for a top-level file."""
    return path.rsplit("/", 1)[0] if "/" in path else ""


def freq_bucket(count: int) -> int:
    """log2 frequency bucket, used for frequency-matched distractor sampling."""
    return count.bit_length()


BANDS = ("low", "mid", "high")


def similarity_band(value: float) -> str:
    if value >= 0.30:
        return "high"
    if value >= 0.10:
        return "mid"
    return "low"


# --------------------------------------------------------------------------------------------
# Index
# --------------------------------------------------------------------------------------------


@dataclass
class PremiseIndex:
    """Corpus- and usage-derived structures the distractor tiers need.

    Every lookup a tier performs is precomputed here so that item generation is O(candidates
    considered) rather than O(corpus) per item.
    """

    frequency: dict[str, int] = field(default_factory=dict)
    def_path: dict[str, str] = field(default_factory=dict)
    proof_premises: dict[str, tuple[str, ...]] = field(default_factory=dict)
    module_premises: dict[str, tuple[str, ...]] = field(default_factory=dict)
    decls: dict[str, CorpusDecl] = field(default_factory=dict)
    file_bit: dict[str, int] = field(default_factory=dict)
    import_closure: dict[str, int] = field(default_factory=dict)
    #: token -> used premises whose name contains that token (tier (d) inverted index).
    token_index: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: declaration keyword -> corpus declarations that are *actually used as a premise* somewhere
    #: in train.  Tier (c) samples from this rather than from all 180k declarations: an arbitrary
    #: corpus declaration is a nonsense negative, and the first shortcut gate measured a combined
    #: shallow model at 0.866 on a tier-(c)-only rung built that way (see the manifest).
    decls_by_keyword: dict[str, tuple[str, ...]] = field(default_factory=dict)
    _tokens: dict[str, tuple[str, ...]] = field(default_factory=dict, repr=False)

    def tokens(self, name: str) -> tuple[str, ...]:
        cached = self._tokens.get(name)
        if cached is None:
            cached = name_tokens(name)
            self._tokens[name] = cached
        return cached

    def similarity(self, name: str, goal_tokens: frozenset[str]) -> float:
        toks = set(self.tokens(name))
        if not toks or not goal_tokens:
            return 0.0
        return len(toks & goal_tokens) / len(toks | goal_tokens)

    def in_scope(self, from_file: str, decl_path: str) -> bool:
        """True when ``decl_path`` is reachable through ``from_file``'s transitive imports."""
        closure = self.import_closure.get(from_file)
        bit = self.file_bit.get(decl_path)
        if closure is None or bit is None:
            return False
        return bool(closure >> bit & 1)

    def freq(self, name: str) -> int:
        return self.frequency.get(name, 0)

    def decl_keyword(self, name: str) -> str:
        decl = self.decls.get(name)
        return decl.decl_keyword if decl else "unknown"

    def order(self, name: str) -> int:
        decl = self.decls.get(name)
        return decl.order if decl else -1

    def path_of(self, name: str) -> str:
        if name in self.def_path:
            return self.def_path[name]
        decl = self.decls.get(name)
        return decl.path if decl else ""


def _decl_keyword(code: str) -> str:
    match = _DECL_KEYWORD_RE.search(code)
    return match.group(1) if match else "other"


def _signature(code: str, limit: int = 400) -> str:
    """The declaration up to its body: everything before the first ``:=``."""
    cut = code.find(":=")
    text = code if cut < 0 else code[:cut]
    return " ".join(text.split())[:limit]


def load_corpus(path: str | Path) -> tuple[dict[str, CorpusDecl], dict[str, list[str]]]:
    """Load ``corpus.jsonl`` into declarations plus the per-file direct import list."""
    source = guard_source_path(path)
    decls: dict[str, CorpusDecl] = {}
    imports: dict[str, list[str]] = {}
    order = 0
    with source.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            file_path = record["path"]
            imports[file_path] = list(record.get("imports") or [])
            for premise in record.get("premises") or []:
                name = premise.get("full_name")
                if not name or name in decls:
                    continue
                code = premise.get("code") or ""
                decls[name] = CorpusDecl(
                    full_name=name,
                    path=file_path,
                    kind=premise.get("kind", ""),
                    decl_keyword=_decl_keyword(code),
                    signature=_signature(code),
                    order=order,
                )
                order += 1
    return decls, imports


def build_import_closure(imports: dict[str, list[str]]) -> tuple[dict[str, int], dict[str, int]]:
    """Transitive import closure as one bitset per file (a file is in its own closure)."""
    file_bit = {path: i for i, path in enumerate(sorted(imports))}
    closure: dict[str, int] = {}
    for root in file_bit:
        if root in closure:
            continue
        stack: list[tuple[str, bool]] = [(root, False)]
        seen: set[str] = set()
        while stack:
            node, expanded = stack.pop()
            if expanded:
                bits = 1 << file_bit[node]
                for dep in imports.get(node, ()):
                    if dep in file_bit:
                        bits |= closure.get(dep, 1 << file_bit[dep])
                closure[node] = bits
                continue
            if node in closure or node in seen:
                continue
            seen.add(node)
            stack.append((node, True))
            for dep in imports.get(node, ()):
                if dep in file_bit and dep not in closure and dep not in seen:
                    stack.append((dep, False))
    return file_bit, closure


def build_index(
    premise_usage: Counter[str],
    def_path: dict[str, str],
    proof_premises: dict[str, set[str]],
    decls: dict[str, CorpusDecl],
    imports: dict[str, list[str]],
) -> PremiseIndex:
    """Assemble the index from train-only usage statistics plus the corpus."""
    module_premises: dict[str, list[str]] = defaultdict(list)
    token_index: dict[str, list[str]] = defaultdict(list)
    tokens: dict[str, tuple[str, ...]] = {}
    for name in premise_usage:
        path = def_path.get(name) or (decls[name].path if name in decls else "")
        if path:
            module_premises[module_of(path)].append(name)
        toks = name_tokens(name)
        tokens[name] = toks
        for token in set(toks):
            token_index[token].append(name)
    decls_by_keyword: dict[str, list[str]] = defaultdict(list)
    for name in premise_usage:
        decl = decls.get(name)
        if decl is not None:
            decls_by_keyword[decl.decl_keyword].append(name)
    file_bit, closure = build_import_closure(imports)
    return PremiseIndex(
        frequency=dict(premise_usage),
        def_path=dict(def_path),
        proof_premises={k: tuple(sorted(v)) for k, v in proof_premises.items()},
        module_premises={k: tuple(sorted(v)) for k, v in module_premises.items()},
        decls=decls,
        file_bit=file_bit,
        import_closure=closure,
        token_index={k: tuple(sorted(v)) for k, v in token_index.items()},
        decls_by_keyword={k: tuple(sorted(v)) for k, v in decls_by_keyword.items()},
        _tokens=tokens,
    )


# --------------------------------------------------------------------------------------------
# Difficulty ladder
# --------------------------------------------------------------------------------------------

TIER_SAME_PROOF = "a_same_proof"
TIER_SAME_MODULE = "b_same_module_freq_matched"
TIER_SCOPE_VALID = "c_scope_valid_type_compatible"
TIER_LEXICAL = "d_lexical_overlap_matched"
TIER_ORDER: tuple[str, ...] = (TIER_SAME_PROOF, TIER_SAME_MODULE, TIER_SCOPE_VALID, TIER_LEXICAL)


@dataclass(frozen=True, slots=True)
class Level:
    """One rung of the difficulty ladder.

    The gradient is over *confusability*, not size: which distractor tiers may be drawn from, how
    close a distractor's goal-similarity band must be to the gold's, how close its usage frequency
    must be, ``k``, and how much local context the prompt keeps.
    """

    name: str
    k: int
    tiers: tuple[str, ...]
    explicit_positive: bool = False
    #: Maximum |band distance| between a distractor's goal-similarity band and the gold's.
    similarity_band_slack: int = 2
    #: Maximum |log2 frequency bucket| distance from the gold premise.
    freq_bucket_slack: int = 8
    #: ``None`` keeps the whole local context; an int keeps that many trailing hypothesis lines.
    context_lines: int | None = None


#: Rungs that were built, gated and **rejected**.  They stay constructible so their measurement
#: is reproducible, but they are not part of the shipped ladder and must not be used to score a
#: Solver.  ``L1_cross_module`` failed its own shortcut gate twice: 0.866 drawing tier (c) from all
#: corpus declarations, then 0.644 after restricting tier (c) to genuinely used premises with
#: frequency-bucket and similarity-band matching -- both far above the 0.45 ceiling.  The cause is
#: structural rather than fixable by sampling: a rung defined as "gold local, every distractor
#: non-local" makes locality itself decisive, so the same-module and declaration-order features
#: identify the answer without any mathematics.
REJECTED_LEVELS: tuple[Level, ...] = (
    Level(
        name="L1_cross_module",
        k=4,
        tiers=(TIER_SCOPE_VALID, TIER_LEXICAL),
        similarity_band_slack=0,
        freq_bucket_slack=1,
    ),
)

LADDER: tuple[Level, ...] = (
    Level(name="L0_explicit_positive", k=6, tiers=TIER_ORDER, explicit_positive=True),
    Level(name="L2_standard", k=6, tiers=TIER_ORDER),
    Level(
        name="L3_same_module_freq_matched",
        k=6,
        tiers=(TIER_SAME_PROOF, TIER_SAME_MODULE),
        freq_bucket_slack=1,
    ),
    Level(
        name="L4_high_similarity",
        k=8,
        tiers=(TIER_SAME_PROOF, TIER_SAME_MODULE, TIER_LEXICAL),
        similarity_band_slack=0,
        freq_bucket_slack=1,
        context_lines=0,
    ),
)

#: Every constructible level, shipped or rejected, so a measurement can still address a rejected
#: rung by name.  Use :data:`LADDER` -- not this map -- when scoring a Solver.
LEVELS_BY_NAME: dict[str, Level] = {level.name: level for level in LADDER + REJECTED_LEVELS}


# --------------------------------------------------------------------------------------------
# Deterministic RNG
# --------------------------------------------------------------------------------------------


def _seed_for(seed: int, proof_id: str, step_index: int, level: str) -> int:
    digest = hashlib.blake2b(
        f"{seed}|{proof_id}|{step_index}|{level}".encode(), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big")


class SplitMix64:
    """A tiny deterministic PRNG.

    ``random.Random`` is deterministic too, but its stream is an implementation detail rather than
    a format guarantee.  splitmix64 written out here keeps generated item bytes stable across
    interpreter versions, which is what the reproducibility test asserts.
    """

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFFFFFFFFFF

    def _next(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)

    def below(self, bound: int) -> int:
        return self._next() % bound if bound > 0 else 0

    def shuffle(self, items: list[Any]) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, population: Sequence[Any], count: int) -> list[Any]:
        pool = list(population)
        self.shuffle(pool)
        return pool[:count]


# --------------------------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------------------------


@dataclass
class GeneratorConfig:
    seed: int = 20260907
    #: Candidates are ranked by closeness to the gold, then sampled from the best ``pool_factor*n``.
    pool_factor: int = 4
    #: Draws attempted when sampling the scope-valid tier (which is far too large to enumerate).
    scope_sample_draws: int = 600
    #: Cap on lexical-tier postings inspected per item.
    lexical_cap: int = 1200


class PremiseSelectionGenerator:
    """Turns sanitised transitions into leak-safe multiple-choice items."""

    def __init__(self, index: PremiseIndex, config: GeneratorConfig | None = None) -> None:
        self.index = index
        self.config = config or GeneratorConfig()
        self.items_with_fallback = 0
        self.items_emitted = 0
        self.items_rejected_gold_in_prompt = 0
        self.tier_counts: Counter[str] = Counter()

    # -- candidate tiers ----------------------------------------------------------------------

    def _tier_candidates(
        self,
        tier: str,
        transition: Transition,
        gold: str,
        banned: set[str],
        goal_tokens: frozenset[str],
        rng: SplitMix64,
    ) -> list[str]:
        idx = self.index
        if tier == TIER_SAME_PROOF:
            return [n for n in idx.proof_premises.get(transition.proof_id, ()) if n not in banned]
        if tier == TIER_SAME_MODULE:
            gold_path = idx.path_of(gold) or transition.file_path
            return [n for n in idx.module_premises.get(module_of(gold_path), ()) if n not in banned]
        if tier == TIER_SCOPE_VALID:
            keyword = idx.decl_keyword(gold)
            population = idx.decls_by_keyword.get(keyword, ())
            if not population:
                return []
            out: list[str] = []
            seen: set[str] = set()
            for _ in range(self.config.scope_sample_draws):
                name = population[rng.below(len(population))]
                if name in banned or name in seen:
                    continue
                seen.add(name)
                decl = idx.decls.get(name)
                if decl is None or not idx.in_scope(transition.file_path, decl.path):
                    continue
                out.append(name)
            return out
        if tier == TIER_LEXICAL:
            out2: list[str] = []
            seen2: set[str] = set()
            for token in sorted(set(idx.tokens(gold)) | goal_tokens):
                for name in idx.token_index.get(token, ()):
                    if name in banned or name in seen2:
                        continue
                    seen2.add(name)
                    out2.append(name)
                    if len(out2) >= self.config.lexical_cap:
                        return out2
            return out2
        raise ValueError(f"unknown distractor tier: {tier!r}")

    # -- ranking ------------------------------------------------------------------------------

    def _match_score(
        self, name: str, gold_bucket: int, gold_sim: float, goal_tokens: frozenset[str]
    ) -> float:
        """Lower is a closer match to the gold on (usage frequency, goal similarity)."""
        freq_gap = abs(freq_bucket(self.index.freq(name)) - gold_bucket)
        sim = self.index.similarity(name, goal_tokens)
        return freq_gap + 6.0 * abs(sim - gold_sim)

    def _admissible(
        self,
        name: str,
        level: Level,
        gold_bucket: int,
        gold_band: str,
        goal_tokens: frozenset[str],
    ) -> bool:
        if abs(freq_bucket(self.index.freq(name)) - gold_bucket) > level.freq_bucket_slack:
            return False
        band = similarity_band(self.index.similarity(name, goal_tokens))
        return abs(BANDS.index(band) - BANDS.index(gold_band)) <= level.similarity_band_slack

    # -- item construction --------------------------------------------------------------------

    def generate(self, transition: Transition, level: Level) -> PremiseItem | None:
        """Build one item, or ``None`` when the transition cannot yield a well-formed one."""
        if len(transition.premises) != 1:
            return None
        gold = transition.premises[0].full_name
        if level.explicit_positive and gold not in self.index.decls:
            # An explicit-positive item must actually state the relation; without a corpus
            # statement for the gold there is nothing to state, so the arm skips the transition.
            return None
        goal_tokens = frozenset(state_tokens(transition.state_before))
        gold_sim = self.index.similarity(gold, goal_tokens)
        gold_band = similarity_band(gold_sim)
        gold_bucket = freq_bucket(self.index.freq(gold))

        banned = {gold}
        chosen: list[tuple[str, str]] = []
        needed = level.k - 1
        rng = SplitMix64(
            _seed_for(self.config.seed, transition.proof_id, transition.step_index, level.name)
        )
        used_fallback = False

        ordered_tiers = [t for t in TIER_ORDER if t in level.tiers]
        for position, tier in enumerate(ordered_tiers):
            if len(chosen) >= needed:
                break
            remaining = needed - len(chosen)
            candidates = self._tier_candidates(tier, transition, gold, banned, goal_tokens, rng)
            admissible = [
                c
                for c in candidates
                if self._admissible(c, level, gold_bucket, gold_band, goal_tokens)
            ]
            if not admissible:
                continue
            admissible.sort(
                key=lambda n: (self._match_score(n, gold_bucket, gold_sim, goal_tokens), n)
            )
            pool = admissible[: max(remaining * self.config.pool_factor, remaining)]
            picked = rng.sample(pool, remaining)
            for name in picked:
                banned.add(name)
                chosen.append((name, tier))
            if position > 0 and picked:
                used_fallback = True

        if len(chosen) < needed:
            return None

        options = [PremiseOption(gold, self.index.path_of(gold), "gold")] + [
            PremiseOption(name, self.index.path_of(name), tier) for name, tier in chosen
        ]
        rng.shuffle(options)
        answer_index = next(i for i, o in enumerate(options) if o.tier == "gold")

        prompt = render_prompt(
            transition,
            tuple(options),
            level,
            gold_signature=self._redacted_signature(gold) if level.explicit_positive else None,
        )
        # Final safety net: never emit an item whose prompt body names its own answer.  Reaching
        # this is a redaction miss, not an ordinary rejection, so it is counted separately.
        body = prompt.split("## Proof state", 1)[-1].split("## Candidates", 1)[0]
        if name_occurs_in(body, gold):
            self.items_rejected_gold_in_prompt += 1
            return None

        self.tier_counts.update(tier for _, tier in chosen)
        self.items_emitted += 1
        if used_fallback:
            self.items_with_fallback += 1
        item_id = hashlib.blake2b(
            f"{SPEC_VERSION}|{self.config.seed}|{transition.proof_id}|"
            f"{transition.step_index}|{level.name}".encode(),
            digest_size=12,
        ).hexdigest()
        return PremiseItem(
            item_id=item_id,
            level=level.name,
            prompt=prompt,
            options=tuple(options),
            answer_index=answer_index,
            k=level.k,
            provenance={
                "proof_id": transition.proof_id,
                "file_path": transition.file_path,
                "thm": transition.thm,
                "step_index": transition.step_index,
                "split": transition.split,
                "commit": DATASET_COMMIT,
                "source_relpath": PERMITTED_TRACE_RELPATH,
                "generator_version": GENERATOR_VERSION,
                "seed": self.config.seed,
            },
            features={
                "gold_similarity": round(gold_sim, 6),
                "gold_similarity_band": gold_band,
                "gold_freq": self.index.freq(gold),
                "gold_freq_bucket": gold_bucket,
                "distractor_tiers": [tier for _, tier in chosen],
                "used_fallback_tier": used_fallback,
            },
        )

    def _redacted_signature(self, gold: str) -> str:
        decl = self.index.decls[gold]
        return redact_name(decl.signature, gold)


def redact_name(text: str, full_name: str) -> str:
    """Replace ``full_name`` and its last component with the redaction token.

    Uses exactly the patterns :func:`name_occurs_in` searches for, so redaction and the leak
    audit cannot disagree about what counts as an occurrence.
    """
    full, short = _name_patterns(full_name)
    out = full.sub(REDACTION, text)
    if short is not None:
        out = short.sub(REDACTION, out)
    return out


def trim_context(state: str, context_lines: int | None) -> str:
    """Keep the goal (from the first ``⊢`` line) plus ``context_lines`` preceding hypotheses."""
    if context_lines is None:
        return state
    lines = state.splitlines()
    goal_start = next((i for i, line in enumerate(lines) if line.startswith("⊢")), None)
    if goal_start is None:
        return state
    keep_from = max(0, goal_start - context_lines)
    prefix: list[str] = [] if keep_from == 0 else ["<local context elided>"]
    return "\n".join(prefix + lines[keep_from:])


def render_prompt(
    transition: Transition,
    options: Sequence[PremiseOption],
    level: Level,
    gold_signature: str | None = None,
) -> str:
    """Render the item.  Sees no tactic, no annotation, no split label and no oracle marker."""
    body = [
        "You are given a Lean 4 proof state and a list of candidate premises.",
        "Exactly one candidate is the premise cited by the valid next proof step.",
        "",
        "## Proof state",
        trim_context(transition.state_before, level.context_lines),
        "",
    ]
    if gold_signature is not None:
        body += [
            "## Stated relation",
            "The next step applies a declaration whose statement is given below, with its own",
            f"name replaced by {REDACTION}:",
            f"    {gold_signature}",
            "",
        ]
    body.append("## Candidates")
    for i, option in enumerate(options):
        body.append(f"{OPTION_LABELS[i]}. {option.full_name}")
    body += ["", "## Answer", "Reply with the single letter of the cited premise."]
    return "\n".join(body)


# --------------------------------------------------------------------------------------------
# Leak audit
# --------------------------------------------------------------------------------------------

#: Substrings that would only ever appear if generator internals leaked into the rendered text.
#: Bare words such as "tactic" or "split" are NOT listed: mathlib genuinely contains declarations
#: named ``List.split`` and files under ``Mathlib/Tactic``, so flagging those is a false positive.
_ORACLE_MARKERS = ("answer_index", "<a>", "</a>", "annotated_tactic", "answer_label")

#: A split *label* being emitted names one of the split values; ``h : l.split = ...`` does not.
_SPLIT_LABEL_RE = re.compile(
    r"split\s*[:=]\s*[\"']?(train|val|valid|test)\b|[\"']split[\"']", re.IGNORECASE
)


def audit_item_leaks(item: PremiseItem, step: RawStep | None = None) -> list[str]:
    """Return every detected leak in a rendered item.  An empty list means clean."""
    problems: list[str] = []
    prompt = item.prompt
    gold = item.options[item.answer_index].full_name

    if sum(1 for o in item.options if o.tier == "gold") != 1:
        problems.append("gold option is not present exactly once")
    if len({o.full_name for o in item.options}) != len(item.options):
        problems.append("duplicate option names")
    if len(item.options) != item.k:
        problems.append("option count does not match k")
    if _SPLIT_LABEL_RE.search(prompt):
        problems.append("split label appears in prompt")
    for marker in _ORACLE_MARKERS:
        if marker in prompt:
            problems.append(f"oracle marker {marker!r} appears in prompt")

    # Only the *variable* region can leak: the boilerplate is fixed text that may legitimately
    # share a word with a short premise name (e.g. gold ``Nat.one`` vs "Exactly one candidate").
    body = prompt.split("## Proof state", 1)[-1].split("## Candidates", 1)[0]
    if name_occurs_in(body, gold):
        problems.append("gold premise name appears outside the option list")

    if step is not None:
        flat_prompt = " ".join(prompt.split())
        tactic_line = " ".join(step.tactic.split())
        if tactic_line and tactic_line in flat_prompt:
            problems.append("tactic text appears in prompt")
        annotated = " ".join(step.annotated_tactic.split())
        if annotated and annotated in flat_prompt:
            problems.append("annotated_tactic markup appears in prompt")
    return problems


# --------------------------------------------------------------------------------------------
# Corpus-scale entry point
# --------------------------------------------------------------------------------------------


def require_permitted_train(train_path: str | Path) -> Path:
    """Refuse anything but ``random/train.json``: the only permitted development source."""
    source = guard_source_path(train_path)
    parts = source.parts
    tail = f"{parts[-2]}/{parts[-1]}" if len(parts) >= 2 else source.name
    if tail != PERMITTED_TRACE_RELPATH:
        raise SealedSplitError(
            f"{source} is not the permitted development source {PERMITTED_TRACE_RELPATH!r}"
        )
    return source


def load_train_transitions(
    train_path: str | Path, limit_theorems: int | None = None
) -> tuple[list[Transition], dict[str, set[str]], list[RawStep], dict[str, int]]:
    """Stream the train split once.

    Returns the usable sanitised transitions, every proof's full premise set (for tier (a)), the
    matching raw steps for audit, and counters describing the filter that was applied.  Intended
    for bounded runs (tests, samples); the full 373 MB pass uses a two-pass research script that
    never holds all proof states at once.
    """
    source = require_permitted_train(train_path)
    transitions: list[Transition] = []
    raws: list[RawStep] = []
    proof_premises: dict[str, set[str]] = defaultdict(set)
    stats: Counter[str] = Counter()
    for theorem in stream_traced_theorems(source, limit=limit_theorems):
        stats["theorems"] += 1
        for step in raw_steps(theorem):
            stats["steps"] += 1
            if step.premises:
                stats["steps_with_premise"] += 1
                proof_premises[step.proof_id].update(p.full_name for p in step.premises)
            if len(step.premises) > 1:
                stats["steps_multi_premise"] += 1
            if is_usable(step):
                stats["steps_usable"] += 1
                transitions.append(sanitise(theorem, step))
                raws.append(step)
    return transitions, dict(proof_premises), raws, dict(stats)
