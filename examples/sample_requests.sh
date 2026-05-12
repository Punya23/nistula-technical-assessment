#!/bin/bash
# ============================================================
# Nistula Guest Message Handler — Sample Requests
# ============================================================
# Run the server first: uvicorn app.main:app --reload
# Then execute these curl commands to test different scenarios.
# ============================================================

BASE_URL="http://localhost:8000"

echo "============================================"
echo "  Nistula Guest Message Handler — Test Suite"
echo "============================================"
echo ""

# --- Health Check ---
echo "1. Health Check"
echo "---"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

# --- Test 1: Pre-sales Availability (from assessment brief) ---
echo "2. Pre-Sales Availability Query (WhatsApp)"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "guest_name": "Rahul Sharma",
    "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
    "timestamp": "2026-05-05T10:30:00Z",
    "booking_ref": "NIS-2024-0891",
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

# --- Test 2: Post-Sales Check-In (Booking.com) ---
echo "3. Post-Sales Check-In Query (Booking.com)"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "booking_com",
    "guest_name": "Priya Menon",
    "message": "What time can we check in tomorrow? Also, what is the WiFi password?",
    "timestamp": "2026-05-06T14:15:00Z",
    "booking_ref": "NIS-2024-0925",
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

# --- Test 3: Complaint (should escalate) ---
echo "4. Complaint (WhatsApp) — Should Escalate"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "guest_name": "Vikram Patel",
    "message": "The AC is not working in the master bedroom. This is unacceptable. I want a refund for tonight.",
    "timestamp": "2026-05-07T03:00:00Z",
    "booking_ref": "NIS-2024-0950",
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

# --- Test 4: Special Request (Airbnb) ---
echo "5. Special Request (Airbnb)"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "airbnb",
    "guest_name": "Sarah Johnson",
    "message": "We would like to arrange an early check-in around 10 AM if possible. Also, can you arrange an airport transfer from Dabolim?",
    "timestamp": "2026-05-08T09:00:00Z",
    "booking_ref": "NIS-2024-0960",
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

# --- Test 5: General Enquiry (Instagram) ---
echo "6. General Enquiry (Instagram)"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "instagram",
    "guest_name": "Ankit Gupta",
    "message": "Do you allow pets? We have a small dog.",
    "timestamp": "2026-05-09T11:30:00Z",
    "booking_ref": null,
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

# --- Test 6: Pricing Query (Direct) ---
echo "7. Pricing Query (Direct)"
echo "---"
curl -s -X POST "$BASE_URL/webhook/message" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "direct",
    "guest_name": "Meera Krishnan",
    "message": "How much would it cost for 5 guests for 3 nights in December?",
    "timestamp": "2026-05-10T16:45:00Z",
    "property_id": "villa-b1"
  }' | python3 -m json.tool
echo ""
echo ""

echo "============================================"
echo "  All tests complete!"
echo "  Also try the interactive API docs at:"
echo "  $BASE_URL/docs"
echo "============================================"
