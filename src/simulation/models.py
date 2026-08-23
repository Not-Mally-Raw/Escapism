"""
Simulation specific models for ground-truth tracking and evaluation.
These models are explicitly separated from the production path (src/core).
"""
from pydantic import BaseModel, Field
from src.core.models import MandateStateRecord

class SimulationRecord(BaseModel):
    """
    Wrapper for MandateStateRecord containing hidden evaluation labels.
    Never imported by guardrails or decision layer.
    """
    state: MandateStateRecord
    ground_truth_recoverable: bool = Field(
        description="Hidden ground truth label set independently at generation time"
    )
