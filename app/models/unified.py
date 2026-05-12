"""Unified message schema — all messages get normalised into this."""

from typing import Optional, Literal
from pydantic import BaseModel, Field



QueryType = Literal[
    "pre_sales_availability",
    "pre_sales_pricing",
    "post_sales_checkin",
    "special_request",
    "complaint",
    "general_enquiry",
]


class UnifiedMessage(BaseModel):
    """Normalised message format used across the pipeline."""

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
