"""
Production Inference API for Recovery Propensity Estimation.
Provides thin, pure, and deterministic inference with strict anti-leakage protection.
"""
from pathlib import Path
from typing import Any, Dict, Optional, Union
import joblib
import numpy as np

from src.core.models import MandateStateRecord
from src.ml.features import FEATURE_COLUMNS_ALL, extract_features

_MODEL_PATH = Path(__file__).parent / "models" / "recovery_propensity_pipeline.joblib"
_CACHED_PIPELINE: Optional[Any] = None


def get_model_pipeline(model_path: Optional[Path] = None):
    """
    Loads and caches the serialized scikit-learn recovery propensity pipeline.
    """
    global _CACHED_PIPELINE
    path = model_path or _MODEL_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Trained model artifact not found at {path}. "
            "Please run 'python src/ml/train.py' first."
        )
    if _CACHED_PIPELINE is None or model_path is not None:
        loaded = joblib.load(path)
        if model_path is None:
            _CACHED_PIPELINE = loaded
        return loaded
    return _CACHED_PIPELINE


def features_to_array(feat_dict: Dict[str, Any]) -> np.ndarray:
    """Converts a feature dictionary into a 2D numpy array with fixed column ordering."""
    row = [feat_dict[col] for col in FEATURE_COLUMNS_ALL]
    return np.array([row], dtype=object)


def predict_recovery_probability(
    record: Union[MandateStateRecord, Dict[str, Any]],
    model_path: Optional[Path] = None,
) -> float:
    """
    Computes calibrated P(recovery | state) for a single mandate case.

    Anti-Leakage Guarantee:
        Strictly rejects any input containing 'ground_truth_recoverable' or related fields.
        Only uses observable features defined in MandateStateRecord.

    PCI-DSS Guarantee:
        Strictly rejects raw cardholder data (PAN) or prohibited PII.

    Args:
        record: MandateStateRecord domain model or observable feature dictionary.
        model_path: Optional custom path to serialized pipeline artifact (for testing/benchmarks).

    Returns:
        float: Estimated recovery probability in [0.0, 1.0].
    """
    # 1. Extract schema-constrained feature dict (will raise ValueError on leakage or PII)
    feat_dict = extract_features(record)

    # 2. Convert to numpy array for pipeline preprocessing
    X = features_to_array(feat_dict)

    # 3. Predict probability using fitted estimator
    pipeline = get_model_pipeline(model_path)
    probs = pipeline.predict_proba(X)
    p_recoverable = float(probs[0, 1])

    # Ensure clean float clipping in [0.0, 1.0]
    return max(0.0, min(1.0, p_recoverable))
