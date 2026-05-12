"""
Inbound webhook payload model.

Validates the raw payload received from external channels
(WhatsApp, Booking.com, Airbnb, Instagram, Direct).
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# Supported source channels
SourceChannel = Literal["whatsapp", "booking_com", "airbnb", "instagram", "direct"]


class WebhookPayload(BaseModel):
    """
    Raw inbound message from any channel.

    Example:
        {
            "source": "whatsapp",
            "guest_name": "Rahul Sharma",
            "message": "Is the villa available from April 20 to 24?",
            "timestamp": "2026-05-05T10:30:00Z",
            "booking_ref": "NIS-2024-0891",
            "property_id": "villa-b1"
        }
    """

    source: SourceChannel = Field(
        ...,
        description="Channel the message originated from",
        examples=["whatsapp", "booking_com", "airbnb"],
    )
    guest_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Guest's display name",
        examples=["Rahul Sharma"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Raw message text from the guest",
        examples=["Is the villa available from April 20 to 24?"],
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 timestamp of when the message was sent",
        examples=["2026-05-05T10:30:00Z"],
    )
    booking_ref: Optional[str] = Field(
        default=None,
        description="Booking reference if available",
        examples=["NIS-2024-0891"],
    )
    property_id: Optional[str] = Field(
        default=None,
        description="Property identifier",
        examples=["villa-b1"],
    )
