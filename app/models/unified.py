"""
Unified message schema.

All inbound messages are normalised into this schema before
being passed to the AI drafter, regardless of source channel.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# Query type classifications as defined in the assessment brief
QueryType = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
]


class UnifiedMessage(BaseModel):
    """
    Normalised message schema — the single format used throughout the pipeline.

    Every inbound message, regardless of source channel, is transformed
    into this schema before classification and AI processing.
    """

    message_id: str = Field(
        ...,
        description="Generated UUID for this message",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],
    )
    source: str = Field(
        ...,
        description="Originating channel",
        examples=["whatsapp"],
    )
    guest_name: str = Field(
        ...,
        description="Guest's display name",
        examples=["Rahul Sharma"],
    )
    message_text: str = Field(
        ...,
        description="Normalised message text",
        examples=["Is the villa available from April 20 to 24?"],
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp",
        examples=["2026-05-05T10:30:00Z"],
    )
    booking_ref: Optional[str] = Field(
        default=None,
        description="Booking reference if available",
    )
    property_id: Optional[str] = Field(
        default=None,
        description="Property identifier",
    )
    query_type: QueryType = Field(
        ...,
        description="Classified query type",
        examples=["pre_sales_availability"],
    )
