"""Tests for the premise-selection task family.

CPU-only and offline.  The bulk of the suite runs against a synthetic world built in-process so
that nothing depends on the 373 MB benchmark file; one test marked ``integration`` reads a bounded
prefix of the real train split when it is present on this machine.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from arena.environments import premise_selection as ps

REAL_BENCHMARK = Path(
    "/Users/moheet/Projects/Hamiltonian-Labs/hml_research_artifacts/leandojo_raw/"
    "leandojo_benchmark_4"
)
REAL_TRAIN = REAL_BENCHMARK / "random" / "train.json"


# --------------------------------------------------------------------------------------------
# Synthetic world
# --------------------------------------------------------------------------------------------

N_PROOFS = 160
STEPS_PER_PROOF = 4
N_MODULES = 5


def _premise_name(proof: int, step: int) -> str:
    return f"Synth.Mod{proof % N_MODULES}.lemma_{proof}_{step}"


def _file_path(proof: int) -> str:
    return f"Mathlib/Synthetic/Mod{proof % N_MODULES}/File{proof}.lean"


def _make_theorems() -> list[dict[str, Any]]:
    theorems = []
    for proof in range(N_PROOFS):
        path = _file_path(proof)
        tactics = []
        for step in range(STEPS_PER_PROOF):
            name = _premise_name(proof, step)
            tactics.append(
                {
                    "tactic": f"rw [{name}] at h",
                    "annotated_tactic": [
                        f"rw [<a>{name}</a>] at h",
                        [
                            {
                                "full_name": name,
                                "def_path": path,
                                "def_pos": [1, 1],
                                "def_end_pos": [1, 2],
                            }
                        ],
                    ],
                    "state_before": (
                        f"x y : Nat\nh : P x y\ninst : Ring R\n⊢ Q x y (mul x y) {'z' * step}"
                    ),
                    "state_after": "x y : Nat\n⊢ True",
                }
            )
        theorems.append(
            {
                "url": "https://github.com/leanprover-community/mathlib4",
                "commit": ps.DATASET_COMMIT,
                "file_path": path,
                "full_name": f"Synthetic.thm_{proof}",
                "start": [1, 1],
                "end": [9, 9],
                "traced_tactics": tactics,
            }
        )
    return theorems


def _make_corpus() -> tuple[dict[str, ps.CorpusDecl], dict[str, list[str]]]:
    decls: dict[str, ps.CorpusDecl] = {}
    imports: dict[str, list[str]] = {}
    order = 0
    for proof in range(N_PROOFS):
        path = _file_path(proof)
        # A strict chain, so the transitive closure is a DAG with no cycles.
        imports[path] = [_file_path(proof - 1)] if proof else []
        for step in range(STEPS_PER_PROOF):
            name = _premise_name(proof, step)
            decls[name] = ps.CorpusDecl(
                full_name=name,
                path=path,
                kind="commanddeclaration",
                decl_keyword="theorem",
                signature=f"theorem {name} (x y : Nat) : Q x y (mul x y)",
                order=order,
            )
            order += 1
    return decls, imports


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    theorems = _make_theorems()
    decls, imports = _make_corpus()
    usage: Counter[str] = Counter()
    def_path: dict[str, str] = {}
    proof_premises: dict[str, set[str]] = {}
    pairs: list[tuple[ps.Transition, ps.RawStep]] = []
    for theorem in theorems:
        for step in ps.raw_steps(theorem):
            proof_premises.setdefault(step.proof_id, set()).update(
                ref.full_name for ref in step.premises
            )
            if ps.is_usable(step):
                usage[step.premises[0].full_name] += 1
                def_path.setdefault(step.premises[0].full_name, step.premises[0].def_path)
                pairs.append((ps.sanitise(theorem, step), step))
    index = ps.build_index(usage, def_path, proof_premises, decls, imports)
    return {"index": index, "pairs": pairs, "theorems": theorems}


def _generate(world: dict[str, Any], level: ps.Level, seed: int = 20260907) -> list[ps.PremiseItem]:
    generator = ps.PremiseSelectionGenerator(world["index"], ps.GeneratorConfig(seed=seed))
    items = []
    for transition, _ in world["pairs"]:
        item = generator.generate(transition, level)
        if item is not None:
            items.append(item)
    return items


# --------------------------------------------------------------------------------------------
# Sealed-split refusal
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("relpath", sorted(ps.SEALED_RELPATHS))
def test_sealed_splits_are_refused(relpath: str) -> None:
    with pytest.raises(ps.SealedSplitError):
        ps.guard_source_path(REAL_BENCHMARK / relpath)
    with pytest.raises(ps.SealedSplitError):
        ps.stream_traced_theorems(REAL_BENCHMARK / relpath).__next__()


def test_only_random_train_is_an_accepted_development_source(tmp_path: Path) -> None:
    other = tmp_path / "somewhere" / "train.json"
    other.parent.mkdir(parents=True)
    other.write_text("[]", encoding="utf-8")
    with pytest.raises(ps.SealedSplitError):
        ps.require_permitted_train(other)
    permitted = tmp_path / "random" / "train.json"
    permitted.parent.mkdir(parents=True)
    permitted.write_text("[]", encoding="utf-8")
    assert ps.require_permitted_train(permitted) == permitted


def test_generated_items_never_claim_a_sealed_origin(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        for item in _generate(world, level):
            provenance = item.provenance
            assert provenance["split"] == ps.PERMITTED_SPLIT
            assert provenance["source_relpath"] == ps.PERMITTED_TRACE_RELPATH
            assert provenance["source_relpath"] not in ps.SEALED_RELPATHS
            assert provenance["commit"] == ps.DATASET_COMMIT


# --------------------------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------------------------


def test_same_seed_reproduces_byte_identical_items(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        first = [json.dumps(i.to_json(), sort_keys=True) for i in _generate(world, level)]
        second = [json.dumps(i.to_json(), sort_keys=True) for i in _generate(world, level)]
        assert first, f"{level.name} produced no items"
        assert first == second


def test_a_different_seed_produces_different_items(world: dict[str, Any]) -> None:
    level = ps.LEVELS_BY_NAME["L2_standard"]
    first = [json.dumps(i.to_json(), sort_keys=True) for i in _generate(world, level, seed=1)]
    second = [json.dumps(i.to_json(), sort_keys=True) for i in _generate(world, level, seed=2)]
    assert first != second


def test_item_order_does_not_affect_an_item(world: dict[str, Any]) -> None:
    """Item bytes depend on the item's own provenance, not on when it was generated."""
    level = ps.LEVELS_BY_NAME["L2_standard"]
    forward = _generate(world, level)
    generator = ps.PremiseSelectionGenerator(world["index"], ps.GeneratorConfig(seed=20260907))
    reverse = [
        item
        for transition, _ in reversed(world["pairs"])
        if (item := generator.generate(transition, level)) is not None
    ]
    by_id = {item.item_id: json.dumps(item.to_json(), sort_keys=True) for item in reverse}
    for item in forward:
        assert by_id[item.item_id] == json.dumps(item.to_json(), sort_keys=True)


# --------------------------------------------------------------------------------------------
# Leak discipline
# --------------------------------------------------------------------------------------------


def test_transition_cannot_carry_tactic_text() -> None:
    """The sanitised record has no field that could hold the answer."""
    fields = set(ps.Transition.__dataclass_fields__)
    assert not fields & {"tactic", "annotated_tactic", "state_after"}


def test_no_tactic_annotation_or_answer_leaks_into_any_prompt(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        generator = ps.PremiseSelectionGenerator(world["index"], ps.GeneratorConfig(seed=20260907))
        checked = 0
        for transition, step in world["pairs"]:
            item = generator.generate(transition, level)
            if item is None:
                continue
            checked += 1
            assert ps.audit_item_leaks(item, step) == [], f"{level.name} {item.item_id}"
            prompt = item.prompt
            assert step.tactic not in prompt
            assert step.annotated_tactic not in prompt
            assert "<a>" not in prompt and "</a>" not in prompt
            assert "answer_index" not in prompt
            gold = item.options[item.answer_index].full_name
            body = prompt.split("## Proof state", 1)[-1].split("## Candidates", 1)[0]
            assert not ps.name_occurs_in(body, gold)
            # Every option name appears exactly once, in the option list only.
            for option in item.options:
                assert prompt.count(f". {option.full_name}") == 1
        assert checked > 0


def test_explicit_positive_level_states_the_relation_without_naming_it(
    world: dict[str, Any],
) -> None:
    level = ps.LEVELS_BY_NAME["L0_explicit_positive"]
    items = _generate(world, level)
    assert items
    for item in items:
        assert "## Stated relation" in item.prompt
        assert ps.REDACTION in item.prompt
    standard = _generate(world, ps.LEVELS_BY_NAME["L2_standard"])
    assert all("## Stated relation" not in item.prompt for item in standard)


def test_redact_name_removes_full_and_short_forms() -> None:
    text = "theorem Foo.bar_baz (x : T) : Foo.bar_baz x = bar_baz x"
    out = ps.redact_name(text, "Foo.bar_baz")
    assert "bar_baz" not in out
    assert out.count(ps.REDACTION) == 3


def test_name_occurs_in_is_token_anchored() -> None:
    assert not ps.name_occurs_in("the statement is elided", "em")
    assert not ps.name_occurs_in("the statement is elided", "id")
    assert ps.name_occurs_in("h : M.Indep X", "Matroid.Indep")
    assert ps.name_occurs_in("⊢ Nat.add_comm a b", "Nat.add_comm")


# --------------------------------------------------------------------------------------------
# Item well-formedness
# --------------------------------------------------------------------------------------------


def test_correct_option_is_present_exactly_once(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        items = _generate(world, level)
        assert items
        for item in items:
            assert len(item.options) == level.k
            assert sum(1 for o in item.options if o.tier == "gold") == 1
            assert item.options[item.answer_index].tier == "gold"
            names = [o.full_name for o in item.options]
            assert len(set(names)) == len(names)


def test_distractor_tiers_are_recorded_and_valid(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        items = _generate(world, level)
        assert items
        for item in items:
            tiers = [o.tier for o in item.options if o.tier != "gold"]
            assert len(tiers) == level.k - 1
            assert all(tier in ps.TIER_ORDER for tier in tiers)
            assert all(tier in level.tiers for tier in tiers)
            assert Counter(tiers) == Counter(item.features["distractor_tiers"])


def test_option_order_is_balanced_across_items(world: dict[str, Any]) -> None:
    for level in ps.LADDER:
        items = _generate(world, level)
        counts = Counter(item.answer_index for item in items)
        assert set(counts) <= set(range(level.k))
        expected = len(items) / level.k
        # Four standard deviations of a Binomial(n, 1/k) count.
        tolerance = 4.0 * math.sqrt(len(items) * (1 / level.k) * (1 - 1 / level.k))
        for index in range(level.k):
            assert abs(counts.get(index, 0) - expected) <= tolerance, (
                f"{level.name} index {index}: {counts.get(index, 0)} vs {expected:.1f}"
            )


def test_multi_premise_and_self_naming_steps_are_excluded() -> None:
    multi = ps.RawStep(
        proof_id="F.lean::t",
        step_index=0,
        tactic="simp [a, b]",
        annotated_tactic="simp [<a>A.a</a>, <a>B.b</a>]",
        state_before="⊢ True",
        state_after="",
        premises=(ps.PremiseRef("A.a", "A.lean"), ps.PremiseRef("B.b", "B.lean")),
    )
    assert not ps.is_usable(multi)

    self_naming = ps.RawStep(
        proof_id="F.lean::t",
        step_index=0,
        tactic="exact Foo.bar",
        annotated_tactic="exact <a>Foo.bar</a>",
        state_before="⊢ Foo.bar x = y",
        state_after="",
        premises=(ps.PremiseRef("Foo.bar", "A.lean"),),
    )
    assert not ps.is_usable(self_naming)

    ok = ps.RawStep(
        proof_id="F.lean::t",
        step_index=0,
        tactic="exact Foo.bar",
        annotated_tactic="exact <a>Foo.bar</a>",
        state_before="⊢ P x = y",
        state_after="",
        premises=(ps.PremiseRef("Foo.bar", "A.lean"),),
    )
    assert ps.is_usable(ok)


def test_trim_context_keeps_the_goal() -> None:
    state = "a : T\nb : U\nc : V\n⊢ P a b c"
    assert ps.trim_context(state, None) == state
    trimmed = ps.trim_context(state, 0)
    assert trimmed.endswith("⊢ P a b c")
    assert "a : T" not in trimmed
    assert "<local context elided>" in trimmed
    assert ps.trim_context(state, 1).count("\n") == 2


def test_ladder_is_a_confusability_gradient_not_a_size_gradient() -> None:
    names = [level.name for level in ps.LADDER]
    assert names == [
        "L0_explicit_positive",
        "L2_standard",
        "L3_same_module_freq_matched",
        "L4_high_similarity",
    ]
    assert ps.LEVELS_BY_NAME["L0_explicit_positive"].explicit_positive
    assert not any(level.explicit_positive for level in ps.LADDER[1:])
    hardest = ps.LEVELS_BY_NAME["L4_high_similarity"]
    easiest = ps.LEVELS_BY_NAME["L2_standard"]
    assert hardest.similarity_band_slack < easiest.similarity_band_slack
    assert hardest.freq_bucket_slack < easiest.freq_bucket_slack
    assert {level.k for level in ps.LADDER} == {6, 8}


def test_gate_failing_rung_is_not_in_the_shipped_ladder() -> None:
    """L1_cross_module failed its own shortcut gate and must not be usable for scoring."""
    rejected = {level.name for level in ps.REJECTED_LEVELS}
    assert "L1_cross_module" in rejected
    assert not rejected & {level.name for level in ps.LADDER}
    # Still constructible, so its rejection stays reproducible.
    assert set(ps.LEVELS_BY_NAME) == {level.name for level in ps.LADDER} | rejected


def test_import_closure_is_transitive() -> None:
    imports = {"a.lean": [], "b.lean": ["a.lean"], "c.lean": ["b.lean"]}
    file_bit, closure = ps.build_import_closure(imports)
    index = ps.PremiseIndex(file_bit=file_bit, import_closure=closure)
    assert index.in_scope("c.lean", "a.lean")
    assert index.in_scope("c.lean", "c.lean")
    assert not index.in_scope("a.lean", "c.lean")


# --------------------------------------------------------------------------------------------
# Bounded check against the real train split
# --------------------------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not REAL_TRAIN.exists(), reason="LeanDojo benchmark not present")
def test_real_train_prefix_is_clean_and_train_only() -> None:
    transitions, proof_premises, raws, stats = ps.load_train_transitions(
        REAL_TRAIN, limit_theorems=150
    )
    assert stats["theorems"] == 150
    assert transitions
    decls, imports = ps.load_corpus(REAL_BENCHMARK / "corpus.jsonl")
    usage: Counter[str] = Counter()
    def_path: dict[str, str] = {}
    for transition in transitions:
        usage[transition.premises[0].full_name] += 1
        def_path.setdefault(transition.premises[0].full_name, transition.premises[0].def_path)
    index = ps.build_index(usage, def_path, proof_premises, decls, imports)
    generator = ps.PremiseSelectionGenerator(index, ps.GeneratorConfig(seed=20260907))
    level = ps.LEVELS_BY_NAME["L2_standard"]
    seen = 0
    for transition, step in zip(transitions, raws, strict=True):
        assert transition.split == ps.PERMITTED_SPLIT
        item = generator.generate(transition, level)
        if item is None:
            continue
        seen += 1
        assert ps.audit_item_leaks(item, step) == []
        assert item.provenance["proof_id"] == f"{transition.file_path}::{transition.thm}"
    assert seen > 0
