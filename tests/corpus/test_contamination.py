import json
from pathlib import Path

import pytest

from arena.corpus.contamination import (
    MINICTX_MATHLIB_CONFIG,
    ContaminationRegistry,
    ContaminationViolation,
    SourceRecord,
    SplitCategory,
    load_source_registry,
)

REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / "artifacts" / "corpus" / "source_registry.json"
)


@pytest.fixture(scope="module")
def registry() -> ContaminationRegistry:
    return load_source_registry(REGISTRY_PATH)


def record(
    source_id: str,
    category: SplitCategory,
    *,
    never_train: bool = False,
    derived_from: tuple[str, ...] = (),
    licence_blocker: bool = False,
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
        category=category,
        never_train=never_train,
        licence="MIT",
        derived_from=derived_from,
        licence_blocker=licence_blocker,
    )


# -- registry loading -----------------------------------------------------------------


def test_real_source_registry_loads_and_validates(registry: ContaminationRegistry) -> None:
    assert registry.require("mathlib4").category is SplitCategory.HISTORICALLY_EXPOSED
    assert registry.require("GSM8K").never_train is True
    assert len(registry.sources) == 28  # 27 registered sources plus the miniCTX config node


def test_loader_rejects_a_foreign_schema(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema": "something-else", "sources": []}), encoding="utf-8")
    with pytest.raises(ContaminationViolation, match="schema"):
        load_source_registry(path)


# -- transitive exposure --------------------------------------------------------------


@pytest.mark.parametrize(
    "source_id",
    [
        "mathlib4",
        "LeanDojo Benchmark 4 (data release)",
        "FormL4 (Process-Driven Autoformalization in Lean 4)",
        MINICTX_MATHLIB_CONFIG,
    ],
)
def test_mathlib_and_its_derivatives_are_exposed(
    registry: ContaminationRegistry, source_id: str
) -> None:
    assert registry.is_exposed(source_id) is True


def test_derivative_exposure_names_the_burned_ancestor(registry: ContaminationRegistry) -> None:
    reasons = registry.exposure_reasons("LeanDojo Benchmark 4 (data release)")
    assert any("mathlib4" in reason for reason in reasons)


def test_exposure_closure_is_multi_hop(registry: ContaminationRegistry) -> None:
    # mathlib4 -> LeanDojo Benchmark 4 -> a hypothetical premise slice two hops away.
    extended = registry.with_sources(
        [
            record(
                "premise-slice",
                SplitCategory.TRAINING_CANDIDATE,
                derived_from=("LeanDojo Benchmark 4 (data release)",),
            )
        ]
    )
    assert extended.derivation_ancestors("premise-slice") == frozenset(
        {"LeanDojo Benchmark 4 (data release)", "mathlib4"}
    )
    assert extended.is_exposed("premise-slice") is True


def test_a_clean_source_is_not_exposed(registry: ContaminationRegistry) -> None:
    assert registry.is_exposed("miniCTX-v2") is False


def test_unregistered_derivation_parent_is_refused() -> None:
    with pytest.raises(ContaminationViolation, match="unregistered source"):
        ContaminationRegistry.from_records(
            [record("child", SplitCategory.DEVELOPMENT, derived_from=("ghost",))]
        )


def test_derivation_cycle_is_refused() -> None:
    with pytest.raises(ContaminationViolation, match="cycle"):
        ContaminationRegistry.from_records(
            [
                record("a", SplitCategory.TRAINING_CANDIDATE, derived_from=("b",)),
                record("b", SplitCategory.TRAINING_CANDIDATE, derived_from=("a",)),
            ]
        )


def test_duplicate_source_ids_are_refused() -> None:
    with pytest.raises(ContaminationViolation, match="duplicate"):
        ContaminationRegistry.from_records(
            [record("a", SplitCategory.DEVELOPMENT), record("a", SplitCategory.OOD)]
        )


def test_an_exposed_source_cannot_be_registered_as_ood() -> None:
    with pytest.raises(ContaminationViolation, match="OOD"):
        ContaminationRegistry.from_records(
            [
                record("parent", SplitCategory.HISTORICALLY_EXPOSED),
                record("child", SplitCategory.OOD, derived_from=("parent",)),
            ]
        )


# -- never-train enforcement ----------------------------------------------------------


def test_unknown_source_is_never_trainable(registry: ContaminationRegistry) -> None:
    assert registry.may_train("some dataset nobody registered") is False
    with pytest.raises(ContaminationViolation, match="not a registered source"):
        registry.require_trainable("some dataset nobody registered")


@pytest.mark.parametrize("source_id", ["GSM8K", "miniCTX-v2", "PutnamBench", "PRM800K"])
def test_never_train_sources_are_refused(registry: ContaminationRegistry, source_id: str) -> None:
    assert registry.may_train(source_id) is False


def test_licence_blocked_source_is_refused(registry: ContaminationRegistry) -> None:
    refusals = registry.training_refusals("NaturalProofs")
    assert any("licence blocker" in reason for reason in refusals)


def test_derivative_of_a_sealed_source_is_refused(registry: ContaminationRegistry) -> None:
    refusals = registry.training_refusals(MINICTX_MATHLIB_CONFIG)
    assert any("derived from miniCTX-v2, which is RESERVED_EVAL" in r for r in refusals)


def test_source_a_sealed_evaluation_was_built_from_is_refused(
    registry: ContaminationRegistry,
) -> None:
    refusals = registry.training_refusals("ProofNet (original)")
    assert any("ProofNet-Verified is derived from it" in reason for reason in refusals)


def test_a_never_train_ancestor_propagates_downward() -> None:
    small = ContaminationRegistry.from_records(
        [
            record("sealed", SplitCategory.ASSURANCE_ONLY, never_train=True),
            record("derivative", SplitCategory.TRAINING_CANDIDATE, derived_from=("sealed",)),
        ]
    )
    assert small.may_train("derivative") is False
    assert small.training_refusals("derivative") == ("derived from sealed, which is never-train",)


def test_a_clean_registered_source_is_trainable(registry: ContaminationRegistry) -> None:
    assert registry.may_train("mathlib4") is True
    registry.require_trainable("mathlib4")


# -- no silent reclassification -------------------------------------------------------


@pytest.mark.parametrize(
    "category", [SplitCategory.OOD, SplitCategory.PROMOTION, SplitCategory.RESERVED_EVAL]
)
def test_exposed_source_cannot_be_reclassified_as_clean(
    registry: ContaminationRegistry, category: SplitCategory
) -> None:
    with pytest.raises(ContaminationViolation, match="cannot reclassify"):
        registry.reclassify("mathlib4", category)


def test_transitively_exposed_source_cannot_be_reclassified_as_ood(
    registry: ContaminationRegistry,
) -> None:
    with pytest.raises(ContaminationViolation, match="cannot reclassify"):
        registry.reclassify("LeanDojo Benchmark 4 (data release)", SplitCategory.OOD)


def test_reclassification_to_a_non_clean_category_is_allowed(
    registry: ContaminationRegistry,
) -> None:
    moved = registry.reclassify("mathlib4", SplitCategory.ASSURANCE_ONLY)
    assert moved.require("mathlib4").category is SplitCategory.ASSURANCE_ONLY
    # The original registry is untouched.
    assert registry.require("mathlib4").category is SplitCategory.HISTORICALLY_EXPOSED


def test_with_sources_cannot_launder_an_exposed_source(
    registry: ContaminationRegistry,
) -> None:
    laundered = SourceRecord(
        source_id="LeanDojo Benchmark 4 (data release)",
        category=SplitCategory.OOD,
        licence="CC BY 2.0",
        derived_from=("mathlib4",),
    )
    with pytest.raises(ContaminationViolation, match="exposed"):
        registry.with_sources([laundered])
