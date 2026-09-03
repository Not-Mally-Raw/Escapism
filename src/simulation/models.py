"""
Simulation specific models for ground-truth tracking and evaluation.
These models are explicitly separated from the production path (src/core).
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.core.models import MandateStateRecord

class SimulationRecord(BaseModel):
    """
    Wrapper for MandateStateRecord containing hidden evaluation labels.
    Never imported by guardrails or decision layer.
    """
    state: MandateStateRecord
    ground_truth_recoverable: bool = Field(
        description="Hidden ground truth label set independently at generation time (control outcome under NOOP)"
    )

class CausalSimulationRecord(BaseModel):
    """Causal ML training record with potential outcomes and propensity."""
    model_config = ConfigDict(frozen=True)
    
    state: MandateStateRecord
    observed_action: str = Field(description="Action taken by logging policy")
    observed_outcome: bool = Field(description="Did recovery succeed under observed action?")
    propensity: float = Field(ge=0.0, le=1.0, description="P(observed_action | state) under logging policy")
    true_cate: Dict[str, float] = Field(description="True CATE for each treatment action (DGP ground truth for PEHE evaluation)")
    ground_truth_recoverable: bool = Field(description="Unconfounded baseline outcome under NOOP (control)")
    potential_outcomes: Optional[Dict[str, bool]] = Field(default=None, description="Complete potential outcome vector Y(a) across actions")

