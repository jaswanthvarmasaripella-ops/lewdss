"""
Models package for LEWDSS (SIH26001).
Provides spatial cross-validation, evaluation metrics, and training pipelines.
"""

from src.models.spatial_cv import (
    FEATURE_SET_1,
    FEATURE_SET_2,
    FEATURE_SET_3,
    FEATURE_SETS,
    OUTER_FOLDS,
    get_outer_splits,
    get_inner_splits,
)
from src.models.metrics import (
    compute_classification_metrics,
    optimize_threshold,
    spatial_cluster_bootstrap,
)

__all__ = [
    "FEATURE_SET_1",
    "FEATURE_SET_2",
    "FEATURE_SET_3",
    "FEATURE_SETS",
    "OUTER_FOLDS",
    "get_outer_splits",
    "get_inner_splits",
    "compute_classification_metrics",
    "optimize_threshold",
    "spatial_cluster_bootstrap",
]
