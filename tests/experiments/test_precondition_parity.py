"""Parity audit of the precondition ladder under every founder surface (offline, < 40 s).

Phase 8 compares five representations of IDENTICAL precondition-conjunction tasks against one
Solver.  That comparison is only meaningful if, for every item, the arms (a) put the same
information on the page, (b) share one envelope and one answer protocol, (c) differ in bytes,
and (d) localise the truth-carrying difference between twins to the substituted premise ids and
the order-rotation difference to the OPTIONS block.  These tests pin each of those properties
for the strata Phase 8 will run, across ALL eight founders (the roster is a subset).

Nothing here calls a model, opens a socket or reads a file.  The harness's own parity assertion
is exercised as-is; the additional checks below are stricter and item-specific, and a
deliberately corrupted arm is shown to be refused.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from arena.canonical.schema import CanonicalExpression
from arena.environments.precondition_ladder import (
    LADDER,
    Pool,
    PreconditionFamily,
    build_family,
    independent_truth,
)
from arena.experiments.game_r_formal_v1 import (
    MaterialisedItem,
    ParityReport,
    ParityViolation,
    SyntaxGuidePolicy,
    answer_protocol_hash,
    assert_arena_parity,
    build_prompt,
    envelope_signature,
    founder_genome,
    prompt_bytes_hash,
    rotate_options,
)
from arena.genome.seeds import SEED_GENOME_BY_ID
from arena.languages.phenotype import GenomePhenotypeLanguage
from arena.model_view.compiler import ModelViewCompiler
from arena.model_view.genome import ModelViewGenome

STRATA = ("P05", "P12", "P05_M2_D2")
FAMILIES = 3
POOL = Pool.DEV
GUIDE = SyntaxGuidePolicy.SHARED_CONSTANT
SURFACES = tuple(SEED_GENOME_BY_ID)
PHASE8_ROSTER = (
    "L3_JSON_AST",
    "L0_STRUCTURED_ENGLISH",
    "L1_CURRENT_HML",
    "L2_SEXPR",
    "L5_COMPACT_SYMBOLIC",
)
BASELINE = "L3_JSON_AST"

#: The identifier-token pattern the audit brief prescribes.  It has no left boundary, so it
#: also matches the tail of a role label such as ``@2a:field`` (-> ``a:field``).  That is a
#: property of the pattern, not of the state; it is pinned below rather than hidden.
ID_TOKEN = re.compile(r"[A-Za-z]+:[A-Za-z0-9:]+|p:\d{4,5}")
STATE_MARKER = "CURRENT STATE:\n"
OPTIONS_MARKER = "\nOPTIONS:\n"
ANSWER_MARKER = "\nANSWER:"

#: Measured divergence of the raw pattern: ``L1_CURRENT_HML`` (TYPED_AFFIX morphology) labels
#: its record keys ``@<hex>:field``; every hex index ending in a letter yields one spurious
#: match.  These six tokens are key names, constant for every item, and are the ONLY tokens on
#: which the raw pattern disagrees across the eight founders.  Any other disagreement fails.
ROLE_LABEL_FRAGMENTS: dict[str, frozenset[str]] = {
    "L1_CURRENT_HML": frozenset({"a:field", "b:field", "c:field", "d:field", "e:field", "f:field"})
}


# ------------------------------------------------------------------------------ fixtures


@dataclass(frozen=True, slots=True)
class Rendered:
    """One item (base or rotated) with its prompt under every founder."""

    stratum: str
    family: PreconditionFamily
    item: MaterialisedItem
    rotated: bool
    prompts: dict[str, str]


def _state_block(prompt: str) -> str:
    start = prompt.index(STATE_MARKER) + len(STATE_MARKER)
    return prompt[start : prompt.index(OPTIONS_MARKER)]


def _options_tail(prompt: str) -> str:
    return prompt[prompt.index(OPTIONS_MARKER) + len(OPTIONS_MARKER) :]


def _identifier_counts(prompt: str) -> Counter[str]:
    return Counter(ID_TOKEN.findall(_state_block(prompt)))


def _twin_ids(family: PreconditionFamily) -> tuple[str, ...]:
    return (family.missing_a, family.missing_b, *family.near_misses_a, *family.near_misses_b)


def _strip(text: str, needles: tuple[str, ...]) -> str:
    for needle in needles:
        text = text.replace(needle, "")
    return text


@pytest.fixture(scope="module")
def genomes() -> dict[str, ModelViewGenome]:
    return {surface: founder_genome(surface) for surface in SURFACES}


@pytest.fixture(scope="module")
def families() -> dict[str, tuple[PreconditionFamily, ...]]:
    return {
        stratum: tuple(build_family(stratum, POOL, index) for index in range(FAMILIES))
        for stratum in STRATA
    }


@pytest.fixture(scope="module")
def rendered(
    genomes: dict[str, ModelViewGenome], families: dict[str, tuple[PreconditionFamily, ...]]
) -> tuple[Rendered, ...]:
    out: list[Rendered] = []
    for stratum, group in families.items():
        for family in group:
            for item in family.items():
                for rotated in (False, True):
                    concrete = rotate_options(item, 1) if rotated else item
                    prompts = {
                        surface: build_prompt(genome, concrete, guide_policy=GUIDE)
                        for surface, genome in genomes.items()
                    }
                    out.append(Rendered(stratum, family, concrete, rotated, prompts))
    return tuple(out)


@pytest.fixture(scope="module")
def reports(
    genomes: dict[str, ModelViewGenome], rendered: tuple[Rendered, ...]
) -> dict[str, ParityReport]:
    arms = list(genomes.values())
    return {
        entry.item.task_id: assert_arena_parity(entry.item, arms, guide_policy=GUIDE)
        for entry in rendered
    }


def _by_stratum(rendered: tuple[Rendered, ...], stratum: str) -> Iterator[Rendered]:
    return (entry for entry in rendered if entry.stratum == stratum)


def _twins(rendered: tuple[Rendered, ...], stratum: str) -> Iterator[tuple[Rendered, Rendered]]:
    """(ORIGINAL, COUNTERFACTUAL) pairs of un-rotated items, per family."""

    base = [entry for entry in _by_stratum(rendered, stratum) if not entry.rotated]
    for family in {entry.family.family_id for entry in base}:
        pair = [entry for entry in base if entry.family.family_id == family]
        assert len(pair) == 2
        original = next(entry for entry in pair if entry.item.variant == "ORIGINAL")
        counter = next(entry for entry in pair if entry.item.variant == "COUNTERFACTUAL")
        yield original, counter


def _rotation_pairs(
    rendered: tuple[Rendered, ...], stratum: str
) -> Iterator[tuple[Rendered, Rendered]]:
    entries = list(_by_stratum(rendered, stratum))
    for base in (entry for entry in entries if not entry.rotated):
        twin = next(
            entry
            for entry in entries
            if entry.rotated and entry.item.provenance["rotated_from"] == base.item.task_id
        )
        yield base, twin


# ------------------------------------------------------------- 0. fixture sanity and scope


def test_audit_covers_the_documented_strata_and_all_eight_founders() -> None:
    assert set(STRATA) <= set(LADDER)
    assert LADDER["P05_M2_D2"].missing_near_misses == 2
    assert len(SURFACES) == 8 and set(PHASE8_ROSTER) <= set(SURFACES)
    assert BASELINE in PHASE8_ROSTER


def test_fixture_materialises_every_item_twice(rendered: tuple[Rendered, ...]) -> None:
    assert len(rendered) == len(STRATA) * FAMILIES * 2 * 2
    assert all(len(entry.prompts) == 8 for entry in rendered)
    assert sum(entry.rotated for entry in rendered) == len(rendered) // 2


# ---------------------------------------------------- 1. the harness's own parity assertion


@pytest.mark.parametrize("stratum", STRATA)
def test_arena_parity_passes_for_base_and_rotated_items(
    stratum: str, rendered: tuple[Rendered, ...], reports: dict[str, ParityReport]
) -> None:
    for entry in _by_stratum(rendered, stratum):
        report = reports[entry.item.task_id]
        assert report.mathematical_hash == entry.item.canonical_state.mathematical_hash
        assert set(report.checks.values()) == {"PASS", "APPLIED"}, (entry.item.task_id, report)
        assert report.checks["v4_cross_check"] == "APPLIED"
        assert set(report.prompt_hashes) == {f"GRF_{surface}" for surface in SURFACES}
        for surface, prompt in entry.prompts.items():
            assert report.prompt_hashes[f"GRF_{surface}"] == prompt_bytes_hash(prompt)


# ------------------------------------------- 2. one envelope, one answer protocol, everywhere


def test_envelope_and_answer_protocol_are_one_constant_across_items_and_arms(
    rendered: tuple[Rendered, ...], reports: dict[str, ParityReport]
) -> None:
    signatures = {report.envelope_signature for report in reports.values()}
    protocols = {report.answer_protocol_hash for report in reports.values()}
    assert len(signatures) == 1 and len(protocols) == 1
    assert protocols == {answer_protocol_hash(2)}
    for entry in rendered:
        assert envelope_signature(entry.item, guide_policy=GUIDE) in signatures
        # The envelope is blind to the arm by construction; the guide text is the shared constant.
        for prompt in entry.prompts.values():
            assert prompt.startswith("Answer with exactly one JSON object")
            assert "GUIDE:\nThe state below is a lossless record" in prompt
            assert prompt.endswith("ANSWER:")
            assert "EXPLICIT_EVERY_USE" not in prompt and "json-ast grammar" not in prompt


# ------------------------------------------------------ 3. rendered bytes pairwise distinct


def test_rendered_bytes_are_pairwise_distinct_across_arms(
    rendered: tuple[Rendered, ...], reports: dict[str, ParityReport]
) -> None:
    for entry in rendered:
        texts = list(entry.prompts.values())
        assert len(set(texts)) == 8, entry.item.task_id
        assert len(set(reports[entry.item.task_id].prompt_hashes.values())) == 8
        # Distinctness holds in the state block alone, not merely via the option renderings.
        assert len({_state_block(text) for text in texts}) == 8


# ------------------------------------------------------- 4. visible-information parity


def test_every_arm_recovers_the_item_hash_from_its_compiled_view(
    genomes: dict[str, ModelViewGenome], rendered: tuple[Rendered, ...]
) -> None:
    for entry in rendered:
        state = entry.item.canonical_state
        for surface, genome in genomes.items():
            compiler = ModelViewCompiler(genome)
            compiled = compiler.compile(state, options=tuple(entry.item.options))
            recovered = compiler.recover_canonical_state(compiled)
            assert recovered.mathematical_hash == state.mathematical_hash, surface
            assert compiled.projection is None and compiled.text == _state_block(
                entry.prompts[surface]
            )


def test_identifier_token_multiset_is_identical_across_arms(
    rendered: tuple[Rendered, ...],
) -> None:
    """Every state identifier occurs the same number of times on every arm's page.

    The raw pattern disagrees ONLY on ``L1_CURRENT_HML``'s six role-label fragments, which are
    pinned exactly (see ``ROLE_LABEL_FRAGMENTS``).  Those fragments are key names: the same
    tokens for every item, never a premise, answer or object id.  After discounting them the
    multisets are identical, and the twin ids occur exactly as the mechanism dictates: the
    licensed answer's would-be-missing premise twice (``requires`` + ``holds``), the unlicensed
    answer's missing premise once (``requires`` only), its near-misses once (``holds`` only)
    and the other near-misses never.
    """

    for entry in rendered:
        counts = {surface: _identifier_counts(text) for surface, text in entry.prompts.items()}
        reference = counts[BASELINE]
        assert not (set(reference) & set().union(*ROLE_LABEL_FRAGMENTS.values()))
        for surface, counter in counts.items():
            fragments = ROLE_LABEL_FRAGMENTS.get(surface, frozenset())
            raw_difference = set(counter) ^ set(reference)
            assert raw_difference == set(fragments), (surface, entry.item.task_id, raw_difference)
            state_ids = Counter(
                {token: n for token, n in counter.items() if token not in fragments}
            )
            assert state_ids == reference, (surface, entry.item.task_id)
        family = entry.family
        # (``provenance["variant"]`` survives rotation; ``item.variant`` becomes ORDER_ROTATED.)
        if entry.item.provenance["variant"] == "ORIGINAL":
            licensed, unlicensed = family.missing_a, family.missing_b
            held_near, absent_near = family.near_misses_b, family.near_misses_a
        else:
            licensed, unlicensed = family.missing_b, family.missing_a
            held_near, absent_near = family.near_misses_a, family.near_misses_b
        expected = Counter({licensed: 2, unlicensed: 1, **dict.fromkeys(held_near, 1)})
        observed = Counter({token: reference[token] for token in _twin_ids(family)})
        assert observed == expected, (entry.item.task_id, observed, expected)
        assert all(reference[token] == 0 for token in absent_near)


def test_role_label_fragments_are_item_independent_key_names(
    genomes: dict[str, ModelViewGenome], rendered: tuple[Rendered, ...]
) -> None:
    """The pinned L1 divergence carries no item information: the same six tokens appear for
    every item, they are substrings of L1's fixed role labels, and no other founder has any."""

    for surface, fragments in ROLE_LABEL_FRAGMENTS.items():
        language = GenomePhenotypeLanguage(genomes[surface].surface)
        labels = "\n".join(language._roles.values())  # the codec's own key table
        assert set(ID_TOKEN.findall(labels)) == set(fragments)
        for entry in rendered:
            observed = set(_identifier_counts(entry.prompts[surface])) - set(
                _identifier_counts(entry.prompts[BASELINE])
            )
            assert observed == set(fragments), entry.item.task_id
    for surface in SURFACES:
        if surface in ROLE_LABEL_FRAGMENTS:
            continue
        language = GenomePhenotypeLanguage(genomes[surface].surface)
        assert not ID_TOKEN.findall("\n".join(language._roles.values())), surface


# ----------------------------------------------------------- 5. counterfactual locality


@pytest.mark.parametrize("stratum", STRATA)
def test_twin_prompts_are_byte_identical_outside_the_substituted_ids(
    stratum: str, rendered: tuple[Rendered, ...]
) -> None:
    for original, counter in _twins(rendered, stratum):
        family = original.family
        needles = _twin_ids(family)
        assert len(set(needles)) == 2 + 2 * family.params.missing_near_misses
        for surface in SURFACES:
            left, right = original.prompts[surface], counter.prompts[surface]
            assert left != right, (stratum, surface)
            assert _strip(left, needles) == _strip(right, needles), (stratum, surface)
            # The substituted ids are the whole difference: the per-arm bytes that differ are
            # exactly (1 + missing_near_misses) premise bodies of `premise_digits` digits.
            slots = 1 + family.params.missing_near_misses
            differing = sum(1 for a, b in zip(left, right, strict=True) if a != b)
            assert slots <= differing <= slots * family.premise_digits, (stratum, surface)


# ---------------------------------------------------------- 6. order-rotation locality


@pytest.mark.parametrize("stratum", STRATA)
def test_rotation_touches_only_the_options_block_and_swaps_the_two_options(
    stratum: str, rendered: tuple[Rendered, ...]
) -> None:
    for base, rotated in _rotation_pairs(rendered, stratum):
        assert rotated.item.canonical_state is base.item.canonical_state
        assert rotated.item.correct_index == (base.item.correct_index + 1) % 2
        for surface in SURFACES:
            left, right = base.prompts[surface], rotated.prompts[surface]
            head = left.index(OPTIONS_MARKER) + len(OPTIONS_MARKER)
            assert left[:head] == right[:head], (stratum, surface)
            tail = _options_tail(left)
            assert tail.startswith("OPTION_A: ") and tail.endswith(ANSWER_MARKER[1:])
            body = tail[len("OPTION_A: ") : -len(ANSWER_MARKER)]
            first, second = body.split("\nOPTION_B: ")
            assert first != second
            expected = f"OPTION_A: {second}\nOPTION_B: {first}{ANSWER_MARKER}"
            assert _options_tail(right) == expected, (stratum, surface)


# ------------------------------------------------------------ 7. twin lengths equal per arm


@pytest.mark.parametrize("stratum", STRATA)
def test_twin_and_family_prompt_lengths_are_identical_per_arm(
    stratum: str, rendered: tuple[Rendered, ...]
) -> None:
    for surface in SURFACES:
        lengths = {len(entry.prompts[surface]) for entry in _by_stratum(rendered, stratum)}
        assert len(lengths) == 1, (stratum, surface, lengths)
    for original, counter in _twins(rendered, stratum):
        for surface in SURFACES:
            assert len(original.prompts[surface]) == len(counter.prompts[surface])
            assert len(original.prompts[surface].encode("utf-8")) == len(
                counter.prompts[surface].encode("utf-8")
            )


# ------------------------------------------------------ 8. independent truth == correct_index


def test_independent_truth_agrees_with_correct_index_for_base_and_rotated_items(
    rendered: tuple[Rendered, ...],
) -> None:
    for entry in rendered:
        item = entry.item
        assert independent_truth(item.canonical_state, item.options) == item.correct_index
        expected = 0 if item.provenance["variant"] == "ORIGINAL" else 1
        if entry.rotated:
            expected = (expected + 1) % 2
            assert item.variant == "ORDER_ROTATED"
        else:
            assert item.variant == item.provenance["variant"]
        assert item.correct_index == expected


# ---------------------------------------------------------- 9. a corrupted arm is refused


def _holds(premise: str) -> CanonicalExpression:
    return CanonicalExpression(
        "holds",
        (CanonicalExpression("symbol", value=premise, sort="Identifier"),),
        sort="Proposition",
    )


@pytest.mark.parametrize("corruption", ("extra_assumption", "trailing_identifier"))
def test_an_arm_that_shows_an_extra_identifier_is_refused(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
    genomes: dict[str, ModelViewGenome],
    families: dict[str, tuple[PreconditionFamily, ...]],
) -> None:
    """Two ways an arm could leak: an extra (parseable) ``holds`` line, or a bare identifier
    appended to the page.  Both are refused by ``assert_arena_parity`` for the corrupted arm
    only; the same item passes when the arm is honest."""

    target = "L5_COMPACT_SYMBOLIC"
    honest_encode = GenomePhenotypeLanguage._encode_payload
    extra = _holds("p:1234").to_dict()

    def corrupted(self: GenomePhenotypeLanguage, payload: dict[str, Any]) -> str:
        if self.genome.candidate_id != target:
            return honest_encode(self, payload)
        if corruption == "extra_assumption":
            payload = {**payload, "assumptions": [*payload["assumptions"], extra]}
            return honest_encode(self, payload)
        return honest_encode(self, payload) + '\n"p:1234"'

    item = families["P05"][0].items()[0]
    arms = [genomes[BASELINE], genomes[target]]
    assert_arena_parity(item, arms, guide_policy=GUIDE)  # honest: passes
    monkeypatch.setattr(GenomePhenotypeLanguage, "_encode_payload", corrupted)
    with pytest.raises(ParityViolation, match=target):
        assert_arena_parity(item, arms, guide_policy=GUIDE)
    with pytest.raises(ParityViolation):
        assert_arena_parity(rotate_options(item, 1), arms, guide_policy=GUIDE)
    # The corruption really put an extra identifier on the page.
    prompt = build_prompt(genomes[target], item, guide_policy=GUIDE)
    assert "p:1234" in _state_block(prompt)
