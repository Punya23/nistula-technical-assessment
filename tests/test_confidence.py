"""
Unit tests for the confidence scoring engine.
"""

import pytest
from app.models.unified import UnifiedMessage
from app.services.confidence import calculate_confidence, _determine_action


class TestConfidenceScoring:
    """Tests for the confidence scoring engine."""

    def _make_message(self, **overrides) -> UnifiedMessage:
        """Helper to create test messages with defaults."""
        defaults = {
            "message_id": "test-id-123",
            "source": "whatsapp",
            "guest_name": "Test User",
            "message_text": "Is the villa available?",
            "timestamp": "2026-05-05T10:30:00Z",
            "booking_ref": "NIS-2024-0891",
            "property_id": "villa-b1",
            "query_type": "pre_sales_availability",
        }
        defaults.update(overrides)
        return UnifiedMessage(**defaults)

    def test_score_between_0_and_1(self):
        """Confidence score must always be between 0 and 1."""
        msg = self._make_message()
        score, _, _ = calculate_confidence(
            msg, 0.8, "Villa B1 is available for those dates!", {"availability": True}
        )
        assert 0 <= score <= 1

    def test_complaint_capped(self):
        """Complaints should have confidence capped at 0.55."""
        msg = self._make_message(
            query_type="complaint",
            message_text="The AC is not working. Unacceptable.",
        )
        score, breakdown, action = calculate_confidence(
            msg, 0.9, "We apologise for the inconvenience.", {"base_rate_inr": 18000}
        )
        assert score <= 0.55
        assert action == "escalate"

    def test_booking_ref_boosts_score(self):
        """Having a booking ref should increase confidence."""
        msg_with_ref = self._make_message(
            query_type="post_sales_checkin",
            message_text="What is the check-in time?",
            booking_ref="NIS-2024-0891",
        )
        msg_without_ref = self._make_message(
            query_type="post_sales_checkin",
            message_text="What is the check-in time?",
            booking_ref=None,
        )
        score_with, _, _ = calculate_confidence(
            msg_with_ref, 0.8, "Check-in is at 2 PM.",
            {"check_in_time": "2:00 PM", "check_out_time": "11:00 AM", "wifi_password": "Nistula@2024"},
        )
        score_without, _, _ = calculate_confidence(
            msg_without_ref, 0.8, "Check-in is at 2 PM.",
            {"check_in_time": "2:00 PM", "check_out_time": "11:00 AM", "wifi_password": "Nistula@2024"},
        )
        assert score_with > score_without

    def test_breakdown_included(self):
        """Confidence breakdown should contain scoring details."""
        msg = self._make_message()
        _, breakdown, _ = calculate_confidence(
            msg, 0.8, "Villa B1 is available!", {"availability": True}
        )
        assert "base_score" in breakdown
        assert "adjustments" in breakdown
        assert "final_score" in breakdown
        assert "action" in breakdown
        assert breakdown["base_score"] == 0.50

    def test_multiple_questions_reduce_score(self):
        """Messages with multiple questions should score lower."""
        msg_single = self._make_message(
            message_text="Is the villa available?",
        )
        msg_multi = self._make_message(
            message_text="Is the villa available? What is the rate? Can we check in early?",
        )
        score_single, _, _ = calculate_confidence(
            msg_single, 0.8, "Yes it is available!",
            {"availability": True},
        )
        score_multi, _, _ = calculate_confidence(
            msg_multi, 0.8, "Yes it is available and the rate is...",
            {"availability": True},
        )
        assert score_multi < score_single


class TestDetermineAction:
    """Tests for action determination from confidence scores."""

    def test_high_confidence_auto_sends(self):
        assert _determine_action(0.90, "pre_sales_availability") == "auto_send"

    def test_medium_confidence_agent_review(self):
        assert _determine_action(0.75, "pre_sales_availability") == "agent_review"

    def test_low_confidence_escalates(self):
        assert _determine_action(0.40, "pre_sales_availability") == "escalate"

    def test_complaint_always_escalates(self):
        assert _determine_action(0.95, "complaint") == "escalate"

    def test_boundary_085(self):
        """Score exactly at 0.85 should NOT auto_send (threshold is > 0.85)."""
        assert _determine_action(0.85, "general_enquiry") == "agent_review"

    def test_boundary_060(self):
        """Score exactly at 0.60 should be agent_review."""
        assert _determine_action(0.60, "general_enquiry") == "agent_review"
