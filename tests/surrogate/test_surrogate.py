from arena.surrogate.dataset import SurrogateDataset, SurrogateExample
from arena.surrogate.features import extract_features
from arena.surrogate.model import CalibratedSurrogate


def _dataset() -> SurrogateDataset:
    return SurrogateDataset.from_examples(
        SurrogateExample(f"candidate:{index}", {"explicit_scope": float(index)}, target)
        for index, target in enumerate((0.0, 0.0, 0.0, 1.0, 1.0, 1.0))
    )


def test_feature_extraction_is_stable_and_sorted() -> None:
    left = extract_features({"grammar": "sexpr", "scope": {"explicit": True}})
    right = extract_features({"scope": {"explicit": True}, "grammar": "sexpr"})
    assert left == right
    assert tuple(left) == tuple(sorted(left))


def test_deterministic_fallback_is_calibrated_probability_model() -> None:
    dataset = _dataset()
    first = CalibratedSurrogate(prefer_sklearn=False).fit(dataset)
    second = CalibratedSurrogate(prefer_sklearn=False).fit(dataset)

    low = first.predict({"explicit_scope": 0.0})
    high = first.predict({"explicit_scope": 5.0})
    assert 0.0 <= low.lower <= low.probability <= low.upper <= 1.0
    assert high.probability > low.probability
    assert first.predict_probability({"explicit_scope": 2.5}) == second.predict_probability(
        {"explicit_scope": 2.5}
    )
    assert first.backend == "deterministic-logistic-fallback"


def test_soft_targets_force_dependency_free_fallback() -> None:
    dataset = SurrogateDataset.from_examples(
        (
            SurrogateExample("a", {"x": 0.0}, 0.2),
            SurrogateExample("b", {"x": 1.0}, 0.8),
        )
    )
    model = CalibratedSurrogate(prefer_sklearn=True).fit(dataset)
    assert model.backend == "deterministic-logistic-fallback"
