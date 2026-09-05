"""A small calibrated survival surrogate with an optional sklearn backend."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist, fmean
from typing import Any

from arena.surrogate.dataset import SurrogateDataset
from arena.surrogate.features import FeatureSchema


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


@dataclass(frozen=True, slots=True)
class SurrogatePrediction:
    probability: float
    lower: float
    upper: float
    uncertainty: float
    backend: str


class CalibratedSurrogate:
    """Predict hard-gate survival probability, never mathematical truth.

    When sklearn and adequate binary data are available, stratified sigmoid calibration
    wraps logistic regression.  Otherwise a deterministic, regularized logistic model
    supports soft targets and small datasets.
    """

    def __init__(
        self,
        *,
        prefer_sklearn: bool = True,
        random_state: int = 0,
        regularization: float = 1e-3,
    ) -> None:
        self.prefer_sklearn = prefer_sklearn
        self.random_state = random_state
        self.regularization = regularization
        self.backend = "unfitted"
        self.schema: FeatureSchema | None = None
        self._model: Any = None
        self._means: list[float] = []
        self._scales: list[float] = []
        self._weights: list[float] = []
        self._bias = 0.0
        self._sample_count = 0
        self._base_rate = 0.5

    def fit(self, dataset: SurrogateDataset) -> CalibratedSurrogate:
        features, targets, sample_weights = dataset.matrix()
        self.schema = dataset.schema
        self._sample_count = len(targets)
        self._base_rate = sum(
            target * weight for target, weight in zip(targets, sample_weights, strict=True)
        ) / sum(sample_weights)
        if (
            self.prefer_sklearn
            and set(targets) <= {0.0, 1.0}
            and len(set(targets)) == 2
            and self._fit_sklearn(features, targets, sample_weights)
        ):
            return self
        self._fit_fallback(features, targets, sample_weights)
        return self

    def _fit_sklearn(
        self,
        features: list[list[float]],
        targets: list[float],
        sample_weights: list[float],
    ) -> bool:
        try:
            from sklearn.calibration import CalibratedClassifierCV
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import StratifiedKFold
        except ImportError:
            return False
        integer_targets = [int(value) for value in targets]
        minority = min(integer_targets.count(0), integer_targets.count(1))
        if minority < 2:
            return False
        folds = min(3, minority)
        splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=self.random_state)
        estimator = LogisticRegression(
            random_state=self.random_state,
            solver="liblinear",
            max_iter=1000,
        )
        model = CalibratedClassifierCV(estimator, method="sigmoid", cv=splitter)
        try:
            model.fit(features, integer_targets, sample_weight=sample_weights)
        except (TypeError, ValueError):
            return False
        self._model = model
        self.backend = "sklearn-calibrated-logistic"
        return True

    def _fit_fallback(
        self,
        features: list[list[float]],
        targets: list[float],
        sample_weights: list[float],
    ) -> None:
        dimension = len(features[0]) if features else 0
        self._means = [fmean(row[index] for row in features) for index in range(dimension)]
        self._scales = []
        for index, mean in enumerate(self._means):
            variance = fmean((row[index] - mean) ** 2 for row in features)
            self._scales.append(math.sqrt(variance) if variance > 1e-18 else 1.0)
        normalized = [
            [(value - self._means[index]) / self._scales[index] for index, value in enumerate(row)]
            for row in features
        ]
        self._weights = [0.0] * dimension
        smoothed_rate = (sum(targets) + 0.5) / (len(targets) + 1.0)
        self._bias = math.log(smoothed_rate / (1.0 - smoothed_rate))
        weight_total = sum(sample_weights)
        for step in range(1200):
            gradient = [0.0] * dimension
            bias_gradient = 0.0
            for row, target, sample_weight in zip(normalized, targets, sample_weights, strict=True):
                score = self._bias + sum(
                    weight * value for weight, value in zip(self._weights, row, strict=True)
                )
                residual = (_sigmoid(score) - target) * sample_weight
                bias_gradient += residual
                for index, value in enumerate(row):
                    gradient[index] += residual * value
            learning_rate = 0.25 / math.sqrt(1.0 + step / 100.0)
            self._bias -= learning_rate * bias_gradient / weight_total
            for index in range(dimension):
                regularized = (
                    gradient[index] / weight_total + self.regularization * self._weights[index]
                )
                self._weights[index] -= learning_rate * regularized
        self.backend = "deterministic-logistic-fallback"

    def _check_fitted(self) -> None:
        if self.schema is None or self.backend == "unfitted":
            raise RuntimeError("surrogate must be fitted before prediction")

    def predict_probability(self, features: Mapping[str, float]) -> float:
        self._check_fitted()
        assert self.schema is not None
        row = list(self.schema.transform(features))
        if self._model is not None:
            probability = float(self._model.predict_proba([row])[0][1])
        else:
            normalized = [
                (value - self._means[index]) / self._scales[index]
                for index, value in enumerate(row)
            ]
            probability = _sigmoid(
                self._bias
                + sum(
                    weight * value for weight, value in zip(self._weights, normalized, strict=True)
                )
            )
            # Small-sample empirical calibration: shrink toward observed prevalence.
            probability = (self._sample_count * probability + 2.0 * self._base_rate) / (
                self._sample_count + 2.0
            )
        return min(1.0, max(0.0, probability))

    def predict(
        self, features: Mapping[str, float], *, confidence: float = 0.95
    ) -> SurrogatePrediction:
        probability = self.predict_probability(features)
        z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
        effective_n = max(1, self._sample_count)
        standard_error = math.sqrt(probability * (1.0 - probability) / effective_n)
        lower = max(0.0, probability - z * standard_error)
        upper = min(1.0, probability + z * standard_error)
        return SurrogatePrediction(probability, lower, upper, upper - lower, self.backend)

    def predict_many(
        self, rows: Mapping[str, Mapping[str, float]]
    ) -> dict[str, SurrogatePrediction]:
        return {candidate_id: self.predict(rows[candidate_id]) for candidate_id in sorted(rows)}


SurrogateModel = CalibratedSurrogate


def brier_score(probabilities: list[float], targets: list[float]) -> float:
    if not probabilities or len(probabilities) != len(targets):
        raise ValueError("probabilities and targets must have equal non-zero length")
    return fmean(
        (probability - target) ** 2
        for probability, target in zip(probabilities, targets, strict=True)
    )
