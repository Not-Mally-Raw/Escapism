"""
Machine Learning Subsystem for AI Revenue Recovery.
Provides trained recovery propensity estimation under strict anti-leakage boundaries.
"""
from src.ml.inference import predict_recovery_probability

__all__ = ["predict_recovery_probability"]
