"""
Unit tests for the message normalizer.
"""

import pytest
from app.models.webhook import WebhookPayload
from app.services.normalizer import normalize_message


class TestNormalizeMessage:
    """Tests for webhook payload normalisation."""

    def test_basic_normalisation(self):
        """Test that a standard payload is normalised correctly."""
        payload = WebhookPayload(
            source="whatsapp",
            guest_name="Rahul Sharma",
            message="Is the villa available?",
            timestamp="2026-05-05T10:30:00Z",
            booking_ref="NIS-2024-0891",
            property_id="villa-b1",
        )
        unified = normalize_message(payload)

        assert unified.message_id  # UUID generated
        assert unified.source == "whatsapp"
        assert unified.guest_name == "Rahul Sharma"
        assert unified.message_text == "Is the villa available?"
        assert unified.timestamp == "2026-05-05T10:30:00Z"
        assert unified.booking_ref == "NIS-2024-0891"
        assert unified.property_id == "villa-b1"
        assert unified.query_type  # Should be classified

    def test_unique_message_ids(self):
        """Test that each normalised message gets a unique ID."""
        payload = WebhookPayload(
            source="whatsapp",
            guest_name="Test User",
            message="Hello",
            timestamp="2026-05-05T10:30:00Z",
        )
        id1 = normalize_message(payload).message_id
        id2 = normalize_message(payload).message_id
        assert id1 != id2

    def test_booking_com_prefix_stripped(self):
        """Test that Booking.com message prefixes are removed."""
        payload = WebhookPayload(
            source="booking_com",
            guest_name="Test User",
            message="Guest message: Is the villa available?",
            timestamp="2026-05-05T10:30:00Z",
        )
        unified = normalize_message(payload)
        assert not unified.message_text.startswith("Guest message:")

    def test_optional_fields_default_none(self):
        """Test that missing optional fields default to None."""
        payload = WebhookPayload(
            source="direct",
            guest_name="Jane Doe",
            message="Hello",
            timestamp="2026-05-05T10:30:00Z",
        )
        unified = normalize_message(payload)
        assert unified.booking_ref is None
        assert unified.property_id is None

    def test_whitespace_stripped(self):
        """Test that leading/trailing whitespace is removed."""
        payload = WebhookPayload(
            source="whatsapp",
            guest_name="Test User",
            message="  Hello world  ",
            timestamp="2026-05-05T10:30:00Z",
        )
        unified = normalize_message(payload)
        assert unified.message_text == "Hello world"
