"""
Scikit-learn Preprocessing and Classification Pipeline for Recovery Propensity.
Builds an end-to-end ColumnTransformer + LogisticRegression estimator on numpy arrays.
"""
from typing import Any, Optional
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.ml.features import (
    FEATURE_COLUMNS_ALL,
    FEATURE_COLUMNS_CATEGORICAL,
    FEATURE_COLUMNS_NUMERIC,
)

CAT_INDICES = list(range(len(FEATURE_COLUMNS_CATEGORICAL)))
NUM_INDICES = list(range(len(FEATURE_COLUMNS_CATEGORICAL), len(FEATURE_COLUMNS_ALL)))


def build_recovery_pipeline(
    C: float = 1.0,
    class_weight: Optional[Any] = None,
    random_state: int = 42,
) -> Pipeline:
    """
    Constructs the standard scikit-learn pipeline for recovery propensity modeling.

    Statistical Strategy (Option A):
        Default class_weight=None to avoid double-weighting penalties on top of
        the sample-level oversampling of rare failure classes (LEGAL_HOLD).

    Args:
        C: Inverse of regularization strength (float > 0).
        class_weight: Optional class re-weighting parameter. Default None.
        random_state: Random seed for deterministic reproducibility.

    Returns:
        Pipeline: Untrained scikit-learn Pipeline instance.
    """
    categorical_transformer = OneHotEncoder(
        handle_unknown="ignore",
        sparse_output=False,
    )

    numeric_transformer = StandardScaler()

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", categorical_transformer, CAT_INDICES),
            ("num", numeric_transformer, NUM_INDICES),
        ],
        remainder="drop",
    )

    classifier = LogisticRegression(
        C=C,
        class_weight=class_weight,
        max_iter=1000,
        random_state=random_state,
        solver="lbfgs",
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )
