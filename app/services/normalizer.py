"""Normalises webhook payloads into the unified message schema."""

import uuid
from app.models.webhook import WebhookPayload
from app.models.unified import UnifiedMessage
from app.services.classifier import classify_query


def normalize_message(payload: WebhookPayload) -> UnifiedMessage:
    """
    Transform a raw webhook payload into the unified message schema.

    This is the single entry point for all inbound messages. It:
    1. Generates a unique message ID
    2. Maps channel-specific fields to the unified schema
    3. Classifies the query type
    4. Returns a clean, consistent UnifiedMessage

    Args:
        payload: Raw webhook payload from any supported channel.

    Returns:
        UnifiedMessage with all fields normalised and query classified.
    """
    # Generate a unique ID for tracking this message through the pipeline
    message_id = str(uuid.uuid4())


    message_text = _normalise_text(payload.message, payload.source)


    query_type = classify_query(message_text)

    return UnifiedMessage(
        message_id=message_id,
        source=payload.source,
        guest_name=payload.guest_name,
        message_text=message_text,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=query_type,
    )


def _normalise_text(message: str, source: str) -> str:
    """
    Clean and normalise message text based on the source channel.

    Different channels may include formatting artifacts, emojis,
    or encoding quirks. This function produces clean, consistent text.

    Args:
        message: Raw message text.
        source: Source channel identifier.

    Returns:
        Cleaned message text.
    """
    # Strip leading/trailing whitespace
    text = message.strip()


    if source == "whatsapp":
        # WhatsApp formatting kept as-is
        pass
    elif source == "booking_com":
        # Strip auto-generated prefixes from Booking.com
        prefixes_to_strip = [
            "Guest message: ",
            "New message from guest: ",
        ]
        for prefix in prefixes_to_strip:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
    elif source == "airbnb":

        pass
    elif source == "instagram":

        pass
    elif source == "direct":

        pass

    return text
