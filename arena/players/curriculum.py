"""Curriculum player facade."""

from arena.tasks.curriculum import (
    AcquisitionScore,
    AcquisitionWeights,
    InformationCurriculum,
    TaskPerformance,
    acquisition_score,
    expected_ranking_information_gain,
    performance_table,
    representation_performance_variance,
)

CurriculumPlayer = InformationCurriculum

__all__ = [
    "AcquisitionScore",
    "AcquisitionWeights",
    "CurriculumPlayer",
    "InformationCurriculum",
    "TaskPerformance",
    "acquisition_score",
    "expected_ranking_information_gain",
    "performance_table",
    "representation_performance_variance",
]
