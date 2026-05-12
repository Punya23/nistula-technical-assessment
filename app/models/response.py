"""API response models."""

from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field



ActionType = Literal["auto_send", "agent_review", "escalate"]


class WebhookResponse(BaseModel):
    """Response after processing a guest message."""

    message_id: str = Field(
        ...,
        description="UUID of the processed message",
    )
    query_type: str = Field(
        ...,
        description="Classified query type",
        examples=["pre_sales_availability"],
    )
    drafted_reply: str = Field(
        ...,
        description="AI-generated reply to the guest",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1",
    )
    action: ActionType = Field(
        ...,
        description="Recommended action based on confidence score",
    )
    confidence_breakdown: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Detailed breakdown of confidence score factors (debug info)",
    )


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details",
    )
