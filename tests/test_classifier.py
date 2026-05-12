"""
Unit tests for the query type classifier.
"""

import pytest
from app.services.classifier import classify_query, get_classification_confidence


class TestClassifyQuery:
    """Tests for query type classification."""

    def test_availability_query(self):
        assert classify_query("Is the villa available from April 20 to 24?") == "pre_sales_availability"

    def test_pricing_query(self):
        assert classify_query("What is the rate per night for 2 adults?") == "pre_sales_pricing"

    def test_checkin_query(self):
        assert classify_query("What time can we check in? WiFi password?") == "post_sales_checkin"

    def test_special_request(self):
        assert classify_query("Can we get an early check-in at 10 AM?") == "special_request"

    def test_complaint(self):
        assert classify_query("The AC is not working. This is unacceptable.") == "complaint"

    def test_general_enquiry(self):
        assert classify_query("Do you allow pets?") == "general_enquiry"

    def test_refund_is_complaint(self):
        assert classify_query("I want a refund for tonight.") == "complaint"

    def test_airport_transfer_is_special(self):
        assert classify_query("Can you arrange an airport transfer?") == "special_request"

    def test_how_much_is_pricing(self):
        assert classify_query("How much does it cost for 3 nights?") == "pre_sales_pricing"

    def test_wifi_is_checkin(self):
        assert classify_query("What is the wifi password?") == "post_sales_checkin"


class TestClassificationConfidence:
    """Tests for classification confidence scoring."""

    def test_clear_query_high_confidence(self):
        """A clear, single-topic query should have high confidence."""
        score = get_classification_confidence(
            "Is the villa available on these dates?",
            "pre_sales_availability",
        )
        assert score >= 0.5

    def test_multi_topic_lower_confidence(self):
        """A message with multiple topics should have lower confidence."""
        score = get_classification_confidence(
            "Is the villa available? How much per night? Can we check in early?",
            "pre_sales_availability",
        )
        # Multiple categories match → ambiguity penalty
        assert score < 0.9

    def test_general_enquiry_moderate_confidence(self):
        """General enquiry (no keyword match) should have moderate confidence."""
        score = get_classification_confidence(
            "Do you allow pets?",
            "general_enquiry",
        )
        assert 0.3 <= score <= 0.7
