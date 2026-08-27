"""
Domain Models for Track 3 Expected-Value Decision Optimizer.
Enforces frozen immutability (extra="forbid") and exact Decimal monetary precision.
Citing: docs/knowledge_base/PS3_Locked_System_Specification.md §4.1
"""
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from src.core.types import ActionType


class CandidateScore(BaseModel):
    """
    Score evaluation details for a single candidate action.
    All monetary and probability calculations use exact Decimal types.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: ActionType
    multiplier: Decimal
    cost_inr: Decimal
    p_hat: Decimal
    lift_probability: Decimal
    lift_ev_inr: Decimal
    cleared_threshold: bool


class DecisionAuditStep(BaseModel):
    """
    Audit trail step matching PS3_Locked_System_Specification.md §4.1 schema.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: int = Field(default=3, description="Pipeline step index (3 = Decision Layer)")
    timestamp: str = Field(description="ISO 8601 evaluation timestamp")
    module: str = Field(default="DECISION_LAYER", description="Emitting module name")
    guardrails_evaluated: List[str] = Field(
        default_factory=lambda: [
            "MASK_ATTEMPTS",
            "MASK_SPACING",
            "MASK_WINDOW",
            "MASK_AFA",
            "MASK_FPC",
            "MASK_LEGAL",
            "MASK_CONSENT",
        ],
        description="List of evaluated constraint identifiers",
    )
    verdict: str = Field(description="Selected action or terminal routing state")
    rationale: str = Field(description="Human-readable decision trace")


class DecisionResult(BaseModel):
    """
    Structured optimization output returned by the decision engine.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    selected_action: ActionType
    is_mandatory_routing: bool = Field(
        description="True if routed directly by compliance invariants (e.g. Legal Hold) bypassing EV scoring"
    )
    lift_ev_inr: Optional[Decimal] = Field(
        default=None,
        description="Expected rupee lift over noop for the selected action (None for mandatory compliance routing)",
    )
    p_hat: Optional[Decimal] = Field(
        default=None,
        description="Point estimate of recovery probability from Track 1 (None for mandatory compliance routing)",
    )
    cost_inr: Optional[Decimal] = Field(
        default=None,
        description="Direct cost in INR of the selected action (None for mandatory compliance routing)",
    )
    candidate_scores: List[CandidateScore] = Field(
        default_factory=list,
        description="Detailed evaluation records for all feasible candidate recovery actions",
    )
    audit_step: DecisionAuditStep
    execution_timestamp: str
