"""
Integration tests for the /webhook/message endpoint.

Tests the full pipeline: payload validation → normalisation →
classification → AI drafting → confidence scoring → response.

These tests use FastAPI's TestClient (no server needed).
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


# --- Test Payloads ---

# Test 1: Pre-sales availability query (from assessment brief)
AVAILABILITY_PAYLOAD = {
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1",
}

# Test 2: Post-sales check-in query
CHECKIN_PAYLOAD = {
    "source": "booking_com",
    "guest_name": "Priya Menon",
    "message": "What time can we check in tomorrow? Also, what is the WiFi password?",
    "timestamp": "2026-05-06T14:15:00Z",
    "booking_ref": "NIS-2024-0925",
    "property_id": "villa-b1",
}

# Test 3: Complaint (should always escalate)
COMPLAINT_PAYLOAD = {
    "source": "whatsapp",
    "guest_name": "Vikram Patel",
    "message": "The AC is not working in the master bedroom. This is unacceptable. I want a refund for tonight.",
    "timestamp": "2026-05-07T03:00:00Z",
    "booking_ref": "NIS-2024-0950",
    "property_id": "villa-b1",
}

# Test 4: Special request
SPECIAL_REQUEST_PAYLOAD = {
    "source": "airbnb",
    "guest_name": "Sarah Johnson",
    "message": "We would like to arrange an early check-in around 10 AM if possible. Also, can you arrange an airport transfer from Dabolim?",
    "timestamp": "2026-05-08T09:00:00Z",
    "booking_ref": "NIS-2024-0960",
    "property_id": "villa-b1",
}

# Test 5: General enquiry
GENERAL_ENQUIRY_PAYLOAD = {
    "source": "instagram",
    "guest_name": "Ankit Gupta",
    "message": "Do you allow pets? We have a small dog.",
    "timestamp": "2026-05-09T11:30:00Z",
    "booking_ref": None,
    "property_id": "villa-b1",
}


class TestWebhookEndpoint:
    """Tests for POST /webhook/message"""

    def test_availability_query(self):
        """Test processing a pre-sales availability query."""
        response = client.post("/webhook/message", json=AVAILABILITY_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert "message_id" in data
        assert "query_type" in data
        assert "drafted_reply" in data
        assert "confidence_score" in data
        assert "action" in data
        assert 0 <= data["confidence_score"] <= 1
        assert data["action"] in ["auto_send", "agent_review", "escalate"]

    def test_checkin_query(self):
        """Test processing a post-sales check-in query."""
        response = client.post("/webhook/message", json=CHECKIN_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert data["query_type"] == "post_sales_checkin"
        assert data["drafted_reply"]  # Not empty
        assert 0 <= data["confidence_score"] <= 1

    def test_complaint_always_escalates(self):
        """Test that complaints always result in 'escalate' action."""
        response = client.post("/webhook/message", json=COMPLAINT_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert data["query_type"] == "complaint"
        assert data["action"] == "escalate"
        assert data["confidence_score"] <= 0.60

    def test_special_request(self):
        """Test processing a special request."""
        response = client.post("/webhook/message", json=SPECIAL_REQUEST_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert data["query_type"] == "special_request"
        assert data["drafted_reply"]

    def test_general_enquiry(self):
        """Test processing a general enquiry."""
        response = client.post("/webhook/message", json=GENERAL_ENQUIRY_PAYLOAD)
        assert response.status_code == 200

        data = response.json()
        assert data["drafted_reply"]
        assert 0 <= data["confidence_score"] <= 1


class TestValidation:
    """Tests for input validation."""

    def test_missing_required_field(self):
        """Test that missing required fields return 422."""
        payload = {
            "source": "whatsapp",
            # missing guest_name, message, timestamp
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 422

    def test_invalid_source_channel(self):
        """Test that invalid source channels return 422."""
        payload = {
            "source": "telegram",  # Not a supported channel
            "guest_name": "Test User",
            "message": "Hello",
            "timestamp": "2026-05-05T10:30:00Z",
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 422

    def test_empty_message(self):
        """Test that empty messages return 422."""
        payload = {
            "source": "whatsapp",
            "guest_name": "Test User",
            "message": "",
            "timestamp": "2026-05-05T10:30:00Z",
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 422

    def test_optional_fields_missing(self):
        """Test that optional fields (booking_ref, property_id) can be omitted."""
        payload = {
            "source": "direct",
            "guest_name": "Jane Doe",
            "message": "Do you have any villas available in December?",
            "timestamp": "2026-05-10T08:00:00Z",
        }
        response = client.post("/webhook/message", json=payload)
        assert response.status_code == 200


class TestHealthCheck:
    """Tests for GET /health"""

    def test_health_check(self):
        """Test that health check returns status info."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "claude_model" in data


class TestResponseStructure:
    """Tests for response format compliance."""

    def test_response_has_all_required_fields(self):
        """Test that every response contains all fields from the spec."""
        response = client.post("/webhook/message", json=AVAILABILITY_PAYLOAD)
        data = response.json()

        required_fields = [
            "message_id",
            "query_type",
            "drafted_reply",
            "confidence_score",
            "action",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_confidence_breakdown_present(self):
        """Test that confidence breakdown is included for transparency."""
        response = client.post("/webhook/message", json=AVAILABILITY_PAYLOAD)
        data = response.json()

        # confidence_breakdown is optional but should be present
        assert "confidence_breakdown" in data
